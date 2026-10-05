#!/usr/bin/env python3
"""Writes the shrine town's school gymnasium (spec 3.15, assets.md 4.1 #16) beside this script:
school_gym.asset.json and school_gym_col.asset.json.

A 1990s school gym: a long hall with a shallow barrel roof of painted red-brown steel, cream
walls on a cement base, two tiers of steel-sashed windows down both long sides, a row of steel
doors under a flat entrance canopy, a clock in each gable and three ventilators on the crown.

Footprint 30 x 24 (the greybox's 24 x 30 turned: the long axis is X here, the entrance on the
long -Z side), crown 9.0, eaves 7.4. The roof is a route (spec 3.15, the east routes): its
collision is four facets of at most 13 degrees, and it is reached without a glide by the
entrance canopy (3.45, a double jump and a grab from the street) and from there the front eave
(7.4, 3.95 above the canopy: a double jump and a grab).

Textures: the town's shared sheets (town_common's tin_red, tin and plaster from
town_alley_house_a; the shopfront sheet's back_door and clock from town_shop_2f_a), and two
small texel grids in the recipe itself, the window bay and the cement base with its vents (no
image of their own).

Run: python3 carts/garden/shrinetown/assets/school_gym/make_school_gym.py (standard library).
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent

POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}

# ---- dimensions (metres) ---------------------------------------------------------------------
X0, X1 = -15.0, 15.0        # gable walls
ZF, ZB = -9.6, 11.7         # front (entrance) and back walls
OVER = 0.3                  # eave and verge overhang
EAVE, CROWN = 7.4, 9.0      # roof top at the eave edge and at the crown
SLAB = 0.25                 # roof thickness
N = 8                       # roof facets across
ZC = (ZF + ZB) / 2          # 1.05
A = (ZB - ZF) / 2 + OVER    # 10.95, half span at the eave edge
R = (A * A + (CROWN - EAVE) ** 2) / (2 * (CROWN - EAVE))
SINK = 0.1                  # walls run this far up into the roof slab

BASE = 1.0                  # cement base band
DOOR = 2.0                  # door head
WIN0, WIN1 = 2.4, 6.4       # window band (two tiers of 2 m sashes)
DOOR_X = 3.0                # doors across x -3..3 under the canopy

CANOPY_X = 5.0              # canopy x -5..5
CANOPY_Z = -12.0            # its front edge (the footprint's front)
CANOPY_TOP, CANOPY_T = 3.45, 0.2

COMMON = '../town_alley_house_a/art/town_common.png'

def window_texels():
    """One 2 x 2 m bay of steel sashes: frame on the left and top, a meeting rail in the
    middle, a transom bar, and glass dark below with a pale streak of sky. Stacked twice and
    repeated along the walls, the frame lines double up into the columns between bays."""
    rows = []
    for y in range(16):
        row = ''
        for x in range(16):
            if y == 0 or x == 0 or x == 8 or y == 6:
                row += '0'
            elif (x + y) % 11 in (3, 4) and y < 6:
                row += '3'
            elif y < 6:
                row += '2'
            else:
                row += '3' if (x + y) % 13 == 5 else '1'
        rows.append(row)
    return rows


def base_texels():
    """The cement base, a metre high: a floor-level vent with a grille in each 2 m bay."""
    rows = []
    for y in range(8):
        row = ''
        for x in range(16):
            if 4 <= x <= 11 and 3 <= y <= 5:
                row += '3' if x % 2 == 0 else '2'
            elif y == 0:
                row += '1'
            else:
                row += '1' if (x * 7 + y * 3) % 9 == 0 else '0'
        rows.append(row)
    return rows


WINDOW_TEXELS = window_texels()
BASE_TEXELS = base_texels()

SHOP = '../town_shop_2f_a/art/shopfront.png'

MATS = {
    'roof': {'color': '#8a3a2a', 'texture': {'sheet': 'town_common', 'cell': 'tin_red',
                                             'projection': 'box', 'scale': [2.0, 2.0]}},
    'plaster': {'color': '#e0d6c0', 'texture': {'sheet': 'town_common', 'cell': 'plaster',
                                                'projection': 'box', 'scale': [2.0, 2.0]}},
    'base': {'color': '#a8a69e', 'texture': {'texels': BASE_TEXELS,
                                             'colors': ['#a8a69e', '#9a988f', '#3a3c40', '#6a665e'],
                                             'projection': 'box', 'scale': [2.0, 1.0],
                                             'offset': [0.5, 0.0]}},
    'windows': {'color': '#5a7488', 'texture': {'texels': WINDOW_TEXELS,
                                                'colors': ['#4a5058', '#3e5266', '#5a7488', '#8aa4b4'],
                                                'projection': 'box', 'scale': [2.0, 2.0],
                                                'offset': [0.5, 0.2]}},
    'doors': {'color': '#8e8a84', 'texture': {'sheet': 'shopfront', 'cell': 'back_door',
                                              'projection': 'box', 'scale': [1.0, 2.0]}},
    'clock': {'color': '#d8b048', 'texture': {'sheet': 'shopfront', 'cell': 'clock',
                                              'projection': 'fit'}},
    'roof_edge': {'color': '#843828', 'palette': True},
    'soffit': {'color': '#8e887c', 'palette': True},
    'trim': {'color': '#e0d6c0', 'palette': True},
    'canopy': {'color': '#a8a69e', 'palette': True},
    'steel': {'color': '#565c64', 'palette': True},
    'vent': {'color': '#8e8a84', 'texture': {'sheet': 'town_common', 'cell': 'tin',
                                             'projection': 'box', 'scale': [2.0, 2.0]}},
}
SHEETS = {'town_common': {'image': COMMON}, 'shopfront': {'image': SHOP}}


def r(v):
    return round(v, 4)


def arc_y(z):
    """The roof's top surface on the true arc."""
    d = z - ZC
    return CROWN - (R - math.sqrt(R * R - d * d))


