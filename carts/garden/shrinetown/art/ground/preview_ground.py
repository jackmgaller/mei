#!/usr/bin/env python3
"""Builds a small test world of the shrine town's ground textures and edges and draws it on the
console, day and night, at gameplay distances: $B/ground_preview/ (world, report.json, shots).

The world is 128 x 128 m in four 64 m cells: the south half is a `town` region (a road with
its lines, a zebra crossing and stop lines, kerbs, sidewalks and the tactile strip, the plaza,
concrete, the sports ground and its line, a canal in its stone walls, the neighbours' backs and
a hoarding), the north half a `shrine` region (a strip of every shrine-region material and a rock
and canal-wall cliff). Each region's report.json `textures.vram_bytes_allocated` is what the
materials cost at the spans GROUND.md gives, so this is also how those numbers were measured.

    make B=build-gt build-gt/meic build-gt/mei-headless build-gt/mei-asset-probe build-gt/mei-scene-probe
    B=build-gt python3 carts/garden/shrinetown/art/ground/preview_ground.py [--shots-only]

Needs NumPy (the World Checker is skipped, the asset checks are not) and Pillow; macOS sips for
the PNGs.
"""
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE.parents[1]                      # carts/garden/shrinetown
ROOT = ST.parents[2]
B = os.environ.get('B', 'build')
OUT = ROOT / B / 'ground_preview'
SRC = OUT / 'src'
SHRINE_ART = ST.parent / 'shrine' / 'assets' / 'art'

# material: (image, scale, span) -- GROUND.md's table
TOWN = {
    'asphalt': ('asphalt', 2.0, 23), 'asphalt_line': ('asphalt_line', 2.0, 23),
    'asphalt_zebra': ('asphalt_zebra', 2.0, 23), 'asphalt_stop': ('asphalt_stop', 2.0, 71),
    'sidewalk': ('sidewalk', 2.0, 23), 'sidewalk_tactile': ('sidewalk_tactile', 2.0, 23),
    'kerb': ('kerb', 1.0, 23), 'plaza': ('plaza', 4.0, 23), 'concrete': ('concrete', 2.0, 23),
    'ground': ('ground', 2.0, 23), 'ground_line': ('ground_line', 2.0, 23),
    'canal_wall': ('canal_wall', 1.6, 23), 'pond_bed': ('shrine:pond_bed', 2.4, 23),
}
SHRINE = {
    'floor': ('shrine:floor', 2.4, 87), 'litter': ('shrine:litter', 2.4, 87), 'moss': ('shrine:moss', 2.4, 87),
    'earth': ('shrine:earth', 2.4, 87), 'path': ('shrine:path', 2.4, 87), 'gravel': ('shrine:gravel', 2.4, 87),
    'paving': ('shrine:paving', 2.4, 87), 'steps': ('shrine:steps', 2.4, 87), 'stone': ('shrine:stone', 3.2, 87),
    'rock': ('shrine:rock', 4.8, 87),
    'cemetery_gravel': ('cemetery_gravel', 2.4, 87), 'bamboo_floor': ('bamboo_floor', 2.4, 87),
    'park_grass': ('park_grass', 2.4, 87), 'park_sand': ('park_sand', 2.4, 23),
}


def image(ref):
    if ref.startswith('shrine:'):
        return SHRINE_ART / f'terrain_{ref[7:]}.png'
    return HERE / f'{ref}.png'


def mean(path):
    from PIL import Image
    im = Image.open(path).convert('RGB')
    px = [im.getpixel((x, y)) for y in range(im.height) for x in range(im.width)]
    return '#' + ''.join(f'{round(sum(p[k] for p in px) / len(px)):02x}' for k in range(3))


def material(ref, scale, span, **extra):
    src = image(ref)
    dst = SRC / 'art' / f'{ref.replace(":", "_")}.png'
    shutil.copy(src, dst)
    tex = {'image': f'art/{dst.name}', 'scale': [scale, scale], 'span': span, **extra}
    return {'color': mean(src), 'texture': tex}


