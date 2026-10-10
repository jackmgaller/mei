#!/usr/bin/env python3
"""Draws art/sakura_sheet.png and art/sakura_sheet.sheet.json for the Sakura Pastel console and
controller (authored art, drawn with Pillow and committed).

Run: python3 examples/assets/console_lab/13_sakura_pastel/make_art.py
"""
import json
import math
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
KAKU = "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc"
KAKU_THIN = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
MARU = "/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc"
ROUND = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"

# The palette of the look.
ROSE = "#b9506f"       # deep sakura, badges
ROSE_D = "#8e3a55"
PINK = "#f6bfcd"       # lower shell
BLUSH = "#fbdbe3"      # upper shell
PETAL = "#f49ab2"
MINT = "#a6dcc6"
MINT_D = "#6fb79c"
CREAM = "#fff6ec"
SUN = "#f7a03a"        # the 日 of 明
MOON = "#b8d4f4"       # the 月
INK = "#3a2a33"

# Cells: name -> (x, y, w, h), packed by hand.
CELLS = {
    "logo":      (0, 0, 64, 24),
    "label":     (64, 0, 48, 40),
    "port1":     (0, 24, 24, 16),
    "port2":     (24, 24, 24, 16),
    "card1":     (0, 40, 32, 12),
    "card2":     (32, 40, 32, 12),
    "sakura":    (64, 40, 32, 32),
    "edition":   (0, 52, 48, 12),
    "power":     (0, 64, 32, 8),
    "reset":     (32, 64, 32, 8),
    "pad_badge": (96, 40, 24, 16),
    "btn_a":     (96, 56, 16, 16),
    "btn_b":     (112, 56, 16, 16),
    "btn_x":     (0, 72, 16, 16),
    "btn_y":     (16, 72, 16, 16),
    "rear":      (32, 72, 64, 16),
    "sakura_mint": (128, 0, 32, 32),
}

# A 3 x 5 pixel font for the small printing.
PIX = {
    "A": ["010", "101", "111", "101", "101"], "B": ["110", "101", "110", "101", "110"],
    "C": ["011", "100", "100", "100", "011"], "D": ["110", "101", "101", "101", "110"],
    "E": ["111", "100", "110", "100", "111"], "H": ["101", "101", "111", "101", "101"], "G": ["011", "100", "101", "101", "011"],
    "I": ["111", "010", "010", "010", "111"],
    "K": ["101", "101", "110", "101", "101"], "L": ["100", "100", "100", "100", "111"],
    "M": ["101", "111", "111", "101", "101"], "N": ["110", "101", "101", "101", "101"],
    "O": ["010", "101", "101", "101", "010"], "P": ["110", "101", "110", "100", "100"],
    "R": ["110", "101", "110", "101", "101"], "S": ["011", "100", "010", "001", "110"],
    "T": ["111", "010", "010", "010", "010"], "U": ["101", "101", "101", "101", "111"],
    "V": ["101", "101", "101", "101", "010"], "W": ["101", "101", "111", "111", "101"],
    "Y": ["101", "101", "010", "010", "010"], "1": ["010", "110", "010", "010", "111"],
    "2": ["110", "001", "010", "100", "111"], "&": ["010", "101", "010", "101", "011"],
    "-": ["000", "000", "111", "000", "000"], " ": ["000", "000", "000", "000", "000"],
}


def pixtext(d, x, y, s, fill):
    for ch in s:
        g = PIX[ch]
        for r, row in enumerate(g):
            for c, bit in enumerate(row):
                if bit == "1":
                    d.point([x + c, y + r], fill=fill)
        x += 4
    return x


def pixwidth(s):
    return len(s) * 4 - 1


