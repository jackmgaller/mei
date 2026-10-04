#!/usr/bin/env python3
"""Draws water_sheet.png and water_sheet.sheet.json: the textures of the shrine's water family
(the falls and their foam, the stepping stones, the bobbing log, the lily pads and their flower,
the reeds, the bamboo fence). Authored art: run once, look, commit the PNG. Needs Pillow.

    python3 carts/garden/shrine/assets/art/draw_water.py
"""
import json
import math
import random
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SHEET_W, SHEET_H = 256, 192


def hexc(s):
    s = s.lstrip('#')
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


CLEAR = (0, 0, 0, 0)


def tile_noise(w, h, cells, seed):
    """Smooth value noise that wraps in both directions: cells x cells lattice, bilinear with a
    smoothstep, values 0..1."""
    rnd = random.Random(seed)
    cx, cy = cells
    grid = [[rnd.random() for _ in range(cx)] for _ in range(cy)]

    def f(x, y):
        gx, gy = x / w * cx, y / h * cy
        x0, y0 = int(math.floor(gx)), int(math.floor(gy))
        tx, ty = gx - x0, gy - y0
        tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
        a = grid[y0 % cy][x0 % cx]
        b = grid[y0 % cy][(x0 + 1) % cx]
        c = grid[(y0 + 1) % cy][x0 % cx]
        d = grid[(y0 + 1) % cy][(x0 + 1) % cx]
        return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty
    return f


def ramp(colours, t):
    t = min(max(t, 0.0), 0.999)
    return colours[int(t * len(colours))]


# --- the falls: 8 frames, 32 x 64, each the one before moved 8 rows down (period 64) ---------

FALL = [hexc(c) for c in ('#4f80a0', '#6a98b4', '#8ab0c4', '#a8c4d4', '#c4d8e4', '#dce8f0',
                          '#f2f6f8', '#ffffff')]


def falls_base():
    w, h = 32, 64
    rnd = random.Random(7)
    # Each column a stream of its own brightness; streams drift a little across with height.
    column = [0.35 + 0.65 * rnd.random() for _ in range(w)]
    for _ in range(2):   # soften: neighbours share light
        column = [(column[i - 1] + 2 * column[i] + column[(i + 1) % w]) / 4 for i in range(w)]
    streak = tile_noise(w, h, (16, 4), 11)
    fine = tile_noise(w, h, (32, 16), 12)
    img = []
    for y in range(h):
        row = []
        for x in range(w):
            sway = int(round(1.5 * math.sin(2 * math.pi * (y / h * 2 + x / w))))
            c = column[(x + sway) % w]
            v = 0.7 * c + 0.4 * streak(x, y) + 0.3 * fine(x, y) - 0.3
            row.append(ramp(FALL, v))
        img.append(row)
    return img


# --- the foam at the foot: 4 frames, 32 x 32, moving 8 rows a frame (outwards, down the mound) --

FOAM = [hexc(c) for c in ('#7aa4bc', '#a0c0d0', '#c4d8e4', '#dce8f0', '#f2f6f8', '#ffffff')]


def foam_base():
    w, h = 32, 32
    a = tile_noise(w, h, (8, 8), 21)
    b = tile_noise(w, h, (16, 16), 22)
    return [[ramp(FOAM, 0.15 + 0.65 * a(x, y) + 0.45 * b(x, y) - 0.2) for x in range(w)]
            for y in range(h)]


def shifted(img, k):
    h = len(img)
    return [img[(y - k) % h] for y in range(h)]


# --- stepping stone tops: mossy granite with a few fallen leaves, 32 x 32, tiling -------------

def stone_top(seed, leaves):
    w = h = 32
    stone = [hexc(c) for c in ('#8e887c', '#a29c8e', '#b4ae9e', '#c2bcac')]
    moss = [hexc(c) for c in ('#5f7a34', '#7a8050', '#6f8a3c')]
    n = tile_noise(w, h, (8, 8), seed)
    g = tile_noise(w, h, (32, 32), seed + 1)
    m = tile_noise(w, h, (4, 4), seed + 2)
    img = []
    for y in range(h):
        row = []
        for x in range(w):
            mv = m(x, y) + 0.2 * g(x, y)
            if mv > 0.78:
                row.append(moss[int((g(x, y) * 2.99))])
            else:
                row.append(ramp(stone, 0.6 * n(x, y) + 0.6 * g(x, y) - 0.1))
        img.append(row)
    rnd = random.Random(seed + 3)
    for colour, shape in leaves:
        cx, cy = rnd.randrange(w), rnd.randrange(h)
        c = hexc(colour)
        for dx, dy in shape:
            img[(cy + dy) % h][(cx + dx) % w] = c
    return img


