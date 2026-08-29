#!/usr/bin/env python3
"""
Comprehensive Judge0 test harness.
Tests all seeded problems with curated test cases, verifies:
  1. Correctness (AC/WA/RE/...)
  2. Determinism (same result on repeated runs)
  3. Disruption handling (infinite loops → TLE, OOM → MLE, etc.)
  4. Edge cases (empty input, large input, corner cases)

Usage:
  python scripts/test_judge_full.py --base http://localhost:2350
  python scripts/test_judge_full.py --base http://localhost:2350 --problems 1-100
  python scripts/test_judge_full.py --base http://localhost:2350 --disruption-only
  python scripts/test_judge_full.py --base http://localhost:2350 --determinism-only
"""
import argparse
import asyncio
import json
import random
import signal
import subprocess
import sys
import time
import traceback
import statistics
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

import httpx
import requests

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PROBLEMS_FILE = DATA_DIR / "problems.json"
TESTCASES_FILE = DATA_DIR / "testcases.json"

DEFAULT_JUDGE0 = "http://localhost:2350"
DEFAULT_BACKEND = "http://localhost:8000"

# Language IDs on Judge0
LANG_IDS = {
    "python3": 71,
    "python": 71,
    "cpp": 54,
    "c": 50,
    "java": 62,
    "javascript": 63,
    "go": 60,
    "rust": 73,
    "typescript": 74,
}


# ──────────────────────────────────────────────────────────────────────────────
# Data models
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class DisruptionScenario:
    name: str
    description: str
    code_template: str  # Python code with injected disruption
    expected_outcome: str  # TLE | MLE | RE | AC
    severity: Literal["critical", "high", "medium"] = "high"


@dataclass
class ProblemTestResult:
    slug: str
    title: str
    difficulty: str
    verdict: str
    runtime_ms: float
    memory_kb: float
    expected_verdict: str
    passed: bool
    error_msg: str = ""
    retries: int = 0
    deterministic: bool = True
    sample_count: int = 0
    failed_case: Optional[dict] = None


@dataclass
class DisruptionResult:
    scenario: str
    expected: str
    actual: str
    passed: bool
    execution_time_ms: float
    memory_kb: float
    error: str = ""


@dataclass
class DeterminismResult:
    slug: str
    runs: int
    verdict: str
    is_deterministic: bool
    runtimes_ms: list[float]
    memories_kb: list[float]


@dataclass
class AggregateReport:
    total: int
    correct: int
    incorrect: int
    error: int
    timeout: int
    accuracy_percent: float
    by_difficulty: dict
    disruption_results: list
    determinism_results: list
    execution_times_ms: list[float]
    memory_kb: list[float]
    issues: list[str]
    duration_seconds: float


# ──────────────────────────────────────────────────────────────────────────────
# Disruption Scenarios
# ──────────────────────────────────────────────────────────────────────────────

