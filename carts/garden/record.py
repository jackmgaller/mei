#!/usr/bin/env python3
"""Reads a play recording of the movement garden (record.akr's lines, the emulator's stdout) and
writes it with names: the placements stood on and walked into, the entities nearby and the sounds.

    build-st/mei build-st/carts/garden.mei                   # play; quit to end the recording
    python3 carts/garden/record.py --build-dir build-st      # the newest run's log
    python3 carts/garden/record.py LOG --build-dir build-st  # or a log named (a run's, or stdout kept)

The desktop emulator keeps each run's debug output in runs/mei-DATE-TIME.log in its preferences
folder (~/Library/Application Support/gallerdude/Mei/ on macOS), so every session is recorded.

Writes, beside the log (or into -o DIR):
  run.csv          a row every 6 frames (10 a second): the player, the camera, the floor, the zone,
                   the sounds since the row before, the walls around and the entities near
  run.timeline.txt the same as text, with the events (state changes, sounds, zones, coins) between
  run.summary.txt  time in each state and zone, distance, the placements stood on, the sounds

The names come from the built world's report (BUILD/worlds/carts/garden/shrinetown/report.json:
each cell's collision tags and the entity numbers), the game's GARDEN_TYPE_ constants and the
sound table (carts/garden/audio/sound_data.akr), so use the build directory the cart was built in.
"""
import argparse
import collections
import csv
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FPS = 60
RUNS = Path.home() / 'Library' / 'Application Support' / 'gallerdude' / 'Mei' / 'runs'
DIRS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']


def names(build):
    world = Path(build) / 'worlds' / 'carts' / 'garden' / 'shrinetown'
    report = json.loads((world / 'report.json').read_text())
    tags = {}
    for c in report['cells']:
        i, j = c['at']
        for t, name in c['collision'].get('placement_tags', {}).items():
            tags[(i, j, int(t))] = name
    ents = {v['number']: k for k, v in report['entities'].items()}
    types = {}
    for m in re.finditer(r'const GARDEN_TYPE_([A-Z_]+) = (\d+)', (world / 'garden.game.akr').read_text()):
        types[int(m.group(2))] = m.group(1).lower()
    sounds = {}
    for m in re.finditer(r'const GA_S_([A-Z0-9_]+) = (\d+)', (HERE / 'audio' / 'sound_data.akr').read_text()):
        sounds[int(m.group(2))] = m.group(1).lower()
    text = (HERE / 'player.akr').read_text()
    body = text[text.index('const ST_NAMES'):]
    states = re.findall(r'"([^"]*)"', body[:body.index(']\n')])
    return tags, ents, types, sounds, states


