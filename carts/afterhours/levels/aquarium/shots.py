#!/usr/bin/env python3
"""Captures of the aquarium in the cart: A's scenario 85 (the ten legs in order, no overlay)
with a frame saved every 10 ticks, and from it one picture of each leg at a chosen moment, as
the game draws it (the dark, the lights' washes, the cones clipped to the light, both levels).

    python3 carts/afterhours/levels/aquarium/shots.py --build-dir build-mine [--out DIR]

Needs the cart's worlds built in the build directory (make B=... B/carts/afterhours.mei) and
Pillow. Writes DIR/legN_ROOM.png (320 x 240), DIR/legN_ROOM_x3.png and DIR/sheet.png (all ten,
scaled twice) into DIR (default levels/aquarium/shots/).
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
CART = HERE.parents[1]
REPO = CART.parents[1]

# Each leg's room, and when in the leg to look (its clock): a moment the leg's idea shows.
LEGS = [('hall', 300), ('great', 450), ('jelly', 420), ('ocean', 500), ('quar', 600),
        ('plant', 800), ('kitchen', 400), ('tops', 700), ('great_catwalk', 700), ('hall_mezzanine', 600)]
EVERY = 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build-dir', default='build')
    ap.add_argument('--out', default=str(HERE / 'shots'))
    args = ap.parse_args()
    b = (REPO / args.build_dir).resolve()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, MEIC=str(b / 'meic'), RUN=str(b / 'mei-headless'),
               WORLDS=str(b / 'cart-worlds' / 'afterhours'), SHOT='1', SEQ=f'{EVERY}')
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / 's85'
        r = subprocess.run([str(CART / 'tests' / 'run.sh'), '85', '10000', str(base)], env=env,
                           capture_output=True, text=True, cwd=REPO)
        log = r.stdout + r.stderr
        if 'DONE 85' not in log:
            sys.exit('scenario 85 did not pass:\n' + log[-3000:])
        ticks = [int(t) for t in re.findall(r'^LEG \d+ room \d+ door \d+ ticks (\d+)', log, re.M)]
        frames = sorted(Path(tmp).glob('s85_seq_*.png'))
        by = {int(re.search(r'(\d+)\.png$', f.name).group(1)): f for f in frames}
        start = 0
        shots = []
        for k, ((name, at), n) in enumerate(zip(LEGS, ticks)):
            want = start + min(at, n - 1)
            f = by[min(by, key=lambda i: abs(i - want))]
            im = Image.open(f).convert('RGB')
            im.save(out / f'leg{k}_{name}.png')
            im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(out / f'leg{k}_{name}_x3.png')
            shots.append(im)
            start += n
        w, h = shots[0].size
        sheet = Image.new('RGB', (w * 2 * 2, h * 2 * 5))
        for i, im in enumerate(shots):
            sheet.paste(im.resize((w * 2, h * 2), Image.NEAREST), ((i % 2) * w * 2, (i // 2) * h * 2))
        sheet.save(out / 'sheet.png')
    print('wrote', out, 'legs', ticks)


if __name__ == '__main__':
    main()
