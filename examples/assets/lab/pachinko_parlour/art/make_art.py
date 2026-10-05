"""Draws parlour_sheet.png and parlour_sheet.sheet.json for pachinko_parlour.asset.json.

Run: python3 make_art.py   (needs Pillow and a macOS font; the PNG is committed).
"""
import json, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"

def font(px):
    return ImageFont.truetype(FONT, px)

draws = []      # (name, w, h, fn)

def text(d, xy, s, px, fill):
    d.fontmode = "1"
    d.text(xy, s, font=font(px), fill=fill)

def text_w(s, px):
    return int(font(px).getlength(s))

def cell(name, w, h):
    def deco(fn):
        draws.append((name, w, h, fn))
        return fn
    return deco

@cell("sign", 128, 32)
def sign(d, w, h):
    d.rectangle([0, 0, w - 1, h - 1], fill="#c4122e")
    d.rectangle([1, 1, w - 2, h - 2], outline="#ffe23a")
    d.rectangle([3, 3, w - 4, h - 4], outline="#ff8a1f")
    s = "パチンコ"
    px = 22
    x0 = (w - text_w(s, px)) // 2 + 1
    text(d, (x0 + 1, 5 + 1), s, px, "#5a0716")
    text(d, (x0, 5), s, px, "#fff6d8")
    for cx in (11, w - 12):             # steel balls with a glint
        d.ellipse([cx - 6, 10, cx + 6, 22], fill="#c9d2dc", outline="#6c7a8a")
        d.ellipse([cx - 4, 12, cx - 2, 14], fill="#ffffff")
    for x in range(8, w - 8, 6):        # dots along the border
        d.point((x, 2), fill="#ffe23a"); d.point((x, h - 3), fill="#ffe23a")

@cell("blade", 24, 64)
def blade(d, w, h):
    d.rectangle([0, 0, w - 1, h - 1], fill="#1e2a8a")
    d.rectangle([1, 1, w - 2, h - 2], outline="#ffe23a")
    for i, ch in enumerate("パチンコ"):
        y = 2 + i * 15
        text(d, (5, y + 1), ch, 16, "#0a1044")
        text(d, (4, y), ch, 16, "#ffffff" if i % 2 == 0 else "#ffe23a")

@cell("banner", 16, 48)
def banner(d, w, h):
    d.rectangle([0, 0, w - 1, h - 1], fill="#d81e1e")
    d.rectangle([0, 0, w - 1, 1], fill="#fff2cc"); d.rectangle([0, h - 2, w - 1, h - 1], fill="#fff2cc")
    for i in range(3):                      # three balls, one lit gold
        cy = 9 + i * 15
        d.ellipse([2, cy - 6, 13, cy + 5], fill="#ffe23a" if i == 1 else "#dfe6ee", outline="#fff6d8")
        d.ellipse([4, cy - 4, 6, cy - 2], fill="#ffffff")
        d.line([(2, cy + 8), (13, cy + 8)], fill="#fff6d8")
