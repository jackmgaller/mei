#!/usr/bin/env python3
"""Draw the MeiNet Receiver's texture sheet: art/sheet.png and art/sheet.sheet.json.

Every cell is drawn at about the texel density the previews show (1.2 mm a texel on the
console, 0.9 mm on the controller). Needs Pillow and the macOS fonts Hiragino Sans GB and
Avenir Next. Run: python3 make_art.py (from anywhere).
"""
import json, math, re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FONTS = Path('/System/Library/Fonts')

# ---- palette ------------------------------------------------------------------------------
BLUE = (47, 76, 122)        # MeiNet blue, the shell
BLUE_D = (31, 52, 88)
BLUE_L = (86, 118, 168)
GREY = (205, 208, 213)      # control-panel grey
GREY_D = (150, 155, 163)
GREY_DD = (98, 103, 112)
INK = (22, 25, 31)          # smoked black
INK_L = (44, 49, 58)
WHITE = (240, 242, 245)
SUN = (247, 168, 64)        # 日
MOON = (170, 196, 236)      # 月
VFD = (102, 255, 217)
VFD_DIM = (18, 62, 56)
VFD_BG = (6, 20, 18)
AMBER = (255, 176, 64)
# Teletext / Fastext
T_RED, T_GREEN, T_YELLOW, T_CYAN = (226, 52, 44), (52, 196, 82), (246, 216, 40), (40, 170, 236)
BARS = [(235, 235, 235), (235, 235, 16), (16, 235, 235), (16, 235, 16), (235, 16, 235),
        (235, 16, 16), (16, 16, 235)]

# ---- fonts --------------------------------------------------------------------------------
F35_ROWS = {
 'A': '.#. #.# ### #.# #.#', 'B': '##. #.# ##. #.# ##.', 'C': '.## #.. #.. #.. .##',
 'D': '##. #.# #.# #.# ##.', 'E': '### #.. ##. #.. ###', 'F': '### #.. ##. #.. #..',
 'G': '.## #.. #.# #.# .##', 'H': '#.# #.# ### #.# #.#', 'I': '### .#. .#. .#. ###',
 'J': '..# ..# ..# #.# .#.', 'K': '#.# #.# ##. #.# #.#', 'L': '#.. #.. #.. #.. ###',
 'M': '#.# ### ### #.# #.#', 'N': '##. #.# #.# #.# #.#', 'O': '.#. #.# #.# #.# .#.',
 'P': '##. #.# ##. #.. #..', 'Q': '.#. #.# #.# ##. .##', 'R': '##. #.# ##. #.# #.#',
 'S': '.## #.. .#. ..# ##.', 'T': '### .#. .#. .#. .#.', 'U': '#.# #.# #.# #.# ###',
 'V': '#.# #.# #.# #.# .#.', 'W': '#.# #.# ### ### #.#', 'X': '#.# #.# .#. #.# #.#',
 'Y': '#.# #.# .#. .#. .#.', 'Z': '### ..# .#. #.. ###',
 '0': '### #.# #.# #.# ###', '1': '.#. ##. .#. .#. ###', '2': '##. ..# .#. #.. ###',
 '3': '##. ..# .#. ..# ##.', '4': '#.# #.# ### ..# ..#', '5': '### #.. ##. ..# ##.',
 '6': '.## #.. ### #.# ###', '7': '### ..# .#. .#. .#.', '8': '### #.# ### #.# ###',
 '9': '### #.# ### ..# ##.', '-': '... ... ### ... ...', '.': '... ... ... ... .#.',
 ':': '... .#. ... .#. ...', '/': '..# ..# .#. #.. #..', '&': '.#. #.# .#. #.# .##',
 ' ': '... ... ... ... ...', '+': '... .#. ### .#. ...',
}
F35 = {k: v.replace(' ', '') for k, v in F35_ROWS.items()}
assert all(len(v) == 15 for v in F35.values())


def text35(d, x, y, s, col):
    """3x5 pixel capitals; returns the width drawn."""
    cx = x
    for ch in s.upper():
        g = F35.get(ch, F35[' '])
        for r in range(5):
            for c in range(3):
                if g[r * 3 + c] == '#':
                    d.point((cx + c, y + r), fill=col)
        cx += 4
    return cx - x - 1


