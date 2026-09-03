---
name: manga-translator-ptbr
description: Translate comic/manga/art-book pages to Brazilian Portuguese as layered PSDs. Two modes - (A) fill the placeholder ("Lorem ipsum") text boxes of already-lettered page PSDs, sourced from the English scanlation and/or the Japanese raw page embedded in the PSD; (B) start from raw images (any size, including 5000-10000 px scans with tiny print, covers, colophons, catalogue inserts) - detect every text block, build a PSD with "Original" + "Copy" raster layers and one editable Photoshop paragraph text box per block, pre-filled with the PT-BR translation. Use when the user asks to translate images/PSDs to Portuguese, add translated text boxes over detected text, or "generate PSDs with two layers and translated text boxes".
---

# Manga Translator (PT-BR)

Two modes. **Mode A** (below, original) fills placeholder boxes in PSDs the
lettering pipeline already built. **Mode B** (section at the end) goes from
raw images to translated PSDs in one pass - use it when the input is a
folder of images, not PSDs.

Fills native Photoshop text layers in a lettered manga page (built by the
lettering-prep pipeline) with real Brazilian Portuguese dialogue, replacing
the "Lorem ipsum" placeholder each box was created with.

This works on any folder of page PSDs that follow the convention used by
this repo's manga lettering tools: each PSD has one or more raster layers
holding the original-language source page(s), a final raster layer with the
lettered/target-language art, and native Photoshop paragraph text layers
(added by `scripts/add_text_layers.mjs`) positioned over each speech
balloon, each pre-filled with placeholder Latin text.

## Division of labor

The scripts below do all the mechanical PSD I/O byte-exactly (no
re-rasterizing, no touching any layer but the text content). Translation
judgment — reading the source art, matching each box to the right line of
dialogue, writing natural PT-BR that fits a balloon — is done by you
(Claude), not by any script.

## Scripts (in `scripts/`, run with `node <script>.mjs ...` from the repo root)

- `list_layers.mjs <psd>` — lists every layer (raster + text) with name,
  position, size; text layers include their current text. Use this first on
  each PSD to see what's there.
- `list_text_layers.mjs <psd>` — same, but text layers only. Faster when you
  already know the raster layout.
- `export_layer.mjs <psd> <layer_index> <out.png>` — exports one raster
  layer to a PNG (and prints its position/size) so you can view the source
  art with the Read tool. Needed because a raw `.psd` isn't directly
  viewable as an image.
- `set_text_layers.mjs <psd> <edits.json> [--output <path>]` — writes new
  text into one or more text layers. `edits.json` is `{ "<layer index or
  name>": "new text", ... }`. Defaults to overwriting the PSD in place;
  everything except the text layers' content is preserved byte-exact.

## Layer convention you'll encounter

- The **last raster (non-text) layer** is always the finished/lettered page
  — leave it alone, it's not a translation source.
- Every **other raster layer** is a piece of the original-language source
  page. Usually just one, named e.g. "Japanese"; sometimes several pieces
  (e.g. `Shinzo_011.jpg copy`) that together form a spread or composite —
  their `left`/`top` (from `list_layers.mjs`) tell you how they're
  positioned relative to the final page, so you can tell which piece sits
  under which text box.
