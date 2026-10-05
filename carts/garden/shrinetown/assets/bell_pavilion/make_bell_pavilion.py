"""Writes bell_pavilion.asset.json and bell_pavilion_col.asset.json beside this script
(python3 make_bell_pavilion.py): the shrine's bell pavilion (shoro) in the north-east corner of
the inner precinct, where direction A's pagoda stood (shrine town spec 3.7; assets.md section 3).

Adapted from the lab model (examples/assets/lab/bell_pavilion, 830 triangles) and rebuilt on the
shrine's architecture sheet so it stands with the halls and the gate: a stone base, four
vermilion posts leaning slightly inward, head beams with their ends standing out, and the
hip-and-gable tile roof of the halls (../arch_wall_gate/arch_parts.py) instead of the lab's
pyramid. Kept from the lab: the bronze bell on its beam (now with its bands, nipples and striking
boss painted on), the striking log on two ropes with its pull rope, a lantern at the front
corner, the name plaque ("the bell of time", art/plaque.png, copied from the lab), and a white cat asleep on the base by the steps.

Footprint 4 x 4 m (the eaves; the base is 3.4 x 3.4, 0.6 high, with a step in front), origin at
the middle of the base's foot, the front (-Z) toward the temple's side of the precinct. Posts at
x, z +-1.25; the head beams 2.65-2.95; the bell's mouth at 1.15, its top 2.45. Eaves 2.92-3.12
at +-2.0 (corners turned up 0.15), the hipped skirt at 26 degrees to 3.51, the gable at 28 degrees
to the ridge at 4.15, the ridge cap to 4.33 and its end tiles to 4.5. Every roof plane is
walkable in the collision; the eave is a double jump and a grab from the terrace, or a jump and a
grab from the base.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

BASE = (1.7, 1.7, 0.6)          # half x, half z, top
STEP = (0.75, 0.3, 0.42)        # half width, height, depth
PX = 1.25                       # post centres (x and z)
LEAN = 0.04                     # each post's foot this much further out than its head
PW = 0.22                       # post width
BEAM = (2.65, 2.95)             # head beams
EAVE = (2.0, 2.0, 3.12)         # ex, ez, top
FASCIA, LIFT, CORNER = 0.2, 0.15, 0.8
INNER = (1.2, 1.2, 3.12 + 0.8 * math.tan(math.radians(26)))
RIDGE = INNER[2] + 1.2 * math.tan(math.radians(28))
CEIL = BEAM[1]
BELL = (0.46, 1.15, 1.3)        # mouth radius, mouth height, height
LOG = (0.09, 1.55, -0.98, 0.95)  # radius, height, centre z, length (its back end at the bell)

# The bell's bronze: 16 x 32 texels, one repeat a quarter of the way round and the whole height.
# From the top: the nipples (chi) in rows, a band, the plain middle with its vertical band, a
# band, the striking boss (a lotus disc), the lip. Digit k is colours[k].
BELL_COLORS = ['#3a3226', '#5c4e38', '#6f8a70', '#8a7a52', '#4a6a58']
BELL_TEXELS = [
    '0111111111111110',
    '1131131131131111',
    '1111111111111111',
    '1131131131131111',
    '1111111111111111',
    '1131131131131111',
    '1111111111111111',
    '1131131131131111',
    '1112111111211111',
    '3333333333333333',
    '0000000000000000',
    '1111111111111112',
    '1121111111111112',
    '1111111141111112',
    '1111121111111112',
    '1111111111121112',
    '1211111111111112',
    '1111111141111112',
    '1111111111111112',
    '1112111111111112',
    '0000000000000000',
    '3333333333333333',
    '1111111111111111',
    '1111133333111111',
    '1111300000311111',
    '1111303330311111',
    '1111300000311111',
    '1111133333111111',
    '1111111111111111',
    '0000000000000000',
    '3333333333333333',
    '1111111111111111',
]


def base(p):
    x, z, h = BASE
    p.box('stone', -x, x, 0.0, h, -z, z, open=('bottom',), su=2.4)
    w, sh, d = STEP
    p.box('stone', -w, w, 0.0, sh, -z - d, -z + 0.02, open=('bottom', 'front'), su=2.4)


def posts(p, top=BEAM[1] - 0.02):
    """Four posts, each a frustum leaning in: its foot LEAN further out than its head."""
    h = PW / 2
    y0 = BASE[2] - 0.02
    for sx in (-1, 1):
        for sz in (-1, 1):
            cb = (sx * (PX + LEAN / 2), sz * (PX + LEAN / 2))
            ct = (sx * (PX - LEAN / 2), sz * (PX - LEAN / 2))

            def c(cc, dx, dz, y):
                return (cc[0] + dx * h, y, cc[1] + dz * h)
            for (ax, az), (bx, bz) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)),
                                       ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
                p.face('lacquer', [c(ct, ax, az, top), c(ct, bx, bz, top), c(cb, bx, bz, y0),
                                   c(cb, ax, az, y0)])


def beams(p):
    """The head beams: along X at the front and back, along Z on the sides (2 cm lower, so
    their undersides never share a plane), each standing 0.3 past the posts; the bell beam
    across the middle; and the ceiling over them."""
    y0, y1 = BEAM
    for sz in (-1, 1):
        z0, z1 = sorted((sz * (PX - 0.07), sz * (PX + 0.07)))
        p.box({'*': 'lacquer', 'bottom': 'shade'}, -PX - 0.3, PX + 0.3, y0, y1, z0, z1,
              open=('top',))
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (PX - 0.07), sx * (PX + 0.07)))
        p.box({'*': 'lacquer', 'bottom': 'shade'}, x0, x1, y0 - 0.05, y1 - 0.01, -PX - 0.3,
              PX + 0.3, open=('top',))
    p.box({'*': 'wood', 'bottom': 'black'}, -PX + 0.05, PX - 0.05, 2.7, y1 - 0.03, -0.11, 0.11,
          open=('top', 'left', 'right'))
    c = PX + 0.08
    p.face('wood', [(-c, CEIL, c), (c, CEIL, c), (c, CEIL, -c), (-c, CEIL, -c)])


def roof(p):
    ix, iz, yi, yr = ap.irimoya(p, EAVE, INNER, (PX + 0.08, PX + 0.08, CEIL), RIDGE, CORNER,
                                LIFT, FASCIA)
    ap.bargeboards(p, ix, iz, yi, yr, out=0.1, over=0.15, down=0.16)
    ap.ridge_cap(p, ix + 0.25, RIDGE - 0.1, RIDGE + 0.18, 0.15, oni=(0.22, RIDGE + 0.35, 0.2))


def bell_nodes():
    r, y0, hgt = BELL
    bell = {'id': 'bell', 'op': 'lathe', 'segments': 8, 'material': 'bronze',
            'faces': {'bottom': 'black'},
            'profile': [[r, 0.0], [r - 0.07, 0.72 * hgt], [r - 0.16, 0.9 * hgt], [0.0, hgt]],
            'transform': {'translate': [0, y0, 0]}}
    return [bell]


def bell_fittings(p):
    """The dragon-head hook from the beam, the striking log on its two ropes, the pull rope."""
    top = BELL[1] + BELL[2]
    p.box('black', -0.07, 0.07, top - 0.04, 2.71, -0.05, 0.05, open=('top', 'bottom'))
    r, y, zc, length = LOG
    for z in (-1.1, -0.6):          # behind the front beam (z -1.32 to -1.18)
        p.box('rope', -0.02, 0.02, y + r - 0.02, CEIL - 0.01, z - 0.02, z + 0.02,
              open=('top', 'bottom'))
    z = zc - length / 2 + 0.06
    p.box('rope', -0.025, 0.025, 0.95, y - r + 0.02, z - 0.025, z + 0.025, open=('top',))


def log_nodes():
    r, y, zc, length = LOG
    return [{'id': 'log', 'op': 'cylinder', 'radius': r, 'height': length, 'segments': 6,
             'material': 'wood_new', 'transform': {'rotate': [90, 0, 0], 'translate': [0, y, zc]}}]


def plaque(p):
    """The name plaque on the front beam's face."""
    z = -PX - 0.07
    p.box({'*': 'black', 'back': 'plaque'}, -0.32, 0.32, 2.68, 2.92, z - 0.08, z - 0.02,
          crop={'back': (0, 0, 1, 1)}, open=('front',))


