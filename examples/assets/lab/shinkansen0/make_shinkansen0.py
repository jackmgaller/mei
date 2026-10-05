#!/usr/bin/env python3
"""Writes shinkansen0.asset.json and art/shinkansen0_sheet.png (with its .sheet.json).

A 0-series shinkansen front car (type 21), 25 m long, nose toward -Z, rail top at y 0.
The body shell is generated here as explicit meshes with hand UVs so that the livery
painted into the sheet lines up with the geometry: run it after changing either.

    python3 examples/assets/lab/shinkansen0/make_shinkansen0.py
"""
import json
import math
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- body section
# Half cross-section, skirt bottom to roof centre (x >= 0).
PROFILE = [(1.52, 0.88), (1.64, 1.15), (1.69, 1.60), (1.69, 2.20), (1.68, 2.75),
           (1.60, 3.25), (1.38, 3.70), (0.80, 3.98), (0.00, 4.05)]
Y0, Y1, HALF = 0.88, 4.05, 1.69

_arc = [0.0]
for (x0, y0), (x1, y1) in zip(PROFILE, PROFILE[1:]):
    _arc.append(_arc[-1] + math.hypot(x1 - x0, y1 - y0))
ARC = [d / _arc[-1] for d in _arc]          # 0 at the skirt, 1 at the roof centre


def y_at_arc(a):
    """World height of the body profile at arc fraction a."""
    for i in range(len(ARC) - 1):
        if a <= ARC[i + 1]:
            t = (a - ARC[i]) / (ARC[i + 1] - ARC[i])
            return PROFILE[i][1] + t * (PROFILE[i + 1][1] - PROFILE[i][1])
    return PROFILE[-1][1]


# ---------------------------------------------------------------- nose
Z_TIP, Z_REAR = -12.5, 12.5
NOSE = 5.6
Z_JOIN = Z_TIP + NOSE
CAP_Y = 1.62


def nose_dims(s):
    """Half width, bottom and top of the section at s (0 tip, 1 full body)."""
    w = HALF * (1 - (1 - s) ** 2.6) ** 0.46
    top = CAP_Y + (Y1 - CAP_Y) * (1 - (1 - s) ** 2.2) ** 0.6
    bot = Y0 + 0.22 * (1 - s) ** 3
    return w, bot, top


def section_point(s, k):
    """Point k (0..8 on the half profile) of the section at s, right side."""
    w, bot, top = nose_dims(s)
    xn, yn = PROFILE[k][0] / HALF, (PROFILE[k][1] - Y0) / (Y1 - Y0)
    th = math.radians(-62 + 152 * ARC[k])
    xe, ye = math.cos(th), 0.5 + 0.5 * math.sin(th) / math.sin(math.radians(90))
    ye = (ye - (0.5 + 0.5 * math.sin(math.radians(-62)))) / (1 - (0.5 + 0.5 * math.sin(math.radians(-62))))
    e = min(1.0, (1 - s) ** 1.3)
    x = w * (xn + (xe - xn) * e)
    y = bot + (top - bot) * (yn + (ye - yn) * e)
    if k == len(PROFILE) - 1:
        x = 0.0
    return x, y


def ring(s, z):
    """Closed ring of 17 points: right skirt up to the roof centre, down the left."""
    right = [section_point(s, k) for k in range(len(PROFILE))]
    pts = [(x, y, z) for x, y in right]
    pts += [(-x, y, z) for x, y in reversed(right[:-1])]
    return pts


RING_A = ARC + list(reversed(ARC[:-1]))      # arc fraction of each ring point
RING_SIDE = [1] * len(PROFILE) + [-1] * (len(PROFILE) - 1)
NR = len(RING_A)

NOSE_S = [1.0, 0.92, 0.84, 0.76, 0.68, 0.60, 0.52, 0.44, 0.36, 0.28, 0.21, 0.15, 0.10, 0.06]

