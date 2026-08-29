"""
TDD Tests — Sandbox Runner
==========================
RED: Write failing tests first (they define expected behavior).
GREEN: Make them pass.

The real SandboxRunner API (from sandbox_runner.py):
    runner = SandboxRunner(
        language="python",          # "python" | "cpp" | "javascript"
        cpu_time_s=5,              # CPU time limit in seconds
        wall_time_s=10,            # Wall-clock limit in seconds
        memory_kb=256*1024,         # Memory limit in KB
        output_kb=128,             # Output size limit in KB
        stack_kb=64*1024,          # Stack size limit in KB
    )
    result = runner.run(code, stdin, expected_stdout="")
    # result is a RunResult dataclass:
    #   verdict, stdout, stderr, exit_code, runtime_ms, memory_kb,
    #   wall_time_ms, token, status_detail
"""
import os
import sys

# Add sandbox directory to path
_TDD_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # tests/tdd → backend
sys.path.insert(0, os.path.join(_TDD_ROOT, "sandbox"))
from sandbox_runner import SandboxRunner, RunResult, DisruptionScenario, Verdict


# ──────────────────────────────────────────────────────────────────────────────
# GREEN Phase: Tests that SHOULD pass with current implementation
# ──────────────────────────────────────────────────────────────────────────────

