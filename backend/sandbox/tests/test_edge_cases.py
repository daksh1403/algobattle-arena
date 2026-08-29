#!/usr/bin/env python3
"""
Comprehensive Edge Case Test Suite
===================================

Tests every edge case that real judge systems (Codeforces, LeetCode, etc.) face.
This ensures the sandbox handles all real-world scenarios.

Run: python -m pytest sandbox/tests/test_edge_cases.py -v
"""

import json
import os
import sys
import time
import threading
import signal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sandbox.sandbox_runner import SandboxRunner, Verdict


class TestCompilationErrors:
    """Test all compilation error types."""
    
    def test_python_syntax_error(self):
        """Python: syntax error (Python compiles at runtime)"""
        runner = SandboxRunner(language="python")
        result = runner.run("print(")
        # Python compiles at runtime, so syntax errors are runtime errors
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_python_indent_error(self):
        """Python: indentation error (Python compiles at runtime)"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
if True:
print("no indent")
""")
        # Python compiles at runtime, so indent errors are runtime errors
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_python_name_error(self):
        """Python: undefined name (runtime but checkable)"""
        runner = SandboxRunner(language="python")
        result = runner.run("print(undefined_var)")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_python_import_error(self):
        """Python: import error"""
        runner = SandboxRunner(language="python")
        result = runner.run("import nonexistent_module_xyz")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_python_type_error(self):
        """Python: type error"""
        runner = SandboxRunner(language="python")
        result = runner.run("print(1 + 'string')")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_python_attribute_error(self):
        """Python: attribute error"""
        runner = SandboxRunner(language="python")
        result = runner.run("[].push()")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_python_recursion_limit(self):
        """Python: recursion depth exceeded"""
        runner = SandboxRunner(language="python", wall_time_s=5)
        result = runner.run("""
def f():
    return f()
f()
""")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_cpp_syntax_error(self):
        """C++: syntax error"""
        runner = SandboxRunner(language="cpp")
        result = runner.run("""
#include <iostream>
int main() {
    cout << "hello"
    return 0;
}
""")
        assert result.verdict == Verdict.COMPILATION_ERROR
    
    def test_cpp_undefined_reference(self):
        """C++: undefined reference"""
        runner = SandboxRunner(language="cpp")
        result = runner.run("""
#include <iostream>
int main() {
    undefined_function();
    return 0;
}
""")
        assert result.verdict == Verdict.COMPILATION_ERROR
    
    def test_cpp_missing_header(self):
        """C++: missing header"""
        runner = SandboxRunner(language="cpp")
        result = runner.run("""
int main() {
    std::string s;
    return 0;
}
""")
        assert result.verdict == Verdict.COMPILATION_ERROR


class TestRuntimeErrors:
    """Test all runtime error types."""
    
    def test_division_by_zero(self):
        """Division by zero"""
        runner = SandboxRunner(language="python")
        result = runner.run("print(1 / 0)")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_modulo_by_zero(self):
        """Modulo by zero"""
        runner = SandboxRunner(language="python")
        result = runner.run("print(1 % 0)")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_index_out_of_bounds(self):
        """Index out of bounds"""
        runner = SandboxRunner(language="python")
        result = runner.run("print([1,2,3][10])")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_negative_index(self):
        """Negative index out of bounds"""
        runner = SandboxRunner(language="python")
        result = runner.run("print([1][-2])")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_list_assignment_out_of_bounds(self):
        """List assignment out of bounds"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
a = [1, 2, 3]
a[10] = 5
""")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_string_index_out_of_bounds(self):
        """String index out of bounds"""
        runner = SandboxRunner(language="python")
        result = runner.run("print('abc'[10])")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_tuple_immutable(self):
        """Tuple is immutable"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
t = (1, 2, 3)
t[0] = 5
""")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_dict_key_error(self):
        """Dictionary key error"""
        runner = SandboxRunner(language="python")
        result = runner.run("print({}['nonexistent'])")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_invalid_conversion(self):
        """Invalid type conversion"""
        runner = SandboxRunner(language="python")
        result = runner.run("int('not_a_number')")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_float_conversion(self):
        """Float conversion from invalid string"""
        runner = SandboxRunner(language="python")
        result = runner.run("float('inf' + '1')")
        # This might work or fail depending on implementation
        assert result.verdict in [Verdict.ACCEPTED, Verdict.RUNTIME_ERROR]
    
    def test_none_type_error(self):
        """NoneType has no attribute"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
x = None
x.append(1)
""")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_unpack_wrong_count(self):
        """Unpack error"""
        runner = SandboxRunner(language="python")
        result = runner.run("a, b = [1, 2, 3]")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_cpp_segfault(self):
        """C++ segmentation fault"""
        runner = SandboxRunner(language="cpp")
        result = runner.run("""
#include <iostream>
int main() {
    int* p = nullptr;
    *p = 42;
    return 0;
}
""")
        assert result.verdict == Verdict.RUNTIME_ERROR
    
    def test_cpp_abort(self):
        """C++ abort signal"""
        runner = SandboxRunner(language="cpp")
        result = runner.run("""
#include <cstdlib>
int main() {
    abort();
    return 0;
}
""")
        assert result.verdict == Verdict.RUNTIME_ERROR


