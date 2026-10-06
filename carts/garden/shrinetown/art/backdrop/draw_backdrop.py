#!/usr/bin/env python3
"""Draws the shrine town's two backdrops (authored art; rerun only to change it):

    town_backdrop.png     1024 x 112, 15 colours: seen from the streets (region `town`)
    shrine_backdrop.png   1024 x 112, 15 colours: seen from the shrine's grounds and woods (region `shrine`)
    backdrop.json         the skies, the night's exact colours and the silhouettes' placement, for apply_patch.py

    python3 carts/garden/shrinetown/art/backdrop/draw_backdrop.py [--preview DIR]

Each PNG is the Horizon Engine's silhouette panorama (WORLDKIT.md, "Backdrops"): 1,024 pixels
round the compass (2.84 a degree, column 0 north, then east, south at column 512), the bottom row
on the horizon (4 rows stand under it), transparent where the sky shows, at most 15 colours. The sky
itself (a gradient on the backdrop colour, stops by elevation, day and night) is in backdrop.json.

What is in each, far to near: a wisp of mackerel cloud; blue ranges; a nearer forested ridge with
the autumn's red and gold in its top rows; and on the town's side the city: far blocks in haze,
the middle rows with their windows, the near rows with roofs, a water tank, a radio tower, a brick
chimney, a crane. The shrine's view has more mountain to the north, east and west, and to the
south the town as seen from above it: tiled roofs in rows and a skyline of apartment blocks.

Windows are 2 x 2 pixels on a 4-pixel grid in one of two glass colours that differ by a hair in
daylight; the night variant lights one of them (backdrop.json, "variants"), so about a third of
the windows glow after dark. The grid is 4 pixels and the buildings' edges are on it so that an
8 x 8 tile of wall repeats: the atlas holds 1,024 tiles at most (it is 34 to 40 % of that).
Deterministic: fixed seeds.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
W, H = 1024, 112
UNDER = 6                                      # rows below the horizon line

# palette (day): name -> colour
C = {
    'far':      '#9db1c3',     # farthest range, haze
    'mid':      '#7d9ba7',     # second range
    'near':     '#55745b',     # nearest forested ridge
    'red':      '#b2573a',     # maple red, in the ridge's top rows
    'gold':     '#c99a46',     # ginkgo gold
    'cloud':    '#f3ebdc',     # cloud lit side
    'cloud_s':  '#d6cbc0',     # cloud shaded underside
    'cfar':     '#adb8c6',     # the far city's blocks, in haze
    'cmid':     '#8e98a8',     # the middle rows
    'cnear':    '#6e7788',     # the near rows
    'roof':     '#5a5c64',     # tiled roofs
    'win_a':    '#566680',     # window glass; this one is lit at night
    'win_b':    '#4e5e78',     # window glass; dark at night
    'steel':    '#b33d36',     # tower and crane: red and white bands
    'white':    '#ece8e0',
}
NIGHT = {                      # exact colours after the night's multiply tint
    'win_a': '#f2cf78',        # lit
    'cloud': '#46517a',
    'cloud_s': '#2c3358',
    'steel': '#d84a3c',        # the tower's lamp-lit bands
    'white': '#9aa0c4',
    'red': '#4c3446',
    'gold': '#5a5a46',
}

SKY = {
    'elevations': [-8, 0, 3, 9, 26, 70],
    'sky': {
        'day':   ['#7d8456', '#ecdcb4', '#d3dfdc', '#9cc4e0', '#6a9fd2', '#3a6cb0'],
        'night': ['#141420', '#5a4466', '#352c58', '#1c1e42', '#0c1028', '#04060f'],
    },
}


def hexrgb(c):
    return tuple(int(c[k:k + 2], 16) for k in (1, 3, 5))


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

    def hline(self, x0, x1, y, name):
        if 0 <= y < H:
            for x in range(x0, x1):
                self.px[y, x % W] = self.colour(name)

    def rect(self, x0, y0, x1, y1, name):
        """Columns x0..x1-1 (wrapping), rows y0..y1-1."""
        y0, y1 = max(0, y0), min(H, y1)
        if y0 >= y1:
            return
        c = self.colour(name)
        for x in range(x0, x1):
            self.px[y0:y1, x % W] = c

    def fill_below(self, tops, name):
        """tops[x]: the row of a ridge's first pixel; everything under it."""
        c = self.colour(name)
        for x in range(W):
            t = int(tops[x])
            if t < H:
                self.px[max(0, t):H, x] = c


def ground_row(h):
    """Row of the pixel `h` pixels above the horizon line."""
    return H - 1 - UNDER - h


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


RIDGE = {'town': 1.9, 'shrine': 1.5}     # the ridges' height scales: lobes() heights are design pixels
view = 'town'


