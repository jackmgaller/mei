#!/usr/bin/env python3
"""Write console.asset.json and controller.asset.json for look 04, Sun & Moon Twin.

Standard library only. The art sheet is drawn by make_art.py (Pillow).

Both bodies are a round sun (a drum, warm orange) cradled by a crescent moon (pale blue) with a
dark gap between them; a dark plinth under both joins them and shows at the bottom of the gap.
Metres, real size, Y up, the front faces -Z.
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------- vectors

def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a):
    l = math.sqrt(dot(a, a))
    return (a[0] / l, a[1] / l, a[2] / l)


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return tuple(n)


# ---------------------------------------------------------------- mesh builder

class Mesh:
    """One `mesh` node: welded vertices, faces with a material each, wound by an outward hint."""

    def __init__(self, ident):
        self.id = ident
        self.v, self.f, self.m, self.key = [], [], [], {}

    def vid(self, p):
        p = tuple(round(c, 6) + 0.0 for c in p)
        if p not in self.key:
            self.key[p] = len(self.v)
            self.v.append(list(p))
        return self.key[p]

    def poly(self, pts, mat, out):
        """A planar polygon, kept as one source polygon (so `fit` textures cover it whole)."""
        if dot(newell(pts), out) < 0:
            pts = pts[::-1]
        idx = [self.vid(p) for p in pts]
        # drop repeated corners (a collapsed edge)
        clean = [i for k, i in enumerate(idx) if i != idx[k - 1]]
        if len(clean) < 3:
            return
        # A polygon stays one source polygon only when it lies in an axis plane (exactly planar
        # after 16.16 rounding); others are convex here and become a fan of triangles.
        flat = any(len({self.v[i][ax] for i in clean}) == 1 for ax in range(3))
        if len(clean) == 3 or flat:
            self.f.append(clean)
            self.m.append(mat)
        else:
            # fan from the corner whose smallest triangle is largest (no collinear slivers)
            V = lambda i: self.v[i]
            def area(a, b, c):
                return math.sqrt(dot(*(2 * [cross(sub(V(b), V(a)), sub(V(c), V(a)))])))
            n = len(clean)
            best = max(range(n), key=lambda s: min(area(clean[s], clean[(s + k) % n], clean[(s + k + 1) % n])
                                                   for k in range(1, n - 1)))
            for k in range(1, n - 1):
                self.f.append([clean[best], clean[(best + k) % n], clean[(best + k + 1) % n]])
                self.m.append(mat)

    def quad(self, a, b, c, d, mat, out):
        """Two triangles (quads here are not always planar)."""
        self.poly([a, b, c], mat, out)
        self.poly([a, c, d], mat, out)

    def node(self):
        return {"id": self.id, "op": "mesh", "vertices": self.v, "faces": self.f, "face_materials": self.m}

    def tris(self):
        return sum(len(f) - 2 for f in self.f)


def ring_pt(c, r, a, y):
    """A point at angle a (radians, in the x-z plane: a=0 is +X, a=-90 deg is -Z, the front)."""
    return (c[0] + r * math.cos(a), y, c[1] + r * math.sin(a))


def revolve(mesh, c, profile, mats, segs, top_mat=None, a_off=0.0):
    """Lathe around the vertical axis through c=(x, z). profile: (r, y) from the bottom outside
    upward; band i between points i and i+1 gets mats[i]. If top_mat is given the last ring is
    closed by one flat polygon (one source polygon, so a `fit` texture covers it)."""
    angs = [a_off + 2 * math.pi * k / segs for k in range(segs)]
    for i in range(len(profile) - 1):
        (r0, y0), (r1, y1) = profile[i], profile[i + 1]
        dr, dy = r1 - r0, y1 - y0
        for k in range(segs):
            a0, a1 = angs[k], angs[(k + 1) % segs]
            am = (a0 + a1) / 2
            out = (dy * math.cos(am), -dr, dy * math.sin(am))
            p = [ring_pt(c, r0, a0, y0), ring_pt(c, r0, a1, y0), ring_pt(c, r1, a1, y1), ring_pt(c, r1, a0, y1)]
            if r1 == 0:
                mesh.poly([p[0], p[1], p[2]], mats[i], out)
            elif r0 == 0:
                mesh.poly([p[0], p[2], p[3]], mats[i], out)
            else:
                mesh.poly(p, mats[i], out)  # a symmetric trapezoid: planar
    if top_mat:
        r, y = profile[-1]
        mesh.poly([ring_pt(c, r, a, y) for a in angs], top_mat, (0, 1, 0))


def extrude(mesh, loop, offset, mats, cap0=True, cap1=True):
    """A prism: a planar loop of 3D points and the same loop moved by `offset`.
    mats: (side, cap0, cap1) or a single material."""
    if isinstance(mats, str):
        mats = (mats, mats, mats)
    nrm = norm(offset)
    sign = 1 if dot(newell(loop), nrm) > 0 else -1
    top = [add(p, offset) for p in loop]
    n = len(loop)
    for i in range(n):
        j = (i + 1) % n
        e = sub(loop[j], loop[i])
        out = mul(cross(e, nrm), sign)
        mesh.poly([loop[i], loop[j], top[j], top[i]], mats[0], out)
    if cap0:
        mesh.poly(loop, mats[1], mul(nrm, -1))
    if cap1:
        mesh.poly(top, mats[2], nrm)


class Frame:
    """A local frame on a surface: lx to the right, ly up, lz into the body (away from the
    viewer standing in front of the surface). `n` is the outward direction in x-z."""

    def __init__(self, origin, n_xz):
        nx, nz = n_xz
        l = math.hypot(nx, nz)
        nx, nz = nx / l, nz / l
        self.o = origin
        self.r = (-nz, 0.0, nx)
        self.u = (0.0, 1.0, 0.0)
        self.b = (-nx, 0.0, -nz)

    def p(self, x, y, z):
        return add(self.o, add(mul(self.r, x), add(mul(self.u, y), mul(self.b, z))))

    def d(self, x, y, z):
        return add(mul(self.r, x), add(mul(self.u, y), mul(self.b, z)))


class TopFrame(Frame):
    """A frame lying on a horizontal surface: lx along `right_xz`, ly toward the back, lz down."""

    def __init__(self, origin, right_xz=(1.0, 0.0)):
        rx, rz = right_xz
        l = math.hypot(rx, rz)
        self.o = origin
        self.r = (rx / l, 0.0, rz / l)
        self.u = (-rz / l, 0.0, rx / l)  # the back, when right is +X
        self.b = (0.0, -1.0, 0.0)


def box(mesh, fr, c, size, mats, skip=()):
    """A box in a frame: c and size in local (x, y, z); mats: dict side -> material, sides
    front (-lz, toward the viewer), back, left, right, top (+ly), bottom; or one material."""
    if isinstance(mats, str):
        mats = {s: mats for s in ("front", "back", "left", "right", "top", "bottom")}
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    P = lambda sx, sy, sz: fr.p(c[0] + sx * hx, c[1] + sy * hy, c[2] + sz * hz)
    faces = {
        "front": ([(-1, 1, -1), (1, 1, -1), (1, -1, -1), (-1, -1, -1)], (0, 0, -1)),
        "back": ([(1, 1, 1), (-1, 1, 1), (-1, -1, 1), (1, -1, 1)], (0, 0, 1)),
        "left": ([(-1, 1, 1), (-1, 1, -1), (-1, -1, -1), (-1, -1, 1)], (-1, 0, 0)),
        "right": ([(1, 1, -1), (1, 1, 1), (1, -1, 1), (1, -1, -1)], (1, 0, 0)),
        "top": ([(-1, 1, 1), (1, 1, 1), (1, 1, -1), (-1, 1, -1)], (0, 1, 0)),
        "bottom": ([(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)], (0, -1, 0)),
    }
    for side, (corners, o) in faces.items():
        if side in skip:
            continue
        mesh.poly([P(*k) for k in corners], mats[side], fr.d(*o))


def recess(mesh, fr, cy, W, H, w, h, depth, back, mats):
    """A port or slot: a bezel W x H standing out of a surface (front plane at lz = 0, running
    back to lz = back), with a w x h opening `depth` deep. mats: (bezel, walls, hole)."""
    bez, wall, hole = mats
    o = [(-W / 2, cy + H / 2), (W / 2, cy + H / 2), (W / 2, cy - H / 2), (-W / 2, cy - H / 2)]
    i = [(-w / 2, cy + h / 2), (w / 2, cy + h / 2), (w / 2, cy - h / 2), (-w / 2, cy - h / 2)]
    for k in range(4):
        j = (k + 1) % 4
        # bezel face: trapezoid between outer and inner edge k
        mesh.poly([fr.p(*o[k], 0), fr.p(*o[j], 0), fr.p(*i[j], 0), fr.p(*i[k], 0)], bez, fr.d(0, 0, -1))
        # opening wall: faces into the opening
        mid = ((i[k][0] + i[j][0]) / 2, (i[k][1] + i[j][1]) / 2)
        inward = (-(mid[0]), cy - mid[1], 0)
        mesh.poly([fr.p(*i[k], 0), fr.p(*i[j], 0), fr.p(*i[j], depth), fr.p(*i[k], depth)], wall, fr.d(*inward))
        # outer side, running back into the body
        mo = ((o[k][0] + o[j][0]) / 2, (o[k][1] + o[j][1]) / 2)
        outward = (mo[0], mo[1] - cy, 0)
        mesh.poly([fr.p(*o[k], 0), fr.p(*o[j], 0), fr.p(*o[j], back), fr.p(*o[k], back)], bez, fr.d(*outward))
    mesh.poly([fr.p(*p, depth) for p in i], hole, fr.d(0, 0, -1))


def tube(mesh, fr, cx, cy, r, z0, z1, segs, mats):
    """A cylinder along the frame's lz from z0 (toward the viewer) to z1. mats: (side, cap)."""
    loop = [fr.p(cx + r * math.cos(2 * math.pi * k / segs), cy + r * math.sin(2 * math.pi * k / segs), z1)
            for k in range(segs)]
    extrude(mesh, loop, fr.d(0, 0, z0 - z1), (mats[0], mats[1], mats[1]), cap0=False, cap1=True)


