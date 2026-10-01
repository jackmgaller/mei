#!/usr/bin/env python3
"""Generates the art of "Check-In!" (carts/checkin/): see carts/checkin/CONTRACT.md.

    python3 tools/gen_checkin_art.py [--review DIR]

Outputs, in carts/checkin/art/ (all 4-bit textures, one 32 KB image per used slot):
  tex0.bin      surfaces: 64x64 floor blocks (4x4 tiles each), 16x44 wall cells, the wall cap
  tex1..5.bin   baked object textures
  tex7..9.bin   people sprite sheets (9 frames x 4 directions per body) and carry props
  tex10.bin     build-menu icons (rendered from the meshes) and UI pieces
  palettes.bin  palettes 0..159; pal_obj / pal_ppl / pal_ui the three ranges; pal_day / pal_night
                for art_lights(); pal_water the pool/sea animation frames for art_water()
  <key>.bin, <key>_lo.bin   one mesh per catalogue object and its low-detail version
  save_icon.bin memory card title and 3-frame icon (SaveMeta)
plus carts/checkin/art.akr (declarations only) and carts/checkin/art_load.akr (art_load(),
art_lights(), art_water() and the ART_MESH / ART_MESH_LO pointer tables).

How objects are made: each object has a detailed source model (boxes, cylinders, rods, cards with
materials from bake-only atlases 100/101 and bake-only palettes numbered from 1000) and a
low-poly proxy (PROXY[key]: boxes, cards, a few kept faces for glass and animated water). Every
proxy face gets a texture rendered orthographically from the source through that face (16 texels
per unit; 8 for the _LO versions), so the detail survives at a fraction of the triangles. The
bakes are quantized per object group to one 15-colour palette (the game relights it; colours from
emissive materials are flagged in ART_PAL_EMIT) and packed into slots 1..5.

--review DIR also writes the save icon and grey index images of the atlases there."""
import math, os, struct, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshlib import Mesh, DOUBLE, SEMI
import mei_icon

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CART = os.path.join(ROOT, 'carts', 'checkin')
OUT = os.path.join(CART, 'art')
os.makedirs(OUT, exist_ok=True)
REVIEW = sys.argv[sys.argv.index('--review') + 1] if '--review' in sys.argv else None
if REVIEW:
    os.makedirs(REVIEW, exist_ok=True)

FILES = {}          # name -> bytes written (for the ROM total)


def write(name, data):
    FILES[name] = len(data)
    with open(os.path.join(OUT, name), 'wb') as f:
        f.write(data)


def clamp8(v):
    return int(max(0, min(255, round(v))))


def c15(c):
    r, g, b = (clamp8(v) for v in c[:3])
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)


def rgbw(c):
    r, g, b = (clamp8(v) for v in c[:3])
    return r | (g << 8) | (b << 16)


