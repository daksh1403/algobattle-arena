#!/usr/bin/env python3
"""
AlgoBattle Web Arena — Remote Runtime Environment
=================================================

GDG VIT Chennai speed-coding event backend. Participants submit code,
it is compiled + run in an isolated sandbox, judged for correctness,
and ranked by algorithmic efficiency.

Features:
- Process-level sandbox (RLIMIT_AS/CPU/STACK/FSIZE + live RSS monitor)
- Python / C++ / Java compile+run
- Hidden test cases (samples visible, hidden judged on submit)
- Participant auth (token-based, admin via ADMIN_KEY)
- Contests: window, freeze, per-contest standings (aggregate scoring)
- Plagiarism detection (normalized-code similarity)
- SSE live standings
- Programiz-style compiler endpoint (/api/compiler/run)
- User-added custom problems with test cases

Run:
    python web_arena.py        # http://127.0.0.1:8080
"""

import hashlib
import json
import os
import re
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Header
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from sandbox.sandbox_runner import SandboxRunner, Verdict

ADMIN_KEY = os.environ.get("ADMIN_KEY", "gdg-admin-2026")

# ---------------------------------------------------------------------------
# Problem bank (curated, with sample + hidden tests)
# ---------------------------------------------------------------------------


@dataclass
class Problem:
    slug: str
    title: str
    difficulty: str
    description: str
    examples: list              # sample (input, output) — shown to users
    hidden_tests: list          # (input, output) — judged on submit only
    solution: str               # reference python
    time_limit_s: float = 3.0


