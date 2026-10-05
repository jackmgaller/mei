"""Writes canal_road_bridge.asset.json and canal_road_bridge_col.asset.json beside this file:
the front road's bridge over the canal (spec 3.4), 14 x 14 m. Run once and commit the outputs:
python3 carts/garden/shrinetown/assets/canal_road_bridge/make_bridge.py

Asset frame: origin at the footprint's centre on the road (y = 0), the road running along X
over the canal, which flows along Z under it (canal 8 m wide, x -4..4, water at -0.4). The
front (-Z) is one parapet's side, as a walker on the canal lane sees it. A humped deck (crown
1.0, ramps of 12.5 degrees) on a segmental stone arch that springs from the banks at road level
and rises to 0.75: a player wading the canal (1.6 m tall on the bed at -1.2, so its head at 0.4)
passes under its middle 2 m. Granite-faced parapets
(walkable tops, a balance beam over the water), four corner posts carrying the name plates
(art/bridge_sheet.png, drawn by art/draw_bridge.py) and two lamps on the crown, whose poles
are climbable poles for the world to place."""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = 'canal_road_bridge'


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


def mesh(nid, V, F, M, decals=None):
    n = {'id': nid, 'op': 'mesh', 'vertices': [[r(c) for c in p] for p in V], 'faces': F, 'face_materials': M}
    if decals:
        n['decals'] = decals
    return n


# ---- the shape
HALF = 7.0                 # half the span (x) and half the width (z)
CROWN, FLAT = 1.0, 2.5     # deck top at the crown, flat for |x| <= FLAT
CANAL = 4.0                # the arch springs at x = +-4 (the banks), y = 0
RISE = 0.75                # the arch's soffit at the crown
CARRIAGE = 4.5             # carriageway |z| <= 4.5, sidewalks to the parapets
KERB = 0.15                # sidewalk above the carriageway
PZ0, PZ1 = 6.6, 7.0        # parapet, inner and outer face
RAIL = 0.95                # parapet top above the sidewalk
XS = [-HALF, -FLAT, FLAT, HALF]


def deck(x):
    return CROWN * min(1.0, (HALF - abs(x)) / (HALF - FLAT))


def arch_points(n=6):
    """The soffit, a circular segment through (+-CANAL, 0) and (0, RISE), n segments."""
    R = (CANAL ** 2 + RISE ** 2) / (2 * RISE)
    cy = RISE - R
    pts = []
    for k in range(n + 1):
        x = -CANAL + 2 * CANAL * k / n
        pts.append((x, cy + math.sqrt(R * R - x * x)))
    pts[0], pts[-1] = (-CANAL, 0.0), (CANAL, 0.0)
    return pts


def parapet_outline():
    """Side elevation, (x, y): along the ground and the arch, back over the parapet's top."""
    bottom = [(-HALF, 0.0)] + arch_points() + [(HALF, 0.0)]
    top = [(x, deck(x) + KERB + RAIL) for x in reversed(XS)]
    return bottom + top


def prism_z(outline, z0, z1, side, front, back, open_edges=(), open_caps=()):
    """Outline (x, y) extruded from z0 to z1; front is the z1 face, back the z0 face."""
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


def join(parts):
    V, F, M = [], [], []
    for v, f, m in parts:
        off = len(V)
        V += v
        F += [[i + off for i in face] for face in f]
        M += m
    return V, F, M


