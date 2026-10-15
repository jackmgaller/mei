#!/usr/bin/env python3
"""Room 4, the tower's lobby, dressed: writes its Asset Kit recipes, draws their textures and
writes the room's placements.

    python3 carts/afterhours/rooms/lobby/dress_lobby.py [--no-placements]

Writes, beside itself:
  r4_lobby.asset.json      the lobby: the painted floor and back wall, the walls, the lifts, the
                           reception desk, the two planters and their palms, the sofa; lit by
                           ROOM_LIGHTS
  r4_lobby_col.asset.json  its collision: the floor, the walls, the desk, the planters, the
                           escalator's steps
  r4_escalator.asset.json  the stopped escalator: its steps, its stainless sides, its glass
                           balustrades and handrails (its own recipe, lit at its corners only, so no
                           light refines its glass)
  r4_front.asset.json      the glass front, cut at 1 m: its granite sill, glass, mullions and doors
                           (the same, for the same reason)
  lobby.placements.json    the placements (replace the greybox's)
  art/*.png                the floor and the back wall (painted as ROOM_LIGHTS light them), the
                           desk's logo, the lifts, the palms' fronds, the steps

PLAN.md is the room's floor plan (the level lead's); this keeps what it says must stay: the
escalator, its foot (the exit) and its balustrade at z 3.5-3.63, the desk where it is and opaque,
the planters, the walls, the front cut at 1 m, and open floor along both guards' lines and between
the desk and the escalator's foot. The light is the passage's method (../passage/diorama.py, whose
helpers this imports): one list for the kit's bake and the painting. The street's sodium lamps
stand outside the glass front; the painting lets them in through the glass between the mullions,
with the desk's and the palms' long shadows. Everything named here is fictional. Needs Pillow and
NumPy.
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
                     hex_rgb, quantise_together, r, recipe, shade, smoothstep, soft_rect, to_array, write_json)

ART = HERE / 'art'
P = 'r4_'

# ---- the plan (PLAN.md): x right, z away from the camera, the floor y = 0, metres
X0, X1 = -7.0, 7.0
Z0, Z1 = -4.75, 4.75
T = 0.25
XO0, XO1, ZO0, ZO1 = X0 - T, X1 + T, Z0 - T, Z1 + T
SLAB = 0.4
DESK = (-1.6, -0.5, 1.6, 0.4)
PLANTERS = [(-5.4, 0.6), (3.6, -2.2)]
PLANTER_S, PLANTER_H = 1.0, 0.55
ESC_X0, ESC_X1, ESC_Z0, ESC_Z1 = 1.0, 7.0, 3.5, 4.75
ESC_STEPS, ESC_RISE = 12, 0.19
BAL_Z = (3.5, 3.63)            # the balustrade, which blocks cones
LIFTS = [(-0.95, -0.05), (0.05, 0.95)]   # the lifts' doors in the east wall, z
ENTRY = (-4.5, -2.9)           # the door from the passage, in the west wall, z
LINTEL = 2.1
SOFA = (-6.97, -2.35, -6.15, -0.55)
MULLIONS = [X0 + 1.75 * k for k in range(1, 8) if k != 4]   # the glass front's posts; the doors between -0.9 and 0.9
SILL_H = 0.3
BOARD = (-4.8, -1.4, 0.3, 1.25)   # the directory board on the back wall, low enough to be in the picture: x, y

# ---- the light
AMBIENT, DIFFUSE = 0.06, 0.04
DIRECTION = [0.0, 1.0, -0.4]
SODIUM = '#ffa04a'


def room_lights():
    return [
        {'id': 'street_w', 'at': [-3.9, 3.6, -7.4], 'color': SODIUM, 'intensity': 3.0, 'range': 11.0,
         'shadows': True, 'radius': 0.12},
        {'id': 'street_e', 'at': [3.7, 3.6, -7.2], 'color': SODIUM, 'intensity': 2.6, 'range': 10.5,
         'shadows': True, 'radius': 0.12},
        {'id': 'across', 'at': [-0.5, 2.2, -9.5], 'color': '#5c9cff', 'intensity': 1.0, 'range': 11.0},
        {'id': 'night', 'at': [0.0, 7.0, 0.0], 'color': '#4c64a4', 'intensity': 0.36, 'range': 18.0},
        {'id': 'desk', 'at': [0.0, 0.8, 0.75], 'color': '#ffd8a0', 'intensity': 1.1, 'range': 2.4,
         'shadows': True, 'radius': 0.3},
        {'id': 'logo', 'at': [0.0, 0.55, -1.0], 'color': '#9cd4ff', 'intensity': 0.7, 'range': 1.9},
        {'id': 'lifts', 'at': [6.55, 2.2, 0.0], 'color': '#ffc884', 'intensity': 1.1, 'range': 2.8},
        {'id': 'comb', 'at': [1.15, 0.3, 4.12], 'color': '#9cffd0', 'intensity': 1.0, 'range': 1.6},
        {'id': 'downlight', 'at': [0.6, 2.4, 3.6], 'color': '#fff2dc', 'intensity': 1.5, 'range': 3.1,
         'shadows': True, 'radius': 0.2},
        {'id': 'downlight_w', 'at': [-2.2, 2.4, 2.3], 'color': '#dce6ff', 'intensity': 0.9, 'range': 2.8},
        {'id': 'board', 'at': [-3.1, 0.8, 4.2], 'color': '#e0ecff', 'intensity': 1.1, 'range': 2.5},
        {'id': 'stair', 'at': [-7.9, 0.7, -3.7], 'color': '#cdf0e0', 'intensity': 1.4, 'range': 2.8,
         'shadows': True, 'radius': 0.3},
    ]


def lights_near(names):
    return [dict(l) for l in room_lights() if l['id'] in names]


def foliage(px, pz, seed):
    """The palm's fronds as small boxes for the painted shadows (dappled)."""
    rng = np.random.default_rng(seed)
    out = []
    for k in range(9):
        a = math.tau * k / 9 + rng.random() * 0.3
        d = 0.35 + rng.random() * 0.45
        y = 1.1 + rng.random() * 0.6
        cx, cz = px + d * math.cos(a), pz + d * math.sin(a)
        s = 0.12 + rng.random() * 0.08
        out.append((cx - s, y - 0.06, cz - s, cx + s, y + 0.06, cz + s))
    out.append((px - 0.08, 0, pz - 0.08, px + 0.08, 1.7, pz + 0.08))
    return out


