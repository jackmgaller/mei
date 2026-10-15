#!/usr/bin/env python3
"""Room 1, the last train, dressed: writes the room's Asset Kit recipes into dressed/, their textures
into dressed/art/, and (with --placements) arrival.placements.json beside this script; without it, a
draft in dressed/draft.placements.json, which ../arrival/capture.py prefers while it exists.

    python3 carts/dorobo/rooms/arrival/dress_arrival.py --placements

The far end of a side platform three floors down, after midnight: fluorescent tubes along the
platform (painted into the floor as pools, with the props' soft shadows), the wall across the track
with its backlit ads, the station's name board and an amber departure board, the stair at the east
end with warm light falling down it from the concourse, an amber timetable on the front wall where
the guard turns to read it, two benches of moulded seats, a smoking corner at the west end.
Everything named is fictional (the station is Tsukinoura); text uses the OFL fonts in tools/fonts/.

The floor plan is the level lead's (PLAN.md, make_arrival.py): its numbers are imported from
make_arrival.py, so the dressing follows them. Light: room_lights() is one list; the kit bakes it
into the lit props (`lighting.lights`, refinement capped) and paint_*() paints it into the emissive
floor, track bed and back wall with the kit's formula (dresskit.py). Needs NumPy and Pillow.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import make_arrival as G  # noqa: E402  (the lead's plan: imported for its numbers only)
from dresskit import (CUT, Mesh, blob, box, at, font, grid, hex_rgb, kit_lights, noise, r, recipe, rect,  # noqa: E402
                      save_png, shade_plane, smoothstep, to_image, write_json)

OUT = HERE / 'dressed'
ART = OUT / 'art'
P = 'r1_'

X0, X1 = G.X0, G.X1
XO0, XO1 = X0 - G.WALL_T, X1 + G.WALL_T
ZF, ZB = G.Z_FRONT, G.Z_BACK
ZFO, ZBO = ZF - G.WALL_T, ZB + G.WALL_T
PZ0, PZ1 = G.PLAT
YB = G.Y_BED
TZ = G.TRACK_Z
H = G.WALL_H
SX0, SX1 = G.STAIR_X
SZ0, SZ1 = G.STAIR_Z
STEPS = G.STAIR_STEPS
RISE = 0.2
RUN = (SX1 - SX0) / STEPS
BAL_T = 0.12                         # the stair's balustrades, inside its footprint
SZ0I, SZ1I = SZ0 + BAL_T, SZ1 - BAL_T

# the trackside wall: (name, x0, x1, y0, y1)
BOXES = [('ad_sea', -5.8, -3.6, 0.5, 1.7), ('name', -2.9, -0.1, 1.15, 1.8), ('ad_coffee', 0.4, 2.6, 0.5, 1.7),
         ('depart', 3.2, 5.4, 1.1, 1.85), ('exit_sign', 5.75, 6.35, 1.55, 1.95)]
TIMETABLE = (5.4, 6.2)               # the lit timetable on the front wall, where the guard reads it (165 deg)
BINS = (-1.95, -0.85)                # recycling bins against the front wall
ASHTRAY = (-5.95, -3.95)             # the smoking corner's standing ashtray
SMOKING = (X0, ZF, -4.9, -3.0)      # its painted zone
LAMPS = (-4.5, -1.5, 1.5, 4.5)          # small lamps low on the trackside wall
DOORS = (-3.33, 0.0, 3.33)           # the train's doors when it stands (PLAN.md)
SEAT_W, SEATS, SEAT_GAP = 0.4, 4, 0.04


# ---- the light

TUBE = '#d6ecf0'


def room_lights():
    """Every light in the room, in its frame. `line` is painted as a tube; the kit takes its middle."""
    tubes = [{'id': f'tube_{k}', 'at': [x, 2.6, -1.6], 'color': TUBE, 'intensity': 1.9, 'range': 4.7,
              'line': 1.2, 'shadows': True} for k, x in enumerate((-4.6, -1.3, 2.0))]
    edge = [{'id': f'edge_{k}', 'at': [x, 2.6, 0.55], 'color': TUBE, 'intensity': 1.1, 'range': 4.2,
             'line': 1.2, 'shadows': True} for k, x in enumerate((-3.0, 0.4))]
    return tubes + edge + [
        {'id': 'stair_top', 'at': [6.2, 3.5, -0.2], 'color': '#ffcf8e', 'intensity': 2.4, 'range': 5.2, 'shadows': True,
         'radius': 0.3},
        {'id': 'stair_foot', 'at': [3.3, 1.7, -0.2], 'color': '#ffd6a6', 'intensity': 0.5, 'range': 2.6},
        {'id': 'timetable', 'at': [5.8, 0.7, ZF + 0.25], 'color': '#ffb048', 'intensity': 1.5, 'range': 2.3},
        # the trackside wall's boxes: painted only (they light the bed, the wall and the platform's edge)
        {'id': 'ad_sea', 'at': [-4.7, 1.1, ZB - 0.3], 'color': '#5cc4ff', 'intensity': 1.3, 'range': 3.4, 'paint': True},
        {'id': 'name', 'at': [-1.5, 1.45, ZB - 0.3], 'color': '#e4eeff', 'intensity': 0.9, 'range': 3.0, 'paint': True},
        {'id': 'ad_coffee', 'at': [1.5, 1.1, ZB - 0.3], 'color': '#ffa860', 'intensity': 1.3, 'range': 3.4, 'paint': True},
        {'id': 'depart', 'at': [4.3, 1.45, ZB - 0.3], 'color': '#ff9a30', 'intensity': 0.7, 'range': 2.6, 'paint': True},
        {'id': 'signal', 'at': [6.25, 0.35, ZB - 0.15], 'color': '#ff3020', 'intensity': 0.9, 'range': 1.2, 'paint': True},
    ]


AMBIENT = 0.13
REFINE = {'tolerance': 22, 'max_added': 180}


def lighting(offset=(0, 0, 0), keep=None, refine=REFINE):
    """The kit's lighting for a recipe placed at `offset` (its lights moved into its own frame)."""
    lights = []
    for L in kit_lights([L for L in room_lights() if not L.get('paint')], keep):
        L = dict(L, at=[r(a - o) for a, o in zip(L['at'], offset)])
        L.pop('shadows', None)          # shadows are painted on the floor; on the props they cost refinement
        L.pop('radius', None)
        lights.append(L)
    return {'direction': [-0.2, 0.9, -0.35], 'ambient': AMBIENT, 'diffuse': 0.08, 'lights': lights, 'refine': refine}


