"""The station zone (PLACE_SPLIT.md): the real assets in place of the grey boxes south of z 40
and east of x 64, and the whole viaduct wherever it runs.

Called by the placement hook (place/__init__.py) from three generators:

- town(ns), from notes/gen_town.py (rows 0-1): the viaduct's pieces in those rows, the station
  (concourse with its stairs and ticket gates, platform, spans and tapers, a two-car train at
  the platform, the signal gantries), the plaza (danchi, pachinko parlour, koban, konbini, bus
  stop, newsstand, bike racks and bicycles, taxi rank, phone booth, postbox, vending machines,
  benches, planters, the konbini's corner pole), the parapet rails along the real parapets, the
  coins the real stairs and canopy moved, and the road's skew under the underpass;
- core(ns), from assets/greybox/core/gen_core.py (rows 2-3): the viaduct's two curves past the
  underpass, where it leaves the level, and the wall that closes its deck;
- world(ns), from make_world.py: the asset directories.

The viaduct is a chain of 16 m pieces from x -8 along z 8 (asset frames in the docstrings of
assets/viaduct_span_16/make_viaduct.py and make_station_viaduct.py): eight standard spans, the
west taper, the three station spans (x 136-184, joints at x = 8 mod 16), the east taper, five
standard spans to x 280, three curves (90 degrees left, R 30.56), four spans north along
x 310.56, the underpass over the front road (24 m, the road through it 25 degrees north of east)
and two curves right, out of the level to the east between the rims (z 132-154). DESIGN.md
12.6 has what changed from the grey box and why.
"""
import math

DECK = 9.0                      # the deck (rail level)
PARAPET_Y = 10.2                # parapet tops: the rails
R_CURVE = 16.0 / (math.pi / 6)  # viaduct_curve_16: 30 degrees in 16 m at the centre line
# viaduct_curve_16's ends in its own frame, (+-7.909, 1.042), heading +-15 degrees there
CURVE_END = (R_CURVE * math.sin(math.pi / 12), R_CURVE * (1 - math.cos(math.pi / 12)))
HALF_STD, HALF_WIDE = 5.875, 7.475   # the parapet rails off the centre line: standard, station
UNDERPASS = 24.0
END_X = 315.0                   # the deck's closing wall stands where the centre line reaches this x

# The town's frame of the station: its middle (concourse, platform, the stair span) at x 160.
STATION_X, STATION_Z = 160.0, 8.0
STAIR_GAPS = [(148.35, 151.65), (168.35, 171.65)]    # the north parapet's gaps at the outside stairs
NORTH_PARAPET_Z = 15.475        # station_concourse's north parapet (its z -7.35..-7.6 at yaw 180)
SOUTH_PARAPET_Z = 0.525         # the station spans' south parapet (z 7.35..7.6, turned)


def r3(v):
    return round(v + 0.0, 3) + 0.0


def yaw_of(heading):
    """The placement yaw that turns an asset's +X to a world heading (degrees from +X toward +Z):
    mesh_at's yaw turns -Z toward -X, so +X goes to (cos y, -sin y)."""
    return (-heading) % 360.0


def turn(x, z, yaw):
    """A point in an asset's frame, turned by the placement's yaw."""
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return x * c + z * s, -x * s + z * c


