#!/usr/bin/env node
// Exports one raster layer of a PSD to a PNG file, plus prints its
// left/top/width/height as JSON on stdout. Used to pull the Japanese source
// pieces out of a manually-assembled PSD so detect_text.py can run on them.
//
// Usage: node export_layer.mjs <psd> <layer_index> <out_png>
// layer_index is the 0-based index into psd.children (bottom-to-top order).

import * as fs from 'fs';
import { readPsd, initializeCanvas } from 'ag-psd';
import { createCanvas } from 'canvas';

initializeCanvas(createCanvas);

const [psdPath, idxArg, outPath] = process.argv.slice(2);
if (!psdPath || idxArg === undefined || !outPath) {
  console.error('Usage: node export_layer.mjs <psd> <layer_index> <out_png>');
  process.exit(1);
}
const idx = parseInt(idxArg, 10);

const psd = readPsd(fs.readFileSync(psdPath));
const layer = psd.children[idx];
if (!layer) {
  console.error(`No layer at index ${idx} (psd has ${psd.children.length} layers)`);
  process.exit(1);
}
const { canvas, left, top, right, bottom, name } = layer;
if (!canvas) {
  console.error(`Layer "${name}" has no raster canvas`);
  process.exit(1);
}
fs.writeFileSync(outPath, canvas.toBuffer('image/png'));

console.log(JSON.stringify({ name, left, top, right, bottom, width: canvas.width, height: canvas.height }));
