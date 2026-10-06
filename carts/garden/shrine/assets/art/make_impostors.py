"""The shrine's landmarks' coarsest level as an impostor: the temple, the pagoda and the two-storey
gate drawn far off as cut-out pictures of themselves on a box round them, instead of flat bands of
palette colour (shrinetown/DESIGN.md 12.7).

    python3 carts/garden/shrine/assets/art/make_impostors.py

For each recipe (hand-authored; this script owns only its coarsest lod level and its impostor_*
materials) it renders level 0 from the front and the side (tools/assetkit/impostor.py) into
art/NAME_front.png and art/NAME_side.png, puts the box in place of the coarsest level, and writes
the recipe back. Deterministic: rerunning writes the same files. Pillow and NumPy.
"""
import json
import re
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ASSETS.parents[3] / 'tools'))
from assetkit.impostor import with_impostor  # noqa: E402

# name: pixels a unit (the pictures are about the size the asset is drawn from its level's distance)
LANDMARKS = {'arch_temple': 2.0, 'arch_pagoda': 3.0, 'arch_gate': 2.5}


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
        path.write_text(dump(out) + '\n')
        print('wrote', path.name, 'and', f'art/{name}_front.png, art/{name}_side.png')


if __name__ == '__main__':
    main()
