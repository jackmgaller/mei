#!/usr/bin/env python3
"""06 Sunset Skeleton: writes console.asset.json, controller.asset.json and art/*.png.

Run from anywhere: python3 examples/assets/console_lab/06_sunset_skeleton/make_sunset_skeleton.py

The kit has no per-face alpha, so the translucent orange plastic is drawn the way 1990s
hardware faked it: a screen-door (ordered-dither) cutout texture over a double-sided shell,
with the real insides modelled underneath and seen through the holes.
"""
import json
import math
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "art")

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lerp_col(a, b, t):
    a, b = hexrgb(a), hexrgb(b)
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ramp(stops, t):
    """stops: [(t, '#hex'), ...] increasing t."""
    t = max(0.0, min(1.0, t))
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            return lerp_col(c0, c1, (t - t0) / (t1 - t0) if t1 > t0 else 0)
    return hexrgb(stops[-1][1])


def dither_on(x, y, opacity):
    return BAYER[y % 4][x % 4] < opacity * 16


def through_orange(h, amount=0.55):
    """A colour as seen through the orange shell: filtered, then lifted toward the plastic."""
    r, g, b = hexrgb(h)
    f = (1.0, 0.72, 0.38)
    r, g, b = r * f[0], g * f[1], b * f[2]
    o = hexrgb("#ff8a2a")
    k = 0.18 * amount
    r, g, b = [min(255, round(c * (1 - k) + oc * k)) for c, oc in zip((r, g, b), o)]
    return "#%02x%02x%02x" % (r, g, b)


