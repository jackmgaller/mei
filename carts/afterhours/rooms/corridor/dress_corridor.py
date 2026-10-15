#!/usr/bin/env python3
"""Stage 2, the staff corridor, dressed: writes the room's Asset Kit recipes into dressed/, their
textures into dressed/art/ and (with --placements) corridor.placements.json beside this script;
without it, a draft in dressed/draft.placements.json, which capture.py prefers while it exists.

    python3 carts/afterhours/rooms/corridor/dress_corridor.py --placements

The back of house on the eighth floor, crossed three times, so it is dressed to be read again:

- fluorescent tubes down the corridor, one of them failing and dim;
- grey sealed concrete with yellow walkway lines, a hatched bay for the roll cages, scuffs and a
  stencilled arrow to the stair;
- the roll cages, their wire sides see-through, stock inside;
- the security office lit cold by its tube and its bank of monitors, its window throwing a long
  pale trapezoid into the back lane. The column stands in it with its shadow running to the back
  wall: the room's secret, drawn in light;
- pallets of wrapped stock;
- on the back wall: a staff notice board, a red hose reel, a big stencilled 8F, and the blue staff
  door's frame with the booth's stair climbing beyond it in warm light;
- the cinema's dark red beyond the west door, and the stair's light beyond the east one.

The floor plan is the level lead's (PLAN.md, make_corridor.py), imported for its numbers. Light as
in s2dress.py; the office's window glass is its own recipe, out of the lights' reach. Everything
named is fictional. Needs NumPy and Pillow.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import make_corridor as G  # noqa: E402  (the lead's plan: imported for its numbers only)
from s2dress import (CUT_H, WALL_H, Mesh, Room, at, blob, box, font, grid, kit_lighting, mat_tex,  # noqa: E402
                     paint_floor, paint_rgb, paint_section, paint_wall, r, recipe, rect, save_png, smoothstep,
                     tile_grid, to_image, write_json)

OUT = HERE / 'dressed'
ART = OUT / 'art'
P = 'sc_'
R = Room(G.ROOM, P)
CX0, CZ0, CX1, CZ1 = G.CAGES
OX0, OZ0, OX1, OZ1 = G.OFFICE
OT = G.OFFICE_T
WE = G.WINDOW_E
SILL, WIN_TOP = 0.85, 2.1                     # the window: glass from the sill to its head
COL = (1.15, 1.85, 1.85, 2.55)               # the column: x0, z0, x1, z1
PAL = (6.0, 2.6, 9.5, 3.5)                    # the pallets
DESK = (OX0 + 0.5, OZ0, OX1 - 0.5, -2.8)
BLUE = (-6.6, -5.4)                           # the blue door in the back wall
TUBES = [(-10.0, 1.4), (-6.0, 1.4), (-2.0, 1.4), (6.0, 1.4), (10.0, 1.4), (-10.0, -2.3), (-6.0, -2.3), (8.0, -2.3)]
DIM_TUBE = 3                                  # the failing one
NOTICE = (-10.6, -8.6, 1.05, 1.8)             # x0, x1, y0, y1 on the back wall
HOSE = (4.4, 5.1, 0.85, 1.6)
AMBIENT = 0.1


def lights():
    out = []
    for k, (x, z) in enumerate(TUBES):
        dim = k == DIM_TUBE
        out.append({'id': f'tube_{k}', 'at': [x, 2.6, z], 'color': '#c8e8c8' if dim else '#e4f0f2',
                    'intensity': 0.45 if dim else (1.45 if z > 0 else 1.2), 'range': 4.4, 'line': 1.2, 'shadows': True})
    out += [
        {'id': 'office', 'at': [1.5, 2.5, -1.7], 'color': '#e8f4ff', 'intensity': 1.6, 'range': 6.4, 'shadows': True,
         'samples': 1},
        # the window itself, as the floor sees it: the office's light leaving through the glass (painted
        # only), so that the column's shadow runs crisp to the back wall
        {'id': 'window', 'at': [0.8, 1.5, -0.3], 'color': '#dceeff', 'intensity': 1.5, 'range': 5.2, 'shadows': True,
         'paint': True, 'zmin': OZ1},
        {'id': 'monitors', 'at': [1.5, 1.0, -2.75], 'color': '#70d0e0', 'intensity': 1.0, 'range': 2.2},
        {'id': 'door_cinema', 'at': [R.XO0 - 0.7, 1.4, -2.0], 'color': '#d06070', 'intensity': 1.2, 'range': 2.6, 'shadows': True},
        {'id': 'door_booth', 'at': [-6.0, 2.6, R.ZO1 + 1.4], 'color': '#ffc88a', 'intensity': 2.2, 'range': 3.6, 'shadows': True},
        {'id': 'door_shop', 'at': [R.XO1 + 0.7, 1.6, 2.0], 'color': '#e8f2ff', 'intensity': 2.0, 'range': 3.0, 'shadows': True},
        {'id': 'exit', 'at': [11.9, 2.15, R.Z1 - 0.15], 'color': '#50ff90', 'intensity': 0.5, 'range': 1.6, 'paint': True},
        {'id': 'hose', 'at': [4.75, 1.25, R.Z1 - 0.2], 'color': '#ff5040', 'intensity': 0.25, 'range': 1.0, 'paint': True},
    ]
    return out


def blockers():
    """As things really stand, up to the ceiling where they are cut at 1 m."""
    out = [(CX0, 0, CZ0, CX1, 1.8, CZ1),
           (OX0, 0, OZ0, OX0 + OT, 2.8, OZ1), (OX1 - OT, 0, OZ0, OX1, 2.8, OZ1),
           (WE, 0, OZ1 - OT, OX1, 2.8, OZ1),
           (OX0, 0, OZ1 - OT, WE, SILL, OZ1), (OX0, WIN_TOP, OZ1 - OT, WE, 2.8, OZ1),
           (COL[0], 0, COL[1], COL[2], 2.8, COL[3]),
           (PAL[0], 0, PAL[1], PAL[2], 0.9, PAL[3]),
           (DESK[0], 0, DESK[1], DESK[2], 0.75, DESK[3])]
    return out


# ---- painting

def floor_base(x, z):
    h, w = x.shape
    rng = np.random.default_rng(int(abs(x[0, 0]) * 10) + 7)
    base = np.zeros((h, w, 3)) + np.array([150, 152, 150]) + (rng.random((h, w)) - 0.5)[..., None] * 12
    # sealed concrete in pours 3 m long, with saw cuts
    base *= np.where(np.abs(((x + 12.5) / 3.125) % 1 - 0.5) > 0.49, 0.8, 1.0)[..., None]
    # scuffs: dark arcs where the cages are swung round, and wheel tracks along the lanes
    for (sx, sz) in ((-4.2, -1.9), (-9.6, 1.5), (3.2, 1.1), (9.8, 0.4)):
        base *= (1 - 0.12 * np.exp(-((np.hypot(x - sx, z - sz) - 0.7) / 0.08) ** 2))[..., None]
    for tz in (-2.15, -1.7, 2.05, 2.5):
        base *= (1 - 0.06 * np.exp(-((z - tz) / 0.05) ** 2))[..., None]
    yellow = (226, 186, 46)
    # walkway lines along the front and the back of the corridor, and round the office's front
    for lz in (-3.2, 3.2):
        base = paint_rgb(base, (np.abs(z - lz) < 0.05) & ~((x > OX0 - 0.3) & (x < OX1 + 0.3) & (lz < 0)), yellow)
    # the cages' bay: a hatched outline round them
    bay = rect(x, z, CX0 - 0.35, CZ0 - 0.35, CX1 + 0.35, CZ1 + 0.35) * (1 - rect(x, z, CX0 - 0.2, CZ0 - 0.2, CX1 + 0.2, CZ1 + 0.2))
    stripe = ((x + z) / 0.25) % 1 < 0.5
    base = paint_rgb(base, (bay > 0) & stripe, yellow)
    base = paint_rgb(base, (bay > 0) & ~stripe, (40, 40, 40))
    # a stencilled arrow toward the stair, and the drain
    ax = (x > 8.6) & (x < 10.4) & (np.abs(z - 0.0) < 0.12)
    head = (x >= 10.4) & (x < 10.9) & (np.abs(z) < (10.9 - x) * 0.7)
    base = paint_rgb(base, ax | head, (232, 232, 222))
    base = paint_rgb(base, rect(x, z, -0.3, 1.0, 0.3, 1.2) > 0, (70, 72, 76))
    base = paint_rgb(base, (rect(x, z, -0.3, 1.0, 0.3, 1.2) > 0) & ((x * 20) % 1 < 0.4), (30, 32, 36))
    # in front of the blue door, a blue line the staff stop at
    base = paint_rgb(base, (np.abs(z - 3.0) < 0.04) & (x > BLUE[0] - 0.2) & (x < BLUE[1] + 0.2), (60, 110, 220))
    # inside the office: grey carpet tiles
    off = rect(x, z, OX0 + OT, OZ0, OX1 - OT, OZ1 - OT) > 0
    base = np.where(off[..., None], tile_grid(x, z, 0.5, (84, 90, 102), seed=3, grout=0.9), base)
    return base


def floor_extra(x, z, rgb):
    # the failing tube's flicker, caught as a faint green cast on the floor under it
    tx, tz = TUBES[DIM_TUBE]
    rgb = rgb + (blob(x, z, tx, tz, 1.1, 0.7) * 0.08)[..., None] * np.array([120, 200, 120])
    return rgb


def wall_base(x, y):
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array([176, 180, 176])
    base = np.where((y < 1.2)[..., None], np.array([140, 150, 156]), base)       # a darker dado, scuffed
    base = np.where((np.abs(y - 0.3) < 0.05)[..., None], np.array([200, 196, 120]), base)   # the bump rail
    base = np.where((np.abs(y - 0.35) < 0.01)[..., None], np.array([90, 90, 80]), base)
    joint = np.abs(((x + 12.75) / 1.2) % 1 - 0.5) > 0.48
    base *= np.where(joint & (y > 1.2), 0.9, 1.0)[..., None]
    # the blue door's painted frame
    fr = rect(x, y, BLUE[0] - 0.15, 0.0, BLUE[1] + 0.15, 2.25) * (1 - rect(x, y, BLUE[0], -1, BLUE[1], 2.1))
    base = paint_rgb(base, fr > 0, (50, 100, 200))
    # the notice board: cork, pinned papers
    nx0, nx1, ny0, ny1 = NOTICE
    board = rect(x, y, nx0, ny0, nx1, ny1) > 0
    base = paint_rgb(base, board, (170, 120, 70))
    rng = np.random.default_rng(4)
    for k in range(9):
        px = nx0 + 0.15 + rng.random() * (nx1 - nx0 - 0.5)
        py = ny0 + 0.1 + rng.random() * (ny1 - ny0 - 0.4)
        col = [(238, 236, 228), (250, 240, 160), (200, 226, 250), (250, 210, 210)][k % 4]
        base = paint_rgb(base, rect(x, y, px, py, px + 0.3, py + 0.3) > 0, col)
    # a big stencilled 8F, east of the office
    return base


def wall_extra(x, y, rgb):
    for k, (tx, tz) in enumerate(TUBES):
        if tz > 0:     # the tubes' bright streak at the wall's head
            a = 0.25 if k == DIM_TUBE else 0.6
            rgb = rgb + (np.exp(-((x - tx) / 0.9) ** 2 - ((y - 2.4) / 0.25) ** 2) * a)[..., None] * np.array([220, 240, 240])
    rgb = rgb + (blob(x, y, 11.9, 2.15, 0.45, 0.25) * 0.35)[..., None] * np.array([60, 255, 120])
    rgb = rgb + (blob(x, y, -6.0, 2.2, 0.8, 0.3) * 0.25)[..., None] * np.array([255, 190, 120])
    return rgb


def stencil_8f(img, x0, x1, chunk_x0, chunk_x1, y0=1.25, y1=2.05):
    """Paints a big 8F (the floor) on a wall chunk's image at x0 .. x1."""
    w, h = img.size
    px0 = int((x0 - chunk_x0) / (chunk_x1 - chunk_x0) * w)
    px1 = int((x1 - chunk_x0) / (chunk_x1 - chunk_x0) * w)
    py0 = int((WALL_H - y1) / WALL_H * h)
    py1 = int((WALL_H - y0) / WALL_H * h)
    if px1 <= 0 or px0 >= w:
        return img
    t = Image.new('RGBA', (px1 - px0, py1 - py0), (0, 0, 0, 0))
    d = ImageDraw.Draw(t)
    d.text((t.width / 2, t.height / 2), '8F', font=font('Figtree-Bold.ttf', py1 - py0 + 4), fill=(236, 196, 52, 255),
           anchor='mm')
    img = img.convert('RGB')
    base = img.crop((px0, py0, px1, py1))
    lit = Image.composite(Image.blend(base, t.convert('RGB'), 0.75), base, t.split()[3])
    img.paste(lit, (px0, py0))
    return img


