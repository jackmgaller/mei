"""Draws grille_sheet.png and grille_sheet.sheet.json beside this file, the textures of
canal_grille (the culvert grille where the canal leaves the town under the viaduct):

- screen: the trash screen's bars, a cutout 32 x 32 for 1 m x 1 m (flat iron bars 3 cm wide
  every 12.5 cm, a stiffener across, rust streaks);
- fence: the fall-prevention railing on the headwall, a cutout 32 x 16 for 2 m x 1.1 m (top and
  bottom rails, a post every 2 m, bars every 12.5 cm), in the grey-green paint of 1980s civil
  works;
- kiken: the warning plate, 32 x 16 for 0.6 x 0.3 m: 危険 in white on red over a white band.

Run once and commit the outputs
(python3 carts/garden/shrinetown/assets/canal_grille/art/draw_grille.py). Needs Pillow and
macOS's Hiragino Sans."""
import json, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = '/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc'


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def h32(*v):
    x = 0x9E3779B9
    for n in v:
        x = ((x ^ (n & 0xFFFFFFFF)) * 0x85EBCA6B) & 0xFFFFFFFF
        x ^= x >> 13
    return x


IRON, IRON_L, RUST, RUST_D = rgb('#3a3a38'), rgb('#5a5a56'), rgb('#7a4a2e'), rgb('#5a3a28')
PAINT, PAINT_L, PAINT_D = rgb('#6f8a80'), rgb('#8aa49a'), rgb('#4e665e')
RED, WHITE, INK = rgb('#c8301e'), rgb('#eceae4'), rgb('#2c2a28')


def screen():
    im = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    for x in range(0, 32, 4):
        for y in range(32):
            c = IRON_L if y % 7 == 0 else IRON
            if h32(x, y // 3, 5) % 9 == 0:
                c = RUST if h32(x, y, 2) % 2 else RUST_D
            im.putpixel((x, y), c)
    for y in (14, 15):                       # the stiffener across
        for x in range(32):
            im.putpixel((x, y), IRON_L if y == 14 else IRON)
    return im


def fence():
    im = Image.new('RGBA', (32, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 31, 1], fill=PAINT)   # top rail (the geometry rail sits on it)
    d.line([(0, 1), (31, 1)], fill=PAINT_D)
    d.rectangle([0, 13, 31, 14], fill=PAINT) # bottom rail
    d.line([(0, 14), (31, 14)], fill=PAINT_D)
    for x in range(2, 32, 2):                # bars
        d.line([(x, 2), (x, 12)], fill=PAINT_L if x % 4 else PAINT)
    d.rectangle([0, 0, 1, 15], fill=PAINT)   # a post every 2 m, its foot to the coping
    d.line([(1, 0), (1, 15)], fill=PAINT_D)
    return im


def kiken():
    im = Image.new('RGBA', (32, 16), WHITE)
    d = ImageDraw.Draw(im)
    d.fontmode = '1'
    d.rectangle([0, 0, 31, 9], fill=RED)
    d.text((16, 5), '危険', font=ImageFont.truetype(FONT, 9), fill=WHITE, anchor='mm')
    for x0 in (3, 8, 13, 18, 23):            # the small print, as dashes
        d.line([(x0, 12), (x0 + 3, 12)], fill=INK)
    d.rectangle([0, 0, 31, 15], outline=INK)
    return im


cells = {}
sheet = Image.new('RGBA', (64, 32), (0, 0, 0, 0))
for name, img, (x, y) in (('screen', screen(), (0, 0)), ('fence', fence(), (32, 0)), ('kiken', kiken(), (32, 16))):
    sheet.paste(img, (x, y))
    cells[name] = [x, y, img.width, img.height]
sheet.save(os.path.join(HERE, 'grille_sheet.png'))
with open(os.path.join(HERE, 'grille_sheet.sheet.json'), 'w') as f:
    json.dump({'format': 'mei-sheet', 'version': 1, 'cells': cells}, f, indent=1)
    f.write('\n')
print('wrote', len(cells), 'cells')
