"""Writes tree_zelkova (keyaki) and tree_zelkova_col beside this script, and draws their sheet
art/zelkova.png (python3 make_tree_zelkova.py; the drawing needs Pillow, --no-art skips it).

A street and shrine-edge zelkova in late October, 14 m: a short grey trunk that splits at 2.8 m
into upright limbs fanning out like a vase, under a broad, flat-topped crown turning russet and
amber with some green left. Built like the shrine's trees (carts/garden/shrine/assets/art/
make_foliage.py, whose helpers it imports): leaf cluster cards facing out from an ellipsoid,
two big crossed cards through the middle, crossed far cards for the coarse levels.
"""
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHRINE_ART = HERE.parent.parent.parent / 'shrine' / 'assets' / 'art'
sys.path.insert(0, str(SHRINE_ART))
import make_foliage as mf  # noqa: E402

HEIGHT = 14.0
TRUNK_H = 2.8
CROWN_C = 9.3            # the crown's centre
CROWN_R = 5.6            # its radius across
CROWN_HH = 3.6           # its half height
SEED = 111

# zelkova in late October (STYLE.md: leaf litter, maple orange, ginkgo amber, dry grass, evergreen)
ZEL = {'shadow': '#5a3a20', 'russet': '#9a5a2e', 'rust': '#b8642a', 'orange': '#e8782a',
       'amber': '#d89a20', 'olive': '#7c8a3c', 'green': '#4f6a3a'}
BARK = {'bark': '#8a8278', 'dark': '#6a645c'}


# ---------------------------------------------------------------- art

def draw_art():
    import draw_foliage as df
    from PIL import Image, ImageDraw

    def leaf(d, x, y, r, col, rot):
        """A small pointed oval leaf."""
        a = math.radians(rot)
        ca, sa = math.cos(a), math.sin(a)
        pts = []
        for k in range(6):
            t = k / 6 * 2 * math.pi
            px, py = math.cos(t) * r, math.sin(t) * r * 0.5
            if k == 0:
                px *= 1.4
            pts.append((x + px * ca - py * sa, y + px * sa + py * ca))
        d.polygon(pts, fill=df.rgb(col))

    layers = [(ZEL['shadow'], 120, (2.5, 3.5), 1.0), (ZEL['russet'], 150, (2.5, 3.5), 0.6),
              (ZEL['green'], 45, (2.5, 3.2), 0.3), (ZEL['olive'], 60, (2.5, 3.2), 0.0),
              (ZEL['rust'], 150, (2.5, 3.5), -0.2), (ZEL['orange'], 60, (2.0, 3.0), -0.7),
              (ZEL['amber'], 40, (2.0, 2.8), -1.0)]

    def cluster():
        rng = random.Random(7)
        img = df.canvas(64, 64)
        mask = df.blob_mask(64, 64, rng, (32, 32), (30, 28), 34, 10)
        df.scatter_leaves(img, mask, rng, layers, leaf)
        df.thin(img, rng, 0.06)
        return img

    def far():
        """The whole tree: a vase of limbs under a broad flat-topped crown. 96 x 96."""
        rng = random.Random(8)
        w = h = 96
        img = df.canvas(w, h)
        d = ImageDraw.Draw(img)
        bark = df.rgb(BARK['dark'])
        d.polygon([(45, 95), (51, 95), (50.5, 77), (45.5, 77)], fill=bark)
        for x1, y1 in [(22, 40), (34, 34), (48, 30), (62, 34), (74, 40)]:
            d.line([(48, 78), (x1, y1)], fill=bark, width=2)
        mask = Image.new('L', (w, h), 0)
        md = ImageDraw.Draw(mask)
        for _ in range(70):
            x = rng.uniform(6, 90)
            dx = abs(x - 48) / 42
            top = 12 + dx ** 2 * 14
            bottom = 56 - dx * 14
            y = rng.uniform(top + 4, max(top + 5, bottom))
            s = rng.uniform(6, 10)
            md.ellipse([x - s, y - s * 0.8, x + s, y + s * 0.8], fill=255)
        leaves = df.canvas(w, h)
        df.scatter_leaves(leaves, mask, rng, [(c, n * 3, (2.0, 3.2), b) for c, n, _, b in layers], leaf)
        df.clip_to(leaves, mask)
        img.alpha_composite(leaves)
        df.thin(img, rng, 0.03)
        return img

    images = [('zelkova', cluster()), ('zelkova_far', far())]
    sheet = Image.new('RGBA', (162, 96), (0, 0, 0, 0))
    rects, x = {}, 0
    for name, im in images:
        colours = {c for _, c in im.getcolors(im.width * im.height) if c[3]}
        assert len(colours) <= 15, (name, len(colours))
        sheet.paste(im, (x, 0))
        rects[name] = [x, 0, im.width, im.height]
        x += im.width + 2
    (HERE / 'art').mkdir(exist_ok=True)
    sheet.save(HERE / 'art' / 'zelkova.png')
    lines = ',\n'.join(f'    "{n}": {json.dumps(r)}' for n, r in rects.items())
    (HERE / 'art' / 'zelkova.sheet.json').write_text(
        '{\n  "format": "mei-sheet",\n  "version": 1,\n  "cells": {\n' + lines + '\n  }\n}\n')


