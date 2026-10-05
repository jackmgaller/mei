"""Far ground: coarse levels of a terrain tile resampled from its own mesh (WORLDKIT.md, "Levels of
detail", far ground).

    meshes = far_levels(mesh0, [8, 16])     # one native mesh per grid (or None), coarsest last

A field's tiles have a level 0 and, with the field's `lod`, a coarse level that keeps every point
its edges share with its neighbours, so that tiles at different levels meet; on a mountain that
leaves a coarse tile with tens of triangles, too many for ground a hundred metres away. A far level
is a regular grid over the tile (two triangles per `grid`-unit square) whose heights are the tile's own
level 0 under each grid point (its top, where a cliff stands there). Each quad takes the face of
level 0 under its centre: its flags, texture and palette, and its colours and texture coordinates
carried over affinely to the quad's corners, so it draws with the same materials and shading. Its
edges do not keep the neighbours' points, so where its straight edge stands above the ground beside
it a crack could open; a skirt (a quad hanging down from that stretch of edge, far enough to close
it, facing out of the tile) is added on each grid segment of the tile's border that needs one.

Nothing here knows about terrain: it reads and writes native meshes (docs/LANGUAGE.md, "Mesh
format") in the tile's own coordinates.
"""
import math
import struct

FACE = struct.Struct('<BBBB4H4I4H')
QUAD = 4
GOURAUD = 1
EPS = 1e-6
SKIRT_MIN = 0.05            # a straight edge this close above the finer ground needs no skirt (units)
SKIRT_EXTRA = 0.1           # a skirt reaches this much below the deepest point it covers


def _decode(mesh):
    nv, nf, vo, fo, wo = struct.unpack_from('<HHIII', mesh)
    verts = [tuple(c / 65536 for c in struct.unpack_from('<3i', mesh, vo + 16 * k)) for k in range(nv)]
    faces = [FACE.unpack_from(mesh, fo + 36 * k) for k in range(nf)]
    table = mesh[wo:] if wo else b''
    return verts, faces, table


def _area(p):
    """The signed area of a triangle's xz projection; (b - a) x (c - a) has y = -area."""
    return (p[1][0] - p[0][0]) * (p[2][2] - p[0][2]) - (p[2][0] - p[0][0]) * (p[1][2] - p[0][2])


class _Surface:
    """A mesh's faces as triangles over their xz projection (upright faces left out)."""

    def __init__(self, verts, faces):
        self.tris = []
        for f in faces:
            for c in ([(0, 1, 2), (1, 2, 3)] if f[0] & QUAD else [(0, 1, 2)]):
                p = [verts[f[4 + k]] for k in c]
                a = _area(p)
                if abs(a) > EPS:
                    self.tris.append((p, f, c, a))

    @staticmethod
    def bary(t, x, z):
        p, _, _, area = t
        l1 = ((x - p[0][0]) * (p[2][2] - p[0][2]) - (p[2][0] - p[0][0]) * (z - p[0][2])) / area
        l2 = ((p[1][0] - p[0][0]) * (z - p[0][2]) - (x - p[0][0]) * (p[1][2] - p[0][2])) / area
        return 1 - l1 - l2, l1, l2

    def hits(self, x, z):
        out = []
        for t in self.tris:
            b = self.bary(t, x, z)
            if min(b) >= -1e-4:
                p = t[0]
                out.append((b[0] * p[0][1] + b[1] * p[1][1] + b[2] * p[2][1], t))
        return out

    def top(self, x, z):
        """(height, triangle) of the highest face over (x, z), or None."""
        h = self.hits(x, z)
        return max(h, key=lambda e: e[0]) if h else None

    def low(self, x, z):
        h = self.hits(x, z)
        return min(e[0] for e in h) if h else None


def _carry(t, x, z):
    """The colour and texture coordinate triangle t's face gives at (x, z), carried affinely
    (outside the triangle too): ((r, g, b), (u, v))."""
    _, f, c, _ = t
    b = _Surface.bary(t, x, z)
    rgb = [sum(w * ((f[8 + k] >> s) & 255) for w, k in zip(b, c)) for s in (0, 8, 16)]
    uv = [sum(w * ((f[12 + k] >> s) & 255) for w, k in zip(b, c)) for s in (0, 8)]
    return rgb, uv


def _clamp8(v):
    return max(0, min(255, round(v)))


