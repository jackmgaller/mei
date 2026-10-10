#!/usr/bin/env python3
"""Console lab look 09, Hi-Fi Deck: writes art/*.png, console.asset.json and controller.asset.json.

Run: python3 examples/assets/console_lab/09_hifi_deck/make_hifi_deck.py  (needs Pillow)

Everything is laid out in metres at real size; the fascia art is drawn from the same numbers as
the geometry, so the printed labels land under and beside the parts they name.
"""
import json
import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "art")
FONTS = "/System/Library/Fonts"
HIRAGINO = os.path.join(FONTS, "ヒラギノ角ゴシック W6.ttc")
FUTURA = os.path.join(FONTS, "Supplemental", "Futura.ttc")

# ---------------------------------------------------------------- colours
CHAMP = ["#d6cbaf", "#d2c7ab", "#d9cfb4", "#ddd3b9"]   # brushed champagne aluminium tones
CHAMP_LOW = ["#bbb095", "#b7ac91", "#beb399", "#c2b89e"]  # the lower band, a shade darker
PRINT = "#3b362e"          # dark silk-screen print
PRINT_SOFT = "#7b7363"     # lighter print (tick marks)
GROOVE = "#8f8672"
SUN = "#f0962e"            # the 日
MOON = "#a8c8f0"           # the 月
WHITE = "#f4f1ea"
GUN = "#3a3b41"            # gunmetal cover
GUN_DARK = "#26272b"
BLACK = "#16161a"
LED_RED = "#ff3b2a"

# ---------------------------------------------------------------- pixel font (3 x 5)
GLYPHS = {
    "A": "010101111101101", "B": "110101110101110", "C": "011100100100011", "D": "110101101101110",
    "E": "111100110100111", "F": "111100110100100", "G": "011100101101011", "H": "101101111101101",
    "I": "111010010010111", "J": "001001001101010", "K": "101101110101101", "L": "100100100100111",
    "M": "101111111101101", "N": "110101101101101", "O": "010101101101010", "P": "110101110100100",
    "Q": "010101101110011", "R": "110101110101101", "S": "011100010001110", "T": "111010010010010",
    "U": "101101101101111", "V": "101101101101010", "W": "101101111111101", "X": "101101010101101",
    "Y": "101101010010010", "Z": "111001010100111",
    "0": "111101101101111", "1": "010110010010111", "2": "110001010100111", "3": "110001010001110",
    "4": "101101111001001", "5": "111100110001110", "6": "011100111101111", "7": "111001010010010",
    "8": "111101111101111", "9": "111101111001110",
    ":": "000010000010000", ".": "000000000000010", "-": "000000111000000", "/": "001001010100100",
    "&": "010101010101011", "+": "000010111010000", " ": "000000000000000", "'": "010010000000000",
    "<": "001010100010001", ">": "100010001010100",
}


def ptext_width(s, scale=1):
    return (len(s) * 4 - 1) * scale


def ptext(d, x, y, s, fill, scale=1, center=False):
    """Draw s in the 3x5 pixel font with its top-left (or top-centre) at x, y."""
    if center:
        x = x - ptext_width(s, scale) // 2
    x = int(round(x))
    y = int(round(y))
    for ch in s.upper():
        g = GLYPHS[ch]
        for i, bit in enumerate(g):
            if bit == "1":
                cx, cy = x + (i % 3) * scale, y + (i // 3) * scale
                d.rectangle([cx, cy, cx + scale - 1, cy + scale - 1], fill=fill)
        x += 4 * scale


def brushed(w, h, tones, seed, streak=True):
    """Horizontal hairline-brushed metal: each row one of a few tones, with longer streaks."""
    rnd = random.Random(seed)
    img = Image.new("RGB", (w, h), tones[0])
    d = ImageDraw.Draw(img)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=tones[rnd.randrange(len(tones) - 1)])
        if streak:
            for _ in range(1):
                x0 = rnd.randrange(w)
                d.line([(x0, y), (x0 + rnd.randrange(8, 40), y)], fill=tones[-1])
    return img


