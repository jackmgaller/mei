"""Writes forest_falls_cave.asset.json and forest_falls_cave_col.asset.json beside this script
(python3 make_forest_falls_cave.py): the rock arch and the cave behind the falls (shrine town spec
3.12 and 6.3).

The asset shares water_falls's origin and yaw: place both at the foot of the falls (the pool's
surface, 12 m), -Z towards the pool. The arch is a craggy rock mass 16 m wide standing in front of
the cliff, its back (z 6-8.6) to be sunk into the cliff's terrain; under it the cave:

- the floor at y 2.0 (14 m), the ceiling 5.0-5.5 (17 m), 8.4 m wide (x -5.6 to 2.8), 5.6 m deep;
- the mouth on the front, x -2.8 to 2.8 and 2.0 to 5.0, rounded at its top corners, 0.4 to 1 m
  behind water_falls's sheet;
- a ledge at 1.0 along the front west of the mouth (x -8.3 to -3.4), a plain jump from the pool
  and another into the mouth;
- the west passage: 2.6 m wide (z 0.6 to 3.2), 2.4 m tall, out to x -8 onto the pool's west
  terrace and the foot of the kick chimney (raise the terrace to meet the floor at 2.0).

The rock blocks are irregular eight-cornered solids (seeded, so the script writes the same
recipe), crossing each other freely (depth mode); the collision is the same blocks, the cave's
floor and the ledge flat.
"""
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent.parent / 'shrine' / 'assets' / 'art'))
import make_foliage as mf  # noqa: E402  (Part)

LIGHT = {'mode': 'vertical', 'ambient': 0.5}
POLICY = {'required': True, 'depth': True, 'perspective': True}
ART = '../../../shrine/assets/art/'
MATS = {'rock': {'color': '#6a665e', 'texture': {'image': ART + 'terrain_rock.png', 'projection': 'box',
                                                 'scale': [2.4, 2.4]}},
        'mossy': {'color': '#7a8050', 'texture': {'image': ART + 'forest_mossy_stone.png', 'projection': 'box',
                                                  'scale': [2.4, 2.4]}},
        'dark': {'color': '#3a3632', 'palette': True},
        'wet': {'color': '#4e4a44', 'palette': True}}

FLOOR = 2.0
# the hollow: faces whose centre lies in here are drawn dark (the cave's inside)
INSIDE = [(-8.4, 2.95), (1.95, 6.2), (0.35, 6.1)]          # x, y, z ranges, a little beyond the walls

# the blocks: (id, x0, x1, y0, y1, z0, z1, jitter, keep flat top)
BLOCKS = [
    ('floor', -8.0, 7.0, -1.0, FLOOR, -1.3, 7.5, 0.0, True),
    ('ledge', -8.3, -3.4, -1.0, 1.0, -2.6, -0.9, 0.12, True),
    ('back', -7.6, 6.6, 1.9, 9.8, 6.0, 8.6, 0.25, False),
    ('east', 2.8, 7.4, 1.9, 9.6, -0.9, 7.2, 0.22, False),
    ('west_jamb', -8.2, -2.8, 1.9, 9.6, -1.0, 0.6, 0.22, False),
    ('west_rear', -8.0, -5.6, 1.9, 9.6, 3.2, 7.4, 0.22, False),
    ('lintel', -8.1, -5.4, 4.4, 9.6, 0.4, 3.4, 0.2, False),
    ('roof_w', -8.4, 3.6, 5.0, 9.4, -1.2, 7.8, 0.3, False),
    ('roof_e', 2.4, 7.8, 5.2, 10.2, -1.0, 8.0, 0.3, False),
    ('crag_w', -7.4, -2.2, 8.5, 11.0, -0.6, 6.0, 0.45, False),
    ('crag_m', -3.2, 2.6, 8.6, 11.6, 0.2, 7.0, 0.45, False),
    ('crag_e', 1.6, 7.2, 9.2, 11.2, -0.4, 6.6, 0.45, False),
    ('crag_back', -6.0, 5.0, 9.4, 12.6, 4.0, 8.4, 0.5, False),
    ('buttress_w', -7.7, -7.0, -1.0, 7.6, -2.4, 0.4, 0.4, False),     # (from -9.6: it closed the way south from the west passage, alpha fix)
    ('buttress_e', 4.8, 8.2, -1.0, 8.1, -2.3, 0.3, 0.4, False),
    ('boulder', -4.9, -3.3, 1.9, 3.0, 4.0, 5.4, 0.2, False),
]
# wedges rounding the mouth's top corners: (id, x outer, x inner, y low, y high, z0, z1)
HAUNCHES = [('haunch_w', -2.9, -1.9, 3.9, 5.2, -1.1, 0.5), ('haunch_e', 2.9, 1.9, 3.9, 5.25, -1.1, 0.5)]


def inside(c):
    return all(lo <= v <= hi for v, (lo, hi) in zip(c, INSIDE))


def corners(b, rng, exact=False):
    _, x0, x1, y0, y1, z0, z1, jit, flat = b
    pts = []
    for (x, y, z) in [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1),
                      (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)]:
        if exact:
            pts.append([x, y, z])
            continue
        dx, dz = rng.uniform(-jit, jit), rng.uniform(-jit, jit)
        dy = 0.0 if (flat and y == y1) else rng.uniform(-jit, jit)
        if y == y0 and y0 <= FLOOR + 0.01 and y0 > 0:
            dy = rng.uniform(-jit, 0)              # stand into the floor, never above it
        pts.append([x + dx, y + dy, z + dz])
    return pts


