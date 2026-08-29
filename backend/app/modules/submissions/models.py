"""ORM models for submissions + per-testcase results."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.modules.contests.models import Contest
    from app.modules.problems.models import Problem, TestCase
    from app.modules.users.models import User


class SubmissionStatus(enum.StrEnum):
    """Lifecycle states for a submission.

    Invariant: PENDING → RUNNING → <terminal>.  Terminal states never
    transition back.
    """

    PENDING = "pending"
    RUNNING = "running"

    # Terminal states
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "tle"
    MEMORY_LIMIT_EXCEEDED = "mle"
    RUNTIME_ERROR = "runtime_error"
    COMPILE_ERROR = "compile_error"
    INTERNAL_ERROR = "internal_error"


TERMINAL_STATUSES: frozenset[SubmissionStatus] = frozenset(
    {
        SubmissionStatus.ACCEPTED,
        SubmissionStatus.WRONG_ANSWER,
        SubmissionStatus.TIME_LIMIT_EXCEEDED,
        SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
        SubmissionStatus.RUNTIME_ERROR,
        SubmissionStatus.COMPILE_ERROR,
        SubmissionStatus.INTERNAL_ERROR,
    }
)


class Submission(Base):
    """A user's code submission against a (problem, [contest])."""

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), index=True, nullable=False
    )
    contest_id: Mapped[int | None] = mapped_column(
        ForeignKey("contests.id", ondelete="SET NULL"), index=True, nullable=True
    )

    language: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    # "test" = sample cases only (Run button), "submit" = all hidden cases.
    mode: Mapped[str] = mapped_column(String(16), default="submit", nullable=False)

    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_status", native_enum=False, length=32),
        default=SubmissionStatus.PENDING,
        nullable=False,
        index=True,
    )
    runtime_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_kb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship("User", back_populates="submissions")
    problem: Mapped[Problem] = relationship("Problem", back_populates="submissions")
    contest: Mapped[Contest | None] = relationship("Contest")
    results: Mapped[list[SubmissionResult]] = relationship(
        "SubmissionResult",
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="SubmissionResult.id",
    )


class SubmissionResult(Base):
    """Per-testcase verdict for a submission."""

    __tablename__ = "submission_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    testcase_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_cases.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_result_status", native_enum=False, length=32),
        nullable=False,
    )
    runtime_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_kb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout: Mapped[str] = mapped_column(Text, default="", nullable=False)
    stderr: Mapped[str] = mapped_column(Text, default="", nullable=False)
    compile_output: Mapped[str] = mapped_column(Text, default="", nullable=False)

    submission: Mapped[Submission] = relationship("Submission", back_populates="results")
    testcase: Mapped[TestCase | None] = relationship("TestCase")


__all__ = [
    "Submission",
    "SubmissionResult",
    "SubmissionStatus",
    "TERMINAL_STATUSES",
]
