#!/usr/bin/env python3
"""Writes tank_nook.asset.json beside itself: a corner of an aquarium after closing, lit only by
three coloured point lights (docs/ASSETKIT.md, "Point lights").

    python3 examples/assets/lab/tank_nook/make_tank_nook.py

A 3 x 3 m tiled floor with two walls, a jellyfish column (violet), a small coral tank (teal) and
a paper lantern on a stand (amber), with a bench between them. Each light shows one part of the
feature: the violet light has soft shadows (the bench and the column's plinth throw them), the
amber one hard shadows, the teal one none. The floor is textured (the light tints it), the walls
are palette-backed (the light tints the entry), and the column's glow, the coral tank's water and
the lantern's paper are emissive (the light leaves them alone). Needs nothing but Python.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

JELLY = (-0.75, 0.75)       # x, z of the jellyfish column
CORAL = (0.85, 0.9)         # the coral tank
LANTERN = (0.9, -0.85)      # the lantern's stand


def box(id, lo, hi, material, **extra):
    """A box from corner lo to corner hi."""
    node = {'id': id, 'op': 'box', 'size': [round(h - l, 4) for l, h in zip(lo, hi)], 'material': material,
            'transform': {'translate': [round((l + h) / 2, 4) for l, h in zip(lo, hi)]}}
    node.update(extra)
    return node


def cylinder(id, x, y0, y1, z, radius, material, segments=12, **extra):
    node = {'id': id, 'op': 'cylinder', 'radius': radius, 'height': round(y1 - y0, 4), 'segments': segments,
            'material': material, 'transform': {'translate': [x, round((y0 + y1) / 2, 4), z]}}
    node.update(extra)
    return node


def recipe():
    materials = {
        'floor': {'color': '#8c96a8', 'texture': {'pattern': 'tile', 'size': 16, 'colors': ['#9aa4b6', '#6c7486'],
                                                  'projection': 'planar', 'axis': 'y', 'scale': [0.5, 0.5]}},
        'slab': {'color': '#3a4258'},
        'wall': {'color': '#7a88a4', 'palette': True, 'tag': 'wall'},
        'cut': {'color': '#c8d0dc'},
        'plinth': {'color': '#4a5068'},
        'jelly_glow': {'color': '#c8a8ff', 'class': 'emissive'},
        'glass': {'color': '#5048a8', 'blend': 'half', 'double_sided': True},
        'jelly': {'color': '#b080e0', 'blend': 'add', 'smooth': True},
        'stand': {'color': '#2c3044'},
        'water': {'color': '#40d0c0', 'class': 'emissive'},
        'coral': {'color': '#e070a0'},
        'paper': {'color': '#ffd090', 'class': 'emissive'},
        'wood': {'color': '#9a7050'},
        'bench': {'color': '#b0b8c8'},
    }
    nodes = [
        # the floor stands 8 cm proud of the walls, as a model's base
        box('floor', [-1.58, -0.2, -1.58], [1.58, 0, 1.58], 'slab', open=['bottom'], faces={'top': 'floor'}),
        # the walls stand 2 cm into the floor, and each ends inside the other
        box('wall_back', [-1.4, -0.02, 1.35], [1.5, 1.6, 1.5], 'wall', open=['bottom'], faces={'top': 'cut'}),
        box('wall_left', [-1.5, -0.02, -1.5], [-1.35, 1.54, 1.46], 'wall', open=['bottom'], faces={'top': 'cut'}),
        # the jellyfish column: a plinth with a glowing top, a glass cylinder, two jellyfish
        {'id': 'column', 'op': 'group', 'children': [
            cylinder('plinth', JELLY[0], -0.02, 0.4, JELLY[1], 0.36, 'plinth', 12, faces={'top': 'jelly_glow'}),
            cylinder('glass', JELLY[0], 0.4, 1.4, JELLY[1], 0.3, 'glass', 12, caps=False),
            {'id': 'jelly_a', 'op': 'lathe', 'profile': [[0.1, 0], [0.08, 0.06], [0, 0.09]], 'segments': 8,
             'caps': False, 'material': 'jelly', 'transform': {'translate': [JELLY[0] - 0.08, 0.95, JELLY[1]]}},
            {'id': 'jelly_b', 'op': 'lathe', 'profile': [[0.07, 0], [0.055, 0.04], [0, 0.06]], 'segments': 8,
             'caps': False, 'material': 'jelly', 'transform': {'translate': [JELLY[0] + 0.1, 0.7, JELLY[1] - 0.05]}},
        ]},
        # the coral tank on its stand
        {'id': 'coral_tank', 'op': 'group', 'children': [
            box('stand', [CORAL[0] - 0.32, -0.02, CORAL[1] - 0.22], [CORAL[0] + 0.32, 0.6, CORAL[1] + 0.22], 'stand',
                open=['bottom']),
            box('water', [CORAL[0] - 0.3, 0.6, CORAL[1] - 0.2], [CORAL[0] + 0.3, 0.98, CORAL[1] + 0.2], 'water',
                open=['bottom']),
        ]},
        # the lantern on its stand
        {'id': 'lantern', 'op': 'group', 'children': [
            cylinder('pole', LANTERN[0], -0.02, 0.92, LANTERN[1], 0.025, 'wood', 6, caps=False),
            {'id': 'paper', 'op': 'lathe', 'profile': [[0.06, 0], [0.14, 0.08], [0.15, 0.2], [0.13, 0.3], [0.06, 0.36]],
             'segments': 10, 'material': 'paper', 'transform': {'translate': [LANTERN[0], 0.9, LANTERN[1]]}},
        ]},
        # the bench between them
        {'id': 'bench', 'op': 'group', 'children': [
            box('seat', [-0.7, 0.4, -0.35], [0.5, 0.46, -0.05], 'bench'),
            box('leg_l', [-0.62, -0.02, -0.32], [-0.56, 0.4, -0.08], 'stand', open=['bottom', 'top']),
            box('leg_r', [0.36, -0.02, -0.32], [0.42, 0.4, -0.08], 'stand', open=['bottom', 'top']),
        ]},
    ]
    lighting = {
        'ambient': 0.22, 'diffuse': 0.12,
        'lights': [
            {'id': 'jelly', 'at': [JELLY[0], 0.85, JELLY[1]], 'color': '#a070ff', 'intensity': 2.4, 'range': 2.6,
             'shadows': True, 'radius': 0.25},
            {'id': 'coral', 'at': [CORAL[0], 1.05, CORAL[1]], 'color': '#30e0c8', 'intensity': 1.8, 'range': 1.8},
            {'id': 'lantern', 'at': [LANTERN[0], 1.08, LANTERN[1]], 'color': '#ffa850', 'intensity': 1.6, 'range': 2.2,
             'shadows': True},
        ],
    }
    return {'format': 'mei-asset', 'version': 1, 'name': 'tank_nook', 'materials': materials, 'nodes': nodes,
            'lighting': lighting, 'budget': {'vertices': 1024, 'triangles': 1000},
            # drawn with the depth buffer: the walls and props stand into the floor
            'verification': {'required': True, 'depth': True}}


def main():
    (HERE / 'tank_nook.asset.json').write_text(json.dumps(recipe(), indent=1) + '\n')
    print('wrote', (HERE / 'tank_nook.asset.json').name)


if __name__ == '__main__':
    main()
