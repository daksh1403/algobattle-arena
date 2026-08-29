"""Leaderboard router — re-exposed via /contests/{id}/leaderboard in the
contests module.  This module exposes only utility endpoints for now.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import DBSession, RedisClient
from app.modules.contests.service import ContestService
from app.modules.leaderboard.service import LeaderboardService

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get(
    "/contests/{contest_id}",
    summary="Live contest leaderboard (with solve-time tiebreak)",
)
async def contest_leaderboard(
    contest_id: int,
    session: DBSession,
    redis_client: RedisClient,
    top: Annotated[int, Query(ge=1, le=200)] = 50,
):
    # Validate contest exists
    await ContestService(session).get_by_id(contest_id)

    lb = LeaderboardService(redis_client)
    entries = await lb.top_with_tiebreak(contest_id, limit=top)
    return {"contest_id": contest_id, "entries": entries}


__all__ = ["router"]
