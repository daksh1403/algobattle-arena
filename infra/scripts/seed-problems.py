#!/usr/bin/env python3
# ============================================================================
# seed-problems.py — populate the DB with sample problems
# ----------------------------------------------------------------------------
# Reads SAMPLE_PROBLEMS env (defaults to a curated set) and inserts them via
# the live API. Falls back to direct DB insert if the API is unavailable.
#
# Usage:
#   python seed-problems.py [--api-url http://localhost:8000]
# ============================================================================
import json
import os
import sys
import argparse
import time
from typing import List, Dict

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Curated sample problems (cover different difficulty / language combos)
# ---------------------------------------------------------------------------
SAMPLE_PROBLEMS: List[Dict] = [
    {
        "slug": "two-sum",
        "title": "Two Sum",
        "difficulty": "easy",
        "tags": ["arrays", "hashmap"],
        "description": (
            "Given an array of integers `nums` and an integer `target`, return "
            "indices of the two numbers such that they add up to `target`.\n\n"
            "You may assume that each input would have exactly one solution, "
            "and you may not use the same element twice."
        ),
        "time_limit_ms": 1000,
        "memory_limit_kb": 256000,
        "starter_code": {
            "python": (
                "class Solution:\n"
                "    def twoSum(self, nums: List[int], target: int) -> List[int]:\n"
                "        pass\n"
            ),
            "cpp": (
                "#include <vector>\n"
                "using namespace std;\n"
                "class Solution {\n"
                "public:\n"
                "    vector<int> twoSum(vector<int>& nums, int target) {\n"
                "        // your code\n"
                "    }\n"
                "};\n"
            ),
        },
        "tests": [
            {"input": "4 2 7 11 15 9\n", "expected": "0 1\n", "weight": 1},
            {"input": "3 3 2 4 6\n", "expected": "1 2\n", "weight": 1},
            {"input": "3 3 3 6\n", "expected": "0 1\n", "weight": 2},
        ],
    },
    {
        "slug": "fibonacci",
        "title": "Nth Fibonacci",
        "difficulty": "easy",
        "tags": ["math", "dp"],
        "description": (
            "Compute the Nth Fibonacci number (0-indexed). F(0)=0, F(1)=1.\n"
            "Modulo 10**9+7. Solve in O(log N) or O(N)."
        ),
        "time_limit_ms": 1000,
        "memory_limit_kb": 128000,
        "starter_code": {
            "python": (
                "MOD = 10**9 + 7\n"
                "def fib(n: int) -> int:\n"
                "    # your code\n"
                "    pass\n"
            ),
        },
        "tests": [
            {"input": "0\n", "expected": "0\n", "weight": 1},
            {"input": "1\n", "expected": "1\n", "weight": 1},
            {"input": "10\n", "expected": "55\n", "weight": 1},
            {"input": "100\n", "expected": "687995182\n", "weight": 3},
        ],
    },
    {
        "slug": "binary-search",
        "title": "Binary Search",
        "difficulty": "easy",
        "tags": ["binary-search"],
        "description": (
            "Given a sorted array `nums` and a `target`, return the index of "
            "`target` if present, else -1. Solve in O(log N)."
        ),
        "time_limit_ms": 500,
        "memory_limit_kb": 128000,
        "starter_code": {
            "python": (
                "from typing import List\n"
                "def search(nums: List[int], target: int) -> int:\n"
                "    # your code\n"
                "    pass\n"
            ),
        },
        "tests": [
            {"input": "5 -1 0 3 5 9 12 9\n", "expected": "4\n", "weight": 1},
            {"input": "5 -1 0 3 5 9 12 2\n", "expected": "-1\n", "weight": 1},
            {"input": "1 5 5\n", "expected": "0\n", "weight": 2},
        ],
    },
    {
        "slug": "merge-intervals",
        "title": "Merge Intervals",
        "difficulty": "medium",
        "tags": ["arrays", "sorting"],
        "description": (
            "Given a list of intervals, merge all overlapping intervals and "
            "return a list of non-overlapping intervals covering the same "
            "input."
        ),
        "time_limit_ms": 2000,
        "memory_limit_kb": 256000,
        "starter_code": {
            "python": (
                "from typing import List\n"
                "def merge(intervals: List[List[int]]) -> List[List[int]]:\n"
                "    # your code\n"
                "    pass\n"
            ),
        },
        "tests": [
            {"input": "2 1 3 2 6 8 10 15 18\n", "expected": "2 1 6 8 15 18\n", "weight": 1},
            {"input": "0\n", "expected": "\n", "weight": 2},
            {"input": "1 1 4 4 5\n", "expected": "1 1 5\n", "weight": 2},
        ],
    },
    {
        "slug": "longest-substring",
        "title": "Longest Substring Without Repeating Characters",
        "difficulty": "medium",
        "tags": ["strings", "sliding-window"],
        "description": (
            "Given a string `s`, find the length of the longest substring "
            "without repeating characters."
        ),
        "time_limit_ms": 1000,
        "memory_limit_kb": 256000,
        "starter_code": {
            "python": (
                "def lengthOfLongestSubstring(s: str) -> int:\n"
                "    # your code\n"
                "    pass\n"
            ),
        },
        "tests": [
            {"input": "abcabcbb\n", "expected": "3\n", "weight": 1},
            {"input": "bbbbb\n", "expected": "1\n", "weight": 1},
            {"input": "pwwkew\n", "expected": "3\n", "weight": 2},
            {"input": "\n", "expected": "0\n", "weight": 2},
        ],
    },
    {
        "slug": "reverse-linked-list",
        "title": "Reverse Linked List",
        "difficulty": "easy",
        "tags": ["linked-list"],
        "description": "Given the head of a singly linked list, reverse it and return the new head.",
        "time_limit_ms": 1000,
        "memory_limit_kb": 128000,
        "starter_code": {
            "python": (
                "class ListNode:\n"
                "    def __init__(self, val=0, next=None):\n"
                "        self.val = val\n"
                "        self.next = next\n"
                "def reverseList(head: ListNode) -> ListNode:\n"
                "    # your code\n"
                "    pass\n"
            ),
        },
        "tests": [
            {"input": "5 1 2 3 4 5\n", "expected": "5 5 4 3 2 1\n", "weight": 1},
            {"input": "0\n", "expected": "\n", "weight": 2},
        ],
    },
    {
        "slug": "valid-parentheses",
        "title": "Valid Parentheses",
        "difficulty": "easy",
        "tags": ["stack", "strings"],
        "description": "Given a string s containing just the characters '()[]{}', determine if the input string is valid.",
        "time_limit_ms": 500,
        "memory_limit_kb": 128000,
        "starter_code": {
            "python": (
                "def isValid(s: str) -> bool:\n"
                "    # your code\n"
                "    pass\n"
            ),
        },
        "tests": [
            {"input": "()[]\n", "expected": "true\n", "weight": 1},
            {"input": "(]\n", "expected": "false\n", "weight": 1},
            {"input": "([)]\n", "expected": "false\n", "weight": 2},
            {"input": "{[]}\n", "expected": "true\n", "weight": 2},
        ],
    },
    {
        "slug": "word-search",
        "title": "Word Search",
        "difficulty": "hard",
        "tags": ["backtracking", "matrix"],
        "description": (
            "Given an m x n grid of characters and a string `word`, return "
            "true if `word` exists in the grid. The word can be constructed "
            "from letters of sequentially adjacent cells (horizontally or "
            "vertically). Each cell may not be used more than once."
        ),
        "time_limit_ms": 5000,
        "memory_limit_kb": 256000,
        "starter_code": {
            "python": (
                "from typing import List\n"
                "def exist(board: List[List[str]], word: str) -> bool:\n"
                "    # your code\n"
                "    pass\n"
            ),
        },
        "tests": [
            {
                "input": "3 4 A B C E S F C S A D E E 3 ABCCED\n",
                "expected": "true\n",
                "weight": 1,
            },
            {
                "input": "3 4 A B C E S F C S A D E E 3 SEE\n",
                "expected": "true\n",
                "weight": 2,
            },
            {
                "input": "3 4 A B C E S F C S A D E E 3 ABCB\n",
                "expected": "false\n",
                "weight": 3,
            },
        ],
    },
]


