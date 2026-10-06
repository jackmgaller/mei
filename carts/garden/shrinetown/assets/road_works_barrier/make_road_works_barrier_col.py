#!/usr/bin/env python3
"""Writes road_works_barrier_col.asset.json beside this script: the collision of the shrine's
`street_barrier` (../../../shrine/assets) as the shrine town places it, at the front road's west
end (place/canal.py, `road_works_0/1`).

    python3 carts/garden/shrinetown/assets/road_works_barrier/make_road_works_barrier_col.py

The shrine's own companion, street_barrier_col, is a 3 m wall (the shrine's road works close its
road there); the barrier is drawn to 1.26 m, so in the shrine town that wall was an invisible top
1.74 m over it (alpha review r09 #6). This one is the barrier's drawn box: 6 m along x, 1.26 m
high, 0.4 m deep. The 5.5 m hoarding behind it closes the level.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H, D = 3.0, 1.26, 0.2

v = [[-W, H, D], [W, H, D], [W, H, -D], [-W, H, -D], [W, 0.0, -D], [-W, 0.0, -D], [-W, 0.0, D], [W, 0.0, D]]
recipe = {
    'format': 'mei-asset', 'version': 1, 'name': 'road_works_barrier_col',
    'materials': {'solid': {'color': '#ffffff', 'palette': True}},
    'lighting': {'mode': 'vertical', 'ambient': 0.5},
    'verification': {'required': True, 'depth': True, 'perspective': True},
    'nodes': [{'id': 'wall', 'op': 'mesh', 'vertices': v,
               'faces': [[0, 1, 2, 3], [3, 2, 4, 5], [6, 7, 1, 0], [6, 0, 3, 5], [4, 2, 1, 7]],
               'face_materials': ['solid'] * 5}],
}
(HERE / 'road_works_barrier_col.asset.json').write_text(json.dumps(recipe, indent=1) + '\n')
print('wrote road_works_barrier_col')
