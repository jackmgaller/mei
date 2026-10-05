#!/usr/bin/env python3
"""Draws the city bus's PNGs next to this script: windows, windscreens, doors, signs, plate, ad, hub.

Text is set in Hiragino Sans GB (a macOS system font); the outputs are committed.
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"

CREAM = (234, 226, 204)
GREEN = (46, 139, 87)
GLASS_HI = (74, 128, 150)
GLASS = (48, 92, 112)
GLASS_LO = (30, 62, 78)
SEAT = (20, 42, 54)
SKIN = (240, 200, 160)


def font(size):
    return ImageFont.truetype(FONT, size)


def save(im, name, colors=None):
    if colors:
        im = im.convert("RGB").quantize(colors=colors, dither=Image.Dither.NONE).convert("RGB")
    im.save(os.path.join(HERE, name))


def window(name, passengers):
    """A 32 x 32 side window: cream frame, tinted glass, a sliding pane, seat backs, passengers."""
    im = Image.new("RGB", (32, 32), CREAM)
    d = ImageDraw.Draw(im)
    d.rectangle([2, 2, 29, 29], fill=GLASS)
    d.rectangle([2, 2, 29, 9], fill=GLASS_HI)
    d.rectangle([2, 10, 29, 12], fill=(60, 110, 130))
    # the sliding pane: its frame, offset to one side
    d.rectangle([13, 14, 29, 29], outline=CREAM)
    d.line([(13, 14), (13, 29)], fill=CREAM)
    # seat backs along the bottom
    d.rectangle([4, 23, 11, 29], fill=SEAT)
    d.rectangle([17, 23, 26, 29], fill=SEAT)
    # hanging straps
    for x in (7, 16, 25):
        d.line([(x, 2), (x, 5)], fill=(235, 235, 235))
        d.rectangle([x - 1, 5, x + 1, 7], outline=(235, 235, 235))
    for cx, tone in passengers:
        d.ellipse([cx - 3, 14, cx + 3, 20], fill=tone)
        d.rectangle([cx - 5, 21, cx + 5, 29], fill=(150, 70, 70) if tone == SKIN else (70, 100, 160))
    d.rectangle([0, 0, 31, 31], outline=(190, 182, 160))
    save(im, name)


def windscreen(name, driver):
    im = Image.new("RGB", (32, 32), CREAM)
    d = ImageDraw.Draw(im)
    d.rectangle([1, 1, 30, 30], fill=GLASS)
    for i in range(5):
        d.line([(0 + i * 3, 30), (14 + i * 3, 1)], fill=GLASS_HI)
    d.polygon([(6, 30), (14, 30), (24, 1), (19, 1)], fill=(150, 190, 205))
    # a wiper
    d.line([(2, 29), (24, 12)], fill=(10, 10, 10), width=2)
    # dashboard
    d.rectangle([1, 25, 30, 30], fill=(40, 40, 46))
    if driver:
        d.ellipse([15, 10, 23, 19], fill=SKIN)          # head
        d.pieslice([14, 6, 24, 16], 180, 360, fill=(30, 40, 90))   # cap
        d.rectangle([13, 10, 25, 11], fill=(30, 40, 90))
        d.rectangle([12, 19, 26, 26], fill=(60, 80, 130))  # shoulders
        d.rectangle([10, 24, 13, 26], fill=(245, 245, 245))   # white gloves on the wheel
        d.rectangle([25, 24, 28, 26], fill=(245, 245, 245))
    else:
        d.ellipse([4, 5, 8, 12], fill=(230, 110, 130))   # a charm hanging from the mirror
        d.line([(6, 1), (6, 5)], fill=(235, 235, 235))
    d.rectangle([0, 0, 31, 31], outline=(190, 182, 160))
    save(im, name)


def door():
    """32 x 64: a pair of folding leaves, glass above, green panel below."""
    im = Image.new("RGB", (32, 64), CREAM)
    d = ImageDraw.Draw(im)
    for x0, x1 in ((2, 15), (17, 29)):
        d.rectangle([x0, 2, x1, 44], fill=GLASS)
        d.rectangle([x0, 2, x1, 14], fill=GLASS_HI)
        d.rectangle([x0, 46, x1, 61], fill=GREEN)
        d.rectangle([x0, 46, x1, 61], outline=(30, 100, 62))
    d.rectangle([15, 2, 16, 61], fill=(25, 25, 28))      # rubber edge
    d.rectangle([0, 0, 31, 63], outline=(190, 182, 160))
    d.rectangle([5, 36, 12, 42], fill=SEAT)
    # a step warning at the bottom
    for x in range(2, 30, 4):
        d.rectangle([x, 62, x + 1, 63], fill=(230, 200, 40))
    save(im, "door.png")


def sign():
    """96 x 20: the front destination blind, amber on black."""
    im = Image.new("RGB", (96, 20), (14, 12, 10))
    d = ImageDraw.Draw(im)
    amber = (255, 176, 40)
    d.rectangle([2, 2, 21, 17], outline=amber)
    d.text((4, 3), "07", font=font(13), fill=amber)
    d.text((24, 3), "みどり台駅前", font=font(12), fill=amber)
    d.text((24, 15), "ワンマン", font=font(5), fill=(90, 220, 120))
    save(im, "sign.png", 12)


def rear_sign():
    im = Image.new("RGB", (32, 12), (14, 12, 10))
    d = ImageDraw.Draw(im)
    amber = (255, 176, 40)
    d.text((2, 0), "07", font=font(11), fill=amber)
    d.text((17, 2), "台", font=font(9), fill=amber)
    save(im, "rear_sign.png", 6)


def plate():
    im = Image.new("RGB", (32, 16), (240, 240, 236))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 31, 15], outline=(30, 90, 60))
    d.text((3, 0), "みどり", font=font(6), fill=(30, 90, 60))
    d.text((17, 0), "200", font=font(6), fill=(30, 90, 60))
    d.text((2, 6), "あ", font=font(8), fill=(30, 90, 60))
    d.text((11, 7), "07-12", font=font(7), fill=(30, 90, 60))
    save(im, "plate.png")


def ad():
    """128 x 20: the livery's name along the side."""
    im = Image.new("RGB", (128, 20), CREAM)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 127, 19], outline=GREEN)
    d.rectangle([2, 2, 125, 17], outline=(230, 190, 50))
    # a tiny bus
    d.rectangle([6, 6, 24, 14], fill=GREEN)
    d.rectangle([8, 8, 22, 10], fill=(150, 200, 220))
    d.ellipse([8, 12, 12, 16], fill=(20, 20, 20))
    d.ellipse([18, 12, 22, 16], fill=(20, 20, 20))
    d.text((30, 3), "みどり市営バス", font=font(13), fill=GREEN)
    save(im, "ad.png", 16)


def hub():
    im = Image.new("RGB", (16, 16), (60, 60, 64))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, 15, 15], fill=(150, 154, 160))
    d.ellipse([3, 3, 12, 12], outline=(100, 104, 110))
    d.ellipse([5, 5, 10, 10], fill=(70, 72, 78))
    for x, y in ((7, 1), (7, 13), (1, 7), (13, 7), (3, 3), (12, 3), (3, 12), (12, 12)):
        d.point((x, y), fill=(40, 40, 44))
    save(im, "hub.png")


if __name__ == "__main__":
    window("win_a.png", [])
    window("win_b.png", [(8, SKIN)])
    window("win_c.png", [(21, (240, 210, 170)), (7, (250, 230, 200))])
    windscreen("screen_l.png", False)
    windscreen("screen_r.png", True)
    door()
    sign()
    rear_sign()
    plate()
    ad()
    hub()
