#!/usr/bin/env node
// Headless-GIMP-free replacement for gimp_clean.py's "standard mode": builds
// the same 2-layer PSD (layer "Original" = untouched source, layer
// "Cleaned" = detect_text.py's fully-erased page) directly via ag-psd,
// for environments where flatpak GIMP 3 isn't installed. Output is the same
// layer convention gimp_clean.py produces, so add_text_layers.mjs,
// list_layers.mjs, export_layer.mjs, set_text_layers.mjs all work unchanged.
//
// Usage (batch mode, mirrors the fixed pipeline's job shape):
//   node build_psd_no_gimp.mjs <output_dir> <stem>:<source_jpg> [<stem>:<source_jpg> ...]
// For each stem, expects <output_dir>/detect/<stem>_cleaned.png (from
// detect_text.py). Writes <output_dir>/<stem>.psd.

import * as fs from 'fs';
import * as path from 'path';
import { writePsdBuffer } from 'ag-psd';
import { loadImage, createCanvas } from 'canvas';

async function decodeToImageData(imgPath) {
  const img = await loadImage(imgPath);
  const canvas = createCanvas(img.width, img.height);
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0);
  const { data } = ctx.getImageData(0, 0, img.width, img.height);
  return { data: new Uint8Array(data.buffer, data.byteOffset, data.byteLength), width: img.width, height: img.height };
}

async function buildOne(outputDir, stem, sourcePath) {
  const cleanedPath = path.join(outputDir, 'detect', `${stem}_cleaned.png`);
  if (!fs.existsSync(cleanedPath)) {
    console.log(`SKIP ${stem}: no cleaned PNG at ${cleanedPath}`);
    return;
  }
  if (!fs.existsSync(sourcePath)) {
    console.log(`SKIP ${stem}: no source at ${sourcePath}`);
    return;
  }
  const original = await decodeToImageData(sourcePath);
  const cleaned = await decodeToImageData(cleanedPath);
  if (original.width !== cleaned.width || original.height !== cleaned.height) {
    console.log(`SKIP ${stem}: size mismatch original ${original.width}x${original.height} vs cleaned ${cleaned.width}x${cleaned.height}`);
    return;
  }
  const psd = {
    width: original.width,
    height: original.height,
    children: [
      { name: 'Original', top: 0, left: 0, bottom: original.height, right: original.width, imageData: original },
      { name: 'Cleaned', top: 0, left: 0, bottom: cleaned.height, right: cleaned.width, imageData: cleaned },
    ],
  };
  const outPath = path.join(outputDir, `${stem}.psd`);
  fs.writeFileSync(outPath, writePsdBuffer(psd, { generateThumbnail: false }));
  console.log(`${stem}: -> ${outPath}`);
}

async function main() {
  const [outputDir, ...pairs] = process.argv.slice(2);
  if (!outputDir || !pairs.length) {
    console.error('Usage: node build_psd_no_gimp.mjs <output_dir> <stem>:<source_jpg> [<stem>:<source_jpg> ...]');
    process.exit(1);
  }
  for (const pair of pairs) {
    const sep = pair.indexOf(':');
    const stem = pair.slice(0, sep);
    const sourcePath = pair.slice(sep + 1);
    try {
      await buildOne(outputDir, stem, sourcePath);
    } catch (e) {
      console.log(`SKIP ${stem}: ${e.message}`);
    }
  }
}

main();
