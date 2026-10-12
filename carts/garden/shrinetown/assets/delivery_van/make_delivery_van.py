"""Writes delivery_van.asset.json and delivery_van_col.asset.json beside this script
(python3 make_delivery_van.py): the Tsuruya parcel van, parked on the front road (shrine town
spec 3.5; assets.md section 3).

Adapted from the lab model (examples/assets/lab/delivery_van, 396 triangles): the same body
outline with its wheel arches, the lab's pictures for the sides, front, back and windscreen (in
art/, copied), the roof rails with three parcels, the green furoshiki bundle, the antenna, and
the ginger cat sitting on the back parcel. The cut: wheels are lathes with a tyre-and-hub disc
painted on their outer face (texels below) instead of capped cylinders with hub plates, the
bumpers and mirrors lose their hidden sides, the bundle is coarser. The picture plates stand
3.5 cm off the body (the lab's 1.2 cm tied in the depth buffer from a few metres).

Footprint 1.96 x 4.84 m (the mirrors and bumpers; the body is 1.7 x 4.5), origin at the middle
of the footprint on the ground, the front -Z. The body's flat roof is at 2.08 from z -1.78 to the
back (2.25); parcels stand on it to 2.47 and 2.53. The collision is the body's outline extruded
(roof flat and walkable, the windscreen a wall) and the two big parcels, so the van can be
climbed and ridden if it becomes a mover. Levels: L1 from 20 m, L2 from 45 m, culled at 100 m.
"""
import copy
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
LAB = REPO / 'examples' / 'assets' / 'lab' / 'delivery_van' / 'delivery_van.asset.json'
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

HALF = 0.85                     # the body's half width
PLATE = 0.035                   # picture plates stand this far off the body
ROOF = 2.08
WHEELS = [(-1.35, 'f'), (1.2, 'r')]
WR, WW, WX = 0.33, 0.24, 0.735
# the body's side outline (x along the van, + to the front; y up), as the lab's extrusion
OUTLINE = [[-2.25, 0.3], [-1.64, 0.3], [-1.511, 0.611], [-1.2, 0.74], [-0.889, 0.611], [-0.76, 0.3],
           [0.91, 0.3], [1.039, 0.611], [1.35, 0.74], [1.661, 0.611], [1.79, 0.3], [2.25, 0.3],
           [2.25, 1.0], [2.18, 1.3], [1.78, 2.02], [1.7, ROOF], [-2.25, ROOF]]
OUTLINE_SIMPLE = [[-2.25, 0.3], [2.25, 0.3], [2.25, 1.0], [2.18, 1.3], [1.75, ROOF], [-2.25, ROOF]]


def wheel_texels():
    """16 x 16: the black tyre, a grey rim line, the chrome hub with five dark nuts."""
    rows = []
    for j in range(16):
        row = ''
        for i in range(16):
            dx, dy = i - 7.5, j - 7.5
            r = math.hypot(dx, dy)
            if r > 7.6:
                c = '0'
            elif r > 5.0:
                c = '0'
            elif r > 4.2:
                c = '1'
            else:
                c = '2'
                ang = math.atan2(dy, dx)
                if 1.6 < r < 3.0 and any(abs(((ang - k * 2 * math.pi / 5 + math.pi) % (2 * math.pi)) - math.pi) < 0.32
                                         for k in range(5)):
                    c = '3'
                if r < 1.0:
                    c = '3'
            row += c
        rows.append(row)
    return rows


def box(id, size, pos, mat, open=None, rot=None):
    n = {'id': id, 'op': 'box', 'size': [round(v, 4) for v in size], 'material': mat,
         'transform': {'translate': [round(v, 4) for v in pos]}}
    if rot:
        n['transform']['rotate'] = rot
    if open:
        n['open'] = open
    return n


def quad(id, mat, corners):
    """A plate: corners top-left, top-right, bottom-right, bottom-left as seen from outside."""
    return {'id': id, 'op': 'mesh', 'material': mat,
            'vertices': [[round(v, 4) for v in c] for c in corners], 'faces': [[0, 1, 2, 3]]}


def body(outline, id='body', faces=None):
    n = {'id': id, 'op': 'extrude', 'material': 'paint', 'depth': 2 * HALF, 'points': outline,
         'transform': {'rotate': [0, 90, 0]}}
    if faces:
        n['faces'] = faces
    return n