def mountains(cv, rng, env, rough, name, floor=0):
    env = env * RIDGE[view]
    n = noise(rng)
    n2 = noise(rng, 40, 20, 140)
    h = env * (1 + rough * (0.75 * n + 0.25 * n2))
    h = np.maximum(h, floor)
    tops = np.array([ground_row(int(round(v))) for v in h])
    cv.fill_below(tops, name)
    return tops


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
                if rng.random() < 0.5 and x + 1 < W and y < H and cv.px[y, x + 1] == near:
                    cv.px[y, x + 1] = cv.px[y, x]


def cloud(cv, cx, cy, w, h, rng):
    """A flat cloud: a lit top and a shaded underside, ragged ends. cy is its row."""
    c, cs = cv.colour('cloud'), cv.colour('cloud_s')
    for dx in range(-w // 2, w // 2 + 1):
        t = max(0.0, 1 - abs(dx) / (w / 2 + 0.01))
        th = int(round(h * (t ** 0.6) * (0.75 + 0.25 * math.sin(dx * 0.31 + cx))))
        for dy in range(th):
            y = cy - th // 2 + dy
            if 0 <= y < H:
                cv.px[y, (cx + dx) % W] = cs if dy >= th - max(1, th // 3) else c


def clouds(cv, rng, bands):
    for cx, cy, w, h in bands:
        cloud(cv, cx, cy, int(w * 1.7), int(h * 1.8), rng)


def city(cv, rng, layer, name, lo, hi, a0, a1, minh, maxh, windows, gap=0, roofs=False, step=4):
    """A row of blocks between bearings a0 and a1 (degrees; a1 > a0, may pass 360): widths and heights
    on the 4-pixel grid, windows as 2 x 2 on the grid, in glass colour A or B."""
    x0 = int(a0 / 360 * W) // 4 * 4
    x1 = int(a1 / 360 * W) // 4 * 4
    x = x0
    wa, wb = cv.colour('win_a'), cv.colour('win_b')
    base = cv.colour(name)
    roof = cv.colour('roof')
    while x < x1:
        bw = int(rng.integers(lo, hi + 1)) // 4 * 4
        bw = max(bw, 4)
        # a gentler envelope: the middle of the span is the tallest
        t = (x - x0) / max(1, x1 - x0)
        env = 0.45 + 0.55 * math.sin(math.pi * t) ** 0.7
        bh = int((minh + (maxh - minh) * env * rng.uniform(0.05, 1.0)) * 1.6) // 4 * 4
        if name == 'cfar' and rng.random() < 0.18:
            bh = bh * 2
        bh = max(bh, 4)
        top = ground_row(bh)
        if roofs:
            # a hipped roof (kawara): a 2-3 row tile cap one pixel in at each end
            rh = 2 + int(rng.integers(0, 2))
            cv.rect(x - 1, top - rh, x + bw + 1, top, 'roof')
            cv.rect(x + 1, top - rh - 1, x + bw - 1, top - rh, 'roof')
        cv.rect(x, top, x + bw - gap, ground_row(0) + 1, name)
        cv.rect(x, ground_row(0) + 1, x + bw - gap, ground_row(-UNDER) + 1, 'cfar')     # the haze at its foot
        if windows:
            # windows start one row under the roof line, on the 4-pixel grid
            for wy in range(top + 2, ground_row(0) - 1, 4):
                for wx in range(x + 1, x + bw - 2, 4):
                    cv.rect(wx, wy, wx + 2, wy + 2, 'win_a' if rng.random() < 0.34 else 'win_b')
        # rooftop: a tank or a stair house on some blocks
        if rng.random() < 0.28 and bw >= 8:
            sw = 4
            sx = x + int(rng.integers(0, bw - sw + 1)) // 4 * 4
            cv.rect(sx, top - 4, sx + sw, top, name)
        elif rng.random() < 0.12:
            cv.rect(x + bw // 2, top - 6, x + bw // 2 + 1, top, name)
        x += bw


def tower(cv, bearing, height, width=6, bands=6, base_y=None):
    """A lattice radio tower: a tapering red and white banded needle with a platform."""
    cx = int(bearing / 360 * W)
    for h in range(height):
        t = h / height
        half = max(0, round((width / 2) * (1 - t) ** 1.3))
        colour = 'steel' if (h // max(2, height // (bands * 2))) % 2 == 0 else 'white'
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
    cv.rect(cx + 18, ground_row(height) + 2, cx + 19, ground_row(height) + 10, 'white')


def town_view():
    global view
    view = 'town'
    rng = np.random.default_rng(1990)
    cv = Canvas()
    for n in ('far', 'mid', 'near'):
        cv.colour(n)
    # mackerel cloud, high in the east and the south-west
    clouds(cv, rng, [(150, 30, 120, 7), (214, 22, 70, 5), (300, 40, 90, 6), (560, 24, 110, 6),
                     (640, 33, 60, 5), (780, 20, 100, 6), (900, 36, 70, 5), (30, 26, 60, 5)])
    far = lobes([0, 330, 40, 120, 250], [75, 50, 45, 60, 70], [16, 10, 12, 4, 8], 7)
    mountains(cv, rng, far, 0.30, 'far')
    mid = lobes([350, 30, 280, 130], [70, 40, 60, 60], [14, 10, 8, 4], 4)
    mountains(cv, rng, mid, 0.34, 'mid')
    near = lobes([0, 20, 300, 90], [70, 50, 50, 55], [10, 8, 8, 5], 2.5)
    tops = mountains(cv, rng, near, 0.40, 'near')
    speckle(cv, rng, tops, 9, 0.38)
    # the city to the south and the south-east, thinning out round to the east and the west
    city(cv, rng, 0, 'cfar', 8, 18, 70, 300, 6, 14, False)
    city(cv, rng, 1, 'cmid', 8, 20, 95, 270, 8, 26, True)
    city(cv, rng, 2, 'cnear', 8, 24, 120, 245, 6, 20, True, roofs=False)
    city(cv, rng, 1, 'cmid', 8, 16, 300, 350, 6, 12, True)           # the west's danchi
    city(cv, rng, 1, 'cmid', 8, 16, 55, 85, 6, 14, True)             # and the east's
    tower(cv, 203, 60, 6)
    chimney(cv, 131, 24)
    crane(cv, 244, 30)
    return cv


def shrine_view():
    global view
    view = 'shrine'
    rng = np.random.default_rng(1969)
    cv = Canvas()
    for n in ('far', 'mid', 'near'):
        cv.colour(n)
    clouds(cv, rng, [(30, 44, 130, 8), (120, 56, 80, 6), (210, 34, 110, 7), (330, 50, 70, 5),
                     (480, 30, 90, 6), (590, 58, 100, 6), (700, 40, 120, 7), (860, 52, 80, 6), (960, 34, 100, 7)])
    far = lobes([5, 335, 60, 100, 255, 300], [90, 50, 55, 60, 70, 60], [34, 20, 22, 10, 18, 14], 8)
    mountains(cv, rng, far, 0.28, 'far')
    mid = lobes([350, 25, 85, 270, 310], [80, 45, 50, 60, 50], [30, 22, 16, 16, 12], 5)
    mountains(cv, rng, mid, 0.34, 'mid')
    near = lobes([0, 45, 315, 100, 260], [80, 50, 55, 50, 50], [20, 14, 14, 12, 12], 3)
    tops = mountains(cv, rng, near, 0.42, 'near')
    speckle(cv, rng, tops, 12, 0.46)
    # the town seen from above: tiled roofs in rows, apartment blocks, the city beyond them
    city(cv, rng, 0, 'cfar', 8, 16, 90, 270, 8, 20, False)
    city(cv, rng, 1, 'cmid', 8, 20, 105, 255, 10, 32, True)
    city(cv, rng, 2, 'cnear', 8, 20, 120, 240, 5, 18, True, roofs=True)
    city(cv, rng, 2, 'cnear', 4, 12, 130, 230, 4, 8, False, roofs=True)    # the nearest, low tiled roofs
    city(cv, rng, 1, 'cmid', 8, 16, 280, 310, 6, 12, True)
    city(cv, rng, 1, 'cmid', 8, 16, 60, 90, 6, 14, True)
    tower(cv, 198, 72, 7)
    chimney(cv, 135, 26)
    chimney(cv, 232, 20)
    crane(cv, 250, 32)
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
    return cv


def tiles(cv):
    seen = {bytes(32)}
    px = cv.px
    for ty in range(H // 8):
        for tx in range(W // 8):
            seen.add(px[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8].tobytes())
    return len(seen)


def gradient(stops, cols, y):
    """The sky's colour at row y of a preview 1024 x 256 whose horizon is at row 200 (2.84 px a degree)."""
    el = (200 - y) / 2.84
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


def preview(outdir, views):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    tint = (0x4a / 255, 0x58 / 255, 0x84 / 255)
    for name, cv in views.items():
        for variant in ('day', 'night'):
            sky = [hexrgb(c) for c in SKY['sky'][variant]]
            im = Image.new('RGB', (W, 256))
            for y in range(256):
                c = gradient(SKY['elevations'], sky, y)
                for x in range(W):
                    im.putpixel((x, y), tuple(int(v) for v in c))
            top = 200 - (H - 1 - UNDER)
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
            im.save(outdir / f'{name}_{variant}.png')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview')
    a = ap.parse_args()
    views = {'town_backdrop': town_view(), 'shrine_backdrop': shrine_view()}
    for name, cv in views.items():
        save(cv, f'{name}.png')
        used = len(cv.names) - 1
        print(f'{name}.png: {used} colours, {tiles(cv)} tiles of 1024')
        assert used <= 15
    # the night's exact colours: the colour as drawn -> the colour in the night variant
    night = {C[k].lower(): v for k, v in NIGHT.items()}
    spec = {
        'elevations': SKY['elevations'], 'sky': SKY['sky'], 'horizon': UNDER,
        'variants': {'night': night},
    }
    (HERE / 'backdrop.json').write_text(json.dumps({'town': spec, 'shrine': spec}, indent=1) + '\n')
    if a.preview:
        preview(a.preview, views)


if __name__ == '__main__':
    sys.exit(main())