def deck_surface(stripe=True, kerbs=True):
    """The road's top: carriageway (with its centre line), the sidewalks and their kerbs, as
    strips along X following the hump; the sidewalks' ends at x = +-7."""
    def strip(z0, z1, lift, mat):
        V = [[x, deck(x) + lift, z] for z in (z0, z1) for x in XS]
        F = [[k, k + 1, 5 + k, 4 + k] for k in range(3)]
        return V, orient(V, F, [[0, 1, 0]] * 3), [mat] * 3
    parts = []
    if stripe:
        parts += [strip(-CARRIAGE, -0.075, 0, 'asphalt'), strip(-0.075, 0.075, 0, 'line'),
                  strip(0.075, CARRIAGE, 0, 'asphalt')]
    else:
        parts += [strip(-CARRIAGE, CARRIAGE, 0, 'asphalt')]
    for sgn in (-1, 1):
        z0, z1 = sorted((sgn * CARRIAGE, sgn * PZ0))
        parts.append(strip(z0, z1, KERB, 'paving'))
        if kerbs:
            zk = sgn * CARRIAGE
            V = [[x, deck(x) + h, zk] for h in (0, KERB) for x in XS]
            F = [[k, k + 1, 5 + k, 4 + k] for k in range(3)]
            parts.append((V, orient(V, F, [[0, 0, -sgn]] * 3), ['kerb'] * 3))
            for ex in (-HALF, HALF):         # the sidewalk's end, 0.15 high
                V = [[ex, 0, z0], [ex, 0, z1], [ex, KERB, z1], [ex, KERB, z0]]
                parts.append((V, orient(V, [[0, 1, 2, 3]], [[ex, 0, 0]]), ['kerb']))
    return join(parts)


def barrel(segments=6):
    """The arch's underside between the parapets, facing down."""
    pts = arch_points(segments)
    V = [[x, y, z] for z in (-PZ0, PZ0) for x, y in pts]
    n = len(pts)
    F = [[k, k + 1, n + k + 1, n + k] for k in range(n - 1)]
    return V, orient(V, F, [[0, -1, 0]] * (n - 1)), ['barrel'] * (n - 1)


POSTS = [(-6.78, -6.8, 'plate_year', 'front'), (6.78, -6.8, 'plate_kanji', 'front'),
         (-6.78, 6.8, 'plate_kana', 'back'), (6.78, 6.8, 'plate_water', 'back')]


def level0():
    nodes = [mesh('deck', *deck_surface()), mesh('barrel', *barrel())]
    for sgn, nid in ((-1, 'parapet_s'), (1, 'parapet_n')):
        z0, z1 = sorted((sgn * PZ0, sgn * PZ1))
        nodes.append(mesh(nid, *prism_z(parapet_outline(), z0, z1, 'coping', 'granite', 'granite')))
    for k, (x, z, plate, side) in enumerate(POSTS):
        # the plate faces the road: a south post's +Z side (box 'front'), a north post's -Z
        nodes.append({'id': f'post_{k}', 'op': 'box', 'size': [0.56, 1.6, 0.56], 'material': 'granite_post',
                      'open': ['bottom', 'top'], 'faces': {side: plate},
                      'transform': {'translate': [x, 0.8, z]}})
        nodes.append({'id': f'post_cap_{k}', 'op': 'cone', 'radius': 0.42, 'height': 0.22, 'segments': 4,
                      'material': 'coping', 'faces': {'bottom': 'granite_post'},
                      'transform': {'rotate': [0, 45, 0], 'translate': [x, 1.71, z]}})
    for k, z in enumerate((-6.8, 6.8)):
        y0 = CROWN + KERB + RAIL
        nodes.append({'id': f'lamp_pole_{k}', 'op': 'cylinder', 'radius': 0.09, 'height': 3.0, 'segments': 5,
                      'caps': False, 'material': 'iron_flat', 'transform': {'translate': [0, y0 + 1.48, z]}})
        nodes.append({'id': f'lamp_{k}', 'op': 'box', 'size': [0.4, 0.5, 0.4], 'material': 'lamp',
                      'open': ['top'], 'transform': {'translate': [0, y0 + 3.0, z]}})
        nodes.append({'id': f'lamp_cap_{k}', 'op': 'cone', 'radius': 0.36, 'height': 0.26, 'segments': 4,
                      'material': 'iron', 'faces': {'bottom': 'iron'},
                      'transform': {'rotate': [0, 45, 0], 'translate': [0, y0 + 3.36, z]}})
    return nodes


