"""A small polygon builder for the Prism Wedge recipes.

Faces are planar polygons (or triangles) with a material and a tag. Faces can be cut by linear
functions (stripes, decal regions, holes for recesses); `mesh_node` welds the vertices, inserts
every vertex that lies on another face's edge into that edge (so no T-junctions open), and
triangulates each polygon itself, so collinear points never reach the kit.
"""
import math

EPS = 1e-10


def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def length(a): return math.sqrt(dot(a, a))
def unit(a):
    n = length(a)
    return (a[0] / n, a[1] / n, a[2] / n)


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return tuple(n)


def centroid(pts):
    return tuple(sum(p[k] for p in pts) / len(pts) for k in range(3))


def planar(pts, tol=1e-9):
    if len(pts) == 3:
        return True
    n = unit(newell(pts))
    d = dot(n, pts[0])
    return all(abs(dot(n, p) - d) < tol for p in pts)


class Face:
    def __init__(self, pts, mat, tag=None):
        self.pts, self.mat, self.tag = list(pts), mat, tag


class Builder:
    def __init__(self):
        self.faces = []
        self.uv = None  # optional function(point, face) -> (u, v) for textured faces

    def add(self, pts, mat, out=None, tag=None):
        pts = list(pts)
        if out is not None and dot(newell(pts), out) < 0:
            pts.reverse()
        if not planar(pts):
            c = centroid(pts)
            if len(pts) == 4:
                # nonplanar quad: two triangles on the shorter diagonal
                a, b, cc, d = pts
                if length(sub(cc, a)) <= length(sub(d, b)):
                    tris = [(a, b, cc), (a, cc, d)]
                else:
                    tris = [(a, b, d), (b, cc, d)]
                for t in tris:
                    self.faces.append(Face(t, mat, tag))
                return
            raise ValueError(f'nonplanar polygon of {len(pts)} points ({mat}, {tag})')
        self.faces.append(Face(pts, mat, tag))

    # ---- solids -------------------------------------------------------------------------
    def loft(self, rings, mats, axis, caps=(True, True), cap_mats=None, tags=None):
        """Bands between consecutive rings (same count, corresponding), outward by the ring's
        own winding; caps facing -axis (first) and +axis (last)."""
        n = unit(newell(rings[0]))
        for k in range(len(rings) - 1):
            a, b = rings[k], rings[k + 1]
            for i in range(len(a)):
                j = (i + 1) % len(a)
                e = sub(a[j], a[i])
                out = cross(e, n)
                if length(out) < 1e-12:
                    out = sub(centroid([a[i], a[j], b[i], b[j]]), centroid(a))
                quad = [a[i], a[j], b[j], b[i]]
                quad = dedup(quad)
                if len(quad) < 3:
                    continue
                self.add(quad, mats[k] if isinstance(mats, (list, tuple)) else mats, out=out,
                         tag=tags[k] if tags else None)
        cm = cap_mats or (mats if isinstance(mats, str) else mats[0], mats if isinstance(mats, str) else mats[-1])
        if caps[0]:
            self.add(rings[0], cm[0], out=mul(axis, -1))
        if caps[1]:
            self.add(rings[-1], cm[1], out=axis)

    def prism(self, ring, offset, side, cap_a=None, cap_b=None):
        self.loft([ring, [add(p, offset) for p in ring]], [side], unit(offset),
                  cap_mats=(cap_a or side, cap_b or side))

    # ---- cutting ------------------------------------------------------------------------
    def cut(self, fn, c, select=lambda f: True):
        out = []
        for f in self.faces:
            if not select(f):
                out.append(f)
                continue
            neg, pos = split(f.pts, fn, c)
            for piece in (neg, pos):
                if piece:
                    out.append(Face(piece, f.mat, f.tag))
        self.faces = out

    def region(self, lines, select, action):
        """lines: [(fn, c)], inside is fn(p) <= c for every line. action(face) returns the
        face to keep (with a new material, say) or None to remove it (a hole)."""
        out, inside = [], []
        for f in self.faces:
            if not select(f):
                out.append(f)
                continue
            cur = f.pts
            for fn, c in lines:
                neg, pos = split(cur, fn, c)
                if pos:
                    out.append(Face(pos, f.mat, f.tag))
                cur = neg
                if not cur:
                    break
            if cur:
                kept = action(Face(cur, f.mat, f.tag))
                if kept is not None:
                    out.append(kept)
                inside.append(Face(cur, f.mat, f.tag))
        self.faces = out
        return inside

    def recess(self, center, U, V, N, outline, depth, wall_mat, floor_mat, select):
        """Cut the convex outline (u, v in the U, V frame at center; N the surface's outward
        normal) out of the selected faces and line the hole with walls and a floor."""
        corners = [add(center, add(mul(U, u), mul(V, v))) for u, v in outline]
        cc = centroid(corners)
        lines = []
        for i in range(len(corners)):
            a, b = corners[i], corners[(i + 1) % len(corners)]
            e = sub(b, a)
            o = cross(e, N)
            if dot(o, sub(a, cc)) < 0:
                o = mul(o, -1)
            o = unit(o)
            lines.append(((lambda p, o=o: dot(o, p)), dot(o, a)))
        self.region(lines, select, lambda f: None)
        floor = [sub(p, mul(N, depth)) for p in corners]
        for i in range(len(corners)):
            j = (i + 1) % len(corners)
            mid = centroid([corners[i], corners[j]])
            self.add([corners[i], corners[j], floor[j], floor[i]], wall_mat, out=sub(cc, mid))
        self.add(floor, floor_mat, out=N)


