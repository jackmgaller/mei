#!/usr/bin/env python3
"""Level 1's solutions, one per room, played on the rules' model (levels/rules_model.py) and
written as the cart's solution tapes.

    python3 carts/dorobo/levels/level1/solutions.py [--check] [--pictures DIR]

Each room's plan is played on that room's play file (its own frame: the level only moves rooms,
so a tape is the same there), from the room's clock 0. The tapes go to
carts/dorobo/tests/tapes/level1_solution.akr, one const per room, SOLUTION_L1_<ROOM>. ROUTE.md
and each room's PLAN.md tell the solutions in words.

--check     only play the plans and print how each ends and how near each watcher came (metres
            from the thief's centre to the fan); write nothing
--pictures  also draw each plan from above every second into DIR (needs Pillow)

The model is not the cart: check the tapes in the cart afterwards (NOTES_B.md says how).
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOROBO = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent))
import planner as PL  # noqa: E402
import rules_model as S  # noqa: E402

G, H = PL.guard, PL.heading
TAPES = DOROBO / 'tests' / 'tapes' / 'level1_solution.akr'


def target(sim, gid, wp):
    return G(sim, gid)['target'] == sim.wp_index[wp]


def facing(sim, gid, deg, within=20):
    return abs((H(sim, gid) - deg + 180) % 360 - 180) < within


# Room 1, the last train: off the train, along the platform to where the guard's cone ends; when
# he turns to the timetable, up to the stair.
ARRIVAL = [
    ('go', -1.0, 0.3),
    ('until', lambda s: H(s, 'r1_guard') < 230),
    ('go', 3.2, -0.2),
]

# Room 2, the ticket gates: into the lockers' alcove and hide (A) before the guard comes through
# the gates; when he has looked at the lockers and is walking back east, out, through the gates
# by the front aisle, and up to the passage.
GATES = [
    ('go', -4.5, 3.0), ('go', -4.5, 3.8), ('press', 'A'),
    ('until', lambda s: target(s, 'r2_guard', 'r2_wp_back_e') and G(s, 'r2_guard')['x'] > -1.0),
    ('go', -4.5, 3.0), ('go', -1.0, -2.05), ('go', 1.0, -2.05), ('go', 6.2, -2.6),
]

# Room 3, the passage: along the front to where the camera's sweep ends; when it looks along the
# back, on to the shadow of the last pillar; when it looks along the back again, on to the door
# under the camera.
PASSAGE = [
    ('go', -3.0, -2.9),
    ('until', lambda s: H(s, 'r3_camera') > 280),
    ('go', 4.6, -2.3),
    ('until', lambda s: H(s, 'r3_camera') > 280),
    ('go', 10.7, -2.6),
]

# Room 4, the lobby: when the west guard has turned back north, across behind him to the desk's
# east side; when the back guard is at an end of his walk looking away, round the desk and up to
# the escalator's foot.
LOBBY = [
    ('until', lambda s: target(s, 'r4_guard_west', 'r4_wp_west_n') and G(s, 'r4_guard_west')['z'] > -1.5),
    ('go', -2.0, -3.6), ('go', 2.2, -1.1),
    ('until', lambda s: (target(s, 'r4_guard_back', 'r4_wp_back_w') and G(s, 'r4_guard_back')['x'] < -1.5)
                        or (target(s, 'r4_guard_back', 'r4_wp_back_e') and G(s, 'r4_guard_back')['x'] > 3.0)),
    ('go', 2.2, 1.0), ('go', 0.55, 1.0), ('go', 0.55, 4.1),
]

# Room 5, the aquarium: along the front to the pillar while the watchman looks at the fish; in the
# pillar's shadow until he looks at the fish again and the keeper is on the cube's far side walking
# west; then along the front and up the east wall to the staff door.
AQUARIUM = [
    ('go', -2.0, -2.4),
    ('until', lambda s: facing(s, 'r5_guard_watchman', 0)),
    ('go', -0.2, -2.45),
    ('until', lambda s: facing(s, 'r5_guard_watchman', 0) and target(s, 'r5_guard_keeper', 'r5_wp_cube_nw')
                        and G(s, 'r5_guard_keeper')['x'] < 4.3),
    ('go', 1.4, -1.65), ('go', 5.35, -1.65), ('go', 5.35, 2.45),
]

ROOMS = [
    ('ARRIVAL', 'rooms/arrival/arrival.play.json', ARRIVAL, 'Room 1, the last train'),
    ('GATES', 'rooms/gates/gates.play.json', GATES, 'Room 2, the ticket gates'),
    ('PASSAGE', 'rooms/passage/passage.play.json', PASSAGE, 'Room 3, the passage'),
    ('LOBBY', 'rooms/lobby/lobby.play.json', LOBBY, 'Room 4, the lobby'),
    ('AQUARIUM', 'levels/level1/aquarium/aquarium.play.json', AQUARIUM, 'Room 5, the aquarium'),
]

HEADER = """\
// Written by carts/dorobo/levels/level1/solutions.py - do not edit; change the plans there.
// Level 1's solution tapes (agent B's), one per room, each from that room's clock 0. Spans as
// dr_tape.akr describes them (ticks, buttons held, the stick). Each reaches its room's exit
// unseen. Drafted on a model of the rules (levels/rules_model.py) and checked in the cart; if a
// room, its watchers or the rules change, redraft them and check again.
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--pictures', metavar='DIR')
    args = ap.parse_args()
    out = [HEADER]
    ok = True
    for const, play, steps, what in ROOMS:
        sim = S.Sim(play=DOROBO / play)
        r = PL.play(steps, sim, frames=range(0, 7200, 60) if args.pictures else ())
        near = ', '.join(f'{k} {m:.2f} m at {t}' for k, (m, t) in sorted(r['margins'].items(), key=lambda kv: kv[1][0]))
        print(f'SOLUTION_L1_{const}: {r["result"]}; nearest: {near}')
        ok &= bool(r['result']) and r['result'][0] == 'cleared'
        if args.pictures:
            PL.sheet(r['shots'], Path(args.pictures) / f'l1_{const.lower()}.png', cols=6)
        if r['result']:
            out += PL.tape_lines(f'SOLUTION_L1_{const}', r['inputs'],
                                 f'{what}. The model clears it on tick {r["result"][1]}.')
    if not ok:
        sys.exit('a plan does not clear its room: the tapes were not written')
    if not args.check:
        text = '\n'.join(out)
        if not TAPES.exists() or TAPES.read_text() != text:
            TAPES.write_text(text)
            print('wrote', TAPES.relative_to(DOROBO))


if __name__ == '__main__':
    main()
