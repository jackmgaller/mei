#!/usr/bin/env python3
"""The aquarium, room 7: the tank tops, dressed. Writes the room's Asset Kit recipes into dressed/,
their textures into dressed/art/ and aq_tops.placements.json beside this script.

    python3 carts/afterhours/rooms/aq_tops/dress_aq_tops.py

The floor over the big tanks, where the public never goes: wet concrete walkways with yellow edge
lines between two sheets of black water, under a dark roof (cut away by the section).

- the shark tank (west): black water, its ripples catching the lamps, three sharks cruising just
  under the surface with their dorsal fins out of it, a keeper's skiff tied up in the corner, the
  grated bridge across it with its rails and its lamp on a timer;
- the turtle pool (east): shallower, greener, a rock to haul out on with a turtle on it and
  another swimming;
- the life-support housings (louvred, cut by the section, their motors showing) with their pipes
  into the water; on the back wall glazed tile, pipes and valves, nets, poles and hoses;
- four work lamps: clamp lamps on posts at the tanks' edges and a bracket lamp on the back wall,
  their pools painted on the walkways exactly over the play file's light boxes (the bridge's, on a
  cycle, at half strength), their glints on the water;
- the kitchen's light beyond the east door, the stair down to the great tank's catwalk beyond the
  west one.

The floor plan is the level lead's (PLAN.md, make_aq_tops.py), imported for its numbers only. The
helpers are the great tank's (../aq_great/dress_aq_great.py). Needs NumPy and Pillow.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOMS = HERE.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOMS / 'aq_great'))
import make_aq_tops as G  # noqa: E402  (the lead's plan: imported for its numbers only)
import dress_aq_great as A  # noqa: E402  (the great tank's helpers)
from dress_aq_great import (Mesh, at, blob, box, caustics, emissive, grid, paint_rail, paint_section, pool, rect,  # noqa: E402
                            recipe, save_png, smoothstep, to_image, write_json)
import aqroom  # noqa: E402  (on the path through dress_aq_great)
sys.path.insert(0, str(ROOMS.parent / 'water'))   # agent W: the moving water (NOTES_W.md)
import wateranim  # noqa: E402
import s2room  # noqa: E402

OUT = HERE / 'dressed'
ART = OUT / 'art'
P = 'at_'
D = G.ROOM
X0, X1 = G.X
Z0, Z1 = G.Z
T = 0.25
XO0, XO1, ZO0, ZO1 = X0 - T, X1 + T, Z0 - T, Z1 + T
H = 2.4
SLAB = 0.4
CUT_H = 1.0
SHARK = G.SHARK
TURTLE = G.TURTLE
BRIDGE = (G.BRIDGE[0], SHARK[1], G.BRIDGE[1], SHARK[3])
WATERS = {'shark': SHARK, 'turtle': TURTLE}
SURFACE = -0.25                 # the water, a little under the walkways
DEEP = -1.3                     # where the tanks' walls end in the dark
PROPS = {p[0]: p for p in D['props']}
LIGHTS = {L[0]: L for L in D['lights']}
GAPS = {s: sorted(dr['at'] for dr in D['doors'] if dr['side'] == s) for s in 'we'}
XS = [X0, SHARK[0], BRIDGE[0], BRIDGE[2], SHARK[2], TURTLE[0], TURTLE[2], X1]
ZS = [Z0, SHARK[1], TURTLE[3], SHARK[3], Z1]
# the lamps: (x, y, z) of the lens, the light it gives (its box), and where its post stands
LAMPS = [
    {'light': 'middle', 'lens': (-1.25, 0.95, 0.0), 'post': (-1.5, 0.0)},
    {'light': 'bridge', 'lens': (-4.25, 0.95, 0.0), 'post': (-3.75, 0.0)},
    {'light': 'front', 'lens': (3.5, 0.95, -3.15), 'post': (3.5, -2.92)},
    {'light': 'back', 'lens': (-4.7, 2.0, Z1 - 0.12), 'post': None},
]
WARM = np.array([1.0, 0.9, 0.66])


def in_water(cx, cz):
    for b in WATERS.values():
        if b[0] < cx < b[2] and b[1] < cz < b[3]:
            return True
    return False


def walk_quads():
    """The walkways' tops: per row of the plan's grid, the runs of walkway (the bridge is its own),
    the long rows split in two so that each texture keeps its texels."""
    out = []
    for j in range(len(ZS) - 1):
        z0, z1 = ZS[j], ZS[j + 1]
        run = None
        for i in range(len(XS) - 1):
            x0, x1 = XS[i], XS[i + 1]
            cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
            walk = not in_water(cx, cz) and not (BRIDGE[0] < cx < BRIDGE[2] and BRIDGE[1] < cz < BRIDGE[3])
            if walk and run is not None and run[1] == x0:
                run[1] = x1
            elif walk:
                if run:
                    out.append((run[0], z0, run[1], z1))
                run = [x0, x1]
            else:
                if run:
                    out.append((run[0], z0, run[1], z1))
                run = None
        if run:
            out.append((run[0], z0, run[1], z1))
    pieces = []
    for (x0, z0, x1, z1) in out:
        if x1 - x0 > 12:
            pieces += [(x0, z0, 0.0, z1), (0.0, z0, x1, z1)]
        else:
            pieces.append((x0, z0, x1, z1))
    return pieces


# ---- painting

def paint_walk(x0, z0, x1, z1, tpm=20):
    w = max(8, min(255, int(round((x1 - x0) * tpm))))
    h = max(8, min(127, int(round((z1 - z0) * tpm))))
    x, z = grid(x0, x1, z0, z1, w, h)
    rng = np.random.default_rng(abs(int(x0 * 7 + z0 * 13)) + 5)
    base = np.zeros((h, w, 3)) + np.array([92, 98, 104]) + (rng.random((h, w)) - 0.5)[..., None] * 14
    # bays of the slab, a drain channel along the back walkway
    base *= np.where(np.abs(((x + 0.0) / 3.0) % 1 - 0.5) > 0.49, 0.78, 1.0)[..., None]
    drain = (np.abs(z - (SHARK[3] + 1.25)) < 0.05)
    base = np.where(drain[..., None], np.where(((x * 25) % 1 < 0.5)[..., None], np.array([30, 32, 36]), np.array([60, 64, 70])), base)
    # wet: dark patches and puddles
    wet = (np.sin(x * 1.3 + np.sin(z * 2.1) * 2) * np.sin(z * 1.7 + x * 0.4) > 0.55)
    base = np.where(wet[..., None], base * 0.84, base)
    # yellow edge lines a hand in from every water edge
    for b in WATERS.values():
        bx0, bz0, bx1, bz1 = b
        ring = (rect(x, z, bx0 - 0.16, bz0 - 0.16, bx1 + 0.16, bz1 + 0.16) > 0) & ~(rect(x, z, bx0 - 0.08, bz0 - 0.08, bx1 + 0.08, bz1 + 0.08) > 0)
        base = np.where(ring[..., None], np.array([196, 160, 40]), base)
    # a hose snaking along the back walkway, buckets and a coil of rope by the housings
    hz = Z1 - 0.35 + 0.08 * np.sin(x * 2.2)
    hose = (np.abs(z - hz) < 0.035) & (x > 1.6) & (x < 7.2)
    base = np.where(hose[..., None], np.array([40, 110, 60]), base)
    for bx, bz in ((7.95, 3.0), (8.35, 3.1), (-0.15, 4.2)):
        dd = np.hypot(x - bx, z - bz)
        base = np.where((dd < 0.15)[..., None], np.array([200, 200, 196]), base)
        base = np.where((dd < 0.11)[..., None], np.array([60, 90, 110]), base)
    # the kitchen's mat at the east door
    for (a, b) in GAPS['e']:
        base = np.where((rect(x, z, X1 - 0.8, a + 0.05, X1, b - 0.05) > 0)[..., None], base * 0.5 + np.array([20, 18, 10]), base)
    shade = np.zeros((h, w, 3)) + 0.3
    shade *= (1 - 0.3 * np.exp(-np.minimum.reduce([x - X0, X1 - x, z - Z0, Z1 - z]).clip(0) / 0.25))[..., None]
    for L in LAMPS:
        b = LIGHTS[L['light']][1]
        if L['light'] == 'bridge':
            continue
        lx, _, lz = L['lens']
        lit = pool(x, z, b, rad=0.3, fade=0.25, edge=0.5)
        hot = 0.8 + 0.5 * np.exp(-((x - lx) ** 2 + (z - lz) ** 2) / 1.2)
        shade += (lit * hot * 1.8)[..., None] * WARM
    rgb = base * shade
    # puddles catch the lamps' light only where it falls
    for L in LAMPS:
        if L['light'] == 'bridge':
            continue
        b = LIGHTS[L['light']][1]
        lit = pool(x, z, b, rad=0.3, fade=0.25, edge=0.3)
        rgb += (wet * lit * 0.35)[..., None] * np.array([255, 230, 170])
    return to_image(rgb, 4.0)


def paint_bridge(w=24, h=120):
    x, z = grid(BRIDGE[0], BRIDGE[2], BRIDGE[1], BRIDGE[3], w, h)
    rng = np.random.default_rng(9)
    base = np.zeros((h, w, 3)) + np.array([100, 106, 116]) + (rng.random((h, w)) - 0.5)[..., None] * 12
    shade = np.zeros((h, w, 3)) + 0.5
    # its lamp is on a cycle: the patch at half strength, so the runtime's wash reads lit or unlit
    lit = pool(x, z, LIGHTS['bridge'][1], rad=0.2, fade=0.2, edge=0.5)
    shade += (lit * 1.1)[..., None] * WARM
    rgb = base * shade
    img = to_image(rgb, 3.0).convert('RGBA')
    i, j = np.meshgrid(np.arange(w), np.arange(h))
    holes = (i % 3 == 1) & (j % 4 != 0)
    img.putalpha(Image.fromarray(np.where(holes, 0, 255).astype(np.uint8), 'L'))
    return img


def ripples(x, z, k=1.0):
    v = (np.sin(x * 5.0 * k + np.sin(z * 4.0) * 0.8) + np.sin(z * 6.0 * k + np.sin(x * 3.1) * 1.2 + 1)
         + np.sin((x + z) * 4.4 * k + 2)) / 3
    return np.clip(1 - np.abs(v) * 2.4, 0, 1) ** 2


def paint_surface(name, tpm=20):
    """A tank's surface from above, half-blended over its depths: near black, ripples, the lamps'
    glints where they hang near."""
    x0, z0, x1, z1 = WATERS[name]
    w, h = int((x1 - x0) * tpm), int((z1 - z0) * tpm)
    x, z = grid(x0, x1, z0, z1, w, h)
    # agent W: the ripples and the lamps' glints on them move now (at_wwater's overlay); the
    # surface keeps their average (0.8 * 0.237 + 0.35 * 0.21)
    c = np.full_like(x, 0.26)
    tint = np.array([2, 8, 14]) if name == 'shark' else np.array([4, 14, 14])
    rgb = tint + c[..., None] * (np.array([20, 42, 54]) if name == 'shark' else np.array([26, 56, 50]))
    for L in LAMPS:
        lx, _, lz = L['lens']
        g = np.exp(-((x - lx) ** 2 + (z - lz) ** 2) / 1.1)
        k = 0.6 if L['light'] == 'bridge' else 1.0
        rgb += (g * (0.25 + 1.6 * c) * k)[..., None] * np.array([150, 120, 70])
    # the wake round the fins
    for (fx, fz, hd) in SHARKS:
        if x0 < fx < x1 and z0 < fz < z1:
            c2, s2 = math.cos(math.radians(hd)), math.sin(math.radians(hd))
            u = (x - fx) * c2 + (z - fz) * s2
            v = -(x - fx) * s2 + (z - fz) * c2
            wake = np.exp(-(np.abs(v) - 0.12 - np.clip(-u, 0, None) * 0.25) ** 2 / 0.003) * (u < 0.1) * np.exp(np.clip(u, None, 0) / 0.8)
            rgb += (wake * 0.8)[..., None] * np.array([70, 100, 110])
    return to_image(rgb, 3.0)


def paint_deep(name, tpm=16):
    """The tank's depths under the surface: the shark tank black with a drain grate's glint; the
    turtle pool shallower, green-grey sand."""
    x0, z0, x1, z1 = WATERS[name]
    w, h = int((x1 - x0) * tpm), int((z1 - z0) * tpm)
    x, z = grid(x0, x1, z0, z1, w, h)
    rng = np.random.default_rng(len(name))
    if name == 'shark':
        rgb = np.zeros((h, w, 3)) + np.array([10, 22, 30]) + (rng.random((h, w)) - 0.5)[..., None] * 6
        rgb += 0.16 * np.array([6, 16, 20])       # agent W: the net moves (at_wwater)
        rgb *= (0.6 + 0.4 * smoothstep(0.0, 1.2, np.minimum.reduce([x - x0, x1 - x, z - z0, z1 - z])))[..., None]
    else:
        rgb = np.zeros((h, w, 3)) + np.array([40, 66, 58]) + (rng.random((h, w)) - 0.5)[..., None] * 10
        rgb += 0.16 * np.array([20, 40, 34])      # agent W: the net moves (at_wwater)
        rgb *= (0.55 + 0.45 * smoothstep(0.0, 1.0, np.minimum.reduce([x - x0, x1 - x, z - z0, z1 - z])))[..., None]
    for L in LAMPS:
        lx, _, lz = L['lens']
        rgb += (np.exp(-((x - lx) ** 2 + (z - lz) ** 2) / 2.0) * 0.35)[..., None] * np.array([60, 60, 40])
    return to_image(rgb, 3.0)


def paint_back(x0, x1, w=255, h=66):
    """The back wall: glazed white tile to 1.2 m, grimy, painted concrete above; a water main and
    its valves, nets and poles on hooks, a coiled hose, the back lamp's glow round its bracket."""
    x, y = grid(x0, x1, 0.0, H, w, h)
    rng = np.random.default_rng(abs(int(x0)) + 3)
    base = np.zeros((h, w, 3)) + np.array([88, 92, 96]) + (rng.random((h, w)) - 0.5)[..., None] * 8
    tile = y < 1.2
    tiles = np.zeros((h, w, 3)) + np.array([150, 160, 164])
    grout = (np.abs((x / 0.15) % 1 - 0.5) > 0.42) | (np.abs((y / 0.15) % 1 - 0.5) > 0.42)
    tiles = np.where(grout[..., None], tiles * 0.7, tiles)
    tiles *= (0.7 + 0.3 * smoothstep(0.0, 0.6, y))[..., None]          # grime toward the floor
    base = np.where(tile[..., None], tiles, base)
    base = np.where((np.abs(y - 1.2) < 0.03)[..., None], np.array([60, 110, 130]), base)
    for py, r_, col in ((1.85, 0.08, (60, 90, 110)), (1.55, 0.04, (150, 60, 50))):
        p = np.abs(y - py) < r_
        base = np.where(p[..., None], np.array(col) * (1.1 - 0.4 * ((y - py) / r_ + 1) / 2)[..., None], base)
    for vx in (-7.8, -2.6, 2.2, 6.4):
        base = np.where((rect(x, y, vx - 0.08, 1.75, vx + 0.08, 2.0) > 0)[..., None], np.array([170, 50, 40]), base)
    shade = np.zeros((h, w, 3)) + 0.36
    lx, ly, _ = LAMPS[3]['lens']
    shade += (np.exp(-((x - lx) / 1.4) ** 2 - ((y - ly + 0.6) / 0.9) ** 2) * 1.5)[..., None] * WARM
    rgb = base * shade
    return to_image(rgb, 4.0)


