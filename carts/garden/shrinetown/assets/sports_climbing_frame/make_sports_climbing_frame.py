#!/usr/bin/env python3
"""Writes the shrine town's schoolyard climbing frame (spec 3.15, assets.md 4.1 #33) beside this
script: sports_climbing_frame.asset.json and sports_climbing_frame_col.asset.json.

Two schoolyard classics in one steel frame, painted as 1990s playground steel is:
- climbing poles (登り棒) at the back (+Z): a blue frame of two posts and a top beam at 4.5 m,
  four bare steel poles hanging between them;
- an overhead ladder (雲梯) at 2.4 m running from the pole frame to the front (-Z): red side
  rails on blue posts, yellow rungs, and a ladder up at its front end.

Footprint 5.8 x 4.5 (x -2.9..2.9, z -2.4..2.0), top 4.5. The rungs of both ladders are cutout
textures on one face each (texel grids in the recipe, no images).

What the player uses (routes):
- The four climbing poles are `pole` entities: x -2.2, -1.1, 1.1, 2.2 at z POLE_Z, from 0 to
  4.38 (the beam's underside). Not in the collision.
- The top beam is a balance beam at 4.5 (collision 0.2 wide, 4.28..4.52, x -2.85..2.85): reached
  by a pole's top or a pole jump.
- The overhead ladder's top is a walkable strip at 2.48 (collision 0.72 wide, z -2.38..1.98),
  reached by its front ladder (a double jump, 3.4) or from the ground; its long edges are
  ledges to grab. Hanging along it under the rungs is a `rail` path in hang mode: (0, 2.3,
  -2.2) to (0, 2.3, 1.8), for the world to place.

Run with the standard library:
python3 carts/garden/shrinetown/assets/sports_climbing_frame/make_sports_climbing_frame.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = 'sports_climbing_frame'

POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}

# ---- dimensions (metres) ---------------------------------------------------------------------
POLE_Z = 2.0                 # the pole frame's plane
BEAM_TOP, BEAM_H, BEAM_Z = 4.5, 0.12, 0.16
BEAM_X = 2.85                # beam ends
POST_X, POST_W = 2.75, 0.10  # the pole frame's posts
POLES_X = [-2.2, -1.1, 1.1, 2.2]
POLE_R = 0.03

LAD_TOP, LAD_H = 2.46, 0.10  # overhead ladder's rails: top, height
RAIL_X, RAIL_W = 0.30, 0.12  # rail centres +-RAIL_X, square section RAIL_W x LAD_H
LAD_Z0, LAD_Z1 = -2.38, 1.98 # rails' ends
UP_Z = -2.30                 # the front ladder's uprights
BACK_Z = 1.88                # the back posts (just in front of the pole frame)
SMALL_W = 0.06               # the ladder's posts and uprights


def r(v):
    return [r(x) for x in v] if isinstance(v, (list, tuple)) else round(v, 4)


def box(id_, mat, size, at, open_=None):
    n = {'id': id_, 'op': 'box', 'size': r(list(size)), 'material': mat,
         'transform': {'translate': r(list(at))}}
    if open_:
        n['open'] = list(open_)
    return n


def prism(id_, mat, radius, height, at, rot=None):
    """A three-sided pole without caps: 6 triangles."""
    n = {'id': id_, 'op': 'cylinder', 'radius': radius, 'height': r(height), 'segments': 3,
         'caps': False, 'material': mat, 'transform': {'translate': r(list(at))}}
    if rot:
        n['transform']['rotate'] = rot
    return n


def quad(id_, mat, verts):
    return {'id': id_, 'op': 'mesh', 'vertices': r(verts), 'faces': [[0, 1, 2, 3]], 'material': mat}


def rung_texels(n_rungs, rows_per, width=8):
    """Rungs across the texture (rows), clear between."""
    out = []
    for k in range(n_rungs * rows_per):
        out.append(('1' if k % rows_per == rows_per // 2 else '0') * width)
    return out


BEAM_Y = BEAM_TOP - BEAM_H / 2
RAIL_Y = LAD_TOP - LAD_H / 2
RAIL_BOT = LAD_TOP - LAD_H
RUNG_Y = RAIL_Y               # the rungs' face, through the rails' middle
RX = RAIL_X - RAIL_W / 2      # the rails' inner faces
POLE_TOP = BEAM_TOP - 0.06    # poles end inside the beam


def frame_nodes():
    n = []
    # the pole frame
    for s, side in ((-1, 'w'), (1, 'e')):
        n.append(box('post_' + side, 'frame', [POST_W, BEAM_Y, POST_W], [s * POST_X, BEAM_Y / 2, POLE_Z],
                     open_=['bottom', 'top']))
    n.append(box('beam', 'beam', [2 * BEAM_X, BEAM_H, BEAM_Z], [0, BEAM_Y, POLE_Z]))
    for k, x in enumerate(POLES_X):
        n.append(prism('pole_%d' % (k + 1), 'steel', POLE_R, POLE_TOP, [x, POLE_TOP / 2, POLE_Z]))
    # the overhead ladder
    for s, side in ((-1, 'w'), (1, 'e')):
        n.append(box('rail_' + side, 'rail', [RAIL_W, LAD_H, LAD_Z1 - LAD_Z0],
                     [s * RAIL_X, RAIL_Y, (LAD_Z0 + LAD_Z1) / 2]))
        n.append(box('back_post_' + side, 'frame', [SMALL_W, RAIL_Y, SMALL_W], [s * RAIL_X, RAIL_Y / 2, BACK_Z],
                     open_=['bottom', 'top']))
        n.append(box('upright_' + side, 'frame', [SMALL_W, RAIL_Y, SMALL_W], [s * RAIL_X, RAIL_Y / 2, UP_Z],
                     open_=['bottom', 'top']))
    # rungs: overhead, one horizontal face between the rails (seen from above u +X, v -Z)
    z0, z1 = LAD_Z0 + 0.06, LAD_Z1 - 0.06
    n.append(quad('rungs', 'rungs', [[-RX, RUNG_Y, z1], [RX, RUNG_Y, z1], [RX, RUNG_Y, z0], [-RX, RUNG_Y, z0]]))
    # the front ladder's rungs, one face between its uprights (seen from -Z)
    ux = RAIL_X - SMALL_W / 2
    n.append(quad('steps', 'steps', [[-ux, RAIL_BOT - 0.02, UP_Z], [ux, RAIL_BOT - 0.02, UP_Z],
                                     [ux, 0.0, UP_Z], [-ux, 0.0, UP_Z]]))
    return n


def l1_nodes():
    """From 24 m: three-sided posts, rails and beam; no rungs, no poles."""
    n = []
    for s, side in ((-1, 'w'), (1, 'e')):
        n.append(prism('post_' + side, 'frame', 0.07, BEAM_Y, [s * POST_X, BEAM_Y / 2, POLE_Z]))
        n.append(prism('rail_' + side, 'rail', 0.08, LAD_Z1 - LAD_Z0, [s * RAIL_X, RAIL_Y, (LAD_Z0 + LAD_Z1) / 2],
                       rot=[90, 0, 0]))
        for z, nm in ((BACK_Z, 'back_post_'), (UP_Z, 'upright_')):
            n.append(prism(nm + side, 'frame', 0.05, RAIL_BOT, [s * RAIL_X, RAIL_BOT / 2, z]))
    n.append(prism('beam', 'beam', 0.09, 2 * BEAM_X, [0, BEAM_Y, POLE_Z], rot=[0, 0, 90]))
    return n                  # the poles (6 cm) are under a pixel from 24 m


def l2_nodes():
    """From 50 m: the posts, the beam and the ladder as three-sided bars."""
    n = []
    for s, side in ((-1, 'w'), (1, 'e')):
        n.append(prism('post_' + side, 'frame', 0.08, BEAM_Y, [s * POST_X, BEAM_Y / 2, POLE_Z]))
    n.append(prism('beam', 'beam', 0.1, 2 * BEAM_X, [0, BEAM_Y, POLE_Z], rot=[0, 0, 90]))
    n.append(prism('ladder', 'rail', 0.2, LAD_Z1 - LAD_Z0, [0, RAIL_Y, (LAD_Z0 + LAD_Z1) / 2], rot=[90, 0, 0]))
    return n


def main():
    materials = {
        'frame': {'color': '#3a6ab0', 'palette': True},
        'beam': {'color': '#e8782a', 'palette': True},
        'rail': {'color': '#d8462a', 'palette': True},
        'steel': {'color': '#c8c4b8', 'palette': True},
        'rungs': {'color': '#f0c030', 'double_sided': True,
                  'texture': {'texels': rung_texels(16, 4), 'colors': ['#000000', '#f0c030'],
                              'clear': '#000000', 'projection': 'fit'}},
        'steps': {'color': '#f0c030', 'double_sided': True,
                  'texture': {'texels': rung_texels(8, 4), 'colors': ['#000000', '#f0c030'],
                              'clear': '#000000', 'projection': 'fit'}},
    }
    recipe = {
        'format': 'mei-asset', 'version': 1, 'name': NAME,
        'budget': {'triangles': 150},
        'materials': materials, 'lighting': LIGHT, 'verification': POLICY,
        'nodes': frame_nodes(),
        'lod': {'levels': [{'distance': 24, 'nodes': l1_nodes()}, {'distance': 50, 'nodes': l2_nodes()}],
                'cull': 90},
    }
    (HERE / (NAME + '.asset.json')).write_text(json.dumps(recipe, indent=1) + '\n')

    S = 'solid'
    slab_bot = LAD_TOP - 0.24 + 0.02       # the strip: 0.24 thick, top 0.02 proud of the rails
    col = [
        box('post_w', S, [0.16, 4.30, 0.14], [-(POST_X - 0.03), 2.15, POLE_Z], open_=['bottom', 'top']),
        box('post_e', S, [0.16, 4.30, 0.14], [(POST_X - 0.03), 2.15, POLE_Z], open_=['bottom', 'top']),
        box('beam', S, [2 * BEAM_X, 0.24, 0.2], [0, 4.40, POLE_Z]),
        box('ladder_top', S, [0.72, 0.24, LAD_Z1 - LAD_Z0], [0, slab_bot + 0.12, (LAD_Z0 + LAD_Z1) / 2]),
        box('back_posts', S, [0.64, slab_bot + 0.02, 0.2], [0, (slab_bot + 0.02) / 2, BACK_Z - 0.04],
            open_=['bottom', 'top']),
        box('front_ladder', S, [0.64, slab_bot + 0.02, 0.2], [0, (slab_bot + 0.02) / 2, UP_Z - 0.04],
            open_=['bottom', 'top']),
    ]
    colr = {'format': 'mei-asset', 'version': 1, 'name': NAME + '_col',
            'materials': {S: {'color': '#ffffff', 'palette': True}},
            'lighting': LIGHT, 'verification': POLICY, 'nodes': col}
    (HERE / (NAME + '_col.asset.json')).write_text(json.dumps(colr, indent=1) + '\n')
    print('ladder strip top %.2f, beam top %.2f' % (slab_bot + 0.24, 4.52))


if __name__ == '__main__':
    main()