def blockers():
    """What throws the painted shadows, at its height in the story: the glass front's posts and
    the wall above the glass, the walls and their door, the desk, the planters and their palms,
    the escalator, the sofa."""
    out = [(XO0 - 6, WALL_H, ZO0 - 0.2, XO1 + 6, 9, Z0), (XO0, 0, ZO0, XO1, SILL_H, Z0)]
    for x in MULLIONS + [-0.9, 0.0, 0.9]:
        out.append((x - 0.06, 0, ZO0, x + 0.06, WALL_H, Z0))
    out += [(XO0, -1, ZO0, X0, 4, ENTRY[0]), (XO0, -1, ENTRY[1], X0, 4, ZO1), (XO0, LINTEL, ENTRY[0], X0, 4, ENTRY[1]),
            (X1, -1, ZO0, XO1, 4, ZO1)]
    x0, z0, x1, z1 = DESK
    out.append((x0, 0, z0, x1, 1.05, z1))
    for k, (px, pz) in enumerate(PLANTERS):
        s = PLANTER_S / 2
        out.append((px - s, 0, pz - s, px + s, PLANTER_H, pz + s))
        out += foliage(px, pz, k)
    for k in range(ESC_STEPS):
        xa = ESC_X0 + (ESC_X1 - ESC_X0) * k / ESC_STEPS
        out.append((xa, 0, ESC_Z0, ESC_X1, ESC_RISE * (k + 1) + 0.9, ESC_Z1))
    out.append((SOFA[0], 0, SOFA[1], SOFA[2], 0.8, SOFA[3]))
    return out


# ---- the floor

FLOOR_SPLIT_X = [XO0, 0.0, XO1]
FLOOR_SPLIT_Z = [ZO0, 0.0, ZO1]
FLOOR_TEX = (174, 120)


def floor_base(x, z):
    """Polished granite in white light: black with a grey fleck, in large slabs, a pale travertine
    border, a rosette inlaid before the desk, the doors' mat, the escalator's landing plate."""
    rng = np.random.default_rng(41)
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array([86, 86, 94])
    fleck = rng.random((h, w))
    base += (fleck > 0.9)[..., None] * np.array([12, 12, 13])
    base += (fleck < 0.06)[..., None] * np.array([-9, -9, -9])
    ix, iz = np.floor((x + 0.6) / 1.2), np.floor(z / 0.8)
    var = (np.sin(ix * 12.9898 + iz * 78.233) * 43758.5453) % 1.0
    base *= (0.94 + 0.12 * var)[..., None]
    joint = (np.abs(((x + 0.6) / 1.2) % 1.0 - 0.5) > 0.485) | (np.abs((z / 0.8) % 1.0 - 0.5) > 0.48)
    base -= joint[..., None] * np.array([18, 18, 18])
    border = (z > Z1 - 0.45) | (z < Z0 + 0.45) | (x < X0 + 0.45) | (x > X1 - 0.45)
    border &= ~((x > ESC_X0 - 0.95) & (z > ESC_Z0))
    base = np.where(border[..., None], np.array([170, 156, 132]) * (0.95 + 0.1 * var[..., None]), base)
    # the rosette: rings of pale stone and brass before the desk
    d = np.hypot(x - 0.0, z + 2.3)
    ring = (np.abs(d - 0.95) < 0.03) | (np.abs(d - 0.62) < 0.022)
    star = (d < 0.62) & (np.abs(np.sin(np.arctan2(z + 2.3, x) * 4)) > 1 - 0.55 * (1 - d / 0.62))
    base = np.where(star[..., None], np.array([118, 112, 104]), base)
    base = np.where(ring[..., None], np.array([170, 146, 96]), base)
    # the doors' mat, the landing plate at the escalator's foot (ribbed steel, its comb green-lit)
    mat = (np.abs(x) < 1.0) & (z < Z0 + 1.0) & (z > Z0 + 0.1)
    base = np.where(mat[..., None], np.array([46, 44, 44]) + ((np.abs(x) > 0.92) | (z > Z0 + 0.92))[..., None] * 30, base)
    plate = (x > 0.05) & (x < ESC_X0 + 0.02) & (z > ESC_Z0 + 0.12) & (z < ESC_Z1 - 0.12)
    ribs = (((z * 20) % 1.0) < 0.5)
    base = np.where(plate[..., None], np.array([150, 154, 160]) + ribs[..., None] * 24, base)
    return base


