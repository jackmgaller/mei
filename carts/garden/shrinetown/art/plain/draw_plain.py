#!/usr/bin/env python3
"""Draws the shrine town's far plain: the ground past the level's drawn edge, as a Mode 7 plane on
the Horizon Engine's affine plane BG2 (docs/PLANES.md). Writes, beside this script:

    plain.png           the painting, 1,024 x 1,024 texels (2 m each), north up, 15 colours
    plain_atlas.bin     its 8 x 8 tiles, 1,024 at most: one 4-bit atlas page (32,768 bytes)
    plain_map.bin       the 128 x 128 map of tile numbers (32,768 bytes, little-endian u16)
    plain_data.akr      the embeds, the colours (day, night) and where the level sits on the map

    python3 carts/garden/shrinetown/art/plain/draw_plain.py [--preview DIR]

--preview writes plain_tiles.png (the painting as the tiles rebuild it, 2x) and plain_zones.png
into DIR. Authored art from a fixed seed: rerun only to change it. Needs NumPy and Pillow.

What is on it (world metres; the level is x 0-320, z 0-384, north +z): the town carried on south
of the station and east and west along the front road, low tiled and tin roofs in narrow
streets with a few flat-roofed blocks; harvested rice paddies (stubble, ploughed earth, a green
crop, greenhouses, homesteads in their tree groves) east, west and further south; a river with
gravel banks in the west; the railway east from the viaduct and west from the station; forested
autumn hills to the north, cedar with maples and ginkgo, as the backdrop's ridges are. The map
is 2,048 m square and wraps; its seams are more than 800 m from the level, where the fog is full.
"""
import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
N = 1024                 # texels a side
TEXEL = 2.0              # metres a texel
UOFF, VOFF = 432, 416    # the texel of world (0, 0): the level's centre (160, 192) at the map's centre
SEED = 1997

# 15 colours (index 0 is transparent on a plane: never drawn). By day; the night's are these times
# the world's night multiply, #4a5884, as the level's palettes are.
COLOURS = [
    None,
    '#4f4f56',   # 1 asphalt (the level's road, #4a4a51)
    '#b5b0a5',   # 2 concrete: flat roofs, yards, greenhouses (the level's concrete, #b7b2a7)
    '#4a5160',   # 3 kawara, the shaded slope
    '#6d7584',   # 4 kawara, the lit slope
    '#5b807c',   # 5 tin roof, teal
    '#8c4c3c',   # 6 tin roof, rust
    '#c4ab70',   # 7 rice stubble
    '#a08856',   # 8 straw, levees, drying racks
    '#7b6247',   # 9 ploughed earth
    '#6b7a3f',   # 10 green crop, grass, gardens (the park's, #688436)
    '#34432f',   # 11 cedar
    '#ad5236',   # 12 maple
    '#c89a44',   # 13 ginkgo, gold
    '#6a8693',   # 14 water
    '#cdc5ae',   # 15 gravel (the shrine's raked gravel far colour, #d4cbb9)
]
NIGHT_MULTIPLY = (0x4a, 0x58, 0x84)

ASPHALT, CONCRETE, KAWARA_D, KAWARA_L, TEAL, RUST, STUBBLE, STRAW, EARTH, GREEN, CEDAR, MAPLE, GOLD, WATER, GRAVEL = range(1, 16)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


# ---- coordinates

u = np.arange(N)
U, V = np.meshgrid(u, u)                          # V rows (north is +v), U columns (east is +u)
X = (U + 0.5 - UOFF) * TEXEL                      # world metres
Z = (V + 0.5 - VOFF) * TEXEL
rng = np.random.default_rng(SEED)


def wave_noise(octaves, seed):
    """Periodic value-like noise from a sum of sines with whole frequencies (the map wraps)."""
    r = np.random.default_rng(seed)
    out = np.zeros((N, N))
    for (fmin, fmax, amp, count) in octaves:
        for _ in range(count):
            ku, kv = r.integers(-fmax, fmax + 1, 2)
            if abs(ku) < fmin and abs(kv) < fmin:
                ku = fmin
            out += amp * np.sin(2 * math.pi * (ku * U + kv * V) / N + r.uniform(0, 2 * math.pi)) / math.sqrt(count)
    return out


