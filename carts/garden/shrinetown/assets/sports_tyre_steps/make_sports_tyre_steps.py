#!/usr/bin/env python3
"""Writes the shrine town's tyre steps (spec 3.15, assets.md 4.1 #32) beside this script:
sports_tyre_steps.asset.json and sports_tyre_steps_col.asset.json.

The schoolyard classic (タイヤ跳び): a row of five old truck tyres, painted, half buried
upright in the clay of the sports ground, graded from a small one at -X to a big one at +X. The
row runs along X across a 6.0 x 0.5 m footprint; the tyres' rings face the front (-Z) and back.
Children hop from top to top; so does the player.

Each tyre is one mesh: a flat-topped octagon cut at the ground (the tread, five faces), the
two ring faces drawn with a painted texture whose hole is a cutout, and three faces lining the
hole (unpainted rubber). 24 triangles a tyre.

What the player uses: each tyre's top is a step (collision: a box to the top of the tread, at
least 0.4 x 0.3 m), the tops at 0.35, 0.42, 0.49, 0.57 and 0.67 m, 0.75-0.85 m apart centre
to centre along the row. Nothing else is a route.

Textures: texel grids in the recipe (no images). Run with the standard library:
python3 carts/garden/shrinetown/assets/sports_tyre_steps/make_sports_tyre_steps.py
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = 'sports_tyre_steps'

POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}

# ---- the tyres: circumradius of the octagon, tread width, paint ------------------------------
# Half buried: the octagon's centre at the ground. The top is R cos 22.5.
TYRES = [  # R, tread width, paint
    (0.38, 0.24, 'blue'),
    (0.45, 0.26, 'yellow'),
    (0.53, 0.30, 'red'),
    (0.62, 0.33, 'white'),
    (0.72, 0.38, 'green'),
]
GAP = 0.15                   # between neighbours at the ground
HOLE = 0.58                  # the hole's radius as a part of R (the rim's opening)
C8 = math.cos(math.radians(22.5))

PAINT = {  # base, worn (darker), as the town's playground paint
    'blue': ('#3a6ab0', '#2c5290'),
    'yellow': ('#f0c030', '#c89a20'),
    'red': ('#d8462a', '#a8321e'),
    'white': ('#eceae4', '#bcb8ae'),
    'green': ('#40a060', '#2e7a48'),
}
RUBBER = '#2c2a28'
TEX_W, TEX_H = 32, 16


def r(v):
    return [r(x) for x in v] if isinstance(v, (list, tuple)) else round(v, 4)


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def wind(verts, face, out):
    """The face's corners in the order whose normal points along `out`."""
    n = newell([verts[i] for i in face])
    return list(face) if sum(n[k] * out[k] for k in range(3)) >= 0 else list(reversed(face))


def outline(R):
    """The tread's outline above the ground, right to left: a flat-topped octagon of
    circumradius R centred at the ground, cut there."""
    pts = [(R * C8, 0.0)]
    for k in range(4):
        a = math.radians(22.5 + 45 * k)
        pts.append((R * math.cos(a), R * math.sin(a)))
    pts.append((-R * C8, 0.0))
    return pts


def hole(R):
    """The hole, right to left: a flat-topped hexagon of radius HOLE R, cut at the ground."""
    h = HOLE * R
    return [(h, 0.0), (h / 2, h * math.sqrt(3) / 2), (-h / 2, h * math.sqrt(3) / 2), (-h, 0.0)]


def inside(poly, x, y):
    """Point in the polygon closed along the ground (y = 0)."""
    c = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def hsh(x, y, s):
    v = (x * 374761393 + y * 668265263 + s * 2246822519) & 0xFFFFFFFF
    v = ((v ^ (v >> 13)) * 1274126177) & 0xFFFFFFFF
    return (v ^ (v >> 16)) & 255


def ring_texels(R, seed):
    """The ring face over its bounding rectangle (x -R..R, y top..0): paint, worn paint toward
    the outer shoulder and the ground, black rubber where it has chipped, the hole clear (0)."""
    top = R * math.sin(math.radians(67.5))
    o, h = outline(R), hole(R)
    rows = []
    for ty in range(TEX_H):
        row = ''
        for tx in range(TEX_W):
            x = -R + (tx + 0.5) * 2 * R / TEX_W
            y = top - (ty + 0.5) * top / TEX_H
            if inside(h, x, y):
                row += '0'
                continue
            d = math.hypot(x, y) / R          # 0 at the centre, about 1 at the tread
            k = hsh(tx, ty, seed)
            if d > 0.9 or y < 0.06 or (0.62 < d < 0.68):
                c = '2'                        # the shoulder, the dirt line, the rim's lip
            else:
                c = '1'
            if k < 8 or (y < 0.08 and k < 60):
                c = '3'                        # chipped to the rubber
            row += c
        rows.append(row)
    return rows


