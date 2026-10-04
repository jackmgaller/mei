"""Writes the forest family's recipes: trees_*.asset.json, plant_*, litter_* and the trees'
collision companions, in carts/garden/shrine/assets/.

The trees are cards: crowns of cutout leaf clusters (art/foliage.png, drawn by draw_foliage.py)
facing out from an ellipsoid or a cone, around trunks and limbs that are open prisms. The cards are
placed by a seeded random generator, so the same script writes the same recipes; change the
numbers here and rerun rather than editing the JSON (python3 make_foliage.py [NAME ...]).
"""
import json
import math
import random
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent

LIGHT = {'mode': 'vertical', 'ambient': 0.55}
POLICY = {'required': True, 'depth': True, 'perspective': True}
SHEETS = {'foliage': {'image': 'art/foliage.png'}}


# ---------------------------------------------------------------- vectors

def add(a, b): return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
def sub(a, b): return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
def mul(a, s): return [a[0] * s, a[1] * s, a[2] * s]
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def unit(a):
    n = math.sqrt(dot(a, a))
    return [a[0] / n, a[1] / n, a[2] / n]


def rotate_about(v, axis, ang):
    """Rodrigues: v turned by ang radians about the unit axis."""
    c, s = math.cos(ang), math.sin(ang)
    return add(add(mul(v, c), mul(cross(axis, v), s)), mul(axis, dot(axis, v) * (1 - c)))


def r4(x):
    return round(x, 4) + 0.0


# ---------------------------------------------------------------- meshes

class Part:
    """One mesh node: vertices, faces, face materials and optional hand UVs."""

    def __init__(self, ident, uvs=False):
        self.id, self.v, self.f, self.m = ident, [], [], []
        self.uv = [] if uvs else None
        self.index = {}

    def vert(self, p, uv=None):
        key = (tuple(r4(c) for c in p), tuple(uv) if uv else None)
        if self.uv is None and key in self.index:
            return self.index[key]
        self.v.append([r4(c) for c in p])
        if self.uv is not None:
            self.uv.append([r4(uv[0]), r4(uv[1])])
        self.index[key] = len(self.v) - 1
        return len(self.v) - 1

    def face(self, idx, mat):
        # quads go in as two triangles: rounded to 16.16, a turned quad is not quite flat
        idx = list(idx)
        for k in range(1, len(idx) - 1):
            self.f.append([idx[0], idx[k], idx[k + 1]])
            self.m.append(mat)

    def poly(self, pts, mat, outward=None):
        """A polygon of points; turned round if its normal points against outward."""
        if outward is not None:
            n = cross(sub(pts[1], pts[0]), sub(pts[2], pts[0]))
            if dot(n, outward) < 0:
                pts = pts[::-1]
        self.face([self.vert(p) for p in pts], mat)

    def tris(self):
        return sum(len(f) - 2 for f in self.f)

    def node(self):
        n = {'id': self.id, 'op': 'mesh', 'vertices': self.v, 'faces': self.f, 'face_materials': self.m}
        if self.uv is not None:
            n['uvs'] = self.uv
        return n


def card(part, c, n, w, h, mat, roll=0.0, uv=(0, 0, 1, 1), lift=0.0):
    """A quad centred at c facing n, w wide and h tall, its texture upright (up = world up
    projected on the card, or +Z for a card facing straight up), turned by roll radians.
    lift moves the quad along its up direction (positive: the card's bottom edge at c)."""
    n = unit(n)
    up = [0, 1, 0]
    if abs(n[1]) > 0.999:
        up = [0, 0, 1]
    u = unit(sub(up, mul(n, dot(n, up))))
    r = cross(u, n)
    if roll:
        u, r = rotate_about(u, n, roll), rotate_about(r, n, roll)
    c = add(c, mul(u, lift * h / 2))
    u0, v0, u1, v1 = uv
    corners = [(add(add(c, mul(r, -w / 2)), mul(u, -h / 2)), (u0, v1)),
               (add(add(c, mul(r, w / 2)), mul(u, -h / 2)), (u1, v1)),
               (add(add(c, mul(r, w / 2)), mul(u, h / 2)), (u1, v0)),
               (add(add(c, mul(r, -w / 2)), mul(u, h / 2)), (u0, v0))]
    part.face([part.vert(p, t) for p, t in corners], mat)


def basis(d):
    d = unit(d)
    t = [1, 0, 0] if abs(d[0]) < 0.9 else [0, 0, 1]
    e1 = unit(cross(d, t))
    return d, e1, cross(d, e1)


