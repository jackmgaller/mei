"""Writes arch_wall_gate (leaves open) and arch_wall_gate_shut (leaves closed), each with its
`_col`, beside this script (python3 make_arch_wall_gate.py): a gate in the precinct's white wall
(shrine town spec 3.7; assets.md #49).

One 8 m module of the white wall (carts/garden/shrine/assets/arch_wall_8, the same profile:
footing 0.5, plaster to 2.2, tiled cap to 2.6) with a gate in it: two vermilion posts 5.5 m apart
(a 5.08 m clear opening), a tie beam at 3.15-3.45 (the clear height), a head beam and two
bracket arms carrying a small gabled roof (eaves 3.8-4.05 at z +-1.35, ridge 4.7, ridge cap to
4.88, end tiles to 5.0). The roof is 26 degrees: a route from the wall top (2.6) by a 1.45 m hop.

Origin: the middle of the opening at the wall's base; the wall runs along X (x -4 to 4, so the
gate replaces one arch_wall_8 and its ends meet the next wall pieces); -Z is the outside of the
precinct. The open gate's leaves stand swung in (+Z, into the precinct), against the opening's
sides. The shut gate's leaves fill the opening (z -0.05 to 0.05); the north gate's bar
(arch_wall_gate_bar, its own asset) lies across their -Z face. Layers: the barred north gate
shows arch_wall_gate_shut, gate_b_open shows arch_wall_gate.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import arch_parts as ap  # noqa: E402

XP = 2.75            # post centres
PW = 0.42            # post width
XI = XP - PW / 2     # opening's side (2.54)
XO = XP + PW / 2
END = 4.0            # module ends
BEAM = (3.15, 3.45)  # tie beam
HEAD = (3.6, 3.8)    # head beam
ARM = (3.68, 3.96)   # bracket arms (cross the soffit by a centimetre near their ends)
EZ, EX = 1.35, 3.5   # eaves: half depth, half length
EAVE_LO, EAVE_HI, RIDGE = 3.80, 4.05, 4.71
LEAF_H = (0.04, 3.14)

# the door leaves' picture: the lattice-panel doors of arch_bay_doors (64 x 64), in repeats
DOORS = (6 / 64, 22.5 / 64, 58 / 64, 59 / 64)      # both leaves, frame included
LEAF_L = (6 / 64, 22.5 / 64, 32 / 64, 59 / 64)     # the left leaf
LEAF_R = (32 / 64, 22.5 / 64, 58 / 64, 59 / 64)


def wing(p, xa, xb):
    """A run of arch_wall_8's profile from x xa to xb (xa < xb), its faces and UVs as that
    asset's (footing and cap textures cover 8 m once), open at both ends."""
    def u(x):
        return (x + END) / 8.0

    def ub(x):
        return (END - x) / 8.0
    a, b = xa, xb
    # front (-Z) side
    p.face('footing', [(a, .5, -.42), (b, .5, -.42), (b, 0, -.42), (a, 0, -.42)],
           [(u(a), 0), (u(b), 0), (u(b), 1), (u(a), 1)])
    p.face('stone_pal', [(a, .5, -.36), (b, .5, -.36), (b, .5, -.42), (a, .5, -.42)])
    p.face('plaster', [(a, 2.2, -.36), (b, 2.2, -.36), (b, .5, -.36), (a, .5, -.36)])
    p.face('wall_cap', [(a, 2.54, -.1), (b, 2.54, -.1), (b, 2.3, -.5), (a, 2.3, -.5)],
           [(u(a), 0), (u(b), 0), (u(b), 1), (u(a), 1)])
    p.face('tile_dark', [(a, 2.3, -.5), (b, 2.3, -.5), (b, 2.22, -.5), (a, 2.22, -.5)])
    p.face('shade', [(a, 2.22, -.5), (b, 2.22, -.5), (b, 2.2, -.36), (a, 2.2, -.36)])
    p.face('tile_dark', [(a, 2.6, -.12), (b, 2.6, -.12), (b, 2.48, -.12), (a, 2.48, -.12)])
    # back (+Z) side
    p.face('footing', [(b, .5, .42), (a, .5, .42), (a, 0, .42), (b, 0, .42)],
           [(ub(b), 0), (ub(a), 0), (ub(a), 1), (ub(b), 1)])
    p.face('stone_pal', [(b, .5, .36), (a, .5, .36), (a, .5, .42), (b, .5, .42)])
    p.face('plaster', [(b, 2.2, .36), (a, 2.2, .36), (a, .5, .36), (b, .5, .36)])
    p.face('wall_cap', [(b, 2.54, .1), (a, 2.54, .1), (a, 2.3, .5), (b, 2.3, .5)],
           [(ub(b), 0), (ub(a), 0), (ub(a), 1), (ub(b), 1)])
    p.face('tile_dark', [(b, 2.3, .5), (a, 2.3, .5), (a, 2.22, .5), (b, 2.22, .5)])
    p.face('shade', [(b, 2.22, .5), (a, 2.22, .5), (a, 2.2, .36), (b, 2.2, .36)])
    p.face('tile_dark', [(b, 2.6, .12), (a, 2.6, .12), (a, 2.48, .12), (b, 2.48, .12)])
    # the cap's top
    p.face('tile_dark', [(a, 2.6, .12), (b, 2.6, .12), (b, 2.6, -.12), (a, 2.6, -.12)])


