"""The reach map: every floor the robot can stand on, and how it gets from one to another.

Nodes are the column grid's floor entries (world.py), plus a node per metre of each pole and
each rail (one per direction for a grind, one for a hang). Edges:

- walking: to the next column's floor within a step up or down (T values: the probe's step), when
  no wall pushes the body there; not uphill off a floor steeper than the slide angle;
- dropping: off an edge, straight down onto the next column's highest floor below;
- flights (sim.py): each move of moves.py from every floor at a boundary (a wall, a drop, a rise
  ahead within half a metre), toward it, on a half-metre lattice: landings, ledge grabs, poles
  and rails caught, and the later passes from those: wall kicks off the walls met, letting go of
  a glide, jumps and drops off poles, grinds to a rail's end, jumps and drops off rails and hangs.

The costs are seconds (run time, flight time and a little for the setup of each move), so the
cheapest route from the spawn is a plausible one, and a route can be printed move by move.
"""
from dataclasses import dataclass, field
import math
import multiprocessing as mp
import os
import time

import numpy as np

from . import moves as M
from . import sim as S
from .world import KEY, WorldModel, entities, path_points, load_world

DIRS8 = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
SETUP = {'walk_off': 0.0, 'hop': 0.1, 'jump': 0.4, 'double': 1.0, 'double_stand': 0.8, 'third': 1.6,
         'double_glide': 1.0, 'third_glide': 1.6, 'long': 0.6, 'backflip': 0.3, 'side_flip': 0.8,
         'jump_dive': 0.4, 'double_dive': 1.0}


@dataclass
class Options:
    lattice: int = 2            # launch from every n-th column (0.25 m each): 2 = half a metre
    probe: int = 2              # look this many columns ahead for a boundary
    headings_extra: bool = False  # also 22.5 degrees either side of each boundary direction
    kick_depth: int = 2         # wall kicks chained after a flight
    release_every: int = 30     # ticks between the glide's let-go points
    processes: int = 0          # 0: the machine's cores
    max_ticks: int = 2400
    moves: tuple = ()           # () all
    deep: bool = False


@dataclass
class Flights:
    """Every flight flown: the batch, its result, and where each came from."""
    src: list = field(default_factory=list)         # node arrays
    move: list = field(default_factory=list)        # move-name index arrays
    batch: list = field(default_factory=list)
    result: list = field(default_factory=list)
    parent: list = field(default_factory=list)      # (flight set, row) of the flight it came out of, or -1
    t0: list = field(default_factory=list)          # seconds spent before this flight (the parents' setup and flight)
    root: list = field(default_factory=list)        # the first move of the chain (move id)
    kicks: list = field(default_factory=list)       # wall kicks in the chain so far (this flight's included)
    release: list = field(default_factory=list)     # glide ticks before letting go in the chain (0: none)


MOVE_NAMES = [m.name for m in M.MOVES] + [M.KICK, M.RELEASE, M.POLE_JUMP, M.POLE_DROP, M.GRIND_END, M.GRIND_JUMP,
                                           M.HANG_JUMP, M.HANG_DROP, M.POLE, M.GRIND, M.HANG]
MOVE_ID = {n: k for k, n in enumerate(MOVE_NAMES)}

_FLYER = None


def _fly_chunk(args):
    b, rel = args
    return _FLYER.fly(b, release_every=rel)


class Pool:
    """Worker processes forked once, with the world's arrays (copy on write), for every batch of
    flights; a batch that does not come back in time is flown here instead."""

    def __init__(self, flyer, processes):
        global _FLYER
        _FLYER = flyer
        self.flyer = flyer
        self.procs = processes or os.cpu_count() or 1
        self.pool = None
        if self.procs > 1:
            import sys
            sys.stdout.flush()
            sys.stderr.flush()
            try:
                self.pool = mp.get_context('fork').Pool(self.procs)
            except (OSError, ValueError, RuntimeError):
                self.pool = None

    def fly(self, batch, release_every):
        n = len(batch)
        if self.pool is None or n < 4000:
            return self.flyer.fly(batch, release_every=release_every)
        k = self.procs * 6
        # shuffled, so that long flights (glides) spread over the workers
        perm = np.random.default_rng(0).permutation(n)
        edges = np.linspace(0, n, k + 1).astype(int)
        parts = [batch.take(perm[a:b]) for a, b in zip(edges[:-1], edges[1:]) if b > a]
        try:
            res = self.pool.map_async(_fly_chunk, [(p, release_every) for p in parts]).get(timeout=1800)
        except Exception:                   # a worker lost or stuck: fly it here
            self.close()
            res = [self.flyer.fly(p, release_every=release_every) for p in parts]
        return unshuffle(merge_results(res, [len(p) for p in parts]), perm)

    def close(self):
        if self.pool is not None:
            self.pool.terminate()
            self.pool = None


def unshuffle(r, perm):
    """A result flown in the order perm, put back in the batch's order."""
    for f in ('outcome', 'x', 'y', 'z', 'ticks', 'floor', 'rail_s', 'rail_v', 'max_y', 'hole_x', 'hole_z',
              'out_x', 'out_z', 'out_y', 'glided'):
        v = getattr(r, f)
        out = np.empty_like(v)
        out[perm] = v
        setattr(r, f, out)
    for name in ('kicks', 'releases', 'pickups'):
        d = getattr(r, name)
        if 'i' in d and len(d['i']):
            d['i'] = perm[d['i']]
    return r


