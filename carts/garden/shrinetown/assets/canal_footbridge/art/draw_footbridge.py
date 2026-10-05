"""Draws footbridge_sheet.png and footbridge_sheet.sheet.json beside this file: the four name
plates on canal_footbridge's corner posts, in the style of canal_road_bridge's (granite, a dark
plate, cream lettering): the bridge's name in kanji and in kana (湯屋橋, ゆやばし: the sento's
bridge), the waterway's name and the year (Showa 32, 1957, older than the road bridge).
Each cell is one post's inner face, 0.54 m by 1.3 m. Run once and commit the outputs
(python3 carts/garden/shrinetown/assets/canal_footbridge/art/draw_footbridge.py). Needs Pillow
and macOS's Hiragino Mincho."""
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


def plate(runs, key, top, bottom):
    """One post face, 32 x 64 texels: granite, a plate from row top to bottom, the text down it
    as runs of (string, size, rows)."""
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
    y0 = top + 1
    for run, sz, rows in runs:
        font = ImageFont.truetype(JP_FONT, sz)
        step = rows / len(run)
        for i, ch in enumerate(run):
            d.text((16, y0 + step * (i + 0.5)), ch, font=font, fill=rgb(INK), anchor='mm')
        y0 += rows
    d.line([(0, 57), (31, 57)], fill=rgb(GRANITE_D))   # a joint in the stone
    px = img.load()                                    # snap the text to the plate's two colours
    for y in range(top + 1, bottom):
        for x in range(5, 27):
            r, g, b, _ = px[x, y]
            px[x, y] = rgb(INK) if r > 110 else rgb(PLATE)
    return img


PLATES = (('plate_kanji', [('湯屋橋', 15, 46)], 3, 50),
          ('plate_kana', [('ゆやばし', 11, 46)], 3, 50),
          ('plate_water', [('疏水', 19, 42)], 5, 48),
          ('plate_year', [('昭和', 15, 26), ('三二年', 10, 22)], 3, 53))

cells = {}
sheet = Image.new('RGBA', (128, 64), (0, 0, 0, 0))
for i, (name, runs, top, bottom) in enumerate(PLATES):
    sheet.paste(plate(runs, i + 7, top, bottom), (32 * i, 0))
    cells[name] = [32 * i, 0, 32, 64]
sheet.save(os.path.join(HERE, 'footbridge_sheet.png'))
with open(os.path.join(HERE, 'footbridge_sheet.sheet.json'), 'w') as f:
    json.dump({'format': 'mei-sheet', 'version': 1, 'cells': cells}, f, indent=1)
    f.write('\n')
print('wrote', len(cells), 'cells')
