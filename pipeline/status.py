#!/usr/bin/env python3
"""Show generation progress across all projects and issues.

Usage: python3 pipeline/status.py [--project NAME]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROJECTS, list_projects

ap = argparse.ArgumentParser()
ap.add_argument("--project", "-p", default=None)
args = ap.parse_args()

for proj in ([args.project] if args.project else list_projects()):
    work = PROJECTS / proj / "work"
    if not work.exists():
        continue
    print(f"== {proj} ==")
    for issue_dir in sorted(work.iterdir()):
        state_path = issue_dir / "state.json"
        if not state_path.exists():
            continue
        state = json.loads(state_path.read_text(encoding="utf-8"))
        counts: dict[str, int] = {}
        for page in state.values():
            counts[page["status"]] = counts.get(page["status"], 0) + 1
        approved = counts.get("approved", 0)
        summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        print(f"  Issue {issue_dir.name}: {approved}/{len(state)} approved  ({summary})")
        for num, page in sorted(state.items()):
            if page["status"] == "needs_review":
                print(f"      page {num} NEEDS REVIEW — {page.get('notes', '')}")
