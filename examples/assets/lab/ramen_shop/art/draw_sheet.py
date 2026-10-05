"""Draws ramen_sheet.png and ramen_sheet.sheet.json, the ramen shop's painted textures.

Authored art: run once with Pillow (python3 draw_sheet.py) and commit the PNG. It uses the
macOS Hiragino fonts for the signs' lettering; nothing else rewrites the sheet.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GOTHIC = '/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc'
ROUND = '/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc'

CELLS = {
    'kanban':   (0, 0, 64, 16),
    'noren':    (64, 0, 48, 24),
    'tate':     (112, 0, 16, 64),
    'doors':    (0, 24, 32, 32),
    'case':     (32, 24, 32, 16),
    'vend':     (64, 24, 16, 32),
    'window':   (80, 24, 32, 24),
    'flatdoor': (0, 64, 16, 32),
    'menu':     (16, 64, 16, 24),
    'laundry':  (32, 64, 32, 16),
    'fan':      (64, 64, 16, 16),
    'backwin':  (80, 64, 16, 16),
}

sheet = Image.new('RGBA', (128, 96), (0, 0, 0, 0))


def cell(name):
    x, y, w, h = CELLS[name]
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def put(name, img):
    x, y, w, h = CELLS[name]
    sheet.paste(img, (x, y))


def text(d, xy, s, size, fill, font=GOTHIC, anchor='mm'):
    d.fontmode = '1'
    d.text(xy, s, font=ImageFont.truetype(font, size), fill=fill, anchor=anchor)


# Kanban: the shop's name, 福来軒 (Fukuraiken), white on lacquer red with a gold rule.
img, d = cell('kanban')
d.rectangle([0, 0, 63, 15], fill='#a51e22')
d.rectangle([0, 0, 63, 15], outline='#e2b33c')
d.rectangle([1, 1, 62, 14], outline='#6e1014')
for i, ch in enumerate('福来軒'):
    text(d, (14 + i * 18, 8), ch, 13, '#fff6e0')
d.point([(5, 7), (5, 8), (58, 7), (58, 8)], fill='#e2b33c')
put('kanban', img)

# Noren: indigo, four panels split by slits, らーめん in white; a band across the top.
img, d = cell('noren')
d.rectangle([0, 0, 47, 23], fill='#26346b')
d.rectangle([0, 0, 47, 2], fill='#1a2450')
for i, ch in enumerate('らーめん'):
    text(d, (6 + i * 12, 13), ch, 11, '#f4f1ea', font=ROUND)
for sx in (11, 23, 35):
    d.line([(sx, 6), (sx, 23)], fill=(0, 0, 0, 0))
put('noren', img)

# Tate kanban: the vertical sign, 中華そば in red on cream, lit from inside.
img, d = cell('tate')
d.rectangle([0, 0, 15, 63], fill='#fff4d6')
d.rectangle([0, 0, 15, 63], outline='#c4302b')
for i, ch in enumerate('中華そば'):
    text(d, (8, 8 + i * 15), ch, 13, '#c4302b')
put('tate', img)

# Doors: two sliding doors, wooden frames, lattice glass glowing warm.
img, d = cell('doors')
d.rectangle([0, 0, 31, 31], fill='#5a3a22')
for x0 in (1, 16):
    d.rectangle([x0 + 1, 1, x0 + 13, 22], fill='#f2d08a')
    d.line([(x0 + 1, 8), (x0 + 13, 8)], fill='#7a5432')
    d.line([(x0 + 1, 15), (x0 + 13, 15)], fill='#7a5432')
    d.line([(x0 + 7, 1), (x0 + 7, 22)], fill='#7a5432')
    d.rectangle([x0 + 1, 24, x0 + 13, 30], fill='#6e4a2c')
    d.line([(x0 + 1, 27), (x0 + 13, 27)], fill='#4a2e1a')
# Silhouettes of a customer at the counter behind the glass.
d.rectangle([5, 10, 7, 14], fill='#c89a5a')
d.rectangle([4, 15, 8, 22], fill='#b4884e')
d.point([(15, 20), (16, 20)], fill='#3a2414')
# 営業中 (open) plate hanging on the left door.
d.rectangle([20, 3, 25, 6], fill='#f6f0e0')
d.line([(21, 4), (24, 4)], fill='#a51e22')
d.line([(21, 5), (23, 5)], fill='#a51e22')
put('doors', img)

# Case: the plastic food sample window; ramen, gyoza, a beer, a maneki-neko.
img, d = cell('case')
d.rectangle([0, 0, 31, 15], fill='#d8d4c8')
d.rectangle([1, 1, 30, 14], fill='#3c3a44')
d.line([(1, 8), (30, 8)], fill='#9a9aa4')
d.rectangle([1, 14, 30, 14], fill='#9a9aa4')
for cx in (5, 13):  # two bowls of ramen
    d.pieslice([cx - 4, 3, cx + 4, 11], 0, 180, fill='#c4302b')
    d.rectangle([cx - 3, 6, cx + 3, 7], fill='#f0c060')
    d.point([(cx - 1, 6), (cx + 2, 6)], fill='#f6f0e0')
    d.point([(cx + 1, 5)], fill='#4a8a3a')
d.ellipse([3, 10, 11, 13], fill='#f0ece0')  # gyoza plate
for gx in (5, 7, 9):
    d.point([(gx, 11), (gx, 12)], fill='#d89a50')
d.rectangle([17, 2, 18, 7], fill='#e8b030')  # beer glass
d.rectangle([17, 2, 18, 2], fill='#fff8e8')
d.rectangle([14, 10, 20, 13], fill='#e8e0d0')  # chashu don
d.rectangle([15, 10, 19, 11], fill='#a0502a')
# Maneki-neko, waving.
d.rectangle([24, 6, 29, 13], fill='#fbfaf4')
d.rectangle([24, 4, 28, 8], fill='#fbfaf4')
d.point([(24, 3), (28, 3)], fill='#fbfaf4')
d.point([(25, 6), (27, 6)], fill='#202020')
d.rectangle([24, 9, 28, 9], fill='#d02a2a')
d.point([(26, 10)], fill='#f0c040')
d.rectangle([29, 3, 30, 6], fill='#fbfaf4')
put('case', img)

# Vend: a drinks machine, white with a blue band, two rows of cans, lit.
img, d = cell('vend')
d.rectangle([0, 0, 15, 31], fill='#f2f4f6')
d.rectangle([0, 0, 15, 4], fill='#1f5fb4')
d.line([(2, 2), (13, 2)], fill='#f2f4f6')
d.rectangle([1, 6, 14, 17], fill='#dfe8f0')
cans = ['#d02a2a', '#2a8a3a', '#e8b030', '#3a3a8a', '#e86020', '#8a5a2a', '#2a9ac0']
for row, y in enumerate((7, 12)):
    for i in range(6):
        c = cans[(i + row * 3) % len(cans)]
        d.rectangle([2 + i * 2, y, 2 + i * 2, y + 3], fill=c)
    d.line([(2, y + 4), (13, y + 4)], fill='#e02020' if row == 0 else '#20a040')
d.rectangle([2, 19, 7, 21], fill='#20242a')
d.point([(3, 20), (5, 20)], fill='#40e060')
d.rectangle([10, 19, 12, 22], fill='#b0b4bc')
d.rectangle([2, 25, 13, 29], fill='#20242a')
d.line([(0, 31), (15, 31)], fill='#9aa0a8')
put('vend', img)

# Window: the flat's aluminium sash, lace curtains half drawn, a cactus on the sill.
img, d = cell('window')
d.rectangle([0, 0, 31, 23], fill='#b8bcc0')
d.rectangle([1, 1, 30, 22], fill='#4a5a74')
d.rectangle([1, 1, 15, 22], fill='#56688a')
d.line([(15, 1), (15, 22)], fill='#d8dce0')
d.line([(16, 1), (16, 22)], fill='#8a9094')
for x in range(1, 10):
    d.line([(x, 1), (x, 22)], fill='#f2e2e6' if x % 2 else '#e2ccd2')
for x in range(24, 31):
    d.line([(x, 1), (x, 22)], fill='#f2e2e6' if x % 2 else '#e2ccd2')
d.rectangle([10, 3, 14, 20], fill='#f4dca0')  # lamp-lit room through the gap
d.rectangle([17, 3, 23, 20], fill='#ecd090')
d.rectangle([11, 4, 13, 7], fill='#fff4c8')
d.rectangle([18, 17, 20, 21], fill='#b05a30')  # cactus in a pot
d.rectangle([19, 13, 19, 17], fill='#3a7a3a')
d.point([(18, 14), (20, 15)], fill='#3a7a3a')
d.line([(1, 22), (30, 22)], fill='#d8dce0')
put('window', img)

# Flat door: a beige steel apartment door, number 201, knob, newspaper slot.
img, d = cell('flatdoor')
d.rectangle([0, 0, 15, 31], fill='#8a8478')
d.rectangle([1, 1, 14, 31], fill='#d6ccb4')
d.rectangle([2, 2, 13, 29], outline='#c2b89e')
d.rectangle([5, 5, 10, 7], fill='#f4f0e4')
d.point([(6, 6), (8, 6), (9, 6)], fill='#303030')
d.rectangle([5, 19, 10, 20], fill='#6a6458')
d.rectangle([11, 15, 12, 16], fill='#e0c060')
put('flatdoor', img)

# Menu: an A-frame chalkboard, today's menu in chalk.
img, d = cell('menu')
d.rectangle([0, 0, 15, 23], fill='#8a5a32')
d.rectangle([1, 1, 14, 22], fill='#26402e')
d.rectangle([3, 2, 12, 4], fill='#f0e8c8')
d.line([(4, 3), (11, 3)], fill='#26402e')
for y, w, c in ((7, 9, '#e8e4d8'), (10, 7, '#e8e4d8'), (13, 10, '#f0c060'),
                (16, 6, '#e8e4d8'), (19, 8, '#f08a8a')):
    d.line([(3, y), (3 + w, y)], fill=c)
d.point([(12, 10), (12, 16)], fill='#e8e4d8')
put('menu', img)

# Laundry: a T-shirt, a striped towel and socks on the line; the rest is a hole.
img, d = cell('laundry')
d.line([(0, 0), (31, 0)], fill='#8a8a8a')
d.rectangle([2, 1, 11, 4], fill='#e8eef8')
d.rectangle([4, 1, 9, 12], fill='#e8eef8')
d.rectangle([5, 4, 8, 6], fill='#4a7ac0')
d.rectangle([14, 1, 21, 13], fill='#f0a040')
for y in (3, 6, 9, 12):
    d.line([(14, y), (21, y)], fill='#f6e6c0')
d.rectangle([24, 1, 25, 6], fill='#d84a6a')
d.rectangle([24, 6, 26, 7], fill='#d84a6a')
d.rectangle([28, 1, 29, 6], fill='#d84a6a')
d.rectangle([28, 6, 30, 7], fill='#d84a6a')
for x in (3, 10, 15, 20, 24, 29):
    d.point([(x, 1)], fill='#f0d040')
put('laundry', img)

# Fan: the air conditioner's outdoor fan grille.
img, d = cell('fan')
d.rectangle([0, 0, 15, 15], fill='#e4e2da')
d.ellipse([1, 1, 14, 14], fill='#5a5e64')
for r in (6, 4, 2):
    d.ellipse([7.5 - r, 7.5 - r, 7.5 + r, 7.5 + r], outline='#9aa0a6')
d.line([(1, 7), (14, 7)], fill='#9aa0a6')
d.line([(7, 1), (7, 14)], fill='#9aa0a6')
d.rectangle([6, 6, 9, 9], fill='#c8ccd0')
put('fan', img)

# Backwin: a frosted kitchen window with a steel grille.
img, d = cell('backwin')
d.rectangle([0, 0, 15, 15], fill='#a8acb0')
d.rectangle([1, 1, 14, 14], fill='#d4dcd8')
d.rectangle([2, 2, 13, 13], fill='#e4ecd8')
for x in (4, 8, 12):
    d.line([(x, 0), (x, 15)], fill='#5a5e64')
d.line([(0, 7), (15, 7)], fill='#5a5e64')
put('backwin', img)

sheet.save(os.path.join(HERE, 'ramen_sheet.png'))
with open(os.path.join(HERE, 'ramen_sheet.sheet.json'), 'w') as f:
    f.write('{\n  "format": "mei-sheet",\n  "version": 1,\n  "cells": {\n')
    f.write(',\n'.join('    "%s": [%d, %d, %d, %d]' % ((k,) + v) for k, v in CELLS.items()))
    f.write('\n  }\n}\n')
