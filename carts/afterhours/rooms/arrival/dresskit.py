"""What the dressing scripts of rooms 1 and 2 share (dress_arrival.py here, ../gates/dress_gates.py):
Asset Kit nodes and recipes, and the painting of light into textures.

Light, as the aquarium found it (rooms/aquarium/shots/NOTES.md): one list of point lights per room
drives both the Asset Kit's bake of the lit props (`lighting.lights`) and the painting of the
emissive floors and walls, which evaluate the kit's formula per texel

    shade = ambient + sum colour / 255 * intensity * max(0, n . l) * (1 - (d / range)^2)^2 * visibility

with soft shadows from boxes standing in for the props. A light may be a line (`line`: a length
along x, for a fluorescent tube): it is painted as samples along the line, and given to the kit
as one point at its middle.

Nothing here writes files but write_json and save_png.
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[4]
FONTS = ROOT / 'tools' / 'fonts'

CUT = '#76849e'          # the section's cut faces, emissive, as the aquarium's
VERIFY = {'required': True, 'depth': True, 'perspective': True}


def r(v, n=4):
    return round(float(v), n)


def box(id, lo, hi, material, **extra):
    """A box from corner lo to corner hi."""
    node = {'id': id, 'op': 'box', 'size': [r(h - l) for l, h in zip(lo, hi)], 'material': material,
            'transform': {'translate': [r((l + h) / 2) for l, h in zip(lo, hi)]}}
    node.update(extra)
    return node


def at(node, translate=None, rotate=None):
    t = {}
    if rotate:
        t['rotate'] = [r(a, 3) for a in rotate]
    if translate:
        t['translate'] = [r(c) for c in translate]
    node['transform'] = t
    return node


def newell(points):
    n = [0.0, 0.0, 0.0]
    for a, b in zip(points, points[1:] + points[:1]):
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


class Mesh:
    """Polygons for a `mesh` node, each turned to face the given direction."""

    def __init__(self):
        self.vertices, self.faces, self.materials = [], [], []
        self.index = {}

    def v(self, p):
        key = tuple(r(c, 5) for c in p)
        if key not in self.index:
            self.index[key] = len(self.vertices)
            self.vertices.append(list(key))
        return self.index[key]

    def poly(self, points, facing, material):
        n = newell(points)
        if sum(a * b for a, b in zip(n, facing)) < 0:
            points = list(reversed(points))
        self.faces.append([self.v(p) for p in points])
        self.materials.append(material)

    def quad_x(self, x, y0, y1, z0, z1, facing, material):
        self.poly([(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)], (facing, 0, 0), material)

    def quad_y(self, y, x0, x1, z0, z1, facing, material):
        self.poly([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], (0, facing, 0), material)

    def quad_z(self, z, x0, x1, y0, y1, facing, material):
        self.poly([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], (0, 0, facing), material)

    def prism(self, outline, z0, z1, side, front=None, back=None, sides=None):
        """An outline in (x, y) between z0 and z1: its -z face `back` (the camera's side), its +z face
        `front`, its walls `side` (or sides[k] for the wall from outline[k] to outline[k+1])."""
        if back:
            self.poly([(x, y, z0) for x, y in outline], (0, 0, -1), back)
        if front:
            self.poly([(x, y, z1) for x, y in outline], (0, 0, 1), front)
        cx = sum(p[0] for p in outline) / len(outline)
        cy = sum(p[1] for p in outline) / len(outline)
        for k, (a, b) in enumerate(zip(outline, outline[1:] + outline[:1])):
            m = (sides or {}).get(k, side)
            if m is None:
                continue
            ex, ey = b[0] - a[0], b[1] - a[1]
            nx, ny = ey, -ex                     # one of the two normals; turned outward below
            if nx * ((a[0] + b[0]) / 2 - cx) + ny * ((a[1] + b[1]) / 2 - cy) < 0:
                nx, ny = -nx, -ny
            self.poly([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], (nx, ny, 0), m)

    def node(self, id, material):
        node = {'id': id, 'op': 'mesh', 'material': material, 'vertices': self.vertices, 'faces': self.faces}
        if any(m != material for m in self.materials):
            node['face_materials'] = self.materials
        return node


def recipe(name, materials, nodes, lighting=None, triangles=600, collision=False):
    out = {'format': 'mei-asset', 'version': 1, 'name': name,
           'budget': {'vertices': 2048, 'triangles': triangles}, 'materials': materials, 'nodes': nodes}
    if lighting is not None:
        out['lighting'] = lighting
    if not collision:
        out['verification'] = dict(VERIFY)
    return out


def used_materials(nodes):
    used = set()

    def walk(ns):
        for n in ns:
            if 'material' in n:
                used.add(n['material'])
            used.update((n.get('faces') or {}).values())
            used.update(n.get('face_materials') or [])
            for d in n.get('decals', []):
                used.add(d['material'])
            walk(n.get('children', []))
    walk(nodes)
    return used


def kit_lights(lights, keep=None):
    """The room's lights as the Asset Kit takes them (a line light as one point at its middle)."""
    out = []
    for L in lights:
        if keep and L['id'] not in keep:
            continue
        k = {key: L[key] for key in ('id', 'at', 'color', 'intensity', 'range', 'shadows', 'radius') if key in L}
        k['at'] = [r(c) for c in k['at']]
        out.append(k)
    return out


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=1) + '\n'
    if not path.exists() or path.read_text() != text:
        path.write_text(text)
        print('wrote', path.relative_to(ROOT))