def paint_cage_mesh(n=16):
    """The roll cages' wire sides: a lattice with holes."""
    img = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for k in range(0, n, 4):
        d.line([(k, 0), (k, n)], fill=(196, 200, 206, 255))
        d.line([(0, k), (n, k)], fill=(196, 200, 206, 255))
    return img


def paint_carton(w=16, h=16, seed=0):
    """A carton from above: tape down the middle, a printed shape."""
    rng = np.random.default_rng(seed)
    col = [(176, 138, 92), (196, 160, 110), (230, 230, 226), (160, 120, 80)][seed % 4]
    img = Image.new('RGB', (w, h), col)
    d = ImageDraw.Draw(img)
    d.rectangle([w // 2 - 1, 0, w // 2, h], fill=(214, 196, 150))
    if seed % 2:
        d.ellipse([2, 2, 6, 6], fill=(200, 60, 60) if seed % 3 else (60, 110, 200))
    return img


def paint_monitors(w=32, h=8):
    """The office's bank of monitors from the front: four views of the floors in blue-green."""
    img = Image.new('RGB', (w, h), (24, 26, 30))
    d = ImageDraw.Draw(img)
    for k in range(4):
        x0 = 1 + k * 8
        d.rectangle([x0, 1, x0 + 5, 6], fill=(40, 120, 120))
        d.line([(x0 + 1, 5), (x0 + 3, 3), (x0 + 5, 4)], fill=(150, 240, 210))
        d.point((x0 + 2 + k % 3, 2), fill=(220, 255, 240))
    return img


def paint_keys(w=16, h=12):
    """The key cabinet in section, from above: hooks with coloured tags."""
    img = Image.new('RGB', (w, h), (118, 132, 158))
    d = ImageDraw.Draw(img)
    d.rectangle([1, 1, w - 2, h - 2], fill=(70, 74, 82))
    cols = [(230, 60, 60), (60, 110, 220), (240, 200, 60), (80, 200, 120)]
    for k in range(12):
        d.point((2 + (k % 6) * 2, 3 + (k // 6) * 4), fill=cols[k % 4])
    return img


def paint_pallet_side(w=16, h=4):
    img = Image.new('RGB', (w, h), (150, 112, 70))
    d = ImageDraw.Draw(img)
    for k in (2, 7, 12):
        d.rectangle([k, 1, k + 2, h - 1], fill=(40, 30, 24))
    return img


def paint_wrap(w=16, h=16):
    """Shrink-wrapped stock on a pallet, from above: white film over cartons."""
    img = Image.new('RGB', (w, h), (208, 214, 220))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 5):
        d.line([(k, 0), (k, h)], fill=(176, 182, 190))
    d.line([(0, h // 2), (w, h // 2)], fill=(176, 182, 190))
    d.line([(1, 1), (w - 2, h - 2)], fill=(236, 240, 244))
    return img


def paint_hose(w=12, h=12):
    img = Image.new('RGB', (w, h), (190, 40, 36))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, 9, 9], outline=(240, 220, 200))
    d.ellipse([4, 4, 7, 7], fill=(120, 20, 20))
    return img


def paint_exit_sign(w=20, h=10):
    img = Image.new('RGB', (w, h), (30, 170, 90))
    d = ImageDraw.Draw(img)
    d.rectangle([13, 1, 18, 8], fill=(240, 255, 240))
    d.rectangle([14, 2, 17, 8], fill=(30, 170, 90))
    d.ellipse([6, 1, 8, 3], fill=(240, 255, 240))
    d.line([(7, 4), (6, 6), (4, 8)], fill=(240, 255, 240))
    d.line([(7, 4), (9, 6), (10, 8)], fill=(240, 255, 240))
    return img


def paint_column(w=8, h=24):
    """The column's faces: grey concrete, a yellow and black guard band at its foot."""
    img = Image.new('RGB', (w, h), (150, 156, 160))
    d = ImageDraw.Draw(img)
    for k in range(-h, w + h, 4):
        d.line([(k, h - 1), (k + 6, h - 8)], fill=(230, 190, 40), width=2)
    d.rectangle([0, 0, w, h - 9], fill=(150, 156, 160))
    d.line([(0, h - 9), (w, h - 9)], fill=(40, 40, 40))
    return img


# ---- the recipes

def cage_nodes():
    """Four roll cages side by side, wire sides you see the stock through, cut at 1 m."""
    n = []
    rng = np.random.default_rng(12)
    width = (CX1 - CX0) / 4
    for k in range(4):
        x0, x1 = CX0 + k * width + 0.03, CX0 + (k + 1) * width - 0.03
        n.append(box(f'cage_{k}', (x0, 0.08, CZ0), (x1, CUT_H, CZ1), 'mesh', open=['top', 'bottom']))
        n.append(box(f'cage_{k}_base', (x0 + 0.03, -0.02, CZ0 + 0.03), (x1 - 0.03, 0.09, CZ1 - 0.03), 'steel', open=['bottom']))
        # the stock: cartons stacked inside, the tallest cut by the section
        zs = [CZ0 + 0.08, (CZ0 + CZ1) / 2 - 0.15, (CZ0 + CZ1) / 2 + 0.05, CZ1 - 0.08]
        for j, (za, zb) in enumerate(((zs[0], zs[1]), (zs[2], zs[3]))):
            ht = [0.55, 0.75, 1.2, 0.9][(k + j) % 4]
            top = min(ht, CUT_H - 0.04)
            n.append(box(f'cage_{k}_stock_{j}', (x0 + 0.08 + 0.03 * j, 0.08, za), (x1 - 0.08, top, zb), f'carton_{(k + j) % 4}',
                         open=['bottom'], faces={'top': 'cut' if ht > CUT_H else f'carton_top_{(k + j) % 4}'}))
    return n


def office_nodes():
    n = [box('office_w', (OX0, -0.02, OZ0), (OX0 + OT, CUT_H, OZ1), 'office', open=['bottom', 'back'],
             faces={'top': 'cut', 'right': 'office_in'}),
         box('office_e', (OX1 - OT, -0.02, OZ0), (OX1, CUT_H, OZ1), 'office', open=['bottom', 'back'],
             faces={'top': 'cut', 'left': 'office_in'}),
         box('office_n', (WE, -0.02, OZ1 - OT), (OX1 - OT, CUT_H, OZ1), 'office', open=['bottom', 'right'],
             faces={'top': 'cut', 'back': 'office_in'}),
         box('office_sill', (OX0 + OT, -0.02, OZ1 - OT), (WE, SILL, OZ1), 'office', open=['bottom', 'left', 'right'],
             faces={'top': 'ledge', 'back': 'office_in'}),
         box('desk', (DESK[0], -0.02, DESK[1]), (DESK[2], 0.75, DESK[3]), 'desk', open=['bottom', 'back'],
             faces={'top': 'desk_top'}),
         box('chair_seat', (2.4, 0.42, -2.6), (2.85, 0.48, -2.15), 'chair'),
         box('chair_back', (2.42, 0.47, -2.17), (2.83, 0.9, -2.1), 'chair'),
         box('key_cabinet', (OX1 - OT - 0.5, -0.02, -0.75), (OX1 - OT - 0.02, CUT_H, -0.15), 'cabinet', open=['bottom', 'right'],
             faces={'top': 'keys'}),
         at({'id': 'thermos', 'op': 'cylinder', 'radius': 0.05, 'height': 0.26, 'segments': 6, 'material': 'thermos'},
            translate=[3.25, 0.87, -3.0])]
    # the monitors: a bank of four on the desk, tilted back toward the room
    m = Mesh()
    mx0, mx1 = 0.0, 3.0
    m.poly([(mx0, 0.8, -2.85), (mx1, 0.8, -2.85), (mx1, 0.98, -3.4), (mx0, 0.98, -3.4)], (0, 1, 0.3), 'monitors')
    m.poly([(mx0, 0.8, -2.85), (mx0, 0.98, -3.4), (mx0, 0.8, -3.4)], (-1, 0, 0), 'monitor_body')
    m.poly([(mx1, 0.8, -2.85), (mx1, 0.98, -3.4), (mx1, 0.8, -3.4)], (1, 0, 0), 'monitor_body')
    n.append(m.node('monitors', 'monitor_body'))
    return n


def room_recipe():
    tiles = R.floor_tiles(2, 1)
    chunks = R.back_chunks(10.0)
    m = R.shell_materials()
    for name, *_ in tiles:
        m[name] = mat_tex(P + name, '#8a8c8a')
    for name, *_ in chunks:
        m[name] = mat_tex(P + name, '#9a9c98')
    m.update({
        'wall_in': {'color': '#8a9098'}, 'end': {'color': '#a4aab0'}, 'reveal': {'color': '#9aa0a8'},
        'lintel': {'color': '#8a9098'}, 'door_glow': {'color': '#e8f0f4', 'class': 'emissive'},
        'threshold': {'color': '#8a8c8e', 'class': 'emissive'}, 'beyond_wall': {'color': '#6a7078', 'class': 'emissive'},
        'beyond': {'color': '#b49a7a', 'class': 'emissive'}, 'riser': {'color': '#6a5444', 'class': 'emissive'},
        'mesh': {'color': '#c4c8ce', 'double_sided': True,
                 'texture': {'image': 'art/sc_cage_mesh.png', 'bits': 4, 'projection': 'box', 'scale': [0.5, 0.5]}},
        'steel': {'color': '#7a8088'},
        'office': {'color': '#a8acb0'}, 'office_in': {'color': '#b8c0c8'}, 'ledge': {'color': '#8a9098'},
        'desk': {'color': '#8a8e94'}, 'desk_top': {'color': '#a4a8ac'}, 'chair': {'color': '#3e4656'},
        'cabinet': {'color': '#7e8890'}, 'keys': mat_tex(P + 'keys', '#5a6070', bits=4),
        'thermos': {'color': '#c03c34'}, 'monitors': mat_tex(P + 'monitors', '#2a6a6c', bits=4),
        'monitor_body': {'color': '#3a3e46'},
        'column': mat_tex(P + 'column', '#949aa0', bits=4, emissive=False),
        'pallet': mat_tex(P + 'pallet', '#8a6a44', bits=4, emissive=False), 'wrap': mat_tex(P + 'wrap', '#c8ccd2', bits=4, emissive=False),
        'wrap_side': {'color': '#b8bec6'},
        'frame': {'color': '#5a6068'}, 'exit': mat_tex(P + 'exit', '#30a860', bits=4),
        'hose': mat_tex(P + 'hose', '#b0302c', bits=4), 'hose_box': {'color': '#b0302c'},
    })
    for k in range(4):
        m[f'carton_{k}'] = {'color': ['#a07a50', '#b48c60', '#d0d0cc', '#906a46'][k]}
        m[f'carton_top_{k}'] = mat_tex(f'{P}carton_{k}', ['#b08a5c', '#c49c6e', '#e0e0dc', '#a07850'][k], bits=4, emissive=False)
    n = R.floor_nodes(tiles) + R.wall_nodes(chunks)
    n += R.beyond_nodes('cinema', 1.4) + R.beyond_nodes('booth', 0.3, steps=7, rise=0.2, run=0.26) + R.beyond_nodes('shop', 1.4)
    n += cage_nodes() + office_nodes()
    n.append(box('column', (COL[0], -0.02, COL[1]), (COL[2], CUT_H, COL[3]), 'column', open=['bottom'], faces={'top': 'cut'}))
    # three pallets of wrapped stock
    pw = (PAL[2] - PAL[0]) / 3
    for k in range(3):
        x0, x1 = PAL[0] + k * pw + 0.04, PAL[0] + (k + 1) * pw - 0.04
        n.append(box(f'pallet_{k}', (x0, -0.02, PAL[1]), (x1, 0.14, R.Z1), 'pallet', open=['bottom', 'front'],
                     faces={'top': 'pallet'}))
        top = [0.86, 0.7, 0.9][k]
        n.append(box(f'wrap_{k}', (x0 + 0.04, 0.13, PAL[1] + 0.05), (x1 - 0.04, top, R.Z1 - 0.03), 'wrap_side',
                     open=['bottom'], faces={'top': 'wrap'}))
    # on the back wall: the hose reel's cabinet, the exit sign over the stair door
    hx0, hx1, hy0, hy1 = HOSE
    n.append(box('hose', (hx0, hy0, R.Z1 - 0.16), (hx1, hy1, R.Z1 + 0.02), 'hose_box', open=['front'], faces={'back': 'hose'}))
    n.append(box('exit', (11.65, 2.0, R.Z1 - 0.06), (12.15, 2.26, R.Z1 + 0.02), 'frame', open=['front'], faces={'back': 'exit'}))
    return recipe(P + 'room', m, n, kit_lighting(lights(), AMBIENT, {'tolerance': 22, 'max_added': 260}), 2000)


def glass_recipe():
    m = {'glass': {'color': '#a4d0e4', 'blend': 'half'}, 'glass_edge': {'color': '#cce6f0'}}
    n = [box('window', (OX0 + OT, SILL - 0.01, OZ1 - 0.1), (WE, CUT_H, OZ1 - 0.06), 'glass', open=['bottom', 'left', 'right'],
             faces={'top': 'glass_edge'})]
    return recipe(P + 'glass', m, n, {'bake': False}, 20)


def main():
    L = lights()
    blk = blockers()
    art = {}
    for name, x0, x1, z0, z1 in R.floor_tiles(2, 1):
        art[P + name] = paint_floor(R, x0, x1, z0, z1, floor_base, L, AMBIENT, blk, floor_extra)
    for name, a, b in R.back_chunks(10.0):
        img = paint_wall(a, b, 0.0, WALL_H, R.Z1, wall_base, L, AMBIENT, wall_extra)
        art[P + name] = stencil_8f(img, 5.6, 7.2, a, b)
    art.update({P + 'section': paint_section(R.XO0, R.XO1), P + 'cage_mesh': paint_cage_mesh(), P + 'keys': paint_keys(),
                P + 'monitors': paint_monitors(), P + 'column': paint_column(), P + 'pallet': paint_pallet_side(),
                P + 'wrap': paint_wrap(), P + 'hose': paint_hose(), P + 'exit': paint_exit_sign()})
    for k in range(4):
        art[f'{P}carton_{k}'] = paint_carton(seed=k)
    for name, img in art.items():
        save_png(img, ART / f'{name}.png')
    for rec in (room_recipe(), glass_recipe(), R.collision(P + 'room_col')):
        write_json(OUT / f'{rec["name"]}.asset.json', rec)
    placements = [{'id': P + 'room', 'asset': P + 'room', 'position': [0, 0, 0], 'collision': P + 'room_col'},
                  {'id': P + 'glass', 'asset': P + 'glass', 'position': [0, 0, 0], 'collision': 'none'}]
    data = {'format': 'after-hours-placements', 'version': 1, 'room': 'corridor', 'placements': placements}
    write_json(HERE / 'corridor.placements.json' if '--placements' in sys.argv else OUT / 'draft.placements.json', data)


if __name__ == '__main__':
    main()
