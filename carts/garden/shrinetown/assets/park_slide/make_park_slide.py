#!/usr/bin/env python3
"""Writes park_slide.asset.json, park_slide_col.asset.json, park_slide.cameras.json and art/
beside this script (python3 make_park_slide.py; needs Pillow): the park's big slide (shrine
town spec 3.16; assets.md #27), a 1990s painted-steel slide: a blue post tower with a ladder at
the back, a deck at 2.4 m with yellow hoop guards, and a stainless chute with red sides that
runs down at 35 degrees to a flat run-out.

Asset frame: origin at the centre of the footprint at the ground; the chute runs downhill toward
-Z (the front, where children land), the tower and its ladder are at +Z.

What the player uses:
- The ladder is a pole: x 0, z LADDER_Z (the plane of the back posts), 0 -> DECK (2.4).
- The deck at DECK, 0.9 m square, guarded on its two sides by walls up to RAIL (3.24); the guard
  rails' tops are standable in collision (0.2 m wide).
- The chute's bed, from the deck down to the run-out, is tagged `slide` in the collision (the
  35-degree slope and the 17.5-degree bend); the flat run-out at 0.42 is an ordinary floor.
- Under the chute's high end the player can walk (1.8 m clear 1 m in front of the tower).
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

ART = HERE / 'art'

POST = 0.08                 # post section
PX = 0.45                   # posts at x +-PX
ZF_RAW, ZB_RAW = 1.85, 2.75  # front and back posts (before centring)
DECK = 2.40
RAIL = 3.24                 # top of the posts and the guard rails
SLOPE = 35.0
# the chute's bed: top (inside the deck), slope end, bend, run-out end (z, y), before centring
A_RAW = (2.0, 2.38)
B_Y = 0.55
RUNOUT_Y = 0.415
RUNOUT_LEN = 0.75
HALF_IN, HALF_OUT, WALL, UNDER = 0.25, 0.31, 0.22, 0.05


def chute_path():
    az, ay = A_RAW
    t = math.tan(math.radians(SLOPE))
    bz = az - (ay - B_Y) / t
    half = math.radians(SLOPE / 2)
    seg = (B_Y - RUNOUT_Y) / math.sin(half)
    cz = bz - seg * math.cos(half)
    dz = cz - RUNOUT_LEN
    return [(az, ay), (bz, B_Y), (cz, RUNOUT_Y), (dz, RUNOUT_Y)]


PATH_RAW = chute_path()
ZMIN_RAW, ZMAX_RAW = PATH_RAW[-1][0], ZB_RAW + POST / 2
SHIFT = -(ZMIN_RAW + ZMAX_RAW) / 2
ZF, ZB = ZF_RAW + SHIFT, ZB_RAW + SHIFT
PATH = [(z + SHIFT, y) for z, y in PATH_RAW]
LADDER_Z = ZB
LADDER_TOP = DECK - 0.07       # the ladder's plane stops under the deck's back face

COL = {
    'blue': '#3a6ab0', 'yellow': '#d8b048', 'red': '#d8462a', 'stainless': '#c8ccd0',
    'steel': '#8e9498',
}


# --------------------------------------------------------------------------------------------
# art

def rgb(h, a=255):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (a,)


def draw_art():
    ART.mkdir(exist_ok=True)
    # ladder: the rungs between the back posts, 0.9 x 2.4 m, 5 cm a texel; a rung every 0.3 m.
    im = Image.new('RGBA', (18, 48), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for k in range(1, 8):
        y = 48 - 6 * k
        d.line([(1, y), (16, y)], fill=rgb('#d8dce0'))
        d.line([(1, y + 1), (16, y + 1)], fill=rgb('#8e9498'))
    im.save(ART / 'ladder.png')

    # the deck's side guard: 0.9 x 0.84 m between the posts, a yellow hoop and a mid rail.
    im = Image.new('RGBA', (32, 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y_ = rgb('#d8b048')
    yd = rgb('#a8862e')
    d.ellipse([5, 2, 26, 27], outline=y_, width=2)
    d.line([(1, 15), (30, 15)], fill=y_, width=2)
    d.line([(1, 29), (30, 29)], fill=yd)
    im.save(ART / 'guard.png')



# --------------------------------------------------------------------------------------------
# geometry helpers

def add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def mul(a, s):
    return tuple(c * s for c in a)


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def planar(pts):
    n = newell(pts)
    ln = math.sqrt(ap.dot(n, n))
    n = [c / ln for c in n]
    ext = max(math.dist(a, b) for a in pts for b in pts)
    return all(abs(ap.dot(ap.sub(q, pts[0]), n)) <= 1e-6 * ext * 0.5 for q in pts)


def face_out(part, mat, pts, want, tris=None):
    """Add a polygon wound so that its normal points along `want`. Corners are rounded as the
    recipe stores them; a polygon no longer planar after that goes in as triangles (`tris`, index
    triples, or a fan)."""
    pts = [tuple(ap.r4(c) for c in q) for q in pts]
    flip = ap.dot(newell(pts), want) < 0   # the kit's outward normal is (b - a) x (c - a)
    if planar(pts):
        part.face(mat, list(reversed(pts)) if flip else pts)
        return
    for t in tris or [(0, k, k + 1) for k in range(1, len(pts) - 1)]:
        tri = [pts[i] for i in t]
        if ap.dot(newell(tri), want) < 0:
            tri.reverse()
        part.face(mat, tri)


def frames(path):
    """Per section: the point (x 0, y, z), the bed's up normal (mitred) and the tangent."""
    out = []
    norms = []
    for i in range(len(path) - 1):
        (z0, y0), (z1, y1) = path[i], path[i + 1]
        L = math.hypot(z1 - z0, y1 - y0)
        tz, ty = (z1 - z0) / L, (y1 - y0) / L
        norms.append(((ty, -tz), (tz, ty)))
    for i, (z, y) in enumerate(path):
        if i == 0:
            n, t = norms[0]
        elif i == len(path) - 1:
            n, t = norms[-1]
        else:
            (na, ta), (nb, tb) = norms[i - 1], norms[i]
            n = (na[0] + nb[0], na[1] + nb[1])
            c = math.hypot(*n)
            cos_half = c / 2
            n = (n[0] / c / cos_half, n[1] / c / cos_half)
            t = ((ta[0] + tb[0]) / 2, (ta[1] + tb[1]) / 2)
        out.append(((0.0, y, z), (0.0, n[1], n[0]), (0.0, t[1], t[0])))
    return out


