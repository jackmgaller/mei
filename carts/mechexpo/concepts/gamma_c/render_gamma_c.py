#!/usr/bin/env python3
"""Mech Expo 2000: renders Gamma's concept C (make_gamma_c.py) and draws its sheets.

Every picture is drawn by Mei: the Asset Kit's `preview` of each recipe from the views in
cameras.json, at the console's 320 x 240 (--upscale 1), beside Beam's, Tank's and the Hero's own
recipes from the same views. The sheets are laid out with Pillow and scaled nearest-neighbour:

  gamma_c_sheet.png   the poses (idle, the Atomic Ray held, Lead Shielding, Geiger Flare,
                      Ground Zero) side-on from both sides (the fight camera, nearer), front
                      three-quarter and back three-quarter, beside Beam and Tank; close-ups of
                      the head, the reactor hatch, the projector, the shield (stowed and swung
                      out) and the back, and the rest pose
  gamma_c_fight.png   fight frames at true game scale (320 x 240 from the fight camera at
                      31.2 m, and closer at 22 m), against Beam and against the Hero, facing
                      right and facing left, the held ray drawn with a stand-in beam
  gamma_c_paint.png   the paint schemes (make_gamma_c.SCHEMES), the idle in each, and each at
                      game scale against Tank

A fight frame is Gamma's view (this mech 7 m left of centre facing right; closer, 5.5 m) with the
other mech's view from the other side laid over it: the other mech is drawn on a key colour with
no ground and keyed out, so the projector can cross the middle of the frame. The ray is a
stand-in for the effect, not the effect: a recipe of two green cylinders from the muzzle (in the
ray pose) into the other mech, written into the work folder only, drawn on black from the same
camera and added to the frame, as the console's additive blend would.

Usage: python3 carts/mechexpo/concepts/gamma_c/render_gamma_c.py -o OUT [--build-dir B]
[--jobs 2] [--sheets-only] [--only NAME ...]. Renders go into B/gamma_c/. The previews skip the
Asset Checker (their copies have verification off); run `mei_assets.py verify` on the recipes
for that. Needs Pillow and the native tools (make B=B B/meic B/mei-headless B/mei-asset-probe).
"""
import argparse
import json
import math
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
import make_gamma_c as M  # noqa: E402

POSES = ['idle', 'ray', 'shield', 'flare', 'ground_zero', 'rest']
PAINTS = [f'gamma_c_paint_{k}' for k in M.SCHEMES]
REFS = {'beam': MODELS/'beam'/'beam.asset.json', 'tank': MODELS/'tank'/'tank.asset.json',
        'hero': MODELS/'hero'/'hero.asset.json'}
GENERAL = ['side', 'side_near', 'side_near_l', 'three_quarter', 'back_quarter', 'front',
           'fight_left', 'close_left']
SEP = {'fight': 14.0, 'close': 11.0}   # the mechs' distance apart in the fight frames

BG, INK, SUB, RULE = (24, 27, 34), (238, 236, 228), (150, 158, 172), (70, 76, 90)
GREEN, CREAM = (140, 255, 110), (230, 223, 196)
BOX = (60, 0, 260, 240)          # the part of a 320 x 240 view the columns show: 200 x 240


def font(size, bold=True):
    return ImageFont.truetype(str(FONTS/('Figtree-Bold.ttf' if bold else 'Figtree-Medium.ttf')),
                              size)


def label(d, xy, text, size, fill=INK, bold=True):
    d.text(xy, text, font=font(size, bold), fill=fill)


def render(name, src, work, build_dir, cams=None, key=None):
    """The recipe's views (cameras.json, or the ones named), 320 x 240 each, in work/NAME/.
    key: on this background colour with no ground (the other mech, the beam)."""
    data = json.loads(Path(src).read_text())
    data['verification'] = {**data.get('verification', {}), 'required': False}
    data['budget'] = {**data.get('budget', {}), 'triangles': 4000}
    copy = work/'recipes'/f'{name}.asset.json'
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_text(json.dumps(data))
    views = json.loads((HERE/'cameras.json').read_text())
    if cams:
        views = [v for v in views if v['name'] in cams]
    cam_file = work/'recipes'/f'{name}.cameras.json'
    cam_file.write_text(json.dumps(views))
    cmd = [sys.executable, str(ROOT/'tools'/'mei_assets.py'), 'preview', str(copy),
           '-o', str(work/name), '--build-dir', str(build_dir), '--cameras', str(cam_file),
           '--upscale', '1']
    if key:
        cmd += ['--look', 'none', '--background', key, '--ground', 'none', '--depth']
    else:
        cmd += ['--look', str(HERE/'asset-preview.json')]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        raise SystemExit(f'{name}: preview failed\n{r.stdout}\n{r.stderr}')
    # keep the work folder small: only the camera views are used
    for p in (work/name).iterdir():
        if p.is_file() and not (p.name.startswith('camera_') and p.suffix == '.png') \
                and p.name != 'report.json':
            p.unlink()
    return name, triangles(work, name)