def ring(centre, d, radius, sides, phase=0.0, radii=None):
    _, e1, e2 = basis(d)
    pts = []
    for i in range(sides):
        a = phase + 2 * math.pi * i / sides
        r = radius * (radii[i] if radii else 1)
        pts.append(add(centre, add(mul(e1, r * math.cos(a)), mul(e2, r * math.sin(a)))))
    return pts


def planar(pts):
    n = unit(cross(sub(pts[1], pts[0]), sub(pts[2], pts[0])))
    return all(abs(dot(n, sub(p, pts[0]))) < 1e-5 for p in pts[3:])


def tube(part, stations, sides, mat, phase=0.0, tip=False, quads=True, radii=None):
    """An open prism along stations [(point, radius), ...]: quads (or two triangles where they
    are not flat), a point at the end when tip; the ring frame comes from the first segment."""
    d = sub(stations[-1][0], stations[0][0])
    rings = [ring(p, d, r, sides, phase, radii[k] if radii else None) for k, (p, r) in enumerate(stations)]
    if tip:
        rings[-1] = None
    for k in range(len(stations) - 1):
        a, b = rings[k], rings[k + 1]
        axis_pt = stations[k][0]
        for i in range(sides):
            j = (i + 1) % sides
            mid = mul(add(a[i], a[j]), 0.5)
            out = sub(mid, axis_pt)
            out = sub(out, mul(unit(d), dot(out, unit(d))))
            if b is None:
                part.poly([a[i], a[j], stations[k + 1][0]], mat, out)
                continue
            if part.uv is not None:
                corners = [(a[i], (0, 1)), (a[j], (1, 1)), (b[j], (1, 0)), (b[i], (0, 0))]
                n = cross(sub(a[j], a[i]), sub(b[i], a[i]))
                if dot(n, out) < 0:
                    corners = [(a[j], (0, 1)), (a[i], (1, 1)), (b[i], (1, 0)), (b[j], (0, 0))]
                idx = [part.vert(p, t) for p, t in corners]
                part.face([idx[0], idx[1], idx[2]], mat)
                part.face([idx[0], idx[2], idx[3]], mat)
                continue
            part.poly([a[i], a[j], b[j]], mat, out)
            part.poly([a[i], b[j], b[i]], mat, out)


def fibonacci(n, rng, jitter=0.25):
    """n directions spread evenly over the sphere, jittered."""
    pts = []
    g = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        y = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(max(0, 1 - y * y))
        a = i * g + rng.uniform(-jitter, jitter)
        y = max(-1, min(1, y + rng.uniform(-jitter, jitter) * 0.3))
        r = math.sqrt(max(0, 1 - y * y))
        pts.append([r * math.cos(a), y, r * math.sin(a)])
    return pts


def crown_cards(part, rng, centre, radii, count, size, mat, depth=0.7, ymin=-1.0, tilt=0.35, sizes=(0.85, 1.15)):
    """Leaf cards over an ellipsoid, each facing out (with a little random tilt)."""
    # spread over the part of the sphere above ymin: count directions out of a larger even set
    total = max(count, int(round(count * 2 / (1 - ymin))))
    dirs = [d for d in fibonacci(total, rng) if d[1] >= ymin][:count]
    for d in dirs:
        k = depth * rng.uniform(0.9, 1.1)
        p = add(centre, [d[0] * radii[0] * k, d[1] * radii[1] * k, d[2] * radii[2] * k])
        n = unit([d[0] / radii[0], d[1] / radii[1], d[2] / radii[2]])
        n = unit(add(n, [rng.uniform(-tilt, tilt), rng.uniform(-tilt, tilt), rng.uniform(-tilt, tilt)]))
        s = size * rng.uniform(*sizes)
        card(part, p, n, s, s, mat, roll=rng.uniform(-0.6, 0.6))


def cross_cards(part, base, w, h, mat, count=2, yaw=0.0, uv=(0, 0, 1, 1)):
    """count vertical cards crossing at base's vertical axis, bottom edge at base."""
    for k in range(count):
        a = yaw + math.pi * k / count
        card(part, base, [math.cos(a), 0, math.sin(a)], w, h, mat, uv=uv, lift=1.0)


def flat_card(part, c, size, mat, yaw=0.0, uv=(0, 0, 1, 1)):
    card(part, c, [0, 1, 0], size, size, mat, roll=yaw, uv=uv)


