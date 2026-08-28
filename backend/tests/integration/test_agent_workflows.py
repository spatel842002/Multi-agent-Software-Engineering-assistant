from __future__ import annotations

from pathlib import Path

import pytest

from app.models.patch import PatchStatus
from app.models.repository import Repository, RepositoryStatus
from app.models.user import User
from app.services.agents.workflows import run_bug_investigation, run_patch_proposal, run_repo_qa
from app.services.ingestion.service import index_repository_files
from app.services.llm.ports import ChatMessage
from app.services.llm.providers import FakeChatProvider
from app.services.retrieval.embeddings import FakeEmbeddingProvider
from tests.fixtures.fake_vector_store import InMemoryVectorStore

pytestmark = pytest.mark.asyncio

FIXTURE_REPO = Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"


@pytest.fixture
async def owner(db_session):
    user = User(email="workflow-owner@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def indexed_repository(db_session, owner):
    repo = Repository(
        owner_id=owner.id,
        name="sample-repo",
        source_url="https://example.com/sample-repo.git",
        status=RepositoryStatus.INDEXING,
    )
    db_session.add(repo)
    await db_session.commit()
    await db_session.refresh(repo)

    embedder = FakeEmbeddingProvider(dimensions=32)
    vector_store = InMemoryVectorStore()
    await index_repository_files(
        db_session, repository=repo, root_path=FIXTURE_REPO, embedder=embedder, vector_store=vector_store
    )
    repo.status = RepositoryStatus.READY
    await db_session.commit()
    return repo, embedder, vector_store


def _cited_responder(messages: list[ChatMessage]) -> str:
    return "The divide function can raise ZeroDivisionError.\nCitations: [1]"


async def test_repo_qa_answers_with_a_resolvable_citation(db_session, owner, indexed_repository):
    repo, embedder, vector_store = indexed_repository
    chat = FakeChatProvider(responder=_cited_responder)

    result = await run_repo_qa(
        db_session,
        owner_id=owner.id,
        repository_id=repo.id,
        question="What happens if you divide by zero?",
        embedder=embedder,
        vector_store=vector_store,
        chat_provider=chat,
    )

    assert result.answer
    assert result.citations, "expected at least one citation"
    for c in result.citations:
        assert c.file_path in {"calculator.py", "README.md"}
        assert c.start_line <= c.end_line
    assert result.prompt_version == "repo_qa.v1"


async def test_bug_investigation_returns_grounded_diagnosis(db_session, owner, indexed_repository):
    repo, embedder, vector_store = indexed_repository
    chat = FakeChatProvider(responder=_cited_responder)

    result = await run_bug_investigation(
        db_session,
        owner_id=owner.id,
        repository_id=repo.id,
        bug_description="Users report a crash with ZeroDivisionError when dividing.",
        embedder=embedder,
        vector_store=vector_store,
        chat_provider=chat,
    )

    assert result.citations
    assert result.prompt_version == "bug_investigation.v1"


async def test_patch_proposal_halts_at_pending_approval_and_never_executes(
    db_session, owner, indexed_repository
):
    repo, embedder, vector_store = indexed_repository

    def responder(messages: list[ChatMessage]) -> str:
        return (
            "--- a/calculator.py\n+++ b/calculator.py\n"
            "@@ -1,1 +1,1 @@\n-def divide(a, b):\n+def divide(a, b):\n"
            "    if b == 0:\n        raise ValueError('b must not be zero')\n"
            "Test command: pytest tests/test_calculator.py -q\n"
            "Citations: [1]"
        )

    chat = FakeChatProvider(responder=responder)

    result = await run_patch_proposal(
        db_session,
        owner_id=owner.id,
        repository_id=repo.id,
        task_description="Guard divide() against division by zero.",
        embedder=embedder,
        vector_store=vector_store,
        chat_provider=chat,
    )

    assert result.patch_proposal_id is not None

    from sqlalchemy import select

    from app.models.patch import PatchProposal

    proposal = (
        await db_session.execute(select(PatchProposal).where(PatchProposal.id == result.patch_proposal_id))
    ).scalar_one()

    assert proposal.status == PatchStatus.PENDING_APPROVAL
    assert proposal.test_command == "pytest tests/test_calculator.py -q"
    assert "divide" in proposal.diff_text


async def test_patch_proposal_unwraps_markdown_fences_and_backticked_test_command(
    db_session, owner, indexed_repository
):
    """Regression test for a real failure observed against a live local Ollama
    model: it wrapped the diff in a ```diff fence and the test command in
    backticks, which broke `git apply` (fence markers aren't valid diff
    content) and would have made the sandbox execute a backtick-quoted shell
    command-substitution instead of running pytest.
    """
    repo, embedder, vector_store = indexed_repository

    def responder(messages: list[ChatMessage]) -> str:
        return (
            "```diff\n"
            "--- a/calculator.py\n+++ b/calculator.py\n"
            "@@ -1,1 +1,1 @@\n-def divide(a, b):\n+def divide(a, b):\n"
            "```\n\n"
            "Test command: `pytest tests/test_calculator.py -q`\n"
            "Citations: [1]"
        )

    chat = FakeChatProvider(responder=responder)

    result = await run_patch_proposal(
        db_session,
        owner_id=owner.id,
        repository_id=repo.id,
        task_description="Guard divide() against division by zero.",
        embedder=embedder,
        vector_store=vector_store,
        chat_provider=chat,
    )

    from sqlalchemy import select

    from app.models.patch import PatchProposal

    proposal = (
        await db_session.execute(select(PatchProposal).where(PatchProposal.id == result.patch_proposal_id))
    ).scalar_one()

    assert "```" not in proposal.diff_text
    assert proposal.diff_text.startswith("--- a/calculator.py")
    assert proposal.test_command == "pytest tests/test_calculator.py -q"
