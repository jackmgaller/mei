"""Shared pieces for shrine town's architecture recipes (arch_wall_gate, arch_chozuya,
arch_shrine_office): explicit `mesh` parts with hand UVs, built the way the shrine's halls, gate
and wall are built (carts/garden/shrine/assets/arch_*.asset.json), on the shrine's architecture
textures (carts/garden/shrine/assets/art/arch_*.png).

Imported by the three generators (make_*.py); writes nothing itself.
"""
import json
import math
from pathlib import Path

LIGHT = {'mode': 'vertical', 'ambient': 0.5}
POLICY = {'required': True, 'depth': True, 'perspective': True}
ART = '../../../shrine/assets/art/'


def _tex(name, projection='planar'):
    return {'image': ART + name, 'projection': projection}


# The shrine's architecture materials, with the names and colours the built halls use.
MATERIALS = {
    'tile': {'color': '#565c64', 'texture': _tex('arch_tile.png')},
    'bay': {'color': '#ece4d2', 'texture': _tex('arch_bay.png')},
    'bay_doors': {'color': '#d8462a', 'texture': _tex('arch_bay_doors.png')},
    'small_bay': {'color': '#ece4d2', 'texture': _tex('arch_small_bay.png')},
    'stone': {'color': '#b4ae9e', 'texture': _tex('arch_stone.png')},
    'rafters': {'color': '#a8321e', 'texture': _tex('arch_rafters.png')},
    'gaku': {'color': '#2c2a28', 'texture': _tex('arch_gaku.png', 'fit')},
    'wall_cap': {'color': '#3e4248', 'texture': _tex('arch_wall_cap.png', 'fit')},
    'footing': {'color': '#b4ae9e', 'texture': _tex('arch_wall_footing.png', 'fit')},
    'lacquer': {'color': '#d8462a', 'palette': True},
    'shade': {'color': '#a8321e', 'palette': True},
    'plaster': {'color': '#ece4d2', 'palette': True},
    'tile_dark': {'color': '#3e4248', 'palette': True},
    'stone_pal': {'color': '#b4ae9e', 'palette': True},
    'black': {'color': '#2c2a28', 'palette': True},
    'gold': {'color': '#d8b048', 'palette': True},
    'wood': {'color': '#5a3e2c', 'palette': True},
    'wood_new': {'color': '#b08a5e', 'palette': True},
    'copper': {'color': '#7a8a70', 'palette': True},
    'water': {'color': '#3f7393', 'palette': True},
    'lantern': {'color': '#f0b050', 'class': 'emissive'},
}


