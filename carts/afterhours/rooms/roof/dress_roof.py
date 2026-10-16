#!/usr/bin/env python3
"""The tower, the roof, dressed: writes the room's Asset Kit recipes into dressed/, their textures into
dressed/art/ and (with --placements) roof.placements.json beside this script; without it, a draft
in dressed/draft.placements.json, which ../corridor/capture.py prefers while it exists.

    python3 carts/afterhours/rooms/roof/dress_roof.py --placements

The top of the tower under the moon, 1990. The roof's membrane is dark and wet: seams, drains,
puddles holding the red warning lights, a paver path from the chairman's stair house. On the roof:

- the chairman's helipad: a green deck, its yellow ring and white H, green edge lights;
- a windsock;
- the lift motor room over the core, cut at 1 m, its section showing three traction machines and
  the fire stair's head; louvres on its face, a bulkhead lamp at the fire stair's door;
- the searchlight's mast (the lamp on it and its beam are the game's own: a camera and its cone);
- two panel water tanks whose section shows the water inside;
- two air-conditioning units with their fans;
- the lift shaft's glazed skylight, glowing faintly from the shaft;
- low parapets with red warning lights at the corners;
- the chairman's stair house, smarter, warm, beyond the east parapet's gap.

The floor plan is the level lead's (PLAN.md, make_roof.py), imported for its numbers. Light as in
../corridor/s2dress.py. The backdrop is its own unlit recipe. Everything named is fictional. Needs
NumPy and Pillow.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'corridor'))
import make_roof as G  # noqa: E402  (the lead's plan: imported for its numbers only)
from s2dress import (CUT_H, Mesh, Room, at, blob, box, grid, kit_lighting, mat_tex, paint_floor,  # noqa: E402
                     paint_rgb, paint_section, paint_wall, recipe, rect, save_png, to_image, write_json)

sys.path.insert(0, str(HERE.parents[1] / 'water'))   # agent W: the moving water (NOTES_W.md)
import wateranim  # noqa: E402

OUT = HERE / 'dressed'
PUDDLES = ((-3.8, -3.6, 0.9, 0.35), (0.2, 3.3, 0.6, 0.3), (9.8, -3.7, 0.6, 0.3), (-9.9, 2.8, 0.5, 0.4))   # agent W: the paint's
ART = OUT / 'art'
P = 'rf_'
R = Room(G.ROOM, P)
PROPS = {p[0]: p[2] for p in G.ROOM['props']}
MX0, MZ0, MX1, MZ1 = PROPS['motor_room']
PAD = PROPS['helipad']
PAD_C = ((PAD[0] + PAD[2]) / 2, (PAD[1] + PAD[3]) / 2)
MAST = (-1.0, -0.1)
STAIR_DOOR = (1.1, 2.3)
PARAPET = 1.15
SOCK = (10.55, -2.1)
AMBIENT = 0.15


def lights():
    return [
        {'id': 'stair_house', 'at': [R.XO1 + 0.8, 1.9, 3.0], 'color': '#ffd49a', 'intensity': 2.0, 'range': 3.2, 'shadows': True},
        {'id': 'bulkhead', 'at': [MX0 - 0.25, 1.9, 1.7], 'color': '#ffcc88', 'intensity': 1.4, 'range': 2.8, 'shadows': True},
        {'id': 'skylight', 'at': [-1.9, 0.9, -2.2], 'color': '#9ab8e0', 'intensity': 0.7, 'range': 1.8},
        {'id': 'moon', 'at': [-4.0, 9.0, -9.0], 'color': '#8ea4d8', 'intensity': 1.2, 'range': 30.0, 'shadows': True,
         'radius': 0.8, 'paint': True},
        {'id': 'warn_w', 'at': [R.X0 + 0.2, 1.3, R.Z1 - 0.1], 'color': '#ff3020', 'intensity': 0.8, 'range': 1.6, 'paint': True},
        {'id': 'warn_e', 'at': [R.X1 - 0.2, 1.3, R.Z1 - 0.1], 'color': '#ff3020', 'intensity': 0.8, 'range': 1.6, 'paint': True},
        {'id': 'mast', 'at': [MAST[0], 2.2, MAST[1]], 'color': '#fff4d8', 'intensity': 0.5, 'range': 2.6, 'paint': True},
    ]


def blockers():
    out = [(MX0, 0, MZ0, MX1, 3.0, MZ1)]
    for name in ('tank_e', 'tank_w'):
        x0, z0, x1, z1 = PROPS[name]
        out.append((x0, 0, z0, x1, 2.6, z1))
    for name, h in (('plant_a', 1.6), ('plant_b', 1.6), ('skylight', 1.2)):
        x0, z0, x1, z1 = PROPS[name]
        out.append((x0, 0, z0, x1, h, z1))
    out += [(R.XO0, 0, R.Z1, R.XO1, PARAPET, R.ZO1), (R.XO0, 0, R.Z0, R.X0, PARAPET, R.Z1), (R.X1, 0, R.Z0, R.XO1, PARAPET, R.Z1),
            (R.XO0, 0, R.ZO0, R.XO1, 1.0, R.Z0), (MAST[0] - 0.08, 0, MAST[1] - 0.08, MAST[0] + 0.08, 2.3, MAST[1] + 0.08)]
    return out


# ---- painting

def floor_base(x, z):
    h, w = x.shape
    rng = np.random.default_rng(int(abs(x[0, 0]) * 5 + abs(z[0, 0]) * 7) + 3)
    base = np.zeros((h, w, 3)) + np.array([96, 100, 110]) + (rng.random((h, w)) - 0.5)[..., None] * 12
    seam = np.abs(((x + 11) / 1.0) % 1 - 0.5) > 0.47
    base *= np.where(seam, 1.12, 1.0)[..., None]
    # the paver path from the chairman's stair to his helipad
    path = (rect(x, z, PAD[2], 2.5, R.X1, 3.5) + rect(x, z, PAD[2] - 0.4, PAD[3], PAD[2] + 0.6, 3.5)) > 0
    pav = np.zeros((h, w, 3)) + np.array([150, 148, 140])
    pav *= np.where((np.abs((x / 0.5) % 1 - 0.5) > 0.44) | (np.abs((z / 0.5) % 1 - 0.5) > 0.44), 0.8, 1.0)[..., None]
    base = np.where(path[..., None], pav, base)
    # the helipad: a green deck, its edge line, the yellow ring and the white H
    px0, pz0, px1, pz1 = PAD
    deck = rect(x, z, px0, pz0, px1, pz1) > 0
    base = paint_rgb(base, deck, (70, 92, 84))
    base = paint_rgb(base, deck & (rect(x, z, px0 + 0.12, pz0 + 0.12, px1 - 0.12, pz1 - 0.12) == 0), (220, 220, 210))
    d = np.hypot(x - PAD_C[0], z - PAD_C[1])
    base = paint_rgb(base, np.abs(d - 1.85) < 0.13, (230, 196, 50))
    cx, cz = PAD_C
    hh = (rect(x, z, cx - 0.75, cz - 0.95, cx - 0.45, cz + 0.95) + rect(x, z, cx + 0.45, cz - 0.95, cx + 0.75, cz + 0.95)
          + rect(x, z, cx - 0.45, cz - 0.15, cx + 0.45, cz + 0.15)) > 0
    base = paint_rgb(base, hh, (236, 236, 230))
    # drains, and puddles where the membrane sags
    for (dx, dz) in ((-3.5, 3.9), (4.0, -3.9), (-10.3, -3.9), (10.3, 0.3)):
        base = paint_rgb(base, blob(x, z, dx, dz, 0.12) > 0.5, (40, 42, 46))
    pud = np.zeros_like(x)
    for (sx, sz, a, b) in ((-3.8, -3.6, 0.9, 0.35), (0.2, 3.3, 0.6, 0.3), (9.8, -3.7, 0.6, 0.3), (-9.9, 2.8, 0.5, 0.4)):
        pud += blob(x, z, sx, sz, a, b)
    base = np.where((pud > 0.5)[..., None], np.array([46, 52, 66]), base)
    return base


def floor_extra(x, z, rgb):
    # the puddles hold the sky and the red warning lights
    pud = np.zeros_like(x)
    for (sx, sz, a, b) in ((-3.8, -3.6, 0.9, 0.35), (0.2, 3.3, 0.6, 0.3), (9.8, -3.7, 0.6, 0.3), (-9.9, 2.8, 0.5, 0.4)):
        pud += blob(x, z, sx, sz, a, b)
    rgb = rgb + ((pud > 0.5) * 0.18)[..., None] * np.array([90, 110, 170])
    rgb = rgb + ((pud > 0.5) * blob(x, z, -9.9, 3.4, 0.2, 0.15) * 0.8)[..., None] * np.array([255, 40, 30])
    # the helipad's edge lights: green, every metre round the deck
    px0, pz0, px1, pz1 = PAD
    pts = [(xx, zz) for xx in np.arange(px0, px1 + 0.01, 1.0) for zz in (pz0, pz1)]
    pts += [(xx, zz) for zz in np.arange(pz0 + 1.2, pz1, 1.2) for xx in (px0, px1)]
    for (lx, lz) in pts:
        rgb = rgb + (blob(x, z, lx, lz, 0.05) * 1.2)[..., None] * np.array([80, 255, 120])
        rgb = rgb + (blob(x, z, lx, lz, 0.3) * 0.18)[..., None] * np.array([40, 200, 90])
    # the searchlight's mast foot catches its lamp's spill
    rgb = rgb + (blob(x, z, MAST[0], MAST[1] - 0.3, 0.8, 0.5) * 0.15)[..., None] * np.array([255, 240, 200])
    return rgb


def parapet_base(x, y):
    h, w = x.shape
    rng = np.random.default_rng(9)
    base = np.zeros((h, w, 3)) + np.array([120, 122, 126]) + (rng.random((h, w)) - 0.5)[..., None] * 10
    base *= (1 - 0.15 * np.clip(1 - y / 0.4, 0, 1))[..., None]                 # damp at its foot
    stains = (np.sin(x * 5.3) > 0.85) & (y > 0.3)
    base = np.where(stains[..., None], base * 0.88, base)
    joint = np.abs(((x + 11.25) / 2.0) % 1 - 0.5) > 0.49
    return np.where(joint[..., None], base * 0.75, base)


def parapet_extra(x, y, rgb):
    for ex in (R.X0 + 0.2, R.X1 - 0.2):
        rgb = rgb + (blob(x, y, ex, 1.05, 0.5, 0.25) * 0.5)[..., None] * np.array([255, 40, 30])
    return rgb


def paint_motor_top(w=160, h=86):
    """The motor room cut at 1 m (north up): three traction machines on their beds over the shafts,
    their sheaves and ropes going down, a control cabinet; the fire stair's head at the west, its
    door in the west face."""
    x, z = grid(MX0, MX1, MZ0, MZ1, w, h)
    cut = np.array([118, 132, 158])
    rgb = np.zeros((h, w, 3)) + cut
    rgb = paint_rgb(rgb, rect(x, z, MX0 + 0.2, MZ0 + 0.2, MX1 - 0.2, MZ1 - 0.2) > 0, (52, 56, 62))
    for k in range(3):
        a = -4.4 + k * 1.4
        rgb = paint_rgb(rgb, rect(x, z, a + 0.15, 0.5, a + 1.25, 1.9) > 0, (84, 90, 100))       # the bed
        rgb = paint_rgb(rgb, rect(x, z, a + 0.3, 0.7, a + 1.1, 1.3) > 0, (60, 110, 90))         # the motor
        rgb = paint_rgb(rgb, np.abs(np.hypot(x - (a + 0.7), z - 1.6) - 0.22) < 0.05, (170, 170, 176))   # the sheave
        rgb = paint_rgb(rgb, (np.abs(x - (a + 0.62)) < 0.02) & (z > 1.35) & (z < 1.85), (30, 30, 34))
    rgb = paint_rgb(rgb, rect(x, z, 0.4, 2.6, 2.6, 3.2) > 0, (150, 156, 164))                     # control cabinets
    rgb = paint_rgb(rgb, rect(x, z, 0.5, 2.7, 2.5, 3.1) > 0, (110, 116, 126))
    for k in range(5):
        rgb = paint_rgb(rgb, blob(x, z, 0.7 + k * 0.4, 2.9, 0.04) > 0.5, (80, 220, 120) if k % 2 else (255, 180, 60))
    stair = rect(x, z, MX0 + 0.2, 2.0, -1.2, MZ1 - 0.2) > 0
    rgb = paint_rgb(rgb, stair, (82, 86, 94))
    rgb = paint_rgb(rgb, stair & (x > MX0 + 1.1) & ((x * 3.7) % 1 < 0.22), (54, 56, 62))
    rgb = paint_rgb(rgb, rect(x, z, MX0 - 0.01, STAIR_DOOR[0], MX0 + 0.2, STAIR_DOOR[1]) > 0, (60, 100, 80))
    return to_image(rgb, dither=0)


def paint_motor_face(w=128, h=16):
    """The motor room's face: board-marked concrete, two louvred vents."""
    img = Image.new('RGB', (w, h), (132, 134, 138))
    d = ImageDraw.Draw(img)
    for k in range(0, h, 3):
        d.line([(0, k), (w, k)], fill=(122, 124, 128))
    for x0 in (20, 84):
        d.rectangle([x0, 3, x0 + 22, 13], fill=(80, 84, 90))
        for k in range(4, 13, 2):
            d.line([(x0 + 1, k), (x0 + 21, k)], fill=(150, 154, 160))
    d.rectangle([0, h - 2, w, h], fill=(90, 92, 96))
    return img


