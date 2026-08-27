from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_owned_repository
from app.db.session import get_db
from app.models.repository import Repository
from app.models.user import User
from app.schemas.chat import (
    BugInvestigationRequest,
    CitationResponse,
    PatchProposalRequest,
    QuestionRequest,
    WorkflowResponse,
)
from app.services.agents.workflows import (
    WorkflowResult,
    run_bug_investigation,
    run_patch_proposal,
    run_repo_qa,
)
from app.services.llm.providers import get_chat_provider
from app.services.retrieval.embeddings import get_embedding_provider
from app.services.retrieval.vector_store import get_vector_store

router = APIRouter(prefix="/repositories/{repository_id}", tags=["chat"])


def _to_response(result: WorkflowResult) -> WorkflowResponse:
    return WorkflowResponse(
        conversation_id=result.conversation_id,
        message_id=result.message_id,
        answer=result.answer,
        citations=[
            CitationResponse(file_path=c.file_path, start_line=c.start_line, end_line=c.end_line)
            for c in result.citations
        ],
        prompt_version=result.prompt_version,
        latency_ms=result.latency_ms,
        patch_proposal_id=result.patch_proposal_id,
    )


@router.post("/qa", response_model=WorkflowResponse)
async def ask_question(
    body: QuestionRequest,
    repository: Repository = Depends(get_owned_repository),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    result = await run_repo_qa(
        db,
        owner_id=current_user.id,
        repository_id=repository.id,
        question=body.question,
        embedder=get_embedding_provider(),
        vector_store=get_vector_store(),
        chat_provider=get_chat_provider(),
    )
    return _to_response(result)


@router.post("/bug-investigations", response_model=WorkflowResponse)
async def investigate_bug(
    body: BugInvestigationRequest,
    repository: Repository = Depends(get_owned_repository),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    result = await run_bug_investigation(
        db,
        owner_id=current_user.id,
        repository_id=repository.id,
        bug_description=body.bug_description,
        embedder=get_embedding_provider(),
        vector_store=get_vector_store(),
        chat_provider=get_chat_provider(),
    )
    return _to_response(result)


@router.post("/patch-proposals", response_model=WorkflowResponse)
async def propose_patch(
    body: PatchProposalRequest,
    repository: Repository = Depends(get_owned_repository),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    result = await run_patch_proposal(
        db,
        owner_id=current_user.id,
        repository_id=repository.id,
        task_description=body.task_description,
        embedder=get_embedding_provider(),
        vector_store=get_vector_store(),
        chat_provider=get_chat_provider(),
    )
    return _to_response(result)