def world():
    if SRC.exists():
        shutil.rmtree(SRC)
    (SRC / 'art').mkdir(parents=True)
    (SRC / 'cells').mkdir()
    (SRC / 'assets').mkdir()
    for d in ('edge_neighbour', 'edge_hoarding'):
        shutil.copytree(ST / 'assets' / d, SRC / 'assets' / d, ignore=shutil.ignore_patterns('*.py'))
    shutil.copy(ROOT / 'examples/worlds/shrine_grounds/garden.game.mochi', SRC / 'garden.game.mochi')

    mats = {k: material(*v) for k, v in {**TOWN, **SHRINE}.items()}
    # markings: a texture's v runs along z; a line along x (the road) is rotate 90, as are the
    # zebra's bars (they run with the traffic); a stop line across the road is rotate 0
    mats['asphalt_line_x'] = material('asphalt_line', 2.0, 23, rotate=90)
    mats['ground_line_x'] = material('ground_line', 2.0, 23, rotate=90)
    mats['asphalt_zebra'] = material('asphalt_zebra', 2.0, 23, rotate=90)
    mats['sidewalk_tactile_x'] = material('sidewalk_tactile', 2.0, 23, rotate=90)
    mats['water'] = {'color': '#3f7393', 'water': True, 'tag': 'water'}

    def paint(rect, m):
        return {'op': 'paint', 'area': {'rect': rect}, 'material': m}

    ops = [
        # town: z 0-64
        paint([0, 0, 128, 64], 'concrete'),
        paint([0, 18, 128, 32], 'asphalt'),                 # the road, z 18-32, along x
        paint([0, 18, 128, 20], 'asphalt_line_x'),          # edge lines (centred 1 m into the row)
        paint([0, 30, 128, 32], 'asphalt_line_x'),
        paint([0, 24, 128, 26], 'asphalt_line_x'),          # the centre line at z 25
        paint([60, 18, 64, 32], 'asphalt_zebra'),           # a crossing at x 60-64: bars along x
        paint([52, 18, 54, 24], 'asphalt_stop'),            # stop lines across each lane
        paint([70, 26, 72, 32], 'asphalt_stop'),
        paint([0, 12, 128, 18], 'sidewalk'), paint([0, 32, 128, 38], 'sidewalk'),
        paint([0, 34, 128, 36], 'sidewalk_tactile_x'),
        paint([60, 12, 64, 18], 'sidewalk_tactile'),
        paint([0, 38, 56, 64], 'plaza'),
        paint([56, 38, 76, 64], 'concrete'),
        paint([76, 38, 128, 64], 'ground'),
        paint([76, 50, 128, 52], 'ground_line_x'),
        paint([100, 38, 102, 64], 'ground_line'),
        {'op': 'cliff', 'area': {'rect': [8, 2, 120, 10]}, 'height': -1.2, 'material': 'canal_wall'},
        {'op': 'set', 'area': {'rect': [8, 2, 120, 10]}, 'height': -1.2},
        paint([8, 2, 120, 10], 'pond_bed'),
        {'op': 'water', 'area': {'rect': [8, 2, 120, 10]}, 'level': -0.4, 'material': 'water'},
        # shrine: z 64-128, a strip of each material along z
    ]
    strips = ['floor', 'litter', 'moss', 'earth', 'path', 'gravel', 'paving', 'steps', 'stone', 'rock',
              'pond_bed', 'cemetery_gravel', 'bamboo_floor', 'park_grass', 'park_sand', 'canal_wall']
    for k, m in enumerate(strips):
        ops.append(paint([k * 8, 64, k * 8 + 8, 120], m))
    ops += [paint([0, 120, 64, 128], 'floor'), paint([64, 120, 128, 128], 'moss'),
            {'op': 'cliff', 'area': {'rect': [0, 120, 64, 128]}, 'height': 10.0, 'material': 'rock'},
            {'op': 'cliff', 'area': {'rect': [64, 120, 128, 128]}, 'height': 3.0, 'material': 'canal_wall'}]
    paths = {'kerb_s': {'points': [[0, 0.0, 18.1], [128, 0.0, 18.1]],
                        'sweep': {'profile': [[-0.1, 0], [-0.1, 0.15], [0.1, 0.15], [0.1, 0]], 'material': 'kerb'}},
             'kerb_n': {'points': [[0, 0.0, 31.9], [128, 0.0, 31.9]],
                        'sweep': {'profile': [[-0.1, 0], [-0.1, 0.15], [0.1, 0.15], [0.1, 0]], 'material': 'kerb'}}}
    variants = {'day': {}, 'night': {'surface': {'multiply': '#4a5884'}, 'colors': {'water': '#1c3050'}}}
    w = {'format': 'mei-world', 'version': 1, 'name': 'ground_preview', 'game': 'garden.game.mochi',
         'assets': 'assets/edge_neighbour', 'asset_dirs': ['assets/edge_hoarding'], 'cell_dir': 'cells',
         'grid': {'cell_size': 64},
         'regions': {'town': {'variants': variants},
                     'shrine': {'variants': {'day': {}, 'night': {'surface': {'multiply': '#4a5884'}}}}},
         'runtime': {'depth': True, 'perspective': True},
         'paths': paths,
         'terrain': {'materials': mats, 'fields': {'ground': {
             'spacing': 2, 'min': [0, 0], 'max': [128, 128], 'material': 'concrete',
             'steep': {'degrees': 38, 'material': 'rock'}, 'tolerance': 0.15, 'tile': 16,
             'lod': {'distance': 22, 'tolerance': 2.5}, 'operations': ops}}}}
    (SRC / 'ground_preview.world.json').write_text(json.dumps(w, indent=1))
    place = {
        'c0_0': [{'id': 'nb_s0', 'asset': 'edge_neighbour_s0', 'position': [16, 0, 0.2], 'yaw': 180, 'collision': 'self'},
                 {'id': 'nb_s1', 'asset': 'edge_neighbour_s1', 'position': [48, 0, 0.2], 'yaw': 180, 'collision': 'self'},
                 {'id': 'hoarding_w', 'asset': 'edge_hoarding', 'position': [0.2, 0, 25], 'yaw': 270, 'collision': 'self'}],
        'c1_0': [{'id': 'nb_s4', 'asset': 'edge_neighbour_s4', 'position': [88, 0, 0.2], 'yaw': 180, 'collision': 'self'},
                 {'id': 'nb_e0', 'asset': 'edge_neighbour_e0', 'position': [127.8, 0, 46], 'yaw': 90, 'collision': 'self'}],
        'c0_1': [], 'c1_1': [],
    }
    for cid, pl in place.items():
        i, j = int(cid[1]), int(cid[3])
        cell = {'format': 'mei-world-cell', 'version': 1, 'id': cid, 'at': [i, j],
                'region': 'town' if j == 0 else 'shrine', 'placements': pl}
        (SRC / 'cells' / f'{cid}.cell.json').write_text(json.dumps(cell, indent=1))