# ------------------------------------------------------------------ the viaduct's chain
def viaduct():
    """The pieces [(asset, x, z, yaw)] and the centre line [(x, z, heading, half width)] (sampled
    every 5 degrees on curves), from x -8 at z 8 heading east."""
    pieces, line = [], []
    p, h = [-8.0, 8.0], 0.0

    def point(half):
        line.append((p[0], p[1], h, half))

    def straight(asset, length=16.0, yaw=None, halves=(HALF_STD, HALF_STD)):
        nonlocal h
        d = (math.cos(math.radians(h)), math.sin(math.radians(h)))
        pieces.append((asset, p[0] + d[0] * length / 2, p[1] + d[1] * length / 2,
                       yaw_of(h) if yaw is None else yaw))
        point(halves[0])
        p[0] += d[0] * length; p[1] += d[1] * length
        point(halves[1])

    def curve(left):
        nonlocal h
        mid = h + (15 if left else -15)
        # left: the arc's entry is its -X end; right: the piece turned round, entry at its +X end
        yaw = yaw_of(mid) if left else yaw_of(mid + 180)
        ex, ez = turn(-CURVE_END[0] if left else CURVE_END[0], CURVE_END[1], yaw)
        ox, oz = p[0] - ex, p[1] - ez
        xx, xz = turn(CURVE_END[0] if left else -CURVE_END[0], CURVE_END[1], yaw)     # its exit
        pieces.append(('viaduct_curve_16', ox, oz, yaw))
        centre_side = 1 if left else -1                     # the centre of curvature: left or right
        cx = p[0] - centre_side * R_CURVE * math.sin(math.radians(h))
        cz = p[1] + centre_side * R_CURVE * math.cos(math.radians(h))
        for k in range(1, 7):
            hk = h + centre_side * 5 * k
            line.append((cx + centre_side * R_CURVE * math.sin(math.radians(hk)),
                         cz - centre_side * R_CURVE * math.cos(math.radians(hk)), hk, HALF_STD))
        p[0], p[1] = line[-1][0], line[-1][1]
        assert abs(ox + xx - p[0]) < 0.01 and abs(oz + xz - p[1]) < 0.01, (ox + xx, oz + xz, p)
        h += centre_side * 30

    for _ in range(8):
        straight('viaduct_span_16')                                    # x -8 .. 120
    straight('viaduct_station_taper', yaw=0.0, halves=(HALF_STD, HALF_WIDE))
    for a in ('viaduct_station_span', 'viaduct_station_span_stair', 'viaduct_station_span'):
        straight(a, yaw=180.0, halves=(HALF_WIDE, HALF_WIDE))         # x 136 .. 184
    straight('viaduct_station_taper', yaw=180.0, halves=(HALF_WIDE, HALF_STD))
    for _ in range(5):
        straight('viaduct_span_16')                                    # x 200 .. 280
    for _ in range(3):
        curve(True)                                                    # to x 310.56, z 38.56, north
    for _ in range(4):
        straight('viaduct_span_16')                                    # z 38.56 .. 102.56
    # the underpass: its +X to the south (yaw 90), so the road runs 25 degrees north of east
    straight('viaduct_underpass', UNDERPASS, yaw=90.0)                 # z 102.56 .. 126.56
    for _ in range(2):
        curve(False)                                                   # east, out of the level
    return pieces, line


PIECES, LINE = viaduct()


def line_to(x_end):
    """The centre line cut where it first reaches x = x_end past the underpass (the closing wall)."""
    out = []
    for a, b in zip(LINE, LINE[1:]):
        out.append(a)
        if a[1] > 110 and a[0] < x_end <= b[0]:
            t = (x_end - a[0]) / (b[0] - a[0])
            out.append((x_end, a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2]), a[3]))
            return out
    raise ValueError('the line does not reach x %s' % x_end)


CUT = line_to(END_X)
END = CUT[-1]                    # (x, z, heading, half) where the wall stands


def distinct(points):
    """The points without one that repeats the one before it (pieces share their ends)."""
    out = []
    for q in points:
        if not out or abs(out[-1][0] - q[0]) > 1e-6 or abs(out[-1][1] - q[1]) > 1e-6:
            out.append(q)
    return out


def offset(points, side, x0=0.5):
    """A parapet rail: the centre line moved its half width to the left (side 1) or right (-1),
    from x0 at the west end."""
    out = []
    for x, z, h, half in points:
        nx, nz = -math.sin(math.radians(h)), math.cos(math.radians(h))
        out.append((x + side * half * nx, z + side * half * nz))
    out[0] = (x0, out[0][1])
    return out


def split(rail, gaps):
    """The rail cut at the x ranges of the gaps (on the straight through the station)."""
    parts, cur = [], [rail[0]]
    for a, b in zip(rail, rail[1:]):
        for g0, g1 in gaps:
            if a[0] < g0 < b[0] and abs(a[1] - b[1]) < 1e-6:
                cur.append((g0, a[1])); parts.append(cur); cur = [(g1, a[1])]
        cur.append(b)
    parts.append(cur)
    return parts


