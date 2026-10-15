#!/usr/bin/env python3
"""Captures the aquarium sketch through Mei at three camera pitches, with its costs.

    python3 carts/dorobo/rooms/aquarium/capture.py [--build-dir build-dorobo-sketch] [--verify]

Packs the five recipes beside this script (make_aquarium.py writes them) with the Asset Kit, writes
one small Akari cart per view into BUILD_DIR/dorobo/aquarium/, compiles it with meic and runs it in
mei-headless, which dumps the frame and its CPU and GPU statistics. Each pitch is drawn:

  full     the room, the tanks, the thief, the guard and his cone, as the shots show it
  noglass  the same without the large semi-transparent panes (the three tanks' glass, the column's
           and the cube's water surfaces), so full - noglass is what the glass costs
  noblend  without anything semi-transparent at all (also the jellyfish, the light shafts, the
           cone and the blob shadows)
  loaded   full plus a third guard and the two cones drawn twice: the frame the budget is about
  thief    the thief alone on black, to measure his height on screen in pixels

45 and 75 degrees are framed alike: the floor's front edge spans the picture, the room centred.
60 degrees is the game's own camera (dr_view.akr), as the level draws the room. Writes
shots/aquarium_PITCH.png (320 x 240, as the console draws it), shots/aquarium_PITCH_x3.png
(scaled up pixel for pixel), shots/compare.png (the three side by side) and shots/numbers.json.
With --verify, runs the Asset Checker on every recipe first. Needs Pillow.
"""
import argparse
import csv
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import make_aquarium as A  # noqa: E402  (the plan's numbers: where the guard and thief stand)

RECIPES = ['aq_room', 'aq_tanks', 'standin_thief', 'standin_guard', 'sight_cone']
PITCHES = [45, 60, 75]
FOV = 20.0                    # vertical field of view, degrees: near-orthographic, a diorama's look
VOID = (6, 10, 22)            # the void around the section: the game's (dr_view.akr), drawn as (0, 8, 16)
GAME_PITCH, GAME_DIST = 60, 28.166      # dr_view.akr's camera: CAM_PITCH, CAM_DIST, CAM_FOV (20 degrees)
GAME_TARGET_Y = 0.6                     # CAM_TARGET_Y
GAME_FRONT_Z, GAME_FRONT_LINE = -3.15, 246    # frame_room(): the room's front edge on screen line 246
PANES = {'window_glass', 'surface', 'jelly_glass', 'jelly_surface', 'cube_glass'}
ROOM_W = 2 * A.XO             # 12.1 m across the outer walls


def run(args, **kw):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True, cwd=ROOT, **kw)
    if result.returncode:
        sys.exit(f'failed: {" ".join(map(str, args))}\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}')
    return result


def variant(name, recipe, drop):
    """The recipe without the nodes drawn in the given materials (searching groups too)."""
    data = json.loads(json.dumps(recipe))

    def keep(node):
        if node.get('op') == 'group':
            node['children'] = [c for c in node['children'] if keep(c)]
            return bool(node['children'])
        return node.get('material') not in drop
    data['nodes'] = [n for n in data['nodes'] if keep(n)]
    data['name'] = name
    data['verification'] = {'required': False, 'depth': True, 'perspective': True}
    return data


def blended(recipe):
    return {k for k, m in recipe['materials'].items() if 'blend' in m}


# ---- the camera: camera_look's projection (stdlib/render.akr), fitted to the room

def project(eye, pitch, f, p):
    sp, cp = math.sin(pitch), math.cos(pitch)
    d = [p[i] - eye[i] for i in range(3)]
    x = d[0]
    y = d[1] * cp - d[2] * sp
    w = d[1] * sp + d[2] * cp
    return 160 + 120 * f * x / w, 120 - 120 * f * y / w, w


def frame_points():
    pts = []
    for x in (-A.SLAB_X, A.SLAB_X):
        for z in (A.SLAB_Z, A.ZBO):
            pts += [(x, -A.SLAB, z), (x, 0, z), (x, A.H, z)]
    return pts       # the tank behind the back wall is under its lid, the void's colour: not framed


