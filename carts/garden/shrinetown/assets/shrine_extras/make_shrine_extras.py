"""Writes the small pieces the shrine zone's placement needs that no asset brief made, beside this
script (python3 make_shrine_extras.py), each with its collision where it has one:

- shrine_wall_plinth_8, _4 and _corner: a 1.0 m course of cut stone that the
  precinct's north wall (the shrine's arch_wall_8 and arch_wall_corner) stands on beside the
  north gate, so its top is 3.6 m over the terrace and a double jump (3.4) does not clear it
  (OVERNIGHT_DECISIONS #5). Footprint 8 (or 4) x 1.1 m and 1.4 x 1.4 m, origin at the middle of the
  base, the top at 1.0. Plain stone colours, no texture, so the world can merge them.
- shrine_stilt_ladder: a wooden ladder up the stage's front stilts from the ledge (44) to over
  the deck's railing (the pole entity holds the body; this is its look). Two rails 0.5 m apart
  and a rung every 0.5 m, 18.3 m; front -Z. No collision.
- shrine_falls_cliff: the rock the falls drop from, over and behind forest_falls_cave, sharing its
  origin (the foot of the falls on the pool's surface, -Z to the pool): a mass 17 m wide from the
  cave's arch (12.4) to the lip at 36.3 (48.3 m in the level, under the stream's bed), its face at z 0.6 behind the water,
  the cave's back sunk into it, and a notch 6.4 m wide down to 34.15 where water_falls (34.2 m)
  pours over. Mossy rock (the shrine's art/forest_mossy_stone.png). Its own collision.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = '../../../shrine/assets/art/'
POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}
ROCK = {'color': '#6e6a62', 'texture': {'image': ART + 'forest_mossy_stone.png', 'projection': 'box',
                                        'scale': [2.4, 2.4]}}
WOOD = {'color': '#8a6446', 'palette': True}
WOOD_DARK = {'color': '#5a3e2c', 'palette': True}


def box(nid, x0, y0, z0, x1, y1, z1, mat, open_=None):
    n = {'id': nid, 'op': 'box', 'size': [round(x1 - x0, 3), round(y1 - y0, 3), round(z1 - z0, 3)],
         'material': mat, 'transform': {'translate': [round((x0 + x1) / 2, 3), round((y0 + y1) / 2, 3),
                                                      round((z0 + z1) / 2, 3)]}}
    if open_:
        n['open'] = open_
    return n


def recipe(name, materials, nodes, budget, lod=None):
    r = {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': {'triangles': budget},
         'materials': materials, 'lighting': LIGHT, 'verification': POLICY, 'nodes': nodes}
    if lod:
        r['lod'] = lod
    return r


def col(name, nodes):
    return recipe(name, {'solid': {'color': '#ffffff', 'palette': True}},
                  [dict(n, material='solid') for n in nodes], 60)


out = {}
# ---- the north wall's plinths
for name, (sx, sz) in (('shrine_wall_plinth_8', (8.0, 1.1)), ('shrine_wall_plinth_4', (4.0, 1.1)),
                       ('shrine_wall_plinth_corner', (1.4, 1.4))):
    nodes = [box('course', -sx / 2, 0, -sz / 2, sx / 2, 1.0, sz / 2, 'stone', ['bottom'])]
    out[name] = recipe(name, {'stone': {'color': '#b4ae9e', 'palette': True}}, nodes, 12)
    out[name + '_col'] = col(name + '_col', nodes)

# ---- the stage's stilt ladder
H, W, R = 18.3, 0.25, 0.04
nodes = [box('rail_w', -W - R, 0, -R, -W + R, H, R, 'wood_dark', ['bottom', 'top']),
         box('rail_e', W - R, 0, -R, W + R, H, R, 'wood_dark', ['bottom', 'top'])]
k, y = 0, 0.35
while y < H - 0.1:
    nodes.append(box(f'rung_{k}', -W + R, y - 0.03, -0.03, W - R, y + 0.03, 0.03, 'wood', ['left', 'right', 'bottom']))
    k += 1
    y += 0.5
out['shrine_stilt_ladder'] = recipe('shrine_stilt_ladder', {'wood': WOOD, 'wood_dark': WOOD_DARK}, nodes, 260,
                                    {'levels': [{'distance': 30, 'nodes': nodes[:2]}], 'cull': 120})

# ---- the cliff over the falls cave
N0, NX, NTOP, TOP, FACE = 6.6, 3.2, 34.15, 36.3, 0.6
# (the boxes overlap a little and never share a plane)
nodes = [box('west', -8.5, 12.4, FACE, -NX + 0.05, TOP, 16.5, 'rock', ['bottom']),
         box('east', NX - 0.05, 12.4, FACE, 8.5, TOP, 16.5, 'rock', ['bottom']),
         box('notch', -NX, 12.45, FACE + 0.02, NX, NTOP, N0, 'rock', ['bottom', 'left', 'right']),
         box('lip', -NX, 12.45, N0 - 0.02, NX, TOP - 0.02, 16.48, 'rock', ['bottom', 'left', 'right']),
         box('back', -8.45, 1.5, 6.0, 8.45, 12.5, 16.45, 'rock', ['bottom', 'top'])]
out['shrine_falls_cliff'] = recipe('shrine_falls_cliff', {'rock': ROCK}, nodes, 160)
out['shrine_falls_cliff_col'] = col('shrine_falls_cliff_col', nodes)

for name, r in out.items():
    (HERE / f'{name}.asset.json').write_text(json.dumps(r, indent=1) + '\n')
    print(name)
