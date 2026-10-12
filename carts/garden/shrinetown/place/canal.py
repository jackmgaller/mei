"""The canal zone's real assets (PLACE_SPLIT.md): everything whose origin is at x < 64, every row.

The canal and its bridges and grille, the machiya rows and the sento (the town's texture region,
rows 0-1); the park with its yagura, toilet and playground, the watermill, the sake brewery and the
bamboo grove (the shrine's region, rows 2-5). The generators call this module through the hook in
place/__init__.py, just before they write:

- town (notes/gen_town.py): the machiya, the sento, the road bridge, the footbridge, the grille,
  the two utility poles and the road works at the front road's west end, the trees between the
  road and the park, the props of the machiya lanes;
- core (assets/greybox/core/gen_core.py): the park, the arched bridge (its rails), the watermill,
  the sake brewery, the park's ginkgo and props, the bamboo's foot;
- mountain (make_mountain.py): the canal's spring and the bamboo grove;
- world (make_world.py): the asset directories, the ground under the brewery and the arched
  bridge's east end.

Where the real assets differ from the grey box (DESIGN.md 12.6, "Canal"): the machiya are turned
to face their lane, the sento sits so that its chimney is the grey box's (30.5, 67.5), the trees
between the road and the park move north of z 128 into the shrine's texture region.
Run the three generators and make_world.py (README.md, "How it is made").
"""
import math
from pathlib import Path

ST = Path(__file__).resolve().parent.parent           # carts/garden/shrinetown
SHRINE_ASSETS = ST.parent / 'shrine' / 'assets'
ZONE_X = 64.0                                         # the zone: x < 64
# the shrine's assets whose names the shrine town's assets/ also has (TEXTURES.md: the street zone
# renames shrine town's street_lamp to town_street_lamp); the park takes the shrine's
FROM_SHRINE = {'street_lamp', 'street_lamp_col'}


def r3(v):
    return round(v, 3)


def folder(name):
    """The asset directory (relative to the world file) that holds NAME's recipe: its own folder in
    assets/, or the shrine's assets (`../shrine/assets`)."""
    if name in FROM_SHRINE and (SHRINE_ASSETS / f'{name}.asset.json').is_file():
        return '../shrine/assets'
    hits = sorted(ST.glob(f'assets/*/{name}.asset.json'))
    hits = [h for h in hits if h.parent.name != 'greybox']
    if hits:
        return hits[0].parent.relative_to(ST).as_posix()
    if (SHRINE_ASSETS / f'{name}.asset.json').is_file():
        return '../shrine/assets'
    return None


def collision_of(name):
    """NAME_col when the asset has a collision companion beside it, else its own mesh."""
    d = folder(name)
    if d and (ST / d / f'{name}_col.asset.json').is_file():
        return f'{name}_col'
    return 'self'


def rot(yaw, x, z):
    """Local (x, z) turned by the kit's yaw (rotate [0, yaw, 0]: 90 turns -Z toward -X)."""
    a = math.radians(yaw)
    return x * math.cos(a) + z * math.sin(a), -x * math.sin(a) + z * math.cos(a)


class Cells:
    """A generator's cells, as (placements, entities) lists by cell id."""

    def __init__(self, lists):
        self.lists = lists                          # cid -> (placements, entities)

    def remove(self, cid, *ids):
        pl, en = self.lists(cid)
        pl[:] = [p for p in pl if p['id'] not in ids]
        en[:] = [e for e in en if e['id'] not in ids]

    def remove_where(self, cid, test):
        pl, _ = self.lists(cid)
        pl[:] = [p for p in pl if not test(p)]

    def put(self, pid, asset, pos, yaw=0, collision=None, layer=None):
        """A placement; pos (x, y, z), or (x, z) to stand it on the ground."""
        x, z = pos[0], pos[-1]
        assert x < ZONE_X, (pid, pos)
        pl, _ = self.lists(f'c{int(x // 64)}_{int(z // 64)}')
        p = {'id': pid, 'asset': asset, 'position': [r3(v) for v in pos]}
        if yaw % 360:
            p['yaw'] = r3(yaw % 360)
        if layer:
            p['layer'] = layer
        p['collision'] = collision or collision_of(asset)
        pl[:] = [q for q in pl if q['id'] != pid] + [p]

    def entity(self, eid, etype, pos, params=None):
        x, z = pos[0], pos[-1]
        _, en = self.lists(f'c{int(x // 64)}_{int(z // 64)}')
        e = {'id': eid, 'type': etype, 'position': [r3(v) for v in pos]}
        if params is not None:
            e['params'] = params
        en[:] = [q for q in en if q['id'] != eid] + [e]


