#!/usr/bin/env python3
"""Arcade Heritage: the Mei console and controller as an arcade-board maker would build them.

Writes art/arcade_sheet.png (+ .sheet.json), console.asset.json and controller.asset.json
beside this script. Needs Pillow. Units are metres, at real size; models face -Z.

    python3 make_arcade.py
"""
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
R = lambda v: round(v, 5)

# ---------------------------------------------------------------- colours
CREAM = "#f6ecd4"
CREAM_D = "#e4d6b8"
PINK = "#f2689e"
PINK_L = "#f9a3c2"
MINT = "#7fd8bd"
MINT_L = "#b4ecd9"
PLUM = "#3a2c4c"
INK = "#2a2236"
SUN = "#f5a33c"
MOON = "#a9c8f2"
LEMON = "#ffe27a"

# ---------------------------------------------------------------- pixel font (3x5, a few wider)
FONT = {
    "A": ["010", "101", "111", "101", "101"], "B": ["110", "101", "110", "101", "110"],
    "C": ["011", "100", "100", "100", "011"], "D": ["110", "101", "101", "101", "110"],
    "E": ["111", "100", "110", "100", "111"], "F": ["111", "100", "110", "100", "100"],
    "G": ["011", "100", "101", "101", "011"], "H": ["101", "101", "111", "101", "101"],
    "I": ["111", "010", "010", "010", "111"], "K": ["101", "101", "110", "101", "101"],
    "L": ["100", "100", "100", "100", "111"], "M": ["10001", "11011", "10101", "10001", "10001"],
    "N": ["1001", "1101", "1011", "1001", "1001"], "O": ["010", "101", "101", "101", "010"],
    "P": ["110", "101", "110", "100", "100"], "R": ["110", "101", "110", "101", "101"],
    "S": ["011", "100", "010", "001", "110"], "T": ["111", "010", "010", "010", "010"],
    "U": ["101", "101", "101", "101", "111"], "V": ["101", "101", "101", "101", "010"],
    "W": ["10001", "10001", "10101", "11011", "10001"], "X": ["101", "101", "010", "101", "101"],
    "Y": ["101", "101", "010", "010", "010"], "Z": ["111", "001", "010", "100", "111"],
    "0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
    "2": ["110", "001", "010", "100", "111"], "3": ["110", "001", "010", "001", "110"],
    "7": ["111", "001", "010", "010", "010"], "9": ["111", "101", "111", "001", "011"],
    "&": ["0100", "1010", "0100", "1010", "0101"], "-": ["000", "000", "111", "000", "000"],
    ".": ["0", "0", "0", "0", "1"], " ": ["00", "00", "00", "00", "00"],
    "^": ["00100", "01110", "11111", "00000", "00000"], "/": ["001", "001", "010", "100", "100"],
}


def text_width(s):
    return sum(len(FONT[c][0]) + 1 for c in s) - 1


def draw_text(d, x, y, s, fill, scale=1):
    for c in s:
        g = FONT[c]
        for j, row in enumerate(g):
            for i, b in enumerate(row):
                if b == "1":
                    d.rectangle([x + i * scale, y + j * scale, x + i * scale + scale - 1,
                                 y + j * scale + scale - 1], fill=fill)
        x += (len(g[0]) + 1) * scale


def draw_text_c(d, cx, y, s, fill, scale=1):
    draw_text(d, int(round(cx - text_width(s) * scale / 2)), y, s, fill, scale)


HIRA = "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc"
if not os.path.exists(HIRA):
    HIRA = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
AVENIR = "/System/Library/Fonts/Avenir Next.ttc"


def glyph(ch, px, path=HIRA, index=0):
    """A crisp glyph image (L mode, 0/255) of height about px."""
    ss = 8
    f = ImageFont.truetype(path, px * ss, index=index)
    box = f.getbbox(ch)
    im = Image.new("L", (box[2] - box[0] + 4 * ss, box[3] - box[1] + 4 * ss), 0)
    ImageDraw.Draw(im).text((2 * ss - box[0], 2 * ss - box[1]), ch, font=f, fill=255)
    im = im.crop(im.getbbox())
    w = max(1, round(im.width / ss))
    h = max(1, round(im.height / ss))
    return im.resize((w, h), Image.LANCZOS).point(lambda v: 255 if v > 110 else 0)


MEI_BIG = (16, [  # (x0, y0, x1, y1, part) inclusive pixel rectangles; 2-pixel strokes
    (0, 2, 5, 3, "sun"), (0, 6, 5, 7, "sun"), (0, 11, 5, 12, "sun"),
    (0, 2, 1, 12, "sun"), (4, 2, 5, 12, "sun"),
    (8, 0, 16, 1, "moon"), (8, 0, 9, 11, "moon"), (7, 12, 8, 13, "moon"), (6, 14, 7, 15, "moon"),
    (15, 0, 16, 14, "moon"), (13, 14, 14, 15, "moon"), (10, 5, 14, 6, "moon"),
    (10, 9, 14, 10, "moon")])
MEI_SMALL = (10, [  # 1-pixel strokes
    (0, 1, 3, 1, "sun"), (0, 4, 3, 4, "sun"), (0, 8, 3, 8, "sun"), (0, 1, 0, 8, "sun"),
    (3, 1, 3, 8, "sun"),
    (5, 0, 10, 0, "moon"), (5, 0, 5, 7, "moon"), (4, 8, 4, 8, "moon"), (3, 9, 3, 9, "moon"),
    (10, 0, 10, 8, "moon"), (9, 9, 9, 9, "moon"), (6, 3, 9, 3, "moon"), (6, 6, 9, 6, "moon")])


