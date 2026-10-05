"""Draws art/bush.png, art/flowers.png and art/blades.png (32 x 32 cutouts) and writes
town_potted_plants.asset.json: three planters outside a house, left to right a terracotta pot
with an evergreen bush, a white styrofoam box of red and white flowers, and a blue plastic bucket
with strap-leaved plants. 1.4 m wide, 0.5 m deep, 1.0 m tall; planters stand along X, the house wall
is behind them on +Z, the entrance side faces -Z. Needs Pillow. Run: python3 gen_town_potted_plants.py
"""
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
(HERE / 'art').mkdir(exist_ok=True)
rng = random.Random(11)


def rgba(h):
    return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), 255)


def blank():
    return Image.new('RGBA', (32, 32), (0, 0, 0, 0))


def blob(d, cx, cy, rx, ry, cols):
    """A leafy mass: many small ellipses of three greens, darker low and lighter high."""
    for _ in range(46):
        a = rng.uniform(0, 2 * math.pi)
        r = math.sqrt(rng.uniform(0, 1))
        x, y = cx + math.cos(a) * r * rx, cy + math.sin(a) * r * ry
        s = rng.uniform(2.0, 3.4)
        t = (y - (cy - ry)) / (2 * ry)          # 0 top, 1 bottom
        c = cols[2] if t > 0.66 else cols[0] if t < 0.3 else cols[1]
        if rng.random() < 0.18:
            c = cols[(cols.index(c) + 1) % 3]
        d.ellipse([x - s, y - s * 0.8, x + s, y + s * 0.8], fill=rgba(c))


def snap(im):
    """Hard alpha: transparent or opaque."""
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            if px[x, y][3] < 128:
                px[x, y] = (0, 0, 0, 0)
            else:
                px[x, y] = px[x, y][:3] + (255,)


def draw_bush():
    im = blank()
    d = ImageDraw.Draw(im)
    blob(d, 16, 17, 14, 13, ['#4f6a3a', '#3c5a34', '#2e4a2e'])
    for _ in range(7):      # a few azalea-pink buds, late October
        x, y = rng.randrange(6, 26), rng.randrange(6, 24)
        d.rectangle([x, y, x + 1, y + 1], fill=rgba('#e0788c'))
    snap(im)
    im.save(HERE / 'art' / 'bush.png')


def draw_flowers():
    im = blank()
    d = ImageDraw.Draw(im)
    blob(d, 16, 23, 14, 8, ['#4f6a3a', '#3c5a34', '#2e4a2e'])
    for x, col in ((6, '#d8462a'), (11, '#ece4d2'), (16, '#d8462a'), (21, '#ece4d2'), (26, '#d8462a'),
                   (9, '#ece4d2'), (23, '#d8462a')):
        top = rng.randrange(6, 14)
        d.line([x, top + 3, x, 20], fill=rgba('#3c5a34'))
        d.ellipse([x - 2, top - 1, x + 2, top + 3], fill=rgba(col))
        d.point([x, top + 1], fill=rgba('#d8b048'))
    snap(im)
    im.save(HERE / 'art' / 'flowers.png')


def draw_blades():
    im = blank()
    d = ImageDraw.Draw(im)
    for ang, ln, w in ((-34, 22, 3), (-16, 29, 4), (0, 31, 4), (15, 27, 4), (33, 21, 3), (-26, 17, 3),
                       (26, 16, 3)):
        a = math.radians(ang)
        bx, by = 16, 31
        tx, ty = bx + math.sin(a) * ln, by - math.cos(a) * ln
        nx, ny = math.cos(a), math.sin(a)
        d.polygon([(bx - nx * w, by - ny * w * 0.2), (bx + nx * w, by + ny * w * 0.2), (tx, ty)],
                  fill=rgba('#3c5a34'))
        d.polygon([(bx - nx * (w - 1.5), by), (bx + nx * (w - 1.5), by),
                   (tx - 0.2 * (tx - bx), ty + 0.2 * (by - ty))], fill=rgba('#4f6a3a'))
        d.line([(bx - nx * w, by), (tx, ty)], fill=rgba('#c8c890'))   # pale margin on one side
    snap(im)
    im.save(HERE / 'art' / 'blades.png')


draw_bush()
draw_flowers()
draw_blades()


