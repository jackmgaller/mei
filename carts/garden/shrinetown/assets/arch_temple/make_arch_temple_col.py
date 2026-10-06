"""Writes arch_temple_town_col.asset.json beside this script (python3 make_arch_temple_col.py): shrine
town's climbing collision for the shrine's main hall (carts/garden/shrine/assets/arch_temple), whose
look is reused unchanged. Its name is not the shrine's own collision's (arch_temple_col), so that the
shrine's assets can be one of shrine town's asset directories, as with arch_pagoda_town_col.

The shrine's collision follows the hall's roofs: each eave overhangs the roof (or the podium) below
it, so a body jumping beside a roof's edge is under its eave and the eave stops its head before the
hands reach the fascia (the alpha review, r10 #4: the temple ridge, G5's take-off, could only be
reached by gliding down from the pagoda). This is that collision with three blocks added under the
eaves, each a wall straight down from just inside an eave's fascia to the roof or the podium below,
so a jump beside the eave meets a wall and the hands catch the roof at the fascia's top (a double jump and a
grab reaches 5.15 m):

- under the lower (pent) roof's front eave (z -11), from the podium (3.6) to its underside, over
  the veranda: the climb starts on the podium's front strip (z -12 to -11), where the stair arrives
  (the hall's sides have no pent roof: their walls rise to the main roof);
- under the main roof's front eave (z -10), from the pent roof to the main roof's underside: from
  the pent roof's front strip (z -11 to -10, outside the main eave);
- under the top roof's front eave (z -6.6), from the main roof to the top roof's underside.

From the top roof (28 degrees) a jump up its upper slope (32 degrees) reaches the ridge (22.54),
whose walk is widened from 1.1 to 2.5 m (a block 1 cm under its top): G5 takes off along it.
The front veranda under the pent roof is closed off by the first block (nothing stood there).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHRINE = HERE.parent.parent.parent / 'shrine' / 'assets' / 'arch_temple_col.asset.json'

# (id, x0, x1, y0, y1, z0, z1), the hall's own frame (origin at the podium's foot, -Z its front).
# Each stands 0.02 in front of its eave's fascia and reaches the fascia's top, where the roof's slope
# starts, so the ledge the hands find is the roof (a block topped under the eave was a floor the
# body climbed onto, inside the roof); inside, it is hidden under the roof's slope. No bottom (it
# stands in the roof or podium below), and no face in the plane of another.
BLOCKS = [
    ('pent_eave_front', -20.98, 20.98, 3.5, 8.0, -11.02, -8.3),
    ('main_eave_front', -20.9, 20.9, 7.9, 12.4, -10.02, -8.35),
    ('top_eave_front', -17.98, 17.98, 13.9, 18.4, -6.62, -5.3),
    ('ridge_walk', -15.9, 15.9, 20.6, 22.53, -1.25, 1.25),
]


def box(nid, x0, x1, y0, y1, z0, z1):
    return {'id': nid, 'op': 'box', 'size': [round(x1 - x0, 3), round(y1 - y0, 3), round(z1 - z0, 3)],
            'material': 'solid', 'transform': {'translate': [round((x0 + x1) / 2, 3), round((y0 + y1) / 2, 3),
                                                            round((z0 + z1) / 2, 3)]}, 'open': ['bottom']}


def main():
    shrine = json.loads(SHRINE.read_text())
    r = dict(shrine, name='arch_temple_town_col')
    r['nodes'] = shrine['nodes'] + [box(*b) for b in BLOCKS]
    (HERE / 'arch_temple_town_col.asset.json').write_text(json.dumps(r, indent=1) + '\n')
    print('wrote arch_temple_town_col')


if __name__ == '__main__':
    main()
