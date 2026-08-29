"""Contests router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.pagination import Page, PageParams
from app.deps import AdminUserId, CurrentUserId, DBSession
from app.modules.contests.schemas import (
    ContestCreate,
    ContestOut,
    ContestSummary,
    ParticipantOut,
)
from app.modules.contests.service import ContestService
from app.modules.leaderboard.service import LeaderboardService
from app.redis_client import get_redis

router = APIRouter(prefix="/contests", tags=["contests"])


@router.get("", response_model=Page[ContestSummary], summary="List contests")
async def list_contests(
    session: DBSession,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    active_only: bool = False,
) -> Page[ContestSummary]:
    service = ContestService(session)
    obj = await service.list(params=PageParams(page=page, size=size), active_only=active_only)
    return Page[ContestSummary](
        items=[ContestSummary.model_validate(c) for c in obj.items],
        total=obj.total,
        page=obj.page,
        size=obj.size,
    )


@router.post("", response_model=ContestOut, status_code=status.HTTP_201_CREATED,
             summary="Create a contest (admin)")
async def create_contest(
    payload: ContestCreate,
    session: DBSession,
    _admin: AdminUserId,
) -> ContestOut:
    service = ContestService(session)
    contest = await service.create(payload)
    return ContestOut.model_validate(contest)


@router.get("/{contest_id}", response_model=ContestOut, summary="Get a contest")
async def get_contest(contest_id: int, session: DBSession) -> ContestOut:
    service = ContestService(session)
    contest = await service.get_by_id(contest_id)
    return ContestOut.model_validate(contest)


@router.post(
    "/{contest_id}/join",
    response_model=ParticipantOut,
    status_code=status.HTTP_201_CREATED,
    summary="Join a contest",
)
async def join_contest(
    contest_id: int,
    user_id: CurrentUserId,
    session: DBSession,
) -> ParticipantOut:
    service = ContestService(session)
    participant = await service.join(contest_id, user_id)

    # Initialise the leaderboard entry so the user shows up at zero points.
    lb = LeaderboardService(get_redis())
    await lb.add_participant(contest_id, user_id, total_points=0)

    return ParticipantOut.model_validate(participant)


@router.get(
    "/{contest_id}/leaderboard",
    summary="Live contest leaderboard",
)
async def contest_leaderboard(
    contest_id: int,
    session: DBSession,
    top: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    service = ContestService(session)
    await service.get_by_id(contest_id)  # raises NotFoundError if missing

    lb = LeaderboardService(get_redis())
    entries = await lb.top(contest_id, limit=top)
    return {
        "contest_id": contest_id,
        "entries": entries,
    }


@router.get(
    "/{contest_id}/participants",
    response_model=list[ParticipantOut],
    summary="SQL-derived participant list (sorted by points)",
)
async def list_participants(
    contest_id: int,
    session: DBSession,
) -> list[ParticipantOut]:
    service = ContestService(session)
    items = await service.list_participants(contest_id)
    return [ParticipantOut.model_validate(p) for p in items]


__all__ = ["router"]