class TestSBR_CorrectSolutions:
    """
    Story: Correct solutions are judged Accepted.
    As a judge, I want to correctly identify correct solutions.
    """

    def test_two_sum_correct_returns_ac(self):
        """Two Sum: nums=[2,7,11,15], target=9 → [0,1]"""
        runner = SandboxRunner(language="python", wall_time_s=15)
        code = """def solution(nums, target):
    seen = {}
    for i, n in enumerate(nums):
        c = target - n
        if c in seen:
            return [seen[c], i]
        seen[n] = i
    return []
print(solution([2, 7, 11, 15], 9))
"""
        result = runner.run(code, "")
        assert result.verdict == Verdict.ACCEPTED, f"Expected AC, got {result.verdict} | stdout={result.stdout!r}"
        assert "[0, 1]" in result.stdout, f"Expected [0, 1], got {result.stdout!r}"

    def test_valid_palindrome_correct_returns_ac(self):
        """Valid palindrome: 'racecar' → True"""
        runner = SandboxRunner(language="python", wall_time_s=15)
        code = """def solution(s):
    clean = ''.join(c.lower() for c in s if c.isalnum())
    return clean == clean[::-1]
print(solution('racecar'))
"""
        result = runner.run(code, "")
        assert result.verdict == Verdict.ACCEPTED, f"Expected AC, got {result.verdict}"
        assert "True" in result.stdout, f"Expected True, got {result.stdout!r}"

    def test_binary_search_correct_returns_ac(self):
        """Binary search: [1,3,5,7,9], target=5 → 2"""
        runner = SandboxRunner(language="python", wall_time_s=15)
        code = """def solution(nums, target):
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
print(solution([1, 3, 5, 7, 9], 5))
"""
        result = runner.run(code, "")
        assert result.verdict == Verdict.ACCEPTED
        assert "2" in result.stdout, f"Expected 2, got {result.stdout!r}"

    def test_valid_anagram_correct_returns_ac(self):
        """Valid anagram: 'anagram', 'nagaram' → True"""
        runner = SandboxRunner(language="python", wall_time_s=15)
        code = """def solution(s, t):
    if len(s) != len(t):
        return False
    c = {}
    for ch in s:
        c[ch] = c.get(ch, 0) + 1
    for ch in t:
        c[ch] = c.get(ch, 0) - 1
        if c[ch] < 0:
            return False
    return True
print(solution('anagram', 'nagaram'))
"""
        result = runner.run(code, "")
        assert result.verdict == Verdict.ACCEPTED, f"Expected AC, got {result.verdict}"

    def test_climbing_stairs_correct_returns_ac(self):
        """Climbing stairs: n=5 → 8"""
        runner = SandboxRunner(language="python", wall_time_s=15)
        code = """def solution(n):
    if n <= 2:
        return n
    a, b = 1, 2
    for _ in range(3, n + 1):
        a, b = b, a + b
    return b
print(solution(5))
"""
        result = runner.run(code, "")
        assert result.verdict == Verdict.ACCEPTED
        assert "8" in result.stdout, f"Expected 8, got {result.stdout!r}"

    def test_reverse_string_correct_returns_ac(self):
        """Reverse string: 'hello' → 'olleh'"""
        runner = SandboxRunner(language="python", wall_time_s=15)
        code = """def solution(s):
    return s[::-1]
print(solution('hello'))
"""
        result = runner.run(code, "")
        assert result.verdict == Verdict.ACCEPTED
        assert "olleh" in result.stdout, f"Expected olleh, got {result.stdout!r}"

    def test_majority_element_correct_returns_ac(self):
        """Majority element: [3,2,3] → 3"""
        runner = SandboxRunner(language="python", wall_time_s=15)
        code = """def solution(nums):
    from collections import Counter
    return Counter(nums).most_common(1)[0][0]
print(solution([3, 2, 3]))
"""
        result = runner.run(code, "")
        assert result.verdict == Verdict.ACCEPTED
        assert "3" in result.stdout, f"Expected 3, got {result.stdout!r}"

    def test_merge_sorted_lists_correct_returns_ac(self):
        """Merge sorted: [1,2,4], [1,3,4] → [1,1,2,3,4,4]"""
        runner = SandboxRunner(language="python", wall_time_s=15)
        code = """def solution(l1, l2):
    result = []
    i = j = 0
    while i < len(l1) and j < len(l2):
        if l1[i] <= l2[j]:
            result.append(l1[i])
            i += 1
        else:
            result.append(l2[j])
            j += 1
    result.extend(l1[i:])
    result.extend(l2[j:])
    return result
print(solution([1, 2, 4], [1, 3, 4]))
"""
        result = runner.run(code, "")
        assert result.verdict == Verdict.ACCEPTED, f"Expected AC, got {result.verdict} stdout={result.stdout!r}"

    def test_container_water_correct_returns_ac(self):
        """Container with most water: [1,8,6,2,5,4,8,3,7] → 49"""
        runner = SandboxRunner(language="python", wall_time_s=15)
        code = """def solution(heights):
    lo, hi = 0, len(heights) - 1
    best = 0
    while lo < hi:
        area = (hi - lo) * min(heights[lo], heights[hi])
        best = max(best, area)
        if heights[lo] < heights[hi]:
            lo += 1
        else:
            hi -= 1
    return best
print(solution([1, 8, 6, 2, 5, 4, 8, 3, 7]))
"""
        result = runner.run(code, "")
        assert result.verdict == Verdict.ACCEPTED
        assert "49" in result.stdout, f"Expected 49, got {result.stdout!r}"


class TestSBR_TLE:
    """
    Story: Infinite loops are killed and return TLE.
    As a judge, I want to prevent infinite loops from hanging the system.
    """

    def test_infinite_loop_returns_tle(self):
        """An infinite while loop should be killed as TLE."""
        runner = SandboxRunner(language="python", wall_time_s=3)
        code = "while True: pass"
        result = runner.run(code, "")
        assert result.verdict == Verdict.TIME_LIMIT_EXCEEDED, f"Expected TLE, got {result.verdict}"
        assert result.runtime_ms < 5000, f"Killed too slowly: {result.runtime_ms}ms"

    def test_infinite_for_loop_returns_tle(self):
        """An infinite for loop should be killed as TLE."""
        runner = SandboxRunner(language="python", wall_time_s=3)
        code = "for i in iter(int, 1): pass"
        result = runner.run(code, "")
        assert result.verdict == Verdict.TIME_LIMIT_EXCEEDED

    def test_tle_under_wall_clock_limit(self):
        """TLE verdict should fire within wall_time_s."""
        runner = SandboxRunner(language="python", wall_time_s=2)
        code = "while True: x = 1"
        result = runner.run(code, "")
        assert result.verdict == Verdict.TIME_LIMIT_EXCEEDED
        assert result.runtime_ms < 3000


