#!/usr/bin/env python3
"""Draws R1's aquarium rooms (the entrance hall, the jellyfish gallery) through Mei at the game's
camera, with their costs.

    python3 carts/afterhours/rooms/aq_hall/capture.py aq_hall|aq_jelly [--build-dir build-ah-R1] [--verify]

rooms/corridor/capture.py adapted to the aquarium's dark rooms and two levels. Packs the room's
placed recipes (the room's folder, dressed/ and greybox/ are searched for them) with the Asset
Kit, places them as NAME.placements.json says (or dressed/draft.placements.json while one
exists), and draws them in a small Akari cart in mei-headless, which dumps the frame and its CPU
and GPU statistics. Per shot two scenes:

  room   the room alone: what the room costs to draw
  full   with a stand-in thief and the shot's watchers (rooms/aquarium's stand-ins), the washes the
         runtime draws over the lights that are on (dr_view.akr's draw_lights(), rgb(46, 70, 88)
         added), and the watchers' fans cut by their level's walls that block sight: a torch's or a
         lit room's fan whole, a dark-eyed watcher's clipped to the lights on (the rest left out,
         where the game draws a dotted outline)

Everything on level 1 is drawn at the room's `upper`. The camera is the game's (dr_view.akr): yaw
0, 60 degrees down, a 20-degree field of view, 28.166 m from a target 0.6 m over the floor, the
target's z as frame_room() sets it (the floor's front edge on line 222, the highest level's back
edge on line 16, their mean when the room fits). A room wider than the picture is drawn panned to
its west end, middle and east end. The game draws the doors' leaves and the cameras' bodies
itself; they are not here. Writes ROOM/shots/ROOM_SHOT.png (320 x 240, the middle pan),
ROOM_SHOT_x3.png, ROOM_SHOT_pan_x3.png (the pans side by side) and numbers.json. Needs Pillow.
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
HALF_VIEW = 6.6
FRONT_Y, BACK_Y = 222, 16
VOID = (6, 10, 22)

# per room, its shots: the level shown, the thief (x, z, heading), the watchers drawn (id, (x, z) or
# None for where the play file puts him, heading; headings as the play file's, 0 toward +z, 90
# toward +x) and the lights on (ids without the prefix; None: every steady light)
SHOTS = {
    'aq_hall': {
        # leg 0: the thief waits at the front wall's west end while the desk guard looks at the east
        # door; his fan crosses the tank's light
        'floor': {'level': 0, 'thief': (-3.0, -2.9, 90),
                  'guards': [('ah_guard_desk', None, 200)], 'lights': None},
        # leg 9: on the mezzanine, the torch guard walking west, the camera looking west along it
        'mezz': {'level': 1, 'thief': (3.6, 3.1, 270),
                 'guards': [('ah_guard_mezz', (-0.5, 2.3), 270), ('ah_camera_mezz', None, 272)], 'lights': None},
    },
    'aq_jelly': {
        # leg 2: bays 1 and 2 on (the wave's middle), the thief in the dark behind it
        'wave': {'level': 0, 'thief': (-4.5, -2.4, 90),
                 'guards': [('aj_guard_end', None, 300), ('aj_guard_keeper', (-1.0, 2.6), 90)],
                 'lights': ['bay_1', 'bay_2']},
        'dark': {'level': 0, 'thief': (1.5, -2.4, 90),
                 'guards': [('aj_guard_end', None, 290)], 'lights': []},
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


def tz_for(z, line, h=0.0):
    tz = z + 5.0
    for _ in range(40):
        tz += (line - project(eye_for(0.0, tz), (0.0, h, z))[1]) / 21
    return tz


def walls(play, level):
    out = []
    for e in play['entities']:
        p = e['params']
        if e['type'] == 'wall' and p.get('blocks', True) and p.get('level', 0) == level:
            (x, _, z), (sx, _, sz) = e['position'], p['size']
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


def clip(poly, x0, z0, x1, z1):
    """A polygon [(x, z)] clipped to a box (Sutherland-Hodgman)."""
    def cut(pts, inside, inter):
        out = []
        for k in range(len(pts)):
            a, b = pts[k - 1], pts[k]
            if inside(b):
                if not inside(a):
                    out.append(inter(a, b))
                out.append(b)
            elif inside(a):
                out.append(inter(a, b))
        return out

    def ix(xc):
        return lambda a, b: (xc, a[1] + (b[1] - a[1]) * (xc - a[0]) / (b[0] - a[0]))

    def iz(zc):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (zc - a[1]) / (b[1] - a[1]), zc)
    for inside, inter in ((lambda p: p[0] >= x0, ix(x0)), (lambda p: p[0] <= x1, ix(x1)),
                          (lambda p: p[1] >= z0, iz(z0)), (lambda p: p[1] <= z1, iz(z1))):
        poly = cut(poly, inside, inter)
        if not poly:
            return []
    return poly


def cone_recipe(name, gx, gz, y, look, sight, fov, boxes, lit_boxes=None, rays=16):
    """The fan, cut by the walls; with lit_boxes, only its parts inside them (a dark-eyed watcher)."""
    edge = []
    for k in range(rays + 1):
        h = math.radians(look - fov / 2 + fov * k / rays)
        dx, dz = math.sin(h), math.cos(h)
        t = ray(gx, gz, dx, dz, sight, boxes)
        edge.append((gx + dx * t, gz + dz * t))
    tris = [[(gx, gz), edge[k], edge[k + 1]] for k in range(rays)]
    polys = tris if lit_boxes is None else [p for t in tris for b in lit_boxes for p in [clip(t, *b)] if len(p) >= 3]
    verts, faces = [], []
    for p in polys:
        base = len(verts)
        verts += [[round(x, 4), round(y + 0.04, 4), round(z, 4)] for x, z in p]
        area = sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))
        idx = list(range(base, base + len(p)))
        faces.append(idx[::-1] if area > 0 else idx)       # facing up (+y): clockwise seen from above in x-z
    if not faces:
        verts, faces = [[gx, y + 0.04, gz], [gx + 0.01, y + 0.04, gz], [gx, y + 0.04, gz + 0.01]], [[0, 2, 1]]
    return {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': {'vertices': 512, 'triangles': 256},
            'materials': {'cone': {'color': '#fff2a8', 'blend': 'half'}}, 'lighting': {'bake': False},
            'nodes': [{'id': 'fan', 'op': 'mesh', 'material': 'cone', 'vertices': verts, 'faces': faces}]}


def wash_recipe(name, boxes):
    """The runtime's wash over the lights on: rgb(46, 70, 88) added, 2 cm over their floor."""
    verts, faces = [], []
    for x0, z0, x1, z1, y in boxes:
        b = len(verts)
        verts += [[x0, y + 0.02, z0], [x1, y + 0.02, z0], [x1, y + 0.02, z1], [x0, y + 0.02, z1]]
        faces.append([b, b + 3, b + 2, b + 1])
    return {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': {'vertices': 256, 'triangles': 128},
            'materials': {'wash': {'color': '#2e4658', 'blend': 'add'}}, 'lighting': {'bake': False},
            'nodes': [{'id': 'wash', 'op': 'mesh', 'material': 'wash', 'vertices': verts, 'faces': faces}]}


