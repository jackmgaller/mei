#!/usr/bin/env python3
"""Draws the vending machine's textures (authored art; run once, the PNGs are committed beside)."""
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


DIGITS = {  # 3x5 digits
    "0": "111101101101111", "1": "010110010010111", "2": "111001111100111",
    "3": "111001111001111", "4": "101101111001001", "5": "111100111001111",
    "6": "111100111101111", "7": "111001001001001", "8": "111101111101111",
    "9": "111101111001111",
}


def digits(d, x, y, s, fill):
    for ch in s:
        for i, b in enumerate(DIGITS[ch]):
            if b == "1":
                d.point((x + i % 3, y + i // 3), fill)
        x += 4


def save(img, name):
    img.save(os.path.join(HERE, name))


def window():
    """Display window, 56 x 100: four shelves of cans and bottles with price tags."""
    BG, SHELF, GLINT = hexc("#17181f"), hexc("#4a4d5c"), hexc("#242733")
    SIL, WHITE = hexc("#c4c9d2"), hexc("#f2eee2")
    RED, BLUE, GREEN, ORANGE = hexc("#d23a32"), hexc("#3466c9"), hexc("#3a9a52"), hexc("#ee8a1f")
    YEL, BROWN, PINK = hexc("#f0cf3c"), hexc("#7a4b2a"), hexc("#ec86a8")
    TAG, TAGT = hexc("#e8e2cc"), hexc("#b02a2a")
    im = Image.new("RGBA", (56, 100), BG)
    d = ImageDraw.Draw(im)
    for k in range(0, 100):  # a glint across the glass
        d.point((k * 56 // 100, 99 - k), GLINT)
        d.point((k * 56 // 100 + 1, 99 - k), GLINT)
        d.point((k * 56 // 100 + 2, 99 - k), GLINT)
    rows = [
        [("can", RED), ("can", RED), ("pet", GREEN), ("pet", GREEN), ("can", BLUE)],
        [("can", BROWN), ("can", BROWN), ("can", ORANGE), ("pet", YEL), ("pet", PINK)],
        [("pet", BLUE), ("pet", WHITE), ("can", GREEN), ("can", RED), ("can", BROWN)],
        [("can", ORANGE), ("pet", GREEN), ("pet", BLUE), ("can", PINK), ("can", YEL)],
    ]
    prices = [["120", "120", "150", "150", "130"], ["130", "130", "120", "150", "150"],
              ["150", "140", "120", "120", "130"], ["120", "150", "150", "130", "130"]]
    for r, row in enumerate(rows):
        y0 = 1 + r * 25
        for c, (kind, col) in enumerate(row):
            x0 = 1 + c * 11
            if kind == "can":
                d.rectangle([x0 + 2, y0 + 5, x0 + 8, y0 + 17], fill=col)
                d.line([x0 + 2, y0 + 5, x0 + 8, y0 + 5], fill=SIL)
                d.line([x0 + 2, y0 + 17, x0 + 8, y0 + 17], fill=SIL)
                d.rectangle([x0 + 3, y0 + 8, x0 + 7, y0 + 13], fill=WHITE)
                d.point((x0 + 5, y0 + 10), col)
                d.point((x0 + 4, y0 + 11), col)
            else:
                d.rectangle([x0 + 3, y0 + 1, x0 + 7, y0 + 3], fill=SIL)
                d.rectangle([x0 + 4, y0 + 4, x0 + 6, y0 + 7], fill=col)
                d.rectangle([x0 + 2, y0 + 8, x0 + 8, y0 + 17], fill=col)
                d.rectangle([x0 + 2, y0 + 10, x0 + 8, y0 + 14], fill=WHITE)
                d.point((x0 + 5, y0 + 11), col)
                d.point((x0 + 4, y0 + 12), col)
        d.line([0, y0 + 18, 55, y0 + 18], fill=SHELF)
        d.line([0, y0 + 19, 55, y0 + 19], fill=hexc("#101116"))
        for c in range(5):
            x0 = 1 + c * 11
            d.rectangle([x0, y0 + 20, x0 + 10, y0 + 24], fill=TAG)
            digits(d, x0 + 1, y0 + 20, prices[r][c], TAGT)
    return im


def header():
    """Lit header sign, 80 x 24: the brand, then cold and hot."""
    BLUE, WHITE, RED, DK = hexc("#2a5fa8"), hexc("#f6f2e6"), hexc("#e0443a"), hexc("#16345f")
    im = Image.new("RGBA", (80, 24), BLUE)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 79, 1], fill=WHITE)
    d.rectangle([0, 22, 79, 23], fill=WHITE)
    d.rectangle([3, 4, 36, 19], fill=WHITE)
    text(d, (3, 7), "ぽんぽこ", 8, DK, MARU)
    d.rectangle([40, 3, 76, 11], fill=hexc("#59b6e8"))
    text(d, (42, 3), "つめたい", 8, WHITE)
    d.rectangle([40, 13, 76, 21], fill=RED)
    text(d, (42, 13), "あったか", 8, WHITE)
    return im


def buttons():
    """Button strip, 56 x 10: five lit buttons, the fourth sold out."""
    BODY, LIT, RIM, SOLD, WHITE = hexc("#cfd3da"), hexc("#46d070"), hexc("#7b8190"), hexc("#ff3a2a"), hexc("#f2eee2")
    im = Image.new("RGBA", (56, 10), BODY)
    d = ImageDraw.Draw(im)
    for c in range(5):
        x0 = 1 + c * 11
        sold = (c == 3)
        d.rectangle([x0 + 1, 1, x0 + 9, 8], fill=RIM)
        d.rectangle([x0 + 2, 2, x0 + 8, 7], fill=SOLD if sold else LIT)
        if sold:
            text(d, (x0 + 2, 1), "売切", 6, WHITE)
        else:
            d.line([x0 + 3, 3, x0 + 7, 3], fill=WHITE)
    return im


def panel():
    """Control column, 20 x 64: price display, coin slot, bill slot, return lever."""
    BODY, RIM, DARK, SILV, GOLD = hexc("#d9dde4"), hexc("#7b8190"), hexc("#1b1d26"), hexc("#a9afbb"), hexc("#e8b830")
    RED, LCD = hexc("#d23a32"), hexc("#14301c")
    im = Image.new("RGBA", (20, 64), BODY)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 19, 63], outline=RIM)
    d.rectangle([2, 3, 17, 12], fill=DARK)
    d.rectangle([3, 4, 16, 11], fill=LCD)
    digits(d, 4, 5, "120", hexc("#ff5a3a"))
    d.rectangle([2, 16, 17, 31], fill=SILV, outline=RIM)
    d.rectangle([8, 18, 11, 26], fill=DARK)
    d.ellipse([3, 18, 6, 21], fill=GOLD)
    d.rectangle([2, 34, 17, 42], fill=SILV, outline=RIM)
    d.rectangle([4, 37, 15, 39], fill=DARK)
    d.line([6, 36, 13, 36], fill=hexc("#4a8a5a"))
    d.rectangle([2, 46, 17, 56], fill=RIM)
    d.ellipse([6, 47, 13, 54], fill=RED)
    d.rectangle([4, 58, 15, 62], fill=DARK)
    return im


def flap():
    """Pickup flap, 56 x 22."""
    BG, RIM, DARK, SIL = hexc("#252936"), hexc("#7b8190"), hexc("#0c0d12"), hexc("#a9afbb")
    im = Image.new("RGBA", (56, 22), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 55, 21], outline=RIM)
    d.rectangle([4, 3, 51, 17], fill=DARK)
    d.rectangle([4, 3, 51, 5], fill=hexc("#34394b"))
    d.rectangle([6, 17, 49, 18], fill=SIL)
    text(d, (5, 6), "とりだし口", 9, hexc("#8d93a6"))
    return im


def tanuki():
    """The brand's tanuki mascot, 32 x 48, for the machine's sides."""
    BG, BR, DK, CR, WH, EDGE, BEL = (hexc("#59b6e8"), hexc("#8a5a34"), hexc("#2a1c14"), hexc("#f4e8c8"),
                                      hexc("#fff8e6"), hexc("#2a5fa8"), hexc("#e6cfa0"))
    LEAF = hexc("#3a9a52")
    im = Image.new("RGBA", (32, 48), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 31, 47], outline=EDGE)
    d.rectangle([1, 1, 30, 46], outline=WH)
    d.ellipse([5, 24, 26, 44], fill=BR)
    d.ellipse([9, 28, 22, 43], fill=BEL)
    d.rectangle([4, 30, 7, 36], fill=BR)
    d.rectangle([24, 30, 27, 36], fill=BR)
    d.ellipse([6, 7, 25, 27], fill=BR)
    d.ellipse([5, 5, 11, 11], fill=BR)
    d.ellipse([20, 5, 26, 11], fill=BR)
    d.ellipse([7, 6, 9, 8], fill=CR)
    d.ellipse([22, 6, 24, 8], fill=CR)
    d.ellipse([10, 15, 21, 25], fill=CR)
    d.ellipse([8, 12, 13, 18], fill=DK)
    d.ellipse([18, 12, 23, 18], fill=DK)
    d.point((10, 14), WH)
    d.point((20, 14), WH)
    d.ellipse([14, 17, 17, 19], fill=DK)
    d.line([13, 21, 15, 22], fill=DK)
    d.line([16, 22, 18, 21], fill=DK)
    d.polygon([(13, 3), (18, 3), (16, 7), (14, 7)], fill=LEAF)
    d.ellipse([7, 41, 13, 45], fill=DK)
    d.ellipse([18, 41, 24, 45], fill=DK)
    return im


def bin_label():
    """Recycling bin front, 40 x 44: blue lid for cans, yellow for bottles."""
    BLUE, YEL, WHITE, DK, BODY = hexc("#2f68c0"), hexc("#f0c838"), hexc("#f6f2e6"), hexc("#1b1d26"), hexc("#7e8a96")
    im = Image.new("RGBA", (40, 44), BODY)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 39, 43], outline=hexc("#566069"))
    d.rectangle([3, 3, 36, 19], fill=BLUE)
    text(d, (7, 4), "かん", 13, WHITE)
    d.rectangle([3, 23, 36, 39], fill=YEL)
    text(d, (3, 24), "ペット", 12, DK)
    return im


def cup():
    """Return cup, 20 x 22."""
    BG, RIM, DARK = hexc("#252936"), hexc("#7b8190"), hexc("#0c0d12")
    im = Image.new("RGBA", (20, 22), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 19, 21], outline=RIM)
    d.rectangle([3, 4, 16, 16], fill=DARK)
    d.rectangle([3, 4, 16, 6], fill=hexc("#34394b"))
    d.ellipse([8, 17, 11, 19], fill=hexc("#e8b830"))
    return im


def tanuki_head():
    return tanuki().crop((6, 3, 26, 27))


if __name__ == "__main__":
    for name, fn in [("window", window), ("header", header), ("buttons", buttons), ("panel", panel),
                     ("flap", flap), ("cup", cup), ("tanuki_head", tanuki_head), ("tanuki", tanuki), ("bin_label", bin_label)]:
        save(fn(), f"{name}.png")
