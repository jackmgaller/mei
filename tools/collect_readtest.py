#!/usr/bin/env python3
"""The collectible read test: how an Asset Kit model reads in the game's real scenes.

    python3 tools/collect_readtest.py RECIPE... -o OUTDIR [--build-dir build-rt]

For each recipe: packs the asset on its own (texture slot 0, palettes from 40, clear of both
worlds' VRAM), writes a cart that draws it into the movement garden's worlds (the shrine and
the city block, as make builds them into BUILD/cart-worlds/garden) with the real reader in depth
mode, runs it headless and makes a contact sheet: a row per scene, a column per distance and
spin, each cell a native 320 x 240 frame (upscaled by --upscale, nearest neighbour).

Writes OUTDIR/NAME.png (the sheet) and OUTDIR/NAME/ (the pack, the cart, the cells as
cells/SCENE_DIST_SPIN.png). The collectible floats with its bounding box's centre --float metres
over the floor (in the sky scene, along a line 35 degrees up from the eye) and keeps its own
colours in every light (the world's palette variants do not touch it).

Needs Pillow; make builds the worlds (NumPy) unless --no-make.
"""
import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT/'tools'/'collect_readtest'

GARDEN, SHRINE = 0, 1
DAY, DUSK, NIGHT = 0, 1, 2

# The scenes: world, light, the eye (x, z, the height to look for its floor from), the direction
# looked along (x, z), the eye's height over its floor and, for the sky, the elevation in degrees
# of the line the collectible is put on. Coordinates in metres: carts/garden/shrine/README.md and
# carts/garden/layout.png have the maps.
SCENES = [
    {'name': 'forest', 'label': 'shrine forest (west trail, ginkgo and cedars)', 'world': SHRINE,
     'light': DAY, 'eye': (22.0, 70.0), 'from': 14.0, 'dir': (-0.3, 1.0), 'eye_h': 1.8},
    {'name': 'street', 'label': 'town street (garden block)', 'world': GARDEN, 'light': DAY,
     'eye': (63.0, 18.0), 'from': 3.0, 'dir': (0.0, 1.0), 'eye_h': 1.8},
    {'name': 'sky', 'label': 'open sky, looking up', 'world': SHRINE, 'light': DAY,
     'eye': (90.0, 40.0), 'from': 3.0, 'dir': (0.3, 1.0), 'eye_h': 1.6, 'elev': 35.0},
    {'name': 'precinct', 'label': 'shrine precinct (approach)', 'world': SHRINE, 'light': DAY,
     'eye': (96.0, 36.0), 'from': 3.0, 'dir': (0.0, 1.0), 'eye_h': 1.8},
    {'name': 'dusk', 'label': 'dusk, road to the torii', 'world': SHRINE, 'light': DUSK,
     'eye': (102.0, 6.0), 'from': 3.0, 'dir': (-0.2, 1.0), 'eye_h': 1.8},
    {'name': 'night', 'label': 'night, precinct', 'world': SHRINE, 'light': NIGHT,
     'eye': (96.0, 36.0), 'from': 3.0, 'dir': (0.0, 1.0), 'eye_h': 1.8},
]

HOLD = 6          # ticks a shot (readtest.akr's HOLD)


def fx(v):
    return f'{v:.4f}'


def v3(x, y, z):
    return f'vec3({fx(x)}, {fx(y)}, {fx(z)})'


def shots(scenes, dists, spins, float_h, look_dist):
    """The shots, scene by scene, distance by distance, spin by spin, and readtest.akr's lines."""
    out = []
    for sc in scenes:
        ex, ez = sc['eye']
        dx, dz = sc['dir']
        n = math.hypot(dx, dz)
        dx, dz = dx / n, dz / n
        elev = sc.get('elev')
        for d in dists:
            for spin in spins:
                if elev is None:
                    # on the ground ahead; the camera looks at where the collectible is at
                    # look_dist, so a row's background is the same in every cell
                    ox, oz = ex + dx * d, ez + dz * d
                    look = (ex + dx * look_dist, float_h, ez + dz * look_dist)
                    obj_h, rel = float_h, 0
                else:
                    e = math.radians(elev)
                    h = d * math.cos(e)
                    ox, oz = ex + dx * h, ez + dz * h
                    look = (ex + dx * 10, sc['eye_h'] + 10 * math.tan(e), ez + dz * 10)
                    obj_h, rel = sc['eye_h'] + d * math.sin(e), 1
                out.append({
                    'scene': sc, 'dist': d, 'spin': spin,
                    'akr': ('    Shot { world: %d, light: %d, eye: %s, eye_h: %s, look: %s, obj: %s, '
                            'obj_h: %s, obj_rel: %d, spin: %s },'
                            % (sc['world'], sc['light'], v3(ex, sc['from'], ez), fx(sc['eye_h']),
                               v3(*look), v3(ox, sc['from'], oz),
                               fx(obj_h), rel, fx(math.radians(spin)))),
                })
    return out


def run(cmd, **kw):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit(f'failed: {" ".join(str(c) for c in cmd)}')
    return r.stdout


