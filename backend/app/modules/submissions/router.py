"""Submissions router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app import rq_app
from app.core.pagination import Page, PageParams
from app.deps import CurrentUserId, DBSession, get_limiter
from app.modules.submissions.schemas import (
    ResultOut,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionOut,
)
from app.modules.submissions.service import SubmissionService

router = APIRouter(prefix="/submissions", tags=["submissions"])

# Rate limiter instance (shared across routes).
# In test mode (no limiter state), skip rate limiting to avoid breaking the test client.
_limiter = get_limiter()


def _rate_limit():
    """Return a rate-limit decorator, or a no-op if the app has no limiter state."""
    from fastapi import Request

    from app.config import get_settings

    if get_settings().is_test:
        return lambda func: func  # no-op in tests

    def decorator(func):
        from slowapi import Limiter

        limiter: Limiter = get_limiter()
        decorated = limiter.limit("30/minute")(func)
        # Wrap so we can inject Request parameter.
        async def wrapper(request: Request, *args, **kwargs):
            return await decorated(request, *args, **kwargs)

        import functools

        return functools.wraps(func)(wrapper)

    return decorator


async def _enqueue_and_maybe_await(result: object) -> None:
    """Fire-and-forget enqueue that also supports async callables.

    Production path: `rq_app.enqueue_judge_submission` is synchronous and
    returns an RQ job — we just drop it.

    Test path: callers (pytest) replace the function with an `async def`
    that runs the judge inline; we await it so the verdict is applied
    before the request returns (still atomic, same session lifecycle).
    """
    if hasattr(result, "__await__"):
        await result


@router.post(
    "",
    response_model=SubmissionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit code for a problem",
)
@_rate_limit()
async def create_submission(
    request: Request,
    payload: SubmissionCreate,
    user_id: CurrentUserId,
    session: DBSession,
) -> SubmissionOut:
    service = SubmissionService(session)
    submission = await service.submit(user_id=user_id, payload=payload)
    # Enqueue judge work to the RQ queue.  An RQ worker (separate process)
    # picks it up and runs `judge_submission` to completion.  We tolerate
    # enqueue failures by returning the submission anyway — the periodic
    # stuck-submission sweeper in `checker.py` will pick up anything left
    # in PENDING for more than 60 s.
    #
    # In tests the queue is monkey-patched to call the judge inline and
    # return a coroutine, which we await so the verdict is applied
    # before the request returns.
    try:
        await _enqueue_and_maybe_await(rq_app.enqueue_judge_submission(submission.id))
    except Exception:  # noqa: BLE001
        pass
    return SubmissionOut.model_validate(submission)


@router.get(
    "/{submission_id}",
    response_model=SubmissionDetail,
    summary="Fetch a submission (with results if judged)",
)
async def get_submission(
    submission_id: int,
    user_id: CurrentUserId,
    session: DBSession,
) -> SubmissionDetail:
    service = SubmissionService(session)
    submission = await service.get_by_id_for_user(submission_id, user_id)
    results = await service.get_results(submission_id)
    return SubmissionDetail(
        **SubmissionOut.model_validate(submission).model_dump(),
        results=[ResultOut.model_validate(r) for r in results],
    )


@router.get(
    "/{submission_id}/results",
    response_model=list[ResultOut],
    summary="Fetch only the per-testcase results",
)
async def get_results(
    submission_id: int,
    user_id: CurrentUserId,
    session: DBSession,
) -> list[ResultOut]:
    service = SubmissionService(session)
    # Ownership check — 404 (not 403) to avoid leaking existence of other users' submissions.
    await service.get_by_id_for_user(submission_id, user_id)
    results = await service.get_results(submission_id)
    return [ResultOut.model_validate(r) for r in results]


@router.get(
    "",
    response_model=Page[SubmissionOut],
    summary="List your own submissions",
)
async def list_my_submissions(
    user_id: CurrentUserId,
    session: DBSession,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[SubmissionOut]:
    service = SubmissionService(session)
    obj = await service.list_for_user(user_id, params=PageParams(page=page, size=size))
    return Page[SubmissionOut](
        items=[SubmissionOut.model_validate(s) for s in obj.items],
        total=obj.total,
        page=obj.page,
        size=obj.size,
    )


@router.post(
    "/{submission_id}/run",
    response_model=SubmissionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Run a submission against sample test cases only (no judging)",
)
async def run_submission(
    payload: SubmissionCreate,
    user_id: CurrentUserId,
    session: DBSession,
) -> SubmissionOut:
    """`/run` is a thin wrapper that creates a `mode="test"` submission and
    enqueues it on the same RQ queue as `/submit`.  The judge filters
    testcases by mode at grading time (see `tasks._grade_submission`), so
    the worker naturally only judges the sample cases here."""
    service = SubmissionService(session)
    # Force the mode to "test" regardless of what the client sent — the
    # whole point of /run is sample cases only.
    payload = payload.model_copy(update={"mode": "test"})
    submission = await service.submit(user_id=user_id, payload=payload)
    try:
        await _enqueue_and_maybe_await(rq_app.enqueue_judge_submission(submission.id))
    except Exception:  # noqa: BLE001
        pass
    return SubmissionOut.model_validate(submission)


__all__ = ["router"]