@cell("machine", 24, 32)
def machine(d, w, h):
    d.rectangle([0, 0, w - 1, h - 1], fill="#26305e")
    d.rectangle([1, 1, w - 2, 7], fill="#ff5ca8")          # top lamp panel
    for x in range(3, w - 3, 4):
        d.rectangle([x, 3, x + 1, 5], fill=["#ffe23a", "#5cf0ff", "#ffffff"][(x // 4) % 3])
    d.rectangle([2, 9, w - 3, 24], fill="#0c6a7c")          # glass board
    for r in range(5):                                      # pegs
        for c in range(5):
            px = 4 + c * 4 + (2 if r % 2 else 0)
            if px < w - 4:
                d.point((px, 11 + r * 3), fill="#fff2cc")
    d.ellipse([8, 14, 15, 21], fill="#ffd23a", outline="#c4122e")   # centre pocket
    d.rectangle([10, 17, 13, 18], fill="#c4122e")
    d.rectangle([2, 26, w - 3, 30], fill="#aeb8c4")          # tray
    d.rectangle([4, 27, 9, 28], fill="#7a8696")
    d.ellipse([w - 7, 26, w - 4, 29], fill="#e9eef4")

@cell("door", 16, 32)
def door(d, w, h):
    d.rectangle([0, 0, w - 1, h - 1], fill="#7fd0e0")
    d.rectangle([0, 0, w - 1, 1], fill="#2c3440"); d.rectangle([0, h - 3, w - 1, h - 1], fill="#2c3440")
    d.rectangle([0, 0, 1, h - 1], fill="#2c3440"); d.rectangle([w - 2, 0, w - 1, h - 1], fill="#2c3440")
    for y in range(4, 14, 3):                               # glare streaks
        d.line([(4, y + 9), (9, y + 4)], fill="#c8f2f8")
    d.ellipse([4, 19, 11, 26], fill="#c4122e", outline="#ffe9a8")   # round "open" sticker
    d.rectangle([7, 22, 8, 23], fill="#ffe9a8")
    d.rectangle([w - 4, 12, w - 3, 20], fill="#c9d2dc")     # handle

@cell("vend", 16, 40)
def vend(d, w, h):
    d.rectangle([0, 0, w - 1, h - 1], fill="#e8e8ea")
    d.rectangle([1, 1, w - 2, 5], fill="#e03030")
    d.rectangle([2, 2, w - 3, 4], fill="#fff2cc")
    cols = ["#e03030", "#2a7ad8", "#30a050", "#f0b020", "#8a4a2a"]
    for r in range(4):
        for c in range(4):
            d.rectangle([2 + c * 3, 7 + r * 5, 3 + c * 3, 10 + r * 5], fill=cols[(r + c) % 5])
    d.rectangle([2, 28, w - 3, 31], fill="#2c3440")
    d.rectangle([3, 34, 12, 37], fill="#2c3440")

@cell("face", 32, 32)
def face(d, w, h):
    d.ellipse([0, 0, w - 1, h - 1], fill="#dfe6ee", outline="#58667a")
    d.ellipse([3, 3, w - 4, h - 4], outline="#f8fbff")
    for ex in (10, 21):
        d.ellipse([ex - 3, 10, ex + 3, 18], fill="#1a1e30")
        d.rectangle([ex - 1, 11, ex, 12], fill="#ffffff")
    d.ellipse([4, 19, 9, 23], fill="#ff9ab0"); d.ellipse([22, 19, 27, 23], fill="#ff9ab0")
    d.arc([11, 17, 20, 25], 20, 160, fill="#1a1e30")

@cell("window", 16, 16)
def window(d, w, h):
    d.rectangle([0, 0, w - 1, h - 1], fill="#3a4250")
    d.rectangle([2, 2, w - 3, h - 3], fill="#a6dcea")
    d.rectangle([2, 2, 7, 7], fill="#f4c6d4")
    d.rectangle([w // 2, 2, w - 3, 5], fill="#fff2cc")
    d.line([(w // 2, 2), (w // 2, h - 3)], fill="#3a4250")
    d.line([(2, h // 2), (w - 3, h // 2)], fill="#3a4250")

def bulbs(phase):
    def f(d, w, h):
        d.rectangle([0, 0, w - 1, h - 1], fill="#3a2410")
        for x in range(0, w, 4):
            lit = (x // 4) % 2 == phase
            d.rectangle([x, 0, x + 2, h - 1], fill="#fff06a" if lit else "#8a5a20")
    return f

draws.append(("bulbs_a", 64, 4, bulbs(0)))
draws.append(("bulbs_b", 64, 4, bulbs(1)))

cells = {}
x = y = rowh = 0
for name, w, h, fn in draws:
    if x + w > 160:
        x, y, rowh = 0, y + rowh, 0
    cells[name] = (x, y, w, h)
    x += w
    rowh = max(rowh, h)
W, H = 160, y + rowh
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
for name, w, h, fn in draws:
    c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fn(ImageDraw.Draw(c), w, h)
    img.paste(c, cells[name][:2])
img.save(os.path.join(HERE, "parlour_sheet.png"))
with open(os.path.join(HERE, "parlour_sheet.sheet.json"), "w") as f:
    json.dump({"format": "mei-sheet", "version": 1,
               "cells": {k: list(v) for k, v in cells.items()}}, f, indent=1)
    f.write("\n")
print(W, H)
