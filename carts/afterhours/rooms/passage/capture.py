#!/usr/bin/env python3
"""Draws room 3 or 4 through Mei at the game's camera, with its costs.

    python3 carts/afterhours/rooms/passage/capture.py passage|lobby [--build-dir build-dr-R2] [--verify]

The camera is the game's (dr_view.akr): fixed yaw, 60 degrees down, a 20-degree field of view,
28.166 m from a target 0.6 m above the floor, the floor between lines 16 and 222; a room wider than
the screen is drawn at each end of its pan and in the middle. Packs the room's recipes (its
placements file says which) with the aquarium's stand-in figures, writes one small Akari cart per
view into BUILD_DIR/afterhours-r2/ROOM/, compiles it with meic and runs it in mei-headless, which
dumps the frame and its CPU and GPU statistics. Each view is drawn:

  full   the room, the thief stand-in where the solution waits, the watchers and their cones
         (16 rays, cut by the play file's walls, as the game cuts them)
  bare   the room alone: what the room itself costs

Writes, in the room's shots/: ROOM_60_K.png (320 x 240, as the console draws it) and its _x3
scaled copy for each view K, ROOM_60.png (the views side by side, scaled up twice) and
numbers.json. With --verify, runs the Asset Checker on each recipe first. Needs Pillow.
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
ROOMS = HERE.parent
ROOT = HERE.parents[3]
AQUARIUM = ROOMS / 'aquarium'

CAM_PITCH = 60.0
FOV = 20.0
CAM_DIST = 28.166
TARGET_Y = 0.6
FRONT_Y = 222                  # the floor's front edge no lower than this line
BACK_Y = 16                    # and its back edge no higher than this one
HALF_VIEW = 6.6
VOID = (6, 10, 22)
CONE_Y = 0.03
RAYS = 16

# Where the stand-ins stand in each room's shot: the thief at a point of the solution, each
# watcher with its look in the game's degrees (0 faces +z, 90 faces +x).
SCENES = {
    'passage': {'thief': ((4.6, -2.3), 80), 'looks': {'r3_camera': 235}, 'assets': ['r3_passage', 'r3_showcase']},
    'lobby': {'thief': ((2.2, -1.1), 0), 'looks': {'r4_guard_west': 10, 'r4_guard_back': 260},
              'at': {'r4_guard_west': (-3.2, 2.2), 'r4_guard_back': (-2.4, 2.6)}, 'assets': ['r4_lobby', 'r4_escalator', 'r4_front']},
    # stage 2 (carts/afterhours/levels/level2): the thief where a leg's solution waits
    'shopfloor': {'thief': ((7.0, -3.7), 90), 'looks': {'sf_camera_lift': 260, 'sf_guard_night': 90},
                  'at': {'sf_guard_night': (2.6, 3.4)}, 'assets': ['sf_floor', 'sf_escalators', 'sf_counters']},
    'foodhall': {'thief': ((-3.0, -3.0), 90), 'looks': {'fh_camera_middle': 180, 'fh_guard_melon': 300, 'fh_guard_cleaner': 270},
                 'at': {'fh_guard_cleaner': (2.0, 2.9)}, 'assets': ['fh_hall', 'fh_cases']},
}


def game_props(play):
    """Stand-ins for what agent A draws from the play file: the fragile stacks, the keycards and
    the shut staff doors' leaves (their places only, in plain colours)."""
    nodes, mats = [], {'stack': {'color': '#e8c8d0'}, 'card_blue': {'color': '#3080ff', 'class': 'emissive'},
                       'card_red': {'color': '#ff3030', 'class': 'emissive'}, 'leaf_red': {'color': '#b02828'},
                       'leaf_blue': {'color': '#2850b0'}}
    for e in play['entities']:
        x, _, z = e['position']
        p = e.get('params', {})
        if e['type'] == 'fragile':
            nodes.append({'id': e['id'], 'op': 'cylinder', 'radius': 0.32, 'height': 0.55, 'segments': 6, 'material': 'stack',
                          'transform': {'translate': [x, 0.275, z]}})
        elif e['type'] == 'keycard':
            nodes.append({'id': e['id'], 'op': 'box', 'size': [0.3, 0.04, 0.2], 'material': 'card_' + p['colour'],
                          'transform': {'translate': [x, 0.03, z]}})
        elif e['type'] == 'door' and p.get('card'):
            sx, sy, sz = p['size']
            yaw = e.get('yaw', 0)
            size = [sx, 2.1, 0.08] if yaw in (0, 180) else [0.08, 2.1, sx]
            nodes.append({'id': e['id'], 'op': 'box', 'size': size, 'material': 'leaf_' + p['card'],
                          'transform': {'translate': [x, 1.05, z]}})
    if not nodes:
        return None
    return {'format': 'mei-asset', 'version': 1, 'name': 'game_props', 'budget': {'vertices': 512, 'triangles': 400},
            'materials': mats, 'nodes': nodes, 'lighting': {'ambient': 0.6}, 'verification': {'required': False}}


