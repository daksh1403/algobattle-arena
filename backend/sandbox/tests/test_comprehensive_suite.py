#!/usr/bin/env python3
"""
Comprehensive Test Suite - Fast Version
======================================

Tests all judge system scenarios efficiently.
Generates representative test cases and runs them.

Run: python sandbox/tests/test_comprehensive_suite.py
"""

import os
import sys
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sandbox.sandbox_runner import SandboxRunner, Verdict


@dataclass
class TestCase:
    name: str
    code: str
    language: str
    stdin: str = ""
    expected: Any = None
    description: str = ""
    category: str = ""
    difficulty: str = ""


class ComprehensiveTestSuite:
    """Fast comprehensive test suite."""
    
    def __init__(self):
        self.results = {}
        self.lock = threading.Lock()
        self.categories = {}
        self.verdicts = {}
        self.errors = {}
    
    def run_all(self) -> Dict[str, Any]:
        """Run all test categories."""
        print("=" * 70)
        print("ALGOBATTLE COMPREHENSIVE TEST SUITE")
        print("=" * 70)
        
        start = time.time()
        
        # Run all categories
        categories = [
            ("ACCEPTED", self._test_accepted),
            ("WRONG_ANSWER", self._test_wrong_answer),
            ("TIME_LIMIT", self._test_time_limit),
            ("MEMORY_LIMIT", self._test_memory_limit),
            ("RUNTIME_ERROR", self._test_runtime_errors),
            ("COMPILATION_ERROR", self._test_compilation_errors),
            ("EDGE_CASES", self._test_edge_cases),
            ("ALGORITHMS", self._test_algorithms),
            ("MULTI_LANG", self._test_multi_language),
            ("SECURITY", self._test_security),
            ("DETERMINISM", self._test_determinism),
            ("PERFORMANCE", self._test_performance),
        ]
        
        total_tests = 0
        total_passed = 0
        
        for name, test_func in categories:
            print(f"\n[{name}] Running tests...")
            cat_start = time.time()
            
            results = test_func()
            passed = sum(1 for r in results if r[1] == "PASS")
            failed = len(results) - passed
            total_tests += len(results)
            total_passed += passed
            
            cat_time = time.time() - cat_start
            rate = len(results) / cat_time if cat_time > 0 else 0
            
            print(f"  {len(results)} tests: {passed} passed, {failed} failed ({rate:.0f} tests/sec)")
            
            self.categories[name] = {
                "total": len(results),
                "passed": passed,
                "failed": failed,
                "time": cat_time
            }
        
        total_time = time.time() - start
        
        # Summary
        print("\n" + "=" * 70)
        print("FINAL SUMMARY")
        print("=" * 70)
        print(f"""
Total Tests:      {total_tests:,}
Passed:          {total_passed:,}
Failed:          {total_tests - total_passed:,}
Pass Rate:       {total_passed / total_tests * 100:.2f}%
Total Time:      {total_time:.1f}s
Tests/Second:    {total_tests / total_time:.0f}
""")
        
        return self._generate_report(total_tests, total_passed, total_time)
    
    def _run_test(self, test: TestCase) -> tuple:
        """Run a single test."""
        try:
            runner = SandboxRunner(
                language=test.language,
                wall_time_s=5,
                memory_kb=256 * 1024
            )
            
            result = runner.run(
                test.code,
                stdin=test.stdin,
                expected_stdout=test.expected
            )
            
            # Determine pass/fail
            if test.expected == "TLE":
                passed = result.verdict == Verdict.TIME_LIMIT_EXCEEDED
            elif test.expected == "MLE":
                passed = result.verdict == Verdict.MEMORY_LIMIT_EXCEEDED
            elif test.expected == "CE":
                passed = result.verdict == Verdict.COMPILATION_ERROR
            elif test.expected == "RE":
                passed = result.verdict == Verdict.RUNTIME_ERROR
            elif test.expected == "OLE":
                passed = result.verdict == Verdict.OUTPUT_LIMIT_EXCEEDED
            else:
                passed = result.verdict == Verdict.ACCEPTED
            
            with self.lock:
                self.verdicts[result.verdict.value] = self.verdicts.get(result.verdict.value, 0) + 1
            
            return (test.name, "PASS" if passed else "FAIL", result.verdict.value, result.runtime_ms)
        
        except Exception as e:
            with self.lock:
                self.errors[str(e)[:50]] = self.errors.get(str(e)[:50], 0) + 1
            return (test.name, "FAIL", str(e), 0)
    
    def _run_batch(self, tests: List[TestCase], workers: int = 8) -> List[tuple]:
        """Run tests in parallel."""
        results = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(self._run_test, t) for t in tests]
            for future in as_completed(futures):
                results.append(future.result())
        return results
    
    # ===================================================================
    # TEST CATEGORIES
    # ===================================================================
    
    def _test_accepted(self) -> List[tuple]:
        """Test ACCEPTED verdicts."""
        tests = [
            TestCase("basic_print", "print('hello')", "python", "", "hello"),
            TestCase("basic_arithmetic", "print(1 + 2 + 3)", "python", "", "6"),
            TestCase("string_upper", "print('hello'.upper())", "python", "", "HELLO"),
            TestCase("string_reverse", "print('abc'[::-1])", "python", "", "cba"),
            TestCase("list_sum", "print(sum([1,2,3,4,5]))", "python", "", "15"),
            TestCase("list_max", "print(max([3,1,4,1,5]))", "python", "", "5"),
            TestCase("list_sort", "print(sorted([3,1,2])[-1])", "python", "", "3"),
            TestCase("dict_access", "print({'a':1}['a'])", "python", "", "1"),
            TestCase("tuple_unpack", "print(sum((1,2,3)))", "python", "", "6"),
            TestCase("set_operations", "print(len({1,2,3,3,3}))", "python", "", "3"),
        ]
        
        # Generate 1000 arithmetic tests
        for a in range(100):
            for b in range(10):
                tests.append(TestCase(
                    f"arith_{a}_{b}",
                    f"print({a} + {b} * {a})",
                    "python", "",
                    str(a + b * a)
                ))
        
        return self._run_batch(tests)
    
    def _test_wrong_answer(self) -> List[tuple]:
        """Test WRONG_ANSWER verdicts."""
        tests = [
            TestCase("wa_offbyone", "print(5)", "python", "", "6"),
            TestCase("wa_case", "print('ABC')", "python", "", "abc"),
            TestCase("wa_whitespace", "print('a b')", "python", "", "a  b"),
            TestCase("wa_extra_newline", "print(1)", "python", "", "1\n2"),
            TestCase("wa_missing_char", "print('hello')", "python", "", "hell"),
            TestCase("wa_reversed", "print(123)", "python", "", "321"),
            TestCase("wa_float_precision", "print(0.1 + 0.2)", "python", "", "0.3"),  # FP issue
        ]
        
        # Generate 500 wrong answer tests
        for i in range(500):
            n = random.randint(1, 1000)
            offset = random.choice([-1, 1, 10, -10])
            tests.append(TestCase(
                f"wa_gen_{i}",
                f"print({n})",
                "python", "",
                str(n + offset)
            ))
        
        return self._run_batch(tests)
    
    def _test_time_limit(self) -> List[tuple]:
        """Test TIME_LIMIT_EXCEEDED verdicts."""
        tests = [
            TestCase("tle_while_true", "while True: pass", "python", "", "TLE"),
            TestCase("tle_for_huge", "for i in range(10**12): pass", "python", "", "TLE"),
            TestCase("tle_nested_100", "for i in range(100):\n for j in range(100):\n  for k in range(100): pass", "python", "", "TLE"),
            TestCase("tle_recursive", "def f(): return f()\nf()", "python", "", "RE"),  # RecursionError
        ]
        return self._run_batch(tests)
    
    def _test_memory_limit(self) -> List[tuple]:
        """Test MEMORY_LIMIT_EXCEEDED verdicts."""
        tests = [
            TestCase("mle_list_huge", "x = [0] * 100000000", "python", "", "MLE"),
            TestCase("mle_dict_huge", "d = {i: i for i in range(10000000)}", "python", "", "MLE"),
        ]
        return self._run_batch(tests)
    
    def _test_runtime_errors(self) -> List[tuple]:
        """Test RUNTIME_ERROR verdicts."""
        tests = [
            TestCase("re_div_zero", "print(1/0)", "python", "", "RE"),
            TestCase("re_index_oob", "print([1,2,3][100])", "python", "", "RE"),
            TestCase("re_key_error", "print({}[0])", "python", "", "RE"),
            TestCase("re_type_error", "print(1 + 'a')", "python", "", "RE"),
            TestCase("re_attr_error", "(1).append(2)", "python", "", "RE"),
            TestCase("re_name_error", "print(undefined_var)", "python", "", "RE"),
            TestCase("re_value_error", "int('abc')", "python", "", "RE"),
            TestCase("re_recursion", "def f(): return f()\nf()", "python", "", "RE"),
            TestCase("re_unpack", "a,b = [1,2,3]", "python", "", "RE"),
            TestCase("re_zero_division", "print(1 % 0)", "python", "", "RE"),
        ]
        return self._run_batch(tests)
    
    def _test_compilation_errors(self) -> List[tuple]:
        """Test COMPILATION_ERROR verdicts."""
        tests = [
            TestCase("ce_syntax_missing_paren", "print(", "python", "", "CE"),
            TestCase("ce_syntax_missing_colon", "if True pass", "python", "", "CE"),
            TestCase("ce_syntax_bad_indent", "if True:\nprint(1)", "python", "", "CE"),
            TestCase("ce_cpp_missing_return", "#include <iostream>\nint main() {\n  cout << 1\n}", "cpp", "", "CE"),
            TestCase("ce_cpp_undefined", "#include <iostream>\nint main() { undefined(); }", "cpp", "", "CE"),
        ]
        return self._run_batch(tests)
    
    def _test_edge_cases(self) -> List[tuple]:
        """Test edge cases."""
        tests = [
            TestCase("edge_empty_list", "print(len([]))", "python", "", "0"),
            TestCase("edge_zero", "print(5 % 5)", "python", "", "0"),
            TestCase("edge_negative", "print(abs(-100))", "python", "", "100"),
            TestCase("edge_large_int", "print(10**100)", "python", "", "1" + "0" * 100),
            TestCase("edge_unicode", "print('नमस्ते')", "python", "", "नमस्ते"),
            TestCase("edge_special_chars", "print('!@#$')", "python", "", "!@#$"),
            TestCase("edge_float_zero", "print(0.0)", "python", "", "0.0"),
            TestCase("edge_negative_zero", "print(-0.0)", "python", "", "-0.0"),
            TestCase("edge_infinity", "print(float('inf'))", "python", "", "inf"),
            TestCase("edge_nan", "print(float('nan'))", "python", "", "nan"),
        ]
        
        # Generate more edge cases
        for i in range(200):
            n = random.randint(-1000, 1000)
            tests.append(TestCase(
                f"edge_int_{i}",
                f"print(abs({n}))",
                "python", "",
                str(abs(n))
            ))
        
        return self._run_batch(tests)
    
    def _test_algorithms(self) -> List[tuple]:
        """Test algorithm implementations."""
        tests = [
            TestCase("algo_two_sum", "def twoSum(nums, t):\n d={}\n for i,n in enumerate(nums):\n  if t-n in d: return [d[t-n], i]\n  d[n]=i\nprint(*twoSum([2,7,11,15], 9))", "python", "", "0 1"),
            TestCase("algo_binary_search", "def bs(arr, t):\n l,r=0,len(arr)-1\n while l<=r:\n  m=(l+r)//2\n  if arr[m]==t: return m\n  arr[m]<t and (l:=m+1) or (r:=m-1)\n return -1\nprint(bs([1,3,5,7,9], 5))", "python", "", "2"),
            TestCase("algo_bubble_sort", "a=[3,1,4,1,5]\nfor i in range(len(a)):\n for j in range(len(a)-i-1):\n  if a[j]>a[j+1]: a[j],a[j+1]=a[j+1],a[j]\nprint(a[-1])", "python", "", "5"),
            TestCase("algo_fib_iter", "def fib(n):\n a,b=0,1\n for _ in range(n): a,b=b,a+b\n return a\nprint(fib(20))", "python", "", "6765"),
            TestCase("algo_factorial", "from math import factorial\nprint(factorial(20))", "python", "", "2432902008176640000"),
            TestCase("algo_gcd", "from math import gcd\nprint(gcd(48, 18))", "python", "", "6"),
            TestCase("algo_prime", "def is_prime(n):\n if n<2: return False\n for i in range(2,int(n**0.5)+1):\n  if n%i==0: return False\n return True\nprint(is_prime(29))", "python", "", "True"),
            TestCase("algo_reverse_str", "print('hello world'[::-1])", "python", "", "dlrow olleh"),
            TestCase("algo_palindrome", "print('racecar' == 'racecar'[::-1])", "python", "", "True"),
            TestCase("algo_anagram", "print(sorted('listen') == sorted('silent'))", "python", "", "True"),
        ]
        return self._run_batch(tests)
    
    def _test_multi_language(self) -> List[tuple]:
        """Test multiple programming languages."""
        tests = [
            TestCase("lang_python", "print('Hello from Python')", "python", "", "Hello from Python"),
            TestCase("lang_cpp", "#include <iostream>\nint main() { std::cout << \"Hello from C++\" << std::endl; return 0; }", "cpp", "", "Hello from C++"),
            TestCase("lang_java", "public class Main { public static void main(String[] args) { System.out.println(\"Hello from Java\"); } }", "java", "", "Hello from Java"),
            TestCase("lang_cpp_add", "#include <iostream>\nint main() { std::cout << 1 + 2 + 3 << std::endl; return 0; }", "cpp", "", "6"),
        ]
        return self._run_batch(tests)
    
    def _test_security(self) -> List[tuple]:
        """Test security restrictions."""
        tests = [
            TestCase("sec_file_read", "open('/etc/passwd').read()", "python", "", "RE"),  # Should fail
            TestCase("sec_import_os", "import os; print(os.listdir('/'))", "python", "", "RE"),  # / might be restricted
            TestCase("sec_eval", "eval('__import__(\"os\").system(\"ls\")')", "python", "", "RE"),
            TestCase("sec_exec", "exec('import os')", "python", "", "RE"),  # May work but limited
        ]
        return self._run_batch(tests)
    
    def _test_determinism(self) -> List[tuple]:
        """Test deterministic execution."""
        tests = []
        for i in range(10):
            tests.append(TestCase(
                f"det_seed_{i}",
                "import random\nrandom.seed(42)\nprint(random.randint(1, 100))",
                "python", "",
                "82"  # First randint with seed 42
            ))
        return self._run_batch(tests)
    
    def _test_performance(self) -> List[tuple]:
        """Test performance limits."""
        tests = [
            TestCase("perf_fast", "print(sum(range(10000)))", "python", "", "49995000"),
            TestCase("perf_sort_100", "print(sorted(range(100, 0, -1))[-1])", "python", "", "100"),
            TestCase("perf_dict_ops", "d = {i: i*2 for i in range(1000)}\nprint(sum(d.values()))", "python", "", "999000"),
            TestCase("perf_set_ops", "s = set(range(1000))\nprint(len(s))", "python", "", "1000"),
        ]
        return self._run_batch(tests)
    
    def _generate_report(self, total: int, passed: int, time_taken: float) -> Dict:
        """Generate final report."""
        print("\n" + "=" * 70)
        print("VERDICT DISTRIBUTION")
        print("=" * 70)
        
        for verdict, count in sorted(self.verdicts.items(), key=lambda x: -x[1]):
            pct = count / total * 100
            bar = "█" * int(pct / 2)
            print(f"  {verdict:<30} {count:>8,} ({pct:5.1f}%) {bar}")
        
        print("\n" + "=" * 70)
        print("CATEGORY BREAKDOWN")
        print("=" * 70)
        
        for cat, stats in self.categories.items():
            pct = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
            bar = "█" * int(pct / 5)
            print(f"  {cat:<20} {stats['passed']:>6}/{stats['total']:<6} ({pct:5.1f}%) {bar}")
        
        if self.errors:
            print("\n" + "=" * 70)
            print("TOP ERRORS")
            print("=" * 70)
            for error, count in sorted(self.errors.items(), key=lambda x: -x[1])[:10]:
                print(f"  {error:<50} {count:>5}")
        
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": f"{passed/total*100:.2f}%",
            "time": f"{time_taken:.1f}s",
            "verdicts": self.verdicts,
            "categories": self.categories,
            "errors": self.errors
        }


def main():
    suite = ComprehensiveTestSuite()
    report = suite.run_all()
    
    # Save report
    import json
    report_file = os.path.join(os.path.dirname(__file__), "comprehensive_report.json")
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved to: {report_file}")


if __name__ == "__main__":
    main()
