"""Writes kei_truck.asset.json and kei_truck_col.asset.json beside this script
(python3 make_kei_truck.py): the mikan grower's kei truck, parked in the back alleys (shrine town
spec 3.3; assets.md section 3).

Adapted from the lab model (examples/assets/lab/kei_truck, 648 triangles), whose recipe and
pictures it reads: the cab's mesh is the lab's, as are its sheet (art/kei_truck_sheet.png and its
sheet file, copied), the white paint, the mikan lettering on the doors, the yellow plates, the
crates of mikan, the blue tarp, the broom and the towel on the guard frame. Same size. The cut:
the wheels are lathes with the lab's wheel picture on their outer face (the lab's were 12-sided
cylinders, 176 triangles), the headlamps are the ones already painted on the cab's face, the
bed is one closed mesh (floor, sides, gates and their rims) instead of five boxes, the guard
frame is its picture on one double-sided face, the mud flaps are faces, three crates.

Footprint 1.64 x 3.56 m (with the plates), origin at the middle of the footprint on the ground, the front -Z. The
cab's flat roof is at 1.74 (z -1.49 to -0.44), the bed's floor at 0.68 and its rim at 0.975, the
top crate at 1.27. The collision is boxes: the cab to 1.74, the bed's floor and rims, the crates,
so a player can climb bed, crates, cab roof; it may become a mover. Levels: L1 from 20 m, L2
from 45 m, culled at 100 m.
"""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
LAB = REPO / 'examples' / 'assets' / 'lab' / 'kei_truck' / 'kei_truck.asset.json'
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

BED = dict(x=0.705, xi=0.665, z0=-0.305, z1=1.695, zi0=-0.265, zi1=1.655, y0=0.63, floor=0.68,
           rim=0.975)
WHEELS = [(-1.0, 'f'), (0.95, 'r')]     # z of the axles
WR, WW, WX = 0.27, 0.16, 0.6            # wheel radius, width, centre x


def lab_nodes():
    return {n['id']: n for n in json.loads(LAB.read_text())['nodes']}


def box(id, size, pos, mat, open=None, faces=None, rot=None):
    n = {'id': id, 'op': 'box', 'size': [round(v, 4) for v in size], 'material': mat,
         'transform': {'translate': [round(v, 4) for v in pos]}}
    if rot:
        n['transform']['rotate'] = rot
    if open:
        n['open'] = open
    if faces:
        n['faces'] = faces
    return n


def fit(p, mat, pts):
    """A face drawn with the whole of a `fit` texture over its own bounding rectangle."""
    tmp = ap.Part('tmp')
    tmp.face_uv(mat, pts, 1.0)
    uv = tmp.uv
    u0, u1 = min(a for a, _ in uv), max(a for a, _ in uv)
    v0, v1 = min(b for _, b in uv), max(b for _, b in uv)
    p.face(mat, pts, [((a - u0) / (u1 - u0), (b - v0) / (v1 - v0)) for a, b in uv])


# ---- level 0 -------------------------------------------------------------------------------
def wheels(segments=8, flat=False):
    """Lathes with the lab's wheel on their outer face; `flat`: a shallow cone standing 3.5-5.5
    cm off the cab's side, for the levels whose cab has no wheel arch."""
    out = []
    for z, t in WHEELS:
        for s in (-1, 1):
            if flat:
                prof, x = [[WR, -0.01], [0.0, 0.01]], CX + 0.045
            else:
                prof, x = [[WR, -WW / 2], [WR, WW / 2 - 0.03], [0.0, WW / 2]], WX
            out.append({'id': f"wheel_{t}{'l' if s < 0 else 'r'}", 'op': 'lathe',
                        'segments': segments, 'caps': False, 'material': 'wheel', 'profile': prof,
                        'transform': {'rotate': [0, 0, 90 if s < 0 else -90],
                                      'translate': [s * x, WR, z]}})
    return out


