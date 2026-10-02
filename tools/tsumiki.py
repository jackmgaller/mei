#!/usr/bin/env python3
"""Tsumiki (積み木) toy builder: turns a .toy file into Mei meshes and Akari data.

    python3 tools/tsumiki.py toys.toy -o carts/mygame          # writes toys.akr + .bin files
    python3 tools/tsumiki.py --stdlib                          # rebuilds stdlib/tsumiki/atlas.akr

A .toy file describes, one statement per line:

  * texture cells (patterns or PNG images packed into a 4-bit texture slot),
  * static meshes made of block primitives (box, ramp, cylinder, cone, sphere, grid, star),
  * rigs: trees of rigid parts, each a mesh that turns about its joint,
  * animation clips: keyframes per part (rotation in degrees, movement in units),
  * morphs: a mesh plus extra vertex poses (blinks, squashes) made by moving its vertices.

The full format is in docs/TSUMIKI.md ("The toy file"). The same builder is a Python API:

    import tsumiki as tk
    toy = tk.Toy('toys')
    toy.mesh('star'); toy.paint('yellow'); toy.star(0, 0, 0, 0.5, 0.22, 0.2)
    toy.write('carts/mygame')

Shapes are lit when they are built, with the same light as stdlib/tsumiki/shapes.akr: a sun
from the upper left in front (so faces turned to a camera at -Z looking +Z read best), on top
of an ambient level. Front faces wind counter-clockwise as seen from outside."""
import math, os, re, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshlib import Mesh as _MeiMesh

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------- shared constants

# The light, as in stdlib/tsumiki/base.akr (keep the two in step).
LIGHT = (-0.4, 0.85, -0.35)
AMBIENT = 0.45
DIFFUSE = 0.55

# Toy paint, as in stdlib/tsumiki/base.akr (r, g, b).
PAINT = {
    'red': (220, 50, 47), 'orange': (240, 130, 30), 'yellow': (250, 200, 40),
    'green': (70, 170, 70), 'blue': (40, 100, 210), 'purple': (140, 80, 180),
    'pink': (240, 140, 170), 'cream': (245, 230, 200), 'white': (250, 250, 250),
    'black': (30, 28, 34), 'beech': (222, 178, 120), 'walnut': (140, 90, 55),
    'sky': (150, 200, 240), 'mint': (150, 220, 190), 'grey': (140, 140, 150),
}

# The built-in atlas: texture slot 15, rows 192-255, 4-bit palette 254 (a grey ramp).
STD_SLOT, STD_ROW, STD_PALETTE = 15, 192, 254
STD_CELLS = ['wood', 'planks', 'felt', 'stripes', 'dots', 'check', 'brick', 'stars',
             'dot', 'star', 'puff', 'drop', 'flame', 'square', 'ring', 'heart']

DIRS = {'+x': 0, 'east': 0, '-x': 1, 'west': 1, '+z': 2, 'north': 2, '-z': 3, 'south': 3}


def _norm(v):
    l = math.sqrt(sum(c * c for c in v))
    return tuple(c / l for c in v) if l > 1e-9 else (0.0, 0.0, 0.0)


_L = _norm(LIGHT)


def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def rgb(r, g, b):
    """A colour word 0xBBGGRR, as the GPU and Akari's rgb() make it."""
    return (int(r) & 255) | ((int(g) & 255) << 8) | ((int(b) & 255) << 16)


def parse_colour(s):
    """'#RRGGBB', a paint name ('red', 'beech', ...) or an (r, g, b) tuple -> (r, g, b)."""
    if isinstance(s, (tuple, list)):
        return tuple(int(c) for c in s[:3])
    s = s.strip().lower()
    if s in PAINT:
        return PAINT[s]
    m = re.fullmatch(r'#?([0-9a-f]{6})', s)
    if not m:
        raise ValueError(f"not a colour: '{s}' (use #RRGGBB or a paint name: {', '.join(PAINT)})")
    v = int(m.group(1), 16)
    return ((v >> 16) & 255, (v >> 8) & 255, v & 255)


def shade(colour, n):
    """The lit colour of a face (or corner) with normal n, as shapes.akr computes it."""
    l = AMBIENT + DIFFUSE * max(0.0, _dot(_norm(n), _L))
    return tuple(min(255, int(c * l)) for c in colour)


