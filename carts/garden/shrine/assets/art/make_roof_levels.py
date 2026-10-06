"""The landmarks' level 1 with their roofs closed from below: the temple, the pagoda and the
two-storey gate (shrinetown ALPHA_REVIEW, "Roofs"; DESIGN.md 12.9).

    python3 carts/garden/shrine/assets/art/make_roof_levels.py

Level 1 of each (hand-authored, the first of the recipe's lod levels) draws each roof as the
sloped ring from the eave up to the next storey, one-sided, and its walls stop short of the roof.
Seen from below (the courtyard and the precinct floor look up at every roof of the gate and the
temple), the ring faces away and the gap between the wall tops and the roof is open, so the roofs
vanish and the storeys float. This script owns two things in that level and nothing else:

- a node `soffit`: under each roof a quad facing down at the eave's height over the eave's
  outline, in the recipe's `lacquer` (level 0's red, shaded as a face turned down; a level may
  draw only the palette colours level 0 uses), like level 0's red rafters under the eaves:
  2 triangles a roof;
- the walls of each storey (faces in its WALLS materials) raised from their old top to the eave,
  so the soffit meets them.

Rerunning writes the same files (the raise looks for the old top or the eave). The roofs are
listed below, from the recipes' level 1: (old wall top, eave height, half width x, half depth z).
"""
import json
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_impostors import dump  # noqa: E402

SOFFIT = 'lacquer'
WALLS = ('bay', 'small_bay', 'lacquer')
ROOFS = {
    'arch_temple': [(7.7, 8.0, 21.0, 11.0), (12.15, 12.4, 22.5, 10.0), (18.2, 18.4, 19.1, 6.6)],
    'arch_gate': [(6.65, 6.9, 10.0, 4.0), (10.4, 10.6, 9.3, 3.2)],
    'arch_pagoda': [(5.0, 5.0, 5.4, 5.4), (8.6, 8.6, 4.7, 4.7), (12.2, 12.2, 4.0, 4.0),
                    (15.8, 15.8, 3.3, 3.3), (19.4, 19.4, 2.6, 2.6)],
}


def soffit(roofs):
    """One down-facing quad a roof (outward right-handed winding: the normal is -y)."""
    vertices, faces = [], []
    for _, y, hx, hz in roofs:
        k = len(vertices)
        vertices += [[-hx, y, -hz], [hx, y, -hz], [hx, y, hz], [-hx, y, hz]]
        faces.append([k, k + 1, k + 2, k + 3])
    return {'id': 'soffit', 'op': 'mesh', 'vertices': vertices, 'faces': faces,
            'face_materials': [SOFFIT] * len(faces)}


def raise_walls(node, roofs):
    """The walls' top vertices from each storey's old top to its eave (vertices are per face)."""
    tops = {old: eave for old, eave, _, _ in roofs if eave != old}
    moved = 0
    for face, material in zip(node['faces'], node['face_materials']):
        if material not in WALLS:
            continue
        for i in face:
            v = node['vertices'][i]
            for old, eave in tops.items():
                if abs(v[1] - old) < 1e-6:
                    v[1] = eave
                    moved += 1
    return moved


def main():
    for name, roofs in ROOFS.items():
        path = ASSETS / f'{name}.asset.json'
        recipe = json.loads(path.read_text())
        level = recipe['lod']['levels'][0]
        nodes = [n for n in level['nodes'] if n['id'] != 'soffit']
        moved = sum(raise_walls(n, roofs) for n in nodes if n['op'] == 'mesh')
        level['nodes'] = nodes + [soffit(roofs)]
        path.write_text(dump(recipe) + '\n')
        print(f'{path.name}: level 1 at {level["distance"]}: {len(roofs)} soffits, {moved} wall corners raised')


if __name__ == '__main__':
    main()
