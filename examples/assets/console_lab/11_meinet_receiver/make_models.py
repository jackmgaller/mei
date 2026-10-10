#!/usr/bin/env python3
"""Write the MeiNet Receiver's two recipes: console.asset.json and controller.asset.json.

Metres, real size, Y up, facing -Z. The shells are explicit meshes so that each face can
carry its own printed panel from art/sheet.png (make_art.py draws it). Run from anywhere.
"""
import json, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = lambda v: round(v, 5)


# ---- mesh helpers -----------------------------------------------------------------------------
class Mesh:
    def __init__(self):
        self.v, self.f, self.m, self.look = [], [], [], {}

    def vid(self, p):
        p = tuple(R(c) for c in p)
        if p not in self.look:
            self.look[p] = len(self.v)
            self.v.append(list(p))
        return self.look[p]

    def poly(self, pts, mat, out):
        """Add a planar polygon, wound so that its normal points along `out`."""
        n = [0.0, 0.0, 0.0]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            n[0] += (a[1] - b[1]) * (a[2] + b[2])
            n[1] += (a[2] - b[2]) * (a[0] + b[0])
            n[2] += (a[0] - b[0]) * (a[1] + b[1])
        # Newell gives the normal of a counterclockwise loop; outward winding is the reverse
        # convention here: (b-a)x(c-a) points out for the kit, which is Newell's direction.
        if sum(x * y for x, y in zip(n, out)) < 0:
            pts = pts[::-1]
        self.f.append([self.vid(p) for p in pts])
        self.m.append(mat)

    def node(self, id_, **extra):
        d = {'id': id_, 'op': 'mesh', 'vertices': self.v, 'faces': self.f,
             'face_materials': self.m}
        d.update(extra)
        return d


def frame(id_, x0, x1, y0, y1, z, border, proud, sink, mat):
    """A rectangular bezel standing proud of a -Z-facing wall at depth z (the hole x0..x1,
    y0..y1), its sides running `sink` into the wall."""
    m = Mesh()
    zf, zb = z - proud, z + sink
    o = [(x0 - border, y0 - border), (x1 + border, y0 - border), (x1 + border, y1 + border),
         (x0 - border, y1 + border)]
    i = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for k in range(4):
        a, b = o[k], o[(k + 1) % 4]
        c, d = i[(k + 1) % 4], i[k]
        m.poly([(a[0], a[1], zf), (b[0], b[1], zf), (c[0], c[1], zf), (d[0], d[1], zf)], mat, (0, 0, -1))
        # outer side: normal away from the centre
        mid = ((a[0] + b[0]) / 2 - (x0 + x1) / 2, (a[1] + b[1]) / 2 - (y0 + y1) / 2)
        m.poly([(a[0], a[1], zf), (b[0], b[1], zf), (b[0], b[1], zb), (a[0], a[1], zb)], mat,
               (mid[0], mid[1], 0))
        m.poly([(d[0], d[1], zf), (c[0], c[1], zf), (c[0], c[1], zb), (d[0], d[1], zb)], mat,
               (-mid[0], -mid[1], 0))
    return m.node(id_)


def hframe(id_, x0, x1, z0, z1, y, border, proud, sink, mat):
    """The same bezel on a +Y-facing top at height y (hole x0..x1, z0..z1)."""
    n = frame(id_, x0, x1, z0, z1, 0, border, proud, sink, mat)
    # frame() builds in XY facing -Z; turn it to face +Y: (x, y, z) -> (x, -z, y)
    n['vertices'] = [[x, R(-zz + y), yy] for x, yy, zz in n['vertices']]
    return n


def tr(t=None, r=None, s=None):
    d = {}
    if s: d['scale'] = s
    if r: d['rotate'] = r
    if t: d['translate'] = t
    return {'transform': d} if d else {}


def node(id_, op, mat=None, t=None, r=None, s=None, **kw):
    d = {'id': id_, 'op': op}
    d.update(kw)
    if mat: d['material'] = mat
    d.update(tr(t, r, s))
    return d


