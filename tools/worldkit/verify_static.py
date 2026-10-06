"""The World Checker's static checks: what can be checked from a pack without rendering.

Collision is read back from the pack as the console reads it: the floor, wall and ceiling
records of every cell's block, translated to world rows (exactly: cell centres are whole units)
and merged across the cells they were copied into. Floor queries here are the reader's, bit for
bit (the same bucket, the same integer edge tests and height rows), so a hole found here is a
hole the console has. See docs/WORLDCHECKER.md.
"""
from dataclasses import dataclass
import math
import struct

from .pack import ONE, KIND_FLOOR, KIND_WALL, KIND_CEILING, mesh_info
from .verify_render import checkable

FLAT_RAYS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
             (1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1), (-1, 1, 1), (-1, 1, -1), (-1, -1, 1), (-1, -1, -1)]


@dataclass
class WTri:
    """A collision triangle in world coordinates, as the pack stores it."""
    kind: int
    rows: tuple         # floors/ceilings: ((a, b, c), (e0, e1, e2) of (mx, mz, k)); walls: (p, edges, push)
    layer: int          # layer id, or None
    surface: int
    tag: int
    cell: tuple         # a cell that holds it
    verts: tuple = None  # corners (world units, float), reconstructed from the rows


def _centre(pack, i, j):
    half = 1 << (15 + pack.cell_shift)
    return (i << (16 + pack.cell_shift)) + half, (j << (16 + pack.cell_shift)) + half


def _layer_of(cell, info):
    m = (info >> 8) & 255
    if not m:
        return None
    return cell.layers[m.bit_length() - 1]


def _flat_corners(h, edges):
    """Corners (world units) of a floor or ceiling: where consecutive edge lines meet."""
    pts = []
    for e in range(3):
        a1, b1, c1 = edges[e - 1]
        a2, b2, c2 = edges[e]
        det = a1 * b2 - a2 * b1
        if det == 0:
            return None
        x = -ONE * (c1 * b2 - c2 * b1) / det
        z = -ONE * (a1 * c2 - a2 * c1) / det
        y = (h[0] * x + h[1] * z) / ONE + h[2]
        pts.append((x / ONE, y / ONE, z / ONE))
    return tuple(pts)


def _wall_corners(p, edges):
    pts = []
    for e in range(3):
        rows = [p[:3], edges[e - 1][:3], edges[e][:3]]
        rhs = [-p[3] * ONE, -edges[e - 1][3] * ONE, -edges[e][3] * ONE]
        m = [[float(v) for v in r] for r in rows]
        det = _det3(m)
        if det == 0:
            return None
        sol = []
        for k in range(3):
            mk = [r[:] for r in m]
            for r in range(3):
                mk[r][k] = rhs[r]
            sol.append(_det3(mk) / det / ONE)
        pts.append(tuple(sol))
    return tuple(pts)