def floor_paint(x, z):
    y = np.zeros_like(x)
    lights = room_lights()
    rgb = floor_base(x, z) * shade(x, y, z, (0, 1, 0), lights, AMBIENT, DIFFUSE, DIRECTION, blockers())
    # reflections in the polished granite: the lit things, seen in the floor toward the camera
    t30 = math.tan(math.radians(30))
    for (cx, cz, half, y0, y1, colour, k) in (
            (0.0, DESK[1], 0.6, 0.45, 0.7, '#9cd4ff', 0.22),          # the desk's logo
            (X1 - 0.12, 0.0, 0.9, 2.05, 2.25, '#ffc884', 0.3),        # the lifts' indicators
            (-3.1, Z1, 1.5, 0.3, 1.25, '#e0ecff', 0.25),             # the directory board
            (1.1, 4.12, 0.25, 0.05, 0.4, '#9cffd0', 0.5)):            # the escalator's comb light
        g = soft_rect(x, z, cx - half, cx + half, cz - y1 * t30, cz - y0 * t30, 0.35)
        rgb += (g * k)[..., None] * hex_rgb(colour)
    # the comb's own glow at the foot, and the desk's under-counter light behind it
    rgb += (blob(x, z, ESC_X0 + 0.02, 4.12, 0.06, 0.5) * 0.9)[..., None] * np.array([120, 240, 190])
    return rgb


# ---- the back wall (seen from the room)

WALL_SPLIT = [XO0, 0.0, XO1]
WALL_TEX = (240, 52)


def wall_base(x, y):
    """Travertine panels, a dark skirting, the directory board (coloured blocks for the tenants,
    floor by floor, under a lit header), a brass plaque with the tower's mark."""
    rng = np.random.default_rng(43)
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array([196, 184, 160])
    vein = np.sin(x * 9 + np.sin(y * 13 + x * 2) * 2.2) > 0.86
    base -= vein[..., None] * np.array([18, 18, 16])
    joint = (np.abs(((x + 0.6) / 1.2) % 1.0 - 0.5) > 0.49) | (np.abs((y / 0.6) % 1.0 - 0.5) > 0.47)
    base -= joint[..., None] * np.array([40, 38, 34])
    base = np.where((y < 0.12)[..., None], np.array([60, 58, 60]), base)
    bx0, bx1, by0, by1 = BOARD
    board = (x > bx0) & (x < bx1) & (y > by0) & (y < by1)
    base = np.where(board[..., None], np.array([30, 32, 40]), base)
    inner = (x > bx0 + 0.08) & (x < bx1 - 0.08) & (y > by0 + 0.08) & (y < by1 - 0.22)
    rows = 8
    fy = (y - by0 - 0.08) / (by1 - 0.22 - by0 - 0.08) * rows
    fx = (x - bx0 - 0.08) / (bx1 - bx0 - 0.16)
    cell = np.floor(fy) * 7 + np.floor(fx * 4)
    pick = (np.sin(cell * 91.7) * 1000) % 1.0
    tenants = np.array([[90, 160, 230], [230, 120, 80], [120, 200, 130], [220, 200, 90], [200, 200, 210], [170, 120, 210]])
    colour = tenants[(pick * len(tenants)).astype(int) % len(tenants)]
    bar = inner & ((fy % 1.0) > 0.25) & ((fy % 1.0) < 0.75) & (((fx * 4) % 1.0) < 0.2 + 0.7 * pick)
    base = np.where(bar[..., None], colour, base)
    num = inner & (fx < 0.06) & ((fy % 1.0) > 0.25) & ((fy % 1.0) < 0.75)
    base = np.where(num[..., None], np.array([230, 230, 230]), base)
    header = (x > bx0 + 0.08) & (x < bx1 - 0.08) & (y > by1 - 0.17) & (y < by1 - 0.06)
    base = np.where(header[..., None], np.array([236, 240, 250]), base)
    plaque = (np.abs(x + 5.6) < 0.35) & (np.abs(y - 1.5) < 0.22)
    base = np.where(plaque[..., None], np.array([200, 160, 90]), base)
    mark = plaque & (np.hypot(x + 5.6, (y - 1.5) * 1.4) < 0.15) & ~(np.hypot(x + 5.55, (y - 1.53) * 1.4) < 0.11)
    base = np.where(mark[..., None], np.array([110, 80, 40]), base)
    base += (rng.random((h, w)) - 0.5)[..., None] * 5
    return base


