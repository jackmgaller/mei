#!/usr/bin/env python3
"""The aquarium, room 1: the great tank (greybox), on two levels. Writes the room's recipes,
placements and play file beside itself (levels/greybox.py and levels/aquarium/aqroom.py say
what each is); PLAN.md is the room's floor plan.

    python3 carts/afterhours/rooms/aq_great/make_aq_great.py

The aquarium's main gallery: a long dark room whose back wall is one acrylic window into the
great tank, the only light a blue band on the floor in front of it. Benches face the window;
a column holds up the roof. A night guard with a torch walks round the gallery. Over the tank,
behind and above the window, run the keepers' catwalks: a rim along the tank's front edge, a
walk along its back, two bridges between them and a feeding platform. The thief crosses the
floor on leg 1 (in from the entrance hall, out to the jellyfish gallery) and comes back on leg 8
along the rim, above the gallery he crossed, from the tank tops to the hall's mezzanine.

The room's frame: x right, z away from the camera, the floor y = 0, the origin in its middle.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
sys.path.insert(0, str(HERE.parents[1] / 'levels' / 'aquarium'))
from greybox import WALL_H, patrol, posted, write_room  # noqa: E402
import aqroom  # noqa: E402

NAME = 'aq_great'
P = 'ag_'
X = (-10.0, 10.0)
Z = (-4.0, 5.0)
UPPER = 3.2
WINDOW = (-10.0, 1.0, 10.0, 1.3)       # the acrylic window (glass, floor to catwalk)
RIM = (-10.0, 1.3, 10.0, 2.6)          # level 1: the catwalk along the tank's front edge
BACK = (-10.0, 4.0, 10.0, 5.0)         # level 1: the walk along the tank's back
BRIDGES = [(-6.0, 2.6, -4.8, 4.0), (4.8, 2.6, 6.0, 4.0)]
FEED = (-1.0, 2.6, 1.0, 3.3)           # level 1: the feeding platform, out over the water

ROOM = {
    'name': NAME, 'prefix': P, 'title': 'the_great_tank', 'x': X, 'z': Z, 'entry': 'hall',
    'dark': True, 'upper': UPPER,
    'doors': [
        {'id': 'hall', 'side': 'w', 'at': (-1.4, -0.2), 'to': 'ah_door_great'},
        {'id': 'jelly', 'side': 'e', 'at': (-3.2, -2.0), 'to': 'aj_door_great'},
        {'id': 'tops', 'side': 'e', 'at': (1.4, 2.6), 'level': 1, 'to': 'at_door_great'},
        {'id': 'hall_up', 'side': 'w', 'at': (1.4, 2.6), 'level': 1, 'to': 'ah_door_catwalk'},
    ],
    'props': [
        ('window', 'glass', WINDOW, WALL_H),
        ('bench_w', 'seat', (-6.6, -1.2, -3.6, -0.7), 0.45),
        ('bench_e', 'seat', (3.6, -1.2, 6.6, -0.7), 0.45),
        ('column', 'pillar', (-0.4, -2.6, 0.4, -1.8), WALL_H),
    ],
    'walks': [RIM, BACK, *BRIDGES, FEED],
    'upper_props': [
        ('water_w', 'water', (-10.0, 2.6, -6.0, 4.0), 0.0),
        ('water_mw', 'water', (-4.8, 2.6, -1.0, 4.0), 0.0),
        ('water_m', 'water', (-1.0, 3.3, 1.0, 4.0), 0.0, ['left', 'right']),
        ('water_me', 'water', (1.0, 2.6, 4.8, 4.0), 0.0),
        ('water_e', 'water', (6.0, 2.6, 10.0, 4.0), 0.0),
        # the feed hopper on the platform: it blocks
        ('hopper', 'machine', (-0.9, 2.65, -0.3, 3.25), 1.2),
    ],
    'lights': [
        # the window's blue band on the gallery floor
        ('window', (-10.0, -0.7, 10.0, 1.0), 0, None),
        # on the rim: the tank's work lamps, two pools
        ('rim_w', (-8.6, 1.3, -6.6, 2.6), 1, None),
        ('rim_m', (-2.2, 1.3, 2.2, 2.6), 1, None),
    ],
    'guards': [
        # the gallery's night guard with a torch: round the benches and the column
        *aqroom.torch(patrol(P + 'guard_floor', (-1.0, -3.0), [
            (P + 'wp_floor_se', (8.4, -3.0), 0, 0),
            (P + 'wp_floor_ne', (8.4, 0.2), 30, 270),
            (P + 'wp_floor_nw', (-8.4, 0.2), 0, 180),
            (P + 'wp_floor_sw', (-8.4, -3.0), 30, 90)], speed=1.0, sight=4.5, fov=60, turn_rate=200)),
        # on the window's east pier, a camera looking west along the window (it sees the blue band)
        posted(P + 'camera_window', (9.7, 0.85), 228, 272, 150, 90, sight=13.0, fov=24, kind='camera', y=2.3),
        # on the back walk, a keeper with a torch, end to end; at each end he looks across the
        # water at the rim
        *aqroom.on_level(aqroom.torch(patrol(P + 'guard_keeper', (3.0, 4.5), [
            (P + 'wp_keeper_w', (-6.5, 4.5), 90, 180),
            (P + 'wp_keeper_e', (5.0, 4.5), 90, 180)], speed=1.0, sight=4.0, fov=50, turn_rate=200)), 1),
        # a camera at the back walk's west end, looking across the water at the rim's two lamps in
        # turn (it sees only their light)
        aqroom.on_level(posted(P + 'camera_rim', (-9.7, 4.7), 105, 150, 150, 90, sight=12.5, fov=30, phase=280,
                               kind='camera', y=UPPER + 2.3), 1),
    ],
}

# The intended ways through (levels/aquarium/sketch.py draws them): leg 1 on the floor, leg 8 on
# the rim.
SKETCH = {
    1: [(-8.9, -0.8), (-8.0, -3.3), (1.5, -3.3, 'wait'), (8.0, -3.3), (8.6, -2.6), (9.8, -2.6)],
    8: [(8.9, 2.0), (2.8, 2.0, 'wait'), (-2.45, 2.0, 'wait'), (-9.0, 2.0), (-9.8, 2.0)],
}


def main():
    recipes, placements, play = aqroom.build(ROOM)
    write_room(HERE, NAME, recipes, placements, play)


if __name__ == '__main__':
    main()
