"""Draws concourse.png and concourse.sheet.json beside this file: Yuyakedai station's hall front
and stairs (station_concourse). Authored pixel art, drawn texel by texel; run once and commit
the outputs (python3 carts/garden/shrinetown/assets/station_concourse/art/draw_concourse.py).
Needs Pillow and macOS's Hiragino Sans for the lettering.

The line's colour is the orange of the platform's name board (station_platform, #e8782a). Texel
sizes as the recipe maps them: the wall tile and the floor 6.25 cm (16 a metre), the cladding
panels 6.25 cm (32 x 64 for 2 x 4 m), a stair step 16 texels, the signs 5 to 10 cm."""
import json, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
JP_FONT = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'
JP_BOLD = '/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc'

W, H = 256, 128
sheet = Image.new('RGBA', (W, H), (0, 0, 0, 0))
cells = {}

ORANGE, ORANGE_D = '#e8782a', '#b85a1c'
NAVY, INK, WHITE, CREAM = '#1e2838', '#2c2a28', '#f6f6f0', '#ece4d2'
STEEL, STEEL_D, STEEL_L = '#9ba3ac', '#5e6a72', '#c9ced0'
GREEN = '#4f7f6a'


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
        self.d.rectangle([x0, y0, x1, y1], fill=rgb(c))

    def text(self, s, x0, y0, w, h, size, c, font=JP_FONT, align='c'):
        """Lettering without antialiasing, centred (or left-aligned) in the box."""
        t = Image.new('L', (self.w, self.h), 0)
        td = ImageDraw.Draw(t)
        td.fontmode = '1'
        f = ImageFont.truetype(font, size)
        l, tp, r, b = td.textbbox((0, 0), s, font=f)
        x = x0 + (w - (r - l)) // 2 - l if align == 'c' else x0 - l
        y = y0 + (h - (b - tp)) // 2 - tp
        td.text((x, y), s, fill=255, font=f)
        for yy in range(self.h):
            for xx in range(self.w):
                if t.getpixel((xx, yy)) > 127:
                    self.px(xx, yy, c)

    def done(self):
        sheet.paste(self.img, self.pos)


# ---- the station's name over the hall: 96 x 24 for 9.6 x 2.4 m. White enamel board, the line's
# orange bar on the left as on the platform's boards, the name in black.
c = Cell('name_sign', 0, 0, 96, 24)
c.rect(0, 0, 95, 23, '#3a3a3c')
c.rect(1, 1, 94, 22, WHITE)
c.rect(1, 1, 6, 22, ORANGE)
c.text('夕焼台駅', 8, 1, 86, 22, 19, INK, JP_BOLD)
c.done()

# ---- the cladding over the hall (repeating, 2 x 4 m): cream enamel panels 1 m wide with dark
# joints, rain streaks from the deck's drip edge, the line's orange stripe and a grey plinth
# band at the foot (4 m down, the top of the ground floor's tile).
c = Cell('panel', 96, 0, 32, 64)
for y in range(64):
    for x in range(32):
        v = h32(x, y, 3) % 100
        col = '#e2dccb' if v < 70 else ('#d8d2c0' if v < 92 else '#eae5d6')
        c.px(x, y, col)
for x in (0, 16):
    for y in range(64):
        c.px(x, y, '#b0aa9a')
for y in (0, 21, 42):
    for x in range(32):
        c.px(x, y, '#c4bead')
for x in range(32):                              # rain streaks below the drip edge
    n = h32(x, 11) % 7
    for y in range(1, 2 + n * 2):
        if h32(x, y, 5) % 3:
            c.px(x, y, '#c8c1ae')
c.rect(0, 50, 31, 54, ORANGE)
c.rect(0, 55, 31, 55, ORANGE_D)
c.rect(0, 56, 31, 63, '#8e887c')
for x in range(32):
    if h32(x, 77) % 4 == 0:
        c.px(x, 57 + h32(x, 78) % 6, '#7a756a')
c.done()

