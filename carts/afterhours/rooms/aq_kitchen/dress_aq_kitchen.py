#!/usr/bin/env python3
"""The aquarium, room 6: the fish kitchen, dressed. Writes the room's Asset Kit recipes into
dressed/, their textures into dressed/art/ and aq_kitchen.placements.json beside this script
(--no-placements leaves the placements alone).

    python3 carts/afterhours/rooms/aq_kitchen/dress_aq_kitchen.py

Where the keepers make the animals' food: the brightest room in the building, cold steel and
white tile under fluorescent tubes, a relief after the dark.

- the prep island: two stainless tables, capelin laid out in rows on white boards, squid on a
  tray, a block of krill thawing, a scale, bowls, knives; boxes of fish on the shelves under them;
- the sinks along the back wall, three basins, a tube light over them, a knife rack, the
  keepers' blue rubber aprons on hooks;
- the walk-in freezer in the west corner, cut by the section so that its insulated walls and its
  frosted inside show, its fish in boxes on the shelves; its doorway open behind a strip
  curtain, frost spilling out over the floor where the thief hides (the play file's hiding place);
- the live feed tank: shrimp in blue-lit water, bubbling;
- the steel rack on the east wall: styrofoam boxes, cartons with fish pictograms;
- the floor: pale non-slip tiles, a drain, wet rings where the buckets of fish stand (the buckets
  are the runtime's fragile things: the floor under them is left plain);
- the feeding chart on the back wall (pictograms of the animals, ticks), a clock;
- beyond the west door the service stair down to the plant, beyond the back door the way through
  to the dark tank tops.

The floor plan is the level lead's (PLAN.md, make_aq_kitchen.py), imported for its numbers. Needs
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
sys.path.insert(0, str(HERE.parents[1] / 'water'))   # agent W: the moving water (NOTES_W.md)
import wateranim  # noqa: E402
import make_aq_kitchen as G  # noqa: E402  (the lead's plan: imported for its numbers only)
from aqdress import (CUT_H, Mesh, Room, at, beyond_flight, blob, box, collision_recipe, grid, kit_lighting,  # noqa: E402
                     mat_tex, paint_floor, paint_rgb, paint_section, paint_wall, placements_file, prune, r, rect,
                     recipe, save_art, smoothstep, tile_grid, to_image, vram, wet, write_json)

OUT = HERE / 'dressed'
ART = OUT / 'art'
P = 'ak_'
R = Room(G.ROOM, P)
PROPS = {p[0]: p[2] for p in G.ROOM['props']}
ISLAND = PROPS['island']
SINKS = PROPS['sinks']
FREEZER = PROPS['freezer']
TANK = PROPS['feed_tank']
SHELVES = PROPS['shelves']
HIDE = G.ROOM['hides'][0][1]
BUCKETS = [(x, z, rad) for _, (x, z), rad, _ in G.ROOM['fragile']]
TOP = 0.9               # the tables' and the sinks' tops
TABLES = [(ISLAND[0], ISLAND[1], -0.55, ISLAND[3]), (-0.45, ISLAND[1], ISLAND[2], ISLAND[3])]
FW = 0.1                # the freezer's walls
AMBIENT = 0.44
TUBES = [(-4.0, -2.0), (0.0, -2.2), (3.6, -2.0), (-3.6, 1.6), (0.4, 1.6), (4.2, 1.2), (-4.0, 3.4)]


def lights():
    out = [{'id': f'tube_{k}', 'at': [x, 2.6, z], 'color': '#eef6f4', 'intensity': 1.1, 'range': 4.8, 'line': 1.2,
            'shadows': True} for k, (x, z) in enumerate(TUBES)]
    out += [{'id': 'freezer', 'at': [-5.6, 0.9, 1.8], 'color': '#cfe6ff', 'intensity': 1.2, 'range': 1.8},
            {'id': 'feed', 'at': [4.7, 0.95, 1.5], 'color': '#90d0ff', 'intensity': 0.9, 'range': 1.4, 'paint': True},
            {'id': 'stair', 'at': [R.XO0 - 0.8, 1.6, -2.6], 'color': '#ffe0b8', 'intensity': 1.0, 'range': 2.6},
            {'id': 'tops', 'at': [4.4, 1.6, R.ZO1 + 1.0], 'color': '#5a78c0', 'intensity': 0.8, 'range': 2.4}]
    return out


def blockers():
    x0, z0, x1, z1 = FREEZER
    out = [(x0, 0, z0, x1, 2.6, z1)]
    for (a, b, c, d) in TABLES:
        out.append((a + 0.05, TOP - 0.05, b + 0.05, c - 0.05, TOP, d - 0.05))
    out.append((SINKS[0], 0, SINKS[1], SINKS[2], TOP, SINKS[3]))
    out.append((TANK[0], 0, TANK[1], TANK[2], 1.2, TANK[3]))
    out.append((SHELVES[0], 0, SHELVES[1], SHELVES[2], 2.0, SHELVES[3]))
    return out


# ---- painting

def floor_base(x, z):
    """Pale grey-green non-slip tiles, a stainless drain, wet patches, the frost at the freezer's
    doorway, wet rings where the buckets stand."""
    base = tile_grid(x, z, 0.3, (184, 196, 194), grout=0.93, var=0.01, seed=int(abs(x[0, 0]) * 10) + 1, ox=-6.5, oz=-4.0,
                     noise_amp=7)
    # the drain: a stainless grate across the room between the island and the sinks
    d = (np.abs(z - 3.12) < 0.08) & (x > -6.3) & (x < -1.7)
    base = paint_rgb(base, d, (70, 76, 80))
    base = paint_rgb(base, d & (np.abs(z - 3.12) < 0.06) & ((x * 25) % 1 < 0.45), (196, 204, 210))
    for (cx, cz) in ((1.2, 1.9), (-2.0, -2.9)):
        g = rect(x, z, cx - 0.18, cz - 0.18, cx + 0.18, cz + 0.18) > 0
        base = paint_rgb(base, g, (70, 76, 80))
        base = paint_rgb(base, g & (rect(x, z, cx - 0.15, cz - 0.15, cx + 0.15, cz + 0.15) > 0) & ((x * 25) % 1 < 0.45), (196, 204, 210))
    # wet: under the sinks, round the island, a trail to the freezer
    for k, (cx, cz, rx, rz) in enumerate(((-4.0, 2.9, 1.6, 0.35), (-1.2, -1.6, 0.9, 0.35), (1.4, 0.55, 0.8, 0.3),
                                         (-3.9, 0.6, 0.5, 0.6), (4.7, 0.6, 0.6, 0.25))):
        base *= (1 - 0.12 * wet(x, z, cx, cz, rx, rz, k))[..., None]
    # the buckets' wet rings (the buckets themselves are the runtime's)
    for (bx, bz, rad) in BUCKETS:
        dd = np.hypot(x - bx, z - bz)
        base *= (1 - 0.22 * np.exp(-((dd - rad * 0.95) / 0.06) ** 2))[..., None]
        base *= (1 - 0.1 * (dd < rad))[..., None]
    # the frost spilling out of the freezer's doorway over its hiding place
    hx0, hz0, hx1, hz1 = HIDE
    frost = rect(x, z, hx0, hz0 + 0.02, hx1 - 0.02, hz1 - 0.02, soft=0.03) * (1 - 0.6 * smoothstep(hx0, hx1, x))
    rng = np.random.default_rng(int(abs(x[0, 0]) * 10) + 41)
    frost = frost * (0.75 + 0.25 * rng.random(x.shape))
    base = base * (1 - frost[..., None]) + frost[..., None] * np.array([232, 244, 252])
    # a rubber mat in the doorway's mouth
    base = paint_rgb(base, rect(x, z, hx0 + 0.02, hz0 + 0.1, hx0 + 0.3, hz1 - 0.1) > 0, (40, 44, 48))
    return base


def floor_extra(x, z, rgb):
    # the feed tank's blue through its glass, close round its stand
    tx0, tz0, tx1, tz1 = TANK
    d = np.maximum(np.maximum(tx0 - x, x - tx1), np.maximum(tz0 - z, z - tz1))
    rgb = rgb + (np.exp(-np.clip(d, 0, None) / 0.25) * (d > 0) * 0.35)[..., None] * np.array([60, 140, 200])
    # the freezer's cold breath at its doorway
    hx0, hz0, hx1, hz1 = HIDE
    rgb = rgb + (blob(x, z, hx0 + 0.1, (hz0 + hz1) / 2, 0.5, 0.6) * 0.18)[..., None] * np.array([120, 180, 255])
    return rgb


WB = (0.3, 2.9, 1.05, 1.85)        # the feeding chart on the back wall: x0, x1, y0, y1


def wall_base(x, y):
    """White tiles to 1.6 m, pale paint over, the knife rack over the sinks, the feeding chart,
    a clock, the hand-wash pictogram."""
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array([226, 230, 230])
    tiles = y < 1.6
    grout = (np.abs(((x + 6.75) / 0.15) % 1 - 0.5) > 0.42) | (np.abs((y / 0.15) % 1 - 0.5) > 0.42)
    base = np.where((tiles & grout)[..., None], base * 0.86, base)
    base = np.where((~tiles)[..., None], np.array([214, 216, 206]), base)
    base = np.where((np.abs(y - 1.6) < 0.015)[..., None], np.array([150, 160, 160]), base)
    base = np.where((y < 0.1)[..., None], np.array([120, 130, 130]), base)
    # the knife rack: a magnetic bar, knives hanging from it
    kx0, kx1, ky = -5.6, -4.2, 1.45
    base = paint_rgb(base, rect(x, y, kx0, ky - 0.02, kx1, ky + 0.02) > 0, (40, 40, 44))
    for k in range(7):
        cx = kx0 + 0.12 + k * 0.19
        blade = rect(x, y, cx - 0.018, ky - 0.24 + 0.02 * (k % 3), cx + 0.018, ky - 0.02) > 0
        base = paint_rgb(base, blade, (200, 206, 214))
        base = paint_rgb(base, rect(x, y, cx - 0.014, ky + 0.01, cx + 0.014, ky + 0.1) > 0, (30, 30, 34))
    # the feeding chart: a white board, rows of animals and ticks
    x0, x1, y0, y1 = WB
    base = paint_rgb(base, rect(x, y, x0 - 0.04, y0 - 0.04, x1 + 0.04, y1 + 0.04) > 0, (150, 156, 160))
    base = paint_rgb(base, rect(x, y, x0, y0, x1, y1) > 0, (244, 244, 240))
    animals = [(40, 90, 170), (60, 140, 90), (200, 120, 60), (60, 70, 90)]
    for row in range(4):
        cy = y1 - 0.12 - row * 0.19
        cx = x0 + 0.16
        dx, dy = x - cx, y - cy
        base = paint_rgb(base, np.hypot(dx / 0.09, dy / 0.05) < 1, animals[row])
        base = paint_rgb(base, (dx < -0.07) & (dx > -0.13) & (np.abs(dy) < (-0.07 - dx) * 0.8), animals[row])
        base = paint_rgb(base, (np.abs(dy - 0.095) < 0.005) & (x > x0 + 0.03) & (x < x1 - 0.03), (180, 190, 200))
        for k in range(7):
            tx = x0 + 0.45 + k * 0.3
            mark = (np.abs(x - tx) < 0.04) & (np.abs(y - cy) < 0.04)
            if (row * 3 + k) % 5 != 4:
                base = paint_rgb(base, mark & (np.abs((x - tx) + (y - cy) * 0.5) < 0.015), (30, 60, 150))
            else:
                base = paint_rgb(base, mark & (np.abs(np.hypot(x - tx, y - cy) - 0.03) < 0.008), (200, 40, 40))
    # the clock
    cx, cy = 3.5, 2.0
    d = np.hypot(x - cx, y - cy)
    base = paint_rgb(base, d < 0.17, (40, 44, 50))
    base = paint_rgb(base, d < 0.15, (246, 246, 240))
    base = paint_rgb(base, (np.abs(x - cx) < 0.01) & (y > cy - 0.1) & (y < cy), (30, 30, 30))
    base = paint_rgb(base, (np.abs(y - cy) < 0.01) & (x > cx) & (x < cx + 0.08), (30, 30, 30))
    # hand-wash pictogram by the sinks
    px, py = -1.9, 1.35
    base = paint_rgb(base, rect(x, y, px - 0.15, py - 0.15, px + 0.15, py + 0.15) > 0, (40, 110, 200))
    base = paint_rgb(base, rect(x, y, px - 0.12, py - 0.12, px + 0.12, py + 0.12) > 0, (240, 244, 248))
    base = paint_rgb(base, (np.hypot(x - px, y - (py + 0.02)) < 0.07) & (y > py - 0.02), (40, 110, 200))
    base = paint_rgb(base, rect(x, y, px - 0.02, py - 0.1, px + 0.02, py - 0.04) > 0, (40, 110, 200))
    # the green emergency sign over the back door
    ex, ey = 4.4, 2.25
    base = paint_rgb(base, rect(x, y, ex - 0.2, ey - 0.07, ex + 0.2, ey + 0.07) > 0, (40, 180, 100))
    base = paint_rgb(base, rect(x, y, ex + 0.05, ey - 0.05, ex + 0.15, ey + 0.05) > 0, (236, 255, 240))
    return base


def wall_extra(x, y, rgb):
    # the tube light over the sinks washes the tiles under it
    rgb = rgb + (np.exp(-((x + 4.0) / 1.6) ** 2 - ((y - 2.0) / 0.5) ** 2) * 0.35)[..., None] * np.array([230, 245, 245])
    return rgb


def paint_table_top(k, w=128, h=72):
    """A prep table's top from above, in its own light: brushed steel, white boards, capelin in
    rows, squid on a tray (table 0); the krill block thawing, a mackerel, knives (table 1)."""
    x0, z0, x1, z1 = TABLES[k]
    x, z = grid(x0, x1, z0, z1, w, h)
    rng = np.random.default_rng(k + 5)
    base = np.zeros((h, w, 3)) + np.array([206, 212, 216]) + (rng.random((h, w)) - 0.5)[..., None] * 10
    base *= (1 + 0.04 * np.sin(x * 40))[..., None]                           # brushed along x
    base = np.where((np.minimum.reduce([x - x0, x1 - x, z - z0, z1 - z]) < 0.03)[..., None], base * 0.8, base)

    def board(bx0, bz0, bx1, bz1, col=(240, 242, 240)):
        nonlocal base
        base = paint_rgb(base, rect(x, z, bx0, bz0, bx1, bz1) > 0, col)

    def fishes(bx0, bz0, bx1, bz1, n_rows, n_cols, length, col, belly):
        nonlocal base
        for i in range(n_rows):
            for j in range(n_cols):
                cx = bx0 + (j + 0.5) * (bx1 - bx0) / n_cols
                cz = bz0 + (i + 0.5) * (bz1 - bz0) / n_rows
                dx, dz = x - cx, z - cz
                body = np.hypot(dx / (length / 2), dz / (length / 6)) < 1
                tail = (dx > length / 2 - 0.01) & (dx < length / 2 + 0.03) & (np.abs(dz) < (dx - length / 2 + 0.01) * 0.9 + 0.003)
                base = paint_rgb(base, body | tail, col)
                base = paint_rgb(base, body & (dz < -length / 40), belly)
                base = paint_rgb(base, (np.hypot(dx + length * 0.38, dz) < 0.008), (20, 20, 30))
    if k == 0:
        # a blue tray heaped with capelin, silver
        base = paint_rgb(base, rect(x, z, x0 + 0.15, z0 + 0.3, x0 + 0.8, z1 - 0.3) > 0, (50, 100, 180))
        heap = rect(x, z, x0 + 0.2, z0 + 0.35, x0 + 0.75, z1 - 0.35) > 0
        silver = 150 + 90 * (np.sin(x * 70 + np.sin(z * 50) * 2) * 0.5 + 0.5)
        base = np.where(heap[..., None], np.stack([silver * 0.85, silver * 0.92, silver], -1), base)
        # a white board with two mackerel
        board(x0 + 0.9, z0 + 0.2, x0 + 1.25, z1 - 0.2)
        fishes(x0 + 0.92, z0 + 0.3, x0 + 1.23, z1 - 0.3, 2, 1, 0.3, (60, 110, 120), (220, 228, 230))
        board(x0 + 1.35, z0 + 0.35, x0 + 2.2, z1 - 0.25, (110, 160, 120))      # a green board
        # squid on a tray
        base = paint_rgb(base, rect(x, z, x0 + 1.45, z0 + 0.45, x0 + 2.1, z1 - 0.35) > 0, (176, 180, 186))
        for j in range(4):
            cx = x0 + 1.55 + j * 0.15
            sq = (np.abs(x - cx) < 0.04) & (z > z0 + 0.52) & (z < z1 - 0.42)
            base = paint_rgb(base, sq, (236, 214, 220))
            base = paint_rgb(base, sq & (z > z1 - 0.5), (200, 150, 170))
    else:
        # the krill block thawing in a tray, pink
        base = paint_rgb(base, rect(x, z, x0 + 0.15, z0 + 0.3, x0 + 0.8, z1 - 0.3) > 0, (176, 180, 186))
        kb = rect(x, z, x0 + 0.22, z0 + 0.37, x0 + 0.73, z1 - 0.37) > 0
        base = paint_rgb(base, kb, (214, 120, 120))
        base = paint_rgb(base, kb & (rng.random((h, w)) < 0.35), (240, 170, 160))
        # a white board with a mackerel and a knife
        board(x0 + 1.0, z0 + 0.25, x0 + 1.9, z1 - 0.25)
        fishes(x0 + 1.15, z0 + 0.45, x0 + 1.75, z1 - 0.45, 1, 1, 0.42, (60, 110, 120), (220, 228, 230))
        mk = (np.abs(z - (z0 + 0.4)) < 0.012) & (x > x0 + 1.2) & (x < x0 + 1.55)
        base = paint_rgb(base, mk, (230, 234, 240))
        base = paint_rgb(base, (np.abs(z - (z0 + 0.4)) < 0.016) & (x > x0 + 1.55) & (x < x0 + 1.7), (30, 30, 34))
        # a bowl of chopped fish
        dd = np.hypot(x - (x1 - 0.25), z - (z1 - 0.35))
        base = paint_rgb(base, dd < 0.17, (190, 196, 202))
        base = paint_rgb(base, dd < 0.13, (170, 110, 110))
    # scales and wet smears
    base *= (1 - 0.1 * (rng.random((h, w)) < 0.05))[..., None]
    shade = 1.15 + 0.1 * np.sin(x * 0.7)
    return to_image(base * shade[..., None], dither=3.0)


def paint_sink_top(w=200, h=28):
    """The sink counter from above: three basins of water, drainboards ribbed, taps' shadows."""
    x0, z0, x1, z1 = SINKS
    x, z = grid(x0, x1, z0, z1, w, h)
    base = np.zeros((h, w, 3)) + np.array([206, 212, 216])
    base *= (1 + 0.04 * np.sin(x * 40))[..., None]
    for cx in (-5.6, -4.3, -3.0):
        bas = rect(x, z, cx - 0.5, z0 + 0.1, cx + 0.5, z1 - 0.15) > 0
        base = paint_rgb(base, bas, (120, 128, 134))
        inner = rect(x, z, cx - 0.44, z0 + 0.15, cx + 0.44, z1 - 0.2) > 0
        base = paint_rgb(base, inner, (90, 130, 150))
        base = paint_rgb(base, inner & ((np.sin(x * 30 + z * 12) > 0.85)), (190, 220, 230))
        base = paint_rgb(base, np.hypot(x - cx, z - (z1 - 0.07)) < 0.04, (60, 64, 70))
    rib = (x > -2.4) & (x < x1 - 0.1) & ((z * 30) % 1 < 0.3) & (z > z0 + 0.1) & (z < z1 - 0.12)
    base = paint_rgb(base, rib, (176, 182, 188))
    return to_image(base * 1.1, dither=3.0)


