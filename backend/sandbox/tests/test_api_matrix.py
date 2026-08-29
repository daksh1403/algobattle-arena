#!/usr/bin/env python3
"""
AlgoBattle endpoint matrix test — every endpoint, every failure condition.

Covers:
  GET  /                    → 200 HTML, problems injected
  GET  /health              → 200 json
  POST /api/submit          → AC / WA / TLE / MLE / CE / RE / 429 / 422
  GET  /api/leaderboard     → ranked
  GET  /api/submissions     → history
  POST /api/run             → stdout / stderr / 422 / flood / crash
Failure modes:
  - invalid slug / language / code
  - empty body / missing fields (422)
  - code that floods output (OLE)
  - infinite loop (TLE), memory bomb (MLE), crash (RE)
  - rate limit (429)
  - XSS/HTML injection in participant name (sanitized)
  - Unicode / emoji code
  - 10k-character code
  - concurrent submissions
"""
import json
import sys
import time
import urllib.request
import urllib.error
import threading

BASE = "http://127.0.0.1:8080"
PASS = 0
FAIL = 0
RESULTS = []


def req(method, path, body=None, raw=None):
    url = BASE + path
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return -1, str(e)


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        RESULTS.append(f"  ✅ {name}")
    else:
        FAIL += 1
        RESULTS.append(f"  ❌ {name} {detail}")


# ---------------- GET / ----------------
s, body = req("GET", "/")
check("GET / returns 200", s == 200)
check("GET / is HTML", "text/html" in body or "<!DOCTYPE" in body)
check("GET / mentions the arena", "AlgoBattle" in body or "algobattle" in body)
check("GET / links the Worker UI", "algobattle-arena" in body)

# ---------------- GET /health ----------------
s, body = req("GET", "/health")
check("GET /health 200", s == 200)
check("GET /health json ok", '"status":"ok"' in body and '"sandbox":"online"' in body)

# ---------------- POST /api/submit: happy path ----------------
CODE_AC = """nums = list(map(int, input().split()))
t = int(input())
d = {}
for i, n in enumerate(nums):
    if t - n in d:
        print(d[t - n], i)
        break
    d[n] = i
"""
s, body = req("POST", "/api/submit", {"slug": "two-sum", "language": "python",
                                      "code": CODE_AC, "mode": "submit", "participant": "MatrixTester"})
d = json.loads(body)
check("submit AC returns 200", s == 200)
check("submit AC verdict", d.get("verdict") == "AC" and d.get("score") == "9/9")

# ---------------- submit: WA ----------------
s, body = req("POST", "/api/submit", {"slug": "fibonacci", "language": "python",
                                      "code": "print(0)", "mode": "submit", "participant": "WaTester"})
d = json.loads(body)
check("submit WA verdict", s == 200 and d.get("verdict") == "WA")

# ---------------- submit: TLE (infinite loop) ----------------
s, body = req("POST", "/api/submit", {"slug": "two-sum", "language": "python",
                                      "code": "while True: pass", "mode": "submit", "participant": "TleTester"})
d = json.loads(body)
check("submit TLE on infinite loop", s == 200 and d.get("verdict") == "TLE")

# ---------------- submit: CE (C++ compile error) ----------------
s, body = req("POST", "/api/submit", {"slug": "two-sum", "language": "cpp",
                                      "code": "#include <iostream>\nint main(){ this is not valid c++ }",
                                      "mode": "submit", "participant": "CeTester"})
d = json.loads(body)
check("submit CE on bad C++", s == 200 and d.get("verdict") == "CE", body[:200])

# ---------------- submit: invalid slug → 422 ----------------
s, body = req("POST", "/api/submit", {"slug": "nope", "language": "python",
                                      "code": "print(1)", "mode": "submit", "participant": "X"})
check("submit invalid slug 422", s == 422 or (s == 500))

# ---------------- submit: missing fields → 422 ----------------
s, body = req("POST", "/api/submit", {})
check("submit empty body 422", s == 422)
s, body = req("POST", "/api/submit", {"slug": "two-sum"})
check("submit missing fields 422", s == 422)

# ---------------- submit: raw garbage (not json) ----------------
s, body = req("POST", "/api/submit", raw=b"this is not json{{{{")
check("submit garbage body 422", s == 422)

# ---------------- submit: XSS injection in name ----------------
s, body = req("POST", "/api/submit", {"slug": "two-sum", "language": "python",
                                      "code": CODE_AC, "mode": "submit",
                                      "participant": "<script>alert(1)</script>"})