def run(args, **kw):
    res = subprocess.run([str(a) for a in args], capture_output=True, text=True, cwd=ROOT, **kw)
    if res.returncode:
        sys.exit(f'failed: {" ".join(map(str, args))}\n{res.stdout[-3000:]}\n{res.stderr[-3000:]}')
    return res


def project(eye, f, p):
    pitch = -math.radians(CAM_PITCH)
    sp, cp = math.sin(pitch), math.cos(pitch)
    d = [p[i] - eye[i] for i in range(3)]
    y = d[1] * cp - d[2] * sp
    w = d[1] * sp + d[2] * cp
    return 160 + 120 * f * d[0] / w, 120 - 120 * f * y / w, w


def eye_at(x, tz, floor=0.0):
    pitch = -math.radians(CAM_PITCH)
    return [x, floor + TARGET_Y - math.sin(pitch) * CAM_DIST, tz - math.cos(pitch) * CAM_DIST]


def tz_for(cx, z, line, f):
    """The target's z at which the floor point (cx, 0, z) projects to picture line `line`."""
    tz = z + 5.0
    for _ in range(60):
        _, y, _ = project(eye_at(cx, tz), f, (cx, 0.0, z))
        tz += (line - y) / 21
    return tz


def frame_room(room, f):
    """The target's z as dr_view.akr's frame_room() finds it (NOTES_A.md, "The framing"): the
    floor's front edge on line 222 and its back edge on line 16; their mean when the room fits,
    else the front on its line (the thief near the front)."""
    cx, cz, sz = room['position'][0], room['position'][2], room['params']['size'][2]
    lo = tz_for(cx, cz - sz / 2, FRONT_Y, f)
    hi = tz_for(cx, cz + sz / 2, BACK_Y, f)
    return (lo + hi) / 2 if hi <= lo else lo


def frame_room_back(room, f):
    """The target's z with the thief at the back: the back edge on line BACK_Y (or the middle)."""
    cx, cz, sz = room['position'][0], room['position'][2], room['params']['size'][2]
    lo = tz_for(cx, cz - sz / 2, FRONT_Y, f)
    hi = tz_for(cx, cz + sz / 2, BACK_Y, f)
    return (lo + hi) / 2 if hi <= lo else hi


def pans(room):
    sx, cx = room['params']['size'][0], room['position'][0]
    lo, hi = cx - sx / 2 + HALF_VIEW, cx + sx / 2 - HALF_VIEW
    if lo >= hi:
        return [cx]
    if hi - lo < 2.0:
        return [cx]
    return [lo, cx, hi]


# ---- the cones: 16 rays cut by the play file's walls that block sight

def segments(play):
    segs = []
    for e in play['entities']:
        if e['type'] != 'wall' or not e['params'].get('blocks', True):
            continue
        (x, _, z), (sx, _, sz) = e['position'], e['params']['size']
        a, b, c, d = (x - sx / 2, z - sz / 2), (x + sx / 2, z - sz / 2), (x + sx / 2, z + sz / 2), (x - sx / 2, z + sz / 2)
        segs += [(a, b), (b, c), (c, d), (d, a)]
    return segs


def ray(ox, oz, dx, dz, length, segs):
    best = length
    for (ax, az), (bx, bz) in segs:
        ex, ez = bx - ax, bz - az
        den = dx * ez - dz * ex
        if abs(den) < 1e-9:
            continue
        t = ((ax - ox) * ez - (az - oz) * ex) / den
        u = ((ax - ox) * dz - (az - oz) * dx) / den
        if 0 <= u <= 1 and 1e-6 < t < best:
            best = t
    return best


