#!/usr/bin/env python3
"""Transcribe Japanese text from images into a block-organized TXT file."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = None

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}


def natural_sort_key(path: Path) -> list[object]:
    parts = re.split(r"(\d+)", path.stem)
    key: list[object] = []
    for part in parts:
        key.append(int(part) if part.isdigit() else part.casefold())
    key.append(path.suffix.casefold())
    return key


def find_images(folder: Path) -> list[Path]:
    return sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS),
        key=natural_sort_key,
    )


def resolve_tesseract(explicit: str | None) -> str:
    candidate = explicit or shutil.which("tesseract")
    if candidate and Path(candidate).exists():
        return candidate

    print("ERROR: Tesseract OCR was not found.")
    print("       Install it with: sudo apt install tesseract-ocr")
    print("       Or pass --tesseract with the full path to the tesseract binary.")
    sys.exit(1)


def default_tessdata_dir() -> Path | None:
    local = Path(__file__).resolve().parent / "tessdata"
    if local.exists():
        return local
    return None


def available_tesseract_languages(tesseract: str, tessdata_dir: Path | None) -> set[str]:
    command = [tesseract]
    if tessdata_dir:
        command.extend(["--tessdata-dir", str(tessdata_dir)])
    command.append("--list-langs")

    proc = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = proc.stdout.decode("utf-8", errors="replace")
    langs = set()
    for line in output.splitlines():
        line = line.strip()
        if line and not line.lower().startswith("list of available languages"):
            langs.add(line)
    return langs


def choose_ocr_language(tesseract: str, preferred: str, tessdata_dir: Path | None) -> str:
    available = available_tesseract_languages(tesseract, tessdata_dir)
    requested = [lang.strip() for lang in preferred.split("+") if lang.strip()]
    found = [lang for lang in requested if lang in available]
    if found:
        return "+".join(found)
    if "jpn" in available:
        return "jpn"

    print("ERROR: Japanese Tesseract language data was not found.")
    print("       Expected jpn.traineddata and preferably jpn_vert.traineddata.")
    print("       Run setup.sh to download them into tools/tessdata, or pass --tessdata-dir.")
    sys.exit(1)


def prepare_image_for_ocr(image: Path, work_dir: Path, max_side: int) -> Path:
    with Image.open(image) as original:
        original = ImageOps.exif_transpose(original)
        width, height = original.size
        largest_side = max(width, height)
        if largest_side <= max_side:
            return image

        scale = max_side / largest_side
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        resized = original.resize(new_size, Image.Resampling.LANCZOS)
        work_dir.mkdir(parents=True, exist_ok=True)
        prepared = work_dir / f"{image.stem}_ocr.png"
        resized.save(prepared)
        return prepared


def clean_ocr_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def run_tesseract(
    image: Path,
    tesseract: str,
    lang: str,
    psm: int,
    tessdata_dir: Path | None,
    work_dir: Path,
    max_side: int,
    timeout_seconds: int,
) -> str:
    ocr_image = prepare_image_for_ocr(image, work_dir=work_dir, max_side=max_side)
    command = [tesseract, str(ocr_image), "stdout", "-l", lang, "--psm", str(psm)]
    if tessdata_dir:
        command.extend(["--tessdata-dir", str(tessdata_dir)])

    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"OCR timed out after {timeout_seconds}s") from exc

    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(stderr.strip() or "Tesseract failed without an error message.")
    return clean_ocr_text(stdout)


def write_block_txt(path: Path, blocks: list[tuple[str, str]]) -> None:
    lines: list[str] = []
    for name, text in blocks:
        lines.append(f"## {name}")
        lines.append("")
        lines.append(text or "[No text detected]")
        lines.append("")
        lines.append("---")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8-sig")


def transcribe_folder(
    folder: Path,
    output: Path,
    tesseract: str,
    tessdata_dir: Path | None,
    lang: str,
    psm: int,
    max_side: int,
    timeout_seconds: int,
    no_cache: bool,
) -> None:
    images = find_images(folder)
    if not images:
        print(f"ERROR: No supported image files found in: {folder}")
        sys.exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = output.parent / f".{output.stem}_ocr_cache"
    work_dir = output.parent / f".{output.stem}_ocr_work"
    if not no_cache:
        cache_dir.mkdir(parents=True, exist_ok=True)

    blocks: list[tuple[str, str]] = []
    for index, image in enumerate(images, start=1):
        print(f"[{index}/{len(images)}] OCR: {image.name}", flush=True)
        cache_file = cache_dir / f"{image.name}.txt"
        if not no_cache and cache_file.exists():
            text = cache_file.read_text(encoding="utf-8")
        else:
            try:
                text = run_tesseract(
                    image=image,
                    tesseract=tesseract,
                    lang=lang,
                    psm=psm,
                    tessdata_dir=tessdata_dir,
                    work_dir=work_dir,
                    max_side=max_side,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                text = f"[OCR error for {image.name}: {exc}]"
            if not no_cache:
                cache_file.write_text(text, encoding="utf-8")
        blocks.append((image.name, text))

    write_block_txt(output, blocks)
    print(f"Done. Wrote: {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe Japanese text from image files into a block-organized TXT file.")
    parser.add_argument("folder", type=Path, help="Folder containing image files.")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output TXT file. Default: <folder>/japanese_transcription.txt")
    parser.add_argument("--tesseract", default=None, help="Full path to the tesseract binary if it is not on PATH.")
    parser.add_argument("--tessdata-dir", type=Path, default=None, help="Folder containing Tesseract traineddata files. Default: ./tessdata next to this script.")
    parser.add_argument("--lang", default="jpn_vert+jpn", help="Tesseract language(s). Use jpn_vert for vertical Japanese novels.")
    parser.add_argument("--psm", type=int, default=5, help="Tesseract page segmentation mode.")
    parser.add_argument("--max-side", type=int, default=4000, help="Downscale images larger than this many pixels on the longest side before OCR.")
    parser.add_argument("--ocr-timeout", type=int, default=240, help="Maximum seconds to spend OCRing one image.")
    parser.add_argument("--no-cache", action="store_true", help="Do not reuse per-image OCR cache files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    folder = args.folder.expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        print(f"ERROR: Input folder does not exist or is not a directory: {folder}")
        return 1

    output = (args.output or folder / "japanese_transcription.txt").expanduser().resolve()
    tesseract = resolve_tesseract(args.tesseract)
    tessdata_dir = args.tessdata_dir.expanduser().resolve() if args.tessdata_dir else default_tessdata_dir()
    lang = choose_ocr_language(tesseract, args.lang, tessdata_dir)

    print(f"Using Tesseract: {tesseract}")
    if tessdata_dir:
        print(f"Using tessdata dir: {tessdata_dir}")
    print(f"Using OCR language: {lang}")

    transcribe_folder(
        folder=folder,
        output=output,
        tesseract=tesseract,
        tessdata_dir=tessdata_dir,
        lang=lang,
        psm=args.psm,
        max_side=args.max_side,
        timeout_seconds=args.ocr_timeout,
        no_cache=args.no_cache,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