FACES = [((0, 1, 2, 3), [0, -1, 0]), ((4, 7, 6, 5), [0, 1, 0]), ((0, 4, 5, 1), [0, 0, -1]),
         ((2, 6, 7, 3), [0, 0, 1]), ((1, 5, 6, 2), [1, 0, 0]), ((3, 7, 4, 0), [-1, 0, 0])]


def block_part(b, rng, exact=False, col=False):
    p = mf.Part(b[0])
    c = corners(b, rng, exact)
    for idx, out in FACES:
        if out[1] < 0 and b[3] <= 0:
            continue                               # the underside of what stands in the pool
        q = [c[i] for i in idx]
        if col:
            mat = 'solid'
        else:
            centre = [sum(v[k] for v in q) / 4 for k in range(3)]
            if b[0] == 'floor' and out[1] > 0:
                mat = 'wet'
            elif inside(centre):
                mat = 'dark'
            elif out[1] > 0:
                mat = 'mossy'
            else:
                mat = 'rock'
        p.poly([q[0], q[1], q[2]], mat, out)
        p.poly([q[0], q[2], q[3]], mat, out)
    return p


def haunch_part(h, col=False):
    """A wedge in a top corner of the mouth: its slanted face looks down and in."""
    ident, xo, xi, ylo, yhi, z0, z1 = h
    p = mf.Part(ident)
    a = [[xo, ylo, z0], [xo, yhi, z0], [xi, yhi, z0]]
    b = [[xo, ylo, z1], [xo, yhi, z1], [xi, yhi, z1]]
    s = 1 if xi > xo else -1
    m = (lambda c: 'solid') if col else (lambda c: 'dark' if inside(c) else 'rock')
    p.poly(a, m(a[0]), [0, 0, -1])
    p.poly(b, 'solid' if col else 'dark', [0, 0, 1])
    for (u, v), out in [((0, 1), [-s, 0, 0]), ((1, 2), [0, 1, 0]), ((2, 0), [s, -1, 0])]:
        q = [a[u], a[v], b[v], b[u]]
        mat = 'solid' if col else ('rock' if out[1] >= 0 or out[0] == -s else 'dark')
        p.poly([q[0], q[1], q[2]], mat, out)
        p.poly([q[0], q[2], q[3]], mat, out)
    return p


def level1():
    """From 40 m: the arch's front as one notched block, the dark mouth behind it, the floor."""
    nodes = [{'id': 'front', 'op': 'extrude', 'material': 'rock', 'depth': 3.0,
              'points': [[-8.2, -1.0], [-2.8, -1.0], [-2.8, 4.2], [-2.0, 5.1], [2.0, 5.1], [2.8, 4.2],
                         [2.8, -1.0], [7.4, -1.0], [7.6, 9.8], [2.0, 11.2], [-3.0, 11.4], [-7.6, 10.6]],
              'faces': {'back': 'rock'}, 'transform': {'translate': [0, 0, 0.3]}},
             {'id': 'mass', 'op': 'box', 'size': [15.0, 9.0, 6.6], 'material': 'rock', 'open': ['bottom'],
              'faces': {'top': 'mossy'}, 'transform': {'translate': [-0.3, 5.5, 4.95]}},
             {'id': 'mouth', 'op': 'box', 'size': [5.4, 3.0, 2.0], 'material': 'dark', 'open': ['back', 'bottom'],
              'transform': {'translate': [0, 3.45, 2.05]}},
             {'id': 'sill', 'op': 'box', 'size': [5.5, 3.0, 0.9], 'material': 'wet', 'open': ['bottom'],
              'transform': {'translate': [0, 0.5, -1.0]}}]
    return nodes


def level2():
    return [{'id': 'mass', 'op': 'box', 'size': [15.6, 11.0, 8.0], 'material': 'rock', 'open': ['bottom'],
             'faces': {'top': 'mossy'},
             'decals': [{'id': 'mouth', 'face': 'back', 'material': 'dark', 'size': [5.6, 3.0], 'at': [0.3, -1.0]}],
             'transform': {'translate': [-0.3, 4.5, 3.7]}}]


def build():
    rng = random.Random(4114)
    parts = [block_part(b, rng) for b in BLOCKS] + [haunch_part(h) for h in HAUNCHES]
    return {'format': 'mei-asset', 'version': 1, 'name': 'forest_falls_cave', 'budget': {'triangles': 300},
            'materials': MATS, 'lighting': LIGHT, 'verification': POLICY,
            'nodes': [p.node() for p in parts],
            'lod': {'levels': [{'distance': 40, 'nodes': level1()}, {'distance': 100, 'nodes': level2()}]}}


def build_col():
    """The same blocks as drawn (the same seed, so the same corners): walls lean a little, the
    cave's floor and the ledge are flat."""
    rng = random.Random(4114)
    parts = [block_part(b, rng, col=True) for b in BLOCKS] + [haunch_part(h, col=True) for h in HAUNCHES]
    return {'format': 'mei-asset', 'version': 1, 'name': 'forest_falls_cave_col',
            'materials': {'solid': {'color': '#ffffff', 'palette': True}}, 'lighting': LIGHT,
            'verification': POLICY, 'nodes': [p.node() for p in parts]}


def main():
    for r in [build(), build_col()]:
        (HERE / f"{r['name']}.asset.json").write_text(json.dumps(r, indent=1) + '\n')
        print('wrote', r['name'])


if __name__ == '__main__':
    main()
