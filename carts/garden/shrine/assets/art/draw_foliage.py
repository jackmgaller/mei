"""Draws art/foliage.png and art/foliage.sheet.json: the forest family's textures (leaf clusters,
far-tree cards, bark, undergrowth, fallen leaves, the shimenawa's rope and paper).

Authored art: run once with Pillow (python3 draw_foliage.py), look at the result and commit it.
Every cell is drawn with at most 15 colours and hard edges (transparent pixels are holes), so the
Asset Kit keeps its colours exactly. Deterministic: the same script draws the same sheet.
"""
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent

# Palette (STYLE.md), plus a few shades of the same hues for depth in the clusters
MAPLE = {'deep': '#8a2418', 'red': '#c8301e', 'scarlet': '#e0502a', 'orange': '#e8782a',
         'shadow': '#5c1a12', 'glow': '#f09838'}
GINKGO = {'gold': '#f0c030', 'pale': '#fad85a', 'amber': '#d89a20', 'shadow': '#a87018',
          'deep': '#7a5414'}
CEDAR = {'deep': '#24382a', 'dark': '#2e4a2e', 'mid': '#3c5a34', 'light': '#4f6a3a',
         'black': '#18261c'}
BARK = {'cedar': '#6a4632', 'cedar_dk': '#4a3a2e', 'cedar_lt': '#86593c', 'cedar_gap': '#38281e',
        'maple': '#5a4a3e', 'ginkgo': '#8a8278', 'ginkgo_dk': '#6a645c'}
MOSS = {'moss': '#5f7a34', 'light': '#6f8a3c', 'dry': '#7c8a3c', 'dark': '#4a6028'}
LITTER = '#9a5a2e'


def rgb(h):
    h = h.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def canvas(w, h):
    return Image.new('RGBA', (w, h), (0, 0, 0, 0))


def blob_mask(w, h, rng, centre, radii, count, spread):
    """A ragged round mask: the union of random circles inside an ellipse."""
    m = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(m)
    cx, cy = centre
    rx, ry = radii
    for _ in range(count):
        a = rng.uniform(0, 2 * math.pi)
        r = math.sqrt(rng.uniform(0, 1))
        x = cx + math.cos(a) * r * (rx - spread)
        y = cy + math.sin(a) * r * (ry - spread)
        s = rng.uniform(spread * 0.5, spread)
        d.ellipse([x - s, y - s, x + s, y + s], fill=255)
    return m


def inside(mask, x, y):
    w, h = mask.size
    xi, yi = int(x), int(y)
    return 0 <= xi < w and 0 <= yi < h and mask.getpixel((xi, yi)) > 0


def star(d, x, y, r, col, rot, lobes=5, inner=0.5):
    pts = []
    for k in range(lobes * 2):
        a = rot + k * math.pi / lobes
        rr = r if k % 2 == 0 else r * inner
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    d.polygon(pts, fill=rgb(col))


def fan(d, x, y, r, col, rot):
    """A ginkgo leaf: a fan of about 120 degrees, and its stalk."""
    a0 = rot - 60
    d.pieslice([x - r, y - r, x + r, y + r], a0, a0 + 120, fill=rgb(col))
    sx = x - math.cos(math.radians(rot)) * r * 0.5
    sy = y - math.sin(math.radians(rot)) * r * 0.5
    d.line([(x, y), (sx, sy)], fill=rgb(col))


def scatter_leaves(img, mask, rng, layers, shape):
    """layers: (colour, count, size range, bias) drawn in order; bias moves leaves down (+) or up."""
    d = ImageDraw.Draw(img)
    w, h = img.size
    for col, count, (s0, s1), bias in layers:
        placed = tries = 0
        while placed < count and tries < count * 40:
            tries += 1
            x = rng.uniform(0, w)
            y = rng.uniform(0, h)
            if bias:
                y = min(h - 1, max(0, y + bias * rng.uniform(0, 1) * h * 0.25))
            if not inside(mask, x, y):
                continue
            shape(d, x, y, rng.uniform(s0, s1), col, rng.uniform(0, 360))
            placed += 1


def maple_shape(d, x, y, r, col, rot):
    star(d, x, y, r, col, math.radians(rot), 5, 0.45)


def ginkgo_shape(d, x, y, r, col, rot):
    fan(d, x, y, r, col, rot)


def clip_to(img, mask):
    """Remove pixels outside a mask (keeps the cluster's ragged outline)."""
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            if mask.getpixel((x, y)) == 0:
                px[x, y] = (0, 0, 0, 0)


