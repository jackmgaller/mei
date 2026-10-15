#!/usr/bin/env python3
"""Stage 2, the cinema, dressed: writes the room's Asset Kit recipes into dressed/, their textures into
dressed/art/ and (with --placements) cinema.placements.json beside this script; without it, a draft
in dressed/draft.placements.json, which ../corridor/capture.py prefers while it exists.

    python3 carts/afterhours/rooms/cinema/dress_cinema.py --placements

The auditorium on the eighth floor after the last show. The film still runs to an empty house, so
the screen's cold light falls across the rows and throws their shadows east. The projector's beam
runs high over the middle aisle from the window in the east wall. There is red carpet with a gold
motif, amber step lights along the aisles, warm sconces on the back wall and green exit
pictograms. Velvet curtains stand either side of the screen and speakers behind it. Beyond the
two doorways: the aquarium's blue service corridor behind the screen, and the staff corridor's
fluorescent light at the east door.

The floor plan is the level lead's (PLAN.md, make_cinema.py), imported for its numbers. Light as
in ../corridor/s2dress.py. The beam is its own recipe, unlit and additive. Everything named is
fictional. Needs NumPy and Pillow.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'corridor'))
import make_cinema as G  # noqa: E402  (the lead's plan: imported for its numbers only)
from s2dress import (CUT_H, WALL_H, Mesh, Room, at, blob, box, grid, kit_lighting, mat_tex, paint_floor,  # noqa: E402
                     paint_rgb, paint_section, paint_wall, r, recipe, rect, save_png, smoothstep, to_image, write_json)

OUT = HERE / 'dressed'
ART = OUT / 'art'
P = 'cn_'
R = Room(G.ROOM, P)
SX0, SZ0, SX1, SZ1 = G.SCREEN
ROW = 0.85                                    # the rows' pitch; seats face the screen (west)
SCONCES = (-6.5, -2.0, 3.0, 7.8)
EXITS = (-10.25, 10.3)                        # exit pictograms on the back wall, over the ways out
PORT = (10.9, 2.3, 0.0)                       # the projector's window
AMBIENT = 0.07


def lights():
    out = [
        {'id': 'screen', 'at': [SX1 + 0.3, 1.5, 0.2], 'color': '#b4c2ff', 'intensity': 2.6, 'range': 9.5,
         'shadows': True, 'radius': 0.9},
        {'id': 'screen_near', 'at': [SX1 + 0.2, 0.9, 0.2], 'color': '#c4ceff', 'intensity': 1.2, 'range': 3.4},
        {'id': 'door_e', 'at': [R.XO1 + 0.7, 1.6, 3.2], 'color': '#e0f0f0', 'intensity': 2.2, 'range': 3.4, 'shadows': True},
        {'id': 'door_w', 'at': [R.XO0 - 0.7, 1.4, 0.0], 'color': '#5aa4ff', 'intensity': 1.8, 'range': 2.8, 'shadows': True},
        {'id': 'beam', 'at': [6.0, 1.8, 0.0], 'color': '#8090c0', 'intensity': 0.35, 'range': 4.0, 'paint': True},
    ]
    # the house lights, left low after the show: over the side aisles' corners and the back aisle
    for k, (x, z) in enumerate(((-8.0, -3.6), (-8.0, 3.7), (7.6, -3.6), (7.6, 3.7), (-1.0, 3.9), (4.0, 3.9))):
        out.append({'id': f'house_{k}', 'at': [x, 2.6, z], 'color': '#ffd6a0', 'intensity': 0.9, 'range': 3.8,
                    'shadows': True})
    for k, x in enumerate(SCONCES):
        out.append({'id': f'sconce_{k}', 'at': [x, 1.7, R.Z1 - 0.2], 'color': '#ffae6a', 'intensity': 0.9, 'range': 2.7})
    for k, x in enumerate(EXITS):
        out.append({'id': f'exit_{k}', 'at': [x, 2.1, R.Z1 - 0.15], 'color': '#50ff90', 'intensity': 0.6, 'range': 1.8,
                    'paint': True})
    return out


def rows():
    """Every row of seats: (x of its back's east face, z0, z1, block)."""
    out = []
    for bi, (x0, x1) in enumerate(G.SEAT_X):
        n = int(round((x1 - x0) / ROW))
        for k in range(n):
            for z0, z1 in G.SEAT_Z:
                out.append((x0 + (k + 1) * (x1 - x0) / n, x0 + k * (x1 - x0) / n, z0, z1))
    return out


def blockers():
    out = [(SX0, 0, SZ0, SX1, 2.6, SZ1)]
    for xe, xw, z0, z1 in rows():
        out.append((xe - 0.16, 0, z0, xe - 0.04, 0.9, z1))
        out.append((xw + 0.12, 0.3, z0, xe - 0.1, 0.46, z1))
    return out


# ---- painting

def carpet(x, z):
    """Red carpet with a gold motif in the seats, plainer and darker in the aisles; bare concrete
    behind the screen."""
    h, w = x.shape
    rng = np.random.default_rng(int(abs(x[0, 0]) * 7 + abs(z[0, 0]) * 3))
    base = np.zeros((h, w, 3)) + np.array([150, 50, 62]) + (rng.random((h, w)) - 0.5)[..., None] * 8
    u, v = (x / 0.5) % 1, (z / 0.5) % 1
    motif = (np.abs(u - 0.5) + np.abs(v - 0.5)) < 0.16
    base = paint_rgb(base, motif, (170, 120, 60))
    aisle = np.zeros_like(x, dtype=bool)
    aisle |= np.abs(z) < 0.7
    aisle |= (z < -3.0) | (z > 3.0)
    for (a, b) in ((-3.6, -2.2), (1.2, 2.6)):
        aisle |= (x > a) & (x < b)
    aisle |= (x < -7.0) | (x > 6.0)
    base = np.where(aisle[..., None], np.array([124, 40, 52]) + (rng.random((h, w)) - 0.5)[..., None] * 6, base)
    behind = x < SX0
    base = np.where(behind[..., None], np.array([92, 94, 100]) + (rng.random((h, w)) - 0.5)[..., None] * 10, base)
    # popcorn spilled in the back aisle, which the cleaner has not reached
    pop = (rng.random((h, w)) < 0.12) & (blob(x, z, 4.4, 3.5, 0.35, 0.22) > 0.4)
    base = paint_rgb(base, pop, (236, 214, 140))
    return base


def step_lights(x, z, rgb):
    """The aisles' amber step lights, low on the seat ends, and their small pools."""
    pts = []
    for (x0, x1) in G.SEAT_X:
        for xx in np.arange(x0 + 0.42, x1, ROW):
            pts += [(xx, -0.72), (xx, 0.72), (xx, -3.02), (xx, 3.02)]
    for xx, zz in pts:
        rgb = rgb + (blob(x, z, xx, zz, 0.04) * 1.0)[..., None] * np.array([255, 190, 90])
        rgb = rgb + (blob(x, z, xx, zz, 0.28, 0.2) * 0.25)[..., None] * np.array([200, 120, 50])
    # the screen's glow on the floor in front of it, and the beam's faint spill down the middle aisle
    rgb = rgb + (np.exp(-np.clip(x - SX1, 0, None) / 0.6) * (x > SX1) * rect(x, z, SX1, SZ0, 0, SZ1, soft=0.4))[..., None] * np.array([40, 46, 80])
    return rgb


def wall_base(x, y):
    """The back wall: dark fabric panels in pleats over a wooden dado, a brass rail between."""
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array([92, 54, 70])
    pleat = np.abs(((x + 11.25) / 0.3) % 1 - 0.5) > 0.38
    base *= np.where(pleat, 0.8, 1.0)[..., None]
    base = np.where((y < 0.95)[..., None], np.array([110, 74, 52]), base)
    base = np.where((np.abs(y - 0.97) < 0.03)[..., None], np.array([200, 170, 100]), base)
    base = np.where((y > 2.25)[..., None], base * 0.6, base)
    return base


def wall_glow(x, y, rgb):
    for sx in SCONCES:       # each sconce throws a fan of light up the fabric
        fan = np.exp(-((x - sx) / (0.12 + 0.35 * np.clip(y - 1.6, 0, None))) ** 2) * (y > 1.6) * np.exp(-(y - 1.6) / 0.9)
        rgb = rgb + (fan * 0.8)[..., None] * np.array([255, 170, 100])
        rgb = rgb + (blob(x, y, sx, 1.62, 0.5, 0.3) * 0.25)[..., None] * np.array([255, 150, 90])
    for ex in EXITS:
        rgb = rgb + (blob(x, y, ex, 2.1, 0.5, 0.25) * 0.35)[..., None] * np.array([60, 255, 120])
    return rgb


def paint_seat_top(w=8, h=32, back=True):
    """A row's top from above: red velvet seats with dark gaps between them (a row runs along z)."""
    img = Image.new('RGB', (w, h), (176, 52, 64) if back else (150, 44, 56))
    d = ImageDraw.Draw(img)
    for k in range(0, h, 8):
        d.line([(0, k), (w, k)], fill=(40, 16, 22))
    if not back:
        for k in range(0, h, 8):
            d.rectangle([1, k + 2, w - 2, k + 6], fill=(170, 54, 66))
    return img


def paint_screen_top(w=6, h=48):
    """The screen in section, from above: the cut, black masking behind, the lit face at its east edge."""
    img = Image.new('RGB', (w, h), (118, 132, 158))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1, h], fill=(30, 30, 36))
    d.rectangle([w - 2, 0, w - 1, h], fill=(236, 240, 255))
    return img


