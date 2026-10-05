"""Draws livery.png and livery.sheet.json beside this file: the train livery of shrine town's line
(the common set for its trains): a 1990s local EMU in stainless steel with the line's orange
(#e8782a, the colour of Yuyakedai's platform boards) as a belt under the windows and a pin
stripe over them, a black-masked cab front. Authored pixel art, drawn texel by texel; run once
and commit the outputs
(python3 carts/garden/shrinetown/assets/train_emu_car/art/draw_livery.py). Needs Pillow.

Texel sizes as train_emu_car maps them: the side 7.6 cm (255 x 32 for 19.5 x 2.45 m), the ends
7.3 cm (40 x 36 for 2.9 x 2.64 m). The side is drawn with the cab on the right (+X seen from
-Z); the recipe flips it for the other side. Window positions match the recipe's DOORS and
WINDOWS, which lay emissive glass over them at level 0."""
import json, os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 256, 128
sheet = Image.new('RGBA', (W, H), (0, 0, 0, 0))
cells = {}

ORANGE, ORANGE_D = '#e8782a', '#b85a1c'
STEEL, STEEL_L, STEEL_D, STEEL_DD = '#bcc2c6', '#d4d9dc', '#9aa1a6', '#7a8186'
GLASS, GLASS_L, RUBBER, BLACK = '#4e5e6c', '#6e8292', '#2a2c30', '#1c1d20'
WHITE, INK = '#f2f2ec', '#2c2a28'

# The car's side in metres (x along the car, cab at +x), as the recipe has them.
BODY_X = (-9.75, 9.75)
BODY_Y = (1.0, 3.45)
DOORS = [-6.3, 0.0, 6.3]                       # 1.3 m double-leaf doors, y 1.0..3.05
WINDOWS = [(-9.25, -7.45), (-5.25, -3.35), (-3.05, -1.05), (1.05, 3.05), (3.35, 5.25),
           (7.3, 8.2)]                         # y 1.95..2.95
CAB_DOOR = (8.45, 9.05)                        # crew door, its window y 2.0..2.8
CAB_WIN = (9.15, 9.5)


def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def h32(*v):
    x = 0x9E3779B9
    for n in v:
        x = ((x ^ (n & 0xFFFFFFFF)) * 0x85EBCA6B) & 0xFFFFFFFF
        x ^= x >> 13
    return x


class Cell:
    def __init__(self, name, x, y, w, h):
        cells[name] = [x, y, w, h]
        self.img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.pos, self.w, self.h = (x, y), w, h

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.img.putpixel((x, y), rgb(c))

    def rect(self, x0, y0, x1, y1, c):
        if x1 < x0 or y1 < y0:
            return
        self.d.rectangle([x0, y0, x1, y1], fill=rgb(c))

    def done(self):
        sheet.paste(self.img, self.pos)


# ---- the side: 255 x 32 for 19.5 x 2.45 m.
c = Cell('side', 0, 0, 255, 32)
SW, SH = 255, 32


def col(x):
    return round((x - BODY_X[0]) / (BODY_X[1] - BODY_X[0]) * SW)


def row(y):
    return round((BODY_Y[1] - y) / (BODY_Y[1] - BODY_Y[0]) * SH)


for y in range(SH):                              # stainless, faint vertical beads
    for x in range(SW):
        c.px(x, y, STEEL_L if x % 4 == 0 else (STEEL if h32(x, y) % 9 else STEEL_D))
c.rect(0, row(3.12), SW - 1, row(3.06), ORANGE)  # pin stripe over the windows
c.rect(0, row(1.85), SW - 1, row(1.56), ORANGE)  # the belt
c.rect(0, row(1.56) + 1, SW - 1, row(1.56) + 1, ORANGE_D)
c.rect(0, SH - 1, SW - 1, SH - 1, STEEL_DD)      # the sole bar's shadow
c.rect(0, 0, SW - 1, 0, STEEL_D)                 # the gutter
for x0, x1 in WINDOWS:                           # windows: rubber frame, glass, a highlight
    a, b = col(x0), col(x1)
    c.rect(a, row(2.95), b, row(1.95), RUBBER)
    c.rect(a + 1, row(2.95) + 1, b - 1, row(1.95) - 1, GLASS)
    c.rect(a + 1, row(2.95) + 1, b - 1, row(2.95) + 2, GLASS_L)
    if b - a > 12:                               # the sash bar of a big window
        m = (a + b) // 2
        c.rect(m, row(2.95), m, row(1.95), STEEL_D)
for xc in DOORS:                                 # doors: a frame, two leaves, two windows
    a, b = col(xc - 0.65), col(xc + 0.65)
    m = (a + b) // 2
    c.rect(a, row(3.05), b, SH - 1, STEEL_DD)
    c.rect(a + 1, row(3.05) + 1, b - 1, SH - 1, STEEL_L)
    c.rect(m, row(3.05), m, SH - 1, RUBBER)
    for l0, l1 in ((a + 2, m - 2), (m + 2, b - 2)):
        c.rect(l0, row(2.9), l1, row(2.0), RUBBER)
        c.rect(l0 + 1, row(2.9) + 1, l1 - 1, row(2.0) - 1, GLASS)
    c.rect(a + 1, row(1.85), b - 1, row(1.56), ORANGE)
