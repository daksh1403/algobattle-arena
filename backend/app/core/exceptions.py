"""Custom exceptions + FastAPI handlers.

Domain-level modules raise these — FastAPI converts them to HTTP responses
with consistent JSON shape: `{"error": {"code": "...", "message": "..."}}`.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class for any application-originated error."""

    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, *, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class JudgeUnavailableError(AppError):
    status_code = 503
    code = "judge_unavailable"


def _payload(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """Install the JSON error handlers on a FastAPI app."""

    @app.exception_handler(AppError)
    async def _app_error_handler(_request: Request, exc: AppError) -> JSONResponse:  # type: ignore[unused-ignore]
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.code, exc.message, exc.details),
        )


__all__ = [
    "AppError",
    "NotFoundError",
    "ConflictError",
    "UnauthorizedError",
    "ForbiddenError",
    "ValidationError",
    "JudgeUnavailableError",
    "register_exception_handlers",
]
