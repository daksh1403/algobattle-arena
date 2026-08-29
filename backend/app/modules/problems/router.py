"""Problems router — read-only listing + detail + test cases."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.pagination import Page, PageParams
from app.deps import AdminUserId, DBSession
from app.modules.problems.models import Difficulty
from app.modules.problems.schemas import (
    ProblemCreate,
    ProblemOut,
    ProblemSummary,
    TestCaseCreate,
    TestCaseOut,
)
from app.modules.problems.service import ProblemService

router = APIRouter(prefix="/problems", tags=["problems"])


@router.get("", response_model=Page[ProblemSummary], summary="List problems")
async def list_problems(
    session: DBSession,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    difficulty: Difficulty | None = None,
    tag: str | None = None,
    search: str | None = None,
) -> Page[ProblemSummary]:
    service = ProblemService(session)
    page_obj = await service.list(
        params=PageParams(page=page, size=size),
        difficulty=difficulty,
        tag=tag,
        search=search,
    )
    return Page[ProblemSummary](
        items=[ProblemSummary.model_validate(p) for p in page_obj.items],
        total=page_obj.total,
        page=page_obj.page,
        size=page_obj.size,
    )


@router.post("", response_model=ProblemOut, status_code=status.HTTP_201_CREATED,
             summary="Create a problem (admin)")
async def create_problem(
    payload: ProblemCreate,
    session: DBSession,
    _admin: AdminUserId,
) -> ProblemOut:
    service = ProblemService(session)
    problem = await service.create(payload)
    return ProblemOut.model_validate(problem)


@router.get("/{slug}", response_model=ProblemOut, summary="Get a problem by slug")
async def get_problem(slug: str, session: DBSession) -> ProblemOut:
    service = ProblemService(session)
    problem = await service.get_by_slug(slug)
    return ProblemOut.model_validate(problem)


@router.get("/{slug}/testcases", response_model=list[TestCaseOut],
            summary="Get a problem's sample test cases")
async def get_testcases(
    slug: str,
    session: DBSession,
    sample_only: bool = True,
) -> list[TestCaseOut]:
    service = ProblemService(session)
    problem = await service.get_by_slug(slug)
    cases = await service.list_test_cases(
        problem.id, samples_only=sample_only, public_only=True
    )
    return [TestCaseOut.model_validate(c) for c in cases]


@router.post(
    "/{problem_id}/testcases",
    response_model=TestCaseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a test case to a problem (admin only)",
)
async def add_test_case(
    problem_id: int,
    payload: TestCaseCreate,
    _admin: AdminUserId,
    session: DBSession,
) -> TestCaseOut:
    service = ProblemService(session)
    tc = await service.add_test_case(problem_id, payload)
    return TestCaseOut.model_validate(tc)


__all__ = ["router"]
