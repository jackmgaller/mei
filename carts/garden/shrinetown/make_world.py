#!/usr/bin/env python3
"""Joins the shrine town's three grey-box regions into one world: shrinetown.world.json (world
`shrinetown`) and its ground, shrinetown.heights.txt.

    python3 carts/garden/shrinetown/make_world.py

Run the three region generators first (README.md, "How it is made"); this reads what they wrote:
parts/town.json, parts/core.json, parts/mountain.json and the three heights files. It writes no
cells and no assets: those are the regions'. What it adds is what only exists once the regions
are together (DESIGN.md, "The joined grey box"):

- one terrain field over the whole level (fields may not touch, so the three regions' fields
  become one): the regions' heights files stacked, then the town's, the core's and the mountain's
  operations in that order, then the level's rims;
- the routes that cross a row seam as one path each (the woods trail, the canal path through the
  park and the bamboo, the stream from the falls pool to the pond);
- the world's settings: assets from the regions' folders and the real pagoda's collision, layers,
  levels of detail, stand-ins, the World Checker's thresholds, and the two texture regions
  (TEXTURES.md; which cell is in which is layout.region_of()).
"""
import json
import sys
from pathlib import Path

ST = Path(__file__).resolve().parent
sys.path.insert(0, str(ST))
import layout as L
OUT = ST / 'shrinetown.world.json'
HEIGHTS = 'shrinetown.heights.txt'


def load(name):
    return json.loads((ST / 'parts' / f'{name}.json').read_text())


town, core, mountain = load('town'), load('core'), load('mountain')


def rows(path):
    return [l for l in (ST / path).read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]


# ---- the ground: z 0-126 from the town's file, 128-254 from the core's, 256-384 from the mountain's
t, c, m = rows('parts/town_heights.txt'), rows('parts/core_heights.txt'), rows('parts/mountain.heights.txt')
assert len(t) == len(c) == len(m) == 65, (len(t), len(c), len(m))
grid = t[:64] + c[:64] + m
assert all(len(r.split()) == 161 for r in grid)
(ST / HEIGHTS).write_text('# The shrine town\'s ground, x 0-320 and z 0-384 every 2 m (a line per z): the regions\' heights files\n'
                          '# stacked (parts/town_heights.txt, core_heights.txt, mountain.heights.txt). Written by make_world.py.\n'
                          + '\n'.join(grid) + '\n')

# ---- terrain materials: the regions' by name (a name two regions define keeps the first one's colour)
materials, clashes = {}, []
for region, part in (('town', town), ('core', core), ('mountain', mountain)):
    for name, spec in part['terrain']['materials'].items():
        if name in materials:
            if materials[name] != spec: clashes.append(f'{name} ({region})')
            continue
        materials[name] = spec

# ---- operations, in order
core_field = core['terrain']['fields']['core']
ops = [{'op': 'paint', 'area': {'rect': [0, 0, 320, 128]}, 'material': 'street'}]      # the town's ground
ops += town['terrain']['operations']
ops += core_field['operations']
ops += mountain['terrain']['operations']
# The level's rims where the regions left none (spec 1.8: no jump or glide leaves the level): the
# west edge along the park and the bamboo's foot (the mountain's west rim, +14, starts at z 256),
# and the east edge north of the road beside the cemetery (the viaduct leaves at z 134-152).
ops += [{'op': 'cliff', 'area': {'rect': [0, 118, 2, 256]}, 'height': 10.0, 'material': 'rock'},
        {'op': 'cliff', 'area': {'rect': [318, 118, 320, 132]}, 'height': 8.0, 'material': 'rock'},
        {'op': 'cliff', 'area': {'rect': [318, 154, 320, 256]}, 'height': 8.0, 'material': 'rock'}]

# ---- paths: the regions', with the routes that cross a row seam joined
paths = {}
for part in (town, core, mountain):
    for name, spec in part['paths'].items():
        assert name not in paths, name
        paths[name] = spec


def join(name, first, second, cut_first=0, cut_second=0):
    """One path from two regions' halves that meet at a row seam (dropping duplicated seam points)."""
    a, b = paths.pop(first), paths.pop(second)
    pts = a['points'][:len(a['points']) - cut_first] + b['points'][cut_second:]
    paths[name] = dict(a, points=pts)


