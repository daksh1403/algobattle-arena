#!/usr/bin/env python3
"""
AlgoBattle Sandbox CLI
=====================

Submit and run code directly from the command line.

Usage:
    python cli.py --lang python --code "print('hello')"
    python cli.py --lang python --file solution.py
    python cli.py --lang python --solve two-sum
    python cli.py --interactive
"""

import argparse
import sys
import os
import time
from dataclasses import dataclass
from typing import Optional

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sandbox.sandbox_runner import SandboxRunner, Verdict


@dataclass
class JudgeResult:
    verdict: str
    runtime_ms: float
    memory_kb: int
    details: str


def run_judge(code: str, language: str, test_cases: list[dict], 
              time_limit_s: float = 5, memory_limit_mb: int = 256) -> dict:
    """Judge code against test cases."""
    runner = SandboxRunner(
        language=language,
        wall_time_s=time_limit_s,
        memory_kb=memory_limit_mb * 1024
    )
    
    results = []
    total_time = 0
    all_passed = True
    
    for i, test in enumerate(test_cases):
        stdin = test.get("stdin", "")
        expected = test.get("expected", "").strip()
        
        result = runner.run(code, stdin=stdin, expected_stdout=expected)
        
        status = "✓" if result.verdict == Verdict.ACCEPTED else "✗"
        total_time += result.runtime_ms
        all_passed = all_passed and result.verdict == Verdict.ACCEPTED
        
        results.append({
            "test": i + 1,
            "status": status,
            "verdict": result.verdict.value,
            "runtime_ms": round(result.runtime_ms, 2),
            "stdin": stdin or "(none)",
            "expected": expected or "(none)",
            "actual": result.stdout.strip() if result.stdout else "(none)",
            "error": result.stderr or result.error_detail
        })
    
    return {
        "all_passed": all_passed,
        "total_tests": len(test_cases),
        "passed": sum(1 for r in results if r["status"] == "✓"),
        "total_runtime_ms": round(total_time, 2),
        "results": results
    }


def print_result(result: dict):
    """Pretty print judge result."""
    header = f"""
╔══════════════════════════════════════════════════════════════╗
║                    ALGOBATTLE JUDGE RESULTS                   ║
╠══════════════════════════════════════════════════════════════╣
║  Tests: {result['passed']}/{result['total_tests']} passed                          Total Time: {result['total_runtime_ms']}ms
╚══════════════════════════════════════════════════════════════╝
"""
    print(header)
    
    for r in result["results"]:
        color = "\033[92m" if r["status"] == "✓" else "\033[91m"
        reset = "\033[0m"
        
        verdict_color = {
            "accepted": "\033[92m",
            "wrong_answer": "\033[93m",
            "time_limit_exceeded": "\033[91m",
            "runtime_error": "\033[91m",
        }.get(r["verdict"], "\033[0m")
        
        print(f"""
{r['status']} Test {r['test']}: {r['verdict'].upper()} ({r['runtime_ms']}ms)
  Input:    {r['stdin'][:50]}{'...' if len(r['stdin']) > 50 else ''}
  Expected: {r['expected'][:50]}{'...' if len(r['expected']) > 50 else ''}
  Got:      {r['actual'][:50]}{'...' if len(r['actual']) > 50 else ''}
""")
        if r["error"]:
            print(f"  Error: {r['error'][:100]}")


def interactive_mode():
    """Run interactive REPL for quick testing."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    ALGOBATTLE SANDBOX                        ║
║                                                                ║
║  Commands:                                                    ║
║    :lang <python|cpp|js|java|go|rust>  - Set language        ║
║    :run <code>                        - Execute code          ║
║    :solve <problem>                   - Solve a problem      ║
║    :quit                              - Exit                 ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    language = "python"
    runner = SandboxRunner(language=language, wall_time_s=5)
    
    while True:
        try:
            code = input(f"\n[{language}] > ").strip()
            
            if not code:
                continue
            
            if code == ":quit":
                print("Goodbye!")
                break
            
            if code.startswith(":lang "):
                language = code.split()[1]
                runner = SandboxRunner(language=language, wall_time_s=5)
                print(f"Language set to: {language}")
                continue
            
            if code.startswith(":run "):
                code = code[5:]
            
            result = runner.run(code)
            
            print(f"\n  Verdict: {result.verdict.value}")
            print(f"  Runtime: {result.runtime_ms:.2f}ms")
            print(f"  Output: {result.stdout.strip() or '(none)'}")
            if result.stderr:
                print(f"  Error: {result.stderr}")
            if result.error_detail:
                print(f"  Details: {result.error_detail}")
                
        except KeyboardInterrupt:
            print("\n(Use :quit to exit)")
        except Exception as e:
            print(f"Error: {e}")


def solve_problem(problem: str) -> tuple[str, list[dict]]:
    """Get problem code and test cases."""
    problems = {
        "two-sum": {
            "language": "python",
            "code": """class Solution:
    def twoSum(self, nums, target):
        seen = {}
        for i, n in enumerate(nums):
            complement = target - n
            if complement in seen:
                return [seen[complement], i]
            seen[n] = i
        return []