def mei_logo(height):
    """明, drawn by hand in pixels: a warm-orange 日 and a pale-blue 月, dark outline; RGBA."""
    h, rects = MEI_BIG if height >= 14 else MEI_SMALL
    w = max(r[2] for r in rects) + 1
    out = Image.new("RGBA", (w + 2, h + 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    for x0, y0, x1, y1, part in rects:
        d.rectangle([x0, y0, x1 + 2, y1 + 2], fill=(42, 34, 54, 255))
    for x0, y0, x1, y1, part in rects:
        d.rectangle([x0 + 1, y0 + 1, x1 + 1, y1 + 1], fill=SUN if part == "sun" else MOON)
    return out


def word(s, height, fill, path=AVENIR, index=8):
    """A word in Avenir Next Heavy (index 8) or another face, RGBA with outline."""
    g = glyph(s, height, path, index)
    w, h = g.size
    out = Image.new("RGBA", (w + 2, h + 2), (0, 0, 0, 0))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            out.paste((42, 34, 54, 255), (1 + dx, 1 + dy), g)
    out.paste(Image.new("RGBA", (w, h), fill), (1, 1), g)
    return out


# ---------------------------------------------------------------- the sheet
CELLS = {}
SHEET_W, SHEET_H = 256, 512
sheet = Image.new("RGBA", (SHEET_W, SHEET_H), (0, 0, 0, 0))
_cursor = [0, 0, 0]  # x, y, row height


def cell(name, w, h):
    x, y, rh = _cursor
    if x + w > SHEET_W:
        x, y, rh = 0, y + rh, 0
    CELLS[name] = [x, y, w, h]
    _cursor[:] = [x + w, y, max(rh, h)]
    im = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    return im


def put(name, im):
    x, y, w, h = CELLS[name]
    assert im.size == (w, h), (name, im.size)
    sheet.paste(im, (x, y))


# ---- console geometry shared with the art -------------------------------------------
HALF = 0.140          # body core half width (x)
PANEL_IN, PANEL_OUT = 0.138, 0.150
TM_IN, TM_OUT = 0.1415, 0.1465
Y0 = 0.010            # body bottom
KICK_Z, KICK_TOP = -0.112, 0.042
DECK_A = (-0.121, 0.057)   # deck front edge (z, y)
DECK_B = (-0.040, 0.069)   # deck back edge
MARQ_TOP = (-0.036, 0.104)
HOOD_Y = 0.118
REAR_Z = 0.114
REAR_TOP = 0.106

PROFILE = [  # (z, y), with a material for the edge that starts at each point
    ((-0.112, Y0), "kick"),
    ((-0.112, KICK_TOP), "underside"),
    ((-0.124, 0.046), "lip"),
    ((-0.124, 0.054), "lip"),
    (DECK_A, "deck"),
    (DECK_B, "marquee"),
    (MARQ_TOP, "underside"),
    ((-0.047, 0.107), "lip"),
    ((-0.047, 0.113), "body"),
    ((-0.042, HOOD_Y), "hood"),
    ((0.100, HOOD_Y), "body"),
    ((0.109, 0.1155), "body"),
    ((0.1135, 0.111), "body"),
    ((REAR_Z, REAR_TOP), "rear"),
    ((REAR_Z, Y0), "bottom"),
]

PANEL = [(-0.112, Y0), (-0.112, 0.042), (-0.124, 0.046), (-0.124, 0.056), (-0.040, 0.069),
         (-0.047, 0.112), (-0.041, 0.119), (0.100, 0.119), (0.110, 0.115), (0.114, 0.107),
         (0.114, Y0)]

# controller ports / coin door on the kickplate (x centres), deck buttons
PORT_X = 0.100
PORT_Y = 0.026
COIN_W, COIN_H = 0.092, 0.024
POWER = (0.078, 0.50, 0.0165)   # x, t along deck, bezel radius
RESET = (0.116, 0.50, 0.0135)
LEDS = [(0.042, 0.66, "led_pink"), (0.042, 0.34, "led_mint")]


def deck_point(x, t):
    z = DECK_A[0] + (DECK_B[0] - DECK_A[0]) * t
    y = DECK_A[1] + (DECK_B[1] - DECK_A[1]) * t
    return x, y, z


def deck_uv(x, t, W, H):
    return (x + HALF) / (2 * HALF) * W, (1 - t) * H


# ---- marquee: backlit, 明 MEI between sunset stripes --------------------------------
def make_marquee():
    W, H = 176, 22
    im = cell("marquee", W, H)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, H], fill="#2b2150")
    # a starfield of a few pixels
    for i in range(40):
        x = (i * 37 + 11) % W
        y = (i * 13 + 5) % H
        d.point((x, y), fill="#6f63a8" if i % 3 else "#d8d2ff")
    # sunset stripes on both ends, getting thinner toward the middle (Out-Run style)
    bands = [(PINK, 3), (PINK_L, 2), (LEMON, 2), (MINT_L, 2), (MINT, 3)]
    for side in (0, 1):
        y = 3
        for col, th in bands:
            for k in range(th):
                if side == 0:
                    d.line([(2, y + k), (50 - (y + k) * 1, y + k)], fill=col)
                else:
                    d.line([(W - 51 + (y + k) * 1, y + k), (W - 3, y + k)], fill=col)
            y += th + 1
    # frame
    d.rectangle([0, 0, W - 1, H - 1], outline=PINK)
    d.rectangle([1, 1, W - 2, H - 2], outline="#5a3e78")
    logo = mei_logo(18)
    mei = word("MEI", 15, "#ffffff")
    total = logo.width + 5 + mei.width
    x0 = (W - total) // 2
    im.alpha_composite(logo, (x0, (H - logo.height) // 2))
    im.alpha_composite(mei, (x0 + logo.width + 5, (H - mei.height) // 2 + 1))
    put("marquee", im)


# ---- control-panel overlay on the deck ---------------------------------------------
def make_deck():
    W, H = 192, 56
    im = cell("deck", W, H)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, H], fill=CREAM)
    # sweeping stripes from the lower left, arcade CPO style
    for k, (col, w) in enumerate([(PINK, 5), (CREAM, 2), (MINT, 5), (CREAM, 2), (LEMON, 2)]):
        off = sum(ww for _, ww in [(PINK, 5), (CREAM, 2), (MINT, 5), (CREAM, 2), (LEMON, 2)][:k])
        for j in range(w):
            o = off + j
            d.line([(0, 40 - o), (70, 40 - o), (118, -8 - o)], fill=col, width=1)
    # print: SUN & MOON SYSTEM, and the arcade's insert prompt
    draw_text(d, 8, 6, "SUN & MOON SYSTEM", INK)
    draw_text(d, 8, 44, "INSERT CART ^", PINK)
    # button labels and rings
    for (x, t, r), label, col in ((POWER, "POWER", PINK), (RESET, "RESET", "#39a98a")):
        u, v = deck_uv(x, t, W, H)
        rr = r / (2 * HALF) * W + 2.5
        d.ellipse([u - rr, v - rr * 1.02, u + rr, v + rr * 1.02], fill=INK)
        draw_text_c(d, u, int(v + rr + 3), label, col)
    for x, t, m in LEDS:
        u, v = deck_uv(x, t, W, H)
        d.ellipse([u - 3, v - 3, u + 3, v + 3], fill=INK)
        lab = "ON" if m == "led_pink" else "NET"
        draw_text(d, int(u - 5 - text_width(lab)), int(v - 2), lab, INK)
    put("deck", im)


# ---- kickplate: 1P / 2P printed beside the ports -----------------------------------
def make_kick():
    W, H = 176, 20
    im = cell("kick", W, H)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, H], fill=MINT)
    d.line([(0, 1), (W, 1)], fill=PINK_L)
    d.line([(0, H - 2), (W, H - 2)], fill="#5fbfa3")
    for i, sx in enumerate((-1, 1)):
        u = (sx * PORT_X + HALF) / (2 * HALF) * W
        tag = "1P" if sx < 0 else "2P"
        tx = u + (14 if sx < 0 else -14 - 2 * text_width(tag))
        draw_text(d, int(tx), 5, tag, PINK if sx < 0 else PLUM, scale=2)
    put("kick", im)