join('trail_west', 'core_trail_woods', 'trail_west_north', cut_second=1)               # road -> fox grove
join('trail_canal_west', 'core_park_path', 'trail_canal_lane_north', cut_second=1)     # park -> bamboo
join('stream', 'stream_gorge', 'core_stream', cut_first=1)                             # falls pool -> pond
for op in ops:
    assert op.get('path') not in ('core_trail_woods', 'trail_west_north', 'core_park_path',
                                  'trail_canal_lane_north', 'stream_gorge', 'core_stream'), op

layers = {}
for part in (town, core, mountain):
    layers.update(part['layers'])
scatter = {**core['scatter'], **mountain['scatter']}

# ---- stand-ins capped (spec 8.2-8.3, option 1 of 8.3): 90 triangles a town cell (rows 0-1), 140 the
# landmark cells (the temple c2_3, the pagoda and the sacred cedar c2_4, the stage c2_5), 60 every
# other cell; the ground on a 32 m grid. The pond's cell keeps its water whole (water is not
# resampled), 103 triangles of ground: its cap is 110.
LANDMARKS = ('c2_3', 'c2_4', 'c2_5')
cell_caps = {f'c{i}_{j}': {'triangles': 140 if f'c{i}_{j}' in LANDMARKS else 60}
             for i in range(5) for j in range(2, 6)}
cell_caps['c3_2'] = {'triangles': 110}
STANDINS = {'distance': 128, 'sweeps': True, 'triangles': 90, 'ground': 32, 'cells': cell_caps}

shrine = json.loads((ST.parent / 'shrine' / 'shrine.world.json').read_text())

# ---- texture regions (TEXTURES.md): the town (rows 0-1) and the shrine (rows 2-5). Each has its own
# texture set in slots 13-0 (slot 14 holds the swatch row, 15 the fonts); entering one loads its set
# over the other's. The budgets are the plan's totals, each zone's allowance and the ground's:
# 380 KB of the town's 448 (15% free) and 300 KB of the shrine's (a third free). The shrine's palette
# variants (day, night) and backdrop for both, so the sky does not change at the boundary.
TEXTURE_BUDGETS = {'town': 380 * 1024, 'shrine': 300 * 1024}
regions = {r: {'textures': {'slots': '13-0', 'budget': TEXTURE_BUDGETS[r]},
               'variants': shrine['regions']['shrine']['variants'],
               'backdrop': shrine['regions']['shrine']['backdrop']} for r in L.REGIONS}
world = {
    'format': 'mei-world', 'version': 1, 'name': 'shrinetown',
    'game': '../world/garden.game.mochi',
    'assets': 'assets/greybox/town',
    # the other regions' grey boxes; a folder per real asset (with assets/arch_pagoda, the pagoda's
    # climbing collision, and assets/game, game.py's train and omamori); the shrine's assets, which
    # the zones place too
    'asset_dirs': ['assets/greybox/core', 'assets/greybox/mountain', 'assets/*', '../shrine/assets'],
    'cell_dir': 'cells',
    'grid': {'cell_size': 64}, 'overhang': 32,
    'collision': town['collision'],
    'regions': regions,
    'runtime': {'depth': True, 'perspective': True, 'near_far': 192},
    'verification': {'thresholds': {'cell_triangles': 12000, 'cell_placements': 400, 'standin_triangles': 140}},
    'layers': layers,
    'paths': paths,
    'terrain': {'materials': materials, 'fields': {'ground': {
        'spacing': 2, 'min': [0, 0], 'max': [320, 384], 'heights': HEIGHTS,
        'material': 'floor', 'steep': {'degrees': 38, 'material': 'rock'}, 'tolerance': 0.15, 'tile': 16,
        'lod': {'distance': 22, 'tolerance': 2.5}, 'operations': ops}}},
    'scatter': scatter,
    'lod': {'ground': [{'distance': 36, 'grid': 8}, {'distance': 76, 'grid': 16}],
            'sweeps': {'cull': 56, 'paths': {'torii_steps': {'cull': 44}}}},
    'standins': STANDINS,
    'meshes': {'quads': True},
}
# the placement zones (place/ZONE.py): asset directories, layers, paths for the real assets
from place import apply as apply_zones
apply_zones('world', globals())
OUT.write_text(json.dumps(world, indent=1) + '\n')
print(f'{OUT.name}: {len(paths)} paths, {len(ops)} operations, {len(materials)} materials, {len(layers)} layers, '
      f'{len(scatter)} scatters')
if clashes:
    print('materials defined differently by two regions (the first kept):', ', '.join(clashes))