def cart(eye, draws):
    lines = ['// Written by carts/afterhours/rooms/aq_hall/capture.py.', 'cart "Room capture"', 'import "roompack.akr"',
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


def find_recipe(room_dir, name):
    for d in (room_dir / 'dressed', room_dir, room_dir / 'greybox'):
        p = d / f'{name}.asset.json'
        if p.exists():
            return p
    sys.exit(f'no recipe {name} in {room_dir}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('room', choices=sorted(SHOTS))
    ap.add_argument('--build-dir', default='build-ah-R1')
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--shots', help='comma-separated shot names (default: all)')
    args = ap.parse_args()
    room_dir = ROOMS / args.room
    build = ROOT / args.build_dir
    tools = {'meic': build / 'meic', 'run': build / 'mei-headless'}
    out = build / 'afterhours-capture' / args.room
    if out.exists():
        shutil.rmtree(out)
    src = out / 'recipes'
    src.mkdir(parents=True)
    draft = room_dir / 'dressed' / 'draft.placements.json'
    pfile = draft if draft.exists() else room_dir / f'{args.room}.placements.json'
    placements = json.loads(pfile.read_text())['placements']
    play = json.loads((room_dir / f'{args.room}.play.json').read_text())
    names = sorted({p['asset'] for p in placements})
    for n in names:
        p = find_recipe(room_dir, n)
        shutil.copy(p, src / p.name)
        if (p.parent / 'art').exists() and not (src / 'art').exists():
            shutil.copytree(p.parent / 'art', src / 'art')
    kit = [sys.executable, ROOT / 'tools' / 'mei_assets.py']
    numbers = {'checks': {}}
    if args.verify:
        for n in names:
            res = subprocess.run([str(a) for a in kit + ['verify', src / f'{n}.asset.json', '-o', out / f'verify_{n}',
                                                          '--build-dir', build, '--json']], capture_output=True, text=True, cwd=ROOT)
            try:
                rep = json.loads(res.stdout)
            except json.JSONDecodeError:
                sys.exit(f'verify {n} failed:\n{res.stdout[-2000:]}\n{res.stderr[-2000:]}')
            numbers['checks'][n] = rep.get('verdict')
            print(f'verify {n}: {rep.get("verdict")}')
            for line in rep.get('failures', []):
                print('   ', line)
    ents = {e['id']: e for e in play['entities']}
    rm = next(e for e in play['entities'] if e['type'] == 'room')
    upper = rm['params'].get('upper', 0.0)
    dark = rm['params'].get('dark', False)
    lights = [e for e in play['entities'] if e['type'] == 'light']
    shots = SHOTS[args.room]
    wanted = args.shots.split(',') if args.shots else list(shots)
    extra, stands = [], {}
    for sname in wanted:
        sc = shots[sname]
        stand = []
        on = []
        for e in lights:
            lid = e['id'].split('light_', 1)[1]
            steady = 'period' not in e['params']
            if (sc['lights'] is None and steady) or (sc['lights'] is not None and lid in sc['lights']):
                (x, _, z), (sx, _, sz) = e['position'], e['params']['size']
                lvl = e['params'].get('level', 0)
                on.append((x - sx / 2, z - sz / 2, x + sx / 2, z + sz / 2, upper if lvl else 0.0, lvl))
        if dark and on:
            extra.append(wash_recipe(f'wash_{sname}', [b[:5] for b in on]))
            stand.append((f'ASSET_WASH_{sname.upper()}', (0, 0, 0), 0.0))
        for k, (gid, at_, look) in enumerate(sc['guards']):
            g = ents[gid]
            gp = g['params']
            lvl = gp.get('level', 0)
            y = upper if lvl else 0.0
            gx, gz = at_ if at_ else (g['position'][0], g['position'][2])
            lit = None
            if dark and not gp.get('torch'):
                lit = [b[:4] for b in on if b[5] == lvl]
            cname = f'cone_{sname}_{k}'
            extra.append(cone_recipe(cname, gx, gz, y, look, gp['sight'], gp['fov'], walls(play, lvl), lit))
            stand.append((f'ASSET_{cname.upper()}', (0, 0, 0), 0.0))
            if gp.get('kind') != 'camera':
                stand.append(('ASSET_STANDIN_GUARD', (gx, y, gz), math.radians(look + 180)))
        tx, tzz, th = sc['thief']
        stand.append(('ASSET_STANDIN_THIEF', (tx, upper if sc['level'] else 0.0, tzz), math.radians(th + 180)))
        stands[sname] = stand
    for rec in extra:
        (src / f'{rec["name"]}.asset.json').write_text(json.dumps(rec))
    for n in ('standin_thief', 'standin_guard'):
        shutil.copy(AQ / f'{n}.asset.json', src / f'{n}.asset.json')
    run(kit + ['pack'] + [src / f'{n}.asset.json' for n in names + ['standin_thief', 'standin_guard'] + [r['name'] for r in extra]] +
        ['-o', out / 'pack', '--name', 'roompack', '--slots', '0-14', '--palette', '0', '--palette8', '14'])
    pack = json.loads((out / 'pack' / 'roompack.pack.json').read_text())
    numbers['assets'] = {a['name']: {'triangles': a.get('triangles'), 'vertices': a.get('vertices')}
                         for a in pack.get('assets', []) if a.get('name') in names}
    for f in (out / 'pack').iterdir():
        shutil.copy(f, out / f.name)

    cz, sz = rm['position'][2], rm['params']['size'][2]
    lo, hi = tz_for(cz - sz / 2, FRONT_Y), tz_for(cz + sz / 2, BACK_Y, upper)
    tz = (lo + hi) / 2 if hi <= lo else lo
    sx = rm['params']['size'][0]
    pans = [('c', 0.0)] if sx / 2 <= HALF_VIEW else [('w', -(sx / 2 - HALF_VIEW)), ('c', 0.0), ('e', sx / 2 - HALF_VIEW)]
    placed = [(f'ASSET_{p["asset"].upper()}', tuple(p['position']), 0.0) for p in placements]
    count = {}
    for p in placements:
        count[p['asset']] = count.get(p['asset'], 0) + 1
    numbers['room_triangles'] = sum(numbers['assets'][a]['triangles'] * k for a, k in count.items())
    shots_dir = room_dir / 'shots'
    shots_dir.mkdir(exist_ok=True)
    numbers['camera'] = {'target_z': round(tz, 3), 'pans': {}}
    for tag, px in pans:
        eye = eye_for(px, tz)
        numbers['camera']['pans'][tag] = [round(c, 3) for c in eye]
        img, st = shoot(tools, out, f'room_{tag}', cart(eye, placed))
        numbers[f'room_{tag}'] = st
    for sname in wanted:
        fulls = []
        for tag, px in pans:
            eye = eye_for(px, tz)
            img, st = shoot(tools, out, f'full_{sname}_{tag}', cart(eye, placed + stands[sname]))
            numbers[f'full_{sname}_{tag}'] = st
            fulls.append(img)
            if tag == 'c':
                img.save(shots_dir / f'{args.room}_{sname}.png')
                img.resize((960, 720), Image.NEAREST).save(shots_dir / f'{args.room}_{sname}_x3.png')
        if len(fulls) > 1:
            sheet = Image.new('RGB', (960 * len(fulls) + 8 * (len(fulls) - 1), 720), VOID)
            for k, img in enumerate(fulls):
                sheet.paste(img.resize((960, 720), Image.NEAREST), (k * 968, 0))
            sheet.save(shots_dir / f'{args.room}_{sname}_pan_x3.png')
    (shots_dir / 'numbers.json').write_text(json.dumps(numbers, indent=1) + '\n')
    for key in sorted(k for k in numbers if k.startswith(('room_', 'full_')) and k != 'room_triangles'):
        s = numbers[key]
        print(f'{key}: tris drawn {s.get("tris")}, cpu {s.get("cpu_cycles")}, gpu {s.get("gpu_cycles")}')
    print(f'room triangles (placed): {numbers["room_triangles"]}; per asset {numbers["assets"]}')


if __name__ == '__main__':
    main()
