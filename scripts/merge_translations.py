#!/usr/bin/env python3
"""Merge a detect_blocks.py result with a translation file into the blocks
JSON that build_translated_psd.mjs consumes.

Usage: python merge_translations.py <stem>_detect.json <translations.json> <out blocks.json>

translations.json:
  {"texts":  {"1": "texto do bloco 1", "2": "...", ...},      # 1-based block index
   "styles": {"3": {"rotate": 90, "color": "#ffffff"}, ...}}  # optional, per block
Blocks with no entry get an empty text box. Unknown indices are reported.
"""
import json
import sys


def main():
    det_path, tr_path, out_path = sys.argv[1:4]
    det = json.load(open(det_path))
    tr = json.load(open(tr_path))
    n = len(det["text_blocks"])
    texts = [""] * n
    styles = [{} for _ in range(n)]
    bad = []
    for k, v in tr.get("texts", {}).items():
        i = int(k) - 1
        if 0 <= i < n:
            texts[i] = v
        else:
            bad.append(k)
    for k, v in tr.get("styles", {}).items():
        i = int(k) - 1
        if 0 <= i < n:
            styles[i] = v
        else:
            bad.append(k)
    out = dict(det)
    out["texts"] = texts
    out["styles"] = styles
    json.dump(out, open(out_path, "w"), ensure_ascii=False, indent=1)
    missing = [i + 1 for i, t in enumerate(texts) if not t]
    print(f"{out_path}: {n} blocks, {n - len(missing)} translated"
          + (f", EMPTY: {missing}" if missing else "")
          + (f", UNKNOWN keys: {bad}" if bad else ""))


if __name__ == "__main__":
    main()
