#!/usr/bin/env python3
"""Stage 2, room 5: the food hall (greybox), the stage's last room. Writes the room's recipes,
placements and play file beside itself (levels/greybox.py and levels/s2room.py say what each is);
PLAN.md is the room's floor plan.

    python3 carts/afterhours/rooms/foodhall/make_foodhall.py

The department store's basement: two rows of lit cases (cakes, fruit, wrapped boxes) either side
of a middle aisle, the melon counter at the east end, stacked gift boxes. The service lift from
the shop floor opens in the back wall at the west end; the way out, to the underground mall, is
the shutter door at the front of the east wall. A cleaner pushes his cart round the cases;
the guard at the melon counter looks along the hall from side to side; a camera on the back wall
sweeps the crossing in the middle. Gift boxes knocked over are heard.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
from greybox import patrol, posted, wall, write_room  # noqa: E402
import s2room  # noqa: E402

NAME = 'foodhall'
P = 'fh_'
X = (-12.0, 12.0)
Z = (-4.75, 4.75)
CASES = [(-7.5, -1.7, -1.0, -1.0), (1.0, -1.7, 7.5, -1.0),        # the front row of cases: glass
         (-7.5, 1.1, -1.0, 1.8), (1.0, 1.1, 7.5, 1.8)]           # the back row
COUNTER = (9.6, -1.0, 10.4, 2.4)          # the melon counter: low
PILLARS = [(-4.25, -3.6), (4.25, 3.4)]    # the basement's columns: they stop cones
PS = 0.7
GIFTS = [(-1.7, 0.05), (8.6, -3.4), (-9.0, -2.2)]    # stacked gift boxes: fragile

ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_food_hall', 'x': X, 'z': Z, 'entry': 'lift',
    'doors': [
        {'id': 'lift', 'side': 'n', 'at': (-10.4, -9.0), 'to': 'sf_door_lift'},
        {'id': 'mall', 'side': 'e', 'at': (-3.6, -2.4), 'end': True, 'spawn': False},
    ],
    'props': [(f'case_{i}', 'glass', c, 0.95) for i, c in enumerate(CASES)] +
             [('counter', 'low', COUNTER, 0.9)] +
             [(f'pillar_{i}', 'pillar', (x - PS / 2, z - PS / 2, x + PS / 2, z + PS / 2), 2.4)
              for i, (x, z) in enumerate(PILLARS)],
    'guards': [
        # the cleaner and his cart, round all the cases, the other way from the clock
        *patrol(P + 'guard_cleaner', (2.0, -2.6), [
            (P + 'wp_cleaner_se', (8.4, -2.6), 0, 0),
            (P + 'wp_cleaner_ne', (8.4, 2.9), 60, 270),
            (P + 'wp_cleaner_nw', (-8.6, 2.9), 0, 180),
            (P + 'wp_cleaner_sw', (-8.6, -2.6), 0, 90)], speed=1.0, sight=4.5, fov=60, turn_rate=200),
        posted(P + 'guard_melon', (11.0, 0.6), 200, 300, 120, 150, sight=6.0, fov=60),
        posted(P + 'camera_middle', (0.0, 4.6), 150, 210, 90, 120, sight=7.0, fov=36, kind='camera', y=2.3),
    ],
}


def fragile(id, x, z, radius=0.4, noise=8.0):
    return {'id': id, 'type': 'fragile', 'position': [x, 0, z], 'params': {'radius': radius, 'noise': noise}}


# What the dressed room (NOTES.md) stands in play that the greybox did not: the shops' counters
# along the back wall (0.5 m deep, 0.86 m, their andons against the wall) and the cleaner's
# parked cart in the west end. They stop the thief; cones pass. In the wall map only, so ROOM
# (which dress_foodhall.py reads) stays as it was.
BACK_COUNTERS = [(-7.6, -2.2), (-1.2, 1.2), (2.4, 7.6)]
DRESSED = [wall(f'{P}wall_back_counter_{k}', a, Z[1] - 0.5, b, Z[1], blocks=False, h=0.86)
           for k, (a, b) in enumerate(BACK_COUNTERS)] + \
          [wall(P + 'wall_cart', -11.9, 2.6, -11.25, 3.5, blocks=False, h=1.0)]


def main():
    recipes, placements, play = s2room.build(ROOM)
    play['entities'] += DRESSED
    play['entities'] += [fragile(f'{P}gifts_{i}', x, z) for i, (x, z) in enumerate(GIFTS)]
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
