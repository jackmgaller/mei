#!/usr/bin/env python3
"""The aquarium room sketch for After Hours: writes its Asset Kit recipes and draws its textures.

    python3 carts/afterhours/rooms/aquarium/make_aquarium.py

Writes, beside itself:
  aq_room.asset.json       the hall: floor slab, the section-cut walls, the window wall, bench,
                           pillar, stanchions, sign, cleaner's cart, lit by the room's point lights
  aq_tanks.asset.json      the three tanks: the ocean window (its glass, rock, kelp and animals,
                           under a dark lid), the glass column (sardines) and the coral cube
  standin_thief.asset.json a 1.7 m stand-in thief in one strong colour
  standin_guard.asset.json a stand-in guard
  sight_cone.asset.json    the guard's sight cone, 6 m and 60 degrees, cut by the walls and pillar
  art/*.png                the floor (painted as the lights light it), tank back, sand, signs,
                           ripples, kelp
  aquarium.placements.json where the level (levels/level1/make_level1.py) places the recipes

The room is 12.1 m across (outer walls), 6.3 m deep, its floor at y = 0 and centred on the
origin; the camera stands on its -Z side. Light: one list, room_lights(), drives both the Asset
Kit's point lights (lighting.lights, baked into the walls' and props' vertex colours, with soft
shadows) and paint_floor(), which evaluates the same formula on the floor and adds what corners
cannot carry: the water's shimmer in the window's light, soft shadows, the guide studs. The floor
is emissive, so the kit spends no refinement triangles on it. The tanks' recipe has two lights of
its own (inside the glass column and the coral cube). AQ_REFINE='{"max_added": 0}' overrides
the room's refinement, for comparisons. Everything here is fictional. Text uses the OFL fonts in
tools/fonts/ only. Needs Pillow and NumPy.
"""
import json
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import sys  # agent W: the moving water's tiles (carts/afterhours/water/wateranim.py, NOTES_W.md)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'water'))
import wateranim  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = HERE / 'art'
FONTS = ROOT / 'tools' / 'fonts'

# ---- the room's plan (metres; X right, Y up, Z away from the camera)
XI = 5.8            # inner face of the side walls
XO = 6.05           # outer face of the front wall and the piers
SLAB_X, SLAB_Z = 6.08, -3.18    # the floor slab stands 3 cm proud of the walls, as a model's base
SIDE_OUT = 6.04     # side walls' outer face, 1 cm inside the front wall's end
ZF, ZFO = -2.9, -3.15   # front wall: inner and outer faces
ZB, ZBO = 2.9, 3.15     # back (window) wall
H = 3.2             # wall height (the section cut through the room's ceiling)
CUT = 1.0           # the front wall, cut like an architect's section
ENTRY = (-4.9, -3.7)    # the gap in the front wall: the way in, from the jellyfish gallery
WIN_X = 4.4         # the ocean window: x in [-WIN_X, WIN_X], y in [WIN_Y0, WIN_Y1]
WIN_Y0, WIN_Y1 = 0.5, 2.7
SLAB = 0.4          # floor slab thickness, shown in section at the front

TANK_X = 4.6        # the big tank's water: x in [-TANK_X, TANK_X], z in [ZBO, TANK_Z1]
TANK_Z1 = 4.6
TANK_WALL = 0.25
TANK_BASE_X = 4.88  # the tank's base stands 3 cm proud of its walls
SAND_Y = 0.35
WATER_Y = 2.95

COLUMN = (-2.9, -0.2)       # the glass column (PLAN.md's "jellyfish column"): sardines now, the
COLUMN_R = 0.75             # jellyfish are the jellyfish gallery's (levels/aquarium/ROUTE.md)
CUBE = (3.0, 0.15)           # the coral cube
CUBE_S = 1.42
PILLAR = (-0.2, -1.6)      # structural column, 0.5 m square
PILLAR_S = 0.5
BENCH = (0.0, 1.35)         # long bench facing the window
BENCH_W = 2.6               # PLAN.md: shortened so the keeper walks between it and the cube
STANCHION_Z = 2.42
STANCHION_X = (-3.6, -1.8, 0.0, 1.8, 3.6)
CART = (4.7, -2.25)         # the night cleaner's cart, left by the front wall
SIGN = (-1.65, -0.5)       # the column's lightbox
DOOR_X = (4.84, 5.66)       # the staff door's opening in the right pier (PLAN.md: the exit at x 5.25)
DOOR_H = 2.1
CORRIDOR_Z1 = 4.95          # the service corridor beyond the staff door runs back to here, then east
PASSAGE_Z0 = -4.5           # the jellyfish gallery's end, beyond the way in, runs out to here

# the watchers of PLAN.md at one moment of the solution: the watchman looks over the room (his cone
# toward the camera) while the keeper walks west along the cube's far side. Headings in degrees in
# the XZ plane, from +X toward +Z (270: toward -Z, the camera).
WATCHERS = [{'id': 'watchman', 'at': (0.0, 2.0), 'heading': 270.0, 'length': 5.0},
            {'id': 'keeper', 'at': (3.3, 1.95), 'heading': 180.0, 'length': 4.5}]
CONE_FOV = 60.0
CONE_RAYS = 16
THIEF = (-0.22, -2.5)       # in the pillar's shadow (PLAN.md's solution)
WALL_TANKS = (-1.4, 0.9)    # z of the small tanks set into each side wall
ROUTE_LIGHTS = [(-4.3, -2.2), (-4.3, -1.3), (-4.0, -0.4), (-3.3, 0.85), (-2.2, 1.0), (-0.9, 0.55),
                (0.6, 0.55), (1.9, 0.75), (3.1, 1.3), (4.2, 1.6), (5.0, 2.2)]

# ---- the room's light: one list drives both the kit's bake (walls and props: lighting.lights)
# and the painting of the floor (paint_floor evaluates the same formula, with the water's shimmer
# and soft shadows painted in, so the floor needs no refinement triangles)
ROOM_DIRECTION = [0.12, 0.62, 1.0]     # a faint fill from the big tank, above and behind
ROOM_AMBIENT = 0.24
ROOM_DIFFUSE = 0.12
ENTRY_X = (ENTRY[0] + ENTRY[1]) / 2


def room_lights():
    window = [{'id': f'window_{k}', 'at': [x, 1.5, ZB - 0.7], 'color': '#48b4ff', 'intensity': 1.8,
               'range': 5.0, 'shadows': True, 'radius': 0.6} for k, x in enumerate((-3.3, -1.1, 1.1, 3.3))]
    walls = [{'id': f'wall_tank_{k}', 'at': [sx * (XI - 0.35), 1.3, wz], 'color': '#50c0e8', 'intensity': 0.9,
              'range': 1.6} for k, (sx, wz) in enumerate((sx, wz) for sx in (-1, 1) for wz in WALL_TANKS)]
    return window + [
        {'id': 'column', 'at': [COLUMN[0], 1.3, COLUMN[1]], 'color': '#a8ccff', 'intensity': 3.6, 'range': 3.4,
         'shadows': True, 'radius': 0.5},
        {'id': 'coral', 'at': [CUBE[0], 1.2, CUBE[1]], 'color': '#3ae6cc', 'intensity': 4.2, 'range': 3.0,
         'shadows': True, 'radius': 0.5},
        {'id': 'exit', 'at': [5.25, 2.2, ZB - 0.3], 'color': '#50ff90', 'intensity': 0.8, 'range': 1.8},
        # the jellyfish gallery's violet, low through the way in (the front wall shades it but there)
        {'id': 'gallery', 'at': [ENTRY_X, 0.8, ZFO - 0.75], 'color': '#a070ff', 'intensity': 3.2, 'range': 4.6,
         'shadows': True, 'radius': 0.2, 'through': (ZFO, ENTRY[0], ENTRY[1], CUT)},
        # the service corridor's tube, through the staff door (the piers and lintel shade it)
        {'id': 'corridor', 'at': [5.3, 2.5, 3.95], 'color': '#e8f4ff', 'intensity': 1.6, 'range': 4.4,
         'shadows': True, 'radius': 0.15, 'through': (ZB, DOOR_X[0], DOOR_X[1], DOOR_H)}] + walls


def kit_lights():
    """room_lights() as the Asset Kit takes them (without the floor painter's own keys)."""
    return [{k: v for k, v in l.items() if k != 'through'} for l in room_lights()]


ROOM_REFINE = {'tolerance': 20, 'max_added': 160}
if os.environ.get('AQ_REFINE'):        # for comparing refinements: AQ_REFINE='{"max_added": 0}'
    ROOM_REFINE = json.loads(os.environ['AQ_REFINE'])


def r(v, n=4):
    return round(float(v), n)


def hexc(rgb):
    return '#%02x%02x%02x' % tuple(int(max(0, min(255, round(c)))) for c in rgb)


# ---- recipe helpers

