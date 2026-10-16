#!/usr/bin/env python3
"""Stage 2, the shop floor (7F), dressed: writes its Asset Kit recipes, draws their textures and
writes the room's placements.

    python3 carts/afterhours/rooms/shopfloor/dress_shopfloor.py [--no-placements]

Writes, beside itself:
  sf_floor.asset.json       the floor (painted, with the escalator well cut out of it), the back
                            wall (painted) with its bag shelves, the end walls and the doorways'
                            lintels, the front wall's cut face (painted: the store's glass skin
                            with the city in it), the three mannequins, the staff stair's landing
                            and the lift's vestibule beyond their doorways; lit by ROOM_LIGHTS
  sf_floor_col.asset.json   its collision: the floor, the walls without tops, the well, the
                            counters, the plinths
  sf_escalators.asset.json  the well: its glass balustrade, the two stopped escalators going down
                            to 6F, the floor below (its own recipe, lit at its corners only, so no
                            light refines its glass)
  sf_counters.asset.json    the four glass counters and the watch counter, lit from inside (the
                            same, for the same reason)
  shopfloor.placements.json the placements (replace the greybox's)
  art/*.png                 the floor and the back wall (painted as ROOM_LIGHTS light them), the
                            front's face, the counters' trays, the signs

PLAN.md is the room's floor plan (the level lead's); this keeps what it says must stay: the well
(its sides cut cones), the counters glass and low, the three mannequins (opaque, cut at 1 m), the
card's place and the watch counter, the camera's corner, the doorways open, the front aisle and
the back lane clear, the front cut at 1 m. The light is ../passage/diorama.py's method: one list
for the kit's bake and for the painting of the floor and the back wall. Everything named here is
fictional. Needs Pillow and NumPy.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent / 'passage'))
from diorama import (CUT, WALL_H, Mesh, at, blob, box, collision_recipe, grid_floor, grid_wall_z, group,  # noqa: E402
                     hex_rgb, painted_floor, painted_wall_z, quantise_together, r, recipe, shade, smoothstep,
                     soft_rect, to_array, write_json)

ART = HERE / 'art'
P = 'sf_'

# ---- the plan (PLAN.md and shopfloor.play.json)
X0, X1 = -12.0, 12.0
Z0, Z1 = -4.75, 4.75
T = 0.25
XO0, XO1, ZO0, ZO1 = X0 - T, X1 + T, Z0 - T, Z1 + T
SLAB = 0.4
WELL = (-2.0, -1.2, 2.0, 1.4)
COUNTERS = [(-9.0, -2.6, -6.0, -1.9), (-9.0, 1.0, -6.0, 1.7), (5.0, -2.6, 8.4, -1.9), (5.0, 1.0, 8.4, 1.7)]
WATCH = (8.6, -4.75, 11.0, -4.3)
MANNEQUINS = [(-5.2, 0.0), (5.0, 4.0), (10.0, -0.5)]
STAIR_DOOR = (1.6, 2.8)        # west wall, z
LIFT_DOOR = (8.4, 9.8)         # back wall, x
LINTEL = 2.1
CAMERA = (11.5, 4.6)
TABLE = (2.6, -0.75, 3.9, 0.35)    # a low table of knits: x0, z0, x1, z1
CASE_H, BODY_H = 0.95, 0.6     # the counters: their glass tops, and their bodies under the glass
LOWER = -4.4                   # 6F's floor, at the well's bottom

# ---- the light
AMBIENT, DIFFUSE = 0.06, 0.04
DIRECTION = [0.0, 1.0, -0.4]
CASE_LIGHT = '#dcecff'
SPOT = '#ffd6a0'


def room_lights():
    out = [{'id': f'case_{k}', 'at': [r((a + c) / 2), 0.78, r((b + d) / 2)], 'color': CASE_LIGHT, 'intensity': 1.6,
            'range': 3.0} for k, (a, b, c, d) in enumerate(COUNTERS + [WATCH])]
    out += [{'id': f'spot_{k}', 'at': [x, 2.6, z - 0.4], 'color': SPOT, 'intensity': 2.6, 'range': 3.4,
             'shadows': True, 'radius': 0.15} for k, (x, z) in enumerate(MANNEQUINS)]
    out += [
        {'id': 'night', 'at': [0.0, 7.0, 0.0], 'color': '#7080b0', 'intensity': 0.6, 'range': 18.0},
        {'id': 'lift_lamp', 'at': [9.1, 2.3, 4.5], 'color': '#ff3828', 'intensity': 1.0, 'range': 2.2},
        {'id': 'camera', 'at': [CAMERA[0], 2.2, 4.4], 'color': '#ff2a1a', 'intensity': 0.7, 'range': 1.5},
        {'id': 'stair', 'at': [X0 - 1.0, 1.6, 2.2], 'color': '#c4f4d8', 'intensity': 1.8, 'range': 3.4,
         'shadows': True, 'radius': 0.25},
        {'id': 'shelves_w', 'at': [-8.3, 2.2, 4.1], 'color': '#ffe2b8', 'intensity': 1.2, 'range': 2.6},
        {'id': 'shelves_e', 'at': [-2.4, 2.2, 4.1], 'color': '#ffe2b8', 'intensity': 1.0, 'range': 2.6},
        {'id': 'well', 'at': [0.0, -0.6, 0.1], 'color': '#6c8cd8', 'intensity': 0.8, 'range': 3.0},
    ]
    return out


def lights_named(*prefixes):
    return [l for l in room_lights() if l['id'].startswith(prefixes)]


def blockers():
    """The painted shadows' casters, at their height in the story: the counters' bodies (the glass
    over them lets light through), the mannequins, the walls with their doorways."""
    out = [(a, -1, b, c, BODY_H, d) for a, b, c, d in COUNTERS + [WATCH]]
    out += [(x - 0.22, 0, z - 0.15, x + 0.22, 1.8, z + 0.15) for x, z in MANNEQUINS]
    out.append((TABLE[0], 0.66, TABLE[1], TABLE[2], 0.72, TABLE[3]))
    out += [(XO0, -1, ZO0, X0, 4, STAIR_DOOR[0]), (XO0, -1, STAIR_DOOR[1], X0, 4, ZO1),
            (XO0, LINTEL, STAIR_DOOR[0], X0, 4, STAIR_DOOR[1]), (X1, -1, ZO0, XO1, 4, ZO1)]
    return out


# ---- the floor

FLOOR_X = [XO0, -4.0833, 4.0833, XO1]
FLOOR_Z = [ZO0, 0.0, ZO1]
FLOOR_TEX = (196, 120)
ZONES = [((-10.4, -3.1, -4.5, 2.25), np.array([96, 34, 44])),      # accessories: a wine carpet
         ((4.3, -3.1, 9.2, 2.25), np.array([92, 104, 120]))]        # watches: a dove grey carpet


def floor_base(x, z):
    """In white light: cream marble in the aisles (polished, with a soft vein and a darker band
    round the well), the boutiques' carpets edged in brass, the lift's landing plate."""
    rng = np.random.default_rng(71)
    h, w = x.shape
    vein = np.sin(x * 1.7 + np.sin(z * 2.3 + x * 0.4) * 2.0) * 0.5 + 0.5
    base = np.zeros((h, w, 3)) + np.array([206, 198, 182])
    base -= (vein ** 6)[..., None] * np.array([26, 26, 24])
    ix, iz = np.floor(x / 1.2), np.floor(z / 1.2)
    var = (np.sin(ix * 12.9898 + iz * 78.233) * 43758.5453) % 1.0
    base *= (0.96 + 0.06 * var)[..., None]
    joint = (np.abs((x / 1.2) % 1.0 - 0.5) > 0.49) | (np.abs((z / 1.2) % 1.0 - 0.5) > 0.49)
    base -= joint[..., None] * np.array([20, 20, 20])
    wx0, wz0, wx1, wz1 = WELL
    band = soft_rect(x, z, wx0 - 0.5, wx1 + 0.5, wz0 - 0.5, wz1 + 0.5, 0.01) > 0.5
    base = np.where(band[..., None], np.array([110, 104, 98]) * (0.95 + 0.1 * var[..., None]), base)
    for (a, b, c, d), col in ZONES:
        inside = (x > a) & (x < c) & (z > b) & (z < d)
        pile = col * (0.92 + 0.16 * rng.random((h, w)))[..., None]
        base = np.where(inside[..., None], pile, base)
        edge = inside & ((x < a + 0.05) | (x > c - 0.05) | (z < b + 0.05) | (z > d - 0.05))
        base = np.where(edge[..., None], np.array([200, 168, 96]), base)
    plate = (x > LIFT_DOOR[0] - 0.1) & (x < LIFT_DOOR[1] + 0.1) & (z > Z1 - 0.35)
    base = np.where(plate[..., None], np.array([150, 150, 154]) + (((x * 12) % 1.0) < 0.5)[..., None] * 16, base)
    base += (rng.random((h, w)) - 0.5)[..., None] * 5
    return base


def floor_paint(x, z):
    y = np.zeros_like(x)
    lights = room_lights()
    rgb = floor_base(x, z) * shade(x, y, z, (0, 1, 0), lights, AMBIENT, DIFFUSE, DIRECTION, blockers())
    # the counters' glass seen in the polished marble: their lit trays, toward the camera
    t30 = math.tan(math.radians(30))
    carpet = np.zeros(x.shape, dtype=bool)
    for (a, b, c, d), _ in ZONES:
        carpet |= (x > a) & (x < c) & (z > b) & (z < d)
    gloss = np.where(carpet, 0.15, 1.0)
    for (a, b, c, d) in COUNTERS + [WATCH]:
        g = soft_rect(x, z, a + 0.1, c - 0.1, b - 0.95 * t30 - 0.05, b - 0.62 * t30, 0.2)
        rgb += (g * gloss * 0.2)[..., None] * hex_rgb(CASE_LIGHT)
    for k, (mx, mz) in enumerate(MANNEQUINS):
        g = blob(x, z, mx, mz - 2.6 * t30 - 0.4, 0.35, 0.25)
        rgb += (g * gloss * 0.25)[..., None] * hex_rgb(SPOT)
    g = soft_rect(x, z, LIFT_DOOR[0] + 0.5, LIFT_DOOR[1] - 0.5, Z1 - 2.3 * t30 - 0.1, Z1 - 2.2 * t30, 0.25)
    rgb += (g * 0.3)[..., None] * np.array([255, 60, 40])
    return rgb


# ---- the back wall

WALL_X = [XO0, 0.0, XO1]
WALL_TEX = (240, 52)
SHELVES = [(-11.2, -5.6), (-4.6, -2.9)]       # bag shelves on the back wall: x
PANEL = (2.6, 7.4)                           # the watch house's lit panel: x


def wall_base(x, y):
    """In white light: pale grey-violet plaster, a dark skirting, the bag shelves' backs (lit
    niches), the watch house's panel (a dial and a band of light), the staff door's red sign."""
    rng = np.random.default_rng(73)
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array([178, 172, 182])
    base -= ((np.abs((x / 1.5) % 1.0 - 0.5) > 0.49))[..., None] * np.array([24, 24, 24])
    base = np.where((y < 0.12)[..., None], np.array([60, 58, 64]), base)
    for a, b in SHELVES:
        niche = (x > a) & (x < b) & (y > 0.5) & (y < 2.2)
        base = np.where(niche[..., None], np.array([226, 214, 196]), base)
        base = np.where((niche & (np.abs(x - (a + b) / 2) % 1.4 < 0.03))[..., None], np.array([150, 130, 100]), base)
    a, b = PANEL
    panel = (x > a) & (x < b) & (y > 0.6) & (y < 2.15)
    base = np.where(panel[..., None], np.array([24, 30, 46]), base)
    d = np.hypot((x - (a + b) / 2) / 1.0, (y - 1.42) / 0.55)
    base = np.where((panel & (np.abs(d - 0.8) < 0.07))[..., None], np.array([214, 190, 120]), base)
    hand = panel & (np.abs(x - (a + b) / 2) < 0.03) & (y > 1.42) & (y < 1.82)
    hand |= panel & (np.abs(y - 1.42) < 0.03) & (x > (a + b) / 2) & (x < (a + b) / 2 + 0.3)
    base = np.where(hand[..., None], np.array([230, 220, 200]), base)
    base = np.where((panel & (y > 0.68) & (y < 0.76))[..., None], np.array([236, 240, 250]), base)
    sign = (x > LIFT_DOOR[0] + 0.25) & (x < LIFT_DOOR[1] - 0.25) & (y > 2.16) & (y < 2.34)
    base = np.where(sign[..., None], np.array([210, 40, 36]), base)
    base += (rng.random((h, w)) - 0.5)[..., None] * 5
    return base


def wall_paint(x, y, z):
    rgb = wall_base(x, y) * shade(x, y, z, (0, 0, -1), room_lights(), AMBIENT, DIFFUSE, DIRECTION, blockers())
    a, b = PANEL
    lit = (x > a) & (x < b) & (y > 0.6) & (y < 2.15)
    sign = (x > LIFT_DOOR[0] + 0.25) & (x < LIFT_DOOR[1] - 0.25) & (y > 2.16) & (y < 2.34)
    glow = wall_base(x, y)
    return np.where((lit | sign)[..., None], glow * 0.9 + 6, rgb)


def front_face(a, b, w=240, h=20):
    """The front wall's face, the store's skin in section: the floor slab pale (cut), above it the
    dark glass of the curtain wall to the cut, with the city's lights in it and a mullion every
    1.5 m."""
    xs = a + (np.arange(w) + 0.5) / w * (b - a)
    ys = CUT - (np.arange(h) + 0.5) / h * (CUT + SLAB)
    x, y = np.meshgrid(xs, ys)
    rng = np.random.default_rng(int(a * 10) + 300)
    rgb = np.zeros((h, w, 3)) + np.array([18, 26, 52])
    rgb += ((CUT - y) / CUT)[..., None] * np.array([8, 12, 26])
    dots = rng.random((h, w))
    rgb = np.where(((dots > 0.985) & (y > 0.1))[..., None], np.array([250, 210, 140]), rgb)
    rgb = np.where(((dots < 0.008) & (y > 0.1))[..., None], np.array([160, 200, 255]), rgb)
    rgb = np.where((np.abs(((x + 0.75) / 1.5) % 1.0 - 0.5) > 0.47)[..., None], np.array([96, 104, 124]), rgb)
    rgb = np.where((y < 0.08)[..., None], np.array([140, 154, 180]), rgb)
    rgb = np.where((np.abs(y - 0.08) < 0.035)[..., None], np.array([170, 182, 206]), rgb)
    return Image.fromarray(to_array(rgb, 4.0), 'RGB')


# ---- small textures

def tray(kind, w=48, h=12):
    """A counter's tray under its glass, lit: watches on navy velvet, or folded scarves and small
    leather goods on cream."""
    if kind == 'watch':
        img = Image.new('RGB', (w, h), (22, 28, 58))
        d = ImageDraw.Draw(img)
        for i in range(6):
            cx = 5 + i * 8 + (2 if i % 2 else 0)
            for cy in (3, 8):
                c = (200, 196, 184) if (i + cy) % 3 else (214, 176, 100)
                d.rectangle([cx - 1, cy - 1, cx, cy], fill=c)
                d.line([(cx - 3, cy), (cx - 2, cy)], fill=(60, 50, 44))
                d.line([(cx + 1, cy), (cx + 2, cy)], fill=(60, 50, 44))
        return img
    img = Image.new('RGB', (w, h), (232, 222, 204))
    d = ImageDraw.Draw(img)
    cols = [(196, 60, 80), (60, 110, 180), (230, 180, 60), (90, 150, 100), (150, 80, 160), (220, 120, 90)]
    for i in range(7):
        x0 = 1 + i * 7
        d.rectangle([x0, 1, x0 + 5, 5], fill=cols[i % len(cols)])
        d.rectangle([x0, 7, x0 + 5, 10], fill=(90, 60, 40) if i % 2 else (40, 36, 34))
    return img


def knits():
    """Folded knits on a table, in piles by colour, seen from above."""
    w, h = 26, 18
    img = Image.new('RGB', (w, h), (110, 78, 54))
    d = ImageDraw.Draw(img)
    cols = [(200, 190, 170), (150, 40, 50), (60, 70, 110), (190, 150, 90), (90, 110, 80), (220, 210, 200)]
    for j in range(2):
        for i in range(3):
            x0, y0 = 2 + i * 8, 2 + j * 8
            c = cols[(i + j * 3) % len(cols)]
            d.rectangle([x0, y0, x0 + 6, y0 + 6], fill=c)
            d.line([(x0, y0 + 3), (x0 + 6, y0 + 3)], fill=tuple(int(v * 0.8) for v in c))
    return img


def section_face(w, h, fill, ring):
    img = Image.new('RGB', (w, h), fill)
    d = ImageDraw.Draw(img)
    for k in range(-h, w, 4):
        d.line([(k, h - 1), (k + h - 1, 0)], fill=tuple(int(c * 0.93) for c in fill))
    d.rectangle([0, 0, w - 1, h - 1], outline=ring)
    return img


def lower_floor():
    """6F at the well's bottom, in its own night: a dim marble with a pool of light."""
    w, h = 32, 24
    xs = (np.arange(w) + 0.5) / w
    zs = (np.arange(h) + 0.5) / h
    x, z = np.meshgrid(xs, zs)
    rgb = np.zeros((h, w, 3)) + np.array([40, 46, 70])
    rgb += np.exp(-((x - 0.6) ** 2 + (z - 0.5) ** 2) / 0.08)[..., None] * np.array([60, 70, 110])
    rgb -= ((np.abs((x * 4) % 1.0 - 0.5) > 0.46) | (np.abs((z * 3) % 1.0 - 0.5) > 0.46))[..., None] * 10
    return Image.fromarray(to_array(rgb, 4.0), 'RGB')