def draw_gear(img, x0, x1):
    w, h = img.size
    d = ImageDraw.Draw(img)

    def px(x, y):
        return ((x - x0) / (x1 - x0) * w, (H - y) / H * h)
    for nx in (-8.2, 1.3, 5.0):                      # nets on long poles, hung on hooks
        if x0 <= nx <= x1:
            d.line([px(nx, 0.15), px(nx + 0.25, 2.2)], fill=(150, 140, 110))
            cx, cy = px(nx + 0.25, 2.2)
            d.ellipse([cx - 5, cy - 3, cx + 5, cy + 6], outline=(120, 130, 130))
    for hx in (-6.0, 3.6):                           # hoses coiled on hooks
        if x0 <= hx <= x1:
            cx, cy = px(hx, 1.45)
            for k, rr in enumerate((7, 6, 5, 4)):
                d.ellipse([cx - rr * 1.2, cy - rr, cx + rr * 1.2, cy + rr], outline=(40, 110, 64) if k % 2 else (30, 86, 50))
    if x0 <= -3.2 <= x1:                             # a pole hook board
        for k in range(5):
            d.line([px(-3.6 + k * 0.18, 0.1), px(-3.5 + k * 0.18, 2.3)], fill=(130, 120, 96))
    return img


def paint_louvre(w=16, h=16):
    img = Image.new('RGB', (w, h), (84, 96, 104))
    d = ImageDraw.Draw(img)
    for k in range(1, h, 3):
        d.line([(1, k), (w - 2, k)], fill=(40, 46, 52))
    return img


