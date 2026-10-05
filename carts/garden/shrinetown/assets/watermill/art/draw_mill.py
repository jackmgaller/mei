#!/usr/bin/env python3
"""Adds the water wheel to mill_sheet.png (the lab watermill's sheet, copied from
examples/assets/lab/watermill/art): a 64 x 64 cutout of the wheel's side, rim, spokes, hub and
paddle tips, drawn once on each side of the wheel. Keeps the sheet's first 48 rows (the lab's
cells) and redraws everything below, so it can be run again. Writes mill_sheet.png and
mill_sheet.sheet.json beside this file."""
import json, math, os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PNG = os.path.join(HERE, "mill_sheet.png")
JSON = os.path.join(HERE, "mill_sheet.sheet.json")


def hexc(s):
    return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16), 255)


old = Image.open(PNG).convert("RGBA").crop((0, 0, 256, 48))
sheet = Image.new("RGBA", (256, 112), (0, 0, 0, 0))
sheet.paste(old, (0, 0))

# the wheel: 64 texels span the paddle tips (radius 2.05 m), so a texel is 6.4 cm
K = 4                                   # drawn at 4x, then reduced without smoothing
S = 64 * K
w = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(w)
c = S / 2
px = S / 2 / 2.05                       # pixels a metre
RIM, PAD, SPOKE, HUB = hexc("#5a3c24"), hexc("#86603a"), hexc("#6a4a2c"), hexc("#3e4248")
for k in range(16):                     # paddles, 26 cm wide, from inside the rim out to 2.04 m
    a = 2 * math.pi * k / 16
    ca, sa = math.cos(a), math.sin(a)
    t0, t1, h = 1.55 * px, 2.04 * px, 0.13 * px
    d.polygon([(c + ca * t0 - sa * h, c + sa * t0 + ca * h), (c + ca * t1 - sa * h, c + sa * t1 + ca * h),
               (c + ca * t1 + sa * h, c + sa * t1 - ca * h), (c + ca * t0 + sa * h, c + sa * t0 - ca * h)], fill=PAD)
d.ellipse([c - 1.8 * px, c - 1.8 * px, c + 1.8 * px, c + 1.8 * px], outline=RIM, width=int(0.2 * px))
for k in range(8):                      # spokes, 16 cm wide
    a = 2 * math.pi * (k + 0.5) / 8
    x1, y1 = c + math.cos(a) * 1.65 * px, c + math.sin(a) * 1.65 * px
    d.line([c, c, x1, y1], fill=SPOKE, width=int(0.16 * px))
d.ellipse([c - 0.28 * px, c - 0.28 * px, c + 0.28 * px, c + 0.28 * px], fill=HUB)
small = w.resize((64, 64), Image.NEAREST)
# hard edges: a texel is solid or a hole
px_ = small.load()
for y in range(64):
    for x in range(64):
        r, g, b, a = px_[x, y]
        px_[x, y] = (r, g, b, 255) if a >= 128 else (0, 0, 0, 0)
sheet.paste(small, (0, 48))
sheet.save(PNG)

cells = json.load(open(JSON))["cells"]
cells["wheel"] = [0, 48, 64, 64]
with open(JSON, "w") as fh:
    fh.write('{"format": "mei-sheet", "version": 1,\n "cells": {\n')
    fh.write(",\n".join('  "%s": %s' % (k, json.dumps(v)) for k, v in cells.items()))
    fh.write("\n }}\n")
print("wrote", PNG)
