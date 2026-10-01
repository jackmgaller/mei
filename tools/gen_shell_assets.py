#!/usr/bin/env python3
"""Generates the system shell's assets in system/shell/ (see system/system.akr).

  tex_font.bin   texture slot 12: medium and small proportional fonts (4-bit)
  tex_big.bin    texture slot 13: the large title font (4-bit)
  tex_art.bin    texture slot 14: icons, sun, moon, the 明 mark, button glyphs, glow dot
  pal.bin        16-colour palettes from palette 192 (15-bit colours)
  glyphs.bin     glyph metrics: 3 fonts x 100 glyphs x (u, v, w, advance)
  snd_*.raw      UI sounds, signed 8-bit PCM at 22,050 Hz
  assets.akr     embed declarations and atlas constants used by the shell

Only the texture rows actually used are written. Fonts come from macOS (Avenir Next,
Hiragino); the generated files are checked in, so other systems don't need them.
`--preview DIR` also writes enlarged pictures of the three atlases to DIR."""
import os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'system', 'shell')
SR = 22050

AVENIR = '/System/Library/Fonts/Avenir Next.ttc'
HIRAGINO = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'

PAL_BASE = 192          # the shell owns 4-bit palettes 192-254
ICON_V = 144            # slot 14 rows from here on are for memory-card save icons
ICON_PAL = 232          # palettes 232-254 are for memory-card save icons
FIRST_CHAR, NCHARS = 32, 100   # ASCII 32-126 plus extras at 127-131
EXTRA = {127: '·', 128: '◀', 129: '▶', 130: '…', 131: '×'}


def c15(r, g, b):
    return (int(r) >> 3) | ((int(g) >> 3) << 5) | ((int(b) >> 3) << 10)


class Atlas:
    """A 256x256 4-bit texture filled shelf by shelf."""
    def __init__(self, name):
        self.name = name
        self.idx = np.zeros((256, 256), np.uint8)
        self.x = 0
        self.y = 0
        self.shelf = 0

    def place(self, w, h):
        if w > 255:
            raise ValueError('too wide')
        if self.x + w > 255:          # u + w must stay below 256 (8-bit texture coordinates)
            self.x = 0
            self.y += self.shelf + 1
            self.shelf = 0
        if self.y + h > 255:
            raise ValueError('atlas %s full' % self.name)
        u, v = self.x, self.y
        self.x += w + 1
        self.shelf = max(self.shelf, h)
        return u, v

    def newline(self):
        if self.x:
            self.x = 0
            self.y += self.shelf + 1
            self.shelf = 0

    def put(self, img_idx):
        h, w = img_idx.shape
        u, v = self.place(w, h)
        self.idx[v:v + h, u:u + w] = img_idx
        return u, v

    def used_rows(self):
        return self.y + self.shelf + 1

    def pack(self):
        rows = self.used_rows()
        a = self.idx[:rows]
        lo = a[:, 0::2] & 15
        hi = a[:, 1::2] & 15
        return ((hi << 4) | lo).astype(np.uint8).tobytes()


palettes = []           # list of 16 (r, g, b) tuples


def add_palette(cols):
    cols = list(cols) + [(0, 0, 0)] * (16 - len(cols))
    palettes.append(cols[:16])
    return PAL_BASE + len(palettes) - 1


# ---------------------------------------------------------------- fonts

SHADOW = (14, 12, 34)
# index 1 is the shadow colour, 2..15 ramp from a dark edge to white
P_TEXT = add_palette([(0, 0, 0)] + [tuple(int(SHADOW[k] + (255 - SHADOW[k]) * (i / 14.0) ** 0.9)
                                          for k in range(3)) for i in range(15)])