MAPLE = [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1), (-2, -1), (2, -1), (0, -2), (-1, 1), (1, 1)]
GINKGO = [(0, 0), (-1, 0), (1, 0), (-2, -1), (-1, -1), (0, -1), (1, -1), (2, -1), (0, 1)]


# --- log bark and end grain ----------------------------------------------------------------

def bark():
    w = h = 32
    tones = [hexc(c) for c in ('#2e241c', '#4a3a2e', '#5a4a3e', '#6a4632', '#7a5a44')]
    moss = [hexc(c) for c in ('#4f6a3a', '#5f7a34', '#6f8a3c')]
    furrow = tile_noise(w, h, (8, 2), 31)      # u around: 8 ridges; v along: long furrows
    fine = tile_noise(w, h, (16, 16), 32)
    mos = tile_noise(w, h, (4, 2), 33)
    img = []
    for y in range(h):
        row = []
        for x in range(w):
            r = 0.5 + 0.5 * math.sin(2 * math.pi * (x / 8 + 0.15 * furrow(x, y)))
            if mos(x, y) + 0.2 * fine(x, y) > 0.92:
                row.append(moss[int(fine(x, y) * 2.99)])
            else:
                row.append(ramp(tones, 0.7 * r + 0.35 * fine(x, y) - 0.05))
        img.append(row)
    return img


def end_grain():
    w = h = 16
    rings = [hexc(c) for c in ('#b08a5e', '#9a7650', '#c49c6c')]
    edge = hexc('#4a3a2e')
    img = []
    for y in range(h):
        row = []
        for x in range(w):
            d = math.hypot(x + 0.5 - 8, y + 0.5 - 8)
            if d > 6.6:
                row.append(edge)
            else:
                row.append(rings[int(d * 0.9) % 3] if d > 1.2 else hexc('#6a4a30'))
        img.append(row)
    return img


# --- lily pads: a disc with its notch cut out, autumn at the rim ------------------------------

def pad(seed, notch_angle, autumn):
    w = h = 32
    greens = [hexc(c) for c in ('#2e4a2e', '#3c5a34', '#4f6a3a', '#5f7a34')]
    rust = [hexc(c) for c in ('#7c8a3c', '#9a5a2e', '#8a6a48')]
    n = tile_noise(w, h, (6, 6), seed)
    img = []
    for y in range(h):
        row = []
        for x in range(w):
            dx, dy = x + 0.5 - 16, y + 0.5 - 16
            d = math.hypot(dx, dy)
            a = math.atan2(dy, dx)
            da = (a - notch_angle + math.pi) % (2 * math.pi) - math.pi
            if d > 15.2 or (abs(da) < 0.16 + 0.02 * d and d > 1.5):
                row.append(CLEAR)
                continue
            vein = abs(math.sin(a * 7)) < 0.12 and d > 2.5
            rim = d > 15.2 - (0.6 + 2.2 * autumn * n(x, y))
            if rim and autumn > 0:
                row.append(rust[int(n(x, y) * 1.99 + (1 if d > 14.4 else 0)) % 3])
            elif vein:
                row.append(greens[3])
            else:
                row.append(greens[min(2, int(0.4 * d / 8 + 1.6 * n(x, y)))])
        img.append(row)
    return img


def petals(w, h, count, colours, seed):
    """A ring of petals for a cylindrical projection: tips at the top, holes between them."""
    rnd = random.Random(seed)
    cols = [hexc(c) for c in colours]
    img = []
    for y in range(h):
        row = []
        t = y / (h - 1)                       # 0 at the top (tips), 1 at the base
        for x in range(w):
            p = (x + 0.5) / w * count % 1.0   # position across one petal, 0..1
            half = 0.5 * min(1.0, 0.35 + 1.3 * t)
            if abs(p - 0.5) > half:
                row.append(CLEAR)
                continue
            shade = 1 if abs(p - 0.5) > half * 0.6 else 0
            row.append(cols[min(len(cols) - 1, shade + (2 if t > 0.75 else 0))])
        img.append(row)
    return img


# --- reeds: dry autumn reeds with plumes, cutout, drawn once (fit) ----------------------------