def tread():
    w, h = 16, 16
    img = Image.new('RGB', (w, h), (120, 124, 132))
    d = ImageDraw.Draw(img)
    for xx in range(0, w, 2):
        d.line([(xx, 0), (xx, h - 1)], fill=(92, 96, 104))
    d.rectangle([0, 0, w - 1, 1], fill=(220, 190, 60))
    return img


def draw_art():
    ART.mkdir(exist_ok=True)
    w, h = FLOOR_TEX
    paintings, names = [], []
    for j, (za, zb) in enumerate(zip(FLOOR_Z, FLOOR_Z[1:])):
        for i, (xa, xb) in enumerate(zip(FLOOR_X, FLOOR_X[1:])):
            x, y, z = grid_floor(xa, xb, za, zb, w, h)
            paintings.append(to_array(floor_paint(x, z)))
            names.append(f'floor_{j}{i}')
    ww, wh = WALL_TEX
    for k, (a, b) in enumerate(zip(WALL_X, WALL_X[1:])):
        x, y, z = grid_wall_z(a, b, 0.0, WALL_H, ww, wh, Z1)
        paintings.append(to_array(wall_paint(x, y, z)))
        names.append(f'wall_{k}')
    for name, img in zip(names, quantise_together(paintings)):
        img.save(ART / f'{name}.png')
    for k, (a, b) in enumerate(zip(WALL_X, WALL_X[1:])):
        front_face(a, b).save(ART / f'front_{k}.png')
    tray('watch').save(ART / 'tray_watch.png')
    tray('scarf').save(ART / 'tray_scarf.png')
    knits().save(ART / 'knits.png')
    section_face(16, 16, (140, 154, 180), (88, 96, 116)).save(ART / 'cut.png')
    lower_floor().save(ART / 'lower.png')
    tread().save(ART / 'tread.png')


