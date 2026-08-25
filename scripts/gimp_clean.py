# GIMP 3 batch script: clean text regions from manga/doujinshi pages and export
# layered PSDs (layer "Original" = untouched scan, layer "Cleaned" = text removed).
#
# Runs INSIDE GIMP's python-fu-eval interpreter. Invoke as:
#   flatpak run --env=CLEAN_JOB=/path/to/job.json org.gimp.GIMP -idf \
#     --batch-interpreter=python-fu-eval \
#     -b "exec(open('/path/to/gimp_clean.py').read())" --quit
#
# Job JSON format:
# {
#   "output_dir": "/abs/path",            # PSDs written here, previews in <output_dir>/preview
#   "pages": [
#     { "source": "/abs/path/010.jpg",
#       "regions": [
#         {"box": [x, y, w, h], "action": "fill_white"},
#         {"box": [x, y, w, h], "action": "heal_dark", "radius": 60}
#       ] }
#   ]
# }
#
# Actions (box is always [x, y, width, height] in source-image pixels):
#   fill_white  dark text on plain white bg: mask dark pixels in box, grow, fill white
#   fill_black  light text on plain black bg: mask light pixels in box, grow, fill black
#   fill_rect   blunt fill of the whole box with "color" (default "#ffffff")
#   heal        Resynthesizer heal of the whole box (text + bg fully resynthesized)
#   heal_dark   mask dark pixels in box, grow, heal only those (keeps surrounding art)
#   heal_light  mask light pixels in box, grow, heal only those
# Optional per-region keys: "radius" (heal sampling radius px, default 50),
#   "grow" (mask growth px, default 3), "threshold" (color-mask 0..1, default 0.35),
#   "color" (fill_rect color).

import json
import os
import traceback

import gi
gi.require_version('Gimp', '3.0')
gi.require_version('Gegl', '0.4')
from gi.repository import Gimp, Gegl, Gio

JOB_PATH = os.environ["CLEAN_JOB"]
LOG_PATH = JOB_PATH + ".log"
_log = open(LOG_PATH, "w")


def log(msg):
    _log.write(msg + "\n")
    _log.flush()


def color(spec):
    c = Gegl.Color.new(spec)
    return c


def mask_select(image, drawable, box, target_color, threshold, grow):
    """Select pixels inside box whose color is close to target_color, grown by a few px."""
    x, y, w, h = box
    image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, w, h)
    Gimp.context_set_sample_threshold(threshold)
    image.select_color(Gimp.ChannelOps.INTERSECT, drawable, color(target_color))
    if grow > 0:
        Gimp.Selection.grow(image, grow)
        # growing can leak outside the box; clamp back to it
        image.select_rectangle(Gimp.ChannelOps.INTERSECT, x - 1, y - 1, w + 2, h + 2)
    return not Gimp.Selection.is_empty(image)


def mask_region_select(image, mask_layer, box, grow):
    """Select detected text strokes (white pixels of mask_layer) inside box."""
    x, y, w, h = box
    image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, w, h)
    Gimp.context_set_sample_threshold(0.5)
    image.select_color(Gimp.ChannelOps.INTERSECT, mask_layer, color("#ffffff"))
    if grow > 0:
        Gimp.Selection.grow(image, grow)
        image.select_rectangle(Gimp.ChannelOps.INTERSECT, x - 1, y - 1, w + 2, h + 2)
    return not Gimp.Selection.is_empty(image)


def apply_mask_region(image, drawable, mask_layer, region):
    box = [int(v) for v in region["box"]]
    action = region["action"]
    grow = int(region.get("grow", 2))
    radius = int(region.get("radius", 50))
    if not mask_region_select(image, mask_layer, box, grow):
        return
    if action == "fill_white":
        drawable.edit_fill(Gimp.FillType.WHITE)
    elif action == "fill_black":
        Gimp.context_set_foreground(color("#000000"))
        drawable.edit_fill(Gimp.FillType.FOREGROUND)
    elif action == "heal":
        heal_selection(image, drawable, radius)
    else:
        raise ValueError(f"unknown mask_region action {action!r}")


def heal_selection(image, drawable, radius):
    pdb = Gimp.get_pdb()
    proc = pdb.lookup_procedure("plug-in-heal-selection")
    cfg = proc.create_config()
    cfg.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
    cfg.set_property("image", image)
    cfg.set_core_object_array("drawables", [drawable])
    cfg.set_property("adjustment", radius)  # sampling radius in px
    cfg.set_property("option", 0)           # sample from all around
    cfg.set_property("option-2", 0)         # random filling order
    result = proc.run(cfg)
    return result.index(0)


def apply_region(image, drawable, region):
    box = [int(v) for v in region["box"]]
    action = region["action"]
    grow = int(region.get("grow", 3))
    threshold = float(region.get("threshold", 0.35))
    radius = int(region.get("radius", 50))
    x, y, w, h = box

    if action == "fill_white":
        if mask_select(image, drawable, box, "#000000", threshold, grow):
            drawable.edit_fill(Gimp.FillType.WHITE)
    elif action == "fill_black":
        if mask_select(image, drawable, box, "#ffffff", threshold, grow):
            Gimp.context_set_foreground(color("#000000"))
            drawable.edit_fill(Gimp.FillType.FOREGROUND)
    elif action == "fill_rect":
        image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, w, h)
        Gimp.context_set_foreground(color(region.get("color", "#ffffff")))
        drawable.edit_fill(Gimp.FillType.FOREGROUND)
    elif action == "heal":
        image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, w, h)
        heal_selection(image, drawable, radius)
    elif action == "heal_dark":
        if mask_select(image, drawable, box, "#000000", threshold, grow):
            heal_selection(image, drawable, radius)
    elif action == "heal_light":
        if mask_select(image, drawable, box, "#ffffff", threshold, grow):
            heal_selection(image, drawable, radius)
    else:
        raise ValueError(f"unknown action {action!r}")


def process_page(page, output_dir, preview_dir):
    src = page["source"]
    stem = os.path.splitext(os.path.basename(src))[0]
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(src))
    try:
        cleaned = image.get_layers()[0]
        original = cleaned.copy()
        image.insert_layer(original, None, 1)
        original.set_name("Original")
        cleaned.set_name("Cleaned")

        mask_regions = page.get("mask_regions", [])
        if mask_regions:
            mask_layer = Gimp.file_load_layer(
                Gimp.RunMode.NONINTERACTIVE, image,
                Gio.File.new_for_path(page["text_mask"]))
            image.insert_layer(mask_layer, None, 0)
            mask_layer.set_visible(False)
            for region in mask_regions:
                apply_mask_region(image, cleaned, mask_layer, region)
            image.remove_layer(mask_layer)

        for region in page.get("regions", []):
            apply_region(image, cleaned, region)
        Gimp.Selection.none(image)

        psd_path = os.path.join(output_dir, stem + ".psd")
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image,
                       Gio.File.new_for_path(psd_path), None)

        preview = image.duplicate()
        layers = preview.get_layers()
        for layer in layers[1:]:
            layer.set_visible(False)
        preview.flatten()
        preview_path = os.path.join(preview_dir, stem + "_cleaned.jpg")
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
    Gimp.context_set_sample_merged(False)
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