def tube_path(mesh, path, r, segs, mat):
    """A round tube along a polyline, open at both ends (one end is buried, the other is cut)."""
    rings = []
    for i, p in enumerate(path):
        a = path[max(i - 1, 0)]
        b = path[min(i + 1, len(path) - 1)]
        t = norm(sub(b, a))
        side = norm(cross(t, (0, 1, 0)))
        up = cross(side, t)
        rings.append([add(p, add(mul(side, r * math.cos(2 * math.pi * k / segs)), mul(up, r * math.sin(2 * math.pi * k / segs))))
                      for k in range(segs)])
    for i in range(len(rings) - 1):
        for k in range(segs):
            j = (k + 1) % segs
            q = [rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]]
            mid = mul(add(path[i], path[i + 1]), 0.5)
            mesh.quad(*q, mat, sub(mul(add(q[0], q[2]), 0.5), mid))
    end = rings[-1]
    t = sub(path[-1], path[-2])
    mesh.poly(end, mat, t)


def circle_union(a, ra, b, rb, n):
    """Outline (x, z) of the union of two overlapping circles, about n points."""
    dx, dz = b[0] - a[0], b[1] - a[1]
    D = math.hypot(dx, dz)
    phi = math.atan2(dz, dx)
    al = math.acos((ra * ra + D * D - rb * rb) / (2 * ra * D))
    be = math.acos((rb * rb + D * D - ra * ra) / (2 * rb * D))
    na = max(4, int(n * (2 * math.pi - 2 * al) * ra / ((2 * math.pi - 2 * al) * ra + (2 * math.pi - 2 * be) * rb)))
    nb = max(4, n - na)
    pts = []
    for k in range(na + 1):  # A, away from B: from phi+al to phi+2pi-al
        t = phi + al + (2 * math.pi - 2 * al) * k / na
        pts.append((a[0] + ra * math.cos(t), a[1] + ra * math.sin(t)))
    for k in range(1, nb):  # B, away from A: from (phi+pi)+be to (phi+pi)+2pi-be
        t = phi + math.pi + be + (2 * math.pi - 2 * be) * k / nb
        pts.append((b[0] + rb * math.cos(t), b[1] + rb * math.sin(t)))
    # make sure B's arc starts at A's arc's end
    if math.dist(pts[na], pts[na + 1]) > math.dist(pts[na], pts[-1]):
        pts = pts[:na + 1] + pts[na + 1:][::-1]
    return pts


