"""Shrine town's two-storey shops: the shopfront sheet and six recipes.

Writes, from this folder:
  art/shopfront.png, art/shopfront.sheet.json   the common shopfront sheet (shared by every shop
                                                family of the town)
  town_shop_2f_a.asset.json, ..._col             clock and glasses shop, tiled gable roof
  ../town_shop_2f_b/town_shop_2f_b.asset.json    greengrocer, open front with shutters, flat roof
  ../town_shop_2f_c/town_shop_2f_c.asset.json    corner liquor shop, two shopfronts, hip roof
  ../town_shop_2f_c/town_shop_2f_c_left...       the corner shop mirrored: second front on -X
  *_noawning.asset.json (in each folder)         A, B, C and C left without their own awning,
                                                 to carry town_awning_bounce instead

Run with Pillow: python3 gen_shops.py. It draws with the macOS Hiragino fonts; the PNG and the
recipes are committed, so building the world needs none of this.

The sheet's sign cells (sign_*, tate_*, valance_*) are masks, not colours: black is the board,
white the lettering and grey the rim. A recipe turns a mask into a texel grid with its own three
colours (`sign_texels`), so one sign drawing serves any number of colourways: signs vary by
palette.

Every shop: origin at the centre of its 9 x 14 m footprint at street level, front (the street)
toward -Z, walls 9 m wide (1 m gaps in a row of 10 m plots), roof top 6.5 m, awning at about 2.6.

The `_noawning` variants: a pink-striped awning always means bounce, so a street-side shop that is
a bounce spot carries the separate town_awning_bounce instead of its own awning. The awning is
left out and the wall finished where it was. town_awning_bounce goes at the shop's (x, 0, -7.75)
(its wall plane, local z +0.75, on the shop's front at z -7.0), x = 0 on A and B, x = 0.1 on C
(-0.1 on C left: the middle of the shopfront). B's opening is 0.1 m lower there (2.7) so the
bounce awning's underside (2.72 at the wall) clears it, and its shutter box is left out (the
awning's roller takes its place); C's kanban starts 0.06 m higher (3.11 to 3.85) so the roller (top
3.09) clears it.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, 'art')
SHEET_REL = 'art/shopfront.png'               # from town_shop_2f_a
SHEET_REL_OTHER = '../town_shop_2f_a/art/shopfront.png'
GOTHIC = '/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc'
GOTHIC_M = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'

# --------------------------------------------------------------------------------------------
# The sheet
# --------------------------------------------------------------------------------------------

CELLS = {}          # name -> Image (RGBA)
MASK, FG, RIM = (0, 0, 0, 255), (255, 255, 255, 255), (128, 128, 128, 255)


def new(name, w, h, fill=(0, 0, 0, 0)):
    img = Image.new('RGBA', (w, h), fill)
    CELLS[name] = img
    d = ImageDraw.Draw(img)
    d.fontmode = '1'
    return img, d


def font(size, path=GOTHIC):
    return ImageFont.truetype(path, size)


def text(d, xy, s, size, fill, path=GOTHIC, anchor='mm'):
    d.text(xy, s, font=font(size, path), fill=fill, anchor=anchor)


def vtext(d, x, y0, s, size, step, fill, path=GOTHIC):
    for i, ch in enumerate(s):
        text(d, (x, y0 + i * step), ch, size, fill, path)


def rect(d, x0, y0, x1, y1, fill=None, outline=None):
    d.rectangle([x0, y0, x1, y1], fill=fill, outline=outline)


# Aluminium and glass, shared by the shopfronts and windows.
AL, AL_D, GL, GL_M, GL_R = '#c4c8cc', '#6e747a', '#4e6a7a', '#6a8a9a', '#a8c4d0'


def shopfront_frame(d, w, h, panels, interior):
    """Aluminium sash front: transom, `panels` glass panels, kick plate; `interior(d)` draws
    what is behind the glass first."""
    interior(d)
    rect(d, 0, 0, w - 1, 2, fill=AL_D)                       # transom bar
    rect(d, 0, h - 3, w - 1, h - 1, fill='#4a4e54')          # kick plate and sill
    rect(d, 0, h - 4, w - 1, h - 4, fill=AL)
    for i in range(panels + 1):
        x = round(i * (w - 1) / panels)
        rect(d, x - (0 if i == 0 else 1), 0, x + (1 if i < panels else 0), h - 4, fill=AL)
    for i in range(panels):                                  # a reflection streak per panel
        x = round(i * (w - 1) / panels) + 4
        for k in range(6):
            d.point((x + k, 5 + k * 2), fill=GL_R)
            d.point((x + k, 6 + k * 2), fill=GL_R)


def draw_sheet():
    # glass_a: clock and glasses shop. Clocks on the back wall, a glass showcase of frames.
    img, d = new('glass_a', 64, 32)

    def inside(d):
        rect(d, 0, 0, 63, 31, fill='#e8dcb0')                # lit back wall
        rect(d, 0, 3, 63, 4, fill='#c8b88e')
        for x, y, r in ((7, 9, 3), (19, 8, 4), (31, 10, 3), (43, 8, 4), (56, 9, 3)):
            d.ellipse([x - r, y - r, x + r, y + r], fill='#f6f2e6', outline='#8a6446')
            d.point((x, y - 1), fill='#2c2a28'); d.point((x + 1, y), fill='#2c2a28')
        rect(d, 0, 17, 63, 27, fill='#8a6446')               # showcase counter
        rect(d, 1, 18, 62, 22, fill='#cfe0e4')               # its glass top, frames inside
        for x in range(3, 61, 6):
            d.point((x, 20), fill='#2c2a28'); d.point((x + 2, 20), fill='#2c2a28')
            d.point((x + 1, 20), fill='#c4302b' if x % 12 == 3 else '#2c2a28')
        rect(d, 26, 6, 37, 16, fill='#f4f0e0')               # a poster: an eye chart
        for k, y in enumerate((8, 11, 14)):
            rect(d, 29 + k, y, 34 - k, y, fill='#2c2a28')
    shopfront_frame(d, 64, 32, 4, inside)

    # interior_b: greengrocer's back wall, seen through the open front. Shelves of produce,
    # bare bulbs, a scale, price cards; dark under the ceiling.
    img, d = new('interior_b', 64, 32)
    rect(d, 0, 0, 63, 31, fill='#8a7a5e')
    rect(d, 0, 0, 63, 4, fill='#3a342c')                     # ceiling shadow
    for x in (8, 24, 40, 56):                                # bulbs on cords
        d.line([(x, 0), (x, 3)], fill='#2c2a28')
        rect(d, x - 1, 4, x + 1, 5, fill='#fff4c0')
    produce = ['#e0502a', '#7aa040', '#e8a020', '#c8301e', '#f0e8c0', '#6a3a7a', '#c8a050']
    for row, y in enumerate((8, 15)):
        rect(d, 0, y + 5, 63, y + 6, fill='#5a3e2c')         # shelf board
        for i, x in enumerate(range(1, 63, 7)):
            c = produce[(i * 3 + row * 2) % len(produce)]
            rect(d, x, y, x + 5, y + 4, fill=c)
            d.point((x + 1, y + 1), fill='#fff4c0')
            if (i + row) % 3 == 0:
                rect(d, x + 1, y - 2, x + 3, y - 1, fill='#f6f2e6')   # price card
                d.point((x + 2, y - 2), fill='#c8301e')
    rect(d, 0, 22, 63, 31, fill='#5a5248')                   # floor and crates
    for x in range(0, 64, 9):
        rect(d, x, 23, x + 7, 29, fill='#b08a5e', outline='#6a4a30')
        rect(d, x + 1, 24, x + 6, 25, fill=produce[(x // 9) % len(produce)])
    rect(d, 46, 17, 52, 21, fill='#c4c8cc')                  # the scale
    rect(d, 47, 16, 51, 16, fill='#e0502a')

    # glass_c: liquor shop. Shelves of isshobin, beer cases stacked, a calendar.
    img, d = new('glass_c', 64, 32)

    def inside_c(d):
        rect(d, 0, 0, 63, 31, fill='#e0d6b8')
        for y in (5, 12):
            rect(d, 0, y + 5, 63, y + 5, fill='#5a3e2c')
            for x in range(1, 63, 3):
                c = ['#2e5a2e', '#5a3a1e', '#2e5a2e', '#3a3a6a', '#7a5a2a'][(x * 7 + y) % 5]
                rect(d, x, y, x + 1, y + 4, fill=c)
                d.point((x, y), fill='#d8b048')
        for x in range(2, 62, 10):                          # beer cases
            rect(d, x, 19, x + 8, 27, fill='#e8b830', outline='#a8321e')
            rect(d, x + 1, 20, x + 7, 21, fill='#5a3a1e')
        rect(d, 40, 4, 47, 10, fill='#f6f2e6')               # calendar
        rect(d, 40, 4, 47, 5, fill='#c4302b')
    shopfront_frame(d, 64, 32, 4, inside_c)

    # win_a: two aluminium sash windows, lace curtains half drawn, a potted plant.
    img, d = new('win_a', 64, 16)
    rect(d, 0, 0, 63, 15, fill='#d8cdb2')
    for x0 in (2, 34):
        rect(d, x0, 1, x0 + 27, 14, fill=AL)
        rect(d, x0 + 1, 2, x0 + 26, 13, fill=GL)
        rect(d, x0 + 1, 2, x0 + 9, 13, fill='#f0ece0')       # lace, left
        rect(d, x0 + 18, 2, x0 + 26, 13, fill='#e8e2d4')     # lace, right
        for y in range(3, 13, 2):
            d.point((x0 + 4, y), fill='#d0c8b8'); d.point((x0 + 22, y), fill='#d0c8b8')
        rect(d, x0 + 13, 1, x0 + 14, 14, fill=AL_D)          # meeting rails
        d.point((x0 + 11, 5), fill=GL_R); d.point((x0 + 12, 6), fill=GL_R)
    rect(d, 14, 10, 18, 13, fill='#b4643c'); rect(d, 13, 7, 19, 10, fill='#4f8f3e')

    # win_b: aluminium window of frosted glass behind a grille (the concrete shop).
    img, d = new('win_b', 32, 16)
    rect(d, 0, 0, 31, 15, fill=AL)
    rect(d, 1, 1, 30, 14, fill='#b8c8cc')
    rect(d, 15, 1, 16, 14, fill=AL_D)
    for x in range(3, 31, 4):
        rect(d, x, 0, x, 15, fill='#7a7e84')
    rect(d, 0, 4, 31, 4, fill='#7a7e84'); rect(d, 0, 11, 31, 11, fill='#7a7e84')

    # win_c: sashes with a sudare (reed blind) let half down over the left one.
    img, d = new('win_c', 64, 16)
    rect(d, 0, 0, 63, 15, fill='#c9d3c0')
    for x0 in (2, 34):
        rect(d, x0, 1, x0 + 27, 14, fill=AL)
        rect(d, x0 + 1, 2, x0 + 26, 13, fill=GL)
        rect(d, x0 + 13, 1, x0 + 14, 14, fill=AL_D)
        d.point((x0 + 5, 4), fill=GL_R); d.point((x0 + 6, 5), fill=GL_R); d.point((x0 + 7, 6), fill=GL_R)
    for y in range(1, 10):
        rect(d, 1, y, 31, y, fill='#c8a870' if y % 2 else '#a8885a')
    rect(d, 40, 2, 51, 13, fill='#e8e0cc')                  # a curtain on the right

    # back_door: grey steel door with a frosted pane and a concrete step.
    img, d = new('back_door', 16, 32)
    rect(d, 0, 0, 15, 31, fill='#6a6e74')
    rect(d, 1, 1, 14, 29, fill='#8e949a')
    rect(d, 4, 4, 11, 11, fill='#c8d4d8')
    rect(d, 11, 16, 12, 17, fill='#d8b048')
    rect(d, 0, 30, 15, 31, fill='#a8a69e')

    # back_win: frosted window behind a grille.
    img, d = new('back_win', 16, 16)
    rect(d, 0, 0, 15, 15, fill=AL)
    rect(d, 1, 1, 14, 14, fill='#c8d4d8')
    for x in (3, 7, 11):
        rect(d, x, 0, x, 15, fill='#6e747a')
    rect(d, 0, 7, 15, 7, fill='#6e747a')

    # shutter: a rolled-down steel shutter, slats, a bottom bar with its lock.
    img, d = new('shutter', 32, 32)
    for y in range(32):
        rect(d, 0, y, 31, y, fill=['#a4aeb6', '#a4aeb6', '#8e98a0', '#6e7880'][y % 4])
    rect(d, 0, 29, 31, 31, fill='#5a626a')
    rect(d, 14, 29, 17, 30, fill='#d8b048')
    rect(d, 4, 13, 9, 17, fill='#e8e2d4')                    # a faded notice
    rect(d, 5, 14, 8, 14, fill='#c4302b')
    d.point((25, 22), fill='#8a5a3a'); d.point((26, 23), fill='#8a5a3a')

    # produce: repeating crates of vegetables and fruit, two rows of four (a tile).
    img, d = new('produce', 32, 16)
    fill = ['#d8301e', '#9ac060', '#f09a20', '#f0ece0', '#5a2a6a', '#c8a060', '#e0502a', '#6a9a30']
    for r in range(2):
        for c in range(4):
            x, y = c * 8, r * 8
            rect(d, x, y, x + 7, y + 7, fill='#8a6446')
            rect(d, x + 1, y + 1, x + 6, y + 6, fill=fill[r * 4 + c])
            for k in range(3):
                d.point((x + 2 + k * 2, y + 2 + (k % 2) * 2), fill='#fff4c0' if r == c % 2 else '#3a3020')
            if (r + c) % 2 == 0:
                rect(d, x + 4, y + 5, x + 6, y + 6, fill='#f6f2e6')
                d.point((x + 5, y + 5), fill='#c8301e')

    # vend_a: drinks machine, white with a red band, sample cans, coin slot and outlet.
    img, d = new('vend_a', 16, 32)
    rect(d, 0, 0, 15, 31, fill='#eceae4')
    rect(d, 0, 0, 15, 2, fill='#c8301e')
    cans = ['#c8301e', '#3a6ab0', '#f0c030', '#40a060', '#2c2a28', '#e8782a']
    for r, y in enumerate((4, 9, 14)):
        rect(d, 1, y - 1, 14, y + 3, fill='#c8d8e0')
        for i, x in enumerate(range(2, 14, 2)):
            rect(d, x, y, x, y + 2, fill=cans[(i + r * 2) % len(cans)])
        rect(d, 1, y + 3, 14, y + 3, fill='#2c2a28')
    rect(d, 11, 19, 13, 23, fill='#6a6e74')
    rect(d, 2, 25, 13, 28, fill='#2c2a28')
    # vend_b: beer and sake machine, dark blue.
    img, d = new('vend_b', 16, 32)
    rect(d, 0, 0, 15, 31, fill='#24345a')
    rect(d, 0, 0, 15, 2, fill='#d8b048')
    for r, y in enumerate((4, 10)):
        rect(d, 1, y - 1, 14, y + 4, fill='#c8d0d8')
        for i, x in enumerate(range(2, 14, 3)):
            c = ['#d8b048', '#5a3a1e', '#2e5a2e', '#eceae4'][(i + r) % 4]
            rect(d, x, y, x + 1, y + 3, fill=c)
    rect(d, 2, 16, 13, 18, fill='#eceae4')                   # the 20-and-over notice
    rect(d, 3, 17, 12, 17, fill='#c8301e')
    rect(d, 11, 20, 13, 23, fill='#6a6e74')
    rect(d, 2, 25, 13, 28, fill='#0e1424')

    # crate: a yellow beer crate with bottle necks above, repeating.
    img, d = new('crate', 16, 16)
    rect(d, 0, 0, 15, 15, fill='#3a3020')
    for x in range(1, 16, 3):
        rect(d, x, 0, x + 1, 5, fill='#5a3a1e')
        d.point((x, 0), fill='#d8b048')
    rect(d, 0, 6, 15, 15, fill='#e8b830')
    rect(d, 0, 6, 15, 6, fill='#f0d060')
    rect(d, 5, 9, 10, 10, fill='#3a3020')                    # hand hole
    rect(d, 0, 15, 15, 15, fill='#a8321e')

    # ac: an outdoor air-conditioner unit's face, fan grille.
    img, d = new('ac', 16, 16)
    rect(d, 0, 0, 15, 15, fill='#e2e0d6')
    d.ellipse([1, 2, 12, 13], fill='#6a6e74')
    d.ellipse([3, 4, 10, 11], fill='#4a4e54')
    d.line([(1, 7), (12, 7)], fill='#a8acb0'); d.line([(6, 2), (6, 13)], fill='#a8acb0')
    rect(d, 13, 3, 14, 12, fill='#c8c4b8')

    # clock: a round clock face for the clock shop's bracket sign (a disc).
    img, d = new('clock', 16, 16)
    rect(d, 0, 0, 15, 15, fill='#2c2a28')
    d.ellipse([0, 0, 15, 15], fill='#d8b048')
    d.ellipse([2, 2, 13, 13], fill='#f6f2e6')
    for x, y in ((7, 3), (12, 7), (7, 12), (3, 7)):
        d.point((x, y), fill='#2c2a28')
    d.line([(7, 7), (7, 4)], fill='#2c2a28'); d.line([(7, 7), (10, 9)], fill='#2c2a28')

    # antenna: a TV antenna, mast and two Yagi booms, holes around (a cutout).
    img, d = new('antenna', 32, 32)
    rect(d, 15, 2, 16, 31, fill='#5a5e64')
    for y, (x0, x1) in ((6, (3, 29)), (14, (7, 25))):
        rect(d, x0, y, x1, y, fill='#7a7e84')
        for x in range(x0 + 1, x1, 3):
            rect(d, x, y - 2 - (x - x0) // 8, x, y + 2 + (x - x0) // 8, fill='#8e9298')
    d.line([(16, 2), (27, 12)], fill='#5a5e64')              # a guy wire

    # rail: a balcony rail in front of a window (a cutout).
    img, d = new('rail', 64, 8)
    rect(d, 0, 0, 63, 1, fill='#b8bcc0')
    rect(d, 0, 6, 63, 7, fill='#8e9298')
    for x in range(0, 64, 3):
        rect(d, x, 2, x, 5, fill='#a8acb0')

    # Sign masks: black board, white lettering, grey rim. Recipes colour them.
    img, d = new('sign_a', 128, 16, MASK)
    rect(d, 0, 0, 127, 15, outline=RIM)
    text(d, (22, 8), '時計', 11, FG, GOTHIC_M)
    text(d, (44, 8), 'メガネ', 9, FG, GOTHIC_M)
    rect(d, 60, 3, 60, 12, fill=RIM)
    for i, ch in enumerate('光 堂'):
        text(d, (78 + i * 11, 8), ch, 14, FG)
    img, d = new('tate_a', 16, 40, MASK)
    rect(d, 0, 0, 15, 39, outline=RIM)
    vtext(d, 8, 8, 'メガネ', 12, 12, FG)
    img, d = new('sign_b', 128, 16, MASK)
    rect(d, 0, 0, 127, 15, outline=RIM)
    rect(d, 2, 2, 125, 13, outline=RIM)
    text(d, (20, 8), '青果', 10, FG, GOTHIC_M)
    for i, ch in enumerate('八百久'):
        text(d, (58 + i * 20, 8), ch, 13, FG)
    img, d = new('valance_b', 128, 8, MASK)
    for x0 in (2, 66):
        for i, ch in enumerate('やさいくだもの'):
            text(d, (x0 + 4 + i * 8, 4), ch, 8, FG, GOTHIC_M)
    img, d = new('sign_c', 128, 16, MASK)
    rect(d, 0, 0, 127, 15, outline=RIM)
    d.ellipse([4, 1, 17, 14], fill=RIM)
    text(d, (11, 8), '酒', 11, FG)
    for i, ch in enumerate('丸十酒店'):
        text(d, (40 + i * 18, 8), ch, 13, FG)
    img, d = new('sign_cs', 128, 16, MASK)
    rect(d, 0, 0, 127, 15, outline=RIM)
    for i, ch in enumerate('米・たばこ・塩'):
        text(d, (18 + i * 15, 8), ch, 12, FG)
    img, d = new('valance_c', 128, 8, MASK)
    for x0 in (4, 68):
        for i, ch in enumerate('さけ こめ'):
            text(d, (x0 + 6 + i * 11, 4), ch, 8, FG, GOTHIC_M)
    img, d = new('tate_c', 16, 32, MASK)
    rect(d, 0, 0, 15, 31, outline=RIM)
    vtext(d, 8, 9, '酒米', 13, 14, FG)


# --------------------------------------------------------------------------------------------
# Recipe helpers
# --------------------------------------------------------------------------------------------

def sub(a, b): return [a[i] - b[i] for i in range(3)]
def dot(a, b): return sum(a[i] * b[i] for i in range(3))


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return n


def r4(x):
    x = round(x, 4)
    return 0.0 if x == 0 else x


class Mesh:
    """A mesh node built face by face; each face is wound to face `out`."""

    def __init__(self, id, material=None):
        self.id, self.material = id, material
        self.v, self.f, self.fm, self.decals = [], [], [], []

    def vid(self, p):
        p = tuple(r4(c) for c in p)
        if p not in self.v:
            self.v.append(p)
        return self.v.index(p)

    def face(self, pts, out, mat):
        if dot(newell(pts), out) < 0:
            pts = pts[::-1]
        self.f.append([self.vid(p) for p in pts])
        self.fm.append(mat)
        return len(self.f) - 1

    def quad(self, a, b, c, d, out, mat):
        return self.face([a, b, c, d], out, mat)

    def decal(self, face, id, mat, size, centre, normal):
        """`centre` in world coordinates; converted to the face's right/up from the origin."""
        x, y, z = centre
        at = {(0, 0, -1): [x, y], (0, 0, 1): [-x, y], (1, 0, 0): [z, y], (-1, 0, 0): [-z, y],
              (0, 1, 0): [x, z]}[tuple(normal)]
        self.decals.append({'id': id, 'face': face, 'material': mat,
                            'size': [r4(size[0]), r4(size[1])], 'at': [r4(at[0]), r4(at[1])]})

    def node(self):
        n = {'id': self.id, 'op': 'mesh', 'vertices': [list(v) for v in self.v], 'faces': self.f,
             'face_materials': self.fm}
        if self.decals:
            n['decals'] = self.decals
        return n


