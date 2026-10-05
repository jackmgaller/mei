"""Shrine town grey box, core region (rows z 128-256, cells c*_2 and c*_3).

Writes, from the shared plan `layout.py` (coordinates and heights):

- assets/greybox/core/gbc_*.asset.json   box recipes (flat colours, collision "self" or a trunk)
- cells/c{0..4}_{2,3}.cell.json          placements and entities of the core rows
- parts/core.json                        world-level entries: paths (sweeps, rails), terrain
                                         (materials and the core rows' field), scatter, layers
- parts/core_heights.txt                 the field's starting heights (layout.height, 2 m grid)

Run from anywhere:
    python3 carts/garden/shrinetown/assets/greybox/core/gen_core.py --layout PATH/layout.py

The default layout is carts/garden/shrinetown/layout.py. Everything here is in metres, x east,
z north, y up; boxes are (x1, z1, x2, z2, base, top). notes/core.md lists what this changes
from layout.py and why.
"""
import argparse
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOWN = os.path.abspath(os.path.join(HERE, '..', '..', '..'))      # carts/garden/shrinetown
ROWS = (2, 3)
Z0, Z1 = 128, 256

ap = argparse.ArgumentParser()
ap.add_argument('--layout', default=os.path.join(TOWN, 'layout.py'))
args = ap.parse_args()
spec = importlib.util.spec_from_file_location('layout', args.layout)
L = importlib.util.module_from_spec(spec)
sys.stdout = open(os.devnull, 'w')          # layout.py is quiet, but be safe
spec.loader.exec_module(L)
sys.stdout = sys.__stdout__

# ------------------------------------------------------------------ colours (a few hues per zone)
MAT = {
    'red': '#c43026', 'red_dark': '#8e2a20', 'roof': '#3a3c44', 'roof_hi': '#5a6068',
    'white': '#e8e2d2', 'wood': '#96683f', 'wood_dark': '#5a3e2c', 'stone': '#97928a',
    'stone_dark': '#6a665e', 'conc': '#c8c4b8', 'conc_dark': '#8a8680',
    'cedar': '#2e4a30', 'maple': '#c8301e', 'ginkgo': '#e8b830', 'bamboo': '#8a9a48',
    'trunk': '#4a3a2e', 'park_blue': '#3a6ab0', 'park_green': '#40a060', 'park_yellow': '#e0c040',
    'grave': '#a8a49a', 'mossy': '#7a8050', 'lantern': '#b4ae9e', 'gold': '#ffd040',
}
TERRAIN_MAT = {
    'floor': {'color': '#6e6236'}, 'earth': {'color': '#6a4a30'}, 'gravel': {'color': '#d4ccb8'},
    'ashlar': {'color': '#b4ae9e'}, 'podium': {'color': '#8e887c'}, 'grass': {'color': '#7c9a4c'},
    'cemetery': {'color': '#a09c90'}, 'bamboo_floor': {'color': '#8a9448'}, 'lane': {'color': '#a89a7a'},
    'canal_stone': {'color': '#7a766c'}, 'path': {'color': '#8a6a48'}, 'steps': {'color': '#9a9488'},
    'planks': {'color': '#8a6446'}, 'rope': {'color': '#e8e0c8'},
    'water': {'color': '#3f7393', 'water': True, 'tag': 'water'},
}

# ------------------------------------------------------------------ changes to the plan (notes/core.md)
TERR = (114, 166, 214, 234)        # layout's TERR with its south edge at 166 (2 m grid; was 167)
TEMPLE = L.TEMPLE
CEM = L.CEMETERY
CANAL = (L.CANAL[0], Z0, L.CANAL[2], Z1)
GATE_Z = 172.0                     # main gate centre (layout: 167); it stands wholly on the terrace
# The white wall sits 1 m inside the terrace edge (a 0.6 m ledge in front, as the built shrine).
WALL = [(150, 167), (117, 167), (115, 169), (115, 229), (119, 233), (209, 233), (213, 229),
        (213, 171), (209, 167), (170, 167)]
GATES = {'west': (115, 200, 4), 'north': (160, 233, 5), 'east': (213, 192, 4)}
CLIFFS = [TERR, TEMPLE, CEM, CANAL]          # CANAL: its banks are the town's cliff (z 0-292)


def ground(x, z):
    """Ground as built: layout.height with the plan's flats and the terrace shifted to z 166."""
    if L.in_rect(x, z, TEMPLE): return 8.6
    if L.in_rect(x, z, TERR): return 5.0
    if L.in_rect(x, z, CANAL): return -1.2
    if L.in_rect(x, z, CEM): return 1.8 * min(9, math.floor((z - 130) / 12) + 1)
    return L.height(x, z)


def file_height(x, z):
    """A sample of the heights file. Samples on a cliffed rectangle's edge take the outside
    ground (the cliff's top sheet is set after), inner samples whatever is there."""
    for r in CLIFFS:
        if L.in_rect(x, z, r):
            dx = -0.01 if x == r[0] else 0.01 if x == r[2] else 0.0
            dz = -0.01 if z == r[1] else 0.01 if z == r[3] else 0.0
            if dx or dz:
                return file_height(x + dx, z + dz) if not any(
                    L.in_rect(x + dx, z + dz, q) for q in CLIFFS if q is not r) else _outside(x + dx, z + dz)
            return L.height(x, z)
    return L.height(x, z)


def _outside(x, z):
    # an edge sample whose outward nudge lands in another (nesting) cliff: TEMPLE inside TERR
    if L.in_rect(x, z, TEMPLE): return 8.6
    if L.in_rect(x, z, TERR): return 5.0
    return L.height(x, z)


