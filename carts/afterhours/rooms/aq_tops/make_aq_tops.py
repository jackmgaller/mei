#!/usr/bin/env python3
"""The aquarium, room 7: the tank tops (greybox). Writes the room's recipes, placements and play file
beside itself (levels/greybox.py and levels/aquarium/aqroom.py say what each is); PLAN.md is the
room's floor plan.

    python3 carts/afterhours/rooms/aq_tops/make_aq_tops.py

The second floor over the big tanks, where the public never goes: the open water of the shark
tank and the turtle pool under a dark roof, crossed by narrow walkways and a bridge, a few work
lamps hung over them. A keeper with a torch walks round the shark tank; a camera at the east end
looks across the water at the lamps. Leg 7: in from the kitchen, out by the stair down to the
great tank's catwalk.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
sys.path.insert(0, str(HERE.parents[1] / 'levels' / 'aquarium'))
from greybox import WALL_H, patrol, posted, write_room  # noqa: E402
import aqroom  # noqa: E402

NAME = 'aq_tops'
P = 'at_'
X = (-9.0, 9.0)
Z = (-4.5, 4.5)
SHARK = (-7.6, -3.0, -1.4, 3.0)         # the shark tank's water, crossed by the bridge
BRIDGE = (-4.9, -3.9)                   # the bridge's x
TURTLE = (1.4, -3.0, 7.6, 1.6)          # the turtle pool's water

ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_tank_tops', 'x': X, 'z': Z, 'entry': 'kitchen', 'dark': True,
    'doors': [
        {'id': 'kitchen', 'side': 'e', 'at': (-4.2, -3.0), 'to': 'ak_door_tops'},
        {'id': 'great', 'side': 'w', 'at': (3.1, 4.3), 'to': 'ag_door_tops'},
    ],
    'props': [
        ('shark_w', 'water', (SHARK[0], SHARK[1], BRIDGE[0], SHARK[3]), 0.0),
        ('shark_e', 'water', (BRIDGE[1], SHARK[1], SHARK[2], SHARK[3]), 0.0),
        ('turtle', 'water', TURTLE, 0.0),
        # the life-support housings at the walkways' corners: they block
        ('housing_0', 'machine', (-1.4, 3.0, -0.4, 3.8), 1.6),
        ('housing_1', 'machine', (7.6, 1.6, 8.6, 2.4), 1.6),
    ],
    'lights': [
        ('middle', (-1.4, -1.2, 1.4, 1.2), 0, None),
        ('bridge', (-4.9, -0.8, -3.9, 0.8), 0, (420, 210, 0)),
        ('front', (2.0, -4.5, 5.0, -3.0), 0, None),
        ('back', (-6.4, 3.0, -3.0, 4.5), 0, None),
    ],
    'guards': [
        # the keeper with a torch, round the shark tank: up the middle walk, west along the back,
        # down the west walk, east along the front
        *aqroom.torch(patrol(P + 'guard_keeper', (0.0, -2.0), [
            (P + 'wp_keeper_ne', (0.0, 4.15), 30, 270),
            (P + 'wp_keeper_nw', (-8.3, 4.15), 0, 180),
            (P + 'wp_keeper_sw', (-8.3, -3.7), 30, 90),
            (P + 'wp_keeper_se', (0.0, -3.7), 0, 0)], speed=1.0, sight=4.5, fov=60, turn_rate=200)),
        # at the east end, looking west across the water (sees only the lamps' light)
        posted(P + 'camera_east', (8.8, 3.6), 240, 290, 120, 120, sight=13.0, fov=36, phase=360, kind='camera', y=2.3),
    ],
}

SKETCH = {
    7: [(8.1, -3.6), (0.0, -3.75, 'wait'), (0.0, 4.15), (-2.8, 4.15, 'wait'), (-8.1, 4.15), (-8.4, 3.7), (-8.9, 3.7)],
}

def main():
    recipes, placements, play = aqroom.build(ROOM)
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
