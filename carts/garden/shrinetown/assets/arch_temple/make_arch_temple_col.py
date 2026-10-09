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

The podium's back strip (behind the hall, z 8.5 to 12: 8.6 in the town, 3.3 m south of the north
wall's 8.95 coping) is a slope, `back_strip`: from the hall's back wall just under the back pent
roof (7.6) down to the podium's back edge (3.6), 49 degrees, a wall to the body, across the
podium's whole width. From the strip a wall kick and a long jump, or a hop and a dive, cleared
the north wall: shortcut B's bypass (the explorer bot; DESIGN.md 12.10). Nothing stands on it
now; a body landing there slides off onto the terrace behind the temple. Not an invisible wall:
the slope lies on the podium's back, under the pent roof's eave.

The roofs (every face wholly above ROOF_FROM, and the blocks standing there) are material `roof`,
tag `tile`: the footsteps' surface byte 7 (carts/garden/README.md, "Surfaces"). The podium (3.6),
the hall's floor (4.2) and the walls below the pent roof's eave stay `solid`, untagged.
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


# The back strip's slope (the hall's frame): from (z 8.5, y 7.6) at the hall's back wall to the
# podium's back edge (z 12, y 3.6), x -26 to 26; its ends close the wedge, and its front faces
# south over the side strips beyond the hall's back wall (x +-18.5), not inside the hall.
BACK = (-26.0, 26.0, 8.5, 12.0, 3.6, 7.6)
HALL_X = 18.5

# The roofs: the pent roof's eave is the lowest, at 8.0; under it the hall's floor is at 4.2.
ROOF_FROM = 7.5
ROOF = {'color': '#ffffff', 'palette': True, 'tag': 'tile'}


def back_strip():
    x0, x1, z0, z1, y0, y1 = BACK
    h = HALL_X
    v = [[x0, y1, z0], [x1, y1, z0], [x1, y0, z1], [x0, y0, z1], [x0, y0, z0], [x1, y0, z0],
         [-h, y1, z0], [-h, y0, z0], [h, y1, z0], [h, y0, z0]]
    # the slope (facing up and back), the two ends, the front's two outer parts
    faces = [[0, 3, 2, 1], [0, 4, 3], [1, 2, 5], [0, 6, 7, 4], [8, 1, 5, 9]]
    return {'id': 'back_strip', 'op': 'mesh', 'vertices': v, 'faces': faces, 'face_materials': ['solid'] * len(faces)}


def box(nid, x0, x1, y0, y1, z0, z1):
    return {'id': nid, 'op': 'box', 'size': [round(x1 - x0, 3), round(y1 - y0, 3), round(z1 - z0, 3)],
            'material': 'roof' if y0 >= ROOF_FROM else 'solid',
            'transform': {'translate': [round((x0 + x1) / 2, 3), round((y0 + y1) / 2, 3),
                                        round((z0 + z1) / 2, 3)]}, 'open': ['bottom']}


def roofs(node):
    """The node with its faces wholly above ROOF_FROM made `roof`."""
    v = node['vertices']
    fm = ['roof' if min(v[i][1] for i in f) >= ROOF_FROM else m
          for f, m in zip(node['faces'], node['face_materials'])]
    return dict(node, face_materials=fm)


def main():
    shrine = json.loads(SHRINE.read_text())
    r = dict(shrine, name='arch_temple_town_col', materials=dict(shrine['materials'], roof=ROOF))
    r['nodes'] = [roofs(n) for n in shrine['nodes']] + [box(*b) for b in BLOCKS] + [back_strip()]
    (HERE / 'arch_temple_town_col.asset.json').write_text(json.dumps(r, indent=1) + '\n')
    print('wrote arch_temple_town_col')


if __name__ == '__main__':
    main()