DISRUPTION_SCENARIOS: list[DisruptionScenario] = [
    # ── Infinite loops ────────────────────────────────────────────────────────
    DisruptionScenario(
        name="infinite_loop_while",
        description="Infinite while True loop",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    while True:
        pass
""",
        expected_outcome="TLE",
        severity="critical",
    ),
    DisruptionScenario(
        name="infinite_loop_for",
        description="Infinite for loop via counter overflow",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    for i in range(10**10):
        if i > 0:
            pass
    # Intentionally wrong: infinite via counter reset
    i = 0
    while True:
        i = (i + 1) % 10
        if i == 0:
            pass
""",
        expected_outcome="TLE",
        severity="critical",
    ),
    DisruptionScenario(
        name="infinite_recursion",
        description="Unbounded recursion causing stack overflow",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    def recurse():
        return recurse()
    return recurse()
""",
        expected_outcome="RE",  # Python catches this, but could TLE on other langs
        severity="high",
    ),
    DisruptionScenario(
        name="infinite_generator",
        description="Generator that never yields",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    while True:
        yield 1
""",
        expected_outcome="TLE",
        severity="medium",
    ),

    # ── Memory exhaustion ─────────────────────────────────────────────────────
    DisruptionScenario(
        name="memory_bomb_list",
        description="Unbounded list growth causing OOM",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    lst = []
    while True:
        lst.append([0] * 100000)
""",
        expected_outcome="MLE",
        severity="critical",
    ),
    DisruptionScenario(
        name="memory_bomb_dict",
        description="Unbounded dict growth causing OOM",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    d = {{}}
    i = 0
    while True:
        d[i] = list(range(10000))
        i += 1
""",
        expected_outcome="MLE",
        severity="high",
    ),
    DisruptionScenario(
        name="memory_bomb_string",
        description="String concatenation in loop causing OOM",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    s = ""
    while True:
        s += "x" * 100000
""",
        expected_outcome="MLE",
        severity="medium",
    ),

    # ── Process preemption ────────────────────────────────────────────────────
    DisruptionScenario(
        name="process_preemption_sleep",
        description="Long sleep simulating process preemption",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    import time
    time.sleep(30)
    return 0
""",
        expected_outcome="TLE",
        severity="medium",
    ),
    DisruptionScenario(
        name="process_preemption_io",
        description="Excessive I/O operations",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    with open("/tmp/test_io_{{pid}}.txt", "w") as f:
        for _ in range(10000000):
            f.write("x" * 1000)
    return 0
""",
        expected_outcome="TLE",
        severity="medium",
    ),

    # ── Runtime errors ────────────────────────────────────────────────────────
    DisruptionScenario(
        name="division_by_zero",
        description="Division by zero error",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    return 1 / 0
""",
        expected_outcome="RE",
        severity="high",
    ),
    DisruptionScenario(
        name="index_error",
        description="List index out of bounds",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    arr = [1, 2, 3]
    return arr[10]
""",
        expected_outcome="RE",
        severity="high",
    ),
    DisruptionScenario(
        name="null_pointer_python",
        description="Type error / None access (Python equivalent of null pointer)",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    x = None
    return x + 1
""",
        expected_outcome="RE",
        severity="high",
    ),
    DisruptionScenario(
        name="key_error",
        description="Dict key not found",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    d = {{}}
    return d["nonexistent"]
""",
        expected_outcome="RE",
        severity="medium",
    ),
    DisruptionScenario(
        name="stack_overflow_deep",
        description="Deep recursion exceeding stack limit",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    def f(n):
        return f(n + 1)
    return f(0)
""",
        expected_outcome="RE",
        severity="high",
    ),

    # ── Edge cases ────────────────────────────────────────────────────────────
    DisruptionScenario(
        name="empty_input",
        description="Empty input to problem",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    return 0
""",
        expected_outcome="WA",  # Should produce wrong output on empty input
        severity="medium",
    ),
    DisruptionScenario(
        name="max_output_size",
        description="Output exceeds limit",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    print("x" * 1000000)
    return 0
""",
        expected_outcome="OLE",  # Output limit exceeded
        severity="medium",
    ),
    DisruptionScenario(
        name="negative_runtime",
        description="Program exits with negative code",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    import sys
    sys.exit(-1)
""",
        expected_outcome="RE",
        severity="low",
    ),
    DisruptionScenario(
        name="timeout_with_partial_work",
        description="Partial computation before timeout",
        code_template="""{user_code}
{signature}():
{user_code_indented}
    result = 0
    for i in range(100000000):
        result += i
        if i == 50000000:
            break
    return result
""",
        expected_outcome="TLE",  # Breaks at 50M but still over limit
        severity="low",
    ),
]


# ──────────────────────────────────────────────────────────────────────────────
# Judge0 Client
# ──────────────────────────────────────────────────────────────────────────────

class Judge0Client:
    """Thin wrapper around Judge0 REST API with retry + determinism."""

    VERDICT_MAP = {
        "AC": "Accepted",
        "WA": "Wrong Answer",
        "TLE": "Time Limit Exceeded",
        "MLE": "Memory Limit Exceeded",
        "RE": "Runtime Error",
        "OLE": "Output Limit Exceeded",
        "CE": "Compile Error",
        "IE": "Internal Error",
        "QU": "Queued",
        "PD": "Processing",
        "RU": "Running",
    }

    def __init__(
        self,
        base_url: str = DEFAULT_JUDGE0,
        timeout: int = 60,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def _post(self, path: str, data: dict, retries: int = 0) -> dict:
        url = f"{self.base_url}{path}"
        backoff = min(2 ** retries, 8)
        time.sleep(backoff)
        try:
            r = requests.post(url, json=data, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            if retries < self.max_retries:
                return self._post(path, data, retries=retries + 1)
            raise RuntimeError(f"Judge0 POST failed after {self.max_retries} retries: {exc}")

    def _get(self, path: str, retries: int = 0) -> dict:
        url = f"{self.base_url}{path}"
        backoff = min(2 ** retries, 4)
        time.sleep(backoff)
        try:
            r = requests.get(url, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            if retries < self.max_retries:
                return self._get(path, retries=retries + 1)
            raise RuntimeError(f"Judge0 GET failed after {self.max_retries} retries: {exc}")

    def submit(
        self,
        source_code: str,
        language_id: int = 71,
        stdin: str = "",
        expected_stdout: str = "",
        cpu_time_limit: int = 5,
        memory_limit: int = 256 * 1024,
    ) -> dict:
        """Submit a single code run and return the result."""
        submission = {
            "language_id": language_id,
            "source_code": source_code,
            "stdin": stdin,
            "expected_stdout": expected_stdout,
            "cpu_time_limit": cpu_time_limit,
            "memory_limit": memory_limit,
            "number_of_runs": 1,
        }
        result = self._post("/submissions?base64_encoded=false&wait=true", submission)
        return result

    def submit_batch(
        self,
        runs: list[dict],
        language_id: int = 71,
        cpu_time_limit: int = 5,
        memory_limit: int = 256 * 1024,
    ) -> list[dict]:
        """
        Submit a batch of runs.
        Each run: {"stdin": str, "expected_stdout": str, "id": any}
        """
        submissions = [
            {
                "language_id": language_id,
                "source_code": runs[0]["source_code"],  # Same code for all
                "stdin": r["stdin"],
                "expected_stdout": r.get("expected_stdout", ""),
                "cpu_time_limit": cpu_time_limit,
                "memory_limit": memory_limit,
            }
            for r in runs
        ]
        batch = {"submissions": submissions}
        result = self._post("/submissions/batch?base64_encoded=false", batch)
        # Result is a list of tokens (Judge0 v1.13+)
        if isinstance(result, list):
            tokens = result
        elif isinstance(result, dict):
            tokens = result.get("submissions", result)
        else:
            tokens = []

        # Poll for results
        results = []
        for token in tokens:
            sub = self._get(f"/submissions/{token}?fields=status,stdout,stderr,time,memory,token")
            results.append(sub)
        return results

    def get_status(self, token: str) -> dict:
        return self._get(f"/submissions/{token}?fields=status,stdout,stderr,time,memory,token,status")

    def health_check(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/", timeout=5)
            return r.status_code == 200
        except Exception:
            return False


# ──────────────────────────────────────────────────────────────────────────────
# Backend API Client
# ──────────────────────────────────────────────────────────────────────────────

class AlgobattleAPI:
    def __init__(self, base_url: str = DEFAULT_BACKEND):
        self.base = base_url.rstrip("/")
        self.token: str | None = None
        self.user_id: str | None = None

    def register(self, username: str, password: str) -> dict:
        r = requests.post(
            f"{self.base}/users/register",
            json={"username": username, "email": f"{username}@test.com", "password": password},
        )
        r.raise_for_status()
        return r.json()

    def login(self, username: str, password: str) -> str:
        r = requests.post(
            f"{self.base}/users/login",
            json={"username": username, "password": password},
        )
        r.raise_for_status()
        self.token = r.json()["access_token"]
        return self.token

    def ensure_admin(self, username: str, password: str) -> str:
        """Register + login + promote to admin."""
        try:
            self.register(username, password)
        except Exception:
            pass
        self.login(username, password)
        # Promote via internal endpoint or DB
        r = requests.post(
            f"{self.base}/users/{self.user_id or username}/set-admin",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        return self.token

    def create_problem(self, problem: dict) -> dict:
        r = requests.post(
            f"{self.base}/problems",
            json=problem,
            headers={"Authorization": f"Bearer {self.token}"},
        )
        r.raise_for_status()
        return r.json()

    def create_contest(self, contest: dict) -> dict:
        r = requests.post(
            f"{self.base}/contests",
            json=contest,
            headers={"Authorization": f"Bearer {self.token}"},
        )
        r.raise_for_status()
        return r.json()

    def submit_solution(
        self,
        problem_id: int,
        code: str,
        language: str = "python3",
        mode: str = "submit",
    ) -> dict:
        r = requests.post(
            f"{self.base}/submissions",
            json={
                "problem_id": problem_id,
                "code": code,
                "language": language,
                "mode": mode,
            },
            headers={"Authorization": f"Bearer {self.token}"},
        )
        r.raise_for_status()
        return r.json()

    def get_submission(self, sub_id: int) -> dict:
        r = requests.get(
            f"{self.base}/submissions/{sub_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        r.raise_for_status()
        return r.json()

    def list_problems(self, page: int = 1, size: int = 100) -> dict:
        r = requests.get(f"{self.base}/problems?page={page}&size={size}")
        r.raise_for_status()
        return r.json()

    def health(self) -> dict:
        r = requests.get(f"{self.base}/health")
        r.raise_for_status()
        return r.json()


# ──────────────────────────────────────────────────────────────────────────────
# Test case registry (curated ground truth for key problems)
# ──────────────────────────────────────────────────────────────────────────────

def load_testcases() -> dict[str, list[dict]]:
    """Load curated test cases from testcases.json."""
    if not TESTCASES_FILE.exists():
        return {}
    with open(TESTCASES_FILE) as f:
        raw = json.load(f)
    if isinstance(raw, dict) and "testcases" in raw:
        raw = raw["testcases"]
    # Index by slug
    result = {}
    for tc in raw:
        slug = tc.get("slug", tc.get("problem_slug", ""))
        if slug:
            result.setdefault(slug, []).append(tc)
    return result


def get_testcases_for_problem(slug: str) -> list[dict]:
    """Get test cases for a specific problem slug."""
    testcases = load_testcases()
    return testcases.get(slug, [])


# ──────────────────────────────────────────────────────────────────────────────
# Disruption Testing
# ──────────────────────────────────────────────────────────────────────────────

def run_disruption_tests(
    client: Judge0Client,
    slug: str = "two-sum",
    signature: str = "solution",
    user_code: str = "",
) -> list[DisruptionResult]:
    """
    Run all disruption scenarios against a given problem template.
    The disruption code is injected into a minimal solution scaffold.
    """
    results = []

    # Build a minimal valid scaffold that has the right function signature
    # We test each disruption in isolation without the user code
    for scenario in DISRUPTION_SCENARIOS:
        code = scenario.code_template.format(
            user_code="",
            signature=signature,
            user_code_indented="",
        )

        try:
            start = time.time()
            result = client.submit(
                source_code=code,
                language_id=71,
                cpu_time_limit=10,
                memory_limit=512 * 1024,
            )
            elapsed_ms = (time.time() - start) * 1000

            status_id = result.get("status", {}).get("id") if isinstance(result.get("status"), dict) else result.get("status", 0)
            verdict = _map_judge0_status(status_id)
            memory_kb = float(result.get("memory", 0) or 0)

            passed = verdict == scenario.expected_outcome
            error = result.get("stderr", "")

            results.append(
                DisruptionResult(
                    scenario=scenario.name,
                    expected=scenario.expected_outcome,
                    actual=verdict,
                    passed=passed,
                    execution_time_ms=elapsed_ms,
                    memory_kb=memory_kb,
                    error=error[:200] if error else "",
                )
            )
        except Exception as exc:
            results.append(
                DisruptionResult(
                    scenario=scenario.name,
                    expected=scenario.expected_outcome,
                    actual="IE",
                    passed=False,
                    execution_time_ms=0,
                    memory_kb=0,
                    error=str(exc)[:200],
                )
            )

    return results


def run_determinism_test(
    client: Judge0Client,
    code: str,
    stdin: str,
    expected: str,
    runs: int = 5,
) -> DeterminismResult:
    """
    Submit the same code N times and verify it gets the same verdict each time.
    """
    runtimes = []
    memories = []
    verdicts = []

    for _ in range(runs):
        try:
            result = client.submit(
                source_code=code,
                language_id=71,
                stdin=stdin,
                expected_stdout=expected,
                cpu_time_limit=5,
            )
            status_id = result.get("status", {}).get("id") if isinstance(result.get("status"), dict) else result.get("status", 0)
            verdict = _map_judge0_status(status_id)
            runtime_ms = float(result.get("time", 0) or 0)
            memory_kb = float(result.get("memory", 0) or 0)
            verdicts.append(verdict)
            runtimes.append(runtime_ms)
            memories.append(memory_kb)
        except Exception:
            verdicts.append("IE")

    is_deterministic = len(set(verdicts)) == 1
    return DeterminismResult(
        slug="test",
        runs=runs,
        verdict=verdicts[0] if verdicts else "IE",
        is_deterministic=is_deterministic,
        runtimes_ms=runtimes,
        memories_kb=memories,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Judge0 status → verdict mapping
# ──────────────────────────────────────────────────────────────────────────────

def _map_judge0_status(status_id: int) -> str:
    """Map Judge0 status ID to our verdict string."""
    STATUS_MAP = {
        1: "QU", 2: "PD", 3: "RU", 4: "AC", 5: "WA",
        6: "TLE", 7: "MLE", 8: "RE", 9: "OLE", 10: "CE",
        11: "IE", 12: "CE",
        # Extended
        13: "QU", 14: "PD", 15: "RU",
    }
    return STATUS_MAP.get(status_id, "IE")


# ──────────────────────────────────────────────────────────────────────────────
# Main test runner
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Algobattle Judge0 comprehensive test harness")
    parser.add_argument("--judge0", default=DEFAULT_JUDGE0, help="Judge0 base URL")
    parser.add_argument("--backend", default=DEFAULT_BACKEND, help="Algobattle backend base URL")
    parser.add_argument("--problems", default="1-100", help="Problem range to test, e.g. 1-100 or 1-500")
    parser.add_argument("--limit", type=int, default=20, help="Max problems to test (0=all)")
    parser.add_argument("--disruption-only", action="store_true", help="Only run disruption tests")
    parser.add_argument("--determinism-only", action="store_true", help="Only run determinism tests")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for problem selection")
    parser.add_argument("--output", default="test_results.json", help="Output JSON file")
    args = parser.parse_args()

    start_time = time.time()

    print("=" * 70)
    print("ALGOBATTLE JUDGE0 COMPREHENSIVE TEST HARNESS")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Judge0: {args.judge0}")
    print(f"Backend: {args.backend}")
    print("=" * 70)

    # ── 1. Health checks ───────────────────────────────────────────────────────
    print("\n[1] Checking services...")
    client = Judge0Client(base_url=args.judge0)

    if not client.health_check():
        print(f"ERROR: Judge0 not reachable at {args.judge0}")
        print("  Start it with: docker run -p 2350:2350 judge0/judge0:1.13.0")
        sys.exit(1)
    print(f"  ✓ Judge0 is healthy")

    # Check backend (optional)
    try:
        api = AlgobattleAPI(base_url=args.backend)
        api.health()
        print(f"  ✓ Backend is healthy")
    except Exception as e:
        print(f"  ⚠ Backend not reachable ({e}) — skipping backend tests")

    # ── 2. Load test cases ────────────────────────────────────────────────────
    print("\n[2] Loading test cases...")
    testcases = load_testcases()
    print(f"  ✓ Loaded {len(testcases)} problem test suites")

    # ── 3. Load problems ──────────────────────────────────────────────────────
    print("\n[3] Loading problems from dataset...")
    with open(PROBLEMS_FILE) as f:
        dataset = json.load(f)
    problems = [p for p in dataset["problems"] if isinstance(p, dict) and p.get("slug")]
    print(f"  ✓ Loaded {len(problems)} problems")

    # Parse range
    if "-" in args.problems:
        start_idx, end_idx = map(int, args.problems.split("-"))
    else:
        start_idx, end_idx = 0, len(problems) - 1
    end_idx = min(end_idx, len(problems) - 1)
    selected = problems[start_idx:end_idx + 1]

    if args.limit > 0 and len(selected) > args.limit:
        random.seed(args.seed)
        selected = random.sample(selected, args.limit)
        print(f"  ✓ Selected {args.limit} random problems (seed={args.seed})")
    else:
        print(f"  ✓ Testing {len(selected)} problems [{start_idx}–{end_idx}]")

    # ── 4. Disruption tests (always run first) ───────────────────────────────
    print("\n[4] Running disruption tests...")
    disruption_results = []

    # Use a known problem for scaffold — doesn't matter, we inject empty code
    disruption_scenarios_run = [s for s in DISRUPTION_SCENARIOS]
    for i, scenario in enumerate(disruption_scenarios_run, 1):
        print(f"  [{i}/{len(disruption_scenarios_run)}] {scenario.name}...", end=" ", flush=True)
        try:
            result = client.submit(
                source_code=scenario.code_template.format(
                    user_code="",
                    signature="solution",
                    user_code_indented="    ",
                ),
                language_id=71,
                cpu_time_limit=10,
                memory_limit=512 * 1024,
            )
            status_id = result.get("status", {}).get("id") if isinstance(result.get("status"), dict) else result.get("status", 0)
            verdict = _map_judge0_status(status_id)
            memory_kb = float(result.get("memory", 0) or 0)
            elapsed_ms = float(result.get("time", 0) or 0) * 1000
            passed = verdict == scenario.expected_outcome
            disruption_results.append(
                DisruptionResult(
                    scenario=scenario.name,
                    expected=scenario.expected_outcome,
                    actual=verdict,
                    passed=passed,
                    execution_time_ms=elapsed_ms,
                    memory_kb=memory_kb,
                    error=result.get("stderr", "")[:200] if result.get("stderr") else "",
                )
            )
            status_str = "✓" if passed else f"✗ (got {verdict})"
            print(status_str)
        except Exception as exc:
            disruption_results.append(
                DisruptionResult(
                    scenario=scenario.name,
                    expected=scenario.expected_outcome,
                    actual="IE",
                    passed=False,
                    execution_time_ms=0,
                    memory_kb=0,
                    error=str(exc)[:200],
                )
            )
            print(f"✗ error: {exc}")

    disruption_passed = sum(1 for r in disruption_results if r.passed)
    disruption_total = len(disruption_results)
    print(f"\n  Disruption: {disruption_passed}/{disruption_total} passed")

    if args.disruption_only:
        _write_report(args.output, {
            "disruption_results": [asdict(r) for r in disruption_results],
        })
        print(f"\nReport written to {args.output}")
        return

    # ── 5. Problem correctness tests ─────────────────────────────────────────
    print(f"\n[5] Testing problem correctness ({len(selected)} problems)...")

    # Load curated test cases for key problems
    testcases_by_slug = load_testcases()

    problem_results: list[ProblemTestResult] = []
    issue_log: list[str] = []
    execution_times: list[float] = []
    memory_usages: list[float] = []

    for i, problem in enumerate(selected, 1):
        slug = problem.get("slug", "")
        title = problem.get("title", "")
        difficulty = problem.get("difficulty", "")
        problem_tcs = testcases_by_slug.get(slug, [])

        print(f"\n  [{i}/{len(selected)}] {slug} ({difficulty})", flush=True)

        if not problem_tcs:
            # No curated test cases — skip correctness test, mark as untested
            print(f"    ⚠ No test cases available, skipping")
            problem_results.append(
                ProblemTestResult(
                    slug=slug,
                    title=title,
                    difficulty=difficulty,
                    verdict="UNTESTED",
                    runtime_ms=0,
                    memory_kb=0,
                    expected_verdict="N/A",
                    passed=False,
                    sample_count=0,
                )
            )
            continue

        # We have test cases — build the code from the problem's starter code
        starter_code = problem.get("starter_code", {}).get("python3", problem.get("boilerplate_code", {}).get("python3", ""))
        if not starter_code:
            starter_code = problem.get("boilerplate_code", {}).get("python3", "")

        # Find the solution function name from the slug
        # e.g. "two-sum" → "two_sum", "three-sum" → "three_sum"
        fn_name = slug.replace("-", "_")

        # Build complete code: boilerplate + user solution stub
        if starter_code:
            # Try to find the function definition pattern
            code = starter_code
        else:
            # Minimal valid solution
            code = f"def solution(nums, target):\n    pass\n"

        # Test against each sample case
        sample_count = len(problem_tcs)
        verdict = "AC"
        runtime_ms = 0.0
        memory_kb = 0.0
        failed_case = None
        error_msg = ""

        for tc in problem_tcs:
            stdin = tc.get("input", tc.get("stdin", ""))
            expected = tc.get("expected", tc.get("output", ""))

            try:
                result = client.submit(
                    source_code=code,
                    language_id=71,
                    stdin=stdin,
                    expected_stdout=expected,
                    cpu_time_limit=10,
                    memory_limit=512 * 1024,
                )
                status_id = result.get("status", {}).get("id") if isinstance(result.get("status"), dict) else result.get("status", 0)
                sample_verdict = _map_judge0_status(status_id)
                sample_time = float(result.get("time", 0) or 0) * 1000
                sample_mem = float(result.get("memory", 0) or 0)
                runtime_ms += sample_time
                memory_kb = max(memory_kb, sample_mem)

                if sample_verdict != "AC":
                    verdict = sample_verdict
                    failed_case = {"input": stdin, "expected": expected, "actual": result.get("stdout", "")}
                    error_msg = result.get("stderr", "")
                    break
            except Exception as exc:
                verdict = "IE"
                error_msg = str(exc)
                break

        passed = verdict == "AC"
        if verdict == "UNTESTED":
            passed = False

        problem_results.append(
            ProblemTestResult(
                slug=slug,
                title=title,
                difficulty=difficulty,
                verdict=verdict,
                runtime_ms=runtime_ms / max(sample_count, 1),
                memory_kb=memory_kb,
                expected_verdict="AC",
                passed=passed,
                error_msg=error_msg[:300] if error_msg else "",
                sample_count=sample_count,
                failed_case=failed_case,
            )
        )

        status_str = "✓" if passed else f"✗ ({verdict})"
        print(f"    {status_str} — {sample_count} cases, {runtime_ms:.1f}ms avg, {memory_kb:.0f}KB")

        if not passed and verdict != "UNTESTED":
            issue_log.append(f"{slug}: expected AC, got {verdict} — {error_msg[:100] if error_msg else ''}")

    # ── 6. Determinism tests ─────────────────────────────────────────────────
    print("\n[6] Running determinism tests...")

    determinism_results: list[DeterminismResult] = []
    det_code = "print(sum(range(100)))"
    det_stdin = ""
    det_expected = "4950\n"
    det_runs = 5

    print(f"  Running {det_runs}x with: print(sum(range(100)))")
    det_result = run_determinism_test(client, det_code, det_stdin, det_expected, runs=det_runs)
    determinism_results.append(det_result)
    det_str = "✓" if det_result.is_deterministic else "✗"
    print(f"  Determinism [{det_runs} runs]: {det_str} — verdict={det_result.verdict}")
    if det_result.runtimes_ms:
        print(f"  Runtimes: {[f'{r:.2f}ms' for r in det_result.runtimes_ms]}")
        print(f"  Variance: {statistics.variance(det_result.runtimes_ms) if len(det_result.runtimes_ms) > 1 else 0:.4f}ms²")

    # Test determinism across different inputs
    det_inputs = [
        ("1\n2\n3\n", "6\n"),
        ("5\n", "120\n"),
        ("10\n20\n30\n", "60\n"),
    ]
    for stdin_val, expected_val in det_inputs:
        result = run_determinism_test(client, det_code, stdin_val, expected_val, runs=3)
        result.slug = f"sum_{stdin_val.strip()!r}"
        determinism_results.append(result)

    # ── 7. Aggregate report ──────────────────────────────────────────────────
    print("\n[7] Building report...")

    correct = sum(1 for r in problem_results if r.passed and r.verdict != "UNTESTED")
    incorrect = sum(1 for r in problem_results if not r.passed and r.verdict != "UNTESTED")
    untested = sum(1 for r in problem_results if r.verdict == "UNTESTED")
    errors = sum(1 for r in problem_results if r.verdict in ("IE", "RE", "CE"))
    timeouts = sum(1 for r in problem_results if r.verdict == "TLE")
    total_tested = correct + incorrect
    accuracy = (correct / total_tested * 100) if total_tested > 0 else 0

    by_difficulty = {}
    for diff in ["Easy", "Medium", "Hard"]:
        diff_results = [r for r in problem_results if r.difficulty == diff]
        diff_correct = sum(1 for r in diff_results if r.passed and r.verdict != "UNTESTED")
        diff_total = sum(1 for r in diff_results if r.verdict != "UNTESTED")
        by_difficulty[diff] = {
            "tested": diff_total,
            "correct": diff_correct,
            "accuracy": f"{diff_correct / diff_total * 100:.1f}%" if diff_total > 0 else "N/A",
        }

    exec_times = [r.runtime_ms for r in problem_results if r.runtime_ms > 0]
    mem_usages = [r.memory_kb for r in problem_results if r.memory_kb > 0]

    duration = time.time() - start_time

    report = AggregateReport(
        total=len(problem_results),
        correct=correct,
        incorrect=incorrect,
        error=errors,
        timeout=timeouts,
        untested=untested,
        accuracy_percent=accuracy,
        by_difficulty=by_difficulty,
        disruption_results=disruption_results,
        determinism_results=determinism_results,
        execution_times_ms=exec_times,
        memory_kb=mem_usages,
        issues=issue_log,
        duration_seconds=duration,
    )

    # ── 8. Print summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    print(f"\n  Problems tested:  {len(problem_results)}")
    print(f"  With test cases:  {len(problem_results) - untested}")
    print(f"  Untested:        {untested}")
    print(f"  Correct (AC):    {correct}")
    print(f"  Incorrect (WA/TLE/RE): {incorrect}")
    print(f"  Accuracy:        {accuracy:.1f}%")
    print(f"  Disruption:      {disruption_passed}/{disruption_total} passed")
    print(f"  Determinism:     {sum(1 for r in determinism_results if r.is_deterministic)}/{len(determinism_results)} passed")
    print(f"  Duration:        {duration:.1f}s")

    if by_difficulty:
        print("\n  By Difficulty:")
        for diff, stats in by_difficulty.items():
            print(f"    {diff:8s}: {stats['tested']:3d} tested, {stats['correct']:3d} correct, {stats['accuracy']}")

    if issue_log:
        print(f"\n  Issues found ({len(issue_log)}):")
        for issue in issue_log[:10]:
            print(f"    - {issue}")
        if len(issue_log) > 10:
            print(f"    ... and {len(issue_log) - 10} more")

    # ── 9. Write results ──────────────────────────────────────────────────────
    _write_report(args.output, report, problem_results, disruption_results, determinism_results)
    print(f"\n  Full report → {args.output}")


def _write_report(
    path: str,
    report: AggregateReport | dict,
    problem_results: list[ProblemTestResult] | None = None,
    disruption_results: list[DisruptionResult] | None = None,
    determinism_results: list[DeterminismResult] | None = None,
):
    data = {
        "generated_at": datetime.now().isoformat(),
        "judge0_version": "1.13.0",
        "report": asdict(report) if isinstance(report, AggregateReport) else report,
    }
    if problem_results is not None:
        data["problem_results"] = [asdict(r) for r in problem_results]
    if disruption_results is not None:
        data["disruption_results"] = [asdict(r) for r in disruption_results]
    if determinism_results is not None:
        data["determinism_results"] = [asdict(r) for r in determinism_results]

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    main()
