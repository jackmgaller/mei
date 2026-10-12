#!/usr/bin/env python3
"""Draws art/jizo.png and art/jizo.sheet.json for cemetery_jizo_hall (shrine town spec 3.14): the
hall's six jizo (roku jizo), each a 16 x 32 cutout of a small stone jizo seen from the front,
hands together or holding a jewel or a staff, in a red bib, most in a red knitted cap; one has a
pinwheel stuck beside it. 2 cm a texel on 0.32 x 0.64 m cards. Also lattice.png, 16 x 16, the
front bays' wooden lattice (kōshi), its gaps transparent.

The stone and bib colours follow the lab's jizo (examples/assets/lab/jizo). 4-bit. Needs Pillow.
Run: python3 draw_jizo.py   (writes next to this script)
"""
import json
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def hx(s):
    s = s.lstrip('#')
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)


ST_L, ST, ST_D = hx('#b4ae9e'), hx('#9a948a'), hx('#6a665e')
MOSS = hx('#7a8050')
RED, RED_D, CAP = hx('#d8302a'), hx('#a8221e'), hx('#c8301e')
INK = hx('#3a3634')
GOLD = hx('#d8b048')


def jizo(cap, hands, bib_white, pinwheel, seed):
    img = Image.new('RGBA', (16, 32), (0, 0, 0, 0))
    p = img.putpixel

    def stone(x, y, cx, half):
        t = (x - (cx - half)) / max(1, 2 * half)
        c = ST_L if t < 0.3 else ST if t < 0.75 else ST_D
        if (x * 7 + y * 13 + seed * 5) % 41 == 0:
            c = MOSS
        p((x, y), c)
    cx = 8
    # the pedestal (a lotus-ish block), rows 28-31
    for y in range(28, 32):
        for x in range(2, 14):
            p((x, y), ST_D if y == 28 or x in (2, 13) else ST)
    # the robe, widening from the shoulders to the pedestal
    for y in range(11, 28):
        half = [3, 4, 5][y - 11] if y < 14 else min(6, 5 + (y - 14) // 7)
        for x in range(cx - half, cx + half):
            stone(x, y, cx, half)
    # the head
    for y in range(3, 11):
        for x in range(4, 12):
            dx, dy = x - 7.5, y - 6.8
            if dx * dx + dy * dy <= 13:
                stone(x, y, cx, 4)
    for x in (5, 6, 9, 10):            # closed eyes
        p((x, 7), INK)
    p((7, 9), ST_D)
    p((8, 9), ST_D)
    if cap:                            # a knitted cap over the crown
        for y in range(2, 6):
            for x in range(4, 12):
                dx, dy = x - 7.5, y - 6.0
                if dx * dx + dy * dy <= 14 and y < 6:
                    p((x, y), CAP if (x + y) % 3 else RED_D)
        p((7, 1), CAP)
        p((8, 1), CAP)
    # the bib under the chin
    bib, bib_d = (hx('#eceae4'), hx('#c8c4b8')) if bib_white else (RED, RED_D)
    for y in range(11, 17):
        half = [3, 4, 5, 4, 3, 2][y - 11]
        for x in range(cx - half, cx + half):
            p((x, y), bib_d if y == 16 or x == cx + half - 1 else bib)
    # hands
    if hands == 'together':
        for y in range(17, 20):
            for x in (7, 8):
                p((x, y), ST_L)
    elif hands == 'jewel':
        for x in range(6, 10):
            p((x, 19), ST_L)
        for y in (17, 18):
            for x in (7, 8):
                p((x, y), GOLD)
    else:                              # a staff in the right hand
        for y in range(4, 28):
            p((13, y), hx('#5a3e2c'))
        p((13, 3), GOLD)
        p((12, 3), GOLD)
        p((14, 3), GOLD)
        for x in (11, 12):
            p((x, 18), ST_L)
    if pinwheel:                       # a pinwheel on a stick, at the pedestal's left
        for y in range(16, 28):
            p((1, y), hx('#8a6446'))
        for (x, y, c) in ((0, 13, '#3a6ab0'), (1, 13, '#f0c030'), (2, 13, '#3a6ab0'),
                          (0, 14, '#d8302a'), (1, 14, '#eceae4'), (2, 14, '#40a060'),
                          (0, 15, '#d8302a'), (1, 15, '#40a060'), (2, 15, '#f0c030')):
            p((x, y), hx(c))
    return img


def lattice():
    img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    wood, wood_d = hx('#5a3e2c'), hx('#3e2a1e')
    for y in range(16):
        for x in range(16):
            if x % 4 == 0:
                img.putpixel((x, y), wood)
            elif x % 4 == 1:
                img.putpixel((x, y), wood_d)
            elif y == 0:
                img.putpixel((x, y), wood)
    img.save(os.path.join(HERE, 'lattice.png'))


def main():
    specs = [(True, 'together', False, False), (True, 'jewel', False, True),
             (False, 'staff', False, False), (True, 'together', True, False),
             (True, 'jewel', False, False), (False, 'together', False, True)]
    sheet = Image.new('RGBA', (96, 32), (0, 0, 0, 0))
    cells = {}
    for k, s in enumerate(specs):
        sheet.paste(jizo(*s, seed=k), (16 * k, 0))
        cells['jizo_%d' % k] = [16 * k, 0, 16, 32]
    sheet.save(os.path.join(HERE, 'jizo.png'))
    with open(os.path.join(HERE, 'jizo.sheet.json'), 'w') as f:
        json.dump({'format': 'mei-sheet', 'version': 1, 'cells': cells}, f, indent=1)
        f.write('\n')
    lattice()


if __name__ == '__main__':
    main()