def at(origin, yaw, local):
    """World (x, y, z) of a point given in an asset's frame placed at origin with yaw."""
    dx, dz = rot(yaw, local[0], local[2])
    return origin[0] + dx, origin[1] + local[1], origin[2] + dz


# ------------------------------------------------------------------ the plan (world coordinates)
# Machiya (town_machiya_a / _b: front -Z, frontage 10 m along X, depth z -7.3..+7.0). The rows run
# north-south, so each house is turned to face the lane between them (x 18-24): the west row
# (x 4-18, a) at yaw 270, its front on x 18; the east row (x 24-40, b) at yaw 90, its front on
# x 24 and its back at 38.3 (b is 2 m short of the 16 m row: the bank's strip is 5.7 m wide).
MACHIYA_Z = (18, 30, 42, 78, 90)                       # the grey box's rows, each z .. z + 10
MACHIYA_W = (18.0 - 7.3, 270)
MACHIYA_E = (24.0 + 7.3, 90)
# The sento (sento_front: 22 x 12.9 m, the chimney at local (8.8, 4.25)). Placed so that the
# chimney is where the grey box had it, (30.5, 67.5): glide G3 (scenario 412) and red coin 7 start
# there. Its iron ladder is a pole at local (8.8, 5.02, 3.45) from the boiler room's roof; the pole
# runs on 1.2 m over the chimney's top (18.2) so that its top holds the feet level with it, and
# letting go there steps onto the top (red coin 7, G3's take-off). To the top only, the feet
# stopped 1.2 m under it, out of a ledge's reach (alpha review r05 #2).
SENTO = (30.5 - 8.8, 0.0, 67.5 - 4.25)
SENTO_POLE = ((8.8, 5.02, 3.45), 19.4 - 5.02)
# The bridges and the grille (their frames: the walk along local X over a canal along local Z).
ROAD_BRIDGE = (48.0, 0.0, 111.0)                      # lamps on the parapets at local (0, 2.1, +-6.8)
ROAD_POLE_Z = 106.0                                   # the front road's utility poles (street zone)
ROAD_LAMPS = [(0.0, 2.1, -6.8), (0.0, 2.1, 6.8)]      # poles 2.75 up to the lamp heads
FOOTBRIDGE = (48.0, 0.0, 60.25)
GRILLE = (48.0, 0.0, 1.0)                             # yaw 180: its front faces upstream (north)
ARCHED = (48.0, 0.6, 160.0)
# The park (0.6), from the asset agents' numbers (PLACEMENT_NOTES.md)
YAGURA = (22.0, 0.6, 160.0)
YAGURA_POLES = [((1.2, 0.0, 3.12), 3.3), ((-0.6, 2.45, 2.02), 2.95)]
TOILET = ((7.0, 0.6, 189.0), 270)                     # front east
SLIDE = ((12.0, 0.6, 140.0), 180)                     # tower south
SLIDE_POLE = ((0.0, 0.0, 2.25), 2.4)
JUNGLE_GYM = (27.5, 0.6, 133.5)
SWINGS = (35.0, 0.6, 140.5 - 0.6)                     # the frame (the grey box's z 140.5) is 0.6 behind the origin
# the swings' two rails, 0.02 over their collision tops (2.6, 0.65) and clear of the legs:
# (name, y, local z, half length)
SWING_RAILS = [('top', 2.62, 0.6, 1.8), ('safety', 0.67, -1.4, 2.05)]
WATERMILL = (42.27, 0.6, 196.0)                       # the bank's edge (local x 1.73) on the canal's wall, x 44
SAKAGURA = (15.0, 0.7, 218.0)                         # on a pad at 0.7
SAKAGURA_PAD = [5.0, 210.5, 25.0, 225.5]
# Ginkgo: the core's six and the town's two, those moved north of the texture boundary (z 128) so
# that the shrine's tree_ginkgo stays out of the town's set; the town's cedar at (58, 122) likewise.
GINKGO = [(8, 150), (36, 152), (8, 172), (36, 176), (14, 200), (32, 196), (12, 130), (39, 130)]
CEDAR = (59.0, 131.0)


