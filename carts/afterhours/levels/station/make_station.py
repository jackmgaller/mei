#!/usr/bin/env python3
"""Stage 1 of After Hours, the station: assembles the stage's World Kit world from its rooms.

    python3 carts/afterhours/levels/station/make_station.py

Writes station.world.json beside itself (levels/assemble.py says how). The station is one
place: the last train's platform three floors down, the ticket gates, and the passage out to
the street, its own way up (ROUTE.md). The rooms are written by their own scripts first
(rooms/arrival, rooms/gates, rooms/passage) and dressed by their builders.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import assemble  # noqa: E402

# (A World Kit name: lower case and underscores; shown in capitals with spaces.)
NAMES = {'arrival': 'the_last_train', 'gates': 'the_ticket_gates', 'passage': 'the_passage'}
STOREYS = {'arrival': -3, 'gates': -2, 'passage': -1}
# The passage's main recipe (r3_passage) is 792 triangles with its street stair: its stand-in
# needs more than the 700 a cell, or the cap leaves it out (a cap takes whole placements)
STANDIN_CAPS = {'passage': 900}

# The rooms in the section's order: (room, floor height, its play file, its placements, its
# asset folders: the dressed rooms', each room's NOTES.md).
ROOMS = [
    ('arrival', -16.0, 'rooms/arrival/arrival.play.json', 'rooms/arrival/arrival.placements.json', ['rooms/arrival/dressed']),
    ('gates', -11.0, 'rooms/gates/gates.play.json', 'rooms/gates/gates.placements.json', ['rooms/gates/dressed']),
    ('passage', -6.0, 'rooms/passage/passage.play.json', 'rooms/passage/passage.placements.json', ['rooms/passage']),
]

if __name__ == '__main__':
    assemble.build(HERE / 'station.world.json', 'station', ROOMS, names=NAMES, storeys=STOREYS,
                   standin_caps=STANDIN_CAPS, standin_max=900)