# ---- sf_floor

def materials():
    m = {
        'cut': {'color': '#8c9ab4', 'class': 'emissive'},
        'cut_tex': {'color': '#8c9ab4', 'class': 'emissive', 'texture': {'image': 'art/cut.png', 'bits': 4, 'projection': 'fit'}},
        'end_wall': {'color': '#aaa4b0'},
        'lintel': {'color': '#5c5a64'},
        'door_light': {'color': '#ffe0c0', 'class': 'emissive'},
        'shelf': {'color': '#d8ccb8'},
        'bag_a': {'color': '#8a3a34'}, 'bag_b': {'color': '#2c2a30'}, 'bag_c': {'color': '#c8a070'},
        'bag_d': {'color': '#40507a'},
        'plinth': {'color': '#d0ccc4'},
        'table': {'color': '#6a4a34'}, 'table_base': {'color': '#3a2c24'},
        'knits': {'color': '#c0a888', 'texture': {'image': 'art/knits.png', 'bits': 4, 'projection': 'fit'}},
        'skin': {'color': '#e8e4dc'},
        'dress': {'color': '#8c2c3c'}, 'coat': {'color': '#b08a5a'}, 'trousers': {'color': '#2c3248'},
        'jacket': {'color': '#3a4466'},
        'landing': {'color': '#8a8c90'}, 'step': {'color': '#a4a6aa'}, 'stair_wall': {'color': '#9a9ca4'},
        'lift_floor': {'color': '#7c7e84'}, 'lift_door': {'color': '#a8acb4'}, 'lift_frame': {'color': '#5a5c64'},
        'lift_panel': {'color': '#ff6040', 'class': 'emissive'},
    }
    for j in range(2):
        for i in range(3):
            m[f'floor_{j}{i}'] = {'color': '#8a8070', 'class': 'emissive',
                                  'texture': {'image': f'art/floor_{j}{i}.png', 'bits': 8, 'projection': 'fit'}}
    for k in range(2):
        m[f'wall_{k}'] = {'color': '#706c74', 'class': 'emissive',
                          'texture': {'image': f'art/wall_{k}.png', 'bits': 8, 'projection': 'fit'}}
        m[f'front_{k}'] = {'color': '#1c2440', 'class': 'emissive',
                           'texture': {'image': f'art/front_{k}.png', 'bits': 4, 'projection': 'fit'}}
    return m