def paint_motor(w=24, h=24):
    """A housing where the section cuts it: the pump's motor and its pipe flanges."""
    img = Image.new('RGB', (w, h), (50, 56, 62))
    d = ImageDraw.Draw(img)
    d.ellipse([3, 3, 15, 15], fill=(60, 110, 140), outline=(20, 30, 36))
    d.ellipse([7, 7, 11, 11], fill=(30, 50, 60))
    d.rectangle([16, 6, 22, 12], fill=(140, 60, 50))
    d.rectangle([4, 17, 20, 21], fill=(90, 96, 100))
    return img


# ---- the room

SHARKS = [(-6.3, -1.6, 70), (-2.4, 1.2, 250), (-5.8, 2.0, 190)]


def shell_nodes():
    n = []
    # the walkways: tops textured per piece, the tanks' walls down into the dark
    m = Mesh()
    for k, (x0, z0, x1, z1) in enumerate(walk_quads()):
        m.quad_y(0.0, x0, x1, z0, z1, 1, f'walk_{k}')
    for name, (x0, z0, x1, z1) in WATERS.items():
        m.quad_z(z1, x0, x1, DEEP, 0.0, -1, 'tank_wall')          # its far wall, toward the camera
        m.quad_x(x0, DEEP, 0.0, z0, z1, 1, 'tank_wall')
        m.quad_x(x1, DEEP, 0.0, z0, z1, -1, 'tank_wall')
    n.append(m.node('walks', 'tank_wall'))
    f = Mesh()
    f.prism([(XO0, -SLAB), (XO1, -SLAB), (XO1, CUT_H), (XO0, CUT_H)], ZO0, Z0, 'cut', back='section',
            sides={0: None})
    n.append(f.node('front_wall', 'cut'))
    # the end walls round their doorways, the back wall in two painted chunks
    for s in 'we':
        ax0, ax1 = (XO0, X0) if s == 'w' else (X1, XO1)
        inner, outer = ('right', 'left') if s == 'w' else ('left', 'right')
        for i, (a, b) in enumerate(s2room.segments(Z0, ZO1, GAPS[s])):
            op = ['bottom', outer]
            faces = {inner: 'end_in', 'top': 'cut', 'back': 'cut' if a == Z0 else 'reveal'}
            if b >= ZO1:
                op.append('front')
            else:
                faces['front'] = 'reveal'
            n.append(box(f'end_{s}_{i}', (ax0, -SLAB, a), (ax1, H, b), 'end_in', open=op, faces=faces))
        for i, (a, b) in enumerate(GAPS[s]):
            n.append(box(f'end_{s}_lintel_{i}', (ax0, 2.1, a), (ax1, H, b), 'end_in', open=['front', 'back', outer],
                         faces={'bottom': 'soffit', 'top': 'cut', inner: 'end_in'}))
            n.append(box(f'end_{s}_sill_{i}', (ax0, -SLAB, a), (ax1, 0.0, b), 'cut',
                         open=['bottom', 'front', 'back', inner, outer], faces={'top': 'threshold'}))
    for k, (a, b) in enumerate(((X0, 0.0), (0.0, X1))):
        n.append(box(f'back_{k}', (a, -SLAB, Z1), (b, H, ZO1), 'end_in', open=['bottom', 'left', 'right', 'front'],
                     faces={'back': f'back_{k}', 'top': 'cut'}))
    # beyond the doors: the kitchen's lit landing (east), the stair down to the catwalk (west)
    bm = Mesh()
    for dr in D['doors']:
        a, b = dr['at']
        s = 1 if dr['side'] == 'e' else -1
        xw = XO1 if s > 0 else XO0
        L = 1.4
        mat = 'beyond_kitchen' if dr['id'] == 'kitchen' else 'beyond_stair'
        bm.quad_y(0.0, *sorted((xw, xw + s * L)), a, b, 1, mat)
        steps = 4 if dr['id'] == 'great' else 0
        for k in range(steps):
            xa = xw + s * (L + k * 0.28)
            xb = xa + s * 0.28
            bm.quad_x(xa, -(k + 1) * 0.2, -k * 0.2, a, b, -s, 'riser')
            bm.quad_y(-(k + 1) * 0.2, *sorted((xa, xb)), a, b, 1, mat)
        far = xw + s * (L + steps * 0.28)
        for z, fz in ((a, 1), (b, -1)):
            bm.quad_z(z, *sorted((xw, far)), -SLAB - steps * 0.2, 2.1, fz, 'beyond_wall')
    n.append(bm.node('beyond', 'beyond_wall'))
    return n


