#!/usr/bin/env python3
"""Contact sheets of every detected text block, for a reviewer/translator to
read the source text block by block (each crop is labelled with its 1-based
block index, the same number shown in <stem>_overlay.jpg and used for the
"Text N" layer names).

Usage: python block_sheets.py <detect.json> <out_dir> [--sheet-w 1600]
                             [--crop-h 260] [--per-sheet 12] [--rotate N:deg ...]

Writes <out_dir>/<stem>_blocks_01.jpg, _02.jpg ... Each crop is scaled so its
smaller side is legible (vertical columns are shown at full height; use
--rotate 7:-90 to display block 7 turned upright when the source is rotated).
"""
import argparse
import json
import os

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("detect_json")
    ap.add_argument("out_dir")
    ap.add_argument("--sheet-w", type=int, default=1600)
    ap.add_argument("--crop-h", type=int, default=260, help="target crop height (px) for horizontal blocks")
    ap.add_argument("--per-sheet", type=int, default=12)
    ap.add_argument("--rotate", nargs="*", default=[], help="N:deg (deg in 90,-90,180)")
    ap.add_argument("--pad", type=int, default=6, help="context padding around each block (px, page scale)")
    ap.add_argument("--scale", type=float, default=0, help="fixed zoom for every crop (e.g. 0.6); overrides --crop-h")
    ap.add_argument("--sheet-h", type=int, default=2600)
    a = ap.parse_args()

    d = json.load(open(a.detect_json))
    src = d.get("source_for_psd") or d["source"]
    img = cv2.imread(src, cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    H, W = img.shape[:2]
    stem = os.path.splitext(os.path.basename(a.detect_json))[0].replace("_detect", "")
    rot = {int(k): int(v) for k, v in (s.split(":") for s in a.rotate)}
    os.makedirs(a.out_dir, exist_ok=True)

    crops = []
    for i, (x, y, w, h) in enumerate(d["text_blocks"], 1):
        x0, y0 = max(0, x - a.pad), max(0, y - a.pad)
        x1, y1 = min(W, x + w + a.pad), min(H, y + h + a.pad)
        c = img[y0:y1, x0:x1]
        r = rot.get(i, 0)
        if r == 90:
            c = cv2.rotate(c, cv2.ROTATE_90_CLOCKWISE)
        elif r == -90:
            c = cv2.rotate(c, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif r == 180:
            c = cv2.rotate(c, cv2.ROTATE_180)
        ch, cw = c.shape[:2]
        # scale: horizontal blocks to crop-h tall; tall columns capped to 3*crop-h
        target_h = a.crop_h if cw >= ch else min(3 * a.crop_h, ch)
        s = min(target_h / ch, (a.sheet_w - 40) / cw)
        if a.scale:
            s = min(a.scale, (a.sheet_w - 40) / cw, (a.sheet_h - 60) / ch)
        c = cv2.resize(c, (max(1, int(cw * s)), max(1, int(ch * s))),
                       interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
        label = np.full((34, c.shape[1], 3), 255, np.uint8)
        cv2.putText(label, f"#{i}  ({x},{y} {w}x{h})", (4, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 200), 2)
        crops.append(np.vstack([label, c]))

    # pack crops row-major into sheets
    sheets, cur, cur_h = [], [], 0
    rows, row, row_w, row_h = [], [], 0, 0
    def flush_row():
        nonlocal row, row_w, row_h
        if not row:
            return
        padded = [np.hstack([c, np.full((row_h - c.shape[0], c.shape[1], 3), 255, np.uint8)]) if False else
                  np.vstack([c, np.full((row_h - c.shape[0], c.shape[1], 3), 255, np.uint8)]) for c in row]
        gaps = [np.full((row_h, 16, 3), 255, np.uint8)] * len(padded)
        line = np.hstack([v for pair in zip(padded, gaps) for v in pair])
        if line.shape[1] < a.sheet_w:
            line = np.hstack([line, np.full((row_h, a.sheet_w - line.shape[1], 3), 255, np.uint8)])
        rows.append(line[:, :a.sheet_w])
        row, row_w, row_h = [], 0, 0
    for c in crops:
        if row and row_w + c.shape[1] + 16 > a.sheet_w:
            flush_row()
        row.append(c); row_w += c.shape[1] + 16; row_h = max(row_h, c.shape[0])
    flush_row()
    n = 0
    cur, cur_h = [], 0
    for r in rows:
        if cur and (cur_h + r.shape[0] > a.sheet_h or len(cur) >= a.per_sheet):
            n += 1
            cv2.imwrite(os.path.join(a.out_dir, f"{stem}_blocks_{n:02d}.jpg"), np.vstack(cur), [cv2.IMWRITE_JPEG_QUALITY, 85])
            cur, cur_h = [], 0
        cur.append(r); cur_h += r.shape[0]
    if cur:
        n += 1
        cv2.imwrite(os.path.join(a.out_dir, f"{stem}_blocks_{n:02d}.jpg"), np.vstack(cur), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"{stem}: {len(crops)} blocks -> {n} sheet(s) in {a.out_dir}")


if __name__ == "__main__":
    main()
