#!/usr/bin/env python3
"""The tower, the trading floor (6F), dressed: writes its Asset Kit recipes, draws their textures
and writes the room's placements.

    python3 carts/afterhours/rooms/trading/dress_trading.py [--no-placements]

A securities house's dealing room at night in 1990, the bubble's money room. Writes, beside itself:
  tf_floor.asset.json      the floor (painted: carpet tiles, the city's light through the window
                           and its blinds) and the back wall (painted: the quote board, its rows
                           stopped at the close), the walls and lintels, the front's face (painted:
                           the tower's granite spandrel and its bronze glass, in section), the back
                           office's partition and its desk, safe and cabinets, the columns, the
                           dealers' desks with their dark screens, phones and chairs, the meeting
                           room's table and chairs, the hall's glass doors beyond the east doorway
                           and the service stair beyond the back one; lit by ROOM_LIGHTS
  tf_floor_col.asset.json  its collision: the floor, the walls without tops, the partition, the
                           desks, the columns, the meeting room
  tf_glass.asset.json      the meeting room's glass and posts, cut at 1 m (its own recipe, lit at its
                           corners only, so that no light refines its glass)
  trading.placements.json  the placements (replace the greybox's)
  art/*.png                the paintings, the screens, the quote board's rows

PLAN.md is the room's floor plan (the level lead's); this keeps what it says must stay: the back
office's partition, doorway, desk and stair door, the camera's place; the meeting room's glass
closed and see-through (its blinds are on the window, and only light); the columns; the desks low
(their screens dark and under 0.9 m); the front strip east of the meeting room, the strip north of
it and the west end clear; the front cut at 1 m. The light is ../passage/diorama.py's method.
Everything named here is fictional. Needs Pillow and NumPy.
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
P = 'tf_'

# ---- the plan (PLAN.md and trading.play.json)
X0, X1 = -9.0, 9.0
Z0, Z1 = -4.5, 4.5
T = 0.25
XO0, XO1, ZO0, ZO1 = X0 - T, X1 + T, Z0 - T, Z1 + T
SLAB = 0.4
HALL_DOOR = (-3.6, -2.4)        # east wall, z
STAIR_DOOR = (-8.6, -7.4)       # back wall, x
LINTEL = 2.1
OFFICE_S = (0.9, 1.05)          # the partition's south side: z, from X0 to -5.4, its doorway x -7.9 ... -6.7
OFFICE_DOOR = (-7.9, -6.7)
OFFICE_E = (-5.55, -5.4)        # its east side: x, from z 1.05 to the back wall
OFFICE_DESK = (-7.4, 3.6, -5.55, 4.5)
MEET = (-1.6, -4.5, 2.5, -1.8)  # the meeting room's glass: x0, z0, x1, z1
GT = 0.15                       # its walls' thickness
MEET_TABLE = (-0.5, -3.6, 1.4, -2.6)
DESKS = [(-4.6, 1.8, -0.6, 2.6), (0.4, 1.8, 4.4, 2.6), (5.2, 1.8, 8.0, 2.6), (4.0, -3.4, 7.2, -2.6)]
DESK_H, TOP_H = 0.9, 0.72
COLUMNS = [(-4.4, -1.4, -3.7, -0.7), (3.5, -1.4, 4.2, -0.7)]
SAFE = (-6.15, 1.25, -5.6, 1.8)
CABINETS = (-8.98, 1.3, -8.55, 3.1)
BOARD = (-5.4, 9.0, 0.3, 2.3)   # the quote board on the back wall: x0, x1, y0, y1
LIT_SCREENS = [(1.4, 2.2), (6.2, -3.0)]     # two screens left on, at desks: x, z

# ---- the light
AMBIENT, DIFFUSE = 0.06, 0.04
DIRECTION = [0.0, 1.0, -0.4]
CITY = '#a8c0f0'


def room_lights():
    return [
        {'id': 'city_w', 'at': [-4.5, 4.0, -9.5], 'color': CITY, 'intensity': 2.6, 'range': 15.0,
         'shadows': True, 'radius': 0.4},
        {'id': 'city_e', 'at': [5.0, 4.5, -9.0], 'color': '#c0b0e0', 'intensity': 2.2, 'range': 15.0,
         'shadows': True, 'radius': 0.4},
        {'id': 'night', 'at': [0.0, 7.0, 0.0], 'color': '#5c6c9c', 'intensity': 0.45, 'range': 18.0},
        {'id': 'board', 'at': [2.0, 1.1, Z1 - 0.4], 'color': '#ffb050', 'intensity': 1.6, 'range': 4.2},
        {'id': 'lamp', 'at': [-6.0, 1.05, 4.0], 'color': '#ffe0a0', 'intensity': 1.6, 'range': 2.6,
         'shadows': True, 'radius': 0.1},
        {'id': 'screen_0', 'at': [LIT_SCREENS[0][0], 0.85, LIT_SCREENS[0][1] - 0.45], 'color': '#70ffa0', 'intensity': 1.0,
         'range': 1.8},
        {'id': 'screen_1', 'at': [LIT_SCREENS[1][0], 0.85, LIT_SCREENS[1][1] + 0.45], 'color': '#70ffa0', 'intensity': 1.0,
         'range': 1.8},
        {'id': 'hall', 'at': [X1 + 1.2, 2.0, -3.0], 'color': '#ffe8c8', 'intensity': 2.4, 'range': 4.6,
         'shadows': True, 'radius': 0.3},
        {'id': 'stair', 'at': [-8.0, 1.8, Z1 + 1.2], 'color': '#c8f0d8', 'intensity': 1.8, 'range': 3.4,
         'shadows': True, 'radius': 0.2},
        {'id': 'exit_sign', 'at': [-8.0, 2.2, Z1 - 0.15], 'color': '#60ff90', 'intensity': 0.6, 'range': 1.6},
    ]


def lights_named(*prefixes):
    return [l for l in room_lights() if l['id'].startswith(prefixes)]


MULLIONS = [X0 + 1.5 * k for k in range(1, 12)]
BLIND_Y = 1.7                   # the window's blinds, half down: slats from here to the ceiling


def blockers():
    """The painted shadows' casters, at their height in the story: the window's spandrel, posts and
    the wall above it, the blinds' slats (over the meeting room's window), the partition, the
    columns, the desks, the walls with their doorways."""
    out = [(XO0 - 6, WALL_H + 0.3, ZO0 - 0.2, XO1 + 6, 9, Z0), (XO0, -1, ZO0, XO1, 0.85, Z0)]
    out += [(x - 0.05, -1, ZO0, x + 0.05, 4, Z0) for x in MULLIONS]
    for k in range(9):
        y = BLIND_Y + k * 0.08
        out.append((MEET[0] - 0.3, y, ZO0, MEET[2] + 0.3, y + 0.035, Z0))
    a, b = OFFICE_S
    out += [(X0, -1, a, OFFICE_DOOR[0], 4, b), (OFFICE_DOOR[1], -1, a, OFFICE_E[1], 4, b),
            (OFFICE_E[0], -1, b, OFFICE_E[1], 4, Z1)]
    out += [(c0, -1, d0, c1, 4, d1) for c0, d0, c1, d1 in COLUMNS]
    out += [(c0, -1, d0, c1, DESK_H, d1) for c0, d0, c1, d1 in DESKS]
    out.append((MEET_TABLE[0], 0.7, MEET_TABLE[1], MEET_TABLE[2], 0.75, MEET_TABLE[3]))
    out += [(X1, -1, ZO0, XO1, 4, HALL_DOOR[0]), (X1, -1, HALL_DOOR[1], XO1, 4, ZO1), (X1, LINTEL, HALL_DOOR[0], XO1, 4, HALL_DOOR[1]),
            (XO0, -1, ZO0, X0, 4, ZO1),
            (XO0 - 3, -1, Z1, STAIR_DOOR[0], 4, ZO1), (STAIR_DOOR[1], -1, Z1, XO1 + 3, 4, ZO1),
            (STAIR_DOOR[0], LINTEL, Z1, STAIR_DOOR[1], 4, ZO1)]
    return out


# ---- the floor

FLOOR_X = [XO0, -3.0833, 3.0833, XO1]
FLOOR_Z = [ZO0, 0.0, ZO1]
FLOOR_TEX = (148, 114)


def floor_base(x, z):
    """In white light: blue-grey carpet tiles laid in alternating grain, darker under the desks
    and round the rows (where the cables run), the meeting room's plum carpet, the back office's
    vinyl, a pale threshold at each door."""
    rng = np.random.default_rng(101)
    h, w = x.shape
    tile = 0.5
    ix, iz = np.floor(x / tile), np.floor(z / tile)
    grain = ((ix + iz) % 2 == 0)
    var = (np.sin(ix * 12.9898 + iz * 78.233) * 43758.5453) % 1.0
    stripe = np.where(grain, np.sin(x * 60) * 0.5 + 0.5, np.sin(z * 60) * 0.5 + 0.5)
    base = np.zeros((h, w, 3)) + np.array([118, 126, 144])
    base *= (0.95 + 0.06 * var + 0.04 * stripe)[..., None]
    base += (rng.random((h, w)) - 0.5)[..., None] * 8
    for (a, b, c, d) in DESKS:
        under = soft_rect(x, z, a - 0.5, c + 0.5, b - 0.55, d + 0.55, 0.1)
        base *= (1 - 0.12 * under)[..., None]
    mx0, mz0, mx1, mz1 = MEET
    room = (x > mx0) & (x < mx1) & (z > mz0) & (z < mz1)
    base = np.where(room[..., None], np.array([104, 70, 92]) * (0.95 + 0.08 * rng.random((h, w)))[..., None], base)
    office = (x < OFFICE_E[1]) & (z > OFFICE_S[0])
    vinyl = np.array([150, 146, 132]) - (((x / 0.3) % 1.0 < 0.06) | ((z / 0.3) % 1.0 < 0.06))[..., None] * 18
    base = np.where(office[..., None], vinyl, base)
    for cond in ((x > X1 - 0.3) & (z > HALL_DOOR[0]) & (z < HALL_DOOR[1]),
                 (z > Z1 - 0.3) & (x > STAIR_DOOR[0]) & (x < STAIR_DOOR[1])):
        base = np.where(cond[..., None], np.array([170, 168, 160]), base)
    return base


def floor_paint(x, z):
    y = np.zeros_like(x)
    rgb = floor_base(x, z) * shade(x, y, z, (0, 1, 0), room_lights(), AMBIENT, DIFFUSE, DIRECTION, blockers())
    # the quote board's rows of light in the floor before it
    t30 = math.tan(math.radians(30))
    g = soft_rect(x, z, BOARD[0] + 0.3, BOARD[1] - 0.3, Z1 - 0.3 - 0.9 * t30, Z1 - 0.3, 0.6)
    rgb += (g * 0.06)[..., None] * np.array([255, 170, 80])
    return rgb


# ---- the back wall

WALL_X = [XO0, 0.0, XO1]
WALL_TEX = (240, 52)


def wall_base(x, y):
    """In white light: pale grey panels, a dark skirting; the back office's cork board; the quote
    board, a black field of amber, red and green rows (the close: a few up, most of the morning
    down; shapes, not numbers); the stair door's frame."""
    rng = np.random.default_rng(103)
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array([176, 176, 172])
    base -= ((np.abs((x / 1.2) % 1.0 - 0.5) > 0.49))[..., None] * np.array([22, 22, 22])
    base = np.where((y < 0.1)[..., None], np.array([56, 56, 60]), base)
    cork = (x > -8.3) & (x < -6.0) & (y > 1.1) & (y < 1.9)
    base = np.where(cork[..., None], np.array([170, 128, 84]), base)
    bx0, bx1, by0, by1 = BOARD
    board = (x > bx0) & (x < bx1) & (y > by0) & (y < by1)
    base = np.where(board[..., None], np.array([14, 14, 18]), base)
    rows = np.floor((y - by0) / 0.14)
    cols = np.floor((x - bx0) / 0.6)
    pick = (np.sin(rows * 37.1 + cols * 11.3) * 4373.1) % 1.0
    inrow = board & (((y - by0) / 0.14) % 1.0 > 0.3) & (((y - by0) / 0.14) % 1.0 < 0.75)
    name = inrow & (((x - bx0) / 0.6) % 1.0 < 0.38)
    price = inrow & (((x - bx0) / 0.6) % 1.0 > 0.45) & (((x - bx0) / 0.6) % 1.0 < 0.9)
    base = np.where(name[..., None], np.array([240, 170, 60]), base)
    col = np.where((pick < 0.3)[..., None], np.array([240, 60, 50]), np.array([60, 200, 90]))
    base = np.where(price[..., None], col, base)
    sx0, sx1 = STAIR_DOOR
    frame = (x > sx0 - 0.1) & (x < sx1 + 0.1) & (y < LINTEL + 0.1)
    base = np.where(frame[..., None], np.array([110, 112, 118]), base)
    base += (rng.random((h, w)) - 0.5)[..., None] * 5
    return base