def materials(*names, extra=None):
    out = {n: MATERIALS[n] for n in names}
    out.update(extra or {})
    return out


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(a):
    n = math.sqrt(dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def r4(v):
    return round(v + 0.0, 4)


class Part:
    """One `mesh` node: each face keeps its own corners, so each can carry its own UVs."""

    def __init__(self, pid):
        self.id = pid
        self.v, self.f, self.m, self.uv = [], [], [], []

    def face(self, mat, pts, uvs=None):
        """A planar polygon, corners clockwise as seen from outside (TL, TR, BR, BL for a quad)."""
        base = len(self.v)
        for k, p in enumerate(pts):
            self.v.append([r4(c) for c in p])
            self.uv.append([r4(c) for c in uvs[k]] if uvs else [0.0, 0.0])
        self.f.append(list(range(base, base + len(pts))))
        self.m.append(mat)

    def face_uv(self, mat, pts, su=1.0, sv=None, origin=(0, 0, 0), up=None):
        """A face whose UVs run as the face is seen from outside: u right, v down, `su`/`sv` world
        units a repeat, from `origin`. Up is world +Y projected into the face (+Z for a face
        looking straight up or down) unless `up` is given."""
        sv = su if sv is None else sv
        n = unit(cross(sub(pts[1], pts[0]), sub(pts[2], pts[0])))
        if up is None:
            up = (0.0, 0.0, 1.0) if abs(n[1]) > 0.999 else (0.0, 1.0, 0.0)
            if abs(n[1]) > 0.999 and n[1] < 0:
                up = (0.0, 0.0, -1.0)
        upp = sub(up, tuple(dot(up, n) * c for c in n))
        upp = unit(upp)
        right = unit(cross(n, upp))
        uvs = [(dot(sub(p, origin), right) / su, -dot(sub(p, origin), upp) / sv) for p in pts]
        self.face(mat, pts, uvs)

    def box(self, mats, x0, x1, y0, y1, z0, z1, open=(), su=1.0, sv=None, crop=None):
        """An axis-aligned box. `mats` is one material or a dict by side (top, bottom, left,
        right, back = -Z, front = +Z, as the kit's boxes). `crop` (dict by side) maps a side's
        whole face onto a texture rectangle [u0, v0, u1, v1] in repeats instead."""
        sides = {
            'back': [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)],
            'front': [(x1, y1, z1), (x0, y1, z1), (x0, y0, z1), (x1, y0, z1)],
            'right': [(x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (x1, y0, z0)],
            'left': [(x0, y1, z1), (x0, y1, z0), (x0, y0, z0), (x0, y0, z1)],
            'top': [(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)],
            'bottom': [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
        }
        for side, pts in sides.items():
            if side in open:
                continue
            mat = mats.get(side, mats.get('*')) if isinstance(mats, dict) else mats
            if crop and side in crop:
                u0, v0, u1, v1 = crop[side]
                self.face(mat, pts, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
            else:
                self.face_uv(mat, pts, su, sv)

    def node(self):
        return {'id': self.id, 'op': 'mesh', 'vertices': self.v, 'faces': self.f,
                'face_materials': self.m, 'uvs': self.uv}

    def tris(self):
        return sum(len(f) - 2 for f in self.f)


def mirror_x(pts):
    """The same polygon mirrored across x = 0, corners reordered to stay outward."""
    return [(-p[0], p[1], p[2]) for p in reversed(pts)]


def mirror_z(pts):
    return [(p[0], p[1], -p[2]) for p in reversed(pts)]


def col_box(part, x0, x1, y0, y1, z0, z1, step=2.0, open=()):
    """A collision box with its faces cut into pieces no longer than `step` (so no long thin
    floor triangles), corners shared along the cuts."""
    def cuts(a, b):
        n = max(1, int(math.ceil((b - a) / step - 1e-9)))
        return [a + (b - a) * k / n for k in range(n + 1)]
    xs, ys, zs = cuts(x0, x1), cuts(y0, y1), cuts(z0, z1)
    grid_face(part, 'top', [(x, y1, z) for z in zs[::-1] for x in xs], len(xs), open)
    grid_face(part, 'bottom', [(x, y0, z) for z in zs for x in xs], len(xs), open)
    grid_face(part, 'back', [(x, y, z0) for y in ys[::-1] for x in xs], len(xs), open)
    grid_face(part, 'front', [(x, y, z1) for y in ys[::-1] for x in xs[::-1]], len(xs), open)
    grid_face(part, 'right', [(x1, y, z) for y in ys[::-1] for z in zs], len(zs), open)
    grid_face(part, 'left', [(x0, y, z) for y in ys[::-1] for z in zs[::-1]], len(zs), open)


def grid_face(part, side, pts, ncols, open=()):
    if side in open:
        return
    rows = [pts[i:i + ncols] for i in range(0, len(pts), ncols)]
    for r in range(len(rows) - 1):
        for c in range(ncols - 1):
            part.face('solid', [rows[r][c], rows[r][c + 1], rows[r + 1][c + 1], rows[r + 1][c]])


def col_quad(part, p00, p10, p11, p01, step=2.0):
    """A collision quad (TL, TR, BR, BL from outside) cut into a grid of pieces <= step."""
    def lerp(a, b, t):
        return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
    w = max(math.dist(p00, p10), math.dist(p01, p11))
    h = max(math.dist(p00, p01), math.dist(p10, p11))
    nu, nv = max(1, math.ceil(w / step - 1e-9)), max(1, math.ceil(h / step - 1e-9))
    for j in range(nv):
        for i in range(nu):
            def P(a, b):
                return lerp(lerp(p00, p10, a), lerp(p01, p11, a), b)
            part.face('solid', [P(i / nu, j / nv), P((i + 1) / nu, j / nv),
                                P((i + 1) / nu, (j + 1) / nv), P(i / nu, (j + 1) / nv)])


def gable_roof(p, ex, ez, lo, hi, ridge, gable='lacquer'):
    """A gabled roof, ridge along X at `ridge`, eaves at z +-ez from x -ex to ex: tiled slopes
    (a repeat 2 m, from the eave), fascias lo-hi, a rafter soffit parallel to the slopes, and
    chevron gable ends (bargeboards) closing it at x +-ex."""
    rlo = ridge - (hi - lo)
    for s in (-1, 1):
        if s < 0:
            pts = [(-ex, ridge, 0.0), (ex, ridge, 0.0), (ex, hi, -ez), (-ex, hi, -ez)]
            sp = [(-ex, lo, -ez), (ex, lo, -ez), (ex, rlo, 0.0), (-ex, rlo, 0.0)]
            fp = [(-ex, hi, -ez), (ex, hi, -ez), (ex, lo, -ez), (-ex, lo, -ez)]
        else:
            pts = [(ex, ridge, 0.0), (-ex, ridge, 0.0), (-ex, hi, ez), (ex, hi, ez)]
            sp = [(ex, lo, ez), (-ex, lo, ez), (-ex, rlo, 0.0), (ex, rlo, 0.0)]
            fp = [(ex, hi, ez), (-ex, hi, ez), (-ex, lo, ez), (ex, lo, ez)]
        p.face_uv('tile', pts, 2.0, 2.0, origin=pts[3])     # v 0 at the eave, as the halls
        p.face_uv('rafters', sp, 1.0, 1.0)
        p.face('tile_dark', fp)
    plus = [(ex, y, z) for z, y in [(-ez, hi), (0.0, ridge), (ez, hi), (ez, lo), (0.0, rlo),
                                    (-ez, lo)]]
    p.face(gable, plus)
    p.face(gable, mirror_x(plus))


def irimoya(p, eave, inner, wall, ridge, corner, lift, fascia):
    """A hip-and-gable roof as the shrine's halls have (arch_side_hall's main roof): a hipped
    skirt from the eaves up to an inner rectangle, then a gable over that to the ridge (along X).

    eave = (ex, ez, y): the eave's outline and its top; inner = (ix, iz, y); wall = (wx, wz, y):
    where the rafter soffit meets the walls; corner: the length of the turned-up corner at each
    end of an eave; lift: how far the corners turn up; fascia: the eave's thickness.
    Returns the gable's (ix, iz, yi, yr) for the bargeboards."""
    ex, ez, yh = eave
    ix, iz, yi = inner
    wx, wz, yw = wall
    c, L, t = corner, lift, fascia
    # each side in (a, y, b): a along the eave (right as seen from outside), b outward
    sides = [
        (lambda a, y, b: (a, y, -b), ex, ez, ix, iz, wx, wz),      # front, -Z
        (lambda a, y, b: (b, y, a), ez, ex, iz, ix, wz, wx),       # right, +X
        (lambda a, y, b: (-a, y, b), ex, ez, ix, iz, wx, wz),      # back, +Z
        (lambda a, y, b: (-b, y, -a), ez, ex, iz, ix, wz, wx),     # left, -X
    ]
    for P, A, B, Ai, Bi, Aw, Bw in sides:
        s = A - c
        top = [P(-Ai, yi, Bi), P(Ai, yi, Bi), P(s, yh, B), P(-s, yh, B)]
        p.face_uv('tile', top, 2.0, 2.0, origin=P(-A, yh, B))
        p.face_uv('tile', [P(Ai, yi, Bi), P(A, yh + L, B), P(s, yh, B)], 2.0, 2.0,
                  origin=P(-A, yh, B))
        p.face_uv('tile', [P(-Ai, yi, Bi), P(-s, yh, B), P(-A, yh + L, B)], 2.0, 2.0,
                  origin=P(-A, yh, B))
        p.face('tile_dark', [P(-A, yh + L, B), P(-s, yh, B), P(-s, yh - t, B), P(-A, yh + L - t, B)])
        p.face('tile_dark', [P(-s, yh, B), P(s, yh, B), P(s, yh - t, B), P(-s, yh - t, B)])
        p.face('tile_dark', [P(s, yh, B), P(A, yh + L, B), P(A, yh + L - t, B), P(s, yh - t, B)])
        p.face_uv('rafters', [P(-s, yh - t, B), P(s, yh - t, B), P(Aw, yw, Bw), P(-Aw, yw, Bw)], 1.0)
        p.face_uv('rafters', [P(s, yh - t, B), P(A, yh + L - t, B), P(Aw, yw, Bw)], 1.0)
        p.face_uv('rafters', [P(-A, yh + L - t, B), P(-s, yh - t, B), P(-Aw, yw, Bw)], 1.0)
    # the gable over the inner rectangle
    for s in (-1, 1):
        if s < 0:
            pts = [(-ix, ridge, 0.0), (ix, ridge, 0.0), (ix, yi, -iz), (-ix, yi, -iz)]
        else:
            pts = [(ix, ridge, 0.0), (-ix, ridge, 0.0), (-ix, yi, iz), (ix, yi, iz)]
        p.face_uv('tile', pts, 2.0, 2.0, origin=pts[3])
    tri = [(ix, ridge, 0.0), (ix, yi, iz), (ix, yi, -iz)]
    p.face('plaster', tri)
    p.face('plaster', mirror_x(tri))
    return ix, iz, yi, ridge


def bargeboards(p, ix, iz, yi, yr, out=0.12, depth=0.08, over=0.2, up=0.07, down=0.2):
    """Lacquered bargeboards on the gables of `irimoya`: a chevron each, its faces at x +-(ix +
    out) and +-(ix + out - depth), standing `up` over the gable's slope and `down` under it, and
    running `over` past the gable's foot."""
    k = (yr - yi) / iz
    a = iz + over
    ya = yi - over * k
    hexa = [(-a, ya + up), (0.0, yr + up), (a, ya + up), (a, ya - down), (0.0, yr - down),
            (-a, ya - down)]                     # (z, y), clockwise as seen from +X
    for x, outward in ((ix + out, True), (ix + out - depth, False)):
        pts = [(x, y, z) for z, y in hexa]
        if not outward:
            pts = mirror_x(mirror_x(pts))[::-1]
        p.face('lacquer', pts)
        p.face('lacquer', mirror_x(pts))


def ridge_cap(p, x, y0, y1, half, oni=None):
    """The ridge: a dark tile beam from x -x to x, y0-y1, z +-half, and (oni = (width, top,
    half depth)) end tiles standing over its ends."""
    p.box('tile_dark', -x, x, y0, y1, -half, half, open=('bottom',))
    if oni:
        w, top, hz = oni
        for s in (-1, 1):
            x0, x1 = sorted((s * (x - 0.1), s * (x - 0.1 + w)))
            p.box('tile_dark', x0, x1, y0 - 0.04, top, -hz, hz, open=('bottom',))


def recipe(name, mats, parts, budget=None, lod=None):
    r = {'format': 'mei-asset', 'version': 1, 'name': name}
    if budget:
        r['budget'] = {'triangles': budget}
    r['materials'] = mats
    r['lighting'] = LIGHT
    r['verification'] = POLICY
    r['nodes'] = [p.node() if isinstance(p, Part) else p for p in parts
                  if not isinstance(p, Part) or p.f]
    if lod:
        r['lod'] = {'levels': [{'distance': d, 'nodes': [q.node() if isinstance(q, Part) else q
                                                         for q in qs if not isinstance(q, Part) or q.f]}
                               for d, qs in lod['levels']], 'band': lod.get('band', 2)}
        if 'cull' in lod:
            r['lod']['cull'] = lod['cull']
    return r


def col_recipe(name, parts):
    return recipe(name, {'solid': {'color': '#ffffff', 'palette': True}}, parts)


def write(path, data):
    """JSON with short numeric arrays kept on one line, as the shrine's recipes are."""
    text = json.dumps(data, indent=1)
    import re
    # fold [a, b, c] number lists onto one line
    text = re.sub(r'\[\s+(-?[\d.]+(?:,\s+-?[\d.]+)*)\s+\]',
                  lambda m: '[' + ','.join(s.strip() for s in m.group(1).split(',')) + ']', text)
    Path(path).write_text(text + '\n')
