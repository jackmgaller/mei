#!/usr/bin/env python3
"""Draws art/sento_sheet.png (and its .sheet.json): the sento front's signs, noren, vending
machine, bicycle and steam. Fonts are macOS system fonts; the PNG is committed."""
import json, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc"
FONT_L = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
CELLS = {
    "noren_blue": (0, 0, 24, 32), "noren_red": (24, 0, 24, 32), "plaque": (48, 0, 32, 32),
    "chochin": (80, 0, 32, 16), "vend": (0, 32, 16, 32), "kanban": (16, 32, 32, 16),
    "bike": (48, 32, 48, 24), "steam": (0, 64, 32, 16), "yu_red": (32, 64, 16, 16),
    "nobori": (96, 32, 16, 48),
}
sheet = Image.new("RGBA", (128, 96), (0, 0, 0, 0))


def hexc(s, a=255):
    return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16), a)


def glyph(ch, size, fg, w, h, dx=0, dy=0, fnt=FONT):
    """The character, drawn big, shrunk and thresholded: hard pixels, no antialiasing."""
    k = 8
    big = Image.new("L", (w * k, h * k), 0)
    d = ImageDraw.Draw(big)
    f = ImageFont.truetype(fnt, size * k)
    bb = d.textbbox((0, 0), ch, font=f)
    x = (w * k - (bb[2] - bb[0])) // 2 - bb[0] + dx * k
    y = (h * k - (bb[3] - bb[1])) // 2 - bb[1] + dy * k
    d.text((x, y), ch, font=f, fill=255)
    small = big.resize((w, h), Image.BOX).point(lambda v: 255 if v > 110 else 0)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(Image.new("RGBA", (w, h), fg), (0, 0), small)
    return out


def put(name, img):
    x, y, w, h = CELLS[name]
    assert img.size == (w, h), (name, img.size)
    sheet.paste(img, (x, y))