def tex(cell, bits=8, proj='fit', **kw):
    d = {'sheet': 'art', 'cell': cell, 'bits': bits, 'projection': proj}
    d.update(kw)
    return d


VERIFY = {'required': True, 'depth': True, 'perspective': True}
SHEETS = {'art': {'image': 'art/sheet.png'}}

# ==== console ==================================================================================
W = 0.30
HX = W / 2
# side profile (z, y), front bottom first, clockwise with z to the right and y up
PROFILE = [(-0.110, 0.008), (-0.110, 0.052), (-0.104, 0.058), (-0.024, 0.058),
           (-0.014, 0.072), (0.104, 0.072), (0.110, 0.066), (0.110, 0.008)]
EDGE_MAT = ['fascia', 'trim', 'deck', 'riser', 'lid', 'trim', 'rear', 'under']


def console_body():
    m = Mesh()
    n = len(PROFILE)
    for k in range(n):
        (za, ya), (zb, yb) = PROFILE[k], PROFILE[(k + 1) % n]
        out = (0, zb - za, -(yb - ya))           # clockwise profile: outward (−dy, dz) in (z, y)
        m.poly([(-HX, ya, za), (HX, ya, za), (HX, yb, zb), (-HX, yb, zb)], EDGE_MAT[k], out)
    for sx in (-1, 1):
        m.poly([(sx * HX, y, z) for z, y in PROFILE], 'side', (sx, 0, 0))
    return m.node('body')


def cart():
    """The cartridge standing in the slot: a box whose front face carries the label."""
    m = Mesh()
    x0, x1, y0, y1, z0, z1 = -0.0855, 0.0255, 0.064, 0.110, 0.0245, 0.0395
    c = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    P = lambda i, j, k: (x1 if i else x0, y1 if j else y0, z1 if k else z0)
    m.poly([P(0, 1, 0), P(1, 1, 0), P(1, 0, 0), P(0, 0, 0)], 'cart_label', (0, 0, -1))
    m.poly([P(0, 1, 1), P(1, 1, 1), P(1, 0, 1), P(0, 0, 1)], 'cart', (0, 0, 1))
    m.poly([P(0, 1, 0), P(1, 1, 0), P(1, 1, 1), P(0, 1, 1)], 'cart', (0, 1, 0))
    m.poly([P(0, 0, 0), P(0, 1, 0), P(0, 1, 1), P(0, 0, 1)], 'cart', (-1, 0, 0))
    m.poly([P(1, 0, 0), P(1, 1, 0), P(1, 1, 1), P(1, 0, 1)], 'cart', (1, 0, 0))
    return m.node('cartridge')


def fastext_key(id_, x, mat):
    return node(id_, 'box', mat, t=[x, 0.0595, -0.068], size=[0.017, 0.006, 0.0085],
                open=['bottom'])


ANT_BASE = [0.125, 0.072, 0.086]


def antenna():
    kids = [node('swivel', 'cylinder', 'chrome_d', t=[0, 0.004, 0], radius=0.0085, height=0.010,
                 segments=10),
            node('joint', 'sphere', 'chrome', t=[0, 0.012, 0], radius=0.0055, rings=4, segments=8)]
    rods = [node('rod1', 'cylinder', 'chrome', t=[0, 0.012 + 0.045, 0], radius=0.0032, height=0.090, segments=6),
            node('collar1', 'cylinder', 'chrome_d', t=[0, 0.012 + 0.089, 0], radius=0.0040, height=0.006, segments=6),
            node('rod2', 'cylinder', 'chrome', t=[0, 0.012 + 0.122, 0], radius=0.0024, height=0.064, segments=6),
            node('tip', 'sphere', 'sun', t=[0, 0.012 + 0.156, 0], radius=0.0042, rings=4, segments=8)]
    kids.append({'id': 'mast', 'op': 'group', 'children': rods,
                 'transform': {'pivot': [0, 0.012, 0], 'rotate': [30, 0, -14]}})
    return {'id': 'antenna', 'op': 'group', 'children': kids, 'transform': {'translate': ANT_BASE}}


