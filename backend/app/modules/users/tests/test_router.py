"""HTTP-level tests for the users router (`/auth/register`, `/auth/login`).

These exercise the FastAPI app via `httpx.AsyncClient`, mocking out
external services via the `client` fixture in `tests/conftest.py`.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_creates_user_and_returns_201(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "longenough1",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"
    assert "password" not in body and "password_hash" not in body


@pytest.mark.asyncio
async def test_register_validation_error_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"username": "x", "email": "not-an-email", "password": "no"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_duplicate_returns_409(client: AsyncClient) -> None:
    payload = {
        "username": "dupuser",
        "email": "dup@example.com",
        "password": "longenough1",
    }
    first = await client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


@pytest.mark.asyncio
async def test_login_returns_token(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/register",
        json={"username": "logg", "email": "logg@example.com", "password": "longenough1"},
    )
    response = await client.post(
        "/api/auth/login",
        json={"username_or_email": "logg", "password": "longenough1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 20
    assert body["user"]["username"] == "logg"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/register",
        json={"username": "wp", "email": "wp@example.com", "password": "longenough1"},
    )
    response = await client.post(
        "/api/auth/login",
        json={"username_or_email": "wp", "password": "WRONGwrong1"},
    )
    assert response.status_code == 401
