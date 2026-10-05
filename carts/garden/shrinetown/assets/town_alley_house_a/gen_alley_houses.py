"""Shrine town's back-alley houses (spec 3.3), and the town's common roof tile and plaster.

Writes, from this folder:
  art/town_common.png, art/town_common.sheet.json   the common set's repeating tiles, for every
                                                    town family: kawara (grey J-tile),
                                                    kawara_blue (glazed), tin (galvanised
                                                    cladding), tin_red (painted roof sheet),
                                                    plaster (cream mortar), plaster_grey (cement)
  art/alley.png, art/alley.sheet.json               the alley houses' doors, windows, railings
  town_alley_house_a.asset.json, ..._col            hip roof of grey kawara, ridge 6.0
  ../town_alley_house_b/town_alley_house_b.asset.json, ..._col
                                                    shed roof of painted tin, 6.5 front to 7.0 back
  ../town_alley_house_c/town_alley_house_c.asset.json, ..._col
                                                    gable of blue kawara, drying platform at 8.0

Run with Pillow: python3 gen_alley_houses.py. The PNGs and the recipes are committed, so
building the world needs none of this.

Using the common tiles from another family: declare the sheet with its path from your recipe,
`"sheets": {"town_common": {"image": "../town_alley_house_a/art/town_common.png"}}`, and give a
material `{"sheet": "town_common", "cell": "kawara", "projection": "box", "scale": [2, 2]}`.
Every tile is 32 x 32 texels, 4-bit, and meant for these scales (one repeat, in metres):
kawara and kawara_blue [2, 2] (a tile 0.25 m wide, courses 0.25 m), tin and tin_red [2, 2]
(corrugations 0.25 m; at this scale a face up to 16 m long is not split), plaster and
plaster_grey [2, 2] (6 cm a texel). Roof tiles run their troughs along v, so a slope that
falls along X (a hip end) takes `"rotate": 90`, which shares the tile. Each tile is 512 bytes
of VRAM.

Every house: origin at the centre of its 9.5 x 8.5 m footprint at street level, front (the
door) toward -Z, walls on the footprint, eaves 0.3-0.35 m beyond them. Alleys are 2.5 m
between walls, so about 1.8 m between eaves. Levels: L1 from 16 m (30 triangles at most), L2
from 40 m (12 at most), as spec 8.2 asks.
"""
import json
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, 'art')
ROOT = os.path.dirname(HERE)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def hsh(x, y, s=0):
    """A small deterministic hash in 0..255."""
    v = (x * 374761393 + y * 668265263 + s * 2246822519) & 0xFFFFFFFF
    v = ((v ^ (v >> 13)) * 1274126177) & 0xFFFFFFFF
    return (v ^ (v >> 16)) & 0xFF


def rect(d, x0, y0, x1, y1, fill):
    d.rectangle([x0, y0, x1, y1], fill=fill)


# --------------------------------------------------------------------------------------------
# The common tiles (town_common.png): 32 x 32 each, in one row
# --------------------------------------------------------------------------------------------

def kawara(trough, mid, crest, lip, joint, odd, seed):
    """J-tile (sangawara) seen from above: 8 tiles across u (4 texels each: trough, mid, crest,
    mid, a soft wave) and 8 courses down v (4 texels each: the lit lower lip of the course above,
    two rows of the wave, the shadow joint). The courses, not the waves, are what reads from a
    neighbouring roof. A tile here and there is a shade off, as on any old roof."""
    im = Image.new('RGBA', (32, 32))
    for y in range(32):
        for x in range(32):
            col, cx = divmod(x, 4)
            row, cy = divmod(y, 4)
            c = [trough, mid, crest, mid][cx]
            if cy == 0:
                c = lip if cx != 0 else mid
            elif cy == 3:
                c = joint
            elif hsh(col, row, seed) < 22:
                c = odd
            im.putpixel((x, y), c)
    return im


def tin(dark, mid, light, seam, rust, seed, seam_row=31):
    """Corrugated sheet: corrugations along v every 4 texels across u; one lap seam across the
    tile, and a few rust streaks running down from it in the troughs."""
    im = Image.new('RGBA', (32, 32))
    for y in range(32):
        for x in range(32):
            col, cx = divmod(x, 4)
            c = [dark, mid, light, mid][cx]
            if y == seam_row:
                c = seam
            elif cx == 0 and hsh(col, 1, seed) < 100 and (y - seam_row - 1) % 32 < 3 + hsh(col, 0, seed) % 9:
                c = rust
            im.putpixel((x, y), c)
    return im


def plaster(base, light, shade, streak, seed):
    """Trowelled mortar: a few soft patches a shade lighter or darker, a few faint rain streaks.
    Low contrast on purpose: walls fill the screen in a 2.5 m alley, and anything busier reads as
    stone and shimmers at 320 x 240."""
    im = Image.new('RGBA', (32, 32), base)
    for by in range(8):
        for bx in range(8):
            v = hsh(bx, by, seed)
            c = light if v < 34 else shade if v > 226 else None
            if c:
                for dy in range(4):
                    for dx in range(4):
                        if (dx, dy) not in ((0, 0), (3, 0), (0, 3), (3, 3)):
                            im.putpixel((bx * 4 + dx, by * 4 + dy), c)
    for k in range(3):
        x = 3 + hsh(k, 9, seed) % 26
        y0 = hsh(k, 11, seed) % 20
        for y in range(y0, y0 + 6 + hsh(k, 12, seed) % 8):
            im.putpixel((x, y % 32), streak)
    return im


COMMON = {
    'kawara': kawara(rgb('#4a5058'), rgb('#565c64'), rgb('#62686f'), rgb('#70767e'), rgb('#2c2f34'),
                     rgb('#4e555e'), 3),
    'kawara_blue': kawara(rgb('#34404f'), rgb('#3e4c5e'), rgb('#4c5a6e'), rgb('#62728a'), rgb('#222a34'),
                          rgb('#44526a'), 5),
    'tin': tin(rgb('#767c80'), rgb('#868c90'), rgb('#9ca2a4'), rgb('#5c6064'), rgb('#7e6a54'), 7),
    'tin_red': tin(rgb('#7a3426'), rgb('#8a3a2a'), rgb('#9c4632'), rgb('#5a2a20'), rgb('#6e4a32'), 9),
    'plaster': plaster(rgb('#d9cfb9'), rgb('#e0d7c3'), rgb('#d1c7b0'), rgb('#cbc0a8'), 11),
    'plaster_grey': plaster(rgb('#b0aca2'), rgb('#b7b3aa'), rgb('#a8a49a'), rgb('#a09c91'), 13),
}
COMMON_ORDER = ['kawara', 'kawara_blue', 'tin', 'tin_red', 'plaster', 'plaster_grey']

