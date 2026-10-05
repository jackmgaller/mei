"""Writes cemetery_terrace_wall_12.asset.json and cemetery_terrace_wall_12_col.asset.json beside
this script (python3 make_cemetery_terrace_wall_12.py; the textures first with
python3 art/draw_cemetery_stone.py): a 12 m module of the cemetery's retaining walls (shrine town
spec 3.14; assets.md #23). Nine terraces 1.8 m apart, five modules a terrace, 45 placed and
merged per cell.

Footprint 12 x 1 m, origin at the middle of the footprint's base, the face toward -Z (downhill).
The face is battered, granite blocks laid diagonally (kenchi-ishi) with a weep hole in every
2 x 1 m repeat, from z -0.50 at the foot to z -0.38 at 1.54; above it a cut-granite coping, a
vertical face at z -0.38 from 1.54 to 1.80 and a top from z -0.38 to +0.50 at 1.80, the upper
terrace's level. The back (+Z) and the bottom are open (earth); the ends are closed, so a run of
modules stops cleanly at the stair or the terrace's end. The texture's u starts at the module's
west end and a module is six whole repeats, so modules placed end to end continue the courses.

The upper terrace's ground should begin at the wall's back (z +0.50), or lie under the coping
(below 1.80) where it runs over it: a ground face at 1.80 over the coping's top would tie with it.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

L = 6.0                          # half length
ZF, ZB = -0.50, 0.50             # foot of the face, back
ZT, YB = -0.38, 1.54             # top of the battered face
H = 1.80                         # the top, the upper terrace's level

MATS = {
    'kenchi': {'color': '#a8a294', 'tag': 'wall',
               'texture': {'image': 'art/kenchi.png', 'projection': 'planar'}},
    'coping': {'color': '#b8b2a2', 'tag': 'wall',
               'texture': {'image': 'art/coping.png', 'projection': 'planar'}},
}


def end_faces(p, mat, profile):
    """The two end faces of the profile (z, y), outward, cut-granite as the coping."""
    east = [(L, y, z) for z, y in profile]
    p.face_uv(mat, east, 2.0, 2.0, origin=(L, H, ZF))
    p.face_uv(mat, ap.mirror_x(east), 2.0, 2.0, origin=(-L, H, ZB))


def level0():
    p = ap.Part('wall')
    # the battered face: v 0 at its top, u 0 at the west end; 2 x 1 m a repeat
    p.face_uv('kenchi', [(-L, YB, ZT), (L, YB, ZT), (L, 0.0, ZF), (-L, 0.0, ZF)], 2.0, 1.0,
              origin=(-L, YB, ZT))
    p.face_uv('coping', [(-L, H, ZT), (L, H, ZT), (L, YB, ZT), (-L, YB, ZT)], 2.0, 2.0,
              origin=(-L, H, ZT))
    p.face_uv('coping', [(-L, H, ZB), (L, H, ZB), (L, H, ZT), (-L, H, ZT)], 2.0, 2.0,
              origin=(-L, H, ZT))
    # east end, clockwise from outside (+X): back top, front top, batter top, foot, back foot
    end_faces(p, 'coping', [(ZB, H), (ZT, H), (ZT, YB), (ZF, 0.0), (ZB, 0.0)][::-1])
    return [p]


def level1():
    """From 40 m: the face as one plane to the top, the top, the ends as quads."""
    p = ap.Part('wall')
    p.face_uv('kenchi', [(-L, H, ZT), (L, H, ZT), (L, 0.0, ZF), (-L, 0.0, ZF)], 2.0, 1.0,
              origin=(-L, H, ZT))
    p.face_uv('coping', [(-L, H, ZB), (L, H, ZB), (L, H, ZT), (-L, H, ZT)], 2.0, 2.0,
              origin=(-L, H, ZT))
    end_faces(p, 'coping', [(ZB, H), (ZT, H), (ZF, 0.0), (ZB, 0.0)][::-1])
    return [p]


def level2():
    """From 100 m: the face and the top."""
    p = ap.Part('wall')
    p.face_uv('kenchi', [(-L, H, ZT), (L, H, ZT), (L, 0.0, ZF), (-L, 0.0, ZF)], 2.0, 1.0,
              origin=(-L, H, ZT))
    p.face_uv('coping', [(-L, H, ZB), (L, H, ZB), (L, H, ZT), (-L, H, ZT)], 2.0, 2.0,
              origin=(-L, H, ZT))
    return [p]


def collision():
    """The face as one battered plane to the top, the top as a floor, the ends; pieces <= 2 m."""
    p = ap.Part('body')
    ap.col_quad(p, (-L, H, ZT), (L, H, ZT), (L, 0.0, ZF), (-L, 0.0, ZF))
    ap.col_quad(p, (-L, H, ZB), (L, H, ZB), (L, H, ZT), (-L, H, ZT))
    for s in (1, -1):
        pts = [(L, H, ZT), (L, H, ZB), (L, 0.0, ZB), (L, 0.0, ZF)]
        if s < 0:
            pts = ap.mirror_x(pts)
        ap.col_quad(p, *pts)
    return [p]


def main():
    lod = {'levels': [(40, level1()), (100, level2())], 'band': 2}
    ap.write(HERE / 'cemetery_terrace_wall_12.asset.json',
             ap.recipe('cemetery_terrace_wall_12', MATS, level0(), 24, lod))
    ap.write(HERE / 'cemetery_terrace_wall_12_col.asset.json',
             ap.col_recipe('cemetery_terrace_wall_12_col', collision()))


if __name__ == '__main__':
    main()