def fit_camera(pitch_deg, f, margin=6, tight=False):
    """Eye position so that the room fills the picture: as large as fits, centred. tight: the floor's
    width fills the picture and its floor is centred; the walls' and the tank's tops may crop."""
    pitch = -math.radians(pitch_deg)
    fwd = (0.0, math.sin(pitch), math.cos(pitch))
    target = [0.0, 0.8, 0.8]
    dist = 18.0
    for _ in range(60):
        eye = [target[i] - dist * fwd[i] for i in range(3)]
        pts = [p for p in frame_points() if p[1] == 0] if tight else frame_points()
        sc = [project(eye, pitch, f, p) for p in pts]
        xs, ys = [s[0] for s in sc], [s[1] for s in sc]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        sx = (max(xs) - min(xs)) / (320 - 2 * margin)
        sy = (max(ys) - min(ys)) / (240 - 2 * margin)
        # move the target so the bounds are centred, then scale the distance to fit
        up = (0.0, math.cos(pitch), -math.sin(pitch))
        k = dist / (120 * f)
        target = [target[i] + (cx - 160) * k * (1 if i == 0 else 0) - (cy - 120) * k * up[i] for i in range(3)]
        dist *= (sx if tight else max(sx, sy)) ** 0.5
    if tight:      # centred when the room fits; else its front edge at the foot, the far top cropped
        up = (0.0, math.cos(pitch), -math.sin(pitch))
        for _ in range(20):
            eye = [target[i] - dist * fwd[i] for i in range(3)]
            ys = [project(eye, pitch, f, p)[1] for p in frame_points()]
            low = max(ys) if max(ys) - min(ys) > 240 - 2 * margin else (max(ys) + min(ys)) / 2 + 120 - margin
            target = [target[i] - (low - (240 - margin)) * dist / (120 * f) * up[i] for i in range(3)]
    eye = [target[i] - dist * fwd[i] for i in range(3)]
    return eye, pitch, dist


def thief_height_projected(eye, pitch, f):
    tx, tz = A.THIEF
    _, y0, _ = project(eye, pitch, f, (tx, 0.0, tz))
    _, y1, _ = project(eye, pitch, f, (tx, 1.7, tz))
    return y0 - y1


# ---- the carts

def cart(pack, eye, pitch, draws, near, far, fog=None):
    lines = [f'// Written by carts/dorobo/rooms/aquarium/capture.py: one view of the aquarium sketch.',
             'cart "Aquarium sketch"', f'import "{pack}.akr"', 'import "depth.akr"', '',
             f'fn init() {{ {pack}_load() }}', '', 'fn draw() {',
             f'    cls(rgb({VOID[0]}, {VOID[1]}, {VOID[2]}))',
             '    render_depth(true)', '    render_perspective(true)',
             f'    camera_fov({math.radians(FOV):.7f})',
             f'    camera_clip({near:.4f}, {far:.4f})',
             f'    camera_look(vec3({eye[0]:.5f}, {eye[1]:.5f}, {eye[2]:.5f}), 0.0, {pitch:.7f})']
    if fog:
        lines.append(f'    gpu_fog(rgb({fog[0]}, {fog[1]}, {fog[2]}), {fog[3]:.3f}, {fog[4]:.3f})')
    for mesh, (x, y, z), yaw in draws:
        lines.append(f'    mesh_at({mesh}, vec3({x:.4f}, {y:.4f}, {z:.4f}), {yaw:.5f})')
    lines.append('}')
    return '\n'.join(lines) + '\n'