def dedup(pts):
    out = []
    for p in pts:
        if not out or length(sub(p, out[-1])) > 1e-9:
            out.append(p)
    while len(out) > 1 and length(sub(out[0], out[-1])) <= 1e-9:
        out.pop()
    return out


def interp(a, da, b, db):
    # canonical order so two faces sharing the edge get the same point
    if b < a:
        a, da, b, db = b, db, a, da
    t = da / (da - db)
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def split(pts, fn, c):
    d = [fn(p) - c for p in pts]
    if all(x >= -EPS for x in d):
        return None, pts
    if all(x <= EPS for x in d):
        return pts, None
    neg, pos = [], []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        da, db = d[i], d[(i + 1) % n]
        if da <= EPS:
            neg.append(a)
        if da >= -EPS:
            pos.append(a)
        if (da < -EPS and db > EPS) or (da > EPS and db < -EPS):
            p = interp(a, da, b, db)
            neg.append(p)
            pos.append(p)
    neg, pos = dedup(neg), dedup(pos)
    return (neg if len(neg) >= 3 else None), (pos if len(pos) >= 3 else None)


# ---- output -----------------------------------------------------------------------------
def _key(p):
    return tuple(round(v, 7) + 0.0 for v in p)


def _triangulate(poly, P, normal):
    """Ear clipping in the polygon's plane; collinear points are kept, never made ears."""
    ax = max(range(3), key=lambda k: abs(normal[k]))
    i0, i1 = (ax + 1) % 3, (ax + 2) % 3
    if normal[ax] < 0:
        i0, i1 = i1, i0
    Q = {v: (P[v][i0], P[v][i1]) for v in poly}

    def cr(a, b, c):
        return (Q[b][0] - Q[a][0]) * (Q[c][1] - Q[a][1]) - (Q[b][1] - Q[a][1]) * (Q[c][0] - Q[a][0])

    def side(a, b, v):
        """Signed distance of v from the line a-b (left positive)."""
        L = math.hypot(Q[b][0] - Q[a][0], Q[b][1] - Q[a][1])
        return cr(a, b, v) / L

    TOL = 1e-6  # metres: a vertex this close to a line counts as on it

    V = list(poly)
    tris = []
    guard = 0
    while len(V) > 3:
        guard += 1
        if guard > 10000:
            raise ValueError('triangulation failed')
        found = False
        for i in range(len(V)):
            a, b, c = V[i - 1], V[i], V[(i + 1) % len(V)]
            if side(a, c, b) > -TOL:   # reflex or (nearly) collinear: not an ear
                continue
            blocked = False
            for v in V:
                if v in (a, b, c):
                    continue
                if Q[v] == Q[a] or Q[v] == Q[b] or Q[v] == Q[c]:
                    continue
                if side(a, b, v) >= -TOL and side(b, c, v) >= -TOL and side(c, a, v) >= -TOL:
                    blocked = True
                    break
            if blocked:
                continue
            tris.append((a, b, c))
            V.pop(i)
            found = True
            break
        if not found:
            raise ValueError(f'no ear in polygon {[P[v] for v in V]}')
    if abs(side(V[0], V[2], V[1])) <= TOL:
        raise ValueError('degenerate last triangle')
    tris.append(tuple(V))
    return tris