def thin(img, rng, fraction):
    """Punch small holes into a cluster: sky seen through the leaves."""
    px = img.load()
    w, h = img.size
    for _ in range(int(w * h * fraction)):
        x, y = rng.randrange(w), rng.randrange(h)
        if px[x, y][3]:
            px[x, y] = (0, 0, 0, 0)


# ---------------------------------------------------------------- leaf clusters (crown cards)

def maple_cluster(seed=1):
    rng = random.Random(seed)
    img = canvas(64, 64)
    mask = blob_mask(64, 64, rng, (32, 32), (30, 29), 34, 10)
    m = MAPLE
    scatter_leaves(img, mask, rng, [
        (m['shadow'], 90, (3.0, 4.5), 1.0),
        (m['deep'], 110, (3.0, 5.0), 0.6),
        (m['scarlet'], 80, (3.0, 4.5), -0.6),
        (m['red'], 150, (3.0, 5.0), 0),
        (m['orange'], 25, (2.5, 4.0), -1.0),
        (m['glow'], 6, (2.0, 3.0), -1.2),
    ], maple_shape)
    thin(img, rng, 0.05)
    return img


def ginkgo_cluster(seed=2):
    rng = random.Random(seed)
    img = canvas(64, 64)
    mask = blob_mask(64, 64, rng, (32, 32), (30, 29), 30, 11)
    g = GINKGO
    scatter_leaves(img, mask, rng, [
        (g['deep'], 50, (3.0, 4.5), 1.0),
        (g['shadow'], 90, (3.0, 4.5), 0.6),
        (g['amber'], 140, (3.0, 4.5), 0.2),
        (g['gold'], 170, (3.0, 4.5), -0.3),
        (g['pale'], 70, (2.5, 3.5), -1.0),
    ], ginkgo_shape)
    thin(img, rng, 0.04)
    return img


def cedar_tuft(seed=3):
    """A sugi spray: dense rounded clumps, dark underneath, lighter tips, drooping a little."""
    rng = random.Random(seed)
    w, h = 64, 48
    img = canvas(w, h)
    mask = Image.new('L', (w, h), 0)
    md = ImageDraw.Draw(mask)
    for _ in range(26):
        x = rng.uniform(8, 56)
        top = 6 + abs(x - 32) * 0.55
        y = rng.uniform(top, 40)
        s = rng.uniform(5, 9)
        md.ellipse([x - s, y - s * 0.8, x + s, y + s * 0.8], fill=255)
    d = ImageDraw.Draw(img)
    c = CEDAR
    for col, n, s0, s1, dy in [
            (c['black'], 60, 3, 5, 2), (c['deep'], 90, 3, 5, 1), (c['dark'], 110, 2.5, 4.5, 0),
            (c['mid'], 90, 2, 3.5, -1), (c['light'], 45, 1.5, 2.5, -2)]:
        for _ in range(n):
            x, y = rng.uniform(0, w), rng.uniform(0, h)
            if not inside(mask, x, y):
                continue
            s = rng.uniform(s0, s1)
            d.ellipse([x - s, y - s * 0.7 + dy, x + s, y + s * 0.7 + dy], fill=rgb(col))
            for _ in range(2):
                a = rng.uniform(0.3, 2.8)
                d.line([(x, y + dy), (x + math.cos(a) * (s + 2), y + dy + math.sin(a) * (s + 1))],
                       fill=rgb(col))
    clip_to(img, mask)
    thin(img, rng, 0.04)
    return img


# ---------------------------------------------------------------- far cards (whole trees)

