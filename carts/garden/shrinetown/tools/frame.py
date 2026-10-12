#!/usr/bin/env python3
"""The level's frame against the frame rule (DESIGN.md 12.9, "The level's frame"): for every
point of the four edges, how high the frame stands there and how high a body can get at that
point from any floor inside; with --tops, the height each 8 m of edge needs; with --probes, the
frame scenarios' probes (carts/garden/tests/frame_probes.akr, scenarios 581-584).

    python3 carts/garden/shrinetown/tools/frame.py --build-dir build-mine [--table] [--tops] [--probes]

The rule: from a floor at height F a body gets to F + REACH at the frame (a backflip, 4.8 m, and
a ledge grab, 1.75 m: 6.55, rounded up) when the floor is within NEAR (4 m) of it; from farther a
glide loses 1 m in RATIO (5) metres, so F + REACH - (d - NEAR) / RATIO. A running triple jump
starts its glide 4.5 m up, under the backflip's 4.8, so the backflip's reach covers it. The glide
sinks 1 m in 4 at its steady speed, but a running third jump's speed carries it farther (the
explorer bot, tools/explore, measured about 1 in 4.8 over 100 m), so 5. Every
floor of the level counts, however far (a glide from the mountain's plateau, 62-70 m, crosses the
level); nothing between is taken to stop a glide. At each edge point the frame's height is the
lowest, along 2 m of edge, of the highest surface across the frame's strip (STRIP metres inside
the edge to 3 m outside it: the rims, the fences, hoardings and neighbours' backs): floors, the
collision's walls and the terrain's top (a steep face is a wall with no floor). Floors in a strip
are not floors to start from, unless a body reaches them, when they count for the rest of the
edge (the edge fence, 3 m, is a step to the hoarding beside it). A point leaks when the reach
there is above the frame.

The floors and walls are the pack's (every layer on), from the compiled world in BUILD/kit-cache
(`mei_world.py`'s quick tools compile it when it has changed, about a minute); the terrain's top
is the World Kit's terrain field, from the world file. Exits 1 when an edge leaks. Needs NumPy.
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np

ST = Path(__file__).resolve().parent.parent
REPO = ST.parents[2]
sys.path.insert(0, str(REPO / 'tools'))

REACH, NEAR, RATIO = 6.6, 4.0, 5.0
STEP = 0.5                      # the floor grid
OUTSIDE = 3.0                   # how far outside the edge the strip reaches
WINDOW = 1.0                    # half the length of edge a frame height is the lowest over
MARGIN = 0.5                    # over the reach, for --tops
FINE = 12.0                     # floors nearer the edge than this are taken at STEP, farther ones by
POOL = 2.0                      # the highest in each POOL square (its middle: at most 0.36 m too low)
W, D = 320.0, 384.0
# edge: (strip depth inside, point at (along s, depth d) -> (x, z), along length)
EDGES = {
    'S': (1.0, lambda s, d: (s, d), W),
    'N': (4.5, lambda s, d: (s, D - d), W),
    'W': (2.5, lambda s, d: (d, s), D),
    'E': (2.5, lambda s, d: (W - d, s), D),
}
PROBE_EVERY = 8.0               # metres of edge a probe point


def floors(build):
    """The top floor every STEP over the level and OUTSIDE beyond it, from the pack (every floor of
    the cell a point is in, or beyond the level of the outermost cell: placements reach over the
    edge), and the terrain's top there (a steep face is a wall, not a floor, but it stands as high
    as its top): (H floors, T terrain, xs, zs), NaN where none."""
    from worldkit import quick as Q
    from kitcore.vector import ONE
    world = Q.load_world(str(ST / 'shrinetown.world.json'), None, str(Path(build) / 'kit-cache'))
    pack = world.decoded
    xs = np.arange(-OUTSIDE, W + OUTSIDE, STEP) + STEP / 2
    zs = np.arange(-OUTSIDE, D + OUTSIDE, STEP) + STEP / 2
    H = np.full((len(zs), len(xs)), np.nan)
    shift = 16 + pack.cell_shift
    size = 1 << pack.cell_shift
    imax, jmax = int(W) // size - 1, int(D) // size - 1
    half = 1 << (15 + pack.cell_shift)
    XI = np.clip(np.floor(xs / size).astype(int), 0, imax)
    ZJ = np.clip(np.floor(zs / size).astype(int), 0, jmax)
    for (i, j), c in pack.cells.items():
        if c.coll is None or not c.coll.floors:
            continue
        ca, cb = np.nonzero(XI == i)[0], np.nonzero(ZJ == j)[0]
        if not len(ca) or not len(cb):
            continue
        A, B = np.meshgrid(ca, cb)
        lx = (np.round(xs[A] * ONE).astype(np.int64) - (i << shift) - half).ravel()
        lz = (np.round(zs[B] * ONE).astype(np.int64) - (j << shift) - half).ravel()
        fl = c.coll.floors
        fa = np.array([f[0] for f in fl], np.int64)
        fb = np.array([f[1] for f in fl], np.int64)
        fc = np.array([f[2] for f in fl], np.int64)
        ed = np.array([[e for e in f[4]] for f in fl], np.int64)        # (n, 3, 3)
        best = np.full(lx.shape, np.iinfo(np.int64).min)
        for k0 in range(0, len(fl), 256):
            sl = slice(k0, k0 + 256)
            h = (fa[sl, None] * lx[None] + fb[sl, None] * lz[None] + fc[sl, None] * ONE) >> 16
            ok = np.ones(h.shape, bool)
            for e in range(3):
                ok &= (ed[sl, e, 0, None] * lx[None] + ed[sl, e, 1, None] * lz[None] + ed[sl, e, 2, None] * ONE) >= 0
            h = np.where(ok, h, np.iinfo(np.int64).min)
            best = np.maximum(best, h.max(axis=0))
        got = best > np.iinfo(np.int64).min
        vals = np.where(got, best / ONE, np.nan).reshape(A.shape)
        H[B, A] = vals
    return H, np.fmax(terrain_top(xs, zs), wall_top(pack, xs, zs)), xs, zs


def wall_top(pack, xs, zs):
    """The highest point of any wall (the collision's steep faces) over each grid point near the
    edges: the neighbours' backs, the hoardings, the rims' faces. A wall's corners are where its
    plane meets its edge rows (pack.wall_record)."""
    from kitcore.vector import ONE
    T = np.full((len(zs), len(xs)), np.nan)
    shift = 16 + pack.cell_shift
    half = 1 << (15 + pack.cell_shift)
    near = 6.0
    for (i, j), c in pack.cells.items():
        if c.coll is None:
            continue
        ox, oz = ((i << shift) + half) / ONE, ((j << shift) + half) / ONE
        for n, edges, *_ in c.coll.walls:
            rows = [np.array(n[:3], float)] + [np.array(e[:3], float) for e in edges]
            rhs = [-n[3]] + [-e[3] for e in edges]
            vs = []
            for a, b in ((0, 1), (1, 2), (2, 0)):
                M = np.array([rows[0], rows[1 + a], rows[1 + b]])
                try:
                    v = np.linalg.solve(M, np.array([rhs[0], rhs[1 + a], rhs[1 + b]], float))
                except np.linalg.LinAlgError:
                    break
                vs.append(v)
            if len(vs) < 3:
                continue
            V = np.array(vs) + np.array([ox, 0.0, oz])
            if not ((V[:, 0].min() < near or V[:, 0].max() > W - near or V[:, 2].min() < near or V[:, 2].max() > D - near)):
                continue
            # points over the triangle every quarter metre, the highest per grid point
            ext = max(np.ptp(V[:, 0]), np.ptp(V[:, 1]), np.ptp(V[:, 2]))
            k = max(2, int(ext / 0.25) + 1)
            u, w = np.meshgrid(np.linspace(0, 1, k), np.linspace(0, 1, k))
            m = u + w <= 1
            P = V[0] + np.outer(u[m], V[1] - V[0]) + np.outer(w[m], V[2] - V[0])
            b = np.clip(np.floor((P[:, 2] - zs[0] + STEP / 2) / STEP).astype(int), 0, len(zs) - 1)
            a = np.clip(np.floor((P[:, 0] - xs[0] + STEP / 2) / STEP).astype(int), 0, len(xs) - 1)
            flat = np.full(T.size, -np.inf)
            np.maximum.at(flat, b * len(xs) + a, P[:, 1])
            flat = flat.reshape(T.shape)
            T = np.where(np.isfinite(flat), np.fmax(T, flat), T)
    return T


def terrain_top(xs, zs, lowest=False):
    """The terrain's top (its highest corner, its cliff sheet's; with lowest, its lowest corner)
    at each grid point, NaN off it."""
    import json
    from worldkit import terrain as TR
    w = json.loads((ST / 'shrinetown.world.json').read_text())
    t = w['terrain']
    ctx = TR.Context(ST, w['grid']['cell_size'], w.get('paths', {}), t['materials'], [])
    ctx.textures = TR.load_textures(t['materials'], ST, ctx.files)
    T = np.full((len(zs), len(xs)), np.nan)
    for name, spec in t['fields'].items():
        f = TR.Field(name, spec, ctx)
        pick = min if lowest else max
        top = np.array([[pick(f.corners(ix, jz)) + f.O[jz][ix] for ix in range(f.nx)] for jz in range(f.nz)])
        ix = np.floor(xs / f.s).astype(int) - f.qx0
        jz = np.floor(zs / f.s).astype(int) - f.qz0
        okx, okz = (ix >= 0) & (ix < f.nx), (jz >= 0) & (jz < f.nz)
        sub = top[np.ix_(jz[okz], ix[okx])]
        T[np.ix_(okz, okx)] = sub
    return T


def grid_index(xs, zs, x, z):
    return int(round((z - zs[0]) / STEP)), int(round((x - xs[0]) / STEP))


def analyse(H, T, xs, zs):
    """{edge: rows [(s, frame, reach, (x, F, z, d) of the worst floor, (x, F, z) of the highest
    floor within NEAR + 2 of the edge)]} every STEP of edge."""
    out = {}
    X, Z = np.meshgrid(xs, zs)
    inside = (X >= 0) & (X <= W) & (Z >= 0) & (Z <= D)
    # every edge's strip: the frame, not a floor to start from (a corner's rims are the other edge's)
    frame_all = (Z < EDGES['S'][0]) | (D - Z < EDGES['N'][0]) | (X < EDGES['W'][0]) | (W - X < EDGES['E'][0])
    # the floors pooled: the highest in each POOL square that is not frame, at the square's middle
    k = int(POOL / STEP)
    Hc = np.where(inside & ~frame_all & ~np.isnan(H), H, -np.inf)
    nz, nx = Hc.shape[0] // k, Hc.shape[1] // k
    PH = Hc[:nz * k, :nx * k].reshape(nz, k, nx, k).max(axis=(1, 3))
    PX = X[:nz * k, :nx * k].reshape(nz, k, nx, k).mean(axis=(1, 3))
    PZ = Z[:nz * k, :nx * k].reshape(nz, k, nx, k).mean(axis=(1, 3))
    pool_ok = np.isfinite(PH)

    def pool_dep(name):
        return {'S': PZ, 'N': D - PZ, 'W': PX, 'E': W - PX}[name]
    for name, (strip, at, length) in EDGES.items():
        ss = np.arange(0, length, STEP) + STEP / 2
        # depth inside the edge of every grid point, and its position along the edge
        if name == 'S':
            dep, alo = Z, X
        elif name == 'N':
            dep, alo = D - Z, X
        elif name == 'W':
            dep, alo = X, Z
        else:
            dep, alo = W - X, Z
        Hn = np.where(np.isnan(H), -1e9, H)
        Bn = np.fmax(Hn, np.where(np.isnan(T), -1e9, T))       # what stands: floors and the terrain's top
        in_strip = (dep < strip) & (dep > -OUTSIDE)
        cand = inside & ~frame_all & ~np.isnan(H)
        # the frame's column height at each along position: the highest floor across the strip
        col = np.full(len(ss), -1e9)
        for k, s in enumerate(ss):
            m = in_strip & (np.abs(alo - s) < STEP / 2 + 1e-6)
            if m.any():
                col[k] = Bn[m].max()
        frame = np.array([col[max(0, k - int(WINDOW / STEP)):k + int(WINDOW / STEP) + 1].min()
                          for k in range(len(ss))])
        # floors near the edge at the grid's step, farther ones by POOL (the highest in each square)
        fine = cand & (dep < FINE)
        cx, cz, cf = X[fine], Z[fine], H[fine]
        pm = pool_ok & (pool_dep(name) >= FINE)
        cx = np.concatenate([cx, PX[pm]])
        cz = np.concatenate([cz, PZ[pm]])
        cf = np.concatenate([cf, PH[pm]])

        def reach_at(px, pz, pf, s):
            ex, ez = at(s, 0.0)
            d = np.hypot(px - ex, pz - ez)
            r = pf + REACH - np.maximum(0.0, d - NEAR) / RATIO
            return r, d

        def pass_(px, pz, pf, extra=None):
            rows = []
            for k, s in enumerate(ss):
                ex, ez = at(s, 0.0)
                near = slice(None)
                r, d = reach_at(px, pz, pf, s)
                best = -1e9
                worst = None
                if r.size:
                    q = int(np.argmax(r))
                    best = float(r[q])
                    worst = (float(px[near][q]), float(pf[near][q]), float(pz[near][q]), float(d[q]))
                if extra is not None:
                    xx, xz, xf = extra
                    sel = np.abs(np.array([alo_of(name, a, b) for a, b in zip(xx, xz)]) - s) > WINDOW + STEP if len(xx) else np.array([], bool)
                    if sel.any():
                        r2, d2 = reach_at(xx[sel], xz[sel], xf[sel], s)
                        q = int(np.argmax(r2))
                        if r2[q] > best:
                            best = float(r2[q])
                            worst = (float(xx[sel][q]), float(xf[sel][q]), float(xz[sel][q]), float(d2[q]))
                rows.append((best, worst))
            return rows

        rows = pass_(cx, cz, cf)
        direct = [r for r, _ in rows]
        # strip floors a body reaches become floors to start from (for the rest of the edge)
        reach = np.array([r for r, _ in rows])
        sm = in_strip & ~np.isnan(H) & inside
        sx, sz, sf, sa = X[sm], Z[sm], H[sm], alo[sm]
        idx = np.clip(np.round((sa - ss[0]) / STEP).astype(int), 0, len(ss) - 1)
        ok = sf <= reach[idx] + 1e-6
        # not a floor under a wall's cap (a rim's top inside a rock wall): nowhere to stand
        ok &= ~(np.nan_to_num(T[sm], nan=-1e9) > sf + 1.0)
        if ok.any():
            rows = pass_(cx, cz, cf, (sx[ok], sz[ok], sf[ok]))
        # the highest floor near the edge, for the walking and backflip probes
        res = []
        for k, s in enumerate(ss):
            ex, ez = at(s, strip)
            m = (np.hypot(cx - ex, cz - ez) < NEAR + 2.0)
            near = None
            if m.any():
                q = int(np.argmax(cf[m]))
                near = (float(cx[m][q]), float(cf[m][q]), float(cz[m][q]))
            res.append((float(s), float(frame[k]), rows[k][0], rows[k][1], near, direct[k]))
        out[name] = res
    return out


# The rock walls' rims (assets/edge_rock): edge, where along it they start and end, and the
# footprint across it (depth inside the edge): the rims' cliffs in make_world.py and the mountain's.
ROCK = 16.0
ROCK_RIMS = {'W': (128.0, 380.0, 2.0), 'E': (154.0, 380.0, 2.0), 'N': (0.0, 320.0, 4.0)}


def print_rocks(result, T, xs, zs):
    """Python rows for assets/edge_rock/make_edge_rock.py's ROCKS: (edge, from, to, foot, top). T:
    the terrain's lowest and highest corners; the top is also 1 m over the rim's highest corner
    (else a sliver of the rim's top stands out at the face's top, a floor by the edge)."""
    T, Tmax = T
    for name, (s0, s1, depth) in ROCK_RIMS.items():
        strip, at, _ = EDGES[name]
        rows = result[name]
        a = s0
        while a < s1 - 1e-6:
            b = min(s1, (math.floor(a / ROCK) + 1) * ROCK)
            seg = [r for r in rows if a <= r[0] < b]
            top = math.ceil((max(r[5] for r in seg) + MARGIN) * 2) / 2
            feet, heads = [], []
            for s in np.arange(a + STEP / 2, b, STEP):
                for d in np.arange(STEP / 2, depth + STEP, STEP):
                    x, z = at(s, d)
                    j, i = int((x - xs[0]) // STEP), int((z - zs[0]) // STEP)
                    if not np.isnan(T[i, j]) and d < depth:
                        feet.append(T[i, j])
                    if not np.isnan(Tmax[i, j]):
                        heads.append(Tmax[i, j])
            top = max(top, math.ceil((max(heads) + 1.0) * 2) / 2)
            foot = math.floor(min(feet)) - 1.0       # the rim's lowest corner under it, less 1 m
            print(f"    ('{name}', {a:g}, {b:g}, {foot:g}, {top:g}),")
            a = b


def alo_of(name, x, z):
    return x if name in 'SN' else z


def leaks(result):
    """The runs of edge where the reach is above the frame: [(edge, s0, s1, frame, reach, worst)]."""
    runs = []
    for name, rows in result.items():
        cur = None
        for s, frame, reach, worst, *_ in rows:
            bad = reach > frame
            if bad and cur and cur[0] == name and s - cur[2] <= STEP + 1e-6:
                cur[2] = s
                if reach - frame > cur[4] - cur[3]:
                    cur[3], cur[4], cur[5] = frame, reach, worst
                continue
            if cur:
                runs.append(tuple(cur))
                cur = None
            if bad:
                cur = [name, s, s, frame, reach, worst]
        if cur:
            runs.append(tuple(cur))
    return runs


def probes(result):
    """Probe points every PROBE_EVERY of edge: (edge, s, edge point, near floor, worst floor)."""
    out = []
    for name, rows in result.items():
        strip, at, length = EDGES[name]
        n = int(length // PROBE_EVERY)
        for k in range(n):
            lo, hi = k * PROBE_EVERY, (k + 1) * PROBE_EVERY
            seg = [r for r in rows if lo <= r[0] < hi and r[3] is not None]
            if not seg:
                continue
            # the point of the segment with the least margin, its worst floor; the highest near floor
            s, frame, reach, worst, *_ = max(seg, key=lambda r: r[2] - r[1])
            nears = [r for r in seg if r[4] is not None]
            near = max(nears, key=lambda r: r[4][1]) if nears else None
            out.append((name, s, at(s, 0.0), near[4] if near else None, near[0] if near else s, worst))
    return out


def write_probes(path, result):
    rows = []
    for name, s, (ex, ez), near, ns, worst in probes(result):
        strip, at, _ = EDGES[name]
        if near is not None:
            nx, ny, nz = near
            tx, tz = at(ns, 0.0)
            h = math.atan2(tx - nx, tz - nz)
            rows.append((name, s, 'walk', nx, ny, nz, h))
            rows.append((name, s, 'flip', nx, ny, nz, h))
        wx, wy, wz, _ = worst
        h = math.atan2(ex - wx, ez - wz)
        rows.append((name, s, 'glide', wx, wy, wz, h))
    mode = {'walk': 0, 'flip': 1, 'glide': 2}
    lines = ['// Generated by carts/garden/shrinetown/tools/frame.py --probes - do not edit.',
             '// The frame case\'s probes (frame_cases.akr): every %g m of each edge, a walk and a backflip' % PROBE_EVERY,
             '// from the highest floor near it and a glide from the floor that reaches highest there.',
             'const FRAME_PROBES: [%d]FrameProbe = [' % len(rows)]
    for name, s, m, x, y, z, h in rows:
        lines.append('    FrameProbe { at: vec3(%.2f, %.2f, %.2f), yaw: %.4f, mode: %d, edge: %d },   // %s %g %s'
                     % (x, y + 0.02, z, h, mode[m], 'SNWE'.index(name), name, s, m))
    lines.append(']')
    Path(path).write_text('\n'.join(lines) + '\n')
    return len(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--build-dir', default='build')
    ap.add_argument('--probes', action='store_true', help='write carts/garden/tests/frame_probes.akr')
    ap.add_argument('--table', action='store_true', help='print every EVERY m of edge, not only the leaks')
    ap.add_argument('--every', type=float, default=4.0)
    ap.add_argument('--rocks', action='store_true', help='print the rock walls the rims need: for every '
                    'ROCK m of a rim north of the town, its foot (the terrain under it less 1 m) and its top (as --tops)')
    ap.add_argument('--tops', action='store_true', help='print, every 8 m of edge, the top the frame needs '
                    '(the reach from the floors inside, not from the frame itself, and MARGIN)')
    a = ap.parse_args()
    H, T, xs, zs = floors(REPO / a.build_dir if not Path(a.build_dir).is_absolute() else a.build_dir)
    T_terrain = (terrain_top(xs, zs, lowest=True), terrain_top(xs, zs)) if a.rocks else None
    result = analyse(H, T, xs, zs)
    if a.table:
        for name, rows in result.items():
            for s, frame, reach, worst, near, direct in rows[::int(a.every / STEP)]:
                w = '(%.1f, %.2f, %.1f) %.1f m off' % worst if worst else '-'
                print(f'{name} {s:6.1f}  frame {frame:7.2f}  reach {reach:7.2f} (direct {direct:7.2f})  '
                      f'margin {frame - reach:+7.2f}  from {w}')
    if a.tops:
        for name, rows in result.items():
            for k in range(0, len(rows), int(8 / STEP)):
                seg = rows[k:k + int(8 / STEP)]
                need = math.ceil((max(r[5] for r in seg) + MARGIN) * 2) / 2
                print(f'TOP {name} {seg[0][0] - STEP / 2:5.0f} {seg[-1][0] + STEP / 2:5.0f}  frame {min(r[1] for r in seg):6.2f}  '
                      f'needs {need:6.1f}')
    if a.rocks:
        print_rocks(result, T_terrain, xs, zs)
    bad = leaks(result)
    for name, s0, s1, frame, reach, worst in bad:
        x, f, z, d = worst
        print(f'LEAK {name} {s0:.1f}-{s1:.1f}: frame {frame:.2f}, reach {reach:.2f} from the floor {f:.2f} '
              f'at ({x:.1f}, {z:.1f}), {d:.1f} m off')
    margins = {name: min(fr - r for _, fr, r, *_ in rows if r > -1e8) for name, rows in result.items()}
    print('least margin by edge: ' + ', '.join(f'{k} {v:+.2f}' for k, v in margins.items()))
    if a.probes:
        n = write_probes(REPO / 'carts/garden/tests/frame_probes.akr', result)
        print(f'frame_probes.akr: {n} probes')
    print(f'{len(bad)} leaking runs of edge' if bad else 'the frame holds')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