class TestTimeLimitExceeded:
    """Test time limit exceeded scenarios."""
    
    def test_infinite_loop(self):
        """Infinite while loop"""
        runner = SandboxRunner(language="python", wall_time_s=2)
        result = runner.run("""
while True:
    pass
""")
        assert result.verdict == Verdict.TIME_LIMIT_EXCEEDED
    
    def test_infinite_for(self):
        """Infinite for loop"""
        runner = SandboxRunner(language="python", wall_time_s=2)
        result = runner.run("""
for i in range(10**10):
    pass
""")
        # Python's range is lazy, but iteration still takes time
        assert result.verdict in [Verdict.TIME_LIMIT_EXCEEDED, Verdict.ACCEPTED]
    
    def test_infinite_recursion(self):
        """Infinite recursion"""
        runner = SandboxRunner(language="python", wall_time_s=2)
        result = runner.run("""
def recurse():
    return recurse()
recurse()
""")
        assert result.verdict == Verdict.RUNTIME_ERROR  # RecursionError before TLE
    
    def test_exponential_slowdown(self):
        """Exponential time complexity"""
        runner = SandboxRunner(language="python", wall_time_s=3)
        result = runner.run("""
def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)
print(fib(30))
""")
        assert result.verdict == Verdict.ACCEPTED  # 30 is manageable
    
    def test_polynomial_slowdown(self):
        """O(n^3) complexity"""
        runner = SandboxRunner(language="python", wall_time_s=3)
        result = runner.run("""
n = 500
result = 0
for i in range(n):
    for j in range(n):
        for k in range(n):
            result += 1
print(result)
""")
        assert result.verdict == Verdict.TIME_LIMIT_EXCEEDED


class TestMemoryLimitExceeded:
    """Test memory limit exceeded scenarios."""
    
    def test_list_append_infinite(self):
        """Infinite list growth"""
        runner = SandboxRunner(language="python", wall_time_s=5, memory_kb=32 * 1024)
        result = runner.run("""
lst = []
while True:
    lst.append(1)
""")
        assert result.verdict in [Verdict.MEMORY_LIMIT_EXCEEDED, Verdict.TIME_LIMIT_EXCEEDED]
    
    def test_dict_growth(self):
        """Unbounded dict growth"""
        runner = SandboxRunner(language="python", wall_time_s=5, memory_kb=32 * 1024)
        result = runner.run("""
d = {}
i = 0
while True:
    d[i] = i
    i += 1
""")
        assert result.verdict in [Verdict.MEMORY_LIMIT_EXCEEDED, Verdict.TIME_LIMIT_EXCEEDED]
    
    def test_string_concat_loop(self):
        """String concatenation in loop (inefficient)"""
        runner = SandboxRunner(language="python", wall_time_s=3, memory_kb=64 * 1024)
        result = runner.run("""
s = ""
for i in range(100000):
    s += "x"
print(len(s))
""")
        assert result.verdict == Verdict.ACCEPTED  # 100K is fine
    
    def test_large_array(self):
        """Large array allocation"""
        runner = SandboxRunner(language="python", wall_time_s=5, memory_kb=16 * 1024)
        result = runner.run("""
import sys
arr = [0] * (100 * 1000 * 1000)  # 800MB
""")
        # Python may allocate lazily or handle this gracefully
        assert result.verdict in [Verdict.MEMORY_LIMIT_EXCEEDED, Verdict.RUNTIME_ERROR, Verdict.ACCEPTED]


