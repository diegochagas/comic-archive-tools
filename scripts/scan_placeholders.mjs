#!/usr/bin/env node
// Scans a folder of PSDs for any text layer still containing the
// "Lorem ipsum" placeholder. Prints one line per offending layer and a
// final count. Used to verify a translation pass actually replaced
// everything.
//
// Usage: node scan_placeholders.mjs <folder-with-psds>

import * as fs from 'fs';
import * as path from 'path';
import { readPsd } from 'ag-psd';

const dir = process.argv[2];
if (!dir) {
  console.error('Usage: node scan_placeholders.mjs <folder>');
  process.exit(1);
}

const files = fs.readdirSync(dir).filter((f) => f.toLowerCase().endsWith('.psd')).sort();
let totalText = 0;
let totalPlaceholder = 0;
let filesWithPlaceholder = 0;

for (const f of files) {
  const full = path.join(dir, f);
  let psd;
  try {
    psd = readPsd(fs.readFileSync(full), { useRawData: true });
  } catch (e) {
    console.log(`ERROR reading ${f}: ${e.message}`);
    continue;
  }
  let fileHasPlaceholder = false;
  psd.children.forEach((layer, idx) => {
    if (layer.text) {
      totalText++;
      if (layer.text.text && layer.text.text.includes('Lorem ipsum')) {
        totalPlaceholder++;
        fileHasPlaceholder = true;
        console.log(`PLACEHOLDER  ${f}  layer ${idx} "${layer.name}"`);
      }
    }
  });
  if (fileHasPlaceholder) filesWithPlaceholder++;
}

console.log(`\n${files.length} PSDs scanned, ${totalText} text layers total, ${totalPlaceholder} still show "Lorem ipsum" across ${filesWithPlaceholder} files.`);
