#!/usr/bin/env python3
"""The tower, the ninth floor (9F), dressed: writes its Asset Kit recipes, draws their textures and
writes the room's placements.

    python3 carts/afterhours/rooms/ninth/dress_ninth.py [--no-placements]

The floor the directory leaves out, the chairman's own, in 1990: the building's lie. Writes,
beside itself:
  nf_floor.asset.json      the floor (painted: deep carpet, the city's light through the windows,
                           the chandelier's over the boardroom) and the back wall (painted:
                           walnut, two paintings hung), the walls and lintels, the front's face
                           (the tower's granite and bronze glass in section), the core cut at 1 m
                           (its walled-up lift doors in fresh plaster on the panelling; in section
                           its lift shafts, a car passing below this floor, the fire stair's
                           flights, the risers), the coat cupboard and its coats, the boardroom's
                           table, chairs and the model of the next tower, the chairman's office
                           (its wall, desk, chair, golf bag), the crated paintings and one
                           unwrapped, the service stair down and the private stair up beyond their
                           doorways; lit by ROOM_LIGHTS
  nf_floor_col.asset.json  its collision: the floor, the walls without tops, the core, the
                           cupboard's sides, the boardroom, the office wall, the desk, the crates
  nf_glass.asset.json      the boardroom's glass and posts, cut at 1 m (corners only: no light
                           refines its glass)
  ninth.placements.json    the placements (replace the greybox's)
  art/*.png                the paintings, the desk's top, the crates, the model's windows

PLAN.md is the room's floor plan (the level lead's); this keeps what it says must stay: the core
solid where it is (cut at 1 m like everything in play), the coat cupboard and its sides, the
boardroom's glass closed, the office wall and doorway, the desk, the camera's place, the stair
doorways, the corridor between the core and the boardroom and the front strip clear, the front
cut at 1 m. The light is ../passage/diorama.py's method. Nothing here names a real company or a
real painting. Needs Pillow and NumPy.
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
P = 'nf_'

# ---- the plan (PLAN.md and ninth.play.json)
X0, X1 = -8.0, 8.0
Z0, Z1 = -4.25, 4.25
T = 0.25
XO0, XO1, ZO0, ZO1 = X0 - T, X1 + T, Z0 - T, Z1 + T
SLAB = 0.4
STAIR_DOOR = (-7.4, -6.2)      # back wall, x
UP_DOOR = (2.6, 3.8)           # east wall, z
LINTEL = 2.1
CORE = (-5.0, 0.4, 3.0, Z1)
CW = 0.25                      # the core's walls
CUPBOARD = (-8.0, -1.2, -7.1, 0.4)    # with its sides: z -1.2 ... -1.0 and 0.2 ... 0.4
BOARD = (-3.4, -3.1, 1.6, -0.8)       # the boardroom's glass
GT = 0.15
TABLE = (-2.4, -2.4, 0.6, -1.5)
OFFICE_WALL = (0.65, 0.8)             # z, from the core (x 3) to the east wall, its doorway x 5 ... 6.2
OFFICE_DOOR = (5.0, 6.2)
DESK = (4.6, 2.0, 6.2, 2.6)
CRATES = [(4.0, -3.4, 5.4, -2.2), (6.2, -1.4, 7.4, -0.4)]
# The core's plan, as the lift hall's builder draws it on the sixth (rooms/hall/dress_hall.py,
# paint_core_top): three lift shafts along its south side, x -4.4 ... -0.2, z to 1.75; the fire
# stair's landing at the (here walled-up) door in its west face, z 1.1 ... 2.3, and its flights east
# behind the shafts; the risers' pipes and a square duct at the east end.
SHAFTS = [(-4.4 + k * 1.4 + 0.08, -4.4 + k * 1.4 + 1.32) for k in range(3)]
SHAFT_Z = (0.65, 1.75)
STAIR_Z = (1.95, 4.0)                                   # the fire stair's flights, behind the shafts
STAIR_DOOR_Z = (1.1, 2.3)                               # its door in the core's west face, walled up here
RISERS = [(0.6, 2.4, 0.12), (0.95, 2.4, 0.12), (1.3, 2.4, 0.12), (0.6, 2.05, 0.12)]
DUCT = (1.8, 0.66, 2.6, 1.6)
LOWER = -4.0                                            # how deep the shafts are drawn

# ---- the light
AMBIENT, DIFFUSE = 0.06, 0.04
DIRECTION = [0.0, 1.0, -0.4]
CITY = '#a8c0f0'


def room_lights():
    return [
        {'id': 'city_w', 'at': [-4.0, 4.0, -9.0], 'color': CITY, 'intensity': 2.4, 'range': 14.0,
         'shadows': True, 'radius': 0.4},
        {'id': 'city_e', 'at': [4.5, 4.5, -8.5], 'color': '#c0b0e0', 'intensity': 2.0, 'range': 14.0,
         'shadows': True, 'radius': 0.4},
        {'id': 'night', 'at': [0.0, 7.0, 0.0], 'color': '#6a5c8c', 'intensity': 0.45, 'range': 18.0},
        {'id': 'chandelier', 'at': [-0.9, 2.35, -1.95], 'color': '#ffd8a0', 'intensity': 2.0, 'range': 3.6,
         'shadows': True, 'radius': 0.3},
        {'id': 'lamp', 'at': [7.5, 1.6, 3.9], 'color': '#ffc880', 'intensity': 1.8, 'range': 3.6,
         'shadows': True, 'radius': 0.15},
        {'id': 'service', 'at': [-6.8, 1.4, Z1 + 1.2], 'color': '#c8f0d8', 'intensity': 1.4, 'range': 3.0,
         'shadows': True, 'radius': 0.2},
        {'id': 'helipad', 'at': [X1 + 1.6, 2.5, 3.2], 'color': '#c8dcff', 'intensity': 2.4, 'range': 4.4,
         'shadows': True, 'radius': 0.3},
        {'id': 'lift_car', 'at': [-2.2, -1.6, 1.2], 'color': '#e0e8ff', 'intensity': 1.2, 'range': 2.4},
        {'id': 'crates', 'at': [5.6, 2.3, -1.8], 'color': '#fff0d8', 'intensity': 1.0, 'range': 2.8},
        {'id': 'exit_w', 'at': [-6.8, 2.2, Z1 - 0.15], 'color': '#60ff90', 'intensity': 0.6, 'range': 1.5},
        {'id': 'exit_e', 'at': [X1 - 0.15, 2.2, 3.2], 'color': '#60ff90', 'intensity': 0.6, 'range': 1.5},
    ]


def lights_named(*prefixes):
    return [l for l in room_lights() if l['id'].startswith(prefixes)]


MULLIONS = [X0 + 1.5 * k for k in range(1, 11)]


def blockers():
    out = [(XO0 - 6, WALL_H + 0.3, ZO0 - 0.2, XO1 + 6, 9, Z0), (XO0, -1, ZO0, XO1, 0.85, Z0)]
    out += [(x - 0.05, -1, ZO0, x + 0.05, 4, Z0) for x in MULLIONS]
    out.append((CORE[0], -1, CORE[1], CORE[2], 4, CORE[3]))
    c0, d0, c1, d1 = CUPBOARD
    out += [(c0, -1, d0, c1, 2.0, d0 + 0.2), (c0, -1, d1 - 0.2, c1, 2.0, d1)]
    a, b = OFFICE_WALL
    out += [(CORE[2], -1, a, OFFICE_DOOR[0], 4, b), (OFFICE_DOOR[1], -1, a, X1, 4, b)]
    out.append((DESK[0], 0.7, DESK[1], DESK[2], 0.75, DESK[3]))
    out.append((TABLE[0], 0.7, TABLE[1], TABLE[2], 0.75, TABLE[3]))
    out += [(c0, -1, d0, c1, 1.8, d1) for c0, d0, c1, d1 in CRATES]
    out += [(X1, -1, ZO0, XO1, 4, UP_DOOR[0]), (X1, -1, UP_DOOR[1], XO1, 4, ZO1), (X1, LINTEL, UP_DOOR[0], XO1, 4, UP_DOOR[1]),
            (XO0, -1, ZO0, X0, 4, ZO1),
            (XO0 - 3, -1, Z1, STAIR_DOOR[0], 4, ZO1), (STAIR_DOOR[1], -1, Z1, XO1 + 3, 4, ZO1),
            (STAIR_DOOR[0], LINTEL, Z1, STAIR_DOOR[1], 4, ZO1)]
    return out


# ---- the floor

FLOOR_X = [XO0, -2.75, 2.75, XO1]
FLOOR_Z = [ZO0, 0.0, ZO1]
FLOOR_TEX = (132, 108)


def floor_base(x, z):
    """In white light: deep bronze carpet with a border of the house's key pattern, the boardroom's
    darker rug, the chairman's wine carpet with its medallion, a marble threshold at each stair."""
    rng = np.random.default_rng(111)
    h, w = x.shape
    pile = rng.random((h, w))
    base = np.zeros((h, w, 3)) + np.array([130, 104, 70])
    base *= (0.94 + 0.08 * pile)[..., None]
    edge = np.minimum.reduce([x - X0, X1 - x, z - Z0, Z1 - z])
    band = (edge > 0.25) & (edge < 0.5)
    key = band & (((np.floor(x / 0.25) + np.floor(z / 0.25)) % 2) == 0)
    base = np.where(band[..., None], np.array([90, 66, 44]), base)
    base = np.where(key[..., None], np.array([170, 140, 80]), base)
    x0, z0, x1, z1 = BOARD
    rug = soft_rect(x, z, x0 + 0.4, x1 - 0.4, z0 + 0.3, z1 - 0.3, 0.02) > 0.5
    base = np.where(rug[..., None], np.array([70, 40, 36]) * (0.95 + 0.08 * pile)[..., None], base)
    office = (x > CORE[2]) & (z > OFFICE_WALL[1])
    wine = np.array([110, 34, 44]) * (0.93 + 0.1 * pile)[..., None]
    base = np.where(office[..., None], wine, base)
    d = np.hypot(x - 5.5, z - 2.6)
    base = np.where((office & (np.abs(d - 0.9) < 0.05))[..., None], np.array([190, 150, 80]), base)
    for cond in ((z > Z1 - 0.3) & (x > STAIR_DOOR[0]) & (x < STAIR_DOOR[1]),
                 (x > X1 - 0.3) & (z > UP_DOOR[0]) & (z < UP_DOOR[1])):
        base = np.where(cond[..., None], np.array([200, 196, 186]), base)
    return base


