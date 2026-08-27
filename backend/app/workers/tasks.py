"""Celery tasks. Each task is a thin synchronous wrapper around an
`async def _*_async` function that does the real work with its own dedicated
database engine -- Celery workers are separate OS processes from the FastAPI
app and must not share its connection pool.

The wrapper always runs its coroutine on a fresh event loop in a dedicated
thread (`_run_coroutine_blocking`) rather than a bare `asyncio.run()`. A bare
`asyncio.run()` works fine in a real Celery worker process (nothing else is
running there), but breaks under `task_always_eager=True` -- the config this
whole codebase runs tests under -- because eager mode calls the task
synchronously from *within* whatever loop is already running (here, the
FastAPI request handler's loop under pytest-asyncio's ASGI transport).
Isolating onto a new thread's own loop makes the wrapper work identically in
both cases without special-casing tests.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections.abc import Coroutine
from typing import TypeVar

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.telemetry import INGESTION_JOBS
from app.models.repository import Repository
from app.services.ingestion.service import ingest_repository
from app.services.retrieval.embeddings import get_embedding_provider
from app.services.retrieval.vector_store import get_vector_store
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

_T = TypeVar("_T")


def _run_coroutine_blocking(coro: Coroutine[object, object, _T]) -> _T:
    outcome: dict[str, object] = {}

    def _runner() -> None:
        try:
            outcome["value"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001 - re-raised on the calling thread below
            outcome["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if "error" in outcome:
        raise outcome["error"]  # type: ignore[misc]
    return outcome["value"]  # type: ignore[return-value]


async def _ingest_repository_async(repository_id: str) -> str:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with session_factory() as db:
            repository = await db.get(Repository, uuid.UUID(repository_id))
            if repository is None:
                logger.warning("ingestion_task_repository_missing", repository_id=repository_id)
                return "missing"

            embedder = get_embedding_provider()
            vector_store = get_vector_store()
            result = await ingest_repository(
                db, repository=repository, embedder=embedder, vector_store=vector_store
            )
            INGESTION_JOBS.labels(status=result.status.value).inc()
            return result.status.value
    finally:
        await engine.dispose()


@celery_app.task(name="masea.ingest_repository", bind=True, max_retries=0)  # type: ignore[untyped-decorator]
def run_ingestion_task(self: object, repository_id: str) -> str:
    return _run_coroutine_blocking(_ingest_repository_async(repository_id))
