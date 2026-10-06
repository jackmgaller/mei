#!/usr/bin/env python3
"""Writes coin_laundry.asset.json, coin_laundry_col.asset.json and coin_laundry.cameras.json
beside this file: shrine town's coin laundry (コインランドリー) on the front road (spec 3.5), cut
from the lab model (examples/assets/lab/coin_laundry, 746 triangles) to the town's density limit
for a hero piece of its size (400). Run once and commit the outputs:
python3 carts/garden/shrinetown/assets/coin_laundry/make_coin_laundry.py

Asset frame: origin at the centre of the shop's footprint (4.2 x 3.5 m walls) at the pavement,
the glass front toward -Z (the road), the drinks machine on +X beside it. The flat roof is 3.26
(coping top), the canopy a 0.8 m ledge at 2.43 over the door.

Kept from the lab: the blue lit sign, the glass front with the lit room behind it (washers with
their turning drums, gas dryers, a bench, a folding table with a basket of pink towels, the
change machine, the CRT on the weather), the drinks machine and can bin, the "24" sign on the
corner, the air conditioner, the two dryer flues on the roof, the planter. The bicycle parked in
front (110 triangles) is left to the town's `mamachari` placements, and the ashtray and the
plastic chairs went for triangles.

Textures: art/coin_laundry_sheet.png is the lab's sheet (drawn by
examples/assets/lab/coin_laundry/art/draw_sheet.py), copied by this script with its glass front
and its sign stored at half width (the faces stretch them back; the town's texture budget,
TEXTURES.md; needs Pillow); the back door and window come from the shop family's shared
../town_shop_2f_a/art/shopfront.png."""
import json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
LAB_ART = HERE.parents[4] / 'examples' / 'assets' / 'lab' / 'coin_laundry' / 'art'
HALVED = ('glass', 'sign')


