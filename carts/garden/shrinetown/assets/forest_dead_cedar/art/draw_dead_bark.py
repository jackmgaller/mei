"""Draws dead_bark.png beside this script (python3 draw_dead_bark.py; needs Pillow): a 32 x 64
repeating tile of a long-dead sugi, silver-grey weathered wood in twisting vertical grain, dark
checks, a few strips of the old red-brown bark still hanging on and flecks of lichen. Seeded, so
the same script draws the same tile; it tiles in both directions."""
import random
from pathlib import Path

from PIL import Image

W, H = 32, 64
GREY, LIGHT, PALE, DARK, CRACK = (138, 132, 122), (164, 158, 146), (188, 182, 168), (104, 98, 90), (62, 56, 50)
BARK, BARK_D = (106, 70, 50), (74, 52, 40)
LICHEN, LICHEN_L = (122, 138, 96), (150, 162, 112)


def main():
    rng = random.Random(53)
    img = Image.new('RGB', (W, H), GREY)
    px = img.load()
    # grain: each column a tone, drifting sideways with height (a slow twist), wrapping
    tones = [rng.choice([GREY, GREY, LIGHT, LIGHT, PALE, DARK]) for _ in range(W)]
    for y in range(H):
        shift = round(2 * (y / H))           # 2 texels of twist over the tile, so it wraps
        for x in range(W):
            px[x, y] = tones[(x + shift) % W]
    # checks: long dark cracks along the grain
    for _ in range(9):
        x, y0, n = rng.randrange(W), rng.randrange(H), rng.randint(8, 26)
        for k in range(n):
            yy = (y0 + k) % H
            xx = (x + round(2 * (yy / H))) % W
            px[xx, yy] = CRACK if k % 7 else DARK
    # strips of the old bark, ragged at the ends
    for x0, y0, w, n in [(4, 6, 4, 22), (19, 38, 3, 18), (26, 2, 2, 12)]:
        for k in range(n):
            yy = (y0 + k) % H
            ww = w - (1 if k in (0, n - 1) or rng.random() < 0.2 else 0)
            for j in range(ww):
                xx = (x0 + j + round(2 * (yy / H))) % W
                px[xx, yy] = BARK_D if j == 0 or rng.random() < 0.25 else BARK
    # lichen flecks
    for _ in range(26):
        x, y = rng.randrange(W), rng.randrange(H)
        px[x, y] = LICHEN if rng.random() < 0.6 else LICHEN_L
        if rng.random() < 0.5:
            px[(x + 1) % W, y] = LICHEN
    img.save(Path(__file__).resolve().parent / 'dead_bark.png')


if __name__ == '__main__':
    main()
