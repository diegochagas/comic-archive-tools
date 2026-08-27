# comic-archive-tools

A toolkit for working with comic/manga page archives: packaging and
extracting CBR/CBZ archives, converting between PDF/PSD/image formats, small
image utilities, and a Claude Code skill that automates Photoshop lettering
prep (text detection, cleaning, paragraph text boxes). Each piece below is
independent — use whichever one you need.

## Overview

| Script / skill | What it does |
| --- | --- |
| **Manga lettering pipeline** (`SKILL.md` + `scripts/`) | Claude Code skill — turns manga/doujinshi page scans into layered, letter-ready PSDs: text detected and erased, a native Photoshop paragraph text box added per speech bubble. |
| `tools/images_to_cbr.py` | Packages a folder of images into a `.cbr` archive. |
| `tools/cbr_to_images.py` | Extracts `.cbr`/`.cbz`/`.zip` comic archives into image folders. |
| `tools/pdf_to_images.py` | Extracts PDF pages as JPG images. |
| `tools/psd_to_jpg.py` | Converts Photoshop `.psd`/`.psb` files to JPG. |
| `tools/rotate_images.py` | Rotates every image in a folder by a given angle. |
| `tools/stretch_pngs.py` | Stretches every PNG in a folder to exact dimensions. |
| `tools/transcribe_japanese_images.py` | Transcribes Japanese text from every image in a folder into a block-organized TXT file. |
| `tools/translate_japanese_texts_ptbr.py` | Translates a block-organized Japanese transcription TXT into Brazilian Portuguese. |

---

## Manga lettering pipeline (Claude Code skill)

Turns a folder of manga/doujinshi page scans into layered PSD files ready to
hand to a letterer: the original text erased cleanly, and an editable
Photoshop paragraph text box already sitting in place of each speech
bubble/caption, pre-filled with placeholder text in a comic lettering font.
No more hand-drawing a Type tool box over every bubble before you can start
translating — open the PSD and start typing.

### Output: what's in the PSD

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

### How it works (fixed pipeline)

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

### Modular alternative: incremental PSD building

Alongside the fixed pipeline above, three scripts let you build and extend PSDs
incrementally, each usable on its own and each accepting a folder or a single
file:

- **`scripts/image_to_psd.py`** — folder or single image -> a PSD with two
  identical raster layers, `Original` (bottom) and `Copy` (top). No detection,
  no cleaning: just the starting point for the two scripts below.
- **`scripts/add_cleaned_layer.py`** — folder or single PSD -> a *copy* of the
  PSD with a new `Cleaned` layer appended on top, with all detected text
  erased exactly like `detect_text.py` does in the fixed pipeline. Detects
  text on the PSD's `Original` layer (or reuses a previous `detect_text.py`
  run's JSON via `--detect-dir`, instead of re-running the model). Never
  modifies the input file.
- **`scripts/add_text_boxes.py`** — folder or single PSD -> appends one native
  Photoshop paragraph text layer per detected text region, in place. Detects
  text the same way (fresh, or reused via `--detect-dir`).

Recommended stacking order when using all three: `image_to_psd.py` ->
`add_cleaned_layer.py` -> `add_text_boxes.py` (Original -> Cleaned -> text
boxes, bottom to top) — this reproduces the same end result as the fixed
pipeline, one composable step at a time. The last two can safely run in either
order on the same file: `add_cleaned_layer.py` never re-opens the PSD through
GIMP (it appends the raster layer directly with `ag-psd`), so it can't
rasterize/corrupt Photoshop text layers `add_text_boxes.py` already wrote.

```
python scripts/image_to_psd.py <folder-or-image> [--output <dir>]
python scripts/add_cleaned_layer.py <folder-or-psd> [--output <dir>] [--layer-name Original] [--detect-dir <dir>]
python scripts/add_text_boxes.py <folder-or-psd> [--layer-name Original] [--detect-dir <dir>]
```

### Fonts and editability

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

### Requirements

