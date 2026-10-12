#!/usr/bin/env python3
"""Draws leaves.png, the bamboo leaf cutout of the shishi-odoshi (run from anywhere)."""
import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
S = 32
GREENS = [(74, 128, 58), (98, 156, 70), (128, 182, 88), (52, 98, 48)]


def leaf(d, cx, cy, dx, dy, length, col):
    """A lanceolate leaf from (cx, cy) toward (dx, dy)."""
    n = math.hypot(dx, dy)
    dx, dy = dx / n, dy / n
    px, py = -dy, dx
    shape = ((0.0, 0.0), (0.3, 1.6), (0.6, 1.9), (0.85, 1.0), (1.0, 0.0))
    left = [(cx + dx * length * t + px * w, cy + dy * length * t + py * w) for t, w in shape]
    right = [(cx + dx * length * t - px * w, cy + dy * length * t - py * w) for t, w in shape]
    d.polygon(left + right[::-1], fill=col)


im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
# a fan of leaves from the lower middle, drooping at the tips
fan = [(-1.0, -0.15), (-0.8, -0.55), (-0.45, -0.85), (0.0, -1.0), (0.45, -0.85), (0.8, -0.55), (1.0, -0.15)]
for i, (ax, ay) in enumerate(fan):
    leaf(d, 16, 27, ax, ay + 0.35, 17 if abs(ax) < 0.6 else 14, GREENS[i % 3])
leaf(d, 16, 27, 0.0, -1.0, 21, GREENS[3])
leaf(d, 16, 27, -0.3, -1.0, 19, GREENS[1])
leaf(d, 16, 27, 0.3, -1.0, 19, GREENS[2])
# flatten alpha to on/off so the cutout is crisp
px = im.load()
for y in range(S):
    for x in range(S):
        r, g, b, a = px[x, y]
        px[x, y] = (r, g, b, 255) if a >= 128 else (0, 0, 0, 0)
im.save(os.path.join(HERE, "leaves.png"))
