#!/usr/bin/env python3
"""Level 1, room 2: the ticket gates (greybox). Writes the room's recipes, placements and play file
beside itself (levels/greybox.py says what each is); PLAN.md is the room's floor plan.

    python3 carts/dorobo/rooms/gates/make_gates.py

The concourse at the top of the platform's stair: a line of ticket gates across it, the station
office with its window at the back, coin lockers, and the way up to the underground passage on
the far side of the gates. One patrol guard comes out of the office, through the gates to the
stair side, round by the lockers and back. Teaches: hiding (A in the lockers' alcove).

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
from greybox import (CUT, WALL_H, WALL_T, box, recipe, wall, patrol, write_room, r)  # noqa: E402

NAME = 'gates'
P = 'r2_'

X0, X1 = -6.5, 6.5             # inner faces of the end walls
Z0, Z1 = -4.25, 4.25           # inner faces of the front (cut at 1 m) and back walls
GATE_X = (-0.3, 0.3)           # the gate line: cabinets 0.6 long, 0.25 wide, aisles 0.95
GATE_Z = [-3.85, -2.65, -1.45, -0.25, 0.95]     # the cabinets' middles; aisles between them
GATE_W = 0.25
OFFICE = (-1.6, 2.15, 1.6, Z1)  # the office: x0, z0, x1, z1 (its front is the window, glass)
OFFICE_DOOR = (0.6, 1.3)       # the office door in its front wall: x from .. to
LOCKERS = (-6.5, 3.35, -2.6, Z1)     # coin lockers against the back wall
ALCOVE = (-5.0, -4.0)          # the alcove in the lockers (x from .. to): a hiding place
STAIRWELL = (-6.5, -4.25, -4.3, -1.6)   # the stair down to the platform: a railed hole
RAIL_OUT = 0.12                          # the dressed railings stand this far outside it (NOTES.md)
MACHINES = (-3.2, -4.25, -1.4, -3.75)   # ticket machines against the front wall (low)
EXIT_DOOR = (-3.6, -1.6)       # the way up to the passage, in the east wall: z from .. to

SPAWN = (-3.6, -2.9, 90)       # the stair's head, facing the gates
GUARD = dict(start=(2.4, 0.4), speed=0.9, sight=4.5, fov=60, turn_rate=180,
             route=[('r2_wp_aisle_e', (2.4, -2.05), 0, 270),      # south, then west through an aisle
                    ('r2_wp_aisle_w', (-2.6, -2.05), 30, 270),    # a look at the stair
                    ('r2_wp_lockers', (-3.2, 2.3), 90, 300),      # a look at the lockers
                    ('r2_wp_back_w', (-2.6, 0.35), 0, 90),
                    ('r2_wp_back_e', (2.4, 0.35), 0, 90),         # east through another aisle
                    ('r2_wp_office', (0.95, 1.75), 120, 180)])      # at the office door, looking out
EXIT = dict(pos=(6.2, -2.6), size=(0.6, 2.0, 2.0))


def shell():
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T
    zo0, zo1 = Z0 - WALL_T, Z1 + WALL_T
    n = [
        box('slab', (xo0, -0.4, zo0), (xo1, 0, zo1), 'floor_dark', faces={'top': 'tile', 'back': 'cut'},
            open=['bottom', 'left', 'right', 'front'],
            decals=[{'id': 'well', 'face': 'top', 'material': 'tunnel',
                     'size': [r(STAIRWELL[2] - STAIRWELL[0] - 0.08), r(STAIRWELL[3] - STAIRWELL[1] - 0.08)],
                     'at': [r((STAIRWELL[0] + STAIRWELL[2]) / 2 - 0.04), r((STAIRWELL[1] + STAIRWELL[3]) / 2 - 0.04)]},
                    {'id': 'alcove', 'face': 'top', 'material': 'hide_floor',
                     'size': [r(ALCOVE[1] - ALCOVE[0] - 0.02), r(LOCKERS[3] - LOCKERS[1] - 0.02)],
                     'at': [r(sum(ALCOVE) / 2), r((LOCKERS[1] + LOCKERS[3]) / 2)]}]),
        box('front_wall', (xo0, 0, zo0), (xo1, CUT, Z0), 'wall', open=['bottom'], faces={'top': 'cut', 'back': 'cut'}),
        box('back_wall', (xo0, -0.02, Z1), (xo1, WALL_H, zo1), 'wall', open=['bottom'], faces={'top': 'cut'}),
        box('end_w', (xo0, -0.02, Z0), (X0, WALL_H, Z1), 'wall', open=['bottom', 'back', 'front'], faces={'top': 'cut'}),
        box('end_e_front', (X1, -0.02, Z0), (xo1, WALL_H, EXIT_DOOR[0]), 'wall', open=['bottom', 'back'], faces={'top': 'cut'}),
        box('end_e_back', (X1, -0.02, EXIT_DOOR[1]), (xo1, WALL_H, Z1), 'wall', open=['bottom', 'front'], faces={'top': 'cut'}),
        box('exit_lintel', (X1, 2.1, EXIT_DOOR[0]), (xo1, WALL_H - 0.01, EXIT_DOOR[1]), 'wall', open=['back', 'front'],
            faces={'bottom': 'door_light'}),
        box('rail_n', (STAIRWELL[0] + 0.01, -0.02, STAIRWELL[3] - 0.06), (STAIRWELL[2], CUT, STAIRWELL[3]), 'gate',
            open=['bottom', 'left'], faces={'top': 'gate_top'}),
        box('rail_e', (STAIRWELL[2] - 0.06, -0.02, STAIRWELL[1] + 0.01), (STAIRWELL[2], CUT, STAIRWELL[3] - 0.06), 'gate',
            open=['bottom', 'front', 'back'], faces={'top': 'gate_top'}),
        box('machines', (MACHINES[0], -0.02, MACHINES[1]), (MACHINES[2], 0.95, MACHINES[3]), 'machine',
            open=['bottom', 'back'], faces={'top': 'cut'}),
    ]
    # the gates: cabinets with light tops
    for i, z in enumerate(GATE_Z):
        n.append(box(f'gate_{i}', (GATE_X[0], -0.02, z - GATE_W / 2), (GATE_X[1], CUT, z + GATE_W / 2), 'gate',
                     open=['bottom'], faces={'top': 'gate_top'}))
    # the office: walls cut at 1 m but its back (the back wall); the window is glass
    ox0, oz0, ox1, oz1 = OFFICE
    t = 0.15
    n += [box('office_w', (ox0, -0.02, oz0), (ox0 + t, CUT, oz1), 'wall_light', open=['bottom', 'front'], faces={'top': 'cut'}),
          box('office_e', (ox1 - t, -0.02, oz0), (ox1, CUT, oz1), 'wall_light', open=['bottom', 'front'], faces={'top': 'cut'}),
          box('office_sill', (ox0 + t, -0.02, oz0), (OFFICE_DOOR[0], 0.8, oz0 + t), 'wall_light', open=['bottom', 'left'],
              faces={'top': 'cut'}),
          box('office_glass', (ox0 + t, 0.8, oz0 + 0.05), (OFFICE_DOOR[0], CUT, oz0 + 0.1), 'glass', open=['bottom', 'left']),
          box('office_jamb', (OFFICE_DOOR[1], -0.02, oz0), (ox1 - t, CUT, oz0 + t), 'wall_light', open=['bottom', 'right'],
              faces={'top': 'cut'}),
          box('office_desk', (ox0 + 0.4, -0.02, oz1 - 0.7), (ox1 - 0.4, 0.75, oz1 - 0.1), 'desk', open=['bottom'])]
    # the lockers, with the alcove
    lx0, lz0, lx1, lz1 = LOCKERS
    n += [box('lockers_w', (lx0, -0.02, lz0), (ALCOVE[0], WALL_H - 0.4, lz1), 'hide', open=['bottom', 'left', 'front'],
              faces={'top': 'cut'}),
          box('lockers_e', (ALCOVE[1], -0.02, lz0), (lx1, WALL_H - 0.4, lz1), 'hide', open=['bottom', 'front'],
              faces={'top': 'cut'})]
    return recipe('r2_shell', n, 700)


def shell_col():
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T
    zo0, zo1 = Z0 - WALL_T, Z1 + WALL_T
    op = ['bottom', 'top']
    n = [box('slab', (xo0, -0.4, zo0), (xo1, 0, zo1), 'floor', open=['bottom', 'left', 'right', 'front', 'back']),
         box('front_wall', (xo0, -0.02, zo0), (xo1, CUT, Z0), 'floor', open=op),
         box('back_wall', (xo0, -0.02, Z1), (xo1, WALL_H, zo1), 'floor', open=op),
         box('end_w', (xo0, -0.02, Z0), (X0, WALL_H, Z1), 'floor', open=op + ['back', 'front']),
         box('end_e_front', (X1, -0.02, Z0), (xo1, WALL_H, EXIT_DOOR[0]), 'floor', open=op + ['back']),
         box('end_e_back', (X1, -0.02, EXIT_DOOR[1]), (xo1, WALL_H, Z1), 'floor', open=op + ['front'])]
    return recipe('r2_shell_col', n, 200, collision=True)


def play():
    xo0, xo1 = X0 - WALL_T, X1 + WALL_T
    zo0, zo1 = Z0 - WALL_T, Z1 + WALL_T
    ox0, oz0, ox1, oz1 = OFFICE
    t = 0.15
    lx0, lz0, lx1, lz1 = LOCKERS
    ents = [
        {'id': P + 'room', 'type': 'room', 'position': [0, 0, 0],
         'params': {'entry': P + 'spawn', 'exit': P + 'exit', 'size': [r(xo1 - xo0), WALL_H, r(zo1 - zo0)]}},
        {'id': P + 'spawn', 'type': 'spawn', 'position': [SPAWN[0], 0, SPAWN[1]], 'params': {'yaw': SPAWN[2]}},
        {'id': P + 'exit', 'type': 'exit', 'position': [EXIT['pos'][0], 0, EXIT['pos'][1]], 'params': {'size': list(EXIT['size'])}},
        {'id': P + 'hide_lockers', 'type': 'hide_spot', 'position': [r(sum(ALCOVE) / 2), 0, r((lz0 + lz1) / 2)],
         'params': {'size': [r(ALCOVE[1] - ALCOVE[0]), 1.7, r(lz1 - lz0)]}},
        wall(P + 'wall_front', xo0, zo0, xo1, Z0, h=CUT),
        wall(P + 'wall_back', xo0, Z1, xo1, zo1),
        wall(P + 'wall_end_w', xo0, Z0, X0, Z1),
        wall(P + 'wall_end_e_front', X1, Z0, xo1, EXIT_DOOR[0]),
        wall(P + 'wall_end_e_back', X1, EXIT_DOOR[1], xo1, Z1),
        # the stairwell is a hole: it stops the thief, not the cones
        # the stairwell and its railings, which the dressed room stands 0.12 m outside the well
        wall(P + 'wall_stairwell', STAIRWELL[0], STAIRWELL[1], STAIRWELL[2] + RAIL_OUT, STAIRWELL[3] + RAIL_OUT,
             blocks=False, h=CUT),
        wall(P + 'wall_machines', MACHINES[0], MACHINES[1], MACHINES[2], MACHINES[3], blocks=False, h=CUT),
        # the office: walls block; its window is glass
        wall(P + 'wall_office_w', ox0, oz0, ox0 + t, oz1, h=CUT),
        wall(P + 'wall_office_e', ox1 - t, oz0, ox1, oz1, h=CUT),
        wall(P + 'wall_office_window', ox0 + t, oz0, OFFICE_DOOR[0], oz0 + t, blocks=False, h=CUT),
        wall(P + 'wall_office_jamb', OFFICE_DOOR[1], oz0, ox1 - t, oz0 + t, h=CUT),
        wall(P + 'wall_lockers_w', lx0, lz0, ALCOVE[0], lz1, h=WALL_H - 0.4),
        wall(P + 'wall_lockers_e', ALCOVE[1], lz0, lx1, lz1, h=WALL_H - 0.4),
    ]
    # the gates stop the thief but are low: cones pass over them
    for i, z in enumerate(GATE_Z):
        ents.append(wall(f'{P}wall_gate_{i}', GATE_X[0], z - GATE_W / 2, GATE_X[1], z + GATE_W / 2, blocks=False, h=CUT))
    # from the last gate to the office: a barrier (glass panels over a low wall)
    ents.append(wall(P + 'wall_gate_barrier', GATE_X[0], GATE_Z[-1] + GATE_W / 2, GATE_X[1], oz0, blocks=False, h=CUT))
    ents += patrol(P + 'guard', GUARD['start'], GUARD['route'], GUARD['speed'], GUARD['sight'], GUARD['fov'],
                   turn_rate=GUARD['turn_rate'])
    return {'entities': ents, 'paths': {}}


def main():
    placements = [{'id': P + 'shell', 'asset': 'r2_shell', 'position': [0, 0, 0], 'collision': 'r2_shell_col'}]
    write_room(HERE, NAME, [shell(), shell_col()], placements, play())


if __name__ == '__main__':
    main()