def blockers():
    """Boxes (x0, y0, z0, x1, y1, z1) that throw the lights' shadows on the painted floor: the pillar
    as it really stands (to the ceiling), the benches, the stair, the bins and the ashtray."""
    px, pz = G.PILLAR
    s = G.PILLAR_S / 2
    out = [(px - s, 0, pz - s, px + s, 2.7, pz + s)]
    for bx, bz in G.BENCHES:
        out.append((bx - 0.9, 0.36, bz - 0.22, bx + 0.9, 0.47, bz + 0.2))
        out.append((bx - 0.9, 0.45, bz - 0.24, bx + 0.9, 0.83, bz - 0.17))
    for k in range(STEPS):
        out.append((SX0 + k * RUN, 0, SZ0, SX1 + 0.25, (k + 1) * RISE, SZ1))
    out.append((SX0, 0, SZ0, SX1, 2.4, SZ0I))
    out.append((SX0, 0, SZ1I, SX1, 2.4, SZ1))
    out.append((BINS[0], 0, ZF, BINS[1], 0.85, ZF + 0.3))
    out.append((ASHTRAY[0] - 0.15, 0, ASHTRAY[1] - 0.15, ASHTRAY[0] + 0.15, 0.9, ASHTRAY[1] + 0.15))
    out.append((XO0, YB, PZ0, XO1, 0, PZ1))       # the platform itself (for the bed)
    return out


# ---- the painted surfaces