def make_port():
    W, H = 24, 12
    im = cell("port", W, H)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, H], fill="#3b3346")
    d.rounded_rectangle([2, 2, W - 3, H - 3], radius=3, fill="#18131f")
    for i in range(5):
        d.rectangle([5 + i * 3, 5, 5 + i * 3, 6], fill="#c9b27a")
    put("port", im)


def make_coindoor():
    W, H = 72, 20
    im = cell("coindoor", W, H)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, H], fill="#cfcbd6")
    d.rectangle([0, 0, W - 1, H - 1], outline="#8d889a")
    d.line([(1, 1), (W - 2, 1)], fill="#f2f0f6")
    for x, y in ((3, 3), (W - 4, 3), (3, H - 4), (W - 4, H - 4)):
        d.point((x, y), fill="#6b6678")
    draw_text_c(d, W / 2, 3, "MEMORY", INK)
    for k, (cx, lamp) in enumerate(((18, PINK), (W - 19, MINT))):
        d.rectangle([cx - 11, 10, cx + 11, 15], fill="#5c5768")
        d.rectangle([cx - 9, 12, cx + 9, 13], fill="#0e0b12")
    put("coindoor", im)


def make_rear():
    W, H = 140, 48
    im = cell("rear", W, H)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, H], fill=CREAM_D)
    # vents: the rear is seen from behind, so the console's left is texture-right
    for i in range(9):
        d.rounded_rectangle([12 + i * 6, 8, 15 + i * 6, 30], radius=1, fill="#5a4f60")
    # AV out, DC in, antenna
    d.rounded_rectangle([76, 14, 92, 22], radius=2, fill="#2a2433")
    draw_text_c(d, 84, 26, "AV", INK)
    d.ellipse([100, 13, 110, 23], fill="#2a2433")
    d.ellipse([103, 16, 107, 20], fill="#a9a2b2")
    draw_text_c(d, 105, 26, "DC", INK)
    d.ellipse([118, 13, 128, 23], fill="#c9b27a")
    d.ellipse([121, 16, 125, 20], fill="#2a2433")
    draw_text_c(d, 123, 26, "NET", INK)
    # label plate
    d.rectangle([12, 35, 128, 43], fill="#fbf6ea")
    draw_text(d, 15, 37, "MEI-001  SUN & MOON SYSTEM", INK)
    put("rear", im)


HOOD_Z0, HOOD_Z1 = -0.042, 0.100
CART_Z = 0.030


def make_hood():
    """The hood's top: speaker grilles either side of the cart slot, a pinstripe."""
    W, H = 128, 64
    im = cell("hood", W, H)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, H], fill=CREAM)
    uv = lambda x, z: ((x + HALF) / (2 * HALF) * W, (HOOD_Z1 - z) / (HOOD_Z1 - HOOD_Z0) * H)
    d.rectangle([3, 3, W - 4, H - 4], outline=PINK_L)
    for sx in (-1, 1):
        cu, cv = uv(sx * 0.100, CART_Z)
        d.ellipse([cu - 11, cv - 11, cu + 11, cv + 11], fill=CREAM_D)
        for i in range(-5, 6):
            for j in range(-5, 6):
                if i * i + j * j <= 22:
                    d.point((cu + 2 * i, cv + 2 * j), fill="#6a5a70")
    u, v = uv(0, CART_Z - 0.026)
    draw_text_c(d, u, int(v), "MEI CARTRIDGE", "#b49a8c")
    put("hood", im)


def make_side(name, mirrored):
    """Side art: candy swooshes rising from the front-bottom toward the back, the 明 near the
    back. Seen from outside, the right panel has the front on the texture's left and the left
    panel on its right, so the left panel's stripes are mirrored but its logo is not."""
    W, H = 112, 52
    im = cell(name, W, H)
    art = Image.new("RGBA", (W, H), CREAM)
    d = ImageDraw.Draw(art)
    for k, (col, w) in enumerate([(PINK, 7), (CREAM, 2), (MINT, 7), (CREAM, 2), (LEMON, 3)]):
        off = [0, 7, 9, 16, 18][k]
        for j in range(w):
            o = off + j
            pts = [(-2, H - 8 - o), (40, H - 8 - o), (W + 2, H - 40 - o)]
            d.line(pts, fill=col, width=1)
    if mirrored:
        art = art.transpose(Image.FLIP_LEFT_RIGHT)
    logo = mei_logo(14)
    art.alpha_composite(logo, (12 if mirrored else W - logo.width - 12, 8))
    im.paste(art, (0, 0))
    put(name, im)


def make_cart_label():
    W, H = 48, 22
    im = cell("cart_label", W, H)
    d = ImageDraw.Draw(im)
    for y in range(H):  # sky gradient pink to lemon
        t = y / (H - 1)
        c = tuple(int(a + (b - a) * t) for a, b in ((0x5c, 0xf9), (0x3a, 0xa3), (0x9a, 0xc2)))
        d.line([(0, y), (W, y)], fill=c)
    d.ellipse([28, 9, 40, 21], fill=SUN)
    d.polygon([(0, H), (14, 12), (26, H)], fill="#3a2c4c")
    d.polygon([(12, H), (30, 14), (48, H)], fill="#55406e")
    draw_text(d, 3, 3, "STAR", "#ffffff")
    draw_text(d, 3, 9, "RALLY", LEMON)
    d.rectangle([0, 0, W - 1, H - 1], outline="#ffffff")
    put("cart_label", im)


