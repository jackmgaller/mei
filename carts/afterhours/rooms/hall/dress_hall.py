#!/usr/bin/env python3
"""The tower, the lift hall (6F), dressed: writes the room's Asset Kit recipes into dressed/, their
textures into dressed/art/ and (with --placements) hall.placements.json beside this script; without
it, a draft in dressed/draft.placements.json, which ../corridor/capture.py prefers while it exists.

    python3 carts/afterhours/rooms/hall/dress_hall.py --placements

1990, the bubble's lift lobby on the sixth floor, and the back of house behind its glass. In front:

- cream marble with a green border and a brass medallion, under warm downlights;
- three brass lift doors in polished granite, and a directory board that skips the ninth floor;
- the reception's marble counter and its lamp, an oxblood leather sofa, a planter's ficus;
- the securities house's name in gold on its glass screen (Kirisame Securities, fictional).

Behind the glass, half lit:

- vinyl tiles with mop streaks;
- the cleaners' stacked boxes and trolley;
- pipes on the back wall, an alarm bell, an extinguisher;
- the fire stair's door wedged open with folded cardboard, its light spilling out;
- the goods lift's padded car beyond the east doorway.

The core is cut at 1 m, and its section shows the plan inside: three lift shafts with the cars far
below, the fire stair's flights, the risers. It is the same core as on the ninth floor and the
roof.

The floor plan is the level lead's (PLAN.md, make_hall.py), imported for its numbers. Light as in
../corridor/s2dress.py. The glass and its gold lettering are their own recipe, unlit. Text uses
Belleza and Figtree from tools/fonts/. Needs NumPy and Pillow.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'corridor'))
import make_hall as G  # noqa: E402  (the lead's plan: imported for its numbers only)
from s2dress import (CUT_H, WALL_H, Mesh, Room, at, blob, box, font, grid, kit_lighting, mat_tex,  # noqa: E402
                     paint_floor, paint_rgb, paint_section, paint_wall, recipe, rect, save_png, smoothstep,
                     to_image, write_json)

OUT = HERE / 'dressed'
ART = OUT / 'art'
P = 'lh_'
R = Room(G.ROOM, P)
CX0, CZ0, CX1, CZ1 = G.CORE
SCREEN_W = (-11.0, 0.05, CX0, 0.2)            # x0, z0, x1, z1
SCREEN_E = (CX1, -4.5, CX1 + 0.15, 0.2)
LIFTS = (-3.7, -2.2, -0.7)                   # the lift doors' middles on the core's south face
DIRECTORY = (0.4, 2.6)
PLANTER = (-4.5, -2.0, -3.5, -0.7)
RECEPTION = (-10.4, -4.5, -8.6, -3.9)
SOFA = (-0.2, -4.5, 1.8, -3.9)
BOXES = (6.6, -1.4, 8.0, 0.0)
TROLLEY = (6.4, 2.4, 7.6, 3.0)
STAIR_DOOR = (1.1, 2.3)                      # z of the fire stair's door in the core's west face
NAME = 'KIRISAME SECURITIES'
AMBIENT = 0.13


def lobby(x, z):
    """The lift lobby: in front of the west screen and west of the east screen."""
    return (x < CX1) & (z < np.where(x < CX0, 0.05, 0.2))


def lights():
    out = [{'id': f'down_{k}', 'at': [x, 2.6, z], 'color': '#ffdcb0', 'intensity': 1.9, 'range': 3.9, 'shadows': True}
           for k, (x, z) in enumerate(((-8.2, -2.6), (-5.6, -1.0), (-2.2, -2.8), (1.0, -2.6)))]
    out += [
        {'id': 'reception', 'at': [-9.1, 1.3, -4.25], 'color': '#ffc070', 'intensity': 1.3, 'range': 2.2},
        {'id': 'tube_w', 'at': [-8.0, 2.6, 2.4], 'color': '#d8e6e8', 'intensity': 1.5, 'range': 4.4, 'line': 1.2,
         'shadows': True},
        {'id': 'tube_back', 'at': [-1.0, 2.6, 3.75], 'color': '#d8e6e8', 'intensity': 1.6, 'range': 4.4, 'line': 1.2,
         'shadows': True},
        {'id': 'tube_e', 'at': [6.0, 2.6, 1.8], 'color': '#d8e6e8', 'intensity': 1.7, 'range': 4.6, 'line': 1.2,
         'shadows': True},
        {'id': 'tube_se', 'at': [8.6, 2.6, -2.2], 'color': '#d8e6e8', 'intensity': 1.1, 'range': 4.2, 'line': 1.2,
         'shadows': True},
        {'id': 'stair_spill', 'at': [-5.5, 1.5, 1.7], 'color': '#cce8dc', 'intensity': 1.0, 'range': 2.4},
        {'id': 'goods', 'at': [R.XO1 + 0.8, 1.7, -3.0], 'color': '#f0f4ff', 'intensity': 2.2, 'range': 3.2, 'shadows': True},
        {'id': 'trading', 'at': [R.XO0 - 0.8, 1.5, -3.0], 'color': '#ffe0b8', 'intensity': 1.3, 'range': 2.6, 'shadows': True},
        {'id': 'lifts', 'at': [-2.2, 0.95, -0.05], 'color': '#ffd090', 'intensity': 0.6, 'range': 1.8, 'paint': True},
        {'id': 'directory', 'at': [1.5, 0.6, 0.05], 'color': '#ffe0a0', 'intensity': 0.35, 'range': 1.4, 'paint': True},
        {'id': 'exit', 'at': [-6.7, 2.15, R.Z1 - 0.15], 'color': '#50ff90', 'intensity': 0.5, 'range': 1.6, 'paint': True},
    ]
    return out


def blockers():
    out = [(CX0, 0, CZ0, CX1, 2.8, CZ1), (PLANTER[0], 0, PLANTER[1], PLANTER[2], 1.6, PLANTER[3]),
           (RECEPTION[0], 0, RECEPTION[1], RECEPTION[2], 1.0, RECEPTION[3]), (SOFA[0], 0, SOFA[1], SOFA[2], 0.75, SOFA[3]),
           (BOXES[0], 0, BOXES[1], BOXES[2], 1.6, BOXES[3]), (TROLLEY[0], 0, TROLLEY[1], TROLLEY[2], 1.0, TROLLEY[3])]
    return out


# ---- painting

def floor_base(x, z):
    h, w = x.shape
    rng = np.random.default_rng(int(abs(x[0, 0]) * 3 + abs(z[0, 0]) * 11) + 1)
    # the back of house: grey-green vinyl tiles, scuffed
    back = np.zeros((h, w, 3)) + np.array([150, 156, 146]) + (rng.random((h, w)) - 0.5)[..., None] * 10
    chk = ((np.floor(x / 0.3) + np.floor(z / 0.3)) % 2 == 0)
    back *= np.where(chk, 0.96, 1.0)[..., None]
    for (sx, sz, rr) in ((7.3, -0.7, 1.6), (7.3, -0.7, 2.2), (-8.0, 2.2, 1.2)):     # the mop's glossy arcs
        back *= (1 + 0.1 * np.exp(-((np.hypot(x - sx, z - sz) - rr) / 0.06) ** 2))[..., None]
    back = paint_rgb(back, rect(x, z, CX0 - 0.42, 1.55, CX0 - 0.12, 1.85) > 0, (170, 130, 80))   # the folded cardboard
    # the lobby: cream marble in 0.9 m slabs with veins, a green border, a brass medallion
    v = np.sin(x * 3.1 + np.sin(z * 2.3) * 2.0 + np.sin((x + z) * 7.0) * 0.4)
    veins = np.clip(1 - np.abs(v) * 6, 0, 1) * 0.12
    marble = np.zeros((h, w, 3)) + np.array([222, 212, 194])
    marble *= (1 - veins)[..., None]
    slab = (np.abs(((x + 11) / 0.9) % 1 - 0.5) > 0.485) | (np.abs(((z + 4.5) / 0.9) % 1 - 0.5) > 0.485)
    marble *= np.where(slab, 0.86, 1.0)[..., None]
    lob = lobby(x, z)
    border = lob & ~lobby(x - 0.3, z + 0.3) | (lob & (z < -4.2)) | (lob & (x < -10.7)) | (lob & (x > CX1 - 0.3))
    marble = paint_rgb(marble, border, (60, 86, 74))
    marble = paint_rgb(marble, lob & ~border & (lobby(x - 0.34, z + 0.34) ^ lobby(x - 0.3, z + 0.3)), (200, 170, 90))
    d = np.hypot(x + 1.0, z + 2.3)
    marble = paint_rgb(marble, (np.abs(d - 0.75) < 0.04) | (np.abs(d - 0.45) < 0.03), (206, 172, 92))
    star = (d < 0.45) & (np.abs(np.sin(np.arctan2(z + 2.3, x + 1.0) * 4)) * d < 0.06)
    marble = paint_rgb(marble, star, (60, 86, 74))
    for lx in LIFTS:     # the lifts' brass sills
        marble = paint_rgb(marble, rect(x, z, lx - 0.5, 0.06, lx + 0.5, 0.19) > 0, (196, 166, 88))
    return np.where(lob[..., None], marble, back)


def floor_extra(x, z, rgb):
    lob = lobby(x, z)
    for k, L in enumerate(lights()):    # the downlights' reflections in the polished marble
        if L['id'].startswith('down'):
            lx, _, lz = L['at']
            rgb = rgb + (lob * np.exp(-((x - lx) / 0.35) ** 2 - ((z - lz + 0.5) / 0.25) ** 2) * 40)[..., None] * np.array([1.0, 0.92, 0.8])
    return rgb


def wall_base(x, y):
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array([180, 178, 168])
    base = np.where((y < 1.1)[..., None], np.array([150, 156, 150]), base)
    for py, c in ((2.02, (130, 134, 140)), (2.16, (150, 120, 90))):     # pipes along the back wall
        base = np.where((np.abs(y - py) < 0.05)[..., None], np.array(c), base)
        base = np.where((np.abs(y - py - 0.03) < 0.012)[..., None], np.array(c) * 1.25, base)
    base = paint_rgb(base, blob(x, y, -7.2, 1.85, 0.11) > 0.5, (200, 40, 36))      # the alarm bell
    base = paint_rgb(base, rect(x, y, 4.9, 0.15, 5.1, 0.65) > 0, (196, 40, 36))   # an extinguisher
    base = paint_rgb(base, rect(x, y, 8.2, 1.2, 8.55, 1.65) > 0, (236, 234, 224))  # the cleaners' rota
    base = paint_rgb(base, (rect(x, y, 8.24, 1.25, 8.51, 1.55) > 0) & ((y * 25) % 1 < 0.3), (110, 110, 120))
    return base


def wall_extra(x, y, rgb):
    return rgb + (blob(x, y, -6.7, 2.15, 0.45, 0.25) * 0.35)[..., None] * np.array([60, 255, 120])


def paint_core_top(w=160, h=56):
    """The core cut at 1 m, from above (north up): thick walls; three lift shafts along its south side
    with their cars far below; the fire stair's flights behind them, landing at the door in the west
    face; the risers' ducts and pipes at the east end."""
    x, z = grid(CX0, CX1, CZ0, CZ1, w, h)
    cut = np.array([118, 132, 158])
    rgb = np.zeros((h, w, 3)) + cut
    inner = rect(x, z, CX0 + 0.2, CZ0 + 0.2, CX1 - 0.2, CZ1 - 0.2) > 0
    rgb = paint_rgb(rgb, inner, (34, 36, 42))
    # the shafts: x -4.4 .. -0.2 in three, z 0.4 .. 1.75
    for k in range(3):
        a = -4.4 + k * 1.4
        shaft = rect(x, z, a + 0.08, 0.4, a + 1.32, 1.75) > 0
        rgb = paint_rgb(rgb, shaft, (14, 14, 18))
        car = rect(x, z, a + 0.3, 0.6, a + 1.1, 1.5) > 0
        rgb = paint_rgb(rgb, car, (40, 42, 48) if k != 1 else (52, 50, 46))
        rgb = paint_rgb(rgb, blob(x, z, a + 0.7, 1.05, 0.06) > 0.5, (110, 110, 116))
        rgb = paint_rgb(rgb, rect(x, z, a + 0.05, 0.4, a + 0.12, 1.75) > 0, cut)
    rgb = paint_rgb(rgb, rect(x, z, -0.2, 0.4, -0.12, 1.75) > 0, cut)
    # the fire stair: a landing at the west door, flights east behind the shafts
    stair = rect(x, z, CX0 + 0.2, 1.95, -1.4, CZ1 - 0.2) > 0
    rgb = paint_rgb(rgb, stair, (78, 82, 90))
    treads = stair & (x > CX0 + 1.1) & ((x * 3.7) % 1 < 0.22)
    rgb = paint_rgb(rgb, treads, (50, 52, 58))
    rgb = paint_rgb(rgb, rect(x, z, CX0 + 0.2, STAIR_DOOR[0], CX0 + 1.0, STAIR_DOOR[1]) > 0, (90, 96, 104))
    rgb = paint_rgb(rgb, rect(x, z, CX0 - 0.01, STAIR_DOOR[0], CX0 + 0.2, STAIR_DOOR[1]) > 0, (60, 100, 80))
    # risers: round pipes and a square duct
    for k, (px, pz) in enumerate(((0.6, 2.4), (0.95, 2.4), (1.3, 2.4), (0.6, 2.05))):
        rgb = paint_rgb(rgb, blob(x, z, px, pz, 0.12) > 0.5, (150, 150, 140) if k % 2 else (140, 100, 70))
    rgb = paint_rgb(rgb, rect(x, z, 1.8, 0.5, 2.6, 1.6) > 0, (96, 100, 108))
    rgb = paint_rgb(rgb, rect(x, z, 1.9, 0.6, 2.5, 1.5) > 0, (20, 22, 26))
    return to_image(rgb, dither=0)


