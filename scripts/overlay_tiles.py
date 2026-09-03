#!/usr/bin/env python3
"""Zoomed, gridded review tiles of a page with its detected text blocks drawn
and numbered — for reading dense pages (catalogue inserts, colophons) block
by block and for measuring page coordinates of blocks the detector missed.

Usage: python overlay_tiles.py <detect.json> <out_dir> [--scale 0.6]
                              [--tile-w 1400 --tile-h 1900] [--grid 200]
                              [--region x,y,w,h]

Every tile shows page-pixel rulers every --grid px (labels are page coords),
so a missed block can be added to <stem>_manual.json by reading the numbers.
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
    ap.add_argument("--scale", type=float, default=0.6)
    ap.add_argument("--tile-w", type=int, default=1400)
    ap.add_argument("--tile-h", type=int, default=1900)
    ap.add_argument("--grid", type=int, default=200)
    ap.add_argument("--region", default=None, help="x,y,w,h page px (default: whole page)")
    a = ap.parse_args()

    d = json.load(open(a.detect_json))
    src = d.get("source_for_psd") or d["source"]
    img = cv2.imread(src, cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    H, W = img.shape[:2]
    stem = os.path.splitext(os.path.basename(a.detect_json))[0].replace("_detect", "")
    os.makedirs(a.out_dir, exist_ok=True)
    rx, ry, rw, rh = map(int, a.region.split(",")) if a.region else (0, 0, W, H)

    s = a.scale
    tw, th = int(a.tile_w / s), int(a.tile_h / s)      # tile size in page px
    n = 0
    for ty in range(ry, ry + rh, th):
        for tx in range(rx, rx + rw, tw):
            x1, y1 = min(W, tx + tw), min(H, ty + th)
            crop = img[ty:y1, tx:x1].copy()
            if crop.size == 0:
                continue
            crop = cv2.resize(crop, (int(crop.shape[1] * s), int(crop.shape[0] * s)), interpolation=cv2.INTER_AREA)
            # grid
            for gx in range((tx // a.grid) * a.grid, x1, a.grid):
                px = int((gx - tx) * s)
                if px < 0:
                    continue
                cv2.line(crop, (px, 0), (px, crop.shape[0]), (255, 200, 0), 1)
                cv2.putText(crop, str(gx), (px + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 120, 0), 1)
            for gy in range((ty // a.grid) * a.grid, y1, a.grid):
                py = int((gy - ty) * s)
                if py < 0:
                    continue
                cv2.line(crop, (0, py), (crop.shape[1], py), (255, 200, 0), 1)
                cv2.putText(crop, str(gy), (2, py + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 120, 0), 1)
            # blocks
            for i, (x, y, w, h) in enumerate(d["text_blocks"], 1):
                if x + w < tx or x > x1 or y + h < ty or y > y1:
                    continue
                p0 = (int((x - tx) * s), int((y - ty) * s))
                p1 = (int((x + w - tx) * s), int((y + h - ty) * s))
                cv2.rectangle(crop, p0, p1, (0, 0, 255), 2)
                cv2.putText(crop, str(i), (p0[0] + 2, p0[1] + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            n += 1
            cv2.imwrite(os.path.join(a.out_dir, f"{stem}_tile_{n:02d}_x{tx}_y{ty}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"{stem}: {n} tiles in {a.out_dir}")


if __name__ == "__main__":
    main()