def paint_tank_side(w=16, h=16):
    """A panel water tank's side: pale FRP panels on a grid, a ladder."""
    img = Image.new('RGB', (w, h), (196, 204, 210))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 5):
        d.line([(k, 0), (k, h)], fill=(160, 168, 176))
        d.line([(0, k), (w, k)], fill=(160, 168, 176))
    d.line([(12, 0), (12, h)], fill=(90, 94, 100))
    d.line([(14, 0), (14, h)], fill=(90, 94, 100))
    for k in range(1, h, 3):
        d.line([(12, k), (14, k)], fill=(90, 94, 100))
    return img


def paint_tank_cut(w=24, h=24):
    """The tank cut at 1 m: its walls in section, the dark water inside with a glint."""
    img = Image.new('RGB', (w, h), (118, 132, 158))
    d = ImageDraw.Draw(img)
    d.rectangle([2, 2, w - 3, h - 3], fill=(24, 60, 70))
    d.line([(5, 8), (12, 8)], fill=(80, 140, 150))
    d.line([(10, 15), (18, 15)], fill=(60, 120, 130))
    return img


def paint_plant_side(w=16, h=8):
    img = Image.new('RGB', (w, h), (170, 172, 168))
    d = ImageDraw.Draw(img)
    for k in range(1, h - 1, 2):
        d.line([(1, k), (w - 2, k)], fill=(110, 112, 110))
    return img


