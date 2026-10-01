#!/usr/bin/env python3
"""Generates the main agent's assets of the "Check-In!" cart (carts/checkin/):

  gen/ui.bin       4-bit texture slot 11: the two fonts and the title logo
  gen/hud.bin      4-bit texture slot 12: HUD icons (stars, coins, clock, needs, speed...)
  gen/pal.bin      15-bit palettes from PAL_BASE (fonts, logo, icons)
  gen/strings.bin  every text the game shows by index (names, reviews), NUL-separated
  gen/save_icon.bin  the memory card save's title + animated 16x16 hotel icon
  gen.akr          generated declarations: embeds, font metrics, icon cells, and the data
                   tables of the object catalogue, room types, guest types and staff roles

The catalogue is defined here (one source of truth); the object meshes, surfaces and people
sprites come from the art agent's tools/gen_checkin_art.py (carts/checkin/CONTRACT.md).

    python3 tools/gen_checkin_assets.py [--review DIR]
"""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mei_icon import make_meta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'carts', 'checkin')
GEN = os.path.join(OUT, 'gen')
os.makedirs(GEN, exist_ok=True)
REVIEW = sys.argv[sys.argv.index('--review') + 1] if '--review' in sys.argv else None

SLOT_UI = 11
SLOT_HUD = 12
PAL_BASE = 160          # main's palettes: 160..254 (CONTRACT.md)


def write(name, data):
    with open(os.path.join(GEN, name), 'wb') as f:
        f.write(data)


def c15(c):
    r, g, b = (int(max(0, min(255, round(v)))) for v in c[:3])
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)


class Atlas:
    def __init__(self):
        self.idx = np.zeros((256, 256), np.uint8)

    def put(self, u, v, img):
        h, w = img.shape
        self.idx[v:v + h, u:u + w] = img

    def pack(self):
        a = self.idx
        return (a[:, 0::2] | (a[:, 1::2] << 4)).astype(np.uint8).tobytes()


A_UI = Atlas()
A_HUD = Atlas()
PALS = []        # list of 16-colour palettes (index 0 unused/transparent)


def pal(cols):
    cols = list(cols)[:15]
    while len(cols) < 15:
        cols.append(cols[-1])
    PALS.append([(0, 0, 0)] + cols)
    return PAL_BASE + len(PALS) - 1


# ----------------------------------------------------------------------------- fonts
FONT_SMALL = '/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf'
FONT_BIG = '/System/Library/Fonts/Supplemental/Arial Black.ttf'
SHADOW = (18, 16, 40)
FONT_PAL = pal([SHADOW] + [tuple(int(SHADOW[k] + (255 - SHADOW[k]) * (i / 13.0) ** 0.85) for k in range(3))
                           for i in range(14)])


class Shelf:
    def __init__(self, atlas, x0, y0, x1, y1):
        self.a, self.x0, self.y0, self.x1, self.y1 = atlas, x0, y0, x1, y1
        self.x, self.y, self.rowh = x0, y0, 0

    def put(self, img):
        h, w = img.shape
        if self.x + w > self.x1:
            self.x = self.x0
            self.y += self.rowh + 1
            self.rowh = 0
        assert self.y + h <= self.y1, 'atlas full'
        self.a.put(self.x, self.y, img)
        u, v = self.x, self.y
        self.x += w + 1
        self.rowh = max(self.rowh, h)
        return u, v


def render_font(shelf, path, size, track=0, firm=True):
    font = ImageFont.truetype(path, size)
    big = ImageFont.truetype(path, size * 4)
    asc, desc = font.getmetrics()
    H = asc + desc + 2
    metrics = []
    for code in range(32, 127):
        ch = chr(code)
        adv = font.getlength(ch)
        cw = int(math.ceil(adv)) + 4
        S = 4
        img = Image.new('L', (cw * S, H * S), 0)
        d = ImageDraw.Draw(img)
        d.text((1 * S, 0), ch, font=big, fill=255)
        a = np.asarray(img.resize((cw, H), Image.BOX), np.float32) / 255.0
        if firm:
            a = np.clip((a - 0.1) / 0.75, 0, 1)
        sh = np.zeros_like(a)
        sh[1:, 1:] = a[:-1, :-1]
        idx = np.zeros(a.shape, np.uint8)
        vis = (a > 0.18) | (sh > 0.4)
        lvl = np.clip(np.round(a * 13), 0, 13).astype(np.uint8) + 2
        idx[vis] = np.where(a[vis] > 0.18, lvl[vis], 1)
        cols = np.where(idx.any(axis=0))[0]
        if len(cols) == 0:
            metrics.append((0, 0, 0, int(round(adv)) + track))
            continue
        w = int(cols.max()) + 1
        idx = idx[:, :w]
        u, v = shelf.put(idx)
        metrics.append((u, v, w, int(round(adv)) + track))
    return metrics, H


shelf = Shelf(A_UI, 0, 0, 255, 180)
FS_METRICS, FS_H = render_font(shelf, FONT_SMALL, 9, track=0)
shelf.x = 0; shelf.y += shelf.rowh + 2; shelf.rowh = 0
FB_METRICS, FB_H = render_font(shelf, FONT_BIG, 13, track=0)
FONT_END = shelf.y + shelf.rowh
print('fonts: small h=%d big h=%d, rows used to %d' % (FS_H, FB_H, FONT_END))

# ----------------------------------------------------------------------------- logo (slot 11, bottom)
LW, LH = 256, 64
LOGO_V = 256 - LH
assert FONT_END < LOGO_V, 'fonts overlap the logo'