- **Text layers** are the boxes to fill. Their `left`/`top`/`width`/`height`
  (in the *final page's* coordinate space) tell you which balloon they
  belong to — match them by position against the source art.

## Workflow per page

1. Run `list_layers.mjs` on the PSD. Note the source raster layer(s) and the
   text layers (position + current placeholder text).
2. Find the original-language source for this page. If you have a manifest
   mapping PSD → source chapter/page (build one with correlation against the
   raw folders if you don't — see "Resolving the source page" below), open:
   - The **English** scanlation page for that same chapter+filename, if the
     project has an English folder — usually the easiest to read, since it's
     already translated prose rather than Japanese script.
   - The **Japanese** raw page (export the PSD's own source raster layer(s)
     with `export_layer.mjs`, or open the raw file directly) when English
     isn't available, doesn't match, or a box's dialogue isn't legible in
     it.
3. For each text layer, using its box position to find the matching balloon
   in the source art, work out the line of dialogue/SFX and translate it to
   natural Brazilian Portuguese — matching register (casual speech, shouts,
   narration boxes read differently), keeping it plausible-length for the
   balloon (a text box that's tight and squarish wants a short line; don't
   pad or drastically shorten just to fit, use judgment).
4. Write all of a page's edits in one `edits.json` and apply with
   `set_text_layers.mjs` in a single call per page.
5. Spot check: re-run `list_text_layers.mjs` and confirm every layer's text
   changed and none were skipped (a "SKIP" line means the key didn't match
   any layer index/name — fix the key and retry).

Batch pages efficiently: there's no need to re-derive the source mapping per
page if you've already built a manifest (step 2) — reuse it across the whole
folder.

## Resolving the source page (when you don't already have a manifest)

Given a raw-page folder (chapters of sequentially-numbered raw pages, e.g.
`Shinzo_000.jpg, Shinzo_001.jpg, ...` restarting per chapter) and a folder of
page PSDs whose filenames don't share that numbering:

1. Export each PSD's source raster layer(s) to PNG (`export_layer.mjs`).
2. Downsample each to a small grayscale vector (e.g. 48×48, normalized) and
   compare via normalized cross-correlation against the same vectors computed
   for every raw page across all chapters (full search, not limited to
   nearby pages — chapter boundaries don't line up with PSD filenames).
   A true match scores close to 1.0; unrelated pages score well under 0.5.
3. For a PSD with multiple source pieces (a stitched spread, or several
   named layers), correlate each piece separately — a two-page spread stored
   as one wide layer should be split into left/right halves first and each
   half correlated independently (remember Japanese manga reads
   right-to-left: in a spread, the LEFT half is usually the chronologically
   LATER raw page).
4. Once you know a piece's chapter + raw filename, the English scanlation
   page (if the project has one) is very often the *same filename* inside
   the corresponding English chapter folder — check for that before assuming
   you need to build any fuzzier English-side matching.

This resolution is the slow/mechanical part — when translating a whole
folder, do it once for every PSD up front (cache the results) rather than
re-deriving it per page.

---

## Mode B - raw images -> translated PSDs (Original + Copy + PT-BR text boxes)

Output per image: `<out>/<stem>.psd` with raster layers **Original** and
**Copy** (both the untouched scan, pixel-exact) and one native Photoshop
*paragraph* Type layer **Text N** per text block, sized to the block and
pre-filled with the Brazilian Portuguese translation. Nothing is erased.
Works on any size (verified on 7008x10208 scans with 6 pt catalogue print).

All commands run from the repo root; python needs `onnxruntime`,
`opencv-python-headless`, `numpy`, `pillow` (the repo venv has them; in a
fresh sandbox `pip install --break-system-packages` them). Node needs
`node_modules` (ag-psd, canvas). For 7000x10000 pages give node
`--max-old-space-size=4096`.

### B1. Detect text blocks (no cleaning)

```bash
python3 scripts/detect_blocks.py <out_dir> <img1> [<img2> ...] [--min-tile 2048] [--no-fullpage]
```

Writes `<out_dir>/detect/<stem>_detect.json` (`text_blocks` = `[x,y,w,h]`
page px, reading order), `<stem>_overlay.jpg` (numbered boxes, 2000 px), and
`<stem>_raw.json`. Runs the comic-text-detector at page scale plus
overlapping tiles (`--tile`, default 2048 px source -> 1024 model input) so
tiny print on big scans is found; boxes are merged into blocks with
compactness limits so dense catalogue pages don't fuse into one blob.

- One 1024 px inference is ~1.4 s (with denormal-as-zero, which the scripts
  set - without it the same model takes ~90 s). A 6000 px page with
  `--min-tile 2048` is ~25 s; a 7000x10000 insert ~40 s. Keep each shell
  call under the tool timeout: one or two pages per call.
- Manga-like pages (colophons, captions, catalogue text) detect well. Large
  display logos, low-contrast spine text and stylised titles are usually
  missed or badly boxed - expect to fix those by hand (B2).
- JPEGs with an EXIF rotation tag are processed on the raw pixel grid;
  an EXIF-free `<stem>_upright.png` is written next to the json and
  recorded as `source_for_psd` - use THAT as the PSD source, otherwise
  node-canvas applies the rotation and the boxes land on the wrong grid.

### B2. Review and fix the blocks

Look at `<stem>_overlay.jpg` for the coarse picture. To *read* the text and
*measure* coordinates, render zoomed, gridded tiles (rulers show page px):

```bash
python3 scripts/overlay_tiles.py <out_dir>/detect/<stem>_detect.json <tiles_dir> --scale 0.6 [--region x,y,w,h]
python3 scripts/block_sheets.py  <out_dir>/detect/<stem>_detect.json <sheets_dir> --scale 0.6   # per-block crops
```

Keep every tile <= ~1400x1900 px so the Read tool shows it unscaled -
coordinates read off a downscaled view are systematically wrong (this bit
us: a 2640 px tile displayed at 2000 px shifted every box by 1.32x).

Overrides go in `<out_dir>/detect/<stem>_manual.json`, then re-run B1
(the model is skipped when `replace` is present):

```json
{"drop": [[x,y,w,h], ...],            // detected boxes whose centre falls inside are removed
 "add":  [[x,y,w,h], ...],            // appended (after the detected ones)
 "replace": [[x,y,w,h], ...],         // use exactly this list, in this order
 "snap": false}                       // true = tighten each hand box to the ink inside it
```

`snap` works on plain backgrounds; leave it false over art / low-contrast
text. Detected blocks are sorted into reading order *before* the manual
list is applied, so a `replace`/`add` list keeps its own order - that order
is what the translation indices below refer to.

What to box: every printed text that is *part of the page* - titles,
captions, prices, form labels, stamps ("品切れ" -> "ESGOTADO"), ISBN
lines, copyright, page numbers. Skip text that is artwork inside
reproduced book-cover thumbnails.

### B3. Translate

Write `<stem>.json` (one per page) with 1-based block indices:

```json
{"texts":  {"1": "Tenkuu Senki Shurato\nLIVRO MEMORIAL", "2": "Preço: ¥1.500 (¥1.456 + imposto)"},
 "styles": {"1": {"rotate": 90, "color": "#ffffff", "align": "left", "font": "Arial", "size": 40}}}
```

Style keys are optional per block: `rotate` 0/90/-90/180 (90 = reads
top-to-bottom, use it for spines and for Japanese vertical columns; a
section printed upside down is 180 for horizontal lines and -90 for its
columns), `color` (default: auto black/white from the block's luminance),
`size` px (default: auto-fit the text into the box), `align`, `font`
(default CCWildWords-Regular).

Translation conventions used so far: keep proper names/titles that are
already Latin (LOVE SONG, BANDAI, series names), Japanese titles in romaji
(天空戦記シュラト -> "Tenkuu Senki Shurato"), 大図鑑 -> "Grande
Enciclopédia", 定価 -> "Preço:", 本体 -> "(¥N + imposto)", 税込 -> "(com
imposto)", 予価 -> "preço previsto", 発売予定 -> "lançamento previsto",
品切れ -> "ESGOTADO", 残部僅少 -> "ÚLTIMAS UNIDADES", 注文書 -> "FORMULÁRIO
DE PEDIDO", 書店印 -> "Carimbo da livraria", 取次 -> "distribuidora".

A convenient way to keep boxes and texts together is a small python file
with `(box, text, style)` tuples that writes both `<stem>_manual.json`
(`replace`) and `<stem>.json` - see `Downloads/psd/translations/*_blocks.py`
style from the 2026-09-03 run (the merged `*_blocks.json` there are the
exact inputs used).

### B4. Build and verify

```bash
python3 scripts/merge_translations.py <out_dir>/detect/<stem>_detect.json <stem>.json <stem>_blocks.json
node --max-old-space-size=4096 scripts/build_translated_psd.mjs <source_for_psd> <stem>_blocks.json <out>/<stem>.psd
node --max-old-space-size=4096 scripts/verify_translated_psd.mjs <out>/<stem>.psd <source_for_psd> <stem>_blocks.json
python3 scripts/preview_psd_text.py <out>/<stem>.psd <source> <preview.jpg> --max 2600
```

`merge_translations.py` reports empty/unknown indices. `verify_*` checks
layer names, that Original/Copy are pixel-identical to the source, and that
every Text N carries its translation. `preview_psd_text.py` draws the boxes
and (approximate, DejaVu) text over the page - read it to catch a wrong
mapping (text in the wrong box), wrong rotation or a box that drifted.
`list_text_layers.mjs` now reports rotated boxes' page-space rect plus
`rotate`, `fontSize`, `color`, `font`, `align`.

Building is fast (a 71 MP page in ~4 s); a PSD is ~1.5-2.5x the JPEG size.

Photoshop notes (unchanged from the lettering pipeline): the font is
referenced by name only; Photoshop shows a one-time "update text layer"
prompt per box; the box is a fixed paragraph box so long translations may
need the font size lowered - the auto-fit is a heuristic (0.55 em advance).