def floor_paint(x, z):
    y = np.zeros_like(x)
    return floor_base(x, z) * shade(x, y, z, (0, 1, 0), room_lights(), AMBIENT, DIFFUSE, DIRECTION, blockers())


# ---- the back wall: what shows of it (the west end and the office; the core stands before the rest)

WALL_X = [XO0, 0.0, XO1]
WALL_TEX = (240, 52)
PAINTINGS = [(-5.9, -5.1, 0.8, 1.7, 'sea'), (4.4, 6.4, 0.85, 1.85, 'field')]


def painting(kind, u, v):
    """A painting in its gilt frame (u, v 0..1, v up): a grey sea under a pale sky, or a yellow
    field under a blue one with a dark tree. Nobody's in particular."""
    if kind == 'sea':
        sky = np.array([200, 196, 180]) * (0.8 + 0.2 * v[..., None])
        sea = np.array([70, 90, 100]) + (np.sin(u * 40 + v * 10) > 0.6)[..., None] * 30
        rgb = np.where((v > 0.45)[..., None], sky, sea)
    else:
        sky = np.array([60, 110, 190]) + (np.sin(u * 20 + v * 30) > 0.5)[..., None] * np.array([40, 40, 30])
        field = np.array([210, 170, 50]) + (np.sin(u * 50) > 0.3)[..., None] * np.array([30, 20, -10])
        rgb = np.where((v > 0.4)[..., None], sky, field)
        tree = (np.hypot((u - 0.7) / 0.06, (v - 0.55) / 0.25) < 1)
        rgb = np.where(tree[..., None], np.array([30, 50, 30]), rgb)
    frame = (u < 0.06) | (u > 0.94) | (v < 0.07) | (v > 0.93)
    return np.where(frame[..., None], np.array([196, 160, 80]), rgb)


