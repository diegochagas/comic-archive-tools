from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from PIL import Image, ImageCms, UnidentifiedImageError


def iter_psd_files(source: Path) -> list[Path]:
    return sorted(
        [p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in {".psd", ".psb"}],
        key=lambda p: str(p).lower(),
    )


def flatten_for_jpeg(image: Image.Image, background: str) -> Image.Image:
    # For PSD files, checking is_animated can force Pillow to parse layers.
    # Some valid PSDs have layer data Pillow cannot parse, while the flattened
    # composite still loads correctly. JPEG export only needs the composite.
    image.load()

    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        matte = Image.new("RGBA", rgba.size, background)
        matte.alpha_composite(rgba)
        return matte.convert("RGB")

    if image.mode == "CMYK":
        return image.copy()

    if image.mode != "RGB":
        return image.convert("RGB")

    return image.copy()


def render_all_layers_visible(psd_path: Path) -> Image.Image:
    # Pillow only reads the flattened composite Photoshop bakes into the file,
    # so forcing hidden layers on requires psd-tools to actually recomposite.
    from psd_tools import PSDImage

    psd = PSDImage.open(psd_path)
    return psd.composite(layer_filter=lambda _layer: True)


def normalize_icc_for_jpeg(image: Image.Image, info: dict) -> bytes | None:
    icc = info.get("icc_profile")
    if not icc:
        return None

    if image.mode == "CMYK":
        return icc

    try:
        source = ImageCms.ImageCmsProfile(bytes(icc))
        target = ImageCms.createProfile("sRGB")
        converted = ImageCms.profileToProfile(image, source, target, outputMode="RGB")
        image.paste(converted)
        return ImageCms.ImageCmsProfile(target).tobytes()
    except Exception:
        return icc


def convert_one(
    psd_path: Path,
    source_root: Path,
    output_root: Path,
    *,
    background: str,
    overwrite: bool,
    show_all_layers: bool,
) -> tuple[bool, str]:
    relative = psd_path.relative_to(source_root)
    jpg_path = output_root / relative.with_suffix(".jpg")

    if jpg_path.exists() and not overwrite and jpg_path.stat().st_mtime >= psd_path.stat().st_mtime:
        return False, f"skip up-to-date: {jpg_path}"

    jpg_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if show_all_layers:
            # psd-tools already returns sRGB-corrected pixels, so the original
            # PSD's icc_profile is dropped rather than re-applied below.
            image = flatten_for_jpeg(render_all_layers_visible(psd_path), background)
            with Image.open(psd_path) as opened:
                original_info = {"dpi": opened.info["dpi"]} if "dpi" in opened.info else {}
        else:
            with Image.open(psd_path) as opened:
                original_info = dict(opened.info)
                image = flatten_for_jpeg(opened, background)
    except (UnidentifiedImageError, OSError, struct.error, ValueError) as exc:
        return False, f"cannot read PSD composite: {psd_path} ({exc})"

    save_kwargs = {
        "format": "JPEG",
        "quality": 100,
        "subsampling": 0,
        "optimize": True,
        "progressive": False,
    }

    dpi = original_info.get("dpi")
    if dpi:
        save_kwargs["dpi"] = dpi

    icc_profile = normalize_icc_for_jpeg(image, original_info)
    if icc_profile:
        save_kwargs["icc_profile"] = icc_profile

    image.save(jpg_path, **save_kwargs)
    return True, f"wrote: {jpg_path} ({image.width}x{image.height}, {image.mode})"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create high-quality JPG files from PSD/PSB files without changing pixel dimensions."
    )
    parser.add_argument(
        "source",
        type=Path,
        help="PSD folder to scan recursively.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output folder. Default: a sibling folder named '<source folder> JPG'.",
    )
    parser.add_argument(
        "--background",
        default="white",
        help="Matte color for transparent PSDs before saving as JPG. Default: white",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite JPGs even when they are newer than the source PSD.",
    )
    parser.add_argument(
        "--show-all-layers",
        action="store_true",
        help=(
            "Force every layer (including hidden ones and hidden groups) visible "
            "before flattening, instead of using Photoshop's saved composite. "
            "Requires the psd-tools package."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Convert only the first N files, useful for testing.",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    output = (
        args.output
        if args.output is not None
        else source.with_name(source.name + " JPG")
    ).resolve()

    if not source.exists():
        print(f"Source folder does not exist: {source}", file=sys.stderr)
        return 2

    if args.show_all_layers:
        try:
            import psd_tools  # noqa: F401
        except ImportError:
            print(
                "--show-all-layers requires the psd-tools package. Install it with: "
                "pip install psd-tools",
                file=sys.stderr,
            )
            return 2

    psd_files = iter_psd_files(source)
    if args.limit > 0:
        psd_files = psd_files[: args.limit]

    if not psd_files:
        print(f"No PSD/PSB files found under: {source}")
        return 0

    print(f"Source: {source}")
    print(f"Output: {output}")
    print(f"Files: {len(psd_files)}")

    converted = 0
    failed = 0
    skipped = 0

    for index, psd_path in enumerate(psd_files, start=1):
        ok, message = convert_one(
            psd_path,
            source,
            output,
            background=args.background,
            overwrite=args.overwrite,
            show_all_layers=args.show_all_layers,
        )
        print(f"[{index}/{len(psd_files)}] {message}")

        if ok:
            converted += 1
        elif message.startswith("skip"):
            skipped += 1
        else:
            failed += 1

    print(f"Done. Converted: {converted}. Skipped: {skipped}. Failed: {failed}.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
