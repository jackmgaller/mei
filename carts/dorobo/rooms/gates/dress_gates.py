#!/usr/bin/env python3
"""Room 2, the ticket gates, dressed: writes the room's Asset Kit recipes into dressed/, their textures
into dressed/art/, and (with --placements) gates.placements.json beside this script; without it, a
draft in dressed/draft.placements.json, which ../arrival/capture.py prefers while it exists.

    python3 carts/dorobo/rooms/gates/dress_gates.py --placements

The concourse at the top of the platform's stair, two floors down, after the last train: the
station office's window warm in the dark, a lamp on its desk and the clock over it; the line of
automatic gates with their green lamps and blue card pads; three ticket machines glowing against
the front wall; the bank of coin lockers with its gap (the hiding place: a missing module, its dust
outline still on the floor); the stairwell down to the platform, cool light coming up it; the way up
to the passage, open in the east wall. Tactile lines on the floor lead from the stair through the
gates to the way up.

The floor plan is the level lead's (PLAN.md, make_gates.py), imported for its numbers. Light as in
room 1 (../arrival/dresskit.py): room_lights() bakes the lit props through the kit and paints the
emissive floor, back wall and locker fronts. The glass (the office window, the barrier's panels) is
its own recipe, out of the lights' reach. Everything named is fictional. Needs NumPy and Pillow.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'arrival'))
import make_gates as G  # noqa: E402  (the lead's plan: imported for its numbers only)
from dresskit import (CUT, Mesh, at, blob, box, font, grid, kit_lights, r, recipe, rect, save_png,  # noqa: E402
                      shade_plane, smoothstep, to_image, write_json)

OUT = HERE / 'dressed'
ART = OUT / 'art'
P = 'r2_'

X0, X1 = G.X0, G.X1
XO0, XO1 = X0 - G.WALL_T, X1 + G.WALL_T
Z0, Z1 = G.Z0, G.Z1
ZO0, ZO1 = Z0 - G.WALL_T, Z1 + G.WALL_T
H = G.WALL_H
SLAB = 0.4
WX0, WZ0, WX1, WZ1 = G.STAIRWELL            # the stairwell: x -6.5 .. -4.3, z -4.25 .. -1.6
WELL_D = 2.2                                 # how deep its walls go
WELL_STEPS, WELL_RUN = 8, (WX1 - WX0) / 8
OX0, OZ0, OX1, OZ1 = G.OFFICE
OT = 0.15
DX0, DX1 = G.OFFICE_DOOR
LX0, LZ0, LX1, LZ1 = G.LOCKERS
AX0, AX1 = G.ALCOVE
LOCK_H = H - 0.4
MX0, MZ0, MX1, MZ1 = G.MACHINES
EZ0, EZ1 = G.EXIT_DOOR
GX0, GX1 = G.GATE_X
AISLES = [(a + b) / 2 for a, b in zip(G.GATE_Z, G.GATE_Z[1:])]
FAREMAP = (2.5, 5.5, 1.05, 2.0)
SIGN = (-1.0, -0.45, 1.6, 2.1)              # the office's pictogram over its desk (x0, x1, y0, y1)
CLOCK = (0.55, 1.85, 0.36)                  # x, y, size


# ---- the light

def room_lights():
    return [
        {'id': 'office_lamp', 'at': [-0.15, 1.05, 3.85], 'color': '#ffbe74', 'intensity': 1.8, 'range': 2.4},
        {'id': 'office_ceiling', 'at': [0.0, 2.7, 3.2], 'color': '#ffe2b8', 'intensity': 1.7, 'range': 5.0,
         'shadows': True, 'samples': 1},
        {'id': 'hall_w', 'at': [-3.4, 2.7, 0.3], 'color': '#e8f0f0', 'intensity': 1.6, 'range': 4.6, 'line': 1.2,
         'shadows': True},
        {'id': 'hall_e', 'at': [3.3, 2.7, 0.3], 'color': '#e8f0f0', 'intensity': 1.4, 'range': 4.4, 'line': 1.2,
         'shadows': True},
        {'id': 'hall_front', 'at': [2.8, 2.7, -2.7], 'color': '#e8f0f0', 'intensity': 1.3, 'range': 4.0, 'line': 1.2,
         'shadows': True},
        {'id': 'lockers', 'at': [-4.5, 2.5, 2.3], 'color': '#cfe6f0', 'intensity': 1.5, 'range': 3.4, 'line': 1.2,
         'shadows': True},
        {'id': 'machines', 'at': [-2.3, 0.95, -3.55], 'color': '#a8d4ff', 'intensity': 1.6, 'range': 2.6},
        {'id': 'well', 'at': [-6.1, -1.7, -2.9], 'color': '#d2eaf0', 'intensity': 2.0, 'range': 2.8},
        {'id': 'way_up', 'at': [7.1, 1.6, -2.6], 'color': '#e6f0ff', 'intensity': 2.4, 'range': 4.0, 'shadows': True},
        {'id': 'faremap', 'at': [4.0, 1.5, Z1 - 0.3], 'color': '#c8e0ff', 'intensity': 0.9, 'range': 2.8, 'paint': True},
    ] + [{'id': f'gate_{k}', 'at': [sx, 1.0, z], 'color': '#58ff9a', 'intensity': 0.5, 'range': 0.9, 'paint': True}
         for k, z in enumerate(AISLES) for sx in (GX0 - 0.05, GX1 + 0.05)]


AMBIENT = 0.12
REFINE = {'tolerance': 22, 'max_added': 220}


def lighting(refine=REFINE):
    lights = []
    for L in kit_lights([L for L in room_lights() if not L.get('paint')]):
        L.pop('shadows', None)
        L.pop('radius', None)
        lights.append(L)
    return {'direction': [-0.25, 0.7, -0.65], 'ambient': AMBIENT, 'diffuse': 0.2, 'lights': lights, 'refine': refine}


def blockers():
    """Boxes (x0, y0, z0, x1, y1, z1) shadowing the painted floor, as things really stand (the
    office's walls to the ceiling, with its window and door open)."""
    t = OT
    out = [(OX0, 0, OZ0, OX0 + t, 2.8, OZ1), (OX1 - t, 0, OZ0, OX1, 2.8, OZ1),
           (OX0, 0, OZ0, DX0, 0.8, OZ0 + t), (OX0, 2.0, OZ0, OX1, 2.8, OZ0 + t), (DX1, 0, OZ0, OX1, 2.8, OZ0 + t),
           (LX0, 0, LZ0, AX0, LOCK_H, LZ1), (AX1, 0, LZ0, LX1, LOCK_H, LZ1),
           (MX0, 0, MZ0, MX1, 0.95, MZ1),
           (OX0 + 0.15, 0, 3.6, 0.4, 0.75, 4.2)]
    for z in G.GATE_Z:
        out.append((GX0, 0, z - 0.125, GX1, 0.98, z + 0.125))
    out.append((-0.06, 0, G.GATE_Z[-1] + 0.125, 0.06, 0.98, OZ0))
    out.append((WX0, 0, WZ1, WX1, 0.95, WZ1 + 0.12))
    out.append((WX1, 0, WZ0, WX1 + 0.12, 0.95, WZ1))
    out.append((X1, 0, Z0, XO1, 2.8, EZ0))
    out.append((X1, 0, EZ1, XO1, 2.8, Z1))
    out.append((X1, 2.1, EZ0, XO1, 2.8, EZ1))
    return out


# ---- painting

def tactile(x, z):
    """The yellow guide line: from the stair's head east, through the wide aisle, to the way up; a
    branch to the office's window."""
    segs = [((-4.05, -2.9), (-0.9, -2.9)), ((-0.9, -2.9), (-0.9, -2.05)), ((-0.9, -2.05), (5.5, -2.05)),
            ((5.5, -2.05), (5.5, -2.6)), ((5.5, -2.6), (6.5, -2.6)), ((-0.9, -2.05), (-0.9, 1.75))]
    m = np.zeros_like(x, dtype=bool)
    for (ax, az), (bx, bz) in segs:
        m |= (x >= min(ax, bx) - 0.15) & (x <= max(ax, bx) + 0.15) & (z >= min(az, bz) - 0.15) & (z <= max(az, bz) + 0.15)
    return m


def paint_floor(z0, z1, w=255, h=84, x1=X1):
    """The concourse floor, z0 .. z1: large cream tiles, the tactile line, the office's linoleum, the
    alcove's dust outline, lit by the room's lights through the office's window and door."""
    x, z = grid(X0, x1, z0, z1, w, h)
    rng = np.random.default_rng(int(z0 * 10) + 50)
    base = np.zeros((h, w, 3)) + np.array([182, 180, 172])
    tid = (np.floor((x + 6.5) / 0.45) * 13 + np.floor((z + 4.25) / 0.45) * 7) % 5
    base *= (0.96 + 0.02 * tid)[..., None]
    grout = (np.abs(((x + 6.5) / 0.45) % 1 - 0.5) > 0.42) | (np.abs(((z + 4.25) / 0.45) % 1 - 0.5) > 0.42)
    base *= np.where(grout, 0.84, 1.0)[..., None]
    base += (rng.random((h, w)) - 0.5)[..., None] * 9
    # where people walk, the tiles are greyer: the line through the gates
    base *= (1 - 0.08 * np.exp(-((z + 2.05) / 0.9) ** 2) * smoothstep(-4.5, -3.0, x))[..., None]
    # the tactile line and its studs
    tac = tactile(x, z)
    studs = ((np.floor((x + 6.5) / 0.075) + np.floor((z + 4.25) / 0.075)) % 2 == 0)
    base = np.where(tac[..., None], np.where(studs[..., None], np.array([232, 192, 54]), np.array([204, 164, 40])), base)
    # under the gate line: a dark rubber strip, and the aisles' mats
    base = np.where((rect(x, z, GX0 - 0.35, Z0, GX1 + 0.35, G.GATE_Z[-1]) > 0)[..., None] & ~tac[..., None],
                    base * 0.8, base)
    # the office: green-grey linoleum, a worn patch at the desk
    office = rect(x, z, OX0 + OT, OZ0 + OT, OX1 - OT, OZ1) > 0
    lino = np.array([116, 132, 120]) + (rng.random((h, w)) - 0.5)[..., None] * 6
    base = np.where(office[..., None], lino * (1 - 0.15 * blob(x, z, -0.5, 3.4, 0.5))[..., None], base)
    # the alcove: the floor a missing module stood on, cleaner, with its dust outline
    alc = rect(x, z, AX0 + 0.06, LZ0 + 0.04, AX1 - 0.06, LZ1)
    base = np.where((alc > 0)[..., None], base * 1.04, base)
    edge = alc * (1 - rect(x, z, AX0 + 0.1, LZ0 + 0.08, AX1 - 0.1, LZ1))
    base = np.where((edge > 0)[..., None], base * 0.6, base)
    # the stair's head: a yellow line along its top step (the floor ends at the well)
    base = np.where((rect(x, z, WX1, WZ0, WX1 + 0.08, WZ1) > 0)[..., None], np.array([230, 196, 60]), base)
    P = np.stack([x.ravel(), np.zeros(x.size), z.ravel()], axis=1)
    lit = shade_plane(P, (0, 1, 0), room_lights(), AMBIENT, blockers()).reshape(h, w, 3)
    rgb = base * lit
    # the gates' green lamps and blue card pads glow on the floor at each aisle's ends
    for z_a in AISLES:
        for sx in (GX0 - 0.25, GX1 + 0.25):
            rgb += (blob(x, z, sx, z_a, 0.22, 0.4) * 0.6)[..., None] * np.array([40, 150, 80])
    # the machines' glow in front of them
    rgb += (rect(x, z, MX0, MZ1, MX1, MZ1 + 0.6, soft=0.35) * 0.35)[..., None] * np.array([70, 120, 190])
    # light up the well's mouth from below, and off the polished floor the office window's sheen
    rgb += (rect(x, z, WX0, WZ1, WX1, WZ1 + 0.25, soft=0.2) * 0.2)[..., None] * np.array([120, 150, 160])
    rgb += (rect(x, z, OX0 + 0.2, OZ0 - 1.1, DX0 - 0.1, OZ0 - 0.15, soft=0.3) * 0.12)[..., None] * np.array([255, 180, 100])
    return to_image(rgb)


def paint_back_wall(w=255, h=46):
    """The back wall: cream tiles and the line's teal band; inside the office warm paint and the
    duty roster; two paper notices; the fare map's glow; dark above the lockers."""
    x, y = grid(XO0, XO1, 0, H, w, h)
    base = np.zeros((h, w, 3)) + np.array([188, 184, 172])
    joint = (np.abs(((x + 6.75) / 0.3) % 1 - 0.5) > 0.45) | (np.abs((y / 0.3) % 1 - 0.5) > 0.45)
    base *= np.where(joint, 0.88, 1.0)[..., None]
    base = np.where(((y > 2.0) & (y < 2.12))[..., None], np.array([40, 156, 156]), base)
    base = np.where((y < 0.12)[..., None], np.array([70, 74, 80]), base)
    office = (x > OX0 + OT) & (x < OX1 - OT)
    base = np.where(office[..., None], np.array([196, 178, 146]), base)
    # the duty roster on the office wall, a calendar, and the notices on the concourse
    for (a, b, c, d, col) in ((-1.35, -1.05, 1.05, 1.45, (232, 230, 220)), (1.0, 1.3, 1.0, 1.35, (236, 232, 222)),
                              (1.9, 2.25, 1.15, 1.6, (236, 236, 228)), (5.85, 6.2, 1.15, 1.6, (240, 214, 200))):
        base = np.where((rect(x, y, a, c, b, d) > 0)[..., None], np.array(col), base)
    lines = (np.abs((y * 18) % 1 - 0.5) > 0.3)
    for (a, b, c, d) in ((-1.33, -1.07, 1.08, 1.4), (1.92, 2.23, 1.18, 1.45), (5.87, 6.18, 1.18, 1.45)):
        base = np.where(((rect(x, y, a, c, b, d) > 0) & lines)[..., None], np.array([120, 120, 128]), base)
    base = np.where((rect(x, y, 5.9, 1.47, 6.15, 1.57) > 0)[..., None], np.array([200, 60, 60]), base)
    base = np.where((rect(x, y, 1.95, 1.47, 2.2, 1.57) > 0)[..., None], np.array([60, 120, 190]), base)
    P = np.stack([x.ravel(), y.ravel(), np.full(x.size, Z1)], axis=1)
    lit = shade_plane(P, (0, 0, -1), [dict(L, shadows=False) for L in room_lights()], AMBIENT).reshape(h, w, 3)
    rgb = base * lit
    fx0, fx1, fy0, fy1 = FAREMAP
    rgb += (rect(x, y, fx0, fy0, fx1, fy1, soft=0.25) * 0.3)[..., None] * np.array([140, 180, 255])
    rgb *= (1 - 0.6 * ((x > LX0) & (x < LX1) & (y > LOCK_H)))[..., None]
    return to_image(rgb)


def paint_lockers(x0, x1, w=40, h=56):
    """A bank of coin lockers' doors as the light above them lights them: three rows of small doors
    and one of large, keys in most, a few taken (their doors' red tabs)."""
    x, y = grid(x0, x1, 0, LOCK_H, w, h)
    base = np.zeros((h, w, 3)) + np.array([150, 164, 178])
    col = 0.375
    rows = [0, 0.15, 0.95, 1.35, 1.75, LOCK_H]
    seam = np.abs(((x - x0) / col) % 1 - 0.5) > 0.44
    for ry in rows:
        seam |= np.abs(y - ry) < 0.025
    base = np.where(seam[..., None], np.array([92, 102, 116]), base)
    base = np.where((y < 0.15)[..., None], np.array([70, 74, 82]), base)
    rng = np.random.default_rng(int(x0 * 10) + 99)
    for i in range(int(round((x1 - x0) / col))):
        for (ra, rb) in zip(rows[1:-1], rows[2:]):
            kx, ky = x0 + (i + 0.82) * col, rb - 0.12
            taken = rng.random() < 0.18
            base = np.where((blob(x, y, kx, ky, 0.03, 0.035) > 0.4)[..., None],
                            np.array([220, 70, 60]) if taken else np.array([230, 224, 180]), base)
            base = np.where((rect(x, y, x0 + i * col + 0.06, rb - 0.1, x0 + i * col + 0.16, rb - 0.06) > 0)[..., None],
                            np.array([236, 236, 230]), base)
    P = np.stack([x.ravel(), y.ravel(), np.full(x.size, LZ0)], axis=1)
    lit = shade_plane(P, (0, 0, -1), [dict(L, shadows=False) for L in room_lights()], AMBIENT).reshape(h, w, 3)
    return to_image(base * lit, dither=3)


def paint_section(w=128, h=40):
    """The front wall where the section cuts it: hatched over the floor's level, the slab darker, the
    stairwell's wall going down at the west."""
    x, y = grid(XO0, XO1, -WELL_D, G.CUT, w, h)
    i, j = np.meshgrid(np.arange(w), np.arange(h))
    rgb = np.zeros((h, w, 3)) + np.array([74, 84, 104])
    rgb = np.where((y < 0)[..., None], np.array([50, 57, 72]), rgb)
    rgb = np.where((((i + j) % 6 == 0) & (y >= 0))[..., None], np.array([92, 102, 122]), rgb)
    rgb = np.where((((i - j) % 8 == 0) & (y < 0))[..., None], np.array([62, 70, 86]), rgb)
    rgb = np.where((np.abs(y) < 0.04)[..., None], np.array([150, 160, 178]), rgb)
    rgb = np.where((y > G.CUT - 0.06)[..., None], np.array([118, 132, 158]), rgb)
    return to_image(rgb, dither=0)


def paint_faremap(w=72, h=24):
    """The fare map: the network as coloured lines and station dots on white, this station ringed."""
    img = Image.new('RGB', (w, h), (236, 240, 244))
    d = ImageDraw.Draw(img)
    lines = [((40, 156, 156), [(2, 12), (20, 12), (30, 7), (50, 7), (70, 7)]),
             ((214, 80, 60), [(10, 2), (20, 12), (26, 21), (60, 21)]),
             ((60, 110, 200), [(4, 20), (30, 7), (36, 2)]),
             ((150, 110, 190), [(44, 2), (50, 7), (58, 16), (70, 16)])]
    for col, pts in lines:
        d.line(pts, fill=col, width=2)
        for p in pts[1:-1]:
            d.rectangle([p[0] - 1, p[1] - 1, p[0] + 1, p[1] + 1], fill=(255, 255, 255), outline=(30, 30, 40))
    d.ellipse([16, 8, 24, 16], outline=(220, 40, 40))
    d.rectangle([0, 0, w - 1, h - 1], outline=(150, 156, 164))
    return img


def paint_sign(w=24, h=20):
    """Over the office's window: the station office's pictogram (a person behind a counter) on blue."""
    img = Image.new('RGB', (w, h), (40, 90, 170))
    d = ImageDraw.Draw(img)
    d.ellipse([9, 2, 15, 8], fill=(246, 248, 250))
    d.rectangle([7, 9, 17, 13], fill=(246, 248, 250))
    d.rectangle([3, 13, 21, 15], fill=(246, 248, 250))
    return img


def paint_clock(n=16):
    """The office's round clock at twelve past midnight."""
    img = Image.new('RGB', (n, n), (196, 178, 146))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, n - 1, n - 1], fill=(40, 44, 50))
    d.ellipse([1, 1, n - 2, n - 2], fill=(246, 246, 240))
    c = (n - 1) / 2
    d.line([(c, c), (c + 0.4, c - 5)], fill=(20, 20, 24))
    d.line([(c, c), (c + 4.5, c + 1.5)], fill=(20, 20, 24))
    return img


