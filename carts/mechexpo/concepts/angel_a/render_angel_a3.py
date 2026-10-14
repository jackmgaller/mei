#!/usr/bin/env python3
"""Mech Expo 2000: renders the angel's third look study (make_angel_a3.py) and draws its sheets.

Every picture is drawn by Mei: the Asset Kit's `preview` of each recipe from the views in
cameras.json, at the console's 320 x 240 (--upscale 1), beside Shadow's and the Hero's own
recipes from the same views. The sheets are laid out with Pillow and scaled nearest-neighbour:

  angelA3_sheet.png     idle, attack and Judgement side-on (the fight camera, nearer), from the
                        front three-quarter and the back three-quarter, beside Shadow and the
                        Hero; the helm close up and the rest pose
  angelA3_paint.png     the paint schemes tried (make_angel_a3.SCHEMES), the idle in each, and
                        each at true game scale against Shadow
  angelA3_overview.png  round two's concept A beside this one, and fight frames at true game
                        scale (320 x 240): each pose against Shadow, the idle against the Hero

Usage: python3 carts/mechexpo/concepts/angel_a/render_angel_a3.py -o OUT [--build-dir B]
[--jobs 2] [--sheets-only] [--only NAME ...] [--round2 RECIPE]. Renders go into
B/angel_a3/. The previews skip the Asset Checker (their copies have verification off); run
`mei_assets.py verify` on the recipes for that. --round2 names round two's concept A idle
(`angel_a_idle.asset.json`, on its own branch), rendered for the comparison; without it the
overview leaves that column out. Needs Pillow and the native tools (make B=B B/meic
B/mei-headless B/mei-asset-probe).
"""
import argparse
import json
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MODELS = HERE.parents[1]/'models'
FONTS = ROOT/'tools'/'fonts'
sys.path.insert(0, str(HERE))
import make_angel_a3 as A  # noqa: E402

POSES = ['angel_a3_idle', 'angel_a3_attack', 'angel_a3_judgement', 'angel_a3_rest']
PAINTS = [f'angel_a3_paint_{k}' for k in A.SCHEMES]
REFS = {'shadow': MODELS/'shadow'/'shadow.asset.json', 'hero': MODELS/'hero'/'hero.asset.json'}

BG, INK, SUB, RULE = (24, 27, 34), (238, 236, 228), (150, 158, 172), (70, 76, 90)
RED, GOLD = (232, 38, 44), (232, 176, 48)
BOX = (60, 0, 260, 240)          # the part of a 320 x 240 view the columns show: 200 x 240


def font(size, bold=True):
    return ImageFont.truetype(str(FONTS/('Figtree-Bold.ttf' if bold else 'Figtree-Medium.ttf')),
                              size)


def label(d, xy, text, size, fill=INK, bold=True):
    d.text(xy, text, font=font(size, bold), fill=fill)


def render(name, src, work, build_dir):
    """The recipe's views from cameras.json, 320 x 240 each, in work/NAME/."""
    data = json.loads(src.read_text())
    data['verification'] = {**data.get('verification', {}), 'required': False}
    data['budget'] = {**data.get('budget', {}), 'triangles': 4000}
    copy = work/'recipes'/f'{name}.asset.json'
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_text(json.dumps(data))
    cmd = [sys.executable, str(ROOT/'tools'/'mei_assets.py'), 'preview', str(copy),
           '-o', str(work/name), '--build-dir', str(build_dir), '--cameras',
           str(HERE/'cameras.json'), '--upscale', '1', '--look', str(HERE/'asset-preview.json')]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        raise SystemExit(f'{name}: preview failed\n{r.stdout}\n{r.stderr}')
    return name, triangles(work, name)


def triangles(work, name):
    rep = work/name/'report.json'
    if not rep.exists():
        return None
    r = json.loads(rep.read_text())
    return r.get('triangles') or r.get('mesh', {}).get('triangles')


def view(work, name, cam):
    return Image.open(work/name/f'camera_{cam}.png').convert('RGB')


def crop(img, box, scale):
    c = img.crop(box)
    return c.resize((c.width*scale, c.height*scale), Image.NEAREST)


def fight(work, left, right, close=False):
    """A fight frame: `left` from the left camera (this mech left of centre facing right), `right`
    from the right one; the halves side by side (the background and floor match, so the seam is
    plain floor)."""
    cl, cr = ('close_left', 'close_right') if close else ('fight_left', 'fight_right')
    out = view(work, left, cl).copy()
    out.paste(view(work, right, cr).crop((160, 0, 320, 240)), (160, 0))
    return out


def big(img, k):
    return img.resize((img.width*k, img.height*k), Image.NEAREST)