def lantern(p):
    """A paper lantern under the front-left eave."""
    x, z = -1.62, -1.62
    p.box({'*': 'lantern', 'top': 'black', 'bottom': 'black'}, x - 0.15, x + 0.15, 2.25, 2.62,
          z - 0.15, z + 0.15)
    p.box('black', x - 0.02, x + 0.02, 2.62, 2.93, z - 0.02, z + 0.02, open=('top', 'bottom'))


def cat_nodes():
    """A white cat asleep on the base, to the right of the steps."""
    x, y, z = 0.98, BASE[2], -1.48
    return [{'id': 'cat', 'op': 'group', 'transform': {'rotate': [0, -70, 0], 'translate': [x, y, z]},
             'children': [
                 {'id': 'body', 'op': 'sphere', 'radius': 1, 'rings': 3, 'segments': 6,
                  'material': 'plaster',
                  'transform': {'scale': [0.17, 0.12, 0.23], 'translate': [0, 0.09, 0]}},
                 {'id': 'head', 'op': 'sphere', 'radius': 0.09, 'rings': 2, 'segments': 5,
                  'material': 'plaster', 'transform': {'scale': [1, 0.85, 1],
                                                       'translate': [-0.04, 0.1, -0.2]}},
                 {'id': 'ears', 'op': 'group',
                  'modifiers': [{'op': 'mirror', 'axis': 'x', 'offset': -0.04}],
                  'children': [{'id': 'ear', 'op': 'cone', 'radius': 0.03, 'height': 0.07,
                                'segments': 3, 'caps': False, 'material': 'black',
                                'transform': {'translate': [0.0, 0.2, -0.21]}}]}]}]