def level1():
    """From 40 m: the deck as one strip, the parapets as their two faces and their top, the lamps
    as a head on a flat pole; the posts (4 pixels from here) are left out."""
    def strip_deck():
        V = [[x, deck(x), z] for z in (-PZ0, PZ0) for x in XS]
        F = [[k, k + 1, 5 + k, 4 + k] for k in range(3)]
        return V, orient(V, F, [[0, 1, 0]] * 3), ['asphalt'] * 3
    nodes = [mesh('deck', *strip_deck()), mesh('barrel', *barrel(2))]
    outline = [(-HALF, 0.0), (-CANAL, 0.0), (0.0, RISE), (CANAL, 0.0), (HALF, 0.0)] + \
              [(x, deck(x) + KERB + RAIL) for x in reversed(XS)]
    n = len(outline)
    for sgn, nid in ((-1, 'parapet_s'), (1, 'parapet_n')):
        V = [[x, y, sgn * PZ1] for x, y in outline] + [[x, y, sgn * PZ0] for x, y in outline]
        F = [list(range(n)), list(range(n, 2 * n))] + [[i, i + 1, n + i + 1, n + i] for i in range(5, n - 1)]
        W = [[0, 0, sgn], [0, 0, -sgn]] + [[0, 1, 0]] * (n - 6)
        nodes.append(mesh(nid, V, orient(V, F, W), ['granite', 'granite'] + ['coping'] * (n - 6)))
    for k, z in enumerate((-6.8, 6.8)):
        y0 = CROWN + KERB + RAIL
        V = [[-0.09, y0, z], [0.09, y0, z], [0.09, y0 + 2.9, z], [-0.09, y0 + 2.9, z]]
        nodes.append(mesh(f'lamp_pole_{k}', V, [[0, 1, 2, 3]], ['iron_flat']))
        nodes.append({'id': f'lamp_{k}', 'op': 'box', 'size': [0.36, 0.6, 0.36], 'material': 'lamp',
                      'open': ['bottom'], 'transform': {'translate': [0, y0 + 3.1, z]}})
    return nodes


def level2():
    """From 80 m: the deck and the parapets' outer faces."""
    V = [[x, deck(x), z] for z in (-PZ1, PZ1) for x in XS]
    F = [[k, k + 1, 5 + k, 4 + k] for k in range(3)]
    nodes = [mesh('deck', V, orient(V, F, [[0, 1, 0]] * 3), ['asphalt'] * 3)]
    for sgn, nid in ((-1, 'parapet_s'), (1, 'parapet_n')):
        pts = [(-HALF, 0.0), (-CANAL, 0.0), (0.0, RISE), (CANAL, 0.0), (HALF, 0.0)] + \
              [(x, deck(x) + KERB + RAIL) for x in reversed(XS)]
        V = [[x, y, sgn * PZ1] for x, y in pts]
        nodes.append(mesh(nid, V, orient(V, [list(range(len(pts)))], [[0, 0, sgn]]), ['granite']))
    return nodes


def collision():
    """The deck as one solid following the render (its top the carriageway, its underside the
    arch's soffit, so a wading player passes under the crown), the sidewalks as bands on it, the
    parapets (walkable tops: a balance beam over the water) and the posts as boxes. The lamp
    poles are left to the world's pole entities."""
    top = [(x, deck(x)) for x in reversed(XS)]
    bottom = [(-HALF, -0.3), (-CANAL, -0.3)] + arch_points() + [(CANAL, -0.3), (HALF, -0.3)]
    # the deck's z ends lie against the parapets' inner faces: open
    nodes = [mesh('road', *prism_z(bottom + top, -PZ0, PZ0, 'solid', 'solid', 'solid', open_caps=(0, 1)))]
    band = [(-HALF, 0.0)] + [(x, deck(x) - 0.1) for x in XS[1:-1]] + [(HALF, 0.0)] + \
           [(x, deck(x) + KERB) for x in reversed(XS)]
    for sgn, nid in ((-1, 'sidewalk_s'), (1, 'sidewalk_n')):
        z0, z1 = sorted((sgn * CARRIAGE, sgn * PZ0))
        nodes.append(mesh(nid, *prism_z(band, z0, z1, 'solid', 'solid', 'solid', open_caps=(1,) if sgn > 0 else (0,))))
    for sgn, nid in ((-1, 'parapet_s'), (1, 'parapet_n')):
        z0, z1 = sorted((sgn * PZ0, sgn * PZ1))
        nodes.append(mesh(nid, *prism_z(parapet_outline(), z0, z1, 'solid', 'solid', 'solid')))
    for k, (x, z, _, _) in enumerate(POSTS):
        nodes.append({'id': f'post_{k}', 'op': 'box', 'size': [0.56, 1.82, 0.56], 'material': 'solid',
                      'open': ['bottom'], 'transform': {'translate': [x, 0.91, z]}})
    return nodes


POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}

MATERIALS = {
    'asphalt': {'color': '#4a4a50', 'tag': 'road',
                'texture': {'pattern': 'speckle', 'size': 16, 'colors': ['#4a4a50', '#56565c', '#3e3e44', '#5e5c5a'],
                            'params': {'density': 0.35, 'seed': 3}, 'projection': 'box', 'scale': [2.0, 2.0]}},
    'line': {'color': '#eceae4', 'palette': True, 'tag': 'road'},
    'paving': {'color': '#a8a69e', 'tag': 'floor',
               'texture': {'pattern': 'tile', 'size': 16, 'colors': ['#a8a69e', '#8e8a84', '#b4ae9e'],
                           'params': {'count': 2, 'grout': 1}, 'projection': 'box', 'scale': [0.6, 0.6]}},
    'kerb': {'color': '#c8c4b8', 'palette': True},
    'granite': {'color': '#b4ae9e', 'tag': 'wall',
                'texture': {'pattern': 'brick', 'size': 16, 'colors': ['#b4ae9e', '#8e887c', '#a8a294'],
                            'params': {'courses': 4, 'bricks': 2, 'bond': 0.5, 'seed': 2},
                            'projection': 'box', 'scale': [1.2, 0.6]}},
    'granite_post': {'color': '#b4ae9e', 'palette': True, 'tag': 'wall'},
    'coping': {'color': '#c8c2b2', 'palette': True, 'tag': 'wall'},
    'barrel': {'color': '#6a665e', 'palette': True},
    'iron': {'color': '#2c2a28', 'palette': True},
    'iron_flat': {'color': '#2c2a28', 'palette': True, 'double_sided': True},
    'lamp': {'color': '#f0d8a0', 'class': 'emissive', 'tag': 'lantern'},
    'plate_kanji': {'color': '#34302c', 'texture': {'sheet': 'plates', 'cell': 'plate_kanji', 'projection': 'fit'}},
    'plate_kana': {'color': '#34302c', 'texture': {'sheet': 'plates', 'cell': 'plate_kana', 'projection': 'fit'}},
    'plate_water': {'color': '#34302c', 'texture': {'sheet': 'plates', 'cell': 'plate_water', 'projection': 'fit'}},
    'plate_year': {'color': '#34302c', 'texture': {'sheet': 'plates', 'cell': 'plate_year', 'projection': 'fit'}},
}


def write(path, recipe):
    with open(path, 'w') as f:
        json.dump(recipe, f, indent=1)
        f.write('\n')


if __name__ == '__main__':
    write(os.path.join(HERE, NAME + '.asset.json'), {
        'format': 'mei-asset', 'version': 1, 'name': NAME,
        'budget': {'triangles': 300},
        'sheets': {'plates': {'image': 'art/bridge_sheet.png'}},
        'materials': MATERIALS, 'lighting': LIGHT, 'verification': POLICY,
        'lod': {'levels': [{'distance': 40, 'nodes': level1()}, {'distance': 80, 'nodes': level2()}]},
        'nodes': level0()})
    write(os.path.join(HERE, NAME + '_col.asset.json'), {
        'format': 'mei-asset', 'version': 1, 'name': NAME + '_col',
        'materials': {'solid': {'color': '#ffffff', 'palette': True}},
        'lighting': LIGHT, 'verification': POLICY, 'nodes': collision()})
    print('wrote', NAME)
