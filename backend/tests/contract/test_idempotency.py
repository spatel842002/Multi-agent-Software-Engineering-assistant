from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_repeating_a_create_with_the_same_idempotency_key_does_not_create_a_second_repository(
    client, authed_user
):
    token, _user = authed_user
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "retry-key-1"}
    payload = {"name": "my-repo", "source_url": "https://example.com/my-repo.git"}

    first = await client.post("/api/v1/repositories", json=payload, headers=headers)
    second = await client.post("/api/v1/repositories", json=payload, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]

    listing = await client.get("/api/v1/repositories", headers={"Authorization": f"Bearer {token}"})
    assert len(listing.json()) == 1


async def test_reusing_an_idempotency_key_with_a_different_body_is_a_conflict(client, authed_user):
    token, _user = authed_user
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "retry-key-2"}

    first = await client.post(
        "/api/v1/repositories",
        json={"name": "repo-a", "source_url": "https://example.com/a.git"},
        headers=headers,
    )
    second = await client.post(
        "/api/v1/repositories",
        json={"name": "repo-b", "source_url": "https://example.com/b.git"},
        headers=headers,
    )

    assert first.status_code == 202
    assert second.status_code == 409


async def test_without_an_idempotency_key_each_request_creates_a_new_repository(client, authed_user):
    token, _user = authed_user
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"name": "no-key-repo", "source_url": "https://example.com/no-key.git"}

    first = await client.post("/api/v1/repositories", json=payload, headers=headers)
    second = await client.post("/api/v1/repositories", json=payload, headers=headers)

    assert first.json()["id"] != second.json()["id"]
