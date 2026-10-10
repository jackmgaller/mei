"""Shared helpers for the Moonlight Skeleton generators: mesh building and texture painting.

Writes nothing itself. make_console.py and make_controller.py import it.
"""
import math
from PIL import Image, ImageDraw, ImageFont

HERE = __import__('pathlib').Path(__file__).resolve().parent
ART = HERE / 'art'

KANJI_FONT = '/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc'

# --- the moonlight palette -------------------------------------------------------------

INDIGO = (62, 50, 160)        # the shell, one layer of translucent indigo
INDIGO_DEEP = (36, 28, 104)   # two layers, or something dark behind it
INDIGO_EDGE = (92, 80, 204)   # the light-catching rims
GHOST = (30, 34, 92)          # the circuit board seen through the shell
GHOST_LINE = (104, 104, 210)  # its traces
LAVENDER = (150, 146, 228)    # metal (shields, screws) seen through
MOON = (214, 228, 255)        # pale moon blue, the print colour
SILVER = (196, 202, 222)
SUN = (246, 168, 64)          # the 日 of the logo


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def hexc(c):
    return '#%02x%02x%02x' % tuple(c)


# --- a 3x5 pixel font for printed labels --------------------------------------------------

GLYPHS = {
    'A': ['010', '101', '111', '101', '101'], 'B': ['110', '101', '110', '101', '110'],
    'C': ['011', '100', '100', '100', '011'], 'D': ['110', '101', '101', '101', '110'],
    'E': ['111', '100', '110', '100', '111'], 'F': ['111', '100', '110', '100', '100'],
    'G': ['011', '100', '101', '101', '011'], 'H': ['101', '101', '111', '101', '101'],
    'I': ['111', '010', '010', '010', '111'], 'K': ['101', '101', '110', '101', '101'],
    'L': ['100', '100', '100', '100', '111'], 'M': ['101', '111', '111', '101', '101'],
    'N': ['110', '101', '101', '101', '101'], 'O': ['010', '101', '101', '101', '010'],
    'P': ['110', '101', '110', '100', '100'], 'R': ['110', '101', '110', '101', '101'],
    'S': ['011', '100', '010', '001', '110'], 'T': ['111', '010', '010', '010', '010'],
    'U': ['101', '101', '101', '101', '111'], 'V': ['101', '101', '101', '101', '010'],
    'W': ['101', '101', '111', '111', '101'], 'X': ['101', '101', '010', '101', '101'],
    'Y': ['101', '101', '010', '010', '010'], 'Z': ['111', '001', '010', '100', '111'],
    '0': ['111', '101', '101', '101', '111'], '1': ['010', '110', '010', '010', '111'],
    '2': ['110', '001', '010', '100', '111'], '3': ['110', '001', '010', '001', '110'],
    '4': ['101', '101', '111', '001', '001'], '5': ['111', '100', '110', '001', '110'],
    '6': ['011', '100', '111', '101', '111'], '7': ['111', '001', '010', '010', '010'],
    '8': ['111', '101', '111', '101', '111'], '9': ['111', '101', '111', '001', '110'],
    '.': ['0', '0', '0', '0', '1'], '-': ['000', '000', '111', '000', '000'],
    '/': ['001', '001', '010', '100', '100'], ' ': ['00', '00', '00', '00', '00'],
}


def text_width(s):
    return sum(len(GLYPHS[ch][0]) + 1 for ch in s) - 1


def pixel_text(img, x, y, s, color, center=False):
    """Draw s at texel (x, y) (its top-left, or its top centre) in the 3x5 font."""
    if center:
        x = int(round(x - text_width(s) / 2))
    px = img.load()
    for ch in s:
        g = GLYPHS[ch]
        for j, row in enumerate(g):
            for i, bit in enumerate(row):
                if bit == '1' and 0 <= x + i < img.width and 0 <= y + j < img.height:
                    px[x + i, y + j] = tuple(color)
        x += len(g[0]) + 1


# --- painting in world units -------------------------------------------------------------