def mannequin(k, x, z):
    """A mannequin on its plinth, cut at 1 m like everything in play: legs, and what she wears
    up to the cut (a long dress, a coat, a suit), its cut drawn pale."""
    n = [box(f'mq{k}_plinth', (x - 0.3, -0.02, z - 0.3), (x + 0.3, 0.12, z + 0.3), 'plinth', open=['bottom'])]
    if k == 0:       # a long dress to the floor
        n.append({'id': f'mq{k}_dress', 'op': 'lathe', 'profile': [[0.28, 0.0], [0.2, 0.5], [0.15, 0.87]],
                   'segments': 8, 'material': 'dress', 'faces': {'top': 'cut', 'bottom': 'dress'},
                  'transform': {'translate': [x, 0.11, z]}})
        return n
    trousers = 'trousers'
    for s in (-1, 1):
        n.append(box(f'mq{k}_leg_{s + 1}', (x + s * 0.11 - 0.06, 0.1, z - 0.06), (x + s * 0.11 + 0.06, 0.78, z + 0.06),
                     'skin' if k == 1 else trousers, open=['bottom']))
    if k == 1:       # a camel coat over bare legs
        n.append({'id': f'mq{k}_coat', 'op': 'lathe', 'profile': [[0.25, 0.0], [0.21, 0.3], [0.17, 0.5]],
                  'segments': 8, 'material': 'coat', 'faces': {'top': 'cut', 'bottom': 'coat'},
                  'transform': {'translate': [x, 0.49, z]}})
    else:            # a suit: the jacket's hem
        n.append({'id': f'mq{k}_jacket', 'op': 'lathe', 'profile': [[0.21, 0.0], [0.19, 0.12], [0.17, 0.24]],
                  'segments': 8, 'material': 'jacket', 'faces': {'top': 'cut', 'bottom': 'jacket'},
                  'transform': {'translate': [x, 0.75, z]}})
    return n