def facet_zs(n):
    return [ZC - A + i * 2 * A / n for i in range(n + 1)]


def facet_y(z, n):
    """The top surface on the n-facet roof (linear between the facet lines)."""
    zs = facet_zs(n)
    for i in range(n):
        if zs[i] - 1e-9 <= z <= zs[i + 1] + 1e-9:
            t = (z - zs[i]) / (zs[i + 1] - zs[i])
            return arc_y(zs[i]) + t * (arc_y(zs[i + 1]) - arc_y(zs[i]))
    raise ValueError(z)


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
        return len(self.f) - 1

    def node(self, decals=None):
        n = {'id': self.ident, 'op': 'mesh', 'vertices': self.v, 'faces': self.f,
             'face_materials': self.m}
        if decals:
            n['decals'] = decals
        return n


def box(ident, size, at, mat, open_sides=None, faces=None):
    n = {'id': ident, 'op': 'box', 'size': [r(s) for s in size], 'material': mat,
         'transform': {'translate': [r(c) for c in at]}}
    if open_sides:
        n['open'] = open_sides
    if faces:
        n['faces'] = faces
    return n


# ---- the roof -----------------------------------------------------------------------------------

def roof(n, top_mat='roof', under=True):
    """A shell of n facets across z, extruded along x from verge to verge."""
    m = Mesh('roof')
    xa, xb = X0 - OVER, X1 + OVER
    zs = facet_zs(n)
    top = [(z, arc_y(z)) for z in zs]
    bot = [(z, y - SLAB) for z, y in top]
    for i in range(n):
        (za, ya), (zb, yb) = top[i], top[i + 1]
        # upward: corners clockwise seen from above with -z toward the viewer's bottom
        m.face([(xa, ya, za), (xa, yb, zb), (xb, yb, zb), (xb, ya, za)], top_mat)
        if under:
            (za, ya), (zb, yb) = bot[i], bot[i + 1]
            m.face([(xa, ya, za), (xb, ya, za), (xb, yb, zb), (xa, yb, zb)], 'soffit')
    # eave edges (front -z, back +z)
    m.face([(xa, top[0][1], zs[0]), (xb, top[0][1], zs[0]), (xb, bot[0][1], zs[0]),
            (xa, bot[0][1], zs[0])], 'roof_edge')
    m.face([(xb, top[-1][1], zs[-1]), (xa, top[-1][1], zs[-1]), (xa, bot[-1][1], zs[-1]),
            (xb, bot[-1][1], zs[-1])], 'roof_edge')
    # verge caps: +x seen from +x has +z to its right... corners clockwise from outside
    cap_e = [(xb, y, z) for z, y in top] + [(xb, y, z) for z, y in reversed(bot)]
    cap_w = [(xa, y, z) for z, y in reversed(top)] + [(xa, y, z) for z, y in bot]
    m.face(cap_e, 'roof_edge')
    m.face(cap_w, 'roof_edge')
    return m


