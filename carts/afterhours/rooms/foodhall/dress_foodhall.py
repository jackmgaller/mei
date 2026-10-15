#!/usr/bin/env python3
"""Stage 2, the food hall (B1), dressed: writes its Asset Kit recipes, draws their textures and
writes the room's placements.

    python3 carts/afterhours/rooms/foodhall/dress_foodhall.py [--no-placements]

Writes, beside itself:
  fh_hall.asset.json       the hall: the floor and the back wall (painted), the walls and the
                           doorways' lintels, the front wall's cut face (painted: the ground beside
                           a basement, in section), the two columns, the counters along the back
                           wall with their paper andon lamps, the melon counter and its melons in
                           their boxes, a parked cleaner's cart, the service lift's open car beyond
                           its doorway and the mall beyond the shutter door; lit by ROOM_LIGHTS
  fh_hall_col.asset.json   its collision: the floor, the walls without tops, the cases, the
                           counters, the columns
  fh_cases.asset.json      the four glass cases, lit from inside (cakes, fruit, wagashi, gift
                           boxes): their own recipe, lit at their corners only, so that no light
                           refines their glass
  foodhall.placements.json the placements (replace the greybox's)
  art/*.png                the floor and the back wall (painted as ROOM_LIGHTS light them), the
                           front's face, the cases' trays, the melons' net, the lift's pads

PLAN.md is the room's floor plan (the level lead's); this keeps what it says must stay: the two
rows of cases glass and low with their aisles, the melon counter low, the two columns (opaque,
cut at 1 m), room round each stack of gift boxes (agent A draws the stacks), the doorways open, the
lift's spawn, the guard's place and the camera's, the front cut at 1 m. The light is
../passage/diorama.py's method. Everything named here is fictional. Needs Pillow and NumPy.
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
P = 'fh_'

# ---- the plan (PLAN.md and foodhall.play.json)
X0, X1 = -12.0, 12.0
Z0, Z1 = -4.75, 4.75
T = 0.25
XO0, XO1, ZO0, ZO1 = X0 - T, X1 + T, Z0 - T, Z1 + T
SLAB = 0.4
CASES = [(-7.5, -1.7, -1.0, -1.0), (1.0, -1.7, 7.5, -1.0), (-7.5, 1.1, -1.0, 1.8), (1.0, 1.1, 7.5, 1.8)]
CASE_KIND = ['cakes', 'fruit', 'wagashi', 'gifts']
CASE_LIGHT = ['#fff0e0', '#eefff0', '#ffe8f4', '#fff2d8']
MELON = (9.6, -1.0, 10.4, 2.4)
COLUMNS = [(-4.25, -3.6), (4.25, 3.4)]
COL_S = 0.7
GIFTS = [(-1.7, 0.05), (8.6, -3.4), (-9.0, -2.2)]
LIFT_DOOR = (-10.4, -9.0)      # back wall, x
MALL_DOOR = (-3.6, -2.4)       # east wall, z
LINTEL = 2.1
CAMERA = (0.0, 4.6)
CASE_H, BODY_H = 0.95, 0.6
BACK_COUNTERS = [(-7.6, -2.2, 'tea'), (-1.2, 1.2, 'bread'), (2.4, 7.6, 'sweets')]   # along the back wall: x0, x1, kind
BACK_D = 0.5                   # their depth from the wall
CART = (-11.9, 2.6, -11.25, 3.5)

# ---- the light
AMBIENT, DIFFUSE = 0.07, 0.04
DIRECTION = [0.0, 1.0, -0.4]


def room_lights():
    out = [{'id': f'case_{k}', 'at': [r((a + c) / 2), 0.78, r((b + d) / 2)], 'color': CASE_LIGHT[k], 'intensity': 1.25,
            'range': 3.0} for k, (a, b, c, d) in enumerate(CASES)]
    out += [{'id': f'andon_{k}', 'at': [r((a + b) / 2), 1.15, Z1 - 0.3], 'color': '#ffb468', 'intensity': 1.2, 'range': 2.6}
            for k, (a, b, _) in enumerate(BACK_COUNTERS)]
    out += [
        {'id': 'melon', 'at': [10.0, 2.0, 0.7], 'color': '#ffd08c', 'intensity': 1.8, 'range': 3.0,
         'shadows': True, 'radius': 0.2},
        {'id': 'mall', 'at': [X1 + 1.3, 1.7, -3.0], 'color': '#ffe6bc', 'intensity': 3.2, 'range': 5.8,
         'shadows': True, 'radius': 0.3},
        {'id': 'lift_car', 'at': [-9.7, 2.1, Z1 + 1.1], 'color': '#e4ecff', 'intensity': 2.6, 'range': 4.4,
         'shadows': True, 'radius': 0.25},
        {'id': 'night', 'at': [0.0, 7.0, 0.0], 'color': '#806c90', 'intensity': 0.55, 'range': 18.0},
        {'id': 'camera', 'at': [CAMERA[0], 2.2, 4.45], 'color': '#ff2a1a', 'intensity': 0.7, 'range': 1.5},
        {'id': 'exit_sign', 'at': [X1 - 0.15, 2.25, -3.0], 'color': '#7cffa0', 'intensity': 0.8, 'range': 2.0},
    ]
    return out


def lights_named(*prefixes):
    return [l for l in room_lights() if l['id'].startswith(prefixes)]


def blockers():
    out = [(a, -1, b, c, BODY_H, d) for a, b, c, d in CASES]
    out.append((MELON[0], -1, MELON[1], MELON[2], 0.9, MELON[3]))
    s = COL_S / 2
    out += [(x - s, -1, z - s, x + s, 4, z + s) for x, z in COLUMNS]
    out += [(a, -1, Z1 - BACK_D, b, 0.9, Z1) for a, b, _ in BACK_COUNTERS]
    out.append((CART[0], -1, CART[1], CART[2], 1.0, CART[3]))
    out += [(X1, -1, ZO0, XO1, 4, MALL_DOOR[0]), (X1, -1, MALL_DOOR[1], XO1, 4, ZO1), (X1, LINTEL, MALL_DOOR[0], XO1, 4, MALL_DOOR[1]),
            (XO0 - 3, -1, Z1, LIFT_DOOR[0], 4, ZO1), (LIFT_DOOR[1], -1, Z1, XO1 + 3, 4, ZO1), (LIFT_DOOR[0], LINTEL, Z1, LIFT_DOOR[1], 4, ZO1),
            (XO0, -1, ZO0, X0, 4, ZO1)]
    return out


# ---- the floor

FLOOR_X = [XO0, -4.0833, 4.0833, XO1]
FLOOR_Z = [ZO0, 0.0, ZO1]
FLOOR_TEX = (196, 120)


def floor_base(x, z):
    """In white light: warm terrazzo, brown guide bands down the aisles, a dark plinth line under
    each case, boards before the melon counter, the lift's sill plate and the door's mat."""
    rng = np.random.default_rng(91)
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array([196, 184, 162])
    chips = rng.random((h, w))
    base += (chips > 0.9)[..., None] * np.array([18, 16, 12]) - (chips < 0.07)[..., None] * np.array([22, 20, 18])
    joint = (np.abs((x / 0.6) % 1.0 - 0.5) > 0.48) | (np.abs((z / 0.6) % 1.0 - 0.5) > 0.48)
    base -= joint[..., None] * np.array([12, 12, 10])
    for zc in (-3.0, 0.05, 3.05):
        band = np.abs(z - zc) < 0.22
        base = np.where(band[..., None], np.array([132, 96, 70]) * (0.95 + 0.1 * chips[..., None]), base)
    for (a, b, c, d) in CASES:
        under = soft_rect(x, z, a - 0.08, c + 0.08, b - 0.08, d + 0.08, 0.02) > 0.5
        base = np.where(under[..., None], np.array([70, 64, 60]), base)
    boards = (x > 8.9) & (x < 11.6) & (z > -1.7) & (z < 3.1)
    plank = np.floor((z + 2) / 0.18)
    wood = np.array([150, 104, 66]) * (0.9 + 0.12 * ((np.sin(plank * 7.1) * 43.7) % 1.0))[..., None]
    wood -= ((np.abs(((z + 2) / 0.18) % 1.0 - 0.5) > 0.45))[..., None] * 20
    base = np.where(boards[..., None], wood, base)
    sill = (x > LIFT_DOOR[0] - 0.1) & (x < LIFT_DOOR[1] + 0.1) & (z > Z1 - 0.3)
    base = np.where(sill[..., None], np.array([160, 162, 168]) + (((x * 12) % 1.0) < 0.5)[..., None] * 14, base)
    mat = (x > X1 - 1.1) & (z > MALL_DOOR[0] - 0.1) & (z < MALL_DOOR[1] + 0.1)
    base = np.where(mat[..., None], np.array([60, 56, 54]), base)
    base += (rng.random((h, w)) - 0.5)[..., None] * 5
    return base


def floor_paint(x, z):
    y = np.zeros_like(x)
    rgb = floor_base(x, z) * shade(x, y, z, (0, 1, 0), room_lights(), AMBIENT, DIFFUSE, DIRECTION, blockers())
    t30 = math.tan(math.radians(30))
    for k, (a, b, c, d) in enumerate(CASES):       # the cases' lit glass in the polished floor
        g = soft_rect(x, z, a + 0.1, c - 0.1, b - 0.95 * t30 - 0.05, b - 0.62 * t30, 0.22)
        rgb += (g * 0.12)[..., None] * hex_rgb(CASE_LIGHT[k])
    for k, (a, b, _) in enumerate(BACK_COUNTERS):  # the andons in it
        for xx in np.linspace(a + 0.6, b - 0.6, 3):
            rgb += (blob(x, z, xx, Z1 - 0.3 - 1.2 * t30, 0.12, 0.2) * 0.35)[..., None] * np.array([255, 180, 104])
    return rgb


# ---- the back wall

WALL_X = [XO0, 0.0, XO1]
WALL_TEX = (240, 52)


def wall_base(x, y):
    """In white light: cream tiles to the counters' height, dark timber above with the shops'
    curtains (noren) in their colours, the lift's frame."""
    rng = np.random.default_rng(93)
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array([92, 66, 48])
    tiles = y < 1.2
    tl = (np.abs((x / 0.2) % 1.0 - 0.5) > 0.42) | (np.abs((y / 0.1) % 1.0 - 0.5) > 0.4)
    base = np.where(tiles[..., None], np.array([214, 206, 188]) - tl[..., None] * 18, base)
    base = np.where((y < 0.1)[..., None], np.array([60, 52, 46]), base)
    noren = {'tea': (34, 64, 54), 'bread': (190, 150, 90), 'sweets': (120, 40, 60)}
    for a, b, kind in BACK_COUNTERS:
        cloth = (x > a) & (x < b) & (y > 1.55) & (y < 2.25)
        slit = np.abs(((x - a) / ((b - a) / 4)) % 1.0) < 0.04
        base = np.where((cloth & ~slit)[..., None], np.array(noren[kind]), base)
        crest = cloth & (np.hypot((x - (a + b) / 2) / 0.22, (y - 1.95) / 0.16) < 1)
        base = np.where(crest[..., None], np.array([236, 230, 214]), base)
    frame = (x > LIFT_DOOR[0] - 0.12) & (x < LIFT_DOOR[1] + 0.12) & (y < LINTEL + 0.12)
    base = np.where(frame[..., None], np.array([120, 122, 128]), base)
    base += (rng.random((h, w)) - 0.5)[..., None] * 5
    return base