def merge_results(res, sizes):
    off = np.cumsum([0] + sizes[:-1])
    cat = {}
    for f in ('outcome', 'x', 'y', 'z', 'ticks', 'floor', 'rail_s', 'rail_v', 'max_y', 'hole_x', 'hole_z',
              'out_x', 'out_z', 'out_y', 'glided'):
        cat[f] = np.concatenate([getattr(r, f) for r in res])
    ev = {}
    for name in ('kicks', 'releases', 'pickups'):
        d = {}
        for r, o in zip(res, off):
            for k, v in getattr(r, name).items():
                d.setdefault(k, []).append(v + o if k == 'i' else v)
        ev[name] = {k: np.concatenate(v) for k, v in d.items()}
    return S.Result(**cat, **ev)


class Explorer:
    def __init__(self, recipe, build_dir, tuning, config=None, layers_on=None, opts=None, log=print, world=None):
        self.t0 = time.perf_counter()
        self.log = log
        self.recipe = recipe
        self.tn = tuning
        self.cfg = config or {}
        self.opts = opts or Options()
        self.world = world or load_world(recipe, build_dir)
        self.timing = {'load': round(time.perf_counter() - self.t0, 1)}
        t = time.perf_counter()
        self.m = WorldModel(self.world, tuning, layers_on)
        self.timing['model'] = round(time.perf_counter() - t, 1)
        self.ents, self.recipe_json = entities(self.world, recipe)
        on = self.m.layers_on
        self.live = [e for e in self.ents if e.layer is None or e.layer in on]
        self.surface_map = tuning.surfaces
        self._setup_attachments()

    # ---- entities

    def _setup_attachments(self):
        tn = self.tn
        self.poles = []
        for e in self.live:
            if e.type == 'pole':
                h = float(e.params.get('height', 0))
                self.poles.append({'id': e.id, 'n': e.n, 'x': e.pos[0], 'y': e.pos[1], 'z': e.pos[2], 'top': e.pos[1] + h,
                                   'front': bool(e.params.get('front', False)), 'ang': e.yaw})
        self.rails = []
        for e in self.live:
            if e.type == 'rail':
                got = path_points(self.world, e.params.get('path'))
                if got:
                    pts, closed = got
                    # a hang-only rail (never ground, not caught falling fast) and where it can be
                    # caught (within `catch` of its first point; 0: anywhere): attach.akr's rules
                    self.rails.append({'id': e.id, 'n': e.n, 'path': e.params.get('path'), 'points': pts, 'closed': closed,
                                       'hang': bool(e.params.get('hang', False)),
                                       'catch': float(e.params.get('catch', 0.0) or 0.0)})
        self.pickups = []
        for e in self.ents:
            if e.type in ('coin', 'red_coin', 'star'):
                self.pickups.append({'id': e.id, 'n': e.n, 'type': e.type, 'x': e.pos[0], 'y': e.pos[1], 'z': e.pos[2],
                                     'params': e.params, 'layer': e.layer})
        self.flyer = S.Flyer(self.m, tn, self.poles, self.rails, self.pickups)
        spawn = [e for e in self.ents if e.type == 'spawn']
        self.spawn = spawn[0].pos if spawn else None

    # ---- nodes and walking

    def build_walk(self):
        t = time.perf_counter()
        m, tn = self.m, self.tn
        F = m.floors
        n = len(F)
        self.n_floor = n
        col, y = F.col, F.y
        ny = F.extra['ny']
        surf = np.asarray(self.surface_map, np.int8)[F.extra['surf'] & 7]
        self.steep = (ny < tn.slide_ny) | (surf == 2)
        self.bounce = surf == 1
        self.free = m.wall_at(col, y) < 0
        # a floor with another floor over it inside the body's height and no ceiling between (a
        # placement's top under the terrain: the falls cliff's 48.3 under the hill at z 345) is
        # not stood on: the controller steps up onto the higher one. The walk graph walked under
        # the hill there and the confirmer, put on the buried floor, fell through the world.
        # (the ground over it only: a platform under a roof's open-bottom collision is stood on)
        from worldkit.terrain import TAG_FIELD
        j = np.searchsorted(F.key, col * KEY + y + tn.step, side='right')
        jj = np.minimum(j, n - 1)
        over = (j < n) & (F.col[jj] == col) & (F.y[jj] < y + tn.height) & (F.extra['tag'][jj] == TAG_FIELD)
        if over.any():
            ce = m.ceiling_above(col, y)
            cy = m.ceilings.y[np.maximum(ce, 0)] if len(m.ceilings) else np.zeros(n)
            over &= (ce < 0) | (cy > F.y[jj])
        self.buried = over
        self.free &= ~over
        step = tn.step
        down = 0.33
        src, dst, cost = [], [], []
        ix = col % m.nx
        iz = col // m.nx
        run = tn.t['RunSpeed']
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            okx = (ix + dx >= 0) & (ix + dx < m.nx) & (iz + dz >= 0) & (iz + dz < m.nz)
            c2 = np.where(okx, col + dz * m.nx + dx, -1)
            tgt = m.floor_below(c2, y + step)
            ty = np.where(tgt >= 0, F.y[np.maximum(tgt, 0)], -1e9)
            # the walls in the next column at the feet's height there: up a step, the height of the
            # step's top (the controller steps up in the tick it moves, and the push of the riser
            # beyond, within the radius at the old height, only slows it: stairs whose treads are
            # shallower than the radius are walked, scenario 715)
            up = (tgt >= 0) & (ty > y)
            moveok = self.free & (m.wall_at(c2, np.where(up, ty, y)) < 0) & (tgt >= 0)
            walk = moveok & (ty >= y - down) & ~(self.steep & (ty > y - 0.005))
            drop = moveok & (ty < y - down) & (m.wall_at(c2, y) < 0)
            # a drop lands on the highest floor below in the next column: keep it if the body is
            # free there
            sel = (walk | (drop & (m.wall_at(c2, ty) < 0))) & ~self.buried[np.maximum(tgt, 0)]
            s = np.nonzero(sel)[0]
            src.append(s.astype(np.int32))
            dst.append(tgt[s].astype(np.int32))
            dist = m.grid
            fall = np.where(drop[s], np.sqrt(2 * np.maximum(y[s] - ty[s], 0) / tn.t['Gravity']), 0.0)
            cost.append((dist / run + fall).astype(np.float32))
        self.walk = (np.concatenate(src), np.concatenate(dst), np.concatenate(cost))
        self.timing['walk'] = round(time.perf_counter() - t, 1)
        self.log(f'  walk graph: {n:,} floor entries, {len(self.walk[0]):,} steps ({self.timing["walk"]} s)')

    # ---- launches from boundaries

    def boundary_launches(self):
        t = time.perf_counter()
        m, tn, o = self.m, self.tn, self.opts
        F = m.floors
        col, y = F.col, F.y
        ix = col % m.nx
        iz = col // m.nx
        lat = (ix % o.lattice == 0) & (iz % o.lattice == 0) & self.free
        cand = np.nonzero(lat)[0]
        heads = []
        for k, (dx, dz) in enumerate(DIRS8):
            c = cand
            ok = (ix[c] + dx * o.probe >= 0) & (ix[c] + dx * o.probe < m.nx) & (iz[c] + dz * o.probe >= 0) & \
                 (iz[c] + dz * o.probe < m.nz)
            c2 = np.where(ok, col[c] + (dz * m.nx + dx) * o.probe, -1)
            tgt = m.floor_below(c2, y[c] + tn.step)
            ty = np.where(tgt >= 0, F.y[np.maximum(tgt, 0)], -1e9)
            walk = (tgt >= 0) & (ty >= y[c] - 0.33) & (m.wall_at(c2, np.maximum(ty, y[c])) < 0)
            # also a rise within reach that walking cannot take
            hi = m.floor_below(c2, y[c] + 8.0)
            rise = (hi >= 0) & (F.y[np.maximum(hi, 0)] > y[c] + tn.step)
            b = ~walk | rise
            heads.append(b)
        heads = np.stack(heads, axis=1)            # (cand, 8)
        has = heads.any(axis=1)
        nodes = cand[has]
        hmask = heads[has]
        self.timing['boundary'] = round(time.perf_counter() - t, 1)
        self.log(f'  launch floors: {len(nodes):,} of {len(cand):,} lattice floors at a boundary, '
                 f'{int(hmask.sum()):,} headings')
        return nodes, hmask

    def first_pass(self):
        o = self.opts
        nodes, hmask = self.boundary_launches()
        src, hd = np.nonzero(hmask)
        src = nodes[src]
        yaw0 = np.array([math.atan2(dx, dz) for dx, dz in DIRS8])[hd]
        if o.headings_extra:
            src = np.concatenate([src, src, src])
            yaw0 = np.concatenate([yaw0, yaw0 + math.pi / 8, yaw0 - math.pi / 8])
        F = self.m.floors
        x, z = self.m.xz_of(F.col[src])
        y = F.y[src]
        moves = [mv for mv in M.MOVES if not o.moves or mv.name in o.moves]
        parts, srcs, mids = [], [], []
        for mv in moves:
            vy, fwd, ctrl, cap, gl = M.launch_state(mv, self.tn)
            sel = np.arange(len(src))
            if mv.name == 'walk_off':
                # only toward a drop: the column ahead has no floor within a step down
                c2 = self.m.col_of(x + np.sin(yaw0) * 0.5, z + np.cos(yaw0) * 0.5)
                tg = self.m.floor_below(c2, y + self.tn.step)
                ty = np.where(tg >= 0, F.y[np.maximum(tg, 0)], -1e9)
                sel = np.nonzero(ty < y - 0.33)[0]
            if self.steep is not None and mv.run:
                pass
            k = len(sel)
            yaw = yaw0[sel] + (math.pi if mv.backwards else 0.0)
            b = S.Batch(x[sel].astype(float), y[sel].astype(float), z[sel].astype(float), yaw, np.full(k, vy),
                        np.full(k, fwd), np.full(k, ctrl), np.full(k, cap), np.full(k, float(mv.stick)),
                        np.full(k, mv.st, np.int8), np.full(k, bool(gl and M.can_glide_from(mv, self.tn))),
                        np.full(k, mv.dive_at_apex), max_ticks=o.max_ticks)
            parts.append(b)
            srcs.append(src[sel])
            mids.append(np.full(k, MOVE_ID[mv.name], np.int16))
        # glides aimed: a player aims a glide at what it wants, so from every floor of a coarser
        # lattice (2 m) high enough over a star or a red coin to glide to it, a double and a triple
        # jump glide straight at it
        F = self.m.floors
        col = F.col
        ix, iz = col % self.m.nx, col // self.m.nx
        step = max(int(round(2.0 / self.m.grid)), 1)
        lat = np.nonzero((ix % step == 0) & (iz % step == 0) & self.free & ~self.steep)[0]
        lx, lz = self.m.xz_of(col[lat])
        ly = F.y[lat]
        ratio = self.tn.t['GlideSpeed'] / self.tn.t['GlideSink']
        aimed = [mv for mv in M.MOVES if mv.glide and (not o.moves or mv.name in o.moves)]
        for p in self.pickups:
            if p['type'] not in ('star', 'red_coin'):
                continue
            dx, dz = p['x'] - lx, p['z'] - lz
            d = np.hypot(dx, dz)
            above = ly + 4.0 - p['y']
            sel = np.nonzero((d > 3.0) & (above > 0) & (d <= above * ratio + 10.0))[0]
            if len(sel) == 0:
                continue
            yaw = np.arctan2(dx[sel], dz[sel])
            for mv in aimed:
                vy, fwd, ctrl, cap, gl = M.launch_state(mv, self.tn)
                k = len(sel)
                parts.append(S.Batch(lx[sel].astype(float), ly[sel].astype(float), lz[sel].astype(float), yaw,
                                     np.full(k, vy), np.full(k, fwd), np.full(k, ctrl), np.full(k, cap), np.ones(k),
                                     np.full(k, mv.st, np.int8), np.ones(k, bool), np.zeros(k, bool),
                                     max_ticks=o.max_ticks))
                srcs.append(lat[sel])
                mids.append(np.full(k, MOVE_ID[mv.name], np.int16))
        return S.Batch.concat(parts), np.concatenate(srcs), np.concatenate(mids)

    # ---- attachments as nodes

    def attachment_nodes(self):
        """Pole levels (a metre apart) and rail samples (a metre apart): node ids after the floors."""
        nid = self.n_floor
        self.pole_nodes = []
        for k, p in enumerate(self.poles):
            lo, hi = p['y'], p['top'] - self.tn.t['PoleTop']
            levels = list(np.arange(lo, hi, 1.0)) + [hi] if hi > lo else [lo]
            self.pole_nodes.append((nid, np.array(levels)))
            nid += len(levels)
        self.rail_nodes = []
        for k, r in enumerate(self.rails):
            pts = r['points']
            seg = [math.dist(a, b) for a, b in zip(pts[:-1], pts[1:])]
            total = sum(seg)
            ss = np.linspace(0, total, max(int(total) + 1, 2))
            # grind +, grind -, hang
            self.rail_nodes.append((nid, ss, total))
            nid += 3 * len(ss)
            # where a body hangs clear of the floors under the rail (attach.akr's hang_clear())
            r['clear'] = np.array([self.hang_clear(*self.rail_point(k, s)[0]) for s in ss], bool)
        self.n_nodes = nid

    def hang_clear(self, x, y, z):
        """attach.akr's hang_clear(): the hanging feet no more than HANG_CLEAR under the floor under
        the rail point (x, y, z)."""
        m, a = self.m, self.tn.attach
        f = int(m.floor_below(np.array([m.col_of(x, z)]), np.array([y - 0.3]))[0])
        return f < 0 or float(m.floors.y[f]) <= y - a['HANG_BELOW'] + a['HANG_CLEAR']

    def pole_node(self, k, yv):
        base, lv = self.pole_nodes[k]
        return base + int(np.clip(np.searchsorted(lv, yv - 0.5), 0, len(lv) - 1))

    def rail_node(self, k, s, kind):
        base, ss, _ = self.rail_nodes[k]
        i = int(np.clip(np.rint(np.interp(s, ss, np.arange(len(ss)))), 0, len(ss) - 1))
        return base + kind * len(ss) + i

    def rail_point(self, k, s):
        pts = self.rails[k]['points']
        acc = 0.0
        for a, b in zip(pts[:-1], pts[1:]):
            ln = math.dist(a, b)
            if acc + ln >= s or b is pts[-1]:
                u = 0 if ln == 0 else min(max((s - acc) / ln, 0), 1)
                d = [(b[i] - a[i]) / ln if ln else 0 for i in range(3)]
                return tuple(a[i] + (b[i] - a[i]) * u for i in range(3)), d
            acc += ln
        return pts[-1], [0, 0, 0]

    def node_pos(self, nid):
        """(x, y, z, what) of a node."""
        if nid < self.n_floor:
            x, z = self.m.xz_of(self.m.floors.col[nid])
            return float(x), float(self.m.floors.y[nid]), float(z), 'floor'
        for k, (base, lv) in enumerate(self.pole_nodes):
            if base <= nid < base + len(lv):
                p = self.poles[k]
                return p['x'], float(lv[nid - base]), p['z'], f'pole {p["id"]}'
        for k, (base, ss, _) in enumerate(self.rail_nodes):
            if base <= nid < base + 3 * len(ss):
                kind, i = divmod(nid - base, len(ss))
                (x, y, z), _ = self.rail_point(k, ss[i])
                what = ('grind' if kind < 2 else 'hang') + f' {self.rails[k]["id"]}'
                return x, y - (1.75 if kind == 2 else 0), z, what
        return None

    # ---- results to edges

    def edges_from(self, res, src, mid, t0):
        """(src, dst, cost, move) for flights that ended on something to stand on or hold."""
        o = res.outcome
        dst = np.full(len(o), -1, np.int64)
        land = (o == S.LAND) | (o == S.LEDGE)
        dst[land] = res.floor[land]
        dst[land & self.buried[np.maximum(dst, 0)]] = -1     # not onto a floor buried under another
        for i in np.nonzero(o == S.POLE)[0]:
            dst[i] = self.pole_node(int(res.floor[i]), res.y[i])
        for i in np.nonzero((o == S.RAIL) | (o == S.HANG))[0]:
            kind = 2 if o[i] == S.HANG else (0 if res.rail_v[i] >= 0 else 1)
            dst[i] = self.rail_node(int(res.floor[i]), res.rail_s[i], kind)
        ok = dst >= 0
        cost = res.ticks / 60.0 + t0 + np.where(o == S.LEDGE, self.tn.t['LedgeClimb'] / 60 + 0.15, 0)
        return src[ok], dst[ok], cost[ok].astype(np.float32), mid[ok], np.nonzero(ok)[0]

    # ---- later passes

    def kick_batch(self, res, src, mid):
        k = res.kicks
        if len(k.get('i', [])) == 0:
            return None
        tn = self.tn
        nx_, nz_ = k['nx'], k['nz']
        vin_x, vin_z = np.sin(k['yaw_in']), np.cos(k['yaw_in'])
        d = vin_x * nx_ + vin_z * nz_
        rx, rz = vin_x - 2 * d * nx_, vin_z - 2 * d * nz_
        ln = np.hypot(rx, rz)
        rx, rz = rx / np.maximum(ln, 1e-9), rz / np.maximum(ln, 1e-9)
        low = rx * nx_ + rz * nz_ < 0.5
        rx = np.where(low, rx + nx_, rx)
        rz = np.where(low, rz + nz_, rz)
        ln = np.hypot(rx, rz)
        yaw = np.arctan2(rx / np.maximum(ln, 1e-9), rz / np.maximum(ln, 1e-9))
        # one kick per wall spot and heading: thin the events
        key = (np.rint(k['x'] * 2).astype(np.int64) * 1000003 + np.rint(k['z'] * 2).astype(np.int64) * 7919 +
               np.rint(k['y'] * 2).astype(np.int64) * 31 + np.rint(yaw * 4).astype(np.int64))
        _, first = np.unique(key, return_index=True)
        n = len(first)
        fwd = np.maximum(k['speed'][first], tn.mps('KickHGood'))
        b = S.Batch(k['x'][first], k['y'][first], k['z'][first], yaw[first], np.full(n, tn.mps('KickVyGood')), fwd,
                    np.ones(n), np.full(n, tn.mps('AirMax')), np.ones(n), np.full(n, M.ST_KICK, np.int8),
                    np.zeros(n, bool), np.zeros(n, bool), max_ticks=self.opts.max_ticks)
        i = k['i'][first]
        return b, src[i], np.full(n, MOVE_ID[M.KICK], np.int16), i, k['tick'][first]

    def release_batch(self, res, src, mid):
        r = res.releases
        if len(r.get('i', [])) == 0:
            return None
        # one let-go per 2 m spot, height band and heading
        key = (np.rint(r['x'] / 2).astype(np.int64) * 1000003 + np.rint(r['z'] / 2).astype(np.int64) * 7919 +
               np.rint(r['y'] / 2).astype(np.int64) * 31 + np.rint(r['yaw'] * 8 / math.pi).astype(np.int64))
        _, first = np.unique(key, return_index=True)
        n = len(first)
        tn = self.tn
        stick = np.tile([1.0, 0.0], n)
        idx = np.repeat(first, 2)
        b = S.Batch(r['x'][idx], r['y'][idx], r['z'][idx], r['yaw'][idx], r['vy'][idx], r['fwd'][idx], np.ones(2 * n),
                    np.full(2 * n, tn.mps('AirMax')), stick, np.full(2 * n, M.ST_FALL, np.int8),
                    np.zeros(2 * n, bool), np.zeros(2 * n, bool), max_ticks=self.opts.max_ticks)
        i = r['i'][idx]
        return b, src[i], np.full(2 * n, MOVE_ID[M.RELEASE], np.int16), i, r['tick'][idx], r['gtime'][idx]

    def attachment_launches(self):
        """Jumps and drops off every pole level and rail sample; and the walking/holding edges
        along them."""
        tn = self.tn
        rows = []           # (src node, x, y, z, yaw, vy, fwd, stick, st, skip_pole, skip_rail, move)
        e_src, e_dst, e_cost, e_mid = [], [], [], []
        climb, slide = tn.t['PoleClimb'], tn.t['PoleSlide']
        hold = self.tn.attach['POLE_HOLD']
        for k, p in enumerate(self.poles):
            base, lv = self.pole_nodes[k]
            for i in range(len(lv) - 1):
                dy = lv[i + 1] - lv[i]
                e_src += [base + i, base + i + 1]
                e_dst += [base + i + 1, base + i]
                e_cost += [dy / climb, dy / slide]
                e_mid += [MOVE_ID[M.POLE]] * 2
            # down at the floor: on foot
            fc = self.m.col_of(p['x'], p['z'] + 0.0)
            f = int(self.m.floor_below(np.array([fc]), np.array([p['y'] + 0.4]))[0])
            if f >= 0:
                e_src.append(base)
                e_dst.append(f)
                e_cost.append(0.2)
                e_mid.append(MOVE_ID[M.POLE_DROP])
            angs = [p['ang']] if p['front'] else [2 * math.pi * a / 8 for a in range(8)]
            levels = sorted(set([len(lv) - 1] + list(range(len(lv) - 1, -1, -3))))
            for li in levels:
                yv = lv[li]
                for ang in angs:
                    px, pz = p['x'] + math.sin(ang) * hold, p['z'] + math.cos(ang) * hold
                    rows.append((base + li, px, yv, pz, ang, tn.mps('PoleJumpVy'), tn.mps('PoleJumpH'), 1.0, M.ST_KICK,
                                 k, -1, MOVE_ID[M.POLE_JUMP]))
                    rows.append((base + li, px, yv, pz, ang, 0.0, 0.0, 0.0, M.ST_FALL, k, -1, MOVE_ID[M.POLE_DROP]))
        gmin, gmax = tn.mps('GrindMin'), tn.mps('GrindMax')
        climb_max = tn.t['GrindAccel'] / tn.t['Gravity']      # the steepest rise a grind keeps going up
        hang_v = tn.t['HangSpeed']
        for k, r in enumerate(self.rails):
            base, ss, total = self.rail_nodes[k]
            n = len(ss)
            clear = r['clear']
            for i in range(n - 1):
                ds = ss[i + 1] - ss[i]
                if not r['hang']:              # a hang-only rail is never ground
                    # uphill only where the stick's push beats gravity (attach.akr: an uphill grind
                    # slows under the minimum and slides back)
                    rise = (self.rail_point(k, ss[i + 1])[0][1] - self.rail_point(k, ss[i])[0][1]) / max(ds, 1e-6)
                    for a_, b_, up_ in ((base + i, base + i + 1, rise), (base + n + i + 1, base + n + i, -rise)):
                        if up_ <= climb_max:
                            e_src.append(a_)
                            e_dst.append(b_)
                            e_cost.append(ds / (gmin * 60))
                            e_mid.append(MOVE_ID[M.GRIND])
                if clear[i] and clear[i + 1]:  # a hang moves along only where it hangs clear
                    e_src += [base + 2 * n + i, base + 2 * n + i + 1]
                    e_dst += [base + 2 * n + i + 1, base + 2 * n + i]
                    e_cost += [ds / hang_v, ds / hang_v]
                    e_mid += [MOVE_ID[M.HANG]] * 2
            for i, s in enumerate(ss):
                (x, y, z), d = self.rail_point(k, s)
                yaw = math.atan2(d[0], d[2])
                for sign, kind in (() if r['hang'] else ((1, 0), (-1, 1))):
                    yw = yaw if sign > 0 else yaw + math.pi
                    for v in (gmin, gmax):
                        rows.append((base + kind * n + i, x, y, z, yw, tn.mps('GrindJumpVy'), v, 1.0, M.ST_JUMP, -1, k,
                                     MOVE_ID[M.GRIND_JUMP]))
                    end = (i == n - 1 and sign > 0) or (i == 0 and sign < 0)
                    if end and not r['closed']:
                        for v in (gmin, gmax):
                            for st in (1.0, 0.0):
                                rows.append((base + kind * n + i, x, y, z, yw, 0.0, v, st, M.ST_FALL, -1, k,
                                             MOVE_ID[M.GRIND_END]))
                # off a hang: drop, or a hang jump toward four sides (where a hang is held)
                if not clear[i]:
                    continue
                hy = y - tn.attach['HANG_BELOW']
                rows.append((base + 2 * n + i, x, hy, z, yaw, 0.0, 0.0, 0.0, M.ST_FALL, -1, k, MOVE_ID[M.HANG_DROP]))
                for a in (0, math.pi / 2, math.pi, -math.pi / 2):
                    rows.append((base + 2 * n + i, x, hy, z, yaw + a, tn.mps('HangJumpVy'), 0.0, 1.0, M.ST_JUMP, -1, k,
                                 MOVE_ID[M.HANG_JUMP]))
        if rows:
            a = np.array(rows, dtype=float)
            n = len(a)
            b = S.Batch(a[:, 1], a[:, 2], a[:, 3], a[:, 4], a[:, 5], a[:, 6], np.ones(n), np.full(n, tn.mps('AirMax')),
                        a[:, 7], a[:, 8].astype(np.int8), np.zeros(n, bool), np.zeros(n, bool),
                        skip_pole=a[:, 9].astype(np.int64), skip_rail=a[:, 10].astype(np.int64),
                        max_ticks=self.opts.max_ticks)
            src = a[:, 0].astype(np.int64)
            mid = a[:, 11].astype(np.int16)
        else:
            b, src, mid = S.empty_batch(), np.zeros(0, np.int64), np.zeros(0, np.int16)
        static = (np.array(e_src, np.int64), np.array(e_dst, np.int64), np.array(e_cost, np.float32),
                  np.array(e_mid, np.int16))
        return (b, src, mid), static

    # ---- everything

    def run(self):
        o = self.opts
        self.build_walk()
        self.attachment_nodes()
        self.flights = Flights()
        self.pool = Pool(self.flyer, o.processes)
        t = time.perf_counter()
        b, src, mid = self.first_pass()
        self._fly('take-offs', b, src, mid, None)
        (ab, asrc, amid), self.static_edges = self.attachment_launches()
        self._fly('poles and rails', ab, asrc, amid, None)
        self.first_sets = len(self.flights.result)
        # wall kicks, chained, and the glides' let-go points
        sets = list(range(len(self.flights.result)))
        for depth in range(o.kick_depth):
            new = []
            for si in sets:
                got = self.kick_batch(self.flights.result[si], self.flights.src[si], self.flights.move[si])
                if got:
                    kb, ks, km, ki, kt = got
                    new.append(self._fly(f'wall kicks ({depth + 1})', kb, ks, km, (si, ki), kt))
                if depth == 0:
                    got = self.release_batch(self.flights.result[si], self.flights.src[si], self.flights.move[si])
                    if got:
                        rb, rs, rm, ri, rt, rg = got
                        new.append(self._fly('glide let-go', rb, rs, rm, (si, ri), rt, rg))
            sets = [s for s in new if s is not None]
        self.pool.close()
        self.timing['flights'] = round(time.perf_counter() - t, 1)
        t = time.perf_counter()
        self.build_graph()
        self.timing['graph'] = round(time.perf_counter() - t, 1)

    def _fly(self, what, b, src, mid, parent, ptick=None, gtime=None):
        if b is None or len(b) == 0:
            return None
        F = self.flights
        n = len(b)
        if parent is None:
            setup = np.array([SETUP.get(nm, 0.0) for nm in MOVE_NAMES])
            F.t0.append(setup[np.asarray(mid, np.int64)])
            F.root.append(np.asarray(mid, np.int16))
            F.kicks.append(np.zeros(n, np.int16))
            F.release.append(np.zeros(n, np.int32))
        else:
            ps, prow = parent
            F.t0.append(F.t0[ps][prow] + np.asarray(ptick) / 60.0)
            F.root.append(F.root[ps][prow])
            F.kicks.append(F.kicks[ps][prow] + (np.asarray(mid) == MOVE_ID[M.KICK]).astype(np.int16))
            F.release.append((np.asarray(gtime) if gtime is not None else 0) + F.release[ps][prow])
        t = time.perf_counter()
        r = self.pool.fly(b, self.opts.release_every)
        self.flights.batch.append(b)
        self.flights.result.append(r)
        self.flights.src.append(np.asarray(src, np.int64))
        self.flights.move.append(np.asarray(mid, np.int16))
        self.flights.parent.append(parent)
        counts = np.bincount(r.outcome, minlength=9)
        self.log(f'  {what}: {len(b):,} flights in {time.perf_counter() - t:.1f} s: ' +
                 ', '.join(f'{S.OUTCOME_NAMES[k]} {counts[k]:,}' for k in range(1, 9) if counts[k]))
        return len(self.flights.result) - 1

    def build_graph(self):
        from scipy.sparse import csr_matrix
        from scipy.sparse.csgraph import dijkstra
        ws, wd, wc = self.walk
        srcs, dsts, costs, mids = [ws.astype(np.int64)], [wd.astype(np.int64)], [wc], [np.full(len(ws), -1, np.int16)]
        fsets, frows = [np.full(len(ws), -1, np.int32)], [np.full(len(ws), -1, np.int64)]
        ss, sd, sc, sm = self.static_edges
        srcs.append(ss)
        dsts.append(sd)
        costs.append(sc)
        mids.append(sm)
        fsets.append(np.full(len(ss), -1, np.int32))
        frows.append(np.full(len(ss), -1, np.int64))
        for k, (r, s, mid) in enumerate(zip(self.flights.result, self.flights.src, self.flights.move)):
            es, ed, ec, em, rows = self.edges_from(r, s, mid, self.flights.t0[k])
            srcs.append(es)
            dsts.append(ed)
            costs.append(ec)
            mids.append(em)
            fsets.append(np.full(len(es), k, np.int32))
            frows.append(rows)
        src = np.concatenate(srcs)
        dst = np.concatenate(dsts)
        cost = np.concatenate(costs).astype(np.float64)
        mid = np.concatenate(mids)
        fset = np.concatenate(fsets)
        frow = np.concatenate(frows)
        # keep the cheapest of parallel edges
        key = src * self.n_nodes + dst
        order = np.lexsort((cost, key))
        key, src, dst, cost, mid, fset, frow = (v[order] for v in (key, src, dst, cost, mid, fset, frow))
        first = np.r_[True, key[1:] != key[:-1]]
        src, dst, cost, mid, fset, frow = (v[first] for v in (src, dst, cost, mid, fset, frow))
        cost = np.maximum(cost, 1e-4)
        self.edges = (src, dst, cost, mid)
        self.edge_flight = (fset, frow)
        self._ekeys_sorted = key[first]              # sorted, unique
        self.G = csr_matrix((cost, (src, dst)), shape=(self.n_nodes, self.n_nodes))
        self.start = None
        if self.spawn is not None:
            c = self.m.col_of(self.spawn[0], self.spawn[2])
            f = int(self.m.floor_below(np.array([c]), np.array([self.spawn[1] + 0.5]))[0])
            self.start = f
        if self.start is None or self.start < 0:
            raise RuntimeError('no floor under the spawn')
        self.dist, self.pred = dijkstra(self.G, directed=True, indices=self.start, return_predecessors=True)
        reach = np.isfinite(self.dist)
        self.log(f'  graph: {self.n_nodes:,} nodes, {len(src):,} edges; reachable from the spawn: '
                 f'{int(reach[:self.n_floor].sum()):,} floor entries')

    def edge_index(self, u, v):
        key = int(u) * int(self.n_nodes) + int(v)
        i = int(np.searchsorted(self._ekeys_sorted, key))
        if i < len(self._ekeys_sorted) and int(self._ekeys_sorted[i]) == key:
            return i
        return -1

    def edge_move(self, u, v):
        """The move name of the cheapest edge u -> v."""
        i = self.edge_index(u, v)
        if i < 0:
            return '?'
        m = int(self.edges[3][i])
        return M.WALK if m < 0 else MOVE_NAMES[m]

    def edge_flight_row(self, u, v):
        """(flight set, row) of the flight behind edge u -> v, or None."""
        i = self.edge_index(u, v)
        if i < 0 or self.edge_flight[0][i] < 0:
            return None
        return int(self.edge_flight[0][i]), int(self.edge_flight[1][i])

    def last_flight(self, node, pred=None):
        """The last flight on the cheapest route to node (walking back past walks, grinds and
        hangs), or None."""
        pred = self.pred if pred is None else pred
        v = int(node)
        guard = 0
        while v >= 0 and guard < 200000:
            u = int(pred[v])
            if u < 0:
                return None
            f = self.edge_flight_row(u, v)
            if f is not None:
                return f
            v = u
            guard += 1
        return None

    def dist_from(self, node):
        from scipy.sparse.csgraph import dijkstra
        d, p = dijkstra(self.G, directed=True, indices=node, return_predecessors=True)
        return d, p

    def route_nodes(self, node, pred=None):
        """The node ids of the cheapest route to node, from its start."""
        pred = self.pred if pred is None else pred
        path = []
        v = int(node)
        guard = 0
        while v >= 0 and guard < 200000:
            path.append(v)
            v = int(pred[v])
            guard += 1
        return path[::-1]

    def route_flights(self, node, pred=None):
        """The flights of the cheapest route to node, in order: [(flight set, row, from node, to node)]."""
        path = self.route_nodes(node, pred)
        out = []
        for u, v in zip(path[:-1], path[1:]):
            f = self.edge_flight_row(u, v)
            if f is not None:
                out.append((f[0], f[1], u, v))
        return out

    def graph_without(self, banned, kick_penalty=5.0):
        """The graph with the edges (u, v) in banned made too dear to take, and wall kicks (the
        reach map's least sure flights) made dearer by kick_penalty seconds."""
        G = self.G.copy()
        if kick_penalty and G.nnz == len(self.edges[0]):
            # the edges are sorted by (src, dst) and unique, as G's data is
            G.data[self.edges[3] == MOVE_ID[M.KICK]] += kick_penalty
        for u, v in banned:
            i = self.edge_index(u, v)
            if i >= 0:
                lo, hi = G.indptr[u], G.indptr[u + 1]
                j = lo + np.searchsorted(G.indices[lo:hi], v)
                if j < hi and G.indices[j] == v:
                    G.data[j] = 1e9
        return G

    def route(self, node, pred=None, dist=None):
        """The cheapest route from the start to node: [(move, node)], walking merged."""
        pred = self.pred if pred is None else pred
        path = []
        v = node
        guard = 0
        while v >= 0 and guard < 200000:
            path.append(v)
            v = pred[v]
            guard += 1
        path.reverse()
        steps = []
        for u, v in zip(path[:-1], path[1:]):
            mv = self.edge_move(u, v)
            if steps and steps[-1][0] == mv == M.WALK:
                steps[-1] = (mv, v)
            else:
                steps.append((mv, v))
        return [(mv, self.node_pos(v)) for mv, v in steps]
