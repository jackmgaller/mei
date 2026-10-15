#!/usr/bin/env python3
"""Room 3, the passage under the street, dressed: writes its Asset Kit recipes, draws their
textures and writes the room's placements.

    python3 carts/afterhours/rooms/passage/dress_passage.py

Writes, beside itself:
  r3_passage.asset.json      the passage: the painted floor and back wall, the cut walls, the four
                             pillars, the vending machine, the shop signs, the payphone, the fire
                             hose cabinet, the bin, the lost umbrella; lit by ROOM_LIGHTS
  r3_passage_col.asset.json  its collision: the floor, the walls, the pillars and the machine
  passage.placements.json    the one placement (replaces the greybox's)
  art/*.png                  the floor and the back wall (painted as ROOM_LIGHTS light them), the
                             shutters' and signs' faces, the pillars, the machine's cut top

PLAN.md is the room's floor plan (the level lead's); this keeps everything it says must stay:
the walls, the pillars (0.8 m, opaque, cut at 1 m), the vending machine, the exit under the
camera. One list of point lights, ROOM_LIGHTS, drives both the Asset Kit's bake of the walls'
ends and the props (`lighting.lights`) and the painting of the floor and the back wall
(diorama.shade, the kit's formula, with soft shadows from the pillars and the machine). The
painted surfaces are emissive, so the kit spends no refinement triangles on them; refinement is
capped for the props. Everything named here is fictional. Needs Pillow and NumPy.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
from diorama import (CUT, WALL_H, Mesh, at, blob, box, collision_recipe, grid_floor, grid_wall_z, group,  # noqa: E402
                     hex_rgb, quantise_together, r, recipe, shade, smoothstep, soft_rect, to_array, write_json)

ART = HERE / 'art'
P = 'r3_'

# ---- the plan (PLAN.md): x right, z away from the camera, the floor y = 0, metres
X0, X1 = -11.0, 11.0
Z0, Z1 = -3.4, 3.4
T = 0.25
XO0, XO1, ZO0, ZO1 = X0 - T, X1 + T, Z0 - T, Z1 + T
SLAB = 0.4
PILLARS = [(-6.5, 0.6), (-2.5, -1.4), (1.5, 0.6), (5.5, -1.4)]
PILLAR_S = 0.8
SHOPS = [(-9.5, -5.5), (-4.5, -0.5), (0.5, 4.5)]
SHOP_H = 1.75             # the shutters' openings; the fascia above to the cut
RECESS = 0.2              # the shutters stand this far back in the wall
MACHINE = (-0.6, -3.4, 0.6, -2.9)
MACHINE_H = 0.95
ENTRY = (-2.6, -0.6)      # the west wall's door, z
EXIT = (-3.4, -1.6)       # the east wall's door, z
LINTEL = 2.1
PHONE_X = -5.0
HOSE_X = -10.25
POSTERS = [5.05 + 1.08 * k for k in range(5)]   # centres of the poster run, x
BIN = (-1.02, -3.38, -0.7, -3.1)
UMBRELLA = (-5.55, 1.55)
SHOWCASE = (-0.42, 0.42, 0.72, 1.5, Z1 - 0.36)   # the coffee shop's window of food models: x, y, its front z

# ---- the light: one list for the kit's bake and the painting. `tube` is the painting's (a
# fluorescent tube's half-length); the kit sees each light at its centre.
AMBIENT, DIFFUSE = 0.07, 0.04
DIRECTION = [0.0, 1.0, -0.25]
TUBE = '#cdf0e0'


def room_lights():
    tubes = [{'id': f'tube_{k}', 'at': [x, 2.35, -0.25], 'color': TUBE, 'intensity': i, 'range': 3.5,
              'shadows': True, 'radius': 0.3, 'tube': [0.55, 0, 0]}
             for k, (x, i) in enumerate(((-8.3, 2.0), (-2.9, 1.7), (2.6, 1.2), (8.0, 1.9)))]
    signs = [{'id': f'sign_{k}', 'at': [r((a + b) / 2), 1.95, Z1 - 0.8], 'color': c, 'intensity': 1.7,
              'range': 3.2, 'shadows': True, 'radius': 0.4}
             for k, ((a, b), c) in enumerate(zip(SHOPS, ('#e6eeff', '#ffac64', '#ff94c4')))]
    return tubes + signs + [
        {'id': 'night', 'at': [0.0, 7.0, -1.0], 'color': '#5c74b0', 'intensity': 0.42, 'range': 16.0},
        {'id': 'machine', 'at': [0.0, 0.8, -2.45], 'color': '#e2f2ff', 'intensity': 3.0, 'range': 3.9,
         'shadows': True, 'radius': 0.35},
        {'id': 'hose', 'at': [HOSE_X, 1.35, Z1 - 0.25], 'color': '#ff3a24', 'intensity': 0.9, 'range': 1.3},
        {'id': 'camera', 'at': [X1 - 0.3, 2.2, 2.85], 'color': '#ff2a1a', 'intensity': 1.1, 'range': 1.9},
        {'id': 'exit_stair', 'at': [X1 + 0.9, 1.7, -2.5], 'color': '#ffc488', 'intensity': 2.4, 'range': 3.6,
         'shadows': True, 'radius': 0.3},
        {'id': 'entry_stair', 'at': [X0 - 0.9, 1.5, -1.6], 'color': '#a8c4ff', 'intensity': 2.0, 'range': 3.2,
         'shadows': True, 'radius': 0.3},
        {'id': 'phone', 'at': [PHONE_X, 1.65, Z1 - 0.35], 'color': '#9cffc0', 'intensity': 0.7, 'range': 1.3},
        {'id': 'posters', 'at': [7.2, 2.3, Z1 - 0.9], 'color': '#dce8ff', 'intensity': 1.3, 'range': 2.9},
        {'id': 'showcase', 'at': [0.0, 1.2, Z1 - 0.5], 'color': '#ffd49a', 'intensity': 1.1, 'range': 2.2},
    ]


def kit_lights():
    return [{k: v for k, v in light.items() if k != 'tube'} for light in room_lights()]


def blockers():
    """Boxes that throw the painted shadows: the pillars and the machine at their full height in the
    story (the cut is the drawing's, not the building's), and the walls, with their doors."""
    s = PILLAR_S / 2
    out = [(x - s, -1, z - s, x + s, 3.0, z + s) for x, z in PILLARS]
    out.append((MACHINE[0], -1, MACHINE[1], MACHINE[2], 1.8, MACHINE[3]))
    out += [(XO0, -1, ZO0, X0, 3, ENTRY[0]), (XO0, -1, ENTRY[1], X0, 3, ZO1), (XO0, LINTEL, ENTRY[0], X0, 3, ENTRY[1]),
            (X1, -1, EXIT[1], XO1, 3, ZO1), (X1, LINTEL, ZO0, XO1, 3, EXIT[1])]
    return out


# ---- painting the floor

FLOOR_SPLIT = [XO0, -3.75, 3.75, XO1]    # three textures across the passage
FLOOR_TEX = (180, 124)


def tactile_path():
    """The tactile paving's line: from the way in, along the passage, out to the way on."""
    return [(X0, -1.6), (-9.7, -1.6), (-9.7, -0.45), (9.6, -0.45), (9.6, -2.5), (X1, -2.5)]


