#!/usr/bin/env python3
"""Draws the shrine town's backdrop (authored art; rerun only to change it):

    backdrop.png     1024 x 128, 15 colours: the far view round the level, for both texture
                     regions (`town` and `shrine`), so nothing in it moves at z = 128
    backdrop.json    the sky, the night's exact colours, the silhouette's placement and the two
                     variants' fog colours, which make_world.py reads

    python3 carts/garden/shrinetown/art/backdrop/draw_backdrop.py [--preview DIR]

The PNG is the Horizon Engine's silhouette panorama (WORLDKIT.md, "Backdrops"): 1,024 pixels
round the compass (2.84 a degree, column 0 north, then east, south at column 512), UNDER rows
standing under the horizon line, transparent where the sky shows, at most 15 colours. The sky
itself (a gradient on the backdrop colour, stops by elevation, day and night) is in backdrop.json.

What is in it, far to near: mackerel cloud; blue ranges, highest to the north (the mountain's
range), whose feet fade into the haze; a nearer forested ridge with the autumn's red and gold in
its top rows; to the south the city (far blocks in haze, the middle rows with their windows, the
near rows with tiled roofs, a red-and-white radio tower at 198 degrees, two chimneys, a crane).
Under the horizon (seen from the pagoda, the walkway and the stage, 30-62 m up, where the level's
drawn world ends 190-260 m off): low far town and fields as haze marks thinning out downward, then
the fog colour itself, so the fogged edge of the drawn world meets the backdrop in one colour.
The `fog` and `haze` colours are the day fog's and a step toward the far city; the night variant
gives them its own (backdrop.json "variants"), and FOG gives make_world.py both variants' fog
colours, exact in 15 bits so the GPU's fog and the plane's pixels are the same colour.

Windows are 2 x 2 pixels on a 4-pixel grid in one of two glass colours that differ by a hair in
daylight; the night variant lights one of them, so about a third of the windows glow after dark.
The grid is 4 pixels and the buildings' edges and the haze's dither are on it, so that an 8 x 8
tile repeats and the atlas stays under its 1,024 tiles. Deterministic: fixed seeds.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
W, H = 1024, 128
UNDER = 40                                     # rows below the horizon line

SKY = {
    'elevations': [-8, 0, 3, 9, 26, 70],
    'sky': {
        'day':   ['#7d8456', '#ecdcb4', '#d3dfdc', '#9cc4e0', '#6a9fd2', '#3a6cb0'],
        'night': ['#141420', '#5a4466', '#352c58', '#1c1e42', '#0c1028', '#04060f'],
    },
}


def hexrgb(c):
    return tuple(int(c[k:k + 2], 16) for k in (1, 3, 5))


def exact15(rgb):
    """The colour a 15-bit entry shows (the GPU's expansion, c << 3 | c >> 2): '#rrggbb'."""
    return '#' + ''.join(f'{(v >> 3) << 3 | (v >> 3) >> 2:02x}' for v in rgb)


def sky_at(variant, e):
    el, cols = SKY['elevations'], [hexrgb(c) for c in SKY['sky'][variant]]
    for k in range(1, len(el)):
        if e <= el[k]:
            t = (e - el[k - 1]) / (el[k] - el[k - 1])
            return tuple(round(a + (b - a) * t) for a, b in zip(cols[k - 1], cols[k]))
    return cols[-1]


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


# The fog colours (make_world.py: each variant's GPU fog, and the sky's stop below the horizon): the
# day's is the sky 3 degrees up, a pale blue-grey (at 1 degree, the warm cream of the horizon, far
# hills and trees went cream in front of the blue ranges); the night's the deep blue of the sky's 9
# degree stop, darker than the horizon's purple, so far things darken into the night instead of
# glowing (ALPHA_REVIEW, far views).
FOG = {'day': exact15(sky_at('day', 3.0)), 'night': exact15(hexrgb('#1c1e42'))}

# palette (day): name -> colour
C = {
    'far':      '#9db1c3',     # farthest range, haze
    'mid':      '#7d9ba7',     # second range
    'near':     '#55745b',     # nearest forested ridge
    'red':      '#b2573a',     # maple red, in the ridge's top rows
    'gold':     '#c99a46',     # ginkgo gold
    'cloud':    '#f3ebdc',     # cloud lit side; the tower's white bands
    'cloud_s':  '#d6cbc0',     # cloud shaded underside
    'cfar':     '#adb8c6',     # the far city's blocks, in haze
    'cmid':     '#8e98a8',     # the middle rows
    'cnear':    '#6e7788',     # the near rows
    'win_a':    '#566680',     # window glass; this one is lit at night
    'win_b':    '#4e5e78',     # window glass, dark at night; the near rows' tiled roofs
    'steel':    '#b33d36',     # tower, crane and chimney bands
    'haze':     exact15(mix(hexrgb(FOG['day']), hexrgb('#adb8c6'), 0.6)),   # far land in the haze
    'fog':      FOG['day'],    # the day fog itself
}
NIGHT = {                      # exact colours after the night's multiply tint
    'win_a': '#f2cf78',        # lit
    'cloud': '#46517a',
    'cloud_s': '#2c3358',
    'steel': '#d84a3c',        # the tower's lamp-lit bands
    'red': '#4c3446',
    'gold': '#5a5a46',
    'haze': exact15(mix(hexrgb(FOG['night']), (0x30, 0x3c, 0x64), 0.5)),
    'fog': FOG['night'],
}


class Canvas:
    def __init__(self):
        self.px = np.zeros((H, W), dtype=np.uint8)        # 0: sky, else a colour index
        self.names = ['']
        self.idx = {}

    def colour(self, name):
        if name not in self.idx:
            self.idx[name] = len(self.names)
            self.names.append(name)
        return self.idx[name]

    def rect(self, x0, y0, x1, y1, name):
        """Columns x0..x1-1 (wrapping), rows y0..y1-1."""
        y0, y1 = max(0, y0), min(H, y1)
        if y0 >= y1:
            return
        c = self.colour(name)
        for x in range(x0, x1):
            self.px[y0:y1, x % W] = c

    def fill_below(self, tops, name, bottom=H):
        """tops[x]: the row of a ridge's first pixel; everything under it down to row bottom - 1."""
        c = self.colour(name)
        for x in range(W):
            t = int(tops[x])
            if t < bottom:
                self.px[max(0, t):bottom, x] = c


def ground_row(h):
    """Row of the pixel `h` pixels above the horizon line (negative: under it)."""
    return H - 1 - UNDER - h


# 4 x 4 ordered dither (Bayer), thresholds 0..15: a level n of 16 sets the pixels under n. Its
# period divides the 8 x 8 tile, so a band at one level is one repeating tile.
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]])


