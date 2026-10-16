#!/usr/bin/env python3
"""The aquarium, room 0: the entrance hall, dressed. Writes the room's Asset Kit recipes into
dressed/, their textures into dressed/art/ and (with --placements) aq_hall.placements.json beside
this script; without it, a draft in dressed/draft.placements.json, which the capture prefers while
it exists.

    python3 carts/afterhours/rooms/aq_hall/dress_aq_hall.py --placements

The aquarium's front of house after closing, hushed and cavernous, lit only by the welcome tank:
a cylinder of sea on a black granite plinth, rising through the hall to the restaurant's
mezzanine, a sardine school turning in it, light falling through it. Its blue lies on the
polished floor round it and down to the front wall, netted with caustics, exactly where the play
file's light boxes are; a brass ring is set in the floor round it. Everything else is in shadow:
the main doors from the street (west), the ticket gates shut for the night with their red lamps,
the information desk with its lit map, two pillars with lit fish posters, and the great tank's
blue spilling in through the east door. Over the back runs the restaurant's mezzanine at +3.2 m:
an open deck of timber slats (the floor under it shows through), a glass railing, tables laid at
the railing, plum velvet booths against the back wall under a long window on the night bay and the
city's lights; the tank's open top in it, ringed in steel and glass, lights the deck round it.
The glass door at its west end goes out to the pedestrian deck: the stage's end.

The floor plan is the level lead's (PLAN.md, make_aq_hall.py, imported for its numbers only). The
welcome tank's glass rises through both floors, semi-transparent (nothing opaque in play stands
over 1 m); TANK_CUT = True cuts it at 1 m instead (NOTES.md). Needs NumPy and Pillow.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import make_aq_hall as G  # noqa: E402  (J's plan: imported for its numbers only)
from aqdress import (CUT_H, SECTION_CUT, Mesh, Shell, at, box, caustics, collision, grid, lit_mask,  # noqa: E402
                     mat_tex, paint_section, quantise_together, r, recipe, ring, save_png, smoothstep, stone,
                     to_image, write_json)

sys.path.insert(0, str(HERE.parents[1] / 'water'))   # agent W: the moving water (NOTES_W.md)
import wateranim  # noqa: E402

OUT = HERE / 'dressed'
ART = OUT / 'art'
P = 'ah_'
S = Shell(G.ROOM)
U = G.UPPER
# True: the tank's glass cut at 1 m (the section's rule), its top alone above; AH_TANK_CUT=1 for a look
TANK_CUT = os.environ.get('AH_TANK_CUT') == '1'
TB = G.TANK                           # the tank's box: x0, z0, x1, z1
TC = ((TB[0] + TB[2]) / 2, (TB[1] + TB[3]) / 2)
TR = 1.36                             # the glass, round inside the box
PLINTH = 0.45
WATER_TOP = U - 0.12
MZ = G.MEZZ
DECK_T = 0.2                          # the deck's fascia, under its top
PROPS = {p[0]: p[2] for p in G.ROOM['props']}
UPROPS = {p[0]: p[2] for p in G.ROOM['upper_props']}
HIDES = {h[0]: h[1] for h in G.ROOM['hides']}
LIGHTS = {lid: (b, lvl) for lid, b, lvl, _ in G.ROOM['lights']}
FLOOR_LIGHTS = [b for b, lvl in LIGHTS.values() if lvl == 0]
TANK_LIGHTS = [LIGHTS[k][0] for k in ('tank_s', 'tank_w', 'tank_e')]
DOOR_LIGHT = LIGHTS['door_e'][0]
TOP_LIGHT = LIGHTS['tank_top'][0]
TEX_M = 28                            # the floor's texels a metre
DECK_M = 25
TANK_BLUE = np.array([70, 170, 255], dtype=float)
DOOR_BLUE = np.array([60, 110, 255], dtype=float)


def hexc(rgb):
    return '#%02x%02x%02x' % tuple(int(max(0, min(255, round(c)))) for c in rgb)


def tank_dist(x, z):
    """Distance from the tank's glass, outward (metres)."""
    return np.hypot(x - TC[0], z - TC[1]) - TR


def lights():
    """The kit's point lights for the props (the floor and the deck are painted)."""
    return [
        {'id': 'tank', 'at': [TC[0], 1.6, TC[1]], 'color': '#58b8ff', 'intensity': 1.6, 'range': 4.6},
        {'id': 'tank_top', 'at': [TC[0], U + 0.5, TC[1] + 0.3], 'color': '#58c0ff', 'intensity': 1.3, 'range': 3.2},
        {'id': 'great', 'at': [S.XO1 + 0.6, 1.2, -1.0], 'color': '#3c70ff', 'intensity': 1.5, 'range': 3.0},
        {'id': 'street', 'at': [S.XO0 - 0.8, 1.6, -2.4], 'color': '#8898c0', 'intensity': 0.6, 'range': 2.4},
    ]


# ---- painting

def tile_grid(x0, x1, z0, z1, per_m):
    w = min(255, int(round((x1 - x0) * per_m)))
    h = min(127, int(round((z1 - z0) * per_m)))
    return grid(x0, x1, z0, z1, w, h)


