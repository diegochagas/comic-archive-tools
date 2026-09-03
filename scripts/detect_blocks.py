#!/usr/bin/env python3
"""Detect TEXT BLOCKS (no erasing) in comic/manga/art-book scans of any size,
including huge scans (5000-10000 px) with tiny print, by running the
comic-text-detector ONNX model at several scales/tiles and merging the boxes.

Usage: python detect_blocks.py <out_dir> <image> [<image>...] [--tile 2048]
                               [--min-tile 1024] [--no-fullpage]

For each page writes into <out_dir>/detect/:
  <stem>_detect.json   {"source", "size", "text_blocks": [[x,y,w,h], ...]}
                       (page-pixel coords, sorted top-left -> bottom-right)
  <stem>_overlay.jpg   downscaled page with numbered block boxes (review aid)

Why tiles: detect_text.py letterboxes the whole page to 1024 px, which is fine
for a 1500 px manga page but loses 6 pt catalog print on a 6000 px scan. Here
the page is additionally cut into overlapping tiles of `--tile` source px (each
scaled to the model's 1024 input), and — for very dense print — of
`--min-tile` px. Boxes from every pass are merged: overlapping / touching boxes
(gap <= a fraction of their height) are unioned into one block, so a
paragraph seen half in two tiles still becomes a single box.
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
import onnxruntime as ort

MODEL = os.path.join(os.path.dirname(__file__), "..", "models", "comictextdetector.pt.onnx")
SIZE = 1024
BLK_CONF = 0.4
BLK_IOU = 0.4
DET_THRESH = 0.4
MERGE_GAP_FRAC = 0.35   # union boxes whose gap <= this * the thinner box's smaller side
DET_UNSHRINK = 0.4      # grow det-map (shrunk kernel) boxes by this * line thickness per side
MERGE_FILL = 0.55       # two boxes merge only if they cover >= this of their union's area
MAX_BLOCK_FRAC = 0.35   # blk-head boxes bigger than this * page area are layout noise, dropped
MERGE_GROWTH = 2.5      # absorbing a box may add at most this * its area of new union space
MAX_BLOCK_SIDE_FRAC = 0.6   # merged blocks never exceed this * page max side (set per page)
MAX_BLOCK_SIDE = 10 ** 9
MIN_BOX = 12            # drop boxes smaller than this in both dimensions (page px)
MIN_SIDE_FRAC = 0.006   # ...and, after merging, blocks thinner than this * page max side


def has_exif_rotation(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.getexif().get(274, 1) != 1
    except Exception:
        return False


def make_session_options():
    """The comictextdetector weights produce lots of denormal floats; with
    denormal-as-zero OFF (onnxruntime's default) one 1024x1024 inference takes
    ~90 s on a CPU that does it in ~1.4 s with DAZ on (measured 2026-09-03).
    Detection quality is unaffected."""
    so = ort.SessionOptions()
    so.add_session_config_entry("session.set_denormal_as_zero", "1")
    return so


def run_model(sess, img):
    """img: BGR array with max side <= SIZE. Returns (blocks [x,y,w,h] in img px, det map)."""
    h, w = img.shape[:2]
    scale = SIZE / max(h, w)
    nh, nw = round(h * scale), round(w * scale)
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((SIZE, SIZE, 3), dtype=np.uint8)
    canvas[:nh, :nw] = resized
    inp = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    blk, _seg, det = sess.run(["blk", "seg", "det"], {"images": np.ascontiguousarray(inp)})
    blk = blk[0]
    score = blk[:, 4] * blk[:, 5:].max(axis=1)
    keep_mask = score >= BLK_CONF
    boxes = []
    if keep_mask.any():
        cand = blk[keep_mask]
        bx = np.stack([cand[:, 0] - cand[:, 2] / 2, cand[:, 1] - cand[:, 3] / 2,
                       cand[:, 2], cand[:, 3]], axis=1) / scale
        keep = cv2.dnn.NMSBoxes(bx.tolist(), score[keep_mask].tolist(), BLK_CONF, BLK_IOU)
        for i in np.array(keep).flatten():
            x, y, bw, bh = bx[i]
            x0, y0 = max(0, int(x)), max(0, int(y))
            x1, y1 = min(w, int(x + bw)), min(h, int(y + bh))
            if x1 > x0 and y1 > y0:
                boxes.append([x0, y0, x1 - x0, y1 - y0])
    det = det[0, 0]
    if det.min() < -0.01 or det.max() > 1.01:
        det = 1.0 / (1.0 + np.exp(-det))
    det_full = cv2.resize((det[:nh, :nw] > DET_THRESH).astype(np.uint8) * 255, (w, h),
                          interpolation=cv2.INTER_LINEAR)
    return boxes, (det_full > 127).astype(np.uint8) * 255


def det_components_to_boxes(det_mask, min_h):
    """Group the text-line map into blocks: dilate lines a bit so neighbouring
    lines of one paragraph fuse, then take component bboxes."""
    if not det_mask.any():
        return []
    k = max(3, int(min_h * 0.6))
    m = cv2.dilate(det_mask, np.ones((k, k), np.uint8))
    n, _labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    out = []
    H, W = det_mask.shape
    for i in range(1, n):
        x, y, bw, bh, _area = stats[i]
        # undo dilation padding
        x0, y0 = x + k // 2, y + k // 2
        bw, bh = max(1, bw - k), max(1, bh - k)
        # the det head is a DBNet-style *shrunk* text kernel: the mask covers
        # only the core of each line, so un-shrink by ~DET_UNSHRINK of the
        # line thickness (its smaller side) on every side
        e = int(round(DET_UNSHRINK * min(bw, bh)))
        x0, y0 = max(0, x0 - e), max(0, y0 - e)
        x1, y1 = min(W, x0 + bw + 2 * e), min(H, y0 + bh + 2 * e)
        out.append([int(x0), int(y0), int(x1 - x0), int(y1 - y0)])
    return out


def snap_box(img, box, tol=45, pad=4):
    """Tighten a rough hand-drawn box to the ink inside it: pixels whose color
    differs from the box border's median color by > tol, specks removed."""
    H, W = img.shape[:2]
    x, y, w, h = box
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    crop = img[y0:y1, x0:x1].astype(np.int16)
    if crop.size == 0:
        return box
    ring = np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]])
    med = np.median(ring, axis=0)
    ink = (np.abs(crop - med).sum(axis=2) > tol).astype(np.uint8)
    k = max(2, min(w, h) // 60)
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    ys, xs = np.where(ink > 0)
    if not len(xs):
        return box
    nx0, ny0 = max(0, x0 + xs.min() - pad), max(0, y0 + ys.min() - pad)
    nx1, ny1 = min(W, x0 + xs.max() + 1 + pad), min(H, y0 + ys.max() + 1 + pad)
    return [int(nx0), int(ny0), int(nx1 - nx0), int(ny1 - ny0)]


def tiles(w, h, tile, overlap):
    step = tile - overlap
    xs = list(range(0, max(1, w - tile + 1), step)) + ([max(0, w - tile)] if w > tile else [0])
    ys = list(range(0, max(1, h - tile + 1), step)) + ([max(0, h - tile)] if h > tile else [0])
    for y in sorted(set(ys)):
        for x in sorted(set(xs)):
            yield x, y, min(tile, w - x), min(tile, h - y)


def boxes_touch(a, b):
    ax0, ay0, aw, ah = a
    bx0, by0, bw, bh = b
    ax1, ay1, bx1, by1 = ax0 + aw, ay0 + ah, bx0 + bw, by0 + bh
    # "line thickness" = smaller side, so vertical (tall) text columns are
    # judged by their width and horizontal lines by their height
    gap = MERGE_GAP_FRAC * min(min(aw, ah), min(bw, bh))
    # horizontal overlap / vertical near, or vertical overlap / horizontal near
    x_ov = min(ax1, bx1) - max(ax0, bx0)
    y_ov = min(ay1, by1) - max(ay0, by0)
    if x_ov > -gap and y_ov > -gap:
        # require real overlap on at least one axis so diagonal neighbours don't merge
        if not (x_ov > min(aw, bw) * 0.3 or y_ov > min(ah, bh) * 0.3):
            return False
        # and the union must stay compact: a merge that creates mostly empty
        # space is two separate blocks (columns of a catalogue, form cells...)
        inter = max(0, x_ov) * max(0, y_ov)
        covered = aw * ah + bw * bh - inter
        ux = max(ax1, bx1) - min(ax0, bx0)
        uy = max(ay1, by1) - min(ay0, by0)
        if covered < MERGE_FILL * ux * uy:
            return False
        # chained merges: absorbing a small box must not grow a big box by
        # much more than the small box itself (stops a blob creeping across a
        # dense catalogue page one caption at a time)
        big, small = max(aw * ah, bw * bh), min(aw * ah, bw * bh)
        if ux * uy - big > MERGE_GROWTH * small:
            return False
        # and never build blocks wider/taller than a fraction of the page
        return ux <= MAX_BLOCK_SIDE and uy <= MAX_BLOCK_SIDE
    return False


def merge_boxes(boxes):
    boxes = [list(b) for b in boxes]
    changed = True
    while changed:
        changed = False
        out = []
        while boxes:
            a = boxes.pop()
            merged = True
            while merged:
                merged = False
                for i in range(len(boxes) - 1, -1, -1):
                    if boxes_touch(a, boxes[i]):
                        b = boxes.pop(i)
                        x0, y0 = min(a[0], b[0]), min(a[1], b[1])
                        x1 = max(a[0] + a[2], b[0] + b[2])
                        y1 = max(a[1] + a[3], b[1] + b[3])
                        a = [x0, y0, x1 - x0, y1 - y0]
                        merged = changed = True
            out.append(a)
        boxes = out
    return boxes


def detect_page(sess, path, out_dir, tile, min_tile, fullpage):
    stem = os.path.splitext(os.path.basename(path))[0]
    # IGNORE_ORIENTATION: work on the raw pixel grid. Scanner JPEGs sometimes
    # carry a bogus EXIF rotation; the raw grid is what PSD builders that
    # ignore EXIF (and what PIL) see, so all box coords stay consistent.
    img = cv2.imread(path, cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    if img is None:
        raise RuntimeError(f"cannot read {path}")
    h, w = img.shape[:2]
    os.makedirs(out_dir, exist_ok=True)
    source_for_psd = os.path.abspath(path)
    if has_exif_rotation(path):
        # node-canvas applies EXIF; give the PSD builder an EXIF-free copy
        # with the same pixel grid the boxes were measured on (lossless PNG)
        source_for_psd = os.path.join(out_dir, f"{stem}_upright.png")
        if not os.path.exists(source_for_psd):
            cv2.imwrite(source_for_psd, img, [cv2.IMWRITE_PNG_COMPRESSION, 1])
        print(f"{stem}: EXIF orientation tag present -> wrote EXIF-free copy {source_for_psd}")
    all_boxes = []
    passes = []
    manual_path = os.path.join(out_dir, f"{stem}_manual.json")
    manual_replace = os.path.exists(manual_path) and bool(json.load(open(manual_path)).get("replace"))
    if manual_replace:
        fullpage = False          # hand-drawn block list: skip the model entirely
        tile = min_tile = 10 ** 9
    if fullpage:
        passes.append(("full", max(w, h)))
    for t in sorted({tile, min_tile}, reverse=True):
        if t < max(w, h):
            passes.append(("tile", t))
    for kind, t in passes:
        if kind == "full":
            # downscale whole page to keep memory sane
            f = SIZE / max(w, h)
            small = cv2.resize(img, (round(w * f), round(h * f)), interpolation=cv2.INTER_AREA)
            boxes, det = run_model(sess, small)
            det_boxes = det_components_to_boxes(det, 8)
            for b in boxes + det_boxes:
                all_boxes.append([int(v / f) for v in b])
        else:
            for x, y, tw, th in tiles(w, h, t, t // 6):
                crop = img[y:y + th, x:x + tw]
                boxes, det = run_model(sess, crop)
                det_boxes = det_components_to_boxes(det, 6)
                for b in boxes + det_boxes:
                    all_boxes.append([b[0] + x, b[1] + y, b[2], b[3]])
    # page-relative floor on the smaller side: screentone / paper grain on big
    # scans produces speckle-sized det components that are never real text
    min_side = max(MIN_BOX, int(MIN_SIDE_FRAC * max(w, h)))
    all_boxes = [b for b in all_boxes if (b[2] >= MIN_BOX or b[3] >= MIN_BOX)
                 and b[2] * b[3] <= MAX_BLOCK_FRAC * w * h]
    with open(os.path.join(out_dir, f"{stem}_raw.json"), "w") as fh:
        json.dump(all_boxes, fh)
    global MAX_BLOCK_SIDE
    MAX_BLOCK_SIDE = int(MAX_BLOCK_SIDE_FRAC * max(w, h))
    blocks = merge_boxes(all_boxes)
    blocks = [b for b in blocks if min(b[2], b[3]) >= min_side]
    # reading order: rows of ~1/40 page height, left to right. Done BEFORE the
    # manual overrides so a hand-written "replace"/"add" list keeps its own
    # order (translations are matched to blocks by index)
    blocks.sort(key=lambda b: (b[1] // max(1, h // 40), b[0]))
    manual = os.path.join(out_dir, f"{stem}_manual.json")
    if os.path.exists(manual):
        # reviewer overrides: {"add": [[x,y,w,h],...], "drop": [[x,y,w,h],...]}
        # (drop = any detected box whose centre falls inside one of these)
        m = json.load(open(manual))
        drops = m.get("drop", [])
        def dropped(b):
            cx, cy = b[0] + b[2] / 2, b[1] + b[3] / 2
            return any(dx <= cx <= dx + dw and dy <= cy <= dy + dh for dx, dy, dw, dh in drops)
        blocks = [b for b in blocks if not dropped(b)]
        for b in m.get("add", []):
            b = list(map(int, b[:4]))
            blocks.append(snap_box(img, b) if m.get("snap", True) else b)
        if m.get("replace"):
            blocks = [snap_box(img, list(map(int, b))) if m.get("snap", True) else list(map(int, b))
                      for b in m["replace"]]

    os.makedirs(out_dir, exist_ok=True)
    f = min(1.0, 2000 / max(w, h))
    ov = cv2.resize(img, (round(w * f), round(h * f)), interpolation=cv2.INTER_AREA)
    for i, (x, y, bw, bh) in enumerate(blocks):
        p0 = (int(x * f), int(y * f))
        p1 = (int((x + bw) * f), int((y + bh) * f))
        cv2.rectangle(ov, p0, p1, (0, 0, 255), 2)
        cv2.putText(ov, str(i + 1), (p0[0], max(12, p0[1] - 3)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (0, 0, 255), 2)
    cv2.imwrite(os.path.join(out_dir, f"{stem}_overlay.jpg"), ov, [cv2.IMWRITE_JPEG_QUALITY, 85])
    out = {"source": os.path.abspath(path), "source_for_psd": source_for_psd,
           "size": [w, h], "text_blocks": blocks}
    with open(os.path.join(out_dir, f"{stem}_detect.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"{stem}: {len(blocks)} text blocks ({len(all_boxes)} raw, {len(passes)} passes)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir")
    ap.add_argument("images", nargs="+")
    ap.add_argument("--tile", type=int, default=2048)
    ap.add_argument("--min-tile", type=int, default=1024)
    ap.add_argument("--no-fullpage", action="store_true")
    a = ap.parse_args()
    out_dir = os.path.join(a.out_dir, "detect")
    sess = ort.InferenceSession(MODEL, make_session_options(), providers=["CPUExecutionProvider"])
    failed = []
    for p in a.images:
        try:
            detect_page(sess, p, out_dir, a.tile, a.min_tile, not a.no_fullpage)
        except Exception as e:
            print(f"SKIP {p}: {e}")
            failed.append(p)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
