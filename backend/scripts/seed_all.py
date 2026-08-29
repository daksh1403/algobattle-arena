#!/usr/bin/env python3
"""Bulk seeder: load all LeetCode problems from data/problems.json into the DB.

Usage:
    python scripts/seed_all.py [--dataset data/problems.json] [--admin-email admin@example.com]

This script:
1. Loads the problem dataset (4,033 problems)
2. Creates an admin user if needed
3. Seeds every problem (upsert — safe to re-run)
4. Seeds curated test cases for known problems
"""
from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/problems.json")
    ap.add_argument("--admin-email", default="admin@example.com")
    ap.add_argument("--admin-password", default="Admin1234!")
    args = ap.parse_args()

    # Load dataset
    path = Path(args.dataset)
    if not path.exists():
        print(f"ERROR: dataset not found at {path}")
        print(f"Run: python scripts/fetch_leetcode.py --output {path}")
        sys.exit(1)

    with open(path) as f:
        dataset = json.load(f)

    problems = dataset.get("problems", [])
    meta = dataset.get("meta", {})
    print(f"Loaded {len(problems)} problems. {meta}")

    # Import after path is verified
    import os
    os.environ.setdefault("APP_ENV", "development")

    # Import ALL models first — SQLAlchemy needs them registered before any
    # engine/session operations.  This mirrors what tests/conftest.py does.
    from app.modules.users.models import User  # noqa
    from app.modules.problems.models import Problem, TestCase  # noqa
    from app.modules.contests.models import Contest, ContestParticipant, ContestProblem  # noqa
    from app.modules.submissions.models import Submission, SubmissionResult  # noqa
    from app.db import init_engine, dispose_engine, get_session

    init_engine()  # must be called AFTER all models are imported

    # Create tables if they don't exist (uses Base.metadata).
    import asyncio
    import app.db as db_module

    async def _create_tables():
        async with db_module._engine.begin() as conn:
            await conn.run_sync(db_module.Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_create_tables())
    print("Tables created/verified.")
    from app.modules.users.service import UserService
    from app.modules.problems.service import ProblemService

    init_engine()

    async def _seed():
        from app.modules.problems.schemas import ProblemCreate, TestCaseCreate
        from app.modules.users.schemas import UserCreate

        async for session in get_session():
            # Create admin user
            try:
                user_svc = UserService(session)
                admin = await user_svc.create(
                        UserCreate(
                            username="admin",
                            email=args.admin_email,
                            password=args.admin_password,
                        )
                    )
                await user_svc.set_admin(admin.id, is_admin=True)
                print(f"Created admin: {args.admin_email}")
            except Exception as exc:
                if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
                    print(f"Admin user exists: {args.admin_email}")
                else:
                    print(f"Admin user error (ignoring): {exc}")

            # Seed problems
            prob_svc = ProblemService(session)
            seeded = 0
            skipped = 0
            for p in problems:
                slug = p.get("slug", "")
                if not slug:
                    skipped += 1
                    continue
                try:
                    test_cases = []
                    for tc in p.get("test_cases", []):
                        if isinstance(tc, dict) and tc.get("input"):
                            test_cases.append(TestCaseCreate(
                                input=tc["input"],
                                expected_output=tc.get("expected_output", ""),
                                is_sample=tc.get("is_sample", False),
                            ))
                    payload = ProblemCreate(
                        slug=slug,
                        title=p.get("title", slug),
                        statement_md=f"""# {p.get("title", slug)}

**Difficulty:** {p.get("difficulty", "medium").capitalize()}
**Acceptance Rate:** {p.get("ac_rate", "N/A")}%

## Description

Solve the problem described at [LeetCode](https://leetcode.com/problems/{slug}/).

## Constraints

- Problem ID: {p.get("frontend_id", "N/A")}
""",
                        difficulty=p.get("difficulty", "medium"),
                        tags=p.get("tags", []),
                        boilerplate_code={"python": "# TODO: solve " + slug + "\npass"},
                        test_cases=test_cases,
                    )
                    await prob_svc.create(payload=payload)
                    seeded += 1
                    if seeded % 100 == 0:
                        print(f"  Seeded {seeded}/{len(problems)}...")
                except Exception as exc:
                    if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
                        skipped += 1
                    else:
                        print(f"  ERROR {slug}: {exc}")

            print(f"Seeding complete: {seeded} seeded, {skipped} skipped (already exists)")
            await session.commit()
            return

    import asyncio
    try:
        asyncio.run(_seed())
    finally:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        loop.run_until_complete(dispose_engine())

if __name__ == "__main__":
    main()
