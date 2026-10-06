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
import re
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
# landmark cells (the temple c2_3, the pagoda and the sacred cedar c2_4, the stage c2_5) and c1_2, 60
# every other cell; the ground on a 32 m grid. The courtyard's two cells hold the side and corridor
# halls (84 and 74 triangles at their level 1) and are seen from the pagoda at 60-130 m as stand-ins
# until the eye is in row 3: c2_2 (with the gate) has 220 and c3_2 270, since the pond keeps its
# water whole (water is not resampled: 103 triangles of ground), so that both halls are in each
# (ALPHA_REVIEW, far views: at 60 and 110 the halls were left out and popped in at z 256).
LANDMARKS = ('c2_3', 'c2_4', 'c2_5', 'c1_2')
COURTYARD = {'c2_2': 220, 'c3_2': 270}
cell_caps = {f'c{i}_{j}': {'triangles': COURTYARD.get(f'c{i}_{j}', 140 if f'c{i}_{j}' in LANDMARKS else 60)}
             for i in range(5) for j in range(2, 6)}
STANDINS = {'distance': 128, 'sweeps': True, 'triangles': 90, 'ground': 32, 'cells': cell_caps,
            # the trees' far cards and the landmarks' impostors stay cut out in the stand-ins: their
            # textures in slots 0, 31 and 30 (96 KB: slot 0 kept free by the regions' split, and the top
            # of VRAM's second megabyte; the third since the pagoda's star of cards, DESIGN.md 12.9), held
            # by both regions' sets (WORLDKIT.md, "Stand-ins made by the kit")
            'textures': {'slots': '0,31,30'}}
BD = json.loads((ST / 'art' / 'backdrop' / 'backdrop.json').read_text())

# ---- fog toward a colour (the GPU's, DECISIONS.md "Fog toward a colour"; DESIGN.md 12.7 and 12.9):
# each variant fades far geometry toward its fog colour (art/backdrop/backdrop.json "fog", drawn by
# draw_backdrop.py): by day the sky 3 degrees up, a pale blue-grey; by night the sky's
# deep blue at 9 degrees, darker than the horizon's purple, so far hills darken into the night
# instead of glowing. The far pass ends three cells off, 192-256 units along an axis, so the day's
# fog is 87 % at 192 and whole at 240, where the world's last cells may end; the night's 87 % at
# 192. The sky's stop below the horizon (-8 degrees) and the backdrop's band under the horizon are
# the fog colour, so the fogged end of the drawn world meets them in one colour (ALPHA_REVIEW,
# far views: the day fog ran on to 380 and the world stopped half fogged against a flat plain).
FOG_RANGE = {'day': (20, 240), 'night': (16, 220)}
FOG_COLOUR = BD['town']['fog']
assert BD['town'] == BD['shrine'], 'one backdrop for both regions (art/backdrop/APPLY.md)'

# ---- haze (WORLDKIT.md, "Haze"): baked into the stand-ins only, a little. The GPU's fog fades every
# far surface by its depth, the levels included, so the levels are not hazed again; the stand-ins'
# far colours are moved a little toward each variant's fog colour as well, which softens their flat
# colours where the fog is still thin (100-200 units).
HAZE = {'start': 20, 'end': 280, 'amount': 0.0, 'standins': 0.15, 'colors': dict(FOG_COLOUR)}

shrine = json.loads((ST.parent / 'shrine' / 'shrine.world.json').read_text())