def render_font(atlas, path, index, size, digits_mono=True, track=0):
    """Renders glyphs 32..131 with a 1px drop shadow; returns (metrics, line height)."""
    font = ImageFont.truetype(path, size, index=index)
    asc, desc = font.getmetrics()
    H = asc + desc // 2 + 2
    metrics = []
    digit_adv = max(font.getlength(str(d)) for d in range(10))
    for code in range(FIRST_CHAR, FIRST_CHAR + NCHARS):
        ch = EXTRA.get(code, chr(code) if code < 127 else ' ')
        if code >= 132:
            ch = ' '
        adv = font.getlength(ch)
        if digits_mono and ch.isdigit():
            adv = digit_adv
        S = 4      # supersample
        big = ImageFont.truetype(path, size * S, index=index)
        cw = int(adv) + 6
        img = Image.new('L', (cw * S, H * S), 0)
        d = ImageDraw.Draw(img)
        ox = 1
        if digits_mono and ch.isdigit():
            ox += (digit_adv - font.getlength(ch)) / 2
        if code in (128, 129):
            # triangles (the font has no arrows): cap height tall, centred on the x-height
            cap = big.getbbox('H')
            top, bot = cap[1], cap[3]
            mid = (top + bot) / 2
            hh = (bot - top) * 0.42
            x0, x1 = ox * S + S * 0.5, ox * S + S * 0.5 + hh * 1.5
            adv = (x1 - x0) / S + 3
            cw = int(adv) + 6
            img = Image.new('L', (cw * S, H * S), 0)
            d = ImageDraw.Draw(img)
            if code == 128:
                d.polygon([(x1, mid - hh), (x1, mid + hh), (x0, mid)], fill=255)
            else:
                d.polygon([(x0, mid - hh), (x0, mid + hh), (x1, mid)], fill=255)
        else:
            d.text((ox * S, 0), ch, font=big, fill=255)
        a = np.asarray(img.resize((cw, H), Image.BOX), np.float32) / 255.0
        a = np.clip((a - 0.12) / 0.76, 0, 1)        # firm the edges up a little
        sh = np.zeros_like(a)
        sh[1:, 1:] = a[:-1, :-1]
        idx = np.zeros(a.shape, np.uint8)
        vis = (a > 0.2) | (sh > 0.45)
        lvl = np.clip(np.round(a * 14), 0, 14).astype(np.uint8) + 1
        idx[vis] = lvl[vis]
        cols = np.where(idx.any(axis=0))[0]
        w = int(cols.max()) + 1 if len(cols) else 1
        idx = idx[:, :w]
        u, v = atlas.put(idx)
        metrics.append((u, v, w, int(round(adv)) + track))
    return metrics, H


# ---------------------------------------------------------------- art


def quantize_rgba(rgba, bg=(30, 26, 60), ncol=15):
    """RGBA float image (h, w, 4) in 0..1 -> (index image, palette list)."""
    a = rgba[..., 3]
    rgb = rgba[..., :3] * 255
    bgc = np.array(bg, np.float32)
    op = a >= 0.45
    col = rgb * a[..., None] + bgc * (1 - a[..., None])
    col = np.where(a[..., None] >= 0.9, rgb, col)
    pix = col[op].astype(np.uint8)
    idx = np.zeros(a.shape, np.uint8)
    if len(pix) == 0:
        return idx, [(0, 0, 0)]
    pimg = Image.fromarray(pix.reshape(1, -1, 3), 'RGB')
    n = min(ncol, len(np.unique(pix.reshape(-1, 3), axis=0)))
    q = pimg.quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    qp = q.getpalette()[:n * 3]
    idx[op] = np.asarray(q, np.uint8).reshape(-1) + 1
    pal = [(0, 0, 0)] + [tuple(qp[i * 3:i * 3 + 3]) for i in range(n)]
    return idx, pal


def draw_ss(w, h, fn, S=8):
    """Draws with fn(draw, S) at S times the size, returns RGBA float array (h, w, 4)."""
    img = Image.new('RGBA', (w * S, h * S), (0, 0, 0, 0))
    fn(ImageDraw.Draw(img), S, img)
    small = img.resize((w, h), Image.LANCZOS)
    return np.asarray(small, np.float32) / 255.0


art_items = {}     # name -> (u, v, w, h, palette)


def add_art(atlas, name, rgba, bg=(30, 26, 60)):
    idx, pal = quantize_rgba(rgba, bg)
    p = add_palette(pal)
    h, w = idx.shape
    u, v = atlas.put(idx)
    art_items[name] = (u, v, w, h, p)


def add_ramp(atlas, name, lum, palette):
    """A greyscale (0..1) image whose levels index a ramp palette (for additive glows)."""
    idx = np.clip(np.round(lum * 15), 0, 15).astype(np.uint8)
    h, w = idx.shape
    u, v = atlas.put(idx)
    art_items[name] = (u, v, w, h, palette)


SUN = (255, 178, 74)
SUN_HI = (255, 226, 140)
MOON = (196, 214, 255)
MOON_LO = (128, 150, 214)
INK = (30, 26, 60)


def sun_img(size):
    def f(d, S, img):
        W = size * S
        c = W / 2
        r = W * 0.30
        # rays
        import math
        for k in range(8):
            ang = k * math.pi / 4
            x0 = c + math.cos(ang) * r * 1.25
            y0 = c + math.sin(ang) * r * 1.25
            x1 = c + math.cos(ang) * r * 1.62
            y1 = c + math.sin(ang) * r * 1.62
            d.line([(x0, y0), (x1, y1)], fill=SUN + (255,), width=int(W * 0.075))
        d.ellipse([c - r, c - r, c + r, c + r], fill=SUN + (255,))
        r2 = r * 0.62
        d.ellipse([c - r2 - r * 0.15, c - r2 - r * 0.15, c + r2 - r * 0.15, c + r2 - r * 0.15], fill=SUN_HI + (255,))
    return draw_ss(size, size, f)


