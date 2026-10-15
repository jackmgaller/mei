"""Helpers the rooms' greybox scripts share (carts/afterhours/rooms/*/make_*.py): Asset Kit boxes and
recipes in flat colours, and the room files the level is assembled from.

A room is written in its own frame: x right on the screen, z away from the camera, y up, the
origin at the middle of its floor (as the aquarium sketch is). A room script writes:

  greybox/*.asset.json   its Asset Kit recipes (deliberately plain: the builders dress them)
  NAME.placements.json   what is drawn: placements of those recipes, in the room's frame; written
                         only while it does not exist (the dressed room's builder owns it after);
                         the greybox's are always in greybox/NAME.placements.json
  NAME.play.json         what is played: the room's entities (the room, spawn, exit, watchers,
                         routes, trains, hiding places and the wall map) and train paths, in the
                         room's frame

levels/level1/make_level1.py moves each room to its place in the level and writes the world. A
room builder replaces the placements (and the recipes) and leaves the play file alone; the room's
PLAN.md says what must stay where.
"""
import json
import math
from pathlib import Path

CART = Path(__file__).resolve().parents[1]

# Flat colours, readable by kind. The thief's colour (orange) is no prop's.
C = {
    'slab': '#3a3f4a', 'cut': '#a8b2c4', 'floor': '#8c9098', 'floor_dark': '#6c7078',
    'tile': '#9aa0a6', 'wall': '#4c5462', 'wall_light': '#6c7484', 'bed': '#2a2c31',
    'rail': '#707680', 'edge_line': '#d0b440', 'tunnel': '#14161a',
    'stair': '#9a9ea6', 'stair_side': '#5c6470', 'pillar': '#b4bac4', 'bench': '#7c6852',
    'hide': '#3c5c8c', 'hide_floor': '#283c5c', 'door': '#3c7c5c', 'door_light': '#7cf0a0',
    'glass': '#6cb4d4', 'gate': '#8a8f9a', 'gate_top': '#c8ccd4', 'desk': '#7a6a5a',
    'shutter': '#5a6068', 'machine': '#4c6c8c', 'plant': '#4c7c4c', 'escalator': '#7c8088',
    'escalator_side': '#4c5058', 'lift': '#9c9070',
}

CUT = 1.0          # anything in the play area is cut at 1 m (the section)
WALL_H = 2.4       # the section's ceiling: back and end walls
WALL_T = 0.25


def r(v, n=4):
    return round(float(v), n)


def box(id, lo, hi, material, **extra):
    """A box from corner lo to corner hi."""
    node = {'id': id, 'op': 'box', 'size': [r(h - l) for l, h in zip(lo, hi)], 'material': material,
            'transform': {'translate': [r((l + h) / 2) for l, h in zip(lo, hi)]}}
    node.update(extra)
    return node


def recipe(name, nodes, triangles, emissive=('door_light',), collision=False):
    """A recipe in flat colours, lit from one direction. Its materials are the colours its nodes
    name (C's keys), including face materials and decals."""
    used = set()

    def walk(ns):
        for n in ns:
            used.add(n['material'])
            used.update((n.get('faces') or {}).values())
            for d in n.get('decals', []):
                used.add(d['material'])
            walk(n.get('children', []))
    walk(nodes)
    rec = {'format': 'mei-asset', 'version': 1, 'name': name,
           'budget': {'vertices': 2048, 'triangles': triangles},
           'lighting': {'direction': [-0.35, 0.85, -0.45], 'ambient': 0.55},
           'materials': {k: dict({'color': C[k]}, **({'class': 'emissive'} if k in emissive else {}))
                         for k in sorted(used)},
           'nodes': nodes}
    if not collision:
        rec['verification'] = {'required': True, 'depth': True, 'perspective': True}
    return rec


def stair_profile(x_foot, x_top, steps, rise=0.2, sink=0.02):
    """The side outline of a stair rising from x_foot (y 0) to x_top (y steps * rise), for an
    `extrude` along z. Works rising either way."""
    run = (x_top - x_foot) / steps
    pts = [(x_top, -sink), (x_foot, -sink)]
    x = x_foot
    for k in range(1, steps + 1):
        pts.append((x, rise * k))
        if k < steps:
            x += run
            pts.append((x, rise * k))
    pts.append((x_top, rise * steps))
    if x_top < x_foot:
        pts.reverse()
    return [[r(a), r(b)] for a, b in pts]


# ---- entities, in the room's frame

def wall(id, x0, z0, x1, z1, blocks=True, solid=True, h=WALL_H):
    e = {'id': id, 'type': 'wall', 'position': [r((x0 + x1) / 2), 0, r((z0 + z1) / 2)],
         'params': {'size': [r(x1 - x0), r(h), r(z1 - z0)]}}
    if not blocks:
        e['params']['blocks'] = False
    if not solid:
        e['params']['solid'] = False
    return e


def heading(dx, dz):
    return math.degrees(math.atan2(dx, dz)) % 360


def patrol(gid, start, route, speed, sight, fov, hear=6, turn_rate=None):
    """A patrol guard and his waypoints. route: [(id, (x, z), wait ticks, look degrees)], a loop."""
    out = []
    ids = [w[0] for w in route]
    for k, (wid, (x, z), wait, look) in enumerate(route):
        out.append({'id': wid, 'type': 'waypoint', 'position': [r(x), 0, r(z)],
                    'params': {'next': ids[(k + 1) % len(ids)], 'wait': wait, 'look': look}})
    fx, fz = route[0][1]
    p = {'kind': 'patrol', 'route': ids[0], 'speed': speed, 'sight': sight, 'fov': fov, 'hear': hear}
    if turn_rate is not None:
        p['turn_rate'] = turn_rate
    out.append({'id': gid, 'type': 'guard', 'position': [r(start[0]), 0, r(start[1])],
                'yaw': r(heading(fx - start[0], fz - start[1]), 2), 'params': p})
    return out


def posted(gid, pos, look_a, look_b, hold, turn, sight, fov, phase=0, hear=6, kind='posted', y=0):
    return {'id': gid, 'type': 'guard', 'position': [r(pos[0]), r(y), r(pos[1])],
            'params': {'kind': kind, 'look_a': look_a, 'look_b': look_b, 'hold': hold, 'turn': turn,
                       'phase': phase, 'sight': sight, 'fov': fov, **({'hear': hear} if kind != 'camera' else {})}}


def write_json(path, data, quiet=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=1) + '\n'
    if not path.exists() or path.read_text() != text:
        path.write_text(text)
        if not quiet:
            print('wrote', path.relative_to(CART))


def write_room(here, name, recipes, placements, play):
    """Writes a room's greybox recipes and play file beside its script, and its placements file
    only while there is none: once the room's builder has written theirs (the dressed room), the
    placements are the builder's, and the greybox's go to greybox/NAME.placements.json instead."""
    here = Path(here)
    for rec in recipes:
        write_json(here / 'greybox' / f'{rec["name"]}.asset.json', rec)
    data = {'format': 'after-hours-placements', 'version': 1, 'room': name, 'placements': placements}
    write_json(here / 'greybox' / f'{name}.placements.json', data)
    if not (here / f'{name}.placements.json').exists():
        write_json(here / f'{name}.placements.json', data)
    write_json(here / f'{name}.play.json', dict({'format': 'after-hours-play', 'version': 1, 'room': name}, **play))
