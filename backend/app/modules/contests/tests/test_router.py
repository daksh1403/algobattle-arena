"""HTTP-level tests for the contests router."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


def _running_window() -> dict:
    now = datetime.now(tz=UTC)
    return {
        "start_at": (now - timedelta(minutes=1)).isoformat(),
        "end_at": (now + timedelta(hours=1)).isoformat(),
    }


async def _register(client: AsyncClient, username: str) -> dict:
    r = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "longenough1",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _login(client: AsyncClient, username: str) -> str:
    # Register first (idempotent per test — unique username), then login.
    await _register(client, username)
    r = await client.post(
        "/api/auth/login",
        json={"username_or_email": username, "password": "longenough1"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


async def _make_admin(client: AsyncClient, username: str) -> str:
    """Register + promote a user to admin; returns their JWT."""
    token = await _login(client, username)
    from sqlalchemy import select

    from app.db import get_session_factory
    from app.modules.users.models import User
    from app.modules.users.service import UserService

    factory = get_session_factory()
    async with factory() as session:
        admin = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one()
        await UserService(session).set_admin(admin.id, is_admin=True)
    return token


@pytest.mark.asyncio
async def test_create_and_get_contest(client: AsyncClient) -> None:
    token = await _make_admin(client, "contestadmin")
    r = await client.post(
        "/api/contests",
        json={"name": "Test Contest", **_running_window()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    body = r.json()
    contest_id = body["id"]

    r2 = await client.get(f"/api/contests/{contest_id}")
    assert r2.status_code == 200
    assert r2.json()["name"] == "Test Contest"


@pytest.mark.asyncio
async def test_create_contest_requires_admin(client: AsyncClient) -> None:
    token = await _login(client, "notadmin")
    r = await client.post(
        "/api/contests",
        json={"name": "Nope", **_running_window()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_join_requires_auth(client: AsyncClient) -> None:
    token = await _make_admin(client, "authadmin")
    r = await client.post(
        "/api/contests",
        json={"name": "Auth Needed", **_running_window()},
        headers={"Authorization": f"Bearer {token}"},
    )
    contest_id = r.json()["id"]
    r2 = await client.post(f"/api/contests/{contest_id}/join")
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_join_creates_participant_and_leaderboard_entry(client: AsyncClient) -> None:
    token = await _make_admin(client, "joineruser")
    r = await client.post(
        "/api/contests",
        json={"name": "Joinable", **_running_window()},
        headers={"Authorization": f"Bearer {token}"},
    )
    contest_id = r.json()["id"]

    r2 = await client.post(
        f"/api/contests/{contest_id}/join",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 201
    body = r2.json()
    assert body["total_points"] == 0


@pytest.mark.asyncio
async def test_leaderboard_endpoint(client: AsyncClient) -> None:
    token = await _make_admin(client, "lbuser")
    r = await client.post(
        "/api/contests",
        json={"name": "LB Contest", **_running_window()},
        headers={"Authorization": f"Bearer {token}"},
    )
    contest_id = r.json()["id"]
    await client.post(
        f"/api/contests/{contest_id}/join",
        headers={"Authorization": f"Bearer {token}"},
    )

    r2 = await client.get(f"/api/contests/{contest_id}/leaderboard")
    assert r2.status_code == 200
    body = r2.json()
    assert body["contest_id"] == contest_id
    assert "entries" in body


@pytest.mark.asyncio
async def test_participants_endpoint(client: AsyncClient) -> None:
    token = await _make_admin(client, "plist")
    r = await client.post(
        "/api/contests",
        json={"name": "Plist", **_running_window()},
        headers={"Authorization": f"Bearer {token}"},
    )
    contest_id = r.json()["id"]
    await client.post(
        f"/api/contests/{contest_id}/join",
        headers={"Authorization": f"Bearer {token}"},
    )

    r2 = await client.get(f"/api/contests/{contest_id}/participants")
    assert r2.status_code == 200
    assert isinstance(r2.json(), list)
    assert r2.json()[0]["user_id"] > 0