def paint_freezer_floor(w=48, h=60):
    x0, z0, x1, z1 = FREEZER
    x, z = grid(x0, x1, z0, z1, w, h)
    rng = np.random.default_rng(9)
    base = np.zeros((h, w, 3)) + np.array([176, 200, 214]) + (rng.random((h, w)) - 0.5)[..., None] * 20
    base = paint_rgb(base, ((x * 12) % 1 < 0.15), (150, 172, 188))
    base = paint_rgb(base, rng.random((h, w)) < 0.06, (236, 246, 252))
    return to_image(base, dither=0)


def paint_carton(seed, w=16, h=12):
    """A carton's side: brown, a fish pictogram in a box, a coloured band."""
    img = Image.new('RGB', (w, h), [(176, 136, 90), (190, 150, 100), (166, 126, 84)][seed % 3])
    d = ImageDraw.Draw(img)
    col = [(40, 80, 160), (190, 50, 40), (40, 120, 70)][seed % 3]
    d.rectangle([0, 0, w - 1, 1], fill=col)
    d.ellipse([4, 4, 11, 8], fill=col)
    d.polygon([(11, 6), (14, 4), (14, 8)], fill=col)
    return img


def paint_styro(w=16, h=8):
    img = Image.new('RGB', (w, h), (238, 240, 236))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, 1], fill=(70, 110, 190))
    d.rectangle([3, 3, 12, 5], fill=(200, 60, 60))
    return img