def maple_far(seed=4, left=8, right=88, top=10, bottom=62):
    """A whole maple: a broad dome over a short trunk forking into limbs. 96 x 96. The dome spans
    left-right, from `top` at its crown to `bottom` (the variants: another dome over the same trunk)."""
    rng = random.Random(seed)
    k = 1.5
    w, h = 96, 96
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    trunk = rgb(BARK['maple'])
    d.polygon([(45, 95), (51, 95), (50, 69), (46, 69)], fill=trunk)
    for (x0, y0, x1, y1) in [(48, 70, 28, 50), (48, 70, 68, 47), (48, 70, 46, 42), (36, 60, 22, 56)]:
        d.line([(x0, y0), (x1, y1)], fill=trunk, width=3)
    mask = Image.new('L', (w, h), 0)
    md = ImageDraw.Draw(mask)
    mid, half = (left + right) / 2, (right - left) / 2
    for _ in range(60):
        x = rng.uniform(left, right)
        crown = top + ((x - mid) / half) ** 2 * 24
        y = rng.uniform(crown + 4, bottom)
        s = rng.uniform(7, 12)
        md.ellipse([x - s, y - s * 0.8, x + s, y + s * 0.8], fill=255)
    m = MAPLE
    leaves = canvas(w, h)
    scatter_leaves(leaves, mask, rng, [
        (m['shadow'], 270, (3, 4.5), 1.0), (m['deep'], 330, (3, 4.5), 0.6),
        (m['scarlet'], 200, (2.5, 4), -0.7), (m['red'], 380, (3, 4.5), 0),
        (m['orange'], 50, (2, 3.5), -1.1), (m['glow'], 12, (2, 3), -1.2)], maple_shape)
    clip_to(leaves, mask)
    img.alpha_composite(leaves)
    thin(img, rng, 0.03)
    return img


def ginkgo_far(seed=5, width=21, top=7):
    """A whole ginkgo: a tall irregular oval of gold, a grey trunk. 48 x 96. `width`: the oval's
    half width at its widest; `top`: its crown (the variants)."""
    rng = random.Random(seed)
    k = 1.5
    w, h = 48, 96
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    d.polygon([(22, 95), (26, 95), (24.8, 30), (23.2, 30)], fill=rgb(BARK['ginkgo_dk']))
    for (y0, a, L) in [(52, -0.9, 14), (44, 0.8, 13), (36, -0.5, 10)]:
        d.line([(24, y0), (24 + math.sin(a) * L, y0 - math.cos(a) * L)], fill=rgb(BARK['ginkgo_dk']), width=2)
    mask = Image.new('L', (w, h), 0)
    md = ImageDraw.Draw(mask)
    for _ in range(46):
        y = rng.uniform(top, 75)
        half = width * math.sin(math.pi * min(1, max(0, (y - top + 4) / (85 - top)))) ** 0.8
        x = 24 + rng.uniform(-half, half) * 0.8
        s = rng.uniform(5, 8.5)
        md.ellipse([x - s, y - s, x + s, y + s], fill=255)
    g = GINKGO
    leaves = canvas(w, h)
    scatter_leaves(leaves, mask, rng, [
        (g['deep'], 110, (2.5, 3.5), 1.0), (g['shadow'], 180, (2.5, 3.5), 0.6),
        (g['amber'], 250, (2.5, 3.5), 0.2), (g['gold'], 290, (2.5, 3.5), -0.3),
        (g['pale'], 110, (2, 3), -1.0)], ginkgo_shape)
    clip_to(leaves, mask)
    img.alpha_composite(leaves)
    thin(img, rng, 0.04)
    return img


def cedar_far(seed=6, base=66, spread=9.5):
    """A sugi spire: straight, narrow, tiers of drooping clumps, a sharp top; trunk below. 32 x 128.
    `base`: the lowest tier (texels / k from the top); `spread`: the tiers' half width at the base
    (the variants: a slimmer and a fuller spire)."""
    rng = random.Random(seed)
    k = 4 / 3
    w, h = 32, 128
    cx = 16
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    d.polygon([(cx - 2, 127), (cx + 2, 127), (cx + 0.5, 26), (cx - 0.5, 26)], fill=rgb(BARK['cedar']))
    c = CEDAR
    y = base * k
    tiers = []
    while y > 6 * k:
        tiers.append(y)
        y -= rng.uniform(4.5, 6.5) * k
    for y in tiers:
        frac = (y - 2 * k) / (64 * k)
        half = min(15.5, (1.5 + spread * frac ** 0.9) * k)
        for side in (-1, 1):
            x1 = cx + side * half * rng.uniform(0.8, 1.05)
            d.polygon([(cx, y - 5 * k), (x1, y + k), (x1 - side * 2 * k, y + 2.5 * k), (cx, y + k)], fill=rgb(c['deep']))
            d.polygon([(cx, y - 5 * k), (x1 * 0.85 + cx * 0.15, y - 0.5 * k), (cx, y - 1.5 * k)], fill=rgb(c['dark']))
            for _ in range(int(3 + half * 1.4)):
                px = cx + (x1 - cx) * rng.uniform(0.15, 0.95)
                py = y - 2 * k + rng.uniform(-2, 2)
                d.ellipse([px - 1.5, py - 1, px + 1.5, py + 1],
                          fill=rgb(rng.choice([c['mid'], c['dark'], c['light'], c['black']])))
    d.polygon([(cx, 0), (cx + 2, 9), (cx - 2, 9)], fill=rgb(c['dark']))
    return img


