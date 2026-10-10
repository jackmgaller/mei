#!/usr/bin/env python3
"""Draw art/sheet.png (and its .sheet.json) for look 04, Sun & Moon Twin. Needs Pillow.

Cells: the sunburst on the sun's top, the 明 MEI badge, a cartridge label, the four face-button
caps with their letters and the controller's small 明.
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ART = HERE / "art"
HIRAGINO = "/System/Library/Fonts/ヒラギノ角ゴシック W7.ttc"
AVENIR = "/System/Library/Fonts/Avenir Next.ttc"

SUN = (240, 152, 64)
SUN_HI = (250, 190, 96)
SUN_LO = (226, 120, 48)
MOON = (190, 206, 234)
NAVY = (34, 40, 62)
WHITE = (250, 250, 246)

cells = {}
sheet = Image.new("RGBA", (128, 128), (0, 0, 0, 0))


def put(name, img, x, y):
    sheet.paste(img, (x, y))
    cells[name] = [x, y, img.width, img.height]


def sunburst(size=64):
    """Rays around a bright centre; drawn at 4x and reduced."""
    k = 4
    s = size * k
    img = Image.new("RGB", (s, s), SUN)
    d = ImageDraw.Draw(img)
    c = s / 2
    rays = 16
    for i in range(rays):
        a0 = (i - 0.22) * 2 * math.pi / rays
        a1 = (i + 0.22) * 2 * math.pi / rays
        r = s * 0.75
        d.polygon([(c, c), (c + r * math.cos(a0), c + r * math.sin(a0)),
                   (c + r * math.cos(a1), c + r * math.sin(a1))], fill=SUN_HI)
    # an outer ring, a little darker, where the top meets its bevel
    d.ellipse([c - s * 0.5, c - s * 0.5, c + s * 0.5, c + s * 0.5], outline=SUN_LO, width=int(s * 0.05))
    d.ellipse([c - s * 0.30, c - s * 0.30, c + s * 0.30, c + s * 0.30], fill=SUN_LO)
    d.ellipse([c - s * 0.27, c - s * 0.27, c + s * 0.27, c + s * 0.27], fill=SUN_HI)
    return img.resize((size, size), Image.LANCZOS)


def mei_mark(h, draw_to, x, y):
    """明 with 日 orange and 月 pale blue, top-left at x, y, h pixels tall (drawn on an RGBA)."""
    font = ImageFont.truetype(HIRAGINO, h)
    glyph = Image.new("L", (h * 2, h * 2), 0)
    ImageDraw.Draw(glyph).text((h // 4, h // 4), "明", font=font, fill=255)
    box = glyph.getbbox()
    glyph = glyph.crop(box)
    w = glyph.width
    # split at the emptiest column in the middle third: left is 日, right is 月
    cols = [sum(glyph.getpixel((cx, cy)) for cy in range(glyph.height)) for cx in range(w)]
    lo, hi = w // 4, w * 2 // 3
    split = min(range(lo, hi), key=lambda cx: cols[cx])
    for cx in range(w):
        for cy in range(glyph.height):
            a = glyph.getpixel((cx, cy))
            if a > 0 and x + cx < draw_to.width and y + cy < draw_to.height:
                col = SUN_HI if cx < split else MOON
                bg = draw_to.getpixel((x + cx, y + cy))
                t = a / 255
                draw_to.putpixel((x + cx, y + cy), tuple(int(bg[i] * (1 - t) + col[i] * t) for i in range(3)))
    return glyph.width, glyph.height


def badge():
    w, h, k = 64, 24, 1
    img = Image.new("RGB", (w, h), NAVY)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=(70, 80, 112))
    gw, gh = mei_mark(18, img, 5, 3)
    font = ImageFont.truetype(AVENIR, 15, index=0)  # Avenir Next Bold
    d.text((5 + gw + 5, 2), "MEI", font=font, fill=WHITE)
    return img


def label():
    """A cartridge label: night sky, full moon, susuki grass, the 明 mark in a corner."""
    w, h, k = 48, 40, 4
    big = Image.new("RGB", (w * k, h * k), (20, 26, 60))
    d = ImageDraw.Draw(big)
    for yy in range(h * k):
        t = yy / (h * k)
        col = (int(20 + 50 * t), int(26 + 30 * t), int(60 + 50 * t))
        d.line([(0, yy), (w * k, yy)], fill=col)
    d.ellipse([18 * k, 5 * k, 38 * k, 25 * k], fill=(250, 236, 196))
    for i in range(9):
        bx = (2 + i * 5.5) * k
        d.polygon([(bx, h * k), (bx + 6 * k, h * k), (bx + 2 * k + (i % 3 - 1) * 4 * k, (21 + (i * 7) % 8) * k)],
                  fill=(16, 18, 30))
    d.rectangle([0, (h - 7) * k, w * k, h * k], fill=(16, 18, 30))
    img = big.resize((w, h), Image.LANCZOS)
    mei_mark(9, img, 3, 2)
    return img


def button_cap(letter, col):
    s, k = 16, 4
    big = Image.new("RGB", (s * k, s * k), col)
    d = ImageDraw.Draw(big)
    font = ImageFont.truetype(AVENIR, 11 * k, index=0)
    bb = d.textbbox((0, 0), letter, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((s * k - tw) / 2 - bb[0], (s * k - th) / 2 - bb[1]), letter, font=font, fill=WHITE)
    return big.resize((s, s), Image.LANCZOS)


def small_mark():
    w, h = 24, 12
    img = Image.new("RGB", (w, h), NAVY)
    mei_mark(10, img, 7, 1)
    return img


put("sunburst", sunburst(), 0, 0)
put("badge", badge(), 64, 0)
put("label", label(), 64, 24)
put("small_mark", small_mark(), 64, 64)
BUTTONS = {"a": (232, 110, 52), "b": (226, 168, 40), "x": (88, 150, 214), "y": (70, 70, 150)}
for i, (name, col) in enumerate(BUTTONS.items()):
    put("btn_" + name, button_cap(name.upper(), col), i * 16, 64)

ART.mkdir(exist_ok=True)
sheet.save(ART / "sheet.png")
(ART / "sheet.sheet.json").write_text(json.dumps({"format": "mei-sheet", "version": 1, "cells": cells}, indent=1) + "\n")
print("wrote", ART / "sheet.png", sorted(cells))
