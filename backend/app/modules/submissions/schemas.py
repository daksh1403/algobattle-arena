"""Pydantic schemas for the submissions module."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.submissions.models import SubmissionStatus


class SubmissionCreate(BaseModel):
    """Payload to create a new submission."""

    problem_id: int = Field(..., ge=1)
    language: str = Field(..., min_length=1, max_length=32, examples=["python3"])
    code: str = Field(..., min_length=1, max_length=100_000)
    contest_id: int | None = None
    # "test" = run against visible sample test cases only (the Run button);
    # "submit" = judge against all hidden test cases (the Submit button).
    mode: Literal["test", "submit"] = "submit"


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    problem_id: int
    contest_id: int | None
    language: str
    mode: str = "submit"
    status: SubmissionStatus
    runtime_ms: int | None
    memory_kb: int | None
    score: int
    created_at: datetime
    finished_at: datetime | None


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    submission_id: int
    testcase_id: int | None
    status: SubmissionStatus
    runtime_ms: int | None
    memory_kb: int | None
    stdout: str
    stderr: str
    compile_output: str


class SubmissionDetail(SubmissionOut):
    """Submission + its per-testcase results."""

    results: list[ResultOut] = Field(default_factory=list)


__all__ = ["SubmissionCreate", "SubmissionOut", "ResultOut", "SubmissionDetail"]
