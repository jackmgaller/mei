#!/usr/bin/env python3
"""Level 1 of After Hours: assembles the level's World Kit world from its rooms.

    python3 carts/afterhours/levels/level1/make_level1.py

Writes level1.world.json beside itself. The rooms are written by their own scripts first (each
room's folder, carts/afterhours/rooms/NAME/; the aquarium's play file by aquarium/make_aquarium_play.py
here); this script only moves them into place:

- one world for the level, so one pack is open for all of it (the reader keeps one);
- each room in its own 32 m cell, side by side along x in the order they are played, at its own
  floor height: the section through the complex unfolded, from the platform deep underground up
  to the aquarium on the roof (ROUTE.md);
- one region per room, so each room's textures and palettes are its own;
- the room entities chained by `next`, the first marked `first`.

A room's files are in its own frame (origin in the middle of its floor); every position here is
that plus the room's place. Entity and placement ids are already world-wide (each room's prefix).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CART = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
from greybox import write_json, r  # noqa: E402

CELL = 32
CAM_DIST, CAM_PITCH = 28.166, 60      # the game's camera (dr_view.akr), for the World Checker's views

# Each room's name, as the transition, the stage select and the stage's end show it.
# (A World Kit name: lower case and underscores; shown in capitals with spaces, "THE LAST TRAIN".)
NAMES = {'arrival': 'the_last_train', 'gates': 'the_ticket_gates', 'passage': 'the_passage',
         'lobby': 'the_lobby', 'aquarium': 'the_aquarium'}

# The route, in order: (room, floor height, its play file, its placements, its asset folders).
# The asset folders are the dressed rooms' (each room's NOTES.md); the greybox recipes stay in
# each room's greybox/ folder, unused, with the greybox's placements beside them.
# Floor heights are the section's: three levels underground, the street, the roof of a tower.
ROOMS = [
    ('arrival', -16.0, 'rooms/arrival/arrival.play.json', 'rooms/arrival/arrival.placements.json', ['rooms/arrival/dressed']),
    ('gates', -11.0, 'rooms/gates/gates.play.json', 'rooms/gates/gates.placements.json', ['rooms/gates/dressed']),
    ('passage', -6.0, 'rooms/passage/passage.play.json', 'rooms/passage/passage.placements.json', ['rooms/passage']),
    ('lobby', 0.0, 'rooms/lobby/lobby.play.json', 'rooms/lobby/lobby.placements.json', ['rooms/lobby']),
    ('aquarium', 40.0, 'levels/level1/aquarium/aquarium.play.json',
     ['rooms/aquarium/aquarium.placements.json', 'levels/level1/aquarium/aquarium.placements.json'],
     ['rooms/aquarium', 'levels/level1/aquarium/collision']),
]


def place(k, y):
    """Where room k's origin goes: the middle of its cell, at its floor height."""
    return (CELL * k + CELL / 2, y, CELL / 2)


def moved(pos, o):
    return [r(pos[0] + o[0]), r(pos[1] + o[1]), r(pos[2] + o[2])]


def main():
    cells, regions, paths, vantage, asset_dirs = [], {}, {}, [], []
    room_ids = []
    for k, (name, y, play_path, placements_path, dirs) in enumerate(ROOMS):
        o = place(k, y)
        play = json.loads((CART / play_path).read_text())
        if isinstance(placements_path, list):        # the builder's placements when they exist, else ours
            placements_path = next(p for p in placements_path if (CART / p).exists())
        placements = json.loads((CART / placements_path).read_text())['placements']
        ents = []
        for e in play['entities']:
            e = json.loads(json.dumps(e))
            e['position'] = moved(e['position'], o)
            ents.append(e)
        room = next(e for e in ents if e['type'] == 'room')
        room['params'] = dict({'name': NAMES[name]}, **room['params'])
        room_ids.append(room['id'])
        for pid, p in play.get('paths', {}).items():
            paths[pid] = dict(p, points=[moved(q, o) for q in p['points']])
        pls = []
        for p in placements:
            p = json.loads(json.dumps(p))
            p['position'] = moved(p['position'], o)
            pls.append(p)
        regions[name] = {}
        cells.append({'id': name, 'at': [k, 0], 'region': name, 'placements': pls, 'entities': ents})
        for d in dirs:
            if (CART / d).exists():
                asset_dirs.append(str(Path('../..') / d))
        # the game's camera over the room's middle (and its ends, for a room wider than a screen)
        sx = room['params']['size'][0]
        xs = [0.0] if sx <= 13.5 else [-(sx / 2 - 6.6), 0.0, sx / 2 - 6.6]
        cz = room['position'][2]
        for i, dx in enumerate(xs):
            vantage.append({'name': f'game_{name}_{i}', 'yaw': 0, 'pitch': -CAM_PITCH,
                            'position': [r(room['position'][0] + dx), r(y + 0.6 + CAM_DIST * math.sin(math.radians(CAM_PITCH))),
                                         r(cz - CAM_DIST * math.cos(math.radians(CAM_PITCH)))]})
    # the route: each room leads to the next
    for k, c in enumerate(cells):
        room = next(e for e in c['entities'] if e['type'] == 'room')
        if k == 0:
            room['params']['first'] = True
        if k + 1 < len(cells):
            room['params']['next'] = room_ids[k + 1]
    world = {
        'format': 'mei-world', 'version': 1, 'name': 'level1',
        'game': '../../afterhours.game.mochi', 'assets': asset_dirs[0], 'asset_dirs': asset_dirs[1:],
        'grid': {'cell_size': CELL},
        'collision': {'surfaces': {'default': 0}},
        'regions': regions,
        'paths': paths,
        'runtime': {'depth': True, 'perspective': True},
        # stand-ins of each room, made by the kit from the room itself: for the pull-back between
        # rooms (Gate 2), which shows the neighbours far and small
        'standins': {'distance': 64, 'triangles': 700, 'cells': {'aquarium': {'triangles': 800}}},
        # the room budget is DESIGN.md's 2,500 triangles; stand-ins as the caps above
        'verification': {'vantage_points': vantage,
                         'thresholds': {'cell_triangles': 2500, 'standin_triangles': 800}},
        'cells': cells,
    }
    write_json(HERE / 'level1.world.json', world)


if __name__ == '__main__':
    main()
