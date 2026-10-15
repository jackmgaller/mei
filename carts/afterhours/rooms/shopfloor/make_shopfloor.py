#!/usr/bin/env python3
"""Stage 2, room 4: the shop floor (greybox). Writes the room's recipes, placements and play file
beside itself (levels/greybox.py and levels/s2room.py say what each is); PLAN.md is the room's
floor plan.

    python3 carts/afterhours/rooms/shopfloor/make_shopfloor.py

A department store's floor at night: the stopped escalators in a well in the middle, glass
counters, mannequins on plinths. The staff stair from the corridor comes in at the west end;
the service lift down to the food hall is in the back wall at the east end, behind a red staff
door. The blue card lies by the watch counter at the front of the east end. A night guard walks
a long round of the floor; a camera high on the back wall by the lift sweeps the east end. The thief comes
here twice: for the blue card (in and out by the stair), and later, with the red card, to the
lift.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
from greybox import patrol, posted, wall, write_room  # noqa: E402
import s2room  # noqa: E402

NAME = 'shopfloor'
P = 'sf_'
X = (-12.0, 12.0)
Z = (-4.75, 4.75)
WELL = (-2.0, -1.2, 2.0, 1.4)               # the escalator well: x0, z0, x1, z1 (its sides cut cones)
COUNTERS = [(-9.0, -2.6, -6.0, -1.9), (-9.0, 1.0, -6.0, 1.7),     # glass counters: low, cones pass
            (5.0, -2.6, 8.4, -1.9), (5.0, 1.0, 8.4, 1.7)]
MANNEQUINS = [(-5.2, 0.0), (5.0, 4.0), (10.0, -0.5)]               # on plinths: cones stop at them
MQ = 0.6
CARD = (9.6, -3.9)                          # the blue card, at the watch counter's end

ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_shop_floor', 'x': X, 'z': Z, 'entry': 'corridor',
    'doors': [
        {'id': 'corridor', 'side': 'w', 'at': (1.6, 2.8), 'to': 'sc_door_shop'},
        {'id': 'lift', 'side': 'n', 'at': (8.4, 9.8), 'to': 'fh_door_lift', 'card': 'red'},
    ],
    'props': [('well', 'block', WELL, 1.0)] +
             [(f'counter_{i}', 'glass', c, 0.95) for i, c in enumerate(COUNTERS)] +
             [(f'mannequin_{i}', 'pillar', (x - MQ / 2, z - MQ / 2, x + MQ / 2, z + MQ / 2), 1.8)
              for i, (x, z) in enumerate(MANNEQUINS)] +
             [('watch_counter', 'glass', (8.6, -4.75, 11.0, -4.3), 0.95)],
    'cards': [('blue', 'blue', CARD)],
    'guards': [
        # a long round: up the west side of the well, east along the back past the lift, down the
        # east end to the watch counter (a look west along the front), west along the front
        *patrol(P + 'guard_night', (-3.6, 0.0), [
            (P + 'wp_night_nw', (-3.6, 3.4), 0, 90),
            (P + 'wp_night_ne', (10.6, 3.4), 30, 180),
            (P + 'wp_night_se', (10.6, -3.3), 90, 270),
            (P + 'wp_night_sw', (-3.6, -3.3), 0, 0)], speed=1.1, sight=5.0, fov=60, turn_rate=220),
        # high in the back corner past the lift, sweeping between the lift and the east end
        posted(P + 'camera_lift', (11.5, 4.6), 200, 260, 90, 120, sight=9.0, fov=40, kind='camera', y=2.3),
    ],
}


# What the dressed room (NOTES.md) stands in play that the greybox did not: the table of knits
# (low) and the bag shelves on the back wall (0.32 m deep). They stop the thief; cones pass. In the
# wall map only, so ROOM (which dress_shopfloor.py reads) stays as it was.
DRESSED = [
    wall(P + 'wall_knits', 2.6, -0.75, 3.9, 0.35, blocks=False, h=0.72),
    wall(P + 'wall_shelves_w', -11.1, Z[1] - 0.32, -5.7, Z[1], blocks=False, h=1.6),
    wall(P + 'wall_shelves_e', -4.5, Z[1] - 0.32, -3.0, Z[1], blocks=False, h=1.6),
]


def main():
    recipes, placements, play = s2room.build(ROOM)
    play['entities'] += DRESSED
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
