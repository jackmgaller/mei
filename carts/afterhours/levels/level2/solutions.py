#!/usr/bin/env python3
"""Stage 2's solution: the stage's eight legs in play order, played on the rules' model
(levels/rules_model.py) with the run's cards and opened doors carried from leg to leg, and
written as the cart's solution tapes.

    python3 carts/afterhours/levels/level2/solutions.py [--check] [--pictures DIR]

A leg is one visit to a room: from the spawn of the door he came in by (the stage's start, for
the first), at the room's clock 0, out by a door. Each leg's plan is played on its room's play
file (its own frame: the stage only moves rooms, so a tape is the same there). The tapes go to
carts/afterhours/tests/tapes/level2_solution.akr: SOLUTION_S2_LEG_0 .. 7, with S2_LEG_ROOM (each
leg's room, numbered in the rooms' `next` order) and S2_LEG_DOOR (the door it leaves by, the
index among its room's doors in entity order). ROUTE.md and each room's PLAN.md tell the
solutions in words.

--check     only play the legs and print how each ends and how near each watcher came (metres
            from the thief's centre to the fan); write nothing
--pictures  also draw each leg from above every second into DIR (needs Pillow)

The model is not the cart: check the tapes in the cart afterwards (NOTES_B.md says how).
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CART = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent))
import planner as PL  # noqa: E402
import rules_model as S  # noqa: E402

G, H = PL.guard, PL.heading
TAPES = CART / 'tests' / 'tapes' / 'level2_solution.akr'

# The rooms in their `next` order (make_level2.py's ROOMS): the tapes number rooms by it.
ORDER = ['cinema', 'booth', 'corridor', 'shopfloor', 'foodhall']


def target(sim, gid, wp):
    return G(sim, gid)['target'] == sim.wp_index[wp]


def cycle(period, at):
    """True on the tick the room's clock is `at` ticks into a cycle of `period`."""
    return lambda s: s.clock % period == at


# ---- the plans

# 1. The cinema, from behind the screen: out of the gap at the back of the screen while the
# usher walks down the front, along the back aisle to the first cross aisle (out of the
# cleaner's reach); when the cleaner sets off back down his aisle, along the back to the staff
# door. The projector's window covers the middle aisle the whole time.
CINEMA = [
    ('until', lambda s: target(s, 'cn_guard_usher', 'cn_wp_usher_sw') and G(s, 'cn_guard_usher')['z'] < 1.5),
    ('go', -10.0, 4.05), ('go', -3.6, 3.9),
    ('until', lambda s: target(s, 'cn_guard_cleaner', 'cn_wp_cleaner_s') and G(s, 'cn_guard_cleaner')['z'] < 1.0),
    ('go', 10.0, 3.2), ('go', 11.2, 3.2),
]

# The corridor's office guard turns his head every 480 ticks: from 0 he looks west out of his
# window (to 90), turns east (to 240), looks east (to 330), turns back (to 480). The column in
# the back lane, straight out from his window, has a shadow he never sees into.
OFFICE = 480

# 2. The corridor, cinema door to the stair: behind the porter along the front of the cages; up
# the west side of the office when the porter has turned the far corner; into the column's
# shadow while the office guard looks east; on to the stair door while he looks west and the
# stair camera looks away.
CORRIDOR_1 = [
    ('go', -5.6, -2.4),
    ('until', lambda s: target(s, 'sc_guard_porter', 'sc_wp_porter_ne') and G(s, 'sc_guard_porter')['z'] > 0.0),
    ('go', -2.2, -2.4), ('go', -2.2, 0.6),
    ('until', lambda s: target(s, 'sc_guard_porter', 'sc_wp_porter_nw') and 225 <= s.clock % OFFICE < 300),
    ('go', 1.5, 3.1),
    ('until', cycle(OFFICE, 0)),
    ('go', 8.0, 2.0), ('go', 12.9, 2.0),
]

# 3. The shop floor, for the blue card: down the west end and along the front while the night
# guard is on his way round the back; at the watch counter's end, in when the camera has swung
# to the lift, out with the card and back the way he came before the guard comes down the east
# end.
SHOP_1 = [
    ('go', -10.0, 2.2), ('go', -10.0, -3.7), ('go', 7.0, -3.7),
    ('until', cycle(420, 160)),
    ('go', 9.6, -3.75),
    ('go', -10.0, -3.7), ('go', -10.0, 2.2), ('go', -12.6, 2.2),
]