def sweep(part, path, profile, mats, cap_mat, caps=(True, True)):
    """Sweep a closed counterclockwise (x, h) profile along a (z, y) path in the YZ plane."""
    fr = frames(path)
    secs = [[add(add(o, (x, 0, 0)), mul(n, h)) for x, h in profile] for o, n, _ in fr]
    m = len(profile)
    for i in range(len(secs) - 1):
        nrm = mul(add(fr[i][1], fr[i + 1][1]), 0.5)
        for k in range(m):
            (x0, h0), (x1, h1) = profile[k], profile[(k + 1) % m]
            ox, oh = (h1 - h0), -(x1 - x0)
            want = add((ox, 0, 0), mul(nrm, oh))
            pts = [secs[i][k], secs[i][(k + 1) % m], secs[i + 1][(k + 1) % m], secs[i + 1][k]]
            mat = mats[k] if isinstance(mats, (list, tuple)) else mats
            face_out(part, mat, pts, want)
    tris = CAP_TRIS if m == 8 else None
    if caps[0]:
        face_out(part, cap_mat, secs[0], mul(fr[0][2], -1), tris)
    if caps[1]:
        face_out(part, cap_mat, secs[-1], fr[-1][2], tris)
    return secs


PROFILE = [(-HALF_OUT, -UNDER), (HALF_OUT, -UNDER), (HALF_OUT, WALL), (HALF_IN, WALL),
           (HALF_IN, 0.0), (-HALF_IN, 0.0), (-HALF_IN, WALL), (-HALF_OUT, WALL)]
CAP_TRIS = [(0, 1, 4), (0, 4, 5), (1, 2, 3), (1, 3, 4), (0, 5, 6), (0, 6, 7)]
PROFILE_MATS = ['red', 'red', 'red', 'stainless', 'stainless', 'stainless', 'red', 'red']


def bed_y(z):
    for (z0, y0), (z1, y1) in zip(PATH, PATH[1:]):
        if z1 <= z <= z0:
            return y0 + (y1 - y0) * (z - z0) / (z1 - z0)
    raise ValueError(z)


