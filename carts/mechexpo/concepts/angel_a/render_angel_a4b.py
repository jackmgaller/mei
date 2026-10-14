#!/usr/bin/env python3
"""Mech Expo 2000: renders the angel's round 4b (make_angel_a4b.py) and draws its sheets.

As render_angel_a4.py (whose renderer and stand-in column it uses, with cameras_a4b.json):

  angelA4b_sheet.png   Judgement (the halo raised on its joint) side-on, front three-quarter and
                       back three-quarter, and with a stand-in for the effect's halo flare; the
                       halo close up at rest and raised; the flight-plate treatments tried
                       (make_angel_a4b.EDGES), each in Judgement side-on, three-quarter and at
                       game scale
  angelA4b_fight.png   fight frames at true game scale (320 x 240, 31.2 m; closer: 22 m):
                       Judgement against Shadow in the stand-in column, with the stand-in flare;
                       the wings before and after

The flare is a stand-in for the effect, not the effect: the Judgement recipe with the raised
ring grown a third and an additive gold disc in its plane, written into the work folder only.

Usage: python3 carts/mechexpo/concepts/angel_a/render_angel_a4b.py -o OUT [--build-dir B]
[--jobs 2] [--sheets-only] [--only NAME ...]. Renders go into B/angel_a4b/.
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_angel_a4b as M  # noqa: E402
import render_angel_a4 as RR  # noqa: E402

R = RR.R
RR.CAMERAS = HERE/'cameras_a4b.json'      # render_angel_a4.render() reads its views from here
ROOT, BG, INK, SUB, RULE, RED, GOLD, BOX = R.ROOT, R.BG, R.INK, R.SUB, R.RULE, R.RED, R.GOLD, R.BOX
NAMES = ['angel_a4b_judgement', 'angel_a4b_rest', 'angel_a4b_raised'] + [
    f'angel_a4b_edge_{k}' for k in M.EDGES]


def flare_recipe(work):
    """The Judgement recipe with the stand-in flare: the raised ring grown 1.3 times, and an
    additive gold disc in its plane, on the halo joint."""
    data = json.loads((HERE/'angel_a4b_judgement.asset.json').read_text())
    data['materials']['halo_flare'] = {'color': '#8a6a20', 'class': 'emissive', 'blend': 'add'}

    def find(n):
        if n.get('id') == 'halo':
            return n
        for c in n.get('children', []):
            f = find(c)
            if f:
                return f
    joint = find(data['nodes'][0])
    ring = next(c for c in joint['children'] if c['id'] == 'ring')
    ring['transform'] = {**ring['transform'], 'scale': [1.3, 1.3, 1.3]}
    ring['children'].append({'id': 'flare', 'op': 'cylinder', 'radius': 1.25, 'height': 0.04,
                             'segments': 10, 'material': 'halo_flare'})
    path = work/'recipes'/'angel_a4b_flare.src.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return path


def sheet(work, tris, out):
    k = 3
    pad, head = 24, 150
    cw, ch = 200*k, 240*k
    W = pad+5*(cw+pad)
    erow = 40+480+pad
    Hh = head+54+ch+pad+60+480+pad+60+len(M.EDGES)*erow+pad
    img = Image.new('RGB', (W, Hh), BG)
    d = ImageDraw.Draw(img)
    R.label(d, (pad, 22), 'Momentum\'s angel (MR-02), round 4b: the halo joint', 48, RED)
    R.label(d, (pad, 86), 'The halo on its own joint, a child of the head, pivoted 0.45 m above '
                          'and 0.78 m behind it: turned 60 degrees it rises 0.9 m straight up. Its '
                          'growth is the effect\'s (stand-in shown). Drawn by Mei, 3x.', 26, SUB,
            bold=False)
    y = head
    cols = [('angel_a4b_judgement', 'side_near', 'Judgement, side-on'),
            ('angel_a4b_judgement', 'three_quarter', 'front three-quarter'),
            ('angel_a4b_judgement', 'back_quarter', 'back three-quarter'),
            ('angel_a4b_flare', 'side_near', 'with the stand-in flare'),
            ('angel_a4b_flare', 'three_quarter', 'stand-in flare, three-quarter')]
    for i, (name, cam, text) in enumerate(cols):
        x = pad+i*(cw+pad)
        R.label(d, (x, y+8), text, 28, INK if i < 3 else GOLD)
        img.paste(R.crop(R.view(work, name, cam), BOX, k), (x, y+54))
    R.label(d, (W-pad-330, 30), f'{tris.get("angel_a4b_judgement")} triangles', 26, SUB,
            bold=False)
    y += 54+ch+pad
    d.line([(pad, y-12), (W-pad, y-12)], fill=RULE, width=2)
    R.label(d, (pad, y), 'The halo close up (2x): at rest (rotation 0, where round four had it) '
                         'and raised (x 60), from the side and a front quarter.', 24, SUB,
            bold=False)
    x = pad
    for name, text in (('angel_a4b_rest', 'rest'), ('angel_a4b_raised', 'raised')):
        for cam in ('halo_side', 'halo_quarter'):
            img.paste(R.big(R.view(work, name, cam), 2), (x, y+50))
            R.label(d, (x+12, y+58), f'{text}, {cam.split("_")[1]}', 24, INK)
            x += 640+pad
    y += 60+480+pad
    d.line([(pad, y-12), (W-pad, y-12)], fill=RULE, width=2)
    R.label(d, (pad, y), 'The flight plates spread (Judgement): the treatments tried, side-on and '
                         'three-quarter (2x), against Shadow at game scale (2x), and that '
                         'frame\'s angel at 4x.', 24, SUB,
            bold=False)
    y += 60
    for key, (title, *_rest) in M.EDGES.items():
        name = f'angel_a4b_edge_{key}'
        chosen = key == M.EDGE
        R.label(d, (pad, y), f'{key}. {title}' + ('  (chosen)' if chosen else ''), 26,
                GOLD if chosen else INK)
        x = pad
        for cam in ('side_near', 'three_quarter'):
            img.paste(R.crop(R.view(work, name, cam), BOX, 2), (x, y+40))
            x += 400+pad
        img.paste(R.big(R.fight(work, name, 'shadow'), 2), (x, y+40))
        x += 640+pad
        # that frame's angel, 4x
        img.paste(R.big(R.view(work, name, 'fight_left').crop((60, 35, 180, 155)), 4), (x, y+40))
        if tris.get(name):
            R.label(d, (x+480+pad, y+44), f'{tris[name]} tris', 24, SUB, bold=False)
        y += erow
    img.save(out)


def fight_sheet(work, out):
    pad, head = 24, 130
    W = pad+320+pad*2+960+pad*2+640+pad
    Hh = head+(50+720+40)+(50+480+40)+pad
    img = Image.new('RGB', (W, Hh), BG)
    d = ImageDraw.Draw(img)
    R.label(d, (pad, 22), 'Round 4b at true game scale', 44, INK)
    R.label(d, (pad, 78), 'Fight frames, 320 x 240, from the fight camera (31.2 m; closer: 22 m). '
                          'The column and the halo flare are stand-in shapes, not the effect.', 24,
            SUB, bold=False)
    y = head
    f = R.fight(work, 'angel_a4b_flare', 'shadow_column')
    x = pad
    for s, text in ((1, 'Judgement, 1x'), (3, 'Judgement, halo raised and flaring, in the column, '
                                               '3x')):
        R.label(d, (x, y+10), text, 24, GOLD, bold=s == 3)
        img.paste(R.big(f, s), (x, y+50))
        x += 320*s+pad*2
    R.label(d, (x, y+10), 'closer (22 m), 2x', 24, GOLD, bold=False)
    img.paste(R.big(R.fight(work, 'angel_a4b_flare', 'shadow_column', True), 2), (x, y+50))
    y += 50+720+40
    d.line([(pad, y-16), (W-pad, y-16)], fill=RULE, width=2)
    x = pad
    for name, text in (('angel_a4b_edge_0', 'wings before: round four\'s chrome, 2x'),
                       (f'angel_a4b_edge_{M.EDGE}', 'wings after: ' + M.EDGES[M.EDGE][0] + ', 2x')):
        R.label(d, (x, y+10), text, 24, SUB, bold=False)
        img.paste(R.big(R.fight(work, name, 'shadow'), 2), (x, y+50))
        x += 640+pad*2
    img.save(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('-o', '--output', required=True, help='where the sheets go')
    ap.add_argument('--build-dir', default='build')
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--sheets-only', action='store_true', help='reuse the last renders')
    ap.add_argument('--only', nargs='*', help='render only these (names)')
    a = ap.parse_args()
    build = Path(a.build_dir) if Path(a.build_dir).is_absolute() else ROOT/a.build_dir
    build = build.resolve()
    work = build/'angel_a4b'
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    jobs = {n: HERE/f'{n}.asset.json' for n in NAMES}
    jobs.update(R.REFS)
    jobs['shadow_column'] = RR.column_recipe(work)
    jobs['angel_a4b_flare'] = flare_recipe(work)
    if not a.sheets_only:
        todo = {n: p for n, p in jobs.items() if not a.only or n in a.only}
        with ThreadPoolExecutor(max(1, a.jobs)) as ex:
            for name, n in ex.map(lambda kv: RR.render(kv[0], kv[1], work, build),
                                  todo.items()):
                print(f'{name}: {n} triangles')
    tris = {n: R.triangles(work, n) for n in jobs}
    sheet(work, tris, out/'angelA4b_sheet.png')
    fight_sheet(work, out/'angelA4b_fight.png')
    print(f'sheets in {out}')


if __name__ == '__main__':
    main()
