"""Exercises the Celery task wrapper itself (`run_ingestion_task.delay(...)`),
as opposed to `tests/integration/test_ingestion_pipeline.py` which exercises
the underlying async indexing function directly.

Deliberately synchronous (not `async def`): the task wraps its work in
`asyncio.run()`, which cannot be nested inside a running event loop, so this
test must not itself be running inside one. It also uses a file-backed
SQLite database rather than `:memory:`, because the task opens its own
database engine (a Celery worker is a separate process from the app in
production) and a `:memory:` SQLite database is private to the connection
that created it -- a second engine would see an empty, tableless database.

Uses an SSRF-blocked source URL (a cloud metadata IP) rather than a real
remote, so the task deterministically hits the FAILED path at URL
validation -- before any network call -- instead of depending on network
conditions or timeout duration in CI.
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401 - populate Base.metadata
from app.db.base import Base
from app.models.repository import RepositoryStatus
from app.models.user import User


def test_run_ingestion_task_indexes_the_fixture_repo_via_a_file_backed_db(tmp_path, monkeypatch):
    db_path = tmp_path / "task_test.sqlite3"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path / "workspace"))

    from app.core.config import get_settings

    get_settings.cache_clear()

    async def _setup() -> str:
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        from app.models.repository import Repository

        session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with session_factory() as db:
            user = User(email="task-owner@example.com", hashed_password="x")
            db.add(user)
            await db.flush()

            repo = Repository(
                owner_id=user.id,
                name="task-repo",
                source_url="https://169.254.169.254/task-repo.git",
                status=RepositoryStatus.PENDING,
            )
            db.add(repo)
            await db.commit()
            await db.refresh(repo)
            repository_id = str(repo.id)
        await engine.dispose()
        return repository_id

    repository_id = asyncio.run(_setup())

    from app.workers.tasks import run_ingestion_task

    # SSRF-blocked URL -> validate_source_url raises before any network call,
    # so this resolves fast and deterministically to the FAILED path -- what
    # this test verifies is that the task wrapper runs end-to-end (its own
    # engine, its own event loop) and lands the repository in a terminal,
    # explained state rather than crashing or hanging.
    result_status = run_ingestion_task.apply(args=[repository_id]).get()
    assert result_status == "failed"

    async def _check() -> RepositoryStatus:
        engine = create_async_engine(db_url)
        session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        from app.models.repository import Repository

        async with session_factory() as db:
            repo = await db.get(Repository, uuid.UUID(repository_id))
            assert repo is not None
            status = repo.status
        await engine.dispose()
        return status

    final_status = asyncio.run(_check())
    assert final_status == RepositoryStatus.FAILED

    get_settings.cache_clear()
