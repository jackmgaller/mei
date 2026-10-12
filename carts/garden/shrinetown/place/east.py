"""Shrine town, placement zone east (PLACE_SPLIT.md): the school, the overpass, the front road's
east part and the culvert; 40 <= z < 128 and x >= 210, and the schoolyard south of z 40 (the pool
and the sports ground), which the zone's list gives it.

Called through place/__init__.py by notes/gen_town.py (`town`: the cells and the town's world
part) and by make_world.py (`world`: the asset directories). It swaps the grey boxes for the real
assets, with the poles and rails they carry, and dresses the zone with a few props. Every number
comes from the asset's own generator (its docstring) or PLACEMENT_NOTES.md; what differs from the
grey box is in DESIGN.md, section 12.6, "East".
"""
import math

# The grey boxes this zone replaces (placement ids in the town's cells). The east hoarding and the
# neighbours' backs are the frame's (place/art.py).
GREY = {'school', 'school_stair', 'gym', 'tyre_steps', 'tyre_steps_2', 'climbing_frame', 'overpass',
        'culvert_deck',
        'pole_road220', 'pole_road250', 'pole_road280',
        'maple_0', 'maple_1', 'zelkova_0', 'zelkova_1', 'zelkova_2', 'zelkova_3', 'zelkova_4'}


TALL_POLES = (250, 280)                   # the poles either side of the overpass (place/street.py)


def local_to_world(at, yaw, p):
    """A point in an asset's frame, placed at `at` turned by `yaw` (mesh_at's convention: 90 turns
    the -Z front toward -X)."""
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    x, y, z = p
    return (round(at[0] + x * c + z * s, 3), round(at[1] + y, 3), round(at[2] - x * s + z * c, 3))


