from pathlib import Path
from PIL import Image
import argparse

parser = argparse.ArgumentParser(
    description="Stretch all PNG images in a folder."
)

parser.add_argument(
    "folder",
    help="Path to the folder containing PNG images"
)

parser.add_argument(
    "width",
    type=int,
    help="Target width in pixels"
)

parser.add_argument(
    "height",
    type=int,
    help="Target height in pixels"
)

args = parser.parse_args()

input_folder = Path(args.folder)

if not input_folder.exists():
    raise FileNotFoundError(f"Folder not found: {input_folder}")

output_folder = input_folder / "output"
output_folder.mkdir(exist_ok=True)

for image_path in input_folder.glob("*.png"):
    with Image.open(image_path) as img:
        resized = img.resize(
            (args.width, args.height),
            Image.Resampling.LANCZOS,
        )
        resized.save(output_folder / image_path.name)

print(
    f"Done! Resized PNG files saved to: {output_folder}"
)