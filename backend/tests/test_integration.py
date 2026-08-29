"""End-to-end integration test.

Flow:
    register → login → seed problem → submit → (mock judge) → poll →
    verify verdict + leaderboard.

We monkeypatch the RQ enqueue + the judge HTTP transport so the test
runs without external services.
"""
from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import AsyncClient

from app.modules.submissions.judge_client import JudgeClient


def _accepted_response() -> dict:
    return {
        "stdout": base64.b64encode(b"output").decode(),
        "stderr": None,
        "compile_output": None,
        "time": "0.123",
        "memory": 4096,
        "status": {"id": 3, "description": "Accepted"},
    }


class _FakeTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self._counter = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if not path.endswith("/submissions/batch"):
            return httpx.Response(404, json={"error": "not found"})

        if request.method == "POST":
            import json

            body = request.read()
            decoded = json.loads(body or b"{}")
            tokens = [f"tok{i}" for i, _ in enumerate(decoded.get("submissions", []))]
            # Judge0's POST /submissions/batch returns a flat array:
            # [{"token": "..."}, ...]
            return httpx.Response(
                200, json=[_accepted_response() | {"token": t} for t in tokens]
            )

        # GET poll
        tokens_param = request.url.params.get("tokens", "")
        token_list = [t for t in tokens_param.split(",") if t]
        payload = {
            "submissions": [
                _accepted_response() | {"token": t} for t in token_list
            ]
        }
        return httpx.Response(200, json=payload)


@pytest.mark.asyncio
async def test_full_submit_poll_result_flow(
    client: AsyncClient, monkeypatch, admin_token: str
) -> None:
    # 1. Register + login
    r = await client.post(
        "/api/auth/register",
        json={
            "username": "e2euser",
            "email": "e2e@example.com",
            "password": "longenough1",
        },
    )
    assert r.status_code == 201

    r2 = await client.post(
        "/api/auth/login",
        json={"username_or_email": "e2euser", "password": "longenough1"},
    )
    token = r2.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    admin_auth = {"Authorization": f"Bearer {admin_token}"}

    # 2. Create a problem (admin only)
    r3 = await client.post(
        "/api/problems",
        json={
            "slug": "two-sum",
            "title": "Two Sum",
            "statement_md": "# ts",
            "difficulty": "easy",
            "tags": ["array"],
            "boilerplate_code": {"python": "def two_sum(nums, target): return []"},
            "test_cases": [
                {"input": "[[2,7,11,15], 9]", "expected_output": "[0,1]", "is_sample": True},
                {"input": "[[3,3], 6]", "expected_output": "[0,1]", "is_public": True},
                {"input": "[[3,2,4], 6]", "expected_output": "[1,2]", "is_public": True},
            ],
        },
        headers=admin_auth,
    )
    assert r3.status_code == 201, r3.text

    # 3. Create a contest (admin only) + join
    now = datetime.now(tz=UTC)
    r4 = await client.post(
        "/api/contests",
        json={
            "name": "E2E Contest",
            "start_at": (now - timedelta(minutes=1)).isoformat(),
            "end_at": (now + timedelta(hours=1)).isoformat(),
            "problem_ids": [r3.json()["id"]],
        },
        headers=admin_auth,
    )
    assert r4.status_code == 201
    contest_id = r4.json()["id"]

    r5 = await client.post(f"/api/contests/{contest_id}/join", headers=auth)
    assert r5.status_code == 201

    # 4. Submit code
    transport = _FakeTransport()

    # Patch enqueue to run the task synchronously with our fake transport.
    async def _run_inline(submission_id: int) -> dict:
        # Replace JudgeClient's transport at runtime.
        import app.modules.submissions.tasks as tasks_mod

        real_init = JudgeClient.__init__

        def _init(self, *args, **kwargs):  # noqa: ANN001
            kwargs["http_client"] = httpx.AsyncClient(
                base_url="http://judge0.local", transport=transport
            )
            kwargs["poll_interval"] = 0.001
            real_init(self, *args, **kwargs)

        JudgeClient.__init__ = _init  # type: ignore[assignment]
        try:
            return await tasks_mod._judge_async(submission_id)
        finally:
            JudgeClient.__init__ = real_init  # type: ignore[assignment]

    monkeypatch.setattr(
        "app.rq_app.enqueue_judge_submission",
        _run_inline,
    )

    r6 = await client.post(
        "/api/submissions",
        json={
            "problem_id": r3.json()["id"],
            "language": "python3",
            "code": "def two_sum(nums, target): return []",
            "contest_id": contest_id,
        },
        headers=auth,
    )
    assert r6.status_code == 201, r6.text
    submission_id = r6.json()["id"]
    assert r6.json()["status"] == "pending"

    # 5. Poll the result
    r7 = await client.get(f"/api/submissions/{submission_id}", headers=auth)
    assert r7.status_code == 200
    body = r7.json()
    assert body["status"] == "accepted"
    assert body["score"] >= 100
    assert len(body["results"]) == 3  # 1 sample + 2 public

    # 6. Verify leaderboard
    r8 = await client.get(f"/api/contests/{contest_id}/leaderboard")
    assert r8.status_code == 200
    entries = r8.json()["entries"]
    assert len(entries) >= 1
    # The e2e user should be in the leaderboard with score >= 100.
    assert any(e["score"] >= 100 for e in entries)
