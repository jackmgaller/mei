#!/usr/bin/env python3
"""Shrine town grey box, the mountain region (rows 4 and 5: z 256-384).

Writes, from the level's plan (layout.py, the single source of coordinates and heights):

- carts/garden/shrinetown/assets/greybox/mountain/gbm_*.asset.json   the grey-box recipes
- carts/garden/shrinetown/cells/c{0..4}_{4,5}.cell.json             this region's cells
- carts/garden/shrinetown/parts/mountain.json                       world-level entries
- carts/garden/shrinetown/parts/mountain.heights.txt                the ground of these rows

    python3 carts/garden/shrinetown/assets/greybox/mountain/make_mountain.py --layout PATH/layout.py

Every structure is boxes at its final footprint, height and collision, in flat colours. Where
this region changes the plan (a height, a position, a shape that did not work in 3D) the change
is made here, named in a comment, and listed in notes/mountain.md for the connector.
"""
import argparse
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOWN = HERE.parents[2]                       # carts/garden/shrinetown
REGION = 'mountain'
Z0, Z1 = 256, 384                            # this region's rows
SPACING = 2

ap = argparse.ArgumentParser()
ap.add_argument('--layout', default=os.environ.get('SHRINETOWN_LAYOUT', str(TOWN / 'layout.py')),
                help='the level plan, layout.py (default: carts/garden/shrinetown/layout.py)')
args = ap.parse_args()
spec = importlib.util.spec_from_file_location('layout', args.layout)
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)

r2 = lambda v: round(v, 3)

# ---------------------------------------------------------------------------------- colours
C = {
    'pagoda': '#a03c2e', 'roof': '#3a3c44', 'gold': '#d8b048', 'trunk': '#5a4636',
    'cedar': '#2e4a30', 'cedar2': '#3c5a34', 'maple': '#b8502e', 'sacred': '#24382a',
    'sacred_trunk': '#6a4632', 'wood': '#96683f', 'deck': '#b08a5e', 'stage': '#aa7c50',
    'hall': '#8a6446', 'red': '#c43026', 'torii': '#e0502a', 'rock': '#6e6a62',
    'rock2': '#85807a', 'dead': '#9a9086', 'white': '#eee8d6', 'water': '#5a96dc',
    'bamboo': '#a8b860', 'bamboo2': '#8a9a48', 'plaster': '#e8e2d2', 'tile': '#5a6068',
    'rope': '#c8b88a', 'marker': '#e02080', 'stone': '#97928a',
}

# ---------------------------------------------------------------------------------- ground
# The plan's height function, with the changes this region makes (notes/mountain.md, "Changes"):
# under the stage the ground is the mountain's slope (layout.height() returns the deck's 60 there,
# which would make the stage a solid block instead of a deck on stilts).
def base_height(x, z):
    if L.in_rect(x, z, L.STAGE): return L.mountain(x, z)
    return L.height(x, z)

def smooth(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)

def area_dist(area, x, z):
    """Distance outside the area (0 inside), for the falloff of set operations."""
    if 'rect' in area:
        x0, z0, x1, z1 = area['rect']
        dx = max(x0 - x, 0, x - x1); dz = max(z0 - z, 0, z - z1)
        return math.hypot(dx, dz)
    if 'circle' in area:
        cx, cz, r = area['circle']
        return max(0.0, math.hypot(x - cx, z - cz) - r)
    if 'polygon' in area:
        pts = area['polygon']
        inside = False
        for (ax, az), (bx, bz) in zip(pts, pts[1:] + pts[:1]):
            if (az > z) != (bz > z) and x < ax + (z - az) * (bx - ax) / (bz - az): inside = not inside
        if inside: return 0.0
        return min(L.seg_dist(x, z, a, b) for a, b in zip(pts, pts[1:] + pts[:1]))
    raise ValueError(area)

OPS = []                                     # the field's operations in this region, in order
def op(**o): OPS.append(o); return o

def gnd(x, z):
    """The ground after this region's set/carve/fill operations (not the beds of paths): what
    the generator stands boxes on. The kit's own floor is the truth (mei_world.py floor)."""
    h = base_height(x, z)
    for o in OPS:
        if o['op'] not in ('set', 'carve', 'fill'): continue
        d = area_dist(o['area'], x, z); f = o.get('falloff', 0)
        if d > f or (d > 0 and f == 0): continue
        w = 1.0 if d == 0 else 1 - smooth(d / f)
        t = o['height']
        if o['op'] == 'set': h = h + (t - h) * w
        elif o['op'] == 'carve' and h > t: h = h + (t - h) * w
        elif o['op'] == 'fill' and h < t: h = h + (t - h) * w
    return h

def gmin(x0, z0, x1, z1, step=1.0):
    n = max(1, int(max(x1 - x0, z1 - z0) / step))
    return min(gnd(x0 + (x1 - x0) * i / n, z0 + (z1 - z0) * j / n) for i in range(n + 1) for j in range(n + 1))

# ---- the region's terrain operations (absolute heights; order matters)
# Stage hall: a level pad at the deck's height (the slope behind the deck is 60-63).
op(op='set', area={'rect': [138, 354, 170, 377]}, height=60.0, falloff=3)
# Rope ladder A's ledge: a flat shelf at 44 cut into the cliff band in front of the stage. Its
# south edge is a sheer face over the basin's north rim (the plan's slope at 24 m is not
# walkable: the basin's rim rises 11 m in 6 m there).
# Each flat cut into the slope is a cliff sheet first (vertical faces at its edges, so poles
# and walls stand on real floors), then set to its height. The ledge runs under the stage's
# front edge (z 340) so the ladder up the front stilts starts on it.
# With the cliff-top path east along the foot of the stage to the falls' lip (the back mountain's
# face is 40-42 degrees from z 316 to 356: no walking on it), the ledge is an L.
LEDGE = [[146, 318], [162, 318], [162, 334], [206, 334], [206, 342], [146, 342]]
FLATS = []
def flat(area, h):
    FLATS.append(area)                                         # each its own sheet (offset), then levelled
    op(op='cliff', area=area, height=0.01 * len(FLATS), material='rock')
    op(op='set', area=area, height=h)
flat({'polygon': LEDGE}, 44.0)
# Rope ladder A hangs plumb, 20 m (the real forest_rope_ladder; owner, 2026-10-05): its foot is a
# shelf at 24 cut into the slope (x 148-160, z 314-318), the ledge's south face above it sheer
# from 24 to 44 at z 318 (not on the row seam at z 320, where the body passed through the face), so foot and top are at the same x and z. Steps climb to the shelf from
# the basin floor (ladder_a_steps).
LADDER_SHELF = [148, 314, 160, 318]
flat({'rect': LADDER_SHELF}, 24.0)
# The falls pool's west terrace at 16 (the chimney's foot), and the chimney's slot floor.
SHELF = [[186, 306], [206, 306], [206, 334], [194, 334], [194, 322], [186, 322]]
flat({'polygon': SHELF}, 16.0)
# The cave behind the falls: floor 14, roofed by gbm_falls_cave (17.5 to the lip at 48).
flat({'rect': [206, 330, 222, 344]}, 14.0)
# Shortcut C's landing: the rock shelf above the falls pool (226, 318) at 20.
op(op='set', area={'circle': [226, 318, 4]}, height=20.0, falloff=2)
# The falls pool, 0.8 m deep.
op(op='carve', area={'circle': [L.FALLS_POOL[0], L.FALLS_POOL[1], 6.5]}, height=11.2, falloff=1.5)

# ---------------------------------------------------------------------------------- assets
ASSETS = {}

def box_nodes(boxes, origin):
    """boxes: (x0, y0, z0, x1, y1, z1, colour key, open sides) in world coordinates."""
    ox, oy, oz = origin
    nodes = []
    for i, b in enumerate(boxes):
        x0, y0, z0, x1, y1, z1, col = b[:7]
        n = {'id': f'b{i}', 'op': 'box', 'size': [r2(x1 - x0), r2(y1 - y0), r2(z1 - z0)], 'material': col,
             'transform': {'translate': [r2((x0 + x1) / 2 - ox), r2((y0 + y1) / 2 - oy), r2((z0 + z1) / 2 - oz)]}}
        if len(b) > 7 and b[7]: n['open'] = list(b[7])
        nodes.append(n)
    return nodes