PROBLEMS = [
    Problem(slug="two-sum", title="1. Two Sum", difficulty="Easy",
            description="""Given an array of integers `nums` and a target `target`, return the indices of the two numbers that add up to the target.

**Input format:** first line = space-separated integers, second line = target.

**Output format:** two indices separated by a space.""",
            examples=[("2 7 11 15\n9", "0 1"), ("3 2 4\n6", "1 2"), ("3 3\n6", "0 1")],
            hidden_tests=[("1 2 3\n5", "1 2"), ("-1 0 1 2\n0", "0 2"),
                          ("0 4 3 0\n0", "0 3"), ("1 2 3 4 5\n9", "3 4"),
                          ("9 9 9 9\n18", "0 1"), ("100 200 300\n500", "1 2")],
            solution="""nums = list(map(int, input().split()))
t = int(input())
d = {}
for i, n in enumerate(nums):
    if t - n in d:
        print(d[t - n], i)
        break
    d[n] = i
"""),
    Problem(slug="fibonacci", title="2. Fibonacci Number", difficulty="Easy",
            description="""Given `n`, return the n-th Fibonacci number (F(0)=0, F(1)=1).

**Input format:** single integer `n`.

**Output format:** F(n).""",
            examples=[("10", "55"), ("20", "6765"), ("30", "832040")],
            hidden_tests=[("0", "0"), ("1", "1"), ("2", "1"), ("25", "75025"),
                          ("40", "102334155"), ("45", "1134903170")],
            solution="""n = int(input())
a, b = 0, 1
for _ in range(n):
    a, b = b, a + b
print(a)
"""),
    Problem(slug="maximum-subarray", title="3. Maximum Subarray", difficulty="Medium",
            description="""Given an array of integers, find the contiguous subarray with the largest sum (Kadane's algorithm).

**Input format:** space-separated integers.

**Output format:** the maximum subarray sum.""",
            examples=[("-2 1 -3 4 -1 2 1 -5 4", "6"), ("1", "1"), ("5 4 -1 7 8", "23")],
            hidden_tests=[("-1", "-1"), ("-2 -1", "-1"), ("3 -2 5 -1", "6"),
                          ("8 -19 5 -4 20", "21"), ("1 2 3 4 5", "15"),
                          ("-5 -4 -3 -2 -1", "-1")],
            solution="""nums = list(map(int, input().split()))
best = cur = nums[0]
for x in nums[1:]:
    cur = max(x, cur + x)
    best = max(best, cur)
print(best)
"""),
    Problem(slug="valid-parentheses", title="4. Valid Parentheses", difficulty="Easy",
            description="""Given a string containing just the characters `()[]{}`, determine if the input string is valid.

**Input format:** the bracket string.

**Output format:** `true` or `false`.""",
            examples=[("()[]{}", "true"), ("([)]", "false"), ("{[]}", "true")],
            hidden_tests=[("(", "false"), (")", "false"), ("((()))", "true"),
                          ("([{}])", "true"), ("(]", "false"), ("{[()]}", "true"),
                          ("(((((((()", "false"), ("", "true")],
            solution="""import sys
s = sys.stdin.read().strip()
st = []
pairs = {')': '(', ']': '[', '}': '{'}
for c in s:
    if c in pairs:
        if not st or st.pop() != pairs[c]:
            print('false')
            break
    else:
        st.append(c)
else:
    print('true' if not st else 'false')
"""),
    Problem(slug="climbing-stairs", title="5. Climbing Stairs", difficulty="Easy",
            description="""You are climbing a staircase with `n` steps. Each time you can climb 1 or 2 steps. In how many distinct ways can you climb to the top?

**Input format:** single integer `n`.

**Output format:** number of ways.""",
            examples=[("2", "2"), ("3", "3"), ("5", "8")],
            hidden_tests=[("1", "1"), ("4", "5"), ("6", "13"), ("10", "89"),
                          ("30", "1346269"), ("44", "1134903170")],
            solution="""n = int(input())
a, b = 1, 1
for _ in range(n - 1):
    a, b = b, a + b
print(b)
"""),
    Problem(slug="palindrome-number", title="6. Palindrome Number", difficulty="Easy",
            description="""Given an integer `x`, return `true` if it is a palindrome (reads the same forwards and backwards).

**Input format:** single integer.

**Output format:** `true` or `false`.""",
            examples=[("121", "true"), ("-121", "false"), ("1221", "true")],
            hidden_tests=[("0", "true"), ("10", "false"), ("12321", "true"),
                          ("123456", "false"), ("11", "true"), ("1001", "true")],
            solution="""x = int(input())
s = str(abs(x))
print('true' if x >= 0 and s == s[::-1] else 'false')
"""),
    Problem(slug="binary-search", title="7. Binary Search", difficulty="Easy",
            description="""Given a sorted array of integers and a target, return the index of the target, or `-1` if not present.

**Input format:** first line = space-separated sorted integers, second line = target.

**Output format:** the index, or `-1`.""",
            examples=[("-1 0 3 5 9 12\n9", "4"), ("-1 0 3 5 9 12\n2", "-1"),
                      ("5\n5", "0")],
            hidden_tests=[("1 2 3 4 5\n1", "0"), ("1 2 3 4 5\n5", "4"),
                          ("1 2 3 4 5\n3", "2"), ("1 2 3 4 5\n6", "-1"),
                          ("10 20 30 40 50\n20", "1"), ("-9 -3 0 7\n-3", "1")],
            solution="""nums = list(map(int, input().split()))
t = int(input())
lo, hi = 0, len(nums) - 1
ans = -1
while lo <= hi:
    mid = (lo + hi) // 2
    if nums[mid] == t:
        ans = mid
        break
    elif nums[mid] < t:
        lo = mid + 1
    else:
        hi = mid - 1
print(ans)
"""),
    Problem(slug="contains-duplicate", title="8. Contains Duplicate", difficulty="Easy",
            description="""Given an array of integers, return `true` if any value appears at least twice, else `false`.

**Input format:** space-separated integers.

**Output format:** `true` or `false`.""",
            examples=[("1 2 3 1", "true"), ("1 2 3 4", "false"),
                      ("1 1 1 3 3 4 3 2 4 2", "true")],
            hidden_tests=[("1", "false"), ("5 5", "true"), ("1 2 3 4 5 6", "false"),
                          ("-1 -1 0", "true"), ("0 1 2 3 0", "true"),
                          ("9 8 7 6", "false")],
            solution="""nums = list(map(int, input().split()))
print('true' if len(set(nums)) < len(nums) else 'false')
"""),
    Problem(slug="best-time-buy-sell", title="9. Best Time to Buy and Sell Stock",
            difficulty="Medium",
            description="""Given an array `prices` where `prices[i]` is the price on day i, return the maximum profit you can achieve by buying one day and selling on a later day. Return `0` if no profit is possible.

**Input format:** space-separated integers (prices).

**Output format:** the max profit.""",
            examples=[("7 1 5 3 6 4", "5"), ("7 6 4 3 1", "0"), ("2 4 1", "2")],
            hidden_tests=[("1", "0"), ("1 2", "1"), ("3 3 3", "0"),
                          ("5 1 5 1 5", "4"), ("9 2 8 3 7", "6"),
                          ("1 2 3 4 5", "4")],
            solution="""p = list(map(int, input().split()))
mn = p[0]
best = 0
for x in p[1:]:
    best = max(best, x - mn)
    mn = min(mn, x)
print(best)
"""),
    Problem(slug="power-of-two", title="10. Power of Two", difficulty="Easy",
            description="""Given an integer `n`, return `true` if it is a power of two, else `false`.

**Input format:** single integer.

**Output format:** `true` or `false`.""",
            examples=[("1", "true"), ("16", "true"), ("3", "false")],
            hidden_tests=[("0", "false"), ("2", "true"), ("64", "true"),
                          ("100", "false"), ("1024", "true"), ("-16", "false")],
            solution="""n = int(input())
print('true' if n > 0 and (n & (n - 1)) == 0 else 'false')
"""),
]

