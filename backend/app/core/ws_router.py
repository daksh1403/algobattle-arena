"""WebSocket endpoints for live submission + leaderboard updates.

Clients connect to:
  /ws/submissions/{id}   → real-time status / result events
  /ws/contests/{id}      → real-time leaderboard events

Authentication: JWT passed as `?token=<jwt>` query parameter.
The connection is closed if the token is invalid or expired.
"""
from __future__ import annotations

import asyncio
import json
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.core.security import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter()


# ----------------------------------------------------------------------
# auth helper
# ----------------------------------------------------------------------


async def _authenticate(token: str | None) -> int | None:
    """Decode a JWT; return user_id or None if invalid."""
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        return int(sub)
    except (ValueError, TypeError):
        return None


# ----------------------------------------------------------------------
# submission live-update WebSocket
# ----------------------------------------------------------------------


@router.websocket("/ws/submissions/{submission_id}")
async def ws_submission_updates(
    websocket: WebSocket,
    submission_id: int,
    token: str | None = Query(default=None),
) -> None:
    """Stream submission status + result events as they happen.

    Events:
      {"type": "status",  "status": "RUNNING", "runtime_ms": null, ...}
      {"type": "result",  "status": "ACCEPTED", "score": 100, ...}
    """
    user_id = await _authenticate(token)
    if user_id is None:
        websocket.close(code=4001, reason="unauthenticated")
        return

    settings = get_settings()
    channel = f"submissions:{submission_id}"

    try:
        redis = aioredis.from_url(settings.effective_redis_url, decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        await websocket.accept()

        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg:
                    await websocket.send_text(msg["data"])
                # Also check if the client sent anything (ping/pong or close)
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_text(), timeout=0.1
                    )
                    if data == "ping":
                        await websocket.send_text("pong")
                except asyncio.TimeoutError:
                    pass
                except WebSocketDisconnect:
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            await redis.close()
    except Exception:  # noqa: BLE001
        logger.debug("WS submission %s ended", submission_id)


# ----------------------------------------------------------------------
# contest leaderboard WebSocket
# ----------------------------------------------------------------------


@router.websocket("/ws/contests/{contest_id}")
async def ws_contest_leaderboard(
    websocket: WebSocket,
    contest_id: int,
    token: str | None = Query(default=None),
) -> None:
    """Stream leaderboard entry updates for a contest.

    Events:
      {"type": "leaderboard", "entries": [{"user_id": 1, "points": 100, ...}]}
      {"type": "user_solved", "user_id": 1, "points": 100}
    """
    user_id = await _authenticate(token)
    if user_id is None:
        websocket.close(code=4001, reason="unauthenticated")
        return

    settings = get_settings()
    channel = f"contest:{contest_id}"

    try:
        redis = aioredis.from_url(settings.effective_redis_url, decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        await websocket.accept()

        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg:
                    await websocket.send_text(msg["data"])
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_text(), timeout=0.1
                    )
                    if data == "ping":
                        await websocket.send_text("pong")
                except asyncio.TimeoutError:
                    pass
                except WebSocketDisconnect:
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            await redis.close()
    except Exception:  # noqa: BLE001
        logger.debug("WS contest %s ended", contest_id)