def width35(s):
    return len(s) * 4 - 1


_src = (ROOT / 'src/core/font8x8.h').read_text()
F8 = [[int(x, 16) for x in re.findall(r'0x([0-9A-Fa-f]{2})', m)]
      for m in re.findall(r'\{((?:\s*0x[0-9A-Fa-f]{2},?){8})\s*\}', _src)]


def text8(d, x, y, s, col, rows=8):
    for i, ch in enumerate(s):
        g = F8[ord(ch) - 32]
        for r in range(rows):
            for c in range(8):
                if (g[r] >> c) & 1:
                    d.point((x + i * 8 + c, y + r), fill=col)


def ttf(name, size, index=0):
    return ImageFont.truetype(str(FONTS / name), size, index=index)


def logo_mei(img, x, y, size):
    """明 with 日 in sun orange and 月 in moon blue, drawn at (x, y), `size` px font."""
    f = ttf('Hiragino Sans GB.ttc', size, 2)
    m = Image.new('L', (size * 2, size * 2), 0)
    ImageDraw.Draw(m).text((size // 2, size // 2), '明', font=f, fill=255)
    bb = m.getbbox()
    m = m.crop(bb)
    w, h = m.size
    # split at the emptiest column in the middle third
    cols = [sum(m.getpixel((c, r)) for r in range(h)) for c in range(w)]
    lo, hi = int(w * 0.28), int(w * 0.55)
    split = min(range(lo, hi), key=lambda c: cols[c])
    sun = Image.new('RGBA', m.size, SUN + (255,))
    moon = Image.new('RGBA', m.size, MOON + (255,))
    col = Image.new('RGBA', m.size)
    col.paste(sun.crop((0, 0, split, h)), (0, 0))
    col.paste(moon.crop((split, 0, w, h)), (split, 0))
    img.paste(col, (x, y), m)
    return w, h


def ttext(img, xy, s, font, col, anchor='la'):
    ImageDraw.Draw(img).text(xy, s, font=font, fill=col, anchor=anchor)


def rrect(d, box, r, fill, outline=None):
    d.rounded_rectangle(box, r, fill=fill, outline=outline)


# ---- cells --------------------------------------------------------------------------------
cells = {}
SHEET = Image.new('RGBA', (256, 560), (0, 0, 0, 255))


def cell(name, x, y, w, h):
    cells[name] = [x, y, w, h]
    im = Image.new('RGBA', (w, h), (0, 0, 0, 255))
    return im


def put(name, im):
    x, y, w, h = cells[name]
    SHEET.paste(im, (x, y))


# Console geometry (metres), as make_models.py builds it
W = 0.30


def fx(x):  # fascia texel x
    return (x + W / 2) / W * 248


def fy(y):
    return (0.052 - y) / 0.044 * 36


# -- fascia: 248 x 36, the smoked-black front ----------------------------------------------
im = cell('fascia', 0, 0, 248, 36)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 247, 35), fill=INK)
d.line((0, 0, 247, 0), fill=INK_L)
# logo
w, h = logo_mei(im, 5, 2, 22)
ttext(im, (8 + w, -1), 'MEI', ttf('Avenir Next.ttc', 15, 0), WHITE)
text35(d, 9 + w, 15, 'SUN&MOON', MOON)
# controller ports: dark sockets with a pin strip, numbers above
for i, x in enumerate((-0.124, -0.088)):
    cx, cy = fx(x), fy(0.017)
    rrect(d, (cx - 10, cy - 4, cx + 10, cy + 4), 2, (8, 9, 12))
    d.rectangle((cx - 6, cy - 1, cx + 6, cy), fill=(70, 74, 82))
    text35(d, int(fx(x - 0.0175)) - 1, int(cy - 2), str(i + 1), GREY_D)
