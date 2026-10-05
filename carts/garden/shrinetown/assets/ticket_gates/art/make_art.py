#!/usr/bin/env python3
"""Draws the ticket gates' textures (authored art; run once, the PNGs are committed beside).

From the asset lab's ticket gates (examples/assets/lab/ticket_gates); shrine town adds floor(),
the tiled floor with its tactile band and guide strips painted in, sized to the recipe.
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GOTHIC = "/System/Library/Fonts/ヒラギノ角ゴシック W7.ttc"
MARU = "/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc"


def hexc(s):
    return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def text(d, xy, s, size, fill, font=GOTHIC):
    d.fontmode = "1"
    d.text(xy, s, font=ImageFont.truetype(font, size), fill=fill)


def save(img, name):
    img.save(os.path.join(HERE, name))


def lamp_go():
    """Green arrow, 16 x 16, lit."""
    BG, G, W = hexc("#0d2414"), hexc("#3be06a"), hexc("#c8ffd8")
    im = Image.new("RGBA", (16, 16), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 15, 15], outline=hexc("#1c4a2c"))
    d.rectangle([6, 2, 9, 8], fill=G)
    d.polygon([(2, 8), (13, 8), (7, 14)], fill=G)
    d.line([7, 3, 7, 8], fill=W)
    return im


def lamp_no():
    """Red cross, 16 x 16, lit."""
    BG, R, W = hexc("#2a0c0c"), hexc("#ff3a30"), hexc("#ffc0b8")
    im = Image.new("RGBA", (16, 16), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 15, 15], outline=hexc("#5a1c1c"))
    for k in range(-1, 2):
        d.line([3 + k, 3, 12 + k, 12], fill=R)
        d.line([12 + k, 3, 3 + k, 12], fill=R)
    d.point((4, 3), W)
    return im


def slot():
    """The ticket entrance panel, 16 x 16: an orange ticket on its way into the slot."""
    BODY, RIM, DARK, ORG, W, BLU = hexc("#b8c0c4"), hexc("#6a7478"), hexc("#14181c"), hexc("#f08a2a"), hexc("#f6f2e6"), hexc("#2a5fa8")
    im = Image.new("RGBA", (16, 16), BODY)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 15, 15], outline=RIM)
    d.rectangle([2, 9, 13, 11], fill=DARK)
    d.rectangle([3, 3, 12, 7], fill=ORG)
    d.rectangle([3, 3, 12, 3], fill=hexc("#f8c070"))
    d.line([4, 5, 11, 5], fill=hexc("#b0561c"))
    d.polygon([(5, 13), (10, 13), (7, 15)], fill=BLU)
    return im


def pedside():
    """Pedestal side, 40 x 24: grey shell, a blue band, a little oval plate."""
    G, G2, B, W, RIM = hexc("#c9ced0"), hexc("#b3b9bc"), hexc("#2a63b0"), hexc("#f2eee2"), hexc("#7b8386")
    im = Image.new("RGBA", (40, 24), G)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 39, 23], outline=RIM)
    d.rectangle([1, 15, 38, 19], fill=B)
    d.line([1, 14, 38, 14], fill=W)
    d.line([1, 20, 38, 20], fill=W)
    d.rectangle([1, 1, 38, 2], fill=G2)
    d.ellipse([15, 4, 24, 11], fill=B)
    d.ellipse([17, 6, 22, 9], fill=W)
    return im


def sign():
    """Hanging gate sign, 96 x 24: white on blue."""
    BLUE, W, Y = hexc("#17499a"), hexc("#f6f2e6"), hexc("#f0d040")
    im = Image.new("RGBA", (96, 24), BLUE)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 95, 23], outline=W)
    d.rectangle([2, 2, 93, 21], outline=hexc("#2e66b8"))
    text(d, (5, 3), "改札口", 17, W)
    text(d, (66, 2), "出口", 13, W)
    d.polygon([(66, 18), (66, 21), (62, 19)], fill=Y)
    d.line([64, 19, 90, 19], fill=Y)
    d.polygon([(90, 17), (90, 21), (94, 19)], fill=Y)
    return im


def master():
    """The stationmaster in his booth window, 32 x 28."""
    WALL, WALL2, NAVY, NAVY2, GOLD, SKIN, SKIN2, DK, W, WOOD, WOOD2, GLASS = (
        hexc("#8d7a5a"), hexc("#74644a"), hexc("#1f2f5a"), hexc("#2c4078"), hexc("#f0c838"), hexc("#f2c9a0"),
        hexc("#d9a47c"), hexc("#241a14"), hexc("#f6f2e6"), hexc("#7c5232"), hexc("#5e3c22"), hexc("#9fd6e6"))
    im = Image.new("RGBA", (32, 28), WALL)
    d = ImageDraw.Draw(im)
    for y in range(0, 22, 4):
        d.line([0, y, 31, y], fill=WALL2)
    # a clock on the back wall
    d.ellipse([2, 3, 8, 9], fill=W, outline=DK)
    d.line([5, 6, 5, 4], fill=DK)
    d.line([5, 6, 7, 6], fill=DK)
    # a poster
    d.rectangle([24, 3, 29, 11], fill=hexc("#e8d8a8"))
    d.line([25, 5, 28, 5], fill=hexc("#b03a30"))
    # body
    d.rectangle([9, 16, 22, 27], fill=NAVY)
    d.polygon([(13, 16), (18, 16), (16, 21)], fill=W)
    for y in (22, 25):
        d.point((16, y), GOLD)
    d.rectangle([8, 17, 10, 22], fill=NAVY2)
    d.rectangle([21, 17, 23, 22], fill=NAVY2)
    # head
    d.ellipse([11, 6, 20, 16], fill=SKIN)
    d.point((11, 12), SKIN2)
    d.point((20, 12), SKIN2)
    d.point((14, 11), DK)
    d.point((17, 11), DK)
    d.line([14, 14, 17, 14], fill=hexc("#8a4a3a"))
    d.line([13, 13, 18, 13], fill=hexc("#3a2a20"))
    # cap
    d.rectangle([11, 3, 20, 6], fill=NAVY)
    d.rectangle([12, 2, 19, 3], fill=NAVY2)
    d.line([11, 6, 20, 6], fill=GOLD)
    d.rectangle([10, 7, 21, 7], fill=DK)
    d.point((15, 4), GOLD)
    d.point((16, 4), GOLD)
    # white gloves resting on the counter
    d.rectangle([7, 22, 11, 24], fill=W)
    d.rectangle([20, 22, 24, 24], fill=W)
    # counter
    d.rectangle([0, 24, 31, 27], fill=WOOD)
    d.line([0, 24, 31, 24], fill=hexc("#a87848"))
    d.line([0, 27, 31, 27], fill=WOOD2)
    # glass: frame and a glint
    d.rectangle([0, 0, 31, 27], outline=hexc("#d8dcd8"))
    d.line([27, 14, 29, 12], fill=GLASS)
    d.line([25, 18, 29, 14], fill=GLASS)
    return im


def hours():
    """A small board on the booth, 24 x 16: 'きっぷ' in white on green."""
    G, W = hexc("#1f6a46"), hexc("#f6f2e6")
    im = Image.new("RGBA", (24, 16), G)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 23, 15], outline=W)
    text(d, (0, 3), "きっぷ", 8, W)
    return im


def map_board():
    """A route map poster, 24 x 32."""
    P, W, B, R, G, DK = hexc("#e9e1c8"), hexc("#f6f2e6"), hexc("#2a5fa8"), hexc("#d23a32"), hexc("#3a9a52"), hexc("#3a3a40")
    im = Image.new("RGBA", (24, 32), P)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 23, 31], outline=DK)
    d.rectangle([1, 1, 22, 5], fill=B)
    text(d, (1, 0), "ろせん", 7, W)
    d.line([4, 28, 4, 9], fill=R, width=2)
    d.line([4, 9, 19, 9], fill=R, width=2)
    d.line([4, 18, 19, 26], fill=G, width=1)
    for x, y in ((4, 28), (4, 18), (4, 9), (12, 9), (19, 9), (12, 22), (19, 26)):
        d.rectangle([x - 1, y - 1, x + 1, y + 1], fill=W, outline=DK)
    return im


def clock():
    """A station clock face, 32 x 32, quarter past eight."""
    W, DK, R, ED = hexc("#f6f2e6"), hexc("#1a1d22"), hexc("#d23a32"), hexc("#9ba3ac")
    im = Image.new("RGBA", (32, 32), W)
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, 31, 31], fill=W, outline=ED)
    import math
    for h in range(12):
        a = math.radians(h * 30)
        x0, y0 = 15.5 + 12.5 * math.sin(a), 15.5 - 12.5 * math.cos(a)
        x1, y1 = 15.5 + 14.5 * math.sin(a), 15.5 - 14.5 * math.cos(a)
        d.line([round(x0), round(y0), round(x1), round(y1)], fill=DK, width=2 if h % 3 == 0 else 1)
    d.line([16, 16, 25, 16], fill=DK, width=1)
    d.line([16, 16, 11, 21], fill=DK, width=2)
    d.point((16, 16), R)
    return im


# The floor slab's top: x -3.6..3.6, z -1.5..0.9 at 5 cm a texel (row 0 is the back, z 0.9).
FLOOR_X0, FLOOR_Z1, TEXEL = -3.6, 0.9, 0.05
AISLES = [-2.10, -0.94, 0.22, 1.38, 2.54]   # aisle centres (x), as in ticket_gates.asset.json


def floor():
    """Grey tiles, the yellow tactile band along the front and a guide strip into each aisle."""
    T0, T1, GR = hexc("#8d9296"), hexc("#9aa0a4"), hexc("#6c7276")
    Y, YD = hexc("#f0cf2c"), hexc("#b89410")
    w, h = 144, 48
    im = Image.new("RGBA", (w, h), T0)
    px = im.load()

    def col(x):
        return round((x - FLOOR_X0) / TEXEL)

    def row(z):
        return round((FLOOR_Z1 - z) / TEXEL)

    for y in range(h):
        for x in range(w):
            if x % 6 == 0 or y % 6 == 0:
                px[x, y] = GR
            elif ((x // 6) + (y // 6)) % 2:
                px[x, y] = T1
    def tactile(x0, x1, y0, y1):
        for y in range(y0, y1):
            for x in range(x0, x1):
                px[x, y] = YD if (x % 2 == 1 and y % 2 == 1) else Y
    tactile(0, w, row(-1.0), row(-1.45))
    for a in AISLES:
        tactile(col(a - 0.15), col(a + 0.15), row(0.0), row(-1.0))
    return im


if __name__ == "__main__":
    for name, fn in [("lamp_go", lamp_go), ("lamp_no", lamp_no), ("slot", slot), ("pedside", pedside),
                     ("sign", sign), ("master", master), ("hours", hours), ("clock", clock), ("floor", floor)]:
        save(fn(), f"{name}.png")
