"""The last train's two cars (★5) on track 2: their paths and their mover entities.

Not a placement zone (place/__init__.py's ZONES does not list it): place/station.py adds the
paths to the world (rows 0-1, notes/gen_town.py), and game.py takes the entities from
`movers()` in place of its grey-box `train_5`.

Each car is a mover of its own, `train_emu_car_mover` (train_emu_car's level 1, 80 triangles: an
entity draws its mesh's level 0 only) with the car's collision, following a path of its own so
that each car keeps to the rails: track 2 is 2.0 m north of the viaduct's line (z 10) on the
standard spans and swings out to 4.1 (z 12.1) at the station along the west taper's S (x 120 to
136, assets/viaduct_station_span/make_station_viaduct.py: z = 8 + 2 + 2.1 smoothstep((x - 120) /
16)). A mover is not turned along its path, so on the taper a car slides 2.1 m sideways over its
16 m, at most 0.2 m off the rails at its ends.

The pair stands parked with its west end at x 24 (4 m east of signal gantry 0's columns at
x 20, which the grey box's train stood through) and comes in to stop with its middle at the
platform's (x 160): the east car (cab east, yaw 0) from x 54 to 170, the west car (turned, cab
west) from x 34 to 150. Both paths are 116 m along x with the same S in them, so the same leg
time keeps the cars 20 m apart, coupler to coupler.
"""
import math

DECK = 9.0                       # rail level (place/station.py DECK)
LINE_Z = 8.0                     # the viaduct's centre line west of the station
TRACK_STD, TRACK_WIDE = 2.0, 4.1
TAPER = (120.0, 136.0)           # the west taper's ends (x)
CAR = 20.0                       # a car over its couplers
PARKED = 44.0                    # the pair's middle, parked
STOP = 160.0                     # the pair's middle, at the platform
ASSET, COLLISION = 'train_emu_car_mover', 'train_emu_car_col'
STEP = 2.0                       # the paths' points along the taper


def track2_z(x):
    """Track 2's z at x, west of the station's middle."""
    t = min(max((x - TAPER[0]) / (TAPER[1] - TAPER[0]), 0.0), 1.0)
    s = t * t * (3.0 - 2.0 * t)
    return LINE_Z + TRACK_STD + (TRACK_WIDE - TRACK_STD) * s


def path_points(x0, x1):
    """[x, y, z] from x0 to x1 along track 2: the ends, and every STEP m on the taper."""
    xs = [x0] + [TAPER[0] + STEP * k for k in range(int((TAPER[1] - TAPER[0]) / STEP) + 1)] + [x1]
    xs = sorted({round(x, 3) for x in xs if x0 <= x <= x1})
    return [[x, DECK, round(track2_z(x), 3)] for x in xs]


# name: (car's middle parked, at the platform, yaw)
CARS = {'race_train_e': (PARKED + CAR / 2, STOP + CAR / 2, 0.0),
        'race_train_w': (PARKED - CAR / 2, STOP - CAR / 2, 180.0)}
PATHS = {name: path_points(a, b) for name, (a, b, _) in CARS.items()}


def movers(period, pause, start, delay, mode='pingpong'):
    """The two cars' mover entities (the garden's game schema's `mover`: carts/garden/world/
    garden.game.mochi), each at its path's first point, with the timing game.py gives the train."""
    out = []
    for name, (_, _, yaw) in CARS.items():
        x, y, z = PATHS[name][0]
        e = {'id': name, 'type': 'mover', 'position': [x, y, z], 'asset': ASSET,
             'collision': COLLISION,
             'params': {'path': name, 'period': period, 'pause': pause, 'start': start,
                        'delay': delay}}
        if mode != 'pingpong':
            e['params']['mode'] = mode
        if yaw:
            e['yaw'] = yaw
        out.append(e)
    return out


def path_length(name):
    p = PATHS[name]
    return sum(math.dist(a, b) for a, b in zip(p, p[1:]))


assert abs(path_length('race_train_e') - path_length('race_train_w')) < 1e-6
