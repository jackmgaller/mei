"""Draws art/sheet.png and art/sheet.sheet.json for the recycling station (authored art, run once).

Needs Pillow and macOS's Hiragino Sans GB:
python3 carts/garden/shrinetown/assets/recycling_station/art/draw_sheet.py (copied from the lab)
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc', 12, index=1)

CELLS = {'board': [0, 0, 80, 48], 'bin': [80, 0, 64, 32], 'lid': [80, 32, 16, 16]}
sheet = Image.new('RGBA', (144, 48), (0, 0, 0, 0))


def text(d, xy, s, fill, centre_w=None):
    d.fontmode = '1'
    x, y = xy
    if centre_w is not None:
        w = d.textlength(s, font=FONT)
        x = x + (centre_w - w) // 2
    d.text((x, y), s, font=FONT, fill=fill)


# The neighbourhood's notice board: which day takes what, and a warning about crows.
board = Image.new('RGB', (80, 96), '#f2eedd')
d = ImageDraw.Draw(board)
d.rectangle([0, 0, 79, 95], outline='#245a36')
d.rectangle([1, 1, 78, 16], fill='#2f7d46')
text(d, (0, 2), 'ごみ集積所', '#ffffff', 80)
rows = [('月木', 'もえる', '#d23c2c'), ('水', 'かん', '#2b5fa8'),
        ('金', 'びん', '#2f8a4a'), ('土', 'ペット', '#e0a81c')]
for i, (day, what, col) in enumerate(rows):
    y = 20 + i * 15
    text(d, (4, y), day, '#2a2a2a')
    d.rounded_rectangle([30, y, 76, y + 13], radius=3, fill=col)
    text(d, (30, y), what, '#ffffff', 47)
d.line([4, 80, 75, 80], fill='#c9c3ad')
text(d, (0, 82), 'カラス注意', '#d23c2c', 80)
# stored at half height (80 x 48; the face stretches it back): the town's texture budget (TEXTURES.md)
sheet.paste(board.resize((80, 48), Image.Resampling.BOX), (0, 0))

# The burnables bin, wrapped round twice: ribs, and a label front and back (the image's centre).
binimg = Image.new('RGB', (64, 32), '#2b5fa8')
d = ImageDraw.Draw(binimg)
for y in (2, 29):
    d.line([0, y, 63, y], fill='#1f4785')
d.line([0, 30, 63, 30], fill='#3a74c4')
d.rectangle([17, 9, 46, 23], fill='#f4f1e6')
d.rectangle([17, 9, 46, 10], fill='#d23c2c')
text(d, (17, 10), '可燃', '#d23c2c', 30)
sheet.paste(binimg, (80, 0))

# Its lid from above: a rim, a handle.
lid = Image.new('RGB', (16, 16), '#2b5fa8')
d = ImageDraw.Draw(lid)
d.ellipse([2, 2, 13, 13], outline='#3a74c4')
d.rectangle([5, 7, 10, 8], fill='#1a3a6c')
sheet.paste(lid, (80, 32))

sheet.save(os.path.join(HERE, 'sheet.png'))
with open(os.path.join(HERE, 'sheet.sheet.json'), 'w') as f:
    json.dump({'format': 'mei-sheet', 'version': 1, 'cells': CELLS}, f, indent=1)
    f.write('\n')