# ---------------------------------------------------------------- recipe

def tex(cell):
    return {'color': ZEL['rust'], 'texture': {'sheet': 'zelkova', 'cell': cell, 'projection': 'fit'},
            'double_sided': True}


def build():
    rng = random.Random(SEED)
    mats = {'bark': mf.pal(BARK['bark']), 'leaves': tex('zelkova'), 'far': tex('zelkova_far')}
    wood = mf.Part('trunk')
    mf.tube(wood, [([0, 0, 0], 0.36), ([0, TRUNK_H, 0], 0.3)], 5, 'bark')
    fork = [0, TRUNK_H * 0.95, 0]
    limbs = 5
    for k in range(limbs):
        a = 2 * math.pi * k / limbs + rng.uniform(-0.25, 0.25)
        reach = CROWN_R * rng.uniform(0.45, 0.55)
        end = [math.cos(a) * reach, CROWN_C - 0.6 + rng.uniform(-0.4, 0.6), math.sin(a) * reach]
        mf.tube(wood, [(fork, 0.2), (end, 0.07)], 3, 'bark', phase=rng.uniform(0, 1))
    crown = mf.Part('crown', uvs=True)
    for k in range(2):
        a = rng.uniform(0, math.pi) + k * math.pi / 2
        mf.card(crown, [0, HEIGHT * 0.2, 0], [math.cos(a), 0, math.sin(a)], HEIGHT * 0.95, HEIGHT * 0.8,
                'far', uv=(0, 0, 1, 0.8), lift=1.0)
    radii = [CROWN_R * 0.88, CROWN_HH * 0.8, CROWN_R * 0.88]
    mf.crown_cards(crown, rng, [0, CROWN_C, 0], radii, 23, CROWN_R * 0.72, 'leaves',
                   depth=0.92, tilt=0.3, ymin=-0.5)
    far = mf.Part('far', uvs=True)
    turn = rng.uniform(0, 1)
    mf.cross_cards(far, [0, 0, 0], HEIGHT, HEIGHT, 'far', yaw=turn, quad=True)
    mf.flat_card(far, [0, HEIGHT * 0.78, 0], CROWN_R * 1.6, 'leaves', yaw=rng.uniform(0, 6), quad=True)
    r, tris = mf.recipe('tree_zelkova', 90, mats, [wood, crown],
                        [(40, [far]), (mf.FAR2, [mf.cross_only(HEIGHT, HEIGHT, turn)])])
    r['sheets'] = {'zelkova': {'image': 'art/zelkova.png'}}
    c, _ = mf.collision_prism('tree_zelkova_col', [([0, 0, 0], 0.4), ([0, TRUNK_H, 0], 0.34)], 4, math.pi / 4)
    return r, tris, c


def main():
    if '--no-art' not in sys.argv:
        draw_art()
    r, tris, c = build()
    (HERE / 'tree_zelkova.asset.json').write_text(json.dumps(r, indent=1) + '\n')
    (HERE / 'tree_zelkova_col.asset.json').write_text(json.dumps(c, indent=1) + '\n')
    print(f'tree_zelkova: triangles per level {tris}')


if __name__ == '__main__':
    main()