def wall_paint(x, y, z):
    return wall_base(x, y) * shade(x, y, z, (0, 0, -1), room_lights(), AMBIENT, DIFFUSE, DIRECTION, blockers())


def ground_section(a, b, w=240, h=20):
    """The front wall's face: the basement's retaining wall and the ground beside it, in section,
    with a drain and the mall's ducts."""
    xs = a + (np.arange(w) + 0.5) / w * (b - a)
    ys = CUT - (np.arange(h) + 0.5) / h * (CUT + SLAB)
    x, y = np.meshgrid(xs, ys)
    rng = np.random.default_rng(61 + int(a))
    rgb = np.zeros((h, w, 3)) + np.array([64, 52, 44])
    rgb += (np.sin(y * 14 + np.sin(x * 0.5) * 2) > 0.5)[..., None] * np.array([10, 8, 6])
    rgb += ((rng.random((h, w)) > 0.93)[..., None]) * np.array([20, 18, 16])
    rgb = np.where((y < 0.0)[..., None], np.array([118, 128, 148]), rgb)
    rgb = np.where((np.abs(y) < 0.03)[..., None], np.array([150, 162, 184]), rgb)
    for px, py, pr, c in ((-8.0, 0.5, 0.32, (110, 110, 116)), (-1.5, 0.55, 0.22, (70, 110, 170)),
                          (6.0, 0.5, 0.3, (150, 120, 90))):
        d = np.hypot(x - px, y - py)
        rgb = np.where((d < pr)[..., None], np.array(c) * 0.55, rgb)
        rgb = np.where(((d < pr) & (d > pr * 0.65))[..., None], np.array(c), rgb)
    return Image.fromarray(to_array(rgb, 4.0), 'RGB')


