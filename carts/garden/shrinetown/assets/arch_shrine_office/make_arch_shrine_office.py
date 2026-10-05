"""Writes arch_shrine_office.asset.json and arch_shrine_office_col.asset.json beside this script
(python3 make_arch_shrine_office.py): the shrine office (juyosho), where charms, fortunes and
prayer plaques are sold, in the outer courtyard (shrine town spec 3.6; assets.md #51).

A one-storey hall in the manner of the side halls (the shrine's architecture textures, through
../arch_wall_gate/arch_parts.py): a stone base 0.45 high, walls of vermilion posts and white
plaster, and a hip-and-gable tile roof. The front (-Z) is the sales window: two 4 m bays of
glazed counter (art/office_counter.png: rows of charms behind the glass) over a wooden counter
ledge, two lanterns hanging at the front corners and a name plaque on the middle post. The left
side (-X) has the staff door.

Footprint 8 x 6 m (the walls; the base is 8.4 x 6.4, the eaves 9.6 x 7.6). Origin at the middle
of the base's foot. Walls 0.45-2.7; eaves 2.62-2.85, corners turned up 0.2; the hipped skirt
rises at 17.5 degrees to 3.45, the gable at 21.5 degrees to the ridge at 4.2; the ridge cap to
4.38, its end tiles to 4.5. The counter ledge is at 1.10. Every roof plane is walkable (the
collision's slopes 17.5 and 21.5 degrees); the eave (2.62) is a jump and a grab from the gravel.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

WX, WZ = 4.0, 3.0               # walls
BASE = (4.2, 3.2, 0.45)         # half x, half z, top
WALL_TOP = 2.7
EAVE = (4.8, 3.8, 2.85)         # ex, ez, top
FASCIA, LIFT, CORNER = 0.23, 0.2, 1.5
INNER = (3.0, 1.9, 3.45)
RIDGE = 4.2
SHELF = (1.04, 1.10)
BAY_V = (18 / 64, 1.0)          # the part of arch_bay under its frieze, as the halls' lower walls


def base(p):
    x, z, h = BASE
    p.box('stone', -x, x, 0.0, h, -z, z, open=('bottom',), su=2.4)


def walls(p):
    y0, y1 = BASE[2], WALL_TOP
    v0, v1 = BAY_V

    def bay(mat, a, b, crop=(0.0, v0, 1.0, v1)):
        """One bay from corner a to corner b (top edge, seen from outside)."""
        u0, w0, u1, w1 = crop
        p.face(mat, [(a[0], y1, a[1]), (b[0], y1, b[1]), (b[0], y0, b[1]), (a[0], y0, a[1])],
               [(u0, w0), (u1, w0), (u1, w1), (u0, w1)])
    # front: the sales window, two bays
    bay('counter', (-WX, -WZ), (0.0, -WZ), (0, 0, 1, 1))
    bay('counter', (0.0, -WZ), (WX, -WZ), (0, 0, 1, 1))
    # back: two window bays
    bay('bay', (WX, WZ), (0.0, WZ))
    bay('bay', (0.0, WZ), (-WX, WZ))
    # right (+X): two window bays of 3 m
    bay('bay', (WX, -WZ), (WX, 0.0))
    bay('bay', (WX, 0.0), (WX, WZ))
    # left (-X): the staff door toward the back, a window toward the front
    bay('bay_doors', (-WX, WZ), (-WX, 0.0))
    bay('bay', (-WX, 0.0), (-WX, -WZ))


def counter(p):
    """The counter ledge standing out of the sales window."""
    p.box({'*': 'wood_new', 'bottom': 'wood'}, -3.78, 3.78, SHELF[0], SHELF[1], -WZ - 0.32,
          -WZ + 0.02, open=('front',))


def lanterns(p):
    """Two lanterns hanging under the front eave, at the corners of the sales window."""
    for s in (-1, 1):
        x = s * 3.55
        z = -WZ - 0.45
        p.box({'*': 'lantern', 'top': 'black', 'bottom': 'black'}, x - 0.16, x + 0.16, 1.95,
              2.35, z - 0.16, z + 0.16)
        p.box('black', x - 0.03, x + 0.03, 2.35, 2.66, z - 0.03, z + 0.03, open=('top', 'bottom'))


def plaque(p):
    """The name plaque on the middle post between the two windows."""
    p.box({'*': 'black', 'back': 'gaku'}, -0.15, 0.15, 1.6, 2.36, -WZ - 0.1, -WZ - 0.04,
          crop={'back': (0, 0, 1, 1)})


def roof(p):
    ix, iz, yi, yr = ap.irimoya(p, EAVE, INNER, (WX, WZ, WALL_TOP), RIDGE, CORNER, LIFT, FASCIA)
    ap.bargeboards(p, ix, iz, yi, yr)
    ap.ridge_cap(p, ix + 0.3, RIDGE - 0.12, 4.38, 0.2, oni=(0.26, 4.5, 0.26))


def level0():
    b, w, r, d = ap.Part('base'), ap.Part('walls'), ap.Part('roof'), ap.Part('details')
    base(b)
    walls(w)
    roof(r)
    counter(d)
    lanterns(d)
    plaque(d)
    return [b, w, r, d]


def simple_roof(p, mat_top, mat_end, under=True):
    """The roof in 16 triangles (or 14): the hipped skirt to the inner rectangle, the gable to
    the ridge, the gable ends, and the eave's underside."""
    ex, ez, yh = EAVE
    ix, iz, yi = INNER
    yl = yh - FASCIA
    for sides in ((lambda a, y, b: (a, y, -b), ex, ez, ix, iz),
                  (lambda a, y, b: (b, y, a), ez, ex, iz, ix),
                  (lambda a, y, b: (-a, y, b), ex, ez, ix, iz),
                  (lambda a, y, b: (-b, y, -a), ez, ex, iz, ix)):
        P, A, B, Ai, Bi = sides
        pts = [P(-Ai, yi, Bi), P(Ai, yi, Bi), P(A, yl, B), P(-A, yl, B)]
        if mat_top == 'tile':
            p.face_uv('tile', pts, 2.0, 2.0, origin=P(-A, yl, B))
        else:
            p.face(mat_top, pts)
    for s in (-1, 1):
        if s < 0:
            pts = [(-ix, RIDGE, 0.0), (ix, RIDGE, 0.0), (ix, yi, -iz), (-ix, yi, -iz)]
        else:
            pts = [(ix, RIDGE, 0.0), (-ix, RIDGE, 0.0), (-ix, yi, iz), (ix, yi, iz)]
        if mat_top == 'tile':
            p.face_uv('tile', pts, 2.0, 2.0, origin=pts[3])
        else:
            p.face(mat_top, pts)
    tri = [(ix, RIDGE, 0.0), (ix, yi, iz), (ix, yi, -iz)]
    p.face(mat_end, tri)
    p.face(mat_end, ap.mirror_x(tri))
    if under:
        p.face_uv('rafters', [(-ex, yl, -ez), (ex, yl, -ez), (ex, yl, ez), (-ex, yl, ez)], 1.0)