def asset(name, boxes, origin=(0, 0, 0), lod=None, collision=None, tags=None, budget=None, extra_nodes=None):
    """A recipe of boxes. lod: [(distance, boxes)], cull; collision: boxes for a companion
    NAME_col (None: the asset is its own collision)."""
    def mats(bxs):
        return sorted({b[6] for b in bxs})
    used = set(mats(boxes))
    for d, bx in (lod or {}).get('levels', []): used |= set(mats(bx))
    materials = {m: {'color': C[m]} for m in sorted(used)}
    for m, t in (tags or {}).items(): materials[m]['tag'] = t
    r = {'format': 'mei-asset', 'version': 1, 'name': name,
         'materials': materials, 'lighting': {'mode': 'vertical', 'ambient': 0.5},
         'nodes': box_nodes(boxes, origin) + (extra_nodes or [])}
    if budget: r['budget'] = budget
    if lod:
        r['lod'] = {'levels': [{'distance': d, 'nodes': box_nodes(bx, origin)} for d, bx in lod['levels']]}
        if lod.get('cull'): r['lod']['cull'] = lod['cull']
    ASSETS[name] = r
    if collision is not None:
        cm = sorted({b[6] for b in collision})
        ASSETS[name + '_col'] = {'format': 'mei-asset', 'version': 1, 'name': name + '_col',
                                 'materials': {m: {'color': C[m], **({'tag': tags[m]} if tags and m in tags else {})} for m in cm},
                                 'lighting': {'mode': 'vertical', 'ambient': 0.5},
                                 'nodes': box_nodes(collision, origin)}
        return name + '_col'
    return 'self'

def cube(cx, cz, half, y0, y1, col, op_=None, hz=None):
    hz = half if hz is None else hz
    return (cx - half, y0, cz - hz, cx + half, y1, cz + hz, col, op_)

# ---------------------------------------------------------------------------------- cells
CELLS = {}
def cell_of(x, z): return f'c{int(x // 64)}_{int(z // 64)}'
def place(pid, name, pos, collision, yaw=None, layer=None):
    c = cell_of(pos[0], pos[2])
    assert c.endswith('_4') or c.endswith('_5'), (pid, pos)
    p = {'id': pid, 'asset': name, 'position': [r2(v) for v in pos], 'collision': collision}
    if yaw is not None: p['yaw'] = r2(yaw)
    if layer: p['layer'] = layer
    CELLS.setdefault(c, {'placements': [], 'entities': []})['placements'].append(p)
def entity(eid, typ, pos, params=None, layer=None, yaw=None):
    c = cell_of(pos[0], pos[2])
    assert c.endswith('_4') or c.endswith('_5'), (eid, pos)
    e = {'id': eid, 'type': typ, 'position': [r2(v) for v in pos]}
    if yaw is not None: e['yaw'] = yaw
    if params: e['params'] = params
    if layer: e['layer'] = layer
    CELLS.setdefault(c, {'placements': [], 'entities': []})['entities'].append(e)
def coin(eid, x, y, z): entity(eid, 'coin', (x, y, z))

PATHS = {}
NOTES = []                                   # measurements written into notes (glides, gaps)

# ================================================================== 3.8 the ridge and the pagoda
PX, PZ = L.PAGODA
# The pagoda is the shrine's real one, reused (owner, 2026-10-05): its tiers are 3.6 m apart, not
# the plan's 4.8. Its climbing collision is arch_pagoda_town_col (assets/arch_pagoda, made from the
# render's own roofs): eave tops at 5.0 / 8.6 / 12.2 / 15.8 / 19.4 above the base, eave half widths
# 5.4 / 4.7 / 4.0 / 3.3 / 2.6, each roof a 0.7 m strip outside the eave above at 27.9 degrees, roof
# 5 rising to the dew basin's flat top at 21.19. The grey box draws that same solid in a flat
# colour (gbm_pagoda) and collides with it; the finial is a pole from the dew basin, 8.8 m.
PAG_EAVE_TOP = [5.0, 8.6, 12.2, 15.8, 19.4]
PAG_EAVE_HALF = [5.4, 4.7, 4.0, 3.3, 2.6]
PAG_ROBAN, PAG_FINIAL = 21.19, 8.8
PB = L.PAG_BASE
_col = json.loads((TOWN / 'assets' / 'arch_pagoda' / 'arch_pagoda_town_col.asset.json').read_text())
_body = dict(_col['nodes'][0], material='pagoda')
_body.pop('face_materials', None)
def _tier_boxes():
    out, y0 = [], -0.3
    for i in range(5):
        out.append(cube(0, 0, PAG_EAVE_HALF[i] - 0.3, y0, PAG_EAVE_TOP[i], 'pagoda' if i % 2 == 0 else 'roof',
                        ['bottom'] if i == 0 else None))
        y0 = PAG_EAVE_TOP[i] - 0.02
    return out
ASSETS['gbm_pagoda'] = {'format': 'mei-asset', 'version': 1, 'name': 'gbm_pagoda',
                        'materials': {'pagoda': {'color': C['pagoda']}, 'roof': {'color': C['roof']}, 'gold': {'color': C['gold']}},
                        'lighting': {'mode': 'vertical', 'ambient': 0.5},
                        'nodes': [_body] + box_nodes([cube(0, 0, 0.25, PAG_ROBAN - 0.02, PAG_ROBAN + PAG_FINIAL, 'gold')], (0, 0, 0)),
                        'lod': {'levels': [{'distance': 90, 'nodes': box_nodes(_tier_boxes() + [cube(0, 0, 0.25, PAG_EAVE_TOP[4] - 0.02, PAG_ROBAN + PAG_FINIAL, 'gold')], (0, 0, 0))},
                                           {'distance': 120, 'nodes': box_nodes([cube(0, 0, PAG_EAVE_HALF[0] - 0.6, -0.3, PAG_EAVE_TOP[4], 'roof', ['bottom']),
                                                                                cube(0, 0, 0.25, PAG_EAVE_TOP[4] - 0.02, PAG_ROBAN + PAG_FINIAL, 'gold', ['bottom'])], (0, 0, 0))}]}}
place('pagoda', 'gbm_pagoda', (PX, PB, PZ), 'arch_pagoda_town_col')
entity('pole_pagoda_finial', 'pole', (PX, PB + PAG_ROBAN, PZ), {'height': PAG_FINIAL})
STRIP_RISE = 0.35 * math.tan(math.radians(27.9))
for i in range(5):
    coin(f'coin_pagoda_{i + 1}', PX - (PAG_EAVE_HALF[i] - 0.35), PB + PAG_EAVE_TOP[i] + STRIP_RISE + 1.0, PZ)   # on each roof's west strip

# The kick pair (star 1, approach 2). layout.py has one cedar 3 m south of the pagoda's wall
# (KICK_CEDAR, in the core region's row); the first roof's eave reaches to 1.2 m of it, so the
# shaft is closed at 23.8. Built here as the spec says: two cedars west of the pagoda, trunks
# face to face 3.2 m apart, here north-south at x 168 (z 259.5 and 264.5).
# Trunk faces 1.05 m from roof 2's west eave line (x 171.35; roof 1's eave passes 0.35 m east of
# them): after the fourth kick the stick carries the body east onto roof 2 (a kick itself goes back
# and forth between the faces, north and south).
KICK_X = PX - PAG_EAVE_HALF[1] - 1.05 - 0.9
KICK = [(KICK_X, 259.5), (KICK_X, 264.5)]
for k, (kx, kz) in enumerate(KICK):
    g = gmin(kx - 0.9, kz - 0.9, kx + 0.9, kz + 0.9)
    # Trunks to 34.5 and crowns 34-38 (from the terrace at 15, four good kicks reach 31.9, the head 33.5):
    # the glides G6 and G8 pass over them (spec: cedars of 25-41 m would stand in their way).
    trunk = cube(kx, kz, 0.9, g - 0.5, 34.5, 'trunk', ['bottom'])
    can = cube(kx - 0.6, kz, 1.6, 34.0, 38.0, 'cedar', ['bottom'])      # crowns 34-38: over the kicks' reach (head 33.5), under the glides G6 (about 42 here) and G8 (43.9)
    name = f'gbm_cedar_kick_{k}'
    place(f'kick_cedar_{k}', name, (kx, g, kz), asset(name, [trunk, can], (kx, g, kz), collision=[trunk]))
