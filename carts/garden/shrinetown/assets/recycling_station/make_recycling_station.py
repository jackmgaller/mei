"""Writes recycling_station.asset.json and recycling_station_col.asset.json beside this script
(python3 make_recycling_station.py): the neighbourhood's rubbish and recycling point at a back
alley corner (shrine town spec 3.3; assets.md section 3).

Adapted from the lab model (examples/assets/lab/recycling_station, 436 triangles), same size and
layout: a concrete pad, a galvanised fence on two posts with the collection-day board on a
crossbar, a green corrugated roof sloping to the front, the blue burnables bin, a crate of empty
bottles, a rubbish bag under the green crow net, and the crow on the roof watching it. The board,
bin and lid are the lab's pictures (art/sheet.png, copied with its sheet file and the script that
drew it). The cut: the fence is one double-sided sheet of the town's tin (town_common's `tin`),
the roof two faces, two bottles, one bag, a simpler crow.

Footprint 2.3 x 1.2 m (the roof; the pad is 2.1 x 1.2), origin at the middle of the pad's foot,
the open front toward -Z. The fence stands at z 0.5 to 1.29, its posts to 2.05; the roof slopes
10 degrees from 2.10 at the back (z 0.65) to 1.92 at the front (z -0.35), walkable in the
collision. Levels: L1 from 20 m, L2 from 45 m, culled at 80 m.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

PAD = (1.05, 0.6, 0.1)                  # half x, half z, top
FENCE_Z, FENCE_TOP = 0.5, 1.29
POST_X, POST_TOP = 0.96, 2.05
ROOF = (1.15, -0.35, 0.65, 2.0, 10)     # half x, front z, back z, height at its middle, pitch
BIN = (-0.62, -0.02, 0.27, 0.7)         # x, z, radius, height
CRATE = (0.02, -0.02)
BAG = (0.63, 0.04)


def roof_y(z):
    _, zf, zb, ym, pitch = ROOF
    return ym + (z - (zf + zb) / 2) * math.tan(math.radians(pitch))


def roof_pts(dy=0.0):
    x, zf, zb = ROOF[0], ROOF[1], ROOF[2]
    return [(-x, roof_y(zb) + dy, zb), (x, roof_y(zb) + dy, zb), (x, roof_y(zf) + dy, zf),
            (-x, roof_y(zf) + dy, zf)]


# ---- level 0 -------------------------------------------------------------------------------
def frame(p):
    x, z, h = PAD
    p.box('concrete', -x, x, 0.0, h, -z, z, open=('bottom',), su=2.0)
    fx = POST_X
    p.face('tin', [(-fx, FENCE_TOP, FENCE_Z), (fx, FENCE_TOP, FENCE_Z), (fx, h - 0.01, FENCE_Z),
                   (-fx, h - 0.01, FENCE_Z)], [(0, 0), (fx, 0), (fx, 0.6), (0, 0.6)])
    for s in (-1, 1):
        p.box('steel', s * POST_X - 0.04, s * POST_X + 0.04, h - 0.01, POST_TOP, FENCE_Z - 0.04,
              FENCE_Z + 0.04, open=('top', 'bottom'))
    p.box('steel', -POST_X + 0.04, POST_X - 0.04, 1.87, 1.93, FENCE_Z - 0.025, FENCE_Z + 0.025,
          open=('left', 'right'))
    # the collection-day board on the crossbar, in front of the fence
    p.box({'*': 'steel', 'back': 'board'}, -0.36, 0.36, 1.12, 1.98, 0.43, 0.46,
          crop={'back': (0, 0, 1, 1)})
    top = roof_pts()
    p.face_uv('roof', top, 0.4, 0.4)
    bot = roof_pts(-0.03)
    p.face('steel', [bot[3], bot[2], bot[1], bot[0]])


def bin_nodes(segments=8):
    x, z, r, h = BIN
    return [{'id': 'bin', 'op': 'cylinder', 'radius': r, 'height': h, 'segments': segments,
             'material': 'bin', 'faces': {'top': 'lid'},
             'transform': {'translate': [x, PAD[2] - 0.01 + h / 2, z]}}]


def crate_nodes():
    x, z = CRATE
    return [{'id': 'crate', 'op': 'box', 'size': [0.5, 0.3, 0.38], 'open': ['top', 'bottom'],
             'material': 'crate', 'transform': {'translate': [x, PAD[2] + 0.14, z]}},
            {'id': 'bottles', 'op': 'group', 'transform': {'translate': [x, PAD[2] - 0.01, z]},
             'children': [
                 {'id': 'bottle_a', 'op': 'instance', 'ref': 'bottle', 'material': 'glass_green',
                  'transform': {'translate': [-0.12, 0.0, -0.06]}},
                 {'id': 'bottle_b', 'op': 'instance', 'ref': 'bottle', 'material': 'glass_brown',
                  'transform': {'rotate': [0, 0, -14], 'translate': [0.1, 0.0, 0.05]}}]}]


def bag_nodes(net_segments=6):
    x, z = BAG
    return [{'id': 'bag', 'op': 'sphere', 'radius': 1, 'rings': 3, 'segments': 6, 'material': 'bag',
             'transform': {'scale': [0.36, 0.26, 0.3], 'translate': [x, PAD[2] + 0.18, z]}},
            {'id': 'net', 'op': 'lathe', 'segments': net_segments, 'caps': False, 'material': 'net',
             'profile': [[0.5, 0], [0.44, 0.26], [0.26, 0.46], [0, 0.56]],
             'transform': {'scale': [0.86, 1, 0.78], 'translate': [x, PAD[2] - 0.01, z]}}]


def crow_nodes():
    """The crow on the roof's front-left, looking down at the net."""
    z = -0.22
    return [{'id': 'crow', 'op': 'group',
             'transform': {'scale': [1.2, 1.2, 1.2], 'rotate': [0, -30, 0],
                           'translate': [-0.55, roof_y(z) + 0.005, z]},
             'children': [
                 {'id': 'body', 'op': 'sphere', 'radius': 1, 'rings': 3, 'segments': 5,
                  'material': 'crow',
                  'transform': {'scale': [0.075, 0.075, 0.14], 'rotate': [15, 0, 0],
                                'translate': [0, 0.07, 0]}},
                 {'id': 'head', 'op': 'sphere', 'radius': 0.06, 'rings': 2, 'segments': 4,
                  'material': 'crow', 'transform': {'rotate': [0, 45, 0], 'translate': [0, 0.16, -0.11]}},
                 {'id': 'beak', 'op': 'cone', 'radius': 0.028, 'height': 0.09, 'segments': 3,
                  'caps': False, 'material': 'beak',
                  'transform': {'rotate': [-90, 0, 0], 'translate': [0, 0.15, -0.19]}},
                 {'id': 'tail', 'op': 'mesh', 'material': 'crow_ds',
                  'vertices': [[-0.04, 0.1, 0.12], [0.04, 0.1, 0.12], [0.04, 0.05, 0.25],
                               [-0.04, 0.05, 0.25]], 'faces': [[0, 1, 2, 3]]}]}]