# 4. The corridor, stair to the blue door: along the east end to the pallets' corner while the
# office guard looks west; into the column's shadow as he turns back west; out of it while he
# looks east, round the office's west side and behind the porter to the blue door, which opens.
CORRIDOR_2 = [
    ('go', 4.6, 3.0),
    ('until', cycle(OFFICE, 470)),
    ('go', 1.5, 3.1),
    ('until', cycle(OFFICE, 235)),
    ('go', -2.0, 2.6),
    ('until', lambda s: target(s, 'sc_guard_porter', 'sc_wp_porter_nw') and G(s, 'sc_guard_porter')['x'] < -7.0),
    ('go', -6.0, 2.6), ('go', -6.0, 3.9),
]

# 5. The booth, for the red card: when the projectionist has gone up the far end, along the
# front of the machines; up the far end behind him as he walks back along the bench, over the
# card, and into the west machine's shadow; when he is walking down the front again, back along
# the bench and down to the door.
BOOTH = [
    ('until', lambda s: target(s, 'pb_guard_projectionist', 'pb_wp_proj_c') and G(s, 'pb_guard_projectionist')['z'] > -0.8),
    ('go', 0.0, -2.4), ('go', -5.3, -2.4),
    ('until', lambda s: target(s, 'pb_guard_projectionist', 'pb_wp_proj_d')),
    ('go', -5.3, 1.7), ('go', -4.6, 1.6),
    ('until', lambda s: target(s, 'pb_guard_projectionist', 'pb_wp_proj_b') and G(s, 'pb_guard_projectionist')['x'] < -2.5),
    ('go', 5.0, 1.6), ('go', 5.0, -1.8), ('go', 6.3, -1.8),
]

# 6. The corridor, blue door to the stair: out of the door behind the office guard's eastward
# turn, into the column's shadow; to the pallets' corner while he looks west; on to the stair
# when the camera looks away.
CORRIDOR_3 = [
    ('until', cycle(OFFICE, 100)),
    ('go', -2.4, 2.6), ('go', 1.5, 3.1),
    ('until', cycle(OFFICE, 470)),
    ('go', 4.6, 3.0),
    ('until', cycle(OFFICE, 60)),
    ('go', 8.0, 2.0), ('go', 12.9, 2.0),
]

# 7. The shop floor, to the lift: behind the night guard along the back; when he is down the
# east end, past the mannequin as the camera swings back from the lift, to the red door, which
# opens.
SHOP_2 = [
    ('until', lambda s: target(s, 'sf_guard_night', 'sf_wp_night_ne') and G(s, 'sf_guard_night')['x'] > 0.0),
    ('go', -9.5, 3.6), ('go', 1.0, 3.6),
    ('until', lambda s: target(s, 'sf_guard_night', 'sf_wp_night_se') and s.clock % 420 == 330),
    ('go', 4.2, 3.6), ('go', 6.0, 3.6), ('go', 9.1, 3.9), ('go', 9.1, 5.1),
]

# 8. The food hall, out of the lift: down the west end, round the gift boxes, to the column at
# the front; when the guard at the melon counter has turned to look up the hall, along the
# front, round the second stack of gift boxes, to the shutter door.
FOOD = [
    ('go', -9.7, 2.5), ('go', -10.5, -3.0), ('go', -3.0, -3.0),
    ('until', lambda s: s.clock >= 540 and s.clock % 540 == 80),
    ('go', 7.0, -3.0), ('go', 7.6, -2.45), ('go', 9.7, -2.45), ('go', 11.2, -3.0), ('go', 12.5, -3.0),
]