def town(g):
    cells, place, entity, path, ops = g['cells'], g['place'], g['entity'], g['path'], g['ops']

    # ---- the grey boxes out
    for c in cells.values():
        c['placements'] = [p for p in c['placements'] if p['id'] not in GREY]

    def put(pid, name, at, yaw=0, col=None):
        """A real asset; its collision is NAME_col unless given ('self', 'none' or a name)."""
        place(pid, (name, col or f'{name}_col'), at[0], at[1], at[2], yaw)

    def rail(name, pts):
        path(name, pts)

    # ---- the schoolhouse: an L (the classroom block along the north, the wing down the west),
    # roof 18.9, its fire stair on the east end. The flagpole is a pole.
    SCHOOL = (273.0, 0.0, 71.0)
    put('schoolhouse', 'schoolhouse', SCHOOL)
    entity('pole_school_flag', 'pole', *local_to_world(SCHOOL, 0, (6.0, 0.0, -2.0)), {'height': 9.1})

    # ---- the gym, entrance east toward the school (yaw 270): x 214-238, z 63.7-94.3, crown 9.0;
    # the entrance canopy (3.45) and the front eave (7.4) are the way up to the roof
    put('gym', 'school_gym', (226.0, 0.0, 79.0), 270)

    # ---- the pool: its tank opening x 216-238, z 26-36 (the terrain is carved there, below)
    put('pool', 'school_pool', (227.0, 0.0, 31.0))

    # ---- the sports ground (x 244-292, z 18-52): a goal at each end, mouths facing each other; the
    # crossbars (2.25) are rails
    for k, (gx, yaw) in enumerate(((247.0, 270), (289.0, 90))):
        at = (gx, 0.0, 35.0)
        put(f'goal_{k}', 'sports_goal', at, yaw)
        rail(f'goal_{k}_bar', [local_to_world(at, yaw, (-2.5, 2.25, -0.95)), local_to_world(at, yaw, (2.5, 2.25, -0.95))])
    # the climbing frame where the grey box had it: four climbing poles (to 4.38, under the beam)
    # and the overhead ladder's hang rail at 2.2, just under its walkable strip's collision
    # (2.24-2.48; the generator's 2.3 is inside it)
    FRAME = (269.0, 0.0, 33.0)
    put('climbing_frame', 'sports_climbing_frame', FRAME)
    for k, px in enumerate((-2.2, -1.1, 1.1, 2.2)):
        entity(f'pole_frame_{k}', 'pole', *local_to_world(FRAME, 0, (px, 0.0, 2.0)), {'height': 4.38})
    rail('frame_ladder', [local_to_world(FRAME, 0, (0.0, 2.2, -2.2)), local_to_world(FRAME, 0, (0.0, 2.2, 1.8))])
    # two rows of tyre steps, where the grey box's two steps were (the tyres' tops 0.35-0.67)
    put('tyres_0', 'sports_tyre_steps', (249.0, 0.0, 25.0))
    put('tyres_1', 'sports_tyre_steps', (249.0, 0.0, 28.0), 180)

    # ---- the overpass: deck 7.0 along z 96-126 at x 260.5-263.5; the school stair down west to
    # x 246 (z 96-99), the cemetery stair east to x 278 (z 123-126). The handrails (8.12) are two
    # rails, each running down one stair, along one side of the deck and down the other stair.
    OV = (262.0, 0.0, 111.0)
    put('overpass', 'overpass', OV, 90)
    y, yb = 8.12, 7.0 - (7.0 / 14.5) * (15.7 - 1.5) + 1.12
    side_a = [(14.95, yb, -15.7), (14.95, y, -1.5), (14.95, y, 1.45), (-12.05, y, 1.45), (-12.05, yb, 15.7)]
    side_b = [(-x, yy, -z) for x, yy, z in side_a]
    rail('overpass_rail_w', [local_to_world(OV, 90, p) for p in side_a])
    rail('overpass_rail_e', [local_to_world(OV, 90, p) for p in side_b])

    # ---- the front road's east part: the utility poles, on the street zone's road line (z 106,
    # yaw 90: the crossarm across the road). The wires (place/street.py, `wire_road_a`/`_b`, at 8.0,
    # z 105.2 and 106.8) run on them from x 10 to 280. The two either side of the overpass (x 250
    # and 280) are the tall pole (wires at 10.5), so the span between them passes 3.5 m over the
    # deck (7.0) and 2.4 m over its handrails: at 8.0 it ran through them (alpha review r16 #1).
    for x in (220, 250, 280):
        name = 'town_utility_pole_tall' if x in TALL_POLES else 'town_utility_pole_transformer'
        put(f'pole_road{x}', name, (float(x), 0.0, 106.0), 90)

    # ---- the culvert's slab in the road (the grey box's flat slab): the road's rows, kerbs and a
    # parapet over each mouth (assets/culvert_deck)
    put('culvert_deck', 'culvert_deck', (236.0, 0.0, 111.0))

    # ---- street trees. The grey box's maples on the road's north verge become zelkovas (one leaf
    # sheet for the zone's trees). The zelkova row south of the road beside the underpass (spec
    # 7.1) moves to z 97 and west of the viaduct (x 296-308): its crowns (6 m) reached the deck and
    # the wires at z 100.
    for k, (x, z) in enumerate([(216, 122), (248, 121)]):
        put(f'zelkova_n{k}', 'tree_zelkova', (float(x), 0.0, float(z)))
    for k, x in enumerate((268, 275, 282, 289)):
        put(f'zelkova_s{k}', 'tree_zelkova', (float(x), 0.0, 97.0), 37 * k)

    # ---- props (spec 8.2: small, few): the school-zone signs where the lane meets the road, a
    # curve mirror at the gym's corner, a fire hydrant, benches by the sports ground
    put('signs_school', 'town_road_signs', (244.0, 0.0, 101.5), 180, 'none')
    put('mirror_gym', 'traffic_mirror', (240.0, 0.0, 95.5), 225)
    put('hydrant_road', 'firepost', (232.0, 0.0, 102.6), 180)
    for k, x in enumerate((256.0, 262.0)):
        put(f'bench_ground{k}', 'town_bench', (x, 0.0, 53.5))
    # the schoolyard's tree (the schoolhouse's own was two flat spheres, alpha review r16 #4): the
    # shrine's small maple, in autumn as the town is, west of the paved way to the fire stair
    # (x 281-287) and clear of the bars (z 59) and the flagpole (279, 69)
    put('maple_school', 'tree_maple_small', (278.5, 0.0, 63.5), 40)

    # ---- terrain. The pool's carve is the asset's tank opening, x 216-238, z 26-36, to -1.3 (the
    # liner's floor is at -1.2, 0.1 inside the cut: no z-fight), water at -0.3 (0.9 m deep).
    POOL_OLD = [214, 22, 240, 40]
    ops[:] = [o for o in ops if o.get('area', {}).get('rect') != POOL_OLD]
    POOL = [216, 26, 238, 36]
    ops += [{'op': 'cliff', 'area': {'rect': POOL}, 'height': -1.3, 'material': 'bank'},
            {'op': 'set', 'area': {'rect': POOL}, 'height': -1.3},
            {'op': 'paint', 'area': {'rect': POOL}, 'material': 'bed'},
            {'op': 'water', 'area': {'rect': POOL}, 'level': -0.3, 'material': 'water'},
            # the school lane's way to the fire stair, whose foot is at (283.8, 76.3): paving from
            # the sports ground's north edge
            {'op': 'paint', 'area': {'rect': [281, 52, 287, 76]}, 'material': 'paving'}]


def world(g):
    """The real assets' folders in the world's asset directories."""
    from place import add_dir
    st = g['ST']
    dirs = g['world'].setdefault('asset_dirs', [])
    for name in _placed(g):
        d = f'assets/{name}'
        if (st / d / f'{name}.asset.json').is_file():
            add_dir(dirs, d)


def _placed(g):
    """The assets the town's cells place (make_world.py runs on its own, after gen_town.py)."""
    import json
    names = []
    for f in sorted((g['ST'] / 'cells').glob('c[0-4]_[01].cell.json')):
        for p in json.loads(f.read_text())['placements']:
            x, z = p['position'][0], p['position'][-1]
            if x >= 210 and z < 128 and p['asset'] not in names and not p['asset'].startswith('gbt_'):
                names.append(p['asset'])
    return names