def wing_end(p, x, facing):
    """The wall's cross-section at x, facing -X (facing=-1) or +X: footing, plaster, cap."""
    def at(zy):
        return [(x, y, z) for z, y in zy]
    foot = [(-.42, 0), (-.42, .5), (.42, .5), (.42, 0)]
    plas = [(-.36, .5), (-.36, 2.2), (.36, 2.2), (.36, .5)]
    cap = [(-.36, 2.2), (-.5, 2.22), (-.5, 2.3), (-.12, 2.528), (-.12, 2.6), (.12, 2.6),
           (.12, 2.528), (.5, 2.3), (.5, 2.22), (.36, 2.2)]
    for mat, poly in (('stone_pal', foot), ('plaster', plas), ('tile_dark', cap)):
        pts = at(poly)          # clockwise as seen from +X (right is +Z)
        if facing < 0:
            pts = pts[::-1]
        p.face(mat, pts)


def roof(p):
    """The gabled roof (arch_parts.gable_roof) and its ridge with end tiles."""
    ap.gable_roof(p, EX, EZ, EAVE_LO, EAVE_HI, RIDGE)
    ap.ridge_cap(p, 3.62, RIDGE - 0.12, 4.88, 0.17, oni=(0.26, 5.0, 0.24))


def frame(p):
    """Posts, tie beam, head beam and the bracket arms."""
    for s in (-1, 1):
        x0, x1 = sorted((s * XI, s * XO))
        p.box('lacquer', x0, x1, 0.0, HEAD[0] + 0.02, -PW / 2, PW / 2, open=('bottom', 'top'))
        a0, a1 = sorted((s * (XP - 0.13), s * (XP + 0.13)))
        p.box({'*': 'lacquer', 'bottom': 'shade'}, a0, a1, ARM[0], ARM[1], -1.08, 1.08)
    p.box({'*': 'lacquer', 'bottom': 'shade'}, -3.22, 3.22, BEAM[0], BEAM[1], -0.13, 0.13)
    p.box({'*': 'lacquer', 'bottom': 'shade'}, -3.05, 3.05, HEAD[0], HEAD[1], -0.15, 0.15)


def leaves(p, shut):
    y0, y1 = LEAF_H
    if shut:
        p.box({'*': 'lacquer', 'back': 'bay_doors', 'front': 'bay_doors'}, -XI + 0.02,
              XI - 0.02, y0, y1, -0.05, 0.05, open=('bottom',),
              crop={'back': DOORS, 'front': DOORS})
        return
    # swung in to +Z about hinges just inside the posts' back corners
    for s in (-1, 1):
        x0, x1 = sorted((s * (XI - 0.03), s * (XI - 0.13)))
        # seen from the opening (the leaf's inner face) the picture is one leaf
        crop_in = LEAF_R if s > 0 else LEAF_L
        crop_out = LEAF_L if s > 0 else LEAF_R
        side_in = 'left' if s > 0 else 'right'
        side_out = 'right' if s > 0 else 'left'
        p.box({'*': 'lacquer', side_in: 'bay_doors', side_out: 'bay_doors'}, x0, x1, y0, y1,
              0.26, 0.26 + 2.48, open=('bottom',), crop={side_in: crop_in, side_out: crop_out})


def level0(shut):
    w, f, r, l = ap.Part('wall'), ap.Part('frame'), ap.Part('roof'), ap.Part('leaves')
    for s in (-1, 1):
        a, b = (XP, END) if s > 0 else (-END, -XP)
        wing(w, a, b)
        wing_end(w, s * XP, -s)
    frame(f)
    roof(r)
    leaves(l, shut)
    return [w, f, r, l]