def box(id, lo, hi, material, **extra):
    """A box from corner lo to corner hi (world units)."""
    size = [r(h - l) for l, h in zip(lo, hi)]
    centre = [r((l + h) / 2) for l, h in zip(lo, hi)]
    node = {'id': id, 'op': 'box', 'size': size, 'material': material,
            'transform': {'translate': centre}}
    node.update(extra)
    return node


def at(node, translate=None, rotate=None, scale=None):
    t = {}
    if scale: t['scale'] = [r(s) for s in scale]
    if rotate: t['rotate'] = [r(a, 3) for a in rotate]
    if translate: t['translate'] = [r(c) for c in translate]
    node['transform'] = t
    return node


def newell(points):
    n = [0.0, 0.0, 0.0]
    for a, b in zip(points, points[1:] + points[:1]):
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


class MeshBuilder:
    """Polygons for a `mesh` node, each turned to face a given direction."""

    def __init__(self):
        self.vertices, self.faces, self.materials = [], [], []
        self.index = {}

    def v(self, p):
        key = tuple(r(c, 5) for c in p)
        if key not in self.index:
            self.index[key] = len(self.vertices)
            self.vertices.append(list(key))
        return self.index[key]

    def poly(self, points, facing, material=None):
        n = newell(points)
        if sum(a * b for a, b in zip(n, facing)) < 0:
            points = list(reversed(points))
        self.faces.append([self.v(p) for p in points])
        self.materials.append(material)

    def node(self, id, material):
        node = {'id': id, 'op': 'mesh', 'material': material, 'vertices': self.vertices,
                'faces': self.faces}
        if any(m for m in self.materials):
            node['face_materials'] = [m or material for m in self.materials]
        return node


def recipe(name, materials, nodes, lighting, budget, prototypes=None, verification=None):
    out = {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': budget,
           'materials': materials}
    if prototypes:
        out['prototypes'] = prototypes
    out['nodes'] = nodes
    out['lighting'] = lighting
    out['verification'] = verification or {'required': True, 'depth': True, 'perspective': True}
    return out


def write(name, data):
    (HERE / f'{name}.asset.json').write_text(json.dumps(data, indent=1) + '\n')


# ---- painting helpers (float RGB arrays, 0-255)

def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def caustics(x, z, scale=1.0, seed=0.0):
    """A caustic net: bright thin lines, 0..1, deterministic."""
    x = x * scale
    z = z * scale
    a = np.sin(x * 2.1 + np.sin(z * 1.7 + seed) * 1.4 + seed)
    b = np.sin(z * 2.6 + np.sin(x * 1.3 - seed) * 1.2 - seed * 0.5)
    c = np.sin((x + z) * 1.6 + np.sin((x - z) * 1.1 + seed) * 1.1)
    v = (a + b + c) / 3.0
    return np.clip(1 - np.abs(v) * 2.6, 0, 1) ** 3


BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0 - 0.5


def to_image(rgb, dither=6.0):
    h, w, _ = rgb.shape
    d = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w, None] * dither
    out = np.clip(np.round(rgb + d), 0, 255).astype(np.uint8)
    return Image.fromarray(out, 'RGB')


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


# ---- the floor: terrazzo lit through the glass

def blockers_2d():
    """Footprints that throw the tank's light: (x0, z0, x1, z1, height)."""
    px, pz = PILLAR
    h = PILLAR_S / 2
    bx, bz = BENCH
    out = [(px - h, pz - h, px + h, pz + h, CUT),
           (bx - BENCH_W / 2, bz - 0.25, bx + BENCH_W / 2, bz + 0.25, 0.5),
           (CUBE[0] - 0.75, CUBE[1] - 0.75, CUBE[0] + 0.75, CUBE[1] + 0.75, 0.72),
           (CART[0] - 0.45, CART[1] - 0.25, CART[0] + 0.45, CART[1] + 0.25, 0.9)]
    jx, jz = COLUMN
    out.append((jx - 0.55, jz - 0.55, jx + 0.55, jz + 0.55, 0.6))
    return out


def hex_rgb(c):
    return np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)


def floor_visibility(x, z, light):
    """The share of a light a floor point sees: 8 rays to a cube in the light's sphere (as the kit
    samples a soft light), blocked where a ray passes over a prop's footprint below its height."""
    lx, ly, lz = light['at']
    rad = light.get('radius', 0.0)
    offsets = [(0, 0, 0)] if rad == 0 else [(a * rad * 0.577, b * rad * 0.577, c * rad * 0.577)
                                             for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]
    vis = np.zeros_like(x)
    for ox, oy, oz in offsets:
        sx, sy, sz = lx + ox, ly + oy, lz + oz
        ok = np.ones_like(x, dtype=bool)
        for (x0, z0, x1, z1, hgt) in blockers_2d():
            if x0 < lx < x1 and z0 < lz < z1:
                continue            # a light standing in a tank does not shadow its own plinth
            for t in np.linspace(0.02, 0.98, 32):
                rx = x + (sx - x) * t
                rz = z + (sz - z) * t
                inside = (rx > x0) & (rx < x1) & (rz > z0) & (rz < z1) & (sy * t < hgt)
                ok &= ~inside
        vis += ok
    return vis / len(offsets)


def floor_light(x, z, light):
    """One point light's shade on the floor (normal +Y), per channel, by the kit's formula."""
    lx, ly, lz = light['at']
    d = np.sqrt((lx - x) ** 2 + ly ** 2 + (lz - z) ** 2)
    fall = np.clip(1 - (d / light['range']) ** 2, 0, None) ** 2
    k = light.get('intensity', 1.0) * (ly / d) * fall
    if light.get('shadows'):
        k = k * floor_visibility(x, z, light)
    if light.get('through'):        # a light beyond a wall reaches the floor only through its opening
        zp, x0, x1, ymax = light['through']
        t = (zp - z) / (lz - z)
        cx, cy = x + (lx - x) * t, ly * t
        k = k * ((t > 0) & (t < 1) & (cx > x0) & (cx < x1) & (cy < ymax))
    return k[..., None] * hex_rgb(light.get('color', '#ffffff'))[None, None, :] / 255


def paint_floor(w=220, h=126):
    """The terrazzo as the room's point lights light it, with the water's shimmer in the window's
    light, the guide studs and the door mat. Emissive: drawn exactly as painted."""
    xs = -SLAB_X + (np.arange(w) + 0.5) / w * (2 * SLAB_X)
    zs = ZBO - (np.arange(h) + 0.5) / h * (ZBO - SLAB_Z)
    x, z = np.meshgrid(xs, zs)
    rng = np.random.default_rng(7)
    # terrazzo in white light: blue-grey with pale chips and polished seams every 1.2 m
    base = np.zeros((h, w, 3)) + np.array([68, 92, 150])
    chips = rng.random((h, w))
    base += (chips > 0.93)[..., None] * np.array([40, 44, 50])
    base += (chips < 0.04)[..., None] * np.array([-20, -22, -28])
    seam = (np.abs(((x + 0.6) / 1.2) % 1 - 0.5) > 0.47) | (np.abs(((z + 0.6) / 1.2) % 1 - 0.5) > 0.47)
    base += seam[..., None] * np.array([-18, -20, -26])
    # the door mat at the way in
    mat = (np.abs(x - ENTRY_X) < 0.62) & (z < ZF + 0.95) & (z > ZF + 0.05)
    edge = mat & ((np.abs(x - ENTRY_X) > 0.52) | (z > ZF + 0.85) | (z < ZF + 0.15))
    base = np.where(mat[..., None], base * 0.4, base)
    base = np.where(edge[..., None], base * 0.4 + np.array([40, 44, 56]), base)
    dvec = np.array(ROOM_DIRECTION) / np.linalg.norm(ROOM_DIRECTION)
    shade = np.zeros((h, w, 3)) + ROOM_AMBIENT + ROOM_DIFFUSE * max(0.0, dvec[1])
    # the water's shimmer: a caustic net in the window's light, strongest near the glass
    # agent W: the net itself moves now (aq_water's caustic overlay); the floor keeps the light's
    # average, a little under it, so that the net adds what was painted
    caus = WATER_CAUS_MEAN
    near = np.exp(-(ZB - z) / 1.6)
    shimmer = (0.45 + 1.9 * caus * (0.2 + near))[..., None]
    for light in room_lights():
        add = floor_light(x, z, light)
        shade += add * shimmer if light['id'].startswith('window') else add
    # the coral cube's glow through its glass, close round its pedestal: painted, as the window's
    # cyan swamps what its point light alone gives the floor there
    cd = np.maximum(np.abs(x - CUBE[0]), np.abs(z - CUBE[1]))
    halo = np.exp(-((cd - 0.85) / 0.38) ** 2) * 0.9 + 0.35 / (1 + (cd / 1.1) ** 2)
    shade += halo[..., None] * np.array([0.25, 1.0, 0.85]) * 1.1
    rgb = base * shade
    # a slot of light along the sill
    rgb += (np.exp(-((ZB - z) / 0.3) ** 2) * (np.abs(x) < WIN_X))[..., None] * np.array([20, 80, 120])
    # the night guide lights: small cyan studs set in the floor along the visitors' route
    for (gx, gz) in ROUTE_LIGHTS:
        gd = np.hypot(x - gx, z - gz)
        rgb += (np.exp(-(gd / 0.09) ** 2) * 1.0)[..., None] * np.array([150, 230, 255])
        rgb += (0.25 * np.exp(-(gd / 0.3) ** 2))[..., None] * np.array([30, 90, 120])
    return to_image(rgb)