def prism_xz(mesh, outline, y0, y1, mats, bottom=True):
    loop = [(x, y0, z) for x, z in outline]
    extrude(mesh, loop, (0, y1 - y0, 0), mats, cap0=bottom, cap1=True)


class Crescent:
    """The moon: the ring between radius rc around the sun's centre s and the outer circle
    (mo, ro), cut where it is thinner than wmin. Points are on rays from s."""

    def __init__(self, s, rc, mo, ro, wmin, base=0.0, low=1.0, flat=0.0):
        """Heights above `base` are scaled from 1 (within `flat` radians of the middle) down to
        `low` at the horns, so the crescent tapers toward its tips."""
        self.s, self.rc, self.mo, self.ro = s, rc, mo, ro
        self.base, self.low, self.flat = base, low, flat
        # the moon's middle direction, and the angle range where the band is wider than wmin
        self.rot = math.atan2(mo[1] - s[1], mo[0] - s[0])
        lim = 0.0
        while self.d(self.rot + lim + 0.001) - rc > wmin:
            lim += 0.001
        self.lim = lim

    def d(self, a):
        """Distance from s along angle a to the outer circle."""
        ux, uz = math.cos(a), math.sin(a)
        ox, oz = self.s[0] - self.mo[0], self.s[1] - self.mo[1]
        bq = ox * ux + oz * uz
        cq = ox * ox + oz * oz - self.ro * self.ro
        return -bq + math.sqrt(bq * bq - cq)

    def mid(self, a):
        return (self.rc + self.d(a)) / 2

    def h(self, a):
        t = max(0.0, (abs(a - self.rot) - self.flat) / (self.lim - self.flat))
        return 1 - (1 - self.low) * (1 - math.cos(t * math.pi / 2))

    def point(self, a, side, off, y, wref=0.03):
        y = self.base + (y - self.base) * self.h(a)
        w = self.d(a) - self.rc
        k = min(1.0, w / wref)
        r = self.rc + off * k if side == "i" else self.d(a) - off * k
        return ring_pt(self.s, r, a, y)

    def build(self, mesh, profile, mats, k, matfn=None):
        """profile: closed loop of (side, off, y), inner bottom first, going up the inner wall,
        over the top and down the outer wall. mats[i] for edge i (to the next point);
        matfn(edge, a_mid) may override."""
        angs = [self.rot - self.lim + 2 * self.lim * j / (k - 1) for j in range(k)]
        n = len(profile)
        for e in range(n):
            p0, p1 = profile[e], profile[(e + 1) % n]
            for j in range(k - 1):
                a0, a1 = angs[j], angs[j + 1]
                am = (a0 + a1) / 2
                q = [self.point(a0, *p0), self.point(a1, *p0), self.point(a1, *p1), self.point(a0, *p1)]
                # outward hint: the edge's normal in the cross-section, (s, y) -> (-dy, ds)
                s0 = math.dist((q[0][0], q[0][2]), (self.s[0], self.s[1]))
                s1 = math.dist((q[3][0], q[3][2]), (self.s[0], self.s[1]))
                ds, dy = s1 - s0, q[3][1] - q[0][1]
                if p0[0] != p1[0]:  # across the band (the top or the bottom)
                    ds = (1 if p1[0] == "o" else -1) * 0.01
                out = (-dy * math.cos(am), ds, -dy * math.sin(am))
                mat = matfn(e, am) if matfn else None
                mesh.quad(*q, mat or mats[e], out)
        for a, sgn in ((angs[0], -1), (angs[-1], 1)):
            t = (-math.sin(a) * sgn, 0, math.cos(a) * sgn)
            mesh.poly([self.point(a, *p) for p in profile], mats[-1] if len(mats) > n else mats[0], t)