def paint_strips(n=16):
    """The freezer's strip curtain: overlapping clear strips, gaps between."""
    img = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for k in range(0, n, 4):
        d.rectangle([k, 0, k + 2, n - 1], fill=(210, 230, 240, 255))
        d.line([(k, 0), (k, n - 1)], fill=(240, 250, 255, 255))
    return img


def paint_feed_bottom(w=32, h=24):
    """The feed tank's bottom: bare, blue-lit, swarming with shrimp (pink-orange specks)."""
    rng = np.random.default_rng(13)
    rgb = np.zeros((h, w, 3)) + np.array([30, 90, 140])
    rgb += (rng.random((h, w)) - 0.5)[..., None] * 16
    specks = rng.random((h, w)) < 0.06
    rgb = np.where(specks[..., None], np.array([230, 140, 110]), rgb)
    return to_image(rgb, dither=0)


def paint_cabinet_front(w=32, h=12):
    """The cupboards under the sinks: stainless doors, handles."""
    img = Image.new('RGB', (w, h), (190, 196, 200))
    d = ImageDraw.Draw(img)
    for k in range(4):
        d.rectangle([k * 8, 0, k * 8 + 7, h - 1], outline=(130, 136, 142))
        d.line([(k * 8 + 2, 2), (k * 8 + 5, 2)], fill=(80, 84, 90))
    return img