# ---- small textures

def tray(kind, w=64, h=12):
    """A case's tray under its glass, lit, seen from above, with its price cards along the front."""
    rng = np.random.default_rng(len(kind))
    bg = {'cakes': (236, 232, 224), 'fruit': (212, 222, 200), 'wagashi': (178, 140, 96), 'gifts': (230, 220, 200)}[kind]
    img = Image.new('RGB', (w, h), bg)
    d = ImageDraw.Draw(img)
    for i in range(10):
        cx = 3 + i * 6
        if kind == 'cakes':      # shortcakes, chocolate, matcha, mont blanc
            c = [(250, 246, 236), (110, 66, 40), (130, 170, 90), (200, 160, 100)][i % 4]
            d.rectangle([cx - 2, 2, cx + 2, 6], fill=c)
            d.point((cx, 3), fill=(220, 40, 50))
        elif kind == 'fruit':    # strawberries in trays, mikan, grapes
            c = [(220, 40, 50), (250, 150, 30), (90, 60, 130), (180, 200, 60)][i % 4]
            d.ellipse([cx - 2, 2, cx + 2, 6], fill=c)
        elif kind == 'wagashi':  # pastel sweets on wooden trays
            c = [(250, 200, 220), (200, 230, 190), (250, 240, 220), (200, 190, 240)][i % 4]
            d.ellipse([cx - 2, 3, cx + 1, 6], fill=c)
            d.point((cx + 2, 4), fill=c)
        else:                    # wrapped gift boxes with ribbons
            c = [(200, 60, 60), (60, 90, 160), (230, 200, 150), (80, 130, 90)][i % 4]
            d.rectangle([cx - 2, 2, cx + 2, 6], fill=c)
            d.line([(cx, 2), (cx, 6)], fill=(240, 220, 120))
        d.rectangle([cx - 1, 9, cx + 1, 10], fill=[(230, 60, 60), (250, 220, 80), (255, 255, 255)][int(rng.random() * 3)])
    return img