# --------------------------------------------------------------------------------------------
# The alley sheet (alley.png): fit cells for the houses
# --------------------------------------------------------------------------------------------

AL, AL_D, AL_L = rgb('#c4c8cc'), rgb('#6e747a'), rgb('#dde0e2')
FROST, FROST_D, FROST_L = rgb('#c8d0d0'), rgb('#a8b4b6'), rgb('#e2e8e6')
GLASS, GLASS_L = rgb('#4e6a7a'), rgb('#7a98a6')
CLEAR = (0, 0, 0, 0)


def frame(d, x0, y0, x1, y1, c=AL):
    d.rectangle([x0, y0, x1, y1], outline=c)


def draw_alley():
    cells = {}

    # genkan: two aluminium sliding doors, frosted glass in 2 x 3 lites, a transom over them,
    # the house name plate on the left jamb. 1.7 x 2.1 m.
    im = Image.new('RGBA', (32, 32), AL)
    d = ImageDraw.Draw(im)
    rect(d, 0, 0, 31, 31, AL_D)
    rect(d, 1, 1, 30, 30, AL)
    rect(d, 2, 2, 29, 6, FROST)                                  # transom
    rect(d, 2, 4, 29, 4, FROST_D)
    for x0 in (2, 16):                                           # the two leaves
        rect(d, x0, 8, x0 + 13, 29, AL)
        for r in range(3):
            for c in range(2):
                gx, gy = x0 + 1 + c * 6, 9 + r * 7
                rect(d, gx, gy, gx + 5, gy + 5, FROST)
                d.point((gx + 1, gy + 1), fill=FROST_L)
                d.point((gx + 2, gy + 1), fill=FROST_L)
                rect(d, gx, gy + 5, gx + 5, gy + 5, FROST_D)
    rect(d, 15, 8, 16, 29, AL_D)                                 # the meeting stiles
    rect(d, 13, 18, 13, 19, AL_D)                                # handles
    rect(d, 18, 18, 18, 19, AL_D)
    rect(d, 0, 30, 31, 31, rgb('#8e887c'))                       # sill
    cells['genkan'] = im

    # win_grille: frosted two-pane sash behind a grille of vertical bars (a kitchen or a
    # bathroom on the alley). 1.6 x 0.9 m.
    im = Image.new('RGBA', (32, 16), AL)
    d = ImageDraw.Draw(im)
    rect(d, 1, 1, 30, 14, FROST)
    rect(d, 1, 1, 30, 2, FROST_L)
    rect(d, 15, 1, 16, 14, AL)
    for x in range(2, 31, 4):
        rect(d, x, 1, x, 14, AL_L)
        d.point((x + 1, 14), fill=AL_D)
    rect(d, 0, 0, 31, 0, AL_L)
    rect(d, 0, 15, 31, 15, AL_D)
    cells['win_grille'] = im

    # win_lit: an upstairs sash with curtains drawn, lit from inside (emissive at night).
    im = Image.new('RGBA', (32, 16), AL)
    d = ImageDraw.Draw(im)
    rect(d, 1, 1, 30, 14, rgb('#e8cc94'))
    for x in range(1, 31, 3):                                    # curtain folds
        rect(d, x, 2, x, 14, rgb('#d4b07a'))
    rect(d, 13, 1, 18, 14, rgb('#f4e6c0'))                       # the gap, brighter
    rect(d, 15, 1, 16, 14, AL)
    rect(d, 1, 1, 30, 1, rgb('#b89060'))                         # curtain rail shadow
    rect(d, 0, 15, 31, 15, AL_D)
    cells['win_lit'] = im

    # win_dark: an upstairs sash, clear glass, a dark room, a reflection.
    im = Image.new('RGBA', (32, 16), AL)
    d = ImageDraw.Draw(im)
    rect(d, 1, 1, 30, 14, GLASS)
    for k in range(5):
        d.point((4 + k, 3 + k * 2), fill=GLASS_L)
        d.point((19 + k, 3 + k * 2), fill=GLASS_L)
    rect(d, 1, 10, 13, 14, rgb('#3e5260'))                       # a shelf, shadows
    rect(d, 15, 1, 16, 14, AL)
    rect(d, 0, 15, 31, 15, AL_D)
    cells['win_dark'] = im

    # win_small: a small frosted bathroom window with a grille. 0.6 x 0.6 m.
    im = Image.new('RGBA', (16, 16), AL)
    d = ImageDraw.Draw(im)
    rect(d, 1, 1, 14, 14, FROST)
    rect(d, 1, 1, 14, 2, FROST_L)
    for x in range(2, 15, 4):
        rect(d, x, 1, x, 14, AL_L)
    rect(d, 0, 15, 15, 15, AL_D)
    cells['win_small'] = im

    # balcony_door: two tall glass leaves onto a balcony, a lace curtain in one. 1.8 x 1.9 m.
    im = Image.new('RGBA', (32, 32), AL)
    d = ImageDraw.Draw(im)
    rect(d, 1, 1, 30, 30, GLASS)
    rect(d, 2, 2, 14, 29, rgb('#d8dcd4'))                        # lace
    for x in range(3, 14, 3):
        rect(d, x, 3, x, 29, rgb('#c4c8c0'))
    for k in range(7):
        d.point((19 + k, 5 + k * 3), fill=GLASS_L)
        d.point((20 + k, 5 + k * 3), fill=GLASS_L)
    rect(d, 15, 1, 16, 30, AL)
    rect(d, 0, 31, 31, 31, AL_D)
    cells['balcony_door'] = im

    # rail: an aluminium balcony railing, a cutout: top and bottom rails, balusters. 0.9 m tall.
    im = Image.new('RGBA', (64, 16), CLEAR)
    d = ImageDraw.Draw(im)
    rect(d, 0, 0, 63, 1, AL_L)
    rect(d, 0, 2, 63, 2, AL_D)
    rect(d, 0, 14, 63, 15, AL)
    for x in range(1, 64, 4):
        rect(d, x, 3, x, 13, AL)
    rect(d, 0, 0, 1, 15, AL)
    rect(d, 62, 0, 63, 15, AL)
    cells['rail'] = im

    # hoshi_rail: the drying platform's rail, galvanised pipe: top rail, a mid rail, posts.
    im = Image.new('RGBA', (64, 16), CLEAR)
    d = ImageDraw.Draw(im)
    STEEL, STEEL_D = rgb('#b4b8bc'), rgb('#7a7e84')
    rect(d, 0, 0, 63, 1, STEEL)
    rect(d, 0, 7, 63, 7, STEEL_D)
    rect(d, 0, 15, 63, 15, STEEL_D)
    for x in (0, 21, 42, 62):
        rect(d, x, 0, x + 1, 15, STEEL)
    cells['hoshi_rail'] = im

    # hoshi_frame: the platform's legs, a cutout: two posts and an X brace.
    im = Image.new('RGBA', (32, 16), CLEAR)
    d = ImageDraw.Draw(im)
    rect(d, 0, 0, 1, 15, STEEL)
    rect(d, 30, 0, 31, 15, STEEL)
    rect(d, 0, 0, 31, 1, STEEL_D)
    d.line([(2, 2), (29, 15)], fill=STEEL_D)
    d.line([(29, 2), (2, 15)], fill=STEEL_D)
    cells['hoshi_frame'] = im

    # hoshi_deck: the platform's deck seen from above, galvanised planks with dark gaps.
    im = Image.new('RGBA', (32, 16), STEEL)
    d = ImageDraw.Draw(im)
    for y in range(0, 16, 3):
        rect(d, 0, y, 31, y, rgb('#4a4e54'))
    for y in range(1, 16, 3):
        rect(d, 0, y, 31, y, rgb('#c8ccce'))
    rect(d, 0, 0, 0, 15, STEEL_D)
    rect(d, 31, 0, 31, 15, STEEL_D)
    cells['hoshi_deck'] = im
    return cells


