"""Writes canal_arched_bridge.asset.json, canal_arched_bridge_col.asset.json and
canal_arched_bridge.cameras.json beside this file: the vermilion arched bridge (taikobashi) over
the canal from the park into the west woods (spec 3.16, at z 160; the threshold (26) of 1.5),
10 x 3 m. Run once and commit the outputs:
python3 carts/garden/shrinetown/assets/canal_arched_bridge/make_arched_bridge.py

Asset frame: origin at the footprint's centre at bank level (y = 0: the park's ground, world
0.6), the walk running along X over the canal, which flows along Z under it (canal 8 m wide,
x -4..4, water at y -1.0 here (world -0.4), bed -1.8 (world -1.2)). The front (-Z) is one
railing's outer side.

The deck is a circular arc through (+-5, 0) and (0, 1.25) (radius 10.625), in six chords of
equal angle: the steepest chord is 23.4 degrees, so the whole walk is walkable in its collision.
Plank deck (the shrine's forest_planks), vermilion fascias 0.35 deep, a cutout railing 0.88
high following the arc (art/arched_rail.png, hand UVs along the arc), a top rail (kasagi) 0.9
above the deck that is a walkable, grindable rail, four end posts with gold giboshi, and stone
abutments on the banks."""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = 'canal_arched_bridge'


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


def mesh(nid, V, F, M, uvs=None):
    n = {'id': nid, 'op': 'mesh', 'vertices': [[r(c) for c in p] for p in V], 'faces': F, 'face_materials': M}
    if uvs is not None:
        n['uvs'] = [[r(c) for c in uv] for uv in uvs]
    return n


# ---- the shape
HALF = 5.0                    # half the span
CROWN = 1.25                  # deck top at the crown
R = (HALF ** 2 + CROWN ** 2) / (2 * CROWN)
CY = CROWN - R                # the arc's centre, (0, CY)
TH0 = math.asin(HALF / R)     # the arc's half angle
DEPTH = 0.35                  # fascia depth below the deck top
DZ = 1.5                      # deck edges (fascias) at z = +-DZ
RZ = 1.4                      # the railing panel's plane
KZ0, KZ1 = 1.34, 1.46         # the top rail's inner and outer edge
PANEL_LO, PANEL_HI = -0.03, 0.86
KASAGI_LO, KASAGI_HI = 0.84, 0.9
POST_X, POST_Z, POST_W, POST_H = 4.9, 1.43, 0.26, 1.15
ABUT_X0, ABUT_X1, ABUT_TOP, ABUT_BOT, ABUT_Z = 3.7, 4.4, 0.2, -1.9, 1.65


def arc(n, rad=R):
    """n + 1 points along the arc of radius rad, equal angles, from x < 0 to x > 0."""
    return [(rad * math.sin(-TH0 + 2 * TH0 * k / n), CY + rad * math.cos(-TH0 + 2 * TH0 * k / n)) for k in range(n + 1)]


def top_pts(n):
    pts = arc(n)
    pts[0], pts[-1] = (-HALF, 0.0), (HALF, 0.0)
    return pts


def bottom_pts(n):
    """The underside: the arc DEPTH lower, its ends meeting the top's at (+-5, 0)."""
    pts = arc(n, R - DEPTH)
    pts[0], pts[-1] = (-HALF, 0.0), (HALF, 0.0)
    return pts


def deck_nodes(n, fascia_sides=(-1, 1), underside=True):
    T, B = top_pts(n), bottom_pts(n)
    V = [[x, y, z] for z in (-DZ, DZ) for x, y in T]
    F = [[k, k + 1, n + 1 + k + 1, n + 1 + k] for k in range(n)]
    nodes = [mesh('deck', V, orient(V, F, [[0, 1, 0]] * n), ['planks'] * n)]
    for sgn in fascia_sides:
        out = T + list(reversed(B[1:-1]))
        V = [[x, y, sgn * DZ] for x, y in out]
        nodes.append(mesh('fascia_s' if sgn < 0 else 'fascia_n', V, orient(V, [list(range(len(out)))], [[0, 0, sgn]]),
                          ['lacquer']))
    if underside:
        V = [[x, y, z] for z in (-DZ, DZ) for x, y in B]
        F = [[k, k + 1, n + 1 + k + 1, n + 1 + k] for k in range(n)]
        nodes.append(mesh('underside', V, orient(V, F, [[0, -1, 0]] * n), ['lacquer_shade'] * n))
    return nodes


