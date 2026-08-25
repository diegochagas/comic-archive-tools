# clean-manga-text

A [Claude Code](https://claude.com/claude-code) skill that converts every
manga/doujinshi page image in a folder into a layered PSD file:

- **Layer "Original"** (bottom) — the untouched scan
- **Layer "Cleaned"** (top) — with CJK text removed, but **only** text sitting on
  a plain single-color background (white or black speech bubbles, boxes,
  margins). Text drawn over artwork — sound effects, artist signatures, captions
  crossed by linework — is deliberately left untouched, because automated
  inpainting over art is not reliable enough.

## How it works

1. **Detection** — [comic-text-detector](https://github.com/dmMaze/comic-text-detector)
   (ONNX, run locally via onnxruntime) produces a pixel-accurate mask of text
   strokes plus a color-coded review overlay per page.
2. **Review** — Claude views each overlay, keeps only real text blocks on plain
   backgrounds (whole-block decision), and draws allow boxes that exclude model
   false positives.
3. **Cleaning** — headless flatpak GIMP 3 repaints only the detected strokes
   inside the allow boxes (white or black fill) and exports the 2-layer PSD,
   plus a JPG preview.
4. **Verification** — Claude compares zoomed crops of every cleaned region
   against the original and reruns with corrected boxes until the page is clean.

The GIMP script also supports optional Resynthesizer-based healing actions for
text over artwork, but the skill only uses them when explicitly asked, with the
caveat that results are imperfect.

## Requirements

- Linux with [flatpak GIMP 3](https://flathub.org/apps/org.gimp.GIMP)
  (`org.gimp.GIMP`). The optional healing actions additionally need the
  Resynthesizer plugin flatpak.
- Python 3 with `venv`.
- ~100 MB disk for the detection model (downloaded by `setup.sh`).

## Install

```bash
git clone <this repo> ~/.claude/skills/clean-manga-text
~/.claude/skills/clean-manga-text/setup.sh
```

Then in Claude Code, ask to clean a folder of pages or invoke
`/clean-manga-text`. Output goes to a `psd/` folder next to the images by
default (PSDs, previews, and detection artifacts).

## Layout

```
SKILL.md               skill instructions (workflow, rules, job format)
scripts/detect_text.py text-stroke detection -> masks, overlays, component JSON
scripts/gimp_clean.py  GIMP 3 batch script -> masked fills/heals, PSD export
setup.sh               creates venv, installs deps, downloads the ONNX model
models/, venv/         created by setup.sh (not committed)
```
