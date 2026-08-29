"""Async client for the Judge0 REST API.

We don't import `httpx` at module-load time when Judge0 is unreachable —
the `JudgeClient` class takes a configured `httpx.AsyncClient` so tests can
inject a `respx` mock (or any object implementing the same surface).
"""
from __future__ import annotations

import asyncio
import base64
from collections.abc import Iterable
from typing import Any

import httpx

from app.config import get_settings

# Judge0 status id → SubmissionStatus mapping
# See https://judge0.com/#statuses-and-languages-status-ids
_JUDGE0_STATUS_MAP: dict[int, str] = {
    1: "pending",
    2: "running",
    3: "accepted",
    4: "wrong_answer",
    5: "tle",
    6: "compile_error",
    7: "runtime_error",  # SIGSEGV
    8: "runtime_error",  # SIGXFSZ
    9: "runtime_error",  # SIGFPE
    10: "runtime_error",  # SIGABRT
    11: "runtime_error",  # NZEC
    12: "runtime_error",  # Other
    13: "internal_error",
    14: "runtime_error",  # Exec format error
}


def _b64(text: str | None) -> str | None:
    if text is None:
        return None
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _decode_b64(value: str | None) -> str:
    if value is None:
        return ""
    try:
        return base64.b64decode(value).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - defensive
        return value


class JudgeResult:
    """One Judge0 verdict, normalised."""

    __slots__ = (
        "token",
        "status",
        "stdout",
        "stderr",
        "compile_output",
        "runtime_ms",
        "memory_kb",
        "raw",
    )

    def __init__(
        self,
        token: str,
        status: str,
        stdout: str = "",
        stderr: str = "",
        compile_output: str = "",
        runtime_ms: int | None = None,
        memory_kb: int | None = None,
        raw: dict | None = None,
    ) -> None:
        self.token = token
        self.status = status
        self.stdout = stdout
        self.stderr = stderr
        self.compile_output = compile_output
        self.runtime_ms = runtime_ms
        self.memory_kb = memory_kb
        self.raw = raw or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "status": self.status,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "compile_output": self.compile_output,
            "runtime_ms": self.runtime_ms,
            "memory_kb": self.memory_kb,
        }