def wall_paint(x, y, z):
    rgb = wall_base(x, y) * shade(x, y, z, (0, 0, -1), room_lights(), AMBIENT, DIFFUSE, DIRECTION, blockers())
    bx0, bx1, by0, by1 = BOARD
    lit = (x > bx0) & (x < bx1) & (y > by0) & (y < by1)
    return np.where(lit[..., None], wall_base(x, y) * 0.92 + 4, rgb)


def front_face(a, b, w=240, h=20):
    """The front wall's face, the tower's skin in section: the slab pale (cut), the polished pink
    granite spandrel, the bronze glass above it with the city in it, a post every 1.5 m."""
    xs = a + (np.arange(w) + 0.5) / w * (b - a)
    ys = CUT - (np.arange(h) + 0.5) / h * (CUT + SLAB)
    x, y = np.meshgrid(xs, ys)
    rng = np.random.default_rng(int(a * 10) + 700)
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

def screen(lit):
    """A dealer's screen: dark glass, or one left on with green rows."""
    img = Image.new('RGB', (8, 6), (16, 22, 24))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 7, 5], outline=(70, 72, 70))
    if lit:
        for yy in (1, 2, 3, 4):
            d.line([(1, yy), (2 + (yy * 3) % 5, yy)], fill=(80, 255, 140))
    return img


