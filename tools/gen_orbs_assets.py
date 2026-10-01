#!/usr/bin/env python3
"""Generates the assets of the "Sun & Moon Orbs" cart in carts/orbs/:

  tex4.bin      4-bit texture atlas for slot 0 (32x32 cells, one 16-colour palette each)
  pal4.bin      its palettes: 4-bit palettes 0-15 (colours 0-255)
  tex8.bin      8-bit texture for slots 2-3 (mountain panorama, mosaic, sun, moon)
  pal8.bin      its palettes: 8-bit palettes 1-3 (colours 256-1023)
  chunk*.bin    the level, split into chunks for culling (textured, Gouraud-lit)
  water.bin     the pool's semi-transparent water surface
  ring.bin      the mountain panorama ring (drawn around the camera)
  player.bin    the player's body, foot.bin a foot
  orb_sun.bin, orb_moon.bin   orb cores
  *.raw         sounds: 8-bit sfx at 22,050 Hz, 16-bit music loops at 11,025 Hz
  save_icon.bin memory card save record (title + 2-frame sun/moon icon)
  level_data.akr  collision boxes, orb positions and the chunk table (generated code)

Lighting is baked into vertex colours: a low warm sun in the west, a cool moon in the east,
ambient sky light, ray-cast shadows from the level boxes and a little ambient occlusion."""
import math, os, struct, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshlib import Mesh, rgb, DOUBLE, SEMI

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'carts', 'orbs')
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(1234)


def write(name, data):
    with open(os.path.join(OUT, name), 'wb') as f:
        f.write(data)


def c15(r, g, b):
    r, g, b = (int(max(0, min(255, round(v)))) for v in (r, g, b))
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)


# ----------------------------------------------------------------------------- noise

def value_noise(w, h, cells, seed, periodic=True):
    """Smooth value noise on a w x h grid with `cells` lattice cells across (tileable)."""
    r = np.random.default_rng(seed)
    lat = r.random((cells + 1, cells + 1))
    if periodic:
        lat[-1, :] = lat[0, :]
        lat[:, -1] = lat[:, 0]
    ys = np.linspace(0, cells, h, endpoint=False)
    xs = np.linspace(0, cells, w, endpoint=False)
    xi = xs.astype(int); yi = ys.astype(int)
    xf = xs - xi; yf = ys - yi
    xf = xf * xf * (3 - 2 * xf); yf = yf * yf * (3 - 2 * yf)
    a = lat[np.ix_(yi, xi)]; b = lat[np.ix_(yi, xi + 1)]
    c = lat[np.ix_(yi + 1, xi)]; d = lat[np.ix_(yi + 1, xi + 1)]
    top = a + (b - a) * xf[None, :]
    bot = c + (d - c) * xf[None, :]
    return top + (bot - top) * yf[:, None]


def fbm(w, h, seed, octaves=(2, 4, 8), weights=(0.55, 0.3, 0.15)):
    return sum(wt * value_noise(w, h, o, seed + i) for i, (o, wt) in enumerate(zip(octaves, weights)))


def ramp(stops, n=15):
    """n colours interpolated through the colour stops."""
    out = []
    for i in range(n):
        t = i / (n - 1) * (len(stops) - 1)
        k = min(int(t), len(stops) - 2)
        f = t - k
        a, b = stops[k], stops[k + 1]
        out.append(tuple(a[j] + (b[j] - a[j]) * f for j in range(3)))
    return out


def quant(v, lo=1, hi=15):
    v = np.clip(v, 0, 1)
    return (lo + np.round(v * (hi - lo))).astype(np.uint8)


# ----------------------------------------------------------------------------- 4-bit atlas

atlas4 = np.zeros((256, 256), np.uint8)       # texel indices 0-15
pal4 = [[(0, 0, 0)] * 16 for _ in range(16)]  # 16 palettes of 16 colours
CELLS = {}                                     # name -> (u0, v0, palette)


def put_cell(name, cx, cy, idx, palette, colours):
    h, w = idx.shape
    atlas4[cy * 32:cy * 32 + h, cx * 32:cx * 32 + w] = idx
    pal4[palette] = [(0, 0, 0)] + list(colours) + [(0, 0, 0)] * (15 - len(colours))
    CELLS[name] = (cx * 32, cy * 32, palette)


yy, xx = np.mgrid[0:32, 0:32]

# grass: soft noise plus vertical blade streaks
n = fbm(32, 32, 10, (4, 8, 16), (0.45, 0.35, 0.2))
blades = (rng.random((32, 32)) > 0.82) * 0.25
put_cell('grass', 0, 0, quant(n * 0.9 + blades - 0.15),
         0, ramp([(28, 52, 30), (52, 96, 40), (96, 140, 52), (150, 176, 80)]))

# grass with flowers: same base, a few pink/white flowers using the top two indices
n2 = fbm(32, 32, 20, (4, 8, 16), (0.45, 0.35, 0.2))
idx = quant(n2 * 0.9 + (rng.random((32, 32)) > 0.85) * 0.2 - 0.15, 1, 13)
for fx_, fy_ in [(5, 6), (20, 3), (13, 17), (27, 22), (7, 26), (22, 12)]:
    idx[fy_, fx_] = 15
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        idx[(fy_ + dy) % 32, (fx_ + dx) % 32] = 14
put_cell('flowers', 1, 0, idx, 1,
         ramp([(28, 52, 30), (52, 96, 40), (96, 140, 52), (150, 176, 80)], 13) + [(230, 120, 170), (255, 240, 200)])

