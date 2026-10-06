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
- shrine_crown_ladder: the same ladder, 13 m, on the crown deck's pole (core_pole_crown).
- shrine_kick_chimney: the kick chimney's two rock faces, their back and the rest ledge (the grey
  box's, in the falls' rock), with its collision.
- shrine_finial_top: the pagoda's spire carried on 6.0 m up the raised finial pole.
- shrine_wall_coping_8_col, _4_col and _corner_col: the north wall's collision with a steep
  coping instead of a flat top, so a jump and a grab from the terrace do not get onto it.
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

# ---- the stage's stilt ladder, and the crown deck's (13 m, the same make)
def ladder(name, H, budget, W=0.25, R=0.04):
    nodes = [box('rail_w', -W - R, 0, -R, -W + R, H, R, 'wood_dark', ['bottom', 'top']),
             box('rail_e', W - R, 0, -R, W + R, H, R, 'wood_dark', ['bottom', 'top'])]
    k, y = 0, 0.35
    while y < H - 0.1:
        nodes.append(box(f'rung_{k}', -W + R, y - 0.03, -0.03, W - R, y + 0.03, 0.03, 'wood', ['left', 'right', 'bottom']))
        k += 1
        y += 0.5
    out[name] = recipe(name, {'wood': WOOD, 'wood_dark': WOOD_DARK}, nodes, budget,
                       {'levels': [{'distance': 30, 'nodes': nodes[:2]}], 'cull': 120})
ladder('shrine_stilt_ladder', 18.3, 260)
ladder('shrine_crown_ladder', 13.0, 200)

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

# ---- the north wall's coping (alpha fix: the wall stops a jump and a grab, DESIGN.md 12.9)
# Collision only, for the north run's arch_wall_8, _4 and _corner (each drawn as the shrine's): the
# wall's 0.8 m section to 2.45, then a gable to 2.95 at 51 degrees (normal y 0.63, under the 0.8 of a
# floor), so ledge_top() finds no floor to hang from and nothing on the wall's top to stand on. The
# shrine's own collision is a flat top at 2.6 that a jump (2.2) and a grab (1.75) reach from the
# terrace, 3.6 m below. Along x, origin at the middle of the base, as arch_wall_*.
GABLE = [[-0.4, 0.0], [0.4, 0.0], [0.4, 2.45], [0.0, 2.95], [-0.4, 2.45]]
for name, length in (('shrine_wall_coping_8_col', 8.0), ('shrine_wall_coping_4_col', 4.0),
                     ('shrine_wall_coping_corner_col', 0.8)):
    out[name] = col(name, [{'id': 'wall', 'op': 'extrude', 'points': GABLE, 'depth': length, 'material': 'solid',
                            'transform': {'rotate': [0, 90, 0]}}])

# ---- the pagoda's finial, taller (alpha fix: star 1 at 51.5, out of every glide, DESIGN.md 12.9)
# The shrine's pagoda draws its spire to 30.0 over its base (45.0 in the level); the finial pole
# (place/shrine.py) now runs to 51.0, so the spire goes on 6.0 m: a bronze rod with three rings and
# a gold jewel at its tip. Origin at the drawn spire's top; no collision (the pole holds the body).
RISE = 6.0
BRONZE = {'color': '#7a8a70', 'palette': True}
GOLD = {'color': '#d8b048', 'palette': True}
nodes = [{'id': 'rod', 'op': 'cylinder', 'radius': 0.08, 'height': RISE - 0.3, 'segments': 6, 'material': 'bronze',
          'transform': {'translate': [0, (RISE - 0.3) / 2, 0]}}]
for k, y in enumerate((RISE - 2.4, RISE - 1.7, RISE - 1.0)):
    nodes.append({'id': f'ring_{k}', 'op': 'cylinder', 'radius': 0.22 - 0.03 * k, 'height': 0.08, 'segments': 8,
                  'material': 'gold', 'transform': {'translate': [0, y, 0]}})
nodes.append({'id': 'jewel', 'op': 'lathe', 'profile': [[0.0, RISE - 0.4], [0.16, RISE - 0.3], [0.2, RISE - 0.2], [0.12, RISE - 0.1], [0.0, RISE]],
              'segments': 6, 'material': 'gold'})
out['shrine_finial_top'] = recipe('shrine_finial_top', {'bronze': BRONZE, 'gold': GOLD}, nodes, 150,
                                  {'levels': [{'distance': 40, 'nodes': nodes[:1]}], 'cull': 140})

# ---- the kick chimney (alpha fix: the grey box's rock faces, textured, DESIGN.md 12.9)
# Two rock faces 3.0 m apart (x -1.5 and 1.5 from the origin, the chimney's foot on the pool's west
# terrace at 16), 10 m long, closed at the back, a rest ledge 14.4 m up; the top 30 m up, the cliff top
# (46). As gbm_kick_chimney was (make_mountain.py), in the falls' mossy rock; its own collision.
nodes = [box('west', -7.5, -0.5, -5.5, -1.5, 30.0, 5.5, 'rock', ['bottom']),
         box('east', 1.5, -0.5, -5.5, 7.5, 30.0, 5.5, 'rock', ['bottom']),
         box('back', -1.5, -0.5, 4.5, 1.5, 29.98, 6.5, 'rock', ['bottom', 'left', 'right']),
         box('rest', -1.52, 14.4, 3.3, 1.52, 15.0, 4.52, 'rock', ['left', 'right', 'back'])]
out['shrine_kick_chimney'] = recipe('shrine_kick_chimney', {'rock': ROCK}, nodes, 120)
out['shrine_kick_chimney_col'] = col('shrine_kick_chimney_col', nodes)

for name, r in out.items():
    (HERE / f'{name}.asset.json').write_text(json.dumps(r, indent=1) + '\n')
    print(name)
