import sys, json
from PIL import Image, ImageDraw, ImageFont

img_path, layers_json_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
with open(layers_json_path) as f:
    layers = json.load(f)

im = Image.open(img_path).convert("RGB")
# upscale 2x for legibility
scale = 2
im = im.resize((im.width*scale, im.height*scale), Image.LANCZOS)
draw = ImageDraw.Draw(im, "RGBA")

try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
except Exception:
    font = ImageFont.load_default()

for L in layers:
    idx = L["index"]
    x0, y0 = L["left"]*scale, L["top"]*scale
    x1, y1 = x0 + L["width"]*scale, y0 + L["height"]*scale
    draw.rectangle([x0, y0, x1, y1], outline=(255,0,0,255), width=3)
    label = str(idx)
    tw = draw.textlength(label, font=font)
    draw.rectangle([x0, y0, x0+tw+8, y0+30], fill=(255,0,0,220))
    draw.text((x0+4, y0+2), label, fill=(255,255,255,255), font=font)

im.save(out_path)
print("saved", out_path, im.size)
