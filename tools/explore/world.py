"""The world as the explorer reads it: the pack's collision rasterised onto a grid of columns,
and the entities the robot can use or take.

Every column (a point of a GRID-metre lattice) keeps three sorted lists, each a pair of arrays
keyed by column * KEY + height so one numpy searchsorted answers a batch of queries:

- floors: the height of every floor triangle over the column, as the reader's wp_floor() tests
  it (the same edge rows and height rows, all of them, not just the highest), with its normal's
  y, its surface byte and its tag;
- ceilings: the same for ceiling triangles;
- walls: for a body whose feet are at height y over the column, whether a wall pushes it at one
  of player.akr's push heights (PUSH_H): wp_coll_push()'s test (closer than the radius to the
  plane, inside the triangle's three edge planes), solved for y, as merged intervals of feet
  heights, each with the horizontal normal of the wall that made it.

Layers: a triangle in a layer is kept with its layer, and a WorldModel is built for one set of
layers on (the world's start state by default, or a shortcut's).
"""
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from worldkit.pack import ONE, KIND_FLOOR, KIND_WALL, KIND_CEILING  # noqa: E402
from worldkit import verify_static as VS  # noqa: E402

GRID = 0.25             # metres between columns
KEY = 4096.0            # column * KEY + height: heights stay within +-2048 m
MARGIN = 6.0            # metres of empty grid kept round the cells (so leaving is seen)


@dataclass
class Sorted:
    """Entries over columns, sorted by (column, y)."""
    key: np.ndarray         # column * KEY + y (float64)
    col: np.ndarray         # int64
    y: np.ndarray           # float64 (walls: the interval's low end)
    extra: dict = field(default_factory=dict)

    def __len__(self):
        return len(self.key)


def _sorted(col, y, **extra):
    col = np.asarray(col, np.int64)
    y = np.asarray(y, np.float64)
    key = col * KEY + y
    order = np.argsort(key, kind='stable')
    return Sorted(key[order], col[order], y[order], {k: np.asarray(v)[order] for k, v in extra.items()})


@dataclass
class Entity:
    n: int                  # the pack's entity number
    id: str                 # the recipe's id ('' when not found)
    type: str
    pos: tuple
    yaw: float
    layer: object           # layer name or None
    params: dict