def floor_nodes():
    f = Mesh()
    painted_floor(f, FLOOR_X, FLOOR_Z, [WELL], 'floor_{}{}')
    for k, (a, b) in enumerate(zip(WALL_X, WALL_X[1:])):
        f.quad(a, -SLAB, ZO0, b, CUT, ZO0, (0, 0, -1), f'front_{k}',        # hand UVs: the mesh has them
               (lambda a, b: lambda p: ((p[0] - a) / (b - a), (CUT - p[1]) / (CUT + SLAB)))(a, b))
    n = [f.node('floor', 'floor_00')]
    w = Mesh()
    for a, b in ((XO0, LIFT_DOOR[0]), (LIFT_DOOR[1], XO1)):
        painted_wall_z(w, WALL_X, a, b, 0, WALL_H, Z1, 'wall_{}', WALL_H)
    painted_wall_z(w, WALL_X, LIFT_DOOR[0], LIFT_DOOR[1], LINTEL, WALL_H, Z1, 'wall_{}', WALL_H)
    w.quad(XO0, WALL_H, Z1, XO1, WALL_H, ZO1, (0, 1, 0), 'cut')
    w.quad(LIFT_DOOR[0], 0, Z1, LIFT_DOOR[0], LINTEL, ZO1, (1, 0, 0), 'lintel')       # the doorway's jambs
    w.quad(LIFT_DOOR[1], 0, Z1, LIFT_DOOR[1], LINTEL, ZO1, (-1, 0, 0), 'lintel')
    w.quad(LIFT_DOOR[0], LINTEL, Z1, LIFT_DOOR[1], LINTEL, ZO1, (0, -1, 0), 'door_light')
    n.append(w.node('back_wall', 'wall_0'))
    n.append(box('front_wall', (XO0, -0.02, ZO0), (XO1, CUT, Z0), 'cut', open=['bottom', 'front', 'back']))
    n.append(box('end_w_0', (XO0, -0.02, Z0), (X0, WALL_H - 0.02, STAIR_DOOR[0]), 'end_wall', open=['bottom'],
                 faces={'top': 'cut', 'back': 'cut'}))
    n.append(box('end_w_1', (XO0, -0.02, STAIR_DOOR[1]), (X0, WALL_H - 0.02, Z1 + 0.01), 'end_wall',
                 open=['bottom', 'front'], faces={'top': 'cut'}))
    n.append(box('end_w_lintel', (XO0 + 0.012, LINTEL, STAIR_DOOR[0] - 0.01), (X0 - 0.012, WALL_H - 0.03, STAIR_DOOR[1] + 0.01),
                 'lintel', open=['back', 'front'], faces={'top': 'cut', 'bottom': 'door_light'}))
    n.append(box('end_e', (X1, -0.02, Z0), (XO1, WALL_H - 0.02, Z1 + 0.01), 'end_wall', open=['bottom', 'front'],
                 faces={'top': 'cut', 'back': 'cut'}))
    return n