def paint_gate_top(w=24, h=8):
    """A gate cabinet from above: grey, a blue card pad and a green arrow lamp at each end, the
    ticket slot along the middle."""
    img = Image.new('RGB', (w, h), (190, 196, 204))
    d = ImageDraw.Draw(img)
    d.rectangle([8, 3, 15, 4], fill=(40, 44, 52))
    for x0, s in ((1, 1), (w - 6, -1)):
        d.rectangle([x0, 1, x0 + 4, 6], fill=(60, 130, 230))
    d.polygon([(6, 2), (7, 4), (6, 6)], fill=(60, 240, 130))
    d.polygon([(w - 7, 2), (w - 8, 4), (w - 7, 6)], fill=(60, 240, 130))
    return img


def paint_machine(w=24, h=16):
    """A ticket machine's sloping console: the touch screen's fare buttons, the coin and note slots."""
    img = Image.new('RGB', (w, h), (40, 50, 70))
    d = ImageDraw.Draw(img)
    d.rectangle([2, 1, 15, 11], fill=(60, 110, 190))
    for i in range(3):
        for j in range(3):
            d.rectangle([3 + 4 * i, 2 + 3 * j, 5 + 4 * i, 3 + 3 * j], fill=(200, 230, 255))
    d.rectangle([18, 2, 21, 3], fill=(230, 200, 80))
    d.rectangle([18, 6, 21, 7], fill=(120, 230, 140))
    d.rectangle([2, 13, 21, 14], fill=(20, 22, 28))
    return img