def rails():
    """{name: [(x, z)]} of the parapet rails (y 10.2): the south one whole, the north one in three."""
    pts = distinct(line_to(END_X - 0.5))     # stopping 0.5 m short of the closing wall
    south = offset(pts, -1)
    north = offset(pts, 1)
    # (through the station both are the wide section's: z 15.475 on station_concourse, 0.525)
    assert all(abs(z - NORTH_PARAPET_Z) < 1e-6 for x, z in north if 136 <= x <= 184)
    assert all(abs(z - SOUTH_PARAPET_Z) < 1e-6 for x, z in south if 136 <= x <= 184)
    nw, nm, ne = split(north, STAIR_GAPS)
    return {'parapet_s': south, 'parapet_n_w': nw, 'parapet_n_m': nm, 'parapet_n_e': ne}


# ------------------------------------------------------------------ what goes where
COL = {   # each real asset's collision (its _col companion, or none for a prop walked through)
    'town_taxi_rank': 'self', 'mamachari': 'none', 'town_potted_plants': 'none',
}


def col(asset):
    return COL.get(asset, asset + '_col')


TRAIN_Z = STATION_Z - 4.1        # track 1, the south one, beside the island platform
GANTRIES = [(20.0, STATION_Z, 0.0), (310.56, 98.0, 270.0)]     # x, z, yaw: the line's two ends
GANTRY_LADDER = (-0.45, 5.3)     # the pole in front of the north column's ladder (its frame)

PLAZA = [  # (id, asset, x, y, z, yaw)
    ('danchi', 'danchi', 78.0, 0.0, 26.0, 0.0),
    ('pachinko', 'pachinko_parlour', 100.5, 0.0, 26.0, 270.0),         # its front to the east
    ('koban', 'koban', 122.0, 0.0, 24.0, 270.0),                       # its front to the east
    ('konbini', 'street_konbini', 196.0, 0.0, 25.0, 180.0),            # its front to the plaza
    ('bus_stop', 'bus_stop', 140.0, 0.0, 36.0, 0.0),
    ('newsstand', 'newsstand', 141.0, 0.0, 18.7, 180.0),
    ('taxi_rank', 'town_taxi_rank', 184.5, 0.0, 37.5, 0.0),
    ('phone_booth', 'phone_booth', 114.5, 0.0, 36.0, 270.0),
    ('postbox', 'postbox', 132.5, 0.0, 37.0, 0.0),
    ('vending_konbini', 'street_vending_machine', 179.1, 0.0, 29.8, 90.0),   # route D's step
    ('vending_station_0', 'street_vending_machine', 154.0, 0.0, 15.6, 180.0),
    ('vending_station_1', 'street_vending_machine', 155.0, 0.0, 15.6, 180.0),
    ('bench_0', 'town_bench', 126.0, 0.0, 38.5, 0.0),
    ('bench_1', 'town_bench', 192.0, 0.0, 38.5, 0.0),
    ('planters_koban', 'town_potted_plants', 122.0, 0.0, 27.2, 180.0),
    ('planters_station', 'town_potted_plants', 165.5, 0.0, 15.7, 180.0),
    ('pole_konbini0', 'town_utility_pole_transformer', 210.0, 0.0, 33.0, -2.42),   # wires to (207, 104)
]
# bicycle shelters against the concourse and the viaduct (backs to the south), with the town's
# mamachari in some of their five slots (bike_rack's docstring: local x -1.2 .. 1.2, z 0, y 0.1);
# the east two stand roof edge to roof edge
RACKS = [(131.0, 17.2, (1, 3)), (145.3, 17.2, (0, 2, 4)), (173.5, 17.2, (1, 3)), (176.9, 17.2, (2,))]
SLOTS = [-1.2, -0.6, 0.0, 0.6, 1.2]

GREY = [  # the grey boxes these replace (gen_town's placement ids)
    'station_concourse', 'station_platform', 'station_stair_0', 'station_stair_1', 'vending',
    'bus_stop', 'koban', 'danchi', 'danchi_tank', 'danchi_stair', 'pachinko', 'konbini',
    'konbini_sign', 'pole_konbini0']