def bed(p, detail=True):
    """The bed as one mesh: the outer sides and gates, the underside, and (detail) the inner
    walls, the rims and the floor."""
    b = BED
    x, xi, z0, z1, zi0, zi1, y0, fl, rim = (b['x'], b['xi'], b['z0'], b['z1'], b['zi0'], b['zi1'],
                                             b['y0'], b['floor'], b['rim'])
    sv = 0.32
    # outer
    p.face_uv('aori', [(x, rim, z0), (x, rim, z1), (x, y0, z1), (x, y0, z0)], 0.5, sv,
              origin=(x, rim, z0))
    p.face_uv('aori', [(-x, rim, z1), (-x, rim, z0), (-x, y0, z0), (-x, y0, z1)], 0.5, sv,
              origin=(-x, rim, z1))
    p.face_uv('aori', [(-x, rim, z0), (x, rim, z0), (x, y0, z0), (-x, y0, z0)], 0.5, sv,
              origin=(-x, rim, z0))
    fit(p, 'gate', [(x, rim, z1), (-x, rim, z1), (-x, y0, z1), (x, y0, z1)])
    if not detail:
        p.face_uv('floor', [(-x, rim - 0.02, z1), (x, rim - 0.02, z1), (x, rim - 0.02, z0),
                            (-x, rim - 0.02, z0)], 0.7)
        return
    p.face('under', [(-x, y0, z0), (x, y0, z0), (x, y0, z1), (-x, y0, z1)])
    # inner walls, facing in
    p.face_uv('aori', [(xi, rim, zi1), (xi, rim, zi0), (xi, fl, zi0), (xi, fl, zi1)], 0.5, sv,
              origin=(xi, rim, zi1))
    p.face_uv('aori', [(-xi, rim, zi0), (-xi, rim, zi1), (-xi, fl, zi1), (-xi, fl, zi0)], 0.5, sv,
              origin=(-xi, rim, zi0))
    p.face_uv('aori', [(-xi, rim, zi1), (xi, rim, zi1), (xi, fl, zi1), (-xi, fl, zi1)], 0.5, sv,
              origin=(-xi, rim, zi1))
    p.face_uv('aori', [(xi, rim, zi0), (-xi, rim, zi0), (-xi, fl, zi0), (xi, fl, zi0)], 0.5, sv,
              origin=(xi, rim, zi0))
    # the rims
    p.face('trim', [(-x, rim, z1), (x, rim, z1), (xi, rim, zi1), (-xi, rim, zi1)])
    p.face('trim', [(xi, rim, zi0), (x, rim, z0), (-x, rim, z0), (-xi, rim, zi0)])
    p.face('trim', [(xi, rim, zi1), (x, rim, z1), (x, rim, z0), (xi, rim, zi0)])
    p.face('trim', [(-xi, rim, zi0), (-x, rim, z0), (-x, rim, z1), (-xi, rim, zi1)])
    p.face_uv('floor', [(-xi, fl, zi1), (xi, fl, zi1), (xi, fl, zi0), (-xi, fl, zi0)], 0.7)


def guard(p):
    """The guard frame behind the cab: the lab's picture of its bars on one double-sided face."""
    z = -0.285
    p.face('guard', [(-0.68, 1.89, z), (0.68, 1.89, z), (0.68, 0.99, z), (-0.68, 0.99, z)],
           [(0, 0), (1, 0), (1, 1), (0, 1)])


def plates(p):
    fit(p, 'plate', [(-0.165, 0.48, -1.805), (0.165, 0.48, -1.805), (0.165, 0.315, -1.805),
                     (-0.165, 0.315, -1.805)])
    fit(p, 'plate', [(0.165, 0.6, 1.755), (-0.165, 0.6, 1.755), (-0.165, 0.435, 1.755),
                     (0.165, 0.435, 1.755)])
    for s in (-1, 1):
        x0, x1 = s * 0.44, s * 0.6
        a, b = (x1, x0) if s > 0 else (x0, x1)
        fit(p, 'tail', [(a, 0.64, 1.735), (b, 0.64, 1.735), (b, 0.52, 1.735), (a, 0.52, 1.735)])
        # the rear mud flaps, behind the wheels
        fx0, fx1 = s * 0.51, s * 0.69
        a, b = (fx0, fx1) if s > 0 else (fx1, fx0)
        p.face('flap', [(a, 0.63, 1.27), (b, 0.63, 1.27), (b, 0.22, 1.27), (a, 0.22, 1.27)])