def level0():
    p = ap.Part('frame')
    frame(p)
    return [p.node()] + bin_nodes() + crate_nodes() + bag_nodes() + crow_nodes()


# ---- coarser levels -----------------------------------------------------------------------------
def level1():
    """From 20 m: the pad, the fence, posts as two faces, the board, the roof, the bin, the crate,
    the bag under its net."""
    p = ap.Part('station')
    x, z, h = PAD
    p.box('concrete', -x, x, 0.0, h, -z, z, open=('bottom',), su=2.0)
    fx = POST_X
    p.face('tin', [(-fx, FENCE_TOP, FENCE_Z), (fx, FENCE_TOP, FENCE_Z), (fx, h - 0.01, FENCE_Z),
                   (-fx, h - 0.01, FENCE_Z)], [(0, 0), (fx, 0), (fx, 0.6), (0, 0.6)])
    for s in (-1, 1):
        for zz, k in ((FENCE_Z - 0.045, 1), (FENCE_Z + 0.045, -1)):
            pts = [(s * fx - 0.04 * k, POST_TOP, zz), (s * fx + 0.04 * k, POST_TOP, zz),
                   (s * fx + 0.04 * k, h, zz), (s * fx - 0.04 * k, h, zz)]
            p.face('steel', pts)
    p.face('board', [(-0.36, 1.98, 0.43), (0.36, 1.98, 0.43), (0.36, 1.12, 0.43), (-0.36, 1.12, 0.43)],
           [(0, 0), (1, 0), (1, 1), (0, 1)])
    p.face_uv('roof', roof_pts(), 0.4, 0.4)
    bot = roof_pts(-0.03)
    p.face('steel', [bot[3], bot[2], bot[1], bot[0]])
    cx, cz = CRATE
    p.box('crate', cx - 0.25, cx + 0.25, h - 0.01, h + 0.29, cz - 0.19, cz + 0.19,
          open=('bottom', 'top'), crop={k: (0, 0, 1, 1) for k in ('left', 'right', 'back', 'front')})
    bx, bz = BAG
    net = {'id': 'net', 'op': 'lathe', 'segments': 5, 'material': 'bag', 'caps': False,
           'profile': [[0.46, 0], [0.3, 0.42], [0, 0.54]],
           'transform': {'scale': [0.86, 1, 0.78], 'translate': [bx, h - 0.01, bz]}}
    return [p.node()] + bin_nodes(6) + [net]


