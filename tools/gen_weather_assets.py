#!/usr/bin/env python3
"""Fair Skies art: fonts, glossy weather-icon layers, interface glyphs, the logo, palettes, the
temperature colour ramp, the memory-card icon and the map geography.

Writes carts/weather/art/ (texture rows per slot, palettes, the geography blob, the save icon)
and carts/weather/art.akr (the embeds and the sprite and font tables).

Texture slots and palettes (4-bit palettes count from colour 0 in steps of 16):
  slot 0       the map, 8-bit (128 x 96, rows 0-95; written at run time), 8-bit palette 0 = the
               temperature ramp (colours 0-255)
  slot 1       the map overlay, 4-bit (256 x 192; rasterised at run time), palette 16
  slot 2       the big fonts                slot 3   the text fonts and interface glyphs
  slot 4       the weather icon layers
  slot 15      the standard library's fonts (palette 255)

Fonts: '`' is drawn as a degree sign in every font of the cart.

The geography (tools/weather_geo.py) is hand-drawn: coasts, lakes, the borders of the US,
Canada and Mexico and the US state lines, simplified for a 64 x 48 temperature map.

    python3 tools/gen_weather_assets.py [--preview DIR]
"""
import argparse, math, os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import meifont
import mei_icon
import weather_geo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CART = os.path.join(ROOT, 'carts', 'weather')
ART = os.path.join(CART, 'art')

AVENIR = '/System/Library/Fonts/Avenir Next.ttc'
AVENIR_COND = '/System/Library/Fonts/Avenir Next Condensed.ttc'
# Avenir Next faces in the collection: 0 Bold, 2 Demi Bold, 7 Medium, 5 Italic ... (looked up by name below)

SS = 4          # supersampling for drawn art


def rgb15(r, g, b):
    return (int(r) >> 3) | ((int(g) >> 3) << 5) | ((int(b) >> 3) << 10)


def face_index(path, want):
    """The index of the face called `want` (e.g. 'Demi Bold') in a font collection."""
    for i in range(32):
        try:
            f = ImageFont.truetype(path, 12, index=i)
        except OSError:
            break
        if f.getname()[1] == want:
            return i
    raise SystemExit('no face %r in %s' % (want, path))


# ============================================================================ fonts

def degree_glyph(path, size, index):
    g, _, _ = meifont.ttf_glyphs(path, size, index=index, first=0xB0, count=1)
    return g[0]


def ttf_font(path, face, size, keep=None, track=0, mono_digits=False):
    idx = face_index(path, face)
    glyphs, h, line = meifont.ttf_glyphs(path, size, index=idx, first=32, count=95,
                                         track=track, mono_digits=mono_digits)
    deg_img, deg_adv = degree_glyph(path, size, idx)
    glyphs[ord('`') - 32] = (deg_img, deg_adv + track)
    if keep is not None:
        glyphs = [(img, adv) if chr(32 + i) in keep else (None, adv) for i, (img, adv) in enumerate(glyphs)]
    # crop the rows no glyph uses (TrueType cells have room above the capitals)
    top, bot = h, 0
    for img, adv in glyphs:
        if img is not None and img.any():
            rows = np.where(img.any(axis=1))[0]
            top, bot = min(top, rows.min()), max(bot, rows.max())
    glyphs = [(img[top:bot + 1] if img is not None else None, adv) for img, adv in glyphs]
    nh = bot + 1 - top
    return glyphs, nh, nh + max(2, line - h)


def pixel_small_font():
    table = dict(meifont.SMALL)
    table['`'] = ('.##.', '#..#', '#..#', '.##.')
    return meifont.pixel_glyphs(table, ink=15)


def font_colours(shadow_rgb=(12, 16, 52)):
    return meifont.default_colours(15, None, shadow_rgb)


# ============================================================================ drawing helpers

def canvas(w, h):
    return Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))


def vgrad(w, h, top, bottom):
    t = np.linspace(0, 1, h)[:, None, None]
    a = np.array(top, np.float32)[None, None, :]
    b = np.array(bottom, np.float32)[None, None, :]
    g = a + (b - a) * t
    return np.broadcast_to(g, (h, w, 3)).copy()


def radial(w, h, cx, cy, r, stops):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    out = np.zeros((h, w, 3), np.float32)
    pos = [s[0] for s in stops]
    for c in range(3):
        out[..., c] = np.interp(d, pos, [s[1][c] for s in stops])
    return out


