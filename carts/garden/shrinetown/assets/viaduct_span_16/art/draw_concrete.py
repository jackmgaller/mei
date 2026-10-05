"""Draws concrete.png and concrete.sheet.json beside this file: the common concrete set of the
shrine town (the viaduct family's textures, shared with every city level): weathered concrete
with form-panel joints and tie holes, the viaduct's precast parapet face with rain streaks, the
ballasted double track, the cable-trough walkway, and the small things of an underpass (the
bridge's name plate, a pier number plate, two posters). Authored pixel art,
drawn texel by texel; run once and commit the outputs
(python3 carts/garden/shrinetown/assets/viaduct_span_16/art/draw_concrete.py). Needs Pillow
and macOS's Hiragino Sans for the name plate.

Texel sizes as the viaduct recipes map them: along the viaduct 12.5 cm (32 texels a 4 m repeat,
16 a 2 m one, so a 16 m face is 128 texels and never split), across 5 to 6.25 cm."""
import json, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
JP_FONT = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'

W, H = 128, 80
sheet = Image.new('RGBA', (W, H), (0, 0, 0, 0))
cells = {}


def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def h32(*v):
    """A small deterministic hash for scattering texels."""
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
        self.img.putpixel((x % self.w, y % self.h), rgb(c))

    def rect(self, x0, y0, x1, y1, c):
        self.d.rectangle([x0, y0, x1, y1], fill=rgb(c))

    def done(self):
        sheet.paste(self.img, self.pos)


# Concrete greys (Street concrete #c8c4b8 is the lit top; walls read a step darker).
C_BASE, C_LIGHT, C_DARK, C_JOINT, C_HOLE = '#b4b0a6', '#bfbbb1', '#a8a49a', '#96928a', '#6e6a62'
GRIME_1, GRIME_2, RUST = '#9a968c', '#86827a', '#8a7058'


def speckle(c, seed, base=C_BASE, light=C_LIGHT, dark=C_DARK):
    for y in range(c.h):
        for x in range(c.w):
            k = h32(x, y, seed) % 16
            c.px(x, y, light if k < 3 else dark if k < 6 else base)


# Blotches: soft patches of a darker or lighter tone, so a 4 m repeat does not read as a grid.
def blotch(c, seed, colour, count, rmax=4):
    for i in range(count):
        cx, cy, r = h32(seed, i, 1) % c.w, h32(seed, i, 2) % c.h, 2 + h32(seed, i, 3) % (rmax - 1)
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r - 2, cx + r + 3):
                d2 = ((x - cx) / 1.6) ** 2 + (y - cy) ** 2
                if d2 <= r * r and h32(x, y, seed, i) % 3:
                    c.px(x, y, colour)


# ---- wall: cast concrete, 4 m along x 2 m (32 x 32): faint form joints every 2 m and 1 m, two
# tie holes a panel (the Japanese "P-con" marks), blotches
c = Cell('wall', 0, 0, 32, 32)
speckle(c, 1)
blotch(c, 11, C_DARK, 3)
blotch(c, 12, C_LIGHT, 2)
for y in range(32):
    c.px(0, y, C_DARK)
    c.px(16, y, C_DARK)
for x in range(32):
    c.px(x, 0, C_DARK)
    c.px(x, 16, C_DARK)
for (x, y) in ((5, 8), (11, 8), (21, 24), (27, 24), (5, 24), (27, 8)):
    c.px(x, y, C_JOINT)
c.done()

# ---- soffit: the deck's underside, the same concrete darker and damp, 4 m x 2 m (32 x 32)
c = Cell('soffit', 0, 32, 32, 32)
speckle(c, 8, base='#a29e94', light='#aaa69c', dark='#98948a')
blotch(c, 13, '#8e8a80', 4, 5)
blotch(c, 14, '#aaa69c', 2)
for y in range(32):
    c.px(0, y, '#8e8a80')
for x in range(32):
    c.px(x, 0, '#96928a')
    c.px(x, 16, '#96928a')
for x in range(1, 32, 9):                        # efflorescence along a joint
    c.px(x, 1, '#c2beb4')
c.done()

# ---- fascia: the viaduct's outer face, 4 m along x 1.65 m tall (32 x 32, top row at the
# parapet's top, 10.2 m). Precast parapet panels 2 m long, the drip groove at the deck's level
# (row 23, 9.0 m), the slab edge below, rain streaks from the coping and from the groove.
c = Cell('fascia', 32, 0, 32, 32)
speckle(c, 2)
for x in range(32):
    c.px(x, 0, C_LIGHT)
    c.px(x, 22, GRIME_1)
    c.px(x, 23, C_HOLE)
    c.px(x, 24, C_LIGHT)
for y in range(1, 23):
    c.px(0, y, C_JOINT)
    c.px(16, y, C_JOINT)
