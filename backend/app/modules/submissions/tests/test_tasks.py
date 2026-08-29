"""TDD tests for the judge task pipeline.

These tests verify:

1. `JudgeClient` correctly base64-encodes payloads + polls until terminal.
2. `judge_submission` (async) reads submission + testcases, calls the
   judge, persists per-testcase results, updates status, and updates the
   contest leaderboard.

A fake `httpx.AsyncClient` is injected into `JudgeClient` to avoid any
network call.
"""
from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contests.models import ContestParticipant
from app.modules.contests.schemas import ContestCreate
from app.modules.contests.service import ContestService
from app.modules.problems.models import Difficulty, TestCase
from app.modules.problems.schemas import ProblemCreate
from app.modules.problems.service import ProblemService
from app.modules.submissions.judge_client import JudgeClient
from app.modules.submissions.models import (
    SubmissionResult,
    SubmissionStatus,
)
from app.modules.submissions.schemas import SubmissionCreate
from app.modules.submissions.service import SubmissionService

# --- Fake HTTP transport for JudgeClient ------------------------------------


class _FakeTransport(httpx.AsyncBaseTransport):
    """Return canned responses for the Judge0 endpoints we exercise."""

    def __init__(self, verdicts: dict[str, dict[str, Any]]):
        # token -> Judge0 response payload
        self._verdicts = verdicts
        self.submissions_calls = 0
        self.batch_calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/submissions/batch"):
            if request.method == "POST":
                self.submissions_calls += 1
                body = request.read()
                import json

                decoded = json.loads(body or b"{}")
                tokens = [
                    f"tok{i}"
                    for i, _ in enumerate(decoded.get("submissions", []))
                ]
                # Remember expected outputs so we can echo them back.
                # Judge0's POST /submissions/batch returns a flat array:
                # [{"token": ...}, ...]
                payload = [
                    self._verdicts.setdefault(t, self._verdicts["default"])
                    | {"token": t}
                    for t in tokens
                ]
                return httpx.Response(200, json=payload)
            # GET (poll)
            self.batch_calls += 1
            tokens_param = request.url.params.get("tokens", "")
            token_list = [t for t in tokens_param.split(",") if t]
            poll_payload = {
                "submissions": [
                    self._verdicts.get(t, self._verdicts["default"]) | {"token": t}
                    for t in token_list
                ]
            }
            return httpx.Response(200, json=poll_payload)
        return httpx.Response(404, json={"error": "unknown route"})


def _accepted_response() -> dict[str, Any]:
    return {
        "stdout": base64.b64encode(b"output").decode(),
        "stderr": None,
        "compile_output": None,
        "time": "0.123",
        "memory": 4096,
        "status": {"id": 3, "description": "Accepted"},
    }


def _wrong_answer_response() -> dict[str, Any]:
    return {
        "stdout": base64.b64encode(b"wrong").decode(),
        "stderr": None,
        "compile_output": None,
        "time": "0.05",
        "memory": 3000,
        "status": {"id": 4, "description": "Wrong Answer"},
    }


def _ac_then_wa() -> dict[str, dict[str, Any]]:
    """Two tokens, first AC then WA."""
    return {
        "default": _accepted_response(),
        "tok0": _accepted_response(),
        "tok1": _wrong_answer_response(),
    }


# --- tests ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_judge_client_base64_encodes_payloads() -> None:
    transport = _FakeTransport(verdicts={"default": _accepted_response()})
    async with httpx.AsyncClient(
        base_url="http://judge0.local",
        transport=transport,
    ) as http_client:
        judge = JudgeClient(http_client=http_client, poll_interval=0.001)
        payloads = [
            judge.make_payload(
                source_code="print(1)",
                language_id=71,
                stdin="",
                expected_output="1",
            )
        ]
        tokens = await judge.submit_batch(payloads)
        assert len(tokens) == 1
        # Verify the request body was base64-encoded.
        results = await judge.poll_batch(tokens)
        assert results[0].status == "accepted"
        assert results[0].runtime_ms == 123
        assert results[0].memory_kb == 4096


@pytest.mark.asyncio
async def test_judge_client_polls_multiple_tokens(db_session: AsyncSession) -> None:
    transport = _FakeTransport(verdicts=_ac_then_wa())
    async with httpx.AsyncClient(
        base_url="http://judge0.local",
        transport=transport,
    ) as http_client:
        judge = JudgeClient(http_client=http_client, poll_interval=0.001)
        tokens = ["tok0", "tok1"]
        results = await judge.poll_batch(tokens)
        statuses = [r.status for r in results]
        assert statuses == ["accepted", "wrong_answer"]