def mask_of(draw_fn, w, h):
    m = Image.new('L', (w * SS, h * SS), 0)
    draw_fn(ImageDraw.Draw(m), SS)
    return np.asarray(m, np.float32) / 255.0


def compose(fill, mask, outline_rgb, outline_px=1.0, highlight=None):
    """fill (H, W, 3) at SS scale, mask (H, W) 0..1 at SS scale -> RGBA float image at 1x with a
    dark rim. highlight: (mask, strength) of a glossy white overlay."""
    H, W = mask.shape
    m_img = Image.fromarray((mask * 255).astype(np.uint8))
    grown = m_img.filter(ImageFilter.MaxFilter(int(outline_px * SS) * 2 + 1))
    g = np.asarray(grown, np.float32) / 255.0
    rgb = np.where(mask[..., None] > 0.5, fill, np.array(outline_rgb, np.float32)[None, None, :])
    if highlight is not None:
        hm, k = highlight
        rgb = rgb + (255 - rgb) * (hm * mask)[..., None] * k
    a = np.maximum(g, mask)
    rgba = np.dstack([rgb, a * 255])
    # (Pillow resizes RGBA with premultiplied alpha, so straight colour goes in and comes out)
    small = np.asarray(Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), 'RGBA')
                       .resize((W // SS, H // SS), Image.BOX), np.float32)
    return np.dstack([small[..., :3], small[..., 3] / 255.0])


def to_indexed(img, ncol=15, edge_rgb=None):
    """RGBA float (h, w, 4) -> (indices 0..15 with 0 transparent, palette [(r,g,b)] of 16)."""
    a = img[..., 3]
    rgb = img[..., :3].copy()
    if edge_rgb is not None:
        k = np.clip((1 - a) * 1.4, 0, 1)[..., None]
        rgb = rgb * (1 - k) + np.array(edge_rgb, np.float32) * k
    opaque = a >= 0.45
    h, w = a.shape
    idx = np.zeros((h, w), np.uint8)
    pal = [(0, 0, 0)] * 16
    if not opaque.any():
        return idx, pal
    pix = rgb[opaque].astype(np.uint8)
    pimg = Image.fromarray(pix.reshape(1, -1, 3), 'RGB')
    q = pimg.quantize(colors=ncol, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    qp = q.getpalette()[:ncol * 3]
    qi = np.asarray(q, np.uint8).reshape(-1)
    idx[opaque] = qi + 1
    for i in range(ncol):
        pal[i + 1] = tuple(qp[i * 3:i * 3 + 3]) if i * 3 + 2 < len(qp) else (0, 0, 0)
    return idx, pal


# ============================================================================ weather icon layers

def sun_disc(d):
    w = h = d + 4
    c = w * SS / 2
    r = d * SS / 2
    m = mask_of(lambda dr, s: dr.ellipse([c - r, c - r, c + r, c + r], fill=255), w, h)
    fill = radial(w * SS, h * SS, c - r * 0.25, c - r * 0.3, r * 1.25,
                  [(0, (255, 252, 225)), (0.45, (255, 226, 110)), (0.85, (255, 178, 60)), (1.2, (240, 140, 40))])
    hl = mask_of(lambda dr, s: dr.ellipse([c - r * 0.62, c - r * 0.78, c + r * 0.1, c - r * 0.18], fill=255), w, h)
    hl = np.asarray(Image.fromarray((hl * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(SS * d / 14)), np.float32) / 255
    return compose(fill, m, (196, 98, 32), 1.0, (hl, 0.55))


def sun_rays(d, n=12):
    w = h = d
    c = w * SS / 2
    r0, r1, r2 = d * SS * 0.33, d * SS * 0.48, d * SS * 0.40

    def draw(dr, s):
        for i in range(n):
            a = 2 * math.pi * i / n
            rr = r1 if i % 2 == 0 else r2
            hw = 0.13 if i % 2 == 0 else 0.11
            pts = [(c + r0 * math.cos(a - hw), c + r0 * math.sin(a - hw)),
                   (c + rr * math.cos(a), c + rr * math.sin(a)),
                   (c + r0 * math.cos(a + hw), c + r0 * math.sin(a + hw))]
            dr.polygon(pts, fill=255)
    m = mask_of(draw, w, h)
    fill = radial(w * SS, h * SS, c, c, d * SS * 0.5, [(0, (255, 236, 140)), (0.7, (255, 205, 90)), (1.0, (255, 170, 60))])
    return compose(fill, m, (205, 110, 35), 0.8)


def moon(d):
    w = h = d + 4
    c = w * SS / 2
    r = d * SS / 2

    def draw(dr, s):
        dr.ellipse([c - r, c - r, c + r, c + r], fill=255)
        o = r * 0.62
        dr.ellipse([c - r + o, c - r - o * 0.45, c + r + o, c + r - o * 0.45], fill=0)
    m = mask_of(draw, w, h)
    fill = radial(w * SS, h * SS, c - r * 0.4, c, r * 1.3,
                  [(0, (255, 252, 232)), (0.6, (246, 236, 190)), (1.1, (214, 200, 150))])
    return compose(fill, m, (120, 116, 100), 1.0)


def cloud(w, h, top, bottom, rim, gloss=0.6):
    W, H = w * SS, h * SS

    def draw(dr, s):
        base = H * 0.86
        dr.rounded_rectangle([W * 0.06, H * 0.48, W * 0.94, base], radius=H * 0.2, fill=255)
        for cx, cy, r in [(0.30, 0.55, 0.24), (0.52, 0.40, 0.33), (0.74, 0.55, 0.22), (0.18, 0.66, 0.17), (0.86, 0.67, 0.16)]:
            dr.ellipse([W * cx - H * r * 1.25, H * cy - H * r * 1.25, W * cx + H * r * 1.25, H * cy + H * r * 1.25], fill=255)
    m = mask_of(draw, w, h)
    fill = vgrad(W, H, top, bottom)
    hl = mask_of(lambda dr, s: dr.ellipse([W * 0.33, H * 0.10, W * 0.66, H * 0.36], fill=255), w, h)
    hl = np.asarray(Image.fromarray((hl * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(SS * h / 10)), np.float32) / 255
    return compose(fill, m, rim, 1.0, (hl, gloss))


def drop(w, h):
    W, H = w * SS, h * SS

    def draw(dr, s):
        dr.ellipse([0, H - W, W, H], fill=255)
        dr.polygon([(W * 0.5, 0), (W * 0.02, H - W * 0.5), (W * 0.98, H - W * 0.5)], fill=255)
    m = mask_of(draw, w, h)
    fill = vgrad(W, H, (170, 225, 255), (40, 130, 235))
    return compose(fill, m, (24, 64, 150), 0.6)


def flake(d):
    W = d * SS
    c = W / 2

    def draw(dr, s):
        for i in range(3):
            a = math.pi * i / 3
            dx, dy = math.cos(a) * c * 0.92, math.sin(a) * c * 0.92
            dr.line([c - dx, c - dy, c + dx, c + dy], fill=255, width=int(SS * 1.3))
        dr.ellipse([c - SS * 1.4, c - SS * 1.4, c + SS * 1.4, c + SS * 1.4], fill=255)
    m = mask_of(draw, d, d)
    fill = vgrad(W, W, (255, 255, 255), (215, 235, 255))
    return compose(fill, m, (70, 110, 170), 0.6)


def bolt(w, h):
    W, H = w * SS, h * SS

    def draw(dr, s):
        pts = [(0.62, 0.0), (0.12, 0.56), (0.44, 0.56), (0.30, 1.0), (0.90, 0.38), (0.56, 0.38), (0.80, 0.0)]
        dr.polygon([(x * W, y * H) for x, y in pts], fill=255)
    m = mask_of(draw, w, h)
    fill = vgrad(W, H, (255, 248, 160), (255, 176, 40))
    return compose(fill, m, (150, 80, 20), 0.8)


def fog(w, h):
    W, H = w * SS, h * SS

    def draw(dr, s):
        dr.rounded_rectangle([0, 0, W, H], radius=H / 2, fill=255)
    m = mask_of(draw, w, h)
    fill = vgrad(W, H, (240, 244, 252), (196, 206, 226))
    return compose(fill, m, (96, 110, 140), 0.6)


CLOUD_W = ((255, 255, 255), (206, 220, 244), (84, 104, 156))
CLOUD_D = ((196, 204, 222), (112, 122, 150), (46, 54, 80))


def icon_layers(scale):
    """The layers for one size: scale 1.0 (large) or about 0.5 (medium)."""
    s = lambda v: max(3, int(round(v * scale)))
    return {
        'rays': sun_rays(s(66)),
        'disc': sun_disc(s(38)),
        'moon': moon(s(38)),
        'cloud': cloud(s(78), s(48), *CLOUD_W),
        'dark': cloud(s(78), s(48), *CLOUD_D, gloss=0.35),
        'bolt': bolt(s(18), s(32)),
        'fog': fog(s(70), s(7)),
    }


def small_icon(kind, night):
    """A static 20 x 16 icon for the hourly chart and lists, composed at 4x and reduced; rain,
    snow and lightning are then drawn crisp at 1x."""
    W, H = 20, 16
    big = Image.new('RGBA', (W * 4, H * 4), (0, 0, 0, 0))

    def paste(layer, cx, cy):
        im = Image.fromarray(np.clip(np.dstack([layer[..., :3], layer[..., 3:] * 255]), 0, 255).astype(np.uint8), 'RGBA')
        big.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))
    L = icon_layers(0.85)

    def sun(cx, cy):
        if night:
            paste(L['moon'], cx, cy)
        else:
            paste(L['rays'], cx, cy)
            paste(L['disc'], cx, cy)
    wet = kind in ('drizzle', 'rain', 'showers', 'snow', 'thunder')
    if kind == 'clear':
        sun(40, 32)
    elif kind == 'partly':
        sun(30, 24)
        paste(L['cloud'], 46, 42)
    elif kind in ('cloudy', 'unknown'):
        paste(L['dark'], 30, 26)
        paste(L['cloud'], 46, 40)
    elif kind == 'fog':
        paste(L['cloud'], 40, 24)
        for i in range(3):
            paste(L['fog'], 40, 40 + i * 9)
    else:
        if kind == 'showers':
            sun(26, 18)
        paste(L['dark'] if kind != 'snow' else L['cloud'], 40, 24)
    im = np.asarray(big.resize((W, H), Image.BOX), np.float32)
    rgba = np.dstack([im[..., :3], im[..., 3] / 255.0])

    def dot(x, y, col):
        if 0 <= y < H and 0 <= x < W:
            rgba[y, x] = (*col, 1.0)
    if kind in ('drizzle', 'rain', 'showers'):
        xs = (6, 10, 14) if kind != 'drizzle' else (7, 12)
        for i, x in enumerate(xs):
            y = 12 + (i % 2)
            dot(x, y, (120, 196, 255))
            if kind != 'drizzle':
                dot(x - 1, y + 2, (70, 150, 245))
    if kind == 'snow':
        for i, x in enumerate((6, 10, 14)):
            y = 12 + (i % 2) * 2
            for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
                dot(x + dx, y + dy, (244, 250, 255) if (dx, dy) == (0, 0) else (190, 220, 255))
    if kind == 'thunder':
        for dx, dy in ((10, 10), (9, 11), (9, 12), (10, 12), (11, 12), (10, 13), (10, 14), (9, 15)):
            dot(dx, dy, (255, 224, 80))
    return rgba


SMALL_KINDS = ['clear', 'partly', 'cloudy', 'fog', 'drizzle', 'rain', 'showers', 'snow', 'thunder', 'unknown']


# ============================================================================ interface glyphs

def glyph_drop():
    return drop(7, 10)


def glyph_wind():
    W, H = 12, 10

    def draw(dr, s):
        k = SS
        dr.line([0, 3 * k, 8 * k, 3 * k], fill=255, width=int(1.4 * k))
        dr.arc([6 * k, 0.6 * k, 10.6 * k, 5.2 * k], 180, 100, fill=255, width=int(1.4 * k))
        dr.line([0, 6.5 * k, 9 * k, 6.5 * k], fill=255, width=int(1.4 * k))
        dr.arc([7 * k, 5 * k, 11.5 * k, 9.6 * k], 260, 160, fill=255, width=int(1.4 * k))
    m = mask_of(draw, W, H)
    fill = vgrad(W * SS, H * SS, (235, 245, 255), (190, 215, 245))
    return compose(fill, m, (30, 44, 90), 0.0)


def glyph_sunrise(up):
    W, H = 16, 10

    def draw(dr, s):
        k = SS
        dr.pieslice([3 * k, 3 * k, 13 * k, 13 * k], 180, 360, fill=255)
        dr.rectangle([0, 8.2 * k, 16 * k, 9.4 * k], fill=255)
        ax = 8 * k
        if up:
            dr.polygon([(ax, 0), (ax - 2.2 * k, 2.4 * k), (ax + 2.2 * k, 2.4 * k)], fill=255)
        else:
            dr.polygon([(ax, 2.6 * k), (ax - 2.2 * k, 0.2 * k), (ax + 2.2 * k, 0.2 * k)], fill=255)
    m = mask_of(draw, W, H)
    fill = vgrad(W * SS, H * SS, (255, 230, 140), (250, 160, 70))
    return compose(fill, m, (60, 30, 30), 0.0)


def glyph_home():
    W, H = 10, 10

    def draw(dr, s):
        k = SS
        dr.polygon([(5 * k, 0.5 * k), (0.2 * k, 5 * k), (9.8 * k, 5 * k)], fill=255)
        dr.rectangle([1.6 * k, 4.5 * k, 8.4 * k, 9.6 * k], fill=255)
    m = mask_of(draw, W, H)
    fill = vgrad(W * SS, H * SS, (255, 255, 255), (220, 230, 250))
    return compose(fill, m, (30, 40, 80), 0.0)


def glyph_dish():
    """A little satellite dish for the tuning screen (24 x 24)."""
    W, H = 24, 24

    def draw(dr, s):
        k = SS
        dr.chord([1 * k, 2 * k, 19 * k, 20 * k], 110, 340, fill=255)
        dr.line([10 * k, 11 * k, 16 * k, 5 * k], fill=255, width=int(1.3 * k))
        dr.ellipse([15 * k, 3.5 * k, 18 * k, 6.5 * k], fill=255)
        dr.polygon([(9 * k, 15 * k), (5 * k, 23 * k), (15 * k, 23 * k)], fill=255)
    m = mask_of(draw, W, H)
    fill = vgrad(W * SS, H * SS, (250, 252, 255), (170, 190, 225))
    return compose(fill, m, (30, 40, 80), 0.9)


def logo():
    """'Fair Skies' wordmark: Avenir Next Heavy Italic, white on a glossy sun swoosh."""
    W, H = 118, 26
    idx = face_index(AVENIR, 'Heavy Italic')
    f = ImageFont.truetype(AVENIR, 19 * SS, index=idx)
    m = Image.new('L', (W * SS, H * SS), 0)
    d = ImageDraw.Draw(m)
    d.text((24 * SS, 1 * SS), 'Fair Skies', font=f, fill=255)
    mask = np.asarray(m, np.float32) / 255
    fill = vgrad(W * SS, H * SS, (255, 255, 255), (210, 228, 255))
    text = compose(fill, mask, (16, 30, 90), 1.2)
    sun = sun_disc(16)
    rays = sun_rays(26, 10)
    out = np.zeros((H, W, 4), np.float32)

    def over(dst, src, x, y):
        h, w = src.shape[:2]
        a = src[..., 3:4]
        dst[y:y + h, x:x + w, :3] = src[..., :3] * a + dst[y:y + h, x:x + w, :3] * (1 - a)
        dst[y:y + h, x:x + w, 3] = a[..., 0] + dst[y:y + h, x:x + w, 3] * (1 - a[..., 0])
    over(out, rays, 0, 0)
    over(out, sun, 3, 3)
    over(out, text, 0, 0)
    return out


# ============================================================================ palettes and ramp

RAMP_STOPS = [
    (-30, (122, 84, 172)), (-20, (112, 112, 212)), (-10, (92, 152, 232)), (0, (96, 196, 236)),
    (5, (98, 214, 208)), (10, (116, 220, 162)), (15, (166, 226, 122)), (20, (224, 230, 112)),
    (25, (250, 206, 98)), (30, (250, 162, 82)), (35, (240, 114, 84)), (40, (222, 74, 96)),
    (45, (190, 54, 116)),
]
RAMP_LO, RAMP_HI = -30.0, 45.0
NO_DATA = (36, 48, 88)


def ramp_colour(t):
    ts = [s[0] for s in RAMP_STOPS]
    return tuple(float(np.interp(t, ts, [s[1][c] for s in RAMP_STOPS])) for c in range(3))


def ramp_palette():
    """8-bit palette 0: index 1 = no data, 2..255 = RAMP_LO..RAMP_HI."""
    cols = [0, rgb15(*NO_DATA)]
    for i in range(2, 256):
        t = RAMP_LO + (RAMP_HI - RAMP_LO) * (i - 2) / 253.0
        cols.append(rgb15(*ramp_colour(t)))
    return cols


def ramp_index_table():
    """Quarter degrees C from -120 (-30 C) to 180 (+45 C) -> ramp index 2..255."""
    out = []
    for q in range(-120, 181):
        t = q / 4.0
        out.append(int(round(2 + (t - RAMP_LO) / (RAMP_HI - RAMP_LO) * 253)))
    return out


OVERLAY = {  # 4-bit palette 16
    1: (20, 40, 92),        # water
    2: (30, 60, 124),       # water near a coast
    3: (226, 236, 250),     # coastline
    4: (28, 34, 70),        # state and province lines
    5: (16, 22, 52),        # national borders
    6: (40, 76, 146),       # water, a second ring off the coast
}


# ============================================================================ atlas packing

class Atlas:
    def __init__(self, slot, rows=256):
        self.slot = slot
        self.img = np.zeros((rows, 256), np.uint8)
        self.x = 0
        self.y = 0
        self.shelf = 0
        self.used = 0

    def place(self, idx, gap=1):
        h, w = idx.shape
        if self.x + w > 255:
            self.x = 0
            self.y += self.shelf + gap
            self.shelf = 0
        if self.y + h > 255:
            raise SystemExit('atlas %d is full' % self.slot)
        u, v = self.x, self.y
        self.img[v:v + h, u:u + w] = idx
        self.x += w + gap
        self.shelf = max(self.shelf, h)
        self.used = max(self.used, v + h)
        return u, v

    def skip_to(self, row):
        self.x = 0
        self.y = row
        self.shelf = 0

    def blob(self):
        rows = self.used
        t = self.img[:rows]
        return ((t[:, 0::2] & 15) | ((t[:, 1::2] & 15) << 4)).astype(np.uint8).tobytes()


class Palettes:
    def __init__(self, first):
        self.first = first
        self.pals = []

    def add(self, pal):
        self.pals.append([rgb15(*c) if i else 0 for i, c in enumerate(pal)])
        return self.first + len(self.pals) - 1

    def add15(self, cols15):
        self.pals.append(list(cols15))
        return self.first + len(self.pals) - 1

    def blob(self):
        return b''.join(struct.pack('<16H', *p) for p in self.pals)


def place_font(atlas, glyphs, h, line, pal_index, colours, name, akr):
    f = meifont.build_font(glyphs, h, line, slot=atlas.slot, palette=pal_index, row=atlas.y + (atlas.shelf + 1 if atlas.x else 0),
                           colours=colours, include_texels=False)
    start = f.row
    rows = f.atlas.shape[0]
    atlas.img[start:start + rows, :] = np.maximum(atlas.img[start:start + rows, :], f.atlas)
    atlas.used = max(atlas.used, start + rows)
    atlas.skip_to(start + rows + 1)
    path = os.path.join(ART, name + '.fnt')
    with open(path, 'wb') as fh:
        fh.write(f.blob())
    akr.append('embed %s: Font = "art/%s.fnt"' % (name.upper(), name))
    return f


# ============================================================================ geography

def geo_blob():
    """Polylines and polygons in hundredths of a degree (s16 pairs).
    Header: u16 count of shapes; per shape u8 kind, u8 reserved, u16 points, then the points
    (lat, lon). Kinds: 0 land ring, 1 lake ring, 2 coast-free border line, 3 state line."""
    shapes = weather_geo.shapes()
    out = bytearray(struct.pack('<HH', len(shapes), 0))
    npts = 0
    for kind, pts in shapes:
        out += struct.pack('<BBH', kind, 0, len(pts))
        for lat, lon in pts:
            out += struct.pack('<hh', int(round(lat * 100)), int(round(lon * 100)))
        npts += len(pts)
    return bytes(out), len(shapes), npts


# ============================================================================ save icon

def save_icon():
    frames = []
    for k in range(2):
        big = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        rays = sun_rays(44, 10)
        if k:
            rays = np.asarray(Image.fromarray(np.clip(np.dstack([rays[..., :3], rays[..., 3:] * 255]), 0, 255)
                                              .astype(np.uint8), 'RGBA').rotate(15), np.float32)
            rays = np.dstack([rays[..., :3], rays[..., 3] / 255])
        for layer, (x, y) in [(rays, (14, 0)), (sun_disc(26), (21, 7)), (cloud(56, 34, *CLOUD_W), (2, 28))]:
            im = Image.fromarray(np.clip(np.dstack([layer[..., :3], layer[..., 3:] * 255]), 0, 255).astype(np.uint8), 'RGBA')
            big.alpha_composite(im, (x, y))
        frames.append(big.resize((16, 16), Image.LANCZOS))
    return mei_icon.make_meta(frames, 'Fair Skies', quantize=True)


# ============================================================================ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview', help='write PNG previews of the atlases here')
    args = ap.parse_args()
    os.makedirs(ART, exist_ok=True)
    akr = ['// Generated by tools/gen_weather_assets.py - do not edit.',
           '// Texture slots, palettes, fonts and sprites of Fair Skies (see the generator for the layout).',
           '']
    consts = []
    pals = Palettes(17)          # 4-bit palettes from 17 (16 is the overlay)

    # ---- slot 2: big fonts
    a2 = Atlas(2)
    cond = AVENIR_COND
    huge = ttf_font(cond, 'Demi Bold', 60, keep='-0123456789:`', mono_digits=True)
    big = ttf_font(cond, 'Demi Bold', 30, keep='-0123456789:`/APMapm ', mono_digits=True)
    p_huge = pals.add15(font_colours())
    place_font(a2, *huge, p_huge, font_colours(), 'f_huge', akr)
    p_big = pals.add15(font_colours())
    place_font(a2, *big, p_big, font_colours(), 'f_big', akr)

    # ---- slot 3: text fonts and interface glyphs
    a3 = Atlas(3)
    med = ttf_font(AVENIR, 'Demi Bold', 15)
    small = ttf_font(AVENIR, 'Demi Bold', 11)
    tiny = pixel_small_font()
    p_med = pals.add15(font_colours())
    place_font(a3, *med, p_med, font_colours(), 'f_med', akr)
    p_small = pals.add15(font_colours())
    place_font(a3, *small, p_small, font_colours(), 'f_small', akr)
    p_tiny = pals.add15(meifont.default_colours(15))
    place_font(a3, *tiny, p_tiny, meifont.default_colours(15), 'f_tiny', akr)

    sprites = []      # (name, slot, palette, u, v, w, h)

    def add_sprite(atlas, name, rgba, edge=None):
        idx, pal = to_indexed(rgba, edge_rgb=edge)
        p = pals.add(pal)
        u, v = atlas.place(idx)
        sprites.append((name, atlas.slot, p, u, v, idx.shape[1], idx.shape[0]))
        return idx, pal

    for name, img in [('g_drop', glyph_drop()), ('g_wind', glyph_wind()), ('g_rise', glyph_sunrise(True)),
                      ('g_set', glyph_sunrise(False)), ('g_home', glyph_home()), ('g_dish', glyph_dish()),
                      ('logo', logo())]:
        add_sprite(a3, name, img)

    # ---- slot 4: icon layers, large and medium, and the small icons
    a4 = Atlas(4)
    for size, scale in (('L', 1.0), ('M', 0.52)):
        for name, img in icon_layers(scale).items():
            add_sprite(a4, 'i%s_%s' % (size, name), img)
    for size, w, h in (('L', 5, 11), ('M', 3, 7)):
        add_sprite(a4, 'i%s_drop' % size, drop(w, h))
    add_sprite(a4, 'iL_flake', flake(11))
    add_sprite(a4, 'iM_flake', flake(7))
    # the small icons: one per icon class, day then night, each with its own palette; laid
    # out in a row (SMALL_ICON_U + i * (w + 1)), one palette each from SMALL_ICON_PAL
    first_pal = None
    for night in (False, True):
        a4.x = 0
        a4.y += a4.shelf + 1
        a4.shelf = 0
        for i, k in enumerate(SMALL_KINDS):
            idx, pal = to_indexed(small_icon(k, night))
            p = pals.add(pal)
            if first_pal is None:
                first_pal = p
            u, v = a4.place(idx)
            sprites.append(('%s_%s' % ('in' if night else 'is', k), 4, p, u, v, 20, 16))
            if night and i == 0:
                consts.append('const SMALL_NIGHT_V = %d' % v)
            if not night and i == 0:
                consts.append('const SMALL_ICON_U = %d' % u)
                consts.append('const SMALL_ICON_V = %d' % v)
    consts.append('const SMALL_ICON_PAL = %d' % first_pal)
    consts.append('const SMALL_ICON_W = 20')
    consts.append('const SMALL_ICON_H = 16')

    # ---- write textures and palettes
    for a in (a2, a3, a4):
        with open(os.path.join(ART, 'slot%d.bin' % a.slot), 'wb') as fh:
            fh.write(a.blob())
        akr.append('embed TEX%d: u8 = "art/slot%d.bin"' % (a.slot, a.slot))
        consts.append('const TEX%d_ROWS = %d' % (a.slot, a.used))
    with open(os.path.join(ART, 'pal.bin'), 'wb') as fh:
        fh.write(pals.blob())
    akr.append('embed PALS: u16 = "art/pal.bin"')
    consts.append('const PAL_FIRST = %d' % pals.first)
    consts.append('const PAL_COUNT = %d' % len(pals.pals))
    with open(os.path.join(ART, 'ramp.bin'), 'wb') as fh:
        fh.write(struct.pack('<256H', *ramp_palette()))
    akr.append('embed RAMP_PAL: u16 = "art/ramp.bin"')
    ov = [0] * 16
    for k, c in OVERLAY.items():
        ov[k] = rgb15(*c)
    with open(os.path.join(ART, 'overlay_pal.bin'), 'wb') as fh:
        fh.write(struct.pack('<16H', *ov))
    akr.append('embed OVERLAY_PAL: u16 = "art/overlay_pal.bin"')
    rit = ramp_index_table()
    akr.append('')
    akr.append('// Ramp index (2-255) of a temperature in quarter degrees C, from -30 C (RAMP_Q0).')
    akr.append('const RAMP_Q0 = -120')
    akr.append('const RAMP_IDX: [%d]u8 = [' % len(rit))
    for i in range(0, len(rit), 20):
        akr.append('    ' + ', '.join(str(v) for v in rit[i:i + 20]) + ',')
    akr[-1] = akr[-1].rstrip(',')
    akr.append(']')
    # the ramp's colours at whole degrees, for the legend and labels (0xBBGGRR)
    akr.append('// The ramp colour of each whole degree C from -30 to 45.')
    rc = []
    for t in range(-30, 46):
        r, g, b = ramp_colour(t)
        rc.append('0x%02X%02X%02X' % (int(b), int(g), int(r)))
    akr.append('const RAMP_RGB: [%d]u32 = [' % len(rc))
    for i in range(0, len(rc), 10):
        akr.append('    ' + ', '.join(rc[i:i + 10]) + ',')
    akr[-1] = akr[-1].rstrip(',')
    akr.append(']')

    # ---- geography
    gb, ns, npts = geo_blob()
    with open(os.path.join(ART, 'geo.bin'), 'wb') as fh:
        fh.write(gb)
    akr.append('embed GEO: u8 = "art/geo.bin"      // %d shapes, %d points' % (ns, npts))

    # ---- save icon
    with open(os.path.join(ART, 'save_icon.bin'), 'wb') as fh:
        fh.write(save_icon())
    akr.append('embed SAVE_ICON: SaveMeta = "art/save_icon.bin"')

    # ---- sprite table
    akr.append('')
    akr.append('struct Spr { slot: u8, pal: u8, u: u8, v: u8, w: u8, h: u8 }')
    for name, slot, p, u, v, w, h in sprites:
        akr.append('const %s: Spr = Spr { slot: %d, pal: %d, u: %d, v: %d, w: %d, h: %d }'
                   % (name.upper(), slot, p, u, v, w, h))
    akr.append('')
    akr += consts
    with open(os.path.join(CART, 'art.akr'), 'w') as fh:
        fh.write('\n'.join(akr) + '\n')

    if args.preview:
        os.makedirs(args.preview, exist_ok=True)

        def c24(c):
            return ((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3)
        for a in (a2, a3, a4):
            img = np.zeros((a.used, 256, 3), np.uint8)
            img[:] = (40, 60, 120)
            grey = a.img[:a.used] > 0
            img[grey] = np.stack([a.img[:a.used][grey] * 16] * 3, axis=1)
            for name, slot, p, u, v, w, h in sprites:
                if slot != a.slot:
                    continue
                pal = pals.pals[p - pals.first]
                for y in range(h):
                    for x in range(w):
                        k = a.img[v + y, u + x]
                        if k:
                            img[v + y, u + x] = c24(pal[k])
            Image.fromarray(img).resize((768, a.used * 3), Image.NEAREST).save(os.path.join(args.preview, 'slot%d.png' % a.slot))
    print('fonts, %d sprites, %d palettes; geography %d shapes, %d points' % (len(sprites), len(pals.pals), ns, npts))


if __name__ == '__main__':
    main()