def desk_top():
    """A double desk's top from above (fit along its length): grey laminate, a phone turret at each
    place on both sides (key fields, a few lit keys), papers, an ashtray here and there."""
    w, h = 80, 16
    img = Image.new('RGB', (w, h), (92, 90, 86))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(3)
    for i in range(5):
        cx = 8 + i * 16
        for y0 in (1, h - 5):
            d.rectangle([cx - 4, y0, cx + 4, y0 + 3], fill=(48, 50, 54))
            for kx in range(3):
                d.point((cx - 3 + kx * 3, y0 + 1), fill=(240, 120, 60) if rng.random() < 0.3 else (170, 170, 160))
        if rng.random() < 0.6:
            d.rectangle([cx + 5, 2, cx + 8, 5], fill=(226, 224, 214))
        if rng.random() < 0.4:
            d.ellipse([cx - 7, h - 6, cx - 5, h - 4], fill=(200, 204, 208))
    return img


def chair(side):
    """A dealer's chair from above: its seat, its back along the side away from the desk."""
    img = Image.new('RGB', (8, 8), (58, 60, 72))
    d = ImageDraw.Draw(img)
    if side > 0:
        d.rectangle([0, 0, 7, 1], fill=(30, 32, 40))
    else:
        d.rectangle([0, 6, 7, 7], fill=(30, 32, 40))
    return img