PROBLEM_MAP = {p.slug: p for p in PROBLEMS}


# ---------------------------------------------------------------------------
# Persistence + competition store
# ---------------------------------------------------------------------------


@dataclass
class Submission:
    id: int
    participant_id: int
    participant: str
    problem_slug: str
    language: str
    code: str
    verdict: str
    score: int
    total_tests: int
    runtime_ms: float
    cpu_time_ms: float
    memory_kb: float
    efficiency: float
    created_at: float
    contest_id: int | None = None


@dataclass
class Participant:
    id: int
    name: str
    token_hash: str
    is_admin: bool = False
    created_at: float = field(default_factory=time.time)


@dataclass
class Contest:
    id: int
    name: str
    description: str
    problem_slugs: list
    created_at: float
    start_time: float | None = None
    end_time: float | None = None
    freeze_at: float | None = None
    status: str = "draft"   # draft | live | ended


class Arena:
    """Competition store — persistent JSON, survives restarts."""

    DATA_FILE = os.environ.get(
        "ARENA_DATA_FILE",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "arena_data.json"),
    )

    def __init__(self):
        self.submissions: list[Submission] = []
        self.custom_problems: dict = {}
        self.participants: list[Participant] = []
        self.contests: list[Contest] = []
        self.counter = 0
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=8)
        self._stream_events = threading.Event()     # SSE wake-up
        self._load()

    # ---- persistence -----------------------------------------------------
    def _load(self):
        try:
            if os.path.exists(self.DATA_FILE):
                with open(self.DATA_FILE) as f:
                    data = json.load(f)
                self.submissions = [Submission(**d) for d in data.get("submissions", [])]
                self.participants = [Participant(**d) for d in data.get("participants", [])]
                self.contests = [Contest(**d) for d in data.get("contests", [])]
                self.custom_problems = data.get("custom_problems", {})
                self.counter = data.get("counter", len(self.submissions))
        except Exception:
            self.submissions, self.participants, self.contests = [], [], []
            self.counter = 0

    def _save(self):
        try:
            with open(self.DATA_FILE, "w") as f:
                json.dump({
                    "counter": self.counter,
                    "submissions": [vars(s) for s in self.submissions],
                    "participants": [vars(p) for p in self.participants],
                    "contests": [vars(c) for c in self.contests],
                    "custom_problems": self.custom_problems,
                }, f, indent=2, default=str)
        except Exception:
            pass

    # ---- auth ------------------------------------------------------------
    def register(self, name: str, admin_key: str | None = None):
        with self.lock:
            is_admin = bool(admin_key) and admin_key == ADMIN_KEY
            raw_token = uuid.uuid4().hex
            p = Participant(
                id=self.counter + 1,
                name=name.strip()[:40],
                token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
                is_admin=is_admin,
            )
            self.counter += 1
            self.participants.append(p)
            self._save()
            return p, raw_token

    def get_participant_by_token(self, token: str):
        if not token:
            return None
        h = hashlib.sha256(token.encode()).hexdigest()
        for p in self.participants:
            if p.token_hash == h:
                return p
        return None

    # ---- contests --------------------------------------------------------
    def create_contest(self, name, description, problem_slugs):
        with self.lock:
            self.counter += 1
            c = Contest(
                id=self.counter,
                name=name.strip()[:60],
                description=description.strip() or "",
                problem_slugs=[s for s in problem_slugs if s in PROBLEM_MAP],
                created_at=time.time(),
            )
            self.contests.append(c)
            self._save()
            return c

    def get_contest(self, cid):
        for c in self.contests:
            if c.id == cid:
                return c
        return None

    def start_contest(self, cid):
        c = self.get_contest(cid)
        if not c:
            return None
        with self.lock:
            if c.start_time is None:
                c.start_time = time.time()
            c.status = "live"
            if c.end_time is None:
                c.end_time = c.start_time + 2 * 3600   # default 2h
            self._save()
        return c

    def end_contest(self, cid):
        c = self.get_contest(cid)
        if not c:
            return None
        with self.lock:
            c.end_time = time.time()
            c.status = "ended"
            self._save()
        return c

    # ---- judging ---------------------------------------------------------
    def _judge_one(self, runner, code, stdin, expected):
        r = runner.run(code, stdin=stdin, expected_stdout=expected)
        if r.verdict == Verdict.ACCEPTED:
            return "AC", r
        if r.verdict == Verdict.WRONG_ANSWER:
            return "WA", r
        if r.verdict == Verdict.TIME_LIMIT_EXCEEDED:
            return "TLE", r
        if r.verdict == Verdict.MEMORY_LIMIT_EXCEEDED:
            return "MLE", r
        if r.verdict == Verdict.COMPILATION_ERROR:
            return "CE", r
        return "RE", r

    def _run_tests(self, code, language, tests, time_limit_s):
        lang_map = {"python": "python", "cpp": "cpp", "java": "java"}
        lang = lang_map.get(language, "python")
        wall = time_limit_s if lang == "python" else max(time_limit_s, 10.0)
        runner = SandboxRunner(language=lang, wall_time_s=wall)
        results, total_cpu, max_mem, passed = [], 0.0, 0.0, 0
        first_fail = None
        for inp, expected in tests:
            verdict, r = self._judge_one(runner, code, inp, expected)
            total_cpu += r.cpu_time_ms
            max_mem = max(max_mem, r.memory_kb)
            results.append({
                "input": inp, "expected": expected,
                "actual": r.stdout.strip(), "verdict": verdict,
                "runtime_ms": round(r.runtime_ms, 1),
                "cpu_time_ms": round(r.cpu_time_ms, 1),
                "memory_kb": round(r.memory_kb, 1),
                "error": r.stderr[:200],
            })
            if verdict == "AC":
                passed += 1
            elif first_fail is None:
                first_fail = verdict
        overall = "AC" if passed == len(tests) else (first_fail or "RE")
        return results, overall, passed, len(tests), total_cpu, max_mem

    def _efficiency(self, overall, total_cpu, max_mem, time_limit_s, n_tests):
        if overall != "AC":
            return 99.0
        budget = time_limit_s * 1000 * max(n_tests, 1)
        cpu_ratio = total_cpu / budget if budget > 0 else 0
        mem_ratio = max_mem / (256 * 1024)
        return round(cpu_ratio * 0.7 + mem_ratio * 0.3, 4)

    def submit(self, slug, language, code, mode="run", participant="Anonymous",
               participant_id=0, contest_id=None):
        problem = PROBLEM_MAP[slug]
        if mode == "submit":
            tests = problem.examples + problem.hidden_tests
            visible = len(problem.examples)
        else:
            tests = problem.examples
            visible = len(tests)
        results, overall, passed, total, total_cpu, max_mem = self._run_tests(
            code, language, tests, problem.time_limit_s)
        eff = self._efficiency(overall, total_cpu, max_mem,
                               problem.time_limit_s, len(tests))
        # Don't leak hidden inputs/outputs — return samples in full, hidden as summary
        visible_results = results[:visible]
        hidden_results = results[visible:]
        hidden_summary = None
        if mode == "submit" and hidden_results:
            hidden_passed = sum(1 for r in hidden_results if r["verdict"] == "AC")
            hidden_verdict = "AC" if hidden_passed == len(hidden_results) else \
                next((r["verdict"] for r in hidden_results if r["verdict"] != "AC"), "RE")
            hidden_summary = {"passed": hidden_passed, "total": len(hidden_results),
                              "verdict": hidden_verdict}

        with self.lock:
            self.counter += 1
            sub = Submission(
                id=self.counter, participant_id=participant_id,
                participant=participant, problem_slug=slug, language=language,
                code=code, verdict=overall, score=passed, total_tests=total,
                runtime_ms=sum(r["runtime_ms"] for r in results),
                cpu_time_ms=total_cpu, memory_kb=max_mem, efficiency=eff,
                created_at=time.time(), contest_id=contest_id,
            )
            self.submissions.append(sub)
            self._save()
            self._stream_events.set()
        return {
            "verdict": overall, "score": f"{passed}/{total}",
            "efficiency": eff, "cpu_time_ms": round(total_cpu, 1),
            "results": visible_results, "hidden_summary": hidden_summary,
            "submission_id": self.counter, "participant": participant,
            "problem_slug": slug, "language": language,
        }

    def compiler_run(self, language, code, stdin="", time_limit_s=3.0):
        lang_map = {"python": "python", "cpp": "cpp", "java": "java"}
        lang = lang_map.get(language, "python")
        wall = time_limit_s if lang == "python" else max(time_limit_s, 10.0)
        runner = SandboxRunner(language=lang, wall_time_s=wall)
        r = runner.run(code, stdin=stdin)
        verdict = "AC" if r.verdict == Verdict.ACCEPTED else (
            "WA" if r.verdict == Verdict.WRONG_ANSWER else
            "TLE" if r.verdict == Verdict.TIME_LIMIT_EXCEEDED else
            "MLE" if r.verdict == Verdict.MEMORY_LIMIT_EXCEEDED else
            "CE" if r.verdict == Verdict.COMPILATION_ERROR else "RE")
        return {"verdict": verdict, "stdout": r.stdout, "stderr": r.stderr[:500],
                "runtime_ms": round(r.runtime_ms, 1),
                "cpu_time_ms": round(r.cpu_time_ms, 1),
                "memory_kb": round(r.memory_kb, 1), "error": r.error_detail}

    def add_custom_problem(self, title, description, examples, hidden=None,
                           creator="Anonymous"):
        slug = "custom-" + hashlib.md5(
            (title + str(time.time())).encode()).hexdigest()[:8]
        with self.lock:
            self.custom_problems[slug] = {
                "slug": slug, "title": title, "description": description,
                "examples": examples, "hidden": hidden or [],
                "creator": creator, "difficulty": "Custom",
            }
            self._save()
        return slug

    def remove_custom_problem(self, slug):
        with self.lock:
            if slug not in self.custom_problems:
                return False
            del self.custom_problems[slug]
            self._save()
        return True

    def submit_custom(self, slug, language, code, participant="Anonymous",
                      participant_id=0, contest_id=None):
        prob = self.custom_problems.get(slug)
        if not prob:
            raise KeyError(slug)
        tests = prob["examples"] + prob.get("hidden", [])
        visible = len(prob["examples"])
        results, overall, passed, total, total_cpu, max_mem = self._run_tests(
            code, language, tests, 3.0)
        eff = self._efficiency(overall, total_cpu, max_mem, 3.0, len(tests))
        visible_results = results[:visible]
        hidden_results = results[visible:]
        hidden_summary = None
        if hidden_results:
            hp = sum(1 for r in hidden_results if r["verdict"] == "AC")
            hv = "AC" if hp == len(hidden_results) else next(
                (r["verdict"] for r in hidden_results if r["verdict"] != "AC"), "RE")
            hidden_summary = {"passed": hp, "total": len(hidden_results), "verdict": hv}
        with self.lock:
            self.counter += 1
            sub = Submission(
                id=self.counter, participant_id=participant_id,
                participant=participant, problem_slug=slug, language=language,
                code=code, verdict=overall, score=passed, total_tests=total,
                runtime_ms=sum(r["runtime_ms"] for r in results),
                cpu_time_ms=total_cpu, memory_kb=max_mem, efficiency=eff,
                created_at=time.time(), contest_id=contest_id,
            )
            self.submissions.append(sub)
            self._save()
            self._stream_events.set()
        return {"verdict": overall, "score": f"{passed}/{total}",
                "efficiency": eff, "cpu_time_ms": round(total_cpu, 1),
                "results": visible_results, "hidden_summary": hidden_summary,
                "submission_id": self.counter, "participant": participant,
                "problem_slug": slug, "language": language}

    # ---- standings -------------------------------------------------------
    def _tests_for(self, slug):
        if slug in PROBLEM_MAP:
            return len(PROBLEM_MAP[slug].examples) + len(PROBLEM_MAP[slug].hidden_tests)
        cp = self.custom_problems.get(slug)
        return len(cp["examples"]) + len(cp.get("hidden", [])) if cp else 1

    def _best_per_problem(self, subs):
        best = {}
        for s in subs:
            key = (s.participant_id, s.problem_slug)
            cur = best.get(key)
            if cur is None:
                best[key] = s
                continue

            def rank(x):
                return (1 if x.verdict == "AC" else 0, x.score,
                        -x.efficiency if x.verdict == "AC" else 0, -x.created_at)
            if rank(s) > rank(cur):
                best[key] = s
        return best

    def standings(self, contest_id, freeze=True):
        c = self.get_contest(contest_id)
        if not c:
            return []
        cutoff = c.freeze_at if (freeze and c.freeze_at) else None
        with self.lock:
            subs = [s for s in self.submissions
                    if s.contest_id == contest_id and
                    (cutoff is None or s.created_at <= cutoff)]
        if not c.problem_slugs:
            return []
        best = self._best_per_problem(subs)
        rows = {}
        for (pid, slug), s in best.items():
            row = rows.setdefault(pid, {"participant": s.participant,
                                        "problem_results": {}, "total": 0,
                                        "penalty": 0.0, "solved": 0})
            row["problem_results"][slug] = {
                "verdict": s.verdict, "score": s.score,
                "total": self._tests_for(slug), "efficiency": s.efficiency,
                "cpu_time_ms": round(s.cpu_time_ms, 1),
            }
            row["total"] += s.score
            row["penalty"] += s.cpu_time_ms if s.verdict == "AC" else \
                s.cpu_time_ms * 0.5
            if s.verdict == "AC":
                row["solved"] += 1
        ranked = sorted(rows.values(),
                        key=lambda r: (-r["total"], r["penalty"], r["participant"].lower()))
        for i, r in enumerate(ranked, 1):
            r["rank"] = i
        return ranked

    # ---- plagiarism ------------------------------------------------------
    @staticmethod
    def _normalize(code):
        code = re.sub(r"//.*|/\*.*?\*/|#.*", "", code, flags=re.S)
        code = re.sub(r"\s+", "", code).lower()
        return code

    def plagiarism_report(self, contest_id, threshold=0.85):
        subs = [s for s in self.submissions if s.contest_id == contest_id]
        norms = {s.id: self._normalize(s.code) for s in subs}
        pairs = []
        ids = list(norms)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = norms[ids[i]], norms[ids[j]]
                if not a or not b:
                    continue

                def grams(t, n=5):
                    return {t[k:k + n] for k in range(len(t) - n + 1)} or {t}
                ga, gb = grams(a), grams(b)
                sim = len(ga & gb) / max(len(ga | gb), 1)
                if sim >= threshold:
                    sa = next(s for s in subs if s.id == ids[i])
                    sb = next(s for s in subs if s.id == ids[j])
                    pairs.append({
                        "a": {"id": sa.id, "participant": sa.participant,
                              "problem": sa.problem_slug},
                        "b": {"id": sb.id, "participant": sb.participant,
                              "problem": sb.problem_slug},
                        "similarity": round(sim, 3),
                    })
        pairs.sort(key=lambda p: -p["similarity"])
        return pairs

    def leaderboard(self):
        """Legacy per-submission leaderboard (score desc, efficiency asc)."""
        with self.lock:
            subs = sorted(self.submissions,
                          key=lambda s: (-s.score, s.efficiency, s.created_at))
            return [{"rank": i + 1, "id": s.id, "participant": s.participant,
                     "problem": s.problem_slug, "language": s.language,
                     "verdict": s.verdict,
                     "score": f"{s.score}/{max(self._tests_for(s.problem_slug),1)}",
                     "efficiency": s.efficiency,
                     "runtime_ms": round(s.runtime_ms, 1),
                     "cpu_time_ms": round(s.cpu_time_ms, 1)}
                    for i, s in enumerate(subs)]


