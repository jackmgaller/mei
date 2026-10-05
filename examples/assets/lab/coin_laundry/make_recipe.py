"""Writes coin_laundry.asset.json, a neighbourhood coin laundry (コインランドリー), 1990s Japan.

The recipe is written by this script so that its many hand-made boxes (mesh nodes with a
material per side) stay consistent; edit this file and rerun it, not the JSON.
Run: python3 examples/assets/lab/coin_laundry/make_recipe.py
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

SIDES = ('left', 'right', 'bottom', 'top', 'back', 'front')   # -X +X -Y +Y -Z +Z


def r(v):
    return round(v, 4)


def quad(a, b, c, d, normal):
    """Corners a b c d in order around the face; reversed if they do not wind outward."""
    ab = [b[i] - a[i] for i in range(3)]
    ac = [c[i] - a[i] for i in range(3)]
    n = [ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0]]
    return (a, b, c, d) if sum(n[i] * normal[i] for i in range(3)) > 0 else (d, c, b, a)


def side_quads(x0, x1, y0, y1, z0, z1):
    """Each side of a box as (name, corners, outward normal)."""
    return [
        ('left', quad((x0, y1, z1), (x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (-1, 0, 0)), (-1, 0, 0)),
        ('right', quad((x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (x1, y0, z0), (1, 0, 0)), (1, 0, 0)),
        ('bottom', quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0)), (0, -1, 0)),
        ('top', quad((x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0), (0, 1, 0)), (0, 1, 0)),
        ('back', quad((x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0), (0, 0, -1)), (0, 0, -1)),
        ('front', quad((x1, y1, z1), (x0, y1, z1), (x0, y0, z1), (x1, y0, z1), (0, 0, 1)), (0, 0, 1)),
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
        """side_mats: a material per side name, the rest `mat`; `open` sides are left out."""
        for name, corners, _ in side_quads(x0, x1, y0, y1, z0, z1):
            if name not in open:
                self.face(corners, side_mats.get(name, mat))
        return self

    def node(self):
        n = {'id': self.id, 'op': 'mesh', 'vertices': [list(p) for p in self.vertices],
             'faces': self.faces}
        if len(set(self.mats)) == 1:
            n['material'] = self.mats[0]
        else:
            n['face_materials'] = self.mats
        if self.transform:
            n['transform'] = self.transform
        return n


def mbox(ident, x0, x1, y0, y1, z0, z1, mat, open=(), transform=None, **side_mats):
    return Mesh(ident, transform).box(x0, x1, y0, y1, z0, z1, mat, open, **side_mats).node()


def box(ident, size, at, mat, open=None, rotate=None):
    n = {'id': ident, 'op': 'box', 'size': [r(s) for s in size], 'material': mat,
         'transform': {'translate': [r(c) for c in at]}}
    if rotate:
        n['transform']['rotate'] = rotate
    if open:
        n['open'] = list(open)
    return n


def tube(ident, a, b, thick, mat, z):
    """A thin box from a to b (x, y) in the plane z: a bicycle's tube."""
    import math
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    return box(ident, [length, thick, thick], [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z], mat,
               rotate=[0, 0, r(math.degrees(math.atan2(dy, dx)))])


def decal(ident, x0, x1, y0, y1, z, mat, facing=-1):
    """A vertical quad in the plane z, seen from -Z (facing -1) or +Z (facing +1)."""
    m = Mesh(ident)
    m.face(quad((x0, y1, z), (x1, y1, z), (x1, y0, z), (x0, y0, z), (0, 0, facing)), mat)
    return m.node()


def sheet(cell=None, frames=None, ticks=None, bits=4, **kw):
    t = {'sheet': 'art', 'projection': 'fit', 'bits': bits}
    if cell:
        t['cell'] = cell
    else:
        t['frames'], t['ticks'] = frames, ticks
    t.update(kw)
    return t


