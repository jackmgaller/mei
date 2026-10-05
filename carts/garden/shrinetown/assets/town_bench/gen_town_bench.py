"""Draws art/seat.png and art/backrest.png and writes town_bench.asset.json and its _col.

A 1990s street bench: two wedge-shaped concrete ends, wooden slats on top. 1.56 m long, 0.50 m
deep, seat 0.46 m, back 0.80 m; the sitter faces -Z. Needs Pillow for the two textures.
Run: python3 gen_town_bench.py
"""
import json
import random
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
random.seed(7)

WOOD = ['#b08a5e', '#a07c52', '#8a6446']
GAP = '#3a2c20'


def rgba(h):
    return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), 255)


def slats(name, w, h, count, gap):
    """count slats stacked in v, each with a few darker grain streaks, thin dark gaps."""
    im = Image.new('RGBA', (w, h), rgba(GAP))
    px = im.load()
    per = h // count
    for s in range(count):
        base = rgba(WOOD[s % 2])
        for y in range(s * per + gap, (s + 1) * per):
            for x in range(w):
                px[x, y] = base
        for _ in range(w // 8):  # grain streaks along u
            y = random.randrange(s * per + gap, (s + 1) * per)
            x0 = random.randrange(0, w)
            for x in range(x0, min(w, x0 + random.randrange(5, 16))):
                px[x, y] = rgba(WOOD[2])
        for _ in range(2):  # a screw head near each end
            pass
    # butt joints / bolt dots at the ends of each slat
    for s in range(count):
        y = s * per + gap + (per - gap) // 2
        for x in (3, w - 4):
            px[x, y] = rgba('#5a5e58')
    im.save(HERE / 'art' / name)


(HERE / 'art').mkdir(exist_ok=True)
slats('seat.png', 64, 16, 3, 1)       # top of the seat: 3 slats over 0.42 m, 64 texels over 1.5 m
slats('backrest.png', 64, 16, 2, 1)   # 2 wider slats over 0.30 m

HX = 0.75   # slats reach 3 cm into the ends
CHEEK = [(-0.20, 0.0), (0.26, 0.0), (0.30, 0.80), (-0.20, 0.42)]   # (z, y) of an end


def cheek(id_, x0, x1):
    v = [[x, y, z] for x in (x0, x1) for z, y in CHEEK]
    f = [[0, 1, 2, 3], [7, 6, 5, 4], [0, 3, 7, 4], [1, 5, 6, 2], [3, 2, 6, 7]]
    # make faces outward: x0 side faces -X; check winding with a normal test
    out = []
    cx = [sum(p[i] for p in v) / len(v) for i in range(3)]
    for face in f:
        a, b, d = (v[face[0]], v[face[1]], v[face[2]])
        u = [b[i] - a[i] for i in range(3)]
        w = [d[i] - a[i] for i in range(3)]
        n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
        m = [sum(v[i][j] for i in face) / len(face) - cx[j] for j in range(3)]
        out.append(face if sum(n[i] * m[i] for i in range(3)) > 0 else face[::-1])
    return {'id': id_, 'op': 'mesh', 'vertices': v, 'faces': out,
            'face_materials': ['concrete'] * len(out)}


recipe = {
    'format': 'mei-asset', 'version': 1, 'name': 'town_bench',
    'budget': {'triangles': 40},
    'materials': {
        'concrete': {'color': '#c8c4b8', 'palette': True},
        'wood': {'color': '#8a6446', 'palette': True},
        'seat': {'color': '#b08a5e', 'texture': {'image': 'art/seat.png', 'projection': 'fit'}},
        'backrest': {'color': '#b08a5e', 'texture': {'image': 'art/backrest.png', 'projection': 'fit'}},
    },
    'lighting': {'mode': 'vertical', 'ambient': 0.5},
    'verification': {'required': True, 'depth': True, 'perspective': True},
    'nodes': [
        cheek('end_left', -0.78, -0.71),
        cheek('end_right', 0.71, 0.78),
        {'id': 'seat', 'op': 'box', 'size': [2 * HX, 0.05, 0.48], 'material': 'wood',
         'open': ['left', 'right', 'bottom'], 'faces': {'top': 'seat'},
         'transform': {'translate': [0, 0.435, -0.01]}},
        {'id': 'backrest', 'op': 'box', 'size': [2 * HX, 0.30, 0.04], 'material': 'wood',
         'open': ['left', 'right'], 'faces': {'back': 'backrest', 'front': 'backrest'},
         'transform': {'rotate': [12, 0, 0], 'translate': [0, 0.66, 0.255]}},
    ],
    'lod': {'cull': 60},
}
with open(HERE / 'town_bench.asset.json', 'w') as fh:
    json.dump(recipe, fh, indent=1)

col = {
    'format': 'mei-asset', 'version': 1, 'name': 'town_bench_col',
    'materials': {'solid': {'color': '#ffffff', 'palette': True}},
    'lighting': {'mode': 'vertical', 'ambient': 0.5},
    'verification': {'required': True, 'depth': True, 'perspective': True},
    'nodes': [
        {'id': 'body', 'op': 'box', 'size': [1.56, 0.46, 0.46], 'material': 'solid',
         'open': ['bottom'], 'transform': {'translate': [0, 0.23, 0.0]}},
        {'id': 'back', 'op': 'box', 'size': [1.5, 0.4, 0.1], 'material': 'solid',
         'open': ['bottom'], 'transform': {'translate': [0, 0.6, 0.25]}},
    ],
}
with open(HERE / 'town_bench_col.asset.json', 'w') as fh:
    json.dump(col, fh, indent=1)