def paint_floor(w=255, h=105):
    """The platform as its lights light it: grey tiles, the edge's coping, the yellow tactile line, the
    door marks, the smoking corner; pools under the tubes, the stair's warm wedge, the amber of the
    timetable, the ads' colours along the edge."""
    x, z = grid(X0, X1, PZ0, PZ1, w, h)
    rng = np.random.default_rng(11)
    base = np.zeros((h, w, 3)) + np.array([132, 138, 148])
    # tiles 0.6 m, each a little different
    tid = (np.floor((x + 6.5) / 0.6) * 31 + np.floor((z + 4.25) / 0.6) * 17) % 7
    base *= (0.95 + 0.016 * tid)[..., None]
    grout = (np.abs(((x + 6.5) / 0.6) % 1 - 0.5) > 0.44) | (np.abs(((z + 4.25) / 0.6) % 1 - 0.5) > 0.44)
    base *= np.where(grout, 0.86, 1.0)[..., None]
    base += (rng.random((h, w)) - 0.5)[..., None] * 10
    # a worn lane where people walk, along the middle
    base *= (1 - 0.06 * np.exp(-((z + 1.6) / 0.9) ** 2))[..., None]
    # the edge: coping, the gap before it, the tactile line with its studs
    coping = z > 0.96
    base = np.where(coping[..., None], np.array([196, 196, 190]), base)
    base = np.where(((z > 0.92) & (z <= 0.96))[..., None], base * 0.55, base)
    tact = (z > 0.06) & (z < 0.36)
    studs = ((np.floor((x + 6.5) / 0.06) + np.floor(z / 0.06)) % 2 == 0)
    yellow = np.where(studs[..., None], np.array([226, 186, 52]), np.array([196, 156, 38]))
    base = np.where(tact[..., None], yellow, base)
    # door marks: queue lines either side of each door, and a teal triangle by the edge
    for d in DOORS:
        for sx in (-0.62, 0.62):
            line = (np.abs(x - (d + sx)) < 0.03) & (z > -1.35) & (z < 0.0)
            base = np.where(line[..., None], np.array([150, 210, 186]), base)
        tri = (z > 0.42) & (z < 0.78) & (np.abs(x - d) < (0.78 - z) * 0.55)
        base = np.where(tri[..., None], np.array([60, 168, 170]), base)
    # the smoking corner: a dashed outline and the ash on its floor
    sx0, sz0, sx1, sz1 = SMOKING
    inside = rect(x, z, sx0, sz0, sx1, sz1)
    base *= (1 - 0.12 * inside)[..., None]
    edge = inside * (1 - rect(x, z, sx0 + 0.05, sz0 + 0.05, sx1 - 0.06, sz1 - 0.06))
    dash = ((np.floor((x + z) / 0.15)) % 2 == 0)
    base = np.where(((edge > 0) & dash)[..., None], np.array([200, 186, 120]), base)
    stains = (rng.random((h, w)) < 0.05) & (inside > 0)
    base = np.where(stains[..., None], base * 0.7, base)

    # what the last passengers left: a newspaper by the west bench, a can by the bins, a ticket
    paper = rect(x, z, -2.35, -3.55, -1.95, -3.25) * (np.abs(((x * 2.3 + z) / 0.1) % 1 - 0.5) < 0.42)
    base = np.where((paper > 0)[..., None], np.array([206, 204, 196]), base)
    base = np.where((rect(x, z, -0.66, -3.98, -0.56, -3.9) > 0)[..., None], np.array([180, 40, 40]), base)
    base = np.where((rect(x, z, 1.2, -1.95, 1.3, -1.9) > 0)[..., None], np.array([214, 200, 150]), base)
    # a puddle from a drip in the ceiling, darker and glossier, by the second bench
    pud = blob(x, z, 1.75, -1.05, 0.45, 0.22) + 0.6 * blob(x, z, 2.15, -1.2, 0.2, 0.12)
    base *= (1 - 0.35 * (pud > 0.5))[..., None]
    P = np.stack([x.ravel(), np.zeros(x.size), z.ravel()], axis=1)
    shade = shade_plane(P, (0, 1, 0), room_lights(), AMBIENT, blockers()[:-1]).reshape(h, w, 3)
    open_ = shade_plane(P, (0, 1, 0), room_lights(), AMBIENT, ()).reshape(h, w, 3)
    shade = 0.65 * shade + 0.35 * open_          # light off the pale platform fills the shadows a little
    rgb = base * shade
    # the tubes' sheen on the polished tiles, a little toward the camera
    for L in room_lights():
        if L['id'].startswith(('tube', 'edge')):
            lx, _, lz = L['at']
            rgb += (np.exp(-((x - lx) / 0.75) ** 2 - ((z - (lz - 0.35)) / 0.22) ** 2) * 18)[..., None] * np.array([0.9, 1.0, 1.0])
    # the puddle mirrors the coffee ad and the tube over it
    rgb += ((pud > 0.5) * 0.35)[..., None] * (np.array([255, 160, 80]) * 0.5 + np.array([200, 230, 235]) * 0.4)
    # the ads mirrored in the polished tiles by the edge
    for name, bx0, bx1, by0, by1 in BOXES:
        g = rect(x, z, bx0 + 0.2, 0.15, bx1 - 0.2, 0.95, soft=0.25)
        rgb += (g * 0.18)[..., None] * np.array(BOX_GLOW[name])
    return to_image(rgb)