def paint_core_face(w=200, h=24):
    """The core's south face, the floor up to the cut: polished granite, three brass lift doors with
    their call buttons, the lit directory board with a line missing where the ninth would be."""
    x, y = grid(CX0, CX1, 0, CUT_H, w, h)
    rgb = np.zeros((h, w, 3)) + np.array([150, 120, 120])
    rgb *= (1 + 0.08 * np.sin(x * 9 + np.sin(y * 13)))[..., None]
    rgb = paint_rgb(rgb, y < 0.08, (40, 40, 44))
    for lx in LIFTS:
        rgb = paint_rgb(rgb, rect(x, y, lx - 0.52, 0.0, lx + 0.52, 1.0) > 0, (110, 92, 60))
        rgb = paint_rgb(rgb, rect(x, y, lx - 0.48, 0.0, lx + 0.48, 1.0) > 0, (206, 172, 100))
        rgb = paint_rgb(rgb, np.abs(x - lx) < 0.012, (90, 74, 44))
        rgb = paint_rgb(rgb, rect(x, y, lx + 0.62, 0.86, lx + 0.7, 0.98) > 0, (255, 220, 140))
    dx0, dx1 = DIRECTORY
    rgb = paint_rgb(rgb, rect(x, y, dx0, 0.12, dx1, 0.98) > 0, (36, 30, 26))
    for k in range(11):
        if k == 2:
            continue                      # 9F: not in the directory
        yy = 0.92 - k * 0.075
        rgb = paint_rgb(rgb, rect(x, y, dx0 + 0.1, yy - 0.02, dx0 + 0.25, yy + 0.02) > 0, (236, 206, 120))
        rgb = paint_rgb(rgb, rect(x, y, dx0 + 0.4, yy - 0.015, dx0 + 0.4 + 0.6 + (k * 37 % 7) * 0.12, yy + 0.015) > 0,
                        (206, 180, 110))
    return to_image(rgb, dither=0)