def floor_base(x, z):
    """The floor in white light: worn beige tiles, 30 cm, a darker border, the tactile line."""
    rng = np.random.default_rng(31)
    h, w = x.shape
    tile = 0.3
    ix, iz = np.floor(x / tile), np.floor(z / tile)
    var = (np.sin(ix * 12.9898 + iz * 78.233) * 43758.5453) % 1.0
    base = np.zeros((h, w, 3)) + np.array([150, 146, 136])
    base += (var[..., None] - 0.5) * np.array([9, 9, 8])
    border = (z > Z1 - 0.6) | (z < Z0 + 0.45) | (x < X0 + 0.45) | (x > X1 - 0.45)
    base = np.where(border[..., None], np.array([92, 92, 98]) + (var[..., None] - 0.5) * 8, base)
    gx = np.abs(((x / tile) % 1.0) - 0.5) > 0.42
    gz = np.abs(((z / tile) % 1.0) - 0.5) > 0.42
    base = base - ((gx | gz)[..., None]) * np.array([12, 12, 11])
    # wear along the walking line, and grime toward the walls
    walk = np.exp(-((z + 1.2) / 1.6) ** 2)
    base = base * (1 - 0.06 * walk[..., None])
    edge = np.minimum.reduce([z - Z0, Z1 - z, x - X0, X1 - x])
    base = base * (0.78 + 0.22 * smoothstep(0, 0.5, edge))[..., None]
    base += (rng.random((h, w)) - 0.5)[..., None] * 6
    # the tactile line: yellow blocks, bars along the way, dots at the turns
    pts = tactile_path()
    line = np.zeros((h, w), dtype=bool)
    bars = np.zeros((h, w), dtype=bool)
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        if az == bz:
            m = (x >= min(ax, bx) - 0.15) & (x <= max(ax, bx) + 0.15) & (np.abs(z - az) < 0.15)
            bars |= m & (np.abs(((z - az + 0.15) / 0.075) % 1.0 - 0.5) < 0.22)
        else:
            m = (z >= min(az, bz) - 0.15) & (z <= max(az, bz) + 0.15) & (np.abs(x - ax) < 0.15)
            bars |= m & (np.abs(((x - ax + 0.15) / 0.075) % 1.0 - 0.5) < 0.22)
        line |= m
    dots = np.zeros((h, w), dtype=bool)
    for (cx, cz) in pts[1:-1]:
        m = (np.abs(x - cx) < 0.3) & (np.abs(z - cz) < 0.3)
        dots |= m & ((np.hypot(((x - cx) / 0.1) % 1.0 - 0.5, ((z - cz) / 0.1) % 1.0 - 0.5)) < 0.3)
        line |= m
    yellow = np.array([180, 150, 50])
    base = np.where(line[..., None], yellow * 0.86, base)
    base = np.where((bars | dots)[..., None], yellow * 1.08, base)
    return base


def floor_paint(x, z):
    """The floor as the room's lights light it, with the glossy tiles' reflections of the lights,
    a trail of drips to the lost umbrella and the umbrella's puddle."""
    y = np.zeros_like(x)
    lights = room_lights()
    s = shade(x, y, z, (0, 1, 0), lights, AMBIENT, DIFFUSE, DIRECTION, blockers())
    rgb = floor_base(x, z) * s
    # reflections in the polished tiles: each light seen in the floor, toward the camera (60 degrees)
    for light in lights:
        lx, ly, lz = light['at']
        if lz > Z1 or lz < Z0 or lx < X0 or lx > X1 or not light['id'].startswith(('tube', 'machine')):
            continue
        zr = lz - ly * math.tan(math.radians(30))
        half = (light.get('tube') or [0.15])[0] + 0.1
        g = blob(x, z, lx, zr, half, 0.3) ** 1.5
        rgb += (g * 0.08 * light['intensity'])[..., None] * hex_rgb(light['color'])
    # the vending machine's face lights the floor before it hard and bright
    g = soft_rect(x, z, MACHINE[0] + 0.05, MACHINE[2] - 0.05, MACHINE[3], MACHINE[3] + 0.5, 0.6)
    rgb += (g * 0.35)[..., None] * np.array([210, 236, 255])
    # drips from the way on to the umbrella, and its puddle
    rng = np.random.default_rng(5)
    ux, uz = UMBRELLA
    for k in range(70):
        t = k / 70
        cx = X1 - 0.6 + (ux - (X1 - 0.6)) * t + rng.normal(0, 0.08)
        cz = -2.4 + (uz - 0.9 - (-2.4)) * min(1, t * 1.3) + 0.9 * max(0, t * 1.3 - 0.3) / 1.0 + rng.normal(0, 0.08)
        if rng.random() < 0.55:
            d = blob(x, z, cx, cz, 0.04, 0.035)
            rgb = rgb * (1 - 0.28 * d[..., None]) + d[..., None] * np.array([10, 14, 20])
    puddle = blob(x, z, ux + 0.25, uz - 0.1, 0.55, 0.32) > 0.5
    rgb = np.where(puddle[..., None], rgb * 0.72 + np.array([8, 12, 22]), rgb)
    return rgb


