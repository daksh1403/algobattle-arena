"""TDD tests for `LeaderboardService` (uses fakeredis)."""
from __future__ import annotations

import pytest

from app.modules.leaderboard.service import LeaderboardService


@pytest.mark.asyncio
async def test_add_participant_zero_points(fake_redis) -> None:
    lb = LeaderboardService(fake_redis)
    await lb.add_participant(1, user_id=42)

    score = await lb.score_of(1, 42)
    assert score == 0.0


@pytest.mark.asyncio
async def test_increment_and_top(fake_redis) -> None:
    lb = LeaderboardService(fake_redis)
    await lb.add_participant(1, user_id=1)
    await lb.add_participant(1, user_id=2)
    await lb.increment(1, user_id=1, delta=300)
    await lb.increment(1, user_id=2, delta=500)

    top = await lb.top(1, limit=10)
    assert [e["user_id"] for e in top] == [2, 1]
    assert [e["score"] for e in top] == [500, 300]


@pytest.mark.asyncio
async def test_rank_of(fake_redis) -> None:
    lb = LeaderboardService(fake_redis)
    for uid, score in [(1, 100), (2, 200), (3, 50)]:
        await lb.add_participant(1, user_id=uid, total_points=score)

    # Highest score first → user 2 should be rank 0 in 0-based.
    assert await lb.rank_of(1, 2) == 0
    assert await lb.rank_of(1, 1) == 1
    assert await lb.rank_of(1, 3) == 2


@pytest.mark.asyncio
async def test_solve_time_tiebreak(fake_redis) -> None:
    lb = LeaderboardService(fake_redis)
    # Two users tied at 100 points.
    await lb.add_participant(1, user_id=10, total_points=100)
    await lb.add_participant(1, user_id=11, total_points=100)
    # User 10 solved faster.
    await lb.record_solve(1, user_id=10, problem_id=1, solve_seconds=120.0)
    await lb.record_solve(1, user_id=10, problem_id=2, solve_seconds=60.0)
    await lb.record_solve(1, user_id=11, problem_id=1, solve_seconds=300.0)

    top = await lb.top_with_tiebreak(1, limit=10)
    assert top[0]["user_id"] == 10
    assert top[0]["total_solve_seconds"] == 180.0
    assert top[1]["user_id"] == 11
    assert top[1]["total_solve_seconds"] == 300.0


@pytest.mark.asyncio
async def test_top_limits_results(fake_redis) -> None:
    lb = LeaderboardService(fake_redis)
    for uid in range(20):
        await lb.add_participant(1, user_id=uid, total_points=uid * 10)
    top = await lb.top(1, limit=5)
    assert len(top) == 5
