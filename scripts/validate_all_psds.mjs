#!/usr/bin/env node
// Sanity-check every PSD in a folder: readable, has Original+Cleaned, and
// has as many "Text N" layers as its detect.json has text_blocks.
import * as fs from 'fs';
import * as path from 'path';
import { readPsd } from 'ag-psd';

const outDir = process.argv[2];
const stems = fs.readdirSync(outDir).filter(f => f.endsWith('.psd')).map(f => f.slice(0, -4)).sort();
let bad = [];
for (const stem of stems) {
  try {
    const psd = readPsd(fs.readFileSync(path.join(outDir, `${stem}.psd`)), { useRawData: true, skipCompositeImageData: true, skipThumbnail: true });
    const names = psd.children.map(l => l.name);
    const hasOriginal = names.includes('Original');
    const hasCleaned = names.includes('Cleaned');
    const textCount = names.filter(n => n.startsWith('Text ')).length;
    const loremCount = psd.children.filter(l => l.text && /Lorem ipsum/.test(l.text.text || '')).length;
    let expected = 0;
    const detectPath = path.join(outDir, 'detect', `${stem}_detect.json`);
    if (fs.existsSync(detectPath)) {
      expected = JSON.parse(fs.readFileSync(detectPath, 'utf8')).text_blocks.length;
    }
    if (!hasOriginal || !hasCleaned || textCount !== expected || loremCount > 0) {
      bad.push(`${stem}: original=${hasOriginal} cleaned=${hasCleaned} text=${textCount}/${expected} lorem=${loremCount}`);
    }
  } catch (e) {
    bad.push(`${stem}: READ ERROR ${e.message}`);
  }
}
console.log(`checked ${stems.length} PSDs`);
if (bad.length) {
  console.log(`${bad.length} PROBLEM(S):`);
  bad.forEach(b => console.log(' - ' + b));
} else {
  console.log('all good');
}
