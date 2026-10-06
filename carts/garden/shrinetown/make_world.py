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
STANDINS = {'distance': 128, 'sweeps': True, 'triangles': 90, 'ground': 32, 'cells': cell_caps,
            # the trees' far cards and the landmarks' impostors stay cut out in the stand-ins: their
            # textures in slots 0 and 31 (64 KB: slot 0 kept free by the regions' split, and the top of
            # VRAM's second megabyte), held by both regions' sets (WORLDKIT.md, "Stand-ins made by the kit")
            'textures': {'slots': '0,31'}}
# ---- haze (WORLDKIT.md, "Haze"): baked into the stand-ins only, a little. The GPU's fog (FOG_RANGE
# below) fades every far surface by its depth, the levels included, so the levels are not hazed
# again; the stand-ins' far colours are moved a little toward each variant's sky as well, which
# softens their flat colours where the fog is still thin (100-200 units).
HAZE = {'start': 20, 'end': 280, 'amount': 0.0, 'standins': 0.15, 'elevation': 1}

shrine = json.loads((ST.parent / 'shrine' / 'shrine.world.json').read_text())

# ---- texture regions (TEXTURES.md): the town (rows 0-1) and the shrine (rows 2-5). Each has its own
# texture set in slots 13-1 and 16-31 (VRAM at 2 MB; slot 14 holds the swatch row and the star, 15
# the fonts, 0 the far views' common stand-in set); entering one loads its set over the other's,
# about 0.94 cycles a byte, so a budget is also the crossing's cost. The budgets are the zones'
# allowances, the ground's and 64 KB for the far views: 668 KB for the town, 460 KB for the shrine
# (TEXTURES.md, "The budgets"). The
# shrine's palettes start at 256, in palette bank 1, so the town has 0-253 (254 is the star's, 255
# the fonts'). The shrine's palette variants (day, night), a copy per region, without its night's
# water colour (the water is textured: the night's multiply tints it, art/water/APPLY.md); each
# region its own backdrop, from art/backdrop/backdrop.json (art/backdrop/APPLY.md): a sky and a far
# view drawn for the streets and one for the shrine's grounds and mountain, with the night's exact
# colours.
TEXTURE_SLOTS = '13-1,16-31'
TEXTURE_BUDGETS = {'town': 668 * 1024, 'shrine': 460 * 1024}
PALETTES = {'shrine': {'first': 256}}
BD = json.loads((ST / 'art' / 'backdrop' / 'backdrop.json').read_text())


# ---- fog toward a colour (the GPU's, DECISIONS.md "Fog toward a colour"; DESIGN.md 12.7): each
# variant fades far geometry toward its own sky at 1 degree above the horizon, the day's from 30 to
# 380 units (a haze: the far ring's stand-ins half gone at 200), the night's from 16 to 220 (the
# dark). The backdrop's stop below the horizon (-8 degrees) is the fog colour too, so the sky under
# the farthest fogged ground has no band of another colour.
FOG_RANGE = {'day': (30, 380), 'night': (16, 220)}


def sky_at(elevations, colours, e):
    for k in range(1, len(elevations)):
        if e <= elevations[k]:
            t = (e - elevations[k - 1]) / (elevations[k] - elevations[k - 1])
            a, b = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (colours[k - 1], colours[k]))
            return '#' + ''.join(f'{round(x + (y - x) * t):02x}' for x, y in zip(a, b))
    return colours[-1]


def fog_colour(r, name):
    return sky_at(BD[r]['elevations'], BD[r]['sky'][name], 1.0)


def sky(r):
    """The region's sky with its stop below the horizon in each variant's fog colour."""
    out = {}
    for name, colours in BD[r]['sky'].items():
        out[name] = [fog_colour(r, name)] + colours[1:] if name in FOG_RANGE and BD[r]['elevations'][0] < 0 else colours
    return out


def variants(r):
    v = json.loads(json.dumps(shrine['regions']['shrine']['variants']))
    for spec in v.values():
        spec.get('colors', {}).pop('water', None)
        if 'colors' in spec and not spec['colors']:
            del spec['colors']
    for name, colours in BD[r].get('variants', {}).items():
        v[name]['backdrop'] = colours
    for name, (near, far) in FOG_RANGE.items():
        v[name]['fog'] = {'color': fog_colour(r, name), 'near': near, 'far': far}
    return v


regions = {r: {'textures': {'slots': TEXTURE_SLOTS, 'budget': TEXTURE_BUDGETS[r]},
               **({'palettes': PALETTES[r]} if r in PALETTES else {}),
               'variants': variants(r),
               'backdrop': {'elevations': BD[r]['elevations'], 'sky': sky(r),
                            'silhouette': {'image': f'art/backdrop/{r}_backdrop.png', 'horizon': BD[r]['horizon'],
                                           'repeat': 1}}} for r in L.REGIONS}
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
    'haze': HAZE,
    'meshes': {'quads': True},
}
# the placement zones (place/ZONE.py): asset directories, layers, paths for the real assets
from place import apply as apply_zones
apply_zones('world', globals())
# the grey boxes the world stage swapped out (the shrine zone's, place/shrine.py): their recipes go
_used = json.dumps(world) + ''.join(f.read_text() for f in sorted((ST / 'cells').glob('*.cell.json')))
for _d, _pre in (('town', 'gbt_'), ('core', 'gbc_'), ('mountain', 'gbm_')):
    for _f in sorted((ST / 'assets' / 'greybox' / _d).glob(_pre + '*.asset.json')):
        if '"' + _f.name[:-len('.asset.json')] + '"' not in _used:
            _f.unlink()
OUT.write_text(json.dumps(world, indent=1) + '\n')
print(f'{OUT.name}: {len(paths)} paths, {len(ops)} operations, {len(materials)} materials, {len(layers)} layers, '
      f'{len(scatter)} scatters')
if clashes:
    print('materials defined differently by two regions (the first kept):', ', '.join(clashes))