# ---- painting the back wall (seen from the room: x left to right, y top down)

WALL_SPLIT = [XO0, 0.0, XO1]
WALL_TEX = (240, 52)


def shutter_motif(k, x, y, a, b):
    """What each shop painted on its shutter: a key (the key cutter), a cup (the coffee shop), a
    flower (the florist). Masks in the shutter's own frame."""
    u = (x - a) / (b - a)
    v = y / SHOP_H
    cx, cy = 0.5, 0.52
    if k == 0:      # a key, lying along the shutter
        bow = np.hypot((u - 0.3) / 0.075, (v - cy) / 0.16) < 1
        hole = np.hypot((u - 0.3) / 0.03, (v - cy) / 0.065) < 1
        shaft = (u > 0.33) & (u < 0.72) & (np.abs(v - cy) < 0.045)
        bit = (u > 0.6) & (u < 0.7) & (v < cy) & (v > cy - 0.16) & (((u * 40) % 2) < 1.2)
        return (bow & ~hole) | shaft | bit, np.array([196, 52, 46])
    if k == 1:      # a cup and its steam
        cup = (np.abs(u - cx) < 0.13) & (v > 0.3) & (v < 0.58) & (np.hypot((u - cx) / 0.13, (v - 0.33) / 0.28) < 1.08)
        handle = (np.hypot((u - cx - 0.15) / 0.05, (v - 0.46) / 0.08) < 1) & ~(np.hypot((u - cx - 0.15) / 0.025, (v - 0.46) / 0.045) < 1)
        saucer = (np.abs(u - cx) < 0.2) & (np.abs(v - 0.28) < 0.025)
        steam = (v > 0.62) & (v < 0.86) & (np.abs(u - cx - 0.035 * np.sin(v * 30)) % 0.09 < 0.018) & (np.abs(u - cx) < 0.1)
        return cup | handle | saucer | steam, np.array([120, 70, 40])
    petals = np.zeros_like(u, dtype=bool)   # a flower, five petals and a stem
    for i in range(5):
        a_ = math.tau * i / 5 + 0.3
        petals |= np.hypot((u - cx - 0.07 * math.cos(a_)) / 0.06, (v - 0.62 - 0.15 * math.sin(a_)) / 0.13) < 1
    middle = np.hypot((u - cx) / 0.035, (v - 0.62) / 0.08) < 1
    stem = (np.abs(u - cx - 0.01 * np.sin(v * 12)) < 0.012) & (v > 0.12) & (v < 0.55)
    leaf = np.hypot((u - cx - 0.05) / 0.05, (v - 0.33) / 0.04) < 1
    return (petals & ~middle) | stem | leaf, np.where(np.dstack([stem | leaf] * 3), np.array([60, 130, 70]),
                                                      np.array([214, 96, 150]))


def poster(u, v):
    """The film poster, one design repeated down the run: night blue, a pale crescent moon, a
    figure on a roof's edge, a red title band. u, v in 0..1 across the sheet (v up)."""
    rgb = np.zeros(u.shape + (3,)) + np.array([30, 42, 92])
    rgb += (v[..., None]) * np.array([20, 18, 40])
    moon = (np.hypot((u - 0.58) / 0.24, (v - 0.66) / 0.17) < 1) & ~(np.hypot((u - 0.68) / 0.22, (v - 0.7) / 0.16) < 1)
    rgb = np.where(moon[..., None], np.array([238, 226, 170]), rgb)
    roof = v < 0.3 + 0.05 * (u > 0.55)
    rgb = np.where(roof[..., None], np.array([14, 16, 34]), rgb)
    figure = (np.abs(u - 0.32) < 0.035) & (v > 0.3) & (v < 0.43)
    head = np.hypot((u - 0.32) / 0.03, (v - 0.455) / 0.022) < 1
    rgb = np.where((figure | head)[..., None], np.array([14, 16, 34]), rgb)
    band = (v > 0.07) & (v < 0.17)
    rgb = np.where(band[..., None], np.array([200, 44, 40]), rgb)
    rgb = np.where(((v > 0.2) & (v < 0.24) & (np.abs(u - 0.5) < 0.3))[..., None], np.array([210, 210, 220]), rgb)
    return rgb


def wall_base(x, y):
    """The back wall in white light: cream tiles to 1.1 m and plaster above on the piers, the fascia
    panels, the shutters and their paintings, the poster run."""
    rng = np.random.default_rng(17)
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array([176, 172, 160])           # plaster
    tiles = y < 1.1
    tx = np.abs(((x / 0.15) % 1.0) - 0.5) > 0.38
    ty = np.abs(((y / 0.15) % 1.0) - 0.5) > 0.38
    base = np.where(tiles[..., None], np.array([206, 204, 192]) - ((tx | ty)[..., None]) * np.array([30, 30, 28]), base)
    base = np.where(((y > 1.1) & (y < 1.16))[..., None], np.array([120, 124, 128]), base)   # a steel rail
    base = np.where((y < 0.1)[..., None], np.array([70, 70, 74]), base)                    # skirting
    for k, (a, b) in enumerate(SHOPS):
        fascia = (x > a) & (x < b) & (y > SHOP_H)
        base = np.where(fascia[..., None], np.array([70, 72, 80]), base)
        sh = (x > a) & (x < b) & (y < SHOP_H)
        ribs = (((y / 0.075) % 1.0) < 0.45)
        metal = np.array([150, 154, 160]) + ribs[..., None] * np.array([22, 22, 22])
        metal = metal * (0.82 + 0.18 * (y / SHOP_H))[..., None]
        motif, colour = shutter_motif(k, x, y, a, b)
        metal = np.where(motif[..., None], colour * (0.9 + 0.1 * ribs[..., None]), metal)
        metal = np.where((y < 0.08)[..., None], np.array([80, 82, 88]), metal)                # bottom rail
        metal = np.where((y > SHOP_H - 0.14)[..., None], np.array([96, 98, 104]), metal)      # roll box
        base = np.where(sh[..., None], metal, base)
    # the poster run
    for cx in POSTERS:
        u = (x - (cx - 0.36)) / 0.72
        v = (y - 0.72) / 1.02
        on = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
        base = np.where(on[..., None], poster(u, v), base)
        frame = on & ((u < 0.04) | (u > 0.96) | (v < 0.03) | (v > 0.97))
        base = np.where(frame[..., None], np.array([200, 200, 196]), base)
    # a tiled pier by the payphone is the same; a route map by the way in: lines and dots
    m = (x > X0 + 0.2) & (x < X0 + 1.2) & (y > 1.3) & (y < 2.0)
    mu = (x - X0 - 0.2) / 1.0
    mv = (y - 1.3) / 0.7
    mp = np.where(m[..., None], np.array([210, 212, 206]), base)
    for k, (c, ph) in enumerate(((np.array([220, 70, 60]), 0.2), (np.array([60, 120, 210]), 1.3),
                                 (np.array([60, 170, 90]), 2.1))):
        ln = m & (np.abs(mv - 0.5 - 0.3 * np.sin(mu * 5 + ph)) < 0.05)
        mp = np.where(ln[..., None], c, mp)
    base = mp
    base += (rng.random((h, w)) - 0.5)[..., None] * 6
    return base