# ---------------------------------------------------------------- recipes

def tex(cell, colour, double=True):
    m = {'color': colour, 'texture': {'sheet': 'foliage', 'cell': cell, 'projection': 'fit'}}
    if double:
        m['double_sided'] = True
    return m


def tile(cell, colour, scale, double=False):
    m = {'color': colour, 'texture': {'sheet': 'foliage', 'cell': cell, 'projection': 'cylindrical',
                                      'scale': scale}}
    if double:
        m['double_sided'] = True
    return m


def pal(colour):
    return {'color': colour, 'palette': True}


def recipe(name, budget, materials, parts, levels=(), cull=None, band=None):
    r = {'format': 'mei-asset', 'version': 1, 'name': name,
         'budget': {'triangles': budget},
         'materials': materials, 'lighting': LIGHT, 'verification': POLICY}
    if any('texture' in m for m in materials.values()):
        r['sheets'] = SHEETS
    r['nodes'] = [p.node() for p in parts if p.f]
    if levels or cull:
        lod = {'levels': [{'distance': d, 'nodes': [p.node() for p in ps if p.f]} for d, ps in levels]}
        if cull:
            lod['cull'] = cull
        if band:
            lod['band'] = band
        r['lod'] = lod
    tris = [sum(p.tris() for p in parts)] + [sum(p.tris() for p in ps) for _, ps in levels]
    return r, tris


def collision_prism(name, stations, sides, phase=0.0):
    """A trunk's collision: walls only, an open prism through the stations."""
    p = Part('trunk')
    tube(p, stations, sides, 'solid', phase=phase)
    r = {'format': 'mei-asset', 'version': 1, 'name': name,
         'materials': {'solid': pal('#ffffff')}, 'lighting': {'mode': 'vertical', 'ambient': 0.5},
         'verification': POLICY, 'nodes': [p.node()]}
    return r, [p.tris()]


# ---------------------------------------------------------------- trees

def maple(name, seed, height, crown_r, crown_h, trunk_h, trunk_r, limbs, cards, budget, far_at):
    """A Japanese maple: a short trunk forking into limbs under a broad dome of red cards."""
    rng = random.Random(seed)
    mats = {'bark': pal('#5a4a3e'), 'leaves': tex('maple', '#c8301e'), 'far': tex('maple_far', '#c8301e')}
    wood = Part('trunk')
    tube(wood, [([0, 0, 0], trunk_r), ([0, trunk_h, 0], trunk_r * 0.75)], 5, 'bark')
    fork = [0, trunk_h * 0.92, 0]
    cy = height - crown_h / 2 - 0.2
    for k in range(limbs):
        a = 2 * math.pi * k / limbs + rng.uniform(-0.3, 0.3)
        reach = crown_r * rng.uniform(0.38, 0.5)
        end = [math.cos(a) * reach, cy + rng.uniform(-0.2, 0.5) * crown_h * 0.3, math.sin(a) * reach]
        tube(wood, [(fork, trunk_r * 0.62), (end, trunk_r * 0.28)], 3, 'bark', phase=rng.uniform(0, 1))
    crown = Part('crown', uvs=True)
    centre = [0, cy, 0]
    radii = [crown_r * 0.86, crown_h / 2 * 0.75, crown_r * 0.86]
    # the core: a few big cards through the middle so the crown never looks hollow
    for k in range(2):
        a = rng.uniform(0, math.pi) + k * math.pi / 2
        card(crown, [0, height * 0.29, 0], [math.cos(a), 0, math.sin(a)], height * 0.95, height * 0.95 * 0.72,
             'far', uv=(0, 0, 1, 0.72), lift=1.0)
    size = crown_r * 0.85
    crown_cards(crown, rng, centre, radii, cards, size, 'leaves', depth=0.92, tilt=0.3, ymin=-0.45)
    # far: two crossed cards of the whole tree, and one flat card over the crown
    far = Part('far', uvs=True)
    w = height  # maple_far is square: the tree's height across
    cross_cards(far, [0, 0, 0], w, w, 'far', yaw=rng.uniform(0, 1))
    flat_card(far, [0, height * 0.66, 0], crown_r * 1.7, 'leaves', yaw=rng.uniform(0, 6))
    return recipe(name, budget, mats, [wood, crown], [(far_at, [far])])


