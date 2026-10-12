#!/usr/bin/env python3
"""Pictures of the shrine town's grey box, drawn headless by the real reader (world and coins, no
player), into carts/garden/shrinetown/screenshots/NAME.png (needs sips, macOS).

Build the world first (make builds it with the garden cart; B is the build directory):
    make B=$B $B/carts/garden.mei
    B=$B python3 carts/garden/shrinetown/tools/shots.py [NAME ...]
    B=$B python3 carts/garden/shrinetown/tools/shots.py --at X Y Z YAW PITCH NAME   # any view
    B=$B python3 carts/garden/shrinetown/tools/shots.py --night art_spawn ...       # palette variant 1
YAW in degrees, 0 north (+z), 90 east; PITCH in degrees, negative looks down. The camera's region
is entered and its backdrop drawn, as the garden cart does; --night loads every region's `night`
variant (variant 1; the picture is NAME_night.png). --out DIR writes the pictures there instead
(relative to the repository).
"""
import argparse, math, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ST = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ST, '../../..'))
B = os.environ.get('B', 'build')
WORLD = os.path.join(ROOT, B, 'worlds', 'carts', 'garden', 'shrinetown')
OUT = os.path.join(ST, 'screenshots')
TMP = os.path.join(ROOT, B, 'shrinetown_shots')
os.makedirs(TMP, exist_ok=True)
VIEWS = {
    # name: (eye x, y, z, yaw deg (0 north, 90 east), pitch deg)
    'spawn': (160, 1.6, 20, 0, 3),
    'shotengai': (160, 1.6, 66, 0, 2),
    'courtyard': (160, 2.2, 128, 0, 4),
    'from_pagoda': (181.5, 46.5, 262, 195, -14),
    'from_stage': (168, 62.5, 341, 200, -12),
    'overview_north': (150, 150, 200, 10, -32),     # from over the precinct (row 3: the far ring of 3 reaches every row)
    'overview_south': (150, 150, 200, 180, -32),
    # the five zones with the art applied (art/ground/GROUND.md, art/water, art/backdrop)
    'art_station': (160, 3.2, 20, 20, -6),          # the plaza, the station, the shotengai's mouth
    'art_street': (160, 3.0, 96, 0, -8),            # the shotengai's north end, the crossing, the torii
    'art_road': (130, 3.4, 111, 90, -6),            # along the front road, east
    'art_east': (250, 6.0, 60, 200, -14),           # the sports ground, the pool, the neighbours
    'art_canal': (56, 3.0, 40, 340, -10),           # the canal's walls and water, the machiya
    'art_shrine': (160, 2.6, 132, 0, 2),            # the sando and the courtyard
    'art_cemetery': (270, 8.0, 150, 30, -12),       # the cemetery's terraces
    'art_pond': (222, 4.0, 150, 60, -14),           # the ponds
    'art_woods': (100, 4.0, 150, 340, -8),          # the woods' floor, the trail
    'art_from_pagoda': (181.5, 46.5, 262, 195, -14),
    'art_neighbours': (84, 20.3, 26, 225, -4),      # the neighbours' backs from the danchi's roof
    # the far views (DESIGN.md 12.7): the far levels, the stand-ins and the haze
    'wall_north': (180, 19, 160, 0, -4),            # the shrine courtyard wall, looking north
    'plaza_north': (160, 1.6, 26, 0, 3),            # the station plaza (V5), looking north
    'canal_north': (48, 6, 170, 0, -4),             # over the canal by the watermill, looking north
    'pagoda_north': (181.5, 46.5, 262, 20, -12),    # from the pagoda, toward the mountain
}


def shot(name, x, y, z, yaw, pitch, night=False, out=OUT):
    v = 1 if night else 0
    if night:
        name += '_night'
    # the region's fog for the variant, as the cart sets it, when the world declares fog
    fog = 'fn world_shrinetown_fog' in open(os.path.join(WORLD, 'shrinetown.akr')).read()
    fog_call = f'world_shrinetown_fog(k, {v})' if fog else ''
    src = f'''cart "Shrine town shot"
import "depth.akr"
import "wpbackdrop.akr"
import "shrinetown.akr"
var sky = false
fn init() {{
    render_depth(true)
    render_perspective(true)
    assert(world_shrinetown_load())
    let c = wp_cell_at(vec3({x:.3f}, {y:.3f}, {z:.3f}))     // the camera's region, as the game enters it
    var k = 0
    if c != null {{ k = c.region as s32 }}
    for r in 0..wp_region_count() {{ wp_variant_load(r, {v}) }}     // stand-ins of the other region too
    wp_region_enter(k, {v})
    sky = wp_backdrop_show(k)
    if sky {{ wp_backdrop_variant({v}, {v}, 0.0) }}
    {fog_call}
}}
fn update() {{}}
fn draw() {{
    let yaw: fixed = {math.radians(yaw):.5f}
    let pitch: fixed = {math.radians(pitch):.5f}
    if sky {{ wp_backdrop_draw(yaw, pitch) }} else {{ cls(rgb(150, 185, 220)) }}
    wp_draw(vec3({x:.3f}, {y:.3f}, {z:.3f}), yaw, pitch)
    wp_draw_entities()
}}
'''
    cart = os.path.join(TMP, f'shot_{name}.akr')
    open(cart, 'w').write(src)
    mei = os.path.join(TMP, f'shot_{name}.mei'); ppm = os.path.join(TMP, f'{name}.ppm')
    subprocess.run([os.path.join(ROOT, B, 'meic'), '-I', WORLD, cart, '-o', mei], check=True)
    subprocess.run([os.path.join(ROOT, B, 'mei-headless'), mei, '--frames', '4', '--dump', ppm], check=True,
                   stdout=subprocess.DEVNULL)
    os.makedirs(out, exist_ok=True)
    png = os.path.join(out, f'{name}.png')
    subprocess.run(['sips', '-s', 'format', 'png', ppm, '--out', png], check=True, stdout=subprocess.DEVNULL)
    print('wrote', os.path.relpath(png, ROOT))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('names', nargs='*')
    ap.add_argument('--at', nargs=6, metavar=('X', 'Y', 'Z', 'YAW', 'PITCH', 'NAME'))
    ap.add_argument('--night', action='store_true', help='palette variant 1 (NAME_night.png)')
    ap.add_argument('--out', default=None, help='folder for the pictures (default screenshots/)')
    a = ap.parse_args()
    out = os.path.join(ROOT, a.out) if a.out else OUT
    if a.at:
        x, y, z, yaw, pitch = map(float, a.at[:5])
        shot(a.at[5], x, y, z, yaw, pitch, a.night, out)
    else:
        for name in a.names or list(VIEWS):
            shot(name, *VIEWS[name], a.night, out)