def windscreen():
    """On the windscreen's slope (outline (2.18, 1.3) to (1.78, 2.02)), PLATE out along its normal."""
    (z0, y0), (z1, y1) = (-2.18, 1.3), (-1.78, 2.02)
    L = math.hypot(z1 - z0, y1 - y0)
    tz, ty = (z1 - z0) / L, (y1 - y0) / L
    nz, ny = -ty, tz                      # outward: toward -Z and up
    a, b = 0.08, 0.86                     # the part of the slope it covers

    def at(t):
        return (z0 + tz * L * t + nz * PLATE, y0 + ty * L * t + ny * PLATE)
    (zb, yb), (zt, yt) = at(a), at(b)
    return quad('windshield', 'windshield', [[-0.76, yt, zt], [0.76, yt, zt], [0.76, yb, zb],
                                             [-0.76, yb, zb]])


def plates():
    x, zf, zr = HALF + PLATE, -2.25 - PLATE, 2.25 + PLATE
    return [quad('side_r', 'side_r', [[x, 1.98, -2.2], [x, 1.98, 2.2], [x, 0.78, 2.2], [x, 0.78, -2.2]]),
            quad('side_l', 'side_l', [[-x, 1.98, 2.2], [-x, 1.98, -2.2], [-x, 0.78, -2.2], [-x, 0.78, 2.2]]),
            quad('front', 'front', [[-0.8, 0.98, zf], [0.8, 0.98, zf], [0.8, 0.5, zf], [-0.8, 0.5, zf]]),
            quad('rear', 'rear', [[0.82, 2.0, zr], [-0.82, 2.0, zr], [-0.82, 0.62, zr], [0.82, 0.62, zr]])]


def wheels(segments=8, flat=False):
    """Lathes with the disc on their outer face; `flat`: a shallow cone standing 3-5 cm off the
    body's side, for the levels whose outline has no wheel arches."""
    out = []
    for z, t in WHEELS:
        for s in (-1, 1):
            if flat:
                prof, x = [[WR, -0.01], [0.0, 0.01]], HALF + 0.04
            else:
                prof, x = [[WR, -WW / 2], [WR, WW / 2 - 0.04], [0.0, WW / 2]], WX
            out.append({'id': f"wheel_{t}{'l' if s < 0 else 'r'}", 'op': 'lathe',
                        'segments': segments, 'caps': False, 'material': 'wheel', 'profile': prof,
                        'transform': {'rotate': [0, 0, 90 if s < 0 else -90],
                                      'translate': [s * x, WR, z]}})
    return out


def roof_load(lab):
    keep = {k: copy.deepcopy(lab[k]) for k in ('rails', 'parcel_a', 'parcel_b', 'parcel_c',
                                               'antenna', 'cat')}
    for k in ('parcel_a', 'parcel_b', 'parcel_c'):
        keep[k]['open'] = ['bottom']
    cat = keep['cat']
    for c in cat['children']:
        if c['id'] == 'cat_body':                   # 5 cm in from the parcel's back face
            c['transform']['translate'][2] = 1.3
        if c['id'] == 'cat_head':                   # 3.5 cm in from the body's sides
            c['size'][0] = 0.13
            c['transform']['translate'][2] = 1.12
        if c['id'] == 'cat_ears':
            c['children'][0]['caps'] = False
        if c['id'] == 'cat_tail':
            c['caps'] = False
    bundle = copy.deepcopy(lab['bundle'])
    bundle['segments'] = 4
    return [keep['rails'], keep['parcel_a'], keep['parcel_b'], keep['parcel_c'], bundle,
            keep['antenna'], cat]


def level0():
    lab = {n['id']: n for n in json.loads(LAB.read_text())['nodes']}
    return ([body(OUTLINE), windscreen()] + plates() + wheels() + [
        box('bumper_f', [1.78, 0.2, 0.16], [0, 0.38, -2.31], 'bumper', open=['front', 'bottom']),
        box('bumper_r', [1.78, 0.2, 0.16], [0, 0.38, 2.31], 'bumper', open=['back', 'bottom']),
        box('mirror_l', [0.1, 0.22, 0.12], [-0.95, 1.5, -1.92], 'trim', open=['right', 'bottom']),
        box('mirror_r', [0.1, 0.22, 0.12], [0.95, 1.5, -1.92], 'trim', open=['left', 'bottom']),
        copy.deepcopy(lab['flaps']),
    ] + roof_load(lab))