class TestSBR_RE:
    """
    Story: Runtime errors are caught and reported as RE.
    As a judge, I want to report crashes gracefully.
    """

    def test_division_by_zero_returns_re(self):
        """Division by zero → RE."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = "result = 1 / 0"
        result = runner.run(code, "")
        assert result.verdict == Verdict.RUNTIME_ERROR, f"Expected RE, got {result.verdict}"

    def test_index_error_returns_re(self):
        """Index out of bounds → RE."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = "arr = [1, 2, 3]\nprint(arr[99])"
        result = runner.run(code, "")
        assert result.verdict == Verdict.RUNTIME_ERROR

    def test_key_error_returns_re(self):
        """Key not found → RE."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = "d = {}\nprint(d[42])"
        result = runner.run(code, "")
        assert result.verdict == Verdict.RUNTIME_ERROR

    def test_attribute_error_returns_re(self):
        """Attribute not found → RE."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = "x = None\nprint(x.foo)"
        result = runner.run(code, "")
        assert result.verdict == Verdict.RUNTIME_ERROR

    def test_type_error_returns_re(self):
        """Type mismatch → RE."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = "print('hello' + 42)"
        result = runner.run(code, "")
        assert result.verdict == Verdict.RUNTIME_ERROR

    def test_infinite_recursion_returns_re(self):
        """Infinite recursion → RE (RecursionError)."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = "def f(): return f()\nprint(f())"
        result = runner.run(code, "")
        assert result.verdict == Verdict.RUNTIME_ERROR


class TestSBR_MLE:
    """
    Story: Memory bombs are caught and reported as MLE.
    As a judge, I want to prevent memory exhaustion.
    """

    def test_memory_bomb_returns_mle_or_tle_or_re(self):
        """Unbounded memory allocation → MLE (if caught fast) or TLE/RE (wall clock kills it)."""
        runner = SandboxRunner(language="python", wall_time_s=3)
        code = "lst = []\nwhile True: lst.append(bytearray(100000))"
        result = runner.run(code, "")
        # Either MLE fires quickly OR wall clock kills it (both are correct)
        assert result.verdict in (Verdict.MEMORY_LIMIT_EXCEEDED, Verdict.TIME_LIMIT_EXCEEDED, Verdict.RUNTIME_ERROR), f"Expected MLE/TLE/RE, got {result.verdict}"


class TestSBR_OLE:
    """
    Story: Output size limits are enforced.
    As a judge, I want to prevent excessive output.
    """

    def test_excessive_output_returns_ole_or_re(self):
        """Output > output_kb limit → OLE or RE."""
        runner = SandboxRunner(language="python", output_kb=1, wall_time_s=5)
        code = "print('x' * 200000)"  # 200KB >> 1KB limit
        result = runner.run(code, "")
        # SIGXFSZ from RLIMIT_FSIZE causes RE; accept both
        assert result.verdict in (Verdict.OUTPUT_LIMIT_EXCEEDED, Verdict.RUNTIME_ERROR), f"Expected OLE or RE, got {result.verdict}"


class TestSBR_WA:
    """
    Story: Wrong output is detected as WA.
    As a judge, I want to correctly identify wrong answers.
    """

    def test_wrong_output_returns_wa(self):
        """Expected stdout mismatch → WA."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = "print('[0, 0]')"  # Always wrong
        result = runner.run(code, "", expected_stdout="[0, 1]")
        assert result.verdict == Verdict.WRONG_ANSWER, f"Expected WA, got {result.verdict}"

    def test_correct_with_expected_stdout_returns_ac(self):
        """Matching expected_stdout → AC."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = "print('[0, 1]')"
        result = runner.run(code, "", expected_stdout="[0, 1]")
        assert result.verdict == Verdict.ACCEPTED