def box(id, size, centre, mat, open=None, faces=None, rotate=None, decals=None):
    n = {'id': id, 'op': 'box', 'size': [r4(s) for s in size], 'material': mat}
    if open:
        n['open'] = open
    if faces:
        n['faces'] = faces
    if decals:
        n['decals'] = decals
    t = {'translate': [r4(c) for c in centre]}
    if rotate:
        t['rotate'] = rotate
    n['transform'] = t
    return n


def prism_x(m, x0, x1, profile, mats, ends=True, skip=()):
    """Faces of a prism along X whose cross-section `profile` is a list of (z, y), in order
    round the outline. mats[i] is the material of the side from point i to i + 1; None or an
    index in `skip` leaves it out. Ends at x0 and x1 in mats['end']."""
    n = len(profile)
    cz = sum(p[0] for p in profile) / n
    cy = sum(p[1] for p in profile) / n
    for i in range(n):
        if i in skip or mats[i] is None:
            continue
        (z0, y0), (z1, y1) = profile[i], profile[(i + 1) % n]
        mz, my = (z0 + z1) / 2 - cz, (y0 + y1) / 2 - cy
        m.quad((x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1), (0, my, mz), mats[i])
    if ends:
        m.face([(x0, y, z) for z, y in profile], (-1, 0, 0), mats['end'])
        m.face([(x1, y, z) for z, y in profile], (1, 0, 0), mats['end'])