def wall_base(x, y):
    """In white light: walnut panelling in tall panels, a dado rail, the paintings."""
    rng = np.random.default_rng(113)
    h, w = x.shape
    grain = np.sin(x * 30 + np.sin(y * 7) * 2) * 0.5 + 0.5
    base = np.zeros((h, w, 3)) + np.array([116, 76, 48]) * (0.9 + 0.15 * grain)[..., None]
    base -= ((np.abs((x / 0.9) % 1.0 - 0.5) > 0.47))[..., None] * np.array([30, 20, 12])
    base = np.where((np.abs(y - 0.9) < 0.03)[..., None], np.array([150, 110, 70]), base)
    base = np.where((y < 0.12)[..., None], np.array([50, 34, 24]), base)
    for x0, x1, y0, y1, kind in PAINTINGS:
        on = (x > x0) & (x < x1) & (y > y0) & (y < y1)
        base = np.where(on[..., None], painting(kind, (x - x0) / (x1 - x0), (y - y0) / (y1 - y0)), base)
    base += (rng.random((h, w)) - 0.5)[..., None] * 5
    return base


def wall_paint(x, y, z):
    return wall_base(x, y) * shade(x, y, z, (0, 0, -1), room_lights(), AMBIENT, DIFFUSE, DIRECTION, blockers())


def front_face(a, b, w=240, h=20):
    """The tower's skin in section, as on the sixth: the granite spandrel, the bronze glass."""
    xs = a + (np.arange(w) + 0.5) / w * (b - a)
    ys = CUT - (np.arange(h) + 0.5) / h * (CUT + SLAB)
    x, y = np.meshgrid(xs, ys)
    rng = np.random.default_rng(int(a * 10) + 900)
    rgb = np.zeros((h, w, 3)) + np.array([150, 112, 104])
    rgb += ((rng.random((h, w)) > 0.8)[..., None]) * np.array([20, 16, 14])
    glass = y > 0.62
    rgb = np.where(glass[..., None], np.array([46, 34, 26]) + (rng.random((h, w)) > 0.985)[..., None] * np.array([200, 170, 120]), rgb)
    rgb = np.where((np.abs(y - 0.62) < 0.03)[..., None], np.array([120, 100, 70]), rgb)
    rgb = np.where((glass & (np.abs(((x + 0.75) / 1.5) % 1.0 - 0.5) > 0.47))[..., None], np.array([110, 90, 64]), rgb)
    rgb = np.where((y < 0.0)[..., None], np.array([118, 128, 148]), rgb)
    rgb = np.where((np.abs(y) < 0.03)[..., None], np.array([150, 162, 184]), rgb)
    return Image.fromarray(to_array(rgb, 4.0), 'RGB')


# ---- small textures

def desk_top():
    """The chairman's desk from above: rosewood, a leather blotter, a telephone, a cigar box."""
    img = Image.new('RGB', (32, 12), (96, 46, 34))
    d = ImageDraw.Draw(img)
    d.rectangle([9, 3, 22, 10], fill=(40, 60, 46))
    d.rectangle([24, 2, 28, 5], fill=(30, 30, 32))
    d.rectangle([3, 6, 7, 9], fill=(150, 100, 60))
    return img


def crate_top():
    """A crate cut at 1 m: its boards in section round the painting standing inside it, wrapped,
    its gilt frame's edge showing."""
    img = Image.new('RGB', (16, 12), (190, 160, 110))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 15, 11], outline=(130, 100, 60))
    d.rectangle([2, 4, 13, 6], fill=(220, 214, 200))
    d.line([(2, 5), (13, 5)], fill=(200, 160, 70))
    return img


def crate_side():
    """A crate's side: pine boards, a stencilled glass-and-arrow mark (handle with care) and a
    shipping number, no words."""
    img = Image.new('RGB', (16, 16), (200, 168, 112))
    d = ImageDraw.Draw(img)
    for yy in (4, 9, 14):
        d.line([(0, yy), (15, yy)], fill=(160, 126, 80))
    d.polygon([(4, 3), (8, 3), (7, 7), (5, 7)], outline=(40, 40, 40))
    d.line([(6, 7), (6, 10)], fill=(40, 40, 40))
    d.line([(11, 2), (11, 6)], fill=(40, 40, 40))
    d.line([(10, 3), (11, 2), (12, 3)], fill=(40, 40, 40))
    d.rectangle([3, 11, 12, 12], fill=(60, 60, 60))
    return img


def unwrapped():
    """The one painting out of its crate, leaning on it: a field and a sky, in its frame."""
    w, h = 24, 16
    u = (np.arange(w) + 0.5) / w
    v = 1 - (np.arange(h) + 0.5) / h
    uu, vv = np.meshgrid(u, v)
    return Image.fromarray(to_array(painting('field', uu, vv), 3.0), 'RGB')


def tower_windows():
    """The model tower's sides: bronze glass in bands, a few windows lit."""
    img = Image.new('RGB', (8, 16), (120, 90, 60))
    d = ImageDraw.Draw(img)
    for yy in range(1, 16, 2):
        d.line([(0, yy), (7, yy)], fill=(60, 44, 34))
    d.point((2, 5), fill=(255, 220, 140))
    d.point((5, 9), fill=(255, 220, 140))
    return img