def recentre(nodes):
    """Move every mesh so the whole model's footprint is centred on x = z = 0 (y stays)."""
    xs = [v[0] for n in nodes for v in n.v]
    zs = [v[2] for n in nodes for v in n.v]
    cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
    for n in nodes:
        n.v = [[round(v[0] - cx, 6) + 0.0, v[1], round(v[2] - cz, 6) + 0.0] for v in n.v]
    print("footprint %.3f x %.3f m, height %.3f m" % (max(xs) - min(xs), max(zs) - min(zs),
                                                      max(v[1] for n in nodes for v in n.v)))


def write(name, recipe):
    path = HERE / f"{name}.asset.json"
    path.write_text(json.dumps(recipe, indent=1) + "\n")
    print("wrote", path.name)


SHEET = {"art": {"image": "art/sheet.png"}}
POLICY = {"required": True, "depth": True, "perspective": True}
LIGHT = {"direction": [-0.45, 0.85, -0.3], "ambient": 0.5}


def cell(name, bits=4):
    t = {"sheet": "art", "cell": name, "projection": "fit"}
    if bits == 8:
        t["bits"] = 8
    return t


# ================================================================= console

def console():
    S = (-0.0425, 0.0)        # the sun's centre (x, z)
    RS = 0.115                # the sun's radius
    ROT = math.radians(20)    # the moon is turned toward the back, leaving the sun's front free
    MO = (S[0] + 0.058 * math.cos(ROT), S[1] + 0.058 * math.sin(ROT))  # the moon's outer circle
    RO = 0.138
    RC = 0.125                # the moon's inner edge: a 1 cm gap around the sun
    nodes = []

    # the plinth: one dark base under both, inset, showing at the bottom of the gap
    m = Mesh("plinth")
    prism_xz(m, circle_union(S, 0.107, MO, 0.128, 34), 0.0, 0.014, "plinth", bottom=False)
    nodes.append(m)

    # the sun: a drum with a bevelled rim and a flat top carrying the sunburst
    m = Mesh("sun")
    revolve(m, S, [(0.109, 0.012), (0.115, 0.019), (0.115, 0.063), (0.111, 0.071), (0.103, 0.076)],
            ["sun_rim", "sun", "sun_rim", "sun_rim"], 28, top_mat="sunburst", a_off=math.pi / 28)
    nodes.append(m)

    # the moon: a crescent wall, taller than the sun, with louvres on its back half
    moon = Crescent(S, RC, MO, RO, 0.006, base=0.012, low=0.22, flat=math.radians(52))
    m = Mesh("moon")
    prof = [("i", 0, 0.012), ("i", 0, 0.079), ("i", 0.005, 0.086), ("o", 0.006, 0.086),
            ("o", 0, 0.079), ("o", 0, 0.064), ("o", 0, 0.032), ("o", 0, 0.012)]
    mats = ["moon_in", "moon_rim", "moon", "moon_rim", "moon_side", "moon_side", "moon_side", "plinth", "moon_side"]

    def vents(e, a):
        return "vent" if e == 5 and a - ROT > math.radians(15) else None
    moon.build(m, prof, mats, 22, vents)
    nodes.append(m)

    # the front of the sun: two controller ports, a memory card slot above each, the small mark
    m = Mesh("front_ports")
    for side in (-1, 1):
        a = math.radians(-90 + side * 17)
        n = (math.cos(a), math.sin(a))
        fr = Frame(ring_pt(S, RS + 0.0025, a, 0.0), n)
        recess(m, fr, 0.0315, 0.027, 0.0165, 0.020, 0.0095, 0.006, 0.010,
               ("port", "port_in", "port_hole"))
        recess(m, fr, 0.0525, 0.034, 0.0075, 0.029, 0.0028, 0.005, 0.010,
               ("port", "port_in", "port_hole"))
    nodes.append(m)

    m = Mesh("front_mark")
    a = math.radians(-90)
    fr = Frame(ring_pt(S, RS + 0.0012, a, 0.0), (0, -1))
    m.poly([fr.p(-0.012, 0.048, 0), fr.p(0.012, 0.048, 0), fr.p(0.012, 0.036, 0), fr.p(-0.012, 0.036, 0)],
           "small_mark", fr.d(0, 0, -1))
    box(m, fr, (0, 0.042, 0.004), (0.024, 0.012, 0.008), "navy", skip=("front",))
    nodes.append(m)

    # the cartridge slot and a cartridge standing in it
    m = Mesh("slot")
    fr = TopFrame((S[0], 0.0, S[1]))
    box(m, fr, (0, 0, -0.0795), (0.104, 0.030, 0.011), "port", skip=("back",))
    nodes.append(m)

    m = Mesh("cart")
    fr = Frame((S[0], 0.0, S[1] - 0.009), (0, -1))
    t, c = 0.018, 0.004
    sec = [(-0.045, 0.06), (-0.045, 0.131), (-0.041, 0.135), (0.041, 0.135), (0.045, 0.131), (0.045, 0.06)]
    loop = [fr.p(x, y, 0) for x, y in sec]
    extrude(m, loop, fr.d(0, 0, t), ("cart", "cart", "cart"))
    # label, standing 0.7 mm proud of the front
    lx, ly0, ly1 = 0.0265, 0.080, 0.124
    m.poly([fr.p(-lx, ly1, -0.0007), fr.p(lx, ly1, -0.0007), fr.p(lx, ly0, -0.0007), fr.p(-lx, ly0, -0.0007)],
           "label", fr.d(0, 0, -1))
    box(m, fr, (0, (ly0 + ly1) / 2, 0.0004), (2 * lx, ly1 - ly0, 0.0022), "cart_dark", skip=("front",))
    # grip ridges on the back
    for k in range(4):
        box(m, fr, (0, 0.09 + k * 0.01, t + 0.0006), (0.07, 0.003, 0.0024), "cart_dark", skip=("front",))
    nodes.append(m)

    # on the moon's top: the 明 MEI badge, power, reset and the power light
    m = Mesh("badge")
    a0 = math.radians(0)
    cr = moon.mid(a0)
    bx, bz = ring_pt(S, cr, a0, 0)[0], ring_pt(S, cr, a0, 0)[2]
    fr = TopFrame((bx, 0.0, bz), (1, 0))
    w, h = 0.048, 0.018
    top = 0.0872
    m.poly([fr.p(-w / 2, h / 2, -top), fr.p(w / 2, h / 2, -top), fr.p(w / 2, -h / 2, -top), fr.p(-w / 2, -h / 2, -top)],
           "badge", (0, 1, 0))
    box(m, fr, (0, 0, -(top - 0.0015)), (w, h, 0.003), "navy", skip=("front", "back"))
    nodes.append(m)

    m = Mesh("buttons")
    for ang, r, col, ht, segs in ((-13, 0.0105, "power", 0.0045, 12), (-28, 0.0075, "reset", 0.003, 10)):
        a = math.radians(ang)
        c = ring_pt(S, moon.mid(a), a, 0)
        cxz = (c[0], c[2])
        revolve(m, cxz, [(r, 0.0845), (r, 0.0865 + ht), (r - 0.0015, 0.088 + ht)],
                ["button_side", "button_side"], segs, top_mat=col)
    a = math.radians(-21)
    c = ring_pt(S, moon.mid(a), a, 0)
    revolve(m, (c[0], c[2]), [(0.0028, 0.0845), (0.0028, 0.0878), (0.0018, 0.0885)], ["led", "led"], 6,
            top_mat="led")
    nodes.append(m)

    # the back: AV out and power in on the sun, the MeiNet aerial socket on the moon
    m = Mesh("back")
    a = math.radians(135)
    fr = Frame(ring_pt(S, RS + 0.002, a, 0.0), (math.cos(a), math.sin(a)))
    recess(m, fr, 0.040, 0.034, 0.013, 0.028, 0.007, 0.005, 0.010, ("port", "port_in", "port_hole"))
    a = math.radians(162)
    fr = Frame(ring_pt(S, RS + 0.002, a, 0.0), (math.cos(a), math.sin(a)))
    recess(m, fr, 0.040, 0.016, 0.016, 0.0075, 0.0075, 0.005, 0.010, ("port", "port_in", "port_hole"))
    a = math.radians(70)
    p = moon.point(a, "o", 0, 0.0)
    nrm = (p[0] - MO[0], p[2] - MO[1])
    fr = Frame(p, nrm)
    tube(m, fr, 0, 0.045, 0.0075, -0.002, 0.006, 8, ("port", "port"))
    tube(m, fr, 0, 0.045, 0.0042, -0.013, -0.001, 6, ("metal", "metal"))
    nodes.append(m)

    materials = {
        "plinth": {"color": "#262a3c"},
        "navy": {"color": "#22283e"},
        "sun": {"color": "#ee9440", "smooth": True},
        "sun_rim": {"color": "#e07c34", "smooth": True},
        "sunburst": {"color": "#f6b45a", "texture": cell("sunburst")},
        "moon": {"color": "#c4d6f6"},
        "moon_rim": {"color": "#aec4ec", "smooth": True},
        "moon_side": {"color": "#b4c8ee", "smooth": True},
        "moon_in": {"color": "#7e92c4", "smooth": True},
        "vent": {"color": "#bccae4", "smooth": True,
                 "texture": {"pattern": "stripes", "colors": ["#b4c8ee", "#56648e"], "size": 8,
                             "params": {"count": 2, "axis": "v"}, "projection": "cylindrical",
                             "scale": [0.02, 0.007]}},
        "port": {"color": "#33374a"},
        "port_in": {"color": "#1d2030"},
        "port_hole": {"color": "#0e0f16"},
        "small_mark": {"color": "#22283e", "texture": cell("small_mark", 8)},
        "badge": {"color": "#22283e", "texture": cell("badge", 8)},
        "cart": {"color": "#5c6378"},
        "cart_dark": {"color": "#474d60"},
        "label": {"color": "#303868", "texture": cell("label", 8)},
        "ring": {"color": "#8e9dc0"},
        "button_side": {"color": "#d8e0f0"},
        "power": {"color": "#f08a3a"},
        "reset": {"color": "#e8eef8"},
        "led": {"color": "#ff4a3a"},
        "metal": {"color": "#d8d4c8", "smooth": True},
    }
    recentre(nodes)
    recipe = {
        "format": "mei-asset", "version": 1, "name": "console_04_sun_moon_twin",
        "budget": {"vertices": 2048, "triangles": 1200},
        "sheets": SHEET,
        "materials": materials,
        "lighting": LIGHT,
        "verification": POLICY,
        "nodes": [n.node() for n in nodes],
    }
    print("console triangles (before the kit's triangulation of polygons):",
          {n.id: n.tris() for n in nodes}, sum(n.tris() for n in nodes))
    write("console", recipe)


