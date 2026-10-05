#!/usr/bin/env python3
"""Draws the rural station's textures (authored art; run once, the PNGs are committed beside).

clock.png, vend_window.png and vend_header.png are copies of the ticket gates' clock and the
vending machine's window and header.
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GOTHIC = "/System/Library/Fonts/ヒラギノ角ゴシック W7.ttc"
MARU = "/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc"
MINCHO = "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc"
AVENIR = "/System/Library/Fonts/Avenir Next Condensed.ttc"


def hexc(s):
    return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


CLEAR = (0, 0, 0, 0)


def text(d, xy, s, size, fill, font=GOTHIC, index=0):
    d.fontmode = "1"
    d.text(xy, s, font=ImageFont.truetype(font, size, index=index), fill=fill)


DIGITS = {
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


def name_board():
    """The station's name board, 96 x 28."""
    W, DK, BL, GR = hexc("#f4f0e2"), hexc("#16181c"), hexc("#1f4f98"), hexc("#a9a590")
    im = Image.new("RGBA", (96, 28), W)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 95, 27], outline=DK)
    d.rectangle([1, 1, 94, 26], outline=GR)
    d.rectangle([2, 2, 93, 4], fill=BL)
    text(d, (5, 6), "夏山駅", 20, DK, MINCHO, 1)
    text(d, (64, 6), "なつやま", 7, DK, GOTHIC)
    text(d, (63, 16), "NATSUYAMA", 7, BL, AVENIR)
    return im


def door():
    """A sliding glass door, 24 x 44: wooden frame, four lights of glass."""
    WD, WD2, GL, GL2, HI = hexc("#6e4a2a"), hexc("#4e331c"), hexc("#a8c9d4"), hexc("#86a9b8"), hexc("#dff0f4")
    im = Image.new("RGBA", (24, 44), WD)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 23, 43], outline=WD2)
    for y0, y1 in ((3, 19), (22, 34), (36, 41)):
        pass
    for (x0, y0, x1, y1) in ((3, 3, 20, 19), (3, 22, 20, 34), (3, 37, 20, 40)):
        d.rectangle([x0, y0, x1, y1], fill=GL)
    d.line([11, 3, 11, 19], fill=WD)
    d.line([12, 3, 12, 19], fill=WD)
    d.line([11, 22, 11, 34], fill=WD)
    d.line([12, 22, 12, 34], fill=WD)
    d.line([3, 11, 20, 11], fill=WD)
    d.rectangle([3, 28, 20, 28], fill=WD)
    for k in range(4):
        d.line([4 + k, 18, 8 + k, 5], fill=HI)
    d.rectangle([20, 20, 21, 25], fill=hexc("#c8b070"))
    return im


def window_ticket():
    """The ticket window, 32 x 24: a dark opening with a counter and a sign."""
    FR, FR2, IN, SIL, GL, SIGN, W = hexc("#f2eee2"), hexc("#b9b39c"), hexc("#3a3128"), hexc("#7b8386"), hexc("#7fa8b8"), hexc("#1f6a46"), hexc("#f6f2e6")
    im = Image.new("RGBA", (32, 24), FR)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 31, 23], outline=FR2)
    d.rectangle([3, 3, 28, 20], fill=IN)
    d.rectangle([5, 5, 26, 10], fill=SIGN)
    text(d, (7, 4), "きっぷ", 7, W)
    d.rectangle([3, 15, 28, 17], fill=hexc("#8a5e38"))
    d.rectangle([13, 11, 18, 14], fill=hexc("#c8b070"))
    d.line([4, 4, 27, 19], fill=GL)
    d.line([6, 4, 27, 17], fill=GL)
    d.rectangle([3, 3, 28, 20], outline=SIL)
    return im


def window_plain():
    """A four-pane window with a lace curtain, 24 x 28."""
    FR, FR2, GL, CU, DK = hexc("#f2eee2"), hexc("#b9b39c"), hexc("#86a9b8"), hexc("#efe6d0"), hexc("#7a6a54")
    im = Image.new("RGBA", (24, 28), FR)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 23, 27], outline=FR2)
    for (x0, y0, x1, y1) in ((2, 2, 10, 12), (13, 2, 21, 12), (2, 15, 10, 25), (13, 15, 21, 25)):
        d.rectangle([x0, y0, x1, y1], fill=GL)
    d.rectangle([2, 2, 10, 5], fill=CU)
    d.rectangle([13, 2, 21, 5], fill=CU)
    for x in range(3, 10, 2):
        d.point((x, 6), CU)
    for x in range(14, 21, 2):
        d.point((x, 6), CU)
    d.line([3, 11, 9, 4], fill=hexc("#cfe4ea"))
    d.line([14, 24, 20, 17], fill=hexc("#cfe4ea"))
    d.rectangle([11, 0, 12, 27], fill=FR2)
    d.rectangle([0, 13, 23, 14], fill=FR2)
    d.rectangle([0, 0, 23, 27], outline=DK)
    return im


