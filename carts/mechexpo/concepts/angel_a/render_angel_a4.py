#!/usr/bin/env python3
"""Mech Expo 2000: renders the angel's fourth look study (make_angel_a4.py) and draws its sheets.

As render_angel_a3.py (whose helpers it uses): each recipe drawn by Mei, the Asset Kit's
`preview` at 320 x 240 from the views in cameras_a4.json, beside Shadow's and the Hero's own
recipes, laid out with Pillow and scaled nearest-neighbour:

  angelA4_sheet.png   idle, lunging straight and Judgement side-on (the fight camera, nearer),
                      front three-quarter and back three-quarter, beside Shadow and the Hero;
                      under them the wings close up, folded (the rest pose) and spread
  angelA4_fight.png   fight frames at true game scale (320 x 240, from the fight camera's 31.2 m;
                      closer: 22 m): the idle and the attack against Shadow, the idle against the
                      Hero, and Judgement against Shadow standing in a stand-in column of light

The column is a stand-in for Judgement's effect, not the effect: Shadow's guard recipe with an
added glowing cylinder (additive blending) on its spot, written into the work folder only.

Usage: python3 carts/mechexpo/concepts/angel_a/render_angel_a4.py -o OUT [--build-dir B]
[--jobs 2] [--sheets-only] [--only NAME ...]. Renders go into B/angel_a4/. The previews skip
the Asset Checker (their copies have verification off); run `mei_assets.py verify` on the
recipes for that. Needs Pillow and the native tools (make B=B B/meic B/mei-headless
B/mei-asset-probe).
"""
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render_angel_a3 as R  # noqa: E402

ROOT = R.ROOT
POSES = ['angel_a4_idle', 'angel_a4_attack', 'angel_a4_judgement', 'angel_a4_rest',
         'angel_a4_spread']
CAMERAS = HERE/'cameras_a4.json'
BG, INK, SUB, RULE, RED, GOLD = R.BG, R.INK, R.SUB, R.RULE, R.RED, R.GOLD
BOX = R.BOX


def column_recipe(work):
    """Shadow's guard standing in the stand-in column: a wide additive gold shaft, a bright core
    and a ring of light on the floor, taller than the fight camera sees."""
    data = json.loads(R.REFS['shadow'].read_text())
    data['materials']['column'] = {'color': '#8a7438', 'class': 'emissive', 'blend': 'add'}
    data['materials']['column_core'] = {'color': '#c8c0a0', 'class': 'emissive', 'blend': 'add'}

    def cyl(id_, r, h, mat, y):
        return {'id': id_, 'op': 'cylinder', 'radius': r, 'height': h, 'segments': 10,
                'material': mat, 'transform': {'translate': [0, y, 0]}}
    data['nodes'] = data['nodes'] + [cyl('column', 2.6, 40.0, 'column', 20.0),
                                     cyl('column_core', 1.1, 40.0, 'column_core', 20.0),
                                     cyl('column_ring', 4.2, 0.12, 'column_core', 0.06)]
    path = work/'recipes'/'shadow_column.src.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return path


def render(name, src, work, build_dir):
    """The recipe's views from cameras_a4.json, 320 x 240 each, in work/NAME/."""
    data = json.loads(src.read_text())
    data['verification'] = {**data.get('verification', {}), 'required': False}
    data['budget'] = {**data.get('budget', {}), 'triangles': 4000}
    copy = work/'recipes'/f'{name}.asset.json'
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_text(json.dumps(data))
    cmd = [sys.executable, str(ROOT/'tools'/'mei_assets.py'), 'preview', str(copy),
           '-o', str(work/name), '--build-dir', str(build_dir), '--cameras', str(CAMERAS),
           '--upscale', '1', '--look', str(HERE/'asset-preview.json')]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        raise SystemExit(f'{name}: preview failed\n{r.stdout}\n{r.stderr}')
    return name, R.triangles(work, name)


