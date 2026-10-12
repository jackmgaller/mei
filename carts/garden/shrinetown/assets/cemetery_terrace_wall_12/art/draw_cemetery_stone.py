#!/usr/bin/env python3
"""Draws the cemetery's stone textures (shrine town spec 3.14) into this folder:

  kenchi.png   64 x 32  the retaining walls' face: squared granite blocks laid diagonally
                        (kenchi-ishi, tani-zumi), grey cement joints, one weep hole with its
                        stain; one repeat is 2 x 1 m, so a block's face is about 35 cm
  coping.png   32 x 32  cut granite slabs (the walls' coping, the plinths' kerbs, the jizo
                        hall's base), a joint every 16 texels; one repeat is 2 x 2 m
  granite.png  16 x 16  polished grey granite, the family graves; one repeat is 0.5 m
  granite_dark.png 16 x 16  black granite, the modern grave
  old_stone.png 16 x 16  weathered stone with lichen and moss, the old graves

Every tile repeats seamlessly. 4-bit, at most 15 colours each, from the shrine's stone palette
(STYLE.md: #b4ae9e light, #8e887c mid, #6a665e dark, #7a8050 mossy). Needs Pillow.
Run: python3 draw_cemetery_stone.py   (writes next to this script)
"""
import os
import random
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def hx(s):
    s = s.lstrip('#')
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)


def h(*a):
    """A small integer hash, deterministic."""
    v = 2166136261
    for x in a:
        v = ((v ^ (x & 0xffffffff)) * 16777619) & 0xffffffff
    return v


def kenchi():
    W, H, D = 64, 32, 16
    tones = [hx('#bab4a4'), hx('#a8a294'), hx('#989284'), hx('#b0aa98'), hx('#a29a8a')]
    light, dark = hx('#c4beae'), hx('#86807a')
    joint, speck, moss = hx('#5e5a54'), hx('#7e786e'), hx('#7a8050')
    hole, rim, stain = hx('#2c2a28'), hx('#8e887c'), hx('#8a8478')
    img = Image.new('RGBA', (W, H))
    px = img.load()
    for y in range(H):
        for x in range(W):
            s, d = x + y, x - y
            a, b = s // D, d // D            # the block's diagonal coordinates
            u, v = (a + b) % 8, (a - b) % 4  # invariant under the tile's wrap
            ps, pd = s % D, d % D            # position inside the block
            if ps == 0 or pd == 0:
                c = joint
            elif ps == 1 or pd == 1:
                c = light                    # the top-left edges catch the light
            elif ps == D - 1 or pd == D - 1:
                c = dark
            else:
                c = tones[h(u, v) % 5]
                r = h(x, y, 7) % 100
                if r < 9:
                    c = speck
                elif r < 12:
                    c = light
            # moss creeps along a few joints near the bottom of some blocks
            if (ps <= 2 or pd >= D - 2) and h(u, v, 3) % 5 == 0 and h(x, y, 11) % 3 == 0:
                c = moss
            px[x, y] = c
    # the weep hole (a cut pipe end) in one block, and its stain running down
    cx, cy = 40, 8
    for y in range(H):
        for x in range(W):
            dx, dy = x - cx, y - cy
            if dx * dx + dy * dy <= 2:
                px[x, y] = hole
            elif dx * dx + dy * dy <= 5:
                px[x, y] = rim
    for k in range(2, 14):
        for x in (cx - 1, cx, cx + 1):
            if abs(x - cx) == 1 and h(x, k) % 3 == 0:
                continue
            y = (cy + k) % H
            if px[x, y] != joint:
                px[x, y] = stain
    img.save(os.path.join(HERE, 'kenchi.png'))


def coping():
    W = 32
    a, b, c = hx('#c8c2b2'), hx('#b8b2a2'), hx('#a8a294')
    joint, speck = hx('#6a665e'), hx('#8e887c')
    img = Image.new('RGBA', (W, W))
    px = img.load()
    for y in range(W):
        for x in range(W):
            slab = x // 16
            base = a if (slab + (y // 16)) % 2 == 0 else b
            r = h(x, y, 5) % 100
            col = base
            if r < 10:
                col = speck
            elif r < 22:
                col = c
            if x % 16 == 0:
                col = joint
            elif x % 16 == 15:
                col = c
            px[x, y] = col
    img.save(os.path.join(HERE, 'coping.png'))


def speckle(name, base, flecks, seed, density=0.3, extra=None):
    img = Image.new('RGBA', (16, 16))
    px = img.load()
    rng = random.Random(seed)
    for y in range(16):
        for x in range(16):
            col = base[(x * 3 + y * 5 + h(x, y, seed)) % len(base)] if len(base) > 1 else base[0]
            if rng.random() < density:
                col = rng.choice(flecks)
            px[x, y] = col
    if extra:
        extra(px, rng)
    img.save(os.path.join(HERE, name))


def old_marks(px, rng):
    lichen, moss, streak = hx('#b8b8a0'), hx('#7a8050'), hx('#5e5a54')
    for _ in range(5):                         # pale lichen blots
        cx, cy = rng.randrange(16), rng.randrange(16)
        for dx, dy in ((0, 0), (1, 0), (0, 1), (-1, 0)):
            px[(cx + dx) % 16, (cy + dy) % 16] = lichen
    for _ in range(4):
        cx, cy = rng.randrange(16), rng.randrange(16)
        for dx, dy in ((0, 0), (1, 0), (1, 1)):
            px[(cx + dx) % 16, (cy + dy) % 16] = moss
    for x in (3, 11):                          # rain streaks
        for y in range(16):
            if rng.random() < 0.6:
                px[x, y] = streak


def main():
    kenchi()
    coping()
    speckle('granite.png', [hx('#a8a6a0'), hx('#b0aea8'), hx('#a0a09c')],
            [hx('#6a6866'), hx('#8a8884'), hx('#d0cec8')], 1)
    speckle('granite_dark.png', [hx('#3a3a40'), hx('#34343a')],
            [hx('#5a5a62'), hx('#26262a'), hx('#7a7a84')], 2, 0.25)
    speckle('old_stone.png', [hx('#8e887c'), hx('#867f74'), hx('#968f82')],
            [hx('#6a665e'), hx('#a29c8e')], 3, 0.2, old_marks)


if __name__ == '__main__':
    main()
