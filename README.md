# manga-letterer

A [Claude Code](https://claude.com/claude-code) skill that turns a folder of
manga/doujinshi page scans into layered PSD files ready to hand to a
letterer: the original text erased cleanly, and an editable Photoshop
paragraph text box already sitting in place of each speech bubble/caption,
pre-filled with placeholder text in a comic lettering font. No more
hand-drawing a Type tool box over every bubble before you can start
translating — open the PSD and start typing.

## Output: what's in the PSD

Every page becomes a PSD with:

- **Layer "Original"** (bottom) — the untouched scan, for reference or to
  restore anything the cleaning step damaged.
- **Layer "Cleaned"** — the same page with **all** detected CJK text erased,
  and **only** text: stroke detections are gated by the model's own
  text-block boxes and text-line map, so stroke-like false positives on art
  (decorative borders, hatching, screentone) stay untouched. Each erased
  region is filled with the predominant color around it: an exact sampled
  solid color when the surroundings are one plain color (white/black speech
  bubbles, grey caption boxes, colored banners, ...), or inpainted from the
  surrounding pixels when the text sits over artwork. Inpainted areas are
  imperfect by nature — restoration of anything worth keeping is manual, by
  copying from the Original layer.
- **One native Photoshop Type layer per detected text block** (top) — a real,
  editable **paragraph text box** (Photoshop's Paragraph Type tool: a fixed
  word-wrap box, not the auto-sizing Point Type), positioned and sized to
  match that text region exactly. Pre-filled with Lorem ipsum placeholder
  text set in **CCWildWords-Regular** (a manga/comic lettering font) so you
  see the actual lettering style immediately — select all, type the
  translation, done.

Every page gets a PSD even if nothing was detected (two identical raster
layers, no text boxes), so a whole folder converts completely in one pass.

## How it works

The pipeline is three separate tools chained together, each doing the one
thing it's actually good at:

1. **Detect + erase** (`scripts/detect_text.py`, Python/ONNX) —
   [comic-text-detector](https://github.com/dmMaze/comic-text-detector) (run
   locally via onnxruntime, no network calls) produces a pixel-accurate mask
   of text strokes plus text-region detections (block boxes + a line map)
   that gate it. The same script classifies each erased component's
   surroundings (plain single color vs. busy), solid-fills or inpaints it,
   and writes the fully cleaned page image plus a color-coded overlay and a
   JSON report (including each text block's bounding box — reused in step 3).
2. **Assemble the raster layers** (`scripts/gimp_clean.py`, headless flatpak
   GIMP 3) — stacks the cleaned page over the untouched original and exports
   the PSD plus a JPG preview.
3. **Add the paragraph text boxes** (`scripts/add_text_layers.mjs`, Node +
   [ag-psd](https://github.com/Agamnentzar/ag-psd)) — GIMP's own PSD exporter
   *rasterizes* any text layer on save (confirmed by inspecting its output
   byte-for-byte: no `TySh`/`EngineData` Photoshop Type-tool records at all),
   so it's structurally incapable of writing a real, editable Photoshop text
   layer. This step writes those binary layer records directly instead: one
   paragraph box per entry in step 1's detected `text_blocks`, appended above
   Cleaned. It rewrites just the PSD's layer list — the existing Original and
   Cleaned raster layers pass through byte-exact (verified pixel-for-pixel
   against the pre-step-3 file).

A fourth step, done by Claude rather than a script, spot-checks the previews
for gross failures (a page that failed to process, a badly wrong fill color)
before moving on — small imperfections over art are expected and left for
manual restoration, not chased automatically.

`gimp_clean.py` also keeps a legacy mode with per-region cleaning actions
(fills, Resynthesizer healing), used only if you explicitly ask for manual
region work instead of the automatic pipeline above.

## Fonts and editability

The text boxes reference their font (`CCWildWords-Regular`) by **PostScript
name only** — no font data is embedded in the PSD. Photoshop resolves the
actual glyphs from fonts installed on whichever machine opens the file. If
that machine doesn't have CCWildWords installed, Photoshop substitutes a
fallback font and shows a missing-font warning — the layer is still fully
editable either way, it just won't *look* right until the real font is
installed (or you pick a different one).

Photoshop will also show a one-time "update text layer" prompt the first
time you touch each box. This is normal for any text layer written
programmatically rather than by Photoshop itself (the raster preview isn't
pre-rendered) and has no effect on editing.

## Requirements

- Linux with [flatpak GIMP 3](https://flathub.org/apps/org.gimp.GIMP)
  (`org.gimp.GIMP`). The optional legacy healing actions additionally need
  the Resynthesizer plugin flatpak.
- Python 3 with `venv`.
- Node.js + npm (for the `ag-psd`-based text-layer step).
- ~100 MB disk for the detection model (downloaded by `setup.sh`).
- The `CCWildWords-Regular` font installed wherever you'll actually letter
  the pages in Photoshop, if you want the placeholder text to render
  correctly instead of falling back.

## Install

```bash
git clone <this repo> ~/.claude/skills/manga-letterer
~/.claude/skills/manga-letterer/setup.sh
```

`setup.sh` creates the Python venv, downloads the ONNX detection model, and
runs `npm install` for the `ag-psd` dependency. Then in Claude Code, ask to
clean a folder of pages or invoke `/manga-letterer`. Output goes to a `psd/`
folder next to the images by default (PSDs, previews, and detection
artifacts).

If the output folder lives inside an actively-syncing cloud drive
(Nextcloud, Dropbox, ...), be aware the sync client can race a fresh write
and revert it to an older version within seconds — verify the result a
moment after writing, or write to a local, unsynced path first if that
happens.

## Layout

```
SKILL.md                     skill instructions (workflow, job format)
scripts/detect_text.py       text detection + erase -> cleaned page, mask, overlay, JSON
scripts/gimp_clean.py        GIMP 3 batch script -> raster layer assembly, PSD export
scripts/add_text_layers.mjs  ag-psd script -> native Photoshop paragraph text layers
setup.sh                     creates venv + node_modules, installs deps, downloads the ONNX model
models/, venv/, node_modules/  created by setup.sh (not committed)
```
