"""Draws art/sheet.png and art/sheet.sheet.json for the fire engine (authored art, run once).

Needs Pillow and macOS's Hiragino Sans GB:
python3 examples/assets/lab/fire_engine/art/draw_sheet.py

The side and rear pictures are drawn in metres: each maps the face of the recipe's mesh it is
on (the hand UVs span the whole picture), so wheel arches and lockers land where the wheels are.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc', 12, index=1)

RED, DRED, WHITE = '#c8202a', '#86141e', '#f2f0e8'
SILVER, SILVER_D, BLACK = '#c4c8cc', '#868c94', '#1c1c22'
GLASS, GLASS_HI, AMBER = '#2e4660', '#7f9fbf', '#f0a020'

CELLS = {}
sheet = Image.new('RGBA', (256, 128), (0, 0, 0, 0))
cursor = {'x': 0, 'y': 0, 'row_h': 0}


def place(name, img):
    if cursor['x'] + img.width > sheet.width:
        cursor['x'], cursor['y'], cursor['row_h'] = 0, cursor['y'] + cursor['row_h'], 0
    sheet.paste(img, (cursor['x'], cursor['y']))
    CELLS[name] = [cursor['x'], cursor['y'], img.width, img.height]
    cursor['x'] += img.width
    cursor['row_h'] = max(cursor['row_h'], img.height)


def mapper(w, h, x0, x1, y_top, y_bottom):
    """Metres to pixels for a picture spanning x0..x1 (left to right) and y_top..y_bottom."""
    def p(x, y):
        return (round((x - x0) / (x1 - x0) * w), round((y_top - y) / (y_top - y_bottom) * h))
    return p


def shutter(d, p, x0, x1, y0, y1):
    a, b = p(x0, y1), p(x1, y0)
    d.rectangle([a, b], fill=SILVER, outline=SILVER_D)
    for y in range(a[1] + 2, b[1], 2):
        d.line([a[0] + 1, y, b[0] - 1, y], fill=SILVER_D)
    d.rectangle([(a[0] + b[0]) // 2 - 2, b[1] - 2, (a[0] + b[0]) // 2 + 1, b[1] - 1], fill=BLACK)


# Cab side, front to the left: door and window, the white line, the front wheel's arch.
w, h = 48, 56
img = Image.new('RGB', (w, h), RED)
d = ImageDraw.Draw(img)
p = mapper(w, h, -3.0, -1.5, 2.42, 0.72)
d.polygon([p(-2.80, 2.22), p(-1.80, 2.22), p(-1.80, 1.62), p(-2.92, 1.62)], fill=GLASS)
d.line([p(-2.55, 2.18), p(-2.80, 1.68)], fill=GLASS_HI, width=2)
d.line([p(-2.25, 2.18), p(-2.38, 1.92)], fill=GLASS_HI)
d.line([p(-2.84, 2.30), p(-1.74, 2.30), p(-1.74, 0.96), p(-2.98, 0.96)], fill=DRED)
d.rectangle([p(-1.95, 1.52), p(-1.84, 1.48)], fill=SILVER)
d.rectangle([p(-3.0, 0.92), p(-1.5, 0.86)], fill=WHITE)
d.ellipse([p(-2.2 - 0.5, 0.42 + 0.5), p(-2.2 + 0.5, 0.42 - 0.5)], fill=BLACK)
d.rectangle([p(-1.62, 0.84), p(-1.52, 0.80)], fill=AMBER)
place('cab_side', img)

# Cab front: a friendly face. Round lamps, a grille, the town's badge, the plate.
w, h = 64, 24
img = Image.new('RGB', (w, h), RED)
d = ImageDraw.Draw(img)
d.rectangle([0, 15, 63, 16], fill=WHITE)
for cx in (9, 54):
    d.ellipse([cx - 5, 3, cx + 5, 13], fill=SILVER_D)
    d.ellipse([cx - 4, 4, cx + 4, 12], fill='#fff6c8')
    d.point([cx - 2, 6], fill=WHITE)
d.rectangle([0, 4, 2, 12], fill=AMBER)
d.rectangle([61, 4, 63, 12], fill=AMBER)
d.rectangle([18, 4, 45, 12], fill=BLACK)
for y in (5, 7, 9, 11):
    d.line([19, y, 44, y], fill=SILVER)
d.ellipse([29, 1, 34, 6], fill='#e8c040', outline='#a07818')
d.rectangle([24, 18, 39, 23], fill=WHITE, outline='#2a6a3a')
d.line([27, 21, 36, 21], fill='#2a6a3a')
place('cab_front', img)

# Windshield: a frame, two wipers, a sky highlight.
w, h = 32, 16
img = Image.new('RGB', (w, h), GLASS)
d = ImageDraw.Draw(img)
d.rectangle([0, 0, 31, 15], outline=BLACK)
d.line([4, 3, 10, 12], fill=GLASS_HI, width=2)
d.line([13, 3, 16, 8], fill=GLASS_HI)
d.line([7, 14, 14, 11], fill=BLACK)
d.line([18, 14, 25, 11], fill=BLACK)
place('windshield', img)

# Body side, front to the left: lockers with roller shutters, the rear wheel's arch, lamps.
w, h = 128, 40
img = Image.new('RGB', (w, h), RED)
d = ImageDraw.Draw(img)
p = mapper(w, h, -1.45, 2.6, 2.05, 0.72)
d.rectangle([p(-1.45, 2.05), p(2.6, 1.99)], fill=DRED)
shutter(d, p, -1.32, -0.08, 0.98, 1.9)
shutter(d, p, 0.04, 1.02, 0.98, 1.9)
shutter(d, p, 2.12, 2.48, 0.98, 1.9)
d.rectangle([p(-1.45, 0.92), p(2.6, 0.86)], fill=WHITE)
d.ellipse([p(1.6 - 0.5, 0.42 + 0.5), p(1.6 + 0.5, 0.42 - 0.5)], fill=BLACK)
for z in (-1.0, 0.5, 2.3):
    d.rectangle([p(z - 0.05, 0.82), p(z + 0.05, 0.77)], fill=AMBER)
place('body_side', img)

# Rear: a shutter, tail lamps, the plate.
w, h = 64, 40
img = Image.new('RGB', (w, h), RED)
d = ImageDraw.Draw(img)
p = mapper(w, h, -0.95, 0.95, 2.05, 0.72)
d.rectangle([p(-0.95, 2.05), p(0.95, 1.99)], fill=DRED)
shutter(d, p, -0.7, 0.7, 1.15, 1.9)
d.rectangle([p(-0.95, 0.92), p(0.95, 0.86)], fill=WHITE)
for x in (-0.86, 0.72):
    d.rectangle([p(x, 1.06), p(x + 0.14, 0.94)], fill='#ff3a2a', outline=DRED)
d.rectangle([p(-0.18, 1.08), p(0.18, 0.95)], fill=WHITE, outline='#2a6a3a')
place('rear', img)

# The town's name, painted on the doors (a cutout: only the letters are drawn).
img = Image.new('RGBA', (52, 14), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.fontmode = '1'
d.text((2, 0), 'メイ消防', font=FONT, fill=WHITE)
place('decal', img)

# Light bar, two frames: the lamps take turns.
for name, (left, right) in (('bar_a', ('#ff4a3a', '#7a1010')), ('bar_b', ('#7a1010', '#ff4a3a'))):
    img = Image.new('RGB', (32, 8), BLACK)
    d = ImageDraw.Draw(img)
    d.rectangle([1, 1, 12, 6], fill=left)
    d.rectangle([19, 1, 30, 6], fill=right)
    d.rectangle([13, 2, 18, 5], fill=SILVER)
    d.point([3, 2], fill=WHITE if left == '#ff4a3a' else left)
    d.point([21, 2], fill=WHITE if right == '#ff4a3a' else right)
    place(name, img)

# Wheel, face on: tyre, rim, hub and its nuts.
img = Image.new('RGB', (16, 16), BLACK)
d = ImageDraw.Draw(img)
d.ellipse([3, 3, 12, 12], fill=SILVER)
d.ellipse([5, 5, 10, 10], fill=SILVER_D)
d.rectangle([7, 7, 8, 8], fill=SILVER)
place('wheel', img)

sheet = sheet.crop((0, 0, sheet.width, cursor['y'] + cursor['row_h']))
sheet.save(os.path.join(HERE, 'sheet.png'))
with open(os.path.join(HERE, 'sheet.sheet.json'), 'w') as f:
    json.dump({'format': 'mei-sheet', 'version': 1, 'cells': CELLS}, f, indent=1)
    f.write('\n')
