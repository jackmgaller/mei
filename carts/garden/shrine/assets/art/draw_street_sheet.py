"""Draws street_sheet.png and street_sheet.sheet.json beside this file: the street family's
textures (konbini, vending machine, the mid-rise, utility pole, road-works barrier). Authored
pixel art, drawn texel by texel; run once and commit the outputs
(python3 carts/garden/shrine/assets/art/draw_street_sheet.py). Needs Pillow and macOS's Hiragino
Sans for the road-works sign."""
import json, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
JP_FONT = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'

W, H = 128, 176
sheet = Image.new('RGBA', (W, H), (0, 0, 0, 0))
cells = {}


def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def cell(name, x, y, w, h):
    cells[name] = [x, y, w, h]
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    return img, (x, y)


def rect(d, x0, y0, x1, y1, c):
    """Fill texels x0..x1, y0..y1 inclusive."""
    d.rectangle([x0, y0, x1, y1], fill=rgb(c))


def put(img, pos):
    sheet.paste(img, pos)


def h32(*v):
    """A small deterministic hash for scattering texels."""
    x = 0x9E3779B9
    for n in v:
        x = ((x ^ (n & 0xFFFFFFFF)) * 0x85EBCA6B) & 0xFFFFFFFF
        x ^= x >> 13
    return x


# ---- konbini: the lit shop window, one 4 m x 2.25 m bay (repeats along the front)
img, pos = cell('shopfront', 0, 0, 64, 32)
d = ImageDraw.Draw(img)
INSIDE, CEIL, SHELF, FRAME = '#f6f4ea', '#ffffff', '#b8b8b0', '#4e5660'
GOODS = ['#d8462a', '#f0c030', '#3a6ab0', '#40a060', '#e8782a', '#e070a0', '#8a2418']
rect(d, 0, 0, 63, 31, INSIDE)
rect(d, 0, 1, 63, 1, CEIL)                       # fluorescent tubes
for x in range(4, 64, 16):
    rect(d, x, 2, x + 9, 2, CEIL)
