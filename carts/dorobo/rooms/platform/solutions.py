#!/usr/bin/env python3
"""The platform's solutions, played on the rules' model (rules_model.py), written as the cart's
solution tapes.

    python3 carts/dorobo/rooms/platform/solutions.py [--check] [--pictures DIR]

Each solution is a plan: walk to a point, wait until something in the room is so (a guard has
passed, a train's doors are open), press a button. The plan is played on the model tick by tick,
which turns it into the pad and stick of every tick; those are written, run-length coded, to
carts/dorobo/tests/tapes/platform_solution.akr as dr_tape.akr's spans. PUZZLE.md tells the same
solutions in words.

--check     only play the plans and print how each ends and how near each watcher came (metres
            between the thief's footprint and the fan); write nothing
--pictures  also draw each plan from above every 2 s into DIR (needs Pillow)

The rules' model is shared with level 1 (carts/dorobo/levels/rules_model.py). The model is not the cart: check the tapes in the cart afterwards (tests/run.sh 1, NOTES_B.md).
"""
import argparse
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
import rules_model as S  # noqa: E402

TAPES = HERE.parents[1] / 'tests' / 'tapes' / 'platform_solution.akr'
NAMES = ['UP', 'DOWN', 'LEFT', 'RIGHT', 'A', 'B', 'X', 'Y', 'L', 'R']


# ---- what the plans ask of the room

def guard(sim, gid):
    return sim.guards[[w['id'] for w in sim.watch].index(gid)]


def heading(sim, gid):
    return math.degrees(guard(sim, gid)['head']) % 360


def doors_open(sim, k):
    return sim.tstate[k]['open']


TRAIN_A, TRAIN_B = 0, 1     # in the world's entity order

# ---- the plans

# The start: into the nook behind the stair while the platform patrol walks to it, out when he has
# turned up the platform's far side.
START = [
    ('go', 2.2, 7.15),
    ('until', lambda s: guard(s, 'guard_platform')['x'] > 7.5 and guard(s, 'guard_platform')['z'] > 6.5),
]

# The end: through train B's last door onto the walkway behind the walkway guard (who walks east),
# into the cupboard before he turns at the walkway's end, out when he has gone back past it, and
# along to the staff door.
CUPBOARD_END = [
    ('go', 22.08, 10.35),
    ('go', 25.0, 10.8), ('go', 25.0, 11.6), ('press', 'A'),
    ('until', lambda s: guard(s, 'guard_walkway')['x'] < 23.5),
    ('go', 25.0, 10.8), ('go', 29.5, 10.8),
]

# Solution 1, the trains: in at train A's second door when the posted guard looks east, along
# inside it (cones see in only through its open doors) to between its last two doors, where none
# reaches; when the posted guard looks west, out at its last door, between the bench and pillar 4
# to train B's last door, which opens on both sides.
TRAINS = START + [
    ('go', 4.6, 6.9), ('go', 6.0, 4.6), ('go', 9.8, 3.75),
    ('until', lambda s: doors_open(s, TRAIN_A) and abs(heading(s, 'guard_kiosk') - 110) < 1),
    ('go', 10.5, 3.75), ('go', 10.5, 2.2), ('go', 13.0, 2.2),
    ('go', 19.4, 2.2),
    ('until', lambda s: abs(heading(s, 'guard_kiosk') - 250) < 1),
    ('go', 20.5, 2.2), ('go', 20.5, 3.8), ('go', 21.95, 4.6), ('go', 22.07, 7.0),
    ('until', lambda s: doors_open(s, TRAIN_B)),
] + CUPBOARD_END

# Solution 2, on foot: behind the platform patrol along the far side, into the kiosk (a hiding
# place) out of the camera's sweep, out as train B comes in and blinds the camera, to train B's
# last door.
ON_FOOT = START + [
    ('go', 4.6, 6.9), ('go', 9.5, 6.9),
    ('until', lambda s: guard(s, 'guard_platform')['z'] < 4.5 and guard(s, 'guard_platform')['x'] > 13.5),
    ('go', 14.2, 6.8), ('go', 15.5, 6.0), ('press', 'A'),
    ('until', lambda s: s.tstate[TRAIN_B]['phase'] == 'arr' and s.tstate[TRAIN_B]['head'] > 20),
    ('go', 15.5, 6.8), ('go', 17.0, 6.1), ('go', 22.07, 6.6), ('go', 22.07, 7.0),
    ('until', lambda s: doors_open(s, TRAIN_B)),
] + CUPBOARD_END

