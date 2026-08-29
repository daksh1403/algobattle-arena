"""
BDD Step Definitions — Algobattle Platform
==========================================
pytest-bdd matches steps by docstring text in .feature files.

Run: pytest tests/bdd/ --tb=short
"""
import pytest
import time
import os
import sys

# Sandbox for pure sandbox tests (no backend needed)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "sandbox"))
from sandbox_runner import SandboxRunner, DisruptionScenario


# ──────────────────────────────────────────────────────────────────────────────
# Shared state
# ──────────────────────────────────────────────────────────────────────────────

class _S:
    result = None          # last RunResult
    results = []           # list of RunResults
    http_resp = None       # last HTTP response
    http_client = None     # TestClient
    token = None
    submission_id = None


S = _S()


# ──────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """FastAPI test client — skips if backend isn't importable."""
    try:
        from app.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)
    except Exception:
        pytest.skip("Backend app not importable")


# ──────────────────────────────────────────────────────────────────────────────
# AUTHENTICATION STEPS
# ──────────────────────────────────────────────────────────────────────────────

def test_user_registers_successfully(client):
    """I register a new user with username "alice", email "alice@algo.dev", and password "SecurePass123!"."""
    S.http_resp = client.post("/api/users/register", json={
        "username": "alice_bdd",
        "email": "alice_bdd@algo.dev",
        "password": "SecurePass123!",
    })
    if S.http_resp.status_code == 201:
        S.token = S.http_resp.json().get("access_token")


def test_user_login_successfully(client):
    """I login with username "alice" and password "SecurePass123!"."""
    S.http_resp = client.post("/api/auth/login", data={
        "username": "alice_bdd",
        "password": "SecurePass123!",
    })
    if S.http_resp.status_code == 200:
        S.token = S.http_resp.json()["access_token"]


def test_login_fails_with_wrong_password(client):
    """I login with username "alice" and password "WrongPassword"."""
    S.http_resp = client.post("/api/auth/login", data={
        "username": "alice_bdd",
        "password": "WrongPassword",
    })


def test_duplicate_registration_rejected(client):
    """I try to register with username "alice" and email "other@algo.dev"."""
    # First register alice_bdd2
    client.post("/api/users/register", json={
        "username": "alice_bdd2",
        "email": "alice_bdd2@algo.dev",
        "password": "SecurePass123!",
    })
    # Now try to register the same username
    S.http_resp = client.post("/api/users/register", json={
        "username": "alice_bdd2",
        "email": "other@algo.dev",
        "password": "SecurePass123!",
    })


def test_non_admin_cannot_create_problem(client):
    """bob tries to create a problem."""
    # Register bob as regular user
    client.post("/api/users/register", json={
        "username": "bob_bdd",
        "email": "bob_bdd@algo.dev",
        "password": "BobPass123!",
    })
    resp = client.post("/api/auth/login", data={
        "username": "bob_bdd",
        "password": "BobPass123!",
    })
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        S.http_resp = client.post("/api/problems/",
            json={
                "title": "Bob's Problem",
                "slug": "bob-problem",
                "difficulty": "EASY",
                "description": "Test",
                "boilerplate_code": {},
            },
            headers={"Authorization": f"Bearer {token}"},
        )


# ──────────────────────────────────────────────────────────────────────────────
# SUBMISSION LIFECYCLE STEPS
# ──────────────────────────────────────────────────────────────────────────────

def test_submit_correct_code_via_sandbox():
    """alice submits correct Python code for problem 1."""
    S.result = SandboxRunner(language="python", wall_time_s=15).run(
        """def solution(nums, target):
    seen = {}
    for i, n in enumerate(nums):
        if target - n in seen:
            return [seen[target - n], i]
        seen[n] = i
    return []
print(solution([2, 7, 11, 15], 9))"""
    )


def test_submit_wrong_code_via_sandbox():
    """alice submits wrong Python code for problem 1."""
    S.result = SandboxRunner(language="python", wall_time_s=15).run(
        "print('[0, 0]')",
        expected_stdout="[0, 1]",
    )


def test_submit_nonexistent_problem(client):
    """I submit code for a non-existent problem id 99999."""
    # Ensure logged in
    client.post("/api/users/register", json={
        "username": "sub_test_user",
        "email": "sub_test@algo.dev",
        "password": "TestPass123!",
    })
    resp = client.post("/api/auth/login", data={
        "username": "sub_test_user",
        "password": "TestPass123!",
    })
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        S.http_resp = client.post("/api/submissions/",
            json={"problem_id": 99999, "language": "python", "code": "print(1)"},
            headers={"Authorization": f"Bearer {token}"},
        )


