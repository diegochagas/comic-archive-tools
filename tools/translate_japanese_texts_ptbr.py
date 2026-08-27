#!/usr/bin/env python3
"""Translate a Japanese transcription TXT into Brazilian Portuguese blocks."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable


def check_dependencies() -> None:
    try:
        import deep_translator  # noqa: F401
    except ImportError:
        print("ERROR: deep-translator is not installed.")
        print("       Run: pip install deep-translator")
        sys.exit(1)


def parse_blocks(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8-sig")
    pattern = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        print("ERROR: No image blocks were found. Expected blocks that start with '## image-name.jpg'.")
        sys.exit(1)

    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body.endswith("---"):
            body = body[:-3].strip()
        body = re.sub(r"\n---\s*$", "", body).strip()
        blocks.append((name, body))
    return blocks


def chunk_text(text: str, max_chars: int = 4500) -> Iterable[str]:
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 > max_chars and current:
            yield current.strip()
            current = ""
        if len(paragraph) > max_chars:
            for i in range(0, len(paragraph), max_chars):
                yield paragraph[i : i + max_chars]
        else:
            current += ("\n\n" if current else "") + paragraph
    if current.strip():
        yield current.strip()


def translate_text(text: str, source: str, target: str) -> str:
    from deep_translator import GoogleTranslator

    if not text or text.startswith("[OCR error") or text == "[No text detected]":
        return text

    translator = GoogleTranslator(source=source, target=target)
    translated_parts = []
    for part in chunk_text(text):
        translated_parts.append(translator.translate(part))
    return "\n\n".join(translated_parts).strip()


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


def translate_file(input_file: Path, output_file: Path, source: str, target: str, no_cache: bool) -> None:
    blocks = parse_blocks(input_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = output_file.parent / f".{output_file.stem}_translation_cache"
    if not no_cache:
        cache_dir.mkdir(parents=True, exist_ok=True)

    translated_blocks: list[tuple[str, str]] = []
    for index, (name, text) in enumerate(blocks, start=1):
        print(f"[{index}/{len(blocks)}] Translate: {name}", flush=True)
        cache_file = cache_dir / f"{Path(name).name}.txt"
        if not no_cache and cache_file.exists():
            translated = cache_file.read_text(encoding="utf-8")
        else:
            try:
                translated = translate_text(text, source=source, target=target)
            except Exception as exc:
                translated = f"[Translation error for {name}: {exc}]"
            if not no_cache:
                cache_file.write_text(translated, encoding="utf-8")
        translated_blocks.append((name, translated))

    write_block_txt(output_file, translated_blocks)
    print(f"Done. Wrote: {output_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate a block-organized Japanese transcription TXT into Brazilian Portuguese.")
    parser.add_argument("input", type=Path, help="Japanese transcription TXT created by transcribe_japanese_images.py.")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output TXT file. Default: <input_stem>_pt_br.txt")
    parser.add_argument("--source", default="ja", help="Source language for Google Translate.")
    parser.add_argument("--target", default="pt", help="Target language for Google Translate. Use pt for Portuguese.")
    parser.add_argument("--no-cache", action="store_true", help="Do not reuse per-block translation cache files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_file = args.input.expanduser().resolve()
    if not input_file.exists() or not input_file.is_file():
        print(f"ERROR: Input file does not exist: {input_file}")
        return 1

    check_dependencies()
    output_file = (args.output or input_file.with_name(f"{input_file.stem}_pt_br.txt")).expanduser().resolve()
    translate_file(
        input_file=input_file,
        output_file=output_file,
        source=args.source,
        target=args.target,
        no_cache=args.no_cache,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
