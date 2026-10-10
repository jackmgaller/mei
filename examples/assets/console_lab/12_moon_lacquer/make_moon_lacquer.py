#!/usr/bin/env python3
"""Moon-viewing Lacquer (console lab look 12): draws art/moon_lacquer.png (+ .sheet.json) and
writes console.asset.json and controller.asset.json beside this file.

Run: python3 examples/assets/console_lab/12_moon_lacquer/make_moon_lacquer.py   (needs Pillow)

Units are metres at real size. Both models face -Z (the player's side); Y is up.
The console's lid carries the hanafuda 'susuki ni tsuki' card (full moon over pampas grass)
as a lacquer inlay; the controller's stick cap is the moon.
"""
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "art")
FONTS = "/System/Library/Fonts"
F_GOTHIC = os.path.join(FONTS, "ヒラギノ角ゴシック W8.ttc")
F_MINCHO = os.path.join(FONTS, "ヒラギノ明朝 ProN.ttc")
F_LATIN = os.path.join(FONTS, "Avenir Next.ttc")

# Palette ---------------------------------------------------------------------------------
LACQUER = "#2a1d20"      # urushi black, a little warm so shading reads
LACQUER_TEX = (42, 29, 32)
SHU = "#c63a24"          # vermilion
SHU_RGB = (198, 58, 36)
SHU_DARK = (150, 38, 24)
GOLD = "#d8b257"         # maki-e gold
GOLD_RGB = (214, 172, 82)
GOLD_DIM = (150, 112, 50)
MOON_RGB = (246, 236, 208)
HOLE = "#0b0809"

S = 4  # supersampling for the drawn cells


def r5(v):
    return [round(x, 5) for x in v]


# ---------------------------------------------------------------------------------------
# Controller outline (plan view, x right, z away from the player), shared with the art
# ---------------------------------------------------------------------------------------
def sd_round_box(x, z, cx, cz, hx, hz, r):
    qx = abs(x - cx) - (hx - r)
    qz = abs(z - cz) - (hz - r)
    return math.hypot(max(qx, 0), max(qz, 0)) + min(max(qx, qz), 0) - r


def sd_capsule(x, z, ax, az, bx, bz, r):
    px, pz = x - ax, z - az
    dx, dz = bx - ax, bz - az
    h = max(0.0, min(1.0, (px * dx + pz * dz) / (dx * dx + dz * dz)))
    return math.hypot(px - dx * h, pz - dz * h) - r


def smin(a, b, k):
    h = max(k - abs(a - b), 0.0) / k
    return min(a, b) - h * h * k * 0.25


def pad_sdf(x, z):
    body = sd_round_box(x, z, 0.0, 0.002, 0.058, 0.034, 0.022)
    gl = sd_capsule(x, z, -0.050, -0.004, -0.054, -0.047, 0.0215)
    gr = sd_capsule(x, z, 0.050, -0.004, 0.054, -0.047, 0.0215)
    return smin(body, min(gl, gr), 0.014)


def pad_grad(x, z):
    e = 1e-5
    gx = (pad_sdf(x + e, z) - pad_sdf(x - e, z)) / (2 * e)
    gz = (pad_sdf(x, z + e) - pad_sdf(x, z - e)) / (2 * e)
    n = math.hypot(gx, gz)
    return gx / n, gz / n


def pad_outline(n_half=18):
    """Symmetric outline, first point at the back centre (x 0, z max), going round through +x."""
    oz = -0.006
    pts = []
    steps = 900
    for i in range(steps + 1):
        a = math.pi / 2 - math.pi * i / steps          # from +z (back) clockwise to -z (front)
        dx, dz = math.cos(a), math.sin(a)
        t_hi = 0.2
        t = t_hi
        while t > 0 and pad_sdf(dx * t, oz + dz * t) > 0:
            t -= 0.0005
        lo, hi = t, t + 0.0005
        for _ in range(40):
            m = (lo + hi) / 2
            if pad_sdf(dx * m, oz + dz * m) > 0:
                hi = m
            else:
                lo = m
        pts.append((dx * lo, oz + dz * lo))
    pts[0] = (0.0, pts[0][1])
    pts[-1] = (0.0, pts[-1][1])
    # resample by arc length, weighting curvature a little so grip ends stay round
    w = [0.0]
    for i in range(1, len(pts)):
        seg = math.dist(pts[i], pts[i - 1])
        w.append(w[-1] + seg)
    total = w[-1]
    half = []
    for k in range(n_half + 1):
        target = total * k / n_half
        j = 1
        while j < len(w) - 1 and w[j] < target:
            j += 1
        f = (target - w[j - 1]) / max(w[j] - w[j - 1], 1e-12)
        half.append((pts[j - 1][0] + (pts[j][0] - pts[j - 1][0]) * f,
                     pts[j - 1][1] + (pts[j][1] - pts[j - 1][1]) * f))
    half[0] = (0.0, half[0][1])
    half[-1] = (0.0, half[-1][1])
    left = [(-x, z) for (x, z) in reversed(half[1:-1])]
    return half + left      # clockwise seen from above (+x first going down)


def inset(pts, d):
    out = []
    for (x, z) in pts:
        gx, gz = pad_grad(x, z)
        out.append((x - gx * d, z - gz * d))
    return out


PAD_TOP_Y = 0.026
PAD_INSET_TOP = 0.0055
PAD_LAYOUT = {
    "dpad": (-0.047, 0.004),
    "abxy": (0.047, 0.004),
    "stick": (0.0, -0.016),
    "select": (-0.011, 0.0115),
    "start": (0.011, 0.0115),
    "logo": (0.0, 0.0235),
}


def pad_top_bounds():
    top = inset(pad_outline(), PAD_INSET_TOP)
    xs = [p[0] for p in top]
    zs = [p[1] for p in top]
    return min(xs), max(xs), min(zs), max(zs)


# ---------------------------------------------------------------------------------------
# Art
# ---------------------------------------------------------------------------------------
CELLS = {}   # name -> (x, y, w, h)


def font(path, px, index=0):
    return ImageFont.truetype(path, px, index=index)


