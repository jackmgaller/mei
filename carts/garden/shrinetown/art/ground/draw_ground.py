#!/usr/bin/env python3
"""Draws the shrine town's ground textures (the PNGs beside this file), for the terrain materials
of shrinetown.world.json: the town's asphalt and its markings, the sidewalk with its tactile
strip, the kerb, the station plaza, plain concrete, the school's sports ground and its white line,
the canal's stone walls (both regions); and for the shrine region what the shrine world's set
(../../../shrine/assets/art/terrain_*.png, reused) does not have: cemetery gravel, the bamboo
grove's floor, the park's grass and sand. GROUND.md lists every material and where it goes.

Authored art: run once with `python3 carts/garden/shrinetown/art/ground/draw_ground.py` and commit
the PNGs; nothing rebuilds them. Needs Pillow. Each texture is drawn from a fixed seed, so a rerun
gives the same pictures. The approach is the shrine's (draw_terrain.py there): small tiles that
repeat seamlessly (every mark wraps round the edges), 4-bit (15 colours at most), soft value
noise and a few marks, low contrast where a surface is large, so it does not shimmer at a
distance, late October (a few maple and ginkgo leaves).

Colour families. Textures drawn together share their colours exactly, so the World Kit's
palette packer (first fit, 15 colours a palette) puts each family in one 4-bit palette:
ROAD (asphalt, asphalt_line, asphalt_zebra, asphalt_stop), PAVING (sidewalk, sidewalk_tactile,
kerb, plaza, concrete), DIRT (ground, ground_line), STONE (canal_wall).

The town's materials are drawn for a scale of 2 units a repeat (32 texels: 6.25 cm a texel; the
plaza's 64 texels for 4),
so one repeat is one 2 m quad of the ground field and a marking painted on a row of quads lies
where its texture's offset puts it (GROUND.md, "Markings").

    python3 carts/garden/shrinetown/art/ground/draw_ground.py                 # the PNGs
    python3 carts/garden/shrinetown/art/ground/draw_ground.py --preview DIR   # and a contact sheet
"""

import argparse
import math
import random
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


class Tile:
    def __init__(self, fill, seed, w=32, h=None):
        self.w, self.h = w, h or w
        self.px = [[fill] * self.w for _ in range(self.h)]
        self.r = random.Random(seed)

    def set(self, x, y, c):
        self.px[y % self.h][x % self.w] = c

    def get(self, x, y):
        return self.px[y % self.h][x % self.w]

    def copy_from(self, other):
        self.px = [list(row) for row in other.px]

    def value_noise(self, cells):
        """A wrapping value noise in 0..1, `cells` lattice cells a side (and twice as many, finer)."""
        r = self.r
        g = [[r.random() for _ in range(cells)] for _ in range(cells)]
        g2 = [[r.random() for _ in range(cells * 2)] for _ in range(cells * 2)]

        def sample(grid, n, x, y):
            fx, fy = x * n / self.w, y * n / self.h
            i, j = int(fx), int(fy)
            tx, ty = fx - i, fy - j
            tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
            a, b = grid[j % n][i % n], grid[j % n][(i + 1) % n]
            c, d = grid[(j + 1) % n][i % n], grid[(j + 1) % n][(i + 1) % n]
            return (a + (b - a) * tx) * (1 - ty) + (c + (d - c) * tx) * ty

        return [[0.65 * sample(g, cells, x, y) + 0.35 * sample(g2, cells * 2, x, y) for x in range(self.w)]
                for y in range(self.h)]

    def noise(self, colours, cells=4, bias=0.0, jitter=0.18, mask=None):
        """Mottles the tile (or the texels where mask(x, y)): the noise picks among `colours`,
        darkest first."""
        v = self.value_noise(cells)
        for y in range(self.h):
            for x in range(self.w):
                if mask and not mask(x, y):
                    continue
                t = v[y][x] + bias + (self.r.random() - 0.5) * jitter
                self.px[y][x] = colours[max(0, min(len(colours) - 1, int(t * len(colours))))]

    def scatter(self, colours, count, where=None):
        for _ in range(count):
            x, y = self.r.randrange(self.w), self.r.randrange(self.h)
            if where and self.get(x, y) not in where:
                continue
            self.set(x, y, self.r.choice(colours))

    def blob(self, cx, cy, rx, ry, c, rough=0.0):
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                d = ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2
                if d <= 1 + (self.r.random() - 0.5) * rough:
                    self.set(x, y, c)

    def leaf(self, x, y, c, dark=None, kind=None):
        """A fallen leaf, 1-5 texels (the shrine's: a maple's, a ginkgo's fan, an oval, a fleck)."""
        r = self.r
        kind = kind or r.choice(('maple', 'fan', 'oval'))
        sx, sy = r.choice((-1, 1)), r.choice((-1, 1))
        if kind == 'maple':
            cells = [(0, 0), (1, 0), (0, 1), (1, 1), r.choice(((2, 0), (0, 2), (2, 1), (1, 2)))]
            if r.random() < 0.5:
                cells.pop(r.randrange(4))
        elif kind == 'fan':
            cells = [(0, 0), (1, 0), (0, 1)]
        elif kind == 'oval':
            cells = r.choice(([(0, 0), (1, 0)], [(0, 0), (1, 1)], [(0, 0), (1, 0), (2, 1)], [(0, 0), (1, 1), (1, 2)]))
        else:
            cells = r.choice(([(0, 0)], [(0, 0), (1, 0)], [(0, 0), (0, 1)]))
        for dx, dy in cells:
            self.set(x + sx * dx, y + sy * dy, c)
        if dark and len(cells) > 2:
            dx, dy = cells[-1]
            self.set(x + sx * dx, y + sy * dy, dark)

    def streak(self, x, y, length, angle, c):
        for k in range(length):
            self.set(round(x + k * math.cos(angle)), round(y + k * math.sin(angle)), c)

    def colours(self):
        return {c for row in self.px for c in row}

    def image(self):
        img = Image.new('RGBA', (self.w, self.h))
        img.putdata([rgb(c) + (255,) for row in self.px for c in row])
        return img


