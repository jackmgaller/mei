#!/usr/bin/env python3
"""The shrine town's game entities (DESIGN.md, section 5 and 4.5): the five stars, the triggers
(the bell, the omamori and the platform of the last train, the shortcuts A-E), the last train and
the updrafts (12.10).

    python3 carts/garden/shrinetown/game.py      # writes assets/game/: the omamori, the leaf fire

The region generators put these entities into their cells: each calls `cell_entities(rows)` and
appends what it returns (notes/gen_town.py for rows 0-1, assets/greybox/core/gen_core.py for 2-3,
assets/greybox/mountain/make_mountain.py for 4-5), so a region's generator still writes all of
its cells. The entity types are the garden's game schema's (carts/garden/world/garden.game.mochi:
`star`, `trigger`, `mover`); what the game does with them is carts/garden/README.md, "Entities".
Positions are the level's, in metres; where a number comes from a region generator's own
constants, the comment says which. A trigger's position is the centre of its box's base, 5 cm
over the floor (the World Checker reports an entity inside a solid).

Flags (names the triggers set and the stars and the train wait for):

| Flag | Set by | Saved | Switches |
|---|---|---|---|
| red_coins | the game, when the last red coin is taken | no | star 2 appears |
| bell | the bell's rope (touch) | no | star 3 appears |
| race5 | the omamori (touch), for TIMER ticks | no | the train starts; the omamori is hidden |
| race5_won | the platform (touch, while race5 is set): ends race5 | no | star 5 appears |
| shortcut_a ... _e | the shortcuts (press or pound) | yes | their layers |
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = HERE / 'assets' / 'game'

# ★5, the last train (DESIGN.md 5, ★5; section 12, 12.9): the omamori's clock, in ticks. The
# train comes in from the west at 30 s, stands at the platform from 40 s and leaves when the
# clock runs out (85 s), so every winner (the fastest, by G8, at about 49 s) sees it standing
# there; a win does not park it (attach.akr: its first cycle runs to the end), it leaves as the
# reward. Measured routes and why this number: DESIGN.md, ★5.
TIMER = 85 * 60
TRAIN_DELAY = 30 * 60               # ticks parked after the omamori is taken
TRAIN_LEG = 600                     # ticks from the west end to the platform (eased)
TRAIN_PAUSE = TIMER - TRAIN_DELAY - TRAIN_LEG   # ticks stopped at the platform: until the clock runs out

# the station's path along track 2 (the set's middle, x 24 to 160, on the taper's S) and the
# two-car train drawn along it, with its collision (place/race_train.py)
from place.race_train import NAME as RACE_PATH, PATH as RACE_POINTS
from place.race_train import ASSET as RACE_TRAIN, COLLISION as RACE_TRAIN_COL
STAGE_Y = 60.0                      # layout.STAGE_Z
BELL = (154.0, 347.15)              # forest_stage_bell's pull rope (place/shrine.py: the bell under the real hall's eave)
DECK = 9.0                          # layout.VIADUCT_DECK
PLATFORM = DECK + 1.0               # station_platform's floor (place/station.py)

def train_mover():
    """The last train: along the world path RACE_PATH (track 2's centre line, from x 24 to the
    platform's middle), two real cars (RACE_TRAIN)."""
    params = {'path': RACE_PATH, 'period': TRAIN_LEG, 'pause': TRAIN_PAUSE, 'start': 'race5',
              'delay': TRAIN_DELAY}
    return {'id': 'train_5', 'type': 'mover', 'position': list(RACE_POINTS[0]), 'asset': RACE_TRAIN,
            'collision': RACE_TRAIN_COL, 'params': params}


ENTITIES = [
    # ---- the five stars (they were coins in the grey box: the IDs, and so the saved bits, stay)
    # ★1 0.5 m over the pagoda's finial (178, 262): taken from the finial pole's top (scenario 422)
    {'id': 'star_1_pagoda', 'type': 'star', 'position': [178, 45.49, 262]},
    # ★2 on the great torii's top beam (13.1 in the real torii's middle): there once the eight red coins are taken
    {'id': 'star_2_torii', 'type': 'star', 'position': [160, 14.7, 124], 'params': {'appear': 'red_coins'}},
    # ★3 rung down onto the stage's deck, 2.4 m in front of the bell's rope
    {'id': 'star_3_bell', 'type': 'star', 'position': [BELL[0], STAGE_Y + 1.0, BELL[1] - 2.4],
     'params': {'appear': 'bell'}},
    # ★4 in the root chamber inside the sacred cedar (layout.CEDAR, the basin floor 13)
    {'id': 'star_4_cedar', 'type': 'star', 'position': [154, 14.0, 296]},
    # ★5 on the platform, at the marked spot, once the race is won
    {'id': 'star_5_platform', 'type': 'star', 'position': [160, PLATFORM + 1.4, 7.0],
     'params': {'appear': 'race5_won'}},

    # ---- ★3: the bell's rope, a touch within about 0.6 m of it
    {'id': 'bell_rope', 'type': 'trigger', 'position': [BELL[0], STAGE_Y, BELL[1]],
     'params': {'size': [1.2, 4.0, 1.2], 'flag': 'bell', 'keep': False}},

    # ---- ★5: the omamori on the stage's south-east corner (layout.RACE_SWITCH) starts the clock;
    # the platform (and the train's roof while it stands there) ends it, won
    {'id': 'race_switch', 'type': 'trigger', 'position': [168, STAGE_Y, 342], 'asset': 'game_omamori',
     'params': {'size': [1.4, 2.0, 1.4], 'flag': 'race5', 'keep': False, 'timer': TIMER, 'ends': 'race5_won',
                'hide': True}},
    # the platform's box: the island platform's floor only (station_platform: z 5.5-10.5, from
    # x 144 to 176), 3 m up from it, so not the trackbeds (9.0) beside it, not the canopy's roof
    # (13.47) and not the walkway north of track 2. (A body's head in it counts: the stair's top
    # flight, coming up through the floor, is in it from about 8.5.)
    {'id': 'race_platform', 'type': 'trigger', 'position': [160, PLATFORM + 0.05, 8.0],
     'params': {'size': [32, 3, 5.0], 'flag': 'race5_won', 'needs': 'race5', 'ends': 'race5', 'keep': False}},
    # the two-car train on track 2: parked until the omamori is taken, then in from the west end
    # of the viaduct, stopped with its middle at the platform's (x 160), and back out west, on
    # track 2 (z 10 on the standard spans, the taper's S to 12.1 at the station)
    train_mover(),

    # ---- the shortcuts (DESIGN.md 4.5): each opens once and stays open (saved)
    # A: the rope ladder, kicked down from the ledge (44) at the lip over it (the face at z 318)
    {'id': 'shortcut_a', 'type': 'trigger', 'position': [154.0, 44.05, 319.2],
     'params': {'size': [3.0, 3.0, 2.4], 'how': 'press', 'flag': 'shortcut_a', 'on': 'ladder_a'}},
    # B: the north gate's bar, lifted from the ridge side (place/shrine.py: the gate at (162, 237.4), the
    # bar on its north face, the stair's foot outside it at 5.0)
    {'id': 'shortcut_b', 'type': 'trigger', 'position': [162.0, 5.05, 239.0],
     'params': {'size': [8.8, 3.0, 2.8], 'how': 'press', 'flag': 'shortcut_b', 'on': 'gate_b_open'}},
    # C: the dead cedar (its trunk 1.4 m square at (256, 306), its foot at 33.37), pounded at its
    # root plate on the shoulder trail's side, east and south-east of it (the rim west of it is
    # too steep to stand on)
    {'id': 'shortcut_c', 'type': 'trigger', 'position': [257.5, 33.4, 305.0],
     'params': {'size': [4.0, 4.0, 4.0], 'how': 'pound', 'flag': 'shortcut_c', 'on': 'cedar_c_down'}},
    # D: the root bulge on the floor of the root chamber inside the sacred cedar (tree_cedar_sacred_hollow:
    # local (0.25, 1.15), the tree turned 59.7 degrees to the rope deck by place/shrine.py; the floor 13.08)
    {'id': 'shortcut_d', 'type': 'trigger', 'position': [155.1, 13.13, 296.4],
     'params': {'size': [2.0, 3.0, 2.8], 'how': 'pound', 'flag': 'shortcut_d', 'off': 'root_d_shut'}},
    # E: the fire-escape ladder, kicked down from the building's roof (the real street_building's
    # deck, 15.2) at its north edge, over the ladder (x 198.5)
    {'id': 'shortcut_e', 'type': 'trigger', 'position': [199.0, 15.25, 101.0],
     'params': {'size': [3.0, 3.0, 2.4], 'how': 'press', 'flag': 'shortcut_e', 'on': 'ladder_e'}},
]

# ---- the updrafts (DESIGN.md 12.10, "Updrafts"; carts/garden/updraft.akr): rising air a glide rides
# up to its cap. Each is placed at its source (the plume is drawn from there); `base` and `cap` are
# metres over it. A box's base sits over what a jump from the ground under it reaches (a running
# triple jump: 5.61 m): a column is caught by a glide, from a roof near it or from far.
SENTO_TOP = (30.5, 18.2, 67.5)      # the sento's chimney top (place/canal.py: SENTO, the chimney at local (8.8, 4.25))
UPDRAFTS = [
    # the sento's steam: the chimney's, blown east-south-east over the lane (toward the danchi). Its
    # box, x 26.5-40.5, z 59.5-71.5, from 6.0: over a running triple jump from the lane (5.6), under
    # a double jump's glide from the sento's roofs (3.7-7.7) and the boiler room's (5.0), and a
    # glide from the danchi's roof (18.8; red coin 4) comes into it at about 13. The glide holds at
    # 24, 5.1 m over red coin 7 (18.9, on the chimney's top 18.2): let go over the chimney and the
    # body drops onto it through the coin.
    {'id': 'ud_sento', 'type': 'updraft', 'position': list(SENTO_TOP),
     'params': {'width': 14.0, 'depth': 12.0, 'base': round(6.0 - SENTO_TOP[1], 2), 'cap': round(24.0 - SENTO_TOP[1], 2),
                'lift': 6.0, 'look': 'steam', 'puffs': 20, 'lean': [6.0, 0.0, -4.0]}},
    # the courtyard's leaf fire (takibi), west of the sando between the torii and the gate: G8's
    # chain. West, so that G8's own line (east of the torii, x 170 at z 146) does not pass through
    # it. Its box, x 142-158, z 136.5-152.5, from 9.3: over a triple jump from what stands in it
    # (the stone lanterns, 2.5; the shed at x 142, 3.3: 8.9). A glide from the stage that clears the
    # gate (17.8) comes into it at about 15; it holds at 21, and from there glides over the great
    # torii (its top beam 13.3; 2.6 m clear, 6 m west of star 2's place) and the front road onto
    # the arcade's roof.
    {'id': 'ud_court', 'type': 'updraft', 'position': [150.0, 0.65, 146.0], 'asset': 'game_takibi',
     'params': {'width': 16.0, 'depth': 16.0, 'base': 8.65, 'cap': 20.35, 'lift': 6.0, 'look': 'smoke',
                'puffs': 24, 'lean': [0.0, 0.0, -3.0]}},
    # the falls' mist, over the pool at the foot of the falls (its bed 11.2): the gentle one. Its box,
    # x 208-220, z 313-327, from 12.7; caught from the pool's west terrace (16) or the east shelf (20)
    # with a double jump's glide. It holds at 30, under the kick chimney's rest ledge (31); from there
    # a glide crosses west over the terrace.
    {'id': 'ud_falls', 'type': 'updraft', 'position': [214.0, 11.2, 320.0],
     'params': {'width': 12.0, 'depth': 14.0, 'base': 1.5, 'cap': 18.8, 'lift': 5.0, 'look': 'mist',
                'puffs': 20}},
]
ENTITIES += UPDRAFTS


def cell_entities(rows):
    """The entities whose cell is in `rows` (z // 64): {cell id: [entity, ...]}, copies."""
    out = {}
    for e in ENTITIES:
        x, _, z = e['position']
        i, j = int(x // 64), int(z // 64)
        if j in rows:
            out.setdefault(f'c{i}_{j}', []).append(json.loads(json.dumps(e)))
    return out


# ---- the grey-box assets: boxes in flat colours (the real train and omamori replace them)

def box(x0, y0, z0, x1, y1, z1, mat, top=None):
    """A box's mesh node faces: 8 vertices, 6 quads (top in `top`, the rest in mat)."""
    v = [[x0, y1, z1], [x1, y1, z1], [x1, y1, z0], [x0, y1, z0],
         [x0, y0, z0], [x1, y0, z0], [x0, y0, z1], [x1, y0, z1]]
    f = [[0, 1, 2, 3], [4, 3, 2, 5], [6, 7, 1, 0], [4, 6, 0, 3], [5, 2, 1, 7], [4, 5, 7, 6]]
    m = [top or mat, mat, mat, mat, mat, mat]
    return v, f, m


def recipe(name, boxes, colours, budget):
    nodes = []
    for k, b in enumerate(boxes):
        v, f, m = box(*b)
        nodes.append({'id': f'b{k}', 'op': 'mesh', 'vertices': [[round(c, 3) for c in p] for p in v],
                      'faces': f, 'face_materials': m})
    return {'format': 'mei-asset', 'version': 1, 'name': name,
            'materials': {k: {'color': c, 'palette': True} for k, c in colours.items()},
            'lighting': {'mode': 'vertical', 'ambient': 0.5},
            'verification': {'required': True, 'depth': True, 'perspective': True},
            'budget': {'triangles': budget}, 'nodes': nodes}


def takibi():
    """A leaf fire (ud_court's source): a low heap of fallen leaves, gold and rust, in a ring of
    four stones, about 1.6 m across."""
    b = [(-0.7, 0.0, -0.7, 0.7, 0.25, 0.7, 'rust'),
         (-0.45, 0.2, -0.5, 0.5, 0.5, 0.45, 'gold', 'ember'),
         (-0.95, 0.0, -0.2, -0.75, 0.22, 0.2, 'stone'), (0.75, 0.0, -0.2, 0.95, 0.22, 0.2, 'stone'),
         (-0.2, 0.0, -0.95, 0.2, 0.22, -0.75, 'stone'), (-0.2, 0.0, 0.75, 0.2, 0.22, 0.95, 'stone')]
    return recipe('game_takibi', b, {'rust': '#8a4a22', 'gold': '#c89a2e', 'ember': '#e0602a', 'stone': '#7c7a74'}, 72)


def omamori():
    """A red brocade pouch (0.36 x 0.5 x 0.12) with its gold cord, at chest height over its spot."""
    b = [(-0.18, 0.9, -0.06, 0.18, 1.4, 0.06, 'red'),
         (-0.05, 1.38, -0.03, 0.05, 1.55, 0.03, 'gold')]
    return recipe('game_omamori', b, {'red': '#d02030', 'gold': '#f0c040'}, 24)


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.glob('game_*.asset.json'): p.unlink()
    for r in (omamori(), takibi()):
        (OUT / f'{r["name"]}.asset.json').write_text(json.dumps(r, separators=(',', ':')) + '\n')
    print(f'{OUT.relative_to(HERE)}: game_omamori, game_takibi; {len(ENTITIES)} entities '
          f'(TIMER {TIMER} ticks, the train in at {(TRAIN_DELAY) / 60:g} s, at the platform at '
          f'{(TRAIN_DELAY + TRAIN_LEG) / 60:g} s, out at {TIMER / 60:g} s)')
