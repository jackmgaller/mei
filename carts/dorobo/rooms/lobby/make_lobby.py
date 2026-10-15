#!/usr/bin/env python3
"""Level 1, room 4: the office tower's lobby (greybox). Writes the room's recipes, placements and
play file beside itself (levels/greybox.py says what each is); PLAN.md is the room's floor plan.

    python3 carts/dorobo/rooms/lobby/make_lobby.py

The ground floor of the tower above the passage: a reception desk in the middle, planters, the
lifts (shut for the night) in the east wall, and a stopped escalator up along the back wall, the
only way up. Two night guards walk routes that cross: one along the back in front of the
escalator, one up and down the west side. Teaches: two routes crossing; find the gap between them.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
from greybox import (CUT, WALL_H, WALL_T, box, recipe, wall, patrol, stair_profile, write_room, r)  # noqa: E402

NAME = 'lobby'
P = 'r4_'

X0, X1 = -7.0, 7.0
Z0, Z1 = -4.75, 4.75
DESK = (-1.6, -0.5, 1.6, 0.4)          # the reception desk (blocks sight: a counter with screens)
PLANTERS = [(-5.4, 0.6), (3.6, -2.2)]  # 1 m square, cut at 1 m (block sight)
PLANTER_S = 1.0
ESC = (1.0, 3.5, X1, Z1)               # the escalator: x from its foot to the east wall, z its width
ESC_STEPS = 12
LIFTS = [(-1.0, 1.0)]                  # the lifts' doors in the east wall, z from .. to (decals)
ENTRY_DOOR = (-4.5, -2.9)              # from the passage, in the west wall: z from .. to

SPAWN = (-6.4, -3.7, 90)
EXIT = dict(pos=(0.55, 4.12), size=(0.7, 2.0, 1.1))   # the escalator's foot
# One guard walks the back of the lobby, in front of the escalator; the other walks the west side
# from the front doors to the back. Their routes cross by the west planter.
GUARD_BACK = dict(start=(3.8, 2.6), speed=0.8, sight=4.5, fov=60, turn_rate=180,
                  route=[('r4_wp_back_w', (-2.6, 2.6), 120, 260),
                         ('r4_wp_back_e', (3.8, 2.6), 120, 80)])
GUARD_WEST = dict(start=(-3.2, 0.4), speed=0.8, sight=4.5, fov=60, turn_rate=180,
                  route=[('r4_wp_west_s', (-3.2, -3.8), 60, 170),
                         ('r4_wp_west_n', (-3.2, 3.6), 60, 10)])


def shell():
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T
    zo0, zo1 = Z0 - WALL_T, Z1 + WALL_T
    n = [
        box('slab', (xo0, -0.4, zo0), (xo1, 0, zo1), 'floor_dark', faces={'top': 'tile', 'back': 'cut'},
            open=['bottom', 'left', 'right', 'front']),
        box('front_wall', (xo0, 0, zo0), (xo1, CUT, Z0), 'wall', open=['bottom'], faces={'top': 'cut', 'back': 'cut'}),
        box('back_wall', (xo0, 0, Z1), (xo1, WALL_H, zo1), 'wall_light', open=['bottom'], faces={'top': 'cut'}),
        box('end_w_front', (xo0, 0, Z0), (X0, WALL_H, ENTRY_DOOR[0]), 'wall', open=['bottom', 'back'], faces={'top': 'cut'}),
        box('end_w_back', (xo0, 0, ENTRY_DOOR[1]), (X0, WALL_H, Z1), 'wall', open=['bottom', 'front'], faces={'top': 'cut'}),
        box('entry_lintel', (xo0, 2.1, ENTRY_DOOR[0]), (X0, WALL_H - 0.01, ENTRY_DOOR[1]), 'wall', open=['back', 'front']),
        box('end_e', (X1, 0, Z0), (xo1, WALL_H, Z1), 'wall_light', open=['bottom', 'back', 'front'], faces={'top': 'cut'},
            decals=[{'id': f'lift_{i}', 'face': 'left', 'material': 'lift', 'size': [r(b - a), 2.0],
                     'at': [r(-(a + b) / 2), r(1.0 - WALL_H / 2 + 0.01)]} for i, (a, b) in enumerate(LIFTS)]),
        box('desk', (DESK[0], 0, DESK[1]), (DESK[2], CUT, DESK[3]), 'desk', open=['bottom'], faces={'top': 'cut'}),
    ]
    s = PLANTER_S / 2
    for i, (x, z) in enumerate(PLANTERS):
        n.append(box(f'planter_{i}', (x - s, 0, z - s), (x + s, CUT, z + s), 'plant', open=['bottom'], faces={'top': 'cut'}))
    ex0, ez0, ex1, ez1 = ESC
    n.append({'id': 'escalator', 'op': 'extrude', 'material': 'escalator', 'depth': r(ez1 - ez0 - 0.3),
              'points': stair_profile(ex0, ex1 + 0.03, ESC_STEPS, rise=0.19),
              'faces': {'front': 'escalator_side', 'back': 'escalator_side'},
              'transform': {'translate': [0, 0, r((ez0 + ez1) / 2)]}})
    n.append(box('balustrade', (ex0, 0, ez0), (ex1, CUT, ez0 + 0.13), 'escalator_side', open=['bottom', 'right'],
                 faces={'top': 'cut'}))
    return recipe('r4_shell', n, 500)


def shell_col():
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T
    zo0, zo1 = Z0 - WALL_T, Z1 + WALL_T
    op = ['bottom', 'top']
    n = [box('slab', (xo0, -0.4, zo0), (xo1, 0, zo1), 'floor', open=['bottom', 'left', 'right', 'front', 'back']),
         box('front_wall', (xo0, 0, zo0), (xo1, CUT, Z0), 'floor', open=op),
         box('back_wall', (xo0, 0, Z1), (xo1, WALL_H, zo1), 'floor', open=op),
         box('end_w_front', (xo0, 0, Z0), (X0, WALL_H, ENTRY_DOOR[0]), 'floor', open=op + ['back']),
         box('end_w_back', (xo0, 0, ENTRY_DOOR[1]), (X0, WALL_H, Z1), 'floor', open=op + ['front']),
         box('end_e', (X1, 0, Z0), (xo1, WALL_H, Z1), 'floor', open=op + ['back', 'front'])]
    esc = dict(next(x for x in shell()['nodes'] if x['id'] == 'escalator'), material='floor')
    esc.pop('faces')
    n.append(esc)
    return recipe('r4_shell_col', n, 200, collision=True)


def play():
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T
    zo0, zo1 = Z0 - WALL_T, Z1 + WALL_T
    ex0, ez0, ex1, ez1 = ESC
    ents = [
        {'id': P + 'room', 'type': 'room', 'position': [0, 0, 0],
         'params': {'entry': P + 'spawn', 'exit': P + 'exit', 'size': [r(xo1 - xo0), WALL_H, r(zo1 - zo0)]}},
        {'id': P + 'spawn', 'type': 'spawn', 'position': [SPAWN[0], 0, SPAWN[1]], 'params': {'yaw': SPAWN[2]}},
        {'id': P + 'exit', 'type': 'exit', 'position': [EXIT['pos'][0], 0, EXIT['pos'][1]], 'params': {'size': list(EXIT['size'])}},
        wall(P + 'wall_front', xo0, zo0, xo1, Z0, h=CUT),
        wall(P + 'wall_back', xo0, Z1, xo1, zo1),
        wall(P + 'wall_end_w_front', xo0, Z0, X0, ENTRY_DOOR[0]),
        wall(P + 'wall_end_w_back', xo0, ENTRY_DOOR[1], X0, Z1),
        wall(P + 'wall_entry_beyond', xo0 - 0.3, ENTRY_DOOR[0], xo0, ENTRY_DOOR[1]),
        wall(P + 'wall_end_e', X1, Z0, xo1, Z1),
        wall(P + 'wall_desk', DESK[0], DESK[1], DESK[2], DESK[3], h=CUT),
        # the escalator: its balustrade blocks; the steps above its foot are out of bounds
        wall(P + 'wall_balustrade', ex0, ez0, ex1, ez0 + 0.13, h=CUT),
        wall(P + 'wall_escalator', ex0 + 0.6, ez0 + 0.13, ex1, ez1, h=WALL_H),
    ]
    s = PLANTER_S / 2
    for i, (x, z) in enumerate(PLANTERS):
        ents.append(wall(f'{P}wall_planter_{i}', x - s, z - s, x + s, z + s, h=CUT))
    for g, gid in ((GUARD_BACK, 'guard_back'), (GUARD_WEST, 'guard_west')):
        ents += patrol(P + gid, g['start'], g['route'], g['speed'], g['sight'], g['fov'], turn_rate=g['turn_rate'])
    return {'entities': ents, 'paths': {}}


def main():
    placements = [{'id': P + 'shell', 'asset': 'r4_shell', 'position': [0, 0, 0], 'collision': 'r4_shell_col'}]
    write_room(HERE, NAME, [shell(), shell_col()], placements, play())


if __name__ == '__main__':
    main()