def timetable():
    """The timetable board, 32 x 44."""
    P, DK, BL, RD, WH = hexc("#efe8d0"), hexc("#2a2a30"), hexc("#2a5fa8"), hexc("#d23a32"), hexc("#f6f2e6")
    im = Image.new("RGBA", (32, 44), P)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 31, 43], outline=DK)
    d.rectangle([1, 1, 30, 7], fill=DK)
    text(d, (3, 0), "じこく", 7, WH)
    d.rectangle([2, 9, 15, 12], fill=BL)
    d.rectangle([17, 9, 30, 12], fill=RD)
    ups = ["6", "7", "8", "9", "10", "12", "14", "16", "17", "19"]
    mins = ["05", "42", "15", "38", "24", "50", "33", "08", "46", "21"]
    for row in range(6):
        y = 14 + row * 5
        digits(d, 3, y, "06"[row % 2:] + "0", DK) if False else None
        digits(d, 3, y, ["6", "7", "8", "9", "1", "1"][row] + str(row), DK)
        digits(d, 9, y, mins[row][0] + mins[row][1], DK)
        digits(d, 18, y, ["6", "7", "8", "9", "1", "1"][row] + str((row * 3 + 1) % 10), DK)
        digits(d, 24, y, mins[(row + 4) % 10], DK)
    d.line([16, 9, 16, 43], fill=DK)
    return im


def lantern():
    """A hanging station lantern, 16 x 24."""
    RD, DK, YL, W = hexc("#c8322a"), hexc("#1a1210"), hexc("#f0c838"), hexc("#fff0d0")
    im = Image.new("RGBA", (16, 24), RD)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 15, 2], fill=DK)
    d.rectangle([0, 21, 15, 23], fill=DK)
    for y in (6, 11, 16):
        d.line([0, y, 15, y], fill=hexc("#a02420"))
    text(d, (2, 4), "駅", 12, W)
    return im


def pole_sign():
    """The platform's name sign, 96 x 20: the stations either side and ours."""
    W, DK, BL, GR, YL = hexc("#f4f0e2"), hexc("#16181c"), hexc("#1f4f98"), hexc("#7c7a6c"), hexc("#f0c838")
    im = Image.new("RGBA", (96, 20), W)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 95, 19], outline=DK)
    d.rectangle([1, 1, 94, 2], fill=BL)
    d.rectangle([31, 3, 64, 18], fill=BL)
    text(d, (32, 7), "なつやま", 8, W, MARU)
    text(d, (2, 5), "かみやま", 7, DK)
    text(d, (66, 5), "しもやま", 7, DK)
    d.polygon([(2, 15), (2, 18), (0, 16)], fill=GR)
    d.line([3, 16, 26, 16], fill=GR)
    d.line([68, 16, 92, 16], fill=GR)
    d.polygon([(93, 14), (93, 18), (95, 16)], fill=GR)
    return im


def bike(body, body2):
    """A mamachari seen from the side, 48 x 28, on a clear ground."""
    im = Image.new("RGBA", (48, 28), CLEAR)
    d = ImageDraw.Draw(im)
    DK, SIL, BR = hexc("#22242a"), hexc("#c4c9d2"), hexc("#7a5030")
    for cx in (10, 37):
        d.ellipse([cx - 9, 17 - 9 + 1, cx + 9, 17 + 9 + 1], outline=DK)
        d.ellipse([cx - 8, 17 - 8 + 1, cx + 8, 17 + 8 + 1], outline=SIL)
        d.point((cx, 18), DK)
        d.line([cx - 7, 18, cx + 7, 18], fill=SIL)
        d.line([cx, 11, cx, 25], fill=SIL)
    # frame
    d.line([10, 18, 22, 18], fill=body, width=1)
    d.line([22, 18, 19, 8], fill=body, width=2)
    d.line([19, 8, 33, 8], fill=body, width=1)
    d.line([33, 8, 37, 18], fill=body, width=1)
    d.line([22, 18, 33, 9], fill=body2, width=1)
    d.line([10, 18, 19, 9], fill=body, width=1)
    # saddle, handlebar, basket
    d.rectangle([16, 5, 21, 6], fill=DK)
    d.line([33, 8, 35, 4], fill=DK)
    d.line([33, 4, 38, 4], fill=DK)
    d.rectangle([35, 5, 43, 11], outline=SIL)
    d.line([36, 7, 42, 7], fill=SIL)
    d.line([36, 9, 42, 9], fill=SIL)
    # a rear carrier
    d.line([3, 11, 12, 11], fill=SIL)
    return im


def vend_note():
    pass


if __name__ == "__main__":
    for name, img in [("name_board", name_board()), ("door", door()), ("window_ticket", window_ticket()),
                      ("window_plain", window_plain()), ("timetable", timetable()), ("lantern", lantern()),
                      ("pole_sign", pole_sign()), ("bike_blue", bike(hexc("#3a6fc0"), hexc("#7fa6e0"))),
                      ("bike_pink", bike(hexc("#d9608c"), hexc("#f0a0bc")))]:
        save(img, f"{name}.png")