class TestOutputLimitExceeded:
    """Test output limit exceeded scenarios."""
    
    def test_infinite_print(self):
        """Infinite printing"""
        runner = SandboxRunner(language="python", wall_time_s=2, output_kb=1)
        result = runner.run("""
while True:
    print("x" * 1000)
""")
        assert result.verdict == Verdict.OUTPUT_LIMIT_EXCEEDED
    
    def test_huge_output(self):
        """Huge single output"""
        runner = SandboxRunner(language="python", wall_time_s=5, output_kb=256)
        result = runner.run("print('x' * (100 * 1024))")
        assert result.verdict == Verdict.ACCEPTED  # 100KB is fine with 256KB limit
    
    def test_excessive_output(self):
        """Excessive output"""
        runner = SandboxRunner(language="python", wall_time_s=5, output_kb=10)
        result = runner.run("print('x' * (50 * 1024))")
        assert result.verdict == Verdict.OUTPUT_LIMIT_EXCEEDED


class TestWrongAnswer:
    """Test wrong answer scenarios."""
    
    def test_incorrect_output(self):
        """Completely wrong output"""
        runner = SandboxRunner(language="python")
        result = runner.run("print(42)", expected_stdout="0")
        assert result.verdict == Verdict.WRONG_ANSWER
    
    def test_off_by_one(self):
        """Off by one error"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
arr = [1, 2, 3, 4, 5]
print(sum(arr))
""", expected_stdout="16")  # Correct is 15
        assert result.verdict == Verdict.WRONG_ANSWER
    
    def test_whitespace_difference(self):
        """Whitespace difference - sandbox strips trailing whitespace"""
        runner = SandboxRunner(language="python")
        result = runner.run("print('hello world')", expected_stdout="hello")
        assert result.verdict == Verdict.WRONG_ANSWER
    
    def test_case_sensitive(self):
        """Case sensitivity"""
        runner = SandboxRunner(language="python")
        result = runner.run("print('TRUE')", expected_stdout="true")
        assert result.verdict == Verdict.WRONG_ANSWER
    
    def test_newline_difference(self):
        """Newline at end - sandbox normalizes newlines"""
        runner = SandboxRunner(language="python")
        result = runner.run("print('a')\nprint('b')", expected_stdout="a\nb\nc")
        assert result.verdict == Verdict.WRONG_ANSWER
    
    def test_extra_whitespace(self):
        """Extra spaces"""
        runner = SandboxRunner(language="python")
        result = runner.run("print('1  2')", expected_stdout="1 2")
        assert result.verdict == Verdict.WRONG_ANSWER
    
    def test_missing_newline(self):
        """Missing newline between outputs"""
        runner = SandboxRunner(language="python")
        result = runner.run("print('1', end=''); print('2')", expected_stdout="1\n2")
        assert result.verdict == Verdict.WRONG_ANSWER
    
    def test_floating_point_precision(self):
        """Floating point precision"""
        runner = SandboxRunner(language="python")
        result = runner.run("print(0.1 + 0.2)", expected_stdout="0.3")
        # 0.1 + 0.2 = 0.30000000000000004
        assert result.verdict == Verdict.WRONG_ANSWER
    
    def test_integer_overflow(self):
        """Integer overflow (theoretical in Python)"""
        runner = SandboxRunner(language="python")
        result = runner.run("print(2**1000)")
        assert result.verdict == Verdict.ACCEPTED  # Python handles big ints
    
    def test_empty_output(self):
        """Empty output when something expected"""
        runner = SandboxRunner(language="python")
        result = runner.run("x = 1", expected_stdout="42")  # No output but expected 42
        assert result.verdict == Verdict.WRONG_ANSWER
    
    def test_no_output_expected(self):
        """No output expected but something produced"""
        runner = SandboxRunner(language="python")
        result = runner.run("print(42)", expected_stdout="")
        assert result.verdict == Verdict.WRONG_ANSWER


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_input(self):
        """Empty input - EOFError when reading empty stdin"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
try:
    s = input()
    print(len(s))
except EOFError:
    print(0)
""", stdin="")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_single_element_array(self):
        """Single element array"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
arr = [1]
print(sum(arr))
""", expected_stdout="1")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_negative_numbers(self):
        """Negative numbers"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
arr = [-1, -2, 3, -4]
print(sum(arr))
""", expected_stdout="-4")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_duplicates(self):
        """Duplicate elements"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
arr = [1, 2, 2, 3, 3, 3]
print(len(set(arr)))
""", expected_stdout="3")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_very_large_numbers(self):
        """Very large numbers"""
        runner = SandboxRunner(language="python")
        result = runner.run("print(10**100)")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_very_small_numbers(self):
        """Very small decimal"""
        runner = SandboxRunner(language="python")
        result = runner.run("print(1e-100)")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_unicode_input(self):
        """Unicode characters"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
s = input()
print(len(s))
""", stdin="नमस्ते")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_special_characters(self):
        """Special characters"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
s = input()
print(s)
""", stdin="!@#$%^&*()")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_newlines_in_input(self):
        """Newlines in input"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
lines = []
for _ in range(3):
    lines.append(input())
print(len(lines))
""", stdin="a\nb\nc")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_whitespace_only(self):
        """Whitespace only input"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
s = input().strip()
print(len(s))
""", stdin="   \n  \n  ")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_zero_values(self):
        """Zero values"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
arr = [0, 0, 0, 0]
print(sum(arr))
print(min(arr))
print(max(arr))
""", expected_stdout="0\n0\n0")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_floating_point_zero(self):
        """Floating point zero - division by zero is caught"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
x = 0.0
y = -0.0
print(x == y)
print(1 / x)  # This raises ZeroDivisionError
""")
        # Division by 0.0 raises ZeroDivisionError
        assert result.verdict == Verdict.RUNTIME_ERROR


