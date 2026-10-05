"""Writes canal_footbridge.asset.json, canal_footbridge_col.asset.json and
canal_footbridge.cameras.json beside this file: the stone footbridge over the canal (spec 3.4,
at z 60 by the sento), 10 x 2.5 m. Run once and commit the outputs:
python3 carts/garden/shrinetown/assets/canal_footbridge/make_footbridge.py

The road bridge's little sibling (canal_road_bridge): the same granite, coping and paving, the
same segmental arch, name plates on its four corner posts (art/footbridge_sheet.png, drawn by
art/draw_footbridge.py).

Asset frame: origin at the footprint's centre at bank level (y = 0, the street), the walk
running along X over the canal, which flows along Z under it (canal 8 m wide, x -4..4, water at
-0.4, bed -1.2). The front (-Z) is one parapet's outer side. A humped deck (crown 0.8, flat for
|x| <= 1.5, ramps of 12.9 degrees) on a segmental arch springing from the banks at y = 0 and
rising to 0.6: a player wading on the bed (head at 0.4) passes under the middle 5 m. Solid
granite parapets 0.3 thick, 0.75 above the walk: their tops are walkable (a balance beam over
the water, 1.55 at the crown). The posts' flat tops (1.3) are perches."""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = 'canal_footbridge'


def r(v):
    return round(v, 4)


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def orient(V, faces, wants):
    out = []
    for f, want in zip(faces, wants):
        nn = newell([V[i] for i in f])
        out.append(f if sum(x * y for x, y in zip(nn, want)) > 0 else list(reversed(f)))
    return out


def mesh(nid, V, F, M):
    return {'id': nid, 'op': 'mesh', 'vertices': [[r(c) for c in p] for p in V], 'faces': F, 'face_materials': M}


# ---- the shape
HALF = 5.0                 # half the span (x)
CROWN, FLAT = 0.8, 1.5     # walk at the crown, flat for |x| <= FLAT
CANAL = 4.0                # the arch springs at x = +-4 (the banks), y = 0
RISE = 0.6                 # the arch's soffit at the crown
PZ0, PZ1 = 0.95, 1.25      # parapet, inner and outer face (walk 1.9 m wide)
RAIL = 0.75                # parapet top above the walk
POST_X, POST_Z = 4.75, 1.1 # post centres
POST_W, POST_H = 0.54, 1.3
XS = [-HALF, -FLAT, FLAT, HALF]


def deck(x):
    return CROWN * min(1.0, (HALF - abs(x)) / (HALF - FLAT))


def arch_points(n=4):
    """The soffit, a circular segment through (+-CANAL, 0) and (0, RISE), n segments."""
    R = (CANAL ** 2 + RISE ** 2) / (2 * RISE)
    cy = RISE - R
    pts = []
    for k in range(n + 1):
        x = -CANAL + 2 * CANAL * k / n
        pts.append((x, cy + math.sqrt(R * R - x * x)))
    pts[0], pts[-1] = (-CANAL, 0.0), (CANAL, 0.0)
    return pts


def parapet_outline(n=4):
    """Side elevation, (x, y): along the bank and the arch, back over the parapet's top."""
    bottom = [(-HALF, 0.0)] + arch_points(n) + [(HALF, 0.0)]
    top = [(x, deck(x) + RAIL) for x in reversed(XS)]
    return bottom + top


def prism_z(outline, z0, z1, side, front, back, open_edges=(), open_caps=()):
    """Outline (x, y) extruded from z0 to z1; front is the z1 face, back the z0 face; edge i
    runs from outline[i] to outline[i + 1]."""
    n = len(outline)
    V = [[x, y, z0] for x, y in outline] + [[x, y, z1] for x, y in outline]
    area = sum(outline[i][0] * outline[(i + 1) % n][1] - outline[(i + 1) % n][0] * outline[i][1] for i in range(n))
    F, W, M = [], [], []
    for i in range(n):
        if i in open_edges:
            continue
        j = (i + 1) % n
        e = (outline[j][0] - outline[i][0], outline[j][1] - outline[i][1])
        out = (e[1], -e[0]) if area > 0 else (-e[1], e[0])
        F.append([i, j, n + j, n + i]); W.append([out[0], out[1], 0]); M.append(side)
    if 0 not in open_caps:
        F.append(list(range(n))); W.append([0, 0, -1]); M.append(back)
    if 1 not in open_caps:
        F.append(list(range(n, 2 * n))); W.append([0, 0, 1]); M.append(front)
    return V, orient(V, F, W), M


