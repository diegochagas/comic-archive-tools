#!/usr/bin/env python3
"""Add native Photoshop paragraph text boxes to each PSD in a folder, or a
single PSD file, one per detected text region. Detects text on the PSD's
source layer (default "Original"), reusing a previous detect_text.py run if
one is already on disk instead of always re-running the ONNX model. Rewrites
each PSD in place (existing raster layers pass through byte-exact).

Usage: python add_text_boxes.py <folder-or-psd> [--layer-name Original]
                                 [--detect-dir <dir>]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from detect_or_reuse import ensure_detection

SCRIPTS_DIR = Path(__file__).parent


def iter_psds(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.glob("*.psd"))
    raise FileNotFoundError(f"Not a file or directory: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Folder of PSDs, or a single PSD file.")
    parser.add_argument("--layer-name", default="Original",
                         help="Source layer to detect text on. Default: Original")
    parser.add_argument("--detect-dir", type=Path, default=None,
                         help="Reuse/write detect_text.py output here. Default: <psd's folder>/detect")
    args = parser.parse_args()

    input_path = args.input.resolve()
    psds = iter_psds(input_path)
    if not psds:
        print(f"No PSDs found in {input_path}", file=sys.stderr)
        return 1

    failed = []
    for psd_path in psds:
        try:
            detection = ensure_detection(psd_path, args.layer_name, args.detect_dir)
            subprocess.run(
                ["node", str(SCRIPTS_DIR / "add_text_layers.mjs"),
                 "--psd", str(psd_path), "--detect-json", str(detection["detect_json"])],
                check=True,
            )
        except Exception as e:
            print(f"SKIP {psd_path.name}: {e}", file=sys.stderr)
            failed.append(psd_path)

    if failed:
        print(f"Skipped {len(failed)} PSD(s): " + ", ".join(p.name for p in failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
