"""Mech Expo 2000: the models' flat art, drawn in code (standard library only).

Shared by the mechs' generators (make_hero.py, ../doubleblade/make_doubleblade.py) and the
props'. Pictures are made of shapes in a unit frame (x right, y down, 0..1 across the picture),
rasterised with supersampling, and come out either as an Asset Kit texel grid (`texels` and
`colors`, at most 15 colours, exact) or as a PNG (RGBA, antialiased) for the menus.

  emblem_momentum(), emblem_umbral()   the companies' marks, as shape lists
  render(shapes, w, h, bg)             an RGBA picture, supersampled
  texels(shapes, w, h, bg)             a texel grid for a recipe (nearest colour, no blending)
  write_png(path, pixels, w, h)        a PNG, standard library only
  text_shapes(text, x, y, px, colour)  a 5 x 7 pixel font, for serial plates
  hazard(colors)                       an 8 x 8 diagonal stripe tile
"""
import math
import struct
import zlib


# ---- shapes ----------------------------------------------------------------------------------
# ('poly', colour, [(x, y), ...]), ('disc', colour, (cx, cy), r), ('ring', colour, (cx, cy), r0, r1)

def hexrgb(c):
    return tuple(int(c[i:i+2], 16) for i in (1, 3, 5))


def inside(shape, x, y):
    """Whether (x, y) is in the shape. Round shapes carry (sx, sy), their squeeze (scaled())."""
    kind = shape[0]
    if kind in ('disc', 'ring', 'crescent'):
        sx, sy = shape[-1] if isinstance(shape[-1], tuple) else (1.0, 1.0)
    if kind == 'disc':
        (cx, cy), r = shape[2], shape[3]
        return ((x-cx)/sx)**2+((y-cy)/sy)**2 <= r*r
    if kind == 'ring':
        (cx, cy), r0, r1 = shape[2], shape[3], shape[4]
        d = ((x-cx)/sx)**2+((y-cy)/sy)**2
        return r0*r0 <= d <= r1*r1
    if kind == 'crescent':      # a disc minus another disc
        (cx, cy), r, (ox, oy), orad = shape[2], shape[3], shape[4], shape[5]
        return (((x-cx)/sx)**2+((y-cy)/sy)**2 <= r*r
                and ((x-ox)/sx)**2+((y-oy)/sy)**2 > orad*orad)
    pts = shape[2]
    c = False
    for i, (ax, ay) in enumerate(pts):
        bx, by = pts[i-1]
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            c = not c
    return c


def colour_at(shapes, x, y, bg):
    col = bg
    for s in shapes:
        if inside(s, x, y):
            col = s[1]
    return col


