"""Pytest configuration + shared fixtures (applies to tests/ and app/modules/*).

Goals:

1. Use an **in-memory SQLite** database so tests don't need Postgres.
2. Use **fakeredis** for the leaderboard so tests don't need Redis.
3. Build a fresh `AsyncClient` per test against an isolated schema.
4. Provide `db_session`, `client`, `auth_token`, `fake_redis` fixtures
   for easy reuse across modules.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import Base, dispose_engine, get_session_factory, init_engine
from app.modules.users.models import User  # noqa: F401  (registration only)
from app.modules.problems.models import Problem, TestCase  # noqa: F401
from app.modules.contests.models import (  # noqa: F401
    Contest,
    ContestParticipant,
    ContestProblem,
)
from app.modules.submissions.models import Submission, SubmissionResult  # noqa: F401
from app.redis_client import close_redis, init_redis


# --- event loop fixture (single loop for the whole test session) ---------


@pytest.fixture(scope="session")
def event_loop():
    """Single loop across the session — asyncpg engines need this."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# --- per-test env ---------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _setup_test_env(monkeypatch):
    """Force the app into `test` mode + wire in-memory sqlite + fakeredis."""
    # Make sure cached settings reflect `test`
    get_settings.cache_clear()  # type: ignore[attr-defined]
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(
        "TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"
    )
    monkeypatch.setenv("TEST_REDIS_URL", "redis://localhost:6379/15")  # unused

    settings = get_settings()
    # Build a shared in-memory engine. `init_engine` auto-detects
    # `sqlite+aiosqlite:///:memory:` and uses a StaticPool so multiple
    # sessions share the same in-memory db.
    engine = init_engine(settings.test_database_url)

    # Init redis (fake)
    init_redis(fake=True)

    # Build schema in the test DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Tear down
    await dispose_engine()
    await close_redis()


# --- per-test session ----------------------------------------------------


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
        await session.rollback()


# --- httpx AsyncClient against the FastAPI app ----------------------------


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    # Import the app after the test env is set so it picks up the test
    # database / fake redis.
    from app.main import create_app

    app = create_app()
    # Install rate limiter state so slowapi decorators don't fail.
    from app.deps import get_limiter
    app.state.limiter = get_limiter()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- redis helpers --------------------------------------------------------


@pytest_asyncio.fixture
async def fake_redis():
    """Return a fresh fakeredis client per-test."""
    from fakeredis import aioredis as fakeredis_async

    client = fakeredis_async.FakeRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


# --- simple auth helper ---------------------------------------------------


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient) -> str:
    r = await client.post(
        "/auth/register",
        json={
            "username": "tester",
            "email": "tester@example.com",
            "password": "longenough1",
        },
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/auth/login",
        json={"username_or_email": "tester", "password": "longenough1"},
    )
    assert r2.status_code == 200
    return r2.json()["access_token"]


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient) -> str:
    """Register a user, promote them to admin directly in the DB, return JWT."""
    r = await client.post(
        "/api/auth/register",
        json={
            "username": "adminuser",
            "email": "admin@example.com",
            "password": "longenough1",
        },
    )
    assert r.status_code == 201, r.text
    user_id = r.json()["id"]

    # Promote via the service (bypasses the admin dependency).
    from app.db import get_session_factory
    from app.modules.users.service import UserService

    factory = get_session_factory()
    async with factory() as session:
        await UserService(session).set_admin(user_id, is_admin=True)

    r2 = await client.post(
        "/api/auth/login",
        json={"username_or_email": "adminuser", "password": "longenough1"},
    )
    assert r2.status_code == 200
    return r2.json()["access_token"]