def level1(shut):
    """From 40 m: the wall as arch_wall_8's coarse level, posts, one beam, the roof."""
    p = ap.Part('gate')
    for s in (-1, 1):
        a, b = (XP, END) if s > 0 else (-END, -XP)
        p.face('plaster', [(a, 2.2, -.36), (b, 2.2, -.36), (b, 0, -.36), (a, 0, -.36)])
        p.face('wall_cap', [(a, 2.6, 0), (b, 2.6, 0), (b, 2.2, -.5), (a, 2.2, -.5)],
               [((a + END) / 8, 0), ((b + END) / 8, 0), ((b + END) / 8, 1), ((a + END) / 8, 1)])
        p.face('plaster', [(b, 2.2, .36), (a, 2.2, .36), (a, 0, .36), (b, 0, .36)])
        p.face('wall_cap', [(b, 2.6, 0), (a, 2.6, 0), (a, 2.2, .5), (b, 2.2, .5)],
               [((END - b) / 8, 0), ((END - a) / 8, 0), ((END - a) / 8, 1), ((END - b) / 8, 1)])
        x0, x1 = sorted((s * XI, s * XO))
        p.box('lacquer', x0, x1, 0.0, EAVE_LO, -PW / 2, PW / 2, open=('bottom', 'top'))
    p.box('lacquer', -3.22, 3.22, BEAM[0], HEAD[1] - 0.04, -0.14, 0.14, open=('left', 'right'))
    for s in (-1, 1):
        if s < 0:
            pts = [(-EX, RIDGE, 0), (EX, RIDGE, 0), (EX, EAVE_LO, -EZ), (-EX, EAVE_LO, -EZ)]
        else:
            pts = [(EX, RIDGE, 0), (-EX, RIDGE, 0), (-EX, EAVE_LO, EZ), (EX, EAVE_LO, EZ)]
        p.face_uv('tile', pts, 2.0, 2.0, origin=pts[3])
    p.face('tile_dark', [(-EX, EAVE_LO, -EZ), (EX, EAVE_LO, -EZ), (EX, EAVE_LO, EZ),
                         (-EX, EAVE_LO, EZ)])
    p.face('lacquer', [(EX, EAVE_LO, -EZ), (EX, RIDGE, 0), (EX, EAVE_LO, EZ)])
    p.face('lacquer', [(-EX, EAVE_LO, EZ), (-EX, RIDGE, 0), (-EX, EAVE_LO, -EZ)])
    y0, y1 = LEAF_H
    if shut:
        p.face('bay_doors', [(-XI, y1, -0.05), (XI, y1, -0.05), (XI, y0, -0.05), (-XI, y0, -0.05)],
               [(DOORS[0], DOORS[1]), (DOORS[2], DOORS[1]), (DOORS[2], DOORS[3]),
                (DOORS[0], DOORS[3])])
        p.face('bay_doors', [(XI, y1, 0.05), (-XI, y1, 0.05), (-XI, y0, 0.05), (XI, y0, 0.05)],
               [(DOORS[0], DOORS[1]), (DOORS[2], DOORS[1]), (DOORS[2], DOORS[3]),
                (DOORS[0], DOORS[3])])
    else:
        for s in (-1, 1):
            xi, xo = s * (XI - 0.13), s * (XI - 0.03)     # the face toward the opening, the other
            a, b = (2.74, 0.26) if s > 0 else (0.26, 2.74)
            p.face('lacquer', [(xi, y1, a), (xi, y1, b), (xi, y0, b), (xi, y0, a)])
            p.face('lacquer', [(xo, y1, b), (xo, y1, a), (xo, y0, a), (xo, y0, b)])
    return [p]