DRAWN = {}       # name -> Tile, in drawing order


def save(name, t):
    n = len(t.colours())
    assert n <= 15, (name, n)
    DRAWN[name] = t
    t.image().save(HERE / f'{name}.png')


MAPLE = ('#c8301e', '#e0502a', '#e8782a')
GINKGO = ('#f0c030', '#d89a20')


def leaves(t, count, colours, dark=None, kinds=None):
    for _ in range(count):
        t.leaf(t.r.randrange(t.w), t.r.randrange(t.h), t.r.choice(colours), dark,
               t.r.choice(kinds) if kinds else None)


# ---------------------------------------------------------------------------------- ROAD
# Asphalt greys (STYLE.md: street asphalt #4a4a50), white paint and its worn tones.
A_TAR, A_D2, A_D1, A_MID, A_L1, A_L2, A_GRIT = ('#323236', '#3c3c42', '#44444a', '#4a4a50', '#505056',
                                                '#5a5a60', '#68686c')
W_PAINT, W_WORN, W_GONE = '#e2e0d8', '#c4c2ba', '#8e8c88'


def asphalt_base():
    """Worn town asphalt: a low mottle (low contrast, for the distance), sparse grit, two short
    tar-sealed cracks and a darker oil-stained drift. No long or single bold mark: the tile
    repeats every 2 m."""
    t = Tile(A_MID, 201)
    t.noise([A_D1, A_MID, A_MID, A_L1], cells=4, jitter=0.22)
    t.scatter([A_L2, A_D2, A_GRIT], 70)
    for x0, y0, n in ((5, 3, 7), (22, 19, 6)):
        x = x0
        for k in range(n):
            t.set(x, y0 + k, A_TAR)
            x += t.r.choice((-1, 0, 1))
    t.blob(24, 6, 3.2, 2.0, A_D1, 0.6)
    return t


def asphalt():
    save('asphalt', asphalt_base())


def worn_paint(t, cells):
    """Paints white over `cells` (x, y): mostly fresh, some worn, a few gone to the asphalt."""
    for x, y in cells:
        k = t.r.random()
        t.set(x, y, W_PAINT if k < 0.88 else W_WORN if k < 0.985 else W_GONE)


def asphalt_line():
    """The road's solid white line (centre or edge line), 2 texels (12.5 cm) at texels 15-16 of u,
    running along v; the asphalt is asphalt.png's, so the line's strip meets plain asphalt with
    no seam."""
    t = asphalt_base()
    worn_paint(t, [(x, y) for y in range(32) for x in (15, 16)])
    save('asphalt_line', t)


def asphalt_zebra():
    """A zebra crossing: white bars 8 texels (50 cm) wide, 8 apart, along v (Japanese crossings'
    bars run with the traffic): bars at u 4-11 and 20-27."""
    t = asphalt_base()
    worn_paint(t, [(x, y) for y in range(32) for x in list(range(4, 12)) + list(range(20, 28))])
    save('asphalt_zebra', t)


