#!/usr/bin/env python3
"""Writes the frame's rock walls (DESIGN.md 12.9, "The level's frame"): edge_rock_KEY.asset.json,
one per ROCKS row, which place/art.py stands on the level's rims north of the town.

The frame's rule asks 13-72 m of the west, east and north edges north of the town (a glide from
the mountain's plateau, 62-70 m, reaches them all). The rims are terrain cliffs at the field's
edge, 8-14 m over the ground; raised to the rule as terrain they were drawn as ramps tens of
metres long by the far levels and the stand-ins (whose grid points on the edge take the rim's
top), so the height is these walls instead, standing on the rims.

A wall is the rim's width deep (2 m on the west and east, 4 m on the north, the rim's footprint),
ROCK (16) m along the edge, on every 16 m of those rims; the steps of one cell's edge are one wall
(one placement). Its face toward the level rises from its
foot (the rim's lowest corner under it, less 1 m) to its top, and goes on down, in the rock's flat
far colour, to SKIRT_TO under the mountain, so that a body that falls through the terrain's steep
faces (review 13 #3) meets it at the edge. Its cap rises from the top to the back, LIP times the
depth (56 degrees, steeper than a floor): nothing stands on a wall, and a body that clears the
face's top meets the cap and slides back. The ends close it from the foot to the cap; the back
and the bottom are open. The rock is the terrain's (../shrine/assets/art/terrain_rock.png at the
terrain's 4.8 m a repeat: no VRAM of its own); from LOD_FAR the rock's flat far colour; place/art.py
culls them from 120 m, so the stand-ins leave them out.
Collision: "self" (its faces).

ROCKS is the table `tools/frame.py --build-dir B --rocks` prints from a built world: per 16 m of
rim, the foot and the top (the reach there by the rule and 0.5 m, and at least 1 m over the rim's
highest corner). Origin: the middle of the wall's footprint at its foot, inside the level's cell;
the face is the asset's front (-Z), turned to the level by the yaw (north 0, east 90, west 270).

Run: python3 carts/garden/shrinetown/assets/edge_rock/make_edge_rock.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROCK_IMAGE = '../../../shrine/assets/art/terrain_rock.png'
REPEAT = 4.8
LOD_FAR = 60
FAR_COLOUR = '#686157'
DEPTH = {'W': 2.0, 'E': 2.0, 'N': 4.0}
YAW = {'N': 0.0, 'E': 90.0, 'W': 270.0}
LIP = 1.5                 # the cap rises this many times the wall's depth to its back: 56 degrees
SKIRT_TO = -200.0         # the face goes on down to here, inside the mountain, in the far colour: a
                          # body that falls through the terrain (DESIGN.md 12.9) meets it at the edge
W, D = 320.0, 384.0
CELL = 64                 # a wall per edge of a cell

# (edge, from, to along it, foot, top): tools/frame.py --rocks
ROCKS = [
    ('W', 128, 144, 9, 25.5),
    ('W', 144, 160, 9, 28.5),
    ('W', 160, 176, 9, 31.5),
    ('W', 176, 192, 9, 34.5),
    ('W', 192, 208, 9, 37.5),
    ('W', 208, 224, 9, 40.5),
    ('W', 224, 240, 10, 43.5),
    ('W', 240, 256, 11, 46),
    ('W', 256, 272, 17, 48.5),
    ('W', 272, 288, 20, 51),
    ('W', 288, 304, 23, 53),
    ('W', 304, 320, 26, 55),
    ('W', 320, 336, 29, 56),
    ('W', 336, 352, 31, 56.5),
    ('W', 352, 368, 33, 56.5),
    ('W', 368, 380, 35, 56.5),
    ('E', 154, 160, 9, 45.5),
    ('E', 160, 176, 8, 48.5),
    ('E', 176, 192, 8, 51.5),
    ('E', 192, 208, 8, 54),
    ('E', 208, 224, 7, 57),
    ('E', 224, 240, 7, 59),
    ('E', 240, 256, 27, 61.5),
    ('E', 256, 272, 27, 63),
    ('E', 272, 288, 31, 64.5),
    ('E', 288, 304, 38, 65),
    ('E', 304, 320, 45, 65),
    ('E', 320, 336, 53, 65.5),
    ('E', 336, 352, 57, 68.5),
    ('E', 352, 368, 65, 72),
    ('E', 368, 380, 69, 72.5),
    ('N', 0, 16, 26, 60),
    ('N', 16, 32, 22, 63),
    ('N', 32, 48, 8, 66),
    ('N', 48, 64, 8, 69),
    ('N', 64, 80, 56, 72),
    ('N', 80, 96, 67, 71.5),
    ('N', 96, 112, 66, 70),
    ('N', 112, 128, 67, 71.5),
    ('N', 128, 144, 68, 73),
    ('N', 144, 160, 68, 73),
    ('N', 160, 176, 66, 71),
    ('N', 176, 192, 66, 71),
    ('N', 192, 208, 67, 71.5),
    ('N', 208, 224, 67, 71.5),
    ('N', 224, 240, 68, 71.5),
    ('N', 240, 256, 68, 72.5),
    ('N', 256, 272, 67, 72),
    ('N', 272, 288, 67, 70.5),
    ('N', 288, 304, 68, 72.5),
    ('N', 304, 320, 69, 72.5),
]


def walls():
    """The walls: the rows grouped by the cell they stand in (edge, 64 m of it), one placement each
    (a placement costs the draw about as much as its triangles: 51 walls were 30,000-66,000 cycles
    of draw CPU in the shrine's views, DESIGN.md 12.9)."""
    groups = {}
    for r in ROCKS:
        groups.setdefault((r[0], int(r[1] // CELL)), []).append(r)
    return list(groups.values())


def key(group):
    edge, a = group[0][0], group[0][1]
    return f'{edge.lower()}{int(a)}'


def span(group):
    return group[0][1], group[-1][2], min(r[3] for r in group)


def place(group):
    """(x, y, z, yaw) of a wall's origin: the middle of its footprint, at its lowest foot."""
    edge = group[0][0]
    a, b, foot = span(group)
    m, d = (a + b) / 2, DEPTH[edge] / 2
    x, z = {'N': (m, D - d), 'E': (W - d, m), 'W': (d, m)}[edge]
    return x, foot, z, YAW[edge]


def segment(row, dx, dy, depth, lo_top, hi_top):
    """One row's face, cap and skirt, its middle dx along the wall from the origin, its foot dy over
    the wall's; and its ends: whole at the wall's ends (lo_top, hi_top None: the -X and +X
    neighbours' tops), and where a neighbour is lower only above that neighbour's face (the faces
    of two steps may not overlap)."""
    edge, a, b, foot, top = row
    length, height = b - a, top - foot
    l2, d2 = length / 2, depth / 2
    lip = LIP * depth
    lo = SKIRT_TO - foot
    # 0-3 the face's foot and top, 4-5 the cap's back edge (LIP higher), 6-7 the skirt's foot
    v = [[-l2, 0, -d2], [l2, 0, -d2], [l2, height, -d2], [-l2, height, -d2],
         [-l2, height + lip, d2], [l2, height + lip, d2], [-l2, lo, -d2], [l2, lo, -d2]]
    faces = [[0, 1, 2, 3][::-1],              # the face (-Z)
             [3, 2, 5, 4][::-1],              # the cap, rising to the back: steeper than a floor
             [6, 7, 1, 0][::-1]]              # the skirt under the rim, in the far colour
    mats = ['rock', 'rock', 'far']
    for x, other, front_top, back_top, flip in ((-l2, lo_top, 3, 4, False), (l2, hi_top, 2, 5, True)):
        if other is not None and other >= top:
            continue
        y0 = 0.0 if other is None else other - foot
        n = len(v)
        v += [[x, y0, -d2], [x, y0 + (0 if other is None else lip), d2]]
        quad = [n + 1, n, front_top, back_top]             # back foot, front foot, front top, back top
        faces.append(quad[::-1] if not flip else [n, n + 1, back_top, front_top][::-1])
        mats.append('rock')
    v = [[round(x + dx, 4), round(y + dy, 4), z] for x, y, z in v]
    return v, faces, mats


def recipe(group):
    edge = group[0][0]
    a, b, foot = span(group)
    depth = DEPTH[edge]
    # the asset's +X runs along the edge: north +x (yaw 0), east -z (yaw 90), west +z (yaw 270)
    sign = -1 if edge == 'E' else 1
    nodes, far, tris = [], [], 0
    dxs = [sign * ((r[1] + r[2]) / 2 - (a + b) / 2) for r in group]
    for k, row in enumerate(group):
        dx = dxs[k]
        lower = [group[j][4] for j in range(len(group)) if abs(dxs[j] - (dx - (row[2] - row[1] + group[j][2] - group[j][1]) / 2)) < 1e-6]
        higher = [group[j][4] for j in range(len(group)) if abs(dxs[j] - (dx + (row[2] - row[1] + group[j][2] - group[j][1]) / 2)) < 1e-6]
        v, faces, mats = segment(row, dx, row[3] - foot, depth, lower[0] if lower else None,
                                 higher[0] if higher else None)
        nodes.append({'id': f'wall{k}', 'op': 'mesh', 'vertices': v, 'faces': faces, 'face_materials': mats})
        far.append({'id': f'wall{k}', 'op': 'mesh', 'vertices': v, 'faces': faces,
                    'face_materials': ['far'] * len(faces)})
        height = row[4] - row[3] + LIP * depth
        tris += 4 * (int((row[2] - row[1]) / (3 * REPEAT)) + 2) * (int(height / (3 * REPEAT)) + 2) + 40
    return {
        'format': 'mei-asset', 'version': 1, 'name': f'edge_rock_{key(group)}',
        'budget': {'triangles': tris},
        'lighting': {'mode': 'vertical', 'ambient': 0.5},
        'verification': {'required': True, 'depth': True, 'perspective': True},
        'materials': {
            'rock': {'color': FAR_COLOUR, 'tag': 'wall',
                     'texture': {'image': ROCK_IMAGE, 'projection': 'box', 'scale': [REPEAT, REPEAT]}},
            'far': {'color': FAR_COLOUR, 'tag': 'wall'},
        },
        'nodes': nodes,
        'lod': {'levels': [{'distance': LOD_FAR, 'nodes': far}]},
    }


if __name__ == '__main__':
    for old in HERE.glob('edge_rock_*.asset.json'):
        old.unlink()
    for group in walls():
        r = recipe(group)
        (HERE / f'{r["name"]}.asset.json').write_text(json.dumps(r, indent=1) + '\n')
    print(f'{len(walls())} rock walls of {len(ROCKS)} 16 m steps, {min(t - f for _, _, _, f, t in ROCKS):g}-'
          f'{max(t - f for _, _, _, f, t in ROCKS):g} m tall')
