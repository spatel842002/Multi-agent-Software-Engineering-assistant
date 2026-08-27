from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def test_create_repository_requires_auth(client):
    resp = await client.post(
        "/api/v1/repositories", json={"name": "x", "source_url": "https://example.com/x.git"}
    )
    assert resp.status_code == 401


async def test_create_repository_returns_202_pending(client, authed_user):
    token, _user = authed_user
    resp = await client.post(
        "/api/v1/repositories",
        json={"name": "my-repo", "source_url": "https://example.com/my-repo.git"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["name"] == "my-repo"
    assert body["status"] == "pending"
    assert body["file_count"] == 0


async def test_list_repositories_only_returns_the_caller_s_own(client, authed_user, db_session):
    token, user = authed_user

    from app.models.repository import Repository, RepositoryStatus
    from app.models.user import User

    other_user = User(email="other-owner@example.com", hashed_password="x")
    db_session.add(other_user)
    await db_session.flush()

    mine = Repository(
        owner_id=user.id,
        name="mine",
        source_url="https://example.com/mine.git",
        status=RepositoryStatus.READY,
    )
    theirs = Repository(
        owner_id=other_user.id,
        name="theirs",
        source_url="https://example.com/theirs.git",
        status=RepositoryStatus.READY,
    )
    db_session.add_all([mine, theirs])
    await db_session.commit()

    resp = await client.get("/api/v1/repositories", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    names = {r["name"] for r in resp.json()}
    assert names == {"mine"}


async def test_get_repository_not_owned_is_404_not_403(client, authed_user, db_session):
    token, _user = authed_user

    from app.models.repository import Repository, RepositoryStatus
    from app.models.user import User

    other_user = User(email="not-mine-owner@example.com", hashed_password="x")
    db_session.add(other_user)
    await db_session.flush()
    theirs = Repository(
        owner_id=other_user.id,
        name="theirs",
        source_url="https://example.com/theirs.git",
        status=RepositoryStatus.READY,
    )
    db_session.add(theirs)
    await db_session.commit()
    await db_session.refresh(theirs)

    resp = await client.get(f"/api/v1/repositories/{theirs.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


async def test_get_nonexistent_repository_is_404(client, authed_user):
    token, _user = authed_user
    resp = await client.get(
        f"/api/v1/repositories/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