# ---- the ground floor's wall tile (repeating, 1 x 1 m): brown 1990s mosaic, 4 x 4 tiles.
c = Cell('tile', 128, 0, 16, 16)
for y in range(16):
    for x in range(16):
        if x % 4 == 3 or y % 4 == 3:
            c.px(x, y, '#9a8670')
        else:
            v = h32(x // 4, y // 4, 9) % 5
            c.px(x, y, ['#b89a78', '#a88a6a', '#c2a684', '#b09070', '#a48464'][v])
c.done()

# ---- the hall's floor (repeating, 1 x 1 m): grey terrazzo slabs with a darker joint.
c = Cell('floor', 144, 0, 16, 16)
for y in range(16):
    for x in range(16):
        v = h32(x, y, 21) % 100
        c.px(x, y, '#a9a8a2' if v < 60 else ('#b9b8b0' if v < 85 else '#8e8d88'))
for i in range(16):
    c.px(i, 0, '#7e7d78')
    c.px(0, i, '#7e7d78')
c.done()

# ---- a stair step (repeating, one step a repeat along the slope): the riser in shade at the
# top, the yellow nosing, the tread.
c = Cell('tread', 160, 0, 16, 16)
for y in range(16):
    for x in range(16):
        if y < 6:
            col = '#8e8a82'
        elif y < 8:
            col = '#e0b830' if (x // 2) % 2 == 0 else '#c89c20'
        else:
            col = '#bcb8ae' if h32(x, y, 31) % 4 else '#aca89e'
        c.px(x, y, col)
c.done()

# ---- the coin lockers beside the entrance: 32 x 24 for 2.4 x 1.8 m. Three columns of
# doors, small at the top, big at the bottom, with keys and numbers.
c = Cell('lockers', 176, 0, 32, 24)
c.rect(0, 0, 31, 23, STEEL_D)
c.rect(1, 1, 30, 22, '#d2d6d4')
rows = [(1, 5), (6, 10), (11, 22)]
for col in range(3):
    x0 = 1 + col * 10
    for y0, y1 in rows:
        c.rect(x0, y0, x0 + 9, y1, '#aab2b4')
        c.rect(x0 + 1, y0 + 1, x0 + 8, y1 - 1, '#e6e8e4' if col != 1 else '#dfe3e6')
        c.px(x0 + 7, y0 + 2, '#e8782a')            # the key
        c.px(x0 + 2, y0 + 1, INK)
        c.px(x0 + 3, y0 + 1, INK)
c.rect(1, 22, 30, 22, '#7a8288')
c.done()

# ---- three ticket machines, fronts: 48 x 32 for 2.4 x 1.6 m. Fare buttons, the coin and note
# slots, the ticket tray, a lit price board.
c = Cell('machines', 208, 0, 48, 32)
for m in range(3):
    x0 = m * 16
    c.rect(x0, 0, x0 + 15, 31, '#c9ced0')
    c.rect(x0, 0, x0 + 15, 0, STEEL_D)
    c.rect(x0, 0, x0, 31, '#9ba3ac')
    c.rect(x0 + 2, 2, x0 + 13, 7, NAVY)        # the lit fare panel
    for i in range(4):
        c.px(x0 + 3 + i * 3, 4, '#f0c020')
        c.px(x0 + 3 + i * 3, 5, '#3be06a' if (i + m) % 2 else '#f6f6f0')
    for r in range(3):                           # buttons
        for i in range(4):
            c.rect(x0 + 3 + i * 3, 10 + r * 3, x0 + 4 + i * 3, 11 + r * 3,
                   '#e8782a' if r == 0 else '#f6f6f0')
    c.rect(x0 + 2, 20, x0 + 5, 21, INK)        # coin slot
    c.rect(x0 + 9, 20, x0 + 13, 20, INK)       # note slot
    c.rect(x0 + 3, 25, x0 + 12, 28, '#3a3a3c') # tray
    c.rect(x0 + 1, 30, x0 + 14, 31, '#8e9496')
c.done()

# ---- the fare chart over the machines: 64 x 24 for 3.2 x 1.2 m. The line as an orange bar
# across, stations as white dots, fares under them, the station itself in red.
c = Cell('fare_chart', 0, 24, 64, 24)
c.rect(0, 0, 63, 23, '#3a3a3c')
c.rect(1, 1, 62, 22, WHITE)
c.rect(1, 1, 62, 8, NAVY)
c.text('きっぷうりば', 1, 1, 62, 8, 7, WHITE)
c.rect(3, 13, 60, 14, ORANGE)
for i, x in enumerate(range(5, 60, 7)):
    c.rect(x, 12, x + 1, 15, '#c8262c' if i == 4 else INK)
    for k in range(2):
        c.px(x + k, 18, INK)
        c.px(x + k, 20, INK)
    c.px(x, 9, INK)
    c.px(x + 1, 10, INK)
c.done()

# ---- the way up to the platform, on the hall's back wall: 48 x 32 for 4 x 2.7 m. A stair
# rising into the light under a hanging "for the platform" sign.
c = Cell('way_up', 0, 64, 48, 32)
c.rect(0, 0, 47, 31, '#e2d8c0')
c.rect(4, 6, 43, 31, '#2c2a28')                 # the opening
for i in range(9):                               # steps rising away, lit from above
    y = 31 - i * 3
    shade = ['#8e8a82', '#9a968c', '#a6a296', '#b2ae a2'.replace(' ', ''), '#bcb8ae', '#c6c2b6',
             '#cfcbc0', '#d8d4ca', '#e0ddd4'][i]
    c.rect(6 + i, y - 2, 41 - i, y, shade)
    c.rect(6 + i, y - 2, 41 - i, y - 2, '#e0b830')
c.rect(15, 4, 32, 9, NAVY)                       # the sign
c.text('のりば', 15, 4, 18, 6, 6, WHITE)
c.rect(15, 4, 15, 9, ORANGE)
c.done()

# ---- the timetable: 24 x 32 for 1.2 x 1.6 m. A white board with hour rows, minutes in black
# and red.
c = Cell('timetable', 128, 16, 24, 32)
c.rect(0, 0, 23, 31, '#3a3a3c')
c.rect(1, 1, 22, 30, WHITE)
c.rect(1, 1, 22, 4, ORANGE)
for r in range(12):
    y = 6 + r * 2
    c.px(2, y, INK)
    c.px(3, y, INK)
    for k in range(4):
        if h32(r, k, 41) % 4:
            c.px(6 + k * 4, y, '#c8262c' if h32(r, k) % 5 == 0 else INK)
            c.px(7 + k * 4, y, INK)
c.done()

# ---- two posters, 16 x 24 for 0.6 x 0.9 m: autumn at the shrine (maples and the pagoda) and
# a travel poster for the sea.
c = Cell('poster_a', 152, 16, 16, 24)
c.rect(0, 0, 15, 23, '#f2e6cc')
c.rect(1, 1, 14, 15, '#e8a050')
for i in range(30):
    x, y = h32(i, 1) % 14 + 1, h32(i, 2) % 10 + 1
    c.px(x, y, '#c8301e' if i % 3 else '#e0502a')
c.rect(7, 6, 8, 15, INK)                         # the pagoda
for k, w in enumerate((4, 3, 2)):
    c.rect(7 - w, 8 + k * 3, 8 + w, 8 + k * 3, INK)
c.rect(2, 17, 13, 18, '#c8301e')
c.rect(2, 20, 10, 20, INK)
c.rect(2, 22, 8, 22, INK)
c.done()
c = Cell('poster_b', 168, 24, 16, 24)
c.rect(0, 0, 15, 23, WHITE)
c.rect(1, 1, 14, 9, '#8fc8e8')
c.rect(1, 10, 14, 15, '#3a6ab0')
c.d.ellipse([9, 2, 13, 6], fill=rgb('#f0c030'))
c.rect(1, 13, 14, 13, '#dce8f0')
c.rect(2, 17, 13, 18, '#3a6ab0')
c.rect(2, 20, 11, 20, INK)
c.rect(2, 22, 7, 22, ORANGE)
c.done()

# ---- the station office window: 32 x 16 for 2.4 x 1.2 m. Frosted glass with half-drawn
# blinds and the counter's small window.
c = Cell('office', 184, 32, 32, 16)
c.rect(0, 0, 31, 15, STEEL_D)
c.rect(1, 1, 30, 14, '#c8d4d8')
for y in range(1, 7):
    if y % 2:
        c.rect(1, y, 30, y, '#e6ece8')
c.rect(15, 1, 16, 14, STEEL_D)
c.rect(5, 9, 11, 14, '#8a9aa2')                  # the counter window
c.rect(20, 8, 27, 9, NAVY)                       # a notice
c.done()

# ---- the crossing over track 2 (fit, 2.4 x 3.6 m): rubber crossing panels between yellow and
# black edges.
c = Cell('crossing', 216, 32, 16, 24)
for y in range(24):
    for x in range(16):
        c.px(x, y, '#4a4a50' if h32(x, y, 51) % 5 else '#3e3e44')
for y in range(0, 24, 6):
    for x in range(16):
        c.px(x, y, '#38383e')
for y in range(24):
    for x in (0, 15):
        c.px(x, y, '#e0b830' if (y // 2) % 2 else INK)
c.done()

# ---- the sign over the entrance: 64 x 12 for 4 x 0.75 m.
c = Cell('entrance_sign', 0, 48, 64, 12)
c.rect(0, 0, 63, 11, NAVY)
c.rect(0, 0, 2, 11, ORANGE)
c.text('きっぷ・のりば', 3, 0, 60, 12, 8, WHITE)
c.done()

# ---- the clock on the cladding (disc, 1 m across): white face, black hands at ten to six.
c = Cell('clock', 64, 48, 16, 16)
c.d.ellipse([0, 0, 15, 15], fill=rgb('#3a3a3c'))
c.d.ellipse([1, 1, 14, 14], fill=rgb(WHITE))
for a in range(12):
    import math
    x = 7.5 + 5.6 * math.sin(a * math.pi / 6)
    y = 7.5 - 5.6 * math.cos(a * math.pi / 6)
    c.px(round(x), round(y), INK)
c.d.line([7, 7, 7, 12], fill=rgb(INK))
c.d.line([7, 7, 3, 5], fill=rgb(INK))
c.done()

sheet.save(os.path.join(HERE, 'concourse.png'))
with open(os.path.join(HERE, 'concourse.sheet.json'), 'w') as f:
    f.write('{"format": "mei-sheet", "version": 1,\n "cells": {\n')
    f.write(',\n'.join(f'  "{k}": {json.dumps(v)}' for k, v in cells.items()))
    f.write('\n }}\n')
print('wrote concourse.png', len(cells), 'cells')
