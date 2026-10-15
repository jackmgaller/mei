"""Helpers rooms 3 and 4's dressing scripts share (dress_passage.py here, ../lobby/dress_lobby.py):
Asset Kit recipe pieces, the rooms' light evaluated on painted surfaces by the kit's own formula,
and painting. Writes nothing itself.

The light: a room keeps one list of point lights in the Asset Kit's form (`lighting.lights`). The
kit bakes it into the walls' and props' vertex colours; `shade()` evaluates the same formula on a
grid of points of a painted surface (the floor, a wall), with soft shadows cast by boxes, so that
the painted surfaces and the lit props agree. Painted surfaces are emissive: the kit spends no
refinement triangles on them (rooms/aquarium/shots/NOTES.md).

8-bit textures share one 256-colour palette per room: `quantise_together()` reduces a room's
8-bit paintings to one set of at most 255 15-bit colours, so the packer can put them all in one
8-bit palette (the level has 16 for every room together).
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[4]
FONTS = ROOT / 'tools' / 'fonts'

CUT = 1.0          # the section: everything in the play area is cut at 1 m
WALL_H = 2.4       # the section's ceiling


def r(v, n=4):
    return round(float(v), n)


def hexc(rgb):
    return '#%02x%02x%02x' % tuple(int(max(0, min(255, round(c)))) for c in rgb)


def hex_rgb(c):
    return np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)


# ---- recipe pieces

def box(id, lo, hi, material, **extra):
    """A box from corner lo to corner hi."""
    node = {'id': id, 'op': 'box', 'size': [r(h - l) for l, h in zip(lo, hi)], 'material': material,
            'transform': {'translate': [r((l + h) / 2) for l, h in zip(lo, hi)]}}
    node.update(extra)
    return node


def at(node, translate=None, rotate=None, scale=None):
    t = {}
    if scale:
        t['scale'] = [r(s) for s in scale]
    if rotate:
        t['rotate'] = [r(a, 3) for a in rotate]
    if translate:
        t['translate'] = [r(c) for c in translate]
    node['transform'] = t
    return node


def group(id, children):
    return {'id': id, 'op': 'group', 'children': children}


def newell(points):
    n = [0.0, 0.0, 0.0]
    for a, b in zip(points, points[1:] + points[:1]):
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


class Mesh:
    """Polygons for a `mesh` node, each turned to face a given direction, with optional hand UVs
    (a function of the corner's position) and a material per polygon."""

    def __init__(self):
        self.vertices, self.faces, self.materials, self.uvs = [], [], [], []
        self.index = {}

    def v(self, p, uv=None):
        key = tuple(r(c, 5) for c in p) + ((r(uv[0], 5), r(uv[1], 5)) if uv is not None else ())
        if key not in self.index:
            self.index[key] = len(self.vertices)
            self.vertices.append([r(c, 5) for c in p])
            self.uvs.append([r(uv[0], 5), r(uv[1], 5)] if uv is not None else None)
        return self.index[key]

    def poly(self, points, facing, material=None, uv=None):
        n = newell(points)
        if sum(a * b for a, b in zip(n, facing)) < 0:
            points = list(reversed(points))
        self.faces.append([self.v(p, uv(p) if uv else None) for p in points])
        self.materials.append(material)

    def quad(self, x0, y0, z0, x1, y1, z1, facing, material=None, uv=None):
        """An axis-aligned rectangle: one of the extents is zero (the plane it lies in)."""
        if x0 == x1:
            pts = [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)]
        elif y0 == y1:
            pts = [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]
        else:
            pts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)]
        self.poly(pts, facing, material, uv)

    def node(self, id, material):
        node = {'id': id, 'op': 'mesh', 'material': material, 'vertices': self.vertices, 'faces': self.faces}
        if any(m for m in self.materials):
            node['face_materials'] = [m or material for m in self.materials]
        if any(u is not None for u in self.uvs):
            node['uvs'] = [u if u is not None else [0, 0] for u in self.uvs]
        return node


def recipe(name, materials, nodes, lighting, triangles, prototypes=None):
    out = {'format': 'mei-asset', 'version': 1, 'name': name,
           'budget': {'vertices': 2048, 'triangles': triangles}, 'materials': materials}
    if prototypes:
        out['prototypes'] = prototypes
    out['nodes'] = nodes
    out['lighting'] = lighting
    out['verification'] = {'required': True, 'depth': True, 'perspective': True}
    return out


def collision_recipe(name, nodes, triangles=400):
    """A collision companion: floors and walls (walls without tops), one plain material."""
    return {'format': 'mei-asset', 'version': 1, 'name': name,
            'budget': {'vertices': 2048, 'triangles': triangles},
            'lighting': {'direction': [-0.35, 0.85, -0.45], 'ambient': 0.55},
            'materials': {'floor': {'color': '#8c9098'}}, 'nodes': nodes}


def write_json(path, data):
    path = Path(path)
    text = json.dumps(data, indent=1) + '\n'
    if not path.exists() or path.read_text() != text:
        path.write_text(text)
        return True
    return False


