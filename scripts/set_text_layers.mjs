#!/usr/bin/env node
// Replaces the text content of one or more existing native Photoshop text
// layers in a PSD (e.g. swapping the Lorem ipsum placeholder for a real
// translation), leaving every other layer byte-exact. Font/size/color/
// paragraph style are untouched -- only the string itself changes.
//
// Usage: node set_text_layers.mjs <psd> <edits.json> [--output <path>]
// edits.json: { "<layer index>": "new text", ... }  (index from
// list_text_layers.mjs) -- or use the layer name instead of the index.
// --output defaults to overwriting <psd> in place.

import * as fs from 'fs';
import * as path from 'path';
import { readPsd, writePsdBuffer } from 'ag-psd';

const [psdPath, editsPath] = process.argv.slice(2);
const outIdx = process.argv.indexOf('--output');
const outPath = outIdx !== -1 ? process.argv[outIdx + 1] : psdPath;

if (!psdPath || !editsPath) {
  console.error('Usage: node set_text_layers.mjs <psd> <edits.json> [--output <path>]');
  process.exit(1);
}

const edits = JSON.parse(fs.readFileSync(editsPath, 'utf8'));
const psd = readPsd(fs.readFileSync(psdPath), { useRawData: true });

let applied = 0;
for (const [key, newText] of Object.entries(edits)) {
  const idx = Number.isInteger(Number(key)) ? Number(key) : -1;
  const layer = idx >= 0
    ? psd.children[idx]
    : psd.children.find((l) => l.name === key);
  if (!layer || !layer.text) {
    console.log(`SKIP "${key}": no such text layer`);
    continue;
  }
  layer.text.text = newText;
  applied++;
}

fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, writePsdBuffer(psd, { generateThumbnail: false }));
console.log(`${path.basename(outPath)}: applied ${applied}/${Object.keys(edits).length} edit(s)`);