# ---- the recipes

def island_nodes():
    n = []
    for k, (x0, z0, x1, z1) in enumerate(TABLES):
        n.append(box(f'table_{k}', (x0, TOP - 0.04, z0), (x1, TOP, z1), 'steel_edge', faces={'top': f'table_top_{k}'}))
        n.append(box(f'undershelf_{k}', (x0 + 0.05, 0.16, z0 + 0.05), (x1 - 0.05, 0.2, z1 - 0.05), 'steel'))
        for j, (lx, lz) in enumerate(((x0 + 0.04, z0 + 0.04), (x1 - 0.04, z0 + 0.04), (x0 + 0.04, z1 - 0.04), (x1 - 0.04, z1 - 0.04))):
            n.append(box(f'leg_{k}{j}', (lx - 0.025, -0.02, lz - 0.025), (lx + 0.025, TOP - 0.039, lz + 0.025), 'steel',
                         open=['bottom', 'top']))
        # boxes of fish on the shelf under the table
        for j in range(3):
            bx = x0 + 0.15 + j * (x1 - x0 - 0.3) / 3
            n.append(box(f'under_box_{k}{j}', (bx, 0.199, z0 + 0.15), (bx + (x1 - x0 - 0.3) / 3 - 0.08, 0.5, z1 - 0.2),
                         'styro', open=['bottom'], faces={'back': 'styro_side' if (j + k) % 2 else f'carton_{j}',
                                                          'top': 'lid_blue' if (j + k) % 2 else 'carton_top'}))
    # on the tables: a scale, bowls, a stack of trays
    x0, z0, x1, z1 = TABLES[1]
    n.append(box('scale', (x1 - 0.32, TOP - 0.01, z0 + 0.08), (x1 - 0.07, TOP + 0.07, z0 + 0.3), 'scale',
                 faces={'top': 'scale_top', 'back': 'scale_lcd'}))
    n.append(at({'id': 'bowl_0', 'op': 'cylinder', 'radius': 0.13, 'height': 0.08, 'segments': 8, 'material': 'bowl',
                 'faces': {'top': 'bowl_in'}}, translate=[TABLES[0][2] - 0.2, TOP + 0.035, TABLES[0][1] + 0.2]))
    n.append(box('trays', (TABLES[0][0] + 1.3, TOP - 0.01, TABLES[0][1] + 0.05), (TABLES[0][0] + 1.75, TOP + 0.08, TABLES[0][1] + 0.3),
                 'tray', open=['bottom']))
    return n


