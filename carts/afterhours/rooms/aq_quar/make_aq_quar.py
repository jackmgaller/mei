#!/usr/bin/env python3
"""The aquarium, room 4: quarantine (greybox). Writes the room's recipes, placements and play file
beside itself (levels/greybox.py and levels/aquarium/aqroom.py say what each is); PLAN.md is the
room's floor plan.

    python3 carts/afterhours/rooms/aq_quar/make_aq_quar.py

Behind the public galleries: the quarantine room, two long rows of holding tanks on stands,
dark but for the ultraviolet sterilisers over the rows, which switch between the rows every three
seconds. A keeper with a torch does his rounds of the tanks; a camera over the stair door down to
the plant watches the room. Leg 4: in by the staff door from the ocean gallery, down the stair.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
sys.path.insert(0, str(HERE.parents[1] / 'levels' / 'aquarium'))
from greybox import WALL_H, patrol, posted, write_room  # noqa: E402
import aqroom  # noqa: E402

NAME = 'aq_quar'
P = 'qt_'
X = (-6.5, 6.5)
Z = (-4.0, 4.0)
ROW_A = (-4.2, 1.2, 4.2, 2.0)           # the back row of tanks (glass)
ROW_B = (-4.2, -1.4, 4.2, -0.6)         # the front row
UV = (480, 240)                         # each row's steriliser: on 240 ticks of every 480, in turn

ROOM = {
    'name': NAME, 'prefix': P, 'title': 'quarantine', 'x': X, 'z': Z, 'entry': 'ocean', 'dark': True,
    'doors': [
        {'id': 'ocean', 'side': 'w', 'at': (1.8, 3.0), 'to': 'ao_door_quar'},
        {'id': 'plant', 'side': 'e', 'at': (-3.4, -2.2), 'to': 'ap_door_quar'},
    ],
    'props': [
        ('row_a', 'glass', ROW_A, 1.2),
        ('row_b', 'glass', ROW_B, 1.2),
        ('filter_a', 'machine', (4.25, 1.0, 5.0, 2.2), 1.6),
        ('filter_b', 'machine', (4.25, -1.6, 5.0, -0.4), 1.6),
        ('desk', 'low', (-6.5, -4.0, -4.8, -3.0), 0.8),
    ],
    'lights': [
        ('uv_a', (-4.4, 1.0, 4.4, 3.2), 0, (UV[0], UV[1], 0)),
        ('uv_b', (-4.4, -1.8, 4.4, 1.0), 0, (UV[0], UV[1], 240)),
        ('exit', (5.0, -4.0, 6.5, -1.6), 0, None),
    ],
    'guards': [
        # the keeper with a torch: east along the front, up the east end, west along the back, down
        *aqroom.torch(patrol(P + 'guard_keeper', (3.0, -2.7), [
            (P + 'wp_keeper_se', (5.6, -2.7), 0, 0),
            (P + 'wp_keeper_ne', (5.6, 3.1), 60, 270),
            (P + 'wp_keeper_nw', (-5.0, 3.2), 0, 180),
            (P + 'wp_keeper_sw', (-5.0, -2.7), 60, 90)], speed=0.9, sight=4.5, fov=60, turn_rate=200)),
        # over the stair door, looking back across the room (sees only where it is lit)
        posted(P + 'camera_stair', (6.3, -3.8), 280, 330, 120, 90, sight=11.0, fov=40, kind='camera', y=2.3),
    ],
}

SKETCH = {
    4: [(-5.4, 2.4), (-4.9, 0.3, 'wait'), (4.6, 0.3, 'wait'), (5.7, 0.3), (5.7, -2.8, 'wait'), (6.4, -2.8)],
}

def main():
    recipes, placements, play = aqroom.build(ROOM)
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