# --------------------------------------------------------------------------------------------
# the levels

def level0():
    p = ap.Part('tower')
    h = POST / 2
    for x in (-PX, PX):
        for z in (ZF, ZB):
            p.box('blue', x - h, x + h, 0.0, RAIL, z - h, z + h, open=('bottom', 'top'))
    # the deck, its edges on the posts' centre lines (4 cm inside their faces)
    p.box({'*': 'steel'}, -PX, PX, DECK - 0.06, DECK, ZF, ZB)
    # guard rails along the two sides at the posts' tops, their ends inside the posts
    for x in (-PX, PX):
        p.box('yellow', x - 0.03, x + 0.03, RAIL - 0.09, RAIL - 0.03, ZF + h, ZB - h,
              open=('back', 'front'))
    g = ap.Part('guards')
    for s in (-1, 1):
        x = s * PX
        g.face('guard', [(x, RAIL - 0.09, ZF), (x, RAIL - 0.09, ZB), (x, DECK, ZB), (x, DECK, ZF)],
               [(0, 0), (1, 0), (1, 1), (0, 1)])
    lad = ap.Part('ladder')
    lad.face('ladder', [(PX, LADDER_TOP, ZB), (-PX, LADDER_TOP, ZB), (-PX, 0.0, ZB), (PX, 0.0, ZB)],
             [(0, 0), (1, 0), (1, 1), (0, 1)])
    ch = ap.Part('chute')
    sweep(ch, PATH, PROFILE, PROFILE_MATS, 'red')
    # supports: a leg under the slope's end, a plinth under the run-out
    sup = ap.Part('supports')
    bz = PATH[1][0]
    by = PATH[1][1] - UNDER
    sup.box('blue', -0.22, 0.22, 0.0, by + 0.03, bz + 0.03, bz + 0.09, open=('bottom', 'top'))
    dz = PATH[-1][0]
    sup.box('blue', -0.22, 0.22, 0.0, RUNOUT_Y - UNDER + 0.02, dz + 0.12, dz + 0.36,
            open=('bottom', 'top'))
    return [p, g, lad, ch, sup]


def level1():
    """From 25 m: posts as three-sided prisms, the deck's top, the guards and ladder, and the
    chute as a channel without its underside."""
    p = ap.Part('tower')
    h = POST / 2
    for x in (-PX, PX):
        for z in (ZF, ZB):
            c = [(x + h * math.cos(a), z + h * math.sin(a)) for a in
                 (math.radians(90), math.radians(210), math.radians(330))]
            for k in range(3):
                (x0, z0), (x1, z1) = c[k], c[(k + 1) % 3]
                mx, mz = (x0 + x1) / 2 - x, (z0 + z1) / 2 - z
                face_out(p, 'blue', [(x0, RAIL, z0), (x1, RAIL, z1), (x1, 0.0, z1), (x0, 0.0, z0)],
                         (mx, 0, mz))
    p.face('steel', [(-PX, DECK, ZB), (PX, DECK, ZB), (PX, DECK, ZF), (-PX, DECK, ZF)])
    for x in (-PX, PX):
        p.face('guard', [(x, RAIL - 0.09, ZF), (x, RAIL - 0.09, ZB), (x, DECK, ZB), (x, DECK, ZF)],
               [(0, 0), (1, 0), (1, 1), (0, 1)])
    p.face('ladder', [(PX, LADDER_TOP, ZB), (-PX, LADDER_TOP, ZB), (-PX, 0.0, ZB), (PX, 0.0, ZB)],
           [(0, 0), (1, 0), (1, 1), (0, 1)])
    ch = ap.Part('chute')
    fr = frames(PATH)
    prof = [(HALF_OUT, -UNDER), (HALF_OUT, WALL), (-HALF_OUT, WALL), (-HALF_OUT, -UNDER)]
    secs = [[add(add(o, (x, 0, 0)), mul(n, hh)) for x, hh in prof] for o, n, _ in fr]
    for i in range(len(secs) - 1):
        nrm = mul(add(fr[i][1], fr[i + 1][1]), 0.5)
        for k, (mat, want) in enumerate([('red', (1, 0, 0)), ('stainless', nrm), ('red', (-1, 0, 0))]):
            pts = [secs[i][k], secs[i][k + 1], secs[i + 1][k + 1], secs[i + 1][k]]
            face_out(ch, mat, pts, want)
    face_out(ch, 'red', secs[-1], fr[-1][2])
    return [p, ch]


