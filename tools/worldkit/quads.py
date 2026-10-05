"""Pairs a native mesh's triangles into quads (WORLDKIT.md, "Quads").

    mesh = pair(mesh)       # the same picture, fewer faces

The Asset Kit and the terrain write every face as a triangle, so a wall, a roof panel or a card
is two faces, and the reader's per-face work (the back-face test, the packet, the sort) is paid
twice. Mei draws a quad as its two triangles 0-1-2 and 1-2-3 (docs/LANGUAGE.md, "Mesh format"),
so two triangles that share an edge, face the same way and agree in everything the face record
holds (flags, blend, texture, palette, and the colour and texture coordinate at both shared
corners) are drawn alike as one quad whose diagonal is that edge, as long as they lie flat: the
reader decides whether a quad faces away by its first triangle alone, so the two triangles' planes
must agree to within a degree (seen from within a degree of edge-on the pair can differ, where it
covers next to no pixels); and the four corners must make a convex quad, because a quad cut by the
near plane or the guard band is clipped as the polygon around its corners and fanned from one of
them, which covers a dart's two triangles wrongly. This pass makes those
quads and leaves everything else as it was: semi-transparent and keyed faces (sorted by the
ordering table, where a quad sorts as one face), and triangles with no partner.

Each triangle pairs with the first unpaired partner it meets, in face order; quads take the place
of their first triangle, so the order of the rest is kept.
"""
import math
import struct

FACE = struct.Struct('<BBBB4H4I4H')
GOURAUD = 1
QUAD = 4
SEMI = 8
KEYED = 32
FLAT_COS = math.cos(math.radians(1.0))      # how flat a pair must be (its triangles' normals)


def _normal(v, idx):
    a, b, c = (v[i] for i in idx)
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    w = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
    ln = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
    return (n[0] / ln, n[1] / ln, n[2] / ln) if ln else None


def _convex(ring, n):
    """Whether the polygon ring (four corners in order) turns the same way, strictly, at every
    corner, about normal n."""
    signs = set()
    for q in range(4):
        p0, p1, p2 = ring[q - 1], ring[q], ring[(q + 1) % 4]
        u = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        v = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
        c = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        t = c[0] * n[0] + c[1] * n[1] + c[2] * n[2]
        lu = math.sqrt(u[0] * u[0] + u[1] * u[1] + u[2] * u[2])
        lv = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
        if abs(t) <= 1e-3 * lu * lv:
            return False            # a straight corner: a triangle with a point on its edge
        signs.add(t > 0)
    return len(signs) == 1


def pair(mesh, flat_cos=FLAT_COS):
    nv, nf, vo, fo, wo = struct.unpack_from('<HHIII', mesh)
    faces = [FACE.unpack_from(mesh, fo + 36 * k) for k in range(nf)]
    table = mesh[wo:] if wo else b''
    verts = [struct.unpack_from('<3i', mesh, vo + 16 * k) for k in range(nv)]
    normals = [_normal(verts, f[4:7]) for f in faces]

    def pairable(f):
        return not f[0] & (QUAD | SEMI | KEYED)

    edges = {}
    for k, f in enumerate(faces):
        if not pairable(f):
            continue
        idx = f[4:7]
        for c in range(3):
            a, b = idx[c], idx[(c + 1) % 3]
            edges.setdefault((a, b), []).append((k, c))
    partner = {}
    for k, f in enumerate(faces):
        if not pairable(f) or k in partner:
            continue
        idx = f[4:7]
        for c in range(3):
            a, b = idx[c], idx[(c + 1) % 3]
            # the same facing: the other triangle runs the shared edge the other way
            for m, d in edges.get((b, a), ()):
                if m == k or m in partner:
                    continue
                g = faces[m]
                if g[0:4] != f[0:4]:
                    continue
                gidx = g[4:7]
                if len(set(idx) | set(gidx)) != 4:
                    continue
                # the reader turns a quad away by its first triangle alone: only a flat pair (to
                # within flat_cos) faces the viewer as its two triangles would
                n, o = normals[k], normals[m]
                if n is None or o is None or n[0] * o[0] + n[1] * o[1] + n[2] * o[2] < flat_cos:
                    continue
                # and convex: a clipped quad is cut as the polygon around its corners, fanned
                # from its first, which covers a dart's two triangles only if it is convex
                w = [i for i in gidx if i not in (a, b)][0]
                x = [i for i in idx if i not in (a, b)][0]
                if not _convex([verts[q] for q in (x, a, w, b)], n):
                    continue
                # corner attributes at the shared corners must agree: g has b at d, a at d + 1
                # (a flat face draws in its first colour: the two must have the same one)
                if (f[12 + c], f[12 + (c + 1) % 3]) != (g[12 + (d + 1) % 3], g[12 + d]):
                    continue
                if f[0] & GOURAUD:
                    if (f[8 + c], f[8 + (c + 1) % 3]) != (g[8 + (d + 1) % 3], g[8 + d]):
                        continue
                elif f[8] != g[8]:
                    continue
                partner[k], partner[m] = (m, c, d), (k, None, None)
                break
            if k in partner:
                break
    out = []
    for k, f in enumerate(faces):
        if k not in partner:
            out.append(FACE.pack(*f))
            continue
        m, c, d = partner[k]
        if c is None:
            continue            # drawn as part of its partner's quad
        g = faces[m]
        # f's corners turned so the shared edge (c, c + 1) is corners 1 and 2: x, y, z; then w
        order = [(c + 2) % 3, c, (c + 1) % 3]
        w = (d + 2) % 3
        idx = [f[4 + o] for o in order] + [g[4 + w]]
        cols = [f[8 + o] for o in order] + [g[8 + w]] if f[0] & GOURAUD else [f[8]] * 4
        uvs = [f[12 + o] for o in order] + [g[12 + w]]
        out.append(FACE.pack(f[0] | QUAD, f[1], f[2], f[3], *idx, *cols, *uvs))
    if len(out) == nf:
        return mesh
    head = struct.pack('<HHIII', nv, len(out), vo, fo, fo + 36 * len(out) if table else 0)
    return head + mesh[16:fo] + b''.join(out) + table