def paint_desk(w=40, h=12):
    """The desk from above: the night's log open, a stack of forms, a tea cup, the phone."""
    img = Image.new('RGB', (w, h), (150, 144, 128))
    d = ImageDraw.Draw(img)
    d.rectangle([14, 3, 25, 9], fill=(236, 232, 218))
    d.line([(19, 3), (19, 9)], fill=(150, 140, 120))
    for k in range(4, 9, 2):
        d.line([(15, k), (18, k)], fill=(110, 110, 120))
        d.line([(20, k), (24, k)], fill=(110, 110, 120))
    d.rectangle([27, 2, 32, 6], fill=(226, 226, 214))
    d.ellipse([34, 7, 37, 10], fill=(220, 220, 210))
    d.point((35, 8), fill=(120, 90, 40))
    d.rectangle([28, 8, 32, 10], fill=(60, 64, 70))
    return img


def paint_crt(w=12, h=10):
    img = Image.new('RGB', (w, h), (30, 34, 40))
    d = ImageDraw.Draw(img)
    d.rectangle([1, 1, w - 2, h - 3], fill=(40, 120, 110))
    for k in range(2, h - 3, 2):
        d.line([(2, k), (w - 4, k)], fill=(130, 230, 190))
    return img


# ---- the recipes

def mat_tex(image, color, bits=8, emissive=True):
    m = {'color': color, 'texture': {'image': f'art/{image}.png', 'bits': bits, 'projection': 'fit'}}
    if emissive:
        m['class'] = 'emissive'
    return m


