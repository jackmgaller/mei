#!/usr/bin/env python3
"""Draws a dressed aquarium room through Mei at the game's camera, with its costs.

    python3 carts/afterhours/rooms/aq_great/capture.py aq_great|aq_tops [--build-dir build-ah-R2] [--verify]

rooms/corridor/capture.py, for the aquarium's rooms: two levels and the pan in z. Packs the room's
recipes (dressed/, written by dress_ROOM.py) with the Asset Kit, places them as the room's
placements file says, and draws them in a small Akari cart in mei-headless, which dumps the frame
and its CPU and GPU statistics. Each view is drawn twice:

  room   the room alone: what the room costs to draw
  full   the room with stand-in figures (the aquarium sketch's) and the torch guards' cones, cut by
         the play file's walls that block sight on the figure's level (pale yellow, as the game
         draws them); a dark-eyed watcher's cone, drawn by the game only where it is lit, is left
         out

The camera is the game's (dr_view.akr): yaw 0, 60 degrees down, a 20-degree field of view, 28.166 m
from a target 0.6 m over the floor. frame_room() puts the floor's front edge on line 222 and the
upper level's back edge (at +upper) on line 16; a room deeper than that pans in z between the two,
and a room wider than a screen pans in x by 6.6 m either side of the thief. Each scene says which
end of the z pan it is drawn at ('lo': the front, 'hi': the back), and is drawn at the west end,
the middle and the east end of the x pan. The game draws the doors' leaves, the cards and the
cameras' bodies itself; they are not here.

Writes ROOM/shots/ROOM_SCENE_60.png (320 x 240, the middle), ROOM_SCENE_60_x3.png, the pans side
by side (ROOM_SCENE_60_pan_x3.png) and numbers.json. Needs Pillow.
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
HALF_VIEW = 6.6
VOID = (6, 10, 22)

# per room, per scene: where the z pan stands, the thief (x, z, heading, level) and the watchers drawn
# (id, (x, z) or None for where the play file puts him, heading), headings as the play file's (0
# toward +z, 90 toward +x); a camera's cone starts at its position, with no stand-in
SCENES = {
    'aq_great': {
        # leg 1: along the front of the gallery behind the night guard, who walks the window
        'floor': {'z': 'lo', 'thief': (-6.0, -3.3, 90, 0),
                  'guards': [('ag_guard_floor', (1.5, 0.2), 270), ('ag_camera_window', None, 262)]},
        # leg 8: west along the rim; the keeper on the back walk, the camera on the rim's lamps, the
        # gallery's guard below
        'catwalk': {'z': 'hi', 'thief': (3.2, 2.0, 270, 1),
                    'guards': [('ag_guard_keeper', (-1.5, 4.5), 200), ('ag_camera_rim', None, 128),
                               ('ag_guard_floor', (-4.0, -3.0), 90)]},
    },
    'aq_tops': {
        # leg 7: up the middle walk in its lamp's light, the keeper on the west walk
        'tops': {'z': 'lo', 'thief': (0.0, -0.4, 0, 0),
                 'guards': [('at_guard_keeper', (-8.3, -1.0), 0), ('at_camera_east', None, 262)]},
    },
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


def tz_for(z, h, line):
    tz = z + 5.0
    for _ in range(40):
        tz += (line - project(eye_for(0.0, tz), (0.0, h, z))[1]) / 21
    return tz


def walls(play, level):
    out = []
    for e in play['entities']:
        if e['type'] == 'wall' and e['params'].get('blocks', True) and e['params'].get('level', 0) == level:
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


def cone_recipe(name, gx, gz, look, sight, fov, boxes, y=0.04, rays=16):
    verts = [[gx, y, gz]]
    for k in range(rays + 1):
        h = math.radians(look - fov / 2 + fov * k / rays)
        dx, dz = math.sin(h), math.cos(h)
        t = ray(gx, gz, dx, dz, sight, boxes)
        verts.append([round(gx + dx * t, 4), y, round(gz + dz * t, 4)])
    faces = []
    for k in range(rays):        # facing up
        a, b = verts[k + 1], verts[k + 2]
        cross = (a[2] - gz) * (b[0] - gx) - (a[0] - gx) * (b[2] - gz)
        faces.append([0, k + 1, k + 2] if cross > 0 else [0, k + 2, k + 1])
    return {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': {'vertices': 64, 'triangles': 32},
            'materials': {'cone': {'color': '#fff2a8', 'blend': 'half'}}, 'lighting': {'bake': False},
            'nodes': [{'id': 'fan', 'op': 'mesh', 'material': 'cone', 'vertices': verts, 'faces': faces}]}


def cart(eye, draws):
    lines = ['// Written by carts/afterhours/rooms/aq_great/capture.py.', 'cart "Room capture"', 'import "roompack.akr"',
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


def main(room=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    if room is None:
        ap.add_argument('room', choices=sorted(SCENES))
    ap.add_argument('--build-dir', default='build-ah-R2')
    ap.add_argument('--verify', action='store_true')
    args = ap.parse_args()
    room = room or args.room
    room_dir = ROOMS / room
    build = ROOT / args.build_dir
    tools = {'meic': build / 'meic', 'run': build / 'mei-headless'}
    out = build / 'afterhours-capture' / room
    if out.exists():
        shutil.rmtree(out)
    src = out / 'recipes'
    shutil.copytree(room_dir / 'dressed', src)
    placements = json.loads((room_dir / f'{room}.placements.json').read_text())['placements']
    play = json.loads((room_dir / f'{room}.play.json').read_text())
    rm = next(e for e in play['entities'] if e['type'] == 'room')
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
    upper = rm['params'].get('upper', 0.0)
    ents = {e['id']: e for e in play['entities']}
    scenes = SCENES[room]
    cones, stand = {}, {}
    for sname, sc in scenes.items():
        cones[sname], stand[sname] = [], []
        for k, (gid, at_, look) in enumerate(sc['guards']):
            g = ents[gid]
            gp = g['params']
            lvl = gp.get('level', 0)
            gx, gz = at_ if at_ else (g['position'][0], g['position'][2])
            if rm['params'].get('dark') and not gp.get('torch'):
                # a dark-eyed watcher's fan is drawn bright only where it is lit (cone_lit()): left
                # out here rather than drawn whole
                continue
            cname = f'cone_{sname}_{k}'
            (src / f'{cname}.asset.json').write_text(json.dumps(
                cone_recipe(cname, gx, gz, look, gp['sight'], gp['fov'], walls(play, lvl), y=0.04 + 0.01 * k)))
            cones[sname].append(cname)
            ly = upper if lvl else 0.0
            stand[sname].append((f'ASSET_{cname.upper()}', (0, ly, 0), 0.0))
            if gp.get('kind') != 'camera':
                stand[sname].append(('ASSET_STANDIN_GUARD', (gx, ly, gz), math.radians(look + 180)))
        tx, tzz, th, tl = sc['thief']
        stand[sname].append(('ASSET_STANDIN_THIEF', (tx, upper if tl else 0.0, tzz), math.radians(th + 180)))
    for n in ('standin_thief', 'standin_guard'):
        shutil.copy(AQ / f'{n}.asset.json', src / f'{n}.asset.json')
    all_cones = [c for v in cones.values() for c in v]
    run(kit + ['pack'] + [src / f'{n}.asset.json' for n in names + ['standin_thief', 'standin_guard'] + all_cones] +
        ['-o', out / 'pack', '--name', 'roompack', '--slots', '0-14', '--palette', '0', '--palette8', '14'])
    pack = json.loads((out / 'pack' / 'roompack.pack.json').read_text())
    numbers['assets'] = {a['name']: {'triangles': a.get('triangles'), 'vertices': a.get('vertices')}
                         for a in pack.get('assets', []) if a.get('name') in names}
    for f in (out / 'pack').iterdir():
        shutil.copy(f, out / f.name)

    cz, sz = rm['position'][2], rm['params']['size'][2]
    lo, hi = tz_for(cz - sz / 2, 0.0, FRONT_Y), tz_for(cz + sz / 2, upper, BACK_Y)
    tzs = {'lo': lo, 'hi': hi} if hi > lo else {'lo': (lo + hi) / 2, 'hi': (lo + hi) / 2}
    sx = rm['params']['size'][0]
    pan = sx / 2 - HALF_VIEW
    pans = [('c', 0.0)] if pan <= 0 else [('w', -pan), ('c', 0.0), ('e', pan)]
    placed = [(f'ASSET_{p["asset"].upper()}', tuple(p['position']), 0.0) for p in placements]
    count = {}
    for p in placements:
        count[p['asset']] = count.get(p['asset'], 0) + 1
    numbers['room_triangles'] = sum(numbers['assets'][a]['triangles'] * k for a, k in count.items())
    shots = room_dir / 'shots'
    shots.mkdir(exist_ok=True)
    numbers['camera'] = {'target_z': {k: round(v, 3) for k, v in tzs.items()}, 'pans': {}}
    for sname, sc in scenes.items():
        tz = tzs[sc['z']]
        fulls = []
        for tag, px in pans:
            eye = eye_for(px, tz)
            numbers['camera']['pans'][f'{sname}_{tag}'] = [round(c, 3) for c in eye]
            for kind, draws in (('room', placed), ('full', placed + stand[sname])):
                img, st = shoot(tools, out, f'{sname}_{kind}_{tag}', cart(eye, draws))
                numbers[f'{sname}_{kind}_{tag}'] = st
                if kind == 'full':
                    fulls.append(img)
                    if tag == 'c':
                        img.save(shots / f'{room}_{sname}_60.png')
                        img.resize((960, 720), Image.NEAREST).save(shots / f'{room}_{sname}_60_x3.png')
        if len(fulls) > 1:
            sheet = Image.new('RGB', (960 * len(fulls) + 8 * (len(fulls) - 1), 720), VOID)
            for k, img in enumerate(fulls):
                sheet.paste(img.resize((960, 720), Image.NEAREST), (k * 968, 0))
            sheet.save(shots / f'{room}_{sname}_60_pan_x3.png')
    (shots / 'numbers.json').write_text(json.dumps(numbers, indent=1) + '\n')
    for key in sorted(k for k in numbers if isinstance(numbers[k], dict) and 'tris' in numbers[k]):
        s = numbers[key]
        print(f'{key}: tris drawn {s.get("tris")}, cpu {s.get("cpu_cycles")}, gpu {s.get("gpu_cycles")}')
    print(f'room triangles (placed): {numbers["room_triangles"]}; per asset {numbers["assets"]}')


if __name__ == '__main__':
    main()