def seed_via_api(api_url: str, problems: List[Dict]) -> bool:
    """POST each problem to the API. Returns True on success."""
    headers = {"Content-Type": "application/json"}
    # If you have admin auth, add it here
    api_token = os.environ.get("API_TOKEN")
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    success = 0
    with httpx.Client(timeout=15) as client:
        for p in problems:
            r = client.post(f"{api_url}/api/admin/problems", json=p, headers=headers)
            if r.status_code in (200, 201, 409):  # 409 = already exists, fine
                success += 1
                print(f"  ✓ {p['slug']}")
            else:
                print(f"  ✗ {p['slug']}: {r.status_code} {r.text}", file=sys.stderr)

    print(f"\nSeeded {success}/{len(problems)} problems via API.")
    return success == len(problems)


def seed_via_db(database_url: str, problems: List[Dict]) -> bool:
    """Direct DB insert. Used as a fallback when the API is unreachable."""
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not installed — skipping DB seed.", file=sys.stderr)
        return False

    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS problems (
            id           SERIAL PRIMARY KEY,
            slug         TEXT UNIQUE NOT NULL,
            title        TEXT NOT NULL,
            difficulty   TEXT NOT NULL,
            tags         TEXT[] DEFAULT '{}',
            description  TEXT NOT NULL,
            time_limit_ms INT DEFAULT 1000,
            memory_limit_kb INT DEFAULT 256000,
            starter_code JSONB DEFAULT '{}',
            tests        JSONB DEFAULT '[]',
            created_at   TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    success = 0
    for p in problems:
        try:
            cur.execute("""
                INSERT INTO problems (slug, title, difficulty, tags, description,
                                      time_limit_ms, memory_limit_kb,
                                      starter_code, tests)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                ON CONFLICT (slug) DO UPDATE
                  SET title = EXCLUDED.title,
                      tests = EXCLUDED.tests,
                      starter_code = EXCLUDED.starter_code
            """, (
                p["slug"], p["title"], p["difficulty"], p["tags"], p["description"],
                p["time_limit_ms"], p["memory_limit_kb"],
                json.dumps(p["starter_code"]), json.dumps(p["tests"]),
            ))
            success += 1
            print(f"  ✓ {p['slug']}")
        except Exception as e:
            print(f"  ✗ {p['slug']}: {e}", file=sys.stderr)

    cur.close()
    conn.close()
    print(f"\nSeeded {success}/{len(problems)} problems via DB.")
    return success == len(problems)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-url", default=os.environ.get("API_URL", "http://localhost:8000"))
    ap.add_argument("--database-url", default=os.environ.get("DATABASE_URL_SYNC"))
    ap.add_argument("--file", help="JSON file with problems (else uses built-in set)")
    args = ap.parse_args()

    problems = SAMPLE_PROBLEMS
    if args.file:
        with open(args.file) as f:
            problems = json.load(f)

    print(f"Seeding {len(problems)} problems...")

    # Try API first
    if seed_via_api(args.api_url, problems):
        return 0

    # Fallback to direct DB
    if args.database_url:
        if seed_via_db(args.database_url, problems):
            return 0

    print("\nNeither API nor DB worked. Make sure the stack is running.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())