# ---- light on painted surfaces, by the kit's formula

def _visible(px, py, pz, sx, sy, sz, blockers):
    """Whether each segment from (px, py, pz) (arrays) to the point (sx, sy, sz) misses every
    box (x0, y0, z0, x1, y1, z1)."""
    ok = np.ones(px.shape, dtype=bool)
    dx, dy, dz = sx - px, sy - py, sz - pz
    for (x0, y0, z0, x1, y1, z1) in blockers:
        t0 = np.full(px.shape, 1e-3)
        t1 = np.full(px.shape, 1 - 1e-3)
        for p, d, lo, hi in ((px, dx, x0, x1), (py, dy, y0, y1), (pz, dz, z0, z1)):
            with np.errstate(divide='ignore', invalid='ignore'):
                a = (lo - p) / d
                b = (hi - p) / d
            near = np.where(np.abs(d) < 1e-12, np.where((p > lo) & (p < hi), -np.inf, np.inf), np.minimum(a, b))
            far = np.where(np.abs(d) < 1e-12, np.where((p > lo) & (p < hi), np.inf, -np.inf), np.maximum(a, b))
            t0 = np.maximum(t0, near)
            t1 = np.minimum(t1, far)
        ok &= ~(t0 < t1)
    return ok


def light_term(px, py, pz, normal, light, blockers=(), samples=None):
    """One light's share, per point, before its colour: intensity x max(0, n.l) x falloff x
    visibility. A light may be a tube: `tube` [dx, dy, dz] spreads it along that half-length
    (painting only; the kit sees its centre)."""
    lx, ly, lz = light['at']
    tube = light.get('tube')
    centres = [(lx, ly, lz)]
    if tube:
        k = 5
        centres = [(lx + tube[0] * s, ly + tube[1] * s, lz + tube[2] * s) for s in np.linspace(-1, 1, k)]
    rng = light['range']
    total = np.zeros(px.shape)
    for cx, cy, cz in centres:
        ddx, ddy, ddz = cx - px, cy - py, cz - pz
        d = np.sqrt(ddx * ddx + ddy * ddy + ddz * ddz) + 1e-9
        ndotl = np.maximum(0, (normal[0] * ddx + normal[1] * ddy + normal[2] * ddz) / d)
        fall = np.clip(1 - (d / rng) ** 2, 0, None) ** 2
        k = light.get('intensity', 1.0) * ndotl * fall
        if light.get('shadows') and blockers:
            rad = light.get('radius', 0.0)
            # a soft light: points spread through its sphere (more than the kit's 8, for smooth
            # penumbrae in a painting)
            n = samples or 24
            offs = [(0, 0, 0)] if rad == 0 else [
                (rad * math.sqrt(1 - (1 - 2 * (i + 0.5) / n) ** 2) * math.cos(i * 2.39996) * ((i % 3 + 1) / 3) ** 0.33,
                 rad * (1 - 2 * (i + 0.5) / n) * ((i % 3 + 1) / 3) ** 0.33,
                 rad * math.sqrt(1 - (1 - 2 * (i + 0.5) / n) ** 2) * math.sin(i * 2.39996) * ((i % 3 + 1) / 3) ** 0.33)
                for i in range(n)]
            vis = np.zeros(px.shape)
            live = k > 1e-4
            for ox, oy, oz in offs:
                v = np.zeros(px.shape, dtype=bool)
                v[live] = _visible(px[live], py[live], pz[live], cx + ox, cy + oy, cz + oz, blockers)
                vis += v
            k = k * vis / len(offs)
        total += k
    return total / len(centres)


def shade(px, py, pz, normal, lights, ambient, diffuse=0.0, direction=(0, 1, 0), blockers=(), extra=None):
    """The kit's shade per point and channel (h, w, 3): ambient + diffuse x the directional term +
    the lights. extra(light, term) may reshape a light's term (a floor's shimmer)."""
    dvec = np.array(direction, dtype=float)
    dvec /= np.linalg.norm(dvec)
    base = ambient + diffuse * max(0.0, float(np.dot(dvec, normal)))
    out = np.zeros(px.shape + (3,)) + base
    for light in lights:
        t = light_term(px, py, pz, normal, light, blockers)
        if extra:
            t = extra(light, t)
        out += t[..., None] * hex_rgb(light.get('color', '#ffffff'))[None, None, :] / 255
    return out


def grid_floor(x0, x1, z0, z1, w, h, y=0.0):
    """Texel centres of a floor texture: x left to right, z from the back (top row) to the front."""
    xs = x0 + (np.arange(w) + 0.5) / w * (x1 - x0)
    zs = z1 - (np.arange(h) + 0.5) / h * (z1 - z0)
    x, z = np.meshgrid(xs, zs)
    return x, np.full(x.shape, y), z


