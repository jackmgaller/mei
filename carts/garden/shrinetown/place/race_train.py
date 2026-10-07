"""The last train (★5) on track 2, and the arrival train on track 1: their paths and their asset.

Not a placement zone (place/__init__.py's ZONES does not list it): place/station.py adds the path
to the world (rows 0-1, notes/gen_town.py), and game.py's mover follows it (RACE_PATH) drawn as
RACE_TRAIN with RACE_TRAIN_COL.

The train is `train_emu_pair` (assets/train_emu_car/make_train.py): two cars at train_emu_car's
level 1 (an entity draws its mesh's level 0 only), 160 triangles, with one collision block over
both. The path is the set's middle along track 2: 2.0 m north of the viaduct's line (z 10) on
the standard spans, swinging out to 4.1 (z 12.1) at the station along the west taper's S (x 120
to 136, assets/viaduct_station_span/make_station_viaduct.py: z = 8 + 2 + 2.1 smoothstep((x -
120) / 16)). A mover is not turned along its path, so on the taper the cars slide sideways with
the set's middle, their far ends up to 2.1 m off the rails for the 16 m the middle takes.

It starts with the set's middle at x 24 (its west end at x 4, on the deck; on track 2 the cars
clear signal gantry 0's north column, z 13.15-13.45) and ends at the platform's middle, x 160.
"""
DECK = 9.0                       # rail level (place/station.py DECK)
LINE_Z = 8.0                     # the viaduct's centre line west of the station
TRACK_STD, TRACK_WIDE = 2.0, 4.1
TAPER = (120.0, 136.0)           # the west taper's ends (x)
START, STOP = 24.0, 160.0        # the set's middle: where it comes in from, where it stands
STEP = 2.0                       # the path's points along the taper
NAME = 'race_track2'
ASSET, COLLISION = 'train_emu_pair', 'train_emu_pair_col'


def track2_z(x):
    """Track 2's z at x, west of the station's middle."""
    t = min(max((x - TAPER[0]) / (TAPER[1] - TAPER[0]), 0.0), 1.0)
    s = t * t * (3.0 - 2.0 * t)
    return LINE_Z + TRACK_STD + (TRACK_WIDE - TRACK_STD) * s


def path_points(x0=START, x1=STOP):
    """[x, y, z] from x0 to x1 along track 2: the ends, and every STEP m on the taper."""
    xs = [x0] + [TAPER[0] + STEP * k for k in range(int((TAPER[1] - TAPER[0]) / STEP) + 1)] + [x1]
    xs = sorted({round(x, 3) for x in xs if x0 <= x <= x1})
    return [[x, DECK, round(track2_z(x), 3)] for x in xs]


PATH = path_points()


# ---- the arrival train (DESIGN.md 12.10, "Arrive by train"; carts/garden/arrival.akr): the same
# two cars on track 1, which is free (the parked train there is gone). Track 1 mirrors track 2
# about the line (z 8): z 6 on the standard spans, 3.9 at the station, through the west taper's
# S (x 120-136) and the east taper's (x 184-200, back out to 6). The set's middle comes in from
# x 134 and stops at x 161.7, so that car_w's east door (the set's x - 3.7, make_train.py's
# DOORS) is at x 158: the platform's one clear way north from track 1's edge (between the column
# at x 155 and the stairwell's low wall at 160.65; the east name board at 166.25-168.75, the soba
# stand and the benches stand on the platform's middle line), past the stair's head. It leaves
# east from there to x 262, its front at the last standard span's end (x 280, where the line
# curves north), and is hidden there. Both paths are added to the world by place/station.py.
ARRIVE_IN, ARRIVE_OUT = 'arrive_track1_in', 'arrive_track1_out'
ARRIVE_FROM, ARRIVE_STOP, ARRIVE_TO = 134.0, 161.7, 262.0
EAST_TAPER = (184.0, 200.0)


def track1_z(x):
    """Track 1's z at x: the line's z less track 2's offset, either taper."""
    if x <= STOP:
        return round(2 * LINE_Z - track2_z(x), 3)
    t = min(max((EAST_TAPER[1] - x) / (EAST_TAPER[1] - EAST_TAPER[0]), 0.0), 1.0)
    s = t * t * (3.0 - 2.0 * t)
    return round(LINE_Z - TRACK_STD - (TRACK_WIDE - TRACK_STD) * s, 3)


def track1_points(x0, x1):
    """[x, y, z] from x0 to x1 along track 1: the ends, and every STEP m on either taper."""
    tapers = [a + STEP * k for a, b in (TAPER, EAST_TAPER) for k in range(int((b - a) / STEP) + 1)]
    xs = sorted({round(x, 3) for x in [x0, x1] + tapers if x0 <= x <= x1})
    return [[x, DECK, track1_z(x)] for x in xs]


ARRIVE_PATHS = {ARRIVE_IN: track1_points(ARRIVE_FROM, ARRIVE_STOP),
                ARRIVE_OUT: track1_points(ARRIVE_STOP, ARRIVE_TO)}