def melon_skin():
    """A melon's netted green skin."""
    w, h = 16, 16
    img = Image.new('RGB', (w, h), (110, 150, 80))
    d = ImageDraw.Draw(img)
    for k in range(-16, 16, 4):
        d.line([(k, 0), (k + 16, 16)], fill=(200, 210, 170))
        d.line([(k + 16, 0), (k, 16)], fill=(200, 210, 170))
    return img


def pads():
    """The service lift's quilted blankets."""
    w, h = 16, 16
    img = Image.new('RGB', (w, h), (60, 76, 110))
    d = ImageDraw.Draw(img)
    for k in range(0, 16, 4):
        d.line([(k, 0), (k, 15)], fill=(44, 56, 84))
        d.line([(0, k), (15, k)], fill=(44, 56, 84))
    return img


def section_face(w, h, fill, ring):
    img = Image.new('RGB', (w, h), fill)
    d = ImageDraw.Draw(img)
    for k in range(-h, w, 4):
        d.line([(k, h - 1), (k + h - 1, 0)], fill=tuple(int(c * 0.93) for c in fill))
    d.rectangle([0, 0, w - 1, h - 1], outline=ring)
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
        ground_section(a, b).save(ART / f'front_{k}.png')
    for kind in CASE_KIND:
        tray(kind).save(ART / f'tray_{kind}.png')
    melon_skin().save(ART / 'melon.png')
    pads().save(ART / 'pads.png')
    section_face(16, 16, (140, 154, 180), (88, 96, 116)).save(ART / 'cut.png')


# ---- fh_hall

