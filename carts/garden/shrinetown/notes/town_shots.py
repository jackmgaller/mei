#!/usr/bin/env python3
"""Pictures of the town grey box, drawn headless by the real reader (world and coins, no player).

Build the test world first (B is the build directory, default build):
  python3 tools/mei_world.py build carts/garden/shrinetown/test_town.world.json -o $B/worlds/town_gb
  B=$B python3 carts/garden/shrinetown/notes/town_shots.py [NAME ...]
Writes carts/garden/shrinetown/screenshots/town_NAME.png (needs sips, macOS).
"""
import math, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '../../../..'))
B = os.environ.get('B', 'build')
WORLD = os.path.join(ROOT, B, 'worlds', 'town_gb')
OUT = os.path.join(HERE, '..', 'screenshots')
TMP = os.path.join(ROOT, B, 'town_shots')
os.makedirs(TMP, exist_ok=True)
VIEWS = {
    # name: (eye x, y, z, yaw deg (0 north, 90 east), pitch deg)
    'spawn': (160, 1.6, 22, 0, 4),
    'shotengai': (160, 1.6, 66, 0, 2),
    'roof': (173, 8.2, 48, -15, -8),
    'viaduct': (118, 17, 36, 125, -18),
    'alleys': (96, 21, 30, 40, -22),
    'overview': (40, 60, -20, 50, -32),
    'canal': (56, 1.6, 30, -10, -2),
}
for name in sys.argv[1:] or list(VIEWS):
    x, y, z, yaw, pitch = VIEWS[name]
    src = f'''cart "Town shot"
import "depth.akr"
import "town_gb.akr"
fn init() {{
    render_depth(true)
    render_perspective(true)
    assert(world_town_gb_load())
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
    mei = os.path.join(TMP, f'shot_{name}.mei'); ppm = os.path.join(TMP, f'town_{name}.ppm')
    subprocess.run([os.path.join(ROOT, B, 'meic'), '-I', WORLD, cart, '-o', mei], check=True)
    subprocess.run([os.path.join(ROOT, B, 'mei-headless'), mei, '--frames', '4', '--dump', ppm], check=True,
                   stdout=subprocess.DEVNULL)
    png = os.path.join(OUT, f'town_{name}.png')
    subprocess.run(['sips', '-s', 'format', 'png', ppm, '--out', png], check=True, stdout=subprocess.DEVNULL)
    print('wrote', os.path.relpath(png, ROOT))