def wall_paint(x, y, z):
    s = shade(x, y, z, (0, 0, -1), room_lights(), AMBIENT, DIFFUSE, DIRECTION, blockers())
    rgb = wall_base(x, y) * s
    # the shutters' recess darkens at its jambs
    for a, b in SHOPS:
        inside = (x > a) & (x < b) & (y < SHOP_H)
        edge = np.minimum(x - a, b - x)
        rgb = np.where(inside[..., None], rgb * (0.6 + 0.4 * smoothstep(0, 0.25, edge))[..., None], rgb)
    return rgb


# ---- small textures

def sign_face(k):
    """A shop's lit fascia sign: a pale lit panel, its pictogram at the left, a line of marks."""
    w, h = 64, 8
    bg = [(236, 240, 250), (250, 196, 120), (252, 200, 222)][k]
    ink = [(200, 40, 40), (96, 52, 30), (190, 50, 120)][k]
    img = Image.new('RGB', (w, h), bg)
    d = ImageDraw.Draw(img)
    if k == 0:
        d.ellipse([3, 1, 8, 6], outline=ink)
        d.line([(8, 4), (16, 4)], fill=ink)
        d.line([(14, 4), (14, 6)], fill=ink)
    elif k == 1:
        d.rectangle([4, 2, 9, 6], fill=ink)
        d.point((10, 3), fill=ink)
        d.point((10, 4), fill=ink)
        d.line([(3, 7), (11, 7)], fill=ink)
    else:
        for (px, py) in ((7, 1), (5, 3), (9, 3), (6, 5), (8, 5)):
            d.point((px, py), fill=ink)
        d.point((7, 3), fill=(240, 200, 60))
        d.line([(7, 6), (7, 7)], fill=(60, 130, 70))
    for i in range(6):
        x0 = 22 + i * 6
        d.rectangle([x0, 2, x0 + 3, 5], fill=ink)
    d.rectangle([0, 0, w - 1, h - 1], outline=tuple(int(c * 0.7) for c in bg))
    return img


def pillar_face():
    """A pillar's side in white light: cream tiles, a green zone band, a number plate."""
    w, h = 16, 20
    img = Image.new('RGB', (w, h), (200, 198, 186))
    d = ImageDraw.Draw(img)
    for yy in range(0, h, 3):
        d.line([(0, yy), (w - 1, yy)], fill=(168, 166, 156))
    for xx in range(0, w, 3):
        d.line([(xx, 0), (xx, h - 1)], fill=(176, 174, 164))
    d.rectangle([0, 9, w - 1, 11], fill=(60, 140, 100))
    d.rectangle([5, 3, 10, 6], fill=(236, 236, 230))
    d.line([(6, 4), (9, 4)], fill=(40, 40, 46))
    d.rectangle([0, h - 2, w - 1, h - 1], fill=(90, 90, 96))
    return img


def section_face(w, h, inner, ring, fill=(196, 204, 222)):
    """A cut top, drawn as a section: pale, with the cladding's ring."""
    img = Image.new('RGB', (w, h), fill)
    d = ImageDraw.Draw(img)
    for k in range(-h, w, 4):          # the section's hatching
        d.line([(k, h - 1), (k + h - 1, 0)], fill=tuple(int(c * 0.93) for c in fill))
    d.rectangle([0, 0, w - 1, h - 1], outline=ring)
    if inner:
        d.rectangle([1, 1, w - 2, h - 2], outline=inner)
    return img


def machine_top():
    """The vending machine cut at 95 cm: inside, the lit columns of cans seen from above."""
    w, h = 24, 10
    img = Image.new('RGB', (w, h), (232, 240, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=(40, 80, 160))
    d.rectangle([1, 1, w - 2, 2], fill=(60, 110, 200))
    cols = [(230, 60, 50), (250, 200, 60), (60, 160, 230), (240, 240, 240), (90, 190, 90), (200, 120, 60),
            (230, 60, 50), (60, 160, 230), (250, 200, 60), (240, 240, 240), (120, 90, 200)]
    for i, c in enumerate(cols):
        x0 = 1 + i * 2
        d.rectangle([x0, 4, x0, 5], fill=c)
        d.rectangle([x0, 7, x0, 8], fill=tuple(int(v * 0.8) for v in c))
    return img


def bin_top():
    img = Image.new('RGB', (8, 8), (150, 160, 168))
    d = ImageDraw.Draw(img)
    d.ellipse([1, 2, 3, 4], fill=(20, 24, 30))
    d.ellipse([4, 2, 6, 4], fill=(20, 24, 30))
    d.rectangle([0, 6, 7, 7], fill=(60, 130, 200))
    return img


def hose_face():
    """The fire hose cabinet's door: red, a white pictogram."""
    w, h = 12, 12
    img = Image.new('RGB', (w, h), (200, 40, 36))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=(120, 20, 20))
    d.ellipse([3, 3, 8, 8], outline=(240, 236, 230))
    d.point((5, 5), fill=(240, 236, 230))
    d.line([(8, 6), (10, 9)], fill=(240, 236, 230))
    return img


