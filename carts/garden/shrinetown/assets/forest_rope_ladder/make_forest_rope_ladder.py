"""Writes shortcut A's rope ladder (shrine town spec 3.12 and 4.5) beside this script
(python3 make_forest_rope_ladder.py; the textures are art/draw_ladder.py's):

- forest_rope_ladder: down (layer ladder_a), 20 m of hemp rope and wooden rungs hanging straight
  from the cliff ledge under the stage to the slope below; a pole when down;
- forest_rope_ladder_rolled: up, rolled into a bundle on the ledge's lip, a metre of it hanging
  over the edge so it reads from below as a ladder waiting to be kicked down;
- their collision companions: the anchor stakes, and the bundle.

Both share one origin and one yaw: the ladder's foot, its centreline at x = 0 in the plane z = 0;
the ledge's top is at y = 20 and its lip (the cliff face) just behind the ladder at z = +0.15, so
the ledge runs to +Z and the ladder faces -Z, out over the basin. Two stakes at z = 0.95 on the
ledge hold the ropes. The ladder hangs plumb (a pole is vertical), so the rock behind it must be
plumb or overhanging over those 20 m.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}

TOP = 20.0          # the ledge
HALF = 0.25         # the rung plane's half width (one 0.5 m repeat across)
ROPE_X = 0.203      # the side ropes' centres (texel columns 1 and 14 of the tile)
ROPE = 0.05         # rope thickness
STAKE_Z = 0.95
ROLL_R, ROLL_Z = 0.22, 0.36

MATS = {
    'rungs': {'color': '#8a6446', 'double_sided': True,
              'texture': {'image': 'art/ladder.png', 'projection': 'planar', 'axis': 'z',
                          'scale': [0.5, 0.5], 'offset': [0.5, 0.0]}},
    'rope': {'color': '#c8b478', 'palette': True},
    'stake': {'color': '#5a3e2c', 'palette': True},
    'bar': {'color': '#8a6446', 'palette': True},
    'roll': {'color': '#9a8458', 'palette': True},
    'roll_end': {'color': '#c8b478', 'texture': {'image': 'art/roll_end.png', 'projection': 'disc',
                                                 'axis': 'y'}},
}


def box(ident, size, at, mat, open_sides=None, rotate=None):
    n = {'id': ident, 'op': 'box', 'size': size, 'material': mat,
         'transform': {'translate': at}}
    if open_sides:
        n['open'] = open_sides
    if rotate:
        n['transform']['rotate'] = rotate
    return n


def plane(ident, y0, y1):
    """The rungs: one upright quad in z = 0, seen from both sides."""
    return {'id': ident, 'op': 'mesh',
            'vertices': [[-HALF, y1, 0], [HALF, y1, 0], [HALF, y0, 0], [-HALF, y0, 0]],
            'faces': [[0, 1, 2, 3]], 'face_materials': ['rungs']}


def ropes(y0, y1):
    h = y1 - y0
    # turned 45 degrees: no side parallel to the rung plane or the lip bar
    return [box(f'rope_{s}', [ROPE, h, ROPE], [sx * ROPE_X, y0 + h / 2, 0], 'rope', ['top', 'bottom'],
                rotate=[0, 45, 0])
            for s, sx in (('west', -1), ('east', 1))]


def anchors(from_z):
    """The two stakes on the ledge and the ropes from them to the lip (or to the bundle)."""
    out = []
    for s, sx in (('west', -1), ('east', 1)):
        out.append(box(f'stake_{s}', [0.1, 0.6, 0.1], [sx * 0.22, TOP + 0.2, STAKE_Z], 'stake', ['bottom']))
        length = STAKE_Z - from_z
        out.append(box(f'tie_{s}', [ROPE, ROPE, length], [sx * ROPE_X, TOP + 0.04, from_z + length / 2],
                       'rope', ['back', 'front'], rotate=[0, 0, 45]))
    return out


def recipe(name, budget, mats, nodes, levels, cull):
    r = {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': {'triangles': budget},
         'materials': mats, 'lighting': LIGHT, 'verification': POLICY, 'nodes': nodes,
         'lod': {'levels': [{'distance': d, 'nodes': ns} for d, ns in levels], 'cull': cull}}
    return r


def col(name, boxes):
    return {'format': 'mei-asset', 'version': 1, 'name': name,
            'materials': {'solid': {'color': '#ffffff', 'palette': True}},
            'lighting': LIGHT, 'verification': POLICY,
            'nodes': [box(i, s, a, 'solid', ['bottom']) for i, s, a in boxes]}


def down():
    mats = {k: MATS[k] for k in ('rungs', 'rope', 'stake', 'bar')}
    nodes = [plane('rungs', 0.05, TOP)]
    nodes += ropes(0.0, TOP + 0.04)
    nodes.append(box('lip_bar', [0.56, 0.07, 0.07], [0, TOP - 0.12, -0.04], 'bar'))
    nodes += anchors(0.0)
    far = [plane('rungs', 0.05, TOP)]
    return recipe('forest_rope_ladder', 80, mats, nodes, [(30, far)], 160)


def rolled():
    mats = {k: MATS[k] for k in ('rungs', 'rope', 'stake', 'roll', 'roll_end')}
    nodes = [
        # the roll lies across the lip, its axis along x
        {'id': 'roll', 'op': 'cylinder', 'radius': ROLL_R, 'height': 0.6, 'segments': 8,
         'material': 'roll', 'faces': {'top': 'roll_end', 'bottom': 'roll_end'},
         'transform': {'rotate': [0, 0, 90], 'translate': [0, TOP + ROLL_R - 0.02, ROLL_Z]}},
        # the last metre hangs over the edge, from under the roll down the cliff
        plane('rungs', TOP - 1.1, TOP + 0.05),
    ]
    nodes += anchors(ROLL_Z + ROLL_R - 0.05)
    far = [{'id': 'roll', 'op': 'cylinder', 'radius': ROLL_R, 'height': 0.6, 'segments': 5,
            'material': 'roll', 'transform': {'rotate': [0, 0, 90], 'translate': [0, TOP + ROLL_R - 0.02, ROLL_Z]}}]
    return recipe('forest_rope_ladder_rolled', 80, mats, nodes, [(30, far)], 90)


def main():
    stakes = ('stakes', [0.64, 0.5, 0.24], [0, TOP + 0.15, STAKE_Z])
    out = {
        'forest_rope_ladder': down(),
        'forest_rope_ladder_rolled': rolled(),
        'forest_rope_ladder_col': col('forest_rope_ladder_col', [stakes]),
        'forest_rope_ladder_rolled_col': col('forest_rope_ladder_rolled_col', [
            stakes, ('roll', [0.64, 0.46, 0.46], [0, TOP + 0.13, ROLL_Z])]),
    }
    for name, r in out.items():
        (HERE / f'{name}.asset.json').write_text(json.dumps(r, indent=1) + '\n')
        print(name)


if __name__ == '__main__':
    main()