# VFD surround: a slightly lighter bezel printed behind the window
d.rectangle((int(fx(-0.061)), int(fy(0.0505)), int(fx(0.075)), int(fy(0.0285))), fill=INK_L)
# memory card slits with labels
for i, x in enumerate((-0.024, 0.040)):
    cx, cy = fx(x), fy(0.017)
    d.rectangle((cx - 19, cy - 1, cx + 19, cy + 1), fill=(4, 4, 6))
    lab = 'MEMORY %d' % (i + 1)
    text35(d, int(cx - width35(lab) / 2), int(cy - 8), lab, GREY_D)
# tuning dial scale
cx, cy = fx(0.112), fy(0.030)
for k in range(9):
    a = math.radians(-135 + k * 270 / 8 - 90)
    r0, r1 = 14.5, 16.5 if k % 2 == 0 else 15.5
    d.line((cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + r1 * math.cos(a), cy + r1 * math.sin(a)),
           fill=AMBER if k == 0 else GREY_D)
text35(d, int(cx - 33), 29, 'TUNE', GREY_D)
put('fascia', im)

# -- VFD window: 128 x 19, emissive ---------------------------------------------------------
im = cell('vfd', 0, 40, 128, 19)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 127, 18), fill=VFD_BG)
for i in range(16):                     # unlit segments
    text8(d, 2 + i * 8, 2, '8', VFD_DIM)
d.rectangle((0, 0, 127, 18), outline=(14, 34, 32))
text8(d, 3, 2, 'P100', VFD)
text8(d, 42, 2, '21', AMBER)
d.point((58, 4), fill=AMBER); d.point((58, 7), fill=AMBER)
text8(d, 60, 2, '47', AMBER)
# sun behind a cloud
d.ellipse((84, 1, 92, 9), fill=SUN)
d.ellipse((87, 5, 95, 11), fill=WHITE); d.ellipse((92, 3, 99, 10), fill=WHITE)
d.rectangle((89, 8, 99, 11), fill=WHITE)
text8(d, 101, 2, '18', VFD)
d.rectangle((118, 2, 120, 4), outline=VFD)
text35(d, 3, 12, 'PAGE', (60, 170, 150))
text35(d, 42, 12, 'TIME', (170, 120, 50))
text35(d, 84, 12, 'WTHR', (60, 170, 150))
text35(d, 112, 12, 'C', (60, 170, 150))
put('vfd', im)

# -- riser: 248 x 14, the status strip (emissive) -------------------------------------------
im = cell('riser', 0, 64, 248, 14)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 247, 13), fill=INK)
x = text35(d, 8, 5, 'SIGNAL', GREY_D) + 12
for k in range(6):
    hh = 2 + k
    d.rectangle((x + k * 5, 10 - hh, x + k * 5 + 3, 10), fill=T_GREEN if k < 5 else (20, 50, 26))
x = 80
d.ellipse((x, 4, x + 5, 9), fill=AMBER); text35(d, x + 9, 5, 'CARRIER', GREY_D)
x = 128
d.ellipse((x, 4, x + 5, 9), fill=T_RED); text35(d, x + 9, 5, 'DATA', GREY_D)
x = 166
d.ellipse((x, 4, x + 5, 9), fill=T_GREEN); text35(d, x + 9, 5, 'POWER', GREY_D)
put('riser', im)


def dx(x):
    return (x + W / 2) / W * 248


def dy(z):   # deck: image top is the rear edge (z -0.024), bottom the front (z -0.104)
    return (-0.024 - z) / 0.080 * 66


# -- deck: 248 x 66, the pale control panel --------------------------------------------------
im = cell('deck', 0, 80, 248, 66)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 247, 65), fill=GREY)
d.line((0, 65, 247, 65), fill=GREY_D)
# colour bars, full width, at the rear edge
bw = 248 / 7
for k, c in enumerate(BARS):
    d.rectangle((int(k * bw), 0, int((k + 1) * bw) - 1, 3), fill=c)
d.line((0, 4, 247, 4), fill=GREY_DD)
# power and reset wells
for x, r, lab in ((-0.122, 11, 'POWER'), (-0.092, 8.5, 'RESET')):
    cx, cy = dx(x), dy(-0.066)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GREY_DD)
    d.ellipse((cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1), fill=GREY_D)
    text35(d, int(cx - width35(lab) / 2), int(cy + r + 4), lab, GREY_DD)
