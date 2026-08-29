"""Problems service — CRUD + filtering + pagination."""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import String, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PageItems, PageParams
from app.modules.problems.models import Difficulty, Problem, TestCase
from app.modules.problems.schemas import ProblemCreate, ProblemUpdate, TestCaseCreate


class ProblemService:
    """Stateless business-logic façade for `Problem` operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- create -------------------------------------------------------

    async def create(self, payload: ProblemCreate) -> Problem:
        existing = await self.session.execute(
            select(Problem).where(Problem.slug == payload.slug)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(f"problem with slug '{payload.slug}' already exists")

        problem = Problem(
            slug=payload.slug,
            title=payload.title,
            statement_md=payload.statement_md,
            difficulty=payload.difficulty,
            tags=payload.tags,
            time_limit_ms=payload.time_limit_ms,
            memory_limit_kb=payload.memory_limit_kb,
            boilerplate_code=payload.boilerplate_code,
            function_signature=payload.function_signature,
            solution_visibility=payload.solution_visibility,
        )
        problem.test_cases = [
            TestCase(
                input=tc.input,
                expected_output=tc.expected_output,
                is_sample=tc.is_sample,
                is_public=tc.is_public,
            )
            for tc in payload.test_cases
        ]
        self.session.add(problem)
        await self.session.commit()
        await self.session.refresh(problem)
        return problem

    # ---- read ---------------------------------------------------------

    async def get_by_id(self, problem_id: int) -> Problem:
        problem = await self.session.get(Problem, problem_id)
        if problem is None:
            raise NotFoundError(f"problem {problem_id} not found")
        return problem

    async def get_by_slug(self, slug: str) -> Problem:
        stmt = select(Problem).where(Problem.slug == slug)
        result = await self.session.execute(stmt)
        problem = result.scalar_one_or_none()
        if problem is None:
            raise NotFoundError(f"problem '{slug}' not found")
        return problem

    async def list(
        self,
        *,
        params: PageParams,
        difficulty: Difficulty | None = None,
        tag: str | None = None,
        search: str | None = None,
    ) -> PageItems[Problem]:
        """List problems with optional difficulty / tag / free-text filters."""
        base = select(Problem)
        if difficulty is not None:
            base = base.where(Problem.difficulty == difficulty)
        if tag:
            # `tags` is an ARRAY on Postgres and JSON on SQLite.  A portable
            # membership test is a LIKE on the serialised representation:
            # the tag appears as a quoted JSON string in both backends.
            base = base.where(
                func.cast(Problem.tags, String).ilike(f'%"{tag.lower()}"%')
            )
        if search:
            like = f"%{search.lower()}%"
            base = base.where(func.lower(Problem.title).like(like))

        # Total count
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        # Page
        stmt = base.order_by(Problem.id.asc()).offset(params.offset).limit(params.limit)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return PageItems(
            items=items, total=total, page=params.page, size=params.size
        )

    async def list_test_cases(
        self, problem_id: int, *, samples_only: bool = False, public_only: bool = True
    ) -> Sequence[TestCase]:
        await self.get_by_id(problem_id)  # raises NotFoundError if missing
        stmt = select(TestCase).where(TestCase.problem_id == problem_id)
        if samples_only:
            stmt = stmt.where(TestCase.is_sample.is_(True))
        if public_only:
            stmt = stmt.where(TestCase.is_public.is_(True))
        stmt = stmt.order_by(TestCase.id.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def add_test_case(
        self, problem_id: int, payload: TestCaseCreate
    ) -> TestCase:
        """Add one test case to an existing problem (admin only)."""
        await self.get_by_id(problem_id)  # raises NotFoundError if missing
        tc = TestCase(
            problem_id=problem_id,
            input=payload.input,
            expected_output=payload.expected_output,
            is_sample=payload.is_sample,
            is_public=payload.is_public,
        )
        self.session.add(tc)
        await self.session.commit()
        await self.session.refresh(tc)
        return tc

    # ---- update -------------------------------------------------------

    async def update(self, problem_id: int, payload: ProblemUpdate) -> Problem:
        problem = await self.get_by_id(problem_id)
        data = payload.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(problem, k, v)
        await self.session.commit()
        await self.session.refresh(problem)
        return problem


__all__ = ["ProblemService"]