def big(w, h, bg):
    im = Image.new("RGBA", (w * S, h * S), bg)
    return im, ImageDraw.Draw(im)


def down(im, w, h):
    return im.resize((w, h), Image.LANCZOS)


def grass_blade(d, x0, y0, x1, y1, bend, width, fill):
    """A susuki blade as a quadratic curve from (x0, y0) to (x1, y1), in big pixels."""
    cx = (x0 + x1) / 2 + bend
    cy = (y0 + y1) / 2
    prev = None
    n = 16
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1
        y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1
        if prev:
            wv = max(1, int(round(width * (1 - 0.6 * t))))
            d.line([prev, (x, y)], fill=fill, width=wv)
        prev = (x, y)
    return prev


def droop(d, x, y, side, length, fill, width=None):
    """A susuki ear hanging from a stalk's tip at (x, y): a horsetail of strokes falling to `side`."""
    width = width or max(1, S // 2)
    for k in range(6):
        a = -0.5 + k * 0.32                       # radians below the horizontal, toward `side`
        L = length * (0.75 + 0.25 * math.sin(k * 1.7))
        pts = []
        for i in range(7):
            t = i / 6
            pts.append((x + side * math.cos(a) * L * t, y + (math.sin(a) * L * t + 0.5 * L * t * t)))
        d.line(pts, fill=fill, width=width, joint="curve")


def arch(d, x0, y0, lean, height, fill, width):
    """A susuki leaf: rises from (x0, y0), then arches over toward `lean`."""
    pts = []
    for i in range(13):
        t = i / 12
        pts.append((x0 + lean * t * t, y0 - height * (1 - (1 - t) ** 2) + abs(lean) * 0.25 * t ** 3))
    for i in range(12):
        wv = max(1, int(round(width * (1 - 0.7 * i / 12))))
        d.line([pts[i], pts[i + 1]], fill=fill, width=wv)


def hill_curve(W, H):
    def hy(x):
        t = x / W
        return H * (0.645 - 0.075 * math.sin(math.pi * (t * 0.85 + 0.1)) + 0.012 * math.cos(9 * t))
    return hy


def draw_card():
    """The hanafuda 'susuki ni tsuki' card: vermilion sky, full moon, a black hill of pampas
    grass worked in gold, three stalks in silhouette across the moon."""
    import random
    w, h = 56, 92
    im, d = big(w, h, SHU_RGB)
    W, H = w * S, h * S
    for yy in range(0, int(H * 0.25)):
        t = yy / (H * 0.25)
        c = tuple(int(SHU_DARK[i] * (1 - t) + SHU_RGB[i] * t) for i in range(3))
        d.line([(0, yy), (W, yy)], fill=c)
    mx, my, mr = 28 * S, 31 * S, 18.5 * S
    d.ellipse([mx - mr - S, my - mr - S, mx + mr + S, my + mr + S], fill=(226, 200, 150))
    d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=MOON_RGB)
    hy = hill_curve(W, H)
    d.polygon([(x, hy(x)) for x in range(0, W + 1, S)] + [(W, H), (0, H)], fill=LACQUER_TEX)
    rnd = random.Random(1997)
    # the grass edge: blade tips in silhouette along the hill's crest
    for i in range(70):
        x = rnd.uniform(-4 * S, W + 4 * S)
        lean = rnd.uniform(-1, 1) * 5 * S
        top = hy(min(max(x, 0), W)) - rnd.uniform(1.5, 5) * S
        grass_blade(d, x - lean * 0.3, hy(min(max(x, 0), W)) + 3 * S, x + lean, top, lean * 0.5, S * 1.0,
                    LACQUER_TEX)
    # gold line work on the hill: clumps of susuki fanning out like fountains
    for (cx, base_y, n, spread) in ((8, 96, 8, 1.0), (27, 98, 10, 1.1), (46, 96, 8, 1.0),
                                    (17, 100, 6, 0.8), (38, 100, 6, 0.8)):
        for k in range(n):
            a = (k / (n - 1) - 0.5) * 2 * 0.95 * spread + rnd.uniform(-0.08, 0.08)
            x0, y0 = cx * S, base_y * S
            reach = y0 - hy(cx * S) - rnd.uniform(0, 6) * S
            L = reach / max(math.cos(a * 0.8), 0.5) * rnd.uniform(0.75, 1.0)
            arch(d, x0, y0, math.sin(a) * L * 0.9, math.cos(a * 0.8) * L,
                 GOLD_RGB if rnd.random() < 0.3 else GOLD_DIM, S * 0.75)
    # three ears of susuki in gold against the sky, bowing away from the moon
    for (bx, tx, ty, side) in ((7, 5, 38, -1), (50, 52, 42, 1), (45, 49, 34, 1)):
        x0, y0 = bx * S, hy(bx * S) + 4 * S
        tip = grass_blade(d, x0, y0, tx * S, ty * S, (tx - bx) * S, S * 1.0, GOLD_RGB)
        droop(d, tip[0], tip[1], side, 7 * S, (240, 214, 150), width=S // 2 + 1)
    # two long leaves in silhouette, arching across the moon's foot
    arch(d, 9 * S, H, 20 * S, H - hy(20 * S) + 9 * S, LACQUER_TEX, S * 1.6)
    arch(d, 47 * S, H, -16 * S, H - hy(34 * S) + 7 * S, LACQUER_TEX, S * 1.6)
    im = down(im, w, h)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=GOLD_RGB)
    for (cx, cy) in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        d.point((cx, cy), fill=LACQUER_TEX)
    return im