def far_levels(mesh0, grids, skirt_min=SKIRT_MIN, skirted=None):
    """Far levels of the tile whose level 0 is mesh0, one per grid (units, finest first): native
    meshes in the tile's coordinates, or None where the grid does not cover the tile's ground.
    skirted(a, b), when given, says whether the border segment from point a to b may have a skirt
    (a stand-in leaves out the skirts between its own tiles, which meet exactly)."""
    verts, faces, table = _decode(mesh0)
    surf = _Surface(verts, faces)
    if not surf.tris:
        return [None] * len(grids)
    xs, zs = [v[0] for v in verts], [v[2] for v in verts]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    # Mei's front faces turn the other way from the right-handed outward normal; read the turn from
    # the tile's largest upward face rather than assume it: k is the sign of (b - a) x (c - a) . n
    big = max(surf.tris, key=lambda t: abs(t[3]))
    k = -1 if big[3] > 0 else 1
    levels, finer = [], []
    for grid in grids:
        nx, nz = max(1, round((x1 - x0) / grid)), max(1, round((z1 - z0) / grid))
        gx = [x0 + (x1 - x0) * a / nx for a in range(nx + 1)]
        gz = [z0 + (z1 - z0) * b / nz for b in range(nz + 1)]
        tops = {(a, b): surf.top(gx[a], gz[b]) for a in range(nx + 1) for b in range(nz + 1)}
        if any(v is None for v in tops.values()):
            levels.append(None)
            continue
        out_v, out_f, index = [], [], {}

        def vertex(q):
            key = tuple(round(c, 4) for c in q)
            if key not in index:
                index[key] = len(out_v)
                out_v.append(key)
            return index[key]

        def face(q, normal, t):
            """A quad (strip order: 0-1-2, 1-2-3, flat) or triangle facing along normal, drawn as
            t's face is."""
            u = [q[1][i] - q[0][i] for i in range(3)]
            v = [q[2][i] - q[0][i] for i in range(3)]
            c = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            if (c[0] * normal[0] + c[1] * normal[1] + c[2] * normal[2]) * k < 0:
                q = [q[1], q[0]] + ([q[3], q[2]] if len(q) == 4 else [q[2]])
            f = t[1]
            carried = [_carry(t, p[0], p[2]) for p in q]
            cols = [_clamp8(r) | _clamp8(g) << 8 | _clamp8(b) << 16 for (r, g, b), _ in carried]
            uvs = [_clamp8(uv[0]) | _clamp8(uv[1]) << 8 for _, uv in carried]
            flags = f[0] & ~QUAD | (QUAD if len(q) == 4 else 0)
            flags = flags | GOURAUD if len(set(cols)) > 1 else flags & ~GOURAUD
            n = len(q)
            out_f.append(FACE.pack(flags, f[1], f[2], f[3], *[vertex(p) for p in q] + [0] * (4 - n),
                                   *cols + [cols[-1]] * (4 - n), *uvs + [uvs[-1]] * (4 - n)))

        def corner(a, b):
            return (gx[a], tops[(a, b)][0], gz[b])

        for b in range(nz):
            for a in range(nx):
                mid = surf.top((gx[a] + gx[a + 1]) / 2, (gz[b] + gz[b + 1]) / 2)
                src = mid or tops[(a, b)]
                p00, p10, p01, p11 = corner(a, b), corner(a + 1, b), corner(a, b + 1), corner(a + 1, b + 1)
                # two triangles (a square's corners are seldom flat: a twisted quad would be drawn
                # and judged by its first triangle's facing), split along the diagonal whose middle
                # lies nearer the ground under the square's centre
                if mid is None or abs((p00[1] + p11[1]) / 2 - mid[0]) <= abs((p10[1] + p01[1]) / 2 - mid[0]):
                    tris = [(p00, p10, p11), (p00, p11, p01)]
                else:
                    tris = [(p00, p10, p01), (p10, p11, p01)]
                for tri in tris:
                    face(list(tri), (0, 1, 0), src[1])
        # skirts: each grid segment of the border whose straight edge stands above the finer
        # ground there (level 0, and the finer far levels' edges) by more than skirt_min
        segs = [((0, b), (0, b + 1)) for b in range(nz)] + [((nx, b), (nx, b + 1)) for b in range(nz)] + \
               [((a, 0), (a + 1, 0)) for a in range(nx)] + [((a, nz), (a + 1, nz)) for a in range(nx)]
        edges = []
        for s0, s1 in segs:
            A, B = corner(*s0), corner(*s1)
            edges.append((A, B))
            n = max(2, int(math.dist((A[0], A[2]), (B[0], B[2])) / 0.5))
            deepest = 0.0
            for m in range(n + 1):
                t = m / n
                x, z = A[0] + (B[0] - A[0]) * t, A[2] + (B[2] - A[2]) * t
                ys = [y for y in [surf.low(x, z)] + [fn(x, z) for fn in finer] if y is not None]
                if ys:
                    deepest = max(deepest, A[1] + (B[1] - A[1]) * t - min(ys))
            if deepest <= skirt_min or (skirted is not None and not skirted(A, B)):
                continue
            drop = deepest + SKIRT_EXTRA
            mx, mz = (A[0] + B[0]) / 2, (A[2] + B[2]) / 2
            out = (mx - (x0 + x1) / 2, 0.0, mz - (z0 + z1) / 2)
            out = (out[0] if s0[0] == s1[0] else 0.0, 0.0, out[2] if s0[1] == s1[1] else 0.0)
            src = surf.top(mx - 0.01 * out[0], mz - 0.01 * out[2]) or tops[s0]
            face([(A[0], A[1] - drop, A[2]), (B[0], B[1] - drop, B[2]), A, B], out, src[1])

        def line(x, z, edges=edges):
            for A, B in edges:
                dx, dz = B[0] - A[0], B[2] - A[2]
                L2 = dx * dx + dz * dz
                t = ((x - A[0]) * dx + (z - A[2]) * dz) / L2
                if -1e-6 <= t <= 1 + 1e-6 and abs((x - A[0]) * dz - (z - A[2]) * dx) < 1e-4 * math.sqrt(L2):
                    return A[1] + (B[1] - A[1]) * t
            return None
        finer.append(line)
        if len(out_v) > 2048:
            levels.append(None)
            continue
        fo = 16 + 16 * len(out_v)
        head = struct.pack('<HHIII', len(out_v), len(out_f), 16, fo, fo + 36 * len(out_f) if table else 0)
        body = b''.join(struct.pack('<4i', *(round(c * 65536) for c in v), 65536) for v in out_v)
        levels.append(head + body + b''.join(out_f) + table)
    return levels
