"""Writes cemetery_jizo_hall.asset.json and cemetery_jizo_hall_col.asset.json beside this script
(python3 make_cemetery_jizo_hall.py; the textures first with python3 art/draw_jizo.py): the small
jizo hall at the top of the cemetery's terraces (shrine town spec 3.14; assets.md #25).

Footprint 5 x 5 m (the eaves), origin at the middle of the base, the open front toward -Z. A
cut-granite base 3.6 m square and 0.4 high (the cemetery stone, ../cemetery_terrace_wall_12/art/)
with a step in front; a plain wooden hall 3 m square, plank walls on three sides, the front a
doorway between two lattice bays; inside, on a dark altar, the six jizo (roku jizo) in red bibs
and caps, and an offering box in the doorway. A pyramidal tile roof (hogyo) on all four sides at
28 degrees, from eaves at 2.70 (all round, a ledge to grab) to 4.03, hip ridges down its corners,
and a bronze jewel finial to 4.95. The roof is walkable all over; the hall stands on the top
terrace (16.2), where glide G7 lands.

Textures: the shrine's tile, planks and inner wood (carts/garden/shrine/assets/art/), the
cemetery stone, and art/jizo.png and art/lattice.png (drawn by art/draw_jizo.py).
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

STONE = '../cemetery_terrace_wall_12/art/'
B, BH = 1.8, 0.4                 # the base's half size and height
PO, PW = 1.45, 0.16              # posts' centres and width
WO, WI = 1.49, 1.41              # walls' outer and inner planes
TOP = 2.58                       # the walls' top, the soffit
FR = 2.2                         # the doorway's head, the frieze's foot
E, EY = 2.5, 2.70                # the eaves' half size and top
APEX = EY + E * math.tan(math.radians(28))
DOOR = 0.6                       # the doorway's half width


def planar(img, color, extra=None):
    m = {'color': color, 'texture': {'image': img, 'projection': 'planar'}}
    m.update(extra or {})
    return m


MATS = ap.materials('tile', 'tile_dark', 'wood', 'black', 'copper', 'gaku', extra={
    'stone': planar(STONE + 'coping.png', '#b8b2a2', {'tag': 'floor'}),
    'planks': planar(ap.ART + 'forest_planks.png', '#8a6446', {'tag': 'wall'}),
    'inner': planar(ap.ART + 'forest_inner_wood.png', '#6a4a30'),
    'soffit': {'color': '#4a3a2e', 'palette': True},
    'lattice': planar('art/lattice.png', '#5a3e2c', {'double_sided': True}),
})
for k in range(6):
    MATS['jizo_%d' % k] = {'color': '#9a948a',
                           'texture': {'sheet': 'jizo', 'cell': 'jizo_%d' % k, 'projection': 'fit'}}


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def outward(pts, want):
    """The polygon wound so its normal points along `want`."""
    return pts if ap.dot(newell(pts), want) > 0 else pts[::-1]


CORNERS = [(-E, -E), (E, -E), (E, E), (-E, E)]       # front left, front right, back right, back left


def base(p):
    p.box('stone', -B, B, 0.0, BH, -B, B, open=('bottom',), su=2.0)
    p.box('stone', -0.7, 0.7, 0.0, 0.2, -B - 0.4, -B + 0.01, open=('bottom', 'front'), su=2.0)


def body(p):
    for sx in (-1, 1):
        for sz in (-1, 1):
            p.box('wood', sx * PO - PW / 2, sx * PO + PW / 2, BH - 0.01, TOP + 0.01,
                  sz * PO - PW / 2, sz * PO + PW / 2, open=('top', 'bottom'))
    y0 = BH - 0.01
    # outer plank faces: back (+Z), left, right
    p.face_uv('planks', [(PO, TOP, WO), (-PO, TOP, WO), (-PO, y0, WO), (PO, y0, WO)], 1.0)
    p.face_uv('planks', [(WO, TOP, -PO), (WO, TOP, PO), (WO, y0, PO), (WO, y0, -PO)], 1.0)
    p.face_uv('planks', [(-WO, TOP, PO), (-WO, TOP, -PO), (-WO, y0, -PO), (-WO, y0, PO)], 1.0)
    # inner faces, looking in
    p.face_uv('inner', [(-PO, TOP, WI), (PO, TOP, WI), (PO, y0, WI), (-PO, y0, WI)], 1.0)
    p.face_uv('inner', [(WI, TOP, PO), (WI, TOP, -PO), (WI, y0, -PO), (WI, y0, PO)], 1.0)
    p.face_uv('inner', [(-WI, TOP, -PO), (-WI, TOP, PO), (-WI, y0, PO), (-WI, y0, -PO)], 1.0)
    # the frieze over the doorway and the lattice bays, outside, inside and its underside
    p.face_uv('planks', [(-PO, TOP, -WO), (PO, TOP, -WO), (PO, FR, -WO), (-PO, FR, -WO)], 1.0)
    p.face_uv('inner', [(PO, TOP, -WI), (-PO, TOP, -WI), (-PO, FR, -WI), (PO, FR, -WI)], 1.0)
    p.face('wood', [(-PO, FR, -WO), (PO, FR, -WO), (PO, FR, -WI), (-PO, FR, -WI)])
    p.face('soffit', outward([(-WI, 2.5, -WI), (WI, 2.5, -WI), (WI, 2.5, WI), (-WI, 2.5, WI)],
                             (0, -1, 0)))     # the ceiling
    # the doorway's posts and the lattice bays beside it
    for sx in (-1, 1):
        p.box('wood', sx * DOOR - 0.05, sx * DOOR + 0.05, BH - 0.01, FR, -PO - 0.05,
              -PO + 0.05, open=('top', 'bottom'))
        x0, x1 = sorted((sx * (DOOR + 0.05), sx * (PO - PW / 2)))
        p.face_uv('lattice', [(x0, FR, -PO), (x1, FR, -PO), (x1, BH, -PO), (x0, BH, -PO)], 0.4,
                  origin=(-PO, FR, -PO))


def roof(p):
    # soffit, flat, from the walls to the eaves (four trapezoids, seen from below)
    y = TOP
    ring_o = [(x, y, z) for x, z in CORNERS]
    ring_i = [(x * WO / E, y, z * WO / E) for x, z in CORNERS]
    for k in range(4):
        a, b = k, (k + 1) % 4
        p.face('soffit', outward([ring_o[a], ring_o[b], ring_i[b], ring_i[a]], (0, -1, 0)))
    apex = (0.0, APEX, 0.0)
    for k in range(4):
        a, b = CORNERS[k], CORNERS[(k + 1) % 4]
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        # the fascia, then the tiled slope; v 0 at the eave
        p.face('tile_dark', outward([(a[0], EY, a[1]), (b[0], EY, b[1]), (b[0], TOP, b[1]),
                                     (a[0], TOP, a[1])], (mid[0], 0, mid[1])))
        tri = outward([(a[0], EY, a[1]), (b[0], EY, b[1]), apex], (mid[0], 1.0, mid[1]))
        left = [q for q in tri if q[1] == EY]
        p.face_uv('tile', tri, 2.0, 2.0, origin=(left[0][0], EY, left[0][1]))
    # hip ridges: a low gabled cap along each corner line
    for cx, cz in CORNERS:
        c = (cx, EY, cz)
        h = (-cx / E, 0.0, -cz / E)                # toward the apex
        s = (-h[2], 0.0, h[0])                      # across the hip
        w, up = 0.09, 0.09
        top_c, top_a = (c[0], c[1] + up, c[2]), (0.0, APEX + up, 0.0)
        for sg in (-1, 1):
            off = (sg * w * s[0] / math.sqrt(2), 0.0, sg * w * s[2] / math.sqrt(2))
            side_c = (c[0] + off[0], c[1] - 0.01, c[2] + off[2])
            side_a = (off[0], APEX - 0.01, off[2])      # parallel to the top line: planar
            want = (off[0] * 10, 1.0, off[2] * 10)
            p.face('tile_dark', outward([top_c, top_a, side_a, side_c], want))


def finial_nodes(p):
    p.box('tile_dark', -0.2, 0.2, APEX - 0.15, APEX + 0.12, -0.2, 0.2, open=('bottom',))
    return [{'id': 'hoju', 'op': 'lathe', 'segments': 6, 'material': 'copper',
             'profile': [[0.0, APEX + 0.1], [0.17, APEX + 0.36], [0.12, APEX + 0.62],
                         [0.0, 4.95]]}]


def inside(p):
    p.box('wood', -1.3, 1.3, BH - 0.01, 0.8, 0.85, 1.39, open=('bottom', 'front'))
    for k in range(6):
        x = -1.075 + 0.43 * k
        z = 1.02 + (0.04 if k % 2 else 0.0)
        p.face('jizo_%d' % k, [(x - 0.18, 1.51, z), (x + 0.18, 1.51, z), (x + 0.18, 0.79, z),
                               (x - 0.18, 0.79, z)], [(0, 0), (1, 0), (1, 1), (0, 1)])
    # the offering box in the doorway, its slatted top dark
    p.box({'*': 'wood', 'top': 'black'}, -0.36, 0.36, BH - 0.01, 0.76, -1.32, -1.0,
          open=('bottom',))
    # the plaque on the frieze
    p.box({'*': 'black', 'back': 'gaku'}, -0.16, 0.16, 2.26, 2.54, -WO - 0.07, -WO + 0.02,
          crop={'back': (0, 0, 1, 1)})


def level0():
    b, w, r, i, f = (ap.Part('base'), ap.Part('hall'), ap.Part('roof'), ap.Part('inside'),
                     ap.Part('finial'))
    base(b)
    body(w)
    roof(r)
    inside(i)
    extra = finial_nodes(f)
    return [b, w, r, i, f] + extra


def simple_roof(p, fascia=True):
    apex = (0.0, APEX, 0.0)
    p.face('soffit', outward([(-E, TOP, -E), (E, TOP, -E), (E, TOP, E), (-E, TOP, E)], (0, -1, 0)))
    for k in range(4):
        a, b = CORNERS[k], CORNERS[(k + 1) % 4]
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if fascia:
            p.face('tile_dark', outward([(a[0], EY, a[1]), (b[0], EY, b[1]), (b[0], TOP, b[1]),
                                         (a[0], TOP, a[1])], (mid[0], 0, mid[1])))
        tri = outward([(a[0], EY, a[1]), (b[0], EY, b[1]), apex], (mid[0], 1.0, mid[1]))
        left = [q for q in tri if q[1] == EY]
        p.face_uv('tile', tri, 2.0, 2.0, origin=(left[0][0], EY, left[0][1]))


def level1():
    """From 30 m: the base, the hall as a box with a dark front, the roof, the finial a block."""
    p = ap.Part('hall')
    p.box('stone', -B, B, 0.0, BH, -B, B, open=('bottom',), su=2.0)
    p.box({'*': 'planks', 'back': 'black'}, -WO, WO, BH - 0.01, TOP + 0.01, -WO, WO,
          open=('bottom', 'top'), su=1.0)
    simple_roof(p)
    p.box('copper', -0.15, 0.15, APEX - 0.15, 4.9, -0.15, 0.15, open=('bottom',))
    return [p]


def level2():
    """From 80 m: the hall's box and the roof."""
    p = ap.Part('hall')
    p.box({'*': 'planks', 'back': 'black'}, -WO, WO, 0.0, TOP + 0.01, -WO, WO,
          open=('bottom', 'top'), su=1.0)
    simple_roof(p, fascia=False)
    return [p]