MATERIALS = {
    # the building
    'mosaic': {'color': '#ad8066', 'tag': 'wall',
               'texture': {'pattern': 'tile', 'colors': ['#b58a6c', '#8a6652', '#a6765c'],
                           'params': {'count': 4, 'grout': 1}, 'projection': 'box', 'scale': [0.5, 0.5]}},
    'coping': {'color': '#c9c4b6', 'tag': 'roof'},
    'kick': {'color': '#7c8590'},
    'step': {'color': '#a9a59b', 'tag': 'floor'},
    'canopy': {'color': '#dcddd6', 'tag': 'roof'},
    'canopy_edge': {'color': '#2a5fae'},
    'board': {'color': '#eef0ec'},
    'sign': {'color': '#1f5cb8', 'class': 'emissive', 'texture': sheet('sign')},
    'glass': {'color': '#c8ced4', 'double_sided': True, 'tag': 'window', 'texture': sheet('glass')},
    # inside
    'floor': {'color': '#e2ddcf', 'tag': 'floor',
              'texture': {'pattern': 'tile', 'colors': ['#e6e1d3', '#a9a497', '#a3bccb'],
                          'params': {'count': 2, 'grout': 1}, 'projection': 'planar', 'axis': 'y',
                          'scale': [0.6, 0.6]}},
    'wall_in': {'color': '#e9eee2', 'tag': 'wall'},
    'ceiling': {'color': '#f4f4ee'},
    'tube_light': {'color': '#f2fbff', 'class': 'emissive'},
    'washer': {'color': '#e9ebe8'},
    'washer_door': {'color': '#e9ebe8',
                    'texture': sheet(frames=['washer_a', 'washer_b', 'washer_c'], ticks=6)},
    'dryer': {'color': '#d5cfc2'},
    'dryer_door': {'color': '#d5cfc2', 'texture': sheet(frames=['dryer_a', 'dryer_b'], ticks=9)},
    'bench': {'color': '#3d7fc4'},
    'towels': {'color': '#f2a7b8'},
    'metal': {'color': '#8d939b'},
    'table': {'color': '#c9a877'},
    'basket': {'color': '#4a9ad8', 'double_sided': True,
               'texture': {'pattern': 'lattice', 'colors': ['#4a9ad8', '#000000'], 'clear': '#000000',
                           'params': {'count': 2, 'bar': 2}, 'projection': 'fit'}},
    'chair': {'color': '#e59a32'},
    'changer': {'color': '#dddbcd'},
    'changer_face': {'color': '#dddbcd', 'texture': sheet('changer')},
    'tv': {'color': '#3a3a3f'},
    'tv_screen': {'color': '#3c78dc', 'class': 'emissive',
                  'texture': sheet(frames=['tv_a', 'tv_b'], ticks=90)},
    'clock': {'color': '#f6f6f0', 'texture': sheet('clock')},
    'poster': {'color': '#f8f4e2', 'texture': sheet('poster')},
    # outside
    'vending': {'color': '#cc3030'},
    'vending_face': {'color': '#e8ecf0', 'class': 'emissive', 'texture': sheet('vending')},
    'bin': {'color': '#3a7cc8'},
    'bin_hole': {'color': '#1c2430'},
    'side_sign': {'color': '#f4f4ee', 'class': 'emissive', 'texture': sheet('side')},
    'ac': {'color': '#dddbd0'},
    'ac_face': {'color': '#cccab8', 'texture': sheet('grille')},
    'pipe': {'color': '#e6e4d8'},
    'flue': {'color': '#a9adb0'},
    'back_door': {'color': '#6f8c9c', 'tag': 'door'},
    'frosted': {'color': '#cfdadf', 'tag': 'window'},
    'ashtray': {'color': '#9aa0a6'},
    'planter': {'color': '#8b5a3c'},
    'soil': {'color': '#4a3424'},
    'leaves': {'color': '#4f9a48', 'double_sided': True, 'texture': sheet('leaves')},
    'bike': {'color': '#5db39b'},
    'tyre': {'color': '#202226', 'double_sided': True, 'texture': sheet('wheel')},
    'saddle': {'color': '#2a2a2c'},
    'bike_basket': {'color': '#c3c7cb', 'double_sided': True,
                    'texture': {'pattern': 'lattice', 'colors': ['#c3c7cb', '#000000'], 'clear': '#000000',
                                'params': {'count': 2, 'bar': 2}, 'projection': 'fit'}},
}

# The plan: the building is 4.2 m wide (x -2.1..2.1) and 3.5 m deep (z -1.5..2.0), its front on
# -Z; the vending machine stands beside it on +X.
W, ZF, ZB, H = 2.1, -1.5, 2.0, 3.2
GLASS_Z = -1.40
FLOOR = 0.18
RX, RZ, CEIL = 1.95, 1.85, 2.95         # the room inside


