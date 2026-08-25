#!/usr/bin/env python3
"""Detect text strokes in manga pages with comic-text-detector (ONNX).

Usage: venv/bin/python detect_text.py <out_dir> <image> [<image>...]

For each page writes into <out_dir>/detect/:
  <stem>_mask_fill_white.png   text strokes sitting on plain white  (may be absent)
  <stem>_mask_fill_black.png   text strokes sitting on plain black  (may be absent)
  <stem>_mask_heal.png         text strokes over art                (may be absent)
  <stem>_overlay.jpg           original tinted with detected strokes for review
                               (red = fill_white, blue = fill_black, green = heal)
  <stem>_detect.json           component bboxes + classes, in page pixel coords
"""
import json
import os
import sys

import cv2
import numpy as np
import onnxruntime as ort

MODEL = os.path.join(os.path.dirname(__file__), "..", "models", "comictextdetector.pt.onnx")
SIZE = 1024
SEG_THRESH = 0.3
DILATE_PX = 2          # cover anti-aliased stroke edges
MIN_AREA = 24          # drop specks
RING_IN, RING_OUT = 3, 10   # background sampling ring around a component
WHITE_LVL, BLACK_LVL = 225, 30
PLAIN_FRAC = 0.95


def letterbox(img):
    h, w = img.shape[:2]
    scale = SIZE / max(h, w)
    nh, nw = round(h * scale), round(w * scale)
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((SIZE, SIZE, 3), dtype=np.uint8)
    canvas[:nh, :nw] = resized
    return canvas, scale, nh, nw


def detect_page(sess, path, out_dir):
    stem = os.path.splitext(os.path.basename(path))[0]
    img = cv2.imread(path)
    if img is None:
        raise RuntimeError(f"cannot read {path}")
    h, w = img.shape[:2]
    canvas, scale, nh, nw = letterbox(img)
    inp = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    seg = sess.run(["seg"], {"images": np.ascontiguousarray(inp)})[0][0, 0]
    if seg.min() < -0.01 or seg.max() > 1.01:      # logits -> sigmoid
        seg = 1.0 / (1.0 + np.exp(-seg))
    mask = (seg[:nh, :nw] > SEG_THRESH).astype(np.uint8) * 255
    mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
    mask = (mask > 127).astype(np.uint8) * 255
    if DILATE_PX:
        mask = cv2.dilate(mask, np.ones((2 * DILATE_PX + 1,) * 2, np.uint8))

    os.makedirs(out_dir, exist_ok=True)
    cv2.imwrite(os.path.join(out_dir, f"{stem}_mask.png"), mask)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    class_masks = {k: np.zeros((h, w), np.uint8) for k in ("fill_white", "fill_black", "heal")}
    comps = []
    k_in = np.ones((2 * RING_IN + 1,) * 2, np.uint8)
    k_out = np.ones((2 * RING_OUT + 1,) * 2, np.uint8)
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < MIN_AREA:
            continue
        # background ring around this component, computed on a padded crop
        pad = RING_OUT + 2
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)
        comp = (labels[y0:y1, x0:x1] == i).astype(np.uint8)
        ring = cv2.dilate(comp, k_out) & ~cv2.dilate(comp, k_in) & ~(mask[y0:y1, x0:x1] > 0)
        bg = gray[y0:y1, x0:x1][ring > 0]
        if bg.size == 0:
            cls = "heal"
        elif (bg >= WHITE_LVL).mean() >= PLAIN_FRAC:
            cls = "fill_white"
        elif (bg <= BLACK_LVL).mean() >= PLAIN_FRAC:
            cls = "fill_black"
        else:
            cls = "heal"
        class_masks[cls][labels == i] = 255
        comps.append({"bbox": [int(x), int(y), int(bw), int(bh)], "class": cls, "area": int(area)})

    out = {"source": os.path.abspath(path), "size": [w, h],
           "text_mask": os.path.join(out_dir, f"{stem}_mask.png"),
           "components": comps, "masks": {}}
    overlay = img.copy()
    tint = {"fill_white": (0, 0, 255), "fill_black": (255, 0, 0), "heal": (0, 200, 0)}
    for cls, m in class_masks.items():
        if not m.any():
            continue
        mpath = os.path.join(out_dir, f"{stem}_mask_{cls}.png")
        cv2.imwrite(mpath, m)
        out["masks"][cls] = mpath
        overlay[m > 0] = 0.25 * overlay[m > 0] + 0.75 * np.array(tint[cls])
    cv2.imwrite(os.path.join(out_dir, f"{stem}_overlay.jpg"), overlay,
                [cv2.IMWRITE_JPEG_QUALITY, 88])
    with open(os.path.join(out_dir, f"{stem}_detect.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(f"{stem}: {len(comps)} components "
          f"({sum(c['class'] == 'fill_white' for c in comps)} fill_white, "
          f"{sum(c['class'] == 'fill_black' for c in comps)} fill_black, "
          f"{sum(c['class'] == 'heal' for c in comps)} heal)")


def main():
    out_dir = os.path.join(sys.argv[1], "detect")
    sess = ort.InferenceSession(MODEL, providers=["CPUExecutionProvider"])
    for path in sys.argv[2:]:
        detect_page(sess, path, out_dir)


if __name__ == "__main__":
    main()
