"""Draws machiya_sheet.png and machiya_sheet.sheet.json beside this file: the machiya family's
textures (the wood lattice fronts, the upper storey's mushiko windows, the side walls, doors,
the garden wall and gate, a shop sign, an air-conditioner grille). Both town_machiya_a and
town_machiya_b read this sheet. Authored pixel art, drawn texel by texel; run once and commit
the outputs (python3 carts/garden/shrinetown/assets/town_machiya_a/art/draw_machiya.py). Needs
Pillow and macOS's Hiragino Mincho for the shop sign."""
import json, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
JP_FONT = '/System/Library/Fonts/ヒラギノ明朝 ProN.ttc'

W, H = 128, 128
sheet = Image.new('RGBA', (W, H), (0, 0, 0, 0))
cells = {}


def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def cell(name, x, y, w, h):
    cells[name] = [x, y, w, h]
    return Image.new('RGBA', (w, h), (0, 0, 0, 0)), (x, y)


def rect(d, x0, y0, x1, y1, c):
    """Fill texels x0..x1, y0..y1 inclusive."""
    d.rectangle([x0, y0, x1, y1], fill=rgb(c))


def h32(*v):
    x = 0x9E3779B9
    for n in v:
        x = ((x ^ (n & 0xFFFFFFFF)) * 0x85EBCA6B) & 0xFFFFFFFF
        x ^= x >> 13
    return x


def koshi(name, x, y, bar, lit, shade, gap, rail):
    """The ground floor's lattice front (senbon-goshi): 1 m wide (32 texels, 3 cm each) by the
    storey's 3.4 m (64 texels, 5.3 cm each). A head beam, a band of plaster under it, the lattice
    of 2-texel bars over the dark room behind with two cross rails, a base board and a stone
    footing. Repeats along the front with a post every metre."""
    img, pos = cell(name, x, y, 32, 64)
    d = ImageDraw.Draw(img)
    rect(d, 0, 0, 31, 63, gap)
    rect(d, 0, 0, 31, 2, rail)                    # head beam under the eave
    rect(d, 0, 3, 31, 7, '#ece4d2')               # plaster band
    rect(d, 0, 8, 31, 9, rail)                    # lintel
    for bx in range(1, 32, 4):                    # bars, 4 texels apart (12 cm)
        rect(d, bx, 10, bx + 1, 54, bar)
        rect(d, bx, 10, bx, 54, lit)
    for ry in (14, 36):                           # cross rails (nuki)
        rect(d, 0, ry, 31, ry, shade)
    rect(d, 0, 10, 1, 58, rail)                   # the post, every metre
    rect(d, 30, 10, 31, 58, shade)
    rect(d, 0, 55, 31, 58, rail)                  # base board
    rect(d, 0, 59, 31, 63, '#8e887c')             # stone footing
    for sx in range(0, 32, 8):
        rect(d, sx, 59, sx, 63, '#6a665e')
    rect(d, 0, 59, 31, 59, '#b4ae9e')
    sheet.paste(img, pos)


koshi('koshi_dark', 0, 0, '#6a4a32', '#8a6446', '#3a2a1e', '#1e1a18', '#4a3424')
koshi('koshi_red', 32, 0, '#8a3a24', '#a8502e', '#5a2416', '#24160f', '#4a2418')

# ---- the upper storey's front: 2.5 m (64 texels) by 1.3 m (32): plaster with a mushiko
# window (thick plaster slats, dark between) in the middle, a floor beam at the foot
img, pos = cell('mushiko', 64, 0, 64, 32)
d = ImageDraw.Draw(img)
rect(d, 0, 0, 63, 31, '#ece4d2')
rect(d, 0, 0, 63, 1, '#dcd2be')                   # eave shadow line
rect(d, 0, 27, 63, 31, '#4a3424')                 # floor beam
rect(d, 0, 27, 63, 27, '#6a4a32')
rect(d, 0, 2, 1, 26, '#5a3e2c')                   # posts at the bay's ends
rect(d, 62, 2, 63, 26, '#5a3e2c')
rect(d, 14, 7, 49, 22, '#cfc5b0')                 # the window's frame, plaster relief
rect(d, 16, 9, 47, 20, '#2a2220')
for sx in range(17, 47, 4):                       # slats
    rect(d, sx, 9, sx + 1, 20, '#e4dac6')
    rect(d, sx + 1, 9, sx + 1, 20, '#c4b8a2')