def sink_nodes():
    x0, z0, x1, z1 = SINKS
    n = [box('sinks', (x0, -0.02, z0), (x1, TOP, z1), 'steel_edge', open=['bottom', 'left', 'front'],
             faces={'top': 'sink_top', 'back': 'sink_front'})]
    for k, cx in enumerate((-5.6, -4.3, -3.0)):
        n.append(box(f'tap_{k}', (cx - 0.02, TOP - 0.01, z1 - 0.12), (cx + 0.02, 0.99, z1 - 0.08), 'chrome'))
        n.append(box(f'spout_{k}', (cx - 0.015, 0.95, z1 - 0.3), (cx + 0.015, 0.985, z1 - 0.11), 'chrome'))
    # the tube light over them, on the back wall
    n.append(box('sink_light', (-5.6, 1.95, R.Z1 - 0.1), (-2.4, 2.05, R.Z1 + 0.01), 'fitting', open=['front'],
                 faces={'bottom': 'tube', 'back': 'tube'}))
    return n


def apron_nodes():
    n = []
    for k, ax in enumerate((-0.9, -0.35, 0.2)):
        n.append(box(f'apron_{k}', (ax - 0.22, 0.95 + 0.04 * k, R.Z1 - 0.04), (ax + 0.22, 1.75, R.Z1 + 0.01), 'apron',
                     open=['front']))
        n.append(box(f'hook_{k}', (ax - 0.03, 1.74, R.Z1 - 0.07), (ax + 0.03, 1.8, R.Z1 + 0.01), 'chrome', open=['front']))
    return n