# ---------------------------------------------------------------- livery
IVORY = (239, 233, 214)
IVORY_SHADE = (214, 208, 190)
BLUE = (28, 60, 146)
GLASS = (34, 44, 60)
GLASS_HI = (104, 132, 160)
SEAT = (240, 238, 228)
SEAM = (150, 146, 134)
HANDLE = (120, 120, 124)

SKIRT_TOP_Y = 1.30
BAND_LO_Y, BAND_HI_Y = 1.98, 2.66
WIN_LO_Y, WIN_HI_Y = 2.08, 2.56


def a_of_y(y):
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if y_at_arc(mid) < y:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


SKIRT_A = a_of_y(SKIRT_TOP_Y)
BAND_LO_A, BAND_HI_A = a_of_y(BAND_LO_Y), a_of_y(BAND_HI_Y)
WIN_LO_A, WIN_HI_A = a_of_y(WIN_LO_Y), a_of_y(WIN_HI_Y)

TILE_W, TILE_H = 16, 64
NOSE_W, NOSE_H = 128, 64


def body_column(a):
    """Livery of the body at arc fraction a (plain wall)."""
    if a < SKIRT_A:
        return BLUE
    if BAND_LO_A <= a < BAND_HI_A:
        return BLUE
    return IVORY


def tile(kind):
    img = Image.new('RGB', (TILE_W, TILE_H))
    for row in range(TILE_H):
        a = 1 - (row + 0.5) / TILE_H
        for col in range(TILE_W):
            c = body_column(a)
            if kind == 'window' and WIN_LO_A <= a < WIN_HI_A and 3 <= col <= 12:
                top = a > WIN_HI_A - 0.012
                bottom = a < WIN_LO_A + 0.012
                corner = (col in (3, 12)) and (top or bottom)
                if not corner:
                    c = GLASS
                    if col in (4, 5) and a > WIN_HI_A - 0.05:
                        c = GLASS_HI
                    if 6 <= col <= 8 and a < WIN_LO_A + 0.02:
                        c = SEAT      # the white cover on a seat back
            if kind == 'door':
                door_lo, door_hi = a_of_y(0.95), a_of_y(2.95)
                if door_lo <= a < door_hi and col in (3, 12):
                    c = SEAM
                if door_lo <= a < door_hi and 4 <= col <= 11:
                    if WIN_LO_A <= a < WIN_HI_A and 6 <= col <= 9:
                        c = GLASS if not (col == 6 and a > WIN_HI_A - 0.04) else GLASS_HI
                    elif a < SKIRT_A or BAND_LO_A <= a < BAND_HI_A:
                        c = BLUE
                    else:
                        c = IVORY
                    if col == 10 and a_of_y(1.55) <= a < a_of_y(1.85):
                        c = HANDLE
                if abs(a - door_hi) < 0.008 and 3 <= col <= 12:
                    c = SEAM
            if a > a_of_y(3.95) and kind != 'nose':
                c = IVORY_SHADE if (col % 8 == 0) else c   # roof panel seams
            img.putpixel((col, row), c)
    return img


# Where the headlights go: (s, arc fraction) on the nose.
LAMP_S, LAMP_A = 0.13, 0.44
WS_S0, WS_S1 = 0.30, 0.48           # windscreen, along the nose
WS_A = 0.57                         # windscreen lower edge, as an arc fraction
CAB_S0, CAB_S1 = 0.80, 0.92         # cab side window