def make_logo():
    S = 4
    font = ImageFont.truetype(FONT_BIG, 40 * S)
    txt = 'Check-In!'
    bb = font.getbbox(txt)
    tw = bb[2] - bb[0]
    ox = (LW * S - tw) // 2 - bb[0]
    oy = 2 * S - bb[1]
    mask = Image.new('L', (LW * S, LH * S), 0)
    ImageDraw.Draw(mask).text((ox, oy), txt, font=font, fill=255)
    outline = mask.filter(ImageFilter.MaxFilter(int(2.5 * S) * 2 + 1))
    m = np.asarray(mask, np.float32)[..., None] / 255
    o = np.asarray(outline, np.float32)[..., None] / 255
    H, W = LH * S, LW * S
    yy = (np.arange(H)[:, None, None] - (oy + bb[1])) / max(1, bb[3] - bb[1])
    xx = np.arange(W)[None, :, None] / W
    # Y2K: aqua -> magenta sweep with a glossy highlight band on top
    c0 = np.array([90, 230, 255], np.float32)
    c1 = np.array([255, 110, 210], np.float32)
    grad = c0 + (c1 - c0) * np.clip(xx * 1.1 - 0.05, 0, 1)
    gloss = np.clip(1.0 - np.abs(yy - 0.28) * 5.0, 0, 1) * 0.55
    grad = grad + (255 - grad) * gloss
    shade = np.clip((yy - 0.55) * 1.4, 0, 0.45)
    grad = grad * (1 - shade)
    outc = np.array([30, 24, 80], np.float32)
    col = np.where(m > 0.5, grad, np.where(o > 0.5, outc, 0))
    alpha = np.maximum(o, m)
    # subtitle
    sf = ImageFont.truetype(FONT_SMALL, 10 * S)
    sub = 'a seaside hotel  ~  est. 2001'
    jm = Image.new('L', (W, H), 0)
    sb = sf.getbbox(sub)
    ImageDraw.Draw(jm).text(((W - (sb[2] - sb[0])) // 2 - sb[0], 49 * S), sub, font=sf, fill=255)
    jo = jm.filter(ImageFilter.MaxFilter(int(1.2 * S) * 2 + 1))
    jmn = np.asarray(jm, np.float32)[..., None] / 255
    jon = np.asarray(jo, np.float32)[..., None] / 255
    col = np.where(jmn > 0.5, np.array([255, 240, 200], np.float32), np.where(jon > 0.5, outc, col))
    alpha = np.maximum(alpha, jon)
    rgba = np.concatenate([np.broadcast_to(col, (H, W, 3)), alpha * 255], axis=2).astype(np.uint8)
    small = Image.fromarray(rgba, 'RGBA').resize((LW, LH), Image.LANCZOS)
    la = np.asarray(small, np.float32)
    op = la[..., 3] > 110
    pix = la[..., :3][op].astype(np.uint8)
    q = Image.fromarray(pix.reshape(1, -1, 3), 'RGB').quantize(colors=15, method=Image.Quantize.MEDIANCUT,
                                                                 dither=Image.Dither.NONE)
    qp = q.getpalette()[:45]
    cols = [tuple(qp[i * 3:i * 3 + 3]) for i in range(15)]
    lab = np.asarray(q).reshape(-1)
    idx = np.zeros((LH, LW), np.uint8)
    idx[op] = lab + 1
    A_UI.put(0, LOGO_V, idx)
    return pal(cols)


LOGO_PAL = make_logo()

# ----------------------------------------------------------------------------- HUD icons (slot 12)
ICONS = []          # (name, u, v, pal)


def icon(name, fn, cols):
    S = 8
    im = Image.new('RGBA', (16 * S, 16 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fn(d, S)
    sm = im.resize((16, 16), Image.LANCZOS)
    a = np.asarray(sm, np.float32) / 255
    rgb = a[..., :3] * 255
    idx = np.zeros((16, 16), np.uint8)
    pl = np.array(cols, np.float32)
    for y in range(16):
        for x in range(16):
            if a[y, x, 3] > 0.45:
                dd = ((pl - rgb[y, x] / max(a[y, x, 3], 0.01)) ** 2).sum(axis=1)
                idx[y, x] = 1 + int(dd.argmin())
    n = len(ICONS)
    u, v = (n % 16) * 16, (n // 16) * 16
    A_HUD.put(u, v, idx)
    ICONS.append((name, u, v, pal(cols)))


def star_pts(cx, cy, r0, r1, n=5, rot=-math.pi / 2):
    pts = []
    for k in range(2 * n):
        r = r0 if k % 2 == 0 else r1
        a = rot + k * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


GOLDS = [(255, 236, 140), (255, 200, 60), (220, 140, 30), (130, 70, 20), (255, 255, 230)]
GREYS = [(90, 96, 120), (60, 64, 90), (130, 136, 160), (40, 40, 60), (170, 176, 200)]


def ic_star(d, S):
    d.polygon(star_pts(8 * S, 8.6 * S, 7.4 * S, 3.0 * S), fill=(220, 140, 30, 255))
    d.polygon(star_pts(8 * S, 8.2 * S, 6.4 * S, 2.6 * S), fill=(255, 200, 60, 255))
    d.polygon(star_pts(7.4 * S, 7.4 * S, 3.0 * S, 1.3 * S), fill=(255, 236, 140, 255))


def ic_star_off(d, S):
    d.polygon(star_pts(8 * S, 8.6 * S, 7.4 * S, 3.0 * S), fill=(40, 40, 60, 255))
    d.polygon(star_pts(8 * S, 8.2 * S, 6.4 * S, 2.6 * S), fill=(90, 96, 120, 255))


def ic_coin(d, S):
    d.ellipse((1.5 * S, 1.5 * S, 14.5 * S, 14.5 * S), fill=(130, 70, 20, 255))
    d.ellipse((1.5 * S, 1 * S, 14.5 * S, 13.5 * S), fill=(255, 200, 60, 255))
    d.ellipse((3.5 * S, 3 * S, 12.5 * S, 11.5 * S), outline=(220, 140, 30, 255), width=S)
    f = ImageFont.truetype(FONT_BIG, 9 * S)
    d.text((8 * S, 7.4 * S), '$', font=f, fill=(130, 70, 20, 255), anchor='mm')


def ic_sun(d, S):
    for k in range(8):
        a = k * math.pi / 4
        d.line([(8 * S + 4.5 * S * math.cos(a), 8 * S + 4.5 * S * math.sin(a)),
                (8 * S + 7 * S * math.cos(a), 8 * S + 7 * S * math.sin(a))], fill=(255, 170, 40, 255), width=int(1.6 * S))
    d.ellipse((4 * S, 4 * S, 12 * S, 12 * S), fill=(255, 220, 80, 255), outline=(230, 120, 30, 255), width=S)


def ic_moon(d, S):
    d.ellipse((2 * S, 2 * S, 14 * S, 14 * S), fill=(250, 240, 190, 255))
    d.ellipse((5.5 * S, 0.5 * S, 16.5 * S, 11.5 * S), fill=(0, 0, 0, 0))


def ic_person(d, S):
    d.ellipse((5 * S, 1 * S, 11 * S, 7 * S), fill=(250, 210, 170, 255), outline=(60, 40, 40, 255), width=S // 2)
    d.rounded_rectangle((3 * S, 7.5 * S, 13 * S, 15 * S), radius=3 * S, fill=(80, 150, 230, 255), outline=(30, 50, 100, 255), width=S // 2)


def ic_staff(d, S):
    d.ellipse((5 * S, 1 * S, 11 * S, 7 * S), fill=(250, 210, 170, 255), outline=(60, 40, 40, 255), width=S // 2)
    d.rectangle((4 * S, 0.5 * S, 12 * S, 3 * S), fill=(200, 40, 60, 255))
    d.rounded_rectangle((3 * S, 7.5 * S, 13 * S, 15 * S), radius=3 * S, fill=(200, 40, 60, 255), outline=(90, 20, 30, 255), width=S // 2)
    d.rectangle((7 * S, 8 * S, 9 * S, 14 * S), fill=(255, 220, 90, 255))


def ic_wrench(d, S):
    d.line([(4 * S, 12 * S), (11 * S, 5 * S)], fill=(150, 160, 180, 255), width=int(2.6 * S))
    d.ellipse((9 * S, 1.5 * S, 15 * S, 7.5 * S), fill=(150, 160, 180, 255))
    d.ellipse((11 * S, 1 * S, 14 * S, 4.5 * S), fill=(0, 0, 0, 0))
    d.ellipse((2 * S, 10 * S, 6 * S, 14 * S), fill=(150, 160, 180, 255))


def ic_clock(d, S):
    d.ellipse((1.5 * S, 1.5 * S, 14.5 * S, 14.5 * S), fill=(240, 244, 255, 255), outline=(40, 60, 120, 255), width=S)
    d.line([(8 * S, 8 * S), (8 * S, 3.5 * S)], fill=(40, 60, 120, 255), width=S)
    d.line([(8 * S, 8 * S), (11.5 * S, 9.5 * S)], fill=(40, 60, 120, 255), width=S)


def ic_check(d, S):
    d.line([(3 * S, 8 * S), (6.5 * S, 12 * S), (13 * S, 3.5 * S)], fill=(90, 220, 110, 255), width=int(2.4 * S))


def ic_cross(d, S):
    d.line([(4 * S, 4 * S), (12 * S, 12 * S)], fill=(255, 90, 90, 255), width=int(2.4 * S))
    d.line([(12 * S, 4 * S), (4 * S, 12 * S)], fill=(255, 90, 90, 255), width=int(2.4 * S))


def ic_plus(d, S):
    d.ellipse((2 * S, 2 * S, 14 * S, 14 * S), fill=(255, 200, 60, 255))
    d.line([(8 * S, 4.5 * S), (8 * S, 11.5 * S)], fill=(255, 255, 230, 255), width=int(2 * S))
    d.line([(4.5 * S, 8 * S), (11.5 * S, 8 * S)], fill=(255, 255, 230, 255), width=int(2 * S))


def ic_warn(d, S):
    d.polygon([(8 * S, 1 * S), (15 * S, 14.5 * S), (1 * S, 14.5 * S)], fill=(255, 200, 60, 255), outline=(130, 70, 20, 255))
    d.line([(8 * S, 5.5 * S), (8 * S, 10 * S)], fill=(60, 30, 10, 255), width=int(1.8 * S))
    d.ellipse((7 * S, 11.3 * S, 9 * S, 13.3 * S), fill=(60, 30, 10, 255))


def ic_pause(d, S):
    d.rectangle((3.5 * S, 3 * S, 6.5 * S, 13 * S), fill=(240, 244, 255, 255))
    d.rectangle((9.5 * S, 3 * S, 12.5 * S, 13 * S), fill=(240, 244, 255, 255))


def ic_play(d, S):
    d.polygon([(4 * S, 2.5 * S), (13 * S, 8 * S), (4 * S, 13.5 * S)], fill=(240, 244, 255, 255))


def ic_ff(d, S):
    d.polygon([(1.5 * S, 3 * S), (8 * S, 8 * S), (1.5 * S, 13 * S)], fill=(240, 244, 255, 255))
    d.polygon([(8 * S, 3 * S), (14.5 * S, 8 * S), (8 * S, 13 * S)], fill=(240, 244, 255, 255))


def ic_heart(d, S):
    d.ellipse((1.5 * S, 2.5 * S, 8.5 * S, 9.5 * S), fill=(255, 90, 140, 255))
    d.ellipse((7.5 * S, 2.5 * S, 14.5 * S, 9.5 * S), fill=(255, 90, 140, 255))
    d.polygon([(2 * S, 7.5 * S), (14 * S, 7.5 * S), (8 * S, 14.5 * S)], fill=(255, 90, 140, 255))
    d.ellipse((4 * S, 4 * S, 6.5 * S, 6.5 * S), fill=(255, 210, 230, 255))


def ic_bed(d, S):
    d.rectangle((1 * S, 6 * S, 15 * S, 12 * S), fill=(120, 160, 230, 255))
    d.rectangle((1 * S, 4 * S, 3 * S, 14 * S), fill=(150, 90, 50, 255))
    d.rounded_rectangle((3.5 * S, 4.5 * S, 7.5 * S, 7.5 * S), radius=S, fill=(250, 250, 255, 255))
    d.rectangle((1 * S, 12 * S, 15 * S, 13.5 * S), fill=(150, 90, 50, 255))


def ic_food(d, S):
    d.ellipse((1.5 * S, 6 * S, 14.5 * S, 14.5 * S), fill=(240, 244, 255, 255))
    d.ellipse((4 * S, 7.5 * S, 12 * S, 12.5 * S), fill=(255, 170, 70, 255))
    d.line([(3 * S, 1 * S), (3 * S, 6 * S)], fill=(180, 186, 210, 255), width=S)
    d.line([(13 * S, 1 * S), (13 * S, 6 * S)], fill=(180, 186, 210, 255), width=S)


def ic_soap(d, S):
    for (x, y, r) in ((5, 6, 3.5), (10.5, 5, 2.5), (10, 11, 3.5), (4, 12, 2)):
        d.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), outline=(120, 220, 255, 255), width=S, fill=(200, 240, 255, 120))


def ic_fun(d, S):
    d.line([(6 * S, 3 * S), (6 * S, 12 * S)], fill=(255, 90, 140, 255), width=int(1.6 * S))
    d.line([(6 * S, 3 * S), (13 * S, 1.5 * S), (13 * S, 10.5 * S)], fill=(255, 90, 140, 255), width=int(1.6 * S))
    d.ellipse((2 * S, 10 * S, 7 * S, 14.5 * S), fill=(255, 90, 140, 255))
    d.ellipse((9 * S, 8.5 * S, 14 * S, 13 * S), fill=(255, 90, 140, 255))


def ic_zzz(d, S):
    f = ImageFont.truetype(FONT_BIG, 8 * S)
    d.text((5 * S, 10 * S), 'Z', font=f, fill=(170, 190, 255, 255), anchor='mm')
    f2 = ImageFont.truetype(FONT_BIG, 6 * S)
    d.text((11 * S, 5 * S), 'z', font=f2, fill=(170, 190, 255, 255), anchor='mm')


def ic_noise(d, S):
    d.polygon([(2 * S, 6 * S), (5 * S, 6 * S), (9 * S, 2.5 * S), (9 * S, 13.5 * S), (5 * S, 10 * S), (2 * S, 10 * S)], fill=(240, 244, 255, 255))
    d.arc((7 * S, 4 * S, 13 * S, 12 * S), -60, 60, fill=(255, 200, 60, 255), width=S)
    d.arc((7 * S, 1.5 * S, 16 * S, 14.5 * S), -60, 60, fill=(255, 200, 60, 255), width=S)


def ic_bell(d, S):
    d.pieslice((2 * S, 4 * S, 14 * S, 18 * S), 180, 360, fill=(255, 200, 60, 255), outline=(130, 70, 20, 255))
    d.rectangle((1 * S, 11 * S, 15 * S, 13 * S), fill=(130, 70, 20, 255))
    d.ellipse((6.5 * S, 2 * S, 9.5 * S, 5 * S), fill=(255, 236, 140, 255))


def ic_broom(d, S):
    d.line([(12 * S, 1 * S), (6 * S, 9 * S)], fill=(150, 90, 50, 255), width=int(1.6 * S))
    d.polygon([(4 * S, 7.5 * S), (9 * S, 11 * S), (6 * S, 15 * S), (1 * S, 12 * S)], fill=(255, 200, 60, 255))


def ic_up(d, S):
    d.polygon([(8 * S, 2 * S), (14 * S, 9 * S), (2 * S, 9 * S)], fill=(240, 244, 255, 255))
    d.rectangle((5.5 * S, 9 * S, 10.5 * S, 14 * S), fill=(240, 244, 255, 255))


def ic_down(d, S):
    d.polygon([(8 * S, 14 * S), (14 * S, 7 * S), (2 * S, 7 * S)], fill=(240, 244, 255, 255))
    d.rectangle((5.5 * S, 2 * S, 10.5 * S, 7 * S), fill=(240, 244, 255, 255))


def ic_hammer(d, S):
    d.line([(4 * S, 14 * S), (10 * S, 6 * S)], fill=(150, 90, 50, 255), width=int(2 * S))
    d.polygon([(6 * S, 2.5 * S), (12 * S, 1 * S), (15 * S, 5 * S), (9.5 * S, 8 * S)], fill=(150, 160, 180, 255))


def ic_eye(d, S):
    d.ellipse((1 * S, 4 * S, 15 * S, 12 * S), fill=(240, 244, 255, 255))
    d.ellipse((5 * S, 4.5 * S, 11 * S, 11.5 * S), fill=(60, 120, 220, 255))
    d.ellipse((7 * S, 6.5 * S, 9 * S, 8.5 * S), fill=(10, 10, 30, 255))


def ic_trash(d, S):
    d.rectangle((3 * S, 4 * S, 13 * S, 5.5 * S), fill=(240, 244, 255, 255))
    d.rectangle((6 * S, 2 * S, 10 * S, 4 * S), fill=(240, 244, 255, 255))
    d.polygon([(4 * S, 6 * S), (12 * S, 6 * S), (11 * S, 15 * S), (5 * S, 15 * S)], fill=(200, 210, 230, 255))


def ic_layers(d, S):
    for k, c in enumerate([(120, 160, 230), (160, 200, 255), (220, 236, 255)]):
        y = 10 - k * 3
        d.polygon([(8 * S, (y - 3) * S), (15 * S, y * S), (8 * S, (y + 3) * S), (1 * S, y * S)], fill=c + (255,), outline=(40, 60, 120, 255))


def ic_wifi(d, S):
    for k, r in enumerate((6.5, 4.5, 2.5)):
        d.arc(((8 - r) * S, (11 - r) * S, (8 + r) * S, (11 + r) * S), 220, 320, fill=(120, 220, 255, 255), width=S)
    d.ellipse((7 * S, 10.5 * S, 9 * S, 12.5 * S), fill=(120, 220, 255, 255))


ICON_DEFS = [
    ('STAR', ic_star, GOLDS), ('STAR_OFF', ic_star_off, GREYS), ('COIN', ic_coin, GOLDS),
    ('SUN', ic_sun, [(255, 220, 80), (255, 170, 40), (230, 120, 30), (255, 250, 200)]),
    ('MOON', ic_moon, [(250, 240, 190), (200, 190, 140)]),
    ('GUEST', ic_person, [(250, 210, 170), (80, 150, 230), (30, 50, 100), (60, 40, 40)]),
    ('STAFF', ic_staff, [(250, 210, 170), (200, 40, 60), (90, 20, 30), (255, 220, 90), (60, 40, 40)]),
    ('WRENCH', ic_wrench, [(150, 160, 180), (90, 96, 120), (220, 226, 240)]),
    ('CLOCK', ic_clock, [(240, 244, 255), (40, 60, 120), (150, 160, 200)]),
    ('CHECK', ic_check, [(90, 220, 110), (40, 120, 60)]),
    ('CROSS', ic_cross, [(255, 90, 90), (140, 40, 40)]),
    ('PLUS', ic_plus, [(255, 200, 60), (255, 255, 230), (220, 140, 30)]),
    ('WARN', ic_warn, [(255, 200, 60), (130, 70, 20), (60, 30, 10)]),
    ('PAUSE', ic_pause, [(240, 244, 255), (160, 170, 200)]),
    ('PLAY', ic_play, [(240, 244, 255), (160, 170, 200)]),
    ('FF', ic_ff, [(240, 244, 255), (160, 170, 200)]),
    ('HEART', ic_heart, [(255, 90, 140), (255, 210, 230), (160, 40, 80)]),
    ('BED', ic_bed, [(120, 160, 230), (150, 90, 50), (250, 250, 255), (80, 110, 180)]),
    ('FOOD', ic_food, [(240, 244, 255), (255, 170, 70), (180, 186, 210), (200, 100, 40)]),
    ('SOAP', ic_soap, [(120, 220, 255), (200, 240, 255), (60, 140, 200)]),
    ('FUN', ic_fun, [(255, 90, 140), (160, 40, 80)]),
    ('ZZZ', ic_zzz, [(170, 190, 255), (90, 110, 200)]),
    ('NOISE', ic_noise, [(240, 244, 255), (255, 200, 60), (130, 70, 20)]),
    ('BELL', ic_bell, GOLDS),
    ('BROOM', ic_broom, [(150, 90, 50), (255, 200, 60), (180, 120, 30)]),
    ('UP', ic_up, [(240, 244, 255), (160, 170, 200)]),
    ('DOWN', ic_down, [(240, 244, 255), (160, 170, 200)]),
    ('HAMMER', ic_hammer, [(150, 90, 50), (150, 160, 180), (90, 96, 120)]),
    ('EYE', ic_eye, [(240, 244, 255), (60, 120, 220), (10, 10, 30)]),
    ('TRASH', ic_trash, [(240, 244, 255), (200, 210, 230), (120, 130, 150)]),
    ('LAYERS', ic_layers, [(120, 160, 230), (160, 200, 255), (220, 236, 255), (40, 60, 120)]),
    ('WIFI', ic_wifi, [(120, 220, 255), (60, 140, 200)]),
]
for name, fn, cols in ICON_DEFS:
    icon(name, fn, cols)

# a soft round glow (additive lamp halos at night) 32x32 at (0, 64), and a dot 16x16 at (32, 64)
GLOW_PAL = pal([(int(255 * (i / 14.0)),) * 3 for i in range(1, 16)])
yy, xx = np.mgrid[0:32, 0:32]
r = np.sqrt((xx - 15.5) ** 2 + (yy - 15.5) ** 2) / 16
g = np.clip(1 - r, 0, 1) ** 1.8
A_HUD.put(0, 64, np.where(g > 0.02, np.clip(np.round(g * 15), 1, 15), 0).astype(np.uint8))
yy, xx = np.mgrid[0:16, 0:16]
r = np.sqrt((xx - 7.5) ** 2 + (yy - 7.5) ** 2) / 8
g = np.clip(1 - r, 0, 1) ** 1.2
A_HUD.put(32, 64, np.where(g > 0.02, np.clip(np.round(g * 15), 1, 15), 0).astype(np.uint8))
# a solid white 8x8 block for flat textured quads (any palette colour 15) at (48, 64)
A_HUD.put(48, 64, np.full((8, 8), 15, np.uint8))
# a cursor tile frame: 32x16 diamond outline at (64, 64)
cur = np.zeros((16, 32), np.uint8)
for y in range(16):
    for x in range(32):
        dx = abs(x - 15.5) / 16.0
        dy = abs(y - 7.5) / 8.0
        s = dx + dy
        if 0.80 < s <= 1.0:
            cur[y, x] = 15
        elif s <= 0.80:
            cur[y, x] = 3
A_HUD.put(64, 64, cur)

# ----------------------------------------------------------------------------- the save icon
def save_icon():
    frames = []
    for f in range(2):
        img = np.zeros((16, 16, 4), np.uint8)
        def px(x, y, c):
            img[y, x] = list(c) + [255]
        sky = (40, 60, 140) if f == 0 else (30, 40, 110)
        for y in range(16):
            for x in range(16):
                if y >= 13:
                    px(x, y, (60, 150, 220))       # sea
        # building
        for y in range(3, 14):
            for x in range(3, 13):
                px(x, y, (240, 220, 190))
        for x in range(2, 14):
            px(x, 2, (220, 60, 90))
            px(x, 3, (220, 60, 90))
        for y in range(5, 12, 2):
            for x in range(4, 12, 2):
                lit = ((x * 7 + y * 3 + f * 5) % 4) != 0
                px(x, y, (255, 220, 110) if lit else (60, 90, 150))
        for y in range(11, 14):
            px(7, y, (120, 70, 40)); px(8, y, (120, 70, 40))
        # a star over the roof (twinkles)
        if f == 0:
            px(13, 0, (255, 240, 140)); px(12, 1, (255, 240, 140)); px(14, 1, (255, 240, 140)); px(13, 1, (255, 255, 230)); px(13, 2, (255, 240, 140))
        else:
            px(13, 1, (255, 255, 230))
        frames.append(img)
    write('save_icon.bin', make_meta(frames, title='Check-In!', quantize=True))


save_icon()

# ============================================================================= game data
STRS = bytearray()
STR_OFF = {}


def s(text):
    """Interns a string; returns its byte offset in strings.bin."""
    if text in STR_OFF:
        return STR_OFF[text]
    off = len(STRS)
    STRS.extend(text.encode('ascii') + b'\0')
    STR_OFF[text] = off
    return off


# use kinds: what an object does for the person using it
USES = ['NONE', 'SLEEP', 'TOILET', 'WASH', 'SHOWER', 'BATH', 'EAT', 'DRINK', 'TV', 'WORK', 'MODEM',
        'LOUNGE', 'MASSAGE', 'SAUNA', 'GYM', 'MEET', 'PLAY', 'SNACK', 'COFFEE', 'CHECKIN', 'CONCIERGE',
        'COOK', 'FRIDGE', 'PASS', 'LAUNDRY', 'DRY', 'LINEN', 'STORE', 'REST', 'LOCKER', 'SIT', 'PHONE',
        'MINIBAR', 'HOTTUB', 'MUSIC', 'KEYS']
U = {n: i for i, n in enumerate(USES)}

# object flags
F_STATION = 1        # needs a staff member on shift
F_OUTDOOR = 2        # may stand outdoors (deck, garden, beach)
F_INDOOR = 4         # may stand indoors
F_VOID = 8           # placed on void tiles (chandelier, skylight)
F_ATRIUM = 16        # stands at the bottom of an atrium (tree, fountain)
F_TRANSPORT = 32     # stairs and elevators
F_WALKABLE = 64      # people walk over it (rugs) - unused
F_WALLPIECE = 128    # door/window/railing: not placed from the catalogue
F_NOISY_NIGHT = 256  # loud at night (jukebox)
F_ROOFTOP = 512      # top floor only (skylight)
F_JOIN = 1024        # segments join (bar counter)
F_TALL = 2048        # placeholder: tall box

TABS = ['Rooms', 'Build', 'Bedroom', 'Bathroom', 'Lobby', 'Dining', 'Service', 'Leisure', 'Decor']
T = {n: i for i, n in enumerate(TABS)}
IO = F_INDOOR | F_OUTDOOR

# key, name, W, D, height (tiles), price, tab, unlock stars, use kind, guest spots, staff spot, noise,
# appeal, flags, placeholder colour
#   spots are (lx, lz) tiles in the object's local frame (front = +z): where a person stands to use it
OBJ = [
    ('bed_single', 'Single bed', 1, 2, 0.6, 300, 'Bedroom', 0, 'SLEEP', [(0, 2)], None, 0, 1, F_INDOOR, (110, 150, 220)),
    ('bed_double', 'Double bed', 2, 2, 0.6, 550, 'Bedroom', 0, 'SLEEP', [(0, 2), (1, 2)], None, 0, 2, F_INDOOR, (90, 130, 210)),
    ('nightstand', 'Nightstand', 1, 1, 0.5, 80, 'Bedroom', 0, 'NONE', [], None, 0, 1, F_INDOOR, (150, 100, 60)),
    ('wardrobe', 'Wardrobe', 1, 1, 2.0, 220, 'Bedroom', 0, 'NONE', [(0, 1)], None, 0, 1, F_INDOOR | F_TALL, (140, 90, 50)),
    ('tv', 'TV set', 1, 1, 1.0, 400, 'Bedroom', 0, 'TV', [(0, 2)], None, 2, 2, F_INDOOR, (60, 60, 70)),
    ('desk', 'Writing desk', 1, 1, 0.8, 180, 'Bedroom', 0, 'WORK', [(0, 1)], None, 0, 1, F_INDOOR, (160, 110, 70)),
    ('chair', 'Chair', 1, 1, 0.9, 60, 'Bedroom', 0, 'SIT', [(0, 1)], None, 0, 1, F_INDOOR | F_OUTDOOR, (170, 120, 80)),
    ('minibar', 'Minibar', 1, 1, 0.8, 350, 'Bedroom', 2, 'MINIBAR', [(0, 1)], None, 1, 2, F_INDOOR, (200, 200, 210)),
    ('floor_lamp', 'Floor lamp', 1, 1, 1.7, 90, 'Decor', 0, 'NONE', [], None, 0, 1, F_INDOOR | F_TALL, (250, 220, 150)),
    ('sofa', 'Sofa', 2, 1, 0.8, 450, 'Bedroom', 1, 'SIT', [(0, 1), (1, 1)], None, 0, 2, F_INDOOR, (200, 90, 90)),
    ('toilet', 'Toilet', 1, 1, 0.8, 150, 'Bathroom', 0, 'TOILET', [(0, 1)], None, 1, 0, F_INDOOR, (240, 240, 245)),
    ('shower', 'Shower', 1, 1, 2.2, 300, 'Bathroom', 0, 'SHOWER', [(0, 1)], None, 1, 1, F_INDOOR | F_TALL, (170, 220, 240)),
    ('bathtub', 'Bathtub', 1, 2, 0.6, 600, 'Bathroom', 1, 'BATH', [(1, 0)], None, 1, 2, F_INDOOR, (230, 235, 245)),
    ('sink', 'Sink', 1, 1, 0.9, 120, 'Bathroom', 0, 'WASH', [(0, 1)], None, 0, 0, F_INDOOR, (220, 225, 235)),
    ('jacuzzi', 'Jacuzzi', 2, 2, 0.6, 2400, 'Bathroom', 3, 'HOTTUB', [(0, 2)], None, 2, 4, F_INDOOR, (120, 200, 230)),
    ('reception_desk', 'Reception desk', 3, 1, 1.1, 1200, 'Lobby', 0, 'CHECKIN', [(1, 1)], (1, -1), 2, 2, F_INDOOR | F_STATION, (190, 140, 90)),
    ('key_rack', 'Key rack', 1, 1, 2.0, 150, 'Lobby', 0, 'KEYS', [], None, 0, 1, F_INDOOR | F_TALL, (120, 80, 40)),
    ('concierge_desk', 'Concierge desk', 2, 1, 1.1, 1500, 'Lobby', 3, 'CONCIERGE', [(0, 1)], (0, -1), 1, 3, F_INDOOR | F_STATION, (150, 60, 80)),
    ('waiting_sofa', 'Lobby sofa', 2, 1, 0.8, 500, 'Lobby', 0, 'SIT', [(0, 1), (1, 1)], None, 0, 2, F_INDOOR, (90, 140, 120)),
    ('coffee_table', 'Coffee table', 1, 1, 0.5, 120, 'Lobby', 0, 'NONE', [], None, 0, 1, F_INDOOR, (150, 110, 70)),
    ('plant', 'Potted plant', 1, 1, 1.4, 60, 'Decor', 0, 'NONE', [], None, 0, 2, IO | F_TALL, (60, 160, 70)),
    ('luggage_cart', 'Luggage cart', 1, 1, 1.3, 250, 'Lobby', 1, 'NONE', [], None, 0, 1, F_INDOOR, (230, 190, 70)),
    ('table_2', 'Table for two', 1, 1, 0.8, 200, 'Dining', 0, 'EAT', [(-1, 0), (1, 0)], None, 1, 1, IO, (200, 170, 130)),
    ('table_4', 'Table for four', 2, 2, 0.8, 380, 'Dining', 0, 'EAT', [(-1, 0), (2, 1), (0, 2), (1, -1)], None, 2, 2, IO, (190, 160, 120)),
    ('buffet', 'Buffet counter', 3, 1, 1.0, 1400, 'Dining', 2, 'EAT', [(0, 1), (1, 1), (2, 1)], None, 2, 3, F_INDOOR, (220, 200, 160)),
    ('bar_counter', 'Bar counter', 1, 1, 1.1, 300, 'Dining', 1, 'DRINK', [(0, 1)], (0, -1), 3, 1, IO | F_STATION | F_JOIN, (120, 70, 50)),
    ('bar_stool', 'Bar stool', 1, 1, 0.8, 70, 'Dining', 1, 'DRINK', [(0, 0)], None, 1, 0, IO, (200, 50, 60)),
    ('bar_shelf', 'Bottle shelf', 2, 1, 2.0, 600, 'Dining', 1, 'NONE', [], None, 0, 3, F_INDOOR | F_TALL, (160, 110, 60)),
    ('lounge_chair', 'Armchair', 1, 1, 0.9, 220, 'Decor', 1, 'SIT', [(0, 1)], None, 0, 2, F_INDOOR, (170, 80, 120)),
    ('piano', 'Grand piano', 2, 2, 1.1, 4000, 'Leisure', 3, 'MUSIC', [(0, 2)], None, 3, 5, F_INDOOR, (30, 30, 36)),
    ('jukebox', 'Jukebox', 1, 1, 1.6, 900, 'Leisure', 1, 'MUSIC', [(0, 1)], None, 5, 2, F_INDOOR | F_NOISY_NIGHT | F_TALL, (230, 120, 60)),
    ('stove', 'Stove', 1, 1, 1.0, 900, 'Dining', 0, 'COOK', [], (0, 1), 3, 0, F_INDOOR | F_STATION, (200, 205, 215)),
    ('prep_counter', 'Kitchen pass', 2, 1, 1.0, 500, 'Dining', 0, 'PASS', [(0, 1), (1, 1)], (0, -1), 1, 0, F_INDOOR, (210, 215, 225)),
    ('fridge', 'Fridge', 1, 1, 2.0, 700, 'Dining', 0, 'FRIDGE', [(0, 1)], None, 1, 0, F_INDOOR | F_TALL, (235, 240, 245)),
    ('dishwasher', 'Dishwasher', 1, 1, 0.9, 600, 'Dining', 1, 'NONE', [(0, 1)], None, 2, 0, F_INDOOR, (190, 195, 205)),
    ('kitchen_sink', 'Kitchen sink', 1, 1, 0.9, 250, 'Dining', 0, 'NONE', [(0, 1)], None, 1, 0, F_INDOOR, (200, 210, 220)),
    ('washer', 'Washing machine', 1, 1, 1.0, 800, 'Service', 0, 'LAUNDRY', [(0, 1)], None, 3, 0, F_INDOOR, (240, 240, 245)),
    ('dryer', 'Tumble dryer', 1, 1, 1.0, 700, 'Service', 1, 'DRY', [(0, 1)], None, 2, 0, F_INDOOR, (230, 230, 240)),
    ('folding_table', 'Folding table', 2, 1, 0.8, 200, 'Service', 1, 'NONE', [(0, 1)], None, 0, 0, F_INDOOR, (200, 190, 170)),
    ('linen_shelf', 'Linen shelf', 1, 1, 1.8, 180, 'Service', 0, 'LINEN', [(0, 1)], None, 0, 0, F_INDOOR | F_TALL, (180, 200, 230)),
    ('storage_shelf', 'Storage shelf', 1, 1, 1.8, 150, 'Service', 0, 'STORE', [(0, 1)], None, 0, 0, F_INDOOR | F_TALL, (170, 150, 120)),
    ('locker', 'Staff lockers', 1, 1, 2.0, 200, 'Service', 0, 'LOCKER', [(0, 1)], None, 0, 0, F_INDOOR | F_TALL, (120, 140, 170)),
    ('staff_table', 'Staff table', 2, 2, 0.8, 300, 'Service', 0, 'REST', [(-1, 0), (2, 1)], None, 0, 1, F_INDOOR, (170, 150, 120)),
    ('vending', 'Vending machine', 1, 1, 2.0, 650, 'Service', 0, 'SNACK', [(0, 1)], None, 1, 1, F_INDOOR | F_TALL, (210, 60, 70)),
    ('cot', 'Staff cot', 1, 2, 0.5, 150, 'Service', 1, 'REST', [(1, 0)], None, 0, 0, F_INDOOR, (120, 140, 110)),
    ('massage_bed', 'Massage bed', 1, 2, 0.8, 1600, 'Leisure', 3, 'MASSAGE', [(1, 0)], (-1, 1), 0, 3, F_INDOOR | F_STATION, (240, 230, 220)),
    ('sauna', 'Sauna', 3, 3, 2.4, 6000, 'Leisure', 3, 'SAUNA', [(1, 3)], None, 0, 4, F_INDOOR | F_TALL, (180, 120, 70)),
    ('hot_tub', 'Hot tub', 2, 2, 0.6, 3000, 'Leisure', 2, 'HOTTUB', [(0, 2), (1, 2)], None, 2, 4, IO, (110, 200, 220)),
    ('towel_rack', 'Towel rack', 1, 1, 1.2, 90, 'Leisure', 2, 'NONE', [], None, 0, 1, IO, (240, 240, 240)),
    ('treadmill', 'Treadmill', 1, 2, 1.2, 1800, 'Leisure', 2, 'GYM', [(0, 2)], None, 3, 1, F_INDOOR, (70, 70, 80)),
    ('weights', 'Weight bench', 2, 1, 0.8, 900, 'Leisure', 2, 'GYM', [(0, 1)], None, 3, 1, F_INDOOR, (90, 90, 110)),
    ('lounger', 'Sun lounger', 1, 2, 0.5, 250, 'Leisure', 1, 'LOUNGE', [(1, 0)], None, 1, 1, IO, (240, 240, 230)),
    ('umbrella', 'Parasol', 1, 1, 2.2, 180, 'Leisure', 1, 'NONE', [], None, 0, 2, IO | F_TALL, (240, 120, 100)),
    ('conf_table', 'Conference table', 3, 2, 0.8, 2200, 'Leisure', 2, 'MEET', [(-1, 0), (-1, 1), (3, 0), (3, 1), (1, 2)], None, 1, 2, F_INDOOR, (120, 80, 50)),
    ('projector', 'Projector screen', 1, 1, 2.0, 1200, 'Leisure', 2, 'NONE', [], None, 0, 1, F_INDOOR | F_TALL, (230, 230, 235)),
    ('lectern', 'Lectern', 1, 1, 1.2, 300, 'Leisure', 2, 'NONE', [(0, 1)], None, 0, 1, F_INDOOR, (130, 90, 50)),
    ('stairs', 'Stairs', 2, 4, 3.0, 2500, 'Build', 0, 'NONE', [(0, 4), (1, 4)], None, 1, 0, F_INDOOR | F_TRANSPORT, (180, 170, 160)),
    ('elevator', 'Elevator', 2, 2, 3.0, 8000, 'Build', 0, 'NONE', [(0, 2), (1, 2)], None, 1, 1, F_INDOOR | F_TRANSPORT | F_TALL, (170, 180, 200)),
    ('glass_elevator', 'Glass elevator', 2, 2, 3.0, 18000, 'Build', 3, 'NONE', [(0, 2), (1, 2)], None, 1, 6, F_INDOOR | F_TRANSPORT | F_TALL, (170, 230, 250)),
    ('grand_staircase', 'Grand staircase', 3, 6, 3.0, 15000, 'Build', 3, 'NONE', [(0, 6), (1, 6), (2, 6)], None, 1, 8, F_INDOOR | F_TRANSPORT, (220, 200, 160)),
    ('chandelier', 'Chandelier', 2, 2, 2.0, 7000, 'Decor', 3, 'NONE', [], None, 0, 6, F_INDOOR | F_VOID, (255, 230, 140)),
    ('skylight', 'Skylight', 2, 2, 0.3, 5000, 'Decor', 3, 'NONE', [], None, 0, 6, F_INDOOR | F_VOID | F_ROOFTOP, (190, 230, 255)),
    ('indoor_tree', 'Indoor tree', 2, 2, 5.5, 4000, 'Decor', 3, 'NONE', [], None, 0, 6, F_INDOOR | F_ATRIUM | F_TALL, (60, 150, 70)),
    ('fountain', 'Fountain', 2, 2, 1.2, 5000, 'Decor', 3, 'NONE', [], None, 2, 6, IO | F_ATRIUM, (150, 200, 230)),
    ('door', 'Door', 1, 1, 2.2, 150, 'Build', 0, 'NONE', [], None, 0, 0, F_WALLPIECE, (150, 100, 60)),
    ('window', 'Window', 1, 1, 2.2, 200, 'Build', 0, 'NONE', [], None, 0, 1, F_WALLPIECE, (170, 220, 250)),
    ('railing', 'Railing', 1, 1, 1.0, 0, 'Build', 0, 'NONE', [], None, 0, 0, F_WALLPIECE, (200, 200, 210)),
    ('railing_glass', 'Glass railing', 1, 1, 1.0, 0, 'Build', 0, 'NONE', [], None, 0, 1, F_WALLPIECE, (190, 230, 250)),
    ('bed_king', 'King-size bed', 2, 2, 0.7, 1800, 'Bedroom', 3, 'SLEEP', [(0, 2), (1, 2)], None, 0, 4, F_INDOOR, (180, 80, 110)),
    ('phone', 'Phone table', 1, 1, 0.7, 120, 'Bedroom', 0, 'PHONE', [(0, 1)], None, 0, 1, F_INDOOR, (230, 210, 170)),
    ('modem', 'Dial-up modem', 1, 1, 0.8, 300, 'Bedroom', 0, 'MODEM', [(0, 1)], None, 1, 1, F_INDOOR, (210, 205, 185)),
    ('arcade', 'Arcade cabinet', 1, 1, 1.8, 1100, 'Leisure', 1, 'PLAY', [(0, 1)], None, 4, 2, F_INDOOR | F_TALL, (80, 60, 160)),
    ('palm', 'Palm tree', 1, 1, 3.0, 150, 'Decor', 0, 'NONE', [], None, 0, 2, F_OUTDOOR | F_TALL, (70, 170, 80)),
    ('coffee_machine', 'Coffee machine', 1, 1, 1.0, 400, 'Service', 0, 'COFFEE', [(0, 1)], None, 1, 1, F_INDOOR, (120, 70, 50)),
]
assert len(OBJ) == 74
OK = {o[0]: i for i, o in enumerate(OBJ)}

# floors / room surfaces offered by the Rooms tab
FLOORS = [   # key, name, kind (0 room, 1 corridor, 2 service corridor, 3 outdoor deck, 4 pool water), price/tile, colour
    ('carpet_red', 'Room: red carpet', 0, 30, (170, 60, 70)),
    ('carpet_blue', 'Room: blue carpet', 0, 30, (60, 80, 160)),
    ('carpet_green', 'Room: green carpet', 0, 30, (60, 120, 90)),
    ('wood', 'Room: wood floor', 0, 40, (170, 120, 70)),
    ('tile', 'Room: white tiles', 0, 35, (215, 220, 225)),
    ('marble', 'Room: marble', 0, 80, (235, 225, 210)),
    ('terracotta', 'Room: terracotta', 0, 35, (200, 110, 70)),
    ('concrete', 'Room: concrete', 0, 15, (150, 150, 150)),
    ('corr_carpet', 'Corridor: carpet', 1, 25, (150, 50, 60)),
    ('corr_marble', 'Corridor: marble', 1, 70, (225, 215, 200)),
    ('service', 'Service corridor', 2, 10, (130, 130, 120)),
    ('deck', 'Outdoor deck', 3, 25, (180, 140, 90)),
    ('pool_water', 'Pool water', 4, 120, (60, 170, 230)),
]
# floor surface (texture) per floor key, and ground terrain kinds
SURF = ['grass', 'sand', 'road', 'sidewalk', 'sea', 'carpet', 'carpet2', 'carpet3', 'wood', 'tile', 'marble',
        'terracotta', 'concrete', 'deck', 'pool_water', 'roof']

# room types: key, name, unlock, min tiles, requirements [(alternatives, count)], bonus objects, overlay colour, noise
ROOMS = [
    ('none', 'Empty room', 0, 0, [], [], (120, 120, 130), 0),
    ('corridor', 'Corridor', 0, 0, [], ['plant', 'floor_lamp', 'vending', 'lounge_chair'], (190, 180, 160), 0),
    ('service', 'Service corridor', 0, 0, [], [], (130, 130, 120), 0),
    ('outdoor', 'Garden & deck', 0, 0, [], ['palm', 'plant', 'umbrella', 'lounger', 'table_2'], (120, 190, 110), 0),
    ('guest', 'Guest room', 0, 6, [(['bed_single', 'bed_double'], 1), (['wardrobe'], 1), (['toilet'], 1), (['sink'], 1),
                                   (['shower', 'bathtub'], 1)],
     ['tv', 'desk', 'chair', 'nightstand', 'floor_lamp', 'plant', 'phone', 'modem', 'minibar', 'sofa', 'lounge_chair'],
     (90, 150, 230), 0),
    ('suite', 'Suite', 3, 12, [(['bed_king'], 1), (['wardrobe'], 1), (['toilet'], 1), (['sink'], 1),
                               (['bathtub', 'jacuzzi'], 1), (['sofa', 'lounge_chair'], 1), (['tv'], 1)],
     ['desk', 'minibar', 'phone', 'modem', 'floor_lamp', 'plant', 'nightstand', 'jacuzzi', 'piano', 'coffee_table'],
     (200, 110, 220), 0),
    ('lobby', 'Lobby', 0, 9, [(['reception_desk'], 1), (['key_rack'], 1)],
     ['waiting_sofa', 'plant', 'coffee_table', 'floor_lamp', 'piano', 'fountain', 'concierge_desk', 'luggage_cart',
      'indoor_tree', 'lounge_chair'], (240, 200, 90), 2),
    ('restaurant', 'Restaurant', 0, 8, [(['table_2', 'table_4'], 2)],
     ['plant', 'floor_lamp', 'piano', 'buffet', 'fountain', 'indoor_tree'], (240, 140, 80), 2),
    ('kitchen', 'Kitchen', 0, 6, [(['stove'], 1), (['fridge'], 1), (['prep_counter'], 1)],
     ['kitchen_sink', 'dishwasher', 'storage_shelf'], (230, 230, 240), 4),
    ('laundry', 'Laundry', 0, 4, [(['washer'], 1), (['linen_shelf'], 1)], ['dryer', 'folding_table'],
     (160, 210, 240), 4),
    ('storage', 'Storage', 0, 4, [(['storage_shelf'], 2)], [], (170, 150, 120), 0),
    ('staff', 'Staff room', 0, 4, [(['locker'], 1), (['staff_table', 'cot', 'coffee_machine'], 1)],
     ['vending', 'plant', 'coffee_machine', 'cot', 'staff_table'], (150, 170, 140), 1),
    ('bar', 'Bar', 1, 6, [(['bar_counter'], 1), (['bar_stool'], 2)],
     ['bar_shelf', 'jukebox', 'lounge_chair', 'piano', 'arcade', 'table_2', 'plant'], (220, 80, 120), 6),
    ('pool', 'Pool', 1, 10, [(['lounger'], 1)], ['umbrella', 'palm', 'towel_rack', 'plant', 'hot_tub'],
     (80, 210, 230), 3),
    ('spa', 'Spa', 3, 6, [(['massage_bed'], 1), (['sauna', 'hot_tub'], 1)], ['towel_rack', 'plant', 'floor_lamp'],
     (240, 170, 200), 0),
    ('gym', 'Gym', 2, 6, [(['treadmill'], 1), (['weights'], 1)], ['towel_rack', 'vending', 'plant'], (240, 120, 70), 3),
    ('conference', 'Conference room', 2, 9, [(['conf_table'], 1), (['projector'], 1)],
     ['lectern', 'coffee_machine', 'plant', 'floor_lamp'], (130, 120, 210), 1),
]
RK = {r[0]: i for i, r in enumerate(ROOMS)}

GUESTS = [   # key, name, unlock stars, budget per night, stays (nights), wants (room kind)
    ('business', 'Business traveller', 0, 110, 1),
    ('family', 'Family', 1, 140, 2),
    ('honeymoon', 'Honeymooners', 3, 320, 2),
    ('rockstar', 'Rock star', 4, 900, 1),
]
STAFF = [   # key, name, wage per day, uniform colour
    ('receptionist', 'Receptionist', 90, (200, 40, 60)),
    ('housekeeper', 'Housekeeper', 70, (90, 160, 220)),
    ('cook', 'Cook', 110, (240, 240, 240)),
    ('waiter', 'Waiter', 80, (40, 40, 50)),
    ('bartender', 'Bartender', 90, (120, 40, 120)),
    ('therapist', 'Spa therapist', 130, (240, 200, 220)),
    ('bellhop', 'Bellhop', 70, (200, 60, 50)),
    ('maintenance', 'Maintenance', 95, (60, 110, 60)),
    ('security', 'Security', 100, (30, 30, 50)),
]

# --- reviews: (key, text) ; the game picks lines by what went right or wrong
REVIEWS = [
    ('no_reception', '"Nobody at the front desk. I rang the bell for 20 minutes."'),
    ('no_room', '"No vacancy?! In THIS economy?"'),
    ('too_pricey', '"That price? I\'m not made of dot-com stock."'),
    ('dirty', '"Found someone else\'s sock in my bed. Gross."'),
    ('noisy', '"Couldn\'t sleep - the bar was thumping till 3am."'),
    ('hungry', '"Waited forever for room service. Ate the mints."'),
    ('no_food', '"No restaurant. Had to drive to the Burger Barn."'),
    ('no_fun', '"Nothing to do here but watch the ceiling fan."'),
    ('slow', '"The elevator took longer than my 56k modem."'),
    ('broken', '"The shower was broken. The TV was broken. I was broken."'),
    ('no_wifi', '"No dial-up in the room?! How do I check my Hotmail?"'),
    ('no_pool', '"The kids wanted a pool. The kids got sad."'),
    ('no_spa', '"A honeymoon without a spa? Unromantic."'),
    ('no_suite', '"I asked for a suite. Do you know who I AM?"'),
    ('great_room', '"Comfy bed, fluffy towels. Would book again!"'),
    ('great_food', '"The chef is a genius. Five stars for the soup."'),
    ('great_view', '"That atrium! I felt like I was in a music video."'),
    ('great_pool', '"Pool, sun, sea. The kids are finally quiet."'),
    ('great_bar', '"Best mojitos this side of the millennium."'),
    ('great_service', '"Bellhop carried my bags AND my emotional baggage."'),
    ('great_spa', '"The massage melted me into a puddle. Bliss."'),
    ('great_wifi', '"Dial-up in every room. Checked my email twice!"'),
    ('rock_trash', '"Trashed the room. Best gig ever. Will return."'),
    ('ok', '"It was fine. Nice enough. A hotel, for sure."'),
    ('lost', '"Got lost looking for my room. Twice."'),
    ('tired', '"The staff looked exhausted. Hire more people!"'),
]

# ----------------------------------------------------------------------------- output
write('ui.bin', A_UI.pack())
write('hud.bin', A_HUD.pack())
palbytes = bytearray()
for p in PALS:
    for c in p:
        palbytes += c15(c).to_bytes(2, 'little')
write('pal.bin', bytes(palbytes))
for k, t in REVIEWS:
    s(t)


def arr(name, ty, vals, per=24):
    lines = []
    for i in range(0, len(vals), per):
        lines.append(', '.join(str(v) for v in vals[i:i + per]))
    return 'const %s: [%d]%s = [%s]' % (name, len(vals), ty, (',\n    ').join(lines))


L = ['// Generated by tools/gen_checkin_assets.py - do not edit.', '']
L.append('embed GEN_UI_TEX: u8 = "gen/ui.bin"')
L.append('embed GEN_HUD_TEX: u8 = "gen/hud.bin"')
L.append('embed GEN_PAL: u16 = "gen/pal.bin"')
L.append('embed STRS: u8 = "gen/strings.bin"')
L.append('embed SAVE_ICON: SaveMeta = "gen/save_icon.bin"')
L.append('const SLOT_UI = %d' % SLOT_UI)
L.append('const SLOT_HUD = %d' % SLOT_HUD)
L.append('const GEN_PAL_BASE = %d' % PAL_BASE)
L.append('const GEN_NPAL = %d' % len(PALS))
L.append('const PAL_FONT = %d' % FONT_PAL)
L.append('const PAL_LOGO = %d' % LOGO_PAL)
L.append('const PAL_GLOW = %d' % GLOW_PAL)
L.append('const LOGO_U = 0')
L.append('const LOGO_V = %d' % LOGO_V)
L.append('const LOGO_W = %d' % LW)
L.append('const LOGO_H = %d' % LH)
L.append('const UV_GLOW_U = 0')
L.append('const UV_GLOW_V = 64')
L.append('const UV_DOT_U = 32')
L.append('const UV_DOT_V = 64')
L.append('const UV_SOLID_U = 48')
L.append('const UV_SOLID_V = 64')
L.append('const UV_CURSOR_U = 64')
L.append('const UV_CURSOR_V = 64')
L.append('')
L.append('// HUD icons (slot %d): u, v, palette' % SLOT_HUD)
for name, u, v, p in ICONS:
    L.append('const IC_%s: Icon = Icon { u: %d, v: %d, pal: %d }' % (name, u, v, p))
L.append('')
L.append('// fonts (slot %d): u, v, width, advance per character 32..126' % SLOT_UI)
L.append('const FS_H = %d' % FS_H)
for nm, met in (('FS', FS_METRICS), ('FB', FB_METRICS)):
    for k, j in (('U', 0), ('V', 1), ('W', 2), ('A', 3)):
        L.append(arr('%s_%s' % (nm, k), 'u8', [m[j] for m in met], per=95))
L.append('const FB_H = %d' % FB_H)
L.append('')

# ---- object catalogue
N = len(OBJ)
L.append('// ---- the object catalogue (index order = CONTRACT.md mesh order)')
L.append('const NOBJT = %d' % N)
for i, o in enumerate(OBJ):
    L.append('const OB_%s = %d' % (o[0].upper(), i))
for k, v in U.items():
    L.append('const USE_%s = %d' % (k, v))
for nm, v in (('F_STATION', F_STATION), ('F_OUTDOOR', F_OUTDOOR), ('F_INDOOR', F_INDOOR), ('F_VOID', F_VOID),
              ('F_ATRIUM', F_ATRIUM), ('F_TRANSPORT', F_TRANSPORT), ('F_WALLPIECE', F_WALLPIECE),
              ('F_NOISY_NIGHT', F_NOISY_NIGHT), ('F_ROOFTOP', F_ROOFTOP), ('F_JOIN', F_JOIN), ('F_TALL', F_TALL)):
    L.append('const %s = %d' % (nm, v))
for i, t in enumerate(TABS):
    L.append('const TAB_%s = %d' % (t.upper(), i))
L.append('const NTABS = %d' % len(TABS))
L.append('const TAB_NAME_OFF: [%d]u16 = [%s]' % (len(TABS), ', '.join(str(s(t)) for t in TABS)))
L.append(arr('OBJ_NAME_OFF', 'u16', [s(o[1]) for o in OBJ]))
L.append(arr('OBJ_W', 'u8', [o[2] for o in OBJ]))
L.append(arr('OBJ_D', 'u8', [o[3] for o in OBJ]))
L.append(arr('OBJ_HT', 'u8', [int(round(o[4] * 16)) for o in OBJ]))
L.append(arr('OBJ_PRICE', 'u16', [o[5] for o in OBJ]))
L.append(arr('OBJ_TAB', 'u8', [T[o[6]] for o in OBJ]))
L.append(arr('OBJ_UNLOCK', 'u8', [o[7] for o in OBJ]))
L.append(arr('OBJ_USE', 'u8', [U[o[8]] for o in OBJ]))
spots_n, spots = [], []
for o in OBJ:
    sp = o[9][:5]
    spots_n.append(len(sp))
    for k in range(5):
        x, z = sp[k] if k < len(sp) else (0, 0)
        spots.append(x)
        spots.append(z)
L.append(arr('OBJ_NSPOT', 'u8', spots_n))
L.append(arr('OBJ_SPOT', 's8', spots, per=20) + '   // 5 x (lx, lz) per object')
L.append(arr('OBJ_STAFF_X', 's8', [o[10][0] if o[10] else 0 for o in OBJ]))
L.append(arr('OBJ_STAFF_Z', 's8', [o[10][1] if o[10] else 0 for o in OBJ]))
L.append(arr('OBJ_NOISE', 'u8', [o[11] for o in OBJ]))
L.append(arr('OBJ_APPEAL', 'u8', [o[12] for o in OBJ]))
L.append(arr('OBJ_FLAGS', 'u16', [o[13] for o in OBJ]))
L.append(arr('OBJ_COL', 'u32', ['0x%06X' % (c[0] | (c[1] << 8) | (c[2] << 16)) for c in (o[14] for o in OBJ)], per=8))
L.append('')
L.append('// ---- floors (Rooms tab)')
L.append('const NFLOORK = %d' % len(FLOORS))
for i, f in enumerate(FLOORS):
    L.append('const FK_%s = %d' % (f[0].upper(), i))
L.append(arr('FLOORK_NAME_OFF', 'u16', [s(f[1]) for f in FLOORS]))
L.append(arr('FLOORK_KIND', 'u8', [f[2] for f in FLOORS]))
L.append(arr('FLOORK_PRICE', 'u16', [f[3] for f in FLOORS]))
L.append(arr('FLOORK_COL', 'u32', ['0x%06X' % (c[0] | (c[1] << 8) | (c[2] << 16)) for c in (f[4] for f in FLOORS)], per=8))
L.append('')
L.append('// ---- room types')
L.append('const NROOMT = %d' % len(ROOMS))
for i, r in enumerate(ROOMS):
    L.append('const RT_%s = %d' % (r[0].upper(), i))
L.append(arr('RT_NAME_OFF', 'u16', [s(r[1]) for r in ROOMS]))
L.append(arr('RT_UNLOCK', 'u8', [r[2] for r in ROOMS]))
L.append(arr('RT_MIN', 'u8', [r[3] for r in ROOMS]))
L.append(arr('RT_COL', 'u32', ['0x%06X' % (c[0] | (c[1] << 8) | (c[2] << 16)) for c in (r[6] for r in ROOMS)], per=8))
L.append(arr('RT_NOISE', 'u8', [r[7] for r in ROOMS]))
# requirements: per room up to 7 reqs; each req = count + up to 3 alternative object types (255 = none)
reqs_n, req_cnt, req_alt = [], [], []
for r in ROOMS:
    rq = r[4]
    assert len(rq) <= 7
    reqs_n.append(len(rq))
    for k in range(7):
        if k < len(rq):
            alts, cnt = rq[k]
            req_cnt.append(cnt)
            a = [OK[x] for x in alts] + [255] * (3 - len(alts))
        else:
            req_cnt.append(0)
            a = [255, 255, 255]
        req_alt.extend(a)
L.append(arr('RT_NREQ', 'u8', reqs_n))
L.append(arr('RT_REQ_CNT', 'u8', req_cnt, per=7) + '   // 7 per room type')
L.append(arr('RT_REQ_ALT', 'u8', req_alt, per=21) + '   // 7 x 3 per room type (255: none)')
bon_n, bon = [], []
for r in ROOMS:
    b = [OK[x] for x in r[5]][:12]
    bon_n.append(len(b))
    bon.extend(b + [255] * (12 - len(b)))
L.append(arr('RT_NBONUS', 'u8', bon_n))
L.append(arr('RT_BONUS', 'u8', bon, per=12) + '   // 12 per room type')
L.append('')
L.append('// ---- guest types and staff roles')
L.append('const NGUESTT = %d' % len(GUESTS))
for i, g in enumerate(GUESTS):
    L.append('const GT_%s = %d' % (g[0].upper(), i))
L.append(arr('GT_NAME_OFF', 'u16', [s(g[1]) for g in GUESTS]))
L.append(arr('GT_UNLOCK', 'u8', [g[2] for g in GUESTS]))
L.append(arr('GT_BUDGET', 'u16', [g[3] for g in GUESTS]))
L.append(arr('GT_NIGHTS', 'u8', [g[4] for g in GUESTS]))
L.append('const NROLES = %d' % len(STAFF))
for i, st in enumerate(STAFF):
    L.append('const ROLE_%s = %d' % (st[0].upper(), i))
L.append(arr('ROLE_NAME_OFF', 'u16', [s(st[1]) for st in STAFF]))
L.append(arr('ROLE_WAGE', 'u16', [st[2] for st in STAFF]))
L.append(arr('ROLE_COL', 'u32', ['0x%06X' % (c[0] | (c[1] << 8) | (c[2] << 16)) for c in (st[3] for st in STAFF)], per=8))
L.append('')
L.append('// ---- reviews')
L.append('const NREVIEW = %d' % len(REVIEWS))
for i, (k, t) in enumerate(REVIEWS):
    L.append('const RV_%s = %d' % (k.upper(), i))
L.append(arr('REVIEW_OFF', 'u16', [s(t) for k, t in REVIEWS]))
write('strings.bin', bytes(STRS))
L.append('const STRS_LEN = %d' % len(STRS))
with open(os.path.join(OUT, 'gen.akr'), 'w') as f:
    f.write('\n'.join(L) + '\n')
print('palettes %d (%d..%d), icons %d, strings %d bytes' % (len(PALS), PAL_BASE, PAL_BASE + len(PALS) - 1,
                                                           len(ICONS), len(STRS)))

# ----------------------------------------------------------------------------- the link to the art
# art.akr (the art agent's generated declarations) is read for the names it defines; art_link.akr
# maps the catalogue's objects and surfaces onto them (placeholders where something is missing).
import re
ART = os.path.join(OUT, 'art.akr')
art_names = {}
if os.path.exists(ART) and os.path.exists(os.path.join(OUT, 'art_load.akr')):
    for m in re.finditer(r'^const (ART_[A-Z0-9_]+)(?:: [^=]+)? = (.+)$', open(ART).read(), re.M):
        art_names[m.group(1)] = m.group(2).strip()
A = ['// Generated by tools/gen_checkin_assets.py from art.akr - do not edit.',
     '// Maps the catalogue (gen.akr) onto the art: meshes by key, surfaces by name.', '']
if art_names:
    A.append('import "art_load.akr"')
    A.append('const ART_PRESENT = true')
    idx = []
    for o in OBJ:
        nm = 'ART_OBJ_' + o[0].upper()
        idx.append(art_names.get(nm, '-1') if nm in art_names else '-1')
    A.append(arr('OBJ_ART', 's16', idx))
    missing = [o[0] for o, i in zip(OBJ, idx) if i == '-1']
    print('art: %d meshes mapped, missing: %s' % (len(OBJ) - len(missing), ' '.join(missing)))
else:
    A.append('const ART_PRESENT = false')
    A.append(arr('OBJ_ART', 's16', ['-1'] * len(OBJ)))
    print('art: art.akr not found, placeholders')


def surf(name, pal=None):
    # (u, v, palette, block): block 1 when a seamless 4x4-tile 64x64 block exists
    if 'ART_FLOOR4_%s_U' % name in art_names:
        u = int(art_names['ART_FLOOR4_%s_U' % name]); v = int(art_names['ART_FLOOR4_%s_V' % name])
        p = pal if pal is not None else int(art_names.get('ART_SURF_%s_PAL' % name, 0))
        return (u, v, p, 1)
    if 'ART_SURF_%s_U' % name in art_names:
        u = int(art_names['ART_SURF_%s_U' % name]); v = int(art_names['ART_SURF_%s_V' % name])
        p = pal if pal is not None else int(art_names['ART_SURF_%s_PAL' % name])
        return (u, v, p, 0)
    return (0, 0, 0, -1)


def pal_of(name, default=0):
    return int(art_names.get('ART_PAL_' + name, default))


# surface codes: floor keys 0..12, then ground kinds (grass, sand, road, sidewalk, sea), then roof
SURF_MAP = [surf('CARPET', pal_of('CARPET_CRIMSON')), surf('CARPET', pal_of('CARPET_ROYAL')),
            surf('CARPET', pal_of('CARPET_EMERALD')), surf('WOOD'), surf('TILE'), surf('MARBLE'),
            surf('TILE', pal_of('TILE_TERRACOTTA')), surf('CONCRETE') if 'ART_FLOOR4_CONCRETE_U' in art_names else surf('PAVEMENT'),
            surf('CARPET', pal_of('CARPET_PLUM')), surf('TERRAZZO'), surf('PAVEMENT'), surf('DECK'), surf('POOL_WATER'),
            surf('GRASS'), surf('SAND'), surf('ROAD') if 'ART_FLOOR4_ROAD_U' in art_names else surf('PAVEMENT', pal_of('GREY')),
            surf('PAVEMENT'), surf('SEA'), surf('ROOF')]
A.append('const NSURF = %d' % len(SURF_MAP))
A.append(arr('SURF_U', 'u8', [m[0] for m in SURF_MAP]))
A.append(arr('SURF_V', 'u8', [m[1] for m in SURF_MAP]))
A.append(arr('SURF_PAL', 'u8', [m[2] for m in SURF_MAP]))
A.append(arr('SURF_BLOCK', 's8', [m[3] for m in SURF_MAP]) + '   // 1: 4x4-tile block, 0: one cell per tile, -1: none')
# walls: interior paint, the facade with a window, the plain facade, glass
for nm, keys in (('WALL', ('PAINT',)), ('WALLPAPER', ('WALLPAPER',)), ('FACADE', ('FACADE_WINDOW', 'FACADE')),
                 ('FACADE_PLAIN', ('FACADE', 'FACADE_PLAIN')), ('FACADE_GLASS', ('FACADE_GLASS',)),
                 ('GLASS', ('GLASS',)), ('WALL_TOP', ('WALL_TOP',))):
    m = (0, 0, 0, -1)
    for key in keys:
        m = surf(key)
        if m[3] >= 0:
            break
    A.append('const SW_%s_U = %d' % (nm, m[0]))
    A.append('const SW_%s_V = %d' % (nm, m[1]))
    A.append('const SW_%s_PAL = %d' % (nm, m[2]))
    A.append('const SW_%s_OK = %s' % (nm, 'true' if m[3] >= 0 else 'false'))
A.append('const SW_FACADE_LIT_PAL = %s' % art_names.get('ART_PAL_FACADE_CREAM_LIT', str(surf('FACADE')[2])))
ext = sorted(set(int(v) for k, v in art_names.items() if re.match(r'ART_PAL_(GRASS|SAND|PAVEMENT|SEA|LEAF|PALM|FACADE.*|ROOF.*|ASPHALT|ROAD|SKY)$', k)))
if not ext:
    ext = [255]
A.append(arr('ART_EXT_PALS', 'u8', ext) + '   // palettes lit by the sky (the rest by the interior light)')
A.append('const ART_NEXT_PALS = %d' % len(ext))
A.append('const SURF_SLOT = %s' % art_names.get('ART_SURF_SLOT', '0'))
A.append('const SURF_CELL = %s' % art_names.get('ART_SURF_SIZE', '32').split('//')[0].strip())
A.append('const SW_CELL_H = %s' % art_names.get('ART_SURF_FACADE_H', '64').split('//')[0].strip())
with open(os.path.join(OUT, 'art_link.akr'), 'w') as f:
    f.write('\n'.join(A) + '\n')

if REVIEW:
    os.makedirs(REVIEW, exist_ok=True)
    for nm, at in (('ui', A_UI), ('hud', A_HUD)):
        img = np.zeros((256, 256, 3), np.uint8)
        img[...] = (at.idx[..., None] * 17).astype(np.uint8)
        Image.fromarray(img).resize((512, 512), Image.NEAREST).save(os.path.join(REVIEW, nm + '.png'))