def moon_img(size):
    def f(d, S, img):
        W = size * S
        c = W / 2
        r = W * 0.40
        d.ellipse([c - r, c - r, c + r, c + r], fill=MOON + (255,))
        # bite out a crescent
        cut = Image.new('L', img.size, 0)
        cd = ImageDraw.Draw(cut)
        cd.ellipse([c - r + r * 0.62, c - r - r * 0.30, c + r + r * 0.62, c + r - r * 0.30], fill=255)
        arr = np.asarray(img).copy()
        arr[..., 3] = np.where(np.asarray(cut) > 0, 0, arr[..., 3])
        img.paste(Image.fromarray(arr, 'RGBA'))
        # a couple of craters
        d2 = ImageDraw.Draw(img)
        for (x, y, rr) in ((-0.45, 0.25, 0.13), (-0.2, -0.35, 0.09), (-0.55, -0.15, 0.07)):
            px, py = c + x * r, c + y * r
            if np.asarray(img)[int(py), int(px), 3] > 0:
                d2.ellipse([px - rr * r, py - rr * r, px + rr * r, py + rr * r], fill=MOON_LO + (255,))
    return draw_ss(size, size, f)


def mei_glyph(size):
    """明 with 日 (sun) warm and 月 (moon) cool, with a soft shadow."""
    font = ImageFont.truetype(HIRAGINO, size * 4, index=0)
    W, H = int(size * 1.15), int(size * 1.15)
    img = Image.new('L', (W * 4, H * 4), 0)
    ImageDraw.Draw(img).text((size * 0.06 * 4, -size * 0.02 * 4), '明', font=font, fill=255)
    a = np.asarray(img.resize((W, H), Image.BOX), np.float32) / 255.0
    cols = np.where(a.max(axis=0) > 0.1)[0]
    # split between 日 and 月 at the emptiest column in the middle third
    mid0, mid1 = cols.min() + (cols.max() - cols.min()) // 4, cols.min() + (cols.max() - cols.min()) // 2
    split = mid0 + int(np.argmin(a[:, mid0:mid1].sum(axis=0)))
    yy = np.linspace(0, 1, H)[:, None]
    warm = np.array(SUN_HI)[None, None] * (1 - yy[..., None]) + np.array((255, 140, 60))[None, None] * yy[..., None]
    cool = np.array((226, 234, 255))[None, None] * (1 - yy[..., None]) + np.array(MOON_LO)[None, None] * yy[..., None]
    # colour by connected stroke so 月's sweeping left leg stays cool
    mask = a > 0.5
    lab = np.zeros(a.shape, np.int32)
    warm_mask = np.zeros(a.shape, bool)
    n = 0
    for y0 in range(H):
        for x0 in range(W):
            if mask[y0, x0] and lab[y0, x0] == 0:
                n += 1
                stack = [(y0, x0)]
                lab[y0, x0] = n
                pts = []
                while stack:
                    y, x = stack.pop()
                    pts.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            yy2, xx2 = y + dy, x + dx
                            if 0 <= yy2 < H and 0 <= xx2 < W and mask[yy2, xx2] and lab[yy2, xx2] == 0:
                                lab[yy2, xx2] = n
                                stack.append((yy2, xx2))
                cx = np.mean([p[1] for p in pts])
                if cx < split:
                    for (y, x) in pts:
                        warm_mask[y, x] = True
    grow = warm_mask.copy()           # soft edge pixels follow their stroke
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            grow |= np.roll(np.roll(warm_mask, dy, 0), dx, 1) & ~mask
    col = np.where(grow[..., None], warm, cool)
    sh = np.zeros_like(a)
    sh[2:, 2:] = a[:-2, :-2]
    rgb = col * a[..., None] + np.array(SHADOW)[None, None] * (1 - a[..., None])
    alpha = np.maximum(a, sh * 0.9)
    rgba = np.concatenate([rgb / 255.0, alpha[..., None]], axis=2)
    return rgba


