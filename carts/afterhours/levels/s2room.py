"""A stage 2 room in greybox from a short description (the rooms' make_*.py): its shell with
doorways in its walls, its props, and its play file's entities (the room, its doors and their
spawns, keycards, hiding places, watchers and the wall map). levels/greybox.py's conventions:
the room's own frame (x right, z away from the camera, the floor y = 0, the origin in its middle),
everything in play cut at 1 m, the back and end walls 2.4 m high.

A room description (a dict):

  name, prefix         the room's file name and its ids' prefix ('cn_')
  title                its name as the game shows it, a World Kit name ('the_cinema')
  x, z                 the inner faces of its end walls (x0, x1) and front and back walls (z0, z1)
  doors                [{id, side: 'w' | 'e' | 'n', at: (a0, a1), to, card, end, spawn: (along, depth)}]
                       a doorway in the west, east or back (north) wall from a0 to a1 (z for the
                       end walls, x for the back wall); its spawn `depth` metres into the room from
                       the wall's middle line (default 1.0), facing in; `along` shifts it along the
                       wall from the doorway's middle
  entry                the door whose spawn the stage starts at (the first room), else any
  props                [(id, kind, (x0, z0, x1, z1), height[, faces to leave open])]: kind 'block'
                       (stops the thief, cuts cones: a wall, a pillar, a mannequin), 'low' (stops
                       the thief, cones pass: counters, seats), 'glass' (the same, drawn as glass),
                       'mark' (drawn only); a face against another prop is named open (the Asset
                       Kit's faces: 'back' is -z, toward the camera, 'front' +z)
  hides                [(id, (x0, z0, x1, z1))]: hiding places (A in the box)
  cards                [(id, colour, (x, z))]
  guards               entities made by greybox.patrol() / greybox.posted()
"""
import math

from greybox import CUT, WALL_H, WALL_T, box, recipe, wall, r

KIND = {'block': ('wall_light', True, True), 'low': ('desk', False, True), 'glass': ('glass', False, True),
        'mark': ('floor_dark', False, False), 'seat': ('bench', False, True), 'machine': ('machine', True, True),
        'pillar': ('pillar', True, True), 'hide': ('hide', True, True)}
DOOR_DEPTH = 0.4
YAW = {'w': 90, 'e': 270, 'n': 180}


def segments(lo, hi, gaps):
    """The pieces of a wall from lo to hi between its gaps [(a0, a1)]."""
    out, at = [], lo
    for a0, a1 in sorted(gaps):
        if a0 > at:
            out.append((at, a0))
        at = a1
    if hi > at:
        out.append((at, hi))
    return out


def shell_nodes(d, collision=False):
    X0, X1 = d['x']
    Z0, Z1 = d['z']
    xo0, xo1, zo0, zo1 = X0 - WALL_T, X1 + WALL_T, Z0 - WALL_T, Z1 + WALL_T
    gaps = {s: [dr['at'] for dr in d['doors'] if dr['side'] == s] for s in 'wen'}
    mat = 'floor' if collision else 'wall'
    op = ['bottom', 'top'] if collision else ['bottom']
    top = {} if collision else {'faces': {'top': 'cut'}}
    n = []
    slab = dict(faces={'top': 'tile', 'back': 'cut'}, open=['bottom', 'left', 'right', 'front'])
    if collision:
        slab = dict(open=['bottom', 'left', 'right', 'front', 'back'])
    decals = []
    if not collision:
        for hid, (x0, z0, x1, z1) in d.get('hides', []):
            decals.append({'id': f'hide_{hid}', 'face': 'top', 'material': 'hide_floor', 'size': [r(x1 - x0 - 0.02), r(z1 - z0 - 0.02)],
                           'at': [r((x0 + x1) / 2), r((z0 + z1) / 2)]})
        if decals:
            slab['decals'] = decals
    n.append(box('slab', (xo0, -0.4, zo0), (xo1, 0, zo1), 'floor' if collision else 'floor_dark', **slab))
    fr = {} if collision else {'faces': {'top': 'cut', 'back': 'cut'}}
    n.append(box('front_wall', (xo0, -0.02 if collision else 0, zo0), (xo1, CUT, Z0), mat, open=list(op), **fr))
    # the back wall in pieces between its doorways, a lintel over each
    for i, (a, b) in enumerate(segments(xo0, xo1, gaps['n'])):
        n.append(box(f'back_{i}', (a, -0.02, Z1), (b, WALL_H, zo1), mat, open=list(op), **top))
    for i, (a, b) in enumerate(gaps['n']):
        if not collision:
            n.append(box(f'back_lintel_{i}', (a, 2.1, Z1), (b, WALL_H - 0.01, zo1), 'wall', open=['left', 'right'],
                         faces={'bottom': 'door_light'}))
    # the end walls between the front and back walls, in pieces
    for side, (ax0, ax1) in (('w', (xo0, X0)), ('e', (X1, xo1))):
        pieces = segments(Z0, Z1, gaps[side])
        for i, (a, b) in enumerate(pieces):
            o = list(op)
            if a == Z0: o.append('back')        # the Asset Kit's 'back' is the -z face (toward the camera)
            if b == Z1: o.append('front')
            n.append(box(f'end_{side}_{i}', (ax0, -0.02, a), (ax1, WALL_H, b), mat, open=o, **top))
        for i, (a, b) in enumerate(gaps[side]):
            if not collision:
                n.append(box(f'end_{side}_lintel_{i}', (ax0, 2.1, a), (ax1, WALL_H - 0.01, b), 'wall', open=['front', 'back'],
                             faces={'bottom': 'door_light'}))
    if collision:
        return n
    for prop in d.get('props', []):
        pid, kind, (x0, z0, x1, z1), h = prop[:4]
        m = KIND[kind][0]
        hh = min(h, CUT) if kind != 'mark' else 0.01
        o = ['bottom'] + list(prop[4] if len(prop) > 4 else [])
        # a face against the room's walls is open (it would lie on the wall's face)
        if z1 >= Z1: o.append('front')
        if z0 <= Z0: o.append('back')
        if x0 <= X0: o.append('left')
        if x1 >= X1: o.append('right')
        node = box(pid, (x0, -0.02 if kind != 'mark' else 0.0, z0), (x1, hh, z1), m, open=o)
        if kind != 'mark':
            node['faces'] = {'top': 'cut' if h > CUT else ('glass' if kind == 'glass' else m)}
        n.append(node)
    return n


