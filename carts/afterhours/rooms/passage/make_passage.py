#!/usr/bin/env python3
"""Level 1, room 3: the underground passage (greybox). Writes the room's recipes, placements and
play file beside itself (levels/greybox.py says what each is); PLAN.md is the room's floor plan.

    python3 carts/afterhours/rooms/passage/make_passage.py

A long tiled passage under the street, its shops' shutters down along the back wall, a row of
pillars down its middle and another along the front. A security camera at the far end sweeps the
whole length. Teaches: pillars cast sight shadows; go from shadow to shadow as the sweep passes.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
from greybox import (CUT, WALL_H, WALL_T, box, recipe, wall, posted, write_room, r)  # noqa: E402

NAME = 'passage'
P = 'r3_'

X0, X1 = -11.0, 11.0           # inner faces of the end walls (22 m: the camera pans)
Z0, Z1 = -3.4, 3.4             # inner faces of the front (cut at 1 m) and back walls
PILLARS = [(-6.5, 0.6), (-2.5, -1.4), (1.5, 0.6), (5.5, -1.4)]   # staggered: shadows to hop between
PILLAR_S = 0.8
SHUTTERS = [(-9.5, -5.5), (-4.5, -0.5), (0.5, 4.5)]   # shop fronts in the back wall, shutters down
MACHINES = [(-0.6, -3.4, 0.6, -2.9)]                    # a vending machine against the front wall (it glows)
ENTRY_DOOR = (-2.6, -0.6)      # the stair up from the gates, in the west wall: z from .. to
EXIT_DOOR = (-3.4, -1.6)       # the way on to the lobby: the east wall's front end, z from .. to

SPAWN = (-10.4, -1.6, 90)
EXIT = dict(pos=(10.7, -2.5), size=(0.6, 2.0, 1.8))
# The camera, high on the east wall at the back, sweeping the passage's length.
CAMERA = dict(pos=(10.85, 2.9), look_a=235, look_b=285, hold=60, turn=210, sight=13.0, fov=34, y=2.3)


def shell():
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T
    zo0, zo1 = Z0 - WALL_T, Z1 + WALL_T
    n = [
        box('slab', (xo0, -0.4, zo0), (xo1, 0, zo1), 'floor_dark', faces={'top': 'tile', 'back': 'cut'},
            open=['bottom', 'left', 'right', 'front']),
        box('front_wall', (xo0, 0, zo0), (xo1, CUT, Z0), 'wall', open=['bottom'], faces={'top': 'cut', 'back': 'cut'}),
        box('back_wall', (xo0, 0, Z1), (xo1, WALL_H, zo1), 'wall_light', open=['bottom'], faces={'top': 'cut'},
            decals=[{'id': f'shutter_{i}', 'face': 'back', 'material': 'shutter', 'size': [r(b - a), 1.9],
                     'at': [r((a + b) / 2), r(0.96 - WALL_H / 2)]} for i, (a, b) in enumerate(SHUTTERS)]),
        box('end_w_front', (xo0, 0, Z0), (X0, WALL_H, ENTRY_DOOR[0]), 'wall', open=['bottom', 'back'], faces={'top': 'cut'}),
        box('end_w_back', (xo0, 0, ENTRY_DOOR[1]), (X0, WALL_H, Z1), 'wall', open=['bottom', 'front'], faces={'top': 'cut'}),
        box('entry_lintel', (xo0, 2.1, ENTRY_DOOR[0]), (X0, WALL_H - 0.01, ENTRY_DOOR[1]), 'wall', open=['back', 'front']),
        box('end_e', (X1, 0, EXIT_DOOR[1]), (xo1, WALL_H, Z1), 'wall', open=['bottom', 'front'], faces={'top': 'cut'}),
        box('exit_lintel', (X1, 2.1, Z0), (xo1, WALL_H - 0.01, EXIT_DOOR[1]), 'wall', open=['back', 'front'],
            faces={'bottom': 'door_light'}),
    ]
    s = PILLAR_S / 2
    for i, (x, z) in enumerate(PILLARS):
        n.append(box(f'pillar_{i}', (x - s, -0.02, z - s), (x + s, CUT, z + s), 'pillar', open=['bottom'], faces={'top': 'cut'}))
    for i, (x0, z0, x1, z1) in enumerate(MACHINES):
        n.append(box(f'machine_{i}', (x0, 0, z0), (x1, CUT - 0.05, z1), 'machine', open=['bottom', 'back'],
                     faces={'top': 'cut', 'front': 'door_light'}))
    return recipe('r3_shell', n, 500)


def shell_col():
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T
    zo0, zo1 = Z0 - WALL_T, Z1 + WALL_T
    op = ['bottom', 'top']
    n = [box('slab', (xo0, -0.4, zo0), (xo1, 0, zo1), 'floor', open=['bottom', 'left', 'right', 'front', 'back']),
         box('front_wall', (xo0, 0, zo0), (xo1, CUT, Z0), 'floor', open=op),
         box('back_wall', (xo0, 0, Z1), (xo1, WALL_H, zo1), 'floor', open=op),
         box('end_w_front', (xo0, 0, Z0), (X0, WALL_H, ENTRY_DOOR[0]), 'floor', open=op + ['back']),
         box('end_w_back', (xo0, 0, ENTRY_DOOR[1]), (X0, WALL_H, Z1), 'floor', open=op + ['front']),
         box('end_e', (X1, 0, EXIT_DOOR[1]), (xo1, WALL_H, Z1), 'floor', open=op + ['front'])]
    return recipe('r3_shell_col', n, 200, collision=True)


def play():
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T
    zo0, zo1 = Z0 - WALL_T, Z1 + WALL_T
    ents = [
        {'id': P + 'room', 'type': 'room', 'position': [0, 0, 0],
         'params': {'entry': P + 'spawn', 'exit': P + 'exit', 'size': [r(xo1 - xo0), WALL_H, r(zo1 - zo0)]}},
        {'id': P + 'spawn', 'type': 'spawn', 'position': [SPAWN[0], 0, SPAWN[1]], 'params': {'yaw': SPAWN[2]}},
        {'id': P + 'exit', 'type': 'exit', 'position': [EXIT['pos'][0], 0, EXIT['pos'][1]], 'params': {'size': list(EXIT['size'])}},
        posted(P + 'camera', CAMERA['pos'], CAMERA['look_a'], CAMERA['look_b'], CAMERA['hold'], CAMERA['turn'],
               CAMERA['sight'], CAMERA['fov'], kind='camera', y=CAMERA['y']),
        wall(P + 'wall_front', xo0, zo0, xo1, Z0, h=CUT),
        wall(P + 'wall_back', xo0, Z1, xo1, zo1),
        wall(P + 'wall_end_w_front', xo0, Z0, X0, ENTRY_DOOR[0]),
        wall(P + 'wall_end_w_back', xo0, ENTRY_DOOR[1], X0, Z1),
        wall(P + 'wall_end_e', X1, EXIT_DOOR[1], xo1, Z1),
        # beyond the doorways: the stairs, closed to the thief
        wall(P + 'wall_entry_beyond', xo0 - 0.3, ENTRY_DOOR[0], xo0, ENTRY_DOOR[1]),
        wall(P + 'wall_exit_beyond', xo1, EXIT_DOOR[0], xo1 + 0.3, EXIT_DOOR[1]),
    ]
    s = PILLAR_S / 2
    for i, (x, z) in enumerate(PILLARS):
        ents.append(wall(f'{P}wall_pillar_{i}', x - s, z - s, x + s, z + s, h=CUT))
    for i, (x0, z0, x1, z1) in enumerate(MACHINES):
        ents.append(wall(f'{P}wall_machine_{i}', x0, z0, x1, z1, h=CUT))
    return {'entities': ents, 'paths': {}}


def main():
    placements = [{'id': P + 'shell', 'asset': 'r3_shell', 'position': [0, 0, 0], 'collision': 'r3_shell_col'}]
    write_room(HERE, NAME, [shell(), shell_col()], placements, play())


if __name__ == '__main__':
    main()
