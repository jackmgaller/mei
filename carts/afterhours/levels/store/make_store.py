#!/usr/bin/env python3
"""Stage 3 of After Hours, the department store (keycards and backtracking): assembles the
stage's World Kit world from its rooms.

    python3 carts/afterhours/levels/store/make_store.py

Writes store.world.json beside itself (levels/assemble.py says how). The store is one place: the
cinema on its eighth floor, the projection booth, the staff corridor behind them, the shop floor
a floor down and the food hall in the basement, joined by doors as a graph (ROUTE.md). `next`
only orders the rooms, left to right in the section; the cinema is `first`.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import assemble  # noqa: E402

STOREYS = {'cinema': 8, 'booth': 9, 'corridor': 8, 'shopfloor': 7, 'foodhall': -1}

# The rooms in the section's order (they name their own titles): the dressed rooms' asset
# folders (each room's NOTES.md).
ROOMS = [
    ('cinema', 36.0, 'rooms/cinema/cinema.play.json', 'rooms/cinema/cinema.placements.json', ['rooms/cinema/dressed']),
    ('booth', 40.0, 'rooms/booth/booth.play.json', 'rooms/booth/booth.placements.json', ['rooms/booth/dressed']),
    ('corridor', 36.0, 'rooms/corridor/corridor.play.json', 'rooms/corridor/corridor.placements.json', ['rooms/corridor/dressed']),
    ('shopfloor', 31.0, 'rooms/shopfloor/shopfloor.play.json', 'rooms/shopfloor/shopfloor.placements.json', ['rooms/shopfloor']),
    ('foodhall', -4.0, 'rooms/foodhall/foodhall.play.json', 'rooms/foodhall/foodhall.placements.json', ['rooms/foodhall']),
]

if __name__ == '__main__':
    # the cinema's, the shop floor's and the food hall's main recipes are 715, 830 and 1,183
    # triangles: their caps hold the whole room
    assemble.build(HERE / 'store.world.json', 'store', ROOMS, storeys=STOREYS,
                   standin_caps={'cinema': 720, 'shopfloor': 1600, 'foodhall': 1400}, standin_max=1600)