for row, top in enumerate((5, 10, 15)):          # back shelves with goods
    rect(d, 2, top + 3, 61, top + 3, SHELF)
    for x in range(2, 62):
        k = h32(x // 2, row) % 9
        if k < 7 and (x % 2 == 0 or k < 4):
            rect(d, x, top, x, top + 2 if k % 3 else top + 1, GOODS[k])
for x in range(1, 63):                           # magazine rack along the glass
    k = h32(x // 3, 7) % 7
    rect(d, x, 21, x, 26, GOODS[k] if x % 3 else INSIDE)
    rect(d, x, 22, x, 22, INSIDE if x % 3 == 0 else '#ffffff')
rect(d, 0, 27, 63, 27, SHELF)                    # the rack's edge
rect(d, 0, 28, 63, 31, '#d8d4c8')                # floor seen through the glass
rect(d, 0, 0, 0, 31, FRAME)                      # mullion every 4 m
rect(d, 0, 0, 63, 0, FRAME)                      # head of the glazing
put(img, pos)

# ---- konbini: the sign over the door (no real brand: a three-stripe mark and 24H)
img, pos = cell('kon_sign', 64, 0, 64, 16)
d = ImageDraw.Draw(img)
rect(d, 0, 0, 63, 15, '#fbfaf4')
rect(d, 0, 0, 63, 0, '#3a6ab0')
rect(d, 0, 15, 63, 15, '#3a6ab0')
for i, c in enumerate(('#3a6ab0', '#40a060', '#e8782a')):   # the mark
    rect(d, 4 + i * 4, 3, 6 + i * 4, 12, c)
GLYPHS = {
    '2': ['111', '001', '111', '100', '111'],
    '4': ['101', '101', '111', '001', '001'],
    'H': ['101', '101', '111', '101', '101'],
}
x = 22
for ch in '24H':
    for gy, line in enumerate(GLYPHS[ch]):
        for gx, b in enumerate(line):
            if b == '1':
                rect(d, x + gx * 2, 3 + gy * 2, x + gx * 2 + 1, 4 + gy * 2, '#3a6ab0')
    x += 9
for gx in range(50, 61):                          # a green leaf for a logo
    for gy in range(4, 12):
        if (gx - 55) ** 2 / 30 + (gy - 8) ** 2 / 14 <= 1:
            rect(d, gx, gy, gx, gy, '#40a060')
rect(d, 55, 4, 55, 11, '#fbfaf4')
put(img, pos)

# ---- konbini: the automatic doors, 2.4 m x 2.6 m, drawn once
img, pos = cell('door', 64, 16, 32, 32)
d = ImageDraw.Draw(img)
rect(d, 0, 0, 31, 31, FRAME)
for x0 in (2, 17):
    rect(d, x0, 3, x0 + 12, 29, INSIDE)
    rect(d, x0, 4, x0 + 12, 4, CEIL)
    for x in range(x0 + 1, x0 + 12):             # shelves deep inside
        k = h32(x, x0) % 7
        rect(d, x, 10, x, 12, GOODS[k])
        rect(d, x, 16, x, 18, GOODS[(k + 3) % 7])
    rect(d, x0, 13, x0 + 12, 13, SHELF)
    rect(d, x0, 19, x0 + 12, 19, SHELF)
    rect(d, x0 + 2, 21, x0 + 10, 22, '#40a060')  # the green band on the glass
    rect(d, x0, 26, x0 + 12, 29, '#d8d4c8')
rect(d, 15, 0, 16, 31, '#3a4048')                # the meeting stiles
rect(d, 0, 30, 31, 31, '#6a665e')                # the mat
put(img, pos)

# ---- vending machine: the lit display (upper 1.15 m of the front), drawn once
img, pos = cell('vend_display', 96, 16, 32, 48)
d = ImageDraw.Draw(img)
rect(d, 0, 0, 31, 47, '#f8f8f4')
rect(d, 0, 0, 31, 5, '#3a6ab0')                  # header band
rect(d, 3, 2, 28, 3, '#9cc0f0')
CANS = ['#d8462a', '#f0c030', '#40a060', '#e8782a', '#3a6ab0', '#6a4632', '#e8e8e8', '#8a2418']
for r, top in enumerate((8, 21, 34)):
    rect(d, 1, top + 9, 30, top + 9, '#c8c4b8')  # the shelf
    for i in range(6):
        x0 = 2 + i * 5
        c = CANS[h32(i, r) % len(CANS)]
        tall = 7 if (i + r) % 3 else 8
        rect(d, x0, top + 9 - tall, x0 + 2, top + 8, c)
        rect(d, x0 + 1, top + 9 - tall, x0 + 1, top + 9 - tall, '#ffffff')
        rect(d, x0 + 1, top + 11, x0 + 1, top + 11,
             '#d8462a' if h32(i, r, 3) % 4 == 0 else '#40a060')  # its button
put(img, pos)

# ---- vending machine: the lower front (coin panel and the take-out slot), not lit
img, pos = cell('vend_lower', 0, 32, 32, 16)
d = ImageDraw.Draw(img)
rect(d, 0, 0, 31, 15, '#3a6ab0')
rect(d, 22, 1, 29, 7, '#c8c4b8')                 # coin and note panel
rect(d, 24, 2, 25, 4, '#2c2a28')
rect(d, 27, 2, 27, 5, '#2c2a28')
rect(d, 23, 6, 28, 6, '#2c2a28')
rect(d, 2, 9, 26, 14, '#2c2a28')                 # take-out slot
rect(d, 2, 9, 26, 9, '#6a665e')
rect(d, 0, 15, 31, 15, '#2c3e70')
put(img, pos)

# ---- the mid-rise: one bay of a flat, 3.4 m x 3.04 m (row 0 is the top of the storey)
img, pos = cell('facade', 32, 32, 32, 32)
d = ImageDraw.Draw(img)
TILE, TILE2, GLASS, GLASS2, ALU, CURT = '#cdb89c', '#c0aa8c', '#5a7488', '#7c96a8', '#c8c4b8', '#e8e0cc'
rect(d, 0, 0, 31, 31, TILE)
for y in range(0, 32, 4):                        # tile courses
    rect(d, 0, y, 31, y, TILE2)
rect(d, 4, 3, 27, 25, ALU)                       # the sliding doors' frame
rect(d, 5, 4, 15, 24, GLASS)
rect(d, 16, 4, 26, 24, GLASS2)
rect(d, 5, 4, 10, 24, CURT)                      # a drawn curtain
rect(d, 21, 4, 26, 13, CURT)
rect(d, 15, 4, 16, 24, ALU)
rect(d, 5, 5, 26, 5, '#a8c0d0')                  # sky caught in the glass
rect(d, 3, 26, 28, 27, '#a8a69e')                # sill
rect(d, 0, 30, 31, 31, '#b4ae9e')                # slab edge
for y in range(28, 30):                          # rain streaks under the sill
    rect(d, 7, y, 7, y, '#a89a80')
    rect(d, 22, y, 22, y, '#a89a80')
put(img, pos)

# ---- the mid-rise: ground floor, two bays (6.8 m x 3.04 m): a shutter and the lobby glass
img, pos = cell('base', 0, 64, 64, 32)
d = ImageDraw.Draw(img)
STONE, STONE2, SHUT, SHUT2 = '#a8a69e', '#8e8a84', '#c8c4b8', '#a8a69e'
rect(d, 0, 0, 63, 31, STONE)
for y in range(1, 32, 6):
    rect(d, 0, y, 63, y, STONE2)
rect(d, 0, 0, 63, 2, '#eceae4')                  # the white slab band over the ground floor
rect(d, 3, 6, 28, 31, SHUT)                      # a roller shutter, down
for y in range(7, 31, 2):
    rect(d, 3, y, 28, y, SHUT2)
rect(d, 3, 5, 28, 6, '#6a665e')                  # shutter box
for x in range(5, 27):                           # grime at its foot
    if h32(x, 9) % 3 == 0:
        rect(d, x, 30, x, 30, '#8e887c')
rect(d, 35, 6, 60, 31, '#3a4048')                # the lobby's glass doors
rect(d, 36, 7, 47, 30, '#c8d0c8')
rect(d, 49, 7, 59, 30, '#c8d0c8')
rect(d, 36, 7, 47, 8, '#f4f2e8')                 # its lights
rect(d, 49, 7, 59, 8, '#f4f2e8')
rect(d, 38, 18, 45, 22, '#8e887c')               # mailboxes inside
rect(d, 51, 22, 57, 30, '#a8a69e')
rect(d, 33, 9, 33, 12, '#3a6ab0')                # the building's name plate
put(img, pos)

# ---- the mid-rise: a balcony's front, one bay: 3.4 m x 1.52 m (16 x 16; the band repeats
# along the whole front in one face, so it stays under 255 texels). Rows 0-11 are the balcony
# wall (1.1 m above the floor), rows 12-15 the slab's edge below the floor.
img, pos = cell('balcony', 64, 64, 16, 16)
d = ImageDraw.Draw(img)
rect(d, 0, 0, 15, 15, '#eceae4')
rect(d, 0, 0, 15, 0, '#c8c4b8')                  # the cap
rect(d, 0, 1, 15, 1, '#a8a69e')
rect(d, 15, 1, 15, 11, '#c8c4b8')                # the joint between flats
for y in range(2, 12):                           # a drain stain, honest wear
    if y > 6 or h32(y, 2) % 2:
        rect(d, 14, y, 14, y, '#d8d4c8')
rect(d, 0, 12, 15, 12, '#a8a69e')                # the floor line
rect(d, 0, 13, 15, 15, '#d8d4c8')                # the slab's edge
rect(d, 1, 13, 1, 14, '#6a665e')                 # the drain spout
put(img, pos)

# ---- the fire stair's outer railing, one storey: 5.8 m (64 texels) x 3.04 m (32 rows).
# u runs from the stair's north end (z = 3.85) to its south end (z = -1.95); row 0 is the
# storey's top. The flight rises from the south landing (0 m) to the north landing (1.52 m).
img, pos = cell('rail_side', 0, 96, 64, 32)
d = ImageDraw.Draw(img)
RAIL, BAR = '#6b4a3a', '#5a3e2c'
SZ, SY = 5.8 / 64, 3.04 / 32


def walk_height(z):
    """Height of the walking surface on the outer lane at z, in the storey (m)."""
    if z <= -0.55:
        return 0.0
    if z >= 2.45:
        return 1.52
    return 1.52 * (z + 0.55) / 3.0


def row_of(y):
    return max(0, min(31, int(round((3.04 - y) / SY - 0.5))))


for c in range(64):
    z = 3.85 - (c + 0.5) * SZ
    wh = walk_height(z)
    top = row_of(wh + 1.0)
    mid = row_of(wh + 0.5)
    bottom = row_of(wh + 0.04)
    rect(d, c, top, c, top, RAIL)
    rect(d, c, mid, c, mid, BAR)
    if c % 6 == 3:                               # balusters
        rect(d, c, top, c, bottom, BAR)
put(img, pos)

# ---- the fire stair's end railing, at a landing: 2.9 m (32 texels) wide, one storey tall
img, pos = cell('rail_end', 64, 96, 32, 32)
d = ImageDraw.Draw(img)
top, mid = row_of(1.0), row_of(0.5)
rect(d, 0, top, 31, top, RAIL)
rect(d, 0, mid, 31, mid, BAR)
for c in range(1, 32, 5):
    rect(d, c, top, c, 31, BAR)
put(img, pos)

# ---- the utility pole: concrete, 9 m, once around (16 texels) by its height (64 rows)
img, pos = cell('pole', 96, 64, 16, 64)
d = ImageDraw.Draw(img)
rect(d, 0, 0, 15, 63, '#a8a69e')
for y in range(64):
    for x in range(16):
        k = h32(x, y, 5) % 23
        if k == 0:
            rect(d, x, y, x, y, '#8e8a84')
        elif k == 1 and y < 50:
            rect(d, x, y, x, y, '#b8b4ac')
rect(d, 0, 0, 15, 1, '#8e8a84')
for y in range(14, 49, 3):                       # step bolts, on two sides, from 2 m up
    x = 3 if (y // 3) % 2 else 11
    rect(d, x, y, x + 1, y, '#3a3a3a')
rect(d, 6, 41, 9, 44, '#3a6ab0')                 # the pole's number plate
rect(d, 7, 42, 8, 42, '#eceae4')
for y in range(51, 64):                          # the yellow-and-black guard sleeve
    for x in range(16):
        c = '#f0c030' if ((x + y) // 3) % 2 == 0 else '#2c2a28'
        rect(d, x, y, x, y, c)
rect(d, 0, 50, 15, 50, '#6a665e')
put(img, pos)

# ---- road-works barricades: three 2 m pipe barricades in one 6 m x 1.2 m panel (cutout)
img, pos = cell('barrier', 0, 128, 64, 16)
d = ImageDraw.Draw(img)
YEL, BLK, RED, WHT, LEG = '#f0c030', '#2c2a28', '#d8462a', '#eceae4', '#6a665e'
for b in range(3):
    x0 = b * 21 + 1
    for x in range(x0, x0 + 20):
        for y in range(2, 6):                    # top board: yellow and black
            rect(d, x, y, x, y, YEL if ((x + y) // 3) % 2 == 0 else BLK)
        for y in range(8, 10):                   # lower board: red and white
            rect(d, x, y, x, y, RED if (x // 3) % 2 == 0 else WHT)
    for lx in (x0 + 1, x0 + 18):                 # legs and feet
        rect(d, lx, 1, lx, 14, LEG)
        rect(d, lx - 1, 15, lx + 1, 15, BLK)
    rect(d, x0 + 1, 1, x0 + 18, 1, LEG)
put(img, pos)

# ---- the road-works sign: 0.8 m x 1.0 m, 工事中 over a bowing worker
img, pos = cell('kouji', 64, 128, 32, 40)
d = ImageDraw.Draw(img)
rect(d, 0, 0, 31, 39, '#3a6ab0')
rect(d, 1, 1, 30, 38, '#fbfaf4')
font = ImageFont.truetype(JP_FONT, 10)
d.text((1, 3), '工事中', font=font, fill=rgb('#d8462a'))
px = img.load()
for y in range(2, 16):                           # snap the anti-aliased text to red or white
    for x in range(1, 31):
        g = px[x, y][1]
        px[x, y] = rgb('#d8462a') if g < 170 else rgb('#fbfaf4')
rect(d, 13, 18, 18, 19, '#f0c030')               # helmet
rect(d, 14, 20, 17, 22, '#e8b890')               # face, bowing
rect(d, 11, 23, 20, 30, '#3a6ab0')               # body
rect(d, 12, 31, 14, 36, '#2c2a28')
rect(d, 17, 31, 19, 36, '#2c2a28')
rect(d, 4, 34, 27, 35, '#f0c030')
put(img, pos)

sheet.save(os.path.join(HERE, 'street_sheet.png'))
with open(os.path.join(HERE, 'street_sheet.sheet.json'), 'w') as f:
    json.dump({'format': 'mei-sheet', 'version': 1, 'cells': cells}, f, indent=1)
    f.write('\n')
print('wrote street_sheet.png', W, 'x', H, len(cells), 'cells')