sol = Solution()
nums = list(map(int, input().split()))
target = int(input())
result = sol.twoSum(nums, target)
print(result[0], result[1])""",
            "tests": [
                {"stdin": "2 7 11 15\n9", "expected": "0 1"},
                {"stdin": "3 2 4\n6", "expected": "1 2"},
                {"stdin": "3 3\n6", "expected": "0 1"},
            ]
        },
        "binary-search": {
            "language": "python",
            "code": """import bisect

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
print(binary_search(arr, target))""",
            "tests": [
                {"stdin": "1 3 5 7 9\n5", "expected": "2"},
                {"stdin": "1 3 5 7 9\n2", "expected": "-1"},
                {"stdin": "1\n1", "expected": "0"},
            ]
        },
        "fibonacci": {
            "language": "python",
            "code": """def fib(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b

n = int(input())
print(fib(n))""",
            "tests": [
                {"stdin": "10", "expected": "55"},
                {"stdin": "20", "expected": "6765"},
                {"stdin": "30", "expected": "832040"},
            ]
        },
        "reverse-string": {
            "language": "python",
            "code": """s = input().strip()
print(s[::-1])""",
            "tests": [
                {"stdin": "hello", "expected": "olleh"},
                {"stdin": "racecar", "expected": "racecar"},
                {"stdin": "world", "expected": "dlrow"},
            ]
        },
        "palindrome": {
            "language": "python",
            "code": """s = input().strip().lower()
print("true" if s == s[::-1] else "false")""",
            "tests": [
                {"stdin": "racecar", "expected": "true"},
                {"stdin": "hello", "expected": "false"},
                {"stdin": "A man a plan a canal Panama", "expected": "true"},
            ]
        },
        "fizzbuzz": {
            "language": "python",
            "code": """n = int(input())
result = []
for i in range(1, n + 1):
    if i % 15 == 0:
        result.append("FizzBuzz")
    elif i % 3 == 0:
        result.append("Fizz")
    elif i % 5 == 0:
        result.append("Buzz")
    else:
        result.append(str(i))
print(" ".join(result))""",
            "tests": [
                {"stdin": "15", "expected": "1 2 Fizz 4 Buzz Fizz 7 8 Fizz Buzz 11 Fizz 13 14 FizzBuzz"},
                {"stdin": "5", "expected": "1 2 Fizz 4 Buzz"},
            ]
        },
    }
    
    return problems.get(problem.lower(), {})


def main():
    parser = argparse.ArgumentParser(
        description="AlgoBattle Sandbox - Run and judge code"
    )
    parser.add_argument("--lang", "-l", default="python",
                       choices=["python", "cpp", "c", "js", "java", "go", "rust"],
                       help="Programming language")
    parser.add_argument("--code", "-c", help="Code to run")
    parser.add_argument("--file", "-f", help="File containing code")
    parser.add_argument("--solve", "-s", help="Solve a problem (two-sum, binary-search, fibonacci, ...)")
    parser.add_argument("--input", "-i", help="Stdin input")
    parser.add_argument("--expected", "-e", help="Expected stdout")
    parser.add_argument("--time", "-t", type=float, default=5, help="Time limit (seconds)")
    parser.add_argument("--interactive", action="store_true", help="Interactive REPL mode")
    parser.add_argument("--problems", action="store_true", help="List available problems")
    
    args = parser.parse_args()
    
    if args.problems:
        print("""
╔══════════════════════════════════════════════════════════════╗
║                    AVAILABLE PROBLEMS                       ║
╠══════════════════════════════════════════════════════════════╣
║  Easy:                                                      ║
║    two-sum          - Find indices that add to target        ║
║    binary-search    - Search in sorted array                 ║
║    fibonacci        - Nth Fibonacci number                  ║
║    reverse-string   - Reverse a string                      ║
║    palindrome       - Check if string is palindrome          ║
║    fizzbuzz         - Classic FizzBuzz problem               ║
╚══════════════════════════════════════════════════════════════╝
""")
        return
    
    if args.interactive:
        interactive_mode()
        return
    
    if args.solve:
        problem = solve_problem(args.solve)
        if not problem:
            print(f"Unknown problem: {args.solve}")
            print("Use --problems to see available problems")
            sys.exit(1)
        
        print(f"\nSolving: {args.solve.upper()}")
        print("=" * 50)
        
        result = run_judge(
            code=problem["code"],
            language=problem["language"],
            test_cases=problem["tests"],
            time_limit_s=args.time
        )
        print_result(result)
        return
    
    # Direct code execution
    if args.file:
        if not os.path.exists(args.file):
            print(f"File not found: {args.file}")
            sys.exit(1)
        with open(args.file) as f:
            code = f.read()
    elif args.code:
        code = args.code
    else:
        print("Error: Provide --code or --file")
        print("Or use --interactive for REPL mode")
        print("Or use --problems to see available problems")
        sys.exit(1)
    
    runner = SandboxRunner(language=args.lang, wall_time_s=args.time)
    result = runner.run(code, stdin=args.input or "", expected_stdout=args.expected or "")
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    EXECUTION RESULT                         ║
╠══════════════════════════════════════════════════════════════╣
║  Language: {args.lang:<47} ║
║  Verdict:  {result.verdict.value:<47} ║
║  Runtime:  {result.runtime_ms:.2f}ms{' ' * 39} ║
╠══════════════════════════════════════════════════════════════╣
║  OUTPUT                                                       ║
║  {result.stdout.strip() or '(no output)'[:53]:<53} ║""")
    
    if result.stderr:
        print(f"║  STDERR: {result.stderr[:47]:<47} ║")
    if result.error_detail:
        print(f"║  ERROR:  {result.error_detail[:47]:<47} ║")
    
    print("╚══════════════════════════════════════════════════════════════╝")
    
    sys.exit(0 if result.verdict == Verdict.ACCEPTED else 1)


if __name__ == "__main__":
    main()