def pack(cells, width, name):
    order = sorted(cells, key=lambda n: (-cells[n].height, n))
    x = y = shelf = 0
    rects = {}
    for n in order:
        im = cells[n]
        if x + im.width > width:
            x, y, shelf = 0, y + shelf, 0
        rects[n] = [x, y, im.width, im.height]
        x += im.width
        shelf = max(shelf, im.height)
    h = (y + shelf + 7) // 8 * 8
    sheet = Image.new('RGBA', (width, h), CLEAR)
    for n, (x, y, w, hh) in rects.items():
        sheet.paste(cells[n], (x, y))
    os.makedirs(ART, exist_ok=True)
    sheet.save(os.path.join(ART, name + '.png'))
    with open(os.path.join(ART, name + '.sheet.json'), 'w') as f:
        json.dump({'format': 'mei-sheet', 'version': 1, 'cells': {n: rects[n] for n in sorted(rects)}},
                  f, indent=1)
        f.write('\n')


def pack_common():
    sheet = Image.new('RGBA', (32 * len(COMMON_ORDER), 32), CLEAR)
    rects = {}
    for i, n in enumerate(COMMON_ORDER):
        sheet.paste(COMMON[n], (32 * i, 0))
        rects[n] = [32 * i, 0, 32, 32]
    os.makedirs(ART, exist_ok=True)
    sheet.save(os.path.join(ART, 'town_common.png'))
    with open(os.path.join(ART, 'town_common.sheet.json'), 'w') as f:
        json.dump({'format': 'mei-sheet', 'version': 1, 'cells': rects}, f, indent=1)
        f.write('\n')


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

    def __init__(self, id):
        self.id = id
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
        """`centre` in the mesh's coordinates; converted to the face's right/up."""
        x, y, z = centre
        at = {(0, 0, -1): [x, y], (0, 0, 1): [-x, y], (1, 0, 0): [z, y], (-1, 0, 0): [-z, y]}[tuple(normal)]
        self.decals.append({'id': id, 'face': face, 'material': mat,
                            'size': [r4(size[0]), r4(size[1])], 'at': [r4(at[0]), r4(at[1])]})

    def node(self):
        n = {'id': self.id, 'op': 'mesh', 'vertices': [list(v) for v in self.v], 'faces': self.f,
             'face_materials': self.fm}
        if self.decals:
            n['decals'] = self.decals
        return n


def box(id, size, centre, mat, open=None, faces=None):
    n = {'id': id, 'op': 'box', 'size': [r4(s) for s in size], 'material': mat}
    if open:
        n['open'] = open
    if faces:
        n['faces'] = faces
    n['transform'] = {'translate': [r4(c) for c in centre]}
    return n


def prism_x(m, x0, x1, profile, mats, ends=True):
    """Faces of a prism along X whose cross-section `profile` is a list of (z, y) round the
    outline; mats[i] the material of the side from point i to i + 1 (None leaves it out), and
    mats['end'] the two ends."""
    n = len(profile)
    cz = sum(p[0] for p in profile) / n
    cy = sum(p[1] for p in profile) / n
    for i in range(n):
        if mats.get(i) is None:
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


def write(path, recipe):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(recipe, f, indent=1, ensure_ascii=False)
        f.write('\n')


VERIFY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}
W, D = 4.75, 4.25           # half the footprint: x (9.5) and z (8.5)
K = 0.265                   # roof slope of the tiled roofs (14.8 degrees), render and collision
L1, L2 = 16, 40             # level switch distances (spec 8.2)
PL = 0.3                    # the concrete footing band's height
GK, GY = (1.7, 2.0), PL + 1.01   # the front door: size, centre height (it stands on the footing)


def sheets(folder):
    """The sheets' paths from a house's folder."""
    pre = '' if folder == 'town_alley_house_a' else '../town_alley_house_a/'
    return {'town_common': {'image': pre + 'art/town_common.png'},
            'alley': {'image': pre + 'art/alley.png'},
            'shopfront': {'image': '../town_shop_2f_a/art/shopfront.png'}}


def common(cell, scale, **kw):
    t = {'sheet': 'town_common', 'cell': cell, 'projection': 'box', 'scale': scale}
    t.update(kw)
    return t


def alley(cell, **kw):
    t = {'sheet': 'alley', 'cell': cell, 'projection': 'fit'}
    t.update(kw)
    return t


def opening_materials():
    """Doors and windows, shared by the three houses."""
    return {
        'genkan': {'color': '#c4c8cc', 'tag': 'door', 'texture': alley('genkan')},
        'win_grille': {'color': '#c8d0d0', 'texture': alley('win_grille')},
        'win_small': {'color': '#c8d0d0', 'texture': alley('win_small')},
        'win_dark': {'color': '#4e6a7a', 'texture': alley('win_dark')},
        'win_lit': {'color': '#e8cc94', 'class': 'emissive', 'tag': 'window', 'texture': alley('win_lit')},
    }


def recipe(name, budget, materials, nodes, levels):
    return {'format': 'mei-asset', 'version': 1, 'name': name, 'sheets': sheets(name),
            'budget': {'triangles': budget}, 'materials': materials, 'lighting': LIGHT,
            'verification': VERIFY, 'nodes': nodes,
            'lod': {'levels': [{'distance': L1, 'nodes': levels[0]}, {'distance': L2, 'nodes': levels[1]}]}}


