"""Draw art/hinomaru_sheet.png and its .sheet.json for the Hinomaru Grey console and controller.

Run: python3 make_art.py (needs Pillow and the macOS Hiragino and Avenir Next fonts).
The sheet is authored art: committed, not rebuilt by make.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, 'art')
JP = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'
JP_BOLD = '/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc'
LATIN = '/System/Library/Fonts/Avenir Next.ttc'

SUN = (240, 160, 64)      # 日, warm orange
MOON = (168, 196, 236)    # 月, pale blue
WHITE = (246, 244, 238)
SHELL = (201, 197, 187)   # the warm light grey
CHAR = (43, 45, 51)       # logo plate charcoal
HINO = (200, 40, 30)      # hinomaru red

SS = 8  # supersampling


def font(path, size, index=0):
    return ImageFont.truetype(path, size, index=index)


def glyph_mei(px):
    """明 as an RGBA image px tall: 日 orange, 月 pale blue, with a dark extrusion shadow."""
    big = px * SS
    f = font(JP, int(big * 1.08))
    mask = Image.new('L', (big * 2, big * 2), 0)
    d = ImageDraw.Draw(mask)
    d.text((0, 0), '明', font=f, fill=255)
    mask = mask.crop(mask.getbbox())
    # split between 日 and 月: the emptiest column near 40 % across
    w, h = mask.size
    cols = [sum(1 for y in range(h) if mask.getpixel((x, y)) > 128) for x in range(w)]
    lo, hi = int(w * 0.30), int(w * 0.50)
    split = min(range(lo, hi), key=lambda x: cols[x])
    out = Image.new('RGBA', mask.size, (0, 0, 0, 0))
    sun = Image.new('RGBA', mask.size, SUN + (255,))
    moon = Image.new('RGBA', mask.size, MOON + (255,))
    left = mask.copy(); left.paste(0, (split, 0, w, h))
    right = mask.copy(); right.paste(0, (0, 0, split, h))
    out.paste(sun, (0, 0), left)
    out.paste(moon, (0, 0), right)
    return out, mask


def paste_glyph(img, xy, px, shadow=(20, 20, 24), depth=1):
    g, mask = glyph_mei(px)
    tw = max(1, round(g.size[0] * px / g.size[1]))
    g = g.resize((tw, px), Image.LANCZOS)
    m = mask.resize((tw, px), Image.LANCZOS)
    for k in range(depth, 0, -1):
        img.paste(Image.new('RGBA', g.size, shadow + (255,)), (xy[0] + k, xy[1] + k), m)
    img.paste(g, xy, g)
    return tw


def text(img, xy, s, size, fill, path=LATIN, index=0, spacing=0):
    """Draw text supersampled then reduced, so small type stays legible."""
    f = font(path, size * SS, index)
    bbox = f.getbbox(s)
    w = bbox[2] + spacing * SS * len(s) + 4 * SS
    hgt = bbox[3] + 2 * SS
    big = Image.new('L', (w, hgt), 0)
    d = ImageDraw.Draw(big)
    x = 0
    for ch in s:
        d.text((x, 0), ch, font=f, fill=255)
        x += f.getlength(ch) + spacing * SS
    big = big.crop(big.getbbox())
    small = big.resize((max(1, big.size[0] // SS), max(1, big.size[1] // SS)), Image.LANCZOS)
    img.paste(Image.new('RGBA', small.size, fill + (255,)), xy, small)
    return small.size


def logo_plate():
    """The console's top badge: 64 x 24, charcoal, 明 and MEI."""
    img = Image.new('RGBA', (64, 24), CHAR + (255,))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 63, 23), outline=(70, 72, 78))
    paste_glyph(img, (4, 3), 17)
    text(img, (26, 3), 'MEI', 11, WHITE, LATIN, 0)
    text(img, (26, 16), 'SUN & MOON', 4, (150, 152, 160), LATIN, 0, spacing=0)
    return img


def pad_badge():
    """The controller's badge: 32 x 12 on the shell grey, 明 and MEI."""
    img = Image.new('RGBA', (32, 12), SHELL + (255,))
    paste_glyph(img, (2, 1), 10, shadow=(120, 116, 108), depth=1)
    text(img, (15, 2), 'MEI', 7, (70, 70, 76), LATIN, 0)
    return img