for x in range(1, 32):                           # streaks under the coping
    if x in (0, 16):
        continue
    n = h32(x, 7) % 13
    if n > 4:
        for y in range(1, 1 + n):
            c.px(x, y, GRIME_2 if y < n // 2 + 1 else GRIME_1)
for x in range(32):                              # streaks under the drip groove
    n = h32(x, 9) % 7
    for y in range(25, 25 + n):
        c.px(x, y, GRIME_1 if (y - 25) > 1 else GRIME_2)
for y in range(1, 9):                            # one rust run from a fixing
    c.px(23, y, RUST if y < 5 else GRIME_2)
c.done()

# ---- track: one ballasted track, 2 m along (u) x 4 m across (v) (16 x 64): concrete bed at the
# edges, ballast, a PC sleeper every 0.5 m, rails 1.0 m apart (narrow gauge) with bright heads
c = Cell('track', 64, 0, 16, 64)
BED, BALLAST = ['#a8a49a', '#9e9a90'], ['#8a8276', '#7a7266', '#968e82', '#6e665c']
for y in range(64):
    for x in range(16):
        k = h32(x, y, 3)
        if y < 8 or y > 55:
            c.px(x, y, BED[k % 5 == 0])
        else:
            c.px(x, y, BALLAST[k % 4] if k % 23 else '#7a5a44')
for x0 in (0, 4, 8, 12):
    for x in (x0, x0 + 1):
        for y in range(17, 47):
            c.px(x, y, '#bcb8ae' if x == x0 else '#aaa69c')
for y in (23, 39):
    for x in range(16):
        c.px(x, y, '#d4d4d0')
        c.px(x, y + 1, '#4a3a30')
c.done()

# ---- trough: the walkway beside the track, 2 m along x 1.75 m across (16 x 16), from the track
# (v 0) to the parapet: plain concrete, then the cable trough's cover slabs, 0.5 m each
c = Cell('trough', 80, 0, 16, 16)
speckle(c, 4, base='#aca89e', light='#b4b0a6', dark='#a29e94')
for y in range(4, 12):
    for x in range(16):
        c.px(x, y, '#c4c0b6' if h32(x, y, 5) % 6 else '#b8b4aa')
for x in (0, 4, 8, 12):
    for y in range(4, 12):
        c.px(x, y, C_JOINT)
for x in range(16):
    c.px(x, 4, C_JOINT)
    c.px(x, 11, C_DARK)
c.done()

# ---- pier plate: the viaduct's pier number, white enamel, 16 x 8 for 0.32 x 0.16 m
c = Cell('pier_plate', 80, 16, 16, 8)
c.rect(0, 0, 15, 7, '#2c2a28')
c.rect(1, 1, 14, 6, '#eceae4')
DIG = {'R': ['110', '101', '110', '101', '101'], '2': ['111', '001', '111', '100', '111'],
       '7': ['111', '001', '010', '010', '010']}
for i, ch in enumerate('R27'):
    for yy, row in enumerate(DIG[ch]):
        for xx, bit in enumerate(row):
            if bit == '1':
                c.px(2 + i * 4 + xx, 1 + yy, '#2c2a28')
c.done()

# ---- name plate: the bridge's name, 宮前架道橋 (Miyamae road bridge), 64 x 16 for 2.4 x 0.6 m
c = Cell('name_plate', 0, 64, 64, 16)
c.rect(0, 0, 63, 15, '#3a3a3c')
c.rect(1, 1, 62, 14, '#eceae4')
txt = Image.new('L', (64, 16), 0)
td = ImageDraw.Draw(txt)
td.fontmode = '1'
font = ImageFont.truetype(JP_FONT, 12)
s = '宮前架道橋'
l, t, r, b = td.textbbox((0, 0), s, font=font)
td.text(((64 - (r - l)) // 2 - l, (16 - (b - t)) // 2 - t), s, fill=255, font=font)
for y in range(16):
    for x in range(64):
        if txt.getpixel((x, y)) > 127:
            c.px(x, y, '#2c2a28')
c.done()

# ---- posters: two bills pasted on the underpass wall, 16 x 24 for 0.6 x 0.9 m. A festival
# poster (red, the shrine's autumn festival) and a police notice (white and blue).
c = Cell('poster_a', 96, 0, 16, 24)
c.rect(0, 0, 15, 23, '#ece4d2')
c.rect(0, 0, 15, 6, '#c8301e')
for x in range(2, 14, 2):
    c.px(x, 2, '#ece4d2')
    c.px(x, 4, '#ece4d2')
c.d.ellipse([3, 8, 12, 17], fill=rgb('#f0c030'))
c.d.ellipse([5, 10, 10, 15], fill=rgb('#e0502a'))
for y in (19, 21):
    for x in range(2, 14):
        if h32(x, y, 6) % 4:
            c.px(x, y, '#2c2a28')
c.done()

c = Cell('poster_b', 112, 0, 16, 24)
c.rect(0, 0, 15, 23, '#eceae4')
c.rect(0, 0, 15, 5, '#3a6ab0')
for x in range(2, 14):
    if h32(x, 8) % 3:
        c.px(x, 2, '#eceae4')
for y in range(8, 20, 2):
    for x in range(2, 14 if y < 18 else 9):
        if h32(x, y, 7) % 5:
            c.px(x, y, '#2c2a28')
c.rect(2, 20, 6, 22, '#c8301e')
for y in range(24):                              # weathered: the lower corner peeling
    if y > 18:
        c.px(15, y, '#b4b0a6')
c.done()

sheet.save(os.path.join(HERE, 'concrete.png'))
with open(os.path.join(HERE, 'concrete.sheet.json'), 'w') as f:
    f.write('{"format": "mei-sheet", "version": 1,\n "cells": {\n')
    f.write(',\n'.join(f'  "{k}": {json.dumps(v)}' for k, v in cells.items()))
    f.write('\n }}\n')
print('wrote', os.path.join(HERE, 'concrete.png'), len(cells), 'cells')