def paint_core_back(w=128, h=16):
    """The core's other faces, behind the glass: painted block, a service hatch, scuffs."""
    img = Image.new('RGB', (w, h), (166, 168, 160))
    d = ImageDraw.Draw(img)
    d.rectangle([0, h - 3, w, h], fill=(110, 112, 110))
    for k in range(0, w, 16):
        d.line([(k, 0), (k, h)], fill=(150, 152, 146))
    d.rectangle([60, 4, 74, 11], fill=(120, 124, 130))
    return img


def paint_name(w=160, h=16):
    """The securities house's name in gold leaf on its glass, with its mark (a fictional house)."""
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((w / 2 + 8, h / 2), NAME, font=font('Belleza-Regular.ttf', 13), fill=(232, 196, 110, 255), anchor='mm')
    d.ellipse([4, 2, 16, 14], outline=(232, 196, 110, 255), width=2)
    d.line([(7, 11), (10, 5), (13, 11)], fill=(232, 196, 110, 255), width=2)
    return img


def paint_counter(w=40, h=12):
    """The reception's counter top: marble, the lamp's brass foot, the visitors' book open, a pen."""
    img = Image.new('RGB', (w, h), (208, 200, 186))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 7):
        d.line([(k, 0), (k + 5, h)], fill=(190, 182, 168))
    d.rectangle([12, 3, 24, 9], fill=(240, 236, 222))
    d.line([(18, 3), (18, 9)], fill=(150, 140, 120))
    d.line([(26, 4), (30, 8)], fill=(40, 40, 60))
    d.ellipse([31, 3, 37, 9], fill=(196, 160, 90))
    return img


