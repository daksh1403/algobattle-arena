"""Pydantic schemas for contests."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContestCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    start_at: datetime
    end_at: datetime
    is_active: bool = True
    problem_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_window(self) -> ContestCreate:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class ContestProblemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    problem_id: int
    position: int
    score: int


class ContestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    start_at: datetime
    end_at: datetime
    is_active: bool
    created_at: datetime
    contest_problems: list[ContestProblemOut] = Field(default_factory=list)


class ContestSummary(BaseModel):
    """Lightweight contest listing entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_at: datetime
    end_at: datetime
    is_active: bool


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contest_id: int
    user_id: int
    total_points: int
    joined_at: datetime


__all__ = [
    "ContestCreate",
    "ContestOut",
    "ContestSummary",
    "ContestProblemOut",
    "ParticipantOut",
]