def safe_face():
    img = Image.new('RGB', (10, 10), (44, 70, 56))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 9, 9], outline=(24, 40, 32))
    d.ellipse([3, 3, 6, 6], outline=(210, 180, 100))
    d.line([(7, 4), (8, 4)], fill=(210, 180, 100))
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
    screen(False).save(ART / 'screen.png')
    screen(True).save(ART / 'screen_on.png')
    desk_top().save(ART / 'desk_top.png')
    chair(1).save(ART / 'chair_n.png')
    chair(-1).save(ART / 'chair_s.png')
    safe_face().save(ART / 'safe.png')
    exit_sign().save(ART / 'exit_sign.png')
    section_face(16, 16, (140, 154, 180), (88, 96, 116)).save(ART / 'cut.png')


# ---- tf_floor

def materials():
    m = {
        'cut': {'color': '#8c9ab4', 'class': 'emissive'},
        'cut_tex': {'color': '#8c9ab4', 'class': 'emissive', 'texture': {'image': 'art/cut.png', 'bits': 4, 'projection': 'fit'}},
        'end_wall': {'color': '#b0b0ac'}, 'lintel': {'color': '#5c5e64'},
        'door_light': {'color': '#ffe8c8', 'class': 'emissive'},
        'partition': {'color': '#a8a49a'}, 'jamb': {'color': '#5a5c62'},
        'column': {'color': '#c8bcb0'},
        'desk': {'color': '#8c8a84'}, 'divider': {'color': '#3c3e44'},
        'desk_top': {'color': '#5c5a58', 'texture': {'image': 'art/desk_top.png', 'bits': 4, 'projection': 'fit'}},
        'monitor': {'color': '#c4c0b0'},
        'screen': {'color': '#202428', 'texture': {'image': 'art/screen.png', 'bits': 4, 'projection': 'fit'}},
        'screen_on': {'color': '#40c070', 'class': 'emissive', 'texture': {'image': 'art/screen_on.png', 'bits': 4, 'projection': 'fit'}},
        'turret': {'color': '#3c3e44', 'texture': {'image': 'art/turret.png', 'bits': 4, 'projection': 'fit'}},
        'chair': {'color': '#2c2e36'}, 'chair_seat': {'color': '#3a3c48'},
        'chair_n': {'color': '#3a3c48', 'texture': {'image': 'art/chair_n.png', 'bits': 4, 'projection': 'fit'}},
        'chair_s': {'color': '#3a3c48', 'texture': {'image': 'art/chair_s.png', 'bits': 4, 'projection': 'fit'}},
        'table': {'color': '#5a3c2c'}, 'ashtray': {'color': '#d0d4d8'},
        'office_desk': {'color': '#7a6450'}, 'lamp_shade': {'color': '#40c070', 'class': 'emissive'},
        'lamp_brass': {'color': '#c8a050'},
        'safe': {'color': '#3c5c4a', 'texture': {'image': 'art/safe.png', 'bits': 4, 'projection': 'fit'}},
        'safe_body': {'color': '#2c4438'}, 'cabinet': {'color': '#9a9c98'},
        'stair': {'color': '#8a8c90'}, 'stairwell': {'color': '#a0a098'}, 'handrail': {'color': '#c8ccd4'},
        'hall_floor': {'color': '#b0a490'}, 'hall_glass': {'color': '#a8c8d8'}, 'hall_frame': {'color': '#c0a060'},
        'exit_sign': {'color': '#30c060', 'class': 'emissive', 'texture': {'image': 'art/exit_sign.png', 'bits': 4, 'projection': 'fit'}},
        'sign_box': {'color': '#50525a'},
    }
    for j in range(2):
        for i in range(3):
            m[f'floor_{j}{i}'] = {'color': '#5c6474', 'class': 'emissive',
                                  'texture': {'image': f'art/floor_{j}{i}.png', 'bits': 8, 'projection': 'fit'}}
    for k in range(2):
        m[f'wall_{k}'] = {'color': '#6c6c6c', 'class': 'emissive',
                          'texture': {'image': f'art/wall_{k}.png', 'bits': 8, 'projection': 'fit'}}
        m[f'front_{k}'] = {'color': '#7c5c50', 'class': 'emissive',
                           'texture': {'image': f'art/front_{k}.png', 'bits': 4, 'projection': 'fit'}}
    return m