def strip(z0, z1, mat, xs=XS, lift=0.0):
    V = [[x, deck(x) + lift, z] for z in (z0, z1) for x in xs]
    n = len(xs)
    F = [[k, k + 1, n + k + 1, n + k] for k in range(n - 1)]
    return V, orient(V, F, [[0, 1, 0]] * (n - 1)), [mat] * (n - 1)


def barrel(segments=4, z=PZ0):
    """The arch's underside between the parapets, facing down."""
    pts = arch_points(segments)
    V = [[x, y, zz] for zz in (-z, z) for x, y in pts]
    n = len(pts)
    F = [[k, k + 1, n + k + 1, n + k] for k in range(n - 1)]
    return V, orient(V, F, [[0, -1, 0]] * (n - 1)), ['barrel'] * (n - 1)


# (x, z, the plate, the box side facing the walk): a south post's +Z side is 'front'
POSTS = [(-POST_X, -POST_Z, 'plate_kanji', 'front'), (POST_X, -POST_Z, 'plate_year', 'front'),
         (-POST_X, POST_Z, 'plate_water', 'back'), (POST_X, POST_Z, 'plate_kana', 'back')]

# The parapet outline's edges: 0 and 5 lie on the banks, 6 and 10 (the ends) inside the posts.
OPEN_PARAPET = (0, 5, 6, 10)


def level0():
    nodes = [mesh('walk', *strip(-PZ0, PZ0, 'paving')), mesh('barrel', *barrel())]
    for sgn, nid in ((-1, 'parapet_s'), (1, 'parapet_n')):
        z0, z1 = sorted((sgn * PZ0, sgn * PZ1))
        nodes.append(mesh(nid, *prism_z(parapet_outline(), z0, z1, 'coping', 'granite', 'granite',
                                        open_edges=OPEN_PARAPET)))
    for k, (x, z, plate, side) in enumerate(POSTS):
        nodes.append({'id': f'post_{k}', 'op': 'box', 'size': [POST_W, POST_H, POST_W], 'material': 'granite_post',
                      'open': ['bottom'], 'faces': {side: plate, 'top': 'coping'},
                      'transform': {'translate': [x, POST_H / 2, z]}})
    return nodes


def level1():
    """From 30 m: the walk as one strip over the whole width, each parapet one double-sided
    slab on its centre line (its ends raised to the posts' height, standing in for them) and
    its top, the arch in two segments."""
    nodes = [mesh('walk', *strip(-PZ1, PZ1, 'paving')), mesh('barrel', *barrel(2, PZ1))]
    px0 = POST_X - POST_W / 2
    pts = [(-HALF, 0.0)] + arch_points(2) + [(HALF, 0.0), (HALF, POST_H), (px0, POST_H),
                                              (px0, deck(px0) + RAIL), (FLAT, CROWN + RAIL),
                                              (-FLAT, CROWN + RAIL), (-px0, deck(px0) + RAIL),
                                              (-px0, POST_H), (-HALF, POST_H)]
    n = len(pts)
    xs = [-px0, -FLAT, FLAT, px0]
    for sgn, nid in ((-1, 'parapet_s'), (1, 'parapet_n')):
        zc = sgn * (PZ0 + PZ1) / 2
        V = [[x, y, zc] for x, y in pts]
        V += [[x, deck(x) + RAIL + 0.01, sgn * PZ0] for x in xs] + [[x, deck(x) + RAIL + 0.01, sgn * PZ1] for x in xs]
        F = [list(range(n))] + [[n + k, n + k + 1, n + 5 + k, n + 4 + k] for k in range(3)]
        W = [[0, 0, sgn]] + [[0, 1, 0]] * 3
        nodes.append(mesh(nid, V, orient(V, F, W), ['granite_2s'] + ['coping'] * 3))
    return nodes


def level2():
    """From 60 m: the walk and the parapets' double-sided faces."""
    nodes = [mesh('walk', *strip(-PZ1, PZ1, 'paving'))]
    pts = [(-HALF, 0.0), (-CANAL, 0.0), (0.0, RISE), (CANAL, 0.0), (HALF, 0.0)] + \
          [(x, deck(x) + RAIL) for x in reversed(XS)]
    for sgn, nid in ((-1, 'parapet_s'), (1, 'parapet_n')):
        V = [[x, y, sgn * PZ1] for x, y in pts]
        nodes.append(mesh(nid, V, orient(V, [list(range(len(pts)))], [[0, 0, sgn]]), ['granite_2s']))
    return nodes


