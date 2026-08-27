from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.test", override=True)

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 - populates Base.metadata before create_all
from app.db.base import Base
from app.db.session import get_db

os.environ.setdefault("ENVIRONMENT", "test")


@pytest_asyncio.fixture
async def db_engine(tmp_path, monkeypatch):
    """A file-backed (not `:memory:`) per-test SQLite database, with
    `DATABASE_URL` pointed at the same file so any code that opens its own
    engine from `get_settings().database_url` -- notably the Celery task
    wrapper, which must use its own engine to mirror how a real worker
    process would -- sees the same data as this fixture's session, the way a
    real shared Postgres would in every non-test environment. A plain
    `:memory:` database is private to the single connection that created it,
    which silently breaks that whenever a request handler and a background
    task each open their own connection.
    """
    db_path = tmp_path / "test.sqlite3"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_async_engine(db_url, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def app(db_engine):
    from app.main import create_app

    fastapi_app = create_app()
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    return fastapi_app


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest_asyncio.fixture
async def authed_user(client, db_session):
    """Registers and logs in a fresh user via the real HTTP auth flow, and
    returns (bearer_token, user_row) -- the user row comes from `db_session`
    so tests can attach owned resources (repositories, etc.) directly.
    """
    import uuid

    from sqlalchemy import select

    from app.models.user import User

    email = f"contract-{uuid.uuid4().hex}@example.com"
    password = "correct-horse-battery-staple"
    register = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert register.status_code == 201

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.json()["access_token"]

    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    return token, user