class JudgeClient:
    """Async Judge0 client.

    Two key methods:
        * `submit_batch(payloads)` — POST `/submissions/batch?base64_encoded=true`
        * `poll_batch(tokens)`     — GET  `/submissions/batch?tokens=...&base64_encoded=true`

    Polling blocks until *all* tokens reach a terminal status (or the
    overall timeout is hit, after which the surviving entries are returned
    with status='running').
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        *,
        base_url: str | None = None,
        poll_interval: float | None = None,
        timeout: float | None = None,
        auth_header: dict[str, str] | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.judge0_url).rstrip("/")
        self.poll_interval = poll_interval or settings.judge0_poll_interval_seconds
        self.timeout = float(timeout or settings.judge0_timeout_seconds)
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=self.base_url,
            headers=auth_header or settings.judge0_auth_header or {},
            timeout=httpx.Timeout(30.0),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # ---- public API ---------------------------------------------------

    async def submit_batch(self, payloads: Iterable[dict[str, Any]]) -> list[str]:
        """Submit a batch of payloads; return Judge0 tokens. Retries on 5xx."""
        body = {"submissions": list(payloads)}
        max_retries, delay = 3, 1.0
        for attempt in range(max_retries):
            try:
                response = await self._client.post(
                    "/submissions/batch",
                    params={"base64_encoded": "true", "wait": "false"},
                    json=body,
                )
                if response.status_code >= 500 and attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                response.raise_for_status()
                data = response.json()
                return [item["token"] for item in data]
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    # Judge0 is overloaded — back off longer.
                    await asyncio.sleep(delay * 8)
                    delay *= 2
                    if attempt < max_retries - 1:
                        continue
                raise
            except (httpx.RequestError, OSError) as exc:
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise

    async def poll_batch(self, tokens: list[str]) -> list[JudgeResult]:
        """Poll tokens until terminal.  Returns one JudgeResult per token. Retries on 5xx."""
        if not tokens:
            return []

        # Judge0 supports up to ~20 tokens per batch poll — keep it small.
        BATCH = 20
        results: dict[str, JudgeResult] = {}
        deadline = asyncio.get_event_loop().time() + self.timeout

        pending = list(tokens)
        while pending:
            if asyncio.get_event_loop().time() > deadline:
                # Timeout — emit whatever we have, mark rest as running.
                for tok in pending:
                    results.setdefault(
                        tok, JudgeResult(token=tok, status="running")
                    )
                break

            for chunk in _chunked(pending, BATCH):
                tokens_param = ",".join(chunk)
                max_retries, delay = 3, 1.0
                for attempt in range(max_retries):
                    try:
                        resp = await self._client.get(
                            "/submissions/batch",
                            params={
                                "tokens": tokens_param,
                                "base64_encoded": "true",
                            },
                        )
                        if resp.status_code >= 500 and attempt < max_retries - 1:
                            await asyncio.sleep(delay)
                            delay *= 2
                            continue
                        resp.raise_for_status()
                        break
                    except (httpx.HTTPStatusError, httpx.RequestError, OSError) as exc:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(delay)
                            delay *= 2
                            continue
                        raise
                else:
                    continue  # no more retries

                data = resp.json()
                # Judge0 returns {"submissions": [...]}; older versions used
                # a flat dict — handle both.
                items = data.get("submissions", data) if isinstance(data, dict) else data
                if isinstance(items, dict):
                    items = list(items.values())

                for item in items:
                    tok = item.get("token")
                    status_id = item.get("status", {}).get("id", 1)
                    status_name = _JUDGE0_STATUS_MAP.get(status_id, "running")
                    res = JudgeResult(
                        token=tok,
                        status=status_name,
                        stdout=_decode_b64(item.get("stdout")),
                        stderr=_decode_b64(item.get("stderr") or item.get("message")),
                        compile_output=_decode_b64(item.get("compile_output")),
                        runtime_ms=_to_int(item.get("time")),
                        memory_kb=_to_int(item.get("memory")),
                        raw=item,
                    )
                    results[tok] = res
                    if status_id >= 3:  # terminal
                        pass

            # Recompute still-pending: tokens whose latest status is not terminal
            pending = [
                tok
                for tok in pending
                if results.get(tok) is None or results[tok].status in ("pending", "running")
            ]
            if pending:
                await asyncio.sleep(self.poll_interval)

        # Preserve input ordering
        return [results[t] for t in tokens]

    # ---- helpers used by tasks.py -------------------------------------

    @staticmethod
    def make_payload(
        *,
        source_code: str,
        language_id: int,
        stdin: str | None = None,
        expected_output: str | None = None,
        cpu_time_limit: float | None = None,
        memory_limit: int | None = None,
    ) -> dict[str, Any]:
        """Build a single submission payload with base64-encoded fields."""
        return {
            "source_code": _b64(source_code),
            "language_id": language_id,
            "stdin": _b64(stdin) if stdin is not None else None,
            "expected_output": _b64(expected_output) if expected_output is not None else None,
            "cpu_time_limit": cpu_time_limit,
            "memory_limit": memory_limit,
        }


# --- module helpers ---------------------------------------------------------


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        # Judge0 returns `time` as a float string ("0.123" seconds) and
        # `memory` as integer KB — both are already in the right units.
        if isinstance(value, str):
            return int(round(float(value) * 1000))
        return int(value)
    except (TypeError, ValueError):
        return None


def _chunked(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


__all__ = [
    "JudgeClient",
    "JudgeResult",
    "JUDGE0_STATUS_MAP",
]


# Public alias so `from ...judge_client import JUDGE0_STATUS_MAP` works.
JUDGE0_STATUS_MAP = _JUDGE0_STATUS_MAP
