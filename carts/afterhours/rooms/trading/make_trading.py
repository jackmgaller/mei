#!/usr/bin/env python3
"""The tower, the trading floor on the sixth floor (greybox). Writes the room's recipes, placements
and play file beside itself (levels/greybox.py and levels/s2room.py say what each is); PLAN.md is
the room's floor plan.

    python3 carts/afterhours/rooms/trading/make_trading.py

A securities house's trading floor at night: rows of dealers' desks, two columns, a meeting room
walled in glass against the front, and in the north-west corner the back office behind its
partition, with the house's own service stair up to the floor the directory leaves out. In by the
glass doors from the lift hall (east); out by the service stair (the back wall, inside the back
office). A guard walks the middle aisle; a camera in the back office looks across it to the stair
door and turns to the window.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
from greybox import WALL_H, patrol, posted, write_room  # noqa: E402
import s2room  # noqa: E402

NAME = 'trading'
P = 'tf_'

ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_trading_floor', 'x': (-9.0, 9.0), 'z': (-4.5, 4.5), 'entry': 'hall',
    'doors': [
        {'id': 'hall', 'side': 'e', 'at': (-3.6, -2.4), 'to': 'lh_door_trading'},
        # behind the trading floor: the back office's door to the service stair, up to the ninth
        {'id': 'stair', 'side': 'n', 'at': (-8.6, -7.4), 'to': 'nf_door_stair'},
    ],
    'props': [
        # the back office in the north-west corner: its door a gap in its south partition
        ('office_s_a', 'block', (-9.0, 0.9, -7.9, 1.05), WALL_H),
        ('office_s_b', 'block', (-6.7, 0.9, -5.4, 1.05), WALL_H, ['right']),
        ('office_e', 'block', (-5.55, 1.05, -5.4, 4.5), WALL_H, ['back']),
        ('office_desk', 'low', (-7.4, 3.6, -5.55, 4.5), 0.75, ['right']),
        # the meeting room, walled in glass, against the front
        ('fish_w', 'glass', (-1.6, -4.5, -1.45, -1.8), WALL_H),
        ('fish_e', 'glass', (2.35, -4.5, 2.5, -1.8), WALL_H),
        ('fish_n', 'glass', (-1.45, -1.95, 2.35, -1.8), WALL_H, ['left', 'right']),
        ('fish_table', 'low', (-0.5, -3.6, 1.4, -2.6), 0.75),
        # the dealers' desks, in rows (cones pass over them)
        ('desks_a', 'low', (-4.6, 1.8, -0.6, 2.6), 0.9),
        ('desks_b', 'low', (0.4, 1.8, 4.4, 2.6), 0.9),
        ('desks_c', 'low', (5.2, 1.8, 8.0, 2.6), 0.9),
        ('desks_d', 'low', (4.0, -3.4, 7.2, -2.6), 0.9),
        ('col_w', 'pillar', (-4.4, -1.4, -3.7, -0.7), WALL_H),
        ('col_e', 'pillar', (3.5, -1.4, 4.2, -0.7), WALL_H),
    ],
    'guards': [
        # the floor guard up and down the middle aisle
        *patrol(P + 'guard_floor', (7.6, 0.4), [
            (P + 'wp_floor_w', (-4.6, 0.4), 90, 0),
            (P + 'wp_floor_e', (7.6, 0.4), 90, 180)], speed=1.0, sight=6.0, fov=60, turn_rate=200),
        # the back office's camera, in its south-east corner, across the office to the stair door
        posted(P + 'camera_office', (-5.75, 1.25), 300, 350, 90, 120, sight=5.0, fov=30, phase=345, kind='camera', y=2.3),
    ],
}


def main():
    recipes, placements, play = s2room.build(ROOM)
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
