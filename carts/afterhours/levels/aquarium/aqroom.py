"""An aquarium room in greybox from a short description (the rooms' make_*.py in rooms/aq_*):
levels/s2room.py's rooms of doors, with what the aquarium adds (NOTES_J.md, "Runtime, agreed
with A"): dark rooms and their lights, water, and a second level (a mezzanine or a catwalk)
`upper` metres over the floor. levels/greybox.py's conventions: the room's own frame (x right, z
away from the camera, the floor y = 0, the origin in its middle), everything in play cut at 1 m
above its own level, the back and end walls 2.4 m over the highest level.

A room description (a dict), as s2room's, and:

  dark       true: a watcher without a torch sees only in the room's lights
  upper      the second level's height (metres), or absent: one level
  doors      as s2room's, with `level` (0 or 1); a doorway on level 1 opens from `upper` up
  props      [(id, kind, (x0, z0, x1, z1), height[, open faces])] on the floor: s2room's kinds,
             and 'water' (a sunken pool or an open tank's water: stops everyone, cones cross)
  upper_props  the same on level 1 (heights from `upper`); 'water' there is a tank's top, 'drop'
             open air (nothing drawn)
  walks      [(x0, z0, x1, z1)]: level 1's floor (catwalks, the mezzanine); everything else on
             level 1 is open air, a solid wall that cones cross (worked out here)
  lights     [(id, (x0, z0, x1, z1), level, cycle)]: where light falls on the floor; cycle None
             (always lit) or (period, on, offset): lit while (clock - offset) mod period < on
  hides      [(id, (x0, z0, x1, z1)[, level])]
  fragile    [(id, (x, z), radius, noise[, level])]
  guards     greybox.patrol() / posted() entities; aqroom.torch() and aqroom.on_level() set
             their extra fields
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from greybox import C, CUT, WALL_H, WALL_T, box, recipe, wall, r  # noqa: E402
import s2room  # noqa: E402

C.setdefault('water', '#1c4a6c')
C.setdefault('water_top', '#2c6c94')
C.setdefault('grate', '#5c6470')
C.setdefault('light_pool', '#7cc8e0')
C.setdefault('light_cycle', '#b08ce0')
C.setdefault('tank', '#3c7ca4')
C.setdefault('fragile_box', '#c87c3c')

KIND = dict(s2room.KIND)
KIND['water'] = ('water', False, True)
KIND['drop'] = (None, False, True)
DOOR_DEPTH = s2room.DOOR_DEPTH
YAW = s2room.YAW


# ---- entities' extra fields

def torch(ents):
    """A guard (the guard entity among a patrol's) carries a lamp: he sees his whole fan."""
    for e in ents if isinstance(ents, list) else [ents]:
        if e['type'] == 'guard':
            e['params']['torch'] = True
    return ents


def on_level(ents, level):
    """A guard (and so his waypoints: they take his level) on level 1."""
    for e in ents if isinstance(ents, list) else [ents]:
        if level and e['type'] == 'guard':
            e['params']['level'] = level
    return ents


# ---- level 1's open air: the room's inside less the walks, as boxes

def complement(x0, z0, x1, z1, rects):
    xs = sorted({x0, x1, *[a for q in rects for a in (q[0], q[2]) if x0 < a < x1]})
    zs = sorted({z0, z1, *[a for q in rects for a in (q[1], q[3]) if z0 < a < z1]})

    def covered(cx, cz):
        return any(q[0] <= cx <= q[2] and q[1] <= cz <= q[3] for q in rects)
    free = [[not covered((xs[i] + xs[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2) for j in range(len(zs) - 1)]
            for i in range(len(xs) - 1)]
    out = []
    used = [[False] * (len(zs) - 1) for _ in range(len(xs) - 1)]
    for j in range(len(zs) - 1):
        for i in range(len(xs) - 1):
            if not free[i][j] or used[i][j]:
                continue
            i1 = i
            while i1 + 1 < len(xs) - 1 and free[i1 + 1][j] and not used[i1 + 1][j]:
                i1 += 1
            j1 = j
            while j1 + 1 < len(zs) - 1 and all(free[k][j1 + 1] and not used[k][j1 + 1] for k in range(i, i1 + 1)):
                j1 += 1
            for k in range(i, i1 + 1):
                for m in range(j, j1 + 1):
                    used[k][m] = True
            out.append((xs[i], zs[j], xs[i1 + 1], zs[j1 + 1]))
    return out


def grid_cells(rects):
    """The union of rects as the cells of the grid their edges make."""
    xs = sorted({a for q in rects for a in (q[0], q[2])})
    zs = sorted({a for q in rects for a in (q[1], q[3])})
    out = []
    for j in range(len(zs) - 1):
        for i in range(len(xs) - 1):
            cx, cz = (xs[i] + xs[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
            if any(q[0] <= cx <= q[2] and q[1] <= cz <= q[3] for q in rects):
                out.append((xs[i], zs[j], xs[i + 1], zs[j + 1]))
    return out


# ---- drawing

def inset(d, q, by=0.01):
    """A box drawn on level 1, kept off the room's walls by `by` (else its faces would lie in
    theirs)."""
    X0, X1 = d['x']
    Z0, Z1 = d['z']
    x0, z0, x1, z1 = q
    return (max(x0, X0 + by), max(z0, Z0 + by), min(x1, X1 - by), min(z1, Z1 - by))


def wall_top(d):
    return (d.get('upper') or 0.0) + WALL_H


def shell_nodes(d, collision=False):
    X0, X1 = d['x']
    Z0, Z1 = d['z']
    U = d.get('upper')
    H = wall_top(d)
    xo0, xo1, zo0, zo1 = X0 - WALL_T, X1 + WALL_T, Z0 - WALL_T, Z1 + WALL_T
    mat = 'floor' if collision else 'wall'
    op = ['bottom', 'top'] if collision else ['bottom']
    top = {} if collision else {'faces': {'top': 'cut'}}
    n = []
    slab = dict(faces={'top': 'tile', 'back': 'cut'}, open=['bottom', 'left', 'right', 'front'])
    if collision:
        slab = dict(open=['bottom', 'left', 'right', 'front', 'back'])
    decals = []
    if not collision:
        for h in d.get('hides', []):
            hid, (x0, z0, x1, z1) = h[:2]
            if (h[2] if len(h) > 2 else 0) == 0:
                decals.append({'id': f'hide_{hid}', 'face': 'top', 'material': 'hide_floor',
                               'size': [r(x1 - x0 - 0.02), r(z1 - z0 - 0.02)], 'at': [r((x0 + x1) / 2), r((z0 + z1) / 2)]})
        for lid, (x0, z0, x1, z1), lvl, cyc in d.get('lights', []):
            if lvl == 0:
                decals.append({'id': f'light_{lid}', 'face': 'top', 'material': 'light_cycle' if cyc else 'light_pool',
                               'size': [r(x1 - x0 - 0.02), r(z1 - z0 - 0.02)], 'at': [r((x0 + x1) / 2), r((z0 + z1) / 2)]})
        if decals:
            slab['decals'] = decals
    n.append(box('slab', (xo0, -0.4, zo0), (xo1, 0, zo1), 'floor' if collision else 'floor_dark', **slab))
    fr = {} if collision else {'faces': {'top': 'cut', 'back': 'cut'}}
    gaps0 = {s: [dr['at'] for dr in d['doors'] if dr['side'] == s and dr.get('level', 0) == 0] for s in 'wen'}
    gaps1 = {s: [dr['at'] for dr in d['doors'] if dr['side'] == s and dr.get('level', 0) == 1] for s in 'wen'}
    n.append(box('front_wall', (xo0, -0.02 if collision else 0, zo0), (xo1, CUT, Z0), mat, open=list(op), **fr))

    def wall_run(tag, lo, hi, gaps, mk, y0, y1):
        for i, (a, b) in enumerate(s2room.segments(lo, hi, gaps)):
            n.append(mk(f'{tag}_{i}', a, b, y0, y1, a == lo, b == hi))

    def back_box(name, a, b, y0, y1, first, last):
        return box(name, (a, y0, Z1), (b, y1, zo1), mat, open=list(op), **top)

    def end_box(side):
        ax0, ax1 = (xo0, X0) if side == 'w' else (X1, xo1)

        def mk(name, a, b, y0, y1, first, last):
            o = list(op)
            if a == Z0: o.append('back')
            if b == Z1: o.append('front')
            return box(name, (ax0, y0, a), (ax1, y1, b), mat, open=o, **top)
        return mk
    if U is None:
        wall_run('back', xo0, xo1, gaps0['n'], back_box, -0.02, WALL_H)
        for s in 'we':
            wall_run(f'end_{s}', Z0, Z1, gaps0[s], end_box(s), -0.02, WALL_H)
    else:
        # two bands: the floor's (with its doorways) up to the upper level, then the upper's
        wall_run('back', xo0, xo1, gaps0['n'], back_box, -0.02, 2.1)
        n.append(box('back_band', (xo0, 2.1, Z1), (xo1, U, zo1), mat, open=['bottom', 'top'] if collision else ['bottom']))
        wall_run('back_up', xo0, xo1, gaps1['n'], back_box, U, H)
        for s in 'we':
            wall_run(f'end_{s}', Z0, Z1, gaps0[s], end_box(s), -0.02, 2.1)
            ax0, ax1 = (xo0, X0) if s == 'w' else (X1, xo1)
            n.append(box(f'end_{s}_band', (ax0, 2.1, Z0), (ax1, U, Z1), mat,
                         open=(['bottom', 'top', 'back', 'front'] if collision else ['bottom', 'back', 'front'])))
            wall_run(f'end_{s}_up', Z0, Z1, gaps1[s], end_box(s), U, H)
    if not collision:
        for lvl, gaps in ((0, gaps0), (1, gaps1)):
            if lvl == 1 and U is None:
                continue
            if lvl == 0 and U is not None:
                continue        # the band over the floor's doorways is their lintel
            y = 0.0 if lvl == 0 else U
            for i, (a, b) in enumerate(gaps['n']):
                n.append(box(f'back_lintel{lvl}_{i}', (a, y + 2.1, Z1), (b, y + 2.4 - 0.01, zo1), 'wall',
                             open=['left', 'right'], faces={'bottom': 'door_light'}))
            for s in 'we':
                ax0, ax1 = (xo0, X0) if s == 'w' else (X1, xo1)
                for i, (a, b) in enumerate(gaps[s]):
                    n.append(box(f'end_{s}_lintel{lvl}_{i}', (ax0, y + 2.1, a), (ax1, y + 2.4 - 0.01, b), 'wall',
                                 open=['front', 'back'], faces={'bottom': 'door_light'}))
    if U is not None:
        walks = d.get('walks', [])
        for i, (x0, z0, x1, z1) in enumerate(walks):
            o = ['bottom']
            # a face against another walk is open (the two would lie in one plane)
            for j, (a0, b0, a1, b1) in enumerate(walks):
                if j == i:
                    continue
                if abs(a1 - x0) < 1e-6 and b0 < z1 and b1 > z0: o.append('left')
                if abs(a0 - x1) < 1e-6 and b0 < z1 and b1 > z0: o.append('right')
                if abs(b1 - z0) < 1e-6 and a0 < x1 and a1 > x0: o.append('back')
                if abs(b0 - z1) < 1e-6 and a0 < x1 and a1 > x0: o.append('front')
            if collision:
                continue
            x0, z0, x1, z1 = inset(d, (x0, z0, x1, z1))
            n.append(box(f'walk_{i}', (x0, U - 0.15, z0), (x1, U, z1), 'grate', open=sorted(set(o))))
        if collision:
            # the walks' floor as a grid of pieces whose edges meet end to end (the World Checker
            # fails an edge that ends in the middle of another)
            for k, (x0, z0, x1, z1) in enumerate(grid_cells(walks)):
                n.append(box(f'walk_c{k}', (x0, U - 0.15, z0), (x1, U, z1), 'floor', open=['bottom']))
    if collision:
        return n
    for lvl, key in ((0, 'props'), (1, 'upper_props')):
        y = 0.0 if lvl == 0 else (U or 0.0)
        for prop in d.get(key, []):
            pid, kind, (x0, z0, x1, z1), h = prop[:4]
            if kind == 'drop':
                continue
            m = KIND[kind][0]
            o = ['bottom'] + list(prop[4] if len(prop) > 4 else [])
            if kind == 'water':
                # the water's surface a little below the level's floor
                if lvl == 1:
                    x0, z0, x1, z1 = inset(d, (x0, z0, x1, z1))
                n.append(box(f'{pid}', (x0, y - 0.35, z0), (x1, y - 0.15, z1), 'water', open=o,
                             faces={'top': 'water_top'}))
                continue
            hh = min(h, CUT) if kind != 'mark' else 0.01
            if z1 >= Z1: o.append('front')
            if z0 <= Z0: o.append('back')
            if x0 <= X0: o.append('left')
            if x1 >= X1: o.append('right')
            node = box(f'{pid}', (x0, y - 0.02 if kind != 'mark' else y, z0), (x1, y + hh, z1), m, open=o)
            if kind != 'mark':
                node['faces'] = {'top': 'cut' if h > CUT else ('glass' if kind == 'glass' else m)}
            n.append(node)
        if lvl == 1 and U is not None:
            for lid, (x0, z0, x1, z1), l, cyc in d.get('lights', []):
                if l == 1:
                    x0, z0, x1, z1 = inset(d, (x0, z0, x1, z1), 0.02)
                    n.append(box(f'light1_{lid}', (x0, U, z0), (x1, U + 0.02, z1),
                                 'light_cycle' if cyc else 'light_pool', open=['bottom']))
    for f in d.get('fragile', []):
        fid, (x, z), rad = f[:3]
        y = 0.0 if (f[4] if len(f) > 4 else 0) == 0 else U
        n.append(box(f'fragile_{fid}', (x - rad * 0.7, y, z - rad * 0.7), (x + rad * 0.7, y + 0.5, z + rad * 0.7),
                     'fragile_box', open=['bottom']))
    return n


# ---- what is played

def play_entities(d):
    P = d['prefix']
    X0, X1 = d['x']
    Z0, Z1 = d['z']
    U = d.get('upper')
    xo0, xo1, zo0, zo1 = X0 - WALL_T, X1 + WALL_T, Z0 - WALL_T, Z1 + WALL_T
    ents = []
    entry = None
    for dr in d['doors']:
        a0, a1 = dr['at']
        lvl = dr.get('level', 0)
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
            sp_e = {'id': P + 'spawn_' + dr['id'], 'type': 'spawn', 'position': [r(sp[0]), 0, r(sp[1])],
                    'params': {'yaw': yaw}}
            if lvl:
                sp_e['params']['level'] = lvl
            ents.append(sp_e)
        if dr.get('to'):
            p['to'] = dr['to']
        if dr.get('end'):
            p['end'] = True
        if lvl:
            p['level'] = lvl
        ents.append({'id': did, 'type': 'door', 'position': [r(pos[0]), 0, r(pos[1])], 'yaw': yaw, 'params': p})
        if dr['id'] == d['entry']:
            entry = P + 'spawn_' + dr['id']
    params = {'name': d['title'], 'entry': entry, 'size': [r(xo1 - xo0), r(wall_top(d)), r(zo1 - zo0)]}
    if d.get('dark'):
        params['dark'] = True
    if U is not None:
        params['upper'] = U
    ents.insert(0, {'id': P + 'room', 'type': 'room', 'position': [0, 0, 0], 'params': params})

    def lw(e, lvl):
        if lvl:
            e['params']['level'] = lvl
        return e
    levels = [0] if U is None else [0, 1]
    for lvl in levels:
        gaps = {s: [dr['at'] for dr in d['doors'] if dr['side'] == s and dr.get('level', 0) == lvl] for s in 'wen'}
        t = '' if lvl == 0 else 'up_'
        if lvl == 0:
            ents.append(wall(P + 'wall_front', xo0, zo0, xo1, Z0, h=CUT))
        for i, (a, b) in enumerate(s2room.segments(xo0, xo1, gaps['n'])):
            ents.append(lw(wall(f'{P}wall_{t}back_{i}', a, Z1, b, zo1), lvl))
        for side, (ax0, ax1) in (('w', (xo0, X0)), ('e', (X1, xo1))):
            for i, (a, b) in enumerate(s2room.segments(Z0, Z1, gaps[side])):
                ents.append(lw(wall(f'{P}wall_{t}end_{side}_{i}', ax0, a, ax1, b), lvl))
    for lvl, key in ((0, 'props'), (1, 'upper_props')):
        for prop in d.get(key, []):
            pid, kind, (x0, z0, x1, z1), h = prop[:4]
            if kind == 'mark':
                continue
            _, blocks, solid = KIND[kind]
            ents.append(lw(wall(P + 'wall_' + pid, x0, z0, x1, z1, blocks=blocks, solid=solid, h=h), lvl))
    if U is not None:
        # level 1's open air: inside the room, off the walks and off level 1's own props
        taken = list(d.get('walks', [])) + [q[2] for q in d.get('upper_props', []) if q[1] in ('water', 'drop')]
        for i, q in enumerate(complement(X0, Z0, X1, Z1, taken)):
            ents.append(lw(wall(f'{P}air_{i}', *q, blocks=False, h=0.0), 1))
    for h in d.get('hides', []):
        hid, (x0, z0, x1, z1) = h[:2]
        e = {'id': P + 'hide_' + hid, 'type': 'hide_spot', 'position': [r((x0 + x1) / 2), 0, r((z0 + z1) / 2)],
             'params': {'size': [r(x1 - x0), 1.7, r(z1 - z0)]}}
        ents.append(lw(e, h[2] if len(h) > 2 else 0))
    for f in d.get('fragile', []):
        fid, (x, z), rad, noise = f[:4]
        e = {'id': P + 'fragile_' + fid, 'type': 'fragile', 'position': [r(x), 0, r(z)],
             'params': {'radius': rad, 'noise': noise}}
        ents.append(lw(e, f[4] if len(f) > 4 else 0))
    for lid, (x0, z0, x1, z1), lvl, cyc in d.get('lights', []):
        e = {'id': P + 'light_' + lid, 'type': 'light', 'position': [r((x0 + x1) / 2), 0, r((z0 + z1) / 2)],
             'params': {'size': [r(x1 - x0), 0.1, r(z1 - z0)]}}
        if cyc:
            e['params'].update(period=cyc[0], on=cyc[1], offset=cyc[2])
        ents.append(lw(e, lvl))
    ents += d.get('guards', [])
    return ents


def build(d, triangles=1200):
    """(recipes, placements, play) for greybox.write_room()."""
    P = d['prefix']
    rec = recipe(P + 'shell', shell_nodes(d), triangles)
    col = recipe(P + 'shell_col', shell_nodes(d, collision=True), 400, collision=True)
    placements = [{'id': P + 'shell', 'asset': P + 'shell', 'position': [0, 0, 0], 'collision': P + 'shell_col'}]
    return [rec, col], placements, {'entities': play_entities(d), 'paths': {}}


def deg(dx, dz):
    return math.degrees(math.atan2(dx, dz)) % 360