entity('camera_kick_pair', 'camera_zone', (KICK_X, L.PAG_BASE, 262.0), {'size': [6, 20, 3.2], 'mode': 'fixed', 'look': [1, 0, 0]})

# ================================================================== 3.9 treetop walkway (rows 4)
DECK6 = L.DECKS[5]            # (114, 264, 22)
ROPE_DECK = L.DECKS[6]        # (130, 282, 24)
def deck_tree(name, x, z, h, canopy=True):
    g = gmin(x - 0.8, z - 0.8, x + 0.8, z + 0.8)
    trunk = cube(x, z, 0.8, g - 0.5, h + 14, 'trunk', ['bottom'])
    deck = cube(x, z, 3.0, h - 0.6, h, 'deck')
    bx = [trunk, deck]
    if canopy: bx.append(cube(x, z, 4.5, h + 7, h + 17, 'cedar2', ['bottom']))
    return place(name, f'gbm_{name}', (x, g, z), asset(f'gbm_{name}', bx, (x, g, z), collision=[trunk, deck]))
deck_tree('deck_6', *DECK6)
deck_tree('deck_rope', *ROPE_DECK)
coin('coin_deck_6', DECK6[0] + 1.5, DECK6[2] + 1.0, DECK6[1] + 1.5)
coin('coin_deck_rope', ROPE_DECK[0] - 1.5, ROPE_DECK[2] + 1.0, ROPE_DECK[1] - 1.5)

PLANK = [[-0.8, -0.12], [-0.8, 0.0], [0.8, 0.0], [0.8, -0.12], [-0.8, -0.12]]
def rope_bridge(name, a, b, sag=0.6, n=5):
    """A plank sweep from a to b ((x, y, z) each) sagging in the middle, with two hand ropes."""
    pts = []
    for i in range(n):
        t = i / (n - 1)
        pts.append([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t - sag * 4 * t * (1 - t), a[2] + (b[2] - a[2]) * t])
    PATHS[name] = {'points': [[r2(v) for v in p] for p in pts], 'raised': True,
                   'sweep': {'profile': PLANK, 'material': 'planks'}}
    dx, dz = b[0] - a[0], b[2] - a[2]; d = math.hypot(dx, dz); nx, nz = dz / d, -dx / d
    for side, s in (('l', -1), ('r', 1)):
        PATHS[f'{name}_{side}'] = {'points': [[r2(p[0] + s * 0.85 * nx), r2(p[1] + 1.0 + 0.4 * (abs(t - 0.5) * 2)), r2(p[2] + s * 0.85 * nz)]
                                              for p, t in zip(pts, [i / (n - 1) for i in range(n)])],
                                   'raised': True,
                                   'sweep': {'profile': [[0.0, -0.05], [0.0, 0.05]], 'material': 'rope', 'double_sided': True, 'collision': False}}
# (Deck 5 to deck 6 is the core region's bridge, core_walkway_56, which runs the whole way.)
# Deck 6 to the rope deck (24 m, 2 m up).
rope_bridge('bridge_deck6_rope', (DECK6[0] + 2.4, DECK6[2] - 0.05, DECK6[1] + 2.4),
            (ROPE_DECK[0] - 2.4, ROPE_DECK[2] - 0.05, ROPE_DECK[1] - 2.4), sag=0.5)

# ================================================================== 3.10 the sacred cedar (star 4)
CX, CZ = L.CEDAR
BF = L.BASIN[3]                               # basin floor 13
OUT, IN = 3.5, 2.0                            # trunk half width, shaft half width (4 m shaft)
SILL, HOLE_TOP, CAP = 21.5, 23.7, 24.5        # the knot hole 1.4 x 2.2 at 21.5; the shaft's roof
HZ0, HZ1 = 294.3, 295.7                       # the hole's z (faces west, towards the rope deck)
DZ0, DZ1 = 294.6, 297.4                       # the root door's z (west foot), 3.1 m tall
x0, x1, z0, z1 = CX - OUT, CX + OUT, CZ - OUT, CZ + OUT
xi0, xi1, zi0, zi1 = CX - IN, CX + IN, CZ - IN, CZ + IN
yb = BF - 0.5
ced = [
    (x0, yb, z0, x1, CAP, zi0, 'sacred_trunk', ['bottom']),            # south wall
    (x0, yb, zi1, x1, CAP, z1, 'sacred_trunk', ['bottom']),            # north wall
    (xi1, yb, zi0 - 0.02, x1, CAP, zi1 + 0.02, 'sacred_trunk', ['bottom']),  # east wall
    # west wall in bands round the root door (13-16.1) and the knot hole (21.5-23.7)
    (x0, yb, zi0 - 0.02, xi0, BF + 3.1, DZ0, 'sacred_trunk', ['bottom']),
    (x0, yb, DZ1, xi0, BF + 3.1, zi1 + 0.02, 'sacred_trunk', ['bottom']),
    (x0, BF + 3.08, zi0 - 0.02, xi0, SILL, zi1 + 0.02, 'sacred_trunk'),
    (x0, SILL - 0.02, zi0 - 0.02, xi0, HOLE_TOP + 0.02, HZ0, 'sacred_trunk'),
    (x0, SILL - 0.02, HZ1, xi0, HOLE_TOP + 0.02, zi1 + 0.02, 'sacred_trunk'),
    (x0, HOLE_TOP, zi0 - 0.02, xi0, CAP, zi1 + 0.02, 'sacred_trunk'),
    (x0 + 0.01, CAP - 0.02, z0 + 0.01, x1 - 0.01, 45.0, z1 - 0.01, 'sacred_trunk'),   # solid above the shaft
    (x0 - 1.2, HOLE_TOP, HZ0 - 0.4, x0 + 0.02, CAP + 0.3, HZ1 + 0.4, 'trunk'),     # the bark lip, 1.2 m deep
]
canopy = [cube(CX, CZ, 9.0, 30.0, 45.0, 'sacred', ['bottom']), cube(CX, CZ, 6.0, 44.98, 54.0, 'sacred', ['bottom']),
          cube(CX, CZ, 3.0, 53.98, BF + 45.8, 'sacred', ['bottom'])]
place('sacred_cedar', 'gbm_cedar_hollow', (CX, BF, CZ),
      asset('gbm_cedar_hollow', ced + canopy, (CX, BF, CZ), collision=ced,
            lod={'levels': [(60, [(x0, yb, z0, x1, 45.0, z1, 'sacred_trunk', ['bottom'])] + canopy)]}))
# The root curtain (shortcut D): solid from outside until pounded from inside; in layer
# root_d_shut, on at the start (the game switches it off when D is open).
curtain = (x0 - 0.2, yb, DZ0 - 0.02, xi0 + 0.1, BF + 3.1, DZ1 + 0.02, 'gold', ['bottom'])
place('root_curtain', 'gbm_root_curtain', (x0 - 0.05, BF, CZ), asset('gbm_root_curtain', [curtain], (x0 - 0.05, BF, CZ)),
      layer='root_d_shut')