def ginkgo(name, seed, budget, far_at):
    rng = random.Random(seed)
    mats = {'bark': pal('#8a8278'), 'leaves': tex('ginkgo', '#f0c030'), 'far': tex('ginkgo_far', '#f0c030')}
    height = 14.0
    wood = Part('trunk')
    tube(wood, [([0, 0, 0], 0.32), ([0, 4.5, 0], 0.26), ([0, 11.5, 0], 0.1)], 5, 'bark', quads=True)
    for k, (y, a, L) in enumerate([(4.2, 0.3, 3.4), (5.6, 2.4, 3.0), (7.0, 4.4, 2.8)]):
        start = [0, y, 0]
        end = [math.cos(a) * L * 0.62, y + L * 0.8, math.sin(a) * L * 0.62]
        tube(wood, [(start, 0.13), (end, 0.05)], 3, 'bark', phase=k)
    crown = Part('crown', uvs=True)
    centre = [0, 8.9, 0]
    radii = [2.55, 4.4, 2.55]
    for k in range(2):
        a = rng.uniform(0, math.pi) + k * math.pi / 2
        card(crown, [0, 14.0 * 0.2, 0], [math.cos(a), 0, math.sin(a)], 6.6, 14.0 * 0.8, 'far',
             uv=(0, 0, 1, 0.8), lift=1.0)
    crown_cards(crown, rng, centre, radii, 24, 2.9, 'leaves', depth=0.95, tilt=0.3)
    far = Part('far', uvs=True)
    cross_cards(far, [0, 0, 0], height / 2, height, 'far', yaw=rng.uniform(0, 1))
    flat_card(far, [0, 9.0, 0], 4.6, 'leaves', yaw=rng.uniform(0, 6))
    return recipe(name, budget, mats, [wood, crown], [(far_at, [far])])


def cedar_crown(part, rng, base, top, r_base, tuft, count, mat, droop=-0.25, dome=False):
    """Sugi tufts in a spiral up a cone (or, for an old tree, a dome-topped column), each facing
    out and a little down; tufts are 4:3."""
    g = math.pi * (3 - math.sqrt(5))
    for i in range(count):
        t = (i + 0.5) / count
        y = base + (top - base) * t
        r = (r_base * math.sqrt(max(0.0, 1 - t ** 2.2)) * (0.8 + 0.2 * (1 - t)) if dome
             else r_base * (1 - t) ** 0.85) + 0.25
        a = i * g * 1.0 + rng.uniform(-0.3, 0.3)
        k = (0.72 if dome else 0.62) * (rng.uniform(0.75, 1.05) if dome else 1)
        p = [math.cos(a) * r * k, y, math.sin(a) * r * k]
        n = unit([math.cos(a), droop + rng.uniform(-0.2, 0.25), math.sin(a)])
        s = (tuft * (1 - t * 0.55)) * rng.uniform(0.85, 1.15)
        card(part, p, n, s * 1.15, s * 0.86, mat, roll=rng.uniform(-0.25, 0.25))


def cedar(name, seed, budget, far_at):
    rng = random.Random(seed)
    height = 25.0
    mats = {'bark': tex('cedar_bark', '#6a4632', double=False), 'wood': pal('#4a3a2e'),
            'leaves': tex('cedar', '#2e4a2e'), 'far': tex('cedar_far', '#2e4a2e')}
    bark = Part('trunk', uvs=True)
    tube(bark, [([0, 0, 0], 0.4), ([0, 8.6, 0], 0.3)], 5, 'bark')
    wood = Part('core')
    tube(wood, [([0, 8.6, 0], 0.26), ([0, 22.5, 0], 0.07)], 3, 'wood', phase=0.4)
    crown = Part('crown', uvs=True)
    # the spire's core: the far card's upper part, crossed, from the crown base to the tip
    v0 = 1 - (height - 7.5) / height
    for k in range(2):
        a = 0.3 + k * math.pi / 2
        card(crown, [0, 7.5, 0], [math.cos(a), 0, math.sin(a)], height * 24 / 96, height - 7.5, 'far',
             uv=(0, 0, 1, 1 - v0 + 0.0), lift=1.0)
    cedar_crown(crown, rng, 8.6, 23.6, 2.7, 2.9, 20, 'leaves')
    far = Part('far', uvs=True)
    cross_cards(far, [0, 0, 0], height * 24 / 96, height, 'far', yaw=0.3)
    flat_card(far, [0, 13.0, 0], 3.6, 'leaves', yaw=rng.uniform(0, 6))
    return recipe(name, budget, mats, [bark, wood, crown], [(far_at, [far])])