# Coins on what the real assets moved (DESIGN.md 12.6): the outside stairs are at x 150 and 170
# with their treads at 0.5 (34.6 - z); the canopy's top is 13.47 over the platform's middle. (Star
# 5 and the platform's trigger are game.py's, on the platform's floor, 10.0.)
COIN_LIFT = 0.7
COINS = {f'coin_stair{k}_{j}': (x, 0.5 * (34.6 - z) + COIN_LIFT, z)
         for k, x in enumerate((150.0, 170.0)) for j, z in enumerate((29.0, 23.0, 17.0))}
COINS['red_canopy'] = (172.0, 13.47 + COIN_LIFT, 8.0)


def _put(ns, cells_put, pid, asset, x, y, z, yaw=0.0, collision=None, layer=None, merge=False):
    # to 0.1 mm: the viaduct's pieces meet edge to edge (at 1 mm their parapets' joints crack)
    p = {'id': pid, 'asset': asset, 'position': [round(v + 0.0, 4) + 0.0 for v in (x, y, z)]}
    if yaw % 360:
        p['yaw'] = round(yaw % 360, 4)
    if layer:
        p['layer'] = layer
    if merge:
        p['merge'] = True
    p['collision'] = collision or col(asset)
    cells_put(pid, p, x, z)


# ------------------------------------------------------------------ stage: notes/gen_town.py
def town(ns):
    cells, paths = ns['cells'], ns['paths']

    def remove(pred):
        for c in cells.values():
            c['placements'] = [p for p in c['placements'] if not pred(p)]

    def put_town(pid, p, x, z):
        cid, at = ns['cell_of'](x, z)
        c = ns['cell'](cid, at)
        assert pid not in {q['id'] for q in c['placements']}, pid
        c['placements'].append(p)

    def drop_entity(eid):
        for c in cells.values():
            c['entities'] = [e for e in c['entities'] if e['id'] != eid]
        ns['entities_n'].discard(eid)

    # -- the grey boxes go: the viaduct's spans, the station, the plaza's buildings
    remove(lambda p: p['id'].startswith('viaduct_') or p['id'] in GREY)

    # -- the viaduct's pieces in the town's rows
    for k, (asset, x, z, yaw) in enumerate(PIECES):
        if z < ns['ROW_MAX']:
            _put(ns, put_town, f'viaduct_{k}', asset, x, 0.0, z, yaw)

    # -- the station: concourse (its stairs, hall, platform stair), ticket gates, platform
    _put(ns, put_town, 'station_concourse', 'station_concourse', STATION_X, 0.0, STATION_Z, 180.0)
    _put(ns, put_town, 'ticket_gates', 'ticket_gates', STATION_X, 0.06, 7.4, 180.0)
    _put(ns, put_town, 'station_platform', 'station_platform', STATION_X, DECK, STATION_Z, 0.0)
    # a two-car local standing at the platform on track 1: cars 20 m long, cabs at the ends
    _put(ns, put_town, 'train_car_e', 'train_emu_car', STATION_X + 10, DECK, TRAIN_Z, 0.0)
    _put(ns, put_town, 'train_car_w', 'train_emu_car', STATION_X - 10, DECK, TRAIN_Z, 180.0)
    for k, (gx, gz, gyaw) in enumerate(GANTRIES):
        _put(ns, put_town, f'signal_gantry_{k}', 'signal_gantry', gx, DECK, gz, gyaw)
        lx, lz = turn(*GANTRY_LADDER, gyaw)
        ns['entity'](f'pole_gantry_{k}', 'pole', gx + lx, DECK + 0.2, gz + lz, {'height': 4.25})

    # -- the plaza
    for pid, asset, x, y, z, yaw in PLAZA:
        _put(ns, put_town, pid, asset, x, y, z, yaw)
    for k, (x, z, slots) in enumerate(RACKS):
        _put(ns, put_town, f'bike_rack_{k}', 'bike_rack', x, 0.0, z, 180.0)
        for s in slots:
            dx, dz = turn(SLOTS[s], 0.0, 180.0)
            # not merged: a merged mesh has no levels, and the bicycle's cull at 40 m is its saving
            _put(ns, put_town, f'bike_{k}_{s}', 'mamachari', x + dx, 0.1, z + dz, 180.0)
    # the konbini's roof sign (red coin 5 on its top, 7.0): the grey sign, standing on the real
    # roof's deck (4.7) instead of the grey roof (5.6). No real asset has a roof sign.
    ns['block']('konbini_sign', 193, 29.6, 199, 30.4, 4.7, 7.0, ns['C']['sign'], label='konbini_sign')

    # -- coins the real stairs, canopy and platform moved
    for c in cells.values():
        for e in c['entities']:
            if e['id'] in COINS:
                e['position'] = [r3(v) for v in COINS[e['id']]]

    # -- the deck's line and the parapet rails along the real parapets (the sweeps are gone)
    for name in ('parapet_s', 'parapet_n_w', 'parapet_n_e'):
        paths.pop(name, None)
        drop_entity(f'rail_{name}')
    deck = distinct(CUT)
    deck[0] = (0.0,) + tuple(deck[0][1:])           # from the level's west edge
    paths['viaduct_deck'] = {'points': [[r3(x), DECK, r3(z)] for x, z, _, _ in deck], 'raised': True}
    for m in ('viaduct', 'viaduct_under', 'deck', 'parapet'):   # the sweeps' materials: no sweep left
        ns['materials'].pop(m, None)
    for name, pts in rails().items():
        ns['path'](name, [(r3(x), PARAPET_Y, r3(z)) for x, z in pts])

    # -- the front road through the underpass: asphalt along its skew (25 degrees north of east)
    ux, uz = next((x, z) for a, x, z, _ in PIECES if a == 'viaduct_underpass')
    a = math.radians(25.0)
    d, n = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
    road = [(ux + d[0] * s + n[0] * w, uz + d[1] * s + n[1] * w) for s, w in ((-24, -7), (24, -7), (24, 7), (-24, 7))]
    ns['ops'].append({'op': 'paint', 'area': {'polygon': [[r3(x), r3(z)] for x, z in road]}, 'material': 'asphalt'})