def freezer_nodes():
    x0, z0, x1, z1 = FREEZER
    hz0, hz1 = HIDE[1], HIDE[3]
    n = []
    walls = [('fz_s', (x0, z0, x1, z0 + FW), ['left']),
             ('fz_n', (x0, z1 - FW, x1, z1), ['left']),
             ('fz_e0', (x1 - FW, z0 + FW, x1, hz0), ['back']),
             ('fz_e1', (x1 - FW, hz1, x1, z1 - FW), ['front'])]
    for name, (a, b, c, d), op in walls:
        n.append(box(name, (a, -0.02, b), (c, CUT_H, d), 'fz_panel', open=['bottom'] + op,
                     faces={'top': 'fz_cut'}))
    # inside: the frosted floor, steel shelves along the west and north walls, boxes of frozen fish
    n.append(box('fz_floor', (x0 + 0.01, -0.03, z0 + FW), (x1 - FW, 0.03, z1 - FW), 'fz_floor',
                 open=['bottom', 'left', 'right', 'back', 'front']))
    for j, y in enumerate((0.3, 0.7)):
        n.append(box(f'fz_shelf_w{j}', (x0 + 0.01, y - 0.02, z0 + FW + 0.05), (x0 + 0.5, y, z1 - FW - 0.02), 'steel', open=['left']))
    rng = np.random.default_rng(4)
    for j, y in enumerate((0.025, 0.3, 0.7)):
        for i in range(4):
            bz = z0 + FW + 0.1 + i * 0.52
            ht = [0.22, 0.26, 0.2][j]
            n.append(box(f'fz_box_{j}{i}', (x0 + 0.05, y + 0.005, bz), (x0 + 0.46, min(y + ht, 0.99), bz + 0.44),
                         'frozen' if (i + j) % 2 else 'styro', open=['bottom', 'left'],
                         faces={'top': 'frost_top' if (i + j) % 2 else 'lid_blue'}))
    # fish blocks in a stack on the floor by the north wall
    for i in range(3):
        n.append(box(f'fz_block_{i}', (x0 + 0.65 + i * 0.36, 0.025, z1 - FW - 0.42), (x0 + 0.97 + i * 0.36, 0.18 + 0.12 * (i % 2), z1 - FW - 0.06),
                     'frozen', open=['bottom'], faces={'top': 'frost_top'}))
    # the doorway's thick frame and its strip curtain
    for j, (a, b) in enumerate(((hz0 - 0.06, hz0 + 0.02), (hz1 - 0.02, hz1 + 0.06))):
        n.append(box(f'fz_jamb_{j}', (x1 - FW - 0.02, -0.02, a), (x1 + 0.04, CUT_H - 0.004, b), 'fz_frame', open=['bottom'],
                     faces={'top': 'fz_cut'}))
    return n


def strips_recipe():
    x1 = FREEZER[2]
    hz0, hz1 = HIDE[1], HIDE[3]
    m = Mesh()
    m.quad_x(x1 - 0.05, 0.0, 0.99, hz0 + 0.02, hz1 - 0.02, 1, 'strips')
    mats = {'strips': {'color': '#b8d8e8', 'blend': 'half', 'double_sided': True,
                       'texture': {'image': f'art/{P}strips.png', 'bits': 4, 'projection': 'planar', 'axis': 'x', 'scale': [0.25, 1.0]}},
            'glass': {'color': '#4a90c0', 'blend': 'quarter', 'double_sided': True},
            'surface': {'color': '#3a90c8', 'blend': 'quarter',          # agent W: the feed tank's ripple moves
                        'texture': wateranim.texture(wateranim.key('w_ripple', '#c8ecff', base='#3a90c8'))},
            'drip': {'color': '#9ad0e0', 'blend': 'add',                  # agent W: the dripping tap's rings
                     'texture': wateranim.texture(wateranim.key('w_drip', '#9ad0e0'), scale=0.5)}}
    n = [m.node('strips', 'strips')]
    # the feed tank's glass and water
    tx0, tz0, tx1, tz1 = TANK
    n.append(box('feed_glass', (tx0 + 0.04, 0.481, tz0 + 0.04), (tx1 - 0.04, 0.97, tz1 - 0.04), 'glass', open=['top', 'bottom']))
    n.append(box('feed_water', (tx0 + 0.05, 0.89, tz0 + 0.05), (tx1 - 0.05, 0.9, tz1 - 0.05), 'surface',
                 open=['bottom', 'left', 'right', 'back', 'front']))
    # agent W: rings spreading in the west basin under the dripping tap (F's amb_kitchen drips)
    sx0, sz0, sx1, sz1 = SINKS
    dm = Mesh()
    dm.quad_y(TOP + 0.02, -5.6 - 0.43, -5.6 + 0.43, sz0 + 0.16, sz1 - 0.21, 1, 'drip')
    n.append(dm.node('drip', 'drip'))
    return wateranim.finish(recipe(P + 'glass', mats, n, {'bake': False}, 100), ART)


