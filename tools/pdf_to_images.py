#!/usr/bin/env python3
"""Extract PDF pages as JPG images.

By default, each PDF in the target folder is rendered into its own image folder.
Use --single-folder to render every PDF into one shared folder named after
the source folder.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def check_dependencies() -> None:
    try:
        import fitz  # noqa: F401
    except ImportError:
        print("ERROR: PyMuPDF is not installed.")
        print("       Run: pip install pymupdf")
        sys.exit(1)


def clean_stem(path: Path) -> str:
    """Return base filename with all .pdf extensions stripped."""
    stem = path.name
    while True:
        p = Path(stem)
        if p.suffix.lower() == ".pdf":
            stem = p.stem
        else:
            return stem.rstrip(".")


def collect_pdfs(folder: Path) -> list[Path]:
    pdf_files = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() == ".pdf"
    )

    seen: dict[str, Path] = {}
    for pdf in pdf_files:
        stem = clean_stem(pdf)
        if stem not in seen or len(pdf.name) < len(seen[stem].name):
            seen[stem] = pdf

    return sorted(seen.values(), key=lambda path: path.name.lower())


def default_single_output_folder(folder: Path) -> Path:
    """Return the default shared output folder for --single-folder."""
    return folder / folder.name


def prepare_output_folder(folder: Path, overwrite: bool) -> bool:
    if folder.exists():
        if not overwrite:
            print(f"  SKIP: {folder.name} already exists. Use --overwrite to replace it.")
            return False
        shutil.rmtree(folder)

    folder.mkdir(parents=True, exist_ok=True)
    return True


def render_pdf(
    pdf_path: Path,
    output_folder: Path,
    dpi: int,
    overwrite: bool,
    include_pdf_name: bool,
) -> dict[str, object]:
    """Render one PDF to JPG files and return a small result summary."""
    import fitz

    result: dict[str, object] = {
        "name": pdf_path.name,
        "pages": 0,
        "images": 0,
        "output_folder": output_folder,
        "image_names": [],
        "status": "ok",
        "error": None,
    }

    try:
        if not include_pdf_name and not prepare_output_folder(output_folder, overwrite):
            result["status"] = "skipped"
            return result

        output_folder.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(str(pdf_path))
        page_count = len(doc)
        result["pages"] = page_count
        print(f"  Pages : {page_count}")
        print(f"  Output: {output_folder}")

        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        stem = clean_stem(pdf_path)
        image_names = []

        for page_index in range(page_count):
            page = doc[page_index]
            pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
            if include_pdf_name:
                image_name = f"{stem}_{page_index + 1:04d}.jpg"
            else:
                image_name = f"{page_index + 1:04d}.jpg"
            image_names.append(image_name)
            pix.save(str(output_folder / image_name))
            del pix

        doc.close()

        result["image_names"] = image_names
        print(f"  Rendered pages: {page_count}")
    except Exception as exc:
        result.update(status="error", error=str(exc))
        print(f"  ERROR: {exc}")

    return result


def verify_extracted_images(results: list[dict[str, object]]) -> int:
    """Check rendered image files on disk against each PDF page count."""
    errors = 0
    print("\nVerifying extracted image counts:")

    for result in results:
        if result["status"] != "ok":
            continue

        output_folder = result["output_folder"]
        image_names = result["image_names"]
        if not isinstance(output_folder, Path) or not isinstance(image_names, list):
            result.update(status="error", error="Internal verification data is invalid.")
            errors += 1
            continue

        extracted = sum(1 for name in image_names if (output_folder / name).is_file())
        result["images"] = extracted

        if extracted != result["pages"]:
            result.update(
                status="error",
                error=f"Expected {result['pages']} image(s), found {extracted}.",
            )
            errors += 1
            print(f"  ERROR: {result['name']} - {result['error']}")
        else:
            print(f"  OK: {result['name']} - {extracted}/{result['pages']} image(s)")

    return errors


def process_folder(
    folder_path: str,
    dpi: int,
    overwrite: bool,
    single_folder: bool,
    output: str | None,
) -> None:
    folder = Path(folder_path).expanduser().resolve()

    if not folder.exists() or not folder.is_dir():
        print(f"ERROR: Folder not found: {folder}")
        sys.exit(1)

    pdf_files = collect_pdfs(folder)
    if not pdf_files:
        print(f"No PDF files found in: {folder}")
        return

    if single_folder:
        output_folder = (
            Path(output).expanduser().resolve()
            if output
            else default_single_output_folder(folder)
        )
        if output_folder == folder:
            print("ERROR: --output cannot be the same folder that contains the PDFs.")
            sys.exit(1)
        if not prepare_output_folder(output_folder, overwrite):
            return
    else:
        output_folder = None

    total = len(pdf_files)
    print(f"Found {total} PDF file(s) in: {folder}")
    print(f"DPI: {dpi} | Mode: {'single folder' if single_folder else 'one folder per PDF'}")
    print("=" * 60)

    results = []
    for index, pdf in enumerate(pdf_files, start=1):
        print(f"\n[{index}/{total}] {pdf.name}")
        target_folder = output_folder if single_folder else folder / clean_stem(pdf)
        result = render_pdf(
            pdf,
            target_folder,
            dpi=dpi,
            overwrite=overwrite,
            include_pdf_name=single_folder,
        )
        results.append(result)

    verification_errors = verify_extracted_images(results)

    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")

    print("\n" + "=" * 60)
    print(
        f"DONE - {ok} extracted | {skipped} skipped | "
        f"{errors} errors ({verification_errors} verification)"
    )

    if errors:
        print("\nFailed files:")
        for result in results:
            if result["status"] == "error":
                print(f"  - {result['name']}: {result['error']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract PDF pages as JPG images.",
    )
    parser.add_argument("folder", nargs="?", help="Folder containing PDF files")
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Rendering resolution in DPI (default: 150)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing output folders",
    )
    parser.add_argument(
        "--single-folder",
        action="store_true",
        help="Extract all PDFs into one shared image folder",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output folder for --single-folder (default: <folder>/<folder_name>)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.dpi < 1:
        print("Error: --dpi must be greater than 0.")
        sys.exit(1)
    if args.output and not args.single_folder:
        print("Error: --output can only be used with --single-folder.")
        sys.exit(1)

    folder = args.folder
    if not folder:
        folder = input("Enter the path to the folder containing PDF files: ").strip()
        if not folder:
            print("No path provided. Exiting.")
            sys.exit(1)

    check_dependencies()
    process_folder(
        folder,
        dpi=args.dpi,
        overwrite=args.overwrite,
        single_folder=args.single_folder,
        output=args.output,
    )


if __name__ == "__main__":
    main()