def shell_nodes():
    f = Mesh()
    painted_floor(f, FLOOR_X, FLOOR_Z, [], 'floor_{}{}')
    for k, (a, b) in enumerate(zip(WALL_X, WALL_X[1:])):
        f.quad(a, -SLAB, ZO0, b, CUT, ZO0, (0, 0, -1), f'front_{k}',        # hand UVs: the mesh has them
               (lambda a, b: lambda p: ((p[0] - a) / (b - a), (CUT - p[1]) / (CUT + SLAB)))(a, b))
    n = [f.node('floor', 'floor_00')]
    w = Mesh()
    sa, sb = STAIR_DOOR
    for a, b in ((XO0, sa), (sb, XO1)):
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
    ha, hb = HALL_DOOR
    n.append(box('end_e_0', (X1, -0.02, Z0), (XO1, WALL_H - 0.02, ha), 'end_wall', open=['bottom'],
                 faces={'top': 'cut', 'back': 'cut'}))
    n.append(box('end_e_1', (X1, -0.02, hb), (XO1, WALL_H - 0.02, Z1 + 0.01), 'end_wall', open=['bottom', 'front'],
                 faces={'top': 'cut'}))
    n.append(box('end_e_lintel', (X1 + 0.012, LINTEL, ha - 0.01), (XO1 - 0.012, WALL_H - 0.03, hb + 0.01), 'lintel',
                 open=['back', 'front'], faces={'top': 'cut', 'bottom': 'door_light'}))
    # the back office's partition, cut at 1 m like everything in play, its doorway framed
    a, b = OFFICE_S
    da, db = OFFICE_DOOR
    ea, eb = OFFICE_E
    n.append(box('part_s_a', (X0 - 0.01, -0.02, a), (da, CUT, b), 'partition', open=['bottom', 'left'], faces={'top': 'cut'}))
    n.append(box('part_s_b', (db, -0.02, a), (eb, CUT, b), 'partition', open=['bottom'], faces={'top': 'cut'}))
    n.append(box('part_e', (ea, -0.02, b), (eb, CUT, Z1 + 0.01), 'partition', open=['bottom', 'front', 'back'],
                 faces={'top': 'cut'}))
    for k, xx in enumerate((da, db)):
        n.append(box(f'jamb_{k}', (xx - 0.03, -0.02, a - 0.02), (xx + 0.03, CUT + 0.004, b + 0.02), 'jamb', open=['bottom'],
                     faces={'top': 'cut'}))
    for k, (c0, d0, c1, d1) in enumerate(COLUMNS):
        n.append(box(f'column_{k}', (c0, -0.02, d0), (c1, CUT, d1), 'column', open=['bottom'], faces={'top': 'cut_tex'}))
    return n


