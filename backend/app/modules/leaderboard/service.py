"""Redis-backed leaderboard service.

Two ZSETs per contest:

    contest:{id}:leaderboard          — score = total_points, member = user_id
    contest:{id}:solve_times          — score = -solve_seconds, member = "{user_id}:{problem_id}"

The first is the public leaderboard (higher score = better).  The second
lets us break ties by fastest solve (lower seconds → higher ZSET score,
since ZRANGEBYSCORE returns highest-first).
"""
from __future__ import annotations

# redis.asyncio and fakeredis.aioredis have different (imprecise) stub
# shapes, so we type the client as a narrow protocol here.
from typing import Any, Protocol


class RedisLike(Protocol):
    async def zadd(self, key: str, mapping: dict[str, float | int], **kwargs: Any) -> Any: ...
    async def zincrby(self, key: str, amount: float, member: str) -> Any: ...
    async def zscore(self, key: str, member: str) -> Any: ...
    async def zrevrank(self, key: str, member: str) -> Any: ...
    async def zrevrange(
        self, key: str, start: int, end: int, withscores: bool = False, **kwargs: Any
    ) -> Any: ...
    async def zrange(
        self, key: str, start: int, end: int, withscores: bool = False, **kwargs: Any
    ) -> Any: ...


# Score-tiebreaker: 0.001 * problem_count solves the problem of equal-point
# users being indistinguishable.  The actual tiebreak comes from the
# `solve_times` ZSET read by `top_with_tiebreak`.
_TIE_EPSILON = 0.001


def _key(contest_id: int) -> str:
    return f"contest:{contest_id}:leaderboard"


def _solve_time_key(contest_id: int) -> str:
    return f"contest:{contest_id}:solve_times"


def _user_member(user_id: int) -> str:
    return str(user_id)


def _solve_member(user_id: int, problem_id: int) -> str:
    return f"{user_id}:{problem_id}"


class LeaderboardService:
    """Thin wrapper around Redis ZSETs.

    Stateless on the Python side — everything lives in Redis under
    `contest:{id}:leaderboard` and `contest:{id}:solve_times`.
    """

    def __init__(self, redis_client: RedisLike) -> None:
        self.redis = redis_client

    # ---- basic ZSET ops ----------------------------------------------

    async def add_participant(
        self, contest_id: int, user_id: int, *, total_points: int = 0
    ) -> None:
        """Initialise a user at a given point total (idempotent)."""
        await self.redis.zadd(
            _key(contest_id), {_user_member(user_id): total_points}, nx=True
        )

    async def set_score(self, contest_id: int, user_id: int, total_points: int) -> None:
        await self.redis.zadd(
            _key(contest_id), {_user_member(user_id): total_points}
        )

    async def increment(self, contest_id: int, user_id: int, delta: int) -> float:
        """Add `delta` to a user's score and return the new value."""
        result = await self.redis.zincrby(_key(contest_id), delta, _user_member(user_id))
        return float(result)

    async def score_of(self, contest_id: int, user_id: int) -> float | None:
        result = await self.redis.zscore(_key(contest_id), _user_member(user_id))
        return None if result is None else float(result)

    async def rank_of(self, contest_id: int, user_id: int) -> int | None:
        result = await self.redis.zrevrank(_key(contest_id), _user_member(user_id))
        return None if result is None else int(result)

    async def top(self, contest_id: int, limit: int = 50) -> list[dict[str, Any]]:
        """Return the top-N entries (highest score first).

        Each entry is `{"user_id": int, "score": float}`.
        """
        raw = await self.redis.zrevrange(
            _key(contest_id), 0, max(0, limit - 1), withscores=True
        )
        return [
            {"user_id": int(member), "score": float(score)}
            for member, score in raw
        ]

    # ---- solve-time secondary index ----------------------------------

    async def record_solve(
        self,
        contest_id: int,
        user_id: int,
        problem_id: int,
        solve_seconds: float,
    ) -> None:
        """Record a problem's solve time.  Lower seconds = higher ZSET score.

        Score is `-solve_seconds`; in case of equal seconds the most recent
        write wins (ZADD overwrites by default).
        """
        await self.redis.zadd(
            _solve_time_key(contest_id),
            {_solve_member(user_id, problem_id): -solve_seconds},
        )

    async def top_with_tiebreak(self, contest_id: int, limit: int = 50) -> list[dict[str, Any]]:
        """Top-N entries with total-points tiebroken by sum of solve times.

        Returns entries sorted first by `total_points` DESC, then by
        `aggregate_solve_seconds` ASC.
        """
        raw = await self.redis.zrevrange(
            _key(contest_id), 0, -1, withscores=True
        )
        if not raw:
            return []

        # Aggregate solve-time per user.
        solve_raw = await self.redis.zrange(
            _solve_time_key(contest_id), 0, -1, withscores=True
        )
        solve_totals: dict[int, float] = {}
        for member, neg_seconds in solve_raw:
            uid_s, _pid_s = str(member).split(":", 1)
            uid = int(uid_s)
            # Negative score → positive seconds.
            solve_totals[uid] = solve_totals.get(uid, 0.0) + (-float(neg_seconds))

        entries = [
            {
                "user_id": int(uid),
                "score": int(score),
                "total_solve_seconds": round(solve_totals.get(int(uid), 0.0), 3),
                "rank": 0,
            }
            for uid, score in raw
        ]
        entries.sort(
            key=lambda e: (-e["score"], e["total_solve_seconds"])
        )
        for i, e in enumerate(entries[:limit]):
            e["rank"] = i + 1
        return entries[:limit]


__all__ = ["LeaderboardService"]