def triangles(work, name):
    rep = work/name/'report.json'
    if not rep.exists():
        return None
    r = json.loads(rep.read_text())
    return r.get('triangles') or r.get('mesh', {}).get('triangles')


def ray_recipe(work, sep):
    """The stand-in beam alone, in Gamma's frame for its ray pose: a core cylinder inside an
    additive outer one, from the muzzle along the barrel into the other mech, `sep` metres
    ahead. Drawn on black and added to the fight frame (as blend mode add would draw it)."""
    st, drop = M.poses()['ray']
    m, d = M.muzzle_world(st, drop)
    length = round((m[2]+sep-0.6)/max(0.2, -d[2]), 3)
    a = math.degrees(math.atan2(d[2], d[1]))        # turns the cylinder's +Y onto the barrel
    centre = [round(m[k]+d[k]*length/2, 3) for k in range(3)]
    nodes = [{'id': id_, 'op': 'cylinder', 'radius': r, 'height': length, 'segments': 8,
              'material': mat, 'transform': {'rotate': [round(a, 3), 0, 0], 'translate': centre}}
             for id_, r, mat in (('ray_core', 0.3, 'core'), ('ray', 0.7, 'outer'))]
    data = {'format': 'mei-asset', 'version': 1, 'name': f'ray{int(sep)}',
            'budget': {'vertices': 256, 'triangles': 200}, 'lighting': M.LIGHTING,
            'materials': {'core': {'color': '#a8f890', 'class': 'emissive'},
                          'outer': {'color': '#2c8a22', 'class': 'emissive', 'blend': 'add'}},
            'nodes': nodes}
    path = work/'recipes'/f'ray{int(sep)}.src.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return path


def view(work, name, cam):
    return Image.open(work/name/f'camera_{cam}.png').convert('RGB')


def crop(img, box, scale):
    c = img.crop(box)
    return c.resize((c.width*scale, c.height*scale), Image.NEAREST)


def big(img, k):
    return img.resize((img.width*k, img.height*k), Image.NEAREST)


def fight(work, left, right, close=False, flip=False, ray=False):
    """A fight frame: `left` (Gamma) from the left camera, the other mech from the right camera
    on the key colour laid over it. flip: Gamma from the right camera (facing left, its left
    side, the shield arm, to the camera), the other mech from the left. ray: the stand-in beam
    added over both."""
    cl, cr = ('close_left', 'close_right') if close else ('fight_left', 'fight_right')
    if flip:
        cl, cr = cr, cl
    out = view(work, left, cl).copy()
    over = view(work, f'{right}_key', cr)
    px, po = out.load(), over.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b = po[x, y]
            if not (r > 200 and g < 60 and b > 200):
                px[x, y] = (r, g, b)
    if ray:
        beam = view(work, f'ray{int(SEP["close" if close else "fight"])}', cl).load()
        for y in range(out.height):
            for x in range(out.width):
                r, g, b = beam[x, y]
                if r or g or b:
                    q = px[x, y]
                    px[x, y] = (min(255, q[0]+r), min(255, q[1]+g), min(255, q[2]+b))
    return out


