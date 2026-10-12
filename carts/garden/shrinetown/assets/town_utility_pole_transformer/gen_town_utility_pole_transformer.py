"""Writes town_utility_pole_transformer.asset.json and its _col: the shrine street's
`street_utility_pole` (same 9 m pole, same crossarm at 8.25-8.35 m, same texture) with a
pole-mounted transformer can, two white bushings and two hanging insulators.

Wire attachment points (local coordinates, wires run along Z): the clamps at the bottom of the
two hanging insulators, (-0.80, 8.00, 0) and (+0.80, 8.00, 0).

Also town_utility_pole_tall and its _col: the same pole 2.5 m taller (11.5 m, the crossarm, can
and insulators raised with it, wires at 10.5), for the front road's two poles either side of the
overpass, whose span crosses the overpass's deck (7.0) and handrails (8.12).

Both have a level 1 from 30 m (a square shaft and the crossarm, 14 triangles: alpha review r01 #3)
and are culled at 56 m, with the wires' sweeps (place/street.py), so a pole and its wires go
together. Run: python3 gen_town_utility_pole_transformer.py (standard library only).
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
base = json.load(open(REPO / 'carts/garden/shrine/assets/street_utility_pole.asset.json'))
nodes = {n['id']: n for n in base['nodes']}


def prism(cx, cz, y0, y1, r0, r1, n, rot=0.0, cap=True):
    """An n-sided frustum: bottom ring, top ring, sides, then the top cap; bottom open."""
    v = []
    for y, r in ((y0, r0), (y1, r1)):
        for k in range(n):
            a = rot + 2 * math.pi * k / n
            v.append([round(cx + r * math.cos(a), 4), y, round(cz + r * math.sin(a), 4)])
    f = []
    for k in range(n):
        k2 = (k + 1) % n
        f.append([k, n + k, n + k2, k2])
    if cap:
        f.append([n + k for k in range(n)])
    return v, f


def outward(v, f):
    """Flip any face whose normal points toward the mesh centre."""
    c = [sum(p[i] for p in v) / len(v) for i in range(3)]
    out = []
    for face in f:
        a, b, d = (v[face[0]], v[face[1]], v[face[2]])
        u = [b[i] - a[i] for i in range(3)]
        w = [d[i] - a[i] for i in range(3)]
        nrm = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
        m = [sum(v[i][j] for i in face) / len(face) - c[j] for j in range(3)]
        out.append(face if sum(nrm[i] * m[i] for i in range(3)) > 0 else face[::-1])
    return out


def mesh(id_, v, f, mats):
    f = outward(v, f)
    return {'id': id_, 'op': 'mesh', 'vertices': v, 'faces': f, 'face_materials': mats}


pole = nodes['pole']
arm = nodes['crossarm']

# transformer can: hexagon with flats facing +-Z, back flat sunk into the pole, open bottom
R = 0.22
cz = 0.10 + R * math.cos(math.pi / 6)
tv, tf = prism(0.0, cz, 6.55, 7.3, R, R, 6)
tank = mesh('transformer', tv, tf, ['tank'] * (len(tf) - 1) + ['lid'])

# two bushings on the lid
bush = []
for i, x in enumerate((-0.08, 0.08)):
    ring = [[round(x + 0.05 * math.cos(math.pi / 2 + 2 * math.pi * k / 3), 4), 7.26,
             round(cz + 0.05 * math.sin(math.pi / 2 + 2 * math.pi * k / 3), 4)] for k in range(3)]
    bv = ring + [[x, 7.52, cz]]
    bf = [[k, 3, (k + 1) % 3] for k in range(3)]
    bush.append(mesh('bushing_%d' % i, bv, bf, ['porcelain'] * len(bf)))

# hanging insulators under the crossarm's ends: their bottom is the wire's height, 8.0 m
hang = []
for i, x in enumerate((-0.8, 0.8)):
    hv, hf = prism(x, 0.0, 8.0, 8.26, 0.03, 0.065, 4, math.pi / 4, cap=False)
    hang.append(mesh('insulator_%d' % i, hv, hf, ['porcelain'] * len(hf)))

def level1(lift=0.0):
    """From 30 m: the shaft as a square prism (open at the bottom), the crossarm."""
    top = 9.0 + lift
    h = 0.17
    v = [[-h, 0.0, -h], [h, 0.0, -h], [h, 0.0, h], [-h, 0.0, h],
         [-h, top, -h], [h, top, -h], [h, top, h], [-h, top, h]]
    f = [[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7], [4, 5, 6, 7]]
    shaft = mesh('pole', v, f, ['concrete'] * 4 + ['cap'])
    return [shaft, raised(arm, lift)]


def raised(node, lift, stretch=None):
    """NODE with every vertex lifted by LIFT; with STRETCH (y), only the vertices at or above it
    (the shaft's top ring, its cap)."""
    n = json.loads(json.dumps(node))
    for p in n['vertices']:
        if stretch is None or p[1] >= stretch - 1e-6:
            p[1] = round(p[1] + lift, 4)
    return n


recipe = {
    'format': 'mei-asset', 'version': 1, 'name': 'town_utility_pole_transformer',
    'sheets': {'street': {'image': 'art/street_sheet.png'}},
    'budget': {'triangles': 60},
    'materials': {
        'concrete': base['materials']['concrete'],
        'cap': base['materials']['cap'],
        'steel': base['materials']['steel'],
        'tank': {'color': '#7c847c', 'palette': True},
        'lid': {'color': '#5a5e58', 'palette': True},
        'porcelain': {'color': '#eceae4', 'palette': True},
    },
    'lighting': {'mode': 'vertical', 'ambient': 0.5},
    'verification': {'required': True, 'depth': True, 'perspective': True},
    'nodes': [pole, arm, tank] + bush + hang,
    'lod': {'levels': [{'distance': 30, 'nodes': level1()}], 'cull': 56},
}
with open(HERE / 'town_utility_pole_transformer.asset.json', 'w') as fh:
    json.dump(recipe, fh, indent=1)

col = json.load(open(REPO / 'carts/garden/shrine/assets/street_utility_pole_col.asset.json'))
col['name'] = 'town_utility_pole_transformer_col'
with open(HERE / 'town_utility_pole_transformer_col.asset.json', 'w') as fh:
    json.dump(col, fh, indent=1)

# the tall pole: the shaft stretched by LIFT, everything on it raised
LIFT = 2.5
tall = json.loads(json.dumps(recipe))
tall['name'] = 'town_utility_pole_tall'
tall['materials']['concrete'] = json.loads(json.dumps(recipe['materials']['concrete']))
tall['materials']['concrete']['texture']['scale'] = [1.2, 9.0 + LIFT]
tall['nodes'] = [raised(pole, LIFT, stretch=9.0)] + [raised(n, LIFT) for n in [arm, tank] + bush + hang]
tall['lod'] = {'levels': [{'distance': 30, 'nodes': level1(LIFT)}], 'cull': 56}
with open(HERE / 'town_utility_pole_tall.asset.json', 'w') as fh:
    json.dump(tall, fh, indent=1)
col_tall = raised(col['nodes'][0], LIFT, stretch=9.0)
col = json.loads(json.dumps(col))
col['name'] = 'town_utility_pole_tall_col'
col['nodes'] = [col_tall] + [raised(n, LIFT) for n in col['nodes'][1:]]
with open(HERE / 'town_utility_pole_tall_col.asset.json', 'w') as fh:
    json.dump(col, fh, indent=1)