def asphalt_stop():
    """A stop line: one white band 7 texels (44 cm) wide at u 13-19, along v."""
    t = asphalt_base()
    worn_paint(t, [(x, y) for y in range(32) for x in range(13, 20)])
    save('asphalt_stop', t)


# --------------------------------------------------------------------------------- PAVING
# Concrete greys (STYLE.md: kerb #a8a69e, concrete #c8c4b8), the tactile strip's yellow, the
# plaza's rose-brown band.
P_JOINT, P_D1, P_MID, P_L1, P_L2, P_L3 = '#8a8680', '#9c988c', '#aca89c', '#b8b4a8', '#c4c0b4', '#cecabe'
Y_SHADE, Y_BODY, Y_DOT = '#b88a1c', '#d8a828', '#ecc448'
R_JOINT, R_BODY = '#9a8474', '#b49c88'
C_STAIN = '#7e7a72'


def sidewalk():
    """The sidewalk: interlocking concrete pavers of the 1990s, 8 x 4 texels (50 x 25 cm) in
    stretcher bond, grey, some lighter, a few darker; stains, grit. No coloured pavers: one in a
    2 m repeat makes a grid at a distance."""
    t = Tile(P_L1, 211)
    for row in range(8):
        y0 = row * 4
        shift = 4 * (row % 2)
        for col in range(4):
            x0 = col * 8 + shift
            k = t.r.random()
            tone = P_L2 if k < 0.3 else P_MID if k < 0.42 else P_L1
            for y in range(y0, y0 + 4):
                for x in range(x0, x0 + 8):
                    t.set(x, y, tone)
            for x in range(x0, x0 + 8):
                t.set(x, y0, P_D1)
            for y in range(y0, y0 + 4):
                t.set(x0, y, P_D1)
    t.scatter([P_L3, P_MID], 40, where={P_L1, P_L2})
    t.scatter([C_STAIN], 3, where={P_L1, P_L2, P_MID})
    return t


def sidewalk_save():
    save('sidewalk', sidewalk())


def sidewalk_tactile():
    """The sidewalk with the yellow tactile strip (tenji blocks: dots), 6 texels (37.5 cm) at u
    13-18, block joints every 8 texels; the pavers either side are sidewalk.png's."""
    t = sidewalk()
    for y in range(32):
        for x in range(13, 19):
            t.set(x, y, Y_BODY)
        t.set(12, y, P_JOINT)
        t.set(19, y, P_JOINT)
    for y0 in range(0, 32, 8):
        for x in range(13, 19):
            t.set(x, y0, Y_SHADE)
        for y in range(y0 + 1, y0 + 8, 2):
            for x in (14, 16, 18):
                if x < 19:
                    t.set(x - (1 if x == 18 else 0), y, Y_DOT)
    # grime at the strip's edges
    for _ in range(10):
        y = t.r.randrange(32)
        t.set(t.r.choice((13, 18)), y, Y_SHADE)
    save('sidewalk_tactile', t)


def kerb():
    """The kerb: precast concrete kerb stones, light, speckled, a joint every 16 texels (1 m at a
    scale of 1), and a slightly darker lower band (road grime) on the outer half of v."""
    t = Tile(P_L2, 213, 16)
    t.noise([P_L1, P_L2, P_L2, P_L3], cells=2, jitter=0.25)
    t.scatter([P_MID, P_L3], 24)
    for y in range(16):
        t.set(0, y, P_JOINT)
    for y in range(12, 16):
        for x in range(1, 16):
            if t.r.random() < 0.5:
                t.set(x, y, P_MID)
    save('kerb', t)


def plaza():
    """The station plaza: 1990s ceramic paving, 64 x 64 texels for a scale of 4 (6.25 cm a
    texel): 50 cm squares in two quiet tones, framed every 4 m each way by a band of rose-brown
    25 cm tiles (u 0-3 and v 0-3). A 2 m repeat made the bands a grid too busy for the distance."""
    t = Tile(P_L2, 214, 64)
    for by in range(8):
        for bx in range(8):
            tone = t.r.choice((P_L2, P_L2, P_L1, P_L3))
            for y in range(by * 8, by * 8 + 8):
                for x in range(bx * 8, bx * 8 + 8):
                    t.set(x, y, tone)
            for k in range(8):
                t.set(bx * 8 + k, by * 8, P_MID)
                t.set(bx * 8, by * 8 + k, P_MID)
    for y in range(64):
        for x in range(64):
            if x < 4 or y < 4:
                t.set(x, y, R_BODY if (x % 4 and y % 4) else R_JOINT)
    t.scatter([P_L3, P_MID], 90, where={P_L1, P_L2})
    t.scatter([C_STAIN], 6, where={P_L1, P_L2})
    save('plaza', t)