def poses_sheet(work, tris, out):
    k = 3
    cols = [('gamma_c_idle', 'Idle: Beam\'s guard'), ('gamma_c_ray', 'Atomic Ray, held'),
            ('gamma_c_shield', 'Lead Shielding'), ('gamma_c_flare', 'Geiger Flare'),
            ('gamma_c_ground_zero', 'Ground Zero'), ('beam', 'Beam (RC-03), guard'),
            ('tank', 'Tank (HA-57), guard')]
    rows = [('side_near', 'side-on (the fight camera, nearer)'),
            ('side_near_l', 'side-on, the other facing (the shield side)'),
            ('three_quarter', 'front three-quarter'), ('back_quarter', 'back three-quarter')]
    close = [('gamma_c_rest', 'head_quarter', 'the searchlight head'),
             ('gamma_c_rest', 'head_side', 'head, side and front'),
             ('gamma_c_rest', 'reactor_quarter', 'the reactor hatch (louvres)'),
             ('gamma_c_rest', 'reactor_side', 'reactor, side-on'),
             ('gamma_c_idle', 'gun_side', 'the ray projector'),
             ('gamma_c_idle', 'gun_quarter', 'projector, front quarter'),
             ('gamma_c_idle', 'shield_stowed', 'shield stowed on the forearm'),
             ('gamma_c_shield', 'shield_front', 'shield swung out (weapon_l y 90)'),
             ('gamma_c_shield', 'shield_quarter', 'shield swung out, side quarter'),
             ('gamma_c_rest', 'back_close', 'the back: cans, toolbox, whip'),
             ('gamma_c_rest', 'front', 'rest pose (every joint at 0)'),
             ('gamma_c_rest', 'side_near', 'rest pose, side')]
    cw, ch = 200*k, 240*k
    pad, head, cap, rowcap = 24, 150, 54, 40
    W = pad+len(cols)*(cw+pad)
    per = (W-pad)//(640+pad)
    crows = (len(close)+per-1)//per
    Hh = head+cap+len(rows)*(ch+rowcap)+pad+60+crows*(480+60)+pad
    img = Image.new('RGB', (W, Hh), BG)
    d = ImageDraw.Draw(img)
    label(d, (pad, 22), 'GAMMA (Heartland Atomic), concept C: military surplus', 48, GREEN)
    label(d, (pad, 86), 'Beam\'s frame refitted from army surplus: a searchlight head, a louvred '
                        'reactor hatch, jerrycans and a toolbox racked on the back, a searchlight '
                        'converted to a ray projector, a field gun\'s shield on the left arm. '
                        'Drawn by Mei, 320 x 240 views shown 3x.', 26, SUB, bold=False)
    y = head
    for i, (name, text) in enumerate(cols):
        x = pad+i*(cw+pad)
        label(d, (x, y+8), text, 30, INK if i < 5 else SUB)
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
    label(d, (pad, y), 'Close-ups, 2x: the head and the reactor in the rest pose, the projector '
                       'and the stowed shield in the idle, the shield swung out in Lead '
                       'Shielding.', 24, SUB, bold=False)
    y += 60
    for n, (name, cam, text) in enumerate(close):
        x = pad+(n % per)*(640+pad)
        yy = y+(n//per)*(480+60)
        label(d, (x, yy-6), text, 24, INK, bold=False)
        img.paste(big(view(work, name, cam), 2), (x, yy+30))
    img.save(out)


def fight_sheet(work, out):
    pad, head = 24, 130
    # (Gamma's recipe, the other mech, closer, Gamma facing left, caption)
    frames = [('gamma_c_idle', 'beam', False, False, 'idle against Beam'),
              ('gamma_c_ray', 'beam', False, False, 'Atomic Ray against Beam'),
              ('gamma_c_ray', 'hero', False, False, 'Atomic Ray against the Hero'),
              ('gamma_c_shield', 'hero', False, False, 'Lead Shielding against the Hero'),
              ('gamma_c_flare', 'beam', False, False, 'Geiger Flare against Beam'),
              ('gamma_c_ground_zero', 'hero', False, False, 'Ground Zero against the Hero'),
              ('gamma_c_idle', 'hero', True, False, 'idle against the Hero, closer (22 m)'),
              ('gamma_c_ray', 'beam', True, False, 'Atomic Ray against Beam, closer (22 m)'),
              ('gamma_c_ray', 'hero', True, False,
               'Atomic Ray against the Hero, closer (22 m)'),
              ('gamma_c_idle', 'beam', False, True, 'facing left: idle against Beam'),
              ('gamma_c_shield', 'hero', True, True,
               'facing left: Lead Shielding, closer (22 m)'),
              ('gamma_c_ray', 'hero', True, True, 'facing left: Atomic Ray, closer (22 m)')]
    rows = (len(frames)+2)//3
    W = pad+3*(640+pad)
    Hh = head+(50+240+30)+rows*(50+480+30)+pad
    img = Image.new('RGB', (W, Hh), BG)
    d = ImageDraw.Draw(img)
    label(d, (pad, 22), 'GAMMA concept C at true game scale', 44, GREEN)
    label(d, (pad, 78), 'Fight frames, 320 x 240, from the fight camera (31.2 m; closer: 22 m). '
                        'The ray is a stand-in shape, not the effect. Top row 1x, the rest 2x.',
          24, SUB, bold=False)
    y = head
    for i, (a, b, close, flip, text) in enumerate(frames[:3]):
        x = pad+i*(640+pad)
        label(d, (x, y+10), text+', 1x', 24, SUB, bold=False)
        img.paste(fight(work, a, b, close, flip, 'Ray' in text), (x, y+50))
    y += 50+240+30
    for n, (a, b, close, flip, text) in enumerate(frames):
        x = pad+(n % 3)*(640+pad)
        yy = y+(n//3)*(50+480+30)
        label(d, (x, yy+10), text+', 2x', 24, INK if 'Ray' in text else SUB, bold='Ray' in text)
        img.paste(big(fight(work, a, b, close, flip, 'Ray' in text), 2), (x, yy+50))
    img.save(out)


BLURB = {
    '1': 'Faded forest green over a darker green, primer-grey replacement panels (the right '
         'pauldron, the left breast, the left shin) and primer showing through the chipped '
         'edges; a dark green lead shield; gunmetal frame; off-white stencils.',
    '2': 'Stripped and primed at the depot: primer grey as the body colour, the few panels '
         'left in the old green (the right pauldron, the left breast, the left shin), green '
         'cans and toolbox, a dark green shield; gunmetal showing through the chips.',
}


def paint_sheet(work, out):
    k = 2
    cw, ch = 200*k, 240*k
    pad, head, cap = 24, 150, 130
    cams = ('side_near', 'three_quarter', 'back_quarter')
    W = pad+len(cams)*(cw+8)+8+640+pad
    Hh = head+len(M.SCHEMES)*(ch+cap+pad)+pad
    img = Image.new('RGB', (W, Hh), BG)
    d = ImageDraw.Draw(img)
    label(d, (pad, 22), 'GAMMA concept C: paint schemes', 48, GREEN)
    label(d, (pad, 86), 'The idle in each scheme: side-on, front and back three-quarter (2x); '
                        'beside Tank (Heartland\'s base mech) at game scale (2x).', 26, SUB,
          bold=False)
    y = head
    for key, (title, _) in M.SCHEMES.items():
        name = f'gamma_c_paint_{key}'
        chosen = key == M.CHOSEN
        label(d, (pad, y+8), f'{key}. {title}' + ('  (chosen for the poses)' if chosen else ''),
              34, GREEN if chosen else INK)
        label(d, (pad, y+54), '\n'.join(textwrap.wrap(BLURB[key], 150)), 22, SUB, bold=False)
        yy = y+cap
        x = pad
        for cam in cams:
            img.paste(crop(view(work, name, cam), BOX, k), (x, yy))
            x += cw+8
        img.paste(big(fight(work, name, 'tank'), 2), (x+8, yy))
        y = yy+ch+pad
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
    work = build/'gamma_c'
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    fights = ['fight_left', 'close_left', 'fight_right', 'close_right']
    # (name, recipe, cameras or None for all, the key colour or None)
    jobs = [(f'gamma_c_{p}', HERE/f'gamma_c_{p}.asset.json', None, None) for p in POSES]
    jobs += [(p, HERE/f'{p}.asset.json', GENERAL, None) for p in PAINTS]
    jobs += [(n, p, GENERAL, None) for n, p in REFS.items() if n != 'hero']
    jobs += [(f'{n}_key', p, fights, '#ff00ff') for n, p in REFS.items()]
    jobs += [(f'ray{int(s)}', ray_recipe(work, s), fights, '#000000') for s in SEP.values()]
    if not a.sheets_only:
        todo = [j for j in jobs if not a.only or j[0] in a.only]
        with ThreadPoolExecutor(max(1, a.jobs)) as ex:
            for name, n in ex.map(lambda j: render(j[0], j[1], work, build, j[2], j[3]), todo):
                print(f'{name}: {n} triangles')
    tris = {j[0]: triangles(work, j[0]) for j in jobs}
    poses_sheet(work, tris, out/'gamma_c_sheet.png')
    fight_sheet(work, out/'gamma_c_fight.png')
    paint_sheet(work, out/'gamma_c_paint.png')
    print(f'sheets in {out}')


if __name__ == '__main__':
    main()