def floor_nodes():
    """The floor in two halves (each its own texture): the front, around the stairwell and out into the
    way up's threshold, and the back."""
    f = Mesh()
    f.poly([(WX1, 0, Z0), (X1, 0, Z0), (X1, 0, EZ0), (XO1, 0, EZ0), (XO1, 0, EZ1), (X1, 0, EZ1), (X1, 0, 0),
            (X0, 0, 0), (X0, 0, WZ1), (WX1, 0, WZ1)], (0, 1, 0), 'floor_front')
    b = Mesh()
    b.poly([(X0, 0, 0), (X1, 0, 0), (X1, 0, Z1), (X0, 0, Z1)], (0, 1, 0), 'floor_back')
    return [f.node('floor_front', 'floor_front'), b.node('floor_back', 'floor_back')]


def well_nodes():
    """The stairwell: its far wall, the steps going down west, the low walls round its mouth."""
    m = Mesh()
    m.quad_z(WZ1, WX0, WX1, -WELL_D, 0, -1, 'well_wall')
    for k in range(1, WELL_STEPS + 1):
        xa, xb = WX1 - k * WELL_RUN, WX1 - (k - 1) * WELL_RUN
        y = -0.2 * k
        m.quad_y(y, xa, xb - 0.06, Z0, WZ1, 1, 'well_tread' if k % 2 else 'well_tread2')
        m.quad_y(y, xb - 0.06, xb, Z0, WZ1, 1, 'well_nose')
        m.quad_x(xb, y, y + 0.2, Z0, WZ1, -1, 'well_riser')
    nodes = [m.node('well', 'well_wall')]
    nodes.append(box('rail_n', (WX0, 0.0, WZ1), (WX1 + 0.12, 0.95, WZ1 + 0.12), 'rail', open=['bottom', 'left'],
                     faces={'top': 'cap'}))
    nodes.append(box('rail_e', (WX1, 0.0, Z0), (WX1 + 0.12, 0.95, WZ1), 'rail', open=['bottom', 'back', 'front'],
                     faces={'top': 'cap'}))
    return nodes


