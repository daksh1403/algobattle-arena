"""Pydantic schemas for contests."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


def _make_slug(name: str) -> str:
    """Generate a URL-safe slug from a contest name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug


def _as_aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; Postgres returns aware ones."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _contest_status(start_at: datetime, end_at: datetime) -> str:
    """Derive 'upcoming' | 'active' | 'past' from the contest window."""
    now = datetime.now(tz=timezone.utc)
    start = _as_aware(start_at)
    end = _as_aware(end_at)
    if start > now:
        return "upcoming"
    if end < now:
        return "past"
    return "active"


class ContestCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=200)
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

    @model_validator(mode="after")
    def _set_slug(self) -> ContestCreate:
        if not self.slug:
            self.slug = _make_slug(self.name)
        return self


class ContestProblemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    problem_id: int
    position: int
    score: int


class ContestOut(BaseModel):
    """Full contest response — matches frontend `ContestDetail`."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str = Field(alias="name")
    description: str
    start_time: datetime = Field(alias="start_at")
    end_time: datetime = Field(alias="end_at")
    is_active: bool
    created_at: datetime
    contest_problems: list[ContestProblemOut] = Field(default_factory=list)

    @computed_field
    @property
    def participant_count(self) -> int:
        return 0

    @computed_field
    @property
    def problem_count(self) -> int:
        return len(self.contest_problems)

    @computed_field
    @property
    def status(self) -> str:
        return _contest_status(self.start_time, self.end_time)


class ContestSummary(BaseModel):
    """Lightweight contest listing entry — matches frontend `Contest`."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str = Field(alias="name")
    start_time: datetime = Field(alias="start_at")
    end_time: datetime = Field(alias="end_at")
    is_active: bool

    @computed_field
    @property
    def participant_count(self) -> int:
        return 0

    @computed_field
    @property
    def problem_count(self) -> int:
        return 0

    @computed_field
    @property
    def status(self) -> str:
        return _contest_status(self.start_time, self.end_time)

    @computed_field
    @property
    def description(self) -> str:
        return ""


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
    "_make_slug",
]
