#!/usr/bin/env python3
"""Writes the shrine town's school pool (spec 3.15, assets.md 4.1 #17) beside this script:
school_pool.asset.json and school_pool_col.asset.json.

An outdoor 1990s school pool inside its 26 x 18 m footprint (the greybox's x 214-240,
z 22-40): a paved deck behind a 2 m green mesh fence, a 22 x 10 m tank of five 2 m lanes
lined in pale blue tile with dark lane lines, white coping, five starting blocks at the west
end (-X), lane ropes, two steel ladders at the east end, a lifeguard chair and a shower by the
gate in the middle of the front (-Z) fence.

The water is not in this asset: it is the World Kit's (a terrain `water` operation, so the
game's wading query finds it). The tank's opening is x -11..11, z -5..5 about the origin, on
the terrain's 2 m grid wherever the origin is on an odd metre (the greybox's (227, 0, 31):
x 216-238, z 26-36). The terrain carves that rectangle to -1.3 with water at -0.3; this
asset's liner stands 0.1 inside the cut, with its floor (and its collision) at -1.2, so the
water is 0.9 m deep (wading; jumping still works).

Textures: kit patterns and texel grids in the recipe (tile, lanes, mesh fence, floats); no
images.

Run: python3 carts/garden/shrinetown/assets/school_pool/make_school_pool.py (standard library).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}

# ---- dimensions (metres) ---------------------------------------------------------------------
FX, FZ = 13.0, 9.0          # the fence, on the footprint's edge
DX, DZ = 12.9, 8.9          # the deck slab's outer edge
DECK, DECK_B = 0.05, -0.1   # deck top and bottom
TX, TZ = 11.0, 5.0          # the terrain's cut (tank opening)
LX, LZ = 10.9, 4.9          # the liner's walls
FLOOR = -1.2
WATER = -0.3
CX0, CX1 = 10.85, 11.35     # coping across x (inner, outer); z: minus 6.0 (4.85, 5.35)
CZ0, CZ1 = 4.85, 5.35
COPE = 0.12
FENCE_H = 2.0
LANES = [-4.0, -2.0, 0.0, 2.0, 4.0]
ROPES = [-3.0, -1.0, 1.0, 3.0]


def fence_texels():
    """2 x 2 m of welded mesh: post and rails dark green, wires every 25 and 50 cm."""
    rows = []
    for y in range(32):
        row = ''
        for x in range(32):
            if x in (0, 1) or y in (0, 1) or y in (30, 31):
                row += '1'
            elif x % 4 == 0 or y % 8 == 0:
                row += '2'
            else:
                row += '0'
        rows.append(row)
    return rows


def lane_texels():
    """The tank floor, 1 x 2 m: pale tile with a grout line, the lane line at v = 0."""
    rows = []
    for y in range(16):
        row = ''
        for x in range(8):
            if y in (0, 15):
                row += '2'
            elif x == 0 or y == 8:
                row += '1'
            else:
                row += '0'
        rows.append(row)
    return rows


def ladder_texels():
    """A steel ladder 0.5 m wide: stiles at the edges, a rung every 0.25 m."""
    rows = []
    for y in range(16):
        row = ''
        for x in range(8):
            row += '1' if x in (0, 7) or y % 4 == 1 else '0'
        rows.append(row)
    return rows


MATS = {
    'floor': {'color': '#7cc0d8', 'texture': {'texels': lane_texels(),
                                              'colors': ['#7cc0d8', '#68acc6', '#1e3c78'],
                                              'projection': 'planar', 'axis': 'y',
                                              'scale': [1.0, 2.0]}},
    'tile': {'color': '#7cc0d8', 'texture': {'pattern': 'tile', 'size': 16,
                                             'colors': ['#7cc0d8', '#68acc6', '#86c8de'],
                                             'params': {'count': 4, 'grout': 1},
                                             'projection': 'box', 'scale': [1.0, 1.0]}},
    'deck': {'color': '#c8c8bc', 'texture': {'pattern': 'tile', 'size': 16,
                                             'colors': ['#c8c8bc', '#aeaea4',
                                                        '#d0d0c4'],
                                             'params': {'count': 2, 'grout': 1},
                                             'projection': 'box', 'scale': [1.0, 1.0]}},
    'fence': {'color': '#2e5a3a', 'double_sided': True,
              'texture': {'texels': fence_texels(), 'colors': ['#000000', '#2e5a3a', '#4a7a52'],
                          'clear': '#000000', 'projection': 'box', 'scale': [2.0, 2.0],
                          'offset': [0.5, 0.0]}},
    'floats': {'color': '#d8462a', 'texture': {'pattern': 'stripes', 'size': 16,
                                               'colors': ['#d8462a', '#eceae4', '#3a6ab0',
                                                          '#eceae4'],
                                               'params': {'count': 4, 'axis': 'u'},
                                               'projection': 'box', 'scale': [2.0, 2.0]}},
    'ladder': {'color': '#c8c4b8', 'double_sided': True,
               'texture': {'texels': ladder_texels(), 'colors': ['#000000', '#c8c4b8'],
                           'clear': '#000000', 'projection': 'planar', 'axis': 'x',
                           'scale': [0.5, 1.0], 'offset': [0.5, 0.0]}},
    'coping': {'color': '#eceae4', 'palette': True},
    'block': {'color': '#3a6ab0', 'palette': True},
    'block_top': {'color': '#eceae4', 'palette': True},
    'steel': {'color': '#c8c4b8', 'palette': True},
    'chair': {'color': '#eceae4', 'palette': True},
    'edge': {'color': '#a8a69e', 'palette': True},
}


def r(v):
    return round(v, 4)


class Mesh:
    def __init__(self, ident):
        self.ident, self.v, self.f, self.m, self.index = ident, [], [], [], {}

    def vert(self, p):
        key = tuple(r(c) for c in p)
        if key not in self.index:
            self.index[key] = len(self.v)
            self.v.append(list(key))
        return self.index[key]

    def face(self, pts, mat):
        self.f.append([self.vert(p) for p in pts])
        self.m.append(mat)

    def node(self):
        return {'id': self.ident, 'op': 'mesh', 'vertices': self.v, 'faces': self.f,
                'face_materials': self.m}


def box(ident, size, at, mat, open_sides=None, faces=None):
    n = {'id': ident, 'op': 'box', 'size': [r(s) for s in size], 'material': mat,
         'transform': {'translate': [r(c) for c in at]}}
    if open_sides:
        n['open'] = open_sides
    if faces:
        n['faces'] = faces
    return n


def ring_top(m, x0, z0, x1, z1, y, mat):
    """The top of a rectangular ring between the inner (x0, z0) and outer (x1, z1) half sizes:
    four trapezoids, corners clockwise seen from above."""
    i = [(-x0, y, -z0), (x0, y, -z0), (x0, y, z0), (-x0, y, z0)]
    o = [(-x1, y, -z1), (x1, y, -z1), (x1, y, z1), (-x1, y, z1)]
    for k in range(4):
        a, b = k, (k + 1) % 4
        # o[a], i[a], i[b], o[b] is clockwise seen from above
        m.face([o[a], i[a], i[b], o[b]], mat)


def ring_sides(m, hx, hz, y0, y1, mat, inward):
    """Upright faces round a rectangle of half sizes hx, hz, facing out (or in)."""
    c = [(-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz)]
    for k in range(4):
        (xa, za), (xb, zb) = c[k], c[(k + 1) % 4]
        # c runs anticlockwise seen from above, so from outside c[k] is on the left
        if inward:
            m.face([(xb, y1, zb), (xa, y1, za), (xa, y0, za), (xb, y0, zb)], mat)
        else:
            m.face([(xa, y1, za), (xb, y1, zb), (xb, y0, zb), (xa, y0, za)], mat)


def tank(m):
    """The liner: floor and four walls facing into the tank, up into the coping."""
    m.face([(-LX, FLOOR, -LZ), (-LX, FLOOR, LZ), (LX, FLOOR, LZ), (LX, FLOOR, -LZ)], 'floor')
    ring_sides(m, LX, LZ, FLOOR, 0.06, 'tile', inward=True)


def deck(m, sides=True):
    ring_top(m, TX, TZ, DX, DZ, DECK, 'deck')
    if sides:
        ring_sides(m, DX, DZ, DECK_B, DECK, 'edge', inward=False)


def coping(m, sides=True):
    ring_top(m, CX0, CZ0, CX1, CZ1, COPE, 'coping')
    if sides:
        ring_sides(m, CX0, CZ0, -0.05, COPE, 'coping', inward=True)
        ring_sides(m, CX1, CZ1, 0.0, COPE, 'coping', inward=False)


def fence(m):
    """Four upright panels on the footprint's edge, seen from both sides."""
    c = [(-FX, -FZ), (FX, -FZ), (FX, FZ), (-FX, FZ)]
    for k in range(4):
        (xa, za), (xb, zb) = c[k], c[(k + 1) % 4]
        m.face([(xb, FENCE_H, zb), (xa, FENCE_H, za), (xa, 0.0, za), (xb, 0.0, zb)], 'fence')