def num(s):
    return None if s == '-' else float(s)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('log', nargs='?', help='the log (default: the newest in RUNS)')
    ap.add_argument('--build-dir', default='build')
    ap.add_argument('-o', '--out', help='directory for the outputs (default: beside the log)')
    a = ap.parse_args()
    tags, ents, types, sounds, states = names(a.build_dir)
    if a.log:
        log = Path(a.log)
    else:
        logs = sorted(RUNS.glob('mei-*.log'), key=lambda q: q.stat().st_mtime)
        if not logs:
            raise SystemExit(f'no run logs in {RUNS}: name a log')
        log = logs[-1]
    out = Path(a.out) if a.out else log.parent
    out.mkdir(parents=True, exist_ok=True)
    stem = log.stem

    def placement(i, j, t):
        if t < 0:
            return ''
        return tags.get((i, j, t), f'cell {i},{j} tag {t}')

    rows, timeline = [], []
    walls = {}                  # dir -> (dist, name), the latest
    near, near_f = [], -1       # the latest batch of entities
    sounds_since = []
    zone = region = ''
    st_ticks = collections.Counter()
    zone_ticks = collections.Counter()
    stood = collections.Counter()
    heard = collections.Counter()
    events = 0
    last = None
    dist = 0.0
    cam = None
    for line in log.read_text(errors='replace').splitlines():
        w = line.split(' ')
        if len(w) < 2 or not w[1].lstrip('-').isdigit() or len(w[0]) != 1:
            continue
        k, f = w[0], int(w[1])
        t = f / FPS
        if k == 'E':
            timeline.append(f'{t:8.2f}  state {states[int(w[2])]} -> {states[int(w[3])]}')
            events += 1
        elif k == 'S':
            n = sounds.get(int(w[2]), f'sound {w[2]}')
            sounds_since.append(n)
            heard[n] += 1
            timeline.append(f'{t:8.2f}  sound {n}')
        elif k == 'L':
            n = 'none' if int(w[2]) < 0 else sounds.get(int(w[2]), w[2])
            timeline.append(f'{t:8.2f}  loop {n}')
        elif k == 'Z':
            zone = ' '.join(w[2:])
            timeline.append(f'{t:8.2f}  zone "{zone}"')
        elif k == 'G':
            region = w[2]
            timeline.append(f'{t:8.2f}  region {region}')
        elif k == 'K':
            timeline.append(f'{t:8.2f}  coins {w[2]}, red coins {w[3]}, stars {w[4]}')
        elif k == 'W':
            d = int(w[2])
            dd = float(w[3])
            walls[d] = None if dd < 0 else (dd, placement(int(w[4]), int(w[5]), int(w[6])))
        elif k == 'N':
            if f != near_f:
                near, near_f = [], f
            n = int(w[3])
            near.append((float(w[4]), ents.get(n, f'entity {n}'), types.get(int(w[2]), w[2])))
        elif k == 'C':
            cam = [float(v) for v in w[2:10]] + [int(w[10])] + [float(v) for v in w[11:14]]
        elif k == 'P':
            w[2] = states[int(w[2])]
            x, y, z = float(w[3]), float(w[4]), float(w[5])
            vx, vy, vz = float(w[6]), float(w[7]), float(w[8])
            fy = num(w[16])
            on = placement(int(w[17]), int(w[18]), int(w[19])) if fy is not None else ''
            if last is not None:
                dist += math.dist((x, y, z), last)
                st_ticks[rows[-1]['state']] += f - rows[-1]['frame']
                zone_ticks[rows[-1]['zone']] += f - rows[-1]['frame']
            last = (x, y, z)
            if on and w[2] in ('ground', 'skid', 'crouch', 'crouch slide'):
                stood[on] += 1
            wall_s = '; '.join(f'{DIRS[d]} {v[1] or "?"} {v[0]:.1f}' for d, v in sorted(walls.items()) if v)
            near_s = '; '.join(f'{n} ({ty}) {d:.1f}' for d, n, ty in sorted(near))
            row = {'frame': f, 'time': round(t, 2), 'state': w[2], 'x': x, 'y': y, 'z': z,
                   'vx': vx, 'vy': vy, 'vz': vz, 'hspeed': round(math.hypot(vx, vz), 3),
                   'yaw': float(w[9]), 'fwd': float(w[10]), 'pad': w[11], 'stick_x': float(w[12]),
                   'stick_y': float(w[13]), 'surf': int(w[14]), 'surf_byte': int(w[15]),
                   'floor_y': fy, 'standing_on': on, 'zone': zone, 'region': region,
                   'sounds': ' '.join(sounds_since), 'walls': wall_s, 'near': near_s}
            if cam:
                row.update({'cam_x': cam[0], 'cam_y': cam[1], 'cam_z': cam[2], 'look_x': cam[3],
                            'look_y': cam[4], 'look_z': cam[5], 'cam_yaw': cam[6], 'cam_pitch': cam[7],
                            'cam_zone': cam[8], 'cam_zone_w': cam[9], 'cam_reach': cam[10],
                            'cam_squeeze': cam[11]})
            rows.append(row)
            sounds_since = []
            timeline.append(f'{t:8.2f}  {w[2]:<12} at ({x:.1f}, {y:.1f}, {z:.1f})  {math.hypot(vx, vz):5.1f} m/s'
                            f'  vy {vy:5.1f}  on {on or "-"}' + (f'  cam ({cam[0]:.1f}, {cam[1]:.1f}, {cam[2]:.1f})'
                                                                 f' yaw {cam[6]:.2f}' if cam else ''))
    if not rows:
        raise SystemExit(f'{log}: no recorder lines (P ...): was it the garden cart, built with record.akr?')
    fields = list(rows[-1].keys())
    with open(out / f'{stem}.csv', 'w', newline='') as fh:
        wr = csv.DictWriter(fh, fieldnames=fields)
        wr.writeheader()
        wr.writerows(rows)
    (out / f'{stem}.timeline.txt').write_text('\n'.join(timeline) + '\n')
    dur = rows[-1]['frame'] / FPS
    s = [f'{log.name}: {dur:.1f} s ({rows[-1]["frame"]} frames), {dist:.0f} m travelled, {events} state changes',
         '', 'Time in each state:']
    s += [f'  {k:<14} {v / FPS:7.1f} s' for k, v in st_ticks.most_common()]
    s += ['', 'Time in each sound zone:'] + [f'  {k or "-":<28} {v / FPS:7.1f} s' for k, v in zone_ticks.most_common()]
    s += ['', 'Placements stood on (rows on the ground):'] + [f'  {k:<32} {v}' for k, v in stood.most_common(30)]
    s += ['', 'Sounds started:'] + [f'  {k:<24} {v}' for k, v in heard.most_common()]
    (out / f'{stem}.summary.txt').write_text('\n'.join(s) + '\n')
    print('\n'.join(s[:1]))
    print(f'wrote {out / (stem + ".csv")}, {stem}.timeline.txt, {stem}.summary.txt')


if __name__ == '__main__':
    main()