def materials():
    m = {
        'cut': {'color': '#8c9ab4', 'class': 'emissive'},
        'cut_tex': {'color': '#8c9ab4', 'class': 'emissive', 'texture': {'image': 'art/cut.png', 'bits': 4, 'projection': 'fit'}},
        'end_wall': {'color': '#c4b8a4'},
        'lintel': {'color': '#5c544c'},
        'door_light': {'color': '#ffe8c8', 'class': 'emissive'},
        'column': {'color': '#d4ccbc'},
        'counter': {'color': '#8a6444'}, 'counter_top': {'color': '#c8b89c'},
        'andon': {'color': '#ffd8a0', 'class': 'emissive'}, 'andon_frame': {'color': '#3a2a20'},
        'canister': {'color': '#2c4a3c'}, 'canister_lid': {'color': '#b89850'},
        'bread': {'color': '#c88a48'}, 'basket': {'color': '#8a6438'},
        'sweet_box': {'color': '#d8c8a8'}, 'sweet_lid': {'color': '#a03040'},
        'melon_counter': {'color': '#9a7048'}, 'melon_top': {'color': '#5a3e28'},
        'kiri': {'color': '#e0d0b0'},
        'melon': {'color': '#9cb478', 'smooth': True, 'texture': {'image': 'art/melon.png', 'bits': 4, 'projection': 'box',
                                                                  'scale': [0.2, 0.2]}},
        'price': {'color': '#f0ece0', 'class': 'emissive'},
        'cart': {'color': '#e0c040'}, 'cart_dark': {'color': '#3a3c44'}, 'mop': {'color': '#d8dce4'},
        'bucket': {'color': '#4a90c8'},
        'lift_floor': {'color': '#8a8c92'}, 'lift_frame': {'color': '#6a6c74'},
        'pads': {'color': '#3c4c70', 'texture': {'image': 'art/pads.png', 'bits': 4, 'projection': 'box', 'scale': [0.5, 0.5]}},
        'lift_lamp': {'color': '#f0f4ff', 'class': 'emissive'},
        'mall_floor': {'color': '#c8beb0'}, 'shutter': {'color': '#8c9098'},
        'exit_sign': {'color': '#40d070', 'class': 'emissive'},
    }
    for j in range(2):
        for i in range(3):
            m[f'floor_{j}{i}'] = {'color': '#a89880', 'class': 'emissive',
                                  'texture': {'image': f'art/floor_{j}{i}.png', 'bits': 8, 'projection': 'fit'}}
    for k in range(2):
        m[f'wall_{k}'] = {'color': '#6c584a', 'class': 'emissive',
                          'texture': {'image': f'art/wall_{k}.png', 'bits': 8, 'projection': 'fit'}}
        m[f'front_{k}'] = {'color': '#40342c', 'class': 'emissive',
                           'texture': {'image': f'art/front_{k}.png', 'bits': 4, 'projection': 'fit'}}
    return m