def tyre_mesh(i, R, w, paint, x0):
    """One tyre at x0: tread faces (paint), two ring faces (textured ring), the hole's lining."""
    o = [(x0 + x, y) for x, y in outline(R)]
    h = [(x0 + x, y) for x, y in hole(R)]
    zf, zb = -w / 2, w / 2
    verts, faces, mats = [], [], []
    no, nh = len(o), len(h)
    for x, y in o:
        verts.append([x, y, zf])
    for x, y in o:
        verts.append([x, y, zb])
    for x, y in h:
        verts.append([x, y, zf])
    for x, y in h:
        verts.append([x, y, zb])
    F, B, HF, HB = 0, no, 2 * no, 2 * no + nh
    faces.append(wind(verts, list(range(F, F + no)), [0, 0, -1]))
    mats.append('ring_' + paint)
    faces.append(wind(verts, list(range(B, B + no)), [0, 0, 1]))
    mats.append('ring_' + paint)
    for k in range(no - 1):
        mx = (o[k][0] + o[k + 1][0]) / 2 - x0
        my = (o[k][1] + o[k + 1][1]) / 2
        faces.append(wind(verts, [F + k, F + k + 1, B + k + 1, B + k], [mx, my, 0]))
        mats.append('paint_' + paint)
    for k in range(nh - 1):
        mx = (h[k][0] + h[k + 1][0]) / 2 - x0
        my = (h[k][1] + h[k + 1][1]) / 2
        faces.append(wind(verts, [HF + k, HF + k + 1, HB + k + 1, HB + k], [-mx, -my, 0]))
        mats.append('rubber')
    return {'id': 'tyre_%d' % (i + 1), 'op': 'mesh', 'vertices': r(verts), 'faces': faces,
            'face_materials': mats}


def tyre_l1(i, R, w, paint, x0):
    """Level 1: the ring as one double-sided face in the tyre's middle plane, and the tread as
    three faces (a flat-topped half hexagon over the octagon's top and shoulders)."""
    top = R * math.sin(math.radians(67.5))
    t = R * math.cos(math.radians(67.5))
    o = [(x0 + R * C8, 0.0), (x0 + t, top), (x0 - t, top), (x0 - R * C8, 0.0)]
    # the ring face spans the same rectangle as level 0's, so its texture lines up
    ring = [[x0 + R * C8, 0.0, 0.0], [x0 + t, top, 0.0], [x0 - t, top, 0.0], [x0 - R * C8, 0.0, 0.0]]
    verts = [list(p) for p in ring]
    faces = [wind(verts, [0, 1, 2, 3], [0, 0, -1])]
    mats = ['ring_ds_' + paint]
    base = len(verts)
    for x, y in o:
        verts.append([x, y, -w / 2])
    for x, y in o:
        verts.append([x, y, w / 2])
    for k in range(3):
        mx = (o[k][0] + o[k + 1][0]) / 2 - x0
        my = (o[k][1] + o[k + 1][1]) / 2
        faces.append(wind(verts, [base + k, base + k + 1, base + 4 + k + 1, base + 4 + k], [mx, my, 0]))
        mats.append('paint_' + paint)
    return {'id': 'tyre_%d' % (i + 1), 'op': 'mesh', 'vertices': r(verts), 'faces': faces,
            'face_materials': mats}


def layout():
    widths = [2 * R * C8 for R, _, _ in TYRES]
    total = sum(widths) + GAP * (len(TYRES) - 1)
    xs, x = [], -total / 2
    for wd in widths:
        xs.append(x + wd / 2)
        x += wd + GAP
    return xs, total


def main():
    xs, total = layout()
    materials = {'rubber': {'color': RUBBER, 'palette': True}}
    for k, (R, w, paint) in enumerate(TYRES):
        base, worn = PAINT[paint]
        materials['paint_' + paint] = {'color': base, 'palette': True}
        tex = {'texels': ring_texels(R, k + 1), 'colors': ['#000000', base, worn, RUBBER],
               'clear': '#000000', 'projection': 'fit'}
        materials['ring_' + paint] = {'color': base, 'texture': tex}
        materials['ring_ds_' + paint] = {'color': base, 'double_sided': True, 'texture': dict(tex)}

    nodes = [tyre_mesh(k, R, w, p, xs[k]) for k, (R, w, p) in enumerate(TYRES)]
    l1 = [tyre_l1(k, R, w, p, xs[k]) for k, (R, w, p) in enumerate(TYRES)]
    recipe = {
        'format': 'mei-asset', 'version': 1, 'name': NAME,
        'budget': {'triangles': 120},
        'materials': materials, 'lighting': LIGHT, 'verification': POLICY,
        'nodes': nodes,
        'lod': {'levels': [{'distance': 20, 'nodes': l1}], 'cull': 60},
    }
    (HERE / (NAME + '.asset.json')).write_text(json.dumps(recipe, indent=1) + '\n')

    # collision: a step per tyre, the box's top at the tread's top
    col = []
    for k, (R, w, p) in enumerate(TYRES):
        top = R * math.sin(math.radians(67.5))
        sx = max(0.4, 2 * R * math.cos(math.radians(67.5)))
        sz = max(0.3, w)
        col.append({'id': 'step_%d' % (k + 1), 'op': 'box', 'size': r([sx, top, sz]), 'material': 'solid',
                    'open': ['bottom'], 'transform': {'translate': r([xs[k], top / 2, 0])}})
    colr = {'format': 'mei-asset', 'version': 1, 'name': NAME + '_col',
            'materials': {'solid': {'color': '#ffffff', 'palette': True}},
            'lighting': LIGHT, 'verification': POLICY, 'nodes': col}
    (HERE / (NAME + '_col.asset.json')).write_text(json.dumps(colr, indent=1) + '\n')
    for k, (R, w, p) in enumerate(TYRES):
        print('tyre %d: x %.3f, top %.3f, R %.2f, tread %.2f, %s' % (
            k + 1, xs[k], R * math.sin(math.radians(67.5)), R, w, p))
    print('row length %.3f' % total)


if __name__ == '__main__':
    main()