def walls_nodes():
    n = []
    # the front wall, cut at 1 m; down the stairwell it goes down with the well
    m = Mesh()
    outline = [(XO0, -WELL_D), (WX1, -WELL_D), (WX1, -SLAB), (XO1, -SLAB), (XO1, G.CUT), (XO0, G.CUT)]
    m.prism(outline, ZO0, Z0, 'cut', back='section', front='wall_in', sides={0: None, 1: None, 2: None, 3: 'cut', 4: 'cut', 5: 'cut'})
    n.append(m.node('front_wall', 'cut'))
    n.append(box('back_wall', (XO0, -SLAB, Z1), (XO1, H, ZO1), 'cut', open=['bottom'], faces={'back': 'wall_back'}))
    n.append(box('end_w_low', (XO0, -WELL_D, Z0), (X0, 0, WZ1), 'well_wall', open=['bottom', 'back', 'top'],
                 faces={'left': 'cut'}))
    n.append(box('end_w', (XO0, 0, Z0), (X0, H, Z1), 'end', open=['bottom', 'back', 'front'], faces={'top': 'cut', 'left': 'cut'}))
    n.append(box('end_w_slab', (XO0, -SLAB, WZ1), (X0, 0, Z1), 'cut', open=['top', 'right', 'back', 'front']))
    n.append(box('end_e_front', (X1, -SLAB, Z0), (XO1, H, EZ0), 'end', open=['bottom', 'back'], faces={'top': 'cut', 'right': 'cut'}))
    n.append(box('end_e_back', (X1, -SLAB, EZ1), (XO1, H, Z1), 'end', open=['bottom', 'front'], faces={'top': 'cut', 'right': 'cut'}))
    n.append(box('exit_lintel', (X1, 2.1, EZ0), (XO1, H - 0.01, EZ1), 'end', open=['back', 'front'],
                 faces={'bottom': 'way_up', 'top': 'cut', 'right': 'cut'}))
    n.append(box('threshold_slab', (X1, -SLAB, EZ0), (XO1, -0.02, EZ1), 'cut', open=['top', 'left', 'back', 'front']))
    return n