def glyph_mask(ch, font, px, size):
    m = Image.new("L", size, 0)
    md = ImageDraw.Draw(m)
    md.fontmode = "1"
    f = ImageFont.truetype(font, px)
    bb = md.textbbox((0, 0), ch, font=f)
    md.text(((size[0] - (bb[2] - bb[0])) // 2 - bb[0], (size[1] - (bb[3] - bb[1])) // 2 - bb[1]),
            ch, font=f, fill=255)
    return m


def mei_glyph(im, x, y, px, box):
    """明 with the 日 in sun orange and the 月 in moon blue, a 1-texel shadow under it."""
    m = glyph_mask("明", KAKU, px, box)
    w, h = box
    # The bold glyph's strokes touch, so the halves are told apart on a thin weight: there the 日
    # is the connected stroke group holding the leftmost lit texel; each bold texel takes the half
    # of the nearest thin one.
    thin = glyph_mask("明", KAKU_THIN, px, box)
    lit = {(c, r) for r in range(h) for c in range(w) if thin.getpixel((c, r))}
    seed = min(lit)
    sun, todo = {seed}, [seed]
    while todo:
        c, r = todo.pop()
        for q in ((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)):
            if q in lit and q not in sun:
                sun.add(q)
                todo.append(q)
    def is_sun(c, r):
        q = min(lit, key=lambda p: ((p[0] - c) ** 2 + (p[1] - r) ** 2, -p[0]))
        return q in sun
    for r in range(h):
        for c in range(w):
            if m.getpixel((c, r)):
                if x + c + 1 < im.width and y + r + 1 < im.height:
                    im.putpixel((x + c + 1, y + r + 1), (60, 30, 45))
    for r in range(h):
        for c in range(w):
            if m.getpixel((c, r)):
                im.putpixel((x + c, y + r), SUN_RGB if is_sun(c, r) else MOON_RGB)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


SUN_RGB = rgb(SUN)
MOON_RGB = rgb(MOON)


def logo(im, d, x, y, w, h):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=ROSE)
    d.rectangle([x + 1, y + 1, x + w - 2, y + h - 2], outline="#d97c97")
    mei_glyph(im, x + 3, y + 2, 19, (20, 20))
    f = ImageFont.truetype(ROUND, 14)
    d.fontmode = "1"
    d.text((x + 26, y + 1), "MEI", font=f, fill="#ffffff")
    pixtext(d, x + 27, y + 17, "SAKURA", "#ffd3df")
    d.point([x + 24, y + 12], fill="#ffffff")


def blossom(d, cx, cy, r, petal, edge, centre, notch=True):
    """A five-petal sakura: each petal an ellipse with a notch cut at its tip."""
    for k in range(5):
        a = -math.pi / 2 + k * 2 * math.pi / 5
        px, py = cx + math.cos(a) * r * 0.52, cy + math.sin(a) * r * 0.52
        rr = r * 0.48
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=petal, outline=edge)
    if notch:
        for k in range(5):
            a = -math.pi / 2 + k * 2 * math.pi / 5
            tx, ty = cx + math.cos(a) * r * 0.98, cy + math.sin(a) * r * 0.98
            n = max(1.0, r * 0.13)
            d.polygon([(tx - n * math.sin(a) - 0, ty + n * math.cos(a)),
                       (tx + n * math.sin(a), ty - n * math.cos(a)),
                       (cx + math.cos(a) * r * 0.78, cy + math.sin(a) * r * 0.78)], fill=(0, 0, 0, 0))
    cr = r * 0.2
    d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=centre)


def label(im, d, x, y, w, h):
    """The cart in the slot: a spring scene, sun and moon over a sakura branch."""
    # sky: mint at the top fading to cream
    for r in range(h):
        t = r / (h - 1)
        c = tuple(int(a + (b - a) * t) for a, b in zip(rgb("#bfe6d8"), rgb("#fff1e6")))
        d.line([x, y + r, x + w - 1, y + r], fill=c)
    d.ellipse([x + 6, y + 6, x + 15, y + 15], fill=SUN)             # sun
    d.ellipse([x + 32, y + 4, x + 41, y + 13], fill=MOON)           # moon
    d.ellipse([x + 35, y + 3, x + 44, y + 12], fill="#cfeee2")      # its shadow: a crescent
    # a branch across the lower half with blossoms
    d.line([x, y + 30, x + 18, y + 24, x + 34, y + 27, x + 46, y + 21], fill="#7a4a42", width=2)
    d.line([x + 18, y + 24, x + 22, y + 18], fill="#7a4a42")
    for bx, by, br in ((x + 8, y + 26, 5), (x + 21, y + 17, 5), (x + 30, y + 26, 6), (x + 43, y + 20, 4),
                       (x + 14, y + 31, 3)):
        blossom(d, bx, by, br, PETAL, "#e07894", "#ffe58a", notch=False)
    # title strip
    d.rectangle([x, y + h - 7, x + w - 1, y + h - 1], fill=ROSE)
    pixtext(d, x + (w - pixwidth("HARU MEI")) // 2, y + h - 6, "HARU MEI", "#ffffff")
    d.rectangle([x, y, x + w - 1, y + h - 1], outline="#e9a7b8")


def port(d, x, y, w, h, n):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=MINT)
    d.rectangle([x, y, x + w - 1, y], fill="#c3eadb")
    # the socket: a rounded D, darker inside, five gold pins
    sx0, sy0, sx1, sy1 = x + 4, y + 3, x + w - 5, y + h - 4
    d.rounded_rectangle([sx0, sy0, sx1, sy1], radius=3, fill="#4a3a44", outline=MINT_D)
    d.rectangle([sx0 + 2, sy0 + 2, sx1 - 2, sy0 + 4], fill="#2c2129")
    for k in range(5):
        px = sx0 + 3 + k * 3
        d.point([px, sy0 + 3], fill="#e8c46a")
    pixtext(d, x + 1, y + 1, str(n), MINT_D)