def desk_row(k, a, b, c, d):
    """A double row of dealers' desks: the desks (their tops painted with the phone turrets), a
    low divider down the middle, a pair of dark screens back to back every 0.8 m, the chairs pushed
    in (a seat seen from above, its back painted on it)."""
    n = [box(f'desk_{k}', (a, -0.02, b), (c, TOP_H, d), 'desk', open=['bottom'], faces={'top': 'desk_top'}),
         box(f'divider_{k}', (a + 0.05, TOP_H - 0.01, (b + d) / 2 - 0.02), (c - 0.05, TOP_H + 0.06, (b + d) / 2 + 0.02), 'divider',
             open=['bottom'])]
    zm = (b + d) / 2
    rng = np.random.default_rng(k)
    for i, x in enumerate(np.arange(a + 0.4, c - 0.2, 0.8)):
        lit = [any(abs(x - lx) < 0.4 and abs(zz - lz) < 0.3 for lx, lz in LIT_SCREENS) for zz in (zm - 0.2, zm + 0.2)]
        n.append(box(f'mon_{k}_{i}', (x - 0.17, TOP_H - 0.01, zm - 0.3), (x + 0.17, DESK_H - 0.01, zm + 0.3), 'monitor',
                     open=['bottom'], faces={'back': 'screen_on' if lit[0] else 'screen',
                                             'front': 'screen_on' if lit[1] else 'screen'}))
        for s in (-1, 1):
            if b < -2 and s < 0:        # the front row's chairs are on its north side only (the front strip is walked)
                continue
            cz = d + 0.27 if s > 0 else b - 0.27
            jx = (rng.random() - 0.5) * 0.14
            n.append(box(f'chair_{k}_{i}_{s + 1}', (x - 0.22 + jx, 0.4, cz - 0.21), (x + 0.22 + jx, 0.48, cz + 0.21),
                         'chair_n' if s > 0 else 'chair_s'))
    return group(f'desks_{k}', n)