def draw_gloss(w, h, seed, flecks=0.003, band=(0.30, 0.18)):
    """Lacquer with a soft window reflection and a sparse dust of nashiji gold."""
    import random
    rnd = random.Random(seed)
    im = Image.new("RGBA", (w, h), LACQUER_TEX + (255,))
    px = im.load()
    for y in range(h):
        for x in range(w):
            u, v = x / (w - 1), y / (h - 1)
            dist = (u * 0.8 - v * 0.6) - band[0]
            k = math.exp(-(dist / band[1]) ** 2) * 0.55 + math.exp(-((dist - 0.28) / 0.05) ** 2) * 0.35
            c = tuple(int(LACQUER_TEX[i] + (88 - LACQUER_TEX[i]) * k * 0.45) for i in range(3))
            px[x, y] = c + (255,)
    for y in range(h):
        for x in range(w):
            if rnd.random() < flecks:
                base = px[x, y]
                px[x, y] = tuple((base[i] + GOLD_DIM[i]) // 2 for i in range(3)) + (255,)
    return im


def text_center(d, cx, cy, s, f, fill):
    l, t, r, b = d.textbbox((0, 0), s, font=f)
    d.text((cx - (l + r) / 2, cy - (t + b) / 2), s, font=f, fill=fill)


def draw_mei(d, cx, cy, size, sun=(240, 160, 64), moon=(168, 200, 236), word=(246, 238, 224),
             word_size=None, gap=None):
    """明 with 日 in warm orange and 月 in pale blue, then MEI. Draws at (cx, cy) as left-centre."""
    f = font(F_GOTHIC, size)
    l, t, r, b = d.textbbox((0, 0), "明", font=f)
    gw = r - l
    mask = Image.new("L", (r + 4, b + 4), 0)
    ImageDraw.Draw(mask).text((0, 0), "明", font=f, fill=255)
    split = l + int(gw * 0.40)
    x0 = int(cx - l)
    y0 = int(cy - (t + b) / 2)
    left = Image.new("RGBA", mask.size, sun + (255,))
    right = Image.new("RGBA", mask.size, moon + (255,))
    lm = mask.copy()
    ImageDraw.Draw(lm).rectangle([split, 0, mask.size[0], mask.size[1]], fill=0)
    rm = mask.copy()
    ImageDraw.Draw(rm).rectangle([0, 0, split - 1, mask.size[1]], fill=0)
    d._image.paste(left, (x0, y0), lm)
    d._image.paste(right, (x0, y0), rm)
    fw = font(F_LATIN, word_size or int(size * 0.78), index=0)
    gx = cx + gw + (gap if gap is not None else size * 0.28)
    l2, t2, r2, b2 = d.textbbox((0, 0), "MEI", font=fw)
    d.text((gx - l2, cy - (t2 + b2) / 2), "MEI", font=fw, fill=word)
    return gx + (r2 - l2)


def draw_logo():
    w, h = 64, 18
    im, d = big(w, h, LACQUER_TEX)
    end = draw_mei(d, 6 * S, 9 * S, 13 * S, word_size=11 * S)
    # a gold dot and a hairline, as on a maker's plate
    d.ellipse([end + 3 * S, 9 * S - S, end + 5 * S, 9 * S + S], fill=GOLD_RGB)
    im = down(im, w, h)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=GOLD_DIM)
    return im


def draw_port():
    w, h = 16, 12
    im = Image.new("RGBA", (w, h), (24, 18, 20))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=SHU_DARK)
    d.rounded_rectangle([2, 2, w - 3, h - 3], radius=2, fill=(8, 6, 7), outline=(60, 50, 52))
    for i in range(4):
        d.point((4 + i * 2 + 1, 5), fill=GOLD_RGB)
        d.point((4 + i * 2 + 1, 7), fill=GOLD_DIM)
    return im


def draw_mcslot():
    w, h = 24, 8
    im = Image.new("RGBA", (w, h), (24, 18, 20))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=SHU_DARK)
    d.rectangle([3, 3, w - 4, 4], fill=(6, 4, 5))
    d.line([3, 5, w - 4, 5], fill=(70, 58, 60))
    d.polygon([(w - 3, 2), (w - 2, 2), (w - 3, 3)], fill=GOLD_RGB)
    return im


def draw_label():
    w, h = 48, 34
    im, d = big(w, h, (28, 34, 70))
    W, H = w * S, h * S
    for yy in range(H):
        t = yy / H
        c = (int(22 + 30 * t), int(26 + 26 * t), int(64 + 20 * t))
        d.line([(0, yy), (W, yy)], fill=c)
    d.ellipse([30 * S, 4 * S, 42 * S, 16 * S], fill=MOON_RGB)
    # a rabbit on a hill: the moon rabbit
    d.polygon([(0, 26 * S), (14 * S, 21 * S), (30 * S, 23 * S), (48 * S, 20 * S), (48 * S, 34 * S), (0, 34 * S)],
              fill=(14, 12, 24))
    d.ellipse([13 * S, 16 * S, 21 * S, 22 * S], fill=(236, 232, 226))
    d.ellipse([19 * S, 14 * S, 23 * S, 18 * S], fill=(236, 232, 226))
    d.ellipse([20 * S, 9 * S, 22 * S, 15 * S], fill=(236, 232, 226))
    d.ellipse([21.5 * S, 10 * S, 23.5 * S, 15 * S], fill=(236, 232, 226))
    f = font(F_LATIN, 7 * S, index=0)
    text_center(d, 24 * S, 29 * S, "TSUKIMI", f, GOLD_RGB)
    im = down(im, w, h)
    ImageDraw.Draw(im).rectangle([0, 0, w - 1, h - 1], outline=(236, 230, 214))
    return im


def draw_geese():
    """Three wild geese (kari) in gold: the August card's other bird, as maki-e draws them."""
    w, h = 48, 26
    im, d = big(w, h, (0, 0, 0, 0))
    for (gx, gy, k) in ((10, 17, 1.0), (24, 9, 0.9), (38, 14, 0.8)):
        x, y, L = gx * S, gy * S, 8 * S * k
        wing = [(x - L, y + 0.15 * L), (x - 0.75 * L, y - 0.20 * L), (x - 0.40 * L, y - 0.32 * L),
                (x - 0.08 * L, y), (x, y + 0.05 * L), (x + 0.08 * L, y), (x + 0.40 * L, y - 0.32 * L),
                (x + 0.75 * L, y - 0.20 * L), (x + L, y + 0.15 * L)]
        d.line(wing, fill=GOLD_RGB, width=int(S * 1.6), joint="curve")
        d.ellipse([x - 0.16 * L, y - 0.10 * L, x + 0.16 * L, y + 0.22 * L], fill=GOLD_RGB)
    return down(im, w, h)


