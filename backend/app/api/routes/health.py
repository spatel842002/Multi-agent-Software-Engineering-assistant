from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe: process is up. Does not touch dependencies."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    """Readiness probe: process can actually serve traffic, i.e. its
    dependencies (database, at minimum) are reachable.
    """
    checks: dict[str, bool] = {}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    ready_state = all(checks.values())
    return {"ready": ready_state, "checks": checks}