def fascia():
    """The front strip: two controller ports with their memory card slots above, 128 x 32."""
    img = Image.new('RGBA', (128, 32), (176, 172, 163, 255))
    d = ImageDraw.Draw(img)
    d.line((0, 0, 127, 0), fill=(150, 146, 138))
    for k, cx in enumerate((34, 94)):
        # memory card slot: a dark letterbox with a lighter lip
        d.rectangle((cx - 16, 4, cx + 15, 9), fill=(96, 93, 88))
        d.rectangle((cx - 14, 6, cx + 13, 7), fill=(22, 22, 25))
        # controller port: rounded socket, pins in a black mouth
        d.rounded_rectangle((cx - 13, 13, cx + 12, 27), radius=4, fill=(88, 86, 82))
        d.rounded_rectangle((cx - 10, 16, cx + 9, 24), radius=3, fill=(18, 18, 20))
        for p in range(6):
            x = cx - 8 + p * 3
            d.rectangle((x, 19, x + 1, 20), fill=(150, 140, 110))
        # the port's number, small, beside it
        text(img, (cx + 15 if k == 0 else cx - 20, 17), str(k + 1), 6, (92, 90, 86), LATIN, 0)
    return img


def rear_panel():
    """The back plate's printing: 64 x 16, small labels under the jacks."""
    img = Image.new('RGBA', (64, 16), (176, 172, 163, 255))
    text(img, (3, 9), 'MEINET', 4, (90, 88, 84))
    text(img, (25, 9), 'AV OUT', 4, (90, 88, 84))
    text(img, (47, 9), 'DC IN', 4, (90, 88, 84))
    return img


def cart_label():
    """A launch title's label: 40 x 32. A red sun over grey hills, title band."""
    img = Image.new('RGBA', (40, 32), (238, 232, 218, 255))
    d = ImageDraw.Draw(img)
    for y in range(9, 32):  # dusk sky
        t = (y - 9) / 22
        c = tuple(int(a + (b - a) * t) for a, b in zip((250, 214, 150), (236, 132, 80)))
        d.line((1, y, 38, y), fill=c)
    d.ellipse((13, 13, 27, 27), fill=HINO)
    d.polygon([(1, 31), (1, 24), (10, 19), (18, 25), (26, 20), (38, 26), (38, 31)], fill=(70, 74, 92))
    d.rectangle((0, 0, 39, 8), fill=(36, 36, 42))
    text(img, (3, 2), 'HINODE', 5, WHITE, LATIN, 0)
    paste_glyph(img, (31, 1), 6, depth=0)
    d.rectangle((0, 0, 39, 31), outline=(36, 36, 42))
    return img


def button(letter, base, ink):
    """A face button's top: 16 x 16, the letter engraved in the middle."""
    img = Image.new('RGBA', (16, 16), base + (255,))
    f = font(LATIN, 11 * SS, 0)
    big = Image.new('L', (16 * SS, 16 * SS), 0)
    d = ImageDraw.Draw(big)
    bb = d.textbbox((0, 0), letter, font=f)
    d.text(((16 * SS - (bb[2] - bb[0])) / 2 - bb[0], (16 * SS - (bb[3] - bb[1])) / 2 - bb[1]),
           letter, font=f, fill=255)
    small = big.resize((16, 16), Image.LANCZOS)
    img.paste(Image.new('RGBA', (16, 16), ink + (255,)), (0, 0), small)
    return img


def small_label(s, w, h, base, ink, size):
    img = Image.new('RGBA', (w, h), base + (255,))
    tw, th = text(Image.new('RGBA', (w, h)), (0, 0), s, size, ink)
    text(img, ((w - tw) // 2, (h - th) // 2), s, size, ink)
    return img


def main():
    os.makedirs(ART, exist_ok=True)
    cells = {
        'logo': logo_plate(),
        'fascia': fascia(),
        'rear': rear_panel(),
        'cart': cart_label(),
        'badge': pad_badge(),
        'btn_a': button('A', HINO, (250, 230, 224)),
        'btn_b': button('B', (70, 70, 76), (214, 212, 206)),
        'btn_x': button('X', (150, 146, 140), (52, 52, 58)),
        'btn_y': button('Y', (150, 146, 140), (52, 52, 58)),
        'lbl_start': small_label('START', 24, 8, SHELL, (96, 94, 90), 5),
        'lbl_select': small_label('SELECT', 24, 8, SHELL, (96, 94, 90), 5),
    }
    # shelf-pack the cells into one sheet
    sheet_w, x, y, row_h, rects = 160, 0, 0, 0, {}
    for name, im in cells.items():
        w, h = im.size
        if x + w > sheet_w:
            x, y, row_h = 0, y + row_h, 0
        rects[name] = [x, y, w, h]
        x += w
        row_h = max(row_h, h)
    sheet = Image.new('RGBA', (sheet_w, y + row_h), (0, 0, 0, 0))
    for name, im in cells.items():
        sheet.paste(im, tuple(rects[name][:2]))
    sheet.save(os.path.join(ART, 'hinomaru_sheet.png'))
    with open(os.path.join(ART, 'hinomaru_sheet.sheet.json'), 'w') as fh:
        json.dump({'format': 'mei-sheet', 'version': 1, 'cells': rects}, fh, indent=1)
        fh.write('\n')


if __name__ == '__main__':
    main()