# ---------------------------------------------------------------- the big cedars

def giant(name, seed, budget):
    """A walkway cedar: 40 m, the trunk 2 m across and bare to 28 m, the crown above."""
    rng = random.Random(seed)
    mats = {'bark': tile('cedar_bark_tile', '#6a4632', [1.6, 6.4]), 'limb': pal('#6a4632'),
            'leaves': tex('cedar', '#2e4a2e'),
            'far': tex('cedar_far', '#2e4a2e')}
    # roots: a flared, lobed base ring
    lobes = [1.0 if i % 2 == 0 else 0.8 for i in range(8)]
    wood = Part('trunk')
    tube(wood, [([0, 0, 0], 1.55), ([0, 1.6, 0], 1.04), ([0, 19.2, 0], 0.97), ([0, 38.4, 0], 0.3)],
         8, 'bark', radii=[lobes, None, None, None], quads=False)
    tube(wood, [([0, 38.4, 0], 0.3), ([0, 40.5, 0], 0.0)], 8, 'bark', tip=True)
    # limbs into the crown, rising
    limbs = Part('limbs')
    for k in range(6):
        a = k * 2.4 + rng.uniform(-0.3, 0.3)
        y = 28.5 + k * 1.3
        L = 3.4 - k * 0.3
        start = [0, y, 0]
        end = [math.cos(a) * L, y + L * 0.55, math.sin(a) * L]
        tube(limbs, [(start, 0.22), (end, 0.06)], 3, 'limb', phase=k)
    crown = Part('crown', uvs=True)
    for k in range(2):
        a = 0.5 + k * math.pi / 2
        card(crown, [0, 27.5, 0], [math.cos(a), 0, math.sin(a)], 5.0, 14.0, 'far', uv=(0, 0, 1, 0.66),
             lift=1.0)
    cedar_crown(crown, rng, 28.6, 40.0, 4.6, 4.6, 42, 'leaves', droop=-0.3)
    # level 1: four sides of trunk, the core and a few tufts
    l1w = Part('trunk')
    tube(l1w, [([0, 0, 0], 1.25), ([0, 19.2, 0], 0.97), ([0, 38.4, 0], 0.3)], 4, 'bark', quads=False)
    l1c = Part('crown', uvs=True)
    for k in range(2):
        a = 0.5 + k * math.pi / 2
        card(l1c, [0, 27.0, 0], [math.cos(a), 0, math.sin(a)], 8.0, 14.5, 'far', uv=(0, 0, 1, 0.66), lift=1.0)
    cedar_crown(l1c, random.Random(seed + 1), 29.0, 39.0, 4.2, 5.4, 12, 'leaves', droop=-0.3)
    l2 = Part('far', uvs=True)
    cross_cards(l2, [0, 0, 0], 41.5 * 24 / 96 * 1.3, 41.5, 'far', yaw=0.5)
    return recipe(name, budget, mats, [wood, limbs, crown], [(70, [l1w, l1c]), (150, [l2])])


