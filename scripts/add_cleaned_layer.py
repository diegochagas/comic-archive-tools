#!/usr/bin/env python3
"""Add an auto-cleaned text layer to a COPY of each PSD in a folder, or a
single PSD file. Detects text on the PSD's source layer (default "Original"),
reusing a previous detect_text.py run if one is already on disk instead of
always re-running the ONNX model, then erases it into a new "Cleaned" layer
appended on top. The input PSD is never modified.

Usage: python add_cleaned_layer.py <folder-or-psd> [--output <dir>]
                                    [--layer-name Original] [--detect-dir <dir>]
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
    parser.add_argument("--output", type=Path, default=None,
                         help="Output directory for the copies. Default: <input>/cleaned")
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

    output_dir = args.output.resolve() if args.output else (
        input_path / "cleaned" if input_path.is_dir() else input_path.parent / "cleaned"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    failed = []
    for psd_path in psds:
        try:
            detection = ensure_detection(psd_path, args.layer_name, args.detect_dir)
            out_path = output_dir / psd_path.name
            subprocess.run(
                ["node", str(SCRIPTS_DIR / "add_cleaned_layer.mjs"),
                 str(psd_path), str(detection["cleaned_png"]), str(out_path)],
                check=True,
            )
            reused = " (reused detection)" if detection["reused"] else ""
            print(f"{psd_path.name}: -> {out_path}{reused}")
        except Exception as e:
            print(f"SKIP {psd_path.name}: {e}", file=sys.stderr)
            failed.append(psd_path)

    if failed:
        print(f"Skipped {len(failed)} PSD(s): " + ", ".join(p.name for p in failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