def lane_props(c):
    """The machiya lanes' and the canal bank's small props (town shared props; culled at 40-50 m)."""
    W, E = 18.0, 24.0                                  # the lane's sides: the two rows' fronts
    props = [
        ('pots_w18', 'town_potted_plants', (W + 0.4, 0, 21.0), 270),
        ('pots_w42', 'town_potted_plants', (W + 0.4, 0, 45.5), 270),
        ('pots_w78', 'town_potted_plants', (W + 0.4, 0, 86.0), 270),
        ('pots_e30', 'town_potted_plants', (E - 0.4, 0, 33.0), 90),
        ('pots_e78', 'town_potted_plants', (E - 0.4, 0, 80.5), 90),
        ('pots_e90', 'town_potted_plants', (E - 0.4, 0, 96.5), 90),
        ('bike_w30', 'mamachari', (W + 0.9, 0, 38.0), 10),
        ('bike_e18', 'mamachari', (E - 0.9, 0, 25.5), 185),
        ('bike_w90', 'mamachari', (W + 0.9, 0, 98.0), 355),
        ('laundry_e42', 'town_laundry_pole', (E - 0.5, 0, 44.0), 90),
        ('aircon_e30', 'town_aircon_pipes', (38.3 + 0.2, 0, 36.0), 270),
        ('aircon_e78', 'town_aircon_pipes', (38.3 + 0.2, 0, 85.0), 270),
        ('bins_lane52', 'town_crates_bins', (W + 0.6, 0, 54.0), 270),
        ('bins_e90', 'town_crates_bins', (38.3 + 0.3, 0, 92.0), 270),
        # the footbridge's west end: a roadside shrine and a jizo on the bank
        ('hokora_footbridge', 'hokora', (41.6, 0, 56.4), 270),
        ('jizo_footbridge', 'jizo', (41.8, 0, 64.2), 270),
        # the canal lane east of the canal (x 52-64): a bench looking over the water
        ('bench_canal_lane', 'town_bench', (53.4, 0, 76.0), 90),
    ]
    for pid, asset, pos, yaw in props:
        c.put(f'canal_{pid}', asset, pos, yaw)


def town(ns):
    """Rows 0-1 (z < 128): c0_0 and c0_1, the town's texture region."""
    def lists(cid):
        i, j = int(cid[1]), int(cid[3])
        cell = ns['cell'](cid, (i, j))
        return cell['placements'], cell['entities']
    c = Cells(lists)
    # machiya
    for z in MACHIYA_Z:
        c.remove('c0_0' if z < 64 else 'c0_1', f'machiya_w{z}', f'machiya_e{z}')
        c.put(f'machiya_w{z}', 'town_machiya_a', (MACHIYA_W[0], 0.0, z + 5.0), MACHIYA_W[1])
        c.put(f'machiya_e{z}', 'town_machiya_b', (MACHIYA_E[0], 0.0, z + 5.0), MACHIYA_E[1])
    # the sento, its boiler room and chimney (all one asset now) and the chimney's ladder
    c.remove('c0_1', 'sento', 'sento_boiler', 'sento_chimney', 'pole_chimney')
    c.put('sento', 'sento_front', SENTO)
    (lx, ly, lz), h = SENTO_POLE
    px, py, pz = at(SENTO, 0, (lx, ly, lz))
    c.entity('pole_chimney', 'pole', (px, py, pz), {'height': r3(h)})
    # the front road's bridge and its two lamp poles
    c.remove('c0_1', 'canal_road_bridge')
    c.put('canal_road_bridge', 'canal_road_bridge', ROAD_BRIDGE)
    for k, (lx, ly, lz) in enumerate(ROAD_LAMPS):
        c.entity(f'pole_road_bridge_{k}', 'pole', at(ROAD_BRIDGE, 0, (lx, ly, lz)), {'height': 2.75})
    c.remove('c0_0', 'canal_footbridge', 'canal_grille')
    c.put('canal_footbridge', 'canal_footbridge', FOOTBRIDGE)
    c.put('canal_grille', 'canal_grille', GRILLE, 180)
    # the road's utility poles in the zone (x 10 and 40): the shrine street's pole, crossarm across
    # the road (wires along x). At z 106, as the street zone's: its two wires at 8.0, 0.8 m either
    # side of the pole, clear the shops' fronts at z 104 (the grey box's wire rail at z 104 is the
    # street zone's to move)
    for x in (10, 40):
        c.remove('c0_1', f'pole_road{x}')
        c.put(f'pole_road{x}', 'street_utility_pole', (float(x), 0.0, ROAD_POLE_Z), 90)
        c.entity(f'pole_road{x}', 'pole', (float(x), 0.0, ROAD_POLE_Z), {'height': 9.0})
    # the road works at the front road's west end: two barriers across the road, facing east; their
    # collision is the drawn barrier's box (assets/road_works_barrier), not the shrine's 3 m wall
    c.remove('c0_1', 'road_works')
    for k, z in enumerate((107.5, 114.5)):
        c.put(f'road_works_{k}', 'street_barrier', (1.0, 0.0, z), 270,
              collision='road_works_barrier_col')
    # the trees between the road and the park move into the shrine's rows (core())
    c.remove('c0_1', 'cedar_0', 'ginkgo_0', 'ginkgo_1')
    lane_props(c)


