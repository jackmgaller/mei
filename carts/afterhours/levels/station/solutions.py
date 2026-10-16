#!/usr/bin/env python3
"""The station's solutions (stage 1), one per room, played on the rules' model
(levels/rules_model.py) and written as the cart's solution tapes.

    python3 carts/afterhours/levels/station/solutions.py [--check] [--pictures DIR]

Each room's plan is played on that room's play file (its own frame), from the room's clock 0.
The tapes go to carts/afterhours/tests/tapes/station_solution.akr, SOLUTION_STATION_<ROOM>.
They are level 1's first three rooms' tapes, unchanged (the station is those rooms). ROUTE.md
and each room's PLAN.md tell the solutions in words. The model is not the cart: check the tapes
in the cart afterwards (NOTES_B.md says how).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CART = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent))
import planner as PL  # noqa: E402

G, H = PL.guard, PL.heading
TAPES = CART / 'tests' / 'tapes' / 'station_solution.akr'


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


ROOMS = [
    ('ARRIVAL', CART / 'rooms/arrival/arrival.play.json', ARRIVAL, 'Room 1, the last train'),
    ('GATES', CART / 'rooms/gates/gates.play.json', GATES, 'Room 2, the ticket gates'),
    ('PASSAGE', CART / 'rooms/passage/passage.play.json', PASSAGE, 'Room 3, the passage'),
]

HEADER = """\
// Written by carts/afterhours/levels/station/solutions.py - do not edit; change the plans there.
// The station's solution tapes (stage 1, agent B's), one per room, each from that room's clock 0.
// Spans as dr_tape.akr describes them (ticks, buttons held, the stick). Each reaches its room's
// exit unseen. Drafted on a model of the rules (levels/rules_model.py) and checked in the cart;
// if a room, its watchers or the rules change, redraft them and check again.
"""

if __name__ == '__main__':
    PL.line_stage(ROOMS, TAPES, 'SOLUTION_STATION', HEADER)