def prop_nodes():
    n = []
    # the bag shelves on the back wall: two shelves each, bags on them
    rng = np.random.default_rng(5)
    for s, (a, b) in enumerate(SHELVES):
        parts = []
        for k, y in enumerate((0.95, 1.6)):
            parts.append(box(f'shelf_{s}_{k}', (a + 0.1, y - 0.03, Z1 - 0.32), (b - 0.1, y, Z1 + 0.02), 'shelf', open=['front']))
            xx = a + 0.3
            while xx < b - 0.55:
                bw = 0.28 + rng.random() * 0.14
                bh = 0.22 + rng.random() * 0.16
                parts.append(box(f'bag_{s}_{k}_{len(parts)}', (xx, y - 0.005, Z1 - 0.26), (xx + bw, y + bh, Z1 - 0.08),
                                 'bag_' + 'abcd'[int(rng.random() * 4)], open=['bottom', 'front']))
                xx += bw + 0.22 + rng.random() * 0.2
        n.append(group(f'shelves_{s}', parts))
    for k, (x, z) in enumerate(MANNEQUINS):
        n.append(group(f'mannequin_{k}', mannequin(k, x, z)))
    # a low table of folded knits between the well and the watches (out of every route)
    tx0, tz0, tx1, tz1 = TABLE
    table = [box('table_top', (tx0, 0.66, tz0), (tx1, 0.72, tz1), 'table', faces={'top': 'knits'}),
             box('table_base', (tx0 + 0.15, -0.02, tz0 + 0.15), (tx1 - 0.15, 0.665, tz1 - 0.15), 'table_base', open=['bottom', 'top'])]
    n.append(group('table', table))
    # beyond the west doorway: the staff stair's landing and its first steps up toward 8F
    sa, sb = STAIR_DOOR
    stair = [box('landing', (XO0 - 1.4, -0.4, sa - 0.4), (XO0, 0.0, sb + 0.4), 'landing', open=['bottom', 'right', 'left'],
                 faces={'back': 'cut'})]
    prof = [(XO0 - 1.4, -0.02)]
    for k in range(4):
        prof += [(XO0 - 1.4 - 0.3 * k, 0.18 * (k + 1)), (XO0 - 1.4 - 0.3 * (k + 1), 0.18 * (k + 1))]
    prof.append((XO0 - 1.4 - 1.2, -0.02))
    stair.append({'id': 'steps', 'op': 'extrude', 'material': 'step', 'depth': r(sb - sa + 0.8),
                  'points': [[r(a_), r(b_)] for a_, b_ in prof], 'faces': {'back': 'cut'},
                  'transform': {'translate': [0, 0, r((sa + sb) / 2)]}})
    stair.append(box('stair_wall_s', (XO0 - 2.6, -0.02, sa - 0.56), (XO0 - 0.01, WALL_H - 0.02, sa - 0.41), 'stair_wall',
                     open=['bottom', 'right'], faces={'top': 'cut', 'back': 'cut'}))
    n.append(group('stair', stair))
    # beyond the red door: the service lift's vestibule, its doors and its call panel
    la, lb = LIFT_DOOR
    lift = [box('vestibule', (la - 0.3, -0.4, ZO1), (lb + 0.3, 0.0, ZO1 + 1.2), 'lift_floor',
                open=['bottom', 'back', 'front', 'left', 'right']),
            box('lift_wall', (la - 0.3, -0.02, ZO1 + 1.2), (lb + 0.3, WALL_H - 0.02, ZO1 + 1.4), 'lift_frame',
                open=['bottom', 'front'], faces={'top': 'cut'},
                decals=[{'id': 'doors', 'face': 'back', 'material': 'lift_door', 'size': [1.1, 2.0],
                         'at': [0, r(1.0 - (WALL_H - 0.02 + 0.02) / 2 + 0.01)]},
                        {'id': 'panel', 'face': 'back', 'material': 'lift_panel', 'size': [0.1, 0.2],
                         'at': [0.75, r(1.2 - (WALL_H - 0.02 + 0.02) / 2)]}])]
    for s, xx in ((0, la - 0.3), (1, lb + 0.1)):
        lift.append(box(f'vest_side_{s}', (xx, -0.02, ZO1 - 0.01), (xx + 0.2, WALL_H - 0.02, ZO1 + 1.2), 'lift_frame',
                        open=['bottom', 'back', 'front'], faces={'top': 'cut'}))
    n.append(group('lift', lift))
    return n


def floor_recipe():
    lighting = {'direction': DIRECTION, 'ambient': AMBIENT, 'diffuse': DIFFUSE,
                'lights': [l for l in room_lights() if l['id'] != 'well'],
                'refine': {'tolerance': 20, 'max_added': 240}}
    return recipe(P + 'floor', materials(), floor_nodes() + prop_nodes(), lighting, 2000)


# ---- sf_counters