def hexc(s):
    s = s.lstrip('#')
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def lerp3(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def ramp(stops, n=15):
    """n colours through the stops (evenly spaced)."""
    stops = [hexc(s) if isinstance(s, str) else s for s in stops]
    out = []
    for i in range(n):
        t = i / max(1, n - 1) * (len(stops) - 1)
        k = min(int(t), len(stops) - 2)
        out.append(lerp3(stops[k], stops[k + 1], t - k))
    return out


def mul3(c, k):
    return tuple(v * k for v in c)


# ----------------------------------------------------------------------------- noise

def value_noise(w, h, cx, cy, seed):
    """Smooth value noise, periodic over the image (cx x cy lattice cells)."""
    r = np.random.default_rng(seed)
    lat = r.random((cy + 1, cx + 1))
    lat[-1, :] = lat[0, :]
    lat[:, -1] = lat[:, 0]
    ys = np.linspace(0, cy, h, endpoint=False)
    xs = np.linspace(0, cx, w, endpoint=False)
    xi = xs.astype(int); yi = ys.astype(int)
    xf = xs - xi; yf = ys - yi
    xf = xf * xf * (3 - 2 * xf); yf = yf * yf * (3 - 2 * yf)
    a = lat[np.ix_(yi, xi)]; b = lat[np.ix_(yi, xi + 1)]
    c = lat[np.ix_(yi + 1, xi)]; d = lat[np.ix_(yi + 1, xi + 1)]
    top = a + (b - a) * xf[None, :]
    bot = c + (d - c) * xf[None, :]
    return top + (bot - top) * yf[:, None]


def fbm(w, h, seed, octs=((2, 0.5), (4, 0.3), (8, 0.2))):
    v = sum(wt * value_noise(w, h, o, max(1, o * h // w), seed + i) for i, (o, wt) in enumerate(octs))
    return (v - v.min()) / max(1e-9, v.max() - v.min())


def quant(v, lo=1, hi=15):
    v = np.clip(v, 0, 1)
    return (lo + np.round(v * (hi - lo))).astype(np.uint8)


RNG = np.random.default_rng(1234)

# ----------------------------------------------------------------------------- palettes

PAL = {}            # palette number -> 16 colours (index 0 unused/transparent)
PALNAME = {}        # name -> number
NEXT = {'obj': 0, 'ppl': 96, 'ui': 128, 'src': 1000}
LIMIT = {'obj': 96, 'ppl': 128, 'ui': 160, 'src': 3000}


def palette(name, cols, group='obj'):
    """Registers a 4-bit palette of 15 colours (indices 1..15); returns its number."""
    assert len(cols) == 15, (name, len(cols))
    n = NEXT[group]
    assert n < LIMIT[group], 'out of %s palettes at %s' % (group, name)
    NEXT[group] = n + 1
    PAL[n] = [(0, 0, 0)] + [tuple(clamp8(v) for v in c) for c in cols]
    PALNAME[name] = n
    return n


NIGHT = {}          # palette number -> night version (emissive palettes)

# ----------------------------------------------------------------------------- atlases


class Cell:
    __slots__ = ('name', 'slot', 'u', 'v', 'w', 'h')

    def __init__(self, name, slot, u, v, w, h):
        self.name, self.slot, self.u, self.v, self.w, self.h = name, slot, u, v, w, h


class Atlas:
    def __init__(self, slot):
        self.slot = slot
        self.idx = np.zeros((256, 256), np.uint8)
        self.used = 0
        self.cells = {}

    def put(self, name, u, v, img):
        h, w = img.shape
        assert u + w <= 256 and v + h <= 256, name
        assert img.max() <= 15
        self.idx[v:v + h, u:u + w] = img
        self.used = max(self.used, v + h)
        c = Cell(name, self.slot, u, v, w, h)
        self.cells[name] = c
        return c

    def pack(self):
        rows = self.used
        a = self.idx[:rows]
        return (a[:, 0::2] | (a[:, 1::2] << 4)).astype(np.uint8).tobytes()


ATL = {s: Atlas(s) for s in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100, 101)}
SRC_SURF, SRC_MAT = 100, 101     # bake-only source atlases (old surface cells, object materials)
CELLS = {}


def cell(slot, name, u, v, img):
    c = ATL[slot].put(name, u, v, img)
    CELLS[name] = c
    return c


yy, xx = np.mgrid[0:32, 0:32]

# ============================================================================= source surface cells (bake only)
# Floors: one 32x32 cell per tile. Walls: one cell spans a tile-wide panel the full wall height
# (2.75), so wall patterns are drawn squashed 2.75x vertically (they look right when stretched).
# Facades: one cell spans a tile-wide panel of one storey (3.0).


def squash(img_tall, rows=32):
    """Point-samples a tall (H x 32) index image down to `rows` rows."""
    H = img_tall.shape[0]
    ys = ((np.arange(rows) + 0.5) * H / rows).astype(int)
    return img_tall[ys]


# ---- carpet: a soft cut-pile weave with a sparse tone-on-tone medallion (classic hotel carpet);
# base indices 1..9, motif 10..13
n = fbm(32, 32, 11, ((4, 0.4), (8, 0.35), (16, 0.25)))
img = quant(n * 0.5 + 0.25 + 0.12 * (((xx + yy) % 2) == 0), 1, 9)
d = np.abs(xx - 15.5) + np.abs(yy - 15.5)
img[(d > 10.5) & (d < 12)] = 10
img[(d > 4.5) & (d < 5.6)] = 11
img[d < 1.6] = 12
img[(np.abs(xx - 15.5) < 0.6) & (d < 4.5)] = 11
img[(np.abs(yy - 15.5) < 0.6) & (d < 4.5)] = 11
cd = np.minimum(np.minimum(np.hypot(xx - 0, yy - 0), np.hypot(xx - 31, yy - 31)), np.minimum(np.hypot(xx - 31, yy), np.hypot(xx, yy - 31)))
img[cd < 2.2] = 13
cell(SRC_SURF, 'carpet', 0, 0, img)

# ---- tile: 2x2 square tiles with grout and a bevel; tiles A/B use separate index ranges so a
# palette can make a checkerboard
img = np.zeros((32, 32), np.uint8)
n = fbm(32, 32, 21, ((2, 0.6), (8, 0.4)))
for ty in range(2):
    for tx in range(2):
        b = 2 if (tx + ty) % 2 == 0 else 8
        sl = (slice(ty * 16, ty * 16 + 16), slice(tx * 16, tx * 16 + 16))
        img[sl] = quant(n[sl] * 0.6 + 0.2, b + 1, b + 4)
        img[ty * 16 + 1, tx * 16 + 1:tx * 16 + 15] = b + 5      # bevel highlight
        img[ty * 16 + 1:ty * 16 + 15, tx * 16 + 1] = b + 5
        img[ty * 16 + 14, tx * 16 + 2:tx * 16 + 15] = b
        img[ty * 16 + 2:ty * 16 + 15, tx * 16 + 14] = b
img[0::16, :] = 1
img[:, 0::16] = 1
cell(SRC_SURF, 'tile', 32, 0, img)

# ---- wood floor: planks along x (4 per tile), staggered butt joints, grain
img = np.zeros((32, 32), np.uint8)
g = fbm(32, 32, 31, ((1, 0.25), (16, 0.75)))
for b in range(4):
    shade = (0.0, 0.18, 0.07, 0.25)[b]
    for y in range(b * 8, b * 8 + 8):
        row = g[y] * 0.5 + 0.18 + shade + 0.07 * np.sin(np.arange(32) * 0.7 + b * 2.0 + y * 0.3)
        img[y] = quant(row, 3, 13)
    img[b * 8 + 7, :] = 2
    img[b * 8, :] = np.maximum(img[b * 8, :], 12)
    j = (b * 13 + 5) % 32
    img[b * 8:b * 8 + 7, j] = 2
cell(SRC_SURF, 'wood', 64, 0, img)

# ---- marble: one big polished tile per cell, soft clouding and a few thin veins, thin joint
n = fbm(32, 32, 41, ((2, 0.5), (4, 0.3), (8, 0.2)))
w = fbm(32, 32, 42, ((2, 0.6), (4, 0.4)))
v = np.abs(((w * 2.2 + xx * 0.012 + yy * 0.02) % 1.0) - 0.5)
img = quant(0.5 + 0.4 * n, 6, 13)
img[v < 0.035] = 5
img[(v < 0.016)] = 4
img[0, :] = 2
img[:, 0] = 2
img[1, 1:] = 14
img[1:, 1] = 14
cell(SRC_SURF, 'marble', 96, 0, img)

# ---- deck: teak boards along x with dark gaps and screws
img = np.zeros((32, 32), np.uint8)
g = fbm(32, 32, 51, ((1, 0.3), (16, 0.7)))
for b in range(5):
    y0 = b * 32 // 5
    y1 = (b + 1) * 32 // 5
    for y in range(y0, y1):
        img[y] = quant(g[y] * 0.55 + 0.25 + 0.05 * ((b * 3) % 4), 4, 13)
    img[y1 - 1, :] = 1
    img[y0 + 2, (b * 7 + 3) % 32] = 2
    img[y0 + 2, (b * 7 + 19) % 32] = 2
cell(SRC_SURF, 'deck', 128, 0, img)

# ---- sand: grainy, ripples, a few shells
n = fbm(32, 32, 61, ((4, 0.5), (16, 0.5)))
rip = 0.08 * np.sin((yy + 3 * np.sin(xx * 2 * np.pi / 32)) * 2 * np.pi / 8)
img = quant(n * 0.5 + 0.25 + rip + RNG.random((32, 32)) * 0.15, 3, 13)
img[RNG.random((32, 32)) > 0.99] = 15
cell(SRC_SURF, 'sand', 160, 0, img)

# ---- water (pool and sea): indices 1..12 hold a phase so cycling the palette animates the
# caustics / waves; 13..15 are highlights


def phase_img(seed, scale, wave):
    n = fbm(32, 32, seed, ((2, 0.4), (4, 0.4), (8, 0.2)))
    ph = (n * scale + wave) % 1.0
    return (1 + np.floor(ph * 12)).astype(np.uint8)


wave = (np.sin(xx * 2 * np.pi / 32 * 2) * 0.12 + np.sin(yy * 2 * np.pi / 32 * 3 + xx * 0.2) * 0.1)
img = phase_img(71, 2.0, wave)
cn = fbm(32, 32, 72, ((4, 0.6), (8, 0.4)))
img[np.abs(cn - 0.5) < 0.035] = 14
img[np.abs(cn - 0.5) < 0.012] = 15
cell(SRC_SURF, 'pool_water', 192, 0, img)

img = phase_img(81, 1.5, (yy / 32.0) * 2 + 0.1 * np.sin(xx * 2 * np.pi / 16))
crest = (np.sin((yy * 2 * np.pi / 16) + np.sin(xx * 2 * np.pi / 32) * 1.5) > 0.93)
img[crest] = 14
img[crest & (RNG.random((32, 32)) > 0.5)] = 15
cell(SRC_SURF, 'sea', 224, 0, img)

# ---- walls (pre-squashed: designed on 32 x 88, i.e. 32 texels per unit)
WH = 88
ty, tx = np.mgrid[0:WH, 0:32]


def baseboard(img, h=4):
    img[WH - h:, :] = 14
    img[WH - h, :] = 15
    img[WH - 1, :] = 13
    return img


n = fbm(32, WH, 91, ((2, 0.4), (8, 0.6)))
img = quant(n * 0.25 + 0.55, 4, 11)
img[0:2, :] = 13                                   # ceiling shadow line
cell(SRC_SURF, 'paint', 0, 32, squash(baseboard(img)))

# wallpaper: stripes above a dado rail, wainscot panels below
img = np.zeros((WH, 32), np.uint8)
n = fbm(32, WH, 92, ((2, 0.5), (8, 0.5)))
st = ((tx // 4) % 2 == 0)
img[:] = np.where(st, 9, 7)
img[(tx % 8) == 0] = 6
img = (img + (n > 0.7)).astype(np.uint8)
dado = 58
img[dado:dado + 2, :] = 13
img[dado + 2, :] = 3
img[dado + 3:, :] = 4                             # wainscot (wood-tone indices 3..5)
img[dado + 6:WH - 6, 3:13] = 5
img[dado + 6:WH - 6, 19:29] = 5
img[dado + 6, 3:13] = 3; img[dado + 6:WH - 6, 3] = 3
img[dado + 6, 19:29] = 3; img[dado + 6:WH - 6, 19] = 3
cell(SRC_SURF, 'wallpaper', 32, 32, squash(baseboard(img)))

# damask: a mirrored fleur motif on a two-tone ground
img = np.full((WH, 32), 7, np.uint8)
img[(tx + ty // 2) % 2 == 0] = 8
mot = np.zeros((44, 16), bool)
cy0, cx0 = 22, 8
for y in range(44):
    for x in range(16):
        dx = abs(x + 0.5 - cx0)
        dy = (y + 0.5 - cy0) / 2.2
        r = math.hypot(dx, dy)
        ang = math.atan2(dy, dx)
        if r < 7 and r > 5.0 + 1.6 * math.sin(ang * 3) or (dx < 1.2 and abs(dy) < 6.5) or (r < 2.2):
            mot[y, x] = True
for oy, ox in ((0, 0), (0, 16), (22, 8), (44, 0), (44, 16), (66, 8), (-22, 8)):
    for y in range(44):
        for x in range(16):
            Y, X = oy + y, (ox + x) % 32
            if 0 <= Y < WH and mot[y, x]:
                img[Y, X] = 11
img[0:2, :] = 13
cell(SRC_SURF, 'wallpaper_damask', 64, 32, squash(baseboard(img)))

# stone: ashlar blocks
img = np.zeros((WH, 32), np.uint8)
n = fbm(32, WH, 93, ((4, 0.5), (8, 0.5)))
rowh = 11
for r in range(WH // rowh + 1):
    off = 8 if r % 2 else 0
    y0, y1 = r * rowh, min(WH, (r + 1) * rowh)
    if y0 >= WH:
        break
    for x0 in range(-16, 32, 16):
        xa, xb = max(0, x0 + off), min(32, x0 + off + 16)
        if xa >= xb:
            continue
        k = (r * 7 + x0 * 3) % 5 * 0.05
        img[y0:y1, xa:xb] = quant(n[y0:y1, xa:xb] * 0.45 + 0.35 + k, 4, 12)
        img[y0, xa:xb] = 13
        img[y0:y1, xa] = np.maximum(img[y0:y1, xa], 13)
    img[y1 - 1, :] = 2
    for x0 in range(-16, 48, 16):
        xb = x0 + off + 15
        if 0 <= xb < 32:
            img[y0:y1, xb] = 2
cell(SRC_SURF, 'stone', 96, 32, squash(img))

# ---- facade: one storey (3.0) per cell, designed on 32 x 96
FH = 96
fy, fx = np.mgrid[0:FH, 0:32]
n = fbm(32, FH, 94, ((2, 0.4), (8, 0.6)))


def facade_base():
    img = quant(n * 0.3 + 0.45, 3, 6)               # stucco 3..6
    img[FH - 9:FH - 7, :] = 2                       # slab band shadow
    img[FH - 7:, :] = 14                            # slab band (light trim)
    img[FH - 7, :] = 15
    return img


img = facade_base()
# window: x 5..26, y 16..70 (glass 9..12 gradient, frame 7/8, sill 15)
wx0, wx1, wy0, wy1 = 5, 27, 14, 70
img[wy0 - 2:wy1 + 2, wx0 - 2:wx1 + 2] = 2        # reveal shadow
img[wy0:wy1, wx0:wx1] = 8                          # frame
gy0, gy1 = wy0 + 2, wy1 - 2
for y in range(gy0, gy1):
    t = (y - gy0) / (gy1 - gy0)
    img[y, wx0 + 2:wx1 - 2] = 9 + min(3, int(t * 4))
img[gy0:gy1, 15:17] = 7                            # mullion
img[38:40, wx0 + 2:wx1 - 2] = 7                    # transom
for k in range(6):                                 # diagonal reflection streak
    y = gy0 + 3 + k * 2
    for x in range(wx0 + 4 + k, wx0 + 7 + k):
        if img[y, x] >= 9:
            img[y, x] = 13
img[gy0:gy0 + 4, wx0 + 2:wx1 - 2] = np.where(img[gy0:gy0 + 4, wx0 + 2:wx1 - 2] >= 9, 13, img[gy0:gy0 + 4, wx0 + 2:wx1 - 2])
img[wy1:wy1 + 3, wx0 - 3:wx1 + 3] = 15             # sill
img[wy1 + 3, wx0 - 3:wx1 + 3] = 1
img[wy0 - 4:wy0 - 2, wx0 - 3:wx1 + 3] = 14         # lintel
cell(SRC_SURF, 'facade', 128, 32, squash(img))

img = facade_base()
img[30:34, :] = 14                                 # string course
img[34, :] = 2
cell(SRC_SURF, 'facade_plain', 160, 32, squash(img))

# ground-floor shop-front: tall glazing with a canopy band
img = facade_base()
img[6:12, :] = 15
img[12:14, :] = 1
img[14:FH - 9, 1:31] = 8
for y in range(16, FH - 11):
    t = (y - 16) / (FH - 27)
    img[y, 3:29] = 9 + min(3, int(t * 4))
img[16:FH - 11, 15:17] = 7
for k in range(8):
    y = 20 + k * 3
    for x in range(5 + k, 9 + k):
        img[y, x] = 13
cell(SRC_SURF, 'facade_glass', 192, 32, squash(img))

# ---- extras: grass, pavement, roof gravel, terrazzo
n = fbm(32, 32, 101, ((4, 0.5), (8, 0.3), (16, 0.2)))
img = quant(n * 0.7 + RNG.random((32, 32)) * 0.25, 2, 12)
img[RNG.random((32, 32)) > 0.97] = 14
cell(SRC_SURF, 'grass', 224, 32, img)

img = np.zeros((32, 32), np.uint8)
n = fbm(32, 32, 102, ((4, 0.5), (16, 0.5)))
img[:] = quant(n * 0.4 + 0.45, 5, 11)
img[0, :] = 2; img[:, 0] = 2; img[16, :] = 3; img[:, 16] = 3
img[1, 1:] = 13; img[1:, 1] = 13
cell(SRC_SURF, 'pavement', 0, 64, img)

n = fbm(32, 32, 103, ((8, 0.4), (16, 0.6)))
img = quant(n * 0.6 + RNG.random((32, 32)) * 0.4, 3, 12)
cell(SRC_SURF, 'roof', 32, 64, img)

n = fbm(32, 32, 104, ((4, 0.5), (8, 0.5)))
img = quant(n * 0.3 + 0.55, 8, 12)
chips = RNG.random((32, 32))
img[chips > 0.93] = 3
img[(chips > 0.88) & (chips <= 0.93)] = 14
img[(chips > 0.86) & (chips <= 0.88)] = 5
cell(SRC_SURF, 'terrazzo', 64, 64, img)

# ============================================================================= source object materials (bake only)
# Mostly "ramp" textures: index 1 darkest .. 15 lightest, so any ramp palette colours them.


def ramp_tex(arr, lo=2, hi=14):
    return quant(arr, lo, hi)


# fine wood grain (along u)
g = fbm(32, 32, 201, ((1, 0.2), (32, 0.8)))
img = ramp_tex(g * 0.5 + 0.25 + 0.12 * np.sin(xx * 0.35 + 3 * np.sin(yy * 0.4)), 3, 12)
img[RNG.random((32, 32)) > 0.995] = 2
cell(SRC_MAT, 'grain', 0, 0, img)

# fabric weave
w = ((xx + yy) % 2) * 0.12 + ((xx // 2 + yy // 2) % 2) * 0.06
n = fbm(32, 32, 202, ((4, 0.6), (8, 0.4)))
cell(SRC_MAT, 'fabric', 32, 0, ramp_tex(n * 0.35 + 0.35 + w, 3, 12))

# quilted duvet: diamond stitching with puffy shading
q = (np.sin((xx + yy) * 2 * np.pi / 16) + np.sin((xx - yy) * 2 * np.pi / 16))
img = ramp_tex(0.55 + 0.18 * q, 4, 13)
st = ((xx + yy) % 16 == 0) | (((xx - yy) % 16 + 16) % 16 == 0)
img[st] = 3
cell(SRC_MAT, 'quilt', 64, 0, img)

# chrome / brushed metal: vertical streaks with a bright band
n = fbm(32, 32, 203, ((32, 1.0),))
band = np.exp(-((yy - 9) / 4.0) ** 2) * 0.45 + np.exp(-((yy - 24) / 3.0) ** 2) * 0.2
cell(SRC_MAT, 'chrome', 96, 0, ramp_tex(n[0:1, :].repeat(32, 0) * 0.2 + 0.25 + band, 2, 15))

# leaves: clumps of leaves with shadowed gaps
img = np.zeros((32, 32), np.uint8)
n = fbm(32, 32, 204, ((4, 0.5), (8, 0.5)))
img[:] = ramp_tex(n * 0.5 + 0.1, 2, 7)
for k in range(70):
    cx, cy = RNG.integers(0, 32), RNG.integers(0, 32)
    ang = RNG.random() * math.pi
    L = 3 + RNG.integers(0, 3)
    tone = 8 + RNG.integers(0, 6)
    for s in np.linspace(-1, 1, 2 * L + 1):
        for wv in (-0.5, 0, 0.5):
            X = int(round(cx + s * L * math.cos(ang) - wv * math.sin(ang) * (1 - abs(s)) * 2)) % 32
            Y = int(round(cy + s * L * math.sin(ang) + wv * math.cos(ang) * (1 - abs(s)) * 2)) % 32
            img[Y, X] = tone + (1 if s < 0 else 0)
cell(SRC_MAT, 'leaves', 128, 0, img)

# small bathroom tiles (8 px grid), ramp
img = np.full((32, 32), 11, np.uint8)
img[(xx % 8 == 0) | (yy % 8 == 0)] = 6
img[(xx % 8 == 1) | (yy % 8 == 1)] = 13
img[(xx % 8 == 7) | (yy % 8 == 7)] = 9
cell(SRC_MAT, 'smalltile', 160, 0, img)

# leather: tufted buttons
img = ramp_tex(0.5 + 0.0 * xx, 5, 11)
for by in range(0, 32, 8):
    for bx in range(0, 32, 8):
        ox = 4 if (by // 8) % 2 else 0
        cx, cy = (bx + ox) % 32, by + 4
        dd = np.hypot(((xx - cx + 16) % 32) - 16, yy - cy)
        img[dd < 3.5] = np.minimum(img[dd < 3.5], 7)
        img[dd < 1.2] = 3
        img[(dd > 3.5) & (dd < 4.5) & (yy < cy)] = 12
cell(SRC_MAT, 'leather', 192, 0, img)

# rubber / dark grip (treadmill belt, mats): fine ribs
cell(SRC_MAT, 'ribs', 224, 0, ramp_tex(0.3 + 0.25 * ((yy % 3) == 0) + 0.05 * RNG.random((32, 32)), 2, 8))

# ---- multi-colour cells (bespoke palettes)


def draw_rect(img, x0, y0, x1, y1, c):
    img[y0:y1, x0:x1] = c


# TV / monitor screen: indices 1 bezel dark, 2..6 picture (sky, sea, sand, sun), 7 scanline,
# 8 glare. The picture palette can be swapped (on / off).
img = np.zeros((32, 32), np.uint8)
img[:] = 2
img[0:12, :] = 3
img[12:20, :] = 4
img[20:, :] = 5
sun = np.hypot(xx - 22, yy - 9) < 4
img[sun] = 6
img[(yy % 3) == 0] = 7
img[np.abs(xx - yy - 4) < 2] = np.where(img[np.abs(xx - yy - 4) < 2] != 7, 8, 7)
cell(SRC_MAT, 'screen', 0, 32, img)

# bottles on a shelf (bar back): 1 dark back, 2-4 wood shelf, 5..12 bottle colours, 13-15 glints
img = np.full((32, 32), 1, np.uint8)
img[30:32, :] = 3
img[29, :] = 4
img[14:16, :] = 3
img[13, :] = 4
for row, base in ((13, 0), (29, 1)):
    x = 1
    k = 0
    while x < 30:
        bw = 3 + ((k + base) % 2)
        bh = 9 + ((k * 7 + base * 3) % 4)
        col = 5 + ((k * 5 + base * 3) % 8)
        top = row - bh
        img[top + 4:row, x:x + bw] = col
        img[top:top + 4, x + bw // 2 - (0 if bw < 4 else 1):x + bw // 2 + 1] = col
        img[top + 5:row - 1, x] = 13 + (k % 2)
        img[top, x + bw // 2] = 15
        x += bw + 1
        k += 1
cell(SRC_MAT, 'bottles', 32, 32, img)

# book spines: 1 dark, 2..12 spine colours, 13 gold lettering, 14 shelf
img = np.full((32, 32), 1, np.uint8)
for row in (0, 16):
    x = 0
    k = row // 16 * 3
    while x < 32:
        bw = 2 + (k * 7 % 3)
        bh = 11 + (k * 5 % 4)
        img[row + 15 - bh:row + 15, x:min(32, x + bw)] = 2 + (k * 7) % 11
        img[row + 15 - bh + 2, x:min(32, x + bw)] = 13
        x += bw
        k += 1
    img[row + 15, :] = 14
cell(SRC_MAT, 'books', 64, 32, img)

# washer / dryer front: control strip on top, round porthole door
img = np.full((32, 32), 12, np.uint8)
img[0:7, :] = 10
img[2:5, 3:9] = 3                                 # display
img[2:5, 22:25] = 5; img[2:5, 26:29] = 6          # buttons
img[7, :] = 8
dd = np.hypot(xx - 15.5, yy - 19.5)
img[dd < 11] = 9                                  # chrome ring
img[dd < 9.5] = 2                                 # glass (dark)
img[(dd < 8) & (yy > 19)] = 4                     # laundry / water
img[(dd < 9.5) & (np.abs(xx - yy + 9) < 1.5)] = 13
img[(dd >= 9.5) & (dd < 10.2) & (yy < 15)] = 14
cell(SRC_MAT, 'washer', 96, 32, img)

# stove top: four burners on dark enamel
img = np.full((32, 32), 3, np.uint8)
for cx, cy, r in ((8, 8, 6), (24, 8, 5), (8, 24, 5), (24, 24, 6)):
    dd = np.hypot(xx - cx + 0.5, yy - cy + 0.5)
    img[dd < r] = 1
    img[(dd < r) & (dd > r - 1.5)] = 6
    img[(dd < 2)] = 6
img[(xx % 32 == 0) | (yy % 32 == 0)] = 8
cell(SRC_MAT, 'stovetop', 128, 32, img)

# vending machine front: glass with rows of drinks, coin panel on the right
img = np.full((32, 32), 2, np.uint8)
img[1:30, 1:22] = 3
for r in range(4):
    y0 = 2 + r * 7
    for c in range(5):
        x0 = 2 + c * 4
        img[y0:y0 + 5, x0:x0 + 3] = 5 + (r * 2 + c) % 6
        img[y0, x0 + 1] = 13
    img[y0 + 5, 1:22] = 4
img[1:30, 23:31] = 12
img[4:8, 24:30] = 1
img[11:13, 25:29] = 11
img[20:26, 24:30] = 4
img[np.abs(xx - yy * 0.7 - 3) < 1.0] = np.where(img[np.abs(xx - yy * 0.7 - 3) < 1.0] < 12, 14, 12)
cell(SRC_MAT, 'vending', 160, 32, img)

# jukebox front: arch top with bubble tubes, record window, speaker grille
img = np.zeros((32, 32), np.uint8)
img[:] = 4
for y in range(32):
    for x in range(32):
        dx = (x - 15.5) / 15.5
        if y < 12 and (dx * dx + ((y - 12) / 12.0) ** 2) > 1.0:
            img[y, x] = 0
img[(np.abs(np.hypot(xx - 15.5, yy - 12) - 11) < 1.2) & (yy < 13)] = 9
img[(np.abs(np.hypot(xx - 15.5, yy - 12) - 13.5) < 1.0) & (yy < 13)] = 10
img[12:32, 1:3] = 9; img[12:32, 29:31] = 9
img[12:32, 3:4] = 10; img[12:32, 28:29] = 10
img[8:16, 8:24] = np.where(img[8:16, 8:24] != 0, 3, 0)
dd = np.hypot(xx - 15.5, yy - 12.5)
img[(dd < 3)] = 11
img[17:19, 5:27] = 14
img[20:30, 6:26] = 2
img[20:30:2, 6:26] = 5
img[31, :] = 1
cell(SRC_MAT, 'jukebox', 192, 32, img)

# piano keys (white keys with black keys), 32x16; then a crystal / glass texture 32x16
img = np.full((16, 32), 14, np.uint8)
img[:, ::4] = 8
for k in range(8):
    if k % 7 in (2, 6):
        continue
    x = k * 4 + 3
    img[0:9, x:x + 2] = 1
img[15, :] = 6
cell(SRC_MAT, 'keys', 224, 32, img)
img = np.full((16, 32), 10, np.uint8)
img[(xx[:16] + yy[:16] * 2) % 8 < 2] = 14
img[(xx[:16] - yy[:16] + 64) % 11 == 0] = 15
img[(xx[:16] * 3 + yy[:16]) % 13 == 0] = 6
cell(SRC_MAT, 'crystal', 224, 48, img)

# grille / vent / speaker cloth: ramp
cell(SRC_MAT, 'grille', 0, 64, ramp_tex(0.3 + 0.5 * ((yy % 4) < 2) + 0.06 * RNG.random((32, 32)), 3, 11))

# towels: stacked folded towels with stripe (ramp + accent 13..15)
img = np.zeros((32, 32), np.uint8)
for r in range(4):
    y0 = r * 8
    img[y0:y0 + 8, :] = ramp_tex(fbm(32, 8, 210 + r, ((8, 1.0),)) * 0.3 + 0.55, 6, 12)
    img[y0 + 7, :] = 4
    img[y0, :] = 13
    img[y0 + 3:y0 + 5, :] = 14
cell(SRC_MAT, 'towels', 32, 64, img)

# door: a panelled door, 32 x 64 (ramp; brass knob 15)
img = np.zeros((64, 32), np.uint8)
g = fbm(32, 64, 211, ((1, 0.3), (16, 0.7)))
img[:] = ramp_tex(g * 0.4 + 0.35, 5, 10)
for (x0, y0, x1, y1) in ((4, 4, 28, 28), (4, 34, 28, 60)):
    img[y0:y1, x0:x1] = np.clip(img[y0:y1, x0:x1].astype(int) - 1, 3, 15)
    img[y0, x0:x1] = 3; img[y0:y1, x0] = 3
    img[y1 - 1, x0:x1] = 12; img[y0:y1, x1 - 1] = 12
img[30:34, 24:27] = 15
img[0, :] = 2; img[:, 0] = 2; img[:, 31] = 2
cell(SRC_MAT, 'door', 64, 64, img)

# kitchen oven / dishwasher front: steel ramp with a dark window and handle
img = ramp_tex(fbm(32, 32, 212, ((32, 1.0),))[0:1, :].repeat(32, 0) * 0.25 + 0.55, 8, 13)
img[0:5, :] = 6
img[1:4, 3:8] = 2
img[1:4, 24:27] = 3; img[1:4, 28:31] = 3
img[7:9, 4:28] = 15
img[12:28, 5:27] = 3
img[13:27, 6:26] = 2
img[14:17, 7:25] = 4
cell(SRC_MAT, 'oven', 96, 64, img)

# fridge front: two doors with handles
img = ramp_tex(fbm(32, 32, 213, ((32, 1.0),))[0:1, :].repeat(32, 0) * 0.2 + 0.6, 9, 13)
img[11, :] = 4
img[2:9, 26:28] = 15; img[14:28, 26:28] = 15
img[2:9, 28] = 6; img[14:28, 28] = 6
cell(SRC_MAT, 'fridge', 128, 64, img)

# locker: ramp with vents and handle
img = ramp_tex(0.55 + 0.0 * xx, 7, 11)
for y in (3, 5, 7, 9):
    img[y, 8:24] = 3
img[16:20, 24:27] = 14
img[0, :] = 13; img[:, 0] = 13; img[:, 31] = 4; img[31, :] = 4
cell(SRC_MAT, 'locker', 160, 64, img)

# control panel / screen (projector, treadmill console, elevator buttons): 1 frame, 2 dark,
# 3..5 lights, 6 screen
img = np.full((32, 32), 2, np.uint8)
img[0, :] = 1; img[31, :] = 1; img[:, 0] = 1; img[:, 31] = 1
for r in range(3):
    for c in range(2):
        dd = np.hypot(xx - (11 + c * 10), yy - (8 + r * 8))
        img[dd < 2.6] = 3 + (r + c) % 3
cell(SRC_MAT, 'buttons', 192, 64, img)

# painting / sign / poster: a seaside picture (sky, sea, sand, palm) in 32 x 32
img = np.zeros((32, 32), np.uint8)
img[:] = 3
img[14:22, :] = 4
img[22:, :] = 5
img[np.hypot(xx - 9, yy - 8) < 4] = 6
for t in range(14):
    img[min(31, 30 - t), 22 + t // 4] = 7
for a in range(6):
    ang = a * math.pi / 3
    for s in range(6):
        X, Y = int(25 + s * math.cos(ang)), int(16 + s * math.sin(ang) * 0.6)
        if 0 <= X < 32 and 0 <= Y < 32:
            img[Y, X] = 8
img[0:2, :] = 1; img[30:, :] = 1; img[:, 0:2] = 1; img[:, 30:] = 1
cell(SRC_MAT, 'picture', 224, 64, img)

# lamp shade: soft vertical glow ramp with seams (emissive palette)
img = ramp_tex(0.5 + 0.35 * np.sin(np.clip(yy / 31.0, 0, 1) * math.pi) + 0.05 * ((xx % 8) == 0), 4, 14)
cell(SRC_MAT, 'shade', 0, 96, img)

# glass: faint streaks (used semi-transparent)
img = np.full((32, 32), 8, np.uint8)
img[np.abs((xx + yy) % 24 - 6) < 2] = 12
img[np.abs((xx + yy) % 24 - 10) < 1] = 14
img[0, :] = 15; img[31, :] = 5
cell(SRC_MAT, 'glass', 32, 96, img)


# key rack: grid of pigeonholes (ramp wood) with brass key tags (15) and the odd letter (13)
img = np.full((32, 32), 9, np.uint8)
for r in range(4):
    for c in range(4):
        x0, y0 = c * 8, r * 8
        img[y0 + 1:y0 + 7, x0 + 1:x0 + 7] = 3
        img[y0 + 1, x0 + 1:x0 + 7] = 2
        if (r * 4 + c) % 3 != 1:
            img[y0 + 3:y0 + 6, x0 + 3:x0 + 5] = 15
            img[y0 + 2, x0 + 4] = 13
        if (r * 4 + c) % 5 == 2:
            img[y0 + 4:y0 + 7, x0 + 1:x0 + 6] = 14
cell(SRC_MAT, 'cubbies', 96, 96, img)

# tablecloth with place settings for 4 (white cloth ramp 9..13; plates 15, rims 14, cutlery 6,
# glass 7, napkin 3..4 accent); the table_2 uses the left half rotated
img = quant(fbm(32, 32, 220, ((8, 1.0),)) * 0.3 + 0.6, 10, 12)
img[0, :] = 9; img[31, :] = 9; img[:, 0] = 9; img[:, 31] = 9
for (cx, cy) in ((16, 5), (16, 26), (5, 16), (26, 16)):
    dd = np.hypot(xx - cx + 0.5, yy - cy + 0.5)
    img[dd < 4.2] = 14
    img[dd < 3.0] = 15
img[2:9, 10] = 6; img[2:9, 22] = 6; img[23:30, 10] = 6; img[23:30, 22] = 6
img[10, 2:9] = 6; img[22, 2:9] = 6; img[10, 23:30] = 6; img[22, 23:30] = 6
for (cx, cy) in ((21, 9), (10, 22), (9, 10), (22, 21)):
    img[cy - 1:cy + 1, cx - 1:cx + 1] = 7
dd = np.hypot(xx - 15.5, yy - 15.5)
img[dd < 3] = 4
img[dd < 1.5] = 3
cell(SRC_MAT, 'tablecloth', 128, 96, img)

# buffet food trays: steel tray rims (6..8) with food (1..5, 9..13 colours)
img = np.full((32, 32), 7, np.uint8)
foods = [(2, 3, 4), (9, 10, 11), (12, 13, 5), (3, 11, 13)]
for k in range(4):
    x0 = 1 + k * 8
    img[2:30, x0:x0 + 6] = 6
    n = RNG.random((26, 4))
    a, b, c = foods[k]
    sub = np.where(n < 0.4, a, np.where(n < 0.75, b, c))
    img[3:29, x0 + 1:x0 + 5] = sub
    img[2, x0:x0 + 6] = 8
cell(SRC_MAT, 'food', 160, 96, img)

# cabinet front: two doors with handles (ramp)
img = quant(fbm(32, 32, 221, ((1, 0.3), (16, 0.7))) * 0.3 + 0.5, 6, 11)
img[0, :] = 13; img[31, :] = 3; img[:, 0] = 13; img[:, 31] = 3
img[:, 15] = 3; img[:, 16] = 13
img[3:28, 3] = 4; img[3, 3:13] = 4; img[3:28, 12] = 12; img[27, 3:13] = 12
img[3:28, 19] = 4; img[3, 19:29] = 4; img[3:28, 28] = 12; img[27, 19:29] = 12
img[12:18, 13:15] = 15; img[12:18, 17:19] = 15
cell(SRC_MAT, 'cabinet', 192, 96, img)

# grand stair tread / riser: marble (8..13) sides, red runner (3..5) with brass rods (15)
img = quant(fbm(32, 32, 222, ((4, 0.6), (8, 0.4))) * 0.4 + 0.5, 9, 13)
img[:, 7:25] = quant(fbm(32, 32, 223, ((8, 0.5), (16, 0.5)))[:, 7:25] * 0.6 + 0.3, 3, 5)
img[:, 7] = 2; img[:, 24] = 2
img[:, 8] = 6; img[:, 23] = 6
img[0:2, 6:26] = 15
cell(SRC_MAT, 'runner', 224, 96, img)

# cardboard boxes (ramp, tape 13..14, label 15)
img = quant(fbm(32, 32, 224, ((4, 0.5), (16, 0.5))) * 0.3 + 0.45, 5, 10)
img[:, 14:18] = 12
img[:, 14] = 13
img[20:27, 3:11] = 15
img[22, 4:10] = 3; img[24, 4:9] = 3
img[0, :] = 13; img[31, :] = 3; img[:, 0] = 12; img[:, 31] = 3
cell(SRC_MAT, 'carton', 0, 128, img)

# barrel staves (vertical) with two iron bands (ramp; bands 2..3)
g = fbm(32, 32, 225, ((32, 0.6), (2, 0.4)))
img = quant(g * 0.4 + 0.35 + 0.1 * ((xx % 6) == 0) * -1, 4, 12)
img[:, ::6] = 3
img[5:8, :] = 2; img[5, :] = 13
img[24:27, :] = 2; img[24, :] = 13
cell(SRC_MAT, 'barrel', 32, 128, img)

# neon sign "HOTEL" (index 1 backing, 2..3 pink tube, 4..5 cyan tube), 32 x 16
img = np.full((16, 32), 1, np.uint8)
glyphs = {'H': ["X.X", "X.X", "XXX", "X.X", "X.X"], 'O': ["XXX", "X.X", "X.X", "X.X", "XXX"],
          'T': ["XXX", ".X.", ".X.", ".X.", ".X."], 'E': ["XXX", "X..", "XX.", "X..", "XXX"],
          'L': ["X..", "X..", "X..", "X..", "XXX"]}
x = 2
for ch in "HOTEL":
    gl = glyphs[ch]
    for r, row in enumerate(gl):
        for c, v in enumerate(row):
            if v == 'X':
                img[3 + r * 2:5 + r * 2, x + c * 2 - 0:x + c * 2 + 1] = 2
    x += 6
img[13:15, 2:30] = 4
img[img == 2] = np.where(RNG.random(int((img == 2).sum())) > 0.7, 3, 2)
cell(SRC_MAT, 'neon', 64, 128, img)

# ============================================================================= slot 0: surfaces
# Floors: seamless 64x64 blocks covering 4x4 tiles (16 texels per tile). Walls: 16x44 cells
# covering one tile-wide panel of the full wall height (1 x 2.75 units, 16 texels per unit), and a
# 16x8 cap for the tops of cut-away walls. Everything in slot 0.

B4 = 64
yb, xb = np.mgrid[0:B4, 0:B4]
FLOOR4 = {}         # name -> Cell
WALLS = {}          # name -> Cell


def pnoise(seed, octs):
    return fbm(B4, B4, seed, octs)


def floor_block(name, i, img):
    u, v = (i % 4) * B4, (i // 4) * B4
    FLOOR4[name] = cell(0, 'f4_' + name, u, v, img)


# carpet: cut-pile weave, a diamond lattice every 2 tiles, medallions and dots (base 1..9, motif 10..13)
n = pnoise(301, ((8, 0.4), (16, 0.35), (32, 0.25)))
img = quant(n * 0.5 + 0.25 + 0.10 * (((xb + yb) % 2) == 0), 1, 9)
dx, dy = (xb % 32) - 15.5, (yb % 32) - 15.5
d = np.abs(dx) + np.abs(dy)
img[(d > 14.4) & (d < 15.6)] = 10
img[(d > 5.4) & (d < 6.6)] = 11
img[d < 2.2] = 12
cdist = np.abs(((xb + 16) % 32) - 15.5) + np.abs(((yb + 16) % 32) - 15.5)
img[cdist < 1.6] = 13
floor_block('carpet', 0, img)

# tile: one 16x16 tile per world tile; A/B ranges alternate (a palette can make a checkerboard)
img = np.zeros((B4, B4), np.uint8)
n = pnoise(302, ((4, 0.6), (16, 0.4)))
for ty in range(4):
    for tx in range(4):
        bse = 2 if (tx + ty) % 2 == 0 else 8
        sl = (slice(ty * 16, ty * 16 + 16), slice(tx * 16, tx * 16 + 16))
        img[sl] = quant(n[sl] * 0.6 + 0.2, bse + 1, bse + 4)
        img[ty * 16 + 1, tx * 16 + 1:tx * 16 + 15] = bse + 5
        img[ty * 16 + 1:ty * 16 + 15, tx * 16 + 1] = bse + 5
        img[ty * 16 + 14, tx * 16 + 2:tx * 16 + 15] = bse
        img[ty * 16 + 2:ty * 16 + 15, tx * 16 + 14] = bse
img[0::16, :] = 1
img[:, 0::16] = 1
floor_block('tile', 1, img)

# wood: planks along x, 4 texels wide (4 per tile), staggered butt joints
img = np.zeros((B4, B4), np.uint8)
g = pnoise(303, ((2, 0.25), (32, 0.75)))
for b in range(16):
    shade = ((b * 7) % 5) * 0.06
    for y in range(b * 4, b * 4 + 4):
        row = g[y] * 0.45 + 0.2 + shade + 0.06 * np.sin(np.arange(B4) * 2 * np.pi / 32 * 3 + b * 1.7)
        img[y] = quant(row, 3, 12)
    img[b * 4 + 3, :] = 2
    img[b * 4, :] = np.maximum(img[b * 4, :], 11)
    for j in ((b * 23) % B4, (b * 23 + 37) % B4):
        img[b * 4:b * 4 + 3, j] = 2
floor_block('wood', 2, img)

# marble: one slab per tile, clouding and thin veins crossing slabs, thin joints
n = pnoise(304, ((4, 0.5), (8, 0.3), (16, 0.2)))
w = pnoise(305, ((4, 0.6), (8, 0.4)))
vv = np.abs(((w * 2.4 + xb * 0.008 + yb * 0.012) % 1.0) - 0.5)
img = quant(0.5 + 0.4 * n, 6, 13)
img[vv < 0.03] = 5
img[vv < 0.012] = 4
img[0::16, :] = 2
img[:, 0::16] = 2
img[1::16, :] = np.maximum(img[1::16, :], 13)
floor_block('marble', 3, img)

# terrazzo
n = pnoise(306, ((8, 0.5), (16, 0.5)))
img = quant(n * 0.3 + 0.55, 8, 12)
ch = RNG.random((B4, B4))
img[ch > 0.93] = 3
img[(ch > 0.88) & (ch <= 0.93)] = 14
img[(ch > 0.86) & (ch <= 0.88)] = 5
img[0::32, :] = 4
img[:, 0::32] = 4
floor_block('terrazzo', 4, img)

# concrete: smooth, a few stains, joints every 2 tiles
n = pnoise(307, ((4, 0.5), (16, 0.3), (32, 0.2)))
img = quant(n * 0.35 + 0.45 + RNG.random((B4, B4)) * 0.06, 4, 11)
img[0::32, :] = 2
img[:, 0::32] = 2
img[1::32, :] = np.maximum(img[1::32, :], 12)
floor_block('concrete', 5, img)

# deck: boards along x, 3 texels + gap, screws
img = np.zeros((B4, B4), np.uint8)
g = pnoise(308, ((2, 0.3), (32, 0.7)))
for b in range(16):
    y0 = b * 4
    for y in range(y0, y0 + 3):
        img[y] = quant(g[y] * 0.5 + 0.25 + 0.05 * ((b * 3) % 4), 4, 13)
    img[y0 + 3, :] = 1
    for j in ((b * 29) % B4, (b * 29 + 32) % B4):
        img[y0:y0 + 3, j] = 2
floor_block('deck', 6, img)

# sand: grain, ripples, the odd shell
n = pnoise(309, ((8, 0.5), (32, 0.5)))
rip = 0.07 * np.sin((yb + 4 * np.sin(xb * 2 * np.pi / 64)) * 2 * np.pi / 16)
img = quant(n * 0.5 + 0.25 + rip + RNG.random((B4, B4)) * 0.14, 3, 13)
img[RNG.random((B4, B4)) > 0.995] = 15
floor_block('sand', 7, img)

# grass: tufts and a few daisies
n = pnoise(310, ((8, 0.5), (16, 0.3), (32, 0.2)))
img = quant(n * 0.7 + RNG.random((B4, B4)) * 0.25, 2, 12)
img[RNG.random((B4, B4)) > 0.985] = 14
floor_block('grass', 8, img)

# road: asphalt with fine grit and tar seams
n = pnoise(311, ((8, 0.4), (32, 0.6)))
img = quant(n * 0.3 + 0.35 + RNG.random((B4, B4)) * 0.2, 2, 11)
img[(np.abs(xb - 20 - 6 * np.sin(yb * 2 * np.pi / 64)) < 0.6)] = 1
floor_block('road', 9, img)

# sidewalk / pavement: slabs (one per tile), slight per-slab tone
img = np.zeros((B4, B4), np.uint8)
n = pnoise(312, ((8, 0.5), (32, 0.5)))
for ty in range(4):
    for tx in range(4):
        sl = (slice(ty * 16, ty * 16 + 16), slice(tx * 16, tx * 16 + 16))
        img[sl] = quant(n[sl] * 0.35 + 0.42 + ((tx * 3 + ty * 5) % 4) * 0.03, 5, 11)
img[0::16, :] = 2
img[:, 0::16] = 2
img[1::16, :] = np.maximum(img[1::16, :], 13)
floor_block('pavement', 10, img)

# water: indices 1..12 hold a phase (palette cycling animates them), 13..15 highlights
wave = (np.sin(xb * 2 * np.pi / 64 * 2) * 0.12 + np.sin(yb * 2 * np.pi / 64 * 3 + xb * 0.1) * 0.1)
n = pnoise(313, ((4, 0.4), (8, 0.4), (16, 0.2)))
img = (1 + np.floor(((n * 2.0 + wave) % 1.0) * 12)).astype(np.uint8)
cn = pnoise(314, ((8, 0.6), (16, 0.4)))
img[np.abs(cn - 0.5) < 0.03] = 14
img[np.abs(cn - 0.5) < 0.01] = 15
floor_block('pool_water', 11, img)

n = pnoise(315, ((4, 0.4), (8, 0.4), (16, 0.2)))
img = (1 + np.floor(((n * 1.5 + (yb / 64.0) * 2 + 0.1 * np.sin(xb * 2 * np.pi / 32)) % 1.0) * 12)).astype(np.uint8)
crest = np.sin((yb * 2 * np.pi / 16) + np.sin(xb * 2 * np.pi / 64) * 1.5) > 0.94
img[crest] = 14
img[crest & (RNG.random((B4, B4)) > 0.5)] = 15
floor_block('sea', 12, img)

# roof: gravel
n = pnoise(316, ((16, 0.4), (32, 0.6)))
img = quant(n * 0.5 + RNG.random((B4, B4)) * 0.5, 3, 12)
floor_block('roof', 13, img)

FLOOR4_ALIAS = {'sidewalk': 'pavement', 'terracotta': 'tile'}

# ---- walls: 16 x 44 cells from (128, 192), eight across; the cap below
WH16 = 44
wy, wx = np.mgrid[0:WH16, 0:16]


def wall_cell(name, k, img):
    assert img.shape == (WH16, 16), name
    WALLS[name] = cell(0, 'w_' + name, 128 + k * 16, 192, img)


def base16(img):
    img[WH16 - 2:, :] = 14
    img[WH16 - 2, :] = 15
    img[WH16 - 1, :] = 13
    return img


# paint (4..11 wall, 13 ceiling shadow, 14 baseboard, 15 baseboard edge)
n = fbm(16, WH16, 321, ((2, 0.4), (4, 0.6)))
img = quant(n * 0.25 + 0.55, 4, 11)
img[0, :] = 13
wall_cell('paint', 0, base16(img))

# wallpaper: stripes above a dado rail at 0.9, wainscot below (3..5 wood, 6 pin, 7..10, 13 rail)
img = np.zeros((WH16, 16), np.uint8)
img[:] = np.where((wx // 2) % 2 == 0, 9, 7)
img[(wx % 4) == 0] = 6
img[0, :] = 13
dado = WH16 - 15
img[dado, :] = 13
img[dado + 1, :] = 3
img[dado + 2:, :] = 4
img[dado + 4:WH16 - 4, 3:13] = 5
img[dado + 4, 3:13] = 3; img[dado + 4:WH16 - 4, 3] = 3
wall_cell('wallpaper', 1, base16(img))

# damask (7/8 ground, 11 motif, 13 ceiling shadow)
img = np.full((WH16, 16), 7, np.uint8)
img[(wx + wy) % 2 == 0] = 8
for cy in (8, 30):
    for y in range(WH16):
        for x in range(16):
            ddx = abs(x + 0.5 - 8)
            ddy = (y + 0.5 - cy) / 1.6
            r = math.hypot(ddx, ddy)
            if (3.2 < r < 4.4 and abs(ddy) < 3.8) or (ddx < 0.8 and abs(ddy) < 4.5) or r < 1.2:
                img[y, x] = 11
img[0, :] = 13
wall_cell('damask', 2, base16(img))

# stone: ashlar blocks 8 tall, 16 wide, rows offset by 8
img = np.zeros((WH16, 16), np.uint8)
n = fbm(16, WH16, 322, ((4, 0.5), (8, 0.5)))
for r in range(6):
    y0, y1 = r * 8, min(WH16, r * 8 + 8)
    off = 8 if r % 2 else 0
    img[y0:y1] = quant(n[y0:y1] * 0.45 + 0.35 + 0.06 * ((r * 3) % 3), 4, 12)
    img[y0, :] = 13
    img[y1 - 1, :] = 2
    img[y0:y1, off % 16] = 2
    img[y0:y1, (off + 1) % 16] = np.maximum(img[y0:y1, (off + 1) % 16], 13)
wall_cell('stone', 3, img)

# facades (1 dark, 2 shadow, 3..6 stucco, 7 mullion, 8 frame, 9..12 glass, 13 reflection, 14 trim, 15 trim highlight)
n = fbm(16, WH16, 323, ((2, 0.4), (4, 0.6)))


def fac16():
    img = quant(n * 0.3 + 0.45, 3, 6)
    img[WH16 - 3:, :] = 14
    img[WH16 - 3, :] = 15
    img[WH16 - 4, :] = 2
    return img


img = fac16()
img[6:8, :] = 14
img[8, :] = 2
wall_cell('facade', 4, img)

img = fac16()
x0, x1, y0, y1 = 2, 14, 8, 33
img[y0 - 1:y1 + 1, x0 - 1:x1 + 1] = 2
img[y0:y1, x0:x1] = 8
for y in range(y0 + 1, y1 - 1):
    tt = (y - y0 - 1) / (y1 - y0 - 2)
    img[y, x0 + 1:x1 - 1] = 9 + min(3, int(tt * 4))
img[y0 + 1:y1 - 1, 7:9] = 7
img[18, x0 + 1:x1 - 1] = 7
for k in range(4):
    yy_ = y0 + 2 + k * 2
    for x in range(x0 + 2 + k, x0 + 4 + k):
        if img[yy_, x] >= 9:
            img[yy_, x] = 13
img[y1:y1 + 2, x0 - 1:x1 + 1] = 15
img[y1 + 2, x0 - 1:x1 + 1] = 1
img[y0 - 3:y0 - 1, x0 - 1:x1 + 1] = 14
wall_cell('facade_window', 5, img)

img = fac16()
img[2:5, :] = 15
img[5, :] = 1
img[6:WH16 - 4, 0:16] = 8
for y in range(7, WH16 - 5):
    tt = (y - 7) / (WH16 - 12)
    img[y, 1:15] = 9 + min(3, int(tt * 4))
img[7:WH16 - 5, 0] = 7
img[14, 1:15] = 7
for k in range(5):
    yy_ = 9 + k * 3
    for x in range(2 + k, 4 + k):
        img[yy_, x] = 13
wall_cell('facade_glass', 6, img)

# glass wall (use semi-transparent): chrome frame, faint streaks (glass ramp)
img = np.full((WH16, 16), 8, np.uint8)
img[np.abs((wx + wy) % 20 - 5) < 1.5] = 11
img[np.abs((wx + wy) % 20 - 9) < 0.6] = 13
img[:, 0] = 14; img[:, 15] = 5
img[0, :] = 15; img[WH16 - 1, :] = 4; img[WH16 - 2, :] = 6
wall_cell('glass', 7, img)

# wall cap 16x8 (wall_top ramp): plaster top with darker edges
img = np.full((8, 16), 11, np.uint8)
img[0, :] = 14
img[7, :] = 6
img[1:7, :] = quant(fbm(16, 8, 324, ((4, 1.0),))[1:7] * 0.2 + 0.7, 10, 13)
WALLS['wall_top'] = cell(0, 'w_wall_top', 128, 236, img)


# ============================================================================= object/surface palettes
# Ramp palettes (indices 1 dark .. 15 light) colour every "ramp" texture: grain, fabric, quilt,
# chrome, leaves, smalltile, leather, ribs, grille, towels, door, oven, fridge, locker, cabinet,
# carton, shade, glass, and the wood / deck / grass / roof / pavement / sand floors.


def rp(*stops):
    return ramp(stops)


RAMPS = {
    # woods
    'oak':      rp('2a1a0e', '6e4a2a', 'b07d4c', 'e0b880'),
    'walnut':   rp('180e08', '4a2c18', '7a4e2e', 'a8784e'),
    'cherry':   rp('2a0c08', '6a2a18', 'a8502e', 'd88a5a'),
    'teak':     rp('2a1c10', '6a5034', 'a4845a', 'd4b88a'),
    'ebony':    rp('050508', '14141c', '2c2c38', '6a6a7a'),
    'white':    rp('6a6a70', 'b8b8be', 'e4e4e6', 'ffffff'),
    # fabrics / paints
    'red':      rp('2a0408', '7a1018', 'c02a30', 'f07a70'),
    'burgundy': rp('1a0408', '4a0c18', '7a1a2c', 'b05060'),
    'navy':     rp('060a1a', '142a5a', '2a4c90', '7a9ad0'),
    'teal':     rp('04201e', '0e5a56', '20a098', '90e8d8'),
    'green':    rp('081a0c', '1e4a26', '3a7a40', '9ac890'),
    'mustard':  rp('2a1c04', '7a5a10', 'c89a28', 'f0d888'),
    'cream':    rp('5a5040', 'b0a488', 'e0d4b8', 'fff8e8'),
    'purple':   rp('140820', '3a1a5a', '6a3a9a', 'c0a0e0'),
    'grey':     rp('101014', '3a3a42', '74747e', 'c8c8d0'),
    'coral':    rp('3a1008', 'a03a2a', 'f07a5a', 'ffd0b0'),
    'aqua':     rp('042a3a', '107a9a', '30c0d8', 'c0f4ff'),
    'pink':     rp('3a1020', 'a04a6a', 'e888a8', 'ffe0ec'),
    'black':    rp('020204', '0c0c10', '22222a', '5a5a66'),
    'mint':     rp('0c2a20', '3a8a6a', '80d0b0', 'e0fff4'),
    # metals and misc
    'steel':    rp('1a1c20', '5a6068', 'a8b0b8', 'f0f4f8'),
    'brass':    rp('2a1a04', '7a5410', 'd0a030', 'fff0a0'),
    'leaf':     rp('041008', '0e3a16', '2a7a2a', 'a8e070'),
    'palm':     rp('061206', '1a4a1a', '4a8a2a', 'c8e880'),
    'terracotta': rp('2a0e06', '7a3418', 'c06a3a', 'f0b088'),
    'rubber':   rp('050506', '18181c', '34343c', '60606a'),
    'glass':    rp('203040', '5a8098', 'a0d0e0', 'f0ffff'),
    'sand':     rp('6a5434', 'b49a6a', 'e0cc9a', 'fff4d8'),
    'grass':    rp('0e2a0a', '2a5a1a', '5a8e2e', 'b4d870'),
    'pavement': rp('3a3834', '7a7670', 'b0aca4', 'e8e4dc'),
}
# ramps used by runtime surfaces (floors, kept glass) get real palette numbers; the rest exist
# only to colour the source models that are baked (numbers from 1000, never exported)
RUNTIME_RAMPS = ('oak', 'walnut', 'cherry', 'teak', 'white', 'ebony', 'sand', 'grass', 'pavement', 'grey', 'glass')
for k in RUNTIME_RAMPS:
    palette(k, RAMPS[k])
for k, v in RAMPS.items():
    if k not in RUNTIME_RAMPS:
        palette(k, v, 'src')
palette('deck', RAMPS['teak'])                                    # exterior copy of teak
palette('concrete', rp('3a3c3e', '6e7072', 'a0a2a2', 'd0d0cc'))
palette('road', rp('141416', '2e2e32', '4a4a4e', '7a7a7c'))
palette('wall_top', rp('3a3634', '9a9690', 'd8d4cc', 'fffcf4'))

# lamp shades: warm fabric by day, glowing at night (emissive)
palette('shade', rp('6a5a40', 'c8b48a', 'f0e0bc', 'fff8e8'), 'src')
palette('shade_red', rp('3a1008', '9a3020', 'e07050', 'ffd0b0'), 'src')


def bespoke(name, cols, night=None, group='src'):
    n = palette(name, cols, group)
    if night:
        NIGHT[n] = [(0, 0, 0)] + [tuple(clamp8(v) for v in c) for c in night]
    return n


def cols15(d):
    """Builds 15 colours from {index: colour}; unspecified indices repeat the previous one."""
    out = []
    last = (0, 0, 0)
    for i in range(1, 16):
        if i in d:
            last = hexc(d[i]) if isinstance(d[i], str) else d[i]
        out.append(last)
    return out


# ---- surfaces


def carpet_pal(name, base, motif, hi):
    b = ramp(base, 9)
    m = ramp(motif, 4)
    bespoke(name, b + m + [hexc(hi), hexc(hi)], group='obj')


CARPETS = [('carpet_crimson', ['2a0608', '6a1418', '9a2a28'], ['b04a30', 'd8a048'], 'f0c060'),
           ('carpet_royal', ['060a24', '142a6a', '2a4a9a'], ['4a64b0', 'c8a848'], 'e8c860'),
           ('carpet_emerald', ['04180e', '0e4a2a', '1e7040'], ['3a8a58', 'c8c890'], 'e8e0b0'),
           ('carpet_plum', ['1a0820', '4a1a50', '6a2a6a'], ['8a4a8a', 'd890b8'], 'f0b0d0'),
           ('carpet_teal', ['04201e', '0e4a48', '1a6a66'], ['2a8a84', 'e0906a'], 'f0b090'),
           ('carpet_sand', ['3a2a1a', '7a6040', 'a88a60'], ['b89a70', '6a4a2a'], 'e8d0a0')]
for nm, b, m, h in CARPETS:
    carpet_pal(nm, b, m, h)


def tile_pal(name, grout, a, b):
    A = ramp(a, 4)
    B = ramp(b, 4)
    bespoke(name, [hexc(grout), mul3(A[0], 0.75)] + A + [lerp3(A[3], (255, 255, 255), 0.5), mul3(B[0], 0.75)]
            + B + [lerp3(B[3], (255, 255, 255), 0.5), (255, 255, 255), (255, 255, 255)], group='obj')


tile_pal('tile_white', '8a8a88', ['c8ccd0', 'f0f4f8'], ['c8ccd0', 'f0f4f8'])
tile_pal('tile_check', '6a6a6a', ['d8d8d0', 'fafaf4'], ['101014', '303038'])
tile_pal('tile_terracotta', 'd8c8b0', ['8a3a1e', 'c0663a'], ['8a3a1e', 'c0663a'])
tile_pal('tile_aqua', 'e0f0f0', ['3aa8b8', '7ad8e0'], ['e0f4f4', 'ffffff'])


def marble_pal(name, joint, vein, base, hi):
    bespoke(name, cols15({1: joint, 2: joint, 3: vein, 4: vein, 5: lerp3(hexc(vein), hexc(base[0]), 0.5)})[:5]
            + ramp(base, 8) + [hexc(hi), (255, 255, 255)], group='obj')


marble_pal('marble_white', 'a0a0a0', 'a8acb4', ['d4d4d2', 'f8f8f4'], 'ffffff')
marble_pal('marble_black', '000000', '8a7a5a', ['14141a', '34343c'], '6a6a72')
marble_pal('marble_rose', '8a6a60', 'a87068', ['e0b8a8', 'f8e4dc'], 'fff8f4')
marble_pal('marble_green', '102018', 'a8c8b0', ['0e3a24', '2a6a48'], '6aa088')

# water: indices 1..12 are a phase (cycled for animation), 13..15 highlights


WATER_FRAMES = {}     # palette number -> 4 animation frames (16 colours each), cycled by art_water()


def water_frames(name, deep, light, hi, frames=4):
    base = ramp([deep, light, deep], 13)[:12]
    fr = []
    for f in range(frames):
        sh = f * 3
        fr.append([base[(i + sh) % 12] for i in range(12)] + [hexc(light), hexc(hi), (255, 255, 255)])
    n = bespoke(name, fr[0], group='obj')
    WATER_FRAMES[n] = [[(0, 0, 0)] + [tuple(clamp8(v) for v in c) for c in f] for f in fr]
    return n


water_frames('pool_water', '1a7ab8', '5ad8f0', 'c8fcff')
water_frames('sea', '0a3a7a', '2a7ac0', 'a8e0f8')

# paint (index 4..11 wall, 13 ceiling shadow, 14 baseboard, 15 baseboard edge)
PAINTS = [('paint_white', 'e8e4dc'), ('paint_cream', 'f0dcb0'), ('paint_peach', 'f4b894'),
          ('paint_sage', 'a8c49c'), ('paint_sky', '9cc8e8'), ('paint_lilac', 'c4b0e0'),
          ('paint_coral', 'f08c78'), ('paint_mint', '9ce0c8')]
for nm, c in PAINTS:
    c = hexc(c)
    bespoke(nm, [mul3(c, 0.5)] * 3 + ramp([mul3(c, 0.86), c, lerp3(c, (255, 255, 255), 0.2)], 8)
            + [mul3(c, 0.7), mul3(c, 0.62), (236, 232, 224), (255, 252, 246)], group='obj')

# wallpaper stripes (3..5 wainscot wood, 6 pinstripe, 7..8 ground, 9..10 stripe, 13 dado rail)


def wp_pal(name, wood, ground, stripe, pin, rail):
    W = ramp(wood, 3)
    G = hexc(ground); S = hexc(stripe)
    bespoke(name, [mul3(W[0], 0.6), mul3(W[0], 0.7)] + W + [hexc(pin), G, lerp3(G, (255, 255, 255), 0.12), S,
                                                            lerp3(S, (255, 255, 255), 0.12), S, G, hexc(rail),
                                                            (236, 232, 224), (255, 252, 246)], group='obj')


wp_pal('wallpaper_regency', ['4a2c18', '7a4e2e', 'a8784e'], 'e8dcc0', 'c8b88e', 'b09a6a', 'f4ecd8')
wp_pal('wallpaper_mint', ['f0f0ec', 'ffffff', 'ffffff'], 'cfe8dc', '9ccab4', '7ab09a', 'ffffff')
wp_pal('wallpaper_rose', ['3a1a10', '6a3a24', '9a6a48'], 'f4d8d0', 'e0a8a0', 'c88880', 'fff0e8')
wp_pal('wallpaper_navy', ['e8e0d0', 'f8f4ec', 'ffffff'], '1e2e5a', '2a4078', 'c8a040', 'f8f4ec')

# damask (7/8 ground, 11 motif, 13 ceiling shadow, 14/15 baseboard)


def dm_pal(name, g, m):
    G = hexc(g); M = hexc(m)
    bespoke(name, cols15({1: mul3(G, 0.5), 7: G, 8: lerp3(G, M, 0.12), 9: G, 11: M, 12: M,
                          13: mul3(G, 0.7), 14: (236, 232, 224), 15: (255, 252, 246)}), group='obj')


dm_pal('damask_gold', 'f0e2c0', 'c8a058')
dm_pal('damask_red', '7a1a24', 'c84a50')
dm_pal('damask_teal', '1a5a5a', '58a8a0')

# stone (2 joint, 4..12 stone, 13 joint highlight)
bespoke('stone_sand', cols15({1: '3a2a1a', 2: '5a4630'})[:3] + ramp(['8a7458', 'c8b090', 'eadcc0'], 9) + [hexc('f8f0e0')] * 3, group='obj')
bespoke('stone_slate', cols15({1: '101418', 2: '20262c'})[:3] + ramp(['3a444e', '5a6670', '8a96a0'], 9) + [hexc('a8b4bc')] * 3, group='obj')

# facades: 1 dark, 2 shadow, 3..6 stucco, 7 mullion, 8 frame, 9..12 glass, 13 reflection,
# 14 trim, 15 trim highlight. Three versions per colour: day, night (windows lit), night (dark).


def facade_pals(name, stucco, frame, trim):
    S = ramp([mul3(hexc(stucco), 0.82), hexc(stucco), lerp3(hexc(stucco), (255, 255, 255), 0.25)], 4)
    F = hexc(frame); T = hexc(trim)
    day = [(30, 34, 44), mul3(S[0], 0.62)] + S + [mul3(F, 0.8), F] + ramp(['bfe4f4', '7ab4d8', '3a6a9a', '2a4a74'], 4) \
        + [(240, 250, 255), T, lerp3(T, (255, 255, 255), 0.5)]
    nl = lambda c, k=0.42: (c[0] * k * 0.8, c[1] * k * 0.85, c[2] * k * 1.1)
    lit = [nl(c) for c in day[:8]] + ramp(['fff0b0', 'ffd070', 'f0a040', 'c87828'], 4) + [(255, 250, 220), nl(T), nl(T, 0.55)]
    dark = [nl(c) for c in day[:8]] + ramp(['2a3a5a', '1a2848', '101a34', '0a1028'], 4) + [(60, 80, 120), nl(T), nl(T, 0.55)]
    bespoke(name, day, group='obj')
    bespoke(name + '_lit', lit, group='obj')


facade_pals('facade_cream', 'f0e2c4', 'f8f8f4', 'ffffff')
facade_pals('facade_coral', 'f4a890', 'ffffff', 'fff4ec')
facade_pals('facade_aqua', '9cdcd8', 'ffffff', 'ffffff')

bespoke('terrazzo', cols15({1: '303030', 3: '3a3a40', 4: '3a3a40', 5: 'c86a50', 6: 'c86a50', 8: 'd8d0c4',
                            9: 'e2dace', 10: 'ece6dc', 11: 'f4f0e8', 12: 'fcf8f2', 13: 'ffffff', 14: '7ab0b8', 15: 'ffffff'}), group='obj')

# ---- object bespoke palettes
bespoke('screen_off', cols15({1: '08080a', 2: '1a2024', 3: '1e2428', 4: '222a2e', 5: '262c30', 6: '2a3236',
                              7: '161a1e', 8: '3a4a50', 9: '3a4a50'}),
        night=None)
bespoke('screen_on', cols15({1: '08080a', 2: '204060', 3: '5ab0f0', 4: '2a6ab8', 5: 'f0d890', 6: 'fff4a0',
                             7: '204a80', 8: 'c0f0ff'}),
        night=cols15({1: '08080a', 2: '305878', 3: '80d0ff', 4: '4090e0', 5: 'fff0b0', 6: 'ffffc0',
                      7: '3060a0', 8: 'e0ffff'}))
bespoke('bottles', cols15({1: '1a120c', 2: '3a2414', 3: '6a4424', 4: 'a07040', 5: '2a7a3a', 6: '8a2a1a',
                           7: 'c89030', 8: '3a5aa0', 9: 'e0e0d0', 10: '6a1a3a', 11: 'd06a20', 12: '4aa0a0',
                           13: 'ffffff', 14: 'c0e0e0', 15: 'ffffff'}))
bespoke('books', cols15({1: '120c08', 2: '8a2020', 3: '204a8a', 4: '2a6a3a', 5: 'c8a040', 6: '6a3a7a',
                         7: 'a85a2a', 8: '303038', 9: 'e0d8c0', 10: '1a5a6a', 11: 'b03a5a', 12: '5a4a2a',
                         13: 'e8c060', 14: '5a3a20', 15: 'ffffff'}))
bespoke('washer', cols15({1: '101014', 2: '1a2a3a', 3: '40f0a0', 4: '6aa8d8', 5: 'e04040', 6: '40a0e0',
                          8: 'a8acb4', 9: 'c8d0d8', 10: 'd8dce0', 12: 'f4f6f8', 13: 'e0f0ff', 14: 'ffffff', 15: 'ffffff'}))
bespoke('dryer', cols15({1: '101014', 2: '2a2420', 3: 'ffa040', 4: 'c8a080', 5: 'e04040', 6: 'f0c040',
                         8: '9a9ca4', 9: 'b8bcc4', 10: 'c8ccd4', 12: 'e4e8ee', 13: 'fff0e0', 14: 'ffffff', 15: 'ffffff'}))
bespoke('stovetop', cols15({1: '0a0a0c', 3: '26262c', 6: '5a5a64', 8: '8a8a94'}))
bespoke('vending', cols15({1: '0a0a10', 2: '1a1a24', 3: '2a3a4a', 4: '8a9aa8', 5: 'e03030', 6: '30a0e0',
                           7: 'f0c020', 8: '40c050', 9: 'f07020', 10: 'ffffff', 11: 'f0c020', 12: 'c02030',
                           13: 'ffffff', 14: '90c8e8', 15: 'ffffff'}),
        night=cols15({1: '0a0a10', 2: '1a1a24', 3: '6a9ac8', 4: 'c0d8f0', 5: 'ff5050', 6: '60d0ff',
                      7: 'ffe040', 8: '70ff80', 9: 'ffa040', 10: 'ffffff', 11: 'ffe060', 12: 'e03040',
                      13: 'ffffff', 14: 'd0f0ff', 15: 'ffffff'}))
bespoke('jukebox', cols15({1: '1a0a04', 2: '3a2010', 3: 'f0d080', 4: '8a2a1a', 5: 'c89040', 9: 'f05030',
                           10: 'f0c030', 11: '40c0f0', 14: 'e0e0e0', 15: 'ffffff'}),
        night=cols15({1: '1a0a04', 2: '5a3010', 3: 'fff0b0', 4: 'b03a20', 5: 'ffc060', 9: 'ff7040',
                      10: 'ffe060', 11: '80f0ff', 14: 'ffffff', 15: 'ffffff'}))
bespoke('buttons', cols15({1: 'a0a8b0', 2: '2a2e34', 3: 'f0c040', 4: '40e070', 5: 'f05040', 6: '60c0f0'}),
        night=cols15({1: 'a0a8b0', 2: '2a2e34', 3: 'ffe070', 4: '70ff90', 5: 'ff7060', 6: '90e0ff'}))
bespoke('picture', cols15({1: 'c8a040', 3: '7ac0f0', 4: '2a7ab8', 5: 'f0dca0', 6: 'fff0a0', 7: '6a4a2a', 8: '3a8a3a'}))
bespoke('crystal', ramp(['8a7a6a', 'f0e0c0', 'fffcf0', 'ffffff']),
        night=ramp(['c08a40', 'ffe0a0', 'fff8e0', 'ffffff']))
bespoke('tablecloth', cols15({1: 'a0a0a0', 3: '8a1a24', 4: 'c84a50', 6: 'b0b4c0', 7: 'c8e8f0', 9: 'c8c8c4',
                              10: 'e8e8e4', 11: 'f2f2ee', 12: 'fafaf6', 14: 'd0d4dc', 15: 'ffffff'}))
bespoke('food', cols15({1: '1a1a1a', 2: 'e0a040', 3: 'f0d080', 4: 'c06a2a', 5: '6ab040', 6: '8a9098',
                        7: 'c0c8d0', 8: 'f0f4f8', 9: 'e04a3a', 10: 'f0e8d0', 11: '8a5a3a', 12: '4a8a30', 13: 'f0c040'}))
bespoke('runner', cols15({1: '000000', 2: '3a0408', 3: '7a1018', 4: '9a1a20', 5: 'b82a2a', 6: 'e0c070',
                          9: 'd8d4cc', 10: 'e4e0d8', 11: 'eeeae4', 12: 'f6f4f0', 13: 'ffffff', 15: 'f0d060'}))
bespoke('cubbies', cols15({1: '1a0e06', 2: '2a1a0e', 3: '3a2414', 9: 'a8784e', 13: 'f4f0e0', 14: 'f8f4e8', 15: 'e8c050'}))
bespoke('mirror', ramp(['3a5060', '8ab0c8', 'd0e8f4', 'ffffff']))
bespoke('neon', cols15({1: '200810', 2: 'ff3a8a', 3: 'ff90c0', 4: '40f0ff', 5: 'c0ffff'}),
        night=cols15({1: '300c18', 2: 'ff60a0', 3: 'ffd0e8', 4: '80ffff', 5: 'ffffff'}))


# ============================================================================= mesh toolkit


def v_sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def v_add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def v_mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def v_dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def v_cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def v_norm(a):
    l = math.sqrt(v_dot(a, a)) or 1.0
    return (a[0] / l, a[1] / l, a[2] / l)


class Mat:
    """A surface: a flat colour (Gouraud-shaded) or a texture cell with a palette.
    glow: not shaded (emissive). semi: blend mode for semi-transparency. double: two-sided.
    fit: stretch the whole cell over each face (else 32 texels per unit, cropped to the cell).
    sub: (u0, v0, u1, v1) fraction of the cell to use. k: brightness multiplier."""

    def __init__(self, col=None, cell=None, pal=None, glow=False, semi=None, double=False, fit=False,
                 sub=None, k=1.0, dens=32.0, flipu=False, frame=None, rot90=False, excl=False, bake=None):
        self.col = hexc(col) if isinstance(col, str) else col
        self.cell = CELLS[cell] if isinstance(cell, str) else cell
        self.pal = PALNAME[pal] if isinstance(pal, str) else pal
        self.glow, self.semi, self.double, self.fit, self.sub = glow, semi, double, fit, sub
        self.k, self.dens, self.flipu = k, dens, flipu
        self.frame, self.rot90 = frame, rot90
        self.excl, self.bake = excl, bake

    def but(self, **kw):
        m = Mat.__new__(Mat)
        for a in ('col', 'cell', 'pal', 'glow', 'semi', 'double', 'fit', 'sub', 'k', 'dens', 'flipu', 'frame', 'rot90',
                  'excl', 'bake'):
            setattr(m, a, getattr(self, a))
        for a, v in kw.items():
            if a == 'pal' and isinstance(v, str):
                v = PALNAME[v]
            if a == 'cell' and isinstance(v, str):
                v = CELLS[v]
            if a == 'col' and isinstance(v, str):
                v = hexc(v)
            setattr(m, a, v)
        return m



def C(col, **kw):
    return Mat(col=col, **kw)


def T(cell, pal, **kw):
    return Mat(cell=cell, pal=pal, **kw)


class Face:
    __slots__ = ('pts', 'n', 'mat', 'shade', 'tag')

    def __init__(self, pts, n, mat, shade=1.0, tag=''):
        self.pts, self.n, self.mat, self.shade, self.tag = pts, n, mat, shade, tag


def light(n, y, mat):
    """Baked light (1.0 = full): bright tops, mid sides, darker near the floor. Rotation-invariant
    apart from a slight bias, because the game turns objects in 90-degree steps."""
    if mat.glow:
        return 1.0
    ny = n[1]
    if ny > 0.6:
        f = 0.96 + 0.06 * ny
    elif ny < -0.6:
        f = 0.50
    else:
        f = 0.76 + 0.22 * ny + 0.04 * (n[0] * -0.6 + n[2] * 0.8)
        f *= 0.80 + 0.20 * min(1.0, max(0.0, y) / 0.5)
    return f


def tex_avg(cell, pal):
    a = ATL[cell.slot].idx[cell.v:cell.v + cell.h, cell.u:cell.u + cell.w]
    P = PAL[pal]
    m = a > 0
    if not m.any():
        return (128, 128, 128)
    cols = np.array([P[i] for i in a[m]], float)
    return tuple(cols.mean(0))


def face_axes(n):
    """Right and up directions on a face for a viewer looking at it from outside."""
    if abs(n[1]) > 0.85:
        R = (-1.0, 0.0, 0.0) if n[1] > 0 else (1.0, 0.0, 0.0)
        U = (0.0, 0.0, -1.0)
    else:
        R = v_norm((-n[2], 0.0, n[0]))
        U = v_norm(v_sub((0.0, 1.0, 0.0), v_mul(n, n[1])))
    return R, U


def face_uvs(f):
    """Planar texture coordinates: u to the viewer's right, v down, seen from outside."""
    n = f.n
    mat = f.mat
    c = mat.cell
    R, U = face_axes(n)
    if mat.flipu:
        R = v_mul(R, -1)
    if mat.rot90:
        R, U = U, v_mul(R, -1)
    s = [v_dot(p, R) for p in f.pts]
    t = [v_dot(p, U) for p in f.pts]
    s0, s1, t0, t1 = min(s), max(s), min(t), max(t)
    if mat.frame:
        s0, s1, t0, t1 = mat.frame
    cu, cv, cw, ch = c.u, c.v, c.w, c.h
    if mat.sub:
        a, b, e, d = mat.sub
        cu, cv, cw, ch = cu + int(round(a * cw)), cv + int(round(b * ch)), int(round((e - a) * cw)), int(round((d - b) * ch))
    sw, th = max(1e-6, s1 - s0), max(1e-6, t1 - t0)
    if mat.excl:
        ku, kv = cw / sw, ch / th
    elif mat.fit:
        ku, kv = (cw - 1) / sw, (ch - 1) / th
    else:
        ku = min(mat.dens, (cw - 1) / sw)
        kv = min(mat.dens, (ch - 1) / th)
    out = []
    for si, ti in zip(s, t):
        u = cu + (si - s0) * ku
        v = cv + (t1 - ti) * kv
        out.append((int(round(u)), int(round(v))))
    return out


def face_colours(f):
    out = []
    for p in f.pts:
        L = light(f.n, p[1], f.mat) * f.shade * f.mat.k
        if f.mat.cell is not None:
            v = 128 * L
            out.append(rgbw((v, v, v)))
        else:
            out.append(rgbw(mul3(f.mat.col, L)))
    return out


def emit(faces):
    """Builds a Mesh. Faces are emitted in reverse order of construction, so details added after
    the surfaces they sit on win ties in an ordering-table bucket (they are drawn later)."""
    m = Mesh()
    vmap = {}

    def vid(p):
        key = tuple(round(c, 4) for c in p)
        if key not in vmap:
            vmap[key] = m.vertex(*p)
        return vmap[key]

    for f in reversed(faces):
        pts = list(f.pts)
        uvs = face_uvs(f) if f.mat.cell is not None else None
        cols = face_colours(f)
        c = v_cross(v_sub(pts[1], pts[0]), v_sub(pts[2], pts[0]))
        if v_dot(c, f.n) > 0:
            order = [1, 0, 3, 2] if len(pts) == 4 else [1, 0, 2]
            pts = [pts[i] for i in order]
            cols = [cols[i] for i in order]
            if uvs:
                uvs = [uvs[i] for i in order]
        flags = 0
        if f.mat.semi is not None:
            flags |= SEMI
        if f.mat.double:
            flags |= DOUBLE
        mat = f.mat
        kw = {}
        if mat.cell is not None:
            kw = dict(slot=mat.cell.slot, four_bit=True, palette=mat.pal)
        m.face([vid(p) for p in pts], cols, uvs, flags, blend=mat.semi or 0, **kw)
    return m


def tri_count(faces):
    return sum(2 if len(f.pts) == 4 else 1 for f in faces)


def face_normal(pts):
    return v_norm(v_mul(v_cross(v_sub(pts[1], pts[0]), v_sub(pts[2], pts[0])), -1))


class B:
    """Collects faces for one object. Corner order for quads is strip order (BL, BR, TL, TR seen
    from outside); emit() fixes the winding from the normal, so only the strip order matters."""

    def __init__(self):
        self.faces = []
        self.tag = ''

    def add(self, pts, mat, n=None, shade=1.0):
        if n is None:
            n = face_normal(pts)
        self.faces.append(Face([tuple(p) for p in pts], n, mat, shade, self.tag))

    def quad(self, a, b, c, d, mat, n=None, shade=1.0):
        self.add([a, b, c, d], mat, n, shade)

    def tri(self, a, b, c, mat, n=None, shade=1.0):
        self.add([a, b, c], mat, n, shade)

    def box(self, x0, y0, z0, x1, y1, z1, mat, skip='b', mats=None, shade=1.0):
        """Axis-aligned box. Face keys: t top, b bottom, f front (+z), k back (-z), l left (-x),
        r right (+x). mats overrides materials per key."""
        mats = mats or {}
        g = lambda k: mats.get(k, mat)
        if 't' not in skip:
            self.quad((x1, y1, z1), (x0, y1, z1), (x1, y1, z0), (x0, y1, z0), g('t'), (0, 1, 0), shade)
        if 'b' not in skip:
            self.quad((x0, y0, z1), (x1, y0, z1), (x0, y0, z0), (x1, y0, z0), g('b'), (0, -1, 0), shade)
        if 'f' not in skip:
            self.quad((x1, y0, z1), (x0, y0, z1), (x1, y1, z1), (x0, y1, z1), g('f'), (0, 0, 1), shade)
        if 'k' not in skip:
            self.quad((x0, y0, z0), (x1, y0, z0), (x0, y1, z0), (x1, y1, z0), g('k'), (0, 0, -1), shade)
        if 'l' not in skip:
            self.quad((x0, y0, z1), (x0, y0, z0), (x0, y1, z1), (x0, y1, z0), g('l'), (-1, 0, 0), shade)
        if 'r' not in skip:
            self.quad((x1, y0, z0), (x1, y0, z1), (x1, y1, z0), (x1, y1, z1), g('r'), (1, 0, 0), shade)

    def boxc(self, cx, cz, w, d, y0, y1, mat, **kw):
        self.box(cx - w / 2, y0, cz - d / 2, cx + w / 2, y1, cz + d / 2, mat, **kw)

    def ring(self, cx, cz, r, n, rot=0.0, rz=None):
        rz = r if rz is None else rz
        return [(cx + r * math.cos(rot + 2 * math.pi * i / n), cz + rz * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]

    def poly_top(self, poly, y, mat, down=False):
        """Convex polygon [(x, z)] at height y as quads (+ one triangle)."""
        P = [(x, y, z) for x, z in poly]
        n = (0, -1, 0) if down else (0, 1, 0)
        k = len(P)
        i = 1
        while i + 2 < k:
            self.quad(P[i], P[0], P[i + 1], P[i + 2], mat, n)
            i += 2
        if i + 1 < k:
            self.tri(P[0], P[i], P[i + 1], mat, n)

    def prism(self, poly, y0, y1, mat, top=None, sides=None, cap=True, skip_edges=()):
        """Extrudes a convex polygon [(x, z)] (any winding) from y0 to y1."""
        k = len(poly)
        cx = sum(p[0] for p in poly) / k
        cz = sum(p[1] for p in poly) / k
        for i in range(k):
            if i in skip_edges:
                continue
            a, b = poly[i], poly[(i + 1) % k]
            mx, mz = (a[0] + b[0]) / 2 - cx, (a[1] + b[1]) / 2 - cz
            ex, ez = b[0] - a[0], b[1] - a[1]
            n = v_norm((ez, 0, -ex))
            if n[0] * mx + n[2] * mz < 0:
                n = v_mul(n, -1)
            self.quad((a[0], y0, a[1]), (b[0], y0, b[1]), (a[0], y1, a[1]), (b[0], y1, b[1]), sides or mat, n)
        if cap:
            self.poly_top(poly, y1, top or mat)

    def cyl(self, cx, cz, r, y0, y1, n, mat, top=None, cap=True, rot=None, r1=None, rz=None):
        """n-sided cylinder (or frustum when r1, the top radius, is given)."""
        rot = math.pi / n if rot is None else rot
        r1 = r if r1 is None else r1
        rz = 1.0 if rz is None else rz
        lo = [(cx + r * math.cos(rot + 2 * math.pi * i / n), cz + r * rz * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]
        hi = [(cx + r1 * math.cos(rot + 2 * math.pi * i / n), cz + r1 * rz * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]
        for i in range(n):
            j = (i + 1) % n
            a0, b0, a1, b1 = (lo[i][0], y0, lo[i][1]), (lo[j][0], y0, lo[j][1]), (hi[i][0], y1, hi[i][1]), (hi[j][0], y1, hi[j][1])
            mx, mz = (lo[i][0] + lo[j][0] + hi[i][0] + hi[j][0]) / 4 - cx, (lo[i][1] + lo[j][1] + hi[i][1] + hi[j][1]) / 4 - cz
            nn = face_normal([a0, b0, a1])
            if nn[0] * mx + nn[2] * mz < 0:
                nn = v_mul(nn, -1)
            self.quad(a0, b0, a1, b1, mat, nn)
        if cap and r1 > 0:
            self.poly_top(hi, y1, top or mat)

    def cone(self, cx, cz, r, y0, y1, n, mat, rot=None, apex=None):
        rot = math.pi / n if rot is None else rot
        ax, az = (cx, cz) if apex is None else apex
        lo = [(cx + r * math.cos(rot + 2 * math.pi * i / n), cz + r * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]
        for i in range(n):
            j = (i + 1) % n
            a, b, c = (lo[i][0], y0, lo[i][1]), (lo[j][0], y0, lo[j][1]), (ax, y1, az)
            nn = face_normal([a, b, c])
            mx, mz = (lo[i][0] + lo[j][0]) / 2 - cx, (lo[i][1] + lo[j][1]) / 2 - cz
            if nn[0] * mx + nn[2] * mz < 0 and y1 > y0 or (y1 < y0 and nn[1] > 0):
                nn = v_mul(nn, -1)
            self.tri(a, b, c, mat, nn)

    def panel(self, x0, y0, x1, y1, z, mat, back=False):
        """A vertical rectangle in the x/y plane at depth z, facing +z (or -z)."""
        n = (0, 0, -1) if back else (0, 0, 1)
        self.quad((x1, y0, z), (x0, y0, z), (x1, y1, z), (x0, y1, z), mat, n)

    def panel_x(self, z0, y0, z1, y1, x, mat, neg=False):
        n = (-1, 0, 0) if neg else (1, 0, 0)
        self.quad((x, y0, z0), (x, y0, z1), (x, y1, z0), (x, y1, z1), mat, n)

    def flat(self, x0, z0, x1, z1, y, mat):
        self.quad((x1, y, z1), (x0, y, z1), (x1, y, z0), (x0, y, z0), mat, (0, 1, 0))

    def bar(self, p0, p1, w, mat, cap=True):
        """A square bar between two points (for rails, legs, arms)."""
        d = v_norm(v_sub(p1, p0))
        up = (0, 1, 0) if abs(d[1]) < 0.9 else (1, 0, 0)
        a = v_norm(v_cross(d, up))
        b = v_norm(v_cross(a, d))
        h = w / 2
        cs = [v_add(v_mul(a, sa * h), v_mul(b, sb * h)) for sa, sb in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
        for i in range(4):
            j = (i + 1) % 4
            q0, q1 = v_add(p0, cs[i]), v_add(p0, cs[j])
            q2, q3 = v_add(p1, cs[i]), v_add(p1, cs[j])
            nn = v_norm(v_add(cs[i], cs[j]))
            self.quad(q0, q1, q2, q3, mat, nn)
        if cap:
            top = p1 if p1[1] >= p0[1] else p0
            sgn = 1 if top is p1 else -1
            q = [v_add(top, c) for c in cs]
            self.quad(q[0], q[1], q[3], q[2], mat, v_mul(d, sgn))

    def rod(self, p0, p1, w, mat):
        """A thin three-sided rod between two points (6 triangles)."""
        d = v_norm(v_sub(p1, p0))
        up = (0, 1, 0) if abs(d[1]) < 0.9 else (0, 0, 1)
        a = v_norm(v_cross(d, up))
        b2 = v_norm(v_cross(a, d))
        cs = [v_add(v_mul(a, w * 0.6 * math.cos(t)), v_mul(b2, w * 0.6 * math.sin(t))) for t in (math.pi / 2, math.pi * 7 / 6, math.pi * 11 / 6)]
        for i in range(3):
            j = (i + 1) % 3
            self.quad(v_add(p0, cs[i]), v_add(p0, cs[j]), v_add(p1, cs[i]), v_add(p1, cs[j]), mat, v_norm(v_add(cs[i], cs[j])))

    def xform(self, fn, start=0):
        """Applies fn(p) -> p to the faces added since index start (normals recomputed)."""
        for f in self.faces[start:]:
            f.pts = [fn(p) for p in f.pts]
            nn = face_normal(f.pts)
            f.n = nn if v_dot(nn, f.n) >= 0 or True else nn

    def mark(self):
        return len(self.faces)

    def rot(self, start, axis, ang, origin=(0.0, 0.0, 0.0)):
        """Rotates faces added since start about an axis ('x', 'y' or 'z') through origin."""
        s, c = math.sin(ang), math.cos(ang)

        def r(v):
            x, y, z = v
            if axis == 'x':
                return (x, y * c - z * s, y * s + z * c)
            if axis == 'z':
                return (x * c - y * s, x * s + y * c, z)
            return (x * c + z * s, y, -x * s + z * c)
        for f in self.faces[start:]:
            f.pts = [v_add(r(v_sub(p, origin)), origin) for p in f.pts]
            f.n = r(f.n)

    def fill(self, poly, y, mat, down=False):
        """Any simple polygon [(x, z)] at height y, by ear clipping (triangles)."""
        P = list(poly)
        area = sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))
        if area < 0:
            P = P[::-1]
        n = (0, -1, 0) if down else (0, 1, 0)

        def cr(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        def inside(p, a, b, c):
            return cr(a, b, p) >= 0 and cr(b, c, p) >= 0 and cr(c, a, p) >= 0
        guard = 0
        while len(P) > 3 and guard < 500:
            guard += 1
            for i in range(len(P)):
                a, b, c = P[i - 1], P[i], P[(i + 1) % len(P)]
                if cr(a, b, c) <= 1e-9:
                    continue
                if any(inside(q, a, b, c) for q in P if q not in (a, b, c)):
                    continue
                self.tri((a[0], y, a[1]), (b[0], y, b[1]), (c[0], y, c[1]), mat, n)
                P.pop(i)
                break
        a, b, c = P
        self.tri((a[0], y, a[1]), (b[0], y, b[1]), (c[0], y, c[1]), mat, n)

    def extrude(self, poly, y0, y1, mat, top=None, cap=True):
        """Extrudes any simple polygon (outward normals from the winding)."""
        P = list(poly)
        area = sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))
        k = len(P)
        for i in range(k):
            a, b = P[i], P[(i + 1) % k]
            ex, ez = b[0] - a[0], b[1] - a[1]
            n = v_norm((ez, 0, -ex)) if area > 0 else v_norm((-ez, 0, ex))
            self.quad((a[0], y0, a[1]), (b[0], y0, b[1]), (a[0], y1, a[1]), (b[0], y1, b[1]), mat, n)
        if cap:
            self.fill(P, y1, top or mat)

    def rot_y(self, start, yaw, ox=0.0, oz=0.0):
        """Turns faces added since start about +Y by yaw (turning +Z toward +X) around (ox, oz)."""
        s, c = math.sin(yaw), math.cos(yaw)

        def tp(p):
            x, z = p[0] - ox, p[2] - oz
            return (ox + x * c + z * s, p[1], oz - x * s + z * c)

        def tn(n):
            return (n[0] * c + n[2] * s, n[1], -n[0] * s + n[2] * c)
        for f in self.faces[start:]:
            f.pts = [tp(p) for p in f.pts]
            f.n = tn(f.n)

    def move(self, start, dx, dy, dz):
        for f in self.faces[start:]:
            f.pts = [(p[0] + dx, p[1] + dy, p[2] + dz) for p in f.pts]


def face_avg_colour(f):
    if f.mat.cell is not None:
        c = tex_avg(f.mat.cell, f.mat.pal)
    else:
        c = f.mat.col
    return c


def auto_lo(faces, boxes=None):
    """Low-detail version: a box (or the given boxes) coloured by the averages of the full mesh."""
    xs = [p[0] for f in faces for p in f.pts]
    ys = [p[1] for f in faces for p in f.pts]
    zs = [p[2] for f in faces for p in f.pts]
    tops, sides = [], []
    for f in faces:
        if f.mat.semi is not None:
            continue
        pts = f.pts
        area = math.sqrt(v_dot(v_cross(v_sub(pts[1], pts[0]), v_sub(pts[2], pts[0])), v_cross(v_sub(pts[1], pts[0]), v_sub(pts[2], pts[0]))))
        if len(pts) == 3:
            area /= 2
        c = face_avg_colour(f)
        (tops if f.n[1] > 0.6 else sides).append((area, c))

    def avg(lst):
        if not lst:
            return (128, 128, 128)
        w = sum(a for a, _ in lst) or 1
        return tuple(sum(a * c[i] for a, c in lst) / w for i in range(3))
    lo = B()
    if boxes is None:
        boxes = [(min(xs), 0.0, min(zs), max(xs), max(ys), max(zs))]
    for bx in boxes:
        x0, y0, z0, x1, y1, z1 = bx[:6]
        col = bx[6] if len(bx) > 6 else None
        skip = bx[7] if len(bx) > 7 else 'b'
        if skip == 'panel':            # a two-sided panel facing +z at z1
            m = C(col or avg(sides), double=True)
            lo.panel(x0, y0, x1, y1, z1, m)
            continue
        if col is not None:
            lo.box(x0, y0, z0, x1, y1, z1, C(col), skip=skip)
        else:
            lo.box(x0, y0, z0, x1, y1, z1, C(avg(sides)), mats={'t': C(avg(tops))}, skip=skip)
    return lo.faces


OBJS = []           # (key, w, d, h, function)
FINISHERS = []      # extra declaration writers: fn(lines)


def obj(key, w, d, h=1):
    def deco(fn):
        OBJS.append((key, w, d, h, fn))
        return fn
    return deco

# ============================================================================= materials

WAL = T('grain', 'walnut')
OAK = T('grain', 'oak')
CHERRY = T('grain', 'cherry')
TEAK = T('grain', 'teak')
EBONY = T('grain', 'ebony', k=1.1)
WHITEWOOD = T('grain', 'white')
LINEN = C('f4f2ec')
PILLOW = C('fcfcf8')
QUILT = T('quilt', 'cream')
QUILT_W = T('quilt', 'white')
CHROME = T('chrome', 'steel', fit=True)
STEEL = T('chrome', 'steel', fit=True, k=0.9)
BRASS = T('chrome', 'brass', fit=True)
GOLD = C('e0b040')
PORC = C('f4f6f8')               # porcelain
DARK = C('2a2a30')
BLACK = C('121216')
SHADE = T('shade', 'shade', glow=True, fit=True)
GLASS = T('w_glass', 'glass', semi=0, double=True, fit=True)
WATER = T('f4_pool_water', 'pool_water', fit=True, glow=True, sub=(0, 0, 0.5, 0.5))
MIRROR = T('glass', 'mirror', fit=True, glow=True)
LEAF = T('leaves', 'leaf', fit=True)


def fab(p, **kw):
    return T('fabric', p, **kw)


def leather(p, **kw):
    return T('leather', p, **kw)


def lamp_on_top(b, x, z, y, h=0.42, r=0.15, base=BRASS, shade=SHADE):
    """A table lamp standing at (x, y, z): base, stem, glowing shade (about 30 triangles)."""
    b.cyl(x, z, r * 0.45, y, y + 0.05, 4, base, rot=0.0)
    b.rod((x, y + 0.05, z), (x, y + h * 0.5, z), 0.07, base)
    b.cyl(x, z, r, y + h * 0.48, y + h, 5, shade, r1=r * 0.68, top=C('fff4d8', glow=True))


# ============================================================================= guest rooms


def bed(b, hw, hz, pillows, head_mat, runner, duvet=QUILT_W, base=WAL):
    """A hotel bed: x in -hw..hw, z in -hz..hz, headboard at -z."""
    b.box(-hw + 0.04, 0.0, -hz + 0.12, hw - 0.04, 0.28, hz - 0.03, base, skip='bt')
    top = 0.52
    segs = [(-hz + 0.12, -hz + 0.58, LINEN, LINEN, top),
            (-hz + 0.58, -hz + 0.70, LINEN, LINEN, top + 0.03),
            (-hz + 0.70, hz - 0.62, duvet, duvet, top),
            (hz - 0.62, hz - 0.34, runner, runner, top + 0.01),
            (hz - 0.34, hz, duvet, duvet, top)]
    for i, (z0, z1, mt, ms, y1) in enumerate(segs):
        skip = 'b'
        if i > 0:
            skip += 'k'
        if i < len(segs) - 1:
            skip += 'f'
        b.box(-hw, 0.24, z0, hw, y1, z1, ms, skip=skip, mats={'t': mt})
        if i > 0 and segs[i - 1][4] != y1:        # step between segments
            yA, yB = sorted((segs[i - 1][4], y1))
            b.box(-hw, yA, z0, hw, yB, z0, ms, skip='btlrf' if segs[i - 1][4] > y1 else 'btlrk')
    # pillows (a little puffy: a raised ridge along x)
    pw = (2 * hw - 0.2) / pillows
    for k in range(pillows):
        x0 = -hw + 0.1 + k * pw + 0.03
        x1 = x0 + pw - 0.06
        z0, z1 = -hz + 0.16, -hz + 0.52
        b.box(x0, top, z0, x1, top + 0.10, z1, PILLOW, skip='bt')
        b.quad((x1, top + 0.10, z1), (x0, top + 0.10, z1), (x1, top + 0.15, (z0 + z1) / 2), (x0, top + 0.15, (z0 + z1) / 2), PILLOW, shade=1.0)
        b.quad((x1, top + 0.15, (z0 + z1) / 2), (x0, top + 0.15, (z0 + z1) / 2), (x1, top + 0.10, z0), (x0, top + 0.10, z0), PILLOW)
    # headboard
    b.box(-hw - 0.03, 0.0, -hz, hw + 0.03, 1.12, -hz + 0.10, base, mats={'f': head_mat})
    b.box(-hw - 0.05, 1.12, -hz - 0.01, hw + 0.05, 1.18, -hz + 0.12, base)


@obj('bed_single', 1, 2)
def _():
    b = B()
    bed(b, 0.46, 0.97, 1, leather('teal'), fab('burgundy'))
    return b.faces


@obj('bed_double', 2, 2)
def _():
    b = B()
    bed(b, 0.92, 0.97, 2, leather('teal'), fab('burgundy'))
    # a small accent cushion
    b.box(-0.2, 0.52, -0.46, 0.2, 0.70, -0.38, fab('mustard'), skip='b')
    return b.faces


@obj('nightstand', 1, 1)
def _():
    b = B()
    b.box(-0.26, 0.0, -0.30, 0.26, 0.56, 0.14, WAL, mats={'f': T('cabinet', 'walnut', fit=True, sub=(0, 0, 1, 0.5))})
    lamp_on_top(b, 0.0, -0.10, 0.56)
    return b.faces


@obj('wardrobe', 1, 1)
def _():
    b = B()
    b.box(-0.45, 0.0, -0.32, 0.45, 0.10, 0.22, C('2a1a10'), skip='bt')
    b.box(-0.46, 0.10, -0.34, 0.46, 1.96, 0.24, WAL, mats={'f': T('door', 'walnut', fit=True)}, skip='bt')
    b.box(-0.49, 1.96, -0.36, 0.49, 2.04, 0.27, WAL)
    return b.faces


def crt(b, x, z, y, w=0.56, h=0.46, d=0.46, col=C('3a3a42'), screen=None):
    screen = screen or T('screen', 'screen_on', fit=True, glow=True)
    b.box(x - w / 2, y, z - d / 2, x + w / 2, y + h, z + d / 2 - 0.02, col, skip='bf')
    # back taper
    b.box(x - w * 0.35, y + 0.06, z - d / 2 - 0.18, x + w * 0.35, y + h - 0.08, z - d / 2, col, skip='bf')
    # bezel and screen
    b.box(x - w / 2, y, z + d / 2 - 0.02, x + w / 2, y + h, z + d / 2, col, skip='bk')
    b.panel(x - w / 2 + 0.06, y + 0.07, x + w / 2 - 0.06, y + h - 0.06, z + d / 2 + 0.005, screen)


@obj('tv', 1, 1)
def _():
    b = B()
    b.box(-0.45, 0.0, -0.30, 0.45, 0.45, 0.20, WAL, mats={'f': T('cabinet', 'walnut', fit=True)})
    crt(b, 0.0, -0.08, 0.45)
    return b.faces


@obj('desk', 1, 1)
def _():
    b = B()
    b.box(-0.46, 0.70, -0.36, 0.46, 0.76, 0.24, OAK, skip='b')
    b.box(-0.44, 0.0, -0.33, -0.40, 0.70, 0.20, OAK, skip='bt')
    b.box(0.08, 0.0, -0.33, 0.44, 0.70, 0.20, OAK, mats={'f': T('cabinet', 'oak', fit=True, sub=(0.5, 0, 1, 1))}, skip='bt')
    b.panel(-0.40, 0.35, 0.08, 0.70, -0.30, OAK)
    b.flat(-0.30, -0.12, 0.10, 0.16, 0.762, C('2a5a3a'))
    lamp_on_top(b, 0.30, -0.20, 0.76, h=0.36, r=0.10, shade=T('shade', 'shade_red', glow=True, fit=True))
    return b.faces


def chair(b, x=0.0, z=0.0, yaw=0.0, seat=None, frame=WAL, back_h=0.95, w=0.44, d=0.44, arms=False):
    """A side chair facing +z, seat at 0.45."""
    st = b.mark()
    seat = seat or fab('teal')
    hw, hd = w / 2, d / 2
    for sx, sz in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        lx, lz = sx * (hw - 0.04), sz * (hd - 0.04)
        b.box(lx - 0.025, 0.0, lz - 0.025, lx + 0.025, 0.38, lz + 0.025, frame, skip='bt')
    b.box(-hw, 0.38, -hd, hw, 0.48, hd, seat, skip='b')
    b.box(-hw, 0.48, -hd, hw, back_h, -hd + 0.07, frame, mats={'f': seat})
    if arms:
        for sx in (-1, 1):
            b.box(sx * hw - 0.04, 0.48, -hd, sx * hw + 0.04, 0.66, hd, frame)
    b.rot_y(st, yaw)
    b.move(st, x, 0, z)


@obj('chair', 1, 1)
def _():
    b = B()
    chair_lite(b, 0.0, 0.0, 0.0, fab('teal'), WAL, w=0.44, back_h=0.96)
    b.box(-0.22, 0.40, -0.22, 0.22, 0.48, 0.22, fab('teal'), skip='b')
    return b.faces


@obj('minibar', 1, 1)
def _():
    b = B()
    b.box(-0.28, 0.0, -0.30, 0.28, 0.62, 0.22, C('3a3036'), mats={'t': WAL}, skip='b')
    b.panel(-0.24, 0.06, 0.24, 0.56, 0.225, T('bottles', 'bottles', fit=True, glow=True, k=0.85))
    b.box(0.20, 0.10, 0.225, 0.23, 0.52, 0.25, CHROME, skip='bkt')
    b.cyl(-0.12, -0.05, 0.08, 0.62, 0.76, 5, CHROME, top=C('d0e8f0'))
    b.cyl(0.14, -0.06, 0.035, 0.62, 0.72, 4, C('c8e0f0', glow=True))
    return b.faces


@obj('floor_lamp', 1, 1)
def _():
    b = B()
    b.cyl(0, 0, 0.20, 0.0, 0.05, 6, BRASS)
    b.rod((0, 0.05, 0), (0, 1.30, 0), 0.09, BRASS)
    b.cyl(0, 0, 0.26, 1.22, 1.62, 6, SHADE, r1=0.18, top=C('fff4d8', glow=True))
    return b.faces


def sofa(b, w, seats, cover, frame=None, d=0.86, back_h=0.86, arm_h=0.62, tufted=False):
    """A sofa along x (width w), seat facing +z."""
    frame = frame or cover
    hw, hd = w / 2, d / 2
    b.box(-hw + 0.04, 0.0, -hd + 0.04, hw - 0.04, 0.10, hd - 0.04, C('1e1410'), skip='bt')
    b.box(-hw + 0.14, 0.10, -hd + 0.2, hw - 0.14, 0.30, hd, cover, skip='bt')
    sw = (w - 0.28) / seats
    for k in range(seats):
        x0 = -hw + 0.14 + k * sw + 0.01
        b.box(x0, 0.30, -hd + 0.22, x0 + sw - 0.02, 0.44, hd, cover, skip='b')
    b.box(-hw, 0.10, -hd, hw, back_h, -hd + 0.2, frame, mats={'f': cover})
    for sx in (-1, 1):
        x0 = -hw if sx < 0 else hw - 0.14
        b.box(x0, 0.10, -hd, x0 + 0.14, arm_h, hd, frame)


@obj('sofa', 2, 1)
def _():
    b = B()
    sofa(b, 1.86, 3, fab('teal'))
    b.box(-0.70, 0.44, -0.24, -0.38, 0.72, -0.14, fab('coral'), skip='b')
    b.box(0.38, 0.44, -0.24, 0.70, 0.72, -0.14, fab('mustard'), skip='b')
    return b.faces


@obj('toilet', 1, 1)
def _():
    b = B()
    b.box(-0.20, 0.42, -0.43, 0.20, 0.82, -0.24, PORC, skip='b')                     # tank
    b.box(-0.03, 0.82, -0.36, 0.03, 0.84, -0.30, CHROME, skip='b')
    b.cyl(0.0, -0.06, 0.13, 0.0, 0.32, 6, PORC, r1=0.17, rz=1.25, cap=False)
    b.cyl(0.0, -0.06, 0.20, 0.32, 0.44, 6, PORC, top=C('b8d8e8'), rz=1.25)
    return b.faces


@obj('shower', 1, 1)
def _():
    b = B()
    b.box(-0.48, 0.0, -0.48, 0.48, 0.10, 0.48, PORC)
    b.flat(-0.42, -0.42, 0.42, 0.42, 0.101, C('c8d4dc'))
    b.box(-0.48, 0.10, -0.48, 0.48, 2.2, -0.42, T('smalltile', 'aqua', dens=24), skip='b')
    b.box(-0.03, 1.0, -0.42, 0.03, 1.95, -0.38, CHROME, skip='b')
    b.box(-0.10, 1.90, -0.42, 0.10, 1.96, -0.22, CHROME)
    b.panel(-0.48, 0.10, 0.48, 2.0, 0.47, GLASS)
    b.panel_x(-0.42, 0.10, 0.48, 2.0, 0.47, GLASS)
    b.box(-0.49, 2.0, 0.45, 0.49, 2.04, 0.49, CHROME)
    b.box(0.45, 2.0, -0.42, 0.49, 2.04, 0.49, CHROME)
    b.box(0.45, 0.10, 0.45, 0.49, 2.0, 0.49, CHROME, skip='bt')
    return b.faces


@obj('bathtub', 1, 2)
def _():
    b = B()
    hw, hz, H = 0.44, 0.95, 0.56
    b.box(-hw, 0.0, -hz, hw, H, hz, PORC, skip='bt')
    t = 0.07
    b.box(-hw, H - 0.0, -hz, hw, H + 0.02, -hz + t, PORC, skip='b')
    b.box(-hw, H - 0.0, hz - t, hw, H + 0.02, hz, PORC, skip='b')
    b.box(-hw, H - 0.0, -hz + t, -hw + t, H + 0.02, hz - t, PORC, skip='bfk')
    b.box(hw - t, H - 0.0, -hz + t, hw, H + 0.02, hz - t, PORC, skip='bfk')
    b.flat(-hw + t, -hz + t, hw - t, hz - t, H - 0.12, WATER)
    # taps at the head end, a bath mat in front
    b.box(-0.05, H + 0.02, -hz + 0.01, 0.05, H + 0.16, -hz + 0.05, CHROME)
    b.box(-0.02, H + 0.10, -hz + 0.05, 0.02, H + 0.14, -hz + 0.16, CHROME)
    return b.faces


@obj('sink', 1, 1)
def _():
    b = B()
    b.box(-0.38, 0.0, -0.38, 0.38, 0.82, 0.12, WAL, mats={'f': T('cabinet', 'walnut', fit=True)}, skip='bt')
    b.box(-0.40, 0.82, -0.40, 0.40, 0.86, 0.15, T('marble', 'marble_white', fit=True), skip='b')
    b.cyl(0.0, -0.10, 0.18, 0.86, 0.90, 6, PORC, top=C('c0d0dc'), rz=0.8)
    b.rod((0.0, 0.86, -0.33), (0.0, 1.02, -0.33), 0.04, CHROME)
    b.rod((0.0, 1.0, -0.34), (0.0, 1.0, -0.22), 0.035, CHROME)
    b.box(-0.34, 1.10, -0.42, 0.34, 1.80, -0.40, MIRROR, skip='bk', mats={'t': CHROME, 'l': CHROME, 'r': CHROME})
    return b.faces


@obj('jacuzzi', 2, 2)
def _():
    b = B()
    R = 0.95
    H = 0.55
    oct8 = b.ring(0, 0, R, 8, rot=math.pi / 8)
    b.prism(oct8, 0.0, H, T('smalltile', 'aqua', dens=24), cap=False)
    inner = b.ring(0, 0, R - 0.14, 8, rot=math.pi / 8)
    for i in range(8):
        j = (i + 1) % 8
        a, c = oct8[i], oct8[j]
        p, q = inner[i], inner[j]
        b.quad((a[0], H + 0.03, a[1]), (c[0], H + 0.03, c[1]), (p[0], H + 0.03, p[1]), (q[0], H + 0.03, q[1]),
               T('marble', 'marble_white', fit=True), (0, 1, 0))
        n = v_norm((a[0] + c[0], 0, a[1] + c[1]))
        b.quad((a[0], H, a[1]), (c[0], H, c[1]), (a[0], H + 0.03, a[1]), (c[0], H + 0.03, c[1]), PORC, n)
    b.poly_top(inner, H - 0.08, WATER)
    # steps
    b.box(-0.45, 0.0, R * 0.92, 0.45, 0.25, R + 0.04, T('marble', 'marble_white', fit=True))
    return b.faces

# ============================================================================= lobby

MARBLE = T('marble', 'marble_white', fit=True)
MARBLE_BK = T('marble', 'marble_black', fit=True)


def imac(b, x, z, y, yaw=0.0, col='30b8c8'):
    """A translucent Y2K all-in-one computer, screen toward +z (before yaw)."""
    st = b.mark()
    body = C(col)
    b.box(-0.17, y + 0.02, -0.16, 0.17, y + 0.34, 0.12, body, skip='b', mats={'f': C('e8f0f0')})
    b.box(-0.11, y + 0.06, -0.27, 0.11, y + 0.30, -0.16, body, skip='bf')
    b.panel(-0.13, y + 0.08, 0.13, y + 0.30, 0.125, T('screen', 'screen_on', fit=True, glow=True))
    b.flat(-0.14, 0.15, 0.14, 0.25, y + 0.01, C('e8f0f0'))
    b.rot_y(st, yaw)
    b.move(st, x, 0, z)


def bell(b, x, z, y):
    b.cyl(x, z, 0.06, y, y + 0.015, 4, BRASS, cap=False)
    b.cone(x, z, 0.055, y + 0.015, y + 0.08, 4, BRASS)


@obj('reception_desk', 3, 1)
def _():
    b = B()
    front = CHERRY
    # guest side (+z): tall counter with a marble ledge, a teal logo panel in the middle
    b.box(-1.46, 0.0, 0.10, 1.46, 0.08, 0.42, C('1a1210'), skip='btk')
    b.box(-1.44, 0.08, 0.06, 1.44, 1.04, 0.40, front, skip='btk')
    b.box(-1.44, 0.62, 0.40, 1.44, 0.68, 0.415, BRASS, skip='bkt')
    b.panel(-0.40, 0.16, 0.40, 0.58, 0.405, T('neon', 'neon', fit=True, glow=True))
    b.box(-1.50, 1.04, 0.02, 1.50, 1.10, 0.48, MARBLE)
    # staff side (-z): work surface
    b.box(-1.44, 0.0, -0.44, 1.44, 0.74, 0.06, T('cabinet', 'cherry', fit=True), skip='bf',
          mats={'t': C('e8e4dc'), 'l': CHERRY, 'r': CHERRY})
    b.panel(-1.44, 0.74, 1.44, 1.04, 0.06, CHERRY, back=True)
    imac(b, -0.7, -0.20, 0.74, yaw=math.pi)
    imac(b, 0.7, -0.20, 0.74, yaw=math.pi, col='f07a8a')
    bell(b, 0.35, 0.26, 1.10)
    # guest book and a small orchid
    b.box(-0.38, 1.10, 0.14, -0.06, 1.13, 0.38, C('8a1a24'), skip='bk', mats={'t': C('f8f4e8')})
    b.cyl(1.25, 0.25, 0.07, 1.10, 1.22, 4, C('f4f4f0'))
    b.rod((1.25, 1.22, 0.25), (1.25, 1.42, 0.25), 0.02, C('2a6a2a'))
    b.box(1.18, 1.38, 0.18, 1.32, 1.46, 0.32, C('e070c0'), skip='b')
    return b.faces


@obj('key_rack', 1, 1)
def _():
    b = B()
    b.box(-0.44, 0.0, -0.46, 0.44, 0.86, -0.12, CHERRY, mats={'f': T('cabinet', 'cherry', fit=True)})
    b.box(-0.46, 0.86, -0.48, 0.46, 0.90, -0.10, MARBLE)
    b.box(-0.42, 1.05, -0.48, 0.42, 2.05, -0.34, CHERRY, mats={'f': T('cubbies', 'cubbies', fit=True)})
    b.box(-0.45, 2.05, -0.49, 0.45, 2.12, -0.32, CHERRY)
    b.box(-0.30, 0.90, -0.30, -0.06, 0.92, -0.16, C('f8f4e8'))               # a note pad
    return b.faces


@obj('concierge_desk', 2, 1)
def _():
    b = B()
    poly = [(-0.85, -0.30), (0.85, -0.30), (0.85, 0.12), (0.45, 0.30), (-0.45, 0.30), (-0.85, 0.12)]
    b.extrude([(x * 0.98, z * 0.95) for x, z in poly], 0.0, 0.98, CHERRY, cap=False)
    b.extrude([(x * 1.04, z * 1.1) for x, z in poly], 0.98, 1.04, MARBLE_BK)
    b.box(-0.3, 0.50, 0.29, 0.3, 0.56, 0.31, BRASS, skip='bkt')
    lamp_on_top(b, -0.55, -0.08, 1.04, h=0.40, r=0.11)
    b.box(0.35, 1.04, -0.14, 0.60, 1.10, 0.04, BLACK, skip='b')                    # phone
    b.flat(-0.15, 0.0, 0.15, 0.20, 1.045, T('picture', 'picture', fit=True))
    return b.faces


@obj('waiting_sofa', 2, 1)
def _():
    b = B()
    sofa(b, 1.86, 2, leather('burgundy', fit=False), frame=leather('burgundy'), back_h=0.80, arm_h=0.72)
    return b.faces


@obj('coffee_table', 1, 1)
def _():
    b = B()
    for sx in (-1, 1):
        b.box(sx * 0.34 - 0.03, 0.0, -0.34, sx * 0.34 + 0.03, 0.34, 0.34, WAL, skip='bt')
    b.box(-0.40, 0.34, -0.40, 0.40, 0.40, 0.40, WAL)
    b.flat(-0.28, -0.05, 0.02, 0.22, 0.402, C('e04a3a'))                          # magazines
    b.flat(-0.22, -0.10, 0.06, 0.14, 0.404, C('40a0e0'))
    b.cyl(0.18, -0.15, 0.06, 0.40, 0.58, 4, C('a8e0e8'), top=C('2a6a2a'))
    b.box(0.13, 0.58, -0.20, 0.23, 0.66, -0.10, C('f0e040'), skip='b')
    return b.faces


def frond(b, x, z, ang, y, L, droop, w=0.16, mat=None):
    """A palm frond from (x, y, z) outward at angle ang: two double-sided strips."""
    mat = mat or T('leaves', 'leaf', fit=True, double=True)
    dx, dz = math.cos(ang), math.sin(ang)
    px, pz = -dz * w, dx * w
    p0 = (x, y, z)
    p1 = (x + dx * L * 0.5, y + L * 0.32, z + dz * L * 0.5)
    p2 = (x + dx * L, y + L * 0.32 - droop, z + dz * L)
    b.quad((p0[0] - px * 0.3, p0[1], p0[2] - pz * 0.3), (p0[0] + px * 0.3, p0[1], p0[2] + pz * 0.3),
           (p1[0] - px, p1[1], p1[2] - pz), (p1[0] + px, p1[1], p1[2] + pz), mat, (0, 1, 0))
    b.quad((p1[0] - px, p1[1], p1[2] - pz), (p1[0] + px, p1[1], p1[2] + pz),
           (p2[0] - px * 0.2, p2[1], p2[2] - pz * 0.2), (p2[0] + px * 0.2, p2[1], p2[2] + pz * 0.2), mat, (0, 1, 0))


@obj('plant', 1, 1)
def _():
    b = B()
    b.cyl(0, 0, 0.18, 0.0, 0.42, 6, T('chrome', 'terracotta', fit=True), r1=0.24, cap=False)
    b.cyl(0, 0, 0.25, 0.42, 0.48, 6, T('chrome', 'terracotta', fit=True), top=C('3a2a1a'))
    b.box(-0.03, 0.48, -0.03, 0.03, 0.80, 0.03, C('6a4a2a'), skip='b')
    for i in range(7):
        a = i * 2 * math.pi / 7 + 0.3
        frond(b, 0, 0, a, 0.78 + (i % 2) * 0.06, 0.62 + 0.08 * (i % 3), 0.32)
    return b.faces


@obj('luggage_cart', 1, 1)
def _():
    b = B()
    for sz in (-1, 1):
        b.box(-0.40, 0.0, sz * 0.20 - 0.04, 0.40, 0.10, sz * 0.20 + 0.04, BLACK, skip='bt')
    b.box(-0.44, 0.10, -0.26, 0.44, 0.16, 0.26, BRASS, mats={'t': fab('red')}, skip='b')
    for sx in (-1, 1):
        b.rod((sx * 0.42, 0.16, 0.0), (sx * 0.42, 1.58, 0.0), 0.05, BRASS)
    b.rod((-0.46, 1.58, 0.0), (0.46, 1.58, 0.0), 0.06, BRASS)
    b.box(-0.34, 0.16, -0.18, 0.30, 0.56, 0.18, C('3a4a8a'), skip='b')            # suitcases
    b.box(-0.28, 0.56, -0.15, 0.22, 0.84, 0.12, C('c84a30'), skip='b')
    b.box(-0.18, 0.84, -0.10, 0.12, 1.04, 0.08, C('d8b060'), skip='b')
    return b.faces


# ============================================================================= restaurant and bar


def chair_lite(b, x, z, yaw, seat, frame, w=0.38, back_h=0.92, seat_h=0.46):
    """A cheap chair (about 16 triangles) facing +z before yaw."""
    st = b.mark()
    hw = w / 2
    leg = frame.but(double=True)
    b.quad((-hw + 0.03, 0, -hw + 0.03), (hw - 0.03, 0, hw - 0.03), (-hw + 0.03, seat_h - 0.06, -hw + 0.03),
           (hw - 0.03, seat_h - 0.06, hw - 0.03), leg, v_norm((1, 0, -1)))
    b.quad((hw - 0.03, 0, -hw + 0.03), (-hw + 0.03, 0, hw - 0.03), (hw - 0.03, seat_h - 0.06, -hw + 0.03),
           (-hw + 0.03, seat_h - 0.06, hw - 0.03), leg, v_norm((1, 0, 1)))
    b.box(-hw, seat_h - 0.06, -hw, hw, seat_h, hw, seat, skip='b')
    b.quad((hw, seat_h, -hw + 0.02), (-hw, seat_h, -hw + 0.02), (hw, back_h, -hw), (-hw, back_h, -hw), frame.but(double=True), (0, 0, 1))
    b.rot_y(st, yaw)
    b.move(st, x, 0, z)


@obj('table_2', 1, 1)
def _():
    b = B()
    b.cyl(0, 0, 0.14, 0.0, 0.03, 4, BLACK, rot=math.pi / 4, cap=False)
    b.rod((0, 0.03, 0), (0, 0.68, 0), 0.06, BLACK)
    cloth = T('tablecloth', 'tablecloth', fit=True)
    b.box(-0.30, 0.66, -0.30, 0.30, 0.74, 0.30, C('f2f2ee'), mats={'t': cloth}, skip='b')
    b.cyl(0, 0, 0.025, 0.74, 0.84, 4, C('f0e8d0'))
    chair_lite(b, -0.40, 0.0, math.pi / 2, fab('red'), WAL, w=0.30, back_h=0.86)
    chair_lite(b, 0.40, 0.0, -math.pi / 2, fab('red'), WAL, w=0.30, back_h=0.86)
    return b.faces


@obj('table_4', 2, 2)
def _():
    b = B()
    cloth = T('tablecloth', 'tablecloth', fit=True)
    b.box(-0.06, 0.0, -0.06, 0.06, 0.45, 0.06, BLACK, skip='bt')
    b.box(-0.50, 0.45, -0.50, 0.50, 0.76, 0.50, C('f2f2ee'), mats={'t': cloth})
    for k in range(4):
        a = k * math.pi / 2
        chair_lite(b, 0.70 * math.sin(a), 0.70 * math.cos(a), a + math.pi, fab('burgundy'), WAL)
    return b.faces


@obj('buffet', 3, 1)
def _():
    b = B()
    b.box(-1.46, 0.0, -0.40, 1.46, 0.84, 0.30, CHERRY, mats={'f': T('cabinet', 'cherry', fit=True)}, skip='b')
    b.box(-1.48, 0.84, -0.42, 1.48, 0.88, 0.34, STEEL)
    b.flat(-1.40, -0.30, 1.40, 0.20, 0.885, T('food', 'food', fit=True))
    for x in (-1.0, 0.0, 1.0):                                                     # chafing dish lids
        b.cyl(x, -0.30, 0.20, 0.88, 1.04, 6, CHROME, r1=0.10, rz=0.5)
    for x in (-1.40, 1.40):
        b.bar((x, 0.88, 0.26), (x, 1.32, 0.26), 0.03, CHROME)
    b.quad((1.42, 1.08, 0.36), (-1.42, 1.08, 0.36), (1.42, 1.32, 0.16), (-1.42, 1.32, 0.16), GLASS, v_norm((0, 1, 1)))
    b.box(-1.0, 0.88, 0.10, -0.6, 0.98, 0.26, C('f4f4f0'))                       # plates
    return b.faces


@obj('bar_counter', 1, 1)
def _():
    b = B()
    b.box(-0.5, 0.0, 0.04, 0.5, 0.10, 0.30, C('1a1210'), skip='btlr')
    b.box(-0.5, 0.10, -0.14, 0.5, 1.04, 0.32, CHERRY, mats={'f': leather('burgundy')}, skip='bt')
    b.box(-0.5, 1.04, -0.22, 0.5, 1.12, 0.44, MARBLE_BK)
    b.box(-0.5, 0.88, -0.48, 0.5, 0.92, -0.14, STEEL)
    b.box(-0.5, 0.0, -0.46, 0.5, 0.88, -0.16, T('cabinet', 'steel', fit=True), skip='bt', mats={'f': STEEL})
    b.bar((-0.5, 0.18, 0.42), (0.5, 0.18, 0.42), 0.04, BRASS, cap=False)
    b.cyl(0.25, 0.10, 0.04, 1.12, 1.26, 5, C('c8e8f0', glow=True))                # a glass
    return b.faces


@obj('bar_stool', 1, 1)
def _():
    b = B()
    b.cyl(0, 0, 0.20, 0.0, 0.03, 6, CHROME)
    b.rod((0, 0.03, 0), (0, 0.70, 0), 0.07, CHROME)
    b.cyl(0, 0, 0.20, 0.70, 0.80, 6, leather('red'), top=leather('red'))
    return b.faces


@obj('bar_shelf', 2, 1)
def _():
    b = B()
    b.box(-0.95, 0.0, -0.46, 0.95, 0.90, -0.06, CHERRY, mats={'f': T('cabinet', 'cherry', fit=True)})
    b.box(-0.97, 0.90, -0.48, 0.97, 0.94, -0.04, MARBLE_BK)
    b.box(-0.95, 0.94, -0.48, 0.95, 2.30, -0.40, CHERRY, mats={'f': MIRROR.but(k=0.8)}, skip='b')
    for y in (0.94, 1.48):
        b.panel(-0.90, y + 0.02, 0.90, y + 0.50, -0.395, T('bottles', 'bottles', fit=True, glow=True, k=0.9))
        b.box(-0.92, y + 0.52, -0.40, 0.92, y + 0.55, -0.22, CHERRY)
    for x in (-0.97, 0.89):
        b.box(x, 0.94, -0.48, x + 0.08, 2.30, -0.22, CHERRY, skip='b')
    b.box(-0.99, 2.30, -0.50, 0.99, 2.38, -0.20, CHERRY)
    b.box(-0.90, 2.20, -0.21, 0.90, 2.24, -0.19, C('ff4aa0', glow=True), skip='bk')   # neon strip
    return b.faces


@obj('lounge_chair', 1, 1)
def _():
    b = B()
    sofa(b, 0.86, 1, leather('mustard'), d=0.80, back_h=0.86, arm_h=0.64)
    return b.faces


@obj('piano', 2, 2)
def _():
    b = B()
    body = [(0.74, 0.42), (0.74, -0.78), (0.58, -0.94), (0.30, -0.95), (0.06, -0.80), (-0.22, -0.45),
            (-0.52, -0.12), (-0.72, 0.12), (-0.74, 0.42)]
    for (x, z) in ((0.62, 0.30), (-0.62, 0.30), (0.40, -0.75)):
        b.box(x - 0.05, 0.0, z - 0.05, x + 0.05, 0.62, z + 0.05, EBONY, skip='bt')
    b.extrude(body, 0.62, 0.98, EBONY, top=C('8a6a3a'))
    # the raised lid, hinged on the straight (+x) side
    st = b.mark()
    b.tag = 'lid'
    b.fill(body, 0.99, EBONY.but(double=True))
    b.tag = ''
    b.rot(st, 'z', -0.55, origin=(0.74, 0.99, 0.0))
    b.bar((-0.25, 0.98, -0.25), (-0.25, 1.62, -0.25), 0.025, EBONY)
    # keyboard
    b.box(-0.72, 0.62, 0.42, 0.72, 0.80, 0.70, EBONY, mats={'t': T('keys', 'grey', fit=True, k=1.05)})
    b.box(-0.74, 0.62, 0.42, -0.66, 0.86, 0.70, EBONY)
    b.box(0.66, 0.62, 0.42, 0.74, 0.86, 0.70, EBONY)
    # bench
    b.box(-0.40, 0.0, 0.76, 0.40, 0.48, 0.98, EBONY, mats={'t': leather('black')})
    return b.faces


@obj('jukebox', 1, 1)
def _():
    b = B()
    hw, d0, d1 = 0.38, -0.28, 0.22
    H = 1.0
    fr = (-hw, hw, 0.0, H + hw)
    tex = T('jukebox', 'jukebox', fit=True, glow=True, frame=fr)
    wood = T('grain', 'cherry')
    b.box(-hw, 0.0, d0, hw, H, d1, wood, skip='bt', mats={'f': tex})
    n = 6
    pts = [(hw * math.cos(math.pi * i / n), H + hw * math.sin(math.pi * i / n)) for i in range(n + 1)]
    for i in range(n):
        (xa, ya), (xb, yb) = pts[i], pts[i + 1]
        nn = v_norm(((xa + xb) / 2, (ya + yb) / 2 - H, 0))
        b.quad((xa, ya, d1), (xb, yb, d1), (xa, ya, d0), (xb, yb, d0), C('e04a2a', glow=True) if i in (0, n - 1) else wood, nn)
        b.tri((0, H, d1), (xa, ya, d1), (xb, yb, d1), tex, (0, 0, 1))
        b.tri((0, H, d0), (xa, ya, d0), (xb, yb, d0), wood, (0, 0, -1))
    return b.faces


# ============================================================================= kitchen

ENAMEL = C('eef0f2')


@obj('stove', 1, 1)
def _():
    b = B()
    b.box(-0.42, 0.0, -0.36, 0.42, 0.88, 0.32, STEEL, skip='b',
          mats={'t': T('stovetop', 'stovetop', fit=True), 'f': T('oven', 'steel', fit=True)})
    b.box(-0.42, 0.88, -0.40, 0.42, 1.10, -0.32, STEEL, skip='b')
    b.cyl(-0.21, 0.13, 0.12, 0.88, 1.04, 6, STEEL, top=C('d8d0c0'))
    b.rod((-0.08, 1.00, 0.13), (0.10, 1.00, 0.13), 0.02, BLACK)
    b.cyl(0.21, -0.12, 0.11, 0.88, 0.92, 6, BLACK, top=C('3a3a40'))
    return b.faces


@obj('prep_counter', 2, 1)
def _():
    b = B()
    b.box(-0.95, 0.0, -0.38, 0.95, 0.88, 0.30, STEEL, skip='bt', mats={'f': T('cabinet', 'steel', fit=True)})
    b.box(-0.97, 0.88, -0.40, 0.97, 0.92, 0.32, STEEL)
    b.box(-0.55, 0.92, -0.18, 0.05, 0.95, 0.18, OAK)                              # cutting board
    b.box(-0.45, 0.95, -0.05, -0.33, 1.01, 0.07, C('e03a2a'))                     # tomato
    b.box(-0.25, 0.95, -0.10, -0.08, 1.02, 0.06, C('5ab040'))                     # lettuce
    b.box(-0.05, 0.95, 0.08, 0.02, 0.96, 0.15, C('d0d8e0'))                      # knife
    b.cyl(0.55, -0.12, 0.13, 0.92, 1.08, 6, STEEL, top=C('e8d080'))               # mixing bowl
    return b.faces


@obj('fridge', 1, 1)
def _():
    b = B()
    b.box(-0.42, 0.0, -0.36, 0.42, 2.0, 0.30, STEEL, mats={'f': T('fridge', 'steel', fit=True)})
    b.box(-0.40, 2.0, -0.34, 0.40, 2.04, 0.26, C('3a3a40'))
    return b.faces


@obj('dishwasher', 1, 1)
def _():
    b = B()
    b.box(-0.42, 0.0, -0.36, 0.42, 0.86, 0.30, STEEL, mats={'f': T('cabinet', 'steel', fit=True)}, skip='bt')
    b.box(-0.44, 0.86, -0.38, 0.44, 0.90, 0.32, STEEL)
    b.box(-0.36, 0.90, -0.30, 0.36, 1.66, 0.24, STEEL)
    b.bar((-0.30, 1.30, 0.29), (0.30, 1.30, 0.29), 0.035, C('d03030'))
    b.box(-0.34, 0.90, 0.24, 0.34, 1.0, 0.26, C('6a7078'), skip='bk')
    b.box(0.10, 1.50, 0.24, 0.30, 1.60, 0.25, C('40f0a0', glow=True), skip='bk')
    return b.faces


@obj('kitchen_sink', 1, 1)
def _():
    b = B()
    b.box(-0.45, 0.0, -0.36, 0.45, 0.86, 0.30, STEEL, mats={'f': T('cabinet', 'steel', fit=True)}, skip='bt')
    t = 0.07
    y = 0.90
    b.box(-0.46, 0.86, -0.38, 0.46, y, -0.38 + t + 0.06, STEEL, skip='b')
    b.box(-0.46, 0.86, 0.32 - t, 0.46, y, 0.32, STEEL, skip='b')
    b.box(-0.46, 0.86, -0.38 + t + 0.06, -0.46 + t, y, 0.32 - t, STEEL, skip='bfk')
    b.box(0.46 - t, 0.86, -0.38 + t + 0.06, 0.46, y, 0.32 - t, STEEL, skip='bfk')
    b.flat(-0.46 + t, -0.38 + t + 0.06, 0.46 - t, 0.32 - t, 0.70, C('5a6068'))
    for (x0, z0, x1, z1, nrm) in ((-0.39, -0.25, 0.39, -0.25, (0, 0, 1)), (-0.39, 0.25, 0.39, 0.25, (0, 0, -1))):
        b.quad((x0, 0.70, z0), (x1, 0.70, z1), (x0, y, z0), (x1, y, z1), C('8a9098'), nrm)
    for (x, nrm) in ((-0.39, (1, 0, 0)), (0.39, (-1, 0, 0))):
        b.quad((x, 0.70, -0.25), (x, 0.70, 0.25), (x, y, -0.25), (x, y, 0.25), C('8a9098'), nrm)
    b.bar((0.0, y, -0.33), (0.0, 1.30, -0.33), 0.04, CHROME)
    b.bar((0.0, 1.30, -0.33), (0.0, 1.30, -0.12), 0.04, CHROME)
    b.bar((0.0, 1.30, -0.12), (0.0, 1.18, -0.12), 0.03, CHROME, cap=False)
    return b.faces


# ============================================================================= laundry and storage


def washer(b, pal):
    b.box(-0.38, 0.0, -0.36, 0.38, 0.92, 0.32, ENAMEL, mats={'f': T('washer', pal, fit=True)})
    b.box(-0.38, 0.92, -0.36, 0.38, 1.02, -0.26, ENAMEL)
    b.box(-0.30, 0.95, -0.26, -0.10, 0.99, -0.25, C('40c0f0', glow=True), skip='bk')


@obj('washer', 1, 1)
def _():
    b = B()
    washer(b, 'washer')
    return b.faces


@obj('dryer', 1, 1)
def _():
    b = B()
    washer(b, 'dryer')
    b.box(0.20, 0.92, -0.36, 0.30, 1.30, -0.28, STEEL)          # vent duct
    return b.faces


def towel_stack(b, x, z, y, n, w=0.34, d=0.26, pal='white', h=0.06):
    b.box(x - w / 2, y, z - d / 2, x + w / 2, y + n * h, z + d / 2, T('towels', pal, fit=True), skip='b',
          mats={'t': C(tex_avg(CELLS['towels'], PALNAME[pal]))})


@obj('folding_table', 2, 1)
def _():
    b = B()
    for x in (-0.85, 0.85):
        b.quad((x, 0, -0.30), (x, 0, 0.30), (x, 0.84, -0.30), (x, 0.84, 0.30), STEEL.but(double=True), (1, 0, 0))
    b.box(-0.95, 0.84, -0.36, 0.95, 0.90, 0.36, C('e8eaec'))
    towel_stack(b, -0.55, 0.0, 0.90, 4, pal='white')
    towel_stack(b, -0.12, -0.05, 0.90, 3, pal='teal')
    towel_stack(b, 0.28, 0.05, 0.90, 5, pal='white')
    b.box(0.55, 0.90, -0.24, 0.90, 1.12, 0.22, T('grain', 'mustard', k=0.9), skip='b', mats={'t': C('f4f2ec')})   # basket
    b.box(-0.85, 0.2, -0.30, 0.85, 0.24, 0.30, STEEL)
    return b.faces


def wire_shelf(b, n_shelves, w=0.86, d=0.44, h=1.9, z0=-0.46):
    hw = w / 2
    for sx in (-1, 1):
        for zz in (z0 + 0.02, z0 + d - 0.02):
            b.rod((sx * hw, 0.0, zz), (sx * hw, h, zz), 0.045, CHROME)
    ys = [0.12 + i * (h - 0.2) / (n_shelves - 1) for i in range(n_shelves)]
    for y in ys:
        b.box(-hw, y, z0, hw, y + 0.03, z0 + d, T('grille', 'steel', fit=True), skip='bk')
    return ys


@obj('linen_shelf', 1, 1)
def _():
    b = B()
    ys = wire_shelf(b, 4)
    for i, y in enumerate(ys[:-1]):
        for x, pal in ((-0.20, 'white'), (0.20, ('teal', 'mustard', 'white')[i])):
            n = 4 - (i + (x > 0)) % 2
            b.box(x - 0.18, y + 0.03, -0.42, x + 0.18, y + 0.03 + n * 0.06, -0.06, T('towels', pal, fit=True), skip='bk',
                  mats={'t': C(tex_avg(CELLS['towels'], PALNAME[pal]))})
    return b.faces


@obj('storage_shelf', 1, 1)
def _():
    b = B()
    ys = wire_shelf(b, 4)
    CART = T('carton', 'teak', fit=True)
    for i, y in enumerate(ys[:-1]):
        b.box(-0.40, y + 0.03, -0.42, -0.04, y + 0.03 + 0.34 - 0.06 * i, -0.08, CART, skip='bk')
        if i != 1:
            b.box(0.02, y + 0.03, -0.40, 0.38, y + 0.03 + 0.26, -0.10, CART, skip='bk')
        else:
            b.cyl(0.20, -0.25, 0.12, y + 0.03, y + 0.40, 5, C('3a7ac8'))
    return b.faces


# ============================================================================= staff room

PLASTIC = C('f07a50')


@obj('locker', 1, 1)
def _():
    b = B()
    b.box(-0.46, 0.0, -0.34, 0.46, 0.08, 0.16, C('2a2e34'), skip='bt')
    b.box(-0.46, 0.08, -0.36, 0.46, 1.92, 0.18, T('chrome', 'navy', fit=True), skip='bf')
    for x0 in (-0.45, 0.005):
        b.panel(x0, 0.10, x0 + 0.445, 1.90, 0.185, T('locker', 'navy', fit=True))
    b.box(-0.46, 0.0, 0.18, 0.46, 0.08, 0.20, C('2a2e34'), skip='bk')
    b.box(-0.48, 1.92, -0.38, 0.48, 1.96, 0.21, T('chrome', 'navy', fit=True))
    return b.faces


@obj('staff_table', 2, 2)
def _():
    b = B()
    b.box(-0.06, 0.0, -0.06, 0.06, 0.70, 0.06, CHROME, skip='bt')
    b.cyl(0, 0, 0.30, 0.0, 0.03, 4, CHROME, rot=math.pi / 4)
    b.box(-0.50, 0.70, -0.40, 0.50, 0.75, 0.40, C('f0f0e8'))
    b.cyl(0.20, 0.10, 0.05, 0.75, 0.86, 5, C('e04040'), top=C('3a2010'))           # mug
    b.box(-0.35, 0.75, -0.25, -0.02, 0.76, 0.05, C('d8d4c8'))                     # newspaper
    for k in range(4):
        a = k * math.pi / 2
        r = 0.66 if k % 2 == 0 else 0.76
        chair_lite(b, r * math.sin(a), r * math.cos(a), a + math.pi, PLASTIC, CHROME)
    return b.faces


@obj('vending', 1, 1)
def _():
    b = B()
    b.box(-0.44, 0.0, -0.38, 0.44, 1.92, 0.30, T('chrome', 'red', fit=True), skip='bf')
    b.box(-0.44, 0.0, 0.30, 0.44, 1.92, 0.32, C('c02030'), skip='bk')
    b.panel(-0.40, 0.30, 0.40, 1.86, 0.325, T('vending', 'vending', fit=True, glow=True))
    b.box(-0.40, 0.08, 0.32, 0.16, 0.24, 0.36, C('1a1a24'))                         # drop tray
    return b.faces


@obj('cot', 1, 2)
def _():
    b = B()
    for z in (-0.85, 0.0, 0.85):
        b.quad((-0.36, 0, z), (0.36, 0, z), (-0.36, 0.34, z), (0.36, 0.34, z), STEEL.but(double=True), (0, 0, 1))
    canvas = T('fabric', 'green')
    b.quad((0.38, 0.38, 0.92), (-0.38, 0.38, 0.92), (0.38, 0.34, 0.0), (-0.38, 0.34, 0.0), canvas, (0, 1, 0))
    b.quad((0.38, 0.34, 0.0), (-0.38, 0.34, 0.0), (0.38, 0.38, -0.92), (-0.38, 0.38, -0.92), canvas, (0, 1, 0))
    for sx in (-1, 1):
        b.bar((sx * 0.38, 0.37, -0.94), (sx * 0.38, 0.37, 0.94), 0.04, STEEL)
    b.box(-0.26, 0.37, -0.86, 0.26, 0.47, -0.58, PILLOW, skip='b')
    b.box(-0.37, 0.36, 0.30, 0.37, 0.44, 0.70, fab('grey'), skip='b')              # folded blanket
    return b.faces


# ============================================================================= spa, gym and pool


@obj('massage_bed', 1, 2)
def _():
    b = B()
    for z in (-0.6, 0.6):
        b.box(-0.28, 0.0, z - 0.05, 0.28, 0.60, z + 0.05, WHITEWOOD, skip='bt')
    b.box(-0.34, 0.60, -0.82, 0.34, 0.74, 0.92, C('e8dcc8'), skip='b')
    b.box(-0.14, 0.60, -0.98, 0.14, 0.70, -0.82, C('e8dcc8'), skip='b')         # face cradle
    b.flat(-0.06, -0.94, 0.06, -0.86, 0.701, C('3a3020'))
    b.box(-0.35, 0.74, 0.20, 0.35, 0.78, 0.92, T('towels', 'mint', fit=True), skip='b')
    b.cyl(0.0, -0.62, 0.07, 0.74, 0.86, 5, C('f4f2ec'))                           # rolled towel
    return b.faces


@obj('sauna', 3, 3)
def _():
    b = B()
    PL = T('wood', 'teak', fit=True, rot90=False)
    H = 2.30
    for k in range(3):
        x0 = -1.45 + k * 2.9 / 3
        x1 = x0 + 2.9 / 3
        for y0, y1 in ((0.0, H / 2), (H / 2, H)):
            b.panel(x0, y0, x1, y1, -1.45, PL, back=True)
            b.panel_x(x0, y0, x1, y1, -1.45, PL, neg=True)
            b.panel_x(x0, y0, x1, y1, 1.45, PL)
            if k != 2:
                b.panel(x0, y0, x1, y1, 1.45, PL)
            elif y0 > 0:
                b.panel(x0, 2.05, x1, y1, 1.45, PL.but(sub=(0, 0, 1, 0.25)))
    b.box(-1.50, H, -1.50, 1.50, H + 0.12, 1.50, T('grain', 'teak', k=0.8), mats={'t': T('wood', 'teak', fit=True, k=0.85)})
    # glass door (bronze) in the right third of the front, a window and a sign
    b.panel(0.48, 0.0, 1.45, 2.05, 1.45, T('grain', 'walnut'))
    b.panel(0.58, 0.08, 1.35, 1.98, 1.455, T('glass', 'mirror', fit=True, k=0.75))
    b.box(1.22, 0.9, 1.455, 1.30, 1.2, 1.50, BRASS, skip='bk')
    b.panel(-1.15, 1.10, -0.45, 1.70, 1.455, T('glass', 'mirror', fit=True, k=0.7))
    b.box(-1.20, 1.05, 1.45, -0.40, 1.10, 1.52, T('grain', 'walnut'), skip='bk')
    b.cyl(-0.9, -0.9, 0.10, H + 0.12, H + 0.55, 5, STEEL, top=BLACK)
    b.box(-0.3, 0.0, 1.55, 0.35, 0.42, 1.95, T('grain', 'teak'), skip='b')
    return b.faces


@obj('hot_tub', 2, 2)
def _():
    b = B()
    R, H = 0.92, 0.85
    b.cyl(0, 0, R, 0.0, H, 8, T('barrel', 'teak', fit=True), cap=False)
    outer = b.ring(0, 0, R, 8, rot=math.pi / 8)
    inner = b.ring(0, 0, R - 0.10, 8, rot=math.pi / 8)
    for i in range(8):
        j = (i + 1) % 8
        b.quad((outer[i][0], H, outer[i][1]), (outer[j][0], H, outer[j][1]), (inner[i][0], H, inner[i][1]),
               (inner[j][0], H, inner[j][1]), T('grain', 'teak'), (0, 1, 0))
    b.poly_top(inner, H - 0.10, WATER)
    b.box(-0.35, 0.0, R - 0.05, 0.35, 0.30, R + 0.08, T('grain', 'teak'))
    b.box(-0.35, 0.0, R - 0.25, 0.35, 0.55, R - 0.05, T('grain', 'teak'), skip='bk')
    return b.faces


@obj('towel_rack', 1, 1)
def _():
    b = B()
    for sx in (-1, 1):
        b.bar((sx * 0.38, 0.0, -0.10), (sx * 0.38, 1.40, -0.10), 0.04, CHROME)
        b.box(sx * 0.38 - 0.04, 0.0, -0.28, sx * 0.38 + 0.04, 0.04, 0.10, CHROME)
    for y, pal in ((1.38, 'white'), (0.95, 'teal'), (0.55, 'white')):
        b.bar((-0.38, y, -0.10), (0.38, y, -0.10), 0.03, CHROME, cap=False)
        tw = T('towels', pal, fit=True, double=True)
        b.quad((0.30, y - 0.42, -0.06), (-0.30, y - 0.42, -0.06), (0.30, y, -0.07), (-0.30, y, -0.07), tw, (0, 0, 1))
        b.quad((-0.30, y - 0.38, -0.14), (0.30, y - 0.38, -0.14), (-0.30, y, -0.13), (0.30, y, -0.13), tw, (0, 0, -1))
    return b.faces


@obj('treadmill', 1, 2)
def _():
    b = B()
    b.box(-0.36, 0.0, -0.70, 0.36, 0.20, 0.92, C('2a2c30'), skip='b')
    b.flat(-0.26, -0.66, 0.26, 0.88, 0.205, T('ribs', 'rubber', fit=True))
    for sx in (-1, 1):
        b.bar((sx * 0.32, 0.20, -0.68), (sx * 0.30, 1.30, -0.80), 0.05, C('6a7078'))
        b.bar((sx * 0.30, 1.05, -0.80), (sx * 0.30, 1.05, -0.30), 0.04, CHROME)
    b.box(-0.36, 1.18, -0.92, 0.36, 1.40, -0.70, C('2a2c30'))
    b.quad((0.32, 1.40, -0.70), (-0.32, 1.40, -0.70), (0.32, 1.46, -0.86), (-0.32, 1.46, -0.86),
           T('buttons', 'buttons', fit=True, glow=True), v_norm((0, 1, 0.4)))
    return b.faces


@obj('weights', 2, 1)
def _():
    b = B()
    b.box(-0.20, 0.0, -0.10, 0.20, 0.40, 0.30, C('3a3c42'), skip='bt')
    b.box(-0.20, 0.40, -0.40, 0.20, 0.50, 0.45, leather('black'), skip='b')
    for sx in (-1, 1):
        b.box(sx * 0.42 - 0.04, 0.0, -0.44, sx * 0.42 + 0.04, 1.05, -0.36, C('3a3c42'), skip='b')
    b.rod((-0.92, 1.00, -0.40), (0.92, 1.00, -0.40), 0.04, CHROME)
    for sx in (-1, 1):
        st = b.mark()
        b.cyl(0, 0, 0.22, -0.05, 0.05, 6, BLACK, rot=0.0)
        b.rot(st, 'z', math.pi / 2 * sx)
        b.move(st, sx * 0.72, 1.00, -0.40)
    # a dumbbell rack
    b.box(0.55, 0.0, -0.05, 0.95, 0.30, 0.40, C('3a3c42'), skip='b', mats={'t': T('ribs', 'rubber', fit=True)})
    for z in (0.02, 0.17, 0.32):
        b.rod((0.60, 0.36, z), (0.90, 0.36, z), 0.10, BLACK)
    return b.faces


@obj('lounger', 1, 2)
def _():
    b = B()
    frame = WHITEWOOD
    for z in (-0.70, 0.85):
        b.box(-0.32, 0.0, z - 0.04, 0.32, 0.20, z + 0.04, frame, skip='bt')
    b.box(-0.32, 0.20, -0.30, 0.32, 0.27, 0.92, frame, skip='b')
    cush = T('ribs', 'aqua', fit=True, rot90=True)
    b.box(-0.29, 0.27, -0.28, 0.29, 0.33, 0.90, C('f4f4f0'), mats={'t': cush}, skip='bk')
    # inclined back rest
    st = b.mark()
    b.box(-0.30, 0.0, 0.0, 0.30, 0.08, 0.66, C('f4f4f0'), mats={'t': cush}, skip='')
    b.rot(st, 'x', 0.95)
    b.move(st, 0, 0.27, -0.28)
    b.box(-0.32, 0.20, -0.92, 0.32, 0.27, -0.30, frame, skip='bf')
    b.box(-0.10, 0.33, 0.55, 0.20, 0.37, 0.85, T('towels', 'coral', fit=True), skip='b')
    return b.faces


@obj('umbrella', 1, 1)
def _():
    b = B()
    b.cyl(0, 0, 0.20, 0.0, 0.10, 6, C('e8e4dc'))
    b.box(-0.025, 0.10, -0.025, 0.025, 2.25, 0.025, WHITEWOOD, skip='b')
    n = 8
    R = 1.05
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        p0 = (R * math.cos(a0), 1.82, R * math.sin(a0))
        p1 = (R * math.cos(a1), 1.82, R * math.sin(a1))
        col = C('f05a40', double=True) if i % 2 == 0 else C('fffaf0', double=True)
        nn = face_normal([p0, p1, (0, 2.28, 0)])
        if nn[1] < 0:
            nn = v_mul(nn, -1)
        b.tri(p0, p1, (0, 2.28, 0), col, nn)
        # scalloped valance
        b.quad(p0, p1, (p0[0], 1.72, p0[2]), (p1[0], 1.72, p1[2]), col, v_norm((p0[0] + p1[0], 0, p0[2] + p1[2])))
    b.cyl(0, 0, 0.04, 2.28, 2.36, 4, WHITEWOOD)
    return b.faces


# ============================================================================= conference


@obj('conf_table', 3, 2)
def _():
    b = B()
    for x in (-0.8, 0.8):
        b.box(x - 0.08, 0.0, -0.30, x + 0.08, 0.72, 0.30, WAL, skip='bt')
    poly = [(-1.25, -0.26), (-1.05, -0.46), (1.05, -0.46), (1.25, -0.26), (1.25, 0.26), (1.05, 0.46), (-1.05, 0.46), (-1.25, 0.26)]
    b.prism(poly, 0.72, 0.78, WAL, top=WAL)
    for x in (-0.75, 0.0, 0.75):
        for sz in (-1, 1):
            chair_lite(b, x, sz * 0.74, 0.0 if sz < 0 else math.pi, fab('navy'), C('3a3c42'), w=0.42, back_h=0.92)
        b.flat(x - 0.12, -0.32, x + 0.10, -0.16, 0.782, C('f8f8f4'))
        b.flat(x - 0.10, 0.16, x + 0.12, 0.32, 0.782, C('f8f8f4'))
    b.cyl(0.0, 0.0, 0.05, 0.78, 0.98, 4, C('c0e8f4', glow=True))
    return b.faces


@obj('projector', 1, 1)
def _():
    b = B()
    for k in range(3):
        a = k * 2 * math.pi / 3 + math.pi / 2
        b.bar((0.0, 0.55, -0.15), (0.32 * math.cos(a), 0.0, -0.15 + 0.32 * math.sin(a)), 0.03, C('3a3c42'))
    b.box(-0.025, 0.55, -0.175, 0.025, 1.0, -0.125, C('3a3c42'), skip='b')
    b.box(-0.48, 0.95, -0.20, 0.48, 1.03, -0.10, C('3a3c42'))
    b.box(-0.46, 1.03, -0.16, 0.46, 2.05, -0.145, C('f4f4f0'), mats={'f': T('picture', 'picture', fit=True, glow=True)})
    b.box(-0.47, 2.05, -0.17, 0.47, 2.09, -0.13, C('3a3c42'))
    return b.faces


@obj('lectern', 1, 1)
def _():
    b = B()
    b.box(-0.30, 0.0, -0.30, 0.30, 0.06, 0.24, WAL)
    b.extrude([(-0.24, -0.22), (0.24, -0.22), (0.20, 0.16), (-0.20, 0.16)], 0.06, 1.0, WAL, cap=False)
    b.quad((0.28, 1.0, 0.22), (-0.28, 1.0, 0.22), (0.28, 1.14, -0.26), (-0.28, 1.14, -0.26), WAL, v_norm((0, 1, 0.3)))
    b.quad((0.28, 1.0, 0.22), (-0.28, 1.0, 0.22), (0.28, 0.96, 0.22), (-0.28, 0.96, 0.22), WAL, (0, 0, 1))
    b.panel(-0.12, 0.55, 0.12, 0.75, 0.205, BRASS)
    b.bar((0.18, 1.08, -0.10), (0.16, 1.28, 0.06), 0.02, BLACK)
    b.box(0.13, 1.26, 0.04, 0.19, 1.32, 0.12, BLACK)
    b.box(-0.18, 1.04, -0.10, 0.08, 1.06, 0.12, C('f8f8f4'), skip='b')
    return b.faces


# ============================================================================= structure
# door / window: wall pieces 1 tile wide, origin at the wall centre (walls assumed <= 0.12 thick),
# facing +z. They fill the whole tile-wide wall panel (0..2.75), so the game skips its own wall
# quad there.

TRIM = C('f4f2ec')
PAINT_W = T('paint', 'paint_white', fit=True)


def door_leaf(b, x0, x1, mat=None):
    mat = mat or T('door', 'walnut', fit=True)
    b.box(x0, 0.0, -0.025, x1, 2.18, 0.025, T('grain', 'walnut'), skip='b', mats={'f': mat, 'k': mat})
    b.box(x0 + 0.30 * (x1 - x0) / 0.84, 1.55, 0.025, x0 + 0.54 * (x1 - x0) / 0.84, 1.66, 0.035, BRASS, skip='bk')   # number plate


def door_frame(b):
    for x0, x1 in ((-0.5, -0.42), (0.42, 0.5)):
        b.box(x0, 0.0, -0.07, x1, 2.26, 0.07, TRIM, skip='b')
    b.box(-0.5, 2.18, -0.07, 0.5, 2.30, 0.07, TRIM)
    b.box(-0.5, 2.30, -0.05, 0.5, 2.75, 0.05, PAINT_W.but(sub=(0, 0, 1, 0.16)), skip='btlr')


@obj('door', 1, 1)
def _():
    b = B()
    door_frame(b)
    door_leaf(b, -0.42, 0.42)
    return b.faces


@obj('window', 1, 1)
def _():
    b = B()
    b.box(-0.5, 0.0, -0.05, 0.5, 0.86, 0.05, PAINT_W.but(sub=(0, 0.69, 1, 1)), skip='btlr')
    b.box(-0.5, 2.24, -0.05, 0.5, 2.75, 0.05, PAINT_W.but(sub=(0, 0, 1, 0.18)), skip='btlr')
    b.box(-0.50, 0.84, -0.12, 0.50, 0.90, 0.14, TRIM)                                   # sill
    for x0, x1 in ((-0.5, -0.42), (0.42, 0.5), (-0.025, 0.025)):
        b.box(x0, 0.90, -0.06, x1, 2.24, 0.06, TRIM, skip='b')
    b.box(-0.5, 2.16, -0.06, 0.5, 2.24, 0.06, TRIM, skip='b')
    b.box(-0.42, 1.52, -0.04, 0.42, 1.56, 0.04, TRIM, skip='b')
    b.panel(-0.42, 0.90, 0.42, 2.16, 0.0, GLASS)
    return b.faces


def flight(b, hw, z_bottom, z_top, rise, steps, tread, riser, side=None, side_x=None, wall_h=0.18):
    """Steps from z_bottom (y=0) up to z_top (y=rise) along -z; x in -hw..hw."""
    run = (z_bottom - z_top) / steps
    h = rise / steps
    for i in range(steps):
        z1 = z_bottom - i * run
        z0 = z1 - run
        y0, y1 = i * h, (i + 1) * h
        b.panel(-hw, y0, hw, y1, z1, riser)
        b.flat(-hw, z0, hw, z1, y1, tread)
    return run, h


@obj('stairs', 2, 4)
def _():
    b = B()
    hw = 0.94
    flight(b, hw, 2.0, -2.0, 3.0, 12, T('grain', 'oak', fit=True), C('f0ece4'))
    side = C('e8e4dc')
    for sx in (-1, 1):
        x = sx * 1.0
        n = (sx, 0, 0)
        b.quad((x, 0.0, 2.0), (x, 0.0, -2.0), (x, 0.40, 2.0), (x, 3.15, -2.0), side, n)
        xi = sx * hw
        b.quad((xi, 0.25, 2.0), (x, 0.25, 2.0), (xi, 0.40, 2.0), (x, 0.40, 2.0), side, (0, 0, 1))
        b.quad((x, 0.40, 2.0), (xi, 0.40, 2.0), (x, 3.15, -2.0), (xi, 3.15, -2.0), side, v_norm((0, 4.0, 2.75)))
        g = GLASS
        b.quad((sx * 0.97, 0.40, 2.0), (sx * 0.97, 3.15, -2.0), (sx * 0.97, 1.25, 2.0), (sx * 0.97, 4.0, -2.0), g, (sx, 0, 0))
        b.bar((sx * 0.97, 1.27, 2.02), (sx * 0.97, 4.02, -1.98), 0.05, CHROME, cap=False)
    b.panel(-1.0, 0.0, 1.0, 3.0, -2.0, side, back=True)
    return b.faces


@obj('elevator', 2, 2)
def _():
    b = B()
    H = 3.0
    wall = T('stone', 'stone_sand', fit=True)
    for x0 in (-0.98, 0.0):                                      # back and side walls, one panel per tile
        b.panel(x0, 0.0, x0 + 0.98, H, -0.98, wall, back=True)
        b.panel_x(x0, 0.0, x0 + 0.98, H, -0.98, wall, neg=True)
        b.panel_x(x0, 0.0, x0 + 0.98, H, 0.98, wall)
    z = 0.98
    b.panel(-0.98, 0.0, -0.56, H, z, wall.but(sub=(0, 0, 0.45, 1)))
    b.panel(0.56, 0.0, 0.98, H, z, wall.but(sub=(0.55, 0, 1, 1)))
    b.panel(-0.56, 2.32, 0.56, H, z, wall.but(sub=(0, 0, 1, 0.22)))
    b.flat(-0.98, -0.98, 0.98, 0.98, H, C('3a3a40'))
    door = T('chrome', 'steel', fit=True)
    b.panel(-0.48, 0.0, -0.005, 2.20, z - 0.04, door)
    b.panel(0.005, 0.0, 0.48, 2.20, z - 0.04, door)
    for x0, x1 in ((-0.56, -0.48), (0.48, 0.56)):
        b.box(x0, 0.0, z - 0.06, x1, 2.32, z + 0.03, BRASS, skip='bk')
    b.box(-0.56, 2.20, z - 0.06, 0.56, 2.32, z + 0.03, BRASS, skip='bk')
    b.panel(-0.16, 2.42, 0.16, 2.62, z + 0.01, C('ffc860', glow=True))
    b.panel(0.66, 1.0, 0.80, 1.32, z + 0.01, T('buttons', 'buttons', fit=True, glow=True, sub=(0.25, 0.1, 0.75, 0.9)))
    return b.faces


@obj('glass_elevator', 2, 2)
def _():
    b = B()
    H = 3.0
    for sx in (-1, 1):
        for sz in (-1, 1):
            b.box(sx * 0.96 - 0.05, 0.0, sz * 0.96 - 0.05, sx * 0.96 + 0.05, H, sz * 0.96 + 0.05, CHROME, skip='bt')
    g = GLASS
    b.panel(-0.91, 0.0, 0.91, H, -0.96, g, back=True)
    b.panel_x(-0.91, 0.0, 0.91, H, -0.96, g, neg=True)
    b.panel_x(-0.91, 0.0, 0.91, H, 0.96, g)
    b.panel(-0.91, 2.30, 0.91, H, 0.96, g)
    b.panel(-0.91, 0.0, -0.46, 2.30, 0.96, g)
    b.panel(0.46, 0.0, 0.91, 2.30, 0.96, g)
    b.box(-0.91, 2.26, 0.93, 0.91, 2.34, 0.99, CHROME, skip='b')
    b.box(-0.46, 0.0, 0.93, -0.40, 2.30, 0.99, CHROME, skip='bt')
    b.box(0.40, 0.0, 0.93, 0.46, 2.30, 0.99, CHROME, skip='bt')
    b.box(-1.0, 0.0, 0.94, 1.0, 0.10, 1.0, CHROME, skip='b')
    return b.faces


@obj('glass_elevator_cab', 2, 2)
def _():
    b = B()
    b.box(-0.86, 0.0, -0.86, 0.86, 0.14, 0.86, CHROME, mats={'t': T('carpet', 'carpet_royal', fit=True)})
    for sx in (-1, 1):
        for sz in (-1, 1):
            b.box(sx * 0.84 - 0.03, 0.14, sz * 0.84 - 0.03, sx * 0.84 + 0.03, 2.30, sz * 0.84 + 0.03, BRASS, skip='bt')
    g = GLASS
    b.panel(-0.84, 0.14, 0.84, 2.30, -0.84, g, back=True)
    b.panel_x(-0.84, 0.14, 0.84, 2.30, -0.84, g, neg=True)
    b.panel_x(-0.84, 0.14, 0.84, 2.30, 0.84, g)
    for (x0, z0, x1, z1) in ((-0.86, -0.86, 0.86, -0.80), (-0.86, -0.80, -0.80, 0.86), (0.80, -0.80, 0.86, 0.86)):
        b.box(x0, 0.95, z0, x1, 1.0, z1, BRASS)
    b.box(-0.90, 2.30, -0.90, 0.90, 2.44, 0.90, BRASS, mats={'b': C('fff0c0', glow=True)}, skip='')
    b.cyl(0, 0, 0.30, 2.44, 2.56, 6, BRASS, r1=0.10)
    return b.faces


@obj('grand_staircase', 3, 6)
def _():
    b = B()
    tread = T('runner', 'runner', fit=True)
    riser = T('runner', 'runner', fit=True, k=0.82)
    steps, rise = 12, 3.0
    zb, zt = 3.0, -2.4
    run = (zb - zt) / steps
    h = rise / steps
    side = T('marble', 'marble_white', fit=True, k=0.95)
    for i in range(steps):
        z1 = zb - i * run
        z0 = z1 - run
        hw = 1.48 if i < 2 else 1.18
        b.panel(-hw, i * h, hw, (i + 1) * h, z1, riser)
        b.flat(-hw, z0, hw, z1, (i + 1) * h, tread)
        if i < 2:
            for sx in (-1, 1):
                b.panel_x(z0, 0.0, z1, (i + 1) * h, sx * hw, side, neg=sx < 0)
    b.flat(-1.18, -3.0, 1.18, zt, 3.0, tread)
    zs = zb - 2 * run
    plain = C('ece6dc')
    for sx in (-1, 1):
        xo, xi = sx * 1.42, sx * 1.18
        y0 = 2 * h
        b.quad((xo, 0.0, zs), (xo, 0.0, -3.0), (xo, y0 + 0.9, zs), (xo, 3.9, -3.0), plain, (sx, 0, 0))
        b.quad((xi, y0, zs), (xi, 3.0, -3.0), (xi, y0 + 0.9, zs), (xi, 3.9, -3.0), plain, (-sx, 0, 0))
        b.quad((xo, y0 + 0.9, zs), (xi, y0 + 0.9, zs), (xo, 3.9, -3.0), (xi, 3.9, -3.0), BRASS,
               v_norm((0, 1, (3.9 - y0 - 0.9) / (zs + 3.0))))
        b.quad((xi, y0, zs), (xo, 0.0, zs), (xi, y0 + 0.9, zs), (xo, y0 + 0.9, zs), plain, (0, 0, 1))
        # newel post with a globe lamp
        b.box(sx * 1.30 - 0.13, 0.0, zs - 0.13, sx * 1.30 + 0.13, 1.20, zs + 0.13, side, skip='b')
        gl = C('fff4d8', glow=True)
        cx, cz = sx * 1.30, zs
        b.cone(cx, cz, 0.15, 1.36, 1.20, 4, gl)
        b.cone(cx, cz, 0.15, 1.36, 1.56, 4, gl)
    b.panel(-1.42, 0.0, 1.42, 3.0, -3.0, plain, back=True)
    return b.faces


def blob(b, cx, cy, cz, r, mat, n=6, squash=0.8):
    """A chunky low-poly ball (for foliage): cones top and bottom, one band."""
    top = (cx, cy + r * squash, cz)
    bot = (cx, cy - r * squash * 0.8, cz)
    up = [(cx + r * 0.85 * math.cos(2 * math.pi * i / n), cy + r * 0.35 * squash, cz + r * 0.85 * math.sin(2 * math.pi * i / n)) for i in range(n)]
    dn = [(cx + r * math.cos(2 * math.pi * (i + 0.5) / n), cy - r * 0.2 * squash, cz + r * math.sin(2 * math.pi * (i + 0.5) / n)) for i in range(n)]
    for i in range(n):
        j = (i + 1) % n
        nn = face_normal([up[i], up[j], top])
        if nn[1] < 0:
            nn = v_mul(nn, -1)
        b.tri(up[i], up[j], top, mat, nn)
        # band: up[i], up[j] above dn[i]
        mid = v_norm(v_sub(v_mul(v_add(up[i], up[j]), 0.5), (cx, cy, cz)))
        b.tri(up[i], up[j], dn[i], mat, mid)
        mid2 = v_norm(v_sub(v_mul(v_add(dn[i], dn[(i - 1) % n]), 0.5), (cx, cy, cz)))
        b.tri(dn[(i - 1) % n], dn[i], up[i], mat, mid2)
        nb = face_normal([dn[i], dn[j], bot])
        if nb[1] > 0:
            nb = v_mul(nb, -1)
        b.tri(dn[i], dn[j], bot, mat, nb)


@obj('fountain', 2, 2)
def _():
    b = B()
    R = 0.95
    st = T('marble', 'marble_white', fit=True)
    b.cyl(0, 0, R, 0.0, 0.45, 8, st, cap=False, rot=math.pi / 8)
    outer = b.ring(0, 0, R, 8, rot=math.pi / 8)
    inner = b.ring(0, 0, R - 0.12, 8, rot=math.pi / 8)
    for i in range(8):
        j = (i + 1) % 8
        b.quad((outer[i][0], 0.45, outer[i][1]), (outer[j][0], 0.45, outer[j][1]), (inner[i][0], 0.45, inner[i][1]),
               (inner[j][0], 0.45, inner[j][1]), st, (0, 1, 0))
    b.poly_top(inner, 0.36, WATER)
    b.cyl(0, 0, 0.12, 0.36, 1.05, 6, st, cap=False)
    b.cyl(0, 0, 0.12, 1.0, 1.15, 6, st, r1=0.42, cap=False)
    b.cyl(0, 0, 0.42, 1.15, 1.18, 6, st, top=WATER, cap=True)
    b.cyl(0, 0, 0.05, 1.18, 1.40, 5, st)
    jet = T('glass', 'pool_water', fit=True, semi=1, double=True, glow=True)
    for a in (0.0, math.pi / 2):
        dx, dz = math.cos(a) * 0.32, math.sin(a) * 0.32
        b.quad((dx, 1.18, dz), (-dx, 1.18, -dz), (dx * 0.2, 1.75, dz * 0.2), (-dx * 0.2, 1.75, -dz * 0.2), jet, v_norm((-dz, 0, dx)))
    # falling water sheet from the bowl
    for a in (0.0, math.pi / 2):
        dx, dz = math.cos(a) * 0.70, math.sin(a) * 0.70
        b.quad((dx, 0.36, dz), (-dx, 0.36, -dz), (dx * 0.6, 1.16, dz * 0.6), (-dx * 0.6, 1.16, -dz * 0.6), jet, v_norm((-dz, 0, dx)))
    return b.faces


@obj('door_frame', 1, 1)
def _():
    b = B()
    door_frame(b)
    return b.faces


@obj('door_leaf', 1, 1)
def _():
    b = B()
    door_leaf(b, 0.0, 0.84)
    return b.faces


# ============================================================================= catalogue additions

@obj('chandelier', 2, 2)
def _():
    # placed on a void tile: hangs from the ceiling (y 2.75) down to about y -1.5 into the void
    b = B()
    G_ = BRASS
    b.tag = 'frame'
    b.cone(0, 0, 0.18, 2.75, 2.64, 4, G_)
    b.rod((0, 0.95, 0), (0, 2.70, 0), 0.05, G_)
    b.cyl(0, 0, 0.12, 0.10, 1.00, 6, G_, r1=0.18)
    n = 8
    bulb = C('fff4c0', glow=True)
    for yy_, rr in ((0.62, 0.88), (0.12, 0.62)):
        ring = b.ring(0, 0, rr, n, rot=math.pi / 8)
        for i in range(n):
            j = (i + 1) % n
            b.quad((ring[i][0], yy_, ring[i][1]), (ring[j][0], yy_, ring[j][1]),
                   (ring[i][0], yy_ + 0.10, ring[i][1]), (ring[j][0], yy_ + 0.10, ring[j][1]), G_,
                   v_norm((ring[i][0] + ring[j][0], 0.3, ring[i][1] + ring[j][1])))
        for i in range(n):
            a = 2 * math.pi * i / n + math.pi / 8
            x, z = rr * math.cos(a), rr * math.sin(a)
            b.rod((x * 0.2, yy_ + 0.05, z * 0.2), (x, yy_ + 0.05, z), 0.04, G_)
            b.box(x - 0.035, yy_ + 0.10, z - 0.035, x + 0.035, yy_ + 0.22, z + 0.035, C('fbf8f0'))
            b.cone(x, z, 0.08, yy_ + 0.22, yy_ + 0.42, 4, bulb)
    b.tag = 'crystal'
    cr = T('crystal', 'crystal', fit=True, glow=True, double=True)
    b.cone(0, 0, 0.55, 0.10, -1.50, 8, cr, rot=math.pi / 8)
    b.tag = ''
    return b.faces




@obj('skylight', 2, 2)
def _():
    # a roof piece over a void: the curb sits on the roof (y 2.75 .. 3.0), glass from y 2.9 up
    b = B()
    y0 = 2.75
    b.box(-0.98, y0, -0.98, 0.98, y0 + 0.25, 0.98, C('e8e4dc'), skip='bt')
    inner = 0.84
    TR = C('f4f2ec')
    yt = y0 + 0.25
    b.box(-0.98, yt - 0.04, -0.98, 0.98, yt + 0.02, -inner, TR, skip='b')
    b.box(-0.98, yt - 0.04, inner, 0.98, yt + 0.02, 0.98, TR, skip='b')
    b.box(-0.98, yt - 0.04, -inner, -inner, yt + 0.02, inner, TR, skip='bfk')
    b.box(inner, yt - 0.04, -inner, 0.98, yt + 0.02, inner, TR, skip='bfk')
    apex = (0.0, yt + 0.55, 0.0)
    c = [(-inner, yt - 0.1, -inner), (inner, yt - 0.1, -inner), (inner, yt - 0.1, inner), (-inner, yt - 0.1, inner)]
    for i in range(4):
        p, q = c[i], c[(i + 1) % 4]
        nn = face_normal([p, q, apex])
        if nn[1] < 0:
            nn = v_mul(nn, -1)
        b.tri(p, q, apex, GLASS, nn)
        b.rod(p, apex, 0.05, TR)
    return b.faces


@obj('indoor_tree', 2, 2, 2)
def _():
    b = B()
    pot = T('terrazzo', 'terrazzo', fit=True)
    b.cyl(0, 0, 0.88, 0.0, 0.62, 8, pot, top=C('3a2a1a'), rot=math.pi / 8)
    b.cyl(0, 0, 0.16, 0.62, 3.6, 5, T('grain', 'walnut', rot90=True), r1=0.08, cap=False)
    b.rod((0.0, 2.2, 0.0), (0.62, 3.4, 0.36), 0.10, C('5a3a20'))
    b.rod((0.0, 2.5, 0.0), (-0.58, 3.6, -0.42), 0.09, C('5a3a20'))
    lf = T('leaves', 'leaf', fit=True)
    blob(b, 0.0, 4.55, 0.0, 1.10, lf)
    blob(b, 0.68, 3.75, 0.40, 0.80, lf)
    blob(b, -0.62, 3.95, -0.45, 0.82, lf)
    return b.faces


@obj('railing', 1, 1)
def _():
    # brass handrail on turned white balusters, along x at the tile's +z edge
    b = B()
    z = 0.46
    b.box(-0.5, 0.0, z - 0.04, 0.5, 0.08, z + 0.04, C('e8e4dc'), skip='blr')
    for k in range(5):
        x = -0.4 + k * 0.2
        b.box(x - 0.025, 0.08, z - 0.025, x + 0.025, 0.96, z + 0.025, C('f4f2ec'), skip='bt')
        b.box(x - 0.04, 0.40, z - 0.04, x + 0.04, 0.52, z + 0.04, C('f4f2ec'), skip='bt')
    b.box(-0.5, 0.96, z - 0.05, 0.5, 1.04, z + 0.05, BRASS, skip='blr')
    return b.faces


@obj('railing_glass', 1, 1)
def _():
    b = B()
    z = 0.47
    b.box(-0.5, 0.0, z - 0.03, 0.5, 0.08, z + 0.03, C('8a9098'), skip='blr')
    b.panel(-0.5, 0.08, 0.5, 1.0, z, GLASS)
    b.box(-0.5, 1.0, z - 0.035, 0.5, 1.06, z + 0.035, CHROME, skip='blr')
    return b.faces


@obj('bed_king', 2, 2)
def _():
    b = B()
    bed(b, 0.96, 0.97, 2, leather('purple'), fab('mustard'), duvet=QUILT, base=CHERRY)
    # a taller winged headboard and a padded bench at the foot
    b.box(-1.0, 0.0, -0.99, 1.0, 1.55, -0.89, CHERRY, mats={'f': leather('purple')})
    b.box(-1.0, 1.55, -1.0, 1.0, 1.62, -0.87, BRASS)
    b.box(-0.2, 0.52, -0.46, 0.2, 0.72, -0.38, fab('teal'), skip='b')
    return b.faces


@obj('phone', 1, 1)
def _():
    # a bedside table with a beige room-service phone
    b = B()
    b.box(-0.26, 0.0, -0.26, 0.26, 0.58, 0.20, WAL, mats={'f': T('cabinet', 'walnut', fit=True, sub=(0, 0, 1, 0.5))})
    beige = C('e4d8b8')
    b.box(-0.13, 0.58, -0.14, 0.13, 0.66, 0.08, beige, skip='b')
    b.box(-0.12, 0.66, -0.12, 0.12, 0.70, -0.05, C('d0c4a0'), skip='b')              # handset
    b.box(-0.13, 0.66, -0.13, -0.08, 0.72, -0.04, beige, skip='b')
    b.box(0.08, 0.66, -0.13, 0.13, 0.72, -0.04, beige, skip='b')
    b.flat(-0.08, -0.02, 0.08, 0.06, 0.661, T('buttons', 'buttons', fit=True))
    b.box(0.10, 0.58, 0.02, 0.20, 0.60, 0.16, C('f8f4e8'))                            # memo pad
    return b.faces


@obj('modem', 1, 1)
def _():
    # a small writing table with a beige dial-up modem: lights blink (emissive)
    b = B()
    for sx in (-1, 1):
        b.box(sx * 0.30 - 0.03, 0.0, -0.25, sx * 0.30 + 0.03, 0.66, 0.15, C('d8d8d4'), skip='bt')
    b.box(-0.34, 0.66, -0.28, 0.34, 0.70, 0.18, C('ececE8'))
    beige = C('e4d8b8')
    b.box(-0.16, 0.70, -0.16, 0.16, 0.76, 0.06, beige, skip='b')
    for k, col in enumerate(('40f070', 'f0c040', '40f070', 'f05040')):
        x = -0.11 + k * 0.06
        b.box(x - 0.015, 0.71, 0.06, x + 0.015, 0.74, 0.07, C(col, glow=True), skip='bk')
    b.rod((0.16, 0.72, -0.10), (0.30, 0.70, -0.24), 0.02, C('3a3a40'))
    b.box(-0.30, 0.70, 0.0, -0.18, 0.71, 0.14, C('3a3a40'))                         # floppy disk
    return b.faces


@obj('arcade', 1, 1)
def _():
    # a Y2K arcade cabinet: glowing marquee, angled screen, control panel, purple side art
    b = B()
    side = T('fabric', 'purple', k=1.35)
    hw = 0.34
    poly = [(-0.36, 0.0), (0.30, 0.0), (0.30, 0.95), (0.42, 0.95), (0.42, 1.05), (0.12, 1.60), (0.22, 1.95), (-0.36, 1.95)]
    # side panels (profile in z/y), front pieces between them
    for sx in (-1, 1):
        st = b.mark()
        b.extrude([(z, y) for z, y in poly], -0.03, 0.03, side, top=side, cap=True)
        b.rot(st, 'z', math.pi / 2)
        b.rot(st, 'y', -math.pi / 2)
        b.move(st, sx * hw, 0, 0)
    blk = C('1a1a24')
    b.panel(-hw, 0.0, hw, 0.95, 0.30, T('grille', 'black', fit=True))
    b.quad((hw, 0.95, 0.30), (-hw, 0.95, 0.30), (hw, 0.95, 0.42), (-hw, 0.95, 0.42), blk, (0, 1, 0))
    b.quad((hw, 1.05, 0.42), (-hw, 1.05, 0.42), (hw, 1.60, 0.12), (-hw, 1.60, 0.12), T('screen', 'screen_on', fit=True, glow=True),
           v_norm((0, 0.48, 0.88)))
    b.panel(-hw, 0.95, hw, 1.05, 0.42, C('e03a8a'))
    b.quad((hw, 1.60, 0.12), (-hw, 1.60, 0.12), (hw, 1.95, 0.22), (-hw, 1.95, 0.22), T('neon', 'neon', fit=True, glow=True),
           v_norm((0, -0.3, 1.0)))
    b.flat(-hw, -0.36, hw, 0.22, 1.95, blk)
    b.panel(-hw, 0.0, hw, 1.95, -0.36, blk, back=True)
    for x, col in ((-0.15, 'f04040'), (0.0, '40c0f0'), (0.12, 'f0d040')):
        b.box(x - 0.03, 1.05, 0.33, x + 0.03, 1.09, 0.39, C(col, glow=True), skip='b')
    b.rod((-0.24, 1.05, 0.36), (-0.24, 1.14, 0.36), 0.03, BLACK)
    return b.faces


@obj('palm', 1, 1)
def _():
    # an outdoor palm, about 3 tall: a leaning ringed trunk and drooping fronds
    b = B()
    bark = T('barrel', 'teak', fit=True, rot90=True)
    pts = [(0.0, 0.0, 0.0), (0.06, 0.8, 0.02), (0.16, 1.6, 0.05), (0.30, 2.4, 0.08), (0.42, 2.85, 0.10)]
    for i in range(len(pts) - 1):
        (x0, y0, z0), (x1, y1, z1) = pts[i], pts[i + 1]
        r0, r1 = 0.13 - 0.015 * i, 0.13 - 0.015 * (i + 1)
        st = b.mark()
        b.cyl(0, 0, r0, 0, y1 - y0, 5, bark, r1=r1, cap=False)
        b.xform(lambda p, x0=x0, y0=y0, z0=z0, x1=x1, y1=y1, z1=z1: (x0 + p[0] + (x1 - x0) * p[1] / (y1 - y0), y0 + p[1],
                                                                       z0 + p[2] + (z1 - z0) * p[1] / (y1 - y0)), st)
    tx, ty, tz = pts[-1]
    fm = T('leaves', 'palm', fit=True, double=True)
    for i in range(8):
        a = i * 2 * math.pi / 8 + 0.2
        frond(b, tx, tz, a, ty, 1.15 + 0.15 * (i % 2), 0.75, w=0.22, mat=fm)
    b.cyl(tx, tz, 0.12, ty - 0.1, ty + 0.12, 5, C('6a4a20'))
    return b.faces


@obj('coffee_machine', 1, 1)
def _():
    # a counter with a chrome espresso machine, cups and a red accent
    b = B()
    b.box(-0.42, 0.0, -0.36, 0.42, 0.88, 0.22, T('grain', 'walnut'), mats={'f': T('cabinet', 'walnut', fit=True)})
    b.box(-0.44, 0.88, -0.38, 0.44, 0.92, 0.25, T('marble', 'marble_black', fit=True))
    b.box(-0.30, 0.92, -0.32, 0.18, 1.34, 0.05, CHROME, skip='b')
    b.box(-0.30, 1.34, -0.32, 0.18, 1.38, 0.05, C('c82a2a'), skip='b')
    b.box(-0.22, 1.02, 0.05, 0.10, 1.12, 0.12, BLACK, skip='bk')
    b.panel(-0.20, 1.20, 0.06, 1.30, 0.052, C('40f0a0', glow=True))
    for x in (-0.16, 0.04):
        b.cyl(x, 0.12, 0.035, 0.92, 0.98, 4, C('f8f8f4'))
    b.cyl(0.32, -0.10, 0.06, 0.92, 1.06, 5, C('6a3a20'), top=C('2a1408'))
    return b.faces


# ============================================================================= people (slots 8 and 9)
# 16x24 frames. A body sheet is 9 frames across (stand, walk 1-4, sit, carry, use, swim) by 4
# directions down (144 x 96 texels), two bodies per slot (slots 7, 8, 9). Directions are relative to the screen: 0 facing the viewer and screen-right,
# 1 facing the viewer and screen-left, 2 facing away and screen-left, 3 facing away and
# screen-right. With the camera looking from +x+z (yaw 225 degrees) a person walking +z uses 0,
# +x uses 1, -z uses 2 and -x uses 3. Frames are drawn with the feet on the bottom row (23).
#
# Palette indices: 1 outline, 2 skin, 3 skin shade, 4 hair, 5 hair shade, 6 top, 7 top shade,
# 8 bottom, 9 bottom shade, 10 shoes, 11 hat, 12 hat band, 13 accent (tie, apron, trim),
# 14 eyes / glasses, 15 white (collar, highlights).

PF_W, PF_H = 16, 24
FRAMES = ['stand', 'walk1', 'walk2', 'walk3', 'walk4', 'sit', 'carry', 'use', 'swim']

BODIES = {
    # name: hair style, hat, bottom, accent style, child
    'man':    dict(hair='short', hat=None, bottom='trousers', accent='tie', child=False),
    'woman':  dict(hair='long', hat=None, bottom='skirt', accent='apron', child=False),
    'cap':    dict(hair='short', hat='cap', bottom='trousers', accent='trim', child=False),
    'chef':   dict(hair='short', hat='toque', bottom='trousers', accent='scarf', child=False),
    'child':  dict(hair='short', hat=None, bottom='shorts', accent='stripe', child=True),
    'rocker': dict(hair='spiky', hat=None, bottom='trousers', accent='shirt', child=False),
}


def _person(body, back, pose, phase):
    """One frame facing screen-right (mirror it for the left directions)."""
    if pose == 'swim':
        # head and shoulders above the water line (the frame's bottom rows), with a ripple
        st = _person(body, back, 'stand', phase)
        child = BODIES[body]['child']
        top = 2 + (6 if child else 0) - (3 if BODIES[body]['hat'] == 'toque' else (2 if BODIES[body]['hair'] == 'spiky' else 1))
        shift = 11 - top
        img = np.zeros_like(st)
        for y in range(PF_H):
            sy = y - shift
            if 0 <= sy < PF_H and y <= 21:
                img[y] = st[sy]
        for x in range(1, 15):
            if (x + (1 if back else 0)) % 3 != 0:
                img[21 if x % 2 else 22, x] = 15
        img[23, :] = 0
        img[22, 4:12] = np.where(img[22, 4:12] == 0, 15, img[22, 4:12])
        return img
    P = BODIES[body]
    img = np.zeros((PF_H, PF_W), np.uint8)

    def px(x, y, c):
        if 0 <= x < PF_W and 0 <= y < PF_H:
            img[y, x] = c

    def rect(x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px(x, y, c)

    child = P['child']
    sit = pose == 'sit'
    carry = pose == 'carry'
    use = pose == 'use'
    dy = 0
    if child:
        dy = 6
    if sit:
        dy += 4
    if pose in ('walk2', 'walk4'):
        dy -= 1                              # bob up on the passing frames
    hx = 5                                   # head left column
    hy = 2 + dy                              # head top row
    ty = hy + 7                              # torso top
    tb = ty + (6 if not child else 4)        # torso bottom (inclusive)
    tx0, tx1 = (4, 11) if not child else (5, 10)
    # ---- legs
    hip = tb + 1
    if not sit:
        foot = 23
        # walk phase: (front leg dx, back leg dx, lifted leg) ; front leg is the right one
        ph = {'stand': (0, 0, None), 'carry': (0, 0, None), 'use': (0, 0, None), 'walk1': (2, -1, None),
              'walk2': (0, 0, 'b'), 'walk3': (-1, 2, None), 'walk4': (0, 0, 'f')}[pose]
        legs = (('b', 5 if not child else 6, ph[1]), ('f', 8 if not child else 8, ph[0]))
        for name, lx, ddx in legs:
            lift = 1 if ph[2] == name else 0
            w = 3 if not child else 2
            fy = foot - lift
            if P['bottom'] == 'skirt':
                for y in range(hip + 4, fy - 1):
                    rect(lx + 1 + (ddx if y > hip + 5 else 0), y, lx + 1 + (ddx if y > hip + 5 else 0), y, 2)
            else:
                cut = hip + 3 if P['bottom'] == 'shorts' else fy - 2
                for y in range(hip, fy - 1):
                    k = (y - hip) / max(1, fy - 2 - hip)
                    ox = int(round(ddx * k))
                    c = (8 if name == 'f' else 9) if y <= cut else 2
                    if P['bottom'] == 'shorts' and y > cut:
                        rect(lx + ox + (0 if w == 2 else 1), y, lx + ox + w - 1 - (0 if w == 2 else 0), y, 2)
                    else:
                        rect(lx + ox, y, lx + ox + w - 1, y, c)
            # shoe, pointing toward the facing side (+x)
            rect(lx + ddx, fy - 1, lx + ddx + w - 1 + (0 if back else 1), fy, 10)
        if P['bottom'] == 'skirt':
            for i, y in enumerate(range(hip, hip + 5)):
                rect(tx0 + 1 - i // 2, y, tx1 - 1 + i // 2, y, 8)
                px(tx0 + 1 - i // 2, y, 9)
    else:
        # sitting: thighs toward the facing side, shins down, shoes on the floor
        if not back:
            rect(6, hip, 12 if not child else 11, hip + 1, 8)
            rect(6, hip + 1, 11, hip + 1, 9)
            sx0 = 10 if not child else 9
            for y in range(hip + 2, 22):
                rect(sx0, y, sx0 + 1, y, 8 if P['bottom'] != 'shorts' else 2)
            rect(sx0, 22, sx0 + 2, 23, 10)
            rect(sx0 - 3, 22, sx0 - 1, 23, 10)
            for y in range(hip + 2, 22):
                rect(sx0 - 3, y, sx0 - 2, y, 9 if P['bottom'] != 'shorts' else 3)
        else:
            rect(5, hip, 10, hip + 1, 9)
            rect(4, 22, 6, 23, 10)
            rect(9, 22, 11, 23, 10)
    # ---- torso
    rect(tx0, ty, tx1, tb, 6)
    px(tx0, ty, 0); px(tx1, ty, 0)
    rect(tx0, ty + 1, tx0, tb, 7)
    rect(tx0, tb, tx1, tb, 7)
    if not back:
        acc = P['accent']
        cx = 8 if not child else 8
        if acc == 'tie':
            px(cx - 1, ty, 15); px(cx + 1, ty, 15)
            rect(cx, ty, cx, ty + 4, 13)
        elif acc == 'apron':
            rect(cx - 2, ty + 3, cx + 1, tb, 13)
            if P['bottom'] == 'skirt' and not sit:
                rect(cx - 2, hip, cx + 1, hip + 3, 13)
            px(cx - 1, ty, 15); px(cx, ty, 15)
        elif acc == 'trim':
            rect(cx, ty, cx, tb, 13)
            rect(tx0, tb - 1, tx1, tb - 1, 13)
        elif acc == 'scarf':
            rect(cx - 1, ty, cx + 1, ty, 13)
            px(cx - 1, ty + 2, 15); px(cx + 1, ty + 2, 15); px(cx - 1, ty + 4, 15); px(cx + 1, ty + 4, 15)
        elif acc == 'stripe':
            rect(tx0 + 1, ty + 2, tx1, ty + 2, 13)
        elif acc == 'shirt':
            rect(cx - 1, ty, cx + 1, tb - 1, 13)
    else:
        if P['accent'] == 'apron':
            rect(7, ty + 3, 8, ty + 3, 13)
    # ---- arms
    aw = ty + (5 if not child else 3)       # hand row
    if use:
        # both forearms reaching forward at waist height (working at a counter or a stove)
        if not back:
            rect(tx1 - 1, ty + 4, tx1 + 2, ty + 4, 6)
            rect(tx1 + 2, ty + 4, tx1 + 3, ty + 4, 2)
            rect(tx1 - 2, ty + 5, tx1 + 1, ty + 5, 7)
            rect(tx1 + 1, ty + 5, tx1 + 2, ty + 5, 3)
            rect(tx0 - 1, ty + 1, tx0 - 1, ty + 3, 7)
        else:
            rect(tx0 - 1, ty + 1, tx0 - 1, ty + 4, 7)
            rect(tx1 + 1, ty + 1, tx1 + 1, ty + 3, 6)
            rect(tx1 + 2, ty + 3, tx1 + 2, ty + 4, 6)
    elif carry:
        # forearms forward, hands together in front of the chest
        if not back:
            rect(tx1 - 1, ty + 3, tx1 + 1, ty + 3, 6)
            rect(tx1, ty + 4, tx1 + 2, ty + 4, 2)
            rect(tx0 - 1, ty + 1, tx0 - 1, ty + 3, 7)
        else:
            rect(tx0 - 1, ty + 1, tx0 - 1, ty + 3, 7)
            rect(tx1 + 1, ty + 1, tx1 + 1, ty + 3, 6)
    elif sit:
        rect(tx0 - 1, ty + 1, tx0 - 1, ty + 4, 7)
        rect(tx1 + 1, ty + 1, tx1 + 1, ty + 3, 6)
        px(tx1 + 1, ty + 4, 2)
    else:
        sw = {'walk1': 1, 'walk3': -1}.get(pose, 0)
        for side, ax, s in ((-1, tx0 - 1, -sw), (1, tx1 + 1, sw)):
            hy2 = aw - (1 if s < 0 else 0)
            hx2 = ax + (s if s > 0 else 0) * (1 if not back else 0)
            rect(ax, ty + 1, ax, hy2 - 1, 7 if side < 0 else 6)
            px(hx2, hy2, 2)
    # ---- head
    rect(hx, hy, hx + 5, hy + 5, 2)
    px(hx, hy, 0); px(hx + 5, hy, 0)
    rect(hx + 1, hy + 6, hx + 4, hy + 6, 3)          # chin / neck
    hair = P['hair']
    if back:
        rect(hx, hy, hx + 5, hy + 5, 4)
        px(hx, hy, 0); px(hx + 5, hy, 0)
        rect(hx, hy + 3, hx + 1, hy + 5, 5)
        px(hx + 5, hy + 4, 2)                         # ear
        if hair == 'long':
            rect(hx - 1, hy + 2, hx + 5, hy + 8, 4)
            rect(hx - 1, hy + 5, hx, hy + 8, 5)
    else:
        rect(hx, hy, hx + 5, hy + 1, 4)
        px(hx, hy, 0); px(hx + 5, hy, 0)
        rect(hx, hy + 1, hx + 1, hy + 4, 4)           # back of the head (left)
        rect(hx, hy + 2, hx, hy + 4, 5)
        px(hx + 3, hy + 3, 14); px(hx + 5, hy + 3, 14)   # eyes, shifted to the facing side
        px(hx + 4, hy + 5, 3)
        if hair == 'long':
            rect(hx - 1, hy + 1, hx, hy + 8, 4)
            rect(hx - 1, hy + 5, hx - 1, hy + 8, 5)
    if hair == 'spiky':
        for x in range(hx - 1, hx + 7):
            if (x + hy) % 2 == 0:
                px(x, hy - 1, 4)
        rect(hx - 1, hy, hx + 6, hy, 4)
        px(hx - 1, hy - 2, 4); px(hx + 2, hy - 2, 4); px(hx + 5, hy - 2, 4)
        if not back:
            rect(hx + 2, hy + 3, hx + 5, hy + 3, 14)  # sunglasses
    hat = P['hat']
    if hat == 'cap':
        rect(hx, hy - 1, hx + 5, hy + 1, 11)
        rect(hx, hy + 1, hx + 5, hy + 1, 12)
        if not back:
            rect(hx + 4, hy + 1, hx + 7, hy + 1, 11)   # peak
    elif hat == 'toque':
        rect(hx - 1, hy - 2, hx + 6, hy, 11)
        rect(hx, hy - 3, hx + 5, hy - 3, 11)
        px(hx - 1, hy - 2, 0); px(hx + 6, hy - 2, 0)
        rect(hx, hy + 1, hx + 5, hy + 1, 12)
    return img


def outline(img, c=1):
    m = img > 0
    o = np.zeros_like(m)
    o[1:, :] |= m[:-1, :]; o[:-1, :] |= m[1:, :]; o[:, 1:] |= m[:, :-1]; o[:, :-1] |= m[:, 1:]
    out = img.copy()
    out[o & ~m] = c
    return out


def body_sheet(body):
    sheet = np.zeros((96, 16 * len(FRAMES)), np.uint8)
    for d in range(4):
        back = d >= 2
        mirror = d in (1, 2)
        for f, pose in enumerate(FRAMES):
            fr = _person(body, back, pose, 0)
            if mirror:
                fr = fr[:, ::-1]
            sheet[d * 24:(d + 1) * 24, f * 16:(f + 1) * 16] = outline(fr)
    return sheet


SHEETS = {}
for body, slot, u, v in (('man', 7, 0, 0), ('woman', 7, 0, 96), ('cap', 8, 0, 0), ('chef', 8, 0, 96),
                         ('child', 9, 0, 0), ('rocker', 9, 0, 96)):
    cell(slot, 'body_' + body, u, v, body_sheet(body))
    SHEETS[body] = (slot, u, v)

# ---- carry props (16 x 16) and a shadow blob, slot 7 from row 192; one shared palette
# indices: 1 outline, 2..4 white linen, 5..7 steel, 8 red, 9 dark red, 10 brown, 11 dark brown,
# 12 food yellow, 13 food green, 14 gold, 15 white highlight
PROP_ART = {
    'linen': [
        "................",
        "................",
        "................",
        "....11111111....",
        "...1444444441...",
        "..14333333334...",
        "..13222222223...",
        "..14444444441...",
        "..13333333331...",
        "..12222222221...",
        "..14444444441...",
        "..13333333331...",
        "...111111111....",
        "................",
        "................",
        "................"],
    'tray': [
        "................",
        "................",
        "................",
        "................",
        ".....1111.......",
        "....1fff11111...",
        "....1fff1c1d1...",
        "..11111111111...",
        ".1777777777771..",
        ".1566666666651..",
        "..11111111111...",
        "................",
        "................",
        "................",
        "................",
        "................"],
    'toolbox': [
        "................",
        "................",
        "................",
        "......1111......",
        ".....1....1.....",
        "....11111111....",
        "...1888888881...",
        "..199999999991..",
        "..18888ee88881..",
        "..18888888888...",
        "..19999999999...",
        "..111111111111..",
        "................",
        "................",
        "................",
        "................"],
    'luggage': [
        "................",
        "......1111......",
        ".....1....1.....",
        "..111111111111..",
        "..1aaaaaaaaaa1..",
        "..1abbbbbbbba1..",
        "..1abaaaaaaba1..",
        "..1abaaaaaaba1..",
        "..1eebbbbbbee1..",
        "..1abaaaaaaba1..",
        "..1abaaaaaaba1..",
        "..1abbbbbbbba1..",
        "..1aaaaaaaaaa1..",
        "..111111111111..",
        "...1........1...",
        "................"],
    'shadow': [
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "....11111111....",
        "..111111111111..",
        "..111111111111..",
        "....11111111....",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................"],
}
HEXMAP = {'.': 0, 'a': 10, 'b': 11, 'c': 12, 'd': 13, 'e': 14, 'f': 15}
PROPS = {}
for i, (nm, rows) in enumerate(PROP_ART.items()):
    a = np.array([[HEXMAP[ch] if ch in HEXMAP else int(ch) for ch in r] for r in rows], np.uint8)
    PROPS[nm] = cell(7, 'prop_' + nm, i * 16, 192, a)

# ---- palettes 96..127


def person_pal(name, skin, hair, top, bottom, shoes='2a2028', hat=None, band=None, accent=None, eyes='1a1418', white='ffffff'):
    sk, hr, tp, bt = hexc(skin), hexc(hair), hexc(top), hexc(bottom)
    hat = hexc(hat) if hat else tp
    band = hexc(band) if band else mul3(hat, 0.7)
    acc = hexc(accent) if accent else tp
    cols = [(34, 24, 34), sk, mul3(sk, 0.78), hr, mul3(hr, 0.7), tp, mul3(tp, 0.72), bt, mul3(bt, 0.72),
            hexc(shoes), hat, band, acc, hexc(eyes), hexc(white)]
    return palette('ppl_' + name, cols, 'ppl')


SKIN = ['f4c8a0', 'e0a878', 'b87850', '8a5432', 'f8d8c0']
PEOPLE = [   # kind, body, palette args
    ('receptionist', 'man', dict(skin=SKIN[0], hair='5a3a20', top='1e2e6a', bottom='1e2e6a', accent='d02a3a')),
    ('receptionist_f', 'woman', dict(skin=SKIN[2], hair='2a1a10', top='1e2e6a', bottom='1e2e6a', accent='1e2e6a')),
    ('housekeeper', 'woman', dict(skin=SKIN[1], hair='3a2414', top='9a7ac8', bottom='9a7ac8', accent='ffffff')),
    ('cook', 'chef', dict(skin=SKIN[0], hair='3a2a1a', top='f4f4f0', bottom='4a4a52', hat='ffffff', band='d8d8d8', accent='d02a3a')),
    ('waiter', 'man', dict(skin=SKIN[3], hair='1a1210', top='f4f4f0', bottom='18181c', accent='18181c')),
    ('bartender', 'man', dict(skin=SKIN[1], hair='6a3a1a', top='7a1a2c', bottom='18181c', accent='18181c')),
    ('spa_therapist', 'woman', dict(skin=SKIN[4], hair='c89a50', top='7ad0b0', bottom='7ad0b0', accent='f4f4f0')),
    ('bellhop', 'cap', dict(skin=SKIN[2], hair='2a1a10', top='c82a2a', bottom='1a1a24', hat='c82a2a', band='e8b830', accent='e8b830')),
    ('maintenance', 'cap', dict(skin=SKIN[0], hair='6a4a2a', top='e8782a', bottom='3a4a6a', hat='3a4a6a', band='2a3448', accent='f0d040')),
    ('security', 'cap', dict(skin=SKIN[3], hair='1a1210', top='22242c', bottom='22242c', hat='22242c', band='e8c040', accent='e8c040')),
    ('business_a', 'man', dict(skin=SKIN[0], hair='3a2a1a', top='6a6e78', bottom='5a5e68', accent='2a5aa8')),
    ('business_b', 'man', dict(skin=SKIN[3], hair='1a1210', top='1e2a48', bottom='1e2a48', accent='c8a040')),
    ('business_c', 'woman', dict(skin=SKIN[1], hair='5a2a14', top='3a3a44', bottom='3a3a44', accent='3a3a44')),
    ('family_a', 'man', dict(skin=SKIN[1], hair='8a5a2a', top='f07a5a', bottom='c8b080', accent='f07a5a')),
    ('family_b', 'woman', dict(skin=SKIN[0], hair='e8c070', top='f0d040', bottom='f0d040', accent='f0d040')),
    ('family_c', 'man', dict(skin=SKIN[2], hair='1a1210', top='30a8a0', bottom='3a5a9a', accent='30a8a0')),
    ('child_a', 'child', dict(skin=SKIN[0], hair='c88a40', top='e03a3a', bottom='2a5ab0', accent='ffffff')),
    ('child_b', 'child', dict(skin=SKIN[3], hair='1a1210', top='f0d030', bottom='3a9a4a', accent='3a9a4a')),
    ('child_c', 'child', dict(skin=SKIN[1], hair='6a3a1a', top='f080b0', bottom='8a5ab8', accent='ffffff')),
    ('honeymoon_a', 'woman', dict(skin=SKIN[4], hair='8a4a20', top='fcfcf8', bottom='fcfcf8', accent='fcfcf8')),
    ('honeymoon_b', 'man', dict(skin=SKIN[2], hair='2a1a10', top='d8d0c0', bottom='d8d0c0', accent='f8b8d0')),
    ('rockstar_a', 'rocker', dict(skin=SKIN[0], hair='a040e0', top='18181c', bottom='18181c', accent='e03a3a', eyes='101014')),
    ('rockstar_b', 'rocker', dict(skin=SKIN[2], hair='f0e060', top='b02020', bottom='18181c', accent='ffffff', eyes='101014')),
]
PERSON = {}
for kind, body, args in PEOPLE:
    PERSON[kind] = (body, person_pal(kind, **args))
PROP_PAL = palette('ppl_props', cols15({1: '1e1820', 2: 'f4f4f0', 3: 'c8c8d0', 4: 'fcfcf8', 5: '6a7078', 6: 'b8c0c8',
                                        7: 'e0e8f0', 8: 'd83a2a', 9: '8a1e18', 10: '7a4a2a', 11: '4a2a14',
                                        12: 'f0c040', 13: '5ab040', 14: 'e8c040', 15: 'ffffff'}), 'ppl')
GUEST_TYPES = [('business', ['business_a', 'business_b', 'business_c']), ('family', ['family_a', 'family_b', 'family_c']),
               ('child', ['child_a', 'child_b', 'child_c']), ('honeymooner', ['honeymoon_a', 'honeymoon_b']),
               ('rockstar', ['rockstar_a', 'rockstar_b'])]


def people_decls(L):
    A = L.append
    kinds = list(PERSON)
    A('')
    A('// ---- people: 16x24 billboard frames, 4-bit, feet on the frame\'s bottom row. A person kind k')
    A('// (ART_PK_*) has a sheet of 9 frame columns (ART_FR_* / ART_PPL_FRAME_*) by 4 direction rows')
    A('// (ART_DIR_* / ART_PPL_DIR_*): frame f, direction d is the 16x24 cell at')
    A('//   u = ART_PERSON_U[k] + f * 16, v = ART_PERSON_V[k] + d * 24 in slot ART_PERSON_SLOT[k],')
    A('// drawn with 4-bit palette ART_PERSON_PAL[k]. Directions are screen-relative: 0 toward the viewer')
    A('// facing screen-right, 1 toward the viewer facing screen-left, 2 away facing screen-left, 3 away')
    A('// facing screen-right (with the camera looking from +x+z: walking +z -> 0, +x -> 1, -z -> 2,')
    A('// -x -> 3). "use" has the arms forward (counter, stove); "swim" is head and shoulders, the frame\'s')
    A('// bottom rows are the water line.')
    A('const ART_PERSON_W = 16')
    A('const ART_PERSON_H = 24')
    A('const ART_PPL_FRAME_W = 16')
    A('const ART_PPL_FRAME_H = 24')
    A('const ART_PPL_NFRAMES = %d' % len(FRAMES))
    for i, f in enumerate(FRAMES):
        A('const ART_FR_%s = %d' % (f.upper(), i))
        A('const ART_PPL_FRAME_%s = %d' % (f.upper(), i))
    for i, d in enumerate(('FRONT_RIGHT', 'FRONT_LEFT', 'BACK_LEFT', 'BACK_RIGHT')):
        A('const ART_DIR_%s = %d' % (d, i))
        A('const ART_PPL_DIR_%s = %d' % (d, i))
    A('const ART_PERSON_COUNT = %d' % len(kinds))
    for i, k in enumerate(kinds):
        A('const ART_PK_%s = %d' % (k.upper(), i))
    A('const ART_PERSON_SLOT: [%d]u8 = [%s]' % (len(kinds), ', '.join(str(SHEETS[PERSON[k][0]][0]) for k in kinds)))
    A('const ART_PERSON_U: [%d]u8 = [%s]' % (len(kinds), ', '.join(str(SHEETS[PERSON[k][0]][1]) for k in kinds)))
    A('const ART_PERSON_V: [%d]u8 = [%s]' % (len(kinds), ', '.join(str(SHEETS[PERSON[k][0]][2]) for k in kinds)))
    A('const ART_PERSON_PAL: [%d]u8 = [%s]' % (len(kinds), ', '.join(str(PERSON[k][1]) for k in kinds)))
    A('// staff roles -> person kind, and per role: sheet slot, U0/V0 (frame 0, direction 0), palette')
    roles = ('receptionist', 'housekeeper', 'cook', 'waiter', 'bartender', 'spa_therapist', 'bellhop', 'maintenance', 'security')
    for role in roles:
        body, pal = PERSON[role]
        slot, u, v = SHEETS[body]
        R_ = role.upper()
        A('const ART_STAFF_%s = %d' % (R_, kinds.index(role)))
        A('const ART_PPL_%s_SLOT = %d' % (R_, slot))
        A('const ART_PPL_%s_U0 = %d' % (R_, u))
        A('const ART_PPL_%s_V0 = %d' % (R_, v))
        A('const ART_PPL_PAL_%s = %d' % (R_, pal))
    A('// guest types -> the first person kind and how many variants follow it; per variant n (1-based):')
    A('// ART_PPL_GUEST_<TYPE>_<n>_SLOT/_U0/_V0 and palette ART_PPL_PAL_GUEST_<TYPE>_<n>')
    for gt, ks in GUEST_TYPES:
        G_ = gt.upper()
        A('const ART_GUEST_%s = %d' % (G_, kinds.index(ks[0])))
        A('const ART_GUEST_%s_N = %d' % (G_, len(ks)))
        for n_, k in enumerate(ks, 1):
            body, pal = PERSON[k]
            slot, u, v = SHEETS[body]
            A('const ART_PPL_GUEST_%s_%d_SLOT = %d' % (G_, n_, slot))
            A('const ART_PPL_GUEST_%s_%d_U0 = %d' % (G_, n_, u))
            A('const ART_PPL_GUEST_%s_%d_V0 = %d' % (G_, n_, v))
            A('const ART_PPL_PAL_GUEST_%s_%d = %d' % (G_, n_, pal))
    A('// carry props and the shadow blob: 16x16, palette ART_PAL_PROPS (draw the shadow')
    A('// semi-transparent with blend mode 2, subtract)')
    A('const ART_PAL_PROPS = %d' % PROP_PAL)
    A('const ART_PROP_SLOT = %d' % PROPS['shadow'].slot)
    for nm, c in PROPS.items():
        A('const ART_PROP_%s_U = %d' % (nm.upper(), c.u))
        A('const ART_PROP_%s_V = %d' % (nm.upper(), c.v))


FINISHERS.append(people_decls)


# ============================================================================= baking
# Every object has a detailed "source" model (built above with materials from the slot 1 atlas)
# and a low-poly proxy: boxes, cards and a few kept faces (glass, water). Each proxy face gets a
# texture rendered orthographically from the source through that face, so the detail survives
# at a fraction of the triangles. Textures are quantized per object group to one 15-colour palette
# (relit by the game), and packed into texture slots 2..6.

HI_D, LO_D = 16.0, 8.0          # texels per unit for the full and the low-detail meshes
BAKE_MAX = 48                   # largest baked texture side
BAKE_SLOTS = [1, 2, 3, 4, 5, 6]


def BK(src=None, behind=True, double=False, D=None, glow=None):
    """Material of a proxy face: bake the source (faces tagged src, default all) onto it.
    behind: only source faces behind the proxy face's plane. glow: force emissive or not."""
    return Mat(col=(255, 0, 255), bake=dict(src=src, behind=behind, D=D, glow=glow), double=double)


def light_flat(n):
    ny = n[1]
    if ny > 0.6:
        return 0.96 + 0.06 * ny
    if ny < -0.6:
        return 0.50
    return 0.76 + 0.22 * ny + 0.04 * (n[0] * -0.6 + n[2] * 0.8)


def raster_tris(canvas, emis, tris):
    """tris: list of (pts2d[3], colour_fn(w0, w1, w2) -> (rgb array, mask array) , emissive)."""
    H, W, _ = canvas.shape
    ys, xs = np.mgrid[0:H, 0:W]
    xs = xs + 0.5
    ys = ys + 0.5
    for (P, fn, em) in tris:
        (x0, y0), (x1, y1), (x2, y2) = P
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12:
            continue
        bx0, bx1 = max(0, int(math.floor(min(x0, x1, x2)))), min(W, int(math.ceil(max(x0, x1, x2))) + 1)
        by0, by1 = max(0, int(math.floor(min(y0, y1, y2)))), min(H, int(math.ceil(max(y0, y1, y2))) + 1)
        if bx0 >= bx1 or by0 >= by1:
            continue
        X = xs[by0:by1, bx0:bx1]
        Y = ys[by0:by1, bx0:bx1]
        w0 = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / den
        w1 = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / den
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not m.any():
            continue
        rgb, ok = fn(w0, w1, w2)
        m = m & ok
        sub = canvas[by0:by1, bx0:bx1]
        sub[m, :3] = rgb[m]
        sub[m, 3] = 1.0
        emis[by0:by1, bx0:bx1][m] = em


def src_colour_fn(f, uv, rel):
    """Returns a function giving the source face's albedo (times rel) at barycentric weights."""
    mat = f.mat
    k = mat.k * rel
    if mat.cell is not None:
        idxatl = ATL[mat.cell.slot].idx
        pal = np.array(PAL[mat.pal], float)

        def fn(w0, w1, w2):
            u = w0 * uv[0][0] + w1 * uv[1][0] + w2 * uv[2][0]
            v = w0 * uv[0][1] + w1 * uv[1][1] + w2 * uv[2][1]
            ui = np.clip(np.floor(u).astype(int), 0, 255)
            vi = np.clip(np.floor(v).astype(int), 0, 255)
            idx = idxatl[vi, ui]
            return np.clip(pal[idx] * k, 0, 255), idx > 0
    else:
        col = np.array(mat.col, float) * k

        def fn(w0, w1, w2):
            out = np.empty(w0.shape + (3,))
            out[:] = np.clip(col, 0, 255)
            return out, np.ones(w0.shape, bool)
    return fn


def bake_face(pf, src, D):
    """Renders the source faces onto proxy face pf. Returns (rgba float HxWx4, emissive HxW)."""
    bk = pf.mat.bake
    D = bk['D'] or D
    n = pf.n
    R, U = face_axes(n)
    s = [v_dot(p, R) for p in pf.pts]
    t = [v_dot(p, U) for p in pf.pts]
    s0, s1, t0, t1 = min(s), max(s), min(t), max(t)
    W = max(1, int(round((s1 - s0) * D)))
    H = max(1, int(round((t1 - t0) * D)))
    if max(W, H) > BAKE_MAX:
        k = BAKE_MAX / max(W, H)
        W, H = max(1, int(round(W * k))), max(1, int(round(H * k)))
    ss = 3
    kx = W * ss / max(1e-6, s1 - s0)
    ky = H * ss / max(1e-6, t1 - t0)
    plane = max(v_dot(p, n) for p in pf.pts)
    cand = []
    for f in src:
        if f.mat.semi is not None or f.mat.bake is not None:
            continue
        if bk['src'] is not None and f.tag not in bk['src']:
            continue
        dn = v_dot(f.n, n)
        if dn <= 0.02 and not f.mat.double:
            continue
        c = v_mul(tuple(sum(p[i] for p in f.pts) for i in range(3)), 1.0 / len(f.pts))
        if bk['behind'] and v_dot(c, n) > plane + 0.03:
            continue
        cand.append((v_dot(c, n), f))
    cand.sort(key=lambda t_: t_[0])
    canvas = np.zeros((H * ss, W * ss, 4))
    emis = np.zeros((H * ss, W * ss), bool)
    tris = []
    lp = light_flat(n)
    for _, f in cand:
        uvs = face_uvs(f) if f.mat.cell is not None else None
        rel = 1.0 if f.mat.glow else max(0.62, min(1.3, light_flat(f.n) / lp))
        pts = f.pts
        idxs = [(0, 1, 2), (1, 2, 3)] if len(pts) == 4 else [(0, 1, 2)]
        for a, b_, c in idxs:
            P = [((v_dot(pts[i], R) - s0) * kx, (t1 - v_dot(pts[i], U)) * ky) for i in (a, b_, c)]
            uv = [uvs[i] for i in (a, b_, c)] if uvs else None
            tris.append((P, src_colour_fn(f, uv, rel), bool(f.mat.glow)))
    raster_tris(canvas, emis, tris)
    # downsample
    a = canvas.reshape(H, ss, W, ss, 4)
    cov = a[..., 3].mean(axis=(1, 3))
    wsum = a[..., 3].sum(axis=(1, 3))[..., None]
    rgb = (a[..., :3] * a[..., 3:4]).sum(axis=(1, 3)) / np.maximum(wsum, 1e-6)
    em = emis.reshape(H, ss, W, ss).mean(axis=(1, 3)) > 0.5
    out = np.concatenate([rgb, (cov >= 0.5)[..., None].astype(float)], -1)
    return out, em


def quantize_bakes(images, nemit=4, ncol=15):
    """images: list of (rgba, emissive). Returns (index images, palette cols[15], emit bits)."""
    norm = np.concatenate([img[..., :3][(img[..., 3] > 0) & ~em] for img, em in images] + [np.zeros((0, 3))], 0)
    glow = np.concatenate([img[..., :3][(img[..., 3] > 0) & em] for img, em in images] + [np.zeros((0, 3))], 0)
    E = 0 if len(glow) == 0 else min(nemit, max(1, len(np.unique(np.round(glow / 16), axis=0))))
    N = ncol - E

    def mc(px, k):
        if len(px) == 0 or k == 0:
            return np.zeros((0, 3))
        im = Image.fromarray(np.clip(px, 0, 255).astype(np.uint8)[None, :, :], 'RGB')
        q = im.quantize(k, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        pal = q.getpalette()[:k * 3]
        cols = np.array(pal, float).reshape(-1, 3)
        cols = cols[np.unique(np.asarray(q))]
        # a few k-means (Lloyd) steps in a perceptually weighted space
        w = np.array([0.30, 0.59, 0.11]) ** 0.5
        X = px[::max(1, len(px) // 20000)] * w
        Cc = cols * w
        for _ in range(8):
            d = ((X[:, None, :] - Cc[None, :, :]) ** 2).sum(-1)
            lab = d.argmin(1)
            for i in range(len(Cc)):
                m = lab == i
                if m.any():
                    Cc[i] = X[m].mean(0)
        return np.clip(Cc / w, 0, 255)
    cn = mc(norm, N)
    cg = mc(glow, E)
    cols = list(map(tuple, cn)) + list(map(tuple, cg))
    nn, ng = len(cn), len(cg)
    while len(cols) < ncol:
        cols.append((0, 0, 0))
    P = np.array(cols, float)
    wv = np.array([0.30, 0.59, 0.11])
    out = []
    for img, em in images:
        rgb = img[..., :3]
        d = (((rgb[..., None, :] - P[None, None, :, :]) ** 2) * wv).sum(-1)
        dn_ = d.copy()
        dn_[..., nn:] = 1e18
        idx = dn_.argmin(-1)
        if ng:
            dg = d.copy()
            dg[..., :nn] = 1e18
            dg[..., nn + ng:] = 1e18
            idx = np.where(em, dg.argmin(-1), idx)
        idx = (idx + 1).astype(np.uint8)
        idx[img[..., 3] <= 0] = 0
        out.append(idx)
    bits = 0
    for i in range(nn, nn + ng):
        bits |= 1 << (i + 1)
    return out, cols[:ncol], bits


def bbox(faces):
    xs = [p[0] for f in faces for p in f.pts]
    ys = [p[1] for f in faces for p in f.pts]
    zs = [p[2] for f in faces for p in f.pts]
    return min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)


class PX(B):
    """Proxy builder: baked boxes and cards, kept source faces."""

    def __init__(self, src):
        B.__init__(self)
        self.src = src

    def bx(self, x0, y0, z0, x1, y1, z1, skip='b', src=None, behind=True, glow=None, D=None):
        self.box(x0, y0, z0, x1, y1, z1, BK(src, behind, D=D, glow=glow), skip=skip)

    def card(self, x0, z0, x1, z1, y0, y1, src=None, behind=False, glow=None, D=None):
        """A two-sided vertical card from (x0, z0) to (x1, z1), baked from its front side."""
        n = v_norm((z1 - z0, 0.0, -(x1 - x0)))
        # make the front face the viewer-facing side for the default camera (+x, +z)
        if n[0] + n[2] < 0:
            n = v_mul(n, -1)
        self.quad((x0, y0, z0), (x1, y0, z1), (x0, y1, z0), (x1, y1, z1), BK(src, behind, double=True, D=D, glow=glow), n)

    def cross(self, cx, cz, hw, y0, y1, src=None, glow=None, D=None):
        self.card(cx - hw, cz, cx + hw, cz, y0, y1, src, glow=glow, D=D)
        self.card(cx, cz - hw, cx, cz + hw, y0, y1, src, glow=glow, D=D)

    def top(self, x0, z0, x1, z1, y, src=None, behind=False, glow=None, D=None):
        self.quad((x1, y, z1), (x0, y, z1), (x1, y, z0), (x0, y, z0), BK(src, behind, D=D, glow=glow), (0, 1, 0))

    def q(self, a, b_, c, d, n=None, src=None, behind=True, double=False, glow=None):
        self.quad(a, b_, c, d, BK(src, behind, double=double, glow=glow), n)

    def t(self, a, b_, c, n=None, src=None, behind=True, double=False, glow=None):
        self.tri(a, b_, c, BK(src, behind, double=double, glow=glow), n)

    def prism_b(self, poly, y0, y1, src=None, cap=True, behind=True):
        self.prism(poly, y0, y1, BK(src, behind), cap=cap)

    def keep(self, pred):
        for f in self.src:
            if pred(f):
                self.faces.append(Face(list(f.pts), f.n, f.mat, f.shade, f.tag))

    def keep_glass(self):
        self.keep(lambda f: f.mat.semi is not None)

    def keep_water(self):
        self.keep(lambda f: f.mat.cell is not None and f.mat.cell.name == 'f4_pool_water')


def lo_box(src, box=None, D=LO_D):
    x0, y0, z0, x1, y1, z1 = box or bbox(src)
    p = PX(src)
    p.bx(x0, max(0.0, y0), z0, x1, y1, z1, D=D)
    return p.faces


def lo_back(src, low_h, back_z0, back_z1, back_h, D=LO_D):
    """Low-detail bed/sofa/chair: a low box and a card for the tall back (10 triangles)."""
    x0, y0, z0, x1, y1, z1 = bbox(src)
    p = PX(src)
    p.bx(x0, 0.0, back_z1, x1, low_h, z1, skip='bk', D=D)
    p.box(x0, 0.0, back_z0, x1, back_h, back_z1, BK(double=True, D=D), skip='btlrk')
    return p.faces


def lo_cross(src, top=True, D=LO_D, cx=0.0, cz=0.0):
    x0, y0, z0, x1, y1, z1 = bbox(src)
    p = PX(src)
    hw = max(x1 - x0, z1 - z0) / 2
    p.cross(cx, cz, hw, max(0.0, y0), y1, D=D)
    if top:
        p.top(cx - hw, cz - hw, cx + hw, cz + hw, y1 - 0.02, D=D)
    return p.faces


class Packer:
    """Shelf packer over texture slots; each rect gets a 1-texel gutter (edges duplicated)."""

    def __init__(self, slots):
        self.slots = list(slots)
        self.si = 0
        self.x = self.y = self.rowh = 0

    def place(self, img, name):
        h, w = img.shape
        H, W = h + 2, w + 2
        while True:
            if self.si >= len(self.slots):
                raise RuntimeError('bake atlas full')
            if self.x + W > 256:
                self.x = 0
                self.y += self.rowh
                self.rowh = 0
            if self.y + H > 256:
                self.si += 1
                self.x = self.y = self.rowh = 0
                continue
            break
        slot = self.slots[self.si]
        pad = np.pad(img, 1, mode='edge')
        ATL.setdefault(slot, Atlas(slot))
        ATL[slot].idx[self.y:self.y + H, self.x:self.x + W] = pad
        ATL[slot].used = max(ATL[slot].used, self.y + H)
        c = Cell(name, slot, self.x + 1, self.y + 1, w, h)
        self.x += W
        self.rowh = max(self.rowh, H)
        return c


# ============================================================================= proxies
# PROXY[key](src) -> (proxy faces, low-detail faces or None for the bounding box)
PROXY = {}


def proxy(*keys):
    def deco(fn):
        for k in keys:
            PROXY[k] = fn
        return fn
    return deco


def p_chair(p, x, z, yaw, w=0.38, seat_h=0.46, back_h=0.92, sides=False):
    st = p.mark()
    hw = w / 2
    p.bx(-hw, 0.0, -hw, hw, seat_h, hw, skip='bk' if sides else 'bklr')
    p.card(-hw, -hw, hw, -hw, seat_h, back_h)
    p.rot_y(st, yaw)
    p.move(st, x, 0, z)


def p_bed(src, hw, hz, head):
    p = PX(src)
    p.bx(-hw, 0.0, -hz + 0.12, hw, 0.53, hz, skip='bk')
    p.bx(-hw + 0.08, 0.53, -hz + 0.14, hw - 0.08, 0.68, -hz + 0.54, skip='bk')
    p.bx(-hw - 0.05, 0.0, -hz - 0.01, hw + 0.05, head, -hz + 0.12)
    return p.faces, lo_back(src, 0.62, -hz - 0.01, -hz + 0.12, head)


PROXY['bed_single'] = lambda s: p_bed(s, 0.46, 0.97, 1.18)
PROXY['bed_double'] = lambda s: p_bed(s, 0.92, 0.97, 1.18)
PROXY['bed_king'] = lambda s: p_bed(s, 0.96, 0.97, 1.62)


def p_lamp(p, x, z, y, h=0.42, r=0.15):
    p.card(x - 0.08, z, x + 0.08, z, y, y + h * 0.5, behind=False)
    p.cyl(x, z, r * 1.05, y + h * 0.46, y + h + 0.01, 4, BK(behind=False), r1=r * 0.75, rot=math.pi / 4)


@proxy('nightstand')
def _(s):
    p = PX(s)
    p.bx(-0.26, 0.0, -0.30, 0.26, 0.56, 0.14)
    p_lamp(p, 0.0, -0.10, 0.56)
    return p.faces, None


@proxy('phone')
def _(s):
    p = PX(s)
    p.bx(-0.26, 0.0, -0.26, 0.26, 0.58, 0.20)
    p.bx(-0.14, 0.58, -0.15, 0.14, 0.72, 0.09)
    return p.faces, None


@proxy('modem')
def _(s):
    p = PX(s)
    p.bx(-0.34, 0.0, -0.28, 0.34, 0.70, 0.18)
    p.bx(-0.17, 0.70, -0.17, 0.17, 0.77, 0.08)
    return p.faces, None


@proxy('tv')
def _(s):
    p = PX(s)
    p.bx(-0.45, 0.0, -0.30, 0.45, 0.45, 0.20)
    p.bx(-0.28, 0.45, -0.49, 0.28, 0.91, 0.15)
    return p.faces, None


@proxy('desk')
def _(s):
    p = PX(s)
    p.bx(-0.46, 0.0, -0.36, 0.46, 0.77, 0.24)
    p_lamp(p, 0.30, -0.20, 0.76, h=0.36, r=0.10)
    return p.faces, None


@proxy('chair')
def _(s):
    p = PX(s)
    p_chair(p, 0.0, 0.0, 0.0, w=0.44, seat_h=0.48, back_h=0.96, sides=True)
    return p.faces, lo_back(s, 0.48, -0.23, -0.15, 0.96)


@proxy('minibar')
def _(s):
    p = PX(s)
    p.bx(-0.28, 0.0, -0.30, 0.28, 0.62, 0.25)
    p.bx(-0.21, 0.62, -0.14, 0.19, 0.77, 0.03)
    return p.faces, None


@proxy('floor_lamp')
def _(s):
    p = PX(s)
    p.cyl(0, 0, 0.27, 1.22, 1.62, 4, BK(), r1=0.19, rot=math.pi / 4)
    p.cross(0.0, 0.0, 0.18, 0.0, 1.24)
    return p.faces, lo_cross(s)


def p_sofa(s, hw, hd, back_h, arm_h, seat_h=0.44, arm_w=0.14):
    p = PX(s)
    p.bx(-hw, 0.0, -hd, hw, back_h, -hd + 0.2)
    p.bx(-hw + arm_w, 0.0, -hd + 0.2, hw - arm_w, seat_h, hd, skip='bklr')
    for sx in (-1, 1):
        x0 = -hw if sx < 0 else hw - arm_w
        p.bx(x0, 0.0, -hd + 0.2, x0 + arm_w, arm_h, hd, skip='bk')
    return p.faces, lo_back(s, arm_h, -hd, -hd + 0.2, back_h)


PROXY['sofa'] = lambda s: p_sofa(s, 0.93, 0.43, 0.86, 0.62)
PROXY['waiting_sofa'] = lambda s: p_sofa(s, 0.93, 0.43, 0.80, 0.72)
PROXY['lounge_chair'] = lambda s: p_sofa(s, 0.43, 0.40, 0.86, 0.64)


@proxy('toilet')
def _(s):
    p = PX(s)
    p.bx(-0.20, 0.0, -0.43, 0.20, 0.84, -0.24)
    p.bx(-0.20, 0.0, -0.24, 0.20, 0.44, 0.20, skip='bk')
    return p.faces, None


@proxy('shower')
def _(s):
    p = PX(s)
    p.bx(-0.48, 0.0, -0.48, 0.48, 0.10, 0.48)
    p.card(-0.48, -0.44, 0.48, -0.44, 0.10, 2.2, behind=True)
    p.keep_glass()
    return p.faces, None


@proxy('bathtub')
def _(s):
    p = PX(s)
    hw, hz, H = 0.44, 0.95, 0.58
    p.bx(-hw, 0.0, -hz, hw, H, hz, skip='bt')
    t = 0.07
    for (x0, z0, x1, z1) in ((-hw, -hz, hw, -hz + t), (-hw, hz - t, hw, hz), (-hw, -hz + t, -hw + t, hz - t), (hw - t, -hz + t, hw, hz - t)):
        p.top(x0, z0, x1, z1, H, behind=True)
    p.keep_water()
    return p.faces, None


@proxy('sink')
def _(s):
    p = PX(s)
    p.bx(-0.40, 0.0, -0.40, 0.40, 0.90, 0.15)
    p.card(-0.36, -0.40, 0.36, -0.40, 1.08, 1.82)
    return p.faces, None


def p_tub(s, R, H, steps):
    p = PX(s)
    oct8 = p.ring(0, 0, R, 8, rot=math.pi / 8)
    p.prism_b(oct8, 0.0, H, cap=False)
    inner = p.ring(0, 0, R - 0.12, 8, rot=math.pi / 8)
    for i in range(8):
        j = (i + 1) % 8
        a, c = oct8[i], oct8[j]
        q, r = inner[i], inner[j]
        p.q((a[0], H + 0.03, a[1]), (c[0], H + 0.03, c[1]), (q[0], H + 0.03, q[1]), (r[0], H + 0.03, r[1]), (0, 1, 0))
    p.keep_water()
    if steps:
        p.bx(*steps)
    return p.faces, None


PROXY['jacuzzi'] = lambda s: p_tub(s, 0.95, 0.55, (-0.45, 0.0, 0.87, 0.45, 0.25, 0.99))
PROXY['hot_tub'] = lambda s: p_tub(s, 0.92, 0.82, (-0.35, 0.0, 0.67, 0.35, 0.55, 1.0))


@proxy('reception_desk')
def _(s):
    p = PX(s)
    p.bx(-1.50, 0.0, 0.02, 1.50, 1.10, 0.48)
    p.bx(-1.44, 0.0, -0.44, 1.44, 0.74, 0.02, skip='bf')
    for x in (-0.7, 0.7):
        p.bx(x - 0.17, 0.74, -0.47, x + 0.17, 1.09, -0.04)
    return p.faces, None


@proxy('key_rack')
def _(s):
    p = PX(s)
    p.bx(-0.46, 0.0, -0.48, 0.46, 0.92, -0.10)
    p.bx(-0.45, 1.05, -0.49, 0.45, 2.12, -0.32)
    return p.faces, None


@proxy('concierge_desk')
def _(s):
    p = PX(s)
    p.bx(-0.89, 0.0, -0.33, 0.89, 1.06, 0.33)
    p_lamp(p, -0.55, -0.08, 1.04, h=0.40, r=0.11)
    return p.faces, None


@proxy('coffee_table')
def _(s):
    p = PX(s)
    p.bx(-0.40, 0.0, -0.40, 0.40, 0.42, 0.40)
    p.cross(0.18, -0.15, 0.08, 0.42, 0.67)
    return p.faces, None


@proxy('plant')
def _(s):
    p = PX(s)
    p.bx(-0.25, 0.0, -0.25, 0.25, 0.48, 0.25)
    p.cross(0.0, 0.0, 0.62, 0.48, 1.30)
    return p.faces, lo_cross(s)


@proxy('luggage_cart')
def _(s):
    p = PX(s)
    p.bx(-0.44, 0.0, -0.26, 0.44, 0.16, 0.26)
    p.bx(-0.34, 0.16, -0.18, 0.30, 1.04, 0.18)
    for sx in (-1, 1):
        p.card(sx * 0.42, -0.06, sx * 0.42, 0.06, 0.16, 1.55, src=None, behind=False)
    p.bx(-0.47, 1.54, -0.04, 0.47, 1.63, 0.04)
    return p.faces, None


@proxy('table_2')
def _(s):
    p = PX(s)
    p.bx(-0.30, 0.0, -0.30, 0.30, 0.74, 0.30)
    p_chair(p, -0.40, 0.0, math.pi / 2, w=0.30, back_h=0.86, sides=True)
    p_chair(p, 0.40, 0.0, -math.pi / 2, w=0.30, back_h=0.86, sides=True)
    return p.faces, None


@proxy('table_4')
def _(s):
    p = PX(s)
    p.bx(-0.50, 0.0, -0.50, 0.50, 0.77, 0.50)
    for k in range(4):
        a = k * math.pi / 2
        p_chair(p, 0.70 * math.sin(a), 0.70 * math.cos(a), a + math.pi)
    return p.faces, None


@proxy('staff_table')
def _(s):
    p = PX(s)
    p.bx(-0.50, 0.0, -0.40, 0.50, 0.87, 0.40)
    for k in range(4):
        a = k * math.pi / 2
        r = 0.66 if k % 2 == 0 else 0.76
        p_chair(p, r * math.sin(a), r * math.cos(a), a + math.pi)
    return p.faces, None


@proxy('conf_table')
def _(s):
    p = PX(s)
    p.bx(-1.25, 0.0, -0.46, 1.25, 0.79, 0.46)
    for x in (-0.75, 0.0, 0.75):
        for sz in (-1, 1):
            p_chair(p, x, sz * 0.74, 0.0 if sz < 0 else math.pi, w=0.42, back_h=0.92)
    return p.faces, None


@proxy('buffet')
def _(s):
    p = PX(s)
    p.bx(-1.48, 0.0, -0.42, 1.48, 0.89, 0.34)
    p.bx(-1.22, 0.89, -0.42, 1.22, 1.05, -0.18, skip='bk')
    p.keep_glass()
    return p.faces, None


@proxy('bar_stool')
def _(s):
    p = PX(s)
    p.bx(-0.20, 0.70, -0.20, 0.20, 0.80, 0.20)
    p.cross(0.0, 0.0, 0.20, 0.0, 0.70)
    return p.faces, None


@proxy('bar_shelf')
def _(s):
    p = PX(s)
    p.bx(-0.97, 0.0, -0.48, 0.97, 0.94, -0.04)
    p.bx(-0.99, 0.94, -0.50, 0.99, 2.38, -0.20, skip='b')
    return p.faces, None


@proxy('piano')
def _(s):
    p = PX(s)
    body = [(0.74, 0.42), (0.74, -0.78), (0.58, -0.94), (0.30, -0.95), (0.06, -0.80), (-0.22, -0.45),
            (-0.52, -0.12), (-0.72, 0.12), (-0.74, 0.42)]
    p.extrude(body, 0.0, 0.99, BK(), top=BK())
    st = p.mark()
    p.fill(body, 0.995, BK(double=True, behind=False, src=['lid']))
    p.rot(st, 'z', -0.55, origin=(0.74, 0.995, 0.0))
    p.bx(-0.74, 0.0, 0.42, 0.74, 0.86, 0.70, skip='bk')
    p.bx(-0.40, 0.0, 0.76, 0.40, 0.48, 0.98)
    return p.faces, None


@proxy('stove')
def _(s):
    p = PX(s)
    p.bx(-0.42, 0.0, -0.36, 0.42, 0.88, 0.32)
    p.bx(-0.42, 0.88, -0.40, 0.42, 1.10, -0.32)
    p.bx(-0.33, 0.88, 0.01, -0.09, 1.04, 0.25)
    return p.faces, None


@proxy('dishwasher')
def _(s):
    p = PX(s)
    p.bx(-0.44, 0.0, -0.38, 0.44, 0.90, 0.32)
    p.bx(-0.36, 0.90, -0.30, 0.36, 1.66, 0.30)
    return p.faces, None


@proxy('kitchen_sink')
def _(s):
    p = PX(s)
    p.bx(-0.46, 0.0, -0.38, 0.46, 0.90, 0.32)
    p.cross(0.0, -0.24, 0.12, 0.90, 1.33)
    return p.faces, None


@proxy('washer', 'dryer')
def _(s):
    p = PX(s)
    p.bx(-0.38, 0.0, -0.36, 0.38, 1.02, 0.32)
    return p.faces, None


@proxy('folding_table')
def _(s):
    p = PX(s)
    p.bx(-0.95, 0.0, -0.36, 0.95, 0.90, 0.36)
    p.bx(-0.73, 0.90, -0.24, 0.90, 1.12, 0.22)
    return p.faces, None


@proxy('sauna')
def _(s):
    p = PX(s)
    p.bx(-1.50, 0.0, -1.50, 1.50, 2.42, 1.50)
    p.bx(-0.30, 0.0, 1.55, 0.35, 0.42, 1.95)
    p.cross(-0.9, -0.9, 0.11, 2.42, 2.85)
    return p.faces, None


@proxy('towel_rack')
def _(s):
    p = PX(s)
    p.cross(0.0, -0.10, 0.42, 0.0, 1.42)
    return p.faces, lo_cross(s, top=False)


@proxy('treadmill')
def _(s):
    p = PX(s)
    p.bx(-0.36, 0.0, -0.70, 0.36, 0.21, 0.92)
    p.bx(-0.37, 0.21, -0.92, 0.37, 1.47, -0.66, skip='b')
    return p.faces, None


@proxy('weights')
def _(s):
    p = PX(s)
    p.bx(-0.20, 0.0, -0.40, 0.20, 0.50, 0.45)
    p.card(-0.95, -0.40, 0.95, -0.40, 0.0, 1.25, behind=False)
    p.bx(0.55, 0.0, -0.05, 0.95, 0.42, 0.40)
    return p.faces, None


@proxy('lounger')
def _(s):
    p = PX(s)
    p.bx(-0.33, 0.0, -0.30, 0.33, 0.37, 0.92)
    p.bx(-0.33, 0.0, -0.92, 0.33, 0.80, -0.30)
    return p.faces, None


@proxy('umbrella')
def _(s):
    p = PX(s)
    n = 8
    R = 1.05
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        p0 = (R * math.cos(a0), 1.82, R * math.sin(a0))
        p1 = (R * math.cos(a1), 1.82, R * math.sin(a1))
        nn = face_normal([p0, p1, (0, 2.28, 0)])
        if nn[1] < 0:
            nn = v_mul(nn, -1)
        p.t(p0, p1, (0, 2.36, 0), nn, double=True)
    p.cross(0.0, 0.0, 0.22, 0.0, 1.85)
    return p.faces, lo_cross(s)


@proxy('projector')
def _(s):
    p = PX(s)
    p.bx(-0.48, 0.95, -0.20, 0.48, 2.10, -0.10)
    p.cross(0.0, -0.15, 0.34, 0.0, 0.98)
    return p.faces, None


@proxy('lectern')
def _(s):
    p = PX(s)
    p.bx(-0.30, 0.0, -0.30, 0.30, 1.15, 0.24)
    p.cross(0.16, 0.08, 0.06, 1.15, 1.34)
    return p.faces, None


@proxy('window')
def _(s):
    p = PX(s)
    p.bx(-0.5, 0.0, -0.13, 0.5, 2.75, 0.15)
    p.keep_glass()
    return p.faces, None


@proxy('stairs')
def _(s):
    p = PX(s)
    hw = 0.94
    steps = 6
    run = 4.0 / steps
    h = 3.0 / steps
    for i in range(steps):
        z1 = 2.0 - i * run
        z0 = z1 - run
        p.q((hw, i * h, z1), (-hw, i * h, z1), (hw, (i + 1) * h, z1), (-hw, (i + 1) * h, z1), (0, 0, 1))
        p.top(-hw, z0, hw, z1, (i + 1) * h, behind=True)
    for sx in (-1, 1):
        x = sx * 1.0
        p.q((x, 0.0, 2.0), (x, 0.0, -2.0), (x, 0.40, 2.0), (x, 3.15, -2.0), (sx, 0, 0))
        p.q((x, 0.40, 2.0), (sx * hw, 0.40, 2.0), (x, 3.15, -2.0), (sx * hw, 3.15, -2.0), v_norm((0, 4.0, 2.75)))
    p.q((-1.0, 0.0, -2.0), (1.0, 0.0, -2.0), (-1.0, 3.0, -2.0), (1.0, 3.0, -2.0), (0, 0, -1))
    p.keep_glass()
    return p.faces, None


@proxy('grand_staircase')
def _(s):
    p = PX(s)
    steps = 6
    zb, zt = 3.0, -2.4
    run = (zb - zt) / steps
    h = 3.0 / steps
    for i in range(steps):
        z1 = zb - i * run
        z0 = z1 - run
        hw = 1.48 if i == 0 else 1.18
        p.q((hw, i * h, z1), (-hw, i * h, z1), (hw, (i + 1) * h, z1), (-hw, (i + 1) * h, z1), (0, 0, 1))
        p.top(-hw, z0, hw, z1, (i + 1) * h, behind=True)
        if i == 0:
            for sx in (-1, 1):
                p.q((sx * hw, 0.0, z1), (sx * hw, 0.0, z0), (sx * hw, h, z1), (sx * hw, h, z0), (sx, 0, 0))
    p.top(-1.18, -3.0, 1.18, zt, 3.0, behind=True)
    zs = zb - run
    y0 = h
    for sx in (-1, 1):
        xo, xi = sx * 1.42, sx * 1.18
        p.q((xo, 0.0, zs), (xo, 0.0, -3.0), (xo, y0 + 0.9, zs), (xo, 3.9, -3.0), (sx, 0, 0))
        p.q((xi, y0, zs), (xi, 3.0, -3.0), (xi, y0 + 0.9, zs), (xi, 3.9, -3.0), (-sx, 0, 0))
        p.q((xo, y0 + 0.9, zs), (xi, y0 + 0.9, zs), (xo, 3.9, -3.0), (xi, 3.9, -3.0), v_norm((0, 1, (3.9 - y0 - 0.9) / (zs + 3.0))))
        p.q((xi, 0.0, zs), (xo, 0.0, zs), (xi, y0 + 0.9, zs), (xo, y0 + 0.9, zs), (0, 0, 1))
        p.cross(sx * 1.30, zb - 2 * 5.4 / 12, 0.16, 0.0, 1.56)
    p.q((-1.42, 0.0, -3.0), (1.42, 0.0, -3.0), (-1.42, 3.0, -3.0), (1.42, 3.0, -3.0), (0, 0, -1))
    return p.faces, None


@proxy('glass_elevator')
def _(s):
    p = PX(s)
    p.bx(-1.0, 0.0, -1.01, 1.0, 3.0, 1.0, skip='bt')
    p.keep_glass()
    return p.faces, None


@proxy('glass_elevator_cab')
def _(s):
    p = PX(s)
    p.bx(-0.86, 0.0, -0.86, 0.86, 0.14, 0.86)
    p.bx(-0.90, 2.30, -0.90, 0.90, 2.56, 0.90, skip='')
    p.keep_glass()
    return p.faces, None


@proxy('chandelier')
def _(s):
    p = PX(s)
    p.card(-0.06, 0.0, 0.06, 0.0, 1.0, 2.75, src=['frame'], behind=False)
    ring = p.ring(0, 0, 0.95, 8, rot=math.pi / 8)
    p.prism(ring, 0.10, 1.06, BK(src=['frame'], behind=False), cap=False)
    p.poly_top(ring, 1.06, BK(src=['frame'], behind=False))
    p.cone(0, 0, 0.58, 0.10, -1.5, 6, BK(src=['crystal'], behind=False, double=True))
    return p.faces, lo_cross(s, top=False)


@proxy('skylight')
def _(s):
    p = PX(s)
    p.bx(-0.98, 2.75, -0.98, 0.98, 3.02, 0.98, skip='bt')
    p.keep_glass()
    return p.faces, None


@proxy('indoor_tree')
def _(s):
    p = PX(s)
    p.bx(-0.88, 0.0, -0.88, 0.88, 0.62, 0.88)
    p.cross(0.0, 0.0, 0.64, 0.62, 3.4, src=None)
    for (cx, cy, cz, r) in ((0.0, 4.55, 0.0, 1.10), (0.68, 3.75, 0.40, 0.80), (-0.62, 3.95, -0.45, 0.82)):
        top = (cx, cy + r * 0.80, cz)
        bot = (cx, cy - r * 0.65, cz)
        ring = [(cx + r * math.cos(a), cy, cz + r * math.sin(a)) for a in [k * math.pi / 3 for k in range(6)]]
        for i in range(6):
            a, b_ = ring[i], ring[(i + 1) % 6]
            nu = face_normal([a, b_, top])
            if nu[1] < 0:
                nu = v_mul(nu, -1)
            p.t(a, b_, top, nu, behind=False)
            nd = face_normal([a, b_, bot])
            if nd[1] > 0:
                nd = v_mul(nd, -1)
            p.t(a, b_, bot, nd, behind=False)
    return p.faces, lo_cross(s)


@proxy('fountain')
def _(s):
    p = PX(s)
    R = 0.95
    oct8 = p.ring(0, 0, R, 8, rot=math.pi / 8)
    p.prism_b(oct8, 0.0, 0.45, cap=False)
    inner = p.ring(0, 0, R - 0.12, 8, rot=math.pi / 8)
    for i in range(8):
        j = (i + 1) % 8
        a, c = oct8[i], oct8[j]
        q, r = inner[i], inner[j]
        p.q((a[0], 0.45, a[1]), (c[0], 0.45, c[1]), (q[0], 0.45, q[1]), (r[0], 0.45, r[1]), (0, 1, 0))
    p.cyl(0, 0, 0.14, 0.36, 1.18, 4, BK(), r1=0.44, cap=False, rot=math.pi / 4)
    p.keep_water()
    p.keep_glass()
    return p.faces, None


@proxy('railing')
def _(s):
    p = PX(s)
    p.card(-0.5, 0.46, 0.5, 0.46, 0.0, 0.97, behind=False)
    p.bx(-0.5, 0.96, 0.41, 0.5, 1.04, 0.51, skip='blr')
    lo = PX(s)
    lo.card(-0.5, 0.46, 0.5, 0.46, 0.0, 1.04, behind=False, D=LO_D)
    return p.faces, lo.faces


@proxy('railing_glass')
def _(s):
    p = PX(s)
    p.bx(-0.5, 0.0, 0.44, 0.5, 0.08, 0.50, skip='blr')
    p.bx(-0.5, 1.0, 0.435, 0.5, 1.06, 0.505, skip='blr')
    p.keep_glass()
    lo = PX(s)
    lo.keep_glass()
    lo.bx(-0.5, 1.0, 0.435, 0.5, 1.06, 0.505, skip='blr', D=LO_D)
    return p.faces, lo.faces


@proxy('arcade')
def _(s):
    p = PX(s)
    p.bx(-0.37, 0.0, -0.36, 0.37, 1.95, 0.30)
    p.bx(-0.37, 0.90, 0.30, 0.37, 1.10, 0.43, skip='bk')
    return p.faces, None


@proxy('palm')
def _(s):
    p = PX(s)
    p.cross(0.2, 0.05, 0.25, 0.0, 2.7)
    n = 6
    R = 1.25
    tx, ty, tz = 0.42, 2.85, 0.10
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        p0 = (tx + R * math.cos(a0), ty - 0.55, tz + R * math.sin(a0))
        p1 = (tx + R * math.cos(a1), ty - 0.55, tz + R * math.sin(a1))
        nn = face_normal([p0, p1, (tx, ty + 0.35, tz)])
        if nn[1] < 0:
            nn = v_mul(nn, -1)
        p.t(p0, p1, (tx, ty + 0.35, tz), nn, behind=False, double=True)
    return p.faces, lo_cross(s, cx=0.2, cz=0.05)


@proxy('coffee_machine')
def _(s):
    p = PX(s)
    p.bx(-0.44, 0.0, -0.38, 0.44, 0.92, 0.25)
    p.bx(-0.31, 0.92, -0.33, 0.39, 1.38, 0.13)
    return p.faces, None


@proxy('jukebox', 'wardrobe', 'fridge', 'locker', 'vending', 'elevator', 'door', 'door_frame', 'door_leaf',
       'linen_shelf', 'storage_shelf', 'prep_counter', 'bar_counter', 'cot', 'massage_bed')
def _(s):
    x0, y0, z0, x1, y1, z1 = bbox(s)
    p = PX(s)
    p.bx(x0, 0.0, z0, x1, y1, z1)
    return p.faces, None


# ============================================================================= icons and UI (slot 10)
# Build-menu icons are rendered from the meshes themselves (same iso angle as the game), 24x24,
# with a dark outline and a 15-colour palette shared by each category.

ICON = 24
ISO_YAW, ISO_PITCH = math.radians(225), math.radians(-35)


def _iso_axes():
    sy, cy, sp, cp = math.sin(ISO_YAW), math.cos(ISO_YAW), math.sin(ISO_PITCH), math.cos(ISO_PITCH)
    return (cy, 0.0, -sy), (-sy * sp, cp, -cy * sp), (sy * cp, sp, cy * cp)


def texel_rgb(cell_slot, pal, u, v):
    i = ATL[cell_slot].idx[v & 255, u & 255]
    return i, PAL[pal][i]


def render_faces(faces, size=96, margin=3, scale=None, centre=None, bg=None, fit=None):
    """Software render (orthographic iso, painter's sort like the console). Returns RGBA float."""
    R, U, F = _iso_axes()
    tris = []
    for f in faces:
        vis = v_dot(f.n, F) < 0 or f.mat.double
        if not vis:
            continue
        uvs = face_uvs(f) if f.mat.cell is not None else None
        cols = face_colours(f)
        pts = f.pts
        idxs = [(0, 1, 2), (1, 2, 3)] if len(pts) == 4 else [(0, 1, 2)]
        depth = sum(v_dot(p, F) for p in pts) / len(pts)
        tris.append((depth, f, [(pts[a], pts[b], pts[c]) for a, b, c in idxs],
                     [(uvs[a], uvs[b], uvs[c]) if uvs else None for a, b, c in idxs],
                     [(cols[a], cols[b], cols[c]) for a, b, c in idxs]))
    allp = [p for t in tris for tri in t[2] for p in tri]
    if fit is not None:
        allp = [p for f in fit for p in f.pts]
    if not allp:
        return np.zeros((size, size, 4))
    sx = [v_dot(p, R) for p in allp]
    sy = [-v_dot(p, U) for p in allp]
    if scale is None:
        ext = max(max(sx) - min(sx), max(sy) - min(sy))
        scale = (size - 2 * margin) / ext
    if centre is None:
        centre = ((max(sx) + min(sx)) / 2, (max(sy) + min(sy)) / 2)
    img = np.zeros((size, size, 4))
    if bg is not None:
        img[:, :, :3] = bg
    tris.sort(key=lambda t: -t[0])
    ys, xs = np.mgrid[0:size, 0:size]
    xs = xs + 0.5
    ys = ys + 0.5
    for depth, f, ptris, uvt, colt in tris:
        semi = f.mat.semi
        for tri, uv, col in zip(ptris, uvt, colt):
            P = [((v_dot(p, R) - centre[0]) * scale + size / 2, (-v_dot(p, U) - centre[1]) * scale + size / 2) for p in tri]
            (x0, y0), (x1, y1), (x2, y2) = P
            den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(den) < 1e-9:
                continue
            bx0, bx1 = max(0, int(min(x0, x1, x2))), min(size, int(max(x0, x1, x2)) + 1)
            by0, by1 = max(0, int(min(y0, y1, y2))), min(size, int(max(y0, y1, y2)) + 1)
            if bx0 >= bx1 or by0 >= by1:
                continue
            X = xs[by0:by1, bx0:bx1]
            Y = ys[by0:by1, bx0:bx1]
            w0 = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / den
            w1 = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / den
            w2 = 1 - w0 - w1
            m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
            if not m.any():
                continue
            cs = [np.array([(c & 255), (c >> 8) & 255, (c >> 16) & 255], float) for c in col]
            if uv is not None:
                u = w0 * uv[0][0] + w1 * uv[1][0] + w2 * uv[2][0]
                v = w0 * uv[0][1] + w1 * uv[1][1] + w2 * uv[2][1]
                ui = np.clip(np.floor(u).astype(int), 0, 255)
                vi = np.clip(np.floor(v).astype(int), 0, 255)
                idx = ATL[f.mat.cell.slot].idx[vi, ui]
                pal = np.array(PAL[f.mat.pal], float)
                rgb = pal[idx]
                tint = (w0[..., None] * cs[0] + w1[..., None] * cs[1] + w2[..., None] * cs[2]) / 128.0
                rgb = np.clip(rgb * tint, 0, 255)
                m = m & (idx > 0)
            else:
                rgb = w0[..., None] * cs[0] + w1[..., None] * cs[1] + w2[..., None] * cs[2]
            sub = img[by0:by1, bx0:bx1]
            if semi is not None:
                a = 0.5
                sub[m, :3] = sub[m, :3] * (1 - a) + rgb[m] * a
                sub[m, 3] = np.maximum(sub[m, 3], 0.6)
            else:
                sub[m, :3] = rgb[m]
                sub[m, 3] = 1.0
    return img


def downsample(img, k):
    h, w, _ = img.shape
    a = img.reshape(h // k, k, w // k, k, 4)
    alpha = a[..., 3].mean(axis=(1, 3))
    wsum = a[..., 3].sum(axis=(1, 3))[..., None]
    rgb = (a[..., :3] * a[..., 3:4]).sum(axis=(1, 3)) / np.maximum(wsum, 1e-6)
    return np.concatenate([rgb, alpha[..., None]], -1)


def icon_rgba(faces, ss=4, size=ICON, margin=1.5, boost=1.12, fit=None):
    big = render_faces(faces, size * ss, margin * ss, fit=fit)
    small = downsample(big, ss)
    rgb = np.clip(small[..., :3] * boost, 0, 255)
    alpha = small[..., 3] > 0.45
    return rgb, alpha


def quantize_group(items, ncol=14, outline_col=(20, 16, 28)):
    """items: list of (rgb, alpha). Returns (index images, 15-colour palette list)."""
    opaque = np.concatenate([rgb[a] for rgb, a in items], 0)
    if len(opaque) == 0:
        opaque = np.zeros((1, 3))
    im = Image.fromarray(np.clip(opaque, 0, 255).astype(np.uint8)[None, :, :], 'RGB')
    q = im.quantize(ncol, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = q.getpalette()[:ncol * 3]
    cols = [tuple(pal[i * 3:i * 3 + 3]) for i in range(ncol)]
    while len(cols) < ncol:
        cols.append((0, 0, 0))
    P = np.array(cols, float)
    out = []
    for rgb, a in items:
        d = ((rgb[..., None, :] - P[None, None, :, :]) ** 2).sum(-1)
        idx = (d.argmin(-1) + 2).astype(np.uint8)        # 2..ncol+1
        idx[~a] = 0
        m = a
        o = np.zeros_like(m)
        o[1:, :] |= m[:-1, :]; o[:-1, :] |= m[1:, :]; o[:, 1:] |= m[:, :-1]; o[:, :-1] |= m[:, 1:]
        idx[o & ~m] = 1
        out.append(idx)
    full = [outline_col] + cols
    full += [(255, 255, 255)] * (15 - len(full))
    return out, full[:15]


ICON_GROUPS = [
    ('beds', ['bed_single', 'bed_double', 'bed_king', 'nightstand', 'wardrobe', 'phone', 'modem', 'desk', 'chair', 'tv']),
    ('room', ['minibar', 'floor_lamp', 'sofa', 'toilet', 'shower', 'bathtub', 'sink', 'jacuzzi']),
    ('lobby', ['reception_desk', 'key_rack', 'concierge_desk', 'waiting_sofa', 'coffee_table', 'plant', 'luggage_cart', 'palm']),
    ('dining', ['table_2', 'table_4', 'buffet', 'bar_counter', 'bar_stool', 'bar_shelf', 'lounge_chair', 'piano', 'jukebox',
                'arcade']),
    ('service', ['stove', 'prep_counter', 'fridge', 'dishwasher', 'kitchen_sink', 'washer', 'dryer', 'folding_table',
                 'linen_shelf', 'storage_shelf']),
    ('staff', ['locker', 'staff_table', 'vending', 'cot', 'coffee_machine', 'conf_table', 'projector', 'lectern']),
    ('leisure', ['massage_bed', 'sauna', 'hot_tub', 'towel_rack', 'treadmill', 'weights', 'lounger', 'umbrella']),
    ('build', ['door', 'window', 'stairs', 'elevator', 'glass_elevator', 'grand_staircase']),
    ('atrium', ['chandelier', 'skylight', 'indoor_tree', 'fountain', 'railing', 'railing_glass']),
]
EXTRA_OBJS = {'glass_elevator_cab', 'door_frame', 'door_leaf'}

# room types (the main agent's room keys): (name, floor block, palette, [(object, x, z, rot)])
ROOM_ICONS = [
    ('corridor', 'carpet', 'carpet_crimson', [('plant', 0.0, 0.0, 0), ('door', 0.0, -0.5, 0)]),
    ('service', 'concrete', 'concrete', [('storage_shelf', -0.5, 0.0, 0), ('linen_shelf', 0.5, 0.0, 0)]),
    ('outdoor', 'deck', 'deck', [('palm', -0.4, -0.3, 0), ('umbrella', 0.6, 0.4, 0)]),
    ('guest', 'carpet', 'carpet_royal', [('bed_double', 0.0, 0.0, 0), ('nightstand', 1.4, -0.6, 0)]),
    ('suite', 'carpet', 'carpet_plum', [('bed_king', 0.0, 0.0, 0), ('nightstand', 1.4, -0.6, 0)]),
    ('lobby', 'marble', 'marble_white', [('reception_desk', 0.0, 0.0, 0), ('plant', 1.6, 0.2, 0)]),
    ('restaurant', 'wood', 'cherry', [('table_4', 0.0, 0.0, 0)]),
    ('kitchen', 'tile', 'tile_check', [('stove', -0.5, 0.0, 0), ('fridge', 0.5, 0.0, 0)]),
    ('laundry', 'tile', 'tile_aqua', [('washer', -0.5, 0.0, 0), ('dryer', 0.5, 0.0, 0)]),
    ('storage', 'concrete', 'concrete', [('storage_shelf', -0.5, 0.0, 0), ('storage_shelf', 0.5, 0.0, 0)]),
    ('staff', 'wood', 'oak', [('staff_table', 0.0, 0.0, 0), ('vending', 1.2, -0.6, 0)]),
    ('bar', 'wood', 'walnut', [('bar_counter', -0.5, 0.0, 0), ('bar_counter', 0.5, 0.0, 0), ('bar_stool', -0.5, 0.8, 0),
                               ('bar_stool', 0.5, 0.8, 0)]),
    ('pool', 'pool_water', 'pool_water', [('lounger', 0.0, 0.0, 0), ('umbrella', 0.9, -0.4, 0)]),
    ('spa', 'tile', 'tile_aqua', [('massage_bed', 0.0, 0.0, 1), ('towel_rack', 0.0, -1.0, 0)]),
    ('gym', 'wood', 'teak', [('treadmill', -0.5, 0.0, 0), ('weights', 0.8, 0.4, 1)]),
    ('conference', 'carpet', 'carpet_sand', [('conf_table', 0.0, 0.0, 0)]),
]

OBJFN = {}


def obj_faces(key):
    if key not in OBJFN:
        for k, w, d, h, fn in OBJS:
            if k == key:
                r = fn()
                OBJFN[key] = r[0] if isinstance(r, tuple) else r
    return OBJFN[key]


def room_faces(surf, pal, items):
    """A floor patch with a bit of wall and the room's key objects; returns (faces, objects)."""
    b = B()
    m = T('f4_' + surf, pal, fit=True, sub=(0, 0, 0.25, 0.25))
    for x in range(-2, 2):
        for z in range(-2, 2):
            b.flat(x * 1.0, z * 1.0, x + 1.0, z + 1.0, 0.0, m)
    wall = T('w_paint', 'paint_cream', fit=True, sub=(0, 0.5, 1, 1))
    for z in range(-2, 2):
        b.panel_x(z, 0, z + 1, 1.4, -1.0, wall)
    for x in range(-2, 2):
        b.panel(x, 0, x + 1, 1.4, -1.0, wall)
    objs = []
    for key, x, z, rot in items:
        bb = B()
        bb.faces = [Face(list(f.pts), f.n, f.mat, f.shade) for f in obj_faces(key)]
        bb.rot_y(0, rot * math.pi / 2)
        bb.move(0, x, 0, z)
        objs += bb.faces
    return b.faces + objs, objs


ICONS = {}          # name -> (u, v, palette)


def build_icons():
    groups = []
    for gname, keys in ICON_GROUPS:
        items = []
        for k in keys:
            fs = obj_faces(k)
            fit = [f for f in fs if max(p[1] for p in f.pts) < 1.3] if k == 'chandelier' else None
            items.append(icon_rgba(fs, fit=fit))
        groups.append((gname, keys, items))
    rooms = []
    for r in ROOM_ICONS:
        allf, objf = room_faces(r[1], r[2], r[3])
        rooms.append((r[0], icon_rgba(allf, margin=2.5, fit=objf)))
    groups.append(('rooms_a', [r[0] for r in rooms[:8]], [r[1] for r in rooms[:8]]))
    groups.append(('rooms_b', [r[0] for r in rooms[8:]], [r[1] for r in rooms[8:]]))
    i = 0
    for gname, keys, items in groups:
        idxs, cols = quantize_group(items)
        pn = palette('icons_' + gname, cols, 'ui')
        for k, im in zip(keys, idxs):
            u, v = (i % 10) * ICON, (i // 10) * ICON
            cell(10, 'icon_' + k, u, v, im)
            ICONS[k] = (u, v, pn)
            i += 1
    assert i <= 90


build_icons()

# ---- UI pieces (Y2K: glossy aqua plastic, brushed silver, chunky bevels)
UI = {}
ui_pal = palette('ui_main', cols15({1: '0c1020', 2: '1a2a50', 3: '2a4a88', 4: '3a70c0', 5: '5aa8e8', 6: '9ad8f8',
                                    7: 'e0f8ff', 8: '5a6070', 9: '9aa2b0', 10: 'c8ced8', 11: 'eef2f8',
                                    12: 'ffffff', 13: 'f0a030', 14: 'ff6a3a', 15: '40e0a0'}), 'ui')
gold_pal = palette('ui_gold', cols15({1: '201408', 2: '6a4a10', 3: 'a87a18', 4: 'e0b030', 5: 'f8d860', 6: 'fff4b0',
                                      7: 'ffffff', 8: '3a3a44', 9: '6a6a78', 10: 'a0a0b0', 11: '2a7a3a', 12: '4ab060',
                                      13: '90e0a0', 14: 'd03030', 15: 'ffffff'}), 'ui')
mood_pal = palette('ui_mood', cols15({1: '201410', 2: 'f8d040', 3: 'e0a020', 4: 'fff0a0', 5: '60d070', 6: '30a040',
                                      7: 'f06040', 8: 'c03020', 9: 'a0a8b0', 10: '6a7078', 11: 'ffffff', 12: 'f090a0',
                                      13: '40a0f0', 14: '1a1a1a', 15: 'ffffff'}), 'ui')


def ui_cell(name, u, v, img, pal):
    c = cell(10, 'ui_' + name, u, v, img)
    UI[name] = (u, v, img.shape[1], img.shape[0], pal)


def from_art(rows, mapping):
    return np.array([[mapping.get(ch, 0) for ch in r] for r in rows], np.uint8)


# panel 32x32 (9-slice, 8 px borders): silver bezel, aqua inner glow, deep blue fill
pan = np.zeros((32, 32), np.uint8)
yy32, xx32 = np.mgrid[0:32, 0:32]
pan[:] = 2
pan[2:30, 2:30] = 2
for y in range(32):
    for x in range(32):
        e = min(x, y, 31 - x, 31 - y)
        if e == 0:
            pan[y, x] = 1
        elif e == 1:
            pan[y, x] = 11 if (x < 16 and y < 16) or (y < 2) or (x < 2) else 9
        elif e == 2:
            pan[y, x] = 10
        elif e == 3:
            pan[y, x] = 8
        elif e == 4:
            pan[y, x] = 4
        else:
            pan[y, x] = 2 if (x + y) % 2 else 2
# rounded corners
for (cx, cy) in ((0, 0), (31, 0), (0, 31), (31, 31)):
    for y in range(32):
        for x in range(32):
            if abs(x - cx) + abs(y - cy) < 3:
                pan[y, x] = 0
            elif abs(x - cx) + abs(y - cy) == 3:
                pan[y, x] = 1
ui_cell('panel', 0, 216, pan, ui_pal)


def button(state):
    b = np.zeros((16, 32), np.uint8)
    top, mid, bot, edge = {'normal': (6, 5, 3, 1), 'hot': (7, 6, 4, 1), 'pressed': (4, 3, 2, 1)}[state]
    for y in range(16):
        for x in range(32):
            dx = max(0, 7 - x, x - 24)
            dy = abs(y - 7.5)
            r = math.hypot(dx, max(0, dy - 0.0)) if dx > 0 else dy
            if dx > 0 and math.hypot(dx, dy) > 7.8:
                continue
            if dx == 0 and dy > 7.5:
                continue
            t = y / 15
            c = top if t < 0.35 else (mid if t < 0.7 else bot)
            b[y, x] = c
    # gloss highlight and outline
    b[2:4, 6:26] = np.where(b[2:4, 6:26] > 0, 7 if state != 'pressed' else 5, 0)
    m = b > 0
    o = np.zeros_like(m)
    o[1:, :] |= ~m[:-1, :]; o[:-1, :] |= ~m[1:, :]; o[:, 1:] |= ~m[:, :-1]; o[:, :-1] |= ~m[:, 1:]
    o[0, :] = True; o[-1, :] = True; o[:, 0] = True; o[:, -1] = True
    b[m & o] = 1
    return b


ui_cell('button', 32, 216, button('normal'), ui_pal)
ui_cell('button_hot', 64, 216, button('hot'), ui_pal)
ui_cell('button_pressed', 96, 216, button('pressed'), ui_pal)

STAR = ["....1.....",
        "....11....",
        "...1441...",
        "...1451...",
        "1111456111",
        "1555456541",
        ".15444441.",
        "..144441..",
        ".1444444..",
        ".144114441",
        "1441..1441",
        "111....111"]
star = from_art([r.ljust(12, '.') for r in STAR], {'1': 1, '4': 4, '5': 5, '6': 6})
star = np.pad(star, ((0, 0), (1, 0)))[:, :12]
half = star.copy()
half[:, 7:] = np.where(half[:, 7:] > 1, 9, half[:, 7:])
empty = np.where(star > 1, 9, star).astype(np.uint8)
empty[(star == 6)] = 10
ui_cell('star', 128, 216, star, gold_pal)
ui_cell('star_half', 140, 216, half, gold_pal)
ui_cell('star_empty', 152, 216, empty, gold_pal)

COIN = ["....1111....",
        "..11444411..",
        ".1455555441.",
        ".1453663541.",
        "145566355541",
        "145536635541",
        "145553366541",
        "145336635541",
        ".1455663541.",
        ".1444444431.",
        "..11333311..",
        "....1111...."]
ui_cell('coin', 164, 216, from_art(COIN, {'1': 1, '3': 3, '4': 4, '5': 5, '6': 6}), gold_pal)
NOTE = ["................",
        ".11111111111111.",
        ".1cccccccccccc1.",
        ".1cdddd11ddddc1.",
        ".1cd111dd111dc1.",
        ".1cd1d1dd1d1dc1.",
        ".1cdd1dddd1ddc1.",
        ".1cd111dd111dc1.",
        ".1cdddd11ddddc1.",
        ".1cccccccccccc1.",
        ".11111111111111.",
        "................"]
ui_cell('money', 176, 216, from_art(NOTE, {'1': 1, 'c': 12, 'd': 13}), gold_pal)


def face(mood):
    f = np.zeros((16, 16), np.uint8)
    base, shade = {'ecstatic': (5, 6), 'happy': (2, 3), 'neutral': (2, 3), 'unhappy': (9, 10), 'angry': (7, 8)}[mood]
    for y in range(16):
        for x in range(16):
            r = math.hypot(x - 7.5, y - 7.5)
            if r < 7.2:
                f[y, x] = base if (x + y) < 19 else shade
            if 6.4 <= r < 7.6:
                f[y, x] = 1
    f[3:5, 4:6] = 4 if mood != 'angry' else 4
    eye = 14
    if mood == 'angry':
        f[5, 4] = eye; f[6, 5] = eye; f[5, 11] = eye; f[6, 10] = eye
        f[7, 5] = eye; f[7, 10] = eye
    elif mood == 'ecstatic':
        for x, y in ((4, 6), (5, 5), (6, 6), (9, 6), (10, 5), (11, 6)):
            f[y, x] = eye
    else:
        f[5:7, 5] = eye; f[5:7, 10] = eye
    mouth = {'ecstatic': [(4, 9), (5, 10), (6, 11), (7, 11), (8, 11), (9, 11), (10, 10), (11, 9), (5, 9), (6, 10), (7, 10), (8, 10), (9, 10), (10, 9)],
             'happy': [(4, 9), (5, 10), (6, 11), (7, 11), (8, 11), (9, 11), (10, 10), (11, 9)],
             'neutral': [(5, 11), (6, 11), (7, 11), (8, 11), (9, 11), (10, 11)],
             'unhappy': [(4, 12), (5, 11), (6, 10), (7, 10), (8, 10), (9, 10), (10, 11), (11, 12)],
             'angry': [(5, 12), (6, 11), (7, 11), (8, 11), (9, 11), (10, 12)]}[mood]
    for x, y in mouth:
        f[y, x] = 14 if mood != 'ecstatic' or y == 11 or x in (4, 11) else 12
    if mood == 'unhappy':
        f[8, 11] = 13; f[9, 11] = 13
    return f


for k, mood in enumerate(('ecstatic', 'happy', 'neutral', 'unhappy', 'angry')):
    ui_cell('mood_' + mood, 192 + (k % 4) * 16, 216 + (k // 4) * 16, face(mood), mood_pal)

# small symbols 16x16 (ui_main palette) in the right-hand column
SYMBOLS = {
    'build': ["................", "..1111111.......", ".1999999991.....", ".1aaaaaaaa1.....", "..1111aa111.....",
              ".....1aa1.......", ".....1aa1.......", ".....1881.......", ".....1881.......", ".....1881.......",
              ".....1881.......", ".....1881.......", ".....1881.......", "......11........", "................", "................"],
    'demolish': ["................", ".11..........11.", "1ee1........1ee1", "1eee1......1eee1", ".1eee1....1eee1.",
                 "..1eee1..1eee1..", "...1eee11eee1...", "....1eeeeee1....", "....1eeeeee1....", "...1eee11eee1...",
                 "..1eee1..1eee1..", ".1eee1....1eee1.", "1eee1......1eee1", "1ee1........1ee1", ".11..........11.", "................"],
    'rotate': ["................", ".....111111.....", "...1155555511...", "..15511111155.1.", ".151........1151",
               ".151.........151", "151.........1551", "151........15551", "151.........111.", "151.............",
               ".151........1...", ".151.......151..", "..15511111151...", "...1155555511...", ".....111111.....", "................"],
    'cancel': ["................", "...1111111111...", "..1eeeeeeeeee1..", ".1eeeeeeeeeeee1.", ".1ee1ceeeec1ee1.",
               ".1eec1ceec1cee1.", ".1eeec1cc1ceee1.", ".1eeeec11ceeee1.", ".1eeeec11ceeee1.", ".1eeec1cc1ceee1.",
               ".1eec1ceec1cee1.", ".1ee1ceeeec1ee1.", ".1eeeeeeeeeeee1.", "..1eeeeeeeeee1..", "...1111111111...", "................"],
    'ok': ["................", "...1111111111...", "..1ffffffffff1..", ".1ffffffffffcf1.", ".1fffffffffccf1.",
           ".1ffffffffccff1.", ".1fffffffccfff1.", ".1fcffffccffff1.", ".1fccffccfffff1.", ".1ffccccffffff1.",
           ".1fffccfffffff1.", ".1ffffffffffff1.", ".1ffffffffffff1.", "..1ffffffffff1..", "...1111111111...", "................"],
    'up': ["................", ".......11.......", "......1661......", ".....166661.....", "....16666661....",
           "...1666666661...", "..111166661111..", ".....166661.....", ".....155551.....", ".....155551.....",
           ".....144441.....", ".....144441.....", ".....133331.....", ".....111111.....", "................", "................"],
    'down': ["................", "................", ".....111111.....", ".....166661.....", ".....166661.....",
             ".....155551.....", ".....155551.....", ".....144441.....", "..111144441111..", "...1444444441...",
             "....14444441....", ".....133331.....", "......1331......", ".......11.......", "................", "................"],
    'sun': ["................", ".......dd.......", "...d...dd...d...", "....d......d....", "......dddd......",
            ".....dddddd.....", ".dd.dddddddd.dd.", ".dd.dddddddd.dd.", ".....dddddd.....", "......dddd......",
            "....d......d....", "...d...dd...d...", ".......dd.......", "................", "................", "................"],
    'moon': ["................", "......1111......", "....11bbbb1.....", "...1bbbbb1......", "..1bbbbb1.......",
             "..1bbbb1........", ".1bbbbb1........", ".1bbbbb1........", ".1bbbbb1........", "..1bbbbb1.......",
             "..1bbbbbb1......", "...1bbbbbbb11...", "....11bbbbbbb1..", "......1111111...", "................", "................"],
    'info': ["................", "...1111111111...", "..1555555555551.", ".15555cccc55551.", ".1555cccccc5551.",
             ".15555cccc55551.", ".15555555555551.", ".1555ccccc55551.", ".15555cccc55551.", ".15555cccc55551.",
             ".15555cccc55551.", ".1555cccccc5551.", ".15555555555551.", "..155555555551..", "...1111111111...", "................"],
    'pause': ["................", "................", "...1111..1111...", "...1cc1..1cc1...", "...1cc1..1cc1...",
              "...1cc1..1cc1...", "...1cc1..1cc1...", "...1cc1..1cc1...", "...1cc1..1cc1...", "...1cc1..1cc1...",
              "...1cc1..1cc1...", "...1cc1..1cc1...", "...1111..1111...", "................", "................", "................"],
    'play': ["................", "................", "...11...........", "...1c11.........", "...1ccc11.......",
             "...1ccccc11.....", "...1ccccccc11...", "...1ccccccccc1..", "...1ccccccc11...", "...1ccccc11.....",
             "...1ccc11.......", "...1c11.........", "...11...........", "................", "................", "................"],
    'fast': ["................", "................", ".11.....11......", ".1c11...1c11....", ".1ccc11.1ccc11..",
             ".1ccccc11ccccc11", ".1ccccccc1cccccc", ".1ccccc11ccccc11", ".1ccc11.1ccc11..", ".1c11...1c11....",
             ".11.....11......", "................", "................", "................", "................", "................"],
}
SYMMAP = {'1': 1, '3': 3, '4': 4, '5': 5, '6': 6, '8': 8, '9': 9, 'a': 10, 'b': 11, 'c': 12, 'd': 13, 'e': 14, 'f': 15}
for k, (nm, rows) in enumerate(SYMBOLS.items()):
    ui_cell(nm, 240, k * 16, from_art(rows, SYMMAP), ui_pal)


def icon_decls(L):
    A = L.append
    A('')
    A('// ---- build-menu icons: 24x24 in slot 10 (4-bit), one per object (ART_ICON_U/V/PAL indexed by')
    A('// ART_OBJ_<KEY>) and one per room type (ART_ROOM_<NAME>). Transparent background, dark outline.')
    A('const ART_ICON_SLOT = 10')
    A('const ART_ICON_SIZE = %d' % ICON)
    keys = [o[0] for o in OBJS]
    A('// (extras without an icon point at the door icon)')
    A('const ART_ICON_U: [%d]u8 = [%s]' % (len(keys), ', '.join(str(ICONS.get(k, ICONS['door'])[0]) for k in keys)))
    A('const ART_ICON_V: [%d]u8 = [%s]' % (len(keys), ', '.join(str(ICONS.get(k, ICONS['door'])[1]) for k in keys)))
    A('const ART_ICON_PAL: [%d]u8 = [%s]' % (len(keys), ', '.join(str(ICONS.get(k, ICONS['door'])[2]) for k in keys)))
    rooms = [r[0] for r in ROOM_ICONS]
    A('const ART_ROOM_COUNT = %d' % len(rooms))
    for i, r in enumerate(rooms):
        A('const ART_ROOM_%s = %d' % (r.upper(), i))
    A('const ART_ROOM_ICON_U: [%d]u8 = [%s]' % (len(rooms), ', '.join(str(ICONS[r][0]) for r in rooms)))
    A('const ART_ROOM_ICON_V: [%d]u8 = [%s]' % (len(rooms), ', '.join(str(ICONS[r][1]) for r in rooms)))
    A('const ART_ROOM_ICON_PAL: [%d]u8 = [%s]' % (len(rooms), ', '.join(str(ICONS[r][2]) for r in rooms)))
    A('')
    A('// ---- UI pieces in slot 10: ART_UI_<NAME>_U/_V/_W/_H/_PAL. The panel is a 9-slice source with')
    A('// 8-texel borders; buttons are 32x16 pills with 8-texel end caps (normal, hot, pressed).')
    for nm, (u, v, w, h, pn) in UI.items():
        N = nm.upper()
        A('const ART_UI_%s_U = %d' % (N, u))
        A('const ART_UI_%s_V = %d' % (N, v))
        A('const ART_UI_%s_W = %d' % (N, w))
        A('const ART_UI_%s_H = %d' % (N, h))
        A('const ART_UI_%s_PAL = %d' % (N, pn))


FINISHERS.append(icon_decls)


# ============================================================================= save icon
# 16x16, three frames: a little seaside hotel whose neon sign blinks (pink, off, cyan).
SAVE_ART = [
    "......8.........",
    ".....898........",
    "......8.........",
    "..111111111111..",
    "8.166666666661..",
    "9.122222222221..",
    "8.124324524321..",
    "9.122222222221..",
    "8.125324424351..",
    "9.122222222221..",
    "8.124324424321..",
    "..122222222221..",
    ".1eeeeeeeeeeee1.",
    "cc12227772221.c.",
    "dc12227772221cdc",
    "d1111111111111d.",
]
SAVE_PAL = [(0, 0, 0), (24, 16, 40), (240, 140, 120), (190, 96, 96), (255, 220, 120), (60, 80, 130),
            (250, 250, 245), (120, 200, 230), (255, 80, 180), (255, 170, 220), (90, 40, 70), (0, 0, 0),
            (60, 170, 80), (130, 90, 50), (40, 190, 180), (120, 255, 255)]


def save_icon():
    m = {'.': 0, 'c': 12, 'd': 13, 'e': 14}
    base = np.array([[m[ch] if ch in m else int(ch) for ch in r] for r in SAVE_ART], np.int64)
    f1 = base.copy()
    f2 = base.copy()
    f2[(f2 == 8) | (f2 == 9)] = 10
    f2[6, 6] = 5; f2[10, 9] = 5                       # a couple of rooms switch off
    f3 = base.copy()
    f3[f3 == 8] = 15
    f3[f3 == 9] = 7
    f3[8, 9] = 4
    blob = mei_icon.make_meta([f1, f2, f3], title='Check-In!', palette=SAVE_PAL)
    write('save_icon.bin', blob)
    if REVIEW:
        P = np.array(SAVE_PAL, np.uint8)
        strip = np.concatenate([P[f] for f in (f1, f2, f3)], 1)
        Image.fromarray(strip).resize((48 * 8, 16 * 8), Image.NEAREST).save(os.path.join(REVIEW, 'save_icon.png'))


def save_decls(L):
    L.append('')
    L.append('// ---- memory card title and icon (3 frames: the hotel\'s neon sign blinks)')
    L.append('embed ART_SAVE_ICON: SaveMeta = "art/save_icon.bin"')


FINISHERS.append(save_decls)


# ============================================================================= OUTPUT

# the contract's mesh index order (main's object enum), then extras
CATALOGUE_ORDER = ['bed_single', 'bed_double', 'nightstand', 'wardrobe', 'tv', 'desk', 'chair', 'minibar',
                   'floor_lamp', 'sofa', 'toilet', 'shower', 'bathtub', 'sink', 'jacuzzi', 'reception_desk',
                   'key_rack', 'concierge_desk', 'waiting_sofa', 'coffee_table', 'plant', 'luggage_cart',
                   'table_2', 'table_4', 'buffet', 'bar_counter', 'bar_stool', 'bar_shelf', 'lounge_chair',
                   'piano', 'jukebox', 'stove', 'prep_counter', 'fridge', 'dishwasher', 'kitchen_sink',
                   'washer', 'dryer', 'folding_table', 'linen_shelf', 'storage_shelf', 'locker',
                   'staff_table', 'vending', 'cot', 'massage_bed', 'sauna', 'hot_tub', 'towel_rack',
                   'treadmill', 'weights', 'lounger', 'umbrella', 'conf_table', 'projector', 'lectern',
                   'stairs', 'elevator', 'glass_elevator', 'grand_staircase', 'chandelier', 'skylight',
                   'indoor_tree', 'fountain', 'door', 'window', 'railing', 'railing_glass', 'bed_king',
                   'phone', 'modem', 'arcade', 'palm', 'coffee_machine']
EXTRA_ORDER = ['glass_elevator_cab', 'door_frame', 'door_leaf']

# objects share a 15-colour palette per group (the game relights it by class: 0 interior, 1 exterior)
OBJ_GROUPS = [
    ('beds', 0, ['bed_single', 'bed_double', 'bed_king']),
    ('wood', 0, ['nightstand', 'wardrobe', 'desk', 'chair']),
    ('gadget', 0, ['phone', 'modem', 'minibar']),
    ('tv', 0, ['tv', 'floor_lamp']),
    ('sofa', 0, ['sofa', 'waiting_sofa', 'lounge_chair']),
    ('wc', 0, ['toilet', 'sink', 'shower']),
    ('tub', 0, ['bathtub', 'jacuzzi', 'towel_rack']),
    ('reception', 0, ['reception_desk']),
    ('concierge', 0, ['concierge_desk', 'key_rack', 'lectern']),
    ('lobby', 0, ['coffee_table', 'plant', 'luggage_cart']),
    ('tables', 0, ['table_2', 'table_4']),
    ('bar', 0, ['buffet', 'bar_counter', 'bar_stool']),
    ('barback', 0, ['bar_shelf', 'jukebox']),
    ('piano', 0, ['piano']),
    ('machines', 0, ['arcade', 'vending', 'coffee_machine']),
    ('kitchen', 0, ['stove', 'prep_counter', 'fridge', 'dishwasher', 'kitchen_sink']),
    ('laundry', 0, ['washer', 'dryer', 'folding_table']),
    ('shelves', 0, ['linen_shelf', 'storage_shelf', 'locker']),
    ('staff', 0, ['staff_table', 'cot', 'massage_bed']),
    ('spa', 0, ['sauna', 'hot_tub']),
    ('gym', 0, ['treadmill', 'weights']),
    ('conference', 0, ['conf_table', 'projector']),
    ('outdoor', 1, ['lounger', 'umbrella', 'palm', 'skylight']),
    ('build', 0, ['stairs', 'door', 'window', 'door_frame', 'door_leaf', 'railing']),
    ('lift', 0, ['elevator', 'glass_elevator', 'glass_elevator_cab']),
    ('grand', 0, ['grand_staircase']),
    ('atrium', 0, ['chandelier', 'fountain', 'railing_glass']),
    ('tree', 0, ['indoor_tree']),
]
OBJ_GROUP = {k: g for g, _, ks in OBJ_GROUPS for k in ks}
GROUP_CLASS = {g: c for g, c, _ in OBJ_GROUPS}
EMIT = {}           # palette number -> bitmask of colours that glow at night
PAL_CLASS = {}      # palette number -> 0 interior, 1 exterior, 2 water, 3 never relit
BUILT = {}          # key -> dict(src, prox, lo, w, d, h)


def build_objects():
    by_key = {k: (w, d, h, fn) for k, w, d, h, fn in OBJS}
    order = [k for k in CATALOGUE_ORDER + EXTRA_ORDER if k in by_key]
    order += [k for k in by_key if k not in order]
    jobs = []           # [key, face, rgba, emissive, D]
    for key in order:
        w, d, h, fn = by_key[key]
        r = fn()
        if isinstance(r, tuple) and len(r) == 3:
            src, prox, lo = r
        else:
            src, prox, lo = (r[0] if isinstance(r, tuple) else r), None, None
        if key in PROXY:
            prox, lo = PROXY[key](src)
        if prox is None:
            prox = lo_box(src, D=HI_D)
        if lo is None:
            lo = lo_box(src)
        BUILT[key] = dict(src=src, prox=prox, lo=lo, w=w, d=d, h=h)
        for which, faces, D in (('hi', prox, HI_D), ('lo', lo, LO_D)):
            for f in faces:
                if f.mat.bake is not None:
                    img, em = bake_face(f, src, D)
                    jobs.append([key, f, img, em])
    # quantize per group
    gpal = {}
    for g, cls, keys in OBJ_GROUPS + [('misc', 0, [k for k in order if k not in OBJ_GROUP])]:
        gj = [j for j in jobs if OBJ_GROUP.get(j[0], 'misc') == g]
        if not gj:
            continue
        idxs, cols, bits = quantize_bakes([(j[2], j[3]) for j in gj])
        pn = palette('grp_' + g, cols)
        PAL_CLASS[pn] = cls
        if bits:
            EMIT[pn] = bits
            NIGHT[pn] = [(0, 0, 0)] + [tuple(clamp8(v) for v in (lerp3(c, (255, 214, 150), 0.3) if bits >> (i + 1) & 1 else c))
                                       for i, c in enumerate(cols)]
        gpal[g] = pn
        for j, ix in zip(gj, idxs):
            j.append(ix)
            j.append(pn)
    # pack, tallest first; identical (or mirrored) textures with the same palette are shared
    pk = Packer(BAKE_SLOTS)
    seen = {}
    for j in sorted(jobs, key=lambda j: (-j[4].shape[0], -j[4].shape[1])):
        key, f, img, em, ix, pn = j
        flip = False
        h1 = (pn, ix.shape, ix.tobytes())
        h2 = (pn, ix.shape, np.ascontiguousarray(ix[:, ::-1]).tobytes())
        if h1 in seen:
            c = seen[h1]
        elif h2 in seen:
            c, flip = seen[h2], True
        else:
            c = pk.place(ix, 'bk_%s' % key)
            seen[h1] = c
        bk = f.mat.bake
        glow = bk['glow'] if bk['glow'] is not None else (em.mean() > 0.6 if em.size else False)
        f.mat = Mat(cell=c, pal=pn, fit=True, excl=True, double=f.mat.double, glow=glow, flipu=flip)
    out = []
    for key in order:
        B_ = BUILT[key]
        prox, lo = B_['prox'], B_['lo']
        nt, nl = tri_count(prox), tri_count(lo)
        assert nl <= 10, (key, nl)
        m, ml = emit(prox), emit(lo)
        write(key + '.bin', m.pack())
        write(key + '_lo.bin', ml.pack())
        out.append((key, B_['w'], B_['d'], B_['h'], nt, nl, len(m.verts), B_['src']))
    return out


# floor blocks and wall cells with the palettes made for them (the first is the default)
FLOOR_PALS = {
    'carpet': [n for n, *_ in CARPETS],
    'tile': ['tile_white', 'tile_check', 'tile_terracotta', 'tile_aqua'],
    'wood': ['oak', 'walnut', 'cherry', 'teak', 'white', 'ebony'],
    'marble': ['marble_white', 'marble_black', 'marble_rose', 'marble_green'],
    'terrazzo': ['terrazzo'],
    'concrete': ['concrete'],
    'deck': ['deck', 'white', 'oak'],
    'sand': ['sand'],
    'grass': ['grass'],
    'road': ['road'],
    'pavement': ['pavement'],
    'pool_water': ['pool_water'],
    'sea': ['sea'],
    'roof': ['grey', 'pavement'],
}
FLOOR_PALS['sidewalk'] = FLOOR_PALS['pavement']
FLOOR_PALS['terracotta'] = ['tile_terracotta']
WALL_PALS = {
    'paint': [n for n, _ in PAINTS],
    'wallpaper': ['wallpaper_regency', 'wallpaper_mint', 'wallpaper_rose', 'wallpaper_navy'],
    'damask': ['damask_gold', 'damask_red', 'damask_teal'],
    'stone': ['stone_sand', 'stone_slate'],
    'facade': ['facade_cream', 'facade_coral', 'facade_aqua'],
    'facade_window': ['facade_cream', 'facade_coral', 'facade_aqua'],
    'facade_glass': ['facade_cream', 'facade_coral', 'facade_aqua'],
    'glass': ['glass'],
    'wall_top': ['wall_top'],
}
EXTERIOR_PALS = ['facade_cream', 'facade_coral', 'facade_aqua', 'facade_cream_lit', 'facade_coral_lit',
                 'facade_aqua_lit', 'grass', 'sand', 'pavement', 'road', 'deck', 'grey']
WATER_PALS_N = ['pool_water', 'sea']


def pal_bytes(lo, hi, src=None):
    src = src or PAL
    b = bytearray()
    for n in range(lo, hi):
        cols = src.get(n, [(0, 0, 0)] * 16)
        b += struct.pack('<16H', *[c15(c) for c in cols])
    return bytes(b)


def finish():
    objs = build_objects()
    save_icon()
    for nm in EXTERIOR_PALS:
        PAL_CLASS[PALNAME[nm]] = 1
    for nm in WATER_PALS_N:
        PAL_CLASS[PALNAME[nm]] = 2
    for nm in ('facade_cream', 'facade_coral', 'facade_aqua', 'facade_cream_lit', 'facade_coral_lit', 'facade_aqua_lit'):
        EMIT[PALNAME[nm]] = sum(1 << i for i in range(9, 14))
    tex_slots = [s for s in sorted(ATL) if s < 16 and ATL[s].used > 0]
    for s in tex_slots:
        data = ATL[s].pack()
        write('tex%d.bin' % s, data + bytes(32768 - len(data)))
    write('pal_obj.bin', pal_bytes(0, NEXT['obj']))
    write('pal_ppl.bin', pal_bytes(96, NEXT['ppl']))
    write('pal_ui.bin', pal_bytes(128, NEXT['ui']))
    write('palettes.bin', pal_bytes(0, 160))
    glow = sorted(n for n in NIGHT if n < 96)
    write('pal_night.bin', b''.join(struct.pack('<16H', *[c15(c) for c in NIGHT[n]]) for n in glow))
    write('pal_day.bin', b''.join(struct.pack('<16H', *[c15(c) for c in PAL[n]]) for n in glow))
    wb = bytearray()
    water = sorted(WATER_FRAMES)
    for n in water:
        for fr in WATER_FRAMES[n]:
            wb += struct.pack('<16H', *[c15(c) for c in fr])
    write('pal_water.bin', bytes(wb))

    L = []
    A = L.append
    A('// Check-In! art: GENERATED by tools/gen_checkin_art.py -- do not edit.')
    A('// Declarations only (embed, const). Loader: art_load.akr (art_load(), ART_MESH tables).')
    A('// Conventions: carts/checkin/CONTRACT.md.')
    A('')
    A('// ---- textures: one 32,768-byte 4-bit slot image per used slot (copy to the slot start)')
    for s in tex_slots:
        A('embed ART_TEX%d: u8 = "art/tex%d.bin"' % (s, s))
    A('const ART_NTEX = %d' % len(tex_slots))
    A('const ART_TEX_SLOTS: [%d]u8 = [%s]   // the slots of ART_TEX<n>' % (len(tex_slots), ', '.join(map(str, tex_slots))))
    A('// slot 0 surfaces; %s baked objects; 7..9 people; 10 build-menu icons and UI'
      % ', '.join(str(s) for s in tex_slots if 2 <= s <= 6))
    A('')
    A('// ---- palettes (16 15-bit colours each)')
    A('embed ART_PAL: u16 = "art/palettes.bin"       // palettes 0..159 contiguous (unused ones black)')
    A('embed ART_PAL_OBJ: u16 = "art/pal_obj.bin"     // palettes 0..%d: objects and surfaces' % (NEXT['obj'] - 1))
    A('embed ART_PAL_PPL: u16 = "art/pal_ppl.bin"     // palettes 96..%d: people' % (NEXT['ppl'] - 1))
    A('embed ART_PAL_UI: u16 = "art/pal_ui.bin"       // palettes 128..%d: icons and UI' % (NEXT['ui'] - 1))
    A('embed ART_PAL_NIGHT: u16 = "art/pal_night.bin" // night versions of ART_GLOW_PALS (16 colours each)')
    A('embed ART_PAL_DAY: u16 = "art/pal_day.bin"     // day versions of ART_GLOW_PALS')
    A('embed ART_PAL_WATER: u16 = "art/pal_water.bin" // ART_WATER_PALS x 4 animation frames x 16 colours')
    A('const ART_PAL_OBJ_COUNT = %d' % NEXT['obj'])
    A('const ART_PAL_PPL_COUNT = %d' % (NEXT['ppl'] - 96))
    A('const ART_PAL_UI_COUNT = %d' % (NEXT['ui'] - 128))
    A('const ART_GLOW_COUNT = %d' % len(glow))
    A('const ART_GLOW_PALS: [%d]u8 = [%s]   // palettes with colours that glow at night' % (len(glow), ', '.join(map(str, glow))))
    A('const ART_WATER_COUNT = %d' % len(water))
    A('const ART_WATER_PALS: [%d]u8 = [%s]' % (len(water), ', '.join(map(str, water))))
    A('// relighting class of palettes 0..127: 0 interior, 1 exterior, 2 water (cycled), 3 never relit')
    A('const ART_PAL_CLASS: [128]u8 = [%s]' % ', '.join(str(PAL_CLASS.get(n, 0)) for n in range(128)))
    A('// bit i set: colour i of the palette glows at night (window glass, lamp shades, screens)')
    A('const ART_PAL_EMIT: [128]u16 = [%s]' % ', '.join(str(EMIT.get(n, 0)) for n in range(128)))
    A('')
    A('// ---- palette numbers')
    for name, n in sorted(PALNAME.items(), key=lambda t: t[1]):
        if n < 160:
            A('const ART_PAL_%s = %d' % (name.upper(), n))
    A('')
    A('// ---- surfaces (slot 0). Floors: seamless 64x64 blocks covering 4x4 tiles (16 texels per tile),')
    A('// ART_FLOOR4_<NAME>_U/_V. Walls: 16x44 cells covering one tile-wide panel of the full wall height')
    A('// (2.75), and a 16x8 cap (WALL_TOP). Every cell: ART_SURF_<NAME>_U/_V/_W/_H/_SLOT/_PAL, and')
    A('// ART_SURF_<NAME>_PALS / _NPAL list the palettes made for it (the first is the default).')
    A('const ART_SURF_SLOT = 0')
    A('const ART_SURF_SIZE = 16          // texels per unit (tile) on floors and walls')
    A('const ART_FLOOR4_SIZE = 64')
    A('const ART_SURF_WALL_W = 16')
    A('const ART_SURF_WALL_H = 44')
    names = list(FLOOR4) + list(FLOOR4_ALIAS)
    for nm in names:
        c = FLOOR4[FLOOR4_ALIAS.get(nm, nm)]
        N = nm.upper()
        pl = [PALNAME[p] for p in FLOOR_PALS[nm]]
        A('const ART_FLOOR4_%s_U = %d' % (N, c.u))
        A('const ART_FLOOR4_%s_V = %d' % (N, c.v))
        for k, v in (('U', c.u), ('V', c.v), ('W', c.w), ('H', c.h), ('SLOT', 0), ('PAL', pl[0]), ('NPAL', len(pl))):
            A('const ART_SURF_%s_%s = %d' % (N, k, v))
        A('const ART_SURF_%s_PALS: [%d]u8 = [%s]' % (N, len(pl), ', '.join(map(str, pl))))
    for nm, c in WALLS.items():
        N = nm.upper()
        pl = [PALNAME[p] for p in WALL_PALS[nm]]
        for k, v in (('U', c.u), ('V', c.v), ('W', c.w), ('H', c.h), ('SLOT', 0), ('PAL', pl[0]), ('NPAL', len(pl))):
            A('const ART_SURF_%s_%s = %d' % (N, k, v))
        A('const ART_SURF_%s_PALS: [%d]u8 = [%s]' % (N, len(pl), ', '.join(map(str, pl))))
    c = WALLS['facade']
    A('// facade_plain: the plain facade (older name)')
    for k, v in (('U', c.u), ('V', c.v), ('W', c.w), ('H', c.h), ('SLOT', 0), ('PAL', PALNAME['facade_cream'])):
        A('const ART_SURF_FACADE_PLAIN_%s = %d' % (k, v))
    A('')
    A('// ---- object meshes. Origin at the footprint centre on the floor, front toward +z. Every face is')
    A('// textured (baked, slots 2..6) with the object group\'s palette, so the game\'s relighting applies.')
    A('// ART_OBJ_<KEY> indexes ART_OBJ_W/D/H, ART_MESH / ART_MESH_LO (art_load.akr) and ART_ICON_*.')
    A('// Indices 0..73 follow the contract\'s mesh index order; extras follow.')
    A('const ART_OBJ_COUNT = %d' % len(objs))
    for i, (key, w, d, h, nt, nl, nv, _) in enumerate(objs):
        K = key.upper()
        A('embed ART_%s: Mesh = "art/%s.bin"%s// %d tris, %d verts' % (K, key, ' ' * max(1, 24 - 2 * len(key)), nt, nv))
        A('embed ART_%s_LO: Mesh = "art/%s_lo.bin"%s// %d tris' % (K, key, ' ' * max(1, 21 - 2 * len(key)), nl))
        A('const ART_%s_W = %d' % (K, w))
        A('const ART_%s_D = %d' % (K, d))
        A('const ART_%s_H = %d' % (K, h))
        A('const ART_OBJ_%s = %d' % (K, i))
    A('const ART_OBJ_W: [%d]u8 = [%s]' % (len(objs), ', '.join(str(o[1]) for o in objs)))
    A('const ART_OBJ_D: [%d]u8 = [%s]' % (len(objs), ', '.join(str(o[2]) for o in objs)))
    A('const ART_OBJ_H: [%d]u8 = [%s]' % (len(objs), ', '.join(str(o[3]) for o in objs)))
    for f in FINISHERS:
        f(L)
    with open(os.path.join(CART, 'art.akr'), 'w') as fh:
        fh.write('\n'.join(L) + '\n')

    G = []
    G.append('// Check-In! art loader: GENERATED by tools/gen_checkin_art.py -- do not edit.')
    G.append('// Uploads the art textures and palettes, and holds the mesh pointer tables.')
    G.append('import "art.akr"')
    G.append('')
    G.append('// ART_MESH[ART_OBJ_<KEY>] is the object\'s mesh, ART_MESH_LO its low-detail version.')
    G.append('var ART_MESH: [%d]*Mesh = [%s]' % (len(objs), ', '.join('ART_' + o[0].upper() for o in objs)))
    G.append('var ART_MESH_LO: [%d]*Mesh = [%s]' % (len(objs), ', '.join('ART_' + o[0].upper() + '_LO' for o in objs)))
    G.append('')
    G.append('// Copies the art textures into their slots (%s) and palettes 0..159.' % ', '.join(map(str, tex_slots)))
    G.append('fn art_load() {')
    for s in tex_slots:
        G.append('    load_texture(%d, ART_TEX%d, len(ART_TEX%d))' % (s, s, s))
    G.append('    load_palette(0, ART_PAL, len(ART_PAL))')
    G.append('}')
    G.append('')
    G.append('// Lamps, screens and signs glow at night (on) or not (off): swaps ART_GLOW_PALS.')
    G.append('fn art_lights(on: bool) {')
    G.append('    var src = ART_PAL_DAY')
    G.append('    if on { src = ART_PAL_NIGHT }')
    G.append('    for i in 0..ART_GLOW_COUNT {')
    G.append('        load_palette((ART_GLOW_PALS[i] as s32) * 16, src + i * 16, 16)')
    G.append('    }')
    G.append('}')
    G.append('')
    G.append('// Animates the pool and sea palettes; call with a frame counter (a new frame every 8 ticks).')
    G.append('fn art_water(tick: s32) {')
    G.append('    let f = (tick >> 3) & 3')
    G.append('    for i in 0..ART_WATER_COUNT {')
    G.append('        load_palette((ART_WATER_PALS[i] as s32) * 16, ART_PAL_WATER + (i * 4 + f) * 16, 16)')
    G.append('    }')
    G.append('}')
    with open(os.path.join(CART, 'art_load.akr'), 'w') as fh:
        fh.write('\n'.join(G) + '\n')

    tot = sum(FILES.values())
    print('objects: %d, triangles: %d (max %d), lo max %d' % (len(objs), sum(o[4] for o in objs), max(o[4] for o in objs),
                                                               max(o[5] for o in objs)))
    for o in objs:
        flag = ' <-- over 60' if o[4] > 60 else (' (>30)' if o[4] > 30 else '')
        print('  %-18s %dx%d  %3d tris  lo %2d%s' % (o[0], o[1], o[2], o[4], o[5], flag))
    print('palettes: obj %d/96, people %d/32, ui %d/32' % (NEXT['obj'], NEXT['ppl'] - 96, NEXT['ui'] - 128))
    print('texture slots: %s; bake rows: %s' % (tex_slots, [ATL[s].used for s in BAKE_SLOTS]))
    print('art ROM: %d bytes (%.1f KB) in %d files' % (tot, tot / 1024, len(FILES)))


def review(objs):
    for s in [s for s in sorted(ATL) if s < 16 and ATL[s].used]:
        a = ATL[s].idx
        img = (a.astype(np.float32) * 17).astype(np.uint8)
        Image.fromarray(img).resize((512, 512), Image.NEAREST).save(os.path.join(REVIEW, 'atlas%d_idx.png' % s))


if __name__ == '__main__':
    finish()