def paint_plant_cut(w=28, h=28):
    """An air-conditioning unit in section from above: two fans in their shrouds, the coil."""
    img = Image.new('RGB', (w, h), (118, 132, 158))
    d = ImageDraw.Draw(img)
    d.rectangle([2, 2, w - 3, h - 3], fill=(60, 64, 70))
    for cy in (8, 20):
        d.ellipse([7, cy - 5, 20, cy + 5], fill=(30, 32, 36), outline=(150, 154, 160))
        d.line([(9, cy), (18, cy)], fill=(110, 114, 120))
        d.line([(13, cy - 4), (13, cy + 4)], fill=(110, 114, 120))
    d.rectangle([22, 4, 24, h - 5], fill=(170, 120, 80))
    return img


def paint_skylight_cut(w=24, h=12):
    """The shaft's skylight in section: glazing bars over the shaft's faint light far below."""
    img = Image.new('RGB', (w, h), (118, 132, 158))
    d = ImageDraw.Draw(img)
    d.rectangle([1, 1, w - 2, h - 2], fill=(60, 80, 110))
    for k in range(3, w - 2, 4):
        d.line([(k, 1), (k, h - 2)], fill=(160, 170, 180))
    d.ellipse([8, 3, 15, 8], fill=(110, 140, 180))
    return img


