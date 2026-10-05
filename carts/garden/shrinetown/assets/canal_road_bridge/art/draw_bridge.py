"""Draws bridge_sheet.png and bridge_sheet.sheet.json beside this file: the four name plates on
canal_road_bridge's corner posts (oyabashira), as Japanese road bridges carry them: the bridge's
name in kanji and in kana, the waterway's name and the year it was finished (Showa 39, 1964).
Each cell is one post's inner face, 0.55 m by 1.5 m: granite with a dark plate set in it.
Run once and commit the outputs
(python3 carts/garden/shrinetown/assets/canal_road_bridge/art/draw_bridge.py). Needs Pillow and
macOS's Hiragino Mincho."""
import json, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
JP_FONT = '/System/Library/Fonts/ヒラギノ明朝 ProN.ttc'

GRANITE, GRANITE_D, GRANITE_L = '#b4ae9e', '#9a9486', '#c8c2b2'
PLATE, PLATE_EDGE, INK = '#34302c', '#5a544c', '#d8d0bc'


def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def h32(*v):
    x = 0x9E3779B9
    for n in v:
        x = ((x ^ (n & 0xFFFFFFFF)) * 0x85EBCA6B) & 0xFFFFFFFF
        x ^= x >> 13
    return x


def runs_of(text):
    return ''.join(run for run, _, _ in text)


def plate(text, size, top=5, bottom=47):
    """One post face, 32 x 64 texels (1.7 by 2.3 cm each): granite, a plate from row top to
    bottom, the text down it."""
    key = len(text) if isinstance(text, str) else len(runs_of(text))
    img = Image.new('RGBA', (32, 64), rgb(GRANITE))
    d = ImageDraw.Draw(img)
    for y in range(64):                           # granite fleck
        for x in range(32):
            k = h32(x, y, key) % 13
            if k == 0:
                d.point((x, y), fill=rgb(GRANITE_D))
            elif k == 1:
                d.point((x, y), fill=rgb(GRANITE_L))
    d.rectangle([4, top, 27, bottom], fill=rgb(PLATE_EDGE))
    d.rectangle([5, top + 1, 26, bottom - 1], fill=rgb(PLATE))
    # text: one string at one size, or runs of (string, size, rows)
    runs = [(text, size, bottom - top - 2)] if isinstance(text, str) else text
    y0 = top + 1
    for run, sz, rows in runs:
        font = ImageFont.truetype(JP_FONT, sz)
        step = rows / len(run)
        for i, ch in enumerate(run):
            d.text((16, y0 + step * (i + 0.5)), ch, font=font, fill=rgb(INK), anchor='mm')
        y0 += rows
    d.line([(0, 55), (31, 55)], fill=rgb(GRANITE_D))   # a joint in the stone
    # snap anti-aliased text to the plate's two colours
    px = img.load()
    for y in range(top + 1, bottom):
        for x in range(5, 27):
            r, g, b, _ = px[x, y]
            px[x, y] = rgb(INK) if r > 110 else rgb(PLATE)
    return img


cells = {}
sheet = Image.new('RGBA', (128, 64), (0, 0, 0, 0))
for i, (name, text, size, top, bottom) in enumerate((('plate_kanji', '宮橋', 19, 5, 47),
                                                     ('plate_kana', 'みやばし', 11, 4, 50),
                                                     ('plate_water', '疏水', 19, 5, 47),
                                                     ('plate_year', [('昭和', 15, 26), ('三九年', 10, 22)], 0, 3, 53))):
    sheet.paste(plate(text, size, top, bottom), (32 * i, 0))
    cells[name] = [32 * i, 0, 32, 64]
sheet.save(os.path.join(HERE, 'bridge_sheet.png'))
with open(os.path.join(HERE, 'bridge_sheet.sheet.json'), 'w') as f:
    json.dump({'format': 'mei-sheet', 'version': 1, 'cells': cells}, f, indent=1)
    f.write('\n')
print('wrote', len(cells), 'cells')
