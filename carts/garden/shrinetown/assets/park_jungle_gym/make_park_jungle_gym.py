#!/usr/bin/env python3
"""Writes park_jungle_gym.asset.json, park_jungle_gym_col.asset.json,
park_jungle_gym.cameras.json and art/ beside this script (python3 make_park_jungle_gym.py; needs
Pillow): the park's jungle gym (shrine town spec 3.16; assets.md #28), the 1990s painted-pipe
cube, 4 x 4 cells of 0.75 m across and three tiers of 0.8 m (3.0 x 3.0, the top at 2.43).

The pipes are drawn on cutout planes: three standing planes each way (the four sides and the
two middle rows) and the three tiers, so that from any side the lattice has depth: where two
planes cross, their two flat bars make a cross that reads as a pipe. (Every row of pipes as a
plane, five each way, cost 1.4 times the GPU time from 5 m: a cutout's clear texels are still
filled.) The four corner posts and the top's four
edge pipes are geometry, for the silhouette and for the hands. Painted the way they were: green
uprights, a red, a yellow and a blue tier, white clamps at the joints.

Asset frame: origin at the centre of the footprint at the ground; square, so no front.

What the player uses:
- The top, a 3.06 m square floor at TOP (2.43), standable; reached by a jump and a grab of its
  edge, a double jump, or a corner post.
- The corner posts can be poles (x, z = +-1.5, 0 -> TOP); the collision is the solid cube, so a
  player on a pole hangs outside its corner.
"""
import json
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

ART = HERE / 'art'

CELL, N = 0.75, 4
HALF = CELL * N / 2          # 1.5: the outer pipes' centre lines
TEX = 0.05                   # a texel
E = HALF + TEX / 2           # a plane's edge: half a texel past the outer pipes' centres
TIER = 0.8
TOP_C = 2.4                  # the top pipes' centre
TOP = TOP_C + 0.04           # the posts' tops
POST = 0.08                  # the corner posts and edge pipes are drawn thicker than the
PIPE = 0.07                  # lattice's, at least 3 cm proud of the planes through them
GRID = [-HALF + CELL * k for k in range(N + 1)]

COL = {'green': '#40a060', 'red': '#d8462a', 'yellow': '#d8b048', 'blue': '#3a6ab0',
       'clamp': '#dcdcd4'}


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def draw_art():
    """The standing lattice (61 x 48 texels for 3.05 x 2.4 m) and the three level lattices
    (61 x 61 for 3.05 x 3.05), 5 cm a texel, a pipe one texel wide."""
    ART.mkdir(exist_ok=True)
    cols = [round((g + E) / TEX - 0.5) for g in GRID]           # 0, 15, 30, 45, 60
    w = len(range(61))
    tiers = {0: COL['blue'], 16: COL['yellow'], 32: COL['red']}  # rows from the top: 2.4, 1.6, 0.8
    im = Image.new('RGBA', (w, 48), (0, 0, 0, 0))
    px = im.load()
    for c in cols:
        for y in range(48):
            px[c, y] = rgb(COL['green'])
    for r, col in tiers.items():
        for x in range(w):
            px[x, r] = rgb(col)
        for c in cols:
            px[c, r] = rgb(COL['clamp'])
    im.save(ART / 'lattice_side.png')
    for name, col in (('lattice_red', 'red'), ('lattice_yellow', 'yellow'), ('lattice_blue', 'blue')):
        im = Image.new('RGBA', (w, w), (0, 0, 0, 0))
        px = im.load()
        for c in cols:
            for k in range(w):
                px[c, k] = rgb(COL[col])
                px[k, c] = rgb(COL[col])
        for a in cols:
            for b in cols:
                px[a, b] = rgb(COL['clamp'])
        im.save(ART / f'{name}.png')


UV = [(0, 0), (1, 0), (1, 1), (0, 1)]
Y1 = TOP_C + TEX / 2          # 48 rows, the top row's centre at 2.4, the bottom 2.5 cm up
Y0 = Y1 - 48 * TEX