a, b = col(CAB_DOOR[0]), col(CAB_DOOR[1])        # the crew door
c.rect(a, row(3.05), b, SH - 1, STEEL_DD)
c.rect(a + 1, row(3.05) + 1, b - 1, SH - 2, STEEL)
c.rect(a + 1, row(2.8), b - 1, row(2.0), GLASS)
c.rect(a + 1, row(1.85), b - 1, row(1.56), ORANGE)
a, b = col(CAB_WIN[0]), col(CAB_WIN[1])
c.rect(a, row(2.95), b, row(1.95), GLASS)
c.rect(col(-1.6), row(1.3), col(-1.0), row(1.3), INK)   # the car number
c.rect(col(1.0), row(1.3), col(1.6), row(1.3), INK)
c.done()

# ---- the cab front: 40 x 36 for 2.9 x 2.64 m (y 1.0..3.64). Black mask round the two
# windscreens, the destination and the run number over them, the belt across, lamps low.
c = Cell('cab', 0, 32, 40, 36)
c.rect(0, 0, 39, 35, STEEL)
for x in range(0, 40, 4):
    for y in range(36):
        c.px(x, y, STEEL_L)
c.rect(0, 0, 39, 1, STEEL_D)                     # roof edge
c.rect(2, 3, 37, 19, BLACK)                      # the mask
c.rect(4, 3, 35, 5, '#3a3a40')                   # destination box (lit at level 0)
c.rect(4, 7, 18, 18, GLASS)                      # driver's windscreen (left)
c.rect(21, 7, 35, 18, GLASS)
c.rect(4, 7, 18, 8, GLASS_L)
c.rect(21, 7, 35, 8, GLASS_L)
c.rect(18, 9, 21, 12, '#3a3a40')                 # the run number between
c.rect(0, 24, 39, 27, ORANGE)                    # the belt
c.rect(0, 28, 39, 28, ORANGE_D)
for x0 in (3, 33):                               # headlight and tail light, each side
    c.rect(x0, 30, x0 + 3, 32, '#f2f0d8')
    c.rect(x0 + (4 if x0 < 20 else -2), 30, x0 + (5 if x0 < 20 else -1), 32, '#a82018')
c.rect(17, 30, 22, 35, STEEL_DD)                 # coupler pocket
c.rect(0, 35, 39, 35, STEEL_DD)
c.done()

# ---- the other end (the gangway): 40 x 36. A narrow door with a window, the corrugated end,
# the belt broken by the gangway.
c = Cell('end', 40, 32, 40, 36)
c.rect(0, 0, 39, 35, STEEL)
for x in range(0, 40, 3):
    for y in range(36):
        c.px(x, y, STEEL_D)
c.rect(0, 0, 39, 1, STEEL_D)
c.rect(0, 24, 39, 27, ORANGE)
c.rect(12, 6, 27, 35, RUBBER)                    # the gangway's opening
c.rect(14, 8, 25, 35, STEEL_L)                   # its door
c.rect(16, 10, 23, 19, GLASS)
c.rect(3, 9, 8, 17, GLASS)                       # end windows
c.rect(31, 9, 36, 17, GLASS)
c.done()

# ---- a bogie's side frame: 32 x 12 for 2.6 x 0.95 m. Two wheels, the coil springs, the
# brake cylinders, all in shadow.
c = Cell('bogie', 80, 32, 32, 12)
c.rect(0, 0, 31, 11, '#3a3c40')
c.rect(0, 2, 31, 5, '#4a4d52')                   # the frame
for cx in (7, 24):
    c.d.ellipse([cx - 6, 2, cx + 6, 11], fill=rgb('#26272a'))
    c.d.ellipse([cx - 4, 4, cx + 4, 10], fill=rgb('#5a5d62'))
    c.d.ellipse([cx - 1, 6, cx + 1, 8], fill=rgb('#2a2b2e'))
for x in (14, 17):
    for y in range(1, 6):
        c.px(x, y, '#7a7d82' if y % 2 else '#2a2b2e')
c.done()

# ---- the roof air conditioner's top: 32 x 24 for 2.4 x 1.9 m. Two fan grilles in a grey
# casing.
c = Cell('ac', 112, 32, 32, 24)
c.rect(0, 0, 31, 23, '#a8aeb2')
c.rect(0, 0, 31, 0, '#c8ccd0')
for cx in (8, 23):
    c.d.ellipse([cx - 6, 5, cx + 6, 17], fill=rgb('#5e6468'))
    for k in range(-5, 6, 2):
        c.rect(cx - 5, 11 + k, cx + 5, 11 + k, '#3e4448')
    c.d.ellipse([cx - 1, 10, cx + 1, 12], fill=rgb('#a8aeb2'))
c.done()

# ---- underfloor equipment, the sides: 32 x 8 for about 4 x 0.55 m. Boxes, latches, a vent.
c = Cell('under', 144, 32, 32, 8)
c.rect(0, 0, 31, 7, '#4a4d52')
for x in (0, 9, 20):
    c.rect(x, 0, x, 7, '#2e3034')
for x in (4, 14, 26):
    c.px(x, 3, '#8a8e92')
for x in range(22, 31, 2):
    c.rect(x, 2, x, 5, '#2e3034')
c.done()

sheet.save(os.path.join(HERE, 'livery.png'))
with open(os.path.join(HERE, 'livery.sheet.json'), 'w') as f:
    f.write('{"format": "mei-sheet", "version": 1,\n "cells": {\n')
    f.write(',\n'.join(f'  "{k}": {json.dumps(v)}' for k, v in cells.items()))
    f.write('\n }}\n')
print('wrote livery.png', len(cells), 'cells')