def section_face(w, h, fill, ring):
    img = Image.new('RGB', (w, h), fill)
    d = ImageDraw.Draw(img)
    for k in range(-h, w, 4):
        d.line([(k, h - 1), (k + h - 1, 0)], fill=tuple(int(c * 0.93) for c in fill))
    d.rectangle([0, 0, w - 1, h - 1], outline=ring)
    return img


def exit_sign():
    img = Image.new('RGB', (16, 9), (40, 170, 90))
    d = ImageDraw.Draw(img)
    d.rectangle([11, 1, 14, 7], outline=(240, 250, 240))
    d.point((6, 1), fill=(250, 255, 250))
    d.line([(6, 2), (5, 5)], fill=(250, 255, 250))
    d.line([(5, 5), (3, 7)], fill=(250, 255, 250))
    d.line([(5, 5), (7, 7)], fill=(250, 255, 250))
    d.line([(4, 3), (8, 3)], fill=(250, 255, 250))
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
    desk_top().save(ART / 'desk_top.png')
    crate_top().save(ART / 'crate_top.png')
    crate_side().save(ART / 'crate_side.png')
    unwrapped().save(ART / 'unwrapped.png')
    tower_windows().save(ART / 'tower.png')
    exit_sign().save(ART / 'exit_sign.png')
    section_face(16, 16, (140, 154, 180), (88, 96, 116)).save(ART / 'cut.png')


# ---- nf_floor

def materials():
    m = {
        'cut': {'color': '#8c9ab4', 'class': 'emissive'},
        'cut_tex': {'color': '#8c9ab4', 'class': 'emissive', 'texture': {'image': 'art/cut.png', 'bits': 4, 'projection': 'fit'}},
        'end_wall': {'color': '#8a6448'}, 'lintel': {'color': '#4c3a2c'},
        'door_light': {'color': '#ffe8c8', 'class': 'emissive'},
        'panel': {'color': '#86583a'}, 'plaster': {'color': '#d8d0c0'}, 'jamb': {'color': '#4c3424'},
        'shaft': {'color': '#30323a'}, 'pit': {'color': '#0c0e16', 'class': 'emissive'},
        'car_roof': {'color': '#4a4c54'}, 'car_lit': {'color': '#6c6a62'}, 'car_lamp': {'color': '#e8f0ff', 'class': 'emissive'},
        'weight': {'color': '#5a5c64'}, 'stair': {'color': '#9a9a94'}, 'riser': {'color': '#4a4c54'},
        'pipe': {'color': '#8a7860'}, 'duct': {'color': '#a8acb4'},
        'coat_a': {'color': '#b08a5a'}, 'coat_b': {'color': '#2c3048'}, 'coat_c': {'color': '#3c3c40'}, 'fur': {'color': '#e8e2d8'},
        'table': {'color': '#4a2a1e'}, 'leather': {'color': '#3a2420'},
        'plinth': {'color': '#e8e4dc'}, 'model': {'color': '#9a7858', 'texture': {'image': 'art/tower.png', 'bits': 4, 'projection': 'box',
                                                                                    'scale': [0.1, 0.2]}},
        'model_top': {'color': '#c8a860'},
        'desk': {'color': '#5a2c20'}, 'desk_top': {'color': '#60302a', 'texture': {'image': 'art/desk_top.png', 'bits': 4, 'projection': 'fit'}},
        'golf_bag': {'color': '#1c3c2c'}, 'club': {'color': '#c8ccd4'},
        'crate': {'color': '#c8a070', 'texture': {'image': 'art/crate_side.png', 'bits': 4, 'projection': 'fit'}},
        'crate_top': {'color': '#c0a070', 'class': 'emissive', 'texture': {'image': 'art/crate_top.png', 'bits': 4, 'projection': 'fit'}},
        'unwrapped': {'color': '#8a9a70', 'texture': {'image': 'art/unwrapped.png', 'bits': 4, 'projection': 'fit'}},
        'frame_back': {'color': '#6a5030'},
        'stair_s': {'color': '#8a8c90'}, 'stairwell': {'color': '#a0a098'},
        'exit_sign': {'color': '#30c060', 'class': 'emissive', 'texture': {'image': 'art/exit_sign.png', 'bits': 4, 'projection': 'fit'}},
        'sign_box': {'color': '#50525a'},
    }
    for j in range(2):
        for i in range(3):
            m[f'floor_{j}{i}'] = {'color': '#6a5438', 'class': 'emissive',
                                  'texture': {'image': f'art/floor_{j}{i}.png', 'bits': 8, 'projection': 'fit'}}
    for k in range(2):
        m[f'wall_{k}'] = {'color': '#5c3c28', 'class': 'emissive',
                          'texture': {'image': f'art/wall_{k}.png', 'bits': 8, 'projection': 'fit'}}
        m[f'front_{k}'] = {'color': '#7c5c50', 'class': 'emissive',
                           'texture': {'image': f'art/front_{k}.png', 'bits': 4, 'projection': 'fit'}}
    return m


