"""The shrine's landmarks' coarsest level as an impostor: the temple, the pagoda and the two-storey
gate drawn far off as cut-out pictures of themselves on a box round them, instead of flat bands of
palette colour (shrinetown/DESIGN.md 12.7).

    python3 carts/garden/shrine/assets/art/make_impostors.py

For each recipe (hand-authored; this script owns only its coarsest lod level and its impostor_*
materials) it renders level 0 from the front and the side (tools/assetkit/impostor.py) into
art/NAME_front.png and art/NAME_side.png, puts the box in place of the coarsest level, and writes
the recipe back. Deterministic: rerunning writes the same files. Pillow and NumPy.

The pagoda (STAR) has a star of four cards through its axis instead of the box: the front and side
pictures on the two cards along the axes, and level 0 drawn turned by 45 degrees
(art/NAME_diag.png) on both diagonal cards. A box round a square tower
showed two towers side by side from a diagonal (ALPHA_REVIEW, far views); the star shows the
diagonal picture head-on there and the two others foreshortened to the same width behind and
before it. Four double-sided quads, as the box.
"""
import copy
import math
import json
import re
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ASSETS.parents[3] / 'tools'))
from assetkit.impostor import with_impostor, render, save_png  # noqa: E402
from assetkit.compiler import shading  # noqa: E402

# name: pixels a unit (the pictures are about the size the asset is drawn from its level's distance)
LANDMARKS = {'arch_temple': 2.0, 'arch_pagoda': 3.0, 'arch_gate': 2.5}
STAR = ('arch_pagoda',)


def turned(point, degrees):
    """A point turned about +y by `degrees` as an Asset Kit `rotate` [0, a, 0] turns it (+X to -Z at
    90)."""
    a = math.radians(degrees)
    x, y, z = point
    return [round(x * math.cos(a) + z * math.sin(a), 4) + 0.0, round(y, 4) + 0.0,
            round(-x * math.sin(a) + z * math.cos(a), 4) + 0.0]


def star(recipe, name, ppu):
    """The impostor level as four cards through the origin (see the docstring)."""
    plain = {k: copy.deepcopy(v) for k, v in recipe.items() if k != 'lod'}
    plain['materials'] = {m: v for m, v in plain['materials'].items() if not m.startswith('impostor_')}
    wall = shading(recipe.get('lighting', {}))([1.0, 0.0, 0.0])
    level = recipe['lod']['levels'][-1]
    box = level['nodes'][0]['vertices']                 # the box with_impostor made: its x, y and z extents
    xs, ys, zs = ([v[k] for v in box] for k in range(3))
    top, bottom = max(ys), min(ys)
    v, f, uv, fm = [], [], [], []

    def card(corners, mat):
        k = len(v)
        v.extend(corners)
        uv.extend([[0, 0], [1, 0], [1, 1], [0, 1]])
        f.append([k, k + 1, k + 2, k + 3])
        fm.append(mat)
    card([[min(xs), top, 0.0], [max(xs), top, 0.0], [max(xs), bottom, 0.0], [min(xs), bottom, 0.0]], 'impostor_front')
    card([[0.0, top, min(zs)], [0.0, top, max(zs)], [0.0, bottom, max(zs)], [0.0, bottom, min(zs)]], 'impostor_side')
    rot = copy.deepcopy(plain)
    rot['nodes'] = [{'id': 'turned', 'op': 'group', 'children': plain['nodes'],
                     'transform': {'rotate': [0, 45, 0]}}]
    img, (x0, x1, _, _) = render(rot, str(ASSETS), 'front', ppu)
    out = save_png(img, ASSETS / 'art' / f'{name}_diag.png', gain=1.0 / wall)
    opaque = out[..., 3] > 0
    mean = out[opaque, :3].mean(axis=0) * wall
    mats = {'impostor_diag': {'color': '#' + ''.join(f'{int(round(c)):02x}' for c in mean),
                              'texture': {'image': f'art/{name}_diag.png', 'projection': 'fit'},
                              'double_sided': True}}
    for angle in (45, 135):
        # the card in the turned frame, turned back; one picture for both diagonals (a square tower
        # looks the same from each), so the stand-ins' set has room for it
        card([turned(p, -angle) for p in ([x0, top, 0.0], [x1, top, 0.0], [x1, bottom, 0.0], [x0, bottom, 0.0])],
             'impostor_diag')
    out = copy.deepcopy(recipe)
    out['materials'] = {**out['materials'], **mats}
    level = out['lod']['levels'][-1]
    level['nodes'] = [{'id': 'impostor', 'op': 'mesh', 'vertices': v, 'faces': f, 'face_materials': fm, 'uvs': uv}]
    return out


def dump(value, depth=0):
    """JSON as the recipes are written: one space of indent; a list of numbers or strings on one
    line; a list of such lists wrapped at about 100 columns."""
    pad = ' ' * depth

    def flat(v):
        return isinstance(v, list) and all(isinstance(x, (int, float, str)) and not isinstance(x, bool) for x in v)
    if isinstance(value, dict):
        if not value:
            return '{}'
        items = [f'{pad} {json.dumps(k)}: {dump(v, depth + 1)}' for k, v in value.items()]
        return '{\n' + ',\n'.join(items) + '\n' + pad + '}'
    if isinstance(value, list):
        if flat(value):
            sep = ', ' if any(isinstance(x, str) for x in value) else ','
            return '[' + sep.join(json.dumps(x) for x in value) + ']'
        if all(flat(x) for x in value):
            lines, line = [], ''
            for x in value:
                piece = dump(x)
                if line and len(line) + len(piece) > 96:
                    lines.append(line)
                    line = ''
                line += piece + ','
            lines.append(line[:-1])
            return '[\n' + '\n'.join(f'{pad} {l}' for l in lines) + '\n' + pad + ']'
        return '[\n' + ',\n'.join(f'{pad} {dump(x, depth + 1)}' for x in value) + '\n' + pad + ']'
    return json.dumps(value)


def main():
    for name, ppu in LANDMARKS.items():
        path = ASSETS / f'{name}.asset.json'
        recipe = json.loads(path.read_text())
        out = with_impostor(recipe, str(ASSETS), name, ppu=ppu)
        if name in STAR:
            out = star(out, name, ppu)
        path.write_text(dump(out) + '\n')
        print('wrote', path.name, 'and', f'art/{name}_front.png, art/{name}_side.png')


if __name__ == '__main__':
    main()
