"""Terrain: ground heightfields and profiles swept along paths, in world coordinates, cut per
cell by the kit so that seams match by construction (WORLDKIT.md, "Terrain").

    result = compile_terrain(world, base, cell_size, cells, surface_of, warnings, overhang,
                             floor_max_degrees)
    result.pieces[(i, j)]      [Piece]: a native mesh per tile or sweep, placed at the cell centre
    result.collision[(i, j)]   [pack.Tri] in world coordinates
    result.palette             the provisional palette entries of the materials used

A **field** is a grid of height samples `spacing` apart over a rectangle. Its heights start from
`height` or a text file and are changed by operations in order; its quads take materials. The
kit cuts it into tiles (a cell, or 16 quads a side if that is less) and merges each tile's quads
greedily into rectangles that share a material and lie within `tolerance` of the patch through
their corners. A rectangle with only its four corners on its edges is two triangles; one with
more (a smaller neighbour's corners, or the neighbouring tile's) is zipped between its two long
sides or fanned from its centre, so no edge has a vertex in the middle of another's: no
T-junctions inside a tile, and across a tile edge both tiles use the same points (every corner
either tile has there, at any level of detail). The coarse level is the same merge with a
larger tolerance; it keeps the tile's edge points, so neighbours drawn at different levels
still meet.

A **sweep** is a profile carried along a path: cross-sections at the path's points (mitred at
corners), where the path crosses a cell edge, and at each step of a stair. Each strip between two
cross-sections goes to the cell holding the middle of its centre line; the cross-section on a
seam is shared, so the two cells' pieces meet there exactly.

Nothing here knows what ground, a path or a step is for: the outputs are ordinary placements and
collision triangles, and the World Checker checks them as it checks any other.
"""
from dataclasses import dataclass, field
import hashlib
import math

import meshlib
from assetkit.compiler import assign_palette, shading
from kitcore.errors import pointer
from .schema import WorldError

TAG_FIELD = 0xFFFE          # placement and collision tag of a field's tiles
TAG_SWEEP = 0xFFFD          # of a sweep's pieces
MAX_TILE_QUADS = 32
DEFAULT_TILE_QUADS = 16
DEFAULT_TOLERANCE = 0.01
DEFAULT_LOD_TOLERANCE = 0.25
DEFAULT_LOD_BAND = 2.0
MIN_MITRE_COS = 0.5         # a path may turn at most 120 degrees at a point
ONE = 65536


def q16(v):
    """v rounded to the 16.16 grid (halves away from zero, as the pack rounds)."""
    r = math.floor(abs(v) * ONE + 0.5) / ONE
    return r if v >= 0 else -r


@dataclass
class Piece:
    """A mesh the kit made for one cell: drawn at the cell centre, yaw 0."""
    kind: str                   # 'field' or 'sweep'
    name: str
    mesh: bytes                 # level 0, provisional palette colours
    faces: int
    levels: list = field(default_factory=list)  # [(distance, mesh bytes)] coarser levels
    band: float = DEFAULT_LOD_BAND
    ground: bool = True
    tag: int = TAG_FIELD
    materials: set = field(default_factory=set)
    level_faces: list = field(default_factory=list)


@dataclass
class Result:
    pieces: dict                # (i, j) -> [Piece]
    collision: dict             # (i, j) -> [P.Tri]
    palette: dict               # assign_palette()'s result, or None
    report: dict
    files: list                 # height files read
    fields: dict = None         # name -> Field (its samples H, materials, h(), for tests and tools)


def smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


# ---- areas

def _seg_closest(px, pz, a, b):
    """(distance, t) from (px, pz) to the segment a-b (each (x, z, ...)) seen from above."""
    dx, dz = b[0] - a[0], b[-1] - a[-1]
    ll = dx * dx + dz * dz
    t = 0.0 if ll == 0 else max(0.0, min(1.0, ((px - a[0]) * dx + (pz - a[-1]) * dz) / ll))
    x, z = a[0] + dx * t, a[-1] + dz * t
    return math.hypot(px - x, pz - z), t


class Polyline:
    """A path's line, for distances and heights seen from above."""

    def __init__(self, points, closed):
        self.points = [tuple(p) for p in points]
        self.closed = closed
        self.segs = list(zip(self.points, self.points[1:]))
        if closed:
            self.segs.append((self.points[-1], self.points[0]))

    def nearest(self, x, z):
        """(distance, height of the line there)."""
        best = None
        for a, b in self.segs:
            d, t = _seg_closest(x, z, a, b)
            if best is None or d < best[0]:
                best = (d, a[1] + (b[1] - a[1]) * t)
        return best

    def beyond(self, x, z, d):
        """Whether (x, z), at distance d from the line, lies past an end of an open path: its
        nearest point is the end, and it is ahead of it along the end segment."""
        if self.closed:
            return False
        for (a, b), sign in ((self.segs[0], -1), (self.segs[-1], 1)):
            p, q = (a, b) if sign > 0 else (b, a)      # q: the end, p: the point before it
            if math.hypot(x - q[0], z - q[-1]) <= d + 1e-9 and \
                    (x - q[0]) * (q[0] - p[0]) + (z - q[-1]) * (q[-1] - p[-1]) > 0:
                return True
        return False


