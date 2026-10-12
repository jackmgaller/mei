"""Shared helpers for Fall Line's hero models (sled, gate, finish): a small mesh builder that
writes Asset Kit `mesh` nodes, ring lofts, and the Synergen artwork drawn with the OFL fonts in
tools/fonts. Imported by make_sled.py, ../gate/make_gate.py and ../finish/make_finish.py; it
writes nothing itself."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
FONTS = ROOT/'tools'/'fonts'

# The palette of the look (README, "Style sheet").
WHITE = '#f4f8fc'
PEARL = '#dfeef8'
CYAN = '#19c3ef'
BONDI = '#0a9cc4'
BLUE = '#1f5fff'
LIME = '#a8f02c'
TANGERINE = '#ff8a1f'
GRAPHITE = '#2a3340'
SILVER = '#c4ccd6'


def sub(a, b): return [a[0]-b[0], a[1]-b[1], a[2]-b[2]]
def add(a, b): return [a[0]+b[0], a[1]+b[1], a[2]+b[2]]
def mul(a, s): return [a[0]*s, a[1]*s, a[2]*s]
def dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(pts):
        q = pts[(i+1) % len(pts)]
        n[0] += (p[1]-q[1])*(p[2]+q[2])
        n[1] += (p[2]-q[2])*(p[0]+q[0])
        n[2] += (p[0]-q[0])*(p[1]+q[1])
    return n


class Mesh:
    """Vertices, polygons and one material per polygon; optional hand UVs per vertex."""

    def __init__(self):
        self.v, self.f, self.fm, self.uv = [], [], [], []

    def vert(self, p, uv=None):
        self.v.append([round(c, 5) for c in p])
        self.uv.append(uv)
        return len(self.v)-1

    def poly(self, idx, mat, want=None, inside=None):
        """A planar polygon (or a triangle) of vertex indices, wound so its normal points along
        `want` or away from the point `inside`."""
        pts = [self.v[i] for i in idx]
        n = newell(pts)
        if want is None:
            cen = mul([sum(p[k] for p in pts) for k in range(3)], 1/len(pts))
            want = sub(cen, inside)
        if dot(n, want) < 0:
            idx = list(reversed(idx))
        self.f.append(list(idx))
        self.fm.append(mat)

    def quad(self, a, b, c, d, mat, want=None, inside=None):
        """Two triangles (lofted quads are seldom exactly planar)."""
        self.poly([a, b, c], mat, want, inside)
        self.poly([a, c, d], mat, want, inside)

    def tris(self):
        return sum(len(f)-2 for f in self.f)

    def node(self, nid, material=None):
        n = {'id': nid, 'op': 'mesh', 'vertices': self.v, 'faces': self.f,
             'face_materials': self.fm}
        if any(u is not None for u in self.uv):
            n['uvs'] = [u if u is not None else [0, 0] for u in self.uv]
        if material:
            n['material'] = material
        return n


def loft(m, rings, mat, inside, cap_start=None, cap_end=None):
    """Joins rings of vertex indices (equal counts, closed loops; a ring of one index is a tip).
    mat(i, j): the material of the band between rings i and i+1, side j (from point j to j+1).
    inside(p): a point inside the solid near p, for winding. cap_start / cap_end: a material for a
    planar cap over the first / last ring."""
    for i in range(len(rings)-1):
        r0, r1 = rings[i], rings[i+1]
        n = max(len(r0), len(r1))
        for j in range(n):
            if len(r0) == 1:
                a, b, c = r0[0], r1[j], r1[(j+1) % n]
                cen = mul(add(add(m.v[a], m.v[b]), m.v[c]), 1/3)
                m.poly([a, b, c], mat(i, j), inside=inside(cen))
            elif len(r1) == 1:
                a, b, c = r0[j], r0[(j+1) % n], r1[0]
                cen = mul(add(add(m.v[a], m.v[b]), m.v[c]), 1/3)
                m.poly([a, b, c], mat(i, j), inside=inside(cen))
            else:
                a, b, c, d = r0[j], r0[(j+1) % n], r1[(j+1) % n], r1[j]
                cen = mul(add(add(m.v[a], m.v[b]), add(m.v[c], m.v[d])), 1/4)
                m.quad(a, b, c, d, mat(i, j), inside=inside(cen))
    for ring, cap in ((rings[0], cap_start), (rings[-1], cap_end)):
        if cap and len(ring) > 2:
            cen = mul([sum(m.v[i][k] for i in ring) for k in range(3)], 1/len(ring))
            m.poly(list(ring), cap, inside=inside(cen) if callable(inside) else inside)


def box_mesh(m, lo, hi, mat, skip=()):
    """An axis-aligned box as six quads (sides named as the kit's box: left -X, right +X, bottom,
    top, back -Z, front +Z); mat is a material or a dict side -> material."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    c = [(x0+x1)/2, (y0+y1)/2, (z0+z1)/2]
    P = {}
    for i, x in enumerate((x0, x1)):
        for j, y in enumerate((y0, y1)):
            for k, z in enumerate((z0, z1)):
                P[i, j, k] = (x, y, z)
    sides = {'left': [(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)],
             'right': [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],
             'bottom': [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],
             'top': [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)],
             'back': [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],
             'front': [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]}
    for name, corners in sides.items():
        if name in skip:
            continue
        idx = [m.vert(P[k]) for k in corners]
        mm = mat[name] if isinstance(mat, dict) else mat
        m.poly(idx, mm, inside=c)


