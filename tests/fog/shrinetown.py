#!/usr/bin/env python3
"""Fog toward a colour (a proposal: docs/DECISIONS.md, "Proposal: fog toward a colour") measured on
the shrine town: each view drawn by the real reader (world, entities, the backdrop) with the fog
off and on, in depth mode as the garden draws it, headless. Writes OUT/NAME.png (the view without
fog on the left, with fog on the right, at twice the size), OUT/NAME_off.png and OUT/NAME_on.png,
and prints a table of each view's triangles, CPU and GPU cycles both ways (Markdown, also
OUT/table.md). Needs Pillow; the garden cart's worlds built into B first:

    make B=$B $B/carts/garden.mei
    B=$B python3 tests/fog/shrinetown.py [-o OUT] [--day COLOUR,NEAR,FAR] [--night COLOUR,NEAR,FAR] [NAME ...]

OUT defaults to $B/fog_shots. NAME picks views: the shots below, or "views" for the World
Checker's worst views (carts/garden/shrinetown/tools/views.py), day only.
"""
import argparse, csv, math, os, subprocess, sys
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
B = os.environ.get('B', 'build')
WORLD = os.path.join(ROOT, B, 'worlds', 'carts', 'garden', 'shrinetown')

DAY, NIGHT = 0, 1          # the regions' palette variants (shrinetown.world.json: day, night)
# name: (eye x, y, z, yaw degrees (0 north, 90 east), pitch degrees, variant)
SHOTS = {
    'courtyard_wall_north': (180, 19, 160, 0, -2, DAY),
    'courtyard_pagoda': (160, 2.2, 128, 10, 6, DAY),
    'from_pagoda': (181.5, 46.5, 262, 195, -14, DAY),
    'from_stage': (168, 62.5, 341, 200, -12, DAY),
    'station_plaza_north': (160, 1.6, 20, 0, 3, DAY),
    'night_from_stage': (168, 62.5, 341, 200, -12, NIGHT),
    'night_station_plaza_north': (160, 1.6, 20, 0, 3, NIGHT),
}
# carts/garden/shrinetown/tools/views.py's views (the World Checker's worst), by number
VIEWS = [
    ((160, 10.0, 94), 180, -8), ((178, 47.0, 262), 180, -12), ((178, 47.0, 262), 225, -12),
    ((178, 47.0, 262), 135, -12), ((178, 52.0, 262), 180, -12), ((154, 62.0, 345), 180, -10),
    ((154, 62.0, 345), 225, -10), ((154, 62.0, 345), 135, -10), ((78, 20.3, 30), 45, -10),
    ((160, 1.6, 26), 0, 0), ((160, 1.6, 26), 0, 5), ((286, 18.0, 244), 270, -10),
    ((160, 1.5, 50), 0, 0), ((160, 10.5, 8), 0, -5), ((102, 16.7, 74), 90, -15),
    ((193, 19.8, 90), 270, -15), ((160, 2.1, 130), 0, 0), ((160, 29.5, 221), 180, -10),
    ((80, 16.6, 206), 90, -5), ((100, 33.0, 325), 0, 0), ((300, 65.0, 372), 225, -12),
]


def fog_arg(text):
    colour, near, far = text.split(',')
    return colour, float(near), float(far)


def cart_source(x, y, z, yaw, pitch, variant, fog):
    fog_call = ''
    if fog:
        c, near, far = fog
        r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
        fog_call = f'gpu_fog(rgb({r}, {g}, {b}), {near:.3f}, {far:.3f})'
    return f'''cart "Shrine town fog"
import "depth.akr"
import "shrinetown.akr"
fn init() {{
    render_depth(true)
    render_perspective(true)
    assert(world_shrinetown_load())
    for k in 0..wp_pack.region_count as s32 {{ wp_variant_load(k, {variant}) }}
    let c = wp_cell_at(vec3({x:.3f}, {y:.3f}, {z:.3f}))     // the camera's region, as the game enters it
    var k = 0
    if c != null {{ k = c.region as s32 }}
    wp_region_enter(k, {variant})
    wp_backdrop_show(k)
    wp_backdrop_variant({variant}, {variant}, 0.0)
    {fog_call}
}}
fn update() {{}}
fn draw() {{
    let yaw: fixed = {math.radians(yaw):.5f}
    let pitch: fixed = {math.radians(pitch):.5f}
    wp_backdrop_draw(yaw, pitch)
    wp_draw(vec3({x:.3f}, {y:.3f}, {z:.3f}), yaw, pitch)
    wp_draw_entities()
}}
'''