def paint_sock(w=8, h=8):
    img = Image.new('RGB', (w, h), (230, 230, 226))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 4):
        d.rectangle([k, 0, k + 1, h], fill=(210, 50, 40))
    return img


# ---- the recipes

def motor_nodes():
    """The motor room over the core, cut at 1 m: its face, its west face with the fire stair's
    doorway (the door stands open into the stair), against the back parapet."""
    m = Mesh()
    a, b = STAIR_DOOR
    m.quad_y(CUT_H, MX0, MX1, MZ0, MZ1, 1, 'motor_top')
    m.quad_z(MZ0, MX0, MX1, -0.02, CUT_H, -1, 'motor_face')
    m.quad_x(MX1, -0.02, CUT_H, MZ0, MZ1, 1, 'motor_face')
    m.quad_x(MX0, -0.02, CUT_H, MZ0, a, -1, 'motor_face')
    m.quad_x(MX0, -0.02, CUT_H, b, MZ1, -1, 'motor_face')
    m.quad_x(MX0 + 0.35, -0.02, CUT_H, a, b, -1, 'stair_dark')
    m.quad_z(a, MX0, MX0 + 0.35, -0.02, CUT_H, 1, 'motor_face')
    m.quad_z(b, MX0, MX0 + 0.35, -0.02, CUT_H, -1, 'motor_face')
    n = [m.node('motor_room', 'motor_face')]
    # the bulkhead lamp by the door, the searchlight's mast (the game draws the lamp on it, a camera)
    n.append(box('bulkhead', (MX0 - 0.08, 0.86, b + 0.06), (MX0 + 0.01, 0.98, b + 0.22), 'lamp', open=['right']))
    mx, mz = MAST
    n.append(at({'id': 'mast', 'op': 'cylinder', 'radius': 0.06, 'height': 2.3, 'segments': 6, 'material': 'steel',
                 'caps': False}, translate=[mx, 1.13, mz]))
    return n


