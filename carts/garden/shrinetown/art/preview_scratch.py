#!/usr/bin/env python3
"""Builds a scratch copy of the shrine town's world with the water and the backdrops applied
(apply_patch.py), or without (--none, the "before"), and draws it with the real reader, day and
night, as the garden cart does (backdrop shown, no cls()).

    make B=build-ws build-ws/meic build-ws/mei-headless build-ws/mei-asset-probe build-ws/mei-scene-probe
    B=build-ws python3 carts/garden/shrinetown/art/preview_scratch.py --tag after --water --backdrop
    B=build-ws python3 carts/garden/shrinetown/art/preview_scratch.py --tag before --none
    ... --shots-only          draw again without building
    ... --views a,b,c         only these views (art/views.json)
    ... --frames N            frames to run before the picture (the water cycles with the frame)

Output: $B/water_skyline/TAG/ (world/, report.json, shots/NAME_day.png, NAME_night.png).
The world is the repository's with its folders symlinked, so nothing in the checkout changes.
Needs NumPy; the World Checker is skipped (the full build is `make`'s); macOS sips for the PNGs.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE.parent                              # carts/garden/shrinetown
ROOT = ST.parents[2]
B = os.environ.get('B', 'build')
sys.path.insert(0, str(HERE))
from apply_patch import patch_water, patch_backdrop     # noqa: E402

VIEWS = json.loads((HERE / 'views.json').read_text())


def scratch(tag, water, backdrop):
    out = ROOT / B / 'water_skyline' / tag
    src = out / 'src' / 'carts' / 'garden'
    if (out / 'src').exists():
        shutil.rmtree(out / 'src')
    (src / 'shrinetown').mkdir(parents=True)
    for p in ST.iterdir():
        if p.name != 'shrinetown.world.json':
            os.symlink(p, src / 'shrinetown' / p.name)
    os.symlink(ST.parent / 'world', src / 'world')
    os.symlink(ST.parent / 'shrine', src / 'shrine')
    w = json.loads((ST / 'shrinetown.world.json').read_text())
    if water:
        w = patch_water(w)
    if backdrop:
        w = patch_backdrop(w)
    (src / 'shrinetown' / 'shrinetown.world.json').write_text(json.dumps(w, indent=1))
    return out, src / 'shrinetown' / 'shrinetown.world.json'


def build(tag, water, backdrop):
    out, recipe = scratch(tag, water, backdrop)
    cmd = [sys.executable, str(ROOT / 'tools/mei_world.py'), 'build', str(recipe), '-o', str(out / 'world'),
           '--world-checker', 'skip', '--compiler', str(ROOT / B / 'meic'), '--runner', str(ROOT / B / 'mei-headless'),
           '--probe', str(ROOT / B / 'mei-asset-probe')]
    r = subprocess.run(cmd, capture_output=True, text=True)
    res = json.loads(r.stdout) if r.stdout.strip().startswith('{') else {'ok': False, 'out': r.stdout + r.stderr}
    if not res.get('ok', r.returncode == 0):
        print(json.dumps(res, indent=1)[:6000])
        sys.exit(1)
    rep = json.loads((out / 'world' / 'report.json').read_text())
    for name, reg in rep['regions'].items():
        t = reg.get('textures', {})
        print(f"region {name}: {t.get('vram_bytes_allocated')} bytes allocated, {t.get('tiles')} tiles")
        bd = reg.get('backdrop', {}).get('silhouette')
        if bd:
            print('   backdrop', json.dumps(bd))
    for m, v in rep.get('terrain', {}).get('textures', {}).items():
        print(f"  {m:12} span {v['span']:3} stored {v['stored']} windowed {v.get('windowed')} stretched {v.get('stretched')} "
              f"far {v.get('far')} tri {v.get('triangles')}")
    for wn in rep.get('warnings', [])[:20]:
        print('  warning', wn if isinstance(wn, str) else json.dumps(wn)[:200])
    return out


def shots(out, names, frames, cycle, shotdir='shots'):
    tmp = out / shotdir
    tmp.mkdir(exist_ok=True)
    for name in names:
        eye, yaw, pitch = VIEWS[name]['eye'], VIEWS[name]['yaw'], VIEWS[name]['pitch']
        region = VIEWS[name]['region']
        for v, vname in ((0, 'day'), (1, 'night')):
            # the garden's way (ground.akr, world_water_find()): each region's palettes found once
            # in its day colours, then the region entered
            cyc_find = ('''    for k in 0..min(wp_region_count(), WATER_MAX_REGIONS) {
        let r = wp_region(k)
        water_cycle_find(k, (__wp_base + r.palette_off + 4 * (r.variant_count as u32)) as *u16,
                         r.first_colour as s32, r.colour_count as s32)
    }''' if cycle else '')
            cyc_enter = (f'    water_cycle_enter({region})' if cycle else '')
            cyc_sync = '    water_cycle_sync()' if cycle else ''
            src = f'''cart "Water and skyline shot"
import "depth.akr"
import "wpbackdrop.akr"
import "shrinetown.akr"
{'import "water_cycle.akr"' if cycle else ''}
fn init() {{
    render_depth(true)
    render_perspective(true)
    assert(world_shrinetown_load())
{cyc_find}
    wp_region_enter({region}, 0)
{cyc_enter}
    if {v} != 0 {{ wp_region_enter({region}, {v}) }}
    wp_backdrop_show({region})
    wp_backdrop_variant({v}, {v}, 0.0)
{cyc_sync if v else ''}
}}
fn update() {{ {'water_cycle_update(frame() as s32)' if cycle else ''} }}
fn draw() {{
    wp_backdrop_draw({math.radians(yaw):.5f}, {math.radians(pitch):.5f})
    wp_draw(vec3({eye[0]:.3f}, {eye[1]:.3f}, {eye[2]:.3f}), {math.radians(yaw):.5f}, {math.radians(pitch):.5f})
}}
'''
            cart = tmp / f'{name}_{vname}.akr'
            cart.write_text(src)
            mei, ppm = tmp / f'{name}_{vname}.mei', tmp / f'{name}_{vname}.ppm'
            subprocess.run([str(ROOT / B / 'meic'), '-I', str(out / 'world'), '-I', str(HERE / 'water'), str(cart), '-o', str(mei)], check=True)
            subprocess.run([str(ROOT / B / 'mei-headless'), str(mei), '--frames', str(frames), '--dump', str(ppm)],
                           check=True, stdout=subprocess.DEVNULL)
            subprocess.run(['sips', '-s', 'format', 'png', str(ppm), '--out', str(tmp / f'{name}_{vname}.png')],
                           check=True, stdout=subprocess.DEVNULL)
            ppm.unlink()
    print('wrote', tmp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', default='after')
    ap.add_argument('--water', action='store_true')
    ap.add_argument('--backdrop', action='store_true')
    ap.add_argument('--none', action='store_true')
    ap.add_argument('--shots-only', action='store_true')
    ap.add_argument('--no-shots', action='store_true')
    ap.add_argument('--views')
    ap.add_argument('--frames', type=int, default=4)
    ap.add_argument('--shotdir', default='shots')
    ap.add_argument('--cycle', action='store_true', help='the water cycles (water_cycle.akr)')
    a = ap.parse_args()
    out = ROOT / B / 'water_skyline' / a.tag
    if not a.shots_only:
        out = build(a.tag, a.water, a.backdrop)
    if not a.no_shots:
        shots(out, a.views.split(',') if a.views else list(VIEWS), a.frames, a.cycle, a.shotdir)


if __name__ == '__main__':
    main()
