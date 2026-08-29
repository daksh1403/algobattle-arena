"""TDD tests for `SubmissionService` (without invoking the judge)."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import PageParams
from app.modules.problems.models import Difficulty, Problem
from app.modules.problems.schemas import ProblemCreate
from app.modules.problems.service import ProblemService
from app.modules.submissions.models import SubmissionStatus
from app.modules.submissions.schemas import SubmissionCreate
from app.modules.submissions.service import (
    LANGUAGE_ID_MAP,
    SubmissionService,
    aggregate_status,
    language_id_for,
    should_penalise,
)


async def _make_problem(session: AsyncSession) -> Problem:
    return await ProblemService(session).create(
        ProblemCreate(
            slug="two-sum",
            title="Two Sum",
            statement_md="# ts",
            difficulty=Difficulty.EASY,
        )
    )


@pytest.mark.asyncio
async def test_submit_creates_pending_row(db_session: AsyncSession) -> None:
    p = await _make_problem(db_session)
    service = SubmissionService(db_session)

    sub = await service.submit(
        user_id=1,
        payload=SubmissionCreate(
            problem_id=p.id,
            language="python3",
            code="def two_sum(nums, target): return []",
        ),
    )

    assert sub.id is not None
    assert sub.status == SubmissionStatus.PENDING
    assert sub.score == 0


@pytest.mark.asyncio
async def test_submit_unknown_problem_raises(db_session: AsyncSession) -> None:
    service = SubmissionService(db_session)
    with pytest.raises(NotFoundError):
        await service.submit(
            user_id=1,
            payload=SubmissionCreate(problem_id=999, language="python3", code="x"),
        )


@pytest.mark.asyncio
async def test_get_by_id_raises_for_missing(db_session: AsyncSession) -> None:
    service = SubmissionService(db_session)
    with pytest.raises(NotFoundError):
        await service.get_by_id(123456)


@pytest.mark.asyncio
async def test_list_for_user_paginates(db_session: AsyncSession) -> None:
    p = await _make_problem(db_session)
    service = SubmissionService(db_session)
    for _ in range(5):
        await service.submit(
            user_id=7,
            payload=SubmissionCreate(problem_id=p.id, language="python3", code="x"),
        )

    page = await service.list_for_user(7, params=PageParams(page=1, size=3))
    assert page.total == 5
    assert len(page.items) == 3


# --- pure helpers ----------------------------------------------------------


def test_aggregate_status_all_accepted() -> None:

    results = [
        _fake_result(SubmissionStatus.ACCEPTED),
        _fake_result(SubmissionStatus.ACCEPTED),
    ]
    assert aggregate_status(results) == SubmissionStatus.ACCEPTED


def test_aggregate_status_any_wa() -> None:

    results = [
        _fake_result(SubmissionStatus.ACCEPTED),
        _fake_result(SubmissionStatus.WRONG_ANSWER),
    ]
    assert aggregate_status(results) == SubmissionStatus.WRONG_ANSWER


def test_aggregate_status_compile_error_overrides_others() -> None:

    results = [
        _fake_result(SubmissionStatus.COMPILE_ERROR),
        _fake_result(SubmissionStatus.ACCEPTED),
    ]
    assert aggregate_status(results) == SubmissionStatus.COMPILE_ERROR


def test_aggregate_status_tle() -> None:

    results = [
        _fake_result(SubmissionStatus.ACCEPTED),
        _fake_result(SubmissionStatus.TIME_LIMIT_EXCEEDED),
    ]
    assert aggregate_status(results) == SubmissionStatus.TIME_LIMIT_EXCEEDED


def test_should_penalise_only_when_now_accepted() -> None:
    assert should_penalise(accepted_previously=False, now_accepted=True) is True
    assert should_penalise(accepted_previously=True, now_accepted=True) is False
    assert should_penalise(accepted_previously=False, now_accepted=False) is False


def test_language_id_for_known() -> None:
    assert language_id_for("python3") in LANGUAGE_ID_MAP.values()
    assert language_id_for("python3") == LANGUAGE_ID_MAP["python3"]


def test_language_id_for_unknown_defaults_python() -> None:
    assert language_id_for("lolcode") == LANGUAGE_ID_MAP["python"]


# --- helper ----------------------------------------------------------------


def _fake_result(status: SubmissionStatus):  # type: ignore[no-untyped-def]
    from app.modules.submissions.models import SubmissionResult

    return SubmissionResult(
        submission_id=1,
        testcase_id=1,
        status=status,
    )
