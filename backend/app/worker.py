"""RQ worker entrypoint.

Run with:

    rq worker algobattle-judge --url $REDIS_URL

This file just exposes the task so RQ can find it via
`app.modules.submissions.tasks.judge_submission`.  We re-export here for
convenience.
"""
from app.modules.submissions.tasks import judge_submission

__all__ = ["judge_submission"]


if __name__ == "__main__":  # pragma: no cover
    import sys

    from rq import Worker

    from app.rq_app import get_queue

    queue = get_queue()
    sys.exit(Worker([queue]).work())