def paint_floor_tile(x0, x1, z0, z1):
    x, z = tile_grid(x0, x1, z0, z1, TEX_M)
    h, w = x.shape
    # black granite in 1.2 m slabs as white light shows it, a brass ring set round the tank
    base = stone(x, z, (100, 108, 128), 1.2, seed=int(abs(x0 * 13 + z0 * 7)) + 3, grout=0.62, fleck=16)
    td = np.hypot(x - TC[0], z - TC[1])
    brass = (np.abs(td - 2.0) < 0.03) | (np.abs(td - 2.12) < 0.015)
    base = np.where(brass[..., None], np.array([200, 170, 100]), base)
    # the entrance mat inside the main doors
    a, b = next(dr['at'] for dr in S.doors if dr['id'] == 'main')
    mat = (x < S.X0 + 1.3) & (z > a + 0.05) & (z < b - 0.05)
    base = np.where(mat[..., None], np.array([84, 88, 100]) + (((x * 20).astype(int) % 2) * 10)[..., None], base)
    shade = np.zeros((h, w, 3)) + 0.2
    # under the mezzanine a little darker still
    shade *= (1 - 0.3 * smoothstep(MZ[1] - 0.2, MZ[1] + 0.4, z))[..., None]
    # the tank's light, in its boxes: strongest at the glass, netted with caustics, reaching the
    # front wall
    m = lit_mask(x, z, TANK_LIGHTS)
    d = np.clip(tank_dist(x, z), 0, None)
    caus = 0.13                 # agent W: the net moves (ah_wwater's overlay); the floor keeps its average, a little under
    L = (0.5 + 0.75 * np.exp(-d / 0.9)) * (0.75 + 0.9 * caus * (0.35 + np.exp(-d / 1.2)))
    shade += (m * L)[..., None] * TANK_BLUE / 255
    # the great tank's blue through the east door
    dm = lit_mask(x, z, [DOOR_LIGHT])
    dz = (DOOR_LIGHT[1] + DOOR_LIGHT[3]) / 2
    Ld = (0.5 + 0.6 * np.exp(-(S.X1 - x) / 0.7)) * (0.85 + 0.25 * np.exp(-((z - dz) / 0.6) ** 2))
    Ld *= 0.85 + 0.5 * 0.13     # agent W: the net moves (ah_wwater)
    shade += (dm * Ld)[..., None] * DOOR_BLUE / 255
    rgb = base * shade
    dd = np.minimum.reduce([x - S.X0, S.X1 - x, z - S.Z0, S.Z1 - z])
    rgb *= (1 - 0.35 * np.exp(-np.clip(dd, 0, None) / 0.2))[..., None]
    return to_image(rgb, 4.0)


def deck_pieces():
    """The mezzanine's deck in three textured pieces round the tank's box: (name, x0, x1, z0, z1)."""
    x0, z0, x1, z1 = MZ
    return [('deck_w', x0, TB[0], z0, z1), ('deck_e', TB[2], x1, z0, z1), ('deck_m', TB[0], TB[2], TB[3], z1)]


def paint_deck(x0, x1, z0, z1):
    """Timber slats running east-west with open gaps (holes: the floor below shows through), lit
    round the tank's top as the play file's light box says."""
    x, z = tile_grid(x0, x1, z0, z1, DECK_M)
    h, w = x.shape
    rng = np.random.default_rng(int(abs(x0 * 10)) + 11)
    base = np.zeros((h, w, 3)) + np.array([150, 112, 82])
    plank = np.floor((z - MZ[1]) / 0.2)
    base *= (0.85 + 0.15 * ((plank * 7) % 5) / 4)[..., None]
    base *= (0.92 + 0.08 * rng.random((h, w)))[..., None]
    butt = (np.abs(((x + plank * 0.7) / 1.8) % 1 - 0.5) > 0.485)
    base *= np.where(butt, 0.6, 1.0)[..., None]
    shade = np.zeros((h, w, 3)) + 0.2
    m = lit_mask(x, z, [TOP_LIGHT])
    d = np.clip(tank_dist(x, z), 0, None)
    L = (0.55 + 0.7 * np.exp(-d / 0.7)) * (0.8 + 0.6 * caustics(x, z, 2.0, 1.1))
    shade += (m * L)[..., None] * TANK_BLUE / 255
    rgb = base * shade
    dd = np.minimum.reduce([x - S.X0, S.X1 - x, S.Z1 - z])
    rgb *= (1 - 0.3 * np.exp(-np.clip(dd, 0, None) / 0.15))[..., None]
    img = to_image(rgb, 3.0)
    gap = ((z - MZ[1]) % 0.2) > 0.125
    alpha = np.where(gap, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([np.asarray(img), alpha]), 'RGBA')


