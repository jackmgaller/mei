#!/usr/bin/env python3
"""Draw art/kodomo.png and art/kodomo.sheet.json, the Kodomo Toy look's texture sheet.

Each cell is drawn at 8x, scaled down and snapped to a small palette of its own, so the
sheet is clean pixel art that the Asset Kit keeps exactly (no median cut).
Needs Pillow and two macOS fonts (Hiragino Maru Gothic, Arial Rounded Bold).
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ART = HERE / "art"
MARU = "/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc"
ROUND = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
SS = 8  # supersampling

CREAM = (242, 230, 200)
CREAM_D = (222, 206, 170)
TOMATO = (224, 64, 44)
TOMATO_D = (176, 44, 30)
DARK = (58, 44, 40)
WHITE = (255, 252, 244)
SUN = (255, 166, 58)
MOON = (168, 202, 240)
SKY = (120, 190, 235)
SKY_L = (176, 220, 245)
GRASS = (110, 186, 84)
GRASS_D = (76, 150, 66)


def hex6(c):
    return "#%02x%02x%02x" % c


def snap(img, palette):
    """Scale the 8x drawing down: each pixel takes the palette colour that most of its 8x8
    block is nearest to, so edges stay hard and no in-between colours appear."""
    w, h = img.size[0] // SS, img.size[1] // SS
    src = img.convert("RGB").load()
    out = Image.new("RGB", (w, h))
    po = out.load()
    near = {}
    for y in range(h):
        for x in range(w):
            votes = {}
            for j in range(SS):
                for i in range(SS):
                    c = src[x*SS + i, y*SS + j]
                    if c not in near:
                        near[c] = min(palette, key=lambda p: sum((a-b)**2 for a, b in zip(p, c)))
                    votes[near[c]] = votes.get(near[c], 0) + 1
            po[x, y] = max(votes, key=votes.get)
    return out


def canvas(w, h, bg):
    img = Image.new("RGB", (w * SS, h * SS), bg)
    return img, ImageDraw.Draw(img)


def glyph_mask(ch, font_path, size, stroke=0):
    font = ImageFont.truetype(font_path, size)
    box = font.getbbox(ch, stroke_width=stroke)
    m = Image.new("L", (box[2] - box[0] + 4, box[3] - box[1] + 4), 0)
    ImageDraw.Draw(m).text((2 - box[0], 2 - box[1]), ch, font=font, fill=255,
                           stroke_width=stroke, stroke_fill=255)
    return m


def paste_mei(img, cx, cy, size, outline=WHITE):
    """明 with the 日 in sun orange and the 月 in moon blue, outlined, centred at (cx, cy)."""
    stroke = size // 48
    body = glyph_mask("明", MARU, size, stroke)
    halo = glyph_mask("明", MARU, size, stroke + size // 24)
    # The 日 ends at the first empty column a third of the way across.
    w, h = body.size
    cols = [sum(body.getpixel((x, y)) for y in range(h)) for x in range(w)]
    split = min(range(w // 4, w // 2), key=lambda x: cols[x])
    ox, oy = cx - halo.size[0] // 2, cy - halo.size[1] // 2
    img.paste(outline, (ox, oy), halo)
    dx = ox + (halo.size[0] - w) // 2
    dy = oy + (halo.size[1] - h) // 2
    left = body.copy()
    left.paste(0, (split, 0, w, h))
    right = body.copy()
    right.paste(0, (0, 0, split, h))
    img.paste(SUN, (dx, dy), left)
    img.paste(MOON, (dx, dy), right)


def text_centre(d, xy, s, font_path, size, fill, stroke=0, stroke_fill=None):
    font = ImageFont.truetype(font_path, size)
    d.text(xy, s, font=font, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=stroke_fill)


def logo(w=64, h=32):
    img, d = canvas(w, h, TOMATO)
    S = SS
    d.rounded_rectangle((2*S, 2*S, (w-2)*S, (h-2)*S), radius=6*S, outline=CREAM, width=S)
    paste_mei(img, 16*S, 16*S, 27*S, outline=DARK)
    text_centre(d, (44*S, 16*S + S // 2), "MEI", ROUND, 15*S, WHITE)
    return snap(img, [TOMATO, CREAM, WHITE, SUN, MOON, DARK])


def small_logo(w=32, h=16):
    img, d = canvas(w, h, TOMATO)
    paste_mei(img, 8*SS, 8*SS, 14*SS, outline=DARK)
    text_centre(d, (23*SS, 8*SS + SS // 2), "MEI", ROUND, 8*SS, WHITE)
    return snap(img, [TOMATO, WHITE, SUN, MOON, DARK])


def power(n=32):
    """The power button: a red disc with a cream sun."""
    img, d = canvas(n, n, TOMATO)
    S, c = SS, n * SS / 2
    d.ellipse((c - 6*S, c - 6*S, c + 6*S, c + 6*S), fill=CREAM)
    import math
    for k in range(8):
        a = k * math.pi / 4
        x0, y0 = c + 8.5*S*math.cos(a), c + 8.5*S*math.sin(a)
        x1, y1 = c + 12*S*math.cos(a), c + 12*S*math.sin(a)
        d.line((x0, y0, x1, y1), fill=CREAM, width=int(2.4*S))
    return snap(img, [TOMATO, CREAM])


def reset(n=32):
    """The reset button: a cream disc with a red crescent moon."""
    img, d = canvas(n, n, CREAM)
    S, c = SS, n * SS / 2
    d.ellipse((c - 10*S, c - 10*S, c + 10*S, c + 10*S), fill=TOMATO)
    d.ellipse((c - 5*S, c - 13*S, c + 13*S, c + 5*S), fill=CREAM)
    return snap(img, [TOMATO, CREAM])


def port(num, w=32, h=16):
    """A controller port's face: a dark socket in the red surround, its number beside it."""
    img, d = canvas(w, h, TOMATO)
    S = SS
    d.rounded_rectangle((1*S, 2*S, 19*S, 14*S), radius=4*S, fill=DARK)
    for k in range(3):
        d.rounded_rectangle(((4 + k*5)*S, 7*S, (6 + k*5)*S, 9*S), radius=S, fill=CREAM_D)
    d.ellipse((20*S, 1*S, 32*S, 15*S), fill=CREAM)
    text_centre(d, (26*S, 8*S + S // 2), str(num), ROUND, 12*S, TOMATO)
    return snap(img, [TOMATO, DARK, CREAM, CREAM_D])


def cart_label(w=64, h=32):
    """The game in the slot: 'おひさま' (Mr Sun), a smiling sun over green hills."""
    img, d = canvas(w, h, SKY)
    S = SS
    d.rectangle((0, 16*S, w*S, h*S), fill=SKY_L)
    d.ellipse((40*S, 3*S, 60*S, 23*S), fill=SUN)
    d.ellipse((45*S, 10*S, 47*S, 12*S), fill=DARK)
    d.ellipse((53*S, 10*S, 55*S, 12*S), fill=DARK)
    d.arc((45*S, 11*S, 55*S, 19*S), 25, 155, fill=DARK, width=S)
    d.ellipse((-16*S, 20*S, 36*S, 52*S), fill=GRASS_D)
    d.ellipse((20*S, 22*S, 84*S, 56*S), fill=GRASS)
    d.rounded_rectangle((2*S, 2*S, 38*S, 15*S), radius=4*S, fill=CREAM)
    text_centre(d, (20*S, 8*S + S // 2), "おひさま", MARU, 9*S, TOMATO, stroke=S // 2, stroke_fill=TOMATO)
    return snap(img, [SKY, SKY_L, GRASS, GRASS_D, SUN, DARK, CREAM, TOMATO])


def face_button(letter, bg, fg, n=32):
    img, d = canvas(n, n, bg)
    text_centre(d, (n/2*SS, n/2*SS + SS), letter, ROUND, 19*SS, fg)
    return snap(img, [bg, fg])


def main():
    cells = [
        ("logo", logo()), ("logo_small", small_logo()),
        ("power", power()), ("reset", reset()),
        ("port1", port(1)), ("port2", port(2)),
        ("cart_label", cart_label()),
        ("btn_a", face_button("A", TOMATO, CREAM)), ("btn_b", face_button("B", TOMATO, CREAM)),
        ("btn_x", face_button("X", CREAM, TOMATO)), ("btn_y", face_button("Y", CREAM, TOMATO)),
    ]
    sheet = Image.new("RGB", (256, 64), (0, 0, 0))
    rects, x, y, row_h = {}, 0, 0, 0
    for name, im in cells:
        if x + im.width > sheet.width:
            x, y, row_h = 0, y + row_h, 0
        sheet.paste(im, (x, y))
        rects[name] = [x, y, im.width, im.height]
        x += im.width
        row_h = max(row_h, im.height)
    ART.mkdir(exist_ok=True)
    sheet.save(ART / "kodomo.png")
    (ART / "kodomo.sheet.json").write_text(json.dumps(
        {"format": "mei-sheet", "version": 1, "cells": rects}, indent=1) + "\n")


if __name__ == "__main__":
    main()