# The legs in play order: (room, the door he leaves by, the plan, what it is). He comes in by
# the stage's start (the first room's `entry`), then by the door on the other side of the last.
LEGS = [
    ('cinema', 'cn_door_corridor', CINEMA, 'The cinema, from behind the screen to the staff corridor'),
    ('corridor', 'sc_door_shop', CORRIDOR_1, 'The staff corridor, from the cinema to the stair'),
    ('shopfloor', 'sf_door_corridor', SHOP_1, 'The shop floor: the blue card, and back to the stair'),
    ('corridor', 'sc_door_booth', CORRIDOR_2, 'The staff corridor, from the stair to the blue door'),
    ('booth', 'pb_door_corridor', BOOTH, 'The projection booth: the red card, and back to the door'),
    ('corridor', 'sc_door_shop', CORRIDOR_3, 'The staff corridor, from the blue door to the stair'),
    ('shopfloor', 'sf_door_lift', SHOP_2, 'The shop floor, from the stair to the red door and the lift'),
    ('foodhall', 'fh_door_mall', FOOD, 'The food hall, from the lift to the way out'),
]

HEADER = """\
// Written by carts/afterhours/levels/level2/solutions.py - do not edit; change the plans there.
// Stage 2's solution tapes (agent B's): the stage's legs in play order, each from its room's
// clock 0, the run's cards and opened doors carried from leg to leg. Spans as dr_tape.akr
// describes them (ticks, buttons held, the stick). Leg k is played in room S2_LEG_ROOM[k] (the
// rooms numbered in their `next` order: the cinema, the projection booth, the staff corridor,
// the shop floor, the food hall) and leaves it unseen by its door S2_LEG_DOOR[k] (the index
// among the room's doors, in entity order). Drafted on a model of the rules
// (levels/rules_model.py) and checked in the cart; if a room, its watchers or the rules change,
// redraft them and check again.
"""


def play_file(room):
    return CART / 'rooms' / room / f'{room}.play.json'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--pictures', metavar='DIR')
    args = ap.parse_args()
    plays = {room: json.loads(play_file(room).read_text()) for room in ORDER}
    door_ents = {room: [e for e in plays[room]['entities'] if e['type'] == 'door'] for room in ORDER}
    held, opened, came_by = set(), set(), None
    out, rooms, doors, total = [], [], [], 0
    ok = True
    for k, (room, leave, steps, what) in enumerate(LEGS):
        sim = S.Sim(play=plays[room], door=came_by, held=held, opened=opened)
        r = PL.play(steps, sim, frames=range(0, 7200, 60) if args.pictures else ())
        near = ', '.join(f'{g} {m:.2f} m at {t}' for g, (m, t) in sorted(r['margins'].items(), key=lambda kv: kv[1][0]))
        res = r['result']
        print(f'SOLUTION_S2_LEG_{k} ({room}, in by {came_by or "the start"}): {res}; holds {sorted(sim.held)}; nearest: {near}')
        good = bool(res) and res[0] == 'cleared' and len(res) > 2 and res[2] == leave
        if not good:
            print(f'  leg {k} does not leave by {leave}')
            ok = False
            break
        if args.pictures:
            PL.sheet(r['shots'], Path(args.pictures) / f's2_leg{k}_{room}.png', cols=6)
        total += res[1] + 1
        # what he leaves with is the run's
        held, opened = set(sim.held), set(sim.opened)
        came_by = next(e for e in door_ents[room] if e['id'] == leave)['params'].get('to')
        rooms.append(ORDER.index(room))
        doors.append([e['id'] for e in door_ents[room]].index(leave))
        out += PL.tape_lines(f'SOLUTION_S2_LEG_{k}', r['inputs'],
                             f'Leg {k}: {what}. The model leaves on tick {res[1]}.')
    if not ok:
        sys.exit('a leg does not leave its room by its door: the tapes were not written')
    print(f'the stage: {total} ticks ({total / 60:.1f} s) without a catch')
    if not args.check:
        text = '\n'.join([HEADER, f'const S2_LEGS = {len(LEGS)}',
                          f'const S2_LEG_ROOM: [{len(rooms)}]u8 = [{", ".join(map(str, rooms))}]',
                          f'const S2_LEG_DOOR: [{len(doors)}]u8 = [{", ".join(map(str, doors))}]', ''] + out)
        if not TAPES.exists() or TAPES.read_text() != text:
            TAPES.write_text(text)
            print('wrote', TAPES.relative_to(CART))


if __name__ == '__main__':
    main()
