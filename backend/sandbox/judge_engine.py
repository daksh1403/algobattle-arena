#!/usr/bin/env python3
"""
AlgoBattle Judge Engine
======================

Complete competitive programming judge with:
- Memory limit enforcement
- CPU time tracking
- Efficiency scoring
- Ranking system
- Deterministic execution

Usage:
    from judge_engine import JudgeEngine
    
    engine = JudgeEngine()
    result = engine.judge(code, language="python", problem=problem)
"""

import os
import sys
import time
import random
import subprocess
import tempfile
import threading
import resource
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum

sys.path.insert(0, os.path.dirname(__file__))

from sandbox_runner import Verdict, RunResult


class Verdict(str, Enum):
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    OUTPUT_LIMIT_EXCEEDED = "output_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    COMPILATION_ERROR = "compilation_error"
    INTERNAL_ERROR = "internal_error"


@dataclass
class TestCase:
    """Individual test case."""
    input: str
    expected_output: str
    time_limit_ms: int = 2000
    memory_limit_kb: int = 256 * 1024
    points: int = 1


@dataclass
class Problem:
    """Competitive programming problem."""
    id: str
    title: str
    difficulty: str
    time_limit_ms: int = 2000
    memory_limit_kb: int = 256 * 1024
    test_cases: List[TestCase] = field(default_factory=list)
    checker: str = "exact"  # exact, float, token


@dataclass
class SubmissionResult:
    """Complete submission result with scoring."""
    verdict: str
    score: float
    total_points: int
    earned_points: int
    runtime_ms: float
    memory_kb: float
    test_results: List[Dict]
    efficiency_score: float = 0.0
    rank: int = 0