def logo_glyph(size, color_sun, color_moon, bg):
    """明 at size px with the 日 half warm and the 月 half pale blue (split at the gap)."""
    font = ImageFont.truetype(HIRAGINO, size)
    mask = Image.new("L", (size * 2, size * 2), 0)
    md = ImageDraw.Draw(mask)
    md.text((size // 2, size // 2), "明", font=font, fill=255)
    bbox = mask.getbbox()
    mask = mask.crop(bbox)
    w, h = mask.size
    # the 日 is left of the emptiest column near a third of the way across, and above the
    # bottom of its own left stroke (the 月's sweep reaches under it)
    on = {(x, y) for y in range(h) for x in range(w) if mask.getpixel((x, y)) > 110}
    cols = [sum(1 for y in range(h) if (x, y) in on) for x in range(w)]
    split = min(range(int(w * 0.3), int(w * 0.5)), key=lambda x: (cols[x], x))
    bottom = max(y for (x, y) in on if x < w * 0.15)
    sun = tuple(int(color_sun[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
    moon = tuple(int(color_moon[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for (x, y) in on:
        out.putpixel((x, y), sun if (x < split and y <= bottom) else moon)
    return out


def futura_text(text, size, fill, bold=True):
    font = ImageFont.truetype(FUTURA, size, index=2 if bold else 0)
    mask = Image.new("L", (size * len(text) + 10, size * 2), 0)
    ImageDraw.Draw(mask).text((2, 2), text, font=font, fill=255)
    mask = mask.crop(mask.getbbox())
    mask = mask.point(lambda v: 255 if v > 110 else 0)
    out = Image.new("RGBA", mask.size, fill)
    out.putalpha(mask)
    return out


def flatten_alpha(img):
    """Binary alpha for pasting onto a texture: pixels are either fully on or off."""
    a = img.split()[-1].point(lambda v: 255 if v > 110 else 0)
    img.putalpha(a)
    return img


# ================================================================ console geometry numbers
FX = 0.152            # fascia half width (ends buried in the walnut cheeks, visible to 0.149)
FY0, FY1 = 0.008, 0.0855   # fascia front face, bottom and top (a diamond-cut chamfer above)
FZ = -0.134           # fascia front plane
FZB = -0.127          # fascia back (buried in the chassis)
TOP = 0.087           # fascia top (1 mm above the cover)
CHY0, CHY1 = 0.0095, 0.086
CHZ0, CHZ1 = -0.130, 0.132
CHEEK_X0, CHEEK_X1 = 0.149, 0.161

FPX = 510 / (2 * FX)  # fascia texels per metre
FW, FH = 510, int(round((FY1 - FY0) * FPX))


def fx(x):
    return (x + FX) * FPX


def fy(y):
    return (FY1 - y) * FPX


# parts on the fascia: (x0, x1, y0, y1)
BADGE = (-0.1445, -0.0905, 0.0590, 0.0805)
DOOR = (-0.0845, 0.0045, 0.0355, 0.0815)
VFD = (0.0125, 0.1005, 0.0525, 0.0805)
PILLS = [(0.0125 + i * 0.0225, 0.0125 + i * 0.0225 + 0.0155, 0.0405, 0.0455) for i in range(4)]
PILL_LABELS = ["DISP", "NET", "CLOCK", "DIM"]
KNOB = (0.1265, 0.0585)       # centre
KNOB_R = 0.0175
POWER = (-0.1305, 0.0205)     # centre
POWER_R = 0.0072
LED = (-0.1175, -0.1155, 0.0262, 0.0282)
RESET = (-0.1110, -0.0970, 0.0175, 0.0235)
EJECT = (-0.0825, -0.0675, 0.0170, 0.0230)
PORTS = [(-0.0585, -0.0375, 0.0145, 0.0265), (-0.0325, -0.0115, 0.0145, 0.0265)]
CARDS = [(0.0125, 0.0485, 0.0175, 0.0245), (0.0585, 0.0945, 0.0175, 0.0245)]
NET_LED = (0.1235, 0.1255, 0.0230, 0.0250)
SPLIT_Y = 0.0320              # the groove between the upper and lower bands


def draw_fascia():
    img = brushed(FW, FH, CHAMP, seed=9)
    low = brushed(FW, FH, CHAMP_LOW, seed=10)
    img.paste(low.crop((0, int(fy(SPLIT_Y)), FW, FH)), (0, int(fy(SPLIT_Y))))
    d = ImageDraw.Draw(img)

    def box(r, **kw):
        x0, x1, y0, y1 = r
        d.rectangle([fx(x0), fy(y1), fx(x1), fy(y0)], **kw)

    # groove between bands, and a shadow line under each proud part
    gy = fy(SPLIT_Y)
    d.line([(fx(-0.149), gy), (fx(0.149), gy)], fill=GROOVE)
    d.line([(fx(-0.149), gy + 1), (fx(0.149), gy + 1)], fill=WHITE)
    for r in [BADGE, DOOR, VFD, RESET, EJECT] + PILLS + PORTS + CARDS:
        x0, x1, y0, y1 = r
        d.line([(fx(x0), fy(y0) + 1), (fx(x1), fy(y0) + 1)], fill=GROOVE)

    # under the badge: the spec-sheet lettering of a 1997 deck
    bx = fx(BADGE[0]) + 1
    ptext(d, bx, fy(0.0545), "SUN & MOON SYSTEM", PRINT)
    y = fy(0.0480)
    d.rectangle([bx, y, fx(-0.1175), y + 1], fill=SUN)     # a twin stripe, sun and moon
    d.rectangle([fx(-0.1175) + 2, y, fx(BADGE[1]), y + 1], fill=MOON)
    ptext(d, bx, fy(0.0440), "MODEL MS-97", PRINT_SOFT)

    # door
    cx = fx((DOOR[0] + DOOR[1]) / 2)
    # eject and its label
    ex = fx(EJECT[1]) + 3
    ptext(d, ex, fy(0.0230), "OPEN", PRINT)
    ptext(d, ex, fy(0.0230) + 7, "CLOSE", PRINT)
    # eject triangle printed above the button
    ecx = fx((EJECT[0] + EJECT[1]) / 2)
    ey = fy(0.0262)
    d.polygon([(ecx - 4, ey), (ecx + 4, ey), (ecx, ey - 4)], fill=PRINT)
    # controller ports
    for i, r in enumerate(PORTS):
        ptext(d, fx((r[0] + r[1]) / 2), fy(r[0] * 0 + 0.0290), str(i + 1), PRINT, center=True)
    ptext(d, fx((PORTS[0][0] + PORTS[1][1]) / 2), fy(0.0128), "CONTROLLER", PRINT, center=True)
    # memory cards
    for i, r in enumerate(CARDS):
        ptext(d, fx(r[0]) - 6, fy(0.0230), str(i + 1), PRINT)
    ptext(d, fx((CARDS[0][0] + CARDS[1][1]) / 2), fy(0.0137), "MEMORY CARD", PRINT, center=True)
    # pills
    for r, lab in zip(PILLS, PILL_LABELS):
        ptext(d, fx((r[0] + r[1]) / 2), fy(0.0385), lab, PRINT, center=True)
    # power, reset
    ptext(d, fx(POWER[0]), fy(0.0115), "POWER", PRINT, center=True)
    ptext(d, fx((RESET[0] + RESET[1]) / 2), fy(0.0150), "RESET", PRINT, center=True)
    # the jog dial: a printed scale of ticks around it
    kx, ky = fx(KNOB[0]), fy(KNOB[1])
    rr = KNOB_R * FPX
    for k in range(25):
        a = math.radians(-135 + k * 270 / 24)
        r0, r1 = rr + 3, rr + (6 if k % 6 == 0 else 4)
        d.line([(kx + r0 * math.sin(a), ky - r0 * math.cos(a)),
                (kx + r1 * math.sin(a), ky - r1 * math.cos(a))], fill=PRINT if k % 6 == 0 else PRINT_SOFT)
    ptext(d, kx, fy(0.0290), "MULTI JOG", PRINT, center=True)
    ptext(d, fx(NET_LED[1]) + 3, fy(NET_LED[3]), "NET", PRINT)
    # model badge at the right of the top band
    return img


DOOR_B = 0.0016
VFD_B = 0.0012


def draw_door():
    w = int(round((DOOR[1] - DOOR[0] - 2 * DOOR_B) * 2200))
    h = int(round((DOOR[3] - DOOR[2] - 2 * DOOR_B) * 2200))
    img = brushed(w, h, CHAMP, seed=21)
    d = ImageDraw.Draw(img)
    # smoked window
    wx0, wy0, wx1, wy1 = 10, 12, w - 11, h - 20
    d.rectangle([wx0 - 1, wy0 - 1, wx1 + 1, wy1 + 1], fill=GROOVE)
    d.rectangle([wx0, wy0, wx1, wy1], fill="#1c1a1e")
    # the cart inside, seen through smoke: grey shell, label with a sunset and a moon
    cx0, cx1 = wx0 + 12, wx1 - 12
    d.rectangle([cx0, wy0 + 6, cx1, wy1 + 4], fill="#4a4a50")
    d.rectangle([cx0 + 3, wy0 + 6, cx1 - 3, wy0 + 9], fill="#3a3a40")   # grip ridges
    lx0, ly0, lx1, ly1 = cx0 + 8, wy0 + 13, cx1 - 8, wy1 - 2
    for y in range(ly0, ly1 + 1):
        t = (y - ly0) / max(1, ly1 - ly0)
        r = int(70 + 80 * t)
        g = int(40 + 40 * t)
        b = int(90 - 40 * t)
        d.line([(lx0, y), (lx1, y)], fill=(r, g, b))
    # sun half-set on the horizon, moon top-right, hills
    sx, sy = lx0 + (lx1 - lx0) * 0.35, ly1 - 9
    d.ellipse([sx - 9, sy - 9, sx + 9, sy + 9], fill="#d0762a")
    d.polygon([(lx0, ly1), (lx0, ly1 - 8), (lx0 + 30, ly1 - 13), (lx0 + 70, ly1 - 6), (lx1, ly1 - 11), (lx1, ly1)],
              fill="#2a2030")
    mx, my = lx1 - 16, ly0 + 9
    d.ellipse([mx - 5, my - 5, mx + 5, my + 5], fill="#b4c8e0")
    d.ellipse([mx - 2, my - 7, mx + 7, my + 3], fill=(int(70 + 80 * 0.1), int(40 + 40 * 0.1), int(90 - 40 * 0.1)))
    ptext(d, lx0 + 4, ly0 + 4, "LANTERN", "#f0e2bc", scale=2)
    # smoke: a pale reflection along the top of the window
    d.line([(wx0 + 1, wy0 + 1), (wx1 - 1, wy0 + 1)], fill="#4a4650")
    d.rectangle([wx0, wy0, wx1, wy1], outline="#0c0b0d")
    # door print
    ptext(d, wx0, h - 14, "CARTRIDGE DECK", PRINT)
    ptext(d, wx1 - ptext_width("64MB"), h - 14, "64MB", PRINT_SOFT)
    return img


def draw_vfd_frames():
    w = int(round((VFD[1] - VFD[0] - 2 * VFD_B) * 2000))
    h = int(round((VFD[3] - VFD[2] - 2 * VFD_B) * 2000))
    cyan, cyan_ghost = "#7ff7e4", "#163430"
    amber, amber_ghost = "#ffb347", "#30261a"
    bg = "#081010"
    frames = []
    spectra = [
        [3, 5, 7, 6, 4, 6, 8, 5, 3, 2],
        [5, 7, 5, 8, 6, 4, 5, 7, 4, 3],
        [7, 4, 6, 5, 8, 7, 4, 3, 5, 2],
        [4, 6, 8, 4, 5, 8, 6, 4, 2, 4],
    ]
    for spec in spectra:
        img = Image.new("RGB", (w, h), bg)
        d = ImageDraw.Draw(img)

        def seg_digit(x, y, ch, on, off, s=2, L=6):
            # seven segments: a b c d e f g
            segs = {
                "a": [(x + s, y), (x + s + L, y + s - 1)],
                "b": [(x + s + L, y + s), (x + 2 * s + L - 1, y + s + L)],
                "c": [(x + s + L, y + 2 * s + L), (x + 2 * s + L - 1, y + 2 * s + 2 * L)],
                "d": [(x + s, y + 2 * s + 2 * L), (x + s + L, y + 3 * s + 2 * L - 1)],
                "e": [(x, y + 2 * s + L), (x + s - 1, y + 2 * s + 2 * L)],
                "f": [(x, y + s), (x + s - 1, y + s + L)],
                "g": [(x + s, y + s + L), (x + s + L, y + 2 * s + L - 1)],
            }
            lit = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg",
                   "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg"}[ch]
            for k, r in segs.items():
                d.rectangle(r, fill=on if k in lit else off)

        # the MeiNet clock, big
        x = 6
        for i, ch in enumerate("1234"):
            if i == 2:
                d.rectangle([x, 14, x + 1, 15], fill=cyan)
                d.rectangle([x, 22, x + 1, 23], fill=cyan)
                x += 5
            seg_digit(x, 8, ch, cyan, cyan_ghost, s=2, L=7)
            x += 15
        # labels above the clock
        ptext(d, 6, 1, "MEINET", amber)
        ptext(d, 32, 1, "TIME", amber_ghost)
        ptext(d, 52, 1, "CART", cyan)
        ptext(d, 72, 1, "1P", cyan)
        ptext(d, 82, 1, "2P", cyan_ghost)
        # weather: a little sun
        sx, sy = 79, 19
        d.ellipse([sx - 4, sy - 4, sx + 4, sy + 4], fill=amber)
        for k in range(8):
            a = k * math.pi / 4
            d.point((sx + 7 * math.cos(a), sy + 7 * math.sin(a)), fill=amber)
            d.point((sx + 6 * math.cos(a), sy + 6 * math.sin(a)), fill=amber)
        ptext(d, 72, 30, "24C", amber)
        # spectrum analyser on the right: 10 bands, 8 steps
        bx0 = 96
        for i, v in enumerate(spec):
            for k in range(8):
                y1 = h - 12 - k * 4
                col = (amber if k >= 6 else cyan) if k < v else (amber_ghost if k >= 6 else cyan_ghost)
                d.rectangle([bx0 + i * 7, y1 - 2, bx0 + i * 7 + 5, y1], fill=col)
        ptext(d, bx0, h - 8, "SPECTRUM", cyan_ghost)
        # bottom status row
        ptext(d, 6, h - 8, "STEREO", cyan)
        ptext(d, 34, h - 8, "PCM", cyan_ghost)
        ptext(d, 50, h - 8, "ADPCM", cyan)
        frames.append(img)
    sheet = Image.new("RGB", (w, h * len(frames)))
    for i, f in enumerate(frames):
        sheet.paste(f, (0, i * h))
    return sheet, (w, h)


BADGE_B = 0.0008


def draw_badge():
    w = int(round((BADGE[1] - BADGE[0] - 2 * BADGE_B) * 2600))
    h = int(round((BADGE[3] - BADGE[2] - 2 * BADGE_B) * 2600))
    img = Image.new("RGB", (w, h), "#141418")
    d = ImageDraw.Draw(img)
    for y in range(h):   # black anodised with a faint hairline
        if y % 3 == 0:
            d.line([(0, y), (w, y)], fill="#1b1b21")
    gh = h - 12
    g = logo_glyph(int(gh * 1.12), SUN, MOON, None)
    g = g.resize((int(g.size[0] * gh / g.size[1]), gh), Image.NEAREST)
    img.paste(g, (7, 6), g)
    th = int(gh * 0.62)
    t = flatten_alpha(futura_text("MEI", int(th * 1.4), WHITE))
    t = t.resize((int(t.size[0] * th / t.size[1]), th), Image.NEAREST)
    tx = 7 + g.size[0] + 9
    img.paste(t, (tx, 6), t)
    d.ellipse([tx - 6, 6 + gh - 5, tx - 3, 6 + gh - 2], fill=MOON)    # the logo's moon dot
    ptext(d, tx + 1, 6 + gh - 5, "SUN & MOON", "#b9b2a2")
    # diamond-cut edge highlight
    d.rectangle([0, 0, w - 1, h - 1], outline="#8c8678")
    return img


def draw_walnut():
    """A 32 x 32 walnut tile: long, gently waving grain lines in close browns."""
    w, h = 32, 32
    img = Image.new("RGB", (w, h), "#6a4027")
    d = ImageDraw.Draw(img)
    rnd = random.Random(7)
    tones = ["#5c361f", "#74482b", "#53301b", "#7a4d2e"]
    for k in range(9):
        y0 = rnd.uniform(0, h)
        amp = rnd.uniform(0.6, 1.6)
        tone = tones[k % len(tones)]
        for x in range(w):
            y = y0 + amp * math.sin(2 * math.pi * x / w + k)
            d.point((x, int(y) % h), fill=tone)
    return img


VENT_Z0 = 0.030


def draw_vents():
    """The vent field on the cover's back part: four rows of long slots, crisp at a distance."""
    zlen = CHZ1 - VENT_Z0
    s = 420
    w, h = int(round(2 * FX * s)), int(round(zlen * s))
    img = Image.new("RGB", (w, h), GUN)
    d = ImageDraw.Draw(img)
    rows = 3
    for r in range(rows):
        y0 = 4 + r * (h - 6) / rows
        y1 = y0 + (h - 6) / rows - 4
        for k in range(26):
            x = 14 + k * 4.3
            d.rectangle([x, y0, x + 1, y1], fill="#121214")
    return img


def draw_spun(size, dot=True):
    """Spun-aluminium cap: concentric rings, with an orange pointer dot."""
    img = Image.new("RGB", (size, size), "#c9c0aa")
    d = ImageDraw.Draw(img)
    c = (size - 1) / 2
    tones = ["#d8d0bc", "#c2b9a3", "#cec5b0", "#b9b09a", "#e2dbca"]
    for r in range(int(c) + 1, 0, -1):
        d.ellipse([c - r, c - r, c + r, c + r], fill=tones[r % len(tones)])
    d.ellipse([c - 2, c - 2, c + 2, c + 2], fill="#a89f8a")
    if dot:
        d.ellipse([c - 2.5, 3, c + 2.5, 8], fill=SUN)
    return img


def draw_port():
    w, h = 42, 24
    img = Image.new("RGB", (w, h), "#2b2b30")
    d = ImageDraw.Draw(img)
    # a D-shaped socket with seven pin slots
    d.polygon([(4, 5), (w - 5, 5), (w - 8, h - 5), (7, h - 5)], fill="#0d0d10")
    for k in range(7):
        x = 9 + k * 4
        d.rectangle([x, 9, x + 1, h - 9], fill="#b49a52")
    d.line([(4, 4), (w - 5, 4)], fill="#4a4a52")
    return img


def draw_card():
    w, h = 72, 15
    img = brushed(w, h, ["#4a4b52", "#44454b", "#3f4046", "#55565d"], seed=5, streak=False)
    d = ImageDraw.Draw(img)
    d.rectangle([4, 6, w - 5, 8], fill="#0b0b0e")
    d.line([(4, 9), (w - 5, 9)], fill="#6a6b72")
    d.polygon([(w - 12, 2), (w - 6, 2), (w - 9, 4)], fill="#a8a196")
    return img


REAR_W, REAR_H = 255, int(round((CHY1 - CHY0) * 255 / (2 * FX)))


def draw_rear():
    s = 255 / (2 * FX)
    w, h = REAR_W, REAR_H
    img = brushed(w, h, ["#3a3b41", "#37383e", "#3d3e44", "#414248"], seed=3, streak=False)
    d = ImageDraw.Draw(img)

    # The rear is seen from behind: its left (u = 0) is the console's +X side.
    def rx(x):
        return (FX - x) * s
    lab = "#b8b4aa"
    # AV out: yellow, white, red rings (the RCA jacks are geometry; print the panel)
    d.rectangle([rx(0.120), 12, rx(0.072), h - 9], outline=lab)
    ptext(d, rx(0.096), 14, "AV OUT", lab, center=True)
    ptext(d, rx(0.096), h - 16, "V   L   R", lab, center=True)
    # RF and MeiNet antenna
    ptext(d, rx(0.040), 14, "MEINET", "#f0962e", center=True)
    ptext(d, rx(0.040), 21, "ANT IN", lab, center=True)
    d.ellipse([rx(0.040) - 6, 30, rx(0.040) + 6, 42], fill="#c8c0a8", outline="#1c1c1f")
    d.ellipse([rx(0.040) - 2, 34, rx(0.040) + 2, 38], fill="#1c1c1f")
    ptext(d, rx(0.010), 21, "RF OUT", lab, center=True)
    d.ellipse([rx(0.010) - 5, 30, rx(0.010) + 5, 40], fill="#c8c0a8", outline="#1c1c1f")
    d.ellipse([rx(0.010) - 1, 34, rx(0.010) + 1, 36], fill="#1c1c1f")
    # channel switch
    d.rectangle([rx(-0.020) - 6, 32, rx(-0.020) + 6, 38], fill="#1c1c1f")
    d.rectangle([rx(-0.020) - 5, 33, rx(-0.020) - 1, 37], fill="#8a8a90")
    ptext(d, rx(-0.020), 22, "CH 1 2", lab, center=True)
    # rating label
    d.rectangle([rx(-0.052), 14, rx(-0.108), h - 14], fill="#b9b4a8")
    ptext(d, rx(-0.052) + 4, 18, "MEI MS-97", "#2a2a2a")
    ptext(d, rx(-0.052) + 4, 25, "DC 12V 1.5A", "#2a2a2a")
    ptext(d, rx(-0.052) + 4, 32, "JAPAN", "#2a2a2a")
    # DC in
    d.ellipse([rx(-0.132) - 6, 28, rx(-0.132) + 6, 40], fill="#1c1c1f", outline=lab)
    d.ellipse([rx(-0.132) - 1, 33, rx(-0.132) + 1, 35], fill="#c8c0a8")
    ptext(d, rx(-0.132), 18, "DC IN", lab, center=True)
    # vent slots low on the panel
    for k in range(18):
        x = rx(0.140) + k * 4
        d.rectangle([x, h - 7, x + 1, h - 4], fill="#141416")
    return img


# ================================================================ controller numbers
def ctl_outline():
    """Top view (x, z) outline of the pad, counterclockwise seen from above, z toward the back."""
    right = [
        (0.000, 0.040), (0.050, 0.040), (0.064, 0.039), (0.073, 0.034), (0.077, 0.025),
        (0.078, 0.010), (0.077, -0.008), (0.074, -0.024), (0.068, -0.038), (0.059, -0.048),
        (0.048, -0.053), (0.037, -0.052), (0.029, -0.045), (0.023, -0.033), (0.016, -0.023),
        (0.008, -0.019),
    ]
    # walk the right half from the back centre down, the bottom centre, the left half up:
    # clockwise seen from above (x right, z up)
    loop = right[1:] + [(0.0, -0.018)] + [(-x, z) for (x, z) in reversed(right[1:])]
    return loop


def offset_loop(loop, d):
    """Move each point of a closed loop d along its outward normal (d < 0 moves inward)."""
    n = len(loop)
    area = sum(loop[i][0] * loop[(i + 1) % n][1] - loop[(i + 1) % n][0] * loop[i][1] for i in range(n)) / 2
    sign = 1 if area < 0 else -1   # clockwise loops have outward normal to the left of travel
    out = []
    for i in range(n):
        p0, p1, p2 = loop[i - 1], loop[i], loop[(i + 1) % n]
        ns = []
        for a, b in ((p0, p1), (p1, p2)):
            ex, ez = b[0] - a[0], b[1] - a[1]
            L = math.hypot(ex, ez)
            ns.append((sign * -ez / L, sign * ex / L))
        nx, nz = ns[0][0] + ns[1][0], ns[0][1] + ns[1][1]
        L = math.hypot(nx, nz)
        nx, nz = nx / L, nz / L
        cosh = nx * ns[0][0] + nz * ns[0][1]
        k = d / max(cosh, 0.5)
        out.append((round(p1[0] + nx * k, 5), round(p1[1] + nz * k, 5)))
    return out


CTL_RINGS = [(-0.0040, 0.0), (0.0, 0.008), (0.0, 0.023), (-0.0045, 0.030)]   # (offset, y)
CTL_TOP_Y = CTL_RINGS[-1][1]
DPAD_C = (-0.0475, 0.002)
ABXY_C = (0.0475, 0.002)
ABXY_R = 0.0118
STICK_C = (0.0, -0.002)
SELSTART = [(-0.0135, 0.0195), (0.0135, 0.0195)]


def ctl_top_bounds():
    loop = offset_loop(ctl_outline(), CTL_RINGS[-1][0])
    xs = [p[0] for p in loop]
    zs = [p[1] for p in loop]
    return loop, min(xs), max(xs), min(zs), max(zs)


def draw_ctl_top():
    loop, x0, x1, z0, z1 = ctl_top_bounds()
    s = 1650
    w = int(round((x1 - x0) * s))
    h = int(round((z1 - z0) * s))

    def P(x, z):
        return ((x - x0) / (x1 - x0) * (w - 1), (z1 - z) / (z1 - z0) * (h - 1))
    img = Image.new("RGB", (w, h), GUN)
    d = ImageDraw.Draw(img)
    # champagne plate: the outline inset 3.5 mm
    plate = offset_loop(ctl_outline(), CTL_RINGS[-1][0] + 0.002)
    bru = brushed(w, h, CHAMP, seed=33)
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon([P(*p) for p in plate], fill=255)
    img.paste(bru, (0, 0), m)
    inner = offset_loop(ctl_outline(), CTL_RINGS[-1][0] - 0.0022)
    d.line([P(*p) for p in inner] + [P(*inner[0])], fill="#a39a84")
    # recess rings around the d-pad, the buttons and the stick
    for (cx, cz), r in ((DPAD_C, 0.0175), (ABXY_C, 0.0215), (STICK_C, 0.0135)):
        px, pz = P(cx, cz)
        rr = r * s
        d.ellipse([px - rr, pz - rr, px + rr, pz + rr], fill="#b2a88e")
        d.ellipse([px - rr, pz - rr, px + rr, pz + rr], outline="#6f6756")
        d.arc([px - rr + 1, pz - rr + 1, px + rr - 1, pz + rr - 1], 200, 340, fill="#8f8672")
    # stick scale ticks (it is the volume knob of the pad)
    px, pz = P(*STICK_C)
    for k in range(12):
        a = k * math.pi / 6
        r0, r1 = 0.0141 * s, 0.0153 * s
        d.line([(px + r0 * math.cos(a), pz + r0 * math.sin(a)), (px + r1 * math.cos(a), pz + r1 * math.sin(a))],
               fill=PRINT)
    # d-pad arrows printed on the ring
    px, pz = P(*DPAD_C)
    # labels
    for (cx, cz), lab in zip(SELSTART, ["SELECT", "START"]):
        lx, lz = P(cx, cz - 0.0038)
        ptext(d, lx, lz, lab, PRINT, center=True)
    # logo at the top centre
    gh = 16
    g = logo_glyph(18, SUN, MOON, None)
    g = g.resize((int(g.size[0] * gh / g.size[1]), gh), Image.NEAREST)
    t = flatten_alpha(futura_text("MEI", 20, PRINT))
    t = t.resize((int(t.size[0] * 11 / t.size[1]), 11), Image.NEAREST)
    lx, lz = P(0.0, 0.0335)
    total = g.size[0] + 4 + t.size[0]
    img.paste(g, (int(lx - total / 2), int(lz)), g)
    img.paste(t, (int(lx - total / 2 + g.size[0] + 4), int(lz + 3)), t)
    # L and R near the shoulders, and a model line
    lx, lz = P(-0.050, 0.0335)
    ptext(d, lx, lz, "L", PRINT, center=True)
    lx, lz = P(0.050, 0.0335)
    ptext(d, lx, lz, "R", PRINT, center=True)
    lx, lz = P(0.0, -0.0185)
    ptext(d, lx, lz + 1, "HI-FI", PRINT_SOFT, center=True)
    return img


def draw_letter(ch, fg, bg):
    s = 20
    img = Image.new("RGB", (s, s), bg)
    d = ImageDraw.Draw(img)
    ptext(d, s / 2 - 0.5, 5, ch, fg, scale=2, center=True)
    return img


# ================================================================ mesh helpers
def norm(a, b, c):
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    return [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]


def oriented(verts, f, out):
    n = [0.0, 0.0, 0.0]   # Newell's normal: right for concave polygons too
    for i in range(len(f)):
        a, b = verts[f[i]], verts[f[(i + 1) % len(f)]]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    if sum(n[i] * out[i] for i in range(3)) < 0:
        f = list(reversed(f))
    return f


def R(v):
    return [round(x, 5) for x in v]


def slab(node_id, rect, zf, zb, bev, mat_front, mat_side, face=-1):
    """A bevelled plate facing -Z (face=-1) on a panel: front face inset by bev, back left open."""
    x0, x1, y0, y1 = rect
    v = [
        [x0 + bev, y1 - bev, zf], [x1 - bev, y1 - bev, zf], [x1 - bev, y0 + bev, zf], [x0 + bev, y0 + bev, zf],
        [x0, y1, zb], [x1, y1, zb], [x1, y0, zb], [x0, y0, zb],
    ]
    faces, mats = [], []
    faces.append(oriented(v, [0, 1, 2, 3], [0, 0, -1])); mats.append(mat_front)
    for quad, out in (([0, 1, 5, 4], [0, 1, 0]), ([1, 2, 6, 5], [1, 0, 0]),
                      ([2, 3, 7, 6], [0, -1, 0]), ([3, 0, 4, 7], [-1, 0, 0])):
        faces.append(oriented(v, quad, out)); mats.append(mat_side)
    return {"id": node_id, "op": "mesh", "vertices": [R(p) for p in v], "faces": faces,
            "face_materials": mats}


def cyl_z(node_id, cx, cy, z_front, depth, r, segs, mat):
    """A cylinder along Z whose front cap is at z_front (facing -Z)."""
    return {"id": node_id, "op": "cylinder", "radius": r, "height": depth, "segments": segs,
            "material": mat,
            "transform": {"rotate": [-90, 0, 0], "translate": R([cx, cy, z_front + depth / 2])}}


# ================================================================ console recipe
def console_recipe():
    mats = {
        "fascia_l": {"color": "#d0c7b1", "texture": {"image": "art/fascia_l.png", "projection": "fit"}},
        "fascia_r": {"color": "#d0c7b1", "texture": {"image": "art/fascia_r.png", "projection": "fit"}},
        "fascia_edge": {"color": "#cbc2ab"},
        "diamond_cut": {"color": "#f3eee2"},
        "cover": {"color": GUN},
        "vents": {"color": GUN, "texture": {"image": "art/vents.png", "projection": "fit"}},
        "rear": {"color": GUN, "texture": {"image": "art/rear.png", "projection": "fit"}},
        "underside": {"color": "#2a2b30"},
        "walnut": {"color": "#6a4027", "texture": {"image": "art/walnut.png", "projection": "box",
                                                    "scale": [0.12, 0.06]}},
        "door": {"color": "#cfc6b0", "texture": {"image": "art/door.png", "projection": "fit"}},
        "door_edge": {"color": "#e4ddcc"},
        "vfd": {"color": "#0b1414", "class": "emissive",
                "texture": {"sheet": "vfd", "frames": [[0, 0], [0, 1], [0, 2], [0, 3]], "ticks": 9,
                            "projection": "fit"}},
        "glass_edge": {"color": "#1a1b1f"},
        "badge": {"color": "#16161a", "texture": {"image": "art/badge.png", "projection": "fit"}},
        "badge_edge": {"color": "#d8d2c4"},
        "knob": {"color": "#cfc6b0", "smooth": True, "texture": {
            "pattern": "stripes", "size": [16, 8], "colors": ["#d6cdb8", "#a59c86", "#c4bba5", "#8f8672"],
            "params": {"count": 4, "axis": "u"}, "projection": "cylindrical", "scale": [0.006, 0.02]}},
        "spun": {"color": "#cfc6b0", "texture": {"image": "art/spun.png", "projection": "disc"}},
        "button_black": {"color": "#1e1e22"},
        "button_ring": {"color": "#bdb4a0", "smooth": True},
        "pill": {"color": "#b9b09a"},
        "pill_edge": {"color": "#8f8672"},
        "led_red": {"color": LED_RED, "class": "emissive"},
        "led_green": {"color": "#59f08a", "class": "emissive"},
        "port": {"color": "#2b2b30", "texture": {"image": "art/port.png", "projection": "fit"}},
        "port_edge": {"color": "#1c1c20"},
        "card": {"color": "#4a4b52", "texture": {"image": "art/card.png", "projection": "fit"}},
        "foot": {"color": "#b8a46e", "smooth": True},
        "rubber": {"color": "#18181a"},
        "rca_y": {"color": "#e8c228"}, "rca_w": {"color": "#e8e6e0"}, "rca_r": {"color": "#d0302a"},
        "nickel": {"color": "#c8c4ba", "smooth": True},
    }

    nodes = []
    # --- chassis: the gunmetal cover's top (plain front, vented back), the rear panel, the floor.
    # The sides are buried in the cheeks and the front in the fascia, so they are left out.
    zv = VENT_Z0
    v = [
        [-FX, CHY1, CHZ0], [FX, CHY1, CHZ0], [FX, CHY1, zv], [-FX, CHY1, zv], [FX, CHY1, CHZ1], [-FX, CHY1, CHZ1],
        [FX, CHY0, CHZ1], [-FX, CHY0, CHZ1], [FX, CHY0, CHZ0], [-FX, CHY0, CHZ0],
    ]
    faces = [oriented(v, [0, 1, 2, 3], [0, 1, 0]), oriented(v, [3, 2, 4, 5], [0, 1, 0]),
             oriented(v, [5, 4, 6, 7], [0, 0, 1]), oriented(v, [9, 8, 6, 7], [0, -1, 0])]
    nodes.append({"id": "chassis", "op": "mesh", "vertices": [R(p) for p in v], "faces": faces,
                  "face_materials": ["cover", "vents", "rear", "underside"]})

    # --- fascia: front split at x = 0 into two printed halves, a diamond-cut chamfer, top, bottom
    zc = FZ + 0.0015
    v = [
        [-FX, FY1, FZ], [0, FY1, FZ], [FX, FY1, FZ], [FX, FY0, FZ], [0, FY0, FZ], [-FX, FY0, FZ],   # 0-5
        [-FX, TOP, zc], [0, TOP, zc], [FX, TOP, zc],                                                    # 6-8
        [-FX, TOP, FZB], [0, TOP, FZB], [FX, TOP, FZB],                                                 # 9-11
        [-FX, FY0, FZB], [0, FY0, FZB], [FX, FY0, FZB],                                                 # 12-14
    ]
    faces = [
        oriented(v, [0, 1, 4, 5], [0, 0, -1]), oriented(v, [1, 2, 3, 4], [0, 0, -1]),
        oriented(v, [6, 7, 1, 0], [0, 1, -1]), oriented(v, [7, 8, 2, 1], [0, 1, -1]),
        oriented(v, [9, 10, 7, 6], [0, 1, 0]), oriented(v, [10, 11, 8, 7], [0, 1, 0]),
        oriented(v, [5, 4, 13, 12], [0, -1, 0]), oriented(v, [4, 3, 14, 13], [0, -1, 0]),
    ]
    nodes.append({"id": "fascia", "op": "mesh", "vertices": [R(p) for p in v], "faces": faces,
                  "face_materials": ["fascia_l", "fascia_r", "diamond_cut", "diamond_cut",
                                     "fascia_edge", "fascia_edge", "fascia_edge", "fascia_edge"]})

    # --- walnut cheeks, profile in (z, y), extruded across X
    prof_zy = [(0.134, 0.006), (-0.1345, 0.006), (-0.1375, 0.010), (-0.1375, 0.082), (-0.1355, 0.0875),
               (-0.1315, 0.0905), (0.134, 0.0905)]
    pts = [[round(-z, 5), y] for (z, y) in prof_zy]
    t = CHEEK_X1 - CHEEK_X0
    nodes.append({"id": "cheeks", "op": "group", "children": [
        {"id": "cheek", "op": "extrude", "points": pts, "depth": t, "material": "walnut",
         "transform": {"rotate": [0, 90, 0], "translate": [round((CHEEK_X0 + CHEEK_X1) / 2, 5), 0, 0]}}],
        "modifiers": [{"op": "mirror", "axis": "x"}]})

    # --- feet: gold insulators with rubber pads
    nodes.append({"id": "feet", "op": "group", "children": [
        {"id": "insulator", "op": "lathe", "segments": 8, "material": "foot",
         "profile": [[0.0, 0.0], [0.0102, 0.0006], [0.0114, 0.0035], [0.0080, 0.0110]],
         "caps": False,
         "transform": {"translate": [0.118, 0, -0.100]}},
    ], "modifiers": [{"op": "mirror", "axis": "x"}, {"op": "mirror", "axis": "z", "offset": 0.0}]})

    # --- the front parts
    front = []
    zf = FZ - 0.0012
    front.append(slab("badge", BADGE, FZ - 0.0012, FZ + 0.001, BADGE_B, "badge", "badge_edge"))
    front.append(slab("deck_door", DOOR, FZ - 0.0032, FZ + 0.001, DOOR_B, "door", "door_edge"))
    front.append(slab("vfd_window", VFD, FZ - 0.0022, FZ + 0.001, VFD_B, "vfd", "glass_edge"))
    for i, r in enumerate(PILLS):
        front.append(slab("pill_%d" % i, r, FZ - 0.0016, FZ + 0.001, 0.0006, "pill", "pill_edge"))
    front.append(slab("reset", RESET, FZ - 0.0018, FZ + 0.001, 0.0007, "button_black", "button_black"))
    front.append(slab("eject", EJECT, FZ - 0.0018, FZ + 0.001, 0.0007, "pill", "pill_edge"))
    for i, r in enumerate(PORTS):
        front.append(slab("port_%d" % (i + 1), r, FZ - 0.0012, FZ + 0.001, 0.0010, "port", "port_edge"))
    for i, r in enumerate(CARDS):
        front.append(slab("card_%d" % (i + 1), r, FZ - 0.0010, FZ + 0.001, 0.0006, "card", "port_edge"))
    front.append(slab("power_led", LED, FZ - 0.0008, FZ + 0.001, 0.0003, "led_red", "led_red"))
    front.append(slab("net_led", NET_LED, FZ - 0.0008, FZ + 0.001, 0.0003, "led_green", "led_green"))
    # power: a chrome ring and a black push button
    front.append(cyl_z("power_ring", POWER[0], POWER[1], FZ - 0.0012, 0.0022, POWER_R + 0.0016, 14, "button_ring"))
    front.append(cyl_z("power_button", POWER[0], POWER[1], FZ - 0.0036, 0.0030, POWER_R, 14, "button_black"))
    # the multi jog: knurled skirt and a spun-aluminium cap
    kx, ky = KNOB
    front.append({"id": "jog_skirt", "op": "lathe", "segments": 18, "caps": False, "material": "knob",
                  "profile": [[KNOB_R, -0.001], [KNOB_R, 0.0105], [KNOB_R - 0.0012, 0.0132], [KNOB_R - 0.0030, 0.0142]],
                  "transform": {"rotate": [-90, 0, 0], "translate": R([kx, ky, FZ])}})
    front.append({"id": "jog_cap", "op": "cylinder", "radius": KNOB_R - 0.0027, "height": 0.0012, "segments": 18,
                  "material": "spun",
                  "transform": {"rotate": [-90, 0, 0], "translate": R([kx, ky, FZ - 0.0140])}})
    nodes.append({"id": "front", "op": "group", "children": front})

    # --- rear AV jacks (geometry where the panel prints their box)
    back = []
    for i, (x, m) in enumerate(((0.110, "rca_y"), (0.096, "rca_w"), (0.082, "rca_r"))):
        back.append({"id": "rca_%d" % i, "op": "group", "children": [
            {"id": "collar", "op": "cylinder", "radius": 0.0042, "height": 0.006, "segments": 8, "material": m,
             "transform": {"rotate": [90, 0, 0], "translate": R([x, 0.040, CHZ1 + 0.0025])}},
            {"id": "pin", "op": "cylinder", "radius": 0.0018, "height": 0.004, "segments": 6, "material": "nickel",
             "transform": {"rotate": [90, 0, 0], "translate": R([x, 0.040, CHZ1 + 0.0060])}}]})
    nodes.append({"id": "rear_jacks", "op": "group", "children": back})

    return {
        "format": "mei-asset", "version": 1, "name": "hifi_deck_console",
        "budget": {"vertices": 1200, "triangles": 1200},
        "sheets": {"vfd": {"image": "art/vfd_sheet.png", "grid": list(VFD_CELL)}},
        "materials": mats,
        "lighting": {"direction": [-0.4, 0.85, -0.45], "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": nodes,
    }


# ================================================================ controller recipe
def controller_recipe():
    mats = {
        "shell": {"color": GUN, "smooth": True},
        "shell_base": {"color": "#2e2f34"},
        "top": {"color": "#cdc4ad", "texture": {"image": "art/ctl_top.png", "projection": "fit"}},
        "dpad": {"color": "#1f1f23"},
        "walnut": {"color": "#6a4027", "texture": {"image": "art/walnut.png", "projection": "box",
                                                    "scale": [0.08, 0.04]}},
        "dpad_top": {"color": "#34353b"},
        "btn_a": {"color": SUN, "texture": {"image": "art/btn_a.png", "projection": "disc"}},
        "btn_b": {"color": MOON, "texture": {"image": "art/btn_b.png", "projection": "disc"}},
        "btn_x": {"color": "#2a2a2e", "texture": {"image": "art/btn_x.png", "projection": "disc"}},
        "btn_y": {"color": "#2a2a2e", "texture": {"image": "art/btn_y.png", "projection": "disc"}},
        "btn_side": {"color": "#2a2a2e"},
        "knob": {"color": "#cfc6b0", "smooth": True, "texture": {
            "pattern": "stripes", "size": [16, 8], "colors": ["#d6cdb8", "#a59c86", "#c4bba5", "#8f8672"],
            "params": {"count": 4, "axis": "u"}, "projection": "cylindrical", "scale": [0.005, 0.02]}},
        "spun": {"color": "#cfc6b0", "texture": {"image": "art/spun.png", "projection": "disc"}},
        "gate": {"color": "#1e1e22", "smooth": True},
        "pill": {"color": "#b9b09a"},
        "pill_edge": {"color": "#8f8672"},
        "shoulder": {"color": "#c8bfa8"},
        "shoulder_edge": {"color": "#9a917c"},
        "cable": {"color": "#1e1e22", "smooth": True},
    }
    nodes = []
    # --- body: rings of the outline at four heights, a flat printed top and a floor
    base = ctl_outline()
    rings = [offset_loop(base, o) for (o, _) in CTL_RINGS]
    n = len(base)
    verts = []
    for ring, (_, y) in zip(rings, CTL_RINGS):
        for (x, z) in ring:
            verts.append([x, y, z])
    faces, fm = [], []
    for r in range(len(rings) - 1):
        for i in range(n):
            j = (i + 1) % n
            a, b, c, d = r * n + i, r * n + j, (r + 1) * n + j, (r + 1) * n + i
            # outward: away from the ring's own centre line
            ex, ez = verts[b][0] - verts[a][0], verts[b][2] - verts[a][2]
            out = [ez, 0, -ex]
            # decide the outward side from the loop's orientation
            out = [o * LOOP_SIGN for o in out]
            for tri in ([a, b, c], [a, c, d]):
                faces.append(oriented(verts, tri, out)); fm.append(["shell_base", "walnut", "shell"][r])
    top = list(range((len(rings) - 1) * n, len(rings) * n))
    faces.append(oriented(verts, top, [0, 1, 0])); fm.append("top")
    bottom = list(range(0, n))
    faces.append(oriented(verts, bottom, [0, -1, 0])); fm.append("shell_base")
    nodes.append({"id": "body", "op": "mesh", "vertices": [R(p) for p in verts], "faces": faces,
                  "face_materials": fm})

    T = CTL_TOP_Y
    # --- d-pad: a cross, raised 3 mm
    a, b = 0.0046, 0.0128
    cross = [(-a, b), (a, b), (a, a), (b, a), (b, -a), (a, -a), (a, -b), (-a, -b), (-a, -a), (-b, -a), (-b, a), (-a, a)]
    nodes.append({"id": "dpad", "op": "extrude", "points": [[x, y] for (x, y) in cross], "depth": 0.0045,
                  "material": "dpad",
                  "transform": {"rotate": [90, 0, 0], "translate": R([DPAD_C[0], T + 0.0012, DPAD_C[1]])}})
    nodes.append({"id": "dpad_pivot", "op": "cylinder", "radius": 0.0040, "height": 0.0010, "segments": 8,
                  "material": "dpad_top",
                  "transform": {"translate": R([DPAD_C[0], T + 0.0036, DPAD_C[1]])}})
    # --- A B X Y: A right, B down, X up, Y left
    btns = []
    for lab, (dx, dz) in (("a", (1, 0)), ("b", (0, -1)), ("x", (0, 1)), ("y", (-1, 0))):
        x, z = ABXY_C[0] + dx * ABXY_R, ABXY_C[1] + dz * ABXY_R
        btns.append({"id": "btn_" + lab, "op": "lathe", "segments": 10, "caps": False,
                     "profile": [[0.0056, -0.0015], [0.0056, 0.0032], [0.0, 0.0041]],
                     "material": "btn_" + lab,
                     "transform": {"translate": R([x, T, z])}})
    nodes.append({"id": "face_buttons", "op": "group", "children": btns})
    # --- the stick: a knurled volume knob in a black gate
    sx, sz = STICK_C
    nodes.append({"id": "stick_gate", "op": "lathe", "caps": False, "material": "gate",
                  "profile": [[0.0135, -0.001], [0.0130, 0.0012], [0.0110, 0.0022]], "segments": 12,
                  "transform": {"translate": R([sx, T, sz])}})
    nodes.append({"id": "stick_stem", "op": "cylinder", "radius": 0.0060, "height": 0.0040, "segments": 8,
                  "material": "gate", "caps": False, "transform": {"translate": R([sx, T + 0.0030, sz])}})
    nodes.append({"id": "stick_knob", "op": "lathe", "segments": 16, "caps": False, "material": "knob",
                  "profile": [[0.0098, 0.0040], [0.0100, 0.0104], [0.0084, 0.0124]],
                  "transform": {"translate": R([sx, T, sz])}})
    nodes.append({"id": "stick_cap", "op": "lathe", "segments": 16, "caps": False, "material": "spun",
                  "profile": [[0.0086, 0.0119], [0.0, 0.0127]], "transform": {"translate": R([sx, T, sz])}})
    # --- select and start: two slim transport keys
    for (x, z), name in zip(SELSTART, ["select", "start"]):
        r = (x - 0.0060, x + 0.0060, z - 0.0017, z + 0.0017)
        sl = slab(name, r, -0.0016, 0.0010, 0.0005, "pill", "pill_edge")
        # the slab faces -Z; turned +90 about X its face looks up (+Y) and its y becomes z
        sl["transform"] = {"rotate": [90, 0, 0], "translate": [0, T, 0]}
        nodes.append(sl)
    # --- L and R: long shoulder bars on the back edge
    for side, name in ((-1, "l"), (1, "r")):
        x0, x1 = (0.034, 0.066) if side > 0 else (-0.066, -0.034)
        sl = slab("shoulder_" + name, (-x1, -x0, 0.0105, 0.0205), -0.0030, 0.0030, 0.0012,
                  "shoulder", "shoulder_edge")
        # face toward the back (+Z): turned 180 about Y, x and z change sign
        sl["transform"] = {"rotate": [0, 180, 0], "translate": [0, 0, 0.0395]}
        nodes.append(sl)
    # --- cable strain relief
    nodes.append({"id": "cable", "op": "lathe", "segments": 6, "caps": True, "material": "cable",
                  "profile": [[0.0042, -0.002], [0.0036, 0.008], [0.0026, 0.020]],
                  "transform": {"rotate": [90, 0, 0], "translate": [0, 0.012, 0.038]}})
    return {
        "format": "mei-asset", "version": 1, "name": "hifi_deck_controller",
        "budget": {"vertices": 800, "triangles": 800},
        "materials": mats,
        "lighting": {"direction": [-0.4, 0.85, -0.45], "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": nodes,
    }


def loop_sign():
    loop = ctl_outline()
    n = len(loop)
    area = sum(loop[i][0] * loop[(i + 1) % n][1] - loop[(i + 1) % n][0] * loop[i][1] for i in range(n)) / 2
    # edge (ex, ez): for a clockwise loop (area < 0) the outward normal is (-ez, ex)... in x/z
    return -1 if area < 0 else 1


LOOP_SIGN = None
VFD_CELL = None


def main():
    global LOOP_SIGN, VFD_CELL
    os.makedirs(ART, exist_ok=True)
    fas = draw_fascia()
    fas.crop((0, 0, FW // 2, FH)).save(os.path.join(ART, "fascia_l.png"))
    fas.crop((FW // 2, 0, FW, FH)).save(os.path.join(ART, "fascia_r.png"))
    draw_door().save(os.path.join(ART, "door.png"))
    sheet, VFD_CELL = draw_vfd_frames()
    sheet.save(os.path.join(ART, "vfd_sheet.png"))
    draw_badge().save(os.path.join(ART, "badge.png"))
    draw_spun(40).save(os.path.join(ART, "spun.png"))
    draw_port().save(os.path.join(ART, "port.png"))
    draw_card().save(os.path.join(ART, "card.png"))
    draw_walnut().save(os.path.join(ART, "walnut.png"))
    draw_vents().save(os.path.join(ART, "vents.png"))
    draw_rear().save(os.path.join(ART, "rear.png"))
    draw_ctl_top().save(os.path.join(ART, "ctl_top.png"))
    draw_letter("A", "#3a1e08", SUN).save(os.path.join(ART, "btn_a.png"))
    draw_letter("B", "#1c2c44", MOON).save(os.path.join(ART, "btn_b.png"))
    draw_letter("X", WHITE, "#2a2a2e").save(os.path.join(ART, "btn_x.png"))
    draw_letter("Y", WHITE, "#2a2a2e").save(os.path.join(ART, "btn_y.png"))
    LOOP_SIGN = loop_sign()
    for name, rec in (("console", console_recipe()), ("controller", controller_recipe())):
        with open(os.path.join(HERE, name + ".asset.json"), "w") as f:
            json.dump(rec, f, indent=1)
            f.write("\n")
    print("wrote art/ and the two recipes")


if __name__ == "__main__":
    main()