# The rope: from 1.75 m above the rope deck (hands overhead, feet on the deck) to 1.2 m short of
# the knot hole, 1.75 m above its sill: hang along it, hang-jump in (spec: 24 -> 21.5 is the
# feet's line). A rail entity names it; it is hang only because it is overhead.
rope_a = (ROPE_DECK[0] + 2.4, ROPE_DECK[2] + 1.75, ROPE_DECK[1] + 1.4)
# The rope ends in the knot hole, 0.5 m into the trunk's wall under the hole's top: the body
# hanging at its end is in the opening, so letting go puts the feet on the sill. (Ending 1.2 m
# short, as first built, a hang jump from it bumped the lip and fell short: scenario 423.)
rope_b = (x0 + 0.5, SILL + 1.75, (HZ0 + HZ1) / 2)
PATHS['cedar_rope'] = {'points': [[r2(v) for v in rope_a], [r2(v) for v in rope_b]], 'raised': True,
                       'sweep': {'profile': [[0.0, -0.06], [0.0, 0.06]], 'material': 'rope', 'double_sided': True, 'collision': False}}
# Hang only (lead's decision, alpha fix): a body dropping onto it from a glide ground along it into
# the knot hole (DESIGN.md 12.9); a hang rail is never ground, nor caught falling past. And caught
# only in its first 3 m, at the rope deck: wall kicks up the trunk from the basin caught its end in
# the knot hole (the explorer bot: shortcut D bypassed).
entity('rail_cedar_rope', 'rail', rope_a, {'path': 'cedar_rope', 'hang': True, 'catch': 3.0})

# ================================================================== 3.11 fox grove, torii tunnel
FX, FZ = L.FOX[:2]
# The fox shrine moved 6 m west of the plan's (86-94, 304-310): the tunnel's first leg runs up
# x 92-94 there.
g = gmin(80, 304, 88, 310)
place('fox_shrine', 'gbm_fox_shrine', (84, g, 307), asset('gbm_fox_shrine',
      [(80, g - 0.5, 304, 88, L.FOX[3] + 3.0, 310, 'red', ['bottom']), (79, L.FOX[3] + 2.98, 303, 89, L.FOX[3] + 4.4, 311, 'roof')], (84, g, 307)))
for k, (sx, sz) in enumerate(((91.2, 298.6), (96.8, 298.6))):
    gg = gnd(sx, sz)
    place(f'fox_statue_{k}', 'gbm_fox_statue', (sx, gg, sz), asset('gbm_fox_statue',
          [cube(sx, sz, 0.4, gg - 0.3, gg + 1.4, 'white', ['bottom'])], (sx, gg, sz)))

# The torii steps: the plan's switchbacks with a steady grade from the grove (15) to the landing
# (54.5), 86 m at 24.6 degrees as a stair sweep. layout.py's terrain along the line is not a
# steady grade (one leg rises 13.6 m in 14 m); the stair's bed cuts and fills it.
SEN = L.SENBON
LEN = L.poly_len(SEN)
y_s, y_e = L.FOX[3], 54.5
acc = 0.0; spts = []
for i, p in enumerate(SEN):
    if i: acc += math.hypot(p[0] - SEN[i - 1][0], p[1] - SEN[i - 1][1])
    spts.append([p[0], y_s + (y_e - y_s) * acc / LEN, p[1]])
PATHS['torii_steps'] = {'points': [[r2(v) for v in p] for p in spts],
                        'sweep': {'profile': [[-2.4, -1.2], [-1.5, 0], [1.5, 0], [2.4, -1.2]],
                                  'materials': ['earth', 'steps', 'earth'], 'caps': True, 'stairs': {'rise': 0.3}}}
torii_frame = [(-1.75, -0.6, -0.15, -1.45, 3.32, 0.15, 'torii', ['bottom']),
               (1.45, -0.6, -0.15, 1.75, 3.32, 0.15, 'torii', ['bottom']),
               (-2.0, 3.3, -0.15, 2.0, 3.6, 0.15, 'torii')]
torii_far = [(-1.75, -0.6, -0.15, -1.45, 3.32, 0.15, 'torii', ['bottom', 'top', 'left', 'right']),
             (1.45, -0.6, -0.15, 1.75, 3.32, 0.15, 'torii', ['bottom', 'top', 'left', 'right']),
             (-2.0, 3.3, -0.15, 2.0, 3.6, 0.15, 'torii', ['bottom'])]
asset('gbm_fox_torii', torii_frame, (0, 0, 0), lod={'levels': [(24, torii_far)], 'cull': 60})
n_torii = 0; acc = 0.0; tcoins = 0
for i in range(len(spts) - 1):
    a, b = spts[i], spts[i + 1]
    seg = math.hypot(b[0] - a[0], b[2] - a[2])
    yaw = math.degrees(math.atan2(b[0] - a[0], b[2] - a[2]))
    d = 1.6
    while d < seg - 1.6:
        tt = d / seg
        x, z = a[0] + (b[0] - a[0]) * tt, a[2] + (b[2] - a[2]) * tt
        y = a[1] + (b[1] - a[1]) * tt
        n_torii += 1
        place(f'torii_{n_torii:02d}', 'gbm_fox_torii', (x, y, z), 'self', yaw=yaw)
        if n_torii % 6 == 3 and tcoins < 8:
            tcoins += 1; coin(f'coin_torii_top_{tcoins}', x, y + 3.6 + 0.9, z)
        d += 1.4
NOTES.append(('torii', n_torii))
# The landing (54.5) to the stage's west end (60): 5.5 m over 16 m, a stair on an embankment; its
# top slips 0.4 m under the deck's edge, 0.1 m below the deck, so no two floors share an edge.
PATHS['landing_stair'] = {'points': [[122.0, 54.5, 346.0], [126.0, 54.5, 346.25], [138.4, 59.9, 347.0]],
                          'sweep': {'profile': [[-1.8, -8.0], [-1.5, 0], [1.5, 0], [1.8, -8.0]],
                                    'materials': ['stone', 'steps', 'stone'], 'caps': True, 'stairs': {'rise': 0.3}}}

# ================================================================== 3.12 the stage, falls, chimney
SX0, SZ0, SX1, SZ1 = L.STAGE
SY = L.STAGE_Z
st = [(SX0, SY - 1.0, SZ0, SX1, SY, SZ1, 'stage')]
for px in range(140, 170, 6):
    for pz in (342, 348, 353):
        gg = gmin(px - 0.6, pz - 0.6, px + 0.6, pz + 0.6)
        if gg < SY - 1.5: st.append(cube(px, pz, 0.6, gg - 0.5, SY - 0.98, 'wood', ['bottom', 'top']))
# The hall (layout.hall(140, 355, 168, 374, 8, 10)) on its pad at 60.
st += [(140, SY - 0.5, 355, 168, SY + 8, 374, 'hall', ['bottom']),
       (138.5, SY + 7.98, 353.5, 169.5, SY + 12.5, 375.5, 'roof'),
       (145.6, SY + 12.48, 358.8, 162.4, SY + 18.0, 370.2, 'roof')]