def prop_nodes():
    n = []
    # the bridge: grated, railed both sides
    bx0, bz0, bx1, bz1 = BRIDGE
    n.append(box('bridge', (bx0, -0.12, bz0), (bx1, 0.0, bz1), 'deck_edge', open=['bottom', 'back', 'front'],
                 faces={'top': 'bridge'}))
    rm = Mesh()
    for x in (bx0, bx1):
        rm.quad_x(x, 0.0, CUT_H, bz0, bz1, -1, 'rail')
    n.append(rm.node('rails', 'rail'))
    # the life-support housings, cut by the section: louvred sides, the pump showing
    for pid in ('housing_0', 'housing_1'):
        x0, z0, x1, z1 = PROPS[pid][2]
        op = ['bottom'] + (['right'] if x1 >= X1 else [])
        n.append(box(pid, (x0, -0.02, z0), (x1, CUT_H, z1), 'housing', open=op,
                     faces={'top': 'motor', 'back': 'louvre'}))
    # their pipes into the water: housing 0's into the shark tank, housing 1's into the turtle pool
    for k, (x, z) in enumerate(((-1.6, 2.82), (7.42, 1.42))):
        n.append(at({'id': f'pipe_{k}', 'op': 'cylinder', 'radius': 0.07, 'height': 0.95, 'segments': 6, 'material': 'pipe'},
                    translate=[x, SURFACE - 0.1 + 0.475, z]))
    # the lamps: clamp lamps on posts at the tanks' edges, the back one on a bracket on the wall
    for k, L in enumerate(LAMPS):
        lx, ly, lz = L['lens']
        if L['post']:
            px, pz = L['post']
            n.append(box(f'lamp_post_{k}', (px - 0.03, SURFACE - 0.1, pz - 0.03), (px + 0.03, ly - 0.06, pz + 0.03), 'post',
                         open=['bottom', 'top']))
            n.append(box(f'lamp_{k}', (min(px, lx) - 0.1, ly - 0.08, min(pz, lz) - 0.1),
                         (max(px, lx) + 0.1, ly + 0.05, max(pz, lz) + 0.1), 'lamp', faces={'bottom': 'lens', 'back': 'lens'}))
        else:
            n.append(box(f'lamp_{k}', (lx - 0.25, ly - 0.08, lz - 0.1), (lx + 0.25, ly + 0.08, Z1), 'lamp',
                         open=['front'], faces={'bottom': 'lens', 'back': 'lens'}))
    # the skiff tied up in the shark tank's corner
    sk = Mesh()
    sx0, sx1, sz0, sz1, y0, y1 = -7.45, -6.15, 2.25, 2.85, SURFACE - 0.05, SURFACE + 0.18
    outline = [(sx0 + 0.15, sz0), (sx1 - 0.25, sz0), (sx1, (sz0 + sz1) / 2), (sx1 - 0.25, sz1), (sx0 + 0.15, sz1),
               (sx0, (sz0 + sz1) / 2)]
    sk.poly([(x, y1, z) for x, z in outline], (0, 1, 0), 'skiff_in')
    cx, cz = sum(q[0] for q in outline) / 6, sum(q[1] for q in outline) / 6
    for a, b in zip(outline, outline[1:] + outline[:1]):
        nx, nz = b[1] - a[1], -(b[0] - a[0])
        if nx * ((a[0] + b[0]) / 2 - cx) + nz * ((a[1] + b[1]) / 2 - cz) < 0:
            nx, nz = -nx, -nz
        sk.poly([(a[0], y0, a[1]), (b[0], y0, b[1]), (b[0], y1, b[1]), (a[0], y1, a[1])], (nx, 0, nz), 'skiff')
    n.append(sk.node('skiff', 'skiff'))
    return n