def counters_recipe():
    m = {'body': {'color': '#f0ece4'}, 'edge': {'color': '#c8e0ff', 'class': 'emissive'}, 'base': {'color': '#3a3840'}, 'glass': {'color': '#a8c8d8', 'blend': 'quarter'},
         'frame': {'color': '#c8b47c'},
         'tray_watch': {'color': '#3a4470', 'class': 'emissive', 'texture': {'image': 'art/tray_watch.png', 'bits': 4, 'projection': 'fit'}},
         'tray_scarf': {'color': '#d8c8b0', 'class': 'emissive', 'texture': {'image': 'art/tray_scarf.png', 'bits': 4, 'projection': 'fit'}}}
    n = []
    for k, (a, b, c, d) in enumerate(COUNTERS + [WATCH]):
        kind = 'tray_scarf' if a < 0 else 'tray_watch'
        edge = [] if b <= Z0 else [{'id': 'edge', 'face': 'back', 'material': 'edge', 'size': [r(c - a - 0.1), 0.04],
                                    'at': [0, r(BODY_H / 2 + 0.01 - 0.05)]}]
        parts = [box(f'body_{k}', (a, -0.02, b), (c, BODY_H, d), 'body', open=['bottom'] + (['back'] if b <= Z0 else []),
                     faces={'top': kind}, **({'decals': edge} if edge else {})),
                 box(f'kick_{k}', (a + 0.04, -0.02, b + 0.04), (c - 0.04, 0.08, d - 0.04), 'base', open=['bottom', 'top'])]
        g = Mesh()
        y0, y1 = BODY_H + 0.005, CASE_H
        e = 0.01
        g.quad(a + e, y1, b + e, c - e, y1, d - e, (0, 1, 0))
        if b > Z0:
            g.quad(a + e, y0, b + e, c - e, y1, b + e, (0, 0, -1))
        g.quad(a + e, y0, d - e, c - e, y1, d - e, (0, 0, 1))
        g.quad(a + e, y0, b + e, a + e, y1, d - e, (-1, 0, 0))
        g.quad(c - e, y0, b + e, c - e, y1, d - e, (1, 0, 0))
        parts.append(g.node(f'glass_{k}', 'glass'))
        parts.append(box(f'rim_{k}', (a + 0.02, y1 - 0.012, b + 0.02), (c - 0.02, y1 - 0.004, b + 0.035), 'frame'))
        n.append(group(f'counter_{k}', parts))
    lighting = {'direction': DIRECTION, 'ambient': AMBIENT + 0.08, 'diffuse': DIFFUSE,
                'lights': lights_named('case', 'night', 'spot'), 'refine': {'max_added': 0}}
    return recipe(P + 'counters', m, n, lighting, 400)


# ---- sf_escalators: the well

def escalator_recipe():
    x0, z0, x1, z1 = WELL
    m = {'tread': {'color': '#7c8088', 'texture': {'image': 'art/tread.png', 'bits': 4, 'projection': 'box', 'scale': [0.4, 0.4]}},
         'side': {'color': '#a8acb4'}, 'deck': {'color': '#b8bcc4'},
         'glass': {'color': '#8cb4c4', 'blend': 'quarter', 'double_sided': True},
         'rail': {'color': '#202024'}, 'cut': {'color': '#8c9ab4', 'class': 'emissive'},
         'well_wall': {'color': '#3a3e4c'}, 'slab_edge': {'color': '#8c9ab4', 'class': 'emissive'},
         'lower': {'color': '#2c3450', 'class': 'emissive', 'texture': {'image': 'art/lower.png', 'bits': 4, 'projection': 'fit'}},
         'cap': {'color': '#c8ccd4'}}
    n = []
    # the well's walls, down to 6F, and 6F's floor
    wm = Mesh()
    wm.quad(x0, LOWER, z1, x1, -0.4, z1, (0, 0, -1), 'well_wall')
    wm.quad(x0, -0.4, z1, x1, 0.0, z1, (0, 0, -1), 'slab_edge')
    wm.quad(x0, LOWER, z0, x0, 0.0, z1, (1, 0, 0), 'well_wall')
    wm.quad(x1, LOWER, z0, x1, 0.0, z1, (-1, 0, 0), 'well_wall')
    wm.quad(x0 - 3, LOWER, z0 - 1.5, x1, LOWER, z1, (0, 1, 0), 'lower')
    n.append(wm.node('well', 'well_wall'))
    # two stopped escalators down to 6F, from the well's east edge (y 0) under its west edge
    steps = 14
    run, rise = 0.42, 0.24
    for k, (za, zb) in enumerate(((z0 + 0.12, z0 + 1.17), (z0 + 1.43, z1 - 0.12))):
        xe = x1 - 0.015
        pts = [(xe, 0.0)]
        xx, yy = xe, 0.0
        for s in range(steps):
            pts.append((xx - run, yy))
            xx -= run
            yy -= rise
            pts.append((xx, yy))
        pts += [(xx - 0.4, yy), (xx - 0.4, yy - 0.6), (xe - 0.2, -0.6), (xe, -0.25)]
        pts = [(a_, b_ - 0.02) for a_, b_ in pts]
        n.append({'id': f'esc_{k}', 'op': 'extrude', 'material': 'tread', 'depth': r(zb - za),
                  'points': [[r(a_), r(b_)] for a_, b_ in pts], 'faces': {'front': 'side', 'back': 'side'},
                  'transform': {'translate': [0, 0, r((za + zb) / 2)]}})
        # glass sides and handrails along the slope, the newels at the top inside the well
        slope = math.degrees(math.atan2(rise, run))
        for s, zz in ((0, za - 0.05), (1, zb + 0.05)):
            g = Mesh()
            top = lambda x_: (x_ - x1) * rise / run + 0.9
            xl = x0 - 0.6
            xr = x1 - 0.25
            g.poly([(xr, top(xr) - 0.8, zz), (xl, top(xl) - 0.8, zz), (xl, top(xl), zz), (xr, top(xr), zz)], (0, 0, -1))
            n.append(g.node(f'glass_{k}_{s}', 'glass'))
            ln = math.hypot(x1 - 0.25 - xl, top(x1 - 0.25) - top(xl))
            n.append(at({'id': f'rail_{k}_{s}', 'op': 'box', 'size': [r(ln), 0.05, 0.07], 'material': 'rail'},
                        translate=[r((x1 - 0.25 + xl) / 2), r((top(x1 - 0.25) + top(xl)) / 2 + 0.02), r(zz)],
                        rotate=[0, 0, r(slope)]))
            n.append(at({'id': f'newel_{k}_{s}', 'op': 'cylinder', 'radius': 0.1, 'height': 0.065, 'segments': 8,
                         'material': 'rail'}, translate=[r(x1 - 0.25), r(top(x1 - 0.25) - 0.08), r(zz)], rotate=[90, 0, 0]))
    # the glass balustrade round the well's three other sides, cut at 1 m, on a stainless kerb
    kerb = [box('kerb_s', (x0 - 0.05, -0.02, z0 - 0.06), (x1 + 0.05, 0.12, z0 + 0.01), 'side', open=['bottom']),
            box('kerb_n', (x0 - 0.05, -0.02, z1 - 0.01), (x1 + 0.05, 0.12, z1 + 0.06), 'side', open=['bottom']),
            box('kerb_w', (x0 - 0.06, -0.02, z0 + 0.01), (x0 + 0.01, 0.12, z1 - 0.01), 'side', open=['bottom', 'back', 'front'])]
    n.append(group('kerb', kerb))
    gb = Mesh()
    yb, yt = 0.12, CUT - 0.02
    gb.quad(x0 - 0.02, yb, z0 - 0.025, x1 + 0.02, yt, z0 - 0.025, (0, 0, -1))
    gb.quad(x0 - 0.02, yb, z1 + 0.025, x1 + 0.02, yt, z1 + 0.025, (0, 0, -1))
    gb.quad(x0 - 0.025, yb, z0 - 0.02, x0 - 0.025, yt, z1 + 0.02, (-1, 0, 0))
    n.append(gb.node('balustrade', 'glass'))
    n.append(box('bal_cut_s', (x0 - 0.04, yt - 0.005, z0 - 0.04), (x1 + 0.04, CUT, z0 - 0.01), 'cut'))
    n.append(box('bal_cut_n', (x0 - 0.04, yt - 0.005, z1 + 0.01), (x1 + 0.04, CUT, z1 + 0.04), 'cut'))
    n.append(box('bal_cut_w', (x0 - 0.04, yt - 0.005, z0 - 0.01), (x0 - 0.01, CUT, z1 + 0.01), 'cut', open=['back', 'front']))
    lighting = {'direction': DIRECTION, 'ambient': AMBIENT + 0.08, 'diffuse': DIFFUSE,
                'lights': lights_named('well', 'night', 'spot_0') +
                [{'id': 'below', 'at': [0.8, LOWER + 1.5, 0.1], 'color': '#7090e0', 'intensity': 1.6, 'range': 4.5}],
                'refine': {'max_added': 0}}
    return recipe(P + 'escalators', m, n, lighting, 700)


