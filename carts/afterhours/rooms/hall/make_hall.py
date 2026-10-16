#!/usr/bin/env python3
"""The tower, the lift hall on the sixth floor (greybox). Writes the room's recipes, placements and
play file beside itself (levels/greybox.py and levels/s2room.py say what each is); PLAN.md is the
room's floor plan.

    python3 carts/afterhours/rooms/hall/make_hall.py

The building's core (the lifts on its south face, the fire stair in its west face) with a corridor
round it, split by the securities house's glass screens: the lift lobby in front, where the lifts
from the lobby open and the glass doors lead onto the trading floor; the back of house round the
core, from the fire stair to the goods lift down to the loading bay (the stage's end). The thief
crosses it twice, once on each side of the glass, and no door joins the two sides: a night guard
walks the lift lobby, a cleaner goes round his boxes behind, and each sees through the glass into
the other's half.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
from greybox import WALL_H, patrol, write_room  # noqa: E402
import s2room  # noqa: E402

NAME = 'hall'
P = 'lh_'
CORE = (-5.0, 0.2, 3.0, 3.0)          # the core, in the same place on every floor (x -5 ... 3)

ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_lift_hall', 'x': (-11.0, 11.0), 'z': (-4.5, 4.5), 'entry': 'lifts',
    'doors': [
        # the lifts up from the lobby: he comes out of one; it goes on without him (a way in only)
        {'id': 'lifts', 'side': 'free', 'pos': (-2.2, 0.0), 'yaw': 180, 'width': 1.2, 'spawn_at': (-2.2, -0.9)},
        # the securities house's glass doors onto the trading floor
        {'id': 'trading', 'side': 'w', 'at': (-3.6, -2.4), 'to': 'tf_door_hall'},
        # the fire stair, in the core's west face, from the roof (the cleaners wedge this one door)
        {'id': 'stair', 'side': 'free', 'pos': (-5.2, 1.7), 'yaw': 270, 'width': 1.2, 'spawn_at': (-6.2, 1.7),
         'to': 'rf_door_stair'},
        # the goods lift down to the loading bay: the stage's end
        {'id': 'goods', 'side': 'e', 'at': (-3.6, -2.4), 'end': True},
    ],
    'props': [
        ('core', 'block', CORE, WALL_H),
        # the glass screens: the lift lobby in front, the back of house behind
        ('screen_w', 'glass', (-11.0, 0.05, CORE[0], 0.2), WALL_H, ['right']),
        ('screen_e', 'glass', (CORE[2], -4.5, CORE[2] + 0.15, 0.2), WALL_H, ['front']),
        ('lift_doors', 'mark', (-4.4, -0.3, -0.2, 0.0), 0),
        ('planter', 'block', (-4.5, -2.0, -3.5, -0.7), 1.2),
        ('reception', 'low', (-10.4, -4.5, -8.6, -3.9), 1.0),
        ('sofa', 'low', (-0.2, -4.5, 1.8, -3.9), 0.6),
        ('boxes', 'block', (6.6, -1.4, 8.0, 0.0), 1.6),
        ('trolley', 'low', (6.4, 2.4, 7.6, 3.0), 1.0),
    ],
    'guards': [
        # the night guard along the lift lobby: at the west end a look up the corridor behind the
        # glass, at the east end a look through the glass at the back of house
        *patrol(P + 'guard_lobby', (-8.6, -2.2), [
            (P + 'wp_lobby_e', (1.6, -2.2), 120, 90),
            (P + 'wp_lobby_w', (-8.6, -2.2), 120, 10)], speed=0.9, sight=6.0, fov=60, turn_rate=200),
        # the cleaner round the boxes in the back of house
        *patrol(P + 'guard_cleaner', (9.6, 1.4), [
            (P + 'wp_clean_se', (9.6, -2.8), 0, 270),
            (P + 'wp_clean_sw', (5.0, -2.8), 0, 0),
            (P + 'wp_clean_nw', (5.0, 1.4), 0, 90),
            (P + 'wp_clean_ne', (9.6, 1.4), 90, 180)], speed=0.8, sight=5.0, fov=60, turn_rate=200),
    ],
}


def main():
    recipes, placements, play = s2room.build(ROOM)
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