# ---- the ocean window's backdrop: deep water lit from the surface

def paint_tank_back(w=240, h=72):
    # the face: x in [-4.85, 4.85] (left to right, seen from the room), y from 3.22 (top) to 0.33
    xs = -4.85 + (np.arange(w) + 0.5) / w * 9.7
    ys = 3.22 - (np.arange(h) + 0.5) / h * (3.22 - 0.33)
    x, y = np.meshgrid(xs, ys)
    depth = np.clip((WATER_Y - y) / (WATER_Y - SAND_Y), 0, 1)
    top = np.array([90, 200, 240])
    bottom = np.array([8, 34, 92])
    rgb = top * (1 - depth[..., None]) ** 1.6 + bottom * (1 - (1 - depth[..., None]) ** 1.6)
    # shafts of light from the surface, slanting
    for sx, wdt, k in ((-3.6, 0.5, 0.9), (-1.9, 0.8, 0.7), (0.4, 0.45, 1.0), (2.1, 0.7, 0.8), (3.7, 0.4, 0.6)):
        u = x - (sx + (WATER_Y - y) * 0.35)
        shaft = np.exp(-(u / wdt) ** 2) * (1 - depth) ** 0.7 * k
        rgb += shaft[..., None] * np.array([40, 80, 90])
    # far rock silhouettes along the bottom
    ridge = 0.33 + 0.55 + 0.25 * np.sin(x * 1.3) + 0.18 * np.sin(x * 3.1 + 1) + 0.1 * np.sin(x * 7.3)
    rock = y < ridge
    rgb = np.where(rock[..., None], rgb * 0.45 + np.array([4, 10, 26]), rgb)
    # a far school, as dark flecks
    rng = np.random.default_rng(3)
    for _ in range(70):
        fx = rng.normal(1.2, 1.1)
        fy = rng.normal(2.1, 0.25)
        m = ((x - fx) / 0.07) ** 2 + ((y - fy) / 0.025) ** 2 < 1
        rgb = np.where(m[..., None], rgb * 0.62, rgb)
    # above the water line: the tank's dark wall, with the surface's bright edge
    air = y > WATER_Y
    rgb = np.where(air[..., None], np.array([14, 24, 44]), rgb)
    line = np.abs(y - WATER_Y) < 0.035
    rgb = np.where(line[..., None], np.array([150, 230, 250]), rgb)
    return to_image(rgb, 4.0)


def paint_sand(w=200, h=40):
    # the big tank's floor seen from above: x in [-4.85, 4.85], z from its back (top row) to its front
    z0, z1 = ZBO - 0.1, TANK_Z1 + TANK_WALL + 0.03
    xs = -TANK_BASE_X + (np.arange(w) + 0.5) / w * 2 * TANK_BASE_X
    zs = z1 - (np.arange(h) + 0.5) / h * (z1 - z0)
    x, z = np.meshgrid(xs, zs)
    rng = np.random.default_rng(11)
    grain = rng.random((h, w))
    rgb = np.zeros((h, w, 3)) + np.array([52, 96, 128])
    rgb += (grain - 0.5)[..., None] * np.array([18, 20, 22])
    rgb += WATER_CAUS_MEAN * np.array([40, 80, 90])     # agent W: the net moves (aq_water's overlay)
    ripple = np.sin(x * 9 + np.sin(z * 4) * 1.5) * 0.5 + 0.5
    rgb += (ripple * 0.15)[..., None] * np.array([30, 40, 40])
    return to_image(rgb, 5.0)


def paint_ripple(n=32):
    # the water surface's shimmer, added in quarter blend: black adds nothing
    xs = (np.arange(n) + 0.5) / n * 2 * math.pi
    x, z = np.meshgrid(xs, xs)
    v = (np.sin(x + np.sin(z * 2) * 0.8) + np.sin(z * 2 + np.sin(x) * 1.2 + 1) + np.sin((x + z) + 2)) / 3
    c = np.clip(1 - np.abs(v) * 2.4, 0, 1) ** 2
    rgb = np.array([6, 24, 44]) + c[..., None] * np.array([90, 140, 160])
    return to_image(rgb, 0)


def paint_kelp(w=16, h=64):
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for yy in range(h):
        cx = w / 2 + math.sin(yy / 9.0) * 3.0
        half = 2.2 + 1.6 * math.sin(yy / 5.0 + 1) ** 2
        shade = 0.55 + 0.45 * (1 - yy / h)
        col = (int(40 * shade), int(150 * shade), int(120 * shade), 255)
        d.line([(cx - half, yy), (cx + half, yy)], fill=col)
        if yy % 7 == 3:   # floats
            d.point((cx + half + 1, yy), fill=(120, 200, 140, 255))
    return img


def paint_disc(w, inner, outer, ring=None):
    xs = (np.arange(w) + 0.5) / w * 2 - 1
    x, y = np.meshgrid(xs, xs)
    d = np.hypot(x, y)
    rgb = np.array(outer) * smoothstep(0.0, 1.0, d)[..., None] + np.array(inner) * (1 - smoothstep(0.0, 1.0, d))[..., None]
    if ring is not None:
        rgb += np.exp(-((d - 0.82) / 0.06) ** 2)[..., None] * np.array(ring)
    return rgb


def paint_column_light():
    return to_image(paint_disc(32, (210, 235, 255), (40, 80, 150), (90, 140, 190)), 4.0)


def paint_porthole():
    rgb = paint_disc(32, (60, 190, 210), (10, 60, 110))
    img = to_image(rgb, 3.0)
    d = ImageDraw.Draw(img)
    # a seahorse, in silhouette
    col = (12, 40, 70)
    d.ellipse([13, 6, 19, 11], fill=col)
    d.polygon([(18, 8), (23, 9), (18, 10)], fill=col)
    d.line([(15, 11), (14, 15), (15, 19), (17, 22), (16, 25), (13, 25), (13, 23)], fill=col, width=3)
    d.line([(13, 14), (11, 17)], fill=col, width=1)
    return img


def text_sign(size, bg, lines):
    """A sign drawn with the repository's OFL fonts, hard-edged (no antialiasing)."""
    img = Image.new('RGB', size, bg)
    d = ImageDraw.Draw(img)
    d.fontmode = '1'
    for text, fname, fsize, colour, y in lines:
        f = font(fname, fsize)
        tw = d.textlength(text, font=f)
        d.text(((size[0] - tw) / 2, y), text, font=f, fill=colour)
    return img


def paint_wall_tank():
    w, h = 32, 18
    ys = (np.arange(h) + 0.5) / h
    rgb = np.zeros((h, w, 3)) + (np.array([70, 200, 220]) * (1 - ys[:, None, None]) + np.array([12, 60, 110]) * ys[:, None, None])
    img = to_image(rgb, 3.0)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=(14, 22, 40))
    d.rectangle([1, h - 4, w - 2, h - 2], fill=(150, 140, 100))                 # gravel
    for px in (5, 11, 25):                                                      # weed
        d.line([(px, h - 4), (px + 1, h - 10)], fill=(40, 150, 90))
    for (fx, fy, col) in ((8, 6, (250, 220, 120)), (18, 9, (240, 110, 150)), (23, 5, (250, 220, 120)),
                          (14, 4, (200, 240, 255))):
        d.rectangle([fx, fy, fx + 2, fy + 1], fill=col)
        d.point((fx - 1, fy), fill=col)
    return img


def paint_exit():
    img = Image.new('RGB', (32, 12), (30, 170, 80))
    d = ImageDraw.Draw(img)
    white = (230, 255, 235)
    d.rectangle([21, 1, 29, 10], outline=white)          # the door
    d.ellipse([9, 1, 12, 4], fill=white)                 # a running figure
    d.line([(10, 4), (8, 7), (5, 8)], fill=white)
    d.line([(8, 7), (11, 9), (10, 11)], fill=white)
    d.line([(9, 5), (13, 6), (15, 4)], fill=white)
    d.line([(8, 7), (6, 11)], fill=white)
    return img


def paint_quar_sign():
    img = text_sign((48, 12), (210, 220, 232), [('QUARANTINE', 'Figtree-Bold.ttf', 9, (30, 50, 90), 0)])
    return img


# ---- the room