def wall_paint(x, y, z):
    rgb = wall_base(x, y) * shade(x, y, z, (0, 0, -1), room_lights(), AMBIENT, DIFFUSE, DIRECTION, blockers())
    bx0, bx1, by0, by1 = BOARD
    lit = (x > bx0 + 0.08) & (x < bx1 - 0.08) & (y > by0 + 0.08) & (y < by1 - 0.06)
    # the board is lit from inside: its blocks and header glow whatever falls on them
    return np.where(lit[..., None], wall_base(x, y) * 0.95 + 8, rgb)


# ---- small textures

def logo_face():
    """The tower's mark on the desk's front: a lit band with a wave over three bars (no words)."""
    w, h = 48, 12
    img = Image.new('RGB', (w, h), (24, 40, 64))
    d = ImageDraw.Draw(img)
    for k in range(3):
        d.rectangle([4 + k * 4, 3 + k, 6 + k * 4, 9], fill=(170, 220, 255))
    d.arc([16, 1, 30, 13], 200, 340, fill=(220, 240, 255))
    d.arc([22, 3, 36, 15], 200, 340, fill=(140, 200, 250))
    d.line([(36, 6), (44, 6)], fill=(170, 220, 255))
    d.line([(36, 8), (42, 8)], fill=(120, 170, 220))
    return img


