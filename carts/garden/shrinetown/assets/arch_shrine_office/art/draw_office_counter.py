"""Draws office_counter.png beside this file: the shrine office's sales window, one 4 m bay.

Authored art: run once with `python3 draw_office_counter.py` and commit the PNG; nothing rebuilds
it. Needs Pillow. 64 x 32 texels for 4 m x 2.25 m (the wall from the base to the eave), 4-bit,
in the shrine palette (carts/garden/shrine/STYLE.md) and the manner of the halls' bays
(carts/garden/shrine/assets/art/draw_arch.py): half a vermilion post at each side, a head beam,
a plaster band, and a wide glazed window over the counter with rows of charms (omamori) and
fortune slips on display behind it, the counter ledge, and dark boards under it.
"""

from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


VERM = rgb("#d8462a")
VERM_SH = rgb("#a8321e")
PLASTER = rgb("#ece4d2")
PLASTER_SH = rgb("#d8cfbc")
BLACK = rgb("#2c2a28")
WOOD_D = rgb("#5a3e2c")
WOOD = rgb("#8a6446")
WOOD_NEW = rgb("#b08a5e")
GOLD = rgb("#d8b048")
RED = rgb("#c8301e")
GREEN = rgb("#3c5a34")
BLUE = rgb("#3a6ab0")
PINK = rgb("#e0502a")


def rect(im, x0, y0, x1, y1, c):
    for y in range(max(0, y0), min(im.height, y1)):
        for x in range(max(0, x0), min(im.width, x1)):
            im.putpixel((x, y), c + (255,))


def counter():
    im = Image.new("RGBA", (64, 32), PLASTER + (255,))
    rect(im, 0, 0, 64, 2, VERM)                    # head beam under the eave
    rect(im, 0, 2, 64, 3, VERM_SH)
    rect(im, 4, 3, 60, 7, PLASTER)                 # plaster band
    rect(im, 0, 7, 64, 9, VERM)                    # lintel over the window
    rect(im, 0, 9, 64, 10, VERM_SH)
    # the window: a dark room behind glass, three panes
    rect(im, 3, 10, 61, 22, WOOD_D)
    # shelves of charms: two rows of omamori, a row of boxed fortunes
    charms = [RED, PLASTER, GOLD, GREEN, PINK, BLUE, RED, GOLD, PLASTER, GREEN]
    k = 0
    for y0 in (11, 15):
        for x in range(5, 59, 3):
            if x in (21, 22, 41, 42):
                continue
            c = charms[k % len(charms)]
            k += 1
            rect(im, x, y0, x + 2, y0 + 3, c)
            im.putpixel((x, y0), GOLD + (255,)) if c not in (GOLD, PLASTER) else None
        rect(im, 4, y0 + 3, 60, y0 + 4, WOOD)      # the shelf under them
    for x in range(6, 58, 4):                       # boxes of fortune slips, lower shelf
        if x in (22, 42):
            continue
        rect(im, x, 19, x + 3, 21, PLASTER_SH if (x // 4) % 2 else PLASTER)
    for x in (21, 41):                              # window mullions
        rect(im, x, 10, x + 2, 22, VERM)
    rect(im, 3, 10, 4, 22, VERM_SH)                 # the window's reveal
    rect(im, 60, 10, 61, 22, VERM_SH)
    rect(im, 0, 21, 64, 22, BLACK)                  # the counter's shadow line
    rect(im, 0, 22, 64, 24, WOOD_NEW)               # the counter ledge
    rect(im, 0, 24, 64, 25, WOOD)
    rect(im, 3, 25, 61, 30, WOOD)                   # boards under the counter
    for x in range(7, 60, 6):
        rect(im, x, 25, x + 1, 30, WOOD_D)
    rect(im, 0, 30, 64, 32, WOOD_D)                 # the sill on the base
    rect(im, 0, 0, 3, 30, VERM)                     # half posts
    rect(im, 61, 0, 64, 30, VERM)
    rect(im, 3, 0, 4, 22, VERM_SH)
    return im


if __name__ == "__main__":
    counter().save(HERE / "office_counter.png")
