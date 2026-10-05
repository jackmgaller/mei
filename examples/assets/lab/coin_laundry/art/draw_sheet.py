"""Draws coin_laundry_sheet.png and its .sheet.json: the coin laundry's textures.

Authored art, drawn once with Pillow and committed (as the stall's sheet is); rerun it only to
change the art. The sign's katakana are drawn with macOS's Hiragino Maru Gothic.
Run: python3 examples/assets/lab/coin_laundry/art/draw_sheet.py
"""

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = '/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc'

CELLS = {
    'sign':     [0, 0, 160, 32],
    'washer_a': [160, 0, 16, 24], 'washer_b': [176, 0, 16, 24], 'washer_c': [192, 0, 16, 24],
    'dryer_a':  [208, 0, 16, 16], 'dryer_b': [224, 0, 16, 16],
    'glass':    [0, 32, 96, 64],
    'vending':  [96, 32, 24, 48],
    'side':     [120, 32, 16, 32],
    'poster':   [136, 32, 16, 20],
    'clock':    [152, 32, 16, 16],
    'grille':   [168, 32, 16, 16],
    'wheel':    [184, 32, 16, 16],
    'tv_a':     [200, 32, 16, 12], 'tv_b': [216, 32, 16, 12],
    'leaves':   [232, 32, 16, 16],
    'changer':  [136, 56, 12, 24],
}

C = {
    'blue': (31, 92, 184), 'navy': (18, 52, 112), 'sky': (120, 186, 236), 'white': (246, 246, 240),
    'red': (214, 52, 44), 'yellow': (250, 206, 60), 'chrome': (200, 206, 212),
    'steel': (130, 138, 148), 'dark': (40, 46, 58), 'glassd': (44, 70, 92), 'black': (16, 18, 22),
}


def cell_image(name):
    x, y, w, h = CELLS[name]
    return Image.new('RGBA', (w, h), (0, 0, 0, 0))


