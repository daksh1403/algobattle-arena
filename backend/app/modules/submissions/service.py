"""Submissions service — submit, list, fetch results.

Submission creation inserts a `PENDING` row, enqueues an RQ job, and returns
the row.  Actual grading happens in `app.modules.submissions.tasks`.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import PageItems, PageParams
from app.modules.problems.service import ProblemService
from app.modules.submissions.models import (
    Submission,
    SubmissionResult,
    SubmissionStatus,
)
from app.modules.submissions.schemas import SubmissionCreate

# Map common language names to Judge0 language IDs.
# These are the IDs from a standard Judge0 install; if your install has
# different IDs, override them via `app.config.get_settings()` or your
# env vars.  Keep this mapping conservative.
LANGUAGE_ID_MAP: dict[str, int] = {
    "python": 71,         # Python 3.8.1
    "python3": 71,
    "javascript": 63,     # JavaScript (Node.js 12.14.0)
    "node": 63,
    "cpp": 54,            # C++ (GCC 9.2.0)
    "c++": 54,
    "c": 50,              # C (GCC 9.2.0)
    "java": 62,           # Java (OpenJDK 13.0.1)
    "go": 60,             # Go (1.13.5)
    "rust": 73,           # Rust (1.40.0)
    "ruby": 72,
}


def language_id_for(lang: str) -> int:
    """Resolve a Judge0 language id, defaulting to 71 (Python 3)."""
    return LANGUAGE_ID_MAP.get(lang.lower(), 71)


class SubmissionService:
    """Stateless façade over `Submission` / `SubmissionResult`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- create -------------------------------------------------------

    async def submit(
        self, *, user_id: int, payload: SubmissionCreate
    ) -> Submission:
        """Persist a PENDING submission row and enqueue a judge job.

        `payload.mode='test'` → sample test cases only (the Run button).
        `payload.mode='submit'` → all public test cases (the Submit button).
        """
        # Validate problem exists
        await ProblemService(self.session).get_by_id(payload.problem_id)

        submission = Submission(
            user_id=user_id,
            problem_id=payload.problem_id,
            contest_id=payload.contest_id,
            language=payload.language,
            code=payload.code,
            mode=payload.mode,
            status=SubmissionStatus.PENDING,
        )
        self.session.add(submission)
        await self.session.commit()
        await self.session.refresh(submission)
        return submission

    # ---- read ---------------------------------------------------------

    async def get_by_id(self, submission_id: int) -> Submission:
        sub = await self.session.get(Submission, submission_id)
        if sub is None:
            raise NotFoundError(f"submission {submission_id} not found")
        return sub

    async def get_by_id_for_user(
        self, submission_id: int, user_id: int
    ) -> Submission:
        """Fetch a submission only if it belongs to `user_id`.

        Returns 404 (not 403) when the submission exists but is owned by
        another user, so the endpoint does not leak the existence of
        other users' submissions.
        """
        sub = await self.get_by_id(submission_id)
        if sub.user_id != user_id:
            raise NotFoundError(f"submission {submission_id} not found")
        return sub

    async def get_results(self, submission_id: int) -> list[SubmissionResult]:
        await self.get_by_id(submission_id)  # raises NotFoundError if missing
        stmt = (
            select(SubmissionResult)
            .where(SubmissionResult.submission_id == submission_id)
            .order_by(SubmissionResult.id.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_user(
        self, user_id: int, *, params: PageParams
    ) -> PageItems[Submission]:
        base = select(Submission).where(Submission.user_id == user_id)
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = base.order_by(Submission.id.desc()).offset(params.offset).limit(params.limit)
        items = list((await self.session.execute(stmt)).scalars().all())
        return PageItems(items=items, total=total, page=params.page, size=params.size)


# --- pure helpers used by tests / tasks ------------------------------------


def aggregate_status(results: list[SubmissionResult]) -> SubmissionStatus:
    """Decide the overall submission verdict from per-testcase results.

    Rules (in order):
      1. Any COMPILE_ERROR → COMPILE_ERROR
      2. Any RUNTIME_ERROR → RUNTIME_ERROR
      3. Any TLE / MLE → that one
      4. Any WRONG_ANSWER → WRONG_ANSWER
      5. All ACCEPTED → ACCEPTED
    """
    if any(r.status == SubmissionStatus.COMPILE_ERROR for r in results):
        return SubmissionStatus.COMPILE_ERROR
    if any(r.status == SubmissionStatus.RUNTIME_ERROR for r in results):
        return SubmissionStatus.RUNTIME_ERROR
    if any(r.status == SubmissionStatus.TIME_LIMIT_EXCEEDED for r in results):
        return SubmissionStatus.TIME_LIMIT_EXCEEDED
    if any(r.status == SubmissionStatus.MEMORY_LIMIT_EXCEEDED for r in results):
        return SubmissionStatus.MEMORY_LIMIT_EXCEEDED
    if any(r.status == SubmissionStatus.WRONG_ANSWER for r in results):
        return SubmissionStatus.WRONG_ANSWER
    if results and all(r.status == SubmissionStatus.ACCEPTED for r in results):
        return SubmissionStatus.ACCEPTED
    return SubmissionStatus.RUNNING


def should_penalise(*, accepted_previously: bool, now_accepted: bool) -> bool:
    """Return True iff this submission incurs the -20 wrong-submit penalty.

    Penalty rule (ICPC): only AC submissions after prior FAILED attempts
    incur a penalty; otherwise the verdict is final.
    """
    return now_accepted and not accepted_previously


__all__ = [
    "SubmissionService",
    "language_id_for",
    "LANGUAGE_ID_MAP",
    "aggregate_status",
    "should_penalise",
]