def poses_sheet(work, tris, out):
    k = 3
    cols = [('angel_a3_idle', 'Idle guard'), ('angel_a3_attack', 'Attack: lunging straight'),
            ('angel_a3_judgement', 'Judgement'), ('shadow', 'Shadow (UR-01), guard'),
            ('hero', 'Hero (MR-01), stance')]
    rows = [('side_near', 'side-on (the fight camera, nearer)'),
            ('three_quarter', 'front three-quarter'), ('back_quarter', 'back three-quarter')]
    cw, ch = 200*k, 240*k
    pad, head, cap, rowcap = 24, 150, 54, 40
    W = pad+len(cols)*(cw+pad)
    Hh = head+cap+len(rows)*(ch+rowcap)+pad+40+240*2+pad
    img = Image.new('RGB', (W, Hh), BG)
    d = ImageDraw.Draw(img)
    label(d, (pad, 22), 'Momentum\'s angel (MR-02), concept A, round three', 48, RED)
    label(d, (pad, 86), 'Shadow\'s skeleton, a body of its own: knight\'s helm and halo, broad '
                        'breastplate, two-tier pauldrons, heavy bracers and gauntlet fists, hip '
                        'armour, folded layered wings. Drawn by Mei, 320 x 240 views shown 3x.',
          26, SUB, bold=False)
    y = head
    for i, (name, text) in enumerate(cols):
        x = pad+i*(cw+pad)
        label(d, (x, y+8), text, 30, INK if i < 3 else SUB)
        if tris.get(name):
            label(d, (x+cw-150, y+12), f'{tris[name]} tris', 24, SUB, bold=False)
    y += cap
    for cam, text in rows:
        label(d, (pad, y+4), text, 24, SUB, bold=False)
        y += rowcap
        for i, (name, _) in enumerate(cols):
            img.paste(crop(view(work, name, cam), BOX, k), (pad+i*(cw+pad), y))
        y += ch
    y += pad
    d.line([(pad, y-12), (W-pad, y-12)], fill=RULE, width=2)
    label(d, (pad, y), 'The helm close up, side and three-quarter, and the rest pose (every '
                       'joint at 0) from the front and the side, 2x.', 24, SUB, bold=False)
    x = pad
    for cam in ('head_side', 'head_quarter'):
        img.paste(big(view(work, 'angel_a3_rest', cam), 2), (x, y+40))
        x += 640+pad
    for cam in ('front', 'side_near'):
        img.paste(crop(view(work, 'angel_a3_rest', cam), BOX, 2), (x, y+40))
        x += 400+pad
    img.save(out)


def paint_sheet(work, tris, out):
    k = 2
    cw, ch = 200*k, 240*k
    pad, head, cap = 24, 150, 124
    cams = ('side_near', 'three_quarter', 'back_quarter')
    colw = len(cams)*(cw+8)+320*2
    W = pad+len(A.SCHEMES)*0+colw+pad
    Hh = head+len(A.SCHEMES)*(ch+cap+pad)+pad
    img = Image.new('RGB', (W, Hh), BG)
    d = ImageDraw.Draw(img)
    label(d, (pad, 22), 'Paint schemes tried', 48, RED)
    label(d, (pad, 86), 'The idle in each scheme: side-on, front and back three-quarter (2x); '
                        'against Shadow at true game scale (1x, and a 2x detail).', 26, SUB,
          bold=False)
    y = head
    for key, (title, _) in A.SCHEMES.items():
        name = f'angel_a3_paint_{key}'
        chosen = key == A.CHOSEN
        label(d, (pad, y+8), f'{key}. {title}' + ('  (chosen)' if chosen else ''), 34,
              GOLD if chosen else INK)
        label(d, (pad, y+54), '\n'.join(textwrap.wrap(BLURB[key], 150)), 22, SUB, bold=False)
        yy = y+cap
        x = pad
        for cam in cams:
            img.paste(crop(view(work, name, cam), BOX, k), (x, yy))
            x += cw+8
        f = fight(work, name, 'shadow')
        img.paste(f, (x+8, yy))
        img.paste(big(f.crop((40, 60, 200, 240)), 2), (x+8+320+8, yy+120))
        y = yy+ch+pad
    img.save(out)


BLURB = {
    '1': 'Red in three kinds of place: what strikes (cuffs and fists), the armour\'s edges (the '
         'pauldrons\' lower tier, knee guards, codpiece), each wing\'s arch. White plates on a '
         'dark gunmetal frame, chrome flight plates; gold only for the holy parts: halo, crest '
         'and temple wings, the core\'s setting, the knuckles.',
    '2': 'The Hero\'s own blocking with red and white swapped: red pauldron shells, yoke, shin '
         'fronts and sabatons; chrome cuffs and skirts; white fists with gold knuckles.',
    '3': 'White plates on a deep navy frame (darker values, more form); red as big shapes (the '
         'upper wings, the yoke, the knees); gold cuffs and knuckles on white fists.',
}