def poses_sheet(work, tris, out):
    k = 3
    cols = [('angel_a4_idle', 'Idle guard'), ('angel_a4_attack', 'Attack: lunging straight'),
            ('angel_a4_judgement', 'Judgement'), ('shadow', 'Shadow (UR-01), guard'),
            ('hero', 'Hero (MR-01), stance')]
    rows = [('side_near', 'side-on (the fight camera, nearer)'),
            ('three_quarter', 'front three-quarter'), ('back_quarter', 'back three-quarter')]
    cw, ch = 200*k, 240*k
    pad, head, cap, rowcap = 24, 150, 54, 40
    W = pad+len(cols)*(cw+pad)
    wk = 2
    Hh = head+cap+len(rows)*(ch+rowcap)+pad+50+2*(240*wk+40)+pad
    img = Image.new('RGB', (W, Hh), BG)
    d = ImageDraw.Draw(img)
    R.label(d, (pad, 22), 'Momentum\'s angel (MR-02), concept A, round four', 48, RED)
    R.label(d, (pad, 86), 'Scheme 1 with solid red upper wings; a joint for each wing (folded '
                          'at rest, spread for Judgement); Judgement raises the halo. Drawn by '
                          'Mei, 320 x 240 views shown 3x.', 26, SUB, bold=False)
    y = head
    for i, (name, text) in enumerate(cols):
        x = pad+i*(cw+pad)
        R.label(d, (x, y+8), text, 30, INK if i < 3 else SUB)
        if tris.get(name):
            R.label(d, (x+cw-150, y+12), f'{tris[name]} tris', 24, SUB, bold=False)
    y += cap
    for cam, text in rows:
        R.label(d, (pad, y+4), text, 24, SUB, bold=False)
        y += rowcap
        for i, (name, _) in enumerate(cols):
            img.paste(R.crop(R.view(work, name, cam), BOX, k), (pad+i*(cw+pad), y))
        y += ch
    y += pad
    d.line([(pad, y-12), (W-pad, y-12)], fill=RULE, width=2)
    R.label(d, (pad, y), 'The wings close up (2x), in the rest pose: folded (top), and spread '
                         'on their new joints (bottom); from the back quarter, the side and the '
                         'front.', 24, SUB, bold=False)
    y += 50
    for name, text in (('angel_a4_rest', 'folded'), ('angel_a4_spread', 'spread')):
        R.label(d, (pad, y), text, 26, INK)
        x = pad+130
        for cam in ('wing_back', 'wing_side', 'wing_front'):
            img.paste(R.big(R.view(work, name, cam), wk), (x, y))
            x += 320*wk+pad
        y += 240*wk+40
    img.save(out)


def fight_sheet(work, out):
    pad, head = 24, 130
    W = pad+3*(640+pad)+400
    frames = [
        ('angel_a4_idle', 'shadow', False, 'idle against Shadow, 2x', 2),
        ('angel_a4_attack', 'shadow', True, 'attack against Shadow, closer (22 m), 2x', 2),
        ('angel_a4_idle', 'hero', False, 'idle against the Hero, 2x', 2),
    ]
    Hh = head+(50+480+40)+(50+720+40)+pad
    img = Image.new('RGB', (W, Hh), BG)
    d = ImageDraw.Draw(img)
    R.label(d, (pad, 22), 'Round four at true game scale', 44, INK)
    R.label(d, (pad, 78), 'Fight frames, 320 x 240, from the fight camera (31.2 m; closer: 22 m). '
                          'Judgement\'s column of light is a stand-in shape, not the effect.',
            24, SUB, bold=False)
    y = head
    x = pad
    for a, b, close, text, s in frames:
        R.label(d, (x, y+10), text, 24, SUB, bold=False)
        img.paste(R.big(R.fight(work, a, b, close), s), (x, y+50))
        x += 640+pad
    y += 50+480+40
    d.line([(pad, y-16), (W-pad, y-16)], fill=RULE, width=2)
    f = R.fight(work, 'angel_a4_judgement', 'shadow_column')
    x = pad
    for s, text in ((1, 'Judgement, 1x'), (3, 'Judgement against Shadow in the stand-in '
                                               'column, 3x')):
        R.label(d, (x, y+10), text, 24, GOLD, bold=s == 3)
        img.paste(R.big(f, s), (x, y+50))
        x += 320*s+pad*2
    g = R.fight(work, 'angel_a4_judgement', 'shadow_column', True)
    R.label(d, (x, y+10), 'closer (22 m), 2x', 24, GOLD, bold=False)
    img.paste(R.big(g, 2), (x, y+50))
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
    work = build/'angel_a4'
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    jobs = {n: HERE/f'{n}.asset.json' for n in POSES}
    jobs.update(R.REFS)
    jobs['shadow_column'] = column_recipe(work)
    if not a.sheets_only:
        todo = {n: p for n, p in jobs.items() if not a.only or n in a.only}
        with ThreadPoolExecutor(max(1, a.jobs)) as ex:
            for name, n in ex.map(lambda kv: render(kv[0], kv[1], work, build), todo.items()):
                print(f'{name}: {n} triangles')
    tris = {n: R.triangles(work, n) for n in jobs}
    poses_sheet(work, tris, out/'angelA4_sheet.png')
    fight_sheet(work, out/'angelA4_fight.png')
    print(f'sheets in {out}')


if __name__ == '__main__':
    main()