def level2():
    """From 45 m: the fence, the roof and the bin as boxes."""
    p = ap.Part('station')
    x, z, h = PAD
    fx = POST_X
    p.face('tin', [(-fx, FENCE_TOP, FENCE_Z), (fx, FENCE_TOP, FENCE_Z), (fx, 0.0, FENCE_Z),
                   (-fx, 0.0, FENCE_Z)], [(0, 0), (fx, 0), (fx, 0.65), (0, 0.65)])
    for s in (-1, 1):
        for zz, k in ((FENCE_Z - 0.045, 1), (FENCE_Z + 0.045, -1)):
            p.face('steel', [(s * fx - 0.05 * k, POST_TOP, zz), (s * fx + 0.05 * k, POST_TOP, zz),
                             (s * fx + 0.05 * k, 0.0, zz), (s * fx - 0.05 * k, 0.0, zz)])
    top = roof_pts()
    p.face_uv('roof', top, 0.4, 0.4)
    bot = roof_pts(-0.03)
    p.face('steel', [bot[3], bot[2], bot[1], bot[0]])
    bx, bz, r, bh = BIN
    p.box({'*': 'bin', 'top': 'steel'}, bx - r, bx + r, 0.0, h + bh, bz - r, bz + r,
          open=('bottom',), su=0.848, sv=0.7)
    return [p.node()]


# ---- collision ------------------------------------------------------------------------------
def collision():
    p = ap.Part('body')
    x, z, h = PAD
    ap.col_box(p, -x, x, 0.0, h, -z, z, open=('bottom',))
    ap.col_box(p, -POST_X - 0.04, POST_X + 0.04, h, roof_y(FENCE_Z) - 0.03, FENCE_Z - 0.1,
               FENCE_Z + 0.1, open=('bottom',))
    bx, bz, r, bh = BIN
    ap.col_box(p, bx - r, bx + r, h, h + bh, bz - r, bz + r, open=('bottom',))
    ap.col_box(p, -0.25, 1.05, h, h + 0.42, -0.45, 0.38, open=('bottom',))   # crate and bags
    # the roof: a slab 0.2 thick under its top face
    t, b = roof_pts(), roof_pts(-0.2)
    ap.col_quad(p, t[0], t[1], t[2], t[3])
    ap.col_quad(p, b[3], b[2], b[1], b[0])
    ap.col_quad(p, t[3], t[2], b[2], b[3])           # front edge
    ap.col_quad(p, t[1], t[0], b[0], b[1])           # back edge
    ap.col_quad(p, t[2], t[1], b[1], b[2])           # right (+X)
    ap.col_quad(p, t[0], t[3], b[3], b[0])           # left (-X)
    return [p]