def test_submit_infinite_loop():
    """I submit code that runs an infinite loop with 3s timeout."""
    S.result = SandboxRunner(language="python", wall_time_s=3).run(
        "while True: pass"
    )


def test_submit_division_by_zero():
    """I submit code that causes a division by zero."""
    S.result = SandboxRunner(language="python", wall_time_s=5).run(
        "result = 1 / 0"
    )


# ──────────────────────────────────────────────────────────────────────────────
# JUDGE SANDBOX — CORRECTNESS STEPS
# ──────────────────────────────────────────────────────────────────────────────

def test_bdd_correct_two_sum():
    """I run Python code that returns the correct answer for "two sum"."""
    S.result = SandboxRunner(language="python", wall_time_s=15).run(
        """def solution(nums, target):
    seen = {}
    for i, n in enumerate(nums):
        c = target - n
        if c in seen:
            return [seen[c], i]
        seen[n] = i
    return []
print(solution([2, 7, 11, 15], 9))"""
    )


def test_bdd_wrong_answer():
    """I run Python code that returns a wrong answer."""
    S.result = SandboxRunner(language="python", wall_time_s=15).run(
        "print('[0, 0]')",
        expected_stdout="[0, 1]",
    )


def test_bdd_no_output():
    """I run Python code that produces no output."""
    S.result = SandboxRunner(language="python", wall_time_s=15).run(
        "x = 1",
        expected_stdout="1",
    )


# ──────────────────────────────────────────────────────────────────────────────
# JUDGE SANDBOX — DISRUPTION STEPS
# ──────────────────────────────────────────────────────────────────────────────

def test_bdd_infinite_loop_tle():
    """I run Python code with an infinite while loop with wall_time_s=3."""
    S.result = SandboxRunner(language="python", wall_time_s=3).run("while True: pass")


def test_bdd_infinite_recursion_re():
    """I run Python code with infinite recursion."""
    S.result = SandboxRunner(language="python", wall_time_s=5).run(
        DisruptionScenario.infinite_recursion()
    )


def test_bdd_division_by_zero_re():
    """I run Python code with division by zero."""
    S.result = SandboxRunner(language="python", wall_time_s=5).run(
        DisruptionScenario.division_by_zero()
    )


def test_bdd_index_error_re():
    """I run Python code with an index error."""
    S.result = SandboxRunner(language="python", wall_time_s=5).run(
        DisruptionScenario.index_error()
    )


def test_bdd_memory_bomb():
    """I run Python code that allocates unbounded memory."""
    S.result = SandboxRunner(language="python", wall_time_s=5).run(
        "lst = []\nwhile True: lst.append(bytearray(100000))"
    )


def test_bdd_excessive_output():
    """I run Python code that prints more than 1KB."""
    S.result = SandboxRunner(language="python", output_kb=1, wall_time_s=5).run(
        "print('x' * 200000)"
    )


# ──────────────────────────────────────────────────────────────────────────────
# JUDGE SANDBOX — DETERMINISM STEPS
# ──────────────────────────────────────────────────────────────────────────────

def test_bdd_determinism_same_code_5x():
    """I run the same Python code 5 times with the same input."""
    runner = SandboxRunner(language="python", wall_time_s=15)
    S.results = [runner.run("print(sum(range(100)))") for _ in range(5)]


def test_bdd_determinism_sort():
    """I run a sort algorithm 5 times."""
    runner = SandboxRunner(language="python", wall_time_s=15)
    S.results = [runner.run("print(sorted([3, 1, 4, 1, 5, 9]))") for _ in range(5)]


# ──────────────────────────────────────────────────────────────────────────────
# JUDGE SANDBOX — PERFORMANCE STEPS
# ──────────────────────────────────────────────────────────────────────────────

def test_bdd_binary_search_perf():
    """I run a binary search on 100 elements."""
    S.result = SandboxRunner(language="python", wall_time_s=15).run(
        """def solution(nums, target):
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if nums[mid] == target:
            return mid
        elif nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
print(solution(list(range(0, 200, 2)), 15))"""
    )


def test_bdd_large_sort_perf():
    """I run a sort on 10000 elements."""
    data_str = str(list(range(10000)))
    S.result = SandboxRunner(language="python", wall_time_s=10).run(
        f"print(sorted({data_str}))"
    )


# ──────────────────────────────────────────────────────────────────────────────
# ASSERTION STEP FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────

