"""Draws the rope ladder's textures beside this script (python3 draw_ladder.py; needs Pillow):

- ladder.png, 16 x 16, a repeating tile 0.5 m square: two rungs (aged wood, 2 texels thick, lashed
  to the side ropes) 0.25 m apart and the two hemp side ropes; transparent between (a cutout);
- roll_end.png, 16 x 16, the end of the rolled ladder: a spiral of rope with rung ends.

Authored art, committed; deterministic.
"""
import math
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent

ROPE = '#c8b478'
ROPE_DK = '#9a8458'
ROPE_LT = '#e0d0a0'
WOOD = '#8a6446'
WOOD_DK = '#5a3e2c'
WOOD_LT = '#b08a5e'


def rgb(h):
    h = h.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def ladder():
    img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    px = img.load()
    # rungs: rows 3-4 and 11-12, light on top, dark underneath
    for y0 in (3, 11):
        for x in range(1, 15):
            px[x, y0] = rgb(WOOD_LT if x % 5 else WOOD)
            px[x, y0 + 1] = rgb(WOOD_DK if x % 3 == 0 else WOOD)
    # side ropes: columns 1 and 14, a twist every 2 texels
    for y in range(16):
        for x in (1, 14):
            px[x, y] = rgb(ROPE if (y // 2) % 2 == 0 else ROPE_DK)
        # lashings round the rung ends
        if y in (2, 5, 10, 13):
            for x in (1, 2, 13, 14):
                px[x, y] = rgb(ROPE_LT)
    return img


def roll_end():
    img = Image.new('RGBA', (16, 16), rgb(ROPE_DK))
    px = img.load()
    for y in range(16):
        for x in range(16):
            dx, dy = x - 7.5, y - 7.5
            r = math.hypot(dx, dy)
            a = math.atan2(dy, dx)
            # an Archimedean spiral, one turn per 2.2 texels
            t = (r - a / (2 * math.pi) * 2.2) % 2.2
            col = ROPE if t < 1.1 else ROPE_DK
            if r < 1.2:
                col = WOOD_DK
            px[x, y] = rgb(col)
    # rung ends poking out of the roll
    for (x, y) in [(3, 7), (11, 8), (7, 3), (8, 12), (5, 11), (11, 4)]:
        px[x, y] = rgb(WOOD_LT)
    return img


def main():
    ladder().save(HERE / 'ladder.png')
    roll_end().save(HERE / 'roll_end.png')


if __name__ == '__main__':
    main()