def icon(name, size=18):
    import math
    def f(d, S, img):
        W = size * S
        L = lambda v: v * W
        warm = SUN + (255,)
        cool = MOON + (255,)
        white = (246, 244, 255, 255)
        ink = INK + (255,)
        if name == 'carts':
            d.rounded_rectangle([L(.16), L(.10), L(.84), L(.90)], radius=L(.08), fill=warm)
            d.rectangle([L(.28), L(.20), L(.72), L(.56)], fill=white)
            d.rectangle([L(.34), L(.26), L(.66), L(.50)], fill=SUN_HI + (255,))
            for k in range(5):
                x = L(.26 + k * .11)
                d.rectangle([x, L(.70), x + L(.06), L(.90)], fill=ink)
        elif name == 'settings':
            c = W / 2
            for k in range(8):
                ang = k * math.pi / 4
                x, y = c + math.cos(ang) * L(.36), c + math.sin(ang) * L(.36)
                d.ellipse([x - L(.10), y - L(.10), x + L(.10), y + L(.10)], fill=cool)
            d.ellipse([c - L(.34), c - L(.34), c + L(.34), c + L(.34)], fill=cool)
            d.ellipse([c - L(.14), c - L(.14), c + L(.14), c + L(.14)], fill=(0, 0, 0, 0))
        elif name == 'pads':
            d.rounded_rectangle([L(.04), L(.26), L(.96), L(.74)], radius=L(.22), fill=white)
            d.rectangle([L(.20), L(.44), L(.38), L(.52)], fill=ink)
            d.rectangle([L(.25), L(.39), L(.33), L(.57)], fill=ink)
            d.ellipse([L(.62), L(.36), L(.72), L(.46)], fill=warm)
            d.ellipse([L(.72), L(.50), L(.82), L(.60)], fill=MOON_LO + (255,))
        elif name == 'sound':
            d.polygon([(L(.10), L(.38)), (L(.28), L(.38)), (L(.50), L(.16)), (L(.50), L(.84)), (L(.28), L(.62)), (L(.10), L(.62))], fill=white)
            for k, rr in enumerate((.18, .32)):
                bb = [L(.50) - L(rr), L(.5) - L(rr), L(.50) + L(rr), L(.5) + L(rr)]
                d.arc(bb, -50, 50, fill=warm if k == 0 else cool, width=int(L(.08)))
        elif name == 'card':
            # a memory card: cut corner, label, contacts
            d.polygon([(L(.20), L(.06)), (L(.70), L(.06)), (L(.82), L(.18)), (L(.82), L(.94)), (L(.20), L(.94))], fill=cool)
            d.rectangle([L(.30), L(.16), L(.70), L(.50)], fill=white)
            d.rectangle([L(.34), L(.22), L(.66), L(.30)], fill=warm)
            for k in range(4):
                x = L(.30 + k * .11)
                d.rectangle([x, L(.70), x + L(.06), L(.86)], fill=ink)
        elif name == 'system':
            d.rounded_rectangle([L(.22), L(.22), L(.78), L(.78)], radius=L(.06), fill=cool)
            d.rectangle([L(.36), L(.36), L(.64), L(.64)], fill=ink)
            for k in range(3):
                t = L(.32 + k * .15)
                for (x0, y0, x1, y1) in ((t, L(.06), t + L(.06), L(.22)), (t, L(.78), t + L(.06), L(.94)),
                                         (L(.06), t, L(.22), t + L(.06)), (L(.78), t, L(.94), t + L(.06))):
                    d.rectangle([x0, y0, x1, y1], fill=cool)
    return draw_ss(size, size, f)


def button_glyph(label, fill, w=13, h=13):
    font = ImageFont.truetype(AVENIR, 9 * 8, index=0)
    def f(d, S, img):
        if w == h:
            d.ellipse([0, 0, w * S - 1, h * S - 1], fill=fill + (255,))
        else:
            d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=h * S / 2, fill=fill + (255,))
        tw = d.textlength(label, font=font)
        d.text(((w * S - tw) / 2, h * S * 0.5), label, font=font, fill=INK + (255,), anchor='lm')
    return draw_ss(w, h, f)


def soft_dot(size):
    y, x = np.mgrid[0:size, 0:size]
    c = (size - 1) / 2
    r = np.sqrt((x - c) ** 2 + (y - c) ** 2) / (size / 2)
    return np.clip(1 - r, 0, 1) ** 1.6


def disc(size, ring=False):
    def f(d, S, img):
        W = size * S
        if ring:
            d.ellipse([0, 0, W - 1, W - 1], outline=(255, 255, 255, 255), width=int(S * 1.5))
        else:
            d.ellipse([0, 0, W - 1, W - 1], fill=(255, 255, 255, 255))
    return draw_ss(size, size, f)


