#!/usr/bin/env python3
"""Draw art/clear_smoke.png and its named cells (art/clear_smoke.sheet.json) for the Clear
Smoke console and controller. Needs Pillow and the macOS Hiragino and Avenir Next fonts.

    python3 examples/assets/console_lab/05_clear_smoke/make_art.py
"""
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, 'art')
SS = 4  # supersampling for type

HIRAGINO = '/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc'
AVENIR = '/System/Library/Fonts/Avenir Next.ttc'  # index 8: Heavy, 0: Bold, 5: Medium

SUN = (240, 160, 64)
MOON = (168, 200, 240)
WHITE = (240, 242, 246)
SMOKE_DARK = (22, 24, 28)


def font(path, size, index=0):
    return ImageFont.truetype(path, size, index=index)


def mei_glyph(px):
    """明 at about px tall, 日 orange and 月 pale blue, on transparent: an RGBA image."""
    big = px * SS
    f = font(HIRAGINO, big)
    box = f.getbbox('明')
    w, h = box[2] - box[0], box[3] - box[1]
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).text((-box[0], -box[1]), '明', font=f, fill=255)
    # the emptiest column in the middle splits 日 from 月
    cols = [sum(1 for y in range(h) if mask.getpixel((x, y)) > 128) for x in range(w)]
    lo, hi = int(w * 0.25), int(w * 0.6)
    split = min(range(lo, hi), key=lambda x: (cols[x], abs(x - w * 0.42)))
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    sun = Image.new('RGBA', (w, h), SUN + (255,))
    moon = Image.new('RGBA', (w, h), MOON + (255,))
    left = Image.new('L', (w, h), 0)
    ImageDraw.Draw(left).rectangle([0, 0, split, h], fill=255)
    from PIL import ImageChops
    out.paste(sun, (0, 0), ImageChops.multiply(mask, left))
    out.paste(moon, (0, 0), ImageChops.multiply(mask, ImageChops.invert(left)))
    return out.resize((max(1, round(w / SS)), max(1, round(h / SS))), Image.LANCZOS)


def text_img(s, px, path, index, colour):
    f = font(path, px * SS, index)
    box = f.getbbox(s)
    w, h = box[2] - box[0], box[3] - box[1]
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((-box[0], -box[1]), s, font=f, fill=colour + (255,))
    return im.resize((max(1, round(w / SS)), max(1, round(h / SS))), Image.LANCZOS)


def flatten(im, bg):
    base = Image.new('RGBA', im.size, bg + (255,))
    base.alpha_composite(im)
    return base.convert('RGB')