def wrap_d(a, b):
    """Signed texel distance a - b on the torus."""
    return (a - b + N // 2) % N - N // 2


big = wave_noise([(1, 4, 1.0, 6), (4, 10, 0.5, 10)], 1)
mid = wave_noise([(10, 30, 1.0, 40)], 2)
fine = wave_noise([(30, 90, 1.0, 60)], 3)

def hash3(a, b, c=0):
    """A deterministic integer hash of integer arrays (for per-lot and per-parcel choices)."""
    h = (np.asarray(a, np.int64) * 73856093) ^ (np.asarray(b, np.int64) * 19349663) ^ (np.asarray(c, np.int64) * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return (h ^ (h >> 16)) & 0x7FFFFFFF


# ---- zones. Forest: the hills north of the level (north-ness peaks 700 m north of it), down to
# about z 380 behind the level and a little lower far east and west. Town: an oval round the
# station's south side and along the front road. Fields everywhere else.
north = np.cos(2 * math.pi * (V - (VOFF + 350)) / N)
west_east = np.cos(2 * math.pi * (U - (UOFF + 80)) / N)    # 1 at the level's x, -1 a kilometre off
forest = north + 0.16 * big + 0.08 * mid - 0.10 * west_east
FOREST = forest > 0.42
oval = np.hypot((X - 160) / 500, (Z + 170) / 340) + 0.14 * big + 0.07 * mid
along = (np.abs(Z - 60) < 80 + 25 * mid) & (np.abs(X - 160) < 430 + 50 * big)
TOWN = ((oval < 1.0) & (Z < 140) | along) & ~FOREST

img = np.full((N, N), STUBBLE, np.uint8)

# ---- fields: parcels of 16 x 48 texels (32 x 96 m) with levees, farm roads and channels
PW, PH = 16, 48
kind = hash3(U // PW, V // PH, 1) % 100
kind = np.select([kind < 40, kind < 57, kind < 72, kind < 82, kind < 88], [0, 1, 2, 3, 4], 5)
speck = hash3(U, V, 2) % 100
field = np.select(
    [kind == 0, kind == 1, kind == 2, kind == 3, kind == 4],
    [np.where(speck < 14, STRAW, STUBBLE),                   # stubble
     np.where(speck < 14, STRAW, EARTH),                     # ploughed
     np.where(V % 3 == 0, EARTH, GREEN),                     # a green crop in rows
     np.where(U % 4 == 0, STRAW, STUBBLE),                   # rice drying on racks in rows
     np.where(U % 3 == 0, GREEN, CONCRETE)],                 # greenhouses
    np.where(speck < 30, STUBBLE, STRAW)).astype(np.uint8)   # straw, gathered
lev = (U % PW == 0) | (V % PH == 0)
field[lev] = np.where(((U + V) % 5 == 0)[lev], GREEN, STRAW)
field[(U % (PW * 4) == 1) | (U % (PW * 4) == 2) | (V % (PH * 3) == 1)] = GRAVEL     # farm roads
field[V % (PH * 3) == 3] = WATER                                                     # a channel beside them
img[:] = field

# homesteads in the fields: two or three roofs in a ring of trees
hrng = np.random.default_rng(SEED + 2)
for _ in range(110):
    cu, cv = hrng.integers(0, N, 2)
    r = int(hrng.integers(6, 10))
    d2 = wrap_d(U, cu) ** 2 + wrap_d(V, cv) ** 2
    m = (d2 < r * r) & ~TOWN & ~FOREST
    img[m & (d2 > (r - 3) ** 2)] = np.where(fine[m & (d2 > (r - 3) ** 2)] > 0.3, MAPLE, CEDAR)
    img[m & (d2 <= (r - 3) ** 2)] = GRAVEL
    for k in range(int(hrng.integers(2, 4))):
        w, h = int(hrng.integers(3, 6)), int(hrng.integers(3, 5))
        hu, hv = cu + int(hrng.integers(-r + 3, r - 2 - w)), cv + int(hrng.integers(-r + 3, r - 2 - h))
        uu, vv = np.arange(hu, hu + w) % N, np.arange(hv, hv + h) % N
        if not m[np.ix_(vv, uu)].all():
            continue
        roof = [KAWARA_D, KAWARA_D, KAWARA_D, TEAL, RUST][int(hrng.integers(0, 5))]
        img[np.ix_(vv, uu)] = roof
        if roof == KAWARA_D:
            img[np.ix_(vv[h // 2:], uu)] = KAWARA_L

# ---- the town: blocks between lanes (1 texel) and streets (2), two rows of lots a block, a roof
# on each lot with a strip of garden, a yard or a tree beside it; a few flat-roofed blocks
def cuts(seed, lo, hi):
    """Where the streets are: gaps of lo-hi texels round the map (the last one wraps)."""
    r = np.random.default_rng(seed)
    at = [0]
    while True:
        g = int(r.integers(lo, hi + 1))
        if at[-1] + g > N - lo:
            return np.array(at)
        at.append(at[-1] + g)


def runs(at):
    """For each texel: the index of the run it is in, its offset in it and the run's length."""
    idx = np.searchsorted(at, np.arange(N), side='right') - 1
    nxt = np.append(at[1:], N)
    return idx, np.arange(N) - at[idx], nxt[idx] - at[idx]


bu, ou, wu = runs(cuts(SEED + 3, 14, 26))       # blocks east-west
bv, ov, wv = runs(cuts(SEED + 4, 10, 15))       # and north-south
BU, BV = np.meshgrid(bu, bv)
OU, OV = np.meshgrid(ou, ov)
WU, WV = np.meshgrid(wu, wv)
main_u = hash3(BU, 0, 5) % 4 == 0               # some streets are 2 texels, the rest lanes
main_v = hash3(0, BV, 6) % 3 == 0
street = (OU == 0) | (OV == 0) | (main_u & (OU == 1)) | (main_v & (OV == 1))
ou_in = OU - 1 - main_u                         # the texel within the block's lots
ov_in = OV - 1 - main_v
depth = np.maximum(WV - 1 - main_v, 2)
row = ov_in >= depth // 2                       # the back row of lots
lv_ = np.where(row, ov_in - depth // 2, ov_in)  # within the lot
lot_w = 4 + hash3(BU, BV, 7) % 3                # 4-6 texels wide, per block
lot_u = ou_in // lot_w
lu_ = ou_in % lot_w
lot_hash = hash3(BU * 64 + lot_u, BV * 2 + row, 8)
roof_kind = lot_hash % 100
roof_c = np.select([roof_kind < 46, roof_kind < 58, roof_kind < 68, roof_kind < 76, roof_kind < 82],
                   [KAWARA_D, KAWARA_L, TEAL, RUST, CONCRETE], -1)
gap = (lu_ == lot_w - 1) | np.where(row, lv_ == depth - depth // 2 - 1, lv_ == 0)
gap |= roof_c == -1
garden = np.select([hash3(U, V, 9) % 10 < 5, hash3(U, V, 9) % 10 < 7, hash3(U, V, 9) % 10 < 9],
                   [GREEN, CONCRETE, MAPLE], GOLD)
# a kawara roof shows its two slopes: the lit one is the lot's front half
slope = np.where(row, lv_ >= (depth - depth // 2) // 2, lv_ >= (depth // 2 + 1) // 2)
roof_px = np.where((roof_c == KAWARA_D) & slope, KAWARA_L, np.where((roof_c == KAWARA_L) & ~slope, KAWARA_D, roof_c))
town = np.where(street, ASPHALT, np.where(gap, garden, roof_px)).astype(np.uint8)
big_block = (hash3(BU, BV, 10) % 100 < 7) & ~street
town[big_block] = np.where(((OU == 1 + main_u) | (OV == 1 + main_v) | (OU == WU - 1) | (OV == WV - 1))[big_block],
                           ASPHALT, CONCRETE)
img[TOWN] = town[TOWN]

# ---- forest: cedar with maple and ginkgo in clumps, gold and green at its edge
tree = np.where(fine + 0.6 * mid > 1.1, MAPLE, np.where(fine - 0.5 * mid > 1.05, GOLD, CEDAR))
tree = np.where((tree == CEDAR) & (hash3(U, V, 11) % 100 < 6), GREEN, tree)
img[FOREST] = tree[FOREST]
fedge = FOREST & (forest < 0.47)
img[fedge] = np.where(fine[fedge] > 0, GOLD, GREEN)

# ---- main roads: the front road east and west (z 106-120), the axis south from the station
img[np.abs(Z - 113) < 6] = ASPHALT
img[(np.abs(X - 160) < 4) & (Z < 0) & TOWN] = ASPHALT
img[(np.abs(Z + 470) < 5) & ~FOREST] = ASPHALT
img[(np.abs(X - 640) < 5) & ~FOREST & (Z < 113)] = ASPHALT

# ---- the railway: west from the station (z 8), east from the viaduct (z 143), on ballast
for zc, side in ((8, X < 0), (143, X > 320)):
    m = (np.abs(Z - zc) < 5) & side
    img[m] = GRAVEL
    img[m & (np.abs(Z - zc) < 2)] = EARTH

# ---- the river, west: water in gravel banks, grassy levees with a road on each crest
rc = -260 + 50 * np.sin(2 * math.pi * 2 * V / N) + 25 * np.sin(2 * math.pi * 5 * V / N + 1.3)
dx = np.abs(X - rc)
img[(dx < 44) & (dx >= 36)] = GREEN
img[(dx < 47) & (dx >= 44)] = ASPHALT
img[dx < 36] = GRAVEL
img[dx < 14 + 4 * np.sin(2 * math.pi * 9 * V / N)] = WATER
for zc, w, c in ((113, 6, ASPHALT), (8, 4, CONCRETE), (-470, 5, ASPHALT)):     # bridges
    img[(dx < 47) & (np.abs(Z - zc) < w)] = c

assert img.min() >= 1 and img.max() <= 15


# ---- tiles: deduplicated, and reduced to 1,024 by k-means when there are more

def tiles_of(a):
    t = a.reshape(N // 8, 8, N // 8, 8).transpose(0, 2, 1, 3).reshape(-1, 64)
    return t


def reduce_tiles(tiles, limit=1024, seed=SEED):
    uniq, inv, counts = np.unique(tiles, axis=0, return_inverse=True, return_counts=True)
    inv = inv.reshape(-1)
    if len(uniq) <= limit:
        return uniq, inv
    pal = np.array([(0, 0, 0)] + [rgb(c) for c in COLOURS[1:]], float)
    x = pal[uniq].reshape(len(uniq), -1)                   # n x 192
    w = counts.astype(float)
    r = np.random.default_rng(seed)
    order = np.argsort(-counts)
    cent = x[order[:limit // 2]]
    rest = r.choice(order[limit // 2:], limit - limit // 2, replace=False)
    cent = np.vstack([cent, x[rest]])
    xx = (x * x).sum(1)
    for it in range(12):
        d = xx[:, None] - 2 * x @ cent.T + (cent * cent).sum(1)[None, :]
        lab = d.argmin(1)
        for k in range(limit):
            m = lab == k
            if m.any():
                cent[k] = (x[m] * w[m, None]).sum(0) / w[m].sum()
    d = xx[:, None] - 2 * x @ cent.T + (cent * cent).sum(1)[None, :]
    lab = d.argmin(1)
    # each cluster is drawn by its member nearest the centre (a real tile: real palette indices)
    rep = np.zeros(limit, int)
    keep = []
    for k in range(limit):
        m = np.nonzero(lab == k)[0]
        if len(m) == 0:
            continue
        rep[k] = m[np.argmin(d[m, k])]
        keep.append(k)
    remap = {k: i for i, k in enumerate(keep)}
    out = uniq[rep[keep]]
    return out, np.array([remap[lab[i]] for i in inv])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--preview', type=Path)
    a = ap.parse_args()
    pal = [(0, 0, 0)] + [rgb(c) for c in COLOURS[1:]]
    flat = sum(pal, ())
    p = Image.fromarray(img[::-1])                       # north up
    p.putpalette(list(flat) + [0] * (768 - len(flat)))
    p.save(HERE / 'plain.png', optimize=True)

    tiles = tiles_of(img)
    atlas_tiles, index = reduce_tiles(tiles)
    n = len(atlas_tiles)
    print(f'{len(np.unique(tiles, axis=0))} distinct 8 x 8 tiles, {n} in the atlas')
    # the atlas: a 256 x 256 4-bit image, tile t at column t mod 32, row t div 32; low nibble even u
    at = np.zeros((256, 256), np.uint8)
    for t in range(n):
        cu, cv = t % 32, t // 32
        at[cv * 8:cv * 8 + 8, cu * 8:cu * 8 + 8] = atlas_tiles[t].reshape(8, 8)
    packed = (at[:, 0::2] | (at[:, 1::2] << 4)).astype(np.uint8)
    (HERE / 'plain_atlas.bin').write_bytes(packed.tobytes())
    m = index.reshape(N // 8, N // 8).astype('<u2')      # row = map y (v / 8), column = map x
    (HERE / 'plain_map.bin').write_bytes(m.tobytes())

    night = [tuple(round(c * k / 255) for c, k in zip(col, NIGHT_MULTIPLY)) for col in pal]
    word = lambda c: f'0x{c[2]:02X}{c[1]:02X}{c[0]:02X}'
    akr = [
        '// Generated by carts/garden/shrinetown/art/plain/draw_plain.py - do not edit.',
        '// The far plain\'s art (README in APPLY.md): a 4-bit atlas page of 8 x 8 tiles, a 128 x 128 map,',
        '// its 15 colours by day and by night (0xBBGGRR; entry 0 is transparent, never drawn).',
        '',
        'embed PLAIN_ATLAS: u8 = "plain_atlas.bin"      // 32,768 bytes: one plane page',
        'embed PLAIN_MAP: u16 = "plain_map.bin"         // 128 x 128 entries, 32,768 bytes',
        f'const PLAIN_TILES = {n}',
        f'const PLAIN_TEXELS: fixed = {1 / TEXEL}       // texels a metre',
        f'const PLAIN_UOFF: fixed = {float(UOFF)}       // the texel of world (0, 0)',
        f'const PLAIN_VOFF: fixed = {float(VOFF)}',
        'const PLAIN_COLOURS: [32]u32 = [' + ', '.join(word(c) for c in pal) + ',',
        '                                ' + ', '.join(word(c) for c in night) + ']',
        '',
    ]
    (HERE / 'plain_data.akr').write_text('\n'.join(akr))

    if a.preview:
        a.preview.mkdir(parents=True, exist_ok=True)
        back = atlas_tiles[index].reshape(N // 8, N // 8, 8, 8).transpose(0, 2, 1, 3).reshape(N, N)
        q = Image.fromarray(back[::-1])
        q.putpalette(list(flat) + [0] * (768 - len(flat)))
        q.convert('RGB').resize((2 * N, 2 * N), Image.NEAREST).save(a.preview / 'plain_tiles.png')
        z = np.zeros((N, N, 3), np.uint8)
        z[TOWN] = (180, 120, 120)
        z[FOREST] = (60, 110, 60)
        z[~TOWN & ~FOREST] = (210, 190, 120)
        lvl = (U >= UOFF) & (U < UOFF + 160) & (V >= VOFF) & (V < VOFF + 192)
        z[lvl] = (255, 255, 255)
        Image.fromarray(z[::-1]).save(a.preview / 'plain_zones.png')
    print('wrote plain.png, plain_atlas.bin, plain_map.bin, plain_data.akr')


if __name__ == '__main__':
    main()