arena = Arena()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="AlgoBattle Arena")


class SubmitReq(BaseModel):
    slug: str
    language: str
    code: str
    mode: str = "run"
    participant: str = "Anonymous"
    contest_id: int | None = None


class RunReq(BaseModel):
    language: str
    code: str
    stdin: str = ""
    time_limit_s: float = 3.0


class CustomProblemReq(BaseModel):
    title: str
    description: str
    examples: list
    hidden: list = []
    creator: str = "Anonymous"


class CustomSubmitReq(BaseModel):
    slug: str
    language: str
    code: str
    participant: str = "Anonymous"


class RegisterReq(BaseModel):
    name: str
    admin_key: str | None = None


class ContestReq(BaseModel):
    name: str
    description: str = ""
    problem_slugs: list = []


# Simple per-participant rate limiter: max 10 submissions / 60s
_RATE: dict = {}
_RATE_LOCK = threading.Lock()
RATE_LIMIT = 10
RATE_WINDOW_S = 60


def _rate_limited(participant: str) -> bool:
    now = time.time()
    with _RATE_LOCK:
        stamps = [s for s in _RATE.get(participant, []) if now - s < RATE_WINDOW_S]
        if len(stamps) >= RATE_LIMIT:
            _RATE[participant] = stamps
            return True
        stamps.append(now)
        _RATE[participant] = stamps
        return False