def console():
    nodes = [console_body()]
    nodes.append({'id': 'feet', 'op': 'group', 'children': [
        node('foot', 'cylinder', 'rubber', t=[0.118, 0.005, -0.082], radius=0.010, height=0.010, segments=8)],
        'modifiers': [{'op': 'mirror', 'axis': 'x'}, {'op': 'mirror', 'axis': 'z'}]})
    # fascia: VFD window, port bezels, memory card bezels, tuning dial
    nodes.append(node('vfd', 'box', 'vfd', t=[0.007, 0.0395, -0.1105], size=[0.130, 0.019, 0.004],
                      open=['front']))
    for i, x in enumerate((-0.124, -0.088)):
        nodes.append(frame('port_%d' % (i + 1), x - 0.0125, x + 0.0125, 0.0115, 0.0225, -0.110,
                           0.0018, 0.003, 0.004, 'bezel'))
    for i, x in enumerate((-0.024, 0.040)):
        nodes.append(frame('card_%d' % (i + 1), x - 0.0245, x + 0.0245, 0.0148, 0.0192, -0.110,
                           0.0016, 0.002, 0.004, 'bezel'))
    nodes.append(node('dial_skirt', 'cylinder', 'knob_side', t=[0.112, 0.030, -0.1115],
                      r=[-90, 0, 0], radius=0.0155, height=0.005, segments=20))
    nodes.append(node('dial', 'cylinder', 'knob', t=[0.112, 0.030, -0.118], r=[-90, 0, 0],
                      radius=0.0125, height=0.012, segments=20))
    # deck: power (sun), reset (moon), the four Fastext page keys
    nodes.append(node('power', 'cylinder', 'power_cap', t=[-0.122, 0.0605, -0.066], radius=0.0105,
                      height=0.007, segments=16))
    nodes.append(node('reset', 'cylinder', 'reset_cap', t=[-0.092, 0.0600, -0.066], radius=0.0078,
                      height=0.006, segments=14))
    for x, mat in ((0.050, 'key_red'), (0.074, 'key_green'), (0.098, 'key_yellow'), (0.122, 'key_cyan')):
        nodes.append(fastext_key('key_' + mat[4:], x, mat))
    # lid: slot bezel, the cart in it, the antenna
    nodes.append(hframe('slot_bezel', -0.0935, 0.0335, 0.0225, 0.0415, 0.072, 0.004, 0.0035, 0.004, 'bezel'))
    nodes.append(cart())
    nodes.append(antenna())
    # rear: the two F connectors
    for i, x in enumerate((0.100, 0.070)):
        nodes.append({'id': 'f_conn_%d' % (i + 1), 'op': 'group', 'children': [
            node('nut', 'cylinder', 'chrome_d', t=[0, 0, 0.004], r=[90, 0, 0], radius=0.0055,
                 height=0.010, segments=6),
            node('pin', 'cylinder', 'chrome', t=[0, 0, 0.0125], r=[90, 0, 0], radius=0.0035,
                 height=0.005, segments=6)],
            'transform': {'translate': [x, 0.034, 0.110]}})
    mats = {
        'fascia': {'color': '#16191f', 'texture': tex('fascia')},
        'trim': {'color': '#2f4c7a'},
        'deck': {'color': '#cdd0d5', 'texture': tex('deck')},
        'riser': {'color': '#16191f', 'class': 'emissive', 'texture': tex('riser')},
        'lid': {'color': '#2f4c7a', 'texture': tex('lid')},
        'rear': {'color': '#2f4c7a', 'texture': tex('rear', bits=4)},
        'under': {'color': '#1f3458'},
        'side': {'color': '#2f4c7a'},
        'rubber': {'color': '#202228'},
        'vfd': {'color': '#06140f', 'class': 'emissive', 'texture': tex('vfd')},
        'bezel': {'color': '#2b2f37'},
        'knob_side': {'color': '#3a3e46'},
        'knob': {'color': '#767c86', 'texture': tex('knob', proj='disc', axis='y')},
        'power_cap': {'color': '#f7a840', 'texture': tex('pwr', proj='disc', axis='y')},
        'reset_cap': {'color': '#aac4ec', 'texture': tex('rst', proj='disc', axis='y')},
        'key_red': {'color': '#e2342c'}, 'key_green': {'color': '#34c452'},
        'key_yellow': {'color': '#f6d828'}, 'key_cyan': {'color': '#28aaec'},
        'cart': {'color': '#80868f'},
        'cart_label': {'color': '#80868f', 'texture': tex('label')},
        'chrome': {'color': '#d8dde4', 'smooth': True},
        'chrome_d': {'color': '#8a9099'},
        'sun': {'color': '#f7a840', 'smooth': True},
    }
    return {'format': 'mei-asset', 'version': 1, 'name': 'meinet_receiver',
            'budget': {'vertices': 1200, 'triangles': 1200}, 'sheets': SHEETS,
            'materials': mats, 'lighting': {'direction': [-0.45, 0.85, -0.4], 'ambient': 0.5},
            'verification': VERIFY, 'nodes': nodes}