def prop_nodes():
    n = [desk_row(k, *d) for k, d in enumerate(DESKS)]
    # the meeting room: its table, chairs round it, a phone and an ashtray
    a, b, c, d = MEET_TABLE
    meet = [box('meet_table', (a, 0.7, b), (c, 0.75, d), 'table'),
            box('meet_leg', (a + 0.3, -0.02, b + 0.25), (c - 0.3, 0.705, d - 0.25), 'table', open=['bottom', 'top']),
            at({'id': 'ashtray', 'op': 'cylinder', 'radius': 0.08, 'height': 0.03, 'segments': 6, 'material': 'ashtray'},
               translate=[r((a + c) / 2), 0.76, r((b + d) / 2)])]
    for k, (x, z) in enumerate([(a + 0.4, b - 0.3), (c - 0.4, b - 0.3), (a + 0.4, d + 0.3), (c - 0.4, d + 0.3), ((a + c) / 2, d + 0.3)]):
        meet.append(box(f'meet_chair_{k}', (x - 0.22, 0.4, z - 0.2), (x + 0.22, 0.47, z + 0.2), 'chair_seat'))
    n.append(group('meeting', meet))
    # the back office: its desk, the green-shaded lamp, the safe, the cabinets
    oa, ob, oc, od = OFFICE_DESK
    n.append(group('office', [
        box('office_desk', (oa, -0.02, ob), (oc - 0.01, 0.75, od - 0.01), 'office_desk', open=['bottom']),
        box('lamp_base', (-6.06, 0.745, 3.94), (-5.94, 0.8, 4.06), 'lamp_brass'),
        box('lamp_stem', (-6.015, 0.79, 3.985), (-5.985, 0.98, 4.015), 'lamp_brass', open=['bottom', 'top']),
        at({'id': 'lamp_shade', 'op': 'cylinder', 'radius': 0.1, 'height': 0.05, 'segments': 6, 'material': 'lamp_shade'},
           translate=[-6.0, 0.97, 4.0], scale=[1.4, 1, 0.7]),
        box('safe', (SAFE[0], -0.02, SAFE[1]), (SAFE[2], 0.85, SAFE[3]), 'safe_body', open=['bottom'], faces={'back': 'safe'}),
        box('cabinets', (CABINETS[0], -0.02, CABINETS[1]), (CABINETS[2], 0.98, CABINETS[3]), 'cabinet', open=['bottom', 'left'])]))
    # beyond the east doorway: the lift hall's floor, its glass doors standing open against the walls
    ha, hb = HALL_DOOR
    n.append(group('hall', [
        box('hall_floor', (XO1, -0.4, ha - 0.8), (XO1 + 1.6, 0.0, hb + 0.8), 'hall_floor', open=['bottom', 'left'],
            faces={'back': 'cut'}),
        box('hall_leaf_s', (XO1 + 0.02, 0.0, ha - 0.62), (XO1 + 0.06, 2.06, ha - 0.02), 'hall_frame', open=['bottom']),
        box('hall_leaf_n', (XO1 + 0.02, 0.0, hb + 0.02), (XO1 + 0.06, 2.06, hb + 0.62), 'hall_frame', open=['bottom'])]))
    # beyond the back doorway: the house's service stair, rising west toward the ninth
    sa, sb = STAIR_DOOR
    prof = [(sb + 0.4, -0.02)]
    for k in range(10):
        prof += [(sb + 0.4 - 0.3 * k, 0.2 * (k + 1)), (sb + 0.4 - 0.3 * (k + 1), 0.2 * (k + 1))]
    prof.append((sb + 0.4 - 3.0, -0.02))
    n.append(group('stair', [
        box('landing', (sa - 0.3, -0.4, ZO1), (sb + 0.4, 0.0, ZO1 + 1.0), 'stair', open=['bottom', 'back', 'left', 'right', 'front']),
        {'id': 'steps', 'op': 'extrude', 'material': 'stair', 'depth': 1.0, 'points': [[r(a_), r(b_)] for a_, b_ in prof],
         'transform': {'translate': [0, 0, r(ZO1 + 1.5)]}},
        box('stair_back', (sb - 3.5, -0.02, ZO1 + 2.01), (sb + 0.6, WALL_H - 0.02, ZO1 + 2.2), 'stairwell', open=['bottom'],
            faces={'top': 'cut'}),
        box('exit_flag', (sa + 0.35, 2.14, Z1 - 0.13), (sb - 0.35, 2.32, Z1 + 0.01), 'sign_box', open=['front'],
            faces={'back': 'exit_sign'})]))
    return n


def floor_recipe():
    lighting = {'direction': DIRECTION, 'ambient': AMBIENT, 'diffuse': DIFFUSE, 'lights': room_lights(),
                'refine': {'tolerance': 20, 'max_added': 240}}
    return recipe(P + 'floor', materials(), shell_nodes() + prop_nodes(), lighting, 2200)


# ---- tf_glass: the meeting room's walls

def glass_recipe():
    m = {'glass': {'color': '#a0c0d4', 'blend': 'quarter', 'double_sided': True},
         'post': {'color': '#3c3e44'}, 'cut': {'color': '#8c9ab4', 'class': 'emissive'}}
    x0, z0, x1, z1 = MEET
    g = Mesh()
    yt = CUT - 0.02
    zg = z1 - GT / 2
    g.quad(x0, 0.02, zg, x1, yt, zg, (0, 0, -1))
    for xx in (x0 + GT / 2, x1 - GT / 2):
        g.quad(xx, 0.02, Z0 + 0.01, xx, yt, z1 - GT, (1, 0, 0))
    n = [g.node('glass', 'glass')]
    n.append(box('cut_n', (x0, yt, zg - 0.02), (x1, CUT, zg + 0.02), 'cut'))
    for k, xx in enumerate((x0 + GT / 2, x1 - GT / 2)):
        n.append(box(f'cut_{k}', (xx - 0.02, yt, Z0 + 0.01), (xx + 0.02, CUT, zg - 0.02), 'cut', open=['front']))
        n.append(box(f'post_{k}', (xx - 0.04, -0.02, zg - 0.04), (xx + 0.04, CUT + 0.01, zg + 0.04), 'post', open=['bottom'],
                     faces={'top': 'cut'}))
    for k, xx in enumerate(np.linspace(x0 + 1.0, x1 - 1.0, 3)):
        n.append(box(f'mullion_{k}', (xx - 0.02, -0.02, zg - 0.03), (xx + 0.02, CUT - 0.03, zg + 0.03), 'post', open=['bottom']))
    lighting = {'direction': DIRECTION, 'ambient': AMBIENT + 0.1, 'diffuse': DIFFUSE,
                'lights': lights_named('city', 'night'), 'refine': {'max_added': 0}}
    return recipe(P + 'glass', m, n, lighting, 200)


