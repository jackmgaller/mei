"""What the reach map finds: the analyses over a finished Explorer (reach.py).

- escapes: flights from a reachable floor that leave the level's frame;
- falls through the world: flights that drop through a column with no floor under it, inside the
  frame (the World Checker's missing "drop" check), and the floorless spots themselves;
- sealed places (the world's explore config): ways in other than the intended ones;
- collectibles (coins, red coins, stars): which can be taken, and by which moves; a card taken in
  mid-air by a glide;
- shortcuts (the config): how fast each shortcut's far side is reached with it shut;
- paths: each walkable sweep (a trail, a bridge, a stair) walked end to end both ways on the walk
  graph alone, and where it stops;
- traps: floors reachable from the spawn from which the spawn cannot be reached again.
"""
import math

import numpy as np

from . import moves as M
from . import sim as S
from .reach import MOVE_NAMES

STATE_NAMES = {M.AIR: 'air', M.GLIDE: 'glide', M.DIVE: 'dive'}


def _r(v, n=2):
    return None if v is None or (isinstance(v, float) and not math.isfinite(v)) else round(float(v), n)


def _pt(p):
    return [_r(p[0]), _r(p[1]), _r(p[2])]


def flight_rows(e, outcome_codes):
    """(set, row, src node, cost to the take-off) for flights with these outcomes whose take-off
    floor is reachable from the spawn."""
    out = []
    for k, (r, src) in enumerate(zip(e.flights.result, e.flights.src)):
        sel = np.isin(r.outcome, outcome_codes)
        idx = np.nonzero(sel)[0]
        if len(idx) == 0:
            continue
        d = e.dist[src[idx]]
        ok = np.isfinite(d)
        for i, dd in zip(idx[ok], d[ok]):
            out.append((k, int(i), int(src[i]), float(dd)))
    return out


def describe_flight(e, k, i):
    """A flight as data: where its chain took off (the root move from a floor, a pole or a rail),
    which way, the wall kicks and the glide's let-go on the way, and how this flight ended."""
    F = e.flights
    b = F.batch[k]
    r = F.result[k]
    # up the chain to its root
    ks, ki = k, i
    chain = [MOVE_NAMES[int(F.move[k][i])]]
    while F.parent[ks] is not None:
        ps, prow = F.parent[ks]
        ki = int(prow[ki])
        ks = ps
        chain.append(MOVE_NAMES[int(F.move[ks][ki])])
    rb = F.batch[ks]
    chain.reverse()
    d = {'move': chain[0], 'chain': chain, 'from': _pt((rb.x[ki], rb.y[ki], rb.z[ki])),
         'heading_deg': _r(math.degrees(rb.yaw[ki] - (math.pi if chain[0] == 'backflip' else 0)) % 360, 1),
         'kicks': int(F.kicks[k][i]), 'release_ticks': int(F.release[k][i]),
         'ticks': int(r.ticks[i]), 'seconds_before': _r(float(F.t0[k][i]), 2), 'max_y': _r(r.max_y[i]),
         'end': _pt((r.x[i], r.y[i], r.z[i])), 'outcome': S.OUTCOME_NAMES[int(r.outcome[i])],
         'last_from': _pt((b.x[i], b.y[i], b.z[i]))}
    return d


def route_text(steps, limit=12):
    parts = []
    for mv, pos in steps[-limit:]:
        if pos is None:
            continue
        parts.append(f'{mv} to ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})')
    pre = '... ' if len(steps) > limit else ''
    return pre + ', then '.join(parts)


def _route(e, node):
    steps = e.route(node)
    return [{'move': mv, 'to': _pt(pos[:3]) if pos else None, 'what': pos[3] if pos else None} for mv, pos in steps]


def _cluster(points, radius):
    """Greedy clusters of 2D points: [(indices)]. Points sorted by caller's priority."""
    left = list(range(len(points)))
    out = []
    pts = np.asarray(points, float).reshape(-1, 2)
    taken = np.zeros(len(pts), bool)
    for i in left:
        if taken[i]:
            continue
        d = np.hypot(pts[:, 0] - pts[i, 0], pts[:, 1] - pts[i, 1])
        members = np.nonzero((d <= radius) & ~taken)[0]
        taken[members] = True
        out.append(members)
    return out


def side_of(frame, x, z):
    x0, z0, x1, z1 = frame
    d = {'west': abs(x - x0), 'east': abs(x - x1), 'south': abs(z - z0), 'north': abs(z - z1)}
    return min(d, key=d.get)


# ---- escapes

