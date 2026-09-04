#!/usr/bin/env python3
"""Turn a merged block list + a translation file into the blocks JSON that
build_translated_psd.mjs consumes.

Usage: python assemble_translation.py <stem>_merged.json <stem>.json <out>_blocks.json
                                      [--overlay-width 1000]

Translation file (all coordinates in OVERLAY pixels - the numbered
<stem>_merged_overlay.jpg is `--overlay-width` px wide - so boxes can be read
straight off that image; they are scaled to page pixels here):

  {"texts":   {"1": "...", "3": "..."},          # 1-based merged-block index
   "styles":  {"1": {"color": "#ffffff", "rotate": 90, "size": 40, "align": "left"}},
   "drop":    [2, 4],                             # blocks to discard
   "box":     {"5": [x, y, w, h]},                # override a block's box
   "add":     [[[x, y, w, h], "text", {style}], ...],   # extra boxes (appended)
   "replace": [[[x, y, w, h], "text", {style}], ...]}   # ignore detection, use only these

Thin vertical boxes (h > 2.5 w and w < 150 page px) get rotate=90 unless the
style says otherwise, so the PT-BR line runs down the column like the
original Japanese did.
"""
import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("merged_json")
    ap.add_argument("translation_json")
    ap.add_argument("out_json")
    ap.add_argument("--overlay-width", type=int, default=1000)
    a = ap.parse_args()

    det = json.load(open(a.merged_json))
    tr = json.load(open(a.translation_json))
    W, H = det["size"]
    s = W / a.overlay_width

    def scale(b):
        x, y, w, h = b
        x0, y0 = max(0, round(x * s)), max(0, round(y * s))
        x1, y1 = min(W, round((x + w) * s)), min(H, round((y + h) * s))
        return [x0, y0, max(1, x1 - x0), max(1, y1 - y0)]

    items = []  # (box, text, style)
    if "replace" in tr:
        for box, text, style in tr["replace"]:
            items.append((scale(box), text, dict(style or {})))
    else:
        drop = set(int(i) for i in tr.get("drop", []))
        texts = {int(k): v for k, v in tr.get("texts", {}).items()}
        styles = {int(k): v for k, v in tr.get("styles", {}).items()}
        boxes = {int(k): v for k, v in tr.get("box", {}).items()}
        n = len(det["text_blocks"])
        for k in list(texts) + list(styles) + list(boxes) + list(drop):
            if not 1 <= k <= n:
                print(f"  WARNING: index {k} out of range (1..{n})")
        for i, b in enumerate(det["text_blocks"], 1):
            if i in drop:
                continue
            box = scale(boxes[i]) if i in boxes else list(b)
            items.append((box, texts.get(i, ""), dict(styles.get(i, {}))))
        for box, text, style in tr.get("add", []):
            items.append((scale(box), text, dict(style or {})))

    for box, text, style in items:
        x, y, w, h = box
        if "rotate" not in style and h > 2.5 * w and w < 150:
            style["rotate"] = 90

    out = dict(det)
    out["text_blocks"] = [it[0] for it in items]
    out["texts"] = [it[1] for it in items]
    out["styles"] = [it[2] for it in items]
    json.dump(out, open(a.out_json, "w"), ensure_ascii=False, indent=1)
    empty = [i + 1 for i, it in enumerate(items) if not it[1].strip()]
    print(f"{a.out_json}: {len(items)} boxes" + (f", EMPTY: {empty}" if empty else ""))


if __name__ == "__main__":
    main()