class Painter:
    """A supersampled canvas over a world rectangle; u0..u1 maps to the image's left..right,
    v0..v1 to its top..bottom. finish() boxes it down to the texel size."""

    def __init__(self, w, h, u0, u1, v0, v1, base, ss=4):
        self.w, self.h, self.ss = w, h, ss
        self.u0, self.u1, self.v0, self.v1 = u0, u1, v0, v1
        self.img = Image.new('RGB', (w * ss, h * ss), tuple(base))
        self.d = ImageDraw.Draw(self.img, 'RGBA')

    def p(self, u, v):
        return ((u - self.u0) / (self.u1 - self.u0) * self.w * self.ss,
                (v - self.v0) / (self.v1 - self.v0) * self.h * self.ss)

    def s(self, length):
        return abs(length / (self.u1 - self.u0) * self.w * self.ss)

    def rect(self, ua, va, ub, vb, fill, alpha=255, outline=None, width=0):
        a, b = self.p(ua, va), self.p(ub, vb)
        box = [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]
        self.d.rectangle(box, fill=tuple(fill) + (alpha,) if fill else None,
                         outline=tuple(outline) + (alpha,) if outline else None,
                         width=int(round(width * self.ss)))

    def rrect(self, ua, va, ub, vb, r, fill, alpha=255, outline=None, width=0):
        a, b = self.p(ua, va), self.p(ub, vb)
        box = [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]
        self.d.rounded_rectangle(box, radius=self.s(r), fill=tuple(fill) + (alpha,) if fill else None,
                                 outline=tuple(outline) + (alpha,) if outline else None,
                                 width=int(round(width * self.ss)))

    def circle(self, u, v, r, fill, alpha=255, outline=None, width=0):
        c, rr = self.p(u, v), self.s(r)
        self.d.ellipse([c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr],
                       fill=tuple(fill) + (alpha,) if fill else None,
                       outline=tuple(outline) + (alpha,) if outline else None,
                       width=int(round(width * self.ss)))

    def line(self, pts, color, width, alpha=255):
        self.d.line([self.p(u, v) for u, v in pts], fill=tuple(color) + (alpha,),
                    width=max(1, int(round(width * self.ss))))

    def poly(self, pts, fill, alpha=255):
        self.d.polygon([self.p(u, v) for u, v in pts], fill=tuple(fill) + (alpha,))

    def text(self, u, v, s, size, color, alpha=255, font=KANJI_FONT, anchor='mm'):
        f = ImageFont.truetype(font, int(round(self.s(size))))
        self.d.text(self.p(u, v), s, font=f, fill=tuple(color) + (alpha,), anchor=anchor)

    def sheen(self, pts, alpha):
        """A soft white highlight band (glossy plastic)."""
        layer = Image.new('RGBA', self.img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).polygon([self.p(u, v) for u, v in pts], fill=(255, 255, 255, alpha))
        from PIL import ImageFilter
        layer = layer.filter(ImageFilter.GaussianBlur(self.ss * 1.5))
        self.img.alpha_composite(layer) if self.img.mode == 'RGBA' else self.img.paste(
            Image.alpha_composite(self.img.convert('RGBA'), layer).convert('RGB'))
        self.d = ImageDraw.Draw(self.img, 'RGBA')

    def finish(self):
        return self.img.resize((self.w, self.h), Image.BOX)

    def texel(self, u, v):
        """World point to integer texel of the finished image."""
        x = (u - self.u0) / (self.u1 - self.u0) * self.w
        y = (v - self.v0) / (self.v1 - self.v0) * self.h
        return int(round(x)), int(round(y))


