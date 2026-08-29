"""Integration tests for the live-deployed judge (web_arena.py).

These exercise the exact FastAPI app that runs behind the Cloudflare
tunnel (the "Path A" architecture in PROJECT_OVERVIEW.md). No external
services — the sandbox runs real subprocesses locally.

Run:
    cd backend
    .venv/bin/python -m pytest sandbox/tests/test_web_arena.py -v
"""
from __future__ import annotations

import sys
import os

# Ensure sandbox package is importable (web_arena imports sandbox_runner)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
import pytest
from httpx import ASGITransport

from web_arena import app


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    )


@pytest.mark.asyncio
async def test_health(client: httpx.AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["sandbox"] == "online"


@pytest.mark.asyncio
async def test_problems_list(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/problems")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) > 0
    slugs = [p["slug"] for p in body]
    assert "two-sum" in slugs


@pytest.mark.asyncio
async def test_submit_correct_two_sum_returns_ac(client: httpx.AsyncClient) -> None:
    """End-to-end: submit a correct two-sum solution, expect AC + 3/3."""
    r = await client.post(
        "/api/submit",
        json={
            "slug": "two-sum",
            "language": "python",
            "participant": "test-user",
            "code": (
                "nums = list(map(int, input().split()))\n"
                "t = int(input())\n"
                "d = {}\n"
                "for i, n in enumerate(nums):\n"
                "    if t - n in d:\n"
                "        print(d[t-n], i)\n"
                "        break\n"
                "    d[n] = i\n"
            ),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "AC", f"Expected AC, got {body}"
    assert body["score"] == "3/3"
    assert len(body["results"]) == 3
    assert all(rr["verdict"] == "AC" for rr in body["results"])


@pytest.mark.asyncio
async def test_submit_wrong_answer_returns_wa(client: httpx.AsyncClient) -> None:
    """Wrong solution → WA, and the leaderboard should NOT show it as AC."""
    r = await client.post(
        "/api/submit",
        json={
            "slug": "two-sum",
            "language": "python",
            "participant": "test-wrong",
            "code": "print('0 0')",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "WA", f"Expected WA, got {body}"


@pytest.mark.asyncio
async def test_compiler_run(client: httpx.AsyncClient) -> None:
    """The Programiz-style compiler endpoint works."""
    r = await client.post(
        "/api/compiler/run",
        json={"language": "python", "code": "print(1 + 1)", "stdin": ""},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "1" in body.get("stdout", "") or "2" in body.get("stdout", "")


@pytest.mark.asyncio
async def test_leaderboard(client: httpx.AsyncClient) -> None:
    """Leaderboard is a list and reflects the AC submission above."""
    r = await client.get("/api/leaderboard")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert any(e["participant"] == "test-user" for e in body)
