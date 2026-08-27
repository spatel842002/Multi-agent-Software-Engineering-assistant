from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_health_ok(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_ready_reports_database_check(client):
    resp = await client.get("/api/v1/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["checks"]["database"] is True