def escapes(e, radius=12.0):
    rows = flight_rows(e, [S.OUT])
    if not rows:
        return []
    pts, costs = [], []
    for k, i, src, d in rows:
        r = e.flights.result[k]
        pts.append((r.out_x[i], r.out_z[i]))
        costs.append(d + r.ticks[i] / 60)
    order = np.argsort(costs)
    pts = np.asarray(pts)[order]
    rows = [rows[j] for j in order]
    costs = np.asarray(costs)[order]
    found = []
    for members in _cluster(pts, radius):
        best = members[0]
        k, i, src, d = rows[best]
        r = e.flights.result[k]
        moves = sorted({MOVE_NAMES[int(e.flights.move[kk][ii])] for kk, ii, _, _ in (rows[m] for m in members)})
        x, z = float(r.out_x[i]), float(r.out_z[i])
        found.append({'kind': 'escape', '_node': src, 'side': side_of(e.m.frame, x, z), 'at': [_r(x), _r(z)],
                      'flights': int(len(members)), 'moves': moves, 'cost_s': _r(costs[best], 1),
                      'takeoff': describe_flight(e, k, i), 'route': _route(e, src),
                      'span': [_r(float(pts[members, 0].min())), _r(float(pts[members, 1].min())),
                               _r(float(pts[members, 0].max())), _r(float(pts[members, 1].max()))]})
    found.sort(key=lambda f: f['cost_s'])
    return found


def escape_stretches(found, gap=20.0, confirmed_only=True):
    """The escapes grouped into stretches of the frame's sides: escapes on one side whose exits
    are within `gap` metres of each other along it. Each: the side, the range along it, the
    escapes and the moves."""
    out = []
    for side in ('north', 'east', 'south', 'west'):
        fs = [f for f in found if f['side'] == side and (not confirmed_only or f.get('confirm', {}).get('confirmed'))]
        along = 0 if side in ('north', 'south') else 1
        fs.sort(key=lambda f: f['at'][along])
        cur = None
        for f in fs:
            v = f['at'][along]
            if cur and v - cur['to'] <= gap:
                cur['to'] = v
                cur['escapes'].append(f['id'])
                cur['moves'] |= {f['takeoff']['chain'][0]}
            else:
                cur = {'side': side, 'axis': 'xz'[along], 'from': v, 'to': v, 'escapes': [f['id']],
                       'moves': {f['takeoff']['chain'][0]}}
                out.append(cur)
    for c in out:
        c['moves'] = sorted(c['moves'])
    return out


# ---- falls through the world

def falls(e, radius=4.0):
    rows = flight_rows(e, [S.FELL])
    rows = [r for r in rows if np.isfinite(e.flights.result[r[0]].hole_x[r[1]])]
    if not rows:
        return []
    pts = np.array([(e.flights.result[k].hole_x[i], e.flights.result[k].hole_z[i]) for k, i, _, _ in rows])
    costs = np.array([d for _, _, _, d in rows])
    order = np.argsort(costs)
    pts, rows, costs = pts[order], [rows[j] for j in order], costs[order]
    found = []
    for members in _cluster(pts, radius):
        k, i, src, d = rows[members[0]]
        x, z = float(pts[members[0], 0]), float(pts[members[0], 1])
        found.append({'kind': 'fall_through', 'at': [_r(x), _r(z)], 'flights': int(len(members)),
                      'moves': sorted({MOVE_NAMES[int(e.flights.move[kk][ii])] for kk, ii, _, _ in (rows[m] for m in members)}),
                      'cost_s': _r(costs[members[0]], 1), 'takeoff': describe_flight(e, k, i), 'route': _route(e, src),
                      'what': floorless_what(e, x, z)})
    return found


def floorless_what(e, x, z):
    """What is round a floorless column: the nearest floors' heights and the walls there."""
    m = e.m
    c = int(m.col_of(x, z))
    w = m.walls
    i = np.searchsorted(w.col, c)
    j = np.searchsorted(w.col, c, side='right')
    walls = []
    for k in range(i, min(j, i + 4)):
        walls.append({'feet_from': _r(w.y[k]), 'feet_to': _r(w.extra['hi'][k]), 'normal_y': _r(w.extra['ny'][k], 3)})
    return {'walls': walls}


