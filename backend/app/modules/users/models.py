"""User ORM model."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.modules.contests.models import ContestParticipant
    from app.modules.submissions.models import Submission


class User(Base):
    """A registered user (contestant)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    rating: Mapped[int] = mapped_column(Integer, default=1500, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    submissions: Mapped[list[Submission]] = relationship(
        "Submission", back_populates="user", cascade="all,delete-orphan"
    )
    contest_participations: Mapped[list[ContestParticipant]] = relationship(
        "ContestParticipant", back_populates="user", cascade="all,delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return f"<User id={self.id} username={self.username!r}>"


__all__ = ["User"]
