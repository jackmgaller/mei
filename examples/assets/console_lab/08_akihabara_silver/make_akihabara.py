#!/usr/bin/env python3
"""Akihabara Silver: writes art/*.png and the two Asset Kit recipes, console.asset.json and
controller.asset.json, beside this script. Run once; the outputs are committed.

    python3 examples/assets/console_lab/08_akihabara_silver/make_akihabara.py

Real size, metres. Models face -Z. Needs Pillow and the macOS system fonts (Hiragino, DIN).
"""
import json
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, 'art')
FONTS = '/System/Library/Fonts'
KAKU = f'{FONTS}/ヒラギノ角ゴシック W6.ttc'
KAKU_B = f'{FONTS}/ヒラギノ角ゴシック W8.ttc'
DIN = f'{FONTS}/Supplemental/DIN Alternate Bold.ttf'
DINC = f'{FONTS}/Supplemental/DIN Condensed Bold.ttf'
SS = 4                      # supersampling for painted art

# ---------------------------------------------------------------------------------------------
# Palette

SILVER = (198, 203, 210)
SILVER_HI = (232, 235, 239)
SILVER_LO = (150, 156, 165)
GUN = (82, 87, 96)
GUN_HI = (116, 122, 132)
GUN_DK = (46, 49, 56)
INK = (22, 24, 28)
SUN = (247, 168, 60)
MOON = (170, 200, 240)
WHITE = (246, 247, 249)


def hx(c):
    return '#%02x%02x%02x' % c


# ---------------------------------------------------------------------------------------------
# Painting helpers

def font(path, px):
    return ImageFont.truetype(path, max(1, int(px)))


class Canvas:
    """A supersampled painting, saved downsampled to its texel size."""

    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.im = Image.new('RGB', (w*SS, h*SS), bg)
        self.d = ImageDraw.Draw(self.im)

    def rect(self, x0, y0, x1, y1, fill, r=0, outline=None, width=1):
        box = [x0*SS, y0*SS, x1*SS-1, y1*SS-1]
        if r:
            self.d.rounded_rectangle(box, r*SS, fill=fill, outline=outline, width=max(1, int(round(width*SS))) if outline else 0)
        else:
            self.d.rectangle(box, fill=fill, outline=outline, width=max(1, int(round(width*SS))) if outline else 0)

    def ellipse(self, cx, cy, rx, ry, fill, outline=None, width=1):
        self.d.ellipse([(cx-rx)*SS, (cy-ry)*SS, (cx+rx)*SS, (cy+ry)*SS], fill=fill,
                       outline=outline, width=max(1, int(round(width*SS))) if outline else 0)

    def line(self, pts, fill, width=1):
        self.d.line([(x*SS, y*SS) for x, y in pts], fill=fill, width=max(1, int(width*SS)))

    def poly(self, pts, fill):
        self.d.polygon([(x*SS, y*SS) for x, y in pts], fill=fill)

    def text(self, x, y, s, f, px, fill, anchor='la', spacing=0.0):
        fo = font(f, px*SS)
        if not spacing:
            self.d.text((x*SS, y*SS), s, font=fo, fill=fill, anchor=anchor)
            return
        # letter-spaced, anchored left/centre by measuring
        widths = [fo.getlength(ch) + spacing*SS for ch in s]
        total = sum(widths) - spacing*SS
        cx = x*SS - (total/2 if anchor[0] == 'm' else 0)
        for ch, wd in zip(s, widths):
            self.d.text((cx, y*SS), ch, font=fo, fill=fill, anchor='l' + anchor[1])
            cx += wd

    def save(self, name):
        out = self.im.resize((self.w, self.h), Image.LANCZOS)
        out.save(os.path.join(ART, name))
        return f'art/{name}'


def brushed(c, w, h, horizontal=True, seed=1, sheen=None, amp=7):
    """Hairline brushing: rows (or columns) of slightly varied brightness, plus an optional
    diagonal sheen band (a function of (x, y) in 0-1 returning a brightness offset)."""
    rnd = random.Random(seed)
    im = Image.new('RGB', (w*SS, h*SS))
    px = im.load()
    n = h*SS if horizontal else w*SS
    lines = []
    v = 0.0
    for _ in range(n):
        v = v*0.55 + rnd.uniform(-amp, amp)
        lines.append(v)
    for y in range(h*SS):
        for x in range(w*SS):
            k = lines[y] if horizontal else lines[x]
            s = sheen(x/(w*SS), y/(h*SS)) if sheen else 0
            px[x, y] = tuple(max(0, min(255, int(ch + k + s))) for ch in c)
    cv = Canvas(w, h, c)
    cv.im = im
    cv.d = ImageDraw.Draw(im)
    return cv


def diag_sheen(strength=22, width=0.18, at=0.35, slope=0.6):
    def f(u, v):
        t = u + v*slope - at
        return strength*math.exp(-(t/width)**2) - strength*0.25
    return f


# ---------------------------------------------------------------------------------------------
# Mesh helpers: explicit `mesh` nodes with one material per polygon

def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def dot(a, b): return sum(x*y for x, y in zip(a, b))


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for a, b in zip(pts, pts[1:]+pts[:1]):
        c = cross(a, b)
        n = [n[i]+c[i] for i in range(3)]
    return tuple(n)


def r6(v):
    return round(v, 6)


class Mesh:
    def __init__(self):
        self.v, self.index, self.f, self.fm = [], {}, [], []

    def vid(self, p):
        key = tuple(r6(x) for x in p)
        if key not in self.index:
            self.index[key] = len(self.v)
            self.v.append(list(key))
        return self.index[key]

    def face(self, pts, mat, out):
        """A planar polygon; reordered so its normal points along `out`."""
        if dot(newell(pts), out) < 0:
            pts = pts[::-1]
        self.f.append([self.vid(p) for p in pts])
        self.fm.append(mat)

    def quad_or_tris(self, pts, mat, out):
        pts = [tuple(r6(x) for x in p) for p in pts]
        a, b, c, d = pts
        n = newell(pts)
        ln = math.sqrt(dot(n, n)) or 1
        n = tuple(x/ln for x in n)
        extent = max(math.sqrt(dot(sub(p, a), sub(p, a))) for p in pts)
        if all(abs(dot(n, sub(p, a))) < extent*1e-7 for p in pts):
            self.face(pts, mat, out)
        else:
            self.face([a, b, c], mat, out)
            self.face([a, c, d], mat, out)

    def node(self, id, transform=None):
        n = {'id': id, 'op': 'mesh', 'vertices': self.v, 'faces': self.f,
             'face_materials': self.fm, 'material': self.fm[0]}
        if transform:
            n['transform'] = transform
        return n