def room_recipe():
    m = {
        'floor': {'color': '#1a2a48', 'class': 'emissive',
                  'texture': {'image': 'art/floor.png', 'bits': 8, 'projection': 'fit'}},
        'slab': {'color': '#2a3550'},
        'cut': {'color': '#3c475e', 'class': 'emissive'},   # the section's cut faces: unlit, quiet, as on a model
        'wall_in': {'color': '#6a7ca0'},
        'wall_tank': {'color': '#30a0c0', 'class': 'emissive',
                      'texture': {'image': 'art/wall_tank.png', 'bits': 4, 'projection': 'fit'}},
        'wall_face': {'color': '#56688a'},    # the window wall, lit only from the room
        'sill': {'color': '#2a3650'},
        'sill_glow': {'color': '#2a9ad0', 'class': 'emissive'},
        'header': {'color': '#9ad8f0', 'class': 'emissive',
                   'texture': {'image': 'art/header.png', 'bits': 8, 'projection': 'fit'}},
        'door_head': {'color': '#c8e4ff', 'class': 'emissive'},   # a light strip under the lintel
        'service_floor': {'color': '#707880'},
        'service_wall': {'color': '#7c8590'},
        'tube': {'color': '#eef6ff', 'class': 'emissive'},
        'pipe': {'color': '#7a8a94'},
        'doorway_dark': {'color': '#06080c', 'class': 'emissive'},
        'quar_sign': {'color': '#e0e8f0', 'class': 'emissive',
                      'texture': {'image': 'art/quar_sign.png', 'bits': 4, 'projection': 'fit'}},
        'passage_floor': {'color': '#5a5470'},
        'passage_wall': {'color': '#4a4664'},
        'glow_strip': {'color': '#9a70ff', 'class': 'emissive'},
        'exit': {'color': '#30b060', 'class': 'emissive',
                 'texture': {'image': 'art/exit.png', 'bits': 4, 'projection': 'fit'}},
        'exit_box': {'color': '#d8e0e0'},
        'porthole': {'color': '#40b0d0', 'class': 'emissive',
                     'texture': {'image': 'art/porthole.png', 'bits': 4, 'projection': 'disc', 'axis': 'y'}},
        'brass': {'color': '#b0a070'},
        'pillar': {'color': '#7484a4'},
        'bench_top': {'color': '#66768e'},
        'bench_leg': {'color': '#3a4458'},
        'rope': {'color': '#6a5ab0'},
        'sign_face': {'color': '#c8b8f0', 'class': 'emissive',
                      'texture': {'image': 'art/sign_column.png', 'bits': 8, 'projection': 'fit'}},
        'sign_body': {'color': '#3a4460'},
        'cart_body': {'color': '#8aa0b8'},
        'cart_dark': {'color': '#3a4a60'},
        'bucket': {'color': '#4ac0b8'},
        'mop': {'color': '#c8d0dc'},
    }
    n = []
    # the floor slab: its top is the painted floor, its front the section through the floor
    n.append(box('slab', [-SLAB_X, -SLAB, SLAB_Z], [SLAB_X, 0, ZBO], 'slab', faces={'top': 'floor', 'back': 'cut'},
                 open=['front']))
    # side walls, full height; their tops are the section's cut
    # and small wall tanks set into them, glowing (decals: the face's right is +Z on the left wall's
    # inner face, -Z on the right wall's)
    zc, yc = (ZF - 0.05 + ZBO - 0.05) / 2, (H - 0.02) / 2
    for s, name in ((-1, 'wall_left'), (1, 'wall_right')):
        x0, x1 = sorted((s * XI, s * SIDE_OUT))
        decals = [{'id': f'tank_{k}', 'face': 'right' if s < 0 else 'left', 'material': 'wall_tank',
                   'at': [r(-s * (z - zc)), r(1.3 - yc)], 'size': [1.1, 0.62]}
                  for k, z in enumerate(WALL_TANKS)]
        n.append(box(name, [x0, -0.02, ZF - 0.05], [x1, H, ZBO - 0.05], 'wall_in', open=['bottom'],
                     faces={'top': 'cut'}, decals=decals))
    # the front wall, cut at 1 m, with the way in
    n.append(box('front_left', [-XO, -0.02, ZFO], [ENTRY[0], CUT, ZF], 'wall_in', open=['bottom'],
                 faces={'top': 'cut', 'back': 'cut'}))
    n.append(box('front_right', [ENTRY[1], -0.02, ZFO], [XO, CUT, ZF], 'wall_in', open=['bottom'],
                 faces={'top': 'cut', 'back': 'cut'}))
    # the window wall: two piers, a sill and a header recessed 3 cm, the glass between
    top = H + 0.04
    left = box('pier_left', [-XO, -0.02, ZB], [-WIN_X, top, ZBO], 'wall_face', open=['bottom'],
               faces={'top': 'cut'})
    n.append(left)
    # the right pier with the staff door open in it (PLAN.md's exit), a lintel over the doorway,
    # recessed 4 cm as the sill and header are
    n.append(box('pier_right', [WIN_X, -0.02, ZB], [DOOR_X[0], top, ZBO], 'wall_face', open=['bottom'],
                 faces={'top': 'cut'}))
    n.append(box('pier_east', [DOOR_X[1], -0.02, ZB], [XO, top, ZBO], 'wall_face', open=['bottom'],
                 faces={'top': 'cut'}))
    n.append(box('lintel', [DOOR_X[0] - 0.02, DOOR_H, ZB + 0.04], [DOOR_X[1] + 0.02, top - 0.04, ZBO - 0.04],
                 'wall_face', faces={'top': 'cut', 'bottom': 'door_head'}))
    # beyond it, the service corridor to quarantine: plain floor and walls, a tube light, pipes,
    # and at its end the door through (dark) under its sign
    n.append(box('corridor_floor', [4.86, -SLAB, ZBO], [XO + 0.02, 0, CORRIDOR_Z1 + 0.05], 'service_floor',
                 open=['bottom', 'back']))
    n.append(box('corridor_wall', [XI, -0.02, ZBO - 0.03], [SIDE_OUT, H, CORRIDOR_Z1 + 0.02], 'service_wall',
                 open=['bottom'], faces={'top': 'cut'}))
    end_cx = (4.84 + SIDE_OUT - 0.03) / 2
    n.append(box('corridor_end', [4.84, -0.02, CORRIDOR_Z1], [SIDE_OUT - 0.03, H - 0.03, CORRIDOR_Z1 + 0.25], 'service_wall',
                 open=['bottom'], faces={'top': 'cut'},
                 decals=[{'id': 'way_through', 'face': 'back', 'material': 'doorway_dark',
                          'at': [r(5.42 - end_cx), r(1.0 - (H - 0.05) / 2)], 'size': [0.8, 1.98]},
                         {'id': 'sign', 'face': 'back', 'material': 'quar_sign',
                          'at': [r(5.42 - end_cx), r(2.32 - (H - 0.05) / 2)], 'size': [0.84, 0.22]}]))
    n.append(box('corridor_tube', [XI - 0.06, 2.45, 3.45], [XI + 0.02, 2.52, 4.6], 'tube'))
    for k, py in enumerate((2.62, 2.78)):
        n.append(box(f'corridor_pipe_{k}', [4.86, py, ZBO + 0.05], [4.94, py + 0.08, CORRIDOR_Z1 - 0.01], 'pipe'))
    # beyond the way in, the end of the jellyfish gallery: a dark passage lit violet, cut at 1 m
    n.append(box('passage_floor', [ENTRY[0] - 0.28, -SLAB, PASSAGE_Z0], [ENTRY[1] + 0.28, 0, SLAB_Z],
                 'passage_floor', open=['bottom', 'front']))
    for k, (x0, x1) in enumerate(((ENTRY[0] - 0.25, ENTRY[0] - 0.02), (ENTRY[1] + 0.02, ENTRY[1] + 0.25))):
        n.append(box(f'passage_wall_{k}', [x0, -0.02, PASSAGE_Z0 + 0.03], [x1, CUT - 0.03, ZFO + 0.02], 'passage_wall',
                     open=['bottom'], faces={'top': 'cut', 'back': 'cut'}))
        gx0, gx1 = (x1 - 0.03, x1 + 0.03) if k == 0 else (x0 - 0.03, x0 + 0.03)
        n.append(box(f'passage_glow_{k}', [gx0, -0.01, PASSAGE_Z0 + 0.05], [gx1, 0.05, ZFO - 0.05], 'glow_strip'))
    n.append(box('sill', [-WIN_X - 0.02, -0.02, ZB + 0.04], [WIN_X + 0.02, WIN_Y0, ZBO - 0.04], 'sill',
                 open=['bottom'], faces={'top': 'sill'},
                 decals=[{'id': 'glow', 'face': 'back', 'material': 'sill_glow', 'at': [0, 0.17],
                          'size': [2 * WIN_X - 0.1, 0.05]}]))
    header = box('header', [-WIN_X - 0.02, WIN_Y1, ZB + 0.04], [WIN_X + 0.02, top - 0.04, ZBO - 0.04],
                 'wall_face', faces={'top': 'cut'},
                 decals=[{'id': 'name', 'face': 'back', 'material': 'header', 'at': [0, 0],
                          'size': [3.2, 0.36]}])
    n.append(header)
    # exit sign over the staff door, and the seahorse porthole on the left pier
    n.append(box('exit_sign', [5.25 - 0.22, 2.24, ZB - 0.07], [5.25 + 0.22, 2.40, ZB + 0.05], 'exit_box',
                 faces={'back': 'exit'}))
    n.append(at({'id': 'porthole', 'op': 'cylinder', 'radius': 0.3, 'height': 0.12, 'segments': 12,
                 'material': 'brass', 'faces': {'bottom': 'porthole'}},
                translate=[-5.15, 1.5, ZB - 0.02], rotate=[90, 0, 0]))
    # the pillar
    px, pz = PILLAR
    h = PILLAR_S / 2
    # cut at 1 m like everything in the play area (PLAN.md), so the thief stays in sight behind it
    n.append(box('pillar', [px - h, -0.02, pz - h], [px + h, CUT, pz + h], 'pillar', open=['bottom'],
                 faces={'top': 'cut'}))
    # the bench: a long seat on three legs
    bx, bz = BENCH
    n.append(box('bench_seat', [bx - BENCH_W / 2, 0.40, bz - 0.24], [bx + BENCH_W / 2, 0.48, bz + 0.24],
                 'bench_top'))
    for k, lx in enumerate((-BENCH_W / 2 + 0.25, 0.0, BENCH_W / 2 - 0.25)):
        n.append(box(f'bench_leg_{k}', [bx + lx - 0.05, -0.02, bz - 0.2], [bx + lx + 0.05, 0.42, bz + 0.2],
                     'bench_leg', open=['bottom', 'top']))
    # stanchions and ropes before the glass
    posts = []
    for k, sx in enumerate(STANCHION_X):
        posts.append(box(f'post_{k}', [sx - 0.03, 0.02, STANCHION_Z - 0.03], [sx + 0.03, 0.92, STANCHION_Z + 0.03],
                         'brass', open=['bottom']))
        posts.append(box(f'foot_{k}', [sx - 0.11, -0.02, STANCHION_Z - 0.11], [sx + 0.11, 0.035, STANCHION_Z + 0.11],
                         'brass', open=['bottom']))
    for k in range(len(STANCHION_X) - 1):
        a, b = STANCHION_X[k], STANCHION_X[k + 1]
        posts.append(box(f'rope_{k}', [a + 0.02, 0.80, STANCHION_Z - 0.02], [b - 0.02, 0.85, STANCHION_Z + 0.02],
                         'rope', open=['left', 'right']))
    n.append({'id': 'stanchions', 'op': 'group', 'children': posts})
    # the column's lightbox, tilted up toward the visitor
    sx, sz = SIGN
    n.append(box('sign_post', [sx - 0.04, -0.02, sz - 0.04], [sx + 0.04, 0.82, sz + 0.04], 'sign_body',
                 open=['bottom']))
    n.append(at({'id': 'sign_panel', 'op': 'box', 'size': [0.44, 0.32, 0.06], 'material': 'sign_body',
                 'faces': {'back': 'sign_face'}}, translate=[sx, 0.92, sz], rotate=[50, 0, 0]))
    # the night cleaner's cart: a trolley, a bucket, a mop leaning on it
    cx, cz = CART
    cart = [box('cart_base', [cx - 0.42, 0.08, cz - 0.22], [cx + 0.42, 0.16, cz + 0.22], 'cart_body'),
            box('cart_shelf', [cx - 0.42, 0.62, cz - 0.22], [cx + 0.42, 0.68, cz + 0.22], 'cart_body'),
            box('cart_frame', [cx + 0.36, -0.02, cz - 0.2], [cx + 0.40, 0.95, cz + 0.2], 'cart_dark',
                open=['bottom']),
            box('cart_bin', [cx - 0.38, 0.15, cz - 0.18], [cx + 0.02, 0.61, cz + 0.18], 'cart_dark',
                open=['bottom', 'top']),
            at({'id': 'bucket', 'op': 'cylinder', 'radius': 0.15, 'height': 0.26, 'segments': 8,
                'material': 'bucket'}, translate=[cx + 0.15, 0.80, cz]),
            at({'id': 'mop', 'op': 'cylinder', 'radius': 0.02, 'height': 1.3, 'segments': 4, 'caps': False,
                'material': 'mop'}, translate=[cx - 0.26, 0.62, cz - 0.05], rotate=[0, 0, -18])]
    n.append({'id': 'cart', 'op': 'group', 'children': cart})
    lighting = {'direction': ROOM_DIRECTION, 'ambient': ROOM_AMBIENT, 'diffuse': ROOM_DIFFUSE,
                'lights': kit_lights(), 'refine': ROOM_REFINE}
    return recipe('aq_room', m, n, lighting, {'vertices': 2048, 'triangles': 1200})


