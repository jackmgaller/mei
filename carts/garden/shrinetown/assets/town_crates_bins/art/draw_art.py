"""Draws the two beer-crate sides (yellow and red slatted plastic). Run: python3 draw_art.py"""
import pathlib
from PIL import Image, ImageDraw

out = pathlib.Path(__file__).parent

def crate(name, body, rim, slot):
    W, H = 32, 20
    im = Image.new("RGBA", (W, H), body)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W - 1, 2], fill=rim)                      # top rim
    d.rectangle([0, H - 3, W - 1, H - 1], fill=rim)              # foot rim
    for row in (5, 11):
        for x in range(3, W - 3, 5):
            d.rectangle([x, row, x + 2, row + 3], fill=slot)     # hand slots / drain holes
    d.rectangle([0, 0, 1, H - 1], fill=rim)                      # corner posts
    d.rectangle([W - 2, 0, W - 1, H - 1], fill=rim)
    im.save(out / name)

crate("crate_yellow.png", "#d8a820", "#b08418", "#5a4410")
crate("crate_red.png", "#b83a2a", "#8a2a1e", "#4a1a14")