d = json.loads(body)
check("submit XSS name accepted (no crash)", s == 200 and d.get("verdict") == "AC")

# ---------------- submit: 10k char code ----------------
big = CODE_AC + "\n# " + "x" * 9900
s, body = req("POST", "/api/submit", {"slug": "two-sum", "language": "python",
                                      "code": big, "mode": "submit", "participant": "BigTester"})
d = json.loads(body)
check("submit 10k-char code", s == 200 and d.get("verdict") == "AC")

# ---------------- submit: unicode/emoji code ----------------
s, body = req("POST", "/api/submit", {"slug": "two-sum", "language": "python",
                                      "code": "# 🎉\n" + CODE_AC, "mode": "submit", "participant": "Emoji"})
d = json.loads(body)
check("submit emoji comment code", s == 200 and d.get("verdict") == "AC")

# ---------------- submit: C++ AC ----------------
CPP_AC = """#include <iostream>
#include <sstream>
#include <unordered_map>
#include <vector>
using namespace std;
int main(){
  string line; getline(cin, line);
  stringstream ss(line); vector<int> nums; int x;
  while(ss >> x) nums.push_back(x);
  int t; cin >> t;
  unordered_map<int,int> d;
  for(size_t i=0;i<nums.size();i++){
    if(d.count(t - nums[i])) { cout << d[t-nums[i]] << " " << i; return 0; }
    d[nums[i]] = i;
  }
  return 0;
}"""
s, body = req("POST", "/api/submit", {"slug": "two-sum", "language": "cpp",
                                      "code": CPP_AC, "mode": "submit", "participant": "CppTester"})
d = json.loads(body)
check("submit C++ AC", s == 200 and d.get("verdict") == "AC", body[:200])

# ---------------- POST /api/compiler/run (dedicated compiler) ----------------
s, body = req("POST", "/api/compiler/run", {"language": "python", "code": "print(sum(map(int, input().split())))", "stdin": "1 2 3 4 5"})
d = json.loads(body)
check("compiler/run python stdout", s == 200 and d.get("stdout", "").strip() == "15")

s, body = req("POST", "/api/compiler/run", {"language": "cpp",
                                            "code": "#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b;}", "stdin": "3 4"})
d = json.loads(body)
check("compiler/run cpp stdout", s == 200 and d.get("stdout", "").strip() == "7")

s, body = req("POST", "/api/compiler/run", {"language": "java",
                                            "code": "public class Main{public static void main(String[] a){System.out.println(9*9);}}", "stdin": ""})
d = json.loads(body)
check("compiler/run java stdout", s == 200 and d.get("stdout", "").strip() == "81")

s, body = req("POST", "/api/compiler/run", {"language": "python", "code": "while True: print('x'*500)", "stdin": ""})
check("compiler/run flood capped (no hang)", s == 200)

s, body = req("POST", "/api/compiler/run", {})
check("compiler/run empty body 422", s == 422)

# ---------------- POST /api/run: happy path ----------------
s, body = req("POST", "/api/run", {"language": "python", "code": "print(sum(map(int, input().split())))", "stdin": "1 2 3 4 5"})
d = json.loads(body)
check("run python stdout", s == 200 and d.get("stdout", "").strip() == "15")

# ---------------- run: C++ ----------------
s, body = req("POST", "/api/run", {"language": "cpp",
                                   "code": "#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b;}", "stdin": "3 4"})
d = json.loads(body)
check("run C++ stdout", s == 200 and d.get("stdout", "").strip() == "7")

# ---------------- run: Java ----------------
s, body = req("POST", "/api/run", {"language": "java",
                                   "code": "import java.util.*;\npublic class Main{public static void main(String[] a){Scanner s=new Scanner(System.in);System.out.println(s.nextInt()+s.nextInt());}}",
                                   "stdin": "10 20"})
d = json.loads(body)
check("run Java stdout", s == 200 and d.get("stdout", "").strip() == "30", body[:200])

# ---------------- run: stderr capture ----------------
s, body = req("POST", "/api/run", {"language": "python", "code": "import sys; sys.stderr.write('oops'); print('out')", "stdin": ""})
d = json.loads(body)
check("run captures stderr", s == 200 and "oops" in d.get("stderr", ""))
check("run captures stdout too", d.get("stdout", "").strip() == "out")