# ---- the tanks

def fish_mesh(b, centre, heading, length, width, colour=None, tail=True):
    """A flat diamond fish, seen from above (double-sided), swimming along heading (degrees)."""
    cx, cy, cz = centre
    c, s = math.cos(math.radians(heading)), math.sin(math.radians(heading))

    def p(u, w):
        return (cx + u * c - w * s, cy, cz + u * s + w * c)
    L, W = length / 2, width / 2
    b.poly([p(L, 0), p(0.1 * L, W), p(-0.55 * L, 0), p(0.1 * L, -W)], (0, 1, 0), colour)
    if tail:
        b.poly([p(-0.55 * L, 0), p(-L * 1.05, W * 0.9), p(-L * 1.05, -W * 0.9)], (0, 1, 0), colour)


def tanks_recipe():
    m = {
        'cut': {'color': '#3c475e', 'class': 'emissive'},
        'lid': {'color': '#121826', 'class': 'emissive'},   # the building beyond the room, in shadow
        'window_glass': {'color': '#2a78b8', 'blend': 'add'},   # the void's colour: nothing beyond the section
        'tank_wall': {'color': '#163056'},
        'backdrop': {'color': '#2a80c0', 'class': 'emissive',
                     'texture': {'image': 'art/tank_back.png', 'bits': 8, 'projection': 'fit'}},
        'sand': {'color': '#5090a8', 'class': 'emissive',
                 'texture': {'image': 'art/sand.png', 'bits': 8, 'projection': 'fit'}},
        'base': {'color': '#0e1830'},
        'surface': {'color': '#3080b0', 'blend': 'quarter',     # agent W: the ripple moves
                    'texture': wateranim.texture(WATER_RIPPLE)},
        'rock': {'color': '#34506e'},
        'rock_dark': {'color': '#223a58'},
        'kelp': {'color': '#2a9a7a', 'double_sided': True,
                 'texture': {'image': 'art/kelp.png', 'bits': 4, 'projection': 'fit'}},
        'fish': {'color': '#b8d8f0', 'double_sided': True},
        'fish_blue': {'color': '#4a7ae8', 'double_sided': True},
        'fish_gold': {'color': '#e8d050', 'double_sided': True},
        'shell': {'color': '#6a7a50', 'smooth': True},
        'turtle_skin': {'color': '#8a9a78', 'double_sided': True},
        'manta': {'color': '#1c2a40', 'double_sided': True},
        'shark': {'color': '#5a7090', 'double_sided': True},
        'shaft': {'color': '#3a78a8', 'blend': 'add'},
        'plinth': {'color': '#141c34'},
        'column_light': {'color': '#b0d0f0', 'class': 'emissive',
                         'texture': {'image': 'art/column_light.png', 'bits': 4, 'projection': 'disc', 'axis': 'y'}},
        'column_glass': {'color': '#0e2848', 'blend': 'add', 'double_sided': True},   # lit glass: the shoal keeps its contrast
        'column_surface': {'color': '#4a80c0', 'blend': 'quarter',     # agent W: the ripple moves
                           'texture': wateranim.texture(WATER_RIPPLE)},
        'sardine': {'color': '#e4eef8', 'double_sided': True},
        'rim': {'color': '#2a3450'},
        'bubble': {'color': '#8090c0', 'blend': 'add', 'double_sided': True},
        'cube_glass': {'color': '#2a8898', 'blend': 'half', 'double_sided': True},
        'cube_base': {'color': '#16243c'},
        'reef_sand': {'color': '#7aa0a8'},
        'coral_pink': {'color': '#d070a8', 'smooth': True},
        'coral_violet': {'color': '#9a5ad8'},
        'fan': {'color': '#c04aa8', 'double_sided': True},
        'anemone': {'color': '#5ad0b0', 'smooth': True},
    }
    n = []
    # the big tank: its floor, walls and backdrop, behind the window wall
    n.append(box('tank_base', [-TANK_BASE_X, -SLAB, ZBO - 0.1], [TANK_BASE_X, SAND_Y, TANK_Z1 + TANK_WALL + 0.03], 'base',
                 faces={'top': 'sand'}, open=['bottom']))
    n.append(box('tank_back', [-4.85, SAND_Y - 0.02, TANK_Z1], [4.85, H + 0.02, TANK_Z1 + TANK_WALL], 'tank_wall',
                 open=['bottom'], faces={'back': 'backdrop', 'top': 'cut'}))
    for s, name in ((-1, 'tank_left'), (1, 'tank_right')):
        x0, x1 = sorted((s * TANK_X, s * 4.84))
        n.append(box(name, [x0, SAND_Y - 0.02, ZBO - 0.15], [x1, H, TANK_Z1 + 0.02], 'tank_wall',
                     open=['bottom'], faces={'top': 'cut'}))
    # the tank's lid: the building beyond the back wall, cut at the same plane as the walls, so the
    # tank shows only through its window (open, its top read as a second window). A dark mass, not
    # the void's colour: the game's void is dithered, and may become a night sky
    n.append(box('tank_lid', [-TANK_BASE_X - 0.02, H - 0.01, ZB + 0.22], [TANK_BASE_X + 0.02, H + 0.06,
                                                                         TANK_Z1 + TANK_WALL + 0.06],
                 'lid'))
    # the ocean window's glass, in this recipe so that the room's lights do not light it: it adds
    # the tank's glow to what is behind it
    g = MeshBuilder()
    gz = ZB + 0.12
    g.poly([(-WIN_X - 0.01, WIN_Y0 - 0.04, gz), (WIN_X + 0.01, WIN_Y0 - 0.04, gz),
            (WIN_X + 0.01, WIN_Y1 + 0.04, gz), (-WIN_X - 0.01, WIN_Y1 + 0.04, gz)], (0, 0, -1))
    n.append(g.node('window_glass', 'window_glass'))
    # rock work along the back and the corners
    rocks = []
    for k, (x, z, sx, sy, sz, mat) in enumerate((
            (-3.9, 4.15, 0.75, 0.95, 0.5, 'rock'), (-3.1, 4.30, 0.55, 0.55, 0.38, 'rock_dark'),
            (-0.9, 4.35, 0.9, 0.5, 0.35, 'rock'), (1.0, 4.28, 0.5, 0.8, 0.4, 'rock_dark'),
            (3.6, 4.10, 0.85, 1.25, 0.55, 'rock'), (2.6, 4.35, 0.45, 0.45, 0.3, 'rock_dark'),
            (-2.0, 3.85, 0.35, 0.22, 0.28, 'rock'))):
        rocks.append(at({'id': f'rock_{k}', 'op': 'sphere', 'radius': 1.0, 'rings': 4, 'segments': 7,
                         'material': mat}, translate=[x, SAND_Y + sy * 0.55, z], scale=[sx, sy, sz],
                        rotate=[0, (k * 23) % 30 - 15, 0]))
    n.append({'id': 'rocks', 'op': 'group', 'children': rocks})
    # kelp, crossed cut-out blades
    kelp = MeshBuilder()
    for k, (x, z, hgt) in enumerate(((-4.2, 3.80, 2.3), (-3.5, 3.95, 1.9), (-2.6, 4.10, 2.45), (2.2, 3.90, 2.0),
                                     (3.0, 3.75, 2.4), (4.15, 3.60, 1.7), (-0.2, 4.15, 1.6))):
        wdt = 0.32
        y0, y1 = SAND_Y - 0.03, SAND_Y + hgt
        kelp.poly([(x - wdt / 2, y1, z), (x + wdt / 2, y1, z), (x + wdt / 2, y0, z), (x - wdt / 2, y0, z)], (0, 0, -1))
    n.append(kelp.node('kelp', 'kelp'))
    # the animals: a school of silver fish in an arc, a turtle, a ray, a few blue and gold fish
    school = MeshBuilder()
    for k in range(28):
        t = k / 28
        ang = -40 + t * 220
        rad = 1.15 + 0.25 * math.sin(k * 2.3)
        x = -0.6 + rad * 1.6 * math.cos(math.radians(ang))
        z = 3.85 + rad * 0.45 * math.sin(math.radians(ang))
        y = 1.55 + 0.35 * math.sin(k * 1.7) + t * 0.4
        fish_mesh(school, (x, y, z), ang + 90, 0.24, 0.08)
    for k, (x, y, z, hdg, mat) in enumerate(((2.9, 1.2, 3.5, 200, 'fish_blue'), (3.3, 1.35, 3.65, 195, 'fish_blue'),
                                            (-3.0, 1.05, 3.45, 10, 'fish_gold'), (0.8, 0.95, 3.4, 170, 'fish_blue'))):
        fish_mesh(school, (x, y, z), hdg, 0.42, 0.18, mat)
    for k in range(9):                       # a second, looser school near the glass
        x = -3.4 + k * 0.8 + 0.25 * math.sin(k * 3.1)
        fish_mesh(school, (x, 1.25 + 0.3 * math.sin(k * 1.9), ZBO + 0.35 + 0.2 * math.cos(k * 2.3)),
                  180 + 15 * math.sin(k), 0.3, 0.1)
    n.append(school.node('school', 'fish'))
    turtle = [at({'id': 'shell', 'op': 'sphere', 'radius': 1.0, 'rings': 4, 'segments': 8, 'material': 'shell'},
                 translate=[1.7, 1.95, 3.85], scale=[0.5, 0.14, 0.38], rotate=[0, -15, 0])]
    tm = MeshBuilder()
    hx, hy, hz = 1.7, 1.95, 3.85
    tm.poly([(hx - 0.5, hy, hz - 0.08), (hx - 0.72, hy, hz - 0.04), (hx - 0.74, hy, hz + 0.06),
             (hx - 0.52, hy, hz + 0.1)], (0, 1, 0))                                   # head
    for sxn, szn in ((-1, -1), (-1, 1)):                                              # front flippers
        tm.poly([(hx - 0.22, hy, hz + szn * 0.3), (hx - 0.05, hy, hz + szn * 0.33),
                 (hx - 0.42, hy - 0.05, hz + szn * 0.6)], (0, 1, 0))
    for szn in (-1, 1):                                                               # back flippers
        tm.poly([(hx + 0.32, hy, hz + szn * 0.2), (hx + 0.42, hy, hz + szn * 0.18),
                 (hx + 0.55, hy, hz + szn * 0.4)], (0, 1, 0))
    turtle.append(tm.node('turtle_limbs', 'turtle_skin'))
    n.append({'id': 'turtle', 'op': 'group', 'children': turtle})
    ray = MeshBuilder()
    rx, ry, rz = -2.3, 2.45, 4.0
    pts = [(rx - 0.55, ry, rz), (rx - 0.1, ry + 0.06, rz + 0.25), (rx + 0.05, ry + 0.02, rz + 0.6),
           (rx + 0.3, ry, rz), (rx + 0.05, ry + 0.02, rz - 0.6), (rx - 0.1, ry + 0.06, rz - 0.25)]
    for a in range(1, 5):
        ray.poly([pts[0], pts[a], pts[a + 1]], (0, 1, 0))
    ray.poly([pts[0], pts[5], pts[1]], (0, 1, 0))
    ray.poly([(rx + 0.25, ry, rz - 0.02), (rx + 0.95, ry - 0.05, rz), (rx + 0.25, ry, rz + 0.02)], (0, 1, 0))
    n.append(ray.node('ray', 'manta'))
    # a reef shark cruising along the glass: a long body, a dorsal fin standing up, a tall tail
    shark = MeshBuilder()
    sx0, sy, sz = 0.6, 1.55, ZBO + 0.45
    body = [(sx0 + 0.85, sy, sz), (sx0 + 0.2, sy + 0.04, sz + 0.17), (sx0 - 0.55, sy + 0.02, sz + 0.07),
            (sx0 - 0.55, sy + 0.02, sz - 0.07), (sx0 + 0.2, sy + 0.04, sz - 0.17)]
    for k in range(1, 4):
        shark.poly([body[0], body[k], body[k + 1]], (0, 1, 0))
    shark.poly([(sx0 + 0.25, sy + 0.17, sz - 0.25), (sx0 - 0.05, sy - 0.02, sz + 0.4), (sx0 + 0.05, sy, sz)],
               (0, 1, 0))                                                     # pectoral fins
    shark.poly([(sx0 + 0.25, sy + 0.17, sz + 0.25), (sx0 + 0.05, sy, sz), (sx0 - 0.05, sy - 0.02, sz - 0.4)],
               (0, 1, 0))
    shark.poly([(sx0 + 0.25, sy + 0.03, sz), (sx0 - 0.05, sy + 0.03, sz), (sx0 - 0.1, sy + 0.3, sz)], (0, 0, -1))
    shark.poly([(sx0 - 0.5, sy + 0.02, sz), (sx0 - 0.85, sy + 0.32, sz), (sx0 - 0.78, sy - 0.18, sz)], (0, 0, -1))
    n.append(shark.node('shark', 'shark'))
    # light shafts falling through the water
    shafts = MeshBuilder()
    for (sx, wdt, z) in ((-3.0, 0.5, 4.35), (-1.0, 0.75, 4.45), (0.9, 0.45, 4.30), (2.6, 0.6, 4.40)):
        top_y, bot_y = WATER_Y - 0.02, SAND_Y + 0.1
        lean = 0.6
        shafts.poly([(sx - wdt / 2, top_y, z), (sx + wdt / 2, top_y, z),
                     (sx + wdt / 2 + lean, bot_y, z - 0.35), (sx - wdt / 2 + lean, bot_y, z - 0.35)], (0, 0.3, -1))
    n.append(shafts.node('shafts', 'shaft'))

    # the glass column: a shoal of sardines turning round its light (the jellyfish are the gallery's)
    jx, jz = COLUMN
    jelly = [at({'id': 'plinth', 'op': 'cylinder', 'radius': 0.76, 'height': 0.64, 'segments': 16,
                 'material': 'plinth', 'faces': {'top': 'column_light'}}, translate=[jx, 0.30, jz]),
             at({'id': 'column_glass', 'op': 'cylinder', 'radius': COLUMN_R, 'height': 1.74, 'segments': 16,
                 'caps': False, 'material': 'column_glass'}, translate=[jx, 0.61 + 0.87, jz]),
             at({'id': 'column_rim', 'op': 'lathe', 'profile': [[0.77, 0.0], [0.77, 0.1], [0.66, 0.13]],
                 'segments': 16, 'caps': False, 'material': 'rim'}, translate=[jx, 2.32, jz])]
    js = MeshBuilder()
    ring = [(jx + 0.73 * math.cos(math.tau * i / 16), 2.24, jz + 0.73 * math.sin(math.tau * i / 16)) for i in range(16)]
    js.poly(ring, (0, 1, 0))
    jelly.append(js.node('column_surface', 'column_surface'))
    shoal = MeshBuilder()
    for k in range(60):                      # a helix: three turns, wider in the middle, each fish on its tangent
        t = k / 60
        ang = t * 3 * 360 + 23 * math.sin(k * 1.7)
        rad = 0.22 + 0.3 * math.sin(math.pi * t) + 0.04 * math.sin(k * 2.9)
        y = 0.82 + t * 1.25 + 0.05 * math.sin(k * 3.3)
        fx = jx + rad * math.cos(math.radians(ang))
        fz = jz + rad * math.sin(math.radians(ang))
        fish_mesh(shoal, (fx, y, fz), ang + 90, 0.22, 0.07)
    jelly.append(shoal.node('sardines', 'sardine'))
    bub = MeshBuilder()
    for k in range(7):                       # a stream of bubbles from the plinth's light
        by = 0.75 + k * 0.21
        bx = jx + 0.04 * math.sin(k * 2.0)
        sz = 0.035 + 0.008 * (k % 3)
        bub.poly([(bx - sz, by, jz - 0.35), (bx, by + sz, jz - 0.35), (bx + sz, by, jz - 0.35), (bx, by - sz, jz - 0.35)],
                 (0, 0, -1))
    jelly.append(bub.node('bubbles', 'bubble'))
    n.append({'id': 'column', 'op': 'group', 'children': jelly})

    # the coral cube
    cx, cz = CUBE
    hs = CUBE_S / 2
    cube = [box('cube_base', [cx - 0.74, -0.02, cz - 0.74], [cx + 0.74, 0.72, cz + 0.74], 'cube_base',
                open=['bottom'], faces={'top': 'reef_sand'}),
            box('cube_glass', [cx - hs, 0.70, cz - hs], [cx + hs, 1.80, cz + hs], 'cube_glass',
                open=['bottom', 'top'])]
    cs = MeshBuilder()
    cs.poly([(cx - hs + 0.01, 1.70, cz - hs + 0.01), (cx + hs - 0.01, 1.70, cz - hs + 0.01),
             (cx + hs - 0.01, 1.70, cz + hs - 0.01), (cx - hs + 0.01, 1.70, cz + hs - 0.01)], (0, 1, 0))
    cube.append(cs.node('cube_surface', 'surface'))
    cube.append(at({'id': 'brain', 'op': 'sphere', 'radius': 1.0, 'rings': 4, 'segments': 7, 'material': 'coral_pink'},
                   translate=[cx - 0.25, 0.78, cz + 0.2], scale=[0.3, 0.2, 0.28]))
    cube.append(at({'id': 'anemone', 'op': 'sphere', 'radius': 1.0, 'rings': 3, 'segments': 6, 'material': 'anemone'},
                   translate=[cx + 0.3, 0.78, cz - 0.25], scale=[0.2, 0.12, 0.2]))
    for k, (dx, dz, hgt, lean) in enumerate(((0.25, 0.3, 0.55, 12), (0.4, 0.15, 0.4, -15), (0.1, 0.42, 0.45, 20),
                                              (-0.4, -0.3, 0.5, -10), (-0.2, -0.4, 0.35, 15))):
        cube.append(at({'id': f'staghorn_{k}', 'op': 'cone', 'radius': 0.05, 'height': hgt, 'segments': 4,
                        'caps': False, 'material': 'coral_violet'},
                       translate=[cx + dx, 0.7 + hgt / 2, cz + dz], rotate=[lean, k * 40, -lean]))
    fan = MeshBuilder()
    fx, fz = cx - 0.1, cz + 0.5
    fpts = [(fx - 0.05, 0.71, fz)] + [(fx + 0.4 * math.cos(math.radians(a)), 0.75 + 0.5 * math.sin(math.radians(a)), fz)
                                      for a in (160, 130, 100, 70, 40, 20)]
    for a in range(1, len(fpts) - 1):
        fan.poly([fpts[0], fpts[a], fpts[a + 1]], (0, 0, -1))
    fish_mesh(fan, (cx - 0.2, 1.3, cz - 0.15), 30, 0.2, 0.11, 'fish_gold')
    fish_mesh(fan, (cx + 0.25, 1.15, cz + 0.05), 210, 0.22, 0.1, 'fish_blue')
    cube.append(fan.node('sea_fan', 'fan'))
    n.append({'id': 'coral_cube', 'op': 'group', 'children': cube})
    jx, jz = COLUMN
    lighting = {'direction': [0.15, 1.0, -0.35], 'ambient': 0.45, 'diffuse': 0.45,
                'lights': [{'id': 'column', 'at': [jx, 0.75, jz], 'color': '#c0dcff', 'intensity': 1.8, 'range': 1.9},
                           {'id': 'coral', 'at': [cx, 1.6, cz], 'color': '#5af0d8', 'intensity': 1.4, 'range': 1.3}],
                'refine': {'max_added': 0}}       # corners only: refining here split the glass
    return recipe('aq_tanks', m, n, lighting, {'vertices': 2048, 'triangles': 1500})


