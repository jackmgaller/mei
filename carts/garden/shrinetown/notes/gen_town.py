#!/usr/bin/env python3
"""Shrine town grey box, region `town` (rows z 0-128, cells c*_0 and c*_1).

Writes, under carts/garden/shrinetown/:
  assets/greybox/town/gbt_*.asset.json   box recipes (and their _col companions), coins
  cells/c{0..4}_{0,1}.cell.json          placements and entities of the town's ten cells
  parts/town.json                        world-level entries: paths (rails), layers, terrain
                                         materials and operations, vantage points
  parts/town_heights.txt                 the ground of these rows (layout.height), for make_world.py
  notes/town_checks.json                 the jump and glide checks this script computes

Coordinates and heights come from the plan's layout.py (import, not a fork): pass its path with
--layout, or put it at carts/garden/shrinetown/layout.py. Where the grey box departs from it,
the change is in this file with a comment and in notes/town.md.

Buildings are boxes at their final footprint, height and collision. Their render meshes carry
the triangle budget of the asset that will replace them (spec 8.2 and assets.md), as a grid of
patches on every face, with the same levels of detail, so the World Checker's numbers for a view
are the numbers the real assets will cost; collision is a plain box (`_col`).
"""
import argparse, importlib.util, json, math, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE.parent                                   # carts/garden/shrinetown
ap = argparse.ArgumentParser()
ap.add_argument('--layout', default=os.environ.get('SHRINETOWN_LAYOUT', str(ST / 'layout.py')))
ap.add_argument('--plain', action='store_true', help='boxes as plain boxes (10 triangles), no budget weights')
args = ap.parse_args()
spec = importlib.util.spec_from_file_location('layout', args.layout)
L = importlib.util.module_from_spec(spec); spec.loader.exec_module(L)

ROW_MAX = 128.0                                    # the town's rows end here
ASSETS = ST / 'assets' / 'greybox' / 'town'
CELLS = ST / 'cells'
PARTS = ST / 'parts'
for d in (ASSETS, CELLS, PARTS): d.mkdir(parents=True, exist_ok=True)

def r3(v): return round(v, 3)

# ------------------------------------------------------------------ asset recipes
VERIFY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}

# budgets: (L0, L1, d1, L2, d2) triangles at level 0, level 1 from d1, level 2 from d2
KIND = {
    'shop2':   (250, 70, 20, 20, 50),            # spec 8.2 shop
    'shop3':   (300, 70, 20, 20, 50),            # assets.md town_shop_3f
    'alley':   (120, 30, 16, 12, 40),
    'machiya': (200, 50, 20, 14, 50),
    'hero':    (600, 200, 24, 40, 60),
    'tree':    (90, 30, 20, 12, 50),             # tree_zelkova 90
    'span':    (120, 40, 48, 12, 100),           # viaduct_span_16
    'plain':   None,
}

recipes = {}            # name -> recipe
recipe_keys = {}        # key -> name
solids = []             # (x1, z1, x2, z2, top) for floor lookups (coins, checks)

def ndiv(length, cell):
    return 1 if cell is None else max(1, math.ceil(length / cell - 1e-6))

def grid_box(cx, cz, sx, sz, y0, y1, cell, mat, top_mat):
    """A box open at the bottom, every face cut into a grid of patches about `cell` units across
    (None: one patch). The count on an edge depends only on its length, so neighbouring faces share
    their edge points (no T-junctions)."""
    x0, z0 = cx - sx / 2, cz - sz / 2
    sy = y1 - y0
    vid, verts, faces, fm = {}, [], [], []
    def v(p):
        k = tuple(r3(c) for c in p)
        if k not in vid: vid[k] = len(verts); verts.append(list(k))
        return vid[k]
    def face(o, u, w, m):                       # u x w points outward
        nu, nw = ndiv(math.sqrt(sum(c * c for c in u)), cell), ndiv(math.sqrt(sum(c * c for c in w)), cell)
        P = lambda i, j: [o[k] + u[k] * i / nu + w[k] * j / nw for k in range(3)]
        for i in range(nu):
            for j in range(nw):
                faces.append([v(P(i, j)), v(P(i + 1, j)), v(P(i + 1, j + 1)), v(P(i, j + 1))]); fm.append(m)
    face((x0, y1, z0 + sz), (sx, 0, 0), (0, 0, -sz), top_mat)          # top
    face((x0, y0, z0), (0, sy, 0), (sx, 0, 0), mat)                     # -z
    face((x0, y0, z0 + sz), (sx, 0, 0), (0, sy, 0), mat)                # +z
    face((x0, y0, z0), (0, 0, sz), (0, sy, 0), mat)                     # -x
    face((x0 + sx, y0, z0), (0, sy, 0), (0, 0, sz), mat)                # +x
    return (verts, faces), fm

def box_tris(sx, sy, sz, cell):
    nx, ny, nz = ndiv(sx, cell), ndiv(sy, cell), ndiv(sz, cell)
    return 2 * (nx * nz + 2 * nx * ny + 2 * nz * ny)

def orient(verts, faces):
    """Turn every face of a convex part outward (from the part's centroid)."""
    c = [sum(v[k] for v in verts) / len(verts) for k in range(3)]
    out = []
    for f in faces:
        p = [verts[i] for i in f]
        a, b, d = p[0], p[1], p[2]
        u = [b[k] - a[k] for k in range(3)]; w = [d[k] - a[k] for k in range(3)]
        n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
        fc = [sum(q[k] for q in p) / len(p) for k in range(3)]
        if sum(n[k] * (fc[k] - c[k]) for k in range(3)) < 0: f = list(reversed(f))
        out.append(f)
    return out

def hexa(pts, mat, open_bottom=False):
    """A convex hexahedron: pts = 4 bottom corners then the 4 above them, in the same order."""
    faces = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    if open_bottom: faces = faces[1:]
    verts = [[r3(c) for c in p] for p in pts]
    return (verts, orient(verts, faces)), [mat] * len(faces)

