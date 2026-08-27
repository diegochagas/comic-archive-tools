#!/usr/bin/env python3
"""Pack image folders into .cbr files.

By default, images are added as-is. Optional flags can convert images to JPEG
and/or resize tall images before they are written into the archive.
"""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"}


@dataclass(frozen=True)
class ImageOptions:
    convert_jpeg: bool
    max_height: int | None
    quality: int
    overwrite: bool

    @property
    def needs_pillow(self) -> bool:
        return self.convert_jpeg or self.max_height is not None


def get_images(folder: Path) -> list[Path]:
    return sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    )


def check_pillow() -> None:
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("ERROR: Pillow is required for --convert-jpeg or --max-height.")
        print("       Run: pip install pillow")
        sys.exit(1)


def processed_image(path: Path, options: ImageOptions) -> tuple[bytes, str]:
    """Return image bytes and archive filename after optional conversion/resizing."""
    if not options.needs_pillow:
        return path.read_bytes(), path.name

    from PIL import Image

    with Image.open(path) as img:
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        if options.max_height and img.height > options.max_height:
            ratio = options.max_height / img.height
            new_size = (int(img.width * ratio), options.max_height)
            img = img.resize(new_size, Image.LANCZOS)

        if img.mode != "RGB":
            img = img.convert("RGB")

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=options.quality, optimize=True)

    return buffer.getvalue(), f"{path.stem}.jpg"


def unique_archive_name(name: str, used_names: set[str]) -> str:
    if name not in used_names:
        used_names.add(name)
        return name

    path = Path(name)
    counter = 2
    while True:
        candidate = f"{path.stem}_{counter}{path.suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        counter += 1


def pack_cbr(image_folder: Path, output_dir: Path, options: ImageOptions) -> Path | None:
    images = get_images(image_folder)
    if not images:
        print(f"  SKIP: '{image_folder.name}' - no images found.")
        return None

    cbr_path = output_dir / f"{image_folder.name}.cbr"
    zip_path = output_dir / f"{image_folder.name}.zip"

    if cbr_path.exists() and not options.overwrite:
        print(f"  SKIP: {cbr_path.name} already exists. Use --overwrite to replace it.")
        return None

    if zip_path.exists():
        zip_path.unlink()

    used_names: set[str] = set()
    written_names: list[str] = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
        for img_path in images:
            data, archive_name = processed_image(img_path, options)
            archive_name = unique_archive_name(archive_name, used_names)
            zf.writestr(archive_name, data)
            written_names.append(archive_name)
            print(f"    + {archive_name}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        zipped_names = set(zf.namelist())

    missing = set(written_names) - zipped_names
    if missing:
        zip_path.unlink()
        print(
            f"  ERROR: '{image_folder.name}' - {len(missing)} file(s) missing from zip "
            f"({', '.join(sorted(missing))}). Aborted."
        )
        return None

    if cbr_path.exists():
        cbr_path.unlink()
    zip_path.rename(cbr_path)
    print(f"  Created: {cbr_path} ({len(images)} images)")
    return cbr_path


def process(root: Path, options: ImageOptions) -> None:
    if not root.is_dir():
        print(f"Error: '{root}' is not a directory.")
        sys.exit(1)

    if options.needs_pillow:
        check_pillow()

    subfolders = sorted(f for f in root.iterdir() if f.is_dir())
    root_images = get_images(root)

    if subfolders:
        print(f"Found {len(subfolders)} subfolder(s) in '{root.name}' - processing each:")
        for subfolder in subfolders:
            pack_cbr(subfolder, root, options)
    elif root_images:
        print(f"Found {len(root_images)} image(s) in '{root.name}' - creating CBR:")
        pack_cbr(root, root.parent, options)
    else:
        print("No images or subfolders with images found.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pack image folders into .cbr files.",
    )
    parser.add_argument("folder", help="Folder containing images or image subfolders")
    parser.add_argument(
        "--convert-jpeg",
        action="store_true",
        help="Convert images to JPEG before adding them to the CBR",
    )
    parser.add_argument(
        "--max-height",
        type=int,
        default=None,
        help="Resize images taller than this many pixels (outputs JPEG)",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=90,
        help="JPEG quality for converted/resized images (default: 90)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing CBR files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= args.quality <= 100:
        print("Error: --quality must be between 1 and 100.")
        sys.exit(1)
    if args.max_height is not None and args.max_height < 1:
        print("Error: --max-height must be greater than 0.")
        sys.exit(1)

    options = ImageOptions(
        convert_jpeg=args.convert_jpeg,
        max_height=args.max_height,
        quality=args.quality,
        overwrite=args.overwrite,
    )
    process(Path(args.folder), options)


if __name__ == "__main__":
    main()