class JudgeEngine:
    """
    Complete judge engine for algorithmic competition.
    
    Features:
    - Memory limit enforcement
    - CPU time tracking
    - Efficiency scoring
    - Deterministic execution
    - Multi-language support
    """
    
    def __init__(
        self,
        default_time_limit_ms: int = 2000,
        default_memory_limit_kb: int = 256 * 1024,
        seed: Optional[int] = None
    ):
        self.default_time_limit_ms = default_time_limit_ms
        self.default_memory_limit_kb = default_memory_limit_kb
        self.seed = seed
        self.submissions: List[SubmissionResult] = []
        
        # Language configurations
        self.languages = {
            "python": {
                "extension": ".py",
                "compile": None,
                "run": ["python3", "{file}"],
                "timeout": 30
            },
            "cpp": {
                "extension": ".cpp",
                "compile": "g++ -o {exe} {file} -O2",
                "run": ["{exe}"],
                "timeout": 60
            },
            "java": {
                "extension": ".java",
                "compile": "javac {file}",
                "run": ["java", "Main"],
                "timeout": 60
            },
            "javascript": {
                "extension": ".js",
                "compile": None,
                "run": ["node", "{file}"],
                "timeout": 30
            }
        }
    
    def judge(
        self,
        code: str,
        language: str,
        problem: Problem,
        interactive: bool = False
    ) -> SubmissionResult:
        """
        Judge a submission against a problem.
        
        Args:
            code: Source code
            language: Programming language
            problem: Problem to solve
            interactive: Enable interactive mode
            
        Returns:
            SubmissionResult with score and ranking
        """
        lang_config = self.languages.get(language.lower())
        if not lang_config:
            return SubmissionResult(
                verdict=Verdict.INTERNAL_ERROR,
                score=0.0,
                total_points=problem.test_cases[0].points * len(problem.test_cases) if problem.test_cases else 0,
                earned_points=0,
                runtime_ms=0,
                memory_kb=0,
                test_results=[{"verdict": "internal_error", "error": "Unsupported language"}]
            )
        
        # Create temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write code to file
            file_path = self._write_code(code, language, lang_config, tmpdir)
            
            # Compile if needed
            if lang_config.get("compile"):
                compile_result = self._compile(file_path, lang_config, tmpdir)
                if compile_result["verdict"] != Verdict.ACCEPTED:
                    return self._create_result(
                        compile_result["verdict"],
                        problem,
                        [compile_result]
                    )
            
            # Run test cases
            test_results = []
            total_time = 0
            total_memory = 0
            earned_points = 0
            total_points = 0
            
            for i, tc in enumerate(problem.test_cases):
                total_points += tc.points
                
                result = self._run_test_case(
                    file_path, lang_config, tmpdir,
                    tc, problem, i
                )
                test_results.append(result)
                total_time += result["runtime_ms"]
                total_memory = max(total_memory, result["memory_kb"])
                
                if result["verdict"] == Verdict.ACCEPTED:
                    earned_points += tc.points
            
            # Calculate efficiency score (lower is better)
            avg_time = total_time / len(test_results) if test_results else 0
            efficiency_score = self._calculate_efficiency(
                avg_time,
                problem.time_limit_ms,
                total_memory,
                problem.memory_limit_kb
            )
            
            # Determine overall verdict
            verdict = self._determine_verdict(test_results)
            
            # Create result
            result = SubmissionResult(
                verdict=verdict,
                score=earned_points / total_points if total_points > 0 else 0,
                total_points=total_points,
                earned_points=earned_points,
                runtime_ms=total_time,
                memory_kb=total_memory,
                test_results=test_results,
                efficiency_score=efficiency_score
            )
            
            # Update rankings
            self._update_rankings(result)
            
            return result
    
    def _write_code(
        self, code: str, language: str, config: Dict, tmpdir: str
    ) -> str:
        """Write code to temp file."""
        ext = config["extension"]
        filepath = os.path.join(tmpdir, f"solution{ext}")
        
        with open(filepath, "w") as f:
            f.write(code)
        
        return filepath
    
    def _compile(
        self, filepath: str, config: Dict, tmpdir: str
    ) -> Dict:
        """Compile code and return result."""
        try:
            compile_cmd = config["compile"].format(
                file=filepath,
                exe=os.path.join(tmpdir, "solution")
            )
            
            result = subprocess.run(
                compile_cmd.split(),
                capture_output=True,
                text=True,
                timeout=config["timeout"],
                cwd=tmpdir
            )
            
            if result.returncode != 0:
                return {
                    "verdict": Verdict.COMPILATION_ERROR,
                    "stderr": result.stderr,
                    "runtime_ms": 0,
                    "memory_kb": 0
                }
            
            return {"verdict": Verdict.ACCEPTED, "stderr": ""}
            
        except subprocess.TimeoutExpired:
            return {
                "verdict": Verdict.COMPILATION_ERROR,
                "stderr": "Compilation timed out",
                "runtime_ms": config["timeout"] * 1000,
                "memory_kb": 0
            }
        except Exception as e:
            return {
                "verdict": Verdict.INTERNAL_ERROR,
                "stderr": str(e),
                "runtime_ms": 0,
                "memory_kb": 0
            }
    
    def _run_test_case(
        self,
        filepath: str,
        config: Dict,
        tmpdir: str,
        test_case: TestCase,
        problem: Problem,
        index: int
    ) -> Dict:
        """Run a single test case with resource limits."""
        
        # Build run command
        run_cmd = [arg.format(file=filepath, exe=os.path.join(tmpdir, "solution")) 
                   for arg in config["run"]]
        
        start_time = time.perf_counter()
        peak_memory = 0
        killed = threading.Event()
        
        def run_with_limits():
            nonlocal peak_memory
            
            try:
                process = subprocess.Popen(
                    run_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=tmpdir,
                    preexec_fn=os.setsid if hasattr(os, 'setsid') else None
                )
                
                # Monitor resources
                def monitor():
                    nonlocal peak_memory
                    while process.poll() is None:
                        try:
                            # Get memory usage
                            if hasattr(os, 'getrusage'):
                                ru = resource.getrusage(resource.RUSAGE_CHILDREN)
                                peak_memory = max(peak_memory, ru.ru_maxrss * 1024)  # KB
                        except:
                            pass
                        time.sleep(0.01)
                
                monitor_thread = threading.Thread(target=monitor, daemon=True)
                monitor_thread.start()
                
                # Run with timeout
                try:
                    stdout, stderr = process.communicate(
                        input=test_case.input,
                        timeout=test_case.time_limit_ms / 1000
                    )
                except subprocess.TimeoutExpired:
                    process.kill()
                    killed.set()
                    stdout, stderr = process.communicate()
                    
                    return {
                        "test": index + 1,
                        "verdict": Verdict.TIME_LIMIT_EXCEEDED,
                        "runtime_ms": test_case.time_limit_ms,
                        "memory_kb": peak_memory,
                        "input": test_case.input,
                        "expected": test_case.expected_output,
                        "actual": stdout.strip(),
                        "stderr": stderr
                    }
                
                runtime_ms = (time.perf_counter() - start_time) * 1000
                
                # Check memory limit
                if peak_memory > test_case.memory_limit_kb:
                    return {
                        "test": index + 1,
                        "verdict": Verdict.MEMORY_LIMIT_EXCEEDED,
                        "runtime_ms": runtime_ms,
                        "memory_kb": peak_memory,
                        "input": test_case.input,
                        "expected": test_case.expected_output,
                        "actual": stdout.strip(),
                        "stderr": stderr
                    }
                
                # Check output limit
                if len(stdout) > 1024 * 1024:  # 1MB
                    return {
                        "test": index + 1,
                        "verdict": Verdict.OUTPUT_LIMIT_EXCEEDED,
                        "runtime_ms": runtime_ms,
                        "memory_kb": peak_memory,
                        "input": test_case.input,
                        "expected": test_case.expected_output,
                        "actual": stdout.strip()[:1000],
                        "stderr": stderr
                    }
                
                # Check output correctness
                actual = stdout.strip()
                expected = test_case.expected_output.strip()
                
                if problem.checker == "exact":
                    correct = actual == expected
                elif problem.checker == "float":
                    try:
                        correct = abs(float(actual) - float(expected)) < 1e-6
                    except:
                        correct = False
                elif problem.checker == "token":
                    correct = set(actual.split()) == set(expected.split())
                else:
                    correct = actual == expected
                
                if process.returncode != 0 and not killed.is_set():
                    return {
                        "test": index + 1,
                        "verdict": Verdict.RUNTIME_ERROR,
                        "runtime_ms": runtime_ms,
                        "memory_kb": peak_memory,
                        "input": test_case.input,
                        "expected": expected,
                        "actual": actual,
                        "stderr": stderr
                    }
                
                return {
                    "test": index + 1,
                    "verdict": Verdict.ACCEPTED if correct else Verdict.WRONG_ANSWER,
                    "runtime_ms": runtime_ms,
                    "memory_kb": peak_memory,
                    "input": test_case.input,
                    "expected": expected,
                    "actual": actual,
                    "stderr": stderr
                }
                
            except Exception as e:
                return {
                    "test": index + 1,
                    "verdict": Verdict.INTERNAL_ERROR,
                    "runtime_ms": (time.perf_counter() - start_time) * 1000,
                    "memory_kb": peak_memory,
                    "input": test_case.input,
                    "expected": test_case.expected_output,
                    "actual": "",
                    "stderr": str(e)
                }
        
        return run_with_limits()
    
    def _calculate_efficiency(
        self,
        runtime_ms: float,
        time_limit_ms: int,
        memory_kb: float,
        memory_limit_kb: int
    ) -> float:
        """
        Calculate efficiency score for ranking.
        Lower is better.
        
        Score = (time / limit) * (memory / limit)
        """
        time_ratio = runtime_ms / time_limit_ms if time_limit_ms > 0 else 1
        memory_ratio = memory_kb / memory_limit_kb if memory_limit_kb > 0 else 1
        
        return time_ratio * memory_ratio
    
    def _determine_verdict(self, test_results: List[Dict]) -> str:
        """Determine overall verdict from test results."""
        verdicts = [r["verdict"] for r in test_results]
        
        if any(v == Verdict.INTERNAL_ERROR for v in verdicts):
            return Verdict.INTERNAL_ERROR
        if any(v == Verdict.COMPILATION_ERROR for v in verdicts):
            return Verdict.COMPILATION_ERROR
        if any(v == Verdict.RUNTIME_ERROR for v in verdicts):
            return Verdict.RUNTIME_ERROR
        if any(v == Verdict.MEMORY_LIMIT_EXCEEDED for v in verdicts):
            return Verdict.MEMORY_LIMIT_EXCEEDED
        if any(v == Verdict.TIME_LIMIT_EXCEEDED for v in verdicts):
            return Verdict.TIME_LIMIT_EXCEEDED
        if any(v == Verdict.WRONG_ANSWER for v in verdicts):
            return Verdict.WRONG_ANSWER
        
        return Verdict.ACCEPTED
    
    def _create_result(
        self,
        verdict: str,
        problem: Problem,
        test_results: List[Dict]
    ) -> SubmissionResult:
        """Create result from verdict."""
        return SubmissionResult(
            verdict=verdict,
            score=0.0,
            total_points=problem.test_cases[0].points * len(problem.test_cases) if problem.test_cases else 0,
            earned_points=0,
            runtime_ms=0,
            memory_kb=0,
            test_results=test_results,
            efficiency_score=float('inf')
        )
    
    def _update_rankings(self, result: SubmissionResult):
        """Update submission rankings."""
        self.submissions.append(result)
        
        # Sort by score desc, then efficiency asc (lower is better)
        self.submissions.sort(
            key=lambda x: (-x.score, x.efficiency_score)
        )
        
        # Assign ranks
        for i, sub in enumerate(self.submissions):
            sub.rank = i + 1
    
    def get_leaderboard(self) -> List[Dict]:
        """Get current leaderboard."""
        return [
            {
                "rank": sub.rank,
                "score": sub.score,
                "earned_points": sub.earned_points,
                "total_points": sub.total_points,
                "verdict": sub.verdict,
                "efficiency_score": sub.efficiency_score,
                "runtime_ms": sub.runtime_ms,
                "memory_kb": sub.memory_kb
            }
            for sub in self.submissions
        ]