def noren(cloth, edge):
    w, h = 24, 32
    im = Image.new("RGBA", (w, h), hexc(cloth))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, 2], fill=hexc(edge))          # the rod's fold
    d.rectangle([0, 3, w - 1, 3], fill=hexc("#10203c"))
    im.alpha_composite(glyph("ゆ", 17, hexc("#f4efe2"), w, 22, 0, 0), (0, 6))
    d.rectangle([0, h - 2, w - 1, h - 1], fill=hexc(edge))  # hem
    for x in (0, w - 1):
        d.line([x, 3, x, h - 1], fill=hexc("#10203c"))
    d.rectangle([w // 2 - 1, 9, w // 2, h - 1], fill=(0, 0, 0, 0))   # the slit
    for x in range(3, w, 4):
        d.point([x, h - 1], fill=(0, 0, 0, 0))                        # scalloped hem
    return im


put("noren_blue", noren("#2c4d92", "#e8dfc8"))
put("noren_red", noren("#b8352f", "#e8dfc8"))

# plaque: yu (hot water) on indigo with a wooden frame
im = Image.new("RGBA", (32, 32), hexc("#7a5232"))
d = ImageDraw.Draw(im)
d.rectangle([2, 2, 29, 29], fill=hexc("#22397a"))
d.rectangle([2, 2, 29, 2], fill=hexc("#4f6cae"))
im.alpha_composite(glyph("ゆ", 24, hexc("#f4efe2"), 28, 28, 0, 0), (2, 2))
put("plaque", im)

# paper lantern wrapped around a cylinder: two characters
im = Image.new("RGBA", (32, 16), hexc("#c63a2c"))
d = ImageDraw.Draw(im)
for y in (0, 1, 7, 8, 14, 15):
    d.line([0, y, 31, y], fill=hexc("#8a2218") if y in (7, 8) else hexc("#6b1a12"))
im.alpha_composite(glyph("湯", 13, hexc("#f4efe2"), 14, 14, 0, 0, fnt=FONT_L), (1, 1))
im.alpha_composite(glyph("ゆ", 11, hexc("#f4efe2"), 14, 11, 0, 0), (17, 2))
put("chochin", im)

# vending machine front, 16 x 32: red body, lit drinks, buttons, slot
im = Image.new("RGBA", (16, 32), hexc("#c8322a"))
d = ImageDraw.Draw(im)
d.rectangle([1, 1, 14, 3], fill=hexc("#f4efe2"))
d.rectangle([2, 2, 5, 2], fill=hexc("#c8322a"))
d.rectangle([7, 2, 12, 2], fill=hexc("#3868b8"))
d.rectangle([1, 5, 14, 17], fill=hexc("#1c2230"))
cols = ["#f4efe2", "#e0b030", "#58a868", "#3868b8", "#e87aa0", "#8a5a3a"]
for r in range(3):
    for c in range(4):
        x, y = 2 + c * 3, 6 + r * 4
        d.rectangle([x, y, x + 1, y + 2], fill=hexc(cols[(r * 4 + c) % 6]))
        d.rectangle([x, y + 3, x + 1, y + 3], fill=hexc("#5a6070"))
for c in range(4):
    d.rectangle([2 + c * 3, 19, 3 + c * 3, 19], fill=hexc("#f0d050" if c % 2 else "#f4efe2"))
d.rectangle([1, 21, 14, 22], fill=hexc("#8a2018"))
d.rectangle([9, 24, 13, 25], fill=hexc("#10131c"))
d.rectangle([2, 24, 6, 29], fill=hexc("#10131c"))
d.rectangle([1, 30, 14, 31], fill=hexc("#8a2018"))
put("vend", im)

# open sign: black on cream with a wooden border
im = Image.new("RGBA", (32, 16), hexc("#ece4cc"))
d = ImageDraw.Draw(im)
d.rectangle([0, 0, 31, 15], outline=hexc("#7a5232"))
for i, ch in enumerate("営業中"):
    im.alpha_composite(glyph(ch, 11, hexc("#20201c"), 10, 12, 0, 0), (1 + i * 10, 2))
put("kanban", im)

# bicycle, side view, with a front basket; mostly holes
im = Image.new("RGBA", (48, 24), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
tyre, rim, frame = hexc("#1c1c20"), hexc("#b8bcc4"), hexc("#2f8f86")
for cx in (9, 38):
    d.ellipse([cx - 8, 7, cx + 8, 23], outline=tyre, width=2)
    d.ellipse([cx - 6, 9, cx + 6, 21], outline=rim)
    d.line([cx - 5, 15, cx + 5, 15], fill=rim)
    d.line([cx, 10, cx, 20], fill=rim)
d.line([9, 15, 20, 15], fill=frame, width=2)
d.line([20, 15, 17, 7], fill=frame, width=2)
d.line([17, 7, 34, 8], fill=frame, width=2)
d.line([34, 8, 38, 15], fill=frame, width=2)
d.line([20, 15, 34, 8], fill=frame, width=1)
d.line([9, 15, 17, 7], fill=frame, width=1)
d.rectangle([14, 5, 20, 6], fill=tyre)                           # saddle
d.line([33, 8, 35, 3], fill=rim, width=1)
d.line([33, 3, 38, 3], fill=tyre, width=2)
d.rectangle([40, 5, 47, 11], outline=hexc("#c0a060"))            # basket
d.rectangle([41, 6, 46, 10], fill=hexc("#8a7040"))
put("bike", im)

# a puff of steam
im = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
for box in [(2, 6, 14, 15), (8, 2, 22, 13), (16, 5, 30, 15), (4, 9, 28, 15)]:
    d.ellipse(box, fill=hexc("#f2f4f6"))
d.ellipse([5, 12, 26, 15], fill=hexc("#d4dce4"))
put("steam", im)

# chimney emblem: yu in white on red, 16 x 16
im = Image.new("RGBA", (16, 16), hexc("#c8322a"))
im.alpha_composite(glyph("ゆ", 13, hexc("#f4efe2"), 16, 16, 0, 0), (0, 0))
ImageDraw.Draw(im).rectangle([0, 0, 15, 15], outline=hexc("#f4efe2"))
put("yu_red", im)

# nobori banner: yu over "open", white on red, 16 x 48
im = Image.new("RGBA", (16, 48), hexc("#c8322a"))
d = ImageDraw.Draw(im)
d.rectangle([0, 0, 15, 2], fill=hexc("#f4efe2"))
d.rectangle([0, 47, 15, 47], fill=hexc("#f4efe2"))
im.alpha_composite(glyph("ゆ", 14, hexc("#f4efe2"), 16, 16, 0, 0), (0, 5))
for i, ch in enumerate("営業中"):
    im.alpha_composite(glyph(ch, 9, hexc("#f4efe2"), 10, 10, 0, 0), (3, 22 + i * 8))
for x in (0, 15):
    d.line([x, 3, x, 44], fill=hexc("#8a2018"))
put("nobori", im)

os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
sheet.save(os.path.join(HERE, "art", "sento_sheet.png"))
with open(os.path.join(HERE, "art", "sento_sheet.sheet.json"), "w") as fh:
    json.dump({"format": "mei-sheet", "version": 1, "cells": {k: list(v) for k, v in CELLS.items()}},
              fh, indent=2)
big = sheet.resize((512, 384), Image.NEAREST)
bg = Image.new("RGBA", big.size, (90, 120, 110, 255))
bg.alpha_composite(big)
bg.save(os.path.join(HERE, "art", "sento_sheet_x4.png"))