def copy_sheet():
    """The lab's sheet, with the HALVED cells squeezed to half their width in place."""
    im = Image.open(LAB_ART / 'coin_laundry_sheet.png').convert('RGBA')
    sheet = json.loads((LAB_ART / 'coin_laundry_sheet.sheet.json').read_text())
    for name in HALVED:
        x, y, w, h = sheet['cells'][name]
        cell = im.crop((x, y, x + w, y + h)).resize((w // 2, h), Image.Resampling.BOX)
        im.paste((0, 0, 0, 0), (x, y, x + w, y + h))
        im.paste(cell, (x, y))
        sheet['cells'][name] = [x, y, w // 2, h]
    (HERE / 'art').mkdir(exist_ok=True)
    im.save(HERE / 'art' / 'coin_laundry_sheet.png')
    (HERE / 'art' / 'coin_laundry_sheet.sheet.json').write_text(json.dumps(sheet, indent=1) + '\n')


copy_sheet()


def r(v):
    return round(v, 4)


def quad(a, b, c, d, normal):
    """Corners a b c d in order around the face; reversed if they do not wind outward."""
    ab = [b[i] - a[i] for i in range(3)]
    ac = [c[i] - a[i] for i in range(3)]
    n = [ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0]]
    return (a, b, c, d) if sum(n[i] * normal[i] for i in range(3)) > 0 else (d, c, b, a)


def side_quads(x0, x1, y0, y1, z0, z1):
    return [
        ('left', quad((x0, y1, z1), (x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (-1, 0, 0))),
        ('right', quad((x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (x1, y0, z0), (1, 0, 0))),
        ('bottom', quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0))),
        ('top', quad((x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0), (0, 1, 0))),
        ('back', quad((x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0), (0, 0, -1))),
        ('front', quad((x1, y1, z1), (x0, y1, z1), (x0, y0, z1), (x1, y0, z1), (0, 0, 1))),
    ]


class Mesh:
    def __init__(self, ident, transform=None, inward=False):
        self.id, self.transform, self.inward = ident, transform, inward
        self.vertices, self.faces, self.mats = [], [], []

    def v(self, p):
        p = tuple(r(c) for c in p)
        if p not in self.vertices:
            self.vertices.append(p)
        return self.vertices.index(p)

    def face(self, corners, mat):
        idx = [self.v(c) for c in corners]
        self.faces.append(idx[::-1] if self.inward else idx)
        self.mats.append(mat)

    def box(self, x0, x1, y0, y1, z0, z1, mat, open=(), **side_mats):
        for name, corners in side_quads(x0, x1, y0, y1, z0, z1):
            if name not in open:
                self.face(corners, side_mats.get(name, mat))
        return self

    def node(self):
        n = {'id': self.id, 'op': 'mesh', 'vertices': [list(p) for p in self.vertices], 'faces': self.faces}
        if len(set(self.mats)) == 1:
            n['material'] = self.mats[0]
        else:
            n['face_materials'] = self.mats
        if self.transform:
            n['transform'] = self.transform
        return n


def mbox(ident, x0, x1, y0, y1, z0, z1, mat, open=(), transform=None, **side_mats):
    return Mesh(ident, transform).box(x0, x1, y0, y1, z0, z1, mat, open, **side_mats).node()


def box(ident, size, at, mat, open=None, faces=None, decals=None):
    n = {'id': ident, 'op': 'box', 'size': [r(s) for s in size], 'material': mat,
         'transform': {'translate': [r(c) for c in at]}}
    if open:
        n['open'] = list(open)
    if faces:
        n['faces'] = faces
    if decals:
        n['decals'] = decals
    return n


def plane(ident, x0, x1, y0, y1, z, mat, facing=-1):
    m = Mesh(ident)
    m.face(quad((x0, y1, z), (x1, y1, z), (x1, y0, z), (x0, y0, z), (0, 0, facing)), mat)
    return m.node()


def sheet(cell=None, frames=None, ticks=None, bits=4, name='art'):
    t = {'sheet': name, 'projection': 'fit', 'bits': bits}
    if cell:
        t['cell'] = cell
    else:
        t['frames'], t['ticks'] = frames, ticks
    return t


MATERIALS = {
    # textured
    'mosaic': {'color': '#ad8066', 'tag': 'wall',
               'texture': {'pattern': 'tile', 'colors': ['#b58a6c', '#8a6652', '#a6765c'],
                           'params': {'count': 4, 'grout': 1}, 'projection': 'box', 'scale': [0.5, 0.5]}},
    'floor': {'color': '#e2ddcf', 'tag': 'floor',
              'texture': {'pattern': 'tile', 'colors': ['#e6e1d3', '#a9a497', '#a3bccb'],
                          'params': {'count': 2, 'grout': 1}, 'projection': 'planar', 'axis': 'y',
                          'scale': [0.5, 0.5]}},
    'sign': {'color': '#1f5cb8', 'class': 'emissive', 'texture': sheet('sign')},
    'glass': {'color': '#c8ced4', 'double_sided': True, 'tag': 'window', 'texture': sheet('glass')},
    'washer_door': {'color': '#e9ebe8', 'texture': sheet(frames=['washer_a', 'washer_b', 'washer_c'], ticks=6)},
    'dryer_door': {'color': '#d5cfc2', 'texture': sheet(frames=['dryer_a', 'dryer_b'], ticks=9)},
    'basket': {'color': '#4a9ad8', 'double_sided': True,
               'texture': {'pattern': 'lattice', 'colors': ['#4a9ad8', '#000000'], 'clear': '#000000',
                           'params': {'count': 2, 'bar': 2}, 'projection': 'fit'}},
    'changer_face': {'color': '#dddbcd', 'texture': sheet('changer')},
    'tv_screen': {'color': '#3c78dc', 'texture': sheet(frames=['tv_a', 'tv_b'], ticks=90)},
    'clock': {'color': '#f6f6f0', 'texture': sheet('clock')},
    'poster': {'color': '#f8f4e2', 'texture': sheet('poster')},
    'vending_face': {'color': '#e8ecf0', 'class': 'emissive', 'texture': sheet('vending')},
    'side_sign': {'color': '#f4f4ee', 'texture': sheet('side')},
    'ac_face': {'color': '#cccab8', 'texture': sheet('grille')},
    'leaves': {'color': '#4f9a48', 'double_sided': True, 'texture': sheet('leaves')},
    'back_door': {'color': '#6f8c9c', 'tag': 'door', 'texture': sheet('back_door', name='shopfront')},
    'back_win': {'color': '#cfdadf', 'tag': 'window', 'texture': sheet('back_win', name='shopfront')},
    # emissive, untextured
    'tube_light': {'color': '#f2fbff', 'class': 'emissive'},
}
# palette-backed surface colours (8)
for name, col, tag in (('white', '#e9ebe6', None), ('stone', '#cfc9bb', None), ('steel', '#8d939b', None),
                       ('blue', '#2a5fae', None), ('red', '#cc3030', None), ('wood', '#c9a877', None),
                       ('dark', '#3a3a3f', None), ('pink', '#f2a7b8', None)):
    MATERIALS[name] = {'color': col, 'palette': True}
MATERIALS['coping'] = {'color': '#cfc9bb', 'palette': True, 'tag': 'roof'}
MATERIALS['wall_in'] = {'color': '#e9ebe6', 'palette': True, 'tag': 'wall'}

W, ZF, ZB, H = 2.1, -1.5, 2.0, 3.2
GLASS_Z = -1.40
FLOOR = 0.18
RX, RZ, CEIL = 1.95, 1.85, 2.95


def shell(detail=True):
    decals = None
    if detail:
        # round the back (the box's +Z side, seen from behind: right is -X)
        decals = [{'id': 'back_door', 'face': 'front', 'material': 'back_door', 'size': [0.85, 1.98], 'at': [0.875, -0.6]},
                  {'id': 'back_win', 'face': 'front', 'material': 'back_win', 'size': [0.9, 0.55], 'at': [-0.95, 0.42]}]
    return box('shell', [2 * W, H, ZB - ZF], [0, H / 2, (ZB + ZF) / 2], 'mosaic', open=['bottom', 'back'],
               decals=decals)


def front():
    nodes = [mbox('coping', -W - 0.05, W + 0.05, H - 0.1, H + 0.06, ZF - 0.03, ZB + 0.05, 'coping', open=['bottom'])]
    for s in (-1, 1):
        x0, x1 = (-W - 0.04, -1.85) if s < 0 else (1.85, W + 0.04)
        nodes.append(mbox('pillar_' + ('l' if s < 0 else 'r'), x0, x1, 0, 2.5, -1.56, -1.24, 'mosaic', open=['bottom']))
    nodes.append(mbox('signboard', -2.22, 2.22, 2.42, 3.34, -1.68, -1.3, 'white', back='sign'))
    nodes.append(mbox('canopy', -2.18, 2.18, 2.33, 2.43, -2.15, -1.35, 'white', back='blue', left='blue', right='blue'))
    nodes.append(plane('glass', -1.86, 1.86, 0.25, 2.46, GLASS_Z, 'glass'))
    room = Mesh('room', inward=True)
    room.box(-RX, RX, FLOOR, CEIL, GLASS_Z - 0.02, RZ, 'wall_in', open=['back'], top='white', bottom='floor')
    nodes.append(room.node())
    return nodes


def interior():
    nodes = [mbox('kickplate', -1.86, 1.86, 0, 0.27, -1.52, -1.32, 'steel', open=['bottom']),
             mbox('step', -1.0, 1.0, 0, 0.1, -1.85, -1.45, 'stone', open=['bottom'])]
    for k, z in enumerate((-0.45, 0.85)):
        nodes.append(mbox('light_%d' % k, -1.1, 1.1, CEIL - 0.07, CEIL + 0.02, z - 0.07, z + 0.07,
                          'tube_light', open=['top']))
    for k, (x, w, h) in enumerate([(-1.55, 0.6, 0.95), (-0.9, 0.6, 0.95), (-0.25, 0.6, 0.95), (0.53, 0.8, 1.15)]):
        nodes.append(mbox('washer_%d' % k, x - w / 2, x + w / 2, FLOOR - 0.02, FLOOR + h, RZ - 0.68, RZ + 0.02,
                          'white', open=['bottom', 'front'], back='washer_door'))
    for k, (z0, z1) in enumerate([(-0.15, 0.7), (0.75, 1.6)]):
        m = Mesh('dryers_%d' % k)
        x0, x1, ym = 1.2, RX + 0.02, FLOOR + 0.84
        for (y0, y1, last) in ((FLOOR - 0.02, ym, False), (ym, FLOOR + 1.72, True)):
            for name, corners in side_quads(x0, x1, y0, y1, z0, z1):
                if name in ('right', 'bottom') or (name == 'top' and not last):
                    continue
                m.face(corners, 'dryer_door' if name == 'left' else 'stone')
        nodes.append(m.node())
    # the bench along the left wall: one block
    nodes.append(mbox('bench', -RX - 0.02, -1.5, FLOOR - 0.02, 0.49, -0.9, 0.7, 'blue', open=['bottom', 'left']))
    nodes.append(mbox('table_top', -0.55, 0.45, 0.72, 0.76, -0.25, 0.35, 'wood'))
    for k, x in enumerate((-0.48, 0.38)):
        nodes.append(mbox('table_leg_%d' % k, x - 0.02, x + 0.02, FLOOR - 0.02, 0.73, -0.2, 0.3, 'steel',
                          open=['bottom', 'top']))
    nodes.append(mbox('basket', -0.35, 0.05, 0.75, 0.97, -0.15, 0.17, 'basket', open=['top', 'bottom']))
    nodes.append(mbox('towels', -0.3, 0.0, 0.74, 0.92, -0.11, 0.13, 'pink', open=['bottom']))
    nodes.append(mbox('changer', 1.62, RX + 0.02, FLOOR - 0.02, 1.45, -1.15, -0.72, 'white',
                      open=['bottom', 'right'], left='changer_face'))
    nodes.append(mbox('tv', -0.24, 0.24, 0.0, 0.36, -0.2, 0.2, 'dark', back='tv_screen',
                      transform={'rotate': [0, -40, 0], 'translate': [-1.6, 2.2, 1.5]}))
    nodes.append(plane('clock', 0.2, 0.5, 2.25, 2.55, RZ - 0.04, 'clock'))
    nodes.append(plane('poster', -1.15, -0.75, 1.45, 1.95, RZ - 0.04, 'poster'))
    return nodes


def exterior():
    nodes = [mbox('vending', 2.15, 3.05, 0, 1.83, -1.45, -0.75, 'red', open=['bottom'], back='vending_face'),
             mbox('vending_roof', 2.11, 3.09, 1.8, 1.88, -1.5, -0.71, 'red'),
             mbox('can_bin', 2.24, 2.56, 0, 0.68, -1.91, -1.59, 'blue', open=['bottom'], top='dark'),
             mbox('side_sign', -2.39, -2.27, 1.85, 2.95, -2.05, -1.5, 'blue', left='side_sign', right='side_sign')]
    for k, (y, x1) in enumerate(((2.0, -2.05), (2.8, -2.18))):
        nodes.append(mbox('bracket_%d' % k, -2.33, x1, y - 0.02, y + 0.02, -1.62, -1.545, 'steel',
                          open=['left', 'right']))
    nodes.append(mbox('ac_unit', -2.42, -2.07, 0, 0.6, 0.05, 0.85, 'white', open=['bottom', 'right'], left='ac_face'))
    nodes.append({'id': 'ac_pipe', 'op': 'cylinder', 'radius': 0.035, 'height': 2.1, 'segments': 4, 'caps': False,
                  'material': 'white', 'transform': {'translate': [-2.15, 1.6, 0.7]}})
    for k, z in enumerate((0.2, 1.15)):
        nodes.append({'id': 'flue_%d' % k, 'op': 'cylinder', 'radius': 0.07, 'height': 0.95, 'segments': 4,
                      'caps': False, 'material': 'steel', 'transform': {'translate': [1.55, H + 0.4, z]}})
        nodes.append({'id': 'flue_cap_%d' % k, 'op': 'cone', 'radius': 0.15, 'height': 0.12, 'segments': 4,
                      'material': 'steel', 'transform': {'translate': [1.55, H + 0.92, z]}})
    nodes.append(mbox('planter', 1.05, 1.4, 0, 0.36, -1.98, -1.63, 'wood', open=['bottom'], top='dark'))
    for k, yaw in enumerate((30, 120)):
        leaf = Mesh('shrub_%d' % k, transform={'rotate': [0, yaw, 0], 'translate': [1.225, 0, -1.805]})
        leaf.face(quad((-0.32, 1.0, 0), (0.32, 1.0, 0), (0.32, 0.3, 0), (-0.32, 0.3, 0), (0, 0, -1)), 'leaves')
        nodes.append(leaf.node())
    return nodes


L0 = [shell()] + front() + interior() + exterior()

L1 = [shell(False)] + front() + [
    mbox('washers', -1.85, 0.93, FLOOR - 0.02, FLOOR + 1.0, RZ - 0.68, RZ + 0.02, 'white', open=['bottom', 'front']),
    mbox('dryers', 1.2, RX + 0.02, FLOOR - 0.02, FLOOR + 1.72, -0.15, 1.6, 'stone', open=['bottom', 'right']),
    mbox('vending', 2.15, 3.05, 0, 1.88, -1.45, -0.75, 'red', open=['bottom'], back='vending_face'),
    mbox('side_sign', -2.39, -2.27, 1.85, 2.95, -2.05, -1.5, 'blue', left='side_sign', right='side_sign')]

L2 = [box('shell', [2 * W + 0.1, H + 0.06, ZB - ZF + 0.08], [0, (H + 0.06) / 2, (ZB + ZF) / 2], 'mosaic',
          open=['bottom'], faces={'top': 'coping', 'back': 'wall_in'}),
      mbox('signboard', -2.22, 2.22, 2.42, 3.34, -1.68, -1.56, 'white', open=['front'], back='sign'),
      mbox('vending', 2.18, 3.05, 0, 1.88, -1.45, -0.75, 'red', open=['bottom'], back='vending_face')]

recipe = {
    'format': 'mei-asset', 'version': 1, 'name': 'coin_laundry',
    'budget': {'triangles': 400},
    'sheets': {'art': {'image': 'art/coin_laundry_sheet.png'},
               'shopfront': {'image': '../town_shop_2f_a/art/shopfront.png'}},
    'materials': MATERIALS,
    'lighting': {'mode': 'vertical', 'ambient': 0.5},
    'verification': {'required': True, 'depth': True, 'perspective': True},
    'nodes': L0,
    'lod': {'levels': [{'distance': 24, 'nodes': L1}, {'distance': 60, 'nodes': L2}], 'band': 2},
}


# ------------------------------------------------------------------------------- collision
def solid_box(ident, x0, x1, y0, y1, z0, z1):
    n = mbox(ident, x0, x1, y0, y1, z0, z1, 'solid')
    return n


C = [solid_box('shop', -W - 0.05, W + 0.05, 0, H + 0.06, GLASS_Z, ZB + 0.05),
     solid_box('pillars', -W - 0.04, W + 0.04, 0.01, 2.42, -1.56, GLASS_Z + 0.01),
     solid_box('signboard', -2.22, 2.22, 2.43, 3.34, -1.68, GLASS_Z + 0.02),
     # the canopy, a ledge to grab or stand on
     solid_box('canopy', -2.2, 2.2, 2.22, 2.42, -2.15, -1.67),
     solid_box('vending', 2.17, 3.08, 0, 1.88, -1.5, -0.73)]
col = {'format': 'mei-asset', 'version': 1, 'name': 'coin_laundry_col',
       'materials': {'solid': {'color': '#ffffff', 'palette': True}},
       'lighting': {'mode': 'vertical', 'ambient': 0.5},
       'verification': {'required': True, 'depth': True, 'perspective': True},
       'nodes': C}

cams = [
    {'name': 'sidewalk', 'eye': [-1.5, 1.6, -5.5], 'target': [0, 1.4, 0]},
    {'name': 'road_across', 'eye': [5.0, 1.6, -13.0], 'target': [0, 1.6, 0]},
    {'name': 'at_glass', 'eye': [0.3, 1.5, -2.4], 'target': [0, 1.0, 1.5]},
    {'name': 'roof', 'eye': [-1.0, 4.9, -3.6], 'target': [0.5, 3.0, 1.0]},
    {'name': 'back_lane', 'eye': [-4.0, 1.6, 6.5], 'target': [0, 1.5, 1.0]},
]

if __name__ == '__main__':
    for name, data in (('coin_laundry.asset.json', recipe), ('coin_laundry_col.asset.json', col),
                       ('coin_laundry.cameras.json', cams)):
        (HERE / name).write_text(json.dumps(data, indent=1) + '\n')
    print('wrote coin_laundry, coin_laundry_col, coin_laundry.cameras.json')
