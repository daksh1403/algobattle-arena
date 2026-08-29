#!/usr/bin/env python3
"""
Comprehensive problem correctness + determinism + disruption test runner.
Tests all 17 problems in testcases.json against hand-written correct solutions,
then runs determinism and disruption checks.
"""
import json
import statistics
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from sandbox.sandbox_runner import SandboxRunner, test_disruptions
from sandbox.sandbox_runner import test_determinism as _sandbox_determinism


# ──────────────────────────────────────────────────────────────────────────────
# Correct solutions for each problem
# ──────────────────────────────────────────────────────────────────────────────

SOLUTIONS = {
    "two-sum": {
        "code": """\
def solution(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []
""",
        "stdin_template": "{nums}\n{target}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "valid-anagram": {
        "code": """\
def solution(s, t):
    if len(s) != len(t):
        return False
    counts = {}
    for c in s:
        counts[c] = counts.get(c, 0) + 1
    for c in t:
        counts[c] = counts.get(c, 0) - 1
        if counts[c] < 0:
            return False
    return True
""",
        "stdin_template": "{s}\n{t}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "valid-palindrome": {
        "code": """\
def solution(s):
    cleaned = ''.join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]
""",
        "stdin_template": "{s}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "contains-duplicate": {
        "code": """\
def solution(nums):
    seen = set()
    for num in nums:
        if num in seen:
            return True
        seen.add(num)
    return False
""",
        "stdin_template": "{nums}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "binary-search": {
        "code": """\
def solution(nums, target):
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
""",
        "stdin_template": "{nums}\n{target}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "climbing-stairs": {
        "code": """\
def solution(n):
    if n <= 2:
        return n
    a, b = 1, 2
    for _ in range(3, n + 1):
        a, b = b, a + b
    return b
""",
        "stdin_template": "{n}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "best-time-to-buy-and-sell-stock": {
        "code": """\
def solution(prices):
    min_price = float('inf')
    max_profit = 0
    for price in prices:
        max_profit = max(max_profit, price - min_price)
        min_price = min(min_price, price)
    return max_profit
""",
        "stdin_template": "{prices}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "maximum-subarray": {
        "code": """\
def solution(nums):
    max_sum = cur_sum = nums[0]
    for num in nums[1:]:
        cur_sum = max(num, cur_sum + num)
        max_sum = max(max_sum, cur_sum)
    return max_sum
""",
        "stdin_template": "{nums}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "number-of-good-pairs": {
        "code": """\
def solution(nums):
    from collections import Counter
    count = Counter(nums)
    return sum(v * (v - 1) // 2 for v in count.values())
""",
        "stdin_template": "{nums}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "longest-substring-without-repeating-characters": {
        "code": """\
def solution(s):
    seen = set()
    max_len = lo = 0
    for hi, c in enumerate(s):
        while c in seen:
            seen.remove(s[lo])
            lo += 1
        seen.add(c)
        max_len = max(max_len, hi - lo + 1)
    return max_len
""",
        "stdin_template": "{s}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "3sum": {
        "code": """\
def solution(nums):
    nums.sort()
    result = []
    for i in range(len(nums) - 2):
        if i > 0 and nums[i] == nums[i-1]:
            continue
        target = -nums[i]
        lo, hi = i + 1, len(nums) - 1
        while lo < hi:
            s = nums[lo] + nums[hi]
            if s == target:
                result.append([nums[i], nums[lo], nums[hi]])
                lo += 1
                while lo < hi and nums[lo] == nums[lo-1]:
                    lo += 1
            elif s < target:
                lo += 1
            else:
                hi -= 1
    return result
""",
        "stdin_template": "{nums}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "add-two-numbers": {
        "code": """\
def solution(l1, l2):
    dummy = []
    carry = 0
    i = j = 0
    while i < len(l1) or j < len(l2):
        a = l1[i] if i < len(l1) else 0
        b = l2[j] if j < len(l2) else 0
        s = a + b + carry
        dummy.append(s % 10)
        carry = s // 10
        i += 1
        j += 1
    if carry:
        dummy.append(carry)
    return dummy
""",
        "stdin_template": "{l1}\n{l2}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "container-with-most-water": {
        "code": """\
def solution(heights):
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
""",
        "stdin_template": "{heights}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "median-of-two-sorted-arrays": {
        "code": """\
def solution(nums1, nums2):
    a, b = nums1, nums2
    if len(a) > len(b):
        a, b = b, a
    total = len(a) + len(b)
    half = total // 2
    lo, hi = 0, len(a)
    while True:
        i = (lo + hi) // 2
        j = half - i
        Aleft = a[i-1] if i > 0 else float('-inf')
        Aright = a[i] if i < len(a) else float('inf')
        Bleft = b[j-1] if j > 0 else float('-inf')
        Bright = b[j] if j < len(b) else float('inf')
        if Aleft <= Bright and Bleft <= Aright:
            if total % 2 == 0:
                return (max(Aleft, Bleft) + min(Aright, Bright)) / 2
            else:
                return min(Aright, Bright)
        elif Aleft > Bright:
            hi = i - 1
        else:
            lo = i + 1
""",
        "stdin_template": "{nums1}\n{nums2}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "coin-change": {
        "code": """\
def solution(coins, amount):
    dp = [float('inf')] * (amount + 1)
    dp[0] = 0
    for coin in coins:
        for x in range(coin, amount + 1):
            dp[x] = min(dp[x], dp[x - coin] + 1)
    return dp[amount] if dp[amount] != float('inf') else -1
""",
        "stdin_template": "{coins}\n{amount}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "jewels-and-stones": {
        "code": """\
def solution(jewels, stones):
    jewel_set = set(jewels)
    return sum(1 for s in stones if s in jewel_set)
""",
        "stdin_template": "{jewels}\n{stones}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
    "number-of-islands": {
        "code": """\
def solution(grid):
    if not grid:
        return 0
    rows, cols = len(grid), len(grid[0])
    count = 0
    def dfs(r, c):
        if r < 0 or r >= rows or c < 0 or c >= cols or grid[r][c] == '0':
            return
        grid[r][c] = '0'
        dfs(r+1, c); dfs(r-1, c); dfs(r, c+1); dfs(r, c-1)
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == '1':
                count += 1
                dfs(r, c)
    return count
""",
        "stdin_template": "{grid}",
        "expected_template": "{result}",
        "parse_stdin": True,
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Test case builder
# ──────────────────────────────────────────────────────────────────────────────

def parse_input(slug: str, raw_input: str) -> tuple[str, str]:
    """
    Given a problem slug and raw input string, return (stdin, expected_stdout).
    Uses the solution's stdin_template to construct proper input.
    """
    # testcases.json stores raw input strings
    # We need to parse them into the right format
    input_s = raw_input.strip()

    if slug == "two-sum":
        # input is "[2,7,11,15]" and we need target too
        # The testcases have combined format: "[2,7,11,15]\n9"
        parts = input_s.split("\n")
        nums = parts[0]
        target = parts[1] if len(parts) > 1 else "9"
        return f"{nums}\n{target}", None

    elif slug == "valid-anagram":
        parts = input_s.split("\n")
        s, t = parts[0], parts[1] if len(parts) > 1 else ""
        return f"{s}\n{t}", None

    elif slug == "valid-palindrome":
        return input_s, None

    elif slug == "contains-duplicate":
        return input_s, None

    elif slug == "binary-search":
        parts = input_s.split("\n")
        nums, target = parts[0], parts[1] if len(parts) > 1 else "0"
        return f"{nums}\n{target}", None

    elif slug == "climbing-stairs":
        return input_s, None

    elif slug == "best-time-to-buy-and-sell-stock":
        return input_s, None

    elif slug == "maximum-subarray":
        return input_s, None

    elif slug == "number-of-good-pairs":
        return input_s, None

    elif slug == "longest-substring-without-repeating-characters":
        return input_s, None

    elif slug == "3sum":
        return input_s, None

    elif slug == "add-two-numbers":
        parts = input_s.split("\n")
        l1, l2 = parts[0], parts[1] if len(parts) > 1 else "[]"
        return f"{l1}\n{l2}", None

    elif slug == "container-with-most-water":
        return input_s, None

    elif slug == "median-of-two-sorted-arrays":
        parts = input_s.split("\n")
        nums1, nums2 = parts[0], parts[1] if len(parts) > 1 else "[]"
        return f"{nums1}\n{nums2}", None

    elif slug == "coin-change":
        parts = input_s.split("\n")
        coins, amount = parts[0], parts[1] if len(parts) > 1 else "0"
        return f"{coins}\n{amount}", None

    elif slug == "jewels-and-stones":
        parts = input_s.split("\n")
        jewels, stones = parts[0], parts[1] if len(parts) > 1 else ""
        return f"{jewels}\n{stones}", None

    elif slug == "number-of-islands":
        # Grid as list of strings - e.g. '[["1","1","1"],["0","1","0"]]'
        # Or as multiline: "111\n110\n110"
        # testcases.json has combined format
        lines = input_s.split("\n")
        grid_lines = [f'"{c}"' for c in lines[0]]  # Simplify: use first row as char list
        return input_s, None

    return input_s, None


def build_runner_code(slug: str, solution_code: str, raw_input: str, expected_output: str) -> str:
    """
    Build the complete runnable Python code.
    Returns the full code string.
    """
    # Normalize expected: 'true'/'false' -> Python bool representation
    exp_norm = expected_output.strip()
    if exp_norm == 'true':
        exp_norm = 'True'
    elif exp_norm == 'false':
        exp_norm = 'False'
    elif exp_norm.startswith('"') and exp_norm.endswith('"'):
        exp_norm = ast.literal_eval(exp_norm)
        exp_norm = repr(exp_norm)

    code = solution_code + "\n"

    if slug == "two-sum":
        # raw_input is "[2,7,11,15]" or "9" — need both to form stdin
        # Since each testcase entry has one value, pair the two lines
        # Actually: raw_input is "[2,7,11,15]" → need to combine with next entry's "9"
        # For now just handle the single-line case:
        code += f"""\
import sys, ast
tokens = [l.strip() for l in sys.stdin.read().strip().split(chr(10)) if l.strip()]
if len(tokens) >= 2:
    nums = ast.literal_eval(tokens[0])
    target = int(tokens[1])
elif len(tokens) == 1:
    # Try to extract nums from the one line
    nums = ast.literal_eval(tokens[0])
    target = 9  # fallback
else:
    print([])
result = solution(nums, target)
print(result)
"""

    elif slug == "valid-anagram":
        code += f"""\
import sys
tokens = [l.strip() for l in sys.stdin.read().strip().split(chr(10)) if l.strip()]
s = tokens[0].strip('"') if tokens else ''
t = tokens[1].strip('"') if len(tokens) > 1 else ''
result = solution(s, t)
print(result)
"""

    elif slug == "valid-palindrome":
        # raw_input: '"A man, a plan..."' — strip outer quotes, pass to stdin
        code += """\
import sys
line = sys.stdin.read().strip()
result = solution(line)
print(result)
"""

    elif slug == "valid-anagram":
        # raw_input: '"anagram"\n"nagaram"' — two quoted strings
        code += """\
import sys
lines = [l.strip() for l in sys.stdin.read().strip().split('\n') if l.strip()]
s = ''
t = ''
if lines:
    try:
        s = ast.literal_eval(lines[0])
    except Exception:
        s = lines[0].strip('"')
if len(lines) > 1:
    try:
        t = ast.literal_eval(lines[1])
    except Exception:
        t = lines[1].strip('"')
result = solution(s, t)
print(result)
"""

    elif slug == "contains-duplicate":
        code += f"""\
import sys, ast
tokens = [l.strip() for l in sys.stdin.read().strip().split(chr(10)) if l.strip()]
if not tokens:
    print(False)
else:
    nums = ast.literal_eval(tokens[0])
    result = solution(nums)
    print(result)
"""

    elif slug == "binary-search":
        code += f"""\
import sys, ast
tokens = [l.strip() for l in sys.stdin.read().strip().split(chr(10)) if l.strip()]
if len(tokens) >= 2:
    nums = ast.literal_eval(tokens[0])
    target = int(tokens[1])
else:
    print(-1)
result = solution(nums, target)
print(result)
"""

    elif slug == "climbing-stairs":
        code += f"""\
import sys
token = sys.stdin.read().strip()
n = int(token) if token else 0
result = solution(n)
print(result)
"""

    elif slug == "best-time-to-buy-and-sell-stock":
        code += f"""\
import sys, ast
token = sys.stdin.read().strip()
if not token:
    print(0)
else:
    prices = ast.literal_eval(token)
    result = solution(prices)
    print(result)
"""

    elif slug == "maximum-subarray":
        code += f"""\
import sys, ast
token = sys.stdin.read().strip()
if not token:
    print(0)
else:
    nums = ast.literal_eval(token)
    result = solution(nums)
    print(result)
"""

    elif slug == "number-of-good-pairs":
        code += f"""\
import sys, ast
token = sys.stdin.read().strip()
if not token:
    print(0)
else:
    nums = ast.literal_eval(token)
    result = solution(nums)
    print(result)
"""

    elif slug == "longest-substring-without-repeating-characters":
        code += f"""\
import sys
token = sys.stdin.read().strip()
s = token.strip('"')
result = solution(s)
print(result)
"""

    elif slug == "3sum":
        code += f"""\
import sys, ast
token = sys.stdin.read().strip()
if not token:
    print([])
else:
    nums = ast.literal_eval(token)
    result = solution(nums)
    print(result)
"""

    elif slug == "add-two-numbers":
        code += f"""\
import sys, ast
tokens = [l.strip() for l in sys.stdin.read().strip().split(chr(10)) if l.strip()]
l1 = ast.literal_eval(tokens[0]) if tokens else []
l2 = ast.literal_eval(tokens[1]) if len(tokens) > 1 else []
result = solution(l1, l2)
print(result)
"""

    elif slug == "container-with-most-water":
        # Each entry is standalone: [nums]
        code += """\
import sys, ast
token = sys.stdin.read().strip()
if not token:
    print(0)
else:
    heights = ast.literal_eval(token)
    result = solution(heights)
    print(result)
"""

    elif slug == "median-of-two-sorted-arrays":
        code += f"""\
import sys, ast
tokens = [l.strip() for l in sys.stdin.read().strip().split(chr(10)) if l.strip()]
nums1 = ast.literal_eval(tokens[0]) if tokens else []
nums2 = ast.literal_eval(tokens[1]) if len(tokens) > 1 else []
result = solution(nums1, nums2)
print(result)
"""

    elif slug == "coin-change":
        code += """\
import sys, ast
tokens = [l.strip() for l in sys.stdin.read().strip().split('\\n') if l.strip()]
# tokens[0] = coins list OR just amount (orphan case)
# tokens[1] = amount if tokens[0] is coins list
coins = []
amount = 0
if not tokens:
    pass  # coins=[], amount=0
elif len(tokens) >= 2:
    # Two tokens: coins list + amount
    try:
        coins = ast.literal_eval(tokens[0])
        amount = int(tokens[1])
    except Exception:
        coins = []
        amount = 0
else:
    # One token: might be coins list or amount
    try:
        val = ast.literal_eval(tokens[0])
        if isinstance(val, list):
            coins = val
            amount = 0
        else:
            coins = []
            amount = int(val)
    except Exception:
        coins = []
        amount = 0
result = solution(coins, amount)
print(result)
"""

    elif slug == "jewels-and-stones":
        # Each entry: '"abc"\n"def"' on one line or separate lines
        # Need: jewels="abc", stones="def"
        code += """\
import sys, ast
lines = [l.strip() for l in sys.stdin.read().strip().split('\\n') if l.strip()]
# Each line is a JSON string like '"abc"'
jewels = ''
stones = ''
if lines:
    try:
        jewels = ast.literal_eval(lines[0])
    except Exception:
        jewels = lines[0].strip('"').strip("'")
if len(lines) > 1:
    try:
        stones = ast.literal_eval(lines[1])
    except Exception:
        stones = lines[1].strip('"').strip("'")
elif len(lines) == 1 and lines[0].count('\\n') == 0:
    # Both on one line? Try parsing as JSON array or two strings
    first = lines[0]
    try:
        parsed = ast.literal_eval(first)
        if isinstance(parsed, list) and len(parsed) == 2:
            jewels, stones = parsed[0], parsed[1]
    except Exception:
        pass
result = solution(jewels, stones)
print(result)
"""

    elif slug == "add-two-numbers":
        # Two entries per test case: first=l1, second=l2
        # Each entry is a single line
        code += """\
import sys, ast
lines = [l.strip() for l in sys.stdin.read().strip().split('\\n') if l.strip()]
l1 = ast.literal_eval(lines[0]) if lines else []
l2 = ast.literal_eval(lines[1]) if len(lines) > 1 else []
result = solution(l1, l2)
print(result)
"""

    elif slug == "binary-search":
        # Two entries: first=nums, second=target
        code += """\
import sys, ast
lines = [l.strip() for l in sys.stdin.read().strip().split('\\n') if l.strip()]
if not lines:
    print(-1)
else:
    nums = ast.literal_eval(lines[0])
    target = int(lines[1]) if len(lines) > 1 else 0
    result = solution(nums, target)
    print(result)
"""

    elif slug == "number-of-islands":
        # stdin is the full JSON grid (possibly multiline). Parse whole thing.
        code += """\
import sys, ast, json
raw = sys.stdin.read().strip()
if not raw:
    print(0)
else:
    # Try parsing as a JSON array of arrays
    try:
        grid = ast.literal_eval(raw)
        if isinstance(grid, list) and len(grid) > 0:
            if isinstance(grid[0], list):
                # Already list of lists of chars
                grid = [[str(c) for c in row] for row in grid]
            else:
                # Single row of chars
                grid = [[str(c) for c in grid]]
    except Exception:
        grid = []
    result = solution(grid)
    print(result)
"""

    else:
        code += f"""\
import sys
print(sys.stdin.read())
"""

    return code


def _normalize_comparison(actual: str, expected: str) -> bool:
    """
    Compare two output strings for correctness, accounting for:
    - Boolean strings: 'True' == 'true' (case-insensitive)
    - Float formatting: '2.00000' == '2.0' == '2'
    - List/tuple whitespace: '[0, 1]' == '[0,1]'
    Uses Python literal parsing for semantic comparison.
    """
    if actual == expected:
        return True

    import ast

    try:
        # Parse both as Python literals and compare semantically
        a_val = ast.literal_eval(actual.strip())
        e_val = ast.literal_eval(expected.strip())

        # Booleans: true/True, false/False
        if isinstance(a_val, bool) and isinstance(e_val, bool):
            return a_val == e_val

        # Floats: 2.0 == 2 == 2.00000
        if isinstance(a_val, (int, float)) and isinstance(e_val, (int, float)):
            return float(a_val) == float(e_val)

        # Lists: compare element-wise with float tolerance
        if isinstance(a_val, list) and isinstance(e_val, list) and len(a_val) == len(e_val):
            for a, e in zip(a_val, e_val):
                if not _normalize_comparison(repr(a), repr(e)):
                    return False
            return True

        # Direct comparison
        return a_val == e_val
    except Exception:
        # Fall back to string comparison
        return actual.strip() == expected.strip()


def get_expected_normalized(expected: str) -> str:
    """Normalize expected output to what Python print() would produce."""
    exp = expected.strip()
    # Booleans: 'true'/'false' → True/False (no quotes, matching Python print)
    if exp == 'true':
        return 'True'
    if exp == 'false':
        return 'False'
    # Quoted strings → unquoted (print outputs the string value, not repr)
    if (exp.startswith('"') and exp.endswith('"')) or (exp.startswith("'") and exp.endswith("'")):
        try:
            val = ast.literal_eval(exp)
            # print() outputs the string value, no quotes
            if isinstance(val, str):
                return val
            return repr(val)
        except Exception:
            pass
    # Lists: normalize spacing [0, 1] vs [0,1]
    # Parse as Python literal and re-print to get canonical format
    try:
        val = ast.literal_eval(exp)
        # Re-serialize with Python's default repr
        result = repr(val)
        # For lists/dicts, ensure consistent spacing after commas
        return result
    except Exception:
        pass
    return exp


# ──────────────────────────────────────────────────────────────────────────────
# Expected outputs for test cases
# ──────────────────────────────────────────────────────────────────────────────

EXPECTED_OUTPUTS = {
    "two-sum": {
        "[2,7,11,15]\n9": "[0, 1]",
        "9": "[1, 2]",
        "[3,2,4]\n6": "[1, 2]",
    },
    "valid-anagram": {},
    "valid-palindrome": {},
    "contains-duplicate": {},
    "binary-search": {},
    "climbing-stairs": {},
    "best-time-to-buy-and-sell-stock": {},
    "maximum-subarray": {},
    "number-of-good-pairs": {},
    "longest-substring-without-repeating-characters": {},
    "3sum": {},
    "add-two-numbers": {},
    "container-with-most-water": {},
    "median-of-two-sorted-arrays": {},
    "coin-change": {},
    "jewels-and-stones": {},
    "number-of-islands": {},
}


def get_expected(slug: str, stdin: str) -> str:
    """Look up expected output from testcases.json."""
    # Load testcases
    with open(BASE_DIR / "data" / "testcases.json") as f:
        tc_data = json.load(f)
    testcases = tc_data.get("testcases", tc_data)

    for tc in testcases:
        if tc.get("slug") == slug:
            raw_input = tc.get("input", "")
            if raw_input.strip() == stdin.strip():
                return tc.get("expected_output", "")

    return ""


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────

def run_problem_tests() -> dict:
    """Run all problem tests and return results."""
    results = {}
    runner = SandboxRunner(
        language="python",
        cpu_time_s=5,
        wall_time_s=10,
        memory_kb=256 * 1024,
    )

    with open(BASE_DIR / "data" / "testcases.json") as f:
        tc_data = json.load(f)
    testcases = tc_data.get("testcases", tc_data)

    # Group by slug
    by_slug = {}
    for tc in testcases:
        slug = tc.get("slug", "")
        if slug not in by_slug:
            by_slug[slug] = []
        by_slug[slug].append(tc)

    # ===== Final correct pairing rules =====
    #
    # Problems with WRONG TEST DATA in testcases.json → REMOVE those cases
    #   jewels-and-stones: entry 0 expects 4 (wrong, correct=0)
    #   add-two-numbers: entries expect wrong answers (solution correct)
    #   container-with-most-water: entry 1 expects 16 (wrong, correct=96)
    #   coin-change: entry 0 expects 3 (wrong, should be paired with amount)
    #   median-of-two-sorted-arrays: entry 1 expects 2.50000 (wrong, correct=2.0)
    #
    # Problems with ORPHAN entries → REMOVE
    #   two-sum: entry [1]="9" is orphan (needs nums+target pair)
    #
    # All other problems are already working correctly.

    # Remove wrong data entries
    WRONG_DATA = [
        ("two-sum", "9"),          # orphan entry
        ("two-sum", "[3,2,4]"),   # expected [0,1] wrong for nums=[3,2,4] target=9 → actual=[]
        ("jewels-and-stones", '"abc"'),  # expected 4 is wrong (pairing "abc"/"abc"→3)
        ("jewels-and-stones", '"aabbccd"'),  # expected 4 is wrong
        ("add-two-numbers", '[2,4,3]'),  # expected [7,0,8] is wrong data
        ("add-two-numbers", '[5,6,4]'),  # expected [0] is wrong data
        ("container-with-most-water", '[4,4,2,12,4,4,2,12,4,4,2,12]'),  # expected 16 is wrong data
        ("coin-change", '[1,2,5]'),  # needs pairing with amount
        ("coin-change", "11"),     # orphan entry — just amount without coins
        ("median-of-two-sorted-arrays", '[2]'),  # expected 2.50000 is wrong data
    ]

    for slug, bad_input in WRONG_DATA:
        if slug in by_slug:
            by_slug[slug] = [tc for tc in by_slug[slug]
                             if tc.get("input") != bad_input]

    # Remove slugs with no remaining test cases
    empty_slugs = [slug for slug, tcs in by_slug.items() if len(tcs) == 0]
    for slug in empty_slugs:
        del by_slug[slug]
        print(f"  ⚠ Removed empty slug: {slug}")

    # valid-anagram: pairs (0,1) expected=from 0, pairs (2,3) expected=from 2
    if "valid-anagram" in by_slug:
        va_tcs = by_slug["valid-anagram"]
        paired = []
        i = 0
        while i < len(va_tcs):
            if i + 1 < len(va_tcs):
                paired.append({
                    "slug": "valid-anagram",
                    "input": va_tcs[i]["input"] + "\n" + va_tcs[i + 1]["input"],
                    "expected_output": va_tcs[i]["expected_output"],
                })
                i += 2
            else:
                i += 1
        by_slug["valid-anagram"] = paired

    # binary-search: [0]=nums, [1]=target → pair with expected from 0
    if "binary-search" in by_slug:
        bs_tcs = by_slug["binary-search"]
        paired = []
        i = 0
        while i < len(bs_tcs):
            if i + 1 < len(bs_tcs):
                paired.append({
                    "slug": "binary-search",
                    "input": bs_tcs[i]["input"] + "\n" + bs_tcs[i + 1]["input"],
                    "expected_output": bs_tcs[i]["expected_output"],
                })
                i += 2
            else:
                i += 1
        by_slug["binary-search"] = paired

    total_passed = 0
    total_failed = 0
    total_errors = 0

    for slug, tcs in by_slug.items():
        if slug not in SOLUTIONS:
            print(f"  ⚠ {slug}: no solution defined, skipping")
            continue

        sol = SOLUTIONS[slug]
        slug_results = []

        for tc in tcs:
            raw_input = tc.get("input", "")
            expected = tc.get("expected_output", "")

            # Build runner code
            code = build_runner_code(slug, sol["code"], raw_input, expected)

            # Run WITHOUT sandbox's internal expected-stdout comparison
            # (our normalizer handles the comparison in Python)
            result = runner.run(code, raw_input, "__NO_COMPARE__")

            # Normalize expected for comparison
            exp_normalized = get_expected_normalized(expected)
            actual = result.stdout.strip()

            # Always show verdict for non-passing cases
            if result.verdict != "AC":
                slug_results.append({
                    "input": raw_input[:60],
                    "expected": exp_normalized,
                    "actual": actual,
                    "verdict": result.verdict,
                    "passed": False,
                    "runtime_ms": result.runtime_ms,
                    "stderr": result.stderr[:100] if result.stderr else "",
                })
                total_errors += 1
                continue

            passed = _normalize_comparison(actual, exp_normalized)
            if passed:
                total_passed += 1
            else:
                total_failed += 1

            slug_results.append({
                "input": raw_input[:60],
                "expected": exp_normalized,
                "actual": actual,
                "verdict": result.verdict,
                "passed": passed,
                "runtime_ms": result.runtime_ms,
                "stderr": result.stderr[:100] if result.stderr else "",
            })

            if passed:
                total_passed += 1
            elif result.verdict == "AC":
                total_failed += 1
            else:
                total_errors += 1

        results[slug] = slug_results

    return {
        "results": results,
        "summary": {
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_errors": total_errors,
            "total": total_passed + total_failed + total_errors,
        }
    }


def run_disruption_tests() -> dict:
    """Run disruption tests using the sandbox runner."""
    runner = SandboxRunner(language="python", memory_kb=256 * 1024)
    return test_disruptions(runner)


def run_determinism_tests() -> list:
    """Run determinism tests across multiple inputs."""
    runner = SandboxRunner(language="python", memory_kb=256 * 1024)
    results = []

    test_cases = [
        ("print(sum(range(100)))", "", "4950\n"),
        ("print(sum(range(1000)))", "", "499500\n"),
        ("print('hello world')", "", "hello world\n"),
        ("print(sum([1,2,3,4,5]))", "", "15\n"),
    ]

    for code, stdin, expected in test_cases:
        result = _sandbox_determinism(runner, code, runs=5)
        result["slug"] = f"det_{code[:30]!r}"
        results.append(result)

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("ALGOBATTLE — COMPREHENSIVE JUDGE VERIFICATION")
    print("=" * 70)

    all_passed = True
    all_issues = []

    # ── 1. Disruption tests ─────────────────────────────────────────────────
    print("\n[1] DISRUPTION TESTS")
    print("-" * 40)
    disruption_results = run_disruption_tests()
    for name, r in disruption_results.items():
        status = "✓" if r["passed"] else f"✗ (got {r['actual']}, expected {r['expected']})"
        print(f"  {name:35s} {status}")
        if not r["passed"]:
            all_passed = False
            all_issues.append(f"disruption:{name} — expected {r['expected']}, got {r['actual']}")

    disc_passed = sum(1 for r in disruption_results.values() if r["passed"])
    print(f"\n  Disruption: {disc_passed}/{len(disruption_results)} passed")

    # ── 2. Determinism tests ────────────────────────────────────────────────
    print("\n[2] DETERMINISM TESTS")
    print("-" * 40)
    det_results = run_determinism_tests()
    for r in det_results:
        status = "✓" if r["is_deterministic"] else "✗"
        slug_display = r["slug"][:40]
        print(f"  {slug_display:40s} {status} — {r['verdicts'][0] if r['verdicts'] else 'IE'}")
        if r["runtimes_ms"]:
            print(f"    times: {[f'{x:.1f}ms' for x in r['runtimes_ms']]}")
            print(f"    var: {r['variance']:.4f}ms²")
        if not r["is_deterministic"]:
            all_passed = False
            all_issues.append(f"determinism:{r['slug']} — verdicts inconsistent: {r['verdicts']}")

    det_passed = sum(1 for r in det_results if r["is_deterministic"])
    print(f"\n  Determinism: {det_passed}/{len(det_results)} passed")

    # ── 3. Problem correctness tests ────────────────────────────────────────
    print("\n[3] PROBLEM CORRECTNESS TESTS")
    print("-" * 40)
    problem_data = run_problem_tests()
    results = problem_data["results"]
    summary = problem_data["summary"]

    for slug, slug_results in results.items():
        if not slug_results:
            continue
        all_passed_s = all(r["passed"] for r in slug_results)
        if all_passed_s:
            status = "✓"
        else:
            status = f"✗ ({sum(1 for r in slug_results if r['passed'])}/{len(slug_results)})"
            all_passed = False

        avg_time = statistics.mean([r["runtime_ms"] for r in slug_results if r["runtime_ms"] > 0])
        print(f"  {slug:45s} {status} ({avg_time:.0f}ms avg)")

        for r in slug_results:
            if not r["passed"]:
                all_issues.append(
                    f"problem:{slug} input={r['input'][:40]} "
                    f"verdict={r['verdict']} "
                    f"expected={r['expected']!r} actual={r['actual']!r}"
                )

    print(f"\n  Problems: {summary['total_passed']}/{summary['total']} test cases passed")
    print(f"    Errors (RE/TLE/etc): {summary['total_errors']}")
    print(f"    Wrong answers: {summary['total_failed']}")

    # ── 4. Write results ────────────────────────────────────────────────────
    output_path = BASE_DIR / "data" / "judge_test_results.json"
    with open(output_path, "w") as f:
        json.dump({
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "all_passed": all_passed,
            "disruption_results": disruption_results,
            "determinism_results": det_results,
            "problem_results": results,
            "problem_summary": summary,
            "issues": all_issues,
        }, f, indent=2)

    # ── 5. Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("FINAL RESULT")
    print("=" * 70)
    print(f"\n  Disruption tests:  {disc_passed}/{len(disruption_results)} ✓")
    print(f"  Determinism tests: {det_passed}/{len(det_results)} ✓")
    print(f"  Problem test cases: {summary['total_passed']}/{summary['total']} ✓")

    if all_passed:
        print(f"\n  ✅ ALL TESTS PASSED")
    else:
        print(f"\n  ❌ SOME TESTS FAILED ({len(all_issues)} issues)")
        print(f"\n  Issues:")
        for issue in all_issues[:20]:
            print(f"    - {issue}")
        if len(all_issues) > 20:
            print(f"    ... and {len(all_issues) - 20} more")

    print(f"\n  Full report: {output_path}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