def floorless_spots(e, min_cells=2):
    """Columns inside the frame with no floor at all, whose neighbours have floors: holes a
    falling body passes through (the "drop" check). Clustered, with the slope's height round."""
    m = e.m
    top = m.top_floor()
    x0, z0, x1, z1 = m.frame
    g = m.grid
    i0, i1 = int(round((x0 - m.ox) / g)), int(round((x1 - m.ox) / g))
    j0, j1 = int(round((z0 - m.oz) / g)), int(round((z1 - m.oz) / g))
    sub = top[j0:j1 + 1, i0:i1 + 1]
    hole = np.isnan(sub)
    if not hole.any():
        return []
    from scipy import ndimage
    lab, n = ndimage.label(hole)
    out = []
    objs = ndimage.find_objects(lab)
    for k, sl in enumerate(objs, 1):
        mask = lab[sl] == k
        cells = int(mask.sum())
        if cells < min_cells:
            continue
        zz, xx = np.nonzero(mask)
        zz = zz + sl[0].start
        xx = xx + sl[1].start
        # touching the frame's edge: the outside, not a hole
        if zz.min() == 0 or xx.min() == 0 or zz.max() == sub.shape[0] - 1 or xx.max() == sub.shape[1] - 1:
            continue
        ring = ndimage.binary_dilation(lab == k, iterations=2) & ~hole
        hs = sub[ring]
        out.append({'kind': 'floorless', 'cells': cells, 'area_m2': _r(cells * g * g, 1),
                    'box': [_r(x0 + xx.min() * g), _r(z0 + zz.min() * g), _r(x0 + xx.max() * g), _r(z0 + zz.max() * g)],
                    'centre': [_r(x0 + xx.mean() * g), _r(z0 + zz.mean() * g)],
                    'heights_round': [_r(np.nanmin(hs)), _r(np.nanmax(hs))] if hs.size else None})
    out.sort(key=lambda f: -f['cells'])
    return out


# ---- collectibles

def collectibles(e):
    """Per coin, red coin and star: taken by which moves, how soon from the spawn."""
    m, tn = e.m, e.tn
    F = m.floors
    H = tn.height
    ways = {k: {} for k in range(len(e.pickups))}

    def add(k, how, cost, extra):
        cur = ways[k].get(how)
        if cur is None or cost < cur['cost_s']:
            ways[k][how] = {'how': how, 'cost_s': _r(cost, 1), **extra}
    # standing or walking: a floor whose body box covers it
    for k, p in enumerate(e.pickups):
        cols = e.flyer._square(p['x'], p['z'], 0.8)
        for c in cols:
            i = np.searchsorted(F.col, c)
            j = np.searchsorted(F.col, c, side='right')
            for f in range(i, j):
                y = F.y[f]
                if abs(p['y'] - (y + H / 2)) < 1.2 and np.isfinite(e.dist[f]):
                    add(k, 'walk', e.dist[f], {'from': _pt((*m.xz_of(c)[:1], y, m.xz_of(c)[1]))})
    # poles: the body held round the axis
    for pk, pole in enumerate(e.poles):
        base, lv = e.pole_nodes[pk]
        hold = tn.attach['POLE_HOLD']
        for k, p in enumerate(e.pickups):
            if math.hypot(p['x'] - pole['x'], p['z'] - pole['z']) > 0.8 + hold:
                continue
            for li, yv in enumerate(lv):
                for ys in np.linspace(yv - 0.5, yv + 0.5, 5):
                    if not (pole['y'] <= ys <= lv[-1]):
                        continue
                    angs = [pole['ang']] if pole['front'] else np.linspace(0, 2 * math.pi, 16, endpoint=False)
                    for a in angs:
                        bx, bz = pole['x'] + math.sin(a) * hold, pole['z'] + math.cos(a) * hold
                        if abs(p['x'] - bx) < 0.8 and abs(p['z'] - bz) < 0.8 and abs(p['y'] - (ys + H / 2)) < 1.2:
                            if np.isfinite(e.dist[base + li]):
                                add(k, 'pole', e.dist[base + li], {'pole': pole['id']})
    # rails: grinding (the feet on the path) and hanging (1.75 below)
    for rk, rail in enumerate(e.rails):
        base, ss, total = e.rail_nodes[rk]
        n = len(ss)
        for k, p in enumerate(e.pickups):
            for s in np.linspace(0, total, max(int(total * 4), 2)):
                (x, y, z), _ = e.rail_point(rk, s)
                if abs(p['x'] - x) >= 0.8 or abs(p['z'] - z) >= 0.8:
                    continue
                i = int(np.clip(np.rint(np.interp(s, ss, np.arange(n))), 0, n - 1))
                for kind, feet, how in ((0, y, 'grind'), (1, y, 'grind'), (2, y - tn.attach['HANG_BELOW'], 'hang')):
                    if abs(p['y'] - (feet + H / 2)) < 1.2 and np.isfinite(e.dist[base + kind * n + i]):
                        add(k, how, e.dist[base + kind * n + i], {'rail': rail['id']})
    # flights: the cheapest of each move and state per pickup, and the cheapest few glides through it
    best = {}
    glides = {k: [] for k in range(len(e.pickups))}
    for fk, (r, src) in enumerate(zip(e.flights.result, e.flights.src)):
        pk = r.pickups
        if len(pk.get('i', [])) == 0:
            continue
        d = e.dist[src[pk['i']]]
        ok = np.isfinite(d)
        for i, ent, tick, st, dd in zip(pk['i'][ok], pk['entity'][ok], pk['tick'][ok], pk['state'][ok], d[ok]):
            mv = MOVE_NAMES[int(e.flights.move[fk][i])]
            state = STATE_NAMES.get(int(st), 'air')
            how = f'{mv} ({state})'
            cost = float(dd + tick / 60)
            key = (int(ent), how)
            if key not in best or cost < best[key][0]:
                best[key] = (cost, fk, int(i), int(src[i]), state)
            if state == 'glide':
                glides[int(ent)].append((cost, fk, int(i), int(src[i])))
    for (ent, how), (cost, fk, i, src, state) in best.items():
        ways[ent][how] = {'how': how, 'cost_s': _r(cost, 1), 'state': state, 'takeoff': describe_flight(e, fk, i),
                          'route': _route(e, src)}
    out = []
    for k, p in enumerate(e.pickups):
        w = sorted(ways[k].values(), key=lambda v: v['cost_s'])
        g = []
        seen = set()
        for cost, fk, i, src in sorted(glides[k]):
            b = e.flights.batch[fk]
            spot = (round(float(b.x[i]) / 3), round(float(b.z[i]) / 3))
            if spot in seen:
                continue
            seen.add(spot)
            g.append({'cost_s': _r(cost, 1), 'takeoff': describe_flight(e, fk, i), '_node': src})
            if len(g) >= 5:
                break
        out.append({'id': p['id'], 'type': p['type'], 'at': _pt((p['x'], p['y'], p['z'])), 'params': p['params'],
                    'reachable': bool(w), 'ways': w, 'glide_take': bool(g), 'glide_flights': g})
    return out