def cone_recipe(name, origin, look, sight, fov, segs):
    ox, oz = origin
    pts = []
    for k in range(RAYS + 1):
        a = math.radians(look - fov / 2 + fov * k / RAYS)
        dx, dz = math.sin(a), math.cos(a)
        t = ray(ox, oz, dx, dz, sight, segs)
        pts.append((ox + dx * t, oz + dz * t))
    verts = [[round(ox, 4), CONE_Y, round(oz, 4)]] + [[round(x, 4), CONE_Y, round(z, 4)] for x, z in pts]
    faces = [[0, k + 1, k] for k in range(1, RAYS + 1)]
    return {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': {'vertices': 64, 'triangles': 32},
            'materials': {'cone': {'color': '#fff2a8', 'blend': 'half', 'double_sided': True}},
            'nodes': [{'id': 'fan', 'op': 'mesh', 'material': 'cone', 'vertices': verts, 'faces': faces}],
            'lighting': {'bake': False}, 'verification': {'required': False}}


def yaw_facing(deg):
    """mesh_at's yaw for a stand-in (built facing -z) to face the game's heading deg."""
    a = math.radians(deg)
    return math.atan2(-math.sin(a), -math.cos(a))


def cart(pack, eye, draws, near, far):
    pitch = -math.radians(CAM_PITCH)
    lines = ['// Written by carts/afterhours/rooms/passage/capture.py: one view of a room.',
             'cart "Room capture"', f'import "{pack}.akr"', 'import "depth.akr"', '',
             f'fn init() {{ {pack}_load() }}', '', 'fn draw() {',
             f'    cls(rgb({VOID[0]}, {VOID[1]}, {VOID[2]}))',
             '    render_depth(true)', '    render_perspective(true)',
             f'    camera_fov({math.radians(FOV):.7f})',
             f'    camera_clip({near:.4f}, {far:.4f})',
             f'    camera_look(vec3({eye[0]:.5f}, {eye[1]:.5f}, {eye[2]:.5f}), 0.0, {pitch:.7f})']
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
    return Image.open(directory / f'{stem}.ppm').convert('RGB'), {k: int(v) for k, v in rows[-1].items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('room', choices=sorted(SCENES))
    ap.add_argument('--build-dir', default='build-dr-R2')
    ap.add_argument('--verify', action='store_true', help='run the Asset Checker on every recipe first')
    args = ap.parse_args()
    folder = ROOMS / args.room
    build = ROOT / args.build_dir
    tools = {'meic': build / 'meic', 'run': build / 'mei-headless'}
    for t in tools.values():
        if not t.is_file():
            sys.exit(f'missing {t}: make B={args.build_dir} {args.build_dir}/meic {args.build_dir}/mei-headless')
    out = build / 'afterhours-r2' / args.room
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    kit = [sys.executable, ROOT / 'tools' / 'mei_assets.py']
    play = json.loads((folder / f'{args.room}.play.json').read_text())
    placements = json.loads((folder / f'{args.room}.placements.json').read_text())['placements']
    if any(not (folder / f'{p["asset"]}.asset.json').is_file() for p in placements):
        # the placements still name the greybox: draw the dressed recipes at the origin
        placements = [{'asset': n, 'position': [0, 0, 0]} for n in SCENES[args.room]['assets']]
    names = sorted({p['asset'] for p in placements})
    sources = {n: folder / f'{n}.asset.json' for n in names}
    checks = {}
    if args.verify:
        for n, src in sources.items():
            res = subprocess.run([str(a) for a in kit + ['verify', src, '-o', out / f'verify_{n}', '--build-dir', build,
                                                          '--json']], capture_output=True, text=True, cwd=ROOT)
            rep = json.loads(res.stdout)
            if 'verdict' not in rep:
                sys.exit(f'verify {n}: {rep.get("errors")}')
            checks[n] = {'ok': rep['ok'], 'verdict': rep['verdict'], 'failures': rep['failures']}
            print(f'verify {n}: {rep["verdict"]}')
            for line in rep['failures']:
                print('   ', line)

    src = out / 'recipes'
    src.mkdir()
    for n, s in sources.items():
        shutil.copy(s, src / s.name)
    if (folder / 'art').is_dir():
        shutil.copytree(folder / 'art', src / 'art')
    for n in ('standin_thief', 'standin_guard'):
        shutil.copy(AQUARIUM / f'{n}.asset.json', src / f'{n}.asset.json')
    scene = SCENES[args.room]
    segs = segments(play)
    watchers = []
    for e in play['entities']:
        if e['type'] != 'guard':
            continue
        p = e['params']
        pos = scene.get('at', {}).get(e['id'], (e['position'][0], e['position'][2]))
        look = scene['looks'].get(e['id'], p.get('look_a', 0))
        cname = f'cone_{e["id"]}'
        (src / f'{cname}.asset.json').write_text(json.dumps(cone_recipe(cname, pos, look, p['sight'], p['fov'], segs)))
        watchers.append((e, pos, look, cname))
    packed = names + ['standin_thief', 'standin_guard'] + [w[3] for w in watchers]
    gp = game_props(play)
    if gp:
        (src / 'game_props.asset.json').write_text(json.dumps(gp))
        packed.append('game_props')
    run(kit + ['pack'] + [src / f'{n}.asset.json' for n in packed] +
        ['-o', out / 'pack', '--name', 'room', '--slots', '0-14', '--palette', '0', '--palette8', '14'])
    pack_json = json.loads((out / 'pack' / 'room.pack.json').read_text())
    for f in (out / 'pack').iterdir():
        shutil.copy(f, out / f.name)

    f = 1 / math.tan(math.radians(FOV) / 2)
    room = next(e for e in play['entities'] if e['type'] == 'room')
    tz = frame_room(room, f)
    (tx, tzz), theading = scene['thief']
    room_draws = [(f'ASSET_{p["asset"].upper()}', tuple(p['position']), math.radians(p.get('yaw', 0))) for p in placements]
    full = list(room_draws) + [('ASSET_STANDIN_THIEF', (tx, 0, tzz), yaw_facing(theading))]
    if gp:
        full.append(('ASSET_GAME_PROPS', (0, 0, 0), 0.0))
    for e, (gx, gz), look, cname in watchers:
        if e['params'].get('kind') != 'camera':
            full.append(('ASSET_STANDIN_GUARD', (gx, 0, gz), yaw_facing(look)))
        full.append((f'ASSET_{cname.upper()}', (0, 0, 0), 0.0))
    shots = folder / 'shots'
    shots.mkdir(exist_ok=True)
    numbers = {'camera': {'pitch_degrees': CAM_PITCH, 'fov_degrees': FOV, 'distance': CAM_DIST, 'target_z': round(tz, 3)},
               'checks': checks, 'assets': {}, 'views': {}}
    for entry in pack_json.get('assets', []):
        if entry.get('name') in names:
            numbers['assets'][entry['name']] = {k: entry.get(k) for k in ('triangles', 'vertices')}
    images = []
    views = [(x, tz) for x in pans(room)]
    tz_back = frame_room_back(room, f)
    if tz_back - tz > 0.05:          # a room deeper than the picture pans in z too: its back as well
        views.append((room['position'][0], tz_back))
    for k, (x, tz) in enumerate(views):
        eye = eye_at(x, tz)
        view = {'pan_x': round(x, 3), 'target_z': round(tz, 3), 'eye': [round(c, 3) for c in eye]}
        for kind, draws in (('full', full), ('bare', room_draws)):
            img, st = shoot(tools, out, f'view_{k}_{kind}', cart('room', eye, draws, CAM_DIST - 14, CAM_DIST + 14))
            view[kind] = st
            if kind == 'full':
                img.save(shots / f'{args.room}_60_{k}.png')
                img.resize((960, 720), Image.NEAREST).save(shots / f'{args.room}_60_{k}_x3.png')
                images.append(img)
        numbers['views'][str(k)] = view
        print(f'view {k} (x {x:+.2f}, z {tz:+.2f}): full {view["full"]["tris"]} tris, cpu {view["full"]["cpu_cycles"]}, '
              f'gpu {view["full"]["gpu_cycles"]}; bare {view["bare"]["tris"]} tris, cpu {view["bare"]["cpu_cycles"]}, '
              f'gpu {view["bare"]["gpu_cycles"]}')
    sheet = Image.new('RGB', (len(images) * 648 - 8, 480), VOID)
    for k, img in enumerate(images):
        sheet.paste(img.resize((640, 480), Image.NEAREST), (k * 648, 0))
    sheet.save(shots / f'{args.room}_60.png')
    (shots / 'numbers.json').write_text(json.dumps(numbers, indent=1) + '\n')
    for n, a in numbers['assets'].items():
        print(f'{n}: {a["triangles"]} triangles, {a["vertices"]} vertices')


if __name__ == '__main__':
    main()