def ring_area(pts):
    return sum(a[0]*b[1]-a[1]*b[0] for a, b in zip(pts, pts[1:]+pts[:1]))


def ring_loft(m, rings, side_mat, top=None, bottom=None):
    """rings: [(y, [(x, z), ...]), ...] bottom to top, same count and order, counter-clockwise
    in (x, z). side_mat(band, seg) -> material. top/bottom: cap materials or None."""
    n = len(rings[0][1])
    for band in range(len(rings)-1):
        (y0, r0), (y1, r1) = rings[band], rings[band+1]
        for s in range(n):
            t = (s+1) % n
            a = (r0[s][0], y0, r0[s][1]); b = (r0[t][0], y0, r0[t][1])
            c = (r1[t][0], y1, r1[t][1]); d = (r1[s][0], y1, r1[s][1])
            dx, dz = r0[t][0]-r0[s][0], r0[t][1]-r0[s][1]
            out = (dz, 0.0, -dx)
            m.quad_or_tris([a, b, c, d], side_mat(band, s), out)
    if top:
        y, r = rings[-1]
        m.face([(x, y, z) for x, z in r], top, (0, 1, 0))
    if bottom:
        y, r = rings[0]
        m.face([(x, y, z) for x, z in r], bottom, (0, -1, 0))


def slab(m, x0, x1, y0, y1, z0, z1, mats, default, open=()):
    """An axis-aligned box as polygons; mats by side: top, bottom, left (-X), right (+X),
    front (-Z, the model's front), back (+Z)."""
    P = lambda x, y, z: (x, y, z)
    sides = {
        'top': ([P(x0, y1, z0), P(x1, y1, z0), P(x1, y1, z1), P(x0, y1, z1)], (0, 1, 0)),
        'bottom': ([P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1)], (0, -1, 0)),
        'left': ([P(x0, y0, z0), P(x0, y1, z0), P(x0, y1, z1), P(x0, y0, z1)], (-1, 0, 0)),
        'right': ([P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)], (1, 0, 0)),
        'front': ([P(x0, y0, z0), P(x1, y0, z0), P(x1, y1, z0), P(x0, y1, z0)], (0, 0, -1)),
        'back': ([P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)], (0, 0, 1)),
    }
    for k, (pts, out) in sides.items():
        if k not in open:
            m.face(pts, mats.get(k, default), out)


def prism_x(m, profile, x0, x1, mats, default, cap_mat=None, skip=()):
    """A profile in (z, y), counter-clockwise as seen from +X, swept from x0 to x1. mats[k] is
    the material of the strip from point k to k+1; cap_mat the two end polygons."""
    n = len(profile)
    for k in range(n):
        if k in skip:
            continue
        (za, ya), (zb, yb) = profile[k], profile[(k+1) % n]
        dz, dy = zb-za, yb-ya
        out = (0.0, -dz, dy)
        m.face([(x0, ya, za), (x0, yb, zb), (x1, yb, zb), (x1, ya, za)], mats.get(k, default), out)
    cap = cap_mat or default
    m.face([(x1, y, z) for z, y in profile], cap, (1, 0, 0))
    m.face([(x0, y, z) for z, y in profile], cap, (-1, 0, 0))


def prism_y(m, pts, y0, y1, top, side, bottom=None):
    """A polygon in (x, z) swept from y0 to y1."""
    rings = [(y0, pts), (y1, pts)]
    if ring_area(pts) < 0:
        rings = [(y0, pts[::-1]), (y1, pts[::-1])]
    ring_loft(m, rings, lambda b, s: side, top=top, bottom=bottom)


def circle(r, n, cx=0.0, cz=0.0, phase=0.5):
    return [(cx + r*math.cos(2*math.pi*(i+phase)/n), cz + r*math.sin(2*math.pi*(i+phase)/n)) for i in range(n)]


def tex_fit(path, bits=8):
    return {'image': path, 'bits': bits, 'projection': 'fit'}


def write(name, recipe):
    with open(os.path.join(HERE, name), 'w') as f:
        json.dump(recipe, f, indent=1)
        f.write('\n')


VERIFY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'direction': [-0.45, 0.85, -0.4], 'ambient': 0.5}

# =============================================================================================
# The console
#
# 300 x 230 mm, 62 mm to the top of the silver body, 79 mm over the heat-sink deck's slot
# housing. A silver body with a chamfered front edge on a recessed gunmetal plinth; the rear
# half of the top is a gunmetal heat-sink deck with twenty silver fins either side of the
# cart slot. Front: two controller ports with memory card slots above them, two LEDs.
# Top front: the 明 badge, and the power (sun) and reset (moon) buttons.

W2, ZF, ZB, CC = 0.150, -0.115, 0.115, 0.008
YB, Y1, YT, CH = 0.010, 0.046, 0.062, 0.015


def body_ring(y, fz):
    return [(-W2+CC, fz), (W2-CC, fz), (W2, fz+CC), (W2, ZB-CC), (W2-CC, ZB), (-W2+CC, ZB),
            (-W2, ZB-CC), (-W2, fz+CC)]


TOP_X = (-W2, W2)
TOP_Z = (ZF+CH, ZB)
FRONT_X = (-W2+CC, W2-CC)

PORTS_X = (-0.111, -0.071)
SOCK_Y = (0.0155, 0.0285)
CARD_Y = (0.0335, 0.0395)
LED_X = (0.050, 0.094)
LED_Y = (0.0215, 0.0315)
PWR = (0.083, -0.080, 0.0110)
RST = (0.119, -0.080, 0.0080)
BADGE = (-0.136, -0.046, -0.094, -0.064)     # x0 x1 z0 z1
HOUS_W2, CART_W2 = 0.045, 0.036