def room_lights():
    out = []
    for k, L in enumerate(LAMPS):
        lx, ly, lz = L['lens']
        out.append({'id': f'lamp_{k}', 'at': [lx, ly - 0.15, lz], 'color': '#ffe0a8',
                    'intensity': 0.7 if L['light'] == 'bridge' else 1.4, 'range': 2.6})
    out.append({'id': 'kitchen', 'at': [X1 + 0.8, 1.6, -3.6], 'color': '#f0f4ff', 'intensity': 1.6, 'range': 2.6})
    return out


def room_recipe():
    m = {
        'cut': {'color': '#3c475e', 'class': 'emissive'},
        'section': {'color': '#4a5468', 'class': 'emissive',
                    'texture': {'image': f'art/{P}section.png', 'bits': 4, 'projection': 'fit'}},
        'end_in': {'color': '#2e3644'}, 'reveal': {'color': '#343e4e'},
        'soffit': {'color': '#3a4658', 'class': 'emissive'}, 'threshold': {'color': '#3e4652', 'class': 'emissive'},
        'beyond_wall': {'color': '#20262e', 'class': 'emissive'}, 'riser': {'color': '#262c36', 'class': 'emissive'},
        'beyond_kitchen': {'color': '#9a9c94', 'class': 'emissive'}, 'beyond_stair': {'color': '#2c3442', 'class': 'emissive'},
        'tank_wall': {'color': '#1e3038', 'class': 'emissive'},
        'deck_edge': {'color': '#5a6474'}, 'bridge': emissive('#5a6470', f'{P}bridge', bits=4),
        'rail': {'color': '#a8b0bc', 'double_sided': True,
                 'texture': {'image': f'art/{P}rail.png', 'bits': 4, 'projection': 'box', 'scale': [1.0, 1.0]}},
        'housing': {'color': '#4a5662'},
        'louvre': {'color': '#54606a', 'texture': {'image': f'art/{P}louvre.png', 'bits': 4, 'projection': 'box',
                                                   'scale': [0.5, 0.5]}},
        'motor': emissive('#405060', f'{P}motor', bits=4),
        'pipe': {'color': '#6a7a86'}, 'post': {'color': '#3a3e46'},
        'lamp': {'color': '#30343c'}, 'lens': {'color': '#fff2c8', 'class': 'emissive'},
        'skiff': {'color': '#c8c4b4'}, 'skiff_in': {'color': '#5a6a7a'},
    }
    for k, _ in enumerate(walk_quads()):
        m[f'walk_{k}'] = emissive('#4a5058', f'{P}walk_{k}', bits=8)
    for k in range(2):
        m[f'back_{k}'] = emissive('#40464e', f'{P}back_{k}')
    nodes = shell_nodes() + prop_nodes()
    lighting = {'direction': [-0.2, 0.8, -0.55], 'ambient': 0.3, 'diffuse': 0.25, 'lights': room_lights(),
                'refine': {'tolerance': 22, 'max_added': 100}}
    return recipe(P + 'room', m, nodes, lighting, 1500)


