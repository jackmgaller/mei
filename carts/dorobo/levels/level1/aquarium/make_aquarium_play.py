#!/usr/bin/env python3
"""Level 1, room 5: the aquarium on the roof. Writes its play file (the room's entities and wall
map), its default placements and a collision recipe for the sketch's room, beside itself.

    python3 carts/dorobo/levels/level1/aquarium/make_aquarium_play.py

The aquarium's drawing is the sketch's (carts/dorobo/rooms/aquarium/, its own builder's, who is
relighting it); its floor plan is rooms/aquarium/PLAN.md. This file holds what is played there,
from the plan's numbers (the same as make_aquarium.py's): if the plan changes, change them here.
The level (levels/level1/make_level1.py) uses rooms/aquarium/aquarium.placements.json when the
builder has written one, else the placements below.

Teaches nothing new: it combines the level's ideas. Glass (the jellyfish column and the coral
cube) lets cones through and stops the thief; the pillar casts a shadow; a posted guard by the
window turns on a cycle; a keeper walks round the coral cube.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from greybox import box, recipe, wall, patrol, posted, write_json, r  # noqa: E402

P = 'r5_'

# ---- the plan (rooms/aquarium/PLAN.md; the sketch's numbers)
XI, XO = 5.8, 6.05             # inner and outer faces of the side walls
ZF, ZFO = -2.9, -3.15          # front wall (cut at 1 m): inner and outer faces
ZB, ZBO = 2.9, 3.15            # back (window) wall
TANK_Z1 = 4.6                  # the big tank's water ends here; its back wall is 0.25 thick
TANK_X, TANK_WALL = 4.6, 0.25  # the tank's water: x in [-TANK_X, TANK_X]
WIN_X = 4.4                    # the ocean window: x in [-WIN_X, WIN_X]
H = 3.2
ENTRY = (-4.9, -3.7)           # the gap in the front wall: the way in (from the lift)
DOOR_X = 5.25                  # the staff door, in the back wall's right pier: the exit
JELLY, JELLY_R = (-2.9, -0.2), 0.75
CUBE, CUBE_S = (3.0, 0.15), 1.42
PILLAR, PILLAR_S = (-0.2, -1.6), 0.5
BENCH, BENCH_W, BENCH_D = (0.0, 1.35), 2.6, 0.5     # the sketch's is 3.4 m: PLAN.md shortens it
STANCHION_Z = 2.42
SIGN = (-1.65, -0.5)
CART = (4.7, -2.25)

SPAWN = (-4.3, -2.45, 0)
EXIT = dict(pos=(DOOR_X, ZB - 0.3), size=(0.8, 2.0, 0.6))
# The night watchman, standing at the window in the middle: he watches the fish (his cone goes
# through the window into the tank), then turns round, past the coral cube, to look over the room.
POSTED = dict(pos=(0.0, 2.0), look_a=0, look_b=180, hold=150, turn=90, sight=5.0, fov=60)
# The keeper, round the coral cube.
KEEPER = dict(start=(1.75, -1.25), speed=0.9, sight=4.5, fov=60, turn_rate=180,
              route=[('r5_wp_cube_se', (4.9, -1.25), 0, 90),
                     ('r5_wp_cube_ne', (4.9, 1.95), 60, 0),
                     ('r5_wp_cube_nw', (1.75, 1.95), 0, 270),
                     ('r5_wp_cube_sw', (1.75, -1.25), 60, 275)])


def play():
    zc = (ZFO + TANK_Z1 + TANK_WALL) / 2
    ents = [
        {'id': P + 'room', 'type': 'room', 'position': [0, 0, r(zc)],
         'params': {'entry': P + 'spawn', 'exit': P + 'exit', 'size': [r(2 * XO), H, r(TANK_Z1 + TANK_WALL - ZFO)]}},
        {'id': P + 'spawn', 'type': 'spawn', 'position': [SPAWN[0], 0, SPAWN[1]], 'params': {'yaw': SPAWN[2]}},
        {'id': P + 'exit', 'type': 'exit', 'position': [EXIT['pos'][0], 0, r(EXIT['pos'][1])],
         'params': {'size': list(EXIT['size'])}},
        posted(P + 'guard_watchman', POSTED['pos'], POSTED['look_a'], POSTED['look_b'], POSTED['hold'], POSTED['turn'],
               POSTED['sight'], POSTED['fov']),
        wall(P + 'wall_front_w', -XO, ZFO, ENTRY[0], ZF, h=1.0),
        wall(P + 'wall_front_e', ENTRY[1], ZFO, XO, ZF, h=1.0),
        wall(P + 'wall_entry_beyond', ENTRY[0], ZFO - 0.3, ENTRY[1], ZFO),
        wall(P + 'wall_side_w', -XO, ZF, -XI, ZB),
        wall(P + 'wall_side_e', XI, ZF, XO, ZB),
        # the window wall: its piers block, the window is glass (cones go through to the fish); the
        # tank's walls behind it stop them
        wall(P + 'wall_pier_w', -XO, ZB, -WIN_X, ZBO),
        wall(P + 'wall_pier_e', WIN_X, ZB, XO, ZBO),
        wall(P + 'glass_window', -WIN_X, ZB, WIN_X, ZBO, blocks=False),
        wall(P + 'wall_tank_back', -TANK_X - TANK_WALL, TANK_Z1, TANK_X + TANK_WALL, TANK_Z1 + TANK_WALL),
        wall(P + 'wall_tank_w', -TANK_X - TANK_WALL, ZBO, -TANK_X, TANK_Z1),
        wall(P + 'wall_tank_e', TANK_X, ZBO, TANK_X + TANK_WALL, TANK_Z1),
        wall(P + 'wall_pillar', PILLAR[0] - PILLAR_S / 2, PILLAR[1] - PILLAR_S / 2,
             PILLAR[0] + PILLAR_S / 2, PILLAR[1] + PILLAR_S / 2, h=1.0),
        # glass: the cones pass, the thief does not
        wall(P + 'glass_jelly', JELLY[0] - JELLY_R, JELLY[1] - JELLY_R, JELLY[0] + JELLY_R, JELLY[1] + JELLY_R,
             blocks=False, h=2.4),
        wall(P + 'glass_cube', CUBE[0] - CUBE_S / 2, CUBE[1] - CUBE_S / 2, CUBE[0] + CUBE_S / 2, CUBE[1] + CUBE_S / 2,
             blocks=False, h=CUBE_S),
        # low things: the bench, the stanchions' rope, the cart, the sign
        wall(P + 'wall_bench', BENCH[0] - BENCH_W / 2, BENCH[1] - BENCH_D / 2, BENCH[0] + BENCH_W / 2,
             BENCH[1] + BENCH_D / 2, blocks=False, h=0.5),
        wall(P + 'wall_stanchions', -3.65, STANCHION_Z - 0.05, 3.65, STANCHION_Z + 0.05, blocks=False, h=0.9),
        wall(P + 'wall_cart', CART[0] - 0.45, CART[1] - 0.25, CART[0] + 0.45, CART[1] + 0.25, blocks=False, h=0.9),
        wall(P + 'wall_sign', SIGN[0] - 0.2, SIGN[1] - 0.1, SIGN[0] + 0.2, SIGN[1] + 0.1, blocks=False, h=1.5),
    ]
    ents += patrol(P + 'guard_keeper', KEEPER['start'], KEEPER['route'], KEEPER['speed'], KEEPER['sight'],
                   KEEPER['fov'], turn_rate=KEEPER['turn_rate'])
    return {'format': 'after-hours-play', 'version': 1, 'room': 'aquarium', 'entities': ents, 'paths': {}}


def collision():
    """Floors and walls without tops, for the World Checker (the game moves on the wall map)."""
    op = ['bottom', 'top']
    n = [box('floor', (-XO, -0.4, ZFO), (XO, 0, ZBO), 'floor', open=['bottom']),
         box('front_w', (-XO, 0, ZFO), (ENTRY[0], 1.0, ZF), 'floor', open=op),
         box('front_e', (ENTRY[1], 0, ZFO), (XO, 1.0, ZF), 'floor', open=op),
         box('side_w', (-XO, 0, ZF), (-XI, H, ZB), 'floor', open=op + ['back', 'front']),
         box('side_e', (XI, 0, ZF), (XO, H, ZB), 'floor', open=op + ['back', 'front']),
         box('back', (-XO, 0, ZB), (XO, H, ZBO), 'floor', open=op)]
    rec = recipe('aq_col', n, 100, collision=True)
    return rec


def main():
    write_json(HERE / 'aquarium.play.json', play())
    write_json(HERE / 'aquarium.placements.json', {
        'format': 'after-hours-placements', 'version': 1, 'room': 'aquarium',
        'placements': [{'id': P + 'room_shell', 'asset': 'aq_room', 'position': [0, 0, 0], 'collision': 'aq_col'},
                       {'id': P + 'tanks', 'asset': 'aq_tanks', 'position': [0, 0, 0], 'collision': 'none'}]})
    write_json(HERE / 'collision' / 'aq_col.asset.json', collision())


if __name__ == '__main__':
    main()
