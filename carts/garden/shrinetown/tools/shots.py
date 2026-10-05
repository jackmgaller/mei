#!/usr/bin/env python3
"""Pictures of the shrine town's grey box, drawn headless by the real reader (world and coins, no
player), into carts/garden/shrinetown/screenshots/NAME.png (needs sips, macOS).

Build the world first (make builds it with the garden cart; B is the build directory):
    make B=$B $B/carts/garden.mei
    B=$B python3 carts/garden/shrinetown/tools/shots.py [NAME ...]
    B=$B python3 carts/garden/shrinetown/tools/shots.py --at X Y Z YAW PITCH NAME   # any view
YAW in degrees, 0 north (+z), 90 east; PITCH in degrees, negative looks down.
"""
import math, os, subprocess, sys
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
}


def shot(name, x, y, z, yaw, pitch):
    src = f'''cart "Shrine town shot"
import "depth.akr"
import "shrinetown.akr"
fn init() {{
    render_depth(true)
    render_perspective(true)
    assert(world_shrinetown_load())
    let c = wp_cell_at(vec3({x:.3f}, {y:.3f}, {z:.3f}))     // the camera's region, as the game enters it
    if c != null {{ wp_region_enter(c.region as s32, 0) }}
}}
fn update() {{}}
fn draw() {{
    let yaw: fixed = {math.radians(yaw):.5f}
    let pitch: fixed = {math.radians(pitch):.5f}
    cls(rgb(150, 185, 220))
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
    png = os.path.join(OUT, f'{name}.png')
    subprocess.run(['sips', '-s', 'format', 'png', ppm, '--out', png], check=True, stdout=subprocess.DEVNULL)
    print('wrote', os.path.relpath(png, ROOT))


if __name__ == '__main__':
    if sys.argv[1:2] == ['--at']:
        x, y, z, yaw, pitch = map(float, sys.argv[2:7])
        shot(sys.argv[7], x, y, z, yaw, pitch)
    else:
        for name in sys.argv[1:] or list(VIEWS):
            shot(name, *VIEWS[name])