def office_nodes():
    t = OT
    n = [box('office_w', (OX0, -0.02, OZ0), (OX0 + t, G.CUT, OZ1), 'office_out', open=['bottom', 'front'],
             faces={'top': 'cut', 'right': 'office_in'}),
         box('office_e', (OX1 - t, -0.02, OZ0), (OX1, G.CUT, OZ1), 'office_out', open=['bottom', 'front'],
             faces={'top': 'cut', 'left': 'office_in'}),
         box('office_sill', (OX0 + t, -0.02, OZ0), (DX0, 0.8, OZ0 + t), 'office_out', open=['bottom', 'left'],
             faces={'top': 'ledge', 'front': 'office_in'}),
         box('office_jamb', (DX1, -0.02, OZ0), (OX1 - t, G.CUT, OZ0 + t), 'office_out', open=['bottom', 'right'],
             faces={'top': 'cut'}),
         # the door, open against the east wall inside
         box('office_door', (OX1 - t - 0.06, -0.02, OZ0 + t + 0.03), (OX1 - t - 0.02, G.CUT, OZ0 + t + 0.72), 'door',
             open=['bottom'], faces={'top': 'cut'}),
         # the desk against the back wall, a CRT, the lamp, a chair, a cabinet
         box('desk', (OX0 + 0.25, -0.02, 3.62), (0.4, 0.75, OZ1 - 0.02), 'desk', open=['bottom', 'front'],
             faces={'top': 'desk_top'}),
         box('crt', (-1.0, 0.74, 3.78), (-0.55, 1.12, 4.18), 'crt_body', faces={'back': 'crt_screen'}, open=['bottom']),
         at({'id': 'lamp_shade', 'op': 'cone', 'radius': 0.11, 'height': 0.14, 'segments': 6, 'material': 'lamp',
             'caps': True}, translate=[-0.15, 1.0, 3.88]),
         box('lamp_arm', (-0.13, 0.74, 3.95), (-0.11, 0.95, 3.98), 'crt_body', open=['bottom']),
         box('chair_seat', (-1.0, 0.42, 3.05), (-0.55, 0.49, 3.5), 'chair'),
         box('chair_back', (-1.0, 0.47, 2.97), (-0.55, 0.9, 3.04), 'chair'),
         box('chair_post', (-0.8, -0.02, 3.25), (-0.75, 0.43, 3.3), 'crt_body', open=['bottom', 'top']),
         box('cabinet', (0.6, -0.02, 3.72), (1.25, 1.3, OZ1 - 0.02), 'cabinet', open=['bottom', 'front'],
             faces={'top': 'cabinet_top'}),
         ]
    # the sign and the clock on the back wall over the desk
    sx0, sx1, sy0, sy1 = SIGN
    n.append(box('sign', (sx0, sy0, Z1 - 0.06), (sx1, sy1, Z1 + 0.02), 'frame', open=['front'], faces={'back': 'sign'}))
    cx, cy, cs = CLOCK
    n.append(box('clock', (cx - cs / 2, cy - cs / 2, Z1 - 0.05), (cx + cs / 2, cy + cs / 2, Z1 + 0.02), 'frame',
                 open=['front'], faces={'back': 'clock'}))
    return n


