#!/usr/bin/env python3
"""The aquarium, room 5: the life-support plant (greybox). Writes the room's recipes, placements and play file
beside itself (levels/greybox.py and levels/aquarium/aqroom.py say what each is); PLAN.md is the
room's floor plan.

    python3 carts/afterhours/rooms/aq_plant/make_aq_plant.py

The aquarium's basement, the size of the galleries above it: open sumps of sea water crossed
by grated walkways, sand filters like boilers along the back, pumps standing in the water. Lit
by work lamps; the water carries every sight across it, and the machinery is the only cover.
The plant engineer walks his round of the west half; a camera at the walkway's east end looks
back along it. Leg 5: in from quarantine's stair, out up the service stair to the kitchen.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
sys.path.insert(0, str(HERE.parents[1] / 'levels' / 'aquarium'))
from greybox import WALL_H, patrol, posted, write_room  # noqa: E402
import aqroom  # noqa: E402

NAME = 'aq_plant'
P = 'ap_'
X = (-9.0, 9.0)
Z = (-4.5, 4.5)
WALK_A = (-3.4, -2.2)                   # the front walkway's z
WALK_B = (1.4, 2.6)                     # the back walkway's z
CROSS = [(-5.2, -4.0), (-0.2, 1.0), (4.8, 6.0)]     # the cross walkways' x

ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_life_support_plant', 'x': X, 'z': Z, 'entry': 'quar',
    'doors': [
        {'id': 'quar', 'side': 'w', 'at': WALK_B, 'to': 'qt_door_plant'},
        {'id': 'kitchen', 'side': 'e', 'at': WALK_A, 'to': 'ak_door_plant'},
    ],
    'props': [
        ('channel', 'water', (-9.0, -4.5, 9.0, WALK_A[0]), 0.0),
        ('sump_0', 'water', (-9.0, WALK_A[1], CROSS[0][0], WALK_B[0]), 0.0),
        ('sump_1', 'water', (CROSS[0][1], WALK_A[1], CROSS[1][0], WALK_B[0]), 0.0),
        ('sump_2', 'water', (CROSS[1][1], WALK_A[1], CROSS[2][0], WALK_B[0]), 0.0),
        ('sump_3', 'water', (CROSS[2][1], WALK_A[1], 9.0, WALK_B[0]), 0.0),
        # the sand filters along the back
        ('filter_0', 'machine', (-7.2, 3.0, -5.2, 4.5), WALL_H),
        ('filter_1', 'machine', (-1.6, 3.0, 0.4, 4.5), WALL_H),
        ('filter_2', 'machine', (3.6, 3.0, 5.6, 4.5), WALL_H),
        # pumps on the front walkway's north half: their shadows from the camera
        ('pump_0', 'machine', (-2.0, -2.7, -1.4, -2.2), 1.0),
        ('pump_1', 'machine', (3.0, -2.7, 3.6, -2.2), 1.0),
        # pumps standing in the sumps by the cross walkways
        ('pump_2', 'machine', (-5.9, -0.9, -5.2, -0.2), 1.0),
        ('pump_3', 'machine', (1.0, 0.2, 1.7, 0.9), 1.0),
    ],
    'guards': [
        # the plant engineer: along the back walkway, down the middle cross walkway, west along the
        # front, up the west cross walkway
        *patrol(P + 'guard_engineer', (-4.6, 2.0), [
            (P + 'wp_eng_ne', (0.4, 2.0), 0, 90),
            (P + 'wp_eng_se', (0.4, -2.8), 60, 90),
            (P + 'wp_eng_sw', (-4.6, -2.8), 0, 0),
            (P + 'wp_eng_nw', (-4.6, 2.0), 60, 270)], speed=1.0, sight=5.0, fov=60, turn_rate=200),
        # at the front walkway's east end, looking back along it
        posted(P + 'camera_walk', (8.8, -2.8), 262, 320, 360, 90, sight=10.0, fov=36, phase=690, kind='camera', y=2.3),
    ],
}

SKETCH = {
    5: [(-8.1, 2.0, 'wait'), (-0.3, 2.0, 'wait'), (0.4, 2.0), (0.4, 1.0, 'wait'), (0.4, -3.0), (8.3, -3.0), (8.7, -2.8)],
}

def main():
    recipes, placements, play = aqroom.build(ROOM)
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