def paint_bed(w=255, h=46):
    """The track: a concrete slab with its middle drain, sleeper blocks and rails, in the shadow of
    the platform's edge, coloured by the ads, dark toward the tunnels."""
    x, z = grid(XO0, XO1, PZ1, ZB, w, h)
    rng = np.random.default_rng(5)
    base = np.zeros((h, w, 3)) + np.array([112, 112, 114]) + (rng.random((h, w)) - 0.5)[..., None] * 16
    base = np.where((np.abs(z - TZ) < 0.12)[..., None], np.array([34, 36, 40]), base)
    rails = [TZ - 0.535, TZ + 0.535]
    for rz in rails:
        block = (np.abs(z - rz) < 0.2) & ((np.abs(((x + 6.75) / 0.6) % 1 - 0.5) < 0.2))
        base = np.where(block[..., None], np.array([122, 120, 116]), base)
    for rz in rails:
        base = np.where((np.abs(z - rz - 0.06) < 0.035)[..., None], base * 0.45, base)
    P = np.stack([x.ravel(), np.full(x.size, YB), z.ravel()], axis=1)
    lights = [dict(L, shadows=True) for L in room_lights()]
    shade = shade_plane(P, (0, 1, 0), lights, AMBIENT, [blockers()[-1]]).reshape(h, w, 3)
    rgb = base * shade
    for lx in LAMPS:      # the trackside lamps' small pools
        rgb += (blob(x, z, lx, ZB - 0.25, 0.5, 0.35) * 0.5)[..., None] * np.array([120, 116, 96])
    for rz in rails:       # rail heads catch the light
        head = np.abs(z - rz) < 0.03
        rgb = np.where(head[..., None], np.array([120, 124, 132]) * (0.35 + 1.6 * shade), rgb)
    rgb *= (1 - 0.75 * smoothstep(5.4, 6.75, np.abs(x)))[..., None]
    return to_image(rgb)


BOX_GLOW = {'ad_sea': (70, 170, 255), 'name': (220, 232, 255), 'ad_coffee': (255, 160, 80),
            'depart': (255, 150, 40), 'exit_sign': (255, 210, 60)}


def paint_back_wall(w=255, h=66):
    """The wall across the track, seen from the platform: enamel panels and the line's teal band over
    the platform's level, bare concrete and cable trays below it, the ads' glow, a red signal."""
    x, y = grid(XO0, XO1, YB, H, w, h)
    base = np.zeros((h, w, 3)) + np.array([170, 174, 176])
    joint = np.abs(((x + 6.75) / 1.125) % 1 - 0.5) > 0.47
    base *= np.where(joint, 0.82, 1.0)[..., None]
    base = np.where(((y > 1.98) & (y < 2.12))[..., None], np.array([40, 156, 156]), base)
    base = np.where((y >= 2.12)[..., None], np.array([92, 96, 104]), base)
    low = y < 0.05
    rng = np.random.default_rng(3)
    concrete = np.array([88, 88, 90]) + (rng.random((h, w)) - 0.5)[..., None] * 12
    base = np.where(low[..., None], concrete, base)
    for ty in (-0.3, -0.55):
        base = np.where((np.abs(y - ty) < 0.035)[..., None], np.array([46, 48, 52]), base)
        base = np.where((np.abs(y - ty - 0.06) < 0.025)[..., None], np.array([128, 128, 124]), base)
    P = np.stack([x.ravel(), y.ravel(), np.full(x.size, ZB)], axis=1)
    lights = [dict(L, shadows=False) for L in room_lights()]
    shade = shade_plane(P, (0, 0, -1), lights, AMBIENT, ()).reshape(h, w, 3)
    rgb = base * shade
    for name, bx0, bx1, by0, by1 in BOXES:
        g = rect(x, y, bx0, by0, bx1, by1, soft=0.22) * 0.5
        rgb += g[..., None] * np.array(BOX_GLOW[name]) * 0.45
    # the trackside lamps, low on the wall, every few metres
    for lx in LAMPS:
        rgb += (blob(x, y, lx, -0.62, 0.05, 0.035))[..., None] * np.array([255, 240, 200])
        rgb += (blob(x, y, lx, -0.62, 0.45, 0.3) * 0.3)[..., None] * np.array([200, 190, 150])
    # the signal by the east tunnel: red, with its halo
    rgb += (blob(x, y, 6.25, 0.35, 0.06) * 1.0)[..., None] * np.array([255, 60, 40])
    rgb += (blob(x, y, 6.25, 0.35, 0.3) * 0.35)[..., None] * np.array([255, 40, 30])
    rgb *= (1 - 0.35 * smoothstep(1.9, 2.4, y))[..., None]
    return to_image(rgb)