# ---- the walls ----------------------------------------------------------------------------------

def wall_top():
    """Long walls stop SINK inside the slab at the wall line (the slab's underside there)."""
    return facet_y(ZF, N) - SLAB + SINK


def long_wall(m, z, outward, xbreaks, cells):
    """A wall in the plane z, a grid of quads. cells[col][row] is a material; rows are
    between ybreaks. outward is -1 (faces -z) or +1."""
    yb = [0.0, BASE, DOOR, WIN0, WIN1, wall_top()]
    for c in range(len(xbreaks) - 1):
        xa, xb = xbreaks[c], xbreaks[c + 1]
        for row in range(len(yb) - 1):
            ya, yc = yb[row], yb[row + 1]
            mat = cells[c][row]
            if outward < 0:   # seen from -z: x to the right
                pts = [(xa, yc, z), (xb, yc, z), (xb, ya, z), (xa, ya, z)]
            else:             # seen from +z: -x to the right
                pts = [(xb, yc, z), (xa, yc, z), (xa, ya, z), (xb, ya, z)]
            m.face(pts, mat)


def gable(m, x, outward, n):
    """An end wall at x: the cement band and the plaster above it up into the roof."""
    zs = [ZF] + [z for z in facet_zs(n) if ZF < z < ZB] + [ZB]
    tops = [(z, facet_y(z, n) - SLAB + SINK) for z in zs]
    if outward > 0:   # seen from +x: +z to the right
        base = [(x, BASE, ZF), (x, BASE, ZB), (x, 0.0, ZB), (x, 0.0, ZF)]
        upper = [(x, y, z) for z, y in tops] + [(x, BASE, ZB), (x, BASE, ZF)]
    else:             # seen from -x: -z to the right
        base = [(x, BASE, ZB), (x, BASE, ZF), (x, 0.0, ZF), (x, 0.0, ZB)]
        upper = [(x, y, z) for z, y in reversed(tops)] + [(x, BASE, ZF), (x, BASE, ZB)]
    m.face(base, 'base')
    return m.face(upper, 'plaster')


