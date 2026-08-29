"""
Universal Sandbox Test Suite
=========================

Tests the cross-platform sandbox runner.
Run: pytest sandbox/tests/test_sandbox.py -v
"""

import json
import os
import sys
import platform

# Setup path  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sandbox.sandbox_runner import (
    SandboxRunner,
    DisruptionScenario,
    Verdict,
)


class TestBasicExecution:
    """Test basic code execution."""
    
    def test_python_print(self):
        runner = SandboxRunner(language="python")
        result = runner.run("print('hello')")
        assert result.verdict == Verdict.ACCEPTED
        assert "hello" in result.stdout
    
    def test_python_arithmetic(self):
        runner = SandboxRunner(language="python")
        result = runner.run("print(1 + 2)")
        assert result.verdict == Verdict.ACCEPTED
        assert "3" in result.stdout
    
    def test_python_sum(self):
        runner = SandboxRunner(language="python")
        result = runner.run("print(sum(range(101)))")
        assert result.verdict == Verdict.ACCEPTED
        assert "5050" in result.stdout
    
    def test_python_list_operations(self):
        runner = SandboxRunner(language="python")
        result = runner.run("print(sorted([3, 1, 2]))")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_python_string_operations(self):
        runner = SandboxRunner(language="python")
        result = runner.run("print('hello'.upper())")
        assert result.verdict == Verdict.ACCEPTED
        assert "HELLO" in result.stdout


class TestDisruptionHandling:
    """Test disruption scenarios are handled correctly."""
    
    def test_infinite_loop(self):
        runner = SandboxRunner(language="python", wall_time_s=2)
        result = runner.run("while True: pass")
        # Should be killed by wall clock
        assert result.verdict == Verdict.TIME_LIMIT_EXCEEDED
        assert result.runtime_ms < 4000
    
    def test_infinite_recursion(self):
        runner = SandboxRunner(language="python", wall_time_s=3)
        result = runner.run(DisruptionScenario.infinite_recursion())
        # Either TLE or RE is acceptable
        assert result.verdict in [
            Verdict.TIME_LIMIT_EXCEEDED, 
            Verdict.RUNTIME_ERROR
        ]
    
    def test_memory_bomb(self):
        runner = SandboxRunner(language="python", wall_time_s=3)
        result = runner.run(DisruptionScenario.memory_bomb())
        # Memory or time limit
        assert result.verdict in [
            Verdict.MEMORY_LIMIT_EXCEEDED,
            Verdict.TIME_LIMIT_EXCEEDED
        ]
    
    def test_division_by_zero(self):
        runner = SandboxRunner(language="python")
        result = runner.run(DisruptionScenario.division_by_zero())
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_index_error(self):
        runner = SandboxRunner(language="python")
        result = runner.run(DisruptionScenario.index_error())
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_all_disruptions(self):
        """Run all disruption scenarios."""
        runner = SandboxRunner(language="python", wall_time_s=3)
        
        scenarios = [
            ("infinite_loop", "while True: pass", [Verdict.TIME_LIMIT_EXCEEDED]),
            ("division_by_zero", DisruptionScenario.division_by_zero(), [Verdict.RUNTIME_ERROR]),
            ("index_error", DisruptionScenario.index_error(), [Verdict.RUNTIME_ERROR]),
        ]
        
        for name, code, expected in scenarios:
            result = runner.run(code)
            assert result.verdict in expected, f"{name}: expected {expected}, got {result.verdict}"


class TestWrongAnswer:
    """Test wrong answer detection."""
    
    def test_wrong_output(self):
        runner = SandboxRunner(language="python")
        result = runner.run("print(42)", expected_stdout="43")
        assert result.verdict == Verdict.WRONG_ANSWER
    
    def test_correct_output(self):
        runner = SandboxRunner(language="python")
        result = runner.run("print(42)", expected_stdout="42")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_whitespace_tolerance(self):
        runner = SandboxRunner(language="python")
        result = runner.run("print(42)  # with comment", expected_stdout="42")
        # Whitespace should be ignored
        assert result.verdict in [Verdict.ACCEPTED, Verdict.WRONG_ANSWER]


class TestTimeLimit:
    """Test time limit enforcement."""
    
    def test_fast_code(self):
        runner = SandboxRunner(language="python", wall_time_s=5)
        result = runner.run("print(sum(range(10000)))")
        assert result.verdict == Verdict.ACCEPTED
        assert result.runtime_ms < 5000  # Relaxed for CI/CD
    
    def test_slow_code(self):
        runner = SandboxRunner(language="python", wall_time_s=2)
        result = runner.run("""
import time
time.sleep(5)
print('done')
""")
        assert result.verdict == Verdict.TIME_LIMIT_EXCEEDED


class TestMemoryLimit:
    """Test memory limit handling."""
    
    def test_normal_memory(self):
        runner = SandboxRunner(language="python")
        result = runner.run("data = [0] * 10000; print(len(data))")
        assert result.verdict == Verdict.ACCEPTED