# ================================================================= controller

def controller():
    S = (-0.044, 0.0)
    RS = 0.035
    MO = (S[0] + 0.062, 0.0)
    RO = 0.049
    RC = 0.061
    nodes = []

    m = Mesh("bridge")
    prism_xz(m, circle_union(S, 0.030, MO, 0.0425, 20), 0.0, 0.015, "plinth", bottom=False)
    nodes.append(m)

    m = Mesh("sun")
    revolve(m, S, [(0.031, 0.006), (0.035, 0.012), (0.035, 0.021), (0.030, 0.027)],
            ["sun_rim", "sun", "sun_rim"], 18, top_mat="sunburst", a_off=math.pi / 18)
    nodes.append(m)

    moon = Crescent(S, RC, MO, RO, 0.007, base=0.006, low=0.62, flat=math.radians(38))
    m = Mesh("moon")
    prof = [("i", 0, 0.006), ("i", 0, 0.025), ("i", 0.004, 0.031), ("o", 0.004, 0.031),
            ("o", 0, 0.025), ("o", 0, 0.006)]
    moon.build(m, prof, ["moon_in", "moon_rim", "moon", "moon_rim", "moon_side", "plinth", "moon_side"], 13)
    nodes.append(m)

    # d-pad: a cross on the sun's top
    m = Mesh("dpad")
    L, Wd = 0.0125, 0.0045
    cross = [(-Wd, L), (Wd, L), (Wd, Wd), (L, Wd), (L, -Wd), (Wd, -Wd), (Wd, -L), (-Wd, -L),
             (-Wd, -Wd), (-L, -Wd), (-L, Wd), (-Wd, Wd)]
    loop = [(S[0] + x, 0.025, S[1] + z) for x, z in cross]
    extrude(m, loop, (0, 0.0065, 0), ("dpad_side", "dpad", "dpad"), cap0=False)
    nodes.append(m)

    # face buttons A B X Y along the crescent, warm at the front to cool at the back
    m = Mesh("face_buttons")
    for ang, name in ((-30, "a"), (-10, "b"), (10, "x"), (30, "y")):
        a = math.radians(ang)
        c = ring_pt(S, moon.mid(a), a, 0)
        r = 0.0062
        revolve(m, (c[0], c[2]), [(r, 0.0300), (r, 0.0352), (r - 0.001, 0.0360)],
                ["btn_side_" + name, "btn_side_" + name], 10, top_mat="btn_" + name, a_off=math.pi / 10)
    nodes.append(m)

    # the analog stick, in the gap at the front
    m = Mesh("stick")
    a = math.radians(-42)
    c = ring_pt(S, (RS + RC) / 2, a, 0)
    cxz = (c[0], c[2])
    revolve(m, cxz, [(0.0115, 0.013), (0.0115, 0.0175), (0.0035, 0.0190), (0.0035, 0.0235),
                     (0.0090, 0.0255), (0.0075, 0.0292)],
            ["stick_base", "stick_base", "stem", "cap", "cap"], 9, top_mat="cap_top")
    nodes.append(m)

    # Select and Start in the gap behind it
    m = Mesh("start_select")
    for ang in (2, 24):
        a = math.radians(ang)
        c = ring_pt(S, (RS + RC) / 2, a, 0)
        fr = TopFrame((c[0], 0.0, c[2]), (-math.sin(a), math.cos(a)))
        box(m, fr, (0, 0, -0.0165), (0.010, 0.0042, 0.004), "small_btn", skip=("back",))
    nodes.append(m)

    # shoulders: L over the sun's back edge, R over the moon's
    m = Mesh("shoulders")

    def arc_bar(c, r0, r1, a0, a1, y0, y1, segs, mat):
        angs = [math.radians(a0 + (a1 - a0) * k / segs) for k in range(segs + 1)]
        prof = [(r0, y0), (r1, y0), (r1, y1), (r0, y1)]
        for k in range(segs):
            am = (angs[k] + angs[k + 1]) / 2
            for i in range(len(prof)):
                (ra, ya), (rb, yb) = prof[i], prof[(i + 1) % len(prof)]
                # profile goes around clockwise in (r, y): outward = (-dy, dr) rotated... use centroid
                mr, my = (ra + rb) / 2, (ya + yb) / 2
                cr, cy = (r0 + r1) / 2, (y0 + y1) / 2
                out = ((mr - cr) * math.cos(am), my - cy, (mr - cr) * math.sin(am))
                m.quad(ring_pt(c, ra, angs[k], ya), ring_pt(c, ra, angs[k + 1], ya),
                       ring_pt(c, rb, angs[k + 1], yb), ring_pt(c, rb, angs[k], yb), mat, out)
        for a, sgn in ((angs[0], -1), (angs[-1], 1)):
            t = (-math.sin(a) * sgn, 0, math.cos(a) * sgn)
            m.poly([ring_pt(c, r, a, y) for r, y in prof], mat, t)

    arc_bar(S, 0.028, 0.0375, 62, 128, 0.017, 0.031, 4, "shoulder_l")
    arc_bar(MO, 0.039, 0.0515, 54, 100, 0.018, 0.034, 4, "shoulder_r")
    nodes.append(m)

    # the cable, out of the back of the bridge
    m = Mesh("cable")
    a = math.radians(90)
    base = (S[0] + 0.040, 0.0, 0.036)
    fr = Frame(base, (0, -1))
    tube(m, fr, 0, 0.0065, 0.0042, -0.012, 0.0, 6, ("navy", "navy"))
    # it runs back, bends down to the table and lies there
    path = [(base[0], 0.0065, base[2]), (base[0] + 0.001, 0.0058, base[2] + 0.016),
            (base[0] + 0.006, 0.0024, base[2] + 0.032), (base[0] + 0.014, 0.0023, base[2] + 0.050)]
    tube_path(m, path, 0.0022, 5, "cable")
    nodes.append(m)

    materials = {
        "plinth": {"color": "#262a3c"},
        "navy": {"color": "#22283e"},
        "sun": {"color": "#ee9440", "smooth": True},
        "sun_rim": {"color": "#e07c34", "smooth": True},
        "sunburst": {"color": "#f6b45a", "texture": cell("sunburst")},
        "moon": {"color": "#c4d6f6"},
        "moon_rim": {"color": "#aec4ec", "smooth": True},
        "moon_side": {"color": "#b4c8ee", "smooth": True},
        "moon_in": {"color": "#7e92c4", "smooth": True},
        "dpad": {"color": "#2c3350"},
        "dpad_side": {"color": "#22283e"},
        "ring": {"color": "#8e9dc0"},
        "btn_a": {"color": "#e86e34", "texture": cell("btn_a")},
        "btn_b": {"color": "#e2a828", "texture": cell("btn_b")},
        "btn_x": {"color": "#5896d6", "texture": cell("btn_x")},
        "btn_y": {"color": "#464696", "texture": cell("btn_y")},
        "btn_side_a": {"color": "#d0602c", "smooth": True},
        "btn_side_b": {"color": "#c89020", "smooth": True},
        "btn_side_x": {"color": "#4a80bc", "smooth": True},
        "btn_side_y": {"color": "#3a3a80", "smooth": True},
        "stick_base": {"color": "#1d2030", "smooth": True},
        "stem": {"color": "#33374a", "smooth": True},
        "cap": {"color": "#d8e0f0", "smooth": True},
        "cap_top": {"color": "#c8d4ea"},
        "small_btn": {"color": "#9aa4bc"},
        "shoulder_l": {"color": "#d8702c"},
        "shoulder_r": {"color": "#7e92c4"},
        "cable": {"color": "#2c3046", "smooth": True},
    }
    recentre(nodes)
    recipe = {
        "format": "mei-asset", "version": 1, "name": "controller_04_sun_moon_twin",
        "budget": {"vertices": 2048, "triangles": 800},
        "sheets": SHEET,
        "materials": materials,
        "lighting": LIGHT,
        "verification": POLICY,
        "nodes": [n.node() for n in nodes],
    }
    print("controller triangles (before polygons):", {n.id: n.tris() for n in nodes},
          sum(n.tris() for n in nodes))
    write("controller", recipe)


if __name__ == "__main__":
    console()
    controller()