# ---- sealed places

def sealed(e):
    out = []
    src, dst, cost, mid = e.edges
    for spec in e.cfg.get('sealed', []):
        pos = node_positions(e)
        inside = in_sealed(spec, pos)
        sel = ~inside[src] & inside[dst] & np.isfinite(e.dist[src])
        ways = {}
        for u, v, c, mv in zip(src[sel], dst[sel], cost[sel], mid[sel]):
            name = M.WALK if mv < 0 else MOVE_NAMES[mv]
            tot = e.dist[u] + c
            if name not in ways or tot < ways[name]['_cost']:
                fl = e.edge_flight_row(u, v) or e.last_flight(u)
                ways[name] = {'move': name, '_cost': tot, '_node': int(v), 'cost_s': _r(tot, 1), 'from': _pt(pos[u]),
                              'to': _pt(pos[v]),
                              'route': _route(e, int(u)), 'flight': describe_flight(e, *fl) if fl else None}
        for w in ways.values():
            w.pop('_cost', None)
        intended = set(spec.get('ways_in', []))
        reached = bool(np.isfinite(e.dist[inside]).any())
        into = ~inside[src] & inside[dst]
        names = np.array([M.WALK] + MOVE_NAMES)[mid.astype(int) + 1]
        meant = into & np.isin(names, list(intended))
        intended_edges = list(zip(src[meant].tolist(), dst[meant].tolist()))
        entries = {}
        for u, v, nm in zip(src[into].tolist(), dst[into].tolist(), names[into].tolist()):
            entries.setdefault(nm, []).append((u, v))
        out.append({'kind': 'sealed', 'name': spec['name'], 'box': sealed_box(spec), 'watch': sealed_watch(spec),
                    'reached': reached, '_inside': np.nonzero(inside)[0].tolist(), '_intended_edges': intended_edges,
                    '_entries': entries,
                    'intended': sorted(intended), 'ways_in': sorted(ways.values(), key=lambda w: w['cost_s']),
                    'other_ways': sorted([w for n, w in ways.items() if n not in intended], key=lambda w: w['cost_s'])})
    return out


def in_sealed(spec, pos):
    """Which points (n, 3) are inside a sealed place: a cylinder [x, z, radius, y0, y1] or a box
    [x0, y0, z0, x1, y1, z1]."""
    if 'cylinders' in spec:
        out = np.zeros(len(pos), bool)
        for x, z, r, y0, y1 in spec['cylinders']:
            out |= ((pos[:, 0] - x) ** 2 + (pos[:, 2] - z) ** 2 <= r * r) & (pos[:, 1] >= y0) & (pos[:, 1] <= y1)
        return out
    if 'cylinder' in spec:
        x, z, r, y0, y1 = spec['cylinder']
        return ((pos[:, 0] - x) ** 2 + (pos[:, 2] - z) ** 2 <= r * r) & (pos[:, 1] >= y0) & (pos[:, 1] <= y1)
    x0, y0, z0, x1, y1, z1 = spec['box']
    return (pos[:, 0] >= x0) & (pos[:, 0] <= x1) & (pos[:, 1] >= y0) & (pos[:, 1] <= y1) & \
           (pos[:, 2] >= z0) & (pos[:, 2] <= z1)


def sealed_watch(spec):
    """The box the headless probe watches: the first cylinder's inscribed square, or the box."""
    c = (spec.get('cylinders') or [spec.get('cylinder')])[0]
    if c:
        x, z, r, y0, y1 = c
        h = r / math.sqrt(2)
        return [x - h, y0, z - h, x + h, y1, z + h]
    return list(spec['box'])


