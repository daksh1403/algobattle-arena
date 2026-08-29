"""Common pagination / cursor helpers.

Pagination is offset-based for now — the data sets are small enough that
we don't need keyset cursors yet.  When problems/contests grow, switch to
cursor pagination (the interface here is the only thing callers see).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    """Query params for paging."""

    page: int = Field(1, ge=1, description="1-based page index")
    size: int = Field(20, ge=1, le=100, description="items per page (max 100)")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        return self.size


class Page(BaseModel, Generic[T]):
    """Generic paginated response envelope."""

    items: list[T]
    total: int
    page: int
    size: int

    @property
    def pages(self) -> int:
        if self.size == 0:
            return 0
        return (self.total + self.size - 1) // self.size


@dataclass
class PageItems(Generic[T]):
    """Plain (non-Pydantic) paged result from a service layer.

    Services return `PageItems[T]` (raw ORM objects) and routers map them
    into `Page[Schema]` for serialization.  This keeps Pydantic models out
    of the service layer so we never validate ORM objects against
    `Page[SomeModel]` (which Pydantic can't schema-ify).
    """

    items: list[T]
    total: int
    page: int
    size: int


__all__ = ["PageParams", "Page", "PageItems"]
