#!/usr/bin/env python3
"""Draws art/graves.png and art/graves.sheet.json for cemetery_grave_row (shrine town spec 3.14):

  name_yamada, name_tanaka, name_nakamura, name_ogawa   16 x 64  the family graves' faces:
        "<family>家之墓" carved down polished grey granite (Hiragino Mincho, no antialiasing)
  old_a, old_b      16 x 48  the old pointed graves' faces: weathered stone, worn characters
  western           64 x 32  the black modern grave's face: "やすらぎ" (peace) in pale gold
  flowers_a/b/c     32 x 24  the offerings card: two stone flower holders with chrysanthemums
        and the incense stand between them (a: yellow and white, b: red and purple, c: old,
        browned); transparent around them (a cutout)

4-bit cells (each at most 15 colours). Needs Pillow and macOS's Hiragino Mincho.
Run: python3 draw_graves.py   (writes next to this script)
"""
import json
import os
import random
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = '/System/Library/Fonts/ヒラギノ明朝 ProN.ttc'


def hx(s, a=255):
    s = s.lstrip('#')
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


GRANITE = [hx('#a8a6a0'), hx('#b0aea8'), hx('#a0a09c'), hx('#8a8884')]
DARK = [hx('#3a3a40'), hx('#34343a'), hx('#44444c')]
OLD = [hx('#8e887c'), hx('#867f74'), hx('#968f82'), hx('#b8b8a0'), hx('#7a8050')]


def speckle(w, h, cols, seed, weights=None):
    rng = random.Random(seed)
    img = Image.new('RGBA', (w, h))
    for y in range(h):
        for x in range(w):
            img.putpixel((x, y), rng.choices(cols, weights)[0])
    return img


