"""Users router — `/auth/register` and `/auth/login`."""
from __future__ import annotations

from fastapi import APIRouter, status

from app.deps import DBSession
from app.modules.users.schemas import LoginIn, TokenOut, UserCreate, UserOut
from app.modules.users.service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account",
)
async def register(payload: UserCreate, session: DBSession) -> UserOut:
    service = UserService(session)
    user = await service.create(payload)
    return UserOut.model_validate(user)


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Exchange credentials for a JWT",
)
async def login(payload: LoginIn, session: DBSession) -> TokenOut:
    service = UserService(session)
    user, token = await service.authenticate(payload)
    return TokenOut(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


__all__ = ["router"]