def reeds(seed):
    w, h = 32, 64
    img = [[CLEAR] * w for _ in range(h)]
    rnd = random.Random(seed)
    blade = [hexc(c) for c in ('#5f7a34', '#7c8a3c', '#8a9a48', '#a8a070', '#c8c890')]
    plume = [hexc(c) for c in ('#9a5a2e', '#b08a5e', '#c8a878')]
    for i in range(30):
        x0 = 2 + rnd.random() * 28
        top = rnd.randrange(2, 30)
        lean = (rnd.random() - 0.5) * 10
        col = blade[rnd.randrange(len(blade))]
        for y in range(top, h):
            t = (h - y) / (h - top)
            x = int(round(x0 + lean * t * t))
            if 0 <= x < w:
                img[y][x] = col
                if t < 0.5 and x + 1 < w:      # blades thicken toward the base
                    img[y][x + 1] = col
        if rnd.random() < 0.6:                  # a plume on top
            pc = plume[rnd.randrange(len(plume))]
            xt = int(round(x0 + lean))
            for dy in range(0, 7):
                for dx in (-1, 0, 1):
                    if (dx == 0 or dy in (1, 2, 3, 4)) and 0 <= xt + dx < w and top + dy - 6 >= 0:
                        img[top + dy - 6][xt + dx] = pc
    # a few broad iris leaves, long gone yellow at the tips
    leaf = [hexc(c) for c in ('#4f6a3a', '#7c8a3c', '#d89a20')]
    for i in range(4):
        x0 = 4 + rnd.random() * 24
        top = rnd.randrange(24, 40)
        lean = (rnd.random() - 0.5) * 12
        for y in range(top, h):
            t = (h - y) / (h - top)
            x = int(round(x0 + lean * t * t))
            c = leaf[2] if t > 0.85 else leaf[1] if t > 0.5 else leaf[0]
            for dx in (0, 1):
                if 0 <= x + dx < w:
                    img[y][x + dx] = c
    return img


# --- bamboo fence: vertical split culms with nodes, and the bundled rails --------------------

def bamboo_panel():
    """Eight split culms, 4 texels each, side by side, with their nodes; tiles both ways."""
    w, h = 32, 64
    tones = [hexc(c) for c in ('#5e6230', '#8a9a48', '#a8a868', '#c8c890', '#d8d4a8')]
    node = hexc('#6a6a3a')
    rnd = random.Random(41)
    n = tile_noise(w, h, (8, 4), 42)
    nodes = [rnd.randrange(h) for _ in range(8)]
    img = []
    for y in range(h):
        row = []
        for x in range(w):
            k, p = divmod(x, 4)
            if p == 0:
                row.append(tones[0])            # the gap between culms
                continue
            if y in (nodes[k], (nodes[k] + 32) % h):
                row.append(node)
                continue
            light = [2, 4, 3][p - 1]
            age = n(x, y)
            row.append(tones[max(1, min(4, light - (1 if age > 0.6 else 0) - (1 if k % 3 == 1 else 0)))])
        img.append(row)
    return img


def bamboo_rail():
    w, h = 16, 8
    tones = [hexc(c) for c in ('#6a6a3a', '#8a9a48', '#a8a868', '#c8c890')]
    rope = [hexc('#2c2a28'), hexc('#4a4642')]
    img = []
    for y in range(h):
        row = []
        for x in range(w):
            if x in (7, 8):
                row.append(rope[(x + y) % 2])
            else:
                row.append(tones[[1, 2, 3, 3, 2, 2, 1, 0][y]])
        img.append(row)
    return img


def main():
    sheet = Image.new('RGBA', (SHEET_W, SHEET_H), CLEAR)
    cells = {}

    def put(name, img, x, y):
        h, w = len(img), len(img[0])
        for j in range(h):
            for i in range(w):
                sheet.putpixel((x + i, y + j), img[j][i])
        cells[name] = [x, y, w, h]

    base = falls_base()
    for k in range(8):
        put('falls_%d' % k, shifted(base, 8 * k), 32 * k, 0)
    fbase = foam_base()
    for k in range(4):
        put('foam_%d' % k, shifted(fbase, 8 * k), 32 * k, 64)
    put('stone_a', stone_top(51, [('#c8301e', MAPLE), ('#e8782a', MAPLE)]), 128, 64)
    put('stone_b', stone_top(61, [('#f0c030', GINKGO), ('#c8301e', MAPLE)]), 160, 64)
    put('stone_c', stone_top(71, [('#e0502a', MAPLE)]), 192, 64)
    put('bark', bark(), 224, 64)
    put('end_grain', end_grain(), 0, 96)
    put('pad_a', pad(81, 0.9, 1.0), 32, 96)
    put('pad_b', pad(91, 2.6, 0.4), 64, 96)
    put('petals', petals(32, 16, 6, ('#fbf6ee', '#ece4d2', '#f0d0cc', '#e0b0b4'), 101), 96, 96)
    put('stamens', petals(16, 8, 8, ('#fad85a', '#f0c030', '#d89a20'), 102), 96, 112)
    put('bamboo_rail', bamboo_rail(), 128, 96)
    put('reeds_a', reeds(111), 0, 128)
    put('reeds_b', reeds(121), 32, 128)
    put('bamboo', bamboo_panel(), 64, 128)

    sheet.save(HERE / 'water_sheet.png')
    (HERE / 'water_sheet.sheet.json').write_text(json.dumps(
        {'format': 'mei-sheet', 'version': 1, 'cells': cells}, indent=1) + '\n')


if __name__ == '__main__':
    main()
