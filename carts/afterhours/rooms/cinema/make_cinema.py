#!/usr/bin/env python3
"""Stage 2, room 1: the cinema (greybox). Writes the room's recipes, placements and play file
beside itself (levels/greybox.py and levels/s2room.py say what each is); PLAN.md is the room's
floor plan.

    python3 carts/afterhours/rooms/cinema/make_cinema.py

The thief comes out of the aquarium's service corridor behind the screen. The auditorium: three
blocks of seats either side of a middle aisle, an aisle in front and one at the back, two cross
aisles. The projector's window high in the east wall looks down the middle aisle (a cone that
never moves). An usher walks round the seats; a cleaner sweeps the second cross aisle, front to
back. The way out is the staff door in the east wall at the back, to the staff corridor.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
from greybox import CUT, WALL_H, patrol, posted, wall, write_room  # noqa: E402
import s2room  # noqa: E402

NAME = 'cinema'
P = 'cn_'
X = (-11.0, 11.0)
Z = (-4.5, 4.5)
SCREEN = (-9.3, -3.2, -9.0, 3.6)           # the screen: x0, z0, x1, z1 (a wall to the cones)
SEAT_X = [(-7.0, -3.6), (-2.2, 1.2), (2.6, 6.0)]     # three blocks of rows
SEAT_Z = [(-3.0, -0.7), (0.7, 3.0)]                  # either side of the middle aisle
AISLE_FRONT, AISLE_BACK = -3.75, 3.75
CROSS_2 = 1.9                                         # the second cross aisle's middle

ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_cinema', 'x': X, 'z': Z, 'entry': 'screen',
    'doors': [
        # behind the screen: the aquarium's service corridor (the stage's start; not a way back)
        {'id': 'screen', 'side': 'w', 'at': (-0.6, 0.6), 'spawn': (0.0, 0.9)},
        {'id': 'corridor', 'side': 'e', 'at': (2.6, 3.8), 'to': 'sc_door_cinema'},
    ],
    'props': [('screen', 'block', SCREEN, WALL_H)] +
             [(f'seats_{i}{j}', 'seat', (x0, z0, x1, z1), 0.9)
              for i, (x0, x1) in enumerate(SEAT_X) for j, (z0, z1) in enumerate(SEAT_Z)],
    'guards': [
        # the projector's window: high in the east wall, looking down the middle aisle, never moving
        posted(P + 'camera_booth', (10.85, 0.0), 270, 270, 600, 60, sight=10.0, fov=30, kind='camera', y=2.3),
        *patrol(P + 'guard_usher', (-8.0, 1.0), [
            (P + 'wp_usher_sw', (-8.0, AISLE_FRONT), 30, 90),
            (P + 'wp_usher_se', (7.6, AISLE_FRONT), 60, 0),
            (P + 'wp_usher_ne', (7.6, AISLE_BACK), 0, 270),
            (P + 'wp_usher_nw', (-8.0, AISLE_BACK), 0, 180)], speed=1.1, sight=5.0, fov=60, turn_rate=200),
        *patrol(P + 'guard_cleaner', (CROSS_2, -3.0), [
            (P + 'wp_cleaner_s', (CROSS_2, AISLE_FRONT), 90, 90),
            (P + 'wp_cleaner_n', (CROSS_2, AISLE_BACK), 90, 260)], speed=0.9, sight=4.5, fov=60, turn_rate=200),
    ],
}


# What the dressed room (NOTES.md) stands in play that the greybox did not: the curtains at the
# screen's ends (they block cones, as the screen does) and the speakers behind it. In the wall
# map only: dress_cinema.py draws them from SCREEN, so ROOM stays as it was.
DRESSED = [
    wall(P + 'wall_curtain_s', SCREEN[0] - 0.12, SCREEN[1], SCREEN[2] + 0.14, SCREEN[1] + 0.4, h=CUT),
    wall(P + 'wall_curtain_n', SCREEN[0] - 0.12, SCREEN[3] - 0.4, SCREEN[2] + 0.14, SCREEN[3], h=CUT),
    wall(P + 'wall_speaker_s', SCREEN[0] - 0.32, -2.4, SCREEN[0], -1.2, h=CUT),
    wall(P + 'wall_speaker_n', SCREEN[0] - 0.32, 1.6, SCREEN[0], 2.8, h=CUT),
]


def main():
    recipes, placements, play = s2room.build(ROOM)
    play['entities'] += DRESSED
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
