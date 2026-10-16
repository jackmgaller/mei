#!/usr/bin/env python3
"""The aquarium, room 5: the life-support plant, dressed. Writes the room's Asset Kit recipes into
dressed/, their textures into dressed/art/ and aq_plant.placements.json beside this script
(--no-placements leaves the placements alone).

    python3 carts/afterhours/rooms/aq_plant/dress_aq_plant.py

The basement under the galleries, the building's engine room: loud, wet, industrial.

- open sumps of sea water, dark green, a little below the walkways: the work lamps' reflections
  broken in them, foam where the returns and the pumps churn, the intakes' strainers under the
  surface; the channel along the front wall;
- grated walkways of galvanised steel with yellow edges and railings, wet footprints, the lamps'
  pools on them;
- the three sand filters along the back (the stage's sand filters: only here): tall pressure
  vessels painted machinery green, whole to their domed heads (they stand against the back wall
  and hide only it: the level lead's call), with seam bands, a manway, their valve nests and
  gauges in front, their pipes climbing the back wall to the manifold;
- four pumps: two on the front walkway with their suction pipes dipping into the sump behind, two
  standing on plinths in the sumps;
- work lamps: cage lamps on the back wall, clamp lamps on the front railing, lamps over the
  cross walkways beyond the section;
- on the back wall, cream over a green dado: the ear-defender and hazard pictograms, a clipboard,
  stains under the pipes;
- the stairs: up to quarantine beyond the west door, the service stair up to the kitchen beyond
  the east one.

The floor plan is the level lead's (PLAN.md, make_aq_plant.py), imported for its numbers. Needs
NumPy and Pillow.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'aq_quar'))
import make_aq_plant as G  # noqa: E402  (the lead's plan: imported for its numbers only)
from aqdress import (CUT_H, Cells, Mesh, Room, at, beyond_flight, blob, box, collision_recipe, grid,  # noqa: E402
                     hex_rgb, kit_lighting, mat_tex, paint_rgb, paint_floor, paint_wall, placements_file, prune, r,
                     rect, recipe, save_art, smoothstep, to_image, vram, wet, write_json)
from s2dress import SLAB  # noqa: E402
from dresskit import shade_plane  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'water'))   # agent W: the moving water (NOTES_W.md)
import wateranim  # noqa: E402

OUT = HERE / 'dressed'
ART = OUT / 'art'
P = 'ap_'
R = Room(G.ROOM, P)
PROPS = {p[0]: p[2] for p in G.ROOM['props']}
WATER = {k: v for k, v in PROPS.items() if k == 'channel' or k.startswith('sump')}
FILTERS = [PROPS[f'filter_{k}'] for k in range(3)]
PUMPS = [PROPS[f'pump_{k}'] for k in range(4)]
SINK = -0.3            # the water's surface under the walkways
X0, X1, Z0, Z1 = R.X0, R.X1, R.Z0, R.Z1
AMBIENT = 0.3

# the textures' spans: (x0, x1, z0, z1)
FLOOR_SPANS = {
    'walk_front_w': (X0, 0.0, G.WALK_A[0], G.WALK_A[1]), 'walk_front_e': (0.0, X1, G.WALK_A[0], G.WALK_A[1]),
    'walk_back_w': (X0, 0.0, G.WALK_B[0], Z1), 'walk_back_e': (0.0, X1, G.WALK_B[0], Z1),
    **{f'cross_{k}': (a, b, G.WALK_A[1], G.WALK_B[0]) for k, (a, b) in enumerate(G.CROSS)},
}
WATER_SPANS = {'water_w': (X0, 0.0, Z0, G.WALK_B[0]), 'water_e': (0.0, X1, Z0, G.WALK_B[0])}
SIZES = {'walk_front_w': (255, 34), 'walk_front_e': (255, 34), 'walk_back_w': (255, 88), 'walk_back_e': (255, 88),
         'cross_0': (34, 102), 'cross_1': (34, 102), 'cross_2': (34, 102), 'water_w': (255, 127), 'water_e': (255, 127)}

BACK_LAMPS = [(-8.1, 2.2, 4.3), (-3.4, 2.2, 4.3), (2.0, 2.2, 4.3), (7.3, 2.2, 4.3)]
CLAMP_LAMPS = [(-6.6, 0.95, -3.33), (1.8, 0.95, -3.33), (7.4, 0.95, -3.33)]
CEIL_LAMPS = [(-4.6, 2.7, 0.4), (0.4, 2.7, 0.4), (5.4, 2.7, 0.4)]


def is_water(x, z):
    return any(x0 <= x <= x1 and z0 <= z <= z1 for (x0, z0, x1, z1) in WATER.values())


def lights():
    out = []
    for k, at_ in enumerate(BACK_LAMPS):
        out.append({'id': f'back_{k}', 'at': list(at_), 'color': '#ffd8a0', 'intensity': 1.5, 'range': 5.2, 'shadows': True})
    for k, at_ in enumerate(CEIL_LAMPS):
        out.append({'id': f'ceil_{k}', 'at': list(at_), 'color': '#ffe4b8', 'intensity': 1.4, 'range': 4.6, 'shadows': True})
    for k, at_ in enumerate(CLAMP_LAMPS):
        out.append({'id': f'clamp_{k}', 'at': list(at_), 'color': '#fff0d4', 'intensity': 1.1, 'range': 3.2})
    out.append({'id': 'door_kitchen', 'at': [R.XO1 + 0.8, 1.8, -2.8], 'color': '#d8e8ff', 'intensity': 1.4, 'range': 3.2})
    out.append({'id': 'door_quar', 'at': [R.XO0 - 0.8, 1.8, 2.0], 'color': '#c8b8f0', 'intensity': 1.0, 'range': 2.8})
    return out


def blockers():
    out = [(x0 + 0.2, 0, z0 + 0.05, x1 - 0.2, 2.6, z1) for (x0, z0, x1, z1) in FILTERS]
    out += [(x0, 0, z0, x1, 0.9, z1) for (x0, z0, x1, z1) in PUMPS]
    return out


# ---- painting

def caustics(x, z, scale=1.0, seed=0.0):
    x = x * scale
    z = z * scale
    a = np.sin(x * 2.1 + np.sin(z * 1.7 + seed) * 1.4 + seed)
    b = np.sin(z * 2.6 + np.sin(x * 1.3 - seed) * 1.2 - seed * 0.5)
    c = np.sin((x + z) * 1.6 + np.sin((x - z) * 1.1 + seed) * 1.1)
    return np.clip(1 - np.abs((a + b + c) / 3.0) * 2.6, 0, 1) ** 3


def walk_base(x, z):
    """Walkways and the back zone in white light: galvanised grating in 1 m panels with yellow edges
    over the water, concrete in the back zone, wet footprints."""
    h, w = x.shape
    rng = np.random.default_rng(int(abs(x[0, 0] * 13 + z[0, 0] * 7)) + 3)
    base = np.zeros((h, w, 3)) + np.array([142, 148, 150]) + (rng.random((h, w)) - 0.5)[..., None] * 16
    # the grating's bars: a fine cross-hatch, darker between
    hatch = ((np.floor(x / 0.06) + np.floor(z / 0.06)) % 2 == 0)
    base *= np.where(hatch, 1.0, 0.88)[..., None]
    # 1 m panels along each walkway: a darker seam
    seam = np.abs((x / 1.0) % 1 - 0.5) > 0.485
    cross = np.zeros_like(x, dtype=bool)
    for (a, b) in G.CROSS:
        cross |= (x > a) & (x < b) & (z > G.WALK_A[1]) & (z < G.WALK_B[0])
    seam_c = np.abs((z / 1.0) % 1 - 0.5) > 0.485
    base *= np.where((seam & ~cross) | (seam_c & cross), 0.7, 1.0)[..., None]
    # the back zone is concrete, not grating
    back = z > G.WALK_B[1]
    conc = np.zeros((h, w, 3)) + np.array([150, 146, 136]) + (rng.random((h, w)) - 0.5)[..., None] * 10
    conc *= (1 + 0.05 * np.sin(x * 1.3 + np.sin(z * 2.1) * 2))[..., None]
    base = np.where(back[..., None], conc, base)
    # a channel drain along the back zone's front edge, and the filters' plinths
    base = paint_rgb(base, back & (np.abs(z - (G.WALK_B[1] + 0.12)) < 0.05), (60, 62, 64))
    base = paint_rgb(base, back & (np.abs(z - (G.WALK_B[1] + 0.12)) < 0.03) & ((x * 20) % 1 < 0.4), (130, 134, 136))
    for (x0, z0, x1, z1) in FILTERS:
        base = paint_rgb(base, rect(x, z, x0 - 0.05, z0 - 0.08, x1 + 0.05, z1) > 0, (120, 118, 112))
    # yellow edges over the water: wherever the floor meets a water box
    for (x0, z0, x1, z1) in WATER.values():
        near = rect(x, z, x0 - 0.07, z0 - 0.07, x1 + 0.07, z1 + 0.07) > 0
        stripe = ((x + z) / 0.2) % 1 < 0.55
        base = paint_rgb(base, near & stripe, (226, 184, 40))
        base = paint_rgb(base, near & ~stripe, (40, 40, 40))
    # puddles and wet footprints along the engineer's round
    for k, (cx, cz) in enumerate(((-6.2, 2.0), (-4.6, -1.2), (0.4, 0.3), (-2.6, -2.9), (5.4, -0.9), (4.4, 3.8), (-3.6, 3.6))):
        base *= (1 - 0.25 * wet(x, z, cx, cz, 0.55, 0.3, k))[..., None]
    for k in range(18):
        fx, fz = -8.0 + k * 0.62, 2.0 + (0.12 if k % 2 else -0.12)
        base *= (1 - 0.18 * blob(x, z, fx, fz, 0.07, 0.04))[..., None]
    return base


def walk_extra(x, z, rgb):
    # the pumps' status lamps catch the wet grating
    for (x0, z0, x1, z1) in PUMPS[:2]:
        rgb = rgb + (blob(x, z, (x0 + x1) / 2, z0 - 0.1, 0.35, 0.15) * 0.25)[..., None] * np.array([80, 255, 140])
    return rgb


def water_base(x, z):
    """The sea water in white light: dark green, deeper under the middle of each sump, the
    intakes' strainers under it."""
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array([38, 104, 104])
    for (x0, z0, x1, z1) in WATER.values():
        d = np.minimum.reduce([x - x0, x1 - x, z - z0, z1 - z])
        base *= (1 - 0.35 * smoothstep(0.0, 1.2, d) * rect(x, z, x0, z0, x1, z1))[..., None]
    # the strainers: dark grilles under the surface by each sump's front kerb
    for cx in (-7.0, -2.2, 2.9, 7.6):
        s = rect(x, z, cx - 0.35, G.WALK_A[1] + 0.15, cx + 0.35, G.WALK_A[1] + 0.5) > 0
        base = paint_rgb(base, s, (20, 50, 54))
        base = paint_rgb(base, s & ((x * 14) % 1 < 0.35), (34, 76, 78))
    return base


