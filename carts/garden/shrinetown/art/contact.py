#!/usr/bin/env python3
"""Contact sheets of preview_scratch.py's pictures: one row a view, before day | after day |
before night | after night, 320 x 240 each, into --out (default $B/water_skyline/sheets/).

    B=build-ws python3 carts/garden/shrinetown/art/contact.py [--views a,b] [--per 4] [--out DIR]
"""
import argparse
import json
import os
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
B = os.environ.get('B', 'build')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--views')
    ap.add_argument('--per', type=int, default=4)
    ap.add_argument('--out')
    ap.add_argument('--before', default='before')
    ap.add_argument('--after', default='after')
    ap.add_argument('--motion', help='VIEW,VIEW: a row each, day, of the shots in motion_N/ at --frames N,N,N,N')
    ap.add_argument('--frames')
    a = ap.parse_args()
    base = ROOT / B / 'water_skyline'
    out = Path(a.out) if a.out else base / 'sheets'
    out.mkdir(parents=True, exist_ok=True)
    if a.motion:
        fr = a.frames.split(',')
        names = a.motion.split(',')
        sheet = Image.new('RGB', (320 * len(fr), 240 * len(names)))
        d = ImageDraw.Draw(sheet)
        for r, v in enumerate(names):
            for c, f in enumerate(fr):
                sheet.paste(Image.open(base / a.after / f'motion_{f}' / f'{v}_day.png').convert('RGB'), (c * 320, r * 240))
                d.text((c * 320 + 4, r * 240 + 4), f'{v}, frame {f}', fill=(255, 255, 0))
        sheet.save(out / 'motion.png')
        print(out / 'motion.png')
        return
    views = a.views.split(',') if a.views else list(json.loads((HERE / 'views.json').read_text()))
    for n in range(0, len(views), a.per):
        chunk = views[n:n + a.per]
        sheet = Image.new('RGB', (1280, 240 * len(chunk)), (20, 20, 20))
        d = ImageDraw.Draw(sheet)
        for r, v in enumerate(chunk):
            for c, (tag, vn) in enumerate(((a.before, 'day'), (a.after, 'day'), (a.before, 'night'), (a.after, 'night'))):
                f = base / tag / 'shots' / f'{v}_{vn}.png'
                if f.exists():
                    sheet.paste(Image.open(f).convert('RGB'), (c * 320, r * 240))
            d.text((4, r * 240 + 4), v, fill=(255, 255, 0))
        name = out / f'sheet_{n // a.per + 1}.png'
        sheet.save(name)
        print(name)


if __name__ == '__main__':
    main()
