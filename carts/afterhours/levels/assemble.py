"""Assembles a stage's World Kit world from its rooms' files (each stage's levels/STAGE/make_STAGE.py
calls it). A stage is one place: one world, each room in its own 32 m cell side by side along x
in the section's order, at its own floor's height, one region per room, kit-made stand-ins.

A room's files are in its own frame (origin in the middle of its floor); every position here is
that plus the room's place. Entity and placement ids are already world-wide (each room's prefix).
The rooms' `next` chain their order (in a stage of a line it is also where each exit leads; in a
stage of doors only the order), and the first is marked `first`.
"""
import json
import math
from pathlib import Path

from greybox import CART, write_json, r

CELL = 32
CAM_DIST, CAM_PITCH = 28.166, 60      # the game's camera (dr_view.akr), for the World Checker's views

# Texture slots. Slot 7 is the front end's fonts' (agent E). Two rooms a door joins are drawn
# together, both textured, while the transition pans from one to the other (agent H, NOTES_H.md),
# so they take disjoint slot sets: two sets when the rooms can be coloured so (a line, a graph
# with no odd cycle), three when not. The biggest room today needs 8 slots.
SLOT_SETS_2 = ['13-8,6-0', '16-31']
SLOT_SETS_3 = ['13-8,6-0', '16-23', '24-31']


def slot_sets(names, joins):
    """{room: slot set} for rooms `names` (in order) joined by `joins` (pairs): two sets if the
    graph is two-colourable, else three (greedy, in order)."""
    nb = {n: set() for n in names}
    for a, b in joins:
        if a != b:
            nb[a].add(b)
            nb[b].add(a)
    colour = {}
    ok = True
    for start in names:
        if start in colour:
            continue
        colour[start] = 0
        todo = [start]
        while todo:
            n = todo.pop()
            for m in nb[n]:
                if m not in colour:
                    colour[m] = 1 - colour[n]
                    todo.append(m)
                elif colour[m] == colour[n]:
                    ok = False
    if ok:
        return {n: SLOT_SETS_2[colour[n]] for n in names}
    colour = {}
    for n in names:
        used = {colour[m] for m in nb[n] if m in colour}
        colour[n] = next(c for c in range(3) if c not in used)
    return {n: SLOT_SETS_3[colour[n]] for n in names}


def exit_to_door(play, door, to):
    """A room of a line's play (a dict) with its exit made a door of a stage of doors: the same box,
    leading to the door `to` (in another room); the room keeps its entry (the stage's start, when
    it is the first room). The tower's lobby, a room of level 1, is played this way."""
    play = json.loads(json.dumps(play))
    ents = play['entities']
    room = next(e for e in ents if e['type'] == 'room')
    ex_id = room['params'].pop('exit')
    k = next(i for i, e in enumerate(ents) if e['id'] == ex_id)
    ex = ents[k]
    sx, _, sz = ex['params']['size']
    ents[k] = {'id': door, 'type': 'door', 'position': ex['position'], 'yaw': 0,
               'params': {'size': [sx, 2.2, sz], 'to': to}}
    return play


def place(k, y):
    """Where room k's origin goes: the middle of its cell, at its floor height."""
    return (CELL * k + CELL / 2, y, CELL / 2)


def moved(pos, o):
    return [r(pos[0] + o[0]), r(pos[1] + o[1]), r(pos[2] + o[2])]