def tank_nodes():
    tx0, tz0, tx1, tz1 = TANK
    n = [box('feed_stand', (tx0, -0.02, tz0), (tx1, 0.44, tz1), 'cabinet', open=['bottom'], faces={'top': 'steel'}),
         box('feed_rim', (tx0 + 0.01, 0.439, tz0 + 0.01), (tx1 - 0.01, 0.49, tz1 - 0.01), 'rim', open=['bottom'],
             faces={'top': 'feed_bottom'}),
         box('feed_trim', (tx0 + 0.01, 0.94, tz0 + 0.01), (tx1 - 0.01, 0.975, tz1 - 0.01), 'rim', open=['bottom', 'top']),
         at({'id': 'feed_airstone', 'op': 'cylinder', 'radius': 0.03, 'height': 0.04, 'segments': 4, 'material': 'bubble'},
            translate=[tx1 - 0.25, 0.505, tz1 - 0.25]),
         box('feed_bubbles', (tx1 - 0.265, 0.53, tz1 - 0.265), (tx1 - 0.235, 0.88, tz1 - 0.235), 'bubble', open=['bottom', 'top']),
         # a net and a scoop hung on the stand
         box('feed_lamp', (tx0 + 0.3, 0.96, tz1 - 0.2), (tx1 - 0.3, 0.995, tz1 - 0.06), 'fitting', faces={'bottom': 'tank_light'})]
    return n


def shelf_nodes():
    x0, z0, x1, z1 = SHELVES
    n = []
    for j, (px, pz) in enumerate(((x0 + 0.03, z0 + 0.03), (x0 + 0.03, z1 - 0.03), (x0 + 0.03, (z0 + z1) / 2))):
        n.append(box(f'post_{j}', (px - 0.02, -0.02, pz - 0.02), (px + 0.02, CUT_H, pz + 0.02), 'steel', open=['bottom'],
                     faces={'top': 'cut'}))
    for j, y in enumerate((0.12, 0.52)):
        n.append(box(f'rack_{j}', (x0 + 0.06, y - 0.03, z0 + 0.05), (x1, y, z1 - 0.05), 'wire', open=['right']))
    k = 0
    for j, y in enumerate((0.12, 0.52)):
        z = z0 + 0.06
        while z < z1 - 0.4:
            dz = [0.5, 0.42, 0.56, 0.46][k % 4]
            top = min(y + [0.3, 0.36, 0.42, 0.32][k % 4], 0.47 if j == 0 else 0.99)
            styro = k % 3 == 1
            n.append(box(f'stock_{k}', (x0 + 0.08, y - 0.005, z), (x1 - 0.04, top, z + dz - 0.04),
                         'styro' if styro else 'carton', open=['bottom', 'right'],
                         faces={'left': 'styro_side' if styro else f'carton_{k % 3}', 'top': 'lid_blue' if styro else 'carton_top'}))
            z += dz
            k += 1
    return n