def col_recipe(name, nodes, budget=120):
    return {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': {'triangles': budget},
            'materials': {'solid': {'color': '#ffffff', 'palette': True}},
            'lighting': LIGHT, 'verification': VERIFY, 'nodes': nodes}


def walls(id, tops, mats, gable=None, plinth=None):
    """The four walls on the footprint, no top or bottom. tops: wall-top heights at the front
    (-Z) and back (+Z) edges (a shed roof gives two). mats: front, back, left, right. gable: the
    apex height of the side walls (a roof ridged along X), or None. plinth: (height, material),
    a concrete footing band round all four walls (8 triangles), or None. Returns the mesh and
    the four faces' indices (above the plinth)."""
    m = Mesh(id)
    yf, yb = tops
    p = plinth[0] if plinth else 0
    f = m.quad((-W, yf, -D), (W, yf, -D), (W, p, -D), (-W, p, -D), (0, 0, -1), mats[0])
    b = m.quad((-W, yb, D), (W, yb, D), (W, p, D), (-W, p, D), (0, 0, 1), mats[1])
    sides = []
    for s, mat in ((-1, mats[2]), (1, mats[3])):
        x = s * W
        pts = [(x, p, -D), (x, yf, -D)] + ([(x, gable, 0)] if gable else []) + [(x, yb, D), (x, p, D)]
        sides.append(m.face(pts, (s, 0, 0), mat))
    if plinth:
        pm = plinth[1]
        for z in (-D, D):
            m.quad((-W, p, z), (W, p, z), (W, 0, z), (-W, 0, z), (0, 0, z), pm)
        for x in (-W, W):
            m.quad((x, p, -D), (x, p, D), (x, 0, D), (x, 0, -D), (x, 0, 0), pm)
    return m, (f, b, sides[0], sides[1])


def strip_top(m, x0, x1, z0, z1, y0, y1, pieces, mat):
    """A sloped floor strip (y0 at z0, y1 at z1) cut into `pieces` along X, sharing edges, so
    no floor triangle is long and thin."""
    for i in range(pieces):
        a, b = x0 + (x1 - x0) * i / pieces, x0 + (x1 - x0) * (i + 1) / pieces
        m.quad((a, y0, z0), (b, y0, z0), (b, y1, z1), (a, y1, z1), (0, 1, 0), mat)


def slab_box(m, x0, x1, y0, y1, z0, z1, mat='solid', open=()):
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


def hisashi(m, x0, x1, y_wall, out_z, drop, thick, mats, ends=True, wall_z=-D + 0.02):
    """A pent roof on the front wall: from the wall (sunk 2 cm) out to out_z, falling `drop`."""
    prof = [(wall_z, y_wall), (out_z, y_wall - drop), (out_z, y_wall - drop - thick), (wall_z, y_wall - thick)]
    prism_x(m, x0, x1, prof, {0: mats[0], 1: mats[1], 2: mats[2], 3: None, 'end': mats[1]}, ends=ends)


# --------------------------------------------------------------------------------------------
# A: a two-storey house of cream mortar under a hipped roof of grey kawara (near square, so the
# ridge is 1 m long). A pent roof over the door and the kitchen window, a TV antenna.
# Ridge 6.0, eaves 4.78 all round.
# --------------------------------------------------------------------------------------------