def nose_color(s, a):
    w, bot, top = nose_dims(s)
    # skirt: rises toward the front into a blue lip under the light cover
    skirt = SKIRT_A + 0.16 * max(0.0, min(1.0, (0.55 - s) / 0.45)) ** 1.6
    if a < skirt:
        return BLUE
    # blue patch around each headlight
    ds = (s - LAMP_S) * NOSE / (2 * w + 1e-6) * 2.0
    da = (a - LAMP_A)
    if (ds * 1.0) ** 2 + (da * 3.2) ** 2 < 0.075 ** 2 * 3.2 ** 2 and s < 0.4:
        return BLUE
    # windscreen frame and glass
    if WS_S0 - 0.035 <= s <= WS_S1 + 0.03 and a >= WS_A - 0.05:
        if WS_S0 <= s <= WS_S1 and a >= WS_A and a < 0.985:
            if s > WS_S1 - 0.025 and a < WS_A + 0.12:
                return GLASS_HI
            return GLASS
        return BLUE
    # window band from the body, rising to meet the windscreen frame
    lo = BAND_LO_A
    hi = BAND_HI_A
    if s < 0.80:
        k = (0.80 - s) / (0.80 - WS_S1)
        k = max(0.0, min(1.0, k))
        lo = BAND_LO_A + (WS_A - 0.05 - BAND_LO_A) * k
        hi = BAND_HI_A + (1.0 - BAND_HI_A) * k
    if s >= WS_S1 and lo <= a < hi:
        if CAB_S0 <= s <= CAB_S1 and WIN_LO_A <= a < WIN_HI_A:
            return GLASS_HI if s > CAB_S1 - 0.02 else GLASS
        return BLUE
    return IVORY


def nose_texture():
    img = Image.new('RGB', (NOSE_W, NOSE_H))
    for row in range(NOSE_H):
        s = 1 - (row + 0.5) / NOSE_H
        for col in range(NOSE_W):
            u = (col + 0.5) / NOSE_W
            a = 1 - abs(u - 0.5) * 2
            img.putpixel((col, row), nose_color(s, a))
    return img


def write_sheet():
    art = os.path.join(HERE, 'art')
    os.makedirs(art, exist_ok=True)
    sheet = Image.new('RGB', (NOSE_W + 3 * TILE_W, NOSE_H))
    sheet.paste(nose_texture(), (0, 0))
    for i, kind in enumerate(('window', 'door', 'plain')):
        sheet.paste(tile(kind), (NOSE_W + i * TILE_W, 0))
    sheet.save(os.path.join(art, 'shinkansen0_sheet.png'))
    cells = {'nose': [0, 0, NOSE_W, NOSE_H]}
    for i, kind in enumerate(('window', 'door', 'plain')):
        cells[kind] = [NOSE_W + i * TILE_W, 0, TILE_W, TILE_H]
    with open(os.path.join(art, 'shinkansen0_sheet.sheet.json'), 'w') as f:
        f.write('{"format": "mei-sheet", "version": 1,\n "cells": {\n')
        f.write(',\n'.join('  "%s": %s' % (k, json.dumps(v)) for k, v in cells.items()))
        f.write('\n }}\n')


# ---------------------------------------------------------------- meshes
def r(v):
    return round(v, 4)


def shell_nose():
    verts, uvs, faces, mats = [], [], [], []
    rings = []
    for s in NOSE_S:
        z = Z_TIP + s * NOSE
        base = len(verts)
        for i, (x, y, zz) in enumerate(ring(s, z)):
            verts.append([r(x), r(y), r(zz)])
            a = RING_A[i]
            u = 0.5 * a if RING_SIDE[i] > 0 else 1 - 0.5 * a
            uvs.append([r(u), r(1 - s)])
        rings.append(base)
    for j in range(len(rings) - 1):
        a0, a1 = rings[j], rings[j + 1]          # a0 rearward, a1 forward
        for i in range(NR):
            i2 = (i + 1) % NR
            # outward winding: viewed from outside the ring runs counter-clockwise
            m = 'under' if i == NR - 1 else 'nose'
            faces += [[a0 + i, a1 + i, a1 + i2], [a0 + i, a1 + i2, a0 + i2]]
            mats += [m, m]
    tip = len(verts)
    verts.append([0.0, r(CAP_Y), r(Z_TIP)])
    uvs.append([0.5, 1.0])
    last = rings[-1]
    for i in range(NR):
        i2 = (i + 1) % NR
        faces.append([last + i, tip, last + i2])
        mats.append('under' if i == NR - 1 else 'nose')
    return {'id': 'nose', 'op': 'mesh', 'material': 'nose', 'vertices': verts,
            'faces': faces, 'face_materials': mats, 'uvs': uvs}