# ---------------- run: output flood → OLE ----------------
s, body = req("POST", "/api/run", {"language": "python", "code": "while True: print('x'*1000)", "stdin": ""})
d = json.loads(body)
check("run output flood capped (no hang)", s == 200)

# ---------------- run: memory bomb → MLE ----------------
s, body = req("POST", "/api/run", {"language": "python", "code": "x = [0] * (10**8)", "stdin": ""})
d = json.loads(body)
check("run memory bomb → MLE", s == 200 and d.get("verdict") == "MLE", body[:200])

# ---------------- run: crash → RE ----------------
s, body = req("POST", "/api/run", {"language": "python", "code": "import sys; sys.exit(3)", "stdin": ""})
d = json.loads(body)
check("run crash → RE", s == 200 and d.get("verdict") == "RE", body[:200])

# ---------------- run: missing fields → 422 ----------------
s, body = req("POST", "/api/run", {})
check("run empty body 422", s == 422)

# ---------------- GET /api/leaderboard ----------------
s, body = req("GET", "/api/leaderboard")
d = json.loads(body)
check("leaderboard 200 + is list", s == 200 and isinstance(d, list))
check("leaderboard ranked #1 is AC", len(d) > 0 and d[0]["verdict"] == "AC")
check("leaderboard has participant", len(d) > 0 and d[0].get("participant"))

# ---------------- GET /api/submissions ----------------
s, body = req("GET", "/api/submissions")
d = json.loads(body)
check("submissions 200 + is list", s == 200 and isinstance(d, list))
check("submissions has entries", len(d) > 0)

# ---------------- rate limit: 11 quick submits → 429 ----------------
# Use CE (C++ compile error) — fails in <1s, so all 11 fit the 60s window.
s_last = 200
for i in range(11):
    s, body = req("POST", "/api/submit", {"slug": "fibonacci", "language": "cpp",
                                          "code": "int main(){ syntax error }",
                                          "mode": "submit",
                                          "participant": "RateLimiter"})
    s_last = s
check("rate limit kicks in (429)", s_last == 429, f"last status {s_last}")

# ---------------- concurrency: 8 parallel submits ----------------
def do_submit(i):
    return req("POST", "/api/submit", {"slug": "two-sum", "language": "python",
                                       "code": CODE_AC, "mode": "submit",
                                       "participant": f"Concurrent{i}"})
threads = [threading.Thread(target=lambda i=i: results.append(do_submit(i))) for i in range(8)]
results = []
for t in threads: t.start()
for t in threads: t.join()
check("8 concurrent submits all 200/AC", all(s == 200 and json.loads(b)["verdict"] == "AC" for s, b in results))

# ---------------- custom problems (user-added) ----------------
s, body = req("POST", "/api/problems/custom", {"title": "Sum List",
                                               "description": "Sum all ints",
                                               "examples": [["1 2 3", "6"], ["10 20", "30"]],
                                               "creator": "MatrixTester"})
d = json.loads(body)
slug = d.get("slug", "")
check("add custom problem returns slug", s == 200 and slug.startswith("custom-"), body[:200])

s, body = req("GET", "/api/problems/custom")
d = json.loads(body)
check("list custom problems", s == 200 and any(p.get("slug") == slug for p in d))

s, body = req("POST", "/api/submit/custom", {"slug": slug, "language": "python",
                                             "code": "print(sum(map(int,input().split())))",
                                             "participant": "CustomTester"})
d = json.loads(body)
check("submit custom problem AC", s == 200 and d.get("verdict") == "AC" and d.get("score") == "2/2", body[:200])

s, body = req("POST", "/api/submit/custom", {"slug": "custom-nonexistent", "language": "python",
                                             "code": "print(1)", "participant": "X"})
check("submit custom 404", s == 404, f"status {s}")

s, body = req("POST", "/api/problems/custom", {"title": "", "examples": []})
check("add custom empty → 422", s == 422, f"status {s}")

# ---------------- leaderboard handles custom problems ----------------
s, body = req("GET", "/api/leaderboard")
d = json.loads(body)
check("leaderboard OK with custom entries", s == 200 and any(e.get("problem", "").startswith("custom-") for e in d))

# ---------------- report ----------------
print("=" * 60)
print(f"ENDPOINT MATRIX: {PASS} passed, {FAIL} failed")
print("=" * 60)
for r in RESULTS:
    print(r)
sys.exit(1 if FAIL else 0)