# ---------------------------------------------------------------- bark

def cedar_bark(w, h, seed):
    """Sugi bark: long fibrous strips, reddish brown, darker cracks running up. Tiles both ways."""
    rng = random.Random(seed)
    img = Image.new('RGBA', (w, h), rgb(BARK['cedar']))
    px = img.load()
    cols = [rgb(BARK['cedar_dk']), rgb(BARK['cedar_lt']), rgb(BARK['cedar_gap'])]
    x = 0.0
    while x < w - 1.5:
        width = rng.uniform(2, 4.5)
        tone = rng.choice([0, 0, 1, None, None])
        wav = rng.uniform(0, 6.28)
        for y in range(h):
            off = math.sin(y / h * 2 * math.pi * 2 + wav) * 0.8
            gx = int(round(x + off)) % w
            px[gx, y] = cols[2]
            if tone is not None:
                for k in range(1, int(width)):
                    if rng.random() < 0.85:
                        px[(gx + k) % w, y] = cols[tone]
        x += width
    return img


# ---------------------------------------------------------------- undergrowth

def fern(seed=7):
    """Three arching fronds side by side, tips to the right."""
    rng = random.Random(seed)
    w, h = 64, 32
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    cols = [MOSS['dark'], MOSS['moss'], MOSS['light'], '#8a9a40', '#a89a48']
    for frond in range(3):
        y0 = 16 + (frond - 1) * 8
        pts = []
        for i in range(60):
            t = i / 59
            pts.append((2 + t * 60, y0 - math.sin(t * math.pi) * 3 + (frond - 1) * t * 2))
        for i, (x, y) in enumerate(pts):
            t = i / 59
            ln = (1 - t) * 6 + 1.2 if t > 0.08 else 1
            if i % 2 == 0:
                k = min(4, int(t * 3 + rng.uniform(0, 1.6)))
                col = rgb(cols[k])
                d.line([(x, y), (x + 1.5, y - ln)], fill=col)
                d.line([(x, y), (x + 1.5, y + ln)], fill=col)
        d.line(pts, fill=rgb(MOSS['dark']))
    return img


def sasa(seed=8):
    """Kuma-zasa: broad dwarf-bamboo leaves with pale withered margins, as in autumn."""
    rng = random.Random(seed)
    w, h = 64, 32
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    green, dark, edge = rgb('#4f6a3a'), rgb('#2e4a2e'), rgb('#b8b48a')
    for _ in range(14):
        x = rng.uniform(6, 58)
        y = rng.uniform(12, 30)
        a = rng.uniform(-0.9, 0.9) - math.pi / 2
        L = rng.uniform(9, 14)
        Wd = rng.uniform(2.5, 3.5)
        tx, ty = x + math.cos(a) * L, y + math.sin(a) * L
        nx, ny = -math.sin(a) * Wd, math.cos(a) * Wd
        mx, my = x + math.cos(a) * L * 0.45, y + math.sin(a) * L * 0.45
        d.polygon([(x, y), (mx + nx * 1.25, my + ny * 1.25), (tx, ty), (mx - nx * 1.25, my - ny * 1.25)], fill=edge)
        d.polygon([(x, y), (mx + nx * 0.7, my + ny * 0.7), (tx - math.cos(a) * 2, ty - math.sin(a) * 2),
                   (mx - nx * 0.7, my - ny * 0.7)], fill=rng.choice([green, green, dark]))
        d.line([(x, min(31, y + 4)), (x, y)], fill=dark)
    return img


def bamboo(seed=9):
    """A few culms with nodes and sprays of narrow leaves near the top."""
    rng = random.Random(seed)
    w, h = 32, 64
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    culm, culm_dk, dry = rgb('#a8b860'), rgb('#8a9a48'), rgb('#c8c890')
    leaf, leaf_dk = rgb('#6f8a3c'), rgb('#4f6a3a')
    for x in [7, 15, 23, 27]:
        top = rng.randint(2, 12)
        lean = rng.uniform(-2, 2)
        d.line([(x, 63), (x + lean, top)], fill=culm, width=2)
        d.line([(x + 1, 63), (x + 1 + lean, top)], fill=culm_dk)
        for ny in range(60, top, -7):
            fx = x + lean * (63 - ny) / (63 - top)
            d.line([(fx, ny), (fx + 1, ny)], fill=culm_dk)
    for _ in range(46):
        x = rng.uniform(2, 30)
        y = rng.uniform(1, 34)
        a = rng.uniform(0.2, 1.2) * rng.choice([-1, 1]) + math.pi / 2
        L = rng.uniform(4, 7)
        d.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=rng.choice([leaf, leaf, leaf_dk]), width=2)
    return img