BAY = (Z_REAR - Z_JOIN) / 20
# bay index -> tile; ring boundaries where the tile changes (and one midway)
BAYS = ['door', 'plain'] + ['window'] * 16 + ['door', 'plain']
CUTS = [0, 1, 2, 10, 18, 19, 20]


def shell_body():
    verts, uvs, faces, mats = [], [], [], []
    rings = []
    for c in CUTS:
        z = Z_JOIN + c * BAY
        base = len(verts)
        for i, (x, y, zz) in enumerate(ring(1.0, z)):
            verts.append([r(x), r(y), r(zz)])
            uvs.append([float(c), r(1 - RING_A[i])])
        rings.append(base)
    for j in range(len(CUTS) - 1):
        a0, a1 = rings[j], rings[j + 1]
        kind = BAYS[CUTS[j]]
        for i in range(NR):
            i2 = (i + 1) % NR
            faces.append([a1 + i, a0 + i, a0 + i2, a1 + i2])
            mats.append('under' if i == NR - 1 else kind)
    # rear end wall
    last = rings[-1]
    faces.append([last + i for i in range(NR)])
    mats.append('endwall')
    return {'id': 'body', 'op': 'mesh', 'material': 'plain', 'vertices': verts,
            'faces': faces, 'face_materials': mats, 'uvs': uvs}


def lamp_nodes():
    """Two headlights on the nose, each turned to face out of the surface."""
    out = []
    s, k = LAMP_S, None
    # interpolate the right-side point at arc LAMP_A
    for i in range(len(ARC) - 1):
        if LAMP_A <= ARC[i + 1]:
            t = (LAMP_A - ARC[i]) / (ARC[i + 1] - ARC[i])
            p0, p1 = section_point(s, i), section_point(s, i + 1)
            x, y = p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1])
            break
    z = Z_TIP + s * NOSE
    # surface direction: estimate dx/dz from the next section
    w0 = nose_dims(s)[0]
    w1 = nose_dims(s + 0.04)[0]
    yaw = math.degrees(math.atan2(w1 - w0, 0.04 * NOSE))     # how far the surface faces sideways
    face_yaw = 90 - yaw
    for side in (1, -1):
        out.append({'id': 'lamp_r' if side > 0 else 'lamp_l', 'op': 'cylinder',
                    'radius': 0.15, 'height': 0.12, 'segments': 8, 'material': 'lamp',
                    'transform': {'rotate': [90, side * (-face_yaw), 0],
                                  'translate': [r(side * (x - 0.02)), r(y), r(z + 0.02)]}})
    return out


def wheelset(id_, z):
    return {'id': id_, 'op': 'cylinder', 'radius': 0.455, 'height': 0.14, 'segments': 10,
            'material': 'wheel', 'transform': {'rotate': [0, 0, 90], 'translate': [0.75, 0.455, z]}}


def bogie(id_, zc):
    return {'id': id_, 'op': 'group', 'children': [
        {'id': 'wheels', 'op': 'group', 'children': [wheelset('front', zc - 1.25), wheelset('rear', zc + 1.25)],
         'modifiers': [{'op': 'mirror', 'axis': 'x'}]},
        {'id': 'frames', 'op': 'group', 'children': [
            {'id': 'side_frame', 'op': 'box', 'size': [0.16, 0.42, 3.5], 'material': 'bogie',
             'transform': {'translate': [1.0, 0.56, zc]}}],
         'modifiers': [{'op': 'mirror', 'axis': 'x'}]},
        {'id': 'bolster', 'op': 'box', 'size': [1.80, 0.3, 0.7], 'material': 'bogie',
         'transform': {'translate': [0, 0.72, zc]}},
    ]}