def build():
    r = subprocess.run([sys.executable, str(ROOT / 'tools/mei_world.py'), 'build',
                        str(SRC / 'ground_preview.world.json'), '-o', str(OUT / 'world'), '--world-checker', 'skip',
                        '--compiler', str(ROOT / B / 'meic'), '--runner', str(ROOT / B / 'mei-headless'),
                        '--probe', str(ROOT / B / 'mei-asset-probe')], capture_output=True, text=True)
    res = json.loads(r.stdout) if r.stdout.strip().startswith('{') else {'ok': False, 'out': r.stdout + r.stderr}
    if not res.get('ok', r.returncode == 0):
        print(json.dumps(res, indent=1)[:4000])
        sys.exit(1)
    rep = json.loads((OUT / 'world' / 'report.json').read_text())
    for name, reg in rep['regions'].items():
        t = reg.get('textures', {})
        print(f"region {name}: {t.get('vram_bytes_allocated')} bytes allocated, {t.get('tiles')} tiles, "
              f"palettes {json.dumps(t.get('palettes'))[:200]}")
        for a, v in (t.get('by_asset') or {}).items():
            print('   ', a, v)
    tt = rep.get('terrain', {}).get('textures', {})
    for m, v in tt.items():
        print(f"  {m:18} span {v['span']:3} stored {v['stored']} texel_cm {v.get('texel_cm')} far {v.get('far')} "
              f"tri {v.get('triangles')} windowed {v.get('windowed')}")
    (OUT / 'terrain_textures.json').write_text(json.dumps({'regions': {k: v.get('textures') for k, v in rep['regions'].items()},
                                                          'terrain': tt}, indent=1))


