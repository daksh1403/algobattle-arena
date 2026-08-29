#!/usr/bin/env python3
"""
AlgoBattle contest + auth + hidden-test feature tests.

Covers:
  - /api/auth/register (participant + admin), /api/auth/me
  - /api/problems (10 problems, hidden counts)
  - /api/contests CRUD + start/end (admin gate)
  - /api/submit with hidden tests (samples visible, hidden summarized)
  - /api/contests/{id}/standings (aggregate scoring)
  - /api/contests/{id}/plagiarism (admin only, detects copies)
  - contest window enforcement (draft = reject, ended = reject)
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8080"
PASS = 0
FAIL = 0
RESULTS = []


def req(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Token"] = token
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception as e:
        return -1, {"error": str(e)}


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        RESULTS.append(f"  ✅ {name}")
    else:
        FAIL += 1
        RESULTS.append(f"  ❌ {name} {detail}")


TWO_SUM = """nums=list(map(int,input().split()))
t=int(input())
d={}
for i,n in enumerate(nums):
    if t-n in d: print(d[t-n],i); break
    d[n]=i"""

# ---- auth ----
s, admin = req("POST", "/api/auth/register", {"name": "Admin", "admin_key": "gdg-admin-2026"})
check("admin register", s == 200 and admin.get("is_admin") is True)
AT = admin.get("token", "")

s, alice = req("POST", "/api/auth/register", {"name": "Alice"})
check("participant register", s == 200 and alice.get("is_admin") is False and alice.get("token"))
AL = alice.get("token", "")

s, bob = req("POST", "/api/auth/register", {"name": "Bob"})
BL = bob.get("token", "")

s, me = req("GET", "/api/auth/me", token=AL)
check("auth/me returns identity", s == 200 and me.get("name") == "Alice")

s, me = req("GET", "/api/auth/me", token="bogus")
check("auth/me rejects bad token", s == 401)

# ---- problems ----
s, probs = req("GET", "/api/problems")
check("10 problems", s == 200 and len(probs) == 10)
check("hidden counts present", all(p.get("hidden_count", 0) > 0 for p in probs))

# ---- contests ----
s, bad = req("POST", "/api/contests", {"name": "hack", "problem_slugs": []}, token=AL)
check("non-admin cannot create contest", s == 403)

s, c = req("POST", "/api/contests", {
    "name": "GDG Speed Coding",
    "description": "2h contest",
    "problem_slugs": ["two-sum", "fibonacci", "valid-parentheses", "binary-search"],
}, token=AT)
check("admin creates contest", s == 200 and c.get("id"))
CID = c["id"]

# submit before start → rejected
s, r = req("POST", "/api/submit", {"slug": "two-sum", "language": "python",
                                   "code": TWO_SUM, "mode": "submit",
                                   "contest_id": CID}, token=AL)
check("submit before start rejected", s == 403 and r.get("error") == "contest_not_started")

s, st = req("POST", f"/api/contests/{CID}/start", token=AT)
check("start contest", s == 200 and st.get("status") == "live")

# ---- hidden test judging ----
s, r = req("POST", "/api/submit", {"slug": "two-sum", "language": "python",
                                   "code": TWO_SUM, "mode": "submit",
                                   "contest_id": CID}, token=AL)
check("alice full AC (9/9 incl hidden)", s == 200 and r.get("verdict") == "AC"
      and r.get("score") == "9/9")
check("hidden summary returned", r.get("hidden_summary") is not None
      and r["hidden_summary"]["passed"] == r["hidden_summary"]["total"])
check("hidden inputs NOT leaked", all(x["input"] in
      ("2 7 11 15\n9", "3 2 4\n6", "3 3\n6") for x in r.get("results", [])))
check("hidden verdict AC", r["hidden_summary"]["verdict"] == "AC")

# bob partial (samples only pass)
s, r = req("POST", "/api/submit", {"slug": "two-sum", "language": "python",
                                   "code": "print(0)", "mode": "submit",
                                   "contest_id": CID}, token=BL)
check("bob fails hidden", s == 200 and r.get("verdict") == "WA"
      and r["hidden_summary"]["passed"] == 0)

# mode=run only uses samples
s, r = req("POST", "/api/submit", {"slug": "two-sum", "language": "python",
                                   "code": TWO_SUM, "mode": "run", "contest_id": CID}, token=AL)
check("run mode only samples (3/3)", s == 200 and r.get("score") == "3/3"
      and r.get("hidden_summary") is None)

# ---- standings ----
s, rows = req("GET", f"/api/contests/{CID}/standings")
check("standings ranked", s == 200 and len(rows) == 2)
check("alice ranked 1", rows[0]["participant"] == "Alice" and rows[0]["total"] == 9
      and rows[0]["solved"] == 1)

# ---- plagiarism ----
s, pl = req("POST", "/api/auth/register", {"name": "Carol"})
CT = pl.get("token", "")
req("POST", "/api/submit", {"slug": "two-sum", "language": "python",
                            "code": TWO_SUM, "mode": "submit", "contest_id": CID}, token=CT)
s, pl = req("GET", f"/api/contests/{CID}/plagiarism", token=AT)
check("plagiarism finds copy (Alice↔Carol 100%)", s == 200 and any(
    p["a"]["participant"] == "Alice" and p["b"]["participant"] == "Carol"
    for p in pl))

s, pl = req("GET", f"/api/contests/{CID}/plagiarism", token=AL)
check("plagiarism admin-only", s == 403)

# ---- contest end ----
s, e = req("POST", f"/api/contests/{CID}/end", token=AT)
check("end contest", s == 200 and e.get("status") == "ended")
s, r = req("POST", "/api/submit", {"slug": "two-sum", "language": "python",
                                   "code": TWO_SUM, "mode": "submit",
                                   "contest_id": CID}, token=AL)
check("submit after end rejected", s == 403 and r.get("error") == "contest_ended")

# ---- report ----
print("=" * 60)
print(f"CONTEST FEATURES: {PASS} passed, {FAIL} failed")
print("=" * 60)
for r in RESULTS:
    print(r)
sys.exit(1 if FAIL else 0)
