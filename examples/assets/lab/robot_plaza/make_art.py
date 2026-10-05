#!/usr/bin/env python3
"""Draws the small PNGs robot_plaza reads (art/*.png). Run from anywhere; needs Pillow."""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "art")
os.makedirs(ART, exist_ok=True)


def save(img, name):
    img.save(os.path.join(ART, name))


def disc(d, cx, cy, r, fill):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


# The faceplate: a dark screen with two big round eyes, cheeks and a small smile (40 x 22).
def face():
    im = Image.new("RGB", (40, 22), "#1b2838")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 39, 21], outline="#2c4a5c")
    for cx in (12, 28):
        disc(d, cx, 9, 7, "#fff1a8")
        disc(d, cx + 1, 10, 4, "#3a97a8")
        disc(d, cx + 1, 10, 2, "#0d1620")
        d.rectangle([cx - 2, 6, cx - 1, 7], fill="#ffffff")
    d.line([(6, 1), (11, 0)], fill="#7fd0da")
    d.line([(29, 0), (34, 1)], fill="#7fd0da")
    for cx in (5, 35):
        d.ellipse([cx - 3, 15, cx + 3, 18], fill="#e0707f")
    smile = [(15, 15), (16, 17), (17, 18), (18, 19), (19, 19), (20, 19), (21, 19), (22, 19),
             (23, 19), (24, 18), (25, 17), (26, 15)]
    for p in smile:
        d.point(p, fill="#ffe9c4")
        d.point((p[0], p[1] + 1), fill="#ffe9c4")
    return im


# The chest badge: a round plate with a heart (32 x 32).
def badge():
    im = Image.new("RGB", (32, 32), "#efe3c4")
    d = ImageDraw.Draw(im)
    disc(d, 15.5, 15.5, 15, "#2f3b4a")
    disc(d, 15.5, 15.5, 13, "#e8862a")
    disc(d, 15.5, 15.5, 11, "#fff6dc")
    disc(d, 12, 13, 4, "#d6403c")
    disc(d, 20, 13, 4, "#d6403c")
    d.polygon([(7, 15), (25, 15), (16, 25)], fill="#d6403c")
    d.rectangle([11, 10, 12, 11], fill="#ff9a8a")
    return im


# The drinks machine front (20 x 40).
def vending():
    im = Image.new("RGB", (20, 40), "#d63a3a")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 19, 39], outline="#8e2424")
    d.rectangle([2, 2, 17, 7], fill="#fff6dc")
    d.rectangle([3, 3, 9, 6], fill="#3a97a8")
    d.rectangle([11, 3, 16, 6], fill="#e8862a")
    d.rectangle([2, 9, 17, 29], fill="#1b2838")
    cans = ["#3a97a8", "#fff6dc", "#e8862a", "#6fbf5a", "#f2c230", "#d6403c"]
    for row in range(4):
        for col in range(4):
            x = 3 + col * 4
            y = 10 + row * 5
            d.rectangle([x, y + 1, x + 2, y + 4], fill=cans[(row * 2 + col) % len(cans)])
            d.point((x, y + 1), fill="#ffffff")
    d.rectangle([2, 31, 7, 37], fill="#2f3b4a")
    d.rectangle([3, 32, 6, 33], fill="#f2c230")
    d.rectangle([10, 31, 17, 37], fill="#14202b")
    d.rectangle([11, 34, 16, 36], fill="#000000")
    return im


# The plaque at the plinth's foot (32 x 16).
def plaque():
    im = Image.new("RGB", (32, 16), "#2d5a45")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 31, 15], outline="#d8c27a")
    d.rectangle([2, 2, 29, 13], outline="#8fb59c")
    try:
        font = ImageFont.load_default(10)
    except TypeError:
        font = ImageFont.load_default()
    d.text((8, 0), "MEI", fill="#fff6dc", font=font)
    for i, x in enumerate(range(5, 27, 3)):
        d.rectangle([x, 11, x + 1, 11], fill="#d8c27a")
    return im


save(face(), "face.png")
save(badge(), "badge.png")
save(vending(), "vending.png")
save(plaque(), "plaque.png")
print("art written to", ART)