# ------------------------------------------------------------------ stage: gen_core.py
def core(ns):
    placements = ns['placements']
    for cid in list(placements):
        placements[cid] = [p for p in placements[cid] if p['id'] not in ('viaduct_span', 'viaduct_pier', 'viaduct_end')]

    def put_core(pid, p, x, z):
        cid = ns['cell_of'](x, z)
        assert cid is not None, (pid, x, z)
        placements.setdefault(cid, []).append(p)

    for k, (asset, x, z, yaw) in enumerate(PIECES):
        if z >= 128:
            _put(ns, put_core, f'viaduct_{k}', asset, x, 0.0, z, yaw)
    # the wall that closes the deck (the core's grey wall, 5.5 m over the deck) across the line
    x, z, h, _ = END
    _put(ns, put_core, 'viaduct_end', 'gbc_viaduct_end', x, DECK, z, (90.0 - h) % 360, collision='self')


# ------------------------------------------------------------------ stage: make_world.py
ASSET_DIRS = ['viaduct_span_16', 'viaduct_curve_16', 'viaduct_underpass', 'viaduct_station_span',
              'viaduct_station_span_stair', 'viaduct_station_taper', 'station_concourse',
              'station_platform', 'ticket_gates', 'train_emu_car', 'signal_gantry', 'danchi',
              'pachinko_parlour', 'koban', 'bus_stop', 'bike_rack', 'mamachari', 'newsstand',
              'town_taxi_rank', 'phone_booth', 'postbox', 'town_bench', 'town_potted_plants',
              'town_utility_pole_transformer']


# Levels and culls for this world (the recipes' own suit a view of one asset): the train's L1
# from 9 m (a car is drawn whole from the ticket hall under it, 10.5 m off, which put the hall's
# view over its draw CPU budget), the plaza's small props culled sooner (seen from the station
# and the danchi through what stands between).
LOD = {'train_emu_car': {'distances': [9, 60], 'band': 1},
       'mamachari': {'cull': 30}, 'bike_rack': {'cull': 60}, 'newsstand': {'cull': 72},
       'phone_booth': {'cull': 66}, 'postbox': {'cull': 66}, 'koban': {'cull': 100},
       'bus_stop': {'cull': 90}}


def world(ns):
    w = ns['world']
    dirs = w.setdefault('asset_dirs', [])
    for d in [f'assets/{a}' for a in ASSET_DIRS] + ['../shrine/assets']:   # the konbini, vending machines
        if d not in dirs:
            dirs.append(d)
    w.setdefault('lod', {}).setdefault('assets', {}).update(LOD)
