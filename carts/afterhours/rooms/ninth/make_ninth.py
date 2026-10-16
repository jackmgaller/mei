#!/usr/bin/env python3
"""The tower, the ninth floor (greybox), the floor missing from the directory. Writes the room's
recipes, placements and play file beside itself (levels/greybox.py and levels/s2room.py say what
each is); PLAN.md is the room's floor plan.

    python3 carts/afterhours/rooms/ninth/make_ninth.py

The chairman's own floor, undeclared: the lifts skip it and the core's doors are walled up here.
The securities house's service stair comes up into its north-west corner from the back office on
the sixth; a boardroom walled in glass stands in front of the core (cones pass the glass; the
thief does not); east of the core is the chairman's office behind its wall, with his private
stair up to the helipad; paintings bought at auction stand crated in the front east corner. A
guard goes round the boardroom and stops behind it to look through the glass at the front; a
camera in the chairman's office watches his stair door; the coat cupboard by the service stair
is somewhere to hide.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
from greybox import WALL_H, patrol, posted, write_room  # noqa: E402
import s2room  # noqa: E402

NAME = 'ninth'
P = 'nf_'
CORE_X = (-5.0, 3.0)                  # the core, in the same place on every floor

cx0, cx1 = CORE_X
ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_ninth_floor', 'x': (-8.0, 8.0), 'z': (-4.25, 4.25), 'entry': 'stair',
    'doors': [
        # the service stair from the trading floor's back office
        {'id': 'stair', 'side': 'n', 'at': (-7.4, -6.2), 'to': 'tf_door_stair'},
        # the chairman's private stair up to his helipad, in his office
        {'id': 'up', 'side': 'e', 'at': (2.6, 3.8), 'to': 'rf_door_private'},
    ],
    'hides': [('cupboard', (-8.0, -1.0, -7.1, 0.2))],
    'props': [
        # the core, its lift doors walled up on this floor
        ('core', 'block', (cx0, 0.4, cx1, 4.25), WALL_H),
        ('cupboard_s', 'block', (-8.0, -1.2, -7.1, -1.0), 2.0),
        ('cupboard_n', 'block', (-8.0, 0.2, -7.1, 0.4), 2.0),
        # the boardroom, walled in glass
        ('glass_s', 'glass', (-3.4, -3.1, 1.6, -2.95), WALL_H),
        ('glass_n', 'glass', (-3.4, -0.95, 1.6, -0.8), WALL_H),
        ('glass_w', 'glass', (-3.4, -2.95, -3.25, -0.95), WALL_H, ['front', 'back']),
        ('glass_e', 'glass', (1.45, -2.95, 1.6, -0.95), WALL_H, ['front', 'back']),
        ('table', 'low', (-2.4, -2.4, 0.6, -1.5), 0.75),
        # the chairman's office east of the core: a wall with a doorway
        ('office_s_a', 'block', (cx1, 0.65, 5.0, 0.8), WALL_H, ['left']),
        ('office_s_b', 'block', (6.2, 0.65, 8.0, 0.8), WALL_H),
        ('office_desk', 'low', (4.6, 2.0, 6.2, 2.6), 0.75),
        # crated paintings bought at auction, in the front east corner
        ('crates_a', 'block', (4.0, -3.4, 5.4, -2.2), 1.8),
        ('crates_b', 'block', (6.2, -1.4, 7.4, -0.4), 1.8),
    ],
    'guards': [
        # round the boardroom; behind it, a long look through the glass at the front
        *patrol(P + 'guard_round', (-1.0, -0.2), [
            (P + 'wp_round_n', (-1.0, -0.2), 120, 180),
            (P + 'wp_round_nw', (-4.3, -0.2), 0, 180),
            (P + 'wp_round_sw', (-4.3, -3.7), 0, 90),
            (P + 'wp_round_se', (2.6, -3.7), 0, 0),
            (P + 'wp_round_ne', (2.6, -0.2), 0, 270)], speed=1.0, sight=6.0, fov=60, turn_rate=200),
        # in the chairman's office, over its doorway, on the private stair's door
        posted(P + 'camera_office', (7.7, 1.0), -20, 40, 120, 120, sight=6.0, fov=30, kind='camera', y=2.3),
    ],
}


def main():
    recipes, placements, play = s2room.build(ROOM)
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