def paint_section(w=128, h=42):
    """The front wall where the section cuts it, as a drawing would show it: the wall over the
    platform's level hatched, the platform's body under it darker, the floor's line between, and
    the amber of the timetable's lightbox where the cut passes through it."""
    x, y = grid(XO0, XO1, YB, G.CUT, w, h)
    i, j = np.meshgrid(np.arange(w), np.arange(h))
    rgb = np.zeros((h, w, 3)) + np.array([74, 84, 104])
    rgb = np.where((y < 0)[..., None], np.array([50, 57, 72]), rgb)
    hatch = ((i + j) % 6 == 0)
    rgb = np.where((hatch & (y >= 0))[..., None], np.array([92, 102, 122]), rgb)
    rgb = np.where((((i - j) % 8 == 0) & (y < 0))[..., None], np.array([62, 70, 86]), rgb)
    rgb = np.where((np.abs(y) < 0.03)[..., None], np.array([150, 160, 178]), rgb)
    rgb = np.where((y > G.CUT - 0.05)[..., None], np.array([118, 132, 158]), rgb)
    return to_image(rgb, dither=0)


def paint_ad_sea(w=64, h=36):
    """A night by the sea: a moon over a still bay, a white hotel on the far shore."""
    img = Image.new('RGB', (w, h))
    px = img.load()
    for j in range(h):
        for i in range(w):
            t = j / (h - 1)
            sky = (20 + 40 * t, 50 + 90 * t, 120 + 100 * t) if t < 0.55 else (30, 120 + 60 * (1 - t), 190)
            px[i, j] = tuple(int(c) for c in sky)
    d = ImageDraw.Draw(img)
    d.ellipse([44, 4, 54, 14], fill=(250, 246, 220))
    d.rectangle([8, 16, 26, 20], fill=(240, 244, 250))
    d.rectangle([12, 12, 20, 16], fill=(230, 236, 246))
    for k in range(6):
        d.line([(46 - k, 21 + 2 * k), (52 + k, 21 + 2 * k)], fill=(220, 236, 250))
    d.rectangle([0, 0, w - 1, h - 1], outline=(235, 240, 245))
    return img


def paint_ad_coffee(w=64, h=36):
    """A can of coffee on warm stripes, steam rising: a shape, not a brand."""
    img = Image.new('RGB', (w, h), (230, 120, 40))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 8):
        d.rectangle([k, 0, k + 3, h], fill=(244, 150, 60))
    d.rounded_rectangle([24, 8, 40, 33], radius=3, fill=(60, 34, 22))
    d.rectangle([24, 16, 40, 20], fill=(240, 230, 210))
    d.ellipse([27, 17, 37, 19], fill=(200, 60, 40))
    for k, sx in enumerate((28, 32, 36)):
        d.arc([sx - 3, 1, sx + 3, 8], 200, 340, fill=(255, 240, 220))
    d.rectangle([4, 26, 18, 30], fill=(255, 240, 220))
    d.rectangle([0, 0, w - 1, h - 1], outline=(250, 236, 220))
    return img


def paint_name(w=96, h=24):
    """The station's name board: Tsukinoura in kana, its romaji, the neighbours either side, and the
    line's teal band."""
    img = Image.new('RGB', (w, h), (234, 240, 244))
    d = ImageDraw.Draw(img)
    d.rectangle([0, h - 6, w, h], fill=(40, 156, 156))
    d.text((w / 2, 8), 'つきのうら', font=font('NotoSansJP-Bold.ttf', 11), fill=(24, 28, 34), anchor='mm')
    d.text((w / 2, 16), 'Tsukinoura', font=font('Figtree-Bold.ttf', 6), fill=(60, 66, 74), anchor='mm')
    d.polygon([(4, h - 3), (9, h - 5), (9, h - 1)], fill=(240, 250, 250))
    d.polygon([(w - 5, h - 3), (w - 10, h - 5), (w - 10, h - 1)], fill=(240, 250, 250))
    d.rectangle([0, 0, w - 1, h - 1], outline=(150, 156, 164))
    return img


def paint_depart(w=72, h=24):
    """The departure board after the last train: amber rows (shapes of times and names) on black, the
    last one blinking off, and the clock's 0:12 in green."""
    img = Image.new('RGB', (w, h), (14, 12, 12))
    d = ImageDraw.Draw(img)
    for row, (y, n) in enumerate(((3, [5, 12, 6, 9]), (10, [5, 10, 8]), (17, [5, 7]))):
        x = 3
        for k, seg in enumerate(n):
            for s in range(seg):
                if (s + row) % 5 != 4:
                    d.rectangle([x + s, y, x + s, y + 3 - (s % 2)], fill=(255, 164, 40) if row < 2 else (150, 80, 20))
            x += seg + 3
    d.text((w - 4, 12), '0:12', font=font('Figtree-Bold.ttf', 9), fill=(110, 255, 140), anchor='rm')
    d.rectangle([0, 0, w - 1, h - 1], outline=(70, 70, 76))
    return img


