#!/usr/bin/env python3
"""Build a base 2-layer PSD (Original + Copy, no cleaning/detection) from a
folder of images or a single image.

Usage: python image_to_psd.py <folder-or-image> [--output <dir>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _gimp import run_gimp_batch, check_log_ok

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif", ".webp"}


def iter_sources(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
    raise FileNotFoundError(f"Not a file or directory: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Folder of images, or a single image file.")
    parser.add_argument("--output", type=Path, default=None,
                         help="Output directory for PSDs. Default: <input>/psd (folder) or the image's own folder (single file).")
    args = parser.parse_args()

    input_path = args.input.resolve()
    sources = iter_sources(input_path)
    if not sources:
        print(f"No images found in {input_path}", file=sys.stderr)
        return 1

    output_dir = args.output.resolve() if args.output else (
        input_path / "psd" if input_path.is_dir() else input_path.parent / "psd"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    job = {
        "output_dir": str(output_dir),
        "pages": [{"source": str(p)} for p in sources],
    }
    log_path = run_gimp_batch("gimp_base_psd.py", "CLEAN_JOB", job)
    check_log_ok(log_path)
    print(f"{len(sources)} page(s) -> {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