rect(d, 14, 22, 49, 22, '#b8ac96')
sheet.paste(img, pos)

# ---- side and back walls: 2 m (32 texels) by 7.2 m (64): stone footing, dark boards to the
# first floor, a beam, plaster above with a post at the bay's edge
img, pos = cell('side', 64, 32, 32, 64)
d = ImageDraw.Draw(img)
rect(d, 0, 0, 31, 63, '#ece4d2')                  # plaster (gable and upper storey)
for yy in range(0, 33):                           # faint weathering under the eaves
    for xx in range(32):
        if h32(xx, yy, 7) % 23 == 0:
            rect(d, xx, yy, xx, yy, '#ddd3bf')
rect(d, 0, 0, 1, 33, '#5a3e2c')                   # post
rect(d, 0, 22, 31, 22, '#6a4a32')                 # tie beam at the eave line (4.7 m)
rect(d, 0, 33, 31, 34, '#4a3424')                 # beam at the first floor (3.4 m)
for bx in range(0, 32, 4):                        # vertical boards (yakisugi-dark)
    rect(d, bx, 35, bx + 3, 58, '#4a3a2e' if (bx // 4) % 2 else '#42342a')
    rect(d, bx, 35, bx, 58, '#2e2620')
for bx in range(0, 32, 8):                        # battens
    rect(d, bx + 2, 35, bx + 2, 58, '#5a4a3e')
rect(d, 0, 59, 31, 63, '#8e887c')                 # footing
rect(d, 0, 59, 31, 59, '#b4ae9e')
for sx in range(3, 32, 9):
    rect(d, sx, 60, sx, 63, '#6a665e')
sheet.paste(img, pos)


def door(name, x, y, cloth, cloth_dark, mark):
    """The entrance, 1.8 m by 2.4 m drawn once: a sliding lattice door with a noren hung in
    front, three panels of cloth with a white mark across them."""
    img, pos = cell(name, x, y, 32, 32)
    d = ImageDraw.Draw(img)
    rect(d, 0, 0, 31, 31, '#4a3424')              # frame
    rect(d, 2, 2, 29, 31, '#2a2220')              # dark inside
    for bx in range(3, 29, 3):                    # door's lattice
        rect(d, bx, 2, bx, 31, '#7a5a3e')
    rect(d, 2, 22, 29, 22, '#7a5a3e')
    rect(d, 15, 2, 16, 31, '#5a3e2c')             # the doors' meeting stiles
    rect(d, 1, 1, 30, 2, '#2e2620')               # noren pole
    for i, nx in enumerate((2, 12, 21)):          # three panels, slits between
        rect(d, nx, 3, nx + 8, 15, cloth)
        rect(d, nx, 15, nx + 8, 15, cloth_dark)
    for (mx, my) in mark:
        rect(d, mx, my, mx, my, '#ece4d2')
    rect(d, 0, 30, 31, 31, '#6a665e')             # threshold stone
    sheet.paste(img, pos)


# a: indigo noren with a white circle crest across the middle panel
ring = [(15, 6), (16, 6), (14, 7), (17, 7), (13, 8), (18, 8), (13, 9), (18, 9), (14, 10), (17, 10),
        (15, 11), (16, 11)]
door('door_a', 0, 64, '#24346a', '#1a244a', ring)
# b: persimmon noren for the tea shop, a white band and the shop's mark (a leaf)
leaf = [(x, 12) for x in range(3, 29) if not 10 <= x <= 12 and not 20 <= x <= 21] + \
       [(15, 6), (16, 6), (14, 7), (15, 7), (16, 7), (17, 7), (14, 8), (15, 8), (16, 8), (17, 8),
        (15, 9), (16, 9), (16, 10)]
door('door_b', 32, 64, '#a8502e', '#7a3420', leaf)

# ---- garden wall: 2 m by 2.4 m repeating: plaster with a stone footing and a coping shadow
img, pos = cell('garden_wall', 0, 96, 32, 32)
d = ImageDraw.Draw(img)
rect(d, 0, 0, 31, 31, '#ece4d2')
rect(d, 0, 0, 31, 1, '#cfc5b0')                   # shadow under the cap
for yy in range(2, 24):
    for xx in range(32):
        if h32(xx, yy, 3) % 31 == 0:
            rect(d, xx, yy, xx, yy, '#ddd3bf')
rect(d, 0, 23, 31, 23, '#b8ac96')
rect(d, 0, 24, 31, 31, '#8e887c')                 # stone footing, ashlar
rect(d, 0, 27, 31, 27, '#6a665e')
for sx in (5, 17, 29):
    rect(d, sx, 24, sx, 27, '#6a665e')
for sx in (11, 23):
    rect(d, sx, 28, sx, 31, '#6a665e')
rect(d, 0, 24, 31, 24, '#b4ae9e')
sheet.paste(img, pos)

# ---- the garden's wicket gate, 1.0 m by 1.9 m drawn once: a plank door in a dark frame
img, pos = cell('gate', 32, 96, 16, 32)
d = ImageDraw.Draw(img)
rect(d, 0, 0, 15, 31, '#3a2a1e')
for bx in range(1, 15, 3):
    rect(d, bx, 2, bx + 2, 30, '#8a6446' if (bx // 3) % 2 else '#7a5a3e')
    rect(d, bx, 2, bx, 30, '#5a3e2c')
rect(d, 1, 8, 14, 8, '#4a3424')
rect(d, 1, 23, 14, 23, '#4a3424')
rect(d, 11, 15, 12, 16, '#d8b048')                # latch
sheet.paste(img, pos)

# ---- the tea shop's hanging sign, 0.5 m by 1.0 m drawn once: dark board, gold 茶
img, pos = cell('sign_b', 48, 96, 16, 32)
d = ImageDraw.Draw(img)
rect(d, 0, 0, 15, 31, '#3a2a1e')
rect(d, 1, 1, 14, 30, '#5a3e2c')
font = ImageFont.truetype(JP_FONT, 13)
d.text((8, 9), '茶', font=font, fill=rgb('#e8c060'), anchor='mm')
font = ImageFont.truetype(JP_FONT, 9)
d.text((8, 23), '舗', font=font, fill=rgb('#e8c060'), anchor='mm')
img = img.convert('RGB').quantize(colors=6).convert('RGBA')
sheet.paste(img, pos)

# ---- air conditioner's outdoor unit, face: casing, round fan grille, louvres
img, pos = cell('ac_unit', 64, 96, 16, 16)
d = ImageDraw.Draw(img)
rect(d, 0, 0, 15, 15, '#d8d4c8')
rect(d, 0, 15, 15, 15, '#a8a69e')
d.ellipse([1, 2, 10, 11], fill=rgb('#6a665e'))
d.ellipse([3, 4, 8, 9], fill=rgb('#4a4a50'))
rect(d, 5, 6, 6, 7, '#a8a69e')
for yy in (3, 5, 7, 9, 11):
    rect(d, 12, yy, 14, yy, '#a8a69e')
sheet.paste(img, pos)

# ---- inuyarai, the curved bamboo guard at the wall's foot: slats along the curve
img, pos = cell('inuyarai', 80, 96, 16, 16)
d = ImageDraw.Draw(img)
for bx in range(16):
    rect(d, bx, 0, bx, 15, '#3a2a1e' if bx % 4 == 3 else ('#8a7a4a' if bx % 4 else '#a8945a'))
rect(d, 0, 4, 15, 4, '#4a3424')
rect(d, 0, 11, 15, 11, '#4a3424')
sheet.paste(img, pos)

sheet.save(os.path.join(HERE, 'machiya_sheet.png'))
with open(os.path.join(HERE, 'machiya_sheet.sheet.json'), 'w') as f:
    json.dump({'format': 'mei-sheet', 'version': 1, 'cells': cells}, f, indent=1)
    f.write('\n')
print('wrote', len(cells), 'cells')