# The bell (star 3) hangs under the hall's south eave over the deck's back edge: the plan's
# (154, 358) is inside the hall's wall (z 355).
BELL = (154.0, 353.9)
st.append(cube(BELL[0], BELL[1], 0.6, SY + 4.0, SY + 5.4, 'gold'))
st.append(cube(BELL[0], BELL[1], 0.04, SY + 1.4, SY + 4.02, 'rope'))
# The ladder up the front stilts (from the ledge, 44, to the deck, 16 m): replaces the
# spec's "stair up through the stilts", which does not fit under a 14 m deck over a 40 degree
# slope (the ground meets the deck's underside 10 m back).
st.append((153.7, 43.8, 339.55, 154.3, SY + 0.6, 339.75, 'wood'))
SORG = (154.0, SY, 355.0)
place('stage', 'gbm_stage', SORG, asset('gbm_stage', st, SORG, lod={'levels': [(60, [st[0]] + st[-7:-4])]}))
gl = 44.0                                                          # on the ledge
entity('pole_stage_front', 'pole', (154.0, gl, 339.4), {'height': r2(SY - gl)})
# Rope ladder A (shortcut A): plumb from the shelf (24) up the ledge's sheer face to 44, 20 m
# (6.7 s); the origin is the real ladder's (its foot, the face 0.15 m behind it). Layer ladder_a:
# down. (The rolled-up ladder on the lip, while it is up, is the real asset's second recipe; the
# grey box shows nothing there.)
LA = (154.0, 24.0, LADDER_SHELF[3] - 0.15)
ladder_a = [(153.6, LA[1] - 0.02, LA[2] - 0.05, 154.4, 44.6, LA[2] + 0.13, 'rope')]
asset('gbm_ladder_a', ladder_a, LA)
place('ladder_a', 'gbm_ladder_a', LA, 'none', layer='ladder_a')     # the pole is what holds the body
# The pole runs 1.2 m past the lip (to the stakes the ropes are tied to): the feet stop 1.2 below
# a pole's top (PoleTop), so at its top they are level with the ledge; let go and push at the rock,
# and the hands catch the lip (scenario 424). A pole 20 m tall left the feet 1.2 below the lip.
entity('pole_ladder_a', 'pole', LA, {'height': 21.2, 'front': True}, layer='ladder_a', yaw=180)   # climbed from the south
PATHS['ladder_a_steps'] = {'points': [[176.0, 13.1, 304.0], [161.5, 24.0, 316.0], [159.4, 24.0, 316.0]],
                           'sweep': {'profile': [[-1.6, -3.0], [-1.2, 0], [1.2, 0], [1.6, -3.0]],
                                     'materials': ['stone', 'steps', 'stone'], 'caps': True, 'stairs': {'rise': 0.3}}}

# The kick chimney, moved 8 m south of the plan's (195-198, 330-338), where the ground is 41-48:
# here its foot is the pool's west terrace (16) and its top the cliff top (46). Two rock faces
# 3.0 m apart (x 195 and 198), 10 m long, closed at the back, a rest ledge at 31.
CH = (196.5, 16.0, 327.0)
chim = [(189, 15.5, 321.5, 195, 46.0, 332.5, 'rock', ['bottom']),
        (198, 15.5, 321.5, 204, 46.0, 332.5, 'rock', ['bottom']),
        (194.98, 15.5, 331.5, 198.02, 46.0, 333.5, 'rock2', ['bottom']),
        (194.98, 30.4, 330.3, 198.02, 31.0, 331.52, 'rock2')]
place('kick_chimney', 'gbm_kick_chimney', CH, asset('gbm_kick_chimney', chim, CH))
entity('camera_chimney', 'camera_zone', (196.5, 16.0, 326.0), {'size': [3, 31, 10], 'mode': 'fixed', 'look': [0, 0, 1]})

# The falls: the cave's roof (17.5 to the lip at 48) is the cliff the water falls from; the water
# is a sheet 0.6 m in front of it, without collision, so the cave is entered through it.
FC = (214.0, 14.0, 341.0)
cave = [(206, 17.5, 336, 221.9, 48.0, 346.5, 'rock')]
place('falls_cave', 'gbm_falls_cave', FC, asset('gbm_falls_cave', cave, FC))
PATHS['falls_sheet'] = {'points': [[209.5, 48.0, 335.4], [218.5, 48.0, 335.4]], 'raised': True,
                        'sweep': {'profile': [[0.0, 0.0], [0.0, -36.0]], 'material': 'falls', 'double_sided': True}}