def cargo():
    def crate(id, x, y, z, yaw):
        return {'id': id, 'op': 'group', 'transform': {'rotate': [0, yaw, 0], 'translate': [x, y, z]},
                'children': [box('shell', [0.36, 0.3, 0.52], [0, 0.15, 0], 'crate',
                                 open=['top', 'bottom']),
                             {'id': 'fruit', 'op': 'mesh', 'material': 'mikan',
                              'vertices': [[-0.18, 0.24, 0.26], [0.18, 0.24, 0.26],
                                           [0.18, 0.24, -0.26], [-0.18, 0.24, -0.26]],
                              'faces': [[0, 1, 2, 3]]}]}
    fl = BED['floor'] - 0.005
    return [crate('crate_a', -0.21, fl, 0.04, 0), crate('crate_b', 0.2, fl, 0.08, 5),
            crate('crate_c', -0.02, fl + 0.295, 0.07, 87),
            box('tarp', [0.46, 0.12, 0.38], [-0.3, fl + 0.06, 1.3], 'tarp', open=['bottom'],
                rot=[0, 12, 0]),
            {'id': 'broom', 'op': 'group', 'transform': {'rotate': [-8, 0, 13], 'translate': [-0.4, fl, 0.7]},
             'children': [{'id': 'twigs', 'op': 'cone', 'radius': 0.11, 'height': 0.36, 'segments': 5,
                           'caps': False, 'material': 'twigs', 'transform': {'translate': [0, 0.18, 0]}},
                          {'id': 'handle', 'op': 'cylinder', 'radius': 0.016, 'height': 1.0,
                           'segments': 3, 'caps': False, 'material': 'handle',
                           'transform': {'translate': [0, 0.82, 0]}}]}]


def level0():
    lab = lab_nodes()
    cab = copy.deepcopy(lab['cab'])
    p = ap.Part('body')
    bed(p)
    guard(p)
    plates(p)
    towel = copy.deepcopy(lab['towel'])
    return [cab, p.node(), towel] + wheels() + [
        box('chassis', [0.9, 0.23, 1.8], [0, 0.515, 0.65], 'under', open=['top']),
        box('bumper_f', [1.48, 0.13, 0.12], [0, 0.4, -1.71], 'trim', open=['front']),
        box('bumper_r', [1.3, 0.08, 0.08], [0, 0.47, 1.68], 'trim', open=['back']),
        box('mirror_l', [0.04, 0.13, 0.09], [-0.8, 1.15, -1.42], 'trim', open=['right', 'bottom']),
        box('mirror_r', [0.04, 0.13, 0.09], [0.8, 1.15, -1.42], 'trim', open=['left', 'bottom']),
    ] + cargo()


# ---- coarser levels -------------------------------------------------------------------------------
SIDE = [(-1.7, 0.42), (-1.7, 1.06), (-1.49, 1.74), (-0.36, 1.74), (-0.36, 0.42)]   # (z, y)
CX = 0.7


def cab_simple(p, detail=True):
    """The cab in 16 triangles (14 without detail, its sides one plain outline each): doors,
    side windows, face, windscreen, roof, back."""
    lower = [(-1.7, 1.06), (-0.36, 1.06), (-0.36, 0.42), (-1.7, 0.42)]     # (z, y), as seen
    upper = [(-1.7, 1.06), (-1.49, 1.74), (-0.36, 1.74), (-0.36, 1.06)]     # from +X
    for s, side in ((1, 'r'), (-1, 'l')):
        def place(poly):
            pts = [(CX, y, z) for z, y in poly]
            return pts if s > 0 else ap.mirror_x(pts)
        if detail:
            fit(p, f'door_{side}', place(lower))
            fit(p, f'sidewin_{side}', place(upper))
        else:
            p.face('paint', place(SIDE))
    fit(p, 'face', [(-CX, 1.06, -1.7), (CX, 1.06, -1.7), (CX, 0.42, -1.7), (-CX, 0.42, -1.7)])
    fit(p, 'windshield', [(-CX, 1.74, -1.49), (CX, 1.74, -1.49), (CX, 1.06, -1.7), (-CX, 1.06, -1.7)])
    p.face('paint', [(-CX, 1.74, -0.36), (CX, 1.74, -0.36), (CX, 1.74, -1.49), (-CX, 1.74, -1.49)])
    back = [(CX, 1.74, -0.36), (-CX, 1.74, -0.36), (-CX, 0.42, -0.36), (CX, 0.42, -0.36)]
    if detail:
        fit(p, 'back', back)
    else:
        p.face('paint', back)