def floor_under(x1, z1, x2, z2):
    pts = [(x1, z1), (x2, z1), (x1, z2), (x2, z2), ((x1 + x2) / 2, (z1 + z2) / 2)]
    return min(ground(x, z) for x, z in pts)


# ------------------------------------------------------------------ assets and placements
assets = {}          # name -> recipe
placements = {}      # cell id -> list
entities = {}        # cell id -> list
problems = []


def cell_of(x, z):
    c, r = int(x // 64), int(z // 64)
    if r not in ROWS or not 0 <= c <= 4:
        problems.append(f'outside the core rows: ({x:.1f}, {z:.1f})')
        return None
    return f'c{c}_{r}'


def recipe(name, boxes, extra_nodes=()):
    """boxes: (cx, cy, cz, sx, sy, sz, material, open_bottom) in the asset's frame."""
    nodes, used = [], set()
    for k, (cx, cy, cz, sx, sy, sz, mat, ob) in enumerate(boxes):
        n = {'id': f'b{k}', 'op': 'box', 'size': [round(sx, 3), round(sy, 3), round(sz, 3)],
             'material': mat, 'transform': {'translate': [round(cx, 3), round(cy, 3), round(cz, 3)]}}
        if ob: n['open'] = ['bottom']
        nodes.append(n); used.add(mat)
    for n in extra_nodes:
        nodes.append(n); used.add(n['material'])
    mats = {}
    for m in sorted(used):
        mats[m] = {'color': MAT[m]}
        if m == 'gold': mats[m]['class'] = 'emissive'
        if m == 'park_yellow' and name == 'gbc_park_slide': mats[m]['tag'] = 'slide'
    return {'format': 'mei-asset', 'version': 1, 'name': name, 'materials': mats,
            'lighting': {'mode': 'vertical', 'ambient': 0.5}, 'nodes': nodes}


def add_asset(name, boxes, extra=()):
    if name not in assets: assets[name] = recipe(name, boxes, extra)
    return name


def place(pid, asset, x, y, z, yaw=0.0, collision='self', merge=False, layer=None):
    c = cell_of(x, z)
    if c is None: return
    p = {'id': pid, 'asset': asset, 'position': [round(x, 3), round(y, 3), round(z, 3)], 'collision': collision}
    if yaw: p['yaw'] = round(yaw, 2)
    if merge: p['merge'] = True
    if layer: p['layer'] = layer
    placements.setdefault(c, []).append(p)


def entity(eid, etype, x, y, z, asset=None, params=None):
    c = cell_of(x, z)
    if c is None: return
    e = {'id': 'core_' + eid, 'type': etype, 'position': [round(x, 3), round(y, 3), round(z, 3)]}
    if asset: e['asset'] = asset
    if params: e['params'] = params
    entities.setdefault(c, []).append(e)


def block(pid, x1, z1, x2, z2, base, top, mat, **kw):
    """One box from base to top over a footprint, as its own asset and placement."""
    cx, cz = (x1 + x2) / 2, (z1 + z2) / 2
    name = add_asset('gbc_' + pid, [(0, (top - base) / 2, 0, x2 - x1, top - base, z2 - z1, mat, True)])
    place(pid, name, cx, base, cz, **kw)
    return top


def stepped_roof(boxes, hx, hz, eave, ridge, tx, tz, over, tiers, slab=0.5, mat='roof'):
    """An eave slab (overhanging) then tiers stepping in to the ridge: a climbable stand-in for a
    sloped roof, every step at most (ridge - eave - slab) / tiers high."""
    boxes.append((0, eave + slab / 2, 0, 2 * (hx + over), slab, 2 * (hz + over), mat, False))
    h0 = eave + slab
    for i in range(1, tiers + 1):
        f = i / tiers
        ax, az = hx + over + (tx - hx - over) * f, hz + over + (tz - hz - over) * f
        b, t = h0 + (ridge - h0) * (i - 1) / tiers, h0 + (ridge - h0) * i / tiers
        boxes.append((0, (b + t) / 2, 0, 2 * ax, t - b, 2 * az, mat if i < tiers else 'roof_hi', True))
    return boxes


def hall(pid, x1, z1, x2, z2, base, eave, ridge, tiers, over=1.5, col='red', top_frac=0.6):
    """A hall: body to the eave, then a stepped roof whose top tier is layout's upper roof box
    (20% in from each side)."""
    hx, hz = (x2 - x1) / 2, (z2 - z1) / 2
    boxes = [(0, (eave - base) / 2, 0, 2 * hx, eave - base, 2 * hz, col, True)]
    stepped_roof(boxes, hx, hz, eave - base, ridge - base, hx * top_frac, hz * top_frac, over, tiers)
    name = add_asset('gbc_' + pid, boxes)
    place(pid, name, (x1 + x2) / 2, base, (z1 + z2) / 2)
    return {'ridge': ridge, 'top': ((x1 + x2) / 2 - hx * top_frac, (z1 + z2) / 2 - hz * top_frac,
                                    (x1 + x2) / 2 + hx * top_frac, (z1 + z2) / 2 + hz * top_frac),
            'slab': eave + 0.5}


# ---- 3.6 outer courtyard: side halls (the torii is c2_1, the town's)
HALL_W = hall('side_hall_w', 122, 126, 134, 162, 0.6, 4.8, 11.6, 3)
HALL_E = hall('side_hall_e', 186, 126, 198, 162, 0.6, 4.8, 11.6, 3)
lantern = add_asset('gbc_stone_lantern', [(0, 1.0, 0, 0.9, 2.0, 0.9, 'lantern', True)])
for k, z in enumerate((132, 140, 148)):
    place(f'lantern_court_w{k}', lantern, 154.0, 0.6, z, merge=True)
    place(f'lantern_court_e{k}', lantern, 166.0, 0.6, z, merge=True)
block('chozuya', 140, 136, 146, 140, 0.6, 3.6, 'wood')                  # water pavilion (dressing)
block('shrine_office', 176, 150, 184, 160, 0.6, 4.6, 'white')

# ---- 3.7 inner precinct
CORR_W = hall('corridor_w', 122, 174, 134, 202, 5.0, 9.2, 15.0, 3)
CORR_E = hall('corridor_e', 186, 174, 198, 202, 5.0, 9.2, 15.0, 3)
# temple on its podium (8.6, terrain): body to the eave 13.0, six tiers to the ridge. The ridge is
# the real temple's, 27.5 (arch_temple: 18.9 above the podium), not layout's 29.5: G5 is checked
# against it (DESIGN.md, "Changes from the plan").
TEMPLE_RIDGE = 27.5
TEMPLE_R = hall('temple', 136, 210, 184, 226, 8.6, 13.0, TEMPLE_RIDGE, 6, over=3, col='wood', top_frac=0.6)
# the main gate: two side blocks and a lintel (an 8 m passage, 4.5 m clear), the lower roof (11.0-12.2),
# the upper storey (12.2-16.2) and its roof stepped to 18.6
gz = GATE_Z
gb = [(-6.5, 3.0, 0, 5, 6.0, 10, 'red', True), (6.5, 3.0, 0, 5, 6.0, 10, 'red', True),
      (0, 5.25, 0, 8, 1.5, 10, 'red', False),
      (0, 6.6, 0, 22, 1.2, 14, 'roof', False),
      (0, 9.2, 0, 16, 4.0, 8, 'red', True)]
stepped_roof(gb, 8, 4, 11.2, 13.6, 4.8, 2.4, 2.0, 1)
add_asset('gbc_gate', gb)
place('gate', 'gbc_gate', 160.0, 5.0, gz)
GATE_LOWER = (149, gz - 7, 171, gz + 7, 12.2)
block('bell_pavilion', 202, 224, 206, 228, 5.0, 9.7, 'wood')
for k, (x, z) in enumerate([(152, 184), (168, 184), (152, 196), (168, 196)]):
    place(f'lantern_terr{k}', lantern, x, 5.0, z, merge=True)

# the white wall (2.6 m on the terrace), split at the three gates; one box per straight run
def wall_runs():
    runs, cur = [], None
    for (ax, az), (bx, bz) in zip(WALL, WALL[1:]):
        n = max(1, int(round(math.hypot(bx - ax, bz - az) / 1.0)))
        for k in range(n):
            p0 = (ax + (bx - ax) * k / n, az + (bz - az) * k / n)
            p1 = (ax + (bx - ax) * (k + 1) / n, az + (bz - az) * (k + 1) / n)
            mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
            if any(math.hypot(mid[0] - gx, mid[1] - gzz) < gr for gx, gzz, gr in GATES.values()):
                cur = None; continue
            if cur and cur['dir'] == (ax, az, bx, bz): cur['b'] = p1
            else:
                cur = {'a': p0, 'b': p1, 'dir': (ax, az, bx, bz)}; runs.append(cur)
    return runs

for k, r in enumerate(wall_runs()):
    (ax, az), (bx, bz) = r['a'], r['b']
    length = math.hypot(bx - ax, bz - az) + 0.8
    yaw = math.degrees(math.atan2(bx - ax, bz - az))
    name = add_asset(f'gbc_wall_{k}', [(0, 1.3, 0, 0.8, 2.6, length, 'white', True),
                                       (0, 2.75, 0, 1.2, 0.3, length + 0.4, 'roof', False)])
    place(f'wall_{k}', name, (ax + bx) / 2, 5.0, (az + bz) / 2, yaw=yaw)

# north gate B: the bar (barred, on at start) and the opened leaves (layer gate_b_open)
block('gate_b_posts_w', 154.4, 232.4, 155.6, 233.6, 5.0, 9.0, 'red')
block('gate_b_posts_e', 164.4, 232.4, 165.6, 233.6, 5.0, 9.0, 'red')
block('gate_b_lintel', 154.4, 232.6, 165.6, 233.4, 8.2, 9.4, 'roof')
block('gate_b_bar', 155.6, 232.7, 164.4, 233.3, 5.0, 7.0, 'wood_dark', layer='gate_b_barred')
block('gate_b_leaf_w', 155.8, 228.6, 156.4, 232.4, 5.0, 7.0, 'wood_dark', layer='gate_b_open')
block('gate_b_leaf_e', 163.6, 228.6, 164.2, 232.4, 5.0, 7.0, 'wood_dark', layer='gate_b_open')
for side, (x, z) in (('w', (115, 200)), ('e', (213, 192))):
    block(f'gate_{side}_post_s', x - 0.6, z - 4.6, x + 0.6, z - 3.4, 5.0, 9.0, 'red')
    block(f'gate_{side}_post_n', x - 0.6, z + 3.4, x + 0.6, z + 4.6, 5.0, 9.0, 'red')
    block(f'gate_{side}_lintel', x - 0.5, z - 4.6, x + 0.5, z + 4.6, 8.2, 9.4, 'roof')

# mossy boulders where the wall is easy (spec 3.7): two by the west wall, one in the courtyard
for k, (x, z, h) in enumerate([(110.5, 184, 2.2), (110.5, 214, 2.8), (128, 164.5, 1.7)]):
    g = floor_under(x - 1.2, z - 1.2, x + 1.2, z + 1.2)
    block(f'boulder_{k}', x - 1.2, z - 1.2, x + 1.2, z + 1.2, g - 0.2, g + h, 'mossy')

# ---- 3.9 west woods: the treetop decks of the core rows, the crown deck and its trunk pole
DECKS = [d for d in L.DECKS if Z0 <= d[1] < Z1]                        # 9, 12, 15, 18, 21
deck_tree = {}
for k, (x, z, h) in enumerate(DECKS + [L.CROWN]):
    g = floor_under(x - 1, z - 1, x + 1, z + 1)
    nm = f'gbc_deck_tree_{k}'
    boxes = [(0, (h - g + 9) / 2, 0, 1.6, h - g + 9, 1.6, 'trunk', True),          # trunk to 9 m above the deck
             (0, h - g - 0.3, 0, 6, 0.6, 6, 'wood', False),                        # the deck, 6 x 6
             (0, h - g + 8, 0, 8, 6, 8, 'cedar', False)]                           # crown 5-11 m above it
    add_asset(nm, boxes)
    place(f'deck_{k}', nm, x, g - 0.2, z, collision='self')
    deck_tree[(x, z)] = (h, g)
# the crown's landing at 15 m south of its trunk, the 13 m pole beside it
cx, cz, ch = L.CROWN
block('crown_landing', cx - 3, cz - 7, cx + 3, cz - 3, 14.4, 15.0, 'wood')
entity('pole_crown', 'pole', cx, 15.0, cz - 3.4, params={'height': 13.0})

# A stone lantern on the pagoda terrace, in front of its south face (its origin is in this row): its
# top is 3.6 m under roof 1's eave, the rhythm of the tiers above. From the terrace the eave is 5.0
# up, and a double jump (3.0 m measured) does not bring the hands to its 0.35 m fascia (scenario 422).
block('pagoda_lantern', 177.4, 254.9, 178.6, 256.1, L.PAG_BASE - 0.2, L.PAG_BASE + 1.4, 'lantern')

# ---- 3.13 pond and east valley: stepping stones, the zig-zag bridge (a path), a stone at the culvert
STONES = []
for (ax, az), (bx, bz) in [((226, 129), (232, 150)), ((232, 150), (236, 179))]:
    n = int(math.hypot(bx - ax, bz - az) // 3.6)
    for k in range(n + 1):
        x, z = ax + (bx - ax) * k / n, az + (bz - az) * k / n
        if ground(x, z) < -0.6 and (round(x, 1), round(z, 1)) not in [(s[0], s[1]) for s in STONES]:
            STONES.append((round(x, 1), round(z, 1)))
stone = add_asset('gbc_pond_stone', [(0, 0.9, 0, 1.4, 1.8, 1.4, 'stone', True)])
for k, (x, z) in enumerate(STONES):
    place(f'pond_stone_{k}', stone, x, -1.5, z, merge=True)              # top at 0.3

# ---- 3.14 cemetery: graves in rows, the jizo hall, the gate; terraces are terrain, stairs paths
grave = add_asset('gbc_grave_row', [(0, 0.6, 0, 20, 1.2, 0.8, 'grave', True)])
for t in range(9):
    z0 = 130 + 12 * t
    zs = (z0 + 4, z0 + 9) if t < 8 else (z0 + 4, z0 + 9, z0 + 16, z0 + 21)
    for j, z in enumerate(zs):
        for side, x in (('w', 271), ('e', 301)):
            place(f'graves_{t}_{j}{side}', grave, x, 1.8 * (t + 1), z, merge=True)
block('jizo_hall', 296, 238, 302, 244, 16.2, 21.2, 'wood')
block('cem_gate_w', 282.6, 129.4, 283.6, 130.6, 0.0, 4.2, 'stone_dark')
block('cem_gate_e', 288.4, 129.4, 289.4, 130.6, 0.0, 4.2, 'stone_dark')
block('cem_gate_beam', 282.0, 129.5, 290.0, 130.5, 4.2, 4.8, 'stone_dark')

# ---- viaduct: the span (306, 134) -> (320, 146) and its pier; the span to its south is the town's.
# The deck and the parapets are the town's sweeps along the whole line (paths viaduct_deck,
# parapet_s, parapet_n_e), so this span is the girders under the deck, as the town's spans.
# The line stops at x 315.5 (the town's VIADUCT_END: its parapets stay over the level), where a
# wall 5.5 m tall closes the deck's end (spec 7.3: the line's end; a double jump and grab is 5.15).
(ax, az), (bx, bz) = (306, 134), (315.5, 134 + 12 * 9.5 / 14)
length = math.hypot(bx - ax, bz - az)
vb = [(-4.0, 6.925, 0, 0.8, 1.05, length - 0.4, 'conc', True), (4.0, 6.925, 0, 0.8, 1.05, length - 0.4, 'conc', True)]
add_asset('gbc_viaduct_span', vb)
add_asset('gbc_viaduct_end', [(0, 2.75, -0.2, 12.6, 5.5, 0.4, 'conc_dark', True)])
place('viaduct_end', 'gbc_viaduct_end', bx, 9.0, bz, yaw=math.degrees(math.atan2(14, 12)))
place('viaduct_span', 'gbc_viaduct_span', (ax + bx) / 2, 0.0, (az + bz) / 2,
      yaw=math.degrees(math.atan2(bx - ax, bz - az)))
pg = ground(306, 134)
block('viaduct_pier', 304, 132, 308, 136, pg - 0.2, 8.0, 'conc_dark')

# ---- 3.16 park and festival ground
block('yagura', 18, 156, 26, 164, 0.6, 8.6, 'wood')
block('park_toilet', 4, 186, 10, 192, 0.6, 3.6, 'conc')
block('jungle_gym', 26, 132, 29, 135, 0.6, 3.1, 'park_blue')
block('swings', 33, 140, 37, 141, 0.6, 3.1, 'park_green')
# the slide: a ladder tower (2.4 m) and a ramp tagged slide down to the south
add_asset('gbc_park_slide', [(0, 1.2, -2.6, 1.2, 2.4, 1.2, 'park_blue', True)],
          [{'id': 'ramp', 'op': 'box', 'size': [0.9, 0.2, 4.6], 'material': 'park_yellow',
            'transform': {'rotate': [-28, 0, 0], 'translate': [0, 1.2, -0.0]}}])
place('park_slide', 'gbc_park_slide', 12.0, 0.6, 140.0)
gink = add_asset('gbc_tree_ginkgo', [(0, 2.0, 0, 0.6, 4.0, 0.6, 'trunk', True), (0, 7.0, 0, 6, 6, 6, 'ginkgo', False)])
add_asset('gbc_trunk_ginkgo_col', [(0, 2.0, 0, 0.6, 4.0, 0.6, 'trunk', True)])
for k, (x, z) in enumerate([(8, 150), (36, 152), (8, 172), (36, 176), (14, 200), (32, 196)]):
    place(f'ginkgo_{k}', gink, x, 0.6, z, collision='gbc_trunk_ginkgo_col')
# watermill on the canal at (48, 196): the house on the park bank, the wheel in the canal
block('watermill_house', 36, 191, 43.6, 201, 0.6, 5.6, 'wood_dark')
block('watermill_wheel', 44.4, 193.5, 46.0, 198.5, -1.2, 4.0, 'wood')

# ---- 3.17 in c0_3: the sake brewery (16.2) at the bamboo's foot
# the recipe is the mountain region's (gbm_sakagura: walls to 10, roofs to 16.2, the sugidama a
# bounce under the south eave), placed on layout's ground at its centre (0.66-1.22 under it)
place('sakagura', 'gbm_sakagura', 15.0, 0.66, 218.0)

# ------------------------------------------------------------------ coins (gold) in the core rows
add_asset('gbc_coin', [], [{'id': 'disc', 'op': 'cylinder', 'radius': 0.3, 'height': 0.08, 'segments': 10,
                             'material': 'gold', 'transform': {'rotate': [90, 0, 0]}}])

def coin(cid, x, y, z):
    entity('coin_' + cid, 'coin', x, y, z, asset='gbc_coin')

for nm, h in (('side_hall_w', HALL_W), ('side_hall_e', HALL_E), ('corridor_w', CORR_W),
              ('corridor_e', CORR_E), ('temple', TEMPLE_R)):
    x1, z1, x2, z2 = h['top']
    coin(nm, (x1 + x2) / 2, h['ridge'] + 1.0, (z1 + z2) / 2)
coin('gate', 160.0, 18.6 + 1.0, gz)
for k, (x, z, h) in enumerate(DECKS):
    coin(f'deck_{k}', x + 1.5, h + 1.0, z + 1.5)
coin('crown', cx, ch + 1.0, cz)
for k, (x, z) in enumerate(STONES[::2][:5]):
    coin(f'pond_{k}', x, 1.3, z)
for k, t in enumerate((1, 3, 5, 7, 8)):
    coin(f'cemetery_{k}', 286.0, 1.8 * (t + 1) + 1.0, 130 + 12 * t + 7)

# ------------------------------------------------------------------ paths: sweeps and rails
paths = {}
SOLID = lambda w, d: [[-w, -d], [-w, 0], [w, 0], [w, -d], [-w, -d]]
PLANKS = [[-0.8, -0.12], [-0.8, 0.0], [0.8, 0.0], [0.8, -0.12], [-0.8, -0.12]]
ROPE = {'profile': [[0.0, -0.05], [0.0, 0.05]], 'material': 'rope', 'double_sided': True, 'collision': False}


def stair(name, a, b, half, depth=4.0):
    paths[name] = {'points': [list(map(lambda v: round(v, 3), a)), list(map(lambda v: round(v, 3), b))],
                   'sweep': {'profile': SOLID(half, depth), 'materials': ['steps', 'steps', 'steps', 'steps'],
                             'stairs': {'rise': 0.3}, 'caps': True}}


stair('core_gate_stair', (160, 0.9, 152), (160, 5.0, 166), 6.0, 4.6)
stair('core_temple_stair', (160, 5.3, 201), (160, 8.6, 208), 6.0, 4.0)
gw = ground(106, 200); stair('core_west_gate_stair', (106, gw + 0.3, 200), (114, 5.0, 200), 3.0, 4.0)
ge = ground(222, 192); stair('core_east_gate_stair', (214, 5.0, 192), (222, ge + 0.3, 192), 3.0, 4.0)
# the stone stair from the north gate to the pagoda terrace, on layout's line (its ground is carved
# to the line; a bed lowers it under the treads)
paths['core_north_stair'] = {'points': [[160, 5.0, 233.6], [172, L.PAG_BASE, 254.0]],
                             'sweep': {'profile': [[-4.2, -1.2], [-3.5, 0], [3.5, 0], [4.2, -1.2]],
                                       'materials': ['earth', 'steps', 'earth'], 'stairs': {'rise': 0.3},
                                       'caps': True}}
# the cemetery's middle stair: one flight at each terrace edge
for t in range(1, 9):
    ze, h = 130 + 12 * t, 1.8 * t
    stair(f'core_cem_stair_{t}', (286, h + 0.3, ze - 3.6), (286, h + 1.8, ze), 1.5, 2.4)


def bridge(name, pts, profile=PLANKS, rails=True):
    paths[name] = {'points': [[round(x, 3), round(y, 3), round(z, 3)] for x, y, z in pts], 'raised': True,
                   'sweep': {'profile': profile, 'material': 'planks'}}


def deck_exit(c, d):
    (x0, z0), (x1, z1) = c, d
    dx, dz = x1 - x0, z1 - z0
    t = 2.6 / max(abs(dx), abs(dz))           # 0.4 m onto the deck: no crack at the join
    return x0 + dx * t, z0 + dz * t


def rope_bridge(name, a, b, sag=0.35):
    """Deck a (x, z, h) to deck b, edge to edge, five points with a little sag."""
    (ax, az, ah), (bx, bz, bh) = a, b
    sx, sz = deck_exit((ax, az), (bx, bz)); ex, ez = deck_exit((bx, bz), (ax, az))
    pts = []
    for i in range(5):
        f = i / 4
        pts.append((sx + (ex - sx) * f, ah + (bh - ah) * f - sag * math.sin(math.pi * f), sz + (ez - sz) * f))
    bridge(name, pts)

decks6 = L.DECKS
for i in range(len(decks6) - 1):
    a, b = decks6[i], decks6[i + 1]
    if Z0 <= a[1] < Z1:                       # a bridge belongs to its first deck's row
        rope_bridge(f'core_walkway_{i + 1}{i + 2}', a, b)
# deck 1 down to the walkway's foot (the stair round the cedar at (102, 118) is the town's: c1_1)
sx, sz = deck_exit((94, 152), (101, 122))
bridge('core_walkway_foot', [(sx, 9.0, sz), (97.5, 7.4, 137.0), (101.0, 6.0, 122.0)])
# the walkway's foot (spec 3.9; the town did not build it): a stair from the bridge's end (6.0) east
# along z 120 down into the courtyard's west end (0.6), clear of the town's cedars at x 84 and 92
paths['core_walkway_stair'] = {'points': [[101.0, 6.0, 122.4], [101.0, 6.0, 120.0], [102.0, 6.0, 120.0], [116.0, 0.9, 120.0]],
                               'sweep': {'profile': SOLID(1.2, 6.5), 'materials': ['steps', 'steps', 'steps', 'steps'],
                                         'stairs': {'rise': 0.3}, 'caps': True}}
# deck 3 to the crown's landing
bridge('core_walkway_crown', [(77.4, 15.0, 210.4), (72.6, 15.0, 213.6)])

# canal bridges: the arched bridge at z 160 into the park, the plank bridge by the mill (z 203)
bridge('core_canal_arch', [(42.0, 0.8, 160), (48.0, 1.7, 160), (54.0, 1.15, 160)],
       profile=[[-1.5, -0.35], [-1.5, 0], [1.5, 0], [1.5, -0.35], [-1.5, -0.35]])
bridge('core_canal_planks', [(42.0, 0.8, 203.5), (54.0, 1.15, 203.5)],
       profile=[[-1.0, -0.3], [-1.0, 0], [1.0, 0], [1.0, -0.3], [-1.0, -0.3]])

# the zig-zag bridge from the east gate stair's foot to the pond's west bank
ZZ = [(222.0, 192.0), (220, 186), (216, 180), (222, 174), (218, 168), (224, 162), (220, 156)]
zpts = []
for (x0, z0), (x1, z1) in zip(ZZ, ZZ[1:]):
    n = max(1, int(math.hypot(x1 - x0, z1 - z0) // 2))
    for k in range(n):
        x, z = x0 + (x1 - x0) * k / n, z0 + (z1 - z0) * k / n
        zpts.append([x, z])
zpts.append(list(ZZ[-1]))
ys = [max(max(ground(x + ox, z + oz) for ox in (-0.8, 0, 0.8) for oz in (-0.8, 0, 0.8)) + 0.3, 0.6) for x, z in zpts]
for _ in range(2):                                    # smooth, never below the ground's clearance
    ys = [ys[0]] + [max(ys[i], (ys[i - 1] + 2 * ys[i] + ys[i + 1]) / 4) for i in range(1, len(ys) - 1)] + [ys[-1]]
bridge('core_zigzag', [(x, y, z) for (x, z), y in zip(zpts, ys)],
       profile=[[-0.9, -0.3], [-0.9, 0], [0.9, 0], [0.9, -0.3], [-0.9, -0.3]])

# trails (draped): the woods trail (R_WEST, kept 3.5 m clear of the deck trunks), the canal lane,
# the park path (R_CANAL)
TRAIL = {'profile': [[-2.0, -0.3], [-1.1, 0], [1.1, 0], [2.0, -0.3]], 'materials': ['earth', 'path', 'earth'], 'caps': True}
DRAPE = {'step': 4, 'bed': {'width': 3.0, 'depth': 0.3, 'falloff': 2}}
paths['core_trail_woods'] = {'points': [[97, 119], [100.4, 128.5], [101, 146], [87, 176], [74, 206], [84, 232], [96, 255.5]],
                             'drape': DRAPE, 'sweep': TRAIL}
paths['core_canal_lane'] = {'points': [[55, 119], [56, 128.5], [56, 158], [56.5, 162], [56, 200], [56, 255.5], [56, 276], [55.5, 290]],
                            'drape': DRAPE,
                            'sweep': dict(TRAIL, materials=['earth', 'lane', 'earth'])}
paths['core_park_path'] = {'points': [[38, 160], [30, 176], [22, 200], [24, 250], [23.6, 255.5]], 'drape': DRAPE,
                           'sweep': dict(TRAIL, materials=['earth', 'lane', 'earth'])}
# the stream (draped downhill into the pond), from where it enters the core rows
paths['core_stream'] = {'points': [[238.6, 255.5], [244, 232], [240, 198], [237, 186], [236.5, 179]],
                        'drape': {'step': 4, 'downhill': True, 'bed': {'width': 3.4, 'depth': 0.6, 'falloff': 2}},
                        'sweep': {'profile': [[-2.6, -0.6], [-1.7, 0], [1.7, 0], [2.6, -0.6]], 'material': 'water'}}

# rails: the lantern strings (torii top beam <-> side halls' ridges <-> the gate's lower roof)
def ridge_corner(h, toward):
    x1, z1, x2, z2 = h['top']
    return (min(max(toward[0], x1 + 0.3), x2 - 0.3), h['ridge'] + 0.1, min(max(toward[1], z1 + 0.3), z2 - 0.3))

rails = []
TORII_W, TORII_E = (155.0, 13.8, 124.0), (165.0, 13.8, 124.0)     # on the kasagi's top (town's torii, c2_1: 0.6 + 13.2)
GATE_W, GATE_E = (151.0, 12.3, gz - 5.0), (169.0, 12.3, gz - 5.0)  # lower roof's front corners
hw = ridge_corner(HALL_W, (134, 158)); he = ridge_corner(HALL_E, (186, 158))
for name, a, b in (('core_string_torii_w', TORII_W, hw), ('core_string_torii_e', TORII_E, he),
                   ('core_string_gate_w', hw, GATE_W), ('core_string_gate_e', he, GATE_E)):
    paths[name] = {'points': [[round(v, 3) for v in a], [round(v, 3) for v in b]], 'raised': True,
                   'sweep': dict(ROPE)}
    rails.append((name, a, b))
for name, a, b in rails:
    c = a if int(a[2] // 64) in ROWS else b
    entity('rail_' + name[5:], 'rail', c[0], c[1], c[2], params={'path': name})
    for k, f in enumerate((1 / 3, 2 / 3)):
        coin(f'{name[5:]}_{k}', a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f + 0.9, a[2] + (b[2] - a[2]) * f)
# (the viaduct's parapets over this span are the town's parapet rails, which run the whole line)

# ------------------------------------------------------------------ terrain: the core rows' field
ops = []
def cliff_set(rect, height, top, material='earth'):
    ops.append({'op': 'cliff', 'area': {'rect': list(rect)}, 'height': height, 'material': material})
    ops.append({'op': 'set', 'area': {'rect': list(rect)}, 'height': top})

cliff_set(TERR, 2.0, 5.0, 'canal_stone')
cliff_set(TEMPLE, 3.6, 8.6, 'canal_stone')
for t in range(9):
    cliff_set((CEM[0], CEM[1] + 12 * t, CEM[2], CEM[3]), 1.8, 1.8 * (t + 1), 'canal_stone')
ops.append({'op': 'bed', 'path': 'core_north_stair', 'width': 8.0, 'depth': 0.6, 'falloff': 2})
for rect, m in (((110, 128, 210, 166), 'gravel'), (TERR, 'ashlar'), (TEMPLE, 'podium'), ((0, 128, 44, 206), 'grass'),
                (CEM, 'cemetery'), ((0, 206, 44, 256), 'bamboo_floor')):
    ops.append({'op': 'paint', 'area': {'rect': list(rect)}, 'material': m})
for (x, z, r) in L.POND:
    ops.append({'op': 'water', 'area': {'circle': [x, z, round(r * 1.12, 2)]}, 'level': 0.0, 'material': 'water'})

heights = []
for zi in range(Z0, Z1 + 1, 2):
    heights.append(' '.join(f'{file_height(float(x), float(zi)):.2f}' for x in range(0, 321, 2)))

field = {'heights': 'parts/core_heights.txt', 'spacing': 2, 'min': [0, Z0], 'max': [320, Z1],
         'material': 'floor', 'steep': {'degrees': 38, 'material': 'earth'}, 'tolerance': 0.15, 'tile': 16,
         'lod': {'distance': 22, 'tolerance': 2.5}, 'operations': ops}

# ------------------------------------------------------------------ scatter: grey trees
add_asset('gbc_tree_cedar', [(0, 6.0, 0, 0.8, 12.0, 0.8, 'trunk', True), (0, 16.0, 0, 5, 14, 5, 'cedar', False)])
add_asset('gbc_trunk_cedar_col', [(0, 6.0, 0, 0.8, 12.0, 0.8, 'trunk', True)])
add_asset('gbc_tree_maple', [(0, 1.75, 0, 0.5, 3.5, 0.5, 'trunk', True), (0, 6.0, 0, 6, 5, 6, 'maple', False)])
add_asset('gbc_trunk_maple_col', [(0, 1.75, 0, 0.5, 3.5, 0.5, 'trunk', True)])
add_asset('gbc_bamboo', [(0, 5.0, 0, 0.5, 10.0, 0.5, 'bamboo', True), (0.9, 4.5, 0.6, 0.4, 9.0, 0.4, 'bamboo', True)])


def tree_lod(name, mat, cy, size, height, d1, d2, cull=None):
    """Grey trees' levels: the canopy box alone from d1, a three-sided cone from d2 (the real
    foliage has two crossed cards from about 50 m)."""
    lv = [{'distance': d1, 'nodes': [{'id': 'canopy', 'op': 'box', 'size': [size, height, size], 'open': ['bottom'],
                                      'material': mat, 'transform': {'translate': [0, cy, 0]}}]},
          {'distance': d2, 'nodes': [{'id': 'far', 'op': 'cone', 'radius': size * 0.7, 'height': height * 1.6,
                                      'segments': 3, 'caps': False, 'material': mat,
                                      'transform': {'translate': [0, cy, 0]}}]}]
    assets[name]['lod'] = {'levels': lv, **({'cull': cull} if cull else {})}

tree_lod('gbc_tree_cedar', 'cedar', 16.0, 5, 14, 40, 90)
tree_lod('gbc_tree_maple', 'maple', 6.0, 6, 5, 36, 80)
tree_lod('gbc_tree_ginkgo', 'ginkgo', 7.0, 6, 6, 36, 80)
assets['gbc_bamboo']['lod'] = {'levels': [{'distance': 30, 'nodes': [
    {'id': 'far', 'op': 'cone', 'radius': 0.8, 'height': 10, 'segments': 3, 'caps': False, 'material': 'bamboo',
     'transform': {'translate': [0, 5, 0]}}]}], 'cull': 100}
deck_excl = [{'circle': [x, z, 6.0]} for x, z, h in DECKS + [L.CROWN]]
built_excl = [{'rect': [110, 118, 216, 238]}, {'rect': [154, 232, 178, 258]}, {'circle': [178, 262, 12]}, {'rect': [CEM[0] - 2, 118, 320, 256]},
              {'rect': [0, 118, 60, 206]}] + [{'circle': [x, z, r * 1.25]} for x, z, r in L.POND]
TREES = [{'asset': 'gbc_tree_cedar', 'weight': 3, 'collision': 'gbc_trunk_cedar_col'},
         {'asset': 'gbc_tree_maple', 'weight': 2, 'collision': 'gbc_trunk_maple_col'}]
THIN = {'distance': 56, 'keep': 0.5, 'scale': 1.2}                 # as the shrine's forests
scatter = {
    'core_woods': {'assets': TREES, 'area': {'rect': [56, Z0, 216, Z1]}, 'spacing': 9, 'fill': 0.8, 'seed': 31,
                   'lift': -0.15, 'exclude': built_excl + deck_excl, 'clearance': 1.6, 'max_slope': 36, 'chunk': 16,
                   'lod': 'assets', 'thin': THIN},
    'core_valley': {'assets': TREES, 'area': {'rect': [210, Z0, 256, Z1]}, 'spacing': 9, 'fill': 0.75, 'seed': 37,
                    'lift': -0.15, 'exclude': [{'circle': [x, z, r * 1.25]} for x, z, r in L.POND] + [{'rect': [210, 160, 228, 196]}],
                    'clearance': 1.6, 'max_slope': 36, 'chunk': 16, 'lod': 'assets', 'thin': THIN},
    'core_bamboo': {'assets': [{'asset': 'gbc_bamboo', 'collision': 'self'}], 'area': {'rect': [0, 206, 44, Z1]},
                    'spacing': 6, 'fill': 0.7, 'seed': 41, 'exclude': [{'rect': [3, 209, 27, 227]}],
                    'clearance': 1.2, 'max_slope': 36, 'chunk': 16, 'lod': 'assets'},
}

layers = {'gate_b_barred': {'group': 'gate_b', 'on': True}, 'gate_b_open': {'group': 'gate_b'}}

parts = {'paths': paths, 'layers': layers,
         'terrain': {'materials': TERRAIN_MAT, 'fields': {'core': field}},
         'scatter': scatter}

# the placement zones (place/ZONE.py) change the cells and the part before they are written
sys.path.insert(0, TOWN)
from place import apply as apply_zones
apply_zones('core', globals())

# ------------------------------------------------------------------ write
os.makedirs(HERE, exist_ok=True)
for f in os.listdir(HERE):
    if f.startswith('gbc_') and f.endswith('.asset.json'): os.remove(os.path.join(HERE, f))
for name, r in assets.items():
    with open(os.path.join(HERE, name + '.asset.json'), 'w') as fh: json.dump(r, fh, indent=1); fh.write('\n')
os.makedirs(os.path.join(TOWN, 'cells'), exist_ok=True)
for c in range(5):
    for r in ROWS:
        cid = f'c{c}_{r}'
        cell = {'format': 'mei-world-cell', 'version': 1, 'id': cid, 'at': [c, r], 'region': L.region_of(c, r),
                'placements': placements.get(cid, []), 'entities': entities.get(cid, [])}
        with open(os.path.join(TOWN, 'cells', cid + '.cell.json'), 'w') as fh: json.dump(cell, fh, indent=1); fh.write('\n')
os.makedirs(os.path.join(TOWN, 'parts'), exist_ok=True)
with open(os.path.join(TOWN, 'parts', 'core.json'), 'w') as fh: json.dump(parts, fh, indent=1); fh.write('\n')
with open(os.path.join(TOWN, 'parts', 'core_heights.txt'), 'w') as fh:
    fh.write(f'# core rows z {Z0}..{Z1} (rows), x 0..320, every 2 m; written by assets/greybox/core/gen_core.py\n')
    fh.write('\n'.join(heights) + '\n')


print(json.dumps({'assets': len(assets), 'placements': {k: len(v) for k, v in sorted(placements.items())},
                  'entities': {k: len(v) for k, v in sorted(entities.items())}, 'paths': len(paths),
                  'stones': len(STONES), 'problems': problems}, indent=1))