for k in range(6):
    coin(f'coin_cave_{k + 1}', 209.5 + 2.2 * (k % 3) + (k // 3) * 1.1, 15.0, 338.5 + 3.2 * (k // 3))
# The stream above the lip, in a gully the region cuts (the falls need water, and the rope bridge
# needs something to cross: the plan's ground under it is level with its ends).
PATHS['gully_falls'] = {'points': [[214.0, 48.4, 345.0], [212.0, 52.0, 352.0], [208.0, 57.0, 362.0], [204.0, 61.0, 383.0]]}
op(op='bed', path='gully_falls', width=12, depth=0.0, falloff=3)
PATHS['stream_upper'] = {'points': [[204.0, 61.15, 383.0], [208.0, 57.15, 362.0], [212.0, 52.15, 352.0], [214.0, 48.55, 345.0], [214.0, 48.15, 336.6]],
                         'raised': True, 'sweep': {'profile': [[-1.6, 0.0], [1.6, 0.0]], 'material': 'water'}}
# The rope bridge from the falls' top to the stage's east end (spec: 52 m, 8 m up): its east end
# is on the ground at (226.4, 346), 54.1 (the falls' top is about 54 in layout.py, not 52).
# The falls' top: a flat at 52 (spec: about 52) east of the lip, where the shoulder trail ends and
# the bridge starts; its east side blends into the slope the trail comes up.
FALLS_TOP = [222, 338, 236, 350]
flat({'rect': FALLS_TOP}, 52.0)
op(op='set', area={'rect': [236, 338, 240, 350]}, height=52.0, falloff=6)
# (alpha fix, DESIGN.md 12.9) The falls' top carried 6 m west under the rope bridge's east end: the
# hillside west of x 222 rose over the planks there, and neither way across could be walked.
flat({'rect': [216, 345, 222, 349]}, 52.0)
# G8's take-off pad (lead's decision, alpha fix, DESIGN.md 12.9): a flat 5 x 5 m at 61.8 east of the
# stage, where the slope's peak was (61.74 at (174, 356), falling over 30 degrees to the south), so a
# standing double jump starts the race's glide without landing on the rope bridge first.
G8_PAD = [171.5, 353.5, 176.5, 358.5]
op(op='set', area={'rect': G8_PAD}, height=61.8, falloff=2)
fe = (223.6, 51.95, 346.0)
rope_bridge('bridge_falls_stage', (169.6, SY - 0.08, 347.0), fe, sag=1.0, n=7)

# ================================================================== 3.14 east shoulder, shortcut C
DC = (256.0, 306.0)
gdc = gmin(DC[0] - 0.7, DC[1] - 0.7, DC[0] + 0.7, DC[1] + 0.7)
dead = [cube(DC[0], DC[1], 0.7, gdc - 0.5, gdc + 24.0, 'dead', ['bottom']),
        (DC[0] - 3.0, gdc + 15.0, DC[1] - 0.25, DC[0] - 0.68, gdc + 15.5, DC[1] + 0.25, 'dead'),
        (DC[0] + 0.68, gdc + 18.0, DC[1] - 0.25, DC[0] + 2.6, gdc + 18.5, DC[1] + 0.25, 'dead')]
place('dead_cedar_up', 'gbm_dead_cedar_up', (DC[0], gdc, DC[1]), asset('gbm_dead_cedar_up', dead, (DC[0], gdc, DC[1])), layer='cedar_c_up')
# Fallen: a log 1.2 m wide from the rim (34.7) to the shelf (20), 24.5 degrees, walkable.
A_, B_ = (DC[0], gdc, DC[1]), (226.0, 20.0, 318.0)
dx, dy, dz = B_[0] - A_[0], B_[1] - A_[1], B_[2] - A_[2]
horiz = math.hypot(dx, dz); ln = math.hypot(horiz, dy); pitch = math.degrees(math.atan2(-dy, horiz))
mid = ((A_[0] + B_[0]) / 2, (A_[1] + B_[1]) / 2 - 0.45, (A_[2] + B_[2]) / 2)
log_node = {'id': 'log', 'op': 'box', 'size': [1.2, 1.0, r2(ln + 2.0)], 'material': 'dead',
            'transform': {'rotate': [r2(pitch), 0, 0]}}
asset('gbm_dead_cedar_down', [], (0, 0, 0), extra_nodes=[log_node])
ASSETS['gbm_dead_cedar_down']['materials'] = {'dead': {'color': C['dead']}}
place('dead_cedar_down', 'gbm_dead_cedar_down', mid, 'self', yaw=math.degrees(math.atan2(dx, dz)), layer='cedar_c_down')
NOTES.append(('log', ln, pitch))

# The way out north-east (42): a gate where the path leaves at (252, 380).
gp = gnd(252.0, 378.0)
place('path_out_gate', 'gbm_path_out', (252.0, gp, 378.0), asset('gbm_path_out',
      [cube(250.2, 378.0, 0.2, gp - 0.5, gp + 3.6, 'marker', ['bottom']), cube(253.8, 378.0, 0.2, gp - 0.5, gp + 3.6, 'marker', ['bottom']),
       (249.6, gp + 3.3, 377.8, 254.4, gp + 3.6, 378.2, 'marker')], (252.0, gp, 378.0)))

# ================================================================== the basin's hollow log, the spring
HL = (188.0, 304.0)
ghl = gmin(HL[0] - 3, HL[1] - 3, HL[0] + 3, HL[1] + 3)
log_t = [(-1.3, -0.5, -3.0, 1.3, 0.0, 3.0, 'trunk'), (-1.3, 2.4, -3.0, 1.3, 2.8, 3.0, 'trunk'),
         (-1.3, -0.02, -3.0, -0.9, 2.42, 3.0, 'trunk'), (0.9, -0.02, -3.0, 1.3, 2.42, 3.0, 'trunk')]
asset('gbm_hollow_log', log_t, (0, 0, 0))
place('hollow_log', 'gbm_hollow_log', (HL[0], ghl + 0.05, HL[1]), 'self', yaw=math.degrees(math.atan2(16, 10)))
gs = gnd(48.0, 294.0)
place('canal_spring', 'gbm_spring', (48.0, gs, 294.0), asset('gbm_spring',
      [(44.5, gs - 0.5, 292.5, 51.5, gs + 0.6, 295.5, 'stone', ['bottom'])], (48.0, gs, 294.0)))

# ================================================================== 3.17 the sake brewery (c0_3)
# Its plan footprint (6-24, 212-224) is in row 3, the core region's cell c0_3: the recipe is
# here, the placement is in notes/mountain.md for the connector.
asset('gbm_sakagura', [(6, -0.5, 212, 24, 10.0, 224, 'plaster', ['bottom']), (4.5, 9.98, 210.5, 25.5, 13.2, 225.5, 'roof'),
                      (9.0, 13.18, 214.4, 21.0, 16.2, 221.6, 'roof'), (14.4, 7.4, 209.6, 15.6, 8.6, 210.8, 'cedar')],
      (15.0, 0.0, 218.0), tags={'cedar': 'bounce'})

# ================================================================== trees, bamboo (scatter assets)
asset('gbm_cedar', [cube(0, 0, 0.45, -0.3, 12.0, 'trunk', ['bottom', 'top']), cube(0, 0, 2.4, 10.0, 28.0, 'cedar', ['bottom'])],
      lod={'levels': [(48, [cube(0, 0, 2.4, 10.0, 28.0, 'cedar', ['bottom'])])]},
      collision=[cube(0, 0, 0.45, -0.3, 28.0, 'trunk', ['bottom'])])
asset('gbm_maple', [cube(0, 0, 0.3, -0.3, 5.0, 'trunk', ['bottom', 'top']), cube(0, 0, 3.0, 4.5, 10.5, 'maple', ['bottom'])],
      lod={'levels': [(44, [cube(0, 0, 3.0, 4.5, 10.5, 'maple', ['bottom'])])]},
      collision=[cube(0, 0, 0.3, -0.3, 6.0, 'trunk', ['bottom'])])
bam = [cube(-0.6, -0.4, 0.09, -0.3, 11.0, 'bamboo', ['bottom', 'top']), cube(0.7, 0.1, 0.09, -0.3, 12.5, 'bamboo2', ['bottom', 'top']),
       cube(0.0, 0.8, 0.09, -0.3, 10.0, 'bamboo', ['bottom', 'top'])]
asset('gbm_bamboo', bam, lod={'levels': [(30, [cube(0, 0, 0.3, -0.3, 11.5, 'bamboo', ['bottom', 'top'])])], 'cull': 90})

# ================================================================== paths on the ground
TRAIL = {'profile': [[-2.0, -0.3], [-1.1, 0], [1.1, 0], [2.0, -0.3]], 'materials': ['earth', 'path', 'earth'], 'caps': True}
def trail(name, pts):
    PATHS[name] = {'points': [list(p) for p in pts], 'drape': {'step': 4, 'bed': {'width': 3.0, 'depth': 0.3, 'falloff': 2}},
                   'sweep': TRAIL}
# R_WEST from the row seam to the fox grove.
# (Straighter up the ridge's west end than first built, on a ramp: below, "the trails' grades".)
trail('trail_west_north', [(91.15, 256.0), (95.5, 270.0), (94.0, 284.0), (90.0, 294.0)])
NOTES.append(('crossing', 'trail_west_north (R_WEST)', (91.15, gnd(91.15, 256), 256)))
# The basin's ways in: from the ridge (north slope), from the fox grove (west), to the falls pool (east).
# The ridge's north slope to the basin is 38 degrees in places (slid down, not climbed): stone
# steps instead of a trail, on their own bed.
# (Its head a landing at the crest's height (22.0, z 263-264.4), on the crest's flat west of x 149:
# from (150, 21.3, 265) the head lay 0.6-0.9 m under the crest, in its own bed, below a 40-degree
# bank: walked down, not up. The explorer bot, DESIGN.md 12.10.)
PATHS['stairs_ridge_basin'] = {'points': [[147.5, 22.0, 263.0], [147.5, 22.0, 264.4], [148.0, 13.1, 283.0]],
                               'sweep': {'profile': [[-2.2, -1.0], [-1.4, 0], [1.4, 0], [2.2, -1.0]],
                                         'materials': ['earth', 'steps', 'earth'], 'caps': True, 'stairs': {'rise': 0.3}}}
op(op='bed', path='stairs_ridge_basin', width=3.6, depth=0.6, falloff=2)
# the ground under the landing just under it: the bed's 2 m samples left a 33-degree dip in front
# of the head, slid on (scenario 685)
op(op='set', area={'rect': [145.5, 262.5, 149.5, 265.0]}, height=21.9)
trail('trail_fox_basin', [(98.0, 294.0), (118.0, 298.0), (138.0, 297.0)])
trail('trail_basin_falls', [(169.0, 299.0), (184.0, 300.0), (198.0, 302.0), (208.0, 305.0), (211.0, 312.0)])
# Steps from the pool's rim up to the west terrace (16) and from the pool to the cave (14); each
# top slips under the flat it meets.
PATHS['steps_pool_shelf'] = {'points': [[210.8, 12.3, 311.0], [206.3, 15.95, 311.0], [205.0, 15.95, 311.0]],
                             'sweep': {'profile': [[-1.6, -3.0], [-1.2, 0], [1.2, 0], [1.6, -3.0]],
                                       'materials': ['stone', 'steps', 'stone'], 'caps': True, 'stairs': {'rise': 0.3}}}
# (alpha fix, DESIGN.md 12.9: they reached 13.95 at z 329.8, inside the cave asset's floor, which starts at
# 14.0 at z 328.7, so a 0.65 m lip stood at its front; now they reach it at its front)
PATHS['steps_pool_cave'] = {'points': [[214.0, 11.25, 324.0], [214.0, 13.95, 328.6], [214.0, 13.95, 331.0]],
                            'sweep': {'profile': [[-1.6, -2.0], [-1.2, 0], [1.2, 0], [1.6, -2.0]],
                                      'materials': ['stone', 'steps', 'stone'], 'caps': True, 'stairs': {'rise': 0.3}}}
# The east shoulder trail (R_EAST) from the row seam to the falls' top, its switchbacks eased. The
# hairpin at (260, 303) has a point 1.5 m up each leg at its own height (alpha fix: the swept trail's
# mitre there met the next sections up the legs in a 31-degree crease, where a walk slid: scenario
# 705; level from the mitre to those points, it is flat).
trail('trail_shoulder', [(288.0, 256.0), (290.0, 262.0), (302.0, 282.0), (266.0, 298.0), (261.15, 302.04),
                         (260.0, 303.0), (261.15, 303.96), (266.0, 308.0), (296.0, 322.0), (298.0, 327.0), (292.0, 331.0), (250.0, 338.0), (237.0, 343.0)])
NOTES.append(('crossing', 'trail_shoulder (R_EAST)', (288.0, gnd(288, 256), 256)))
# The canal lane through the bamboo (R_CANAL), bending north-west round the grove's rise.
trail('trail_canal_lane_north', [(23.5, 256.0), (20.0, 300.0), (8.0, 350.0)])
NOTES.append(('crossing', 'trail_canal_lane_north (R_CANAL)', (23.5, gnd(23.5, 256), 256)))
# The stream from the falls pool down the gorge to the row seam.
sx = 236 + (244 - 236) * (268 - Z0) / (268 - 232)
PATHS['stream_gorge'] = {'points': [[218.0, 317.0], [224.0, 298.0], [236.0, 268.0], [r2(sx), float(Z0)]],
                   'drape': {'step': 4, 'downhill': True, 'bed': {'width': 3.4, 'depth': 0.6, 'falloff': 2}},
                   'sweep': {'profile': [[-2.6, -0.6], [-1.7, 0], [1.7, 0], [2.6, -0.6]], 'material': 'water'}}
NOTES.append(('crossing', 'stream_gorge (STREAM, R_WATER)', (sx, gnd(sx, Z0), Z0)))
op(op='bed', path='torii_steps', width=4.0, depth=0.6, falloff=3)
op(op='bed', path='landing_stair', width=3.6, depth=0.6, falloff=1)
op(op='bed', path='ladder_a_steps', width=3.2, depth=0.6, falloff=1)
# (alpha fix, DESIGN.md 12.9) The beds lowered the ground in front of the torii tunnel's first step
# (14.48 against its 15.0) and of ladder A's steps (12.4 against 13.1): lips a walk cannot take. The
# ground at each foot is set just under its first tread.
op(op='set', area={'rect': [91.5, 297.0, 96.5, 300.5]}, height=14.75)
op(op='set', area={'rect': [174.5, 301.5, 178.5, 304.5]}, height=12.85)
# The cave's west passage (forest_falls_cave: 2.6 m wide, floor 14) came out against the pool's west
# terrace at 16, under the passage's roof, so a jump could not take it: the 2 m between the chimney's
# east rock (x 204) and the cave's west jamb is cut to 14 from the passage south to z 326, and steps
# stand in it from the passage's mouth up to the terrace.
flat({'rect': [204.0, 326.1, 206.0, 334.0]}, 14.0)
PATHS['steps_cave_terrace'] = {'points': [[205.0, 14.0, 330.6], [205.0, 15.95, 327.2], [205.0, 15.95, 325.6]],
                               'sweep': {'profile': [[-1.0, -2.0], [-0.8, 0], [0.8, 0], [1.0, -2.0]],
                                         'materials': ['stone', 'steps', 'stone'], 'caps': True, 'stairs': {'rise': 0.3}}}

# The trails' grades (alpha fix, DESIGN.md 12.9): each leg a ramp between the ground at its ends, so
# the draped trail climbs evenly. The woods trail's climb over the ridge's west end (R_WEST, the core
# region's half up to z 256 too) was 30-35 degrees between its points, over the 30 at which a body
# slides; it now runs straighter up a 20 degree embankment from (86.5, 240) to the crest at
# (95.5, 270). The shoulder trail's legs are 2-16 degrees, but the slope under them is 25 and
# rough, and the draped line followed its bumps over 30 at the hairpins.
# A hairpin (a turn of more than 60 degrees) gets a level landing at its height, so the mitred
# corner of the trail lies flat (on the slope, its outer edge stood 1 m proud and the body slid).
def ramp_trail(name, pts, width=4.4, falloff=2.0, heights=None, max_grade=21.0):
    hs = heights or [gnd(x, z) for x, z in pts]
    for (a, ha), (b, hb) in zip(zip(pts, hs), zip(pts[1:], hs[1:])):
        grade = math.degrees(math.atan2(abs(hb - ha), math.hypot(b[0] - a[0], b[1] - a[1])))
        assert grade <= max_grade, (name, a, b, grade)
        op(op='ramp', **{'from': [a[0], r2(ha), a[1]], 'to': [b[0], r2(hb), b[1]]}, width=width, falloff=falloff)
    for i in range(1, len(pts) - 1):
        (ax, az), (bx, bz), (cx, cz) = pts[i - 1], pts[i], pts[i + 1]
        d1, d2 = math.atan2(bx - ax, bz - az), math.atan2(cx - bx, cz - bz)
        turn = abs(math.degrees((d2 - d1 + math.pi) % (2 * math.pi) - math.pi))
        if turn > 60:
            op(op='set', area={'circle': [bx, bz, 3.5]}, height=r2(hs[i]), falloff=2.5)
WOODS_UP = [(84.0, 232.0), (86.5, 240.0), (95.5, 270.0), (94.0, 284.0), (90.0, 294.0)]
ramp_trail('trail_west', WOODS_UP, heights=[0.8, 1.0, 12.4, 14.0, 15.0])
_sh = [tuple(p) for p in PATHS['trail_shoulder']['points']]
_shh = [gnd(x, z) for x, z in _sh]
_shh[4] = _shh[6] = _shh[5]                   # the hairpin's level: its legs 22 degrees beyond it
ramp_trail('trail_shoulder', _sh, heights=_shh, max_grade=23.0)
# From the trail (35.6 at (263, 307)) level west to the fallen dead cedar's stump (its top 35.96, 1.26
# over the trunk's foot at 34.7: forest_dead_cedar_fallen_col), so shortcut C's log is walked onto.
op(op='ramp', **{'from': [263.0, 35.6, 307.0], 'to': [256.2, 35.94, 306.8]}, width=2.2, falloff=1.0)
# The way out north-east: a trail from the falls' top (52) to the small torii (61.6) at the north rim,
# on a ramp cut into the bank (more than 45 degrees there).
trail('trail_way_out', [(238.0, 349.0), (243.0, 359.0), (248.0, 369.0), (252.0, 376.5)])
_wo = PATHS['trail_way_out']['points']
_d = [0.0]
for _a, _b in zip(_wo, _wo[1:]): _d.append(_d[-1] + math.hypot(_b[0] - _a[0], _b[1] - _a[1]))
_h0, _h1 = 52.0, gnd(252.0, 378.0)
ramp_trail('trail_way_out', [tuple(p) for p in _wo], width=4.0, heights=[_h0 + (_h1 - _h0) * d / _d[-1] for d in _d])

# ---- water, paint, rims
op(op='water', area={'circle': [L.FALLS_POOL[0], L.FALLS_POOL[1], 7.5]}, level=12.0, material='water')
for area, mat in [({'rect': [0, 256, 44, 384]}, 'bamboo_floor'),
                  ({'polygon': [[52, 256], [256, 256], [256, 320], [52, 320]]}, 'floor'),
                  ({'rect': [44, 320, 244, 384]}, 'litter'),
                  ({'rect': [244, 256, 320, 384]}, 'grass'),
                  ({'circle': [PX, PZ, 14]}, 'gravel'),
                  ({'circle': [L.BASIN[0], L.BASIN[1], 15]}, 'moss'),
                  ({'circle': [FX, FZ, 11]}, 'fox_earth'),
                  ({'polygon': LEDGE}, 'stone'),
                  ({'polygon': SHELF}, 'stone'),
                  ({'rect': [138, 354, 170, 377]}, 'stone')]:
    op(op='paint', area=area, material=mat)
# The level's rims in these rows (spec 1.8: the rims are things): rock walls 2-4 m thick, high
# enough that no glide crosses them (west 14: a glide from the stage reaches x 0 at about 29).
op(op='cliff', area={'rect': [0, 380, 320, 384]}, height=8.0, material='rock')
op(op='cliff', area={'rect': [0, 256, 2, 380]}, height=14.0, material='rock')
op(op='cliff', area={'rect': [318, 256, 320, 380]}, height=8.0, material='rock')

# ================================================================== scatter
clear = [{'circle': [L.BASIN[0], L.BASIN[1], 16]}, {'circle': [FX, FZ, 11]}, {'circle': [PX, PZ, 15]},
         {'circle': [L.FALLS_POOL[0], L.FALLS_POOL[1], 11]}, {'rect': [134, 336, 174, 380]}, {'polygon': LEDGE},
         {'polygon': SHELF}, {'rect': [186, 318, 224, 348]}, {'path': 'ladder_a_steps', 'width': 6}, {'rect': LADDER_SHELF}, {'circle': [226, 318, 6]},
         {'path': 'cedar_rope', 'width': 10}, {'path': 'bridge_deck6_rope', 'width': 8}, {'path': 'bridge_falls_stage', 'width': 8},
         {'path': 'torii_steps', 'width': 7}, {'path': 'landing_stair', 'width': 6},
         {'circle': [DECK6[0], DECK6[1], 6]}, {'circle': [ROPE_DECK[0], ROPE_DECK[1], 6]}, {'circle': [168, 262, 6]},
         {'circle': [DC[0], DC[1], 4]}, {'path': 'gully_falls', 'width': 12}, {'circle': [252, 378, 5]},
         {'rect': [0, 256, 46, 384]},
         # the way out's trail and the cave's west steps (alpha fix)
         {'path': 'trail_way_out', 'width': 6}, {'path': 'steps_cave_terrace', 'width': 4},
         # G8 as flown now: from its pad, east of the great torii (place/shrine.py), its part in these rows
         {'rect': [166, 340, 182, 362]}, {'polygon': [[169.0, 352.0], [179.0, 352.0], [176.6, 256.0], [166.6, 256.0]]}]
# Glide corridors kept clear of trees (10 m wide): G6 stage -> pagoda roof 4/5, G7 pagoda roof 5 ->
# cemetery top (its part in these rows), G8 the race line, stage -> arcade.
for gname, (sx_, sz_, sh_), (ex_, ez_) in L.GLIDES:
    if gname.split()[0] in ('G6', 'G7', 'G8'):
        d_ = math.hypot(ex_ - sx_, ez_ - sz_); nx_, nz_ = (ez_ - sz_) / d_ * 5, -(ex_ - sx_) / d_ * 5
        clear.append({'polygon': [[r2(sx_ + nx_), r2(sz_ + nz_)], [r2(ex_ + nx_), r2(ez_ + nz_)],
                                  [r2(ex_ - nx_), r2(ez_ - nz_)], [r2(sx_ - nx_), r2(sz_ - nz_)]]})
SCATTER = {
    'mountain_forest': {'assets': [{'asset': 'gbm_cedar', 'weight': 3, 'collision': 'gbm_cedar_col'},
                                   {'asset': 'gbm_maple', 'weight': 2, 'collision': 'gbm_maple_col'}],
                        'area': {'rect': [46, Z0, 318, 380]}, 'spacing': 9, 'fill': 0.8, 'seed': 41, 'lift': -0.1,
                        'exclude': clear, 'clearance': 1.6, 'max_slope': 40, 'chunk': 16, 'lod': 'assets',
                        'thin': {'distance': 56, 'keep': 0.5, 'scale': 1.2}},
    'mountain_bamboo': {'assets': [{'asset': 'gbm_bamboo', 'collision': 'self'}],
                        'area': {'rect': [2, Z0, 44, 380]}, 'spacing': 4, 'fill': 0.75, 'seed': 43, 'lift': -0.1,
                        'clearance': 1.2, 'max_slope': 45, 'chunk': 16, 'lod': 'assets'},
}

# ================================================================== the game's entities
# The stars (1, 3 and 4 here), the triggers (the bell, the omamori, shortcuts A, C and D): ../../../game.py
_gs = importlib.util.spec_from_file_location('game', TOWN / 'game.py'); G = importlib.util.module_from_spec(_gs); _gs.loader.exec_module(G)
for _cid, _es in G.cell_entities((4, 5)).items(): CELLS.setdefault(_cid, {'placements': [], 'entities': []})['entities'].extend(_es)

# ================================================================== write
TERRAIN_MATERIALS = {
    'floor': {'color': '#5e6a3a'}, 'litter': {'color': '#7a5a34'}, 'grass': {'color': '#8a8a4a'},
    'bamboo_floor': {'color': '#9aa860'}, 'moss': {'color': '#4f7a34'}, 'fox_earth': {'color': '#a0603a'},
    'gravel': {'color': '#d4ccb8'}, 'rock': {'color': '#6a665e'}, 'earth': {'color': '#6a4a30'},
    'path': {'color': '#b08a5e'}, 'steps': {'color': '#a8a294'}, 'stone': {'color': '#8e887c'},
    'planks': {'color': '#8a6446'}, 'rope': {'color': '#e8dcc0'},
    'water': {'color': '#3f7393', 'water': True, 'tag': 'water'}, 'falls': {'color': '#dce8f0', 'water': True},
}
LAYERS = {'ladder_a': {}, 'cedar_c_up': {'group': 'cedar_c', 'on': True}, 'cedar_c_down': {'group': 'cedar_c'},
          'root_d_shut': {'on': True}}

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1) + '\n')

