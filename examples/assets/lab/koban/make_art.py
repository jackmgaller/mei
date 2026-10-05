#!/usr/bin/env python3
"""Draws art/koban_sheet.png and art/koban_sheet.sheet.json (authored art, drawn with Pillow).

Run: python3 examples/assets/lab/koban/make_art.py
"""
import json
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc"

# Cells: name -> (x, y, w, h), packed by hand.
CELLS = {
    "sign":   (0, 0, 48, 16),
    "window": (48, 0, 24, 24),
    "door":   (72, 0, 20, 34),
    "board":  (92, 0, 20, 28),
    "stop":   (0, 16, 32, 32),
    "mascot": (32, 24, 20, 20),
    "wheel":  (52, 24, 16, 16),
    "aframe": (72, 34, 16, 24),
    "grille": (88, 34, 16, 16),
}


def text(d, xy, s, px, fill):
    d.fontmode = "1"
    d.text(xy, s, font=ImageFont.truetype(FONT, px), fill=fill)


def sign(d, x, y, w, h):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill="#1d3a6e")
    d.rectangle([x + 1, y + 1, x + w - 2, y + h - 2], outline="#f2efe4")
    text(d, (x + 2, y - 1), "交番", 16, "#fbf8ee")
    cx, cy = x + 40, y + 8
    d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill="#e8b830")
    d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill="#1d3a6e")
    d.ellipse([cx - 1, cy - 1, cx + 1, cy + 1], fill="#e8b830")


def window(d, x, y, w, h):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill="#c9cdd0")
    d.rectangle([x + 2, y + 2, x + w - 3, y + h - 3], fill="#274a5c")
    for k in range(5):
        d.line([x + 4 + k, y + h - 4, x + 14 + k, y + 3], fill="#3f7389" if k < 3 else "#5c93a6")
    for r in range(y + 3, y + 10, 2):
        d.line([x + 3, r, x + w - 4, r], fill="#d8d2bd")
    d.rectangle([x + 2, y + h - 7, x + w - 3, y + h - 3], fill="#6d4a30")
    d.rectangle([x + 14, y + h - 12, x + 18, y + h - 8], fill="#f4f1e8")
    d.rectangle([x + 15, y + h - 14, x + 17, y + h - 12], fill="#f4f1e8")
    d.point([x + 14, y + h - 14], fill="#f4f1e8")
    d.point([x + 18, y + h - 14], fill="#f4f1e8")
    d.line([x + 15, y + h - 11, x + 17, y + h - 11], fill="#d83a2a")
    d.line([x + 19, y + h - 13, x + 19, y + h - 11], fill="#f4f1e8")
    d.rectangle([x + 4, y + h - 10, x + 7, y + h - 8], fill="#3f8a4a")
    d.point([x + 5, y + h - 11], fill="#3f8a4a")
    for bx in (x + 8, x + 12, x + 16):
        d.line([bx, y + 2, bx, y + h - 3], fill="#1b1b1e")
    d.line([x + 1, y + h - 1, x + w - 2, y + h - 1], fill="#8d9296")


def door(d, x, y, w, h):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill="#c9cdd0")
    d.rectangle([x + 2, y + 2, x + 9, y + h - 12], fill="#274a5c")
    d.rectangle([x + 11, y + 2, x + w - 3, y + h - 12], fill="#274a5c")
    for k in range(3):
        d.line([x + 3 + k, y + 18, x + 8, y + 4], fill="#4a8099")
        d.line([x + 12 + k, y + 18, x + 17, y + 4], fill="#3f7389")
    d.rectangle([x + 2, y + h - 10, x + w - 3, y + h - 3], fill="#a9aeb2")
    d.line([x + 2, y + h - 10, x + w - 3, y + h - 10], fill="#8d9296")
    d.rectangle([x + 9, y + 14, x + 10, y + 22], fill="#2a2a2e")
    d.rectangle([x + 11, y + 14, x + 12, y + 22], fill="#2a2a2e")
    d.rectangle([x + 3, y + 5, x + 7, y + 8], fill="#f2eee0")
    d.line([x + 4, y + 6, x + 6, y + 6], fill="#c0392b")


