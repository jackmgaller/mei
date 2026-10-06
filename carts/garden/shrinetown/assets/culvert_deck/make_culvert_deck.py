#!/usr/bin/env python3
"""Writes culvert_deck.asset.json and culvert_deck_col.asset.json beside this script: the front
road's slab over the culvert (shrine town spec 41: the pond's outflow under the road, x 234-238),
in place of the grey box's flat dark slab (alpha review r16 #6).

    python3 carts/garden/shrinetown/assets/culvert_deck/make_culvert_deck.py      (standard library)

Origin at the slab's centre on the road, (236, 0, 111) as place/east.py puts it; the road runs
along x, the culvert along z under it. The slab is 4 m across the culvert (x) and 14 m along it
(z 104-118, the road's rows), 0.15 m thick, so the culvert keeps its 1.85 m under it. Its top
carries the road's own rows in the ground's textures (art/ground, GROUND.md "Markings"): the
tactile strips, the sidewalks, the asphalt with its centre line; the kerbs (0.15) run across it
at z 108 and 114 as the road's do; a low concrete parapet (0.6) stands on each of its two edges
over the culvert's mouths, so the slab reads as a structure and the sidewalk's edge is closed.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
G = '../../art/ground/'
HX, HZ, T = 2.0, 7.0, 0.15            # half width (x), half length (z), thickness
PAR_H, PAR_T = 0.6, 0.2               # the parapets
KERB = 0.15
# the road's rows from its south edge (z 104 = -7): (z0, z1, material)
ROWS = [(-7, -5, 'tactile'), (-5, -3, 'sidewalk'), (-3, -1, 'asphalt'), (-1, 1, 'line'), (1, 3, 'asphalt'),
        (3, 5, 'sidewalk'), (5, 7, 'tactile')]


def tex(image, **kw):
    t = {'image': G + image, 'projection': 'box', 'scale': [2.0, 2.0]}
    t.update(kw)
    return t


MATS = {
    'asphalt': {'color': '#4a4a51', 'tag': 'floor', 'texture': tex('asphalt.png')},
    'line': {'color': '#53535a', 'tag': 'floor', 'texture': tex('asphalt_line.png', rotate=90)},
    'sidewalk': {'color': '#b2aea2', 'tag': 'floor', 'texture': tex('sidewalk.png')},
    'tactile': {'color': '#b8ab8a', 'tag': 'floor', 'texture': tex('sidewalk_tactile.png', rotate=90)},
    'concrete': {'color': '#a8a69e', 'tag': 'wall', 'texture': tex('concrete.png', scale=[2.0, 1.0])},
    'under': {'color': '#6e6c66', 'palette': True},
    'kerb': {'color': '#bbb7ab', 'palette': True},
}


def r(v):
    return round(v, 4)


class Mesh:
    def __init__(self, nid):
        self.nid, self.v, self.f, self.m = nid, [], [], []

    def quad(self, pts, mat):
        """pts counter-clockwise seen from outside."""
        self.f.append(list(range(len(self.v), len(self.v) + 4)))
        self.v += [[r(c) for c in p] for p in pts]
        self.m.append(mat)

    def box(self, x0, x1, y0, y1, z0, z1, mat, top=None, skip=()):
        """A box's faces, out-facing, without its bottom; `skip` names faces left out."""
        faces = {
            'top': [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)],
            'front': [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)],
            'back': [(x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (x0, y0, z1)],
            'left': [(x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (x0, y0, z0)],
            'right': [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
        }
        for k, pts in faces.items():
            if k not in skip:
                self.quad(pts, top if (k == 'top' and top) else mat)

    def node(self):
        return {'id': self.nid, 'op': 'mesh', 'vertices': self.v, 'faces': self.f, 'face_materials': self.m}


def deck(detail):
    m = Mesh('deck')
    for z0, z1, mat in ROWS:
        m.quad([(-HX, 0.0, z0), (-HX, 0.0, z1), (HX, 0.0, z1), (HX, 0.0, z0)], mat if detail else
               ('asphalt' if mat in ('asphalt', 'line') else 'sidewalk'))
    # the slab's edges over the mouths and its underside (seen from the culvert)
    m.quad([(-HX, -T, -HZ), (-HX, 0.0, -HZ), (HX, 0.0, -HZ), (HX, -T, -HZ)], 'concrete')
    m.quad([(HX, -T, HZ), (HX, 0.0, HZ), (-HX, 0.0, HZ), (-HX, -T, HZ)], 'concrete')
    m.quad([(-HX, -T, -HZ), (HX, -T, -HZ), (HX, -T, HZ), (-HX, -T, HZ)], 'under')
    return m.node()


def parapets(level):
    m = Mesh('parapets')
    x0, x1 = -HX - 0.2, HX + 0.2
    for z0, z1 in ((-HZ, -HZ + PAR_T), (HZ - PAR_T, HZ)):
        m.box(x0, x1, 0.0, PAR_H, z0, z1, 'concrete', skip=() if level == 0 else ('left', 'right'))
    return m.node()


def kerbs():
    m = Mesh('kerbs')
    for z in (-3.0, 3.0):
        m.box(-HX, HX, 0.0, KERB, z - 0.1, z + 0.1, 'kerb', skip=('left', 'right'))
    return m.node()


def collision():
    m = Mesh('deck')
    m.box(-HX, HX, -T, 0.0, -HZ, HZ, 'solid', skip=('left', 'right'))
    m.quad([(-HX, -T, -HZ), (HX, -T, -HZ), (HX, -T, HZ), (-HX, -T, HZ)], 'solid')
    p = Mesh('parapets')
    for z0, z1 in ((-HZ, -HZ + PAR_T), (HZ - PAR_T, HZ)):
        p.box(-HX - 0.2, HX + 0.2, 0.0, PAR_H, z0, z1, 'solid')
    return [m.node(), p.node()]


LIGHT = {'mode': 'vertical', 'ambient': 0.5}
POLICY = {'required': True, 'depth': True, 'perspective': True}


def main():
    recipe = {'format': 'mei-asset', 'version': 1, 'name': 'culvert_deck', 'budget': {'triangles': 80},
              'materials': MATS, 'lighting': LIGHT, 'verification': POLICY,
              'nodes': [deck(True), parapets(0), kerbs()],
              'lod': {'levels': [{'distance': 30, 'nodes': [deck(False), parapets(1)]}], 'cull': 120}}
    (HERE / 'culvert_deck.asset.json').write_text(json.dumps(recipe, indent=1) + '\n')
    col = {'format': 'mei-asset', 'version': 1, 'name': 'culvert_deck_col',
           'materials': {'solid': {'color': '#ffffff', 'palette': True}}, 'lighting': LIGHT,
           'verification': POLICY, 'nodes': collision()}
    (HERE / 'culvert_deck_col.asset.json').write_text(json.dumps(col, indent=1) + '\n')
    print('wrote culvert_deck, culvert_deck_col')


if __name__ == '__main__':
    main()
