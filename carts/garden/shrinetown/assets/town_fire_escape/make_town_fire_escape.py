#!/usr/bin/env python3
"""Writes shortcut E's fire escape (shrine town spec 4.5, assets.md 4.1 #22) beside this script:

- town_fire_escape: a steel switchback stair hung on the building's end wall from its roof
  (15.2) down to a lowest landing at 7.6, without its ladder: placed in no layer, it carries the
  collision both states share;
- town_fire_escape_up: the drop ladder up (the default, layer `ladder_e_up`), folded in its
  hanger on that landing's outer edge with a metre of it showing below (bottom 6.3, out of reach);
- town_fire_escape_down: the ladder down (layer `ladder_e`): two steel sections from the street
  to the lowest landing's rail, a pole when down;
- town_fire_escape_col: the stair's collision (landings, flights, rails).

The ladder is a separate asset in each state so that the stair's collision (300 triangles in a
5 x 2 m footprint) is packed once: two copies, one per layer, overfilled the reader's collision
lookup (at most 255 triangles of one kind in a bucket).

The building is shrine/assets/street_building (reused as it is): roof deck 15.2, parapet 16.0,
storeys 3.04, and a blank end wall at its local x = -29 (the end without its own stair). The
escape's back (+Z) is that wall; its front (-Z) faces out. Five flights of 1.52 m over 3.0 m
(26.9 degrees, walkable), each 0.85 m wide, two lanes side by side, landings at alternate ends
every 1.52 m: 7.60 (-X end, the ladder), 9.12 (+X, a door: the building's third floor), 10.64,
12.16 (+X, a door), 13.68, 15.20 (+X, the roof: step over the 0.8 m parapet). Nothing below
7.6 but the ladder, so the street cannot reach the stair without it (a double jump and a grab
reaches about 5.2 m).

Origin: the centre of the 5.0 x 2.0 m footprint at street level; the wall plane is z = +1.0.

Run: python3 carts/garden/shrinetown/assets/town_fire_escape/make_town_fire_escape.py
(standard library).
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent

POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}

# ---- dimensions (metres) ---------------------------------------------------------------------
WALL = 1.0                  # the building's face
ZI0, ZI1 = 0.05, 0.95       # inner lane (against the wall)
ZO0, ZO1 = -0.85, 0.05      # outer lane
DIV = ZI0 + 0.1             # the lane divider's rail (collision 0.05..0.25)
XE = 2.5                    # the footprint's half width
XL = 1.5                    # landings from |x| = 1.5 to 2.5; flights between
RISE, RUN = 1.52, 3.0
LOW = 7.60                  # the lowest landing
LEVELS = 6                  # 7.60 ... 15.20
SLOPE = math.degrees(math.atan2(RISE, RUN))
FLEN = math.hypot(RISE, RUN)
T = 0.12                    # flight and landing thickness
RAIL = 1.0
LAD_X = -2.0                # the ladder's centre line (the -X landing's middle)
LAD_Z = -0.95               # outboard of the outer rail
LAD_W = 0.5

SHOP = '../town_shop_2f_a/art/shopfront.png'


def rail_texels():
    """1 x 1 m of railing: top rail, a mid rail, balusters every 12.5 cm; the rest clear."""
    rows = []
    for y in range(16):
        row = ''
        for x in range(16):
            row += '1' if y in (0, 1) or y == 9 or x % 2 == 0 and y < 15 and x % 4 == 0 else '0'
        rows.append(row)
    return rows


def ladder_texels():
    """0.5 m wide: stiles at the edges, a rung every 0.25 m."""
    return [''.join('1' if x in (0, 7) or y % 4 == 1 else '0' for x in range(8)) for y in range(16)]


def tread_texels():
    """A flight's top, drawn once: eight steps, nosing dark."""
    return [''.join('1' if x % 4 == 3 else ('2' if x % 4 == 0 else '0') for x in range(32))
            for _ in range(8)]