def concourse_nodes():
    n = []
    # the lockers: two banks, the gap between them the hiding place
    for name, x0, x1, tex, op in (('lockers_w', LX0, AX0, 'lockers_w', ['bottom', 'front', 'left']),
                                  ('lockers_e', AX1, LX1, 'lockers_e', ['bottom', 'front'])):
        n.append(box(name, (x0, -0.02, LZ0), (x1, LOCK_H, Z1), 'locker_side', open=op,
                     faces={'back': tex, 'top': 'locker_top'}))
    # the gates: cabinets with their lamps and pads on top, the barrier up to the office
    for k, z in enumerate(G.GATE_Z):
        n.append(box(f'gate_{k}', (GX0, -0.02, z - 0.125), (GX1, 0.98, z + 0.125), 'gate', open=['bottom'],
                     faces={'top': 'gate_top'}))
    n.append(box('barrier', (-0.06, -0.02, G.GATE_Z[-1] + 0.125), (0.06, 0.72, OZ0), 'gate', open=['bottom', 'front', 'back'],
                 faces={'top': 'cap'}))
    # the ticket machines, each with its console sloping up to the wall
    for k in range(3):
        x0 = MX0 + k * (MX1 - MX0) / 3 + 0.02
        x1 = MX0 + (k + 1) * (MX1 - MX0) / 3 - 0.02
        n.append(box(f'machine_{k}', (x0, -0.02, Z0), (x1, 0.75, MZ1), 'machine', open=['bottom', 'back', 'top']))
        m = Mesh()
        m.poly([(x0, 0.75, MZ1), (x1, 0.75, MZ1), (x1, 0.95, Z0), (x0, 0.95, Z0)], (0, 1, 0.4), 'screen')
        m.poly([(x0, 0.75, MZ1), (x0, 0.95, Z0), (x0, 0.75, Z0)], (-1, 0, 0), 'machine')
        m.poly([(x1, 0.75, MZ1), (x1, 0.95, Z0), (x1, 0.75, Z0)], (1, 0, 0), 'machine')
        n.append(m.node(f'console_{k}', 'machine'))
    fx0, fx1, fy0, fy1 = FAREMAP
    # cardboard boxes left on top of the lockers
    n.append(box('carton_a', (-6.3, LOCK_H - 0.02, 3.6), (-5.75, LOCK_H + 0.3, 4.15), 'carton', open=['bottom']))
    n.append(box('carton_b', (-3.4, LOCK_H - 0.02, 3.7), (-3.0, LOCK_H + 0.2, 4.1), 'carton', open=['bottom']))
    n.append(box('faremap', (fx0, fy0, Z1 - 0.06), (fx1, fy1, Z1 + 0.02), 'frame', open=['front'], faces={'back': 'faremap'}))
    return n