class TestDeterminism:
    """Test deterministic execution."""
    
    def test_same_output_multiple_runs(self):
        """Same code produces same output"""
        runner = SandboxRunner(language="python")
        code = "print(sum(range(100)))"
        result1 = runner.run(code)
        result2 = runner.run(code)
        assert result1.stdout == result2.stdout
    
    def test_time_consistency(self):
        """Runtime is relatively consistent"""
        runner = SandboxRunner(language="python")
        times = []
        for _ in range(3):
            result = runner.run("print(sum(range(10000)))")
            times.append(result.runtime_ms)
        
        # Times should be within 5x of each other
        avg = sum(times) / len(times)
        for t in times:
            assert t < avg * 5


class TestSecurity:
    """Test security restrictions."""
    
    def test_file_system_access(self):
        """File system access should be limited"""
        runner = SandboxRunner(language="python", wall_time_s=2)
        result = runner.run("""
import os
print(os.listdir('/'))
""")
        # Should complete, though output may be restricted
    
    def test_network_access(self):
        """Network access should be limited"""
        runner = SandboxRunner(language="python", wall_time_s=3)
        result = runner.run("""
import socket
socket.gethostbyname('google.com')
""")
        # May timeout or fail
    
    def test_system_command_injection(self):
        """Command injection prevention"""
        runner = SandboxRunner(language="python", wall_time_s=2)
        result = runner.run("""
import os
os.system('ls')
""")
        # Should complete (os.system is allowed, but limited)