# ---- collision and placements

def collision():
    op = ['bottom', 'top']
    f = Mesh()
    f.quad(XO0, 0, ZO0, XO1, 0, ZO1, (0, 1, 0))
    sa, sb = STAIR_DOOR
    a, b = OFFICE_S
    n = [f.node('slab', 'floor'),
         box('front_wall', (XO0, 0, ZO0), (XO1, CUT, Z0), 'floor', open=op),
         box('back_0', (XO0, 0, Z1), (sa, WALL_H, ZO1), 'floor', open=op),
         box('back_1', (sb, 0, Z1), (XO1, WALL_H, ZO1), 'floor', open=op),
         box('end_w', (XO0, 0, Z0), (X0, WALL_H, Z1), 'floor', open=op + ['back', 'front']),
         box('end_e_0', (X1, 0, Z0), (XO1, WALL_H, HALL_DOOR[0]), 'floor', open=op + ['back']),
         box('end_e_1', (X1, 0, HALL_DOOR[1]), (XO1, WALL_H, Z1), 'floor', open=op + ['front']),
         box('part_s_a', (X0, 0, a), (OFFICE_DOOR[0], WALL_H, b), 'floor', open=op + ['left']),
         box('part_s_b', (OFFICE_DOOR[1], 0, a), (OFFICE_E[1], WALL_H, b), 'floor', open=op),
         box('part_e', (OFFICE_E[0], 0, b), (OFFICE_E[1], WALL_H, Z1), 'floor', open=op + ['back', 'front']),
         box('office_desk', OFFICE_DESK[:1] + (0,) + OFFICE_DESK[1:2], (OFFICE_DESK[2], 0.75, OFFICE_DESK[3]), 'floor', open=op)]
    for k, (c0, d0, c1, d1) in enumerate(DESKS):
        n.append(box(f'desk_{k}', (c0, 0, d0), (c1, DESK_H, d1), 'floor', open=op))
    for k, (c0, d0, c1, d1) in enumerate(COLUMNS):
        n.append(box(f'column_{k}', (c0, 0, d0), (c1, WALL_H, d1), 'floor', open=op))
    x0, z0, x1, z1 = MEET
    n += [box('meet_w', (x0, 0, Z0 + 0.01), (x0 + GT, WALL_H, z1 - GT), 'floor', open=op + ['back', 'front']),
          box('meet_e', (x1 - GT, 0, Z0 + 0.01), (x1, WALL_H, z1 - GT), 'floor', open=op + ['back', 'front']),
          box('meet_n', (x0, 0, z1 - GT), (x1, WALL_H, z1), 'floor', open=op)]
    return collision_recipe(P + 'floor_col', n)


def placements():
    return [{'id': P + 'floor', 'asset': P + 'floor', 'position': [0, 0, 0], 'collision': P + 'floor_col'},
            {'id': P + 'glass', 'asset': P + 'glass', 'position': [0, 0, 0], 'collision': 'none'}]   # in tf_floor_col


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--no-placements', action='store_true', help='leave trading.placements.json as it is')
    args = ap.parse_args()
    draw_art()
    write_json(HERE / f'{P}floor.asset.json', floor_recipe())
    write_json(HERE / f'{P}floor_col.asset.json', collision())
    write_json(HERE / f'{P}glass.asset.json', glass_recipe())
    if not args.no_placements:
        write_json(HERE / 'trading.placements.json', {'format': 'after-hours-placements', 'version': 1,
                                                      'room': 'trading', 'placements': placements()})
    print('wrote tf_floor, tf_floor_col, tf_glass and', len(list(ART.glob('*.png'))), 'textures')


if __name__ == '__main__':
    main()