def railing(n, sgn):
    """The cutout panel along the arc, double-sided, u by arc length (2 m a repeat)."""
    T = top_pts(n)
    V, uv = [], []
    s = 0.0
    for k, (x, y) in enumerate(T):
        if k:
            s += math.hypot(x - T[k - 1][0], y - T[k - 1][1])
        V += [[x, y + PANEL_HI, sgn * RZ], [x, y + PANEL_LO, sgn * RZ]]
        uv += [[s / 2.0, 0.0], [s / 2.0, 1.0]]
    F = [[2 * k, 2 * k + 2, 2 * k + 3, 2 * k + 1] for k in range(n)]
    return mesh('railing_s' if sgn < 0 else 'railing_n', V, orient(V, F, [[0, 0, sgn]] * n), ['railing'] * n, uv)


def kasagi(n, sgn):
    """The top rail: its top face and its outer face."""
    T = top_pts(n)
    V = [[x, y + KASAGI_HI, sgn * KZ0] for x, y in T] + [[x, y + KASAGI_HI, sgn * KZ1] for x, y in T] + \
        [[x, y + KASAGI_LO, sgn * KZ1] for x, y in T]
    m = n + 1
    F = [[k, k + 1, m + k + 1, m + k] for k in range(n)] + [[m + k, m + k + 1, 2 * m + k + 1, 2 * m + k] for k in range(n)]
    W = [[0, 1, 0]] * n + [[0, 0, sgn]] * n
    return mesh('kasagi_s' if sgn < 0 else 'kasagi_n', V, orient(V, F, W), ['lacquer'] * (2 * n))


POSTS = [(-POST_X, -POST_Z), (POST_X, -POST_Z), (-POST_X, POST_Z), (POST_X, POST_Z)]


def level0():
    nodes = deck_nodes(6)
    for sgn in (-1, 1):
        nodes += [railing(6, sgn), kasagi(6, sgn)]
    for k, (x, z) in enumerate(POSTS):
        nodes.append({'id': f'post_{k}', 'op': 'box', 'size': [POST_W, POST_H, POST_W], 'material': 'lacquer',
                      'open': ['bottom'], 'transform': {'translate': [x, POST_H / 2, z]}})
        nodes.append({'id': f'giboshi_{k}', 'op': 'cone', 'radius': 0.14, 'height': 0.26, 'segments': 6, 'caps': False,
                      'material': 'gold', 'transform': {'translate': [x, POST_H + 0.12, z]}})
    for sgn, nid in ((-1, 'abutment_w'), (1, 'abutment_e')):
        nodes.append({'id': nid, 'op': 'box', 'size': [ABUT_X1 - ABUT_X0, ABUT_TOP - ABUT_BOT, 2 * ABUT_Z],
                      'material': 'stone', 'open': ['bottom', 'right' if sgn > 0 else 'left'],
                      'transform': {'translate': [sgn * (ABUT_X0 + ABUT_X1) / 2, (ABUT_TOP + ABUT_BOT) / 2, 0]}})
    return nodes


def level1():
    """From 30 m: the deck in three chords, the railings as their panels (no top rail), the
    posts without giboshi, the abutments' canal faces."""
    nodes = deck_nodes(3)
    for sgn in (-1, 1):
        nodes.append(railing(3, sgn))
    for k, (x, z) in enumerate(POSTS):
        nodes.append({'id': f'post_{k}', 'op': 'box', 'size': [POST_W, POST_H, POST_W], 'material': 'lacquer',
                      'open': ['bottom', 'top'], 'transform': {'translate': [x, POST_H / 2, z]}})
    return nodes


def level2():
    """From 60 m: the deck's top and fascias in three chords, the railing panels."""
    nodes = deck_nodes(3, underside=False)
    for sgn in (-1, 1):
        nodes.append(railing(3, sgn))
    return nodes


