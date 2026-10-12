#!/usr/bin/env python3
"""Mech Expo 2000: a lightbox banner tower for the expo floor, in front of the crowds and
booths (D's plane art) and behind the fighters: a pole on a weighted base with a pair of tall
lit banners, MECH EXPO on one and 2000 on the other, in the show's blue and white.

Writes, beside this script:
  expo_banner.asset.json  15 m tall, the banners 2.6 x 9.4 m each side of the pole, facing -Z;
                          its origin on the floor under the pole. Meant for the midground (about
                          z = +8 to +20), where it stands above the mechs' shoulders
  art/banner_expo.png, art/banner_2000.png   the banners' faces, drawn with the OFL fonts in
                          tools/fonts/ (Figtree Black Italic, Sofia Sans Condensed)
  cameras.json            the game's camera (the banner 12 m behind the fight plane) and closer

The banner faces are emissive: lit from behind, as a lightbox is, so they hold their colour
under the hall's light. Run from anywhere: python3 carts/mechexpo/models/expo_banner/make_expo_banner.py
(Pillow).
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FONTS = ROOT/'tools'/'fonts'
LIGHTING = {'direction': [0, 0.62, -0.78], 'ambient': 0.66}   # the mechs' light
POLICY = {'required': True, 'depth': True, 'perspective': True}

TOP_BLUE, LOW_BLUE, WHITE, CYAN = (18, 62, 168), (64, 170, 238), (246, 248, 252), (150, 236, 255)

MATERIALS = {
    'chrome':  {'color': '#c6d0dc', 'smooth': True},
    'base':    {'color': '#3c4454'},
    'cloth':   {'color': '#1d4fb0'},
    'expo':    {'color': '#2f7fe0', 'class': 'emissive',
                'texture': {'image': 'art/banner_expo.png', 'projection': 'fit'}},
    'y2k':     {'color': '#2f7fe0', 'class': 'emissive',
                'texture': {'image': 'art/banner_2000.png', 'projection': 'fit'}},
}

W, H, S = 32, 112, 8          # texels, and the supersampling the art is drawn at


def field():
    """A vertical gradient, blue at the top to light blue, with a white band and a cyan rule."""
    im = Image.new('RGB', (W*S, H*S))
    d = ImageDraw.Draw(im)
    for y in range(H*S):
        t = y/(H*S-1)
        d.line([(0, y), (W*S, y)], fill=tuple(round(a+(b-a)*t) for a, b in zip(TOP_BLUE, LOW_BLUE)))
    d.rectangle([0, 3*S, W*S, 5*S-1], fill=WHITE)
    d.rectangle([0, (H-6)*S, W*S, (H-5)*S-1], fill=CYAN)
    return im, d


def fitted(name, text, length, height):
    """The font at the largest size whose `text` is at most `length` long and `height` tall
    (in drawing pixels)."""
    size = height
    while True:
        font = ImageFont.truetype(str(FONTS/name), size)
        l, t, r, b = font.getbbox(text)
        if r-l <= length and b-t <= height:
            return font
        size -= S//2


def vertical_text(im, text, font, centre, fill):
    """Text turned to read bottom to top, centred on `centre`."""
    l, t, r, b = font.getbbox(text)
    tile = Image.new('L', (r-l+8, b-t+8), 0)
    ImageDraw.Draw(tile).text((4-l, 4-t), text, font=font, fill=255)
    tile = tile.rotate(90, expand=True)
    x, y = centre[0]-tile.width//2, centre[1]-tile.height//2
    im.paste(Image.new('RGB', tile.size, fill), (x, y), tile)


def finish(im, path):
    im = im.resize((W, H), Image.BOX).quantize(colors=12, method=Image.Quantize.MEDIANCUT,
                                                  dither=Image.Dither.NONE)
    im.convert('RGB').save(path)


def draw_expo(path):
    im, d = field()
    # an orbit ring round a bright dot at the top: the show's mark
    cx, cy, r = W*S//2, 16*S, 9*S
    d.ellipse([cx-r, cy-r*0.55, cx+r, cy+r*0.55], outline=WHITE, width=2*S)
    d.ellipse([cx-3*S, cy-3*S, cx+3*S, cy+3*S], fill=CYAN)
    font = fitted('Figtree-BlackItalic.ttf', 'MECH EXPO', 74*S, 22*S)
    vertical_text(im, 'MECH EXPO', font, (W*S//2, 66*S), WHITE)
    finish(im, path)


def draw_2000(path):
    im, d = field()
    font = fitted('Figtree-BlackItalic.ttf', '2000', 54*S, 22*S)
    vertical_text(im, '2000', font, (W*S//2, 38*S), WHITE)
    small = fitted('SofiaSansCondensed-SemiBold.ttf', 'UAPC TRIAL', 36*S, 12*S)
    vertical_text(im, 'UAPC TRIAL', small, (W*S//2, 86*S), CYAN)
    finish(im, path)


def box(id_, size, mat, centre, faces=None, open_=None):
    n = {'id': id_, 'op': 'box', 'size': size, 'material': mat,
         'transform': {'translate': centre}}
    if faces:
        n['faces'] = faces
    if open_:
        n['open'] = open_
    return n


def nodes():
    bz = -0.3                                   # the banners hang in front of the pole
    return [
        box('base', [3.0, 0.4, 2.0], 'base', [0, 0.2, 0], open_=['bottom']),
        box('pole', [0.36, 15.0, 0.36], 'chrome', [0, 7.85, 0], open_=['bottom']),
        {'id': 'finial', 'op': 'cone', 'radius': 0.34, 'height': 0.8, 'segments': 6,
         'material': 'chrome', 'transform': {'translate': [0, 15.65, 0]}},
        box('bar_top', [6.4, 0.24, 0.24], 'chrome', [0, 14.2, bz+0.02]),
        box('bar_low', [6.4, 0.2, 0.2], 'chrome', [0, 4.62, bz+0.04]),
        box('banner_expo', [2.6, 9.4, 0.08], 'cloth', [-1.62, 9.4, bz+0.04],
            faces={'back': 'expo'}),
        box('banner_2000', [2.6, 9.4, 0.08], 'cloth', [1.62, 9.4, bz+0.04],
            faces={'back': 'y2k'}),
    ]


def main():
    (HERE/'art').mkdir(exist_ok=True)
    draw_expo(HERE/'art'/'banner_expo.png')
    draw_2000(HERE/'art'/'banner_2000.png')
    recipe = {'format': 'mei-asset', 'version': 1, 'name': 'expo_banner',
              'budget': {'vertices': 256, 'triangles': 100},
              'lighting': LIGHTING, 'verification': POLICY,
              'materials': MATERIALS, 'nodes': nodes()}
    (HERE/'expo_banner.asset.json').write_text(json.dumps(recipe, indent=1)+'\n')
    cams = [
        {'name': 'game', 'eye': [6.0, 6.5, -42.0], 'target': [6.0, 6.5, 0.0]},
        {'name': 'game_near', 'eye': [3.0, 6.0, -26.0], 'target': [1.0, 8.0, 0.0]},
        {'name': 'face', 'eye': [0.0, 9.4, -16.0], 'target': [0.0, 9.4, 0.0]},
        {'name': 'quarter', 'eye': [-9.0, 6.0, -12.0], 'target': [0.0, 9.0, 0.0]},
    ]
    (HERE/'cameras.json').write_text(json.dumps(cams, indent=1)+'\n')


if __name__ == '__main__':
    main()
