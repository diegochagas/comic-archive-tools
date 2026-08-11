#!/usr/bin/env python3
"""Assemble a project's approved pages into a .cbz.

Reads projects/<p>/work/<issue>/approved/page_NN.(png|jpg|jpeg|webp),
normalizes each page to JPEG portrait (max height from project.json), names
pages per the project's naming patterns, and zips them into
projects/<p>/out/<cbz_name>.

Usage: python3 pipeline/assemble_cbz.py [--project NAME] <issue> [issues...]
"""
import argparse
import io
import re
import sys
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import resolve_project


def assemble(pdir: Path, cfg: dict, issue: str) -> None:
    approved = pdir / "work" / issue / "approved"
    pages = sorted(
        p for p in approved.iterdir()
        if re.match(r"page_\d+\.(png|jpe?g|webp)$", p.name, re.I)
    ) if approved.exists() else []
    if not pages:
        sys.exit(f"No approved pages in {approved}")

    expected = len(list((pdir / "jobs" / issue).glob("page_*.json")))
    if len(pages) != expected:
        print(f"WARNING: issue {issue} has {len(pages)}/{expected} approved pages — assembling anyway")

    cbz = cfg.get("cbz", {})
    max_h = cbz.get("max_height", 2048)
    folder = cbz.get("folder", "{title}{issue}").format(issue=issue, title=cfg.get("title", pdir.name))
    page_name = cbz.get("page_name", "page{issue}{page:02d}.jpg")
    out_name = cbz.get("out_name", "{title}{issue}.cbz").format(issue=issue, title=cfg.get("title", pdir.name))

    out = pdir / "out" / out_name
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
        for p in pages:
            n = int(re.search(r"\d+", p.name).group())
            im = Image.open(p).convert("RGB")
            if im.height > max_h:
                im = im.resize((round(im.width * max_h / im.height), max_h), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=92)
            z.writestr(f"{folder}/{page_name.format(issue=issue, page=n)}", buf.getvalue())
    print(f"Wrote {out} ({len(pages)} pages)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", "-p", default=None)
    ap.add_argument("issues", nargs="+")
    args = ap.parse_args()

    name, cfg, pdir = resolve_project(args.project)
    for issue in args.issues:
        assemble(pdir, cfg, str(issue))