- Linux with [flatpak GIMP 3](https://flathub.org/apps/org.gimp.GIMP)
  (`org.gimp.GIMP`). The optional legacy healing actions additionally need
  the Resynthesizer plugin flatpak.
- Python 3 with `venv`.
- Node.js + npm (for the `ag-psd`-based text-layer steps).
- ~100 MB disk for the detection model (downloaded by `setup.sh`).
- Tesseract OCR binary on `PATH` (`sudo apt install tesseract-ocr`), only
  needed for `tools/transcribe_japanese_images.py`.
- The `CCWildWords-Regular` font installed wherever you'll actually letter
  the pages in Photoshop, if you want the placeholder text to render
  correctly instead of falling back.

### Install as a skill

```bash
git clone <this repo> ~/.claude/skills/manga-letterer
~/.claude/skills/manga-letterer/setup.sh
```

`setup.sh` creates the Python venv (also covers the standalone `tools/`
scripts' deps), downloads the ONNX detection model and the Japanese Tesseract
language data (`tools/tessdata/`), and runs `npm install` for the
`ag-psd`/`pngjs` dependencies. Then in Claude Code, ask to clean a folder of
pages or invoke `/manga-letterer`. Output goes to a `psd/` folder next to the
images by default (PSDs, previews, and detection artifacts).

If the output folder lives inside an actively-syncing cloud drive
(Nextcloud, Dropbox, ...), be aware the sync client can race a fresh write
and revert it to an older version within seconds — verify the result a
moment after writing, or write to a local, unsynced path first if that
happens.

---

## Comic archive packaging

`tools/images_to_cbr.py` and `tools/cbr_to_images.py` package and unpack
`.cbr`/`.cbz` comic archives.

### tools/images_to_cbr.py

Packages a folder of images into a `.cbr` file, which is a ZIP archive renamed for comic book readers.

By default, images are added exactly as they are. Optional flags can convert images to JPEG and resize tall images before they are written into the archive.

#### How it works

- If the target folder contains subfolders, each subfolder is packaged into its own `.cbr` file saved in the target folder.
- If the target folder contains images directly and no subfolders, the folder is packaged into a single `.cbr` saved in the parent folder.
- Existing `.cbr` files are skipped unless `--overwrite` is passed.

Supported image formats: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.bmp`, `.tiff`, `.tif`

#### Requirements

- Python 3.10+
- Standard library only for as-is packing
- [Pillow](https://pillow.readthedocs.io/) when using `--convert-jpeg` or `--max-height`

```
pip install pillow
```

#### Usage

```
python tools/images_to_cbr.py <folder> [--convert-jpeg] [--max-height <pixels>] [--quality <number>] [--overwrite]
```

| Flag                  | Description                                             | Default |
| --------------------- | ------------------------------------------------------- | ------- |
| `--convert-jpeg`      | Convert all images to JPEG before packaging             | Off     |
| `--max-height <px>`   | Resize images taller than this height; outputs JPEG     | Off     |
| `--quality <number>`  | JPEG quality for converted or resized images, 1-100     | `90`    |
| `--overwrite`         | Replace existing `.cbr` files                           | Off     |

#### Examples

Pack each subfolder of a directory into its own CBR:

```
python tools/images_to_cbr.py "/path/to/comics"
```

Pack all images in one folder into one CBR:

```
python tools/images_to_cbr.py "/path/to/chapter1"
```

Convert to JPEG and resize images taller than 2500 pixels:

```
python tools/images_to_cbr.py "/path/to/chapter1" --convert-jpeg --max-height 2500
```

### tools/cbr_to_images.py

Extracts `.cbr`, `.cbz`, and `.zip` comic book archives into image folders.

The script detects whether each archive is ZIP-based or RAR-based, then extracts it into a folder with the same base name without renaming the original archive.

#### How it works

- Scans only the target folder itself for `.cbr`, `.cbz`, and `.zip` files.
- Extracts each archive into a sibling folder with the same base name.
- If an output folder already exists, a numeric suffix is added, such as `Comic (1)`.
- If extraction fails, the partially created output folder is removed.
- ZIP-based archives are extracted with Python's standard library.
- RAR-based `.cbr` files are extracted with WinRAR, UnRAR, or 7-Zip when one is installed or available on `PATH`.
- `.zip` files are included so a previously renamed archive can still be extracted.

Example:

```
/path/to/comics/Chapter 01.cbr -> /path/to/comics/Chapter 01/...
```

#### Requirements

- Python 3.10+
- Standard library only for ZIP-based `.cbz` files
- WinRAR, UnRAR, or 7-Zip for RAR-based `.cbr` files

#### Usage

```
python tools/cbr_to_images.py <folder> [--dry-run] [--first-only]
```

| Flag           | Description                                                                  | Default |
| -------------- | ----------------------------------------------------------------------------- | ------- |
| `--dry-run`    | Show planned extractions without changing files                              | Off     |
| `--first-only` | Extract only the first image from each archive and save it to the same folder | Off     |

#### Examples

Extract all CBR/CBZ archives in a folder:

```
python tools/cbr_to_images.py "/path/to/comics"
```

Preview what would happen first:

```
python tools/cbr_to_images.py "/path/to/comics" --dry-run
```

Extract only the first image (cover) from every archive in the folder:

```
python tools/cbr_to_images.py "/path/to/comics" --first-only
```

Each archive produces one image file next to itself named `<archive stem>.<ext>` (e.g. `Chapter 01.cbr` → `Chapter 01.jpg`). Combine with `--dry-run` to preview which files would be created.

---

## PDF & PSD conversion

`tools/pdf_to_images.py` and `tools/psd_to_jpg.py` convert between PDF/PSD
source files and plain images.

### tools/pdf_to_images.py

Extracts PDF pages as JPG images.

#### How it works

For each PDF found in the target folder, the script renders every page as a JPG image at the requested DPI.
After rendering, it checks that the extracted JPG count matches the PDF page count.

By default, each PDF gets its own output folder:

```
/path/to/pdfs/Comic.pdf -> /path/to/pdfs/Comic/0001.jpg
```

With `--single-folder`, every PDF is extracted into one shared folder, and output filenames include the PDF name:

```
/path/to/pdfs/pdfs/Comic_0001.jpg
```

#### Requirements

- Python 3.7+
- [PyMuPDF](https://pymupdf.readthedocs.io/)

```
pip install pymupdf
```

#### Usage

```
python tools/pdf_to_images.py <folder> [--dpi <number>] [--overwrite] [--single-folder] [--output <folder>]
```

If you omit the folder path, the script will prompt you to enter it.

| Flag                | Description                                                | Default                       |
| ------------------- | ------------------------------------------------------------ | ------------------------------ |
| `--dpi <number>`    | Rendering resolution in DPI                                | `150`                         |
| `--overwrite`       | Replace existing output folders                            | Off                           |
| `--single-folder`   | Extract all PDFs into one shared image folder              | Off                           |
| `--output <folder>` | Shared output folder; only valid with `--single-folder`    | `<folder>/<folder_name>` |

#### Examples

Extract each PDF into its own folder:

```
python tools/pdf_to_images.py "/path/to/pdfs"
```

Extract at higher resolution:

```
python tools/pdf_to_images.py "/path/to/pdfs" --dpi 300
```

Extract all PDFs into one folder:

```
python tools/pdf_to_images.py "/path/to/pdfs" --single-folder
```

Extract all PDFs into a specific folder:

```
python tools/pdf_to_images.py "/path/to/pdfs" --single-folder --output "/path/to/all-images"
```

To turn extracted images into CBR files, run `tools/images_to_cbr.py` on the folder that contains the image folders.

### tools/psd_to_jpg.py

Converts Photoshop `.psd` and `.psb` files into high-quality `.jpg` files without changing their pixel dimensions.

#### How it works

- Scans the source folder recursively for `.psd` and `.psb` files.
- Saves JPG files into a separate output folder while preserving the source folder structure.
- Uses the flattened PSD/PSB composite image; it does not export individual layers.
- With `--show-all-layers`, ignores the saved composite and instead recomposites the file with every layer and group forced visible, using `psd-tools`.
- Transparent images are flattened against a matte background color before saving as JPG.
- Existing JPG files are skipped when they are newer than the source file unless `--overwrite` is passed.

If no output folder is provided, JPG files are written to a sibling folder named `<source folder> JPG`.

#### Requirements

- Python 3.10+
- [Pillow](https://pillow.readthedocs.io/)
- [psd-tools](https://psd-tools.readthedocs.io/) with the `composite` extras, only needed for `--show-all-layers`

```
pip install pillow
pip install "psd-tools[composite]"
```

#### Usage

```
python tools/psd_to_jpg.py <source> [--output <folder>] [--background <color>] [--overwrite] [--show-all-layers] [--limit <number>]
```

| Flag                   | Description                                                  | Default                    |
| ---------------------- | -------------------------------------------------------------- | ---------------------------- |
| `source`               | Folder to scan recursively for PSD/PSB files                 | Required                   |
| `-o`, `--output <dir>` | Output folder for generated JPG files                        | `<source folder> JPG`      |
| `--background <color>` | Matte color used when flattening transparent files           | `white`                    |
| `--overwrite`          | Replace JPGs even when they are newer than the source PSD/PSB | Off                        |
| `--show-all-layers`    | Force every layer and group visible before flattening (requires `psd-tools`) | Off         |
| `--limit <number>`     | Convert only the first N files, useful for testing           | `0` / no limit             |

#### Examples

Convert a specific folder:

```
python tools/psd_to_jpg.py "/path/to/psd-files"
```

Write JPG files to a specific output folder:

```
python tools/psd_to_jpg.py "/path/to/psd-files" --output "/path/to/jpg-output"
```

Flatten transparent images against a black background:

```
python tools/psd_to_jpg.py "/path/to/psd-files" --background black
```

Render with hidden layers and groups forced visible:

```
python tools/psd_to_jpg.py "/path/to/psd-files" --show-all-layers
```

Test with only the first five PSD/PSB files:

```
python tools/psd_to_jpg.py "/path/to/psd-files" --limit 5
```

---

## Image utilities

`tools/rotate_images.py` and `tools/stretch_pngs.py` are small single-purpose
image transforms.

### tools/rotate_images.py

Rotates all images in a folder by a specified number of degrees, overwriting the originals in place.

#### Requirements

- Python 3.7+
- [Pillow](https://pillow.readthedocs.io/)

```
pip install pillow
```

#### Usage

```
python tools/rotate_images.py <folder> [degrees]
```

`degrees` defaults to `90` if not specified.

#### Examples

Rotate all images 90 degrees clockwise:

```
python tools/rotate_images.py "/path/to/images"
```

Rotate all images 180 degrees:

```
python tools/rotate_images.py "/path/to/images" 180
```

#### Notes

- Images are overwritten in place. Make a backup first if needed.
- Supported formats: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.tiff`, `.webp`

### tools/stretch_pngs.py

Stretches every PNG image in a folder to an exact width and height. The resized images are saved in an `output` subfolder, leaving the originals unchanged.

#### Requirements

- Python 3.7+
- [Pillow](https://pillow.readthedocs.io/)

```
pip install pillow
```

#### Usage

```
python tools/stretch_pngs.py <folder> <width> <height>
```

- `folder`: folder containing the PNG images
- `width`: target width in pixels
- `height`: target height in pixels

#### Examples

Stretch all PNG files to 1920 x 1080 pixels:

```
python tools/stretch_pngs.py "/path/to/images" 1920 1080
```

Stretch all PNG files to 800 x 1200 pixels:

```
python tools/stretch_pngs.py "/path/to/images" 800 1200
```

#### Notes

- Only PNG files directly inside the specified folder are processed; subfolders are not scanned.
- The aspect ratio is not preserved. Each image is stretched to the exact dimensions provided.
- Output is written to `<folder>/output` using the original filenames. Existing files with the same names are overwritten.
- Images are resized with Pillow's high-quality LANCZOS resampling filter.

---

## Japanese OCR & translation

`tools/transcribe_japanese_images.py` and `tools/translate_japanese_texts_ptbr.py`
form a Japanese OCR + Portuguese translation pipeline for manga/novel page
scans: the first produces a block-organized transcription, and the second
translates it, keeping the same block structure so each translated block
still maps back to its source image.

### tools/transcribe_japanese_images.py

Transcribes Japanese text from every image in a folder into a UTF-8 `.txt` file.

The output is organized in blocks. Each block starts with the original image filename, so it is easy to review or translate page by page.

Example output block:

```
## 10-11.jpg

Japanese OCR text for this image...

---
```

#### How it works

- Scans only the target folder itself for supported image files.
- Sorts image filenames naturally, so `2-3.jpg` comes before `10-11.jpg`.
- Uses Tesseract OCR with Japanese language data.
- Defaults to `jpn_vert+jpn` and `--psm 5`, which works better for many vertical Japanese novel scans.
- Downscales very large images before OCR so oversized scans do not stall processing.
- Writes one text block per original image file.
- Caches each image OCR result next to the output file, so reruns are faster.

Supported image formats: `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`, `.bmp`, `.webp`

#### Requirements

- Python 3.10+ with [Pillow](https://pillow.readthedocs.io/) (already in `venv/` if you ran `setup.sh`)
- Tesseract OCR binary on `PATH` (`sudo apt install tesseract-ocr`)
- Japanese Tesseract data: `jpn.traineddata` and `jpn_vert.traineddata` — `setup.sh` downloads both into `tools/tessdata/`, which the script uses automatically

#### Usage

```
python tools/transcribe_japanese_images.py <folder> [--output <txt>] [--lang <langs>] [--psm <number>] [--max-side <pixels>] [--ocr-timeout <seconds>] [--no-cache]
```

| Flag                      | Description                                                        | Default                          |
| ------------------------- | ------------------------------------------------------------------ | --------------------------------- |
| `--output`, `-o <txt>`    | Output TXT file                                                    | `<folder>/japanese_transcription.txt` |
| `--tesseract <path>`      | Full path to the tesseract binary                                  | Auto-detected on `PATH`          |
| `--tessdata-dir <folder>` | Folder containing Tesseract language data                          | `tools/tessdata`                 |
| `--lang <langs>`          | Tesseract OCR language setting                                     | `jpn_vert+jpn`                   |
| `--psm <number>`          | Tesseract page segmentation mode                                   | `5`                               |
| `--max-side <pixels>`     | Resize images larger than this on the longest side before OCR      | `4000`                            |
| `--ocr-timeout <seconds>` | Maximum OCR time for one image                                     | `240`                             |
| `--no-cache`              | Disable per-image OCR cache                                        | Off                                |

#### Examples

Transcribe all images in a folder:

```
python tools/transcribe_japanese_images.py "/path/to/images"
```

Write the transcription to a specific file:

```
python tools/transcribe_japanese_images.py "/path/to/images" --output "/path/to/japanese_text.txt"
```

Try horizontal Japanese OCR instead of vertical OCR:

```
python tools/transcribe_japanese_images.py "/path/to/images" --lang jpn --psm 6
```

### tools/translate_japanese_texts_ptbr.py

Translates a block-organized Japanese transcription `.txt` file into Brazilian Portuguese.

It expects the input file generated by `transcribe_japanese_images.py`, keeps the same block structure, and writes a new `.txt` file where each block is still identified by the original image filename.

#### How it works

- Reads blocks that start with `## image-name.jpg`.
- Translates each image block separately.
- Keeps the original image filename as the block heading.
- Writes UTF-8 text with the same `---` separator between blocks.
- Caches each translated block next to the output file, so reruns are faster.

#### Requirements

- Python 3.10+
- [deep-translator](https://pypi.org/project/deep-translator/) (already in `venv/` if you ran `setup.sh`, otherwise `pip install deep-translator`)
- Internet access for Google Translate requests

#### Usage

```
python tools/translate_japanese_texts_ptbr.py <japanese_txt> [--output <txt>] [--source <lang>] [--target <lang>] [--no-cache]
```

| Flag                   | Description                         | Default                  |
| ---------------------- | ------------------------------------| ------------------------- |
| `--output`, `-o <txt>` | Output translated TXT file          | `<input_stem>_pt_br.txt` |
| `--source <lang>`      | Source language for translation     | `ja`                      |
| `--target <lang>`      | Target language for translation     | `pt`                      |
| `--no-cache`           | Disable per-block translation cache | Off                       |

#### Examples

Translate the default transcription file:

```
python tools/translate_japanese_texts_ptbr.py "/path/to/images/japanese_transcription.txt"
```

Write the translation to a specific file:

```
python tools/translate_japanese_texts_ptbr.py "/path/to/japanese_text.txt" --output "/path/to/portuguese_pt_br.txt"
```

---

## Layout

```
SKILL.md                        manga-letterer skill instructions (workflow, job format)
scripts/detect_text.py          text detection + erase -> cleaned page, mask, overlay, JSON
scripts/gimp_clean.py           GIMP 3 batch script -> raster layer assembly, PSD export (fixed pipeline)
scripts/gimp_base_psd.py        GIMP 3 batch script -> base 2-layer PSD, no cleaning (image_to_psd.py)
scripts/gimp_export_layer.py    GIMP 3 batch script -> exports one named PSD layer to PNG
scripts/detect_or_reuse.py      shared helper: reuse a previous detect_text.py run or generate one
scripts/image_to_psd.py         CLI: folder/image -> base PSD (Original + Copy)
scripts/add_cleaned_layer.py    CLI: folder/PSD -> copy with a new Cleaned layer appended
scripts/add_cleaned_layer.mjs   ag-psd script -> appends a raster layer to an existing PSD
scripts/add_text_boxes.py       CLI: folder/PSD -> native Photoshop paragraph text layers appended
scripts/add_text_layers.mjs     ag-psd script -> native Photoshop paragraph text layers (also used by the fixed pipeline)
setup.sh                        creates venv + node_modules, installs deps, downloads the ONNX model + tessdata
models/, venv/, node_modules/   created by setup.sh (not committed)
tools/                          comic archive packaging, PDF/PSD conversion, image utilities, and Japanese OCR/translation scripts
tools/tessdata/                 Japanese Tesseract language data, downloaded by setup.sh (not committed)
```
