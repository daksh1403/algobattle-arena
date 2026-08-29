"""Seed problems — three EASY + one MEDIUM, LeetCode-style.

Use directly with:

    python -m app.modules.problems.data.seed

The script is idempotent: problems are inserted only if their slug is not
already present.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db import get_session_factory, init_engine
from app.modules.problems.models import Difficulty, Problem
from app.modules.problems.schemas import ProblemCreate, TestCaseCreate


def _two_sum() -> ProblemCreate:
    return ProblemCreate(
        slug="two-sum",
        title="Two Sum",
        statement_md=(
            "Given an array of integers `nums` and an integer `target`, "
            "return indices of the two numbers such that they add up to "
            "`target`.\n\n"
            "You may assume that each input has **exactly one** solution, "
            "and you may not use the same element twice.\n\n"
            "Return the answer as a list of two integers `[i, j]`."
        ),
        difficulty=Difficulty.EASY,
        tags=["array", "hash-table"],
        time_limit_ms=2000,
        memory_limit_kb=262144,
        function_signature="def two_sum(nums: list[int], target: int) -> list[int]:",
        boilerplate_code={
            "python": "def two_sum(nums, target):\n    # your code here\n    return []\n",
            "javascript": "function twoSum(nums, target) {\n  // your code here\n  return [];\n}\n",
        },
        test_cases=[
            TestCaseCreate(
                input="[[2,7,11,15], 9]",
                expected_output="[0,1]",
                is_sample=True,
                is_public=True,
            ),
            TestCaseCreate(
                input="[[3,2,4], 6]",
                expected_output="[1,2]",
                is_sample=False,
                is_public=True,
            ),
            TestCaseCreate(
                input="[[3,3], 6]",
                expected_output="[0,1]",
                is_sample=True,
                is_public=True,
            ),
        ],
    )


def _valid_parentheses() -> ProblemCreate:
    return ProblemCreate(
        slug="valid-parentheses",
        title="Valid Parentheses",
        statement_md=(
            "Given a string `s` containing just the characters `()[]{}`, "
            "determine if the input string is valid.\n\n"
            "An input is valid if open brackets are closed by the same "
            "type of bracket and in the correct order."
        ),
        difficulty=Difficulty.EASY,
        tags=["stack", "string"],
        function_signature="def is_valid(s: str) -> bool:",
        boilerplate_code={
            "python": "def is_valid(s):\n    return False\n",
            "javascript": "function isValid(s) {\n  return false;\n}\n",
        },
        test_cases=[
            TestCaseCreate(input='["()"]', expected_output="true", is_sample=True),
            TestCaseCreate(input='["()[]{}"]', expected_output="true", is_sample=True),
            TestCaseCreate(input='["(]"]', expected_output="false", is_sample=False),
            TestCaseCreate(input='["{[()]}"]', expected_output="true", is_sample=False),
        ],
    )


def _reverse_linked_list() -> ProblemCreate:
    return ProblemCreate(
        slug="reverse-linked-list",
        title="Reverse Linked List",
        statement_md=(
            "Given the `head` of a singly linked list, reverse the list "
            "and return the reversed list.\n\n"
            "The input is a JSON array representing the list, e.g. "
            "`[1,2,3,4,5]` for `1 -> 2 -> 3 -> 4 -> 5`."
        ),
        difficulty=Difficulty.EASY,
        tags=["linked-list"],
        function_signature="def reverse_list(head: list[int]) -> list[int]:",
        boilerplate_code={"python": "def reverse_list(head):\n    return head[::-1]\n"},
        test_cases=[
            TestCaseCreate(input="[[1,2,3,4,5]]", expected_output="[5,4,3,2,1]", is_sample=True),
            TestCaseCreate(input="[[1,2]]", expected_output="[2,1]", is_sample=True),
            TestCaseCreate(input="[[]]", expected_output="[]", is_sample=False),
        ],
    )


def _longest_substring() -> ProblemCreate:
    return ProblemCreate(
        slug="longest-substring-without-repeating-characters",
        title="Longest Substring Without Repeating Characters",
        statement_md=(
            "Given a string `s`, find the length of the longest substring "
            "without repeating characters.\n\n"
            "Input is a JSON string, e.g. `\"abcabcbb\"`.  Output the "
            "length as a JSON integer."
        ),
        difficulty=Difficulty.MEDIUM,
        tags=["string", "sliding-window", "hash-table"],
        time_limit_ms=2000,
        function_signature="def length_of_longest_substring(s: str) -> int:",
        boilerplate_code={
            "python": "def length_of_longest_substring(s):\n    return 0\n",
        },
        test_cases=[
            TestCaseCreate(input='["abcabcbb"]', expected_output="3", is_sample=True),
            TestCaseCreate(input='["bbbbb"]', expected_output="1", is_sample=True),
            TestCaseCreate(input='["pwwkew"]', expected_output="3", is_sample=False),
            TestCaseCreate(input='[""]', expected_output="0", is_sample=False),
            TestCaseCreate(input='[" "]', expected_output="1", is_sample=False),
        ],
    )


PROBLEMS: list[ProblemCreate] = [
    _two_sum(),
    _valid_parentheses(),
    _reverse_linked_list(),
    _longest_substring(),
]


async def seed_async() -> list[Problem]:
    """Insert any missing problems; returns the full list (pre + new)."""
    from app.modules.problems.service import ProblemService  # local import

    factory = get_session_factory()
    async with factory() as session:
        service = ProblemService(session)
        for p in PROBLEMS:
            existing = (
                await session.execute(select(Problem).where(Problem.slug == p.slug))
            ).scalar_one_or_none()
            if existing is not None:
                continue
            await service.create(p)
        # Return all
        result = await session.execute(select(Problem).order_by(Problem.id))
        return list(result.scalars().all())


def main() -> None:  # pragma: no cover - entrypoint only
    init_engine()
    inserted = asyncio.run(seed_async())
    print(f"Seeded {len(inserted)} problems:")
    for p in inserted:
        tc_count = len(getattr(p, "test_cases", []) or [])
        print(f"  - {p.slug} ({p.difficulty.value}) — {tc_count} test cases")


if __name__ == "__main__":  # pragma: no cover
    main()


__all__ = ["seed_async", "PROBLEMS"]
