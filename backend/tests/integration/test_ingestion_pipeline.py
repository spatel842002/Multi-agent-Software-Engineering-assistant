from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.models.repository import Repository, RepositoryStatus
from app.models.user import User
from app.services.ingestion.service import index_repository_files
from app.services.retrieval.embeddings import FakeEmbeddingProvider
from app.services.retrieval.hybrid import hybrid_retrieve
from tests.fixtures.fake_vector_store import InMemoryVectorStore

pytestmark = pytest.mark.asyncio

FIXTURE_REPO = Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"


@pytest.fixture
async def owner(db_session):
    user = User(email="owner@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def repository(db_session, owner):
    repo = Repository(
        owner_id=owner.id,
        name="sample-repo",
        source_url="https://example.com/sample-repo.git",
        status=RepositoryStatus.INDEXING,
    )
    db_session.add(repo)
    await db_session.commit()
    await db_session.refresh(repo)
    return repo


async def test_index_repository_files_extracts_files_symbols_and_chunks(db_session, repository):
    embedder = FakeEmbeddingProvider(dimensions=32)
    vector_store = InMemoryVectorStore()

    result = await index_repository_files(
        db_session,
        repository=repository,
        root_path=FIXTURE_REPO,
        embedder=embedder,
        vector_store=vector_store,
    )

    assert result.file_count == 2  # calculator.py + README.md
    assert result.symbol_count >= 4  # add, divide, Calculator, Calculator.add, Calculator.reset
    assert result.chunk_count >= 2


async def test_hybrid_retrieve_finds_the_divide_function_by_keyword(db_session, repository):
    embedder = FakeEmbeddingProvider(dimensions=32)
    vector_store = InMemoryVectorStore()
    await index_repository_files(
        db_session,
        repository=repository,
        root_path=FIXTURE_REPO,
        embedder=embedder,
        vector_store=vector_store,
    )

    hits = await hybrid_retrieve(
        db_session,
        repository_id=repository.id,
        query="divide function ZeroDivisionError",
        embedder=embedder,
        vector_store=vector_store,
        top_k=3,
    )

    assert hits, "expected at least one retrieved chunk"
    assert any("divide" in h.chunk.content for h in hits)
    # Every retrieved chunk must resolve to a real file/line span in the fixture repo.
    for hit in hits:
        assert hit.chunk.file_path in {"calculator.py", "README.md"}
        assert hit.chunk.start_line <= hit.chunk.end_line


async def test_hybrid_retrieve_returns_empty_for_unrelated_repository(db_session, repository):
    embedder = FakeEmbeddingProvider(dimensions=32)
    vector_store = InMemoryVectorStore()
    await index_repository_files(
        db_session,
        repository=repository,
        root_path=FIXTURE_REPO,
        embedder=embedder,
        vector_store=vector_store,
    )

    hits = await hybrid_retrieve(
        db_session,
        repository_id=uuid.uuid4(),  # a repository that was never indexed
        query="divide function",
        embedder=embedder,
        vector_store=vector_store,
        top_k=3,
    )
    assert hits == []