def concrete():
    """Plain concrete for the alleys and service lanes (and the pool's deck): a cast slab, a joint
    at u = 0 and v = 0 (slabs of one repeat), a hairline crack, water stains."""
    t = Tile(P_L1, 215)
    t.noise([P_MID, P_L1, P_L1, P_L2], cells=3, jitter=0.2)
    for k in range(32):
        t.set(k, 0, P_D1)
        t.set(0, k, P_D1)
    x, y = 9, 6
    for k in range(10):
        t.set(x, y, P_MID)
        x += 1
        y += t.r.choice((0, 1, 1))
    t.blob(23, 21, 4.0, 2.6, P_MID, 0.8)
    t.scatter([C_STAIN, P_L3, P_MID], 36)
    save('concrete', t)


# ----------------------------------------------------------------------------------- DIRT
# The schoolyard's packed sandy dirt (masa-do) and the white lime line.
D_DARK, D_D1, D_MID, D_L1, D_L2 = '#8a6a48', '#a8804e', '#b48c5a', '#c49a6a', '#d0aa7c'
D_PEBBLE, D_STONE = '#dccab0', '#7a766c'
L_LIME, L_LIME2 = '#ece8dc', '#d4ccb8'


def ground_base():
    t = Tile(D_MID, 221)
    t.noise([D_MID, D_L1, D_L1, D_L2], cells=3, jitter=0.35)
    t.scatter([D_PEBBLE, D_DARK, D_STONE], 40)
    # shoe scuffs: short dark arcs
    for _ in range(4):
        x, y = t.r.randrange(32), t.r.randrange(32)
        for k in range(3):
            t.set(x + k, y + (k == 1), D_D1)
    return t


def ground():
    """The school's sports ground: packed light-brown sandy dirt, pebbles, a few shoe scuffs."""
    save('ground', ground_base())


def ground_line():
    """The sports ground's white lime line, 2 texels at u 15-16 with a powdery edge, along v."""
    t = ground_base()
    for y in range(32):
        for x in (15, 16):
            t.set(x, y, L_LIME if t.r.random() < 0.85 else L_LIME2)
        for x in (14, 17):
            if t.r.random() < 0.3:
                t.set(x, y, L_LIME2)
    save('ground_line', t)


# ---------------------------------------------------------------------------------- STONE
S_JOINT, S_WET, S_D1, S_MID, S_L1, S_L2, S_L3 = ('#4e4a44', '#5e5a52', '#6a665e', '#7a766c', '#8e887c',
                                                 '#9a9488', '#aaa496')
S_MOSS, S_MOSS2 = '#5a6a3a', '#6f8a3c'


def canal_wall():
    """The canal's stone walls (and the cemetery's terrace walls): kenchi-ishi, squarish granite
    stones laid on the diagonal, each with a pyramid face (light upper left, dark lower right),
    dark joints, moss in the lower joints, wet streaks running down (v is down on a wall)."""
    t = Tile(S_MID, 231)
    tones = {}
    for y in range(32):
        for x in range(32):
            a, b = (x + y) // 16, (x - y) // 16
            ka, kb = a % 4, b % 4
            if ka >= 2:
                ka, kb = ka - 2, (kb - 2) % 4
            key = (ka, kb)
            if key not in tones:
                tones[key] = t.r.choice(((S_D1, S_MID, S_L1), (S_MID, S_L1, S_L2), (S_MID, S_L2, S_L3),
                                         (S_D1, S_MID, S_L2)))
            dark, body, light = tones[key]
            u, v = (x + y) % 16, (x - y) % 16          # position within the diamond, 0..15
            if u == 0 or v == 0:
                t.px[y][x] = S_JOINT
            elif u <= 3:
                t.px[y][x] = light                     # upper-left facets
            elif u >= 12:
                t.px[y][x] = dark                      # lower-right facets
            else:
                t.px[y][x] = body
    t.scatter([S_L1, S_D1], 50, where={S_MID, S_L2})
    for _ in range(12):
        x, y = t.r.randrange(32), t.r.randrange(32)
        if t.get(x, y) == S_JOINT and t.r.random() < 0.8:
            t.set(x, y, S_MOSS)
            t.set(x + 1, y, S_MOSS2 if t.r.random() < 0.4 else S_MOSS)
    for _ in range(4):
        x, y = t.r.randrange(32), t.r.randrange(32)
        for k in range(t.r.randint(4, 9)):
            if t.get(x, y + k) != S_JOINT:
                t.set(x, y + k, S_WET)
    save('canal_wall', t)


