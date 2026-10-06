"""Writes arch_wall_gate_shut_town_col.asset.json beside this script (python3
make_arch_wall_gate_town_col.py): the barred north gate's collision in shrine town, where the gate
is shortcut B and must not be climbed over (alpha fix; the explorer bot: a side flip from the
terrace landed on the gate's roof, 4.7 m up, and walked off its far side onto the north stair).

arch_wall_gate_shut_col with its walkable 26-degree roof replaced and its wings capped, as the
north wall's own coping is (shrine_wall_coping_*_col, place/shrine.py):

- the roof: a steep gable over the eaves' footprint (x +-3.5, z +-1.35), from the soffit (3.8) to a
  ridge at 6.6 (64 degrees: no floor, no ledge). It stands 1.9 m over the drawn ridge, out of every
  jump's reach from the terrace (a running third jump: 5.6 m);
- the wings (the wall either side of the posts, its top at 2.6): a coping ridge 0.6 m over the top
  (56 degrees), so the hands find no ledge there either.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import arch_parts as ap  # noqa: E402
import make_arch_wall_gate as g  # noqa: E402

PEAK = 6.6          # the steep roof's ridge
WING_TOP, WING_PEAK, WING_H = 2.6, 3.2, 0.4


def check_out(pts, centre):
    """The face's normal (corners clockwise from outside) points away from the prism's centre."""
    a, b, c = pts[0], pts[1], pts[2]
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    m = [sum(p[i] for p in pts) / len(pts) - centre[i] for i in range(3)]
    assert sum(n[i] * m[i] for i in range(3)) > 0, pts


def prism(p, x0, x1, base, peak, h, bottom):
    """A gable along X over x0..x1, z -h..h, from `base` to a ridge at `peak` (z 0)."""
    centre = ((x0 + x1) / 2, (base + peak) / 2, 0.0)
    quads = [[(x0, peak, 0), (x1, peak, 0), (x1, base, -h), (x0, base, -h)],
             [(x1, peak, 0), (x0, peak, 0), (x0, base, h), (x1, base, h)]]
    if bottom:
        quads.append([(x0, base, -h), (x1, base, -h), (x1, base, h), (x0, base, h)])
    for q in quads:
        check_out(q, centre)
        ap.col_quad(p, *q)
    for pts in ([(x1, peak, 0), (x1, base, h), (x1, base, -h)], [(x0, peak, 0), (x0, base, -h), (x0, base, h)]):
        check_out(pts, centre)
        p.face('solid', pts)


def collision():
    p = ap.Part('body')
    for s in (-1, 1):
        x0, x1 = sorted((s * g.XI, s * g.END))
        # the wall and the post's foot, no top (the coping stands on it)
        ap.col_box(p, x0, x1, 0.0, WING_TOP, -0.4, 0.4, open=('bottom', 'top'))
        x0, x1 = sorted((s * g.XI, s * g.XO))
        ap.col_box(p, x0, x1, WING_TOP, g.BEAM[0] + 0.05, -0.21, 0.21, open=('bottom',))  # the post
        x0, x1 = sorted((s * (g.XO + 0.01), s * g.END))
        prism(p, x0, x1, WING_TOP, WING_PEAK, WING_H, False)                     # the wing's coping
    ap.col_box(p, -3.22, 3.22, g.BEAM[0], g.EAVE_LO + 0.05, -0.3, 0.3)         # beams to the soffit
    prism(p, -g.EX, g.EX, g.EAVE_LO, PEAK, g.EZ, True)                          # the steep roof
    ap.col_box(p, -g.XI - 0.05, g.XI + 0.05, 0.0, g.BEAM[0] + 0.1, -0.1, 0.1, open=('bottom',))   # leaves
    print('roof slope %.0f degrees, wing coping %.0f degrees' % (
        math.degrees(math.atan2(PEAK - g.EAVE_LO, g.EZ)), math.degrees(math.atan2(WING_PEAK - WING_TOP, WING_H))))
    return [p]


if __name__ == '__main__':
    ap.write(HERE / 'arch_wall_gate_shut_town_col.asset.json', ap.col_recipe('arch_wall_gate_shut_town_col', collision()))
    print('wrote arch_wall_gate_shut_town_col')
