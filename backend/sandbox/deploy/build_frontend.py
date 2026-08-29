#!/usr/bin/env python3
"""
Build the static frontend for Cloudflare.
Injects the problem bank + Python boilerplates into public/index.html.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(HERE, "public")
TEMPLATE = os.path.join(PUBLIC, "index.html")

# Make the sandbox package importable (web_arena does `from sandbox...`)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))   # backend/
sys.path.insert(0, os.path.dirname(HERE))                    # sandbox/


def main():
    sys.path.insert(0, os.path.join(HERE, ".."))
    from web_arena import PROBLEMS

    problems_json = json.dumps([
        {"slug": p.slug, "title": p.title, "difficulty": p.difficulty,
         "description": p.description, "examples": p.examples,
         "hidden_count": len(p.hidden_tests)}
        for p in PROBLEMS
    ])
    boilerplates_json = json.dumps({p.slug: p.solution for p in PROBLEMS})

    with open(TEMPLATE) as f:
        html = f.read()

    html = html.replace("__PROBLEMS__", problems_json)
    html = html.replace("__BOILERPLATES__", boilerplates_json)

    with open(TEMPLATE, "w") as f:
        f.write(html)

    print(f"Built {TEMPLATE}")
    print(f"  {len(PROBLEMS)} problems injected")
    print("Ready for: wrangler deploy")


if __name__ == "__main__":
    main()