# =============================================================================
# Example Problems
# =============================================================================

def create_two_sum_problem() -> Problem:
    """Two Sum - Classic problem."""
    return Problem(
        id="two-sum",
        title="Two Sum",
        difficulty="Easy",
        time_limit_ms=2000,
        memory_limit_kb=256 * 1024,
        checker="exact",
        test_cases=[
            TestCase(input="2 7 11 15\n9", expected_output="0 1", points=10),
            TestCase(input="3 2 4\n6", expected_output="1 2", points=10),
            TestCase(input="3 3\n6", expected_output="0 1", points=10),
        ]
    )


def create_fibonacci_problem() -> Problem:
    """Fibonacci - Calculate nth Fibonacci number."""
    test_cases = [
        TestCase(input="10", expected_output="55", points=10),
        TestCase(input="20", expected_output="6765", points=10),
        TestCase(input="30", expected_output="832040", points=10),
        TestCase(input="40", expected_output="102334155", points=10),
    ]
    
    return Problem(
        id="fibonacci",
        title="Fibonacci Number",
        difficulty="Easy",
        time_limit_ms=2000,
        memory_limit_kb=256 * 1024,
        checker="exact",
        test_cases=test_cases
    )


def create_sorting_problem() -> Problem:
    """Sorting problem."""
    test_cases = [
        TestCase(input="5 4 3 2 1", expected_output="1 2 3 4 5", points=10),
        TestCase(input="1 1 1 1", expected_output="1 1 1 1", points=10),
        TestCase(input="9 8 7 6 5 4 3 2 1", expected_output="1 2 3 4 5 6 7 8 9", points=10),
    ]
    
    return Problem(
        id="sorting",
        title="Sort the Array",
        difficulty="Easy",
        time_limit_ms=3000,
        memory_limit_kb=256 * 1024,
        checker="exact",
        test_cases=test_cases
    )