MATS = {
    'steel': {'color': '#6b4a3a', 'palette': True},
    'steel_under': {'color': '#5a3e2c', 'palette': True},
    'deck': {'color': '#8e8a84', 'palette': True},
    'treads': {'color': '#8e8a84', 'texture': {'texels': tread_texels(),
                                               'colors': ['#8e8a84', '#5a5650', '#a8a69e'],
                                               'projection': 'fit'}},
    'rail': {'color': '#6b4a3a', 'double_sided': True,
             'texture': {'texels': rail_texels(), 'colors': ['#000000', '#6b4a3a'],
                         'clear': '#000000', 'projection': 'planar', 'axis': 'z'}},
    'ladder': {'color': '#c8c4b8', 'double_sided': True,
               'texture': {'texels': ladder_texels(), 'colors': ['#000000', '#c8c4b8'],
                           'clear': '#000000', 'projection': 'planar', 'axis': 'z',
                           'scale': [0.5, 1.0], 'offset': [0.5, 0.0]}},
    'hanger': {'color': '#c8c4b8', 'palette': True},
    'door': {'color': '#8e8a84', 'texture': {'sheet': 'shopfront', 'cell': 'back_door',
                                             'projection': 'fit'}},
}
SHEETS = {'shopfront': {'image': SHOP}}


def r(v):
    return round(v, 4)


def level_y(k):
    return LOW + k * RISE


def level_end(k):
    """-1 for the -X end (even levels), +1 for +X."""
    return -1 if k % 2 == 0 else 1


def box(ident, size, at, mat, open_sides=None, faces=None, rotate=None):
    n = {'id': ident, 'op': 'box', 'size': [r(s) for s in size], 'material': mat,
         'transform': {'translate': [r(c) for c in at]}}
    if rotate:
        n['transform']['rotate'] = rotate
    if open_sides:
        n['open'] = open_sides
    if faces:
        n['faces'] = faces
    return n


def flight_lane(k):
    return (ZO0, ZO1) if k % 2 == 0 else (ZI0, ZI1)


def flights(collide=False):
    """Flight k climbs from level k to k + 1: from -X to +X when k is even."""
    out = []
    cos = math.cos(math.radians(SLOPE))
    for k in range(LEVELS - 1):
        z0, z1 = flight_lane(k)
        y0 = level_y(k)
        d = -level_end(k)            # the direction it climbs along x
        ang = r(SLOPE * d)
        if collide:
            # a centimetre off the landings' sides and each other, so no faces coincide
            z0, z1 = (ZO0 + 0.01, ZO1 - 0.01) if k % 2 == 0 else (ZI0 + 0.01, ZI1 - 0.01)
            out.append(box(f'flight_{k}', [FLEN + 0.1, 0.2, z1 - z0],
                           [0, y0 + RISE / 2 - 0.1 / cos, (z0 + z1) / 2], 'solid',
                           rotate=[0, 0, ang]))
        else:
            # inset from the rails: 5 cm from the outer rail, 5 cm from the divider
            if k % 2 == 0:
                z0, z1 = ZO0 + 0.05, ZO1 - 0.05
            else:
                z0, z1 = DIV + 0.05, ZI1 - 0.05
            out.append(box(f'flight_{k}', [FLEN + 0.06, T, z1 - z0],
                           [0, y0 + RISE / 2 - T / 2 / cos, (z0 + z1) / 2], 'steel',
                           ['left', 'right'], faces={'top': 'treads', 'bottom': 'steel_under'},
                           rotate=[0, 0, ang]))
    return out


def landings(collide=False):
    out = []
    for k in range(LEVELS):
        y = level_y(k)
        x = level_end(k) * (XL + XE) / 2
        if collide:
            out.append(box(f'landing_{k}', [XE - XL, 0.2, ZI1 - ZO0], [x, y - 0.1, (ZO0 + ZI1) / 2],
                           'solid'))
        else:
            out.append(box(f'landing_{k}', [XE - XL, T, ZI1 - ZO0], [x, y - T / 2, (ZO0 + ZI1) / 2],
                           'steel', ['front'], faces={'top': 'deck', 'bottom': 'steel_under'}))
    return out


def struts():
    """A diagonal bracket under each landing, from its outer edge back to the wall."""
    out = []
    for k in range(LEVELS):
        y = level_y(k) - T
        x = level_end(k) * (XL + XE) / 2
        # from the outer edge down to the wall a metre below
        za, ya, zb, yb = ZO0 + 0.15, y - 0.02, WALL + 0.05, y - 1.0
        length = math.hypot(zb - za, yb - ya)
        ang = math.degrees(math.atan2(ya - yb, zb - za))
        out.append(box(f'strut_{k}', [0.08, 0.08, length], [x, (ya + yb) / 2, (za + zb) / 2],
                       'steel', ['back', 'front'], rotate=[r(ang), 0, 0]))
    return out


