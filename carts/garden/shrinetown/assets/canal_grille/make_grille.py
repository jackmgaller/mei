"""Writes canal_grille.asset.json, canal_grille_col.asset.json and canal_grille.cameras.json
beside this file: the culvert grille where the canal leaves shrine town under the viaduct (spec
7.3, the level's south-west boundary, 1.8), 8 x 2 m. Run once and commit the outputs:
python3 carts/garden/shrinetown/assets/canal_grille/make_grille.py

Asset frame: origin at the canal's centre line at bank level (y = 0, the street), the canal
(x -4..4, water -0.4, bed -1.2 to -2) running along Z and coming from -Z: the front (-Z) faces
the water upstream; the culvert goes on under the viaduct to +Z. A concrete headwall
(the viaduct's concrete sheet) 8.6 wide (0.3 into each bank), from y -2 to its top at 0.2, 2 m
deep (z -1..1); in it the culvert's mouth, 6.8 wide, up to -0.15, dark inside, closed by a
leaning trash screen of flat bars. On its top a walkable slab across the canal with a
fall-prevention fence on each edge (1.1 high, a cutout in art/grille_sheet.png, drawn by
art/draw_grille.py) whose top rails (1.33) are geometry, to grind; a 危険 plate on the canal
side."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = 'canal_grille'


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


def quad(V, F, W, M, pts, want, mat):
    base = len(V)
    V += pts
    F += orient(V, [list(range(base, base + 4))], [want])
    W.append(want); M.append(mat)


# ---- the shape
WX = 4.3                   # headwall half width (0.3 into each bank)
MX = 3.4                   # the mouth's half width
BOT, TOP, MOUTH = -2.0, 0.2, -0.15
Z0, Z1 = -1.0, 1.0         # headwall front (the canal) and back
ZB = 0.8                   # the culvert's dark back
SCREEN_TOP_Z, SCREEN_BOT_Z = -0.92, -0.7
FENCE_Z = (-0.85, 0.85)    # the fences' planes
FENCE_LO, FENCE_HI = 0.18, 1.3
RAIL_Y = 1.33


def headwall(mouth=True, back=True):
    V, F, W, M = [], [], [], []
    if mouth:
        for x0, x1 in ((-WX, -MX), (MX, WX)):                       # the jambs
            quad(V, F, W, M, [[x0, BOT, Z0], [x1, BOT, Z0], [x1, TOP, Z0], [x0, TOP, Z0]], [0, 0, -1], 'concrete')
        quad(V, F, W, M, [[-MX, MOUTH, Z0], [MX, MOUTH, Z0], [MX, TOP, Z0], [-MX, TOP, Z0]], [0, 0, -1], 'concrete')
    else:
        quad(V, F, W, M, [[-WX, BOT, Z0], [WX, BOT, Z0], [WX, TOP, Z0], [-WX, TOP, Z0]], [0, 0, -1], 'concrete')
    quad(V, F, W, M, [[-WX, TOP, Z0], [WX, TOP, Z0], [WX, TOP, Z1], [-WX, TOP, Z1]], [0, 1, 0], 'deck')
    if back:
        quad(V, F, W, M, [[-WX, 0, Z1], [WX, 0, Z1], [WX, TOP, Z1], [-WX, TOP, Z1]], [0, 0, 1], 'concrete')
    return mesh('headwall', V, F, M)


def culvert(sides=True):
    """The mouth's inside: soffit, side walls and a dark back."""
    V, F, W, M = [], [], [], []
    quad(V, F, W, M, [[-MX, MOUTH, Z0], [MX, MOUTH, Z0], [MX, MOUTH, ZB], [-MX, MOUTH, ZB]], [0, -1, 0], 'inside')
    if sides:
        for sgn in (-1, 1):
            x = sgn * MX
            quad(V, F, W, M, [[x, BOT, Z0], [x, MOUTH, Z0], [x, MOUTH, ZB], [x, BOT, ZB]], [-sgn, 0, 0], 'inside')
    quad(V, F, W, M, [[-MX, BOT, ZB], [MX, BOT, ZB], [MX, MOUTH, ZB], [-MX, MOUTH, ZB]], [0, 0, -1], 'void')
    return mesh('culvert', V, F, M)


def screen():
    x = MX - 0.01
    y0, y1 = BOT, MOUTH - 0.01
    V = [[-x, y1, SCREEN_TOP_Z], [x, y1, SCREEN_TOP_Z], [x, y0, SCREEN_BOT_Z], [-x, y0, SCREEN_BOT_Z]]
    uv = [[-x, 0], [x, 0], [x, y1 - y0], [-x, y1 - y0]]       # 1 m a repeat
    return mesh('screen', V, orient(V, [[0, 1, 2, 3]], [[0, 0.3, -1]]), ['screen'], uv)


def fence(nid, z):
    V = [[-WX, FENCE_HI, z], [WX, FENCE_HI, z], [WX, FENCE_LO, z], [-WX, FENCE_LO, z]]
    uv = [[-WX / 2, 0], [WX / 2, 0], [WX / 2, 1], [-WX / 2, 1]]  # 2 m a repeat, one tall
    return mesh(nid, V, orient(V, [[0, 1, 2, 3]], [[0, 0, -1]]), ['fence'], uv)


