"""RQ task: grade a single submission against all (public) test cases.

This is the heart of the judge pipeline:

    1. Validate submission is PENDING (idempotent — never grade twice).
    2. Load problem + testcases.
    3. Build Judge0 payloads (one per testcase, base64-encoded).
    4. Send as a batch and poll until terminal.
    5. Persist per-testcase `SubmissionResult` rows.
    6. Update parent `Submission.status` + `runtime_ms` / `memory_kb` / `score`.
    7. If part of a contest and AC: update `ContestParticipant.total_points`
       and the leaderboard ZSET.

The function is intentionally synchronous — RQ runs it in a worker thread.
A new sync `AsyncSession` is created per invocation.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.db import dispose_engine, get_session_factory, init_engine
from app.modules.contests.service import ContestService
from app.modules.leaderboard.service import LeaderboardService
from app.modules.problems.models import Problem
from app.modules.problems.service import ProblemService
from app.modules.submissions.judge_client import JudgeClient
from app.modules.submissions.models import (
    TERMINAL_STATUSES,
    Submission,
    SubmissionResult,
    SubmissionStatus,
)
from app.modules.submissions.service import (
    aggregate_status,
    language_id_for,
)
from app.core.pubsub import publish_submission_update, publish_contest_update

logger = logging.getLogger(__name__)

# Penalty per wrong submission (ICPC-style)
_WRONG_PENALTY = 20
# Default score granted on first AC
_DEFAULT_AC_SCORE = 100


def judge_submission(submission_id: int) -> dict[str, Any]:
    """RQ entrypoint — run the async judge safely from a worker process.

    Always expects to be called from an RQ worker (no running event loop).
    Callers that need to enqueue work should use
    `app.rq_app.enqueue_judge_submission(submission_id)` — never call
    this function directly from a request handler.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Expected: no running loop in an RQ worker process.
        pass
    else:
        # Defensive: if we ever end up here (e.g. someone calls us from
        # inside the FastAPI event loop), raise loudly instead of
        # silently fire-and-forget'ing a coroutine that may be cancelled
        # when the request finishes.
        raise RuntimeError(
            "judge_submission must be called from an RQ worker process, "
            "not from a running event loop. Use enqueue_judge_submission()."
        )

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_judge_async(submission_id))
    finally:
        loop.close()


async def _judge_async(submission_id: int) -> dict[str, Any]:
    settings = get_settings()
    # Re-initialise the engine against the *non-test* URL so workers that
    # share the process with tests don't accidentally write to SQLite.
    if settings.app_env != "test":
        init_engine()
    factory = get_session_factory()

    # Use the app's shared redis client (fakeredis in tests, real Redis in
    # prod).
    from app.redis_client import get_redis

    redis_client = get_redis()

    try:
        async with httpx.AsyncClient(
            base_url=settings.judge0_url,
            headers=settings.judge0_auth_header or {},
            timeout=httpx.Timeout(30.0),
        ) as http_client:
            judge = JudgeClient(http_client=http_client)
            async with factory() as session:
                result = await _grade_submission(
                    submission_id=submission_id,
                    session=session,
                    judge=judge,
                    redis_client=redis_client,
                )
                await session.commit()
                return result
    finally:
        if settings.app_env != "test":
            # In production each worker process owns its engine.  In tests the
            # engine is shared with the API fixtures — never dispose it here.
            await dispose_engine()


