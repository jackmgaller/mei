#!/usr/bin/env python3
"""The shrine town's game entities (DESIGN.md, section 5 and 4.5): the five stars, the triggers
(the bell, the omamori and the platform of the last train, the shortcuts A-E) and the last train.

    python3 carts/garden/shrinetown/game.py      # writes assets/game/: the train and the omamori

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
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'assets' / 'game'

# ★5, the last train (DESIGN.md 5, ★5; section 12): the omamori's clock, in ticks. The train
# comes in from the west 25 s before the end, stops at the platform 15 s before it and leaves
# when the clock runs out. Measured routes and why this number: DESIGN.md, ★5.
TIMER = 85 * 60
TRAIN_LEG = 600                     # ticks from the west end to the platform (eased)
TRAIN_PAUSE = 900                   # ticks stopped at the platform
TRAIN_DELAY = TIMER - TRAIN_LEG - TRAIN_PAUSE

STAGE_Y = 60.0                      # layout.STAGE_Z
BELL = (154.0, 347.15)              # forest_stage_bell's pull rope (place/shrine.py: the bell under the real hall's eave)
TRACK2_Z = 12.1                     # the station's track 2 (the north one); the rail at the deck, 9.0
DECK = 9.0                          # layout.VIADUCT_DECK

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
    {'id': 'star_5_platform', 'type': 'star', 'position': [160, DECK + 1.4, 7.0], 'params': {'appear': 'race5_won'}},

    # ---- ★3: the bell's rope, a touch within about 0.6 m of it
    {'id': 'bell_rope', 'type': 'trigger', 'position': [BELL[0], STAGE_Y, BELL[1]],
     'params': {'size': [1.2, 4.0, 1.2], 'flag': 'bell', 'keep': False}},

    # ---- ★5: the omamori on the stage's south-east corner (layout.RACE_SWITCH) starts the clock;
    # the platform (and the train's roof while it stands there) ends it, won
    {'id': 'race_switch', 'type': 'trigger', 'position': [168, STAGE_Y, 342], 'asset': 'game_omamori',
     'params': {'size': [1.4, 2.0, 1.4], 'flag': 'race5', 'keep': False, 'timer': TIMER, 'ends': 'race5_won',
                'hide': True}},
    # the platform's box: x 144-176 over the whole deck's width up to the north parapet (z 3.5-14),
    # 6 m high: the island platform, the train standing at it and, in the grey box, the head of the
    # plaza stairs, which reach the deck north of track 2
    {'id': 'race_platform', 'type': 'trigger', 'position': [160, DECK + 0.05, 8.75],
     'params': {'size': [32, 6, 10.5], 'flag': 'race5_won', 'needs': 'race5', 'ends': 'race5', 'keep': False}},
    # the two-car train on track 2: parked until the omamori is taken, then in from the west end
    # of the viaduct, stopped with its middle at the platform's (x 160), and back out west
    {'id': 'train_5', 'type': 'mover', 'position': [2.0, DECK, TRACK2_Z], 'asset': 'game_train',
     'collision': 'game_train',
     'params': {'to': [158, 0, 0], 'period': TRAIN_LEG, 'pause': TRAIN_PAUSE, 'start': 'race5',
                'delay': TRAIN_DELAY}},

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
    # E: the fire-escape ladder, kicked down from the building's roof (18.3) at its north edge
    {'id': 'shortcut_e', 'type': 'trigger', 'position': [199.0, 18.35, 101.0],
     'params': {'size': [3.0, 3.0, 2.4], 'how': 'press', 'flag': 'shortcut_e', 'on': 'ladder_e'}},
]


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


def train():
    """Two cars of 19.5 m (x), 2.8 m wide, their floors 1.1 over the rail (the origin), roofs at
    3.6; bogies under them. Centred on the origin along x: 40 m in all."""
    b = []
    for cx in (-9.9, 9.9):
        b.append((cx - 9.75, 1.0, -1.4, cx + 9.75, 3.6, 1.4, 'body', 'roof'))
        for bx in (cx - 6.5, cx + 6.5):
            b.append((bx - 1.3, 0.0, -1.1, bx + 1.3, 1.02, 1.1, 'bogie'))     # 2 cm into the car
    b.append((-0.2, 1.2, -1.0, 0.2, 3.3, 1.0, 'bogie'))            # the gangway between the cars
    return recipe('game_train', b, {'body': '#e8e2d0', 'roof': '#8a8c90', 'bogie': '#3a3c40'}, 96)


def omamori():
    """A red brocade pouch (0.36 x 0.5 x 0.12) with its gold cord, at chest height over its spot."""
    b = [(-0.18, 0.9, -0.06, 0.18, 1.4, 0.06, 'red'),
         (-0.05, 1.38, -0.03, 0.05, 1.55, 0.03, 'gold')]
    return recipe('game_omamori', b, {'red': '#d02030', 'gold': '#f0c040'}, 24)


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.glob('game_*.asset.json'): p.unlink()
    for r in (train(), omamori()):
        (OUT / f'{r["name"]}.asset.json').write_text(json.dumps(r, separators=(',', ':')) + '\n')
    print(f'{OUT.relative_to(HERE)}: game_train, game_omamori; {len(ENTITIES)} entities '
          f'(TIMER {TIMER} ticks, the train in at {(TRAIN_DELAY) / 60:g} s, at the platform at '
          f'{(TRAIN_DELAY + TRAIN_LEG) / 60:g} s, out at {TIMER / 60:g} s)')
