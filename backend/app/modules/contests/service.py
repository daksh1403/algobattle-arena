"""Contests service — CRUD + join + simple leaderboard aggregation.

Note: a separate `app/modules/leaderboard` module owns the Redis-backed
*live* leaderboard.  This service only manages SQL state — the leaderboard
module reads/updates the ZSET as submissions are graded.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.pagination import PageItems, PageParams
from app.modules.contests.models import Contest, ContestParticipant, ContestProblem
from app.modules.contests.schemas import ContestCreate


class ContestService:
    """Stateless business-logic façade for `Contest` operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _contest_select() -> Any:
        """Base SELECT that eager-loads the relationship `contest_problems`.

        Pydantic `model_validate` (from_attributes) touches the relationship,
        so it must be loaded inside the greenlet — otherwise SQLAlchemy raises
        `MissingGreenlet` when the async session is not in a greenlet context.
        """
        return select(Contest).options(selectinload(Contest.contest_problems))

    # ---- create -------------------------------------------------------

    async def create(self, payload: ContestCreate) -> Contest:
        contest = Contest(
            name=payload.name,
            description=payload.description,
            start_at=payload.start_at,
            end_at=payload.end_at,
            is_active=payload.is_active,
        )
        # Attach problems with auto-incremented position.
        for idx, problem_id in enumerate(payload.problem_ids):
            contest.contest_problems.append(
                ContestProblem(problem_id=problem_id, position=idx, score=100)
            )
        self.session.add(contest)
        await self.session.commit()
        await self.session.refresh(contest, attribute_names=["contest_problems"])
        return contest

    # ---- read ---------------------------------------------------------

    async def get_by_id(self, contest_id: int) -> Contest:
        stmt = self._contest_select().where(Contest.id == contest_id)
        contest = (await self.session.execute(stmt)).scalar_one_or_none()
        if contest is None:
            raise NotFoundError(f"contest {contest_id} not found")
        return contest

    async def list(
        self,
        *,
        params: PageParams,
        active_only: bool = False,
    ) -> PageItems[Contest]:
        stmt = self._contest_select()
        if active_only:
            now = datetime.now(tz=UTC)
            stmt = stmt.where(
                Contest.is_active.is_(True),
                Contest.start_at <= now,
                Contest.end_at >= now,
            )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Contest.start_at.asc()).offset(params.offset).limit(params.limit)
        items = list((await self.session.execute(stmt)).scalars().all())
        return PageItems(items=items, total=total, page=params.page, size=params.size)

    # ---- join ---------------------------------------------------------

    async def join(self, contest_id: int, user_id: int) -> ContestParticipant:
        contest = await self.get_by_id(contest_id)
        now = datetime.now(tz=UTC)

        def _as_aware(dt: datetime) -> datetime:
            """SQLite returns naive datetimes; Postgres returns aware ones."""
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt

        start_at = _as_aware(contest.start_at)
        end_at = _as_aware(contest.end_at)
        if start_at > now or end_at < now:
            raise ValidationError("contest is not currently running")

        stmt = select(ContestParticipant).where(
            ContestParticipant.contest_id == contest_id,
            ContestParticipant.user_id == user_id,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("user already joined this contest")

        participant = ContestParticipant(contest_id=contest_id, user_id=user_id)
        self.session.add(participant)
        await self.session.commit()
        await self.session.refresh(participant)
        return participant

    async def list_participants(self, contest_id: int) -> list[ContestParticipant]:
        await self.get_by_id(contest_id)  # raises NotFoundError if missing
        stmt = (
            select(ContestParticipant)
            .where(ContestParticipant.contest_id == contest_id)
            .order_by(ContestParticipant.total_points.desc(), ContestParticipant.joined_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    # ---- point adjustment (called by submissions.tasks) ---------------

    async def adjust_points(self, contest_id: int, user_id: int, delta: int) -> None:
        """Adjust a participant's total_points (negative `delta` on penalty)."""
        stmt = select(ContestParticipant).where(
            ContestParticipant.contest_id == contest_id,
            ContestParticipant.user_id == user_id,
        )
        participant = (await self.session.execute(stmt)).scalar_one_or_none()
        if participant is None:
            # User joined the contest after auto-joining logic? Skip.
            return
        participant.total_points += delta
        await self.session.commit()


__all__ = ["ContestService"]