def ground_section(a, b, w=240, h=20):
    """The cut through the ground beside the passage, on the front wall's face: the wall's concrete
    and the slab in section (pale, as every cut), and the earth around them with the services that
    run beside a passage under a street: a duct bank of cables, a water main, a gas main, drains."""
    xs = a + (np.arange(w) + 0.5) / w * (b - a)
    ys = CUT - (np.arange(h) + 0.5) / h * (CUT + SLAB)
    x, y = np.meshgrid(xs, ys)
    rng = np.random.default_rng(23 + int(a))
    rgb = np.zeros((h, w, 3)) + np.array([58, 46, 42])
    rgb += (np.sin(y * 18 + np.sin(x * 0.7) * 2) > 0.6)[..., None] * np.array([10, 8, 6])     # strata
    rgb += ((rng.random((h, w)) > 0.93)[..., None]) * np.array([22, 20, 18])                  # gravel
    slab = y < 0.0
    rgb = np.where(slab[..., None], np.array([118, 128, 148]), rgb)
    rgb = np.where((np.abs(y) < 0.03)[..., None], np.array([150, 162, 184]), rgb)
    pipes = [(-9.0, 0.5, 0.3, (70, 110, 170)), (-7.9, 0.42, 0.2, (210, 180, 60)), (-4.2, 0.5, 0.36, (110, 110, 116)),
             (2.0, 0.48, 0.3, (70, 110, 170)), (5.4, 0.44, 0.22, (210, 180, 60)), (8.6, 0.5, 0.36, (110, 110, 116))]
    for px, py, pr, c in pipes:
        d = np.hypot((x - px) / 1.0, (y - py) / 1.0)
        rgb = np.where((d < pr)[..., None], np.array(c) * 0.6, rgb)
        rgb = np.where(((d < pr) & (d > pr * 0.6))[..., None], np.array(c), rgb)
    for k in range(4):     # a duct bank: a row of cable ducts in a concrete block
        bx = -1.65 + k * 0.42
        d = np.hypot(x - bx, y - 0.48)
        rgb = np.where(((np.abs(x + 1.02) < 0.9) & (np.abs(y - 0.48) < 0.3))[..., None] & (d >= 0.14)[..., None],
                       np.array([110, 112, 118]), rgb)
        rgb = np.where((d < 0.14)[..., None], np.array([30, 30, 34]), rgb)
    return Image.fromarray(to_array(rgb, 4.0), 'RGB')


def crate_top():
    """A crate of empty bottles from above: a yellow crate, a grid of bottle mouths."""
    img = Image.new('RGB', (10, 8), (210, 170, 40))
    d = ImageDraw.Draw(img)
    for i in range(4):
        for j in range(3):
            d.point((1 + i * 2 + 1, 1 + j * 2 + 1), fill=(60, 90, 70))
    d.rectangle([0, 0, 9, 7], outline=(150, 110, 20))
    return img


def paper_top():
    """A bundle of the morning's papers, tied, waiting by the coffee shop."""
    img = Image.new('RGB', (8, 10), (214, 210, 196))
    d = ImageDraw.Draw(img)
    for j in (2, 4, 6):
        d.line([(1, j), (6, j)], fill=(150, 146, 136))
    d.line([(4, 0), (4, 9)], fill=(190, 60, 50))
    d.line([(0, 5), (7, 5)], fill=(190, 60, 50))
    return img


def draw_art():
    ART.mkdir(exist_ok=True)
    w, h = FLOOR_TEX
    paintings = []
    for a, b in zip(FLOOR_SPLIT, FLOOR_SPLIT[1:]):
        x, y, z = grid_floor(a, b, ZO0, ZO1, w, h)
        paintings.append(to_array(floor_paint(x, z)))
    ww, wh = WALL_TEX
    for a, b in zip(WALL_SPLIT, WALL_SPLIT[1:]):
        x, y, z = grid_wall_z(a, b, 0.0, WALL_H, ww, wh, Z1)
        z = np.where((y < SHOP_H) & np.logical_or.reduce([(x > sa) & (x < sb) for sa, sb in SHOPS]), Z1 + RECESS, z)
        paintings.append(to_array(wall_paint(x, y, z)))
    names = [f'floor_{k}' for k in range(3)] + [f'wall_{k}' for k in range(2)]
    for name, img in zip(names, quantise_together(paintings)):
        img.save(ART / f'{name}.png')
    for k in range(3):
        sign_face(k).save(ART / f'sign_{k}.png')
    pillar_face().save(ART / 'pillar.png')
    section_face(16, 16, (126, 138, 162), (88, 96, 116), fill=(140, 154, 180)).save(ART / 'pillar_cut.png')
    for k, (a, b) in enumerate(zip(WALL_SPLIT, WALL_SPLIT[1:])):
        ground_section(a, b).save(ART / f'ground_{k}.png')
    machine_top().save(ART / 'machine_top.png')
    bin_top().save(ART / 'bin_top.png')
    crate_top().save(ART / 'crate_top.png')
    paper_top().save(ART / 'papers.png')
    hose_face().save(ART / 'hose.png')


# ---- the recipe