def render(name, view, fog, tmp):
    src = os.path.join(tmp, f'{name}.akr')
    mei, ppm, stats = (os.path.join(tmp, f'{name}{ext}') for ext in ('.mei', '.ppm', '.csv'))
    open(src, 'w').write(cart_source(*view, fog))
    subprocess.run([os.path.join(ROOT, B, 'meic'), '-I', WORLD, src, '-o', mei], check=True)
    subprocess.run([os.path.join(ROOT, B, 'mei-headless'), mei, '--frames', '4', '--dump', ppm, '--gpu-stats', stats],
                   check=True, stdout=subprocess.DEVNULL)
    row = list(csv.DictReader(open(stats)))[-1]
    return Image.open(ppm).convert('RGB'), {k: int(row.get(k) or 0) for k in
                                            ('tris', 'cpu_cycles', 'gpu_cycles', 'tris_fog', 'px_fog')}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('names', nargs='*')
    ap.add_argument('-o', '--out', default=os.path.join(ROOT, B, 'fog_shots'))
    ap.add_argument('--day', type=fog_arg, default=('#c8c8b4', 40, 220), help='COLOUR,NEAR,FAR (default %(default)s)')
    ap.add_argument('--night', type=fog_arg, default=('#141826', 16, 140), help='COLOUR,NEAR,FAR (default %(default)s)')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    tmp = os.path.join(a.out, 'work')
    os.makedirs(tmp, exist_ok=True)
    jobs = []
    for name in a.names or list(SHOTS):
        if name == 'views':
            jobs += [(f'view{k + 1:02d}', (*eye, yaw, pitch, DAY), True) for k, (eye, yaw, pitch) in enumerate(VIEWS)]
        else:
            jobs.append((name, SHOTS[name], False))
    lines = [f'Fog: day {a.day[0]} from {a.day[1]:g} to {a.day[2]:g} units, night {a.night[0]} from {a.night[1]:g} '
             f'to {a.night[2]:g}.', '',
             '| View | Triangles | CPU off | CPU on | GPU off | GPU on | GPU + | Fogged triangles | Fogged pixels |',
             '|---|---|---|---|---|---|---|---|---|']
    for name, view, quiet in jobs:
        fog = a.night if view[5] == NIGHT else a.day
        off, s0 = render(name + '_off', view, None, tmp)
        on, s1 = render(name + '_on', view, fog, tmp)
        if not quiet:
            off.save(os.path.join(a.out, f'{name}_off.png'))
            on.save(os.path.join(a.out, f'{name}_on.png'))
            pair = Image.new('RGB', (644, 240), (255, 255, 255))
            pair.paste(off, (0, 0))
            pair.paste(on, (324, 0))
            pair.resize((1288, 480), Image.NEAREST).save(os.path.join(a.out, f'{name}.png'))
        lines.append(f"| {name} | {s0['tris']:,} | {s0['cpu_cycles']:,} | {s1['cpu_cycles']:,} | {s0['gpu_cycles']:,} | "
                     f"{s1['gpu_cycles']:,} | {s1['gpu_cycles'] - s0['gpu_cycles']:,} | {s1['tris_fog']:,} | {s1['px_fog']:,} |")
        print(lines[-1], flush=True)
    open(os.path.join(a.out, 'table.md'), 'w').write('\n'.join(lines) + '\n')
    print('wrote', os.path.relpath(a.out, ROOT))


if __name__ == '__main__':
    sys.exit(main())