def level0():
    nodes = []
    t = Mesh('tank')
    tank(t)
    nodes.append(t.node())
    d = Mesh('deck')
    deck(d)
    nodes.append(d.node())
    c = Mesh('coping')
    coping(c)
    nodes.append(c.node())
    f = Mesh('fence')
    fence(f)
    nodes.append(f.node())
    # starting blocks at the west end, one a lane, standing on the coping
    for i, z in enumerate(LANES):
        h = 0.75
        nodes.append(box(f'block_{i}', [0.5, h, 0.5], [-(CX0 + 0.2), h / 2, z],
                         'block', ['bottom'], faces={'top': 'block_top'}))
    # lane ropes floating at the water line, wall to wall
    for i, z in enumerate(ROPES):
        nodes.append(box(f'rope_{i}', [2 * LX, 0.12, 0.12], [0, WATER, z], 'floats',
                         ['left', 'right']))
    # steel ladders at the east end, 0.2 m off the wall, rising 0.9 above the deck
    for s, z in (('s', -3.9), ('n', 3.9)):
        x = LX - 0.2
        nodes.append({'id': f'ladder_{s}', 'op': 'mesh',
                      'vertices': [[x, 0.95, z - 0.25], [x, 0.95, z + 0.25],
                                   [x, -1.05, z + 0.25], [x, -1.05, z - 0.25]],
                      'faces': [[0, 1, 2, 3]], 'face_materials': ['ladder']})
    # the lifeguard chair on the front deck, facing the water: a platform on two ladder frames
    chx, chz = 6.0, -7.0
    nodes.append(box('chair_seat', [0.9, 0.1, 0.9], [chx, 1.85, chz], 'chair'))
    nodes.append(box('chair_back', [0.9, 0.6, 0.08], [chx, 2.2, chz - 0.41], 'chair', ['bottom']))
    for s, sx in (('w', -1), ('e', 1)):
        x = chx + sx * 0.4
        nodes.append({'id': f'chair_frame_{s}', 'op': 'mesh',
                      'vertices': [[x, 1.82, chz - 0.45], [x, 1.82, chz + 0.45],
                                   [x, 0.0, chz + 0.45], [x, 0.0, chz - 0.45]],
                      'faces': [[0, 1, 2, 3]], 'face_materials': ['ladder']})
    # the shower by the gate: two posts and the spray bar
    shx, shz = -3.0, -7.6
    for s, sx in (('w', -1), ('e', 1)):
        nodes.append(box(f'shower_{s}', [0.08, 2.3, 0.08], [shx + sx * 1.2, 1.15, shz], 'steel',
                         ['top', 'bottom']))
    bar = box('shower_bar', [2.6, 0.06, 0.06], [shx, 2.3, shz], 'steel', ['left', 'right'])
    bar['transform']['rotate'] = [45, 0, 0]   # no face parallel to the posts'
    nodes.append(bar)
    return nodes