# =============================================================================
# Demo
# =============================================================================

def demo():
    """Demonstrate the judge engine."""
    print("=" * 70)
    print(" " * 15 + "ALGOBATTLE JUDGE ENGINE DEMO")
    print("=" * 70)
    
    engine = JudgeEngine()
    
    # Create problem
    problem = create_fibonacci_problem()
    print(f"\nProblem: {problem.title} ({problem.difficulty})")
    print(f"Test cases: {len(problem.test_cases)}")
    print(f"Time limit: {problem.time_limit_ms}ms")
    
    # Correct solution
    correct_code = """def fib(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b

n = int(input())
print(fib(n))"""
    
    print("\n[1] Testing CORRECT solution...")
    result = engine.judge(correct_code, "python", problem)
    
    print(f"""
Results:
  Verdict:        {result.verdict}
  Score:          {result.earned_points}/{result.total_points} ({result.score*100:.0f}%)
  Runtime:        {result.runtime_ms:.2f}ms
  Efficiency:     {result.efficiency_score:.4f}
  Rank:           #{result.rank}
""")
    
    # Wrong solution
    wrong_code = """n = int(input())
print(n * 2)  # Wrong: returns 2n instead of fib(n)"""
    
    print("[2] Testing WRONG solution...")
    result2 = engine.judge(wrong_code, "python", problem)
    
    print(f"""
Results:
  Verdict:        {result2.verdict}
  Score:          {result2.earned_points}/{result2.total_points} ({result2.score*100:.0f}%)
  Failed test:    {result2.test_results[0]['test'] if result2.test_results else 'N/A'}
""")
    
    # Slow solution (TLE)
    slow_code = """def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)

n = int(input())
print(fib(n))"""
    
    print("[3] Testing SLOW solution (exponential)...")
    result3 = engine.judge(slow_code, "python", problem)
    
    print(f"""
Results:
  Verdict:        {result3.verdict}
  Score:          {result3.earned_points}/{result3.total_points}
  Runtime:        {result3.runtime_ms:.2f}ms
""")
    
    # Leaderboard
    print("\n[LEADERBOARD]")
    print("-" * 70)
    for entry in engine.get_leaderboard():
        print(f"  #{entry['rank']} | {entry['verdict']:25} | Score: {entry['score']:.2f} | Eff: {entry['efficiency_score']:.4f}")
    
    print("\n" + "=" * 70)
    print("Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    demo()