def _resolve_participant(token: str | None):
    return arena.get_participant_by_token(token or "") if token else None


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse("""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>AlgoBattle Arena</title></head><body style="background:#0f1117;color:#e6e8ef;
font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh">
<div style="text-align:center"><h1>⚔️ AlgoBattle Arena</h1>
<p>This is the judge backend. The UI is served by the Cloudflare Worker at
<a href="https://algobattle-arena.dakshx.workers.dev" style="color:#4f8cff">
algobattle-arena.dakshx.workers.dev</a></p>
<p style="color:#8b90a5">API docs: <a href="/docs" style="color:#4f8cff">/docs</a></p>
</div></body></html>""")


@app.get("/health")
def health():
    return JSONResponse({"status": "ok", "app": "algobattle", "sandbox": "online",
                         "contests": len(arena.contests),
                         "participants": len(arena.participants)})


# ---- auth ----------------------------------------------------------------
@app.post("/api/auth/register")
def register(req: RegisterReq):
    if not req.name.strip():
        return JSONResponse({"error": "name required"}, status_code=422)
    p, raw_token = arena.register(req.name, req.admin_key)
    return JSONResponse({"id": p.id, "name": p.name, "is_admin": p.is_admin,
                         "token": raw_token})


@app.get("/api/auth/me")
def auth_me(x_token: str | None = Header(default=None)):
    p = _resolve_participant(x_token)
    if not p:
        return JSONResponse({"error": "invalid token"}, status_code=401)
    return JSONResponse({"id": p.id, "name": p.name, "is_admin": p.is_admin})