def paint_water(span, size):
    x0, x1, z0, z1 = span
    w, h = size
    x, z = grid(x0, x1, z0, z1, w, h)
    base = water_base(x, z)
    P3 = np.stack([x.ravel(), np.full(x.size, SINK), z.ravel()], axis=1)
    lit = shade_plane(P3, (0, 1, 0), [dict(L, shadows=False) for L in lights()], AMBIENT * 0.8).reshape(h, w, 3)
    rgb = base * (0.5 + 0.5 * lit)
    # ripples: bands across the surface
    rip = 0.16                  # agent W: the ripples move (ap_wwater's overlay): their average
    rgb = rgb * (0.9 + 0.35 * rip)
    # the lamps' reflections, where the camera sees them: streaks broken by the ripple
    for (lx, ly, lz), col, strength in ([(L, (255, 214, 150), 1.0) for L in CEIL_LAMPS] +
                                        [(L, (255, 236, 200), 0.8) for L in CLAMP_LAMPS]):
        zr = lz - (ly - SINK) / math.tan(math.radians(60))
        streak = np.exp(-((x - lx) / 0.2) ** 2 - ((z - zr) / 0.7) ** 2)
        broken = 0.5                # agent W: the streak's breaking up moves (ap_wwater's glints at its place)
        rgb = rgb + (streak * broken * strength)[..., None] * np.array(col) * 0.9
    # foam: where the filters' returns pour in under the back walkway, and round the pumps in the sumps
    rng = np.random.default_rng(int(x0 * 10) + 99)
    speck = rng.random(x.shape)
    churn = np.zeros_like(x)
    for cx in (-7.0, -2.2, 3.0, 7.5):
        churn = np.maximum(churn, blob(x, z, cx, G.WALK_B[0] - 0.25, 0.55, 0.3))
    for (px0, pz0, px1, pz1) in PUMPS[2:]:
        churn = np.maximum(churn, blob(x, z, (px0 + px1) / 2, (pz0 + pz1) / 2, 0.7, 0.55) * 0.8)
    foam = (speck < churn ** 2 * 0.55) | ((churn > 0.8) & (speck < 0.75))
    rgb = np.where(foam[..., None], rgb * 0.3 + np.array([170, 196, 190]), rgb)
    rgb = rgb + (churn * 0.25)[..., None] * np.array([60, 90, 90])
    # the kerbs' shadow on the water along every edge, and the walkways' dark undersides
    for (wx0, wz0, wx1, wz1) in WATER.values():
        d = np.minimum.reduce([x - wx0, wx1 - x, z - wz0, wz1 - z])
        inside = rect(x, z, wx0, wz0, wx1, wz1)
        rgb = rgb * (1 - 0.5 * inside * np.exp(-np.clip(d, 0, None) / 0.07))[..., None]
    # the channel along the front: a faint current line
    rgb = rgb + (np.exp(-((z - (Z0 + 0.55)) / 0.08) ** 2) * 0.15 * (np.sin(x * 3) * 0.5 + 0.5))[..., None] * np.array([90, 140, 140])
    return to_image(rgb, dither=4.0)