def materials():
    m = {
        'cut': {'color': '#8c9ab4', 'class': 'emissive'},          # the section's cut faces: pale, unlit
        'ground_0': {'color': '#3a3230', 'class': 'emissive',      # the ground beside the passage, in section
                     'texture': {'image': 'art/ground_0.png', 'bits': 4, 'projection': 'fit'}},
        'ground_1': {'color': '#3a3230', 'class': 'emissive',
                     'texture': {'image': 'art/ground_1.png', 'bits': 4, 'projection': 'fit'}},
        'jamb': {'color': '#8a8c90'},
        'end_wall': {'color': '#a8a69c',
                     'texture': {'pattern': 'tile', 'colors': ['#c8c6ba', '#9a988e'], 'size': 16,
                                 'params': {'count': 2, 'grout': 1}, 'projection': 'box', 'scale': [0.3, 0.3]}},
        'lintel': {'color': '#76787e'},
        'door_light': {'color': '#ffd8a8', 'class': 'emissive'},
        'pillar': {'color': '#c4c2b4', 'texture': {'image': 'art/pillar.png', 'bits': 4, 'projection': 'fit'}},
        'pillar_cut': {'color': '#8c9ab4', 'class': 'emissive',
                       'texture': {'image': 'art/pillar_cut.png', 'bits': 4, 'projection': 'fit'}},
        'machine': {'color': '#c8d4e4'},
        'machine_side': {'color': '#3c64b4'},
        'machine_top': {'color': '#e0e8f4', 'class': 'emissive',
                        'texture': {'image': 'art/machine_top.png', 'bits': 4, 'projection': 'fit'}},
        'bin': {'color': '#8c98a4'},
        'bin_top': {'color': '#96a0a8', 'texture': {'image': 'art/bin_top.png', 'bits': 4, 'projection': 'fit'}},
        'sign_box': {'color': '#50525a'},
        'phone': {'color': '#3c9c5c'},
        'phone_dark': {'color': '#30343a'},
        'phone_lit': {'color': '#b8f0c8', 'class': 'emissive'},
        'shelf': {'color': '#9a9ea4'},
        'hose_box': {'color': '#a83028'},
        'hose_face': {'color': '#c83028', 'texture': {'image': 'art/hose.png', 'bits': 4, 'projection': 'fit'}},
        'hose_lamp': {'color': '#ff4030', 'class': 'emissive'},
        'vinyl': {'color': '#e8f4ff', 'blend': 'half', 'double_sided': True},
        'umbrella_rib': {'color': '#e8eef4'},
        'umbrella_handle': {'color': '#3a2c24'},
        'crate': {'color': '#c09a30'},
        'crate_top': {'color': '#c8a034', 'texture': {'image': 'art/crate_top.png', 'bits': 4, 'projection': 'fit'}},
        'papers': {'color': '#c8c4b4', 'texture': {'image': 'art/papers.png', 'bits': 4, 'projection': 'fit'}},
        'bucket': {'color': '#3c8c6c'},
    }
    for k in range(3):
        m[f'floor_{k}'] = {'color': '#5a6070', 'class': 'emissive',
                           'texture': {'image': f'art/floor_{k}.png', 'bits': 8, 'projection': 'fit'}}
        m[f'sign_{k}'] = {'color': ['#e0e6f4', '#f0b878', '#f0b8d0'][k], 'class': 'emissive',
                          'texture': {'image': f'art/sign_{k}.png', 'bits': 4, 'projection': 'fit'}}
    for k in range(2):
        m[f'wall_{k}'] = {'color': '#6a6c70', 'class': 'emissive',
                          'texture': {'image': f'art/wall_{k}.png', 'bits': 8, 'projection': 'fit'}}
    return m


def floor_mesh():
    f = Mesh()
    for k, (a, b) in enumerate(zip(FLOOR_SPLIT, FLOOR_SPLIT[1:])):
        f.quad(a, 0, ZO0, b, 0, ZO1, (0, 1, 0), f'floor_{k}')
    for k, (a, b) in enumerate(zip(WALL_SPLIT, WALL_SPLIT[1:])):
        f.quad(a, -SLAB, ZO0, b, CUT, ZO0, (0, 0, -1), f'ground_{k}')
    return f.node('floor', 'floor_0')


def back_wall_mesh():
    """The back wall's room side: its piers and fascias at z 3.4, the shutters set back in their
    openings, all mapped by x and y onto the two painted wall textures; the jambs plain."""
    m = Mesh()

    def uv_for(k):
        a, b = WALL_SPLIT[k], WALL_SPLIT[k + 1]
        return lambda p: ((p[0] - a) / (b - a), (WALL_H - p[1]) / WALL_H)

    def rect(x0, x1, y0, y1, z):
        for k, (a, b) in enumerate(zip(WALL_SPLIT, WALL_SPLIT[1:])):
            lo, hi = max(x0, a), min(x1, b)
            if hi - lo > 1e-6:
                m.quad(lo, y0, z, hi, y1, z, (0, 0, -1), f'wall_{k}', uv_for(k))

    edges = [XO0] + [v for s in SHOPS for v in s] + [XO1]
    for a, b in zip(edges[0::2], edges[1::2]):
        rect(a, b, 0, WALL_H, Z1)                       # piers
    for a, b in SHOPS:
        rect(a, b, SHOP_H, WALL_H, Z1)                  # fascias
        rect(a, b, 0, SHOP_H, Z1 + RECESS)              # shutters
        m.quad(a, 0, Z1, a, SHOP_H, Z1 + RECESS, (1, 0, 0), 'jamb')
        m.quad(b, 0, Z1, b, SHOP_H, Z1 + RECESS, (-1, 0, 0), 'jamb')
    m.quad(XO0, WALL_H, Z1, XO1, WALL_H, ZO1, (0, 1, 0), 'cut')
    return m.node('back_wall', 'wall_0')


def shell_nodes():
    n = [floor_mesh(), back_wall_mesh()]
    n.append(box('front_wall', (XO0, -0.02, ZO0), (XO1, CUT, Z0), 'cut', open=['bottom', 'front', 'back']))
    n.append(box('end_w_front', (XO0, -0.02, Z0), (X0, WALL_H - 0.02, ENTRY[0]), 'end_wall',
                 open=['bottom'], faces={'top': 'cut', 'back': 'cut'}))
    n.append(box('end_w_back', (XO0, -0.02, ENTRY[1]), (X0, WALL_H - 0.02, Z1 + 0.01), 'end_wall',
                 open=['bottom', 'front'], faces={'top': 'cut'}))
    n.append(box('entry_lintel', (XO0 + 0.012, LINTEL, ENTRY[0] - 0.01), (X0 - 0.012, WALL_H - 0.03, ENTRY[1] + 0.01), 'lintel',
                 open=['back', 'front'], faces={'top': 'cut'}))
    n.append(box('end_e', (X1, -0.02, EXIT[1]), (XO1, WALL_H - 0.02, Z1 + 0.01), 'end_wall',
                 open=['bottom', 'front'], faces={'top': 'cut'}))
    n.append(box('exit_lintel', (X1 + 0.012, LINTEL, Z0 + 0.01), (XO1 - 0.012, WALL_H - 0.03, EXIT[1] + 0.01), 'lintel',
                 open=['back', 'front'], faces={'top': 'cut', 'bottom': 'door_light'}))
    return n


