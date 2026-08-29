"""TDD tests for `app.modules.users.service.UserService`.

Run with:

    pytest app/modules/users/tests/test_service.py -v

These were written *before* the implementation; see the corresponding
`service.py` for the green-code that makes them pass.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import verify_password
from app.modules.users.schemas import LoginIn, UserCreate
from app.modules.users.service import UserService

# --- creation -------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_user_persists_to_db(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    payload = UserCreate(
        username="alice",
        email="alice@example.com",
        password="supersecure123",
    )

    user = await service.create(payload)

    assert user.id is not None
    assert user.username == "alice"
    assert user.email == "alice@example.com"
    # Password must NOT be stored in plaintext.
    assert user.password_hash != "supersecure123"
    assert verify_password("supersecure123", user.password_hash) is True


@pytest.mark.asyncio
async def test_create_user_duplicate_username_raises(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    payload = UserCreate(username="bob", email="bob@example.com", password="longenough1")
    await service.create(payload)

    with pytest.raises(ConflictError):
        await service.create(
            UserCreate(username="bob", email="another@example.com", password="longenough2")
        )


@pytest.mark.asyncio
async def test_create_user_duplicate_email_raises(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    await service.create(
        UserCreate(
            username="carol",
            email="dup@example.com",
            password="longenough1",
        )
    )

    with pytest.raises(ConflictError):
        await service.create(
            UserCreate(username="carol2", email="dup@example.com", password="longenough2")
        )


# --- authentication --------------------------------------------------------


@pytest.mark.asyncio
async def test_authenticate_with_correct_password_returns_token(
    db_session: AsyncSession,
) -> None:
    service = UserService(db_session)
    await service.create(
        UserCreate(username="dave", email="dave@example.com", password="longenough1")
    )

    user, token = await service.authenticate(
        LoginIn(username_or_email="dave", password="longenough1")
    )

    assert user.username == "dave"
    assert isinstance(token, str) and len(token) > 20  # JWT


@pytest.mark.asyncio
async def test_authenticate_accepts_email(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    await service.create(
        UserCreate(username="erin", email="erin@example.com", password="longenough1")
    )

    user, _token = await service.authenticate(
        LoginIn(username_or_email="erin@example.com", password="longenough1")
    )
    assert user.username == "erin"


@pytest.mark.asyncio
async def test_authenticate_wrong_password_raises(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    await service.create(
        UserCreate(username="frank", email="frank@example.com", password="longenough1")
    )
    with pytest.raises(UnauthorizedError):
        await service.authenticate(
            LoginIn(username_or_email="frank", password="WRONGwrong1")
        )


@pytest.mark.asyncio
async def test_authenticate_unknown_user_raises(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    with pytest.raises(UnauthorizedError):
        await service.authenticate(
            LoginIn(username_or_email="ghost", password="somethinglong")
        )


# --- schema validation ------------------------------------------------------


def test_user_create_rejects_short_password() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        UserCreate(username="abc", email="x@x.com", password="short")


def test_user_create_rejects_bad_username_chars() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        UserCreate(username="bad name!", email="x@x.com", password="longenough1")