def paint_curtain_top(w=12, h=12):
    """A curtain in section: its velvet folds as a zig-zag."""
    img = Image.new('RGB', (w, h), (118, 132, 158))
    d = ImageDraw.Draw(img)
    pts = []
    for k in range(0, h + 1, 3):
        pts.append((3 if (k // 3) % 2 else 8, k))
    d.line(pts, fill=(150, 30, 44), width=3)
    return img


def paint_exit_sign(w=20, h=10):
    """The exit pictogram: a figure running out through a door, white on green."""
    img = Image.new('RGB', (w, h), (30, 170, 90))
    d = ImageDraw.Draw(img)
    d.rectangle([13, 1, 18, 8], fill=(240, 255, 240))
    d.rectangle([14, 2, 17, 8], fill=(30, 170, 90))
    d.ellipse([6, 1, 8, 3], fill=(240, 255, 240))
    d.line([(7, 4), (6, 6), (4, 8)], fill=(240, 255, 240))
    d.line([(7, 4), (9, 6), (10, 8)], fill=(240, 255, 240))
    d.line([(5, 5), (10, 4)], fill=(240, 255, 240))
    return img


def paint_screen_face(w=8, h=32):
    """The screen's face, seen edge-on: the film's cold light, brighter in the middle."""
    img = Image.new('RGB', (w, h))
    px = img.load()
    for j in range(h):
        for i in range(w):
            t = 1 - abs(j / (h - 1) - 0.5) * 0.6
            px[i, j] = (int(200 * t), int(212 * t), int(255 * t))
    return img


# ---- the recipes

def seat_nodes():
    n = []
    for k, (xe, xw, z0, z1) in enumerate(rows()):
        n.append(box(f'row_{k}_back', (xe - 0.16, -0.02, z0), (xe - 0.04, 0.9, z1), 'velvet', open=['bottom'],
                     faces={'top': 'back_top'}))
        n.append(box(f'row_{k}_seat', (xw + 0.12, 0.3, z0 + 0.03), (xe - 0.15, 0.46, z1 - 0.03), 'velvet_dark',
                     open=['bottom', 'right'], faces={'top': 'seat_top'}))
    return n


def room_recipe():
    tiles = R.floor_tiles(2, 2)
    chunks = R.back_chunks(12.0)
    m = R.shell_materials()
    for name, *_ in tiles:
        m[name] = mat_tex(P + name, '#6a2a30')
    for name, *_ in chunks:
        m[name] = mat_tex(P + name, '#4a3036')
    m.update({
        'wall_in': {'color': '#6a5a64'}, 'end': {'color': '#7a6470'}, 'reveal': {'color': '#8a7a84'},
        'lintel': {'color': '#5a4a54'}, 'door_glow': {'color': '#d8e8f0', 'class': 'emissive'},
        'threshold': {'color': '#7a8a9a', 'class': 'emissive'}, 'beyond_wall': {'color': '#4a5a70', 'class': 'emissive'},
        'beyond': {'color': '#6a7a8a', 'class': 'emissive'}, 'riser': {'color': '#3a4450', 'class': 'emissive'},
        'velvet': {'color': '#a83c4c'}, 'velvet_dark': {'color': '#8a3040'},
        'back_top': mat_tex(P + 'back_top', '#b03848', bits=4, emissive=False),
        'seat_top': mat_tex(P + 'seat_top', '#963040', bits=4, emissive=False),
        'screen_top': mat_tex(P + 'screen_top', '#8a96b0', bits=4),
        'screen_face': mat_tex(P + 'screen_face', '#c8d4ff', bits=4),
        'masking': {'color': '#202026'},
        'curtain': {'color': '#a8303e'}, 'curtain_top': mat_tex(P + 'curtain_top', '#7a5060', bits=4),
        'speaker': {'color': '#3a3c44'},
        'frame': {'color': '#4a4a50'}, 'exit': mat_tex(P + 'exit', '#30a860', bits=4),
        'sconce': {'color': '#ffc488', 'class': 'emissive'}, 'brass': {'color': '#b09060'},
        'port': {'color': '#e8ecff', 'class': 'emissive'},
    })
    n = R.floor_nodes(tiles) + R.wall_nodes(chunks)
    n += R.beyond_nodes('screen', 1.4) + R.beyond_nodes('corridor', 1.4)
    # the screen, cut at 1 m: its section shows the lit face; curtains at its ends, speakers behind
    n.append(box('screen', (SX0, -0.02, SZ0 + 0.4), (SX1, CUT_H, SZ1 - 0.4), 'masking', open=['bottom', 'back', 'front'],
                 faces={'top': 'screen_top', 'right': 'screen_face'}))
    for k, (z0, z1) in enumerate(((SZ0, SZ0 + 0.4), (SZ1 - 0.4, SZ1))):
        n.append(box(f'curtain_{k}', (SX0 - 0.12, -0.02, z0), (SX1 + 0.14, CUT_H + 0.0, z1), 'curtain', open=['bottom'],
                     faces={'top': 'curtain_top'}))
    for k, (z0, z1) in enumerate(((-2.4, -1.2), (1.6, 2.8))):
        n.append(box(f'speaker_{k}', (SX0 - 0.32, -0.02, z0), (SX0, CUT_H, z1), 'speaker', open=['bottom', 'right'],
                     faces={'top': 'cut'}))
    n += seat_nodes()
    # sconces and exit signs on the back wall, the projector's port in the east wall
    for k, x in enumerate(SCONCES):
        n.append(box(f'sconce_{k}', (x - 0.12, 1.5, R.Z1 - 0.1), (x + 0.12, 1.66, R.Z1 + 0.02), 'brass', open=['front'],
                     faces={'top': 'sconce', 'back': 'sconce'}))
    for k, x in enumerate(EXITS):
        n.append(box(f'exit_{k}', (x - 0.25, 1.98, R.Z1 - 0.06), (x + 0.25, 2.24, R.Z1 + 0.02), 'frame', open=['front'],
                     faces={'back': 'exit'}))
    n.append(box('port', (R.X1 - 0.04, 2.15, -0.3), (R.X1 + 0.02, 2.45 - 0.06, 0.3), 'port', open=['right']))
    return recipe(P + 'room', m, n, kit_lighting(lights(), AMBIENT, {'tolerance': 22, 'max_added': 260}), 2000)


def beam_recipe():
    """The projector's beam: two additive sheets from the window to the screen, high over the middle
    aisle; unlit."""
    px, py, pz = PORT
    m = {'beam': {'color': '#080c18', 'blend': 'add'}, 'beam_core': {'color': '#0c1224', 'blend': 'add'}}
    a = Mesh()
    a.poly([(px, py, pz), (SX1 + 0.05, 1.6, -1.7), (SX1 + 0.05, 1.6, 2.1)], (0, 1, 0), 'beam')
    a.poly([(px, py - 0.02, pz), (SX1 + 0.05, 1.9, -0.7), (SX1 + 0.05, 1.9, 1.1)], (0, 1, 0), 'beam_core')
    return recipe(P + 'beam', m, [a.node('beam', 'beam')], {'bake': False}, 20)


def main():
    L = lights()
    blk = blockers()
    tiles = R.floor_tiles(2, 2)
    art = {}
    for name, x0, x1, z0, z1 in tiles:
        art[P + name] = paint_floor(R, x0, x1, z0, z1, carpet, L, AMBIENT, blk, step_lights)
    for name, a, b in R.back_chunks(12.0):
        art[P + name] = paint_wall(a, b, 0.0, WALL_H, R.Z1, wall_base, L, AMBIENT, wall_glow, w=255)
    art.update({P + 'section': paint_section(R.XO0, R.XO1), P + 'back_top': paint_seat_top(),
                P + 'seat_top': paint_seat_top(back=False), P + 'screen_top': paint_screen_top(),
                P + 'curtain_top': paint_curtain_top(), P + 'exit': paint_exit_sign(), P + 'screen_face': paint_screen_face()})
    for name, img in art.items():
        save_png(img, ART / f'{name}.png')
    for rec in (room_recipe(), beam_recipe(), R.collision(P + 'room_col')):
        write_json(OUT / f'{rec["name"]}.asset.json', rec)
    placements = [{'id': P + 'room', 'asset': P + 'room', 'position': [0, 0, 0], 'collision': P + 'room_col'},
                  {'id': P + 'beam', 'asset': P + 'beam', 'position': [0, 0, 0], 'collision': 'none'}]
    data = {'format': 'after-hours-placements', 'version': 1, 'room': 'cinema', 'placements': placements}
    write_json(HERE / 'cinema.placements.json' if '--placements' in sys.argv else OUT / 'draft.placements.json', data)


if __name__ == '__main__':
    main()