def prop_nodes():
    n = []
    s = PILLAR_S / 2
    for k, (x, z) in enumerate(PILLARS):
        n.append(box(f'pillar_{k}', (x - s, -0.02, z - s), (x + s, CUT, z + s), 'pillar', open=['bottom'],
                     faces={'top': 'pillar_cut'}))
    x0, z0, x1, z1 = MACHINE
    n.append(box('machine', (x0, -0.02, z0), (x1, MACHINE_H, z1), 'machine', open=['bottom', 'back'],
                 faces={'top': 'machine_top', 'left': 'machine_side', 'right': 'machine_side'}))
    bx0, bz0, bx1, bz1 = BIN
    n.append(box('bin', (bx0, -0.02, bz0), (bx1, 0.74, bz1), 'bin', open=['bottom'], faces={'top': 'bin_top'}))
    # the shop signs on their fascias
    for k, (a, b) in enumerate(SHOPS):
        n.append(box(f'sign_{k}', (a + 0.3, 1.86, Z1 - 0.12), (b - 0.3, 2.3, Z1 + 0.02), 'sign_box',
                     open=['front'], faces={'back': f'sign_{k}'}))
    # the payphone on its shelf
    px = PHONE_X
    phone = [box('phone_shelf', (px - 0.42, 0.84, Z1 - 0.34), (px + 0.42, 0.89, Z1 + 0.02), 'shelf', open=['front']),
             box('phone_body', (px - 0.2, 0.875, Z1 - 0.22), (px + 0.2, 1.42, Z1 + 0.02), 'phone', open=['front', 'bottom'],
                 faces={'top': 'phone_dark'}),
             box('phone_handset', (px - 0.17, 1.12, Z1 - 0.27), (px - 0.07, 1.36, Z1 - 0.21), 'phone_dark'),
             box('phone_sign', (px - 0.22, 1.62, Z1 - 0.06), (px + 0.22, 1.76, Z1 + 0.02), 'phone_lit', open=['front'])]
    n.append(group('payphone', phone))
    hx = HOSE_X
    n.append(group('hose', [
        box('hose_box', (hx - 0.4, 0.4, Z1 - 0.12), (hx + 0.4, 1.12, Z1 + 0.02), 'hose_box', open=['front'],
            faces={'back': 'hose_face'}),
        at({'id': 'hose_lamp', 'op': 'sphere', 'radius': 0.07, 'rings': 3, 'segments': 6, 'material': 'hose_lamp'},
           translate=[hx, 1.26, Z1 - 0.04])]))
    # the lost umbrella: open, on its side by the pillar
    ux, uz = UMBRELLA
    n.append(group('umbrella', [
        at({'id': 'canopy', 'op': 'cone', 'radius': 0.48, 'height': 0.3, 'segments': 8, 'caps': False,
            'material': 'vinyl'}, translate=[ux, 0.3, uz], rotate=[0, 0, 62]),
        at({'id': 'shaft', 'op': 'box', 'size': [0.78, 0.025, 0.025], 'material': 'umbrella_rib'},
           translate=[ux + 0.36, 0.2, uz - 0.02], rotate=[0, 0, -28]),
        at({'id': 'handle', 'op': 'box', 'size': [0.05, 0.12, 0.04], 'material': 'umbrella_handle'},
           translate=[ux + 0.73, 0.05, uz - 0.02])]))
    # by the coffee shop: a crate of empties and the morning's papers; by the florist: its buckets
    n.append(group('morning', [
        box('crate', (-1.42, -0.02, Z1 - 0.48), (-0.92, 0.3, Z1 - 0.1), 'crate', open=['bottom'], faces={'top': 'crate_top'}),
        box('papers_0', (-2.05, -0.02, Z1 - 0.42), (-1.65, 0.22, Z1 - 0.1), 'papers', open=['bottom']),
        box('papers_1', (-2.0, 0.21, Z1 - 0.44), (-1.62, 0.4, Z1 - 0.14), 'papers', open=['bottom'])]))
    n.append(group('buckets', [
        at({'id': f'bucket_{k}', 'op': 'cylinder', 'radius': 0.17, 'height': h, 'segments': 8, 'material': 'bucket'},
           translate=[x, h / 2 - 0.01, Z1 - 0.3]) for k, (x, h) in enumerate(((4.05, 0.42), (3.65, 0.36), (4.12, 0.3)))
        ][:2] + [at({'id': 'bucket_2', 'op': 'cylinder', 'radius': 0.15, 'height': 0.3, 'segments': 8,
                     'material': 'bucket'}, translate=[3.86, 0.14, Z1 - 0.62])]))
    return n


