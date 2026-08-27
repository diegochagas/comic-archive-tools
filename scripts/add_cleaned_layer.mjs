#!/usr/bin/env node
// Appends a new raster layer (default name "Cleaned") to a COPY of an
// existing PSD, filled from an already-rendered cleaned PNG (from
// detect_text.py). Existing layers -- including any native Photoshop text
// layers add_text_layers.mjs may have already written -- pass through
// byte-exact via ag-psd's raw-channel read mode; only a new layer is
// appended, using a plain {data,width,height} imageData object (no native
// `canvas` package needed). Never touches the input file.
//
// Usage: node add_cleaned_layer.mjs <psd> <cleaned_png> <output_psd> [--layer-name <name>]

import * as fs from 'fs';
import * as path from 'path';
import { PNG } from 'pngjs';
import { readPsd, writePsdBuffer } from 'ag-psd';

function decodePng(pngPath) {
  const png = PNG.sync.read(fs.readFileSync(pngPath));
  return {
    data: new Uint8Array(png.data.buffer, png.data.byteOffset, png.data.byteLength),
    width: png.width,
    height: png.height,
  };
}

function main() {
  const args = process.argv.slice(2);
  const [psdPath, pngPath, outPath] = args;
  if (!psdPath || !pngPath || !outPath) {
    console.error('Usage: node add_cleaned_layer.mjs <psd> <cleaned_png> <output_psd> [--layer-name <name>]');
    process.exit(1);
  }
  let layerName = 'Cleaned';
  const idx = args.indexOf('--layer-name');
  if (idx !== -1 && args[idx + 1]) layerName = args[idx + 1];

  const psd = readPsd(fs.readFileSync(psdPath), { useRawData: true });
  const imageData = decodePng(pngPath);
  if (imageData.width !== psd.width || imageData.height !== psd.height) {
    throw new Error(`cleaned PNG size ${imageData.width}x${imageData.height} does not match PSD size ${psd.width}x${psd.height}`);
  }

  psd.children.push({
    name: layerName,
    top: 0,
    left: 0,
    bottom: psd.height,
    right: psd.width,
    imageData,
  });

  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, writePsdBuffer(psd, { generateThumbnail: false }));
  console.log(`${path.basename(outPath)}: ${psd.children.length} layer(s), added "${layerName}"`);
}

main();