def level1():
    """From 40 m: the base's top band and the walls as four textured faces, the roof simple."""
    p = ap.Part('office')
    x, z, h = BASE
    p.box('stone', -x, x, 0.0, h, -z, z, open=('bottom', 'top'), su=2.4)
    y0, y1 = h, WALL_TOP
    v0, v1 = BAY_V
    p.face('counter', [(-WX, y1, -WZ), (WX, y1, -WZ), (WX, y0, -WZ), (-WX, y0, -WZ)],
           [(0, 0), (2, 0), (2, 1), (0, 1)])
    p.face('bay', [(WX, y1, WZ), (-WX, y1, WZ), (-WX, y0, WZ), (WX, y0, WZ)],
           [(0, v0), (2, v0), (2, v1), (0, v1)])
    p.face('bay', [(WX, y1, -WZ), (WX, y1, WZ), (WX, y0, WZ), (WX, y0, -WZ)],
           [(0, v0), (2, v0), (2, v1), (0, v1)])
    p.face('bay', [(-WX, y1, WZ), (-WX, y1, -WZ), (-WX, y0, -WZ), (-WX, y0, WZ)],
           [(0, v0), (2, v0), (2, v1), (0, v1)])
    simple_roof(p, 'tile', 'plaster')
    return [p]


def level2():
    """From 90 m: four walls and the roof, flat colours."""
    p = ap.Part('office')
    y0, y1 = 0.0, WALL_TOP
    for pts in ([(-WX, y1, -WZ), (WX, y1, -WZ), (WX, y0, -WZ), (-WX, y0, -WZ)],
                [(WX, y1, WZ), (-WX, y1, WZ), (-WX, y0, WZ), (WX, y0, WZ)],
                [(WX, y1, -WZ), (WX, y1, WZ), (WX, y0, WZ), (WX, y0, -WZ)],
                [(-WX, y1, WZ), (-WX, y1, -WZ), (-WX, y0, -WZ), (-WX, y0, WZ)]):
        p.face('plaster', pts)
    simple_roof(p, 'tile_dark', 'tile_dark', under=False)
    return [p]


