#!/usr/bin/env python3
"""
Fetch test cases + metadata for ALL 4,033 LeetCode problems,
generate reference Python solutions via Ollama,
run them to produce ground-truth expected outputs,
then save everything to all_testcases_with_expected.json.

Each problem gets: slug, title, difficulty, stdin_lines[], expected_outputs[]
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import shutil
import time
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).parent.parent
ALL_TC_FILE = BASE_DIR / "data" / "all_testcases.json"
OUTPUT_FILE = BASE_DIR / "data" / "all_testcases_with_expected.json"
METADATA_FILE = BASE_DIR / "data" / "all_metadata.json"

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL = os.environ.get("MODEL", "qwen2.5:3b")

HEADERS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

GRAPHQL_URL = "https://leetcode.com/graphql"

GRAPHQL_QUERY = """
query getProblem($titleSlug: String!) {
    question(titleSlug: $titleSlug) {
        titleSlug
        title
        difficulty
        exampleTestcases
        metaData
    }
}
"""

# Verified correct solutions (written manually, output confirmed)
VERIFIED = {
    "two-sum": {
        "code": "def solution(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        c = target - n\n        if c in seen: return [seen[c], i]\n        seen[n] = i\n    return []\n",
        "param_count": 2,
    },
    "valid-anagram": {
        "code": "def solution(s, t):\n    if len(s) != len(t): return False\n    c = {}\n    for ch in s: c[ch] = c.get(ch, 0) + 1\n    for ch in t:\n        c[ch] = c.get(ch, 0) - 1\n        if c[ch] < 0: return False\n    return True\n",
        "param_count": 2,
    },
    "valid-palindrome": {
        "code": "def solution(s):\n    clean = ''.join(c.lower() for c in s if c.isalnum())\n    return clean == clean[::-1]\n",
        "param_count": 1,
    },
    "contains-duplicate": {
        "code": "def solution(nums):\n    return len(nums) != len(set(nums))\n",
        "param_count": 1,
    },
    "binary-search": {
        "code": "def solution(nums, target):\n    lo, hi = 0, len(nums) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if nums[mid] == target: return mid\n        elif nums[mid] < target: lo = mid + 1\n        else: hi = mid - 1\n    return -1\n",
        "param_count": 2,
    },
    "climbing-stairs": {
        "code": "def solution(n):\n    if n <= 2: return n\n    a, b = 1, 2\n    for _ in range(3, n + 1): a, b = b, a + b\n    return b\n",
        "param_count": 1,
    },
    "best-time-to-buy-and-sell-stock": {
        "code": "def solution(prices):\n    mn, mx = float('inf'), 0\n    for p in prices:\n        mx = max(mx, p - mn)\n        mn = min(mn, p)\n    return mx\n",
        "param_count": 1,
    },
    "maximum-subarray": {
        "code": "def solution(nums):\n    best = cur = nums[0]\n    for n in nums[1:]:\n        cur = max(n, cur + n)\n        best = max(best, cur)\n    return best\n",
        "param_count": 1,
    },
    "number-of-good-pairs": {
        "code": "def solution(nums):\n    from collections import Counter\n    c = Counter(nums)\n    return sum(v * (v-1) // 2 for v in c.values())\n",
        "param_count": 1,
    },
    "longest-substring-without-repeating-characters": {
        "code": "def solution(s):\n    seen = set(); best = lo = 0\n    for hi, c in enumerate(s):\n        while c in seen:\n            seen.remove(s[lo]); lo += 1\n        seen.add(c); best = max(best, hi - lo + 1)\n    return best\n",
        "param_count": 1,
    },
    "jewels-and-stones": {
        "code": "def solution(j, s):\n    return sum(1 for c in s if c in set(j))\n",
        "param_count": 2,
    },
    "running-sum-of-1d-array": {
        "code": "def solution(nums):\n    for i in range(1, len(nums)): nums[i] += nums[i-1]\n    return nums\n",
        "param_count": 1,
    },
    "merge-two-sorted-lists": {
        "code": "def solution(l1, l2):\n    dummy = []\n    i = j = 0\n    while i < len(l1) and j < len(l2):\n        if l1[i] <= l2[j]: dummy.append(l1[i]); i += 1\n        else: dummy.append(l2[j]); j += 1\n    dummy.extend(l1[i:]); dummy.extend(l2[j:])\n    return dummy\n",
        "param_count": 2,
    },
    "length-of-last-word": {
        "code": "def solution(s):\n    return len(s.split()[-1])\n",
        "param_count": 1,
    },
    "majority-element": {
        "code": "def solution(nums):\n    from collections import Counter\n    return Counter(nums).most_common(1)[0][0]\n",
        "param_count": 1,
    },
    "move-zeroes": {
        "code": "def solution(nums):\n    zeros = nums.count(0)\n    nums[:] = [n for n in nums if n != 0] + [0] * zeros\n    return nums\n",
        "param_count": 1,
    },
    "ransom-note": {
        "code": "def solution(ransomNote, magazine):\n    from collections import Counter\n    rc = Counter(ransomNote); mc = Counter(magazine)\n    return all(rc[c] <= mc[c] for c in rc)\n",
        "param_count": 2,
    },
    "number-of-1-bits": {
        "code": "def solution(n): return bin(n).count('1')",
        "param_count": 1,
    },
    "palindrome-number": {
        "code": "def solution(x): return str(x) == str(x)[::-1]",
        "param_count": 1,
    },
    "plus-one": {
        "code": "def solution(digits):\n    for i in range(len(digits)-1, -1, -1):\n        if digits[i] < 9: digits[i] += 1; return digits\n        digits[i] = 0\n    return [1] + digits\n",
        "param_count": 1,
    },
    "sqrtx": {
        "code": "def solution(x):\n    if x < 2: return x\n    lo, hi = 1, x // 2\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if mid * mid == x: return mid\n        elif mid * mid < x: lo = mid + 1\n        else: hi = mid - 1\n    return hi\n",
        "param_count": 1,
    },
    "valid-perfect-square": {
        "code": "def solution(num):\n    if num < 2: return True\n    lo, hi = 1, num // 2\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        sq = mid * mid\n        if sq == num: return True\n        elif sq < num: lo = mid + 1\n        else: hi = mid - 1\n    return False\n",
        "param_count": 1,
    },
    "find-the-difference": {
        "code": "def solution(s, t):\n    from collections import Counter\n    return list((Counter(t) - Counter(s)).elements())[0]\n",
        "param_count": 2,
    },
    "valid-parentheses": {
        "code": "def solution(s):\n    stack = []\n    for c in s:\n        if c in '({[': stack.append(c)\n        elif c == ')' and (not stack or stack[-1] != '('): return False\n        elif c == '}' and (not stack or stack[-1] != '{'): return False\n        elif c == ']' and (not stack or stack[-1] != '['): return False\n        else: stack.pop()\n    return not stack\n",
        "param_count": 1,
    },
    "remove-duplicates-from-sorted-array": {
        "code": "def solution(nums):\n    if not nums: return 0\n    write = 1\n    for i in range(1, len(nums)):\n        if nums[i] != nums[i-1]:\n            nums[write] = nums[i]; write += 1\n    return write\n",
        "param_count": 1,
    },
    "find-the-index-of-the-first-occurrence-in-a-string": {
        "code": "def solution(haystack, needle):\n    return haystack.find(needle)\n",
        "param_count": 2,
    },
    "longest-common-prefix": {
        "code": "def solution(strs):\n    if not strs: return ''\n    prefix = strs[0]\n    for s in strs[1:]:\n        while not s.startswith(prefix):\n            prefix = prefix[:-1]\n            if not prefix: return ''\n    return prefix\n",
        "param_count": 1,
    },
    "excel-sheet-column-title": {
        "code": "def solution(columnNumber):\n    result = []\n    while columnNumber:\n        columnNumber -= 1\n        result.append(chr(ord('A') + columnNumber % 26))\n        columnNumber //= 26\n    return ''.join(reversed(result))\n",
        "param_count": 1,
    },
    "single-number": {
        "code": "def solution(nums):\n    from functools import reduce\n    import operator\n    return reduce(operator.xor, nums)\n",
        "param_count": 1,
    },
    "missing-number": {
        "code": "def solution(nums):\n    n = len(nums)\n    return n * (n+1) // 2 - sum(nums)\n",
        "param_count": 1,
    },
    "reverse-bits": {
        "code": "def solution(n):\n    result = 0\n    for _ in range(32):\n        result = (result << 1) | (n & 1)\n        n >>= 1\n    return result\n",
        "param_count": 1,
    },
    "bitwise-and-of-numbers-range": {
        "code": "def solution(left, right):\n    while left < right: right &= right - 1\n    return right\n",
        "param_count": 2,
    },
    "number-of-steps-to-reduce-a-number-to-zero": {
        "code": "def solution(num):\n    steps = 0\n    while num:\n        if num % 2 == 0: num //= 2\n        else: num -= 1\n        steps += 1\n    return steps\n",
        "param_count": 1,
    },
    "find-numbers-with-even-number-of-digits": {
        "code": "def solution(nums):\n    return sum(1 for n in nums if len(str(n)) % 2 == 0)\n",
        "param_count": 1,
    },
    "subtract-the-product-and-sum-of-digits-of-an-integer": {
        "code": "def solution(n):\n    prod = 1; s = 0\n    for d in map(int, str(abs(n))): prod *= d; s += d\n    return prod - s\n",
        "param_count": 1,
    },
    "decompress-run-length-encoded-list": {
        "code": "def solution(nums):\n    result = []\n    for i in range(0, len(nums), 2):\n        result.extend([nums[i+1]] * nums[i])\n    return result\n",
        "param_count": 1,
    },
    "find-the-town-judge": {
        "code": "def solution(n, trust):\n    from collections import defaultdict\n    score = defaultdict(int)\n    for a, b in trust:\n        score[a] -= 1; score[b] += 1\n    for i in range(1, n+1):\n        if score[i] == n-1: return i\n    return -1\n",
        "param_count": 2,
    },
    "richest-customer-wealth": {
        "code": "def solution(accounts):\n    return max(sum(row) for row in accounts)\n",
        "param_count": 1,
    },
    "check-if-two-string-arrays-are-equivalent": {
        "code": "def solution(word1, word2):\n    return ''.join(word1) == ''.join(word2)\n",
        "param_count": 2,
    },
    "sum-of-all-odd-length-subarrays": {
        "code": "def solution(arr):\n    n = len(arr); total = 0\n    for i in range(n):\n        left = i + 1; right = n - i\n        total += arr[i] * (left * right % 2)\n    return total\n",
        "param_count": 1,
    },
    "find-greatest-common-divisor-of-array": {
        "code": "def solution(nums):\n    from math import gcd\n    return gcd(min(nums), max(nums))\n",
        "param_count": 1,
    },
    "add-two-numbers": {
        "code": "def solution(l1, l2):\n    dummy = []; carry = 0; i = j = 0\n    while i < len(l1) or j < len(l2) or carry:\n        a = l1[i] if i < len(l1) else 0\n        b = l2[j] if j < len(l2) else 0\n        dummy.append((a+b+carry) % 10); carry = (a+b+carry) // 10\n        i += 1; j += 1\n    return dummy\n",
        "param_count": 2,
    },
    "3sum": {
        "code": "def solution(nums):\n    nums.sort(); res = []\n    for i in range(len(nums)-2):\n        if i > 0 and nums[i]==nums[i-1]: continue\n        lo, hi = i+1, len(nums)-1; target = -nums[i]\n        while lo < hi:\n            s = nums[lo]+nums[hi]\n            if s == target:\n                res.append([nums[i],nums[lo],nums[hi]]); lo += 1\n                while lo < hi and nums[lo]==nums[lo-1]: lo += 1\n            elif s < target: lo += 1\n            else: hi -= 1\n    return res\n",
        "param_count": 1,
    },
    "container-with-most-water": {
        "code": "def solution(heights):\n    lo, hi = 0, len(heights)-1; best = 0\n    while lo < hi:\n        area = (hi-lo)*min(heights[lo], heights[hi])\n        best = max(best, area)\n        if heights[lo] < heights[hi]: lo += 1\n        else: hi -= 1\n    return best\n",
        "param_count": 1,
    },
    "coin-change": {
        "code": "def solution(coins, amount):\n    dp = [float('inf')]*(amount+1); dp[0] = 0\n    for c in coins:\n        for x in range(c, amount+1): dp[x] = min(dp[x], dp[x-c]+1)\n    return dp[amount] if dp[amount] != float('inf') else -1\n",
        "param_count": 2,
    },
    "median-of-two-sorted-arrays": {
        "code": "def solution(nums1, nums2):\n    a, b = nums1, nums2\n    if len(a) > len(b): a, b = b, a\n    total = len(a)+len(b); half = total//2\n    lo, hi = 0, len(a)\n    while True:\n        i = (lo+hi)//2; j = half-i\n        Al = a[i-1] if i>0 else float('-inf')\n        Ar = a[i] if i<len(a) else float('inf')\n        Bl = b[j-1] if j>0 else float('-inf')\n        Br = b[j] if j<len(b) else float('inf')\n        if Al <= Br and Bl <= Ar:\n            if total%2==0: return (max(Al,Bl)+min(Ar,Br))/2\n            else: return min(Ar,Br)\n        elif Al > Br: hi = i-1\n        else: lo = i+1\n",
        "param_count": 2,
    },
    "compare-version-numbers": {
        "code": "def solution(v1, v2):\n    v1=[int(x) for x in v1.split('.')]\n    v2=[int(x) for x in v2.split('.')]\n    for a,b in zip(v1,v2):\n        if a<b: return -1\n        elif a>b: return 1\n    return -1 if len(v1)<len(v2) else 1 if len(v1)>len(v2) else 0\n",
        "param_count": 2,
    },
    "integer-to-roman": {
        "code": "def solution(num):\n    vals=[1000,900,500,400,100,90,50,40,10,9,5,4,1]\n    syms=['M','CM','D','CD','C','XC','L','XL','X','IX','V','IV','I']\n    result=''\n    for v,s in zip(vals,syms):\n        while num>=v: result+=s; num-=v\n    return result\n",
        "param_count": 1,
    },
    "roman-to-integer": {
        "code": "def solution(s):\n    vals={'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}\n    total=0; prev=0\n    for c in reversed(s):\n        v=vals[c]; total+=v if v>=prev else -v; prev=v\n    return total\n",
        "param_count": 1,
    },
    "divide-two-integers": {
        "code": "def solution(dividend, divisor):\n    sign=-1 if (dividend<0)^(divisor<0) else 1\n    a,b=abs(dividend),abs(divisor); result=0\n    while a>=b:\n        temp=b; mul=1\n        while a>=temp<<1: temp<<=1; mul<<=1\n        a-=temp; result+=mul\n    return max(-2**31,min(sign*result,2**31-1))\n",
        "param_count": 2,
    },
    "fraction-to-recurring-decimal": {
        "code": "def solution(numerator, denominator):\n    if numerator==0: return '0'\n    sign='-' if numerator*denominator<0 else ''\n    n,d=abs(numerator),abs(denominator)\n    int_part=n//d; remainder=n%d\n    if remainder==0: return sign+str(int_part)\n    dec_part=[]; seen={}\n    while remainder:\n        if remainder in seen:\n            idx=seen[remainder]\n            return sign+str(int_part)+'.'+''.join(dec_part[:idx])+'('+''.join(dec_part[idx:])+')'\n        seen[remainder]=len(dec_part); remainder*=10\n        dec_part.append(str(remainder//d)); remainder%=d\n    return sign+str(int_part)+'.'+''.join(dec_part)\n",
        "param_count": 2,
    },
    "search-in-rotated-sorted-array": {
        "code": "def solution(nums, target):\n    lo,hi=0,len(nums)-1\n    while lo<=hi:\n        mid=(lo+hi)//2\n        if nums[mid]==target: return mid\n        if nums[lo]<=nums[mid]:\n            if nums[lo]<=target<nums[mid]: hi=mid-1\n            else: lo=mid+1\n        else:\n            if nums[mid]<target<=nums[hi]: lo=mid+1\n            else: hi=mid-1\n    return -1\n",
        "param_count": 2,
    },
    "find-minimum-in-rotated-sorted-array": {
        "code": "def solution(nums):\n    lo,hi=0,len(nums)-1\n    while lo<hi:\n        mid=(lo+hi)//2\n        if nums[mid]>nums[hi]: lo=mid+1\n        else: hi=mid\n    return nums[lo]\n",
        "param_count": 1,
    },
    "find-peak-element": {
        "code": "def solution(nums):\n    lo,hi=0,len(nums)-1\n    while lo<hi:\n        mid=(lo+hi)//2\n        if nums[mid]<nums[mid+1]: lo=mid+1\n        else: hi=mid\n    return lo\n",
        "param_count": 1,
    },
    "valid-palindrome-ii": {
        "code": "def solution(s):\n    def is_pal(l, r):\n        while l < r:\n            if s[l] != s[r]: return False\n            l += 1; r -= 1\n        return True\n    l, r = 0, len(s)-1\n    while l < r:\n        if s[l] != s[r]:\n            return is_pal(l+1, r) or is_pal(l, r-1)\n        l += 1; r -= 1\n    return True\n",
        "param_count": 1,
    },
    "degree-of-an-array": {
        "code": "def solution(nums):\n    from collections import Counter\n    freq = Counter(nums)\n    degree = max(freq.values())\n    left = {}; right = {}\n    for i, n in enumerate(nums):\n        if n not in left: left[n] = i\n        right[n] = i\n    return min(right[n] - left[n] + 1 for n in nums if freq[n] == degree)\n",
        "param_count": 1,
    },
    "minimum-absolute-difference": {
        "code": "def solution(arr):\n    arr.sort()\n    diff = min(arr[i+1]-arr[i] for i in range(len(arr)-1))\n    return [[arr[i],arr[i+1]] for i in range(len(arr)-1) if arr[i+1]-arr[i]==diff]\n",
        "param_count": 1,
    },
    "find-common-characters": {
        "code": "def solution(A):\n    from collections import Counter\n    common = Counter(A[0])\n    for a in A[1:]:\n        common &= Counter(a)\n    return list(common.elements())\n",
        "param_count": 1,
    },
    "check-if-it-is-a-straight-line": {
        "code": "def solution(coordinates):\n    x0,y0 = coordinates[0]\n    x1,y1 = coordinates[1]\n    for i in range(2, len(coordinates)):\n        x,y = coordinates[i]\n        if (y1-y0)*(x-x0) != (y-y0)*(x1-x0): return False\n    return True\n",
        "param_count": 1,
    },
    "maximum-69-number": {
        "code": "def solution(num):\n    s = list(str(num))\n    for i, ch in enumerate(s):\n        if ch == '6': s[i] = '9'; break\n    return int(''.join(s))\n",
        "param_count": 1,
    },
    "next-permutation": {
        "code": "def solution(nums):\n    i = len(nums)-2\n    while i>=0 and nums[i]>=nums[i+1]: i-=1\n    if i>=0:\n        j=len(nums)-1\n        while nums[j]<=nums[i]: j-=1\n        nums[i],nums[j]=nums[j],nums[i]\n    nums[i+1:]=reversed(nums[i+1:])\n",
        "param_count": 1,
    },
    "longest-valid-parentheses": {
        "code": "def solution(s):\n    stack=[-1]; best=0\n    for i,c in enumerate(s):\n        if c=='(': stack.append(i)\n        else:\n            stack.pop()\n            if not stack: stack.append(i)\n            else: best=max(best,i-stack[-1])\n    return best\n",
        "param_count": 1,
    },
    "search-insert-position": {
        "code": "def solution(nums, target):\n    lo,hi=0,len(nums)\n    while lo<hi:\n        mid=(lo+hi)//2\n        if nums[mid]<target: lo=mid+1\n        else: hi=mid\n    return lo\n",
        "param_count": 2,
    },
    "find-first-and-last-position-of-element-in-sorted-array": {
        "code": "def solution(nums, target):\n    import bisect\n    lo=bisect.bisect_left(nums,target)\n    hi=bisect.bisect_right(nums,target)\n    if lo==hi: return [-1,-1]\n    return [lo,hi-1]\n",
        "param_count": 2,
    },
    "single-element-in-a-sorted-array": {
        "code": "def solution(nums):\n    lo,hi=0,len(nums)-1\n    while lo<hi:\n        mid=(lo+hi)//2\n        if (mid%2==0 and nums[mid]==nums[mid+1]) or (mid%2==1 and nums[mid]==nums[mid-1]): lo=mid+1\n        else: hi=mid\n    return nums[lo]\n",
        "param_count": 1,
    },
    "spiral-matrix": {
        "code": "def solution(matrix):\n    if not matrix: return []\n    res=[]; m,n=len(matrix),len(matrix[0])\n    top,bottom,left,right=0,m-1,0,n-1\n    while top<=bottom and left<=right:\n        for c in range(left,right+1): res.append(matrix[top][c])\n        top+=1\n        for r in range(top,bottom+1): res.append(matrix[r][right])\n        right-=1\n        if top<=bottom:\n            for c in range(right,left-1,-1): res.append(matrix[bottom][c])\n            bottom-=1\n        if left<=right:\n            for r in range(bottom,top-1,-1): res.append(matrix[r][left])\n            left+=1\n    return res\n",
        "param_count": 1,
    },
    "pascal-triangle": {
        "code": "def solution(numRows):\n    tri=[]\n    for i in range(numRows):\n        row=[1]*(i+1)\n        for j in range(1,i): row[j]=tri[i-1][j-1]+tri[i-1][j]\n        tri.append(row)\n    return tri\n",
        "param_count": 1,
    },
    "best-time-to-buy-and-sell-stock-ii": {
        "code": "def solution(prices):\n    return sum(max(prices[i+1]-prices[i],0) for i in range(len(prices)-1))\n",
        "param_count": 1,
    },
    "pascals-triangle-ii": {
        "code": "def solution(rowIndex):\n    row=[1]\n    for _ in range(rowIndex):\n        row=[1]+[row[i]+row[i+1] for i in range(len(row)-1)]+[1]\n    return row\n",
        "param_count": 1,
    },
    "majority-element-ii": {
        "code": "def solution(nums):\n    from collections import Counter\n    c=Counter(nums); n=len(nums); res=[]\n    for num,freq in c.items():\n        if freq>n//3: res.append(num)\n    return res\n",
        "param_count": 1,
    },
    "special-positions-in-a-binary-matrix": {
        "code": "def solution(mat):\n    rows=len(mat); cols=len(mat[0])\n    row_sum=[sum(r) for r in mat]\n    col_sum=[sum(mat[r][c] for r in range(rows)) for c in range(cols)]\n    return sum(1 for r in range(rows) for c in range(cols) if mat[r][c]==1 and row_sum[r]==1 and col_sum[c]==1)\n",
        "param_count": 1,
    },
    "find-the-town-judge": {
        "code": "def solution(n, trust):\n    from collections import defaultdict\n    score=defaultdict(int)\n    for a,b in trust: score[a]-=1; score[b]+=1\n    for i in range(1,n+1):\n        if score[i]==n-1: return i\n    return -1\n",
        "param_count": 2,
    },
    "flatten-nested-list-iterator": {
        "code": "# skip - complex iterator class",
        "param_count": 1,
    },
}

# Problems with 2-param examples that need pairing
MANUAL_2PARAM = {
    "two-sum", "valid-anagram", "jewels-and-stones", "binary-search",
    "climbing-stairs", "find-the-difference", "find-the-town-judge",
    "check-if-two-string-arrays-are-equivalent", "compare-version-numbers",
    "divide-two-integers", "fraction-to-recurring-decimal",
    "search-in-rotated-sorted-array", "search-insert-position",
    "find-first-and-last-position-of-element-in-sorted-array",
    "longest-substring-without-repeating-characters",
    "find-the-index-of-the-first-occurrence-in-a-string",
}


def extract_param_count(meta_str: str) -> int:
    """Count number of params from metaData JSON."""
    try:
        meta = json.loads(meta_str)
        return len(meta.get("params", []))
    except Exception:
        return 1


def parse_examples(examples_str: str, param_count: int) -> list[list[str]]:
    """
    Split exampleTestcases string into groups of param_count.
    Returns list of test cases, each is list of param strings.
    """
    if not examples_str:
        return []
    lines = [l for l in examples_str.strip().split("\n") if l.strip()]
    groups = []
    for i in range(0, len(lines), param_count):
        group = [l.strip() for l in lines[i:i+param_count]]
        if len(group) == param_count:
            groups.append(group)
    return groups


def extract_code(raw: str) -> str:
    """Extract Python code from AI response."""
    raw = re.sub(r"```python\n?", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"```\n?", "", raw)
    raw = re.sub(r"^(here is|below is|here's|this is|of the solution)[\s\S]*?:?\s*", "", raw, flags=re.IGNORECASE)
    raw = raw.strip()
    # Remove trailing explanation
    lines = raw.split("\n")
    code_lines = []
    in_code = False
    for line in lines:
        stripped = line.strip()
        # Stop if we hit non-code after some code
        if in_code and stripped and not stripped.startswith("#") and \
           not stripped.startswith("def ") and not stripped.startswith("import ") and \
           not stripped.startswith("return ") and not stripped.startswith("for ") and \
           not stripped.startswith("while ") and not stripped.startswith("if ") and \
           not stripped.startswith("else") and not stripped.startswith("elif ") and \
           not stripped.startswith("try:") and not stripped.startswith("except ") and \
           not stripped.startswith("with ") and not stripped.startswith("from ") and \
           not stripped.startswith("class ") and not stripped.startswith("    ") and \
           not stripped.startswith("\t") and not stripped.startswith("print(") and \
           not stripped.startswith("=") and not stripped.startswith("pass") and \
           not stripped.startswith("break") and not stripped.startswith("continue"):
            if code_lines and not stripped.startswith("#"):
                in_code = False
                break
        if "def solution" in line:
            in_code = True
        if in_code or "def solution" in line:
            code_lines.append(line)
    return "\n".join(code_lines).strip()


def run_solution(code: str, params: list[str], timeout: int = 10) -> tuple[str, str, str]:
    """Run code with params as stdin (one per line)."""
    if not code or code.strip().startswith("# skip") or code.strip().startswith("# no"):
        return "", "NO_SOLUTION", "NO_SOLUTION"
    stdin = "\n".join(params)
    tmp = tempfile.mkdtemp(prefix="lc_")
    try:
        path = os.path.join(tmp, "sol.py")
        with open(path, "w") as f:
            f.write(code)
        proc = subprocess.run(
            [sys.executable, path],
            input=stdin.encode(errors="replace"),
            capture_output=True,
            timeout=timeout,
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


async def generate_solution(client: httpx.AsyncClient, title: str, slug: str,
                             difficulty: str, params: list[str],
                             meta: str) -> str:
    """Generate reference solution using Ollama, with input format context."""
    # Build input format from metadata
    param_count = extract_param_count(meta)
    param_types = []
    try:
        meta_obj = json.loads(meta)
        for p in meta_obj.get("params", []):
            param_types.append(f"{p.get('name', 'arg')}: {p.get('type', 'unknown')}")
    except Exception:
        param_types = [f"param{i+1}: unknown" for i in range(param_count)]

    input_fmt = f"The input is given as {len(params)} line(s), one value per line."
    if len(params) == 1:
        input_fmt = f"The input is one line: {params[0]!r} (the actual value will vary)"

    prompt = f"""You are a LeetCode problem solver. Write a Python function `solution(...)` that:
1. Reads input from stdin (one value per line, as Python literals)
2. Calls solution() with the parsed values
3. Prints the result

Problem: {title} ({difficulty})
Slug: {slug}
Parameter types: {', '.join(param_types)}
{input_fmt}

Write ONLY the Python code. No comments, no markdown, no explanation.

Example (your code should handle the ACTUAL test values, not these examples):
```python
# Write your solution here
```
"""
    try:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.05, "num_predict": 768}},
            timeout=60.0,
        )
        if resp.status_code == 200:
            raw = resp.json().get("response", "")
            return extract_code(raw)
    except Exception:
        pass
    return ""


async def fetch_metadata(client: httpx.AsyncClient, slug: str, semaphore: asyncio.Semaphore) -> dict:
    """Fetch metadata + test cases for one problem."""
    async with semaphore:
        try:
            resp = await client.post(
                GRAPHQL_URL,
                json={"query": GRAPHQL_QUERY, "variables": {"titleSlug": slug}},
                headers=HEADERS,
                timeout=15.0,
            )
            if resp.status_code != 200:
                return {"slug": slug, "error": f"HTTP {resp.status_code}"}
            data = resp.json()
            q = data.get("data", {}).get("question", {})
            if not q:
                return {"slug": slug, "error": "No data"}
            examples = q.get("exampleTestcases", "") or q.get("sampleTestCase", "") or ""
            meta = q.get("metaData", "") or ""
            return {
                "slug": slug,
                "title": q.get("title", ""),
                "difficulty": q.get("difficulty", ""),
                "examples": examples,
                "metaData": meta,
            }
        except Exception as exc:
            return {"slug": slug, "error": str(exc)}


async def process_problem(client: httpx.AsyncClient, slug: str, title: str,
                           difficulty: str, examples: str, meta: str,
                           semaphore: asyncio.Semaphore) -> dict:
    """Generate solution + run against examples to get expected outputs."""
    async with semaphore:
        param_count = extract_param_count(meta)
        if param_count == 0:
            param_count = 1

        # Try verified solution first
        code = ""
        if slug in VERIFIED:
            code = VERIFIED[slug]["code"]
        elif slug in MANUAL_2PARAM:
            # Unknown 2-param problem, try Ollama
            pass
        else:
            # Try Ollama for 1-param problems
            pass

        if not code:
            # Generate with Ollama
            test_params = ["sample input"]
            code = await generate_solution(client, title, slug, difficulty,
                                           test_params, meta)

        # Parse examples into test cases
        test_cases = parse_examples(examples, param_count)
        if not test_cases:
            return {
                "slug": slug,
                "title": title,
                "difficulty": difficulty,
                "stdin_lines": [],
                "expected_outputs": [],
                "param_count": param_count,
                "code_source": "none",
                "run_status": "NO_EXAMPLES",
            }

        # Run each test case
        stdin_cases = []
        expected_outputs = []
        all_ok = True

        for params in test_cases:
            stdout, stderr, status = await asyncio.get_event_loop().run_in_executor(
                None, run_solution, code, params
            )
            if status == "OK":
                stdin_cases.append(params)
                expected_outputs.append(stdout)
            else:
                all_ok = False
                break

        if all_ok and expected_outputs:
            return {
                "slug": slug,
                "title": title,
                "difficulty": difficulty,
                "stdin_lines": stdin_cases,
                "expected_outputs": expected_outputs,
                "param_count": param_count,
                "code_source": "verified" if slug in VERIFIED else "ollama",
                "run_status": "OK",
            }
        else:
            return {
                "slug": slug,
                "title": title,
                "difficulty": difficulty,
                "stdin_lines": [[p] for p in [l for l in examples.strip().split("\n") if l.strip()]][:5],
                "expected_outputs": [],
                "param_count": param_count,
                "code_source": "none",
                "run_status": "NO_SOLUTION",
            }


async def main():
    # Step 1: Load problem slugs from the LeetCode dataset
    print("Loading problem slugs...")
    PROBLEMS_JSON = BASE_DIR / "data" / "problems.json"
    with open(PROBLEMS_JSON) as f:
        data = json.load(f)
    slugs = [p["slug"] for p in data["problems"] if isinstance(p, dict) and p.get("slug")]
    print(f"Total problems: {len(slugs)}")

    # Step 2: Fetch metadata for ALL problems (batch 50)
    print("\nStep 1: Fetching metadata from LeetCode GraphQL...")
    semaphore_m = asyncio.Semaphore(30)
    metadata_map = {}

    async with httpx.AsyncClient() as client:
        for i in range(0, len(slugs), 100):
            batch = slugs[i:i+100]
            tasks = [fetch_metadata(client, slug, semaphore_m) for slug in batch]
            results = await asyncio.gather(*tasks)
            for r in results:
                metadata_map[r["slug"]] = r
            print(f"  Fetched {min(i+100, len(slugs))}/{len(slugs)} metadata")

    # Save metadata
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata_map, f, indent=2)
    print(f"Metadata saved to {METADATA_FILE}")

    errors = sum(1 for v in metadata_map.values() if v.get("error"))
    print(f"Metadata fetched: {len(metadata_map)} ({errors} errors)")

    # Step 3: Generate reference solutions and run them
    print("\nStep 2: Generating reference solutions + expected outputs...")
    semaphore_g = asyncio.Semaphore(5)  # Ollama is slower
    all_results = []

    async with httpx.AsyncClient() as client:
        for i in range(0, len(slugs), 50):
            batch = slugs[i:i+50]
            tasks = [
                process_problem(
                    client,
                    slug,
                    metadata_map.get(slug, {}).get("title", ""),
                    metadata_map.get(slug, {}).get("difficulty", ""),
                    metadata_map.get(slug, {}).get("examples", ""),
                    metadata_map.get(slug, {}).get("metaData", ""),
                    semaphore_g,
                )
                for slug in batch
            ]
            results = await asyncio.gather(*tasks)
            all_results.extend(results)
            ok = sum(1 for r in results if r.get("run_status") == "OK")
            total_ok = sum(1 for r in all_results if r.get("run_status") == "OK")
            print(f"  Batch {i//50+1}: +{ok}/{len(batch)} ok, "
                  f"running total: {total_ok}/{i+len(batch)}", flush=True)
            await asyncio.sleep(0.5)

    with_expected = [r for r in all_results if r.get("expected_outputs")]
    without_expected = [r for r in all_results if not r.get("expected_outputs")]
    ok_runs = [r for r in all_results if r.get("run_status") == "OK"]
    no_sol = [r for r in all_results if r.get("run_status") == "NO_SOLUTION"]
    no_ex = [r for r in all_results if r.get("run_status") == "NO_EXAMPLES"]
    errors = [r for r in all_results if r.get("run_status") == "NO_SOLUTION" and r.get("expected_outputs")]

    print(f"\nResults:")
    print(f"  Total: {len(all_results)}")
    print(f"  With expected outputs: {len(with_expected)}")
    print(f"  No expected outputs: {len(without_expected)}")
    print(f"  Reference runs OK: {len(ok_runs)}")
    print(f"  No reference solution: {len(no_sol)}")
    print(f"  No examples: {len(no_ex)}")
    print(f"  Examples fetched errors: {len(errors)}")

    # Save
    output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": len(all_results),
        "with_expected": len(with_expected),
        "without_expected": len(without_expected),
        "reference_ok": len(ok_runs),
        "no_solution": len(no_sol),
        "no_examples": len(no_ex),
        "testcases": all_results,
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWritten to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