def building():
    nodes = []
    nodes.append(box('shell', [2 * W, H, ZB - ZF], [0, H / 2, (ZB + ZF) / 2], 'mosaic',
                     open=['bottom', 'back']))
    nodes.append(mbox('coping', -W - 0.05, W + 0.05, H - 0.1, H + 0.06, ZF - 0.03, ZB + 0.05,
                      'coping', open=['bottom']))
    for s in (-1, 1):
        x0, x1 = (-W - 0.02, -1.85) if s < 0 else (1.85, W + 0.02)
        nodes.append(mbox('pillar_' + ('l' if s < 0 else 'r'), x0, x1, 0, 2.5, -1.56, -1.27,
                          'mosaic', open=['bottom']))
    nodes.append(mbox('kickplate', -1.86, 1.86, 0, 0.27, -1.52, -1.32, 'kick', open=['bottom']))
    nodes.append(mbox('step', -1.0, 1.0, 0, 0.1, -1.85, -1.45, 'step', open=['bottom']))
    nodes.append(mbox('signboard', -2.22, 2.22, 2.42, 3.34, -1.68, -1.3, 'board', back='sign'))
    nodes.append(mbox('canopy', -2.2, 2.2, 2.33, 2.43, -2.15, -1.32, 'canopy', back='canopy_edge',
                      left='canopy_edge', right='canopy_edge'))
    g = Mesh('glass')
    g.face(quad((-1.86, 2.46, GLASS_Z), (1.86, 2.46, GLASS_Z), (1.86, 0.25, GLASS_Z),
                (-1.86, 0.25, GLASS_Z), (0, 0, -1)), 'glass')
    nodes.append(g.node())
    # the room, its faces looking inward
    room = Mesh('room', inward=True)
    room.box(-RX, RX, FLOOR, CEIL, GLASS_Z - 0.02, RZ, 'wall_in', open=['back'], top='ceiling',
             bottom='floor')
    nodes.append(room.node())
    for k, z in enumerate((-0.45, 0.85)):
        nodes.append(mbox('light_%d' % k, -1.1, 1.1, CEIL - 0.07, CEIL + 0.02, z - 0.07, z + 0.07,
                          'tube_light', open=['top']))
    return nodes


def interior():
    nodes = []
    # front-loading washers along the back wall: three, and a big one
    for k, (x, w, h) in enumerate([(-1.55, 0.6, 0.95), (-0.9, 0.6, 0.95), (-0.25, 0.6, 0.95),
                                   (0.53, 0.8, 1.15)]):
        nodes.append(mbox('washer_%d' % k, x - w / 2, x + w / 2, FLOOR - 0.02, FLOOR + h,
                          RZ - 0.68, RZ + 0.02, 'washer', open=['bottom', 'front'],
                          back='washer_door'))
    # two stacks of gas dryers on the right wall, doors facing -X
    for k, (z0, z1) in enumerate([(-0.15, 0.7), (0.75, 1.6)]):
        m = Mesh('dryers_%d' % k)
        x0, x1, ym = 1.2, RX + 0.02, FLOOR + 0.84
        for (y0, y1, last) in ((FLOOR - 0.02, ym, False), (ym, FLOOR + 1.72, True)):
            for name, corners, _ in side_quads(x0, x1, y0, y1, z0, z1):
                if name in ('right', 'bottom') or (name == 'top' and not last):
                    continue
                m.face(corners, 'dryer_door' if name == 'left' else 'dryer')
        nodes.append(m.node())
    # a bench on the left wall, with a basket of laundry left on it
    nodes.append(mbox('bench_seat', -RX - 0.02, -1.5, 0.43, 0.49, -0.9, 0.7, 'bench'))
    for k, z in enumerate((-0.8, 0.6)):
        nodes.append(mbox('bench_leg_%d' % k, -RX - 0.01, -1.55, FLOOR - 0.02, 0.44, z - 0.03,
                          z + 0.03, 'metal', open=['bottom', 'top']))
    # a folding table and two plastic chairs
    nodes.append(mbox('table_top', -0.55, 0.45, 0.72, 0.76, -0.25, 0.35, 'table'))
    for k, x in enumerate((-0.48, 0.38)):
        nodes.append(mbox('table_leg_%d' % k, x - 0.02, x + 0.02, FLOOR - 0.02, 0.73, -0.2, 0.3,
                          'metal', open=['bottom', 'top']))
    nodes.append(mbox('basket', -0.35, 0.05, 0.75, 0.97, -0.15, 0.17, 'basket', open=['top']))
    nodes.append(mbox('towels', -0.3, 0.0, 0.74, 0.92, -0.11, 0.13, 'towels', open=['bottom']))
    for k, (x, z, yaw) in enumerate([(-0.15, -0.65, 0), (0.75, 0.05, -100)]):
        c = Mesh('chair_%d' % k, transform={'rotate': [0, yaw, 0], 'translate': [x, 0, z]})
        c.box(-0.2, 0.2, 0.42, 0.46, -0.2, 0.2, 'chair')
        c.box(-0.2, 0.2, 0.47, 0.82, -0.2 + 0.36, 0.2 + 0.0, 'chair')
        c.box(-0.17, 0.17, FLOOR - 0.02, 0.43, -0.17, 0.17, 'metal', open=['bottom', 'top', 'left', 'right'])
        nodes.append(c.node())
    # the change machine by the door
    nodes.append(mbox('changer', 1.62, RX + 0.02, FLOOR - 0.02, 1.45, -1.15, -0.72, 'changer',
                      open=['bottom', 'right'], left='changer_face'))
    # a CRT on a corner shelf, tuned to the weather
    tv = Mesh('tv', transform={'rotate': [0, -40, 0], 'translate': [-1.6, 2.2, 1.5]})
    tv.box(-0.24, 0.24, 0.0, 0.36, -0.2, 0.2, 'tv', back='tv_screen')
    tv.box(-0.3, 0.3, -0.06, 0.01, -0.26, 0.26, 'metal')
    nodes.append(tv.node())
    nodes.append(decal('clock', 0.2, 0.5, 2.25, 2.55, RZ - 0.02, 'clock'))
    nodes.append(decal('poster', -1.15, -0.75, 1.45, 1.95, RZ - 0.02, 'poster'))
    return nodes