async def _grade_submission(
    *,
    submission_id: int,
    session,
    judge: JudgeClient,
    redis_client,
) -> dict[str, Any]:
    submission = await session.get(Submission, submission_id)
    if submission is None:
        logger.warning("judge: submission %s not found", submission_id)
        return {"ok": False, "reason": "not_found"}
    if submission.status in TERMINAL_STATUSES:
        logger.info(
            "judge: submission %s already terminal (%s), skipping",
            submission_id,
            submission.status,
        )
        return {"ok": False, "reason": "already_terminal"}

    problem = await session.get(Problem, submission.problem_id)
    if problem is None:
        submission.status = SubmissionStatus.INTERNAL_ERROR
        submission.finished_at = datetime.now(tz=UTC)
        return {"ok": False, "reason": "problem_missing"}

    # Mark RUNNING — invariant: PENDING → RUNNING → terminal.
    submission.status = SubmissionStatus.RUNNING
    await session.flush()

    # Push RUNNING status to WebSocket clients immediately.
    publish_submission_update(submission.id, {
        "type": "status",
        "submission_id": submission.id,
        "status": submission.status.value,
        "runtime_ms": None,
        "memory_kb": None,
        "score": 0,
    })

    # Fetch public test cases — 'test' mode = sample cases only (the Run button).
    # 'submit' mode = all public cases (the Submit button).
    problem_service = ProblemService(session)
    test_cases = await problem_service.list_test_cases(
        problem.id, samples_only=(submission.mode == "test"), public_only=True
    )
    if not test_cases:
        submission.status = SubmissionStatus.INTERNAL_ERROR
        submission.finished_at = datetime.now(tz=UTC)
        return {"ok": False, "reason": "no_test_cases"}

    language_id = language_id_for(submission.language)
    payloads = [
        judge.make_payload(
            source_code=submission.code,
            language_id=language_id,
            stdin=tc.input,
            expected_output=tc.expected_output,
            cpu_time_limit=max(0.1, problem.time_limit_ms / 1000.0),
            memory_limit=problem.memory_limit_kb,
        )
        for tc in test_cases
    ]

    try:
        tokens = await judge.submit_batch(payloads)
        verdicts = await judge.poll_batch(tokens)
    except httpx.HTTPError as exc:
        if not settings.judge_allow_local_fallback:
            # Production: do NOT fall back to an unsandboxed local subprocess.
            # A Judge0 outage is a hard failure — the stuck-submission sweeper
            # will retry the job once Judge0 recovers. Mark the submission
            # as INTERNAL_ERROR so the user sees a clear error rather than
            # silently swapping to an unsafe sandbox.
            logger.error(
                "judge: Judge0 unavailable (%s); marking submission %s as INTERNAL_ERROR",
                exc,
                submission.id,
            )
            submission.status = SubmissionStatus.INTERNAL_ERROR
            submission.finished_at = datetime.now(tz=UTC)
            return {
                "ok": False,
                "submission_id": submission.id,
                "status": SubmissionStatus.INTERNAL_ERROR.value,
                "reason": "judge_unavailable",
            }
        logger.warning(
            "judge: Judge0 unavailable (%s), falling back to local sandbox (DEV ONLY)",
            exc,
        )
        from app.modules.submissions.local_judge import LocalJudgeClient
        local = LocalJudgeClient(timeout_seconds=max(problem.time_limit_ms / 1000.0, 10.0))
        local_tokens = await local.submit_batch(payloads)
        verdicts = await local.poll_batch(local_tokens)

    # Persist per-testcase results
    results: list[SubmissionResult] = []
    max_runtime_ms = 0
    max_memory_kb = 0
    for tc, verdict in zip(test_cases, verdicts, strict=True):
        result_status = SubmissionStatus(verdict.status)
        results.append(
            SubmissionResult(
                submission_id=submission.id,
                testcase_id=tc.id,
                status=result_status,
                runtime_ms=verdict.runtime_ms,
                memory_kb=verdict.memory_kb,
                stdout=verdict.stdout[:8000],  # cap text fields
                stderr=verdict.stderr[:8000],
                compile_output=verdict.compile_output[:8000],
            )
        )
        if verdict.runtime_ms is not None:
            max_runtime_ms = max(max_runtime_ms, verdict.runtime_ms)
        if verdict.memory_kb is not None:
            max_memory_kb = max(max_memory_kb, verdict.memory_kb)
    session.add_all(results)

    final_status = aggregate_status(results)
    submission.status = final_status
    submission.runtime_ms = max_runtime_ms
    submission.memory_kb = max_memory_kb
    submission.finished_at = datetime.now(tz=UTC)

    # Push terminal verdict to WebSocket clients.
    publish_submission_update(submission.id, {
        "type": "result",
        "submission_id": submission.id,
        "status": final_status.value,
        "runtime_ms": submission.runtime_ms,
        "memory_kb": submission.memory_kb,
        "score": submission.score,
    })

    # Score: only AC earns points; failed attempts cost the ICPC penalty.
    if final_status == SubmissionStatus.ACCEPTED:
        # First-AC bonus logic — penalty = wrong submissions before this AC.
        prior_failed_q = await session.execute(
            select(Submission).where(
                Submission.user_id == submission.user_id,
                Submission.problem_id == submission.problem_id,
                Submission.contest_id == submission.contest_id,
                Submission.id != submission.id,
                Submission.status.in_(
                    [
                        SubmissionStatus.WRONG_ANSWER,
                        SubmissionStatus.RUNTIME_ERROR,
                        SubmissionStatus.TIME_LIMIT_EXCEEDED,
                        SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
                        SubmissionStatus.COMPILE_ERROR,
                    ]
                ),
            )
        )
        prior_failed = len(list(prior_failed_q.scalars().all()))
        submission.score = max(_DEFAULT_AC_SCORE - prior_failed * _WRONG_PENALTY, 0)
    else:
        submission.score = 0

    # Contest side-effects
    if submission.contest_id is not None:
        contest_service = ContestService(session)
        if final_status == SubmissionStatus.ACCEPTED:
            # First-time AC for this user+problem+contest?
            previous_q = await session.execute(
                select(Submission).where(
                    Submission.user_id == submission.user_id,
                    Submission.problem_id == submission.problem_id,
                    Submission.contest_id == submission.contest_id,
                    Submission.id != submission.id,
                    Submission.status == SubmissionStatus.ACCEPTED,
                )
            )
            already_accepted = previous_q.scalar_one_or_none() is not None
            if not already_accepted:
                # Grant problem score (default 100); update SQL + leaderboard.
                await contest_service.adjust_points(
                    submission.contest_id, submission.user_id, submission.score
                )
                lb = LeaderboardService(redis_client)
                await lb.increment(
                    submission.contest_id, submission.user_id, submission.score
                )
                # Record solve time relative to contest start.
                solve_seconds = await _seconds_since(submission, session)
                await lb.record_solve(
                    submission.contest_id,
                    submission.user_id,
                    submission.problem_id,
                    solve_seconds,
                )
                # Push leaderboard update to all WS clients watching this contest.
                publish_contest_update(submission.contest_id, {
                    "type": "user_solved",
                    "user_id": submission.user_id,
                    "problem_id": submission.problem_id,
                    "points": submission.score,
                })
        else:
            # Failed attempt — apply penalty (only first N fails count; we
            # charge every failed submission, capped at problem score - 1).
            prior_failed = len(
                list(
                    (
                        await session.execute(
                            select(Submission).where(
                                Submission.user_id == submission.user_id,
                                Submission.problem_id == submission.problem_id,
                                Submission.contest_id == submission.contest_id,
                                Submission.id != submission.id,
                                Submission.status != SubmissionStatus.ACCEPTED,
                            )
                        )
                    ).scalars().all()
                )
            )
            # Cap penalty at total available score.
            remaining = _DEFAULT_AC_SCORE - 1 - prior_failed * _WRONG_PENALTY
            penalty = min(_WRONG_PENALTY, max(remaining, 0))
            if penalty > 0:
                contest_service = ContestService(session)
                await contest_service.adjust_points(
                    submission.contest_id, submission.user_id, -penalty
                )
                lb = LeaderboardService(redis_client)
                await lb.increment(
                    submission.contest_id, submission.user_id, -penalty
                )

    return {
        "ok": True,
        "submission_id": submission.id,
        "status": final_status.value,
        "score": submission.score,
    }


async def _seconds_since(submission: Submission, session) -> float:
    """Return seconds between the contest's start_at and this submission's
    creation — used as the solve-time score for the leaderboard tiebreaker.
    """
    from app.modules.contests.models import Contest

    contest = await session.get(Contest, submission.contest_id)
    if contest is None:
        return 0.0
    delta = submission.created_at - contest.start_at
    return max(delta.total_seconds(), 0.0)


__all__ = ["judge_submission"]