# ==== controller ================================================================================
HALF = [(0.0, 0.045), (0.030, 0.046), (0.052, 0.044), (0.066, 0.038), (0.074, 0.027),
        (0.077, 0.011), (0.077, -0.007), (0.074, -0.025), (0.068, -0.043), (0.060, -0.057),
        (0.049, -0.066), (0.037, -0.066), (0.029, -0.058), (0.024, -0.042), (0.016, -0.030),
        (0.0, -0.027)]
OUTLINE = HALF + [(-x, z) for x, z in reversed(HALF[1:-1])]   # clockwise from above


def offset(pts, d):
    """Move each point of a closed outline outward by d (negative: inward)."""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    s = 1 if area < 0 else -1
    out = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        e1 = (b[0] - a[0], b[1] - a[1]); e2 = (c[0] - b[0], c[1] - b[1])
        n1 = (e1[1], -e1[0]); n2 = (e2[1], -e2[0])
        l1 = math.hypot(*n1); l2 = math.hypot(*n2)
        nx, nz = n1[0] / l1 + n2[0] / l2, n1[1] / l1 + n2[1] / l2
        ln = math.hypot(nx, nz)
        out.append((b[0] - s * d * nx / ln, b[1] - s * d * nz / ln))
    return out


def shell():
    m = Mesh()
    rings = [(0.000, offset(OUTLINE, -0.004)), (0.006, OUTLINE), (0.021, OUTLINE),
             (0.026, offset(OUTLINE, -0.0035))]
    n = len(OUTLINE)
    for (ya, a), (yb, b) in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            e = (a[j][0] - a[i][0], a[j][1] - a[i][1])
            # outward in the XZ plane: perpendicular to the edge, away from the inside
            out = (-e[1], 0, e[0])
            q = [(a[i][0], ya, a[i][1]), (a[j][0], ya, a[j][1]), (b[j][0], yb, b[j][1]),
                 (b[i][0], yb, b[i][1])]
            m.poly([q[0], q[1], q[2]], 'shell', out)       # offset rings: not planar quads
            m.poly([q[0], q[2], q[3]], 'shell', out)
    m.poly([(x, 0.0, z) for x, z in rings[0][1]], 'shell_d', (0, -1, 0))
    m.poly([(x, 0.026, z) for x, z in rings[-1][1]], 'face', (0, 1, 0))
    return m


