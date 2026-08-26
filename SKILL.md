---
name: manga-letterer
description: Convert every manga/doujinshi page image in a folder to a layered PSD ready for lettering — layer "Original" + layer "Cleaned" (ALL detected CJK text erased, and ONLY text; the model's text-region heads keep art like borders/hatching safe from false positives) + one editable Photoshop paragraph text box per detected text region, pre-filled with CCWildWords-Regular placeholder text. Each erased region is filled with the predominant color around it (exact solid color on plain backgrounds of any color — white, black, grey, red...; inpainted from surrounding pixels over art). Uses an ONNX text-detection model plus headless GIMP for PSD assembly, then ag-psd (Node) to write real Photoshop Type-tool paragraph boxes GIMP itself cannot export. Anything worth keeping is restored manually from the Original layer.
---

# manga-letterer — clean manga pages into letter-ready layered PSDs

For every image in a folder, produce a PSD with: **Original** (untouched
scan, bottom), **Cleaned** (top of the raster stack) with **every detected
text stroke erased — and only text** (stroke detections are gated by the
model's own text-block boxes and text-line map, so stroke-like false
positives on art — decorative borders, hatching, screentone — stay
untouched), and one **empty, editable Photoshop paragraph text box per
detected text region**, positioned and sized to that region, ready to type a
translation into with Photoshop's own Type tool. No manual review step for
the cleaning. Each erased region is filled with the predominant color around
it:

- surroundings are one plain color (white/black bubbles, grey caption boxes,
  colored banners...) → filled with that exact sampled color;
- surroundings are busy (art, screentone, gradients) → inpainted from the
  surrounding pixels (results over art are imperfect by nature).

**Restoration is manual by design** (user decision, 2026-08-26, superseding the
earlier leave-text-over-art policy): if the automated erase damaged something
the user wants back (a signature, an SFX crossed by the gate), they copy that
area from the Original layer themselves in an editor. Every page gets a PSD
even if nothing was detected (two identical layers), so the folder converts
completely.

Division of labor:

- **`detect_text.py` does everything pixel-level.** The comic-text-detector
  ONNX model finds text strokes and text regions (block boxes + line map);
  the script erases strokes inside text regions only, classifies each
  component's surroundings, solid-fills or inpaints it, and writes the fully
  cleaned page image. Only detected stroke pixels are ever modified. The same
  text-block boxes also become the paragraph text box positions in step 3.
- **GIMP assembles the raster layers**: stacks Cleaned over Original and
  exports PSD + JPG preview. GIMP's own PSD exporter rasterizes GIMP text
  layers on save — it cannot write native Photoshop text layers, so it never
  touches text.
- **`add_text_layers.mjs` (Node + ag-psd) writes the real Photoshop text
  layers** the GIMP step can't: one native "paragraph" (word-wrap box) Type
  layer per detected text block, empty and positioned exactly over that
  block, stacked above Cleaned. This rewrites the PSD's binary layer records
  directly; it round-trips the existing raster layers byte-exact (verified
  pixel-for-pixel) and only appends new layers.
- **You (Claude) orchestrate and spot-check**: run the scripts in batches,
  glance at previews/overlays for gross failures (e.g. a wrong fill color, a
  page that failed to process), and report what was touched.

## Requirements (all already installed)

- Flatpak GIMP 3 (`org.gimp.GIMP`).
- This skill's venv: `<skill>/venv/bin/python` (onnxruntime, opencv, numpy).
- Model: `<skill>/models/comictextdetector.pt.onnx` (re-download from
  manga-image-translator GitHub release `beta-0.3` if missing).
- Node.js + `<skill>/node_modules/ag-psd` (installed by `setup.sh`; run it
  again if `node_modules` is missing).
- Scripts: `<skill>/scripts/detect_text.py`, `<skill>/scripts/gimp_clean.py`,
  `<skill>/scripts/add_text_layers.mjs`.

## Inputs

- **Source folder** of images (jpg/jpeg/png). Required — ask if not given.
- **Output dir**: default `<source folder>/psd`. PSDs land there; previews in
  `<output>/preview/<stem>_cleaned.jpg`; detection artifacts in `<output>/detect/`.
- Optional page range/subset.

## Workflow

### 0. Setup and resume

- List images sorted; track finished pages in `<output>/progress.json`
  (`{"done": ["010", ...]}`); skip those on re-invocation.
- Work in chunks of ~8 pages; for big folders report progress as you go.

### 1. Detect and erase text

```bash
<skill>/venv/bin/python <skill>/scripts/detect_text.py <output_dir> <img1> <img2> ...
```

Only actual text is touched: the model's text-block boxes and text-line map
gate its stroke segmentation, so stroke-like false positives on art
(ornamental borders, hatching, screentone) are left untouched automatically.

Per page this writes into `<output>/detect/`:

- `<stem>_cleaned.png` — the page with all text erased (becomes the PSD's
  Cleaned layer)
- `<stem>_mask.png` — union mask of every touched pixel
- `<stem>_overlay.jpg` — original tinted where strokes were detected
  (red = solid color fill, green = inpainted, yellow = detected strokes
  outside any text region — left untouched)
- `<stem>_detect.json` — text block boxes, erased component bboxes, method,
  and sampled `bg_color` hex for solid fills

Unreadable images are skipped with a `SKIP` line, not fatal.

### 2. Assemble PSDs with GIMP

Job JSON (batch several pages per invocation — GIMP startup is ~15 s):

```json
{
  "output_dir": "/abs/out",
  "pages": [
    {"source": "/abs/010.jpg", "cleaned": "/abs/out/detect/010_cleaned.png"},
    {"source": "/abs/011.jpg", "cleaned": "/abs/out/detect/011_cleaned.png"}
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

(`gimp_clean.py` also keeps a legacy mode — pages without a `"cleaned"` key are
cleaned inside GIMP from `mask_regions`/`regions` lists, including the
Resynthesizer `heal*` actions. Use only if the user explicitly asks for manual
region work.)

### 3. Add Photoshop paragraph text boxes

```bash
node <skill>/scripts/add_text_layers.mjs <output_dir> <stem1> <stem2> ...
```

For each `<stem>` this reads `<output_dir>/<stem>.psd` (from step 2) and
`<output_dir>/detect/<stem>_detect.json` (from step 1), and appends one
native Photoshop Type layer per entry in `text_blocks` — `shapeType: "box"`
(a fixed word-wrap paragraph box, matching Photoshop's Paragraph Type tool,
not the auto-sizing Point Type), positioned/sized to that block, pre-filled
with Lorem ipsum placeholder text, centered black 10–32px CCWildWords-Regular
(a manga/comic lettering font) by default. Rewrites the PSD in place. A page
with zero detected blocks is skipped (logged, not fatal) — nothing to add.

The font is referenced by PostScript name only, no font data is embedded —
Photoshop resolves it from fonts installed on the machine that opens the
file, substituting a fallback (with a missing-font warning, editability
unaffected) if it isn't installed there. Opening a page in Photoshop will
also show a one-time "update text layer" prompt per box the first time each
is touched; this is normal for programmatically written text layers (the
raster preview isn't pre-rendered) and does not affect editability.

If `<output_dir>` lives inside an actively-syncing cloud folder (Nextcloud,
Dropbox, etc.), a sync client can race a fresh write to that path and revert
it to an older version within seconds. Verify the file (byte size, or grep
for `TySh`) a moment after this step before trusting it, and prefer writing
first to a local, unsynced path if that happens.

### 4. Spot-check previews

Read each preview at page scale and confirm nothing is grossly wrong (missing
page, huge miscolored patch, unprocessed text the model plainly caught in the
overlay). Do NOT chase small imperfections — faint inpaint ghosts and the odd
missed glyph are expected and are the user's to fix manually against the
Original layer. When a page looks sane, add it to `progress.json`.

### 5. Report

Pages processed, output location, PSD layer structure, and anything notable
per page: text the model left (yellow in the overlay usually means protected
art, but check for real text the gate skipped) and art areas that were
inpainted (green) and may want manual restoration.