def build_textures():
    font_atlas = Atlas('font')
    med, med_h = render_font(font_atlas, AVENIR, 2, 15)
    font_atlas.newline()
    small, small_h = render_font(font_atlas, AVENIR, 5, 12)
    big_atlas = Atlas('big')
    big, big_h = render_font(big_atlas, AVENIR, 2, 26, track=0)

    art = Atlas('art')
    add_art(art, 'mei', mei_glyph(52))
    add_art(art, 'sun', sun_img(30))
    add_art(art, 'moon', moon_img(26))
    add_art(art, 'sun_s', sun_img(14))
    add_art(art, 'moon_s', moon_img(12))
    art.newline()
    for n in ('carts', 'settings', 'pads', 'sound', 'system', 'card'):
        add_art(art, 'ic_' + n, icon(n))
    add_art(art, 'btn_a', button_glyph('A', SUN))
    add_art(art, 'btn_b', button_glyph('B', MOON))
    add_art(art, 'btn_start', button_glyph('START', (220, 216, 236), w=38, h=11))
    add_art(art, 'btn_select', button_glyph('SELECT', (220, 216, 236), w=38, h=11))
    art.newline()
    p_ramp = add_palette([tuple(int(255 * (i / 15.0) ** 1.0) for _ in range(3)) for i in range(16)])
    add_ramp(art, 'dot', soft_dot(16), p_ramp)
    add_ramp(art, 'glow', soft_dot(48) ** 0.8, p_ramp)
    # white discs/rings tinted at draw time (index 1 = white)
    p_white = add_palette([(0, 0, 0)] + [(255, 255, 255)] * 15)
    for nm, sz, ring in (('disc12', 12, False), ('disc8', 8, False), ('ring56', 56, True)):
        a = disc(sz, ring)[..., 3]
        idx = (a >= 0.5).astype(np.uint8)
        u, v = art.put(idx)
        art_items[nm] = (u, v, sz, sz, p_white)
    # rows from ICON_V down hold save icons uploaded at run time (system/shell/memcard.akr)
    assert art.used_rows() <= ICON_V, art.used_rows()
    return (font_atlas, big_atlas, art), (med, med_h), (small, small_h), (big, big_h)


# ---------------------------------------------------------------- sounds


def env_adsr(n, a, d_tau):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-np.maximum(0, t - a) / d_tau)
    return e


def bell(freq, dur, a=0.004, tau=0.09, partials=((1, 1.0), (2.0, 0.35), (3.01, 0.12), (4.2, 0.05))):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for k, (m, amp) in enumerate(partials):
        s += amp * np.sin(2 * np.pi * freq * m * t) * np.exp(-t / (tau / (1 + k * 0.8)))
    return s * env_adsr(n, a, 10)


def reverb(x, tail=0.22, mix=0.22, seed=1):
    rng = np.random.default_rng(seed)
    n = int(tail * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / (n / 5.0))
    ir[:int(0.008 * SR)] = 0                       # pre-delay
    # darken the tail
    k = np.ones(6) / 6
    ir = np.convolve(ir, k, mode='same')
    ir /= np.sqrt(np.sum(ir ** 2))
    wet = np.convolve(np.concatenate([x, np.zeros(n)]), ir)[:len(x) + n]
    dry = np.concatenate([x, np.zeros(n)])
    return dry + mix * wet * (np.max(np.abs(x)) / (np.max(np.abs(wet)) + 1e-9))


def lowpass(x, cutoff):
    # one-pole
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def place(dst, src, at):
    i = int(at * SR)
    dst[i:i + len(src)] += src[:max(0, len(dst) - i)]


def finish(x, peak=0.92, fade=0.03, seed=3):
    """Trim trailing silence, fade out, normalise and dither to signed 8-bit."""
    x = x / (np.max(np.abs(x)) + 1e-9) * peak
    thr = 0.012
    nz = np.where(np.abs(x) > thr)[0]
    end = int(nz.max()) + 1 if len(nz) else len(x)
    x = x[:end]
    nf = min(len(x), int(fade * SR))
    x[-nf:] *= np.linspace(1, 0, nf) ** 2
    rng = np.random.default_rng(seed)
    tpdf = (rng.random(len(x)) - rng.random(len(x))) / 127.0
    q = np.clip(np.round((x + tpdf) * 127), -127, 127).astype(np.int8)
    return q.tobytes()


# A major pentatonic, the family's key
NOTE = {'A4': 440.0, 'C#5': 554.37, 'E5': 659.26, 'F#5': 739.99, 'A5': 880.0, 'B5': 987.77,
        'C#6': 1108.73, 'E6': 1318.51, 'F#6': 1479.98, 'A6': 1760.0}