def susuki(seed=10):
    """Japanese pampas grass in October: arching blades and silver-tan plumes."""
    rng = random.Random(seed)
    w, h = 32, 64
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    blades = [rgb('#7c8a3c'), rgb('#8a9a48'), rgb('#a8a060'), rgb('#5f7a34')]
    plume, plume_lt, stem = rgb('#c8b898'), rgb('#e6dccc'), rgb('#a89870')
    for _ in range(22):
        x0 = rng.uniform(10, 22)
        lean = rng.uniform(-14, 14)
        top = rng.uniform(22, 40)
        pts = []
        for i in range(12):
            t = i / 11
            pts.append((x0 + lean * t * t, 63 - (63 - top) * t + (t * t) * abs(lean) * 0.4))
        d.line(pts, fill=rng.choice(blades))
    for _ in range(6):
        x0 = rng.uniform(12, 20)
        lean = rng.uniform(-10, 10)
        top = rng.uniform(1, 10)
        d.line([(x0, 63), (x0 + lean * 0.7, top + 12)], fill=stem)
        cx, cy = x0 + lean * 0.8, top
        for k in range(10):
            a = math.pi / 2 + rng.uniform(-0.5, 0.5) + lean * 0.03
            L = rng.uniform(6, 12)
            sx, sy = cx + rng.uniform(-1, 1), cy + rng.uniform(0, 6)
            d.line([(sx, sy), (sx + math.cos(a) * L * 0.3 + lean * 0.15, sy + math.sin(a) * L)],
                   fill=plume_lt if k % 3 == 0 else plume)
    return img


def shrub(seed=11):
    """Dodan-tsutsuji in autumn: a rounded clipped shrub, red with green still inside."""
    rng = random.Random(seed)
    img = canvas(32, 32)
    mask = blob_mask(32, 32, rng, (16, 16), (15, 14), 22, 6)
    m = MAPLE

    def leaf(d, x, y, r, c, rot):
        d.ellipse([x - r, y - r * 0.7, x + r, y + r * 0.7], fill=rgb(c))
    scatter_leaves(img, mask, rng, [
        ('#24382a', 40, (2, 3), 1.0), ('#3c5a34', 40, (2, 3), 0.6),
        (m['deep'], 40, (2, 3), 0.2), (m['red'], 50, (2, 3), 0), (m['scarlet'], 35, (1.5, 2.5), -0.8),
        (m['orange'], 12, (1.5, 2), -1.0)], leaf)
    clip_to(img, mask)
    return img


# ---------------------------------------------------------------- fallen leaves

def litter(kind, seed):
    """A ragged patch of fallen leaves, dense in the middle and thinning out to the rim."""
    rng = random.Random(seed)
    img = canvas(64, 64)
    d = ImageDraw.Draw(img)
    if kind == 'red':
        cols = [MAPLE['deep'], MAPLE['red'], MAPLE['scarlet'], MAPLE['orange'], LITTER, '#6a2a1a', MAPLE['glow']]
        weights = [4, 5, 3, 2, 4, 3, 1]
        shape = maple_shape
    else:
        cols = [GINKGO['gold'], GINKGO['pale'], GINKGO['amber'], GINKGO['shadow'], LITTER, MAPLE['orange']]
        weights = [6, 3, 4, 2, 1, 1]
        shape = ginkgo_shape
    pool = [c for c, k in zip(cols, weights) for _ in range(k)]
    for _ in range(900):
        a = rng.uniform(0, 2 * math.pi)
        r = 27.5 * math.sqrt(rng.uniform(0, 1)) ** 0.8
        if rng.random() < (r / 27.5) ** 2.2:
            continue
        x, y = 32 + math.cos(a) * r, 32 + math.sin(a) * r
        shape(d, x, y, rng.uniform(2.2, 3.4), rng.choice(pool), rng.uniform(0, 360))
    return img