def grid_wall_z(x0, x1, y0, y1, w, h, z):
    """Texel centres of a wall facing -z (seen from the room's camera): x left to right, y top down."""
    xs = x0 + (np.arange(w) + 0.5) / w * (x1 - x0)
    ys = y1 - (np.arange(h) + 0.5) / h * (y1 - y0)
    x, y = np.meshgrid(xs, ys)
    return x, y, np.full(x.shape, z)


# ---- painting

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0 - 0.5


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def soft_rect(x, z, x0, x1, z0, z1, soft):
    """1 inside the rectangle, falling to 0 over `soft` outside it."""
    dx = np.maximum(np.maximum(x0 - x, x - x1), 0)
    dz = np.maximum(np.maximum(z0 - z, z - z1), 0)
    return 1 - smoothstep(0, soft, np.hypot(dx, dz))


def blob(x, z, cx, cz, rx, rz):
    return np.exp(-(((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2))


def to_array(rgb, dither=6.0):
    """Float RGB (h, w, 3) to 8-bit with ordered dither."""
    h, w, _ = rgb.shape
    d = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w, None] * dither
    return np.clip(np.round(rgb + d), 0, 255).astype(np.uint8)


def to15(a):
    """8-bit RGB as the GPU's 15-bit colour shows it, back in 8 bits (each channel's 5 bits)."""
    q = (a.astype(int) * 31 + 127) // 255
    return (q * 255 + 15) // 31


def quantise_together(arrays, colours=255):
    """Reduces several 8-bit RGB arrays to one shared set of at most `colours` 15-bit colours
    (median cut over all of them), so they share one 8-bit palette. Returns images."""
    flat = np.concatenate([to15(a).reshape(-1, 3) for a in arrays], axis=0)
    strip = Image.fromarray(flat.reshape(1, -1, 3).astype(np.uint8), 'RGB')
    q = strip.quantize(colors=colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = np.array(q.getpalette()[:colours * 3]).reshape(-1, 3)
    pal = to15(pal)
    idx = np.array(q).reshape(-1)
    mapped = pal[idx].astype(np.uint8)
    out, k = [], 0
    for a in arrays:
        n = a.shape[0] * a.shape[1]
        out.append(Image.fromarray(mapped[k:k + n].reshape(a.shape), 'RGB'))
        k += n
    return out


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def pictogram_canvas(w, h, bg):
    img = Image.new('RGB', (w, h), bg)
    d = ImageDraw.Draw(img)
    d.fontmode = '1'
    return img, d


# ---- painted surfaces cut into pieces (stage 2's rooms: floors with holes, walls with doorways)

def rects_minus(rect, holes):
    """The rectangle (a0, b0, a1, b1) less the holes, as rectangles: a grid on every edge, the cells
    outside every hole, merged along a into strips."""
    a0, b0, a1, b1 = rect
    xs = sorted({a0, a1} | {v for h in holes for v in (h[0], h[2]) if a0 < v < a1})
    zs = sorted({b0, b1} | {v for h in holes for v in (h[1], h[3]) if b0 < v < b1})
    out = []
    for za, zb in zip(zs, zs[1:]):
        run = None
        for xa, xb in zip(xs, xs[1:]):
            cx, cz = (xa + xb) / 2, (za + zb) / 2
            inside = any(h[0] < cx < h[2] and h[1] < cz < h[3] for h in holes)
            if inside:
                if run:
                    out.append((run[0], za, run[1], zb))
                run = None
            else:
                run = (run[0], xb) if run else (xa, xb)
        if run:
            out.append((run[0], za, run[1], zb))
    return out


def painted_floor(mesh, splits_x, splits_z, holes, name, y=0.0):
    """Floor quads, one painted texture per cell of the splits (material name.format(j, i), j the
    row from the front, i the column from the left), less the holes, mapped by hand onto their
    cell's texture (u along x, v from the back edge)."""
    for j, (za, zb) in enumerate(zip(splits_z, splits_z[1:])):
        for i, (xa, xb) in enumerate(zip(splits_x, splits_x[1:])):
            uv = (lambda xa, xb, za, zb: lambda p: ((p[0] - xa) / (xb - xa), (zb - p[2]) / (zb - za)))(xa, xb, za, zb)
            for (x0, z0, x1, z1) in rects_minus((xa, za, xb, zb), holes):
                mesh.quad(x0, y, z0, x1, y, z1, (0, 1, 0), name.format(j, i), uv)


def painted_wall_z(mesh, splits_x, x0, x1, y0, y1, z, name, height, facing=(0, 0, -1)):
    """A rectangle of a wall facing -z (at z), mapped by hand onto the painted textures that cover
    the wall from y 0 to `height` between the splits (material name.format(k))."""
    for k, (a, b) in enumerate(zip(splits_x, splits_x[1:])):
        lo, hi = max(x0, a), min(x1, b)
        if hi - lo > 1e-6:
            uv = (lambda a, b: lambda p: ((p[0] - a) / (b - a), (height - p[1]) / height))(a, b)
            mesh.quad(lo, y0, z, hi, y1, z, facing, name.format(k), uv)