def shell_nodes():
    f = Mesh()
    cx0, cz0, cx1, cz1 = CORE
    painted_floor(f, FLOOR_X, FLOOR_Z, [(cx0 + CW, cz0 + CW, cx1 - CW, cz1 + 0.5)], 'floor_{}{}')
    for k, (a, b) in enumerate(zip(WALL_X, WALL_X[1:])):
        f.quad(a, -SLAB, ZO0, b, CUT, ZO0, (0, 0, -1), f'front_{k}',        # hand UVs: the mesh has them
               (lambda a, b: lambda p: ((p[0] - a) / (b - a), (CUT - p[1]) / (CUT + SLAB)))(a, b))
    n = [f.node('floor', 'floor_00')]
    w = Mesh()
    sa, sb = STAIR_DOOR
    for a, b in ((XO0, sa), (sb, cx0), (cx1, XO1)):
        painted_wall_z(w, WALL_X, a, b, 0, WALL_H, Z1, 'wall_{}', WALL_H)
    painted_wall_z(w, WALL_X, sa, sb, LINTEL, WALL_H, Z1, 'wall_{}', WALL_H)
    w.quad(XO0, WALL_H, Z1, XO1, WALL_H, ZO1, (0, 1, 0), 'cut')
    w.quad(sa, 0, Z1, sa, LINTEL, ZO1, (1, 0, 0), 'lintel')
    w.quad(sb, 0, Z1, sb, LINTEL, ZO1, (-1, 0, 0), 'lintel')
    w.quad(sa, LINTEL, Z1, sb, LINTEL, ZO1, (0, -1, 0), 'door_light')
    n.append(w.node('back_wall', 'wall_0'))
    n.append(box('front_wall', (XO0, -0.02, ZO0), (XO1, CUT, Z0), 'cut', open=['bottom', 'front', 'back']))
    n.append(box('end_w', (XO0, -0.02, Z0), (X0, WALL_H - 0.02, Z1 + 0.01), 'end_wall', open=['bottom', 'front'],
                 faces={'top': 'cut', 'back': 'cut'}))
    ua, ub = UP_DOOR
    n.append(box('end_e_0', (X1, -0.02, Z0), (XO1, WALL_H - 0.02, ua), 'end_wall', open=['bottom'],
                 faces={'top': 'cut', 'back': 'cut'}))
    n.append(box('end_e_1', (X1, -0.02, ub), (XO1, WALL_H - 0.02, Z1 + 0.01), 'end_wall', open=['bottom', 'front'],
                 faces={'top': 'cut'}))
    n.append(box('end_e_lintel', (X1 + 0.012, LINTEL, ua - 0.01), (XO1 - 0.012, WALL_H - 0.03, ub + 0.01), 'lintel',
                 open=['back', 'front'], faces={'top': 'cut', 'bottom': 'door_light'}))
    return n