def snd_tick():
    n = int(0.05 * SR)
    s = bell(NOTE['A6'] * 1.5, 0.05, a=0.0012, tau=0.016, partials=((1, 1.0), (0.5, 0.5), (2.0, 0.15)))
    s = s[:n]
    return reverb(s, tail=0.07, mix=0.18)


def snd_select():
    out = np.zeros(int(0.42 * SR))
    place(out, bell(NOTE['E6'], 0.3, a=0.003, tau=0.11), 0.0)
    place(out, bell(NOTE['A6'], 0.34, a=0.003, tau=0.13) * 0.9, 0.055)
    return reverb(out, tail=0.25, mix=0.3)


def snd_back():
    out = np.zeros(int(0.32 * SR))
    place(out, bell(NOTE['C#6'], 0.22, a=0.004, tau=0.08) * 0.85, 0.0)
    place(out, bell(NOTE['F#5'], 0.26, a=0.004, tau=0.1) * 0.9, 0.05)
    return reverb(out, tail=0.2, mix=0.26)


def snd_launch():
    """A rising whoosh under a quick upward arpeggio. It has to land within the launch
    transition (about 0.6 s): the console resets when the cart starts."""
    dur = 0.62
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(n)
    # whoosh: band-pass noise sweeping upward (two one-pole stages with a moving cutoff)
    y = np.zeros(n)
    lp1 = lp2 = 0.0
    for i in range(n):
        fc = 400 + 4200 * (t[i] / dur) ** 1.3
        a = np.exp(-2 * np.pi * fc / SR)
        lp1 = (1 - a) * noise[i] + a * lp1
        lp2 = (1 - a) * lp1 + a * lp2
        y[i] = lp1 - lp2
    x = np.clip(t / dur, 0, 1)
    swell = np.minimum(1, x / 0.08) * (1 - x) ** 1.2 * (0.6 + 0.4 * np.sin(np.pi * np.minimum(1, x / 0.6)))
    y *= swell / (np.max(np.abs(y)) + 1e-9) * 0.75
    # rising sparkle arpeggio
    for k, nm in enumerate(('A5', 'C#6', 'E6', 'A6', 'C#6')):
        if k == 4:
            place(y, bell(NOTE['E6'] * 2, 0.3, a=0.003, tau=0.1) * 0.35, 0.3)
            continue
        place(y, bell(NOTE[nm], 0.3, a=0.003, tau=0.1) * (0.45 + 0.08 * k), 0.03 + k * 0.065)
    return reverb(y, tail=0.18, mix=0.28)


def snd_error():
    out = np.zeros(int(0.3 * SR))
    for k, at in enumerate((0.0, 0.11)):
        n = int(0.085 * SR)
        t = np.arange(n) / SR
        f = 155.0
        s = np.zeros(n)
        for h in range(1, 12, 2):           # soft square: odd harmonics, rolled off
            s += np.sin(2 * np.pi * f * h * t + 0.3 * h) / h ** 1.4
        s += 0.5 * np.sin(2 * np.pi * f * 1.012 * t)
        e = np.minimum(1, t / 0.004) * np.minimum(1, (t[-1] - t) / 0.012)
        place(out, s * e * (1.0 if k == 0 else 0.8), at)
    out = lowpass(out, 2400)
    return reverb(out, tail=0.12, mix=0.15)


# ---------------------------------------------------------------- ambient music
# Three instrument samples for the shell's generative ambient music (system/shell/music.akr).
# Pitch comes from the channel's PITCH register and loudness from VOL, written per frame.

MU_PAD_LEN = 8000          # 80 cycles of 220.5 Hz (A3, period 100 samples): loops seamlessly
MU_BELL_LOOP = 2200        # the bell's attack (88 cycles of 882 Hz), then a steady loop
MU_BELL_LEN = 2600


def to16(x, peak=0.9):
    x = x / (np.max(np.abs(x)) + 1e-9) * peak
    return np.clip(np.round(x * 32767), -32767, 32767).astype('<i2').tobytes()


def music_pad():
    """A soft, slowly beating pad tone: a fundamental with detuned neighbours (whole
    numbers of cycles in the loop) and a few quiet upper partials. Envelopes are done at
    run time, so this is just the sustain."""
    L = MU_PAD_LEN
    n = np.arange(L)
    w = lambda cyc, ph=0.0: np.sin(2 * np.pi * cyc * n / L + ph)
    s = (w(80) + 0.55 * w(81, 1.3) + 0.4 * w(79, 0.4) + 0.2 * w(160, 0.7) + 0.1 * w(161, 2.0)
         + 0.05 * w(240, 1.1) + 0.025 * w(321, 0.3))
    return to16(s)