def hash01(x, y, seed):
    h = (x * 374761393 + y * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(1 << 24)


GLARE = hexrgb("#fff1c4")


def fill_plastic(cv, colfn, opfn, seed, streaks=(), slope=1.0, wrap=None, border=0, border_col=None):
    """Clear plastic: sparse random flecks of colour (no regular grid to alias), glossy streaks,
    an optional solid border. colfn(t) and opfn(t) take t = row / height (0 top).
    streaks: (position, width) in texels along x + slope*y; wrap repeats them (tiles)."""
    for y in range(cv.h):
        t = (y + 0.5) / cv.h
        for x in range(cv.w):
            if border and (x < border or y < border or x >= cv.w - border or y >= cv.h - border):
                cv.set(x, y, border_col or colfn(t))
                continue
            d = x + slope * y
            if wrap:
                d %= wrap
            on_streak = any(p <= d < p + w for p, w in streaks)
            if on_streak:
                cv.set(x, y, GLARE)
            elif hash01(x, y, seed) < opfn(t):
                cv.set(x, y, colfn(t))


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [[(0, 0, 0, 0)] * w for _ in range(h)]

    def set(self, x, y, rgb, a=255):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = (rgb[0], rgb[1], rgb[2], a)

    def clear(self, x, y):
        self.set(x, y, (0, 0, 0), 0)

    def rect(self, x0, y0, x1, y1, rgb):
        """Inclusive-exclusive texel rectangle, solid."""
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.set(x, y, rgb)

    def hole(self, x0, y0, x1, y1):
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.clear(x, y)

    def save(self, name):
        im = Image.new("RGBA", (self.w, self.h))
        im.putdata([p for row in self.px for p in row])
        os.makedirs(ART, exist_ok=True)
        im.save(os.path.join(ART, name))


# --- The logo and lettering, as texel rectangles ------------------------------------------

def draw_mei_kanji(cv, x0, y0, sun, moon, moon_outline_only=False, dark=None):
    """明 in a 20 x 18 cell: 日 left (sun), 月 right (moon)."""
    # 日: a 7-wide, 14-tall box with one middle bar, 2-texel strokes.
    S = [(0, 3, 7, 5), (0, 3, 2, 17), (5, 3, 7, 17), (0, 9, 7, 11), (0, 15, 7, 17)]
    for (a, b, c, d) in S:
        cv.rect(x0 + a, y0 + b, x0 + c, y0 + d, sun)
    # 月: top bar, left stroke sweeping down-left, right stroke with a hook, two inner bars.
    M = [(10, 1, 19, 3), (10, 1, 12, 13), (17, 1, 19, 16), (10, 6, 19, 8), (10, 10, 19, 12),
         (9, 13, 11, 15), (8, 15, 10, 17), (15, 16, 18, 18)]
    if moon_outline_only and dark is not None:
        # draw the moon as a 1-texel outline: fill then hollow
        for (a, b, c, d) in M:
            cv.rect(x0 + a - 1, y0 + b - 1, x0 + c + 1, y0 + d + 1, moon)
        for (a, b, c, d) in M:
            cv.rect(x0 + a, y0 + b, x0 + c, y0 + d, dark)
    else:
        for (a, b, c, d) in M:
            cv.rect(x0 + a, y0 + b, x0 + c, y0 + d, moon)


FONT = {
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "I": ["111", "010", "010", "010", "010", "010", "111"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    " ": ["000", "000", "000", "000", "000", "000", "000"],
}


def text_width(s, scale=1):
    return sum((len(FONT[ch][0]) + 1) * scale for ch in s) - scale


def draw_text(cv, x0, y0, s, rgb, scale=1):
    x = x0
    for ch in s:
        g = FONT[ch]
        for r, row in enumerate(g):
            for c, bit in enumerate(row):
                if bit == "1":
                    cv.rect(x + c * scale, y0 + r * scale, x + (c + 1) * scale, y0 + (r + 1) * scale, rgb)
        x += (len(g[0]) + 1) * scale


def disc(cv, cx, cy, r, rgb):
    for y in range(int(cy - r) - 1, int(cy + r) + 2):
        for x in range(int(cx - r) - 1, int(cx + r) + 2):
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r:
                cv.set(x, y, rgb)


def disc_hole(cv, cx, cy, r):
    for y in range(int(cy - r) - 1, int(cy + r) + 2):
        for x in range(int(cx - r) - 1, int(cx + r) + 2):
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r:
                cv.clear(x, y)


def setting_sun(cv, cx, base_y, r, stops, gaps=None, gap_col=None):
    """A striped half sun sitting on a horizon at base_y (texel row), bands thinning downward."""
    if gaps is None:
        gaps = [base_y - 2, base_y - 4, base_y - 6]
    for y in range(int(base_y - r), base_y):
        for x in range(int(cx - r) - 1, int(cx + r) + 2):
            dy = base_y - (y + 0.5)
            if (x + 0.5 - cx) ** 2 + dy ** 2 <= r * r:
                if y in gaps:
                    if gap_col:
                        cv.set(x, y, gap_col)
                    else:
                        cv.clear(x, y)
                else:
                    cv.set(x, y, ramp(stops, (y - (base_y - r)) / r))


# --- Palette --------------------------------------------------------------------------------

SUNSET = [(0.0, "#ffd25a"), (0.35, "#ffa632"), (0.7, "#ff7424"), (1.0, "#e8401e")]
PLUM = hexrgb("#3a1430")
CREAM = hexrgb("#fff3d6")
MOON = hexrgb("#a9c4ff")
SUN = hexrgb("#ffa21e")
FRAME = hexrgb("#ff8a1e")
FRAME_D = hexrgb("#d9541a")


# --- Mesh helper ----------------------------------------------------------------------------

class Mesh:
    def __init__(self):
        self.v, self.f, self.m, self.uv = [], [], [], []

    def add_face(self, pts, mat, uvs=None, outward=None):
        """pts: list of [x,y,z]. outward: a point the face must point away from (flips if not)."""
        if outward is not None:
            n = normal(pts)
            c = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
            d = [c[i] - outward[i] for i in range(3)]
            if sum(n[i] * d[i] for i in range(3)) < 0:
                pts = pts[::-1]
                if uvs is not None:
                    uvs = uvs[::-1]
        base = len(self.v)
        for i, p in enumerate(pts):
            self.v.append([round(c, 6) for c in p])
            self.uv.append([round(c, 5) for c in (uvs[i] if uvs is not None else (0.0, 0.0))])
        self.f.append(list(range(base, base + len(pts))))
        self.m.append(mat)

    def node(self, nid, with_uv):
        n = {"id": nid, "op": "mesh", "vertices": self.v, "faces": self.f,
             "face_materials": self.m}
        if with_uv:
            n["uvs"] = self.uv
        return n


def normal(pts):
    # Newell's method
    nx = ny = nz = 0.0
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return [nx, ny, nz]


def box(nid, size, at, mat, rot=None, open_=None):
    n = {"id": nid, "op": "box", "size": [round(s, 6) for s in size], "material": mat,
         "transform": {"translate": [round(c, 6) for c in at]}}
    if rot:
        n["transform"]["rotate"] = rot
    if open_:
        n["open"] = open_
    return n


def cyl(nid, r, h, at, mat, seg=12, rot=None, caps=True):
    n = {"id": nid, "op": "cylinder", "radius": round(r, 6), "height": round(h, 6),
         "segments": seg, "material": mat, "transform": {"translate": [round(c, 6) for c in at]}}
    if rot:
        n["transform"]["rotate"] = rot
    if not caps:
        n["caps"] = False
    return n


def tex_img(name, proj="fit", bits=4, **kw):
    t = {"image": "art/" + name, "bits": bits, "projection": proj}
    t.update(kw)
    return t


# =============================================================================================
# Console
# =============================================================================================

W, D = 0.270, 0.205          # footprint
A, B = W / 2, D / 2
CH = 0.024                   # corner chamfer
Y0, Y1, Y2, Y3 = 0.004, 0.011, 0.058, 0.070
I0, I3 = 0.005, 0.010        # bottom and top bevel insets
DROP = 0.012                 # the deck slopes down toward the front by this much
TX = 0.0015                  # texel size of the fitted images (front, top)
TW = 0.003                   # texel size of the wall tile
WALL_OP, TOP_OP = 0.3, 0.25  # share of opaque flecks in the clear plastic


def octagon(a, b, c):
    """Footprint going around: front-left corner first, clockwise seen from above (x right, z up)."""
    return [(-a + c, -b), (a - c, -b), (a, -b + c), (a, b - c), (a - c, b), (-a + c, b),
            (-a, b - c), (-a, -b + c)]


def inset_oct(i):
    return octagon(A - i, B - i, CH - i * (2 - math.sqrt(2)))


def sloped(y_back, z):
    """Heights of the upper rings: the deck falls DROP from the back edge to the front edge."""
    return y_back - DROP * (B - z) / (2 * B)


def deck_y(z):
    return sloped(Y3, z)


def console():
    def ring(yfn, inset):
        return [(x, yfn(z), z) for (x, z) in inset_oct(inset)]

    rings = [ring(lambda z: Y0, I0), ring(lambda z: Y1, 0), ring(lambda z: sloped(Y2, z), 0),
             ring(lambda z: sloped(Y3, z), I3)]
    centre = [0, (Y0 + Y3) / 2 - DROP / 2, 0]
    shell = Mesh()      # clear walls
    front = Mesh()      # front wall
    top = Mesh()        # top deck
    rims = Mesh()       # opaque bevels and floor

    # walls: band 1-2; side 0 is the front wall
    ra, rb = rings[1], rings[2]
    perim = 0.0
    n = len(ra)
    # start the perimeter at the front-right corner so u runs continuously round the back
    for k in range(1, n):
        i, j = k, (k + 1) % n
        quad = [list(rb[i]), list(rb[j]), list(ra[j]), list(ra[i])]
        L = math.dist((ra[i][0], ra[i][2]), (ra[j][0], ra[j][2]))
        u0, u1 = perim / (32 * TW), (perim + L) / (32 * TW)
        uvs = [(u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)]
        shell.add_face(quad, "shell_wall", uvs, outward=centre)
        perim += L
    # front wall, fitted image
    quad = [list(rb[0]), list(rb[1]), list(ra[1]), list(ra[0])]
    front.add_face(quad, "shell_front", [(0, 0), (1, 0), (1, 1), (0, 1)], outward=centre)
    front_w = ra[1][0] - ra[0][0]
    front_top = rb[0][1]

    # bevels
    for r0, r1, mat in [(rings[0], rings[1], "rim_low"), (rings[2], rings[3], "rim_high")]:
        for i in range(n):
            j = (i + 1) % n
            q = [list(r0[i]), list(r0[j]), list(r1[j]), list(r1[i])]
            rims.add_face([q[0], q[1], q[2]], mat, outward=centre)
            rims.add_face([q[0], q[2], q[3]], mat, outward=centre)
    # floor
    rims.add_face([list(p) for p in rings[0]], "floor", outward=centre)
    # top deck, uvs projected from above: u along +x, v from the back (+z) down to the front
    tr = rings[3]
    ta, tb = A - I3, B - I3
    top.add_face([list(p) for p in tr], "shell_top",
                 [((p[0] + ta) / (2 * ta), (tb - p[2]) / (2 * tb)) for p in tr], outward=centre)

    # ---- textures for the shell ----
    # wall tile: 32 x 16, gradient top (gold) to bottom (red), denser toward the bottom
    cv = Canvas(32, 16)
    fill_plastic(cv, lambda t: ramp(SUNSET, 0.15 + 0.85 * t), lambda t: WALL_OP + 0.1 * t, 1,
                 streaks=[(3, 2), (8, 1)], slope=-0.5, wrap=32)
    cv.save("console_wall.png")

    # front wall
    fw, fh = round(front_w / TX), round((front_top - Y1) / TX)
    cv = Canvas(fw, fh)
    fill_plastic(cv, lambda t: ramp(SUNSET, 0.15 + 0.85 * t), lambda t: WALL_OP + 0.1 * t, 2,
                 streaks=[(20, 3), (27, 1), (118, 2)], slope=-0.6)

    def fx(xm):   # metres from centre -> texel column
        return round((xm + front_w / 2) / TX)

    def fy(ym):   # metres down from wall top -> texel row
        return round(ym / TX)

    port_x, port_w, port_h, port_y = 0.068, 0.024, 0.012, 0.0205
    mc_w, mc_h, mc_y = 0.032, 0.0045, 0.0075
    for s in (-1, 1):
        cx = s * port_x
        # controller port: solid frame 2 texels, hole inside
        x0, x1 = fx(cx - port_w / 2), fx(cx + port_w / 2)
        y0, y1 = fy(port_y - port_h / 2), fy(port_y + port_h / 2)
        cv.rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2, FRAME_D)
        cv.hole(x0, y0, x1, y1)
        # memory card slot
        x0, x1 = fx(cx - mc_w / 2), fx(cx + mc_w / 2)
        y0, y1 = fy(mc_y - mc_h / 2), fy(mc_y + mc_h / 2)
        cv.rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2, FRAME_D)
        cv.hole(x0, y0, x1, y1)
        # port numbers as pips under the ports
        pips = 1 if s < 0 else 2
        for k in range(pips):
            px = fx(cx) - (pips * 3 - 1) // 2 + k * 3
            cv.rect(px, fy(port_y + port_h / 2) + 3, px + 2, fy(port_y + port_h / 2) + 4, CREAM)
    # centre: the setting sun on a horizon line, the edition's mark
    cxt = fw / 2
    hz = fh - 5
    cv.rect(int(cxt - 18), hz - 14, int(cxt + 18), hz + 2, PLUM)
    setting_sun(cv, cxt, hz, 12.5, [(0, "#ffe070"), (0.5, "#ff9a2a"), (1, "#f04a1e")],
                gaps=(hz - 2, hz - 4, hz - 7), gap_col=PLUM)
    cv.rect(int(cxt - 16), hz, int(cxt + 16), hz + 1, hexrgb("#f04a1e"))
    cv.save("console_front.png")

    # top deck
    tw, th = round(2 * ta / TX), round(2 * tb / TX)
    cv = Canvas(tw, th)
    fill_plastic(cv, lambda t: ramp([(0, "#ffb238"), (1, "#ffc650")], t), lambda t: TOP_OP, 3,
                 streaks=[(30, 6), (40, 2), (150, 4)], slope=0.8)

    def tx(xm):
        return round((xm + ta) / TX)

    def tz(zm):     # z in metres -> row (row 0 at the back, +z)
        return round((tb - zm) / TX)

    feats = {}
    # cart slot: hole with a solid frame under the lip geometry
    slot_z, slot_w, slot_d = 0.040, 0.106, 0.022
    lip = 0.006
    cv.rect(tx(-slot_w / 2 - lip) - 1, tz(slot_z + slot_d / 2 + lip) - 1,
            tx(slot_w / 2 + lip) + 1, tz(slot_z - slot_d / 2 - lip) + 1, FRAME)
    cv.hole(tx(-slot_w / 2), tz(slot_z + slot_d / 2), tx(slot_w / 2), tz(slot_z - slot_d / 2))
    feats["slot"] = (slot_z, slot_w, slot_d, lip)
    # power and reset bezels (rings), the LED's
    btn = {"power": (-0.088, -0.058, 0.0105), "reset": (0.088, -0.058, 0.0075)}
    for name, (bx, bz, br) in btn.items():
        disc(cv, (bx + ta) / TX, (tb - bz) / TX, (br + 0.0035) / TX, FRAME_D)
        disc_hole(cv, (bx + ta) / TX, (tb - bz) / TX, (br + 0.0006) / TX)
    led = (-0.062, -0.072, 0.0022)
    disc(cv, (led[0] + ta) / TX, (tb - led[1]) / TX, (led[2] + 0.002) / TX, FRAME_D)
    disc_hole(cv, (led[0] + ta) / TX, (tb - led[1]) / TX, (led[2] + 0.0004) / TX)
    # the logo badge, front centre: plum plate, 明 with the 日 lit and the 月 in outline, MEI
    bwid, bhgt = 62, 26
    bx0, bz0 = tx(0) - bwid // 2, tz(-0.044)
    cv.rect(bx0 - 1, bz0 - 1, bx0 + bwid + 1, bz0 + bhgt + 1, FRAME)
    for y in range(bhgt):
        for x in range(bwid):
            corner = (x in (0, bwid - 1)) and (y in (0, bhgt - 1))
            cv.set(bx0 + x, bz0 + y, FRAME if corner else PLUM)
    draw_mei_kanji(cv, bx0 + 4, bz0 + 4, SUN, MOON, moon_outline_only=True, dark=PLUM)
    draw_text(cv, bx0 + 28, bz0 + 5, "MEI", CREAM, scale=2)
    # a thin sunset rule under the wordmark
    for x in range(bx0 + 28, bx0 + 58):
        cv.set(x, bz0 + 21, ramp(SUNSET, (x - bx0 - 28) / 30))
    cv.save("console_top.png")

    # ---- materials ----
    mats = {
        "shell_wall": {"color": "#ff8a2a", "double_sided": True,
                       "texture": tex_img("console_wall.png", proj="planar")},
        "shell_front": {"color": "#ff8a2a", "double_sided": True,
                        "texture": tex_img("console_front.png")},
        "shell_top": {"color": "#ffc248", "double_sided": True,
                      "texture": tex_img("console_top.png")},
        "rim_low": {"color": "#d8401c", "double_sided": True},
        "rim_high": {"color": "#ff9a2c", "double_sided": True},
        "floor": {"color": "#f07424", "double_sided": True, "class": "emissive"},
        "pcb": {"color": "#23604a",
                "texture": {"texels": ["0000100000010000", "0000100000010000", "1111100000011111",
                                       "0000000220000000", "0000000220000000", "0011111111111100",
                                       "0010000000000100", "0010022002200100", "0010022002200100",
                                       "0010000000000100", "0011111111111100", "0000000220000000",
                                       "0000000220000000", "1111100000011111", "0000100000010000",
                                       "0000100000010000"],
                            "colors": ["#2c6a4a", "#3c7c56", "#d9b64a"],
                            "projection": "box", "scale": [0.032, 0.032]}},
        "chip": {"color": "#26222a"},
        "chip_mark": {"color": "#8c8894"},
        "shield": {"color": "#c9ccd4"},
        "alu": {"color": "#d7dbe2"},
        "gold": {"color": "#e6b84a"},
        "copper": {"color": "#b8622e"},
        "tape": {"color": "#f2d04a"},
        "cap": {"color": "#2c3f8e"},
        "socket": {"color": "#2a2830"},
        "socket_pin": {"color": "#8a8794"},
        "lip": {"color": "#ff7c1e"},
        "cart": {"color": "#4a1f48"},
        "cart_label": {"color": "#ffb040", "texture": tex_img("cart_label.png", bits=8)},
        "power": {"color": "#e8381c"},
        "reset": {"color": "#ffc23a"},
        "led": {"color": "#ff3a20", "class": "emissive"},
        "rubber": {"color": "#3a2a2a"},
    }

    # what lies inside the shell is seen through orange plastic: warm it
    for k in ("pcb", "chip", "chip_mark", "shield", "alu", "gold", "copper", "tape", "cap",
              "socket", "socket_pin"):
        mats[k]["color"] = through_orange(mats[k]["color"])
        if "texture" in mats[k]:
            mats[k]["texture"]["colors"] = [through_orange(c) for c in mats[k]["texture"]["colors"]]

    # ---- inside ----
    nodes = [shell.node("shell_walls", True), front.node("shell_front", True),
             top.node("shell_top", True), rims.node("shell_rims", False)]
    pcb_y = 0.0145
    nodes.append(box("pcb", [0.212, 0.0016, 0.160], [0, pcb_y, 0.002], "pcb"))
    on = pcb_y + 0.0008     # board surface
    inside = [
        box("cpu", [0.026, 0.003, 0.026], [-0.050, on + 0.0012, -0.012], "chip"),
        box("cpu_mark", [0.010, 0.0006, 0.004], [-0.050, on + 0.0029, -0.018], "chip_mark"),
        box("ram_a", [0.020, 0.0025, 0.010], [-0.012, on + 0.001, -0.030], "chip"),
        box("ram_b", [0.020, 0.0025, 0.010], [-0.012, on + 0.001, -0.010], "chip"),
        box("rom_chip", [0.016, 0.0025, 0.012], [0.000, on + 0.001, 0.075], "chip"),
        box("hs_base", [0.042, 0.003, 0.042], [0.050, on + 0.0022, -0.014], "alu"),
    ]
    fins = {"id": "hs_fins", "op": "group", "children": [
        box("fin", [0.0016, 0.022, 0.040], [0.050 - 0.0175, on + 0.0145, -0.014], "alu")],
        "modifiers": [{"op": "array", "count": 6, "step": [0.007, 0, 0]}]}
    inside.append(fins)
    # MeiNet tuner can at the back left, its coax going out of the back wall
    inside += [
        box("tuner", [0.052, 0.014, 0.040], [-0.082, on + 0.0066, 0.058], "shield"),
        cyl("coax", 0.0042, 0.024, [-0.082, on + 0.008, B + 0.004], "gold", seg=10, rot=[90, 0, 0]),
        cyl("coax_nut", 0.0058, 0.005, [-0.082, on + 0.008, B + 0.010], "gold", seg=6, rot=[90, 0, 0]),
        box("av_out", [0.024, 0.010, 0.020], [-0.030, on + 0.0055, B - 0.004], "socket"),
        box("dc_in", [0.012, 0.012, 0.022], [0.112, on + 0.0065, B - 0.004], "socket"),
        cyl("dc_pin", 0.0025, 0.006, [0.112, on + 0.0065, B + 0.0075], "socket_pin", seg=8, rot=[90, 0, 0]),
        # power supply corner: transformer with yellow tape and two capacitors
        box("transformer", [0.030, 0.024, 0.028], [0.082, on + 0.0125, 0.060], "copper"),
        box("transformer_tape", [0.031, 0.008, 0.029], [0.082, on + 0.016, 0.060], "tape"),
        cyl("cap_a", 0.0062, 0.020, [0.052, on + 0.0095, 0.080], "cap", seg=10),
        cyl("cap_b", 0.0050, 0.016, [0.038, on + 0.0073, 0.072], "cap", seg=10),
        # cart connector under the slot
        box("cart_conn", [0.114, 0.016, 0.026], [0, on + 0.0075, feats["slot"][0]], "socket"),
    ]
    # controller ports and memory card slots behind the front wall's openings
    zf = -B
    for s, tag in ((-1, "1"), (1, "2")):
        cx = s * port_x
        py = front_top - port_y
        my = front_top - mc_y
        inside += [
            box("port" + tag, [0.030, 0.019, 0.028], [cx, py, zf + 0.0035 + 0.014], "socket"),
            box("port" + tag + "_tongue", [0.016, 0.0045, 0.010], [cx, py + 0.001, zf + 0.0062], "socket_pin"),
            box("card" + tag, [0.038, 0.008, 0.030], [cx, my, zf + 0.0028 + 0.015], "socket"),
        ]
    # power and reset: plungers rising through the deck; the LED
    for name, (bx, bz, br) in btn.items():
        h = deck_y(bz) + 0.004 - 0.040
        inside.append(cyl(name + "_button", br, h, [bx, 0.040 + h / 2, bz], name, seg=12))
        inside.append(box(name + "_switch", [0.014, 0.010, 0.014], [bx, 0.034, bz], "chip"))
    inside.append(cyl("led", led[2], 0.012, [led[0], deck_y(led[1]) - 0.004, led[1]], "led", seg=8))
    # cart slot lip, four bars
    sz, sw, sd, lp = feats["slot"]
    lh = 0.006
    ly = lh / 2 - 0.002
    slope_deg = math.degrees(math.atan2(DROP, 2 * B))
    inside.append({"id": "slot_lip", "op": "group", "children": [
        box("lip_back", [sw + 2 * lp, lh, lp], [0, ly, sd / 2 + lp / 2], "lip"),
        box("lip_front", [sw + 2 * lp, lh, lp], [0, ly, -sd / 2 - lp / 2], "lip"),
        box("lip_left", [lp - 0.0006, lh - 0.001, sd + 0.002], [-sw / 2 - lp / 2, ly, 0], "lip"),
        box("lip_right", [lp - 0.0006, lh - 0.001, sd + 0.002], [sw / 2 + lp / 2, ly, 0], "lip")],
        "transform": {"rotate": [round(-slope_deg, 4), 0, 0], "translate": [0, round(deck_y(sz), 6), sz]}})
    # the cart, standing in the connector
    cw, cd = 0.100, 0.016
    cy0, cy1 = on + 0.010, deck_y(sz) + 0.044
    cart_pts = [[-cw / 2, cy0], [cw / 2, cy0], [cw / 2, cy1 - 0.008], [cw / 2 - 0.008, cy1],
                [-cw / 2 + 0.008, cy1], [-cw / 2, cy1 - 0.008]]
    inside.append({"id": "cart", "op": "extrude", "points": [[round(a, 6), round(b, 6)] for a, b in cart_pts],
                   "depth": cd, "material": "cart", "transform": {"translate": [0, 0, sz]}})
    # grip ridges on the cart's top
    inside.append({"id": "cart_grip", "op": "group", "children": [
        box("ridge", [0.0016, 0.004, cd + 0.002], [-0.020, cy1 - 0.0045, sz], "cart")],
        "modifiers": [{"op": "array", "count": 6, "step": [0.008, 0, 0]}]})
    # label on the cart's front (-z), 0.6 mm proud
    lw, lh2 = 0.070, 0.034
    lz = sz - cd / 2 - 0.0006
    lyc = deck_y(sz) + 0.022
    inside.append({"id": "cart_label", "op": "mesh", "material": "cart_label",
                   "vertices": [[-lw / 2, lyc + lh2 / 2, lz], [lw / 2, lyc + lh2 / 2, lz],
                                [lw / 2, lyc - lh2 / 2, lz], [-lw / 2, lyc - lh2 / 2, lz]],
                   "faces": [[0, 1, 2, 3]]})
    # feet
    inside.append({"id": "feet", "op": "group", "children": [
        cyl("foot", 0.011, 0.006, [0.100, 0.003, 0.072], "rubber", seg=8)],
        "modifiers": [{"op": "mirror", "axis": "x"}, {"op": "mirror", "axis": "z"}]})
    nodes += inside

    # cart label art: 48 x 24, a sunset over the sea with a title bar
    cv = Canvas(48, 24)
    for y in range(24):
        for x in range(48):
            if y < 15:
                cv.set(x, y, ramp([(0, "#5a2a7a"), (0.45, "#e04a6a"), (1, "#ffb040")], y / 14))
            else:
                cv.set(x, y, ramp([(0, "#2a3a8a"), (1, "#181a4a")], (y - 15) / 8))
    setting_sun(cv, 24, 15, 9, [(0, "#fff0a0"), (1, "#ff7a2a")])
    for y in (17, 19, 21):
        for x in range(16 + (y - 17), 32 - (y - 17)):
            cv.set(x, y, hexrgb("#ff9a3a"))
    cv.rect(0, 0, 48, 5, PLUM)
    draw_mei_kanji_small(cv, 2, 0)
    cv.save("cart_label.png")

    return {
        "format": "mei-asset", "version": 1, "name": "sunset_console",
        "budget": {"vertices": 2048, "triangles": 1200},
        "materials": mats,
        "lighting": {"direction": [-0.4, 0.85, -0.35], "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": nodes,
    }


def draw_mei_kanji_small(cv, x0, y0):
    """A 5-texel-tall 明 for the cart label's title bar, with a dash for the title."""
    for (a, b, c, d) in [(0, 1, 3, 2), (0, 1, 1, 5), (2, 1, 3, 5), (0, 3, 3, 4), (0, 4, 3, 5)]:
        cv.rect(x0 + a, y0 + b, x0 + c, y0 + d, SUN)
    for (a, b, c, d) in [(4, 0, 7, 1), (4, 0, 5, 5), (6, 0, 7, 5), (4, 2, 7, 3)]:
        cv.rect(x0 + a, y0 + b, x0 + c, y0 + d, MOON)
    cv.rect(x0 + 10, y0 + 2, x0 + 40, y0 + 3, CREAM)


# =============================================================================================
# Controller
# =============================================================================================

# Right half of the outline seen from above (x right, z away from the player), from the back
# centre round to the front centre; the left half mirrors it.
PAD_RIGHT = [(0.000, 0.034), (0.022, 0.035), (0.042, 0.038), (0.056, 0.038), (0.067, 0.033),
             (0.074, 0.022), (0.077, 0.006), (0.076, -0.012), (0.072, -0.030), (0.066, -0.046),
             (0.058, -0.058), (0.048, -0.064), (0.038, -0.062), (0.031, -0.053), (0.027, -0.038),
             (0.022, -0.026), (0.012, -0.020), (0.000, -0.019)]
PTX = 0.001          # texel size of the controller's top image
PTW = 0.0015         # texel size of its wall tile


def pad_outline():
    right = PAD_RIGHT
    left = [(-x, z) for (x, z) in reversed(right[1:-1])]
    return right + left


def signed_area(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def inset_poly(poly, d):
    """Offset a simple polygon inward by d (miter, clamped)."""
    n = len(poly)
    ccw = signed_area(poly) > 0
    out = []
    for i in range(n):
        p0, p1, p2 = poly[i - 1], poly[i], poly[(i + 1) % n]
        def inward(a, b):
            ex, ez = b[0] - a[0], b[1] - a[1]
            L = math.hypot(ex, ez)
            # left normal of the edge points inside for a CCW polygon
            nx, nz = -ez / L, ex / L
            return (nx, nz) if ccw else (-nx, -nz)
        n0, n1 = inward(p0, p1), inward(p1, p2)
        mx, mz = n0[0] + n1[0], n0[1] + n1[1]
        L = math.hypot(mx, mz)
        mx, mz = mx / L, mz / L
        cos = mx * n0[0] + mz * n0[1]
        k = d / max(cos, 0.5)
        out.append((p1[0] + mx * k, p1[1] + mz * k))
    return out


def ear_clip(poly):
    """Triangulate a simple polygon (2D); returns index triples, same winding as the polygon."""
    idx = list(range(len(poly)))
    ccw = signed_area(poly) > 0
    tris = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def inside(p, a, b, c):
        d1, d2, d3 = cross(a, b, p), cross(b, c, p), cross(c, a, p)
        if ccw:
            return d1 > 1e-12 and d2 > 1e-12 and d3 > 1e-12
        return d1 < -1e-12 and d2 < -1e-12 and d3 < -1e-12

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        best = None
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i0], poly[i1], poly[i2]
            cr = cross(a, b, c)
            if (cr <= 1e-12) if ccw else (cr >= -1e-12):
                continue
            if any(inside(poly[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            # prefer fat ears
            e = [math.dist(a, b), math.dist(b, c), math.dist(c, a)]
            q = abs(cr) / (max(e) ** 2)
            if best is None or q > best[0]:
                best = (q, k, (i0, i1, i2))
        if best is None:
            raise RuntimeError("ear clipping failed")
        tris.append(best[2])
        idx.pop(best[1])
    tris.append(tuple(idx))
    return tris


def grip_s(z):
    t = max(0.0, min(1.0, (-z - 0.005) / 0.055))
    return t * t * (3 - 2 * t)


PAD_RINGS = [  # (height, droop at the grip tips, inset)
    (0.000, -0.017, 0.006), (0.006, -0.016, 0.0), (0.020, -0.009, 0.0), (0.027, -0.007, 0.006)]


def pad_top_y(z):
    return PAD_RINGS[3][0] + PAD_RINGS[3][1] * grip_s(z)


def controller():
    base = pad_outline()
    rings = []
    for (h, droop, ins) in PAD_RINGS:
        poly = inset_poly(base, ins) if ins else base
        rings.append([(x, h + droop * grip_s(z), z) for (x, z) in poly])
    n = len(base)
    centre_at = lambda p: [p[0] * 0.6, 0.013 + -0.006 * grip_s(p[2]), p[2] * 0.6]
    walls, top, rims = Mesh(), Mesh(), Mesh()

    def oriented_tri(m, pts, mat, uvs, ref):
        m.add_face(pts, mat, uvs, outward=ref)

    # walls (clear), rims (opaque bevels)
    perim = 0.0
    for i in range(n):
        j = (i + 1) % n
        a0, a1, b1, b0 = rings[1][i], rings[1][j], rings[2][j], rings[2][i]
        L = math.dist((a0[0], a0[2]), (a1[0], a1[2]))
        u0, u1 = perim / (32 * PTW), (perim + L) / (32 * PTW)
        perim += L
        mid = [(a0[k] + a1[k]) / 2 for k in range(3)]
        ref = centre_at(mid)
        q = [list(b0), list(b1), list(a1), list(a0)]
        quv = [(u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)]
        oriented_tri(walls, [q[0], q[1], q[2]], "pad_wall", [quv[0], quv[1], quv[2]], ref)
        oriented_tri(walls, [q[0], q[2], q[3]], "pad_wall", [quv[0], quv[2], quv[3]], ref)
        for r0, r1, mat in ((rings[0], rings[1], "pad_rim_low"), (rings[2], rings[3], "pad_rim_high")):
            q = [list(r0[i]), list(r0[j]), list(r1[j]), list(r1[i])]
            rims.add_face([q[0], q[1], q[2]], mat, outward=ref)
            rims.add_face([q[0], q[2], q[3]], mat, outward=ref)
    # caps
    xs = [p[0] for p in rings[3]]
    zs = [p[2] for p in rings[3]]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    tris = ear_clip([(p[0], p[2]) for p in rings[3]])
    for t in tris:
        pts = [list(rings[3][k]) for k in t]
        uvs = [((p[0] - x0) / (x1 - x0), (z1 - p[2]) / (z1 - z0)) for p in pts]
        c = [sum(p[k] for p in pts) / 3 for k in range(3)]
        top.add_face(pts, "pad_top", uvs, outward=[c[0], c[1] - 1.0, c[2]])
    tris = ear_clip([(p[0], p[2]) for p in rings[0]])
    for t in tris:
        pts = [list(rings[0][k]) for k in t]
        c = [sum(p[k] for p in pts) / 3 for k in range(3)]
        rims.add_face(pts, "pad_floor", outward=[c[0], c[1] + 1.0, c[2]])

    # ---- layout on the top ----
    dpad_c = (-0.047, 0.006)
    abxy_c = (0.047, 0.006)
    off = 0.0115
    face = {"y": (abxy_c[0], abxy_c[1] + off, "#9a4ab4"),      # violet: dusk
            "x": (abxy_c[0] - off, abxy_c[1], "#f2587e"),      # rose
            "b": (abxy_c[0] + off, abxy_c[1], "#ffc030"),      # gold
            "a": (abxy_c[0], abxy_c[1] - off, "#f2441c")}      # vermilion: the sun
    btn_r = 0.0056
    stick_c = (0.0, -0.007)
    ss = {"select": (-0.012, 0.019), "start": (0.012, 0.019)}

    # ---- top image ----
    tw, th = round((x1 - x0) / PTX), round((z1 - z0) / PTX)
    cv = Canvas(tw, th)
    fill_plastic(cv, lambda t: ramp([(0, "#ffb436"), (1, "#ff9a2c")], t), lambda t: 0.27, 5,
                 streaks=[(26, 5), (35, 2), (118, 3)], slope=0.9)

    def px(xm):
        return (xm - x0) / PTX

    def pz(zm):
        return (z1 - zm) / PTX

    # d-pad well: a solid rounded square bezel with a cross-shaped hole
    cx, cz = px(dpad_c[0]), pz(dpad_c[1])
    disc(cv, cx, cz, 17.5, FRAME_D)
    for (a, b, c, d) in ((-14, -5, 14, 5), (-5, -14, 5, 14)):
        cv.hole(round(cx + a), round(cz + b), round(cx + c), round(cz + d))
    # face buttons: bezel rings and holes, and their letters as pips of colour beside them
    for k, (bx, bz, col) in face.items():
        disc(cv, px(bx), pz(bz), (btn_r + 0.0022) / PTX, FRAME_D)
    for k, (bx, bz, col) in face.items():
        disc_hole(cv, px(bx), pz(bz), (btn_r + 0.0005) / PTX)
    # stick: a sunken ring
    disc(cv, px(stick_c[0]), pz(stick_c[1]), 0.0155 / PTX, FRAME_D)
    disc_hole(cv, px(stick_c[0]), pz(stick_c[1]), 0.0128 / PTX)
    # start/select: pill slots
    for k, (sx, sz) in ss.items():
        x0p, z0p = round(px(sx) - 6), round(pz(sz) - 3)
        cv.rect(x0p - 1, z0p - 1, x0p + 13, z0p + 7, FRAME_D)
        cv.hole(x0p + 1, z0p + 1, x0p + 11, z0p + 5)
    # on the grips: 明 on the right, MEI on the left, each on a plum plate
    bx0, bz0 = round(px(0.049) - 12), round(pz(-0.030))
    cv.rect(bx0 - 1, bz0 - 1, bx0 + 25, bz0 + 21, FRAME)
    cv.rect(bx0, bz0, bx0 + 24, bz0 + 20, PLUM)
    draw_mei_kanji(cv, bx0 + 3, bz0 + 1, SUN, MOON, moon_outline_only=True, dark=PLUM)
    bx0, bz0 = round(px(-0.049) - 10), round(pz(-0.030)) + 5
    cv.rect(bx0 - 1, bz0 - 1, bx0 + 21, bz0 + 12, FRAME)
    cv.rect(bx0, bz0, bx0 + 20, bz0 + 11, PLUM)
    draw_text(cv, bx0 + 3, bz0 + 2, "MEI", CREAM)
    cv.save("pad_top.png")

    cv = Canvas(32, 8)
    fill_plastic(cv, lambda t: ramp(SUNSET, 0.3 + 0.7 * t), lambda t: 0.34 + 0.12 * t, 6,
                 streaks=[(4, 2)], slope=-0.5, wrap=32)
    cv.save("pad_wall.png")

    mats = {
        "pad_wall": {"color": "#ff8a2a", "double_sided": True,
                     "texture": tex_img("pad_wall.png", proj="planar")},
        "pad_top": {"color": "#ffb436", "double_sided": True, "texture": tex_img("pad_top.png")},
        "pad_rim_low": {"color": "#d8401c", "double_sided": True, "smooth": True},
        "pad_rim_high": {"color": "#ff9a2c", "double_sided": True, "smooth": True},
        "pad_floor": {"color": "#f07424", "double_sided": True, "class": "emissive"},
        "pcb": {"color": through_orange("#2c6a4a"),
                "texture": {"texels": ["0000100000010000", "0000100000010000", "1111100000011111",
                                       "0000000220000000", "0000000220000000", "0011111111111100",
                                       "0010000000000100", "0010022002200100", "0010022002200100",
                                       "0010000000000100", "0011111111111100", "0000000220000000",
                                       "0000000220000000", "1111100000011111", "0000100000010000",
                                       "0000100000010000"],
                            "colors": [through_orange(c) for c in ("#2c6a4a", "#3c7c56", "#d9b64a")],
                            "projection": "box", "scale": [0.02, 0.02]}},
        "membrane": {"color": through_orange("#3a3640")},
        "gimbal": {"color": through_orange("#55525c")},
        "motor": {"color": through_orange("#c9ccd4")},
        "plum": {"color": "#4a1f48"},
        "plum_light": {"color": "#6a2f62"},
        "sun_cap": {"color": "#f2441c"},
        "cable": {"color": "#c2401e", "smooth": True},
    }
    for k, (bx, bz, col) in face.items():
        mats["btn_" + k] = {"color": col}

    nodes = [walls.node("shell_walls", True), top.node("shell_top", True), rims.node("shell_rims", False)]

    # ---- inside ----
    pcb_poly = [(-0.060, 0.026), (0.060, 0.026), (0.066, 0.010), (0.062, -0.012), (0.024, -0.016),
                (0.0, -0.013), (-0.024, -0.016), (-0.062, -0.012), (-0.066, 0.010)]
    pcb = {"id": "pcb", "op": "extrude", "points": [[x, -z] for (x, z) in pcb_poly], "depth": 0.0014,
           "material": "pcb", "transform": {"rotate": [90, 0, 0], "translate": [0, 0.0085, 0]}}
    nodes.append(pcb)
    on = 0.0085 + 0.0007
    nodes += [
        cyl("dpad_membrane", 0.016, 0.002, [dpad_c[0], on + 0.0007, dpad_c[1]], "membrane", seg=6),
        cyl("abxy_membrane", 0.020, 0.002, [abxy_c[0], on + 0.0007, abxy_c[1]], "membrane", seg=6),
        box("gimbal", [0.022, 0.012, 0.022], [stick_c[0], on + 0.0055, stick_c[1]], "gimbal"),
        # rumble motors in the grips, seen as silver cans
        cyl("motor_l", 0.0065, 0.016, [-0.050, 0.004, -0.036], "motor", seg=6, rot=[90, 0, 0]),
        cyl("motor_r", 0.0055, 0.014, [0.050, 0.004, -0.036], "motor", seg=6, rot=[90, 0, 0]),
    ]
    # ---- on top ----
    # d-pad: a plus, 4 mm thick
    arm, half = 0.0088, 0.0135
    plus = [(-half, arm / 2), (-arm / 2, arm / 2), (-arm / 2, half), (arm / 2, half), (arm / 2, arm / 2),
            (half, arm / 2), (half, -arm / 2), (arm / 2, -arm / 2), (arm / 2, -half), (-arm / 2, -half),
            (-arm / 2, -arm / 2), (-half, -arm / 2)]
    ty = pad_top_y(dpad_c[1])
    nodes.append({"id": "dpad", "op": "extrude", "points": [[round(x, 6), round(z, 6)] for x, z in plus],
                  "depth": 0.0065, "material": "plum",
                  "transform": {"rotate": [90, 0, 0], "translate": [dpad_c[0], round(ty + 0.0002, 6), dpad_c[1]]}})
    for k, (bx, bz, col) in face.items():
        y = pad_top_y(bz)
        nodes.append({"id": "btn_" + k, "op": "lathe", "segments": 8, "caps": False, "material": "btn_" + k,
                      "profile": [[btn_r, -0.0042], [btn_r, 0.0028], [0.0, 0.0040]],
                      "transform": {"translate": [round(bx, 6), round(y, 6), round(bz, 6)]}})
    # analog stick: collar, shaft, sun cap
    y = pad_top_y(stick_c[1])
    nodes += [
        {"id": "stick_collar", "op": "lathe", "segments": 10, "caps": False, "material": "plum",
         "profile": [[0.0125, -0.003], [0.0118, 0.002], [0.0045, 0.0055]],
         "transform": {"translate": [stick_c[0], y, stick_c[1]]}},
        cyl("stick_shaft", 0.0035, 0.012, [stick_c[0], y + 0.009, stick_c[1]], "plum_light", seg=6, caps=False),
        {"id": "stick_cap", "op": "lathe", "segments": 10, "caps": False, "material": "sun_cap",
         "profile": [[0.0098, 0.0], [0.0105, 0.003], [0.0085, 0.0048], [0.0, 0.0052]],
         "transform": {"translate": [stick_c[0], y + 0.0135, stick_c[1]]}},
    ]
    for k, (sx, sz) in ss.items():
        y = pad_top_y(sz)
        nodes.append({"id": k, "op": "cylinder", "radius": 0.0022, "height": 0.0075, "segments": 6,
                      "material": "plum",
                      "transform": {"scale": [1, 1, 1], "rotate": [0, 0, 90],
                                    "translate": [round(sx, 6), round(y + 0.0006, 6), round(sz, 6)]}})
    # shoulders: L and R on the back edge
    for s, k in ((-1, "l"), (1, "r")):
        nodes.append({"id": "shoulder_" + k, "op": "lathe", "segments": 6, "material": "plum",
                      "profile": [[0.0, -0.016], [0.0062, -0.0145], [0.0068, 0.0], [0.0062, 0.0145], [0.0, 0.016]],
                      "transform": {"scale": [1, 1, 0.8], "rotate": [0, 0, 90],
                                    "translate": [s * 0.050, 0.0185, 0.0365]}})
        nodes[-1]["transform"]["rotate"] = [0, s * -12, 90]
    # cable: strain relief and a stub (the cable runs on to the console)
    nodes += [
        {"id": "strain_relief", "op": "lathe", "segments": 6, "caps": False, "material": "cable",
         "profile": [[0.0052, 0.0], [0.0045, 0.008], [0.0030, 0.016]],
         "transform": {"rotate": [90, 0, 0], "translate": [0, 0.013, 0.031]}},
        cyl("cable", 0.0024, 0.024, [0, 0.013, 0.056], "cable", seg=6, rot=[90, 0, 0]),
    ]
    # the grips droop below the body: lift the whole pad so it rests on the table at y = 0
    nodes = [{"id": "pad", "op": "group", "children": nodes,
              "transform": {"translate": [0, -PAD_RINGS[0][1], 0]}}]
    return {
        "format": "mei-asset", "version": 1, "name": "sunset_controller",
        "budget": {"vertices": 2048, "triangles": 850},
        "materials": mats,
        "lighting": {"direction": [-0.4, 0.85, -0.35], "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": nodes,
    }


def main():
    for name, fn in (("console", console), ("controller", controller)):
        rec = fn()
        with open(os.path.join(HERE, name + ".asset.json"), "w") as f:
            json.dump(rec, f, indent=1)
            f.write("\n")


if __name__ == "__main__":
    main()