# Solution 3, the bell: solution 1, with the pocket bell set down at train B's door on the walkway.
# It rings 3 s later and calls the walkway guard back from the walkway's end, past the cupboard,
# so the thief is out 3 s sooner.
BELL = TRAINS[:TRAINS.index(CUPBOARD_END[0])] + [
    ('go', 22.08, 10.35), ('press', 'L'), ('press', 'B'),
    ('go', 25.0, 10.8), ('go', 25.0, 11.6), ('press', 'A'),
    ('until', lambda s: guard(s, 'guard_walkway')['x'] < 24.0),
    ('go', 25.0, 10.8), ('go', 29.5, 10.8),
]

SOLUTIONS = [
    ('SOLUTION_PLATFORM', TRAINS, 'Solution 1, "the trains": along inside train A, through train B, the cupboard'),
    ('SOLUTION_PLATFORM_ON_FOOT', ON_FOOT, 'Solution 2, "on foot": behind the patrol, the kiosk, through train B, the cupboard'),
    ('SOLUTION_PLATFORM_BELL', BELL, 'Solution 3, "the bell": solution 1, with the bell calling the walkway guard back'),
]


# ---- playing a plan

def play(steps, frames=(), limit=6000):
    """Plays a plan on a fresh room. Returns the result, the input of every tick, the nearest each
    watcher's fan came to the thief, and pictures at the given ticks."""
    sim = S.Sim(world=HERE / 'platform.world.json')
    inputs, path, shots, margins = [], [], [], {}
    result = None

    def emit(pad, sx=0, sy=0):
        nonlocal result
        if sim.clock in frames:
            shots.append(draw(sim, path))
        why, cleared = sim.tick(pad, sx, sy)
        inputs.append((pad, sx, sy))
        path.append((sim.th['x'], sim.th['z']))
        if not sim.th['hidden']:
            for g, w in zip(sim.guards, sim.watch):
                m = S.fan_dist(g['fan'], sim.th['x'], sim.th['z']) - (0.0 if S.RULES['centre'] else S.THIEF_R)
                if m < margins.get(w['id'], (99, 0))[0]:
                    margins[w['id']] = (round(m, 2), sim.clock - 1)
        if why:
            result = ('caught', why, sim.clock - 1)
        elif cleared:
            result = ('cleared', sim.clock - 1)
        return result

    for st in steps:
        op = st[0]
        if op == 'until':
            while not st[1](sim):
                if emit(0) or sim.clock > limit:
                    break
        elif op == 'press':
            emit({'A': S.A, 'B': S.B, 'L': S.L}[st[1]])
        elif op == 'go':
            tx, tz = st[1], st[2]
            aim, still = None, 0
            for _ in range(3000):
                dx, dz = tx - sim.th['x'], tz - sim.th['z']
                dd = math.hypot(dx, dz)
                if dd < 0.02:
                    break
                if dd < S.WALK:
                    sx, sy = round(127 * dx / S.WALK), round(127 * dz / S.WALK)
                    if abs(sx) < 27 and abs(sy) < 27:     # inside the stick's dead zone: there
                        break
                    aim = None
                else:
                    # one direction for as long as it passes within 2 cm of the point
                    if aim is not None:
                        n = math.hypot(*aim)
                        ux, uz = aim[0] / n, aim[1] / n
                        if abs(dx * uz - dz * ux) > 0.02 or dx * ux + dz * uz <= 0:
                            aim = None
                    if aim is None:
                        if abs(dx) < 1e-4 or abs(dz) < 1e-4:
                            aim = ((dx > 1e-4) * 127 - (dx < -1e-4) * 127, (dz > 1e-4) * 127 - (dz < -1e-4) * 127)
                        else:
                            aim = (round(127 * dx / dd), round(127 * dz / dd))
                    sx, sy = aim
                x0, z0 = sim.th['x'], sim.th['z']
                if emit(0, sx, sy):
                    break
                still = still + 1 if abs(sim.th['x'] - x0) < 1e-6 and abs(sim.th['z'] - z0) < 1e-6 else 0
                if still >= 3:
                    break     # against something
        if result:
            break
    return dict(result=result, inputs=inputs, margins=margins, shots=shots)


# ---- the tape

def spans(inputs):
    out = []
    for pad, sx, sy in inputs:
        if out and out[-1][1:] == [pad, sx, sy] and out[-1][0] < 65535:
            out[-1][0] += 1
        else:
            out.append([1, pad, sx, sy])
    return out


def pad_name(p):
    names = [NAMES[i] for i in range(10) if p >> i & 1]
    return ' | '.join(names) if names else '0'


HEADER = """\
// Written by carts/dorobo/rooms/platform/solutions.py - do not edit; change the plans there.
// The subway platform's solution tapes (agent B's; carts/dorobo/rooms/platform/PUZZLE.md tells
// the solutions in words). Spans as dr_tape.akr describes them (ticks, buttons held, the stick),
// from the room clock's 0 of a fresh attempt. Each reaches the staff door unseen. They are drafted
// on a model of the rules and checked in the cart (tests/run.sh 1); if the room, the timetables
// or the rules change, redraft them and check again.
//
// SOLUTION_PLATFORM is the one tests/check.sh plays; the other two are the room's other
// solutions, kept so that a change which closes one of them shows.
"""