def sacred(name, seed, budget):
    """The sacred tree: a huge old sugi, 45 m, its trunk about 4.6 m across over mossy roots,
    dividing into three leaders, a shimenawa with paper streamers at about 4 m."""
    rng = random.Random(seed)
    mats = {'bark': tile('cedar_bark_tile', '#6a4632', [1.8, 6.4]),
            'moss': tile('moss', '#5f7a34', [1.6, 1.6]),
            'rope': tile('rope', '#c8b478', [0.5, 0.25]),
            'paper': tex('shide', '#ece4d2'), 'limb': pal('#6a4632'),
            'leaves': tex('cedar', '#2e4a2e'), 'far': tex('cedar_far', '#2e4a2e')}
    S = 12
    lobes0 = [1.0, 0.66, 0.9, 0.62, 1.05, 0.7, 0.95, 0.6, 1.0, 0.64, 0.88, 0.7]
    lobes1 = [1.0, 0.92, 0.97, 0.9, 1.0, 0.93, 0.98, 0.9, 1.0, 0.92, 0.96, 0.93]
    roots = Part('roots')
    tube(roots, [([0, 0, 0], 3.7), ([0, 1.3, 0], 2.7)], S, 'moss', radii=[lobes0, lobes1], quads=False)
    trunk = Part('trunk')
    tube(trunk, [([0, 1.3, 0], 2.7), ([0, 6.4, 0], 2.3), ([0, 15.0, 0], 2.05)], S, 'bark',
         radii=[lobes1, None, None], quads=False)
    # three leaders from the fork at 15 m, leaning out a little
    leaders = Part('leaders')
    tops = []
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.4
        base = [math.cos(a) * 0.9, 14.0, math.sin(a) * 0.9]
        top = [math.cos(a) * 2.6, 41.0 - k * 2.5, math.sin(a) * 2.6]
        tops.append(top)
        tube(leaders, [(base, 1.15), (mul(add(base, top), 0.5), 0.75), (top, 0.12)], 5, 'bark',
             phase=a, quads=False)
    # limbs from the leaders into the crown
    for k in range(6):
        t = tops[k % 3]
        a = k * 2.1 + 0.2
        y = 21.0 + k * 2.6
        start = [t[0] * (y - 14) / 27, y, t[2] * (y - 14) / 27]
        L = 6.0 - k * 0.5
        end = add(start, [math.cos(a) * L, L * 0.45, math.sin(a) * L])
        tube(leaders, [(start, 0.35), (end, 0.08)], 3, 'limb', phase=k)
    # the shimenawa: a rope ring round the trunk at 4 m, two faces (the rest is against the bark)
    rope = Part('shimenawa', uvs=True)
    N = 14
    R_in, R_out, y0, half = 2.36, 2.72, 4.0, 0.24
    for i in range(N):
        a0, a1 = 2 * math.pi * i / N, 2 * math.pi * (i + 1) / N
        sag = lambda a: -0.12 * math.cos(a - 0.4) ** 2
        def pt(a, r, dy):
            return [math.cos(a) * r, y0 + dy + sag(a), math.sin(a) * r]
        u0, u1 = i * 2.0, (i + 1) * 2.0
        top0, top1 = pt(a0, R_in, half), pt(a1, R_in, half)
        out0, out1 = pt(a0, R_out, 0), pt(a1, R_out, 0)
        bot0, bot1 = pt(a0, R_in, -half), pt(a1, R_in, -half)
        for (p0, p1, q1, q0), (va, vb) in [((out0, out1, top1, top0), (0.0, 1.0)), ((bot0, bot1, out1, out0), (1.0, 2.0))]:
            pts = [(p0, (u0, vb)), (p1, (u1, vb)), (q1, (u1, va)), (q0, (u0, va))]
            n = cross(sub(p1, p0), sub(q0, p0))
            outv = [math.cos((a0 + a1) / 2), 0, math.sin((a0 + a1) / 2)]
            if dot(n, outv) < 0:
                pts = pts[::-1]
            rope.face([rope.vert(p, t) for p, t in pts], 'rope')
    paper = Part('shide', uvs=True)
    for k in range(8):
        a = k * 2 * math.pi / 8 + 0.25
        r = R_out + 0.04
        c = [math.cos(a) * r, y0 - 0.62 - 0.12 * math.cos(a - 0.4) ** 2, math.sin(a) * r]
        card(paper, c, [math.cos(a), 0, math.sin(a)], 0.4, 0.8, 'paper')
    crown = Part('crown', uvs=True)
    for k in range(3):
        a = 0.2 + k * math.pi / 3
        card(crown, [0, 17.0, 0], [math.cos(a), 0, math.sin(a)], 10.0, 28.5, 'far', uv=(0, 0, 1, 0.7), lift=1.0)
    cedar_crown(crown, rng, 17.0, 44.5, 10.5, 7.0, 48, 'leaves', droop=-0.3, dome=True)
    # level 1: fewer sides, no rope detail beyond a band, fewer tufts
    l1 = Part('trunk')
    tube(l1, [([0, 0, 0], 3.3), ([0, 1.3, 0], 2.6)], 6, 'moss', quads=False)
    tube(l1, [([0, 1.3, 0], 2.6), ([0, 15.0, 0], 2.05), ([0, 40.0, 0], 0.4)], 6, 'bark', quads=False)
    l1c = Part('crown', uvs=True)
    for k in range(3):
        a = 0.2 + k * math.pi / 3
        card(l1c, [0, 17.0, 0], [math.cos(a), 0, math.sin(a)], 12.0, 28.5, 'far', uv=(0, 0, 1, 0.7), lift=1.0)
    cedar_crown(l1c, random.Random(seed + 1), 17.5, 43.5, 10.0, 9.0, 24, 'leaves', droop=-0.3, dome=True)
    l2 = Part('far', uvs=True)
    for k in range(3):
        a = 0.2 + k * math.pi / 3
        card(l2, [0, 0, 0], [math.cos(a), 0, math.sin(a)], 16.0, 46.0, 'far', lift=1.0)
    return recipe(name, budget, mats, [roots, trunk, leaders, rope, paper, crown],
                  [(90, [l1, l1c]), (180, [l2])])