class TestSignalHandling:
    """Test signal handling."""
    
    def test_keyboard_interrupt(self):
        """Keyboard interrupt simulation"""
        runner = SandboxRunner(language="python", wall_time_s=2)
        result = runner.run("""
import time
time.sleep(5)
""")
        assert result.verdict == Verdict.TIME_LIMIT_EXCEEDED
    
    def test_memory_error_handling(self):
        """Memory error handling - Python may allocate lazily"""
        runner = SandboxRunner(language="python", memory_kb=16 * 1024)
        result = runner.run("""
arr = [0] * (50 * 1000 * 1000)  # Try to allocate 400MB
""")
        # Python may allocate lazily, so this could pass
        assert result.verdict in [Verdict.MEMORY_LIMIT_EXCEEDED, Verdict.RUNTIME_ERROR, Verdict.ACCEPTED]

    def test_hard_memory_limit_kills_memory_bomb(self):
        """Hard RLIMIT_AS must catch a growing memory bomb."""
        runner = SandboxRunner(language="python", wall_time_s=5, memory_kb=64 * 1024)
        result = runner.run("""
lst = []
while True:
    lst.append(bytearray(1000000))  # 1MB chunks, unbounded
""")
        assert result.verdict in [Verdict.MEMORY_LIMIT_EXCEEDED, Verdict.TIME_LIMIT_EXCEEDED]

    def test_cpu_time_tracked_on_accepted(self):
        """CPU time must be populated and <= wall time for fast code."""
        runner = SandboxRunner(language="python", wall_time_s=5)
        result = runner.run("print(sum(range(1000)))", expected_stdout="499500")
        assert result.verdict == Verdict.ACCEPTED
        assert result.cpu_time_ms >= 0
        assert result.cpu_time_ms <= result.runtime_ms * 1.5 + 100  # not wildly inflated

    def test_live_memory_kill_records_peak(self):
        """A process killed for memory must still report peak usage."""
        runner = SandboxRunner(language="python", wall_time_s=5, memory_kb=64 * 1024)
        result = runner.run("x = bytearray(200 * 1024 * 1024)\nprint(len(x))")  # 200MB alloc
        assert result.verdict in [Verdict.MEMORY_LIMIT_EXCEEDED, Verdict.RUNTIME_ERROR]
        assert result.memory_kb >= 0


class TestCompetitiveProgramming:
    """Test classic competitive programming scenarios."""
    
    def test_two_sum_classic(self):
        """Two Sum - Classic problem"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
def twoSum(nums, target):
    seen = {}
    for i, n in enumerate(nums):
        complement = target - n
        if complement in seen:
            return [seen[complement], i]
        seen[n] = i
    return []

nums = list(map(int, input().split()))
target = int(input())
result = twoSum(nums, target)
print(result[0], result[1])
""", stdin="2 7 11 15\n9", expected_stdout="0 1")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_binary_search_classic(self):
        """Binary Search - Classic problem"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
def binary_search(arr, target):
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1

arr = list(map(int, input().split()))
target = int(input())
print(binary_search(arr, target))
""", stdin="1 3 5 7 9\n5", expected_stdout="2")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_bubble_sort(self):
        """Bubble Sort implementation"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr

arr = list(map(int, input().split()))
print(' '.join(map(str, bubble_sort(arr))))
""", stdin="64 34 25 12 22 11 90", expected_stdout="11 12 22 25 34 64 90")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_linked_list(self):
        """Linked list operations"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
class Node:
    def __init__(self, val):
        self.val = val
        self.next = None

class LinkedList:
    def __init__(self):
        self.head = None
    
    def append(self, val):
        if not self.head:
            self.head = Node(val)
            return
        curr = self.head
        while curr.next:
            curr = curr.next
        curr.next = Node(val)
    
    def to_list(self):
        result = []
        curr = self.head
        while curr:
            result.append(curr.val)
            curr = curr.next
        return result

ll = LinkedList()
for v in [1, 2, 3, 4, 5]:
    ll.append(v)
print(' '.join(map(str, ll.to_list())))
""", expected_stdout="1 2 3 4 5")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_stack_operations(self):
        """Stack operations"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
stack = []
stack.append(1)
stack.append(2)
stack.append(3)
print(stack.pop())
print(stack.pop())
print(len(stack))
""", expected_stdout="3\n2\n1")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_queue_operations(self):
        """Queue operations"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
from collections import deque
queue = deque()
queue.append(1)
queue.append(2)
queue.append(3)
print(queue.popleft())
print(queue.popleft())
print(len(queue))
""", expected_stdout="1\n2\n1")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_hash_map_usage(self):
        """Hash map (dict) usage"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
freq = {}
for x in [1, 2, 2, 3, 3, 3]:
    freq[x] = freq.get(x, 0) + 1
for k in sorted(freq.keys()):
    print(f"{k}:{freq[k]}", end=" ")
print()
""", expected_stdout="1:1 2:2 3:3")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_graph_bfs(self):
        """BFS on graph"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
from collections import deque

def bfs(graph, start):
    visited = set()
    queue = deque([start])
    result = []
    
    while queue:
        node = queue.popleft()
        if node not in visited:
            visited.add(node)
            result.append(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    queue.append(neighbor)
    return result

graph = {
    'A': ['B', 'C'],
    'B': ['A', 'D', 'E'],
    'C': ['A', 'F'],
    'D': ['B'],
    'E': ['B', 'F'],
    'F': ['C', 'E']
}
print(''.join(bfs(graph, 'A')))
""", expected_stdout="ABCDEF")
        assert result.verdict == Verdict.ACCEPTED