def wall_base(x, y):
    """The back wall in white light: cream paint over a green dado, stains under the pipes, the
    pictograms (ear defenders, a hazard triangle, a slip warning), a clipboard on a hook."""
    h, w = x.shape
    rng = np.random.default_rng(5)
    base = np.zeros((h, w, 3)) + np.array([206, 200, 180]) + (rng.random((h, w)) - 0.5)[..., None] * 8
    base = np.where((y < 1.2)[..., None], np.array([104, 140, 118]), base)
    base = np.where((np.abs(y - 1.2) < 0.02)[..., None], np.array([70, 90, 76]), base)
    # damp stains running down under the manifold
    for k in range(12):
        sx = -8.5 + k * 1.55 + (k % 3) * 0.2
        base *= (1 - 0.2 * np.exp(-((x - sx) / 0.12) ** 2) * smoothstep(1.85, 0.4, y))[..., None]
    # concrete wall joints
    base *= np.where(np.abs(((x + 9.25) / 3.0) % 1 - 0.5) > 0.495, 0.85, 1.0)[..., None]

    def sign(cx, cy, bg, rim, s=0.18):
        nonlocal base
        base = paint_rgb(base, rect(x, y, cx - s, cy - s, cx + s, cy + s) > 0, rim)
        base = paint_rgb(base, rect(x, y, cx - s + 0.03, cy - s + 0.03, cx + s - 0.03, cy + s - 0.03) > 0, bg)
    # ear defenders (blue disc, white muffs) by both doors and mid-wall
    for cx in (-8.4, -2.6, 8.3):
        cy = 1.55
        base = paint_rgb(base, np.hypot(x - cx, y - cy) < 0.17, (30, 90, 190))
        band = (np.abs(np.hypot(x - cx, y - cy + 0.02) - 0.1) < 0.02) & (y > cy - 0.02)
        base = paint_rgb(base, band | (np.hypot(x - (cx - 0.1), y - (cy - 0.04)) < 0.04) |
                         (np.hypot(x - (cx + 0.1), y - (cy - 0.04)) < 0.04), (240, 244, 250))
    # hazard triangles (yellow, a black mark)
    for cx in (1.2, 6.6):
        cy = 1.5
        tri = (y > cy - 0.14) & (y < cy + 0.16) & (np.abs(x - cx) < (cy + 0.16 - y) * 0.6)
        base = paint_rgb(base, tri, (30, 30, 30))
        tri2 = (y > cy - 0.1) & (y < cy + 0.1) & (np.abs(x - cx) < (cy + 0.1 - y) * 0.55)
        base = paint_rgb(base, tri2, (240, 200, 30))
        base = paint_rgb(base, (np.abs(x - cx) < 0.012) & (y > cy - 0.06) & (y < cy + 0.04), (30, 30, 30))
    # the clipboard on its hook
    base = paint_rgb(base, rect(x, y, -4.4, 1.25, -4.12, 1.62) > 0, (120, 90, 60))
    base = paint_rgb(base, rect(x, y, -4.37, 1.28, -4.15, 1.56) > 0, (236, 234, 226))
    for k in range(5):
        base = paint_rgb(base, (np.abs(y - (1.5 - k * 0.05)) < 0.006) & (x > -4.34) & (x < -4.18), (90, 100, 140))
    return base