VIEWS = {
    'top': ((64, 60, 10), 0, -60, 0),
    'new_strips': ((104, 3.2, 68), 0, -14, 1),
    # name: eye (x, y, z), yaw deg (0 north, 90 east), pitch deg, region
    'road_east': ((20, 3.2, 14), 70, -14, 0),
    'crossing': ((62, 3.0, 4.5), 0, -18, 0),
    'road_long': ((4, 2.6, 25), 90, -8, 0),
    'plaza_ground': ((40, 3.4, 44), 60, -14, 0),
    'neighbours': ((60, 4, 56), 190, 8, 0),
    'neighbours_roof': ((70, 26, 62), 200, -10, 0),
    'canal': ((30, 2.6, 14), 200, -28, 0),
    'shrine_strips': ((64, 3.4, 70), 0, -12, 1),
    'shrine_low': ((20, 2.4, 76), 20, -16, 1),
    'shrine_high': ((64, 30, 60), 0, -35, 1),
    'cliff': ((40, 3, 104), 10, 10, 1),
    'hoarding': ((12, 2.4, 22), 280, 2, 0),
}


def shots():
    tmp = OUT / 'shots'
    tmp.mkdir(exist_ok=True)
    for name, (eye, yaw, pitch, region) in VIEWS.items():
        for variant, vname in ((0, 'day'), (1, 'night')):
            src = f'''cart "Ground preview"
import "depth.akr"
import "ground_preview.akr"
fn init() {{
    render_depth(true)
    render_perspective(true)
    assert(world_ground_preview_load())
    wp_region_enter({region}, {variant})
}}
fn update() {{}}
fn draw() {{
    cls({'rgb(150, 185, 220)' if variant == 0 else 'rgb(12, 16, 40)'})
    wp_draw(vec3({eye[0]:.3f}, {eye[1]:.3f}, {eye[2]:.3f}), {math.radians(yaw):.5f}, {math.radians(pitch):.5f})
}}
'''
            cart = tmp / f'{name}_{vname}.akr'
            cart.write_text(src)
            mei = tmp / f'{name}_{vname}.mei'
            ppm = tmp / f'{name}_{vname}.ppm'
            subprocess.run([str(ROOT / B / 'meic'), '-I', str(OUT / 'world'), str(cart), '-o', str(mei)], check=True)
            subprocess.run([str(ROOT / B / 'mei-headless'), str(mei), '--frames', '4', '--dump', str(ppm)], check=True,
                           stdout=subprocess.DEVNULL)
            subprocess.run(['sips', '-s', 'format', 'png', str(ppm), '--out', str(tmp / f'{name}_{vname}.png')],
                           check=True, stdout=subprocess.DEVNULL)
    # one sheet: day | night per view, 2x
    from PIL import Image
    names = list(VIEWS)
    sheet = Image.new('RGB', (2 * 640, len(names) * 480))
    for k, name in enumerate(names):
        for c, vname in enumerate(('day', 'night')):
            im = Image.open(tmp / f'{name}_{vname}.png').convert('RGB').resize((640, 480), Image.NEAREST)
            sheet.paste(im, (c * 640, k * 480))
    sheet.save(OUT / 'ground_views.png')
    print('wrote', OUT / 'ground_views.png')


if __name__ == '__main__':
    if '--shots-only' not in sys.argv:
        world()
        build()
    shots()