def shark(mb, x, y, z, hd, L=2.0):
    c, s = math.cos(math.radians(hd)), math.sin(math.radians(hd))

    def p(u, v, dy=0.0):
        return (x + u * c - v * s, y + dy, z + u * s + v * c)
    W = L * 0.16
    body = [p(L * 0.5, 0), p(L * 0.15, W), p(-L * 0.3, W * 0.4), p(-L * 0.3, -W * 0.4), p(L * 0.15, -W)]
    mb.poly(body, (0, 1, 0), 'shark')
    mb.poly([p(L * 0.12, W * 0.9, -0.04), p(-L * 0.02, W * 2.4, -0.04), p(-L * 0.06, W * 0.7, -0.04)], (0, 1, 0), 'shark')
    mb.poly([p(L * 0.12, -W * 0.9, -0.04), p(-L * 0.06, -W * 0.7, -0.04), p(-L * 0.02, -W * 2.4, -0.04)], (0, 1, 0), 'shark')
    mb.poly([p(-L * 0.3, 0), p(-L * 0.52, W * 0.9), p(-L * 0.46, 0), p(-L * 0.52, -W * 0.9)], (0, 1, 0), 'shark')
    # the dorsal fin, up out of the water
    top = SURFACE + 0.4
    a, b = p(L * 0.1, 0, 0.0), p(-L * 0.14, 0, 0.0)
    tip = p(-L * 0.12, 0, 0.0)
    mb.poly([(a[0], y + 0.02, a[2]), (b[0], y + 0.02, b[2]), (tip[0] - c * 0.05, top, tip[2] - s * 0.05)], (-s, 0, c), 'fin')