def core(ns):
    """Rows 2-3 (z 128-256): c0_2 and c0_3, the shrine's texture region."""
    def lists(cid):
        return ns['placements'].setdefault(cid, []), ns['entities'].setdefault(cid, [])
    c = Cells(lists)
    c.remove('c0_2', 'yagura', 'park_toilet', 'jungle_gym', 'swings', 'park_slide')
    c.put('yagura', 'festival_yagura', YAGURA)
    for k, ((lx, ly, lz), h) in enumerate(YAGURA_POLES):
        c.entity(f'pole_yagura_{k}', 'pole', at(YAGURA, 0, (lx, ly, lz)), {'height': h})
    c.put('park_toilet', 'park_toilet', *TOILET)
    c.put('park_slide', 'park_slide', *SLIDE)
    (lx, ly, lz), h = SLIDE_POLE
    c.entity('pole_park_slide', 'pole', at(SLIDE[0], SLIDE[1], (lx, ly, lz)), {'height': h})
    c.put('jungle_gym', 'park_jungle_gym', JUNGLE_GYM)
    c.put('swings', 'park_swings', SWINGS)
    paths = ns['paths']
    for name, y, lz, half in SWING_RAILS:
        pts = [at(SWINGS, 0, (sx, y, lz)) for sx in (-half, half)]
        paths[f'canal_swings_{name}'] = {'points': [[r3(v) for v in p] for p in pts], 'raised': True}
        c.entity(f'rail_canal_swings_{name}', 'rail', pts[0], {'path': f'canal_swings_{name}'})
    # the arched bridge replaces the core's plank sweep over the canal at z 160; its two top rails
    # (kasagi, local z +-1.4, 0.9 over the arc through (+-5, 0) and (0, 1.25)) are rails
    paths.pop('core_canal_arch', None)
    c.put('canal_arched_bridge', 'canal_arched_bridge', ARCHED)
    for k, lz in enumerate((-1.4, 1.4)):
        pts = [at(ARCHED, 0, (x, -9.375 + math.sqrt(10.625 ** 2 - x * x) + 0.9, lz)) for x in range(-5, 6)]
        paths[f'canal_arch_rail_{k}'] = {'points': [[r3(v) for v in p] for p in pts], 'raised': True}
        c.entity(f'rail_canal_arch_{k}', 'rail', pts[0], {'path': f'canal_arch_rail_{k}'})
    # the plank bridge by the mill (the core's sweep): boards, the arched bridge's (its material
    # `planks` is the walkway's too, flat; this one is the zone's own, textured in world())
    paths['core_canal_planks']['sweep']['material'] = 'canal_planks'
    # the watermill (house and wheel in one asset) and the brewery
    c.remove('c0_3', 'watermill_house', 'watermill_wheel', 'sakagura')
    c.put('watermill', 'watermill', WATERMILL)
    c.put('sakagura', 'sakagura', SAKAGURA)
    # trees: the shrine's ginkgo for the core's six and the town's two; the town's cedar
    for k in range(6):
        c.remove('c0_2' if k < 4 else 'c0_3', f'ginkgo_{k}')
    for k, (x, z) in enumerate(GINKGO):
        c.put(f'ginkgo_{k}', 'tree_ginkgo', (x, z), (k * 47) % 360)
    c.put('cedar_canal_lane', 'tree_cedar', CEDAR, 30)
    # the park's props: benches round the dance ground facing the yagura, the shrine's lamps, shrubs
    # behind the toilet, a stone lantern at the arched bridge's foot, a shishi-odoshi by the mill
    # and a tanuki at the brewery's door
    props = [
        ('bench_sw', 'town_bench', (14.0, 152.0), 225), ('bench_se', 'town_bench', (30.0, 152.0), 135),
        ('bench_w', 'town_bench', (9.5, 162.0), 270), ('bench_e', 'town_bench', (35.0, 166.0), 90),
        ('lamp_park_s', 'street_lamp', (20.0, 136.0), 0), ('lamp_park_e', 'street_lamp', (40.5, 168.0), 90),
        ('lamp_park_n', 'street_lamp', (18.0, 184.0), 180),
        ('shrub_toilet_s', 'plant_shrub', (3.4, 185.0), 0), ('shrub_toilet_n', 'plant_shrub', (3.4, 193.2), 140),
        ('shrub_toilet_e', 'plant_shrub', (11.2, 194.0), 70),
        ('lantern_arch', 'forest_stone_lantern', (41.3, 157.0), 0),
        ('shishi_odoshi_mill', 'shishi_odoshi', (36.6, 192.6), 90),
        ('tanuki_brewery', 'tanuki', (9.0, 211.0), 0),
    ]
    for pid, asset, pos, yaw in props:
        c.put(f'canal_{pid}', asset, pos, yaw)
    bamboo(ns['scatter'], 206, 256, 'core', exclude=[{'rect': [3, 209, 27, 227]}])
    ns['scatter'].pop('core_bamboo', None)