def write_recipe(path, recipe):
    Path(path).write_text(json.dumps(recipe, indent=1)+'\n')


# ---- artwork --------------------------------------------------------------------------------

def _font(name, px):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTS/name), px)


def text_image(text, w, h, ink, bg, font='Figtree-BlackItalic.ttf', fill=0.8, scale=8,
               underline=None, y_frac=0.5, box=None):
    """`text` centred in a w x h image (drawn `scale` times larger and reduced), as tall as fits
    `fill` of the box (x0, y0, x1, y1 in texels; default the image). underline: (colour,
    thickness in texels, gap) for a swoosh under the word."""
    from PIL import Image, ImageDraw
    W, H = w*scale, h*scale
    im = Image.new('RGB', (W, H), bg)
    d = ImageDraw.Draw(im)
    bx0, by0, bx1, by1 = [c*scale for c in (box or (0, 0, w, h))]
    bw, bh = bx1-bx0, by1-by0
    size = 400
    f = _font(font, size)
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    k = min(bw*fill/(r-l), bh*fill/(b-t))
    f = _font(font, max(8, int(size*k)))
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    x = bx0+(bw-(r-l))/2-l
    y = by0+(bh-(b-t))*y_frac-t
    d.text((x, y), text, font=f, fill=ink)
    if underline:
        col, thick, gap = underline
        yy = y+b+gap*scale
        x0, x1 = x+l, x+r
        d.polygon([(x0, yy+thick*scale), (x1-thick*scale*1.5, yy+thick*scale),
                   (x1, yy), (x0+thick*scale*1.5, yy)], fill=col)
    return im.resize((w, h), Image.LANCZOS)


def chrome_strip(path, h=32, w=8):
    """Fake chrome: a vertical gradient strip, sky above a dark horizon and bright snow below
    (top row = the top of the surface)."""
    from PIL import Image
    stops = [(0.00, (236, 248, 255)), (0.14, (150, 212, 250)), (0.40, (56, 136, 220)),
             (0.48, (20, 36, 82)), (0.55, (84, 104, 146)), (0.72, (218, 230, 244)),
             (1.00, (128, 148, 180))]
    im = Image.new('RGB', (w, h))
    for y in range(h):
        t = (y+0.5)/h
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                a = (t-t0)/(t1-t0)
                col = tuple(round(c0[i]+(c1[i]-c0[i])*a) for i in range(3))
                break
        for x in range(w):
            im.putpixel((x, y), col)
    im.save(path)


def save(im, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