def test_verdict_is_ac():
    """the verdict should be "AC"."""
    assert S.result is not None
    assert S.result.verdict == "AC", \
        f"Expected AC, got {S.result.verdict} | stdout={S.result.stdout!r}"


def test_stdout_has_correct_output():
    """the stdout should contain the correct output."""
    assert S.result is not None
    assert "4950" in S.result.stdout


def test_verdict_is_wa():
    """the verdict should be "WA"."""
    assert S.result is not None
    assert S.result.verdict == "WA", \
        f"Expected WA, got {S.result.verdict}"


def test_verdict_is_tle():
    """the verdict should be "TLE"."""
    assert S.result is not None
    assert S.result.verdict == "TLE", \
        f"Expected TLE, got {S.result.verdict} | wall_time={S.result.wall_time_ms}ms"


def test_verdict_is_re():
    """the verdict should be "RE"."""
    assert S.result is not None
    assert S.result.verdict == "RE", \
        f"Expected RE, got {S.result.verdict}"


def test_verdict_is_mle_tle_or_re():
    """the verdict should be one of "MLE", "TLE", or "RE"."""
    assert S.result is not None
    assert S.result.verdict in ("MLE", "TLE", "RE"), \
        f"Expected MLE/TLE/RE, got {S.result.verdict}"


def test_verdict_is_ole_or_re():
    """the verdict should be one of "OLE" or "RE"."""
    assert S.result is not None
    assert S.result.verdict in ("OLE", "RE"), \
        f"Expected OLE/RE, got {S.result.verdict}"


def test_wall_time_under_5000ms():
    """the wall time should be less than 5000ms."""
    assert S.result is not None
    assert S.result.wall_time_ms < 5000, \
        f"Wall time too high: {S.result.wall_time_ms}ms"


def test_wall_time_under_2000ms():
    """the wall time should be under 2000ms."""
    assert S.result is not None
    assert S.result.wall_time_ms < 2000


def test_wall_time_under_10000ms():
    """the wall time should be under 10000ms."""
    assert S.result is not None
    assert S.result.wall_time_ms < 10000


def test_all_5_verdicts_ac():
    """all 5 results should have verdict "AC"."""
    assert S.results, "No results collected"
    for i, r in enumerate(S.results):
        assert r.verdict == "AC", f"Run {i+1}: expected AC, got {r.verdict}"


def test_all_5_outputs_identical():
    """all 5 stdout values should be identical."""
    assert S.results, "No results collected"
    outputs = [r.stdout.strip() for r in S.results]
    assert len(set(outputs)) == 1, f"Outputs varied: {set(outputs)}"


def test_http_status_201():
    """the registration should succeed with status 201."""
    assert S.http_resp is not None
    assert S.http_resp.status_code == 201, \
        f"Expected 201, got {S.http_resp.status_code}: {S.http_resp.text}"


def test_http_status_200_with_token():
    """the response should contain a JWT access token."""
    assert S.http_resp is not None
    assert S.http_resp.status_code == 200
    data = S.http_resp.json()
    assert "access_token" in data


def test_http_login_200():
    """the login should succeed with status 200."""
    assert S.http_resp is not None
    assert S.http_resp.status_code == 200


def test_http_login_401():
    """the login should fail with status 401."""
    assert S.http_resp is not None
    assert S.http_resp.status_code == 401


def test_http_registration_409():
    """the registration should fail with status 409."""
    assert S.http_resp is not None
    assert S.http_resp.status_code == 409


def test_http_forbidden_403():
    """the request should be forbidden with status 403."""
    assert S.http_resp is not None
    assert S.http_resp.status_code == 403, \
        f"Expected 403, got {S.http_resp.status_code}"


def test_http_not_found_404():
    """the submission should fail with status 404."""
    assert S.http_resp is not None
    assert S.http_resp.status_code == 404


def test_submission_is_ac():
    """the submission should be accepted with verdict "AC"."""
    assert S.result is not None
    assert S.result.verdict == "AC", \
        f"Expected AC, got {S.result.verdict}"


def test_submission_wall_time_under_5s():
    """the wall time should be under 5 seconds."""
    assert S.result is not None
    assert S.result.wall_time_ms < 5000


def test_submission_is_tle():
    """the submission should be terminated with verdict "TLE"."""
    assert S.result is not None
    assert S.result.verdict == "TLE"


def test_submission_is_re():
    """the submission verdict should be "RE"."""
    assert S.result is not None
    assert S.result.verdict == "RE"


def test_submission_wa():
    """the submission verdict should be "WA"."""
    assert S.result is not None
    assert S.result.verdict == "WA"
