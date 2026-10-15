#!/usr/bin/env python3
"""Level 1, room 1: the last train (greybox). Writes the room's recipes, placements and play file
beside itself (levels/greybox.py says what each is); PLAN.md is the room's floor plan.

    python3 carts/afterhours/rooms/arrival/make_arrival.py

The end of a side platform, deep under the complex. The thief steps off the last train, which
pulls out behind him; the stair up to the ticket gates is at the platform's east end, and a
station guard stands beside it, looking up the platform, then turning to the timetable on the
wall. Teaches: what a cone is, and timing it.

The room's frame: x right, z away from the camera, the platform's top y = 0, the origin in the
middle of the room's floor.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
from greybox import (CUT, WALL_H, WALL_T, box, recipe, stair_profile, wall, posted, write_room, r)  # noqa: E402

NAME = 'arrival'
P = 'r1_'                      # entity ids are world-wide: every id of this room starts so

# ---- the plan
X0, X1 = -6.5, 6.5             # inner faces of the end walls
Z_FRONT = -4.25                # front wall's inner face (cut at 1 m)
PLAT = (-4.25, 1.1)            # the platform
TRACK = (1.1, 3.5)             # the track (train width 2.4)
Z_BACK = 3.5                   # back wall's inner face
Y_BED = -1.1
TRACK_Z = (TRACK[0] + TRACK[1]) / 2
STAIR_X = (3.6, X1)            # the stair up to the gates, rising east
STAIR_Z = (-1.3, 0.9)
STAIR_STEPS = 11
BENCHES = [(-3.0, -2.6), (0.4, -2.6)]
BENCH_W, BENCH_D = 1.8, 0.45
PILLAR = (-5.0, -1.2)          # one pillar, west, out of the guard's reach
PILLAR_S = 0.5

# Low props of the dressed room (dress_arrival.py), for the wall map: x0, z0, x1, z1, height
DRESSED_LOW = {'wall_bins': (-1.95, -4.25, -0.85, -3.95, 0.9),
               'wall_timetable': (5.4, -4.25, 6.2, -4.17, 1.0),
               'wall_ashtray': (-6.1, -4.1, -5.8, -3.8, 0.9)}

SPAWN = (-3.08, 0.6, 180)      # off the train's first door, facing the camera
EXIT = dict(pos=(3.2, -0.2), size=(0.8, 2.0, 2.2))     # the stair's foot
GUARD = dict(pos=(5.5, -3.2), look_a=300, look_b=165, hold=240, turn=90, sight=5.5, fov=60)
# The last train, standing with its doors just shut at clock 0; it pulls out east and does not
# come back.
TRAIN = dict(period=7200, offset=-540, arrive=240, stop=11.75, dwell=300, leave=360,
             cars=2, car_length=10, width=TRACK[1] - TRACK[0], doors=3, door_width=1.3, sides='left')


def shell():
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T
    zo0, zo1 = Z_FRONT - WALL_T, Z_BACK + WALL_T
    pz = PLAT[1] - PLAT[0]
    n = [
        box('slab', (xo0, -1.4, zo0), (xo1, Y_BED, zo1), 'slab',
            faces={'top': 'bed', 'back': 'cut', 'left': 'cut', 'right': 'cut'}),
        box('front_wall', (xo0, Y_BED, zo0), (xo1, CUT, Z_FRONT), 'wall', open=['bottom'],
            faces={'top': 'cut', 'back': 'cut'}),
        box('platform', (X0, Y_BED, PLAT[0]), (X1, 0, PLAT[1]), 'floor_dark',
            open=['bottom', 'left', 'right', 'back'], faces={'top': 'floor'},
            decals=[{'id': 'edge', 'face': 'top', 'material': 'edge_line',
                     'size': [r(X1 - X0 - 0.1), 0.3], 'at': [0, r(pz / 2 - 0.65)]}]),
        box('back_wall', (xo0, Y_BED, Z_BACK), (xo1, WALL_H, zo1), 'wall', open=['bottom'],
            faces={'top': 'cut'},
            decals=[{'id': 'timetable', 'face': 'back', 'material': 'door_light', 'size': [1.2, 0.5],
                     'at': [5.0, 1.0]}]),
        box('end_w', (xo0, Y_BED, PLAT[0]), (X0, WALL_H, PLAT[1]), 'wall', open=['bottom', 'back'], faces={'top': 'cut'}),
        box('end_e', (X1, Y_BED, PLAT[0]), (xo1, WALL_H, PLAT[1]), 'wall', open=['bottom', 'back'], faces={'top': 'cut'}),
        box('lintel_w', (xo0, 2.2, TRACK[0]), (X0, WALL_H - 0.01, Z_BACK), 'wall', open=['back', 'front'],
            faces={'bottom': 'tunnel'}),
        box('lintel_e', (X1, 2.2, TRACK[0]), (xo1, WALL_H - 0.01, Z_BACK), 'wall', open=['back', 'front'],
            faces={'bottom': 'tunnel'}),
    ]
    for s, dz in (('l', -0.535), ('r', 0.535)):
        n.append(box(f'rail_{s}', (xo0, Y_BED - 0.01, TRACK_Z + dz - 0.035), (xo1, Y_BED + 0.16, TRACK_Z + dz + 0.035),
                     'rail', open=['bottom', 'left', 'right']))
    n.append({'id': 'stair', 'op': 'extrude', 'material': 'stair', 'depth': r(STAIR_Z[1] - STAIR_Z[0]),
              'points': stair_profile(STAIR_X[0], STAIR_X[1] + 0.02, STAIR_STEPS),
              'faces': {'front': 'stair_side', 'back': 'stair_side'},
              'transform': {'translate': [0, 0, r((STAIR_Z[0] + STAIR_Z[1]) / 2)]}})
    return recipe('r1_shell', n, 500)


def shell_col():
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T
    zo0, zo1 = Z_FRONT - WALL_T, Z_BACK + WALL_T
    op = ['bottom', 'top']
    stair = next(x for x in shell()['nodes'] if x['id'] == 'stair')
    n = [box('slab', (xo0, -1.4, zo0), (xo1, Y_BED, zo1), 'floor'),
         box('platform', (X0, Y_BED, PLAT[0]), (X1, 0, PLAT[1]), 'floor', open=['bottom', 'left', 'right', 'back']),
         box('front_wall', (xo0, Y_BED, zo0), (xo1, CUT, Z_FRONT), 'floor', open=op),
         box('back_wall', (xo0, Y_BED, Z_BACK), (xo1, WALL_H, zo1), 'floor', open=op),
         box('end_w', (xo0, Y_BED, PLAT[0]), (X0, WALL_H, PLAT[1]), 'floor', open=op + ['back']),
         box('end_e', (X1, Y_BED, PLAT[0]), (xo1, WALL_H, PLAT[1]), 'floor', open=op + ['back']),
         dict(stair, material='floor', faces={})]
    n[-1].pop('faces')
    return recipe('r1_shell_col', n, 300, collision=True)


def pillar():
    s = PILLAR_S / 2
    return recipe('r1_pillar', [box('pillar', (-s, -0.02, -s), (s, CUT, s), 'pillar', open=['bottom'],
                                    faces={'top': 'cut'})], 20)


def bench():
    w, d = BENCH_W / 2, BENCH_D / 2
    return recipe('r1_bench', [box('seat', (-w, 0.33, -d), (w, 0.45, d), 'bench'),
                               box('leg_w', (-w + 0.08, -0.02, -d + 0.04), (-w + 0.18, 0.34, d - 0.04), 'bench', open=['bottom']),
                               box('leg_e', (w - 0.18, -0.02, -d + 0.04), (w - 0.08, 0.34, d - 0.04), 'bench', open=['bottom'])], 40)


def play():
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T
    zo0, zo1 = Z_FRONT - WALL_T, Z_BACK + WALL_T
    ents = [
        {'id': P + 'room', 'type': 'room', 'position': [0, 0, r((zo0 + zo1) / 2)],
         'params': {'entry': P + 'spawn', 'exit': P + 'exit', 'size': [r(xo1 - xo0), WALL_H, r(zo1 - zo0)]}},
        {'id': P + 'spawn', 'type': 'spawn', 'position': [SPAWN[0], 0, SPAWN[1]], 'params': {'yaw': SPAWN[2]}},
        {'id': P + 'exit', 'type': 'exit', 'position': [EXIT['pos'][0], 0, EXIT['pos'][1]],
         'params': {'size': list(EXIT['size'])}},
        posted(P + 'guard', GUARD['pos'], GUARD['look_a'], GUARD['look_b'], GUARD['hold'], GUARD['turn'],
               GUARD['sight'], GUARD['fov']),
        {'id': P + 'train', 'type': 'train', 'position': [r(xo0 + TRAIN['stop']), 0, r(TRACK_Z)],
         'params': dict({'path': P + 'track'}, **TRAIN)},
        wall(P + 'wall_front', xo0, zo0, xo1, Z_FRONT, h=CUT),
        wall(P + 'wall_back', xo0, Z_BACK, xo1, zo1),
        wall(P + 'wall_end_w', xo0, Z_FRONT, X0, Z_BACK),
        wall(P + 'wall_end_e', X1, Z_FRONT, xo1, Z_BACK),
        # the stair: solid but for its foot, where the exit is; it stands above the cut
        wall(P + 'wall_stair', STAIR_X[0] + 0.3, STAIR_Z[0], STAIR_X[1], STAIR_Z[1], h=2.2),
        wall(P + 'wall_pillar', PILLAR[0] - PILLAR_S / 2, PILLAR[1] - PILLAR_S / 2, PILLAR[0] + PILLAR_S / 2,
             PILLAR[1] + PILLAR_S / 2, h=CUT),
    ]
    for i, (x, z) in enumerate(BENCHES):
        ents.append(wall(f'{P}wall_bench_{i + 1}', x - BENCH_W / 2, z - BENCH_D / 2, x + BENCH_W / 2, z + BENCH_D / 2,
                         blocks=False, h=0.82))      # the dressed seats' moulded backs reach 0.82 m
    # the dressed room's low props by the front wall (rooms/arrival/NOTES.md): they stop the
    # thief, cones pass over them
    for pid, (x0, z0, x1, z1, h) in DRESSED_LOW.items():
        ents.append(wall(P + pid, x0, z0, x1, z1, blocks=False, h=h))
    paths = {P + 'track': {'points': [[r(xo0), 0, r(TRACK_Z)], [r(xo1), 0, r(TRACK_Z)]], 'raised': True}}
    return {'entities': ents, 'paths': paths}


def main():
    placements = [{'id': P + 'shell', 'asset': 'r1_shell', 'position': [0, 0, 0], 'collision': 'r1_shell_col'},
                  {'id': P + 'pillar', 'asset': 'r1_pillar', 'position': [PILLAR[0], 0, PILLAR[1]], 'collision': 'self'}]
    for i, (x, z) in enumerate(BENCHES):
        placements.append({'id': f'{P}bench_{i + 1}', 'asset': 'r1_bench', 'position': [x, 0, z], 'collision': 'self'})
    write_room(HERE, NAME, [shell(), shell_col(), pillar(), bench()], placements, play())


if __name__ == '__main__':
    main()