def cell_handle(slot, palette, u, v, w, h):
    """A cell handle: a texture rectangle as one u32 (see base.akr). Rectangles are whole
    multiples of 8 texels in a 4-bit texture."""
    assert u % 8 == 0 and v % 8 == 0 and w % 8 == 0 and h % 8 == 0 and 8 <= w <= 256 and 8 <= h <= 256
    return (u >> 3) | ((v >> 3) << 5) | ((w // 8 - 1) << 10) | ((h // 8 - 1) << 15) | (slot << 20) | (palette << 24)


# ---------------------------------------------------------------------------- texture cells

def _np():
    import numpy as np
    return np


def _value_noise(w, h, cells, seed):
    np = _np()
    r = np.random.default_rng(seed)
    lat = r.random((cells + 1, cells + 1))
    lat[-1, :] = lat[0, :]
    lat[:, -1] = lat[:, 0]
    ys = np.linspace(0, cells, h, endpoint=False)
    xs = np.linspace(0, cells, w, endpoint=False)
    xi, yi = xs.astype(int), ys.astype(int)
    xf, yf = xs - xi, ys - yi
    xf = xf * xf * (3 - 2 * xf)
    yf = yf * yf * (3 - 2 * yf)
    a = lat[np.ix_(yi, xi)]; b = lat[np.ix_(yi, xi + 1)]
    c = lat[np.ix_(yi + 1, xi)]; d = lat[np.ix_(yi + 1, xi + 1)]
    top = a + (b - a) * xf[None, :]
    bot = c + (d - c) * xf[None, :]
    return top + (bot - top) * yf[:, None]


# A 5x7 pixel font for letter cells (A-Z, 0-9 and a few signs).
_FONT = {
    'A': '01110100011000111111100011000110001', 'B': '11110100011000111110100011000111110',
    'C': '01110100011000010000100001000101110', 'D': '11110100011000110001100011000111110',
    'E': '11111100001000011110100001000011111', 'F': '11111100001000011110100001000010000',
    'G': '01110100011000010111100011000101111', 'H': '10001100011000111111100011000110001',
    'I': '01110001000010000100001000010001110', 'J': '00111000100001000010000101001001100',
    'K': '10001100101010011000101001001010001', 'L': '10000100001000010000100001000011111',
    'M': '10001110111010110101100011000110001', 'N': '10001110011010110011100011000110001',
    'O': '01110100011000110001100011000101110', 'P': '11110100011000111110100001000010000',
    'Q': '01110100011000110001101011001001101', 'R': '11110100011000111110101001001010001',
    'S': '01111100001000001110000010000111110', 'T': '11111001000010000100001000010000100',
    'U': '10001100011000110001100011000101110', 'V': '10001100011000110001100010101000100',
    'W': '10001100011000110101101011010101010', 'X': '10001100010101000100010101000110001',
    'Y': '10001100010101000100001000010000100', 'Z': '11111000010001000100010001000011111',
    '0': '01110100011001110101110011000101110', '1': '00100011000010000100001000010001110',
    '2': '01110100010000100010001000100011111', '3': '11111000100010000010000011000101110',
    '4': '00010001100101010010111110001000010', '5': '11111100001111000001000011000101110',
    '6': '00110010001000011110100011000101110', '7': '11111000010001000100010000100001000',
    '8': '01110100011000101110100011000101110', '9': '01110100011000101111000010001001100',
    '!': '00100001000010000100001000000000100', '?': '01110100010000100010001000000000100',
    '+': '00000001000010011111001000010000000', '*': '00000101010111011111011101010100000',
    '-': '00000000000000011111000000000000000', ' ': '0' * 35,
}


def pattern(kind, w, h, arg=None, seed=1):
    """Pattern values 0..1 (numpy array h x w); 0 picks the first colour of the cell's ramp.
    Values below 0 are transparent (palette index 0)."""
    np = _np()
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    rng = np.random.default_rng(seed)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    rad = np.hypot((xx - cx) / (w / 2), (yy - cy) / (h / 2))
    if kind == 'plain':
        return np.ones((h, w))
    if kind == 'wood':          # long grain along the cell, a few knots' worth of wobble
        n = _value_noise(w, h, 2, seed)
        g = np.sin(yy * 0.85 + n * 4.0 + np.sin(xx * 0.2 + yy * 0.1) * 0.8)
        return 0.86 + g * 0.07 + (_value_noise(w, h, 8, seed + 1) - 0.5) * 0.08
    if kind == 'planks':        # floorboards running across, staggered joints
        board = (yy // 8).astype(int)
        n = _value_noise(w, h, 4, seed)
        g = np.sin((xx * 0.4 + n * 6 + board * 3.0)) * 0.12
        v = 0.6 + g + (board % 3) * 0.06 + _value_noise(w, h, 8, seed + 2) * 0.16
        v[(yy % 8) == 7] = 0.3
        joint = ((xx + board * 13) % w) == 0
        v[joint] = 0.4
        return v
    if kind == 'felt':          # soft fabric noise
        return 0.62 + (_value_noise(w, h, 8, seed) - 0.5) * 0.35 + (rng.random((h, w)) - 0.5) * 0.18
    if kind == 'stripes':       # vertical stripes, two tones
        return np.where((xx // (w / 4)) % 2 == 0, 1.0, 0.72)
    if kind == 'dots':          # polka dots on a light ground
        px, py = (xx % (w / 2)) - w / 4 + 0.5, (yy % (h / 2)) - h / 4 + 0.5
        return np.where(np.hypot(px, py) < w / 9, 0.55, 1.0)
    if kind == 'check':         # a 2 x 2 checkerboard
        return np.where(((xx // (w / 2)) + (yy // (h / 2))) % 2 == 0, 1.0, 0.7)
    if kind == 'brick':
        course = (yy // (h / 4)).astype(int)
        bx = (xx + (course % 2) * (w / 4)) % (w / 2)
        v = 0.8 + _value_noise(w, h, 8, seed) * 0.2
        v[(yy % (h / 4)) == (h / 4 - 1)] = 0.35
        v[bx == 0] = 0.35
        return v
    if kind == 'stars':         # little stars scattered on a ground (wallpaper)
        v = np.ones((h, w)) * 0.86
        for sx, sy in ((w * 0.25, h * 0.3), (w * 0.75, h * 0.75), (w * 0.8, h * 0.2), (w * 0.2, h * 0.8)):
            d = np.abs(xx - sx) + np.abs(yy - sy)
            v[d < w / 12] = 1.0 if sx < w / 2 else 0.5
        return v
    if kind == 'dot':           # a soft round dot, bright in the middle
        v = np.clip(1.0 - rad, 0, 1) ** 1.3
        return np.where(rad < 1.0, v, -1.0)
    if kind == 'star':          # a four-point sparkle
        ax, ay = np.abs(xx - cx) / (w / 2), np.abs(yy - cy) / (h / 2)
        v = np.clip(1.0 - (np.sqrt(ax) + np.sqrt(ay)) * 0.95, 0, 1) * 1.6 + np.clip(0.3 - rad, 0, 1) * 2
        v = np.clip(v, 0, 1)
        return np.where(v > 0.04, v, -1.0)
    if kind == 'puff':          # a lumpy cloud
        n = _value_noise(w, h, 4, seed)
        edge = rad + (n - 0.5) * 0.45
        v = np.clip(0.95 - rad * 0.5 + (n - 0.5) * 0.3, 0, 1)
        return np.where(edge < 0.85, v, -1.0)
    if kind == 'drop':          # a falling drop, round at the bottom
        dx = (xx - cx) / (w / 2)
        dy = (yy - cy) / (h / 2)
        r = np.where(dy < 0.2, np.hypot(dx / np.maximum(0.05, (dy + 1.0) * 0.8), (dy - 0.2) * 0.75), np.hypot(dx, (dy - 0.2) * 1.4))
        v = np.clip(1.1 - r, 0, 1)
        return np.where(r < 0.8, v, -1.0)
    if kind == 'flame':         # a candle flame, pointed at the top
        dx = (xx - cx) / (w / 2)
        dy = (yy - cy) / (h / 2)
        width = np.clip((dy + 1.0) * 0.55, 0, 1) * np.where(dy > 0.35, np.sqrt(np.clip(1 - (dy - 0.35) / 0.65, 0, 1)), 1)
        inside = np.abs(dx) < width * 0.85
        v = np.clip(1.0 - np.abs(dx) / np.maximum(width, 0.01) * 0.6 - (1 - (dy + 1) / 2) * 0.3, 0, 1)
        return np.where(inside & (dy > -0.95), v, -1.0)
    if kind == 'square':
        return np.ones((h, w))
    if kind == 'ring':
        v = np.clip(1.0 - np.abs(rad - 0.75) * 6, 0, 1)
        return np.where(v > 0.05, v, -1.0)
    if kind == 'heart':
        x = (xx - cx) / (w / 2) * 1.25
        y = -(yy - cy) / (h / 2) * 1.25 + 0.25
        f = (x * x + y * y - 1) ** 3 - x * x * y ** 3
        return np.where(f < 0, 0.9 + np.clip(-f, 0, 0.1), -1.0)
    if kind == 'letter':        # a letter on a bevelled block face
        ch = (arg or 'A').upper()[0]
        bits = _FONT.get(ch, _FONT['?'])
        v = np.zeros((h, w))
        border = (xx < 2) | (yy < 2) | (xx >= w - 2) | (yy >= h - 2)
        v[border] = 0.5
        sx, sy = max(1, (w - 8) // 5), max(1, (h - 8) // 7)
        ox, oy = (w - sx * 5) // 2, (h - sy * 7) // 2
        for r in range(7):
            for c in range(5):
                if bits[r * 5 + c] == '1':
                    v[oy + r * sy:oy + (r + 1) * sy, ox + c * sx:ox + (c + 1) * sx] = 1.0
        return v
    raise ValueError(f"unknown pattern '{kind}'")


def ramp(colours, n=15):
    """n colours along the given colour stops."""
    if len(colours) == 1:
        colours = [tuple(c * 0.55 for c in colours[0]), colours[0]]
    out = []
    for i in range(n):
        t = i / (n - 1) * (len(colours) - 1)
        k = min(int(t), len(colours) - 2)
        f = t - k
        a, b = colours[k], colours[k + 1]
        out.append(tuple(int(round(a[j] + (b[j] - a[j]) * f)) for j in range(3)))
    return out


def c15(c):
    r, g, b = (max(0, min(255, int(v))) for v in c)
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)


class Cell:
    def __init__(self, name, kind, w, h, colours, arg=None, image=None, seed=1):
        self.name, self.kind, self.w, self.h, self.arg = name, kind, w, h, arg
        np = _np()
        if kind == 'image':
            from PIL import Image
            im = Image.open(image).convert('RGBA').resize((w, h), Image.NEAREST)
            a = np.array(im)
            q = im.convert('RGB').quantize(colors=15)
            idx = np.array(q).astype(np.uint8) + 1
            idx[a[:, :, 3] < 128] = 0
            pal = q.getpalette()[:45]
            self.palette = [(0, 0, 0)] + [tuple(pal[i * 3:i * 3 + 3]) for i in range(15)]
            self.texels = idx
            return
        v = pattern(kind, w, h, arg, seed)
        cols = [parse_colour(c) for c in colours] if colours else [(200, 200, 200), (255, 255, 255)]
        self.palette = [(0, 0, 0)] + ramp(cols)
        idx = (1 + np.round(np.clip(v, 0, 1) * 14)).astype(np.uint8)
        idx[v < 0] = 0
        self.texels = idx


class Atlas:
    """Packs cells into one 4-bit texture slot (rows of 32 or more texels), a palette each."""

    def __init__(self, slot=0, first_palette=0, first_row=0):
        self.slot, self.first_palette, self.first_row = slot, first_palette, first_row
        self.cells = []
        self.x, self.y, self.row_h = 0, first_row, 0

    def add(self, cell):
        if self.x + cell.w > 256:
            self.x, self.y, self.row_h = 0, self.y + self.row_h, 0
        if self.y + cell.h > 256:
            raise ValueError('texture cells do not fit in one 256 x 256 slot')
        cell.u, cell.v = self.x, self.y
        cell.pal = self.first_palette + len(self.cells)
        if cell.pal > 253:
            raise ValueError('too many cells: palettes run into the ones Tsumiki keeps (254-255)')
        cell.handle = cell_handle(self.slot, cell.pal, cell.u, cell.v, cell.w, cell.h)
        self.x += cell.w
        self.row_h = max(self.row_h, cell.h)
        self.cells.append(cell)
        return cell

    def rows(self):
        return self.y + self.row_h - self.first_row

    def texel_bytes(self):
        """The 4-bit texels of the rows used, 128 bytes a row (low nibble = left texel)."""
        np = _np()
        img = np.zeros((256, 256), np.uint8)
        for c in self.cells:
            img[c.v:c.v + c.h, c.u:c.u + c.w] = c.texels
        rows = img[self.first_row:self.first_row + self.rows()]
        return (rows[:, 0::2] | (rows[:, 1::2] << 4)).astype(np.uint8).tobytes()

    def palette_bytes(self):
        out = b''
        for c in self.cells:
            out += b''.join(struct.pack('<H', c15(col)) for col in c.palette)
        return out


# ---------------------------------------------------------------------------- shape builder

class Brush:
    def __init__(self):
        self.colour = (250, 250, 250)
        self.cell = None          # None: plain colour; else a handle (int) and its rectangle
        self.smooth = False
        self.blend = -1
        self.twosided = False


class Builder:
    """Vertices and faces of one mesh, built from block primitives (as shapes.akr does)."""

    def __init__(self):
        self.verts = []
        self.faces = []         # (idx list, colours, uvs, flags, cell handle, blend)
        self.brush = Brush()
        self.offset = (0.0, 0.0, 0.0)
        self.rot = None         # 3x3 rows, or None
        self.origin = (0.0, 0.0, 0.0)   # subtracted from every vertex (a part's joint)

    # -- placement of the following shapes
    def place(self, offset=(0, 0, 0), turn=(0, 0, 0)):
        self.offset = tuple(float(c) for c in offset)
        rx, ry, rz = (math.radians(a) for a in turn)
        if rx == ry == rz == 0:
            self.rot = None
            return
        # yaw (Y), then pitch (X), then roll (Z), as anim.akr turns joints
        sx, cx, sy, cy, sz, cz = math.sin(rx), math.cos(rx), math.sin(ry), math.cos(ry), math.sin(rz), math.cos(rz)
        self.rot = [
            (cy * cz - sy * sx * sz, -cy * sz - sy * sx * cz, sy * cx),
            (cx * sz, cx * cz, sx),
            (-sy * cz - cy * sx * sz, sy * sz - cy * sx * cz, cy * cx),
        ]

    def _xf(self, p):
        if self.rot:
            p = tuple(_dot(r, p) for r in self.rot)
        return _sub(_add(p, self.offset), self.origin)

    def _xn(self, n):
        return tuple(_dot(r, n) for r in self.rot) if self.rot else n

    def v(self, p):
        self.verts.append(self._xf(p))
        return len(self.verts) - 1

    def _uvs(self, n):
        c = self.brush.cell
        if c is None:
            return None
        u0, v0, u1, v1 = c[1], c[2], c[1] + c[3] - 1, c[2] + c[4] - 1
        if n == 4:
            return [(u0, v1), (u1, v1), (u0, v0), (u1, v0)]
        return [(u0, v1), (u1, v1), ((u0 + u1) // 2, v0)]

    def _colour(self, n):
        c = shade(self.brush.colour, self._xn(n))
        if self.brush.cell is not None:      # a tint: 128 leaves the texel as it is
            c = tuple((ch + 1) // 2 for ch in c)
        return rgb(*c)

    def face(self, idx, normal, corner_normals=None):
        """A triangle or quad (strip order: bottom-left, bottom-right, top-left, top-right as
        seen from outside), turned to face along `normal` whichever way it was given."""
        idx = list(idx)
        P = [self.verts[i] for i in idx]
        n = self._xn(normal)
        c = _cross(_sub(P[1], P[0]), _sub(P[2], P[0]))
        if _dot(c, n) > 0:        # Mei's world is left-handed: front faces have cross . n < 0
            idx[0], idx[1] = idx[1], idx[0]
            if len(idx) == 4:
                idx[2], idx[3] = idx[3], idx[2]
            if corner_normals:
                cn = list(corner_normals)
                cn[0], cn[1] = cn[1], cn[0]
                if len(cn) == 4:
                    cn[2], cn[3] = cn[3], cn[2]
                corner_normals = cn
        if self.brush.smooth and corner_normals:
            cols = [self._colour(cn) for cn in corner_normals]
        else:
            cols = [self._colour(normal)] * len(idx)
        flags = 16 if self.brush.twosided else 0
        if self.brush.blend >= 0:
            flags |= 8
        self.faces.append((idx, cols, self._uvs(len(idx)), flags, self.brush.cell, max(self.brush.blend, 0)))

    # -- primitives (coordinates before placement)
    def box(self, lo, hi):
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        p = [self.v((x, y, z)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
        # p index: x + 2y + 4z
        self.face([p[0], p[1], p[2], p[3]], (0, 0, -1))
        self.face([p[5], p[4], p[7], p[6]], (0, 0, 1))
        self.face([p[1], p[5], p[3], p[7]], (1, 0, 0))
        self.face([p[4], p[0], p[6], p[2]], (-1, 0, 0))
        self.face([p[2], p[3], p[6], p[7]], (0, 1, 0))
        self.face([p[4], p[5], p[0], p[1]], (0, -1, 0))

    def ramp(self, lo, hi, d):
        """A wedge in the box lo..hi rising toward d (0 +x, 1 -x, 2 +z, 3 -z)."""
        x0, y0, z0 = lo
        x1, y1, z1 = hi

        def at(a, s, y):     # a: 0..1 along the rise, s: 0..1 across it
            if d == 0: return (x0 + (x1 - x0) * a, y, z0 + (z1 - z0) * s)
            if d == 1: return (x1 - (x1 - x0) * a, y, z0 + (z1 - z0) * s)
            if d == 2: return (x0 + (x1 - x0) * s, y, z0 + (z1 - z0) * a)
            return (x0 + (x1 - x0) * s, y, z1 - (z1 - z0) * a)

        run = (x1 - x0) if d < 2 else (z1 - z0)
        rise = y1 - y0
        fwd = [(1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)][d]
        b00, b01 = self.v(at(0, 0, y0)), self.v(at(0, 1, y0))
        b10, b11 = self.v(at(1, 0, y0)), self.v(at(1, 1, y0))
        t10, t11 = self.v(at(1, 0, y1)), self.v(at(1, 1, y1))
        slope_n = _norm(_add(_mul(fwd, -rise), (0, run, 0)))
        self.face([b00, b01, t10, t11], slope_n)
        self.face([b10, b11, t10, t11], fwd)
        self.face([b00, b01, b10, b11], (0, -1, 0))
        side = (0, 0, -1) if d < 2 else (-1, 0, 0)
        self.face([b00, b10, t10], side)
        self.face([b01, b11, t11], _mul(side, -1))

    def _axis(self, axis):
        # maps (radial x, along, radial z) onto the axis
        return {'y': lambda a, h, b: (a, h, b), 'x': lambda a, h, b: (h, a, b),
                'z': lambda a, h, b: (a, b, h), '-y': lambda a, h, b: (a, -h, b),
                '-x': lambda a, h, b: (-h, a, b), '-z': lambda a, h, b: (a, b, -h)}[axis]

    def cylinder(self, base, r, h, sides=8, axis='y', cone=False):
        m = self._axis(axis)
        ring0, ring1, ns = [], [], []
        for i in range(sides):
            a = 2 * math.pi * i / sides
            ca, sa = math.cos(a), math.sin(a)
            ring0.append(self.v(_add(base, m(ca * r, 0, sa * r))))
            if not cone:
                ring1.append(self.v(_add(base, m(ca * r, h, sa * r))))
            slope = r / h if cone else 0
            ns.append(_norm(m(ca, slope, sa)))
        apex = self.v(_add(base, m(0, h, 0))) if cone else None
        for i in range(sides):
            j = (i + 1) % sides
            mid = _norm(_add(ns[i], ns[j]))
            if cone:
                self.face([ring0[i], ring0[j], apex], mid, [ns[i], ns[j], m(0, 1, 0)])
            else:
                self.face([ring0[i], ring0[j], ring1[i], ring1[j]], mid, [ns[i], ns[j], ns[i], ns[j]])
        down, up = m(0, -1, 0), m(0, 1, 0)
        for i in range(1, sides - 1):
            self.face([ring0[0], ring0[i], ring0[i + 1]], down)
            if not cone:
                self.face([ring1[0], ring1[i], ring1[i + 1]], up)

    def sphere(self, c, r, rings=4, scale=(1, 1, 1)):
        segs = rings * 2
        grid = []
        for k in range(1, rings):
            ph = math.pi * k / rings
            row = []
            for i in range(segs):
                th = 2 * math.pi * i / segs
                n = (math.sin(ph) * math.cos(th), math.cos(ph), math.sin(ph) * math.sin(th))
                row.append((self.v(_add(c, (n[0] * r * scale[0], n[1] * r * scale[1], n[2] * r * scale[2]))), n))
            grid.append(row)
        top = self.v(_add(c, (0, r * scale[1], 0)))
        bot = self.v(_add(c, (0, -r * scale[1], 0)))
        for i in range(segs):
            j = (i + 1) % segs
            a, b = grid[0][i], grid[0][j]
            self.face([a[0], b[0], top], _norm(_add(_add(a[1], b[1]), (0, 1, 0))), [a[1], b[1], (0, 1, 0)])
            a, b = grid[-1][i], grid[-1][j]
            self.face([a[0], b[0], bot], _norm(_add(_add(a[1], b[1]), (0, -1, 0))), [a[1], b[1], (0, -1, 0)])
            for k in range(len(grid) - 1):
                a, b, cc, d = grid[k + 1][i], grid[k + 1][j], grid[k][i], grid[k][j]
                n = _norm(_add(_add(a[1], b[1]), _add(cc[1], d[1])))
                self.face([a[0], b[0], cc[0], d[0]], n, [a[1], b[1], cc[1], d[1]])

    def grid(self, x0, y, z0, x1, z1, nx, nz, alt=None):
        ids = [[self.v((x0 + (x1 - x0) * i / nx, y, z0 + (z1 - z0) * k / nz)) for i in range(nx + 1)] for k in range(nz + 1)]
        base = self.brush.colour
        for k in range(nz):
            for i in range(nx):
                if alt is not None:
                    self.brush.colour = base if (i + k) % 2 == 0 else alt
                self.face([ids[k][i], ids[k][i + 1], ids[k + 1][i], ids[k + 1][i + 1]], (0, 1, 0))
        self.brush.colour = base

    def star(self, c, r_out, r_in, depth, points=5):
        """A star facing -Z (toward a camera at -Z), extruded `depth` along Z."""
        n = points * 2
        front, back = [], []
        for i in range(n):
            a = math.pi / 2 + math.pi * i / points
            rr = r_out if i % 2 == 0 else r_in
            x, y = math.cos(a) * rr, math.sin(a) * rr
            front.append(self.v(_add(c, (x, y, -depth / 2))))
            back.append(self.v(_add(c, (x, y, depth / 2))))
        fc = self.v(_add(c, (0, 0, -depth / 2 - depth * 0.35)))
        bc = self.v(_add(c, (0, 0, depth / 2 + depth * 0.35)))
        for i in range(n):
            j = (i + 1) % n
            pa, pb = self.verts[front[i]], self.verts[front[j]]
            out = _norm(_add(_sub(pa, self._xf(c)), _sub(pb, self._xf(c))))
            self.face([front[i], front[j], back[i], back[j]], self._unxn(out))
            self.face([front[i], front[j], fc], self._unxn(_norm(_add(out, (0, 0, -1.6)))))
            self.face([back[i], back[j], bc], self._unxn(_norm(_add(out, (0, 0, 1.6)))))

    def _unxn(self, n):
        # normals computed from placed vertices: undo the rotation so face() can redo it
        if not self.rot:
            return n
        return tuple(sum(self.rot[r][c] * n[r] for r in range(3)) for c in range(3))

    def bin(self):
        m = _MeiMesh()
        m.verts = list(self.verts)
        for idx, cols, uvs, flags, cell, blend in self.faces:
            kw = {}
            if cell is not None:
                h = cell[0]
                kw = dict(slot=(h >> 20) & 15, four_bit=True, palette=(h >> 24) & 255)
            m.face(idx, cols, uvs, flags, blend=blend, **kw)
        if len(m.verts) > 2048:
            raise ValueError('a mesh may have at most 2,048 vertices')
        return m.pack()


# ---------------------------------------------------------------------------- the toy

class Part:
    def __init__(self, name, parent, joint):
        self.name, self.parent, self.joint = name, parent, joint
        self.builder = Builder()


class Model:
    def __init__(self, name):
        self.name = name
        self.parts = []

    def find(self, name):
        for i, p in enumerate(self.parts):
            if p.name == name:
                return i
        raise ValueError(f"model '{self.name}' has no part '{name}'")


class Clip:
    def __init__(self, model, name, frames, loop):
        self.model, self.name, self.frames, self.loop = model, name, int(frames), loop
        self.tracks = {}       # part index -> {frame: (rot, move)}


class Morph:
    def __init__(self, name):
        self.name = name
        self.builder = Builder()
        self.poses = []         # (name, [vertex positions])


class Toy:
    """Everything one .toy file makes; write() puts it in an output directory."""

    def __init__(self, name):
        self.name = name
        self.meshes = []        # (name, Builder)
        self.models = []
        self.clips = []
        self.morphs = []
        self.atlas = None
        self.cells = {}
        self.cur = None         # the Builder that shapes go into
        self.model_cur = None
        self.clip_cur = None
        self.morph_cur = None
        self.pose_cur = None
        self._slot, self._first_palette = 0, 0

    # -- textures
    def texture(self, slot=0, palette=0):
        if self.atlas is not None:
            raise ValueError("one 'texture' per toy file")
        self._slot, self._first_palette = slot, palette

    def cell(self, name, kind, w=32, h=32, colours=(), arg=None, image=None):
        if self.atlas is None:
            self.atlas = Atlas(self._slot, self._first_palette)
        c = Cell(name, kind, w, h, list(colours), arg, image, seed=len(self.cells) + 3)
        self.atlas.add(c)
        self.cells[name.lower()] = c
        return c

    # -- what shapes go into
    def _new_builder(self, b):
        self.cur = b
        self.clip_cur = None
        self.pose_cur = None
        return b

    def mesh(self, name):
        b = self._new_builder(Builder())
        self.meshes.append((name, b))
        self.model_cur = None
        self.morph_cur = None
        return b

    def model(self, name):
        self.model_cur = Model(name)
        self.models.append(self.model_cur)
        self.morph_cur = None
        self.cur = None
        return self.model_cur

    def part(self, name, parent=None, joint=(0, 0, 0)):
        m = self.model_cur
        if m is None:
            raise ValueError("'part' needs a 'model' first")
        pi = -1 if parent in (None, '-', '') else m.find(parent)
        p = Part(name, pi, tuple(float(c) for c in joint))
        p.builder.origin = p.joint      # shapes are given in model space
        m.parts.append(p)
        if len(m.parts) > 16:
            raise ValueError('a model may have at most 16 parts')
        self._new_builder(p.builder)
        return p

    def morph(self, name):
        self.morph_cur = Morph(name)
        self.morphs.append(self.morph_cur)
        self.model_cur = None
        self._new_builder(self.morph_cur.builder)
        return self.morph_cur

    def pose(self, name):
        m = self.morph_cur
        if m is None:
            raise ValueError("'pose' needs a 'morph' first")
        if len(m.poses) >= 7:
            raise ValueError('a morph may have at most 8 poses (the base and 7 more)')
        m.poses.append((name, list(m.builder.verts)))
        self.pose_cur = len(m.poses) - 1
        # shapes given after 'pose' describe it again from scratch
        self._respec = Builder()
        self._respec.brush = m.builder.brush
        self.cur = self._respec
        return self.pose_cur

    def _builder(self):
        if self.cur is None:
            raise ValueError("shapes need a 'mesh', 'part' or 'morph' to go into")
        return self.cur

    # -- the brush
    def paint(self, colour, finish='plain', smooth=None):
        b = self._builder().brush
        b.colour = parse_colour(colour)
        f = (finish or 'plain').lower()
        if f == 'plain':
            b.cell = None
        elif f in STD_CELLS[:8]:
            i = STD_CELLS.index(f)
            u, v = (i % 8) * 32, STD_ROW + (i // 8) * 32
            b.cell = (cell_handle(STD_SLOT, STD_PALETTE, u, v, 32, 32), u, v, 32, 32)
        elif f in self.cells:
            c = self.cells[f]
            b.cell = (c.handle, c.u, c.v, c.w, c.h)
        else:
            raise ValueError(f"unknown finish '{finish}' (plain, a built-in finish or a cell of this file)")
        if smooth is not None:
            b.smooth = smooth

    def blend(self, mode):
        modes = {'none': -1, 'half': 0, 'add': 1, 'sub': 2, 'quarter': 3}
        self._builder().brush.blend = modes[mode]

    def twosided(self, on=True):
        self._builder().brush.twosided = on

    def place(self, offset=(0, 0, 0), turn=(0, 0, 0)):
        self._builder().place(offset, turn)

    # -- shapes
    def box(self, *a): self._builder().box(tuple(a[0:3]), tuple(a[3:6]))
    def ramp(self, x0, y0, z0, x1, y1, z1, d):
        self._builder().ramp((x0, y0, z0), (x1, y1, z1), DIRS[d] if isinstance(d, str) else d)
    def cylinder(self, x, y, z, r, h, sides=8, axis='y'): self._builder().cylinder((x, y, z), r, h, int(sides), axis)
    def cone(self, x, y, z, r, h, sides=8, axis='y'): self._builder().cylinder((x, y, z), r, h, int(sides), axis, cone=True)
    def sphere(self, x, y, z, r, rings=4, scale=(1, 1, 1)): self._builder().sphere((x, y, z), r, int(rings), scale)
    def grid(self, x0, y, z0, x1, z1, nx=1, nz=1, alt=None):
        self._builder().grid(x0, y, z0, x1, z1, int(nx), int(nz), parse_colour(alt) if alt else None)
    def star(self, x, y, z, r_out, r_in, depth, points=5): self._builder().star((x, y, z), r_out, r_in, depth, int(points))

    # -- clips
    def clip(self, model, name, frames, loop=True):
        m = model if isinstance(model, Model) else next((x for x in self.models if x.name == model), None)
        if m is None:
            raise ValueError(f"no model '{model}' for clip '{name}'")
        self.clip_cur = Clip(m, name, frames, loop)
        self.clips.append(self.clip_cur)
        self.cur = None
        return self.clip_cur

    def key(self, frame, part, rot=None, move=None):
        c = self.clip_cur
        if c is None:
            raise ValueError("'key' needs a 'clip' first")
        pi = c.model.find(part)
        tr = c.tracks.setdefault(pi, {})
        old = tr.get(int(frame), ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
        r = tuple(math.radians(float(a)) for a in rot) if rot is not None else old[0]
        mv = tuple(float(a) for a in move) if move is not None else old[1]
        tr[int(frame)] = (r, mv)

    # -- pose edits (after 'pose')
    def _pose_verts(self):
        m = self.morph_cur
        if m is None or self.pose_cur is None:
            raise ValueError("'scale' and 'move' change a pose: they need a 'pose' first")
        return m.poses[self.pose_cur][1]

    @staticmethod
    def _inside(p, box):
        if box is None:
            return True
        return all(box[i] <= p[i] <= box[i + 3] for i in range(3))

    def pose_scale(self, s, about=(0, 0, 0), inside=None):
        vs = self._pose_verts()
        base = self.morph_cur.builder.verts
        for i, p in enumerate(vs):
            if self._inside(base[i], inside):
                vs[i] = tuple(about[k] + (p[k] - about[k]) * s[k] for k in range(3))

    def pose_move(self, d, inside=None):
        vs = self._pose_verts()
        base = self.morph_cur.builder.verts
        for i, p in enumerate(vs):
            if self._inside(base[i], inside):
                vs[i] = _add(p, d)

    def _finish_pose(self):
        # a pose described again with shapes replaces the copied vertices
        if self.morph_cur is not None and self.pose_cur is not None and self._respec.verts:
            m = self.morph_cur
            if len(self._respec.verts) != len(m.builder.verts):
                raise ValueError(f"pose '{m.poses[self.pose_cur][0]}' of morph '{m.name}' has "
                                 f"{len(self._respec.verts)} vertices, the base has {len(m.builder.verts)}: "
                                 "describe it with the same shapes in the same order")
            m.poses[self.pose_cur] = (m.poses[self.pose_cur][0], list(self._respec.verts))
            self._respec = Builder()
            self._respec.brush = m.builder.brush
            self.cur = self._respec

    # -- output
    def write(self, outdir):
        self._finish_pose()
        os.makedirs(outdir, exist_ok=True)
        N = self.name
        L = [f'// Generated by tools/tsumiki.py from {N}.toy - do not edit.',
             '// Import it after "tsumiki.akr". docs/TSUMIKI.md describes what is here.', '']
        files = []

        def emit_bin(fname, data):
            with open(os.path.join(outdir, fname), 'wb') as f:
                f.write(data)
            files.append(fname)

        def cname(*parts):
            return '_'.join(re.sub(r'[^A-Za-z0-9]', '_', p).upper() for p in parts)

        def fx(v):
            return f'{v:.4f}'.rstrip('0').rstrip('.') if '.' in f'{v:.4f}' else f'{v}'

        def fv(v):
            s = f'{round(v, 4):.4f}'.rstrip('0')
            return s + '0' if s.endswith('.') else s

        def vec3(p):
            return f'vec3({fv(p[0])}, {fv(p[1])}, {fv(p[2])})'

        if self.atlas:
            a = self.atlas
            emit_bin(f'{N}_tex.bin', a.texel_bytes())
            emit_bin(f'{N}_pal.bin', a.palette_bytes())
            L += [f'// Texture cells: slot {a.slot}, rows 0-{a.rows() - 1}, palettes {a.first_palette}-'
                  f'{a.first_palette + len(a.cells) - 1}. Load them once: tk_load_atlas(&{cname(N, "atlas")})',
                  f'embed {cname(N, "tex")}: u8 = "{N}_tex.bin"',
                  f'embed {cname(N, "pal")}: u16 = "{N}_pal.bin"',
                  f'const {cname(N, "atlas")}: TkAtlas = TkAtlas {{ slot: {a.slot}, texels: {cname(N, "tex")}, '
                  f'rows: {a.rows()}, palettes: {cname(N, "pal")}, first_palette: {a.first_palette}, count: {len(a.cells)} }}']
            for c in a.cells:
                L.append(f'const {cname(c.name)}: u32 = 0x{c.handle:08X}    // {c.kind} {c.w}x{c.h} at ({c.u}, {c.v}), palette {c.pal}')
            L.append('')

        for name, b in self.meshes:
            fname = f'{name.lower()}.bin'
            emit_bin(fname, b.bin())
            L.append(f'embed {cname(name)}: Mesh = "{fname}"    // {len(b.verts)} vertices, {len(b.faces)} faces')
        if self.meshes:
            L.append('')

        for m in self.models:
            L.append(f'// Model "{m.name}": {len(m.parts)} parts')
            for p in m.parts:
                fname = f'{m.name.lower()}_{p.name.lower()}.bin'
                emit_bin(fname, p.builder.bin())
                L.append(f'embed {cname(m.name, p.name, "mesh")}: Mesh = "{fname}"')
            L.append(f'const {cname(m.name, "parts")}: [{len(m.parts)}]TkPart = [')
            for p in m.parts:
                rel = p.joint if p.parent < 0 else _sub(p.joint, m.parts[p.parent].joint)
                L.append(f'    TkPart {{ parent: {p.parent}, mesh: {cname(m.name, p.name, "mesh")}, joint: {vec3(rel)} }},')
            L.append(']')
            L.append(f'const {cname(m.name)}: TkRig = TkRig {{ parts: {cname(m.name, "parts")}, count: {len(m.parts)} }}')
            for i, p in enumerate(m.parts):
                L.append(f'const {cname(m.name, p.name)} = {i}    // part number (tk_anim_joint)')
            L.append('')

        for c in self.clips:
            m = c.model
            times = {0, c.frames}
            for tr in c.tracks.values():
                times |= set(f for f in tr if 0 <= f <= c.frames)
            times = sorted(times)
            keys = []
            for t in times:
                for pi in range(len(m.parts)):
                    keys.append(self._sample(c, pi, t))
            nm = cname(m.name, c.name)
            L.append(f'// Clip "{c.name}" of {m.name}: {c.frames} frames, {"looping" if c.loop else "once"}')
            L.append(f'const {nm}_TIMES: [{len(times)}]s16 = [{", ".join(str(t) for t in times)}]')
            L.append(f'const {nm}_KEYS: [{len(keys)}]TkJoint = [')
            for r, mv in keys:
                L.append(f'    TkJoint {{ rot: {vec3(r)}, move: {vec3(mv)} }},')
            L.append(']')
            L.append(f'const {nm}: TkClip = TkClip {{ keys: {nm}_KEYS, times: {nm}_TIMES, nkeys: {len(times)}, '
                     f'nparts: {len(m.parts)}, length: {c.frames}, looping: {"true" if c.loop else "false"} }}')
            L.append('')

        for mo in self.morphs:
            b = mo.builder
            fname = f'{mo.name.lower()}.bin'
            emit_bin(fname, b.bin())
            nm = cname(mo.name)
            poses = [b.verts] + [p[1] for p in mo.poses]
            L.append(f'// Morph "{mo.name}": {len(b.verts)} vertices, {len(poses)} poses')
            L.append(f'embed {nm}_MESH: Mesh = "{fname}"')
            L.append(f'const {nm}_POSES: [{len(poses) * len(b.verts)}]vec4 = [')
            for pv in poses:
                for p in pv:
                    L.append(f'    vec4({fv(p[0])}, {fv(p[1])}, {fv(p[2])}, 1.0),')
            L.append(']')
            L.append(f'const {nm}: TkMorphData = TkMorphData {{ mesh: {nm}_MESH, poses: {nm}_POSES, count: {len(poses)} }}')
            L.append(f'const {cname(mo.name, "base")} = 0    // pose numbers (tk_morph_blend)')
            for i, (pn, _) in enumerate(mo.poses):
                L.append(f'const {cname(mo.name, pn)} = {i + 1}')
            L.append('')

        with open(os.path.join(outdir, f'{N}.akr'), 'w') as f:
            f.write('\n'.join(L).rstrip() + '\n')
        return [f'{N}.akr'] + files

    @staticmethod
    def _sample(c, pi, t):
        """Part pi's (rot, move) at frame t: linear between its own keys. A looping clip wraps
        (after its last key it heads back to its first); a clip played once holds its ends."""
        tr = c.tracks.get(pi)
        zero = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        if not tr:
            return zero
        frames = sorted(tr)
        if c.loop:
            tr = dict(tr)
            first, last = frames[0], frames[-1]
            tr.setdefault(first + c.frames, tr[first])
            tr.setdefault(last - c.frames, tr[last])
            frames = sorted(tr)
        if t <= frames[0]:
            return tr[frames[0]]
        if t >= frames[-1]:
            return tr[frames[-1]]
        for a, b in zip(frames, frames[1:]):
            if a <= t <= b:
                f = (t - a) / (b - a)
                ra, ma = tr[a]
                rb, mb = tr[b]
                return (tuple(ra[i] + (rb[i] - ra[i]) * f for i in range(3)),
                        tuple(ma[i] + (mb[i] - ma[i]) * f for i in range(3)))
        return zero


# ---------------------------------------------------------------------------- the .toy parser

def _nums(tokens, n, line):
    try:
        v = [float(t) for t in tokens[:n]]
    except ValueError:
        raise ValueError(f'line {line}: expected {n} numbers, got {" ".join(tokens[:n])}')
    if len(v) < n:
        raise ValueError(f'line {line}: expected {n} numbers')
    return v


def _opts(tokens, line, spec):
    """Keyword options after the fixed arguments: spec maps a word to its number count
    (0: a flag, 'w': one word)."""
    out = {}
    i = 0
    while i < len(tokens):
        k = tokens[i].lower()
        if k not in spec:
            raise ValueError(f"line {line}: unexpected '{tokens[i]}' (expected one of: {', '.join(spec)})")
        n = spec[k]
        if n == 0:
            out[k] = True
            i += 1
        elif n == 'w':
            out[k] = tokens[i + 1]
            i += 2
        else:
            out[k] = _nums(tokens[i + 1:], n, line)
            i += 1 + n
    return out


def parse_toy(text, name, basedir='.'):
    toy = Toy(name)
    for ln, raw in enumerate(text.splitlines(), 1):
        # '#' starts a comment, except a '#' with six hex digits, which is a colour
        line = re.sub(r'\s+', ' ', raw).strip()
        line = re.sub(r'(^|\s)#(?![0-9A-Fa-f]{6}\b).*$', '', line).strip()
        if not line:
            continue
        t = line.split(' ')
        w, a = t[0].lower(), t[1:]
        try:
            if w == 'texture':
                o = _opts(a, ln, {'slot': 1, 'palette': 1})
                toy.texture(int(o.get('slot', [0])[0]), int(o.get('palette', [0])[0]))
            elif w == 'cell':
                nm, kind = a[0], a[1].lower()
                rest = a[2:]
                arg = image = None
                if kind.startswith('letter:'):
                    kind, arg = 'letter', kind.split(':', 1)[1]
                elif kind.startswith('image:'):
                    kind, image = 'image', os.path.join(basedir, a[1].split(':', 1)[1])
                size = (32, 32)
                if rest and re.fullmatch(r'\d+x\d+', rest[0]):
                    size = tuple(int(v) for v in rest[0].split('x'))
                    rest = rest[1:]
                toy.cell(nm, kind, size[0], size[1], rest, arg, image)
            elif w == 'mesh':
                toy.mesh(a[0])
            elif w == 'model':
                toy.model(a[0])
            elif w == 'part':
                o = _opts(a[1:], ln, {'parent': 'w', 'joint': 3})
                toy.part(a[0], o.get('parent'), o.get('joint', (0, 0, 0)))
            elif w == 'morph':
                toy.morph(a[0])
            elif w == 'pose':
                toy._finish_pose()
                toy.pose(a[0])
            elif w == 'paint':
                finish = 'plain'
                smooth = None
                for x in a[1:]:
                    xl = x.lower()
                    if xl == 'smooth': smooth = True
                    elif xl == 'flat': smooth = False
                    else: finish = xl
                toy.paint(a[0], finish, smooth)
            elif w == 'blend':
                toy.blend(a[0].lower())
            elif w == 'twosided':
                toy.twosided(not a or a[0].lower() in ('on', 'yes', 'true'))
            elif w == 'place':
                o = _opts(a, ln, {'at': 3, 'turn': 3})
                toy.place(o.get('at', (0, 0, 0)), o.get('turn', (0, 0, 0)))
            elif w == 'box':
                toy.box(*_nums(a, 6, ln))
            elif w == 'ramp':
                v = _nums(a, 6, ln)
                if len(a) < 7 or a[6].lower() not in DIRS:
                    raise ValueError(f'line {ln}: a ramp needs a direction: +x -x +z -z')
                toy.ramp(*v, a[6].lower())
            elif w in ('cylinder', 'cone'):
                v = _nums(a, 5, ln)
                o = _opts(a[5:], ln, {'sides': 1, 'axis': 'w'})
                f = toy.cylinder if w == 'cylinder' else toy.cone
                f(*v, int(o.get('sides', [8])[0]), o.get('axis', 'y').lower())
            elif w == 'sphere':
                v = _nums(a, 4, ln)
                o = _opts(a[4:], ln, {'rings': 1, 'scale': 3})
                toy.sphere(*v, int(o.get('rings', [4])[0]), o.get('scale', (1, 1, 1)))
            elif w == 'grid':
                v = _nums(a, 5, ln)
                o = _opts(a[5:], ln, {'cells': 2, 'alt': 'w'})
                c = o.get('cells', (1, 1))
                toy.grid(*v, int(c[0]), int(c[1]), o.get('alt'))
            elif w == 'star':
                v = _nums(a, 6, ln)
                o = _opts(a[6:], ln, {'points': 1})
                toy.star(*v, int(o.get('points', [5])[0]))
            elif w == 'clip':
                if len(a) < 3:
                    raise ValueError(f'line {ln}: clip MODEL NAME FRAMES [loop|once]')
                loop = not (len(a) > 3 and a[3].lower() == 'once')
                toy.clip(a[0], a[1], int(a[2]), loop)
            elif w == 'key':
                frame = int(_nums(a, 1, ln)[0])
                o = _opts(a[2:], ln, {'rot': 3, 'move': 3})
                toy.key(frame, a[1], o.get('rot'), o.get('move'))
            elif w == 'scale':
                o = _opts(a[3:], ln, {'about': 3, 'inside': 6})
                toy.pose_scale(_nums(a, 3, ln), o.get('about', (0, 0, 0)), o.get('inside'))
            elif w == 'move':
                o = _opts(a[3:], ln, {'inside': 6})
                toy.pose_move(_nums(a, 3, ln), o.get('inside'))
            else:
                raise ValueError(f"line {ln}: unknown statement '{t[0]}'")
        except ValueError as e:
            msg = str(e)
            raise ValueError(msg if msg.startswith('line') else f'line {ln}: {msg}')
    return toy


# ---------------------------------------------------------------------------- the built-in atlas

def write_stdlib_atlas(path):
    """stdlib/tsumiki/atlas.akr: the built-in cells (slot 15, rows 192-255, palette 254)."""
    np = _np()
    img = np.zeros((64, 256), np.uint8)
    names = []
    for i, kind in enumerate(STD_CELLS):
        c = Cell(kind, kind, 32, 32, ['#5a5a5a', '#ffffff'] if i >= 8 else ['#b4b4b4', '#ffffff'], seed=11 + i)
        u, v = (i % 8) * 32, (i // 8) * 32
        img[v:v + 32, u:u + 32] = c.texels
        names.append((kind, cell_handle(STD_SLOT, STD_PALETTE, u, STD_ROW + v, 32, 32)))
    packed = (img[:, 0::2] | (img[:, 1::2] << 4)).astype(np.uint8).tobytes()
    words = struct.unpack('<%dI' % (len(packed) // 4), packed)
    grey = [0] + [c15((g, g, g)) for g in (int(round(255 * (k / 15) ** 0.85)) for k in range(1, 16))]
    L = ['// Generated by tools/tsumiki.py --stdlib - do not edit.',
         '// The built-in texture cells: 4-bit, texture slot 15 rows 192-255 (below the fonts, which',
         '// use rows 0-66), palette 254 (a grey ramp, so a face colour or tint gives them their colour).',
         '']
    for kind, h in names:
        L.append(f'const TK_{kind.upper()}: u32 = 0x{h:08X}')
    L.append('')
    L.append(f'const __TK_ATLAS_PAL: [16]u16 = [{", ".join("0x%04X" % g for g in grey)}]')
    L.append(f'const __TK_ATLAS: [{len(words)}]u32 = [')
    for i in range(0, len(words), 8):
        L.append('    ' + ', '.join('0x%08X' % w for w in words[i:i + 8]) + ',')
    L.append(']')
    with open(path, 'w') as f:
        f.write('\n'.join(L) + '\n')


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description='Builds Tsumiki meshes, rigs, clips, morphs and texture cells from a .toy file.')
    ap.add_argument('toy', nargs='?', help='the .toy file')
    ap.add_argument('-o', '--out', default=None, help='output directory (default: next to the .toy file)')
    ap.add_argument('--stdlib', action='store_true', help='rebuild stdlib/tsumiki/atlas.akr')
    args = ap.parse_args(argv)
    if args.stdlib:
        p = os.path.join(ROOT, 'stdlib', 'tsumiki', 'atlas.akr')
        write_stdlib_atlas(p)
        print('wrote', p)
        return 0
    if not args.toy:
        ap.error('give a .toy file (or --stdlib)')
    name = os.path.splitext(os.path.basename(args.toy))[0]
    base = os.path.dirname(os.path.abspath(args.toy))
    try:
        toy = parse_toy(open(args.toy).read(), name, base)
        files = toy.write(args.out or base)
    except ValueError as e:
        print(f'{args.toy}:{e}', file=sys.stderr)
        return 1
    print(f'wrote {len(files)} files: ' + ', '.join(files))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