def play_entities(d):
    P = d['prefix']
    X0, X1 = d['x']
    Z0, Z1 = d['z']
    xo0, xo1, zo0, zo1 = X0 - WALL_T, X1 + WALL_T, Z0 - WALL_T, Z1 + WALL_T
    gaps = {s: [dr['at'] for dr in d['doors'] if dr['side'] == s] for s in 'wen'}
    ents = []
    entry = None
    for dr in d['doors']:
        a0, a1 = dr['at']
        mid = (a0 + a1) / 2
        along, depth = dr.get('spawn') or (0.0, 1.0)
        if dr['side'] == 'w':
            pos, sp = (X0 - WALL_T / 2, mid), (X0 - WALL_T / 2 + depth, mid + along)
        elif dr['side'] == 'e':
            pos, sp = (X1 + WALL_T / 2, mid), (X1 + WALL_T / 2 - depth, mid + along)
        else:
            pos, sp = (mid, Z1 + WALL_T / 2), (mid + along, Z1 + WALL_T / 2 - depth)
        yaw = YAW[dr['side']]
        did = P + 'door_' + dr['id']
        p = {'size': [r(a1 - a0), 2.2, DOOR_DEPTH]}
        if dr.get('spawn') is not False:
            p['spawn'] = P + 'spawn_' + dr['id']
            ents.append({'id': P + 'spawn_' + dr['id'], 'type': 'spawn', 'position': [r(sp[0]), 0, r(sp[1])],
                         'params': {'yaw': yaw}})
        if dr.get('to'):
            p['to'] = dr['to']
        if dr.get('end'):
            p['end'] = True
        if dr.get('card', 'none') != 'none':
            p['card'] = dr['card']
        ents.append({'id': did, 'type': 'door', 'position': [r(pos[0]), 0, r(pos[1])], 'yaw': yaw, 'params': p})
        if dr['id'] == d['entry']:
            entry = P + 'spawn_' + dr['id']
    room = {'id': P + 'room', 'type': 'room', 'position': [0, 0, 0],
            'params': {'name': d['title'], 'entry': entry, 'size': [r(xo1 - xo0), WALL_H, r(zo1 - zo0)]}}
    ents.insert(0, room)
    # the wall map: the shell, then the props
    ents.append(wall(P + 'wall_front', xo0, zo0, xo1, Z0, h=CUT))
    for i, (a, b) in enumerate(segments(xo0, xo1, gaps['n'])):
        ents.append(wall(f'{P}wall_back_{i}', a, Z1, b, zo1))
    for side, (ax0, ax1) in (('w', (xo0, X0)), ('e', (X1, xo1))):
        for i, (a, b) in enumerate(segments(Z0, Z1, gaps[side])):
            ents.append(wall(f'{P}wall_end_{side}_{i}', ax0, a, ax1, b))
    for prop in d.get('props', []):
        pid, kind, (x0, z0, x1, z1), h = prop[:4]
        if kind == 'mark':
            continue
        _, blocks, solid = KIND[kind]
        ents.append(wall(P + 'wall_' + pid, x0, z0, x1, z1, blocks=blocks, solid=solid, h=h))
    for hid, (x0, z0, x1, z1) in d.get('hides', []):
        ents.append({'id': P + 'hide_' + hid, 'type': 'hide_spot', 'position': [r((x0 + x1) / 2), 0, r((z0 + z1) / 2)],
                     'params': {'size': [r(x1 - x0), 1.7, r(z1 - z0)]}})
    for cid, colour, (x, z) in d.get('cards', []):
        ents.append({'id': P + 'card_' + cid, 'type': 'keycard', 'position': [r(x), 0, r(z)], 'params': {'colour': colour}})
    ents += d.get('guards', [])
    return ents


def build(d, triangles=900):
    """(recipes, placements, play) for greybox.write_room()."""
    P = d['prefix']
    rec = recipe(P + 'shell', shell_nodes(d), triangles)
    col = recipe(P + 'shell_col', shell_nodes(d, collision=True), 300, collision=True)
    placements = [{'id': P + 'shell', 'asset': P + 'shell', 'position': [0, 0, 0], 'collision': P + 'shell_col'}]
    return [rec, col], placements, {'entities': play_entities(d), 'paths': {}}


def deg(dx, dz):
    return math.degrees(math.atan2(dx, dz)) % 360
