"""Shrine town, placement zone street (PLACE_SPLIT.md): 40 <= z < 128 and 64 <= x < 210. The
shotengai (its shops, the arcade roof and gates, the bounce awnings), the back alleys (the alley
houses, the fire tower and its kura, the dagashi shop, the coin laundry), the building with its
fire escape, the front road's west part, the utility poles and the town's wires, street props.

Called through place/__init__.py by notes/gen_town.py (`town`: the town's cells and world part)
and by make_world.py (`world`: the asset directories). It takes out the zone's grey boxes (all but
the great torii, which the shrine zone places) and puts the real assets in their place, with the
poles, rails, layers and coins that come with them. Every number comes from the asset's own
generator (its docstring) or PLACEMENT_NOTES.md; what differs from the grey box is in DESIGN.md,
section 12.6, "Street".

Yaw is the kit's: 90 turns an asset's -Z front toward -X. The shops' fronts face the street, so
the west row (x 140-154) stands at yaw 270 and the east row (x 166-180) at yaw 90.
"""
import json
import math
import sys
from pathlib import Path

ST = Path(__file__).resolve().parent.parent            # carts/garden/shrinetown
ROOT = ST.parents[2]
SHRINE = ST.parent / 'shrine' / 'assets'


def in_zone(x, z):
    return 40 <= z < 128 and 64 <= x < 210


def lw(at, yaw, p):
    """A point in an asset's frame, placed at `at` turned by `yaw`, in world coordinates."""
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    x, y, z = p
    return (at[0] + x * c + z * s, at[1] + y, at[2] - x * s + z * c)


# ------------------------------------------------------------------ the shotengai
# Six plots a side, 10 m each from z 44; a shop's origin is its plot's middle. The three bounce
# awnings on the street go on no-awning shops (a pink-striped awning always means bounce,
# OVERNIGHT_DECISIONS #4); the three on the service lanes go on the back walls of shops whose
# back roofs are low enough to land on (5.0-6.5: the record shop's back room, 7.3, is not).
# The arcade gates stand on the plot lines at z 54 and 94, where no shop's awning reaches (at z 60
# and 96, the plan's places, the gates' posts went through the shops' awnings).
WEST = ['town_shop_2f_c_left_noawning', 'town_shop_3f', 'tobacco_shop', 'recordshop', 'ramen_shop', 'town_shop_3f']
EAST = ['town_shop_2f_c_noawning', 'town_shop_2f_a_noawning', 'town_shop_3f', 'town_shop_2f_a', 'town_shop_2f_b',
        'town_shop_3f']
STREET_AWNING = {('w', 0): -0.1, ('e', 0): 0.1, ('e', 1): 0.0}       # x on the shop's front (gen_shops.py)
BACK_AWNING = [('w', 2), ('e', 3), ('w', 4)]
ARCADE_ROOFS = [(160.0, 69.0), (160.0, 85.0)]                       # z 61-93
ARCADE_GATES = [(160.0, 54.0, 0), (160.0, 94.0, 180)]               # each front toward its approach

# ------------------------------------------------------------------ the back alleys
ALLEY_KIND = {6: 'town_alley_house_a', 6.5: 'town_alley_house_b', 7: 'town_alley_house_b', 8: 'town_alley_house_c'}
TOWER = (102.0, 0.0, 74.0)
# The alley plot west of the tower (x 90-99.5, z 66-74.5) is left to the tower's yard: the real
# house there (x 89.7-99.8, z 65.4-74.9 with its eaves) took in the tower's hose shed (x 97.6-100.3,
# z 73.3-75.4), and moved it would meet its neighbours (the alley west is 1.9 m, the one south 1.3
# m between the eaves). The tower stays at (102, 74): glide G4 (scenario 413) starts from its top.
TOWER_YARD = {(90, 66)}
KURA = (107.8, 0.0, 74.0)                                           # x 106.3-109.3: the kick wall 2.85 m east

