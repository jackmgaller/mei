"""Draws gantry.png and gantry.sheet.json beside this file: the signal gantry's galvanised lattice
girder, its grating walkway, the handrail and ladder (cutouts) and the signal heads' faces.
Authored pixel art; run once and commit the outputs
(python3 carts/garden/shrinetown/assets/signal_gantry/art/draw_gantry.py). Needs Pillow."""
import json, os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 128, 48
sheet = Image.new('RGBA', (W, H), (0, 0, 0, 0))
cells = {}
STEEL, STEEL_L, STEEL_D, STEEL_DD = '#9ba3ac', '#c0c6cc', '#7a828a', '#4e555c'
BLACK, YELLOW = '#2c2a28', '#e0b830'


def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


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
        self.d.rectangle([x0, y0, x1, y1], fill=rgb(c))

    def done(self):
        sheet.paste(self.img, self.pos)


# ---- the girder's sides: 64 x 8 for 11.3 x 0.3 m (chords and a Warren lattice, the walkway's
# toe board above it in safety yellow).
c = Cell('truss', 0, 0, 64, 8)
c.rect(0, 0, 63, 7, STEEL_DD)
c.rect(0, 0, 63, 1, YELLOW)
c.rect(0, 2, 63, 2, STEEL_L)
c.rect(0, 7, 63, 7, STEEL_D)
for x in range(0, 64, 4):
    for k in range(4):
        c.px(x + k, 3 + k if (x // 4) % 2 == 0 else 6 - k, STEEL)
c.done()

# ---- the walkway's grating from above: 64 x 8 for 11.3 x 1.2 m.
c = Cell('grating', 0, 8, 64, 8)
c.rect(0, 0, 63, 7, STEEL_D)
for x in range(0, 64, 2):
    c.rect(x, 1, x, 6, STEEL_L)
c.rect(0, 0, 63, 0, STEEL)
c.rect(0, 7, 63, 7, STEEL)
c.done()

# ---- the handrail (cutout): 32 x 8 for 2.1 x 1.0 m. Top rail, knee rail, posts.
c = Cell('rail', 0, 16, 32, 8)
c.rect(0, 0, 31, 0, YELLOW)
c.rect(0, 4, 31, 4, STEEL)
for x in (0, 15, 31):
    c.rect(x, 0, x, 7, STEEL_L)
c.done()

# ---- the ladder (cutout): 8 x 32 for 0.45 x 4.4 m.
c = Cell('ladder', 64, 0, 8, 32)
c.rect(0, 0, 0, 31, STEEL_L)
c.rect(7, 0, 7, 31, STEEL_L)
for y in range(1, 32, 2):
    c.rect(1, y, 6, y, STEEL)
c.done()

# ---- a signal head's face: 8 x 20 for 0.35 x 0.9 m. Three lamps in hoods on black, the
# backboard's white rim; the green lamp is lit by an emissive decal at level 0.
c = Cell('signal', 72, 0, 8, 20)
c.rect(0, 0, 7, 19, '#e8e6de')
c.rect(1, 1, 6, 18, BLACK)
for k, col in enumerate(('#7a2018', '#7a6a18', '#1a5a30')):
    y = 2 + k * 6
    c.rect(2, y, 5, y + 3, col)
    c.rect(1, y - 1, 6, y - 1, '#4a4846')
c.done()

sheet.save(os.path.join(HERE, 'gantry.png'))
with open(os.path.join(HERE, 'gantry.sheet.json'), 'w') as f:
    f.write('{"format": "mei-sheet", "version": 1,\n "cells": {\n')
    f.write(',\n'.join(f'  "{k}": {json.dumps(v)}' for k, v in cells.items()))
    f.write('\n }}\n')
print('wrote gantry.png', len(cells), 'cells')