def logo(img, cx, cy, h, sun=SUN, moon=MOON, word=(255, 255, 255), wordmark=True, ss=8):
    """The 明 mark (日 orange, 月 pale blue) and the MEI wordmark, h texels tall, drawn into a
    finished image centred at texel (cx, cy)."""
    big = int(h * ss)
    f = ImageFont.truetype(KANJI_FONT, big)
    tile = Image.new('RGBA', (big * 4, big + 4 * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    # draw the whole kanji in moon colour, then recolour its left part (日) in sun colour
    d.text((0, 0), '明', font=f, fill=tuple(moon) + (255,))
    bbox = d.textbbox((0, 0), '明', font=f)
    split = bbox[0] + (bbox[2] - bbox[0]) * 0.40
    px = tile.load()
    for y in range(tile.height):
        for x in range(int(split)):
            if px[x, y][3]:
                px[x, y] = tuple(sun) + (px[x, y][3],)
    if wordmark:
        wf = ImageFont.truetype('/System/Library/Fonts/Avenir Next.ttc', int(big * 0.78), index=2)
        d.text((bbox[2] + big * 0.18, bbox[1] + (bbox[3] - bbox[1]) / 2), 'MEI', font=wf,
               fill=tuple(word) + (255,), anchor='lm')
    tile = tile.crop(tile.getbbox())
    tw, th = max(1, round(tile.width / ss)), max(1, round(tile.height / ss))
    small = tile.resize((tw, th), Image.LANCZOS)
    base = img.convert('RGBA')
    base.alpha_composite(small, (int(round(cx - tw / 2)), int(round(cy - th / 2))))
    return base.convert('RGB')


# --- geometry ------------------------------------------------------------------------------

def sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def r6(v):
    return [round(c, 6) for c in v]


class MeshBuilder:
    """Collects one mesh node: vertices (deduplicated per node), faces with materials and
    optional per-vertex uvs. Faces are wound outward from the hint direction given."""

    def __init__(self, ident, uv=False):
        self.id, self.uv = ident, uv
        self.verts, self.uvs, self.faces, self.mats, self.index = [], [], [], [], {}

    def v(self, p, uv=None):
        key = (tuple(r6(p)), tuple(round(c, 5) for c in uv) if uv else None)
        if key not in self.index:
            self.index[key] = len(self.verts)
            self.verts.append(r6(p))
            self.uvs.append([round(c, 5) for c in uv] if uv else [0, 0])
        return self.index[key]

    def face(self, pts, mat, out, uvs=None):
        idx = [self.v(p, uvs[i] if uvs else None) for i, p in enumerate(pts)]
        pts_ = [self.verts[i] for i in idx]
        n = [0.0, 0.0, 0.0]          # Newell's normal: right for concave polygons too
        for k in range(len(pts_)):
            p0, p1 = pts_[k], pts_[(k + 1) % len(pts_)]
            n[0] += (p0[1] - p1[1]) * (p0[2] + p1[2])
            n[1] += (p0[2] - p1[2]) * (p0[0] + p1[0])
            n[2] += (p0[0] - p1[0]) * (p0[1] + p1[1])
        if dot(n, out) < 0:
            idx.reverse()
        self.faces.append(idx)
        self.mats.append(mat)

    def node(self):
        n = {'id': self.id, 'op': 'mesh', 'vertices': self.verts, 'faces': self.faces,
             'face_materials': self.mats}
        if self.uv:
            n['uvs'] = self.uvs
        return n


def rounded_rect(hw, hd, r, inset, segs, cx=0.0, cz=0.0):
    """Plan-view outline (x, z), counter-clockwise from the +X+Z corner. Returns points and a
    list telling, for each edge i -> i+1, whether it is a straight side ('px','pz','nx','nz')
    or a corner (None)."""
    pts, kinds = [], []
    corners = [(hw - r, hd - r, 0), (-(hw - r), hd - r, 90), (-(hw - r), -(hd - r), 180),
               (hw - r, -(hd - r), 270)]
    sides = ['pz', 'nx', 'nz', 'px']
    rr = r - inset
    for k, (ox, oz, a0) in enumerate(corners):
        for s in range(segs + 1):
            a = math.radians(a0 + 90 * s / segs)
            pts.append((cx + ox + rr * math.cos(a), cz + oz + rr * math.sin(a)))
            kinds.append(None if s < segs else sides[k])
    return pts, kinds
