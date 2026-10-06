#!/usr/bin/env python3
"""Writes the frame's rock walls (DESIGN.md 12.9, "The level's frame"): edge_rock_KEY.asset.json,
one per ROCKS row, which place/art.py stands on the level's rims north of the town.

The frame's rule asks 13-72 m of the west, east and north edges north of the town (a glide from
the mountain's plateau, 62-70 m, reaches them all). The rims are terrain cliffs at the field's
edge, 8-14 m over the ground; raised to the rule as terrain they were drawn as ramps tens of
metres long by the far levels and the stand-ins (whose grid points on the edge take the rim's
top), so the height is these walls instead, standing on the rims.

A wall is the rim's width deep (2 m on the west and east, 4 m on the north, the rim's footprint),
ROCK (16) m along the edge, from its foot (the rim's top under it, less 1 m) to its top: its face
toward the level, its top and its two ends, in the shrine's rock (the terrain's rock texture,
../shrine/assets/art/terrain_rock.png, at the terrain's 4.8 m a repeat: no VRAM of its own), the
back and the bottom left open. From LOD_FAR a level in the rock's flat far colour. Collision:
"self" (its faces).

ROCKS is the table `tools/frame.py --build-dir B --rocks` prints from a built world: per 16 m of
rim, the foot and the top (the reach there by the rule, and 0.5 m). Origin: the middle of the
wall's footprint at its foot, inside the level's cell; the face is the asset's front (-Z), turned
to the level by the yaw (north 0, east 90, west 270).

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
W, D = 320.0, 384.0

# (edge, from, to along it, foot, top): tools/frame.py --rocks
ROCKS = [
    ('W', 128, 144, 9, 14.5),
    ('W', 144, 160, 9, 18.5),
    ('W', 160, 176, 9, 22.5),
    ('W', 176, 192, 9, 26),
    ('W', 192, 208, 9, 29.5),
    ('W', 208, 224, 9, 33.5),
    ('W', 224, 240, 10, 37),
    ('W', 240, 256, 11, 40),
    ('W', 256, 272, 18, 43.5),
    ('W', 272, 288, 20, 46.5),
    ('W', 288, 304, 23, 49),
    ('W', 304, 320, 26, 51),
    ('W', 320, 336, 29, 52.5),
    ('W', 336, 352, 31, 53.5),
    ('W', 352, 368, 33, 53.5),
    ('W', 368, 380, 35, 53.5),
    ('E', 154, 160, 9, 38),
    ('E', 160, 176, 8, 41.5),
    ('E', 176, 192, 8, 45),
    ('E', 192, 208, 8, 48.5),
    ('E', 208, 224, 7, 52),
    ('E', 224, 240, 7, 55),
    ('E', 240, 256, 27, 57.5),
    ('E', 256, 272, 27, 59.5),
    ('E', 272, 288, 32, 61),
    ('E', 288, 304, 39, 62),
    ('E', 304, 320, 47, 62),
    ('E', 320, 336, 54, 65),
    ('E', 336, 352, 58, 68.5),
    ('E', 352, 368, 66, 70.5),
    ('E', 368, 380, 70, 70.5),
    ('N', 0, 16, 27, 57.5),
    ('N', 16, 32, 22, 61.5),
    ('N', 32, 48, 8, 65.5),
    ('N', 48, 64, 8, 69),
    ('N', 64, 80, 65, 69.5),
    ('N', 80, 96, 68, 69.5),
    ('N', 96, 112, 66, 68.5),
    ('N', 112, 128, 67, 69.5),
    ('N', 128, 144, 69, 70),
    ('N', 144, 160, 68, 70),
    ('N', 160, 176, 67, 70),
    ('N', 176, 192, 67, 69),
    ('N', 192, 208, 67, 69),
    ('N', 208, 224, 67, 69.5),
    ('N', 224, 240, 68, 70.5),
    ('N', 240, 256, 68, 72),
    ('N', 256, 272, 67, 72),
    ('N', 272, 288, 67, 68.5),
    ('N', 288, 304, 68, 70.5),
    ('N', 304, 320, 69, 70.5),
]


def walls():
    """The rows that stand over their rim: the rim's top (the foot and 1 m) is under the top."""
    return [r for r in ROCKS if r[4] > r[3] + 1.0]


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
    v = [[-l2, 0, -d2], [l2, 0, -d2], [l2, height, -d2], [-l2, height, -d2],
         [-l2, 0, d2], [l2, 0, d2], [l2, height, d2], [-l2, height, d2]]
    # the face (-Z), the top, the two ends; wound to face out
    faces = [[0, 1, 2, 3][::-1], [3, 2, 6, 7][::-1], [4, 0, 3, 7][::-1], [1, 5, 6, 2][::-1]]
    body = {'id': 'wall', 'op': 'mesh', 'vertices': v, 'faces': faces,
            'face_materials': ['rock', 'rock', 'rock', 'rock']}
    far = dict(body, face_materials=['far'] * 4)
    pieces = (int(length / (3 * REPEAT)) + 2) * (int(height / (3 * REPEAT)) + 2)
    return {
        'format': 'mei-asset', 'version': 1, 'name': f'edge_rock_{key(row)}',
        'budget': {'triangles': 2 * pieces + 24},
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
