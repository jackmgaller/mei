"""Draws art/ferry_sheet.png, the ferry's texture sheet (needs Pillow). Run from anywhere."""
import json, math, os
from PIL import Image, ImageDraw, ImageFont

here = os.path.dirname(os.path.abspath(__file__))
W, H = 128, 64
im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.fontmode = "1"
cells = {}


def cell(name, x, y, w, h):
    cells[name] = [x, y, w, h]


def rgb(s):
    return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


WALL, FRAME = rgb("#f0ede2"), rgb("#8d949e")
G1, G2, G3 = rgb("#223f68"), rgb("#3c6896"), rgb("#6d9bc4")
NAVY, RED, WHITE = rgb("#1f3d78"), rgb("#c8352b"), rgb("#f4f1e6")

# windows: 32 x 32, a cabin wall with two windows, repeated
cell("windows", 0, 0, 32, 32)
d.rectangle([0, 0, 31, 31], fill=WALL)
d.rectangle([0, 28, 31, 31], fill=rgb("#d9d6ca"))
for x0 in (2, 18):
    d.rectangle([x0, 8, x0 + 12, 21], fill=FRAME)
    for yy in range(9, 21):
        t = (yy - 9) / 11
        d.line([x0 + 1, yy, x0 + 11, yy], fill=G1 if t < .3 else G2 if t < .75 else G3)
    d.line([x0 + 2, 19, x0 + 6, 10], fill=rgb("#bcd3e6"))
    d.line([x0 + 4, 19, x0 + 7, 13], fill=rgb("#bcd3e6"))
    d.line([x0 + 6, 9, x0 + 6, 20], fill=FRAME)

# bridge: 32 x 16, a wheelhouse's band of glass with mullions
cell("bridge", 32, 0, 32, 16)
d.rectangle([32, 0, 63, 15], fill=WALL)
d.rectangle([32, 3, 63, 12], fill=FRAME)
for x0 in (34, 48):
    for yy in range(4, 12):
        t = (yy - 4) / 7
        d.line([x0, yy, x0 + 12, yy], fill=G1 if t < .3 else G2 if t < .7 else G3)
    d.line([x0 + 1, 10, x0 + 5, 5], fill=rgb("#bcd3e6"))
d.rectangle([32, 13, 63, 15], fill=rgb("#d9d6ca"))

# name board: 64 x 16, "shiokaze maru" in navy on white
cell("name", 64, 0, 64, 16)
d.rectangle([64, 0, 127, 15], fill=WHITE)
font = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", 12)
d.text((66, 1), "しおかぜ丸", font=font, fill=NAVY)
d.rectangle([64, 0, 127, 0], fill=NAVY)
d.rectangle([64, 15, 127, 15], fill=NAVY)

# funnel roundel: 16 x 16, a navy disc with a white wave, cut out round
cell("logo", 32, 16, 16, 16)
for yy in range(16):
    for xx in range(16):
        r = math.hypot(xx - 7.5, yy - 7.5)
        if r <= 7.6:
            im.putpixel((32 + xx, 16 + yy), WHITE if r > 6.2 else NAVY)
for xx in range(2, 14):
    yy = 8 + round(1.6 * math.sin(xx * 0.9))
    for k in (-2, 0, 2):
        d.point((32 + xx, 16 + yy + k), fill=WHITE)

# life ring: 16 x 16, orange and white quarters, hole in the middle
cell("buoy", 48, 16, 16, 16)
for yy in range(16):
    for xx in range(16):
        dx, dy = xx - 7.5, yy - 7.5
        r = math.hypot(dx, dy)
        if 3.0 <= r <= 7.6:
            quarter = int(math.atan2(dy, dx) / (math.pi / 2) + 8) % 2
            c = rgb("#e8591f") if quarter else WHITE
            if r > 7.0 or r < 3.6:
                c = rgb("#b8431a") if quarter else rgb("#d0cdc0")
            im.putpixel((48 + xx, 16 + yy), c)

# flag: 24 x 16, a white field with a red sun
cell("flag", 64, 16, 24, 16)
d.rectangle([64, 16, 87, 31], fill=WHITE)
for yy in range(16):
    for xx in range(24):
        if math.hypot(xx - 11.5, yy - 7.5) <= 4.6:
            im.putpixel((64 + xx, 16 + yy), RED)

# vending machine front: 16 x 24
cell("vend", 96, 16, 16, 24)
d.rectangle([96, 16, 111, 39], fill=rgb("#d8dde2"))
d.rectangle([97, 17, 110, 29], fill=rgb("#1a2230"))
cols = ["#d63a2f", "#e8a61f", "#3a8f4a", "#2f6fc0", "#f0efe6", "#8a4fa0", "#d63a2f", "#2f6fc0"]
for i in range(8):
    x0 = 98 + (i % 4) * 3
    y0 = 18 + (i // 4) * 6
    d.rectangle([x0, y0, x0 + 1, y0 + 4], fill=rgb(cols[i]))
    d.point((x0, y0 + 5), fill=rgb("#f6d070"))
d.rectangle([97, 31, 105, 32], fill=rgb("#f0cf3a"))
d.rectangle([107, 31, 110, 36], fill=rgb("#3b4350"))
d.rectangle([97, 35, 105, 38], fill=rgb("#4a525e"))
d.rectangle([96, 39, 111, 39], fill=rgb("#8a9098"))

im.save(os.path.join(here, "ferry_sheet.png"))
with open(os.path.join(here, "ferry_sheet.sheet.json"), "w") as f:
    json.dump({"format": "mei-sheet", "version": 1, "cells": cells}, f, indent=2)
    f.write("\n")