def concourse_recipe():
    m = {
        'cut': {'color': CUT, 'class': 'emissive'},
        'section': mat_tex('r2_section', '#4a5468', bits=4),
        'floor_front': mat_tex('r2_floor_front', '#a8a294'),
        'floor_back': mat_tex('r2_floor_back', '#a8a294'),
        'wall_back': mat_tex('r2_wall', '#b4b0a4'),
        'lockers_w': mat_tex('r2_lockers_w', '#8a96a4'),
        'lockers_e': mat_tex('r2_lockers_e', '#8a96a4'),
        'faremap': mat_tex('r2_faremap', '#c8d0d8'),
        'sign': mat_tex('r2_sign', '#3a6ab0', bits=4),
        'clock': mat_tex('r2_clock', '#e0e0d8', bits=4),
        'gate_top': mat_tex('r2_gate_top', '#b0b8c0', bits=4),
        'screen': mat_tex('r2_machine', '#3c5c90', bits=4),
        'crt_screen': mat_tex('r2_crt', '#2c7468', bits=4),
        'wall_in': {'color': '#7a8292'},
        'end': {'color': '#a4acb8'},
        'way_up': {'color': '#d8e6f4', 'class': 'emissive'},
        'well_wall': {'color': '#68707e'},
        'well_tread': {'color': '#a4aab2'},
        'well_tread2': {'color': '#9ca2aa'},
        'well_riser': {'color': '#7c828c'},
        'well_nose': {'color': '#c8bc84'},
        'rail': {'color': '#9aa2ae'},
        'cap': {'color': '#d4dae2'},
        'office_out': {'color': '#a8a29a'},
        'office_in': {'color': '#c0aa88'},
        'ledge': {'color': '#8a8274'},
        'door': {'color': '#7c8a96'},
        'desk': {'color': '#8a8a84'},
        'desk_top': mat_tex('r2_desk', '#9a9488', bits=4, emissive=False),
        'crt_body': {'color': '#c4c0b4'},
        'lamp': {'color': '#ffd890', 'class': 'emissive'},
        'chair': {'color': '#4a5470'},
        'cabinet': {'color': '#8e9aa6'},
        'cabinet_top': {'color': '#a4aeb8'},
        'frame': {'color': '#5c626c'},
        'locker_side': {'color': '#7e8a98'},
        'locker_top': {'color': '#5a6470'},
        'gate': {'color': '#c8ccd4'},
        'machine': {'color': '#8a98aa'},
        'carton': {'color': '#b08a5c'},
    }
    nodes = floor_nodes() + well_nodes() + walls_nodes() + office_nodes() + concourse_nodes()
    return recipe(P + 'concourse', m, nodes, lighting(), 1400)


def glass_recipe():
    """The office's window and the barrier's panels: glass, unlit, so that refinement leaves it alone."""
    m = {'glass': {'color': '#9ccce0', 'blend': 'half'}, 'glass_edge': {'color': '#c8e4f0'}}
    n = [box('window', (OX0 + OT, 0.79, OZ0 + 0.05), (DX0, G.CUT, OZ0 + 0.09), 'glass', open=['bottom'],
             faces={'top': 'glass_edge'}),
         box('barrier_glass', (-0.02, 0.71, G.GATE_Z[-1] + 0.15), (0.02, 0.98, OZ0 - 0.02), 'glass', open=['bottom'],
             faces={'top': 'glass_edge'})]
    return recipe(P + 'glass', m, n, {'bake': False}, 60)


def concourse_col():
    col = G.shell_col()
    col['name'] = P + 'concourse_col'
    return col


def main():
    art = {'r2_floor_front': paint_floor(Z0, 0.0, x1=XO1), 'r2_floor_back': paint_floor(0.0, Z1),
           'r2_wall': paint_back_wall(), 'r2_lockers_w': paint_lockers(LX0, AX0), 'r2_lockers_e': paint_lockers(AX1, LX1),
           'r2_section': paint_section(), 'r2_faremap': paint_faremap(), 'r2_sign': paint_sign(), 'r2_clock': paint_clock(),
           'r2_gate_top': paint_gate_top(), 'r2_machine': paint_machine(), 'r2_crt': paint_crt(), 'r2_desk': paint_desk()}
    for name, img in art.items():
        save_png(img, ART / f'{name}.png')
    for rec in (concourse_recipe(), glass_recipe(), concourse_col()):
        write_json(OUT / f'{rec["name"]}.asset.json', rec)
    placements = [{'id': P + 'concourse', 'asset': P + 'concourse', 'position': [0, 0, 0], 'collision': P + 'concourse_col'},
                  {'id': P + 'glass', 'asset': P + 'glass', 'position': [0, 0, 0], 'collision': 'none'}]
    data = {'format': 'after-hours-placements', 'version': 1, 'room': 'gates', 'placements': placements}
    if '--placements' in sys.argv:
        write_json(HERE / 'gates.placements.json', data)
    else:
        write_json(OUT / 'draft.placements.json', data)


if __name__ == '__main__':
    main()
