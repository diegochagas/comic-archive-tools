# GIMP 3 batch script: build a base 2-layer PSD from a raw image, no cleaning.
# Layer "Original" (bottom) = untouched source, layer "Copy" (top) = exact
# duplicate. Starting point for add_cleaned_layer.py / add_text_boxes.py.
#
# Runs INSIDE GIMP's python-fu-eval interpreter. Invoke as:
#   flatpak run --env=CLEAN_JOB=/path/to/job.json org.gimp.GIMP -idf \
#     --batch-interpreter=python-fu-eval \
#     -b "exec(open('/path/to/gimp_base_psd.py').read())" --quit
#
# Job JSON format:
# {
#   "output_dir": "/abs/path",       # PSDs written here, previews in <output_dir>/preview
#   "pages": [ { "source": "/abs/path/010.jpg" } ]
# }

import json
import os
import traceback

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp, Gio

JOB_PATH = os.environ["CLEAN_JOB"]
LOG_PATH = JOB_PATH + ".log"
_log = open(LOG_PATH, "w")


def log(msg):
    _log.write(msg + "\n")
    _log.flush()


def process_page(page, output_dir, preview_dir):
    src = page["source"]
    stem = os.path.splitext(os.path.basename(src))[0]
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(src))
    try:
        original = image.get_layers()[0]
        copy = original.copy()
        image.insert_layer(copy, None, 0)
        original.set_name("Original")
        copy.set_name("Copy")

        psd_path = os.path.join(output_dir, stem + ".psd")
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image,
                       Gio.File.new_for_path(psd_path), None)

        preview = image.duplicate()
        layers = preview.get_layers()
        for layer in layers[1:]:
            layer.set_visible(False)
        preview.flatten()
        preview_path = os.path.join(preview_dir, stem + "_base.jpg")
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, preview,
                       Gio.File.new_for_path(preview_path), None)
        preview.delete()
        log(f"OK {src} -> {psd_path}")
    finally:
        image.delete()


def main():
    with open(JOB_PATH) as f:
        job = json.load(f)
    output_dir = job["output_dir"]
    preview_dir = os.path.join(output_dir, "preview")
    os.makedirs(preview_dir, exist_ok=True)
    for page in job["pages"]:
        try:
            process_page(page, output_dir, preview_dir)
        except Exception:
            log(f"FAIL {page.get('source')}\n" + traceback.format_exc())


try:
    main()
    log("DONE")
except Exception:
    log("FATAL\n" + traceback.format_exc())
_log.close()