def paint_back_up(x0, x1, w=160, h=48):
    """The mezzanine's back wall over the deck (U .. U + 2.4): dark panelling to 0.85 m, then the
    restaurant's long window on the night bay: the far shore's towers and their lights, the water
    with the lights' streaks, mullions."""
    x, y = grid(x0, x1, 0.0, 2.4, w, h)
    rng = np.random.default_rng(int(abs(x0)) + 5)
    rgb = np.zeros((h, w, 3)) + np.array([30, 22, 24])
    rgb *= (0.85 + 0.15 * (np.abs((x / 0.6) % 1 - 0.5) < 0.47))[..., None]
    win = (y > 0.9) & (y < 2.3)
    horizon = 1.22
    sky = np.array([10, 14, 34]) + (y - horizon)[..., None] * np.array([-2, -2, -6])
    sea = np.array([6, 10, 24]) + 0 * x[..., None]
    view = np.where((y > horizon)[..., None], sky, sea)
    # the far shore: towers' silhouettes along the horizon, lit windows in them
    hts = np.interp(x, np.arange(x0 - 1, x1 + 1, 0.35),
                    rng.uniform(0.02, 0.32, len(np.arange(x0 - 1, x1 + 1, 0.35))) ** 1.4)
    tower = (y > horizon) & (y < horizon + 0.05 + np.round(hts * 12) / 12 * 0.5)
    view = np.where(tower[..., None], np.array([16, 18, 30]), view)
    lit = tower & (rng.random((h, w)) < 0.22)
    view = np.where(lit[..., None], np.array([210, 190, 130]) * rng.uniform(0.5, 1.0, (h, w, 1)), view)
    shore = (np.abs(y - horizon - 0.02) < 0.025) & (rng.random((h, w)) < 0.5)
    view = np.where(shore[..., None], np.array([230, 210, 160]), view)
    beacon = (np.abs(y - horizon - 0.02 - np.round(hts * 12) / 12 * 0.5) < 0.03) & (rng.random((h, w)) < 0.02)
    view = np.where(beacon[..., None], np.array([255, 60, 50]), view)
    # the lights' streaks on the water
    streak = (y < horizon) & (y > horizon - 0.25) & (rng.random((h, w)) < 0.06 * (1 - (horizon - y) / 0.25))
    view = np.where(streak[..., None], np.array([150, 130, 90]), view)
    rgb = np.where(win[..., None], view, rgb)
    mull = win & ((np.abs((x / 1.6) % 1 - 0.5) > 0.48) | (np.abs(y - 0.92) < 0.03) | (np.abs(y - 2.28) < 0.03))
    rgb = np.where(mull[..., None], np.array([44, 36, 34]), rgb)
    rgb = np.where((np.abs(y - 0.86) < 0.02)[..., None], np.array([120, 96, 60]), rgb)     # a brass rail
    # the tank's glow on the wall behind it
    rgb += (np.exp(-((x - TC[0]) / 2.0) ** 2) * np.exp(-y / 0.7) * 0.6 * ~win)[..., None] * TANK_BLUE * 0.35
    return to_image(rgb, 2.0)


def paint_glass(top, bottom, w=8, h=32, glint=40):
    """A tank's water as its glass shows it (each side quad, fit): lighter at the top."""
    t = (np.arange(h) + 0.5) / h
    c = np.array(top)[None, :] * (1 - t[:, None]) + np.array(bottom)[None, :] * t[:, None]
    rgb = c[:, None, :] * np.ones((1, w, 1))
    rgb[:, 2] += glint * (1 - t[:, None] * 0.6)
    return to_image(rgb, 0)


def paint_ripple(n=32):
    i, j = np.meshgrid(np.arange(n), np.arange(n))
    v = caustics(i / n * 6.283, j / n * 6.283, 1.0, 0.7)
    rgb = np.zeros((n, n, 3)) + np.array([60, 140, 200]) + v[..., None] * np.array([120, 110, 50])
    return to_image(rgb, 0)