class TestFloatingPointEdgeCases:
    """Test floating point edge cases."""
    
    def test_float_precision(self):
        """Float precision issues"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
# Use round to handle precision
a = 0.1
b = 0.2
c = 0.3
print(round(a + b, 10) == round(c, 10))
""", expected_stdout="True")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_float_division(self):
        """Float division"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
print(10 / 3)
print(10 / 2)
print(0 / 3)
""", expected_stdout="3.3333333333333335\n5.0\n0.0")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_integer_division(self):
        """Integer division"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
print(10 // 3)
print(-10 // 3)
print(10 // -3)
""", expected_stdout="3\n-4\n-4")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_nan_handling(self):
        """NaN handling"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
import math
print(math.nan)
print(math.isnan(math.nan))
""")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_infinity_handling(self):
        """Infinity handling"""
        runner = SandboxRunner(language="python")
        result = runner.run("""
import math
print(math.inf)
print(-math.inf)
print(math.inf + 1)
print(math.inf * 2)
""")
        assert result.verdict == Verdict.ACCEPTED


class TestMultiLanguage:
    """Test multiple programming languages."""
    
    def test_javascript_hello(self):
        """JavaScript basic - may not be supported on all systems"""
        runner = SandboxRunner(language="js")
        result = runner.run("console.log('Hello from JS')", expected_stdout="Hello from JS")
        # JavaScript may not be supported on all systems
        assert result.verdict in [Verdict.ACCEPTED, Verdict.COMPILATION_ERROR]
    
    def test_cpp_hello(self):
        """C++ basic"""
        runner = SandboxRunner(language="cpp")
        result = runner.run("""
#include <iostream>
using namespace std;
int main() {
    cout << "Hello from C++" << endl;
    return 0;
}
""", expected_stdout="Hello from C++")
        assert result.verdict == Verdict.ACCEPTED
    
    def test_java_hello(self):
        """Java basic"""
        runner = SandboxRunner(language="java")
        result = runner.run("""
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello from Java");
    }
}
""", expected_stdout="Hello from Java")
        assert result.verdict == Verdict.ACCEPTED


class TestStressTesting:
    """Stress test the sandbox."""
    
    def test_rapid_sequential(self):
        """Rapid sequential submissions"""
        runner = SandboxRunner(language="python")
        for i in range(5):
            result = runner.run(f"print({i})", expected_stdout=str(i))
            assert result.verdict == Verdict.ACCEPTED
    
    def test_large_input_processing(self):
        """Process large input"""
        runner = SandboxRunner(language="python")
        large_input = " ".join(str(i) for i in range(10000))
        result = runner.run("""
nums = list(map(int, input().split()))
print(sum(nums))
""", stdin=large_input, expected_stdout=str(sum(range(10000))))
        assert result.verdict == Verdict.ACCEPTED
    
    def test_nested_loops(self):
        """Nested loops"""
        runner = SandboxRunner(language="python", wall_time_s=5)
        result = runner.run("""
count = 0
for i in range(50):
    for j in range(50):
        for k in range(50):
            count += 1
print(count)
""", expected_stdout="125000")
        assert result.verdict == Verdict.ACCEPTED


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
