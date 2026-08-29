"""Redis pubsub publisher for live WebSocket events.

The judge task calls `publish_event()` whenever a submission changes state.
WebSocket clients subscribe to the corresponding Redis channel and receive
push events in real-time — no polling required.

Channels:
  submissions:{id}  →  submission status updates
  contest:{id}      →  leaderboard updates
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _channel(submission_id: int) -> str:
    return f"submissions:{submission_id}"


def _contest_channel(contest_id: int) -> str:
    return f"contest:{contest_id}"


def publish_event(channel: str, event: dict[str, Any]) -> None:
    """Publish a JSON event to a Redis channel (sync, fire-and-forget).

    Silently ignores Redis errors so that judge errors never cascade into
    the WebSocket delivery path.
    """
    try:
        import redis as redis_sync

        settings = get_settings()
        client = redis_sync.from_url(settings.effective_redis_url)
        try:
            client.publish(channel, json.dumps(event, default=_json_serial))
        finally:
            client.close()
    except Exception:  # noqa: BLE001 — best-effort delivery
        logger.debug("Redis publish failed for channel %s", channel)


def publish_submission_update(submission_id: int, event: dict[str, Any]) -> None:
    """Push a submission lifecycle event to its WebSocket listeners."""
    publish_event(_channel(submission_id), event)


def publish_contest_update(contest_id: int, event: dict[str, Any]) -> None:
    """Push a leaderboard update to all clients watching a contest."""
    publish_event(_contest_channel(contest_id), event)


def _json_serial(obj: Any) -> str | None:
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return None