def level0():
    walls = Mesh('walls')
    p, b, w, d = 'plaster', 'base', 'windows', 'doors'
    side = [b, p, p, w, p]
    long_wall(walls, ZF, -1, [X0, -DOOR_X, DOOR_X, X1], [side, [d, d, p, w, p], side])
    long_wall(walls, ZB, +1, [X0, X1], [side])
    east = gable(walls, X1, +1, N)
    west = gable(walls, X0, -1, N)
    nodes = [walls.node(), roof(N).node()]
    # the clocks: decals on the gables' plaster, centred under the crown. A decal's 'at' is
    # right and up from the mesh's origin as it lies on the face: on +x, right is +z
    cy = 6.2
    nodes[0]['decals'] = [
        {'id': 'clock_e', 'face': east, 'material': 'clock', 'size': [2.0, 2.0], 'at': [ZC, cy]},
        {'id': 'clock_w', 'face': west, 'material': 'clock', 'size': [2.0, 2.0], 'at': [-ZC, cy]},
    ]
    # the entrance canopy and its posts
    cz0, cz1 = CANOPY_Z, ZF + 0.02
    nodes.append(box('canopy', [2 * CANOPY_X, CANOPY_T, cz1 - cz0],
                     [0, CANOPY_TOP - CANOPY_T / 2, (cz0 + cz1) / 2], 'canopy',
                     faces={'back': 'trim', 'left': 'trim', 'right': 'trim', 'bottom': 'soffit'}))
    post_h = CANOPY_TOP - CANOPY_T + 0.02
    for s, sx in (('w', -1), ('e', 1)):
        nodes.append(box(f'post_{s}', [0.2, post_h, 0.2], [sx * (CANOPY_X - 0.3), post_h / 2,
                         CANOPY_Z + 0.3], 'steel', ['top', 'bottom']))
    # downpipes at the four corners, 0.15 off the walls
    ph = wall_top() - 0.15
    for s, x, z in (('fw', X0 + 0.4, ZF - 0.15), ('fe', X1 - 0.4, ZF - 0.15),
                    ('bw', X0 + 0.4, ZB + 0.15), ('be', X1 - 0.4, ZB + 0.15)):
        nodes.append(box(f'pipe_{s}', [0.12, ph, 0.12], [x, ph / 2, z], 'steel',
                         ['top', 'bottom']))
    # ridge ventilators on the crown, sunk into the roof
    for i, x in enumerate((-9.0, 0.0, 9.0)):
        h = 0.5
        nodes.append(box(f'vent_{i}', [1.4, h, 1.0], [x, CROWN - 0.15 + h / 2, ZC], 'vent',
                         ['bottom'], faces={'top': 'roof_edge'}))
    return nodes


def level1():
    walls = Mesh('walls')
    p, b, w = 'plaster', 'base', 'windows'
    yb = [0.0, BASE, WIN0, WIN1, wall_top()]
    for z, out in ((ZF, -1), (ZB, 1)):
        for row, mat in enumerate((b, p, w, p)):
            ya, yc = yb[row], yb[row + 1]
            if out < 0:
                pts = [(X0, yc, z), (X1, yc, z), (X1, ya, z), (X0, ya, z)]
            else:
                pts = [(X1, yc, z), (X0, yc, z), (X0, ya, z), (X1, ya, z)]
            walls.face(pts, mat)
    n = 4
    for x, out in ((X1, 1), (X0, -1)):
        zs = [ZF] + [z for z in facet_zs(n) if ZF < z < ZB] + [ZB]
        tops = [(z, facet_y(z, n) - SLAB + SINK) for z in zs]
        if out > 0:
            pts = [(x, y, z) for z, y in tops] + [(x, 0.0, ZB), (x, 0.0, ZF)]
        else:
            pts = [(x, y, z) for z, y in reversed(tops)] + [(x, 0.0, ZF), (x, 0.0, ZB)]
        walls.face(pts, 'trim')
    cz0, cz1 = CANOPY_Z, ZF + 0.02
    canopy = box('canopy', [2 * CANOPY_X, CANOPY_T, cz1 - cz0],
                 [0, CANOPY_TOP - CANOPY_T / 2, (cz0 + cz1) / 2], 'canopy', ['bottom'])
    return [walls.node(), roof(n, under=False).node(), canopy]


