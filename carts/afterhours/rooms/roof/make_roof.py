#!/usr/bin/env python3
"""The tower, the roof (greybox), the tower's top. Writes the room's recipes, placements and play
file beside itself (levels/greybox.py and levels/s2room.py say what each is); PLAN.md is the
room's floor plan.

    python3 carts/afterhours/rooms/roof/make_roof.py

The top of the tower at night, the city's lights all round: the lift motor room and the fire
stair's house over the core, the chairman's helipad painted at the east end with his stair house
beside it, water tanks, air-conditioning plant and a skylight. A searchlight on a mast at the
motor room's front sweeps a narrow beam slowly across the roof and back, cut by everything that
stands on it; a guard walks the west end past the fire stair's door. In by the chairman's stair
(from the ninth); out by the fire stair, down the core to the sixth.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
from greybox import WALL_H, patrol, posted, write_room  # noqa: E402
import s2room  # noqa: E402

NAME = 'roof'
P = 'rf_'
CORE_X = (-5.0, 3.0)                  # the core, in the same place on every floor

cx0, cx1 = CORE_X
ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_roof', 'x': (-11.0, 11.0), 'z': (-4.5, 4.5), 'entry': 'private',
    'doors': [
        # the chairman's stair house by the helipad, from his office
        {'id': 'private', 'side': 'e', 'at': (2.4, 3.6), 'to': 'nf_door_up'},
        # the fire stair's house, in the motor room's west face: down the core to the sixth
        {'id': 'stair', 'side': 'free', 'pos': (-5.2, 1.7), 'yaw': 270, 'width': 1.2, 'spawn_at': (-6.2, 1.7),
         'to': 'lh_door_stair'},
    ],
    'props': [
        # the lift motor room and the stair house over the core
        ('motor_room', 'block', (cx0, 0.2, cx1, 4.5), WALL_H),
        ('helipad', 'mark', (4.4, -3.4, 9.4, 1.4), 0),
        ('tank_e', 'block', (5.2, 2.4, 6.8, 4.0), WALL_H),
        ('plant_a', 'block', (1.4, -3.0, 2.8, -1.6), 1.6),
        ('skylight', 'block', (-2.6, -2.6, -1.2, -1.8), 1.2),
        ('plant_b', 'block', (-6.9, -3.75, -5.0, -2.0), 1.6),
        ('tank_w', 'block', (-9.8, -1.2, -8.2, 0.4), WALL_H),
    ],
    'guards': [
        # the searchlight on its mast at the motor room's front: a narrow beam swept slowly
        # across the roof, cut by everything that stands on it
        posted(P + 'camera_light', (-1.0, -0.1), 95, 265, 40, 360, sight=12.0, fov=10, kind='camera', y=2.3),
        # a guard up and down the west end, past the fire stair, with a look each way at the ends
        *patrol(P + 'guard_west', (-7.0, 3.6), [
            (P + 'wp_west_n', (-7.0, 3.6), 120, 180),
            (P + 'wp_west_s', (-7.2, -0.6), 150, 0)], speed=0.8, sight=5.0, fov=60, turn_rate=200),
    ],
}


def main():
    recipes, placements, play = s2room.build(ROOM)
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