# ---- controller art ----------------------------------------------------------------
def make_start(name, label, bg, fg):
    W, H = 28, 11
    im = cell(name, W, H)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, H], fill=bg)
    d.rectangle([0, 0, W - 1, H - 1], outline="#ffffff")
    draw_text_c(d, W / 2, 3, label, fg)
    put(name, im)


def make_pad_badge():
    W, H = 44, 14
    im = cell("pad_badge", W, H)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, H], fill=CREAM)
    logo = mei_logo(11)
    mei = word("MEI", 9, "#ffffff")
    total = logo.width + 2 + mei.width
    x0 = (W - total) // 2
    im.alpha_composite(logo, (x0, (H - logo.height) // 2))
    im.alpha_composite(mei, (x0 + logo.width + 2, (H - mei.height) // 2))
    put("pad_badge", im)


PLATE_ART = {}  # filled by the controller builder: letter positions in texels


def make_plate(size, letters):
    W, H = size
    im = cell("plate", W, H)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, H], fill=PLUM)
    for (u, v, r, ch) in letters:
        d.ellipse([u - r, v - r, u + r, v + r], fill="#241a30")
    uc = sum(l[0] for l in letters) / len(letters)
    vc = sum(l[1] for l in letters) / len(letters)
    for (u, v, r, ch) in letters:
        du, dv = u - uc, v - vc
        L = math.hypot(du, dv)
        tu = u + du / L * (r + 3) - 1
        tv = v + dv / L * (r + 3) - 2
        tu = min(max(tu, 2), W - 5)
        tv = min(max(tv, 2), H - 7)
        draw_text(d, int(round(tu)), int(round(tv)), ch, LEMON)
    put("plate", im)


# ---------------------------------------------------------------- mesh helpers
def newell(pts):
    nx = ny = nz = 0.0
    for i in range(len(pts)):
        x1, y1, z1 = pts[i]
        x2, y2, z2 = pts[(i + 1) % len(pts)]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return nx, ny, nz


def orient(face, verts, want):
    n = newell([verts[i] for i in face])
    if n[0] * want[0] + n[1] * want[1] + n[2] * want[2] < 0:
        face = list(reversed(face))
    return face


def mesh_node(id_, verts, faces, mats):
    return {"id": id_, "op": "mesh", "vertices": [[R(c) for c in v] for v in verts],
            "faces": faces, "face_materials": mats}


def signed_area(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0]
               * poly[i][1] for i in range(len(poly))) / 2


def prism_x(id_, prof, x0, x1, edge_mats, cap_neg, cap_pos):
    """A prism of a (z, y) profile between x0 and x1; one material per edge, per cap."""
    n = len(prof)
    verts = [(x0, y, z) for z, y in prof] + [(x1, y, z) for z, y in prof]
    ccw = signed_area(prof) > 0
    faces, mats = [], []
    for i in range(n):
        j = (i + 1) % n
        dz, dy = prof[j][0] - prof[i][0], prof[j][1] - prof[i][1]
        out = (dy, -dz) if ccw else (-dy, dz)   # outward in (z, y)
        faces.append(orient([i, j, n + j, n + i], verts, (0, out[1], out[0])))
        mats.append(edge_mats[i])
    faces.append(orient(list(range(n)), verts, (-1, 0, 0)))
    mats.append(cap_neg)
    faces.append(orient(list(range(n, 2 * n)), verts, (1, 0, 0)))
    mats.append(cap_pos)
    return mesh_node(id_, verts, faces, mats)


def prism_y(id_, poly, y0, y1, side, top, bottom=None):
    """A prism of an (x, z) polygon between heights y0 and y1."""
    n = len(poly)
    verts = [(x, y0, z) for x, z in poly] + [(x, y1, z) for x, z in poly]
    ccw = signed_area(poly) > 0
    faces, mats = [], []
    for i in range(n):
        j = (i + 1) % n
        dx, dz = poly[j][0] - poly[i][0], poly[j][1] - poly[i][1]
        out = (dz, -dx) if ccw else (-dz, dx)
        faces.append(orient([i, j, n + j, n + i], verts, (out[0], 0, out[1])))
        mats.append(side)
    faces.append(orient(list(range(n, 2 * n)), verts, (0, 1, 0)))
    mats.append(top)
    if bottom:
        faces.append(orient(list(range(n)), verts, (0, -1, 0)))
        mats.append(bottom)
    return mesh_node(id_, verts, faces, mats)


def box_mesh(id_, c, s, mats, skip=()):
    """Box centred at c with size s; mats per side name (back = -Z, the model's front)."""
    hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
    verts = [(c[0] + sx * hx, c[1] + sy * hy, c[2] + sz * hz)
             for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    idx = lambda sx, sy, sz: ((sx > 0) * 4 + (sy > 0) * 2 + (sz > 0))
    sides = {
        "left": ((-1, 0, 0), [idx(-1, -1, -1), idx(-1, 1, -1), idx(-1, 1, 1), idx(-1, -1, 1)]),
        "right": ((1, 0, 0), [idx(1, -1, -1), idx(1, 1, -1), idx(1, 1, 1), idx(1, -1, 1)]),
        "bottom": ((0, -1, 0), [idx(-1, -1, -1), idx(1, -1, -1), idx(1, -1, 1), idx(-1, -1, 1)]),
        "top": ((0, 1, 0), [idx(-1, 1, -1), idx(1, 1, -1), idx(1, 1, 1), idx(-1, 1, 1)]),
        "back": ((0, 0, -1), [idx(-1, -1, -1), idx(1, -1, -1), idx(1, 1, -1), idx(-1, 1, -1)]),
        "front": ((0, 0, 1), [idx(-1, -1, 1), idx(1, -1, 1), idx(1, 1, 1), idx(-1, 1, 1)]),
    }
    faces, fm = [], []
    used = sorted({i for k, (_, f) in sides.items() if k not in skip for i in f})
    remap = {v: i for i, v in enumerate(used)}
    for k, (want, f) in sides.items():
        if k in skip:
            continue
        faces.append([remap[i] for i in orient(f, verts, want)])
        fm.append(mats.get(k, mats.get("*")))
    return mesh_node(id_, [verts[i] for i in used], faces, fm)


def offset_poly(poly, d):
    """Miter offset of a simple polygon outward by d."""
    n = len(poly)
    ccw = signed_area(poly) > 0
    out = []
    for i in range(n):
        p0, p1, p2 = poly[i - 1], poly[i], poly[(i + 1) % n]
        def nrm(a, b):
            ex, ey = b[0] - a[0], b[1] - a[1]
            L = math.hypot(ex, ey)
            return ((ey / L, -ex / L) if ccw else (-ey / L, ex / L))
        n1, n2 = nrm(p0, p1), nrm(p1, p2)
        bx, by = n1[0] + n2[0], n1[1] + n2[1]
        bl = math.hypot(bx, by)
        bx, by = bx / bl, by / bl
        cosh = bx * n1[0] + by * n1[1]
        k = d / max(cosh, 0.35)
        out.append((p1[0] + bx * k, p1[1] + by * k))
    return out


def lathe_node(id_, profile, mat, pos, rot=(0, 0, 0), segments=12, caps=True):
    node = {"id": id_, "op": "lathe", "profile": [[R(r), R(y)] for r, y in profile],
            "segments": segments, "caps": caps, "material": mat,
            "transform": {"translate": [R(c) for c in pos]}}
    if any(rot):
        node["transform"]["rotate"] = list(rot)
    return node


def cyl(id_, r, h, mat, pos, rot=(0, 0, 0), segments=10, caps=True):
    node = {"id": id_, "op": "cylinder", "radius": R(r), "height": R(h), "segments": segments,
            "material": mat, "transform": {"translate": [R(c) for c in pos]}}
    if not caps:
        node["caps"] = False
    if any(rot):
        node["transform"]["rotate"] = list(rot)
    return node


def arcade_button(id_, r, mat, pos, rot, segments=12, sink=0.0015, small=False):
    """A Sanwa-style arcade button: bezel ring and a domed plunger, one lathe."""
    if small:   # controller size: bezel, shoulder, dome
        prof = [(r, -sink), (r, 0.0026), (r * 0.74, 0.0044), (0.0, 0.0072)]
        return lathe_node(id_, prof, mat, pos, rot, segments, caps=False)
    prof = [(r, -sink), (r, 0.0028), (r * 0.93, 0.0042), (r * 0.80, 0.0047),
            (r * 0.74, 0.0062), (r * 0.62, 0.0084), (r * 0.36, 0.0094), (0.0, 0.0097)]
    return lathe_node(id_, prof, mat, pos, rot, segments)


def fit(cellname, emissive=False, color="#ffffff", bits=8, flip=None):
    tex = {"sheet": "arcade", "cell": cellname, "projection": "fit", "bits": bits}
    if flip:
        tex["flip"] = flip
    m = {"color": color, "texture": tex}
    if emissive:
        m["class"] = "emissive"
    return m


VERIFY = {"required": True, "depth": True, "perspective": True}


# ---------------------------------------------------------------- console
def console():
    deck_slope = math.degrees(math.atan2(DECK_B[1] - DECK_A[1], DECK_B[0] - DECK_A[0]))
    nodes = []
    prof = [p for p, _ in PROFILE]
    nodes.append(prism_x("body", prof, -HALF, HALF, [m for _, m in PROFILE], "body", "body"))

    # side panels with candy side art, and their pink T-molding
    panel = offset_poly(PANEL, 0.0015)
    tmold = offset_poly(PANEL, 0.0042)
    for side, sx in (("l", -1), ("r", 1)):
        xs = sorted((sx * PANEL_IN, sx * PANEL_OUT))
        cap_neg = "side_l" if sx < 0 else "body"
        cap_pos = "side_r" if sx > 0 else "body"
        nodes.append(prism_x("panel_" + side, panel, xs[0], xs[1], ["panel_edge"] * len(panel),
                             cap_neg, cap_pos))
        xt = sorted((sx * TM_IN, sx * TM_OUT))
        nodes.append(prism_x("tmold_" + side, tmold, xt[0], xt[1], ["tmold"] * len(tmold),
                             "tmold", "tmold"))

    # arcade buttons on the deck: power (30 mm, pink) and reset (24 mm, mint)
    for name, (x, t, r), mat in (("power", POWER, "btn_pink"), ("reset", RESET, "btn_mint")):
        nodes.append(arcade_button(name, r, mat, deck_point(x, t), (-deck_slope, 0, 0),
                                   segments=14 if name == "power" else 12))
    for i, (x, t, mat) in enumerate(LEDS):
        nodes.append(cyl("led_%d" % i, 0.0026, 0.004, mat, deck_point(x, t),
                         (-deck_slope, 0, 0), segments=8))

    # controller ports: cream bezels with dark sockets, 1P left and 2P right
    for side, sx in (("1p", -1), ("2p", 1)):
        x = sx * PORT_X
        nodes.append(box_mesh("port_bezel_" + side, (x, PORT_Y, KICK_Z + 0.002),
                              (0.032, 0.020, 0.0076), {"*": "bezel"}, skip=("front",)))
        nodes.append(box_mesh("port_" + side, (x, PORT_Y, KICK_Z - 0.001),
                              (0.023, 0.0115, 0.0064), {"*": "socket", "back": "port"},
                              skip=("front",)))

    # the coin door: memory card slots behind a coin-door plate
    nodes.append(box_mesh("coin_door", (0, PORT_Y, KICK_Z + 0.0005), (COIN_W, COIN_H, 0.004),
                          {"*": "chrome", "back": "coindoor"}, skip=("front",)))
    for side, sx, lamp in (("1", -1, "led_pink"), ("2", 1, "led_mint")):
        x = sx * (COIN_W / 2 - 18.5 / 72 * COIN_W)
        nodes.append(box_mesh("lamp_" + side, (x + sx * 0.0, PORT_Y + 0.0072, KICK_Z - 0.0012),
                              (0.004, 0.0025, 0.0024), {"*": lamp}, skip=("front",)))

    # the cart slot: a pink frame on the hood, the slot's dark mouth, a cart standing in it
    cz = CART_Z
    fy = HOOD_Y + 0.0012
    ow, od, iw, idp, fh = 0.124, 0.036, 0.106, 0.022, 0.0056
    sw = (ow - iw) / 2 - 0.0012
    rails = [((0, fy, cz - (od + idp) / 4), (ow, fh, (od - idp) / 2)),
             ((0, fy, cz + (od + idp) / 4), (ow, fh, (od - idp) / 2)),
             (-(iw / 2 + sw / 2), fy, cz), ((iw / 2 + sw / 2), fy, cz)]
    rails = rails[:2] + [((c[0], c[1] - 0.0002, c[2]), (sw, fh - 0.0004, idp + 0.0004))
                         for c in rails[2:]]
    for i, (c, s) in enumerate(rails):
        nodes.append(box_mesh("slot_frame_%d" % i, c, s, {"*": "slot_frame"}, skip=("bottom",)))
    nodes.append(box_mesh("slot_mouth", (0, HOOD_Y + 0.0006, cz), (iw + 0.001, 0.003, idp + 0.001),
                          {"*": "slot_dark"}, skip=("bottom",)))
    cart_w, cart_h, cart_d = 0.100, 0.076, 0.017
    cart_top = HOOD_Y + 0.040
    cart = {"id": "cart", "op": "group", "children": [
        box_mesh("cart_shell", (0, cart_top - cart_h / 2, cz), (cart_w, cart_h, cart_d),
                 {"*": "cart", "top": "cart_top"}, skip=("bottom",)),
        box_mesh("cart_label", (0, cart_top - 0.020, cz - cart_d / 2 - 0.0004),
                 (0.082, 0.032, 0.002), {"*": "cart", "back": "cart_label"},
                 skip=("front", "bottom")),
        box_mesh("cart_grip", (0, cart_top + 0.0015, cz), (cart_w - 0.016, 0.004, cart_d - 0.004),
                 {"*": "cart_top"}, skip=("bottom",)),
    ]}
    nodes.append(cart)

    # feet
    for i, (fx, fz) in enumerate(((-0.112, -0.090), (0.112, -0.090), (-0.112, 0.092),
                                  (0.112, 0.092))):
        nodes.append(cyl("foot_%d" % i, 0.010, 0.0115, "foot", (fx, 0.00575, fz), segments=8))

    mats = {
        "body": {"color": CREAM},
        "underside": {"color": CREAM_D},
        "hood": fit("hood", color=CREAM, bits=4),
        "bottom": {"color": "#bfb39a"},
        "lip": {"color": PINK},
        "panel_edge": {"color": CREAM},
        "tmold": {"color": PINK},
        "kick": fit("kick", color=MINT),
        "deck": fit("deck", color=CREAM),
        "marquee": fit("marquee", emissive=True, color="#2b2150"),
        "rear": fit("rear", color=CREAM_D, bits=4),
        "side_r": fit("side", color=CREAM),
        "side_l": fit("side_l", color=CREAM),
        "btn_pink": {"color": PINK, "smooth": True},
        "btn_mint": {"color": MINT, "smooth": True},
        "led_pink": {"color": "#ff4f8b", "class": "emissive"},
        "led_mint": {"color": "#5dffc8", "class": "emissive"},
        "bezel": {"color": "#fbf4e2"},
        "socket": {"color": "#2a2433"},
        "port": fit("port", color="#2a2433", bits=4),
        "chrome": {"color": "#bdb8c6"},
        "coindoor": fit("coindoor", color="#cfcbd6", bits=4),
        "slot_frame": {"color": PINK},
        "slot_dark": {"color": "#1c1724"},
        "cart": {"color": "#43375a"},
        "cart_top": {"color": "#56486e"},
        "cart_label": fit("cart_label", color="#f9a3c2"),
        "foot": {"color": "#4a4050"},
    }
    return {
        "format": "mei-asset", "version": 1, "name": "arcade_heritage_console",
        "budget": {"vertices": 1100, "triangles": 1000},
        "sheets": {"arcade": {"image": "art/arcade_sheet.png"}},
        "materials": mats,
        "lighting": {"direction": [-0.45, 0.85, -0.4], "ambient": 0.55},
        "verification": VERIFY,
        "nodes": nodes,
    }


# ---------------------------------------------------------------- controller
def smin(a, b, k):
    h = max(k - abs(a - b), 0.0) / k
    return min(a, b) - h * h * k * 0.25


def pad_sdf(x, z):
    # rounded-rect bar plus two grip circles, blended
    a, b, p = 0.0635, 0.0255, 4.0
    bar = ((abs(x / a) ** p + abs((z - 0.012) / b) ** p) ** (1 / p) - 1) * b
    g = min(math.hypot(x - 0.047, z + 0.016), math.hypot(x + 0.047, z + 0.016)) - 0.0305
    return smin(bar, g, 0.022)


def pad_grad(x, z, e=1e-6):
    gx = (pad_sdf(x + e, z) - pad_sdf(x - e, z)) / (2 * e)
    gz = (pad_sdf(x, z + e) - pad_sdf(x, z - e)) / (2 * e)
    return gx, gz


def pad_project(x, z, level=0.0):
    for _ in range(8):
        d = pad_sdf(x, z) - level
        gx, gz = pad_grad(x, z)
        g2 = gx * gx + gz * gz
        x, z = x - d * gx / g2, z - d * gz / g2
    return x, z


def pad_normal(x, z):
    gx, gz = pad_grad(x, z)
    L = math.hypot(gx, gz)
    return gx / L, gz / L


def pad_outline(n):
    """The outline traced along the zero contour (counterclockwise in x, z), resampled to n
    points evenly spaced by arc length, starting on +X."""
    x, z = pad_project(0.07, 0.004)
    start = (x, z)
    pts = [start]
    h = 0.0004
    while True:
        nx, nz = pad_normal(x, z)
        x, z = pad_project(x - nz * h, z + nx * h)
        if len(pts) > 20 and math.hypot(x - start[0], z - start[1]) < h * 1.01:
            break
        pts.append((x, z))
        assert len(pts) < 5000
    L = [0.0]
    for i in range(1, len(pts) + 1):
        a, b = pts[i - 1], pts[i % len(pts)]
        L.append(L[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    out = []
    for k in range(n):
        s = L[-1] * k / n
        i = next(j for j in range(1, len(L)) if L[j] >= s)
        f = (s - L[i - 1]) / (L[i] - L[i - 1])
        a, b = pts[i - 1], pts[i % len(pts)]
        out.append(pad_project(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    return out


def inset_pt(p, inset):
    nx, nz = pad_normal(*p)
    return p[0] - nx * inset, p[1] - nz * inset


def inside(poly, x, z):
    c = False
    for i in range(len(poly)):
        (x1, z1), (x2, z2) = poly[i - 1], poly[i]
        if (z1 > z) != (z2 > z) and x < x1 + (z - z1) * (x2 - x1) / (z2 - z1):
            c = not c
    return c


def seg_dist(px, pz, a, b):
    ax, az, bx, bz = a[0], a[1], b[0], b[1]
    t = max(0, min(1, ((px - ax) * (bx - ax) + (pz - az) * (bz - az)) /
                   ((bx - ax) ** 2 + (bz - az) ** 2)))
    return math.hypot(px - ax - t * (bx - ax), pz - az - t * (bz - az))


def margin(poly, pts):
    """Smallest distance from points (all inside) to the polygon's edges; negative if outside."""
    m = 1.0
    for x, z in pts:
        d = min(seg_dist(x, z, poly[i - 1], poly[i]) for i in range(len(poly)))
        m = min(m, d if inside(poly, x, z) else -d)
    return m


def circle(c, r, n):
    return [(c[0] + r * math.cos(2 * math.pi * k / n), c[1] + r * math.sin(2 * math.pi * k / n))
            for k in range(n)]


def make_face(size, to_uv, parts):
    """The controller's face print: cream, a candy sweep, small labels."""
    W, H = size
    im = cell("face", W, H)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, H], fill=CREAM)
    sweep = [(-0.080, -0.010), (-0.032, 0.004), (0.000, 0.024), (0.030, 0.034), (0.080, 0.037)]
    for k, (col, w) in enumerate([(LEMON, 2), (CREAM, 1), (MINT, 3), (CREAM, 1), (PINK, 3)]):
        off = [0, 2, 3, 6, 7][k]
        for j in range(w):
            pts = [to_uv(x, z) for x, z in sweep]
            pts = [(u, v + off + j) for u, v in pts]
            d.line(pts, fill=col, width=1)
    for (x, z, r) in parts:   # shadows around raised parts
        u, v = to_uv(x, z)
        rr = r / 0.0011
        d.ellipse([u - rr, v - rr, u + rr, v + rr], fill=CREAM_D)
    put("face", im)


def controller():
    N = 28
    base = pad_outline(N)
    T = 0.026    # body thickness
    # rings of the shell: (height, inset, material of the band above it); a pink band round the
    # widest part echoes the console's T-molding
    sections = [(0.000, 0.0060, "shell"), (0.0045, 0.0012, "shell"), (0.0110, 0.0, "tmold"),
                (0.0150, 0.0, "shell"), (0.0225, 0.0016, "shell"), (T, 0.0062, None)]
    rings = [[inset_pt(p, inset) for p in base] for _, inset, _ in sections]
    verts = [(x, y, z) for (y, _, _), ring in zip(sections, rings) for x, z in ring]
    ccw = signed_area(base) > 0
    faces, fmats = [], []
    for k in range(len(sections) - 1):
        for i in range(N):
            j = (i + 1) % N
            dx, dz = base[j][0] - base[i][0], base[j][1] - base[i][1]
            out = (dz, 0, -dx) if ccw else (-dz, 0, dx)
            q = orient([k * N + i, k * N + j, (k + 1) * N + j, (k + 1) * N + i], verts, out)
            faces += [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
            fmats += [sections[k][2]] * 2
    last = (len(sections) - 1) * N
    faces.append(orient(list(range(last, last + N)), verts, (0, 1, 0)))
    fmats.append("face")
    faces.append(orient(list(range(N)), verts, (0, -1, 0)))
    fmats.append("shell")
    nodes = [mesh_node("shell", verts, faces, fmats)]
    top = rings[-1]
    top_y = T
    minx, maxx = min(p[0] for p in top), max(p[0] for p in top)
    minz, maxz = min(p[1] for p in top), max(p[1] for p in top)
    FW = 128
    FH = int(round(FW * (maxz - minz) / (maxx - minx)))
    to_uv = lambda x, z: ((x - minx) / (maxx - minx) * FW, (maxz - z) / (maxz - minz) * FH)

    # d-pad on a pink disc
    DP = (-0.049, 0.005)
    disc = circle(DP, 0.0152, 12)
    nodes.append(prism_y("dpad_plate", disc, top_y - 0.002, top_y + 0.0012, "plate_pink",
                         "plate_pink"))
    a, b = 0.0041, 0.0122
    cross = [(-a, -b), (a, -b), (a, -a), (b, -a), (b, a), (a, a), (a, b), (-a, b), (-a, a),
             (-b, a), (-b, -a), (-a, -a)]
    cross = [(DP[0] + x, DP[1] + z) for x, z in cross]
    nodes.append(prism_y("dpad", cross, top_y, top_y + 0.0055, "dpad", "dpad"))

    # the analog stick: a mini ball-top lever, as on a cabinet
    ST = (-0.025, -0.009)
    nodes.append(lathe_node("stick_washer", [(0.0100, -0.0015), (0.0100, 0.0012), (0.0, 0.0024)],
                            "plate_pink", (ST[0], top_y, ST[1]), segments=10, caps=False))
    nodes.append(cyl("stick_shaft", 0.0022, 0.016, "steel", (ST[0], top_y + 0.009, ST[1]),
                     segments=6, caps=False))
    nodes.append({"id": "stick_ball", "op": "sphere", "radius": 0.0085, "rings": 4,
                  "segments": 8, "material": "ball",
                  "transform": {"translate": [ST[0], R(top_y + 0.0215), ST[1]]}})

    # face buttons: two staggered rows, arcade style, on a plum plate
    BTN = {"A": (0.0255, -0.0095, "btn_pink"), "B": (0.0475, -0.0045, "btn_mint"),
           "X": (0.0295, 0.0125, "btn_mint"), "Y": (0.0515, 0.0170, "btn_pink")}
    br = 0.0090
    cxs = [v[0] for v in BTN.values()]
    czs = [v[1] for v in BTN.values()]
    pc = (sum(cxs) / 4, sum(czs) / 4)
    rot = math.atan2(0.006, 0.022)
    hw, hd = 0.0235, 0.0210
    hull = []
    for k in range(16):
        c, s_ = math.cos(2 * math.pi * (k + 0.5) / 16), math.sin(2 * math.pi * (k + 0.5) / 16)
        ex = hw * math.copysign(abs(c) ** 0.55, c)
        ez = hd * math.copysign(abs(s_) ** 0.55, s_)
        hull.append((pc[0] + ex * math.cos(rot) - ez * math.sin(rot),
                     pc[1] + ex * math.sin(rot) + ez * math.cos(rot)))
    nodes.append(prism_y("button_plate", hull, top_y - 0.002, top_y + 0.0012, "plate_side",
                         "plate"))
    plate_top = top_y + 0.0012
    pminx, pmaxx = min(p[0] for p in hull), max(p[0] for p in hull)
    pminz, pmaxz = min(p[1] for p in hull), max(p[1] for p in hull)
    PW, PH = 56, 50
    letters = []
    for ch, (x, z, m) in BTN.items():
        u = (x - pminx) / (pmaxx - pminx) * PW
        v = (pmaxz - z) / (pmaxz - pminz) * PH
        letters.append((u, v, (br + 0.0012) / (pmaxx - pminx) * PW, ch))
        nodes.append(arcade_button("btn_" + ch.lower(), br, m, (x, plate_top, z), (0, 0, 0),
                                   segments=10, small=True))
    make_plate((PW, PH), letters)

    # start and select: lit rectangular buttons, like a cabinet's 1P / 2P start
    for name, x in (("select", -0.0105), ("start", 0.0105)):
        nodes.append(box_mesh(name, (x, top_y + 0.0008, 0.002), (0.016, 0.0040, 0.0068),
                              {"*": name + "_side", "top": name}, skip=("bottom",)))
    nodes.append(box_mesh("badge", (-0.001, top_y + 0.0001, 0.019), (0.028, 0.0016, 0.0095),
                          {"*": "shell", "top": "badge"}, skip=("bottom",)))

    # how far each raised part keeps inside the flat face (metres; must stay positive)
    checks = {"dpad_plate": disc, "stick_washer": circle(ST, 0.0100, 12), "button_plate": hull,
              "badge": [(-0.015, 0.0143), (0.015, 0.0143), (0.015, 0.0238), (-0.015, 0.0238)],
              "start": [(0.0025, -0.0014), (0.0185, -0.0014), (0.0185, 0.0054), (0.0025, 0.0054)]}
    for k, poly in checks.items():
        mg = margin(top, poly)
        if mg < 0.0015:
            print("controller: %s comes within %.4f m of the face's edge" % (k, mg))
    make_face((FW, FH), to_uv, [(DP[0], DP[1], 0.0162), (ST[0], ST[1], 0.0108)])

    # shoulder buttons L and R: bumpers along the back edge (the right one, mirrored for L)
    sel = sorted((p for p in base if 0.022 < p[0] < 0.070 and p[1] > 0.012), key=lambda p: p[0])
    right = [inset_pt(p, -0.0032) for p in sel] + [inset_pt(p, 0.0045) for p in sel][::-1]
    for name, sx, mat in (("l", -1, "shoulder_pink"), ("r", 1, "shoulder_mint")):
        poly = [(sx * x, z) for x, z in right]
        nodes.append(prism_y("shoulder_" + name, poly, 0.0120, 0.0205, mat, mat, mat))

    # cord: strain relief, then the cable falling away behind
    nodes.append(cyl("strain", 0.0040, 0.014, "cord", (0, 0.012, 0.0405), (90, 0, 0), segments=6))
    p0 = (0.0, 0.012, 0.046)
    L1 = 0.016
    nodes.append(cyl("cord_a", 0.0023, L1, "cord", (0, p0[1], p0[2] + L1 / 2), (90, 0, 0),
                     segments=6, caps=False))
    ang = 114
    L2 = 0.022
    dy, dz = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    c2 = (0.0, p0[1] + dy * (L2 / 2 - 0.001), p0[2] + L1 - 0.001 + dz * L2 / 2)
    nodes.append(cyl("cord_b", 0.0023, L2, "cord", c2, (ang, 0, 0), segments=6, caps=False))

    mats = {
        "shell": {"color": CREAM, "smooth": True},
        "face": fit("face", color=CREAM),
        "tmold": {"color": PINK, "smooth": True},
        "plate_pink": {"color": PINK},
        "plate": fit("plate", color=PLUM),
        "plate_side": {"color": PLUM},
        "dpad": {"color": "#3a3046"},
        "steel": {"color": "#c8c8d4", "smooth": True},
        "ball": {"color": PINK, "smooth": True},
        "btn_pink": {"color": PINK, "smooth": True},
        "btn_mint": {"color": MINT, "smooth": True},
        "start": fit("start", emissive=True, color=PINK),
        "select": fit("select", emissive=True, color=MINT),
        "start_side": {"color": "#d64f86"},
        "select_side": {"color": "#5cbf9f"},
        "badge": fit("pad_badge", color=CREAM),
        "shoulder_pink": {"color": PINK},
        "shoulder_mint": {"color": MINT},
        "cord": {"color": "#d9cdb2", "smooth": True},
    }
    return {
        "format": "mei-asset", "version": 1, "name": "arcade_heritage_controller",
        "budget": {"vertices": 900, "triangles": 880},
        "sheets": {"arcade": {"image": "art/arcade_sheet.png"}},
        "materials": mats,
        "lighting": {"direction": [-0.45, 0.85, -0.4], "ambient": 0.55},
        "verification": VERIFY,
        "nodes": nodes,
    }


def main():
    make_marquee()
    make_deck()
    make_kick()
    make_port()
    make_coindoor()
    make_rear()
    make_side("side", False)
    make_side("side_l", True)
    make_hood()
    make_cart_label()
    make_start("start", "START", PINK, "#ffffff")
    make_start("select", "SELECT", MINT, PLUM)
    make_pad_badge()
    con = console()
    pad = controller()      # draws the plate cell
    used = max(y + h for x, y, w, h in CELLS.values())
    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    sheet.crop((0, 0, SHEET_W, used)).save(os.path.join(HERE, "art", "arcade_sheet.png"))
    with open(os.path.join(HERE, "art", "arcade_sheet.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1, "cells": CELLS}, f, indent=1)
        f.write("\n")
    for name, rec in (("console", con), ("controller", pad)):
        with open(os.path.join(HERE, name + ".asset.json"), "w") as f:
            json.dump(rec, f, indent=1)
            f.write("\n")


if __name__ == "__main__":
    main()