def lift_face():
    """A lift's door: brushed steel, the meeting line, the floor indicator above."""
    w, h = 16, 32
    img = Image.new('RGB', (w, h), (150, 156, 164))
    d = ImageDraw.Draw(img)
    for yy in range(4, h, 2):
        d.line([(1, yy), (w - 2, yy)], fill=(140, 146, 154))
    d.rectangle([0, 0, w - 1, 3], fill=(40, 36, 32))
    d.rectangle([5, 1, 10, 2], fill=(255, 180, 80))
    d.line([(w // 2, 4), (w // 2, h - 1)], fill=(90, 94, 100))
    d.rectangle([0, 4, w - 1, h - 1], outline=(100, 104, 110))
    return img


def frond():
    """A palm frond from above: a midrib and its leaflets, the rest a hole."""
    w, h = 32, 8
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(2, w - 1, 2):
        span = int(3.6 * math.sin(math.pi * i / w)) + 1
        d.line([(i, h // 2), (i + 2, h // 2 - span)], fill=(70, 130, 60, 255))
        d.line([(i, h // 2), (i + 2, h // 2 + span)], fill=(56, 112, 52, 255))
    d.line([(0, h // 2), (w - 1, h // 2)], fill=(110, 140, 70, 255))
    return img


def steps_top():
    """An escalator step's tread: fine grooves, a yellow edge."""
    w, h = 16, 16
    img = Image.new('RGB', (w, h), (120, 124, 130))
    d = ImageDraw.Draw(img)
    for xx in range(0, w, 2):
        d.line([(xx, 0), (xx, h - 1)], fill=(90, 94, 100))
    d.rectangle([0, 0, w - 1, 1], fill=(220, 190, 60))
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
    for j, (za, zb) in enumerate(zip(FLOOR_SPLIT_Z, FLOOR_SPLIT_Z[1:])):
        for i, (xa, xb) in enumerate(zip(FLOOR_SPLIT_X, FLOOR_SPLIT_X[1:])):
            x, y, z = grid_floor(xa, xb, za, zb, w, h)
            paintings.append(to_array(floor_paint(x, z)))
            names.append(f'floor_{j}{i}')
    ww, wh = WALL_TEX
    for k, (a, b) in enumerate(zip(WALL_SPLIT, WALL_SPLIT[1:])):
        x, y, z = grid_wall_z(a, b, 0.0, WALL_H, ww, wh, Z1)
        paintings.append(to_array(wall_paint(x, y, z)))
        names.append(f'wall_{k}')
    for name, img in zip(names, quantise_together(paintings)):
        img.save(ART / f'{name}.png')
    logo_face().save(ART / 'logo.png')
    lift_face().save(ART / 'lift.png')
    frond().save(ART / 'frond.png')
    steps_top().save(ART / 'tread.png')
    section_face(16, 16, (140, 154, 180), (88, 96, 116)).save(ART / 'cut.png')


# ---- the lobby recipe

def materials():
    m = {
        'cut': {'color': '#8c9ab4', 'class': 'emissive'},
        'slab_cut': {'color': '#76849e', 'class': 'emissive'},
        'side_wall': {'color': '#b8ac94',
                      'texture': {'pattern': 'tile', 'colors': ['#c4b89c', '#a0947c'], 'size': 16,
                                  'params': {'count': 1, 'grout': 1}, 'projection': 'box', 'scale': [1.2, 0.6]}},
        'lintel': {'color': '#6a6660'},
        'lift': {'color': '#9aa0a8', 'texture': {'image': 'art/lift.png', 'bits': 4, 'projection': 'fit'}},
        'lift_frame': {'color': '#5a5650'},
        'call': {'color': '#ffcc70', 'class': 'emissive'},
        'desk_front': {'color': '#7a5a44'},
        'desk_top': {'color': '#3c5048'},
        'desk_work': {'color': '#8a7058'},
        'logo': {'color': '#a0c8f0', 'class': 'emissive', 'texture': {'image': 'art/logo.png', 'bits': 4, 'projection': 'fit'}},
        'book': {'color': '#f0ece0'},
        'book_cover': {'color': '#5a2a2a'},
        'phone': {'color': '#c8c0b0'},
        'bell': {'color': '#d8b060', 'smooth': True},
        'chair': {'color': '#3a3c44'},
        'planter': {'color': '#8a8a94'},
        'soil': {'color': '#1c1a18'},
        'palm': {'color': '#4c8c48', 'double_sided': True, 'texture': {'image': 'art/frond.png', 'bits': 4, 'projection': 'fit'}},
        'trunk': {'color': '#6a5a40'},
        'sofa': {'color': '#4a4044'},
        'sofa_seat': {'color': '#5c5054'},
        'planter_cut': {'color': '#8c9ab4', 'class': 'emissive', 'texture': {'image': 'art/cut.png', 'bits': 4, 'projection': 'fit'}},
    }
    for j in range(2):
        for i in range(2):
            m[f'floor_{j}{i}'] = {'color': '#4a4a52', 'class': 'emissive',
                                  'texture': {'image': f'art/floor_{j}{i}.png', 'bits': 8, 'projection': 'fit'}}
    for k in range(2):
        m[f'wall_{k}'] = {'color': '#6a645a', 'class': 'emissive',
                          'texture': {'image': f'art/wall_{k}.png', 'bits': 8, 'projection': 'fit'}}
    return m


def shell_nodes():
    f = Mesh()
    for j, (za, zb) in enumerate(zip(FLOOR_SPLIT_Z, FLOOR_SPLIT_Z[1:])):
        for i, (xa, xb) in enumerate(zip(FLOOR_SPLIT_X, FLOOR_SPLIT_X[1:])):
            f.quad(xa, 0, za, xb, 0, zb, (0, 1, 0), f'floor_{j}{i}')
    f.quad(XO0, -SLAB, ZO0, XO1, 0, ZO0, (0, 0, -1), 'slab_cut')
    n = [f.node('floor', 'floor_00')]
    b = Mesh()
    for k, (a, c) in enumerate(zip(WALL_SPLIT, WALL_SPLIT[1:])):
        b.quad(a, 0, Z1, c, WALL_H, Z1, (0, 0, -1), f'wall_{k}')
    b.quad(XO0, WALL_H, Z1, XO1, WALL_H, ZO1, (0, 1, 0), 'cut')
    n.append(b.node('back_wall', 'wall_0'))
    n.append(box('end_w_front', (XO0, -0.02, Z0), (X0, WALL_H - 0.02, ENTRY[0]), 'side_wall',
                 open=['bottom'], faces={'top': 'cut', 'back': 'cut'}))
    n.append(box('end_w_back', (XO0, -0.02, ENTRY[1]), (X0, WALL_H - 0.02, Z1 + 0.01), 'side_wall',
                 open=['bottom', 'front'], faces={'top': 'cut'}))
    n.append(box('entry_lintel', (XO0 + 0.012, LINTEL, ENTRY[0] - 0.01), (X0 - 0.012, WALL_H - 0.03, ENTRY[1] + 0.01),
                 'lintel', open=['back', 'front'], faces={'top': 'cut'}))
    lift_decals = [{'id': f'lift_{k}', 'face': 'left', 'material': 'lift', 'size': [r(b_ - a_), 2.2],
                    'at': [r(-(a_ + b_) / 2), r(1.1 - (WALL_H - 0.02) / 2 + 0.01)]} for k, (a_, b_) in enumerate(LIFTS)]
    lift_decals.append({'id': 'call', 'face': 'left', 'material': 'call', 'size': [0.08, 0.14],
                        'at': [r(-1.25), r(1.15 - (WALL_H - 0.02) / 2 + 0.01)]})
    n.append(box('end_e', (X1, -0.02, Z0), (XO1, WALL_H - 0.02, Z1 + 0.01), 'side_wall', open=['bottom', 'front'],
                 faces={'top': 'cut', 'back': 'cut'}, decals=lift_decals))
    return n


def prop_nodes():
    n = []
    x0, z0, x1, z1 = DESK
    desk = [box('desk_front', (x0, -0.02, z0), (x1, 0.97, z0 + 0.22), 'desk_front', open=['bottom'],
                faces={'top': 'desk_top'},
                decals=[{'id': 'logo', 'face': 'back', 'material': 'logo', 'size': [1.6, 0.4], 'at': [0, 0.06]}]),
            box('desk_work', (x0 + 0.06, -0.02, z0 + 0.2), (x1 - 0.06, 0.73, z1), 'desk_work', open=['bottom']),
            box('book', (-0.95, 0.96, z0 + 0.04), (-0.45, 0.999, z0 + 0.19), 'book', faces={'back': 'book_cover'}),
            box('phone', (0.75, 0.72, z0 + 0.32), (1.0, 0.8, z0 + 0.52), 'phone'),
            at({'id': 'bell', 'op': 'sphere', 'radius': 0.05, 'rings': 3, 'segments': 6, 'material': 'bell'},
               translate=[0.5, 0.975, z0 + 0.12], scale=[1, 0.6, 1]),
            box('chair_seat', (-0.85, 0.42, 0.55), (-0.35, 0.5, 1.03), 'chair'),
            box('chair_back', (-0.84, 0.49, 0.98), (-0.36, 0.92, 1.05), 'chair'),
            box('chair_post', (-0.63, -0.02, 0.77), (-0.57, 0.43, 0.83), 'chair', open=['bottom', 'top'])]
    n.append(group('desk', desk))
    s = PLANTER_S / 2
    for k, (px, pz) in enumerate(PLANTERS):
        parts = [box(f'planter_{k}', (px - s, -0.02, pz - s), (px + s, PLANTER_H, pz + s), 'planter', open=['bottom'],
                     faces={'top': 'soil'}),
                 at({'id': f'trunk_{k}', 'op': 'cylinder', 'radius': 0.06, 'height': 0.4, 'segments': 5, 'caps': False,
                     'material': 'trunk'}, translate=[px, PLANTER_H + 0.18, pz])]
        fr = Mesh()
        rng = np.random.default_rng(k + 3)
        for i in range(9):
            a = math.tau * i / 9 + rng.random() * 0.25 + k
            ln = 0.55 + rng.random() * 0.25
            wd = 0.16
            c, sn = math.cos(a), math.sin(a)
            y0, y1 = PLANTER_H + 0.36, 0.72 + rng.random() * 0.2

            def p(u, v, yy):
                return (px + u * c - v * sn, yy, pz + u * sn + v * c)
            q = [p(0.02, -wd / 2, y0), p(ln, -wd / 2, y1), p(ln, wd / 2, y1), p(0.02, wd / 2, y0)]
            fr.poly([q[0], q[1], q[2]], (0, 1, 0))      # two triangles: a tilted quad is not planar
            fr.poly([q[0], q[2], q[3]], (0, 1, 0))      # once rounded
        parts.append(fr.node(f'fronds_{k}', 'palm'))
        n.append(group(f'palm_{k}', parts))
    sx0, sz0, sx1, sz1 = SOFA
    n.append(group('sofa', [
        box('sofa_base', (sx0 + 0.18, -0.02, sz0 + 0.125), (sx1, 0.42, sz1 - 0.125), 'sofa_seat', open=['bottom']),
        box('sofa_back', (sx0, -0.02, sz0 + 0.12), (sx0 + 0.19, 0.78, sz1 - 0.12), 'sofa', open=['bottom']),
        box('sofa_arm_s', (sx0 + 0.005, -0.02, sz0), (sx1 + 0.01, 0.6, sz0 + 0.13), 'sofa', open=['bottom']),
        box('sofa_arm_n', (sx0 + 0.005, -0.02, sz1 - 0.13), (sx1 + 0.01, 0.6, sz1), 'sofa', open=['bottom'])]))
    return n


def lobby_recipe():
    lighting = {'direction': DIRECTION, 'ambient': AMBIENT, 'diffuse': DIFFUSE,
                'lights': [l for l in room_lights()], 'refine': {'tolerance': 20, 'max_added': 260}}
    return recipe(P + 'lobby', materials(), shell_nodes() + prop_nodes(), lighting, 2000)


# ---- the escalator

def nose(x):
    """The steps' nose line, rising from the foot (x 1.0) to the top (x 7)."""
    return (x - ESC_X0) / (ESC_X1 - ESC_X0) * ESC_STEPS * ESC_RISE


def escalator_recipe():
    m = {'tread': {'color': '#7c8088', 'texture': {'image': 'art/tread.png', 'bits': 4, 'projection': 'box',
                                                   'scale': [0.5, 0.5]}},
         'riser': {'color': '#5a5e66'},
         'side': {'color': '#a8acb4'},
         'skirt': {'color': '#c0c4cc'},
         'glass': {'color': '#8cb4c4', 'blend': 'half', 'double_sided': True},
         'rail': {'color': '#202024'},
         'cut': {'color': '#8c9ab4', 'class': 'emissive'},
         'comb': {'color': '#a0ffd0', 'class': 'emissive'}}
    run = (ESC_X1 + 0.03 - ESC_X0) / ESC_STEPS
    pts = [(ESC_X1 + 0.03, -0.02), (ESC_X0, -0.02)]
    xx = ESC_X0
    for k in range(1, ESC_STEPS + 1):
        pts.append((xx, ESC_RISE * k))
        if k < ESC_STEPS:
            xx += run
            pts.append((xx, ESC_RISE * k))
    pts.append((ESC_X1 + 0.03, ESC_RISE * ESC_STEPS))
    zc = (ESC_Z0 + ESC_Z1) / 2 + 0.02
    depth = 0.92
    n = [{'id': 'steps', 'op': 'extrude', 'material': 'tread', 'depth': depth,
          'points': [[r(a), r(b)] for a, b in pts], 'faces': {'front': 'side', 'back': 'side'},
          'transform': {'translate': [0, 0, r(zc)]}}]
    # the sides: stainless trusses, each a slanted wall from the floor to above the nose line
    slope = math.degrees(math.atan2(ESC_STEPS * ESC_RISE, ESC_X1 - ESC_X0))
    length = math.hypot(ESC_X1 - ESC_X0, ESC_STEPS * ESC_RISE)
    for side, (za, zb) in (('in', (BAL_Z[0] + 0.01, BAL_Z[1])), ('out', (ESC_Z1 - 0.12, ESC_Z1 - 0.01))):
        sk = Mesh()
        top = lambda x: min(nose(x) + 0.12, WALL_H - 0.02)
        poly = [(ESC_X0 - 0.15, -0.02), (ESC_X1, -0.02), (ESC_X1, min(top(ESC_X1), WALL_H - 0.02)),
                (ESC_X0, top(ESC_X0)), (ESC_X0 - 0.15, 0.12)]
        for zz, face in ((za, (0, 0, -1)), (zb, (0, 0, 1))):
            sk.poly([(x, y, zz) for x, y in poly], face)
        sk.poly([(ESC_X0 - 0.15, 0.12, za), (ESC_X0, top(ESC_X0), za), (ESC_X0, top(ESC_X0), zb),
                 (ESC_X0 - 0.15, 0.12, zb)], (0, 1, 0))
        sk.poly([(ESC_X0, top(ESC_X0), za), (ESC_X1, top(ESC_X1), za), (ESC_X1, top(ESC_X1), zb),
                 (ESC_X0, top(ESC_X0), zb)], (0, 1, 0))
        sk.poly([(ESC_X0 - 0.15, -0.02, za), (ESC_X0 - 0.15, 0.12, za), (ESC_X0 - 0.15, 0.12, zb),
                 (ESC_X0 - 0.15, -0.02, zb)], (-1, 0, 0))
        n.append(sk.node(f'skirt_{side}', 'skirt'))
        # the glass balustrade above it, cut at the section's ceiling, and its handrail
        zg = (za + zb) / 2
        g = Mesh()
        x_cut = ESC_X0 + (WALL_H - 0.03 - 0.95) / (ESC_STEPS * ESC_RISE / (ESC_X1 - ESC_X0))
        x_low = ESC_X0 + (WALL_H - 0.03 - 0.13) / (ESC_STEPS * ESC_RISE / (ESC_X1 - ESC_X0))
        g.poly([(ESC_X0 - 0.1, 0.13, zg), (x_low, WALL_H - 0.03, zg), (x_cut, WALL_H - 0.03, zg),
                (ESC_X0 - 0.1, 0.92, zg)], (0, 0, -1))
        n.append(g.node(f'glass_{side}', 'glass'))
        rl = math.hypot(x_cut - ESC_X0, WALL_H - 0.03 - 0.95)
        n.append(at({'id': f'rail_{side}', 'op': 'box', 'size': [r(rl), 0.06, 0.08], 'material': 'rail',
                     'faces': {'right': 'cut'}},
                    translate=[r((ESC_X0 + x_cut) / 2), r((0.95 + WALL_H - 0.03) / 2 + 0.03), r(zg)], rotate=[0, 0, slope]))
        n.append(at({'id': f'newel_{side}', 'op': 'cylinder', 'radius': 0.12, 'height': 0.08, 'segments': 8,
                     'material': 'rail'}, translate=[ESC_X0 - 0.02, 0.88, r(zg)], rotate=[90, 0, 0]))
        n[-1]['height'] = 0.065
    n.append(box('comb', (ESC_X0 - 0.06, -0.02, ESC_Z0 + 0.16), (ESC_X0 + 0.02, 0.05, ESC_Z1 - 0.16), 'comb',
                 open=['bottom']))
    lighting = {'direction': DIRECTION, 'ambient': AMBIENT + 0.1, 'diffuse': DIFFUSE,
                'lights': lights_near({'downlight', 'comb', 'night', 'board', 'lifts'}),
                'refine': {'max_added': 0}}
    return recipe(P + 'escalator', m, n, lighting, 600)


# ---- the glass front

def front_recipe():
    m = {'sill': {'color': '#5c5a5e'}, 'cut': {'color': '#8c9ab4', 'class': 'emissive'},
         'glass': {'color': '#405870', 'blend': 'half'}, 'post': {'color': '#2c2e34'},
         'bar': {'color': '#b0b4bc'}}
    n = [box('sill', (XO0, -0.02, ZO0), (XO1, SILL_H, Z0), 'sill', open=['bottom', 'front'], faces={'top': 'cut'})]
    zg = (ZO0 + Z0) / 2
    g = Mesh()
    g.poly([(XO0, SILL_H - 0.01, zg), (XO1, SILL_H - 0.01, zg), (XO1, CUT - 0.01, zg), (XO0, CUT - 0.01, zg)], (0, 0, -1))
    n.append(g.node('glass', 'glass'))
    n.append(box('glass_cut', (XO0, CUT - 0.02, zg - 0.012), (XO1, CUT, zg + 0.012), 'cut', open=['bottom']))
    for k, x in enumerate(MULLIONS + [-0.9, 0.0, 0.9]):
        n.append(box(f'post_{k}', (x - 0.04, SILL_H - 0.02, ZO0 + 0.06), (x + 0.04, CUT - 0.03, Z0 - 0.06), 'post',
                     open=['bottom'], faces={'top': 'cut'}))
    for k, x in enumerate((-0.45, 0.45)):
        n.append(box(f'push_{k}', (x - 0.3, 0.62, Z0 - 0.06), (x + 0.3, 0.66, Z0 - 0.02), 'bar'))
    lighting = {'direction': DIRECTION, 'ambient': AMBIENT + 0.06, 'diffuse': DIFFUSE,
                'lights': lights_near({'street_w', 'street_e', 'across', 'night'}), 'refine': {'max_added': 0}}
    return recipe(P + 'front', m, n, lighting, 300)


def collision():
    op = ['bottom', 'top']
    n = [box('slab', (XO0, -SLAB, ZO0), (XO1, 0, ZO1), 'floor', open=['bottom', 'left', 'right', 'front', 'back']),
         box('front_wall', (XO0, 0, ZO0), (XO1, CUT, Z0), 'floor', open=op),
         box('back_wall', (XO0, 0, Z1), (XO1, WALL_H, ZO1), 'floor', open=op),
         box('end_w_front', (XO0, 0, Z0), (X0, WALL_H, ENTRY[0]), 'floor', open=op + ['back']),
         box('end_w_back', (XO0, 0, ENTRY[1]), (X0, WALL_H, Z1), 'floor', open=op + ['front']),
         box('end_e', (X1, 0, Z0), (XO1, WALL_H, Z1), 'floor', open=op + ['back', 'front'])]
    x0, z0, x1, z1 = DESK
    n.append(box('desk', (x0, 0, z0), (x1, CUT, z1), 'floor', open=op))
    s = PLANTER_S / 2
    for k, (px, pz) in enumerate(PLANTERS):
        n.append(box(f'planter_{k}', (px - s, 0, pz - s), (px + s, CUT, pz + s), 'floor', open=op))
    n.append(box('balustrade', (ESC_X0, 0, BAL_Z[0]), (ESC_X1, CUT, BAL_Z[1]), 'floor', open=op + ['right']))
    steps = dict(escalator_recipe()['nodes'][0], material='floor')
    steps.pop('faces')
    n.append(steps)
    return collision_recipe(P + 'lobby_col', n)


def placements():
    return [{'id': P + 'lobby', 'asset': P + 'lobby', 'position': [0, 0, 0], 'collision': P + 'lobby_col'},
            {'id': P + 'escalator', 'asset': P + 'escalator', 'position': [0, 0, 0], 'collision': 'none'},   # in r4_lobby_col
            {'id': P + 'front', 'asset': P + 'front', 'position': [0, 0, 0], 'collision': 'none'}]


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--no-placements', action='store_true', help='leave lobby.placements.json as it is')
    args = ap.parse_args()
    draw_art()
    write_json(HERE / f'{P}lobby.asset.json', lobby_recipe())
    write_json(HERE / f'{P}lobby_col.asset.json', collision())
    write_json(HERE / f'{P}escalator.asset.json', escalator_recipe())
    write_json(HERE / f'{P}front.asset.json', front_recipe())
    if not args.no_placements:
        write_json(HERE / 'lobby.placements.json', {'format': 'after-hours-placements', 'version': 1, 'room': 'lobby',
                                                    'placements': placements()})
    print('wrote r4_lobby, r4_lobby_col, r4_escalator, r4_front and', len(list(ART.glob('*.png'))), 'textures')


if __name__ == '__main__':
    main()
