---
name: clean-manga-text
description: Convert every manga/doujinshi page image in a folder to a layered PSD (layer "Original" + layer "Cleaned") where the Cleaned layer has CJK text removed — but ONLY text sitting on a plain single-color background (white or black speech bubbles, boxes, margins). Text drawn over artwork is deliberately left untouched. Uses an ONNX text-detection model plus headless GIMP.
---

# Clean manga text → layered PSDs (plain backgrounds only)

For every image in a folder, produce a PSD with two layers: **Original**
(untouched scan, bottom) and **Cleaned** (top). On the Cleaned layer, remove text
that sits on a plain single color — dark text on white (typical speech bubbles)
or light text on black. **Text over drawings — sound effects across art, artist
signatures, captions crossed by linework — is left as-is by design**: automated
healing over art proved unreliable (user decision, 2026-08-25). Every page gets a
PSD even if nothing is cleaned (two identical layers), so the folder converts
completely.

Division of labor — do not regress this:

- **The model finds the pixels.** `comic-text-detector` (ONNX) outputs a
  pixel-accurate mask of text strokes. Only masked pixels are ever modified —
  never fill bare rectangles or hand-guessed tight boxes (v1 did; it left white
  squares and bit chunks out of figures).
- **You (Claude) provide the semantics.** The model over-detects (flags art as
  text). You view each page and draw generous "allow boxes" around text blocks
  that qualify (boxes may safely overlap art — only detected strokes inside them
  get touched). Anything not covered by a box stays untouched.
- **GIMP does the pixel work** (masked fills, PSD export).

## Requirements (all already installed)

- Flatpak GIMP 3 (`org.gimp.GIMP`).
- This skill's venv: `<skill>/venv/bin/python` (onnxruntime, opencv, numpy).
- Model: `<skill>/models/comictextdetector.pt.onnx` (re-download from
  manga-image-translator GitHub release `beta-0.3` if missing).
- Scripts: `<skill>/scripts/detect_text.py`, `<skill>/scripts/gimp_clean.py`.

## Inputs

- **Source folder** of images (jpg/jpeg/png). Required — ask if not given.
- **Output dir**: default `<source folder>/psd`. PSDs land there; previews in
  `<output>/preview/<stem>_cleaned.jpg`; detection artifacts in `<output>/detect/`.
- Optional page range/subset.

## Workflow

### 0. Setup and resume

- List images sorted; track verified pages in `<output>/progress.json`
  (`{"done": ["010", ...]}`); skip those on re-invocation.
- Work in chunks of ~5 pages; for big folders report progress as you go
  (~1 min per page).

### 1. Detect text strokes

```bash
<skill>/venv/bin/python <skill>/scripts/detect_text.py <output_dir> <img1> <img2> ...
```

Per page this writes into `<output>/detect/`: `<stem>_mask.png` (union stroke
mask — what the cleaner uses), `<stem>_overlay.jpg` (page tinted where strokes
were detected: red = classified on-plain-white, blue = on-plain-black, green =
over art; colors are only a hint), and `<stem>_detect.json` (component bboxes in
page pixel coords).

### 2. Review each overlay (your judgment)

Read the overlay next to the original. For each real text block decide whether it
qualifies, **at whole-block level**:

- Block entirely on plain white → `fill_white`. Entirely on plain black →
  `fill_black`.
- If ANY art linework runs under or through the block (hair strands, rays,
  foliage, screentone drawings), or the block is a signature/SFX over art →
  **skip the whole block**; do not clean parts of a sentence. When unsure, crop
  + 2× zoom the area with PIL and look.
- Ignore model false positives on art by simply not covering them with a box.

Emit one box per qualifying block. A box only needs to contain the block's
tinted strokes — but **before finalizing it, scan the overlay INSIDE the box for
tinted art** (model false positives: plant strokes, bubble-spike doodles, hair,
screentone marks). Any tinted art inside the box WILL be erased by the fill, so
shrink the box until it contains text strokes only (crop + 2× zoom the overlay
when text and tinted art sit close). "Overlapping art is safe" holds only for
art the model did NOT tint. Use `<stem>_detect.json` bboxes to get coordinates
right.

### 3. Run the GIMP job

Job JSON (batch several pages per invocation — GIMP startup is ~15 s). Only
`fill_white` / `fill_black` mask_regions are used; pages with nothing to clean
still get an entry with empty `mask_regions`:

```json
{
  "output_dir": "/abs/out",
  "pages": [
    {"source": "/abs/010.jpg",
     "text_mask": "/abs/out/detect/010_mask.png",
     "mask_regions": [
       {"box": [1090, 0, 210, 250], "action": "fill_white"},
       {"box": [80, 50, 200, 310], "action": "fill_black"}
     ]},
    {"source": "/abs/011.jpg", "text_mask": "/abs/out/detect/011_mask.png",
     "mask_regions": []}
  ]
}
```

```bash
timeout 500 flatpak run --env=CLEAN_JOB=/abs/job.json org.gimp.GIMP -idf \
  --batch-interpreter=python-fu-eval \
  -b "exec(open('<skill>/scripts/gimp_clean.py').read())" --quit
```

Check `<job.json>.log` (GIMP stderr is noise): `OK <src> -> <psd>` per page,
`DONE` at the end, `FAIL` + traceback per page on errors.

(`gimp_clean.py` also still supports `heal`/`heal_dark`/`heal_light` Resynthesizer
actions and old-style `regions` — use them only if the user explicitly asks to
attempt removal of text over art, and warn that results are imperfect.)

### 4. Verify and iterate (mandatory, at zoom level)

A full-page preview look is NOT enough — small collateral damage (an erased
plant stroke, a clipped bubble spike) is invisible at page scale and has slipped
through before. For **each cleaned box**, crop the same area (box + ~40 px
margin) from BOTH the original and the preview, view the two crops side by side,
and confirm: (a) the text is fully gone, (b) every art stroke present in the
original crop is still present in the cleaned crop (spikes, plants, outlines),
(c) nothing changed outside the box. Then also read the full preview once for
overall sanity. Fix boxes and rerun failed pages — **each rerun reloads the
pristine source, so a page's job must always carry its FULL region list**; any
damage from a bad pass is undone by the next. When a page passes, add it to
`progress.json`.

### 5. Report

Pages processed, output location, PSD layer structure, and per page which text
was intentionally left (over-art SFX, signatures, blocks crossed by linework).