def crossed_quads(id, centre, w, h, mat):
    x, y0, z = centre
    m = Mesh(id)
    m.quad((x - w / 2, y0 + h, z), (x + w / 2, y0 + h, z), (x + w / 2, y0, z), (x - w / 2, y0, z), (0, 0, -1), mat)
    m.quad((x, y0 + h, z - w / 2), (x, y0 + h, z + w / 2), (x, y0, z + w / 2), (x, y0, z - w / 2), (1, 0, 0), mat)
    return m.node()


def sign_texels(cell, colours):
    """A sheet mask as a texel grid in three colours: board, lettering, rim."""
    img = CELLS[cell]
    keys = {MASK[:3]: '0', FG[:3]: '1', RIM[:3]: '2'}
    rows = []
    for y in range(img.height):
        rows.append(''.join(keys[img.getpixel((x, y))[:3]] for x in range(img.width)))
    return {'texels': rows, 'colors': colours, 'projection': 'fit'}


def cell_tex(name, **kw):
    t = {'sheet': 'shopfront', 'cell': name, 'projection': 'fit'}
    t.update(kw)
    return t


VERIFY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}
W, D = 4.5, 7.0          # half the walls' width (x) and depth (z)

def bands(m, face, x0, x1, fixed, ys, mats):
    """A wall of horizontal bands, each the full width, for the coarsest level: face 'front'
    (z = fixed, x0..x1) or 'side' (x = fixed, z0..z1 as x0..x1); ys the band edges bottom to top,
    mats one material a band. The bands share full-width edges, so no T-junctions between them."""
    for k, mat in enumerate(mats):
        y0, y1 = ys[k], ys[k + 1]
        if face == 'front':
            m.quad((x0, y1, fixed), (x1, y1, fixed), (x1, y0, fixed), (x0, y0, fixed), (0, 0, -1), mat)
        else:
            m.quad((fixed, y1, x0), (fixed, y1, x1), (fixed, y0, x1), (fixed, y0, x0), (1, 0, 0), mat)


# --------------------------------------------------------------------------------------------
# Shared parts
# --------------------------------------------------------------------------------------------

BACK = [('door', 'back_door', (2.6, 1.02), (0.9, 2.0)), ('win1', 'back_win', (-1.8, 1.6), (1.0, 0.8)),
        ('win2', 'back_win', (-1.2, 4.1), (1.4, 0.9))]


def back_decals(m, face, z=D):
    for id, mat, (x, y), size in BACK:
        m.decal(face, id, mat, size, (x, y, z), (0, 0, 1))


def back_materials():
    return {'back_door': {'color': '#8e949a', 'texture': cell_tex('back_door')},
            'back_win': {'color': '#c8d4d8', 'texture': cell_tex('back_win')}}


def awning_profile(wall_top, out_z, out_top, val, under_wall, wall_z=-6.98):
    """Cross-section (z, y) of an awning: top from the wall out, valance down, underside back."""
    return [(wall_z, wall_top), (out_z, out_top), (out_z, out_top - val), (wall_z, under_wall)]


def write(path, recipe):
    with open(path, 'w') as f:
        json.dump(recipe, f, indent=1, ensure_ascii=False)
        f.write('\n')


def recipe(name, budget, materials, nodes, levels=None, sheet=SHEET_REL):
    r = {'format': 'mei-asset', 'version': 1, 'name': name,
         'sheets': {'shopfront': {'image': sheet}},
         'budget': {'triangles': budget}, 'materials': materials, 'lighting': LIGHT,
         'verification': VERIFY, 'nodes': nodes}
    if levels:
        r['lod'] = {'levels': levels}
    return r


def col_recipe(name, nodes, budget=300):
    return {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': {'triangles': budget},
            'materials': {'solid': {'color': '#ffffff', 'palette': True},
                          'awning': {'color': '#ffffff', 'palette': True}},
            'lighting': LIGHT, 'verification': VERIFY, 'nodes': nodes}


def slab_box(id, x0, x1, y0, y1, z0, z1, mat='solid', open=()):
    """A closed box as a mesh (collision)."""
    m = Mesh(id)
    sides = {
        'top': ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
        'bottom': ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
        'front': ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),
        'back': ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
        'left': ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0)),
        'right': ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
    }
    for k, (pts, out) in sides.items():
        if k not in open:
            m.face(pts, out, mat)
    return m.node()


def ledge(id, x0, x1, y0, y1, z0, z1, pieces, along, open=()):
    """A collision box whose top is split into `pieces` along `along`, so no floor triangle is
    long and thin; the other sides whole (T-junctions on them are allowed)."""
    m = Mesh(id)
    for i in range(pieces):
        if along == 'x':
            a, b = x0 + (x1 - x0) * i / pieces, x0 + (x1 - x0) * (i + 1) / pieces
            m.quad((a, y1, z0), (b, y1, z0), (b, y1, z1), (a, y1, z1), (0, 1, 0), 'solid')
        else:
            a, b = z0 + (z1 - z0) * i / pieces, z0 + (z1 - z0) * (i + 1) / pieces
            m.quad((x0, y1, a), (x1, y1, a), (x1, y1, b), (x0, y1, b), (0, 1, 0), 'solid')
    sides = {
        'bottom': ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
        'front': ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),
        'back': ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
        'left': ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0)),
        'right': ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
    }
    for k, (pts, out) in sides.items():
        if k not in open:
            m.face(pts, out, 'solid')
    return m.node()