# ---- agent W: the moving water (NOTES_W.md). The caustic net the window throws on the floor, on
# the tank's sand and up its back wall: grey tiles added over them, lit only by lights of their
# own (ambient 0), so the net is as bright and as blue as the window's light where it falls

WATER_CAUS_MEAN = 0.12      # what the floor and the sand keep of the still net they had (its mean is 0.16)
WATER_RIPPLE = wateranim.key('w_ripple', '#5ab0e8')
WATER_Y_UP = 0.03           # the overlay over the floor (the cones are 3 cm up too)


def water_recipe():
    m = {'floor_caustic': wateranim.material('w_caustic'),
         'sand_caustic': wateranim.material('w_caustic', scale=1.0),
         'back_caustic': wateranim.material('w_caustic', axis='z', scale=[2.0, 1.0])}
    n = []
    # the floor in front of the window: four strips, so that the light's corners follow its pool
    f = MeshBuilder()
    zs = (-1.4, 0.2, 1.5, ZB - 0.02)
    xs = (-XI + 0.02, -WIN_X, -1.5, 1.5, WIN_X, XI - 0.02)
    for i in range(len(xs) - 1):
        for j in range(len(zs) - 1):
            f.poly([(xs[i], WATER_Y_UP, zs[j]), (xs[i + 1], WATER_Y_UP, zs[j]), (xs[i + 1], WATER_Y_UP, zs[j + 1]),
                    (xs[i], WATER_Y_UP, zs[j + 1])], (0, 1, 0))
    n.append(f.node('floor_net', 'floor_caustic'))
    # the tank's sand, seen through the window
    sd = MeshBuilder()
    sy = SAND_Y + 0.02
    for (a, b) in ((-TANK_X + 0.01, 0.0), (0.0, TANK_X - 0.01)):
        sd.poly([(a, sy, ZBO + 0.02), (b, sy, ZBO + 0.02), (b, sy, TANK_Z1 - 0.02), (a, sy, TANK_Z1 - 0.02)], (0, 1, 0))
    n.append(sd.node('sand_net', 'sand_caustic'))
    # the tank's back wall, the net strongest high up, under the surface
    bk = MeshBuilder()
    bz = TANK_Z1 - 0.02
    for (a, b) in ((-TANK_X + 0.01, 0.0), (0.0, TANK_X - 0.01)):
        bk.poly([(b, SAND_Y + 0.05, bz), (a, SAND_Y + 0.05, bz), (a, WATER_Y - 0.05, bz), (b, WATER_Y - 0.05, bz)],
                (0, 0, -1))
    n.append(bk.node('back_net', 'back_caustic'))
    lights = [{'id': f'window_{k}', 'at': [x, 1.4, ZB - 0.9], 'color': '#58b8ff', 'intensity': 1.2, 'range': 4.0}
              for k, x in enumerate((-3.3, -1.1, 1.1, 3.3))]
    lights += [{'id': f'surface_{k}', 'at': [x, WATER_Y + 0.6, 3.8], 'color': '#70d0ff', 'intensity': 1.3,
                'range': 3.6} for k, x in enumerate((-2.4, 2.4))]
    lighting = {'ambient': 0.0, 'diffuse': 0.0, 'lights': lights, 'refine': {'tolerance': 20, 'max_added': 48}}
    rec = recipe('aq_water', m, n, lighting, {'vertices': 400, 'triangles': 200})
    return wateranim.finish(rec, ART)