def simple(pts):
    """An outline without repeated or collinear neighbours (the kit refuses them)."""
    out = []
    for p_ in pts:
        if out and abs(out[-1][0] - p_[0]) < 1e-9 and abs(out[-1][1] - p_[1]) < 1e-9:
            continue
        out.append(p_)
    changed = True
    while changed:
        changed = False
        for i in range(len(out)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
            if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < 1e-9:
                out.pop(i)
                changed = True
                break
    return out


def core_nodes():
    """The core, cut at 1 m: its walnut-panelled faces, the lift doors on its south face walled up
    in fresh plaster (and the fire stair's on its west face); in section the plan the sixth shows:
    the three shafts with their cars far below (the middle one a little lighter), the fire stair's
    landing and its flights (one down, one up to the cut), the risers' pipes and duct."""
    from diorama import rects_minus
    cx0, cz0, cx1, cz1 = CORE
    n = []
    hc = CUT - 0.02
    lift = [{'id': f'walled_{k}', 'face': 'back', 'material': 'plaster', 'size': [1.0, r(hc - 0.06)],
             'at': [r((a + b) / 2 - (cx0 + cx1) / 2), -0.02]} for k, (a, b) in enumerate(SHAFTS)]
    n.append(box('core_s', (cx0, -0.02, cz0), (cx1, hc, cz0 + CW), 'panel', open=['bottom'], faces={'top': 'cut'}, decals=lift))
    da, db = STAIR_DOOR_Z
    n.append(box('core_w', (cx0, -0.02, cz0 + CW), (cx0 + CW, hc, cz1 + 0.01), 'panel', open=['bottom', 'back', 'front'],
                 faces={'top': 'cut'},
                 decals=[{'id': 'walled_stair', 'face': 'left', 'material': 'plaster', 'size': [r(db - da), r(hc - 0.06)],
                          'at': [r((cz0 + CW + cz1 + 0.01) / 2 - (da + db) / 2), -0.02]}]))
    n.append(box('core_e', (cx1 - CW, -0.02, cz0 + CW), (cx1, hc, cz1 + 0.01), 'panel', open=['bottom', 'back', 'front'],
                 faces={'top': 'cut'}))
    ix0, ix1 = cx0 + CW, cx1 - CW
    za, zb = SHAFT_Z
    sa_, sb_ = STAIR_Z
    flight_x = (-3.9, -1.4)
    sh = Mesh()
    # the core's floor in section, dark, round the shafts and the flight going down
    holes = [(a, za - 0.01, b, zb) for a, b in SHAFTS] + [(flight_x[0], sa_, flight_x[1], (sa_ + sb_) / 2)]
    for (x0_, z0_, x1_, z1_) in rects_minus((ix0, cz0 + CW, ix1, cz1), holes):
        sh.quad(x0_, -0.05, z0_, x1_, -0.05, z1_, (0, 1, 0), 'riser')
    for k, (a, b) in enumerate(SHAFTS):
        sh.quad(a, LOWER, zb, b, -0.05, zb, (0, 0, -1), 'shaft')
        sh.quad(a, LOWER, za, a, -0.05, zb, (1, 0, 0), 'shaft')
        sh.quad(b, LOWER, za, b, -0.05, zb, (-1, 0, 0), 'shaft')
        sh.quad(a, LOWER, za, b, LOWER, zb, (0, 1, 0), 'pit')
    sh.quad(ix0, LOWER, cz1, ix1, WALL_H, cz1, (0, 0, -1), 'riser')      # the building's back wall inside the core
    n.append(sh.node('shafts', 'shaft'))
    for k, (a, b) in enumerate(SHAFTS):     # the walls between the shafts, cut at 1 m
        if k + 1 < len(SHAFTS):
            n.append(box(f'shaft_wall_{k}', (b + 0.005, -0.4, za), (SHAFTS[k + 1][0] - 0.005, hc - 0.01, zb + 0.08), 'riser',
                         open=['bottom', 'back'], faces={'top': 'cut'}))
        car = 'car_lit' if k == 1 else 'car_roof'
        n.append(box(f'car_{k}', (a + 0.22, -3.2 + 0.4 * k, za + 0.15), (b - 0.22, -3.1 + 0.4 * k, zb - 0.15), car, open=['bottom']))
    n.append(box('shaft_back', (SHAFTS[0][0], -0.4, zb + 0.005), (SHAFTS[-1][1], hc, zb + 0.15), 'riser',
                 open=['bottom', 'left', 'right'], faces={'top': 'cut'}))
    # the fire stair: the landing by its walled-up door, a flight down east, a flight up east (cut)
    zm = (sa_ + sb_) / 2
    prof_d = [(flight_x[0], 0.0)]
    for k in range(8):
        prof_d += [(flight_x[0] + 0.3 * (k + 1), -0.18 * k), (flight_x[0] + 0.3 * (k + 1), -0.18 * (k + 1))]
    prof_d = simple(prof_d + [(flight_x[0] + 2.4, -1.8), (flight_x[0], -1.8)])
    n.append({'id': 'flight_down', 'op': 'extrude', 'material': 'stair', 'depth': r(zm - sa_ - 0.04),
              'points': [[r(a_), r(b_)] for a_, b_ in prof_d], 'transform': {'translate': [0, 0, r((sa_ + zm) / 2)]}})
    prof_u = [(flight_x[0], -0.02)]
    for k in range(5):
        prof_u += [(flight_x[0] + 0.3 * k, 0.18 * (k + 1)), (flight_x[0] + 0.3 * (k + 1), 0.18 * (k + 1))]
    prof_u = simple(prof_u + [(flight_x[0] + 1.5, -0.02)])
    n.append({'id': 'flight_up', 'op': 'extrude', 'material': 'stair', 'depth': r(sb_ - zm - 0.04),
              'points': [[r(a_), r(b_)] for a_, b_ in prof_u], 'transform': {'translate': [0, 0, r((zm + sb_) / 2)]}})
    n.append(box('stair_rail', (flight_x[0] + 0.1, -0.05, zm - 0.015), (flight_x[1], hc - 0.05, zm + 0.015), 'riser', open=['bottom'],
                 faces={'top': 'cut'}))
    # the risers: pipes and a duct, cut at 1 m
    for k, (px, pz, pr) in enumerate(RISERS):
        n.append(at({'id': f'pipe_{k}', 'op': 'cylinder', 'radius': pr, 'height': 1.0, 'segments': 6,
                     'material': 'pipe' if k % 2 == 0 else 'duct', 'faces': {'top': 'cut'}}, translate=[px, hc - 0.5, pz]))
    a, b, c, d = DUCT
    n.append(box('duct', (a, -0.04, b), (c, hc, d), 'duct', open=['bottom'], faces={'top': 'cut'},
                 decals=[{'id': 'void', 'face': 'top', 'material': 'pit', 'size': [r(c - a - 0.2), r(d - b - 0.2)], 'at': [0, 0]}]))
    return n


def prop_nodes():
    n = core_nodes()
    # the coat cupboard: its sides (cut at 1 m), coats on their hangers cut at the section
    c0, d0, c1, d1 = CUPBOARD
    cup = [box('cup_s', (c0 - 0.01, -0.02, d0), (c1, CUT, d0 + 0.2), 'panel', open=['bottom', 'left'], faces={'top': 'cut'}),
           box('cup_n', (c0 - 0.01, -0.02, d1 - 0.2), (c1, CUT, d1), 'panel', open=['bottom', 'left'], faces={'top': 'cut'})]
    for k, (zc, mat) in enumerate(((-0.82, 'coat_a'), (-0.6, 'coat_b'), (-0.38, 'coat_c'), (-0.15, 'fur'), (0.05, 'coat_b'))):
        cup.append(box(f'coat_{k}', (c0 + 0.03, 0.2 if mat != 'fur' else 0.55, zc - 0.07), (c0 + 0.42, CUT - 0.03, zc + 0.07), mat))
    n.append(group('cupboard', cup))
    # the boardroom: the long table, leather chairs, the model of the next tower in the middle
    a, b, c, d = TABLE
    br = [box('table', (a, 0.7, b), (c, 0.75, d), 'table'),
          box('table_foot', (a + 0.4, -0.02, b + 0.25), (c - 0.4, 0.705, d - 0.25), 'table', open=['bottom', 'top'])]
    for k, x in enumerate(np.linspace(a + 0.4, c - 0.4, 4)):
        for s, z in ((-1, b - 0.3), (1, d + 0.3)):
            br.append(box(f'chair_{k}_{s + 1}', (x - 0.24, 0.42, z - 0.22), (x + 0.24, 0.52, z + 0.22), 'leather'))
            br.append(box(f'chair_back_{k}_{s + 1}', (x - 0.23, 0.51, z + s * 0.19 - 0.04), (x + 0.23, CUT - 0.02, z + s * 0.19 + 0.04),
                          'leather', faces={'top': 'cut'}))
    for k, (x, z) in enumerate(((a - 0.3, (b + d) / 2), (c + 0.3, (b + d) / 2))):
        br.append(box(f'chair_end_{k}', (x - 0.22, 0.42, z - 0.24), (x + 0.22, 0.52, z + 0.24), 'leather'))
    mx, mz = (a + c) / 2, (b + d) / 2
    br += [box('model_plinth', (mx - 0.3, 0.745, mz - 0.2), (mx + 0.3, 0.78, mz + 0.2), 'plinth'),
           box('model_0', (mx - 0.1, 0.775, mz - 0.08), (mx + 0.1, 0.88, mz + 0.08), 'model'),
           box('model_1', (mx - 0.07, 0.875, mz - 0.055), (mx + 0.07, 0.95, mz + 0.055), 'model'),
           at({'id': 'model_top', 'op': 'cone', 'radius': 0.07, 'height': 0.05, 'segments': 4, 'material': 'model_top'},
              translate=[r(mx), 0.97, r(mz)], rotate=[0, 45, 0])]
    n.append(group('boardroom', br))
    # the chairman's office: its wall (cut at 1 m) and doorway, his desk and chair, the golf bag
    oa, ob = OFFICE_WALL
    da, db = OFFICE_DOOR
    cx1 = CORE[2]
    off = [box('office_a', (cx1, -0.02, oa), (da, CUT, ob), 'panel', open=['bottom', 'left'], faces={'top': 'cut'}),
           box('office_b', (db, -0.02, oa), (X1 + 0.01, CUT, ob), 'panel', open=['bottom', 'right'], faces={'top': 'cut'})]
    for k, xx in enumerate((da, db)):
        off.append(box(f'jamb_{k}', (xx - 0.03, -0.02, oa - 0.02), (xx + 0.03, CUT + 0.004, ob + 0.02), 'jamb', open=['bottom'],
                       faces={'top': 'cut'}))
    a, b, c, d = DESK
    off += [box('desk', (a, -0.02, b), (c, 0.75, d), 'desk', open=['bottom'], faces={'top': 'desk_top'}),
            box('desk_chair', (5.15, 0.42, d + 0.15), (5.75, 0.55, d + 0.65), 'leather'),
            box('desk_chair_back', (5.17, 0.54, d + 0.58), (5.73, CUT - 0.02, d + 0.68), 'leather', faces={'top': 'cut'}),
            at({'id': 'golf_bag', 'op': 'cylinder', 'radius': 0.13, 'height': 0.9, 'segments': 8, 'material': 'golf_bag'},
               translate=[3.38, 0.43, 1.12], rotate=[6, 0, -6])]
    for k, (dx, dz, top) in enumerate(((-0.05, 0.03, 0.97), (0.05, -0.02, 0.99), (0.0, 0.07, 0.95))):
        off.append(box(f'club_{k}', (3.38 + dx - 0.04, 0.86 + k * 0.01, 1.12 + dz - 0.025), (3.38 + dx + 0.04, top, 1.12 + dz + 0.025), 'club'))
    n.append(group('office', off))
    # the paintings bought at auction, still in their crates (cut at 1 m), one unwrapped
    for k, (a, b, c, d) in enumerate(CRATES):
        n.append(box(f'crate_{k}', (a, -0.02, b), (c, CUT - 0.01, d), 'crate', open=['bottom'], faces={'top': 'crate_top'}))
    a, b, c, d = CRATES[1]
    n.append(at({'id': 'unwrapped', 'op': 'box', 'size': [1.0, 0.7, 0.05], 'material': 'frame_back', 'faces': {'back': 'unwrapped'}},
                translate=[r((a + c) / 2), 0.36, r(b - 0.12)], rotate=[14, 0, 0]))
    # beyond the back doorway: the service stair, down to the sixth
    sa, sb = STAIR_DOOR
    prof = [(ZO1, 0.0)]
    for k in range(8):
        prof += [(ZO1 + 0.6 + 0.28 * k, -0.18 * k), (ZO1 + 0.6 + 0.28 * k, -0.18 * (k + 1))]
    prof = simple(prof + [(ZO1 + 0.6 + 0.28 * 8, -0.18 * 8), (ZO1 + 0.6 + 0.28 * 8, -1.8), (ZO1, -1.8)])
    n.append(group('service_stair', [
        {'id': 'down', 'op': 'extrude', 'material': 'stair_s', 'depth': r(sb - sa + 0.4),
         'points': [[r(a_), r(b_)] for a_, b_ in prof], 'transform': {'rotate': [0, -90, 0], 'translate': [r((sa + sb) / 2), 0, 0]}},
        box('down_wall', (sb + 0.2, -1.8, ZO1), (sb + 0.4, WALL_H - 0.02, ZO1 + 3.0), 'stairwell', open=['bottom', 'back', 'left'],
            faces={'top': 'cut'}),
        box('exit_w', (sa + 0.3, 2.14, Z1 - 0.13), (sb - 0.3, 2.32, Z1 + 0.01), 'sign_box', open=['front'], faces={'back': 'exit_sign'})]))
    # beyond the east doorway: the chairman's private stair, up to his helipad
    ua, ub = UP_DOOR
    prof = [(XO1, -0.02)]
    for k in range(1, 12):
        prof += [(XO1 + 0.28 * (k - 1), 0.2 * k), (XO1 + 0.28 * k, 0.2 * k)]
    prof.append((XO1 + 0.28 * 11, -0.02))
    n.append(group('private_stair', [
        {'id': 'up', 'op': 'extrude', 'material': 'stair_s', 'depth': r(ub - ua - 0.02), 'points': [[r(a_), r(b_)] for a_, b_ in prof],
         'faces': {'back': 'cut'}, 'transform': {'translate': [0, 0, r((ua + ub) / 2)]}},
        box('up_wall', (XO1, -0.02, ua - 0.22), (XO1 + 3.2, WALL_H - 0.02, ua - 0.02), 'panel', open=['bottom', 'left'],
            faces={'top': 'cut', 'back': 'cut'}),
        box('exit_e', (X1 - 0.13, 2.14, 3.2 - 0.32), (X1 + 0.01, 2.32, 3.2 + 0.32), 'sign_box', open=['right'],
            faces={'left': 'exit_sign'})]))
    return n


def floor_recipe():
    lighting = {'direction': DIRECTION, 'ambient': AMBIENT, 'diffuse': DIFFUSE, 'lights': room_lights(),
                'refine': {'tolerance': 20, 'max_added': 240}}
    return recipe(P + 'floor', materials(), shell_nodes() + prop_nodes(), lighting, 2200)


# ---- nf_glass: the boardroom's walls

def glass_recipe():
    m = {'glass': {'color': '#a0c0d4', 'blend': 'quarter', 'double_sided': True},
         'post': {'color': '#c8a860'}, 'cut': {'color': '#8c9ab4', 'class': 'emissive'}}
    x0, z0, x1, z1 = BOARD
    g = Mesh()
    yt = CUT - 0.02
    xa, xb, za, zb = x0 + GT / 2, x1 - GT / 2, z0 + GT / 2, z1 - GT / 2
    g.quad(xa, 0.02, za, xb, yt, za, (0, 0, -1))
    g.quad(xa, 0.02, zb, xb, yt, zb, (0, 0, -1))
    g.quad(xa, 0.02, za, xa, yt, zb, (1, 0, 0))
    g.quad(xb, 0.02, za, xb, yt, zb, (1, 0, 0))
    n = [g.node('glass', 'glass')]
    n.append(box('cut_s', (xa - 0.02, yt, za - 0.02), (xb + 0.02, CUT, za + 0.02), 'cut'))
    n.append(box('cut_n', (xa - 0.02, yt, zb - 0.02), (xb + 0.02, CUT, zb + 0.02), 'cut'))
    n.append(box('cut_w', (xa - 0.02, yt, za + 0.02), (xa + 0.02, CUT, zb - 0.02), 'cut', open=['back', 'front']))
    n.append(box('cut_e', (xb - 0.02, yt, za + 0.02), (xb + 0.02, CUT, zb - 0.02), 'cut', open=['back', 'front']))
    for k, (xx, zz) in enumerate(((xa, za), (xb, za), (xa, zb), (xb, zb))):
        n.append(box(f'post_{k}', (xx - 0.045, -0.02, zz - 0.045), (xx + 0.045, CUT + 0.01, zz + 0.045), 'post', open=['bottom'],
                     faces={'top': 'cut'}))
    lighting = {'direction': DIRECTION, 'ambient': AMBIENT + 0.1, 'diffuse': DIFFUSE,
                'lights': lights_named('city', 'night', 'chandelier'), 'refine': {'max_added': 0}}
    return recipe(P + 'glass', m, n, lighting, 200)


# ---- collision and placements

def collision():
    op = ['bottom', 'top']
    f = Mesh()
    f.quad(XO0, 0, ZO0, XO1, 0, ZO1, (0, 1, 0))
    sa, sb = STAIR_DOOR
    cx0, cz0, cx1, cz1 = CORE
    c0, d0, c1, d1 = CUPBOARD
    a, b = OFFICE_WALL
    n = [f.node('slab', 'floor'),
         box('front_wall', (XO0, 0, ZO0), (XO1, CUT, Z0), 'floor', open=op),
         box('back_0', (XO0, 0, Z1), (sa, WALL_H, ZO1), 'floor', open=op),
         box('back_1', (sb, 0, Z1), (XO1, WALL_H, ZO1), 'floor', open=op),
         box('end_w', (XO0, 0, Z0), (X0, WALL_H, Z1), 'floor', open=op + ['back', 'front']),
         box('end_e_0', (X1, 0, Z0), (XO1, WALL_H, UP_DOOR[0]), 'floor', open=op + ['back']),
         box('end_e_1', (X1, 0, UP_DOOR[1]), (XO1, WALL_H, Z1), 'floor', open=op + ['front']),
         box('core', (cx0, 0, cz0), (cx1, WALL_H, cz1), 'floor', open=op + ['front']),
         box('cup_s', (c0, 0, d0), (c1, 2.0, d0 + 0.2), 'floor', open=op + ['left']),
         box('cup_n', (c0, 0, d1 - 0.2), (c1, 2.0, d1), 'floor', open=op + ['left']),
         box('office_a', (cx1, 0, a), (OFFICE_DOOR[0], WALL_H, b), 'floor', open=op + ['left']),
         box('office_b', (OFFICE_DOOR[1], 0, a), (X1, WALL_H, b), 'floor', open=op + ['right']),
         box('desk', (DESK[0], 0, DESK[1]), (DESK[2], 0.75, DESK[3]), 'floor', open=op)]
    x0, z0, x1, z1 = BOARD
    n += [box('board_s', (x0, 0, z0), (x1, WALL_H, z0 + GT), 'floor', open=op),
          box('board_n', (x0, 0, z1 - GT), (x1, WALL_H, z1), 'floor', open=op),
          box('board_w', (x0, 0, z0 + GT), (x0 + GT, WALL_H, z1 - GT), 'floor', open=op + ['back', 'front']),
          box('board_e', (x1 - GT, 0, z0 + GT), (x1, WALL_H, z1 - GT), 'floor', open=op + ['back', 'front'])]
    for k, (a_, b_, c_, d_) in enumerate(CRATES):
        n.append(box(f'crate_{k}', (a_, 0, b_), (c_, 1.8, d_), 'floor', open=op))
    return collision_recipe(P + 'floor_col', n)


def placements():
    return [{'id': P + 'floor', 'asset': P + 'floor', 'position': [0, 0, 0], 'collision': P + 'floor_col'},
            {'id': P + 'glass', 'asset': P + 'glass', 'position': [0, 0, 0], 'collision': 'none'}]   # in nf_floor_col


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--no-placements', action='store_true', help='leave ninth.placements.json as it is')
    args = ap.parse_args()
    draw_art()
    write_json(HERE / f'{P}floor.asset.json', floor_recipe())
    write_json(HERE / f'{P}floor_col.asset.json', collision())
    write_json(HERE / f'{P}glass.asset.json', glass_recipe())
    if not args.no_placements:
        write_json(HERE / 'ninth.placements.json', {'format': 'after-hours-placements', 'version': 1,
                                                    'room': 'ninth', 'placements': placements()})
    print('wrote nf_floor, nf_floor_col, nf_glass and', len(list(ART.glob('*.png'))), 'textures')


if __name__ == '__main__':
    main()