def music_bell():
    """A mellow celesta-like note at 882 Hz (A5): a short inharmonic 'ting' over a pure
    tone, then a loop of the steady tone that the sequencer fades out by VOL."""
    n = np.arange(MU_BELL_LEN)
    t = n / SR
    f = SR / 25.0
    steady = np.sin(2 * np.pi * f * t) + 0.07 * np.sin(4 * np.pi * f * t + 0.5)
    ting = (0.45 * np.sin(2 * np.pi * 3.98 * f * t) + 0.18 * np.sin(2 * np.pi * 6.9 * f * t)
            + 0.12 * np.sin(2 * np.pi * 2.76 * f * t)) * np.exp(-t / 0.018)
    fade = np.ones(len(n))
    k = np.arange(MU_BELL_LOOP - 400, MU_BELL_LOOP)
    fade[k] = 0.5 + 0.5 * np.cos(np.pi * (k - k[0]) / 400)
    fade[MU_BELL_LOOP:] = 0
    s = steady + ting * fade
    s *= np.minimum(1, t / 0.003)          # soft start: no click
    return to16(s)


def music_air():
    """A breathy, filtered noise loop (crossfaded at the seam), mixed very low."""
    rng = np.random.default_rng(11)
    L = int(0.8 * SR)
    X = int(0.1 * SR)
    x = rng.standard_normal(L + X)
    # band-limit: a two-pole low-pass around 2.2 kHz minus a slow low-pass (removes rumble)
    def lp(sig, fc):
        a = np.exp(-2 * np.pi * fc / SR)
        y = np.zeros_like(sig)
        acc = 0.0
        for i in range(len(sig)):
            acc = (1 - a) * sig[i] + a * acc
            y[i] = acc
        return y
    y = lp(lp(x, 2200), 2200) - lp(x, 300)
    # crossfade the tail into the head so the loop has no seam
    head = y[:X].copy()
    tail = y[L:L + X]
    r = np.linspace(0, 1, X)
    y = y[:L].copy()
    y[:X] = head * np.sqrt(r) + tail * np.sqrt(1 - r)
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.9
    tp = (rng.random(L) - rng.random(L)) / 127.0
    return np.clip(np.round((y + tp) * 127), -127, 127).astype(np.int8).tobytes()


def wavetable():
    """One 64-sample cycle of a soft tone (sine with a little 2nd/3rd harmonic), for the
    sweep and the stereo check (pitched at run time)."""
    t = np.arange(64) / 64.0
    s = np.sin(2 * np.pi * t) + 0.12 * np.sin(4 * np.pi * t) + 0.04 * np.sin(6 * np.pi * t)
    s = s / np.max(np.abs(s)) * 0.95
    return np.clip(np.round(s * 127), -127, 127).astype(np.int8).tobytes()


# ---------------------------------------------------------------- main


