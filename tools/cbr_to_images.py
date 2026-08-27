from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ARCHIVE_SUFFIXES = {".cbr", ".cbz", ".zip"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"}
RAR_SIGNATURES = (b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00")
EXTRACTOR_CANDIDATES = (
    ("unrar", ("x", "-y")),
    ("rar", ("x", "-y")),
    (r"C:\Program Files\WinRAR\UnRAR.exe", ("x", "-y")),
    (r"C:\Program Files\WinRAR\WinRAR.exe", ("x", "-ibck", "-y")),
    ("7z", ("x", "-y")),
    (r"C:\Program Files\7-Zip\7z.exe", ("x", "-y")),
)


def unique_path(path: Path) -> Path:
    """Return a non-existing path by appending a numeric suffix when needed."""
    if not path.exists():
        return path

    for counter in range(1, 10_000):
        candidate = path.with_name(f"{path.name} ({counter})")
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Could not find an available folder name for {path}")


def is_rar_archive(archive: Path) -> bool:
    with archive.open("rb") as file:
        header = file.read(8)
    return header.startswith(RAR_SIGNATURES)


def find_external_extractor() -> tuple[str, tuple[str, ...]]:
    for executable, args in EXTRACTOR_CANDIDATES:
        if shutil.which(executable) or Path(executable).exists():
            return executable, args

    raise RuntimeError(
        "Could not find an extractor for RAR-based .cbr files. "
        "Install 7-Zip or WinRAR, or add one of them to PATH."
    )


def extract_with_external_tool(archive: Path, output_dir: Path) -> None:
    executable, args = find_external_extractor()

    if Path(executable).name.lower().startswith("7z"):
        command = [executable, *args, f"-o{output_dir}", str(archive)]
    else:
        command = [executable, *args, str(archive), str(output_dir) + "\\"]

    subprocess.run(command, check=True)


def extract_first_image(archive: Path, dry_run: bool = False) -> None:
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zip_archive:
            image_names = sorted(
                name for name in zip_archive.namelist()
                if Path(name).suffix.lower() in IMAGE_EXTENSIONS and not name.endswith("/")
            )
            if not image_names:
                print(f"Skip (no images): {archive.name}")
                return
            first_name = image_names[0]
            output_path = unique_path(archive.parent / (archive.stem + Path(first_name).suffix))
            print(f"Cover: {archive.name} -> {output_path.name}")
            if not dry_run:
                output_path.write_bytes(zip_archive.read(first_name))
    elif is_rar_archive(archive):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            if not dry_run:
                extract_with_external_tool(archive, tmp_path)
            images = sorted(
                p for p in tmp_path.rglob("*")
                if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
            )
            if not images:
                print(f"Skip (no images): {archive.name}")
                return
            first_image = images[0]
            output_path = unique_path(archive.parent / (archive.stem + first_image.suffix))
            print(f"Cover: {archive.name} -> {output_path.name}")
            if not dry_run:
                shutil.copy2(first_image, output_path)
    else:
        raise ValueError(f"Unsupported archive format: {archive}")


def extract_archive(archive: Path, dry_run: bool = False) -> None:
    output_dir = unique_path(archive.with_suffix(""))

    print(f"Extract: {archive.name} -> {output_dir.name}\\")
    if dry_run:
        return

    output_dir.mkdir(parents=True, exist_ok=False)
    try:
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as zip_archive:
                zip_archive.extractall(output_dir)
        elif is_rar_archive(archive):
            extract_with_external_tool(archive, output_dir)
        else:
            raise ValueError(f"Unsupported archive format: {archive}")
    except Exception:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise


def process_folder(target: Path, dry_run: bool = False, first_only: bool = False) -> None:
    if not target.is_dir():
        raise NotADirectoryError(f"Target folder does not exist: {target}")

    archives = sorted(
        path
        for path in target.iterdir()
        if path.is_file() and path.suffix.lower() in ARCHIVE_SUFFIXES
    )

    if not archives:
        print("No .cbr, .cbz, or .zip files found.")
        return

    action = extract_first_image if first_only else extract_archive
    for archive in archives:
        action(archive, dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract .cbr/.cbz comic archives into folders with the same "
            "base name."
        )
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Folder containing .cbr/.cbz archives.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without extracting files.",
    )
    parser.add_argument(
        "--first-only",
        action="store_true",
        help="Extract only the first image from each archive into the target folder.",
    )
    args = parser.parse_args()

    process_folder(args.target, args.dry_run, args.first_only)


if __name__ == "__main__":
    main()
