import os
import sys
from pathlib import Path
from PIL import Image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}


def rotate_images(folder: str, degrees: int = 90) -> None:
    folder_path = Path(folder)
    if not folder_path.is_dir():
        print(f"Error: '{folder}' is not a valid directory.")
        sys.exit(1)

    images = [f for f in folder_path.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS]
    if not images:
        print("No images found in the folder.")
        return

    for image_path in images:
        with Image.open(image_path) as img:
            rotated = img.rotate(-degrees, expand=True)
            rotated.save(image_path)
        print(f"Rotated: {image_path.name}")

    print(f"\nDone. {len(images)} image(s) rotated {degrees} degrees.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python rotate_images.py <folder> [degrees]")
        print("  degrees defaults to 90 if not specified")
        sys.exit(1)

    folder_arg = sys.argv[1]
    degrees_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    rotate_images(folder_arg, degrees_arg)
