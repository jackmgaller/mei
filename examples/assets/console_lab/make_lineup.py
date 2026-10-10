import sys, os, re
from PIL import Image, ImageDraw, ImageFont
root = sys.argv[1]; out = sys.argv[2]
looks = sorted(d for d in os.listdir(root) if re.match(r"\d\d_", d))
names = {}
for line in open(os.path.join(root, "LOOKS.md")):
    m = re.match(r"\| (\d\d) \| ([^|]+) \|", line)
    if m: names.setdefault(m.group(1), m.group(2).strip())
CW, CH = 320, 240
def cell(path, col, row, crop=36):
    im = Image.open(path).convert("RGB")
    return im.crop((col*CW, row*CH + 22, (col+1)*CW, (row+1)*CH - 22))
tile_w, tile_h = 2*CW, CH - 44 + 30
cols = 4; rows = (len(looks) + cols - 1)//cols
sheet = Image.new("RGB", (cols*tile_w, rows*tile_h), (24, 25, 32))
d = ImageDraw.Draw(sheet)
try: font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Futura.ttc", 18)
except Exception: font = ImageFont.load_default()
for i, look in enumerate(looks):
    x, y = (i % cols)*tile_w, (i//cols)*tile_h
    p = os.path.join(root, look)
    try:
        sheet.paste(cell(os.path.join(p, "preview_console.png"), 0, 0), (x, y + 30))
        sheet.paste(cell(os.path.join(p, "preview_controller.png"), 1, 1), (x + CW, y + 30))
    except FileNotFoundError: pass
    d.text((x + 12, y + 6), f"{look[:2]}  {names.get(look[:2], look)}", fill=(235, 235, 240), font=font)
    d.rectangle((x, y, x + tile_w - 1, y + tile_h - 1), outline=(50, 52, 64))
sheet.save(out)
print(sheet.size, len(looks))