class Area:
    """The signed distance (units, <= 0 inside) from a point to an operation's area."""

    def __init__(self, spec, paths, path):
        self.kind = None
        if spec is None:
            return
        kinds = [k for k in ('rect', 'circle', 'polygon', 'path') if k in spec]
        if len(kinds) != 1:
            raise WorldError(path, 'An area is exactly one of rect, circle, polygon or path.')
        self.kind = kinds[0]
        if ('width' in spec) != (self.kind == 'path'):
            raise WorldError(path + '/width', 'A path area takes a width, and only a path area does.')
        v = spec[self.kind]
        if self.kind == 'rect':
            self.r = (min(v[0], v[2]), min(v[1], v[3]), max(v[0], v[2]), max(v[1], v[3]))
        elif self.kind == 'circle':
            if v[2] <= 0:
                raise WorldError(path + '/circle/2', 'A circle\'s radius is positive.')
            self.c = v
        elif self.kind == 'polygon':
            self.poly = [tuple(p) for p in v]
        else:
            if v not in paths:
                raise WorldError(path + '/path', f'No path {v!r} in the world file\'s paths.')
            self.line = Polyline(paths[v]['points'], paths[v].get('closed', False))
            self.half = spec['width'] / 2

    def distance(self, x, z):
        k = self.kind
        if k is None:
            return -1.0
        if k == 'rect':
            x0, z0, x1, z1 = self.r
            dx, dz = max(x0 - x, 0.0, x - x1), max(z0 - z, 0.0, z - z1)
            if dx == 0 and dz == 0:
                return -min(x - x0, x1 - x, z - z0, z1 - z)
            return math.hypot(dx, dz)
        if k == 'circle':
            return math.hypot(x - self.c[0], z - self.c[1]) - self.c[2]
        if k == 'polygon':
            inside = False
            best = None
            n = len(self.poly)
            for i in range(n):
                a, b = self.poly[i], self.poly[(i + 1) % n]
                if (a[1] > z) != (b[1] > z) and x < a[0] + (z - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
                    inside = not inside
                d, _ = _seg_closest(x, z, a, b)
                best = d if best is None else min(best, d)
            return -best if inside else best
        return self.line.nearest(x, z)[0] - self.half

    def weight(self, x, z, falloff):
        d = self.distance(x, z)
        if d <= 0:
            return 1.0
        if falloff <= 0 or d >= falloff:
            return 0.0
        return smoothstep(1 - d / falloff)


# ---- heightfields

class Field:
    def __init__(self, name, spec, ctx):
        self.name, self.spec = name, spec
        self.path = pointer('/terrain/fields', name)
        s = spec['spacing']
        self.s = s
        (x0, z0), (x1, z1) = spec['min'], spec['max']
        for k, v in enumerate((x0, z0)):
            if v / s != math.floor(v / s):
                raise WorldError(f'{self.path}/min/{k}', f'The field\'s corners are multiples of its spacing ({s}).')
        for k, v in enumerate((x1, z1)):
            if v / s != math.floor(v / s):
                raise WorldError(f'{self.path}/max/{k}', f'The field\'s corners are multiples of its spacing ({s}).')
        if x1 <= x0 or z1 <= z0:
            raise WorldError(self.path + '/max', 'max lies beyond min in x and z.')
        size = ctx.size
        if size / s > 4096 or (x1 - x0) / s > 8192 or (z1 - z0) / s > 8192:
            raise WorldError(self.path + '/spacing', 'At most 8,192 quads along a side of a field.')
        self.qx0, self.qz0 = int(x0 / s), int(z0 / s)       # lattice coordinates of the low corner
        self.nx, self.nz = int((x1 - x0) / s), int((z1 - z0) / s)
        if self.nx * self.nz > 4_000_000:
            raise WorldError(self.path, 'At most 4,000,000 quads in a field.')
        tile = spec.get('tile')
        cell_quads = int(size / s)
        if tile is None:
            self.tq = min(cell_quads, DEFAULT_TILE_QUADS)
        else:
            if tile > size or tile / s > MAX_TILE_QUADS or tile / s < 1:
                raise WorldError(self.path + '/tile', f'A tile is at most a cell ({size}) and {MAX_TILE_QUADS} quads '
                                 f'({MAX_TILE_QUADS * s} units at this spacing), and at least one quad.')
            self.tq = int(tile / s)
        if cell_quads < 1:
            raise WorldError(self.path + '/spacing', 'The spacing is larger than a cell.')
        mats = ctx.materials
        for key in ('material',):
            if spec[key] not in mats:
                raise WorldError(f'{self.path}/{key}', f'No terrain material {spec[key]!r}.')
        if 'steep' in spec and spec['steep']['material'] not in mats:
            raise WorldError(self.path + '/steep/material', f'No terrain material {spec["steep"]["material"]!r}.')
        self.floor_cos = ctx.floor_cos
        self.heights(ctx)
        self.materials = [[spec['material']] * self.nx for _ in range(self.nz)]
        self.painted = [[False] * self.nx for _ in range(self.nz)]
        for k, op in enumerate(spec.get('operations', [])):
            self.apply(op, f'{self.path}/operations/{k}', ctx)
        self.H = [[q16(h) for h in row] for row in self.H]
        self.normals()
        if 'steep' in spec:
            lim = math.cos(math.radians(spec['steep']['degrees']))
            for jz in range(self.nz):
                for ix in range(self.nx):
                    m = self.materials[jz][ix]
                    if m is None or self.painted[jz][ix]:
                        continue
                    if min(n[1] / math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) for n in self.quad_normals(ix, jz)) < lim:
                        self.materials[jz][ix] = spec['steep']['material']

    # samples are H[jz][ix], jz along z from min, ix along x
    def heights(self, ctx):
        spec = self.spec
        if 'heights' in spec and 'height' in spec:
            raise WorldError(self.path + '/heights', 'Give height or a heights file, not both.')
        if 'heights' not in spec:
            self.H = [[float(spec.get('height', 0))] * (self.nx + 1) for _ in range(self.nz + 1)]
            return
        f = (ctx.base / spec['heights']).resolve()
        if not f.is_file():
            raise WorldError(self.path + '/heights', f'No heights file at {f}.')
        data = f.read_bytes()
        ctx.files.append((str(f), hashlib.sha256(data).hexdigest()))
        rows = []
        for n, line in enumerate(data.decode('utf-8').splitlines(), 1):
            line = line.split('#', 1)[0].split()
            if not line:
                continue
            try:
                row = [float(v) for v in line]
            except ValueError:
                raise WorldError(self.path + '/heights', f'{f}:{n}: heights are numbers separated by spaces.') from None
            if len(row) != self.nx + 1:
                raise WorldError(self.path + '/heights', f'{f}:{n}: {len(row)} heights; a row has {self.nx + 1} '
                                 f'(x from min to max every {self.s}).')
            if any(not math.isfinite(v) or abs(v) > 4000 for v in row):
                raise WorldError(self.path + '/heights', f'{f}:{n}: heights are finite and within +-4000.')
            rows.append(row)
        if len(rows) != self.nz + 1:
            raise WorldError(self.path + '/heights', f'{f}: {len(rows)} rows; the field has {self.nz + 1} '
                             f'(z from min to max every {self.s}).')
        self.H = rows

    def xz(self, ix, jz):
        return ((self.qx0 + ix) * self.s, (self.qz0 + jz) * self.s)

    def apply(self, op, path, ctx):
        kind = op['op']
        area = Area(op.get('area'), ctx.paths, path + '/area')
        falloff = op.get('falloff', 0.0)
        if kind in ('paint', 'hole'):
            if 'falloff' in op:
                raise WorldError(path + '/falloff', f'{kind} acts on whole quads: it has no falloff.')
            if kind == 'paint' and op['material'] not in ctx.materials:
                raise WorldError(path + '/material', f'No terrain material {op["material"]!r}.')
            s = self.s
            for jz in range(self.nz):
                for ix in range(self.nx):
                    x, z = self.xz(ix, jz)
                    if area.distance(x + s / 2, z + s / 2) <= 0:
                        if kind == 'hole':
                            self.materials[jz][ix] = None
                        elif self.materials[jz][ix] is not None:
                            self.materials[jz][ix] = op['material']
                            self.painted[jz][ix] = True
            return
        if kind == 'smooth':
            for _ in range(op.get('passes', 1)):
                H = self.H
                nz, nx = self.nz, self.nx
                blurred = []
                for jz in range(nz + 1):
                    row = []
                    for ix in range(nx + 1):
                        acc = 0.0
                        for dz, wz in ((-1, 1), (0, 2), (1, 1)):
                            r = H[min(nz, max(0, jz + dz))]
                            acc += wz * (r[max(0, ix - 1)] + 2 * r[ix] + r[min(nx, ix + 1)])
                        row.append(acc / 16)
                    blurred.append(row)
                for jz in range(nz + 1):
                    for ix in range(nx + 1):
                        w = area.weight(*self.xz(ix, jz), falloff)
                        if w:
                            H[jz][ix] += w * (blurred[jz][ix] - H[jz][ix])
            return
        if kind == 'ramp':
            a, b = op['from'], op['to']
            dx, dz = b[0] - a[0], b[2] - a[2]
            length = math.hypot(dx, dz)
            if length == 0:
                raise WorldError(path + '/to', 'A ramp\'s ends differ seen from above.')
            ux, uz = dx / length, dz / length
            half = op['width'] / 2
        if kind == 'bed':
            if op['path'] not in ctx.paths:
                raise WorldError(path + '/path', f'No path {op["path"]!r} in the world file\'s paths.')
            if 'area' in op:
                raise WorldError(path + '/area', 'A bed\'s area is its path and width.')
            line = Polyline(ctx.paths[op['path']]['points'], ctx.paths[op['path']].get('closed', False))
            half, depth = op['width'] / 2, op.get('depth', 0.0)
        if kind == 'terrace':
            step, bank, tb = op['step'], op.get('bank', 0.25), op.get('base', 0.0)
        for jz in range(self.nz + 1):
            row = self.H[jz]
            for ix in range(self.nx + 1):
                x, z = self.xz(ix, jz)
                h = row[ix]
                if kind == 'ramp':
                    t = (x - a[0]) * ux + (z - a[2]) * uz
                    p = abs(-(x - a[0]) * uz + (z - a[2]) * ux)
                    d = math.hypot(max(-t, t - length, 0.0), max(p - half, 0.0))
                    w = 1.0 if d <= 0 else (smoothstep(1 - d / falloff) if falloff > 0 and d < falloff else 0.0)
                    if w:
                        target = a[1] + (b[1] - a[1]) * max(0.0, min(1.0, t / length))
                        row[ix] = h + w * (target - h)
                    continue
                if kind == 'bed':
                    d, y = line.nearest(x, z)
                    if line.beyond(x, z, d):
                        continue            # an open path's bed ends square at its ends
                    d -= half
                    w = 1.0 if d <= 0 else (smoothstep(1 - d / falloff) if falloff > 0 and d < falloff else 0.0)
                    if w:
                        row[ix] = h + w * (y - depth - h)
                    continue
                w = area.weight(x, z, falloff)
                if not w:
                    continue
                if kind == 'set':
                    target = op['height']
                elif kind == 'add':
                    target = h + op['height']
                elif kind == 'carve':
                    target = min(h, op['height'])
                elif kind == 'fill':
                    target = max(h, op['height'])
                else:                       # terrace
                    u = (h - tb) / step
                    k = math.floor(u)
                    f = u - k
                    target = tb + (k + smoothstep((f - (1 - bank)) / bank)) * step
                row[ix] = h + w * (target - h)

    def present(self, qx, qz):
        """The material of the quad at lattice (qx, qz), or None (outside the field or a hole)."""
        ix, jz = qx - self.qx0, qz - self.qz0
        if 0 <= ix < self.nx and 0 <= jz < self.nz:
            return self.materials[jz][ix]
        return None

    def h(self, qx, qz):
        return self.H[qz - self.qz0][qx - self.qx0]

    def diagonal(self, ix, jz):
        """True: the quad splits along (0,0)-(1,1); False: along (1,0)-(0,1). The split whose two
        triangles are the same kind for the body (both floors or both walls, by the game's
        floor_max_degrees), so that a steep sliver never lies between two floors where they meet
        (a crack to a point query); then the one along the shorter rise."""
        key = self.__dict__.setdefault('_diag', {})
        if (ix, jz) not in key:
            H = self.H
            rise = (abs(H[jz][ix] - H[jz + 1][ix + 1]), abs(H[jz][ix + 1] - H[jz + 1][ix]))
            mixed = []
            for d in (True, False):
                kinds = {n[1] / math.sqrt(dot(n, n)) >= self.floor_cos for n in self.split_normals(ix, jz, d)}
                mixed.append(len(kinds) > 1)
            key[(ix, jz)] = (mixed[0], rise[0]) <= (mixed[1], rise[1])
        return key[(ix, jz)]

    def split_normals(self, ix, jz, diag):
        """The quad's two triangles' upward normals (unnormalised, area weighted) for a split."""
        s, H = self.s, self.H
        c = {(0, 0): H[jz][ix], (1, 0): H[jz][ix + 1], (0, 1): H[jz + 1][ix], (1, 1): H[jz + 1][ix + 1]}
        tris = (((0, 0), (1, 0), (1, 1)), ((0, 0), (1, 1), (0, 1))) if diag else \
            (((0, 0), (1, 0), (0, 1)), ((1, 0), (1, 1), (0, 1)))
        out = []
        for t in tris:
            p = [(u * s, c[(u, v)], v * s) for u, v in t]
            n = cross(sub(p[1], p[0]), sub(p[2], p[0]))
            out.append(n if n[1] > 0 else (-n[0], -n[1], -n[2]))
        return out

    def quad_normals(self, ix, jz):
        return self.split_normals(ix, jz, self.diagonal(ix, jz))

    def normals(self):
        """Per sample: the sum of the normals of the finest triangles around it (holes left out
        later: sampled from every quad of the field, so a seam's two sides agree)."""
        self.N = [[(0.0, 0.0, 0.0)] * (self.nx + 1) for _ in range(self.nz + 1)]
        for jz in range(self.nz):
            for ix in range(self.nx):
                if self.materials[jz][ix] is None:
                    continue
                n1, n2 = self.quad_normals(ix, jz)
                s = (n1[0] + n2[0], n1[1] + n2[1], n1[2] + n2[2])
                for dz in (0, 1):
                    for dx in (0, 1):
                        o = self.N[jz + dz][ix + dx]
                        self.N[jz + dz][ix + dx] = (o[0] + s[0], o[1] + s[1], o[2] + s[2])

    def normal(self, qx, qz):
        n = self.N[qz - self.qz0][qx - self.qx0]
        ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
        return (0.0, 1.0, 0.0) if ln == 0 else (n[0] / ln, n[1] / ln, n[2] / ln)

    # ---- merging quads

    def flat(self, x0, z0, w, d, tol):
        """Whether every sample of the w x d block at lattice (x0, z0) lies within tol of the
        bilinear patch of its corners, with the patch's twist (how far its two triangles can
        part from it) added."""
        c00, c10 = self.h(x0, z0), self.h(x0 + w, z0)
        c01, c11 = self.h(x0, z0 + d), self.h(x0 + w, z0 + d)
        twist = abs(c00 + c11 - c10 - c01) / 4
        if twist > tol:
            return False
        for dz in range(d + 1):
            v = dz / d
            a, b = c00 + (c01 - c00) * v, c10 + (c11 - c10) * v
            for dx in range(w + 1):
                if abs(self.h(x0 + dx, z0 + dz) - (a + (b - a) * dx / w)) + twist > tol:
                    return False
        return True

    def rects(self, tx0, tz0, tol):
        """The tile at lattice (tx0, tz0) as rectangles of quads [(qx, qz, w, d, material)]:
        greedily, row by row, each grown along x and then along z while its quads share a
        material and stay flat (within tol of one plane-like patch)."""
        n = self.tq
        taken = set()
        out = []
        for qz in range(tz0, tz0 + n):
            for qx in range(tx0, tx0 + n):
                if (qx, qz) in taken:
                    continue
                m = self.present(qx, qz)
                if m is None:
                    continue
                w = 1
                while (qx + w < tx0 + n and (qx + w, qz) not in taken and self.present(qx + w, qz) == m
                       and self.flat(qx, qz, w + 1, 1, tol)):
                    w += 1
                d = 1
                while (qz + d < tz0 + n and all((x, qz + d) not in taken and self.present(x, qz + d) == m
                                                for x in range(qx, qx + w))
                       and self.flat(qx, qz, w, d + 1, tol)):
                    d += 1
                for z in range(qz, qz + d):
                    for x in range(qx, qx + w):
                        taken.add((x, z))
                out.append((qx, qz, w, d, m))
        return out