def tape_text(results):
    out = [HEADER]
    for (const, _steps, what), r in zip(SOLUTIONS, results):
        # walk on toward the door's middle for half a second: the cart's fixed point lands the
        # thief a few centimetres from the model's position
        sp = spans(r['inputs'] + [(S.RIGHT, 0, 0)] * 30)
        out.append(f'// {what}. The model clears it on tick {r["result"][1]}.')
        out.append(f'const {const}: [{len(sp)}]Span = [')
        out += [f'    Span {{ n: {n}, pad: {pad_name(p)}, sx: {sx}, sy: {sy} }},' for n, p, sx, sy in sp]
        out.append(']\n')
    return '\n'.join(out)


# ---- pictures

def draw(sim, path):
    from PIL import Image, ImageDraw
    px = 28

    def at(x, z):
        return (x * px, (13.0 - z) * px)
    im = Image.new('RGB', (32 * px, 13 * px), (20, 22, 28))
    d = ImageDraw.Draw(im, 'RGBA')
    d.rectangle([*at(1, 7.6), *at(31, 3.4)], fill=(120, 124, 132))
    d.rectangle([*at(1, 11.2), *at(31, 10.0)], fill=(105, 108, 116))
    for b in sim.walls:
        col = (40, 40, 44) if b.edge else (60, 66, 80) if b.blocks else (150, 120, 90)
        d.polygon([at(*p) for p in b.corners()], fill=col)
    for s in sim.spots:
        d.polygon([at(*p) for p in s.corners()], outline=(80, 120, 220))
    d.polygon([at(*p) for p in sim.exit.corners()], outline=(80, 220, 120))
    for tr, st in zip(sim.trains, sim.tstate):
        for c in st['cars']:
            b = tr.car_box(c, -c['len'] / 2, c['len'] / 2, -tr.width / 2, tr.width / 2)
            d.polygon([at(*p) for p in b.corners()], fill=(200, 190, 120, 120 if st['open'] else 200))
    for b in sim.dyn_boxes:
        d.polygon([at(*p) for p in b.corners()], fill=(240, 230, 150))
    for g, w in zip(sim.guards, sim.watch):
        ax, az, pts = g['fan']
        d.polygon([at(ax, az)] + [at(*p) for p in pts], fill=(255, 240, 120, 70), outline=(255, 240, 120, 160))
        x, y = at(g['x'], g['z'])
        d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(160, 160, 255) if w['kind'] == 'camera' else (220, 60, 60))
    if len(path) > 1:
        d.line([at(*p) for p in path], fill=(255, 140, 0, 160), width=2)
    x, y = at(sim.th['x'], sim.th['z'])
    d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(120, 70, 0) if sim.th['hidden'] else (255, 140, 0))
    d.text((6, 4), f't = {sim.clock} ({sim.clock / 60:.1f} s)', fill=(255, 255, 255))
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='play the plans only; write nothing')
    ap.add_argument('--pictures', metavar='DIR', help='draw each plan from above every 2 s')
    args = ap.parse_args()
    results = []
    ok = True
    for const, steps, what in SOLUTIONS:
        r = play(steps, frames=range(0, 6000, 120) if args.pictures else ())
        results.append(r)
        near = ', '.join(f'{k} {m:.2f} m at {t}' for k, (m, t) in sorted(r['margins'].items(), key=lambda kv: kv[1][0]))
        print(f'{const}: {r["result"]}; nearest: {near}')
        ok &= bool(r['result']) and r['result'][0] == 'cleared'
        if args.pictures and r['shots']:
            from PIL import Image
            out = Path(args.pictures)
            out.mkdir(parents=True, exist_ok=True)
            w, h = r['shots'][0].size
            cols, rows = 3, (len(r['shots']) + 2) // 3
            sheet = Image.new('RGB', (w * cols, h * rows))
            for i, s in enumerate(r['shots']):
                sheet.paste(s, ((i % cols) * w, (i // cols) * h))
            sheet.save(out / f'{const.lower()}.png')
    if not ok:
        sys.exit('a plan does not clear the room: the tapes were not written')
    if not args.check:
        text = tape_text(results)
        if not TAPES.exists() or TAPES.read_text() != text:
            TAPES.parent.mkdir(parents=True, exist_ok=True)
            TAPES.write_text(text)
            print('wrote', TAPES.relative_to(HERE.parents[3]))


if __name__ == '__main__':
    main()
