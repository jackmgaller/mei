#!/usr/bin/env python3
"""Writes town_wall_lamp.asset.json beside this script: the back alleys' lamp, a bare bulb under a
tin shade on a bent arm, screwed to a house's side wall (shrine town, alpha review r15 #5: the
alleys had no light at night).

    python3 carts/garden/shrinetown/assets/town_wall_lamp/make_town_wall_lamp.py   (standard library)

Origin on the wall at the alley's ground, the lamp's plate 2.4 m up it; the wall is the plane
z = 0 and the lamp reaches out toward -Z, as every town asset's front does. The bulb and the
shade's underside are emissive (`light`), so the night palette keeps them lit. No collision
(placed with collision none): it is 2.4 m up, over the body's head.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
Y = 2.4                       # the plate's middle


def box(nid, size, at, mat, open_=('back',), faces=None):
    n = {'id': nid, 'op': 'box', 'size': list(size), 'material': mat,
         'transform': {'translate': [round(c, 4) for c in at]}}
    if open_:
        n['open'] = list(open_)
    if faces:
        n['faces'] = faces
    return n


nodes = [
    box('plate', (0.12, 0.2, 0.04), (0.0, Y, -0.02), 'steel'),
    box('arm', (0.04, 0.04, 0.36), (0.0, Y + 0.06, -0.2), 'steel', open_=('back', 'front')),
    box('shade', (0.3, 0.1, 0.3), (0.0, Y + 0.04, -0.46), 'shade', open_=None, faces={'bottom': 'glow'}),
    box('bulb', (0.1, 0.1, 0.1), (0.0, Y - 0.06, -0.46), 'glow', open_=('top',)),
]
recipe = {
    'format': 'mei-asset', 'version': 1, 'name': 'town_wall_lamp',
    'budget': {'triangles': 40},
    'materials': {
        'steel': {'color': '#4e5258', 'palette': True},
        'shade': {'color': '#2e5b47', 'palette': True},
        'glow': {'color': '#fff1c4', 'class': 'emissive', 'tag': 'light'},
    },
    'lighting': {'mode': 'vertical', 'ambient': 0.5},
    'verification': {'required': True, 'depth': True, 'perspective': True},
    'nodes': nodes,
    'lod': {'levels': [{'distance': 20, 'nodes': [box('shade', (0.3, 0.12, 0.3), (0.0, Y + 0.02, -0.46), 'shade',
                                                      open_=None, faces={'bottom': 'glow'})]}],
            'cull': 45},
}
(HERE / 'town_wall_lamp.asset.json').write_text(json.dumps(recipe, indent=1) + '\n')
print('wrote town_wall_lamp')