# ------------------------------------------------------------------- the shrine region's new
def cemetery_gravel():
    """The cemetery's grey river gravel: rounded pebbles of one to four texels, unraked, a tuft of
    moss, a few fallen maple leaves. Scale 2.4 like the shrine's gravel (7.5 cm a texel)."""
    t = Tile('#9a968a', 241)
    t.noise(['#8a867c', '#9a968a', '#9a968a', '#a8a498'], cells=4, jitter=0.3)
    for _ in range(70):
        x, y = t.r.uniform(0, 32), t.r.uniform(0, 32)
        c = t.r.choice(('#b4b0a4', '#c4c0b4', '#a8a498', '#7a766c'))
        if t.r.random() < 0.5:
            t.set(int(x), int(y), c)
        else:
            t.blob(x, y, 1.0, 0.8, c)
            t.set(int(x) + 1, int(y) + 1, '#6a665e')
    t.set(7, 25, '#5f7a34')
    t.set(8, 25, '#6f8a3c')
    leaves(t, 3, MAPLE, dark='#8a2418', kinds=('maple', 'oval'))
    t.leaf(26, 9, '#9a5a2e', None, 'oval')
    save('cemetery_gravel', t)


def bamboo_floor():
    """The bamboo grove's floor: a mat of narrow dry bamboo leaves (straw and tan, a few still
    green-grey), dark soil showing between them, a curl of brown culm sheath."""
    t = Tile('#8a7a48', 242)
    t.noise(['#5a4c2c', '#7a6a40', '#8a7a48', '#8a7a48', '#9a8a54'], cells=4, jitter=0.3)
    for _ in range(46):
        x, y = t.r.randrange(32), t.r.randrange(32)
        c = t.r.choice(('#b8a46a', '#a89458', '#b8a46a', '#6a5a34', '#8a9a48', '#c8c890'))
        a = t.r.choice((0.15, 0.5, 0.8, 1.2, 2.4, 2.8, -0.4)) + t.r.uniform(-0.2, 0.2)
        t.streak(x, y, t.r.randint(3, 5), a, c)
    for k in range(5):
        t.set(20 + k, 12 + (k > 2), '#7a5a34')
        t.set(20 + k, 13 + (k > 2), '#4a3e26')
    t.scatter(['#4a3e26'], 14)
    save('bamboo_floor', t)


def park_grass():
    """The park's grass in late October: worn, yellowing turf in tufts, a bare trodden patch, and
    gold ginkgo leaves fallen from the park's six ginkgo."""
    t = Tile('#6f8a3c', 243)
    t.noise(['#4f6a2c', '#5f7a34', '#6f8a3c', '#7c8a3c', '#8a8a48'], cells=4, jitter=0.3)
    for _ in range(90):
        x, y = t.r.randrange(32), t.r.randrange(32)
        c = t.get(x, y)
        t.set(x, y - 1, {'#4f6a2c': '#5f7a34', '#5f7a34': '#7c8a3c', '#6f8a3c': '#8a9a50',
                         '#7c8a3c': '#8a9a50', '#8a8a48': '#9a9a58'}.get(c, c))
    leaves(t, 4, GINKGO, kinds=('fan',))
    save('park_grass', t)


def park_sand():
    """The playground's sand: pale, raked smooth by the wind, footprints and a few pebbles, a
    ginkgo leaf."""
    t = Tile('#d4c09a', 244)
    t.noise(['#c4b08a', '#d4c09a', '#d4c09a', '#dccaa4', '#e4d4b0'], cells=3, jitter=0.2)
    for fx, fy in ((6, 6), (10, 13), (7, 20), (11, 27)):           # a child's footprints
        t.blob(fx, fy, 1.1, 1.9, '#b8a47e', 0.2)
        t.set(fx, fy - 1, '#c4b08a')
    t.scatter(['#8e887c', '#e4d4b0', '#b8a47e'], 40)
    t.leaf(24, 8, '#f0c030', None, 'fan')
    t.leaf(20, 25, '#d89a20', None, 'fan')
    save('park_sand', t)