class WorldModel:
    """A world's collision on the column grid, for one set of layers."""

    def __init__(self, world, tuning, layers_on=None, grid=GRID):
        self.world = world                      # worldkit.quick.World
        self.tuning = tuning
        self.grid = grid
        pack = world.decoded
        self.pack = pack
        size = world.meta['cell_size']
        self.cell_size = size
        xs = [i for i, _ in pack.cells]
        zs = [j for _, j in pack.cells]
        # the level: the cells' rectangle (world metres)
        self.frame = (min(xs) * size, min(zs) * size, (max(xs) + 1) * size, (max(zs) + 1) * size)
        x0, z0, x1, z1 = self.frame
        self.ox, self.oz = x0 - MARGIN, z0 - MARGIN
        self.nx = int(round((x1 - x0 + 2 * MARGIN) / grid)) + 1
        self.nz = int(round((z1 - z0 + 2 * MARGIN) / grid)) + 1
        names = [n for n, _ in world.meta['layers']]
        self.layer_names = names
        if layers_on is None:
            layers_on = {n for n, on in world.meta['layers'] if on}
        self.layers_on = set(layers_on)
        self._on_ids = {names.index(n) for n in self.layers_on if n in names}
        self.tris = VS.world_triangles(pack)
        self._build()

    # ---- the grid

    def col_of(self, x, z):
        """Column index of points (arrays or scalars); -1 off the grid."""
        ix = np.rint((np.asarray(x, np.float64) - self.ox) / self.grid).astype(np.int64)
        iz = np.rint((np.asarray(z, np.float64) - self.oz) / self.grid).astype(np.int64)
        ok = (ix >= 0) & (ix < self.nx) & (iz >= 0) & (iz < self.nz)
        return np.where(ok, iz * self.nx + ix, -1)

    def xz_of(self, col):
        col = np.asarray(col, np.int64)
        return self.ox + (col % self.nx) * self.grid, self.oz + (col // self.nx) * self.grid

    def inside(self, x, z):
        x0, z0, x1, z1 = self.frame
        return (np.asarray(x) >= x0) & (np.asarray(x) <= x1) & (np.asarray(z) >= z0) & (np.asarray(z) <= z1)

    def _present(self, t):
        return t.layer is None or t.layer in self._on_ids

    def _pairs(self, bx0, bx1, bz0, bz1):
        """(triangle index, ix, iz) for every column in each triangle's box (inclusive)."""
        w = np.maximum(bx1 - bx0 + 1, 0)
        h = np.maximum(bz1 - bz0 + 1, 0)
        n = w * h
        total = int(n.sum())
        if total == 0:
            e = np.zeros(0, np.int64)
            return e, e, e
        t = np.repeat(np.arange(len(n)), n)
        start = np.repeat(np.cumsum(n) - n, n)
        off = np.arange(total) - start
        ww = w[t]
        return t, bx0[t] + off % ww, bz0[t] + off // ww

    def _box(self, verts, grow):
        v = np.asarray(verts, np.float64)              # (n, 3, 3)
        lo = v.min(axis=1)
        hi = v.max(axis=1)
        bx0 = np.ceil((lo[:, 0] - grow - self.ox) / self.grid).astype(np.int64)
        bx1 = np.floor((hi[:, 0] + grow - self.ox) / self.grid).astype(np.int64)
        bz0 = np.ceil((lo[:, 2] - grow - self.oz) / self.grid).astype(np.int64)
        bz1 = np.floor((hi[:, 2] + grow - self.oz) / self.grid).astype(np.int64)
        return (np.clip(bx0, 0, self.nx - 1), np.clip(bx1, -1, self.nx - 1),
                np.clip(bz0, 0, self.nz - 1), np.clip(bz1, -1, self.nz - 1))

    def _flats(self, kind):
        tris = [t for t in self.tris if t.kind == kind and t.verts is not None and self._present(t)]
        if not tris:
            return _sorted([], [], ny=[], surf=[], tag=[])
        h = np.array([t.rows[0] for t in tris], np.float64)                 # a, b, c (raw)
        ed = np.array([t.rows[1] for t in tris], np.float64)                # (n, 3, 3): mx, mz, k
        surf = np.array([t.surface for t in tris], np.int32)
        tag = np.array([t.tag for t in tris], np.int32)
        bx0, bx1, bz0, bz1 = self._box([t.verts for t in tris], 0.0)
        cols, ys, nys, ss, tg = [], [], [], [], []
        chunk = 400000
        order = np.arange(len(tris))
        # chunk by the triangles' column counts
        counts = np.maximum(bx1 - bx0 + 1, 0) * np.maximum(bz1 - bz0 + 1, 0)
        csum = np.cumsum(counts)
        starts = [0]
        acc = 0
        for k, c in enumerate(counts):
            acc += c
            if acc > chunk:
                starts.append(k + 1)
                acc = 0
        starts.append(len(tris))
        for a, b in zip(starts[:-1], starts[1:]):
            if a >= b:
                continue
            sl = order[a:b]
            t, ix, iz = self._pairs(bx0[sl], bx1[sl], bz0[sl], bz1[sl])
            t = sl[t]
            X = (self.ox + ix * self.grid) * ONE
            Z = (self.oz + iz * self.grid) * ONE
            ok = np.ones(len(t), bool)
            for e in range(3):
                ok &= ed[t, e, 0] * X + ed[t, e, 1] * Z + ed[t, e, 2] * ONE >= 0
            t, X, Z, ix, iz = t[ok], X[ok], Z[ok], ix[ok], iz[ok]
            y = (h[t, 0] * X + h[t, 1] * Z) / ONE / ONE + h[t, 2] / ONE
            # the normal of a floor row: (-a, ONE, -b) normalised
            ny = ONE / np.sqrt(h[t, 0] ** 2 + h[t, 1] ** 2 + ONE * ONE)
            cols.append(iz * self.nx + ix)
            ys.append(y)
            nys.append(ny)
            ss.append(surf[t])
            tg.append(tag[t])
        return _sorted(np.concatenate(cols), np.concatenate(ys), ny=np.concatenate(nys),
                       surf=np.concatenate(ss), tag=np.concatenate(tg))

    def _walls(self):
        r = self.tuning.radius
        tris = [t for t in self.tris if t.kind == KIND_WALL and t.verts is not None and self._present(t)]
        if not tris:
            return _sorted([], [], hi=[], hx=[], hz=[], ny=[], tag=[])
        P = np.array([t.rows[0] for t in tris], np.float64) / ONE          # plane: n (unit), w
        P[:, 3] = np.array([t.rows[0][3] for t in tris], np.float64) / ONE
        E = np.array([t.rows[1] for t in tris], np.float64) / ONE          # (n, 3, 4)
        tag = np.array([t.tag for t in tris], np.int32)
        hl = np.hypot(P[:, 0], P[:, 2])
        hx = np.where(hl > 0, P[:, 0] / np.maximum(hl, 1e-9), 0.0)
        hz = np.where(hl > 0, P[:, 2] / np.maximum(hl, 1e-9), 0.0)
        bx0, bx1, bz0, bz1 = self._box([t.verts for t in tris], r + self.grid)
        counts = np.maximum(bx1 - bx0 + 1, 0) * np.maximum(bz1 - bz0 + 1, 0)
        starts, acc = [0], 0
        for k, c in enumerate(counts):
            acc += c
            if acc > 400000:
                starts.append(k + 1)
                acc = 0
        starts.append(len(tris))
        push = self.tuning.push_h
        cols, los, his, hxs, hzs, nys, tgs = [], [], [], [], [], [], []
        big = 1e6
        for a, b in zip(starts[:-1], starts[1:]):
            if a >= b:
                continue
            sl = np.arange(a, b)
            t, ix, iz = self._pairs(bx0[sl], bx1[sl], bz0[sl], bz1[sl])
            t = sl[t]
            x = self.ox + ix * self.grid
            z = self.oz + iz * self.grid
            lo = np.full(len(t), -big)
            hi = np.full(len(t), big)
            ok = np.ones(len(t), bool)

            def half(cy, c0, strict_lo=None):
                # the y with cy * y + c0 >= 0
                nonlocal lo, hi, ok
                pos = cy > 1e-12
                neg = cy < -1e-12
                zer = ~(pos | neg)
                with np.errstate(divide='ignore', invalid='ignore'):
                    root = -c0 / np.where(zer, 1.0, cy)
                lo = np.where(pos, np.maximum(lo, root), lo)
                hi = np.where(neg, np.minimum(hi, root), hi)
                ok &= ~(zer & (c0 < 0))
            base = P[t, 0] * x + P[t, 2] * z + P[t, 3]
            # -r < d < r, d = P.y * y + base
            half(P[t, 1], base + r)
            half(-P[t, 1], r - base)
            for e in range(3):
                half(E[t, e, 1], E[t, e, 0] * x + E[t, e, 2] * z + E[t, e, 3])
            ok &= lo < hi
            t, ix, iz, lo, hi = t[ok], ix[ok], iz[ok], lo[ok], hi[ok]
            # an unbounded interval comes from a wall with no extent in y over this column (it
            # cannot be: the edge planes bound it), but clamp anyway
            lo = np.maximum(lo, -500.0)
            hi = np.minimum(hi, 2000.0)
            c = iz * self.nx + ix
            for ph in push:        # the feet heights at which this push height is in the wall
                cols.append(c)
                los.append(lo - ph)
                his.append(hi - ph)
                hxs.append(hx[t])
                hzs.append(hz[t])
                nys.append(P[t, 1])
                tgs.append(tag[t])
        col = np.concatenate(cols)
        lo = np.concatenate(los)
        hi = np.concatenate(his)
        hxa, hza, nya, tga = (np.concatenate(v) for v in (hxs, hzs, nys, tgs))
        # merge overlapping intervals per column, keeping the normal of the widest piece
        order = np.lexsort((lo, col))
        col, lo, hi, hxa, hza, nya, tga = (v[order] for v in (col, lo, hi, hxa, hza, nya, tga))
        if len(col) == 0:
            return _sorted([], [], hi=[], hx=[], hz=[], ny=[], tag=[])
        # running maximum of hi within each column
        newcol = np.r_[True, col[1:] != col[:-1]]
        grp = np.cumsum(newcol) - 1
        run_hi = hi.copy()
        # a segmented running max: process with a loop over a small number of passes
        run_hi = _seg_cummax(run_hi, newcol)
        start = newcol.copy()
        start[1:] |= lo[1:] > run_hi[:-1]
        sid = np.cumsum(start) - 1
        m_lo = lo[start]
        m_col = col[start]
        m_hi = np.full(sid[-1] + 1, -1e9)
        np.maximum.at(m_hi, sid, hi)
        width = hi - lo
        best = np.full(sid[-1] + 1, -1.0)
        np.maximum.at(best, sid, width)
        pick = np.zeros(sid[-1] + 1, np.int64)
        isbest = width >= best[sid]
        pick[sid[isbest]] = np.nonzero(isbest)[0]
        del grp
        return Sorted(m_col * KEY + m_lo, m_col, m_lo, {'hi': m_hi, 'hx': hxa[pick], 'hz': hza[pick],
                                                       'ny': nya[pick], 'tag': tga[pick]})

    def _build(self):
        self.floors = self._flats(KIND_FLOOR)
        self.ceilings = self._flats(KIND_CEILING)
        self.walls = self._walls()

    # ---- queries (vectorised; col -1 answers "none")

    def floor_below(self, col, y):
        """Index into self.floors of the highest floor at or below y over col, or -1."""
        if len(self.floors) == 0:
            return np.full(np.shape(col), -1, np.int64)
        q = np.asarray(col, np.int64) * KEY + np.asarray(y, np.float64)
        i = np.searchsorted(self.floors.key, q, side='right') - 1
        i = np.where(i >= 0, i, 0)
        ok = (len(self.floors) > 0) & (self.floors.col[i] == col) & (np.asarray(col) >= 0)
        return np.where(ok, i, -1)

    def ceiling_above(self, col, y):
        """Index into self.ceilings of the lowest ceiling at or above y over col, or -1."""
        if len(self.ceilings) == 0:
            return np.full(np.shape(col), -1, np.int64)
        q = np.asarray(col, np.int64) * KEY + np.asarray(y, np.float64)
        i = np.searchsorted(self.ceilings.key, q, side='left')
        n = len(self.ceilings)
        j = np.minimum(i, max(n - 1, 0))
        ok = (n > 0) & (i < n) & (self.ceilings.col[j] == col) & (np.asarray(col) >= 0)
        return np.where(ok, j, -1)

    def wall_at(self, col, y):
        """Index into self.walls of the wall interval holding feet height y over col, or -1."""
        if len(self.walls) == 0:
            return np.full(np.shape(col), -1, np.int64)
        q = np.asarray(col, np.int64) * KEY + np.asarray(y, np.float64)
        i = np.searchsorted(self.walls.key, q, side='right') - 1
        i = np.where(i >= 0, i, 0)
        n = len(self.walls)
        ok = (n > 0) & (self.walls.col[i] == col) & (self.walls.extra['hi'][i] >= y) & (np.asarray(col) >= 0)
        return np.where(ok, i, -1)

    # ---- per-column summaries

    def top_floor(self):
        """(nz, nx) array of the highest floor's height per column, NaN where there is none."""
        out = np.full(self.nx * self.nz, np.nan)
        f = self.floors
        if len(f):
            last = np.r_[f.col[1:] != f.col[:-1], True]
            out[f.col[last]] = f.y[last]
        return out.reshape(self.nz, self.nx)

    def floor_count(self):
        out = np.zeros(self.nx * self.nz, np.int32)
        np.add.at(out, self.floors.col, 1)
        return out


def _seg_cummax(v, newseg):
    """Running maximum of v restarting at each True in newseg."""
    out = v.copy()
    # doubling passes: out[i] = max(out[i], out[i - 2^k]) within the segment
    seg = np.cumsum(newseg)
    k = 1
    n = len(v)
    while k < n:
        same = np.zeros(n, bool)
        same[k:] = seg[k:] == seg[:-k]
        if not same.any():
            break
        shifted = np.full(n, -np.inf)
        shifted[k:] = out[:-k]
        out = np.where(same, np.maximum(out, shifted), out)
        k *= 2
    return out


# ---- entities

TYPES_KEPT = ('spawn', 'coin', 'red_coin', 'star', 'pole', 'rail', 'trigger', 'door', 'mover')


def recipe_entities(recipe):
    """Every entity of the world's cells, as written in the recipes: (id, type, position,
    params, layer, yaw)."""
    recipe = Path(recipe)
    w = json.loads(recipe.read_text())
    cell_dir = recipe.parent / w.get('cell_dir', 'cells')
    out = []
    for f in sorted(cell_dir.glob('*.cell.json')):
        c = json.loads(f.read_text())
        for e in c.get('entities', []):
            out.append(e)
    return out, w


def entities(world, recipe):
    """The pack's entities (numbered as the game numbers them) with their recipe ids and
    parameters, matched by position: the pack keeps neither."""
    pack = world.decoded
    rec, wjson = recipe_entities(recipe)
    snap = [e for c in world.meta['cells'] for e in c['entities']]
    by_id = {}
    for e in rec:
        by_id.setdefault(e['id'], e)
    pe = []
    for (i, j), c in pack.cells.items():
        cx, cz = VS._centre(pack, i, j)
        for e in c.entities:
            pe.append((e, (e['pos'][0] + cx) / ONE, e['pos'][1] / ONE, (e['pos'][2] + cz) / ONE))
    pe.sort(key=lambda r: r[0]['number'])
    names = [n for n, _ in world.meta['layers']]
    out = []
    used = set()
    for e, px, py, pz in pe:
        pos = (px, py, pz)
        best, bd = None, 1e9
        for k, s in enumerate(snap):
            if k in used:
                continue
            d = sum((a - b) ** 2 for a, b in zip(pos, s['position']))
            if d < bd:
                best, bd = k, d
        s = snap[best]
        used.add(best)
        r = by_id.get(s['id'], {})
        layer = r.get('layer')
        out.append(Entity(n=e['number'], id=s['id'], type=s['type'], pos=pos, yaw=e['yaw'] / ONE,
                          layer=layer if layer in names else None, params=dict(r.get('params', {}))))
    return out, wjson


def path_points(world, name):
    """A pack path's points (metres), or None."""
    pack = world.decoded
    for p in pack.paths:
        if p['name'] == name:
            return [tuple(c / ONE for c in q['pos']) for q in p['points']], bool(p.get('closed'))
    return None


def load_world(recipe, build_dir):
    """The compiled world through the World Kit's quick cache in BUILD/kit-cache."""
    from worldkit.quick import load_world as lw
    return lw(str(recipe), None, str(Path(build_dir) / 'kit-cache'))