def mesh_node(node_id, b, uv=None):
    """Weld, remove T-junctions, triangulate. uv: function(point) -> [u, v] for every vertex
    (only textured faces use it)."""
    P, index = [], {}

    def idx(p):
        k = _key(p)
        if k not in index:
            index[k] = len(P)
            P.append(k)
        return index[k]

    polys = []
    for f in b.faces:
        ids = []
        for p in f.pts:
            i = idx(p)
            if not ids or ids[-1] != i:
                ids.append(i)
        while len(ids) > 1 and ids[0] == ids[-1]:
            ids.pop()
        if len(ids) >= 3:
            polys.append((ids, f.mat, newell(f.pts)))
    # insert vertices lying inside other faces' edges
    out_faces, mats = [], []
    for ids, mat, normal in polys:
        boundary = []
        for a, bb in zip(ids, ids[1:] + ids[:1]):
            A, B = P[a], P[bb]
            d = sub(B, A)
            L2 = dot(d, d)
            boundary.append(a)
            on = []
            for v, X in enumerate(P):
                if v in (a, bb):
                    continue
                if min(A[0], B[0]) - 1e-7 > X[0] or X[0] > max(A[0], B[0]) + 1e-7:
                    continue
                if min(A[1], B[1]) - 1e-7 > X[1] or X[1] > max(A[1], B[1]) + 1e-7:
                    continue
                if min(A[2], B[2]) - 1e-7 > X[2] or X[2] > max(A[2], B[2]) + 1e-7:
                    continue
                t = dot(sub(X, A), d) / L2
                if 1e-6 < t < 1 - 1e-6:
                    q = add(A, mul(d, t))
                    if length(sub(X, q)) < 2e-7:
                        on.append((t, v))
            boundary.extend(v for t, v in sorted(on))
        for tri in _triangulate(boundary, P, normal):
            n = cross(sub(P[tri[1]], P[tri[0]]), sub(P[tri[2]], P[tri[0]]))
            if dot(n, normal) < 0:
                tri = (tri[0], tri[2], tri[1])
            out_faces.append(list(tri))
            mats.append(mat)
    node = {'id': node_id, 'op': 'mesh', 'vertices': [list(p) for p in P], 'faces': out_faces,
            'face_materials': mats}
    if uv:
        node['uvs'] = [[round(min(1.0, max(0.0, c)), 6) for c in uv(p)] for p in P]
    return node


def inset(poly2, d):
    """Offset a simple 2D polygon inward by d (miter joins)."""
    area = sum(poly2[i][0] * poly2[(i + 1) % len(poly2)][1] - poly2[(i + 1) % len(poly2)][0] * poly2[i][1]
               for i in range(len(poly2)))
    s = 1 if area > 0 else -1  # CCW: inward is the left normal
    out = []
    n = len(poly2)
    for i in range(n):
        p0, p1, p2 = poly2[i - 1], poly2[i], poly2[(i + 1) % n]

        def nrm(a, b):
            ex, ey = b[0] - a[0], b[1] - a[1]
            L = math.hypot(ex, ey)
            return (-ey / L * s, ex / L * s)
        n1, n2 = nrm(p0, p1), nrm(p1, p2)
        k = 1 + n1[0] * n2[0] + n1[1] * n2[1]
        out.append((p1[0] + d * (n1[0] + n2[0]) / k, p1[1] + d * (n1[1] + n2[1]) / k))
    return out