def level1():
    t = Mesh('tank')
    tank(t)
    d = Mesh('deck')
    deck(d, sides=False)
    coping(d, sides=False)
    fence(d)
    blocks = box('blocks', [0.5, 0.65, 9.0], [-(CX0 + 0.2), 0.425, 0], 'block', ['bottom'],
                 faces={'top': 'block_top'})
    ropes = Mesh('ropes')
    for z in ROPES:
        y = WATER + 0.06
        ropes.face([(-LX, y, z - 0.06), (-LX, y, z + 0.06), (LX, y, z + 0.06), (LX, y, z - 0.06)],
                   'floats')
    return [t.node(), d.node(), blocks, ropes.node()]


def level2():
    m = Mesh('pool')
    m.face([(-LX, FLOOR, -LZ), (-LX, FLOOR, LZ), (LX, FLOOR, LZ), (LX, FLOOR, -LZ)], 'block')
    ring_top(m, TX, TZ, DX, DZ, DECK, 'edge')
    fence(m)
    return [m.node()]


def ring_solid(m, ix, iz, ox, oz, y0, y1, mat):
    """A closed rectangular ring: top, bottom, outer and inner sides."""
    ring_top(m, ix, iz, ox, oz, y1, mat)
    i = [(-ix, y0, -iz), (ix, y0, -iz), (ix, y0, iz), (-ix, y0, iz)]
    o = [(-ox, y0, -oz), (ox, y0, -oz), (ox, y0, oz), (-ox, y0, oz)]
    for k in range(4):
        a, b = k, (k + 1) % 4
        m.face([o[b], i[b], i[a], o[a]], mat)
    ring_sides(m, ox, oz, y0, y1, mat, inward=False)
    ring_sides(m, ix, iz, y0, y1, mat, inward=True)