# the placement zones (place/ZONE.py) change the cells and the part before they are written
sys.path.insert(0, str(TOWN))
from place import apply as apply_zones, unused
apply_zones('mountain', globals())
for _n in unused(ASSETS, CELLS, SCATTER, PATHS): del ASSETS[_n]          # the grey boxes swapped out

for f in HERE.glob('gbm_*.asset.json'): f.unlink()
for name, r in ASSETS.items(): dump(HERE / f'{name}.asset.json', r)
for i in range(5):
    for j in (4, 5):
        cid = f'c{i}_{j}'
        c = CELLS.get(cid, {'placements': [], 'entities': []})
        body = {'format': 'mei-world-cell', 'version': 1, 'id': cid, 'at': [i, j], 'region': L.region_of(i, j),
                'placements': c['placements']}
        if c['entities']: body['entities'] = c['entities']
        dump(TOWN / 'cells' / f'{cid}.cell.json', body)

# the ground of these rows, one line per row of samples (z = 256 .. 384), x = 0 .. 320
lines = [f'# Ground of the shrine town\'s mountain rows (z {Z0}-{Z1}, x 0-{L.W}, every {SPACING} m) from layout.py;'
         ' generated by make_mountain.py, do not edit.']
for z in range(Z0, Z1 + 1, SPACING):
    lines.append(' '.join(f'{base_height(x, z):.2f}' for x in range(0, L.W + 1, SPACING)))
(TOWN / 'parts').mkdir(parents=True, exist_ok=True)
(TOWN / 'parts' / 'mountain.heights.txt').write_text('\n'.join(lines) + '\n')

parts = {
    '_about': 'The mountain region (rows 4-5, z 256-384) of the shrine town grey box, generated by '
              'assets/greybox/mountain/make_mountain.py. World-level entries in the world recipe\'s format: '
              'paths, scatter, terrain materials and this region\'s operations on the one ground field '
              '(apply after the field\'s heights, in this order), layers. See notes/mountain.md.',
    'layers': LAYERS,
    'paths': PATHS,
    'scatter': SCATTER,
    'terrain': {'materials': TERRAIN_MATERIALS, 'operations': OPS},
}
dump(TOWN / 'parts' / 'mountain.json', parts)


print(f'{len(ASSETS)} assets, {sum(len(c["placements"]) for c in CELLS.values())} placements, '
      f'{sum(len(c["entities"]) for c in CELLS.values())} entities, {len(PATHS)} paths, {len(OPS)} operations')
for n in NOTES: print(n)