def draw_side():
    w, h = 128, 24
    im, d = big(w, h, (0, 0, 0, 0))
    W, H = w * S, h * S
    # a low drift of susuki along the bottom, thinning toward the back
    import random
    rnd = random.Random(12)
    for i in range(46):
        x0 = rnd.uniform(0, W)
        density = 1.0 - x0 / W * 0.5
        if rnd.random() > density:
            continue
        hgt = rnd.uniform(0.35, 0.9) * H
        lean = rnd.uniform(-6, 10) * S
        grass_blade(d, x0, H, x0 + lean, H - hgt, lean * 0.7, S * 0.8, GOLD_RGB if rnd.random() < 0.7 else GOLD_DIM)
    for i in range(9):
        x0 = rnd.uniform(0.05, 0.9) * W
        hgt = rnd.uniform(0.6, 0.85) * H
        lean = rnd.uniform(2, 9) * S
        grass_blade(d, x0, H, x0 + lean, H - hgt, lean * 0.7, S * 0.8, GOLD_RGB)
        droop(d, x0 + lean, H - hgt, 1, 3.5 * S, (236, 210, 140))
    return down(im, w, h)


def draw_back():
    w, h = 64, 12
    im = Image.new("RGBA", (w, h), (30, 22, 24))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=(70, 56, 58))
    # AV multi-out, MeiNet antenna, DC in
    d.rounded_rectangle([4, 3, 22, 8], radius=1, fill=(6, 4, 5), outline=GOLD_DIM)
    for i in range(6):
        d.point((7 + i * 2, 5), fill=GOLD_RGB)
    d.ellipse([30, 2, 37, 9], fill=(10, 8, 9), outline=GOLD_RGB)
    d.point((33, 5), fill=GOLD_RGB)
    d.point((34, 6), fill=GOLD_RGB)
    d.ellipse([46, 3, 52, 9], fill=(10, 8, 9), outline=(150, 150, 150))
    d.point((49, 6), fill=(200, 200, 200))
    d.rectangle([56, 3, 59, 8], fill=SHU_RGB)
    return im


def draw_letter(ch):
    w, h = 12, 12
    im, d = big(w, h, (238, 230, 220))
    f = font(F_LATIN, 9 * S, index=0)
    text_center(d, 6 * S, 6.3 * S, ch, f, SHU_RGB)
    return down(im, w, h)


