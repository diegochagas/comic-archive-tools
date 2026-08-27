# GIMP 3 batch script: export one named layer of an existing PSD to a flat PNG.
# Used to get pixels for detect_text.py when a PSD has no cached detection to
# reuse (add_cleaned_layer.py / add_text_boxes.py both call this via
# detect_or_reuse.py).
#
# Runs INSIDE GIMP's python-fu-eval interpreter. Invoke as:
#   flatpak run --env=EXPORT_JOB=/path/to/job.json org.gimp.GIMP -idf \
#     --batch-interpreter=python-fu-eval \
#     -b "exec(open('/path/to/gimp_export_layer.py').read())" --quit
#
# Job JSON format:
# {
#   "psd": "/abs/path/010.psd",
#   "layer_name": "Original",
#   "output": "/abs/path/010_original.png"
# }

import json
import os
import traceback

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp, Gio

JOB_PATH = os.environ["EXPORT_JOB"]
LOG_PATH = JOB_PATH + ".log"
_log = open(LOG_PATH, "w")


def log(msg):
    _log.write(msg + "\n")
    _log.flush()


def main():
    with open(JOB_PATH) as f:
        job = json.load(f)
    psd_path = job["psd"]
    layer_name = job["layer_name"]
    output_path = job["output"]

    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(psd_path))
    try:
        target = None
        for layer in image.get_layers():
            if layer.get_name() == layer_name:
                target = layer
                break
        if target is None:
            raise ValueError(f"no layer named {layer_name!r} in {psd_path}")

        new_image = Gimp.Image.new(target.get_width(), target.get_height(), image.get_base_type())
        copy = Gimp.Layer.new_from_drawable(target, new_image)
        new_image.insert_layer(copy, None, 0)
        new_image.flatten()
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, new_image,
                       Gio.File.new_for_path(output_path), None)
        new_image.delete()
        log(f"OK {psd_path} [{layer_name}] -> {output_path}")
    finally:
        image.delete()


try:
    main()
    log("DONE")
except Exception:
    log("FATAL\n" + traceback.format_exc())
_log.close()
