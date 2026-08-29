"""HTTP-level tests for the submissions router.

Uses an in-memory `JudgeClient` mock by monkeypatching `app.rq_app.enqueue_judge_submission`
and replacing the judge's behaviour via `tests/conftest.py`.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, username: str) -> str:
    r = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "longenough1",
        },
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/auth/login",
        json={"username_or_email": username, "password": "longenough1"},
    )
    assert r2.status_code == 200
    return r2.json()["access_token"]


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    token = await _register_and_login(client, "subuser")
    return {"Authorization": f"Bearer {token}"}


async def _create_problem(client: AsyncClient, slug: str = "two-sum") -> int:
    # Problem creation requires admin — register + promote a one-off admin.
    await client.post(
        "/api/auth/register",
        json={"username": "pbadmin", "email": "pbadmin@example.com", "password": "longenough1"},
    )
    from app.db import get_session_factory
    from app.modules.users.service import UserService

    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select

        from app.modules.users.models import User

        admin = (
            await session.execute(select(User).where(User.username == "pbadmin"))
        ).scalar_one()
        await UserService(session).set_admin(admin.id, is_admin=True)

    r_login = await client.post(
        "/api/auth/login",
        json={"username_or_email": "pbadmin", "password": "longenough1"},
    )
    admin_token = r_login.json()["access_token"]

    r = await client.post(
        "/api/problems",
        json={
            "slug": slug,
            "title": "Two Sum",
            "statement_md": "# desc",
            "difficulty": "easy",
            "tags": ["array"],
            "boilerplate_code": {"python": "def f(): pass"},
            "test_cases": [
                {"input": "[[2,7,11,15], 9]", "expected_output": "[0,1]", "is_sample": True}
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_submit_requires_auth(client: AsyncClient) -> None:
    r = await client.post(
        "/api/submissions",
        json={"problem_id": 1, "language": "python3", "code": "x"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_submit_returns_pending_submission(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    # Patch enqueue to a no-op so this test doesn't need Redis.
    monkeypatch.setattr(
        "app.rq_app.enqueue_judge_submission",
        lambda _id: None,
    )
    problem_id = await _create_problem(client)

    r = await client.post(
        "/api/submissions",
        json={
            "problem_id": problem_id,
            "language": "python3",
            "code": "def f(): return 0",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["problem_id"] == problem_id


@pytest.mark.asyncio
async def test_get_submission_returns_detail(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.rq_app.enqueue_judge_submission",
        lambda _id: None,
    )
    problem_id = await _create_problem(client, slug="valid-parentheses")

    r = await client.post(
        "/api/submissions",
        json={
            "problem_id": problem_id,
            "language": "python3",
            "code": "def f(): return True",
        },
        headers=auth_headers,
    )
    submission_id = r.json()["id"]

    r2 = await client.get(f"/api/submissions/{submission_id}", headers=auth_headers)
    assert r2.status_code == 200
    body = r2.json()
    assert body["id"] == submission_id
    assert "results" in body


@pytest.mark.asyncio
async def test_list_my_submissions(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.rq_app.enqueue_judge_submission",
        lambda _id: None,
    )
    problem_id = await _create_problem(client, slug="reverse-linked-list")

    for _ in range(3):
        await client.post(
            "/api/submissions",
            json={
                "problem_id": problem_id,
                "language": "python3",
                "code": "def f(): return None",
            },
            headers=auth_headers,
        )

    r = await client.get("/api/submissions?size=10", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3


@pytest.mark.asyncio
async def test_run_endpoint_exists(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.rq_app.enqueue_judge_submission",
        lambda _id: None,
    )
    problem_id = await _create_problem(client, slug="two-sum")
    r = await client.post(
        "/api/submissions/999/run",
        json={
            "problem_id": problem_id,
            "language": "python3",
            "code": "x",
        },
        headers=auth_headers,
    )
    # The /run endpoint creates a new submission; submission_id in URL is ignored for now.
    assert r.status_code == 201
