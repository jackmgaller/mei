#!/usr/bin/env python3
"""Stage 2 of After Hours, the tower: assembles the stage's World Kit world from its rooms.

    python3 carts/afterhours/levels/tower/make_tower.py

Writes tower.world.json beside itself (levels/assemble.py says how). The tower is one building, a
stage of doors (the store's rules, without keycards): its lobby on the street, the lift hall on
the sixth floor round the building's core (crossed twice, on either side of its glass), the
securities house's trading floor beside it, the ninth floor the directory leaves out, and the
roof with the chairman's helipad (ROUTE.md). The rooms are written by their own scripts first
(rooms/lobby, rooms/hall, rooms/trading, rooms/ninth, rooms/roof) and dressed by their builders.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import assemble  # noqa: E402

NAMES = {'lobby': 'the_lobby'}       # the new rooms name themselves
STOREYS = {'lobby': 1, 'hall': 6, 'trading': 6, 'ninth': 9, 'roof': 12}
# The lobby is level 1's room of a line: its exit (the escalator) becomes a door to the lifts that
# come out in the lift hall (a way in only there).
EXIT_DOORS = {'lobby': ('r4_door_up', 'lh_door_lifts')}

# The rooms in their `next` order (the tapes number rooms by it; the lobby, first, holds the
# stage's start), floors 4 m apart (1F at 0): (room, floor height, its play file, its placements
# (the builder's), its asset folders: the dressed rooms', each room's NOTES.md).
ROOMS = [
    ('lobby', 0.0, 'rooms/lobby/lobby.play.json', 'rooms/lobby/lobby.placements.json', ['rooms/lobby']),
    ('hall', 20.0, 'rooms/hall/hall.play.json', 'rooms/hall/hall.placements.json', ['rooms/hall/dressed']),
    ('trading', 20.0, 'rooms/trading/trading.play.json', 'rooms/trading/trading.placements.json', ['rooms/trading']),
    ('ninth', 32.0, 'rooms/ninth/ninth.play.json', 'rooms/ninth/ninth.placements.json', ['rooms/ninth']),
    ('roof', 44.0, 'rooms/roof/roof.play.json', 'rooms/roof/roof.placements.json', ['rooms/roof/dressed']),
]
# Stand-ins take whole placements: a room whose main recipe is over the 700 a cell gets its own
# cap (the trading floor's tf_floor is 1,285 triangles and its glass 88; the ninth's nf_floor
# 1,402 and its glass 88; the lobby's main recipe fits in 700).
STANDIN_CAPS = {'trading': 1400, 'ninth': 1500}

if __name__ == '__main__':
    assemble.build(HERE / 'tower.world.json', 'tower', ROOMS, names=NAMES, storeys=STOREYS, exit_doors=EXIT_DOORS,
                   standin_caps=STANDIN_CAPS, standin_max=1500)
