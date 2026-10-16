#!/usr/bin/env python3
"""Captures of the moving water in the cart (agent W, NOTES_W.md): each stage played on its
solution tapes through the front end's transitions (tests/water/, scenario 97), and in chosen
rooms a run of frames as the game draws them, a strip of a few frames and an animated GIF.

    python3 carts/afterhours/water/capture.py --build-dir build-ah-W [--out DIR] [--only NAME]

Needs the cart's worlds built (make B=... B/carts/afterhours.mei) and Pillow. Writes
DIR/NAME_strip.png (four frames, EVERY * 3 ticks apart, side by side), DIR/NAME.gif (every
EVERY-th frame for COUNT frames) and DIR/NAME_crop.png (the strip cropped to the water, scaled
twice), default water/shots/.
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
CART = HERE.parent
REPO = CART.parents[1]

# name: (stage, the room (in the run's order, 1-based), its visit (1: the first), ticks into the
# visit, the crop (x0, y0, x1, y1) of the 320 x 240 picture that holds its water)
SHOTS = {
    'ocean': ('STAGE_AQUARIUM', 4, 1, 330, (0, 40, 320, 200)),
    'tops': ('STAGE_AQUARIUM', 8, 1, 300, (0, 30, 320, 200)),
    'plant': ('STAGE_AQUARIUM', 6, 1, 300, (0, 40, 320, 220)),
    'great': ('STAGE_AQUARIUM', 2, 1, 300, (0, 20, 320, 200)),
    'hall': ('STAGE_AQUARIUM', 1, 1, 260, (0, 40, 320, 220)),
    'jelly': ('STAGE_AQUARIUM', 3, 1, 300, (0, 30, 320, 200)),
    'quar': ('STAGE_AQUARIUM', 5, 1, 300, (0, 30, 320, 210)),
    'kitchen': ('STAGE_AQUARIUM', 7, 1, 300, (0, 30, 320, 210)),
    'roof': ('STAGE_TOWER', 5, 1, 1080, (0, 20, 320, 220)),
    'passage': ('STAGE_STATION', 3, 1, 40, (60, 40, 260, 160)),
    'stair': ('STAGE_STATION', 3, 1, 880, (160, 20, 320, 200)),
}
EVERY = 2
COUNT = 36
STAGE_FRAMES = {'STAGE_STATION': 4000, 'STAGE_TOWER': 10000, 'STAGE_AQUARIUM': 11500, 'STAGE_STORE': 12500}


def run(stage, frames, base, env, seq=None):
    e = dict(env)
    if seq:
        e['SEQ'] = seq
    r = subprocess.run([str(CART / 'tests' / 'water' / 'run.sh'), stage, str(frames), str(base)], env=e,
                       capture_output=True, text=True, cwd=REPO)
    return r.stdout + r.stderr


def entries(log):
    """The frame each room's visits start on: {room: [frames]} (the first room from the start)."""
    out = {}
    m = re.search(r'^START at frame (\d+)', log, re.M)
    first = re.search(r'^TRANS 1 into room', log, re.M)
    if m:
        out.setdefault(1, []).append(int(m.group(1)) + 30)
    for room, f in re.findall(r'^TRANS \d+ into room (\d+) at frame (\d+)', log, re.M):
        out.setdefault(int(room), []).append(int(f))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build-dir', default='build')
    ap.add_argument('--worlds', help='the built worlds (default BUILD/cart-worlds/afterhours)')
    ap.add_argument('--out', default=str(HERE / 'shots'))
    ap.add_argument('--only', action='append', help='only these shots (repeatable)')
    ap.add_argument('--suffix', default='', help='added to the files\' names (e.g. _still)')
    ap.add_argument('--still', action='store_true', help='the water still (water_enabled() false)')
    args = ap.parse_args()
    b = (REPO / args.build_dir).resolve()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, MEIC=str(b / 'meic'), RUN=str(b / 'mei-headless'), TRAP='0', SHOT='1',
               WORLDS=str(Path(args.worlds).resolve() if args.worlds else b / 'cart-worlds' / 'afterhours'))
    if args.still:
        env['W_HEAD'] = 'fn water_enabled() -> bool { return false }'
    names = args.only or list(SHOTS)
    with tempfile.TemporaryDirectory() as tmp:
        logs = {}
        for name in names:
            stage, room, visit, at, crop = SHOTS[name]
            if stage not in logs:
                logs[stage] = run(stage, STAGE_FRAMES[stage], Path(tmp) / stage, env)
                if 'DONE 97' not in logs[stage]:
                    sys.exit(f'{stage} did not finish:\n' + logs[stage][-2000:])
            start = entries(logs[stage])[room][visit - 1] + at
            base = Path(tmp) / name
            run(stage, start + EVERY * COUNT + 1, base, env, seq=f'{EVERY} {start}')
            frames = sorted(Path(tmp).glob(f'{name}_seq_*.png'), key=lambda p: int(re.search(r'(\d+)\.png$', p.name).group(1)))
            frames = [Image.open(f).convert('RGB') for f in frames][:COUNT]
            if not frames:
                sys.exit(f'{name}: no frames')
            pick = [frames[i] for i in range(0, min(len(frames), 12), 3)]
            strip = Image.new('RGB', (320 * len(pick), 240))
            for i, im in enumerate(pick):
                strip.paste(im, (320 * i, 0))
            strip.save(out / f'{name}{args.suffix}_strip.png')
            x0, y0, x1, y1 = crop
            cs = Image.new('RGB', ((x1 - x0) * len(pick), y1 - y0))
            for i, im in enumerate(pick):
                cs.paste(im.crop(crop), ((x1 - x0) * i, 0))
            cs.resize((cs.width * 2, cs.height * 2), Image.NEAREST).save(out / f'{name}{args.suffix}_crop.png')
            big = frames
            big[0].save(out / f'{name}{args.suffix}.gif', save_all=True, append_images=big[1:],
                        duration=round(1000 * EVERY / 60), loop=0)
            print(f'{name}: frames {start}..{start + EVERY * (len(frames) - 1)} ({len(frames)})')


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    main()
