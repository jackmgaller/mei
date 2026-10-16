#!/usr/bin/env python3
"""The aquarium, room 0: the entrance hall (greybox), on two levels. Writes the room's recipes,
placements and play file beside itself (levels/greybox.py and levels/aquarium/aqroom.py say
what each is); PLAN.md is the room's floor plan.

    python3 carts/afterhours/rooms/aq_hall/make_aq_hall.py

The aquarium's front of house after closing, dark but for its tanks: the main doors, the ticket
gates shut, the information desk, and the welcome tank in the middle, a cylinder of sea rising
through both floors. Over the back runs the restaurant's mezzanine, round the tank's top. The
stage starts at the main doors (leg 0, the floor: across the tank's light while the guard at
the desk looks away) and ends on the mezzanine (leg 9: from the great tank's catwalk, past a
torch and a camera, out by the glass door to the pedestrian deck).

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
sys.path.insert(0, str(HERE.parents[1] / 'levels' / 'aquarium'))
from greybox import WALL_H, patrol, posted, write_room  # noqa: E402
import aqroom  # noqa: E402

NAME = 'aq_hall'
P = 'ah_'
X = (-8.0, 8.0)
Z = (-3.5, 3.5)
UPPER = 3.2
TANK = (-1.2, -0.6, 1.6, 2.2)          # the welcome tank (glass, both floors): x0, z0, x1, z1
MEZZ = (-8.0, 1.3, 8.0, 3.5)           # the mezzanine (level 1)

ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_entrance_hall', 'x': X, 'z': Z, 'entry': 'main',
    'dark': True, 'upper': UPPER,
    'doors': [
        # the main doors from the street: the stage's start (not a way back)
        {'id': 'main', 'side': 'w', 'at': (-3.0, -1.8)},
        {'id': 'great', 'side': 'e', 'at': (-1.6, -0.4), 'to': 'ag_door_hall'},
        # the mezzanine: in from the great tank's catwalk, out by the glass door to the deck
        {'id': 'catwalk', 'side': 'e', 'at': (2.2, 3.4), 'level': 1, 'to': 'ag_door_hall_up'},
        {'id': 'deck', 'side': 'w', 'at': (2.2, 3.4), 'level': 1, 'end': True, 'spawn': False},
    ],
    'props': [
        ('tank', 'glass', TANK, WALL_H),
        ('gates', 'low', (-4.7, -1.0, -4.4, 3.5), 1.0),
        ('desk', 'low', (3.6, 0.6, 6.4, 1.2), 1.0),
        ('pillar_w', 'pillar', (-6.3, 0.9, -5.7, 1.5), WALL_H),
        ('pillar_e', 'pillar', (6.6, 0.9, 7.2, 1.5), WALL_H),
    ],
    'walks': [MEZZ],
    'upper_props': [
        ('tank_top', 'water', (TANK[0], MEZZ[1], TANK[2], TANK[3]), 0.0),
        ('tables_w', 'low', (-6.6, 1.35, -5.4, 1.85), 0.8),
        ('tables_e', 'low', (5.4, 1.35, 6.6, 1.85), 0.8),
    ],
    'hides': [
        ('booth_w', (-4.6, 2.85, -3.4, 3.5), 1),
        ('booth_e', (3.0, 2.85, 4.2, 3.5), 1),
    ],
    'lights': [
        # the welcome tank's light on the floor, all round it and down to the front wall
        ('tank_s', (-2.4, -3.5, 2.8, -0.6), 0, None),
        ('tank_w', (-2.4, -0.6, -1.2, 1.3), 0, None),
        ('tank_e', (1.6, -0.6, 2.8, 1.3), 0, None),
        # the great tank's blue through the east door
        ('door_e', (6.6, -1.8, 8.0, 0.2), 0, None),
        # on the mezzanine: the tank's top, lit from inside
        ('tank_top', (-2.2, 1.3, 2.6, 3.5), 1, None),
    ],
    'guards': [
        # behind the information desk: looks at the east door, then across the tank's light
        posted(P + 'guard_desk', (5.0, 1.9), 135, 235, 150, 90, sight=8.0, fov=50, phase=300),
        # the mezzanine's night guard with a torch, end to end
        *aqroom.on_level(aqroom.torch(patrol(P + 'guard_mezz', (3.5, 2.3), [
            (P + 'wp_mezz_w', (-5.8, 2.3), 60, 270),
            (P + 'wp_mezz_e', (5.8, 2.3), 60, 90)], speed=0.9, sight=4.5, fov=60, turn_rate=200)), 1),
        # a camera on the back wall by the east booth, looking west along the mezzanine
        aqroom.on_level(posted(P + 'camera_mezz', (4.6, 3.3), 250, 295, 180, 90, sight=7.5, fov=40, phase=443,
                               kind='camera', y=UPPER + 2.3), 1),
    ],
}

# The intended ways through (levels/aquarium/sketch.py draws them): leg 0 on the floor, leg 9 on
# the mezzanine. A point with a third value is a wait (or 'hide').
SKETCH = {
    0: [(-7.1, -2.4), (-3.0, -2.9, 'wait'), (3.4, -2.9, 'wait'), (7.2, -1.0), (7.9, -1.0)],
    9: [(7.1, 2.8), (2.8, 2.6, 'wait'), (-2.5, 2.6, 'wait'), (-4.0, 3.15, 'hide'), (-7.0, 2.8), (-7.9, 2.8)],
}


def main():
    recipes, placements, play = aqroom.build(ROOM)
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
