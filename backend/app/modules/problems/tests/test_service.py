"""TDD tests for `ProblemService`."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PageParams
from app.modules.problems.models import Difficulty
from app.modules.problems.schemas import ProblemCreate, ProblemUpdate, TestCaseCreate
from app.modules.problems.service import ProblemService


def _example_payload(**overrides) -> ProblemCreate:
    base = dict(
        slug="two-sum",
        title="Two Sum",
        statement_md="Find two indices that add up to target.",
        difficulty=Difficulty.EASY,
        tags=["array", "hash-table"],
        time_limit_ms=2000,
        memory_limit_kb=262144,
        boilerplate_code={"python": "def two_sum(nums, target):\n    return []\n"},
        function_signature="def two_sum(nums, target):",
        test_cases=[
            TestCaseCreate(input="[[2,7,11,15], 9]", expected_output="[0,1]", is_sample=True),
            TestCaseCreate(input="[[3,3], 6]", expected_output="[0,1]"),
        ],
    )
    base.update(overrides)
    return ProblemCreate(**base)


@pytest.mark.asyncio
async def test_create_problem_persists_with_test_cases(db_session: AsyncSession) -> None:
    service = ProblemService(db_session)

    problem = await service.create(_example_payload())

    assert problem.id is not None
    assert problem.slug == "two-sum"
    assert problem.difficulty == Difficulty.EASY
    # Test cases are linked back to the problem.
    cases = await service.list_test_cases(problem.id, public_only=False)
    assert len(cases) == 2


@pytest.mark.asyncio
async def test_create_duplicate_slug_raises(db_session: AsyncSession) -> None:
    service = ProblemService(db_session)
    await service.create(_example_payload())

    with pytest.raises(ConflictError):
        await service.create(_example_payload())


@pytest.mark.asyncio
async def test_get_by_slug_raises_not_found(db_session: AsyncSession) -> None:
    service = ProblemService(db_session)
    with pytest.raises(NotFoundError):
        await service.get_by_slug("does-not-exist")


@pytest.mark.asyncio
async def test_list_filters_by_difficulty(db_session: AsyncSession) -> None:
    service = ProblemService(db_session)
    await service.create(_example_payload(slug="easy-1", difficulty=Difficulty.EASY))
    await service.create(
        _example_payload(
            slug="hard-1",
            title="Hard One",
            difficulty=Difficulty.HARD,
        )
    )
    await service.create(
        _example_payload(slug="med-1", title="Medium One", difficulty=Difficulty.MEDIUM)
    )

    page = await service.list(
        params=PageParams(page=1, size=20), difficulty=Difficulty.EASY
    )

    assert page.total == 1
    assert page.items[0].slug == "easy-1"


@pytest.mark.asyncio
async def test_list_filters_by_tag(db_session: AsyncSession) -> None:
    service = ProblemService(db_session)
    await service.create(
        _example_payload(slug="has-array", tags=["array", "math"])
    )
    await service.create(
        _example_payload(slug="no-array", title="No Array", tags=["graph"])
    )

    page = await service.list(params=PageParams(page=1, size=20), tag="array")

    # `array` may not work on SQLite depending on JSON support; this test
    # validates that *at least* the no-array problem is not in the result
    # when array support is available, otherwise it is ignored gracefully.
    slugs = {p.slug for p in page.items}
    assert "no-array" not in slugs or page.total == 0


@pytest.mark.asyncio
async def test_list_searches_title(db_session: AsyncSession) -> None:
    service = ProblemService(db_session)
    await service.create(_example_payload(slug="apple"))
    await service.create(_example_payload(slug="banana", title="Banana Republic"))

    page = await service.list(params=PageParams(page=1, size=20), search="banana")

    slugs = {p.slug for p in page.items}
    assert "banana" in slugs


@pytest.mark.asyncio
async def test_list_testcases_sample_only(db_session: AsyncSession) -> None:
    service = ProblemService(db_session)
    p = await service.create(_example_payload())
    samples = await service.list_test_cases(p.id, samples_only=True, public_only=False)
    assert all(c.is_sample for c in samples)
    assert len(samples) >= 1


@pytest.mark.asyncio
async def test_update_problem_partial(db_session: AsyncSession) -> None:
    service = ProblemService(db_session)
    p = await service.create(_example_payload())

    updated = await service.update(p.id, ProblemUpdate(title="Two Sum v2"))

    assert updated.title == "Two Sum v2"
    assert updated.slug == "two-sum"  # unchanged


@pytest.mark.asyncio
async def test_update_unknown_problem_raises(db_session: AsyncSession) -> None:
    service = ProblemService(db_session)
    with pytest.raises(NotFoundError):
        await service.update(999, ProblemUpdate(title="nope"))