# ---------------------------------------------------------------- the sacred tree's dressing

def rope(seed=12):
    """Twisted rice-straw rope: slanting strands; tiles both ways."""
    w, h = 32, 16
    img = Image.new('RGBA', (w, h), rgb('#c8b478'))
    px = img.load()
    a, b, c, base = rgb('#e0d09a'), rgb('#a8925a'), rgb('#7a6838'), rgb('#c8b478')
    for y in range(h):
        for x in range(w):
            s = (x * 2 + y * 4) % 16
            px[x, y] = a if s < 6 else base if s < 9 else b if s < 14 else c
    return img


def shide():
    """A paper streamer: a white strip cut and folded into a zigzag, hung over the rope."""
    w, h = 16, 32
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    white, grey = rgb('#ece4d2'), rgb('#c8c0b0')
    d.rectangle([5, 0, 10, 3], fill=grey)
    # four steps, each a block shifted left or right of the last, with a fold line under it
    for k, (x0, x1) in enumerate([(3, 10), (7, 14), (2, 9), (6, 13), (3, 10)]):
        y0 = 4 + k * 5 + (1 if k else 0)
        y1 = y0 + 4
        d.rectangle([x0, y0, x1, y1], fill=white)
        d.line([(x0, y1), (x1, y1)], fill=grey)
    return img


def moss(seed=13):
    """Moss over old roots: a repeating mottle."""
    rng = random.Random(seed)
    w, h = 32, 32
    img = Image.new('RGBA', (w, h), rgb(MOSS['moss']))
    d = ImageDraw.Draw(img)
    for col, n in [(MOSS['dark'], 50), (MOSS['light'], 60), (MOSS['dry'], 16), (BARK['cedar_dk'], 10)]:
        for _ in range(n):
            x, y, s = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(1, 2.5)
            for ox in (-w, 0, w):
                for oy in (-h, 0, h):
                    d.ellipse([x + ox - s, y + oy - s, x + ox + s, y + oy + s], fill=rgb(col))
    return img


CELLS = [
    ('maple', maple_cluster), ('ginkgo', ginkgo_cluster), ('maple_far', maple_far),
    ('litter_red', lambda: litter('red', 21)), ('litter_gold', lambda: litter('gold', 22)),
    ('cedar', cedar_tuft), ('fern', fern), ('sasa', sasa),
    ('ginkgo_far', ginkgo_far), ('bamboo', bamboo), ('susuki', susuki), ('cedar_far', cedar_far),
    ('cedar_bark', lambda: cedar_bark(16, 64, 14)), ('cedar_bark_tile', lambda: cedar_bark(32, 64, 15)),
    ('shrub', shrub), ('moss', moss), ('rope', rope), ('shide', shide),
    # the far cards' variants (the trees' two crossed cards carry two of them, so a wood seen from
    # far off is not one tree repeated): a lopsided smaller maple, a slimmer taller ginkgo, a
    # slimmer and a fuller cedar
    ('maple_far_b', lambda: maple_far(31, left=18, right=90, top=16, bottom=66)),
    ('ginkgo_far_b', lambda: ginkgo_far(32, width=17, top=3)),
    ('cedar_far_b', lambda: cedar_far(33, base=70, spread=8.0)),
    ('cedar_far_c', lambda: cedar_far(34, base=60, spread=10.5)),
]


def main():
    images = [(name, fn()) for name, fn in CELLS]
    for name, im in images:
        colours = {c for _, c in im.getcolors(im.width * im.height) if c[3]}
        assert len(colours) <= 15, (name, len(colours))
    x = y = shelf = 0      # shelf packing, 256 wide, cells 2 pixels apart
    rects = {}
    for name, im in images:
        w, h = im.size
        if x + w > 256:
            x, y, shelf = 0, y + shelf + 2, 0
        rects[name] = [x, y, w, h]
        x += w + 2
        shelf = max(shelf, h)
    sheet = Image.new('RGBA', (256, y + shelf), (0, 0, 0, 0))
    for name, im in images:
        sheet.paste(im, tuple(rects[name][:2]))
    sheet.save(HERE / 'foliage.png')
    lines = ',\n'.join(f'    "{n}": {json.dumps(r)}' for n, r in rects.items())
    (HERE / 'foliage.sheet.json').write_text(
        '{\n  "format": "mei-sheet",\n  "version": 1,\n  "cells": {\n' + lines + '\n  }\n}\n')


if __name__ == '__main__':
    main()
