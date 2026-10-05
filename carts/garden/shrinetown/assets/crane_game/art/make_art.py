#!/usr/bin/env python3
"""Draws the crane game's PNGs next to this script: sign, panel, side, label, face, glare.

Text is set in Hiragino Sans GB (a macOS system font); the outputs are committed.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def font(size):
    return ImageFont.truetype(FONT, size)


def star(d, cx, cy, r, fill):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.42
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def outlined(d, xy, text, f, fill, edge, w=1):
    x, y = xy
    for dx in range(-w, w + 1):
        for dy in range(-w, w + 1):
            if dx or dy:
                d.text((x + dx, y + dy), text, font=f, fill=edge)
    d.text((x, y), text, font=f, fill=fill)


def hard(im, threshold=110):
    """No antialiasing: text edges become the nearest of the two colours."""
    return im


def sign():
    W, H = 160, 40
    im = Image.new("RGB", (W, H), (214, 38, 120))
    d = ImageDraw.Draw(im)
    for y in range(H):  # a pink-to-orange vertical ramp in bands
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=(int(214 + 30 * t), int(38 + 60 * t), int(120 - 50 * t)))
    d.rectangle([0, 0, W - 1, H - 1], outline=(255, 236, 120))
    d.rectangle([2, 2, W - 3, H - 3], outline=(255, 255, 255))
    for cx, cy, r in ((10, 12, 6), (150, 27, 6), (146, 10, 4), (14, 30, 4)):
        star(d, cx, cy, r, (255, 240, 90))
    f = font(18)
    outlined(d, (17, 10), "クレーンゲーム", f, (255, 252, 230), (120, 20, 80), 1)
    im = im.quantize(colors=48, dither=Image.Dither.NONE).convert("RGB")
    im.save(os.path.join(HERE, "sign.png"))


def panel():
    W, H = 96, 40
    im = Image.new("RGB", (W, H), (58, 40, 90))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W - 1, H - 1], outline=(255, 214, 90))
    # joystick well, left
    d.ellipse([8, 9, 34, 35], fill=(30, 22, 52), outline=(150, 130, 190))
    d.ellipse([14, 15, 28, 29], outline=(90, 74, 130))
    # arrows round the stick
    for pts in (((21, 3), (17, 8), (25, 8)), ((21, 38), (17, 33), (25, 33)),
                ((3, 22), (8, 18), (8, 26)), ((39, 22), (34, 18), (34, 26))):
        d.polygon(pts, fill=(255, 214, 90))
    # two buttons
    for cx, col in ((52, (60, 150, 240)), (70, (80, 210, 120))):
        d.ellipse([cx - 8, 6, cx + 8, 22], fill=(30, 22, 52), outline=col)
    f = font(9)
    d.text((43, 25), "おろす", font=f, fill=(255, 255, 255))
    # coin plate, right
    d.rectangle([77, 5, 93, 35], fill=(190, 194, 204), outline=(255, 255, 255))
    d.rectangle([84, 8, 86, 15], fill=(30, 30, 40))
    d.text((78, 17), "100", font=font(7), fill=(40, 40, 60))
    d.text((81, 26), "円", font=font(8), fill=(40, 40, 60))
    im = im.quantize(colors=32, dither=Image.Dither.NONE).convert("RGB")
    im.save(os.path.join(HERE, "panel.png"))


def side():
    W, H = 64, 40
    im = Image.new("RGB", (W, H), (255, 244, 214))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W - 1, H - 1], outline=(214, 38, 120))
    d.rectangle([2, 2, W - 3, H - 3], outline=(46, 196, 201))
    star(d, 10, 9, 6, (255, 200, 40))
    star(d, 54, 31, 5, (255, 120, 150))
    star(d, 52, 9, 3, (46, 196, 201))
    outlined(d, (12, 12), "GET!", font(17), (214, 38, 120), (255, 255, 255), 1)
    d.text((20, 3), "とって", font=font(8), fill=(60, 40, 90))
    d.text((20, 29), "ゲット", font=font(7), fill=(60, 40, 90))
    im = im.quantize(colors=24, dither=Image.Dither.NONE).convert("RGB")
    im.save(os.path.join(HERE, "side.png"))


def label():
    W, H = 96, 16
    im = Image.new("RGB", (W, H), (255, 236, 120))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W - 1, H - 1], outline=(60, 40, 90))
    d.text((6, 1), "とりだしぐち", font=font(13), fill=(60, 40, 90))
    im = im.quantize(colors=8, dither=Image.Dither.NONE).convert("RGB")
    im.save(os.path.join(HERE, "label.png"))


def face():
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ink = (28, 22, 30, 255)
    d.rectangle([3, 4, 4, 6], fill=ink)
    d.rectangle([11, 4, 12, 6], fill=ink)
    d.rectangle([7, 7, 8, 8], fill=(214, 90, 110, 255))
    d.point([(6, 9), (9, 9)], fill=ink)
    d.point([(7, 10), (8, 10)], fill=ink)
    d.point([(2, 8), (3, 8), (12, 8), (13, 8)], fill=(255, 130, 150, 255))
    im.save(os.path.join(HERE, "face.png"))


def glare():
    S = 32
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for off, w in ((4, 3), (11, 1), (18, 5)):
        d.polygon([(off, S), (off + w, S), (off + w + S * 0.9, 0), (off + S * 0.9, 0)],
                  fill=(236, 246, 255, 255))
    px = im.load()
    for y in range(S):
        for x in range(S):
            if px[x, y][3] < 128:
                px[x, y] = (0, 0, 0, 0)
    im.save(os.path.join(HERE, "glare.png"))


if __name__ == "__main__":
    sign()
    panel()
    side()
    label()
    face()
    glare()
