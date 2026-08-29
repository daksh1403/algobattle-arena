"""Security primitives: password hashing + JWT.

The hashing uses passlib's bcrypt handler (cost 12 by default — see config).
JWT uses python-jose with HS256 by default.  The token payload is a thin dict
containing `sub` (user id as a string), `exp`, and `iat`.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

# Lazy module-level context so the bcrypt backend is only initialised once.
_pwd_context: CryptContext | None = None


def _get_pwd_context() -> CryptContext:
    global _pwd_context
    if _pwd_context is None:
        rounds = get_settings().bcrypt_rounds
        _pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=rounds,
        )
    return _pwd_context


# --- Password helpers --------------------------------------------------------

def hash_password(plain: str) -> str:
    """Return a bcrypt hash for the plaintext password."""
    return _get_pwd_context().hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time-ish verification via passlib."""
    try:
        return _get_pwd_context().verify(plain, hashed)
    except ValueError:
        # Malformed hash, or bcrypt backend mismatch.
        return False


# --- JWT helpers -------------------------------------------------------------

def create_access_token(
    subject: str | int,
    *,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Sign an HS256 JWT for the given subject (typically the user id)."""
    settings = get_settings()
    now = datetime.now(tz=UTC)
    expire = now + timedelta(minutes=expires_minutes or settings.jwt_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode + verify a JWT.  Raises `jose.JWTError` on failure."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# --- Helpers for tests / callers ---------------------------------------------

def is_jwt_error(exc: Exception) -> bool:
    return isinstance(exc, JWTError)


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "is_jwt_error",
]