# ---- the stand-ins

def figure(prefix, colours, cap=False):
    """A blocky person 1.7 m tall facing -Z, feet at y = 0."""
    body, dark, skin = colours
    n = [box(f'{prefix}_leg_l', [-0.17, 0.0, -0.09], [-0.03, 0.82, 0.09], dark),
         box(f'{prefix}_leg_r', [0.03, 0.0, -0.09], [0.17, 0.82, 0.09], dark),
         box(f'{prefix}_torso', [-0.23, 0.80, -0.13], [0.23, 1.42, 0.13], body),
         box(f'{prefix}_arm_l', [-0.33, 0.78, -0.07], [-0.21, 1.38, 0.07], body),
         box(f'{prefix}_arm_r', [0.21, 0.78, -0.07], [0.33, 1.38, 0.07], body),
         at({'id': f'{prefix}_head', 'op': 'sphere', 'radius': 1.0, 'rings': 4, 'segments': 8, 'material': skin},
            translate=[0, 1.555, 0], scale=[0.13, 0.145, 0.13])]
    if cap:
        n.append(at({'id': f'{prefix}_cap', 'op': 'cylinder', 'radius': 0.15, 'height': 0.09, 'segments': 8,
                     'material': 'cap'}, translate=[0, 1.655, 0]))
        n.append(box(f'{prefix}_peak', [-0.1, 1.62, -0.24], [0.1, 1.645, -0.1], 'cap'))
    return n


