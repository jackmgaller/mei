#!/usr/bin/env python3
"""The tower's layout sheet (the owner's gate before a stage is built; approved 2026-10-15): the
building in section and a plan of each room, with the watchers and the solution's paths, from the
rooms' play files and solutions.py's plans. Writes sketch.png beside itself.

    python3 carts/afterhours/levels/tower/sketch.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import layout_sheet as sketch  # noqa: E402
import solutions as SOL  # noqa: E402

PLAYS = SOL.plays()
ROOMS = [
    dict(label='The lobby (1F)', play=PLAYS['lobby'], status='dressed', legs=[(1, SOL.LOBBY, None)],
         doors={'r4_door_up': 'escalator: the lifts up'},
         note='Level 1\'s room, unchanged in play: two patrol guards, two routes crossing. In from the street; '
              'its escalator now takes him to the lifts.'),
    dict(label='The lift hall (6F)', play=PLAYS['hall'], status='new',
         legs=[(2, SOL.HALL_1, 'lh_door_lifts'), (6, SOL.HALL_2, 'lh_door_stair')],
         doors={'lh_door_lifts': 'lifts (in only)', 'lh_door_trading': 'trading floor',
                'lh_door_stair': 'fire stair', 'lh_door_goods': 'goods lift: the end'},
         note='The core (lifts, fire stair) with a corridor round it, split by the securities house\'s glass '
              'screens. Crossed twice: leg 2 in the lift lobby (lifts to the trading floor), leg 6 round the back '
              '(fire stair to the goods lift). Each side\'s watchers see the other through the glass.'),
    dict(label='The trading floor (6F)', play=PLAYS['trading'], status='new', legs=[(3, SOL.TRADING, 'tf_door_hall')],
         doors={'tf_door_hall': 'lift hall', 'tf_door_stair': 'service stair up'},
         note='Columns, the dealers\' desks (low), a glass meeting room, the back office behind its partition '
              'with the service stair: the door behind the trading floor.'),
    dict(label='The ninth floor (9F)', play=PLAYS['ninth'], status='new', legs=[(4, SOL.NINTH, 'nf_door_stair')],
         doors={'nf_door_stair': 'service stair', 'nf_door_up': 'private stair up'},
         note='Not in the directory: the lifts skip it, the core\'s doors are walled up. The glass boardroom '
              '(hides nothing), the coat cupboard (hide), the chairman\'s office and his private stair.'),
    dict(label='The roof and the helipad', play=PLAYS['roof'], status='new', legs=[(5, SOL.ROOF, 'rf_door_private')],
         doors={'rf_door_private': 'chairman\'s stair', 'rf_door_stair': 'fire stair down'},
         note='A searchlight\'s narrow beam (10 degrees, 12 m) sweeps the roof; the plant, the skylight and the '
              'motor room cast its shadows. A guard walks the west end past the fire stair.'),
]

ORANGE, PURPLE = sketch.THIEF, sketch.THIEF_2
LIFT, STAIR = (90, 110, 140), (120, 120, 120)
BUILDING = dict(
    width=44.0,
    storeys=[('1F', 0)] + [(f'{n}F', 4.0 * (n - 1)) for n in range(2, 12)] + [('R', 44.0)],
    rooms=[('The lobby', 'existing, dressed', 6, 36, 0.0, 'dressed'),
           ('The trading floor', 'new', 0, 20, 20.0, 'new'),
           ('The lift hall', 'new: crossed twice', 20, 42, 20.0, 'new'),
           ('The ninth floor', 'new: not in the directory', 0, 42, 32.0, 'new'),
           ('The roof', 'new: the helipad, the searchlight', 0, 42, 44.0, 'new')],
    shafts=[('lifts', 27, 31, 0.0, 40.0, LIFT, 'the core: lifts'),
            ('fire stair', 24.5, 26.5, 0.0, 47.6, STAIR, 'fire stair'),
            ('service stair', 1.0, 3.0, 20.0, 35.6, STAIR, 'service stair'),
            ('private stair', 38.5, 40.5, 32.0, 47.6, STAIR, 'private stair'),
            ('goods lift', 42.2, 43.8, 0.0, 23.6, LIFT, '')],
    marks=[(29.0, 33.8, 'walled up', (150, 60, 60)), (43.0, 10.0, 'goods', LIFT)],
    route=[([(-3.0, 1.2), (28.0, 1.2), (28.0, 21.2), (2.0, 21.2), (2.0, 33.2), (39.5, 33.2), (39.5, 45.2),
             (25.5, 45.2)], ORANGE),
           ([(25.5, 45.2), (25.5, 22.4), (43.0, 22.4), (43.0, 1.2), (46.0, 1.2)], PURPLE)],
    legs=[(1, 15.0, 1.2, ORANGE), (2, 23.0, 21.2, ORANGE), (3, 12.0, 21.2, ORANGE), (4, 18.0, 33.2, ORANGE),
          (5, 33.0, 45.2, ORANGE), (6, 35.0, 22.4, PURPLE)],
    notes=[(-3.0, 2.6, 'in: the street', sketch.DOOR), (43.0, -0.6, 'out: the loading bay', sketch.DOOR)],
    label_dx={'The ninth floor': 3.0, 'The trading floor': 3.0},
)

if __name__ == '__main__':
    out, ok, total = SOL.run(quiet=True)
    assert ok, 'a leg of the draft does not clear on the model'
    sketch.sheet('Stage 2, the tower', ROOMS, HERE / 'sketch.png', building=BUILDING,
                 footer=[
        'A building, not four boxes in a line (the sheet before). One core of lifts and stairs in the same place on every floor; '
        'the route goes up it by lift,',
        'up the service stair from the back office behind the trading floor (the only way onto the ninth, which the lifts skip), up the '
        'chairman\'s private stair to his helipad,',
        'and back down the core\'s fire stair to the sixth, where the lift hall is crossed a second time on the far side of its glass, to the '
        'goods lift down and out. A stage of doors',
        f'(the store\'s rules) without keycards: six legs, five rooms, played perfectly in {total / 60:.0f} s ({total:,} ticks on the model; '
        'the aquarium aims at 142 s, the store is 170 s). No tools; the dash is never needed.'])