def shell_nodes():
    f = Mesh()
    painted_floor(f, FLOOR_X, FLOOR_Z, [], 'floor_{}{}')
    for k, (a, b) in enumerate(zip(WALL_X, WALL_X[1:])):
        f.quad(a, -SLAB, ZO0, b, CUT, ZO0, (0, 0, -1), f'front_{k}')
    n = [f.node('floor', 'floor_00')]
    w = Mesh()
    for a, b in ((XO0, LIFT_DOOR[0]), (LIFT_DOOR[1], XO1)):
        painted_wall_z(w, WALL_X, a, b, 0, WALL_H, Z1, 'wall_{}', WALL_H)
    painted_wall_z(w, WALL_X, LIFT_DOOR[0], LIFT_DOOR[1], LINTEL, WALL_H, Z1, 'wall_{}', WALL_H)
    w.quad(XO0, WALL_H, Z1, XO1, WALL_H, ZO1, (0, 1, 0), 'cut')
    w.quad(LIFT_DOOR[0], 0, Z1, LIFT_DOOR[0], LINTEL, ZO1, (1, 0, 0), 'lintel')
    w.quad(LIFT_DOOR[1], 0, Z1, LIFT_DOOR[1], LINTEL, ZO1, (-1, 0, 0), 'lintel')
    w.quad(LIFT_DOOR[0], LINTEL, Z1, LIFT_DOOR[1], LINTEL, ZO1, (0, -1, 0), 'door_light')
    n.append(w.node('back_wall', 'wall_0'))
    n.append(box('front_wall', (XO0, -0.02, ZO0), (XO1, CUT, Z0), 'cut', open=['bottom', 'front', 'back']))
    n.append(box('end_w', (XO0, -0.02, Z0), (X0, WALL_H - 0.02, Z1 + 0.01), 'end_wall', open=['bottom', 'front'],
                 faces={'top': 'cut', 'back': 'cut'}))
    ma, mb = MALL_DOOR
    n.append(box('end_e_0', (X1, -0.02, Z0), (XO1, WALL_H - 0.02, ma), 'end_wall', open=['bottom'],
                 faces={'top': 'cut', 'back': 'cut'}))
    n.append(box('end_e_1', (X1, -0.02, mb), (XO1, WALL_H - 0.02, Z1 + 0.01), 'end_wall', open=['bottom', 'front'],
                 faces={'top': 'cut'}))
    n.append(box('end_e_lintel', (X1 + 0.012, LINTEL, ma - 0.01), (XO1 - 0.012, WALL_H - 0.03, mb + 0.01), 'lintel',
                 open=['back', 'front'], faces={'top': 'cut', 'bottom': 'door_light'}))
    n.append(box('exit_sign', (X1 - 0.08, 2.18, ma + 0.25), (X1 + 0.02, 2.32, mb - 0.25), 'exit_sign', open=['right']))
    s = COL_S / 2
    for k, (x, z) in enumerate(COLUMNS):
        n.append(box(f'column_{k}', (x - s, -0.02, z - s), (x + s, CUT, z + s), 'column', open=['bottom'],
                     faces={'top': 'cut_tex'}))
    return n


