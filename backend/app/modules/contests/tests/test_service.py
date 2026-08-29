"""TDD tests for `ContestService`."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.contests.schemas import ContestCreate
from app.modules.contests.service import ContestService
from app.modules.problems.models import Difficulty, Problem
from app.modules.problems.schemas import ProblemCreate
from app.modules.problems.service import ProblemService
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService


async def _make_problem(session: AsyncSession, slug: str) -> Problem:
    return await ProblemService(session).create(
        ProblemCreate(
            slug=slug,
            title=slug.title(),
            statement_md="# desc",
            difficulty=Difficulty.EASY,
        )
    )


async def _make_user(session: AsyncSession, username: str) -> User:
    return await UserService(session).create(
        UserCreate(
            username=username,
            email=f"{username}@example.com",
            password="longenough1",
        )
    )


def _running_window() -> tuple[datetime, datetime]:
    now = datetime.now(tz=UTC)
    return now - timedelta(minutes=1), now + timedelta(hours=1)


@pytest.mark.asyncio
async def test_create_contest_with_problems(db_session: AsyncSession) -> None:
    p1 = await _make_problem(db_session, "c1-p1")
    p2 = await _make_problem(db_session, "c1-p2")

    start, end = _running_window()
    service = ContestService(db_session)
    contest = await service.create(
        ContestCreate(
            name="Round 1",
            description="Hello",
            start_at=start,
            end_at=end,
            problem_ids=[p1.id, p2.id],
        )
    )

    assert contest.id is not None
    assert len(contest.contest_problems) == 2
    # Position is the order they were inserted.
    assert [cp.position for cp in contest.contest_problems] == [0, 1]


@pytest.mark.asyncio
async def test_create_contest_window_validation() -> None:
    from pydantic import ValidationError as PydValError

    now = datetime.now(tz=UTC)
    with pytest.raises(PydValError):
        ContestCreate(name="bad", start_at=now, end_at=now - timedelta(seconds=1))


@pytest.mark.asyncio
async def test_join_running_contest(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "joiner")
    start, end = _running_window()
    contest = await ContestService(db_session).create(
        ContestCreate(name="Running", start_at=start, end_at=end)
    )

    p = await ContestService(db_session).join(contest.id, user.id)

    assert p.contest_id == contest.id
    assert p.user_id == user.id
    assert p.total_points == 0


@pytest.mark.asyncio
async def test_join_duplicate_user_raises(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "dup")
    start, end = _running_window()
    contest = await ContestService(db_session).create(
        ContestCreate(name="Running2", start_at=start, end_at=end)
    )

    service = ContestService(db_session)
    await service.join(contest.id, user.id)

    with pytest.raises(ConflictError):
        await service.join(contest.id, user.id)


@pytest.mark.asyncio
async def test_join_outside_window_raises(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "outofwindow")
    now = datetime.now(tz=UTC)
    contest = await ContestService(db_session).create(
        ContestCreate(
            name="Future",
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=2),
        )
    )
    with pytest.raises(ValidationError):
        await ContestService(db_session).join(contest.id, user.id)


@pytest.mark.asyncio
async def test_join_unknown_contest_raises(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "ghost")
    with pytest.raises(NotFoundError):
        await ContestService(db_session).join(9999, user.id)


@pytest.mark.asyncio
async def test_list_participants_sorted_by_points(db_session: AsyncSession) -> None:
    u1 = await _make_user(db_session, "player1")
    u2 = await _make_user(db_session, "player2")
    u3 = await _make_user(db_session, "player3")
    start, end = _running_window()
    contest = await ContestService(db_session).create(
        ContestCreate(name="Sort Me", start_at=start, end_at=end)
    )
    service = ContestService(db_session)
    await service.join(contest.id, u1.id)
    await service.join(contest.id, u2.id)
    await service.join(contest.id, u3.id)
    # Manual point adjustments
    await service.adjust_points(contest.id, u1.id, 100)
    await service.adjust_points(contest.id, u3.id, 200)

    items = await service.list_participants(contest.id)

    assert [p.user_id for p in items] == [u3.id, u1.id, u2.id]