# centre: MeiNet wordmark and the system line
ttext(im, (dx(-0.024), 15), 'MeiNet', ttf('Avenir Next.ttc', 16, 8), BLUE, 'ma')
# broadcast waves after the wordmark
cx, cy = dx(-0.024) + 32, 26
for r in (3, 6, 9):
    d.arc((cx - r, cy - r, cx + r, cy + r), -60, 0, fill=SUN)
d.ellipse((cx - 1, cy - 1, cx + 1, cy + 1), fill=SUN)
for i, s in enumerate(('SUN & MOON SYSTEM', 'BROADCAST RECEIVER')):
    text35(d, int(dx(-0.024) - width35(s) / 2), 40 + i * 7, s, GREY_DD)
# Fastext page keys: icons above, colours under
keys = [(0.050, T_RED, 'TIME'), (0.074, T_GREEN, 'NOW'), (0.098, T_YELLOW, '5DAY'),
        (0.122, T_CYAN, 'MAP')]
for x, c, lab in keys:
    cx, cy = dx(x), dy(-0.068)
    d.rectangle((cx - 9, cy - 5, cx + 9, cy + 5), fill=GREY_DD)
    text35(d, int(cx - width35(lab) / 2), int(cy - 13), lab, GREY_DD)
    d.rectangle((cx - 8, int(cy + 8), cx + 8, int(cy + 9)), fill=c)
text35(d, int(dx(0.086) - width35('MEINET PAGE') / 2), 58, 'MEINET PAGE', GREY_DD)
put('deck', im)


def lx(x):
    return (x + W / 2) / W * 248


def ly(z):   # lid: image top is the rear (z 0.104), bottom the riser (z -0.014)
    return (0.104 - z) / 0.118 * 98


# -- lid: 248 x 98, the blue top -------------------------------------------------------------
im = cell('lid', 0, 150, 248, 98)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 247, 97), fill=BLUE)
# cartridge slot (the cart stands in it)
d.rectangle((int(lx(-0.093)), int(ly(0.041)), int(lx(0.033)), int(ly(0.023))), fill=(6, 8, 12))
text35(d, int(lx(-0.030) - width35('CARTRIDGE') / 2), int(ly(0.010)), 'CARTRIDGE', BLUE_L)
# vents: left block and right block of slits
for i in range(13):
    y = int(ly(0.094)) + i * 5
    d.rectangle((int(lx(-0.140)), y, int(lx(-0.112)), y + 1), fill=BLUE_D)
for i in range(9):
    y = int(ly(0.094)) + i * 5
    d.rectangle((int(lx(0.052)), y, int(lx(0.098)), y + 1), fill=BLUE_D)
# antenna boss ring and the broadcast emblem
cx, cy = lx(0.125), ly(0.086)
d.ellipse((cx - 11, cy - 11, cx + 11, cy + 11), fill=BLUE_D)
cx, cy = lx(0.124), ly(0.030)
for r in (4, 8, 12):
    d.arc((cx - r, cy - r, cx + r, cy + r), 200, 340, fill=SUN)
d.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=SUN)
text35(d, int(cx - width35('MEINET') / 2), int(cy + 5), 'MEINET', MOON)
text35(d, int(lx(0.075) - width35('ANT') / 2), int(ly(0.0)), 'ANT', BLUE_L)
put('lid', im)


def rx(x):   # rear, seen from behind: image left is +X
    return (W / 2 - x) / W * 248


def ry(y):
    return (0.066 - y) / 0.058 * 48


# -- rear: 248 x 48 -------------------------------------------------------------------------
im = cell('rear', 0, 252, 248, 48)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 247, 47), fill=BLUE)
d.rectangle((6, int(ry(0.052)), 241, int(ry(0.014))), fill=BLUE_D)
for x, lab in ((0.106, 'ANT IN'), (0.064, 'RF OUT')):
    cx, cy = rx(x), ry(0.034)
    d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=GREY_D)
    d.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=INK)
    text35(d, int(cx - width35(lab) / 2), int(cy - 13), lab, GREY)