def prop_nodes():
    n = []
    rng = np.random.default_rng(9)
    for k, (a, b, kind) in enumerate(BACK_COUNTERS):
        parts = [box(f'bc_{k}', (a, -0.02, Z1 - BACK_D), (b, 0.86, Z1 + 0.02), 'counter', open=['bottom', 'front'],
                     faces={'top': 'counter_top'})]
        for j, xx in enumerate(np.linspace(a + 0.6, b - 0.6, 3)):     # three paper andons on each
            parts.append(box(f'andon_{k}_{j}', (xx - 0.11, 0.855, Z1 - 0.42), (xx + 0.11, 1.3, Z1 - 0.2), 'andon',
                             faces={'top': 'andon_frame'}))
        xx = a + 0.25
        while xx < b - 0.35:
            if any(abs(xx - q) < 0.3 for q in np.linspace(a + 0.6, b - 0.6, 3)):
                xx += 0.15
                continue
            if kind == 'tea':
                parts.append(at({'id': f'tin_{k}_{len(parts)}', 'op': 'cylinder', 'radius': 0.07, 'height': 0.2, 'segments': 6,
                                 'material': 'canister', 'faces': {'top': 'canister_lid'}}, translate=[r(xx), 0.95, Z1 - 0.32]))
            elif kind == 'bread':
                parts.append(box(f'basket_{k}_{len(parts)}', (xx - 0.14, 0.855, Z1 - 0.44), (xx + 0.14, 0.93, Z1 - 0.2), 'basket',
                                 faces={'top': 'bread'}))
            else:
                parts.append(box(f'box_{k}_{len(parts)}', (xx - 0.12, 0.855, Z1 - 0.42), (xx + 0.12, 0.97, Z1 - 0.22), 'sweet_box',
                                 faces={'top': 'sweet_lid'}))
            xx += 0.34 + rng.random() * 0.1
        n.append(group(f'back_counter_{k}', parts))
    # the melon counter: wooden, its melons each in a paulownia box, a price card at each
    a, b, c, d = MELON
    mel = [box('melon_counter', (a, -0.02, b), (c, 0.82, d), 'melon_counter', open=['bottom'], faces={'top': 'melon_top'})]
    for k, zz in enumerate(np.linspace(b + 0.4, d - 0.4, 5)):
        mel.append(box(f'kiri_{k}', (a + 0.16, 0.815, zz - 0.2), (c - 0.16, 0.88, zz + 0.2), 'kiri', open=['bottom', 'top']))
        mel.append(at({'id': f'melon_{k}', 'op': 'sphere', 'radius': 0.13, 'rings': 4, 'segments': 6, 'material': 'melon'},
                      translate=[r((a + c) / 2), 0.86, r(zz)]))
        mel.append(box(f'price_{k}', (a - 0.01, 0.6, zz - 0.07), (a + 0.01, 0.7, zz + 0.07), 'price'))
    n.append(group('melons', mel))
    # a parked cleaner's cart in the west end, out of every route
    cx0, cz0, cx1, cz1 = CART
    n.append(group('cart', [
        box('cart_base', (cx0, 0.08, cz0), (cx1, 0.16, cz1), 'cart'),
        box('cart_bin', (cx0 + 0.04, 0.15, cz0 + 0.05), (cx1 - 0.04, 0.7, cz0 + 0.45), 'cart', open=['bottom']),
        box('cart_frame', (cx0 + 0.02, -0.02, cz1 - 0.06), (cx1 - 0.02, 0.95, cz1 - 0.02), 'cart_dark', open=['bottom']),
        at({'id': 'cart_bucket', 'op': 'cylinder', 'radius': 0.13, 'height': 0.25, 'segments': 8, 'material': 'bucket'},
           translate=[r((cx0 + cx1) / 2), 0.29, r(cz1 - 0.3)]),
        at({'id': 'mop', 'op': 'cylinder', 'radius': 0.02, 'height': 0.9, 'segments': 4, 'caps': False, 'material': 'mop'},
           translate=[r((cx0 + cx1) / 2 + 0.1), 0.6, r(cz1 - 0.32)], rotate=[12, 0, 0])]))
    # beyond the back doorway: the service lift's open car, padded for the deliveries
    la, lb = LIFT_DOOR
    lift = [box('car_floor', (la - 0.2, -0.4, ZO1), (lb + 0.2, 0.0, ZO1 + 1.7), 'lift_floor',
                open=['bottom', 'back', 'front', 'left', 'right']),
            box('car_back', (la - 0.2, -0.02, ZO1 + 1.7), (lb + 0.2, WALL_H - 0.02, ZO1 + 1.85), 'pads', open=['bottom', 'front'],
                faces={'top': 'cut'})]
    for s, xx in ((0, la - 0.35), (1, lb + 0.05)):
        lift.append(box(f'car_side_{s}', (xx, -0.02, ZO1), (xx + 0.15, WALL_H - 0.02, ZO1 + 1.7), 'pads',
                        open=['bottom', 'back', 'front'], faces={'top': 'cut'}))
    lift.append(box('car_lamp', (la + 0.3, WALL_H - 0.1, ZO1 + 0.6), (lb - 0.3, WALL_H - 0.06, ZO1 + 1.2), 'lift_lamp'))
    n.append(group('lift', lift))
    # beyond the shutter door: the mall's floor, the shutter rolled up in its box over the doorway
    ma, mb = MALL_DOOR
    n.append(group('mall', [
        box('mall_floor', (XO1, -0.4, ma - 0.6), (XO1 + 1.6, 0.0, mb + 0.6), 'mall_floor', open=['bottom', 'left'],
            faces={'back': 'cut'}),
        box('shutter_box', (X1 + 0.03, 1.94, ma + 0.02), (X1 + 0.2, 2.09, mb - 0.02), 'shutter')]))
    return n


def hall_recipe():
    lighting = {'direction': DIRECTION, 'ambient': AMBIENT, 'diffuse': DIFFUSE, 'lights': room_lights(),
                'refine': {'tolerance': 20, 'max_added': 240}}
    return recipe(P + 'hall', materials(), shell_nodes() + prop_nodes(), lighting, 2000)


# ---- fh_cases

