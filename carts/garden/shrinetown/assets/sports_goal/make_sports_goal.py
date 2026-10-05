#!/usr/bin/env python3
"""Writes the shrine town's schoolyard football goal (spec 3.15, assets.md 4.1 #34) beside this
script: sports_goal.asset.json and sports_goal_col.asset.json.

A junior (少年用) goal, 5.0 x 2.15 m inside the posts, as a school sports ground has: white
square-section steel posts and crossbar, two stays running back from the crossbar's ends to a
ground bar 2 m behind the goal line, and a white net hung on them (a lattice cutout, both sides
drawn). Two are placed, one at each end of the sports ground.

Asset frame: origin at the centre of the 5.2 x 2.0 m footprint; the mouth faces -Z (the goal
line is z = -0.95, the ground bar z = +1.0).

What the player uses: the crossbar is a **rail** (grind it, or hang from it): a `rail` path from
(-2.5, 2.25, -0.95) to (2.5, 2.25, -0.95) for the world to place. Its collision is also a ledge:
a 0.2 x 0.2 bar with its top at 2.25 (stand on it, or grab it from a jump). The posts are walls;
the net is not solid, so the player can walk into the goal.

Run with the standard library: python3 carts/garden/shrinetown/assets/sports_goal/make_sports_goal.py
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = 'sports_goal'

POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}

IN_W, IN_H = 5.0, 2.15       # inside the posts, under the crossbar
T = 0.10                     # section of posts and crossbar
PX = IN_W / 2 + T / 2        # post centres 2.55
LINE_Z = -0.95               # the goal line (posts' centre)
BACK_Z = 0.97                # the ground bar's centre
TOP = IN_H + T               # 2.25
WHITE = '#eceae4'


def r(v):
    return [r(x) for x in v] if isinstance(v, (list, tuple)) else round(v, 4)


def box(id_, mat, size, at, open_=None):
    n = {'id': id_, 'op': 'box', 'size': r(list(size)), 'material': mat,
         'transform': {'translate': r(list(at))}}
    if open_:
        n['open'] = list(open_)
    return n


def stay(id_, side, radius):
    """A three-sided bar from the crossbar's end down to the ground bar's end."""
    y0, z0, y1, z1 = IN_H + T / 2, LINE_Z, 0.03, BACK_Z
    length = math.hypot(y0 - y1, z1 - z0)
    tilt = math.degrees(math.atan2(z1 - z0, y0 - y1))      # from vertical toward +Z (top back)
    return {'id': id_, 'op': 'cylinder', 'radius': radius, 'height': r(length), 'segments': 3,
            'caps': False, 'material': 'frame',
            'transform': {'rotate': [r(-tilt), 0, 0],
                          'translate': r([side * PX, (y0 + y1) / 2, (z0 + z1) / 2])}}


def net_nodes():
    x = PX
    back = {'id': 'net_back', 'op': 'mesh', 'material': 'net',
            'vertices': r([[-x, IN_H, LINE_Z + 0.04], [x, IN_H, LINE_Z + 0.04], [x, 0.0, BACK_Z], [-x, 0.0, BACK_Z]]),
            'faces': [[0, 1, 2, 3]]}
    sides = {'id': 'net_sides', 'op': 'mesh', 'material': 'net',
             'vertices': r([[-x, 0.0, LINE_Z + 0.04], [-x, IN_H, LINE_Z + 0.04], [-x, 0.0, BACK_Z],
                            [x, 0.0, LINE_Z + 0.04], [x, IN_H, LINE_Z + 0.04], [x, 0.0, BACK_Z]]),
             'faces': [[0, 1, 2], [3, 5, 4]]}
    return [back, sides]


def main():
    materials = {
        'frame': {'color': WHITE, 'palette': True},
        'net': {'color': WHITE, 'double_sided': True,
                'texture': {'pattern': 'lattice', 'size': 8, 'params': {'count': 2, 'bar': 1},
                            'colors': [WHITE, '#000000'], 'clear': '#000000',
                            'projection': 'box', 'scale': [0.25, 0.25]}},
    }
    nodes = []
    for s, side in ((-1, 'w'), (1, 'e')):
        nodes.append(box('post_' + side, 'frame', [T, IN_H, T], [s * PX, IN_H / 2, LINE_Z], open_=['bottom', 'top']))
        nodes.append(stay('stay_' + side, s, 0.035))
    nodes.append(box('crossbar', 'frame', [2 * PX + T, T, T], [0, IN_H + T / 2, LINE_Z]))
    nodes.append(box('ground_bar', 'frame', [2 * PX + 0.08, 0.06, 0.06], [0, 0.03, BACK_Z], open_=['bottom']))
    nodes += net_nodes()

    l1 = []
    for s, side in ((-1, 'w'), (1, 'e')):
        l1.append({'id': 'post_' + side, 'op': 'cylinder', 'radius': 0.07, 'height': IN_H, 'segments': 3,
                   'caps': False, 'material': 'frame', 'transform': {'translate': r([s * PX, IN_H / 2, LINE_Z])}})
    l1.append({'id': 'crossbar', 'op': 'cylinder', 'radius': 0.07, 'height': r(2 * PX + T), 'segments': 3,
               'caps': False, 'material': 'frame',
               'transform': {'rotate': [0, 0, 90], 'translate': r([0, IN_H + T / 2, LINE_Z])}})
    l1 += net_nodes()

    recipe = {
        'format': 'mei-asset', 'version': 1, 'name': NAME,
        'budget': {'triangles': 60},
        'materials': materials, 'lighting': LIGHT, 'verification': POLICY,
        'nodes': nodes,
        'lod': {'levels': [{'distance': 24, 'nodes': l1}], 'cull': 80},
    }
    (HERE / (NAME + '.asset.json')).write_text(json.dumps(recipe, indent=1) + '\n')

    S = 'solid'
    col = [
        box('post_w', S, [0.2, IN_H + 0.02, 0.16], [-PX, (IN_H + 0.02) / 2, LINE_Z], open_=['bottom', 'top']),
        box('post_e', S, [0.2, IN_H + 0.02, 0.16], [PX, (IN_H + 0.02) / 2, LINE_Z], open_=['bottom', 'top']),
        box('crossbar', S, [2 * PX + 0.3, 0.2, 0.2], [0, TOP - 0.1, LINE_Z]),
    ]
    colr = {'format': 'mei-asset', 'version': 1, 'name': NAME + '_col',
            'materials': {S: {'color': '#ffffff', 'palette': True}},
            'lighting': LIGHT, 'verification': POLICY, 'nodes': col}
    (HERE / (NAME + '_col.asset.json')).write_text(json.dumps(colr, indent=1) + '\n')


if __name__ == '__main__':
    main()