def turtle(mb, x, y, z, hd, L=0.9, mat='turtle'):
    c, s = math.cos(math.radians(hd)), math.sin(math.radians(hd))

    def p(u, v, dy=0.0):
        return (x + u * c - v * s, y + dy, z + u * s + v * c)
    for side in (1, -1):
        mb.poly([p(L * 0.2, side * L * 0.25), p(L * 0.02, side * L * 0.62), p(-L * 0.05, side * L * 0.2)], (0, 1, 0), 'flipper')
        mb.poly([p(-L * 0.3, side * L * 0.15), p(-L * 0.45, side * L * 0.3), p(-L * 0.38, side * L * 0.08)], (0, 1, 0), 'flipper')
    mb.poly([p(L * 0.42, -L * 0.07), p(L * 0.6, 0), p(L * 0.42, L * 0.07)], (0, 1, 0), 'flipper')


def water_recipe():
    m = {
        'shark': {'color': '#3a4a58', 'double_sided': True}, 'fin': {'color': '#9aa8b4', 'double_sided': True},
        'turtle': {'color': '#5a6a3c', 'smooth': True}, 'flipper': {'color': '#7a8a6a', 'double_sided': True},
        'rock': {'color': '#3a4440'}, 'rock_top': {'color': '#58625a'},
    }
    for name in WATERS:
        m[f'{name}_surface'] = {'color': '#06121c', 'blend': 'half',
                                'texture': {'image': f'art/{P}{name}_surface.png', 'bits': 4, 'projection': 'fit'}}
        m[f'{name}_deep'] = emissive('#0c1a22', f'{P}{name}_deep', bits=8)
    n = []
    w = Mesh()
    for name, (x0, z0, x1, z1) in WATERS.items():
        w.quad_y(DEEP, x0, x1, z0, z1, 1, f'{name}_deep')
    n.append(w.node('deeps', 'shark_deep'))
    sf = Mesh()
    for name, (x0, z0, x1, z1) in WATERS.items():
        sf.quad_y(SURFACE, x0, x1, z0, z1, 1, f'{name}_surface')
    n.append(sf.node('surfaces', 'shark_surface'))
    life = Mesh()
    for k, (x, z, hd) in enumerate(SHARKS):
        shark(life, x, SURFACE - 0.22 - 0.06 * k, z, hd, [2.1, 1.8, 1.6][k])
    turtle(life, 3.4, SURFACE - 0.3, -1.6, 30)
    turtle(life, 5.95, -0.1, 0.2, 200, 0.8)
    n.append(life.node('life', 'shark'))
    n.append(at({'id': 'shell_0', 'op': 'sphere', 'radius': 1.0, 'rings': 3, 'segments': 8, 'material': 'turtle'},
                translate=[3.4, SURFACE - 0.3, -1.6], rotate=[0, -30, 0]))
    n[-1]['transform']['scale'] = [0.42, 0.1, 0.32]
    # the haul-out rock in the turtle pool, its top just out of the water, a turtle on it
    n.append(at({'id': 'rock', 'op': 'lathe', 'profile': [[1.1, 0.0], [0.95, 0.95], [0.5, 1.2]], 'segments': 7,
                 'material': 'rock', 'faces': {'top': 'rock_top'}},
                translate=[6.0, DEEP - 0.05, 0.1]))
    n[-1]['transform']['scale'] = [1.1, 1.0, 0.8]
    n.append(at({'id': 'shell_1', 'op': 'sphere', 'radius': 1.0, 'rings': 3, 'segments': 8, 'material': 'turtle'},
                translate=[5.95, -0.08, 0.2], rotate=[0, 20, 0]))
    n[-1]['transform']['scale'] = [0.38, 0.1, 0.3]
    lighting = {'direction': [-0.2, 1.0, -0.4], 'ambient': 0.45, 'diffuse': 0.45}
    return recipe(P + 'water', m, n, lighting, 600)