def cases_recipe():
    m = {'body': {'color': '#d8dcdc'}, 'base': {'color': '#3a3c40'}, 'glass': {'color': '#b0d0dc', 'blend': 'quarter'},
         'edge': {'color': '#fff4e0', 'class': 'emissive'}}
    for kind in CASE_KIND:
        m[f'tray_{kind}'] = {'color': '#e0d8c8', 'class': 'emissive',
                             'texture': {'image': f'art/tray_{kind}.png', 'bits': 4, 'projection': 'fit'}}
    n = []
    for k, (a, b, c, d) in enumerate(CASES):
        edge = [{'id': 'edge', 'face': 'back', 'material': 'edge', 'size': [r(c - a - 0.1), 0.04], 'at': [0, r(BODY_H / 2 + 0.01 - 0.05)]}]
        parts = [box(f'body_{k}', (a, -0.02, b), (c, BODY_H, d), 'body', open=['bottom'], faces={'top': f'tray_{CASE_KIND[k]}'},
                     decals=edge),
                 box(f'kick_{k}', (a + 0.04, -0.02, b + 0.04), (c - 0.04, 0.08, d - 0.04), 'base', open=['bottom', 'top'])]
        g = Mesh()
        y0, y1, e = BODY_H + 0.005, CASE_H, 0.01
        g.quad(a + e, y1, b + e, c - e, y1, d - e, (0, 1, 0))
        g.quad(a + e, y0, b + e, c - e, y1, b + e, (0, 0, -1))
        g.quad(a + e, y0, d - e, c - e, y1, d - e, (0, 0, 1))
        g.quad(a + e, y0, b + e, a + e, y1, d - e, (-1, 0, 0))
        g.quad(c - e, y0, b + e, c - e, y1, d - e, (1, 0, 0))
        parts.append(g.node(f'glass_{k}', 'glass'))
        n.append(group(f'case_{k}', parts))
    lighting = {'direction': DIRECTION, 'ambient': AMBIENT + 0.1, 'diffuse': DIFFUSE,
                'lights': lights_named('case', 'night', 'andon'), 'refine': {'max_added': 0}}
    return recipe(P + 'cases', m, n, lighting, 400)


# ---- collision and placements

def collision():
    op = ['bottom', 'top']
    f = Mesh()
    f.quad(XO0, 0, ZO0, XO1, 0, ZO1, (0, 1, 0))
    n = [f.node('slab', 'floor'),
         box('front_wall', (XO0, 0, ZO0), (XO1, CUT, Z0), 'floor', open=op),
         box('back_0', (XO0, 0, Z1), (LIFT_DOOR[0], WALL_H, ZO1), 'floor', open=op),
         box('back_1', (LIFT_DOOR[1], 0, Z1), (XO1, WALL_H, ZO1), 'floor', open=op),
         box('end_w', (XO0, 0, Z0), (X0, WALL_H, Z1), 'floor', open=op + ['back', 'front']),
         box('end_e_0', (X1, 0, Z0), (XO1, WALL_H, MALL_DOOR[0]), 'floor', open=op + ['back']),
         box('end_e_1', (X1, 0, MALL_DOOR[1]), (XO1, WALL_H, Z1), 'floor', open=op + ['front'])]
    for k, (a, b, c, d) in enumerate(CASES):
        n.append(box(f'case_{k}', (a, 0, b), (c, CASE_H, d), 'floor', open=op))
    n.append(box('melon', (MELON[0], 0, MELON[1]), (MELON[2], 0.9, MELON[3]), 'floor', open=op))
    s = COL_S / 2
    for k, (x, z) in enumerate(COLUMNS):
        n.append(box(f'column_{k}', (x - s, 0, z - s), (x + s, CUT, z + s), 'floor', open=op))
    return collision_recipe(P + 'hall_col', n)


def placements():
    return [{'id': P + 'hall', 'asset': P + 'hall', 'position': [0, 0, 0], 'collision': P + 'hall_col'},
            {'id': P + 'cases', 'asset': P + 'cases', 'position': [0, 0, 0], 'collision': 'none'}]   # the cases are in fh_hall_col


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--no-placements', action='store_true', help='leave foodhall.placements.json as it is')
    args = ap.parse_args()
    draw_art()
    write_json(HERE / f'{P}hall.asset.json', hall_recipe())
    write_json(HERE / f'{P}hall_col.asset.json', collision())
    write_json(HERE / f'{P}cases.asset.json', cases_recipe())
    if not args.no_placements:
        write_json(HERE / 'foodhall.placements.json', {'format': 'after-hours-placements', 'version': 1,
                                                       'room': 'foodhall', 'placements': placements()})
    print('wrote fh_hall, fh_hall_col, fh_cases and', len(list(ART.glob('*.png'))), 'textures')


if __name__ == '__main__':
    main()