def card(d, x, y, w, h, n):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=MINT)
    d.rectangle([x, y, x + w - 1, y], fill="#c3eadb")
    d.rectangle([x + 9, y + 4, x + w - 3, y + 6], fill="#3c2c36")          # the slit
    d.line([x + 9, y + 7, x + w - 3, y + 7], fill="#8fcab4")
    pixtext(d, x + 2, y + 3, str(n), "#4f8f78")


def edition(d, x, y, w, h):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=CREAM)
    d.fontmode = "1"
    f = ImageFont.truetype(MARU, 11)
    d.text((x + 1, y - 2), "さくら", font=f, fill=ROSE)
    blossom(d, x + w - 6, y + 6, 5, PETAL, "#e07894", "#ffe58a", notch=False)


def printed(d, x, y, w, h, s, bg, fg):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=bg)
    pixtext(d, x + (w - pixwidth(s)) // 2, y + (h - 5) // 2, s, fg)


def pad_badge(im, d, x, y, w, h):
    d.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=3, fill=ROSE)
    mei_glyph(im, x + 5, y + 1, 13, (14, 14))


def face_button(d, x, y, w, h, cap, ink, letter):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=cap)
    d.fontmode = "1"
    f = ImageFont.truetype(ROUND, 12)
    bb = d.textbbox((0, 0), letter, font=f)
    d.text((x + (w - (bb[2] - bb[0])) // 2 - bb[0], y + (h - (bb[3] - bb[1])) // 2 - bb[1]),
           letter, font=f, fill=ink)


def rear(d, x, y, w, h):
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=PINK)
    for lx, s in ((2, "DC"), (20, "AV"), (40, "ANT")):
        pixtext(d, x + lx, y + 10, s, "#a8607a")


def main():
    im = Image.new("RGBA", (160, 88), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = CELLS
    logo(im, d, *c["logo"])
    label(im, d, *c["label"])
    port(d, *c["port1"], 1)
    port(d, *c["port2"], 2)
    card(d, *c["card1"], 1)
    card(d, *c["card2"], 2)
    x, y, w, h = c["sakura"]
    blossom(d, x + w / 2 - 0.5, y + h / 2 - 0.5, 15.5, "#f7a8bd", "#d9718f", "#ffe58a")
    # inner veins: a lighter star
    for k in range(5):
        a = -math.pi / 2 + k * 2 * math.pi / 5
        d.line([x + 16 + math.cos(a) * 4, y + 16 + math.sin(a) * 4,
                x + 16 + math.cos(a) * 9, y + 16 + math.sin(a) * 9], fill="#fcd3de")
    x, y, w, h = c["sakura_mint"]
    blossom(d, x + w / 2 - 0.5, y + h / 2 - 0.5, 15.5, "#9fdcc4", "#5fae92", "#fbe7a8")
    for k in range(5):
        a = -math.pi / 2 + k * 2 * math.pi / 5
        d.line([x + 16 + math.cos(a) * 4, y + 16 + math.sin(a) * 4,
                x + 16 + math.cos(a) * 9, y + 16 + math.sin(a) * 9], fill="#d2f1e4")
    edition(d, *c["edition"])
    printed(d, *c["power"], "POWER", BLUSH, "#b4627d")
    printed(d, *c["reset"], "RESET", BLUSH, "#b4627d")
    pad_badge(im, d, *c["pad_badge"])
    face_button(d, *c["btn_a"], "#f3889f", "#ffffff", "A")
    face_button(d, *c["btn_b"], "#f6d77a", "#9a6a1e", "B")
    face_button(d, *c["btn_x"], "#9cc8f0", "#ffffff", "X")
    face_button(d, *c["btn_y"], "#93d8b9", "#ffffff", "Y")
    rear(d, *c["rear"])
    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    im.save(os.path.join(HERE, "art", "sakura_sheet.png"))
    with open(os.path.join(HERE, "art", "sakura_sheet.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1,
                   "cells": {k: list(v) for k, v in CELLS.items()}}, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