def dithered(x, y, level):
    return BAYER[y % 4, x % 4] < level


def noise(rng, terms=24, lo=3, hi=60):
    """Periodic fractal noise round the panorama, -1 .. 1 (integer waves, so the ends join)."""
    x = np.arange(W)
    out = np.zeros(W)
    norm = 0.0
    for k in range(terms):
        f = int(rng.integers(lo, hi))
        a = 1.0 / (1 + 0.12 * f)
        out += a * np.sin(2 * math.pi * f * x / W + rng.uniform(0, 2 * math.pi))
        norm += a
    return out / norm


def lobes(centres, widths, heights, base):
    """An envelope round the compass: base plus a raised cosine bump at each bearing (degrees)."""
    x = np.arange(W) / W * 360
    env = np.full(W, float(base))
    for c, w, h in zip(centres, widths, heights):
        d = (x - c + 180) % 360 - 180
        env += h * np.where(np.abs(d) < w, 0.5 + 0.5 * np.cos(np.pi * d / w), 0.0)
    return env


RIDGE = 1.25           # the ranges' height scale: lobes() heights are design pixels
FOOT = 2               # the ranges and the city stand this many rows into the band under the horizon


def mountains(cv, rng, env, rough, name):
    env = env * RIDGE
    n = noise(rng)
    n2 = noise(rng, 40, 20, 140)
    h = np.maximum(env * (1 + rough * (0.75 * n + 0.25 * n2)), 0)
    tops = np.array([ground_row(int(round(v))) for v in h])
    cv.fill_below(tops, name, ground_row(-FOOT) + 1)
    return tops