# ---- problems ------------------------------------------------------------
@app.get("/api/problems")
def problems():
    return JSONResponse([
        {"slug": p.slug, "title": p.title, "difficulty": p.difficulty,
         "description": p.description, "examples": p.examples,
         "hidden_count": len(p.hidden_tests)} for p in PROBLEMS])


# ---- contests ------------------------------------------------------------
@app.get("/api/contests")
def list_contests():
    out = []
    for c in arena.contests:
        out.append({"id": c.id, "name": c.name, "description": c.description,
                    "problem_slugs": c.problem_slugs, "status": c.status,
                    "start_time": c.start_time, "end_time": c.end_time,
                    "freeze_at": c.freeze_at})
    return JSONResponse(out)


@app.post("/api/contests")
def create_contest(req: ContestReq, x_token: str | None = Header(default=None)):
    p = _resolve_participant(x_token)
    if not p or not p.is_admin:
        return JSONResponse({"error": "admin required"}, status_code=403)
    c = arena.create_contest(req.name, req.description, req.problem_slugs)
    return JSONResponse({"id": c.id, "name": c.name})


@app.post("/api/contests/{cid}/start")
def start_contest(cid: int, x_token: str | None = Header(default=None)):
    p = _resolve_participant(x_token)
    if not p or not p.is_admin:
        return JSONResponse({"error": "admin required"}, status_code=403)
    c = arena.start_contest(cid)
    if not c:
        return JSONResponse({"error": "contest not found"}, status_code=404)
    return JSONResponse({"id": c.id, "status": c.status,
                         "start_time": c.start_time, "end_time": c.end_time})


