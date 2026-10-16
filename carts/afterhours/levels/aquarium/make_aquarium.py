#!/usr/bin/env python3
"""The aquarium stage of After Hours: assembles the stage's World Kit world from its rooms.

    python3 carts/afterhours/levels/aquarium/make_aquarium.py

Writes aquarium.world.json beside itself (levels/assemble.py, B's, says how). The aquarium is one
place: its public galleries on the ground floor, the life-support plant under them, the kitchen
and the tank tops over them (ROUTE.md). The rooms are written by their own scripts first
(rooms/aq_*/make_aq_*.py; the ocean gallery's play file by ocean/make_ocean_play.py here) and
dressed by their builders. `next` only orders the rooms, left to right in the section; the
entrance hall is `first`.

Texture slots: the transition draws two rooms a door joins at once, textured, so no two such
rooms may share slots. The stage's doors make a cycle of seven rooms, so it takes three sets
(SLOTS); slot 7 and 4-bit palettes 250-251 stay the front end's.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import assemble  # noqa: E402
from greybox import write_json  # noqa: E402

STOREYS = {'aq_hall': 1, 'aq_great': 1, 'aq_jelly': 1, 'aquarium': 1, 'aq_quar': 1, 'aq_plant': -1,
           'aq_kitchen': 2, 'aq_tops': 2}

SET_A, SET_B, SET_C = '13-9,16-19', '8,6-3,20-24', '2-0,25-31'
SLOTS = {'aq_hall': SET_A, 'aq_jelly': SET_A, 'aq_quar': SET_A, 'aq_kitchen': SET_A,
         'aq_great': SET_B, 'aquarium': SET_B, 'aq_plant': SET_B,
         'aq_tops': SET_C}


def room(name, y, dirs=None):
    """A new room of this stage: its play file, its placements (the builder's when they exist),
    its asset folders (the room's folder and every folder in it: greybox/ and the builder's)."""
    folder = f'rooms/{name}'
    return (name, y, f'{folder}/{name}.play.json', f'{folder}/{name}.placements.json', dirs or [folder])


# The rooms in the section's order, at their floors (4 m a storey, 1F at 0).
ROOMS = [
    room('aq_hall', 0.0),
    room('aq_great', 0.0),
    room('aq_jelly', 0.0),
    ('aquarium', 0.0, 'levels/aquarium/ocean/ocean.play.json',
     ['rooms/aquarium/aquarium.placements.json', 'levels/level1/aquarium/aquarium.placements.json'],
     ['rooms/aquarium', 'levels/level1/aquarium/collision']),
    room('aq_quar', 0.0),
    room('aq_plant', -4.0),
    room('aq_kitchen', 4.0),
    room('aq_tops', 4.0),
]

if __name__ == '__main__':
    out = HERE / 'aquarium.world.json'
    assemble.build(out, 'aquarium', ROOMS, storeys=STOREYS, standin_caps={'aquarium': 800})
    w = json.loads(out.read_text())
    # every folder in a new room's folder too (greybox/ and the builder's): assemble.py keeps
    # only folders that exist, so the /* entries are added here
    for name, *_ in ROOMS:
        if name.startswith('aq_'):
            w['asset_dirs'].append(f'../../rooms/{name}/*')
    for name, slots in SLOTS.items():
        w['regions'][name] = {'textures': {'slots': slots}}
    write_json(out, w, quiet=True)