def text_mask(text, w, h, size, vertical=True):
    """A 1-bit mask of the text, centred, glyphs stacked down (vertical) or across."""
    m = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(m)
    d.fontmode = '1'
    f = ImageFont.truetype(FONT, size)
    if vertical:
        n = len(text)
        step = size
        y0 = (h - n * step) // 2
        for k, ch in enumerate(text):
            bb = d.textbbox((0, 0), ch, font=f)
            d.text(((w - (bb[2] - bb[0])) // 2 - bb[0], y0 + k * step - bb[1] + (step - (bb[3] - bb[1])) // 2),
                   ch, font=f, fill=255)
    else:
        bb = d.textbbox((0, 0), text, font=f)
        d.text(((w - (bb[2] - bb[0])) // 2 - bb[0], (h - (bb[3] - bb[1])) // 2 - bb[1]), text,
               font=f, fill=255)
    return m


def name_face(family, seed):
    img = speckle(16, 64, GRANITE, seed, [5, 4, 4, 1])
    m = text_mask(family + '家之墓', 16, 64, 12)
    for y in range(64):
        for x in range(16):
            if m.getpixel((x, y)):
                img.putpixel((x, y), hx('#3e3c3a'))
    # a polished edge: the face's border a shade lighter
    for y in range(64):
        for x in (0, 15):
            img.putpixel((x, y), hx('#bcbab4'))
    return img


def old_face(seed, text):
    rng = random.Random(seed)
    img = speckle(16, 48, OLD, seed, [5, 4, 4, 1, 1])
    m = text_mask(text, 16, 48, 11)
    for y in range(48):
        for x in range(16):
            if m.getpixel((x, y)) and rng.random() < 0.6:     # worn away in places
                img.putpixel((x, y), hx('#5e5a54'))
    return img


def western():
    img = speckle(64, 32, DARK, 9, [5, 4, 1])
    m = text_mask('やすらぎ', 64, 32, 13, vertical=False)
    for y in range(32):
        for x in range(64):
            if m.getpixel((x, y)):
                img.putpixel((x, y), hx('#d8c890'))
    return img


def flowers(kind):
    """32 x 24: holders at x 2-7 and 24-29, the incense stand at x 11-20."""
    img = Image.new('RGBA', (32, 24), (0, 0, 0, 0))
    p = img.putpixel
    stone, stone_d, stone_l = hx('#a8a6a0'), hx('#7a7874'), hx('#c4c2bc')
    leaf, leaf_d = hx('#4f6a3a'), hx('#2e4a2e')
    blooms = {'a': [hx('#f0c030'), hx('#eceae4'), hx('#fad85a')],
              'b': [hx('#c8301e'), hx('#8a4aa0'), hx('#eceae4')],
              'c': [hx('#9a7a3e'), hx('#8a6a48'), hx('#b8a070')]}[kind]
    rng = random.Random(ord(kind))
    for x0 in (2, 24):
        # the holder: a stone cup, 6 wide, 9 tall, lit on its left
        for y in range(15, 24):
            for x in range(x0, x0 + 6):
                c = stone_l if x == x0 else stone_d if x == x0 + 5 else stone
                p((x, y), c)
        for x in range(x0 - 1, x0 + 7):
            p((x, 15), stone_d)
        # the bunch: leaves fanning out of the cup, blooms over them
        for k in range(70):
            x = x0 + 2 + rng.randint(-3, 4)
            y = rng.randint(1, 14)
            if abs(x - (x0 + 2.5)) > (15 - y) * 0.3 + 1.0:
                continue
            p((x, y), leaf if k % 3 else leaf_d)
        for k in range(22):
            x = x0 + 2 + rng.randint(-3, 3)
            y = rng.randint(1, 8)
            if kind == 'c' and y < 4:
                continue                       # old flowers: drooped
            c = blooms[k % 3]
            p((x, y), c)
            if x + 1 < 32:
                p((x + 1, y), c)
        for y in range(10, 15):                # stems
            p((x0 + 2, y), leaf_d)
            p((x0 + 3, y), leaf)
    # the incense stand: a stone box on short legs, lit on top
    for y in range(18, 23):
        for x in range(11, 21):
            p((x, y), stone_l if y == 18 else stone_d if x in (11, 20) else stone)
    for x in (12, 19):
        p((x, 23), stone_d)
    if kind != 'c':
        for x in (14, 16, 18):                 # sticks, their embers, a wisp of smoke
            for y in range(13, 18):
                p((x, y), hx('#5a6a3a'))
            p((x, 12), hx('#e0502a'))
        for (x, y) in ((15, 10), (15, 9), (16, 8), (16, 7), (17, 6), (17, 5), (16, 3)):
            p((x, y), hx('#d8dce0'))
    return img


def main():
    cells = {}
    sheet = Image.new('RGBA', (128, 104), (0, 0, 0, 0))

    def put(name, img, x, y):
        sheet.paste(img, (x, y))
        cells[name] = [x, y, img.width, img.height]
    for k, fam in enumerate(['山田', '田中', '中村', '小川']):
        put('name_' + ['yamada', 'tanaka', 'nakamura', 'ogawa'][k], name_face(fam, k + 1), 16 * k, 0)
    put('old_a', old_face(11, '南無'), 64, 0)
    put('old_b', old_face(12, '先祖'), 80, 0)
    put('western', western(), 64, 48)
    for k, kind in enumerate('abc'):
        put('flowers_' + kind, flowers(kind), 32 * k, 80)
    sheet.save(os.path.join(HERE, 'graves.png'))
    with open(os.path.join(HERE, 'graves.sheet.json'), 'w') as f:
        json.dump({'format': 'mei-sheet', 'version': 1, 'cells': cells}, f, indent=1)
        f.write('\n')

    # the plots' top: one 1 x 2 m plot a repeat (32 x 64): granite kerbs on its sides and front,
    # a paved back half where the stones stand, white pebbles in the front half
    plot = Image.new('RGBA', (32, 64))
    rng = random.Random(5)
    kerb, kerb_d, joint = hx('#c8c2b2'), hx('#b0aa9a'), hx('#6a665e')
    pave, pave_d = hx('#a8a294'), hx('#8e887c')
    peb = [hx('#d4ccb8'), hx('#c4beb0'), hx('#b8b2a2'), hx('#e0dccf')]
    for y in range(64):
        for x in range(32):
            if x < 2 or x > 29 or y > 60 or y < 1:
                c = kerb if rng.random() < 0.8 else kerb_d
                if x in (0, 31):
                    c = joint
            elif y < 32:
                c = pave if rng.random() < 0.85 else pave_d
                if y in (16, 31) or x == 16:
                    c = joint
            else:
                c = rng.choice(peb)
            plot.putpixel((x, y), c)
    plot.save(os.path.join(HERE, 'plot.png'))


if __name__ == '__main__':
    main()