def shoot(tools, directory, stem, code):
    akr = directory / f'{stem}.akr'
    akr.write_text(code)
    run([tools['meic'], akr, '-o', directory / f'{stem}.mei'])
    run([tools['run'], directory / f'{stem}.mei', '--frames', '4', '--dump', directory / f'{stem}.ppm',
         '--gpu-stats', directory / f'{stem}.csv'])
    with (directory / f'{stem}.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    stats = {k: int(v) for k, v in rows[-1].items()}
    return Image.open(directory / f'{stem}.ppm').convert('RGB'), stats


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--build-dir', default='build-dorobo-sketch')
    ap.add_argument('--verify', action='store_true', help='run the Asset Checker on every recipe first')
    ap.add_argument('--fog', action='store_true', help='also draw with GPU fog toward the void')
    args = ap.parse_args()
    build = ROOT / args.build_dir
    tools = {'meic': build / 'meic', 'run': build / 'mei-headless'}
    for t in tools.values():
        if not t.is_file():
            sys.exit(f'missing {t}: make B={args.build_dir} {args.build_dir}/meic {args.build_dir}/mei-headless '
                     f'{args.build_dir}/mei-asset-probe')
    out = build / 'dorobo' / 'aquarium'
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    kit = [sys.executable, ROOT / 'tools' / 'mei_assets.py']
    checks = {}
    if args.verify:
        for name in RECIPES:
            res = subprocess.run([str(a) for a in kit + ['verify', HERE / f'{name}.asset.json', '-o', out / f'verify_{name}',
                                                          '--build-dir', build, '--json']],
                                 capture_output=True, text=True, cwd=ROOT)
            rep = json.loads(res.stdout)
            if 'verdict' not in rep:
                sys.exit(f'verify {name}: {rep.get("errors")}')
            checks[name] = {'ok': rep['ok'], 'verdict': rep['verdict'], 'failures': rep['failures']}
            print(f'verify {name}: {rep["verdict"]}')
            for line in rep['failures']:
                print('   ', line)

    # recipes, and variants without the glass and without anything blended, beside a copy of the art
    src = out / 'recipes'
    shutil.copytree(HERE / 'art', src / 'art')
    recipes = {n: json.loads((HERE / f'{n}.asset.json').read_text()) for n in RECIPES}
    for n, data in recipes.items():
        (src / f'{n}.asset.json').write_text(json.dumps(data))
    for n in ('aq_room', 'aq_tanks'):
        (src / f'{n}_noglass.asset.json').write_text(json.dumps(variant(f'{n}_noglass', recipes[n], PANES)))
        (src / f'{n}_noblend.asset.json').write_text(
            json.dumps(variant(f'{n}_noblend', recipes[n], blended(recipes[n]))))
    for n in ('standin_thief', 'standin_guard'):
        (src / f'{n}_noblend.asset.json').write_text(
            json.dumps(variant(f'{n}_noblend', recipes[n], blended(recipes[n]))))
    names = RECIPES + ['aq_room_noglass', 'aq_tanks_noglass', 'aq_room_noblend', 'aq_tanks_noblend',
                       'standin_thief_noblend', 'standin_guard_noblend']
    run(kit + ['pack'] + [src / f'{n}.asset.json' for n in names] +
        ['-o', out / 'pack', '--name', 'aquarium', '--slots', '0-14', '--palette', '0', '--palette8', '14'])
    pack_json = json.loads((out / 'pack' / 'aquarium.pack.json').read_text())
    per_asset = {}
    for entry in pack_json.get('assets', []):
        per_asset[entry.get('name')] = entry
    for f in (out / 'pack').iterdir():
        shutil.copy(f, out / f.name)

    f = 1 / math.tan(math.radians(FOV) / 2)
    tx, tz = A.THIEF
    # the stand-ins face -Z at yaw 0; mesh_at's yaw turns +Z toward +X. Each guard looks along his
    # heading (degrees in the XZ plane from +X toward +Z).
    def yaw_of(heading_deg):
        h = math.radians(heading_deg)
        return math.atan2(-math.cos(h), -math.sin(h))
    thief_yaw = math.radians(20)

    def scene(kind):
        room = {'full': 'aq_room', 'noglass': 'aq_room_noglass', 'noblend': 'aq_room_noblend',
                'loaded': 'aq_room'}[kind]
        tanks = {'full': 'aq_tanks', 'noglass': 'aq_tanks_noglass', 'noblend': 'aq_tanks_noblend',
                 'loaded': 'aq_tanks'}[kind]
        suffix = '_NOBLEND' if kind == 'noblend' else ''
        d = [(f'ASSET_{room.upper()}', (0, 0, 0), 0.0), (f'ASSET_{tanks.upper()}', (0, 0, 0), 0.0),
             (f'ASSET_STANDIN_THIEF{suffix}', (tx, 0, tz), thief_yaw)]
        for w in A.WATCHERS:
            d.append((f'ASSET_STANDIN_GUARD{suffix}', (w['at'][0], 0, w['at'][1]), yaw_of(w['heading'])))
        if kind != 'noblend':
            d.append(('ASSET_SIGHT_CONE', (0, 0, 0), 0.0))
        if kind == 'loaded':      # a third guard, and both fans drawn a second time: four cones in all
            d.append(('ASSET_STANDIN_GUARD', (-4.6, 0, 1.4), yaw_of(-20)))
            d.append(('ASSET_SIGHT_CONE', (0.4, 0, -0.3), 0.0))
        return d

    shots = HERE / 'shots'
    shots.mkdir(exist_ok=True)
    numbers = {'fov_degrees': FOV, 'room_width_m': ROOM_W, 'views': {}, 'checks': checks,
               'assets': {n: {k: per_asset[n].get(k) for k in ('triangles', 'vertices')} for n in per_asset
                          if n in RECIPES}}
    images = []
    for pitch_deg, tight in [(p, True) for p in PITCHES]:
        tag = str(pitch_deg)
        eye, pitch, dist = fit_camera(pitch_deg, f, tight=tight)
        if pitch_deg == GAME_PITCH:    # the game's own camera (dr_view.akr), as the level draws the room
            dist = GAME_DIST
            # frame_room(): the target's z puts the room's front edge (z -3.15) on line 246
            cam_tz = GAME_FRONT_Z + 5.0
            for _ in range(12):
                eye = [0.0, GAME_TARGET_Y - dist * math.sin(pitch), cam_tz - dist * math.cos(pitch)]
                cam_tz += (GAME_FRONT_LINE - project(eye, pitch, f, (0.0, 0.0, GAME_FRONT_Z))[1]) / 21
        near, far = max(0.5, dist - 12), dist + 12
        view = {'pitch_degrees': pitch_deg, 'tight': tight, 'eye': [round(c, 3) for c in eye], 'distance': round(dist, 3),
                'px_per_m_at_target': round(120 * f / dist, 2),
                'thief_height_px_projected': round(thief_height_projected(eye, pitch, f), 1)}
        for kind in ('full', 'noglass', 'noblend', 'loaded'):
            img, st = shoot(tools, out, f'view_{tag}_{kind}', cart('aquarium', eye, pitch, scene(kind), near, far))
            view[kind] = st
            if kind == 'full':
                img.save(shots / f'aquarium_{tag}.png')
                img.resize((960, 720), Image.NEAREST).save(shots / f'aquarium_{tag}_x3.png')
                images.append(img)
        if args.fog:
            fog = (VOID[0], VOID[1], VOID[2], dist - 2, dist + 9)
            img, st = shoot(tools, out, f'view_{tag}_fog', cart('aquarium', eye, pitch, scene('full'), near, far, fog))
            img.save(shots / f'aquarium_{tag}_fog.png')
            view['fog'] = st
        # the thief alone, to count the rows he covers
        img, st = shoot(tools, out, f'view_{tag}_thief',
                        cart('aquarium', eye, pitch, [('ASSET_STANDIN_THIEF_NOBLEND', (tx, 0, tz), thief_yaw)], near, far))
        bg = img.getpixel((0, 0))
        rows = [y for y in range(240) if any(img.getpixel((x, y)) != bg for x in range(320))]
        view['thief_height_px'] = (max(rows) - min(rows) + 1) if rows else 0
        numbers['views'][tag] = view
    sheet = Image.new('RGB', (3 * 640 + 2 * 8, 480), VOID)
    for k, img in enumerate(images):
        sheet.paste(img.resize((640, 480), Image.NEAREST), (k * 648, 0))
    sheet.save(shots / 'compare.png')
    (shots / 'numbers.json').write_text(json.dumps(numbers, indent=1) + '\n')
    for p, v in numbers['views'].items():
        full, ng, nb, ld = v['full'], v['noglass'], v['noblend'], v['loaded']
        print(f'{p}: tris {full["tris"]}, cpu {full["cpu_cycles"]}, gpu {full["gpu_cycles"]} '
              f'(no glass {ng["gpu_cycles"]}, no blend {nb["gpu_cycles"]}, loaded {ld["gpu_cycles"]} / cpu {ld["cpu_cycles"]} / tris {ld["tris"]}); '
              f'thief {v["thief_height_px"]} px (projected {v["thief_height_px_projected"]}), {v["px_per_m_at_target"]} px/m')


if __name__ == '__main__':
    main()