def text_mask(text, size, box_w, box_h, scale=8, weight=0):
    """Text rendered large, then each target pixel set where at least half is ink."""
    font = ImageFont.truetype(FONT, size * scale)
    big = Image.new('L', (box_w * scale, box_h * scale), 0)
    d = ImageDraw.Draw(big)
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    d.text(((box_w * scale - (r - l)) // 2 - l, (box_h * scale - (b - t)) // 2 - t), text,
           font=font, fill=255, stroke_width=weight * scale // 2, stroke_fill=255)
    small = big.resize((box_w, box_h), Image.BOX)
    return [[small.getpixel((i, j)) >= 110 for i in range(box_w)] for j in range(box_h)]


def disc(px, cx, cy, r, colour):
    for j in range(int(cy - r - 1), int(cy + r + 2)):
        for i in range(int(cx - r - 1), int(cx + r + 2)):
            if (i + 0.5 - cx) ** 2 + (j + 0.5 - cy) ** 2 <= r * r:
                put(px, i, j, colour)


def ring(px, cx, cy, r0, r1, colour):
    for j in range(int(cy - r1 - 1), int(cy + r1 + 2)):
        for i in range(int(cx - r1 - 1), int(cx + r1 + 2)):
            d2 = (i + 0.5 - cx) ** 2 + (j + 0.5 - cy) ** 2
            if r0 * r0 <= d2 <= r1 * r1:
                put(px, i, j, colour)


def put(img, i, j, colour):
    if 0 <= i < img.width and 0 <= j < img.height:
        img.putpixel((i, j), tuple(colour) + ((255,) if len(colour) == 3 else ()))


def rect(img, x0, y0, x1, y1, colour):
    for j in range(y0, y1):
        for i in range(x0, x1):
            put(img, i, j, colour)


def sign():
    im = cell_image('sign')
    rect(im, 0, 0, 160, 32, C['blue'])
    rect(im, 0, 0, 160, 1, C['navy']); rect(im, 0, 31, 160, 32, C['navy'])
    rect(im, 0, 1, 160, 3, C['white']); rect(im, 0, 29, 160, 31, C['white'])
    rect(im, 0, 3, 160, 4, C['red']); rect(im, 0, 28, 160, 29, C['red'])
    # a little washing machine, its door a bubble
    rect(im, 5, 8, 23, 25, C['white'])
    rect(im, 6, 9, 22, 11, C['sky']); put(im, 19, 9, C['red']); put(im, 20, 9, C['red'])
    disc(im, 14, 17.5, 5.6, C['steel']); disc(im, 14, 17.5, 4.5, C['sky'])
    disc(im, 12.8, 16.3, 1.6, C['white'])
    m = text_mask('コインランドリー', 16, 118, 24, weight=1)
    ink = [(29 + i, 4 + j) for j, row in enumerate(m) for i, on in enumerate(row) if on]
    for (i, j) in ink:                      # drop shadow first, then the letters
        put(im, i + 1, j + 1, C['navy'])
    for (i, j) in ink:
        put(im, i, j, C['white'])
    for (cx, cy, rr) in [(155.5, 10, 2.4), (151.5, 18, 1.7), (156, 23, 1.2)]:
        ring(im, cx, cy, rr - 0.9, rr, C['white'])
    return im


def washer(frame):
    im = cell_image('washer_a')
    rect(im, 0, 0, 16, 24, C['white'])
    rect(im, 0, 0, 16, 5, (222, 226, 230))
    rect(im, 1, 1, 7, 4, C['dark']); rect(im, 2, 2, 5, 3, (120, 230, 120))  # display
    rect(im, 11, 1, 13, 4, C['steel']); put(im, 12, 2, C['black'])         # coin slot
    put(im, 14, 2, C['red'])
    disc(im, 8, 13.5, 6.5, C['chrome']); disc(im, 8, 13.5, 5.5, C['steel'])
    disc(im, 8, 13.5, 4.7, C['glassd'])
    # tumbling clothes: three blobs turning about the drum
    for k, col in enumerate([C['red'], C['yellow'], C['sky']]):
        a = frame * 2.1 + k * 2.1
        cx, cy = 8 + 2.4 * math.cos(a), 14.5 + 2.4 * math.sin(a)
        disc(im, cx, cy, 1.6, col)
    put(im, 6, 11, (200, 220, 236)); put(im, 5, 12, (200, 220, 236))      # glint
    rect(im, 1, 22, 15, 23, (206, 210, 214))
    return im


def dryer(frame):
    im = cell_image('dryer_a')
    rect(im, 0, 0, 16, 16, (214, 208, 196))
    rect(im, 0, 0, 16, 2, (170, 164, 150)); put(im, 2, 0, C['yellow']); put(im, 13, 0, C['red'])
    disc(im, 8, 9, 6.5, C['chrome']); disc(im, 8, 9, 5.5, (110, 70, 40))
    disc(im, 8, 9, 4.8, (236, 150, 64))
    for k, col in enumerate([C['white'], (240, 170, 200), C['white']]):
        a = frame * 1.6 + k * 2.1
        disc(im, 8 + 2.2 * math.cos(a), 9.6 + 2.2 * math.sin(a), 1.7, col)
    put(im, 6, 6, (255, 230, 180))
    return im


def glass():
    im = cell_image('glass')
    frame, dk = C['chrome'], C['steel']
    rect(im, 0, 0, 96, 3, frame); rect(im, 0, 61, 96, 64, frame)
    for x in (0, 31, 63, 93):
        rect(im, x, 0, x + 3, 64, frame)
    rect(im, 0, 12, 96, 14, frame)                 # transom
    rect(im, 47, 14, 49, 61, dk)                   # meeting stiles of the sliding door
    rect(im, 32, 14, 34, 61, dk); rect(im, 62, 14, 64, 61, dk)
    rect(im, 41, 34, 43, 42, C['dark']); rect(im, 53, 34, 55, 42, C['dark'])  # handles
    # reflections: pale diagonal streaks on every pane
    streak = (214, 236, 248)
    for (x0, y0, x1, y1) in [(3, 14, 31, 61), (34, 14, 47, 61), (49, 14, 62, 61), (64, 14, 93, 61),
                             (3, 3, 31, 12), (64, 3, 93, 12)]:
        for k in range(0, 200, 23):
            for t in range(0, 40):
                i, j = x0 + k - t // 2 - 14, y1 - 1 - t
                if x0 <= i < x1 and y0 <= j < y1 and t % 13 < 6:
                    put(im, i, j, streak)
                    if x0 <= i + 1 < x1:
                        put(im, i + 1, j, streak)
    # the door's lettering band and stickers
    rect(im, 35, 24, 61, 27, C['blue'])
    for i in range(36, 61, 3):
        put(im, i, 25, C['white'])
    disc(im, 40, 50, 3.6, C['red']); disc(im, 40, 50, 2.6, C['white'])
    for (i, j) in [(39, 49), (40, 49), (40, 50), (39, 51), (40, 51), (41, 51)]:
        put(im, i, j, C['red'])                    # a tiny "2"
    rect(im, 8, 34, 18, 47, C['white'])            # a notice taped inside the left pane
    rect(im, 9, 35, 17, 37, C['red'])
    for j in (39, 41, 43, 45):
        rect(im, 9, j, 17 if j != 45 else 14, j + 1, (90, 100, 120))
    rect(im, 72, 40, 86, 46, C['yellow'])          # an "open 24h" strip on the right pane
    for i in range(73, 86, 2):
        put(im, i, 42, C['black']); put(im, i, 43, C['black'])
    return im


def vending():
    im = cell_image('vending')
    rect(im, 0, 0, 24, 48, C['red'])
    rect(im, 2, 2, 22, 25, (236, 240, 244))        # the lit display window
    cans = [C['red'], C['blue'], C['yellow'], (60, 160, 80), (240, 240, 240), (120, 70, 40),
            (250, 130, 40), (40, 40, 40), C['sky'], (230, 90, 150)]
    k = 0
    for row in range(3):
        y = 3 + row * 7
        for col in range(6):
            x = 3 + col * 3
            c = cans[(k * 7 + row) % len(cans)]
            rect(im, x, y, x + 2, y + 5, c)
            put(im, x, y, (255, 255, 255))
            k += 1
        rect(im, 2, y + 5, 22, y + 6, C['steel'])
        for col in range(6):
            put(im, 3 + col * 3, y + 6, (60, 220, 90))
    rect(im, 2, 26, 22, 31, (250, 250, 250))       # logo band
    rect(im, 4, 27, 12, 30, C['blue']); rect(im, 14, 27, 20, 30, C['red'])
    rect(im, 16, 33, 21, 38, C['dark']); rect(im, 17, 34, 18, 37, C['steel'])  # coins
    put(im, 19, 35, C['yellow'])
    rect(im, 3, 33, 12, 36, (180, 20, 24))
    rect(im, 3, 40, 21, 45, C['black'])            # the take-out flap
    rect(im, 4, 41, 20, 42, (60, 60, 64))
    return im


def side_sign():
    im = cell_image('side')
    rect(im, 0, 0, 16, 32, C['white'])
    rect(im, 0, 0, 16, 1, C['blue']); rect(im, 0, 31, 16, 32, C['blue'])
    rect(im, 0, 0, 1, 32, C['blue']); rect(im, 15, 0, 16, 32, C['blue'])
    rect(im, 3, 3, 13, 13, C['blue'])
    disc(im, 8, 8.5, 3.6, C['sky']); disc(im, 8, 8.5, 2.2, C['white'])
    put(im, 4, 4, C['yellow']); put(im, 5, 4, C['yellow'])
    m = text_mask('24', 10, 12, 10, weight=1)
    for j, row in enumerate(m):
        for i, on in enumerate(row):
            if on:
                put(im, 2 + i, 15 + j, C['red'])
    rect(im, 3, 26, 13, 28, C['blue'])
    return im


def poster():
    im = cell_image('poster')
    rect(im, 0, 0, 16, 20, (248, 244, 226))
    rect(im, 0, 0, 16, 4, C['blue'])
    for i in range(2, 14, 3):
        put(im, i, 2, C['white']); put(im, i + 1, 2, C['white'])
    for n, y in enumerate((6, 10, 14)):
        disc(im, 3.5, y + 1.5, 1.6, [C['red'], C['yellow'], (60, 160, 80)][n])
        rect(im, 7, y + 1, 14, y + 2, (100, 100, 110))
        rect(im, 7, y + 3, 12, y + 4, (160, 160, 170))
    return im


def clock():
    im = cell_image('clock')
    disc(im, 8, 8, 7.6, C['dark']); disc(im, 8, 8, 6.6, C['white'])
    for k in range(12):
        a = k * math.pi / 6
        put(im, int(8 + 5.6 * math.cos(a)), int(8 + 5.6 * math.sin(a)), C['dark'])
    for t in range(5):
        put(im, 8, 8 - t, C['black'])              # ten o'clock-ish
    for t in range(4):
        put(im, 8 - t, 8 - t // 2, C['black'])
    for t in range(6):
        put(im, 8 + t // 2, 8 + t, C['red'])
    return im


def grille():
    im = cell_image('grille')
    rect(im, 0, 0, 16, 16, (204, 202, 190))
    disc(im, 7.5, 8, 6.8, (90, 92, 90))
    for r in (2, 4, 6):
        ring(im, 7.5, 8, r - 0.5, r, (190, 190, 182))
    for t in range(-6, 7):
        put(im, 7 + (t > 0), 8 + t, (190, 190, 182))
    rect(im, 14, 2, 15, 14, (170, 168, 158))
    return im


def wheel():
    im = cell_image('wheel')
    ring(im, 8, 8, 6.3, 7.9, C['black'])
    ring(im, 8, 8, 5.4, 6.3, C['chrome'])
    for k in range(8):
        a = k * math.pi / 4
        for t in range(1, 6):
            put(im, int(8 + t * math.cos(a)), int(8 + t * math.sin(a)), C['steel'])
    disc(im, 8, 8, 1.4, C['chrome'])
    return im


def tv(frame):
    im = cell_image('tv_a')
    rect(im, 0, 0, 16, 12, (40, 40, 44))
    if frame == 0:   # a weather map
        rect(im, 1, 1, 15, 11, (60, 120, 220))
        rect(im, 6, 3, 9, 6, (90, 190, 90)); rect(im, 8, 5, 11, 9, (90, 190, 90))
        disc(im, 4, 3.5, 1.5, C['yellow'])
        put(im, 12, 3, C['white']); put(im, 13, 3, C['white'])
    else:            # a game show
        rect(im, 1, 1, 15, 11, (230, 120, 60))
        rect(im, 3, 6, 13, 10, (250, 220, 90))
        disc(im, 8, 4, 2, (250, 220, 200)); rect(im, 6, 6, 10, 9, C['red'])
    return im


def leaves():
    im = cell_image('leaves')
    shades = [(52, 120, 56), (80, 152, 64), (36, 92, 46)]
    for k, (cx, cy, r) in enumerate([(8, 5, 4), (4, 9, 3.5), (12, 9, 3.5), (8, 11, 4),
                                     (5, 4, 2.5), (11, 4, 2.5), (8, 14, 2)]):
        disc(im, cx, cy, r, shades[k % 3])
    for (i, j) in [(7, 3), (3, 8), (11, 7), (9, 11), (6, 12)]:
        put(im, i, j, (130, 196, 96))
    return im


def changer():
    im = cell_image('changer')
    rect(im, 0, 0, 12, 24, (226, 224, 214))
    rect(im, 1, 1, 11, 6, C['blue'])
    m = text_mask('両替', 6, 10, 5)
    for j, row in enumerate(m):
        for i, on in enumerate(row):
            if on:
                put(im, 1 + i, 1 + j, C['white'])
    rect(im, 2, 8, 10, 11, C['dark']); rect(im, 3, 9, 9, 10, (120, 230, 120))
    rect(im, 2, 13, 6, 15, C['steel']); put(im, 8, 14, C['red']); put(im, 9, 14, C['red'])
    rect(im, 3, 18, 9, 21, C['black'])
    return im


def main():
    sheet = Image.new('RGBA', (256, 96), (0, 0, 0, 0))
    art = {'sign': sign(), 'glass': glass(), 'vending': vending(), 'side': side_sign(),
           'poster': poster(), 'clock': clock(), 'grille': grille(), 'wheel': wheel(),
           'leaves': leaves(), 'changer': changer()}
    for k, n in enumerate('abc'):
        art['washer_' + n] = washer(k)
    for k, n in enumerate('ab'):
        art['dryer_' + n] = dryer(k)
        art['tv_' + n] = tv(k)
    for name, im in art.items():
        x, y, w, h = CELLS[name]
        assert im.size == (w, h), name
        sheet.paste(im, (x, y))
    sheet.save(HERE / 'coin_laundry_sheet.png')
    (HERE / 'coin_laundry_sheet.sheet.json').write_text(json.dumps(
        {'format': 'mei-sheet', 'version': 1, 'cells': CELLS}, indent=1) + '\n')
    sheet.resize((sheet.width * 4, sheet.height * 4), Image.NEAREST).save(
        HERE.parent / 'preview' / 'sheet_x4.png')


if __name__ == '__main__':
    main()