def prism_z(outline, z0, z1):
    n = len(outline)
    V = [[x, y, z0] for x, y in outline] + [[x, y, z1] for x, y in outline]
    area = sum(outline[i][0] * outline[(i + 1) % n][1] - outline[(i + 1) % n][0] * outline[i][1] for i in range(n))
    F, W = [], []
    for i in range(n):
        j = (i + 1) % n
        e = (outline[j][0] - outline[i][0], outline[j][1] - outline[i][1])
        out = (e[1], -e[0]) if area > 0 else (-e[1], e[0])
        F.append([i, j, n + j, n + i]); W.append([out[0], out[1], 0])
    F += [list(range(n)), list(range(n, 2 * n))]
    W += [[0, 0, -1], [0, 0, 1]]
    return V, orient(V, F, W), ['solid'] * len(F)


def collision():
    """The deck as one solid (its top the walk in the render's six chords, its underside the
    soffit), the railings as fences 0.2 thick whose tops (0.93 above the walk) are walkable,
    the posts and abutments as boxes."""
    T, B = top_pts(6), bottom_pts(6)
    nodes = [mesh('deck', *prism_z(T + list(reversed(B[1:-1])), -DZ, DZ))]
    for sgn, nid in ((-1, 'railing_s'), (1, 'railing_n')):
        out = [(x, y + 0.93) for x, y in T] + [(x, y - 0.05) for x, y in reversed(T)]
        z0, z1 = sorted((sgn * 1.28, sgn * (DZ - 0.01)))
        nodes.append(mesh(nid, *prism_z(out, z0, z1)))
    for k, (x, z) in enumerate(POSTS):
        nodes.append({'id': f'post_{k}', 'op': 'box', 'size': [POST_W, POST_H + 0.25, POST_W], 'material': 'solid',
                      'open': ['bottom'], 'transform': {'translate': [x, (POST_H + 0.25) / 2, z]}})
    for sgn, nid in ((-1, 'abutment_w'), (1, 'abutment_e')):
        nodes.append({'id': nid, 'op': 'box', 'size': [ABUT_X1 - ABUT_X0, ABUT_TOP - ABUT_BOT, 2 * ABUT_Z],
                      'material': 'solid', 'open': ['bottom'],
                      'transform': {'translate': [sgn * (ABUT_X0 + ABUT_X1) / 2, (ABUT_TOP + ABUT_BOT) / 2, 0]}})
    return nodes


POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}
SHRINE_ART = '../../../shrine/assets/art/'

MATERIALS = {
    'planks': {'color': '#8a6446', 'tag': 'floor',
               'texture': {'image': SHRINE_ART + 'forest_planks.png', 'projection': 'box', 'scale': [2.0, 2.0]}},
    'lacquer': {'color': '#d8462a', 'palette': True},
    'lacquer_shade': {'color': '#a8321e', 'palette': True},
    'gold': {'color': '#d8b048', 'palette': True},
    'railing': {'color': '#d8462a', 'double_sided': True,
                'texture': {'image': 'art/arched_rail.png', 'projection': 'planar'}},
    'stone': {'color': '#b4ae9e', 'tag': 'wall',
              'texture': {'image': SHRINE_ART + 'arch_stone.png', 'projection': 'box', 'scale': [2.4, 2.4]}},
}

CAMERAS = [
    {'name': 'park_10m', 'eye': [-12, 1.6, -7], 'target': [0, 0.8, 0]},
    {'name': 'approach', 'eye': [-9, 1.6, 0.2], 'target': [0, 1.4, 0]},
    {'name': 'crown', 'eye': [0, 2.85, 0.4], 'target': [5, 0.8, -0.2]},
    {'name': 'wading', 'eye': [0, -0.2, -9], 'target': [0, 0.6, 0]},
    {'name': 'kasagi_top', 'eye': [-4.6, 2.6, -1.4], 'target': [0, 2.4, -1.4]},
    {'name': 'lane_30m', 'eye': [18, 1.6, -24], 'target': [0, 0.8, 0]},
    {'name': 'yagura_above', 'eye': [-24, 9, -6], 'target': [0, 0.6, 0]},
]


def write(path, recipe):
    with open(path, 'w') as f:
        json.dump(recipe, f, indent=1)
        f.write('\n')


if __name__ == '__main__':
    write(os.path.join(HERE, NAME + '.asset.json'), {
        'format': 'mei-asset', 'version': 1, 'name': NAME,
        'budget': {'triangles': 200},
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
