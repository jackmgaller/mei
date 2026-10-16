#!/usr/bin/env python3
"""The aquarium, room 6: the fish kitchen (greybox). Writes the room's recipes, placements and play file
beside itself (levels/greybox.py and levels/aquarium/aqroom.py say what each is); PLAN.md is the
room's floor plan.

    python3 carts/afterhours/rooms/aq_kitchen/make_aq_kitchen.py

The keepers' kitchen where the animals' food is made: steel prep tables, buckets of fish and
squid stacked on the floor, the walk-in freezer, a tank of live feed. The brightest room in the
building. The cook walks round the prep tables, and he hears a knocked bucket from anywhere in
the room: a breather after the plant, walked behind his back.
Leg 6: up the service stair from the plant, out to the tank tops.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
sys.path.insert(0, str(HERE.parents[1] / 'levels' / 'aquarium'))
from greybox import WALL_H, patrol, posted, write_room  # noqa: E402
import aqroom  # noqa: E402

NAME = 'aq_kitchen'
P = 'ak_'
X = (-6.5, 6.5)
Z = (-4.0, 4.0)
ISLAND = (-3.0, -1.2, 2.0, 0.2)        # the prep tables (low)

ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_fish_kitchen', 'x': X, 'z': Z, 'entry': 'plant',
    'doors': [
        {'id': 'plant', 'side': 'w', 'at': (-3.2, -2.0), 'to': 'ap_door_kitchen'},
        {'id': 'tops', 'side': 'n', 'at': (3.8, 5.0), 'to': 'at_door_kitchen'},
    ],
    'props': [
        ('island', 'low', ISLAND, 0.9),
        ('sinks', 'low', (-6.5, 3.3, -1.5, 4.0), 0.9),
        ('freezer', 'block', (-6.5, 0.6, -4.6, 3.0), WALL_H),
        ('feed_tank', 'glass', (3.8, 0.9, 5.6, 2.1), 1.2),
        ('shelves', 'block', (5.8, -3.6, 6.5, 0.0), WALL_H),
    ],
    'hides': [('freezer', (-4.6, 1.2, -3.8, 2.4))],
    'fragile': [('buckets_0', (-0.6, -2.3), 0.35, 6.0), ('buckets_1', (2.6, -1.6), 0.35, 6.0),
                ('buckets_2', (1.4, 3.1), 0.35, 6.0)],
    'guards': [
        # the cook, round the prep tables
        *patrol(P + 'guard_cook', (-1.5, -2.4), [
            (P + 'wp_cook_se', (3.0, -2.4), 30, 0),
            (P + 'wp_cook_ne', (3.0, 1.2), 0, 270),
            (P + 'wp_cook_nw', (-4.0, 1.2), 30, 180),
            (P + 'wp_cook_sw', (-4.0, -2.4), 0, 90)], speed=1.0, sight=5.0, fov=60, turn_rate=200),
    ],
}

SKETCH = {
    6: [(-5.6, -2.6), (-2.0, -3.1, 'wait'), (2.0, -3.1, 'wait'), (3.4, -0.6, 'wait'), (3.4, 2.7), (4.4, 2.8), (4.4, 3.9)],
}

def main():
    recipes, placements, play = aqroom.build(ROOM)
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