def main():
    os.makedirs(OUT, exist_ok=True)
    (font_atlas, big_atlas, art), (med, med_h), (small, small_h), (big, big_h) = build_textures()
    files = {}
    files['tex_font.bin'] = font_atlas.pack()
    files['tex_big.bin'] = big_atlas.pack()
    files['tex_art.bin'] = art.pack()
    pal = b''.join(struct.pack('<16H', *[c15(*c) for c in p]) for p in palettes)
    files['pal.bin'] = pal
    g = bytearray()
    for m in (big, med, small):
        for (u, v, w, adv) in m:
            g += bytes((u, v, w, adv))
    files['glyphs.bin'] = bytes(g)
    sounds = [('tick', finish(snd_tick(), peak=0.8)), ('select', finish(snd_select())), ('back', finish(snd_back())),
              ('launch', finish(snd_launch())), ('error', finish(snd_error()))]
    for nm, data in sounds:
        files['snd_%s.raw' % nm] = data
    files['wave.raw'] = wavetable()
    music = [('pad', music_pad()), ('bell', music_bell()), ('air', music_air())]
    for nm, data in music:
        files['mu_%s.raw' % nm] = data
    total_mu = sum(len(d) for _, d in music)
    total_snd = sum(len(d) for _, d in sounds)
    assert total_snd <= 48 * 1024, total_snd
    for nm, data in files.items():
        with open(os.path.join(OUT, nm), 'wb') as f:
            f.write(data)

    L = []
    L.append('// Generated by tools/gen_shell_assets.py - do not edit.')
    L.append('// Shell resources: texture slots 12-14, 4-bit palettes %d-%d (docs/SYSTEM.md).' % (PAL_BASE, PAL_BASE + len(palettes) - 1))
    L.append('')
    L.append('embed SH_TEX_FONT: u8 = "tex_font.bin"')
    L.append('embed SH_TEX_BIG: u8 = "tex_big.bin"')
    L.append('embed SH_TEX_ART: u8 = "tex_art.bin"')
    L.append('embed SH_PAL: u16 = "pal.bin"')
    L.append('embed SH_GLYPHS: u8 = "glyphs.bin"')
    for nm, _ in sounds:
        L.append('embed SH_SND_%s: s8 = "snd_%s.raw"' % (nm.upper(), nm))
    L.append('embed SH_WAVE: s8 = "wave.raw"')
    L.append('embed SH_MU_PAD: s16 = "mu_pad.raw"      // looped, 220.5 Hz at pitch 1.0')
    L.append('embed SH_MU_BELL: s16 = "mu_bell.raw"    // 882 Hz at pitch 1.0, loops from SH_MU_BELL_LOOP')
    L.append('embed SH_MU_AIR: s8 = "mu_air.raw"       // looped noise')
    L.append('const SH_MU_BELL_LOOP = %d' % MU_BELL_LOOP)
    L.append('// pitch ratios 2^(n/12) for n = -24..24: SH_SEMI[n + 24]')
    L.append('const SH_SEMI: [49]fixed = [%s]' % ', '.join('%.5f' % (2 ** ((k - 24) / 12.0)) for k in range(49)))
    L.append('')
    L.append('const SH_SLOT_FONT = 12')
    L.append('const SH_SLOT_BIG = 13')
    L.append('const SH_SLOT_ART = 14')
    L.append('const SH_PAL_BASE = %d' % PAL_BASE)
    L.append('const SH_PAL_COUNT = %d' % len(palettes))
    L.append('const SH_PAL_TEXT = %d' % P_TEXT)
    L.append('const SH_ICON_V = %d          // slot 14 rows from here: save icons (memcard.akr)' % ICON_V)
    L.append('const SH_ICON_PAL = %d        // palettes from here to 254: save icon palettes' % ICON_PAL)
    assert PAL_BASE + len(palettes) <= ICON_PAL
    L.append('')
    L.append('// fonts: glyph table index, line height, texture slot')
    L.append('const SH_FIRST_CHAR = %d' % FIRST_CHAR)
    L.append('const SH_NCHARS = %d' % NCHARS)
    L.append('const SH_FONT_BIG = 0')
    L.append('const SH_FONT_MED = 1')
    L.append('const SH_FONT_SMALL = 2')
    L.append('const SH_FONT_H: [3]s32 = [%d, %d, %d]' % (big_h, med_h, small_h))
    L.append('const SH_FONT_SLOT: [3]u32 = [13, 12, 12]')
    L.append('// extra glyphs')
    L.append('const SH_CH_DOT = "\\x7f"')
    L.append('const SH_CH_LEFT = "\\x80"')
    L.append('const SH_CH_RIGHT = "\\x81"')
    L.append('')
    L.append('// art in slot 14: u, v, w, h, palette')
    for nm, (u, v, w, h, p) in art_items.items():
        L.append('const SH_ART_%s: [5]s32 = [%d, %d, %d, %d, %d]' % (nm.upper(), u, v, w, h, p))
    with open(os.path.join(OUT, 'assets.akr'), 'w') as f:
        f.write('\n'.join(L) + '\n')
    print('music samples: %d bytes (%s)' % (total_mu, ', '.join('%s %d' % (n, len(d)) for n, d in music)))
    print('rows used: font %d, big %d, art %d; palettes %d; sounds %d bytes (%s)' % (
        font_atlas.used_rows(), big_atlas.used_rows(), art.used_rows(), len(palettes), total_snd,
        ', '.join('%s %d' % (n, len(d)) for n, d in sounds)))

    if len(sys.argv) > 2 and sys.argv[1] == '--preview':
        prev = sys.argv[2]
        for at in (font_atlas, big_atlas, art):
            img = np.zeros((256, 256, 3), np.uint8)
            img[:] = (60, 50, 110)
            # show with each item's palette is complex; use the text palette / greys
            pal_arr = np.array(palettes[0], np.uint8)
            img[at.idx > 0] = pal_arr[at.idx[at.idx > 0]]
            if at is art:
                for nm, (u, v, w, h, p) in art_items.items():
                    pa = np.array(palettes[p - PAL_BASE], np.uint8)
                    reg = at.idx[v:v + h, u:u + w]
                    sub = img[v:v + h, u:u + w]
                    sub[reg > 0] = pa[reg[reg > 0]]
            Image.fromarray(img).resize((768, 768), Image.NEAREST).save(os.path.join(prev, 'atlas_%s.png' % at.name))


if __name__ == '__main__':
    main()
