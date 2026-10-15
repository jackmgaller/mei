#!/usr/bin/env python3
"""Draws a dressed room of stage 2 through Mei at the game's camera, with its costs.

    python3 carts/afterhours/rooms/arrival/capture.py arrival|gates [--build-dir build-dr-R1] [--verify]

Packs the room's recipes (dressed/, written by dress_ROOM.py) with the Asset Kit, places them as the
room's placements file says (or dressed/draft.placements.json while one exists), and draws them in a small Akari cart in mei-headless, which dumps the
frame and its CPU and GPU statistics (the method of rooms/aquarium/capture.py). Two scenes:

  room   the room alone: what the room costs to draw
  full   the room with a stand-in thief and its watchers (the aquarium's stand-ins) and their
         cones, cut by the play file's walls that block sight (pale yellow, as the game draws them)

The camera is the game's (dr_view.akr): yaw 0, 60 degrees down, a 20-degree field of view, 28.166 m
from a target 0.6 m over the floor, the target's z as frame_room() sets it (NOTES_A.md, "The
framing"): the floor's front edge on line 222 and its back edge on line 16, their mean when the room
fits. A room wider than a screen is drawn three times, the camera panned to its west end, its
middle and its east end, as the game pans. The game draws the doors' leaves, the cards and the
cameras' bodies itself; they are not here. Writes ROOM/shots/ROOM_60.png (320 x 240, the middle),
ROOM_60_x3.png, ROOM_60_pan_x3.png (the pans side by side, for a wide room) and numbers.json.
Level 1's arrival/capture.py, generalised. Needs Pillow.
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
AQ = ROOMS / 'aquarium'

PITCH = -1.0472
FOV = 0.34907
DIST = 28.166
TARGET_Y = 0.6
FRONT_Y, BACK_Y = 222, 16
VOID = (6, 10, 22)

# per room: the thief (x, z, heading) and the watchers drawn (id, (x, z) or None for where the play
# file puts him, heading), headings as the play file's (0 toward +z, 90 toward +x); a camera's cone
# starts at its position, with no stand-in
SCENES = {
    'cinema': {'thief': (-3.0, 3.75, 90), 'guards': [('cn_guard_usher', (-8.0, -3.75), 90),
                                                     ('cn_guard_cleaner', (1.9, 3.75), 260),
                                                     ('cn_camera_booth', None, 270)]},
    'booth': {'thief': (-4.6, 1.6, 180), 'guards': [('pb_guard_projectionist', (-1.8, -1.4), 55)]},
    'corridor': {'thief': (1.5, 2.95, 180), 'guards': [('sc_guard_office', None, 40), ('sc_guard_porter', (-3.2, 1.0), 0),
                                                       ('sc_camera_stair', None, 300)]},
}


def run(args, **kw):
    res = subprocess.run([str(a) for a in args], capture_output=True, text=True, cwd=ROOT, **kw)
    if res.returncode:
        sys.exit(f'failed: {" ".join(map(str, args))}\n{res.stdout[-3000:]}\n{res.stderr[-3000:]}')
    return res


def project(eye, p):
    sp, cp = math.sin(PITCH), math.cos(PITCH)
    f = 1 / math.tan(FOV / 2)
    d = [p[i] - eye[i] for i in range(3)]
    y = d[1] * cp - d[2] * sp
    w = d[1] * sp + d[2] * cp
    return 160 + 120 * f * d[0] / w, 120 - 120 * f * y / w


def eye_for(x, tz):
    return [x, TARGET_Y - math.sin(PITCH) * DIST, tz - math.cos(PITCH) * DIST]


def tz_for(z, line):
    tz = z + 5.0
    for _ in range(40):
        tz += (line - project(eye_for(0.0, tz), (0.0, 0.0, z))[1]) / 21
    return tz


def walls(play):
    out = []
    for e in play['entities']:
        if e['type'] == 'wall' and e['params'].get('blocks', True):
            (x, _, z), (sx, _, sz) = e['position'], e['params']['size']
            out.append((x - sx / 2, z - sz / 2, x + sx / 2, z + sz / 2))
    return out


def ray(ox, oz, dx, dz, length, boxes):
    best = length
    for x0, z0, x1, z1 in boxes:
        tmin, tmax = 0.0, best
        ok = True
        for o, d, lo, hi in ((ox, dx, x0, x1), (oz, dz, z0, z1)):
            if abs(d) < 1e-9:
                if not lo <= o <= hi:
                    ok = False
                continue
            t0, t1 = sorted(((lo - o) / d, (hi - o) / d))
            tmin, tmax = max(tmin, t0), min(tmax, t1)
        if ok and tmin <= tmax and tmin > 0.05:
            best = min(best, tmin)
    return best


def cone_recipe(name, gx, gz, look, sight, fov, boxes, rays=16):
    verts = [[gx, 0.04, gz]]
    for k in range(rays + 1):
        h = math.radians(look - fov / 2 + fov * k / rays)
        dx, dz = math.sin(h), math.cos(h)
        t = ray(gx, gz, dx, dz, sight, boxes)
        verts.append([round(gx + dx * t, 4), 0.04, round(gz + dz * t, 4)])
    faces = []
    for k in range(rays):        # facing up
        a, b = verts[k + 1], verts[k + 2]
        cross = (a[2] - gz) * (b[0] - gx) - (a[0] - gx) * (b[2] - gz)
        faces.append([0, k + 1, k + 2] if cross > 0 else [0, k + 2, k + 1])
    return {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': {'vertices': 64, 'triangles': 32},
            'materials': {'cone': {'color': '#fff2a8', 'blend': 'half'}}, 'lighting': {'bake': False},
            'nodes': [{'id': 'fan', 'op': 'mesh', 'material': 'cone', 'vertices': verts, 'faces': faces}]}


def cart(eye, draws):
    lines = ['// Written by carts/afterhours/rooms/arrival/capture.py.', 'cart "Room capture"', 'import "roompack.akr"',
             'import "depth.akr"', '', 'fn init() { roompack_load() }', '', 'fn draw() {',
             f'    cls(rgb({VOID[0]}, {VOID[1]}, {VOID[2]}))', '    render_depth(true)', '    render_perspective(true)',
             f'    camera_fov({FOV:.5f})', f'    camera_clip({DIST - 14:.3f}, {DIST + 14:.3f})',
             f'    camera_look(vec3({eye[0]:.5f}, {eye[1]:.5f}, {eye[2]:.5f}), 0.0, {PITCH:.5f})']
    for mesh, (x, y, z), yaw in draws:
        lines.append(f'    mesh_at({mesh}, vec3({x:.4f}, {y:.4f}, {z:.4f}), {yaw:.5f})')
    lines.append('}')
    return '\n'.join(lines) + '\n'


def shoot(tools, out, stem, code):
    (out / f'{stem}.akr').write_text(code)
    run([tools['meic'], out / f'{stem}.akr', '-o', out / f'{stem}.mei'])
    run([tools['run'], out / f'{stem}.mei', '--frames', '4', '--dump', out / f'{stem}.ppm', '--gpu-stats', out / f'{stem}.csv'])
    with (out / f'{stem}.csv').open() as f:
        stats = {k: int(v) for k, v in list(csv.DictReader(f))[-1].items()}
    return Image.open(out / f'{stem}.ppm').convert('RGB'), stats


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('room', choices=sorted(SCENES))
    ap.add_argument('--build-dir', default='build-ah-R1')
    ap.add_argument('--verify', action='store_true')
    args = ap.parse_args()
    room_dir = ROOMS / args.room
    build = ROOT / args.build_dir
    tools = {'meic': build / 'meic', 'run': build / 'mei-headless'}
    out = build / 'afterhours-capture' / args.room
    if out.exists():
        shutil.rmtree(out)
    src = out / 'recipes'
    shutil.copytree(room_dir / 'dressed', src)
    draft = room_dir / 'dressed' / 'draft.placements.json'
    pfile = draft if draft.exists() else room_dir / f'{args.room}.placements.json'
    placements = json.loads(pfile.read_text())['placements']
    play = json.loads((room_dir / f'{args.room}.play.json').read_text())
    kit = [sys.executable, ROOT / 'tools' / 'mei_assets.py']
    numbers = {'checks': {}}
    names = sorted({p['asset'] for p in placements})
    if args.verify:
        for n in names:
            res = subprocess.run([str(a) for a in kit + ['verify', src / f'{n}.asset.json', '-o', out / f'verify_{n}',
                                                          '--build-dir', build, '--json']], capture_output=True, text=True, cwd=ROOT)
            rep = json.loads(res.stdout)
            numbers['checks'][n] = rep.get('verdict')
            print(f'verify {n}: {rep.get("verdict")}')
            for line in rep.get('failures', []):
                print('   ', line)
    sc = SCENES[args.room]
    ents = {e['id']: e for e in play['entities']}
    cones, stand = [], []
    for k, (gid, at_, look) in enumerate(sc['guards']):
        g = ents[gid]
        gx, gz = at_ if at_ else (g['position'][0], g['position'][2])
        gp = g['params']
        (src / f'cone_{k}.asset.json').write_text(json.dumps(cone_recipe(f'cone_{k}', gx, gz, look, gp['sight'], gp['fov'], walls(play))))
        cones.append(f'cone_{k}')
        stand.append((f'ASSET_CONE_{k}', (0, 0, 0), 0.0))
        if gp.get('kind') != 'camera':
            stand.append(('ASSET_STANDIN_GUARD', (gx, 0, gz), math.radians(look + 180)))
    tx, tzz, th = sc['thief']
    stand.append(('ASSET_STANDIN_THIEF', (tx, 0, tzz), math.radians(th + 180)))
    for n in ('standin_thief', 'standin_guard'):
        shutil.copy(AQ / f'{n}.asset.json', src / f'{n}.asset.json')
    run(kit + ['pack'] + [src / f'{n}.asset.json' for n in names + ['standin_thief', 'standin_guard'] + cones] +
        ['-o', out / 'pack', '--name', 'roompack', '--slots', '0-14', '--palette', '0', '--palette8', '14'])
    pack = json.loads((out / 'pack' / 'roompack.pack.json').read_text())
    numbers['assets'] = {a['name']: {'triangles': a.get('triangles'), 'vertices': a.get('vertices')}
                         for a in pack.get('assets', []) if a.get('name') in names}
    for f in (out / 'pack').iterdir():
        shutil.copy(f, out / f.name)

    rm = next(e for e in play['entities'] if e['type'] == 'room')
    cz, sz = rm['position'][2], rm['params']['size'][2]
    lo, hi = tz_for(cz - sz / 2, FRONT_Y), tz_for(cz + sz / 2, BACK_Y)
    tz = (lo + hi) / 2 if hi <= lo else lo
    sx = rm['params']['size'][0]
    pans = [('c', 0.0)] if sx <= 13.5 else [('w', -(sx / 2 - 6.6)), ('c', 0.0), ('e', sx / 2 - 6.6)]
    placed = [(f'ASSET_{p["asset"].upper()}', tuple(p['position']), 0.0) for p in placements]
    count = {}
    for p in placements:
        count[p['asset']] = count.get(p['asset'], 0) + 1
    numbers['room_triangles'] = sum(numbers['assets'][a]['triangles'] * k for a, k in count.items())
    shots = room_dir / 'shots'
    shots.mkdir(exist_ok=True)
    numbers['camera'] = {'target_z': round(tz, 3), 'pans': {}}
    fulls = []
    for tag, px in pans:
        eye = eye_for(px, tz)
        numbers['camera']['pans'][tag] = [round(c, 3) for c in eye]
        for kind, draws in (('room', placed), ('full', placed + stand)):
            img, st = shoot(tools, out, f'{kind}_{tag}', cart(eye, draws))
            numbers[f'{kind}_{tag}'] = st
            if kind == 'full':
                fulls.append(img)
                if tag == 'c':
                    img.save(shots / f'{args.room}_60.png')
                    img.resize((960, 720), Image.NEAREST).save(shots / f'{args.room}_60_x3.png')
    if len(fulls) > 1:
        sheet = Image.new('RGB', (960 * len(fulls) + 8 * (len(fulls) - 1), 720), VOID)
        for k, img in enumerate(fulls):
            sheet.paste(img.resize((960, 720), Image.NEAREST), (k * 968, 0))
        sheet.save(shots / f'{args.room}_60_pan_x3.png')
    (shots / 'numbers.json').write_text(json.dumps(numbers, indent=1) + '\n')
    for key in sorted(k for k in numbers if k.startswith(('room_', 'full_')) and k != 'room_triangles'):
        s = numbers[key]
        print(f'{key}: tris drawn {s.get("tris")}, cpu {s.get("cpu_cycles")}, gpu {s.get("gpu_cycles")}')
    print(f'room triangles (placed): {numbers["room_triangles"]}; per asset {numbers["assets"]}')


if __name__ == '__main__':
    main()
