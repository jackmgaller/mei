#!/usr/bin/env python3
"""Draws town_signs.png and town_signs.sheet.json, the sign sheet of the shrine town.

Authored art: run once with Pillow (python3 draw_signs.py) and commit the PNG. Lettering uses
the macOS Hiragino fonts, drawn without antialiasing so 8-bit textures keep it crisp. Several
props reuse the sheet (town_kanban_set, town_road_signs, town_taxi_rank, the shopfronts): add
cells at the end of CELLS and leave existing ones alone. Each recipe packs only the cells it uses.
Texels are about 1.5 to 2.5 cm at the size the prop uses them.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GOTHIC = '/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc'
BOLD = '/System/Library/Fonts/ヒラギノ角ゴシック W9.ttc'

# name: (width, height). Packed left to right in shelves, in this order.
CELLS = {
    # town_kanban_set
    'aframe':  (40, 56),   # A-frame menu board, chalk on green
    'cafe':    (24, 56),   # lit pole sign, 喫茶
    'soba':    (56, 16),   # hanging wooden board, 手打そば
    # town_road_signs
    'tomare':  (48, 42),   # 止まれ, point down
    'speed30': (32, 32),   # 最高速度 30
    'school':  (32, 32),   # 学校あり (yellow diamond)
    # town_taxi_rank
    'taxi':    (64, 32),   # lit rank sign, タクシーのりば
    # for other props
    'cross':   (32, 32),   # 横断歩道 (blue square)
    'noentry': (32, 32),   # 進入禁止
    'nopark':  (32, 32),   # 駐車禁止
    'detour':  (64, 24),   # 工事中 with hazard stripes
}
SHEET_W = 160
PAD = 1

cells = {}


def new(name):
    w, h = CELLS[name]
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.fontmode = '1'
    return img, d


def text(d, xy, s, size, fill, font=GOTHIC, anchor='mm'):
    d.text(xy, s, font=ImageFont.truetype(font, size), fill=fill, anchor=anchor)


CHALK, CHALK_Y = '#ece4d2', '#f0c030'

# A-frame: lacquered wood frame, green board, chalk lettering, a rice bowl.
img, d = new('aframe')
d.rectangle([0, 0, 39, 55], fill='#8a6446')
d.rectangle([0, 0, 39, 55], outline='#5a3e2c')
d.rectangle([3, 3, 36, 52], fill='#24382a')
d.rectangle([3, 3, 36, 52], outline='#3c5a34')
text(d, (20, 11), '本日の', 11, CHALK)
text(d, (20, 25), 'ランチ', 12, CHALK_Y, BOLD)
d.line([(6, 33), (33, 33)], fill=CHALK)
text(d, (20, 40), '750円', 10, CHALK)
d.pieslice([13, 41, 27, 53], 0, 180, fill=CHALK)           # bowl
d.line([(11, 47), (29, 47)], fill=CHALK)
cells['aframe'] = img

# Cafe: warm white lit box, red 喫茶 stacked, a cup.
img, d = new('cafe')
d.rectangle([0, 0, 23, 55], fill='#c8301e')
d.rectangle([2, 2, 21, 53], fill='#f6f0d8')
text(d, (12, 14), '喫', 17, '#b02a1a', BOLD)
text(d, (12, 32), '茶', 17, '#b02a1a', BOLD)
d.rectangle([6, 44, 16, 51], fill='#6a4632')              # cup
d.rectangle([7, 45, 15, 46], fill='#c89a6a')
d.arc([14, 45, 19, 50], 270, 90, fill='#6a4632')
d.line([(5, 52), (18, 52)], fill='#8a6446')
d.point([(9, 41), (12, 40), (10, 39)], fill='#b4ae9e')    # steam
cells['cafe'] = img

# Soba: dark wood board, brush-white lettering, a pale rim.
img, d = new('soba')
d.rectangle([0, 0, 55, 15], fill='#3a2a22')
d.rectangle([0, 0, 55, 15], outline='#8a6446')
d.rectangle([1, 1, 54, 14], outline='#5a3e2c')
text(d, (28, 8), '手打そば', 12, '#f2ead4', BOLD)
cells['soba'] = img

# Tomare: red inverted triangle, white band, red field, white lettering.
img, d = new('tomare')
tri = [(0, 0), (47, 0), (23.5, 41)]
cx, cy = 23.5, 13.7


def inset(k):
    return [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in tri]


d.polygon(tri, fill='#d8301e')
d.polygon(inset(0.86), fill='#f4f1e6')
d.polygon(inset(0.76), fill='#d8301e')
text(d, (23.5, 10), '止まれ', 9, '#f4f1e6', BOLD)
cells['tomare'] = img

# 30 km/h: red ring, white face, black numerals.
img, d = new('speed30')
d.ellipse([0, 0, 31, 31], fill='#d8301e')
d.ellipse([5, 5, 26, 26], fill='#f4f1e6')
text(d, (16, 16), '30', 14, '#1c1c20', BOLD)
cells['speed30'] = img

# School zone: yellow diamond, black rim, a pair of children.
img, d = new('school')
d.polygon([(15.5, 0), (31, 15.5), (15.5, 31), (0, 15.5)], fill='#1c1c20')
d.polygon([(15.5, 2), (29, 15.5), (15.5, 29), (2, 15.5)], fill='#f0c030')
for x, h in ((11, 12), (20, 9)):                          # tall child, small child
    top = 23 - h
    d.rectangle([x - 1, top - 3, x + 1, top - 1], fill='#1c1c20')     # head
    d.rectangle([x - 1, top, x + 1, top + h - 5], fill='#1c1c20')     # body
    d.line([(x - 1, top + h - 5), (x - 2, 23)], fill='#1c1c20')       # legs
    d.line([(x + 1, top + h - 5), (x + 2, 23)], fill='#1c1c20')
    d.line([(x - 3, top + 3), (x - 1, top + 1)], fill='#1c1c20')      # arms
    d.line([(x + 3, top + 3), (x + 1, top + 1)], fill='#1c1c20')
d.line([(14, 14), (17, 14)], fill='#1c1c20')                          # held hands
cells['school'] = img

# Taxi rank: blue lit sign, a yellow cab, タクシー / のりば.
img, d = new('taxi')
d.rectangle([0, 0, 63, 31], fill='#f4f1e6')
d.rectangle([1, 1, 62, 30], fill='#1f4e9c')
d.rounded_rectangle([3, 8, 20, 24], 3, fill='#f6d94a')    # the cab, side on
d.rectangle([7, 5, 15, 8], fill='#f4f1e6')                # roof lamp
d.rectangle([6, 11, 17, 15], fill='#bfe3f0')
d.ellipse([5, 22, 9, 26], fill='#1c1c20')
d.ellipse([14, 22, 18, 26], fill='#1c1c20')
text(d, (42, 10), 'タクシー', 11, '#f4f1e6', BOLD)
text(d, (36, 23), 'のりば', 11, '#f6d94a', BOLD)
d.polygon([(55, 18), (60, 23), (55, 28)], fill='#f6d94a')  # arrow
cells['taxi'] = img

# Pedestrian crossing: blue square, white triangle, a walker.
img, d = new('cross')
d.rounded_rectangle([0, 0, 31, 31], 3, fill='#f4f1e6')
d.rounded_rectangle([1, 1, 30, 30], 3, fill='#1f55a8')
d.polygon([(16, 5), (28, 26), (4, 26)], fill='#f4f1e6')
d.ellipse([15, 11, 17, 13], fill='#1f55a8')
d.line([(16, 14), (16, 19)], fill='#1f55a8')
d.line([(16, 19), (13, 23)], fill='#1f55a8')
d.line([(16, 19), (19, 23)], fill='#1f55a8')
d.line([(16, 15), (13, 18)], fill='#1f55a8')
d.line([(16, 15), (19, 17)], fill='#1f55a8')
cells['cross'] = img

# No entry.
img, d = new('noentry')
d.ellipse([0, 0, 31, 31], fill='#d8301e')
d.rectangle([5, 13, 26, 18], fill='#f4f1e6')
cells['noentry'] = img

# No parking: blue disc, red rim and slash.
img, d = new('nopark')
d.ellipse([0, 0, 31, 31], fill='#d8301e')
d.ellipse([4, 4, 27, 27], fill='#1f55a8')
for off in (-1, 0, 1):
    d.line([(7 + off, 24), (24 + off, 7)], fill='#d8301e')
    d.line([(7 + off, 7), (24 + off, 24)], fill='#d8301e')
cells['nopark'] = img

# Road works board: yellow, black hazard bars, 工事中.
img, d = new('detour')
d.rectangle([0, 0, 63, 23], fill='#f0c030')
d.rectangle([0, 0, 63, 23], outline='#1c1c20')
for x in range(-8, 72, 8):
    d.polygon([(x, 1), (x + 4, 1), (x + 0, 5), (x - 4, 5)], fill='#1c1c20')
    d.polygon([(x, 18), (x + 4, 18), (x + 0, 22), (x - 4, 22)], fill='#1c1c20')
text(d, (32, 12), '工事中', 11, '#1c1c20', BOLD)
cells['detour'] = img

# Pack in shelves.
x = y = shelf = 0
layout = {}
for name, (w, h) in CELLS.items():
    if x + w > SHEET_W:
        x, y, shelf = 0, y + shelf + PAD, 0
    layout[name] = (x, y, w, h)
    x += w + PAD
    shelf = max(shelf, h)
sheet_h = y + shelf
sheet = Image.new('RGBA', (SHEET_W, sheet_h), (0, 0, 0, 0))
for name, (cx, cy, w, h) in layout.items():
    sheet.paste(cells[name], (cx, cy))
sheet.save(os.path.join(HERE, 'town_signs.png'))
with open(os.path.join(HERE, 'town_signs.sheet.json'), 'w') as f:
    json.dump({'format': 'mei-sheet', 'version': 1,
               'cells': {k: list(v) for k, v in layout.items()}}, f, indent=1)
print(SHEET_W, sheet_h)
