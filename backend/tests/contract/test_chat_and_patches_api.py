from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.asyncio

FIXTURE_REPO = Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"


@pytest.fixture
async def ready_repository(db_session, authed_user):
    """A repository owned by `authed_user`, indexed against the shared fixture
    repo, using the SAME embedder/vector-store the API routes will resolve
    via `get_embedding_provider()` / `get_vector_store()` in `LLM_PROVIDER=fake`
    mode -- so a chat request made over HTTP retrieves real chunks.
    """
    _token, user = authed_user

    from app.models.repository import Repository, RepositoryStatus
    from app.services.ingestion.service import index_repository_files
    from app.services.retrieval.embeddings import get_embedding_provider
    from app.services.retrieval.vector_store import get_vector_store

    repo = Repository(
        owner_id=user.id,
        name="sample-repo",
        source_url="https://example.com/sample-repo.git",
        status=RepositoryStatus.INDEXING,
    )
    db_session.add(repo)
    await db_session.commit()
    await db_session.refresh(repo)

    await index_repository_files(
        db_session,
        repository=repo,
        root_path=FIXTURE_REPO,
        embedder=get_embedding_provider(),
        vector_store=get_vector_store(),
    )
    repo.status = RepositoryStatus.READY
    await db_session.commit()
    await db_session.refresh(repo)
    return repo


async def test_qa_endpoint_returns_grounded_answer(client, authed_user, ready_repository):
    token, _user = authed_user
    resp = await client.post(
        f"/api/v1/repositories/{ready_repository.id}/qa",
        json={"question": "What does the divide function do?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"]
    assert body["prompt_version"] == "repo_qa.v1"
    assert isinstance(body["citations"], list)


async def test_qa_endpoint_requires_auth(client, ready_repository):
    resp = await client.post(
        f"/api/v1/repositories/{ready_repository.id}/qa",
        json={"question": "test"},
    )
    assert resp.status_code == 401


async def test_qa_endpoint_not_owned_is_404(client, ready_repository):
    other_email = "other-qa-owner@example.com"
    other_password = "correct-horse-battery-y"
    await client.post("/api/v1/auth/register", json={"email": other_email, "password": other_password})
    login = await client.post("/api/v1/auth/login", json={"email": other_email, "password": other_password})
    other_token = login.json()["access_token"]

    resp = await client.post(
        f"/api/v1/repositories/{ready_repository.id}/qa",
        json={"question": "test"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404


async def test_patch_proposal_endpoint_creates_pending_approval(client, authed_user, ready_repository):
    token, _user = authed_user
    resp = await client.post(
        f"/api/v1/repositories/{ready_repository.id}/patch-proposals",
        json={"task_description": "Guard divide() against division by zero."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["patch_proposal_id"] is not None

    patch_id = body["patch_proposal_id"]
    get_resp = await client.get(
        f"/api/v1/patch-proposals/{patch_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "pending_approval"


async def test_patch_decision_endpoint_rejects(client, authed_user, ready_repository):
    token, _user = authed_user
    propose = await client.post(
        f"/api/v1/repositories/{ready_repository.id}/patch-proposals",
        json={"task_description": "Guard divide() against division by zero."},
        headers={"Authorization": f"Bearer {token}"},
    )
    patch_id = propose.json()["patch_proposal_id"]

    decision = await client.post(
        f"/api/v1/patch-proposals/{patch_id}/decision",
        json={"decision": "reject", "reason": "not needed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "rejected"


async def test_patch_proposal_not_owned_is_404(client, authed_user, ready_repository, db_session):
    from app.models.user import User

    other = User(email="patch-not-mine@example.com", hashed_password="x")
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    token, _user = authed_user
    propose = await client.post(
        f"/api/v1/repositories/{ready_repository.id}/patch-proposals",
        json={"task_description": "Guard divide() against division by zero."},
        headers={"Authorization": f"Bearer {token}"},
    )
    patch_id = propose.json()["patch_proposal_id"]

    # Register and log in as a second, unrelated user and try to read the first user's proposal.
    other_email = "second-real-user@example.com"
    await client.post(
        "/api/v1/auth/register", json={"email": other_email, "password": "correct-horse-battery-x"}
    )
    other_login = await client.post(
        "/api/v1/auth/login", json={"email": other_email, "password": "correct-horse-battery-x"}
    )
    other_token = other_login.json()["access_token"]

    resp = await client.get(
        f"/api/v1/patch-proposals/{patch_id}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert resp.status_code == 404
