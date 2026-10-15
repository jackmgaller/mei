#!/usr/bin/env python3
"""The subway platform for Dorobo Night, Gate 1 (greybox): writes its World Kit world and its
Asset Kit recipes.

    python3 carts/dorobo/rooms/platform/make_platform.py

Writes, beside itself:
  platform.world.json        the world: one cell, the placements, the paths of the two tracks and
                             every game entity (the room, the spawn, the exit, the watchers and their
                             routes, the trains and their timetables, the hiding places, the fragile
                             things and the wall map)
  assets/pf_shell.asset.json the station box: slab, track beds and rails, the island platform, the
                             staff walkway, the cut front wall, the back wall with the staff door and
                             the cupboard, the end walls with the tunnel mouths, the stair
  assets/pf_pillar.asset.json a pillar, cut at 1 m
  assets/pf_bench.asset.json  a bench
  assets/pf_kiosk.asset.json  the closed kiosk, open at the back: a hiding place
  assets/pf_shell_col.asset.json, pf_kiosk_col.asset.json  their collision: floors, and walls
                             without tops

Everything is a box in a flat colour, deliberately plain (Gate 2 dresses it). The wall map (the
`wall` entities the runtime cuts cones and stops the thief with) is written from the same numbers
as the boxes, so the two cannot drift apart. The puzzle and its solutions are in PUZZLE.md.

Plan (metres; x right on the screen, z away from the camera, y up; the platform's top is y = 0):
  z 0.75-1.0   the front wall, cut at 1 m (the section)
  z 1.0-3.4    track A (the near track): train A runs +x
  z 3.4-7.6    the island platform, x 1-31
  z 7.6-10.0   track B (the far track): train B runs -x
  z 10.0-11.2  the staff walkway, x 1-31, with the staff door (the exit) at its right end
  z 11.2-11.45 the back wall, 2.4 m (the section's ceiling), with a cupboard set into it
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE / 'assets'

# ---- the plan
X0, X1 = 1.0, 31.0            # inner faces of the end walls
WALL_T = 0.25                 # wall thickness
Y_BED = -1.1                  # the track beds
Y_SLAB = -1.4                 # the slab's underside, shown in section at the front
H = 2.4                       # the section's ceiling: back wall, end walls, stair top
CUT = 1.0                     # walls and pillars nearest the play are cut here

Z_FRONT = 1.0                 # front wall's inner face
TRACK_A = (1.0, 3.4)
PLAT = (3.4, 7.6)
TRACK_B = (7.6, 10.0)
WALK = (10.0, 11.2)
Z_BACK = 11.2                 # back wall's inner face

PLAT_Z = (PLAT[0] + PLAT[1]) / 2          # 5.5, the platform's centre line
TRACK_A_Z = (TRACK_A[0] + TRACK_A[1]) / 2  # 2.2
TRACK_B_Z = (TRACK_B[0] + TRACK_B[1]) / 2  # 8.8
WALK_Z = (WALK[0] + WALK[1]) / 2           # 10.6
TRACK_W = TRACK_A[1] - TRACK_A[0]          # 2.4
TUNNEL_TOP = 2.2              # tunnel mouths in the end walls, from the bed to here

STAIR_X = (X0, 4.4)           # the stair down from the concourse: the way in
STAIR_Z = (4.5, 6.5)
STAIR_STEPS = 11              # 0.2 m risers, 0.3 m treads
STAIR_TOP = 0.2 * STAIR_STEPS

PILLARS = [8.0, 13.0, 18.0, 23.0, 28.0]   # on the centre line
PILLAR_S = 0.5
BENCHES = [(10.5, PLAT_Z), (20.5, PLAT_Z), (25.5, PLAT_Z)]
BENCH_W, BENCH_D = 1.8, 0.45
KIOSK = (15.5, PLAT_Z)        # outer 1.6 x 1.3, open toward +z (the far track)
KIOSK_W, KIOSK_D, KIOSK_T = 1.6, 1.3, 0.15

CUPBOARD_X = (24.5, 25.5)     # a staff cupboard set into the back wall: a hiding place
CUPBOARD_D = 0.8              # how deep it goes behind the wall's face
DOOR_X = (29.0, 30.0)         # the staff door: the exit
DOOR_H = 2.1

# ---- the watchers, the trains and the tools (the puzzle; see PUZZLE.md)
SPAWN = (5.0, PLAT_Z, 90)     # x, z, yaw: at the stair's foot, facing along the platform
TOYS, BELLS = 2, 1

# The camera on the back wall above the walkway, looking across track B at the platform.
CAMERA = dict(pos=(16.0, 2.3, Z_BACK - 0.05), look_a=150, look_b=210, hold=60, turn=150,
              phase=0, sight=8.2, fov=40)
# The posted guard in the middle of the platform, by the kiosk, turning his head along it.
POSTED = dict(pos=(17.6, 0, 4.3), look_a=250, look_b=110, hold=120, turn=90, phase=0,
              sight=6.5, fov=60, hear=7)
# The platform patrol: a loop round the left half, in front of the pillars going left and behind
# them coming back.
PATROL_P = dict(start=(14.0, 4.3), speed=1.2, sight=6, fov=60, hear=7,
                route=[('p1_left_front', (6.1, 4.3), 60, 270),
                       ('p1_left_back', (6.1, 6.7), 30, 0),
                       ('p1_right_back', (14.0, 6.7), 60, 90),
                       ('p1_right_front', (14.0, 4.3), 30, 180)])
# The walkway patrol: up and down the walkway's right part, looking across track B at each end.
PATROL_W = dict(start=(25.3, WALK_Z), speed=1.0, sight=6, fov=60, hear=7,
                route=[('p2_east', (28.0, WALK_Z), 120, 180),
                       ('p2_west', (17.6, WALK_Z), 120, 180)])

# The timetables (ticks, 60 a second). The paths run between the end walls' outer faces.
TRACK_LEN = (X1 + WALL_T) - (X0 - WALL_T)   # 30.5
TRAIN_A = dict(period=2400, offset=480, arrive=240, stop=22.25, dwell=720, leave=300,
               cars=2, car_length=10, width=TRACK_W, doors=2, door_width=1.3, sides='left')
TRAIN_B = dict(period=2700, offset=1140, arrive=300, stop=27.5, dwell=600, leave=300,
               cars=2, car_length=10, width=TRACK_W, doors=3, door_width=1.3, sides='both')

FRAGILE = [('fragile_papers', (17.0, 6.9)),      # newspaper bundles behind the kiosk
           ('fragile_bucket', (21.4, 10.95))]     # a mop bucket on the walkway

# ---- colours (greybox: flat, plain, readable by kind)
C = {
    'slab': '#3a3f4a', 'cut': '#a8b2c4', 'bed': '#2a2c31', 'rail': '#707680',
    'platform': '#8c9098', 'platform_side': '#5c6068', 'edge_line': '#d0b440',
    'walkway': '#7a7e86', 'wall': '#4c5462', 'tunnel': '#14161a',
    'stair': '#9a9ea6', 'stair_side': '#5c6470',
    'pillar': '#b4bac4', 'bench': '#7c6852', 'hide': '#3c5c8c', 'hide_floor': '#283c5c',
    'door': '#3c7c5c', 'door_light': '#7cf0a0',
}


def r(v, n=4):
    return round(float(v), n)


def box(id, lo, hi, material, **extra):
    """A box from corner lo to corner hi."""
    node = {'id': id, 'op': 'box', 'size': [r(h - l) for l, h in zip(lo, hi)],
            'material': material,
            'transform': {'translate': [r((l + h) / 2) for l, h in zip(lo, hi)]}}
    node.update(extra)
    return node


def material(color, **extra):
    m = {'color': color}
    m.update(extra)
    return m


def recipe(name, materials, nodes, triangles):
    return {
        'format': 'mei-asset', 'version': 1, 'name': name,
        'budget': {'vertices': 2048, 'triangles': triangles},
        'lighting': {'direction': [-0.35, 0.85, -0.45], 'ambient': 0.55},
        'materials': {k: material(C[v] if v in C else v, **({'class': 'emissive'} if k == 'door_light' else {}))
                      for k, v in materials.items()},
        'verification': {'required': True, 'depth': True, 'perspective': True},
        'nodes': nodes,
    }


# ---- the station box

def shell():
    mats = {k: k for k in ('slab', 'cut', 'bed', 'rail', 'platform', 'platform_side', 'edge_line',
                           'walkway', 'wall', 'tunnel', 'stair', 'stair_side', 'hide',
                           'hide_floor', 'door', 'door_light')}
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T            # outer faces of the end walls
    zo0 = Z_FRONT - WALL_T                         # outer face of the front wall
    zo1 = Z_BACK + WALL_T                          # outer face of the back wall
    zc = Z_BACK + CUPBOARD_D                       # the cupboard's back
    n = []
    # The slab: its top is the track beds; its front is the section.
    n.append(box('slab', (xo0, Y_SLAB, zo0), (xo1, Y_BED, zc + WALL_T), 'slab',
                 faces={'top': 'bed', 'back': 'cut', 'left': 'cut', 'right': 'cut'}))
    # The front wall, cut at 1 m.
    n.append(box('front_wall', (xo0, Y_BED, zo0), (xo1, CUT, Z_FRONT), 'wall', open=['bottom'],
                 faces={'top': 'cut', 'back': 'cut'}))
    # The island platform and the walkway: their ends sink into the end walls.
    pz = PLAT[1] - PLAT[0]
    n.append(box('platform', (X0, Y_BED, PLAT[0]), (X1, 0, PLAT[1]), 'platform_side',
                 open=['bottom', 'left', 'right'], faces={'top': 'platform'},
                 decals=[{'id': 'edge_a', 'face': 'top', 'material': 'edge_line',
                          'size': [r(X1 - X0 - 0.1), 0.3], 'at': [0, r(-pz / 2 + 0.65)]},
                         {'id': 'edge_b', 'face': 'top', 'material': 'edge_line',
                          'size': [r(X1 - X0 - 0.1), 0.3], 'at': [0, r(pz / 2 - 0.65)]}]))
    wz = WALK[1] - WALK[0]
    n.append(box('walkway', (X0, Y_BED, WALK[0]), (X1, 0, Z_BACK + 0.02), 'platform_side',
                 open=['bottom', 'left', 'right', 'front'], faces={'top': 'walkway'},
                 decals=[{'id': 'edge_w', 'face': 'top', 'material': 'edge_line',
                          'size': [r(X1 - X0 - 0.1), 0.15], 'at': [0, r(-(wz + 0.02) / 2 + 0.3)]}]))
    # The rails.
    for t, zt in (('a', TRACK_A_Z), ('b', TRACK_B_Z)):
        for s, dz in (('l', -0.535), ('r', 0.535)):
            n.append(box(f'rail_{t}{s}', (xo0, Y_BED - 0.01, zt + dz - 0.035),
                         (xo1, Y_BED + 0.16, zt + dz + 0.035), 'rail', open=['bottom', 'left', 'right']))
    # The back wall, with the cupboard set into it and the staff door painted on it.
    door_cx = (DOOR_X[0] + DOOR_X[1]) / 2
    n.append(box('back_wall_w', (xo0, Y_BED, Z_BACK), (CUPBOARD_X[0], H, zo1), 'wall',
                 open=['bottom'], faces={'top': 'cut'}))
    seg_cx = (CUPBOARD_X[1] + xo1) / 2
    n.append(box('back_wall_e', (CUPBOARD_X[1], Y_BED, Z_BACK), (xo1, H, zo1), 'wall',
                 open=['bottom'], faces={'top': 'cut'},
                 decals=[{'id': 'door', 'face': 'back', 'material': 'door',
                          'size': [r(DOOR_X[1] - DOOR_X[0]), DOOR_H],
                          'at': [r(door_cx - seg_cx), r(DOOR_H / 2 - (H + Y_BED) / 2)]},
                         {'id': 'door_light', 'face': 'back', 'material': 'door_light',
                          'size': [0.5, 0.14], 'at': [r(door_cx - seg_cx), r(DOOR_H + 0.15 - (H + Y_BED) / 2)]}]))
    cx0, cx1 = CUPBOARD_X
    n.append(box('cupboard_back', (cx0 - WALL_T, Y_BED, zc), (cx1 + WALL_T, H, zc + WALL_T), 'hide',
                 open=['bottom'], faces={'top': 'cut'}))
    n.append(box('cupboard_w', (cx0 - WALL_T, Y_BED, zo1), (cx0, H, zc), 'hide',
                 open=['bottom', 'back', 'front'], faces={'top': 'cut'}))
    n.append(box('cupboard_e', (cx1, Y_BED, zo1), (cx1 + WALL_T, H, zc), 'hide',
                 open=['bottom', 'back', 'front'], faces={'top': 'cut'}))
    n.append(box('cupboard_floor', (cx0 - 0.01, Y_BED, Z_BACK + 0.02), (cx1 + 0.01, 0, zc + 0.01),
                 'platform_side', open=['bottom', 'back', 'left', 'right', 'front'], faces={'top': 'hide_floor'}))
    # The end walls, with a tunnel mouth over each track.
    for side, (wx0, wx1) in (('w', (xo0, X0)), ('e', (X1, xo1))):
        n.append(box(f'end_{side}_plat', (wx0, Y_BED, PLAT[0]), (wx1, H, PLAT[1]), 'wall',
                     open=['bottom'], faces={'top': 'cut'}))
        n.append(box(f'end_{side}_walk', (wx0, Y_BED, WALK[0]), (wx1, H, Z_BACK), 'wall',
                     open=['bottom', 'front'], faces={'top': 'cut'}))
        n.append(box(f'end_{side}_lintel_a', (wx0, TUNNEL_TOP, Z_FRONT), (wx1, H, TRACK_A[1]), 'wall',
                     open=['front'], faces={'top': 'cut', 'bottom': 'tunnel'}))
        n.append(box(f'end_{side}_lintel_b', (wx0, TUNNEL_TOP, TRACK_B[0]), (wx1, H, TRACK_B[1]), 'wall',
                     open=['back', 'front'], faces={'top': 'cut', 'bottom': 'tunnel'}))
    # The stair down from the concourse: one extrusion of its side, its foot at x = STAIR_X[1].
    run = (STAIR_X[1] - STAIR_X[0] - 0.1) / STAIR_STEPS
    pts = [(STAIR_X[0] - 0.02, -0.02), (STAIR_X[1], -0.02)]
    x = STAIR_X[1]
    for k in range(1, STAIR_STEPS + 1):
        pts.append((x, 0.2 * k))
        if k < STAIR_STEPS:
            x -= run
            pts.append((x, 0.2 * k))
    pts.append((STAIR_X[0] - 0.02, STAIR_TOP))
    n.append({'id': 'stair', 'op': 'extrude', 'material': 'stair', 'depth': r(STAIR_Z[1] - STAIR_Z[0]),
              'points': [[r(a), r(b)] for a, b in pts], 'faces': {'front': 'stair_side', 'back': 'stair_side'},
              'transform': {'translate': [0, 0, r((STAIR_Z[0] + STAIR_Z[1]) / 2)]}})
    return recipe('pf_shell', mats, n, 900)


def pillar():
    s = PILLAR_S / 2
    return recipe('pf_pillar', {'pillar': 'pillar', 'cut': 'cut'},
                  [box('pillar', (-s, -0.02, -s), (s, CUT, s), 'pillar', open=['bottom'], faces={'top': 'cut'})], 40)


def bench():
    w, d = BENCH_W / 2, BENCH_D / 2
    return recipe('pf_bench', {'bench': 'bench'},
                  [box('seat', (-w, 0.33, -d), (w, 0.45, d), 'bench'),
                   box('leg_w', (-w + 0.08, -0.02, -d + 0.04), (-w + 0.18, 0.34, d - 0.04), 'bench', open=['bottom']),
                   box('leg_e', (w - 0.18, -0.02, -d + 0.04), (w - 0.08, 0.34, d - 0.04), 'bench', open=['bottom'])], 60)


def kiosk():
    w, d, t = KIOSK_W / 2, KIOSK_D / 2, KIOSK_T
    return recipe('pf_kiosk', {'hide': 'hide', 'cut': 'cut', 'hide_floor': 'hide_floor'},
                  [box('front', (-w, -0.02, -d), (w, CUT, -d + t), 'hide', open=['bottom'], faces={'top': 'cut'}),
                   box('side_w', (-w, -0.02, -d + t), (-w + t, CUT, d), 'hide', open=['bottom', 'back'], faces={'top': 'cut'}),
                   box('side_e', (w - t, -0.02, -d + t), (w, CUT, d), 'hide', open=['bottom', 'back'], faces={'top': 'cut'}),
                   box('mat', (-w + t - 0.01, -0.02, -d + t - 0.01), (w - t + 0.01, 0.03, d - 0.05), 'hide_floor', open=['bottom'])], 80)


def shell_col():
    """The station box's collision: floors and walls only, walls without tops (nobody stands on
    them), simpler than the drawn box (docs/WORLDKIT.md, "Collision")."""
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T
    zo0, zo1 = Z_FRONT - WALL_T, Z_BACK + WALL_T
    zc = Z_BACK + CUPBOARD_D
    cx0, cx1 = CUPBOARD_X
    wall_open = ['bottom', 'top']
    n = [box('slab', (xo0, Y_SLAB, zo0), (xo1, Y_BED, zc + WALL_T), 'm'),
         box('platform', (X0, Y_BED, PLAT[0]), (X1, 0, PLAT[1]), 'm', open=['bottom', 'left', 'right']),
         # The walkway in three, so that its edges meet the cupboard's floor end to end.
         box('walkway_w', (X0, Y_BED, WALK[0]), (cx0, 0, Z_BACK + 0.02), 'm', open=['bottom', 'left', 'right', 'front']),
         box('walkway_m', (cx0, Y_BED, WALK[0]), (cx1, 0, Z_BACK + 0.02), 'm', open=['bottom', 'left', 'right', 'front']),
         box('walkway_e', (cx1, Y_BED, WALK[0]), (X1, 0, Z_BACK + 0.02), 'm', open=['bottom', 'left', 'right', 'front']),
         box('cupboard_floor', (cx0, Y_BED, Z_BACK + 0.02), (cx1, 0, zc), 'm', open=['bottom', 'left', 'right', 'back', 'front']),
         box('front_wall', (xo0, Y_BED, zo0), (xo1, CUT, Z_FRONT), 'm', open=wall_open),
         box('back_wall_w', (xo0, Y_BED, Z_BACK), (cx0, H, zo1), 'm', open=wall_open),
         box('back_wall_e', (cx1, Y_BED, Z_BACK), (xo1, H, zo1), 'm', open=wall_open),
         box('cupboard_back', (cx0 - WALL_T, Y_BED, zc), (cx1 + WALL_T, H, zc + WALL_T), 'm', open=wall_open),
         box('cupboard_w', (cx0 - WALL_T, Y_BED, zo1), (cx0, H, zc), 'm', open=wall_open + ['back', 'front']),
         box('cupboard_e', (cx1, Y_BED, zo1), (cx1 + WALL_T, H, zc), 'm', open=wall_open + ['back', 'front'])]
    for side, (wx0, wx1) in (('w', (xo0, X0)), ('e', (X1, xo1))):
        n.append(box(f'end_{side}_plat', (wx0, Y_BED, PLAT[0]), (wx1, H, PLAT[1]), 'm', open=wall_open))
        n.append(box(f'end_{side}_walk', (wx0, Y_BED, WALK[0]), (wx1, H, Z_BACK), 'm', open=wall_open + ['front']))
    stair = next(x for x in shell()['nodes'] if x['id'] == 'stair')
    stair = dict(stair, material='m')
    stair.pop('faces', None)
    n.append(stair)
    rec = recipe('pf_shell_col', {'m': '#808080'}, n, 400)
    rec.pop('verification')
    return rec


def kiosk_col():
    w, d, t = KIOSK_W / 2, KIOSK_D / 2, KIOSK_T
    rec = recipe('pf_kiosk_col', {'m': '#808080'},
                 [box('front', (-w, -0.02, -d), (w, CUT, -d + t), 'm', open=['bottom', 'top']),
                  box('side_w', (-w, -0.02, -d + t), (-w + t, CUT, d), 'm', open=['bottom', 'top', 'back']),
                  box('side_e', (w - t, -0.02, -d + t), (w, CUT, d), 'm', open=['bottom', 'top', 'back'])], 40)
    rec.pop('verification')
    return rec


# ---- the world

def wall(id, lo, hi, blocks=True, solid=True, h=None):
    """A wall entity: a box in plan from (x0, z0) to (x1, z1)."""
    (x0, z0), (x1, z1) = lo, hi
    e = {'id': id, 'type': 'wall', 'position': [r((x0 + x1) / 2), 0, r((z0 + z1) / 2)],
         'params': {'size': [r(x1 - x0), r(h if h is not None else H), r(z1 - z0)]}}
    if not blocks:
        e['params']['blocks'] = False
    if not solid:
        e['params']['solid'] = False
    return e


def world():
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T
    zo0 = Z_FRONT - WALL_T
    zo1 = Z_BACK + WALL_T
    zc = Z_BACK + CUPBOARD_D
    placements = [{'id': 'shell', 'asset': 'pf_shell', 'position': [0, 0, 0], 'collision': 'pf_shell_col'}]
    for i, x in enumerate(PILLARS):
        placements.append({'id': f'pillar_{i + 1}', 'asset': 'pf_pillar', 'position': [x, 0, PLAT_Z],
                           'collision': 'self'})
    for i, (x, z) in enumerate(BENCHES):
        placements.append({'id': f'bench_{i + 1}', 'asset': 'pf_bench', 'position': [x, 0, z], 'collision': 'self'})
    placements.append({'id': 'kiosk', 'asset': 'pf_kiosk', 'position': [KIOSK[0], 0, KIOSK[1]], 'collision': 'pf_kiosk_col'})

    ents = []
    ents.append({'id': 'room', 'type': 'room', 'position': [r((xo0 + xo1) / 2), 0, r((zo0 + zc + WALL_T) / 2)],
                 'params': {'entry': 'spawn', 'exit': 'staff_door', 'first': True, 'toys': TOYS, 'bells': BELLS,
                            'size': [r(xo1 - xo0), H, r(zc + WALL_T - zo0)]}})
    ents.append({'id': 'spawn', 'type': 'spawn', 'position': [SPAWN[0], 0, SPAWN[1]], 'params': {'yaw': SPAWN[2]}})
    ents.append({'id': 'staff_door', 'type': 'exit',
                 'position': [r((DOOR_X[0] + DOOR_X[1]) / 2), 0, r(Z_BACK - 0.35)],
                 'params': {'size': [r(DOOR_X[1] - DOOR_X[0]), DOOR_H, 0.7]}})

    def patrol(gid, p):
        first = None
        names = [w[0] for w in p['route']]
        for k, (wid, (x, z), wait, look) in enumerate(p['route']):
            ents.append({'id': wid, 'type': 'waypoint', 'position': [r(x), 0, r(z)],
                         'params': {'next': names[(k + 1) % len(names)], 'wait': wait, 'look': look}})
        # yaw: he starts facing his first waypoint (the runtime starts a patrol at the entity's yaw)
        (fx, fz) = p['route'][0][1]
        yaw = math.degrees(math.atan2(fx - p['start'][0], fz - p['start'][1])) % 360
        ents.append({'id': gid, 'type': 'guard', 'position': [r(p['start'][0]), 0, r(p['start'][1])], 'yaw': r(yaw, 2),
                     'params': {'kind': 'patrol', 'route': names[0], 'speed': p['speed'],
                                'sight': p['sight'], 'fov': p['fov'], 'hear': p['hear']}})

    patrol('guard_platform', PATROL_P)
    patrol('guard_walkway', PATROL_W)
    ents.append({'id': 'guard_kiosk', 'type': 'guard', 'position': [POSTED['pos'][0], 0, POSTED['pos'][2]],
                 'params': {'kind': 'posted', **{k: POSTED[k] for k in ('look_a', 'look_b', 'hold', 'turn', 'phase',
                                                                       'sight', 'fov', 'hear')}}})
    ents.append({'id': 'camera_far', 'type': 'guard', 'position': list(CAMERA['pos']),
                 'params': {'kind': 'camera', **{k: CAMERA[k] for k in ('look_a', 'look_b', 'hold', 'turn', 'phase',
                                                                       'sight', 'fov')}}})
    for tid, path, t in (('train_a', 'track_a', TRAIN_A), ('train_b', 'track_b', TRAIN_B)):
        # The entity stands where the train's head stops (the game moves it).
        z = TRACK_A_Z if path == 'track_a' else TRACK_B_Z
        x = (X0 - WALL_T) + t['stop'] if path == 'track_a' else (X1 + WALL_T) - t['stop']
        ents.append({'id': tid, 'type': 'train', 'position': [r(x), 0, r(z)],
                     'params': {'path': path, **{k: (r(v) if isinstance(v, float) else v) for k, v in t.items()}}})
    ents.append({'id': 'hide_kiosk', 'type': 'hide_spot', 'position': [KIOSK[0], 0, r(KIOSK[1] + KIOSK_T / 2)],
                 'params': {'size': [r(KIOSK_W - 2 * KIOSK_T), 1.7, r(KIOSK_D - KIOSK_T)]}})
    ents.append({'id': 'hide_cupboard', 'type': 'hide_spot',
                 'position': [r(sum(CUPBOARD_X) / 2), 0, r(Z_BACK + CUPBOARD_D / 2)],
                 'params': {'size': [r(CUPBOARD_X[1] - CUPBOARD_X[0]), 1.7, CUPBOARD_D]}})
    for fid, (x, z) in FRAGILE:
        ents.append({'id': fid, 'type': 'fragile', 'position': [x, 0, z], 'params': {'radius': 0.35, 'noise': 8}})

    # The wall map, from the same numbers as the boxes.
    walls = [
        wall('wall_front', (xo0, zo0), (xo1, Z_FRONT), h=CUT),
        wall('wall_back_w', (xo0, Z_BACK), (CUPBOARD_X[0], zo1)),
        wall('wall_back_e', (CUPBOARD_X[1], Z_BACK), (xo1, zo1)),
        wall('wall_cupboard_back', (CUPBOARD_X[0] - WALL_T, zc), (CUPBOARD_X[1] + WALL_T, zc + WALL_T)),
        wall('wall_cupboard_w', (CUPBOARD_X[0] - WALL_T, zo1), (CUPBOARD_X[0], zc)),
        wall('wall_cupboard_e', (CUPBOARD_X[1], zo1), (CUPBOARD_X[1] + WALL_T, zc)),
        wall('wall_end_w', (xo0, Z_FRONT), (X0, Z_BACK)),
        wall('wall_end_e', (X1, Z_FRONT), (xo1, Z_BACK)),
        wall('wall_stair', (STAIR_X[0], STAIR_Z[0]), (STAIR_X[1], STAIR_Z[1]), h=STAIR_TOP),
    ]
    s = PILLAR_S / 2
    for i, x in enumerate(PILLARS):
        walls.append(wall(f'wall_pillar_{i + 1}', (x - s, PLAT_Z - s), (x + s, PLAT_Z + s), h=CUT))
    for i, (x, z) in enumerate(BENCHES):
        walls.append(wall(f'wall_bench_{i + 1}', (x - BENCH_W / 2, z - BENCH_D / 2), (x + BENCH_W / 2, z + BENCH_D / 2),
                          blocks=False, h=0.45))
    kx, kz = KIOSK
    w, d, t = KIOSK_W / 2, KIOSK_D / 2, KIOSK_T
    walls += [wall('wall_kiosk_front', (kx - w, kz - d), (kx + w, kz - d + t), h=CUT),
              wall('wall_kiosk_w', (kx - w, kz - d + t), (kx - w + t, kz + d), h=CUT),
              wall('wall_kiosk_e', (kx + w - t, kz - d + t), (kx + w, kz + d), h=CUT)]
    ents += walls

    paths = {
        'track_a': {'points': [[r(X0 - WALL_T), 0, r(TRACK_A_Z)], [r(X1 + WALL_T), 0, r(TRACK_A_Z)]],
                    'raised': True},
        'track_b': {'points': [[r(X1 + WALL_T), 0, r(TRACK_B_Z)], [r(X0 - WALL_T), 0, r(TRACK_B_Z)]],
                    'raised': True},
    }
    return {
        'format': 'mei-world', 'version': 1, 'name': 'platform',
        'game': '../../dorobo.game.mochi', 'assets': 'assets',
        'grid': {'cell_size': 32},
        'collision': {'surfaces': {'default': 0}},
        'regions': {'station': {}},
        'paths': paths,
        'runtime': {'depth': True, 'perspective': True},
        # The game's camera (dr_view.akr: 60 degrees down, 28.2 m from its target) over the room's
        # west end, middle and east end. The checker draws them at its own field of view, wider
        # than the game's 20 degrees, so they see more of the room than the game does.
        'verification': {'vantage_points': [
            {'name': f'game_{k}', 'position': [x, r(0.6 + 28.166 * math.sin(math.radians(60))),
                                               r(6.0 - 28.166 * math.cos(math.radians(60)))],
             'yaw': 0, 'pitch': -60} for k, x in (('west', 7.5), ('middle', 16.0), ('east', 24.5))]},
        'cells': [{'id': 'platform', 'at': [0, 0], 'region': 'station',
                   'placements': placements, 'entities': ents}],
    }


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=1) + '\n'
    if not path.exists() or path.read_text() != text:
        path.write_text(text)
        print('wrote', path.relative_to(HERE))


def main():
    write(ASSETS / 'pf_shell.asset.json', shell())
    write(ASSETS / 'pf_pillar.asset.json', pillar())
    write(ASSETS / 'pf_bench.asset.json', bench())
    write(ASSETS / 'pf_kiosk.asset.json', kiosk())
    write(ASSETS / 'pf_shell_col.asset.json', shell_col())
    write(ASSETS / 'pf_kiosk_col.asset.json', kiosk_col())
    write(HERE / 'platform.world.json', world())


if __name__ == '__main__':
    main()