def collision():
    """The deck as one solid following the render (its top the walk, its underside the arch's
    soffit, so a wading player passes under the crown), the parapets (walkable tops) and the
    posts as boxes."""
    top = [(x, deck(x)) for x in reversed(XS)]
    bottom = [(-HALF, -0.3), (-CANAL, -0.3)] + arch_points() + [(CANAL, -0.3), (HALF, -0.3)]
    nodes = [mesh('walk', *prism_z(bottom + top, -PZ0, PZ0, 'solid', 'solid', 'solid', open_caps=(0, 1)))]
    for sgn, nid in ((-1, 'parapet_s'), (1, 'parapet_n')):
        z0, z1 = sorted((sgn * PZ0, sgn * PZ1))
        nodes.append(mesh(nid, *prism_z(parapet_outline(), z0, z1, 'solid', 'solid', 'solid')))
    for k, (x, z, _, _) in enumerate(POSTS):
        nodes.append({'id': f'post_{k}', 'op': 'box', 'size': [POST_W, POST_H, POST_W], 'material': 'solid',
                      'open': ['bottom'], 'transform': {'translate': [x, POST_H / 2, z]}})
    return nodes


POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}

GRANITE_TEX = {'pattern': 'brick', 'size': 16, 'colors': ['#b4ae9e', '#8e887c', '#a8a294'],
               'params': {'courses': 4, 'bricks': 2, 'bond': 0.5, 'seed': 2},
               'projection': 'box', 'scale': [1.2, 0.6]}
MATERIALS = {
    'paving': {'color': '#a8a69e', 'tag': 'floor',
               'texture': {'pattern': 'tile', 'size': 16, 'colors': ['#a8a69e', '#8e8a84', '#b4ae9e'],
                           'params': {'count': 2, 'grout': 1}, 'projection': 'box', 'scale': [0.6, 0.6]}},
    'granite': {'color': '#b4ae9e', 'tag': 'wall', 'texture': GRANITE_TEX},
    'granite_2s': {'color': '#b4ae9e', 'tag': 'wall', 'double_sided': True, 'texture': GRANITE_TEX},
    'granite_post': {'color': '#b4ae9e', 'palette': True, 'tag': 'wall'},
    'coping': {'color': '#c8c2b2', 'palette': True, 'tag': 'wall'},
    'barrel': {'color': '#6a665e', 'palette': True},
    'plate_kanji': {'color': '#34302c', 'texture': {'sheet': 'plates', 'cell': 'plate_kanji', 'projection': 'fit'}},
    'plate_kana': {'color': '#34302c', 'texture': {'sheet': 'plates', 'cell': 'plate_kana', 'projection': 'fit'}},
    'plate_water': {'color': '#34302c', 'texture': {'sheet': 'plates', 'cell': 'plate_water', 'projection': 'fit'}},
    'plate_year': {'color': '#34302c', 'texture': {'sheet': 'plates', 'cell': 'plate_year', 'projection': 'fit'}},
}

CAMERAS = [
    {'name': 'lane_12m', 'eye': [9, 1.6, -10], 'target': [0, 0.8, 0]},
    {'name': 'on_walk', 'eye': [-8, 1.6, -0.3], 'target': [0, 1.2, 0]},
    {'name': 'plates', 'eye': [-3.2, 1.6, 0.2], 'target': [-4.75, 0.8, -0.85]},
    {'name': 'wading', 'eye': [0, 0.0, -9], 'target': [0, 0.3, 0]},
    {'name': 'parapet_top', 'eye': [-4.3, 3.15, -1.1], 'target': [3, 1.4, -1.1]},
    {'name': 'lane_30m', 'eye': [16, 1.6, -26], 'target': [0, 0.6, 0]},
    {'name': 'roof_above', 'eye': [-14, 8.5, -10], 'target': [0, 0.5, 0]},
]


def write(path, recipe):
    with open(path, 'w') as f:
        json.dump(recipe, f, indent=1)
        f.write('\n')


if __name__ == '__main__':
    write(os.path.join(HERE, NAME + '.asset.json'), {
        'format': 'mei-asset', 'version': 1, 'name': NAME,
        'budget': {'triangles': 120},
        'sheets': {'plates': {'image': 'art/footbridge_sheet.png'}},
        'materials': MATERIALS, 'lighting': LIGHT, 'verification': POLICY,
        'lod': {'levels': [{'distance': 30, 'nodes': level1()}, {'distance': 60, 'nodes': level2()}]},
        'nodes': level0()})
    write(os.path.join(HERE, NAME + '_col.asset.json'), {
        'format': 'mei-asset', 'version': 1, 'name': NAME + '_col',
        'materials': {'solid': {'color': '#ffffff', 'palette': True}},
        'lighting': LIGHT, 'verification': POLICY, 'nodes': collision()})
    with open(os.path.join(HERE, NAME + '.cameras.json'), 'w') as f:
        f.write('[\n' + ',\n'.join('  ' + json.dumps(c) for c in CAMERAS) + '\n]\n')
    print('wrote', NAME)
