"""HTTP-level tests for the problems router."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _create_problem(client: AsyncClient, admin_token: str, **overrides) -> dict:
    body = {
        "slug": "two-sum",
        "title": "Two Sum",
        "statement_md": "...",
        "difficulty": "easy",
        "tags": ["array"],
        "time_limit_ms": 2000,
        "memory_limit_kb": 262144,
        "boilerplate_code": {"python": "def two_sum(nums, target): return []"},
        "function_signature": "def two_sum(nums, target):",
        "test_cases": [
            {"input": "[[2,7,11,15], 9]", "expected_output": "[0,1]", "is_sample": True}
        ],
    }
    body.update(overrides)
    r = await client.post(
        "/api/problems", json=body, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_create_requires_admin(client: AsyncClient, admin_token: str) -> None:
    """A non-admin user must NOT be able to create problems."""
    await client.post(
        "/api/auth/register",
        json={
            "username": "normaluser",
            "email": "normal@example.com",
            "password": "longenough1",
        },
    )
    r_login = await client.post(
        "/api/auth/login",
        json={"username_or_email": "normaluser", "password": "longenough1"},
    )
    token = r_login.json()["access_token"]
    r = await client.post(
        "/api/problems",
        json={
            "slug": "hax",
            "title": "Hax",
            "statement_md": "...",
            "difficulty": "easy",
            "tags": [],
            "boilerplate_code": {},
            "test_cases": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_list_problems_empty(client: AsyncClient) -> None:
    r = await client.get("/api/problems")
    assert r.status_code == 200
    body = r.json()
    assert body == {"items": [], "total": 0, "page": 1, "size": 20}


@pytest.mark.asyncio
async def test_create_then_get_by_slug(client: AsyncClient, admin_token: str) -> None:
    created = await _create_problem(client, admin_token)
    assert created["slug"] == "two-sum"

    r = await client.get("/api/problems/two-sum")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Two Sum"
    assert "id" in body


@pytest.mark.asyncio
async def test_list_problems_returns_summary(client: AsyncClient, admin_token: str) -> None:
    await _create_problem(client, admin_token)
    r = await client.get("/api/problems")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["slug"] == "two-sum"
    # Summary fields only
    for forbidden in ("statement_md", "boilerplate_code"):
        assert forbidden not in items[0]


@pytest.mark.asyncio
async def test_get_unknown_slug_returns_404(client: AsyncClient) -> None:
    r = await client.get("/api/problems/no-such-problem")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_get_sample_testcases(client: AsyncClient, admin_token: str) -> None:
    await _create_problem(client, admin_token)
    r = await client.get("/api/problems/two-sum/testcases")
    assert r.status_code == 200
    cases = r.json()
    assert len(cases) >= 1
    assert cases[0]["is_sample"] is True


@pytest.mark.asyncio
async def test_create_duplicate_slug_returns_409(client: AsyncClient, admin_token: str) -> None:
    await _create_problem(client, admin_token)
    r = await client.post(
        "/api/problems",
        json={
            "slug": "two-sum",
            "title": "Two Sum Again",
            "statement_md": "...",
            "difficulty": "easy",
            "tags": [],
            "boilerplate_code": {},
            "test_cases": [],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 409