def paint_section(w=255, h=24):
    """The front wall in section, below ground: concrete over the floor line, the earth under."""
    x, y = grid(R.XO0, R.XO1, -SLAB, CUT_H, w, h)
    i, j = np.meshgrid(np.arange(w), np.arange(h))
    rgb = np.zeros((h, w, 3)) + np.array([84, 88, 96])
    rgb = np.where((((i + j) % 6 == 0) & (y >= 0))[..., None], np.array([104, 108, 116]), rgb)
    rgb = np.where((y < 0)[..., None], np.array([70, 56, 44]), rgb)
    rgb = np.where((((i * 3 + j * 5) % 11 == 0) & (y < 0))[..., None], np.array([96, 78, 60]), rgb)
    rgb = np.where((np.abs(y) < 0.04)[..., None], np.array([150, 156, 164]), rgb)
    rgb = np.where((y > CUT_H - 0.05)[..., None], np.array([122, 130, 146]), rgb)
    return to_image(rgb, dither=0)


def paint_filter_cut(n=32):
    """A sand filter's cut, from above (a disc): the steel shell, sand, the centre distributor."""
    img = Image.new('RGB', (n, n), (40, 44, 46))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, n - 1, n - 1], fill=(70, 96, 82))
    d.ellipse([2, 2, n - 3, n - 3], fill=(200, 176, 128))
    rng = np.random.default_rng(3)
    for k in range(40):
        px, py = rng.integers(4, n - 4, 2)
        if (px - n / 2) ** 2 + (py - n / 2) ** 2 < (n / 2 - 4) ** 2:
            img.putpixel((int(px), int(py)), (170, 146, 104) if k % 2 else (226, 206, 160))
    d.ellipse([n // 2 - 3, n // 2 - 3, n // 2 + 2, n // 2 + 2], fill=(60, 64, 70))
    return img


def paint_rail(n=16):
    """The railing: a top rail, a knee rail, a toe board and a post every metre; holes between."""
    img = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    yellow = (230, 190, 40, 255)
    d.rectangle([0, 0, n - 1, 1], fill=yellow)
    d.rectangle([0, 7, n - 1, 7], fill=(200, 166, 36, 255))
    d.rectangle([0, n - 2, n - 1, n - 1], fill=(180, 150, 36, 255))
    d.rectangle([0, 0, 1, n - 1], fill=yellow)
    return img


def paint_gauge(n=12):
    img = Image.new('RGB', (n, n), (40, 40, 40))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, n - 1, n - 1], fill=(236, 236, 230), outline=(40, 40, 40))
    d.line([(n // 2, n // 2), (n - 3, 3)], fill=(200, 30, 30))
    d.arc([2, 2, n - 3, n - 3], 200, 300, fill=(40, 160, 60))
    return img


def paint_motor(w=16, h=8):
    """A pump motor's side: cooling fins and a rating plate (a blank silver square)."""
    img = Image.new('RGB', (w, h), (60, 100, 170))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 2):
        d.line([(k, 0), (k, h)], fill=(44, 76, 136))
    d.rectangle([5, 2, 9, 5], fill=(200, 204, 208))
    return img


# ---- the recipes

def floor_nodes():
    xs = [X0, X1, 0.0] + [v for ab in G.CROSS for v in ab]
    zs = [Z0, Z1, *G.WALK_A, *G.WALK_B]
    cells = Cells(xs, zs, is_water, SINK)
    n = cells.tops(FLOOR_SPANS, 'floor', False) + cells.tops(WATER_SPANS, 'water', True)
    n.append(cells.kerbs('kerbs', 'kerb', lip='walk_edge', lip_h=0.08))
    return n, cells


def rail_nodes(cells):
    """Railings along every walkway edge over the water: runs of the cells' edges, two quads each
    (double-sided cutouts)."""
    runs = []
    nx, nz = len(cells.xs) - 1, len(cells.zs) - 1
    for i in range(nx):
        for j in range(nz):
            if cells.sunk[i][j]:
                continue
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a, b = i + di, j + dj
                if 0 <= a < nx and 0 <= b < nz and cells.sunk[a][b]:
                    if di:
                        x = cells.xs[i + 1] if di > 0 else cells.xs[i]
                        x += -0.04 * di
                        runs.append(('z', x, cells.zs[j], cells.zs[j + 1]))
                    else:
                        z = cells.zs[j + 1] if dj > 0 else cells.zs[j]
                        z += -0.04 * dj
                        runs.append(('x', z, cells.xs[i], cells.xs[i + 1]))
    # merge collinear neighbours
    runs.sort()
    merged = []
    for run in runs:
        if merged and merged[-1][0] == run[0] and abs(merged[-1][1] - run[1]) < 1e-6 and abs(merged[-1][3] - run[2]) < 1e-6:
            merged[-1] = (run[0], run[1], merged[-1][2], run[3])
        else:
            merged.append(run)
    mx, mz = Mesh(), Mesh()
    for axis, c, a, b in merged:
        # keep clear of the walls and of the doorways' thresholds
        a, b = a + 0.04, b - 0.04
        if axis == 'x':
            a, b = max(a, X0 + 0.06), min(b, X1 - 0.06)
            mx.quad_z(c, a, b, 0.0, 0.99, -1, 'rail_x')
        else:
            mz.quad_x(c, 0.0, 0.99, a, b, -1, 'rail_z')
    return [mx.node('rails_x', 'rail_x'), mz.node('rails_z', 'rail_z')]


def filter_nodes():
    n = []
    for k, (x0, z0, x1, z1) in enumerate(FILTERS):
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        rad = (z1 - z0) / 2 - 0.03
        # whole, full height (J, 2026-10-15): they stand against the back wall and hide only it; a
        # pressure vessel with a domed head, a band at each seam, a manway on its face
        n.append(at({'id': f'filter_{k}', 'op': 'lathe', 'segments': 12, 'caps': False, 'material': 'filter',
                     'profile': [[rad, -0.02], [rad, 1.95], [rad * 0.93, 2.1], [rad * 0.72, 2.24], [rad * 0.4, 2.33], [0.0, 2.37]]},
                    translate=[cx, 0.0, cz]))
        for j, y in enumerate((0.55, 1.6)):
            n.append(at({'id': f'band_{k}{j}', 'op': 'cylinder', 'radius': rad + 0.035, 'height': 0.07, 'segments': 12,
                         'caps': False, 'material': 'band'}, translate=[cx, y, cz]))
        n.append(at({'id': f'manway_{k}', 'op': 'cylinder', 'radius': 0.2, 'height': 0.06, 'segments': 8,
                     'material': 'band', 'faces': {'bottom': 'manway'}},
                    translate=[cx + 0.3, 1.25, cz - rad + 0.02], rotate=[90, 0, 0]))
        n.append(at({'id': f'vent_{k}', 'op': 'cylinder', 'radius': 0.05, 'height': 0.12, 'segments': 6,
                     'material': 'pipe_grey'}, translate=[cx, 2.38, cz]))
        # a plinth, the vessel's skirt
        n.append(box(f'plinth_{k}', (cx - rad - 0.04, -0.02, cz - rad - 0.04), (cx + rad + 0.04, 0.12, min(z1, cz + rad + 0.04)),
                     'plinth', open=['bottom'] + (['front'] if cz + rad + 0.04 >= z1 else [])))
        # the valve nest in front: two headers across, valves, a gauge on a stalk
        for j, y in enumerate((0.32, 0.78)):
            n.append(at({'id': f'header_{k}{j}', 'op': 'cylinder', 'radius': 0.07, 'height': x1 - x0 - 0.1, 'segments': 6,
                         'material': 'pipe_green' if j else 'pipe_grey'},
                        translate=[cx, y, z0 + 0.12], rotate=[0, 0, 90]))
            for s in (-1, 1):
                n.append(at({'id': f'valve_{k}{j}{s + 1}', 'op': 'cylinder', 'radius': 0.11, 'height': 0.03, 'segments': 6,
                             'material': 'valve'}, translate=[cx + s * 0.62, y, z0 + 0.02], rotate=[90, 0, 0]))
        n.append(box(f'gauge_post_{k}', (cx - 0.02, 0.78, z0 + 0.1), (cx + 0.02, 0.92, z0 + 0.14), 'pipe_grey', open=['bottom']))
        n.append(at({'id': f'gauge_{k}', 'op': 'cylinder', 'radius': 0.07, 'height': 0.03, 'segments': 8,
                     'material': 'gauge_rim', 'faces': {'bottom': 'gauge'}},
                    translate=[cx, 0.92, z0 + 0.08], rotate=[90, 0, 0]))
        # the pipes up the back wall beside the vessel to the manifold
        for s in (-1, 1):
            n.append(at({'id': f'riser_{k}{s + 1}', 'op': 'cylinder', 'radius': 0.07, 'height': 1.95, 'segments': 6,
                         'caps': False, 'material': 'pipe_green'}, translate=[cx + s * 0.86, 0.95, Z1 - 0.12]))
    # the manifold along the back wall, and a second, grey return line under it
    n.append(at({'id': 'manifold', 'op': 'cylinder', 'radius': 0.11, 'height': X1 - X0 - 0.04, 'segments': 6, 'caps': False,
                 'material': 'pipe_green'}, translate=[0.0, 1.95, Z1 - 0.13], rotate=[0, 0, 90]))
    n.append(at({'id': 'return', 'op': 'cylinder', 'radius': 0.07, 'height': X1 - X0 - 0.04, 'segments': 6, 'caps': False,
                 'material': 'pipe_blue'}, translate=[0.0, 1.7, Z1 - 0.08], rotate=[0, 0, 90]))
    return n


def pump_nodes():
    n = []
    for k, (x0, z0, x1, z1) in enumerate(PUMPS):
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        if k < 2:
            # on the walkway: a base plate, a motor along x, the volute, the suction pipe into the sump
            n.append(box(f'pump_base_{k}', (x0, -0.02, z0), (x1, 0.1, z1), 'pump_base', open=['bottom', 'front']))
            n.append(at({'id': f'motor_{k}', 'op': 'cylinder', 'radius': 0.17, 'height': 0.38, 'segments': 8,
                         'material': 'motor', 'faces': {'side': 'motor_side'}},
                        translate=[x0 + 0.21, 0.3, cz], rotate=[0, 0, 90]))
            n.append(at({'id': f'volute_{k}', 'op': 'cylinder', 'radius': 0.2, 'height': 0.14, 'segments': 8,
                         'material': 'volute'}, translate=[x1 - 0.1, 0.32, cz], rotate=[0, 0, 90]))
            n.append(at({'id': f'outlet_{k}', 'op': 'cylinder', 'radius': 0.06, 'height': 0.4, 'segments': 6,
                         'material': 'pipe_blue'}, translate=[x1 - 0.1, 0.7, cz], rotate=[0, 0, 0]))
            n.append(box(f'suction_{k}', (x1 - 0.16, 0.26, cz), (x1 - 0.04, 0.38, z1 + 0.3), 'pipe_grey', open=['back']))
            n.append(box(f'dip_{k}', (x1 - 0.15, SINK - 0.05, z1 + 0.19), (x1 - 0.05, 0.27, z1 + 0.29), 'pipe_grey',
                         open=['bottom']))
            n.append(box(f'lamp_{k}', (x0 + 0.05, 0.1, z0 - 0.0), (x0 + 0.12, 0.17, z0 + 0.03), 'status', open=['bottom']))
        else:
            # in the sump: a concrete plinth out of the water, an upright pump, its discharge to the walkway
            # its face against the cross walkway's kerb is open (it would lie in the kerb's plane)
            against = 'right' if any(abs(x1 - a) < 1e-6 for a, _ in G.CROSS) else 'left'
            n.append(box(f'pump_plinth_{k}', (x0, SINK - 0.05, z0), (x1, 0.05, z1), 'plinth', open=['bottom', against]))
            n.append(at({'id': f'motor_{k}', 'op': 'cylinder', 'radius': 0.2, 'height': 0.51, 'segments': 8,
                         'material': 'motor', 'faces': {'side': 'motor_side'}}, translate=[cx, 0.545, cz]))
            n.append(at({'id': f'casing_{k}', 'op': 'cylinder', 'radius': 0.25, 'height': 0.26, 'segments': 8,
                         'material': 'volute'}, translate=[cx, 0.17, cz]))
            n.append(at({'id': f'fan_{k}', 'op': 'cylinder', 'radius': 0.16, 'height': 0.13, 'segments': 8,
                         'material': 'motor_cap'}, translate=[cx, 0.855, cz]))
    return n


def lamp_nodes():
    n = []
    for k, (x, y, z) in enumerate(BACK_LAMPS):
        n.append(box(f'cage_{k}', (x - 0.16, y - 0.1, Z1 - 0.2), (x + 0.16, y + 0.1, Z1 + 0.01), 'cage', open=['front'],
                     faces={'back': 'lamp_glow', 'bottom': 'lamp_glow'}))
    for k, (x, y, z) in enumerate(CLAMP_LAMPS):
        n.append(box(f'clamp_{k}', (x - 0.05, 0.86, z - 0.07), (x + 0.05, 0.97, z + 0.03), 'cage'))
        n.append(at({'id': f'clamp_head_{k}', 'op': 'cone', 'radius': 0.1, 'height': 0.12, 'segments': 6,
                     'material': 'cage', 'faces': {'bottom': 'lamp_glow'}}, translate=[x, 0.9, z + 0.1], rotate=[-70, 0, 0]))
    return n


def room_recipe(cells_nodes, cells):
    chunks = R.back_chunks(9.5)
    m = R.shell_materials()
    m['section'] = mat_tex(P + 'section', '#5a5a5c', bits=4)
    for name in list(FLOOR_SPANS) + list(WATER_SPANS):
        m[name] = mat_tex(P + name, '#2a6a6a' if name.startswith('water') else '#8a8e90')
    for name, *_ in chunks:
        m[name] = mat_tex(P + name, '#b0aa98')
    m.update({
        'wall_in': {'color': '#8a8e88'}, 'end': {'color': '#b4b0a0'}, 'reveal': {'color': '#a4a090'},
        'lintel': {'color': '#9a9688'}, 'door_glow': {'color': '#e8eef4', 'class': 'emissive'},
        'kerb': {'color': '#4a5a58', 'class': 'emissive'}, 'walk_edge': {'color': '#c8a434', 'class': 'emissive'},
        'threshold': {'color': '#8a8a84', 'class': 'emissive'}, 'beyond_wall': {'color': '#6a6c70', 'class': 'emissive'},
        'tread': {'color': '#9a9a90', 'class': 'emissive'}, 'riser': {'color': '#5a5a54', 'class': 'emissive'},
        'stair_wall': {'color': '#5a5c66', 'class': 'emissive'}, 'stair_landing': {'color': '#8a8a84', 'class': 'emissive'},
        'filter': {'color': '#6a9a80', 'smooth': True}, 'band': {'color': '#4e7a62'},
        'manway': {'color': '#5a8a70'}, 'filter_cut': {'color': '#c8b088', 'class': 'emissive',
                                                       'texture': {'image': f'art/{P}filter_cut.png', 'bits': 4,
                                                                   'projection': 'disc', 'axis': 'y'}},
        'plinth': {'color': '#8a8880'}, 'pipe_green': {'color': '#5a8a70'}, 'pipe_grey': {'color': '#9aa0a4'},
        'pipe_blue': {'color': '#4a78b0'}, 'valve': {'color': '#c03a30'}, 'gauge_rim': {'color': '#30343a'},
        'gauge': mat_tex(P + 'gauge', '#e0e0d8', bits=4), 'pump_base': {'color': '#4a5058'},
        'motor': {'color': '#3c64aa'}, 'motor_side': mat_tex(P + 'motor', '#3c64aa', bits=4, emissive=False),
        'motor_cap': {'color': '#2c4a80'}, 'volute': {'color': '#7a8088'}, 'status': {'color': '#50ff90', 'class': 'emissive'},
        'cage': {'color': '#3a3c40'}, 'lamp_glow': {'color': '#fff0c8', 'class': 'emissive'},
    })
    n = list(cells_nodes) + R.wall_nodes(chunks)
    # the end walls' doorways sit on the walkways; under the doorways the water does not reach
    n += [beyond_flight(R, 'quar', 6, landing=0.5, threshold='stair_landing', side_wall='stair_wall'),
          beyond_flight(R, 'kitchen', 6, landing=0.5, threshold='stair_landing', side_wall='stair_wall')]
    n += lamp_nodes()
    props = filter_nodes() + pump_nodes()
    # the shell (floor, water, walls, lamps, the ways on) and the machinery apart: the shell alone
    # fits the kit's stand-in cap (700 triangles)
    return (recipe(P + 'room', prune(m, n), n, kit_lighting(lights(), AMBIENT, {'tolerance': 24, 'max_added': 60}), 1000),
            recipe(P + 'machines', prune(m, props), props, kit_lighting(lights(), AMBIENT, {'tolerance': 24, 'max_added': 120}), 1900))


def rails_recipe(cells):
    tex = {'image': f'art/{P}rail.png', 'bits': 4, 'scale': [1.0, 1.0]}
    m = {'rail_x': {'color': '#d0aa30', 'double_sided': True, 'texture': dict(tex, projection='planar', axis='z')},
         'rail_z': {'color': '#d0aa30', 'double_sided': True, 'texture': dict(tex, projection='planar', axis='x')}}
    return recipe(P + 'rails', m, rail_nodes(cells), kit_lighting(lights(), AMBIENT, {'tolerance': 24, 'max_added': 0}), 400)


def wwater_recipe():
    """Agent W (NOTES_W.md): the glints on the sumps and the channel. Lit by lights of their own:
    one where each lamp's reflection lies on the water as the camera sees it (the streaks the
    paint keeps smooth), and a faint green fill over the sumps."""
    ov = wateranim.Overlay(P + 'wwater')
    ov.material('glint', 'w_ripple')
    for (x0, z0, x1, z1) in WATER.values():
        ov.floor('glint', SINK + 0.03, x0 + 0.01, x1 - 0.01, z0 + 0.01, z1 - 0.01,
                 nx=max(1, round((x1 - x0) / 3.0)), nz=max(1, round((z1 - z0) / 2.4)))
    for k, ((lx, ly, lz), col, strength) in enumerate([(L, '#ffd696', 1.0) for L in CEIL_LAMPS] +
                                                      [(L, '#ffecc8', 0.8) for L in CLAMP_LAMPS]):
        zr = lz - (ly - SINK) / math.tan(math.radians(60))
        ov.light((lx, SINK + 0.45, zr), col, round(2.6 * strength, 2), 1.3, id=f'reflection_{k}')
    for k, x in enumerate((-7.1, -2.1, 2.9, 7.5)):
        ov.light((x, 1.6, -0.4), '#3a8a80', 1.6, 3.4, id=f'fill_{k}')
    return ov.recipe(ART, refine={'tolerance': 24, 'max_added': 40})


def main():
    art8, art4 = {}, {}
    L = lights()
    blk = blockers()
    for name, span in FLOOR_SPANS.items():
        w, h = SIZES[name]
        x0, x1, z0, z1 = span
        art8[P + name] = paint_floor(R, x0, x1, z0, z1, walk_base, L, AMBIENT, blk, walk_extra, w=w, h=h, occlusion=0.3)
    for name, span in WATER_SPANS.items():
        art8[P + name] = paint_water(span, SIZES[name])
    for name, a, b in R.back_chunks(9.5):
        art8[P + name] = paint_wall(a, b, 0.0, 2.4, R.Z1, wall_base, L, AMBIENT)
    art4.update({P + 'section': paint_section(), P + 'rail': paint_rail(),
                 P + 'gauge': paint_gauge(), P + 'motor': paint_motor()})
    save_art(art8, art4, ART)
    nodes, cells = floor_nodes()
    recs = [*room_recipe(nodes, cells), rails_recipe(cells), wwater_recipe(),        # agent W: wwater
            collision_recipe(G.ROOM, P + 'room_col')]
    for rec in recs:
        write_json(OUT / f'{rec["name"]}.asset.json', rec)
    print(f'texture bytes (estimate): {vram(art8, art4):,}')
    if '--no-placements' not in sys.argv:
        write_json(HERE / 'aq_plant.placements.json',
                   placements_file('aq_plant', [(P + 'room', P + 'room', P + 'room_col'), (P + 'machines', P + 'machines', 'none'),
                                                 (P + 'rails', P + 'rails', 'none'),
                                                 (P + 'wwater', P + 'wwater', 'none')]))      # agent W


if __name__ == '__main__':
    main()