def paint_exit_sign(w=24, h=16):
    """The way up: a yellow sign with a stair climbing to the right and an arrow."""
    img = Image.new('RGB', (w, h), (246, 204, 48))
    d = ImageDraw.Draw(img)
    pts = [(3, 13)]
    for k in range(4):
        pts += [(3 + 3 * k, 13 - 2 * (k + 1)), (6 + 3 * k, 13 - 2 * (k + 1))]
    pts += [(15, 13)]
    d.polygon(pts, fill=(28, 26, 22))
    d.polygon([(17, 5), (21, 8), (17, 11)], fill=(28, 26, 22))
    return img


def paint_bin_top(w=32, h=8):
    """The bins' lids from above: a round mouth for cans (blue), one for bottles (green), a slot for
    papers."""
    img = Image.new('RGB', (w, h), (150, 156, 164))
    d = ImageDraw.Draw(img)
    for cx, rim in ((5, (60, 110, 200)), (15, (60, 160, 90))):
        d.ellipse([cx - 4, 0, cx + 4, 7], fill=rim)
        d.ellipse([cx - 2, 2, cx + 2, 5], fill=(20, 22, 26))
    d.rectangle([22, 2, 30, 5], fill=(110, 116, 124))
    d.rectangle([23, 3, 29, 4], fill=(20, 22, 26))
    return img


def paint_pillar(w=16, h=32):
    """The pillar's tiles: white, the teal band at shoulder height, a dark skirting (one face; `fit`
    puts it on each)."""
    img = Image.new('RGB', (w, h), (104, 112, 126))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 4):
        d.line([(k, 0), (k, h)], fill=(80, 86, 98))
    for k in range(0, h, 4):
        d.line([(0, k), (w, k)], fill=(80, 86, 98))
    d.rectangle([0, 4, w, 7], fill=(40, 156, 156))
    d.rectangle([0, h - 3, w, h], fill=(70, 74, 80))
    d.rectangle([6, 14, 9, 18], fill=(200, 40, 36))        # the emergency stop button's red box
    d.point((7, 16), fill=(255, 220, 120))
    return img


# ---- the recipes

def mat_tex(image, color, bits=8, emissive=True):
    m = {'color': color, 'texture': {'image': f'art/{image}.png', 'bits': bits, 'projection': 'fit'}}
    if emissive:
        m['class'] = 'emissive'
    return m


def stair_nodes():
    """The stair up to the gates: treads with yellow nosings, risers, the balustrades either side
    rising with it to the section's ceiling, their handrail caps."""
    m = Mesh()
    xs = [SX0 + k * RUN for k in range(STEPS + 1)]
    xs[-1] = XO1
    for k in range(STEPS):
        y0, y1 = k * RISE, (k + 1) * RISE
        m.quad_x(xs[k], y0 - (0.02 if k == 0 else 0), y1, SZ0I, SZ1I, -1, 'riser')
        m.quad_y(y1, xs[k], xs[k] + 0.06, SZ0I, SZ1I, 1, 'nose')
        m.quad_y(y1, xs[k] + 0.06, xs[k + 1], SZ0I, SZ1I, 1, 'tread')
    nodes = [m.node('stair', 'tread')]
    slope = (STEPS * RISE) / (SX1 - SX0)
    yc = 0.95
    xc = SX0 + (H - yc) / slope
    outline = [(SX0, -0.02), (XO1, -0.02), (XO1, H), (xc, H), (SX0, yc)]
    sides = {0: None, 1: 'cut', 2: 'cut', 3: 'cap', 4: 'balu_end'}
    for name, z0, z1, back, front in (('balustrade_s', SZ0, SZ0I, 'balu', 'balu_in'),
                                       ('balustrade_n', SZ1I, SZ1, 'balu_in', 'balu')):
        b = Mesh()
        b.prism(outline, z0, z1, 'balu', front=front, back=back, sides=sides)
        nodes.append(b.node(name, 'balu'))
    return nodes


