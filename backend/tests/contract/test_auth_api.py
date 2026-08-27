from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_register_then_login_then_me(client):
    register = await client.post(
        "/api/v1/auth/register", json={"email": "dev@example.com", "password": "correct-horse-battery-staple"}
    )
    assert register.status_code == 201
    assert register.json()["email"] == "dev@example.com"

    login = await client.post(
        "/api/v1/auth/login", json={"email": "dev@example.com", "password": "correct-horse-battery-staple"}
    )
    assert login.status_code == 200
    tokens = login.json()
    assert tokens["token_type"] == "bearer"

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "dev@example.com"


async def test_register_duplicate_email_is_conflict(client):
    payload = {"email": "dup@example.com", "password": "correct-horse-battery-staple"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


async def test_login_wrong_password_is_unauthorized(client):
    payload = {"email": "wrongpw@example.com", "password": "correct-horse-battery-staple"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post(
        "/api/v1/auth/login", json={"email": payload["email"], "password": "not-the-password"}
    )
    assert resp.status_code == 401


async def test_me_without_token_is_unauthorized(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_refresh_rotates_token_and_old_token_is_rejected(client):
    payload = {"email": "rotate@example.com", "password": "correct-horse-battery-staple"}
    await client.post("/api/v1/auth/register", json=payload)
    login = await client.post("/api/v1/auth/login", json=payload)
    original_refresh = login.json()["refresh_token"]

    first_refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
    assert first_refresh.status_code == 200
    new_refresh_token = first_refresh.json()["refresh_token"]
    assert new_refresh_token != original_refresh

    # Reusing the now-rotated-away original token must be rejected (reuse detection).
    reuse_attempt = await client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
    assert reuse_attempt.status_code == 401

    # And reuse detection revokes the whole chain, so even the *new* token,
    # issued from the compromised one, stops working.
    chain_broken = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh_token})
    assert chain_broken.status_code == 401


async def test_refresh_with_garbage_token_is_unauthorized(client):
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 401