def overview(work, tris, out, round2):
    k = 3
    pad, head = 24, 130
    cols = ([('round2', 'Round two (A)', SUB)] if round2 else []) + [
        ('angel_a3_idle', 'Round three, idle', RED), ('angel_a3_judgement', 'Judgement', RED),
        ('shadow', 'Shadow (UR-01)', SUB), ('hero', 'Hero (MR-01)', SUB)]
    cw, ch = 200*k, 240*k
    W = pad+len(cols)*(cw+pad)
    fights = [('angel_a3_idle', 'shadow', False, 'idle against Shadow, 1x', 1),
              ('angel_a3_idle', 'shadow', False, 'idle against Shadow, 2x', 2),
              ('angel_a3_attack', 'shadow', True, 'attack against Shadow, closer, 2x', 2),
              ('angel_a3_judgement', 'shadow', False, 'Judgement against Shadow, 2x', 2),
              ('angel_a3_idle', 'hero', False, 'idle against the Hero, 2x', 2),
              ('angel_a3_idle', 'shadow', True, 'idle against Shadow, closer, 2x', 2)]
    Hh = head+54+2*ch+40+pad+60+2*(480+60)+pad
    W = max(W, pad+3*(640+pad))
    img = Image.new('RGB', (W, Hh), BG)
    d = ImageDraw.Draw(img)
    label(d, (pad, 22), 'Momentum\'s angel (MR-02): round two and round three', 44, INK)
    label(d, (pad, 78), 'Top: side-on (the fight camera, nearer) and front three-quarter, 3x. '
                        'Below: fight frames at true game scale (320 x 240) from the fight '
                        'camera (31.2 m; closer: 22 m).', 24, SUB, bold=False)
    y = head
    for i, (name, text, colour) in enumerate(cols):
        x = pad+i*(cw+pad)
        label(d, (x, y+8), text, 30, colour)
        if tris.get(name):
            label(d, (x+cw-150, y+12), f'{tris[name]} tris', 24, SUB, bold=False)
    y += 54
    for cam in ('side_near', 'three_quarter'):
        for i, (name, _, _) in enumerate(cols):
            img.paste(crop(view(work, name, cam), BOX, k), (pad+i*(cw+pad), y))
        y += ch+20
    y += pad
    d.line([(pad, y-12), (W-pad, y-12)], fill=RULE, width=2)
    x, row_y = pad, y
    for n, (a, b, close, text, s) in enumerate(fights):
        f = fight(work, a, b, close)
        if s == 1:
            label(d, (x, row_y+10), text, 24, SUB, bold=False)
            img.paste(f, (x, row_y+50))
            x += 320+pad
            continue
        if x+640 > W:
            x, row_y = pad, row_y+480+60
        label(d, (x, row_y+10), text, 24, SUB, bold=False)
        img.paste(big(f, s), (x, row_y+50))
        x += 640+pad
    img.save(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('-o', '--output', required=True, help='where the sheets go')
    ap.add_argument('--build-dir', default='build')
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--sheets-only', action='store_true', help='reuse the last renders')
    ap.add_argument('--only', nargs='*', help='render only these (names)')
    ap.add_argument('--round2', help="round two's concept A idle recipe, for the comparison")
    a = ap.parse_args()
    build = Path(a.build_dir) if Path(a.build_dir).is_absolute() else ROOT/a.build_dir
    build = build.resolve()
    work = build/'angel_a3'
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    jobs = {n: HERE/f'{n}.asset.json' for n in POSES+PAINTS}
    jobs.update(REFS)
    if a.round2:
        jobs['round2'] = Path(a.round2)
    if not a.sheets_only:
        todo = {n: p for n, p in jobs.items() if not a.only or n in a.only}
        with ThreadPoolExecutor(max(1, a.jobs)) as ex:
            for name, n in ex.map(lambda kv: render(kv[0], kv[1], work, build), todo.items()):
                print(f'{name}: {n} triangles')
    tris = {n: triangles(work, n) for n in jobs}
    poses_sheet(work, tris, out/'angelA3_sheet.png')
    paint_sheet(work, tris, out/'angelA3_paint.png')
    overview(work, tris, out/'angelA3_overview.png', (work/'round2').exists())
    print(f'sheets in {out}')


if __name__ == '__main__':
    main()