def station_recipe():
    m = {
        'cut': {'color': CUT, 'class': 'emissive'},
        'floor': mat_tex('r1_floor', '#8a8c90'),
        'bed': mat_tex('r1_bed', '#3a3a3c'),
        'wall_back': mat_tex('r1_wall', '#9a9ea2'),
        'plat_edge': {'color': '#6a6e76'},
        'end': {'color': '#a4acb8'},
        'wall_in': {'color': '#7a8292'},
        'tunnel': {'color': '#06070a', 'class': 'emissive'},
        'riser': {'color': '#8a8e96'},
        'tread': {'color': '#aeb2ba'},
        'nose': {'color': '#c4bc94'},
        'balu': {'color': '#8e98a8'},
        'section': mat_tex('r1_section', '#4a5468', bits=4),
        'poche': {'color': '#323a4a', 'class': 'emissive'},
        'balu_in': {'color': '#a2a8b2'},
        'balu_end': {'color': '#9aa0aa'},
        'cap': {'color': '#d4dae2'},
        'frame': {'color': '#5c626c'},
        'ad_sea': mat_tex('r1_ad_sea', '#3c7cc0'),
        'ad_coffee': mat_tex('r1_ad_coffee', '#d07a34'),
        'name': mat_tex('r1_name', '#d8e0e6'),
        'depart': mat_tex('r1_depart', '#3a2a18'),
        'exit_sign': mat_tex('r1_exit_sign', '#e0c040', bits=4),
        'amber': {'color': '#ffb44c', 'class': 'emissive'},
        'bin': {'color': '#7c8694'},
        'bin_top': mat_tex('r1_bin_top', '#8a909a', bits=4, emissive=False),
        'ash': {'color': '#8e959e'},
        'ash_top': {'color': '#2c2e32'},
    }
    n = [
        box('slab', (XO0, -1.4, ZFO), (XO1, YB, ZBO), 'cut', open=['top', 'bottom'], faces={'back': 'poche'}),
        box('platform', (X0, YB, PZ0), (X1, 0, PZ1), 'plat_edge', open=['bottom', 'left', 'right', 'back'],
            faces={'top': 'floor'}),
        box('bed', (XO0, YB - 0.05, PZ1), (XO1, YB, ZB), 'bed', open=['bottom', 'left', 'right', 'back', 'front']),
        box('back_wall', (XO0, YB, ZB), (XO1, H, ZBO), 'cut', open=['bottom'], faces={'back': 'wall_back'}),
        box('front_wall', (XO0, YB, ZFO), (XO1, G.CUT, ZF), 'wall_in', open=['bottom'],
            faces={'top': 'cut', 'back': 'section', 'left': 'cut', 'right': 'cut'}),
        box('end_w', (XO0, YB, PZ0), (X0, H, PZ1), 'end', open=['bottom', 'back'], faces={'top': 'cut', 'left': 'cut'}),
        box('end_e_s', (X1, YB, PZ0), (XO1, H, SZ0), 'end', open=['bottom', 'back', 'front'],
            faces={'top': 'cut', 'right': 'cut'}),
        box('end_e_n', (X1, YB, SZ1), (XO1, H, PZ1), 'end', open=['bottom', 'back'], faces={'top': 'cut', 'right': 'cut'}),
        box('lintel_w', (XO0, 2.2, PZ1), (X0, H - 0.01, ZB), 'end', open=['back', 'front'],
            faces={'bottom': 'tunnel', 'top': 'cut', 'left': 'cut'}),
        box('lintel_e', (X1, 2.2, PZ1), (XO1, H - 0.01, ZB), 'end', open=['back', 'front'],
            faces={'bottom': 'tunnel', 'top': 'cut', 'right': 'cut'}),
    ]
    # the end walls' bases under the platform's level, beside the track, are the platform's ends
    n += stair_nodes()
    # the boxes on the trackside wall, 6 cm proud of it
    for name, bx0, bx1, by0, by1 in BOXES:
        n.append(box(f'box_{name}', (bx0, by0, ZB - 0.06), (bx1, by1, ZB + 0.02), 'frame', open=['front'],
                     faces={'back': name}))
    # the timetable on the front wall, cut by the section: its lit face shows as an amber line
    n.append(box('timetable', (TIMETABLE[0], 0.3, ZF - 0.0), (TIMETABLE[1], G.CUT, ZF + 0.08), 'frame', open=['back'],
                 faces={'top': 'amber', 'front': 'amber'}))
    n.append(box('bins', (BINS[0], -0.02, ZF), (BINS[1], 0.85, ZF + 0.3), 'bin', open=['bottom', 'back'],
                 faces={'top': 'bin_top'}))
    ax, az = ASHTRAY
    n.append(at({'id': 'ashtray', 'op': 'cylinder', 'radius': 0.15, 'height': 0.9, 'segments': 8, 'material': 'ash',
                 'faces': {'top': 'ash_top'}}, translate=[ax, 0.43, az]))
    return recipe(P + 'station', m, n, lighting(), 1100)


def station_col():
    """Floors and walls for the probe, from the lead's greybox collision (its shapes are the plan's)."""
    col = G.shell_col()
    col['name'] = P + 'station_col'
    return col