# ---- recipe ---------------------------------------------------------------------------------
TOWN = '../town_alley_house_a/art/town_common.png'
CONCRETE = '../viaduct_span_16/art/concrete.png'
CRATE_TEXELS = ['2222222222222222', '1111111111111111', '1001100110011001', '1001100110011001',
                '1001100110011001', '1001100110011001', '1111111111111111', '2222222222222222']


def materials():
    def pal(c, **kw):
        return {'color': c, 'palette': True, **kw}
    return {
        'concrete': {'color': '#b4b0a6', 'tag': 'floor',
                     'texture': {'sheet': 'concrete', 'cell': 'wall', 'projection': 'box'}},
        'tin': {'color': '#9ea4a8', 'double_sided': True, 'tag': 'wall',
                'texture': {'sheet': 'town_common', 'cell': 'tin', 'projection': 'box'}},
        'roof': {'color': '#4f8f5a', 'tag': 'roof',
                 'texture': {'pattern': 'stripes', 'colors': ['#5a9a62', '#3d7448'],
                             'params': {'count': 8}, 'projection': 'box'}},
        'board': {'color': '#f2eedd', 'texture': {'sheet': 'art', 'cell': 'board', 'projection': 'fit'}},
        'bin': {'color': '#2b5fa8', 'texture': {'sheet': 'art', 'cell': 'bin', 'projection': 'cylindrical',
                                                 'scale': [0.848, 0.7], 'offset': [0.5, 0.5]}},
        'lid': {'color': '#2b5fa8', 'texture': {'sheet': 'art', 'cell': 'lid', 'projection': 'disc',
                                                 'axis': 'y'}},
        'crate': {'color': '#e8b923', 'double_sided': True,
                  'texture': {'texels': CRATE_TEXELS, 'colors': ['#000000', '#e8b923', '#c99a14'],
                              'clear': '#000000', 'projection': 'fit'}},
        'net': {'color': '#2f8a74', 'double_sided': True,
                'texture': {'pattern': 'lattice', 'colors': ['#2f8a74', '#000000'], 'clear': '#000000',
                            'params': {'count': 2, 'bar': 1, 'diagonal': True},
                            'projection': 'cylindrical', 'scale': [0.3, 0.3]}},
        'steel': pal('#7d848c'),
        'glass_green': pal('#3f8f4f'),
        'glass_brown': pal('#7a4a22'),
        'bag': pal('#e4ecef', smooth=True),
        'crow': pal('#23263a', smooth=True),
        'crow_ds': pal('#23263a', double_sided=True),
        'beak': pal('#3a3c44'),
    }


def recipe():
    mats = materials()
    lv0 = level0()
    return {
        'format': 'mei-asset', 'version': 1, 'name': 'recycling_station',
        'budget': {'triangles': 200},
        'sheets': {'art': {'image': 'art/sheet.png'}, 'town_common': {'image': TOWN},
                   'concrete': {'image': CONCRETE}},
        'materials': mats,
        'lighting': ap.LIGHT,
        'verification': ap.POLICY,
        'prototypes': {'bottle': {'id': 'bottle', 'op': 'lathe', 'segments': 4, 'caps': False,
                                  'profile': [[0.04, 0], [0.04, 0.2], [0.0, 0.31]]}},
        'nodes': lv0,
        'lod': {'levels': [{'distance': 20, 'nodes': level1()},
                           {'distance': 45, 'nodes': level2()}], 'cull': 80, 'band': 2},
    }


def scale_textures(r):
    """Repeats in metres for the projected textures (Part faces carry their own UVs)."""
    r['materials']['concrete']['texture']['scale'] = [2.0, 2.0]
    r['materials']['tin']['texture']['scale'] = [2.0, 2.0]
    r['materials']['roof']['texture']['scale'] = [0.4, 0.4]
    return r


def main():
    ap.write(HERE / 'recycling_station.asset.json', scale_textures(recipe()))
    ap.write(HERE / 'recycling_station_col.asset.json',
             ap.col_recipe('recycling_station_col', collision()))


if __name__ == '__main__':
    main()
