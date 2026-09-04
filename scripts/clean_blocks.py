#!/usr/bin/env python3
"""Erase the text inside blocks found by detect_blocks.py (Mode B) and write a
cleaned page for the PSD "Copy" layer.

Usage: python clean_blocks.py <detect_json> [<detect_json> ...] [--pad 6]

For every <stem>_detect.json (from detect_blocks.py) writes, next to it:
  <stem>_cleaned.png   page with the strokes inside every text block erased
  <stem>_clean_overlay.jpg   red = solid fill, green = inpainted

Per block the comic-text-detector is run on a crop of that block (letterboxed
to 1024 px), so its stroke segmentation sees the text at block scale — big
display titles that the page-scale pass blurs away are segmented cleanly.
Each stroke component is then erased exactly like detect_text.py does: a
solid fill with the sampled surrounding color when the ring around it is
uniform, cv2.inpaint otherwise. Pixels outside the blocks are never touched.
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
import onnxruntime as ort

sys.path.insert(0, os.path.dirname(__file__))
import detect_text as dt  # noqa: E402  (constants + MODEL path)

CROP_PAD = 24      # context around the block given to the model
MIN_CROP = 256     # tiny blocks are padded up to this so the model sees context


def seg_mask_for_crop(sess, crop):
    """Stroke mask (uint8 0/255) for a BGR crop, model run at crop scale."""
    h, w = crop.shape[:2]
    canvas, scale, nh, nw = dt.letterbox(crop)
    inp = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    seg = sess.run(["seg"], {"images": np.ascontiguousarray(inp)})[0][0, 0]
    if seg.min() < -0.01 or seg.max() > 1.01:
        seg = 1.0 / (1.0 + np.exp(-seg))

    def to_full(th):
        m = (seg[:nh, :nw] > th).astype(np.uint8) * 255
        m = cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)
        return (m > 127).astype(np.uint8) * 255

    high, low = to_full(dt.SEG_THRESH), to_full(dt.SEG_LOW)
    near = cv2.dilate(high, np.ones((2 * dt.SEG_NEAR + 1,) * 2, np.uint8))
    mask = low & near
    if dt.DILATE_PX:
        mask = cv2.dilate(mask, np.ones((2 * dt.DILATE_PX + 1,) * 2, np.uint8))
    return mask


def clean_page(sess, det_path, pad):
    d = json.load(open(det_path))
    src = d.get("source_for_psd") or d["source"]
    img = cv2.imread(src)
    if img is None:
        raise RuntimeError(f"cannot read {src}")
    H, W = img.shape[:2]
    blocks = d["text_blocks"]

    # 1. stroke mask restricted to the (padded) blocks: union of the page-scale
    #    segmentation (best for small print) and a per-block crop-scale pass
    #    (best for large display text)
    page_mask = seg_mask_for_crop(sess, img)
    mask = np.zeros((H, W), np.uint8)
    plain = []   # (block, bg color) for blocks on a uniform background
    for bx, by, bw, bh in blocks:
        # crop with context; grow small blocks so the model has something to see
        ex = max(CROP_PAD, (MIN_CROP - bw) // 2)
        ey = max(CROP_PAD, (MIN_CROP - bh) // 2)
        cx0, cy0 = max(0, bx - ex), max(0, by - ey)
        cx1, cy1 = min(W, bx + bw + ex), min(H, by + bh + ey)
        if max(bw, bh) > 300 and (min(bw, bh) > 100 or len(blocks) <= 40):   # crop pass (skipped for thin columns on very dense pages)
            m = seg_mask_for_crop(sess, img[cy0:cy1, cx0:cx1])
        else:
            m = np.zeros((cy1 - cy0, cx1 - cx0), np.uint8)
        # keep only strokes inside the block (+pad)
        keep = np.zeros_like(m)
        kx0, ky0 = max(0, bx - pad - cx0), max(0, by - pad - cy0)
        kx1, ky1 = min(cx1, bx + bw + pad) - cx0, min(cy1, by + bh + pad) - cy0
        keep[ky0:ky1, kx0:kx1] = 255
        mask[cy0:cy1, cx0:cx1] |= (m | page_mask[cy0:cy1, cx0:cx1]) & keep

        # plain-background test: band just outside and just inside the block
        # edge, ignoring detected strokes.  Uniform -> fill every non-bg pixel.
        ox0, oy0 = max(0, bx - pad - 8), max(0, by - pad - 8)
        ox1, oy1 = min(W, bx + bw + pad + 8), min(H, by + bh + pad + 8)
        band = np.zeros((oy1 - oy0, ox1 - ox0), np.uint8)
        band[:] = 255
        ix0, iy0 = bx + 4 - ox0, by + 4 - oy0
        ix1, iy1 = bx + bw - 4 - ox0, by + bh - 4 - oy0
        if ix1 > ix0 and iy1 > iy0:
            band[iy0:iy1, ix0:ix1] = 0
        band &= ~mask[oy0:oy1, ox0:ox1]
        bg = img[oy0:oy1, ox0:ox1][band > 0].astype(np.float32)
        if bg.size:
            med = np.median(bg, axis=0)
            if (np.linalg.norm(bg - med, axis=1) <= dt.COLOR_TOL).mean() >= dt.PLAIN_FRAC:
                plain.append(((bx, by, bw, bh), med))

    for (bx, by, bw, bh), med in plain:
        x0, y0 = max(0, bx - pad), max(0, by - pad)
        x1, y1 = min(W, bx + bw + pad), min(H, by + bh + pad)
        reg = img[y0:y1, x0:x1].astype(np.float32)
        far = (np.linalg.norm(reg - med, axis=2) > dt.COLOR_TOL).astype(np.uint8) * 255
        far = cv2.dilate(far, np.ones((5, 5), np.uint8))
        mask[y0:y1, x0:x1] |= far

    # 2. erase components (same fill/inpaint rule as detect_text.py)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    cleaned = img.copy()
    inpaint_mask = np.zeros((H, W), np.uint8)
    fill_tint = np.zeros((H, W), np.uint8)
    k_in = np.ones((2 * dt.RING_IN + 1,) * 2, np.uint8)
    k_out = np.ones((2 * dt.RING_OUT + 1,) * 2, np.uint8)
    nfill = ninp = 0
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < dt.MIN_AREA:
            continue
        p = dt.RING_OUT + 2
        x0, y0 = max(0, x - p), max(0, y - p)
        x1, y1 = min(W, x + bw + p), min(H, y + bh + p)
        comp = (labels[y0:y1, x0:x1] == i).astype(np.uint8)
        ring = cv2.dilate(comp, k_out) & ~cv2.dilate(comp, k_in) & ~(mask[y0:y1, x0:x1] > 0)
        bg = img[y0:y1, x0:x1][ring > 0].astype(np.float32)
        median = np.median(bg, axis=0) if bg.size else None
        uniform = (bg.size > 0 and
                   (np.linalg.norm(bg - median, axis=1) <= dt.COLOR_TOL).mean() >= dt.PLAIN_FRAC)
        if uniform:
            cleaned[labels == i] = median.round().clip(0, 255).astype(np.uint8)
            fill_tint[labels == i] = 255
            nfill += 1
        else:
            inpaint_mask[labels == i] = 255
            ninp += 1
    if inpaint_mask.any():
        cleaned = cv2.inpaint(cleaned, inpaint_mask, dt.INPAINT_RADIUS, cv2.INPAINT_TELEA)

    out_dir = os.path.dirname(det_path)
    stem = os.path.basename(det_path)[:-len("_detect.json")]
    cleaned_path = os.path.join(out_dir, f"{stem}_cleaned.png")
    cv2.imwrite(cleaned_path, cleaned)
    overlay = img.copy()
    for m, tint in ((fill_tint, (0, 0, 255)), (inpaint_mask, (0, 200, 0))):
        if m.any():
            overlay[m > 0] = 0.25 * overlay[m > 0] + 0.75 * np.array(tint)
    cv2.imwrite(os.path.join(out_dir, f"{stem}_clean_overlay.jpg"), overlay,
                [cv2.IMWRITE_JPEG_QUALITY, 85])
    d["cleaned"] = cleaned_path
    with open(det_path, "w") as f:
        json.dump(d, f, indent=1)
    print(f"{stem}: {len(blocks)} blocks, {nfill} fill + {ninp} inpaint components -> {cleaned_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("detect_json", nargs="+")
    ap.add_argument("--pad", type=int, default=6, help="px around each block still erased")
    a = ap.parse_args()
    so = ort.SessionOptions()
    so.add_session_config_entry("session.set_denormal_as_zero", "1")
    sess = ort.InferenceSession(dt.MODEL, so, providers=["CPUExecutionProvider"])
    for p in a.detect_json:
        try:
            clean_page(sess, p, a.pad)
        except Exception as e:
            print(f"SKIP {p}: {e}")


if __name__ == "__main__":
    main()
