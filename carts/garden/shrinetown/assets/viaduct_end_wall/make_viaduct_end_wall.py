#!/usr/bin/env python3
"""Writes viaduct_end_wall.asset.json: the concrete wall that closes the viaduct's deck at its end,
the underpass's north end (place/station.py, `viaduct_end`), in place of the grey box's
gbc_viaduct_end.

A wall across the deck 13.2 m wide (the deck's section is 12 m over its fascias: 0.6 m past each
parapet) and 5.5 m over the deck, 0.6 m thick, with a coping. Its faces carry the viaduct's
concrete (viaduct_span_16/art/concrete.png, the sheet's `wall` cell at the spans' scale), so it
needs no VRAM of its own: the viaduct's pieces in the same cell use that sheet. 20 triangles.

Origin and facing: the middle of its foot on the deck; it spans local X, its faces toward -Z and
+Z. Collision: "self". It is the line's end, not the level's frame: the neighbours' backs 3.4 m
east of the deck are (DESIGN.md 12.9).

Run: python3 carts/garden/shrinetown/assets/viaduct_end_wall/make_viaduct_end_wall.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIDTH, HEIGHT, THICK = 13.2, 5.5, 0.6
COPING = 0.2


def recipe():
    return {
        'format': 'mei-asset', 'version': 1, 'name': 'viaduct_end_wall',
        'budget': {'triangles': 24},
        'sheets': {'concrete': {'image': '../viaduct_span_16/art/concrete.png'}},
        'lighting': {'mode': 'vertical', 'ambient': 0.5},
        'verification': {'required': True, 'depth': True, 'perspective': True},
        'materials': {
            'concrete': {'color': '#b4b0a6', 'texture': {'sheet': 'concrete', 'cell': 'wall',
                                                         'projection': 'box', 'scale': [4.0, 2.0]}},
            'coping': {'color': '#c8c4b8', 'palette': True},
        },
        'nodes': [
            {'id': 'wall', 'op': 'box', 'size': [WIDTH, HEIGHT - COPING, THICK], 'material': 'concrete',
             'open': ['bottom'], 'faces': {'top': 'coping'},
             'transform': {'translate': [0, (HEIGHT - COPING) / 2, 0]}},
            {'id': 'coping', 'op': 'box', 'size': [WIDTH + 0.1, COPING, THICK + 0.1], 'material': 'coping',
             'open': ['bottom'], 'transform': {'translate': [0, HEIGHT - COPING / 2, 0]}},
        ],
    }


if __name__ == '__main__':
    (HERE / 'viaduct_end_wall.asset.json').write_text(json.dumps(recipe(), indent=1) + '\n')
    print(f'viaduct_end_wall: {WIDTH} x {HEIGHT} x {THICK} m')