def level2():
    """From 100 m: the wall's two faces, the posts as slabs and the roof as a prism."""
    p = ap.Part('gate')
    for s in (-1, 1):
        a, b = (XI, END) if s > 0 else (-END, -XI)
        p.face('plaster', [(a, 2.6, -.4), (b, 2.6, -.4), (b, 0, -.4), (a, 0, -.4)])
        p.face('plaster', [(b, 2.6, .4), (a, 2.6, .4), (a, 0, .4), (b, 0, .4)])
        p.face('tile_dark', [(a, 2.6, .4), (b, 2.6, .4), (b, 2.6, -.4), (a, 2.6, -.4)])
    p.face('lacquer', [(-XO, BEAM[1], -0.2), (XO, BEAM[1], -0.2), (XO, BEAM[0], -0.2),
                       (-XO, BEAM[0], -0.2)])
    for s in (-1, 1):
        x0, x1 = sorted((s * XI, s * XO))
        p.face('lacquer', [(x0, BEAM[0], -0.21), (x1, BEAM[0], -0.21), (x1, 0, -0.21),
                           (x0, 0, -0.21)])
        p.face('lacquer', [(x1, BEAM[0], 0.21), (x0, BEAM[0], 0.21), (x0, 0, 0.21),
                           (x1, 0, 0.21)])
    for s in (-1, 1):
        if s < 0:
            pts = [(-EX, RIDGE, 0), (EX, RIDGE, 0), (EX, EAVE_LO, -EZ), (-EX, EAVE_LO, -EZ)]
        else:
            pts = [(EX, RIDGE, 0), (-EX, RIDGE, 0), (-EX, EAVE_LO, EZ), (EX, EAVE_LO, EZ)]
        p.face('tile_dark', pts)
    return [p]


def collision(shut):
    p = ap.Part('body')
    for s in (-1, 1):
        x0, x1 = sorted((s * XI, s * END))
        ap.col_box(p, x0, x1, 0.0, 2.6, -0.4, 0.4, open=('bottom',))     # wall and post foot
        x0, x1 = sorted((s * XI, s * XO))
        ap.col_box(p, x0, x1, 2.6, BEAM[0] + 0.05, -0.21, 0.21, open=('bottom',))  # the post
        if not shut:
            x0, x1 = sorted((s * (XI - 0.03), s * (XI - 0.25)))
            ap.col_box(p, x0, x1, 0.0, LEAF_H[1], 0.26, 2.74, open=('bottom',))  # the open leaf
    # beams: a block over the opening, the posts' tops to the roof's soffit
    ap.col_box(p, -3.22, 3.22, BEAM[0], EAVE_LO + 0.05, -0.3, 0.3)
    # the roof: eaves 3.80-4.05, slopes to the ridge (26 degrees, walkable)
    for s in (-1, 1):
        if s < 0:
            ap.col_quad(p, (-EX, RIDGE, 0), (EX, RIDGE, 0), (EX, EAVE_HI, -EZ), (-EX, EAVE_HI, -EZ))
            ap.col_quad(p, (-EX, EAVE_HI, -EZ), (EX, EAVE_HI, -EZ), (EX, EAVE_LO, -EZ),
                        (-EX, EAVE_LO, -EZ))
        else:
            ap.col_quad(p, (EX, RIDGE, 0), (-EX, RIDGE, 0), (-EX, EAVE_HI, EZ), (EX, EAVE_HI, EZ))
            ap.col_quad(p, (EX, EAVE_HI, EZ), (-EX, EAVE_HI, EZ), (-EX, EAVE_LO, EZ),
                        (EX, EAVE_LO, EZ))
    ap.col_quad(p, (-EX, EAVE_LO, -EZ), (EX, EAVE_LO, -EZ), (EX, EAVE_LO, EZ), (-EX, EAVE_LO, EZ))
    for s in (-1, 1):
        pts = [(EX, EAVE_HI, -EZ), (EX, RIDGE, 0), (EX, EAVE_HI, EZ), (EX, EAVE_LO, EZ),
               (EX, EAVE_LO, -EZ)]
        p.face('solid', pts if s > 0 else ap.mirror_x(pts))
    if shut:
        ap.col_box(p, -XI - 0.05, XI + 0.05, 0.0, BEAM[0] + 0.1, -0.1, 0.1, open=('bottom',))
    return [p]


def build(name, shut):
    mats = ap.materials('tile', 'bay_doors', 'rafters', 'wall_cap', 'footing', 'lacquer', 'shade',
                        'plaster', 'tile_dark', 'stone_pal')
    lod = {'levels': [(40, level1(shut)), (100, level2())], 'band': 2}
    ap.write(HERE / f'{name}.asset.json', ap.recipe(name, mats, level0(shut), 250, lod))
    ap.write(HERE / f'{name}_col.asset.json', ap.col_recipe(f'{name}_col', collision(shut)))


if __name__ == '__main__':
    build('arch_wall_gate', False)
    build('arch_wall_gate_shut', True)
