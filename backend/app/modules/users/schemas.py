"""Pydantic schemas for the users module."""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")


class UserCreate(BaseModel):
    """Payload to register a new user."""

    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def _validate_username(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "username must be 3-32 chars and contain only letters, digits, '.', '_' or '-'"
            )
        return v


class LoginIn(BaseModel):
    """Login payload."""

    username_or_email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class UserOut(BaseModel):
    """Public-facing user representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    rating: int
    is_admin: bool = False
    created_at: datetime  # noqa: F821 - forward ref via pydantic


class TokenOut(BaseModel):
    """JWT auth response."""

    access_token: str
    token_type: str = "bearer"
    user: UserOut


__all__ = ["UserCreate", "LoginIn", "UserOut", "TokenOut"]


# Local import to break pydantic forward-ref cycle surprise
from datetime import datetime  # noqa: E402