def paint_foliage(n=24):
    """The ficus cut at 1 m: leaves in section, dark and light greens round a trunk."""
    rng = np.random.default_rng(5)
    img = Image.new('RGB', (n, n), (40, 70, 44))
    d = ImageDraw.Draw(img)
    for _ in range(40):
        cx, cy = rng.integers(0, n, 2)
        r = int(rng.integers(1, 4))
        g = [(60, 110, 60), (86, 140, 70), (30, 60, 36)][int(rng.integers(0, 3))]
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=g)
    d.ellipse([n // 2 - 2, n // 2 - 2, n // 2 + 2, n // 2 + 2], fill=(110, 80, 50))
    return img


def paint_boxes_top(w=28, h=28):
    img = Image.new('RGB', (w, h), (118, 132, 158))
    d = ImageDraw.Draw(img)
    for (a, b, c, e, col) in ((1, 1, 13, 13, (176, 138, 92)), (15, 1, 27, 11, (196, 160, 110)),
                              (1, 15, 11, 27, (160, 120, 80)), (13, 13, 27, 27, (186, 150, 100))):
        d.rectangle([a, b, c, e], fill=col)
        d.line([((a + c) // 2, b), ((a + c) // 2, e)], fill=(220, 200, 150))
    return img


def paint_trolley_top(w=24, h=12):
    """The cleaner's trolley from above: a yellow mop bucket, a bin bag, sprays, a cloth."""
    img = Image.new('RGB', (w, h), (70, 74, 82))
    d = ImageDraw.Draw(img)
    d.ellipse([1, 1, 10, 10], fill=(230, 196, 40))
    d.ellipse([3, 3, 8, 8], fill=(80, 110, 140))
    d.ellipse([13, 2, 21, 10], fill=(30, 30, 34))
    d.rectangle([11, 1, 12, 4], fill=(60, 160, 220))
    d.rectangle([22, 7, 23, 11], fill=(220, 60, 60))
    return img


def paint_padding(w=16, h=16):
    """The goods lift's walls: grey quilted blankets hung against knocks."""
    img = Image.new('RGB', (w, h), (96, 100, 108))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 4):
        d.line([(k, 0), (k, h)], fill=(70, 74, 80))
        d.line([(0, k), (w, k)], fill=(110, 114, 122))
    return img


# ---- the recipes

def core_nodes():
    m = Mesh()
    # the core as a block cut at 1 m: its south face toward the lobby, its west face with the fire
    # stair's opening (a dark doorway, the door wedged back inside), its north and east faces
    m.quad_y(CUT_H, CX0, CX1, CZ0, CZ1, 1, 'core_top')
    m.quad_z(CZ0, CX0, CX1, -0.02, CUT_H, -1, 'core_face')
    m.quad_z(CZ1, CX0, CX1, -0.02, CUT_H, 1, 'core_back')
    m.quad_x(CX1, -0.02, CUT_H, CZ0, CZ1, 1, 'core_back')
    a, b = STAIR_DOOR
    m.quad_x(CX0, -0.02, CUT_H, CZ0, a, -1, 'core_back')
    m.quad_x(CX0, -0.02, CUT_H, b, CZ1, -1, 'core_back')
    m.quad_x(CX0 + 0.35, -0.02, CUT_H, a, b, -1, 'stair_dark')          # the open doorway's depth
    m.quad_z(a, CX0, CX0 + 0.35, -0.02, CUT_H, 1, 'core_back')
    m.quad_z(b, CX0, CX0 + 0.35, -0.02, CUT_H, -1, 'core_back')
    n = [m.node('core', 'core_back')]
    n.append(box('stair_wedge', (CX0 - 0.3, -0.02, a + 0.05), (CX0 - 0.04, 0.12, a + 0.3), 'cardboard', open=['bottom']))
    return n


def screen_nodes():
    """The glass screens' frames: brass mullions every 1.5 m and a brass base, cut at 1 m."""
    n = []
    x0, z0, x1, z1 = SCREEN_W
    for k, x in enumerate(np.arange(x0 + 1.5, x1, 1.5)):
        n.append(box(f'mullion_w_{k}', (x - 0.03, -0.02, z0 - 0.01), (x + 0.03, CUT_H, z1 + 0.01), 'brass', open=['bottom'],
                     faces={'top': 'cut'}))
    n.append(box('base_w', (x0, -0.02, z0), (x1, 0.08, z1), 'brass_dark', open=['bottom', 'left', 'right']))
    x0, z0, x1, z1 = SCREEN_E
    for k, z in enumerate(np.arange(z0 + 1.5, z1, 1.5)):
        n.append(box(f'mullion_e_{k}', (x0 - 0.01, -0.02, z - 0.03), (x1 + 0.01, CUT_H, z + 0.03), 'brass', open=['bottom'],
                     faces={'top': 'cut'}))
    n.append(box('base_e', (x0, -0.02, z0), (x1, 0.08, z1), 'brass_dark', open=['bottom', 'back', 'front']))
    return n


def lobby_nodes():
    px0, pz0, px1, pz1 = PLANTER
    rx0, rz0, rx1, rz1 = RECEPTION
    sx0, sz0, sx1, sz1 = SOFA
    n = [box('planter', (px0, -0.02, pz0), (px1, 0.6, pz1), 'stone', open=['bottom'], faces={'top': 'soil'}),
         box('ficus', (px0 + 0.1, 0.58, pz0 + 0.12), (px1 - 0.1, CUT_H, pz1 - 0.12), 'leaves', open=['bottom'],
             faces={'top': 'foliage'}),
         box('reception', (rx0, -0.02, rz0), (rx1, 1.0, rz1), 'marble', open=['bottom', 'back'], faces={'top': 'counter'}),
         box('reception_plinth', (rx0 + 0.05, -0.02, rz1 - 0.02), (rx1 - 0.05, 0.1, rz1 + 0.04), 'brass_dark', open=['bottom']),
         box('lamp_stem', (-9.13, 0.99, -4.27), (-9.07, 1.25, -4.21), 'brass', open=['bottom']),
         at({'id': 'lamp_shade', 'op': 'cone', 'radius': 0.14, 'height': 0.16, 'segments': 6, 'material': 'lamp'},
            translate=[-9.1, 1.3, -4.24]),
         box('sofa_seat', (sx0 + 0.18, -0.02, sz0 + 0.02), (sx1 - 0.18, 0.42, sz1 - 0.03), 'leather', open=['bottom', 'back']),
         box('sofa_back', (sx0 + 0.02, -0.02, sz0), (sx1 - 0.02, 0.74, sz0 + 0.2), 'leather_dark', open=['bottom', 'back']),
         box('sofa_arm_w', (sx0, -0.02, sz0 + 0.18), (sx0 + 0.2, 0.56, sz1), 'leather_dark', open=['bottom']),
         box('sofa_arm_e', (sx1 - 0.2, -0.02, sz0 + 0.18), (sx1, 0.56, sz1), 'leather_dark', open=['bottom'])]
    return n


def back_nodes():
    bx0, bz0, bx1, bz1 = BOXES
    tx0, tz0, tx1, tz1 = TROLLEY
    n = [box('boxes', (bx0, -0.02, bz0), (bx1, CUT_H, bz1), 'carton', open=['bottom'], faces={'top': 'boxes_top'}),
         box('trolley', (tx0, 0.12, tz0), (tx1, 0.72, tz1), 'trolley', open=['bottom'], faces={'top': 'trolley_top'}),
         box('trolley_handle', (tx1 - 0.06, 0.7, tz0 + 0.05), (tx1 - 0.02, 1.0, tz1 - 0.05), 'trolley', open=['bottom']),
         at({'id': 'mop', 'op': 'cylinder', 'radius': 0.02, 'height': 1.2, 'segments': 4, 'caps': False, 'material': 'mop'},
            translate=[tx0 + 0.1, 0.72, tz0 + 0.3], rotate=[0, 0, 15])]
    for k, x in enumerate((tx0 + 0.1, tx1 - 0.1)):
        n.append(box(f'trolley_wheel_{k}', (x - 0.05, -0.02, tz0 + 0.05), (x + 0.05, 0.13, tz1 - 0.05), 'tyre', open=['bottom']))
    # the exit sign over the fire stair's door, on the back wall where the corridor turns
    n.append(box('exit', (-7.0, 2.02, R.Z1 - 0.06), (-6.4, 2.28, R.Z1 + 0.02), 'frame', open=['front'], faces={'back': 'exit'}))
    return n


def room_recipe():
    tiles = [('floor_0_0', R.X0, 0.0, R.Z0, 0.0), ('floor_1_0', 0.0, R.X1, R.Z0, 0.0),
             ('floor_0_1', R.X0, 0.0, 0.0, R.Z1), ('floor_1_1', 0.0, R.X1, 0.0, R.Z1)]
    chunks = R.back_chunks(12.0)
    m = R.shell_materials()
    for name, *_ in tiles:
        m[name] = mat_tex(P + name, '#b8b0a0')
    for name, *_ in chunks:
        m[name] = mat_tex(P + name, '#a8a69c')
    m.update({
        'wall_in': {'color': '#8a8a84'}, 'end': {'color': '#a8a49c'}, 'reveal': {'color': '#c8b080'},
        'lintel': {'color': '#9a8a6a'}, 'door_glow': {'color': '#f0e4c8', 'class': 'emissive'},
        'threshold': {'color': '#8a8478', 'class': 'emissive'}, 'beyond_wall': {'color': '#4a4e56', 'class': 'emissive'},
        'beyond': {'color': '#8a8e94', 'class': 'emissive'}, 'riser': {'color': '#4a5058', 'class': 'emissive'},
        'core_top': mat_tex(P + 'core_top', '#5a6070'), 'core_face': mat_tex(P + 'core_face', '#9a7a70', emissive=False),
        'core_back': mat_tex(P + 'core_back', '#a4a69c', bits=4, emissive=False), 'stair_dark': {'color': '#1a2a24', 'class': 'emissive'},
        'cardboard': {'color': '#a87c4c'},
        'brass': {'color': '#c09a58'}, 'brass_dark': {'color': '#7a6238'},
        'stone': {'color': '#8a7a70'}, 'soil': {'color': '#3a2c22'}, 'leaves': {'color': '#3a6a3c'},
        'foliage': mat_tex(P + 'foliage', '#3a6a3c', bits=4, emissive=False),
        'marble': {'color': '#c8bca8'}, 'counter': mat_tex(P + 'counter', '#c8c0b0', bits=4, emissive=False),
        'lamp': {'color': '#ffd890', 'class': 'emissive'},
        'leather': {'color': '#7a2e30'}, 'leather_dark': {'color': '#5e2224'},
        'carton': {'color': '#a07a50'}, 'boxes_top': mat_tex(P + 'boxes_top', '#a88660', bits=4, emissive=False),
        'trolley': {'color': '#5a7090'}, 'trolley_top': mat_tex(P + 'trolley_top', '#6a6e70', bits=4, emissive=False),
        'mop': {'color': '#d0d4d8'}, 'tyre': {'color': '#2a2a2e'},
        'frame': {'color': '#5a6068'}, 'exit': mat_tex(P + 'exit', '#30a860', bits=4),
        'padding': mat_tex(P + 'padding', '#606670', bits=4),
    })
    n = R.floor_nodes(tiles) + R.wall_nodes(chunks)
    n += R.beyond_nodes('trading', 1.4) + R.beyond_nodes('goods', 1.6, material='padding')
    n += core_nodes() + screen_nodes() + lobby_nodes() + back_nodes()
    return recipe(P + 'room', m, n, kit_lighting(lights(), AMBIENT, {'tolerance': 22, 'max_added': 260}), 2000), tiles


def glass_recipe():
    """The securities house's glass screens and its name in gold: unlit, so refinement leaves them be."""
    m = {'glass': {'color': '#a8c8d4', 'blend': 'half'}, 'glass_edge': {'color': '#d0e4ec'},
         'gold': {'color': '#e0bc6c', 'texture': {'image': 'art/lh_name.png', 'bits': 4, 'projection': 'fit'}}}
    x0, z0, x1, z1 = SCREEN_W
    n = [box('glass_w', (x0, 0.07, z0 + 0.04), (x1, CUT_H, z1 - 0.04), 'glass', open=['bottom', 'left', 'right'],
             faces={'top': 'glass_edge'})]
    x0, z0, x1, z1 = SCREEN_E
    n.append(box('glass_e', (x0 + 0.04, 0.07, z0), (x1 - 0.04, CUT_H, z1), 'glass', open=['bottom', 'back', 'front'],
                 faces={'top': 'glass_edge'}))
    g = Mesh()
    g.quad_z(SCREEN_W[1] + 0.04 - 0.035, -10.3, -5.7, 0.42, 0.72, -1, 'gold')
    n.append(g.node('name', 'gold'))
    return recipe(P + 'glass', m, n, {'bake': False}, 40)


def main():
    L = lights()
    blk = blockers()
    rec, tiles = room_recipe()
    art = {}
    for name, x0, x1, z0, z1 in tiles:
        art[P + name] = paint_floor(R, x0, x1, z0, z1, floor_base, L, AMBIENT, blk, floor_extra)
    for name, a, b in R.back_chunks(12.0):
        art[P + name] = paint_wall(a, b, 0.0, WALL_H, R.Z1, wall_base, L, AMBIENT, wall_extra)
    from dress_corridor import paint_exit_sign  # noqa: E402  (the stage's exit pictogram, drawn the same)
    art.update({P + 'section': paint_section(R.XO0, R.XO1), P + 'core_top': paint_core_top(), P + 'core_face': paint_core_face(),
                P + 'core_back': paint_core_back(), P + 'name': paint_name(), P + 'counter': paint_counter(),
                P + 'foliage': paint_foliage(), P + 'boxes_top': paint_boxes_top(), P + 'trolley_top': paint_trolley_top(),
                P + 'exit': paint_exit_sign(), P + 'padding': paint_padding()})
    for name, img in art.items():
        save_png(img, ART / f'{name}.png')
    for r_ in (rec, glass_recipe(), R.collision(P + 'room_col')):
        write_json(OUT / f'{r_["name"]}.asset.json', r_)
    placements = [{'id': P + 'room', 'asset': P + 'room', 'position': [0, 0, 0], 'collision': P + 'room_col'},
                  {'id': P + 'glass', 'asset': P + 'glass', 'position': [0, 0, 0], 'collision': 'none'}]
    data = {'format': 'after-hours-placements', 'version': 1, 'room': 'hall', 'placements': placements}
    write_json(HERE / 'hall.placements.json' if '--placements' in sys.argv else OUT / 'draft.placements.json', data)


if __name__ == '__main__':
    main()
