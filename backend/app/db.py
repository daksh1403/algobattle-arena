"""Async SQLAlchemy 2.x engine + session factory.

A single shared `engine` is built lazily from `app.config.get_settings()`,
plus a `sessionmaker` that produces `AsyncSession` instances scoped per request.

In tests we let `tests/conftest.py` override the engine with an in-memory SQLite
URL — so this module intentionally does no work at import time.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

# Lazily created so tests can swap the URL before the engine is built.
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_engine(url: str | None = None) -> AsyncEngine:
    """Create the async engine.

    A new engine is created whenever a different URL is passed in,
    which is how tests swap the database.

    If Postgres is unreachable (dev without Docker), falls back to SQLite automatically.
    """
    if url is None:
        url = get_settings().effective_database_url

    # Fallback to SQLite if Postgres is unreachable (dev without Docker)
    if url.startswith("postgresql"):
        try:
            import socket
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 5432
            with socket.create_connection((host, port), timeout=1):
                pass  # reachable
        except Exception:
            # Postgres not reachable — use local SQLite for dev
            import os
            sqlite_path = os.path.join(os.path.dirname(__file__), "algobattle_dev.db")
            url = f"sqlite+aiosqlite:///{sqlite_path}"
            import logging
            logging.warning(f"Postgres unreachable, using SQLite at {sqlite_path}")

    connect_args: dict = {}
    kwargs: dict = {}
    if url.startswith("sqlite"):
        # SQLite needs check_same_thread=False when used from an async context.
        connect_args["check_same_thread"] = False
        if ":memory:" in url:
            # A single shared in-memory DB across all connections/sessions,
            # so multiple test sessions see the same schema + data.
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool

    return create_async_engine(
        url, future=True, echo=False, connect_args=connect_args, **kwargs
    )


def init_engine(url: str | None = None) -> AsyncEngine:
    """Initialise (or rebuild) the global async engine + session factory."""
    global _engine, _session_factory
    _engine = _build_engine(url)
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        init_engine()
    assert _engine is not None  # noqa: S101 - kept for type-narrowing
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        init_engine()
    assert _session_factory is not None  # noqa: S101
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield an `AsyncSession` and close it after use."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def dispose_engine() -> None:
    """Tear down the engine on shutdown / between tests."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


# Re-export the SQLAlchemy declarative base via `Base` so other modules
# can `from app.db import Base` without reaching into SQLAlchemy directly.
from sqlalchemy.orm import DeclarativeBase  # noqa: E402


class Base(DeclarativeBase):
    """Shared declarative base for every ORM model in the project."""


__all__ = [
    "Base",
    "get_engine",
    "get_session",
    "get_session_factory",
    "init_engine",
    "dispose_engine",
]