class Rails:
    """Railing panels as one mesh with hand UVs (balusters stay upright on the slopes)."""

    def __init__(self):
        self.v, self.f, self.m, self.uv = [], [], [], []

    def quad(self, a, b, h):
        """An upright panel from a to b (bottom points), h high; u along x or z, v down."""
        length = math.hypot(b[0] - a[0], b[2] - a[2])
        base = len(self.v)
        self.v += [[r(a[0]), r(a[1] + h), r(a[2])], [r(b[0]), r(b[1] + h), r(b[2])],
                   [r(b[0]), r(b[1]), r(b[2])], [r(a[0]), r(a[1]), r(a[2])]]
        self.uv += [[0, 0], [r(length), 0], [r(length), 1], [0, 1]]
        self.f.append([base, base + 1, base + 2, base + 3])
        self.m.append('rail')

    def node(self):
        return {'id': 'rails', 'op': 'mesh', 'vertices': self.v, 'faces': self.f,
                'face_materials': self.m, 'uvs': self.uv}


def rails_mesh(divider=True):
    rl = Rails()
    for k in range(LEVELS - 1):
        if k % 2 == 1 and not divider:
            continue
        y0 = level_y(k)
        d = -level_end(k)
        z = ZO0 if k % 2 == 0 else DIV   # outer flights: the outer edge; inner: the divider
        rl.quad((-d * XL, y0, z), (d * XL, y0 + RISE, z), RAIL)
    for k in range(LEVELS):
        y = level_y(k)
        e = level_end(k)
        # chained with the flight rail they meet, so the panels agree on their facing
        if k % 2 == 1:
            rl.quad((e * XL, y, ZO0), (e * XE, y, ZO0), RAIL)
            rl.quad((e * XE, y, ZO0), (e * XE, y, ZI1), RAIL)
        else:
            rl.quad((e * XE, y, ZI1), (e * XE, y, ZO0), RAIL)
            if k > 0:   # the lowest landing's outer edge is the ladder's gap
                rl.quad((e * XE, y, ZO0), (e * XL, y, ZO0), RAIL)
    return rl.node()


def doors():
    out = []
    for k in (1, 3):
        y = level_y(k)
        x = level_end(k) * (XL + XE) / 2
        out.append(box(f'door_{k}', [0.9, 2.0, 0.06], [x, y + 1.0, WALL - 0.03 - 0.01], 'steel',
                       ['front', 'bottom'], faces={'back': 'door'}))
    return out


def ladder_down():
    """Two sections, the upper 4 cm nearer the stair, from the street to the rail's height."""
    top = LOW + RAIL
    nodes = []
    for ident, y0, y1, z in (('ladder_low', 0.0, 4.7, LAD_Z), ('ladder_high', 4.4, top, LAD_Z + 0.04)):
        x0, x1 = LAD_X - LAD_W / 2, LAD_X + LAD_W / 2
        nodes.append({'id': ident, 'op': 'mesh',
                      'vertices': [[x0, y1, z], [x1, y1, z], [x1, y0, z], [x0, y0, z]],
                      'faces': [[0, 1, 2, 3]], 'face_materials': ['ladder']})
    # the hooks over the landing's edge
    nodes.append(box('hooks', [LAD_W + 0.1, 0.08, 0.3], [LAD_X, top - 0.04, LAD_Z + 0.13],
                     'hanger'))
    return nodes


def hanger():
    """The folded ladder's steel hanger on the landing's outer edge, sunk into its deck."""
    return box('hanger', [LAD_W + 0.12, 0.7, 0.24], [LAD_X, LOW + 0.3, LAD_Z + 0.16], 'hanger',
               ['bottom'])


def ladder_up():
    """Folded in its hanger, a metre of it showing below the landing."""
    x0, x1 = LAD_X - LAD_W / 2, LAD_X + LAD_W / 2
    y0, y1 = LOW - 1.3, LOW + 0.5
    z = LAD_Z
    return [{'id': 'ladder_stub', 'op': 'mesh',
             'vertices': [[x0, y1, z], [x1, y1, z], [x1, y0, z], [x0, y0, z]],
             'faces': [[0, 1, 2, 3]], 'face_materials': ['ladder']}, hanger()]


