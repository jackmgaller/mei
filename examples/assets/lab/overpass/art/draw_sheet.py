"""Draws art/sheet.png and art/sheet.sheet.json for the pedestrian overpass (authored art, run once).

Needs Pillow and macOS's Hiragino Sans GB:
python3 examples/assets/lab/overpass/art/draw_sheet.py
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc', 12, index=1)
BLUE, WHITE = '#1f4f9c', '#f4f4ee'

CELLS = {}
sheet = Image.new('RGBA', (256, 128), (0, 0, 0, 0))
cursor = {'x': 0, 'y': 0, 'row_h': 0}


def place(name, img):
    if cursor['x'] + img.width > sheet.width:
        cursor['x'], cursor['y'], cursor['row_h'] = 0, cursor['y'] + cursor['row_h'], 0
    sheet.paste(img, (cursor['x'], cursor['y']))
    CELLS[name] = [cursor['x'], cursor['y'], img.width, img.height]
    cursor['x'] += img.width
    cursor['row_h'] = max(cursor['row_h'], img.height)


def text(d, x, y, s, fill, centre_w=None):
    d.fontmode = '1'
    if centre_w is not None:
        x += (centre_w - d.textlength(s, font=FONT)) // 2
    d.text((x, y), s, font=FONT, fill=fill)


# The guide sign facing the traffic: the station ahead, the town hall left, the park right.
img = Image.new('RGB', (128, 56), BLUE)
d = ImageDraw.Draw(img)
d.rectangle([1, 1, 126, 54], outline=WHITE)
# up arrow
d.polygon([(64, 6), (74, 18), (68, 18), (68, 48), (60, 48), (60, 18), (54, 18)], fill=WHITE)
text(d, 42, 5, '駅', WHITE)
text(d, 74, 5, '前', WHITE)
# left: town hall
d.polygon([(6, 38), (14, 31), (14, 35), (26, 35), (26, 41), (14, 41), (14, 45)], fill=WHITE)
text(d, 6, 12, '市役所', WHITE)
d.rectangle([6, 27, 41, 28], fill=WHITE)
# right: the park, in green
d.polygon([(121, 38), (113, 31), (113, 35), (101, 35), (101, 41), (113, 41), (113, 45)], fill=WHITE)
d.rounded_rectangle([86, 11, 121, 25], radius=2, fill='#2f8a4a')
text(d, 86, 12, '公園', WHITE, 36)
place('sign', img)

# The bridge's name plate.
img = Image.new('RGB', (64, 16), '#ece8d8')
d = ImageDraw.Draw(img)
d.rectangle([0, 0, 63, 15], outline='#6a6a62')
text(d, 0, 1, 'めい歩道橋', '#283850', 64)
place('plate', img)

# A traffic-safety banner hung on the railing.
img = Image.new('RGB', (64, 16), WHITE)
d = ImageDraw.Draw(img)
d.rectangle([0, 0, 63, 1], fill='#2f8a4a')
d.rectangle([0, 14, 63, 15], fill='#2f8a4a')
text(d, 0, 2, '交通安全', '#d23c2c', 64)
place('banner', img)

sheet = sheet.crop((0, 0, sheet.width, cursor['y'] + cursor['row_h']))
sheet.save(os.path.join(HERE, 'sheet.png'))
with open(os.path.join(HERE, 'sheet.sheet.json'), 'w') as f:
    json.dump({'format': 'mei-sheet', 'version': 1, 'cells': CELLS}, f, indent=1)
    f.write('\n')