def showcase_recipe():
    """The coffee shop's window of food models, on the pier beside its shutter, lit from inside:
    an omelette on rice, spaghetti, a cream soda with its cherry, a slice of cake. Its own recipe,
    lit by its own lamp only and corners only, so that no light refines its glass."""
    x0, x1, y0, y1, zf = SHOWCASE
    zb = Z1 + 0.02
    m = {'frame': {'color': '#4a3426'}, 'back': {'color': '#e8d8b8', 'class': 'emissive'},
         'shelf': {'color': '#c8b89c'}, 'glass': {'color': '#9cb8c8', 'blend': 'half'},
         'omelette': {'color': '#f0c840'}, 'ketchup': {'color': '#c83020'}, 'pasta': {'color': '#e08838'},
         'soda': {'color': '#40d070'}, 'cherry': {'color': '#e02030'}, 'cake': {'color': '#f4e8d0'},
         'plate': {'color': '#f0f0ec'}}
    n = [box('base', (x0, y0, zf), (x1, y0 + 0.06, zb), 'frame', open=['front']),
         box('back', (x0 + 0.02, y0 + 0.05, zb - 0.03), (x1 - 0.02, y1 - 0.005, zb - 0.005), 'back', open=['front', 'bottom']),
         box('side_l', (x0 + 0.004, y0 + 0.05, zf + 0.004), (x0 + 0.03, y1, zb - 0.004), 'frame', open=['front', 'bottom']),
         box('side_r', (x1 - 0.03, y0 + 0.05, zf + 0.004), (x1 - 0.004, y1, zb - 0.004), 'frame', open=['front', 'bottom']),
         box('shelf', (x0 + 0.025, y0 + 0.36, zf + 0.04), (x1 - 0.025, y0 + 0.39, zb - 0.02), 'shelf'),
         box('glass_front', (x0 + 0.03, y0 + 0.06, zf), (x1 - 0.03, y1, zf + 0.01), 'glass',
             open=['front', 'left', 'right', 'top', 'bottom']),
         box('glass_top', (x0 + 0.03, y1 - 0.01, zf), (x1 - 0.03, y1, zb - 0.03), 'glass',
             open=['front', 'back', 'left', 'right', 'bottom'])]
    food = [('plate_0', 'plate', (-0.2, y0 + 0.07, 0.2, 0.012)), ('plate_1', 'plate', (0.18, y0 + 0.07, 0.16, 0.012)),
            ('plate_2', 'plate', (-0.18, y0 + 0.4, 0.15, 0.012))]
    for id, mat, (fx, fy, rad, hh) in food:
        n.append(at({'id': id, 'op': 'cylinder', 'radius': rad, 'height': hh * 2, 'segments': 8, 'material': mat},
                    translate=[fx, fy + hh, zf + 0.18]))
    n.append(at({'id': 'omelette', 'op': 'sphere', 'radius': 1.0, 'rings': 3, 'segments': 6, 'material': 'omelette'},
                translate=[-0.2, y0 + 0.12, zf + 0.18], scale=[0.14, 0.06, 0.09]))
    n.append(box('ketchup', (-0.26, y0 + 0.17, zf + 0.16), (-0.12, y0 + 0.185, zf + 0.2), 'ketchup'))
    n.append(at({'id': 'pasta', 'op': 'sphere', 'radius': 1.0, 'rings': 3, 'segments': 6, 'material': 'pasta'},
                translate=[0.18, y0 + 0.11, zf + 0.18], scale=[0.12, 0.05, 0.1]))
    n.append(at({'id': 'soda', 'op': 'cylinder', 'radius': 0.05, 'height': 0.2, 'segments': 6, 'material': 'soda'},
                translate=[0.18, y0 + 0.485, zf + 0.18]))
    n.append(at({'id': 'cherry', 'op': 'sphere', 'radius': 0.025, 'rings': 3, 'segments': 5, 'material': 'cherry'},
                translate=[0.18, y0 + 0.61, zf + 0.18]))
    n.append(box('cake', (-0.24, y0 + 0.41, zf + 0.12), (-0.12, y0 + 0.5, zf + 0.24), 'cake'))
    lighting = {'direction': [0.0, 1.0, -0.6], 'ambient': 0.45, 'diffuse': 0.3,
                'lights': [{'id': 'lamp', 'at': [0.0, y1 - 0.08, zf + 0.2], 'color': '#fff0d0', 'intensity': 1.2,
                            'range': 1.2}], 'refine': {'max_added': 0}}
    return recipe(P + 'showcase', m, n, lighting, 400)


def passage_recipe():
    lighting = {'direction': DIRECTION, 'ambient': AMBIENT, 'diffuse': DIFFUSE, 'lights': kit_lights(),
                'refine': {'tolerance': 20, 'max_added': 220}}
    return recipe(P + 'passage', materials(), shell_nodes() + prop_nodes(), lighting, 2400)


def collision():
    op = ['bottom', 'top']
    s = PILLAR_S / 2
    n = [box('slab', (XO0, -SLAB, ZO0), (XO1, 0, ZO1), 'floor', open=['bottom', 'left', 'right', 'front', 'back']),
         box('front_wall', (XO0, 0, ZO0), (XO1, CUT, Z0), 'floor', open=op),
         box('back_wall', (XO0, 0, Z1), (XO1, WALL_H, ZO1), 'floor', open=op),
         box('end_w_front', (XO0, 0, Z0), (X0, WALL_H, ENTRY[0]), 'floor', open=op + ['back']),
         box('end_w_back', (XO0, 0, ENTRY[1]), (X0, WALL_H, Z1), 'floor', open=op + ['front']),
         box('end_e', (X1, 0, EXIT[1]), (XO1, WALL_H, Z1), 'floor', open=op + ['front'])]
    for k, (x, z) in enumerate(PILLARS):
        n.append(box(f'pillar_{k}', (x - s, 0, z - s), (x + s, CUT, z + s), 'floor', open=op))
    x0, z0, x1, z1 = MACHINE
    n.append(box('machine', (x0, 0, z0 + 0.01), (x1, MACHINE_H, z1), 'floor', open=op + ['back']))
    return collision_recipe(P + 'passage_col', n)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--no-placements', action='store_true', help='leave passage.placements.json as it is')
    args = ap.parse_args()
    draw_art()
    write_json(HERE / f'{P}passage.asset.json', passage_recipe())
    write_json(HERE / f'{P}passage_col.asset.json', collision())
    write_json(HERE / f'{P}showcase.asset.json', showcase_recipe())
    if not args.no_placements:
        write_json(HERE / 'passage.placements.json', {
            'format': 'after-hours-placements', 'version': 1, 'room': 'passage',
            'placements': [{'id': P + 'passage', 'asset': P + 'passage', 'position': [0, 0, 0],
                            'collision': P + 'passage_col'},
                           {'id': P + 'showcase', 'asset': P + 'showcase', 'position': [0, 0, 0],
                            'collision': 'none'}]})     # on the wall, out of reach: the wall's collision is the shell's
    print('wrote r3_passage, r3_passage_col, passage.placements.json and', len(list(ART.glob('*.png'))),
          'textures in', ART.relative_to(HERE.parents[3]))


if __name__ == '__main__':
    main()