def _det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
            m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def world_triangles(pack):
    """Every collision triangle of the pack's cells, once, in world rows (a triangle copied into
    several cells gives identical world rows in each)."""
    seen = {}
    for (i, j) in sorted(pack.cells, key=lambda ij: (ij[1], ij[0])):
        c = pack.cells[(i, j)]
        if c.coll is None:
            continue
        cx, cz = _centre(pack, i, j)
        for kind, recs in ((KIND_FLOOR, c.coll.floors), (KIND_CEILING, c.coll.ceilings)):
            for a, b, cc, info, edges, ymin, ymax in recs:
                h = (a, b, cc - (a * cx + b * cz) // ONE)
                ed = tuple((mx, mz, k - (mx * cx + mz * cz) // ONE) for mx, mz, k in edges)
                key = (kind, h, ed, info & 0xFFFF00FF, _layer_of(c, info))
                if key not in seen:
                    seen[key] = WTri(kind, (h, ed), _layer_of(c, info), info & 255, info >> 16, (i, j),
                                     _flat_corners(h, ed))
        for p, edges, hx, hz, inv, info in c.coll.walls:
            pw = (p[0], p[1], p[2], p[3] - (p[0] * cx + p[2] * cz) // ONE)
            ed = tuple((ux, uy, uz, k - (ux * cx + uz * cz) // ONE) for ux, uy, uz, k in edges)
            key = (KIND_WALL, pw, ed, info & 0xFFFF00FF, _layer_of(c, info))
            if key not in seen:
                seen[key] = WTri(KIND_WALL, (pw, ed), _layer_of(c, info), info & 255, info >> 16, (i, j),
                                 _wall_corners(pw, ed))
    return list(seen.values())


# ---- the reader's floor query, exactly

def near_cells(tris, cells, size, margin=1.0):
    """The triangles a check of `cells` ((i, j) pairs, cell size `size`) needs: near_boxes() of
    the cells grown by `margin`."""
    return near_boxes(tris, [(i * size - margin, j * size - margin, (i + 1) * size + margin, (j + 1) * size + margin)
                             for i, j in cells])


def near_boxes(tris, boxes):
    """The triangles whose bounds (seen from above) meet one of the boxes (x0, z0, x1, z1), and
    every triangle whose bounds meet theirs, so that an edge they share with a neighbour outside
    the boxes is still shared."""
    def meets(b, c):
        return b[0] <= c[2] and c[0] <= b[2] and b[1] <= c[3] and c[1] <= b[3]
    marked = [(t, (min(v[0] for v in t.verts), min(v[2] for v in t.verts),
                   max(v[0] for v in t.verts), max(v[2] for v in t.verts))) for t in tris if t.verts is not None]
    unions = []
    for c in boxes:
        core = [b for _, b in marked if meets(b, c)]
        if core:
            unions.append((min(b[0] for b in core), min(b[1] for b in core),
                           max(b[2] for b in core), max(b[3] for b in core)))
    return [t for t, b in marked if any(meets(b, u) for u in unions)]


def reader_floor(pack, x, y, z, layers_on, above=0):
    """wp_floor() at raw world point (x, y, z): the height (raw) of the highest present floor at
    or below y + above whose edge rows accept the point, and its tag; or None."""
    (i, j), lx, lz = pack.cell_of(x, z)
    c = pack.cells.get((i, j))
    if c is None or c.coll is None:
        return None
    mask = sum(1 << k for k, lid in enumerate(c.layers) if lid in layers_on)
    lim = y + above
    best = None
    for fid in c.coll.bucket(lx, lz)[0]:
        a, b, cc, info, edges, _, _ = c.coll.floors[fid]
        lm = (info >> 8) & 255
        if lm and not lm & mask:
            continue
        if any(mx * lx + mz * lz + k * ONE < 0 for mx, mz, k in edges):
            continue
        h = (a * lx + b * lz + cc * ONE) >> 16
        if h > lim or (best is not None and h <= best[0]):
            continue
        best = (h, info >> 16, info & 255)
    return best


# wp_floor_across()'s steps (raw units): 1/16 along x and z, 181/4096 in x and z along the diagonals.
ACROSS = ((4096, 0), (0, 4096), (2896, 2896), (2896, -2896))


def across_steps(bridge):
    """wp_floor_across()'s span in steps of 1/16: (span * 16) as s32, span in fixed point."""
    return (round(bridge * ONE) * 16) >> 16


def reader_floor_across(pack, x, y, z, layers_on, above, below, n):
    """wp_floor_across() at raw world point (x, y, z), bit for bit (above, below raw; n steps,
    across_steps()): wp_floor()'s floor when it is at or above y - below; else, along x, z and
    the two diagonals in that order, the nearest floor within y - below .. y + above on each
    side, a and b steps out with a + b <= n: the higher of the two (the first direction that
    has them); else wp_floor()'s answer. Returns (height raw, tag, surface) or None."""
    lo = y - below
    got = reader_floor(pack, x, y, z, layers_on, above)
    if got is not None and got[0] >= lo:
        return got

    def ok(k, sx, sz):
        g = reader_floor(pack, x + k * sx, y, z + k * sz, layers_on, above)
        return g if g is not None and g[0] >= lo else None
    for sx, sz in ACROSS:
        side = None
        a = 1
        while a < n:
            side = ok(a, sx, sz)
            if side is not None:
                break
            a += 1
        if side is None:
            continue
        other = None
        b = 1
        while a + b <= n:
            other = ok(-b, sx, sz)
            if other is not None:
                break
            b += 1
        if other is None:
            continue
        return side if side[0] > other[0] else other
    return got


def bridged(pack, x, h, z, layers_on, probe):
    """Whether the game's floor query bridges raw point (x, z) for a body at height h (units):
    wp_floor_across() with the probe's step above and below and its bridge as the span finds a
    floor within the step of h."""
    n = across_steps(probe.get('bridge', 0) or 0)
    if n < 2:
        return False
    y, step = round(h * ONE), round(probe['step'] * ONE)
    got = reader_floor_across(pack, x, y, z, layers_on, step, step, n)
    return got is not None and got[0] >= y - step


# ---- collision checks

def _present(t, layers_on):
    return t.layer is None or t.layer in layers_on


def _height(t, x, z):
    a, b, c = t.rows[0]
    return (a * x * ONE + b * z * ONE) / ONE / ONE + c / ONE


def _same_ends(a, b):
    """Whether boundary edges a and b ((p, q, tol_p, tol_q)) have the same ends, each within the
    larger of the two ends' tolerances."""
    (p, q, tp, tq), (r, s, tr, ts) = a, b
    close = lambda u, v, t: abs(u[0] - v[0]) <= t and abs(u[2] - v[2]) <= t  # noqa: E731
    return (close(p, r, max(tp, tr)) and close(q, s, max(tq, ts))) or (close(p, s, max(tp, ts)) and close(q, r, max(tq, tr)))


def _corner_tol(t, e):
    """How far (units) corner e of floor t, worked out from its rounded edge rows (where edge
    lines e - 1 and e meet), can lie from the true corner: 2/1000 of a unit, plus the rows'
    rounding (half a raw unit in k, and half a raw unit of the unit normal times the distance from
    the edge's midpoint, at most its length) divided by the sine of the angle between the two
    lines (a raw unit and half the longest edge's raw units, over the sine). A long thin triangle
    meets its long edges at a small angle, so its corners slide along them by much more than 2/1000
    (0.0033 units for a 2 x 50 quad's diagonal, whose tolerance this makes 0.012)."""
    (a1, b1, _), (a2, b2, _) = t.rows[1][e - 1], t.rows[1][e]
    l1, l2 = math.hypot(a1, b1), math.hypot(a2, b2)
    sin = abs(a1 * b2 - a2 * b1) / (l1 * l2) if l1 and l2 else 0.0
    v = t.verts
    reach = max(math.hypot(v[k][0] - v[k - 1][0], v[k][2] - v[k - 1][2]) for k in range(3))
    delta = (1 + reach / 2) / ONE
    return 2e-3 + (delta / sin if sin > 1e-9 else float('inf'))


def _boundary_edges(floors):
    """Edges of floors with no neighbour across them: no other floor has the exactly opposite
    edge row (the encoder makes rows of a shared edge exactly opposite, so the two lie on one
    line) with the same ends. The ends are worked out from the rounded rows; how closely they agree
    depends on the angles at the corners (_corner_tol)."""
    edges = {}
    tols = {}
    for t in floors:
        if t.verts is None:
            continue
        tc = [_corner_tol(t, e) for e in range(3)]
        tols[id(t)] = tc
        for e, row in enumerate(t.rows[1]):
            edges.setdefault(row, []).append((t.verts[e], t.verts[(e + 1) % 3], tc[e], tc[(e + 1) % 3]))
    out = []
    for t in floors:
        if t.verts is None:
            continue
        tc = tols[id(t)]
        for e, row in enumerate(t.rows[1]):
            # edge e runs between the corners where edge lines e-1/e and e/e+1 meet
            p, q = t.verts[e], t.verts[(e + 1) % 3]
            mine = (p, q, tc[e], tc[(e + 1) % 3])
            if any(_same_ends(mine, o) for o in edges.get((-row[0], -row[1], -row[2]), ())):
                continue
            out.append((t, row, p, q))
    return out


def crack_check(pack, floors_all, layers_on, probe, settings, limit):
    """Holes in walkable floors that a point query can fall through: from points along each
    boundary edge of a floor, step outward up to probe radius; a gap (no floor within probe step
    of the edge's height) followed by a floor again is a crack. Also boundary edges that run
    along another floor's boundary edge, facing it, at a height within probe step, without
    sharing its rows: a T-junction or mismatched corners (WORLDPACK.md, "Floor and ceiling
    records"), which leave a sliver no row accepts."""
    floors = [t for t in floors_all if t.kind == KIND_FLOOR and _present(t, layers_on)]
    edges = _boundary_edges(floors)
    radius, step = probe['radius'], probe['step']
    bridging = across_steps(probe.get('bridge', 0) or 0) >= 2
    per_unit = settings['crack_samples_per_unit']
    offsets = [1 / ONE, 2 / ONE, 4 / ONE, 16 / ONE, 1 / 256, 1 / 64]
    t = 1 / 16
    while t <= radius + 1e-9:
        offsets.append(t)
        t += 1 / 16
    S = 1 << pack.cell_shift
    findings = {}
    count = 0
    for tri, row, p, q in edges:
        ln = math.hypot(q[0] - p[0], q[2] - p[2])
        if ln == 0:
            continue
        mlen = math.hypot(row[0], row[1])
        out = (-row[0] / mlen, -row[1] / mlen)
        n = max(2, min(64, math.ceil(ln * per_unit)))
        for s in range(n):
            f = (s + 0.5) / n
            px, pz = p[0] + (q[0] - p[0]) * f, p[2] + (q[2] - p[2]) * f
            h = _height(tri, px, pz)
            gap = None
            holes = []
            last = 0.0                  # the last offset with a floor before the gap
            for off in offsets:
                x, z = round((px + out[0] * off) * ONE), round((pz + out[1] * off) * ONE)
                got = reader_floor(pack, x, round((h + step) * ONE), z, layers_on)
                present = got is not None and got[0] >= (h - step) * ONE
                if not present:
                    holes.append((off, x, z))
                    if gap is None:
                        gap = off
                elif gap is None:
                    last = off
                else:
                    if bridging:
                        # the game's query bridges it unless a point of the gap is not bridged
                        gap = next((o for o, hx, hz in holes if not bridged(pack, hx, h, hz, layers_on, probe)), None)
                        if gap is None:
                            break
                    count += 1
                    key = (tri.tag, got[1], tri.cell)
                    if key not in findings:
                        findings[key] = {'code': 'crack', 'cell': list(tri.cell), 'floor_tag': tri.tag,
                                         'beyond_tag': got[1], 'at': [round(px, 4), round(h, 4), round(pz, 4)],
                                         'gap': [round(gap, 6), round(off, 6)], 'samples': 0,
                                         'on_seam': _on_seam(px, pz, S), 'width': 0.0}
                    found = findings[key]
                    found['samples'] += 1
                    width = round(off - last, 6)    # at most this wide here; the widest of the samples
                    if width > found['width']:
                        found['width'] = width
                        found['widest_at'] = [round(px, 4), round(h, 4), round(pz, 4)]
                    break
    # collinear boundary edges facing each other without shared rows
    lines = {}
    for tri, row, p, q in edges:
        mlen = math.hypot(row[0], row[1])
        nx, nz = row[0] / mlen, row[1] / mlen
        off = row[2] * ONE / mlen / ONE        # n . x + off = 0, units
        sgn = 1 if (nx > 1e-9 or (abs(nx) <= 1e-9 and nz > 0)) else -1
        key = (round(math.atan2(sgn * nz, sgn * nx) * 2000), round(sgn * off * 128))
        lines.setdefault(key, []).append((tri, row, p, q, sgn))
    mism = {}
    for key, group in sorted(lines.items()):
        cands = list(group)
        for dk in ((0, 1), (1, 0), (1, 1), (0, -1), (-1, 0), (-1, -1), (1, -1), (-1, 1)):
            cands += lines.get((key[0] + dk[0], key[1] + dk[1]), [])
        for a in group:
            for b in cands:
                if a is b or a[4] == b[4] or id(a[0]) >= id(b[0]):
                    continue
                r = _facing_overlap(a, b, step)
                if r is None:
                    continue
                if bridging and _sliver_bridged(pack, a, r, layers_on, probe):
                    continue
                k2 = (a[0].tag, b[0].tag, a[0].cell)
                if k2 not in mism:
                    mx_, mz_ = r
                    mism[k2] = {'code': 'edge_mismatch', 'cell': list(a[0].cell), 'floor_tag': a[0].tag,
                                'beyond_tag': b[0].tag,
                                'at': [round(mx_, 4), round(_height(a[0], mx_, mz_), 4), round(mz_, 4)],
                                'on_seam': _on_seam(mx_, mz_, S)}
    found = list(findings.values()) + list(mism.values())
    found.sort(key=lambda f: (f['code'], f['cell'], f['floor_tag'], f['beyond_tag']))
    return found[:limit], len(found), len(edges), count


# ---- the crack baseline (NAME.cracks.json beside the recipe; WORLDCHECKER.md, "Crack baseline")

BASELINE_FORMAT = 'mei-world-cracks'
BASELINE_KEYS = ('code', 'cell', 'floor_tag', 'beyond_tag', 'layers', 'at', 'width')


def _same_crack(f, b):
    """Whether finding f is baseline entry b: the same code and layers, and the same cell and
    tags, or a point within 1 unit across and 0.5 up of b's (tags change when a cell's placements
    are renumbered; a finding's point moves when its first sample does)."""
    if f['code'] != b['code'] or sorted(f.get('layers', [])) != sorted(b.get('layers', [])):
        return False
    if list(f['cell']) == list(b['cell']) and f['floor_tag'] == b['floor_tag'] and f['beyond_tag'] == b['beyond_tag']:
        return True
    (x, y, z), (bx, by, bz) = f['at'], b['at']
    return abs(x - bx) <= 1.0 and abs(z - bz) <= 1.0 and abs(y - by) <= 0.5


def against_baseline(found, baseline):
    """Findings split by the baseline's entries: (new, known, fixed), fixed being the entries
    no finding matches."""
    new, known, used = [], [], set()
    for f in found:
        hit = next((k for k, b in enumerate(baseline) if _same_crack(f, b)), None)
        if hit is None:
            new.append(f)
        else:
            known.append(f)
            used.add(hit)
    return new, known, [b for k, b in enumerate(baseline) if k not in used]


def baseline_entry(f):
    """A finding as NAME.cracks.json keeps it."""
    out = {k: f[k] for k in BASELINE_KEYS if k in f}
    for k in ('floor', 'beyond', 'route'):
        if k in f:
            out[k] = f[k]
    return out


def _sliver_bridged(pack, a, r, layers_on, probe):
    """Whether the game's floor query bridges the sliver a mismatched edge can leave: at the
    overlap's midpoint r and 1 and 2 raw units either side of edge a's line, every point without
    a floor within the step of the edge's height is bridged (bridged())."""
    tri, row = a[0], a[1]
    mlen = math.hypot(row[0], row[1])
    nx, nz = row[0] / mlen, row[1] / mlen
    h = _height(tri, r[0], r[1])
    step = probe['step']
    for t in (-2, -1, 0, 1, 2):
        x, z = round(r[0] * ONE + nx * t), round(r[1] * ONE + nz * t)
        got = reader_floor(pack, x, round((h + step) * ONE), z, layers_on)
        if got is not None and got[0] >= (h - step) * ONE:
            continue
        if not bridged(pack, x, h, z, layers_on, probe):
            return False
    return True


def _on_seam(x, z, S):
    return abs(x / S - round(x / S)) * S < 1e-3 or abs(z / S - round(z / S)) * S < 1e-3


def _facing_overlap(a, b, step):
    """Whether boundary edges a and b lie on one line (within 1/1024 unit), face each other,
    overlap by more than 1/256 unit and are at heights within step there: the midpoint."""
    ta, ra, pa, qa, _ = a
    tb, rb, pb, qb, _ = b
    la, lb = math.hypot(ra[0], ra[1]), math.hypot(rb[0], rb[1])
    if abs(ra[0] / la + rb[0] / lb) > 1e-4 or abs(ra[1] / la + rb[1] / lb) > 1e-4:
        return None
    # distance of b's ends from a's line
    for pt in (pb, qb):
        if abs((ra[0] * pt[0] + ra[1] * pt[2]) / la + ra[2] / la) > 1 / 1024:
            return None
    dx, dz = qa[0] - pa[0], qa[2] - pa[2]
    ln = math.hypot(dx, dz)
    if ln == 0:
        return None
    ux, uz = dx / ln, dz / ln
    sa = sorted([0.0, ln])
    sb = sorted([(pb[0] - pa[0]) * ux + (pb[2] - pa[2]) * uz, (qb[0] - pa[0]) * ux + (qb[2] - pa[2]) * uz])
    lo, hi = max(sa[0], sb[0]), min(sa[1], sb[1])
    if hi - lo <= 1 / 256:
        return None
    mid = (lo + hi) / 2
    x, z = pa[0] + ux * mid, pa[2] + uz * mid
    if abs(_height(ta, x, z) - _height(tb, x, z)) > step:
        return None
    return x, z


def _ray_hit(t, a, d):
    """First crossing of segment a + d s (s in 0..1, world units) with triangle t, as the reader
    tests it in floating point: (s, from_behind) or None. Points it starts on do not count."""
    if t.kind == KIND_WALL:
        p, edges = t.rows
        n = [p[0] / ONE, p[1] / ONE, p[2] / ONE]
        fa = n[0] * a[0] + n[1] * a[1] + n[2] * a[2] + p[3] / ONE
        fb = fa + n[0] * d[0] + n[1] * d[1] + n[2] * d[2]
    else:
        (ha, hb, hc), edges = t.rows
        fa = a[1] - (ha * a[0] + hb * a[2]) / ONE - hc / ONE
        bx, by, bz = a[0] + d[0], a[1] + d[1], a[2] + d[2]
        fb = by - (ha * bx + hb * bz) / ONE - hc / ONE
    if abs(fa) < 1e-6 or not ((fa > 0 and fb <= 0) or (fa < 0 and fb >= 0)):
        return None
    s = fa / (fa - fb)
    q = (a[0] + d[0] * s, a[1] + d[1] * s, a[2] + d[2] * s)
    if t.kind == KIND_WALL:
        if any((e[0] * q[0] + e[1] * q[1] + e[2] * q[2]) / ONE + e[3] / ONE < -1e-6 for e in edges):
            return None
        back = fa < 0
    else:
        if any((e[0] * q[0] + e[1] * q[2]) / ONE + e[2] / ONE < -1e-6 for e in edges):
            return None
        back = (t.kind == KIND_FLOOR) == (fa < 0)
    return s, back


class TriGrid:
    """Triangles filed by their boxes on a 4-unit grid over x and z, for segment queries."""
    CELL = 4.0

    def __init__(self, tris):
        self.cells = {}
        self.box = {}
        for n, t in enumerate(tris):
            if t.verts is None:
                lo, hi = (-1e9,) * 3, (1e9,) * 3
                self.cells.setdefault(None, []).append(n)
            else:
                lo = tuple(min(v[k] for v in t.verts) for k in range(3))
                hi = tuple(max(v[k] for v in t.verts) for k in range(3))
                for gx in range(math.floor(lo[0] / self.CELL), math.floor(hi[0] / self.CELL) + 1):
                    for gz in range(math.floor(lo[2] / self.CELL), math.floor(hi[2] / self.CELL) + 1):
                        self.cells.setdefault((gx, gz), []).append(n)
            self.box[n] = (lo, hi)
        self.tris = tris

    def near(self, lo, hi):
        found = set(self.cells.get(None, ()))
        for gx in range(math.floor(lo[0] / self.CELL), math.floor(hi[0] / self.CELL) + 1):
            for gz in range(math.floor(lo[2] / self.CELL), math.floor(hi[2] / self.CELL) + 1):
                found.update(self.cells.get((gx, gz), ()))
        return [self.tris[n] for n in sorted(found)
                if all(self.box[n][0][k] <= hi[k] + 1e-3 and self.box[n][1][k] >= lo[k] - 1e-3 for k in range(3))]


def first_hit(grid, a, d, layers_on=None):
    """The nearest crossing of segment a -> a + d with a triangle in grid (present under
    layers_on, or every triangle when None): (s, from_behind, triangle) or None."""
    best = None
    lo = [min(a[k], a[k] + d[k]) for k in range(3)]
    hi = [max(a[k], a[k] + d[k]) for k in range(3)]
    for t in grid.near(lo, hi):
        if layers_on is not None and not _present(t, layers_on):
            continue
        h = _ray_hit(t, a, d)
        if h is not None and (best is None or h[0] < best[0]):
            best = (h[0], h[1], t)
    return best


def entity_check(pack, tris, settings, limit):
    """Entities whose origin is inside solid collision: every one of 14 rays from it (axes and
    diagonals, `solid_ray_length` units) first meets a triangle from behind."""
    S = 1 << pack.cell_shift
    reach = settings['solid_ray_length']
    grid = tris if isinstance(tris, TriGrid) else TriGrid(tris)
    out = []
    count = 0
    for (i, j) in sorted(pack.cells, key=lambda ij: (ij[1], ij[0])):
        c = pack.cells[(i, j)]
        for e in c.entities:
            cx, cz = i * S + S / 2, j * S + S / 2
            o = (e['pos'][0] / ONE + cx, e['pos'][1] / ONE, e['pos'][2] / ONE + cz)
            on = set()
            if e['mask']:
                on.add(c.layers[e['mask'].bit_length() - 1])
            inside = True
            hits = []
            for r in FLAT_RAYS:
                ln = math.sqrt(sum(x * x for x in r))
                # a slight skew keeps rays off edges and corners that line up with the axes
                d = [reach * (r[0] / ln + 0.0123), reach * (r[1] / ln + 0.0071), reach * (r[2] / ln + 0.0037)]
                h = first_hit(grid, o, d, on)
                if h is None or not h[1]:
                    inside = False
                    break
                hits.append(h[2].tag)
            if inside:
                count += 1
                if len(out) < limit:
                    out.append({'code': 'entity_in_solid', 'cell': [i, j], 'entity': e['number'], 'type': e['type'],
                                'at': [round(x, 4) for x in o], 'enclosing_tags': sorted(set(hits))})
    return out, count


# ---- references and counts

def mesh_triangles_count(data, off):
    nv, nf, vo, fo = mesh_info(data[off:])
    tris = 0
    for k in range(nf):
        flags = data[off + fo + 36 * k]
        tris += 2 if flags & 4 else 1
    return nv, nf, tris


def reference_check(pack, far_ring):
    """Face indices within their meshes, stand-ins where a cell can be seen from 2 or more cells
    away, layers that are used. Returns (errors, warnings)."""
    errors, warnings = [], []
    data = pack.data
    meshes = set(pack.meshes)
    for c in pack.cells.values():
        meshes.update(p['mesh'] for p in c.placements)
        meshes.update(e['mesh'] for e in c.entities if e['mesh'])
        if c.standin:
            meshes.add(c.standin)
    unverifiable = 0
    textured = any(r.textures for r in pack.regions)
    for off in sorted(meshes):
        nv, nf, vo, fo = mesh_info(data[off:])
        for k in range(nf):
            at = off + fo + 36 * k
            flags = data[at]
            idx = struct.unpack_from('<4H', data, at + 4)[:4 if flags & 4 else 3]
            if max(idx) >= nv:
                errors.append({'code': 'bad_face_index', 'mesh': off, 'face': k,
                               'message': f'face {k} of the mesh at {off} names vertex {max(idx)} of {nv}'})
            uv = struct.unpack_from('<4H', data, at + 28)[:len(idx)]
            tex = data[at + 2]
            if not checkable(flags, tex, uv) and not (textured and not flags & 8):
                # (a textured pack: textured faces are judged whole or per texel, verify_render.py)
                unverifiable += 1
    if unverifiable:
        warnings.append({'code': 'unverifiable_faces', 'faces': unverifiable,
                         'message': 'semi-transparent or textured (not palette swatch) faces: their pixels '
                                    'are not compared in the ordering check'})
    cells = set(pack.cells)
    if far_ring >= 2:
        for (i, j), c in sorted(pack.cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            if c.standin:
                continue
            seen_from = [ij for ij in cells if 2 <= max(abs(ij[0] - i), abs(ij[1] - j)) <= far_ring]
            if seen_from:
                errors.append({'code': 'standin_missing', 'cell': [i, j], 'policy': True,
                               'message': f'cell ({i}, {j}) has no stand-in but is in the far ring of '
                                          f'{len(seen_from)} cells'})
    used = set()
    for c in pack.cells.values():
        used.update(c.layers)
    for lid, (name, group, on) in enumerate(pack.layers):
        if lid not in used:
            warnings.append({'code': 'layer_unused', 'layer': name, 'message': f'no cell has layer {name!r}'})
    return errors, warnings


GROUND_TOL = 1 / 64        # how far behind a ground face's plane counts as behind it (units)
GROUND_UP = math.sin(math.radians(10))  # ground faces whose normal is at least 10 degrees above level


def _world_faces(pack, inst, mesh):
    """An instance's triangles in world coordinates: [(corners, front normal, face number,
    double-sided)]; a quad gives (0, 1, 2) and (2, 1, 3) as collision does."""
    S = 1 << pack.cell_shift
    cx, cz = inst.cell[0] * S + S / 2, inst.cell[1] * S + S / 2
    if inst.yaw is not None:
        c, s = math.cos(inst.yaw), math.sin(inst.yaw)
    else:
        c, s = inst.cos / ONE, inst.sin / ONE
    px, py, pz = inst.pos[0] / ONE + cx, inst.pos[1] / ONE, inst.pos[2] / ONE + cz
    vs = []
    for x, y, z in mesh.raw:
        x, y, z = x / ONE, y / ONE, z / ONE
        vs.append((c * x + s * z + px, y + py, -s * x + c * z + pz))
    out = []
    for k, (flags, idx, _, _, _) in enumerate(mesh.faces):
        tris = [(idx[0], idx[1], idx[2])] + ([(idx[2], idx[1], idx[3])] if len(idx) == 4 else [])
        for t in tris:
            a, b, cc = (vs[i] for i in t)
            n = _cross(_sub(cc, a), _sub(b, a))
            ln = math.sqrt(_dot(n, n))
            if ln > 1e-12:
                out.append(((a, b, cc), tuple(q / ln for q in n), k, bool(flags & 16)))
    return out


def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _clip_side(poly, n, d):
    """The part of a convex polygon where n . p - d > 0."""
    out = []
    for i in range(len(poly)):
        a, b = poly[i - 1], poly[i]
        da, db = _dot(n, a) - d, _dot(n, b) - d
        if (da > 0) != (db > 0):
            t = da / (da - db)
            out.append(tuple(a[q] + (b[q] - a[q]) * t for q in range(3)))
        if db > 0:
            out.append(b)
    return out


def ground_check(pack, near_far, limit, cells=None):
    """Likely misuse of the ground flag (docs/WORLDPACK.md, "Ground"): geometry that a ground
    face can hide. The reader draws ground first, so whatever is drawn after it shows through
    ground that truly hides it, and ground faces that can overlap on screen are sorted among
    themselves by average depth like any other faces. A pair is reported when a camera above a
    ground face that faces up (GROUND_UP) can see the other face through it: part of the other
    face lies more than GROUND_TOL behind the ground face's plane, part of the ground face lies in
    front of the other face's plane, and those parts are within the near pass's reach (near_far)
    of each other. The sides and undersides of ground meshes are left out as hiding faces: only
    cameras below the ground's top see through them. Layers that can never be on together are
    skipped. Returns warnings: one per pair of
    instances, at most `limit` of each code, with the totals. cells: only the ground of these
    cells ((i, j) pairs; the quick check's focus), or None for every cell."""
    from .verify_render import instances, read_mesh
    insts = [i for i in instances(pack) if i.key[0] != 'standin']
    if cells is not None:
        insts = [i for i in insts if any(max(abs(i.cell[0] - a), abs(i.cell[1] - b)) <= 2 for a, b in cells)]
    ground = [i for i in insts if i.ground and (cells is None or tuple(i.cell) in cells)]
    if not ground:
        return []
    meshes, faces = {}, {}
    for inst in insts:
        if inst.mesh not in meshes:
            meshes[inst.mesh] = read_mesh(pack.data, inst.mesh)
        faces[inst.key] = _world_faces(pack, inst, meshes[inst.mesh])

    def layer(inst):
        if not inst.mask:
            return None
        return pack.cells[inst.cell].layers[inst.mask.bit_length() - 1]

    def exclusive(a, b):
        la, lb = layer(a), layer(b)
        return (la is not None and lb is not None and la != lb and
                pack.layers[la][1] != 0xFF and pack.layers[la][1] == pack.layers[lb][1])

    found = {'ground_hides': [], 'ground_over_ground': []}
    total = {'ground_hides': 0, 'ground_over_ground': 0}
    for g in ground:
        for x in insts:
            if max(abs(g.cell[0] - x.cell[0]), abs(g.cell[1] - x.cell[1])) > 2 or exclusive(g, x):
                continue
            hit = _ground_pair(faces[g.key], faces[x.key], near_far)
            if hit is None:
                continue
            code = 'ground_over_ground' if x.ground else 'ground_hides'
            total[code] += 1
            if len(found[code]) < limit:
                gf, xf, behind, point = hit
                found[code].append({'ground': _inst_name(g, gf), 'other': _inst_name(x, xf),
                                    'behind': round(behind, 4), 'point': [round(q, 4) for q in point]})
    out = []
    if total['ground_hides']:
        out.append({'code': 'ground_hides', 'pairs': total['ground_hides'], 'findings': found['ground_hides'],
                    'message': 'geometry drawn after the ground lies behind a ground face: from some cameras '
                               'the ground truly hides it, and it is drawn over the ground anyway'})
    if total['ground_over_ground']:
        out.append({'code': 'ground_over_ground', 'pairs': total['ground_over_ground'],
                    'findings': found['ground_over_ground'],
                    'message': 'ground faces that can overlap on screen: the ground pass sorts them by '
                               'average depth, so they can be drawn in the wrong order'})
    return out


def _inst_name(inst, face):
    out = {'kind': inst.key[0], 'cell': list(inst.cell), 'face': face}
    if inst.key[0] == 'placement':
        out['placement'], out['tag'] = inst.key[3], inst.tag
    else:
        out['entity'] = inst.key[1]
    return out


def _ground_pair(gfaces, xfaces, reach):
    """The first (ground face, other face, depth behind, a point behind) where a face of x can
    be seen through a ground face, or None."""
    xs = [v for f in xfaces for v in f[0]]
    if not xs:
        return None
    for gv, gn, gk, gdouble in gfaces:
        for side in ((1, -1) if gdouble else (1,)):
            n = tuple(side * q for q in gn)
            if n[1] < GROUND_UP:
                continue
            d = _dot(n, gv[0])
            if min(_dot(n, v) for v in xs) - d >= -GROUND_TOL:
                continue                    # all of x is in front of this ground face
            for xv, xn, xk, xdouble in xfaces:
                if xv == gv:
                    continue
                behind = _clip_side(list(xv), tuple(-q for q in n), -d + GROUND_TOL)
                if not behind:
                    continue
                for xside in ((1, -1) if xdouble else (1,)):
                    m = tuple(xside * q for q in xn)
                    front = _clip_side(list(gv), m, _dot(m, xv[0]) + GROUND_TOL)
                    if not front:
                        continue
                    near = min(math.sqrt(_dot(_sub(p, q), _sub(p, q))) for p in behind for q in front)
                    if near <= reach:
                        p = max(behind, key=lambda v: d - _dot(n, v))
                        return gk, xk, d - _dot(n, p), p
    return None


def counts(pack):
    data = pack.data
    cache = {}

    def mc(off):
        if off not in cache:
            cache[off] = mesh_triangles_count(data, off)
        return cache[off]
    cells, regions = [], {}
    for (i, j) in sorted(pack.cells, key=lambda ij: (ij[1], ij[0])):
        c = pack.cells[(i, j)]
        tri = sum(mc(p['mesh'])[2] for p in c.placements)
        verts = sum(mc(p['mesh'])[0] for p in c.placements)
        base = sum(mc(p['mesh'])[2] for p in c.placements if not p['mask'])
        layered = {}
        for p in c.placements:
            if p['mask']:
                layered[p['mask']] = layered.get(p['mask'], 0) + mc(p['mesh'])[2]
        rec = {'cell': [i, j], 'region': c.region, 'placements': len(c.placements), 'triangles': tri,
               'triangles_no_layers': base, 'vertices': verts,
               'standin_triangles': mc(c.standin)[2] if c.standin else None,
               'entities': len(c.entities),
               'entity_triangles': sum(mc(e['mesh'])[2] for e in c.entities if e['mesh']),
               'collision': {'floors': len(c.coll.floors) if c.coll else 0,
                             'walls': len(c.coll.walls) if c.coll else 0,
                             'ceilings': len(c.coll.ceilings) if c.coll else 0},
               'layers': [pack.layers[l][0] for l in c.layers]}
        cells.append(rec)
        r = regions.setdefault(c.region, {'region': c.region, 'name': pack.regions[c.region].name, 'cells': 0,
                                          'placements': 0, 'triangles': 0, 'standin_triangles': 0, 'entities': 0})
        r['cells'] += 1
        r['placements'] += rec['placements']
        r['triangles'] += tri
        r['standin_triangles'] += rec['standin_triangles'] or 0
        r['entities'] += rec['entities']
    return cells, [regions[k] for k in sorted(regions)]