def house_a():
    name = 'town_alley_house_a'
    RT, O, T = 6.0, 0.35, 0.15          # ridge (top of the tiles), overhang, roof thickness
    EX, EZ = W + O, D + O               # eave line
    RX = W - D                          # half the ridge's length (0.5)
    ye = RT - K * O - K * D             # tile top at the eaves (4.781)
    WT = 4.80                           # wall top, 7 cm under the tiles
    mats = {
        'plaster': {'color': '#ddd3bd', 'tag': 'wall', 'texture': common('plaster', [2, 2])},
        'kawara': {'color': '#565c64', 'tag': 'roof', 'texture': common('kawara', [2, 2])},
        'kawara_r': {'color': '#565c64', 'tag': 'roof', 'texture': common('kawara', [2, 2], rotate=90)},
        'eave': {'color': '#2c2f34', 'palette': True, 'tag': 'roof'},
        'soffit': {'color': '#5a4a3e', 'palette': True},
        'footing': {'color': '#8e887c', 'palette': True},
        'hisashi': {'color': '#6a7078', 'palette': True, 'tag': 'roof'},
        'antenna': {'color': '#7a7e84', 'double_sided': True,
                    'texture': {'sheet': 'shopfront', 'cell': 'antenna', 'projection': 'fit'}},
        'kawara_ds': {'color': '#565c64', 'tag': 'roof', 'double_sided': True, 'texture': common('kawara', [2, 2])},
        'kawara_r_ds': {'color': '#565c64', 'tag': 'roof', 'double_sided': True,
                        'texture': common('kawara', [2, 2], rotate=90)},
    }
    mats.update(opening_materials())

    def roof(m, top_y, mat, mat_r, under=None, edge=None, pyramid=False):
        """Hip roof: top faces at top_y (ridge), the underside T lower, the eave band between."""
        rx = 0 if pyramid else RX
        e = top_y - K * EZ
        ridge = [(-rx, top_y, 0), (rx, top_y, 0)]
        m.quad((-EX, e, -EZ), (EX, e, -EZ), ridge[1], ridge[0], (0, 1, -K), mat) if rx else \
            m.face([(-EX, e, -EZ), (EX, e, -EZ), ridge[0]], (0, 1, -K), mat)
        m.quad((-EX, e, EZ), (EX, e, EZ), ridge[1], ridge[0], (0, 1, K), mat) if rx else \
            m.face([(-EX, e, EZ), (EX, e, EZ), ridge[0]], (0, 1, K), mat)
        m.face([(-EX, e, -EZ), ridge[0], (-EX, e, EZ)], (-K, 1, 0), mat_r)
        m.face([(EX, e, -EZ), ridge[1], (EX, e, EZ)], (K, 1, 0), mat_r)
        if under:
            u, eu = top_y - T, e - T
            ru = [(-rx, u, 0), (rx, u, 0)]
            m.quad((-EX, eu, -EZ), (EX, eu, -EZ), ru[1], ru[0], (0, -1, K), under)
            m.quad((-EX, eu, EZ), (EX, eu, EZ), ru[1], ru[0], (0, -1, -K), under)
            m.face([(-EX, eu, -EZ), ru[0], (-EX, eu, EZ)], (K, -1, 0), under)
            m.face([(EX, eu, -EZ), ru[1], (EX, eu, EZ)], (-K, -1, 0), under)
            c = [(-EX, -EZ), (EX, -EZ), (EX, EZ), (-EX, EZ)]
            for i in range(4):
                (x0, z0), (x1, z1) = c[i], c[(i + 1) % 4]
                m.quad((x0, e, z0), (x1, e, z1), (x1, eu, z1), (x0, eu, z0),
                       ((x0 + x1) / 2, 0, (z0 + z1) / 2), edge)

    # Level 0
    wall, (f, b, l, r) = walls('walls', (WT, WT), ['plaster'] * 4, plinth=(PL, 'footing'))
    wall.decal(f, 'genkan', 'genkan', GK, (-2.6, GY, -D), (0, 0, -1))
    wall.decal(f, 'kitchen', 'win_grille', (1.6, 0.9), (1.4, 1.45, -D), (0, 0, -1))
    wall.decal(f, 'up_l', 'win_lit', (1.6, 0.9), (-2.2, 3.55, -D), (0, 0, -1))
    wall.decal(f, 'up_r', 'win_dark', (1.6, 0.9), (2.2, 3.55, -D), (0, 0, -1))
    wall.decal(b, 'back_low', 'win_grille', (1.6, 0.9), (2.0, 1.45, D), (0, 0, 1))
    wall.decal(b, 'back_up', 'win_dark', (1.6, 0.9), (-1.8, 3.55, D), (0, 0, 1))
    wall.decal(l, 'side_up', 'win_dark', (1.6, 0.9), (-W, 3.55, -1.2), (-1, 0, 0))
    wall.decal(r, 'bath', 'win_small', (0.6, 0.6), (W, 1.75, 2.2), (1, 0, 0))
    rf = Mesh('roof')
    roof(rf, RT, 'kawara', 'kawara_r', 'soffit', 'eave')
    hs = Mesh('hisashi')
    hisashi(hs, -4.0, 2.4, 2.72, -D - 0.62, 0.16, 0.08, ['hisashi', 'eave', 'soffit'])
    antenna = crossed_quads('antenna', (1.8, RT - K * 1.6 - 0.05, 1.6), 1.4, 1.6, 'antenna')
    nodes0 = [wall.node(), rf.node(), hs.node(), antenna]

    # Level 1 (from 16 m): the walls, the roof's top (double-sided, for the eaves seen from
    # below), the door, the pent roof's top.
    w1, (f1, _, _, _) = walls('walls', (WT, WT), ['plaster'] * 4)
    w1.decal(f1, 'genkan', 'genkan', GK, (-2.6, GY, -D), (0, 0, -1))
    r1 = Mesh('roof')
    roof(r1, RT, 'kawara_ds', 'kawara_r_ds')
    h1 = Mesh('hisashi')
    h1.quad((-4.0, 2.72, -D + 0.02), (2.4, 2.72, -D + 0.02), (2.4, 2.56, -D - 0.62), (-4.0, 2.56, -D - 0.62),
            (0, 1, -0.2), 'hisashi')
    nodes1 = [w1.node(), r1.node(), h1.node()]

    # Level 2 (from 40 m): the walls and a pyramid with the same eaves.
    w2, _ = walls('walls', (WT, WT), ['plaster'] * 4)
    r2 = Mesh('roof')
    roof(r2, RT, 'kawara', 'kawara_r', pyramid=True)
    nodes2 = [w2.node(), r2.node()]

    write(os.path.join(ROOT, name, name + '.asset.json'), recipe(name, 120, mats, nodes0, [nodes1, nodes2]))

    # Collision: the walls, the roof as a 0.2 m slab on the render's slope (its eave band the
    # grabbing lip), the pent roof as a ledge (in three pieces).
    c = Mesh('walls')
    for s in (-1, 1):
        c.quad((-W, WT, s * D), (W, WT, s * D), (W, 0, s * D), (-W, 0, s * D), (0, 0, s), 'solid')
        c.quad((s * W, WT, -D), (s * W, WT, D), (s * W, 0, D), (s * W, 0, -D), (s, 0, 0), 'solid')
    cr = Mesh('roof')
    e, eu = RT - K * EZ, RT - K * EZ - 0.2
    rid, riu = [(-RX, RT, 0), (RX, RT, 0)], [(-RX, RT - 0.2, 0), (RX, RT - 0.2, 0)]
    for s in (-1, 1):
        cr.quad((-EX, e, s * EZ), (EX, e, s * EZ), rid[1], rid[0], (0, 1, s * K), 'solid')
        cr.quad((-EX, eu, s * EZ), (EX, eu, s * EZ), riu[1], riu[0], (0, -1, -s * K), 'solid')
        cr.face([(s * EX, e, -EZ), rid[(s + 1) // 2], (s * EX, e, EZ)], (s * K, 1, 0), 'solid')
        cr.face([(s * EX, eu, -EZ), riu[(s + 1) // 2], (s * EX, eu, EZ)], (-s * K, -1, 0), 'solid')
    cc = [(-EX, -EZ), (EX, -EZ), (EX, EZ), (-EX, EZ)]
    for i in range(4):
        (x0, z0), (x1, z1) = cc[i], cc[(i + 1) % 4]
        cr.quad((x0, e, z0), (x1, e, z1), (x1, eu, z1), (x0, eu, z0), ((x0 + x1) / 2, 0, (z0 + z1) / 2), 'solid')
    ch = Mesh('hisashi')
    z0, z1 = -D, -D - 0.62
    strip_top(ch, -4.0, 2.4, z1, z0, 2.56, 2.72, 3, 'solid')
    ch.quad((-4.0, 2.56, z1), (2.4, 2.56, z1), (2.4, 2.36, z1), (-4.0, 2.36, z1), (0, 0, -1), 'solid')
    ch.quad((-4.0, 2.36, z1), (2.4, 2.36, z1), (2.4, 2.52, z0), (-4.0, 2.52, z0), (0, -1, 0), 'solid')
    for s, x in ((-1, -4.0), (1, 2.4)):
        ch.face([(x, 2.72, z0), (x, 2.56, z1), (x, 2.36, z1), (x, 2.52, z0)], (s, 0, 0), 'solid')
    write(os.path.join(ROOT, name, name + '_col.asset.json'),
          col_recipe(name + '_col', [c.node(), cr.node(), ch.node()]))


# --------------------------------------------------------------------------------------------
# B: a narrow-fronted 1960s house rebuilt in grey cement mortar, its sides clad in corrugated
# tin, under a nearly flat shed roof of painted tin: 6.5 at the front eave, 7.0 at the back.
# A balcony with an aluminium railing upstairs, a small pent roof over the door.
# --------------------------------------------------------------------------------------------

def house_b():
    name = 'town_alley_house_b'
    YF, YB = 6.5, 7.0                   # roof top at the front and back eaves
    OZ, OX, T = 0.35, 0.3, 0.12
    EZ, EX = D + OZ, W + OX
    s_ = (YB - YF) / (2 * EZ)
    top = lambda z: (YF + YB) / 2 + s_ * z
    WF, WB = top(-D) - 0.06, top(D) - 0.06      # wall tops, 6 cm under the roof's top
    mats = {
        'mortar': {'color': '#b2aea4', 'tag': 'wall', 'texture': common('plaster_grey', [2, 2])},
        'tin': {'color': '#868c90', 'tag': 'wall', 'texture': common('tin', [2, 2])},
        'tin_roof': {'color': '#8a3a2a', 'tag': 'roof', 'texture': common('tin_red', [2, 2])},
        'tin_roof_ds': {'color': '#8a3a2a', 'tag': 'roof', 'double_sided': True, 'texture': common('tin_red', [2, 2])},
        'gutter': {'color': '#8e9498', 'palette': True},
        'soffit': {'color': '#5a4a3e', 'palette': True},
        'footing': {'color': '#8e887c', 'palette': True},
        'slab': {'color': '#a8a49a', 'palette': True},
        'rail': {'color': '#c4c8cc', 'double_sided': True, 'texture': alley('rail')},
        'balcony_door': {'color': '#4e6a7a', 'texture': alley('balcony_door')},
        'hisashi': {'color': '#6a7078', 'palette': True, 'tag': 'roof'},
        'antenna': {'color': '#7a7e84', 'double_sided': True,
                    'texture': {'sheet': 'shopfront', 'cell': 'antenna', 'projection': 'fit'}},
    }
    mats.update(opening_materials())
    BX0, BX1, BY, BZ = -4.2, 0.6, 2.9, -D - 0.95       # balcony: x span, floor top, its front

    def roof(m, mat, under=None, edge=None):
        a, b_ = (-EX, top(-EZ), -EZ), (EX, top(-EZ), -EZ)
        c, d = (EX, top(EZ), EZ), (-EX, top(EZ), EZ)
        m.quad(a, b_, c, d, (0, 1, 0), mat)
        if under:
            dn = lambda p: (p[0], p[1] - T, p[2])
            m.quad(dn(a), dn(b_), dn(c), dn(d), (0, -1, 0), under)
            ring = [a, b_, c, d]
            for i in range(4):
                p, q = ring[i], ring[(i + 1) % 4]
                m.quad(p, q, dn(q), dn(p), ((p[0] + q[0]) / 2, 0, (p[2] + q[2]) / 2), edge)

    # Level 0
    wall, (f, b, l, r) = walls('walls', (WF, WB), ['mortar', 'mortar', 'tin', 'tin'], plinth=(PL, 'footing'))
    wall.decal(f, 'genkan', 'genkan', GK, (2.65, GY, -D), (0, 0, -1))
    wall.decal(f, 'front_low', 'win_grille', (1.6, 0.9), (-1.6, 1.45, -D), (0, 0, -1))
    wall.decal(f, 'balcony_door', 'balcony_door', (1.8, 1.9), (-1.8, BY + 0.97, -D), (0, 0, -1))
    wall.decal(f, 'up_r', 'win_lit', (1.6, 0.9), (2.6, 4.35, -D), (0, 0, -1))
    wall.decal(b, 'back_low', 'win_grille', (1.6, 0.9), (-2.4, 1.45, D), (0, 0, 1))
    wall.decal(b, 'back_up', 'win_dark', (1.6, 0.9), (1.6, 4.35, D), (0, 0, 1))
    wall.decal(r, 'bath', 'win_small', (0.6, 0.6), (W, 1.75, 2.4), (1, 0, 0))
    rf = Mesh('roof')
    roof(rf, 'tin_roof', 'soffit', 'gutter')
    balc = box('balcony', (BX1 - BX0, 0.16, -BZ - D + 0.03), (( BX0 + BX1) / 2, BY - 0.08, (BZ - D + 0.03) / 2),
               'slab', open=['front'])
    rail = Mesh('rail')
    rz = BZ + 0.05
    rail.quad((BX0 + 0.05, BY + 0.9, rz), (BX1 - 0.05, BY + 0.9, rz), (BX1 - 0.05, BY - 0.04, rz),
              (BX0 + 0.05, BY - 0.04, rz), (0, 0, -1), 'rail')
    for x in (BX0 + 0.05, BX1 - 0.05):
        rail.quad((x, BY + 0.9, rz), (x, BY + 0.9, -D - 0.03), (x, BY - 0.04, -D - 0.03), (x, BY - 0.04, rz),
                  (1 if x > 0 else -1, 0, 0), 'rail')
    hs = Mesh('hisashi')
    hisashi(hs, 1.5, 3.8, 2.6, -D - 0.55, 0.14, 0.08, ['hisashi', 'gutter', 'soffit'])
    antenna = crossed_quads('antenna', (-2.6, top(2.6) - 0.05, 2.6), 1.4, 1.6, 'antenna')
    nodes0 = [wall.node(), rf.node(), balc, rail.node(), hs.node(), antenna]

    # Level 1 (from 16 m): walls, the roof's top (double-sided), the door and the balcony door,
    # the balcony as its floor and the front of its railing.
    w1, (f1, _, _, _) = walls('walls', (WF, WB), ['mortar', 'mortar', 'tin', 'tin'])
    w1.decal(f1, 'genkan', 'genkan', GK, (2.65, GY, -D), (0, 0, -1))
    w1.decal(f1, 'balcony_door', 'balcony_door', (1.8, 1.9), (-1.8, BY + 0.97, -D), (0, 0, -1))
    r1 = Mesh('roof')
    roof(r1, 'tin_roof_ds')
    b1 = Mesh('balcony')
    b1.quad((BX0, BY, BZ), (BX1, BY, BZ), (BX1, BY, -D + 0.03), (BX0, BY, -D + 0.03), (0, 1, 0), 'slab')
    b1.quad((BX0 + 0.05, BY + 0.9, rz), (BX1 - 0.05, BY + 0.9, rz), (BX1 - 0.05, BY - 0.04, rz),
            (BX0 + 0.05, BY - 0.04, rz), (0, 0, -1), 'rail')
    nodes1 = [w1.node(), r1.node(), b1.node()]

    # Level 2 (from 40 m): the walls and the roof's top.
    w2, _ = walls('walls', (WF, WB), ['mortar', 'mortar', 'tin', 'tin'])
    r2 = Mesh('roof')
    roof(r2, 'tin_roof')
    nodes2 = [w2.node(), r2.node()]

    write(os.path.join(ROOT, name, name + '.asset.json'), recipe(name, 120, mats, nodes0, [nodes1, nodes2]))

    # Collision: walls, the roof as a 0.2 m slab, the balcony's floor and the top of its front
    # railing (a 0.2 m ledge), the pent roof.
    c = Mesh('walls')
    c.quad((-W, WF, -D), (W, WF, -D), (W, 0, -D), (-W, 0, -D), (0, 0, -1), 'solid')
    c.quad((-W, WB, D), (W, WB, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'solid')
    for s in (-1, 1):
        c.face([(s * W, 0, -D), (s * W, WF, -D), (s * W, WB, D), (s * W, 0, D)], (s, 0, 0), 'solid')
    cr = Mesh('roof')
    pts = [(-EX, top(-EZ), -EZ), (EX, top(-EZ), -EZ), (EX, top(EZ), EZ), (-EX, top(EZ), EZ)]
    dn = lambda p: (p[0], p[1] - 0.2, p[2])
    cr.quad(*pts, (0, 1, 0), 'solid')
    cr.quad(*[dn(p) for p in pts], (0, -1, 0), 'solid')
    for i in range(4):
        p, q = pts[i], pts[(i + 1) % 4]
        cr.quad(p, q, dn(q), dn(p), ((p[0] + q[0]) / 2, 0, (p[2] + q[2]) / 2), 'solid')
    cb = Mesh('balcony')
    slab_box(cb, BX0, BX1, BY - 0.2, BY, BZ, -D, open=('back',))
    crl = Mesh('rail')
    slab_box(crl, BX0, BX1, BY, BY + 0.9, BZ, BZ + 0.2, open=('bottom',))
    ch = Mesh('hisashi')
    z0, z1 = -D, -D - 0.55
    ch.quad((1.5, 2.46, z1), (3.8, 2.46, z1), (3.8, 2.6, z0), (1.5, 2.6, z0), (0, 1, 0), 'solid')
    ch.quad((1.5, 2.46, z1), (3.8, 2.46, z1), (3.8, 2.26, z1), (1.5, 2.26, z1), (0, 0, -1), 'solid')
    ch.quad((1.5, 2.26, z1), (3.8, 2.26, z1), (3.8, 2.4, z0), (1.5, 2.4, z0), (0, -1, 0), 'solid')
    for s, x in ((-1, 1.5), (1, 3.8)):
        ch.face([(x, 2.6, z0), (x, 2.46, z1), (x, 2.26, z1), (x, 2.4, z0)], (s, 0, 0), 'solid')
    write(os.path.join(ROOT, name, name + '_col.asset.json'),
          col_recipe(name + '_col', [c.node(), cr.node(), cb.node(), crl.node(), ch.node()]))


# --------------------------------------------------------------------------------------------
# C: a taller two-storey house of cream mortar under a gable of blue glazed kawara (ridge along
# X, 7.2), with a galvanised drying platform (monohoshi) straddling the ridge, its deck at 8.0:
# the alleys' high step. Rails on its two long sides and its east end; the west end is open.
# --------------------------------------------------------------------------------------------

def house_c():
    name = 'town_alley_house_c'
    RT, OZ, OX, T = 7.2, 0.35, 0.3, 0.15
    EZ, EX = D + OZ, W + OX
    ye = RT - K * EZ                         # 5.98
    WT = RT - K * D - 0.09                   # front and back wall tops (5.98), 9 cm under the tiles
    GA = RT - 0.08                           # the gables' apex, inside the roof slab
    PX0, PX1, PZ, PY = -0.6, 3.4, 1.3, 8.0   # the platform: x span, half its depth, deck top
    mats = {
        'plaster': {'color': '#ddd3bd', 'tag': 'wall', 'texture': common('plaster', [2, 2])},
        'kawara': {'color': '#3e4c5e', 'tag': 'roof', 'texture': common('kawara_blue', [2, 2])},
        'kawara_ds': {'color': '#3e4c5e', 'tag': 'roof', 'double_sided': True,
                      'texture': common('kawara_blue', [2, 2])},
        'eave': {'color': '#222a34', 'palette': True, 'tag': 'roof'},
        'soffit': {'color': '#5a4a3e', 'palette': True},
        'footing': {'color': '#8e887c', 'palette': True},
        'hisashi': {'color': '#3e4c5e', 'palette': True, 'tag': 'roof'},
        'steel': {'color': '#a8acb0', 'palette': True},
        'deck': {'color': '#b4b8bc', 'texture': alley('hoshi_deck')},
        'deck_ds': {'color': '#b4b8bc', 'double_sided': True, 'texture': alley('hoshi_deck')},
        'hoshi_rail': {'color': '#b4b8bc', 'double_sided': True, 'texture': alley('hoshi_rail')},
        'hoshi_frame': {'color': '#b4b8bc', 'double_sided': True, 'texture': alley('hoshi_frame')},
    }
    mats.update(opening_materials())

    def roof(m, mat, under=None, edge=None):
        top = [(-EZ, ye), (0, RT), (EZ, ye)]
        for s in (-1, 1):
            m.quad((-EX, ye, s * EZ), (EX, ye, s * EZ), (EX, RT, 0), (-EX, RT, 0), (0, 1, s * K), mat)
        if under:
            for s in (-1, 1):
                m.quad((-EX, ye - T, s * EZ), (EX, ye - T, s * EZ), (EX, RT - T, 0), (-EX, RT - T, 0),
                       (0, -1, -s * K), under)
                m.quad((-EX, ye, s * EZ), (EX, ye, s * EZ), (EX, ye - T, s * EZ), (-EX, ye - T, s * EZ),
                       (0, 0, s), edge)
            prof = [(-EZ, ye), (0, RT), (EZ, ye), (EZ, ye - T), (0, RT - T), (-EZ, ye - T)]
            for s in (-1, 1):
                m.face([(s * EX, y, z) for z, y in prof], (s, 0, 0), edge)

    def platform(level):
        nodes = []
        if level == 0:
            nodes.append(box('deck', (PX1 - PX0, 0.12, 2 * PZ), ((PX0 + PX1) / 2, PY - 0.06, 0), 'steel',
                             faces={'top': 'deck'}))
        else:
            m = Mesh('deck')
            m.quad((PX0, PY, -PZ), (PX1, PY, -PZ), (PX1, PY, PZ), (PX0, PY, PZ), (0, 1, 0), 'deck_ds')
            nodes.append(m.node())
        legs = Mesh('legs')
        y0, y1 = RT - K * PZ - 0.2, PY - 0.12
        for x in (PX0 + 0.12, PX1 - 0.12):
            legs.quad((x, y1, -PZ + 0.05), (x, y1, PZ - 0.05), (x, y0, PZ - 0.05), (x, y0, -PZ + 0.05),
                      (1, 0, 0), 'hoshi_frame')
        nodes.append(legs.node())
        if level:
            return nodes
        rail = Mesh('rail')
        yb, yt = PY - 0.04, PY + 0.9
        for s in (-1, 1):
            z = s * (PZ - 0.06)
            rail.quad((PX0 + 0.04, yt, z), (PX1 - 0.04, yt, z), (PX1 - 0.04, yb, z), (PX0 + 0.04, yb, z),
                      (0, 0, s), 'hoshi_rail')
        x = PX1 - 0.06
        rail.quad((x, yt, -PZ + 0.1), (x, yt, PZ - 0.1), (x, yb, PZ - 0.1), (x, yb, -PZ + 0.1), (1, 0, 0), 'hoshi_rail')
        nodes.append(rail.node())
        return nodes

    # Level 0
    wall, (f, b, l, r) = walls('walls', (WT, WT), ['plaster'] * 4, gable=GA, plinth=(PL, 'footing'))
    wall.decal(f, 'genkan', 'genkan', GK, (-2.8, GY, -D), (0, 0, -1))
    wall.decal(f, 'front_low', 'win_grille', (1.6, 0.9), (1.6, 1.5, -D), (0, 0, -1))
    wall.decal(f, 'up', 'win_lit', (1.6, 0.9), (0.4, 4.2, -D), (0, 0, -1))
    wall.decal(b, 'back_low', 'win_grille', (1.6, 0.9), (2.2, 1.5, D), (0, 0, 1))
    wall.decal(b, 'back_up', 'win_dark', (1.6, 0.9), (-1.6, 4.2, D), (0, 0, 1))
    wall.decal(l, 'gable_w', 'win_dark', (1.6, 0.9), (-W, 4.2, 0.0), (-1, 0, 0))
    rf = Mesh('roof')
    roof(rf, 'kawara', 'soffit', 'eave')
    hs = Mesh('hisashi')
    hisashi(hs, -4.1, 2.6, 2.75, -D - 0.62, 0.16, 0.08, ['hisashi', 'eave', 'soffit'])
    nodes0 = [wall.node(), rf.node(), hs.node()] + platform(0)

    # Level 1 (from 16 m): walls, the roof's top (double-sided), the door, the deck and its legs.
    w1, (f1, _, _, _) = walls('walls', (WT, WT), ['plaster'] * 4, gable=GA)
    w1.decal(f1, 'genkan', 'genkan', GK, (-2.8, GY, -D), (0, 0, -1))
    r1 = Mesh('roof')
    roof(r1, 'kawara_ds')
    nodes1 = [w1.node(), r1.node()] + platform(1)

    # Level 2 (from 40 m): the walls up to the eaves and the roof's two slopes, double-sided so
    # the open gables show the far slope's underside, not the sky.
    w2, _ = walls('walls', (WT, WT), ['plaster'] * 4)
    r2 = Mesh('roof')
    roof(r2, 'kawara_ds')
    nodes2 = [w2.node(), r2.node()]

    write(os.path.join(ROOT, name, name + '.asset.json'), recipe(name, 120, mats, nodes0, [nodes1, nodes2]))

    # Collision: walls, the roof as a 0.2 m slab, the platform as a solid block from inside the
    # roof up to the deck (nothing to get wedged under), its rails as 0.2 m walls to 8.9.
    c, _ = walls('walls', (WT, WT), ['solid'] * 4, gable=GA)
    cr = Mesh('roof')
    for s in (-1, 1):
        cr.quad((-EX, ye, s * EZ), (EX, ye, s * EZ), (EX, RT, 0), (-EX, RT, 0), (0, 1, s * K), 'solid')
        cr.quad((-EX, ye - 0.2, s * EZ), (EX, ye - 0.2, s * EZ), (EX, RT - 0.2, 0), (-EX, RT - 0.2, 0),
                (0, -1, -s * K), 'solid')
        cr.quad((-EX, ye, s * EZ), (EX, ye, s * EZ), (EX, ye - 0.2, s * EZ), (-EX, ye - 0.2, s * EZ), (0, 0, s), 'solid')
    prof = [(-EZ, ye), (0, RT), (EZ, ye), (EZ, ye - 0.2), (0, RT - 0.2), (-EZ, ye - 0.2)]
    for s in (-1, 1):
        cr.face([(s * EX, y, z) for z, y in prof], (s, 0, 0), 'solid')
    cp = Mesh('platform')
    yl = RT - K * PZ - 0.25
    slab_box(cp, PX0, PX1, yl, PY, -PZ, PZ, open=('bottom',))
    for s in (-1, 1):
        z0, z1 = (PZ - 0.2, PZ) if s > 0 else (-PZ, -PZ + 0.2)
        rm = Mesh('rail_n' if s > 0 else 'rail_s')
        slab_box(rm, PX0, PX1, PY, PY + 0.9, z0, z1, open=('bottom',))
        cp_extra = rm.node()
        if s < 0:
            rail_s = cp_extra
        else:
            rail_n = cp_extra
    re = Mesh('rail_e')
    slab_box(re, PX1 - 0.2, PX1, PY, PY + 0.9, -PZ + 0.21, PZ - 0.21, open=('bottom',))
    ch = Mesh('hisashi')
    z0, z1 = -D, -D - 0.62
    strip_top(ch, -4.1, 2.6, z1, z0, 2.59, 2.75, 3, 'solid')
    ch.quad((-4.1, 2.59, z1), (2.6, 2.59, z1), (2.6, 2.39, z1), (-4.1, 2.39, z1), (0, 0, -1), 'solid')
    ch.quad((-4.1, 2.39, z1), (2.6, 2.39, z1), (2.6, 2.55, z0), (-4.1, 2.55, z0), (0, -1, 0), 'solid')
    for s, x in ((-1, -4.1), (1, 2.6)):
        ch.face([(x, 2.75, z0), (x, 2.59, z1), (x, 2.39, z1), (x, 2.55, z0)], (s, 0, 0), 'solid')
    write(os.path.join(ROOT, name, name + '_col.asset.json'),
          col_recipe(name + '_col', [c.node(), cr.node(), cp.node(), rail_s, rail_n, re.node(), ch.node()]))


if __name__ == '__main__':
    pack_common()
    pack(draw_alley(), 128, 'alley')
    house_a()
    house_b()
    house_c()