def level1():
    """From 20 m: the outline without its arches, the pictures, the wheels as discs on the
    sides, the parcels as one box."""
    return ([body(OUTLINE_SIMPLE), windscreen()] + plates() + wheels(6, flat=True) +
            [box('parcels', [0.6, 0.38, 1.9], [0, ROOF + 0.18, 0.45], 'box1', open=['bottom'])])


def level2():
    """From 45 m: the outline with its sides painted on, the windscreen."""
    return [body(OUTLINE_SIMPLE, faces={'front': 'side_r', 'back': 'side_l'}), windscreen()]


def collision():
    p = ap.Part('body')
    out = [(-2.25, 0.0), (2.25, 0.0), (2.25, 1.0), (1.75, ROOF), (-2.25, ROOF)]   # (x fwd, y)
    pts = [(-x, y) for x, y in out]                   # in z (front -Z)
    # sides: the outline at x = +-HALF, split into quads no longer than 2 m
    zs = [-2.25, -1.75, -0.6, 0.6, 1.75, 2.25]

    def top(z):
        if z <= -1.75:
            return 1.0 + (z + 2.25) / 0.5 * (ROOF - 1.0)
        return ROOF
    for k in range(len(zs) - 1):
        za, zb = zs[k], zs[k + 1]
        ap.col_quad(p, (HALF, top(za), za), (HALF, top(zb), zb), (HALF, 0.0, zb), (HALF, 0.0, za))
        ap.col_quad(p, (-HALF, top(zb), zb), (-HALF, top(za), za), (-HALF, 0.0, za), (-HALF, 0.0, zb))
        if za >= -1.75:
            ap.col_quad(p, (-HALF, ROOF, zb), (HALF, ROOF, zb), (HALF, ROOF, za), (-HALF, ROOF, za))
    ap.col_quad(p, (-HALF, ROOF, -1.75), (HALF, ROOF, -1.75), (HALF, 1.0, -2.25), (-HALF, 1.0, -2.25))
    ap.col_quad(p, (-HALF, 1.0, -2.25), (HALF, 1.0, -2.25), (HALF, 0.0, -2.25), (-HALF, 0.0, -2.25))
    ap.col_quad(p, (HALF, ROOF, 2.25), (-HALF, ROOF, 2.25), (-HALF, 0.0, 2.25), (HALF, 0.0, 2.25))
    del pts
    # the two big parcels on the roof (parcel_a 0.62 x 0.4 x 0.5, parcel_c 0.45 cube)
    ap.col_box(p, -0.43, 0.19, ROOF, ROOF + 0.39, -0.6, -0.1, open=('bottom',))
    ap.col_box(p, -0.425, 0.025, ROOF, ROOF + 0.445, 1.1, 1.5, open=('bottom',))
    return [p]


def materials():
    lab = json.loads(LAB.read_text())['materials']
    m = {}
    for k, v in lab.items():
        v = copy.deepcopy(v)
        if 'texture' not in v:
            v['palette'] = True
        if 'texture' in v:
            v['texture'].pop('bits', None)      # every texture 4-bit: the level's palettes (TEXTURES.md)
        m[k] = v
    m.pop('chrome')
    m['paint']['tag'] = 'roof'
    m['wheel'] = {'color': '#26262a', 'texture': {'texels': wheel_texels(),
                                                  'colors': ['#26262a', '#5a5e64', '#c8ced4', '#6a7078'],
                                                  'projection': 'disc'}}
    m.pop('tire')
    m['flap'] = {'color': '#26262a', 'palette': True, 'double_sided': True}
    return m


def recipe():
    lv0 = level0()
    for n in lv0:
        if n['id'] == 'flaps':
            n['children'][0]['material'] = 'flap'
    return {
        'format': 'mei-asset', 'version': 1, 'name': 'delivery_van',
        'budget': {'triangles': 300},
        'materials': materials(),
        'lighting': ap.LIGHT,
        'verification': ap.POLICY,
        'nodes': lv0,
        'lod': {'levels': [{'distance': 20, 'nodes': level1()},
                           {'distance': 45, 'nodes': level2()}], 'cull': 100, 'band': 2},
    }


def main():
    ap.write(HERE / 'delivery_van.asset.json', recipe())
    ap.write(HERE / 'delivery_van_col.asset.json', ap.col_recipe('delivery_van_col', collision()))


if __name__ == '__main__':
    main()
