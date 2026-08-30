#!/usr/bin/env python3
"""Build a lettering guide per issue: every dialogue/caption line, per page,
in script order, with its context line (which usually names the speaker and
balloon type). Use it side by side with the generated pages to add the text
manually.

Output: projects/<p>/out/lettering_<issue>.md

Usage: python3 pipeline/make_lettering_guide.py [--project NAME] [issues...]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import resolve_project

QUOTE_RE = re.compile(r"[\"“]([^\"”]{2,2000})[\"”]", re.S)


def guide_for_issue(pdir: Path, cfg: dict, issue: str) -> None:
    jobs = sorted((pdir / "jobs" / issue).glob("page_*.json"))
    if not jobs:
        sys.exit(f"No jobs for issue {issue} — run split_scripts.py first")

    lines_out = [f"# Guia de letreiramento — {cfg.get('display_name', pdir.name)} — edição {issue}", ""]
    for jf in jobs:
        j = json.loads(jf.read_text(encoding="utf-8"))
        lines_out.append(f"## Página {j['page']:02d} — {j['title']}")
        lines_out.append("")
        prompt = j["prompt"]
        count = 0
        for m in QUOTE_RE.finditer(prompt):
            quote = m.group(1).strip()
            # context: from the start of the line where the quote begins up to
            # the quote itself — usually "Balloon (Mega):" / "Caption box:"
            line_start = prompt.rfind("\n", 0, m.start()) + 1
            context = prompt[line_start:m.start()].strip().lstrip("-").strip().rstrip(":(").strip()
            count += 1
            if "\n" in quote:
                quoted = "\n".join("   > " + ln for ln in quote.splitlines())
                lines_out.append(f"{count}. **{context or 'texto'}**:")
                lines_out.append(quoted)
            else:
                lines_out.append(f"{count}. **{context or 'texto'}**: “{quote}”")
        if count == 0:
            lines_out.append("*(sem texto nesta página)*")
        lines_out.append("")

    out = pdir / "out" / f"lettering_{issue}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines_out), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", "-p", default=None)
    ap.add_argument("issues", nargs="*")
    args = ap.parse_args()

    name, cfg, pdir = resolve_project(args.project)
    for issue in (args.issues or [str(i) for i in cfg["issues"]]):
        guide_for_issue(pdir, cfg, str(issue))