def bamboo(scatter, z0, z1, region, exclude=()):
    """The grove as clumps of tree_bamboo_tall: loose culms on a 6 m lattice, and two more sets on a
    9 m lattice held near their squares' centres, so that culms gather in twos and threes."""
    area = {'rect': [2, z0, 44, z1]}
    base = {'area': area, 'clearance': 1.2, 'max_slope': 45, 'chunk': 16, 'lod': 'assets', 'lift': -0.1}
    if exclude:
        base['exclude'] = list(exclude)
    asset = [{'asset': 'tree_bamboo_tall', 'collision': 'tree_bamboo_tall_col'}]
    scatter[f'canal_bamboo_{region}'] = dict(base, assets=asset, spacing=6, fill=0.6, seed=51)
    scatter[f'canal_bamboo_{region}_clump_a'] = dict(base, assets=asset, spacing=9, fill=0.8, jitter=0.2, seed=52)
    scatter[f'canal_bamboo_{region}_clump_b'] = dict(base, assets=asset, spacing=9, fill=0.6, jitter=0.25, seed=53)
    # bamboo grass under the culms
    scatter[f'canal_sasa_{region}'] = dict(base, assets=[{'asset': 'plant_sasa', 'collision': 'none'}], spacing=5,
                                           fill=0.35, seed=54, lift=0.0, chunk=32)   # culled at 40: big chunks, few placements


def mountain(ns):
    """Rows 4-5 (z 256-384): c0_4 and c0_5."""
    def lists(cid):
        c = ns['CELLS'].setdefault(cid, {'placements': [], 'entities': []})
        return c['placements'], c['entities']
    c = Cells(lists)
    # the canal's spring: boulders round its head instead of the grey box's slab
    c.remove('c0_4', 'canal_spring')
    c.put('canal_spring_0', 'forest_boulder_big', (48.0, 295.0), 20)
    c.put('canal_spring_1', 'forest_boulder', (44.6, 293.6), 110)
    c.put('canal_spring_2', 'forest_boulder', (51.6, 293.8), 250)
    bamboo(ns['SCATTER'], 256, 380, 'mountain')
    ns['SCATTER'].pop('mountain_bamboo', None)


def world(ns):
    """The world: asset directories for what the zone places, and its ground operations."""
    w = ns['world']
    import json
    names = set()
    for f in sorted((ST / w['cell_dir']).glob('*.cell.json')):
        for p in json.loads(f.read_text()).get('placements', []):
            if p['position'][0] < ZONE_X:
                names.add(p['asset'])
    for s in w['scatter'].values():
        if any(a['asset'] in ('tree_bamboo_tall', 'plant_sasa') for a in s['assets']):
            names.update(a['asset'] for a in s['assets'])
    from place import add_dir
    dirs = w.setdefault('asset_dirs', [])
    for n in sorted(names):
        d = folder(n)
        if d and not n.startswith(('gbt_', 'gbc_', 'gbm_')):
            add_dir(dirs, d)
    # the plank bridge's boards (alpha review r16 #5: the one flat-colour bridge of the four)
    w['terrain']['materials']['canal_planks'] = {
        'color': '#8a6446',
        'texture': {'image': '../shrine/assets/art/forest_planks.png', 'scale': [2.0, 2.0], 'span': 23}}
    ops = w['terrain']['fields']['ground']['operations']
    # a flat pad under the brewery; the arched bridge's east foot down to its abutment (0.6), clear
    # of the canal's bank (x 52)
    ops.append({'op': 'set', 'area': {'rect': SAKAGURA_PAD}, 'height': SAKAGURA[1], 'falloff': 3})
    ops.append({'op': 'set', 'area': {'rect': [53, 156, 56, 164]}, 'height': 0.6})