def roof_props():
    n = []
    for name in ('tank_e', 'tank_w'):
        x0, z0, x1, z1 = PROPS[name]
        n.append(box(f'{name}_stand', (x0 + 0.1, -0.02, z0 + 0.1), (x1 - 0.1, 0.32, z1 - 0.1), 'steel', open=['bottom', 'top']))
        n.append(box(name, (x0, 0.3, z0), (x1, CUT_H, z1), 'tank_side', open=['bottom'], faces={'top': 'tank_cut'}))
    for name in ('plant_a', 'plant_b'):
        x0, z0, x1, z1 = PROPS[name]
        n.append(box(name, (x0, -0.02, z0), (x1, CUT_H, z1), 'plant_side', open=['bottom'], faces={'top': 'plant_cut'}))
    x0, z0, x1, z1 = PROPS['skylight']
    n.append(box('skylight_kerb', (x0, -0.02, z0), (x1, 0.4, z1), 'kerb', open=['bottom', 'top']))
    n.append(box('skylight', (x0 + 0.06, 0.38, z0 + 0.06), (x1 - 0.06, CUT_H, z1 - 0.06), 'sky_side', open=['bottom'],
                 faces={'top': 'sky_cut'}))
    # the windsock on its pole
    sx, sz = SOCK
    n.append(at({'id': 'sock_pole', 'op': 'cylinder', 'radius': 0.035, 'height': 2.0, 'segments': 4, 'caps': False,
                 'material': 'steel'}, translate=[sx, 0.98, sz]))
    n.append(at({'id': 'sock', 'op': 'cone', 'radius': 0.14, 'height': 0.7, 'segments': 6, 'material': 'sock'},
                translate=[sx - 0.36, 1.86, sz], rotate=[0, 0, 95]))
    # the red warning lights on the back parapet's corners
    for k, x in enumerate((R.X0 + 0.2, R.X1 - 0.2)):
        n.append(box(f'warn_{k}', (x - 0.07, PARAPET - 0.02, R.Z1 + 0.05), (x + 0.07, PARAPET + 0.12, R.Z1 + 0.19), 'warn',
                     open=['bottom']))
    return n