def exterior():
    nodes = []
    # the drinks machine beside the shop, and its can bin
    nodes.append(mbox('vending', 2.15, 3.05, 0, 1.83, -1.45, -0.75, 'vending', open=['bottom'],
                      back='vending_face'))
    nodes.append(mbox('vending_roof', 2.13, 3.08, 1.8, 1.88, -1.5, -0.73, 'vending'))
    nodes.append({'id': 'can_bin', 'op': 'cylinder', 'radius': 0.17, 'height': 0.68, 'segments': 8,
                  'material': 'bin', 'transform': {'translate': [2.4, 0.34, -1.75]}})
    nodes.append({'id': 'can_bin_hole', 'op': 'cylinder', 'radius': 0.08, 'height': 0.04,
                  'segments': 6, 'material': 'bin_hole',
                  'transform': {'translate': [2.4, 0.685, -1.75]}})
    # the projecting sign on the left corner, lit, with its brackets
    nodes.append(mbox('side_sign', -2.39, -2.27, 1.85, 2.95, -2.05, -1.5, 'canopy_edge',
                      left='side_sign', right='side_sign'))
    for k, y in enumerate((2.0, 2.8)):
        nodes.append(mbox('bracket_%d' % k, -2.3, -2.05, y - 0.02, y + 0.02, -1.64, -1.48, 'metal'))
    # the air conditioner's outdoor unit on the left wall, its pipe up the wall
    nodes.append(mbox('ac_unit', -2.42, -2.07, 0, 0.6, 0.05, 0.85, 'ac', open=['bottom', 'right'],
                      left='ac_face'))
    nodes.append({'id': 'ac_pipe', 'op': 'cylinder', 'radius': 0.035, 'height': 2.1, 'segments': 6,
                  'caps': False, 'material': 'pipe', 'transform': {'translate': [-2.14, 1.6, 0.7]}})
    # round the back: the dryers' gas flues through the roof, a steel door, a frosted window
    for k, z in enumerate((0.2, 1.15)):
        nodes.append({'id': 'flue_%d' % k, 'op': 'cylinder', 'radius': 0.07, 'height': 0.95,
                      'segments': 6, 'caps': False, 'material': 'flue',
                      'transform': {'translate': [1.55, H + 0.4, z]}})
        nodes.append({'id': 'flue_cap_%d' % k, 'op': 'cone', 'radius': 0.15, 'height': 0.12,
                      'segments': 6, 'material': 'flue',
                      'transform': {'translate': [1.55, H + 0.92, z]}})
    nodes.append(mbox('back_door', -1.3, -0.45, 0, 2.0, ZB - 0.02, ZB + 0.03, 'back_door',
                      open=['bottom', 'back']))
    nodes.append(mbox('back_window', 0.5, 1.4, 1.75, 2.3, ZB - 0.02, ZB + 0.025, 'frosted',
                      open=['back']))
    # an ashtray stand and a planter by the door
    nodes.append({'id': 'ashtray_post', 'op': 'cylinder', 'radius': 0.04, 'height': 0.72,
                  'segments': 6, 'caps': False, 'material': 'ashtray',
                  'transform': {'translate': [1.62, 0.36, -1.9]}})
    nodes.append({'id': 'ashtray', 'op': 'cylinder', 'radius': 0.16, 'height': 0.06, 'segments': 8,
                  'material': 'ashtray', 'transform': {'translate': [1.62, 0.74, -1.9]}})
    nodes.append({'id': 'ashtray_foot', 'op': 'cylinder', 'radius': 0.14, 'height': 0.04,
                  'segments': 8, 'material': 'ashtray', 'transform': {'translate': [1.62, 0.02, -1.9]}})
    nodes.append(mbox('planter', 1.05, 1.4, 0, 0.36, -1.98, -1.63, 'planter', open=['bottom'],
                      top='soil'))
    for k, yaw in enumerate((30, 120)):
        leaf = Mesh('shrub_%d' % k, transform={'rotate': [0, yaw, 0], 'translate': [1.225, 0, -1.805]})
        leaf.face(quad((-0.32, 1.0, 0), (0.32, 1.0, 0), (0.32, 0.3, 0), (-0.32, 0.3, 0), (0, 0, -1)),
                  'leaves')
        nodes.append(leaf.node())
    return nodes