def body():
    return flights() + landings() + struts() + [rails_mesh()] + doors()


def level1(ladder=None):
    """From 30 m: the flights and landings as slabs (top and underside), the outer railing
    panels (the ladder is its own asset)."""
    nodes = []
    for k in range(LEVELS - 1):
        z0, z1 = flight_lane(k)
        d = -level_end(k)
        y0 = level_y(k)
        nodes.append(box(f'flight_{k}', [FLEN, T, z1 - z0 - 0.1],
                         [0, y0 + RISE / 2 - T / 2, (z0 + z1) / 2], 'steel',
                         ['left', 'right', 'front', 'back'],
                         faces={'top': 'deck', 'bottom': 'steel_under'},
                         rotate=[0, 0, r(SLOPE * d)]))
    for k in range(LEVELS):
        x = level_end(k) * (XL + XE) / 2
        nodes.append(box(f'landing_{k}', [XE - XL, T, ZI1 - ZO0], [x, level_y(k) - T / 2,
                         (ZO0 + ZI1) / 2], 'steel', ['front', 'left', 'right'],
                         faces={'top': 'deck', 'bottom': 'steel_under'}))
    nodes.append(rails_mesh(divider=False))
    return nodes


def collision():
    nodes = flights(True) + landings(True)
    # rails: walls 0.2 thick along the outer edges and the lane divider, 1.0 high
    cos = math.cos(math.radians(SLOPE))
    for k in range(LEVELS - 1):
        y0 = level_y(k)
        d = -level_end(k)
        z = ZO0 + 0.09 if k % 2 == 0 else ZI0 + 0.12
        cy = y0 + RISE / 2 + (RAIL / 2) / cos
        nodes.append(box(f'rail_flight_{k}', [FLEN, RAIL + 0.2, 0.2], [0, cy - 0.1, z], 'solid',
                         rotate=[0, 0, r(SLOPE * d)]))
    for k in range(1, LEVELS):
        y = level_y(k)
        e = level_end(k)
        x = e * (XL + XE) / 2
        nodes.append(box(f'rail_out_{k}', [XE - XL - 0.22, RAIL, 0.2], [x - e * 0.11, y + RAIL / 2,
                         ZO0 + 0.1], 'solid', ['bottom']))
    for k in range(LEVELS):
        y = level_y(k)
        e = level_end(k)
        nodes.append(box(f'rail_end_{k}', [0.2, RAIL, ZI1 - ZO0], [e * (XE - 0.1), y + RAIL / 2,
                         (ZO0 + ZI1) / 2], 'solid', ['bottom']))
    return nodes


def write(name, recipe):
    (HERE / f'{name}.asset.json').write_text(json.dumps(recipe, indent=1) + '\n')


def recipe(name, nodes, lod_nodes):
    return {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': {'triangles': 250},
            'sheets': SHEETS, 'materials': MATS, 'lighting': LIGHT, 'verification': POLICY,
            'nodes': nodes,
            'lod': {'levels': [{'distance': 30, 'nodes': lod_nodes}], 'cull': 160}}


def ladder_recipe(name, nodes):
    return {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': {'triangles': 40},
            'sheets': SHEETS, 'materials': MATS, 'lighting': LIGHT, 'verification': POLICY,
            'nodes': nodes, 'lod': {'cull': 160}}


def main():
    write('town_fire_escape', recipe('town_fire_escape', body(), level1(None)))
    write('town_fire_escape_up', ladder_recipe('town_fire_escape_up', ladder_up()))
    write('town_fire_escape_down', ladder_recipe('town_fire_escape_down', ladder_down()))
    # tag 'metal': the footsteps' surface byte 8 (carts/garden/README.md, "Surfaces")
    write('town_fire_escape_col', {
        'format': 'mei-asset', 'version': 1, 'name': 'town_fire_escape_col',
        'materials': {'solid': {'color': '#ffffff', 'palette': True, 'tag': 'metal'}},
        'lighting': LIGHT, 'verification': POLICY, 'nodes': collision(),
    })


if __name__ == '__main__':
    main()