def label_font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def sheet(name, cells, scenes, dists, spins, up, path):
    """Rows: scenes; columns: distance x spin. cells[(scene, dist, spin)] = PIL image."""
    from PIL import Image, ImageDraw
    cw, ch = 320 * up, 240 * up
    pad = 4
    f_big, f = label_font(10 + 4 * up), label_font(8 + 3 * up)
    head, row_label = 18 + 6 * up, 12 + 5 * up
    cols = [(d, s) for d in dists for s in spins]
    W = len(cols) * (cw + pad) + pad
    top = head + row_label
    H = top + len(scenes) * (row_label + ch + pad) + pad
    im = Image.new('RGB', (W, H), (24, 24, 28))
    dr = ImageDraw.Draw(im)
    dr.text((pad, 4), f'{name}: rows are scenes; columns are distance from the camera and spin '
            f'(0 = front to the camera)', fill=(235, 235, 235), font=f_big)
    for i, (d, s) in enumerate(cols):
        dr.text((pad + i * (cw + pad), head), f'{d:g} m, spin {s:g}\u00b0',
                fill=(170, 200, 255), font=f)
    y = top
    for sc in scenes:
        dr.text((pad, y), sc['label'], fill=(255, 220, 140), font=f)
        y += row_label
        for i, key in enumerate(cols):
            c = cells[(sc['name'], key[0], key[1])]
            im.paste(c.resize((cw, ch), Image.NEAREST), (pad + i * (cw + pad), y))
        y += ch + pad
    im.save(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('recipes', nargs='+', help='Asset Kit recipes (*.asset.json)')
    ap.add_argument('-o', '--out', required=True, help='output directory')
    ap.add_argument('--build-dir', default='build', help='make build directory (default build)')
    ap.add_argument('--no-make', action='store_true', help='do not run make for the tools and worlds')
    ap.add_argument('--dist', default='2,8,20', help='distances in metres (default 2,8,20)')
    ap.add_argument('--spin', default='0,60', help='spins in degrees (default 0,60)')
    ap.add_argument('--scenes', default=','.join(s['name'] for s in SCENES),
                    help='scenes, in order (default all: %(default)s)')
    ap.add_argument('--float', type=float, default=1.3,
                    help="the collectible's centre over the floor, metres (default 1.3)")
    ap.add_argument('--upscale', type=int, default=2, help='sheet scale, nearest neighbour (default 2)')
    ap.add_argument('--slots', default='0', help="texture slots for the asset's pack (default 0)")
    a = ap.parse_args(argv)
    t_start = time.time()
    B = Path(a.build_dir)
    if not B.is_absolute():
        B = ROOT/B
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    dists = [float(x) for x in a.dist.split(',')]
    spins = [float(x) for x in a.spin.split(',')]
    by_name = {s['name']: s for s in SCENES}
    scenes = [by_name[n] for n in a.scenes.split(',')]
    worlds = B/'cart-worlds'/'garden'
    if not a.no_make:
        print('make: tools and the garden worlds (the first time builds the worlds: minutes)')
        # make, run from the repository, wants paths without spaces: relative ones
        try:
            mb = B.relative_to(ROOT)
        except ValueError:
            mb = B
        run(['make', f'B={mb}', str(mb/'meic'), str(mb/'mei-headless'),
             str(mb/'cart-worlds'/'garden'/'worlds.json')])
    meic, headless = B/'meic', B/'mei-headless'
    sh = shots(scenes, dists, spins, a.float, 8.0)
    for recipe in a.recipes:
        recipe = Path(recipe).resolve()
        t0 = time.time()
        info = json.loads(run([sys.executable, 'tools/mei_assets.py', 'inspect', str(recipe)]))
        name = info['name']
        lo, hi = info['bounds']['min'], info['bounds']['max']
        centre = [(lo[i] + hi[i]) / 2 for i in range(3)]
        d = out/name
        if d.exists():
            shutil.rmtree(d)
        (d/'cells').mkdir(parents=True)
        run([sys.executable, 'tools/mei_assets.py', 'pack', str(recipe), '-o', str(d/'pack'),
             '--name', 'rtpack', '--slots', a.slots, '--palette', '40', '--palette8', '14'])
        cart = d/'pack'/'readtest_cart.akr'
        cart.write_text(
            f'cart "Read Test {name}"\n'
            f'// Generated by tools/collect_readtest.py for {recipe.name} - do not edit.\n'
            'import "rtpack.akr"\nimport "readtest.akr"\n'
            f'const OBJ_CENTRE: vec3 = {v3(*centre)}\n'
            f'fn obj_mesh() -> *Mesh {{ return ASSET_{name.upper()} }}\n'
            'fn obj_load() { rtpack_load() }\n'
            f'const N_SHOTS = {len(sh)}\n'
            f'const SHOTS: [{len(sh)}]Shot = [\n' + '\n'.join(s['akr'] for s in sh) + '\n]\n')
        mei = d/'readtest.mei'
        run([str(meic), '-I', str(HERE), '-I', str(worlds), str(cart), '-o', str(mei)])
        log = run([str(headless), str(mei), '--frames', str(len(sh) * HOLD),
                   '--dump-every', str(HOLD), str(d/'f'), '--dump-from', str(HOLD - 1)])
        (d/'run.log').write_text(log)
        for line in log.splitlines():
            if line.startswith('NOTE'):
                print(f'{name}: warning: {line[5:]} (a scene\'s "from" is below the ground there)')
        from PIL import Image
        cells = {}
        for k, s in enumerate(sh):
            p = d/f'f_{k * HOLD + HOLD - 1:05d}.ppm'
            im = Image.open(p).convert('RGB')
            im.load()
            key = (s['scene']['name'], s['dist'], s['spin'])
            cells[key] = im
            im.save(d/'cells'/f'{key[0]}_{key[1]:g}m_{key[2]:g}deg.png')
            p.unlink()
        sheet(name, cells, scenes, dists, spins, a.upscale, out/f'{name}.png')
        print(f'{name}: {len(sh)} shots in {time.time() - t0:.1f} s -> {out/name}.png')
    print(f'done in {time.time() - t_start:.1f} s')


if __name__ == '__main__':
    main()
