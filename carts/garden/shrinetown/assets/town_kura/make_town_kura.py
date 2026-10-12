#!/usr/bin/env python3
"""Writes town_kura.asset.json and town_kura_col.asset.json beside this script: the white
storehouse (蔵) in the fire tower's yard in the back alleys (shrine town spec 3.3), the second wall
of the tower's kick pair.

    python3 carts/garden/shrinetown/assets/town_kura/make_town_kura.py      (standard library)

Origin at the centre of its 3 x 8 m footprint at the yard's ground, the long sides along Z, the
door on +X. Plastered walls to 7.6 over a dark tiled base (1.0 m), a gable roof of grey kawara
along Z: ridge 8.0, eaves 7.52 at 0.3 m past the walls, 15 degrees, so the roof is a floor (the
spec's 8.0 roof). The -X wall is plain and straight from the ground to the eave: the kick wall,
2.85 m from the fire tower's +X face when the kura stands at x 106.3-109.3 beside the tower at
(102, 74) (FOLLOWUPS.md, the fire tower). The walls and roof use the town's common plaster and
kawara tiles (../town_alley_house_a/art/town_common.png), so the kura adds no texture of its own.
Levels: L1 from 16 m (no door, windows or base), L2 from 40 m (walls and roof as one block).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
HX, HZ = 1.5, 4.0            # half the walls' footprint
WALL = 7.6                   # wall top (the eave line)
RIDGE, EAVE, OVER = 8.0, 7.52, 0.3
THICK = 0.12                 # the roof slab
BASE = 1.0                   # the dark base band
POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}


def r(v):
    return [round(c, 4) for c in v]


def outward(verts, faces, centre):
    """Wind each face so its normal points away from `centre` (the parts are convex)."""
    out = []
    for f in faces:
        p = [verts[i] for i in f]
        n = [0.0, 0.0, 0.0]
        for i, a in enumerate(p):
            b = p[(i + 1) % len(p)]
            n[0] += (a[1] - b[1]) * (a[2] + b[2])
            n[1] += (a[2] - b[2]) * (a[0] + b[0])
            n[2] += (a[0] - b[0]) * (a[1] + b[1])
        c = [sum(q[k] for q in p) / len(p) for k in range(3)]
        d = sum(n[k] * (c[k] - centre[k]) for k in range(3))
        out.append(list(f) if d >= 0 else list(reversed(f)))
    return out


def prism(ident, section, z0, z1, mats, open_ends=False):
    """A polygon in (x, y) extruded along Z; mats: one per side (in section order), then the ends."""
    n = len(section)
    v = [[x, y, z0] for x, y in section] + [[x, y, z1] for x, y in section]
    faces = [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    fm = list(mats[:n])
    if not open_ends:
        faces += [list(range(n)), list(range(n, 2 * n))]
        fm += [mats[n], mats[n]]
    cx = sum(x for x, _ in section) / n
    cy = sum(y for _, y in section) / n
    return {'id': ident, 'op': 'mesh', 'vertices': [r(p) for p in v],
            'faces': outward(v, faces, [cx, cy, (z0 + z1) / 2]), 'face_materials': fm}


def box(ident, mat, size, at, open_=None):
    n = {'id': ident, 'op': 'box', 'size': r(size), 'material': mat, 'transform': {'translate': r(at)}}
    if open_:
        n['open'] = list(open_)
    return n


ROOF = [(-HX - OVER, EAVE - THICK), (-HX - OVER, EAVE), (0.0, RIDGE), (HX + OVER, EAVE),
        (HX + OVER, EAVE - THICK), (0.0, RIDGE - THICK)]
GABLE = [(-HX, 0.0), (HX, 0.0), (HX, WALL), (0.0, RIDGE - THICK), (-HX, WALL)]


def walls(mat='plaster'):
    return prism('walls', GABLE, -HZ, HZ, [None, mat, mat, mat, mat, mat], open_ends=False)


def roof():
    return prism('roof', ROOF, -HZ - OVER, HZ + OVER,
                 ['eave', 'kawara', 'kawara', 'eave', 'soffit', 'soffit', 'eave'])


def body_walls():
    """The walls without a floor: the section's first side (the ground) is dropped."""
    w = walls()
    keep = [i for i, m in enumerate(w['face_materials']) if m is not None]
    w['faces'] = [w['faces'][i] for i in keep]
    w['face_materials'] = [w['face_materials'][i] for i in keep]
    return w


def detail():
    return [
        box('base', 'namako', [2 * HX + 0.04, BASE, 2 * HZ + 0.04], [0, BASE / 2, 0], ['top', 'bottom']),
        box('door', 'door', [0.08, 2.1, 1.3], [HX + 0.04, 1.05, 1.2], ['left', 'bottom']),
        box('win_e', 'window', [0.06, 0.6, 0.7], [HX + 0.03, 5.6, -1.6], ['left']),
        box('win_n', 'window', [0.7, 0.6, 0.06], [0, 5.9, HZ + 0.03], ['back']),
    ]


MATERIALS = {
    'plaster': {'color': '#e8e2d2', 'tag': 'wall', 'texture': {
        'sheet': 'town_common', 'cell': 'plaster', 'projection': 'box', 'scale': [2, 2]}},
    'kawara': {'color': '#565c64', 'tag': 'roof', 'texture': {
        'sheet': 'town_common', 'cell': 'kawara', 'projection': 'box', 'scale': [2, 2], 'rotate': 90}},
    'eave': {'color': '#3a3e44', 'palette': True, 'tag': 'roof'},
    'soffit': {'color': '#5a4a3e', 'palette': True},
    'namako': {'color': '#34383e', 'palette': True},
    'door': {'color': '#4a3a2e', 'palette': True},
    'window': {'color': '#26282c', 'palette': True},
}


def recipe():
    plain = {'id': 'block', 'op': 'box', 'size': [2 * HX, WALL, 2 * HZ], 'material': 'plaster',
             'open': ['bottom'], 'transform': {'translate': [0, WALL / 2, 0]}}
    return {
        'format': 'mei-asset', 'version': 1, 'name': 'town_kura',
        'sheets': {'town_common': {'image': '../town_alley_house_a/art/town_common.png'}},
        'budget': {'triangles': 80},
        'materials': MATERIALS,
        'lighting': LIGHT,
        'verification': POLICY,
        'nodes': [body_walls(), roof()] + detail(),
        'lod': {'levels': [{'distance': 16, 'nodes': [body_walls(), roof()]},
                           {'distance': 40, 'nodes': [plain, roof()]}]},
    }


def collision():
    w = walls('solid')
    w['face_materials'] = ['solid'] * len(w['faces'])
    rf = roof()
    rf['face_materials'] = ['solid'] * len(rf['faces'])
    # tag 'tile': the footsteps' surface byte 7 (carts/garden/README.md, "Surfaces"): what
    # stands on the kura is its roof
    return {'format': 'mei-asset', 'version': 1, 'name': 'town_kura_col',
            'materials': {'solid': {'color': '#ffffff', 'palette': True, 'tag': 'tile'}},
            'lighting': LIGHT, 'verification': POLICY, 'nodes': [w, rf]}


if __name__ == '__main__':
    for name, data in (('town_kura', recipe()), ('town_kura_col', collision())):
        (HERE / f'{name}.asset.json').write_text(json.dumps(data, indent=1) + '\n')
    print('wrote town_kura, town_kura_col')
