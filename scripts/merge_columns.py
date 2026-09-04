#!/usr/bin/env python3
"""Merge detect_blocks.py blocks into translation-sized paragraphs.

Japanese vertical text is detected one COLUMN per block (an interview page
yields 100+ thin boxes); multi-line horizontal captions sometimes come out one
LINE per block. Neither is a sensible Photoshop text box for a translation,
so this groups:
  - thin vertical columns (h > 2.5 w) that sit side by side (gap <= 1.6 x
    column width) and overlap vertically (>= 40% of the shorter one)
  - wide horizontal lines (w > 2.5 h) stacked with a gap <= 0.6 x line height
    and >= 50% horizontal overlap
into one block (union bbox), iterating until nothing merges. Everything else
is kept as is. Output goes to <stem>_merged.json (same schema as the detect
json, blocks in reading order: top -> bottom, and right -> left for columns
within a row) plus <stem>_merged_overlay.jpg (numbered, `--width` px wide) for
reading the source and for the 1-based indices used in the translation file.

Usage: python merge_columns.py <stem>_detect.json [...] [--width 1000]
"""
import argparse
import json
import os

import cv2


def is_col(b): return b[3] > 2.5 * b[2]
def is_line(b): return b[2] > 2.5 * b[3]


def overlap(a0, a1, b0, b1):
    return max(0, min(a1, b1) - max(a0, b0))


def kind(b):
    if b[2] <= 130 and b[3] >= 1.2 * b[2]:
        return "col"
    if is_line(b):
        return "line"
    return "other"


def can_merge(a, b, ka, kb, ca, cb):
    """a, b boxes; ka, kb kinds; ca, cb the column width of each group."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if ka == "col" and kb == "col":
        cw = max(ca, cb)
        hgap = max(bx - (ax + aw), ax - (bx + bw))
        vgap = max(by - (ay + ah), ay - (by + bh))
        vo = overlap(ay, ay + ah, by, by + bh) / min(ah, bh)
        # neighbouring columns of one paragraph: adjacent (not overlapping by
        # more than a column) and sharing most of their height
        side = -cw <= hgap <= 1.6 * cw and vo >= 0.6
        # two fragments of ONE column (both still single-column wide)
        stacked = aw <= 130 and bw <= 130 and hgap <= 0 and vgap <= 1.5 * cw
        # a column group sitting right under / over another one whose x-range
        # contains it (columns interrupted by a photo)
        inside = (ax >= bx - cw and ax + aw <= bx + bw + cw) or (bx >= ax - cw and bx + bw <= ax + aw + cw)
        contained = inside and -cw <= vgap <= 1.5 * cw
        return side or stacked or contained
    if ka == "line" and kb == "line":
        gap = max(by - (ay + ah), ay - (by + bh))
        ho = overlap(ax, ax + aw, bx, bx + bw) / min(aw, bw)
        return gap <= 0.6 * max(ah, bh) and ho >= 0.5
    return False


def union(a, b):
    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
    x1, y1 = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
    return [x0, y0, x1 - x0, y1 - y0]


def merge(blocks):
    # items: [box, kind, column width]  (kind/width fixed by the original block)
    items = [[list(b), kind(b), b[2]] for b in blocks]
    changed = True
    while changed:
        changed = False
        out = []
        while items:
            a = items.pop(0)
            i = 0
            while i < len(items):
                b = items[i]
                if can_merge(a[0], b[0], a[1], b[1], a[2], b[2]):
                    a = [union(a[0], b[0]), a[1], max(a[2], b[2])]
                    items.pop(i)
                    changed = True
                else:
                    i += 1
            out.append(a)
        items = out
    return [it[0] for it in items]


def reading_order(blocks):
    """Rows by vertical position (top), right-to-left inside a row for
    column groups, left-to-right for horizontal text."""
    blocks = sorted(blocks, key=lambda b: b[1])
    rows, cur = [], []
    for b in blocks:
        if cur and b[1] > cur[0][1] + 0.5 * cur[0][3]:
            rows.append(cur); cur = []
        cur.append(b)
    if cur:
        rows.append(cur)
    out = []
    for r in rows:
        if all(is_col(b) or b[3] > b[2] for b in r):
            r.sort(key=lambda b: -(b[0] + b[2]))
        else:
            r.sort(key=lambda b: b[0])
        out.extend(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("detect_json", nargs="+")
    ap.add_argument("--width", type=int, default=1000)
    a = ap.parse_args()
    for p in a.detect_json:
        d = json.load(open(p))
        raw = d["text_blocks"]
        merged = reading_order(merge(raw))
        d["text_blocks_detected"] = raw
        d["text_blocks"] = merged
        stem = os.path.basename(p)[:-len("_detect.json")]
        out_json = os.path.join(os.path.dirname(p), f"{stem}_merged.json")
        json.dump(d, open(out_json, "w"), indent=1)
        src = d.get("source_for_psd") or d["source"]
        img = cv2.imread(src, cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
        H, W = img.shape[:2]
        s = a.width / W
        ov = cv2.resize(img, (a.width, round(H * s)), interpolation=cv2.INTER_AREA)
        for i, (x, y, w, h) in enumerate(merged, 1):
            x0, y0, x1, y1 = round(x * s), round(y * s), round((x + w) * s), round((y + h) * s)
            cv2.rectangle(ov, (x0, y0), (x1, y1), (0, 0, 255), 1)
            cv2.rectangle(ov, (x0, max(0, y0 - 14)), (x0 + 8 * len(str(i)) + 4, y0), (0, 0, 255), -1)
            cv2.putText(ov, str(i), (x0 + 2, max(10, y0 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imwrite(os.path.join(os.path.dirname(p), f"{stem}_merged_overlay.jpg"), ov,
                    [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"{stem}: {len(raw)} -> {len(merged)} blocks")


if __name__ == "__main__":
    main()