# stone path: 2x2 flagstones with dark joints and speckle
n = fbm(32, 32, 30, (4, 8, 16), (0.4, 0.35, 0.25))
v = 0.25 + n * 0.6
slab = ((xx + (yy // 16) * 7) // 16 + yy // 16) % 3
v += slab * 0.07
joint = ((xx + (yy // 16) * 7) % 16 == 0) | (yy % 16 == 0)
v[joint] = 0.02
v += (rng.random((32, 32)) - 0.5) * 0.12
put_cell('path', 2, 0, quant(v), 2, ramp([(40, 36, 44), (110, 100, 100), (160, 150, 140), (205, 196, 176)]))

# sandstone bricks: 4 courses of 8 texels, offset every other course
course = yy // 8
bx = (xx + (course % 2) * 8) % 16
v = 0.45 + fbm(32, 32, 40, (4, 8, 16), (0.35, 0.35, 0.3)) * 0.5
v += ((xx + (course % 2) * 8) // 16 + course * 3) % 4 * 0.05
mortar = (yy % 8 == 7) | (bx == 15)
v[mortar] = 0.05
v[(yy % 8 == 0) & ~mortar] += 0.12      # light top edge of each brick
put_cell('brick', 3, 0, quant(v), 3, ramp([(48, 34, 32), (140, 92, 62), (186, 132, 84), (232, 190, 130)]))

# wooden planks: vertical boards, grain and nail dots
plank = xx // 8
grain = np.sin((yy + plank * 11) * 0.7 + np.sin(xx * 1.3 + plank) * 1.5) * 0.12
v = 0.45 + grain + fbm(32, 32, 50, (2, 8, 16), (0.3, 0.4, 0.3)) * 0.35 + (plank % 2) * 0.06
v[xx % 8 == 0] = 0.03
for py in (3, 28):
    for px in range(4, 32, 8):
        v[py, px] = 0.0
put_cell('wood', 4, 0, quant(v), 4, ramp([(36, 22, 18), (98, 60, 36), (146, 96, 56), (196, 146, 92)]))

# mossy stone blocks (columns): stone greys 1-9, moss greens 10-15
n = fbm(32, 32, 60, (4, 8, 16), (0.4, 0.35, 0.25))
block = ((yy // 11) + (xx // 16)) % 2
v = 0.3 + n * 0.55 + block * 0.08
v[(yy % 11 == 10) | (((xx + (yy // 11) * 8) % 16) == 0)] = 0.0
idx = quant(v, 1, 9)
moss = fbm(32, 32, 61, (2, 4, 16), (0.5, 0.3, 0.2)) + (31 - yy) / 31 * 0.25
mm = moss > 0.62
idx[mm] = quant((moss[mm] - 0.62) * 3, 10, 15)
put_cell('mossy', 5, 0, idx, 5,
         ramp([(36, 36, 46), (96, 96, 104), (150, 148, 150), (190, 186, 180)], 9)
         + ramp([(40, 70, 30), (80, 120, 40), (140, 170, 70)], 6))

# cap stone: large smooth slabs
n = fbm(32, 32, 70, (2, 4, 8), (0.5, 0.3, 0.2))
v = 0.35 + n * 0.5
v[(xx % 32 == 0) | (yy % 16 == 0)] = 0.05
v[(yy % 16 == 1)] += 0.15
put_cell('cap', 6, 0, quant(v), 6, ramp([(46, 40, 52), (130, 120, 126), (180, 170, 168), (226, 216, 200)]))

# water: concentric-ish wave bands. Indices are cycled by palette rotation at run time.
w = (np.sin(xx * 2 * math.pi / 32 * 2 + np.sin(yy * 2 * math.pi / 32) * 1.4) +
     np.sin(yy * 2 * math.pi / 32 * 3 + np.sin(xx * 2 * math.pi / 32 * 2) * 1.2)) * 0.25 + 0.5
widx = (1 + (np.floor(w * 15) % 15)).astype(np.uint8)
water_cols = []
for i in range(15):
    t = 0.5 + 0.5 * math.cos(i / 15 * 2 * math.pi)
    water_cols.append((40 + 60 * t ** 3, 110 + 80 * t ** 2, 150 + 90 * t))
put_cell('water', 7, 0, widx, 7, water_cols)

# player face: skin, big dark eyes with highlights, rosy cheeks
idx = np.full((32, 32), 3, np.uint8)
idx[0:9, :] = 1                         # hair fringe
idx[9:11, ::3] = 1
for ex in (8, 20):
    idx[13:22, ex:ex + 5] = 2           # eyes
    idx[14:16, ex + 1:ex + 3] = 5       # highlight
for cx_ in (5, 24):
    idx[23:25, cx_:cx_ + 4] = 4         # cheeks
idx[26, 14:18] = 2                      # mouth
put_cell('face', 0, 1, idx, 8, [(130, 66, 38), (20, 16, 30), (240, 200, 170), (240, 130, 140), (255, 255, 255)])

# hair: chestnut strands running down the head (own palette)
strands = np.sin(xx * 1.7 + np.sin(yy * 0.4) * 1.5) * 0.3 + fbm(32, 32, 77, (4, 8, 16), (0.3, 0.3, 0.4)) * 0.6
put_cell('hair', 1, 1, quant(strands + 0.25 + (31 - yy) / 31 * 0.2), 14,
         ramp([(50, 24, 20), (120, 60, 36), (180, 100, 56), (230, 160, 100)]))
put_cell('skin', 2, 1, np.full((32, 32), 3, np.uint8), 8, pal4[8][1:6])

# robe: deep indigo cloth with a hem band and small gold stars
n = fbm(32, 32, 80, (4, 8, 16), (0.4, 0.35, 0.25))
idx = quant(n * 0.6 + 0.1, 1, 9)
idx[26:30, :] = 12                     # hem band
idx[27:29, ::4] = 14
for sx, sy in [(4, 4), (14, 9), (25, 5), (9, 17), (21, 19), (29, 14)]:
    idx[sy, sx] = 15
    idx[sy - 1, sx] = idx[sy + 1, sx] = idx[sy, sx - 1] = idx[sy, (sx + 1) % 32] = 13
put_cell('robe', 3, 1, idx, 9,
         ramp([(30, 26, 80), (52, 46, 130), (80, 70, 170)], 9) + [(0, 0, 0)] * 2 +
         [(200, 150, 60), (220, 170, 80), (250, 210, 110), (255, 250, 210)])

# pool wall: glazed blue tiles
v = 0.45 + fbm(32, 32, 90, (4, 8, 16), (0.3, 0.3, 0.4)) * 0.4 + ((xx // 8 + yy // 8) % 2) * 0.1
v[(xx % 8 == 0) | (yy % 8 == 0)] = 0.05
put_cell('pooltile', 4, 1, quant(v), 10, ramp([(20, 40, 60), (40, 100, 130), (80, 160, 180), (170, 230, 230)]))

# gold trim (hat, obelisk cap): brushed metal
v = 0.3 + 0.5 * (np.sin(yy * 0.9 + xx * 0.2) * 0.5 + 0.5) * 0.5 + fbm(32, 32, 95, (4, 8, 16), (0.3, 0.3, 0.4)) * 0.5
put_cell('gold', 5, 1, quant(v), 11, ramp([(90, 50, 20), (200, 130, 40), (250, 200, 90), (255, 250, 210)]))

# halo: 64x64 radial glow at (192, 192), greyscale ramp (tinted per polygon), 0 outside
hy, hx = np.mgrid[0:64, 0:64]
r = np.hypot(hx - 31.5, hy - 31.5) / 32.0
g = np.clip(1 - r, 0, 1) ** 1.6
hidx = np.where(r < 1.0, quant(g, 1, 15), 0).astype(np.uint8)
atlas4[192:256, 192:256] = hidx
pal4[12] = [(0, 0, 0)] + ramp([(8, 8, 8), (70, 70, 70), (170, 170, 170), (255, 255, 255)])
CELLS['halo'] = (192, 192, 12)

# sparkle: four-pointed star at (160, 224), same palette as the halo
sy, sx = np.mgrid[0:32, 0:32]
dx = np.abs(sx - 15.5); dy = np.abs(sy - 15.5)
star = np.clip(1 - (dx * dy) ** 0.5 / 3.2 - np.hypot(dx, dy) / 22, 0, 1)
atlas4[224:256, 160:192] = np.where(star > 0.02, quant(star, 1, 15), 0)
CELLS['sparkle'] = (160, 224, 12)

# blob shadow: a flat disc with a soft rim at (64, 224), same grey palette
br = np.hypot(sx - 15.5, sy - 15.5) / 16.0
blob = np.clip((1 - br) * 2.6, 0, 1) ** 0.8
atlas4[224:256, 64:96] = np.where(br < 1.0, quant(blob, 1, 15), 0)
CELLS['blob'] = (64, 224, 12)

# HUD icons (16x16): a sun at (0, 224) and a crescent moon at (16, 224), palette 13
iy, ix = np.mgrid[0:16, 0:16]
ir = np.hypot(ix - 7.5, iy - 7.5)
ang = np.arctan2(iy - 7.5, ix - 7.5)
sun = np.zeros((16, 16), np.uint8)
rays = (ir < 7.6) & (np.cos(ang * 8) > 0.55) & (ir > 5)
sun[rays] = 3
sun[ir < 5.2] = 4
sun[ir < 3.6] = 5
sun[(ir < 5.2) & (ir > 4.3)] = 2
atlas4[224:240, 0:16] = sun
moon = np.zeros((16, 16), np.uint8)
disc = ir < 6.8
cut = np.hypot(ix - 10.5, iy - 5.0) < 5.6
moon[disc & ~cut] = 7
moon[disc & ~cut & (np.hypot(ix - 6, iy - 9) < 3.5)] = 8
moon[disc & ~cut & (ir > 6.0)] = 6
atlas4[224:240, 16:32] = moon
pal4[13] = [(0, 0, 0), (0, 0, 0), (200, 90, 30), (250, 160, 50), (255, 210, 80), (255, 250, 200),
            (120, 140, 200), (210, 225, 255), (170, 185, 230)] + [(0, 0, 0)] * 7
CELLS['icon_sun'] = (0, 224, 13)
CELLS['icon_moon'] = (16, 224, 13)

# memory card save icon: the same sun and moon as two animation frames
from mei_icon import make_meta
write('save_icon.bin', make_meta([sun, moon], title='Sun & Moon Orbs', palette=pal4[13][:9]))

# pack: two texels per byte, the low nibble is the left texel; 128-byte rows
tex4 = (atlas4[:, 0::2] & 15) | ((atlas4[:, 1::2] & 15) << 4)
write('tex4.bin', tex4.astype(np.uint8).tobytes())

# Coarse-LOD copies (slot 1): each tiling material as a 64x64 cell holding its 32x32 cell
# repeated 2x2. Coarse tiles are 4 units wide, so they keep 16 texels per unit like the
# fine 2-unit tiles (the GPU has no texture repeat). Same palettes as the fine cells.
COARSE_MATS = ('grass', 'flowers', 'path', 'brick', 'wood', 'mossy', 'cap', 'pooltile', 'gold')
atlas4b = np.zeros((256, 256), np.uint8)
CELLS_LO = {}
for i, name in enumerate(COARSE_MATS):
    u0, v0, pal = CELLS[name]
    cx, cy = (i % 4) * 64, (i // 4) * 64
    atlas4b[cy:cy + 64, cx:cx + 64] = np.tile(atlas4[v0:v0 + 32, u0:u0 + 32], (2, 2))
    CELLS_LO[name] = (cx, cy, pal)
tex4b = (atlas4b[:, 0::2] & 15) | ((atlas4b[:, 1::2] & 15) << 4)
write('tex4b.bin', tex4b.astype(np.uint8).tobytes())
write('pal4.bin', struct.pack('<256H', *[c15(*c) for p in pal4 for c in p]))


# ----------------------------------------------------------------------------- 8-bit texture

from PIL import Image

tex8 = np.zeros((256, 256), np.uint8)
pal8 = {}            # 8-bit palette number -> list of 256 RGB


def quantize_into(rgba, x0, y0, palette, ncol=255):
    """Quantizes an RGBA float image (0-255) into tex8 at (x0, y0) with 8-bit palette
    `palette` (index 0 = transparent where alpha < 128)."""
    h, w = rgba.shape[:2]
    rgb_ = np.clip(rgba[..., :3], 0, 255).astype(np.uint8)
    opaque = rgba[..., 3] >= 128
    im = Image.fromarray(rgb_, 'RGB')
    q = im.quantize(colors=ncol, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    qi = np.array(q, np.uint8).astype(np.int32) + 1
    qi[~opaque] = 0
    tex8[y0:y0 + h, x0:x0 + w] = qi
    pl = q.getpalette()[:ncol * 3]
    cols = [(0, 0, 0)] + [tuple(pl[i * 3:i * 3 + 3]) for i in range(len(pl) // 3)]
    cols += [(0, 0, 0)] * (256 - len(cols))
    return cols


def periodic_ridge(width, seed, freqs, amps):
    r = np.random.default_rng(seed)
    x = np.arange(width) / width * 2 * math.pi
    h = np.zeros(width)
    for f, a in zip(freqs, amps):
        h += a * np.sin(f * x + r.random() * 2 * math.pi)
        h += a * 0.5 * np.abs(np.sin(f * 2.3 * x + r.random() * 6))
    return h


# mountain panorama: 256 x 64, repeats twice around the ring; layers far -> near
W8, H8 = 256, 64
img = np.zeros((H8, W8, 4))
ys_ = np.arange(H8)[:, None]
layers = [
    # base row, amplitude scale, freqs, colour top, colour bottom
    (26, 1.0, (2, 5, 9, 17), (132, 104, 150), (110, 92, 140)),
    (36, 0.8, (3, 7, 13, 23), (88, 70, 118), (66, 56, 100)),
    (45, 0.55, (4, 9, 19, 31), (52, 44, 82), (38, 34, 64)),
]
for li, (base, sc, fr, ct, cb) in enumerate(layers):
    ridge = base - periodic_ridge(W8, 300 + li, fr, (6 * sc, 3 * sc, 1.6 * sc, 0.8 * sc))
    mask = ys_ >= ridge[None, :]
    t = np.clip((ys_ - ridge[None, :]) / 22.0, 0, 1)
    col = np.array(ct)[None, None, :] * (1 - t[..., None]) + np.array(cb)[None, None, :] * t[..., None]
    # snow caps on the far range, lit rim on the left (sun side) of each peak
    if li == 0:
        snow = (ys_ - ridge[None, :] < 3) & (ridge[None, :] < 20)
        col[snow] = (220, 200, 220)
    rim = np.gradient(ridge)
    lit = (ys_ - ridge[None, :] < 2.5) & (rim[None, :] > 0.25)
    col[lit] = col[lit] * 0.6 + np.array((250, 170, 120)) * 0.4
    tex = fbm(W8, H8, 310 + li, (8, 16, 32), (0.4, 0.35, 0.25))
    col = col * (0.88 + tex[..., None] * 0.24)
    img[..., :3] = np.where(mask[..., None], col, img[..., :3])
    img[..., 3] = np.where(mask, 255, img[..., 3])
# a band of evening mist and dark treeline at the bottom
mist = np.clip((ys_ - 50) / 14.0, 0, 1)[..., None]
img[..., :3] = img[..., :3] * (1 - mist * 0.5) + np.array((96, 72, 110)) * mist * 0.5
trees = 56 - (np.abs(np.sin(np.arange(W8) * 0.9)) * 3 + np.abs(np.sin(np.arange(W8) * 2.7)) * 2)
tmask = ys_ >= trees[None, :]
img[..., :3] = np.where(tmask[..., None], np.array((26, 22, 40)), img[..., :3])
img[..., 3] = np.where(tmask, 255, img[..., 3])
pal8[1] = quantize_into(img, 0, 0, 1, 200)
RING_V0, RING_V1 = 0, 63

# sun & moon emblem mosaic for the pool floor: 128x128 at (0, 64), palette 2
M = 128
my, mx = np.mgrid[0:M, 0:M].astype(float)
cxm, cym = 63.5, 63.5
rr = np.hypot(mx - cxm, my - cym)
aa = np.arctan2(my - cym, mx - cxm)
mos = np.zeros((M, M, 3))
mos[:] = (36, 92, 120)                                          # teal ground
mos[(rr > 54) & (rr < 60)] = (230, 200, 120)                    # outer gold ring
mos[(rr > 50) & (rr < 54)] = (20, 50, 80)
west = mx < cxm
# sun half: rays and disc
sunr = (rr < 46) & west & (np.cos(aa * 12) > 0.3) & (rr > 26)
mos[sunr] = (240, 150, 50)
mos[(rr < 24) & west] = (250, 200, 80)
mos[(rr < 16) & west] = (255, 240, 170)
# moon half: night blue with a crescent and stars
mos[(rr < 48) & ~west & ~((rr > 26) & (np.cos(aa * 12) > 0.3) & False)] = (24, 30, 80)
cres = (np.hypot(mx - 80, my - cym) < 24) & ~(np.hypot(mx - 90, my - 56) < 20)
mos[cres] = (210, 220, 250)
for sx_, sy_ in [(100, 30), (110, 80), (78, 100), (96, 104), (70, 28)]:
    mos[(np.abs(mx - sx_) + np.abs(my - sy_) < 3.2)] = (255, 250, 200)
mos[(np.abs(mx - cxm) < 1.5) & (rr < 50)] = (230, 200, 120)    # dividing line
# tesserae: jitter each 4x4 tile's colour, dark grout lines
tile_j = rng.random((M // 4, M // 4)) * 0.25 + 0.85
mos *= np.kron(tile_j, np.ones((4, 4)))[..., None]
grout = (mx % 4 == 0) | (my % 4 == 0)
mos[grout] *= 0.45
mosa = np.concatenate([mos, np.full((M, M, 1), 255.0)], axis=2)
pal8[2] = quantize_into(mosa, 0, 64, 2, 255)
MOSAIC = (0, 64)

# sun disc (64x64 at (128, 64)) and crescent moon (64x64 at (192, 64)), palette 3
sy8, sx8 = np.mgrid[0:64, 0:64].astype(float)
r8 = np.hypot(sx8 - 31.5, sy8 - 31.5) / 31.5
sunimg = np.zeros((64, 64, 4))
t = np.clip(r8, 0, 1)
sunimg[..., 0] = 255
sunimg[..., 1] = 250 - 140 * t ** 1.5
sunimg[..., 2] = 210 - 190 * t ** 0.8
bands = (np.abs(sy8 - 40) < 1.5) | (np.abs(sy8 - 48) < 1.2) | (np.abs(sy8 - 54) < 1.0)
sunimg[..., 3] = np.where((r8 < 1.0) & ~bands, 255, 0)
moonimg = np.zeros((64, 64, 4))
mdisc = r8 < 1.0
mcut = np.hypot(sx8 - 44, sy8 - 22) / 31.5 < 0.86
cr = fbm(64, 64, 500, (4, 8, 16), (0.4, 0.35, 0.25))
shade = 0.65 + 0.35 * np.clip((40 - sx8) / 40, 0, 1)
moonimg[..., 0] = (190 + cr * 60) * shade
moonimg[..., 1] = (200 + cr * 55) * shade
moonimg[..., 2] = (235 + cr * 20) * shade
for ccx, ccy, cr_ in [(16, 30, 5), (24, 46, 4), (12, 42, 3), (28, 54, 3)]:
    crater = np.hypot(sx8 - ccx, sy8 - ccy) < cr_
    moonimg[crater, :3] *= 0.78
moonimg[..., 3] = np.where(mdisc & ~mcut, 255, 0)
both = np.concatenate([sunimg, moonimg], axis=1)
pal8[3] = quantize_into(both, 128, 64, 3, 255)
SUN_UV = (128, 64)
MOON_UV = (192, 64)

write('tex8.bin', tex8.tobytes())
pal8_words = []
for p in (1, 2, 3):
    pal8_words += [c15(*c) for c in pal8[p]]
write('pal8.bin', struct.pack('<%dH' % len(pal8_words), *pal8_words))


# ----------------------------------------------------------------------------- level

# materials: name -> (u0, v0, slot, four_bit, palette, texels per unit)
def mat4b(cell):
    u0, v0, p = CELLS[cell]
    return (u0, v0, 0, True, p, 16)


MATS = {k: mat4b(k) for k in ('grass', 'flowers', 'path', 'brick', 'wood', 'mossy', 'cap', 'pooltile', 'gold')}
MATS['mosaic'] = (MOSAIC[0], MOSAIC[1], 2, False, 2, 16)

POOL = (-4.0, -2.0, 4.0, 6.0)      # x0, z0, x1, z1
POOL_FLOOR = -1.4
WATER_Y = -0.3

# Collision boxes: (x0, y0, z0, x1, y1, z1). Rendering is described separately below.
boxes = []


def box(x0, y0, z0, x1, y1, z1):
    boxes.append((x0, y0, z0, x1, y1, z1))


# ground around the pool and the pool floor
box(-14, -3, -14, 14, 0, -2)
box(-14, -3, 6, 14, 0, 14)
box(-14, -3, -2, -4, 0, 6)
box(4, -3, -2, 14, 0, 6)
box(-4, -3, -2, 4, POOL_FLOOR, 6)
# perimeter walls
WALL_H = 2.5
box(-15, -3, -15, 15, WALL_H, -14)
box(-15, -3, 14, 15, WALL_H, 15)
box(-15, -3, -14, -14, WALL_H, 14)
box(14, -3, -14, 15, WALL_H, 14)
# east staircase of platforms
PLATFORMS = [(7, -11, 11, -7, 1.0, 'path', 'brick'),
             (9, -5, 13, -1, 2.0, 'path', 'brick'),
             (9, 1, 13, 5, 3.0, 'cap', 'brick'),
             (6, 7, 10, 11, 4.0, 'wood', 'wood')]
for x0, z0, x1, z1, top, _, _ in PLATFORMS:
    box(x0, 0, z0, x1, top, z1)
# stepping stones in the pool
STONES = [(-2.5, 0.5, 0.2), (0.0, 2.5, 0.2), (2.4, 4.4, 0.2)]
for sx_, sz_, top in STONES:
    box(sx_ - 0.6, POOL_FLOOR, sz_ - 0.6, sx_ + 0.6, top, sz_ + 0.6)
# west column stair (climbable) and tall pillars (obstacles)
COLUMNS = [(-9.5, -9.0, 0.9), (-11.5, -6.5, 1.8), (-9.5, -4.0, 2.7), (-11.5, -1.5, 3.6)]
for cx_, cz_, top in COLUMNS:
    box(cx_ - 0.7, 0, cz_ - 0.7, cx_ + 0.7, top, cz_ + 0.7)
PILLARS = [(-7.0, 5.0), (-7.0, 10.5), (-11.5, 10.5), (-11.5, 5.0)]
PILLAR_H = 4.6
for px_, pz_ in PILLARS:
    box(px_ - 0.6, 0, pz_ - 0.6, px_ + 0.6, PILLAR_H, pz_ + 0.6)
# the shrine in the north: a stepped plinth with a gold-capped obelisk
SHRINE = (0.0, 10.5)
box(-2.0, 0, 8.5, 2.0, 0.5, 12.5)
box(-0.6, 0.5, 9.9, 0.6, 3.2, 11.1)

ORBS = [  # x, y, z, kind (0 sun, 1 moon)
    (0.0, 0.9, -4.6, 0),
    (9.0, 1.9, -9.0, 1),
    (11.0, 2.9, -3.0, 0),
    (11.0, 3.9, 3.0, 1),
    (8.0, 4.9, 9.0, 0),
    (-2.5, 1.1, 0.5, 1),
    (2.0, -0.85, 1.0, 0),
    (-11.5, 4.5, -1.5, 1),
    (-9.25, 0.9, 7.75, 0),
    (-12.3, 0.9, -12.3, 1),
]
START = (0.0, 0.0, -8.5)


# ---- baked lighting

def norm(v):
    l = math.sqrt(sum(c * c for c in v))
    return tuple(c / l for c in v)


SUN_DIR = norm((-0.8, 0.42, -0.3))      # toward the sun (west, low)
MOON_DIR = norm((0.7, 0.6, 0.35))       # toward the moon (east)
SUN_COL = (1.05, 0.70, 0.45)
MOON_COL = (0.32, 0.40, 0.62)
AMB = (0.42, 0.40, 0.52)


def ray_hits(o, d, skip=None):
    for bi, b in enumerate(boxes):
        if bi == skip:
            continue
        tmin, tmax = 1e-4, 1e9
        ok = True
        for k in range(3):
            lo, hi = b[k], b[k + 3]
            if abs(d[k]) < 1e-9:
                if o[k] < lo or o[k] > hi:
                    ok = False
                    break
            else:
                t1 = (lo - o[k]) / d[k]
                t2 = (hi - o[k]) / d[k]
                if t1 > t2:
                    t1, t2 = t2, t1
                tmin = max(tmin, t1)
                tmax = min(tmax, t2)
                if tmin > tmax:
                    ok = False
                    break
        if ok:
            return True
    return False


def ao_at(p, n):
    """Cheap ambient occlusion: fraction of a few upward-hemisphere rays that escape."""
    dirs = [(0, 1, 0), (0.7, 0.7, 0), (-0.7, 0.7, 0), (0, 0.7, 0.7), (0, 0.7, -0.7),
            (0.5, 0.4, 0.5), (-0.5, 0.4, 0.5), (0.5, 0.4, -0.5), (-0.5, 0.4, -0.5)]
    o = tuple(p[i] + n[i] * 0.05 for i in range(3))
    free = 0
    tot = 0
    for d in dirs:
        d = norm(d)
        if sum(d[i] * n[i] for i in range(3)) <= 0.05:
            continue
        tot += 1
        # only nearby occluders matter: test a short segment
        hit = False
        for b in boxes:
            if ray_box_t(o, d, b) < 2.2:
                hit = True
                break
        free += 0 if hit else 1
    return free / tot if tot else 1.0


def ray_box_t(o, d, b):
    tmin, tmax = 1e-4, 1e9
    for k in range(3):
        lo, hi = b[k], b[k + 3]
        if abs(d[k]) < 1e-9:
            if o[k] < lo or o[k] > hi:
                return 1e9
        else:
            t1 = (lo - o[k]) / d[k]
            t2 = (hi - o[k]) / d[k]
            if t1 > t2:
                t1, t2 = t2, t1
            tmin = max(tmin, t1)
            tmax = min(tmax, t2)
            if tmin > tmax:
                return 1e9
    return tmin


def hash3(p):
    h = math.sin(p[0] * 12.9898 + p[1] * 78.233 + p[2] * 37.719) * 43758.5453
    return h - math.floor(h)


def light(p, n, emissive=None):
    o = tuple(p[i] + n[i] * 0.04 for i in range(3))
    c = list(AMB)
    ao = 0.45 + 0.55 * ao_at(p, n)
    c = [ci * ao for ci in c]
    ds = sum(n[i] * SUN_DIR[i] for i in range(3))
    if ds > 0 and not ray_hits(o, SUN_DIR):
        c = [c[i] + SUN_COL[i] * ds for i in range(3)]
    dm = sum(n[i] * MOON_DIR[i] for i in range(3))
    if dm > 0 and not ray_hits(o, MOON_DIR):
        c = [c[i] + MOON_COL[i] * dm for i in range(3)]
    # warm glow around the shrine, cool glow up from the pool
    ds_ = math.hypot(p[0] - SHRINE[0], p[2] - SHRINE[1])
    g = max(0.0, 1 - ds_ / 6.0) ** 2 * 0.5
    c = [c[0] + g * 1.0, c[1] + g * 0.7, c[2] + g * 0.3]
    if POOL[0] - 1.5 < p[0] < POOL[2] + 1.5 and POOL[1] - 1.5 < p[2] < POOL[3] + 1.5 and p[1] < 0.3:
        c = [c[0] + 0.0, c[1] + 0.12, c[2] + 0.22]
    j = 0.92 + 0.16 * hash3(p)
    return rgb(*[int(max(16, min(255, 128 * ci * j))) for ci in c])


# ---- face emission
#
# The level is built twice: a fine version (2-unit tiles, 16 texels per unit) and a coarse
# one (4-unit tiles, 8 texels per unit) for chunks away from the camera. Tiles are cut at
# absolute multiples of the tile size, and chunk borders lie on multiples of 4, so a fine
# chunk always meets a coarse neighbour along the same line.

chunks = {}
STEP = 2.0
_light_cache = {}


def chunk_of(cx, cz):
    i = 0 if cx < -4 else (1 if cx < 4 else 2)
    j = 0 if cz < -4 else (1 if cz < 4 else 2)
    return j * 3 + i


def lit(p, n):
    key = (tuple(round(c, 4) for c in p), n)
    if key not in _light_cache:
        _light_cache[key] = light(p, n)
    return _light_cache[key]


class Builder:
    def __init__(self):
        self.mesh = Mesh()
        self.vmap = {}
        self.pts = []

    def v(self, p):
        # positions are shared between faces (colours belong to the faces), which cuts the
        # vertex transforms of a tiled surface to about a quarter
        key = tuple(round(c, 4) for c in p)
        if key not in self.vmap:
            self.pts.append(p)
            self.vmap[key] = self.mesh.vertex(*p)
        return self.vmap[key]


def segments(length, start_offset, step):
    """Splits [0, length] at multiples of `step` measured from -start_offset."""
    cuts = [0.0]
    k = math.floor(start_offset / step + 1e-9) + 1
    while True:
        c = k * step - start_offset
        if c >= length - 1e-6:
            break
        if c > 1e-6:
            cuts.append(c)
        k += 1
    cuts.append(length)
    return cuts


def axis_offset(origin, ax, step):
    """Offset that aligns cuts along `ax` to absolute multiples of step."""
    a0 = sum(origin[i] * abs(ax[i]) for i in range(3))
    sgn = sum(ax)
    return (a0 % step) if sgn > 0 else ((-a0) % step)


def emit_rect(origin, uax, vax, ulen, vlen, normal, mat, chunk=None, absolute_v=False):
    """Emits a rectangle cut into tiles. uax/vax: unit vectors (right and up as seen from
    the front). Texture coordinates follow world distance along the axes."""
    u0, v0, slot, four, pal, _ = MATS[mat]
    step = STEP
    cell = 32                       # texels per tile edge (the tile is `step` units)
    if step == 4.0 and mat != 'mosaic':
        u0, v0, pal = CELLS_LO[mat]
        slot, cell = 1, 64
    tpu = 16                        # texels per unit: the same for both LODs
    uoff = axis_offset(origin, uax, step)
    voff = axis_offset(origin, vax, step) if absolute_v else 0.0
    cu = segments(ulen, uoff, step)
    cv = segments(vlen, voff, step)
    for a in range(len(cu) - 1):
        for b in range(len(cv) - 1):
            s0, s1, t0, t1 = cu[a], cu[a + 1], cv[b], cv[b + 1]
            corners = ((s0, t0), (s1, t0), (s0, t1), (s1, t1))
            pts = [tuple(origin[i] + uax[i] * s + vax[i] * t for i in range(3)) for s, t in corners]
            cx = sum(p[0] for p in pts) / 4
            cz = sum(p[2] for p in pts) / 4
            ch = chunk if chunk is not None else chunk_of(cx, cz)
            bld = chunks.setdefault(ch, Builder())
            idx = [bld.v(p) for p in pts]
            cols = [lit(p, normal) for p in pts]
            if mat == 'mosaic':   # the emblem glows a little so it reads through the water
                cols = [rgb(*[min(255, int(((c >> sh) & 255) * 1.7) + 12) for sh in (0, 8, 16)]) for c in cols]
            uvs = []
            if mat == 'mosaic':
                for s, t in corners:
                    uu = min(127, int(round(s * tpu)))
                    vv = min(127, int(round((vlen - t) * tpu)))
                    uvs.append((u0 + uu, v0 + vv))
            else:
                base_s = math.floor((s0 + uoff) / step + 1e-6) * step
                base_t = math.floor((t0 + voff) / step + 1e-6) * step
                for s, t in corners:
                    uu = min(cell - 1, int(round((s + uoff - base_s) * tpu)))
                    vv = min(cell - 1, int(round((t + voff - base_t) * tpu)))
                    uvs.append((u0 + uu, v0 + cell - 1 - vv))
            bld.mesh.quad(idx, cols, uvs, slot=slot, four_bit=four, palette=pal)


X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
NX, NZ = (-1, 0, 0), (0, 0, -1)


def top(x0, z0, x1, z1, y, mat, **kw):
    emit_rect((x0, y, z0), X, Z, x1 - x0, z1 - z0, Y, mat, absolute_v=True, **kw)


def side(face, x0, z0, x1, z1, yb, yt, mat, **kw):
    h = yt - yb
    if face == '-z':
        emit_rect((x0, yb, z0), X, Y, x1 - x0, h, NZ, mat, **kw)
    elif face == '+z':
        emit_rect((x1, yb, z1), NX, Y, x1 - x0, h, Z, mat, **kw)
    elif face == '-x':
        emit_rect((x0, yb, z1), NZ, Y, z1 - z0, h, NX, mat, **kw)
    elif face == '+x':
        emit_rect((x1, yb, z0), Z, Y, z1 - z0, h, X, mat, **kw)


def column(x0, z0, x1, z1, yb, yt, topmat, sidemat, faces=('-z', '+z', '-x', '+x')):
    top(x0, z0, x1, z1, yt, topmat)
    for f in faces:
        side(f, x0, z0, x1, z1, yb, yt, sidemat)


# ground: grass with a stone path from the start to the pool and the shrine
def ground_mat(cx, cz):
    if abs(cx) < 1.5 and (cz < POOL[1] or cz > POOL[3]):
        return 'path'
    return 'flowers' if hash3((cx, 0, cz)) > 0.82 else 'grass'


def ground_area(x0, z0, x1, z1):
    gx = math.floor(x0 / STEP) * STEP
    while gx < x1 - 1e-6:
        gz = math.floor(z0 / STEP) * STEP
        while gz < z1 - 1e-6:
            a, b = max(gx, x0), min(gx + STEP, x1)
            c, d = max(gz, z0), min(gz + STEP, z1)
            top(a, c, b, d, 0.0, ground_mat((a + b) / 2, (c + d) / 2))
            gz += STEP
        gx += STEP


def build_level():
    ground_area(-14, -14, 14, -2)
    ground_area(-14, 6, 14, 14)
    ground_area(-14, -2, -4, 6)
    ground_area(4, -2, 14, 6)
    # pool: mosaic floor and tiled walls
    px0, pz0, px1, pz1 = POOL
    emit_rect((px0, POOL_FLOOR, pz0), X, Z, px1 - px0, pz1 - pz0, Y, 'mosaic', chunk=9)
    side('+z', px0, pz0 - 1, px1, pz0, POOL_FLOOR, 0, 'pooltile', chunk=9)   # south wall faces +z
    side('-z', px0, pz1, px1, pz1 + 1, POOL_FLOOR, 0, 'pooltile', chunk=9)   # north wall faces -z
    side('+x', px0 - 1, pz0, px0, pz1, POOL_FLOOR, 0, 'pooltile', chunk=9)
    side('-x', px1, pz0, px1 + 1, pz1, POOL_FLOOR, 0, 'pooltile', chunk=9)
    # walls: inner face and top
    side('+z', -14, -15, 14, -14, 0, WALL_H, 'brick')
    side('-z', -14, 14, 14, 15, 0, WALL_H, 'brick')
    side('+x', -15, -14, -14, 14, 0, WALL_H, 'brick')
    side('-x', 14, -14, 15, 14, 0, WALL_H, 'brick')
    top(-15, -15, 15, -14, WALL_H, 'cap')
    top(-15, 14, 15, 15, WALL_H, 'cap')
    top(-15, -14, -14, 14, WALL_H, 'cap')
    top(14, -14, 15, 14, WALL_H, 'cap')
    for x0, z0, x1, z1, t, tm, sm in PLATFORMS:
        column(x0, z0, x1, z1, 0, t, tm, sm)
    for sx_, sz_, t in STONES:
        column(sx_ - 0.6, sz_ - 0.6, sx_ + 0.6, sz_ + 0.6, POOL_FLOOR, t, 'cap', 'mossy')
    for cx_, cz_, t in COLUMNS:
        column(cx_ - 0.7, cz_ - 0.7, cx_ + 0.7, cz_ + 0.7, 0, t, 'cap', 'mossy')
    for px_, pz_ in PILLARS:
        column(px_ - 0.6, pz_ - 0.6, px_ + 0.6, pz_ + 0.6, 0, PILLAR_H, 'cap', 'mossy')
    column(-2.0, 8.5, 2.0, 12.5, 0, 0.5, 'path', 'cap')
    column(-0.6, 9.9, 0.6, 11.1, 0.5, 3.2, 'gold', 'brick')


chunk_info = []
for STEP, suffix in ((2.0, ''), (4.0, '_lo')):
    chunks = {}
    build_level()
    for ch in sorted(chunks):
        b = chunks[ch]
        write('chunk%d%s.bin' % (ch, suffix), b.mesh.pack())
        pts = np.array(b.pts)
        lo_, hi_ = pts.min(0), pts.max(0)
        c = (lo_ + hi_) / 2
        r = float(np.max(np.linalg.norm(pts - c, axis=1)))
        if suffix == '':
            chunk_info.append([ch, c, r, len(b.mesh.verts), len(b.mesh.faces), lo_, hi_, 0, 0])
        else:
            ci = [x for x in chunk_info if x[0] == ch][0]
            ci[7], ci[8] = len(b.mesh.verts), len(b.mesh.faces)

# water surface: semi-transparent (mode 0), Gouraud: brighter toward the middle
px0, pz0, px1, pz1 = POOL
wm = Mesh()
for i in range(4):
    for j in range(4):
        x0 = px0 + i * 2; z0 = pz0 + j * 2
        pts = [(x0, WATER_Y, z0), (x0 + 2, WATER_Y, z0), (x0, WATER_Y, z0 + 2), (x0 + 2, WATER_Y, z0 + 2)]
        idx = [wm.vertex(*p) for p in pts]
        cols = []
        for p in pts:
            d = math.hypot(p[0] - 0, p[2] - 2) / 5.7
            k = 1.15 - 0.35 * d
            cols.append(rgb(int(110 * k), int(140 * k), int(160 * k)))
        u0, v0, pal = CELLS['water']
        wm.quad(idx, cols, [(u0, v0 + 31), (u0 + 31, v0 + 31), (u0, v0), (u0 + 31, v0)],
                flags=SEMI, slot=0, four_bit=True, palette=pal, blend=0)
write('water.bin', wm.pack())

# mountain ring: 32 segments, radius 50, texture wraps twice; faces inward
ring = Mesh()
RING_R, RING_TOP, RING_BOT = 50.0, 13.0, -22.0
SEG = 32
for i in range(SEG):
    a0 = i / SEG * 2 * math.pi
    a1 = (i + 1) / SEG * 2 * math.pi
    pts = [(math.sin(a0) * RING_R, RING_BOT, math.cos(a0) * RING_R),
           (math.sin(a1) * RING_R, RING_BOT, math.cos(a1) * RING_R),
           (math.sin(a0) * RING_R, RING_TOP, math.cos(a0) * RING_R),
           (math.sin(a1) * RING_R, RING_TOP, math.cos(a1) * RING_R)]
    idx = [ring.vertex(*p) for p in pts]
    ua = (i % 16) * 16
    ub = min(255, ua + 16)
    ring.quad(idx, [rgb(128, 128, 128)], [(ua, RING_V1), (ub, RING_V1), (ua, RING_V0), (ub, RING_V0)],
              slot=2, four_bit=False, palette=1)
write('ring.bin', ring.pack())


# ----------------------------------------------------------------------------- characters

def shade_col(base, n, bright=1.0):
    c = list(AMB)
    ds = max(0, sum(n[i] * SUN_DIR[i] for i in range(3)))
    dm = max(0, sum(n[i] * MOON_DIR[i] for i in range(3)))
    c = [c[i] + SUN_COL[i] * ds + MOON_COL[i] * dm for i in range(3)]
    return rgb(*[int(max(0, min(255, base[i] * c[i] * bright))) for i in range(3)])


def tex_quad(m, pts, cell, base=(128, 128, 128), span=31, bright=1.0):
    """A textured quad (strip order) lit by its normal."""
    a, b, c, d = pts
    e1 = [b[i] - a[i] for i in range(3)]
    e2 = [c[i] - a[i] for i in range(3)]
    n = norm((e2[1] * e1[2] - e2[2] * e1[1], e2[2] * e1[0] - e2[0] * e1[2], e2[0] * e1[1] - e2[1] * e1[0]))
    idx = [m.vertex(*p) for p in pts]
    cols = [shade_col(base, n, bright * (1.1 if p[1] > (a[1] + c[1]) / 2 else 0.9)) for p in pts]
    u0, v0, pal = CELLS[cell]
    m.quad(idx, cols, [(u0, v0 + span), (u0 + span, v0 + span), (u0, v0), (u0 + span, v0)],
           slot=0, four_bit=True, palette=pal)


def tex_tri(m, pts, cell, base=(128, 128, 128), uvs=None):
    a, b, c = pts
    e1 = [b[i] - a[i] for i in range(3)]
    e2 = [c[i] - a[i] for i in range(3)]
    n = norm((e2[1] * e1[2] - e2[2] * e1[1], e2[2] * e1[0] - e2[0] * e1[2], e2[0] * e1[1] - e2[1] * e1[0]))
    idx = [m.vertex(*p) for p in pts]
    cols = [shade_col(base, n, 1.15 if k == 2 else 0.95) for k, p in enumerate(pts)]
    u0, v0, pal = CELLS[cell]
    uvs = uvs or [(0, 31), (31, 31), (15, 0)]
    m.tri(idx, cols, [(u0 + u, v0 + v) for u, v in uvs], slot=0, four_bit=True, palette=pal)


def ring_pts(r, y, k, phase=0.0):
    return [(math.sin(phase + i / k * 2 * math.pi) * r, y, math.cos(phase + i / k * 2 * math.pi) * r) for i in range(k)]


player = Mesh()
# robe: hexagonal frustum, front panel facing +Z
K = 6
lo = ring_pts(0.40, 0.08, K, math.pi / K)
hi = ring_pts(0.20, 0.78, K, math.pi / K)
for i in range(K):
    j = (i + 1) % K
    # seen from outside: BL = lo[j], BR = lo[i]? angles increase toward +X (clockwise from
    # above); from outside, increasing angle runs right-to-left, so BL is the later vertex.
    tex_quad(player, [lo[j], lo[i], hi[j], hi[i]], 'robe', (150, 150, 170))
# a little cape collar: gold band triangle fan under the head
collar = ring_pts(0.27, 0.74, K, math.pi / K)
for i in range(K):
    j = (i + 1) % K
    tex_tri(player, [collar[j], collar[i], (0, 0.82, 0)], 'gold', (130, 120, 110), [(0, 20), (31, 20), (15, 0)])
# head: a cube with the face texture on +Z
hx0, hx1, hy0, hy1, hz0, hz1 = -0.24, 0.24, 0.78, 1.24, -0.22, 0.24
# the face is seen from +Z looking -Z, so its right-hand side is -X
tex_quad(player, [(hx1, hy0, hz1), (hx0, hy0, hz1), (hx1, hy1, hz1), (hx0, hy1, hz1)], 'face', (170, 160, 160))
tex_quad(player, [(hx0, hy0, hz0), (hx1, hy0, hz0), (hx0, hy1, hz0), (hx1, hy1, hz0)], 'hair', (150, 150, 150))
tex_quad(player, [(hx0, hy0, hz1), (hx0, hy0, hz0), (hx0, hy1, hz1), (hx0, hy1, hz0)], 'hair', (150, 150, 150))
tex_quad(player, [(hx1, hy0, hz0), (hx1, hy0, hz1), (hx1, hy1, hz0), (hx1, hy1, hz1)], 'hair', (150, 150, 150))
tex_quad(player, [(hx0, hy1, hz0), (hx1, hy1, hz0), (hx0, hy1, hz1), (hx1, hy1, hz1)], 'hair', (150, 150, 150))
# hat: a wide brim (double-sided flat ring) and a gold cone with a crescent tilt
brim = ring_pts(0.42, 1.2, 8)
tip = (0.0, 1.78, -0.16)
cone = ring_pts(0.26, 1.2, 8)
for i in range(8):
    j = (i + 1) % 8
    tex_tri(player, [cone[j], cone[i], tip], 'robe', (130, 130, 160), [(0, 25), (31, 25), (15, 0)])
    tex_quad(player, [brim[j], brim[i], cone[j], cone[i]], 'robe', (120, 120, 150))
# a gold star at the hat tip (double-sided diamond)
st = [(0, 1.70, -0.16), (0.09, 1.80, -0.16), (-0.09, 1.80, -0.16), (0, 1.92, -0.16)]
si = [player.vertex(*p) for p in st]
gu, gv, gp = CELLS['gold']
player.quad(si, [rgb(255, 230, 140)], [(gu, gv + 31), (gu + 31, gv + 31), (gu, gv), (gu + 31, gv)],
            flags=DOUBLE, slot=0, four_bit=True, palette=gp)
write('player.bin', player.pack())

# foot: a small box (local origin at the ground contact point)
foot = Mesh()
fx0, fx1, fy0, fy1, fz0, fz1 = -0.08, 0.08, 0.0, 0.12, -0.12, 0.14
fc = (90, 60, 50)
tex_quad(foot, [(fx0, fy0, fz0), (fx1, fy0, fz0), (fx0, fy1, fz0), (fx1, fy1, fz0)], 'wood', fc)
tex_quad(foot, [(fx1, fy0, fz1), (fx0, fy0, fz1), (fx1, fy1, fz1), (fx0, fy1, fz1)], 'wood', fc)
tex_quad(foot, [(fx0, fy0, fz1), (fx0, fy0, fz0), (fx0, fy1, fz1), (fx0, fy1, fz0)], 'wood', fc)
tex_quad(foot, [(fx1, fy0, fz0), (fx1, fy0, fz1), (fx1, fy1, fz0), (fx1, fy1, fz1)], 'wood', fc)
tex_quad(foot, [(fx0, fy1, fz0), (fx1, fy1, fz0), (fx0, fy1, fz1), (fx1, fy1, fz1)], 'wood', fc)
write('foot.bin', foot.pack())


def orb_mesh(top_col, mid_col, bot_col, r=0.27):
    """A four-sided bipyramid (6 vertices, 8 triangles); it spins, so it reads as a gem."""
    m = Mesh()
    t = m.vertex(0, r * 1.35, 0)
    b = m.vertex(0, -r * 1.35, 0)
    ring_ = [m.vertex(*p) for p in ring_pts(r, 0, 4)]
    for i in range(4):
        j = (i + 1) % 4
        m.tri([ring_[j], ring_[i], t], [mid_col, mid_col if i % 2 else top_col, top_col])
        m.tri([ring_[i], ring_[j], b], [mid_col, bot_col, bot_col])
    return m.pack()


write('orb_sun.bin', orb_mesh(rgb(255, 250, 210), rgb(255, 190, 70), rgb(230, 100, 30)))
write('orb_moon.bin', orb_mesh(rgb(250, 252, 255), rgb(170, 200, 255), rgb(90, 110, 220)))


# ----------------------------------------------------------------------------- sounds

SR = 22050


def s8(x):
    return (np.clip(np.round(x * 127), -127, 127).astype(np.int8)).tobytes()


def s16(x):
    return (np.clip(np.round(x * 32767), -32767, 32767).astype('<i2')).tobytes()


def env(n, attack, decay_rate, sr=SR):
    t = np.arange(n) / sr
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t * decay_rate)


def tone(freq, dur, kind='sine', sr=SR):
    t = np.arange(int(round(dur * sr))) / sr
    ph = 2 * np.pi * np.cumsum(np.broadcast_to(freq, t.shape)) / sr if np.ndim(freq) else 2 * np.pi * freq * t
    if kind == 'sine':
        return np.sin(ph)
    if kind == 'square':
        return np.sign(np.sin(ph)) * 0.6
    if kind == 'pulse':
        return np.where((ph / (2 * np.pi)) % 1 < 0.25, 0.6, -0.6)
    if kind == 'tri':
        return 2 / np.pi * np.arcsin(np.sin(ph))
    raise ValueError(kind)


def lowpass(x, a):
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a * (x[i] - acc)
        y[i] = acc
    return y


# jump: a pulse-wave sweep up
n = int(0.16 * SR)
f = 260 * (720 / 260) ** (np.arange(n) / n)
jump = tone(f, 0.16, 'pulse') * env(n, 0.003, 14) * 0.7
write('sfx_jump.raw', s8(jump))

# collect: a two-note bell (the game raises its pitch with every orb)
def bell(freq, dur, sr=SR):
    n = int(dur * sr)
    t = np.arange(n) / sr
    x = (np.sin(2 * np.pi * freq * t) * np.exp(-t * 5) +
         0.5 * np.sin(2 * np.pi * freq * 2.0 * t) * np.exp(-t * 8) +
         0.25 * np.sin(2 * np.pi * freq * 3.01 * t) * np.exp(-t * 12) +
         0.18 * np.sin(2 * np.pi * freq * 4.2 * t) * np.exp(-t * 16))
    return x * np.clip(t / 0.002, 0, 1)


n = int(0.75 * SR)
col = np.zeros(n)
b1 = bell(880, 0.75)
b2 = bell(1318.5, 0.65)
col[:len(b1)] += b1 * 0.5
off = int(0.07 * SR)
col[off:off + len(b2)] += b2[:n - off] * 0.5
write('sfx_collect.raw', s8(col / np.max(np.abs(col)) * 0.9))

# step: a soft filtered noise tick; land: a heavier thump
n = int(0.05 * SR)
step = lowpass(rng.uniform(-1, 1, n), 0.25) * env(n, 0.001, 90) * 1.6
write('sfx_step.raw', s8(np.clip(step, -1, 1) * 0.6))
n = int(0.12 * SR)
land = (lowpass(rng.uniform(-1, 1, n), 0.12) * 2.5 + np.sin(2 * np.pi * 70 * np.arange(n) / SR)) * env(n, 0.001, 35)
write('sfx_land.raw', s8(np.clip(land / np.max(np.abs(land)), -1, 1) * 0.85))

# splash: noise with a falling band and bubbly blips
n = int(0.45 * SR)
nz = rng.uniform(-1, 1, n)
sp = lowpass(nz, 0.5) - lowpass(nz, 0.05)
sp *= env(n, 0.005, 7)
t = np.arange(n) / SR
for k in range(6):
    st_ = int(rng.uniform(0.05, 0.3) * SR)
    ln = int(0.03 * SR)
    fr = rng.uniform(500, 1100)
    seg = np.sin(2 * np.pi * (fr + 3000 * t[:ln]) * t[:ln]) * np.exp(-t[:ln] * 80) * 0.4
    sp[st_:st_ + ln] += seg[:max(0, min(ln, n - st_))]
write('sfx_splash.raw', s8(sp / np.max(np.abs(sp)) * 0.8))

# fanfare: a bright arpeggio and a held major chord
def note_hz(semis, base=440.0):
    return base * 2 ** (semis / 12)


n = int(2.0 * SR)
fan = np.zeros(n)
for k, s in enumerate([3, 7, 10, 15, 19]):          # C E G C E (relative to A4)
    st_ = int(k * 0.11 * SR)
    ln = int(0.5 * SR)
    seg = (tone(note_hz(s), 0.5, 'pulse') * 0.5 + tone(note_hz(s), 0.5, 'tri') * 0.5) * env(ln, 0.004, 5)
    fan[st_:st_ + ln] += seg[:n - st_]
st_ = int(0.6 * SR)
ln = n - st_
for s in (3, 7, 10, 15):
    fan[st_:] += (tone(note_hz(s), ln / SR, 'tri') * 0.35 + tone(note_hz(s) * 1.003, ln / SR, 'pulse') * 0.15) * env(ln, 0.01, 2.2)
write('sfx_fanfare.raw', s8(fan / np.max(np.abs(fan)) * 0.9))

# start chime: three quick bells going up
n = int(0.8 * SR)
stc = np.zeros(n)
for k, s in enumerate([0, 4, 7]):
    b = bell(note_hz(s + 12), 0.6)
    o = int(k * 0.08 * SR)
    stc[o:o + len(b)] += b[:n - o] * 0.4
write('sfx_start.raw', s8(stc / np.max(np.abs(stc)) * 0.85))

# ---- music: a dreamy 4-bar loop at 11,025 Hz, 16-bit, in two channels for stereo
MSR = 11025
BPM = 84
beat = 60 / BPM
bars = 4
L = int(round(bars * 4 * beat * MSR))


def add_wrap(buf, start, x):
    i = np.arange(len(x)) + start
    np.add.at(buf, i % len(buf), x)


def pad_note(freq, dur):
    n = int(dur * MSR)
    t = np.arange(n) / MSR
    x = np.zeros(n)
    for det in (-0.004, 0.0, 0.0045):
        f = freq * (1 + det)
        x += np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * 0.25 * t)) + 0.25 * np.sin(4 * np.pi * f * t)
    a = np.clip(t / 0.6, 0, 1)
    r = np.clip((dur - t) / 0.9, 0, 1)
    return x * a * r / 3


def pluck(freq, dur, bright=0.5):
    n = int(dur * MSR)
    p = max(2, int(MSR / freq))
    buf = rng.uniform(-1, 1, p)
    out = np.zeros(n)
    for i in range(n):
        v = buf[i % p]
        out[i] = v
        buf[i % p] = 0.5 * (v + buf[(i + 1) % p]) * (0.996 if bright else 0.99)
    return out * np.clip(np.arange(n) / 30, 0, 1)


# chords as semitones from A4 (440 Hz): Dmaj9, Bm9, Gmaj7(#11), Asus4 -> A
CHORDS = [[-19, -7, -3, 0, 4], [-22, -10, -7, -3, 1], [-14, -2, 2, 5, 9], [-12, -5, 0, 2, 7]]
BASS = [-31, -34, -38, -36]
pad = np.zeros(L)
lead = np.zeros(L)
for bi, ch in enumerate(CHORDS):
    st_ = int(bi * 4 * beat * MSR)
    for s in ch[1:]:
        add_wrap(pad, st_, pad_note(note_hz(s), 4 * beat + 0.8) * 0.22)
    for k in (0, 2):
        ln = 2 * beat
        n = int(ln * MSR)
        t = np.arange(n) / MSR
        bass = np.sin(2 * np.pi * note_hz(BASS[bi]) * t) * np.exp(-t * 1.2) * np.clip(t / 0.01, 0, 1)
        add_wrap(pad, st_ + int(k * beat * MSR), bass * 0.35)
    # arpeggio in eighths: up and down the chord, an octave up
    order = [1, 2, 3, 4, 3, 2, 1, 2]
    for e in range(8):
        s = ch[order[e]] + 12
        add_wrap(lead, st_ + int(e * beat / 2 * MSR), pluck(note_hz(s), 1.2) * 0.16)
# a sparse bell melody (D major pentatonic) over the arpeggio
MEL = [(0, 17, 1.5), (1.5, 14, 0.5), (2, 12, 2), (4, 10, 1.5), (5.5, 12, 0.5), (6, 14, 2),
       (8, 9, 1.5), (9.5, 10, 0.5), (10, 14, 2), (12, 12, 1), (13, 10, 1), (14, 7, 2)]
for b0, s, d in MEL:
    x = bell(note_hz(s), d * beat + 0.6, MSR) * 0.18
    add_wrap(lead, int(b0 * beat * MSR), x)
pad = pad / np.max(np.abs(pad)) * 0.7
lead = lead / np.max(np.abs(lead)) * 0.7
write('music_pad.raw', s16(pad))
write('music_lead.raw', s16(lead))


# ----------------------------------------------------------------------------- level_data.akr

def fx(v):
    return ('%.4f' % v) if v != int(v) else ('%.1f' % v)


lines = ['// Generated by tools/gen_orbs_assets.py - do not edit.',
         '// Level collision boxes, orb placements and the culling table of the level chunks.', '']
lines.append('const NUM_BOXES = %d' % len(boxes))
lines.append('// (the perimeter walls are 2.5 high but collide up to 40, so no jump leaves the courtyard)')
lines.append('const BOXES: [%d]Box = [' % len(boxes))
for b in boxes:
    if b[4] == WALL_H and (abs(b[0]) == 15 or abs(b[3]) == 15):
        b = b[:4] + (40.0,) + b[5:]
    lines.append('    Box { x0: %s, y0: %s, z0: %s, x1: %s, y1: %s, z1: %s },' % tuple(fx(c) for c in b))
lines.append(']')
lines.append('')
lines.append('const NUM_ORBS = %d' % len(ORBS))
lines.append('const ORB_POS: [%d]vec3 = [' % len(ORBS))
for o in ORBS:
    lines.append('    vec3(%s, %s, %s),' % (fx(o[0]), fx(o[1]), fx(o[2])))
lines.append(']')
lines.append('const ORB_KIND: [%d]u8 = [%s]' % (len(ORBS), ', '.join(str(o[3]) for o in ORBS)))
lines.append('')
lines.append('const START_X: fixed = %s' % fx(START[0]))
lines.append('const START_Z: fixed = %s' % fx(START[2]))
lines.append('const WATER_Y: fixed = %s' % fx(WATER_Y))
lines.append('const POOL_X0: fixed = %s' % fx(POOL[0]))
lines.append('const POOL_Z0: fixed = %s' % fx(POOL[1]))
lines.append('const POOL_X1: fixed = %s' % fx(POOL[2]))
lines.append('const POOL_Z1: fixed = %s' % fx(POOL[3]))
lines.append('const SHRINE_X: fixed = %s' % fx(SHRINE[0]))
lines.append('const SHRINE_Z: fixed = %s' % fx(SHRINE[1]))
lines.append('')
for ch, c, r, nv, nf, lo_, hi_, nvl, nfl in chunk_info:
    lines.append('embed CHUNK%d: Mesh = "chunk%d.bin"         // %d vertices, %d quads' % (ch, ch, nv, nf))
    lines.append('embed CHUNK%d_LO: Mesh = "chunk%d_lo.bin"   // %d vertices, %d quads' % (ch, ch, nvl, nfl))
lines.append('')
lines.append('// Draws the level chunks that may be visible (sphere test against the view), with the')
lines.append('// fine version near the camera and the coarse one further away.')
lines.append('fn draw_level() {')
for ch, c, r, nv, nf, lo_, hi_, nvl, nfl in chunk_info:
    lines.append('    if chunk_visible(vec3(%s, %s, %s), %s) {'
                 % (fx(round(c[0], 2)), fx(round(c[1], 2)), fx(round(c[2], 2)), fx(round(r + 0.05, 2))))
    if ch == 9:   # the pool lies below the ground around it: sort it behind
        lines.append('        depth_bias(30)')
    lines.append('        if chunk_near(%s, %s, %s, %s) { mesh(CHUNK%d) } else { mesh(CHUNK%d_LO) }'
                 % (fx(lo_[0]), fx(lo_[2]), fx(hi_[0]), fx(hi_[2]), ch, ch))
    if ch == 9:
        lines.append('        depth_bias(0)')
    lines.append('    }')
lines.append('}')
with open(os.path.join(OUT, 'level_data.akr'), 'w') as f:
    f.write('\n'.join(lines) + '\n')

print('chunks (id, verts, quads, lo verts, lo quads):', [(ci[0], ci[3], ci[4], ci[7], ci[8]) for ci in chunk_info])
print('total quads', sum(ci[4] for ci in chunk_info), 'coarse', sum(ci[8] for ci in chunk_info))
print('player faces', len(player.faces), 'ring', len(ring.faces), 'water', len(wm.faces))
print('music %d samples (%.1f s), %d KB per channel' % (L, L / MSR, L * 2 // 1024))
print('wrote assets to', OUT)