# ---------------------------------------------------------------- undergrowth and litter

def fern(name, seed):
    rng = random.Random(seed)
    mats = {'frond': tex('fern', '#5f7a34')}
    def fronds(part, n, rng):
        for k in range(n):
            a = 2 * math.pi * k / n + rng.uniform(-0.25, 0.25)
            L = rng.uniform(0.75, 0.95)
            d = [math.cos(a), 0, math.sin(a)]
            side = [-d[2], 0, d[0]]
            w = L * 0.5
            p0 = [d[0] * 0.05, 0.08, d[2] * 0.05]
            p1 = [d[0] * L * 0.42, 0.72 * L, d[2] * L * 0.42]
            p2 = [d[0] * L * 0.95, 0.52 * L, d[2] * L * 0.95]
            for (q0, q1), (ua, ub) in [((p0, p1), (0.0, 0.5)), ((p1, p2), (0.5, 1.0))]:
                pts = [(add(q0, mul(side, -w / 2)), (ua, 1)), (add(q1, mul(side, -w / 2)), (ub, 1)),
                       (add(q1, mul(side, w / 2)), (ub, 0)), (add(q0, mul(side, w / 2)), (ua, 0))]
                nrm = cross(sub(pts[1][0], pts[0][0]), sub(pts[3][0], pts[0][0]))
                if nrm[1] < 0:
                    pts = pts[::-1]
                part.face([part.vert(p, t) for p, t in pts], 'frond')
    l0 = Part('fronds', uvs=True)
    fronds(l0, 7, rng)
    l1 = Part('fronds', uvs=True)
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.3
        c = [math.cos(a) * 0.35, 0.3, math.sin(a) * 0.35]
        card(l1, c, unit([math.cos(a) * 0.3, 1, math.sin(a) * 0.3]), 0.9, 0.45, 'frond', roll=-a)
    return recipe(name, 30, mats, [l0], [(20, [l1])], cull=45)


def upright_clump(name, cell, colour, w, h, extra, budget, seed, cull, far_at):
    """Undergrowth of upright cards: three crossed through the middle and a few offset."""
    rng = random.Random(seed)
    mats = {'plant': tex(cell, colour)}
    l0 = Part('clump', uvs=True)
    for k in range(3):
        a = k * math.pi / 3 + rng.uniform(-0.1, 0.1)
        card(l0, [0, 0, 0], [math.cos(a), 0, math.sin(a)], w, h, 'plant', lift=1.0)
    for k in range(extra):
        a = rng.uniform(0, 2 * math.pi)
        r = w * rng.uniform(0.3, 0.45)
        b = a + math.pi / 2 + rng.uniform(-0.5, 0.5)
        s = rng.uniform(0.7, 0.9)
        card(l0, [math.cos(a) * r, 0, math.sin(a) * r], [math.cos(b), 0, math.sin(b)], w * s, h * s,
             'plant', lift=1.0)
    l1 = Part('clump', uvs=True)
    cross_cards(l1, [0, 0, 0], w, h, 'plant', yaw=0.2)
    return recipe(name, budget, mats, [l0], [(far_at, [l1])], cull=cull)


def shrub(name, seed):
    rng = random.Random(seed)
    mats = {'leaves': tex('shrub', '#c8301e')}
    l0 = Part('shrub', uvs=True)
    centre = [0, 0.55, 0]
    for k in range(2):
        a = k * math.pi / 2 + 0.3
        card(l0, [0, 0, 0], [math.cos(a), 0, math.sin(a)], 1.4, 1.1, 'leaves', lift=1.0)
    crown_cards(l0, rng, centre, [0.6, 0.45, 0.6], 7, 0.85, 'leaves', depth=0.9, ymin=-0.3, tilt=0.2)
    l1 = Part('shrub', uvs=True)
    cross_cards(l1, [0, 0, 0], 1.4, 1.1, 'leaves', yaw=0.3)
    flat_card(l1, [0, 0.8, 0], 1.1, 'leaves')
    return recipe(name, 24, mats, [l0], [(20, [l1])], cull=45)


