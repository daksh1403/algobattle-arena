"""FastAPI entrypoint.

Build the app via `create_app()` so tests can construct an isolated
instance and override dependencies.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.ws_router import router as ws_router
from app.db import dispose_engine, init_engine
from app.deps import get_limiter, rate_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Import models BEFORE routers so SQLAlchemy can resolve `relationship('Other')`
# references at router import time. Without this, FastAPI 0.141+ lazy route
# resolution fails to register `/api/*` routes when the lifespan runs.
import app.modules.users.models      # noqa: E402,F401  registers User
import app.modules.problems.models   # noqa: E402,F401  registers Problem, TestCase
import app.modules.submissions.models  # noqa: E402,F401  registers Submission, SubmissionResult
import app.modules.contests.models   # noqa: E402,F401  registers Contest, ContestParticipant, ContestProblem

from app.modules.contests.router import router as contests_router
from app.modules.leaderboard.router import router as leaderboard_router
from app.modules.problems.router import router as problems_router
from app.modules.submissions.router import router as submissions_router
from app.modules.users.router import router as users_router
from app.redis_client import close_redis, init_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "Starting %s in %s mode", settings.app_name, settings.app_env
    )
    # Init DB engine + redis (test env uses fakeredis/in-memory sqlite).
    init_engine()
    init_redis(fake=settings.is_test)

    # Auto-create tables on SQLite fallback (dev without Postgres/Docker).
    # Models are already imported at module top so SQLAlchemy has registered
    # them with Base.metadata by the time we get here.
    from app.db import get_engine
    engine = get_engine()
    if engine is not None:
        async with engine.begin() as conn:
            from app.db import Base
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified")

    # Start the periodic stuck-submission checker (production only).
    scheduler: AsyncIOScheduler | None = None
    if not settings.is_test:
        from app.modules.submissions.checker import health_check

        scheduler = AsyncIOScheduler()
        scheduler.add_job(health_check, "interval", seconds=60, id="stuck_checker")
        scheduler.start()
        logger.info("Stuck-submission checker started (every 60 s)")

    yield

    # Shutdown scheduler before tearing down DB.
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")

    await dispose_engine()
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Algobattle API",
        version="0.1.0",
        description="Competitive coding judge platform — backend.",
        lifespan=lifespan,
        redirect_slashes=False,
    )

    # CORS — origins controlled via ALLOWED_ORIGINS env var.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=len(settings.cors_origins) == 1 and settings.cors_origins[0] != "*",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom error handler
    register_exception_handlers(app)

    # Rate-limit error handler
    app.state.limiter = get_limiter()
    app.add_exception_handler(RateLimitExceeded, rate_exceeded_handler)

    # Routers — all under /api prefix
    api_prefix = "/api"
    app.include_router(users_router, prefix=api_prefix)
    app.include_router(problems_router, prefix=api_prefix)
    app.include_router(contests_router, prefix=api_prefix)
    app.include_router(submissions_router, prefix=api_prefix)
    app.include_router(leaderboard_router, prefix=api_prefix)
    app.include_router(ws_router, prefix=api_prefix)  # WebSocket (live submission + leaderboard updates)

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok", "app": settings.app_name, "env": settings.app_env}

    @app.get("/", tags=["health"])
    async def root() -> dict:
        return {"name": settings.app_name, "docs": "/docs"}

    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    s = get_settings()
    uvicorn.run("app.main:app", host=s.host, port=s.port, reload=s.debug)