def build(out, name, rooms, names=None, storeys=None, standin_caps=None, standin_max=800, exit_doors=None):
    """Writes the world `name` to `out`.

    rooms         [(room, floor height, play file, placements file (or a list: the first that
                  exists), asset folders)], in the section's order, paths from the cart's folder
    names         {room: World Kit name} for rooms whose play file has none
    storeys       {room: storey} (room.storey: nF, Bn)
    standin_caps  {room: triangles} where a room's stand-in needs more than 700
    exit_doors    {room: (door id, to)}: a room of a line played in a stage of doors, its exit made
                  that door (exit_to_door())
    """
    names, storeys, standin_caps = names or {}, storeys or {}, standin_caps or {}
    exit_doors = exit_doors or {}
    out = Path(out)
    cells, regions, paths, vantage, asset_dirs = [], {}, {}, [], []
    room_ids = []
    for k, (room_name, y, play_path, placements_path, dirs) in enumerate(rooms):
        o = place(k, y)
        play = json.loads((CART / play_path).read_text())
        if room_name in exit_doors:
            play = exit_to_door(play, *exit_doors[room_name])
        if isinstance(placements_path, list):        # the builder's placements when they exist, else ours
            placements_path = next(p for p in placements_path if (CART / p).exists())
        placements = json.loads((CART / placements_path).read_text())['placements']
        ents = []
        for e in play['entities']:
            e = json.loads(json.dumps(e))
            e['position'] = moved(e['position'], o)
            ents.append(e)
        room = next(e for e in ents if e['type'] == 'room')
        params = dict(room['params'])
        if room_name in names:
            params['name'] = names[room_name]
        if room_name in storeys:
            params['storey'] = storeys[room_name]
        room['params'] = dict({'name': params.pop('name')}, **params)
        room_ids.append(room['id'])
        for pid, p in play.get('paths', {}).items():
            paths[pid] = dict(p, points=[moved(q, o) for q in p['points']])
        pls = []
        for p in placements:
            p = json.loads(json.dumps(p))
            p['position'] = moved(p['position'], o)
            pls.append(p)
        regions[room_name] = {}
        cells.append({'id': room_name, 'at': [k, 0], 'region': room_name, 'placements': pls, 'entities': ents})
        for d in dirs:
            if (CART / d).exists():
                asset_dirs.append(str(Path('../..') / d))
        # the game's camera over the room's middle (and its ends, for a room wider than a screen)
        sx = room['params']['size'][0]
        xs = [0.0] if sx <= 13.5 else [-(sx / 2 - 6.6), 0.0, sx / 2 - 6.6]
        cz = room['position'][2]
        for i, dx in enumerate(xs):
            vantage.append({'name': f'game_{room_name}_{i}', 'yaw': 0, 'pitch': -CAM_PITCH,
                            'position': [r(room['position'][0] + dx), r(y + 0.6 + CAM_DIST * math.sin(math.radians(CAM_PITCH))),
                                         r(cz - CAM_DIST * math.cos(math.radians(CAM_PITCH)))]})
    for k, c in enumerate(cells):
        room = next(e for e in c['entities'] if e['type'] == 'room')
        if k == 0:
            room['params']['first'] = True
        if k + 1 < len(cells):
            room['params']['next'] = room_ids[k + 1]
    # which rooms a door joins: the doors' `to`, or (a stage of a line) each room and the next
    room_of = {e['id']: c['id'] for c in cells for e in c['entities']}
    joins = [(room_of[e['id']], room_of[e['params']['to']]) for c in cells for e in c['entities']
             if e['type'] == 'door' and e['params'].get('to') in room_of]
    if not joins:
        joins = [(cells[k]['id'], cells[k + 1]['id']) for k in range(len(cells) - 1)]
    sets = slot_sets([c['id'] for c in cells], joins)
    for c in cells:
        regions[c['id']] = {'textures': {'slots': sets[c['id']]}}
    standins = {'distance': 64, 'triangles': 700}
    if standin_caps:
        standins['cells'] = {k: {'triangles': v} for k, v in standin_caps.items()}
    world = {
        'format': 'mei-world', 'version': 1, 'name': name,
        'game': '../../afterhours.game.mochi', 'assets': asset_dirs[0], 'asset_dirs': asset_dirs[1:],
        'grid': {'cell_size': CELL},
        'collision': {'surfaces': {'default': 0}},
        'regions': regions,
        'paths': paths,
        'runtime': {'depth': True, 'perspective': True},
        # the front end's fonts (agent E, front_art.akr) live in texture slot 7 and 4-bit palettes
        # 250-251, loaded once for the whole cart: no region may take them (each region's own
        # slots are above, from slot_sets())
        'textures': {'slots': '13-8,6-0,16-31'},
        'palette': {'reserved': [250, 251]},
        # stand-ins of each room, made by the kit from the room itself, for the pull-back between
        # rooms and the stage select's model. A cap takes whole placements: a room whose main
        # recipe is over 700 triangles gets its own cap, or its stand-in would leave it out
        'standins': standins,
        # the room budget is DESIGN.md's 2,500 triangles
        'verification': {'vantage_points': vantage,
                         'thresholds': {'cell_triangles': 2500, 'standin_triangles': standin_max}},
        'cells': cells,
    }
    write_json(out, world)