def prism(poly, z0, z1, mat):
    """A polygon in (x, y), counter-clockwise or not, extruded along z from z0 to z1."""
    n = len(poly)
    area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
    if area < 0: poly = list(reversed(poly))           # counter-clockwise seen from +z
    verts = [[r3(x), r3(y), r3(z0)] for x, y in poly] + [[r3(x), r3(y), r3(z1)] for x, y in poly]
    faces = [list(range(n, 2 * n)), list(reversed(range(n)))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    return (verts, faces_out(verts, faces, poly)), [mat] * len(faces)

def faces_out(verts, faces, poly):
    out = []
    n = len(poly)
    for k, f in enumerate(faces):
        if k == 0: want = (0, 0, 1)
        elif k == 1: want = (0, 0, -1)
        else:
            i = k - 2; j = (i + 1) % n
            dx, dy = poly[j][0] - poly[i][0], poly[j][1] - poly[i][1]
            want = (dy, -dx, 0)
        a, b, d = (verts[f[0]], verts[f[1]], verts[f[2]])
        u = [b[q] - a[q] for q in range(3)]; w = [d[q] - a[q] for q in range(3)]
        nn = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
        if sum(nn[q] * want[q] for q in range(3)) < 0: f = list(reversed(f))
        out.append(f)
    return out

def mesh_node(nid, verts_faces_mats):
    (verts, faces), mats = verts_faces_mats[0], verts_faces_mats[1]
    return {'id': nid, 'op': 'mesh', 'vertices': verts, 'faces': faces, 'face_materials': mats}

def part_mesh(nid, part, cell):
    kind = part[0]
    if kind == 'box':
        _, cx, y0, cz, sx, sy, sz, mat, top = part[:9]
        (v, f), m = grid_box(cx, cz, sx, sz, y0, y0 + sy, cell, mat, top)
        return {'id': nid, 'op': 'mesh', 'vertices': v, 'faces': f, 'face_materials': m}
    if kind == 'hexa':
        _, pts, mat = part[:3]
        (v, f), m = hexa(pts, mat)
        return {'id': nid, 'op': 'mesh', 'vertices': v, 'faces': f, 'face_materials': m}
    if kind == 'prism':
        _, poly, z0, z1, mat = part[:5]
        (v, f), m = prism(poly, z0, z1, mat)
        return {'id': nid, 'op': 'mesh', 'vertices': v, 'faces': f, 'face_materials': m}
    raise ValueError(kind)

def tri_count(parts, cell):
    n = 0
    for p in parts:
        n += box_tris(p[4], p[5], p[6], cell) if p[0] == 'box' else (12 if p[0] == 'hexa' else 4 * len(p[1]) - 4)
    return n

def cell_for(parts, target):
    """The patch size whose triangle count is nearest the target (None: plain boxes)."""
    if tri_count(parts, None) >= target: return None
    lo, hi = 0.05, 200.0
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        if tri_count(parts, mid) > target: lo = mid
        else: hi = mid
    best = min((lo, hi), key=lambda c: abs(tri_count(parts, c) - target))
    return r3(best) if best < 199 else None

def make_recipe(label, parts, colours, kind='plain', budget_l0=None, tags=None, collide=True, cull=None):
    """parts in asset space (origin: footprint centre at the base). Returns (name, collision)."""
    key = json.dumps([parts, colours, kind, budget_l0, tags, collide, cull], sort_keys=True)
    if key in recipe_keys: return recipe_keys[key]
    name = f'gbt_{label}'
    k = 2
    while name in recipes: name = f'gbt_{label}_{k}'; k += 1
    mats = {m: {'color': c, 'palette': True} for m, c in colours.items()}
    for m, t in (tags or {}).items(): mats[m]['tag'] = t
    spec_k = KIND[kind] if not args.plain else None
    if budget_l0 and spec_k: spec_k = (budget_l0,) + spec_k[1:]
    b0 = cell_for(parts, spec_k[0]) if spec_k else None
    nodes = [part_mesh(f'p{i}', p, b0) for i, p in enumerate(parts)]
    t0 = tri_count(parts, b0)
    rec = {'format': 'mei-asset', 'version': 1, 'name': name, 'materials': mats, 'lighting': LIGHT,
           'verification': VERIFY, 'budget': {'triangles': max(t0, 16)}, 'nodes': nodes}
    if spec_k:
        levels = []
        prev = t0
        for tgt, dist in ((spec_k[1], spec_k[2]), (spec_k[3], spec_k[4])):
            b = cell_for(parts, tgt)
            t = tri_count(parts, b)
            if t >= prev: continue
            levels.append({'distance': dist, 'nodes': [part_mesh(f'p{i}', p, b) for i, p in enumerate(parts)]})
            prev = t
        if levels or cull:
            rec['lod'] = {'levels': levels} if levels else {}
            if cull: rec['lod']['cull'] = cull
    elif cull:
        rec['lod'] = {'cull': cull}
    recipes[name] = rec
    col = 'none'
    if collide:
        if b0 is None and not spec_k:
            col = 'self'
        else:
            cparts = [part_mesh(f'p{i}', p, None) for i, p in enumerate(parts)]
            cm = {m: {'color': '#ffffff', 'palette': True} for m in colours}
            for m, t in (tags or {}).items(): cm[m]['tag'] = t
            recipes[name + '_col'] = {'format': 'mei-asset', 'version': 1, 'name': name + '_col', 'materials': cm,
                                      'lighting': LIGHT, 'verification': VERIFY, 'nodes': cparts}
            col = name + '_col'
    recipe_keys[key] = (name, col)
    return name, col

# ------------------------------------------------------------------ cells
cells = {}
entities_n = set()

def cell_of(x, z):
    i, j = int(x // 64), int(z // 64)
    assert 0 <= i < 5 and 0 <= j < 2, (x, z)
    return f'c{i}_{j}', (i, j)

def cell(cid, at):
    if cid not in cells:
        cells[cid] = {'format': 'mei-world-cell', 'version': 1, 'id': cid, 'at': list(at),
                      'region': L.region_of(*at), 'placements': [], 'entities': []}
    return cells[cid]

def place(pid, name_col, x, y, z, yaw=0, layer=None):
    cid, at = cell_of(x, z)
    c = cell(cid, at)
    ids = {p['id'] for p in c['placements']}
    base, k = pid, 2
    while pid in ids: pid = f'{base}_{k}'; k += 1
    p = {'id': pid, 'asset': name_col[0], 'position': [r3(x), r3(y), r3(z)]}
    if yaw: p['yaw'] = r3(yaw)
    if layer: p['layer'] = layer
    p['collision'] = name_col[1]
    c['placements'].append(p)

def entity(eid, etype, x, y, z, params=None, asset=None, layer=None, yaw=None):
    assert eid not in entities_n, eid
    entities_n.add(eid)
    cid, at = cell_of(x, z)
    e = {'id': eid, 'type': etype, 'position': [r3(x), r3(y), r3(z)]}
    if yaw is not None: e['yaw'] = yaw
    if asset: e['asset'] = asset
    if layer: e['layer'] = layer
    if params is not None: e['params'] = params
    cell(cid, at)['entities'].append(e)

def block(pid, x1, z1, x2, z2, base, top, wall, roof=None, kind='plain', budget=None, label=None, layer=None,
          tags=None, solid=True):
    """An axis-aligned building or block: footprint, base and top height, wall and roof colours."""
    sx, sz, sy = x2 - x1, z2 - z1, top - base
    parts = [('box', 0.0, 0.0, 0.0, r3(sx), r3(sy), r3(sz), 'wall', 'roof')]
    nc = make_recipe(label or pid, parts, {'wall': wall, 'roof': roof or wall}, kind, budget, tags)
    place(pid, nc, (x1 + x2) / 2, base, (z1 + z2) / 2, layer=layer)
    if solid: solids.append((x1, z1, x2, z2, top))
    return top

def compound(pid, label, x, y, z, parts_world, colours, kind='plain', budget=None, tags=None, yaw=0, cull=None):
    """Parts given in world coordinates around the placement's (x, y, z); placed at yaw 0."""
    parts = []
    for p in parts_world:
        if p[0] == 'box':
            _, x1, y1, z1, x2, y2, z2, mat, top = p
            parts.append(('box', r3((x1 + x2) / 2 - x), r3(y1 - y), r3((z1 + z2) / 2 - z), r3(x2 - x1), r3(y2 - y1),
                          r3(z2 - z1), mat, top))
            solids.append((x1, z1, x2, z2, y2))
        elif p[0] == 'prism':
            _, poly, z0, z1, mat = p
            parts.append(('prism', [[r3(a - x), r3(b - y)] for a, b in poly], r3(z0 - z), r3(z1 - z), mat))
        else:
            _, pts, mat = p
            parts.append(('hexa', [[r3(a - x), r3(b - y), r3(c - z)] for a, b, c in pts], mat))
    nc = make_recipe(label, parts, colours, kind, budget, tags, cull=cull)
    place(pid, nc, x, y, z, yaw)
    return nc

def slab_ramp(x1, z1, x2, z2, y_start, y_end, axis, mat='wall', t=0.3):
    """A sloped walkway slab over the rectangle, rising along +axis ('x' or 'z') or falling if y_end < y_start;
    its top runs from y_start at the low coordinate to y_end at the high one."""
    if axis == 'z':
        top = [(x1, y_start, z1), (x2, y_start, z1), (x2, y_end, z2), (x1, y_end, z2)]
    else:
        top = [(x1, y_start, z1), (x2, y_end, z1), (x2, y_end, z2), (x1, y_start, z2)]
    bot = [(a, b - t, c) for a, b, c in top]
    return ('hexa', bot + top, mat)

def flat_slab(x1, z1, x2, z2, y, mat='wall', t=0.3):
    return ('box', x1, y - t, z1, x2, y, z2, mat, mat)

def ramp_ext(x1, z1, x2, z2, y0, y1, axis, e0=0.0, e1=0.0, mat='stair', t=0.3):
    """slab_ramp from y0 at the low end to y1 at the high end, run on past either end by e0, e1 (same slope),
    so that it ends inside the landing it meets instead of on its face."""
    run = (z2 - z1) if axis == 'z' else (x2 - x1)
    k = (y1 - y0) / run
    if axis == 'z': return slab_ramp(x1, z1 - e0, x2, z2 + e1, y0 - k * e0, y1 + k * e1, 'z', mat, t)
    return slab_ramp(x1 - e0, z1, x2 + e1, z2, y0 - k * e0, y1 + k * e1, 'x', mat, t)
def landing(x1, z1, x2, z2, y, mat='stair'):
    return flat_slab(x1 - .1, z1 - .1, x2 + .1, z2 + .1, y, mat, 0.5)

# ------------------------------------------------------------------ colours (flat, a hue per zone)
C = dict(
    shop_w='#c8bca4', shop_r='#5a6068',            # shotengai: warm plaster, grey tile
    alley_w='#9a8c7a', alley_r='#3a3c44',          # alleys: brown-grey, dark tile
    mach_w='#7a5a40', mach_r='#3a3c44',            # machiya: dark wood
    conc='#c8c4b8', concd='#a8a69e', red='#c43026', redd='#a8321e',
    station='#7a8a70', canopy='#56685a', konbini='#dfe3e8', koban='#3a6ab0', bus='#b4ae9e',
    danchi='#c8c4b8', pachinko='#d88aa0', building='#b8b0a0', fire='#a8321e', dagashi='#b08a5e',
    sento='#7a5a48', chimney='#8a8478', school='#d8d4c8', gym='#8a9a80', overpass='#5a8a60',
    arcade='#a8c0cc', gate='#c8402a', awning='#e0502a', pole='#6a665e', fence='#8e887c',
    trunk='#4a3a2e', cedar='#2e4a2e', maple='#c8301e', ginkgo='#f0c030', zelkova='#5f7a34',
    tank='#dce8f0', sign='#f0c030', viaduct='#b0aca2', parapet='#d0ccc2', ladder='#40a060',
)

# ------------------------------------------------------------------ 3.1 station and plaza
# The viaduct (spans along layout.VIADUCT, rows 0-1 only): deck 9.0 (1.5 thick), parapets to
# 10.2 (0.3 wide, 5.85 m off the centre line), a pier 1.6 x 8 under the middle of each span.
VD, VW = L.VIADUCT_DECK, L.VIADUCT_W
POFF = VW / 2 - 0.15
vpts = [p for p in L.VIADUCT]
# the town builds the segments whose middle lies in its rows; the last town segment ends at
# (306, 134): the crossing point with the core region (notes)
segs = [(a, b) for a, b in zip(vpts, vpts[1:]) if (a[1] + b[1]) / 2 < ROW_MAX]
span_list = []                                     # (cx, cz, yaw, length, s0, s1, seg index)
for si, (a, b) in enumerate(segs):
    Ls = math.hypot(b[0] - a[0], b[1] - a[1])
    n = max(1, round(Ls / 16))
    for k in range(n):
        t0, t1 = k / n, (k + 1) / n
        cx = a[0] + (b[0] - a[0]) * (t0 + t1) / 2; cz = a[1] + (b[1] - a[1]) * (t0 + t1) / 2
        yaw = math.degrees(math.atan2(b[0] - a[0], b[1] - a[1]))
        span_list.append((cx, cz, yaw, Ls / n, si, k, n))

STATION_X = (136, 184)
STAIRS = [(150, 154), (170, 174)]                  # plaza stairs (x ranges), z 32 -> 14, 0 -> 9
STATION_GAP = (146.0, 178.0)                       # the north parapet is open here (the stairs arrive)
# The deck and the parapets are swept along the line (paths with a sweep: exact mitres at the
# bends, collision from the kit); each 16 m span is a placement carrying a pier and two girders
# under the deck, with viaduct_span_16's budget, so views count its placements and triangles.
for idx, (cx, cz, yaw, ln, si, k, n) in enumerate(span_list):
    over_road = L.ROAD[1] - 2 < cz < L.ROAD[3] + 2 and cx > 280
    parts = [('box', x, VD - 2.6, 0.0, 0.8, 1.05, r3(ln - 0.4), 'girder', 'girder') for x in (-4.0, 4.0)]
    if not over_road:
        parts.append(('box', 0.0, 0.0, 0.0, 8.0, VD - 2.6, 1.6, 'pier', 'pier'))
    lab = f'viaduct_{"road_" if over_road else ""}{int(round(ln * 10))}'
    nc = make_recipe(lab, parts, {'girder': C['viaduct'], 'pier': C['viaduct']}, 'span')
    place(f'viaduct_{idx}', nc, cx, 0.0, cz, yaw)
# station: concourse under the deck (station_concourse 800 + ticket_gates 400), platform canopy
# (station_platform 900) with its posts; the platform is the deck (9.0)
block('station_concourse', 136, 3, 184, 13, 0, 5.0, C['station'], C['station'], 'hero', 1200, 'station_concourse')
compound('station_platform', 'station_platform', 160, VD, 8,
         [('box', 140, 12.4, 5, 180, 12.8, 11, 'canopy', 'canopy')] +
         [('box', px - .2, VD, 7.8, px + .2, 12.4, 8.2, 'post', 'post') for px in (146, 154, 166, 174)],
         {'canopy': C['canopy'], 'post': C['pole']}, 'hero', 900)
for k, (x0, x1) in enumerate(STAIRS):
    compound(f'station_stair_{k}', 'station_stair', (x0 + x1) / 2, 0, 23,
             [ramp_ext(x0, 14, x1, 32, VD, 0.0, 'z', 0.3, 0.0, 'stair', 0.4)], {'stair': C['concd']})
SPAWN = L.SPAWN
entity('spawn', 'spawn', SPAWN[0], 0.0, SPAWN[1], {'yaw': 0})
block('konbini', 178, 18, 214, 32, 0, 5.6, C['konbini'], '#b8bcc4', 'hero', 300, 'konbini')
block('konbini_sign', 193, 29.6, 199, 30.4, 5.6, 7.0, C['sign'], label='konbini_sign')
block('vending', 176.9, 29.0, 177.9, 30.6, 0, 1.9, '#d83a30', label='vending', budget=24)
block('koban', 116, 18, 128, 28, 0, 5.9, C['koban'], '#2c4a80', 'hero', 300, 'koban')
block('bus_stop', 136, 34, 144, 37, 0, 2.6, C['bus'], '#8e887c', 'hero', 150, 'bus_stop')
block('danchi', 70, 18, 86, 34, 0, 18.8, C['danchi'], '#a8a69e', 'hero', 600, 'danchi')
block('danchi_tank', 76, 24, 80, 28, 18.8, 20.8, C['tank'], label='danchi_tank')
block('pachinko', 92, 18, 108, 34, 0, 9.1, C['pachinko'], '#a86a80', 'hero', 450, 'pachinko')
# the danchi's outside stair: four flights of 4.7 m round the block (16-21 degrees), landings
# at the corners, the last flight arriving beside the roof's south-west corner
compound('danchi_stair', 'danchi_stair', 78, 0, 26, [
    ramp_ext(67, 18, 70, 34, 0.0, 4.7, 'z', 0, .3),
    landing(67, 34, 70, 37, 4.7),
    ramp_ext(70, 34.0, 86, 36.9, 4.7, 9.4, 'x', .3, .3),
    landing(86, 34, 89, 37, 9.4),
    ramp_ext(86.0, 18, 88.9, 34, 14.1, 9.4, 'z', .3, .3),
    landing(86, 15, 89, 18, 14.1),
    ramp_ext(74, 15.1, 86, 18.0, 18.8, 14.1, 'x', .3, .3),
    landing(70, 15, 74, 18, 18.8),
], {'stair': C['concd']})

# ------------------------------------------------------------------ 3.2 shotengai
SHOP_TOPS = {}
for i, z in enumerate(range(44, 104, 10)):
    hw = 9.5 if i in (1, 5) else 6.5
    he = 9.5 if i in (2, 5) else 6.5
    for side, (x1, x2), h in (('w', (140, 154), hw), ('e', (166, 180), he)):
        kind = 'shop3' if h > 7 else 'shop2'
        block(f'shop_{side}{i}', x1, z + .5, x2, z + 9.5, 0, h, C['shop_w'], C['shop_r'], kind, label=kind)
        SHOP_TOPS[(side, i)] = h
# the arcade roof (arcade_roof_16 x 2): eaves 7.0 at x 152 and 168, ridge 8.5 on the axis
# (10.6 degrees), 0.3 thick
compound('arcade_roof', 'arcade_roof', 160, 7.0, 78, [
    ('prism', [(152, 6.7), (160, 8.2), (168, 6.7), (168, 7.0), (160, 8.5), (152, 7.0)], 62, 94, 'roof')] +
    [('box', 155, 6.3, zz - .1, 165, 6.6, zz + .1, 'rib', 'rib') for zz in range(64, 94, 4)],
    {'roof': C['arcade'], 'rib': '#6a7a84'}, 'hero', 400)
solids.append((152, 62, 168, 94, 8.5))
# arcade gates (arcade_gate): two posts on the street's edges, a beam 7.0-8.3 over the street
for k, zz in enumerate((60, 96)):
    compound(f'arcade_gate_{k}', 'arcade_gate', 160, 0, zz + 1, [
        ('box', 154, 0, zz, 155, 7.0, zz + 2, 'gate', 'gate'),
        ('box', 165, 0, zz, 166, 7.0, zz + 2, 'gate', 'gate'),
        ('box', 152, 7.0, zz, 168, 8.3, zz + 2, 'gate', 'gate')], {'gate': C['gate']}, 'hero', 300)
# six awnings at 2.6 tagged bounce (+4.5 m), each landing on its own 6.5 m roof. Three on the
# street south of the arcade (the only 6.5 m shops not under it: under the arcade a bounce hits
# its underside at 6.7), three on the service lanes behind shops under the arcade.
AWNINGS = [('w0', 154, 155.5, 44.5), ('e0', 164.5, 166, 44.5), ('e1', 164.5, 166, 54.5),
           ('w2b', 138.5, 140, 64.5), ('e3b', 180, 181.5, 74.5), ('w4b', 138.5, 140, 84.5)]
for nm, x1, x2, z in AWNINGS:
    block(f'awning_{nm}', x1, z + .5, x2, z + 8.5, 2.3, 2.6, C['awning'], label='awning', tags={'roof': 'bounce', 'wall': 'bounce'})
entity('cam_arcade', 'camera_zone', 160, 0, 78, {'size': [12, 7, 32], 'mode': 'follow'})

# the building with the fire escape (street_building, 450): x 186-200, z 44-102, 18.3
block('building', 186, 44, 200, 102, 0, 18.3, C['building'], '#8e887c', 'hero', 450, 'building')
# its fire escape, grey box: one 27-degree ramp up the east face from the school lane (z 44)
# to the roof at z 80 (street_building's stair is a switchback at its end; same heights)
compound('building_escape', 'building_escape', 201.25, 0, 62, [slab_ramp(200, 44, 202.5, 80, 0.0, 18.3, 'z', 'stair')],
         {'stair': C['concd']})
# shortcut E: the drop ladder on the north face (layer ladder_e), a pole when down
block('ladder_e', 199.0, 102.0, 200.0, 102.2, 0, 17.9, C['ladder'], label='ladder_e', layer='ladder_e', solid=False)
entity('pole_ladder_e', 'pole', 199.5, 0, 102.6, {'height': 18.3, 'front': True}, layer='ladder_e')   # climbed from the north

# ------------------------------------------------------------------ 3.3 back alleys
# layout.py's loop makes rows z 44..99; the z 99 row (99-107.5) runs 3.5 m into the front road
# (z 104), and the spec counts 24 houses: rows 44..88 give exactly 24. The z 99 row is left out.
k = 0
for b in L.boxes:
    x1, z1, x2, z2, base, top, col, lab = b
    if not (66 <= x1 < 136 and 44 <= z1 < 102 and abs((x2 - x1) - 9.5) < .01): continue
    if z1 >= 99: continue
    block(f'alley_{int(x1)}_{int(z1)}', x1, z1, x2, z2, 0, top, C['alley_w'], C['alley_r'], 'alley', label='alley')
    k += 1
ALLEY_HOUSES = k
block('fire_tower', 99, 71, 105, 77, 0, 15.2, C['fire'], '#6a2418', 'hero', 600, 'fire_tower')
entity('pole_fire_tower', 'pole', 102, 0, 70.55, {'height': 15.2})
# The spec's kick pair ("the house 3 m east") needs a wall 3 m from the tower; the nearest house
# is 9 m away. A storehouse (kura) in the yard, 8.0 m, 3 m east of the tower: kicks off both.
block('fire_kura', 108, 70, 111, 78, 0, 8.0, '#ece4d2', C['alley_r'], 'alley', label='kura')
block('dagashi', 126, 44, 131, 49, 0, 4.4, C['dagashi'], '#6a4a30', 'hero', 400, 'dagashi')
# camera zones: the alleys are narrower than the camera's distance (6.5 m)
for k, x in enumerate((75.5, 87.5, 99.5, 111.5, 123.5)):
    entity(f'cam_alley_ns{k}', 'camera_zone', x + 1.25, 0, 70.25, {'size': [2.5, 12, 52.5], 'mode': 'rail', 'look': [0, 0, 1]})
for k, z in enumerate((52.5, 63.5, 74.5, 85.5)):
    entity(f'cam_alley_ew{k}', 'camera_zone', 100.75, 0, z + 1.25, {'size': [69.5, 12, 2.5], 'mode': 'rail', 'look': [1, 0, 0]})
entity('cam_lane_w', 'camera_zone', 137.75, 0, 74, {'size': [4.5, 12, 60], 'mode': 'rail', 'look': [0, 0, 1]})

# ------------------------------------------------------------------ 3.4 canal and machiya
# layout.py's machiya loop (z 18..102 by 12, skipping 56-78) puts the z 54 row into the sento
# (z 60-73) and the z 102 row into the front road. Rows here: 18, 30, 42 (to 52), then 78, 90.
MACHIYA = 0
for z in (18, 30, 42, 78, 90):
    block(f'machiya_w{z}', 4, z, 18, z + 10, 0, 7.5, C['mach_w'], C['mach_r'], 'machiya', label='machiya_a')
    block(f'machiya_e{z}', 24, z, 40, z + 10, 0, 7.0, C['mach_w'], C['mach_r'], 'machiya', label='machiya_b')
    MACHIYA += 2
block('sento', 8, 60, 30, 73, 0, 8.0, C['sento'], '#3e4248', 'hero', 700, 'sento')
# The chimney is reached by a ladder from the boiler room's roof (5 m), so it stands at the
# sento's east wall over the boiler room: (30.5, 67.5) instead of layout's (23.5, 68.5)
CHIMNEY = (30.5, 67.5)
block('sento_boiler', 32, 63, 36, 72, 0, 5.0, '#6a665e', '#4a4a50', label='sento_boiler')
block('sento_chimney', 29, 66, 32, 69, 0, 18.2, C['chimney'], '#5a5650', label='sento_chimney')
entity('pole_chimney', 'pole', 32.45, 5.0, 67.5, {'height': 13.2})
# bridges: the front road's (canal_road_bridge, flush with the road, 0.5 thick) and the
# footbridge at z 60 (canal_footbridge, 0.3, a step up)
block('canal_road_bridge', 44, 104, 52, 118, -0.5, 0.0, '#8e887c', '#6a6a6e', 'hero', 300, 'canal_road_bridge')
block('canal_footbridge', 44, 59, 52, 61.5, 0.1, 0.3, '#b4ae9e', label='canal_footbridge', budget=120, kind='hero')
block('canal_grille', 44, 0.4, 52, 0.8, -1.2, 1.0, '#4a4a50', label='canal_grille')

# ------------------------------------------------------------------ 3.5 the front road
POLES = []
def pole(pid, x, z, h=9.0, y=0.0):
    block(f'pole_{pid}', x - .175, z - .175, x + .175, z + .175, y, y + h, C['pole'], label='utility_pole',
          budget=30, solid=False)
    entity(f'pole_{pid}', 'pole', x, y, z, {'height': h})
    POLES.append((pid, x, z))
WIRE_Y = 8.0
# poles every 30 m from x 10, but none on the axis (x 160, where the shotengai meets the road):
# that one is split into two on the sando's kerbs, x 152.5 and 167.5
road_wire = [(x, 104.0) for x in (10, 40, 70, 100, 130, 152.5, 167.5, 190, 220, 250, 280)]
for x, z in road_wire: pole(f'road{int(x)}', x, z)
# service-lane wires: layout's x 118 and x 150 lie over houses and shops; moved to the alley at
# x 112.75 and the west service lane at x 137.75 (both 2.5-4.5 m lanes), z 44 to 104
LANE_W = [(112.75, 44.0), (112.75, 104.0)]
LANE_E = [(137.75, 44.0), (137.75, 104.0)]
for k, (x, z) in enumerate(LANE_W): pole(f'lane_w{k}', x, z)
for k, (x, z) in enumerate(LANE_E): pole(f'lane_e{k}', x, z)
# the konbini wire: from a pole at the roof's north-east corner (the "corner pole") to the road
KONBINI_WIRE = [(210.0, 33.0), (207.0, 104.0)]
for k, (x, z) in enumerate(KONBINI_WIRE): pole(f'konbini{k}', x, z)
block('road_works', 0.5, 104.5, 1.5, 117.5, 0, 1.2, '#e8782a', '#eceae4', label='road_works')
# overpass (overpass, 600): deck 7.0 over the road at x 260-264, z 100-122; ramps west at the
# school side (z 96-100) and east at the cemetery lane (z 122-126), 26.6 degrees
compound('overpass', 'overpass', 262, 0, 111, [
    flat_slab(260, 96, 264, 126, 7.0, 'deck', 0.5),
    ramp_ext(246, 96.1, 260, 99.9, 0.0, 7.0, 'x', 0, .3, 'deck', 0.4),
    ramp_ext(264, 122.1, 278, 125.9, 7.0, 0.0, 'x', .3, 0, 'deck', 0.4)] +
    [('box', px - .3, 0, pz - .3, px + .3, 6.6, pz + .3, 'deck', 'deck') for px in (260.5, 263.5) for pz in (101, 121)],
    {'deck': C['overpass']}, 'hero', 600)
# the culvert (41): the pond's outflow under the road, x 234-238; the road over it is a slab
block('culvert_deck', 234, 104, 238, 118, -0.15, 0.0, '#4a4a50', '#4a4a50', label='culvert_deck')

# ------------------------------------------------------------------ 3.15 schoolyard
block('school', 258, 56, 288, 86, 0, 18.9, C['school'], '#a8a69e', 'hero', 800, 'school')
compound('school_stair', 'school_stair', 289.25, 0, 67, [slab_ramp(288, 48, 290.5, 86, 0.0, 18.9, 'z', 'stair')],
         {'stair': C['concd']})
block('gym', 214, 64, 238, 94, 0, 9.0, C['gym'], '#5a6a54', 'hero', 500, 'gym')
block('tyre_steps', 246, 24, 252, 26, 0, 0.8, '#2c2a28', label='tyre_steps')
block('tyre_steps_2', 246, 27, 252, 29, 0, 1.6, '#2c2a28', label='tyre_steps')
block('climbing_frame', 266, 30, 272, 36, 0, 2.6, '#3a6ab0', '#e0502a', label='climbing_frame')

# ------------------------------------------------------------------ the great torii (c2_1)
# a frame, not a box: posts (poles, 12.6) at x 155.5 and 164.5, the kasagi 12.4-13.2 over
# x 153.5-166.5, the nuki 10.4-11.0 (G8 passes under it at about 9.4)
TB = L.height(160, 124)
compound('torii', 'torii', 160, TB, 124, [
    ('box', 155, TB, 123.5, 156, TB + 12.5, 124.5, 'red', 'red'),
    ('box', 164, TB, 123.5, 165, TB + 12.5, 124.5, 'red', 'red'),
    ('box', 153.5, TB + 12.4, 123.4, 166.5, TB + 13.2 - .0, 124.6, 'red', 'black'),
    ('box', 155.5, TB + 9.8, 123.7, 164.5, TB + 10.4, 124.3, 'red', 'red')],
    {'red': C['red'], 'black': '#2c2a28'}, 'hero', 160)
TORII_TOP = TB + 13.2
entity('pole_torii_w', 'pole', 155.5, TB, 124 - 0.85, {'height': 12.6})
entity('pole_torii_e', 'pole', 164.5, TB, 124 - 0.85, {'height': 12.6})

# ------------------------------------------------------------------ trees: trunk and canopy boxes
def tree(tid, kind, x, z):
    g = L.height(x, z)
    if kind == 'cedar':   parts = [('box', -.5, 0, -.5, .5, 8, .5, 'trunk', 'trunk'), ('box', -2.5, 6, -2.5, 2.5, 22, 2.5, 'leaf', 'leaf')]; col = C['cedar']
    elif kind == 'maple': parts = [('box', -.3, 0, -.3, .3, 3, .3, 'trunk', 'trunk'), ('box', -3, 3, -3, 3, 8, 3, 'leaf', 'leaf')]; col = C['maple']
    elif kind == 'ginkgo':parts = [('box', -.3, 0, -.3, .3, 4, .3, 'trunk', 'trunk'), ('box', -3.5, 4, -3.5, 3.5, 13, 3.5, 'leaf', 'leaf')]; col = C['ginkgo']
    else:                 parts = [('box', -.3, 0, -.3, .3, 3, .3, 'trunk', 'trunk'), ('box', -3, 3, -3, 3, 9, 3, 'leaf', 'leaf')]; col = C['zelkova']
    pw = [(p[0], x + p[1], g + p[2], z + p[3], x + p[4], g + p[5], z + p[6], p[7], p[8]) for p in parts]
    compound(tid, f'tree_{kind}', x, g, z, pw, {'trunk': C['trunk'], 'leaf': col}, 'tree')
for k, (x, z) in enumerate([(58, 122), (66, 125), (74, 121), (84, 124), (92, 121)]): tree(f'cedar_{k}', 'cedar', x, z)
for k, (x, z) in enumerate([(14, 124), (32, 122)]): tree(f'ginkgo_{k}', 'ginkgo', x, z)
for k, (x, z) in enumerate([(216, 122), (248, 121)]): tree(f'maple_{k}', 'maple', x, z)
for k, (x, z) in enumerate([(280, 100), (286, 100), (292, 100), (310, 100), (316, 100)]): tree(f'zelkova_{k}', 'zelkova', x, z)

# ------------------------------------------------------------------ the level's frame (no invisible walls)
for k, (x1, x2) in enumerate([(0, 44), (52, 64), (64, 128), (128, 192), (192, 256), (256, 290)]):
    block(f'edge_s{k}', x1, 0.0, x2, 0.4, 0, 3.0, C['fence'], label='edge_fence')
for k, (z1, z2) in enumerate([(0, 64), (64, 104)]):
    block(f'edge_w{k}', 0.0, z1, 0.4, z2, 0, 3.0, C['fence'], label='edge_fence')
    block(f'edge_e{k}', 319.6, z1, 320.0, z2, 0, 3.0, C['fence'], label='edge_fence')
# The neighbours beyond the town's three open sides (spec 4.4, "the neighbour beyond"): until those
# levels exist, the backs of their buildings stand just outside the level, 18-28 m here, at least as
# high as the frame's rule asks (DESIGN.md 12.9: 6.6 m over any floor within 4 m, less 1 m for each
# 4 m farther, for a backflip and a ledge grab and a glide; place/art.py gives the real ones their
# heights and adds the ones behind the front road's hoardings, tools/frame.py checks them). Each
# block's origin is inside the level (a placement must lie in its cell) and the block reaches out
# past the edge (the world's overhang, 32 m). Plain boxes, a colour of their own.
NB = C['neighbour'] = '#a6a49c'
for k, (x1, x2, h) in enumerate([(0, 32, 26), (32, 64, 22), (64, 96, 28), (96, 136, 24), (136, 184, 22),
                                 (184, 216, 27), (216, 256, 23), (256, 288, 26), (288, 320, 24)]):
    compound(f'neighbour_s{k}', 'neighbour', (x1 + x2) / 2, 0, 0.2,
             [('box', x1, 0, -8.0, x2, h, 0.0, 'wall', 'roof')], {'wall': NB, 'roof': '#7e7c76'})
for k, (z1, z2, h) in enumerate([(0, 36, 25), (36, 72, 22), (72, 104, 27)]):
    compound(f'neighbour_e{k}', 'neighbour', 319.8, 0, (z1 + z2) / 2,
             [('box', 320.0, 0, z1, 328.0, h, z2, 'wall', 'roof')], {'wall': NB, 'roof': '#7e7c76'})
    compound(f'neighbour_w{k}', 'neighbour', 0.2, 0, (z1 + z2) / 2,
             [('box', -8.0, 0, z1, 0.0, h - 4, z2, 'wall', 'roof')], {'wall': NB, 'roof': '#7e7c76'})
# The front road's two ends (spec 7.3, 7.1): road-works hoardings 5.5 m tall, until the shopping
# street (west) and downtown (east, the seamless edge) exist. They are not the frame: a backflip
# and a grab reach 6.55 m, so the neighbours' backs stand behind them (place/art.py, e3, w3).
block('hoarding_w', 0.0, 104.0, 0.4, 118.0, 0, 5.5, '#eceae4', '#e8782a', label='hoarding')
block('hoarding_e', 319.6, 104.0, 320.0, 118.0, 0, 5.5, '#eceae4', '#e8782a', label='hoarding')
# Doors (the garden cart's door entities, spec 7.3): the konbini's leads to the garden, as the
# shrine's does; walking into the road works at the front road's west end leads back along the
# road to the shrine (whose road's west end leads here).
entity('door_garden', 'door', 196.0, 0.0, 33.0, {'world': 'garden', 'size': [3.0, 3.0, 1.2]})
entity('door_shrine', 'door', 1.6, 0.0, 111.0, {'world': 'shrine', 'size': [2.0, 3.0, 13.0]})

# ------------------------------------------------------------------ floors under points
def floor_at(x, z, below=99.0):
    best = L.height(x, z) if not (L.in_rect(x, z, L.CANAL) or L.in_rect(x, z, L.POOL)) else -1.2
    for x1, z1, x2, z2, top in solids:
        if x1 <= x <= x2 and z1 <= z <= z2 and best < top <= below: best = top
    return best

# ------------------------------------------------------------------ coins, red coins, stars
coin_rec = {'format': 'mei-asset', 'version': 1, 'name': 'gbt_coin',
            'materials': {'gold': {'color': '#ffd040', 'class': 'emissive', 'tag': 'pickup'}},
            'lighting': LIGHT, 'nodes': [{'id': 'disc', 'op': 'cylinder', 'radius': 0.3, 'height': 0.08, 'segments': 10,
                                          'material': 'gold', 'transform': {'rotate': [90, 0, 0]}}],
            'budget': {'vertices': 64, 'triangles': 64},
            'verification': {'required': True, 'yaw_steps': 4, 'pitches': [0], 'distances': [1.5]}}
recipes['gbt_coin'] = coin_rec
recipes['gbt_coin_red'] = json.loads(json.dumps(coin_rec).replace('gbt_coin', 'gbt_coin_red').replace('#ffd040', '#e02828'))
COIN_LIFT = 0.7
RED = [  # (id, x, y_surface, z, what); layout.RED_COINS with the grey box's changes
    ('red_arcade', 160, 8.5, 78, 'arcade ridge'),
    ('red_fire_tower', 102, 15.2, 74, 'fire tower top'),
    ('red_canopy', 172, 12.8, 8, 'station canopy'),
    ('red_danchi', 78, 20.8, 26, 'danchi water tank'),
    ('red_konbini', 196, 7.0, 30, 'konbini roof sign'),
    ('red_wire', 145, WIRE_Y, 104, 'front-road wire, mid-span (layout: x 130, a pole)'),
    ('red_chimney', CHIMNEY[0], 18.2, CHIMNEY[1], 'sento chimney'),
    ('red_parapet', 48, VD + 1.2, 8 + POFF, 'viaduct north parapet over the canal'),
]
for rid, x, y, z, _ in RED:
    entity(rid, 'red_coin', x, y + COIN_LIFT, z, asset='gbt_coin_red')
# the game's entities in these rows (../game.py: the stars, the triggers, the last train)
_gs = importlib.util.spec_from_file_location('game', ST / 'game.py'); G = importlib.util.module_from_spec(_gs); _gs.loader.exec_module(G)
for _cid, _es in G.cell_entities((0, 1)).items():
    for _e in _es: entities_n.add(_e['id']); cell(_cid, (int(_cid[1]), int(_cid[3])))['entities'].append(_e)
# coin lines (spec 6.1, the town's share)
coins = []
for k, (x0, x1) in enumerate(STAIRS):                       # plaza and station stairs: 6
    for j, zz in enumerate((29, 23, 17)):
        coins.append((f'coin_stair{k}_{j}', (x0 + x1) / 2, VD * (32 - zz) / 18 + COIN_LIFT, zz))
for j, (x, z) in enumerate([(165.2, 49), (173, 49), (173, 58), (173, 68), (166, 70), (160, 74),
                            (160, 84), (160, 90), (147, 97), (147, 101)]):   # shotengai roofs and arcade: 10
    coins.append((f'coin_roof{j}', x, floor_at(x, z) + COIN_LIFT, z))
for j, x in enumerate((170, 175, 180)):                     # wires: 9
    coins.append((f'coin_wire_road{j}', x, WIRE_Y + COIN_LIFT, 104))
for j, z in enumerate((60, 70, 80)):
    coins.append((f'coin_wire_lane{j}', 137.75, WIRE_Y + COIN_LIFT, z))
for j, t in enumerate((0.35, 0.55, 0.75)):
    coins.append((f'coin_wire_konbini{j}', 210 - 3 * t, WIRE_Y + COIN_LIFT, 33 + 71 * t))
for j, (x, z) in enumerate([(135, 66), (125, 70), (118, 66), (107, 74), (95, 64), (88, 58), (80, 48), (78, 40)]):
    coins.append((f'coin_alley{j}', x, floor_at(x, z) + COIN_LIFT, z))      # alley roofs: 8
for j, z in enumerate((20, 36, 52, 68, 84, 100)):           # canal, in the water: 6
    coins.append((f'coin_canal{j}', 48, -0.4 + 0.5, z))
for j, x in enumerate(range(60, 130, 10)):                  # viaduct parapet: 7 (+ red coin 8)
    coins.append((f'coin_parapet{j}', x, VD + 1.2 + COIN_LIFT, 8 + POFF))
for cid, x, y, z in coins: entity(cid, 'coin', x, y, z, asset='gbt_coin')

# ------------------------------------------------------------------ paths: rails
def offset_line(pts, d):
    """The polyline moved d to the left of its direction (mitred)."""
    out = []
    for i, p in enumerate(pts):
        ns = []
        for a, b in ((pts[i - 1], p) if i > 0 else (None, None), (p, pts[i + 1]) if i < len(pts) - 1 else (None, None)):
            if a is None: continue
            dx, dz = b[0] - a[0], b[1] - a[1]; ln = math.hypot(dx, dz)
            ns.append((-dz / ln, dx / ln))                  # left of (dx, dz) with x east, z north... see below
        nx = sum(n[0] for n in ns); nz = sum(n[1] for n in ns); ln = math.hypot(nx, nz)
        nx, nz = nx / ln, nz / ln
        cosh = nx * ns[0][0] + nz * ns[0][1]
        out.append((p[0] + nx * d / cosh, p[1] + nz * d / cosh))
    return out
# Going east along z 8, (-dz, dx) = (0, 1) points north: "left" here is north (+z).
# The deck and the parapets are swept along the whole line, to (320, 146) in the core's row 2 (one
# path each, so there is no seam in them); the spans (placements) are this region's rows only.
# The line stops 4.5 m short of the level's east edge (x 315.5), so that the parapets, 5.85 m to
# either side, stay over the level's cells; a wall closes the deck's end there (the core's c4_2).
(_ax, _az), (_bx, _bz) = L.VIADUCT[-2], L.VIADUCT[-1]
_t = (315.5 - _ax) / (_bx - _ax)
VIADUCT_END = (315.5, _az + (_bz - _az) * _t)
vline = list(L.VIADUCT[:-1]) + [VIADUCT_END]
par_n = offset_line(vline, POFF)
par_s = offset_line(vline, -POFF)
PY = VD + 1.2
paths = {}
def pts3(pts2, y): return [(x, y, z) for x, z in pts2]
def path(name, pts, y=None, sweep=None, rail=True):
    paths[name] = {'points': [[r3(p[0]), r3(y if y is not None else p[1]), r3(p[-1])] if len(p) == 2 else [r3(c) for c in p]
                              for p in pts], 'raised': True}
    if sweep: paths[name]['sweep'] = sweep
    first = paths[name]['points'][0]
    if rail: entity(f'rail_{name}', 'rail', first[0], first[1], first[2], {'path': name})
DECK_SWEEP = {'profile': [[-VW / 2, -1.5], [-VW / 2, 0], [VW / 2, 0], [VW / 2, -1.5], [-VW / 2, -1.5]],
              'materials': ['viaduct', 'deck', 'viaduct', 'viaduct_under']}
PARAPET_SWEEP = {'profile': [[-0.15, -1.2], [-0.15, 0], [0.15, 0], [0.15, -1.2]], 'material': 'parapet', 'caps': True}
path('wire_road', pts3(road_wire, WIRE_Y))
path('wire_lane_w', pts3(LANE_W, WIRE_Y))
path('wire_lane_e', pts3(LANE_E, WIRE_Y))
path('wire_konbini', pts3(KONBINI_WIRE, WIRE_Y))
path('viaduct_deck', pts3(vline, VD), rail=False, sweep=DECK_SWEEP)
path('parapet_s', pts3(par_s, PY), sweep=PARAPET_SWEEP)
# the north parapet is open over the station's two spans (the stairs arrive there)
gx0, gx1 = STATION_GAP
path('parapet_n_w', pts3([par_n[0], (gx0, par_n[0][1])], PY), sweep=PARAPET_SWEEP)
path('parapet_n_e', pts3([(gx1, par_n[0][1])] + par_n[1:], PY), sweep=PARAPET_SWEEP)
# (the lantern strings from the torii's top beam are the core region's paths core_string_torii_*,
# from the kasagi's top at TORII_TOP)

# ------------------------------------------------------------------ terrain: materials and operations
materials = {
    'street':   {'color': '#8e8c88'},
    'asphalt':  {'color': '#4a4a50'},
    'paving':   {'color': '#b4ae9e'},
    'sando':    {'color': '#c8b89a'},
    'clay':     {'color': '#c49a6a'},
    'pooldeck': {'color': '#d8d8d0'},
    'grass':    {'color': '#6f8a3c'},
    'floor':    {'color': '#5f7a34'},
    'gravel':   {'color': '#d4ccb8'},
    'bank':     {'color': '#8e887c'},
    'bed':      {'color': '#5a5a4e'},
    'earth':    {'color': '#6a4a30'},
    'viaduct':  {'color': '#b0aca2'},
    'viaduct_under': {'color': '#8e8a82'},
    'deck':     {'color': '#9a968e'},
    'parapet':  {'color': '#d0ccc2'},
    'water':    {'color': '#3f7393', 'water': True, 'tag': 'water'},
}
ops = [
    {'op': 'paint', 'area': {'rect': [100, 14, 216, 44]}, 'material': 'paving'},
    {'op': 'paint', 'area': {'rect': [154, 44, 166, 104]}, 'material': 'sando'},
    {'op': 'paint', 'area': {'rect': [0, 104, 320, 118]}, 'material': 'asphalt'},
    {'op': 'paint', 'area': {'rect': [244, 18, 292, 52]}, 'material': 'clay'},
    {'op': 'paint', 'area': {'rect': [210, 18, 244, 44]}, 'material': 'pooldeck'},
    {'op': 'paint', 'area': {'rect': [0, 118, 44, 128]}, 'material': 'grass'},
    {'op': 'paint', 'area': {'rect': [52, 118, 110, 128]}, 'material': 'floor'},
    {'op': 'paint', 'area': {'rect': [210, 118, 252, 128]}, 'material': 'floor'},
    {'op': 'paint', 'area': {'rect': [110, 118, 210, 128]}, 'material': 'gravel'},
    # the canal, its whole length from the grille (z 0) to the spring (z 292): vertical stone banks,
    # bed -1.2, water -0.4 (0.8 m: wading). One cliff, so there is no wall across it at a row seam.
    {'op': 'cliff', 'area': {'rect': [44, 0, 52, 292]}, 'height': -1.2, 'material': 'bank'},
    {'op': 'set', 'area': {'rect': [44, 0, 52, 292]}, 'height': -1.2},
    {'op': 'paint', 'area': {'rect': [44, 0, 52, 292]}, 'material': 'bed'},
    {'op': 'water', 'area': {'rect': [44, 0, 52, 292]}, 'level': -0.4, 'material': 'water'},
    # the school pool: bed -1.2, water -0.3 (0.9 m)
    {'op': 'cliff', 'area': {'rect': [214, 22, 240, 40]}, 'height': -1.2, 'material': 'bank'},
    {'op': 'set', 'area': {'rect': [214, 22, 240, 40]}, 'height': -1.2},
    {'op': 'paint', 'area': {'rect': [214, 22, 240, 40]}, 'material': 'bed'},
    {'op': 'water', 'area': {'rect': [214, 22, 240, 40]}, 'level': -0.3, 'material': 'water'},
    # the culvert (41) and the school's ditch: bed -2.0, water -1.2 (0.8 m), 1.85 m under the road
    # slab; north of the road the channel's bed rises to the pond's (-1.4 at z 134), so it opens
    # into the pond instead of ending at a step. The pond's water (the core's, level 0) covers it
    # from z 124.
    {'op': 'cliff', 'area': {'rect': [234, 96, 238, 134]}, 'height': -2.0, 'material': 'bank'},
    {'op': 'set', 'area': {'rect': [234, 96, 238, 134]}, 'height': -2.0},
    {'op': 'ramp', 'from': [236, -2.0, 118], 'to': [236, -1.4, 134], 'width': 4},
    {'op': 'paint', 'area': {'rect': [234, 96, 238, 134]}, 'material': 'bed'},
    {'op': 'water', 'area': {'rect': [234, 96, 238, 124]}, 'level': -1.2, 'material': 'water'},
]
SP = 2
heights = []
for j in range(0, int(ROW_MAX) // SP + 1):
    z = j * SP
    row = []
    for i in range(0, 320 // SP + 1):
        x = i * SP
        h = 0.0 if (L.in_rect(x, z, L.CANAL) or L.in_rect(x, z, L.POOL)) else L.height(x, z)
        row.append(f'{h:.2f}')
    heights.append(' '.join(row))
(PARTS / 'town_heights.txt').write_text('# layout.height() on a 2 m grid, x 0-320, z 0-128 (canal and pool at 0: the cliffs lower them)\n'
                                        + '\n'.join(heights) + '\n')

VANTAGE = [
    {'name': 'V5 spawn looking north', 'position': [160, 1.6, 26], 'yaw': 0, 'pitch': 0},
    {'name': 'V5b spawn looking north, up 5', 'position': [160, 1.6, 26], 'yaw': 0, 'pitch': 5},
    {'name': 'V1 arcade roof north end looking south', 'position': [160, 10.0, 94], 'yaw': 180, 'pitch': -8},
    {'name': 'V4 danchi roof looking north-east', 'position': [78, 20.3, 30], 'yaw': 45, 'pitch': -10},
    {'name': 'shotengai floor looking north', 'position': [160, 1.5, 50], 'yaw': 0, 'pitch': 0},
    {'name': 'shotengai floor looking south', 'position': [160, 1.5, 100], 'yaw': 180, 'pitch': 0},
    {'name': 'platform looking north', 'position': [160, 10.5, 8], 'yaw': 0, 'pitch': -5},
    {'name': 'parapet over the canal looking east', 'position': [48, 11.7, 13.85], 'yaw': 90, 'pitch': -5},
    {'name': 'fire tower top looking east', 'position': [102, 16.7, 74], 'yaw': 90, 'pitch': -15},
    {'name': 'building roof looking west', 'position': [193, 19.8, 90], 'yaw': 270, 'pitch': -15},
    {'name': 'school roof looking west', 'position': [273, 20.4, 71], 'yaw': 270, 'pitch': -10},
    {'name': 'front road looking east', 'position': [120, 1.5, 111], 'yaw': 90, 'pitch': 0},
    {'name': 'sento chimney looking east', 'position': [30.5, 19.7, 67.5], 'yaw': 90, 'pitch': -15},
]

part = {
    'about': 'Shrine town grey box, region town (z 0-128): world-level entries in the world recipe\'s format. '
             'Written by notes/gen_town.py; see notes/town.md.',
    'regions': {r: {} for r in L.REGIONS},
    'layers': {'ladder_e': {}},
    'paths': paths,
    'terrain': {'materials': materials, 'operations': ops,
                'heights': 'layout.height() over the rows (parts/town_heights.txt for the test world)'},
    'collision': {'surfaces': {'default': 0, 'tags': {'bounce': 1, 'slide': 2, 'water': 3}}},
    'vantage_points': VANTAGE,
}
# the placement zones (place/ZONE.py) change the cells and the part before they are written
sys.path.insert(0, str(ST))
from place import apply as apply_zones, unused
apply_zones('town', globals())
for _n in unused(recipes, cells, part): del recipes[_n]          # the grey boxes swapped out
(PARTS / 'town.json').write_text(json.dumps(part, indent=1) + '\n')

# ------------------------------------------------------------------ write recipes and cells
for p in ASSETS.glob('gbt_*.asset.json'): p.unlink()
for name, rec in recipes.items():
    (ASSETS / f'{name}.asset.json').write_text(json.dumps(rec, separators=(',', ':')) + '\n')
for p in CELLS.glob('c[0-4]_[01].cell.json'): p.unlink()
for cid, c in sorted(cells.items()):
    (CELLS / f'{cid}.cell.json').write_text(json.dumps(c, indent=1) + '\n')

# ------------------------------------------------------------------ checks: jumps, steps, glides
checks = {'alley_houses': ALLEY_HOUSES, 'machiya': MACHIYA, 'poles': len(POLES) + 5, 'rails': len(paths) - 1,
          'placements': sum(len(c['placements']) for c in cells.values()),
          'placements_per_cell': {k: len(c['placements']) for k, c in sorted(cells.items())},
          'recipes': len(recipes)}
def glide(start, end):
    h, d = L.glide_end_height(start, end); return {'distance': round(d, 1), 'arrives': round(h, 1)}
checks['glides'] = {
    'G1 building roof -> east side hall (11.6)': glide((193, 102, 18.3), (192, 126)),
    'G2 danchi roof -> canal lane (0)': glide((78, 34, 18.8), (56, 80)),
    'G3 sento chimney (moved) -> park (0.6)': glide((CHIMNEY[0], CHIMNEY[1], 18.2), (22, 138)),
    'G4 fire tower -> courtyard west (0.6)': glide((102, 77, 15.2), (112, 140)),
    'G9 school roof -> cemetery terrace 2-3': glide((273, 86, 18.9), (276, 150)),
}
JUMP = {'jump': 2.2, 'double': 3.4, 'double_grab': 3.4 + 1.75, 'bounce': 4.5}
checks['steps'] = {
    'awning 2.6 + bounce 4.5 vs shop roof 6.5': round(2.6 + JUMP['bounce'] - 6.5, 2),
    'shop roof 6.5 -> 9.5 (double jump 3.4)': round(JUMP['double'] - 3.0, 2),
    'vending 1.9 -> konbini roof 5.6 (double + grab 5.15)': round(JUMP['double_grab'] - 3.7, 2),
    'platform 9.0 -> canopy 12.8 (double + grab)': round(JUMP['double_grab'] - 3.8, 2),
    'deck 9.0 -> parapet 10.2 (jump)': round(JUMP['jump'] - 1.2, 2),
    'ground -> sento boiler 5.0 (double + grab)': round(JUMP['double_grab'] - 5.0, 2),
    'boiler 5.0 -> sento roof 8.0 (double)': round(JUMP['double'] - 3.0, 2),
    'kura 8.0 -> fire tower 15.2: two good kicks 6.8 + grab 1.75': round(6.8 + 1.75 - 7.2, 2),
    'danchi roof 18.8 -> tank 20.8 (jump)': round(JUMP['jump'] - 2.0, 2),
    'arcade eave over shop roof 6.5 -> 7.0 (jump)': round(JUMP['jump'] - 0.5, 2),
}
# alley roofs: every pair of neighbours (gap, rise)
alley = [s for s in solids if abs((s[2] - s[0]) - 9.5) < .01 and abs((s[3] - s[1]) - 8.5) < .01]
worst = (0, 0)
for a in alley:
    for b in alley:
        if a is b: continue
        gx = max(b[0] - a[2], a[0] - b[2]); gz = max(b[1] - a[3], a[1] - b[3])
        if (gx <= 3.01 and gz < 0) or (gz <= 3.01 and gx < 0):
            worst = (max(worst[0], max(gx, gz)), max(worst[1], abs(a[4] - b[4])))
checks['alley_roof_neighbours'] = {'largest gap': worst[0], 'largest rise': worst[1]}
(HERE / 'town_checks.json').write_text(json.dumps(checks, indent=1) + '\n')
print(json.dumps(checks, indent=1))
