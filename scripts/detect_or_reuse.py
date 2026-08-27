"""Shared helper: get a detect_text.py-style detection JSON + cleaned PNG for
a PSD's source layer, reusing a previous run if one is already on disk instead
of always re-running the ONNX model. Used by add_cleaned_layer.py and
add_text_boxes.py.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from _gimp import run_gimp_batch, check_log_ok, venv_python

REPO_ROOT = Path(__file__).parent.parent


def ensure_detection(psd_path: Path, layer_name: str = "Original",
                      detect_dir: Path | None = None) -> dict:
    """Return {"detect_json": Path, "cleaned_png": Path, "reused": bool}.

    If `<detect_dir>/<stem>_detect.json` and its sibling `_cleaned.png`
    already exist, reuse them as-is. Otherwise export `layer_name` from the
    PSD to a PNG via GIMP and run detect_text.py on it to produce both.
    """
    stem = psd_path.stem
    if detect_dir is None:
        detect_dir = psd_path.parent / "detect"
    detect_dir = Path(detect_dir)
    detect_json = detect_dir / f"{stem}_detect.json"
    cleaned_png = detect_dir / f"{stem}_cleaned.png"

    if detect_json.exists() and cleaned_png.exists():
        return {"detect_json": detect_json, "cleaned_png": cleaned_png, "reused": True}

    with tempfile.TemporaryDirectory() as tmp:
        export_path = Path(tmp) / f"{stem}.png"
        log_path = run_gimp_batch("gimp_export_layer.py", "EXPORT_JOB", {
            "psd": str(psd_path.resolve()),
            "layer_name": layer_name,
            "output": str(export_path),
        })
        check_log_ok(log_path)
        if not export_path.exists():
            raise RuntimeError(f"layer export produced no file for {psd_path}")

        detect_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [venv_python(REPO_ROOT), str(REPO_ROOT / "scripts" / "detect_text.py"),
             str(psd_path.parent), str(export_path)],
            check=True,
        )
        # detect_text.py writes into <out_dir>/detect/, named after export_path's
        # stem (which we set to match the PSD's stem) -- but out_dir here is
        # psd_path.parent, so redirect if detect_dir was overridden explicitly.
        default_detect_dir = psd_path.parent / "detect"
        if default_detect_dir != detect_dir:
            detect_dir.mkdir(parents=True, exist_ok=True)
            for f in default_detect_dir.glob(f"{stem}_*"):
                f.replace(detect_dir / f.name)

    if not (detect_json.exists() and cleaned_png.exists()):
        raise RuntimeError(f"detect_text.py did not produce expected output for {psd_path}")
    return {"detect_json": detect_json, "cleaned_png": cleaned_png, "reused": False}


def main():
    if len(sys.argv) < 2:
        print("Usage: python detect_or_reuse.py <psd> [layer_name] [detect_dir]", file=sys.stderr)
        sys.exit(1)
    psd_path = Path(sys.argv[1])
    layer_name = sys.argv[2] if len(sys.argv) > 2 else "Original"
    detect_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    result = ensure_detection(psd_path, layer_name, detect_dir)
    print(result)


if __name__ == "__main__":
    main()