def draw_padtop():
    w, h = 128, 96
    x0, x1, z0, z1 = pad_top_bounds()
    im = draw_gloss(w, h, 3, flecks=0.004, band=(0.05, 0.16)).resize((w * S, h * S), Image.NEAREST)
    d = ImageDraw.Draw(im)

    def P(x, z):
        return ((x - x0) / (x1 - x0) * w * S, (z1 - z) / (z1 - z0) * h * S)

    def R(r):
        return r / (x1 - x0) * w * S

    def ring(x, z, r, fill=None, outline=None, width=1):
        cx, cy = P(x, z)
        rx, ry = R(r), r / (z1 - z0) * h * S
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill, outline=outline, width=width)

    # a clump of susuki on each grip, fanning up and bowing toward the stick, the moon
    import random
    rnd = random.Random(7)
    for side in (-1, 1):
        bx, by = P(side * 0.054, -0.064)
        n = 11
        for k in range(n):
            a = side * (-0.45 + 1.25 * k / (n - 1)) + rnd.uniform(-0.06, 0.06)   # + leans inward
            L = R(rnd.uniform(0.026, 0.040))
            arch(d, bx, by, -math.sin(a) * L * 0.9, math.cos(a * 0.7) * L * 0.95,
                 GOLD_RGB if rnd.random() < 0.4 else GOLD_DIM, S * 0.85)
        for (tx, tz) in ((0.024, -0.030), (0.032, -0.021)):
            qx, qy = P(side * tx, tz)
            grass_blade(d, bx, by, qx, qy, R(side * 0.008), S * 0.9, GOLD_RGB)
            droop(d, qx, qy, -side, 3.4 * S, (240, 216, 150))
    # vermilion wells under the controls, ringed in gold
    dx, dz = PAD_LAYOUT["dpad"]
    ring(dx, dz, 0.0175, fill=SHU_RGB, outline=GOLD_RGB, width=S)
    ax_, az_ = PAD_LAYOUT["abxy"]
    ring(ax_, az_, 0.0205, fill=SHU_RGB, outline=GOLD_RGB, width=S)
    sx, sz = PAD_LAYOUT["stick"]
    ring(sx, sz, 0.0150, fill=(18, 12, 14), outline=GOLD_RGB, width=S)
    ring(sx, sz, 0.0125, outline=GOLD_DIM, width=S // 2)
    # select / start labels as small gold ticks
    for key in ("select", "start"):
        kx, kz = PAD_LAYOUT[key]
        ring(kx, kz, 0.0060, outline=GOLD_DIM, width=S // 2)
    # the logo at the top centre
    lx, lz = PAD_LAYOUT["logo"]
    cx, cy = P(lx - 0.0125, lz)
    draw_mei(d, cx, cy, int(6.5 * S), word_size=int(5.5 * S), gap=1.5 * S)
    return down(im, w, h)


def build_sheet():
    cells = [
        ("card", draw_card()),
        ("padtop", draw_padtop()),
        ("side", draw_side()),
        ("logo", draw_logo()),
        ("gloss", draw_gloss(128, 96, 12)),
        ("label", draw_label()),
        ("geese", draw_geese()),
        ("back", draw_back()),
        ("port", draw_port()),
        ("mcslot", draw_mcslot()),
        ("btn_a", draw_letter("A")),
        ("btn_b", draw_letter("B")),
        ("btn_x", draw_letter("X")),
        ("btn_y", draw_letter("Y")),
    ]
    # simple shelf packing
    W = 256
    x = y = shelf = 0
    for name, im in cells:
        w, h = im.size
        if x + w > W:
            x, y, shelf = 0, y + shelf, 0
        CELLS[name] = (x, y, w, h)
        x += w
        shelf = max(shelf, h)
    H = y + shelf
    sheet = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for name, im in cells:
        x, y, w, h = CELLS[name]
        sheet.paste(im.convert("RGBA"), (x, y))
    os.makedirs(ART, exist_ok=True)
    sheet.save(os.path.join(ART, "moon_lacquer.png"))
    with open(os.path.join(ART, "moon_lacquer.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1,
                   "cells": {k: list(v) for k, v in CELLS.items()}}, f, indent=1)
        f.write("\n")


# ---------------------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------------------
def sub(a, b): return [a[i] - b[i] for i in range(3)]
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
def dot(a, b): return sum(a[i] * b[i] for i in range(3))


class Mesh:
    def __init__(self):
        self.v, self.f, self.fm, self.key = [], [], [], {}

    def vert(self, p):
        p = tuple(r5(p))
        if p not in self.key:
            self.key[p] = len(self.v)
            self.v.append(list(p))
        return self.key[p]

    def poly(self, pts, mat, outward):
        """Add a polygon, turned so its normal points along `outward`."""
        idx = [self.vert(p) for p in pts]
        P = [self.v[i] for i in idx]
        n = [0.0, 0.0, 0.0]
        for i in range(len(P)):
            a, b = P[i], P[(i + 1) % len(P)]
            n[0] += (a[1] - b[1]) * (a[2] + b[2])
            n[1] += (a[2] - b[2]) * (a[0] + b[0])
            n[2] += (a[0] - b[0]) * (a[1] + b[1])
        # Newell's normal is for counter-clockwise; the kit wants (b-a)x(c-a) outward
        nn = cross(sub(P[1], P[0]), sub(P[2], P[0]))
        if abs(dot(nn, nn)) < 1e-20:
            nn = n
        if dot(nn, outward) < 0:
            idx.reverse()
        self.f.append(idx)
        self.fm.append(mat)

    def node(self, id, transform=None):
        n = {"id": id, "op": "mesh", "vertices": self.v, "faces": self.f}
        mats = set(self.fm)
        if len(mats) == 1:
            n["material"] = self.fm[0]
        else:
            n["face_materials"] = self.fm
        if transform:
            n["transform"] = transform
        return n


def plate(id, c, size, face, mats, transform=None):
    """A box whose `face` side ('-z', '+z', '+y', '-x', '+x') takes mats['face'] and the
    others mats['side']; the side opposite `face` is left open (it is buried)."""
    m = Mesh()
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    cx, cy, cz = c

    def P(sx, sy, sz):
        return [cx + sx * hx, cy + sy * hy, cz + sz * hz]
    sides = {
        "+x": ([P(1, -1, -1), P(1, 1, -1), P(1, 1, 1), P(1, -1, 1)], [1, 0, 0]),
        "-x": ([P(-1, -1, -1), P(-1, 1, -1), P(-1, 1, 1), P(-1, -1, 1)], [-1, 0, 0]),
        "+y": ([P(-1, 1, -1), P(1, 1, -1), P(1, 1, 1), P(-1, 1, 1)], [0, 1, 0]),
        "-y": ([P(-1, -1, -1), P(1, -1, -1), P(1, -1, 1), P(-1, -1, 1)], [0, -1, 0]),
        "+z": ([P(-1, -1, 1), P(1, -1, 1), P(1, 1, 1), P(-1, 1, 1)], [0, 0, 1]),
        "-z": ([P(-1, -1, -1), P(1, -1, -1), P(1, 1, -1), P(-1, 1, -1)], [0, 0, -1]),
    }
    opp = {"+x": "-x", "-x": "+x", "+y": "-y", "-y": "+y", "+z": "-z", "-z": "+z"}[face]
    for k, (pts, n) in sides.items():
        if k == opp:
            continue
        m.poly(pts, mats["face"] if k == face else mats["side"], n)
    return m.node(id, transform)


def rrect(w, d, r, n=4):
    """Rounded rectangle in (x, z), n segments a corner, counter-clockwise from +x."""
    pts = []
    for (sx, sz, a0) in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        cx, cz = sx * (w / 2 - r), sz * (d / 2 - r)
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append([round(cx + r * math.cos(a), 5), round(cz + r * math.sin(a), 5)])
    return pts


def loft(id, sections, mat, caps=True):
    return {"id": id, "op": "loft", "material": mat, "caps": caps,
            "sections": [{"y": round(y, 5), "points": pts} for (y, pts) in sections]}


def cyl(id, r, h, c, mat, seg=12, caps=True, rotate=None):
    t = {"translate": r5(c)}
    if rotate:
        t["rotate"] = rotate
    return {"id": id, "op": "cylinder", "radius": r, "height": h, "segments": seg, "caps": caps,
            "material": mat, "transform": t}


def tex(cell, bits=8, projection="fit", **kw):
    t = {"sheet": "art", "cell": cell, "bits": bits, "projection": projection}
    t.update(kw)
    return t


VERIFY = {"required": True, "depth": True, "perspective": True}
LIGHT = {"direction": [-0.45, 0.85, -0.4], "ambient": 0.42}


# ---------------------------------------------------------------------------------------
# Console: a lacquered box (W 300 x D 220 x H 70 mm), lid with the moon card
# ---------------------------------------------------------------------------------------
CW, CD, CR = 0.300, 0.220, 0.016
SEAM_Y0, SEAM_Y1 = 0.046, 0.0495
LID_FULL, LID_MID, LID_TOP = 0.060, 0.066, 0.070
TOP_INSET = 0.011


def corner_fitting():
    """Gold kanagu wrapping the lid's front-right corner, 0.8 mm proud of the lacquer."""
    m = Mesh()
    e, t = 0.0008, 0.0025
    L = 0.014
    y0, y1 = 0.0515, 0.0622
    cx, cz = CW / 2 - CR, -(CD / 2 - CR)
    n = 5
    outer, inner = [], []
    # along the front face toward the corner
    outer.append((cx - L, -(CD / 2) - e))
    inner.append((cx - L, -(CD / 2) + t))
    for i in range(n + 1):
        a = math.radians(270 + 90 * i / n)
        outer.append((cx + (CR + e) * math.cos(a), cz + (CR + e) * math.sin(a)))
        inner.append((cx + (CR - t) * math.cos(a), cz + (CR - t) * math.sin(a)))
    outer.append((CW / 2 + e, cz + L))
    inner.append((CW / 2 - t, cz + L))
    for i in range(len(outer) - 1):
        a, b = outer[i], outer[i + 1]
        ai, bi = inner[i], inner[i + 1]
        mid = ((a[0] + b[0]) / 2 - cx, 0, (a[1] + b[1]) / 2 - cz)
        m.poly([[a[0], y0, a[1]], [b[0], y0, b[1]], [b[0], y1, b[1]], [a[0], y1, a[1]]], "gold", list(mid))
        m.poly([[a[0], y1, a[1]], [b[0], y1, b[1]], [bi[0], y1, bi[1]], [ai[0], y1, ai[1]]], "gold", [0, 1, 0])
        m.poly([[a[0], y0, a[1]], [b[0], y0, b[1]], [bi[0], y0, bi[1]], [ai[0], y0, ai[1]]], "gold", [0, -1, 0])
    a, ai = outer[0], inner[0]
    m.poly([[a[0], y0, a[1]], [ai[0], y0, ai[1]], [ai[0], y1, ai[1]], [a[0], y1, a[1]]], "gold", [-1, 0, 0])
    a, ai = outer[-1], inner[-1]
    m.poly([[a[0], y0, a[1]], [ai[0], y0, ai[1]], [ai[0], y1, ai[1]], [a[0], y1, a[1]]], "gold", [0, 0, 1])
    node = m.node("fitting")
    return {"id": "fittings", "op": "group", "children": [node],
            "modifiers": [{"op": "mirror", "axis": "x"}, {"op": "mirror", "axis": "z"}]}


def slot_collar(cx, cz, ow, od, iw, idp, y0, y1, yf):
    """The cart slot: a vermilion collar standing on the lid with a dark mouth."""
    m = Mesh()
    ox, oz, ix, iz = ow / 2, od / 2, iw / 2, idp / 2
    O = [(cx - ox, cz - oz), (cx + ox, cz - oz), (cx + ox, cz + oz), (cx - ox, cz + oz)]
    I = [(cx - ix, cz - iz), (cx + ix, cz - iz), (cx + ix, cz + iz), (cx - ix, cz + iz)]
    for i in range(4):
        a, b = O[i], O[(i + 1) % 4]
        ai, bi = I[i], I[(i + 1) % 4]
        out = [(a[0] + b[0]) / 2 - cx, 0, (a[1] + b[1]) / 2 - cz]
        m.poly([[a[0], y0, a[1]], [b[0], y0, b[1]], [b[0], y1, b[1]], [a[0], y1, a[1]]], "shu", out)
        m.poly([[a[0], y1, a[1]], [b[0], y1, b[1]], [bi[0], y1, bi[1]], [ai[0], y1, ai[1]]], "shu", [0, 1, 0])
        m.poly([[ai[0], y1, ai[1]], [bi[0], y1, bi[1]], [bi[0], yf, bi[1]], [ai[0], yf, ai[1]]], "hole",
               [-out[0], 0, -out[2]])
    m.poly([[p[0], yf, p[1]] for p in I], "hole", [0, 1, 0])
    return m.node("cart_slot")


def cartridge(cx, cz):
    """A cart standing in the slot, its label toward the front."""
    w, th, y0, y1, r = 0.100, 0.0150, 0.0660, 0.1240, 0.009
    pts = [[-w / 2, y0], [w / 2, y0]]
    for i in range(5):
        a = math.radians(0 + 90 * i / 4)
        pts.append([w / 2 - r + r * math.cos(a), y1 - r + r * math.sin(a)])
    for i in range(5):
        a = math.radians(90 + 90 * i / 4)
        pts.append([-w / 2 + r + r * math.cos(a), y1 - r + r * math.sin(a)])
    # drop duplicated corner points
    clean = []
    for p in pts:
        p = [round(p[0], 5), round(p[1], 5)]
        if not clean or clean[-1] != p:
            clean.append(p)
    if clean[0] == clean[-1]:
        clean.pop()
    shell = {"id": "cart_shell", "op": "extrude", "points": clean, "depth": th, "material": "cart",
             "transform": {"translate": [cx, 0, cz]}}
    # grip ridges on the back
    ridges = {"id": "cart_ridges", "op": "box", "size": [0.070, 0.0016, 0.0016], "material": "cart_dark",
              "transform": {"translate": [cx, 0.1150, cz + th / 2 - 0.0002]},
              "modifiers": [{"op": "array", "count": 3, "step": [0, -0.0045, 0]}]}
    label = plate("cart_label", [cx, 0.0965, cz - th / 2 + 0.0004], [0.078, 0.046, 0.0020], "-z",
                  {"face": "label", "side": "label_edge"})
    return [shell, ridges, label]


def console_recipe():
    body_outline = rrect(CW, CD, CR, 5)
    sections = [
        (0.0085, body_outline),
        (LID_FULL, body_outline),
        (LID_MID, rrect(CW - 0.008, CD - 0.008, CR - 0.003, 5)),
        (LID_TOP, rrect(CW - 2 * TOP_INSET, CD - 2 * TOP_INSET, CR - 0.008, 5)),
    ]
    nodes = []
    nodes.append(loft("plinth", [(0.0, rrect(CW - 0.014, CD - 0.014, CR - 0.007, 3)),
                                 (0.0110, rrect(CW - 0.012, CD - 0.012, CR - 0.006, 3))], "shu"))
    nodes.append(loft("body", sections, "lacquer", caps=False))
    lid = Mesh()
    lid.poly([[p[0], LID_TOP, p[1]] for p in sections[-1][1]], "lid", [0, 1, 0])
    nodes.append(lid.node("lid_top"))
    base = Mesh()
    base.poly([[p[0], sections[0][0], p[1]] for p in sections[0][1]], "lacquer", [0, -1, 0])
    nodes.append(base.node("underside"))
    nodes.append(loft("seam", [(SEAM_Y0, rrect(CW + 0.0016, CD + 0.0016, CR + 0.0008, 5)),
                               (SEAM_Y1, rrect(CW + 0.0016, CD + 0.0016, CR + 0.0008, 5))], "shu", caps=False))
    nodes.append(corner_fitting())
    # lid: the moon card inlay, and three geese in gold
    nodes.append(plate("moon_card", [0.072, LID_TOP, 0.000], [0.096, 0.0028, 0.158], "+y",
                       {"face": "card", "side": "gold"}))
    geese = Mesh()   # gold geese in flight: a cutout 1 mm above the lacquer
    gy = LID_TOP + 0.0010
    geese.poly([[-0.058, gy, -0.092], [0.014, gy, -0.092], [0.014, gy, -0.053], [-0.058, gy, -0.053]],
               "geese", [0, 1, 0])
    nodes.append(geese.node("geese"))
    # cart slot and a cart in it
    scx, scz = -0.066, 0.052
    nodes.append(slot_collar(scx, scz, 0.122, 0.032, 0.108, 0.020, LID_TOP - 0.0015, LID_TOP + 0.0075,
                             LID_TOP + 0.0016))
    nodes.extend(cartridge(scx, scz))
    # power (vermilion seal), reset (gold) and the moon lamp
    nodes.append(cyl("power_ring", 0.0105, 0.0040, [-0.106, LID_TOP + 0.0005, -0.064], "gold", 14))
    nodes.append(cyl("power", 0.0078, 0.0060, [-0.106, LID_TOP + 0.0025, -0.064], "shu", 14))
    nodes.append(cyl("reset", 0.0055, 0.0050, [-0.075, LID_TOP + 0.0010, -0.064], "gold", 12))
    nodes.append(cyl("lamp", 0.0028, 0.0024, [-0.128, LID_TOP + 0.0002, -0.064], "moonlamp", 8))
    # front: two controller ports, the maker's plate, two memory card slots
    fz = -CD / 2
    for i, x in enumerate((-0.113, -0.081)):
        nodes.append(plate(f"port_{i + 1}", [x, 0.0270, fz - 0.0003], [0.026, 0.018, 0.0050], "-z",
                           {"face": "port", "side": "shu"}))
    nodes.append(plate("maker_plate", [0.0, 0.0285, fz - 0.0001], [0.074, 0.0205, 0.0030], "-z",
                       {"face": "logo", "side": "gold"}))
    for i, x in enumerate((0.081, 0.113)):
        nodes.append(plate(f"card_slot_{i + 1}", [x, 0.0270, fz - 0.0003], [0.028, 0.0095, 0.0050], "-z",
                           {"face": "mcslot", "side": "shu"}))
    # back: AV, MeiNet antenna and DC in
    nodes.append(plate("back_panel", [0.0, 0.0280, CD / 2 + 0.0001], [0.112, 0.021, 0.0030], "+z",
                       {"face": "back", "side": "lacquer"}))
    # sides: susuki in gold maki-e
    side_m = Mesh()  # susuki in gold maki-e: a cutout 1 mm off each side
    sx = CW / 2 + 0.0010
    side_m.poly([[sx, 0.0115, -0.086], [sx, 0.0115, 0.086], [sx, 0.0425, 0.086], [sx, 0.0425, -0.086]],
                "side", [1, 0, 0])
    side = side_m.node("side_grass")
    nodes.append({"id": "sides", "op": "group", "children": [side],
                  "modifiers": [{"op": "mirror", "axis": "x"}]})

    materials = {
        "lacquer": {"color": LACQUER},
        "shu": {"color": SHU},
        "gold": {"color": GOLD},
        "hole": {"color": HOLE},
        "cart": {"color": "#3b3335"},
        "cart_dark": {"color": "#211c1e"},
        "label_edge": {"color": "#e6decc"},
        "moonlamp": {"color": "#f6e8c0", "class": "emissive"},
        "card": {"color": "#c63a24", "texture": tex("card")},
        "geese": {"color": GOLD, "texture": tex("geese")},
        "lid": {"color": LACQUER, "texture": tex("gloss")},
        "logo": {"color": LACQUER, "texture": tex("logo")},
        "label": {"color": "#1c2448", "texture": tex("label")},
        "port": {"color": "#181214", "texture": tex("port", 4)},
        "mcslot": {"color": "#181214", "texture": tex("mcslot", 4)},
        "back": {"color": "#1e1618", "texture": tex("back", 4)},
        "side": {"color": GOLD, "texture": tex("side")},
    }
    return {
        "format": "mei-asset", "version": 1, "name": "moon_lacquer_console",
        "budget": {"vertices": 2048, "triangles": 1200},
        "sheets": {"art": {"image": "art/moon_lacquer.png"}},
        "materials": materials,
        "lighting": LIGHT,
        "verification": VERIFY,
        "nodes": nodes,
    }


# ---------------------------------------------------------------------------------------
# Controller: black lacquer top over a vermilion under-shell, the stick cap a moon
# ---------------------------------------------------------------------------------------
def ear_clip(pts):
    """Triangulate a simple polygon given as (x, z); returns index triples."""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    idx = list(range(n)) if area > 0 else list(reversed(range(n)))
    tris = []

    def inside(p, a, b, c):
        def s(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
        d1, d2, d3 = s(p, a, b), s(p, b, c), s(p, c, a)
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) <= 0:
                continue
            if any(inside(pts[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            break
    tris.append(tuple(idx))
    return tris


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def grip_drop(x, z):
    return 0.012 * smoothstep(-0.006, -0.050, z) * smoothstep(0.018, 0.048, abs(x))


def pad_shell():
    outline = pad_outline(18)
    rings = [  # (inset, y at the centre, how much of the grip drop, material of the band above)
        (0.0045, 0.0000, 1.00, "shu"),
        (0.0000, 0.0060, 0.70, "shu"),
        (0.0000, 0.0100, 0.25, "lacquer"),
        (0.0006, 0.0215, 0.00, "lacquer"),
        (PAD_INSET_TOP, PAD_TOP_Y, 0.00, None),
    ]
    ring_pts = []
    for (d, y, k, _) in rings:
        pts2 = inset(outline, d) if d else outline
        ring_pts.append([[x, y - k * grip_drop(x, z), z] for (x, z) in pts2])
    m = Mesh()
    n = len(outline)
    for r in range(len(rings) - 1):
        mat = rings[r][3]
        A, B = ring_pts[r], ring_pts[r + 1]
        for i in range(n):
            j = (i + 1) % n
            ox = (outline[i][0] + outline[j][0]) / 2
            oz = (outline[i][1] + outline[j][1]) / 2
            gx, gz = pad_grad(ox, oz)
            # two triangles: a band's quad need not be planar
            m.poly([A[i], A[j], B[j]], mat, [gx, 0.3 if r == len(rings) - 2 else 0, gz])
            m.poly([A[i], B[j], B[i]], mat, [gx, 0.3 if r == len(rings) - 2 else 0, gz])
    # bottom: non-planar (the grips hang lower), so triangles of our own
    bottom = ring_pts[0]
    for (a, b, c) in ear_clip([(p[0], p[2]) for p in bottom]):
        m.poly([bottom[a], bottom[b], bottom[c]], "shu_under", [0, -1, 0])
    shell = m.node("shell")
    # the face: triangles of our own (its back edge has collinear points), hand UVs over its
    # bounding rectangle, so the one texture spans the whole face as the art expects
    tp = ring_pts[-1]
    x0, x1, z0, z1 = pad_top_bounds()
    faces = []
    for (a, b, c) in ear_clip([(p[0], p[2]) for p in tp]):
        P = [tp[a], tp[b], tp[c]]
        nn = cross(sub(P[1], P[0]), sub(P[2], P[0]))
        faces.append([a, b, c] if nn[1] > 0 else [a, c, b])
    face = {"id": "face", "op": "mesh", "material": "padtop", "vertices": [r5(p) for p in tp],
            "faces": faces,
            "uvs": [[round((p[0] - x0) / (x1 - x0), 5), round((z1 - p[2]) / (z1 - z0), 5)] for p in tp]}
    return shell, face


def controller_recipe():
    shell, face = pad_shell()
    nodes = [shell, face]
    ty = PAD_TOP_Y
    # d-pad: a gold cross
    a, b = 0.0047, 0.0135
    cross_pts = [[-a, -b], [a, -b], [a, -a], [b, -a], [b, a], [a, a], [a, b], [-a, b], [-a, a], [-b, a],
                 [-b, -a], [-a, -a]]
    dx, dz = PAD_LAYOUT["dpad"]
    nodes.append({"id": "dpad", "op": "extrude", "points": cross_pts, "depth": 0.0050, "material": "gold",
                  "transform": {"rotate": [90, 0, 0], "translate": [dx, ty + 0.0010, dz]}})
    # A B X Y: pearl (raden) buttons with vermilion letters, SNES order
    ax, az = PAD_LAYOUT["abxy"]
    s = 0.0118
    for name, (ox, oz) in (("x", (0, s)), ("a", (s, 0)), ("b", (0, -s)), ("y", (-s, 0))):
        nodes.append(cyl(f"btn_{name}", 0.0058, 0.0060, [ax + ox, ty + 0.0010, az + oz], f"btn_{name}", 10))
    # stick: shaft and a moon cap
    sx, sz = PAD_LAYOUT["stick"]
    nodes.append(cyl("stick_shaft", 0.0036, 0.0080, [sx, ty + 0.0020, sz], "hole", 6, caps=False))
    nodes.append({"id": "stick_cap", "op": "lathe", "segments": 12, "material": "moon",
                  "profile": [[0.0098, 0.0], [0.0104, 0.0022], [0.0090, 0.0038]],
                  "transform": {"translate": [sx, ty + 0.0055, sz]}})
    # select and start: small gold pills, angled like the period's pads
    for key, ang in (("select", 25), ("start", -25)):
        kx, kz = PAD_LAYOUT[key]
        nodes.append({"id": key, "op": "box", "size": [0.0085, 0.0030, 0.0034], "material": "gold",
                      "transform": {"rotate": [0, ang, 0], "translate": [kx, ty + 0.0004, kz]}})
    # shoulder buttons L and R, gold bars along the back corners
    for name, sgn in (("l", -1), ("r", 1)):
        nodes.append({"id": f"shoulder_{name}", "op": "cylinder", "radius": 0.0052, "height": 0.026,
                      "segments": 10, "material": "gold",
                      "transform": {"scale": [1.0, 1.0, 1.25], "rotate": [0, sgn * 18, 90],
                                    "translate": [sgn * 0.044, 0.0185, 0.0285]}})
    # the cord's vermilion boot and its gold ferrule (the silk cord itself detaches)
    nodes.append(cyl("cord_boot", 0.0045, 0.014, [0.0, 0.0125, 0.0385], "shu", 8, rotate=[90, 0, 0]))
    nodes.append(cyl("cord_ferrule", 0.0032, 0.004, [0.0, 0.0125, 0.0470], "gold", 8, rotate=[90, 0, 0]))

    materials = {
        "lacquer": {"color": LACQUER},
        "shu": {"color": SHU},
        "shu_under": {"color": "#a8301e"},
        "gold": {"color": GOLD},
        "hole": {"color": HOLE},
        "moon": {"color": "#f3e9cf", "smooth": True},
        "padtop": {"color": LACQUER, "texture": tex("padtop")},
    }
    for k in "abxy":
        materials[f"btn_{k}"] = {"color": "#eee6dc", "texture": tex(f"btn_{k}", 4, "disc")}
    return {
        "format": "mei-asset", "version": 1, "name": "moon_lacquer_controller",
        "budget": {"vertices": 2048, "triangles": 800},
        "sheets": {"art": {"image": "art/moon_lacquer.png"}},
        "materials": materials,
        "lighting": LIGHT,
        "verification": VERIFY,
        "nodes": [{"id": "controller", "op": "group", "children": nodes,
                   "transform": {"translate": [0, 0.012, 0]}}],
    }


def main():
    build_sheet()
    for name, recipe in (("console", console_recipe()), ("controller", controller_recipe())):
        with open(os.path.join(HERE, f"{name}.asset.json"), "w") as f:
            json.dump(recipe, f, indent=1)
            f.write("\n")
    print("wrote art/moon_lacquer.png, console.asset.json, controller.asset.json")


if __name__ == "__main__":
    main()
