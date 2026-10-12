#!/usr/bin/env python3
"""Draws art/komainu.png and art/komainu.sheet.json, the komainu's carved details, texel by
texel (python3 art/draw_komainu.py; needs Pillow).

Cells, each drawn once (`fit`) on one face:
  face      32 x 24  the head's front: bulging eyes under curled brows, cheek curls
  snout_un  24 x 16  the closed mouth's muzzle: a broad nose, shut lips, two fangs up
  snout_a   24 x 8   the open mouth's upper jaw: the nose and a row of teeth, fangs down
  jaw_a     16 x 8   the open mouth's lower jaw: teeth and fangs up
  mane      32 x 32  rows of snail-shell curls, for the mane and the tail
"""
import json, os
from PIL import Image

here = os.path.dirname(os.path.abspath(__file__))

LIGHT = (200, 194, 178)
BASE = (180, 174, 158)
MID = (142, 136, 124)
DARK = (106, 102, 94)
BLACK = (44, 42, 40)
WHITE = (214, 208, 192)
MOSS = (122, 128, 80)

W, H = 64, 48
img = Image.new("RGB", (W, H), BASE)
px = img.load()


def put(x, y, c, ox, oy, w, h):
    if 0 <= x < w and 0 <= y < h:
        px[ox + x, oy + y] = c


def fill(ox, oy, w, h, c):
    for y in range(h):
        for x in range(w):
            px[ox + x, oy + y] = c


def mottle(ox, oy, w, h, seed, colours):
    """Sparse deterministic flecks, as weathered stone."""
    for y in range(h):
        for x in range(w):
            v = ((x + ox) * 73856093 ^ (y + oy) * 19349663 ^ seed * 83492791) & 0xFFFF
            if v % 23 == 0:
                px[ox + x, oy + y] = colours[0]
            elif v % 41 == 1 and len(colours) > 1:
                px[ox + x, oy + y] = colours[1]


def disc(cx, cy, r, c, ox, oy, w, h):
    for y in range(h):
        for x in range(w):
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r:
                put(x, y, c, ox, oy, w, h)


