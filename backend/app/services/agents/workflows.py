"""The three required workflows, each built as a `WorkflowGraph`:

1. `run_repo_qa`            -- retrieval-grounded Q&A over an ingested repo.
2. `run_bug_investigation`  -- same retrieval, a diagnosis-focused prompt.
3. `run_patch_proposal`     -- retrieval + a proposed diff, which halts the
   graph at a `PENDING_APPROVAL` `PatchProposal` row. Nothing past that point
   (applying the diff, running tests) is reachable from here; see
   `services/patch/service.py` for the human-gated continuation.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.telemetry import LLM_REQUEST_ERRORS, LLM_REQUEST_LATENCY_SECONDS
from app.models.conversation import Citation, Conversation, Message, MessageRole, WorkflowType
from app.models.patch import PatchProposal
from app.services.agents.citations import ResolvedCitation, resolve_citations
from app.services.agents.diff_extraction import extract_diff_text
from app.services.agents.graph import GraphContext, GraphNode, WorkflowGraph
from app.services.agents.prompts import (
    BUG_INVESTIGATION_PROMPT_VERSION,
    BUG_INVESTIGATION_SYSTEM_PROMPT,
    PATCH_PROPOSAL_PROMPT_VERSION,
    PATCH_PROPOSAL_SYSTEM_PROMPT,
    REPO_QA_PROMPT_VERSION,
    REPO_QA_SYSTEM_PROMPT,
    build_context_block,
)
from app.services.llm.ports import ChatCompletion, ChatMessage, ChatProvider
from app.services.retrieval.hybrid import hybrid_retrieve
from app.services.retrieval.ports import EmbeddingProvider, VectorStore

logger = get_logger(__name__)


async def _complete_with_metrics(
    chat_provider: ChatProvider, messages: list[ChatMessage], *, workflow: str
) -> ChatCompletion:
    provider_label = get_settings().llm_provider
    try:
        completion = await chat_provider.complete(messages)
    except Exception:
        LLM_REQUEST_ERRORS.labels(workflow=workflow, provider=provider_label).inc()
        raise
    LLM_REQUEST_LATENCY_SECONDS.labels(workflow=workflow, provider=provider_label).observe(
        completion.latency_ms / 1000
    )
    return completion


@dataclass(frozen=True)
class WorkflowResult:
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    citations: list[ResolvedCitation]
    prompt_version: str
    latency_ms: int
    patch_proposal_id: uuid.UUID | None = None


async def _retrieve_and_build_excerpts(
    db: AsyncSession,
    *,
    repository_id: uuid.UUID,
    query: str,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    top_k: int,
) -> tuple[str, dict[int, ResolvedCitation]]:
    hits = await hybrid_retrieve(
        db,
        repository_id=repository_id,
        query=query,
        embedder=embedder,
        vector_store=vector_store,
        top_k=top_k,
    )
    excerpts_by_index = {
        i + 1: ResolvedCitation(
            file_path=h.chunk.file_path,
            start_line=h.chunk.start_line,
            end_line=h.chunk.end_line,
            chunk_id=h.chunk.id,
        )
        for i, h in enumerate(hits)
    }
    context_block = build_context_block(
        [
            (i + 1, h.chunk.file_path, h.chunk.start_line, h.chunk.end_line, h.chunk.content)
            for i, h in enumerate(hits)
        ]
    )
    return context_block, excerpts_by_index


async def _run_retrieval_grounded_workflow(
    db: AsyncSession,
    *,
    owner_id: uuid.UUID,
    repository_id: uuid.UUID,
    workflow_type: WorkflowType,
    system_prompt: str,
    prompt_version: str,
    query: str,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    chat_provider: ChatProvider,
    top_k: int = 8,
) -> WorkflowResult:
    context_block, excerpts_by_index = await _retrieve_and_build_excerpts(
        db,
        repository_id=repository_id,
        query=query,
        embedder=embedder,
        vector_store=vector_store,
        top_k=top_k,
    )

    conversation = Conversation(
        owner_id=owner_id, repository_id=repository_id, workflow_type=workflow_type, title=query[:200]
    )
    db.add(conversation)
    await db.flush()
    db.add(Message(conversation_id=conversation.id, role=MessageRole.USER, content=query))

    user_prompt = f"Question: {query}\n\nRetrieved excerpts:\n\n{context_block or '(no excerpts retrieved)'}"

    async def _generate(ctx: GraphContext) -> None:
        completion = await _complete_with_metrics(
            chat_provider,
            [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt),
            ],
            workflow=workflow_type.value,
        )
        ctx.data["completion"] = completion

    graph = WorkflowGraph(workflow_type.value, [GraphNode("generate", _generate)])
    ctx = await graph.run(GraphContext())
    completion = cast(ChatCompletion, ctx.data["completion"])

    resolved = resolve_citations(completion.content, excerpts_by_index)

    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=completion.content,
        prompt_version=prompt_version,
        latency_ms=completion.latency_ms,
    )
    db.add(assistant_message)
    await db.flush()

    for citation in resolved:
        db.add(
            Citation(
                message_id=assistant_message.id,
                chunk_id=citation.chunk_id,
                file_path=citation.file_path,
                start_line=citation.start_line,
                end_line=citation.end_line,
            )
        )

    await db.commit()

    return WorkflowResult(
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        answer=completion.content,
        citations=resolved,
        prompt_version=prompt_version,
        latency_ms=completion.latency_ms,
    )


async def run_repo_qa(
    db: AsyncSession,
    *,
    owner_id: uuid.UUID,
    repository_id: uuid.UUID,
    question: str,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    chat_provider: ChatProvider,
) -> WorkflowResult:
    return await _run_retrieval_grounded_workflow(
        db,
        owner_id=owner_id,
        repository_id=repository_id,
        workflow_type=WorkflowType.REPO_QA,
        system_prompt=REPO_QA_SYSTEM_PROMPT,
        prompt_version=REPO_QA_PROMPT_VERSION,
        query=question,
        embedder=embedder,
        vector_store=vector_store,
        chat_provider=chat_provider,
    )


async def run_bug_investigation(
    db: AsyncSession,
    *,
    owner_id: uuid.UUID,
    repository_id: uuid.UUID,
    bug_description: str,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    chat_provider: ChatProvider,
) -> WorkflowResult:
    return await _run_retrieval_grounded_workflow(
        db,
        owner_id=owner_id,
        repository_id=repository_id,
        workflow_type=WorkflowType.BUG_INVESTIGATION,
        system_prompt=BUG_INVESTIGATION_SYSTEM_PROMPT,
        prompt_version=BUG_INVESTIGATION_PROMPT_VERSION,
        query=bug_description,
        embedder=embedder,
        vector_store=vector_store,
        chat_provider=chat_provider,
    )


_TEST_COMMAND_RE = re.compile(r"Test command:\s*(.+)", re.IGNORECASE)
_BACKTICK_WRAPPED_RE = re.compile(r"^`+(.*?)`+$")


def _clean_test_command(raw: str) -> str:
    """Strips markdown code-span backticks the model wraps the command in.

    This matters beyond cosmetics: the command is run via `subprocess.run(...,
    shell=True)` in the sandbox, and a leading/trailing backtick is POSIX
    shell command-substitution syntax, not a no-op -- leaving them in would
    silently change what actually executes.
    """
    cleaned = raw.strip()
    match = _BACKTICK_WRAPPED_RE.match(cleaned)
    return match.group(1).strip() if match else cleaned


async def run_patch_proposal(
    db: AsyncSession,
    *,
    owner_id: uuid.UUID,
    repository_id: uuid.UUID,
    task_description: str,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    chat_provider: ChatProvider,
) -> WorkflowResult:
    """Runs retrieval + patch generation, then HALTS: it persists a
    `PatchProposal` with status `PENDING_APPROVAL` and returns. No diff is
    ever applied or executed as part of this call.
    """
    context_block, excerpts_by_index = await _retrieve_and_build_excerpts(
        db,
        repository_id=repository_id,
        query=task_description,
        embedder=embedder,
        vector_store=vector_store,
        top_k=8,
    )

    conversation = Conversation(
        owner_id=owner_id,
        repository_id=repository_id,
        workflow_type=WorkflowType.PATCH_PROPOSAL,
        title=task_description[:200],
    )
    db.add(conversation)
    await db.flush()
    db.add(Message(conversation_id=conversation.id, role=MessageRole.USER, content=task_description))

    user_prompt = (
        f"Task: {task_description}\n\nRetrieved excerpts:\n\n{context_block or '(no excerpts retrieved)'}"
    )

    completion = await _complete_with_metrics(
        chat_provider,
        [
            ChatMessage(role="system", content=PATCH_PROPOSAL_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ],
        workflow=WorkflowType.PATCH_PROPOSAL.value,
    )

    resolved = resolve_citations(completion.content, excerpts_by_index)

    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=completion.content,
        prompt_version=PATCH_PROPOSAL_PROMPT_VERSION,
        latency_ms=completion.latency_ms,
    )
    db.add(assistant_message)
    await db.flush()
    for citation in resolved:
        db.add(
            Citation(
                message_id=assistant_message.id,
                chunk_id=citation.chunk_id,
                file_path=citation.file_path,
                start_line=citation.start_line,
                end_line=citation.end_line,
            )
        )

    test_command_match = _TEST_COMMAND_RE.search(completion.content)
    test_command = _clean_test_command(test_command_match.group(1)) if test_command_match else None

    patch_proposal = PatchProposal(
        conversation_id=conversation.id,
        repository_id=repository_id,
        diff_text=extract_diff_text(completion.content),
        target_files=sorted({c.file_path for c in resolved}),
        rationale=completion.content,
        test_command=test_command,
    )
    db.add(patch_proposal)
    await db.commit()
    await db.refresh(patch_proposal)

    logger.info("patch_proposal_created", patch_proposal_id=str(patch_proposal.id), status="pending_approval")

    return WorkflowResult(
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        answer=completion.content,
        citations=resolved,
        prompt_version=PATCH_PROPOSAL_PROMPT_VERSION,
        latency_ms=completion.latency_ms,
        patch_proposal_id=patch_proposal.id,
    )
