"""Draws the washing as cutout silhouettes: a T-shirt, a long towel, a blue shirt. Run: python3 draw_art.py"""
import pathlib
from PIL import Image, ImageDraw

out = pathlib.Path(__file__).parent
T = (0, 0, 0, 0)

def shirt(name, body, trim, stripe=None):
    W, H = 32, 32
    im = Image.new("RGBA", (W, H), T)
    d = ImageDraw.Draw(im)
    pts = [(0, 0), (9, 0), (12, 3), (20, 3), (23, 0), (32, 0), (32, 9), (27, 9), (27, 31), (5, 31), (5, 9), (0, 9)]
    d.polygon([(x, y) for x, y in pts], fill=body)
    d.polygon([(12, 3), (20, 3), (16, 8)], fill=T)               # neck hole
    d.line([(12, 3), (16, 8), (20, 3)], fill=trim)
    if stripe:
        for y in range(12, 31, 5):
            d.line([(5, y), (26, y)], fill=stripe)
    im.save(out / name)

def towel(name, body, band):
    W, H = 20, 32
    im = Image.new("RGBA", (W, H), T)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W - 1, H - 1], fill=body)
    d.rectangle([0, H - 6, W - 1, H - 4], fill=band)
    for x in range(0, W, 2):                                     # fringe
        d.line([(x, H - 3), (x, H - 1)], fill=band)
    d.rectangle([0, 0, W - 1, 1], fill=band)
    im.save(out / name)

shirt("wash_shirt_white.png", "#eceae4", "#a8a69e", "#a8c0d8")
shirt("wash_shirt_blue.png", "#3a6ab0", "#2a4a80")
towel("wash_towel.png", "#f0e6c0", "#d8462a")