@app.post("/api/contests/{cid}/end")
def end_contest(cid: int, x_token: str | None = Header(default=None)):
    p = _resolve_participant(x_token)
    if not p or not p.is_admin:
        return JSONResponse({"error": "admin required"}, status_code=403)
    c = arena.end_contest(cid)
    if not c:
        return JSONResponse({"error": "contest not found"}, status_code=404)
    return JSONResponse({"id": c.id, "status": c.status})


@app.get("/api/contests/{cid}/standings")
def contest_standings(cid: int):
    return JSONResponse(arena.standings(cid))


@app.get("/api/contests/{cid}/standings/stream")
def standings_stream(cid: int):
    def gen():
        last = None
        while True:
            data = arena.standings(cid)
            if data != last:
                last = data
                yield f"data: {json.dumps(data)}\n\n"
            else:
                yield ": keepalive\n\n"
            arena._stream_events.clear()
            arena._stream_events.wait(15)
            arena._stream_events.clear()
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/contests/{cid}/plagiarism")
def contest_plagiarism(cid: int, x_token: str | None = Header(default=None)):
    p = _resolve_participant(x_token)
    if not p or not p.is_admin:
        return JSONResponse({"error": "admin required"}, status_code=403)
    return JSONResponse(arena.plagiarism_report(cid))