def save_png(img, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    old = Image.open(path).convert(img.mode) if path.exists() else None
    if old is None or old.size != img.size or old.tobytes() != img.tobytes():
        img.save(path)
        print('wrote', path.relative_to(ROOT))


# ---- painting (float RGB arrays, 0-255)

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0 - 0.5


def to_image(rgb, dither=5.0):
    h, w, _ = rgb.shape
    d = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w, None] * dither
    return Image.fromarray(np.clip(np.round(rgb + d), 0, 255).astype(np.uint8), 'RGB')


def hex_rgb(c):
    return np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def grid(x0, x1, y0, y1, w, h):
    """Texel centres of a texture fitted over [x0, x1] x [y0, y1], row 0 at y1 (as `fit` lays a
    face's texture: v down from its top, the top being +y on a wall and +z on a floor)."""
    xs = x0 + (np.arange(w) + 0.5) / w * (x1 - x0)
    ys = y1 - (np.arange(h) + 0.5) / h * (y1 - y0)
    return np.meshgrid(xs, ys)


def ray_blocked(P, S, boxes):
    """For points P (N x 3) and one light sample S: whether the segment P->S crosses any box
    (x0, y0, z0, x1, y1, z1)."""
    blocked = np.zeros(len(P), dtype=bool)
    D = S[None, :] - P
    with np.errstate(divide='ignore', invalid='ignore'):
        inv = 1.0 / np.where(np.abs(D) < 1e-9, 1e-9, D)
    for b in boxes:
        lo = np.array(b[:3])
        hi = np.array(b[3:])
        t0 = (lo[None, :] - P) * inv
        t1 = (hi[None, :] - P) * inv
        tmin = np.max(np.minimum(t0, t1), axis=1)
        tmax = np.min(np.maximum(t0, t1), axis=1)
        blocked |= (tmax >= np.maximum(tmin, 0.002)) & (tmin <= 0.995) & (tmax > 0.002)
    return blocked


def light_samples(L):
    """Points standing in for a light: along its line, and over its radius when it is soft."""
    lx, ly, lz = L['at']
    n = L.get('samples', 9 if L.get('line') else 1)
    pts = []
    for k in range(n):
        dx = 0.0 if n == 1 else (k / (n - 1) - 0.5) * L.get('line', 0.0)
        pts.append((lx + dx, ly, lz))
    rad = L.get('radius', 0.0)
    if rad and not L.get('line'):
        pts = [(lx + a * rad * 0.577, ly + b * rad * 0.577, lz + c * rad * 0.577)
               for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]
    return pts


def light_shade(P, normal, L, boxes=()):
    """One light's shade (N x 3, per channel) at points P (N x 3) on a surface facing `normal`,
    by the kit's formula; a line light is the mean of its samples."""
    n = np.array(normal, dtype=float)
    n /= np.linalg.norm(n)
    total = np.zeros(len(P))
    samples = light_samples(L)
    skip = L.get('no_shadow_from', ())
    use = [b for i, b in enumerate(boxes) if i not in skip] if L.get('shadows') else []
    for S in samples:
        S = np.array(S, dtype=float)
        D = S[None, :] - P
        d = np.linalg.norm(D, axis=1)
        ndl = np.clip((D @ n) / np.maximum(d, 1e-6), 0, None)
        fall = np.clip(1 - (d / L['range']) ** 2, 0, None) ** 2
        k = L.get('intensity', 1.0) * ndl * fall
        if use:
            k = k * ~ray_blocked(P, S, use)
        if 'zmin' in L:               # a light that reaches only beyond a plane (out through a window)
            k = k * (P[:, 2] > L['zmin'])
        total += k
    total /= len(samples)
    return total[:, None] * hex_rgb(L.get('color', '#ffffff'))[None, :] / 255


def shade_plane(P, normal, lights, ambient, boxes=()):
    out = np.zeros((len(P), 3)) + ambient
    for L in lights:
        out += light_shade(P, normal, L, boxes)
    return out


def blob(x, y, cx, cy, sx, sy=None):
    """A soft round spot, 1 at its centre."""
    sy = sx if sy is None else sy
    return np.exp(-(((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2))


def rect(x, y, x0, y0, x1, y1, soft=0.0):
    """1 inside the rectangle, with a soft edge `soft` wide."""
    if soft <= 0:
        return ((x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)).astype(float)
    return (smoothstep(x0 - soft, x0 + soft, x) * (1 - smoothstep(x1 - soft, x1 + soft, x)) *
            smoothstep(y0 - soft, y0 + soft, y) * (1 - smoothstep(y1 - soft, y1 + soft, y)))


def noise(h, w, seed, scale=1.0):
    return np.random.default_rng(seed).random((h, w)) * scale


def text_image(size, text, fnt, fill, bg=(0, 0, 0, 0), anchor='mm', at=None):
    img = Image.new('RGBA', size, bg)
    ImageDraw.Draw(img).text(at or (size[0] / 2, size[1] / 2), text, font=fnt, fill=fill, anchor=anchor)
    return img
