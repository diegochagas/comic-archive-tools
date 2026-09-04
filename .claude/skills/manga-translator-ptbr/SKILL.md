---
name: manga-translator-ptbr
description: Translate comic/manga/art-book pages to Brazilian Portuguese as layered PSDs. Two modes - (A) fill the placeholder ("Lorem ipsum") text boxes of already-lettered page PSDs, sourced from the English scanlation and/or the Japanese raw page embedded in the PSD; (B) start from raw images (a single page or a whole folder; any size, including 5000-10000 px scans with tiny print, covers, colophons, catalogue inserts) - detect every text block, merge Japanese vertical columns into paragraphs, build a PSD with an "Original" raster layer, a "Copy" layer with the source text erased, and one editable Photoshop paragraph text box per block, pre-filled with the PT-BR translation. Use when the user asks to translate images/PSDs to Portuguese, add translated text boxes over detected text, clean text off a page, or "generate PSDs with two layers and translated text boxes".
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

## Mode B - raw images -> translated PSDs (Original + cleaned Copy + PT-BR text boxes)

Output per image: `<out>/<stem>.psd` with raster layers **Original** (the
untouched scan, pixel-exact) and **Copy** (same page with the source-language
text erased) plus one native Photoshop *paragraph* Type layer **Text N** per
text block, sized to the block and pre-filled with the Brazilian Portuguese
translation. Works on any size (verified on 7008x10208 scans with 6 pt
catalogue print, and on a 117-page A4 art book at ~2100x3000).

Pass `--copy-image` to make Copy the cleaned render; without it Copy is a
pixel-identical duplicate of Original (the older behaviour, still valid when
the letterer wants to erase by hand).

All commands run from the repo root; python needs `onnxruntime`,
`opencv-python-headless`, `numpy`, `pillow` (the repo venv has them; in a
fresh sandbox `pip install --break-system-packages` them). Node needs
`node_modules` (ag-psd, canvas). For 7000x10000 pages give node
`--max-old-space-size=4096`.

### Pipeline at a glance (whole-folder run)

```
detect_blocks.py      -> <stem>_detect.json         (raw blocks, one per column/line)
merge_columns.py      -> <stem>_merged.json         (paragraph-sized blocks) +
                         <stem>_merged_overlay.jpg  (numbered, 1000 px - READ THIS to translate)
  [you write]            tr/<stem>.json             (PT-BR keyed by overlay index)
assemble_translation.py -> final/<stem>_blocks.json (boxes + texts + styles, page px)
clean_blocks.py       -> final/<stem>_cleaned.png   (erased using the FINAL boxes)
build_translated_psd.mjs --copy-image -> <stem>.psd
verify_translated_psd.mjs --copy-image
preview_psd_text.py   -> preview/<stem>.jpg
```

Steps B1-B2 below are the older single-page path (hand-authored
`_manual.json` + `merge_translations.py`); it still works and is the right
choice for one-off pages with tricky layout. B1b-B4b are the folder path.

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

### B1b. Merge columns into paragraphs (folder path)

```bash
python3 scripts/merge_columns.py <out_dir>/detect/*_detect.json [--width 1000]
```

The detector returns one block per *vertical column* of Japanese text (a
dense interview page gives 100+ thin boxes) and sometimes one block per
*line* of a horizontal caption. Neither is a sensible Photoshop box for a
PT-BR translation, which runs horizontally. `merge_columns.py` unions:

- neighbouring columns of one paragraph (adjacent horizontally, sharing
  >= 60% of their height),
- fragments of a single column stacked vertically,
- a column group directly above/below another whose x-range contains it
  (columns interrupted by a photo),
- stacked lines of one horizontal caption.

It writes `<stem>_merged.json` (same schema, `text_blocks` in reading order:
rows top->bottom, right-to-left inside a row of columns, left-to-right for
horizontal text; the raw list is kept as `text_blocks_detected`) and
`<stem>_merged_overlay.jpg`, a `--width` px page with every block numbered.

**That overlay is the working document.** Read it to see the layout and the
box numbers; zoom into the page itself (crops via PIL at 0.7-1.2x) to
actually read the Japanese - the 1000 px overlay is too small for body text.

Merging is heuristic. On art-book caption pages it lands well; on dense
interview pages expect to hand-author the paragraph boxes with `replace`
(next step), which is often faster than fighting the merge.

### B2b. Translate against the overlay

Write `tr/<stem>.json`, one per page. **All coordinates are in OVERLAY
pixels** (the `--width` of the merged overlay, default 1000), so boxes can be
read straight off that image; `assemble_translation.py` scales them to page
px.