# ------------------------------------------------------------------ the building and shortcut E
BUILDING = (193.0, 0.0, 73.0)
ESCAPE = (196.5, 0.0, 103.0)
LADDER_E_POLE = (198.5, 0.0, 103.95)

# ------------------------------------------------------------------ poles and wires
# town_utility_pole_transformer carries two wires at 8.0, 0.8 m either side of the pole (its
# local x), running along its local z. The front road's poles stand at z 106 (the grey box's 104
# put the south wire through the 3F shops at the shotengai's north end and the fire escape).
WIRE_Y = 8.0
ROAD_POLES = [10, 40, 70, 100, 130, 152.5, 167.5, 190, 220, 250, 280]
ROAD_Z = 106.0
LANE_W = [(112.75, 44.0), (112.75, 104.0)]
LANE_E = [(137.75, 44.0), (137.75, 104.0)]
KONBINI = [(210.0, 33.0), (207.0, 104.0)]            # the first pole is the station zone's (yaw 0)
WIRE_SWEEP = {'profile': [[0.0, -0.03], [0.0, 0.03]], 'material': 'wire', 'double_sided': True, 'collision': False}

COIN_LIFT = 0.7


def town(g):
    cells, place, entity, path, paths = g['cells'], g['place'], g['entity'], g['path'], g['paths']
    placed = []                                   # (id, asset, collision, x, y, z, yaw)

    # ---- the grey boxes out: every placement in the zone but the great torii
    gone = set()
    for c in cells.values():
        keep = []
        for p in c['placements']:
            x, z = p['position'][0], p['position'][-1]
            if in_zone(x, z) and p['id'] != 'torii':
                gone.add(p['id'])
                continue
            keep.append(p)
        c['placements'] = keep

    def put(pid, name, at, yaw=0.0, col=None, layer=None, merge=False):
        """A real asset; its collision is NAME_col unless given ('self', 'none' or a name)."""
        col = col or f'{name}_col'
        yaw = round(yaw % 360, 3)
        place(pid, (name, col), at[0], at[1], at[2], yaw, layer)
        cid = f'c{int(at[0] // 64)}_{int(at[2] // 64)}'
        p = cells[cid]['placements'][-1]
        if merge:
            p['merge'] = True
        placed.append((p['id'], name, col, at[0], at[1], at[2], yaw, layer))
        return p

    # ---- the shotengai
    for side, x0, yaw, names in (('w', 147.0, 270.0, WEST), ('e', 173.0, 90.0, EAST)):
        for i, name in enumerate(names):
            at = (x0, 0.0, 49.0 + 10 * i)
            put(f'shop_{side}{i}', name, at, yaw)
            if (side, i) in STREET_AWNING:
                put(f'awning_{side}{i}', 'town_awning_bounce', lw(at, yaw, (STREET_AWNING[(side, i)], 0, -7.75)), yaw)
            if (side, i) in BACK_AWNING:
                put(f'awning_{side}{i}b', 'town_awning_bounce', lw(at, yaw, (0.0, 0, 7.75)), yaw + 180)
    for k, (x, z) in enumerate(ARCADE_ROOFS):
        put(f'arcade_roof_{k}', 'arcade_roof_16', (x, 0.0, z))
    for k, (x, z, yaw) in enumerate(ARCADE_GATES):
        # the north gate collides with its pillars only: glide G8 comes in under it with its feet
        # at about 4.3, and the name board's underside is at 5.11 (make_arcade_gate_posts_col.py)
        put(f'arcade_gate_{k}', 'arcade_gate', (x, 0.0, z), yaw, col='arcade_gate_posts_col' if k else None)
    # lamps where the arcade is not, clear of the awnings and of the street's middle (the walk
    # north, scenario 400); each is a pole to 3.8
    for k, (x, z) in enumerate([(155.9, 46.0), (164.1, 51.5), (155.9, 98.5), (164.1, 101.0)]):
        put(f'lamp_sando{k}', 'town_street_lamp', (x, 0.0, z), 90)
        entity(f'pole_lamp_sando{k}', 'pole', x, 0.0, z, {'height': 3.8})

    # ---- the back alleys: the grey box's 24 houses (layout.py), each the real house of its height.
    # Doors (-Z) face the plaza in the first row and the road strip in the last; between, they
    # alternate.
    L = g['L']
    for b in L.boxes:
        x1, z1, x2, z2, base, top, col, lab = b
        if not (66 <= x1 < 136 and 44 <= z1 < 102 and abs((x2 - x1) - 9.5) < .01) or z1 >= 99:
            continue
        if (x1, z1) in TOWER_YARD:
            continue
        if z1 == 44:
            yaw = 0
        elif z1 == 88:
            yaw = 180
        else:
            yaw = 0 if (int((x1 - 66) // 12) + int((z1 - 44) // 11)) % 2 == 0 else 180
        put(f'alley_{int(x1)}_{int(z1)}', ALLEY_KIND[top], ((x1 + x2) / 2, 0.0, (z1 + z2) / 2), yaw)
    # the fire tower in its yard (ladder south, the hose shed on -X against the house's corner),
    # and the kura 2.85 m east of the tower's kick face (FOLLOWUPS: the kick pair as built)
    put('fire_tower', 'fire_tower', TOWER)
    put('fire_kura', 'town_kura', KURA)
    _move_entity(cells, 'pole_fire_tower', (102.0, 0.0, 72.08))
    # the dagashi shop on its corner, its front to the plaza side's walk; gachapon and a jizo
    put('dagashi', 'dagashi_shop', (128.5, 0.0, 46.5))
    put('gacha_0', 'gachapon', (126.6, 0.0, 43.55))
    put('gacha_1', 'gachapon', (128.0, 0.0, 43.55))
    put('jizo_dagashi', 'jizo', (124.3, 0.0, 44.6))           # (repeating textures: not merged)
    # the coin laundry on the strip between the last alley row and the road, facing the road
    put('coin_laundry', 'coin_laundry', (130.75, 0.0, 100.6), 180)

    # ---- the building and its fire escape (shortcut E): the stair in no layer, with the collision;
    # its ladder folded up (layer ladder_e_up) by default, down (ladder_e) once kicked; the
    # ladder's pole only when down
    put('building', 'street_building', BUILDING, 90)
    put('fire_escape', 'town_fire_escape', ESCAPE, 180)
    put('fire_escape_up', 'town_fire_escape_up', ESCAPE, 180, col='none', layer='ladder_e_up')
    put('fire_escape_down', 'town_fire_escape_down', ESCAPE, 180, col='none', layer='ladder_e')
    _move_entity(cells, 'pole_ladder_e', LADDER_E_POLE, {'height': 7.6})      # front: climbed from the north
    _entity(cells, 'pole_ladder_e')['yaw'] = 0
    g['part']['layers'].pop('ladder_e', None)
    g['part']['layers'].update({'ladder_e_up': {'group': 'shortcut_e', 'on': True}, 'ladder_e': {'group': 'shortcut_e'}})

    # ---- poles and wires
    for x in ROAD_POLES:
        pid = f'pole_road{int(x)}'
        if in_zone(x, ROAD_Z):
            put(pid, 'town_utility_pole_transformer', (float(x), 0.0, ROAD_Z), 90)
        _move_entity(cells, pid, (float(x), 0.0, ROAD_Z))
    for k, (x, z) in enumerate(LANE_W):
        put(f'pole_lane_w{k}', 'town_utility_pole_transformer', (x, 0.0, z))
    for k, (x, z) in enumerate(LANE_E):
        put(f'pole_lane_e{k}', 'town_utility_pole_transformer', (x, 0.0, z))
    put('pole_konbini1', 'town_utility_pole_transformer', (KONBINI[1][0], 0.0, KONBINI[1][1]))
    g['materials']['wire'] = {'color': '#26262a'}
    for old in ('wire_road', 'wire_lane_w', 'wire_lane_e', 'wire_konbini'):
        paths.pop(old, None)
        _drop_entity(g, f'rail_{old}')

    def wires(name, poles, yaw):
        for tag, dx in (('a', -0.8), ('b', 0.8)):
            path(f'{name}_{tag}', [lw((px, 0.0, pz), yaw, (dx, WIRE_Y, 0.0)) for px, pz in poles], sweep=WIRE_SWEEP)
    wires('wire_road', [(x, ROAD_Z) for x in ROAD_POLES], 90)      # a: z 106.8 (north), b: z 105.2
    wires('wire_lane_w', LANE_W, 0)                                 # a: x 111.95, b: x 113.55
    wires('wire_lane_e', LANE_E, 0)                                 # a: x 136.95, b: x 138.55
    wires('wire_konbini', KONBINI, 0)                               # a: x 209.2 to 206.2, b: +1.6
    # the wires' coins onto the wire the grey box's line became: the road's south wire (z 105.2),
    # the service lane's east one (x 138.55), the konbini wire's east one
    for c in cells.values():
        for e in c['entities']:
            i, (x, y, z) = e['id'], e['position']
            if i.startswith('coin_wire_road') or i == 'red_wire':
                e['position'] = [x, WIRE_Y + COIN_LIFT, round(ROAD_Z - 0.8, 3)]
            elif i.startswith('coin_wire_lane'):
                e['position'] = [round(LANE_E[0][0] + 0.8, 3), WIRE_Y + COIN_LIFT, z]
            elif i.startswith('coin_wire_konbini'):
                (ax, az), (bx, bz) = KONBINI
                t = (z - az) / (bz - az)
                e['position'] = [round(ax + (bx - ax) * t + 0.8, 3), WIRE_Y + COIN_LIFT, round(z, 3)]

    # ---- the front road (its west part): street trees on the north verge where the grey box's
    # cedars stood (zelkovas, the town's street tree, as the east zone's); the shrine's slim lamps
    # on the north side, arms over the road; signs and mirrors at the alley mouths
    for k, (x, z) in enumerate([(66, 125), (74, 121), (84, 124), (92, 121)]):
        put(f'zelkova_road{k}', 'tree_zelkova', (float(x), 0.0, float(z)), 53 * k)
    for k, x in enumerate((85.0, 115.0, 140.0, 182.0, 204.0)):
        put(f'lamp_road{k}', 'street_lamp', (x, 0.0, 117.2), 90)
    # the delivery van, parked in the south lane between the poles at x 70 and 100 (left out while
    # the town's shared set had no room for its 14 KB; back with 2 MB of VRAM, TEXTURES.md)
    put('van_road', 'delivery_van', (85.0, 0.0, 108.6), 90)
    put('signs_alley', 'town_road_signs', (100.75, 0.0, 102.9), 180, col='none')
    put('mirror_alley_0', 'traffic_mirror', (124.8, 0.0, 103.3), 180)
    put('mirror_alley_1', 'traffic_mirror', (88.8, 0.0, 103.3), 180)
    put('firepost_sando', 'firepost', (155.4, 0.0, 103.6), 180)

    # ---- props (spec 8.2: small; not merged: a merged chunk has no levels or cull and drew 360
    # triangles from 97 m, where each prop alone is culled at 40-60 m)
    put('crane_sando', 'crane_game', (154.75, 0.0, 87.0), 270)
    put('kanban_e3', 'town_kanban_set', (165.6, 0.0, 78.0), 90, col='none')
    put('kanban_e4', 'town_kanban_set', (165.6, 0.0, 88.0), 90, col='none')
    for k, (x, z, yaw) in enumerate([(127.0, 100.6, 0), (131.9, 44.9, 0), (165.4, 74.2, 0), (118.6, 94.6, 90)]):
        put(f'bike_{k}', 'mamachari', (x, 0.0, z), yaw, col='none')
    for k, (x, z, yaw) in enumerate([(139.7, 47.5, 90), (139.7, 98.0, 90), (180.3, 59.0, 270), (180.3, 90.0, 270)]):
        put(f'crates_{k}', 'town_crates_bins', (x, 0.0, z), yaw, col='none')
    for k, (x, z, yaw) in enumerate([(81.0, 52.75, 180), (94.0, 65.75, 0), (118.0, 76.75, 0), (70.0, 74.75, 180)]):
        put(f'aircon_{k}', 'town_aircon_pipes', (x, 0.0, z), yaw, col='none')
    for k, (x, z, yaw) in enumerate([(73.0, 43.7, 0), (85.0, 54.7, 0), (97.0, 87.3, 0), (121.0, 65.7, 0)]):
        put(f'plants_{k}', 'town_potted_plants', (x, 0.0, z), yaw, col='none')
    put('laundry_yard_a', 'town_laundry_pole', (73.5, 0.0, 62.4), 0, col='none')
    put('laundry_yard_c', 'town_laundry_pole', (120.5, 0.0, 90.5), 0, col='none')
    put('kei_yard_a', 'kei_truck', (70.75, 0.0, 59.25), 90)
    put('recycling_yard_b', 'recycling_station', (82.75, 0.0, 84.9))
    put('bench_tower_yard', 'town_bench', (106.0, 0.0, 84.6))

    # ---- coins on floors: onto the real roofs (the grey box's were 0.7 over its boxes)
    _reseat_coins(cells, placed)


def _move_entity(cells, eid, pos, params=None):
    for c in cells.values():
        for e in c['entities']:
            if e['id'] == eid:
                e['position'] = [round(v, 3) for v in pos]
                if params:
                    e.setdefault('params', {}).update(params)
                return
    raise KeyError(eid)


def _entity(cells, eid):
    return next(e for c in cells.values() for e in c['entities'] if e['id'] == eid)


def _drop_entity(g, eid):
    for c in g['cells'].values():
        c['entities'] = [e for e in c['entities'] if e['id'] != eid]
    g['entities_n'].discard(eid)


def _find(name):
    for f in [*sorted((ST / 'assets').glob(f'*/{name}.asset.json')), SHRINE / f'{name}.asset.json']:
        if f.is_file() and f.parent.name != 'greybox':
            return f
    return None


def _reseat_coins(cells, placed):
    """Every coin and red coin in the zone not on a wire: 0.7 over the highest floor at most 1.5 m
    above it, of the zone's real collision and the ground."""
    sys.path.insert(0, str(ROOT / 'tools'))
    from kitcore import jsonio
    from assetkit.compiler import compile_recipe
    from assetkit.geometry import AssetError
    meshes = {}

    def tris(col):
        if col not in meshes:
            f = _find(col)
            mesh, _, _ = compile_recipe(jsonio.load(str(f), AssetError), f.parent)
            out = []
            for fc in mesh.faces:
                p = [mesh.vertices[i] for i in fc.indices]
                out += [(p[0], p[k], p[k + 1]) for k in range(1, len(p) - 1)]
            meshes[col] = out
        return meshes[col]

    solids = []
    for pid, name, col, x, y, z, yaw, layer in placed:
        if col in ('none', 'self') or layer == 'ladder_e':
            continue
        world = [tuple(lw((x, y, z), yaw, v) for v in t) for t in tris(col)]
        xs = [v[0] for t in world for v in t]
        zs = [v[2] for t in world for v in t]
        solids.append(((min(xs), min(zs), max(xs), max(zs)), world))

    def floor(x, z, below):
        best = 0.0
        for (x0, z0, x1, z1), world in solids:
            if not (x0 <= x <= x1 and z0 <= z <= z1):
                continue
            for a, b, c in world:
                d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
                if abs(d) < 1e-9:
                    continue
                l1 = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / d
                l2 = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / d
                if min(l1, l2, 1 - l1 - l2) < -1e-6:
                    continue
                yy = l1 * a[1] + l2 * b[1] + (1 - l1 - l2) * c[1]
                if best < yy <= below:
                    best = yy
        return best

    for c in cells.values():
        for e in c['entities']:
            if e['type'] not in ('coin', 'red_coin') or e['id'].startswith(('coin_wire', 'red_wire', 'star_')):
                continue
            x, y, z = e['position']
            if in_zone(x, z):
                e['position'] = [x, round(floor(x, z, y + 1.5) + COIN_LIFT, 3), z]


# Levels of detail sooner than the assets' own (world lod.assets: levels 1 and 2, cull): the
# shops to spec 8.2's 20 m (the ramen shop is 483 triangles at level 0, its own L1 is from 24 m),
# the building from 30 m (its 446-triangle level 0 was drawn to 60 m in V1), the arcade gates
# from 30 m. Measured with tools/views.py (V1, the platform): DESIGN.md 12.6.
LOD = {'ramen_shop': {'distances': [16, 45]}, 'recordshop': {'distances': [20, 50]},
       'tobacco_shop': {'distances': [20, 50]}, 'street_building': {'distances': [30]},
       'arcade_gate': {'distances': [30, 70]},
       # the street's small props culled at 40-70 m (spec 8.2: 40), not the 90-120 m of their
       # recipes, or never: from the platform the shotengai's lamps and the alleys' props were drawn
       'town_street_lamp': {'cull': 60}, 'street_lamp': {'cull': 70}, 'gachapon': {'cull': 40},
       'jizo': {'cull': 40}, 'town_kanban_set': {'cull': 45}, 'town_road_signs': {'cull': 60},
       'firepost': {'cull': 50}, 'traffic_mirror': {'cull': 50}, 'kei_truck': {'cull': 60}, 'delivery_van': {'cull': 60},
       'recycling_station': {'cull': 50}, 'crane_game': {'cull': 45},
       'town_crates_bins': {'cull': 40},
       # the poles with their wires (the sweeps are culled at 56): from over the station the
       # front road's poles were drawn at 100-110 m
       'town_utility_pole_transformer': {'cull': 56},
       # (the join) the dagashi shop and the shops' level 2 sooner: from the station's stair and
       # canopy the shotengai's mouth is 45-60 m off
       'dagashi_shop': {'distances': [20, 45]},
       **{n: {'distances': [20, 40]} for n in (
           'town_shop_2f_a', 'town_shop_2f_a_noawning', 'town_shop_2f_b',
           'town_shop_2f_c_left_noawning', 'town_shop_2f_c_noawning',
           'town_shop_3f')}}


def world(g):
    """The real assets' folders in the world's asset directories (the town's cells as written),
    and the zone's levels of detail."""
    from place import add_dir
    w = g['world']
    lod = w.setdefault('lod', {}).setdefault('assets', {})
    for name, spec in LOD.items():
        lod[name] = spec
    dirs = w.setdefault('asset_dirs', [])
    for f in sorted((ST / 'cells').glob('c[0-4]_[01].cell.json')):
        for p in json.loads(f.read_text())['placements']:
            x, z = p['position'][0], p['position'][-1]
            if not in_zone(x, z):
                continue
            for name in (p['asset'], p['collision']):
                if name in ('self', 'none') or name.startswith('gbt_'):
                    continue
                src = _find(name)
                if src is None:
                    raise SystemExit(f'place/street.py: no asset recipe {name!r}')
                add_dir(dirs, Path(__import__('os').path.relpath(src.parent, ST)).as_posix())