def litter(name, cell, colour, radius, seed):
    """Fallen leaves: a low fan of eight triangles, its centre 6 cm up and its rim 3 cm. The
    leaves stay inside the octagon's inscribed circle, so its straight edges never show."""
    rng = random.Random(seed)
    mats = {'leaves': tex(cell, colour, double=False)}
    l0 = Part('patch', uvs=True)
    turn = rng.uniform(0, 1)
    rim = []
    for k in range(8):
        a = turn + 2 * math.pi * k / 8
        rim.append(([math.cos(a) * radius, 0.03, math.sin(a) * radius],
                    (0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a))))
    c = ([0, 0.06, 0], (0.5, 0.5))
    for k in range(8):
        p, q = rim[k], rim[(k + 1) % 8]
        pts = [c, q, p]
        n = cross(sub(pts[1][0], pts[0][0]), sub(pts[2][0], pts[0][0]))
        if n[1] < 0:
            pts = [c, p, q]
        l0.face([l0.vert(x, t) for x, t in pts], 'leaves')
    l1 = Part('patch', uvs=True)
    s = radius * 2
    card(l1, [0, 0.05, 0], [0, 1, 0], s, s, 'leaves', roll=turn)
    return recipe(name, 8, mats, [l0], [(16, [l1])], cull=40)


# ---------------------------------------------------------------- all of them

def build():
    out = {}
    out['tree_maple'] = maple('tree_maple', 101, 8.2, 3.8, 4.8, 2.0, 0.24, 3, 29, 90, 35)
    out['tree_maple_small'] = maple('tree_maple_small', 102, 4.6, 2.3, 2.8, 1.1, 0.13, 2, 17, 60, 30)
    out['tree_ginkgo'] = ginkgo('tree_ginkgo', 103, 90, 40)
    out['tree_cedar'] = cedar('tree_cedar', 104, 60, 45)
    out['tree_cedar_giant'] = giant('tree_cedar_giant', 105, 180)
    out['tree_cedar_sacred'] = sacred('tree_cedar_sacred', 106, 350)
    out['plant_fern'] = fern('plant_fern', 201)
    out['plant_sasa'] = upright_clump('plant_sasa', 'sasa', '#4f6a3a', 1.5, 0.7, 2, 12, 202, 40, 16)
    out['plant_bamboo'] = upright_clump('plant_bamboo', 'bamboo', '#a8b860', 1.25, 2.5, 2, 12, 203, 60, 25)
    out['plant_susuki'] = upright_clump('plant_susuki', 'susuki', '#c8b898', 0.9, 1.8, 1, 10, 204, 50, 20)
    out['plant_shrub'] = shrub('plant_shrub', 205)
    out['litter_red'] = litter('litter_red', 'litter_red', '#c8301e', 1.8, 301)
    out['litter_gold'] = litter('litter_gold', 'litter_gold', '#f0c030', 1.7, 302)
    # collision: trunks only
    out['tree_maple_col'] = collision_prism('tree_maple_col', [([0, 0, 0], 0.28), ([0, 2.0, 0], 0.22)], 4, math.pi / 4)
    out['tree_maple_small_col'] = collision_prism('tree_maple_small_col', [([0, 0, 0], 0.2), ([0, 1.1, 0], 0.2)], 4, math.pi / 4)
    out['tree_ginkgo_col'] = collision_prism('tree_ginkgo_col', [([0, 0, 0], 0.34), ([0, 4.0, 0], 0.28)], 4, math.pi / 4)
    out['tree_cedar_col'] = collision_prism('tree_cedar_col', [([0, 0, 0], 0.42), ([0, 8.0, 0], 0.32)], 4, math.pi / 4)
    out['tree_cedar_giant_col'] = collision_prism(
        'tree_cedar_giant_col', [([0, 0, 0], 1.06), ([0, 10, 0], 1.0), ([0, 20, 0], 0.97), ([0, 30, 0], 0.86)], 8)
    out['tree_cedar_sacred_col'] = collision_prism(
        'tree_cedar_sacred_col', [([0, 0, 0], 2.75), ([0, 6.4, 0], 2.3), ([0, 15, 0], 2.05)], 12)
    return out


def main():
    want = set(sys.argv[1:])
    for name, (r, tris) in build().items():
        if want and name not in want:
            continue
        (ASSETS / f'{name}.asset.json').write_text(json.dumps(r, indent=1) + '\n')
        print(f'{name}: triangles per level {tris}')


if __name__ == '__main__':
    main()
