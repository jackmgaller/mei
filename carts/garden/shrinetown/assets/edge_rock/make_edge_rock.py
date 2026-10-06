#!/usr/bin/env python3
"""Writes the frame's rock walls (DESIGN.md 12.9, "The level's frame"): edge_rock_KEY.asset.json,
one per ROCKS row, which place/art.py stands on the level's rims north of the town.

The frame's rule asks 13-72 m of the west, east and north edges north of the town (a glide from
the mountain's plateau, 62-70 m, reaches them all). The rims are terrain cliffs at the field's
edge, 8-14 m over the ground; raised to the rule as terrain they were drawn as ramps tens of
metres long by the far levels and the stand-ins (whose grid points on the edge take the rim's
top), so the height is these walls instead, standing on the rims.

A wall is the rim's width deep (2 m on the west and east, 4 m on the north, the rim's footprint),
ROCK (16) m along the edge, on every 16 m of those rims. Its face toward the level rises from its
foot (the rim's lowest corner under it, less 1 m) to its top, and goes on down, in the rock's flat
far colour, to SKIRT_TO under the mountain, so that a body that falls through the terrain's steep
faces (review 13 #3) meets it at the edge. Its cap rises from the top to the back, LIP times the
depth (56 degrees, steeper than a floor): nothing stands on a wall, and a body that clears the
face's top meets the cap and slides back. The ends close it from the foot to the cap; the back
and the bottom are open. The rock is the terrain's (../shrine/assets/art/terrain_rock.png at the
terrain's 4.8 m a repeat: no VRAM of its own); from LOD_FAR the rock's flat far colour.
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
    """Every row: a wall on every 16 m of rim, so that no rim's top is a floor by the edge."""
    return list(ROCKS)


def key(row):
    edge, a, b, _, _ = row
    return f'{edge.lower()}{int(a)}'


def place(row):
    """(x, y, z, yaw) of a wall's origin: the middle of its footprint, at its foot."""
    edge, a, b, foot, _ = row
    m, d = (a + b) / 2, DEPTH[edge] / 2
    x, z = {'N': (m, D - d), 'E': (W - d, m), 'W': (d, m)}[edge]
    return x, foot, z, YAW[edge]


def recipe(row):
    edge, a, b, foot, top = row
    length, depth, height = b - a, DEPTH[edge], top - foot
    l2, d2 = length / 2, depth / 2
    lip = LIP * depth
    lo = SKIRT_TO - foot
    # 0-3 the face's foot and top, 4-5 the cap's back edge (LIP higher), 6-7 the skirt's foot;
    # y from the wall's foot
    v = [[-l2, 0, -d2], [l2, 0, -d2], [l2, height, -d2], [-l2, height, -d2],
         [-l2, height + lip, d2], [l2, height + lip, d2], [-l2, lo, -d2], [l2, lo, -d2]]
    v += [[-l2, 0, d2], [l2, 0, d2]]                                      # 8-9 the ends' back foot
    faces = [[0, 1, 2, 3][::-1],              # the face (-Z)
             [3, 2, 5, 4][::-1],              # the cap, rising to the back: steeper than a floor
             [6, 7, 1, 0][::-1],              # the skirt under the rim, in the far colour
             [8, 0, 3, 4][::-1],              # the -X end, from the foot to the cap
             [1, 9, 5, 2][::-1]]              # the +X end
    mats = ['rock', 'rock', 'far', 'rock', 'rock']
    body = {'id': 'wall', 'op': 'mesh', 'vertices': v, 'faces': faces, 'face_materials': mats}
    far = dict(body, face_materials=['far'] * len(faces))
    pieces = (int(length / (3 * REPEAT)) + 2) * (int((height + lip) / (3 * REPEAT)) + 2)
    return {
        'format': 'mei-asset', 'version': 1, 'name': f'edge_rock_{key(row)}',
        'budget': {'triangles': 4 * pieces + 40},
        'lighting': {'mode': 'vertical', 'ambient': 0.5},
        'verification': {'required': True, 'depth': True, 'perspective': True},
        'materials': {
            'rock': {'color': FAR_COLOUR, 'tag': 'wall',
                     'texture': {'image': ROCK_IMAGE, 'projection': 'box', 'scale': [REPEAT, REPEAT]}},
            'far': {'color': FAR_COLOUR, 'tag': 'wall'},
        },
        'nodes': [body],
        'lod': {'levels': [{'distance': LOD_FAR, 'nodes': [far]}]},
    }


if __name__ == '__main__':
    for old in HERE.glob('edge_rock_*.asset.json'):
        old.unlink()
    for row in walls():
        r = recipe(row)
        (HERE / f'{r["name"]}.asset.json').write_text(json.dumps(r, indent=1) + '\n')
    print(f'{len(walls())} rock walls, {min(t - f for _, _, _, f, t in walls()):g}-'
          f'{max(t - f for _, _, _, f, t in walls()):g} m tall')