def recipe():
    tex = lambda cell, proj: {'sheet': 'livery', 'cell': cell, 'projection': proj}
    return {
        'format': 'mei-asset', 'version': 1, 'name': 'shinkansen0',
        'budget': {'vertices': 1400, 'triangles': 1600},
        'sheets': {'livery': {'image': 'art/shinkansen0_sheet.png'}},
        'materials': {
            'nose': {'color': '#efe9d6', 'tag': 'body', 'texture': tex('nose', 'fit')},
            'window': {'color': '#efe9d6', 'tag': 'body', 'texture': tex('window', 'box')},
            'door': {'color': '#efe9d6', 'tag': 'body', 'texture': tex('door', 'box')},
            'plain': {'color': '#efe9d6', 'tag': 'body', 'texture': tex('plain', 'box')},
            'endwall': {'color': '#e2dcc8', 'tag': 'body'},
            'under': {'color': '#3a3c42', 'tag': 'under'},
            'gangway': {'color': '#2c2d31'},
            'roofbox': {'color': '#d8d4c6', 'tag': 'body'},
            'cap': {'color': '#fff6dc', 'class': 'emissive', 'tag': 'light'},
            'lamp': {'color': '#fff2b0', 'class': 'emissive', 'tag': 'light'},
            'plough': {'color': '#55585f'},
            'bogie': {'color': '#2e3036'},
            'wheel': {'color': '#6a6d74'},
        },
        'lighting': {'mode': 'vertical', 'ambient': 0.5},
        'verification': {'required': True, 'depth': True, 'perspective': True},
        'nodes': [
            shell_nose(),
            shell_body(),
            {'id': 'cap', 'op': 'sphere', 'radius': 0.36, 'rings': 5, 'segments': 10, 'material': 'cap',
             'transform': {'scale': [1, 1, 0.75], 'translate': [0, CAP_Y, Z_TIP + 0.08]}},
            *lamp_nodes(),
            {'id': 'plough', 'op': 'mesh', 'material': 'plough',
             'vertices': [[0, 0.32, -11.1], [0.95, 0.32, -10.2], [-0.95, 0.32, -10.2],
                          [0, 1.02, -11.45], [1.15, 0.98, -10.0], [-1.15, 0.98, -10.0],
                          [0.95, 0.32, -9.6], [-0.95, 0.32, -9.6], [1.15, 0.98, -9.6], [-1.15, 0.98, -9.6]],
             'faces': [[0, 1, 4], [0, 4, 3], [2, 0, 3], [2, 3, 5], [1, 6, 8], [1, 8, 4],
                       [7, 2, 5], [7, 5, 9], [0, 2, 7, 6, 1], [6, 7, 9, 8]]},
            bogie('bogie_front', -4.9),
            bogie('bogie_rear', 10.6),
            {'id': 'equipment', 'op': 'box', 'size': [2.6, 0.5, 11.8], 'material': 'under', 'open': ['top'],
             'transform': {'translate': [0, 0.66, 2.85]}},
            {'id': 'gangway', 'op': 'box', 'size': [1.1, 2.3, 0.3], 'material': 'gangway', 'open': ['back'],
             'transform': {'translate': [0, 2.15, Z_REAR + 0.15]}},
            {'id': 'roof_units', 'op': 'group', 'children': [
                {'id': 'unit', 'op': 'box', 'size': [1.3, 0.24, 1.6], 'material': 'roofbox',
                 'transform': {'translate': [0, 4.08, -3.0]}}],
             'modifiers': [{'op': 'array', 'count': 5, 'step': [0, 0, 3.2]}]},
        ],
    }


def main():
    write_sheet()
    with open(os.path.join(HERE, 'shinkansen0.asset.json'), 'w') as f:
        json.dump(recipe(), f, separators=(',', ':'))
        f.write('\n')


if __name__ == '__main__':
    main()
