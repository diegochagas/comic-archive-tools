#!/usr/bin/env node
// Lists every layer in a PSD (raster and text), with name, position/size,
// and for text layers the current text. Used by the manga-translator-ptbr
// skill to figure out which raster layers are the Japanese source pieces
// (everything except the last raster layer, which is the lettered page)
// and which are the placeholder text boxes to fill in.
//
// Usage: node list_layers.mjs <psd>
// Output (stdout): JSON array of
//   { index, name, isText, left, top, width, height, text? }

import * as fs from 'fs';
import { readPsd } from 'ag-psd';

const psdPath = process.argv[2];
if (!psdPath) {
  console.error('Usage: node list_layers.mjs <psd>');
  process.exit(1);
}

const psd = readPsd(fs.readFileSync(psdPath), { useRawData: true });
const out = [];
psd.children.forEach((layer, index) => {
  if (layer.text) {
    const t = layer.text;
    const tx = t.transform ? t.transform[4] : layer.left;
    const ty = t.transform ? t.transform[5] : layer.top;
    const w = t.boxBounds ? t.boxBounds[2] : (layer.right - layer.left);
    const h = t.boxBounds ? t.boxBounds[3] : (layer.bottom - layer.top);
    out.push({
      index, name: layer.name, isText: true,
      left: Math.round(tx), top: Math.round(ty),
      width: Math.round(w), height: Math.round(h),
      text: t.text,
    });
  } else {
    out.push({
      index, name: layer.name, isText: false,
      left: layer.left, top: layer.top,
      width: layer.right - layer.left, height: layer.bottom - layer.top,
    });
  }
});
console.log(JSON.stringify(out, null, 1));