# ---- submissions ---------------------------------------------------------
@app.post("/api/submit")
def submit(req: SubmitReq, x_token: str | None = Header(default=None)):
    p = _resolve_participant(x_token)
    participant = p.name if p else req.participant
    pid = p.id if p else 0
    if _rate_limited(participant):
        return JSONResponse({"error": "rate_limited",
                             "detail": "Too many submissions (max 10/min)"},
                            status_code=429)
    cid = req.contest_id
    if cid is not None:
        c = arena.get_contest(cid)
        if not c:
            return JSONResponse({"error": "contest not found"}, status_code=404)
        now = time.time()
        if c.status == "ended" or (c.end_time and now > c.end_time):
            return JSONResponse({"error": "contest_ended",
                                 "detail": "This contest has ended."}, status_code=403)
        if c.status == "draft":
            return JSONResponse({"error": "contest_not_started",
                                 "detail": "This contest hasn't started yet."},
                                status_code=403)
    if req.slug not in PROBLEM_MAP:
        return JSONResponse({"error": "unknown problem"}, status_code=422)
    result = arena.submit(req.slug, req.language, req.code, req.mode,
                          participant=participant, participant_id=pid,
                          contest_id=cid)
    return JSONResponse(result)


@app.post("/api/compiler/run")
def compiler_run(req: RunReq):
    return JSONResponse(arena.compiler_run(req.language, req.code, req.stdin,
                                           req.time_limit_s))


@app.post("/api/run")
def run_alias(req: RunReq):
    return compiler_run(req)


# ---- custom problems -----------------------------------------------------
@app.get("/api/problems/custom")
def custom_problems():
    with arena.lock:
        return JSONResponse(list(arena.custom_problems.values()))


@app.post("/api/problems/custom")
def add_custom_problem(req: CustomProblemReq):
    if not req.title.strip() or not req.examples:
        return JSONResponse({"error": "title and examples required"},
                            status_code=422)
    slug = arena.add_custom_problem(req.title, req.description, req.examples,
                                    hidden=req.hidden, creator=req.creator)
    return JSONResponse({"slug": slug, "title": req.title})


@app.delete("/api/problems/custom/{slug}")
def delete_custom_problem(slug: str):
    removed = arena.remove_custom_problem(slug)
    if not removed:
        return JSONResponse({"error": "custom problem not found"}, status_code=404)
    return JSONResponse({"ok": True, "slug": slug})


@app.post("/api/submit/custom")
def submit_custom(req: CustomSubmitReq):
    try:
        result = arena.submit_custom(req.slug, req.language, req.code,
                                     participant=req.participant)
    except KeyError:
        return JSONResponse({"error": "custom problem not found"}, status_code=404)
    return JSONResponse(result)


# ---- legacy leaderboard + history ---------------------------------------
@app.get("/api/leaderboard")
def leaderboard():
    return JSONResponse(arena.leaderboard())


@app.get("/api/submissions")
def submissions():
    with arena.lock:
        return JSONResponse([
            {"id": s.id, "participant": s.participant, "problem": s.problem_slug,
             "language": s.language, "verdict": s.verdict,
             "score": f"{s.score}/{s.total_tests}",
             "efficiency": s.efficiency,
             "cpu_time_ms": round(s.cpu_time_ms, 1), "created_at": s.created_at}
            for s in sorted(arena.submissions, key=lambda s: -s.id)][:100])


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print(" AlgoBattle Arena  →  http://127.0.0.1:8080")
    print(f" problems: {len(PROBLEMS)} · admin key: {ADMIN_KEY!r}")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="warning")