def paint_console():
    os.makedirs(ART, exist_ok=True)
    out = {}

    # --- top: brushed silver with a broad sheen, POWER / RESET legends, a holo sticker
    W, H = 180, 127
    tw, th = TOP_X[1]-TOP_X[0], TOP_Z[1]-TOP_Z[0]
    U = lambda x: (x-TOP_X[0])/tw*W
    V = lambda z: (TOP_Z[1]-z)/th*H
    cv = brushed(SILVER, W, H, horizontal=True, seed=3, sheen=diag_sheen(26, 0.16, 0.45, 0.9), amp=6)
    # a thin engraved line framing the front zone
    cv.line([(U(-0.142), V(-0.054)), (U(0.142), V(-0.054))], SILVER_LO, 0.6)
    cv.line([(U(-0.142), V(-0.0545)+0.7), (U(0.142), V(-0.0545)+0.7)], SILVER_HI, 0.5)
    for (x, z, r), label in ((PWR, 'POWER'), (RST, 'RESET')):
        cv.ellipse(U(x), V(z), r/tw*W+1.3, r/th*H+1.3, None, outline=GUN, width=0.5)
        cv.text(U(x), V(-0.0975), label, DINC, 5.2, GUN_DK, anchor='mm', spacing=0.5)
    # power: a small orange LED dot between the legends
    cv.ellipse(U(0.101), V(-0.0975), 1.0, 1.0, SUN)
    # holo spec sticker, front-centre
    sx0, sx1, sz0, sz1 = -0.030, 0.034, -0.092, -0.066
    x0, x1, y0, y1 = U(sx0), U(sx1), V(sz1), V(sz0)
    holo = Image.new('RGB', (int((x1-x0)*SS), int((y1-y0)*SS)))
    hp = holo.load()
    for yy in range(holo.size[1]):
        for xx in range(holo.size[0]):
            t = (xx/holo.size[0])*1.4 + (yy/holo.size[1])*0.6
            r = 205 + 40*math.sin(6.28*t)
            g = 205 + 40*math.sin(6.28*t + 2.1)
            b = 210 + 40*math.sin(6.28*t + 4.2)
            hp[xx, yy] = tuple(int(max(150, min(255, c))) for c in (r, g, b))
    cv.im.paste(holo, (int(x0*SS), int(y0*SS)))
    cv.rect(x0, y0, x1, y1, None, outline=SILVER_LO, width=0.4)
    cv.text((x0+x1)/2, y0+5.2, '64-BIT', DIN, 6.2, INK, anchor='mm', spacing=0.3)
    cv.text((x0+x1)/2, y0+11.4, 'PRISM ENGINE', DINC, 4.6, GUN_DK, anchor='mm', spacing=0.4)
    out['c_top'] = cv.save('c_top.png')

    # --- front face (seen from the front: u along +X, v down)
    W, H = 240, 30
    fw, fh = FRONT_X[1]-FRONT_X[0], Y1-YB
    U = lambda x: (x-FRONT_X[0])/fw*W
    V = lambda y: (Y1-y)/fh*H
    cv = brushed(SILVER, W, H, horizontal=True, seed=5, sheen=diag_sheen(18, 0.2, 0.55, 0.3), amp=6)
    # recessed port well behind each port pair
    for k, x in enumerate(PORTS_X):
        cv.rect(U(x-0.0185), V(0.0425), U(x+0.0185), V(0.0125), GUN, r=1.5)
        cv.rect(U(x-0.0185)+0.5, V(0.0425)+0.5, U(x+0.0185)-0.5, V(0.0125)-0.5, GUN_DK, r=1.2)
    # LED legends under the window
    cv.text(U(0.061), V(0.0165), 'POWER', DINC, 3.6, GUN, anchor='mm', spacing=0.3)
    cv.text(U(0.083), V(0.0165), 'MEINET', DINC, 3.6, GUN, anchor='mm', spacing=0.3)
    # ribs at the right: horizontal grooves
    for i in range(6):
        y = 0.0175 + i*0.0042
        cv.line([(U(0.103), V(y)), (U(0.138), V(y))], GUN, 0.9)
        cv.line([(U(0.103), V(y)+0.9), (U(0.138), V(y)+0.9)], SILVER_HI, 0.5)
    # a gunmetal line along the foot
    cv.rect(0, H-2.2, W, H, GUN_HI)
    out['c_front'] = cv.save('c_front.png')

    # --- front chamfer band: the spec print (seen from the front and above)
    W, H = 240, 18
    cv = brushed(GUN, W, H, horizontal=True, seed=7, amp=5)
    cv.rect(0, 0, W, 0.8, GUN_HI)
    U = lambda x: (x-FRONT_X[0])/(FRONT_X[1]-FRONT_X[0])*W
    for k, x in enumerate(PORTS_X):       # port numbers over the ports
        cv.rect(U(x)-5.5, 3.5, U(x)+5.5, H-3.5, GUN_DK, r=1.5)
        cv.text(U(x), H/2+0.4, str(k+1), DIN, 9, SILVER_HI, anchor='mm')
    specs = '64-BIT RISC  ·  PRISM ENGINE 3D  ·  64MB CARTRIDGE  ·  MEINET'
    fo = font(DINC, 6.6*SS)
    tw_ = fo.getlength(specs)/SS
    cv.text(W-9-tw_, H/2+0.4, specs, DINC, 6.6, SILVER_HI, anchor='lm')
    bx = W-9-tw_-9
    cv.rect(bx-0.8, 4, bx+0.8, H-4, SUN)
    cv.rect(bx+2.4, 4, bx+4.0, H-4, MOON)
    out['c_chamfer'] = cv.save('c_chamfer.png')

    # --- sides: vent louvres (seen from outside; symmetric)
    W, H = 128, 24
    cv = brushed(SILVER, W, H, horizontal=True, seed=9, amp=6)
    n = 22
    for i in range(n):
        x = 12 + i*(W-24)/(n-1)
        cv.rect(x-1.4, 4.5, x+1.4, H-5, INK, r=1.2)
        cv.line([(x+1.6, 5), (x+1.6, H-5.5)], SILVER_HI, 0.5)
    cv.rect(0, H-1.6, W, H, GUN_HI)
    out['c_side'] = cv.save('c_side.png')

    # --- rear (seen from behind: u along -X)
    W, H = 240, 30
    cv = brushed(SILVER_LO, W, H, horizontal=True, seed=11, amp=5)
    # from the viewer's left (+X) to right (-X): DC IN, AV MULTI OUT, ANT IN (MeiNet), EXT
    cv.ellipse(28, 13, 5, 5, GUN_DK); cv.ellipse(28, 13, 1.6, 1.6, SILVER)
    cv.text(28, 24.5, 'DC IN 12V', DINC, 4.2, GUN_DK, anchor='mm')
    cv.rect(70, 8, 108, 18, GUN_DK, r=2); cv.rect(73, 11, 105, 15, INK, r=1)
    cv.text(89, 24.5, 'AV MULTI OUT', DINC, 4.2, GUN_DK, anchor='mm')
    cv.ellipse(140, 13, 5.5, 5.5, SILVER_HI); cv.ellipse(140, 13, 3.6, 3.6, GUN_DK)
    cv.ellipse(140, 13, 0.8, 0.8, SILVER_HI)
    cv.text(140, 24.5, 'ANT IN · MEINET', DINC, 4.2, GUN_DK, anchor='mm')
    # model sticker
    cv.rect(170, 5, 230, 22, WHITE)
    cv.text(173, 9, 'MEI  MODEL MEI-1000', DINC, 4.0, INK, anchor='lm')
    cv.text(173, 14, 'AC100V 50/60Hz 12W', DINC, 3.6, GUN_DK, anchor='lm')
    for i in range(30):
        if (i*7) % 5 < 3:
            cv.rect(173+i*1.6, 17, 173+i*1.6+0.9, 21, INK)
    cv.rect(0, H-1.6, W, H, GUN)
    out['c_rear'] = cv.save('c_rear.png')

    # --- the 明 badge: smoked gunmetal plate, chrome rim
    W, H = 96, 32
    cv = brushed(GUN_DK, W, H, horizontal=True, seed=13, amp=4)
    cv.rect(0, 0, W, H, None, outline=SILVER, width=1)
    cv.rect(1, 1, W-1, H-1, None, outline=GUN_HI, width=0.5)
    # 日 and 月 as one 明 glyph, each half coloured: draw twice and mask
    gx, gy, gs = 5, 4.5, 23
    for color, keep in ((SUN, 'left'), (MOON, 'right')):
        layer = Image.new('L', cv.im.size, 0)
        ImageDraw.Draw(layer).text((gx*SS, gy*SS), '明', font=font(KAKU_B, gs*SS), fill=255)
        mask = Image.new('L', cv.im.size, 0)
        split = (gx + gs*0.43)*SS
        md = ImageDraw.Draw(mask)
        if keep == 'left':
            md.rectangle([0, 0, split, cv.im.size[1]], fill=255)
        else:
            md.rectangle([split, 0, cv.im.size[0], cv.im.size[1]], fill=255)
        from PIL import ImageChops
        layer = ImageChops.multiply(layer, mask)
        cv.im.paste(Image.new('RGB', cv.im.size, color), (0, 0), layer)
    cv.text(34, 13.5, 'MEI', DIN, 15, WHITE, anchor='lm', spacing=1.0)
    cv.text(34.5, 24.5, 'SUN & MOON SYSTEM', DINC, 5.0, SILVER, anchor='lm', spacing=0.35)
    out['c_badge'] = cv.save('c_badge.png')

    # --- cart label (front face of the cartridge)
    W, H = 56, 30
    cv = Canvas(W, H, (58, 62, 70))
    cv.rect(3, 3, W-3, H-3, (20, 34, 74), r=1.5)
    # a night-sky title card: moon over a skyline, sun rising in the corner
    for i in range(20):
        t = i/19
        col = tuple(int(a + (b-a)*t) for a, b in zip((22, 36, 88), (226, 128, 92)))
        cv.rect(3.5, 3.5+i*1.25, W-3.5, 3.5+(i+1)*1.25, col)
    cv.ellipse(42, 10, 4.2, 4.2, (238, 240, 226))
    cv.ellipse(44, 9, 3.6, 3.6, (40, 58, 120))
    for i, hgt in enumerate((7, 11, 5, 9, 13, 6, 10, 8, 6, 9)):
        x = 3.5 + i*4.9
        cv.rect(x, H-3.5-hgt, x+4.4, H-3.5, (18, 20, 34))
        for wy in range(int(hgt)//3):
            cv.rect(x+1.2, H-3.5-hgt+1.5+wy*3, x+2.2, H-3.5-hgt+2.5+wy*3, (250, 210, 120))
    cv.text(6, 7.5, 'NEON', DIN, 7, WHITE, anchor='lm', spacing=0.6)
    cv.text(6, 14, 'MOON', DIN, 7, SUN, anchor='lm', spacing=0.6)
    cv.rect(3, H-4.2, W-3, H-3, SILVER)
    out['cart_label'] = cv.save('cart_label.png')

    # --- slot housing top: the slot mouth and its dust flaps around the cart
    W, H = 46, 42
    cv = brushed(GUN_DK, W, H, horizontal=False, seed=15, amp=4)
    # the housing's top spans x +-0.040, z 0.012 - 0.096
    U = lambda x: (x+HOUS_W2)/(2*HOUS_W2)*W
    V = lambda z: (0.096-z)/0.084*H
    cv.rect(U(-CART_W2-0.0035), V(0.0605), U(CART_W2+0.0035), V(0.0365), INK, r=1.2)
    cv.rect(U(-CART_W2-0.0035), V(0.0605), U(CART_W2+0.0035), V(0.0365), None, outline=GUN_HI, width=0.5)
    for i in range(6):
        z = 0.016 + i*0.0032
        cv.line([(U(-CART_W2), V(z)), (U(CART_W2), V(z))], GUN_HI, 0.5)
    cv.text(W/2, V(0.083), 'CARTRIDGE', DINC, 3.4, GUN_HI, anchor='mm', spacing=0.25)
    out['c_slot'] = cv.save('c_slot.png')

    # --- sockets and slits
    W, H = 32, 14
    cv = Canvas(W, H, GUN)
    cv.rect(0.5, 0.5, W-0.5, H-0.5, INK, r=3.5)
    cv.rect(5, 4.5, W-5, 9.5, GUN_DK, r=1)
    for i in range(7):
        cv.rect(7+i*3, 6, 8.2+i*3, 8, SILVER_LO)
    out['c_socket'] = cv.save('c_socket.png')
    W, H = 32, 8
    cv = Canvas(W, H, GUN)
    cv.rect(2, 2.5, W-2, H-2.5, INK, r=0.6)
    out['c_card'] = cv.save('c_card.png')

    # --- LED window (emissive)
    W, H = 44, 10
    cv = Canvas(W, H, (16, 18, 22))
    cv.rect(0, 0, W, 1.2, (40, 44, 52))
    cv.ellipse(11, 5.2, 2.6, 2.6, (120, 60, 20))
    cv.ellipse(11, 5.2, 1.7, 1.7, SUN)
    cv.ellipse(10.4, 4.6, 0.6, 0.6, (255, 236, 200))
    cv.ellipse(33, 5.2, 2.6, 2.6, (40, 60, 100))
    cv.ellipse(33, 5.2, 1.7, 1.7, MOON)
    cv.ellipse(32.4, 4.6, 0.6, 0.6, (240, 248, 255))
    out['c_led'] = cv.save('c_led.png')

    # --- power (sun) and reset (moon) button tops, disc projection
    for name, ring, glyph in (('c_power', SUN, 'sun'), ('c_reset', MOON, 'moon')):
        W = 32
        cv = Canvas(W, W, GUN)
        c = W/2
        cv.ellipse(c, c, 15.5, 15.5, GUN_HI)
        cv.ellipse(c, c, 13.5, 13.5, GUN)
        cv.ellipse(c, c, 11.5, 11.5, ring)
        cv.ellipse(c, c, 9.6, 9.6, GUN_DK)
        if glyph == 'sun':
            cv.ellipse(c, c, 5.2, 5.2, None, outline=SUN, width=1.6)
            cv.rect(c-0.9, c-7.5, c+0.9, c-1.5, GUN_DK)
            cv.rect(c-0.8, c-7.2, c+0.8, c+0.5, SUN)
        else:
            cv.ellipse(c, c, 5.5, 5.5, MOON)
            cv.ellipse(c+2.6, c-1.6, 4.8, 4.8, GUN_DK)
        out[name] = cv.save(f'{name}.png')

    # --- brushed tiles (repeating, 4-bit)
    for name, col, horiz, seed in (('t_silver', SILVER, True, 21), ('t_gun', GUN, True, 23),
                                   ('t_fin', (220, 224, 230), False, 25)):
        rnd = random.Random(seed)
        im = Image.new('RGB', (32, 32))
        p = im.load()
        vals = [rnd.uniform(-7, 7) for _ in range(32)]
        vals = [(vals[i-1]+2*vals[i]+vals[(i+1) % 32])/4 for i in range(32)]
        for y in range(32):
            for x in range(32):
                k = vals[y] if horiz else vals[x]
                p[x, y] = tuple(max(0, min(255, int(ch+k))) for ch in col)
        im.save(os.path.join(ART, f'{name}.png'))
        out[name] = f'art/{name}.png'
    return out


def console():
    art = paint_console()
    mats = {
        'top': {'color': hx(SILVER), 'texture': tex_fit(art['c_top'])},
        'front': {'color': hx(SILVER), 'texture': tex_fit(art['c_front'])},
        'chamfer': {'color': hx(GUN), 'texture': tex_fit(art['c_chamfer'])},
        'side': {'color': hx(SILVER), 'texture': tex_fit(art['c_side'])},
        'rear': {'color': hx(SILVER_LO), 'texture': tex_fit(art['c_rear'])},
        'silver': {'color': hx(SILVER), 'texture': {'image': art['t_silver'], 'projection': 'box', 'scale': [0.08, 0.08]}},
        'gun': {'color': hx(GUN), 'texture': {'image': art['t_gun'], 'projection': 'box', 'scale': [0.08, 0.08]}},
        'fin': {'color': '#dce0e6', 'texture': {'image': art['t_fin'], 'projection': 'box', 'scale': [0.06, 0.06]}},
        'gun_dk': {'color': hx(GUN_DK)},
        'ink': {'color': hx(INK)},
        'badge': {'color': hx(GUN_DK), 'texture': tex_fit(art['c_badge'])},
        'slot': {'color': hx(GUN_DK), 'texture': tex_fit(art['c_slot'])},
        'socket': {'color': hx(INK), 'texture': tex_fit(art['c_socket'], 4)},
        'card': {'color': hx(INK), 'texture': tex_fit(art['c_card'], 4)},
        'led': {'color': hx(SUN), 'class': 'emissive', 'texture': tex_fit(art['c_led'])},
        'power': {'color': hx(SUN), 'texture': {'image': art['c_power'], 'bits': 8, 'projection': 'disc'}},
        'reset': {'color': hx(MOON), 'texture': {'image': art['c_reset'], 'bits': 8, 'projection': 'disc'}},
        'cart': {'color': '#3e424a'},
        'cart_label': {'color': '#28305a', 'texture': tex_fit(art['cart_label'])},
    }
    nodes = []

    # body: chamfered front edge, chamfered vertical corners
    m = Mesh()
    rings = [(YB, body_ring(YB, ZF)), (Y1, body_ring(Y1, ZF)), (YT, body_ring(YT, ZF+CH))]
    lower = {0: 'front', 2: 'side', 4: 'rear', 6: 'side'}
    upper = {0: 'chamfer'}
    ring_loft(m, rings, lambda b, s: (lower if b == 0 else upper).get(s, 'silver'), top='top', bottom='gun_dk')
    nodes.append(m.node('body'))

    # plinth: a recessed gunmetal foot ring
    m = Mesh()
    slab(m, -0.136, 0.136, 0.0, YB+0.0012, -0.101, 0.103, {}, 'gun_dk', open=('top', 'bottom'))
    nodes.append(m.node('plinth'))

    # heat-sink deck over the rear half
    m = Mesh()
    DY0, DY1 = YT-0.0015, YT+0.0065
    deck_profile = [(-0.004, DY0), (0.108, DY0), (0.108, DY1), (0.004, DY1), (-0.004, DY1-0.004)]
    prism_x(m, deck_profile, -0.141, 0.141, {}, 'gun', skip=(0,))
    nodes.append(m.node('deck'))

    # fins: twenty per side, a raked front edge
    fins = []
    pitch = 0.0089
    for side in (-1, 1):
        for i in range(10):
            xc = side*(0.0545 + i*pitch)
            m = Mesh()
            fy0, fy1 = DY1-0.0015, DY1+0.0075
            prof = [(0.002, fy0), (0.104, fy0), (0.104, fy1), (0.016, fy1)]
            prism_x(m, prof, xc-0.00175, xc+0.00175, {}, 'fin', skip=(0,))
            fins.append(m.node(f'fin_{"l" if side < 0 else "r"}{i}'))
    nodes.append({'id': 'fins', 'op': 'group', 'children': fins})

    # cart slot housing, raised in the middle of the deck
    m = Mesh()
    HY1 = 0.0795
    hprof = [(0.004, DY1-0.002), (0.096, DY1-0.002), (0.096, HY1), (0.012, HY1), (0.004, HY1-0.006)]
    prism_x(m, hprof, -HOUS_W2, HOUS_W2, {2: 'slot'}, 'gun', skip=(0,))
    nodes.append(m.node('slot_housing'))

    # the cartridge standing in the slot
    m = Mesh()
    cprof = [(0.042, HY1-0.002), (0.055, HY1-0.002), (0.055, 0.1135), (0.0525, 0.117),
             (0.0445, 0.117), (0.042, 0.1135)]
    prism_x(m, cprof, -CART_W2, CART_W2, {5: 'cart_label'}, 'cart', skip=(0,))
    nodes.append(m.node('cartridge'))
    # grip ridges on the cart's back
    ridges = []
    for i in range(5):
        m = Mesh()
        y = 0.088 + i*0.005
        slab(m, -CART_W2+0.006, CART_W2-0.006, y, y+0.0022, 0.0545, 0.0565, {}, 'cart', open=('front',))
        ridges.append(m.node(f'ridge{i}'))
    nodes.append({'id': 'cart_ridges', 'op': 'group', 'children': ridges})

    # 明 badge on the top front-left
    m = Mesh()
    x0, x1, z0, z1 = BADGE
    slab(m, x0, x1, YT-0.001, YT+0.0014, z0, z1, {'top': 'badge'}, 'silver', open=('bottom',))
    nodes.append(m.node('badge'))

    # power (sun) and reset (moon)
    for name, (x, z, r), mat in (('power', PWR, 'power'), ('reset', RST, 'reset')):
        m = Mesh()
        prism_y(m, circle(r, 16), -0.004, 0.004, top=mat, side='gun')
        nodes.append(m.node(name, {'translate': [x, YT+0.0005, z]}))

    # front: port sockets, card slits, LED window
    zf = ZF
    ports = []
    for k, x in enumerate(PORTS_X):
        m = Mesh()
        slab(m, x-0.0155, x+0.0155, SOCK_Y[0], SOCK_Y[1], zf-0.0035, zf+0.002, {'front': 'socket'}, 'gun', open=('back',))
        ports.append(m.node(f'port{k+1}'))
        m = Mesh()
        slab(m, x-0.0160, x+0.0160, CARD_Y[0], CARD_Y[1], zf-0.0022, zf+0.002, {'front': 'card'}, 'gun', open=('back',))
        ports.append(m.node(f'card{k+1}'))
    nodes.append({'id': 'ports', 'op': 'group', 'children': ports})
    m = Mesh()
    slab(m, LED_X[0], LED_X[1], LED_Y[0], LED_Y[1], zf-0.0015, zf+0.002, {'front': 'led'}, 'gun_dk', open=('back',))
    nodes.append(m.node('led_window'))

    recipe = {
        'format': 'mei-asset', 'version': 1, 'name': 'akihabara_console',
        'budget': {'vertices': 1400, 'triangles': 1200},
        'materials': mats,
        'lighting': LIGHT,
        'verification': VERIFY,
        'nodes': nodes,
    }
    write('console.asset.json', recipe)


# =============================================================================================
# The controller
#
# 154 x 105 mm, grips toward the player (-Z), shoulders at +Z. A silver top shell with a
# printed face plate over a gunmetal lower shell; ribbed gunmetal grips; a d-pad left, A B X Y
# right, one analog stick in the middle between the grips, Start and Select above it, L and R
# on the shoulders.

HALF = [(0.000, 0.036), (0.030, 0.040), (0.052, 0.040), (0.066, 0.035), (0.074, 0.024),
        (0.077, 0.008), (0.076, -0.012), (0.071, -0.033), (0.063, -0.052), (0.053, -0.063),
        (0.042, -0.065), (0.033, -0.058), (0.027, -0.042), (0.020, -0.027), (0.010, -0.020),
        (0.000, -0.018)]
OUTLINE = HALF + [(-x, z) for x, z in reversed(HALF[1:-1])]   # right side first, then left
if ring_area(OUTLINE) < 0:
    OUTLINE = OUTLINE[::-1]

TOPY = 0.027
DPAD = (-0.047, 0.006)
ABXY = (0.047, 0.006)
ABXY_R, BTN_R = 0.0125, 0.0058
STICK = (0.0, -0.010)
STSE = ((-0.0115, 0.016), (0.0115, 0.016))


def inset(pts, d):
    """The outline moved inward by d (mitred), same point count."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2 = pts[i-1], pts[i], pts[(i+1) % n]
        def nrm(a, b):
            dx, dz = b[0]-a[0], b[1]-a[1]
            l = math.hypot(dx, dz)
            return (-dz/l, dx/l)            # inward for a counter-clockwise ring
        n1, n2 = nrm(p0, p1), nrm(p1, p2)
        bx, bz = n1[0]+n2[0], n1[1]+n2[1]
        k = 1 + n1[0]*n2[0] + n1[1]*n2[1]
        out.append((p1[0] + d*bx/k, p1[1] + d*bz/k))
    return out


FACE_RING = inset(OUTLINE, 0.0055)
FX = (min(p[0] for p in FACE_RING), max(p[0] for p in FACE_RING))
FZ = (min(p[1] for p in FACE_RING), max(p[1] for p in FACE_RING))


def paint_controller():
    out = {}
    W, H = 128, 84
    fw, fd = FX[1]-FX[0], FZ[1]-FZ[0]
    U = lambda x: (x-FX[0])/fw*W
    V = lambda z: (FZ[1]-z)/fd*H
    sx, sz = W/fw, H/fd                      # texels per metre
    cv = brushed(SILVER, W, H, horizontal=True, seed=31, sheen=diag_sheen(24, 0.18, 0.5, 0.8), amp=6)
    # ribbed gunmetal grips
    for side in (-1, 1):
        cx, cz = side*0.052, -0.062
        layer = Image.new('L', cv.im.size, 0)
        ld = ImageDraw.Draw(layer)
        rx, rz = 0.034*sx*SS, 0.034*sz*SS
        ld.ellipse([U(cx)*SS-rx, V(cz)*SS-rz, U(cx)*SS+rx, V(cz)*SS+rz], fill=255)
        grip = brushed(GUN, W, H, horizontal=True, seed=33, amp=4)
        for i in range(14):
            y = V(-0.030) + i*2.0
            grip.line([(0, y), (W, y)], GUN_DK, 0.7)
        cv.im.paste(grip.im, (0, 0), layer)
        edge = Image.new('L', cv.im.size, 0)
        ImageDraw.Draw(edge).ellipse([U(cx)*SS-rx, V(cz)*SS-rz, U(cx)*SS+rx, V(cz)*SS+rz],
                                     outline=255, width=int(0.7*SS))
        cv.im.paste(Image.new('RGB', cv.im.size, SILVER_HI), (0, 0), edge)
    # the gunmetal centre spine, as the console's deck: logo, start / select, the stick
    spine = [(-0.024, 0.0345), (0.024, 0.0345), (0.019, -0.006), (0.017, -0.024), (-0.017, -0.024), (-0.019, -0.006)]
    pts = [(U(x), V(z)) for x, z in spine]
    sp = brushed(GUN, W, H, horizontal=True, seed=35, amp=4)
    layer = Image.new('L', cv.im.size, 0)
    ImageDraw.Draw(layer).polygon([(x*SS, y*SS) for x, y in pts], fill=255)
    layer = layer.filter(ImageFilter.GaussianBlur(SS*0.3))
    cv.im.paste(sp.im, (0, 0), layer)
    cv.line(pts + [pts[0]], SILVER_HI, 0.5)
    # d-pad well
    x, z = DPAD
    cv.ellipse(U(x), V(z), 0.0185*sx, 0.0185*sz, GUN_HI)
    cv.ellipse(U(x), V(z), 0.0172*sx, 0.0172*sz, GUN_DK)
    # A B X Y wells
    x, z = ABXY
    cv.ellipse(U(x), V(z), 0.0215*sx, 0.0215*sz, None, outline=SILVER_LO, width=0.6)
    for dx, dz in ((ABXY_R, 0), (0, -ABXY_R), (0, ABXY_R), (-ABXY_R, 0)):
        cv.ellipse(U(x+dx), V(z+dz), 0.0074*sx, 0.0074*sz, GUN_DK)
    # stick well
    x, z = STICK
    cv.ellipse(U(x), V(z), 0.0145*sx, 0.0145*sz, GUN_HI)
    cv.ellipse(U(x), V(z), 0.0135*sx, 0.0135*sz, GUN_DK)
    # start / select legends
    for (x, z), lab in zip(STSE, ('SELECT', 'START')):
        cv.rect(U(x)-0.0062*sx, V(z)-0.0030*sz, U(x)+0.0062*sx, V(z)+0.0030*sz, GUN_DK, r=1.6)
        cv.text(U(x), V(z-0.0062), lab, DINC, 3.6, SILVER_HI, anchor='mm', spacing=0.25)
    # logo, centre top: 明 MEI with vent ribs either side
    lx, lz = 0.0, 0.0295
    for color, keep in ((SUN, 'left'), (MOON, 'right')):
        layer = Image.new('L', cv.im.size, 0)
        gs = 8.5
        gx, gy = U(lx)-11, V(lz)-gs/2-0.6
        ImageDraw.Draw(layer).text((gx*SS, gy*SS), '明', font=font(KAKU_B, gs*SS), fill=255)
        mask = Image.new('L', cv.im.size, 0)
        split = (gx + gs*0.43)*SS
        md = ImageDraw.Draw(mask)
        if keep == 'left':
            md.rectangle([0, 0, split, cv.im.size[1]], fill=255)
        else:
            md.rectangle([split, 0, cv.im.size[0], cv.im.size[1]], fill=255)
        from PIL import ImageChops
        layer = ImageChops.multiply(layer, mask)
        cv.im.paste(Image.new('RGB', cv.im.size, color), (0, 0), layer)
    cv.text(U(lx)+4.2, V(lz), 'MEI', DIN, 6.4, WHITE, anchor='mm', spacing=0.4)
    for side in (-1, 1):
        for i in range(6):
            x = side*(0.026 + i*0.0026)
            cv.line([(U(x)-0.6, V(lz+0.0035)), (U(x)+0.6, V(lz-0.0035))], SILVER_LO, 0.9)
    # L and R
    cv.text(U(-0.056), V(0.031), 'L', DIN, 5.5, GUN, anchor='mm')
    cv.text(U(0.056), V(0.031), 'R', DIN, 5.5, GUN, anchor='mm')
    out['k_face'] = cv.save('k_face.png')

    # d-pad top: arrows
    W = 28
    cv = Canvas(W, W, GUN)
    c = W/2
    for ang in range(4):
        a = ang*math.pi/2
        tip = (c + 11*math.sin(a), c - 11*math.cos(a))
        l = (c + 7.5*math.sin(a) - 2.4*math.cos(a), c - 7.5*math.cos(a) - 2.4*math.sin(a))
        r = (c + 7.5*math.sin(a) + 2.4*math.cos(a), c - 7.5*math.cos(a) + 2.4*math.sin(a))
        cv.poly([tip, l, r], GUN_HI)
    cv.ellipse(c, c, 3.4, 3.4, GUN_DK)
    cv.ellipse(c, c, 2.2, 2.2, GUN)
    out['k_dpad'] = cv.save('k_dpad.png')

    # button tops (disc projection): gunmetal caps with a bright letter
    for name, letter, col in (('k_a', 'A', SUN), ('k_b', 'B', MOON), ('k_x', 'X', WHITE), ('k_y', 'Y', SILVER)):
        W = 24
        cv = Canvas(W, W, GUN)
        c = W/2
        cv.ellipse(c, c, 11.8, 11.8, GUN_HI)
        cv.ellipse(c, c, 10.4, 10.4, GUN)
        cv.ellipse(c-2.5, c-2.5, 5, 4, (100, 106, 116))
        cv.text(c, c+0.6, letter, DIN, 13, col, anchor='mm')
        out[name] = cv.save(f'{name}.png')

    # stick cap: concave dish with a knurled rim
    W = 24
    cv = Canvas(W, W, GUN)
    c = W/2
    for i in range(24):
        a = i*math.pi/12
        cv.line([(c + 9.5*math.cos(a), c + 9.5*math.sin(a)), (c + 11.8*math.cos(a), c + 11.8*math.sin(a))], GUN_DK, 0.8)
    cv.ellipse(c, c, 8.8, 8.8, SILVER_LO)
    cv.ellipse(c, c, 7.6, 7.6, SILVER)
    cv.ellipse(c+1.2, c+1.2, 5.5, 5.5, SILVER_HI)
    cv.ellipse(c, c, 1.2, 1.2, SILVER_LO)
    out['k_stick'] = cv.save('k_stick.png')
    return out


def controller():
    art = paint_controller()
    mats = {
        'face': {'color': hx(SILVER), 'texture': tex_fit(art['k_face'])},
        'silver': {'color': hx(SILVER), 'texture': {'image': 'art/t_silver.png', 'projection': 'box', 'scale': [0.05, 0.05]}},
        'gun': {'color': hx(GUN), 'texture': {'image': 'art/t_gun.png', 'projection': 'box', 'scale': [0.05, 0.05]}},
        'grip': {'color': hx(GUN), 'texture': {'pattern': 'stripes', 'colors': [hx(GUN), '#43474f'], 'size': 16,
                                               'params': {'count': 4, 'axis': 'v'}, 'projection': 'box', 'scale': [0.008, 0.008]}},
        'gun_dk': {'color': hx(GUN_DK)},
        'dpad': {'color': hx(GUN), 'texture': tex_fit(art['k_dpad'])},
        'btn_a': {'color': hx(GUN), 'texture': {'image': art['k_a'], 'bits': 8, 'projection': 'disc'}},
        'btn_b': {'color': hx(GUN), 'texture': {'image': art['k_b'], 'bits': 8, 'projection': 'disc'}},
        'btn_x': {'color': hx(GUN), 'texture': {'image': art['k_x'], 'bits': 8, 'projection': 'disc'}},
        'btn_y': {'color': hx(GUN), 'texture': {'image': art['k_y'], 'bits': 8, 'projection': 'disc'}},
        'stick': {'color': hx(SILVER), 'texture': {'image': art['k_stick'], 'bits': 8, 'projection': 'disc'}},
    }
    nodes = []

    # shell: gunmetal lower half, silver upper half, the printed face on top
    m = Mesh()
    rings = [(0.000, inset(OUTLINE, 0.0055)), (0.0145, OUTLINE),
             (0.0225, inset(OUTLINE, 0.0016)), (TOPY, FACE_RING)]
    ring_loft(m, rings, lambda b, s: 'gun' if b < 1 else 'silver', top='face', bottom='gun_dk')
    nodes.append(m.node('shell'))

    # grips: ribbed gunmetal bulbs under the handles
    for side, name in ((-1, 'grip_l'), (1, 'grip_r')):
        nodes.append({'id': name, 'op': 'lathe', 'segments': 9, 'material': 'grip',
                      'profile': [[0.0, -0.030], [0.0110, -0.025], [0.0165, -0.011], [0.0170, 0.006],
                                  [0.0125, 0.022], [0.0, 0.030]],
                      'transform': {'scale': [1.0, 1.0, 0.85], 'rotate': [68, side*-10, 0],
                                    'translate': [side*0.050, 0.008, -0.036]}})

    # d-pad
    m = Mesh()
    a, l = 0.0047, 0.0138
    cross_pts = [(a, -l), (a, -a), (l, -a), (l, a), (a, a), (a, l), (-a, l), (-a, a), (-l, a), (-l, -a), (-a, -a), (-a, -l)]
    prism_y(m, cross_pts, -0.003, 0.0032, top='dpad', side='gun_dk')
    nodes.append(m.node('dpad', {'translate': [DPAD[0], TOPY, DPAD[1]]}))

    # A B X Y
    for (dx, dz), mat in (((ABXY_R, 0), 'btn_a'), ((0, -ABXY_R), 'btn_b'), ((0, ABXY_R), 'btn_x'), ((-ABXY_R, 0), 'btn_y')):
        m = Mesh()
        prism_y(m, circle(BTN_R, 10), -0.003, 0.0035, top=mat, side='gun')
        nodes.append(m.node(mat, {'translate': [ABXY[0]+dx, TOPY, ABXY[1]+dz]}))

    # the analog stick: a gunmetal boot, a shaft and a silver cap
    x, z = STICK
    nodes.append({'id': 'stick_boot', 'op': 'lathe', 'segments': 10, 'material': 'gun', 'caps': False,
                  'profile': [[0.0128, -0.002], [0.0118, 0.0025], [0.0068, 0.0058], [0.0, 0.0068]],
                  'transform': {'translate': [x, TOPY, z]}})
    nodes.append({'id': 'stick_shaft', 'op': 'cylinder', 'radius': 0.0034, 'height': 0.009, 'segments': 8,
                  'caps': False, 'material': 'gun_dk', 'transform': {'translate': [x, TOPY+0.0095, z]}})
    m = Mesh()
    prism_y(m, circle(0.0098, 14), -0.0028, 0.0028, top='stick', side='gun')
    nodes.append(m.node('stick_cap', {'translate': [x, TOPY+0.0150, z]}))

    # start and select: small pills
    for (x, z), name in zip(STSE, ('select', 'start')):
        m = Mesh()
        pts = []
        for i in range(8):
            t = 2*math.pi*(i+0.5)/8
            px = 0.0021*math.cos(t) + (0.0030 if math.cos(t) > 0 else -0.0030)
            pts.append((px, 0.0021*math.sin(t)))
        prism_y(m, pts, -0.002, 0.0022, top='gun', side='gun_dk')
        nodes.append(m.node(name, {'translate': [x, TOPY, z]}))

    # L and R on the shoulders
    for side, name in ((-1, 'l_button'), (1, 'r_button')):
        m = Mesh()
        edge = [(0.028, 0.0405), (0.052, 0.0405), (0.066, 0.0355), (0.0745, 0.024)]
        o = [(x+0.0, z+0.0045) for x, z in edge[:2]] + [(0.069, 0.0395), (0.0790, 0.0255)]
        i_ = [(0.0705, 0.0215), (0.063, 0.031), (0.051, 0.0355), (0.028, 0.0355)]
        pts = o + i_
        if side < 0:
            pts = [(-x, z) for x, z in pts]
        prism_y(m, pts, 0.0125, 0.0225, top='gun', side='silver')
        nodes.append(m.node(name))

    recipe = {
        'format': 'mei-asset', 'version': 1, 'name': 'akihabara_controller',
        'budget': {'vertices': 900, 'triangles': 800},
        'materials': mats,
        'lighting': LIGHT,
        'verification': VERIFY,
        # lifted so the grips, the lowest point, rest on y = 0
        'nodes': [{'id': 'controller', 'op': 'group', 'children': nodes,
                   'transform': {'translate': [0, 0.0099, 0]}}],
    }
    write('controller.asset.json', recipe)


if __name__ == '__main__':
    console()
    controller()
