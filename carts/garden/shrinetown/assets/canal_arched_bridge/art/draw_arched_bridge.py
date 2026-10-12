"""Draws arched_rail.png beside this file: the railing (koran) of canal_arched_bridge, a cutout
32 x 16 texels for 2 m of railing by 0.88 m: the upper rail (hiragi) under the bridge's top rail
(kasagi, geometry), short posts (tsuka) every metre with gold fittings, a middle rail, and the
solid plinth rail (jifuku) along the deck; the rest a hole. Vermilion lacquer in the shrine's
colours (carts/garden/shrine/STYLE.md). Run once and commit the PNG
(python3 carts/garden/shrinetown/assets/canal_arched_bridge/art/draw_arched_bridge.py). Needs
Pillow."""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


VERM, VERM_SH, GOLD, BLACK = rgb('#d8462a'), rgb('#a8321e'), rgb('#d8b048'), rgb('#2c2a28')

im = Image.new('RGBA', (32, 16), (0, 0, 0, 0))


def rect(x0, y0, x1, y1, c):
    for y in range(y0, y1):
        for x in range(x0, x1):
            im.putpixel((x, y), c)


rect(0, 0, 32, 2, VERM)            # upper rail
rect(0, 2, 32, 3, VERM_SH)         # its shadow side
rect(0, 9, 32, 10, VERM)           # middle rail
rect(0, 10, 32, 11, VERM_SH)
rect(0, 13, 32, 16, VERM)          # the plinth rail on the deck
rect(0, 15, 32, 16, VERM_SH)
for x in (7, 23):                  # short posts every metre
    rect(x, 3, x + 2, 13, VERM)
    rect(x + 1, 3, x + 2, 13, VERM_SH)
    rect(x, 3, x + 2, 4, GOLD)     # gold fittings where post meets rail
    rect(x, 12, x + 2, 13, GOLD)
for x in (15, 31):                 # thin balusters between, black lacquer
    rect(x, 3, x + 1, 9, BLACK)
im.save(os.path.join(HERE, 'arched_rail.png'))
print('wrote arched_rail.png')