cx, cy = rx(0.0), ry(0.034)
d.polygon([(cx - 16, cy - 5), (cx + 16, cy - 5), (cx + 13, cy + 5), (cx - 13, cy + 5)], fill=INK)
for k in range(7):
    d.point((cx - 12 + k * 4, cy - 1), fill=GREY_D)
text35(d, int(cx - width35('AV MULTI OUT') / 2), int(cy - 13), 'AV MULTI OUT', GREY)
cx, cy = rx(-0.080), ry(0.034)
d.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=INK)
d.ellipse((cx - 1, cy - 1, cx + 1, cy + 1), fill=GREY_D)
text35(d, int(cx - width35('DC IN 12V') / 2), int(cy - 13), 'DC IN 12V', GREY)
# rating sticker
sx, sy = int(rx(-0.112)), int(ry(0.050))
d.rectangle((sx, sy, sx + 30, sy + 18), fill=(196, 198, 202))
text35(d, sx + 2, sy + 2, 'MEI', INK)
text35(d, sx + 2, sy + 8, 'RX-1', INK)
d.rectangle((sx + 2, sy + 14, sx + 28, sy + 15), fill=GREY_DD)
put('rear', im)

# -- side: 96 x 52, plain blue with a parting line -------------------------------------------
im = cell('side', 0, 304, 96, 52)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 95, 51), fill=BLUE)
put('side', im)

# -- cartridge front: 96 x 40 (the lowest 7 rows sit inside the slot) -----------------------
im = cell('label', 100, 304, 96, 40)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 95, 39), fill=(128, 134, 144))
for k in range(3):                       # grip ridges along the top
    d.line((6, 1 + k * 2, 89, 1 + k * 2), fill=(104, 110, 120))
lab = (8, 7, 87, 28)
sky = Image.new('RGBA', (lab[2] - lab[0] + 1, lab[3] - lab[1] + 1))
for yy in range(sky.size[1]):
    t = yy / (sky.size[1] - 1)
    c = tuple(int(a + (b - a) * t) for a, b in zip((40, 120, 214), (150, 206, 246)))
    ImageDraw.Draw(sky).line((0, yy, sky.size[0], yy), fill=c + (255,))
im.paste(sky, lab[:2])
d.ellipse((62, 7, 82, 27), fill=SUN)
d.ellipse((54, 16, 70, 28), fill=WHITE); d.ellipse((64, 14, 80, 28), fill=WHITE)
d.rectangle((56, 22, 84, 28), fill=WHITE)
ttext(im, (11, 7), 'Mei', ttf('Avenir Next.ttc', 11, 0), WHITE)
ttext(im, (11, 17), 'Weather', ttf('Avenir Next.ttc', 9, 2), WHITE)
d.rectangle(lab, outline=(232, 234, 238))
put('label', im)

# -- tuning knob cap: 32 x 32 disc ----------------------------------------------------------
im = cell('knob', 200, 304, 32, 32)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 31, 31), fill=(58, 62, 70))
d.ellipse((1, 1, 30, 30), fill=(84, 89, 98))
d.ellipse((5, 5, 26, 26), fill=(118, 124, 134))
d.ellipse((8, 8, 23, 23), fill=(150, 156, 166))
d.line((15.5, 2, 15.5, 9), fill=AMBER, width=2)
put('knob', im)

# -- power (sun) and reset (moon) caps: 24 x 24 discs ---------------------------------------
im = cell('pwr', 0, 360, 24, 24)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 23, 23), fill=(214, 128, 40))
d.ellipse((2, 2, 21, 21), fill=SUN)
d.ellipse((7, 7, 16, 16), outline=WHITE)
d.line((11.5, 5, 11.5, 11), fill=WHITE)
put('pwr', im)
im = cell('rst', 30, 360, 24, 24)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 23, 23), fill=(126, 156, 204))
d.ellipse((2, 2, 21, 21), fill=MOON)
d.ellipse((7, 6, 17, 16), fill=WHITE)
d.ellipse((10, 4, 20, 14), fill=MOON)
put('rst', im)

# ---- controller -----------------------------------------------------------------------------
CW, CZ0, CZ1 = 0.077, -0.066, 0.046


def cx_(x):
    return (x + CW) / (2 * CW) * 174