def feet(cv, name, rows):
    """A range's foot fades into the haze: its lowest `rows` rows above the horizon dithered with
    haze, thicker toward the horizon."""
    c, hz = cv.colour(name), cv.colour('haze')
    for k in range(rows):
        y = ground_row(k)
        level = round(10 * (1 - k / rows))
        for x in range(W):
            if cv.px[y, x] == c and dithered(x, y, level):
                cv.px[y, x] = hz


def speckle(cv, rng, tops, depth, density):
    """Autumn colour in the nearest ridge's top rows: red and gold crowns, one or two pixels."""
    red, gold, near = cv.colour('red'), cv.colour('gold'), cv.colour('near')
    for x in range(W):
        t = int(tops[x])
        for d in range(depth):
            y = t + d
            if y >= H or cv.px[y, x] != near:
                continue
            p = density * (1 - d / depth) ** 1.2
            if rng.random() < p:
                cv.px[y, x] = gold if rng.random() < 0.38 else red
                if rng.random() < 0.5 and x + 1 < W and cv.px[y, x + 1] == near:
                    cv.px[y, x + 1] = cv.px[y, x]


def cloud(cv, cx, cy, w, h):
    """A flat cloud: a lit top and a shaded underside, ragged ends. cy is its row."""
    c, cs = cv.colour('cloud'), cv.colour('cloud_s')
    for dx in range(-w // 2, w // 2 + 1):
        t = max(0.0, 1 - abs(dx) / (w / 2 + 0.01))
        th = int(round(h * (t ** 0.6) * (0.75 + 0.25 * math.sin(dx * 0.31 + cx))))
        for dy in range(th):
            y = cy - th // 2 + dy
            if 0 <= y < H:
                cv.px[y, (cx + dx) % W] = cs if dy >= th - max(1, th // 3) else c


def city(cv, rng, name, lo, hi, a0, a1, minh, maxh, windows, roofs=False):
    """A row of blocks between bearings a0 and a1 (degrees; a1 > a0, may pass 360): widths and heights
    on the 4-pixel grid, windows as 2 x 2 on the grid, in glass colour A or B."""
    x0 = int(a0 / 360 * W) // 4 * 4
    x1 = int(a1 / 360 * W) // 4 * 4
    x = x0
    while x < x1:
        bw = max(int(rng.integers(lo, hi + 1)) // 4 * 4, 4)
        t = (x - x0) / max(1, x1 - x0)          # a gentler envelope: the middle of the span is the tallest
        env = 0.45 + 0.55 * math.sin(math.pi * t) ** 0.7
        bh = int((minh + (maxh - minh) * env * rng.uniform(0.05, 1.0)) * 1.6) // 4 * 4
        if name == 'cfar' and rng.random() < 0.18:
            bh = bh * 2
        bh = max(bh, 4)
        top = ground_row(bh)
        if roofs:
            # a hipped roof (kawara): a 2-3 row tile cap one pixel in at each end
            rh = 2 + int(rng.integers(0, 2))
            cv.rect(x - 1, top - rh, x + bw + 1, top, 'win_b')
            cv.rect(x + 1, top - rh - 1, x + bw - 1, top - rh, 'win_b')
        cv.rect(x, top, x + bw, ground_row(-FOOT) + 1, name)
        if windows:
            for wy in range(top + 2, ground_row(0) - 1, 4):
                for wx in range(x + 1, x + bw - 2, 4):
                    cv.rect(wx, wy, wx + 2, wy + 2, 'win_a' if rng.random() < 0.34 else 'win_b')
        if rng.random() < 0.28 and bw >= 8:     # rooftop: a tank or a stair house on some blocks
            sx = x + int(rng.integers(0, bw - 3)) // 4 * 4
            cv.rect(sx, top - 4, sx + 4, top, name)
        elif rng.random() < 0.12:
            cv.rect(x + bw // 2, top - 6, x + bw // 2 + 1, top, name)
        x += bw


def tower(cv, bearing, height, width=6, bands=6):
    """A lattice radio tower: a tapering red and white banded needle with a platform."""
    cx = int(bearing / 360 * W)
    for h in range(height):
        t = h / height
        half = max(0, round((width / 2) * (1 - t) ** 1.3))
        colour = 'steel' if (h // max(2, height // (bands * 2))) % 2 == 0 else 'cloud'
        y = ground_row(h)
        cv.rect(cx - half, y, cx + half + 1, y + 1, colour)
    pl = int(height * 0.55)
    cv.rect(cx - 4, ground_row(pl) - 1, cx + 5, ground_row(pl) + 2, 'steel')
    cv.rect(cx, ground_row(height) - 3, cx + 1, ground_row(height), 'steel')


def chimney(cv, bearing, height, width=4):
    cx = int(bearing / 360 * W)
    for h in range(height):
        y = ground_row(h)
        cv.rect(cx - width // 2, y, cx + width // 2, y + 1, 'steel' if (height - h) % 8 < 2 else 'cnear')


def crane(cv, bearing, height):
    cx = int(bearing / 360 * W)
    cv.rect(cx, ground_row(height), cx + 2, ground_row(0), 'steel')
    cv.rect(cx - 14, ground_row(height), cx + 20, ground_row(height) + 2, 'steel')
    cv.rect(cx + 18, ground_row(height) + 2, cx + 19, ground_row(height) + 10, 'cloud')


def footing(cv, rows=6):
    """Everything standing on the horizon (the ranges' feet, the city's blocks) fades into the
    haze over its lowest `rows` rows and the FOOT rows under the line: dithered, thicker downward."""
    hz = cv.colour('haze')
    for k in range(-FOOT, rows):
        y = ground_row(k)
        level = min(16, round(13 * (1 - (k + FOOT) / (rows + FOOT)) + 3))
        for x in range(W):
            if cv.px[y, x] and dithered(x, y, level):
                cv.px[y, x] = hz


def under(cv, rng):
    """The band under the horizon: far low town (south) and fields (elsewhere) as haze marks on
    the fog colour, thinning out downward, then the fog colour alone. Every pixel under the
    ranges' and the city's feet is written."""
    hz, fog = cv.colour('haze'), cv.colour('fog')
    top = ground_row(-FOOT) + 1
    cv.px[top:H, :] = fog
    marks = 18                                   # rows of marks under the feet
    # a dithered haze layer, level 9 of 16 under the feet down to 0
    for k in range(marks):
        y = top + k
        level = round(8 * (1 - k / marks) ** 1.3)
        for x in range(W):
            if dithered(x, y, level):
                cv.px[y, x] = hz
    # the low town to the south: rows of roofs, 4 to 12 pixels wide on the 4-pixel grid, sparser
    # and lower down; fields elsewhere: long low strips
    for k, y in enumerate(range(top + 2, top + marks - 2, 4)):
        keep = 0.8 - 0.16 * k
        x = 0
        while x < W:
            bearing = x / W * 360
            south = 95 <= bearing <= 265
            w = int(rng.integers(1, 4 if south else 9)) * 4
            if rng.random() < keep:
                cv.rect(x, y, x + w, y + (2 if south else 1), 'haze')
            x += w + 4 * int(rng.integers(1, 3))


def panorama():
    rng = np.random.default_rng(1969)
    cv = Canvas()
    for n in ('far', 'mid', 'near', 'haze', 'fog'):
        cv.colour(n)
    clouds = [(30, 26, 130, 8), (120, 38, 80, 6), (210, 16, 110, 7), (330, 32, 70, 5), (480, 12, 90, 6),
              (590, 40, 100, 6), (700, 22, 120, 7), (860, 34, 80, 6), (960, 16, 100, 7)]
    for cx, cy, w, h in clouds:
        cloud(cv, cx, cy, int(w * 1.7), int(h * 1.8))
    far = lobes([5, 335, 60, 100, 255, 300], [90, 50, 55, 60, 70, 60], [34, 20, 22, 10, 18, 14], 8)
    mountains(cv, rng, far, 0.28, 'far')
    feet(cv, 'far', 10)
    mid = lobes([350, 25, 85, 270, 310], [80, 45, 50, 60, 50], [30, 22, 16, 16, 12], 5)
    mountains(cv, rng, mid, 0.34, 'mid')
    feet(cv, 'mid', 6)
    near = lobes([0, 45, 315, 100, 260], [80, 50, 55, 50, 50], [20, 14, 14, 12, 12], 3)
    tops = mountains(cv, rng, near, 0.42, 'near')
    speckle(cv, rng, tops, 12, 0.46)
    # the city to the south and the south-east, thinning out round to the east and the west
    city(cv, rng, 'cfar', 8, 16, 90, 270, 8, 20, False)
    city(cv, rng, 'cmid', 8, 20, 105, 255, 10, 30, True)
    city(cv, rng, 'cnear', 8, 20, 120, 240, 5, 18, True, roofs=True)
    city(cv, rng, 'cmid', 8, 16, 285, 340, 6, 12, True)           # the west's danchi
    city(cv, rng, 'cmid', 8, 16, 55, 88, 6, 14, True)             # and the east's
    tower(cv, 198, 64, 7)
    chimney(cv, 135, 24)
    chimney(cv, 232, 20)
    crane(cv, 248, 30)
    footing(cv)
    under(cv, rng)
    return cv


def save(cv, name):
    cols = [hexrgb(C[n]) for n in cv.names[1:]]
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for y in range(H):
        for x in range(W):
            k = cv.px[y, x]
            if k:
                im.putpixel((x, y), cols[k - 1] + (255,))
    im.save(HERE / name)


def tiles(cv):
    seen = {bytes(64)}
    px = cv.px
    for ty in range(H // 8):
        for tx in range(W // 8):
            seen.add(px[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8].tobytes())
    return len(seen)


def gradient(stops, cols, y, horizon):
    """The sky's colour at row y of a preview whose horizon is at row `horizon` (2.84 px a degree)."""
    el = (horizon - y) / 2.84
    if el <= stops[0]:
        return cols[0]
    if el >= stops[-1]:
        return cols[-1]
    for i in range(len(stops) - 1):
        if stops[i] <= el <= stops[i + 1]:
            t = (el - stops[i]) / (stops[i + 1] - stops[i])
            a, b = cols[i], cols[i + 1]
            return tuple(a[k] + (b[k] - a[k]) * t for k in range(3))
    return cols[-1]


def preview(outdir, cv):
    """The panorama on its sky, day and night (the sky's stop under the horizon is the fog colour,
    as make_world.py sets it)."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    tint = (0x4a / 255, 0x58 / 255, 0x84 / 255)
    horizon = 200
    for variant in ('day', 'night'):
        sky = [hexrgb(c) for c in SKY['sky'][variant]]
        sky[0] = hexrgb(FOG[variant])
        im = Image.new('RGB', (W, 300))
        for y in range(300):
            c = tuple(int(v) for v in gradient(SKY['elevations'], sky, y, horizon))
            for x in range(W):
                im.putpixel((x, y), c)
        top = horizon - (H - 1 - UNDER)
        for y in range(H):
            for x in range(W):
                k = cv.px[y, x]
                if not k:
                    continue
                n = cv.names[k]
                col = hexrgb(C[n])
                if variant == 'night':
                    col = tuple(int(col[i] * tint[i]) for i in range(3))
                    if n in NIGHT:
                        col = hexrgb(NIGHT[n])
                im.putpixel((x, top + y), col)
        im.save(outdir / f'backdrop_{variant}.png')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview')
    a = ap.parse_args()
    cv = panorama()
    save(cv, 'backdrop.png')
    used = len(cv.names) - 1
    n = tiles(cv)
    print(f'backdrop.png: {used} colours, {n} tiles of 1024')
    assert used <= 15 and n <= 1024
    # the night's exact colours: the colour as drawn -> the colour in the night variant
    night = {C[k].lower(): v for k, v in NIGHT.items()}
    spec = {'elevations': SKY['elevations'], 'sky': SKY['sky'], 'horizon': UNDER,
            'variants': {'night': night}, 'fog': FOG}
    (HERE / 'backdrop.json').write_text(json.dumps({'town': spec, 'shrine': spec}, indent=1) + '\n')
    if a.preview:
        preview(a.preview, cv)


if __name__ == '__main__':
    sys.exit(main())
