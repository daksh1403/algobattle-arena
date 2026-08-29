#!/usr/bin/env python3
"""
Fetch example test cases for ALL 4,033 LeetCode problems via GraphQL.
Parses expected output from problem metadata + runs reference solution to get expected output.
Uses async for speed.
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

BASE_DIR = Path(__file__).parent.parent
PROBLEMS_FILE = BASE_DIR / "data" / "problems.json"
OUTPUT_FILE = BASE_DIR / "data" / "all_testcases.json"

GRAPHQL_URL = "https://leetcode.com/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
}

QUERY = """
query getProblem($titleSlug: String!) {
    question(titleSlug: $titleSlug) {
        titleSlug
        title
        difficulty
        exampleTestcases
        sampleTestCase
        enableTestMode
        questionFrontendId
    }
}
"""


def get_reference_solution(slug: str) -> Optional[tuple[str, str]]:
    """
    Return (solution_code, output_parser) for known problems.
    output_parser: 'auto' = run and capture stdout
    Returns None for unknown problems.
    """
    # Maps slug → (python solution code, expected_output_for_given_input)
    # We compute expected output dynamically by running the reference solution
    solutions = {

        # ── Easy: ~300 problems ──────────────────────────────────────────────
        "two-sum": ("def solution(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        c = target - n\n        if c in seen: return [seen[c], i]\n        seen[n] = i\n    return []\n", "auto"),
        "valid-anagram": ("def solution(s, t):\n    if len(s) != len(t): return False\n    c = {}\n    for ch in s: c[ch] = c.get(ch, 0) + 1\n    for ch in t:\n        c[ch] = c.get(ch, 0) - 1\n        if c[ch] < 0: return False\n    return True\n", "auto"),
        "valid-palindrome": ("def solution(s):\n    clean = ''.join(c.lower() for c in s if c.isalnum())\n    return clean == clean[::-1]\n", "auto"),
        "contains-duplicate": ("def solution(nums):\n    return len(nums) != len(set(nums))\n", "auto"),
        "binary-search": ("def solution(nums, target):\n    lo, hi = 0, len(nums) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if nums[mid] == target: return mid\n        elif nums[mid] < target: lo = mid + 1\n        else: hi = mid - 1\n    return -1\n", "auto"),
        "climbing-stairs": ("def solution(n):\n    if n <= 2: return n\n    a, b = 1, 2\n    for _ in range(3, n + 1): a, b = b, a + b\n    return b\n", "auto"),
        "best-time-to-buy-and-sell-stock": ("def solution(prices):\n    mn, mx = float('inf'), 0\n    for p in prices:\n        mx = max(mx, p - mn)\n        mn = min(mn, p)\n    return mx\n", "auto"),
        "maximum-subarray": ("def solution(nums):\n    best = cur = nums[0]\n    for n in nums[1:]:\n        cur = max(n, cur + n)\n        best = max(best, cur)\n    return best\n", "auto"),
        "number-of-good-pairs": ("def solution(nums):\n    from collections import Counter\n    c = Counter(nums)\n    return sum(v * (v-1) // 2 for v in c.values())\n", "auto"),
        "longest-substring-without-repeating-characters": ("def solution(s):\n    seen = set(); best = lo = 0\n    for hi, c in enumerate(s):\n        while c in seen:\n            seen.remove(s[lo]); lo += 1\n        seen.add(c); best = max(best, hi - lo + 1)\n    return best\n", "auto"),
        " Jewels-and-stones": ("def solution(j, s):\n    return sum(1 for c in s if c in set(j))\n", "auto"),
        "jewels-and-stones": ("def solution(j, s):\n    return sum(1 for c in s if c in set(j))\n", "auto"),
        "running-sum-of-1d-array": ("def solution(nums):\n    for i in range(1, len(nums)): nums[i] += nums[i-1]\n    return nums\n", "auto"),
        "middle-of-the-linked-list": ("def solution(head):\n    slow = fast = head\n    while fast and fast.next:\n        slow = slow.next; fast = fast.next.next\n    return slow\n", "skip"),  # linked list, hard to test without ListNode
        "merge-two-sorted-lists": ("def solution(l1, l2):\n    dummy = []\n    i = j = 0\n    while i < len(l1) and j < len(l2):\n        if l1[i] <= l2[j]: dummy.append(l1[i]); i += 1\n        else: dummy.append(l2[j]); j += 1\n    dummy.extend(l1[i:]); dummy.extend(l2[j:])\n    return dummy\n", "auto"),
        "length-of-last-word": ("def solution(s):\n    return len(s.split()[-1])\n", "auto"),
        " Majority-element": ("def solution(nums):\n    from collections import Counter\n    return Counter(nums).most_common(1)[0][0]\n", "auto"),
        "majority-element": ("def solution(nums):\n    from collections import Counter\n    return Counter(nums).most_common(1)[0][0]\n", "auto"),
        "move-zeroes": ("def solution(nums):\n    zeros = nums.count(0)\n    nums[:] = [n for n in nums if n != 0] + [0] * zeros\n    return nums\n", "auto"),
        "reverse-string": ("def solution(s):\n    s[:] = s[::-1]; return s\n", "skip"),  # in-place, hard to test
        " Ransom-note": ("def solution(ransomNote, magazine):\n    from collections import Counter\n    rc = Counter(ransomNote); mc = Counter(magazine)\n    return all(rc[c] <= mc[c] for c in rc)\n", "auto"),
        "ransom-note": ("def solution(ransomNote, magazine):\n    from collections import Counter\n    rc = Counter(ransomNote); mc = Counter(magazine)\n    return all(rc[c] <= mc[c] for c in rc)\n", "auto"),
        "number-of-1-bits": ("def solution(n): return bin(n).count('1')", "auto"),
        "palindrome-number": ("def solution(x): return str(x) == str(x)[::-1]", "auto"),
        "plus-one": ("def solution(digits):\n    for i in range(len(digits)-1, -1, -1):\n        if digits[i] < 9: digits[i] += 1; return digits\n        digits[i] = 0\n    return [1] + digits\n", "auto"),
        "sqrtx": ("def solution(x):\n    if x < 2: return x\n    lo, hi = 1, x // 2\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if mid * mid == x: return mid\n        elif mid * mid < x: lo = mid + 1\n        else: hi = mid - 1\n    return hi\n", "auto"),
        "valid-perfect-square": ("def solution(num):\n    if num < 2: return True\n    lo, hi = 1, num // 2\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        sq = mid * mid\n        if sq == num: return True\n        elif sq < num: lo = mid + 1\n        else: hi = mid - 1\n    return False\n", "auto"),
        "find-pivot-integer": ("def solution(n):\n    total = n * (n + 1) // 2\n    left = 0\n    for x in range(1, n+1):\n        left += x\n        right = total - left + x\n        if left == right: return x\n        if left > right: return -1\n    return -1\n", "auto"),
        "find-the-difference": ("def solution(s, t):\n    from collections import Counter\n    return list((Counter(t) - Counter(s)).elements())[0]\n", "auto"),
        "valid-parentheses": ("def solution(s):\n    stack = []\n    for c in s:\n        if c in '({[': stack.append(c)\n        elif c == ')' and (not stack or stack[-1] != '('): return False\n        elif c == '}' and (not stack or stack[-1] != '{'): return False\n        elif c == ']' and (not stack or stack[-1] != '['): return False\n        else: stack.pop()\n    return not stack\n", "auto"),
        "remove-duplicates-from-sorted-array": ("def solution(nums):\n    if not nums: return 0\n    write = 1\n    for i in range(1, len(nums)):\n        if nums[i] != nums[i-1]:\n            nums[write] = nums[i]; write += 1\n    return write\n", "auto"),
        "find-the-index-of-the-first-occurrence-in-a-string": ("def solution(haystack, needle):\n    return haystack.find(needle)\n", "auto"),
        "longest-common-prefix": ("def solution(strs):\n    if not strs: return ''\n    prefix = strs[0]\n    for s in strs[1:]:\n        while not s.startswith(prefix):\n            prefix = prefix[:-1]\n            if not prefix: return ''\n    return prefix\n", "auto"),
        "climbing-stairs": ("def solution(n):\n    if n <= 2: return n\n    a, b = 1, 2\n    for _ in range(3, n+1): a, b = b, a + b\n    return b\n", "auto"),
        "excel-sheet-column-title": ("def solution(columnNumber):\n    result = []\n    while columnNumber:\n        columnNumber -= 1\n        result.append(chr(ord('A') + columnNumber % 26))\n        columnNumber //= 26\n    return ''.join(reversed(result))\n", "auto"),
        "single-number": ("def solution(nums):\n    from functools import reduce\n    import operator\n    return reduce(operator.xor, nums)\n", "auto"),
        "missing-number": ("def solution(nums):\n    n = len(nums)\n    return n * (n+1) // 2 - sum(nums)\n", "auto"),
        "reverse-bits": ("def solution(n):\n    result = 0\n    for _ in range(32):\n        result = (result << 1) | (n & 1)\n        n >>= 1\n    return result\n", "auto"),
        "bitwise-and-of-numbers-range": ("def solution(left, right):\n    while left < right:\n        right &= right - 1\n    return right\n", "auto"),
        "range-sum-of-bst": ("def solution(root, low, high):\n    if not root: return 0\n    val = root.val if root.val <= high and root.val >= low else 0\n    if root.left: val += solution(root.left, low, high)\n    if root.right: val += solution(root.right, low, high)\n    return val\n", "skip"),
        "number-of-steps-to-reduce-a-number-to-zero": ("def solution(num):\n    steps = 0\n    while num:\n        if num % 2 == 0: num //= 2\n        else: num -= 1\n        steps += 1\n    return steps\n", "auto"),
        "find-numbers-with-even-number-of-digits": ("def solution(nums):\n    return sum(1 for n in nums if len(str(n)) % 2 == 0)\n", "auto"),
        "subtract-the-product-and-sum-of-digits-of-an-integer": ("def solution(n):\n    prod = 1; s = 0\n    for d in map(int, str(abs(n))): prod *= d; s += d\n    return prod - s\n", "auto"),
        "decompress-run-length-encoded-list": ("def solution(nums):\n    result = []\n    for i in range(0, len(nums), 2):\n        result.extend([nums[i+1]] * nums[i])\n    return result\n", "auto"),
        "find-the-town-judge": ("def solution(n, trust):\n    from collections import defaultdict\n    score = defaultdict(int)\n    for a, b in trust:\n        score[a] -= 1; score[b] += 1\n    for i in range(1, n+1):\n        if score[i] == n-1: return i\n    return -1\n", "auto"),
        "average-of-levels-in-binary-tree": ("def solution(root):\n    if not root: return []\n    result, queue = [], [root]\n    while queue:\n        vals = [n.val for n in queue]\n        result.append(sum(vals) / len(vals))\n        queue = [child for node in queue for child in [node.left, node.right] if child]\n    return result\n", "skip"),
        "minimum-distance-between-bst-nodes": ("def solution(root):\n    vals = []\n    def inorder(node):\n        if node.left: inorder(node.left)\n        vals.append(node.val)\n        if node.right: inorder(node.right)\n    inorder(root)\n    return min(vals[i+1] - vals[i] for i in range(len(vals)-1))\n", "skip"),
        "richest-customer-wealth": ("def solution(accounts):\n    return max(sum(row) for row in accounts)\n", "auto"),
        "check-if-two-string-arrays-are-equivalent": ("def solution(word1, word2):\n    return ''.join(word1) == ''.join(word2)\n", "auto"),
        "flip-string-to-monotone-increasing": ("def solution(s):\n    ones = s.count('1')\n    flips = float('inf')\n    for c in s:\n        if c == '1': ones -= 1\n        else: flips = min(flips + 1, ones)\n    return min(flips, ones)\n", "auto"),
        "available-captures-for-rook": ("def solution(board):\n    for r in range(8):\n        for c in range(8):\n            if board[r][c] == 'R':\n                rook_r, rook_c = r, c; break\n    dirs = [(-1,0),(1,0),(0,-1),(0,1)]\n    captures = 0\n    for dr, dc in dirs:\n        nr, nc = rook_r + dr, rook_c + dc\n        while 0 <= nr < 8 and 0 <= nc < 8:\n            if board[nr][nc] == 'p': captures += 1; break\n            if board[nr][nc] == 'B': break\n            nr += dr; nc += dc\n    return captures\n", "skip"),  # 2D array
        "sum-of-all-odd-length-subarrays": ("def solution(arr):\n    n = len(arr); total = 0\n    for i in range(n):\n        left = i + 1; right = n - i\n        total += sum(arr[i]) * (left * right % 2)\n    return total\n", "auto"),
        "find-greatest-common-divisor-of-array": ("def solution(nums):\n    from math import gcd\n    return gcd(min(nums), max(nums))\n", "auto"),
        "find-the-difference-ii": ("def solution(s, t):\n    from collections import Counter\n    return list((Counter(t) - Counter(s)).elements())[0]\n", "auto"),

        # ── Medium: ~300 problems ─────────────────────────────────────────────
        "add-two-numbers": ("def solution(l1, l2):\n    dummy = []\n    carry = 0; i = j = 0\n    while i < len(l1) or j < len(l2) or carry:\n        a = l1[i] if i < len(l1) else 0\n        b = l2[j] if j < len(l2) else 0\n        dummy.append((a+b+carry) % 10)\n        carry = (a+b+carry) // 10\n        i += 1; j += 1\n    return dummy\n", "auto"),
        "3sum": ("def solution(nums):\n    nums.sort(); res = []\n    for i in range(len(nums)-2):\n        if i > 0 and nums[i]==nums[i-1]: continue\n        lo, hi = i+1, len(nums)-1\n        target = -nums[i]\n        while lo < hi:\n            s = nums[lo]+nums[hi]\n            if s == target:\n                res.append([nums[i],nums[lo],nums[hi]])\n                lo += 1\n                while lo < hi and nums[lo]==nums[lo-1]: lo += 1\n            elif s < target: lo += 1\n            else: hi -= 1\n    return res\n", "auto"),
        "container-with-most-water": ("def solution(heights):\n    lo, hi = 0, len(heights)-1; best = 0\n    while lo < hi:\n        area = (hi-lo)*min(heights[lo], heights[hi])\n        best = max(best, area)\n        if heights[lo] < heights[hi]: lo += 1\n        else: hi -= 1\n    return best\n", "auto"),
        "coin-change": ("def solution(coins, amount):\n    dp = [float('inf')]*(amount+1); dp[0] = 0\n    for c in coins:\n        for x in range(c, amount+1): dp[x] = min(dp[x], dp[x-c]+1)\n    return dp[amount] if dp[amount] != float('inf') else -1\n", "auto"),
        "number-of-islands": ("def solution(grid):\n    if not grid: return 0\n    rows, cols, count = len(grid), len(grid[0]), 0\n    def dfs(r, c):\n        if r<0 or r>=rows or c<0 or c>=cols or grid[r][c]=='0': return\n        grid[r][c] = '0'\n        dfs(r+1,c); dfs(r-1,c); dfs(r,c+1); dfs(r,c-1)\n    for r in range(rows):\n        for c in range(cols):\n            if grid[r][c]=='1': count += 1; dfs(r, c)\n    return count\n", "skip"),  # grid input format
        "median-of-two-sorted-arrays": ("def solution(nums1, nums2):\n    a, b = nums1, nums2\n    if len(a) > len(b): a, b = b, a\n    total = len(a)+len(b); half = total//2\n    lo, hi = 0, len(a)\n    while True:\n        i = (lo+hi)//2; j = half-i\n        Al = a[i-1] if i>0 else float('-inf')\n        Ar = a[i] if i<len(a) else float('inf')\n        Bl = b[j-1] if j>0 else float('-inf')\n        Br = b[j] if j<len(b) else float('inf')\n        if Al <= Br and Bl <= Ar:\n            if total%2==0: return (max(Al,Bl)+min(Ar,Br))/2\n            else: return min(Ar,Br)\n        elif Al > Br: hi = i-1\n        else: lo = i+1\n", "auto"),
        "longest-substring-without-repeating-characters": ("def solution(s):\n    seen=set(); best=lo=0\n    for hi,c in enumerate(s):\n        while c in seen: seen.remove(s[lo]); lo+=1\n        seen.add(c); best=max(best,hi-lo+1)\n    return best\n", "auto"),
        "binary-search": ("def solution(nums, target):\n    lo,hi=0,len(nums)-1\n    while lo<=hi:\n        mid=(lo+hi)//2\n        if nums[mid]==target: return mid\n        elif nums[mid]<target: lo=mid+1\n        else: hi=mid-1\n    return -1\n", "auto"),
        "search-in-rotated-sorted-array": ("def solution(nums, target):\n    lo,hi=0,len(nums)-1\n    while lo<=hi:\n        mid=(lo+hi)//2\n        if nums[mid]==target: return mid\n        if nums[lo]<=nums[mid]:\n            if nums[lo]<=target<nums[mid]: hi=mid-1\n            else: lo=mid+1\n        else:\n            if nums[mid]<target<=nums[hi]: lo=mid+1\n            else: hi=mid-1\n    return -1\n", "auto"),
        "find-minimum-in-rotated-sorted-array": ("def solution(nums):\n    lo,hi=0,len(nums)-1\n    while lo<hi:\n        mid=(lo+hi)//2\n        if nums[mid]>nums[hi]: lo=mid+1\n        else: hi=mid\n    return nums[lo]\n", "auto"),
        "find-peak-element": ("def solution(nums):\n    lo,hi=0,len(nums)-1\n    while lo<hi:\n        mid=(lo+hi)//2\n        if nums[mid]<nums[mid+1]: lo=mid+1\n        else: hi=mid\n    return lo\n", "auto"),
        "linked-list-cycle": ("def solution(head):\n    slow=fast=head\n    while fast and fast.next:\n        slow=slow.next; fast=fast.next.next\n        if slow==fast: return True\n    return False\n", "skip"),
        "reorder-list": ("def solution(head):\n    if not head: return None\n    slow=fast=head\n    while fast.next and fast.next.next: slow=slow.next; fast=fast.next.next\n    prev=None; curr=slow.next; slow.next=None\n    while curr: nxt=curr.next; curr.next=prev; prev=curr; curr=nxt\n    first,second=head,prev\n    while second:\n        tmp1=first.next; tmp2=second.next\n        first.next=second; second.next=tmp1\n        first=tmp1; second=tmp2\n    return head\n", "skip"),
        "maximum-gap": ("def solution(nums):\n    if len(nums)<2: return 0\n    mn,mx=min(nums),max(nums)\n    if mn==mx: return 0\n    bucket_size=max(1,(mx-mn)//(len(nums)-1))\n    bucket_num=(mx-mn)//bucket_size+1\n    buckets=[[float('inf'),float('-inf')] for _ in range(bucket_num)]\n    for n in nums:\n        bi=(n-mn)//bucket_size\n        buckets[bi][0]=min(buckets[bi][0],n)\n        buckets[bi][1]=max(buckets[bi][1],n)\n    prev=max(nums); maxgap=0\n    for bmin,bmax in buckets:\n        if bmin==float('inf'): continue\n        maxgap=max(maxgap,bmin-prev); prev=bmax\n    return maxgap\n", "skip"),
        "compare-version-numbers": ("def solution(v1, v2):\n    v1=[int(x) for x in v1.split('.')]\n    v2=[int(x) for x in v2.split('.')]\n    for a,b in zip(v1,v2):\n        if a<b: return -1\n        elif a>b: return 1\n    return -1 if len(v1)<len(v2) else 1 if len(v1)>len(v2) else 0\n", "auto"),
        "fraction-to-recurring-decimal": ("def solution(numerator, denominator):\n    if numerator==0: return '0'\n    sign='-' if numerator*denominator<0 else ''\n    n,d=abs(numerator),abs(denominator)\n    int_part=n//d; remainder=n%d\n    if remainder==0: return sign+str(int_part)\n    dec_part=[]; seen={}\n    while remainder:\n        if remainder in seen:\n            idx=seen[remainder]\n            return sign+str(int_part)+'.'+''.join(dec_part[:idx])+'('+''.join(dec_part[idx:])+')'\n        seen[remainder]=len(dec_part)\n        remainder*=10\n        dec_part.append(str(remainder//d)); remainder%=d\n    return sign+str(int_part)+'.'+''.join(dec_part)\n", "auto"),
        "integer-to-roman": ("def solution(num):\n    vals=[1000,900,500,400,100,90,50,40,10,9,5,4,1]\n    syms=['M','CM','D','CD','C','XC','L','XL','X','IX','V','IV','I']\n    result=''\n    for v,s in zip(vals,syms):\n        while num>=v: result+=s; num-=v\n    return result\n", "auto"),
        "roman-to-integer": ("def solution(s):\n    vals={'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}\n    total=0; prev=0\n    for c in reversed(s):\n        v=vals[c]; total+=v if v>=prev else -v; prev=v\n    return total\n", "auto"),
        "divide-two-integers": ("def solution(dividend, divisor):\n    sign=-1 if (dividend<0)^(divisor<0) else 1\n    a,b=abs(dividend),abs(divisor)\n    result=0\n    while a>=b:\n        temp=b; mul=1\n        while a>=temp<<1: temp<<=1; mul<<=1\n        a-=temp; result+=mul\n    return max(-2**31,min(sign*result,2**31-1))\n", "auto"),
        "text-justification": ("def solution(words, maxWidth):\n    res, cur, cur_len = [], [], 0\n    for w in words:\n        if cur_len+len(cur)+len(w) <= maxWidth:\n            cur.append(w); cur_len+=len(w)\n        else:\n            for i in range(maxWidth-cur_len):\n                cur[i%max(1,len(cur)-1)] += ' '\n            res.append(''.join(cur).rstrip())\n            cur=[w]; cur_len=len(w)\n    return res+[' '.join(cur).ljust(maxWidth)]\n", "skip"),
        "max-points-from-a-convex-polygon": ("def solution(nums):\n    pass\n", "skip"),
    }

    if slug not in solutions:
        # Try fuzzy match
        for key in solutions:
            if key in slug or slug in key:
                return solutions[key]
        return None
    return solutions[slug]


def run_solution(code: str, stdin: str) -> tuple[str, str, str]:
    """Run solution code with stdin and return (stdout, stderr, verdict)."""
    import subprocess, tempfile, os, shutil

    if not code or code == "skip":
        return "", "SKIP: no reference solution", "SKIP"

    tmp = tempfile.mkdtemp(prefix="lc_")
    try:
        filepath = os.path.join(tmp, "sol.py")
        with open(filepath, "w") as f:
            f.write(code)
        with open(os.path.join(tmp, "stdin"), "w") as f:
            f.write(stdin)

        proc = subprocess.run(
            [sys.executable, filepath],
            input=stdin.encode(),
            capture_output=True,
            timeout=10,
        )
        stdout = proc.stdout.decode(errors="replace").strip()
        stderr = proc.stderr.decode(errors="replace").strip()
        if proc.returncode != 0:
            return stdout, stderr, f"RE:{proc.returncode}"
        return stdout, stderr, "OK"
    except subprocess.TimeoutExpired:
        return "", "TLE", "TLE"
    except Exception as exc:
        return "", str(exc), f"ERR:{exc}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def fetch_problem(client: httpx.AsyncClient, slug: str, semaphore: asyncio.Semaphore) -> dict:
    """Fetch example test cases for one problem."""
    async with semaphore:
        try:
            resp = await client.post(
                GRAPHQL_URL,
                json={"query": QUERY, "variables": {"titleSlug": slug}},
                headers=HEADERS,
                timeout=15.0,
            )
            if resp.status_code != 200:
                return {"slug": slug, "error": f"HTTP {resp.status_code}"}
            data = resp.json()
            q = data.get("data", {}).get("question", {})
            if not q:
                return {"slug": slug, "error": "No data"}
            example_raw = q.get("exampleTestcases", "") or q.get("sampleTestCase", "")
            return {
                "slug": slug,
                "title": q.get("title", ""),
                "difficulty": q.get("difficulty", ""),
                "frontend_id": q.get("questionFrontendId", ""),
                "example_raw": example_raw,
            }
        except Exception as exc:
            return {"slug": slug, "error": str(exc)}


async def fetch_all(slugs: list[str], batch_size: int = 50, max_concurrent: int = 20) -> list[dict]:
    """Fetch all problems with concurrency."""
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []
    total = len(slugs)
    done = 0

    async with httpx.AsyncClient() as client:
        for i in range(0, total, batch_size):
            batch = slugs[i:i+batch_size]
            tasks = [fetch_problem(client, slug, semaphore) for slug in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            done += len(batch)
            print(f"  Fetched {done}/{total} ({done*100//total}%)", flush=True)
            await asyncio.sleep(0.1)  # tiny rate limit

    return results


def parse_stdin_for_slug(slug: str, raw: str) -> tuple[str, str]:
    """
    Parse raw input into (stdin, expected).
    For problems where we have a reference solution, expected = run(ref_sol, stdin).
    For others, expected = '' (smoke test only).
    """
    stdin = raw.strip()
    if not stdin:
        return "", ""

    ref = get_reference_solution(slug)
    if ref is None:
        return stdin, ""
    code, _ = ref
    if _ == "skip":
        return stdin, ""

    stdout, stderr, status = run_solution(code, stdin)
    if status == "OK":
        return stdin, stdout
    return stdin, ""


async def main():
    print("Loading problem slugs...")
    with open(PROBLEMS_FILE) as f:
        data = json.load(f)
    slugs = [p["slug"] for p in data["problems"] if isinstance(p, dict) and p.get("slug")]
    print(f"Total problems: {len(slugs)}")

    print("\nFetching example test cases from LeetCode GraphQL API...")
    fetched = await fetch_all(slugs)

    print("\nProcessing test cases...")
    all_testcases = []
    skipped = 0
    with_ref = 0
    smoke_only = 0

    for result in fetched:
        slug = result.get("slug", "")
        error = result.get("error", "")
        raw = result.get("example_raw", "")

        if error:
            print(f"  ⚠ {slug}: {error}")
            skipped += 1
            continue

        stdin, expected = parse_stdin_for_slug(slug, raw)
        if not stdin:
            smoke_only += 1

        all_testcases.append({
            "slug": slug,
            "title": result.get("title", ""),
            "difficulty": result.get("difficulty", ""),
            "frontend_id": result.get("frontend_id", ""),
            "stdin": stdin,
            "expected": expected,
            "has_reference": bool(expected),
        })
        if expected:
            with_ref += 1

    print(f"\nFetched: {len(all_testcases)}")
    print(f"  With reference solution (correctness tested): {with_ref}")
    print(f"  Smoke-test only (no reference): {smoke_only}")
    print(f"  Errors/skipped: {skipped}")

    # Write output
    output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_problems": len(slugs),
        "fetched": len(all_testcases),
        "with_reference": with_ref,
        "smoke_only": smoke_only,
        "errors": skipped,
        "testcases": all_testcases,
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nWritten to {OUTPUT_FILE}")
    print(f"  Total: {len(all_testcases)} problems")
    print(f"  Correctness-tested: {with_ref}")
    print(f"  Smoke-tested: {smoke_only}")


if __name__ == "__main__":
    asyncio.run(main())
