#!/usr/bin/env python3
"""Stage 2, room 2: the projection booth (greybox). Writes the room's recipes, placements and play
file beside itself (levels/greybox.py and levels/s2room.py say what each is); PLAN.md is the
room's floor plan.

    python3 carts/afterhours/rooms/booth/make_booth.py

Up the stair behind the corridor's blue staff door: a long, low room over the back of the
cinema, its two projectors facing the ports in the west wall (the film running), the rewind
bench along the back wall, racks of film cans. The projectionist walks round his west machine
and stops between the two to watch the east one. The red card (the service lift's) lies at the far end of the bench. In and out by the same door.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
from greybox import patrol, wall, write_room  # noqa: E402
import s2room  # noqa: E402

NAME = 'booth'
P = 'pb_'
X = (-6.0, 6.0)
Z = (-3.0, 3.0)
PROJECTORS = [(-3.9, -0.4, -3.1, 1.0), (0.1, -0.4, 0.9, 1.0)]     # x0, z0, x1, z1: they stop cones
BENCH = (-5.6, 2.4, -1.8, 3.0)                                     # the rewind bench: low
RACKS = (2.0, 2.1, 4.6, 3.0)                                       # film cans: tall
CARD = (-5.0, 1.9)

ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_projection_booth', 'x': X, 'z': Z, 'entry': 'corridor',
    'doors': [
        {'id': 'corridor', 'side': 'e', 'at': (-2.4, -1.2), 'to': 'sc_door_booth'},
    ],
    'props': [(f'projector_{i}', 'machine', p, 1.6) for i, p in enumerate(PROJECTORS)] +
             [('bench', 'low', BENCH, 0.9), ('racks', 'block', RACKS, 2.0),
              # the ports in the west wall, over the cinema (drawn only)
              ('ports', 'mark', (-6.0, -0.2, -5.7, 1.4), 0.0)],
    'cards': [('red', 'red', CARD)],
    'guards': [
        # round his west machine: along the front, up the far end past the bench, back along the
        # bench and out between the machines, where he stops to watch the east one
        *patrol(P + 'guard_projectionist', (-1.8, -1.4), [
            (P + 'wp_proj_a', (-1.8, -1.4), 120, 55),
            (P + 'wp_proj_b', (-5.0, -1.4), 0, 0),
            (P + 'wp_proj_c', (-5.0, 1.6), 0, 90),
            (P + 'wp_proj_d', (-1.8, 1.6), 0, 180)], speed=1.0, sight=5.0, fov=60, turn_rate=220),
    ],
}


# What the dressed room (NOTES.md) stands in play that the greybox did not: each projector's lens,
# 0.18 m out of its west face at 0.86 m (it stops the thief; cones pass, it is small). In the wall
# map only: dress_booth.py draws them from PROJECTORS, so ROOM stays as it was.
def lens(k):
    x0, z0, x1, z1 = PROJECTORS[k]
    zc = (z0 + z1) / 2 - 0.25
    return wall(f'{P}wall_lens_{k}', x0 - 0.17, zc - 0.07, x0, zc + 0.07, blocks=False, h=0.93)


DRESSED = [lens(0), lens(1)]


def main():
    recipes, placements, play = s2room.build(ROOM)
    play['entities'] += DRESSED
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