# ---- texture regions (TEXTURES.md): the town (rows 0-1) and the shrine (rows 2-5). Since the alpha
# fixes (DESIGN.md 12.9) their texture sets are in disjoint slots, the town's 13-1 and 16-18 (16
# slots, 512 KB), the shrine's 19-29 (11, 352 KB), so both can be in VRAM at once (slot 14 holds the
# swatch row and the star, 15 the fonts, 0, 31 and 30 the far views' common stand-in set). A cart that
# enters both regions once and then draws with wp_region_loaded = -1 draws every near cell at its
# own levels, whichever side of z = 128 the eye is on, and crossing the line copies nothing but the
# backdrop; a cart that enters a region at a time still works as before (each entry copies only its
# own slots). The budgets are those slots: 512 KB for the town (it uses 376 KB), 352 KB for the
# shrine (212 KB). The
# shrine's palettes start at 256, in palette bank 1, so the town has 0-253 (254 is the star's, 255
# the fonts'). The shrine's palette variants (day, night), a copy per region, without its night's
# water colour (the water is textured: the night's multiply tints it, art/water/APPLY.md); and one
# backdrop for both, art/backdrop/backdrop.png (art/backdrop/APPLY.md): a sky and a far view round
# the level, with the night's exact colours, the same in both regions so that nothing in it moves
# when the line is crossed.
TEXTURE_SLOTS = {'town': '13-1,16-18', 'shrine': '19-29'}
TEXTURE_BUDGETS = {'town': 16 * 32768, 'shrine': 11 * 32768}
PALETTES = {'shrine': {'first': 256}}


def sky(r):
    """The region's sky with its stop below the horizon in each variant's fog colour."""
    out = {}
    for name, colours in BD[r]['sky'].items():
        out[name] = [FOG_COLOUR[name]] + colours[1:] if name in FOG_RANGE and BD[r]['elevations'][0] < 0 else colours
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
        v[name]['fog'] = {'color': FOG_COLOUR[name], 'near': near, 'far': far}
    if r == 'town':
        v['night']['texels'] = NEIGHBOUR_NIGHT
    return v


# The neighbours' lit panes at night (assets/edge_neighbour/make_edge_neighbour.py: LIT, LIT_NIGHT),
# near and far, every neighbour the cells place (all in the town's rows).
NEIGHBOURS = sorted(set(re.findall(r'"(edge_neighbour_[a-z0-9]+)"', ''.join(
    f.read_text() for f in sorted((ST / 'cells').glob('*.cell.json'))))))
NEIGHBOUR_NIGHT = {f'{n}.{m}': {'#3e4a5e': '#e8c878'} for n in NEIGHBOURS for m in ('facade', 'facade_far')}


regions = {r: {'textures': {'slots': TEXTURE_SLOTS[r], 'budget': TEXTURE_BUDGETS[r]},
               **({'palettes': PALETTES[r]} if r in PALETTES else {}),
               'variants': variants(r),
               'backdrop': {'elevations': BD[r]['elevations'], 'sky': sky(r),
                            'silhouette': {'image': 'art/backdrop/backdrop.png', 'horizon': BD[r]['horizon'],
                                           'repeat': 1}}} for r in L.REGIONS}

# ---- the ground's levels (WORLDKIT.md, "Levels of detail"): the field's coarse level from 22 units,
# to 2.5 units, drawn in each texture's mean colour, untextured; the far levels on 8- and 16-unit
# grids. The alpha review (far views) found the ridge, the grove and the mountain flat brown facets
# from 22 units; moving the coarse level out was measured and not taken (DESIGN.md 12.9): at 40 units
# and a tolerance of 1.5 the draw CPU rose by a median 13,000 cycles a view and the views over
# 600,000 near z = 128 went from 5 to 54 of 5,760, at 30 and 1.5 by 3,500 and to 20. At 1.2 or 1.0
# the kit also leaves a hole in level 0's floor under the giant cedar at (102, 252). A textured
# coarse level is the fix that costs no triangles (a World Kit change).
GROUND_LOD = {'distance': 22, 'tolerance': 2.5}
FAR_GROUND = [{'distance': 36, 'grid': 8}, {'distance': 76, 'grid': 16}]

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
    'verification': {'thresholds': {'cell_triangles': 12000, 'cell_placements': 400, 'standin_triangles': max(COURTYARD.values())}},
    'layers': layers,
    'paths': paths,
    'terrain': {'materials': materials, 'fields': {'ground': {
        'spacing': 2, 'min': [0, 0], 'max': [320, 384], 'heights': HEIGHTS,
        'material': 'floor', 'steep': {'degrees': 38, 'material': 'rock'}, 'tolerance': 0.15, 'tile': 16,
        'lod': GROUND_LOD, 'operations': ops}}},
    'scatter': scatter,
    'lod': {'ground': FAR_GROUND,
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
