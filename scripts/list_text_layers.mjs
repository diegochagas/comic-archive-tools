#!/usr/bin/env node
// Lists every native Photoshop text layer in a PSD: index, name, position,
// size and current text content. Self-contained (reads straight from the
// PSD, no dependency on any detect.json from the build step) so the
// manga-translator-ptbr skill can work on any PSD folder on its own.
//
// Usage: node list_text_layers.mjs <psd>
// Output (stdout): JSON array of
//   { index, name, left, top, width, height, text }

import * as fs from 'fs';
import { readPsd } from 'ag-psd';

const psdPath = process.argv[2];
if (!psdPath) {
  console.error('Usage: node list_text_layers.mjs <psd>');
  process.exit(1);
}

const psd = readPsd(fs.readFileSync(psdPath), { skipLayerImageData: true, skipCompositeImageData: true, skipThumbnail: true });
const out = [];
psd.children.forEach((layer, index) => {
  if (layer.text) {
    const t = layer.text;
    // box is [0,0,bw,bh] in text space; transform [a b c d tx ty] maps it to
    // the page (rotated boxes from build_translated_psd.mjs included), so
    // report the page-space bounding rect of the transformed box
    const [a, b, c, d, tx, ty] = t.transform || [1, 0, 0, 1, layer.left, layer.top];
    const bb = t.boxBounds || [0, 0, layer.right - layer.left, layer.bottom - layer.top];
    const pts = [[bb[0], bb[1]], [bb[2], bb[1]], [bb[0], bb[3]], [bb[2], bb[3]]]
      .map(([px, py]) => [a * px + c * py + tx, b * px + d * py + ty]);
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const left = Math.min(...xs), top = Math.min(...ys);
    const w = Math.max(...xs) - left, h = Math.max(...ys) - top;
    const rotate = Math.round((Math.atan2(b, a) * 180) / Math.PI);
    out.push({
      index,
      name: layer.name,
      left: Math.round(left),
      top: Math.round(top),
      width: Math.round(w),
      height: Math.round(h),
      rotate,
      fontSize: t.style && t.style.fontSize,
      color: t.style && t.style.fillColor,
      font: t.style && t.style.font && t.style.font.name,
      align: t.paragraphStyle && t.paragraphStyle.justification,
      text: t.text,
    });
  }
});
console.log(JSON.stringify(out, null, 1));