def room_recipe():
    tiles = R.floor_tiles(2, 2)
    chunks = R.back_chunks(12.0)
    m = R.shell_materials()
    for name, *_ in tiles:
        m[name] = mat_tex(P + name, '#5a5e66')
    for name, *_ in chunks:
        m[name] = mat_tex(P + name, '#7a7c80')
    m.update({
        'wall_in': {'color': '#7a7c82'}, 'end': {'color': '#8a8c92'}, 'reveal': {'color': '#9a9ca2'},
        'cap': {'color': '#a8aab0'}, 'lintel': {'color': '#8a8c92'}, 'door_glow': {'color': '#f0e0c0', 'class': 'emissive'},
        'threshold': {'color': '#a89a84', 'class': 'emissive'}, 'beyond_wall': {'color': '#8a7a64', 'class': 'emissive'},
        'beyond': {'color': '#b0a088', 'class': 'emissive'}, 'riser': {'color': '#5a5048', 'class': 'emissive'},
        'motor_top': mat_tex(P + 'motor_top', '#5a6070'), 'motor_face': mat_tex(P + 'motor_face', '#7a7c80', bits=4, emissive=False),
        'stair_dark': {'color': '#1a2a24', 'class': 'emissive'}, 'lamp': {'color': '#ffd890', 'class': 'emissive'},
        'steel': {'color': '#7a8088'},
        'tank_side': mat_tex(P + 'tank_side', '#b8c0c8', bits=4, emissive=False), 'tank_cut': mat_tex(P + 'tank_cut', '#3a5a64', bits=4),
        'plant_side': mat_tex(P + 'plant_side', '#9a9c9a', bits=4, emissive=False), 'plant_cut': mat_tex(P + 'plant_cut', '#5a6068', bits=4),
        'kerb': {'color': '#8a8c90'}, 'sky_side': {'color': '#7a9ab8'}, 'sky_cut': mat_tex(P + 'sky_cut', '#5a7090', bits=4),
        'sock': mat_tex(P + 'sock', '#d08070', bits=4, emissive=False), 'warn': {'color': '#ff3020', 'class': 'emissive'},
    })
    n = R.floor_nodes(tiles) + R.wall_nodes(chunks, height=PARAPET, top='cap')
    n += R.beyond_nodes('private', 1.6)
    n += motor_nodes() + roof_props()
    return recipe(P + 'room', m, n, kit_lighting(lights(), AMBIENT, {'tolerance': 22, 'max_added': 220},
                                                 direction=(-0.3, 0.8, -0.5), diffuse=0.3), 1800), tiles


def wwater_recipe():
    """Agent W (NOTES_W.md): the wind on the puddles, glints moving over each (the painted puddle's
    shape, blob > 0.5: an ellipse 0.83 of its radii), lit by the night sky and, in the one by the
    corner, the red warning light it holds."""
    ov = wateranim.Overlay(P + 'wwater')
    ov.material('glint', 'w_ripple', scale=1.0)      # finer: a puddle is a metre across
    for (sx, sz, a, b) in PUDDLES:
        ov.ellipse('glint', 0.03, sx, sz, a * 0.8, b * 0.8, n=10)
        ov.light((sx, 1.2, sz - 0.3), '#8098d8', 2.6, 2.2, id=f'sky_{len(ov.lights)}')
    ov.light((-9.9, 0.25, 3.3), '#ff3020', 5.0, 1.0, id='warning')
    return ov.recipe(ART, refine={'tolerance': 20, 'max_added': 16})


def main():
    L = lights()
    blk = blockers()
    rec, tiles = room_recipe()
    art = {}
    for name, x0, x1, z0, z1 in tiles:
        art[P + name] = paint_floor(R, x0, x1, z0, z1, floor_base, L, AMBIENT, blk, floor_extra, occlusion=0.25)
    for name, a, b in R.back_chunks(12.0):
        art[P + name] = paint_wall(a, b, 0.0, PARAPET, R.Z1, parapet_base, L, AMBIENT, parapet_extra, h=24)
    art.update({P + 'section': paint_section(R.XO0, R.XO1), P + 'motor_top': paint_motor_top(), P + 'motor_face': paint_motor_face(),
                P + 'tank_side': paint_tank_side(), P + 'tank_cut': paint_tank_cut(), P + 'plant_side': paint_plant_side(),
                P + 'plant_cut': paint_plant_cut(), P + 'sky_cut': paint_skylight_cut(),
                P + 'sock': paint_sock()})
    for name, img in art.items():
        save_png(img, ART / f'{name}.png')
    for r_ in (rec, R.collision(P + 'room_col')):
        write_json(OUT / f'{r_["name"]}.asset.json', r_)
    write_json(OUT / f'{P}wwater.asset.json', wwater_recipe())      # agent W
    placements = [{'id': P + 'room', 'asset': P + 'room', 'position': [0, 0, 0], 'collision': P + 'room_col'},
                  {'id': P + 'wwater', 'asset': P + 'wwater', 'position': [0, 0, 0], 'collision': 'none'}]     # agent W
    data = {'format': 'after-hours-placements', 'version': 1, 'room': 'roof', 'placements': placements}
    write_json(HERE / 'roof.placements.json' if '--placements' in sys.argv else OUT / 'draft.placements.json', data)


if __name__ == '__main__':
    main()