ORDER = (asphalt, asphalt_line, asphalt_zebra, asphalt_stop, sidewalk_save, sidewalk_tactile, kerb, plaza,
         concrete, ground, ground_line, canal_wall, cemetery_gravel, bamboo_floor, park_grass, park_sand)

# The shrine world's ground textures this level reuses (shown on the contact sheet with the new).
SHRINE_ART = HERE.parents[2] / 'shrine' / 'assets' / 'art'
REUSED = ('floor', 'litter', 'moss', 'earth', 'path', 'gravel', 'paving', 'steps', 'stone', 'rock', 'pond_bed')

# The edges' art, drawn by their assets' scripts (assets/edge_neighbour, assets/edge_hoarding).
EDGE_ART = [HERE.parents[1] / 'assets' / d / 'art' / f'{n}.png'
            for d, n in (('edge_neighbour', 'facade_a'), ('edge_neighbour', 'facade_b'),
                         ('edge_hoarding', 'panel'), ('edge_hoarding', 'sign'))]

NIGHT = rgb('#4a5884')


def mean_colour(img):
    img = img.convert('RGB'); px = [img.getpixel((x, y)) for y in range(img.height) for x in range(img.width)]
    return tuple(round(sum(p[k] for p in px) / len(px)) for k in range(3))


def night(img):
    return Image.merge('RGB', [ch.point(lambda v, m=m: v * m // 255)
                               for ch, m in zip(img.convert('RGB').split(), NIGHT)])


def contact_sheet(out):
    """Each texture at 1:1, at 4x (64-texel ones 2x), tiled 4 x 4, its far colour (the mean) and
    a 16 x 16 repeat shrunk to 64 pixels (as the distance blends it), then the same at night
    (STYLE.md's multiply); the reused shrine textures and the edges' art after the new ones."""
    from PIL import ImageDraw
    items = [(n, Image.open(HERE / f'{n}.png')) for n in DRAWN] + \
            [(f'shrine:{n}', Image.open(SHRINE_ART / f'terrain_{n}.png')) for n in REUSED] + \
            [(f'{f.parents[1].name}:{f.stem}', Image.open(f)) for f in EDGE_ART if f.exists()]
    row_h = 280
    sheet = Image.new('RGB', (1500, row_h * len(items)), (32, 32, 36))
    d = ImageDraw.Draw(sheet)
    for i, (name, img) in enumerate(items):
        y = i * row_h
        img = img.convert('RGB')
        w, h = img.size
        d.text((8, y + 6), f'{name}  {w}x{h}', fill=(230, 230, 230))
        for k, im in enumerate((img, night(img))):
            x0 = 8 + k * 740
            sheet.paste(im, (x0, y + 24))
            big = im.resize((w * 4 if w <= 32 else w * 2, h * 4 if w <= 32 else h * 2), Image.NEAREST)
            sheet.paste(big, (x0 + 70, y + 24))
            tiled = Image.new('RGB', (w * 4, h * 4))
            for a in range(4):
                for b in range(4):
                    tiled.paste(im, (a * w, b * h))
            tz = 2 if w <= 32 else 1
            tiled = tiled.resize((w * 4 * tz, h * 4 * tz), Image.NEAREST)
            tiled = tiled.crop((0, 0, min(tiled.width, 256), min(tiled.height, 256)))
            sheet.paste(tiled, (x0 + 210, y + 24))
            far = mean_colour(im)
            d.rectangle((x0 + 476, y + 24, x0 + 540, y + 88), fill=far)
            d.text((x0 + 476, y + 92), '#%02x%02x%02x' % far, fill=(230, 230, 230))
            # a fake distance: the tile tiled and shrunk 8x with box filtering, as the eye sees it
            far_t = Image.new('RGB', (w * 16, h * 16))
            for a in range(16):
                for b in range(16):
                    far_t.paste(im, (a * w, b * h))
            far_t = far_t.resize((64, 64), Image.BOX)
            sheet.paste(far_t, (x0 + 560, y + 24))
    sheet.save(out / 'ground_contact.png')
    print('wrote', out / 'ground_contact.png')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--preview', metavar='DIR', help='also write a contact sheet into DIR')
    args = ap.parse_args()
    for draw in ORDER:
        draw()
    for name, t in DRAWN.items():
        print(f'{name}.png  {t.w}x{t.h}  {len(t.colours())} colours  far #%02x%02x%02x' % mean_colour(t.image()))
    if args.preview:
        out = Path(args.preview)
        out.mkdir(parents=True, exist_ok=True)
        contact_sheet(out)