def collision():
    p = ap.Part('body')
    x, z, h = BASE
    ap.col_box(p, -x, x, 0.0, h, -z, z, open=('bottom',))
    ap.col_box(p, -WX, WX, h, WALL_TOP, -WZ, WZ, open=('bottom',))
    ex, ez, yh = EAVE
    ix, iz, yi = INNER
    yl = yh - FASCIA
    ap.col_quad(p, (-ex, yl, -ez), (ex, yl, -ez), (ex, yl, ez), (-ex, yl, ez))        # under
    for P, A, B, Ai, Bi in ((lambda a, y, b: (a, y, -b), ex, ez, ix, iz),
                            (lambda a, y, b: (b, y, a), ez, ex, iz, ix),
                            (lambda a, y, b: (-a, y, b), ex, ez, ix, iz),
                            (lambda a, y, b: (-b, y, -a), ez, ex, iz, ix)):
        ap.col_quad(p, P(-A, yh, B), P(A, yh, B), P(A, yl, B), P(-A, yl, B))           # fascia
        ap.col_quad(p, P(-Ai, yi, Bi), P(Ai, yi, Bi), P(A, yh, B), P(-A, yh, B))       # skirt
    ap.col_quad(p, (-ix, RIDGE, 0.0), (ix, RIDGE, 0.0), (ix, yi, -iz), (-ix, yi, -iz))
    ap.col_quad(p, (ix, RIDGE, 0.0), (-ix, RIDGE, 0.0), (-ix, yi, iz), (ix, yi, iz))
    tri = [(ix, RIDGE, 0.0), (ix, yi, iz), (ix, yi, -iz)]
    p.face('solid', tri)
    p.face('solid', ap.mirror_x(tri))
    return [p]


def main():
    mats = ap.materials('tile', 'bay', 'bay_doors', 'stone', 'rafters', 'gaku', 'lacquer',
                        'shade', 'plaster', 'tile_dark', 'black', 'wood', 'wood_new', 'lantern',
                        extra={'counter': {'color': '#d8462a',
                                           'texture': {'image': 'art/office_counter.png',
                                                       'projection': 'planar'}}})
    lod = {'levels': [(40, level1()), (90, level2())], 'band': 2}
    ap.write(HERE / 'arch_shrine_office.asset.json',
             ap.recipe('arch_shrine_office', mats, level0(), 400, lod))
    ap.write(HERE / 'arch_shrine_office_col.asset.json',
             ap.col_recipe('arch_shrine_office_col', collision()))


if __name__ == '__main__':
    main()