def render(shapes, w, h, bg=None, ss=4):
    """RGBA rows; bg None is transparent."""
    rows = []
    for j in range(h):
        row = []
        for i in range(w):
            acc = [0, 0, 0, 0]
            for sj in range(ss):
                for si in range(ss):
                    c = colour_at(shapes, (i+(si+0.5)/ss)/w, (j+(sj+0.5)/ss)/h, bg)
                    if c is not None:
                        r, g, b = hexrgb(c)
                        acc[0] += r
                        acc[1] += g
                        acc[2] += b
                        acc[3] += 1
            n = ss*ss
            a = acc[3]
            row.append((acc[0]//a, acc[1]//a, acc[2]//a, 255*a//n) if a else (0, 0, 0, 0))
        rows.append(row)
    return rows


def texels(shapes, w, h, bg, ss=3):
    """{'texels': [...], 'colors': [...]}: each texel the colour covering most of it."""
    colours = [bg]
    rows = []
    for j in range(h):
        line = ''
        for i in range(w):
            votes = {}
            for sj in range(ss):
                for si in range(ss):
                    c = colour_at(shapes, (i+(si+0.5)/ss)/w, (j+(sj+0.5)/ss)/h, bg)
                    votes[c] = votes.get(c, 0)+1
            c = max(sorted(votes), key=lambda k: votes[k])
            if c not in colours:
                colours.append(c)
            line += '%x' % colours.index(c)
        rows.append(line)
    assert len(colours) <= 16, colours
    return {'texels': rows, 'colors': colours}


def write_png(path, rows):
    h, w = len(rows), len(rows[0])
    raw = b''.join(b'\0'+bytes(v for px in row for v in px) for row in rows)

    def chunk(tag, data):
        return struct.pack('>I', len(data))+tag+data+struct.pack('>I', zlib.crc32(tag+data))
    png = (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(raw, 9))+chunk(b'IEND', b''))
    path.write_bytes(png)


def scaled(shapes, sx, sy, ox=0.0, oy=0.0):
    """The shapes squeezed into the box (ox, oy) to (ox + sx, oy + sy)."""
    def p(q):
        return (ox+q[0]*sx, oy+q[1]*sy)
    out = []
    for s in shapes:
        if s[0] == 'poly':
            out.append(('poly', s[1], [p(q) for q in s[2]]))
        elif s[0] == 'disc':
            out.append(('disc', s[1], p(s[2]), s[3], (sx, sy)))
        elif s[0] == 'ring':
            out.append(('ring', s[1], p(s[2]), s[3], s[4], (sx, sy)))
        else:
            out.append(('crescent', s[1], p(s[2]), s[3], p(s[4]), s[5], (sx, sy)))
    return out


# ---- the companies' marks --------------------------------------------------------------------

MOMENTUM_RED, MOMENTUM_WHITE, MOMENTUM_DARK = '#e8262c', '#f6f6f2', '#262a33'


def emblem_momentum(red=MOMENTUM_RED, white=MOMENTUM_WHITE):
    """Momentum Robotics: a red roundel, a white rim, and a white italic M whose right leg runs
    on into an arrow pointing forward, with two speed lines trailing behind it."""
    s = [('disc', white, (0.5, 0.5), 0.5), ('disc', red, (0.5, 0.5), 0.43)]
    k = 0.2                                   # italic slant: x shifts by k per unit of y up

    def sl(pts):
        return [(x+k*(0.5-y), y) for x, y in pts]

    def stroke(a, b, w):
        dx, dy = b[0]-a[0], b[1]-a[1]
        n = math.hypot(dx, dy)
        px, py = -dy/n*w/2, dx/n*w/2
        return [(a[0]+px, a[1]+py), (b[0]+px, b[1]+py), (b[0]-px, b[1]-py), (a[0]-px, a[1]-py)]
    # the M: two posts and a V
    for pts in ([(0.20, 0.70), (0.20, 0.30), (0.30, 0.30), (0.30, 0.70)],
                [(0.52, 0.70), (0.52, 0.30), (0.62, 0.30), (0.62, 0.70)],
                stroke((0.25, 0.32), (0.41, 0.58), 0.1), stroke((0.41, 0.58), (0.57, 0.32), 0.1),
                # the arrow out of the right post, pointing forward
                [(0.61, 0.43), (0.69, 0.43), (0.69, 0.33), (0.83, 0.48), (0.69, 0.63), (0.69, 0.53),
                 (0.61, 0.53)],
                # speed lines trailing the left post
                [(0.08, 0.42), (0.17, 0.42), (0.17, 0.48), (0.10, 0.48)],
                [(0.07, 0.54), (0.17, 0.54), (0.17, 0.60), (0.09, 0.60)]):
        s.append(('poly', white, sl(pts)))
    return s


UMBRAL_BLACK, UMBRAL_VIOLET, UMBRAL_GLOW = '#1f1d27', '#8f46ee', '#e2b8ff'


def emblem_umbral(black=UMBRAL_BLACK, violet=UMBRAL_VIOLET, glow=UMBRAL_GLOW):
    """Umbral Research: an eclipse. A black disc, a violet corona ring, a violet crescent
    swallowed by the shadow, and one bright point where the light escapes."""
    return [('disc', violet, (0.5, 0.5), 0.5), ('disc', black, (0.5, 0.5), 0.44),
            ('ring', violet, (0.5, 0.5), 0.33, 0.37),
            ('crescent', violet, (0.5, 0.5), 0.28, (0.6, 0.44), 0.26),
            ('disc', glow, (0.27, 0.66), 0.055)]


# ---- a 5 x 7 pixel font, for serial numbers (only the glyphs the plates use) -----------------

FONT = {
    'M': ['10001', '11011', '10101', '10101', '10001', '10001', '10001'],
    'R': ['11110', '10001', '10001', '11110', '10100', '10010', '10001'],
    'U': ['10001', '10001', '10001', '10001', '10001', '10001', '01110'],
    'X': ['10001', '10001', '01010', '00100', '01010', '10001', '10001'],
    'B': ['11110', '10001', '10001', '11110', '10001', '10001', '11110'],
    'E': ['11111', '10000', '10000', '11110', '10000', '10000', '11111'],
    '-': ['00000', '00000', '00000', '11111', '00000', '00000', '00000'],
    '0': ['01110', '10001', '10011', '10101', '11001', '10001', '01110'],
    '1': ['00100', '01100', '00100', '00100', '00100', '00100', '01110'],
    '2': ['01110', '10001', '00001', '00010', '00100', '01000', '11111'],
    '7': ['11111', '00001', '00010', '00100', '01000', '01000', '01000'],
    ' ': ['00000']*7,
}


def text_shapes(text, x, y, w, h, colour):
    """Squares for each lit pixel of `text`, its top-left at (x, y), each glyph pixel w x h (in
    the picture's unit frame), glyphs 6 pixels apart."""
    out = []
    for n, ch in enumerate(text):
        for j, row in enumerate(FONT[ch]):
            for i, bit in enumerate(row):
                if bit == '1':
                    px, py = x+(n*6+i)*w, y+j*h
                    out.append(('poly', colour, [(px, py), (px+w, py), (px+w, py+h), (px, py+h)]))
    return out


def serial_plate(text, field, ink, w=32, h=16):
    """A texel grid: `text` in the 5 x 7 font on `field`, a rule and a bar code under it."""
    tw = len(text)*6-1
    x0 = (w-tw)//2
    shapes = text_shapes(text, x0/w, 2/h, 1/w, 1/h, ink)
    shapes.append(('poly', ink, [(2/w, 11/h), ((w-2)/w, 11/h), ((w-2)/w, 12/h), (2/w, 12/h)]))
    for i in range(2, w-2):
        if (i*7+3) % 5 < 2:
            shapes.append(('poly', ink, [(i/w, 13/h), ((i+1)/w, 13/h), ((i+1)/w, 15/h),
                                         (i/w, 15/h)]))
    return texels(shapes, w, h, field, ss=1)


def hazard(colors, size=8):
    """A size x size tile of diagonal stripes, half each colour, repeating seamlessly."""
    return {'texels': [''.join('%x' % (((i+j)//(size//2)) % 2) for i in range(size))
                       for j in range(size)], 'colors': list(colors)}