def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def perimeter(x0, z0, w, d):
    """Lattice points around a w x d block, in order."""
    pts = [(x0 + k, z0) for k in range(w)]
    pts += [(x0 + w, z0 + k) for k in range(d)]
    pts += [(x0 + w - k, z0 + d) for k in range(w)]
    pts += [(x0, z0 + d - k) for k in range(d)]
    return pts


def rect_triangles(fld, rect, points):
    """A rectangle's triangles, each wound to face up (outward right-handed), as corners
    (world point, unit normal at it). With only its own four corners on its edges it is two
    triangles; with more (a neighbour's corners on its edges) it is a fan from its centre, so no
    corner of one face lies in the middle of another's edge."""
    x0, z0, w, d, _ = rect
    s = fld.s

    def corner(q):
        return ((q16(q[0] * s), fld.h(*q), q16(q[1] * s)), fld.normal(*q))

    ring = [p for p in perimeter(x0, z0, w, d) if p in points]
    inner_x = [p for p in ring if p[1] in (z0, z0 + d) and x0 < p[0] < x0 + w]     # on the x sides
    inner_z = [p for p in ring if p[0] in (x0, x0 + w) and z0 < p[1] < z0 + d]     # on the z sides
    if len(ring) > 4 and (not inner_x or not inner_z):
        # extra points on two opposite sides only: zip the two sides together (no centre, no
        # slivers from it); every triangle has two corners on one side and one on the other
        k = 0 if not inner_z else 1             # zip along x (the z = z0 and z0 + d sides) or along z
        lo = sorted((p for p in ring if p[1 - k] == (z0, x0)[k]), key=lambda p: p[k])
        hi = sorted((p for p in ring if p[1 - k] == (z0 + d, x0 + w)[k]), key=lambda p: p[k])
        tris = []
        i = j = 0
        while i < len(lo) - 1 or j < len(hi) - 1:
            if j == len(hi) - 1 or (i < len(lo) - 1 and lo[i + 1][k] <= hi[j + 1][k]):
                tris.append((lo[i], lo[i + 1], hi[j]))
                i += 1
            else:
                tris.append((lo[i], hi[j + 1], hi[j]))
                j += 1
        tris = [tuple(corner(q) for q in t) for t in tris]
    elif len(ring) == 4:
        c00, c10, c11, c01 = (x0, z0), (x0 + w, z0), (x0 + w, z0 + d), (x0, z0 + d)
        if w == d == 1:
            diag = fld.diagonal(x0 - fld.qx0, z0 - fld.qz0)
        else:
            diag = abs(fld.h(*c00) - fld.h(*c11)) <= abs(fld.h(*c10) - fld.h(*c01))
        tris = [(c00, c10, c11), (c00, c11, c01)] if diag else [(c00, c10, c01), (c10, c11, c01)]
        tris = [tuple(corner(q) for q in t) for t in tris]
    else:
        if w % 2 == 0 and d % 2 == 0:
            centre = corner((x0 + w // 2, z0 + d // 2))
        else:
            # between samples: on the patch of the corners (the rectangle is flat within tol)
            hs = [fld.h(x0, z0), fld.h(x0 + w, z0), fld.h(x0, z0 + d), fld.h(x0 + w, z0 + d)]
            a = (x0 * s, hs[0], z0 * s)
            n = unit(cross(sub((x0 * s, hs[3], (z0 + d) * s), a), sub(((x0 + w) * s, hs[1], z0 * s), a)))
            centre = ((q16((x0 + w / 2) * s), q16(sum(hs) / 4), q16((z0 + d / 2) * s)), n if n[1] > 0 else (-n[0], -n[1], -n[2]))
        tris = [(centre, corner(ring[k]), corner(ring[(k + 1) % len(ring)])) for k in range(len(ring))]
    out = []
    for t in tris:
        p = [c[0] for c in t]
        if cross(sub(p[1], p[0]), sub(p[2], p[0]))[1] < 0:
            t = (t[0], t[2], t[1])
        out.append(t)
    return out


# ---- native meshes

class MeshOut:
    """A cell-local native mesh being written: vertices deduplicated, palette swatch faces."""

    def __init__(self, palette, centre):
        self.mesh = meshlib.Mesh()
        self.index = {}
        self.palette, self.centre = palette, centre
        self.faces = 0
        self.materials = set()

    def vertex(self, p):
        key = (p[0] - self.centre[0], p[1], p[2] - self.centre[2])
        if key not in self.index:
            self.index[key] = self.mesh.vertex(*key)
        return self.index[key]

    def tri(self, pts, shades, material):
        """pts: world corners, wound outward right-handed; shades: 0-1 per corner."""
        entry = self.palette['by_material'][material]
        if entry['class'] == 'emissive':
            shades = (1, 1, 1)
        idx = [self.vertex(p) for p in pts]
        cols = [meshlib.rgb(*([max(0, min(255, round(128 * sh)))] * 3)) for sh in shades]
        uv = (entry['index'], self.palette['layout']['row'])
        # Mei's front faces are the reverse of the outward right-handed winding (assetkit.compiler).
        self.mesh.tri(list(reversed(idx)), list(reversed(cols)), [uv] * 3, 0,
                      slot=self.palette['layout']['slot'], four_bit=True, palette=entry['palette'])
        self.faces += 1
        self.materials.add(material)

    def pack(self):
        if len(self.mesh.verts) > 2048:
            raise WorldError('/terrain', 'A terrain piece has more than 2,048 vertices.')
        return self.mesh.pack()


def unit(n):
    ln = math.sqrt(dot(n, n))
    return (0.0, 1.0, 0.0) if ln == 0 else (n[0] / ln, n[1] / ln, n[2] / ln)


# ---- sweeps

def right_of(t):
    """The horizontal unit vector to the right of horizontal direction t (x, z) seen from above
    with +x right and +z forward."""
    return (t[1], -t[0])


class Sweep:
    def __init__(self, name, spec, ctx):
        self.name = name
        self.path = pointer('/paths', name) + '/sweep'
        sw = spec['sweep']
        prof = [tuple(p) for p in sw['profile']]
        for k in range(1, len(prof)):
            if prof[k] == prof[k - 1]:
                raise WorldError(f'{self.path}/profile/{k}', 'A profile point repeats the one before it.')
        self.profile = prof
        if ('material' in sw) == ('materials' in sw):
            raise WorldError(self.path + '/material', 'Give material, or materials (one per profile edge).')
        mats = [sw['material']] * (len(prof) - 1) if 'material' in sw else sw['materials']
        if len(mats) != len(prof) - 1:
            raise WorldError(self.path + '/materials', f'The profile has {len(prof) - 1} edges; give one material each.')
        for k, m in enumerate(mats):
            if m not in ctx.materials:
                raise WorldError(self.path + ('/material' if 'material' in sw else f'/materials/{k}'),
                                 f'No terrain material {m!r}.')
        self.materials = mats
        self.points = [tuple(float(c) for c in p) for p in spec['points']]
        self.closed = bool(spec.get('closed'))
        self.raised = bool(spec.get('raised'))
        self.ground = sw.get('ground', not self.raised)
        self.collision = sw.get('collision', True)
        self.caps = sw.get('caps', False)
        if self.caps and self.closed:
            raise WorldError(self.path + '/caps', 'A closed path has no ends to cap.')
        self.rise = sw['stairs']['rise'] if 'stairs' in sw else None
        pts = self.points + ([self.points[0]] if self.closed else [])
        self.segs = []
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            dx, dz = b[0] - a[0], b[2] - a[2]
            ln = math.hypot(dx, dz)
            if ln == 0:
                raise WorldError(f'{pointer("/paths", name)}/points/{(k + 1) % len(self.points)}',
                                 'A swept path\'s points differ seen from above: a sweep cannot go straight up.')
            self.segs.append((a, b, (dx / ln, dz / ln), ln))
        # The frame at each path point: the mitre of the segments meeting there.
        n = len(self.segs)
        self.frames = []
        for k in range(len(pts)):
            t_in = self.segs[k - 1][2] if (k > 0 or self.closed) else None
            t_out = self.segs[k][2] if k < n else (self.segs[0][2] if self.closed else None)
            if k == n and self.closed:
                self.frames.append(self.frames[0])
                continue
            if t_in is None or t_out is None:
                t = t_in or t_out
                self.frames.append((right_of(t), 1.0))
                continue
            m = (t_in[0] + t_out[0], t_in[1] + t_out[1])
            ml = math.hypot(*m)
            cos = (m[0] * t_out[0] + m[1] * t_out[1]) / ml if ml else 0.0
            if cos < MIN_MITRE_COS:
                raise WorldError(f'{pointer("/paths", name)}/points/{k % len(self.points)}',
                                 'A swept path turns more than 120 degrees here; add a point to round the corner.')
            r = right_of((m[0] / ml, m[1] / ml))
            self.frames.append((r, 1.0 / cos))

    def stations(self, size):
        """Per segment: [(t, y, frame)] along it, t in 0..1, with a riser where two stations
        share a t (a step). Cross-sections where the centre line crosses a cell edge."""
        out = []
        for k, (a, b, tdir, ln) in enumerate(self.segs):
            ts = {0.0, 1.0}
            for axis in (0, 2):
                lo, hi = sorted((a[axis], b[axis]))
                m = math.floor(lo / size) + 1
                while m * size < hi:
                    if b[axis] != a[axis]:
                        ts.add((m * size - a[axis]) / (b[axis] - a[axis]))
                    m += 1
            rise = self.rise
            dy = b[1] - a[1]
            runs = None
            if rise is not None and dy != 0:
                runs = math.ceil(abs(dy) / rise - 1e-9) + 1
                for r in range(1, runs):
                    ts.add(r / runs)
            seg = []
            mid = (right_of(tdir), 1.0)
            for t in sorted(ts):
                frame = self.frames[k] if t == 0 else self.frames[k + 1] if t == 1 else mid
                if runs is None:
                    seg.append((t, a[1] + dy * t, frame))
                    continue
                # run r covers t in [r / runs, (r + 1) / runs] at the r-th of runs equal heights
                # from a to b; between two runs a riser joins them
                r = t * runs
                rr = round(r)
                if 0 < rr < runs and abs(r - rr) < 1e-9:
                    seg.append((t, a[1] + dy * (rr - 1) / (runs - 1), frame))
                    seg.append((t, a[1] + dy * rr / (runs - 1), frame))
                else:
                    seg.append((t, a[1] + dy * min(runs - 1, math.floor(r + 1e-9)) / (runs - 1), frame))
            out.append(seg)
        return out


def sweep_section(sw, a, b, t, y, frame):
    """The cross-section's world points at t along segment a-b at height y."""
    x = a[0] + (b[0] - a[0]) * t
    z = a[2] + (b[2] - a[2]) * t
    (rx, rz), scale = frame
    return [(q16(x + px * rx * scale), q16(y + py), q16(z + px * rz * scale)) for px, py in sw.profile]


# ---- the whole terrain

@dataclass
class Context:
    base: object
    size: int
    paths: dict
    materials: dict
    files: list
    floor_cos: float = math.cos(math.radians(45))


def compile_terrain(w, base, size, cells, surface_of, warnings, overhang, floor_max_degrees=45.0):
    """cells: (i, j) -> anything (the cells that exist). Returns a Result; pieces carry meshes
    with provisional palette colours (assign_palette's layout), which world.py moves into each
    region's palettes as it moves an asset's."""
    from . import pack as P
    terrain = w.get('terrain')
    sweeps_spec = {n: p for n, p in w.get('paths', {}).items() if 'sweep' in p}
    if terrain is None and not sweeps_spec:
        return None
    if terrain is None:
        raise WorldError('/paths', 'A path with a sweep needs terrain materials: declare them in terrain.materials.')
    materials = terrain['materials']
    if not materials:
        raise WorldError('/terrain/materials', 'Declare at least one terrain material.')
    ctx = Context(base, size, w.get("paths", {}), materials, [], math.cos(math.radians(floor_max_degrees)))
    lighting = dict({'mode': 'vertical'}, **terrain.get('lighting', {}))
    if lighting['mode'] == 'vertical' and 'direction' in lighting:
        raise WorldError('/terrain/lighting/direction', 'Vertical lighting shades by the normal\'s Y only. Remove '
                         'direction, or use mode "directional".')
    if lighting['mode'] == 'directional' and dot(lighting.get('direction', [-0.4, 0.85, -0.35]),
                                                 lighting.get('direction', [-0.4, 0.85, -0.35])) == 0:
        raise WorldError('/terrain/lighting/direction', 'The light\'s direction is not zero.')
    shade_of = shading(lighting)
    half = size / 2

    fields = []
    for name, spec in terrain.get('fields', {}).items():
        fields.append(Field(name, spec, ctx))
    for a in range(len(fields)):
        for b in range(a + 1, len(fields)):
            fa, fb = fields[a], fields[b]
            ax0, az0, ax1, az1 = fa.qx0 * fa.s, fa.qz0 * fa.s, (fa.qx0 + fa.nx) * fa.s, (fa.qz0 + fa.nz) * fa.s
            bx0, bz0, bx1, bz1 = fb.qx0 * fb.s, fb.qz0 * fb.s, (fb.qx0 + fb.nx) * fb.s, (fb.qz0 + fb.nz) * fb.s
            if ax0 <= bx1 and bx0 <= ax1 and az0 <= bz1 and bz0 <= az1:
                raise WorldError(fb.path, f'Fields {fa.name!r} and {fb.name!r} overlap or touch; fields keep apart '
                                 '(make one field, or leave a gap).')
    sweeps = [Sweep(n, p, ctx) for n, p in sweeps_spec.items()]

    used = set()
    for f in fields:
        for row in f.materials:
            used.update(m for m in row if m is not None)
    for sw in sweeps:
        used.update(sw.materials)
    for name in materials:
        if name not in used:
            warnings.append({'code': 'terrain_material_unused', 'material': name,
                             'message': 'No field or sweep draws this terrain material.'})
    faces = [type('F', (), {'material': m})() for m in sorted(used)]
    mats = {m: dict(materials[m], palette=True) for m in used}
    palette = assign_palette(type('M', (), {'faces': faces})(), mats, {}) if used else None

    pieces, collision = {}, {}
    report = {'fields': {}, 'sweeps': {}, 'lighting': lighting['mode']}

    def centre_of(key):
        return (key[0] * size + half, 0.0, key[1] * size + half)

    # ---- fields: tiles, their rectangles at each level, the points every tile edge keeps
    for f in fields:
        spec = f.spec
        lod = spec.get('lod')
        tols = [spec.get('tolerance', DEFAULT_TOLERANCE)]
        if lod:
            tols.append(lod.get('tolerance', DEFAULT_LOD_TOLERANCE))
            if tols[1] <= tols[0]:
                raise WorldError(f.path + '/lod/tolerance', 'The coarse level\'s tolerance is larger than the field\'s.')
        tq = f.tq
        tiles = {}
        outside = 0
        for tz in range(math.floor(f.qz0 / tq), math.floor((f.qz0 + f.nz - 1) / tq) + 1):
            for tx in range(math.floor(f.qx0 / tq), math.floor((f.qx0 + f.nx - 1) / tq) + 1):
                cell = (math.floor(tx * tq * f.s / size), math.floor(tz * tq * f.s / size))
                if cell not in cells:
                    if any(f.present(qx, qz) for qz in range(tz * tq, tz * tq + tq) for qx in range(tx * tq, tx * tq + tq)):
                        outside += 1
                    continue
                levels = [f.rects(tx * tq, tz * tq, t) for t in tols]
                if levels[0]:
                    tiles[(tx, tz)] = levels
        if outside:
            warnings.append({'code': 'terrain_outside_cells', 'field': f.name, 'tiles': outside,
                             'message': 'Parts of the field lie over no cell of the world; they are left out.'})

        def rect_corners(r):
            x0, z0, w, d, _ = r
            return ((x0, z0), (x0 + w, z0), (x0, z0 + d), (x0 + w, z0 + d))

        corners = {}            # tile -> every corner of its rectangles at any level
        for key, levels in tiles.items():
            pts = set()
            for lv in levels:
                for r in lv:
                    pts.update(rect_corners(r))
            corners[key] = pts
        frep = {'spacing': f.s, 'samples': (f.nx + 1) * (f.nz + 1), 'quads': f.nx * f.nz,
                'holes': sum(m is None for row in f.materials for m in row),
                'heights': [min(min(r) for r in f.H), max(max(r) for r in f.H)],
                'tile': tq * f.s, 'tiles': len(tiles), 'triangles': [0] * len(tols), 'vertices': 0,
                'materials': {}, 'cells': {}}
        for (tx, tz), levels in sorted(tiles.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            x0, z0 = tx * tq, tz * tq
            # the tile's own corners, and those of its four neighbours on the shared edges
            edge = set()
            for (dx, dz) in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                other = corners.get((tx + dx, tz + dz))
                if not other:
                    continue
                for p in other:
                    if (dx == -1 and p[0] == x0) or (dx == 1 and p[0] == x0 + tq) or \
                            (dz == -1 and p[1] == z0) or (dz == 1 and p[1] == z0 + tq):
                        if x0 <= p[0] <= x0 + tq and z0 <= p[1] <= z0 + tq:
                            edge.add(p)
            own = corners[(tx, tz)]
            border = {p for p in own if p[0] in (x0, x0 + tq) or p[1] in (z0, z0 + tq)}
            cell = (math.floor(x0 * f.s / size), math.floor(z0 * f.s / size))
            centre = centre_of(cell)
            meshes = []
            for li, lv in enumerate(levels):
                points = edge | border
                for r in lv:
                    points.update(rect_corners(r))
                out = MeshOut(palette, centre)
                for rect in lv:
                    material = rect[4]
                    for t in rect_triangles(f, rect, points):
                        world = [c[0] for c in t]
                        if spec.get('shading', 'smooth') == 'smooth':
                            shades = [shade_of(c[1]) for c in t]
                        else:
                            shades = [shade_of(unit(cross(sub(world[1], world[0]), sub(world[2], world[0]))))] * 3
                        out.tri(world, shades, material)
                        if li == 0:
                            frep['materials'][material] = frep['materials'].get(material, 0) + 1
                            if spec.get('collision', True):
                                a, b, c = world
                                collision.setdefault(cell, []).append(
                                    P.Tri(c, b, a, surface=surface_of(materials[material].get('tag')), tag=TAG_FIELD))
                meshes.append(out)
                frep['triangles'][li] += out.faces
            frep['vertices'] += len(meshes[0].mesh.verts)
            cr = frep['cells'].setdefault(f'{cell[0]},{cell[1]}', [0] * len(tols))
            for li, m in enumerate(meshes):
                cr[li] += m.faces
            piece = Piece('field', f.name, meshes[0].pack(), meshes[0].faces, ground=spec.get('ground', True),
                          tag=TAG_FIELD, materials=set().union(*(m.materials for m in meshes)),
                          level_faces=[m.faces for m in meshes])
            if lod and meshes[1].faces < meshes[0].faces:
                piece.levels = [(lod['distance'], meshes[1].pack())]
                piece.band = lod.get('band', DEFAULT_LOD_BAND)
            pieces.setdefault(cell, []).append(piece)
        frep['full_triangles'] = 2 * (f.nx * f.nz - frep['holes'])
        report['fields'][f.name] = frep

    # ---- sweeps: strips between cross-sections, risers and caps, each in the cell of its middle
    for sw in sweeps:
        outs = {}
        tris_by_cell = {}
        srep = {'path': sw.name, 'profile_edges': len(sw.profile) - 1, 'cross_sections': 0, 'steps': 0,
                'triangles': 0, 'cells': {}, 'ground': sw.ground}

        def cell_of(x, z):
            return (math.floor(x / size), math.floor(z / size))

        def emit(key, tri, material, normal_hint):
            if key not in cells:
                srep.setdefault('outside', 0)
                srep['outside'] += 1
                return
            lo_x, lo_z = key[0] * size, key[1] * size
            for p in tri:
                if not (lo_x - overhang <= p[0] <= lo_x + size + overhang and lo_z - overhang <= p[2] <= lo_z + size + overhang):
                    raise WorldError(sw.path + '/profile', f'The sweep reaches {p} from cell {list(key)}, past the '
                                     f'world\'s overhang ({overhang}): narrow the profile or raise overhang.')
            n = cross(sub(tri[1], tri[0]), sub(tri[2], tri[0]))
            if dot(n, n) == 0:
                return
            if dot(n, normal_hint) < 0:
                tri = (tri[0], tri[2], tri[1])
                n = (-n[0], -n[1], -n[2])
            if key not in outs:
                outs[key] = MeshOut(palette, centre_of(key))
            outs[key].tri(tri, [shade_of(unit(n))] * 3, material)
            if sw.collision:
                a, b, c = tri
                tris_by_cell.setdefault(key, []).append(P.Tri(c, b, a, surface=surface_of(materials[material].get('tag')),
                                                              tag=TAG_SWEEP))

        def quad(key, p, material, hint):
            emit(key, (p[0], p[1], p[2]), material, hint)
            emit(key, (p[0], p[2], p[3]), material, hint)

        prof = sw.profile
        stations = sw.stations(size)
        for k, seg in enumerate(stations):
            a, b, tdir, ln = sw.segs[k]
            prev = None
            for t, y, frame in seg:
                cs = sweep_section(sw, a, b, t, y, frame)
                srep['cross_sections'] += 1
                if prev is not None:
                    pt, py, pcs, pframe = prev
                    x = a[0] + (b[0] - a[0]) * (pt + t) / 2
                    z = a[2] + (b[2] - a[2]) * (pt + t) / 2
                    key = cell_of(x, z)
                    if t == pt:             # a riser: the profile at two heights
                        srep['steps'] += 1
                        up = 1 if y > py else -1
                        hint = (-tdir[0] * up, 0.0, -tdir[1] * up)
                        for e in range(len(prof) - 1):
                            quad(key, (pcs[e], pcs[e + 1], cs[e + 1], cs[e]), sw.materials[e], hint)
                    else:
                        r = right_of(tdir)
                        for e in range(len(prof) - 1):
                            dx, dy = prof[e + 1][0] - prof[e][0], prof[e + 1][1] - prof[e][1]
                            hint = (-dy * r[0], dx, -dy * r[1])
                            quad(key, (pcs[e], pcs[e + 1], cs[e + 1], cs[e]), sw.materials[e], hint)
                prev = (t, y, cs, frame)
        if sw.caps and len(prof) >= 3:
            # the start faces back along the path, the end forward; each goes to the cell the
            # path leaves from or arrives in (an end on a cell edge belongs to the cell it is in)
            for k, station, sign in ((0, stations[0][0], -1), (len(stations) - 1, stations[-1][-1], 1)):
                a, b, tdir, ln = sw.segs[k]
                t, y, frame = station
                cs = sweep_section(sw, a, b, t, y, frame)
                x, z = a[0] + (b[0] - a[0]) * t, a[2] + (b[2] - a[2]) * t
                key = cell_of(x - tdir[0] * 1e-6 * sign, z - tdir[1] * 1e-6 * sign)
                hint = (tdir[0] * sign, 0.0, tdir[1] * sign)
                for e in range(1, len(cs) - 1):
                    emit(key, (cs[0], cs[e], cs[e + 1]), sw.materials[0], hint)
        if srep.get('outside'):
            warnings.append({'code': 'sweep_outside_cells', 'path': sw.name, 'triangles': srep['outside'],
                             'message': 'Parts of the sweep lie over no cell of the world; they are left out.'})
        for key in sorted(outs, key=lambda c: (c[1], c[0])):
            out = outs[key]
            pieces.setdefault(key, []).append(Piece('sweep', sw.name, out.pack(), out.faces, ground=sw.ground,
                                                    tag=TAG_SWEEP, materials=set(out.materials),
                                                    level_faces=[out.faces]))
            srep['triangles'] += out.faces
            srep['cells'][f'{key[0]},{key[1]}'] = out.faces
            collision.setdefault(key, []).extend(tris_by_cell.get(key, []))
        report['sweeps'][sw.name] = srep

    if ctx.files:
        report['files'] = [{'file': f, 'sha256': h} for f, h in ctx.files]
    return Result(pieces, collision, palette, report, [f for f, _ in ctx.files], {f.name: f for f in fields})
