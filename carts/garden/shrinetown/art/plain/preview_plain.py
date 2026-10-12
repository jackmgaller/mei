#!/usr/bin/env python3
"""Draws the shrine town from its high points with and without the far plain (plain.akr), day and
night, with the real reader as the garden cart draws it (backdrop shown, region fog set, no
cls()), and prints what the plain costs the CPU.

    make B=$B $B/carts/garden.mei          # builds the world into $B/worlds/
    B=$B python3 carts/garden/shrinetown/art/plain/preview_plain.py [--out DIR] [--views a,b]
         [--world DIR] [--cap 1.0 --tail 900] [--palette 240] [--frames 4]

Output (default $B/plain_preview/): NAME_{before,after}_{day,night}.png, a sheet per view
(NAME.png: before | after, day over night) and costs.txt. --world draws another build of the
world (a scratch copy with the look's branch applied, say). Needs Pillow.
"""
import argparse
import math
import os
import subprocess
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
B = os.environ.get('B', 'build')

# name: eye x, y, z, yaw (degrees, 0 north, 90 east), pitch (degrees, negative down): the views
# the far-views review (r18) found the empty plain from
VIEWS = {
    'pagoda_s': (181.5, 46.5, 262, 195, -14),
    'pagoda_w': (181.5, 46.5, 262, 270, -8),
    'stage_s': (168, 62.5, 341, 200, -12),
    'stage_se': (168, 62.5, 341, 160, -6),
    'crown_s': (70, 28.6, 220, 180, -6),
    'crown_e': (70, 28.6, 220, 90, -6),
    'roof_w': (193, 19.8, 90, 270, -10),
    'roof_s': (193, 19.8, 90, 180, -4),
    'road_w': (160, 1.6, 116, 270, 2),      # at street level, down the front road west
}


def cart(x, y, z, yaw, pitch, night, plain, a):
    v = 1 if night else 0
    plain_import = 'import "plain.akr"' if plain else ''
    plain_init = (f'plain_palette = {a.palette}\n    plain_cap = {a.cap}\n    plain_tail = {a.tail}\n'
                  f'    plain_show()\n    plain_variant({v})') if plain else ''
    plain_draw = 'plain_draw(eye, pitch)' if plain else ''
    plain_print = 'print_int(plain_cycles)' if plain else 'print_int(0)'
    return f'''cart "Shrine town plain preview"
import "depth.akr"
import "wpbackdrop.akr"
import "shrinetown.akr"
{plain_import}
var sky = false
var n = 0
fn init() {{
    render_depth(true)
    render_perspective(true)
    assert(world_shrinetown_load())
    let c = wp_cell_at(vec3({x:.3f}, {y:.3f}, {z:.3f}))
    var k = 0
    if c != null {{ k = c.region as s32 }}
    for r in 0..wp_region_count() {{ wp_variant_load(r, {v}) }}
    wp_region_enter(k, {v})
    sky = wp_backdrop_show(k)
    if sky {{ wp_backdrop_variant({v}, {v}, 0.0) }}
    world_shrinetown_fog(k, {v})
    {plain_init}
}}
fn update() {{}}
fn draw() {{
    let c0 = CYCLES
    let yaw: fixed = {math.radians(yaw):.5f}
    let pitch: fixed = {math.radians(pitch):.5f}
    let eye = vec3({x:.3f}, {y:.3f}, {z:.3f})
    if sky {{ wp_backdrop_draw(yaw, pitch) }} else {{ cls(rgb(150, 185, 220)) }}
    wp_draw(eye, yaw, pitch)
    {plain_draw}
    wp_draw_entities()
    n += 1
    if n == 3 {{
        print("cycles ")
        print_int(c0 - CYCLES)
        print(" plain ")
        {plain_print}
        println("")
    }}
}}
'''


def shot(name, view, night, plain, a, world, tmp, out):
    tag = f'{name}_{"after" if plain else "before"}_{"night" if night else "day"}'
    src = tmp / f'{tag}.akr'
    src.write_text(cart(*view, night, plain, a))
    mei, ppm = tmp / f'{tag}.mei', tmp / f'{tag}.ppm'
    subprocess.run([str(ROOT / B / 'meic'), '-I', str(world), '-I', str(HERE), str(src), '-o', str(mei)], check=True)
    r = subprocess.run([str(ROOT / B / 'mei-headless'), str(mei), '--frames', str(a.frames), '--dump', str(ppm)],
                       check=True, capture_output=True, text=True)
    cyc = [l for l in r.stdout.splitlines() if l.startswith('cycles')]
    png = out / f'{tag}.png'
    Image.open(ppm).save(png)
    return png, (cyc[0] if cyc else '?')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', type=Path, default=ROOT / B / 'plain_preview')
    ap.add_argument('--views', default=','.join(VIEWS))
    ap.add_argument('--world', type=Path, default=ROOT / B / 'worlds' / 'carts' / 'garden' / 'shrinetown')
    ap.add_argument('--cap', type=float, default=0.85)
    ap.add_argument('--tail', type=float, default=900.0)
    ap.add_argument('--palette', type=int, default=232)
    ap.add_argument('--frames', type=int, default=4)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    tmp = ROOT / B / 'plain_preview_tmp'
    tmp.mkdir(parents=True, exist_ok=True)
    costs = []
    for name in a.views.split(','):
        sheet = Image.new('RGB', (640, 480))
        for j, night in enumerate((False, True)):
            for i, plain in enumerate((False, True)):
                png, cyc = shot(name, VIEWS[name], night, plain, a, a.world, tmp, a.out)
                sheet.paste(Image.open(png).convert('RGB'), (320 * i, 240 * j))
                costs.append(f'{png.stem:28} {cyc}')
                print(costs[-1])
        sheet.save(a.out / f'{name}.png')
    (a.out / 'costs.txt').write_text('\n'.join(costs) + '\n')


if __name__ == '__main__':
    main()
