#!/usr/bin/env python3
"""The aquarium's solution: the stage's ten legs in play order, played on the rules' model
(levels/rules_model.py, with the aquarium's dark rooms, lights and two levels) and written as the
cart's solution tapes.

    python3 carts/afterhours/levels/aquarium/solutions.py [--check] [--pictures DIR]

A leg is one visit to a room: from the spawn of the door he came in by (the stage's start, for
the first), at the room's clock 0, out by a door. Each leg's plan is played on its room's play
file (its own frame: the stage only moves rooms, so a tape is the same there). The tapes go to
carts/afterhours/tests/tapes/aquarium_solution.akr: SOLUTION_AQUARIUM_LEG_0 .. 9, with
AQUARIUM_LEG_ROOM (each leg's room, numbered in the rooms' `next` order) and AQUARIUM_LEG_DOOR (the
door it leaves by, the index among its room's doors in entity order). ROUTE.md tells the
solutions in words. No leg dashes or runs.

--check     only play the legs and print how each ends and how near each watcher came (metres
            from the thief's centre to the fan; for a watcher without a torch in a dark room,
            to the lit part of it); write nothing
--pictures  also draw each leg from above every second into DIR (needs Pillow)

The model is not the cart: check the tapes in the cart afterwards (A's scenarios).
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
TAPES = CART / 'tests' / 'tapes' / 'aquarium_solution.akr'

# The rooms in their `next` order (make_aquarium.py's ROOMS): the tapes number rooms by it.
ORDER = ['aq_hall', 'aq_great', 'aq_jelly', 'aquarium', 'aq_quar', 'aq_plant', 'aq_kitchen', 'aq_tops']
PLAYS = {name: CART / 'rooms' / name / f'{name}.play.json' for name in ORDER}
PLAYS['aquarium'] = HERE / 'ocean' / 'ocean.play.json'


def target(sim, gid, wp):
    return G(sim, gid)['target'] == sim.wp_index[wp]


def facing(sim, gid, deg, within=1.0):
    return abs((H(sim, gid) - deg + 180) % 360 - 180) < within


def cycle(gid, at):
    """True on the tick a posted watcher's or camera's cycle (hold at look_a from 0, turn, hold
    at look_b from hold + turn, turn back) is `at` ticks in."""
    def f(sim):
        d = next(w for w in sim.watch if w['id'] == gid)
        n = 2 * (d['hold'] + d['turn'])
        return (sim.clock + d['phase']) % n == at % n
    return f


def x_of(gid):
    return lambda sim: G(sim, gid)['x']


# ---- the plans

# 0. The entrance hall, the floor: along the front in the dark; across the welcome tank's light
# while the desk guard looks at the east door; in the dark again, then through the east door's
# blue while he looks back across the tank.
HALL_FLOOR = [
    ('go', -3.0, -2.9), ('until', cycle('ah_guard_desk', 450)),
    ('go', 3.4, -2.9), ('until', cycle('ah_guard_desk', 200)),
    ('go', 7.2, -1.0), ('go', 8.3, -1.0),
]

# 1. The great tank, the floor: along the front behind the night guard's torch; at the column
# while he walks the far end; out when he has turned up it.
GREAT_FLOOR = [
    ('go', -8.0, -3.3),
    ('until', lambda s: x_of('ag_guard_floor')(s) > 5.0), ('go', 1.5, -3.3),
    ('until', lambda s: G(s, 'ag_guard_floor')['z'] > -0.5),
    ('go', 8.0, -3.3), ('go', 8.6, -2.6), ('go', 10.3, -2.6),
]

# 2. The jellyfish gallery: down the front aisle in the dark behind the wave of light, a bay at a
# time, then up the far end (never lit) to the door.
JELLY = [
    ('go', -6.2, -2.4), ('until', lambda s: s.clock % 480 == 245),
    ('go', -3.2, -2.4), ('until', lambda s: s.clock % 480 == 365),
    ('go', -0.2, -2.4), ('until', lambda s: s.clock % 480 == 5),
    ('go', 2.8, -2.4), ('until', lambda s: s.clock % 480 == 125),
    ('go', 6.4, -2.0), ('go', 6.4, 2.2), ('go', 7.4, 2.2),
]

# 3. The ocean gallery (the tower's aquarium, unchanged): along the front to the pillar while the
# watchman looks at the fish; in the pillar's shadow until he looks at the fish again and the
# keeper is on the cube's far side walking west; along the front and up the east wall to the
# staff door.
OCEAN = [
    ('go', -2.0, -2.4),
    ('until', lambda s: facing(s, 'ao_guard_watchman', 0, 20)),
    ('go', -0.2, -2.45),
    ('until', lambda s: facing(s, 'ao_guard_watchman', 0, 20) and target(s, 'ao_guard_keeper', 'ao_wp_cube_nw')
                        and G(s, 'ao_guard_keeper')['x'] < 4.3),
    ('go', 1.4, -1.65), ('go', 5.35, -1.65), ('go', 5.35, 2.45), ('go', 5.25, 2.65),
]

# 4. Quarantine: round the west end of the tanks into the middle aisle; along it while the front
# row's lamps are off (the keeper is up the east end); behind him down the east end when he has
# turned along the back, and out by the stair door while the camera looks away from its lamp.
QUAR = [
    ('go', -4.9, 0.3), ('until', lambda s: s.clock > 0 and s.clock % 480 == 0),
    ('go', 4.6, 0.3),
    ('until', lambda s: G(s, 'qt_guard_keeper')['z'] > 2.0),
    ('go', 5.7, 0.3), ('go', 5.7, -2.8),
    ('until', lambda s: facing(s, 'qt_camera_stair', 280, 3)), ('go', 6.8, -2.8),
]

# 5. The life-support plant: along the back walkway when the engineer has gone down the middle;
# into the pump's shadow at the top of the middle walkway while the camera looks along the front;
# when it turns away over the sumps, down and along the front walkway to the stair.
PLANT = [
    ('until', lambda s: target(s, 'ap_guard_engineer', 'ap_wp_eng_se')),
    ('go', -0.3, 2.0), ('until', lambda s: facing(s, 'ap_camera_walk', 262)),
    ('go', 0.4, 2.0), ('go', 0.4, 1.0),
    ('until', lambda s: facing(s, 'ap_camera_walk', 320)),
    ('go', 0.4, -3.0), ('go', 8.3, -3.0), ('go', 9.4, -2.8),
]

# 6. The fish kitchen: behind the cook round the prep tables, well clear of the buckets (a knock
# brings him); up the east side behind him and out by the back door when he has turned along the back.
KITCHEN = [
    ('go', -2.0, -3.1),
    ('until', lambda s: target(s, 'ak_guard_cook', 'ak_wp_cook_ne')), ('go', 2.0, -3.1),
    ('until', lambda s: G(s, 'ak_guard_cook')['z'] > 0.4), ('go', 3.4, -3.1), ('go', 3.4, -0.6),
    ('until', lambda s: target(s, 'ak_guard_cook', 'ak_wp_cook_nw') and G(s, 'ak_guard_cook')['x'] < 2.2),
    ('go', 3.4, 2.7), ('go', 4.4, 2.8), ('go', 4.4, 4.4),
]

# 7. The tank tops: along the front walkway to the middle; up it through its lamp while the
# camera looks at the back; along the back to its lamp's edge; through the lamp when the camera
# looks at the middle and the keeper has gone down the west walkway, and out.
TOPS = [
    ('go', 0.0, -3.75),
    ('until', lambda s: facing(s, 'at_camera_east', 290)),
    ('go', 0.0, 4.15), ('go', -2.8, 4.15),
    ('until', lambda s: target(s, 'at_guard_keeper', 'at_wp_keeper_sw') and G(s, 'at_guard_keeper')['z'] < 2.4
                        and facing(s, 'at_camera_east', 240)),
    ('go', -8.1, 4.15), ('go', -8.4, 3.7), ('go', -9.4, 3.7),
]

# 8. The great tank, the catwalk: along the rim behind the keeper on the back walk; through the
# middle lamp while the camera looks at the west lamp; at the lamp's edge until the keeper has
# turned back east and the camera looks at the middle, then through the west lamp and out.
GREAT_RIM = [
    ('go', 2.8, 2.0),
    ('until', lambda s: facing(s, 'ag_camera_rim', 150)),
    ('go', -2.45, 2.0),
    ('until', lambda s: G(s, 'ag_guard_keeper')['x'] > -6.0 and target(s, 'ag_guard_keeper', 'ag_wp_keeper_e')
                        and facing(s, 'ag_camera_rim', 105)),
    ('go', -9.0, 2.0), ('go', -10.4, 2.0),
]

# 9. The entrance hall, the mezzanine: behind the night guard's torch to the tank's lit top;
# across it while the camera looks away; into the west booth after he passes it, hidden while he
# turns at the end and walks back; out by the deck door behind him.
HALL_MEZZ = [
    ('go', 2.8, 2.6),
    ('until', lambda s: facing(s, 'ah_camera_mezz', 295, 2)),
    ('go', -2.5, 2.6),
    ('until', lambda s: x_of('ah_guard_mezz')(s) < -4.65),
    ('go', -4.0, 3.15), ('press', 'A'),
    ('until', lambda s: s.clock > 650 and x_of('ah_guard_mezz')(s) > -2.6),
    ('go', -7.0, 2.8), ('go', -8.4, 2.8),
]

# The legs in play order: (room, the door he leaves by, the plan, what it is). He comes in by
# the stage's start (the first room's `entry`), then by the door on the other side of the last.
LEGS = [
    ('aq_hall', 'ah_door_great', HALL_FLOOR, 'The entrance hall, from the main doors to the great tank'),
    ('aq_great', 'ag_door_jelly', GREAT_FLOOR, 'The great tank\'s gallery, from the hall to the jellyfish'),
    ('aq_jelly', 'aj_door_ocean', JELLY, 'The jellyfish gallery, behind the wave of light'),
    ('aquarium', 'ao_door_quar', OCEAN, 'The ocean gallery, to the staff door'),
    ('aq_quar', 'qt_door_plant', QUAR, 'Quarantine, to the stair down'),
    ('aq_plant', 'ap_door_kitchen', PLANT, 'The life-support plant, to the service stair'),
    ('aq_kitchen', 'ak_door_tops', KITCHEN, 'The fish kitchen, to the tank tops'),
    ('aq_tops', 'at_door_great', TOPS, 'The tank tops, to the catwalk'),
    ('aq_great', 'ag_door_hall_up', GREAT_RIM, 'The great tank\'s catwalk, to the mezzanine'),
    ('aq_hall', 'ah_door_deck', HALL_MEZZ, 'The entrance hall\'s mezzanine, out to the deck'),
]

HEADER = """\
// Written by carts/afterhours/levels/aquarium/solutions.py - do not edit; change the plans there.
// The aquarium's solution tapes (agent J's): the stage's legs in play order, each from its room's
// clock 0. Spans as dr_tape.akr describes them (ticks, buttons held, the stick). Leg k is played
// in room AQUARIUM_LEG_ROOM[k] (the rooms numbered in their `next` order: the entrance hall, the
// great tank, the jellyfish gallery, the ocean gallery, quarantine, the life-support plant, the
// fish kitchen, the tank tops) and leaves it unseen by its door AQUARIUM_LEG_DOOR[k] (the index
// among the room's doors, in entity order). Drafted on a model of the rules
// (levels/rules_model.py) and checked in the cart; if a room, its watchers or the rules change,
// redraft them and check again.
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--pictures', metavar='DIR')
    args = ap.parse_args()
    plays = {room: json.loads(PLAYS[room].read_text()) for room in ORDER}
    door_ents = {room: [e for e in plays[room]['entities'] if e['type'] == 'door'] for room in ORDER}
    came_by = None
    out, rooms, doors, total = [], [], [], 0
    ok = True
    for k, (room, leave, steps, what) in enumerate(LEGS):
        sim = S.Sim(play=plays[room], door=came_by)
        r = PL.play(steps, sim, frames=range(0, 7200, 60) if args.pictures else ())
        near = ', '.join(f'{g} {m:.2f} m at {t}' for g, (m, t) in sorted(r['margins'].items(), key=lambda kv: kv[1][0]))
        res = r['result']
        print(f'SOLUTION_AQUARIUM_LEG_{k} ({room}, in by {came_by or "the start"}): {res}; nearest: {near}')
        good = bool(res) and res[0] == 'cleared' and len(res) > 2 and res[2] == leave
        if good and any(f is not False for f in sim.frag_down):
            print(f'  leg {k} knocks a fragile thing over (a noise): keep the plan clear of them')
            good = False
        elif not good:
            print(f'  leg {k} does not leave by {leave}')
            ok = False
            break
        if args.pictures:
            PL.sheet(r['shots'], Path(args.pictures) / f'aq_leg{k}_{room}.png', cols=6)
        total += res[1] + 1
        came_by = next(e for e in door_ents[room] if e['id'] == leave)['params'].get('to')
        rooms.append(ORDER.index(room))
        doors.append([e['id'] for e in door_ents[room]].index(leave))
        out += PL.tape_lines(f'SOLUTION_AQUARIUM_LEG_{k}', r['inputs'],
                             f'Leg {k}: {what}. The model leaves on tick {res[1]}.')
    if not ok:
        sys.exit('a leg does not leave its room by its door: the tapes were not written')
    print(f'the stage: {total} ticks ({total / 60:.1f} s) without a catch')
    if not args.check:
        text = '\n'.join([HEADER, f'const AQUARIUM_LEGS = {len(LEGS)}',
                          f'const AQUARIUM_LEG_ROOM: [{len(rooms)}]u8 = [{", ".join(map(str, rooms))}]',
                          f'const AQUARIUM_LEG_DOOR: [{len(doors)}]u8 = [{", ".join(map(str, doors))}]', ''] + out)
        if not TAPES.exists() or TAPES.read_text() != text:
            TAPES.write_text(text)
            print('wrote', TAPES.relative_to(CART))


if __name__ == '__main__':
    main()