def ring(cx, cy, r0, r1, c, ox, oy, w, h):
    for y in range(h):
        for x in range(w):
            d = (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2
            if r0 * r0 <= d <= r1 * r1:
                put(x, y, c, ox, oy, w, h)


def curl(cx, cy, ox, oy, w, h, fg=LIGHT, edge=DARK, eye=DARK):
    """A snail-shell curl: a light round knob, dark rim below and right, a dark spiral dot."""
    disc(cx, cy, 3.4, edge, ox, oy, w, h)
    disc(cx - 0.4, cy - 0.4, 2.8, fg, ox, oy, w, h)
    put(int(cx), int(cy), eye, ox, oy, w, h)
    put(int(cx) - 1, int(cy), MID, ox, oy, w, h)
    put(int(cx), int(cy) - 1, MID, ox, oy, w, h)


cells = {}

# --- face (0, 0) 32 x 24 -------------------------------------------------------------------
ox, oy, w, h = 0, 0, 32, 24
cells["face"] = [ox, oy, w, h]
fill(ox, oy, w, h, BASE)
mottle(ox, oy, w, h, 1, [LIGHT, MID])
for ex in (8, 24):
    # bulging eye: dark socket, pale ball, black pupil looking ahead
    disc(ex, 8.5, 4.6, DARK, ox, oy, w, h)
    disc(ex, 8.5, 3.6, WHITE, ox, oy, w, h)
    disc(ex + (0.6 if ex < 16 else -0.6), 9.0, 1.6, BLACK, ox, oy, w, h)
    # heavy brow over it, curling up at the outer end
    for x in range(ex - 6, ex + 6):
        put(x, 2, LIGHT, ox, oy, w, h)
        put(x, 3, MID, ox, oy, w, h)
    outer = ex - 6 if ex < 16 else ex + 5
    step = -1 if ex < 16 else 1
    put(outer, 1, LIGHT, ox, oy, w, h)
    put(outer + step, 1, DARK, ox, oy, w, h)
    put(outer + step, 0, LIGHT, ox, oy, w, h)
# the frown between the brows
for y in range(2, 7):
    put(15, y, DARK, ox, oy, w, h)
    put(16, y, DARK, ox, oy, w, h)
# cheek curls beside the muzzle (the muzzle covers the middle of rows 12 and down)
for cx, cy in ((3, 16), (3.5, 21.5), (28.5, 16), (28, 21.5)):
    curl(cx, cy, ox, oy, w, h)

# --- mane (32, 0) 32 x 32 ------------------------------------------------------------------
ox, oy, w, h = 32, 0, 32, 32
cells["mane"] = [ox, oy, w, h]
fill(ox, oy, w, h, MID)
mottle(ox, oy, w, h, 2, [DARK, MOSS])
for row in range(5):
    for col in range(5):
        cx = col * 7 + (3.5 if row % 2 == 0 else 0) + 0.5
        cy = row * 7 + 3.5
        curl(cx, cy, ox, oy, w, h)

# --- snout_un (0, 24) 24 x 16 --------------------------------------------------------------
ox, oy, w, h = 0, 24, 24, 16
cells["snout_un"] = [ox, oy, w, h]
fill(ox, oy, w, h, BASE)
mottle(ox, oy, w, h, 3, [LIGHT, MID])
# broad flat nose
for y in range(1, 7):
    half = 4 + min(y, 3)
    for x in range(12 - half, 12 + half):
        put(x, y, MID if y < 5 else DARK, ox, oy, w, h)
for x in range(8, 16):
    put(x, 1, LIGHT, ox, oy, w, h)
for nx in (8, 9, 14, 15):
    put(nx, 5, BLACK, ox, oy, w, h)
# shut lips: a black line turning down at the corners
for x in range(3, 21):
    put(x, 11, BLACK, ox, oy, w, h)
for x, y in ((2, 12), (21, 12), (1, 13), (22, 13)):
    put(x, y, BLACK, ox, oy, w, h)
for x in range(4, 20):
    put(x, 12, DARK, ox, oy, w, h)
# fangs up over the upper lip
for fx in (6, 17):
    put(fx, 9, WHITE, ox, oy, w, h)
    put(fx, 10, WHITE, ox, oy, w, h)
    put(fx + 1, 10, WHITE, ox, oy, w, h)

# --- snout_a (0, 40) 24 x 8 ----------------------------------------------------------------
ox, oy, w, h = 0, 40, 24, 8
cells["snout_a"] = [ox, oy, w, h]
fill(ox, oy, w, h, BASE)
mottle(ox, oy, w, h, 4, [LIGHT, MID])
for y in range(0, 4):
    half = 5 + min(y, 2)
    for x in range(12 - half, 12 + half):
        put(x, y, MID if y < 3 else DARK, ox, oy, w, h)
for nx in (8, 9, 14, 15):
    put(nx, 3, BLACK, ox, oy, w, h)
# upper teeth along the bottom edge, fangs at the corners
for x in range(2, 22):
    put(x, 6, WHITE if x % 3 else DARK, ox, oy, w, h)
    put(x, 7, WHITE if x % 3 else BLACK, ox, oy, w, h)
for fx in (3, 20):
    put(fx, 5, WHITE, ox, oy, w, h)

# --- jaw_a (32, 32) 16 x 8 -----------------------------------------------------------------
ox, oy, w, h = 32, 32, 16, 8
cells["jaw_a"] = [ox, oy, w, h]
fill(ox, oy, w, h, BASE)
mottle(ox, oy, w, h, 5, [LIGHT, MID])
for x in range(1, 15):
    put(x, 0, WHITE if x % 3 else BLACK, ox, oy, w, h)
    put(x, 1, WHITE if x % 3 else DARK, ox, oy, w, h)
for fx in (2, 13):
    put(fx, 2, WHITE, ox, oy, w, h)
    put(fx, 3, WHITE, ox, oy, w, h)
for x in range(0, 16):
    put(x, 7, MID, ox, oy, w, h)

img.save(os.path.join(here, "komainu.png"))
with open(os.path.join(here, "komainu.sheet.json"), "w") as f:
    json.dump({"format": "mei-sheet", "version": 1, "cells": cells}, f, indent=1)
    f.write("\n")