def rail(nid, z):
    return {'id': nid, 'op': 'box', 'size': [2 * WX, 0.06, 0.08], 'material': 'fence_paint', 'open': ['left', 'right'],
            'transform': {'translate': [0, RAIL_Y - 0.03, z]}}


def sign():
    """The plate: its face toward the canal 5 cm in front of the fence, its grey back 5 cm
    behind it."""
    V, F, W, M = [], [], [], []
    for z, want, mat in ((FENCE_Z[0] - 0.05, [0, 0, -1], 'kiken'), (FENCE_Z[0] + 0.05, [0, 0, 1], 'sign_back')):
        quad(V, F, W, M, [[-0.3, 0.95, z], [0.3, 0.95, z], [0.3, 0.65, z], [-0.3, 0.65, z]], want, mat)
    return mesh('sign', V, F, M)


def level0():
    return [headwall(), culvert(), screen(), fence('fence_front', FENCE_Z[0]), fence('fence_back', FENCE_Z[1]),
            rail('rail_front', FENCE_Z[0]), rail('rail_back', FENCE_Z[1]), sign()]


def level1():
    """From 30 m: the headwall, the mouth's soffit and dark back, the screen and the fences."""
    return [headwall(), culvert(sides=False), screen(), fence('fence_front', FENCE_Z[0]),
            fence('fence_back', FENCE_Z[1])]


def collision():
    """The headwall as one block (a wader stops at its face, 0.08 short of the screen's top),
    the fences as walls 0.2 thick whose tops (1.33) are walkable."""
    nodes = [{'id': 'headwall', 'op': 'box', 'size': [2 * WX, TOP - BOT, Z1 - Z0], 'material': 'solid',
              'open': ['bottom'], 'transform': {'translate': [0, (TOP + BOT) / 2, 0]}}]
    for nid, z in (('fence_front', FENCE_Z[0]), ('fence_back', FENCE_Z[1])):
        nodes.append({'id': nid, 'op': 'box', 'size': [2 * WX - 0.02, RAIL_Y - 0.1, 0.2], 'material': 'solid',
                      'open': ['bottom'], 'transform': {'translate': [0, 0.1 + (RAIL_Y - 0.1) / 2, z]}})
    return nodes


POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}

MATERIALS = {
    'concrete': {'color': '#b4b0a6', 'tag': 'wall',
                 'texture': {'sheet': 'concrete', 'cell': 'wall', 'projection': 'box', 'scale': [4.0, 2.0]}},
    'deck': {'color': '#b4b0a6', 'tag': 'floor',
             'texture': {'sheet': 'concrete', 'cell': 'wall', 'projection': 'box', 'scale': [4.0, 2.0]}},
    'inside': {'color': '#4a4844', 'palette': True},
    'void': {'color': '#1e1e20', 'palette': True},
    'screen': {'color': '#3a3a38', 'double_sided': True,
               'texture': {'sheet': 'grille', 'cell': 'screen', 'projection': 'planar'}},
    'fence': {'color': '#6f8a80', 'double_sided': True,
              'texture': {'sheet': 'grille', 'cell': 'fence', 'projection': 'planar'}},
    'fence_paint': {'color': '#6f8a80', 'palette': True},
    'kiken': {'color': '#c8301e', 'texture': {'sheet': 'grille', 'cell': 'kiken', 'projection': 'fit'}},
    'sign_back': {'color': '#8e8a84', 'palette': True},
}

CAMERAS = [
    {'name': 'wading_8m', 'eye': [0.8, -0.4, -9], 'target': [0, -0.6, 0]},
    {'name': 'at_screen', 'eye': [-1.5, -0.2, -2.6], 'target': [0, -0.8, -0.8]},
    {'name': 'bank_lane', 'eye': [8, 1.6, -9], 'target': [0, 0, 0]},
    {'name': 'on_slab', 'eye': [-3.5, 1.6, 0], 'target': [3, 0.8, 0]},
    {'name': 'canal_40m', 'eye': [3, 1.6, -40], 'target': [0, 0, 0]},
    {'name': 'from_viaduct', 'eye': [-6, 10.2, 6], 'target': [0, 0, -2]},
]


def write(path, recipe):
    with open(path, 'w') as f:
        json.dump(recipe, f, indent=1)
        f.write('\n')


if __name__ == '__main__':
    write(os.path.join(HERE, NAME + '.asset.json'), {
        'format': 'mei-asset', 'version': 1, 'name': NAME,
        'budget': {'triangles': 60},
        'sheets': {'concrete': {'image': '../viaduct_span_16/art/concrete.png'},
                   'grille': {'image': 'art/grille_sheet.png'}},
        'materials': MATERIALS, 'lighting': LIGHT, 'verification': POLICY,
        'lod': {'levels': [{'distance': 30, 'nodes': level1()}]},
        'nodes': level0()})
    write(os.path.join(HERE, NAME + '_col.asset.json'), {
        'format': 'mei-asset', 'version': 1, 'name': NAME + '_col',
        'materials': {'solid': {'color': '#ffffff', 'palette': True}},
        'lighting': LIGHT, 'verification': POLICY, 'nodes': collision()})
    with open(os.path.join(HERE, NAME + '.cameras.json'), 'w') as f:
        f.write('[\n' + ',\n'.join('  ' + json.dumps(c) for c in CAMERAS) + '\n]\n')
    print('wrote', NAME)
