#!/usr/bin/env python3
"""Draws the shrine town's water textures (authored art; rerun only to change it):

    water.png        32 x 32, 15 colours: the canal, the school pool and the stream (both regions)
    pond_water.png   32 x 32, 15 colours: the shrine's two ponds and the falls pool
    falls.png        16 x 32, 15 colours: the waterfall's sheet

    python3 carts/garden/shrinetown/art/water/draw_water.py [--preview DIR]

How they move. Each texture is a *colour-cycling* picture: every texel is a phase of a repeating
wave (a texel's colour index is its phase, 0 .. N-1) and the colours of the N phases are a
ramp that goes round once, dull body colour with one narrow bright crest. Rotating the
texture's palette one place a few frames moves every crest one step on, so the ripples travel
(across the canal, down the falls). That costs no VRAM and no ROM beyond the still texture:
`wp_animate()` and an animated sheet would copy a whole frame into the tile (a 32 x 32
4-bit tile is 512 bytes of ROM a frame); this is a 15-colour palette rewritten, 30 bytes. The
pond keeps four colours out of the cycle (floating leaves and a lily pad) that do not move.
`water_cycle.akr` does the rotating (about 600 cycles a frame on average). A still picture of the same texture (frame 0) is what the
world's VRAM holds and what the stand-ins' far colour is the mean of.

Each texture has exactly 15 colours, so the kit's packer gives it a 4-bit palette of its own
(a palette shared with another texture could not be rotated).

It also writes `water_ramps.akr` (the textures' phase colours, which water_cycle.akr finds in
palette memory: the packer may put the palettes anywhere).
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent


def periodic_noise(w, h, rng, terms=7, max_f=3):
    """Smooth noise that tiles: a sum of sines of whole numbers of periods, -1 .. 1."""
    yy, xx = np.mgrid[0:h, 0:w]
    out = np.zeros((h, w))
    norm = 0.0
    for _ in range(terms):
        fx, fy = int(rng.integers(0, max_f + 1)), int(rng.integers(0, max_f + 1))
        if fx == 0 and fy == 0:
            fx = 1
        a = 1.0 / math.hypot(fx, fy)
        out += a * np.sin(2 * math.pi * (fx * xx / w + fy * yy / h) + rng.uniform(0, 2 * math.pi))
        norm += a
    return out / norm


def hexrgb(c):
    return tuple(int(c[k:k + 2], 16) for k in (1, 3, 5))


def mix(a, b, t):
    return tuple(a[k] + (b[k] - a[k]) * t for k in range(3))


def ramp(n, body_lo, body_hi, crest, width, power=1.0):
    """n colours going once round: a body colour that swells between body_lo and body_hi, and a
    narrow crest of `crest` (a Gaussian `width` of the cycle wide) at the middle phase."""
    out = []
    for i in range(n):
        s = i / n
        swell = 0.5 - 0.5 * math.cos(2 * math.pi * s)           # 0 at phase 0, 1 at the middle
        body = mix(body_lo, body_hi, swell ** power)
        d = min(abs(s - 0.5), 1 - abs(s - 0.5))
        h = math.exp(-(d / width) ** 2)
        out.append(mix(body, crest, h))
    return distinct(out)


def distinct(cols):
    """The colours at the GPU's 15 bits (5 per channel), no two the same: the kit tells a texture's
    phases apart by their colours, so a phase that shared a colour would be lost. A clash is
    moved one step of blue, then green, then red (at most 8 of 255 off)."""
    seen, out = set(), []
    for c in cols:
        q = [min(31, max(0, int(round(v)) >> 3)) for v in c]
        k = 0
        while tuple(q) in seen:
            ch = (2, 1, 0)[k % 3]
            q[ch] += 1 if q[ch] < 31 else -1
            k += 1
        seen.add(tuple(q))
        out.append(tuple((v << 3) | (v >> 2) for v in q))
    return out


def save(name, grid, colours, fixed=()):
    """grid: ints, 0 .. len(colours)-1 (cycled phases) then the fixed colours after them."""
    allc = list(colours) + list(fixed)
    h, w = grid.shape
    im = Image.new('RGB', (w, h))
    for y in range(h):
        for x in range(w):
            im.putpixel((x, y), tuple(int(round(v)) for v in allc[grid[y, x]]))
    im.save(HERE / name)
    return im, allc


def phases(w, h, nx, ny, wobble, rng, n, extra=None):
    """The wave: phase = whole bands across the tile plus periodic wobble, 0 .. 1 -> 0 .. n-1."""
    yy, xx = np.mgrid[0:h, 0:w]
    ph = nx * xx / w + ny * yy / h + wobble * periodic_noise(w, h, rng)
    if extra is not None:
        ph = ph + extra
    return np.floor((ph % 1.0) * n).astype(int) % n


def canal():
    rng = np.random.default_rng(1993)
    n = 15
    # murky green-blue water of an old concrete canal under autumn light; one pale crest
    cols = ramp(n, hexrgb('#365a6e'), hexrgb('#47707f'), hexrgb('#a9cbd0'), 0.07, 1.0)
    # bands run across the canal (along x), drifting along it (z): ny whole bands up a repeat
    grid = phases(32, 32, 1, 3, 0.55, rng, n)
    save('water.png', grid, cols)
    return {'file': 'water.png', 'cycled': cols, 'fixed': []}


def pond():
    rng = np.random.default_rng(1996)
    n = 11
    cols = ramp(n, hexrgb('#27423f'), hexrgb('#3d5d54'), hexrgb('#8fb59c'), 0.08, 1.0)
    fixed = [hexrgb('#c8702a'), hexrgb('#d9ad3c'), hexrgb('#8c3a24'), hexrgb('#5f7a34')]
    grid = phases(32, 32, 2, 2, 0.7, rng, n)
    leaves = [(5, 6, 2, 1, 0), (6, 7, 1, 1, 0), (22, 3, 2, 1, 1), (15, 19, 2, 1, 2), (27, 23, 2, 1, 0)]
    for x, y, lw, lh, c in leaves:
        for dy in range(lh):
            for dx in range(lw):
                grid[(y + dy) % 32, (x + dx) % 32] = n + c
    # a lily pad: a small disc of the green, one notch cut
    for y in range(32):
        for x in range(32):
            d = math.hypot((x - 11), (y - 13) * 1.2)
            if d < 2.6 and not (x > 11 and abs(y - 13) < 1):
                grid[y, x] = n + 3
    save('pond_water.png', grid, cols, fixed)
    return {'file': 'pond_water.png', 'cycled': cols, 'fixed': fixed}


def falls():
    rng = np.random.default_rng(1971)
    n = 12
    w, h = 16, 32
    cols = ramp(n, hexrgb('#a4c2d3'), hexrgb('#d6e8f0'), hexrgb('#ffffff'), 0.2, 1.0)
    fixed = [hexrgb('#7e9aaa'), hexrgb('#e6f0f2'), hexrgb('#6a8aa0')]
    yy, xx = np.mgrid[0:h, 0:w]
    # strands: the phase runs down the sheet (one band a tile, so the crests are 32 texels apart),
    # each column a little ahead or behind its neighbour in smooth strands, with a few columns that
    # lag a whole strand
    strand = periodic_noise(w, 1, rng, 3, 2)[0]
    lag = np.zeros(w)
    for x in rng.choice(w, 4, replace=False):
        lag[x] = rng.uniform(0.3, 0.7)
    off = 0.28 * strand + lag
    ph = (yy / h + off[None, :]) % 1.0
    grid = np.floor(ph * n).astype(int) % n
    # fixed spray flecks and two shadow strands
    for _ in range(9):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        grid[y, x] = n + int(rng.integers(0, 2))
    for x in (3, 11):
        for y in range(0, h, 1):
            if rng.random() < 0.55:
                grid[y, x] = n + 2
    save('falls.png', grid, cols, fixed)
    return {'file': 'falls.png', 'cycled': cols, 'fixed': fixed}


def preview(outdir, specs):
    """Each texture tiled 4 x 4 at 4x, and its phases rotated through a cycle."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for name, spec in specs.items():
        im = Image.open(HERE / spec['file']).convert('RGB')
        w, h = im.size
        n = len(spec['cycled'])
        sheet = Image.new('RGB', (w * 3 * 4, h * 3 * 4 * 2))
        for row, step in enumerate((0, n // 3)):
            pal = {tuple(int(round(v)) for v in c): k for k, c in enumerate(spec['cycled'])}
            frame = Image.new('RGB', (w, h))
            for y in range(h):
                for x in range(w):
                    p = im.getpixel((x, y))
                    if p in pal:
                        k = (pal[p] + step) % n
                        p = tuple(int(round(v)) for v in spec['cycled'][k])
                    frame.putpixel((x, y), p)
            big = frame.resize((w * 4, h * 4), Image.NEAREST)
            for ty in range(3):
                for tx in range(3):
                    sheet.paste(big, (tx * w * 4, (row * 3 + ty) * h * 4))
        sheet.save(outdir / f'{name}_tiled.png')


def c15(c):
    return (int(c[0]) >> 3) | (int(c[1]) >> 3) << 5 | (int(c[2]) >> 3) << 10


def write_akr(specs):
    """water_ramps.akr: each texture's cycled colours, in phase order, as the palette holds them
    (15 bits, red low), for water_cycle.akr to find in palette memory and rotate."""
    names = list(specs)
    rows = []
    for k in names:
        cols = [c15(c) for c in specs[k]['cycled']]
        rows.append(cols + [0] * (16 - len(cols)))
    flat = [c for r in rows for c in r]
    assert len(set(c for c in flat if c)) == sum(len(specs[k]['cycled']) for k in names), 'colours clash'
    lines = ['// Generated by carts/garden/shrinetown/art/water/draw_water.py - do not edit.',
             '// The water textures\' colour-cycled phases: texture k\'s phase L at [k * 16 + L] as a palette',
             '// holds it (r | g << 5 | b << 10); the texture order is ' + ', '.join(names) + '.',
             f'const WATER_TEXTURES = {len(names)}',
             f'const WATER_LEVELS: [{len(names)}]s32 = [' + ', '.join(str(len(specs[k]['cycled'])) for k in names) + ']',
             f'const WATER_RAMP: [{len(flat)}]u16 = [']
    for k in range(0, len(flat), 8):
        lines.append('    ' + ', '.join(str(c) for c in flat[k:k + 8]) + ',')
    lines.append(']')
    (HERE / 'water_ramps.akr').write_text('\n'.join(lines) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview')
    a = ap.parse_args()
    specs = {'water': canal(), 'pond_water': pond(), 'falls': falls()}
    write_akr(specs)
    if a.preview:
        preview(a.preview, specs)
    for k, v in specs.items():
        print(k, v['file'], len(v['cycled']), 'cycled +', len(v['fixed']), 'fixed')


if __name__ == '__main__':
    sys.exit(main())