def board(d, x, y, w, h):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill="#5b3b22")
    d.rectangle([x + 2, y + 2, x + w - 3, y + h - 3], fill="#b8895a")
    d.rectangle([x + 3, y + 3, x + 9, y + 11], fill="#f2eee0")
    d.rectangle([x + 3, y + 3, x + 9, y + 4], fill="#b0302a")
    d.ellipse([x + 5, y + 6, x + 7, y + 8], fill="#6b5a4a")
    d.line([x + 4, y + 10, x + 8, y + 10], fill="#3a3a3a")
    d.rectangle([x + 11, y + 3, x + 16, y + 9], fill="#bfd8e8")
    d.line([x + 12, y + 5, x + 15, y + 5], fill="#1d3a6e")
    d.line([x + 12, y + 7, x + 15, y + 7], fill="#1d3a6e")
    d.rectangle([x + 3, y + 13, x + 8, y + 20], fill="#f3d6dc")
    d.line([x + 4, y + 15, x + 7, y + 15], fill="#c0506a")
    d.rectangle([x + 10, y + 12, x + 16, y + 22], fill="#f2eee0")
    d.line([x + 10, y + 17, x + 16, y + 17], fill="#4a8a4a")
    d.line([x + 13, y + 12, x + 13, y + 22], fill="#3a6aa0")
    d.rectangle([x + 4, y + 22, x + 15, y + 24], fill="#f7e27a")
    for px, py in ((6, 3), (13, 3), (5, 13), (13, 12), (9, 22)):
        d.point([x + px, y + py], fill="#d02828")


def stop(d, x, y, w, h):
    d.polygon([(x, y), (x + w - 1, y), (x + (w - 1) / 2, y + h - 1)], fill="#f4f1ea")
    d.polygon([(x + 3, y + 2), (x + w - 4, y + 2), (x + (w - 1) / 2, y + h - 8)], fill="#c8201e")
    text(d, (x + 7, y + 3), "止まれ", 6, "#ffffff")


def mascot(d, x, y, w, h):
    cx, cy = x + w // 2, y + h // 2 + 1
    d.ellipse([x + 2, y + 4, x + w - 3, y + h - 1], fill="#fbe9c2", outline="#3a2a1c")
    d.pieslice([x + 1, y, x + w - 2, y + 14], 180, 360, fill="#1d3a6e")
    d.rectangle([x + 1, y + 7, x + w - 2, y + 8], fill="#14284e")
    d.ellipse([cx - 2, y + 2, cx + 1, y + 5], fill="#e8b830")
    d.rectangle([cx - 5, cy + 1, cx - 4, cy + 3], fill="#2a1a10")
    d.rectangle([cx + 4, cy + 1, cx + 5, cy + 3], fill="#2a1a10")
    d.rectangle([cx - 8, cy + 4, cx - 6, cy + 5], fill="#f2a0a0")
    d.rectangle([cx + 6, cy + 4, cx + 8, cy + 5], fill="#f2a0a0")
    d.line([cx - 2, cy + 6, cx + 2, cy + 6], fill="#a8321e")
    d.point([cx - 3, cy + 5], fill="#a8321e")
    d.point([cx + 3, cy + 5], fill="#a8321e")


def wheel(d, x, y, w, h):
    d.ellipse([x, y, x + w - 1, y + h - 1], outline="#17171a", width=2)
    d.ellipse([x + 2, y + 2, x + w - 3, y + h - 3], outline="#9aa0a6")
    for a, b in (((x + 7, y + 3), (x + 8, y + 12)), ((x + 3, y + 7), (x + 12, y + 8)),
                 ((x + 4, y + 4), (x + 11, y + 11)), ((x + 11, y + 4), (x + 4, y + 11))):
        d.line([a, b], fill="#b9bec2")
    d.rectangle([x + 7, y + 7, x + 8, y + 8], fill="#2a2a2e")


def aframe(d, x, y, w, h):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill="#f4f1e8")
    d.rectangle([x, y, x + w - 1, y + 5], fill="#e8b830")
    d.rectangle([x, y + h - 4, x + w - 1, y + h - 1], fill="#1d3a6e")
    text(d, (x + 1, y - 1), "安全", 7, "#1d3a6e")
    d.ellipse([x + 6, y + 9, x + 9, y + 12], fill="#2a2a2e")
    d.rectangle([x + 6, y + 12, x + 9, y + 17], fill="#2a2a2e")
    d.line([x + 6, y + 18, x + 5, y + 20], fill="#2a2a2e")
    d.line([x + 9, y + 18, x + 10, y + 20], fill="#2a2a2e")
    d.line([x + 1, y + 20, x + w - 2, y + 20], fill="#c0392b")


def grille(d, x, y, w, h):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill="#d7d9d6")
    d.ellipse([x + 1, y + 1, x + w - 2, y + h - 2], fill="#4a4e52")
    for r in range(y + 3, y + h - 3, 2):
        d.line([x + 3, r, x + w - 4, r], fill="#8a8f93")
    d.ellipse([x + 6, y + 6, x + 9, y + 9], fill="#d7d9d6")


DRAW = {"sign": sign, "window": window, "door": door, "board": board, "stop": stop,
        "mascot": mascot, "wheel": wheel, "aframe": aframe, "grille": grille}


def main():
    im = Image.new("RGBA", (112, 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    for name, (x, y, w, h) in CELLS.items():
        DRAW[name](d, x, y, w, h)
    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    im.save(os.path.join(HERE, "art", "koban_sheet.png"))
    with open(os.path.join(HERE, "art", "koban_sheet.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1,
                   "cells": {k: list(v) for k, v in CELLS.items()}}, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
