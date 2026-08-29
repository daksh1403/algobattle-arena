"""Pydantic schemas for the problems module."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.problems.models import Difficulty, SolutionVisibility

# --- Create / Update payloads ---------------------------------------------


class TestCaseCreate(BaseModel):
    """A test case shipped inside a `ProblemCreate` payload."""

    __test__ = False  # pytest: don't try to collect this as a test class

    input: str = Field(..., description="JSON-encoded argument list")
    expected_output: str = Field(..., description="JSON-encoded expected value")
    is_sample: bool = False
    is_public: bool = True


class ProblemCreate(BaseModel):
    """Create a new problem.  Used by admins only (no auth wiring here)."""

    slug: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9-]+$")
    title: str = Field(..., min_length=1, max_length=200)
    statement_md: str = Field(..., min_length=1)
    difficulty: Difficulty = Difficulty.EASY
    tags: list[str] = Field(default_factory=list, max_length=16)
    time_limit_ms: int = Field(2000, ge=100, le=15000)
    memory_limit_kb: int = Field(262144, ge=16384, le=1048576)
    boilerplate_code: dict[str, str] = Field(default_factory=dict)
    function_signature: str = ""
    solution_visibility: SolutionVisibility = SolutionVisibility.PRIVATE
    test_cases: list[TestCaseCreate] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def _strip_tags(cls, v: list[str]) -> list[str]:
        cleaned = [t.strip().lower() for t in v if t.strip()]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("tags must be unique")
        return cleaned


class ProblemUpdate(BaseModel):
    """Partial update — only admins should call this."""

    title: str | None = None
    statement_md: str | None = None
    difficulty: Difficulty | None = None
    tags: list[str] | None = None
    time_limit_ms: int | None = None
    memory_limit_kb: int | None = None
    boilerplate_code: dict[str, str] | None = None
    solution_visibility: SolutionVisibility | None = None


# --- Read models ---------------------------------------------------------


class TestCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    input: str
    expected_output: str
    is_sample: bool
    is_public: bool


class ProblemOut(BaseModel):
    """Public problem representation (no solution leakage)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    statement_md: str
    difficulty: Difficulty
    tags: list[str]
    time_limit_ms: int
    memory_limit_kb: int
    boilerplate_code: dict[str, Any]
    function_signature: str
    solution_visibility: SolutionVisibility
    created_at: datetime


class ProblemSummary(BaseModel):
    """Trimmed problem for leaderboards / contest lists."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    difficulty: Difficulty
    tags: list[str]


__all__ = [
    "TestCaseCreate",
    "TestCaseOut",
    "ProblemCreate",
    "ProblemUpdate",
    "ProblemOut",
    "ProblemSummary",
]