def outward(v, f):
    c = [sum(p[i] for p in v) / len(v) for i in range(3)]
    out = []
    for face in f:
        a, b, d = v[face[0]], v[face[1]], v[face[2]]
        u = [b[i] - a[i] for i in range(3)]
        w = [d[i] - a[i] for i in range(3)]
        n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
        m = [sum(v[i][j] for i in face) / len(face) - c[j] for j in range(3)]
        out.append(face if sum(n[i] * m[i] for i in range(3)) > 0 else face[::-1])
    return out


def frustum(id_, cx, cz, y0, y1, r0, r1, n, rot, side_mat, top_mat):
    """n-sided pot, bottom open, flat top in top_mat."""
    v = []
    for y, r in ((y0, r0), (y1, r1)):
        for k in range(n):
            a = rot + 2 * math.pi * k / n
            v.append([cx + r * math.cos(a), y, cz + r * math.sin(a)])
    f = [[k, n + k, n + (k + 1) % n, (k + 1) % n] for k in range(n)] + [[n + k for k in range(n)]]
    return {'id': id_, 'op': 'mesh', 'vertices': v, 'faces': outward(v, f),
            'face_materials': [side_mat] * n + [top_mat]}


def star(id_, cx, cz, y0, h, w, mat, yaws, off=0.0):
    """Vertical cards through (cx, cz), one per yaw (degrees), top corners flared by `off`."""
    v, f = [], []
    for i, yaw in enumerate(yaws):
        a = math.radians(yaw)
        ca, sa = math.cos(a), math.sin(a)
        for dx, y in ((-w / 2 - off, y0 + h), (w / 2 + off, y0 + h), (w / 2, y0), (-w / 2, y0)):
            v.append([cx + dx * ca, y, cz - dx * sa])
        f.append([4 * i, 4 * i + 1, 4 * i + 2, 4 * i + 3])
    return {'id': id_, 'op': 'mesh', 'vertices': v, 'faces': f, 'face_materials': [mat] * len(f)}


def card_mat(img):
    return {'color': '#4f6a3a', 'texture': {'image': 'art/%s.png' % img, 'projection': 'fit'},
            'double_sided': True}


recipe = {
    'format': 'mei-asset', 'version': 1, 'name': 'town_potted_plants',
    'budget': {'triangles': 60},
    'materials': {
        'terracotta': {'color': '#b0623a', 'palette': True},
        'soil': {'color': '#4a3a2e', 'palette': True},
        'foam': {'color': '#e4e2dc', 'palette': True},
        'bucket': {'color': '#3a6ab0', 'palette': True},
        'bush': card_mat('bush'),
        'flowers': card_mat('flowers'),
        'blades': card_mat('blades'),
    },
    'lighting': {'mode': 'vertical', 'ambient': 0.55},
    'verification': {'required': True, 'depth': True, 'perspective': True},
    'nodes': [
        frustum('clay_pot', -0.50, 0.0, 0.0, 0.34, 0.12, 0.19, 4, math.radians(30), 'terracotta', 'soil'),
        star('bush', -0.50, 0.0, 0.32, 0.58, 0.60, 'bush', (0, 45, 90, 135), 0.0),
        {'id': 'foam_box', 'op': 'box', 'size': [0.58, 0.28, 0.30], 'material': 'foam', 'open': ['bottom'],
         'faces': {'top': 'soil'}, 'transform': {'translate': [0.08, 0.14, 0.04]}},
        star('flowers_a', -0.08, 0.04, 0.26, 0.36, 0.34, 'flowers', (0, 90)),
        star('flowers_b', 0.24, 0.04, 0.26, 0.36, 0.34, 'flowers', (20, 110)),
        frustum('bucket', 0.56, -0.04, 0.0, 0.34, 0.13, 0.17, 6, 0.0, 'bucket', 'soil'),
        star('blades', 0.56, -0.04, 0.32, 0.72, 0.52, 'blades', (0, 45, 90, 135), 0.05),
    ],
    'lod': {'cull': 50},
}
# pots on the left, a card star of 4 is 8 triangles; flowers are two crossed pairs (4 cards)
with open(HERE / 'town_potted_plants.asset.json', 'w') as fh:
    json.dump(recipe, fh, indent=1)
