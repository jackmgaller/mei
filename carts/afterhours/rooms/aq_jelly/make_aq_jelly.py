#!/usr/bin/env python3
"""The aquarium, room 2: the jellyfish gallery (greybox). Writes the room's recipes, placements and play file
beside itself (levels/greybox.py and levels/aquarium/aqroom.py say what each is); PLAN.md is the
room's floor plan.

    python3 carts/afterhours/rooms/aq_jelly/make_aq_jelly.py

A narrow dark gallery of jellyfish: four glass columns down its middle, each lit from below
by a lamp that slowly comes up and fades, one after another, so a wave of light runs down the
gallery every eight seconds. A guard stands at the far end looking back up it; a keeper without
a torch walks the back aisle. Leg 2: in from the great tank, out to the ocean gallery, walking
in the dark behind the wave.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
sys.path.insert(0, str(HERE.parents[1] / 'levels' / 'aquarium'))
from greybox import WALL_H, patrol, posted, write_room  # noqa: E402
import aqroom  # noqa: E402

NAME = 'aq_jelly'
P = 'aj_'
X = (-7.0, 7.0)
Z = (-4.0, 4.0)
COLS = [-4.5, -1.5, 1.5, 4.5]           # the jellyfish columns' x (glass, 1 m square)
CYCLE = (480, 240)                      # each bay's lamp: lit 240 ticks of every 480

ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_jellyfish_gallery', 'x': X, 'z': Z, 'entry': 'great', 'dark': True,
    'doors': [
        {'id': 'great', 'side': 'w', 'at': (-3.2, -2.0), 'to': 'ag_door_jelly'},
        {'id': 'ocean', 'side': 'e', 'at': (1.6, 2.8), 'to': 'ao_door_jelly'},
    ],
    'props': [(f'column_{i}', 'glass', (x - 0.5, -0.5, x + 0.5, 0.5), WALL_H) for i, x in enumerate(COLS)] +
             [('wall_tanks', 'glass', (-5.5, 3.6, 5.5, 4.0), WALL_H)],
    # four bays, x -6..6, lit in turn from the west: a wave running east
    'lights': [(f'bay_{i}', (-6.0 + 3.0 * i, -4.0, -3.0 + 3.0 * i, 3.6), 0, (CYCLE[0], CYCLE[1], 120 * i))
               for i in range(4)],
    'guards': [
        # at the far end's front corner, looking back up the gallery
        posted(P + 'guard_end', (6.3, -3.3), 285, 315, 120, 120, sight=13.0, fov=40),
        # the keeper, no torch: along the back aisle and back
        *patrol(P + 'guard_keeper', (-5.5, 2.6), [
            (P + 'wp_keeper_e', (5.5, 2.6), 90, 180),
            (P + 'wp_keeper_w', (-5.5, 2.6), 90, 180)], speed=0.9, sight=4.5, fov=60, turn_rate=180),
    ],
}

SKETCH = {
    2: [(-6.1, -2.6), (-6.2, -2.4, 'wait'), (-3.2, -2.4, 'wait'), (-0.2, -2.4, 'wait'), (2.8, -2.4, 'wait'), (6.4, -2.0), (6.4, 2.2), (6.9, 2.2)],
}

def main():
    recipes, placements, play = aqroom.build(ROOM)
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