def cz_(z):
    return (CZ1 - z) / (CZ1 - CZ0) * 127


im = cell('pad', 0, 390, 174, 127)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 173, 126), fill=BLUE)
# the grey control panel across the middle, as on the console's deck
rrect(d, (cx_(-0.030), cz_(0.050), cx_(0.030), cz_(-0.020)), 6, GREY)
d.line((cx_(-0.030), cz_(-0.020) + 1, cx_(0.030), cz_(-0.020) + 1), fill=BLUE_D)
# d-pad and button wells
c = (cx_(-0.050), cz_(0.012)); r = 19
d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=BLUE_D)
d.ellipse((c[0] - r + 2, c[1] - r + 2, c[0] + r - 2, c[1] + r - 2), fill=GREY_D)
c = (cx_(0.050), cz_(0.012)); r = 22
d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=BLUE_D)
d.ellipse((c[0] - r + 2, c[1] - r + 2, c[0] + r - 2, c[1] + r - 2), fill=GREY_D)
c = (cx_(-0.040), cz_(-0.030)); r = 15
d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=BLUE_D)
d.ellipse((c[0] - r + 2, c[1] - r + 2, c[0] + r - 2, c[1] + r - 2), fill=INK_L)
# centre: the smoked window with the logo, colour bars under it
x0, x1, z0, z1 = cx_(-0.026), cx_(0.026), cz_(0.042), cz_(0.019)
rrect(d, (x0, z0, x1, z1), 3, INK)
w, h = logo_mei(im, int(x0 + 4), int(z0 + 3), 19)
ttext(im, (x0 + 6 + w, z0 + 3), 'MEI', ttf('Avenir Next.ttc', 14, 0), WHITE)
bw = (x1 - x0 - 6) / 7
for k, col in enumerate(BARS):
    d.rectangle((int(x0 + 3 + k * bw), int(z1 + 3), int(x0 + 3 + (k + 1) * bw) - 1, int(z1 + 5)), fill=col)
# select / start labels
for x, lab in ((-0.011, 'SELECT'), (0.011, 'START')):
    text35(d, int(cx_(x) - width35(lab) / 2), int(cz_(-0.007)), lab, GREY_DD)
# right grip: the broadcast waves
c = (cx_(0.044), cz_(-0.034))
for r in (3, 6, 9):
    d.arc((c[0] - r, c[1] - r, c[0] + r, c[1] + r), 200, 340, fill=SUN)
d.ellipse((c[0] - 1, c[1] - 1, c[0] + 1, c[1] + 1), fill=SUN)
text35(d, int(c[0] - width35('MEINET') / 2), int(c[1] + 4), 'MEINET', MOON)
put('pad', im)

# face buttons: Fastext colours with their letter
for i, (n, col) in enumerate((('a', T_YELLOW), ('b', T_CYAN), ('x', T_GREEN), ('y', T_RED))):
    im = cell('btn_' + n, 180 + (i % 2) * 20, 390 + (i // 2) * 20, 16, 16)
    d = ImageDraw.Draw(im)
    dark = tuple(int(v * 0.72) for v in col)
    d.rectangle((0, 0, 15, 15), fill=dark)
    d.ellipse((1, 1, 14, 14), fill=col)
    ttext(im, (8, 8), n.upper(), ttf('Avenir Next.ttc', 11, 0), WHITE if n in 'by' else INK, 'mm')
    put('btn_' + n, im)
im = cell('stick', 180, 432, 24, 24)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 23, 23), fill=(70, 76, 86))
for r, c in ((10, (96, 102, 112)), (7, (80, 86, 96)), (4, (96, 102, 112))):
    d.ellipse((11.5 - r, 11.5 - r, 11.5 + r, 11.5 + r), outline=c)
put('stick', im)

(HERE / 'art').mkdir(exist_ok=True)
SHEET.convert('RGB').save(HERE / 'art/sheet.png')
(HERE / 'art/sheet.sheet.json').write_text(json.dumps(
    {'format': 'mei-sheet', 'version': 1, 'cells': cells}, indent=1) + '\n')
print('wrote art/sheet.png with', len(cells), 'cells')