def collision():
    p = ap.Part('body')
    ap.col_box(p, -B, B, 0.0, BH, -B, B, open=('bottom',))
    ap.col_box(p, -0.7, 0.7, 0.0, 0.2, -B - 0.4, -B, open=('bottom', 'front'))
    t = 0.1          # boxes overlap by a few cm, so no two faces share a plane
    ap.col_box(p, -WO - t + 0.01, WO + t - 0.01, BH, TOP, WO - 0.2, WO + t, open=('bottom',))
    for sx in (-1, 1):                                                                 # sides
        x0, x1 = sorted((sx * (WO - 0.2), sx * (WO + t)))
        ap.col_box(p, x0, x1, BH, TOP - 0.01, -WO - t, WO, open=('bottom',))
        x0, x1 = sorted((sx * (DOOR - 0.05), sx * (WO - 0.1)))                         # bays
        ap.col_box(p, x0, x1, BH, TOP - 0.03, -PO - 0.1, -PO + 0.1, open=('bottom',))
    ap.col_box(p, -DOOR, DOOR, FR, TOP - 0.05, -PO - 0.09, -PO + 0.09, open=('bottom',))  # frieze
    ap.col_box(p, -1.3, 1.3, BH, 0.8, 0.85, WO - 0.15, open=('bottom',))               # altar
    ap.col_box(p, -0.36, 0.36, BH, 0.76, -1.32, -1.0, open=('bottom',))               # offering box
    # the roof: four walkable slopes (28 degrees) and the eaves' edge
    apex = (0.0, APEX, 0.0)
    for k in range(4):
        a, b = CORNERS[k], CORNERS[(k + 1) % 4]
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        p.face('solid', outward([(a[0], EY, a[1]), (b[0], EY, b[1]), apex], (mid[0], 1, mid[1])))
        ap.col_quad(p, *outward([(a[0], EY, a[1]), (b[0], EY, b[1]), (b[0], TOP, b[1]),
                                 (a[0], TOP, a[1])], (mid[0], 0, mid[1])))
    ap.col_box(p, -0.2, 0.2, APEX - 0.1, 4.95, -0.2, 0.2, open=('bottom',))          # finial
    return [p]


def main():
    lod = {'levels': [(30, level1()), (80, level2())], 'cull': 200, 'band': 2}
    r = ap.recipe('cemetery_jizo_hall', MATS, level0(), 300, lod)
    r['sheets'] = {'jizo': {'image': 'art/jizo.png'}}
    ap.write(HERE / 'cemetery_jizo_hall.asset.json', r)
    ap.write(HERE / 'cemetery_jizo_hall_col.asset.json',
             ap.col_recipe('cemetery_jizo_hall_col', collision()))


if __name__ == '__main__':
    main()