def level0():
    b, fr, rf, det = ap.Part('base'), ap.Part('frame'), ap.Part('roof'), ap.Part('details')
    base(b)
    posts(fr)
    beams(fr)
    roof(rf)
    bell_fittings(det)
    plaque(det)
    lantern(det)
    return [b, fr, rf, det] + bell_nodes() + log_nodes() + cat_nodes()


def simple_roof(p, mat, end, under):
    """The roof in 16 triangles: the hipped skirt to the inner square, the gable to the ridge,
    the gable ends, and the eave's underside."""
    ex, ez, yh = EAVE
    ix, iz, yi = INNER
    yl = yh - FASCIA
    for P, A, B, Ai, Bi in ((lambda a, y, b: (a, y, -b), ex, ez, ix, iz),
                            (lambda a, y, b: (b, y, a), ez, ex, iz, ix),
                            (lambda a, y, b: (-a, y, b), ex, ez, ix, iz),
                            (lambda a, y, b: (-b, y, -a), ez, ex, iz, ix)):
        pts = [P(-Ai, yi, Bi), P(Ai, yi, Bi), P(A, yl, B), P(-A, yl, B)]
        if mat == 'tile':
            p.face_uv('tile', pts, 2.0, 2.0, origin=P(-A, yl, B))
        else:
            p.face(mat, pts)
    for s in (-1, 1):
        if s < 0:
            pts = [(-ix, RIDGE, 0.0), (ix, RIDGE, 0.0), (ix, yi, -iz), (-ix, yi, -iz)]
        else:
            pts = [(ix, RIDGE, 0.0), (-ix, RIDGE, 0.0), (-ix, yi, iz), (ix, yi, iz)]
        if mat == 'tile':
            p.face_uv('tile', pts, 2.0, 2.0, origin=pts[3])
        else:
            p.face(mat, pts)
    tri = [(ix, RIDGE, 0.0), (ix, yi, iz), (ix, yi, -iz)]
    p.face(end, tri)
    p.face(end, ap.mirror_x(tri))
    if under:
        p.face(under, [(-ex, yl, -ez), (ex, yl, -ez), (ex, yl, ez), (-ex, yl, ez)])


def level1():
    """From 30 m: the base, straight posts, the beams as one band, the roof simple, the bell."""
    p = ap.Part('pavilion')
    x, z, h = BASE
    p.box('stone', -x, x, 0.0, h, -z, z, open=('bottom',), su=2.4)
    for sx in (-1, 1):
        for sz in (-1, 1):
            x0, x1 = sorted((sx * (PX - PW / 2), sx * (PX + PW / 2)))
            z0, z1 = sorted((sz * (PX - PW / 2), sz * (PX + PW / 2)))
            p.box('lacquer', x0, x1, h - 0.02, BEAM[0] + 0.02, z0, z1, open=('bottom', 'top'))
    c = PX + 0.08
    p.box({'*': 'lacquer', 'bottom': 'wood'}, -c, c, BEAM[0], EAVE[2] - FASCIA - 0.02, -c, c,
          open=('top',))
    simple_roof(p, 'tile', 'plaster', 'rafters')
    r, y0, hgt = BELL
    bell = {'id': 'bell', 'op': 'lathe', 'segments': 6, 'caps': False, 'material': 'bronze',
            'profile': [[r, 0.0], [r - 0.1, 0.95], [0.0, hgt]],
            'transform': {'translate': [0, y0, 0]}}
    return [p, bell]