# ---- collision and placements

def collision():
    op = ['bottom', 'top']
    n = [box('front_wall', (XO0, 0, ZO0), (XO1, CUT, Z0), 'floor', open=op),
         box('back_0', (XO0, 0, Z1), (LIFT_DOOR[0], WALL_H, ZO1), 'floor', open=op),
         box('back_1', (LIFT_DOOR[1], 0, Z1), (XO1, WALL_H, ZO1), 'floor', open=op),
         box('end_w_0', (XO0, 0, Z0), (X0, WALL_H, STAIR_DOOR[0]), 'floor', open=op + ['back']),
         box('end_w_1', (XO0, 0, STAIR_DOOR[1]), (X0, WALL_H, Z1), 'floor', open=op + ['front']),
         box('end_e', (X1, 0, Z0), (XO1, WALL_H, Z1), 'floor', open=op + ['back', 'front']),
         box('well', (WELL[0], 0, WELL[1]), (WELL[2], CUT, WELL[3]), 'floor', open=op)]
    f = Mesh()
    for (x0, z0, x1, z1) in [(XO0, ZO0, XO1, ZO1)]:
        f.quad(x0, 0, z0, x1, 0, z1, (0, 1, 0))
    n.insert(0, f.node('slab', 'floor'))
    for k, (a, b, c, d) in enumerate(COUNTERS + [WATCH]):
        n.append(box(f'counter_{k}', (a, 0, b + (0.01 if b <= Z0 else 0)), (c, CASE_H, d), 'floor', open=op))
    n.append(box('table', (TABLE[0], 0, TABLE[1]), (TABLE[2], 0.72, TABLE[3]), 'floor', open=op))
    for k, (x, z) in enumerate(MANNEQUINS):
        n.append(box(f'plinth_{k}', (x - 0.3, 0, z - 0.3), (x + 0.3, CUT, z + 0.3), 'floor', open=op))
    return collision_recipe(P + 'floor_col', n)


def placements():
    return [{'id': P + 'floor', 'asset': P + 'floor', 'position': [0, 0, 0], 'collision': P + 'floor_col'},
            {'id': P + 'escalators', 'asset': P + 'escalators', 'position': [0, 0, 0], 'collision': 'none'},   # the well is in sf_floor_col
            {'id': P + 'counters', 'asset': P + 'counters', 'position': [0, 0, 0], 'collision': 'none'}]       # and so are the counters


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--no-placements', action='store_true', help='leave shopfloor.placements.json as it is')
    args = ap.parse_args()
    draw_art()
    write_json(HERE / f'{P}floor.asset.json', floor_recipe())
    write_json(HERE / f'{P}floor_col.asset.json', collision())
    write_json(HERE / f'{P}escalators.asset.json', escalator_recipe())
    write_json(HERE / f'{P}counters.asset.json', counters_recipe())
    if not args.no_placements:
        write_json(HERE / 'shopfloor.placements.json', {'format': 'after-hours-placements', 'version': 1,
                                                        'room': 'shopfloor', 'placements': placements()})
    print('wrote sf_floor, sf_floor_col, sf_escalators, sf_counters and', len(list(ART.glob('*.png'))), 'textures')


if __name__ == '__main__':
    main()