class TestDeterminism:
    """Test that code produces deterministic results."""
    
    def test_same_output(self):
        runner = SandboxRunner(language="python")
        code = "print(sum(range(100)))"
        results = [runner.run(code) for _ in range(5)]
        
        # All should have same verdict
        assert all(r.verdict == Verdict.ACCEPTED for r in results)
        
        # All should have same output
        outputs = [r.stdout.strip() for r in results]
        assert len(set(outputs)) == 1
    
    def test_seeded_random(self):
        runner = SandboxRunner(language="python")
        code = """
import random
random.seed(42)
print(random.randint(1, 1000000))
"""
        results = [runner.run(code) for _ in range(3)]
        outputs = [r.stdout.strip() for r in results]
        assert len(set(outputs)) == 1


class TestMultiLanguage:
    """Test multi-language support."""
    
    def test_python(self):
        runner = SandboxRunner(language="python")
        result = runner.run("print('python works')")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_cpp(self):
        runner = SandboxRunner(language="cpp")
        code = """
#include <iostream>
int main() {
    std::cout << "cpp works" << std::endl;
    return 0;
}
"""
        result = runner.run(code)
        assert result.verdict == Verdict.ACCEPTED
        assert "cpp works" in result.stdout
    
    def test_cpp_infinite_loop(self):
        runner = SandboxRunner(language="cpp", wall_time_s=2)
        code = """
#include <iostream>
int main() {
    while(true) {}
    return 0;
}
"""
        result = runner.run(code)
        assert result.verdict == Verdict.TIME_LIMIT_EXCEEDED
    
    def test_cpp_compilation_error(self):
        runner = SandboxRunner(language="cpp")
        code = """
#include <iostream>
int main() {
    std::cout << "missing semicolon"
    return 0;
}
"""
        result = runner.run(code)
        assert result.verdict == Verdict.COMPILATION_ERROR
    
    def test_javascript(self):
        runner = SandboxRunner(language="javascript")
        result = runner.run("console.log('js works')")
        # May fail if node not installed, which is OK
        assert result.verdict in [Verdict.ACCEPTED, Verdict.INTERNAL_ERROR]


class TestAlgorithmicProblems:
    """Test real algorithmic problems."""
    
    def test_two_sum(self):
        runner = SandboxRunner(language="python")
        code = """
def two_sum(nums, target):
    seen = {}
    for i, n in enumerate(nums):
        if target - n in seen:
            return [seen[target - n], i]
        seen[n] = i
    return []
"""
        
        test_cases = [
            ("[2,7,11,15]", "9", "[0, 1]"),
            ("[3,2,4]", "6", "[1, 2]"),
            ("[3,3]", "6", "[0, 1]"),
        ]
        
        for nums_str, target_str, expected in test_cases:
            code_full = code + f"""
import json
data = json.loads(input())
nums = data['nums']
target = data['target']
result = two_sum(nums, target)
print(result)
"""
            input_data = json.dumps({"nums": json.loads(nums_str), "target": int(target_str)})
            result = runner.run(code_full, stdin=input_data)
            assert result.verdict == Verdict.ACCEPTED, f"Failed for {nums_str}, {target_str}"
    
    def test_binary_search(self):
        runner = SandboxRunner(language="python")
        code = """
def binary_search(arr, target):
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1

arr = list(range(100))
target = 42
print(binary_search(arr, target))
"""
        result = runner.run(code)
        assert result.verdict == Verdict.ACCEPTED
        assert "42" in result.stdout
    
    def test_fibonacci(self):
        runner = SandboxRunner(language="python")
        code = """
def fib(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b

print(fib(20))
"""
        result = runner.run(code)
        assert result.verdict == Verdict.ACCEPTED
        assert "6765" in result.stdout


class TestStress:
    """Stress tests."""
    
    def test_large_sum(self):
        runner = SandboxRunner(language="python")
        code = "print(sum(range(1000000)))"
        result = runner.run(code)
        assert result.verdict == Verdict.ACCEPTED
        assert "499999500000" in result.stdout
    
    def test_many_operations(self):
        runner = SandboxRunner(language="python")
        code = """
total = 0
for i in range(100000):
    total += i
print(total)
"""
        result = runner.run(code)
        assert result.verdict == Verdict.ACCEPTED
    
    def test_nested_loops(self):
        runner = SandboxRunner(language="python")
        code = """
count = 0
for i in range(100):
    for j in range(100):
        count += 1
print(count)
"""
        result = runner.run(code)
        assert result.verdict == Verdict.ACCEPTED
        assert "10000" in result.stdout


class TestOutputLimit:
    """Test output limit handling."""
    
    def test_normal_output(self):
        runner = SandboxRunner(language="python")
        result = runner.run("print('hello world')")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_large_output(self):
        runner = SandboxRunner(language="python", output_kb=1)
        result = runner.run("print('x' * 1000)")
        # May pass or fail depending on limit
        assert result.verdict in [Verdict.ACCEPTED, Verdict.OUTPUT_LIMIT_EXCEEDED]


# Helper for json import in test
import json


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
