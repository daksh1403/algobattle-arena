"""FastAPI dependency providers.

These are the *only* bindings routers need to know about — they hide the
DB engine, redis client, and JWT plumbing behind simple callables so that
tests can override them with `app.dependency_overrides[...]`.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db import get_session
from app.modules.users.models import User
from app.redis_client import get_redis

# Type aliases — keeps FastAPI signatures readable.
DBSession = Annotated[AsyncSession, Depends(get_session)]
RedisClient = Annotated[object, Depends(get_redis)]


async def get_current_user_id(
    authorization: str | None = Header(default=None),
) -> int:
    """Extract + verify the bearer JWT and return `int(user_id)`.

    Modules that need the full `User` instance should call
    `app.modules.users.service.UserService(...).get_by_id(user_id)`.
    """
    if not authorization:
        raise UnauthorizedError("Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError("Authorization header must be: Bearer <token>")
    token = parts[1]
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc

    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedError("Token missing subject")
    try:
        return int(sub)
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError("Invalid token subject") from exc


# Optional version — returns None when no/invalid token is present.
async def get_current_user_id_optional(
    authorization: str | None = Header(default=None),
) -> int | None:
    try:
        return await get_current_user_id(authorization=authorization)
    except UnauthorizedError:
        return None


CurrentUserId = Annotated[int, Depends(get_current_user_id)]
OptionalUserId = Annotated[int | None, Depends(get_current_user_id_optional)]


async def get_current_admin(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> int:
    """Require the current user to be an admin; returns their user id.

    Raises 401 when unauthenticated, 403 when authenticated but not admin.
    """
    user = await session.get(User, user_id)
    if user is None:
        raise UnauthorizedError("invalid credentials")
    if not user.is_admin:
        raise ForbiddenError("admin privileges required")
    return user_id


AdminUserId = Annotated[int, Depends(get_current_admin)]

# ----------------------------------------------------------------------
# Rate limiting (slowapi)
# ----------------------------------------------------------------------
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

_limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


def get_limiter() -> Limiter:
    return _limiter


RateLimiter = Annotated[Limiter, Depends(get_limiter)]


def rate_exceeded_handler(request, exc: RateLimitExceeded):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=429,
        content={"error": {"code": "rate_limit_exceeded", "detail": str(exc.detail)}},
    )


# Re-exported so other modules can do `from app.deps import DBSession`.
__all__ = [
    "DBSession",
    "RedisClient",
    "get_current_user_id",
    "get_current_user_id_optional",
    "CurrentUserId",
    "OptionalUserId",
    "get_current_admin",
    "AdminUserId",
    "get_limiter",
    "RateLimiter",
    "rate_exceeded_handler",
]