def sealed_box(spec):
    if 'cylinders' in spec:
        cs = spec['cylinders']
        return [min(c[0] - c[2] for c in cs), min(c[3] for c in cs), min(c[1] - c[2] for c in cs),
                max(c[0] + c[2] for c in cs), max(c[4] for c in cs), max(c[1] + c[2] for c in cs)]
    if 'cylinder' in spec:
        x, z, r, y0, y1 = spec['cylinder']
        return [x - r, y0, z - r, x + r, y1, z + r]
    return list(spec['box'])


_POS = {}


def node_positions(e):
    """(n_nodes, 3) positions of every node (floors from the grid; poles and rails sampled)."""
    key = id(e)
    if key in _POS:
        return _POS[key]
    pos = np.zeros((e.n_nodes, 3))
    F = e.m.floors
    x, z = e.m.xz_of(F.col)
    pos[:e.n_floor, 0], pos[:e.n_floor, 1], pos[:e.n_floor, 2] = x, F.y, z
    for k, (base, lv) in enumerate(e.pole_nodes):
        p = e.poles[k]
        pos[base:base + len(lv)] = np.stack([np.full(len(lv), p['x']), lv, np.full(len(lv), p['z'])], 1)
    for k, (base, ss, _) in enumerate(e.rail_nodes):
        n = len(ss)
        for i, s in enumerate(ss):
            (x, y, z), _ = e.rail_point(k, s)
            pos[base + i] = pos[base + n + i] = (x, y, z)
            pos[base + 2 * n + i] = (x, y - 1.75, z)
    _POS[key] = pos
    return pos


# ---- shortcuts

def shortcuts(e):
    out = []
    trig = {t.id: t for t in e.ents if t.type == 'trigger'}
    pos = node_positions(e)
    for spec in e.cfg.get('shortcuts', []):
        t = trig.get(spec['trigger'])
        if t is None:
            continue
        near = spec['near']
        c = e.m.col_of(near[0], near[2])
        f = int(e.m.floor_below(np.array([c]), np.array([near[1] + 0.5]))[0])
        if f < 0:
            out.append({'kind': 'shortcut', 'name': spec['name'], 'error': 'no floor at its near end'})
            continue
        d, p = e.dist_from(f)
        sx, sy, sz = (float(t.params.get('size', [1, 2, 1])[k]) for k in range(3))
        tx, ty, tz = t.pos
        box = (np.abs(pos[:, 0] - tx) <= sx / 2) & (np.abs(pos[:, 2] - tz) <= sz / 2) & \
              (pos[:, 1] >= ty - 0.5) & (pos[:, 1] <= ty + sy)
        idx = np.nonzero(box)[0]
        if len(idx) == 0:
            out.append({'kind': 'shortcut', 'name': spec['name'], 'error': 'no floor in its trigger box'})
            continue
        best = idx[np.argmin(d[idx])]
        straight = math.dist(near, (tx, ty, tz))
        cost = float(d[best])
        steps = e.route(int(best), pred=p) if np.isfinite(cost) else []
        # how far the route strays from the line between the shortcut's two ends: a route that
        # stays near it gets past the shut shortcut where it stands; one that strays is the long way
        off = 0.0
        ax, az, bx, bz = near[0], near[2], tx, tz
        L2 = max((bx - ax) ** 2 + (bz - az) ** 2, 1e-9)
        for mv, q in steps:
            if not q:
                continue
            u = min(max(((q[0] - ax) * (bx - ax) + (q[2] - az) * (bz - az)) / L2, 0.0), 1.0)
            off = max(off, math.hypot(q[0] - (ax + (bx - ax) * u), q[2] - (az + (bz - az) * u)))
        local = spec.get('local_m', 12.0)
        out.append({'kind': 'shortcut', 'name': spec['name'], 'trigger': spec['trigger'], 'near': near,
                    'far': _pt(t.pos), 'straight_m': _r(straight, 1), 'shut_cost_s': _r(cost, 1),
                    'route_strays_m': _r(off, 1), 'local_m': local,
                    'bypassed': bool(np.isfinite(cost) and off <= local),
                    '_end': int(best) if np.isfinite(cost) else None, '_pred': p, '_start': f,
                    '_targets': [int(i) for i in idx],
                    'route': [{'move': mv, 'to': _pt(q[:3]) if q else None} for mv, q in steps]})
    return out


# ---- paths

def walkable_paths(e):
    """The world's sweeps a body walks on: collision on, not water, at least 1 m wide."""
    out = []
    for name, p in e.recipe_json.get('paths', {}).items():
        sw = p.get('sweep')
        if not sw or sw.get('collision') is False:
            continue
        mats = sw.get('materials') or [sw.get('material')]
        if any(m and 'water' in m for m in mats):
            continue
        prof = sw.get('profile', [])
        xs = [q[0] for q in prof]
        if not xs or max(xs) - min(xs) < 1.0:
            continue
        out.append(name)
    return out