```json
{"texts":   {"1": "...", "3": "..."},
 "styles":  {"1": {"color": "#ffffff", "rotate": 90, "size": 40, "align": "left"}},
 "drop":    [2, 4],
 "box":     {"5": [x, y, w, h]},
 "add":     [[[x, y, w, h], "texto", {"color": "#d0202a"}]],
 "replace": [[[x, y, w, h], "texto", {}]]}
```

- `texts` / `styles` are keyed by the **merged overlay index** (1-based).
- `drop` discards a block: use it for false positives, for logos and artwork
  the detector boxed, and for handwritten margin scribbles you are not
  translating.
- `box` overrides one block's rectangle (a merged box that swallowed a
  neighbour, or a title box that should span the banner).
- `add` appends boxes the detector missed - display titles, spine text,
  section headers on dark bands.
- `replace` ignores detection entirely and uses exactly this list, in this
  order. **Use it for any page whose layout you are re-cutting** (dense
  interviews, contents pages, letter columns): it is the least fiddly way to
  express "here are the 18 paragraphs and what each says".

A box taller than 2.5x its width and under 150 page px wide gets
`rotate: 90` automatically unless a style says otherwise, so narrow side
captions still read down the column like the original did.

### B3. Translate (single-page path)

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

From the Shurato art book (anime setting-material books generally):
設定資料集 -> "Coletânea de material de ambientação", 八部衆 -> "Os Oito
Guardiões", 神将 -> "general divino", 光流(ソーマ) -> "fluxo de luz (Soma)",
神甲冑(シャクティ) -> "Armadura Divina (Shakti)", 転生 -> "reencarnação",
必殺技 -> "golpe especial", 真言 -> "mantra", スタッフ表 -> "equipe",
声優 -> "dublador(a)", 絵コンテ -> "storyboard", 作画監督 -> "direção de
animação", 初期設定 -> "material de produção inicial", おまけ -> "extras",
同人誌 -> "fanzine". Titles of episodes/albums stay translated, series and
company names stay as they are (Tatsunoko, King Record, BANDAI). Mantras and
attack names stay in romaji ("On Shura Sowaka", "Shura Mahaken"). Keep the
book's chatty fan-magazine register - it jokes about the characters, so the
PT-BR should too. Song lyrics: leave a bracketed placeholder rather than
reproducing them.

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

### B4b. Build and verify (folder path)

```bash
python3 scripts/assemble_translation.py <d>/<stem>_merged.json tr/<stem>.json final/<stem>_blocks.json
cp final/<stem>_blocks.json final/<stem>_detect.json      # clean_blocks reads a detect-shaped json
python3 scripts/clean_blocks.py final/<stem>_detect.json
node --max-old-space-size=4096 scripts/build_translated_psd.mjs <src>.png final/<stem>_blocks.json <out>/<stem>.psd --copy-image final/<stem>_cleaned.png
node --max-old-space-size=4096 scripts/verify_translated_psd.mjs <out>/<stem>.psd <src>.png final/<stem>_blocks.json --copy-image final/<stem>_cleaned.png
python3 scripts/preview_psd_text.py <out>/<stem>.psd <src>.png preview/<stem>.jpg --max 1400
```

`clean_blocks.py` erases only inside the **final** boxes, so anything you
dropped (art, handwriting, logos) survives untouched on the Copy layer. Per
block it unions the page-scale stroke segmentation with a crop-scale pass
(large display text is lost at page scale) and, when the block sits on a
uniform background, fills every pixel that differs from the sampled
background colour - which catches stylised titles the model misses. Each
component is then filled with the sampled surrounding colour, or inpainted
when the surroundings are busy. `<stem>_clean_overlay.jpg` tints what was
touched (red = fill, green = inpaint) - check it before building.

Run the whole folder in chunks: detect+clean is ~15-25 s/page on 2 cores and
a shell call may be capped at ~3 min, so loop 5-8 pages per call with a
"skip if the output already exists" guard.

**Verify the batch at the end**, not just per page: read every PSD with
ag-psd and assert Original+Copy exist and no Type layer is empty. An empty
box means a `texts` key was forgotten - and note that `verify_*` failing
does *not* delete the PSD it just wrote, so a rerun guarded on "psd exists"
will skip the broken page. Fix the json, then rebuild that page explicitly.

Timings from the 117-page Shurato art book (2026-09-04): detect+merge+clean
~45 min total, 1011 text boxes, PSDs ~40 MB each (4.9 GB for the book).