def pillar_recipe():
    px, pz = G.PILLAR
    s = G.PILLAR_S / 2
    m = {'cut': {'color': CUT, 'class': 'emissive'},
         'tiles': mat_tex('r1_pillar', '#c8ccd0', bits=4, emissive=False)}
    n = [box('pillar', (-s, -0.02, -s), (s, G.CUT, s), 'tiles', open=['bottom'], faces={'top': 'cut'})]
    near = {'tube_0', 'tube_1', 'edge_0'}
    return recipe(P + 'pillar', m, n, lighting((px, 0, pz), near, {'tolerance': 22, 'max_added': 24}), 80)


def bench_recipe(k):
    """A bench of four moulded seats on a steel beam, facing the track."""
    bx, bz = G.BENCHES[k]
    m = {'seat': {'color': '#4c6aa8'}, 'steel': {'color': '#7c828c'}, 'foot': {'color': '#5a606a'}}
    w = G.BENCH_W / 2
    n = [box('beam', (-w + 0.15, 0.3, -0.05), (w - 0.15, 0.38, 0.05), 'steel'),
         box('leg_w', (-w + 0.2, 0.0, -0.02), (-w + 0.28, 0.31, 0.02), 'steel', open=['bottom', 'top']),
         box('leg_e', (w - 0.28, 0.0, -0.02), (w - 0.2, 0.31, 0.02), 'steel', open=['bottom', 'top']),
         box('foot_w', (-w + 0.16, -0.02, -0.2), (-w + 0.32, 0.04, 0.2), 'foot', open=['bottom']),
         box('foot_e', (w - 0.32, -0.02, -0.2), (w - 0.16, 0.04, 0.2), 'foot', open=['bottom'])]
    for s in range(SEATS):
        cx = -w + 0.04 + SEAT_W / 2 + s * (SEAT_W + SEAT_GAP)
        n.append(box(f'pan_{s}', (cx - SEAT_W / 2, 0.37, -0.17), (cx + SEAT_W / 2, 0.44, 0.21), 'seat'))
        n.append(box(f'back_{s}', (cx - SEAT_W / 2 + 0.015, 0.40, -0.24), (cx + SEAT_W / 2 - 0.015, 0.82, -0.16), 'seat'))
    near = {f'tube_{i}' for i in range(3)} | {f'edge_{i}' for i in range(2)}
    return recipe(f'{P}bench_{k + 1}', m, n, lighting((bx, 0, bz), near, {'tolerance': 22, 'max_added': 40}), 200)


def bench_col():
    """The bench for the probe: one block of its footprint, as the greybox's seat (its seats' gaps
    would be cracks in a floor)."""
    w, d = G.BENCH_W / 2, G.BENCH_D / 2
    return recipe(P + 'bench_col', {'floor': {'color': '#8c9098'}},
                  [box('bench', (-w, -0.02, -d), (w, 0.45, d), 'floor', open=['bottom'])], None, 40, collision=True)


def main():
    art = {'r1_floor': paint_floor(), 'r1_bed': paint_bed(), 'r1_wall': paint_back_wall(),
           'r1_ad_sea': paint_ad_sea(), 'r1_ad_coffee': paint_ad_coffee(), 'r1_name': paint_name(),
           'r1_depart': paint_depart(), 'r1_exit_sign': paint_exit_sign(), 'r1_bin_top': paint_bin_top(),
           'r1_pillar': paint_pillar(), 'r1_section': paint_section()}
    for name, img in art.items():
        save_png(img, ART / f'{name}.png')
    recipes = [station_recipe(), station_col(), pillar_recipe(), bench_recipe(0), bench_recipe(1), bench_col()]
    for rec in recipes:
        write_json(OUT / f'{rec["name"]}.asset.json', rec)
    px, pz = G.PILLAR
    placements = [{'id': P + 'station', 'asset': P + 'station', 'position': [0, 0, 0], 'collision': P + 'station_col'},
                  {'id': P + 'pillar', 'asset': P + 'pillar', 'position': [px, 0, pz], 'collision': 'self'}]
    for k, (bx, bz) in enumerate(G.BENCHES):
        placements.append({'id': f'{P}bench_{k + 1}', 'asset': f'{P}bench_{k + 1}', 'position': [bx, 0, bz],
                           'collision': P + 'bench_col'})
    data = {'format': 'after-hours-placements', 'version': 1, 'room': 'arrival', 'placements': placements}
    if '--placements' in sys.argv:
        write_json(HERE / 'arrival.placements.json', data)
    else:
        write_json(OUT / 'draft.placements.json', data)


if __name__ == '__main__':
    main()