def paint_poster(kind, w=22, h=32):
    """A lit fish poster, a picture only: a moon jelly, or a sunfish in a school of sardines."""
    img = Image.new('RGB', (w, h), (14, 40, 90))
    d = ImageDraw.Draw(img)
    for yy in range(h):
        c = (14 + yy // 3, 40 + yy, 90 + yy * 2)
        d.line([(0, yy), (w, yy)], fill=c)
    if kind == 'jelly':
        d.ellipse([5, 7, 17, 15], fill=(220, 200, 250))
        d.rectangle([5, 12, 17, 15], fill=(110, 90, 170))
        for k in range(4):
            d.line([(7 + k * 3, 15), (6 + k * 3, 26)], fill=(200, 180, 240))
    else:
        d.ellipse([4, 9, 15, 22], fill=(170, 180, 190))
        d.polygon([(9, 9), (11, 2), (13, 9)], fill=(150, 160, 175))
        d.polygon([(9, 22), (11, 29), (13, 22)], fill=(150, 160, 175))
        d.point((7, 13), fill=(20, 20, 30))
        rng = np.random.default_rng(2)
        for _ in range(14):
            px, py = int(rng.integers(1, w - 2)), int(rng.integers(2, h - 3))
            d.line([(px, py), (px + 2, py)], fill=(230, 240, 255))
    d.rectangle([0, 0, w - 1, h - 1], outline=(180, 200, 220))
    return img


def paint_map(w=48, h=16):
    """The information desk's lit map: the building's plan in shapes, the route, a dot for here."""
    img = Image.new('RGB', (w, h), (210, 220, 228))
    d = ImageDraw.Draw(img)
    d.rectangle([2, 2, 45, 13], outline=(40, 70, 120))
    for (a, b, c, e, col) in ((4, 4, 14, 11, (90, 150, 220)), (16, 4, 24, 8, (60, 110, 200)), (26, 4, 32, 11, (170, 120, 220)),
                              (34, 4, 43, 8, (60, 170, 200)), (34, 9, 43, 11, (120, 200, 150))):
        d.rectangle([a, b, c, e], fill=col)
    d.line([(5, 12), (44, 12)], fill=(220, 60, 60))
    d.rectangle([8, 11, 9, 12], fill=(220, 40, 40))
    return img


def paint_gate_top(w=8, h=16):
    """A ticket gate's top from above: the ticket slot, the small display."""
    img = Image.new('RGB', (w, h), (64, 70, 82))
    d = ImageDraw.Draw(img)
    d.rectangle([1, 2, 6, 3], fill=(20, 22, 26))
    d.rectangle([2, 10, 5, 13], fill=(30, 60, 70))
    return img


# ---- the recipes

def tank_nodes():
    """The welcome tank: its plinth filling the box, the glass rising to the mezzanine (water to
    WATER_TOP, then the parapet's clear glass to 1 m over the deck), rims, the water's surface,
    rock and coral on its floor, a sardine school turning in it, light shafts."""
    cx, cz = TC
    top = CUT_H if TANK_CUT else WATER_TOP
    n = [box('tank_plinth', (TB[0] + 0.01, -0.02, TB[1] + 0.01), (TB[2] - 0.01, PLINTH, TB[3] - 0.01), 'plinth',
             open=['bottom'], faces={'top': 'plinth_top'},
             decals=[{'id': 'plaque', 'face': 'back', 'material': 'plaque', 'size': [0.6, 0.12], 'at': [0, 0.03]}]),
         at({'id': 'tank_glass', 'op': 'cylinder', 'radius': TR, 'height': top - PLINTH - 0.08 - (0 if TANK_CUT else 0.02),
             'segments': 20, 'caps': False, 'material': 'tank_water'},
            translate=[cx, (top - (0 if TANK_CUT else 0.02) + PLINTH + 0.06) / 2, cz]),
         ring('tank_foot', cx, cz, PLINTH - 0.02, PLINTH + 0.06, TR + 0.03, TR - 0.06, 20, 'steel')]
    if TANK_CUT:
        n.append(ring('tank_cut', cx, cz, top - 0.02, top, TR + 0.02, TR - 0.04, 20, 'cut'))
        sm = Mesh()
        sm.poly([(cx + (TR - 0.04) * math.cos(math.tau * i / 20), top - 0.03, cz + (TR - 0.04) * math.sin(math.tau * i / 20))
                 for i in range(20)], (0, 1, 0), 'water_cut')
        n.append(sm.node('tank_section', 'water_cut'))
    n.append(ring('tank_rim', cx, cz, WATER_TOP - 0.02, U + 0.04, TR + 0.03, TR - 0.06, 20, 'steel'))
    if not TANK_CUT:
        n.append(at({'id': 'tank_parapet', 'op': 'cylinder', 'radius': TR, 'height': CUT_H - 0.06, 'segments': 20,
                     'caps': False, 'material': 'parapet'}, translate=[cx, U + 0.04 + (CUT_H - 0.06) / 2, cz]))
    sm = Mesh()
    sm.poly([(cx + (TR - 0.06) * math.cos(math.tau * i / 20), WATER_TOP - 0.06, cz + (TR - 0.06) * math.sin(math.tau * i / 20))
             for i in range(20)], (0, 1, 0), 'surface')
    n.append(sm.node('tank_surface', 'surface'))
    # rock and coral on the tank's floor (opaque, under 1 m)
    rng = np.random.default_rng(9)
    rocks = []
    for k, (a, rr, s, hgt) in enumerate(((200, 0.8, 0.5, 0.35), (260, 0.9, 0.42, 0.3), (330, 0.75, 0.38, 0.25),
                                         (40, 0.85, 0.45, 0.32), (120, 0.6, 0.35, 0.22), (0, 0.1, 0.4, 0.2))):
        ax, az = cx + rr * math.cos(math.radians(a)), cz + rr * math.sin(math.radians(a))
        rocks.append(at({'id': f'rock_{k}', 'op': 'sphere', 'radius': 1.0, 'rings': 3, 'segments': 6, 'material': 'rock'},
                        translate=[ax, PLINTH + 0.02, az], scale=[s, hgt, s * 0.8], rotate=[0, a, 0]))
    n.append({'id': 'rocks', 'op': 'group', 'children': rocks})
    corals = []
    for k, (a, rr, hgt) in enumerate(((210, 0.75, 0.38), (280, 0.6, 0.3), (60, 0.8, 0.34), (20, 0.45, 0.26))):
        ax, az = cx + rr * math.cos(math.radians(a)), cz + rr * math.sin(math.radians(a))
        corals.append(at({'id': f'coral_{k}', 'op': 'cone', 'radius': 0.07, 'height': hgt, 'segments': 4, 'caps': False,
                          'material': 'coral' if k % 2 else 'coral_b'},
                         translate=[ax, PLINTH + 0.25 + hgt / 2, az], rotate=[12 - k * 8, k * 40, 10]))
    n.append({'id': 'corals', 'op': 'group', 'children': corals})
    # the sardine school: a ring of silver flecks turning round the tank's middle, in two layers,
    # and a few larger fish (all adding light: nothing opaque stands high in the glass)
    fish = Mesh()
    hi = top - 0.2
    for k in range(48 if not TANK_CUT else 16):
        t = k / 48 * math.tau * (1 if not TANK_CUT else 3)
        rr = 0.75 + 0.18 * math.sin(k * 1.7)
        y = PLINTH + 0.6 + (hi - PLINTH - 0.8) * (0.5 + 0.45 * math.sin(t * 1.5 + k * 0.4))
        fx, fz = cx + rr * math.cos(t), cz + rr * math.sin(t)
        hx, hz = -math.sin(t) * 0.11, math.cos(t) * 0.11
        fish.poly([(fx + hx, y, fz + hz), (fx - hx * 0.6, y + 0.035, fz - hz * 0.6), (fx - hx * 0.6, y - 0.035, fz - hz * 0.6)],
                  (hz, 0, -hx), 'sardine')
    for k, (a, y, ln, col) in enumerate(((30, 1.3, 0.3, 'fish_gold'), (160, 1.9, 0.26, 'fish_blue'), (250, 2.5, 0.34, 'fish_gold'),
                                         (300, 1.6, 0.24, 'fish_blue'))):
        if y > hi:
            continue
        fx, fz = cx + 0.5 * math.cos(math.radians(a)), cz + 0.5 * math.sin(math.radians(a))
        fish.poly([(fx + ln / 2, y, fz), (fx - ln / 2, y + 0.1, fz), (fx - ln / 2, y - 0.1, fz)], (0, 0, -1), col)
    n.append(fish.node('fish', 'sardine'))
    if not TANK_CUT:
        shafts = Mesh()
        for (sx, wdt) in ((-0.5, 0.35), (0.25, 0.5), (0.85, 0.3)):
            shafts.poly([(cx + sx - wdt / 2, WATER_TOP - 0.1, cz + 0.6), (cx + sx + wdt / 2, WATER_TOP - 0.1, cz + 0.6),
                         (cx + sx + wdt / 2 + 0.3, PLINTH + 0.4, cz + 0.2), (cx + sx - wdt / 2 + 0.3, PLINTH + 0.4, cz + 0.2)],
                        (0, 0.3, -1), 'shaft')
        n.append(shafts.node('shafts', 'shaft'))
    return n


def gate_nodes():
    """The ticket gates, shut for the night: cabinets with their tops and red stop lamps, closed
    flaps between them, a low glass screen on to the back wall."""
    x0, z0, x1, z1 = PROPS['gates']
    n = []
    cabs = [(z0, z0 + 0.9), (z0 + 1.45, z0 + 2.35), (z0 + 2.9, z0 + 3.8)]
    for k, (a, b) in enumerate(cabs):
        n.append(box(f'gate_{k}', (x0 + 0.02, -0.02, a + 0.01), (x1 - 0.02, 0.98, b), 'gate', open=['bottom'],
                     faces={'top': 'gate_top'},
                     decals=[{'id': 'lamp', 'face': 'back', 'material': 'stop_lamp', 'size': [0.12, 0.06], 'at': [0, 0.36]}]))
    for k, ((_, a), (b, _)) in enumerate(zip(cabs, cabs[1:])):
        n.append(box(f'flap_{k}', (x0 + 0.1, 0.42, a + 0.01), (x1 - 0.1, 0.86, b - 0.01), 'flap'))
    n.append(box('gate_screen', (x0 + 0.12, -0.02, cabs[-1][1] + 0.01), (x1 - 0.12, 0.95, z1 - 0.01), 'screen',
                 open=['bottom', 'front']))
    return n


def desk_nodes():
    """The information desk: a counter with its lit map on the front, leaflet racks on the top."""
    x0, z0, x1, z1 = PROPS['desk']
    n = [box('desk', (x0 + 0.06, -0.02, z0 + 0.08), (x1 - 0.06, 0.9, z1 - 0.05), 'desk', open=['bottom'],
             faces={'top': 'desk_top'},
             decals=[{'id': 'map', 'face': 'back', 'material': 'map', 'size': [1.2, 0.4], 'at': [-0.4, 0.05]}]),
         box('desk_top', (x0 + 0.01, 0.89, z0 + 0.01), (x1 - 0.01, 0.95, z1), 'counter', open=['bottom'])]
    cols = ['leaflet_a', 'leaflet_b', 'leaflet_c', 'leaflet_a']
    for k, xx in enumerate((x0 + 0.4, x0 + 0.75, x1 - 0.8, x1 - 0.45)):
        n.append(box(f'rack_{k}', (xx - 0.12, 0.94, z0 + 0.06), (xx + 0.12, 0.99, z0 + 0.3), cols[k], open=['bottom']))
    return n


def pillar_nodes():
    n = []
    for k, (pid, kind) in enumerate((('pillar_w', 'jelly'), ('pillar_e', 'fish'))):
        x0, z0, x1, z1 = PROPS[pid]
        n.append(box(pid, (x0, -0.02, z0), (x1, CUT_H, z1), 'pillar', open=['bottom'], faces={'top': 'cut'},
                     decals=[{'id': 'poster', 'face': 'back', 'material': f'poster_{kind}', 'size': [0.44, 0.64],
                              'at': [0, 0.06]}]))
    return n


def deck_nodes():
    """The mezzanine's deck (textured slats, the floor below seen between them), its fascia along
    the front, the coping round the tank's top within the tank's box, and the glass railing."""
    x0, z0, x1, z1 = MZ
    y = U
    m = Mesh()
    for name, a, b, c, d in deck_pieces():
        m.quad_y(y, a, b, c, d, 1, name)
    # the coping: the tank's box within the deck, outside the tank's round top
    cx, cz = TC
    ro = TR + 0.03
    for side in (-1, 1):
        xe = TB[0] if side < 0 else TB[2]
        xa = cx + side * math.sqrt(ro ** 2 - (z0 - cz) ** 2)
        arc = [(cx + side * ro * math.cos(t), cz + ro * math.sin(t))
               for t in np.linspace(math.asin((z0 - cz) / ro), math.pi / 2, 7)]
        pts = [(xe, z0), (xa, z0)] + arc[1:] + [(xe, TB[3])]
        m.poly([(px, y, pz) for px, pz in pts], (0, 1, 0), 'coping')
    for a, b in ((x0, TB[0]), (TB[2], x1)):
        m.quad_z(z0, a, b, y - DECK_T, y, -1, 'fascia')
    return [m.node('deck', 'deck_w')]


def rail_nodes():
    """The mezzanine's railing: clear glass panes, steel posts and the handrail at 1 m."""
    x0, z0, x1, z1 = MZ
    y = U
    n = []
    # the railing: clear glass panes, steel posts and the handrail at 1 m
    rail = Mesh()
    posts = []
    for side, (a, b) in (('w', (x0 + 0.02, TB[0] - 0.05)), ('e', (TB[2] + 0.05, x1 - 0.02))):
        rail.quad_z(z0 + 0.14, a, b, y, y + 0.94, -1, 'rail_glass')
        n.append(box(f'handrail_{side}', (a, y + 0.94, z0 + 0.03), (b, y + CUT_H, z0 + 0.11), 'steel'))
        cnt = max(2, int(round((b - a) / 2.2)) + 1)
        for k in range(cnt):
            px = a + 0.1 + (b - a - 0.2) * k / (cnt - 1)
            posts.append(box(f'post_{side}_{k}', (px - 0.025, y - 0.01, z0 + 0.055), (px + 0.025, y + 0.96, z0 + 0.085),
                             'steel', open=['bottom', 'top']))
    n.append(rail.node('rail_glass', 'rail_glass'))
    n.append({'id': 'posts', 'op': 'group', 'children': posts})
    return n


def table_nodes():
    """The restaurant's tables at the railing: two small round tables laid with white cloths in
    each footprint, a chair tucked behind each."""
    n = []
    for tid in ('tables_w', 'tables_e'):
        x0, z0, x1, z1 = UPROPS[tid]
        zc = (z0 + z1) / 2 - 0.03
        for k, xc in enumerate((x0 + 0.3, x1 - 0.3)):
            n.append(at({'id': f'{tid}_{k}_cloth', 'op': 'cylinder', 'radius': 0.22, 'height': 0.26, 'segments': 8,
                         'material': 'cloth'}, translate=[xc, U + 0.62, zc]))
            n.append(at({'id': f'{tid}_{k}_foot', 'op': 'cylinder', 'radius': 0.05, 'height': 0.5, 'segments': 4,
                         'caps': False, 'material': 'steel'}, translate=[xc, U + 0.24, zc]))
            n.append(at({'id': f'{tid}_{k}_lamp', 'op': 'cylinder', 'radius': 0.035, 'height': 0.09, 'segments': 5,
                         'material': 'candle'}, translate=[xc, U + 0.79, zc]))
            n.append(box(f'{tid}_{k}_chair', (xc - 0.17, U + 0.44, z1 - 0.12), (xc + 0.17, U + 0.84, z1 - 0.06), 'chair'))
    return n


def booth_nodes():
    """The two booths against the back wall (the hiding places): plum velvet benches facing over a
    small table, their high backs cut at 1 m."""
    n = []
    for hid in ('booth_w', 'booth_e'):
        x0, z0, x1, z1 = HIDES[hid]
        y = U
        for side, (a, b) in (('l', (x0 + 0.02, x0 + 0.4)), ('r', (x1 - 0.4, x1 - 0.02))):
            sa, sb = (a + 0.03, b) if side == 'l' else (a, b - 0.03)
            n.append(box(f'{hid}_seat_{side}', (sa, y - 0.01, z0 + 0.06), (sb, y + 0.45, z1 - 0.01), 'velvet',
                         open=['bottom', 'front']))
            ba, bb = (a, a + 0.1) if side == 'l' else (b - 0.1, b)
            n.append(box(f'{hid}_back_{side}', (ba, y + 0.44, z0 + 0.02), (bb, y + CUT_H, z1 - 0.01), 'velvet_dark',
                         open=['bottom', 'front'], faces={'top': 'cut'}))
        n.append(box(f'{hid}_table', (x0 + 0.44, y + 0.66, z0 + 0.06), (x1 - 0.44, y + 0.71, z1 - 0.02), 'wood',
                     open=['front']))
    return n


def beyond_extra(kind):
    """Things beyond the doorways: the street's kerb, the catwalk's rail, the pedestrian deck's
    railing."""
    def street(m, lo, hi, a, b, y, s):
        m.quad_z(b - 0.01, lo, hi, y, y + 0.06, -1, 'kerb')
    return None


def room_recipe():
    tiles = S.floor_tiles(4, 2)
    m = {
        'cut': {'color': SECTION_CUT, 'class': 'emissive'},
        'section': mat_tex(P + 'section', '#2e3444', bits=4),
        'end': {'color': '#2a2e3a'}, 'reveal': {'color': '#30343e'},
        'door_glow': {'color': '#5a6a80', 'class': 'emissive'},
        'threshold': {'color': '#181c26', 'class': 'emissive'},
        'beyond_wall': {'color': '#141824', 'class': 'emissive'},
        'street_floor': {'color': '#1e2230', 'class': 'emissive'}, 'street_wall': {'color': '#161a26', 'class': 'emissive'},
        'kerb': {'color': '#4a4e58', 'class': 'emissive'},
        'great_floor': {'color': '#1c4282', 'class': 'emissive'}, 'great_wall': {'color': '#16305c', 'class': 'emissive'},
        'catwalk_floor': {'color': '#22344e', 'class': 'emissive'}, 'catwalk_wall': {'color': '#16243a', 'class': 'emissive'},
        'outdeck_floor': {'color': '#2a2c3a', 'class': 'emissive'}, 'outdeck_wall': {'color': '#1a1c2a', 'class': 'emissive'},
        'back_low': {'color': '#1a1c24', 'class': 'emissive'},
        'plinth': {'color': '#2a2e3a'}, 'plinth_top': {'color': '#3a404e'},
        'plaque': {'color': '#8a9ab0', 'class': 'emissive'},
        'tank_water': dict(mat_tex(P + 'tank_water', '#1c5aa0', bits=4), blend='half', double_sided=True),
        'parapet': {'color': '#4a7090', 'class': 'emissive', 'blend': 'quarter', 'double_sided': True},
        # agent W: the tank's surface ripples (a coloured tile: these are lit by the recipe's own light)
        'water_cut': {'color': '#2a78c0', 'class': 'emissive', 'texture': wateranim.texture(WATER_RIPPLE)},
        'surface': {'color': '#3a90d0', 'class': 'emissive', 'texture': wateranim.texture(WATER_RIPPLE), 'blend': 'half'},
        'steel': {'color': '#7c8496'},
        'rock': {'color': '#2c3a50'}, 'coral': {'color': '#c06aa8'}, 'coral_b': {'color': '#8a6ad0'},
        'sardine': {'color': '#9ab4d0', 'class': 'emissive', 'blend': 'add', 'double_sided': True},
        'fish_gold': {'color': '#c0a040', 'class': 'emissive', 'blend': 'add', 'double_sided': True},
        'fish_blue': {'color': '#4060c0', 'class': 'emissive', 'blend': 'add', 'double_sided': True},
        'shaft': {'color': '#1e4060', 'class': 'emissive', 'blend': 'add'},
        'gate': {'color': '#5a6070'}, 'gate_top': mat_tex(P + 'gate_top', '#40464e', bits=4, emissive=False),
        'stop_lamp': {'color': '#e03030', 'class': 'emissive'}, 'flap': {'color': '#8a3034'},
        'screen': {'color': '#5a7890', 'blend': 'half'},
        'desk': {'color': '#3a3640'}, 'counter': {'color': '#6a6670'}, 'desk_top': {'color': '#6a6670'},
        'map': mat_tex(P + 'map', '#a0b0c0'),
        'leaflet_a': {'color': '#5a8ac0'}, 'leaflet_b': {'color': '#c0b060'}, 'leaflet_c': {'color': '#70b090'},
        'pillar': {'color': '#3a404e'},
        'poster_jelly': mat_tex(P + 'poster_jelly', '#5060a0'), 'poster_fish': mat_tex(P + 'poster_fish', '#4070a0'),
        'coping': {'color': '#2c4a6c', 'class': 'emissive'},
        'fascia': {'color': '#20232c', 'class': 'emissive'},
        'rail_glass': {'color': '#8ab0c8', 'blend': 'quarter'},
        'cloth': {'color': '#c8ccd4'}, 'candle': {'color': '#e0c890'}, 'chair': {'color': '#4a3428'},
        'velvet': {'color': '#6a2a4c'}, 'velvet_dark': {'color': '#58223e'}, 'wood': {'color': '#5a3e2c'},
    }
    for name, *_ in tiles:
        m[name] = mat_tex(P + name, '#20283a')
    for name, *_ in deck_pieces():
        m[name] = mat_tex(P + name, '#2a3040')
    m['back_w'] = mat_tex(P + 'back_w', '#1e1a20')
    m['back_e'] = mat_tex(P + 'back_e', '#1e1a20')
    n = [S.floor_mesh(tiles), S.front_wall(), S.end_wall('w'), S.end_wall('e'),
         S.back_wall([(0.0, U, [(S.X0, S.X1, 'back_low')]), (U, S.H, [(S.X0, 0.0, 'back_w'), (0.0, S.X1, 'back_e')])])]
    n.append(S.beyond('main', 1.6, far='street_floor', wall='street_wall', extra=beyond_extra('main')))
    n.append(S.beyond('great', 1.6, far='great_floor', wall='great_wall'))
    n.append(S.beyond('catwalk', 1.6, far='catwalk_floor', wall='catwalk_wall'))
    n.append(S.beyond('deck', 1.6, far='outdeck_floor', wall='outdeck_wall'))
    n += deck_nodes()
    props = tank_nodes() + gate_nodes() + desk_nodes() + pillar_nodes() + rail_nodes() + table_nodes() + booth_nodes()
    lighting = {'direction': [-0.3, 0.8, -0.5], 'ambient': 0.28, 'diffuse': 0.18}
    lit = dict(lighting, lights=lights(), refine={'tolerance': 22, 'max_added': 200})
    # two recipes: the shell (the World Kit's stand-in for the cell is made from it: under 700
    # triangles) and the props, lit by the room's point lights
    return [recipe(P + 'room', m, n, lighting, 700), recipe(P + 'props', m, props, lit, 1700)]


# ---- agent W: the moving water (NOTES_W.md)

WATER_RIPPLE = wateranim.key('w_ripple', '#d0f0ff', base='#3c8cc8')


def wwater_recipe():
    """The caustic net the welcome tank throws on the floor in its light boxes, and the great
    tank's through the east door, lit by lights of its own."""
    ov = wateranim.Overlay(P + 'wwater')
    ov.material('net', 'w_caustic')
    for (x0, z0, x1, z1) in TANK_LIGHTS + [DOOR_LIGHT]:
        ov.floor('net', 0.03, max(x0, S.X0) + 0.02, min(x1, S.X1) - 0.02, max(z0, S.Z0) + 0.02, min(z1, S.Z1) - 0.02,
                 nx=max(1, round((x1 - x0) / 1.6)), nz=max(1, round((z1 - z0) / 1.6)))
    ov.light((TC[0], 1.0, TC[1]), '#50b0ff', 2.6, 3.8, id='tank')
    dz = (DOOR_LIGHT[1] + DOOR_LIGHT[3]) / 2
    ov.light((S.X1 + 0.4, 1.0, dz), '#4a78ff', 1.6, 2.4, id='door')
    return ov.recipe(ART, refine={'tolerance': 20, 'max_added': 48})


def main():
    art = {}
    for name, x0, x1, z0, z1 in S.floor_tiles(4, 2):
        art[P + name] = paint_floor_tile(x0, x1, z0, z1)
    for name, x0, x1, z0, z1 in deck_pieces():
        art[P + name] = paint_deck(x0, x1, z0, z1)
    art[P + 'back_w'] = paint_back_up(S.X0, 0.0)
    art[P + 'back_e'] = paint_back_up(0.0, S.X1)
    art[P + 'poster_jelly'] = paint_poster('jelly')
    art[P + 'poster_fish'] = paint_poster('fish')
    art[P + 'map'] = paint_map()
    keys = list(art)
    for k, img in zip(keys, quantise_together([art[k] for k in keys])):
        art[k] = img
    art[P + 'section'] = paint_section(S.XO0, S.XO1)
    art[P + 'tank_water'] = paint_glass((26, 80, 150), (40, 130, 210))
    art[P + 'ripple'] = paint_ripple()
    art[P + 'gate_top'] = paint_gate_top()
    for name, img in art.items():
        save_png(img, ART / f'{name}.png')
    recs = room_recipe()
    for rec in recs:
        wateranim.finish(rec, ART)          # agent W: the tank's ripple tile (in the materials both share)
    for rec in recs + [wwater_recipe(), collision(G.ROOM, P + 'room_col')]:     # agent W: wwater
        write_json(OUT / f'{rec["name"]}.asset.json', rec)
    placements = [{'id': P + 'room', 'asset': P + 'room', 'position': [0, 0, 0], 'collision': P + 'room_col'},
                  {'id': P + 'props', 'asset': P + 'props', 'position': [0, 0, 0], 'collision': 'none'},
                  {'id': P + 'wwater', 'asset': P + 'wwater', 'position': [0, 0, 0], 'collision': 'none'}]  # agent W
    data = {'format': 'after-hours-placements', 'version': 1, 'room': 'aq_hall', 'placements': placements}
    write_json(HERE / 'aq_hall.placements.json' if '--placements' in sys.argv else OUT / 'draft.placements.json', data)


if __name__ == '__main__':
    main()