def collision():
    nodes = []
    d = Mesh('deck')
    ring_solid(d, TX, TZ, DX, DZ, DECK_B, DECK, 'solid')
    nodes.append(d.node())
    c = Mesh('coping')
    ring_solid(c, CX0, CZ0, CX1, CZ1, 0.0, COPE, 'solid')
    nodes.append(c.node())
    # the tank: its floor at -1.2 and its walls, faces into the water (an open surface)
    t = Mesh('tank')
    t.face([(-LX, FLOOR, -LZ), (-LX, FLOOR, LZ), (LX, FLOOR, LZ), (LX, FLOOR, -LZ)], 'solid')
    ring_sides(t, LX, LZ, FLOOR, 0.06, 'solid', inward=True)
    nodes.append(t.node())
    # the fence: walls 0.2 thick, 2.0 high, inside the footprint; the end walls stop 1 cm short
    fy = FENCE_H / 2
    nodes.append(box('fence_s', [2 * FX, FENCE_H, 0.2], [0, fy, -(FZ - 0.1)], 'solid', ['bottom']))
    nodes.append(box('fence_n', [2 * FX, FENCE_H, 0.2], [0, fy, FZ - 0.1], 'solid', ['bottom']))
    nodes.append(box('fence_w', [0.2, FENCE_H, 2 * FZ - 0.42], [-(FX - 0.1), fy, 0], 'solid',
                     ['bottom']))
    nodes.append(box('fence_e', [0.2, FENCE_H, 2 * FZ - 0.42], [FX - 0.1, fy, 0], 'solid',
                     ['bottom']))
    # the starting blocks and the lifeguard chair's seat
    for i, z in enumerate(LANES):
        nodes.append(box(f'block_{i}', [0.5, 0.7, 0.5], [-(CX0 + 0.2), 0.4, z], 'solid',
                         ['bottom']))
    nodes.append(box('chair_seat', [0.9, 0.2, 0.9], [6.0, 1.8, -7.0], 'solid'))
    return nodes


def write(name, recipe):
    (HERE / f'{name}.asset.json').write_text(json.dumps(recipe, indent=1) + '\n')


def main():
    write('school_pool', {
        'format': 'mei-asset', 'version': 1, 'name': 'school_pool',
        'budget': {'triangles': 300},
        'materials': MATS, 'lighting': LIGHT, 'verification': POLICY,
        'nodes': level0(),
        'lod': {'levels': [{'distance': 24, 'nodes': level1()},
                           {'distance': 60, 'nodes': level2()}]},
    })
    write('school_pool_col', {
        'format': 'mei-asset', 'version': 1, 'name': 'school_pool_col',
        'materials': {'solid': {'color': '#ffffff', 'palette': True}},
        'lighting': LIGHT, 'verification': POLICY, 'nodes': collision(),
    })


if __name__ == '__main__':
    main()
