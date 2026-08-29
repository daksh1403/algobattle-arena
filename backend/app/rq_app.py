"""RQ (Redis Queue) factory.

RQ is intentionally simple: one queue, one synchronous worker process.
Because judge calls are I/O-heavy (network roundtrips to Judge0), we
keep workers small (default 2 — see `RQ_WORKER_COUNT`) and scale by
adding processes / pods.

In tests the queue is *not* started; we invoke the job function directly
instead of going through redis.
"""
from __future__ import annotations

import redis as redis_sync
import rq

from app.config import get_settings

_queue: rq.Queue | None = None


def get_queue() -> rq.Queue:
    """Return the singleton RQ queue, building it on first use."""
    global _queue
    if _queue is None:
        settings = get_settings()
        connection = redis_sync.from_url(settings.effective_redis_url)
        _queue = rq.Queue(name=settings.rq_queue_name, connection=connection)
    return _queue


def enqueue_judge_submission(submission_id: int) -> rq.job.Job:
    """Enqueue a judge job for the given submission id.

    Imported lazily so importing the module doesn't pull in RQ at app-startup
    in environments that don't use the queue (e.g. some test sessions).
    """
    from app.modules.submissions.tasks import judge_submission

    queue = get_queue()
    return queue.enqueue(
        judge_submission,
        submission_id,
        job_timeout="5m",
        result_ttl="1h",
        failure_ttl="6h",
    )


__all__ = ["get_queue", "enqueue_judge_submission"]
