#!/usr/bin/env python3
"""Stage 2, room 3: the staff corridor (greybox), the stage's hub. Writes the room's recipes,
placements and play file beside itself (levels/greybox.py and levels/s2room.py say what each is);
PLAN.md is the room's floor plan.

    python3 carts/afterhours/rooms/corridor/make_corridor.py

The back of house behind the cinema and the store: a wide service corridor with roll cages
parked down its west half, the security office in the middle of its front with a window onto
the corridor, and three doors: from the cinema (west), up to the projection booth (in the back
wall, a blue staff door) and down the staff stair to the shop floor (east). A porter walks round
the roll cages, the guard in the office looks out of his window from side to side, and a camera
over the stair door watches the east end. The thief crosses it three times, each time between
another pair of doors, each time from its clock 0.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
from greybox import WALL_H, patrol, posted, write_room  # noqa: E402
import s2room  # noqa: E402

NAME = 'corridor'
P = 'sc_'
X = (-12.5, 12.5)
Z = (-3.5, 3.5)
CAGES = (-9.0, -1.0, -5.0, 0.8)           # the roll cages parked in a block: x0, z0, x1, z1
OFFICE = (-1.0, -3.5, 4.0, 0.2)           # the security office: x0, z0, x1, z1 (its north side the window)
OFFICE_T = 0.15
WINDOW_E = 2.5                            # the window runs from the office's west wall to here

ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_staff_corridor', 'x': X, 'z': Z, 'entry': 'cinema',
    'doors': [
        {'id': 'cinema', 'side': 'w', 'at': (-2.6, -1.4), 'to': 'cn_door_corridor'},
        {'id': 'booth', 'side': 'n', 'at': (-6.6, -5.4), 'to': 'pb_door_corridor', 'card': 'blue'},
        {'id': 'shop', 'side': 'e', 'at': (1.4, 2.6), 'to': 'sf_door_corridor'},
    ],
    'props': [
        ('cages', 'block', CAGES, 1.8),
        # the office: its side walls block; its window (the north side) is glass over a sill
        ('office_w', 'block', (OFFICE[0], OFFICE[1], OFFICE[0] + OFFICE_T, OFFICE[3]), WALL_H),
        ('office_e', 'block', (OFFICE[2] - OFFICE_T, OFFICE[1], OFFICE[2], OFFICE[3]), WALL_H),
        ('office_window', 'glass', (OFFICE[0] + OFFICE_T, OFFICE[3] - OFFICE_T, WINDOW_E, OFFICE[3]), 1.0, ['left', 'right']),
        ('office_n', 'block', (WINDOW_E, OFFICE[3] - OFFICE_T, OFFICE[2] - OFFICE_T, OFFICE[3]), WALL_H, ['right']),
        ('office_desk', 'low', (OFFICE[0] + 0.5, -3.5, OFFICE[2] - 0.5, -2.8), 0.75),
        # a column in the back lane, straight out from the office's window: its shadow
        ('column', 'pillar', (1.15, 1.85, 1.85, 2.55), WALL_H),
        # pallets of stock along the back wall east of the office: low
        ('pallets', 'low', (6.0, 2.6, 9.5, 3.5), 0.9),
    ],
    'guards': [
        posted(P + 'guard_office', (1.5, -1.6), -40, 40, 90, 150, sight=6.0, fov=60),
        # round the roll cages: east along the front, up, west along the back, down past the door
        *patrol(P + 'guard_porter', (-7.0, -2.4), [
            (P + 'wp_porter_se', (-3.2, -2.4), 0, 0),
            (P + 'wp_porter_ne', (-3.2, 2.3), 0, 270),
            (P + 'wp_porter_nw', (-10.2, 2.3), 0, 180),
            (P + 'wp_porter_sw', (-10.2, -2.4), 0, 90)], speed=1.1, sight=4.5, fov=60, turn_rate=220),
        posted(P + 'camera_stair', (12.3, -3.3), 280, 328, 90, 150, sight=8.0, fov=40, phase=360, kind='camera', y=2.3),
    ],
}


def main():
    recipes, placements, play = s2room.build(ROOM)
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