def wwater_recipe():
    """Agent W: the moving water (NOTES_W.md). The glints on both surfaces, lit by the work lamps
    (the bridge's at half strength, as painted: it runs on a timer the bake cannot follow) and
    faintly by the roof's dark; the caustic net on the turtle pool's sand and, fainter, in the
    shark tank's black."""
    ov = wateranim.Overlay(P + 'wwater')
    ov.material('glint', 'w_ripple')
    ov.material('net', 'w_caustic')
    for name, (x0, z0, x1, z1) in WATERS.items():
        ov.floor('glint', SURFACE + 0.03, x0 + 0.01, x1 - 0.01, z0 + 0.01, z1 - 0.01, nx=3, nz=3)
        ov.floor('net', DEEP + 0.03, x0 + 0.01, x1 - 0.01, z0 + 0.01, z1 - 0.01, nx=2, nz=2)
    for L in LAMPS:
        k = 0.5 if L['light'] == 'bridge' else 1.0
        lx, ly, lz = L['lens']
        ov.light((lx, ly, lz), '#ffd890', round(3.0 * k, 2), 2.6, id=f'lamp_{L["light"]}')
    ov.light((-4.5, 3.5, 0.0), '#3a6a80', 0.8, 6.5, id='dark_shark')
    ov.light((4.5, 3.0, -0.7), '#3a8070', 1.5, 6.0, id='dark_turtle')
    return ov.recipe(ART, refine={'tolerance': 20, 'max_added': 64})


def collision_recipe():
    return recipe(P + 'room_col', {'floor': {'color': '#8c9098'}}, aqroom.shell_nodes(D, collision=True), None, 400,
                  collision=True)


def main():
    art = {}
    for k, q in enumerate(walk_quads()):
        art[f'{P}walk_{k}'] = paint_walk(*q)
    for k, (a, b) in enumerate(((X0, 0.0), (0.0, X1))):
        art[f'{P}back_{k}'] = draw_gear(paint_back(a, b), a, b)
    for name in WATERS:
        art[f'{P}{name}_surface'] = paint_surface(name)
        art[f'{P}{name}_deep'] = paint_deep(name)
    art.update({P + 'section': paint_section(XO0, XO1), P + 'rail': paint_rail(), P + 'bridge': paint_bridge(),
                P + 'louvre': paint_louvre(), P + 'motor': paint_motor()})
    for name, img in art.items():
        save_png(img, ART / f'{name}.png')
    for rec in (room_recipe(), water_recipe(), wwater_recipe(), collision_recipe()):    # agent W: wwater
        write_json(OUT / f'{rec["name"]}.asset.json', rec)
    placements = [{'id': P + 'room', 'asset': P + 'room', 'position': [0, 0, 0], 'collision': P + 'room_col'},
                  {'id': P + 'water', 'asset': P + 'water', 'position': [0, 0, 0], 'collision': 'none'},
                  {'id': P + 'wwater', 'asset': P + 'wwater', 'position': [0, 0, 0], 'collision': 'none'}]  # agent W
    write_json(HERE / 'aq_tops.placements.json',
               {'format': 'after-hours-placements', 'version': 1, 'room': 'aq_tops', 'placements': placements})


if __name__ == '__main__':
    main()
