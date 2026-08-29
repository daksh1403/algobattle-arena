"""ORM models for problems + test cases."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base

if TYPE_CHECKING:
    from app.modules.submissions.models import Submission


class Difficulty(enum.StrEnum):
    """Problem difficulty — kept tiny on purpose."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class SolutionVisibility(enum.StrEnum):
    """Controls whether the reference solution is publicly viewable."""

    PUBLIC = "public"
    PRIVATE = "private"


# JSON column that uses JSONB on Postgres and plain JSON elsewhere (so the
# test database — SQLite — also works).
JSON_TYPE: Any = JSON().with_variant(JSONB(), "postgresql")


class Problem(Base):
    """A coding problem, with metadata + per-language boilerplate."""

    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    statement_md: Mapped[str] = mapped_column(Text, nullable=False)

    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(Difficulty, name="difficulty", native_enum=False, length=16),
        nullable=False,
        default=Difficulty.EASY,
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)).with_variant(JSON(), "sqlite"),
        default=list,
        nullable=False,
    )

    time_limit_ms: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)
    memory_limit_kb: Mapped[int] = mapped_column(Integer, default=262144, nullable=False)

    boilerplate_code: Mapped[dict[str, Any]] = mapped_column(
        JSON_TYPE, default=dict, nullable=False
    )
    function_signature: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    solution_visibility: Mapped[SolutionVisibility] = mapped_column(
        Enum(SolutionVisibility, name="solution_visibility", native_enum=False, length=16),
        default=SolutionVisibility.PRIVATE,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    test_cases: Mapped[list[TestCase]] = relationship(
        "TestCase",
        back_populates="problem",
        cascade="all, delete-orphan",
        order_by="TestCase.id",
    )
    submissions: Mapped[list[Submission]] = relationship(
        "Submission", back_populates="problem"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Problem id={self.id} slug={self.slug!r}>"


class TestCase(Base):
    """A single test case for a problem."""

    __test__ = False  # pytest: don't try to collect ORM models as tests

    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # JSON-serialised argument list and expected value — kept as TEXT so we
    # can ship test cases as plain JSON strings (trivially inspectable).
    input: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    problem: Mapped[Problem] = relationship("Problem", back_populates="test_cases")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TestCase id={self.id} problem_id={self.problem_id}>"


__all__ = [
    "Problem",
    "TestCase",
    "Difficulty",
    "SolutionVisibility",
]
