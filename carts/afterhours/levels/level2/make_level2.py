#!/usr/bin/env python3
"""Stage 2 of After Hours (keycards and backtracking): assembles the stage's World Kit world from
its rooms.

    python3 carts/afterhours/levels/level2/make_level2.py

Writes level2.world.json beside itself. The rooms are written by their own scripts first
(carts/afterhours/rooms/NAME/make_NAME.py); this script only moves them into place, as level 1's
does (levels/level1/make_level1.py):

- one world for the stage, each room in its own 32 m cell side by side along x, at its own floor
  height: a section through the department store, from the cinema on the eighth floor down to
  the food hall in the basement (ROUTE.md);
- one region per room;
- the rooms joined by their doors (each room's play file names the doors on the other side);
  the room entities chained by `next` only for their order, left to right in the section, the
  first (the cinema) marked `first`.

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

# The rooms in the section's order, left to right: (room, floor height, its play file, its
# placements, its asset folders). The cinema on the eighth floor of the store, the projection
# booth above the back of it, the staff corridor behind both, the shop floor a floor down, the
# food hall in the basement. The rooms name their own titles (s2room.py's `title`). The asset
# folders are the dressed rooms' (each room's NOTES.md); the greybox recipes stay in each room's
# greybox/ folder, unused, with the greybox's placements beside them.
ROOMS = [
    ('cinema', 36.0, 'rooms/cinema/cinema.play.json', 'rooms/cinema/cinema.placements.json', ['rooms/cinema/dressed']),
    ('booth', 40.0, 'rooms/booth/booth.play.json', 'rooms/booth/booth.placements.json', ['rooms/booth/dressed']),
    ('corridor', 36.0, 'rooms/corridor/corridor.play.json', 'rooms/corridor/corridor.placements.json', ['rooms/corridor/dressed']),
    ('shopfloor', 31.0, 'rooms/shopfloor/shopfloor.play.json', 'rooms/shopfloor/shopfloor.placements.json', ['rooms/shopfloor']),
    ('foodhall', -4.0, 'rooms/foodhall/foodhall.play.json', 'rooms/foodhall/foodhall.placements.json', ['rooms/foodhall']),
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
    # the order: each room's `next` is the one right of it in the section (the doors join them)
    for k, c in enumerate(cells):
        room = next(e for e in c['entities'] if e['type'] == 'room')
        if k == 0:
            room['params']['first'] = True
        if k + 1 < len(cells):
            room['params']['next'] = room_ids[k + 1]
    world = {
        'format': 'mei-world', 'version': 1, 'name': 'level2',
        'game': '../../afterhours.game.mochi', 'assets': asset_dirs[0], 'asset_dirs': asset_dirs[1:],
        'grid': {'cell_size': CELL},
        'collision': {'surfaces': {'default': 0}},
        'regions': regions,
        'paths': paths,
        'runtime': {'depth': True, 'perspective': True},
        # stand-ins of each room, made by the kit from the room itself: for the pull-back between
        # rooms, which shows the neighbours far and small. A cap takes whole placements, and the
        # dressed cinema, shop floor and food hall each draw their shell and most of the room as
        # one recipe (717, 830 and 1,183 triangles): their caps hold all of each room, or its
        # stand-in would be a few counters in the air
        'standins': {'distance': 64, 'triangles': 700,
                     'cells': {'cinema': {'triangles': 720}, 'shopfloor': {'triangles': 1600},
                               'foodhall': {'triangles': 1400}}},
        # the room budget is DESIGN.md's 2,500 triangles; stand-ins as the caps above
        'verification': {'vantage_points': vantage,
                         'thresholds': {'cell_triangles': 2500, 'standin_triangles': 1600}},
        'cells': cells,
    }
    write_json(HERE / 'level2.world.json', world)


if __name__ == '__main__':
    main()
