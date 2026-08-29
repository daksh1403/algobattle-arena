"""Periodic health-check: re-enqueue submissions stuck in RUNNING/PENDING.

A worker crash, OOM kill, or network hiccup can leave a submission in
RUNNING forever.  This job runs every 60 s and re-enqueues any submission
that has been in a non-terminal state for more than `STUCK_THRESHOLD_S`.

It is idempotent — if a submission is already being handled by a live
worker, the second job will see PENDING → it will re-enqueue but the
original job will also write a result; both writes are idempotent (final
status overwrites).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.modules.submissions.models import Submission, SubmissionStatus, TERMINAL_STATUSES
from app import rq_app

logger = logging.getLogger(__name__)

# How long a submission can be stuck in RUNNING/PENDING before we retry it.
STUCK_THRESHOLD_S = 60


async def find_stuck_submissions() -> list[int]:
    """Return IDs of non-terminal submissions older than `STUCK_THRESHOLD_S`.

    Uses the async session — APScheduler's `AsyncIOScheduler` runs jobs on
    the event loop, so we can use the shared async engine.  Uses the ORM
    with `.notin_()` so the IN-list is built safely by SQLAlchemy (no
    hand-built SQL strings).
    """
    from app.db import get_session_factory

    factory = get_session_factory()
    cutoff = datetime.now(tz=UTC) - timedelta(seconds=STUCK_THRESHOLD_S)
    async with factory() as session:
        stmt = select(Submission.id).where(
            Submission.status.notin_(TERMINAL_STATUSES),
            Submission.created_at < cutoff,
        )
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]


async def health_check() -> None:
    """APScheduler job: find and re-enqueue stuck submissions."""
    try:
        stuck_ids = await find_stuck_submissions()
        if not stuck_ids:
            return
        logger.info("Checker: found %d stuck submissions, re-enqueuing", len(stuck_ids))
        for sid in stuck_ids:
            try:
                rq_app.enqueue_judge_submission(sid)
                logger.info("Checker: re-enqueued stuck submission %s", sid)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Checker: failed to re-enqueue %s: %s", sid, exc)
    except Exception as exc:
        logger.error("Checker: health check failed: %s", exc)
