#!/usr/bin/env node
// Injects one editable Photoshop "Paragraph Type Tool" text layer (a
// word-wrap box, PSD shapeType "box") per detected text block into a PSD
// already assembled by gimp_clean.py, stacked above "Cleaned". The box is
// positioned and sized to match the detected text block exactly, pre-filled
// with placeholder text in CCWildWords-Regular so the letterer sees the
// real lettering font immediately and just selects-and-types over it.
// Existing raster layers (Original, Cleaned) pass through byte-exact via
// ag-psd's raw-channel mode -- their pixels are never touched. GIMP itself
// cannot write native Photoshop text layers (its PSD exporter rasterizes
// them), so this step uses ag-psd to write the "TySh" layer info directly.
//
// Usage: node add_text_layers.mjs <output_dir> <stem> [<stem>...]
//
// For each <stem> expects <output_dir>/<stem>.psd (from gimp_clean.py) and
// <output_dir>/detect/<stem>_detect.json (from detect_text.py, for
// text_blocks). Rewrites the PSD in place. Stems with no PSD, no detect
// json, or zero text blocks are skipped (logged, not fatal).
//
// The font is referenced by PostScript name only (no font data is
// embedded) -- Photoshop resolves it from fonts installed on the machine
// that opens the file. If CCWildWords-Regular isn't installed there,
// Photoshop substitutes a fallback and shows a missing-font warning, but
// the layer stays fully editable either way.

import * as fs from 'fs';
import * as path from 'path';
import { readPsd, writePsdBuffer } from 'ag-psd';

const FONT = { name: 'CCWildWords-Regular' };
const PLACEHOLDER_TEXT = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.';
const MIN_FONT_SIZE = 10;
const MAX_FONT_SIZE = 32;
const LINES_PER_BOX = 7; // rough heuristic: box height / this many lines -> font size

function fontSizeFor(_w, h) {
  return Math.max(MIN_FONT_SIZE, Math.min(MAX_FONT_SIZE, Math.round(h / LINES_PER_BOX)));
}

function addTextLayers(outDir, stem) {
  const psdPath = path.join(outDir, `${stem}.psd`);
  const detectPath = path.join(outDir, 'detect', `${stem}_detect.json`);

  if (!fs.existsSync(psdPath)) {
    console.log(`SKIP ${stem}: no PSD at ${psdPath}`);
    return;
  }
  if (!fs.existsSync(detectPath)) {
    console.log(`SKIP ${stem}: no detect json at ${detectPath}`);
    return;
  }

  const detect = JSON.parse(fs.readFileSync(detectPath, 'utf8'));
  const blocks = detect.text_blocks || [];
  if (!blocks.length) {
    console.log(`${stem}: 0 text blocks, nothing to add`);
    return;
  }

  const psd = readPsd(fs.readFileSync(psdPath), { useRawData: true });

  for (const [i, [x, y, w, h]] of blocks.entries()) {
    psd.children.push({
      name: `Text ${i + 1}`,
      top: y,
      left: x,
      bottom: y + h,
      right: x + w,
      text: {
        text: PLACEHOLDER_TEXT,
        transform: [1, 0, 0, 1, x, y],
        left: 0,
        top: 0,
        right: w,
        bottom: h,
        orientation: 'horizontal',
        antiAlias: 'smooth',
        shapeType: 'box',
        boxBounds: [0, 0, w, h],
        style: {
          font: FONT,
          fontSize: fontSizeFor(w, h),
          fillColor: { r: 0, g: 0, b: 0 },
        },
        paragraphStyle: { justification: 'center' },
      },
    });
  }

  fs.writeFileSync(psdPath, writePsdBuffer(psd));
  console.log(`${stem}: added ${blocks.length} text layer(s)`);
}

function main() {
  const [outDir, ...stems] = process.argv.slice(2);
  if (!outDir || !stems.length) {
    console.error('Usage: node add_text_layers.mjs <output_dir> <stem> [<stem>...]');
    process.exit(1);
  }
  for (const stem of stems) {
    try {
      addTextLayers(outDir, stem);
    } catch (e) {
      console.log(`SKIP ${stem}: ${e.message}`);
    }
  }
}

main();
