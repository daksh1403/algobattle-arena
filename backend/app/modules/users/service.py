"""User service — registration, login, lookups.

This is the only place that touches the User model's password_hash field;
all routers go through these methods.
"""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.users.models import User
from app.modules.users.schemas import LoginIn, UserCreate


class UserService:
    """Stateless business-logic façade for `User` operations.

    Instances are cheap: callers pass the request-scoped `AsyncSession`
    in the constructor.  The service holds no DB connection of its own.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- creation / registration --------------------------------------

    async def create(self, payload: UserCreate) -> User:
        """Create a new user.  Raises `ConflictError` on duplicate username/email."""
        existing = await self.session.execute(
            select(User).where(
                or_(User.username == payload.username, User.email == payload.email)
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("username or email already exists")

        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    # ---- authentication ----------------------------------------------

    async def authenticate(self, payload: LoginIn) -> tuple[User, str]:
        """Validate credentials and return `(user, access_token)`.

        Raises `UnauthorizedError` if the user does not exist OR the password
        is wrong — callers must not distinguish the two cases (no user enum).
        """
        user = await self._find_by_login(payload.username_or_email)
        if user is None or not verify_password(payload.password, user.password_hash):
            raise UnauthorizedError("invalid credentials")
        token = create_access_token(user.id)
        return user, token

    # ---- lookups ------------------------------------------------------

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def set_admin(self, user_id: int, is_admin: bool = True) -> User | None:
        """Promote/demote a user to/from admin.  Returns the user or None."""
        user = await self.session.get(User, user_id)
        if user is None:
            return None
        user.is_admin = is_admin
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def _find_by_login(self, username_or_email: str) -> User | None:
        stmt = select(User).where(
            or_(User.username == username_or_email, User.email == username_or_email)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


__all__ = ["UserService"]
