#!/usr/bin/env python3
"""The tower's solution (stage 2): its six legs in play order, played on the rules' model
(levels/rules_model.py) with the run carried from leg to leg, and written as the cart's solution
tapes, as the store's are.

    python3 carts/afterhours/levels/tower/solutions.py [--check] [--pictures DIR]

A leg is one visit to a room: from the spawn of the door he came in by (the stage's start, for
the first), at the room's clock 0, out by a door. Each leg's plan is played on its room's play
file (its own frame). The lobby is level 1's room with its exit made a door to the lift hall's
lifts (make_tower.py's EXIT_DOORS, assemble.exit_to_door()); its plan is level 1's, unchanged.
The tapes go to carts/afterhours/tests/tapes/tower_solution.akr: SOLUTION_TOWER_LEG_0 .. 5, with
TOWER_LEG_ROOM (each leg's room, numbered in the rooms' `next` order) and TOWER_LEG_DOOR (the door
it leaves by, the index among its room's doors in entity order). ROUTE.md and each room's
PLAN.md tell the solutions in words.

--check     only play the legs and print how each ends and how near each watcher came (metres
            from the thief's centre to the fan); write nothing
--pictures  also draw each leg from above every 1.5 s into DIR (needs Pillow)

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
sys.path.insert(0, str(HERE))
import assemble  # noqa: E402
import planner as PL  # noqa: E402
import rules_model as S  # noqa: E402
import make_tower  # noqa: E402

G = PL.guard
TAPES = CART / 'tests' / 'tapes' / 'tower_solution.akr'
ORDER = [r[0] for r in make_tower.ROOMS]        # the rooms' `next` order: the tapes number rooms by it


def plays():
    """Each room's play file as the world has it (the lobby's exit made a door)."""
    out = {}
    for name, _, play, _, _ in make_tower.ROOMS:
        p = json.loads((CART / play).read_text())
        if name in make_tower.EXIT_DOORS:
            p = assemble.exit_to_door(p, *make_tower.EXIT_DOORS[name])
        out[name] = p
    return out


def target(sim, gid, wp):
    return G(sim, gid)['target'] == sim.wp_index[wp]


def cycle(period, at):
    return lambda s: s.clock % period == at


# ---- the plans

# 0. The lobby (level 1's room 4, its plan unchanged): when the west guard has turned back north,
# across behind him to the desk's east side; when the back guard is at an end of his walk
# looking away, round the desk and up the escalator to the lifts.
LOBBY = [
    ('until', lambda s: target(s, 'r4_guard_west', 'r4_wp_west_n') and G(s, 'r4_guard_west')['z'] > -1.5),
    ('go', -2.0, -3.6), ('go', 2.2, -1.1),
    ('until', lambda s: (target(s, 'r4_guard_back', 'r4_wp_back_w') and G(s, 'r4_guard_back')['x'] < -1.5)
                        or (target(s, 'r4_guard_back', 'r4_wp_back_e') and G(s, 'r4_guard_back')['x'] > 3.0)),
    ('go', 2.2, 1.0), ('go', 0.55, 1.0), ('go', 0.55, 4.1),
]

# 1. The lift hall, the lift lobby: out of the lift behind the planter while the night guard comes
# east along the lobby; when he has passed, west behind him to the trading floor's glass doors.
HALL_1 = [
    ('go', -3.0, -0.75),
    ('until', lambda s: target(s, 'lh_guard_lobby', 'lh_wp_lobby_e') and G(s, 'lh_guard_lobby')['x'] > -2.6),
    ('go', -8.0, -2.9), ('go', -11.6, -2.9),
]

# 2. The trading floor: along the front to the meeting room's glass; when the floor guard has
# walked away west past it, round its north side behind him and down to the front west corner;
# when he has turned back east, up the west end into the back office's doorway, and when its
# camera has turned to the window, across the office to the service stair.
TRADING = [
    ('go', 3.0, -3.9),
    ('until', lambda s: target(s, 'tf_guard_floor', 'tf_wp_floor_w') and G(s, 'tf_guard_floor')['x'] < 1.0),
    ('go', 3.0, -1.25), ('go', -2.6, -1.25), ('go', -6.6, -3.7),
    ('until', lambda s: target(s, 'tf_guard_floor', 'tf_wp_floor_e') and G(s, 'tf_guard_floor')['x'] > -3.4),
    ('go', -7.4, -3.0), ('go', -7.4, 1.35),
    ('until', lambda s: PL.heading(s, 'tf_camera_office') > 349.9),    # the office camera at the window
    ('go', -8.0, 2.4), ('go', -8.0, 5.0),
]

# 3. The ninth floor: into the coat cupboard and hide (A) before the guard comes down the west
# side; out when he has turned along the front, east behind the boardroom (its glass hides
# nothing: he must be walking away) and into the chairman's office before he comes up the east
# side; to the office's back corner, and when its camera has turned away from the stair door,
# to the chairman's private stair.
NINTH = [
    ('go', -6.6, -0.4), ('go', -7.55, -0.4), ('press', 'A'),
    ('until', lambda s: target(s, 'nf_guard_round', 'nf_wp_round_se') and G(s, 'nf_guard_round')['x'] > -4.0),
    ('go', -6.6, -0.1), ('go', 5.6, -0.1), ('go', 5.6, 1.4), ('go', 3.6, 3.6),
    ('until', lambda s: abs(PL.heading(s, 'nf_camera_office') - 40) < 1),
    ('go', 7.4, 3.2), ('go', 8.6, 3.2),
]

# 4. The roof: the searchlight's narrow beam sweeps from the east end (95) to the west end (265),
# holds, and sweeps back; the plant, the skylight and the motor room cast its shadows. When the
# beam has swept on west past the helipad, from the stair house down to the east plant's shadow;
# when it has swept back east past him, along the front past the skylight to the west plant's
# shadow, ahead of it as it comes round again; when the guard is walking away north and the beam
# is on its way back east, round the plant and up to the fire stair in the motor room's shadow,
# behind the guard.
def beam(s, west=None, above=None, below=None):
    """The searchlight's heading now is past `above` / short of `below`, sweeping west (True) or
    east (False)."""
    w = [x for x in s.watch if x['id'] == 'rf_camera_light'][0]
    p = (s.clock + w['phase']) % (2 * (w['hold'] + w['turn']))
    going_west = w['hold'] <= p < w['hold'] + w['turn']
    going_east = p >= 2 * w['hold'] + w['turn']
    h = PL.heading(s, 'rf_camera_light')
    return ((west is None or (going_west if west else going_east)) and (above is None or h > above)
            and (below is None or h < below))


ROOF = [
    ('until', lambda s: beam(s, west=True, above=150)),
    ('go', 8.4, -3.9), ('go', 3.2, -3.5),
    ('until', lambda s: beam(s, west=False, below=125)),
    ('go', -3.0, -3.9), ('go', -6.2, -4.15),
    ('until', lambda s: target(s, 'rf_guard_west', 'rf_wp_west_n') and -0.4 < G(s, 'rf_guard_west')['z'] < 0.6
                        and beam(s, west=False, below=210)),
    ('go', -4.75, -4.0), ('go', -4.75, -1.7), ('go', -6.0, -0.3), ('go', -6.2, 1.7), ('go', -5.0, 1.7),
]

# 5. The lift hall, round the back: while the night guard walks off east along the lobby (at its
# west end he looks up this corridor through the glass), up the corridor and along behind the
# core; when the cleaner has turned west along the front of his round, along the back and down
# the east end behind him to the goods lift.
HALL_2 = [
    ('go', -6.2, 3.75), ('go', 2.0, 3.75),
    ('until', lambda s: target(s, 'lh_guard_cleaner', 'lh_wp_clean_sw') and G(s, 'lh_guard_cleaner')['x'] < 8.0),
    ('go', 10.4, 3.75), ('go', 10.4, -3.0), ('go', 11.6, -3.0),
]

# The legs in play order: (room, the door he leaves by, the plan, what it is).
LEGS = [
    ('lobby', 'r4_door_up', LOBBY, 'The lobby, from the street to the escalator and the lifts'),
    ('hall', 'lh_door_trading', HALL_1, 'The lift hall, the lift lobby: from the lifts to the trading floor'),
    ('trading', 'tf_door_stair', TRADING, 'The trading floor, to the service stair behind it'),
    ('ninth', 'nf_door_up', NINTH, 'The ninth floor, from the service stair to the chairman\'s stair'),
    ('roof', 'rf_door_stair', ROOF, 'The roof, from the chairman\'s stair house to the fire stair'),
    ('hall', 'lh_door_goods', HALL_2, 'The lift hall, round the back: from the fire stair to the goods lift'),
]


HEADER = """\
// Written by carts/afterhours/levels/tower/solutions.py - do not edit; change the plans there.
// The tower's solution tapes (stage 2, agent B's): the stage's legs in play order, each from its
// room's clock 0, the run carried from leg to leg. Spans as dr_tape.akr describes them (ticks,
// buttons held, the stick). Leg k is played in room TOWER_LEG_ROOM[k] (the rooms numbered in their
// `next` order: the lobby, the lift hall, the trading floor, the ninth floor, the roof) and leaves
// it unseen by its door TOWER_LEG_DOOR[k] (the index among the room's doors, in entity order). The
// lift hall is played twice (legs 1 and 5). Drafted on a model of the rules (levels/rules_model.py)
// and checked in the cart; if a room, its watchers or the rules change, redraft them and check
// again.
"""


def run(pictures=None, quiet=False):
    """Plays the legs. Returns ([(room, came_by, plan, result, inputs, leaves by)], all cleared,
    total ticks)."""
    P = plays()
    door_ents = {room: [e for e in P[room]['entities'] if e['type'] == 'door'] for room in ORDER}
    held, opened, came_by = set(), set(), None
    out, total, ok = [], 0, True
    for k, (room, leave, steps, what) in enumerate(LEGS):
        sim = S.Sim(play=P[room], door=came_by, held=held, opened=opened)
        r = PL.play(steps, sim, frames=range(0, 7200, 90) if pictures else ())
        near = ', '.join(f'{g} {m:.2f} m at {t}' for g, (m, t) in sorted(r['margins'].items(), key=lambda kv: kv[1][0]))
        res = r['result']
        if not quiet:
            print(f'SOLUTION_TOWER_LEG_{k} ({room}, in by {came_by or "the start"}): {res}; nearest: {near}')
        if pictures:
            PL.sheet(r['shots'], Path(pictures) / f'tower_leg{k}_{room}.png', cols=4)
        out.append((room, came_by, steps, res, r['inputs'], leave))
        good = bool(res) and res[0] == 'cleared' and len(res) > 2 and res[2] == leave
        if not good:
            ok = False
            if not quiet:
                print(f'  leg {k} does not leave by {leave}')
            break
        total += res[1] + 1
        held, opened = set(sim.held), set(sim.opened)
        came_by = next(e for e in door_ents[room] if e['id'] == leave)['params'].get('to')
    if not quiet:
        print(f'the stage: {total} ticks ({total / 60:.1f} s)' + (' without a catch' if ok else ''))
    return out, ok, total


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--pictures', metavar='DIR')
    args = ap.parse_args()
    legs, ok, total = run(args.pictures)
    if not ok:
        sys.exit('a leg does not leave its room by its door: the tapes were not written')
    if args.check:
        return
    P = plays()
    rooms, doors, lines = [], [], []
    for k, ((room, came_by, steps, res, inputs, leave), (_, _, _, what)) in enumerate(zip(legs, LEGS)):
        rooms.append(ORDER.index(room))
        doors.append([e['id'] for e in P[room]['entities'] if e['type'] == 'door'].index(leave))
        lines += PL.tape_lines(f'SOLUTION_TOWER_LEG_{k}', inputs, f'Leg {k}: {what}. The model leaves on tick {res[1]}.')
    text = '\n'.join([HEADER, f'const TOWER_LEGS = {len(LEGS)}',
                      f'const TOWER_LEG_ROOM: [{len(rooms)}]u8 = [{", ".join(map(str, rooms))}]',
                      f'const TOWER_LEG_DOOR: [{len(doors)}]u8 = [{", ".join(map(str, doors))}]', ''] + lines)
    if not TAPES.exists() or TAPES.read_text() != text:
        TAPES.write_text(text)
        print('wrote', TAPES.relative_to(CART))


if __name__ == '__main__':
    main()