def blob_shadow(id):
    b = MeshBuilder()
    ring = [(0.36 * math.cos(math.tau * i / 10), 0.02, 0.3 * math.sin(math.tau * i / 10)) for i in range(10)]
    b.poly(ring, (0, 1, 0))
    return b.node(id, 'shadow')


def thief_recipe():
    m = {'suit': {'color': '#ff5a1e'}, 'suit_dark': {'color': '#e0400c'}, 'hood': {'color': '#ff6a2c'},
         'shadow': {'color': '#0a0c10', 'blend': 'sub'}}
    n = figure('thief', ('suit', 'suit_dark', 'hood'))
    n.append(blob_shadow('thief_shadow'))
    return recipe('standin_thief', m, n, {'direction': [-0.2, 1.0, 0.6], 'ambient': 0.62},
                  {'vertices': 256, 'triangles': 200})


def guard_recipe():
    m = {'uniform': {'color': '#8a9cbc'}, 'trousers': {'color': '#2a3650'}, 'skin': {'color': '#d8b8a0'},
         'cap': {'color': '#202c48'}, 'shadow': {'color': '#0a0c10', 'blend': 'sub'},
         'torch': {'color': '#fff0b0', 'class': 'emissive'}}
    n = figure('guard', ('uniform', 'trousers', 'skin'), cap=True)
    n.append(box('torch', [0.22, 1.0, -0.32], [0.31, 1.08, -0.06], 'torch'))
    n.append(blob_shadow('guard_shadow'))
    return recipe('standin_guard', m, n, {'direction': [-0.2, 1.0, 0.6], 'ambient': 0.55},
                  {'vertices': 256, 'triangles': 250})


# ---- the sight cone: a fan on the floor, cut by the walls and the pillar (not by glass)

def wall_segments():
    px, pz = PILLAR
    h = PILLAR_S / 2
    segs = [((-XI, ZF), (XI, ZF)), ((XI, ZF), (XI, ZB)), ((XI, ZB), (-XI, ZB)), ((-XI, ZB), (-XI, ZF)),
            ((px - h, pz - h), (px + h, pz - h)), ((px + h, pz - h), (px + h, pz + h)),
            ((px + h, pz + h), (px - h, pz + h)), ((px - h, pz + h), (px - h, pz - h))]
    return segs


def ray_hit(ox, oz, dx, dz, length):
    best = length
    for (ax, az), (bx, bz) in wall_segments():
        ex, ez = bx - ax, bz - az
        den = dx * ez - dz * ex
        if abs(den) < 1e-9:
            continue
        t = ((ax - ox) * ez - (az - oz) * ex) / den
        u = ((ax - ox) * dz - (az - oz) * dx) / den
        if 0 <= u <= 1 and 0 < t < best:
            best = t
    return best


def cone_points(origin, heading, length):
    ox, oz = origin
    pts = []
    for k in range(CONE_RAYS + 1):
        a = math.radians(heading - CONE_FOV / 2 + CONE_FOV * k / CONE_RAYS)
        dx, dz = math.cos(a), math.sin(a)
        t = ray_hit(ox, oz, dx, dz, length)
        pts.append((ox + dx * t, oz + dz * t))
    return pts


def cone_recipe():
    m = {'cone': {'color': '#fff2a8', 'blend': 'half'}}
    b = MeshBuilder()
    for k, w in enumerate(WATCHERS):
        y = 0.03 + 0.01 * k          # each fan in its own plane: where two overlap they would be coplanar
        ox, oz = w['at']
        pts = cone_points(w['at'], w['heading'], w['length'])
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            b.poly([(ox, y, oz), (ax, y, az), (bx, y, bz)], (0, 1, 0))
    return recipe('sight_cone', m, [b.node('fans', 'cone')], {'bake': False},
                  {'vertices': 128, 'triangles': 64})


# ---- the textures

def draw_art():
    ART.mkdir(exist_ok=True)
    paint_floor().save(ART / 'floor.png')
    paint_tank_back().save(ART / 'tank_back.png')
    paint_sand().save(ART / 'sand.png')
    paint_ripple().save(ART / 'ripple.png')
    paint_kelp().save(ART / 'kelp.png')
    paint_column_light().save(ART / 'column_light.png')
    paint_porthole().save(ART / 'porthole.png')
    paint_exit().save(ART / 'exit.png')
    paint_wall_tank().save(ART / 'wall_tank.png')
    paint_quar_sign().save(ART / 'quar_sign.png')
    text_sign((128, 14), (10, 26, 52), [
        ('OCEAN WINDOW', 'Figtree-Bold.ttf', 10, (150, 220, 245), 1)]).save(ART / 'header.png')
    text_sign((48, 32), (18, 34, 66), [
        ('イワシ', 'ZenMaruGothic-Medium.ttf', 14, (225, 240, 255), 1),
        ('SARDINES', 'Figtree-Bold.ttf', 8, (170, 200, 240), 20)]).save(ART / 'sign_column.png')


def main():
    draw_art()
    write('aq_room', room_recipe())
    write('aq_tanks', wateranim.finish(tanks_recipe(), ART))      # agent W: its surfaces' ripple tile
    write('aq_water', water_recipe())                                 # agent W
    write('standin_thief', thief_recipe())
    write('standin_guard', guard_recipe())
    write('sight_cone', cone_recipe())
    # where the level places the room's recipes (PLAN.md, "How the room joins the level"): the
    # shell with the level lead's collision, aq_col; the tanks without (they are out of play)
    placements = {'format': 'after-hours-placements', 'version': 1, 'room': 'aquarium', 'placements': [
        {'id': 'r5_room_shell', 'asset': 'aq_room', 'position': [0, 0, 0], 'collision': 'aq_col'},
        {'id': 'r5_tanks', 'asset': 'aq_tanks', 'position': [0, 0, 0], 'collision': 'none'},
        {'id': 'r5_water', 'asset': 'aq_water', 'position': [0, 0, 0], 'collision': 'none'}]}     # agent W
    (HERE / 'aquarium.placements.json').write_text(json.dumps(placements, indent=1) + '\n')
    print('wrote', ', '.join(sorted(p.name for p in HERE.glob('*.asset.json'))), 'and', len(list(ART.glob('*.png'))),
          'textures in', ART.relative_to(ROOT))


if __name__ == '__main__':
    main()