def standing(part, mat, axis, at):
    """A standing lattice plane: across x (axis 'z', at z = at) or across z (axis 'x')."""
    if axis == 'z':
        part.face(mat, [(-E, Y1, at), (E, Y1, at), (E, Y0, at), (-E, Y0, at)], UV)
    else:
        part.face(mat, [(at, Y1, -E), (at, Y1, E), (at, Y0, E), (at, Y0, -E)], UV)


def level(part, mat, y):
    part.face(mat, [(-E, y, E), (E, y, E), (E, y, -E), (-E, y, -E)], UV)


def level0():
    lat = ap.Part('lattice')
    for g in GRID[::2]:
        standing(lat, 'lattice_side', 'z', g)
        standing(lat, 'lattice_side', 'x', g)
    level(lat, 'lattice_red', TIER)
    level(lat, 'lattice_yellow', 2 * TIER)
    level(lat, 'lattice_blue', TOP_C)
    fr = ap.Part('frame')
    h = POST / 2
    for x in (-HALF, HALF):
        for z in (-HALF, HALF):
            fr.box('green', x - h, x + h, 0.0, TOP, z - h, z + h, open=('bottom',))
    p = PIPE / 2
    for s in (-HALF, HALF):
        fr.box('blue', -HALF + h, HALF - h, TOP_C - p, TOP_C + p, s - p, s + p, open=('left', 'right'))
        fr.box('blue', s - p, s + p, TOP_C - p, TOP_C + p, -HALF + h, HALF - h, open=('back', 'front'))
    return [lat, fr]


def level1():
    """From 25 m: the outer four planes, the middle two and the top."""
    lat = ap.Part('lattice')
    for g in (-HALF, 0.0, HALF):
        standing(lat, 'lattice_side', 'z', g)
        standing(lat, 'lattice_side', 'x', g)
    level(lat, 'lattice_blue', TOP_C)
    return [lat]


def collision():
    b = ap.Part('body')
    c = HALF + POST / 2
    ap.col_box(b, -c, c, 0.0, TOP, -c, c, open=('bottom',))
    return [b]


def tex(name):
    return {'color': COL['green'], 'double_sided': True,
            'texture': {'image': f'art/{name}.png', 'projection': 'fit'}}


MATS = {
    'lattice_side': tex('lattice_side'),
    'lattice_red': tex('lattice_red'),
    'lattice_yellow': tex('lattice_yellow'),
    'lattice_blue': tex('lattice_blue'),
    'green': {'color': COL['green'], 'palette': True},
    'blue': {'color': COL['blue'], 'palette': True},
}

CAMERAS = [
    {'name': 'eye', 'eye': [1.2, 1.6, -6.0], 'target': [0, 1.2, 0]},
    {'name': 'corner', 'eye': [-4.5, 1.6, -4.0], 'target': [0, 1.2, 0]},
    {'name': 'close', 'eye': [0.6, 1.2, -2.6], 'target': [0, 1.2, 0]},
    {'name': 'on_top', 'eye': [0.0, 4.0, -1.0], 'target': [0, 1.0, 1.5]},
    {'name': 'above', 'eye': [-5.0, 7.0, -6.0], 'target': [0, 1.0, 0]},
    {'name': 'far', 'eye': [8.0, 3.0, -24.0], 'target': [0, 1.2, 0]},
]


def main():
    draw_art()
    lod = {'levels': [(25, level1())], 'cull': 80, 'band': 2}
    ap.write(HERE / 'park_jungle_gym.asset.json', ap.recipe('park_jungle_gym', MATS, level0(), 150, lod))
    ap.write(HERE / 'park_jungle_gym_col.asset.json', ap.col_recipe('park_jungle_gym_col', collision()))
    (HERE / 'park_jungle_gym.cameras.json').write_text(json.dumps(CAMERAS, indent=1) + '\n')


if __name__ == '__main__':
    main()