def logo_cell(w, h, glyph_px, word_px, sub=True):
    """The badge: black glossy plate, 明 then MEI, with a thin smoke rule."""
    im = Image.new('RGBA', (w, h), SMOKE_DARK + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=(70, 76, 86))
    g = mei_glyph(glyph_px)
    gx = max(2, int(w * 0.06))
    im.alpha_composite(g, (gx, (h - g.height) // 2))
    word = text_img('MEI', word_px, AVENIR, 0, WHITE)
    wx = gx + g.width + max(2, w // 18)
    wy = (h - word.height) // 2 - (2 if sub else 0)
    im.alpha_composite(word, (wx, max(1, wy)))
    if sub:
        s = text_img('SUN & MOON', max(4, word_px // 3), AVENIR, 5, (150, 160, 175))
        im.alpha_composite(s, (wx, min(h - s.height - 1, wy + word.height + 2)))
    return im.convert('RGB')


def emblem_cell(n):
    """A round badge: 明 on dark smoke, a pale ring."""
    big = n * SS
    im = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, big - 1, big - 1], fill=(150, 158, 170, 255))
    d.ellipse([SS * 1.5, SS * 1.5, big - 1 - SS * 1.5, big - 1 - SS * 1.5], fill=SMOKE_DARK + (255,))
    im = im.resize((n, n), Image.LANCZOS)
    g = mei_glyph(int(n * 0.62))
    im.alpha_composite(g, ((n - g.width) // 2, (n - g.height) // 2))
    return flatten(im, SMOKE_DARK)


def smoke_top(w, h, bands=((0.55, 0.07), (0.82, 0.025)), slant=0.6):
    """The clear top seen from above: half its texels holes (alpha 0), the rest smoke, and a
    diagonal gloss streak or two where the plastic catches the light (lighter, fewer holes)."""
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    smoke, light, gloss = (95, 103, 116), (120, 129, 142), (152, 161, 174)
    for y in range(h):
        for x in range(w):
            u, v = x / (w - 1), y / (h - 1)
            t = u + slant * (1 - v)            # rising toward the back-right
            b = max(math.exp(-((t - c) / wd) ** 2) for c, wd in bands)
            solid = (x + y) % 2 == 0 or (b > 0.55 and x % 2 == 0)
            if not solid:
                continue
            if b > 0.7:
                c = gloss
            elif b > 0.3:
                c = light
            else:
                c = smoke
            im.putpixel((x, y), c + (255,))
    return im


def pcb_cell(w, h, chips, seed=1):
    """A green circuit board seen from above, gold traces and white silkscreen."""
    im = Image.new('RGB', (w, h), (36, 96, 58))
    d = ImageDraw.Draw(im)
    # mottled solder mask: a few slightly lighter copper pours
    s = seed
    def rnd(n):
        nonlocal s
        s = (s * 1103515245 + 12345) & 0x7fffffff
        return (s >> 16) % n
    for _ in range(8):
        x, y = rnd(w), rnd(h)
        d.rectangle([x, y, x + 8 + rnd(w // 4), y + 6 + rnd(h // 5)], fill=(42, 108, 64))
    trace = (184, 160, 84)
    dim = (70, 140, 84)
    # bus traces: runs of parallel lines with right-angle bends
    for _ in range(26):
        x, y = rnd(w), rnd(h)
        n = 2 + rnd(4)
        horiz = rnd(2) == 0
        L = 10 + rnd(w // 3)
        col = trace if rnd(3) == 0 else dim
        for k in range(n):
            if horiz:
                d.line([x, y + 2 * k, x + L, y + 2 * k], fill=col)
                d.line([x + L, y + 2 * k, x + L + 3, y + 2 * k + 3], fill=col)
            else:
                d.line([x + 2 * k, y, x + 2 * k, y + L], fill=col)
    # vias
    for _ in range(60):
        x, y = rnd(w), rnd(h)
        d.point((x, y), fill=(210, 190, 110))
    # silkscreen outlines and the parts painted flat
    for (x0, y0, x1, y1, kind) in chips:
        if kind == 'outline':
            d.rectangle([x0, y0, x1, y1], outline=(214, 228, 210))
        elif kind == 'smd':
            d.rectangle([x0, y0, x1, y1], fill=(24, 24, 28))
            for yy in range(y0 + 1, y1, 2):
                d.point((x0 - 1, yy), fill=(200, 200, 205))
                d.point((x1 + 1, yy), fill=(200, 200, 205))
        elif kind == 'pad':
            d.ellipse([x0, y0, x1, y1], fill=(200, 200, 205), outline=(150, 150, 160))
        elif kind == 'resistors':
            for xx in range(x0, x1, 3):
                d.rectangle([xx, y0, xx + 1, y1], fill=(60, 50, 40))
    # seen through smoke-grey plastic: darker and greyer
    return Image.blend(im, Image.new('RGB', im.size, (44, 48, 56)), 0.35)


def port_cell():
    """The controller port's face: a trapezoid socket with a row of pins."""
    w, h = 24, 16
    im = Image.new('RGB', (w, h), (40, 43, 50))
    d = ImageDraw.Draw(im)
    d.polygon([(3, 3), (20, 3), (18, 12), (5, 12)], fill=(8, 8, 10))
    for x in range(6, 18, 2):
        d.line([x, 6, x, 9], fill=(196, 170, 96))
    d.rectangle([0, 0, w - 1, h - 1], outline=(66, 70, 80))
    return im


def card_cell():
    """A memory card slot's face: a dark slit with a spring flap."""
    w, h = 32, 8
    im = Image.new('RGB', (w, h), (44, 47, 55))
    d = ImageDraw.Draw(im)
    d.rectangle([2, 2, w - 3, h - 3], fill=(10, 10, 12))
    d.line([3, 3, w - 4, 3], fill=(30, 32, 36))
    d.rectangle([0, 0, w - 1, h - 1], outline=(70, 74, 84))
    return im


def cart_label():
    """A game label: the night sea under a big moon with a sun setting, and a title."""
    w, h = 48, 36
    im = Image.new('RGB', (w, h), (20, 22, 40))
    d = ImageDraw.Draw(im)
    for y in range(h - 10):  # dusk sky
        t = y / (h - 10)
        c = (int(30 + 200 * t * t), int(30 + 90 * t), int(90 - 30 * t))
        d.line([0, y, w, y], fill=c)
    d.ellipse([28, 3, 42, 17], fill=(220, 232, 250))      # moon
    d.ellipse([31, 3, 45, 15], fill=(52, 46, 96))          # its bite: a crescent
    d.ellipse([6, 16, 18, 28], fill=(250, 150, 60))        # the sun on the sea line
    d.rectangle([0, 23, w, h], fill=(18, 40, 78))          # sea
    for y in range(24, 30, 2):
        d.line([8, y, 16, y], fill=(250, 170, 90))
    t = text_img('YUZUKI', 7, AVENIR, 8, WHITE)
    im.paste(flatten(t, (18, 40, 78)), ((w - t.width) // 2, h - t.height - 2))
    d.rectangle([0, 0, w - 1, h - 1], outline=(235, 235, 240))
    return im


def main():
    os.makedirs(ART, exist_ok=True)
    cells = {}
    sheet = Image.new('RGBA', (256, 256), (255, 0, 255, 255))

    def put(name, im, x, y):
        sheet.paste(im, (x, y))
        cells[name] = [x, y, im.width, im.height]

    # console board, 128 x 96 over a 0.28 x 0.20 m board, seen from above (+Z is up the image)
    console_chips = [
        (18, 34, 44, 60, 'outline'), (60, 38, 88, 62, 'outline'),   # CPU, Prism Engine
        (48, 8, 80, 20, 'outline'),                                  # cart connector
        (20, 66, 30, 76, 'smd'), (34, 66, 44, 76, 'smd'), (100, 20, 112, 28, 'smd'),
        (52, 70, 76, 74, 'resistors'), (6, 24, 14, 30, 'smd'), (114, 70, 122, 84, 'outline'),
    ]
    put('pcb_console', pcb_cell(128, 96, console_chips, seed=7), 0, 0)
    pad_chips = []
    for (cx, cy) in [(22, 34), (16, 28), (28, 28), (22, 22)]:      # d-pad contacts
        pad_chips.append((cx - 3, cy - 3, cx + 3, cy + 3, 'pad'))
    for (cx, cy) in [(106, 34), (98, 28), (114, 28), (106, 22)]:   # face buttons
        pad_chips.append((cx - 4, cy - 4, cx + 4, cy + 4, 'pad'))
    pad_chips += [(56, 40, 72, 52, 'smd'), (48, 20, 60, 24, 'resistors'), (70, 20, 82, 24, 'resistors')]
    put('pcb_pad', pcb_cell(128, 64, pad_chips, seed=3), 0, 96)
    put('logo', logo_cell(64, 24, 18, 13), 128, 0)
    put('logo_small', logo_cell(40, 14, 11, 8, sub=False), 128, 24)
    put('port', port_cell(), 128, 40)
    put('card', card_cell(), 152, 40)
    put('label', cart_label(), 128, 56)
    put('emblem', emblem_cell(24), 176, 56)
    put('top_console', smoke_top(72, 52, bands=((0.52, 0.05), (0.78, 0.02))), 0, 160)
    put('top_deck', smoke_top(48, 22, bands=((0.62, 0.09),)), 72, 160)
    put('top_pad', smoke_top(58, 36, bands=((0.50, 0.08), (0.78, 0.03))), 120, 160)
    sheet.save(os.path.join(ART, 'clear_smoke.png'))
    with open(os.path.join(ART, 'clear_smoke.sheet.json'), 'w') as fh:
        json.dump({'format': 'mei-sheet', 'version': 1, 'cells': cells}, fh, indent=1)
        fh.write('\n')
    print('wrote', os.path.join(ART, 'clear_smoke.png'), sorted(cells))


if __name__ == '__main__':
    main()