def strip_top(id, x0, x1, z0, z1, y, pieces, along, mat='solid'):
    """A floor strip split into `pieces` quads along `along` ('x' or 'z'), sharing edges, so
    that no floor triangle is long and thin."""
    m = Mesh(id)
    for i in range(pieces):
        if along == 'x':
            a, b = x0 + (x1 - x0) * i / pieces, x0 + (x1 - x0) * (i + 1) / pieces
            m.quad((a, y, z0), (b, y, z0), (b, y, z1), (a, y, z1), (0, 1, 0), mat)
        else:
            a, b = z0 + (z1 - z0) * i / pieces, z0 + (z1 - z0) * (i + 1) / pieces
            m.quad((x0, y, a), (x1, y, a), (x1, y, b), (x0, y, b), (0, 1, 0), mat)
    return m.node()


# --------------------------------------------------------------------------------------------
# A: Hikari-do, clocks and glasses. Cream mortar, tiled gable roof (ridge along the street),
# a recessed glass front, a red awning, a navy kanban, a vertical sign and a clock on a bracket.
# --------------------------------------------------------------------------------------------

def shop_a(has_awning=True):
    name = 'town_shop_2f_a' + ('' if has_awning else '_noawning')
    E, RU, T = 5.2, 6.32, 0.18          # wall top at the eaves, underside at the ridge, slab
    k = (RU - E) / D                    # the roof's slope (about 9 degrees)
    OZ, OX = 7.5, 4.75                  # roof overhangs
    yu = lambda z: RU - k * abs(z)      # underside height
    sign = ['#1e3a6e', '#f4f0e0', '#d8b048']
    tate = ['#f4f0e0', '#c4302b', '#c4302b']
    awn = ['#a8321e', '#ece4d2']
    wall = '#e6dcc4'
    mats = {
        'plaster': {'color': wall, 'tag': 'wall', 'texture': {
            'pattern': 'speckle', 'size': 16, 'colors': [wall, '#d8cdb2', '#efe7d4'],
            'params': {'density': 0.22, 'seed': 5}, 'projection': 'box', 'scale': [1, 1]}},
        'kawara': {'color': '#4a5560', 'tag': 'roof', 'texture': {
            'texels': ['0111011101110111', '1222122212221222', '1222122212221222', '1222122212221222',
                       '1222122212221222', '1222122212221222', '1222122212221222', '3333333333333333',
                       '1110111011101110', '2221222122212221', '2221222122212221', '2221222122212221',
                       '2221222122212221', '2221222122212221', '2221222122212221', '3333333333333333'],
            'colors': ['#3b444e', '#56616d', '#6a7684', '#2c333b'], 'projection': 'box', 'scale': [1, 0.5]}},
        'ridge': {'color': '#2c333b', 'palette': True, 'tag': 'roof'},
        'soffit': {'color': '#5a3e2c', 'palette': True},
        'reveal': {'color': '#a8acb0', 'palette': True},
        'board': {'color': '#3a3a3e', 'palette': True},
        'ac_body': {'color': '#e2e0d6', 'palette': True},
        'pipe': {'color': '#8e887c', 'palette': True},
        'awning': {'color': awn[0], 'tag': 'awning', 'texture': {
            'pattern': 'stripes', 'size': 16, 'colors': awn, 'params': {'count': 4, 'axis': 'u'},
            'projection': 'box', 'scale': [1, 1]}},
        'glass': {'color': '#e8dcb0', 'class': 'emissive', 'tag': 'shopfront', 'texture': cell_tex('glass_a')},
        'window': {'color': '#4e6a7a', 'texture': cell_tex('win_a')},
        'kanban': {'color': sign[0], 'class': 'emissive', 'tag': 'sign', 'texture': sign_texels('sign_a', sign)},
        'tate': {'color': tate[0], 'class': 'emissive', 'tag': 'sign', 'texture': sign_texels('tate_a', tate)},
        'ac': {'color': '#e2e0d6', 'texture': cell_tex('ac')},
        'clock': {'color': '#f6f2e6', 'texture': cell_tex('clock', projection='disc', axis='y')},
        'clock_ds': {'color': '#f6f2e6', 'double_sided': True, 'texture': cell_tex('clock')},
        'rail': {'color': '#b8bcc0', 'double_sided': True, 'texture': cell_tex('rail')},
        'antenna': {'color': '#7a7e84', 'double_sided': True, 'texture': cell_tex('antenna')},
    }
    mats.update(back_materials())

    def shell(level):
        m = Mesh('shell')
        if level == 0:
            front = m.face([(-W, E, -D), (W, E, -D), (W, 0, -D), (3.9, 0, -D), (3.9, 2.5, -D),
                            (-3.9, 2.5, -D), (-3.9, 0, -D), (-W, 0, -D)], (0, 0, -1), 'plaster')
            m.decal(front, 'window', 'window', (5.6, 1.0), (0, 4.5, -D), (0, 0, -1))
            zr = -6.4                                            # the recessed glass front
            m.quad((-3.9, 2.5, -D), (3.9, 2.5, -D), (3.9, 2.5, zr), (-3.9, 2.5, zr), (0, -1, 0), 'reveal')
            m.quad((-3.9, 0, -D), (-3.9, 2.5, -D), (-3.9, 2.5, zr), (-3.9, 0, zr), (1, 0, 0), 'reveal')
            m.quad((3.9, 0, -D), (3.9, 2.5, -D), (3.9, 2.5, zr), (3.9, 0, zr), (-1, 0, 0), 'reveal')
            m.quad((-3.9, 2.5, zr), (3.9, 2.5, zr), (3.9, 0, zr), (-3.9, 0, zr), (0, 0, -1), 'glass')
            back = m.quad((-W, E, D), (W, E, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'plaster')
            back_decals(m, back)
        elif level == 1:
            front = m.quad((-W, E, -D), (W, E, -D), (W, 0, -D), (-W, 0, -D), (0, 0, -1), 'plaster')
            m.decal(front, 'glass', 'glass', (7.8, 2.48), (0, 1.25, -D), (0, 0, -1))
            m.decal(front, 'window', 'window', (5.6, 1.0), (0, 4.5, -D), (0, 0, -1))
            m.quad((-W, E, D), (W, E, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'plaster')
        else:
            if has_awning:
                bands(m, 'front', -W, W, -D, [0, 3.05, 3.95, E], ['glass', 'kanban', 'window'])
            else:                                        # the wall over the shopfront shows
                bands(m, 'front', -W, W, -D, [0, 2.5, 3.05, 3.95, E], ['glass', 'plaster', 'kanban', 'window'])
            m.quad((-W, E, D), (W, E, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'plaster')
        for s in (-1, 1):
            m.face([(s * W, 0, -D), (s * W, E, -D), (s * W, RU, 0), (s * W, E, D), (s * W, 0, D)], (s, 0, 0), 'plaster')
        return m.node()

    def roof(level):
        m = Mesh('roof')
        top = lambda z: yu(z) + T
        if level == 2:
            for s in (-1, 1):
                m.quad((-OX, top(OZ), s * OZ), (OX, top(OZ), s * OZ), (OX, top(0), 0), (-OX, top(0), 0),
                       (0, 1, s * 0.2), 'kawara')
            return m.node()
        for s in (-1, 1):
            z = s * OZ
            m.quad((-OX, top(z), z), (OX, top(z), z), (OX, top(0), 0), (-OX, top(0), 0), (0, 1, s * 0.2), 'kawara')
            m.quad((-OX, yu(z), z), (OX, yu(z), z), (OX, RU, 0), (-OX, RU, 0), (0, -1, -s * 0.2), 'soffit')
            m.quad((-OX, top(z), z), (OX, top(z), z), (OX, yu(z), z), (-OX, yu(z), z), (0, 0, s), 'ridge')
        if level == 0:
            for s in (-1, 1):
                m.face([(s * OX, top(-OZ), -OZ), (s * OX, top(0), 0), (s * OX, top(OZ), OZ),
                        (s * OX, yu(OZ), OZ), (s * OX, RU, 0), (s * OX, yu(-OZ), -OZ)], (s, 0, 0), 'ridge')
        return m.node()

    def awning(level):
        m = Mesh('awning')
        prof = awning_profile(3.0, -8.3, 2.62, 0.25, 2.78)
        mats_ = {0: 'awning', 1: 'awning', 2: 'awning', 3: None, 'end': 'awning'}
        if level == 2:
            mats_ = {0: 'awning', 1: None, 2: None, 3: None, 'end': None}
        prism_x(m, -4.45, 4.45, prof, mats_, ends=(level == 0))
        return m.node()

    kanban = box('kanban', (8.1, 0.8, 0.3), (-0.2, 3.5, -7.13), 'board', open=['front'], faces={'back': 'kanban'})
    tate = box('tate', (0.16, 1.5, 0.62), (4.15, 4.25, -7.29), 'board', open=['front'],
               faces={'left': 'tate', 'right': 'tate'})
    clock = {'id': 'clock', 'op': 'cylinder', 'radius': 0.36, 'height': 0.12, 'segments': 10,
             'material': 'board', 'faces': {'top': 'clock', 'bottom': 'clock'},
             'transform': {'rotate': [0, 0, 90], 'translate': [-4.1, 4.45, -7.55]}}
    bracket = box('bracket', (0.06, 0.06, 0.62), (-4.1, 4.83, -7.28), 'board', open=['front'])
    rail = Mesh('rail')
    rail.quad((-2.9, 4.45, -7.22), (2.9, 4.45, -7.22), (2.9, 4.0, -7.22), (-2.9, 4.0, -7.22), (0, 0, -1), 'rail')
    ac = box('ac', (0.8, 0.6, 0.28), (-1.2 + 3.6, 4.4, 7.12), 'ac_body', open=['back'], faces={'front': 'ac'})
    pipe = box('downpipe', (0.1, 5.1, 0.1), (-4.36, 2.55, -7.03), 'pipe', open=['top', 'bottom'])
    ridge = box('ridge', (9.7, 0.16, 0.36), (0, RU + T, 0), 'ridge', open=['bottom'])
    antenna = crossed_quads('antenna', (2.5, RU + T - k * 2.0 - 0.1, 2.0), 1.4, 1.8, 'antenna')

    nodes0 = [shell(0), roof(0), ridge] + ([awning(0)] if has_awning else []) + [
        kanban, tate, clock, bracket, rail.node(), ac, pipe, antenna]

    # Level 1 (from 20 m): the shopfront and the window as decals on a flat front, the roof without its gable ends, the awning
    # without its ends, the kanban and the vertical sign as open boxes, the clock as a plate.
    plate = Mesh('clock')
    import math
    ring = [(-4.1, 4.45 + 0.36 * math.cos(a * math.pi / 4), -7.55 + 0.36 * math.sin(a * math.pi / 4)) for a in range(8)]
    plate.face(ring, (1, 0, 0), 'clock_ds')
    nodes1 = [shell(1), roof(1)] + ([awning(1)] if has_awning else []) + [
              box('kanban', (8.1, 0.8, 0.3), (-0.2, 3.5, -7.13), 'board', open=['front', 'top'], faces={'back': 'kanban'}),
              box('tate', (0.16, 1.5, 0.62), (4.15, 4.25, -7.29), 'board', open=['front', 'top', 'bottom'],
                  faces={'left': 'tate', 'right': 'tate'}),
              plate.node()]
    nodes2 = [shell(2), roof(2)] + ([awning(2)] if has_awning else [])
    if not has_awning:
        del mats['awning']

    r = recipe(name, 250, mats, nodes0,
               [{'distance': 20, 'nodes': nodes1}, {'distance': 50, 'nodes': nodes2}])
    write(os.path.join(HERE, name + '.asset.json'), r)

    # Collision: the walls, the roof as a 0.2 m slab on the same slope (its fascias are the
    # grabbing lips), the awning, the kanban's ledge (in pieces).
    roofc = Mesh('roof')
    tc = lambda z: yu(z) + 0.2
    for s in (-1, 1):
        z = s * OZ
        roofc.quad((-OX, tc(z), z), (OX, tc(z), z), (OX, tc(0), 0), (-OX, tc(0), 0), (0, 1, s * 0.2), 'solid')
        roofc.quad((-OX, yu(z), z), (OX, yu(z), z), (OX, RU, 0), (-OX, RU, 0), (0, -1, -s * 0.2), 'solid')
        roofc.quad((-OX, tc(z), z), (OX, tc(z), z), (OX, yu(z), z), (-OX, yu(z), z), (0, 0, s), 'solid')
        roofc.face([(s * OX, tc(-OZ), -OZ), (s * OX, tc(0), 0), (s * OX, tc(OZ), OZ),
                    (s * OX, yu(OZ), OZ), (s * OX, RU, 0), (s * OX, yu(-OZ), -OZ)], (s, 0, 0), 'solid')
    body = Mesh('body')
    body.quad((-W, E, -D), (W, E, -D), (W, 0, -D), (-W, 0, -D), (0, 0, -1), 'solid')
    body.quad((-W, E, D), (W, E, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'solid')
    for s in (-1, 1):
        body.face([(s * W, 0, -D), (s * W, E, -D), (s * W, RU, 0), (s * W, E, D), (s * W, 0, D)], (s, 0, 0), 'solid')
    awc = Mesh('awning')
    prism_x(awc, -4.45, 4.45, awning_profile(3.0, -8.3, 2.62, 0.25, 2.78, wall_z=-7.0),
            {0: 'awning', 1: 'awning', 2: 'awning', 3: None, 'end': 'awning'})
    ledge_ = [ledge('kanban', -4.25, 3.85, 3.1, 3.9, -7.28, -7.0, 3, 'x', open=('back',))]
    write(os.path.join(HERE, name + '_col.asset.json'),
          col_recipe(name + '_col', [body.node(), roofc.node()] + ([awc.node()] if has_awning else []) + ledge_))


# --------------------------------------------------------------------------------------------
# B: Yaokyu, greengrocer. A 1970s concrete front faced in small tiles, flat roof with a parapet,
# the ground floor open 1.6 m deep with a produce stand under a green awning, one bay shuttered.
# --------------------------------------------------------------------------------------------

def shop_b(has_awning=True):
    name = 'town_shop_2f_b' + ('' if has_awning else '_noawning')
    H, DECK, PT = 6.5, 6.3, 0.25        # parapet top, roof deck, parapet thickness
    OPX, OPY, ZR = 4.1, 2.8, -5.4       # the opening's half width, height; the back of the recess
    if not has_awning:
        OPY = 2.7                       # under the bounce awning's underside (2.72 at the wall)
    sign = ['#f4f0e0', '#c8301e', '#2e7a3a']
    val = ['#2e7a3a', '#f4f0e0', '#2e7a3a']
    awn = ['#2e7a3a', '#f4f0e0']
    tile, mortar = '#c8a882', '#c8c4b8'
    mats = {
        'tile': {'color': tile, 'tag': 'wall', 'texture': {
            'pattern': 'tile', 'size': 16, 'colors': [tile, '#a88a66', '#d4b892'],
            'params': {'count': 4, 'grout': 1}, 'projection': 'box', 'scale': [1, 1]}},
        'mortar': {'color': mortar, 'tag': 'wall', 'texture': {
            'pattern': 'speckle', 'size': 16, 'colors': [mortar, '#b8b4a8', '#d4d0c4'],
            'params': {'density': 0.25, 'seed': 2}, 'projection': 'box', 'scale': [1, 1]}},
        'deck': {'color': '#7a8070', 'tag': 'roof', 'texture': {
            'pattern': 'speckle', 'size': 16, 'colors': ['#7a8070', '#6a7062', '#8a907e'],
            'params': {'density': 0.3, 'seed': 4}, 'projection': 'box', 'scale': [2, 2]}},
        'parapet': {'color': '#d4d0c4', 'palette': True, 'tag': 'wall'},
        'soffit': {'color': '#6a665e', 'palette': True},
        'wood': {'color': '#8a6446', 'palette': True},
        'steel': {'color': '#8e98a0', 'palette': True},
        'ac_body': {'color': '#e2e0d6', 'palette': True},
        'pipe': {'color': '#8e887c', 'palette': True},
        'tank': {'color': '#d8dcd4', 'texture': {
            'pattern': 'tile', 'size': 16, 'colors': ['#d8dcd4', '#a8aca4'], 'params': {'count': 1, 'grout': 1},
            'projection': 'box', 'scale': [1, 1]}},
        'awning': {'color': awn[0], 'tag': 'awning', 'texture': {
            'pattern': 'stripes', 'size': 16, 'colors': awn, 'params': {'count': 4, 'axis': 'u'},
            'projection': 'box', 'scale': [1, 1]}},
        'valance': {'color': val[0], 'tag': 'awning', 'texture': sign_texels('valance_b', val)},
        'interior': {'color': '#8a7a5e', 'class': 'emissive', 'tag': 'shopfront', 'texture': cell_tex('interior_b')},
        'produce': {'color': '#e0502a', 'texture': {'sheet': 'shopfront', 'cell': 'produce', 'projection': 'box',
                                                    'scale': [2, 1]}},
        'shutter': {'color': '#a4aeb6', 'texture': cell_tex('shutter')},
        'window': {'color': '#b8c8cc', 'texture': cell_tex('win_b')},
        'kanban': {'color': sign[0], 'class': 'emissive', 'tag': 'sign', 'texture': sign_texels('sign_b', sign)},
        'ac': {'color': '#e2e0d6', 'texture': cell_tex('ac')},
        'antenna': {'color': '#7a7e84', 'double_sided': True, 'texture': cell_tex('antenna')},
    }
    mats.update(back_materials())
    WIN = [(-2.2, 4.1), (2.2, 4.1)]

    def shell(level):
        m = Mesh('shell')
        if level < 2:
            front = m.face([(-W, H, -D), (W, H, -D), (W, 0, -D), (OPX, 0, -D), (OPX, OPY, -D),
                            (-OPX, OPY, -D), (-OPX, 0, -D), (-W, 0, -D)], (0, 0, -1), 'tile')
            for i, (x, y) in enumerate(WIN):
                m.decal(front, f'window_{i}', 'window', (1.9, 1.1), (x, y, -D), (0, 0, -1))
            m.decal(front, 'kanban', 'kanban', (8.4, 1.2), (0, 5.65, -D), (0, 0, -1))
            if level == 0:                               # the open front, 1.6 m deep
                m.quad((-OPX, OPY, -D), (OPX, OPY, -D), (OPX, OPY, ZR), (-OPX, OPY, ZR), (0, -1, 0), 'soffit')
                m.quad((-OPX, 0, -D), (-OPX, OPY, -D), (-OPX, OPY, ZR), (-OPX, 0, ZR), (1, 0, 0), 'mortar')
                m.quad((OPX, 0, -D), (OPX, OPY, -D), (OPX, OPY, ZR), (OPX, 0, ZR), (-1, 0, 0), 'mortar')
                m.quad((-OPX, OPY, ZR), (OPX, OPY, ZR), (OPX, 0, ZR), (-OPX, 0, ZR), (0, 0, -1), 'interior')
            else:                                        # level 1: the interior in the opening
                m.quad((-OPX, OPY, -D), (OPX, OPY, -D), (OPX, 0, -D), (-OPX, 0, -D), (0, 0, -1), 'interior')
            back = m.quad((-W, H, D), (W, H, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'mortar')
        if level == 0:
            back_decals(m, back)
            # the deck and the parapet's inner faces and rim
            i_x, i_z = W - PT, D - PT
            m.quad((-i_x, DECK, -i_z), (i_x, DECK, -i_z), (i_x, DECK, i_z), (-i_x, DECK, i_z), (0, 1, 0), 'deck')
            m.quad((-i_x, H, -i_z), (i_x, H, -i_z), (i_x, DECK, -i_z), (-i_x, DECK, -i_z), (0, 0, 1), 'parapet')
            m.quad((-i_x, H, i_z), (i_x, H, i_z), (i_x, DECK, i_z), (-i_x, DECK, i_z), (0, 0, -1), 'parapet')
            for s in (-1, 1):
                m.quad((s * i_x, H, -i_z), (s * i_x, H, i_z), (s * i_x, DECK, i_z), (s * i_x, DECK, -i_z), (-s, 0, 0), 'parapet')
            m.quad((-W, H, -D), (W, H, -D), (i_x, H, -i_z), (-i_x, H, -i_z), (0, 1, 0), 'parapet')
            m.quad((-W, H, D), (W, H, D), (i_x, H, i_z), (-i_x, H, i_z), (0, 1, 0), 'parapet')
            for s in (-1, 1):
                m.quad((s * W, H, -D), (s * W, H, D), (s * i_x, H, i_z), (s * i_x, H, -i_z), (0, 1, 0), 'parapet')
        elif level == 2:
            if has_awning:
                bands(m, 'front', -W, W, -D, [0, 3.2, 4.9, H], ['interior', 'window', 'kanban'])
            else:
                bands(m, 'front', -W, W, -D, [0, OPY, 3.2, 4.9, H], ['interior', 'tile', 'window', 'kanban'])
            m.quad((-W, H, D), (W, H, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'mortar')
        if level > 0:                                            # a flat top at the parapet
            m.quad((-W, H, -D), (W, H, -D), (W, H, D), (-W, H, D), (0, 1, 0), 'deck')
        for s in (-1, 1):
            m.quad((s * W, 0, -D), (s * W, H, -D), (s * W, H, D), (s * W, 0, D), (s, 0, 0), 'mortar')
        return m.node()

    prof = awning_profile(3.32, -8.6, 2.8, 0.32, 3.16)

    def awning(level):
        m = Mesh('awning')
        if level == 2:
            prism_x(m, -4.45, 4.45, prof, {0: 'awning', 1: None, 2: None, 3: None, 'end': None}, ends=False)
        else:
            prism_x(m, -4.45, 4.45, prof, {0: 'awning', 1: 'valance', 2: 'awning', 3: None, 'end': 'awning'},
                    ends=(level == 0))
        return m.node()

    def stand(level):
        m = Mesh('stand')
        p = [(-7.7, 0.0), (-7.7, 0.55), (-5.6, 1.15), (-5.6, 0.0)]
        mats_ = {0: 'wood', 1: 'produce', 2: 'wood' if level == 0 else None, 3: None,
                 'end': 'wood'}
        prism_x(m, -4.0, 2.25, p, mats_, ends=(level == 0))
        return m.node()

    shutter_box = box('shutter_box', (2 * OPX + 0.3, 0.24, 0.2), (0, 2.91, -7.1), 'steel', open=['front'])
    shutter = box('shutter', (1.73, 2.84, 0.06), (3.265, 1.42, -6.9), 'steel', open=['top', 'bottom'],
                  faces={'back': 'shutter'})
    tank = box('tank', (1.4, 1.0, 1.1), (2.6, DECK + 0.48, 4.2), 'tank', open=['bottom'])
    ac = box('ac', (0.9, 0.65, 0.35), (-2.5, DECK + 0.305, 5.6), 'ac_body', open=['bottom'], faces={'back': 'ac'})
    pipe = box('downpipe', (0.1, 6.4, 0.1), (-4.38, 3.2, 7.03), 'pipe', open=['top', 'bottom'])
    antenna = crossed_quads('antenna', (-2.2, DECK - 0.05, 1.5), 1.4, 1.8, 'antenna')

    if has_awning:
        nodes0 = [shell(0), awning(0), shutter_box, shutter, stand(0), tank, ac, pipe, antenna]
    else:
        nodes0 = [shell(0), shutter, stand(0), tank, ac, pipe, antenna]
    nodes1 = [shell(1)] + ([awning(1)] if has_awning else []) + [stand(1),
              box('shutter', (1.73, 2.84, 0.06), (3.265, 1.42, -6.9), 'steel',
                  open=['top', 'bottom', 'left', 'right', 'front'], faces={'back': 'shutter'}),
              box('tank', (1.4, 1.0, 1.1), (2.6, H + 0.48, 4.2), 'tank', open=['bottom', 'front'])]
    nodes2 = [shell(2)] + ([awning(2)] if has_awning else [])
    if not has_awning:
        del mats['awning'], mats['valance']

    r = recipe(name, 250, mats, nodes0,
               [{'distance': 20, 'nodes': nodes1}, {'distance': 50, 'nodes': nodes2}], sheet=SHEET_REL_OTHER)
    folder = os.path.join(HERE, '..', 'town_shop_2f_b')
    os.makedirs(folder, exist_ok=True)
    write(os.path.join(folder, name + '.asset.json'), r)

    # Collision: the walls (the open front too: the recess is a shop, not a room to enter),
    # the deck, the parapet as a wall inside and a rim in short pieces, the awning, the stand,
    # the tank and the air conditioner.
    body = Mesh('body')
    body.quad((-W, H, -D), (W, H, -D), (W, 0, -D), (-W, 0, -D), (0, 0, -1), 'solid')
    body.quad((-W, H, D), (W, H, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'solid')
    for s in (-1, 1):
        body.quad((s * W, 0, -D), (s * W, H, -D), (s * W, H, D), (s * W, 0, D), (s, 0, 0), 'solid')
    i_x, i_z = W - PT, D - PT
    body.quad((-i_x, DECK, -i_z), (i_x, DECK, -i_z), (i_x, DECK, i_z), (-i_x, DECK, i_z), (0, 1, 0), 'solid')
    body.quad((-i_x, H, -i_z), (i_x, H, -i_z), (i_x, DECK, -i_z), (-i_x, DECK, -i_z), (0, 0, 1), 'solid')
    body.quad((-i_x, H, i_z), (i_x, H, i_z), (i_x, DECK, i_z), (-i_x, DECK, i_z), (0, 0, -1), 'solid')
    for s in (-1, 1):
        body.quad((s * i_x, H, -i_z), (s * i_x, H, i_z), (s * i_x, DECK, i_z), (s * i_x, DECK, -i_z), (-s, 0, 0), 'solid')
    rims = [strip_top('rim_front', -W, W, -D, -i_z, H, 4, 'x'), strip_top('rim_back', -W, W, i_z, D, H, 4, 'x'),
            strip_top('rim_west', -W, -i_x, -i_z, i_z, H, 6, 'z'), strip_top('rim_east', i_x, W, -i_z, i_z, H, 6, 'z')]
    awc = Mesh('awning')
    prism_x(awc, -4.45, 4.45, awning_profile(3.32, -8.6, 2.8, 0.32, 3.16, wall_z=-7.0),
            {0: 'awning', 1: 'awning', 2: 'awning', 3: None, 'end': 'awning'})
    stc = Mesh('stand')
    prism_x(stc, -4.0, 2.25, [(-7.7, 0.0), (-7.7, 0.55), (-7.0, 0.75), (-7.0, 0.0)],
            {0: 'solid', 1: 'solid', 2: None, 3: None, 'end': 'solid'})
    nodes = [body.node()] + rims + ([awc.node()] if has_awning else []) + [stc.node(),
                                    slab_box('tank', 1.9, 3.3, DECK, DECK + 0.98, 3.65, 4.75, open=('bottom',)),
                                    slab_box('ac', -2.95, -2.05, DECK, DECK + 0.63, 5.425, 5.775, open=('bottom',))]
    write(os.path.join(folder, name + '_col.asset.json'), col_recipe(name + '_col', nodes))


# --------------------------------------------------------------------------------------------
# C: Maruju, liquor shop on a corner. Shopfronts on the front (-Z) and the right side (+X),
# an awning and a kanban wrapping the corner, a vertical sign set diagonally at the corner,
# two vending machines and crates on the side, a hip roof of blue corrugated iron.
# --------------------------------------------------------------------------------------------

def mirror_x(nodes):
    """The nodes mirrored left for right (x -> -x), faces rewound so they still face out.
    Textures stay readable: every projection works in each face's own right/down frame as seen
    from outside, so a mirrored sign reads the right way round; a decal's `at` (right, up) flips
    its right, and a box's left and right sides swap."""
    swap = {'left': 'right', 'right': 'left'}
    out = []
    for n in nodes:
        n = json.loads(json.dumps(n))
        if n['op'] == 'mesh':
            n['vertices'] = [[r4(-v[0]), v[1], v[2]] for v in n['vertices']]
            n['faces'] = [f[::-1] for f in n['faces']]
        elif n['op'] != 'box':
            raise ValueError('mirror_x: ' + n['op'])
        if 'open' in n:
            n['open'] = [swap.get(k, k) for k in n['open']]
        if 'faces' in n and n['op'] == 'box':
            n['faces'] = {swap.get(k, k): v for k, v in n['faces'].items()}
        for d in n.get('decals', []):
            if n['op'] == 'box':
                d['face'] = swap.get(d['face'], d['face'])
            d['at'] = [r4(-d['at'][0]), d['at'][1]]
        t = n.get('transform')
        if t:
            if 'translate' in t:
                t['translate'][0] = r4(-t['translate'][0])
            if 'rotate' in t:
                rx, ry, rz = t['rotate']
                t['rotate'] = [rx, -ry, -rz]
        out.append(n)
    return out


def shop_c(has_awning=True, left=False):
    name = 'town_shop_2f_c' + ('_left' if left else '') + ('' if has_awning else '_noawning')
    flip = mirror_x if left else (lambda nodes: nodes)
    E = 5.22                             # wall top = the roof's soffit
    OX, OZ = 4.9, 7.4                    # eaves
    ET, RT, RZ = 5.37, 6.5, 2.5          # eave top, ridge top, ridge half length
    sign = ['#2c2a28', '#f4f0e0', '#c8301e']
    sign_s = ['#f4f0e0', '#2c2a28', '#c8301e']
    tate = ['#c8301e', '#f4f0e0', '#f4f0e0']
    val = ['#d8782a', '#f4f0e0', '#d8782a']
    awn = ['#d8782a', '#f4f0e0']
    wall = '#c9d3c0'
    tin = ['#3a6ab0', '#2e5490']
    mats = {
        'mortar': {'color': wall, 'tag': 'wall', 'texture': {
            'pattern': 'speckle', 'size': 16, 'colors': [wall, '#b8c2ae', '#d6decf'],
            'params': {'density': 0.22, 'seed': 7}, 'projection': 'box', 'scale': [1, 1]}},
        'tin_ns': {'color': tin[0], 'tag': 'roof', 'texture': {
            'pattern': 'stripes', 'size': 16, 'colors': tin, 'params': {'count': 8, 'axis': 'u'},
            'projection': 'box', 'scale': [1, 1]}},
        'tin_ew': {'color': tin[0], 'tag': 'roof', 'texture': {
            'pattern': 'stripes', 'size': 16, 'colors': tin, 'params': {'count': 8, 'axis': 'v'},
            'projection': 'box', 'scale': [1, 1]}},
        'ridge': {'color': '#2e5490', 'palette': True, 'tag': 'roof'},
        'fascia': {'color': '#eceae4', 'palette': True},
        'soffit': {'color': '#8a8278', 'palette': True},
        'reveal': {'color': '#a8acb0', 'palette': True},
        'board': {'color': '#3a3a3e', 'palette': True},
        'vend_side': {'color': '#eceae4', 'palette': True},
        'pipe': {'color': '#8e887c', 'palette': True},
        'ac_body': {'color': '#e2e0d6', 'palette': True},
        'awning': {'color': awn[0], 'tag': 'awning', 'texture': {
            'pattern': 'stripes', 'size': 16, 'colors': awn, 'params': {'count': 4, 'axis': 'u'},
            'projection': 'box', 'scale': [1, 1]}},
        'awning_side': {'color': awn[0], 'tag': 'awning', 'texture': {
            'pattern': 'stripes', 'size': 16, 'colors': awn, 'params': {'count': 4, 'axis': 'v'},
            'projection': 'box', 'scale': [1, 1]}},
        'valance': {'color': val[0], 'tag': 'awning', 'texture': sign_texels('valance_c', val)},
        'glass': {'color': '#e0d6b8', 'class': 'emissive', 'tag': 'shopfront', 'texture': cell_tex('glass_c')},
        'window': {'color': '#4e6a7a', 'texture': cell_tex('win_c')},
        'kanban': {'color': sign[0], 'class': 'emissive', 'tag': 'sign', 'texture': sign_texels('sign_c', sign)},
        'kanban_side': {'color': sign_s[0], 'class': 'emissive', 'tag': 'sign', 'texture': sign_texels('sign_cs', sign_s)},
        'tate': {'color': tate[0], 'class': 'emissive', 'tag': 'sign', 'texture': sign_texels('tate_c', tate)},
        'vend_a': {'color': '#eceae4', 'class': 'emissive', 'texture': cell_tex('vend_a')},
        'vend_b': {'color': '#24345a', 'class': 'emissive', 'texture': cell_tex('vend_b')},
        'crate': {'color': '#e8b830', 'texture': {'sheet': 'shopfront', 'cell': 'crate', 'projection': 'box',
                                                  'scale': [0.5, 0.5]}},
        'ac': {'color': '#e2e0d6', 'texture': cell_tex('ac')},
        'antenna': {'color': '#7a7e84', 'double_sided': True, 'texture': cell_tex('antenna')},
    }
    mats.update(back_materials())
    FX0, FX1 = -3.7, 3.9                 # front opening (x)
    SZ0, SZ1 = -6.4, 1.4                 # side opening (z)
    R = 0.4                              # recess depth
    SWIN = [(-3.6, 4.4), (3.6, 4.4)]     # side windows (z, y)

    def shell(level):
        m = Mesh('shell')
        if level == 0:
            front = m.face([(-W, E, -D), (W, E, -D), (W, 0, -D), (FX1, 0, -D), (FX1, 2.5, -D),
                            (FX0, 2.5, -D), (FX0, 0, -D), (-W, 0, -D)], (0, 0, -1), 'mortar')
            m.decal(front, 'window', 'window', (5.0, 1.0), (-0.3, 4.4, -D), (0, 0, -1))
            zr = -D + R
            m.quad((FX0, 2.5, -D), (FX1, 2.5, -D), (FX1, 2.5, zr), (FX0, 2.5, zr), (0, -1, 0), 'reveal')
            m.quad((FX0, 0, -D), (FX0, 2.5, -D), (FX0, 2.5, zr), (FX0, 0, zr), (1, 0, 0), 'reveal')
            m.quad((FX1, 0, -D), (FX1, 2.5, -D), (FX1, 2.5, zr), (FX1, 0, zr), (-1, 0, 0), 'reveal')
            m.quad((FX0, 2.5, zr), (FX1, 2.5, zr), (FX1, 0, zr), (FX0, 0, zr), (0, 0, -1), 'glass')
            side = m.face([(W, E, -D), (W, E, D), (W, 0, D), (W, 0, SZ1), (W, 2.5, SZ1), (W, 2.5, SZ0),
                           (W, 0, SZ0), (W, 0, -D)], (1, 0, 0), 'mortar')
            for i, (z, y) in enumerate(SWIN):
                m.decal(side, f'window_{i}', 'window', (3.2, 1.0), (W, y, z), (1, 0, 0))
            xr = W - R
            m.quad((W, 2.5, SZ0), (W, 2.5, SZ1), (xr, 2.5, SZ1), (xr, 2.5, SZ0), (0, -1, 0), 'reveal')
            m.quad((W, 0, SZ0), (W, 2.5, SZ0), (xr, 2.5, SZ0), (xr, 0, SZ0), (0, 0, 1), 'reveal')
            m.quad((W, 0, SZ1), (W, 2.5, SZ1), (xr, 2.5, SZ1), (xr, 0, SZ1), (0, 0, -1), 'reveal')
            m.quad((xr, 2.5, SZ0), (xr, 2.5, SZ1), (xr, 0, SZ1), (xr, 0, SZ0), (1, 0, 0), 'glass')
            back = m.quad((-W, E, D), (W, E, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'mortar')
            back_decals(m, back)
        elif level == 1:
            front = m.quad((-W, E, -D), (W, E, -D), (W, 0, -D), (-W, 0, -D), (0, 0, -1), 'mortar')
            m.decal(front, 'glass', 'glass', (FX1 - FX0, 2.48), ((FX0 + FX1) / 2, 1.25, -D), (0, 0, -1))
            m.decal(front, 'window', 'window', (5.0, 1.0), (-0.3, 4.4, -D), (0, 0, -1))
            side = m.quad((W, E, -D), (W, E, D), (W, 0, D), (W, 0, -D), (1, 0, 0), 'mortar')
            m.decal(side, 'glass_side', 'glass', (SZ1 - SZ0, 2.48), (W, 1.25, (SZ0 + SZ1) / 2), (1, 0, 0))
            m.quad((-W, E, D), (W, E, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'mortar')
        else:
            if has_awning:
                bands(m, 'front', -W, W, -D, [0, 3.05, 3.95, E], ['glass', 'kanban', 'window'])
            else:
                bands(m, 'front', -W, W, -D, [0, 2.5, KY0, 3.95, E], ['glass', 'mortar', 'kanban', 'window'])
            m.quad((W, E, -D), (W, E, D), (W, 0, D), (W, 0, -D), (1, 0, 0), 'mortar')
            m.quad((-W, E, D), (W, E, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'mortar')
        m.quad((-W, E, -D), (-W, E, D), (-W, 0, D), (-W, 0, -D), (-1, 0, 0), 'mortar')
        return m.node()

    def roof(level):
        m = Mesh('roof')
        e = [(-OX, ET, -OZ), (OX, ET, -OZ), (OX, ET, OZ), (-OX, ET, OZ)]
        r1, r2 = (0, RT, -RZ), (0, RT, RZ)
        m.face([e[0], e[1], r1], (0, 1, -0.3), 'tin_ns')
        m.face([e[2], e[3], r2], (0, 1, 0.3), 'tin_ns')
        m.face([e[1], e[2], r2, r1], (0.3, 1, 0), 'tin_ew')
        m.face([e[3], e[0], r1, r2], (-0.3, 1, 0), 'tin_ew')
        if level < 2:
            b = [(x, E, z) for x, _, z in e]
            if level == 0:
                for i, out in enumerate([(0, 0, -1), (1, 0, 0), (0, 0, 1), (-1, 0, 0)]):
                    j = (i + 1) % 4
                    m.quad(e[i], e[j], b[j], b[i], out, 'fascia')
            m.face(b, (0, -1, 0), 'soffit')
        return m.node()

    # The awning wraps the corner: a front run along x and a side run along z, mitred.
    AW_TOP, AW_OUT, AW_VAL, AW_UND = 3.0, 2.62, 0.25, 2.62
    XO, ZO = 5.7, -8.2                   # outer edge of the side run, of the front run
    XL, ZE = -4.45, 1.6                  # free ends

    def awning(level, wall=(-6.98, 4.48), mat=None):
        m = Mesh('awning')
        wz, wx = wall
        a = mat or {}
        top, top_s = a.get('top', 'awning'), a.get('top_s', 'awning_side')
        val_f, val_s = a.get('val', 'valance'), a.get('val_s', 'awning_side')
        und, und_s = a.get('und', 'awning'), a.get('und_s', 'awning_side')
        lo = AW_OUT - AW_VAL
        W0, W1, W2 = (XL, AW_TOP, wz), (wx, AW_TOP, wz), (wx, AW_TOP, ZE)      # wall line, top
        O0, O1, O2 = (XL, AW_OUT, ZO), (XO, AW_OUT, ZO), (XO, AW_OUT, ZE)      # outer line, top
        L0, L1, L2 = (XL, lo, ZO), (XO, lo, ZO), (XO, lo, ZE)                  # outer line, bottom
        U0, U1, U2 = (XL, AW_UND, wz), (wx, AW_UND, wz), (wx, AW_UND, ZE)      # wall line, bottom
        m.quad(W0, W1, O1, O0, (0, 1, -0.3), top)
        if level == 2:
            return m.node()
        m.quad(W1, W2, O2, O1, (0.3, 1, 0), top_s)
        m.quad(O0, O1, L1, L0, (0, 0, -1), val_f)
        m.quad(O1, O2, L2, L1, (1, 0, 0), val_s)
        m.quad(L0, L1, U1, U0, (0, -1, 0), und)
        m.quad(L1, L2, U2, U1, (0, -1, 0), und_s)
        if level == 0:
            m.quad(W0, O0, L0, U0, (-1, 0, 0), top)
            m.quad(W2, O2, L2, U2, (0, 0, 1), top_s)
        return m.node()

    # The kanban wraps the corner too: an L-shaped band, its inside sunk into the walls.
    KY0, KY1, KO = 3.05, 3.85, 0.3
    if not has_awning:
        KY0 = 3.11                      # over the bounce awning's roller (top 3.09)

    def kanban(level):
        m = Mesh('kanban')
        x0, z1 = -4.25, 1.6
        xo, zo = W + KO, -D - KO
        xi, zi = W - 0.02, -D + 0.02
        m.quad((x0, KY1, zo), (xo, KY1, zo), (xo, KY0, zo), (x0, KY0, zo), (0, 0, -1), 'kanban')
        m.quad((xo, KY1, zo), (xo, KY1, z1), (xo, KY0, z1), (xo, KY0, zo), (1, 0, 0), 'kanban_side')
        m.face([(x0, KY1, zi), (x0, KY1, zo), (xo, KY1, zo), (xo, KY1, z1), (xi, KY1, z1), (xi, KY1, zi)],
               (0, 1, 0), 'board')
        if level == 0:
            m.face([(x0, KY0, zi), (x0, KY0, zo), (xo, KY0, zo), (xo, KY0, z1), (xi, KY0, z1), (xi, KY0, zi)],
                   (0, -1, 0), 'board')
            m.quad((x0, KY1, zi), (x0, KY1, zo), (x0, KY0, zo), (x0, KY0, zi), (-1, 0, 0), 'board')
            m.quad((xi, KY1, z1), (xo, KY1, z1), (xo, KY0, z1), (xi, KY0, z1), (0, 0, 1), 'board')
        return m.node()

    def tate(level):
        return box('tate', (0.16, 1.3, 0.7), (4.733, 4.51, -7.233), 'board',
                   open=['front'] + (['top', 'bottom'] if level else []),
                   faces={'left': 'tate', 'right': 'tate'}, rotate=[0, -45, 0])

    def vending(level):
        if level:                                # their faces only, toward the side street
            m = Mesh('vending')
            for z0, z1, mat in ((2.05, 3.05, 'vend_a'), (3.1, 4.1, 'vend_b')):
                m.quad((5.23, 1.83, z0), (5.23, 1.83, z1), (5.23, 0, z1), (5.23, 0, z0), (1, 0, 0), mat)
            return [m.node()]
        op = ['left', 'bottom']
        return [box('vend_0', (0.75, 1.83, 1.0), (4.855, 0.915, 2.55), 'vend_side', open=op, faces={'right': 'vend_a'}),
                box('vend_1', (0.75, 1.83, 1.0), (4.855, 0.915, 3.6), 'board', open=op, faces={'right': 'vend_b'})]

    crates = box('crates', (0.6, 1.0, 1.0), (4.79, 0.5, 4.75), 'crate', open=['left', 'bottom'])
    ac = box('ac', (0.28, 0.6, 0.8), (4.62, 4.3, 6.2), 'ac_body', open=['left'], faces={'right': 'ac'})
    pipe = box('downpipe', (0.1, 5.1, 0.1), (-4.36, 2.55, -7.03), 'pipe', open=['top', 'bottom'])
    ridge = box('ridge', (0.3, 0.14, 2 * RZ + 0.3), (0, RT, 0), 'ridge', open=['bottom'])
    slope = (RT - ET) / OX
    antenna = crossed_quads('antenna', (-1.6, RT - slope * 1.6 - 0.1, 1.0), 1.4, 1.8, 'antenna')

    awl = (lambda level: [awning(level)]) if has_awning else (lambda level: [])
    nodes0 = [shell(0), roof(0), ridge] + awl(0) + [kanban(0), tate(0)] + vending(0) + [crates, ac, pipe, antenna]
    nodes1 = [shell(1), roof(1)] + awl(1) + [kanban(1), tate(1)] + vending(1)
    nodes2 = [shell(2), roof(2)] + awl(2)
    if not has_awning:
        for k in ('awning', 'awning_side', 'valance'):
            del mats[k]

    r = recipe(name, 250, mats, flip(nodes0),
               [{'distance': 20, 'nodes': flip(nodes1)}, {'distance': 50, 'nodes': flip(nodes2)}],
               sheet=SHEET_REL_OTHER)
    folder = os.path.join(HERE, '..', 'town_shop_2f_c')
    os.makedirs(folder, exist_ok=True)
    write(os.path.join(folder, name + '.asset.json'), r)

    # Collision: the walls, the hip roof as a slab (its fascias are the lips), the awning round
    # the corner, the kanban ledge in pieces, the vending machines and the crates (steps up).
    body = Mesh('body')
    body.quad((-W, E, -D), (W, E, -D), (W, 0, -D), (-W, 0, -D), (0, 0, -1), 'solid')
    body.quad((-W, E, D), (W, E, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'solid')
    for s in (-1, 1):
        body.quad((s * W, 0, -D), (s * W, E, -D), (s * W, E, D), (s * W, 0, D), (s, 0, 0), 'solid')
    roofc = Mesh('roof')
    e = [(-OX, ET, -OZ), (OX, ET, -OZ), (OX, ET, OZ), (-OX, ET, OZ)]
    b = [(x, ET - 0.2, z) for x, _, z in e]
    r1, r2 = (0, RT, -RZ), (0, RT, RZ)
    roofc.face([e[0], e[1], r1], (0, 1, -0.3), 'solid')
    roofc.face([e[2], e[3], r2], (0, 1, 0.3), 'solid')
    roofc.face([e[1], e[2], r2, r1], (0.3, 1, 0), 'solid')
    roofc.face([e[3], e[0], r1, r2], (-0.3, 1, 0), 'solid')
    for i, out in enumerate([(0, 0, -1), (1, 0, 0), (0, 0, 1), (-1, 0, 0)]):
        j = (i + 1) % 4
        roofc.quad(e[i], e[j], b[j], b[i], out, 'solid')
    roofc.face(b, (0, -1, 0), 'solid')
    aw = awning(0, wall=(-7.0, 4.5), mat={k: 'awning' for k in ('top', 'top_s', 'val', 'val_s', 'und', 'und_s')})
    ledges = [ledge('kanban_front', -4.25, W + KO, KY0, KY1, -D - KO, -D, 3, 'x', open=('back',)),
              ledge('kanban_side', W, W + KO, KY0, KY1, -D, 1.6, 3, 'z', open=('left',))]
    nodes = [body.node(), roofc.node()] + ([aw] if has_awning else []) + ledges + [
        slab_box('vending', W, W + 0.73, 0, 1.83, 2.05, 4.1, open=('left', 'bottom')),
        slab_box('crates', W, W + 0.58, 0, 1.0, 4.25, 5.25, open=('left', 'bottom'))]
    write(os.path.join(folder, name + '_col.asset.json'), col_recipe(name + '_col', flip(nodes)))


# --------------------------------------------------------------------------------------------



def pack_sheet():
    """Shelf-pack every cell into one PNG, 256 wide; named cells in shopfront.sheet.json."""
    cells = dict(CELLS)
    order = sorted(cells, key=lambda n: (-cells[n].height, n))
    x = y = shelf = 0
    rects = {}
    for n in order:
        im = cells[n]
        if x + im.width > 256:
            x, y, shelf = 0, y + shelf, 0
        rects[n] = [x, y, im.width, im.height]
        x += im.width
        shelf = max(shelf, im.height)
    h = y + shelf
    h = (h + 7) // 8 * 8
    sheet = Image.new('RGBA', (256, h), (0, 0, 0, 0))
    for n, (x, y, w, hh) in rects.items():
        sheet.paste(cells[n], (x, y))
    os.makedirs(ART, exist_ok=True)
    sheet.save(os.path.join(ART, 'shopfront.png'))
    with open(os.path.join(ART, 'shopfront.sheet.json'), 'w') as f:
        json.dump({'format': 'mei-sheet', 'version': 1, 'cells': {n: rects[n] for n in sorted(rects)}}, f, indent=1)
        f.write('\n')


if __name__ == '__main__':
    draw_sheet()
    shop_a()
    shop_b()
    shop_c()
    shop_a(has_awning=False)
    shop_b(has_awning=False)
    shop_c(has_awning=False)
    shop_c(left=True)
    shop_c(has_awning=False, left=True)
    pack_sheet()