def bicycle():
    """A mamachari parked in front, its front wheel toward the door."""
    z = -2.15
    nodes = []
    for k, x in enumerate((-1.85, -0.78)):
        nodes.append(decal('wheel_%d' % k, x - 0.31, x + 0.31, 0.0, 0.62, z, 'tyre'))
    bb, seat, head = (-1.38, 0.3), (-1.52, 0.86), (-0.86, 0.86)
    nodes.append(tube('down_tube', bb, (-0.9, 0.72), 0.045, 'bike', z))
    nodes.append(tube('seat_tube', bb, seat, 0.05, 'bike', z))
    nodes.append(tube('chain_stay', bb, (-1.85, 0.31), 0.04, 'bike', z))
    nodes.append(tube('seat_stay', (-1.5, 0.78), (-1.85, 0.31), 0.035, 'bike', z))
    nodes.append(tube('fork', (-0.78, 0.31), head, 0.04, 'bike', z))
    nodes.append(tube('stem', head, (-0.92, 1.04), 0.035, 'metal', z))
    nodes.append(box('handlebar', [0.04, 0.035, 0.56], [-0.95, 1.05, z], 'metal'))
    nodes.append(box('carrier', [0.5, 0.025, 0.2], [-1.86, 0.72, z], 'metal'))
    nodes.append(box('saddle', [0.24, 0.07, 0.14], [-1.54, 0.9, z], 'saddle'))
    nodes.append(mbox('chain_guard', -1.86, -1.3, 0.24, 0.38, z + 0.03, z + 0.07, 'bike'))
    nodes.append(mbox('bike_basket', -0.78, -0.44, 0.74, 0.98, z - 0.17, z + 0.17, 'bike_basket',
                      open=['top']))
    return nodes


def main():
    recipe = {
        'format': 'mei-asset', 'version': 1, 'name': 'coin_laundry',
        'budget': {'vertices': 1200, 'triangles': 900},
        'sheets': {'art': {'image': 'art/coin_laundry_sheet.png'}},
        'materials': MATERIALS,
        'lighting': {'mode': 'vertical', 'ambient': 0.55},
        'verification': {'required': True, 'depth': True, 'perspective': True},
        'nodes': building() + interior() + exterior() + bicycle(),
    }
    text = json.dumps(recipe, indent=1)
    (HERE / 'coin_laundry.asset.json').write_text(text + '\n')


if __name__ == '__main__':
    main()