def level1():
    """From 20 m: the cab in 16 triangles, the bed outside and its floor, the crates as one box,
    the guard, the wheels as discs on the sides."""
    p = ap.Part('truck')
    cab_simple(p)
    bed(p, detail=False)
    guard(p)
    fl = BED['floor']
    return [p.node(), box('crates', [0.76, 0.58, 0.52], [-0.01, fl + 0.29, 0.06], 'crate',
                          open=['bottom'])] + wheels(6, flat=True)


def level2():
    """From 45 m: the cab's outline, the bed as an open box, the dark band of the wheels."""
    p = ap.Part('truck')
    cab_simple(p, detail=False)
    bed(p, detail=False)
    pts = [(0.62, 0.63, -1.3), (0.62, 0.63, 1.25), (0.62, 0.0, 1.25), (0.62, 0.0, -1.3)]
    p.face('under', pts)
    p.face('under', ap.mirror_x(pts))
    return [p.node()]


# ---- collision ------------------------------------------------------------------------------------
def collision():
    p = ap.Part('body')
    b = BED
    ap.col_box(p, -0.7, 0.7, 0.0, 1.74, -1.72, -0.26, open=('bottom',))
    ap.col_box(p, -b['x'], b['x'], 0.0, b['floor'], -0.26, b['z1'], open=('bottom', 'back'))
    for s in (-1, 1):                                   # the side rims, 0.2 thick
        x0, x1 = sorted((s * b['x'], s * (b['x'] - 0.2)))
        ap.col_box(p, x0, x1, b['floor'], b['rim'], -0.26, b['z1'], open=('bottom', 'back'))
    ap.col_box(p, -b['x'] + 0.2, b['x'] - 0.2, b['floor'], b['rim'], b['z1'] - 0.2, b['z1'],
               open=('bottom', 'left', 'right'))       # the tailgate
    ap.col_box(p, -0.39, 0.38, b['floor'], b['rim'], -0.22, 0.34, open=('bottom',))   # crates
    ap.col_box(p, -0.28, 0.24, b['rim'], 1.27, -0.11, 0.25, open=('bottom',))
    return [p]


# ---- recipe ---------------------------------------------------------------------------------------
def materials():
    lab = json.loads(LAB.read_text())['materials']
    m = {}
    for k, v in lab.items():
        v = copy.deepcopy(v)
        if 'texture' not in v:
            v['palette'] = True
        m[k] = v
    for k in ('lamp', 'bar'):
        m.pop(k)
    m['paint']['tag'] = 'roof'
    return m


def recipe():
    return {
        'format': 'mei-asset', 'version': 1, 'name': 'kei_truck',
        'budget': {'triangles': 300},
        'sheets': {'kei': {'image': 'art/kei_truck_sheet.png'}},
        'materials': materials(),
        'lighting': ap.LIGHT,
        'verification': ap.POLICY,
        'nodes': level0(),
        'lod': {'levels': [{'distance': 20, 'nodes': level1()},
                           {'distance': 45, 'nodes': level2()}], 'cull': 100, 'band': 2},
    }


def main():
    ap.write(HERE / 'kei_truck.asset.json', recipe())
    ap.write(HERE / 'kei_truck_col.asset.json', ap.col_recipe('kei_truck_col', collision()))


if __name__ == '__main__':
    main()