@pytest.mark.asyncio
async def test_judge_submission_updates_status_and_persists_results(
    db_session: AsyncSession, fake_redis, monkeypatch
) -> None:
    # Set up problem + test cases
    problem = await ProblemService(db_session).create(
        ProblemCreate(
            slug="two-sum",
            title="Two Sum",
            statement_md="# ts",
            difficulty=Difficulty.EASY,
            test_cases=[
                # Two test cases — both AC in our fake.
            ],
        )
    )
    # Manually add two more test cases (the create payload above was empty
    # for test_cases in this branch — add them via SQL directly).
    db_session.add_all([
        TestCase(problem_id=problem.id, input="[]", expected_output="[]", is_public=True),
        TestCase(problem_id=problem.id, input="[]", expected_output="[]", is_public=True),
    ])
    await db_session.commit()

    # Create a user + submission
    from app.modules.users.models import User
    user = User(username="judger", email="judger@example.com", password_hash="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    sub = await SubmissionService(db_session).submit(
        user_id=user.id,
        payload=SubmissionCreate(problem_id=problem.id, language="python3", code="print(0)"),
    )

    # Patch JudgeClient to use the fake transport
    transport = _FakeTransport(verdicts={"default": _accepted_response()})

    async def _patched_judge(**_):
        return httpx.AsyncClient(base_url="http://judge0.local", transport=transport)

    # Monkeypatch the judge client constructor inside the task
    import app.modules.submissions.tasks as tasks_mod

    real_judge_init = JudgeClient.__init__

    def _judge_init(self, *args, **kwargs):  # noqa: ANN001
        # Force our http_client
        kwargs["http_client"] = httpx.AsyncClient(
            base_url="http://judge0.local", transport=transport
        )
        kwargs["poll_interval"] = 0.001
        real_judge_init(self, *args, **kwargs)

    monkeypatch.setattr(tasks_mod, "JudgeClient", JudgeClient)
    JudgeClient.__init__ = _judge_init  # type: ignore[assignment]

    try:
        await tasks_mod._judge_async(sub.id)
    finally:
        JudgeClient.__init__ = real_judge_init  # type: ignore[assignment]

    # Re-fetch the submission
    await db_session.refresh(sub)
    assert sub.status == SubmissionStatus.ACCEPTED
    assert sub.score >= 100

    # Results persisted
    from sqlalchemy import select

    res_q = await db_session.execute(
        select(SubmissionResult).where(SubmissionResult.submission_id == sub.id)
    )
    results = list(res_q.scalars().all())
    assert len(results) == 2
    assert all(r.status == SubmissionStatus.ACCEPTED for r in results)


@pytest.mark.asyncio
async def test_judge_submission_wrong_answer_keeps_score_zero(
    db_session: AsyncSession, fake_redis, monkeypatch
) -> None:
    problem = await ProblemService(db_session).create(
        ProblemCreate(
            slug="two-sum-wa",
            title="Two Sum WA",
            statement_md="# ts",
            difficulty=Difficulty.EASY,
            test_cases=[],
        )
    )
    db_session.add(
        TestCase(
            problem_id=problem.id, input="[]", expected_output="[]", is_public=True
        )
    )
    await db_session.commit()

    from app.modules.users.models import User
    user = User(username="wajudger", email="wajudger@example.com", password_hash="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    sub = await SubmissionService(db_session).submit(
        user_id=user.id,
        payload=SubmissionCreate(problem_id=problem.id, language="python3", code="print(0)"),
    )

    transport = _FakeTransport(verdicts={"default": _wrong_answer_response()})

    import app.modules.submissions.tasks as tasks_mod

    real_judge_init = JudgeClient.__init__

    def _judge_init(self, *args, **kwargs):  # noqa: ANN001
        kwargs["http_client"] = httpx.AsyncClient(
            base_url="http://judge0.local", transport=transport
        )
        kwargs["poll_interval"] = 0.001
        real_judge_init(self, *args, **kwargs)

    JudgeClient.__init__ = _judge_init  # type: ignore[assignment]
    try:
        await tasks_mod._judge_async(sub.id)
    finally:
        JudgeClient.__init__ = real_judge_init  # type: ignore[assignment]

    await db_session.refresh(sub)
    assert sub.status == SubmissionStatus.WRONG_ANSWER
    assert sub.score == 0


@pytest.mark.asyncio
async def test_judge_submission_updates_contest_leaderboard_on_ac(
    db_session: AsyncSession, fake_redis, monkeypatch
) -> None:
    # Problem with 1 public test case
    problem = await ProblemService(db_session).create(
        ProblemCreate(
            slug="lb-problem",
            title="LB",
            statement_md="# ts",
            difficulty=Difficulty.EASY,
            test_cases=[],
        )
    )
    db_session.add(
        TestCase(
            problem_id=problem.id, input="[]", expected_output="[]", is_public=True
        )
    )
    await db_session.commit()

    # Running contest
    now = datetime.now(tz=UTC)
    contest = await ContestService(db_session).create(
        ContestCreate(
            name="LB Contest",
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=1),
            problem_ids=[problem.id],
        )
    )

    # User + join
    from app.modules.users.models import User
    user = User(username="lbjudger", email="lbjudger@example.com", password_hash="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    await ContestService(db_session).join(contest.id, user.id)

    # Submission
    sub = await SubmissionService(db_session).submit(
        user_id=user.id,
        payload=SubmissionCreate(
            problem_id=problem.id,
            language="python3",
            code="print(0)",
            contest_id=contest.id,
        ),
    )

    transport = _FakeTransport(verdicts={"default": _accepted_response()})

    import app.modules.submissions.tasks as tasks_mod

    real_judge_init = JudgeClient.__init__

    def _judge_init(self, *args, **kwargs):  # noqa: ANN001
        kwargs["http_client"] = httpx.AsyncClient(
            base_url="http://judge0.local", transport=transport
        )
        kwargs["poll_interval"] = 0.001
        real_judge_init(self, *args, **kwargs)

    JudgeClient.__init__ = _judge_init  # type: ignore[assignment]
    try:
        await tasks_mod._judge_async(sub.id)
    finally:
        JudgeClient.__init__ = real_judge_init  # type: ignore[assignment]

    # Refresh
    await db_session.refresh(sub)
    part = await db_session.get(ContestParticipant, 1)
    # First AC should grant full problem score (default 100).
    assert part is not None
    assert part.total_points == 100
    assert sub.status == SubmissionStatus.ACCEPTED