def path_walks(e):
    """Each walkable sweep walked end to end, both ways, on the walk graph alone, within its
    corridor: where each direction stops."""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import breadth_first_order
    from .world import path_points
    m = e.m
    F = m.floors
    ws, wd, _ = e.walk
    W = csr_matrix((np.ones(len(ws), np.int8), (ws.astype(np.int64), wd.astype(np.int64))), shape=(e.n_floor, e.n_floor))
    out = []
    for name in walkable_paths(e):
        got = path_points(e.world, name)
        if not got:
            continue
        pts, _ = got
        prof = e.recipe_json['paths'][name]['sweep']['profile']
        half = max(abs(q[0]) for q in prof)
        # samples along the path every half metre
        samples = []
        acc = 0.0
        for a, b in zip(pts[:-1], pts[1:]):
            ln = math.dist(a, b)
            k = max(int(ln / 0.5), 1)
            for j in range(k):
                u = j / k
                samples.append((acc + ln * u, [a[i] + (b[i] - a[i]) * u for i in range(3)]))
            acc += ln
        samples.append((acc, list(pts[-1])))
        # a metre and a half beyond each end, along the end segments: the floor a walker comes from
        def beyond(p0, p1, dist):
            d = [p1[i] - p0[i] for i in range(3)]
            ln = math.hypot(d[0], d[2]) or 1.0
            return [p1[0] + d[0] / ln * dist, p1[1], p1[2] + d[2] / ln * dist]
        samples.insert(0, (-1.5, beyond(pts[1], pts[0], 1.5)))
        samples.append((acc + 1.5, beyond(pts[-2], pts[-1], 1.5)))
        # the corridor's floors: within half the width (and a margin) of the line, near its height
        xs = [q[1][0] for q in samples]
        zs = [q[1][2] for q in samples]
        x0, x1, z0, z1 = min(xs) - half - 1, max(xs) + half + 1, min(zs) - half - 1, max(zs) + half + 1
        g = m.grid
        ia, ib = int((x0 - m.ox) / g), int((x1 - m.ox) / g) + 1
        ja, jb = int((z0 - m.oz) / g), int((z1 - m.oz) / g) + 1
        cols = (np.arange(ja, jb)[:, None] * m.nx + np.arange(ia, ib)[None, :]).ravel()
        lo = np.searchsorted(F.col, cols)
        hi = np.searchsorted(F.col, cols, side='right')
        cand = np.concatenate([np.arange(a, b) for a, b in zip(lo, hi)]) if len(cols) else np.zeros(0, int)
        if len(cand) == 0:
            continue
        cx, cz = m.xz_of(F.col[cand])
        sp = np.array([q[1] for q in samples])
        # distance to the polyline (by samples) and the height there
        d2 = (cx[:, None] - sp[None, :, 0]) ** 2 + (cz[:, None] - sp[None, :, 2]) ** 2
        near = np.argmin(d2, axis=1)
        dd = np.sqrt(d2[np.arange(len(cand)), near])
        keep = (dd <= half + 0.6) & (np.abs(F.y[cand] - sp[near, 1]) <= 2.0)
        sub = cand[keep]
        if len(sub) == 0:
            continue
        Ws = W[sub][:, sub]
        sx, sz = cx[keep], cz[keep]
        sy = F.y[sub]
        # each sample's floors: the corridor's floors within 0.75 m of it, near its height
        sets = []
        for q in samples:
            d = (sx - q[1][0]) ** 2 + (sz - q[1][2]) ** 2
            sets.append(np.nonzero((d <= 0.75 ** 2) & (np.abs(sy - q[1][1]) <= 1.5))[0])
        valid = [k for k, st in enumerate(sets) if len(st)]
        if len(valid) < 2:
            continue

        def walk(order):
            from scipy.sparse.csgraph import dijkstra
            dist = dijkstra(Ws, directed=True, indices=sets[order[0]], min_only=True, unweighted=True)
            seen = np.isfinite(dist)
            last = order[0]
            for si in order:
                if seen[sets[si]].any():
                    last = si
                else:
                    break
            return last
        fwd = walk(valid)
        back = walk(valid[::-1])
        total = samples[-2][0]
        rec = {'kind': 'path', 'path': name, 'length_m': _r(total, 1),
               'forward_to_m': _r(samples[fwd][0], 1), 'backward_to_m': _r(samples[back][0], 1),
               'forward_ok': bool(fwd == valid[-1]), 'backward_ok': bool(back == valid[0])}
        for side, at, nxt in (('forward', fwd, min(fwd + 2, len(samples) - 1)), ('backward', back, max(back - 2, 0))):
            if rec[f'{side}_ok']:
                continue
            ys = sy[sets[at]] if len(sets[at]) else [samples[at][1][1]]
            ya = float(min(ys, key=lambda y: abs(y - samples[at][1][1])))
            why = stop_reason(e, samples[at][1], samples[nxt][1], ya)
            past_end = (side == 'forward' and nxt >= len(samples) - 1) or (side == 'backward' and nxt <= 0)
            if past_end and why.get('why') != 'lip':
                rec[f'{side}_ok'] = True          # the sweep's end meets a wall or a drop: by design
                continue
            rec[f'{side}_stop'] = _pt(samples[at][1])
            rec[f'{side}_why'] = why
        out.append(rec)
    return out