def room_recipe():
    tiles = R.floor_tiles(2, 2)
    chunks = R.back_chunks(7.0)
    m = R.shell_materials()
    m['section'] = mat_tex(P + 'section', '#5a6274', bits=4)
    for name, *_ in tiles:
        m[name] = mat_tex(P + name, '#b0bab4')
    for name, *_ in chunks:
        m[name] = mat_tex(P + name, '#d0d4d2')
    m.update({
        'wall_in': {'color': '#a0a8aa'}, 'end': {'color': '#d4d8d6'}, 'reveal': {'color': '#c4c8c6'},
        'lintel': {'color': '#c0c4c2'}, 'door_glow': {'color': '#f0f6f8', 'class': 'emissive'},
        'threshold': {'color': '#9a9e9c', 'class': 'emissive'}, 'beyond_wall': {'color': '#2e3a5a', 'class': 'emissive'},
        'beyond': {'color': '#3a4868', 'class': 'emissive'}, 'riser': {'color': '#28324a', 'class': 'emissive'},
        'stair_wall': {'color': '#7a7468', 'class': 'emissive'}, 'stair_landing': {'color': '#a8a49a', 'class': 'emissive'},
        'steel': {'color': '#b4bcc2'}, 'steel_edge': {'color': '#a4acb2'}, 'chrome': {'color': '#d8dee4'},
        'wire': {'color': '#9aa2a8'}, 'scale': {'color': '#e0e2e0'}, 'scale_top': {'color': '#c8ccd0'},
        'scale_lcd': {'color': '#60c890', 'class': 'emissive'}, 'bowl': {'color': '#c8ccd0'}, 'bowl_in': {'color': '#a86a6a'},
        'tray': {'color': '#e8eaec'}, 'styro': {'color': '#eef0ec'}, 'lid_blue': {'color': '#4a78c8'},
        'carton': {'color': '#b08a5c'}, 'carton_top': {'color': '#c09a6a'},
        'styro_side': mat_tex(P + 'styro', '#e8eae6', bits=4, emissive=False),
        'sink_top': mat_tex(P + 'sink_top', '#b8c0c4'), 'sink_front': mat_tex(P + 'cupboards', '#b8bec2', bits=4, emissive=False),
        'fitting': {'color': '#c8ccd0'}, 'tube': {'color': '#f4fcff', 'class': 'emissive'},
        'apron': {'color': '#2a5aa8'},
        'fz_panel': {'color': '#e2e6ea'}, 'fz_cut': {'color': '#9aa4b4', 'class': 'emissive'},
        'fz_frame': {'color': '#c8ccd2'}, 'fz_floor': mat_tex(P + 'freezer_floor', '#b8d0e0', bits=4),
        'frozen': {'color': '#c0d8ea'}, 'frost_top': {'color': '#e4f0f8'},
        'cabinet': {'color': '#9aa2a8'}, 'rim': {'color': '#3a4048'}, 'feed_bottom': mat_tex(P + 'feed_bottom', '#3a7ab0', bits=4),
        'bubble': {'color': '#c8e8ff', 'class': 'emissive'}, 'tank_light': {'color': '#c8f0ff', 'class': 'emissive'},
    })
    for j in range(3):
        m[f'carton_{j}'] = mat_tex(f'{P}carton_{j}', '#b08a5c', bits=4, emissive=False)
    for k in range(2):
        m[f'table_top_{k}'] = mat_tex(f'{P}table_top_{k}', '#c8ccd0')
    n = R.floor_nodes(tiles) + R.wall_nodes(chunks)
    n += [beyond_flight(R, 'plant', -6, landing=0.45, threshold='stair_landing', side_wall='stair_wall',
                        fade=['stair_0', 'stair_1', 'stair_2', 'stair_3', 'stair_4', 'stair_5']),
          *R.beyond_nodes('tops', 1.0, steps=2, rise=0.18, run=0.3, material='beyond')]
    for k, c in enumerate(('#a09a8e', '#8a857a', '#747066', '#5e5a52', '#4a4740', '#36342e')):
        m[f'stair_{k}'] = {'color': c, 'class': 'emissive'}
    n += apron_nodes()
    props = island_nodes() + sink_nodes() + freezer_nodes() + tank_nodes() + shelf_nodes()
    # the shell (floor, walls, the ways on) and the furniture apart: the shell alone fits the kit's
    # stand-in cap (700 triangles)
    return (recipe(P + 'room', prune(m, n), n, kit_lighting(lights(), AMBIENT, {'tolerance': 24, 'max_added': 60}), 1000),
            recipe(P + 'props', prune(m, props), props, kit_lighting(lights(), AMBIENT, {'tolerance': 24, 'max_added': 120}), 1600))


def main():
    art8, art4 = {}, {}
    L = lights()
    blk = blockers()
    for name, x0, x1, z0, z1 in R.floor_tiles(2, 2):
        art8[P + name] = paint_floor(R, x0, x1, z0, z1, floor_base, L, AMBIENT, blk, floor_extra, occlusion=0.18)
    for name, a, b in R.back_chunks(7.0):
        art8[P + name] = paint_wall(a, b, 0.0, 2.4, R.Z1, wall_base, L, AMBIENT, wall_extra, w=int(min(255, 36 * (b - a))))
    for k in range(2):
        art8[f'{P}table_top_{k}'] = paint_table_top(k)
    art8[P + 'sink_top'] = paint_sink_top()
    art4.update({P + 'section': paint_section(R.XO0, R.XO1), P + 'styro': paint_styro(), P + 'strips': paint_strips(),
                 P + 'freezer_floor': paint_freezer_floor(), P + 'feed_bottom': paint_feed_bottom(),
                 P + 'cupboards': paint_cabinet_front()})
    for j in range(3):
        art4[f'{P}carton_{j}'] = paint_carton(j)
    save_art(art8, art4, ART)
    recs = [*room_recipe(), strips_recipe(), collision_recipe(G.ROOM, P + 'room_col')]
    for rec in recs:
        write_json(OUT / f'{rec["name"]}.asset.json', rec)
    print(f'texture bytes (estimate): {vram(art8, art4):,}')
    if '--no-placements' not in sys.argv:
        write_json(HERE / 'aq_kitchen.placements.json',
                   placements_file('aq_kitchen', [(P + 'room', P + 'room', P + 'room_col'), (P + 'props', P + 'props', 'none'),
                                                   (P + 'glass', P + 'glass', 'none')]))


if __name__ == '__main__':
    main()