class TestSBR_Determinism:
    """
    Story: The sandbox is deterministic.
    As a judge, I want same code + input to always produce the same result.
    """

    def test_sum_deterministic(self):
        """sum(range(100)) = 4950 every time."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = "print(sum(range(100)))"
        outputs = []
        for _ in range(5):
            result = runner.run(code, "")
            assert result.verdict == Verdict.ACCEPTED
            outputs.append(result.stdout.strip())
        assert len(set(outputs)) == 1, f"Outputs varied: {outputs}"
        assert outputs[0] == "4950"

    def test_sort_deterministic(self):
        """Sorting is deterministic."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = "print(sorted([3, 1, 4, 1, 5, 9]))"
        outputs = []
        for _ in range(5):
            result = runner.run(code, "")
            assert result.verdict == Verdict.ACCEPTED
            outputs.append(result.stdout.strip())
        assert len(set(outputs)) == 1

    def test_binary_search_deterministic(self):
        """Binary search is deterministic."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = """def solution(nums, target):
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
print(solution([1,3,5,7,9,11,13,15,17,19], 13))
"""
        outputs = []
        for _ in range(5):
            result = runner.run(code, "")
            assert result.verdict == Verdict.ACCEPTED
            outputs.append(result.stdout.strip())
        assert len(set(outputs)) == 1
        assert outputs[0] == "6"

    def test_hello_world_deterministic(self):
        """Hello world is deterministic."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = "print('hello world')"
        outputs = []
        for _ in range(5):
            result = runner.run(code, "")
            assert result.verdict == Verdict.ACCEPTED
            outputs.append(result.stdout.strip())
        assert len(set(outputs)) == 1
        assert outputs[0] == "hello world"


class TestSBR_Performance:
    """
    Story: Execution time is measured accurately.
    As a judge, I want to measure how fast correct solutions run.
    """

    def test_binary_search_fast(self):
        """Binary search on 100 elements should complete quickly."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = """def solution(nums, target):
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
print(solution(list(range(0, 200, 2)), 15))
"""
        result = runner.run(code, "")
        assert result.verdict == Verdict.ACCEPTED
        assert result.runtime_ms < 2000, f"Too slow: {result.runtime_ms}ms"

    def test_large_sort_completes(self):
        """Sorting 10K elements should complete (subprocess overhead is ~1s on macOS)."""
        runner = SandboxRunner(language="python", wall_time_s=10)
        # Use escaped braces so f-string doesn't interpolate
        data_str = str(list(range(10000)))
        code = f"print(sorted({data_str}))"
        result = runner.run(code, "")
        assert result.verdict == Verdict.ACCEPTED
        assert result.runtime_ms < 10000, f"Too slow: {result.runtime_ms}ms"


class TestSBR_DisruptionScenarios:
    """
    Story: DisruptionScenario class provides safe injection templates.
    As a test, I want to use pre-built disruption scenarios.
    """

    def test_disruption_scenario_infinite_loop(self):
        """DisruptionScenario.infinite_loop() → TLE."""
        runner = SandboxRunner(language="python", wall_time_s=3)
        code = DisruptionScenario.infinite_loop()
        result = runner.run(code, "")
        assert result.verdict == Verdict.TIME_LIMIT_EXCEEDED

    def test_disruption_scenario_division_by_zero(self):
        """DisruptionScenario.division_by_zero() → RE."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = DisruptionScenario.division_by_zero()
        result = runner.run(code, "")
        assert result.verdict == Verdict.RUNTIME_ERROR

    def test_disruption_scenario_index_error(self):
        """DisruptionScenario.index_error() → RE."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        code = DisruptionScenario.index_error()
        result = runner.run(code, "")
        assert result.verdict == Verdict.RUNTIME_ERROR


# ──────────────────────────────────────────────────────────────────────────────
# Run with: pytest tests/tdd/test_sandbox_runner.py -v
# Expected: ALL GREEN (all tests pass against the real SandboxRunner)
# ──────────────────────────────────────────────────────────────────────────────