def stop_reason(e, a, b, ya=None):
    """Why a walk from a (its floor at ya) toward b stops: a wall (and what it belongs to), a lip
    (a rise over a step), a steep floor, no floor."""
    from worldkit.quick import tag_name
    m = e.m
    F = m.floors
    if ya is None:
        ca = int(m.col_of(a[0], a[2]))
        fa = int(m.floor_below(np.array([ca]), np.array([a[1] + 0.5]))[0])
        ya = F.y[fa] if fa >= 0 else a[1]
    for u in np.linspace(0.1, 1.0, 10):
        p = [a[i] + (b[i] - a[i]) * u for i in range(3)]
        c = int(m.col_of(p[0], p[2]))
        w = int(m.wall_at(np.array([c]), np.array([ya]))[0])
        if w >= 0:
            tag = int(m.walls.extra['tag'][w])
            cell = (int(p[0] // e.m.cell_size), int(p[2] // e.m.cell_size))
            what = tag_name(e.world, cell, tag, (p[0], p[2]))
            # a low face with a floor on top just beyond: a lip (a riser too high to step)
            q = [a[i] + (b[i] - a[i]) * min(u + 0.15, 1.0) for i in range(3)]
            cq = int(m.col_of(q[0], q[2]))
            fq = int(m.floor_below(np.array([cq]), np.array([ya + 1.2]))[0])
            rise = float(F.y[fq] - ya) if fq >= 0 else None
            out = {'why': 'lip' if rise is not None and e.tn.step < rise <= 1.2 else 'wall', 'at': _pt(p),
                   'what': what.get('id'), 'asset': what.get('asset'), 'wall_normal_y': _r(m.walls.extra['ny'][w], 3)}
            if out['why'] == 'lip':
                out['rise'] = _r(rise)
            return out
        hi_ = int(m.floor_below(np.array([c]), np.array([ya + 1.2]))[0])
        if hi_ >= 0 and F.y[hi_] > ya + e.tn.step:
            return {'why': 'lip', 'at': _pt(p), 'rise': _r(F.y[hi_] - ya)}
        f = int(m.floor_below(np.array([c]), np.array([ya + e.tn.step]))[0])
        if f < 0:
            hi = int(m.floor_below(np.array([c]), np.array([ya + 10]))[0])
            if hi >= 0:
                return {'why': 'step up', 'at': _pt(p), 'rise': _r(F.y[hi] - ya)}
            return {'why': 'no floor', 'at': _pt(p)}
        if F.extra['ny'][f] < e.tn.slide_ny:
            return {'why': 'steep', 'at': _pt(p), 'degrees': _r(math.degrees(math.acos(min(1, F.extra['ny'][f]))), 1)}
        ya = F.y[f]
    return {'why': 'unknown', 'at': _pt(b)}


# ---- traps

def traps(e, min_area=2.0):
    """Floors reachable from the spawn from which it cannot be reached back (without a respawn),
    as connected pieces of the grid: each with its area, its floors' heights and a floor in it."""
    from scipy import ndimage
    from scipy.sparse.csgraph import dijkstra
    back = dijkstra(e.G.T.tocsr(), directed=True, indices=e.start, return_predecessors=False)
    fwd = np.isfinite(e.dist[:e.n_floor])
    stuck = np.nonzero(fwd & ~np.isfinite(back[:e.n_floor]))[0]
    if len(stuck) == 0:
        return []
    m = e.m
    F = m.floors
    grid = np.zeros(m.nx * m.nz, bool)
    grid[F.col[stuck]] = True
    lab, n = ndimage.label(grid.reshape(m.nz, m.nx), structure=np.ones((3, 3)))
    lab = lab.ravel()
    out = []
    comp = lab[F.col[stuck]]
    for k in range(1, n + 1):
        members = stuck[comp == k]
        cols = np.unique(F.col[members])
        area = len(cols) * m.grid * m.grid
        if area < min_area:
            continue
        x, z = m.xz_of(F.col[members])
        cx, cz = x.mean(), z.mean()
        i = members[np.argmin((x - cx) ** 2 + (z - cz) ** 2)]
        out.append({'kind': 'trap', 'at': _pt(node_positions(e)[i]), 'area_m2': _r(area, 1),
                    'box': [_r(x.min()), _r(z.min()), _r(x.max()), _r(z.max())],
                    'heights': [_r(F.y[members].min()), _r(F.y[members].max())],
                    'cost_s': _r(e.dist[i], 1), 'route': _route(e, int(i)), '_cols': cols, '_ys': F.y[members]})
    out.sort(key=lambda f: -f['area_m2'])
    return out


def in_trap(e, t, p):
    """Whether point p (x, y, z) stands in trap t: on one of its columns (or next to one), within
    a metre of its floors' heights."""
    m = e.m
    c = int(m.col_of(p[0], p[2]))
    if c < 0:
        return False
    near = [c + dz * m.nx + dx for dx in (-1, 0, 1) for dz in (-1, 0, 1)]
    if not np.isin(near, t['_cols']).any():
        return False
    return bool(t['heights'][0] - 1.0 <= p[1] <= t['heights'][1] + 1.0)


# ---- the drop check's points

def drop_points(e, spacing=1.0, near=4.0, limit=3000):
    """Points over floorless columns inside the frame, within `near` metres of a reachable floor:
    where a body can come down onto a face steeper than a floor. Each: (x, drop height, z), the
    height 3 m over the highest floor round it. Thinned to `limit` (a wider spacing)."""
    from scipy import ndimage
    m = e.m
    top, _ = _grids(e)
    reach = _reach_top(e)
    g = m.grid
    x0, z0, x1, z1 = m.frame
    inside = np.zeros_like(top, bool)
    i0, i1 = int(round((x0 - m.ox) / g)), int(round((x1 - m.ox) / g))
    j0, j1 = int(round((z0 - m.oz) / g)), int(round((z1 - m.oz) / g))
    inside[j0 + 1:j1, i0 + 1:i1] = True
    hole = np.isnan(top) & inside
    k = int(round(near / g))
    near_reach = ndimage.binary_dilation(np.isfinite(reach), iterations=k)
    cand = hole & near_reach
    round_top = ndimage.maximum_filter(np.nan_to_num(top, nan=-1e9), size=int(round(2.0 / g)) * 2 + 1)
    while True:
        st = max(int(round(spacing / g)), 1)
        jj, ii = np.nonzero(cand)
        keep = (jj % st == 0) & (ii % st == 0)
        jj, ii = jj[keep], ii[keep]
        if len(jj) <= limit:
            break
        spacing *= 1.25
    xs = m.ox + ii * g
    zs = m.oz + jj * g
    ys = round_top[jj, ii] + 3.0
    ok = ys > -1e8
    return [(float(x), float(y), float(z)) for x, y, z in zip(xs[ok], ys[ok], zs[ok])], spacing


def _grids(e):
    m = e.m
    return m.top_floor(), None


def _reach_top(e):
    m = e.m
    F = m.floors
    out = np.full(m.nx * m.nz, np.nan)
    ok = np.isfinite(e.dist[:e.n_floor])
    out[F.col[ok]] = F.y[ok]
    return out.reshape(m.nz, m.nx)


def drop_clusters(e, drops, radius=4.0):
    """The drops that fell through the world, in clusters, each with the nearest reachable floor
    (and its route from the spawn) and the nearest walkable path."""
    hit = [d for d in drops if d.get('confirmed')]
    if not hit:
        return []
    pts = np.array([(d['at'][0], d['at'][2]) for d in hit])
    m = e.m
    F = m.floors
    ok = np.nonzero(np.isfinite(e.dist[:e.n_floor]))[0]
    fx, fz = m.xz_of(F.col[ok])
    out = []
    for members in _cluster(pts, radius):
        cx, cz = pts[members].mean(axis=0)
        d2 = (fx - cx) ** 2 + (fz - cz) ** 2
        j = int(np.argmin(d2))
        node = int(ok[j])
        out.append({'kind': 'drop_through', 'at': [_r(cx), _r(cz)], 'drops': int(len(members)),
                    'points': [hit[i]['at'] for i in members[:6]],
                    'nearest_reachable_floor': _pt((fx[j], F.y[node], fz[j])),
                    'nearest_m': _r(math.sqrt(d2[j]), 1), 'route': _route(e, node)})
    out.sort(key=lambda c: -c['drops'])
    return out


def all_finds(e, log=print):
    import time
    res = {}
    for name, fn in (('escapes', escapes), ('falls', falls), ('floorless', floorless_spots),
                     ('collectibles', collectibles), ('sealed', sealed), ('shortcuts', shortcuts),
                     ('paths', path_walks), ('traps', traps)):
        t = time.perf_counter()
        res[name] = fn(e)
        log(f'  {name}: {len(res[name])} ({time.perf_counter() - t:.1f} s)')
    return res