def controller():
    sh = shell()
    # check the side normals point out (outline is clockwise seen from above with z up)
    nodes = [sh.node('shell')]
    nodes.append({'id': 'grips', 'op': 'group', 'children': [
        node('grip', 'sphere', 'shell', t=[0.051, 0.006, -0.046], s=[0.9, 0.7, 1.15], radius=0.022,
             rings=4, segments=8, r=[0, 20, 0])], 'modifiers': [{'op': 'mirror', 'axis': 'x'}]})
    top = 0.026
    # d-pad: a cross, extruded, lying flat
    a, b = 0.0135, 0.0045
    cross = [(-b, a), (b, a), (b, b), (a, b), (a, -b), (b, -b), (b, -a), (-b, -a), (-b, -b),
             (-a, -b), (-a, b), (-b, b)]
    nodes.append(node('dpad', 'extrude', 'dpad', t=[-0.050, top + 0.0012, 0.012], r=[90, 0, 0],
                      points=cross, depth=0.006))
    nodes.append(node('dpad_pivot', 'cylinder', 'dpad', t=[-0.050, top + 0.0035, 0.012],
                      radius=0.0035, height=0.002, segments=8))
    # face buttons in a diamond: Y left (red), X top (green), A right (yellow), B bottom (cyan)
    cx, cz, s = 0.050, 0.012, 0.0125
    for n, dx, dz in (('y', -s, 0), ('x', 0, s), ('a', s, 0), ('b', 0, -s)):
        nodes.append(node('btn_' + n, 'cylinder', 'btn_' + n, t=[cx + dx, top + 0.0005, cz + dz],
                          radius=0.0058, height=0.007, segments=10))
    # analog stick: collar, shaft, cap
    sx, sz = -0.040, -0.030
    nodes.append(node('stick_collar', 'cylinder', 'dpad', t=[sx, top + 0.0005, sz], radius=0.0115,
                      height=0.004, segments=12))
    nodes.append(node('stick_shaft', 'cylinder', 'dpad', t=[sx, top + 0.006, sz], radius=0.0045,
                      height=0.008, segments=8))
    nodes.append(node('stick_cap', 'cylinder', 'stick', t=[sx, top + 0.0115, sz], radius=0.0095,
                      height=0.004, segments=12))
    # select and start: rubber pills
    for n, x in (('select', -0.011), ('start', 0.011)):
        nodes.append(node(n, 'cylinder', 'rubber', t=[x, top + 0.0003, -0.0015], s=[2.0, 1, 1],
                          r=[0, -20 if x < 0 else 20, 0], radius=0.0028, height=0.0035, segments=8))
    # L and R on the far corners
    sh_pts = [(-0.017, -0.004), (0.017, -0.004), (0.015, 0.004), (-0.015, 0.004)]
    nodes.append({'id': 'shoulders', 'op': 'group', 'children': [
        node('shoulder', 'extrude', 'shoulder', t=[0.050, 0.0225, 0.0425], r=[0, 20, 0],
             points=sh_pts, depth=0.010)], 'modifiers': [{'op': 'mirror', 'axis': 'x'}]})
    nodes.append(node('cable_relief', 'cylinder', 'shell_d', t=[0, 0.013, 0.050], r=[90, 0, 0],
                      radius=0.0045, height=0.012, segments=8))
    mats = {
        'shell': {'color': '#2f4c7a'},
        'shell_d': {'color': '#1f3458'},
        'face': {'color': '#cdd0d5', 'texture': tex('pad')},
        'dpad': {'color': '#2b2f37'},
        'shoulder': {'color': '#3a3e46'},
        'rubber': {'color': '#5a606a'},
        'stick': {'color': '#464c56', 'texture': tex('stick', proj='disc', axis='y')},
        'btn_a': {'color': '#f6d828', 'texture': tex('btn_a', proj='disc', axis='y')},
        'btn_b': {'color': '#28aaec', 'texture': tex('btn_b', proj='disc', axis='y')},
        'btn_x': {'color': '#34c452', 'texture': tex('btn_x', proj='disc', axis='y')},
        'btn_y': {'color': '#e2342c', 'texture': tex('btn_y', proj='disc', axis='y')},
    }
    return {'format': 'mei-asset', 'version': 1, 'name': 'meinet_pad',
            'budget': {'vertices': 800, 'triangles': 800}, 'sheets': SHEETS,
            'materials': mats, 'lighting': {'direction': [-0.45, 0.85, -0.4], 'ambient': 0.5},
            'verification': VERIFY, 'nodes': nodes}


for name, rec in (('console', console()), ('controller', controller())):
    (HERE / f'{name}.asset.json').write_text(json.dumps(rec, indent=1) + '\n')
    print('wrote', name)