def level2():
    """From 70 m: the roof as a tent over four posts and the base."""
    p = ap.Part('pavilion')
    x, z, h = BASE
    p.box('stone', -x, x, 0.0, h, -z, z, open=('bottom', 'top'), su=2.4)
    simple_roof(p, 'tile_dark', 'tile_dark', 'shade')
    yl = EAVE[2] - FASCIA
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (PX - PW / 2), sx * (PX + PW / 2)))
        p.face('lacquer', [(x0, yl, -PX), (x1, yl, -PX), (x1, h, -PX), (x0, h, -PX)])
        p.face('lacquer', [(x1, yl, PX), (x0, yl, PX), (x0, h, PX), (x1, h, PX)])
        z0, z1 = x0, x1
        p.face('lacquer', [(PX, yl, z0), (PX, yl, z1), (PX, h, z1), (PX, h, z0)])
        p.face('lacquer', [(-PX, yl, z1), (-PX, yl, z0), (-PX, h, z0), (-PX, h, z1)])
    return [p]


def collision():
    p = ap.Part('body')
    x, z, h = BASE
    ap.col_box(p, -x, x, 0.0, h, -z, z, open=('bottom',))
    w, sh, d = STEP
    ap.col_box(p, -w, w, 0.0, sh, -z - d, -z, open=('bottom', 'front'))
    for sx in (-1, 1):
        for sz in (-1, 1):
            ap.col_box(p, sx * PX - 0.11, sx * PX + 0.11, h, BEAM[0], sz * PX - 0.11,
                       sz * PX + 0.11, open=('bottom', 'top'))
    r, y0, hgt = BELL
    ap.col_box(p, -r, r, y0, BEAM[0], -r, r, open=('top',))
    # the roof: a solid from the beams' underside up, its eave a ledge at the fascia's top
    ex, ez, yh = EAVE
    ix, iz, yi = INNER
    yb = BEAM[0]
    ap.col_quad(p, (-ex, yb, -ez), (ex, yb, -ez), (ex, yb, ez), (-ex, yb, ez))
    for P, A, B, Ai, Bi in ((lambda a, y, b: (a, y, -b), ex, ez, ix, iz),
                            (lambda a, y, b: (b, y, a), ez, ex, iz, ix),
                            (lambda a, y, b: (-a, y, b), ex, ez, ix, iz),
                            (lambda a, y, b: (-b, y, -a), ez, ex, iz, ix)):
        ap.col_quad(p, P(-A, yh, B), P(A, yh, B), P(A, yb, B), P(-A, yb, B))           # eave
        ap.col_quad(p, P(-Ai, yi, Bi), P(Ai, yi, Bi), P(A, yh, B), P(-A, yh, B))       # skirt
    ap.col_quad(p, (-ix, RIDGE, 0.0), (ix, RIDGE, 0.0), (ix, yi, -iz), (-ix, yi, -iz))
    ap.col_quad(p, (ix, RIDGE, 0.0), (-ix, RIDGE, 0.0), (-ix, yi, iz), (ix, yi, iz))
    tri = [(ix, RIDGE, 0.0), (ix, yi, iz), (ix, yi, -iz)]
    p.face('solid', tri)
    p.face('solid', ap.mirror_x(tri))
    return [p]


def main():
    mats = ap.materials('tile', 'rafters', 'stone', 'lacquer', 'shade', 'plaster',
                        'tile_dark', 'black', 'wood', 'wood_new', 'lantern',
                        extra={'rope': {'color': '#c8aa5a', 'palette': True},
                               'plaque': {'color': '#2c2a28',
                                          'texture': {'image': 'art/plaque.png',
                                                      'projection': 'fit'}},
                               'bronze': {'color': '#5c4e38', 'tag': 'bell',
                                          'texture': {'texels': BELL_TEXELS,
                                                      'colors': BELL_COLORS,
                                                      'projection': 'cylindrical',
                                                      'scale': [0.72, BELL[2]]}}})
    lod = {'levels': [(30, level1()), (70, level2())], 'cull': 160, 'band': 2}
    ap.write(HERE / 'bell_pavilion.asset.json',
             ap.recipe('bell_pavilion', mats, level0(), 400, lod))
    ap.write(HERE / 'bell_pavilion_col.asset.json',
             ap.col_recipe('bell_pavilion_col', collision()))


if __name__ == '__main__':
    main()