def collision():
    s = ap.Part('body')
    h = 0.1
    for x in (-PX, PX):
        for z in (ZF, ZB):
            ap.col_box(s, x - h, x + h, 0.0, DECK - 0.2, z - h, z + h, open=('bottom', 'top'))
    ap.col_box(s, -PX - h, PX + h, DECK - 0.2, DECK, ZF - h, ZB + h, open=())
    for x in (-PX, PX):
        ap.col_box(s, x - h, x + h, DECK, RAIL, ZF - h, ZB + h, open=('bottom',))
    # the chute: a slab 0.2 under the bed, its slope and bend tagged slide
    c = ap.Part('chute')
    fr = frames(PATH)
    hw = HALF_OUT
    secs = [[add(add(o, (x, 0, 0)), mul(n, hh)) for x, hh in
             [(-hw, -0.2), (hw, -0.2), (hw, 0.0), (-hw, 0.0)]] for o, n, _ in fr]
    for i in range(len(secs) - 1):
        nrm = mul(add(fr[i][1], fr[i + 1][1]), 0.5)
        top = 'chute' if i < len(secs) - 2 else 'solid'
        for k, (mat, want) in enumerate([('solid', mul(nrm, -1)), ('solid', (1, 0, 0)),
                                         (top, nrm), ('solid', (-1, 0, 0))]):
            pts = [secs[i][k], secs[i][(k + 1) % 4], secs[i + 1][(k + 1) % 4], secs[i + 1][k]]
            face_out(c, mat, pts, want)
    face_out(c, 'solid', secs[-1], fr[-1][2])
    # the run-out's plinth down to the ground
    dz = PATH[-1][0]
    ap.col_box(s, -0.25, 0.25, 0.0, RUNOUT_Y - 0.2, dz, dz + 0.5, open=('bottom', 'top'))
    return [s, c]


# --------------------------------------------------------------------------------------------

MATS = {
    'blue': {'color': COL['blue'], 'palette': True},
    'yellow': {'color': COL['yellow'], 'palette': True},
    'red': {'color': COL['red'], 'palette': True},
    'stainless': {'color': COL['stainless'], 'palette': True},
    'steel': {'color': COL['steel'], 'palette': True},
    'guard': {'color': COL['yellow'], 'double_sided': True,
              'texture': {'image': 'art/guard.png', 'projection': 'fit'}},
    'ladder': {'color': '#c8ccd0', 'double_sided': True,
               'texture': {'image': 'art/ladder.png', 'projection': 'fit'}},
}

CAMERAS = [
    {'name': 'eye_front', 'eye': [1.5, 1.6, -6.5], 'target': [0, 1.2, 0]},
    {'name': 'side', 'eye': [6.0, 1.6, 0.0], 'target': [0, 1.3, 0]},
    {'name': 'ladder', 'eye': [-1.2, 1.6, 5.5], 'target': [0, 1.5, 2.0]},
    {'name': 'from_deck', 'eye': [0.0, 4.0, 2.4], 'target': [0, 0.4, -2.0]},
    {'name': 'above', 'eye': [-5.0, 7.0, -5.0], 'target': [0, 1.0, 0]},
    {'name': 'far', 'eye': [10.0, 3.0, -28.0], 'target': [0, 1.2, 0]},
]


def main():
    draw_art()
    lod = {'levels': [(25, level1())], 'cull': 90, 'band': 2}
    r = ap.recipe('park_slide', MATS, level0(), 150, lod)
    ap.write(HERE / 'park_slide.asset.json', r)
    col = ap.recipe('park_slide_col', {'solid': {'color': '#ffffff', 'palette': True},
                                       'chute': {'color': '#e0c040', 'palette': True,
                                                 'tag': 'slide'}}, collision())
    ap.write(HERE / 'park_slide_col.asset.json', col)
    (HERE / 'park_slide.cameras.json').write_text(json.dumps(CAMERAS, indent=1) + '\n')
    print('footprint z', round(PATH[-1][0], 3), round(ZB + POST / 2, 3), 'ladder z', round(LADDER_Z, 3),
          'path', [(round(z, 3), round(y, 3)) for z, y in PATH])


if __name__ == '__main__':
    main()