def level2():
    m = Mesh('hall')
    top = wall_top()
    # four walls, open top and bottom; the long ones keep the window band as a dark stripe
    for z, out in ((ZF, -1), (ZB, 1)):
        for ya, yc, mat in ((0.0, WIN0, 'trim'), (WIN0, WIN1, 'steel'), (WIN1, top, 'trim')):
            if out < 0:
                m.face([(X0, yc, z), (X1, yc, z), (X1, ya, z), (X0, ya, z)], mat)
            else:
                m.face([(X1, yc, z), (X0, yc, z), (X0, ya, z), (X1, ya, z)], mat)
    m.face([(X1, top, ZF), (X1, top, ZB), (X1, 0, ZB), (X1, 0, ZF)], 'trim')
    m.face([(X0, top, ZB), (X0, top, ZF), (X0, 0, ZF), (X0, 0, ZB)], 'trim')
    # a two-facet roof down to the wall tops, its gable triangles
    xa, xb = X0 - OVER, X1 + OVER
    zf, zb = ZC - A, ZC + A
    m.face([(xa, EAVE, zf), (xa, CROWN, ZC), (xb, CROWN, ZC), (xb, EAVE, zf)], 'roof_edge')
    m.face([(xa, CROWN, ZC), (xa, EAVE, zb), (xb, EAVE, zb), (xb, CROWN, ZC)], 'roof_edge')
    m.face([(X1, top, ZF), (X1, CROWN - 0.1, ZC), (X1, top, ZB)], 'trim')
    m.face([(X0, top, ZB), (X0, CROWN - 0.1, ZC), (X0, top, ZF)], 'trim')
    return [m.node()]


def collision():
    nodes = []
    top = wall_top()
    nodes.append(box('hall', [X1 - X0, top, ZB - ZF], [0, top / 2, ZC], 'solid', ['top']))
    # the roof: four walkable facets on the true arc, a flat underside inside the hall
    n = 4
    zs = facet_zs(n)
    pts = [[r(-z), r(arc_y(z))] for z in zs] + [[r(-zs[-1]), r(top - 0.2)], [r(-zs[0]), r(top - 0.2)]]
    nodes.append({'id': 'roof', 'op': 'extrude', 'material': 'solid', 'depth': X1 - X0 + 2 * OVER,
                  'points': pts, 'transform': {'rotate': [0, 90, 0]}})
    cz0, cz1 = CANOPY_Z, ZF + 0.02
    nodes.append(box('canopy', [2 * CANOPY_X, CANOPY_T, cz1 - cz0],
                     [0, CANOPY_TOP - CANOPY_T / 2, (cz0 + cz1) / 2], 'solid'))
    post_h = CANOPY_TOP - CANOPY_T + 0.02
    for s, sx in (('w', -1), ('e', 1)):
        nodes.append(box(f'post_{s}', [0.2, post_h, 0.2], [sx * (CANOPY_X - 0.3), post_h / 2,
                         CANOPY_Z + 0.3], 'solid', ['top', 'bottom']))
    for i, x in enumerate((-9.0, 0.0, 9.0)):
        h = 0.5
        nodes.append(box(f'vent_{i}', [1.4, h, 1.0], [x, CROWN - 0.15 + h / 2, ZC], 'solid',
                         ['bottom']))
    return nodes


def write(name, recipe):
    (HERE / f'{name}.asset.json').write_text(json.dumps(recipe, indent=1) + '\n')


def main():
    write('school_gym', {
        'format': 'mei-asset', 'version': 1, 'name': 'school_gym',
        'budget': {'triangles': 500},
        'sheets': SHEETS, 'materials': MATS, 'lighting': LIGHT, 'verification': POLICY,
        'nodes': level0(),
        'lod': {'levels': [{'distance': 24, 'nodes': level1()},
                           {'distance': 60, 'nodes': level2()}]},
    })
    write('school_gym_col', {
        'format': 'mei-asset', 'version': 1, 'name': 'school_gym_col',
        'materials': {'solid': {'color': '#ffffff', 'palette': True}},
        'lighting': LIGHT, 'verification': POLICY, 'nodes': collision(),
    })


if __name__ == '__main__':
    main()
