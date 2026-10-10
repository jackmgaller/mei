#!/usr/bin/env python3
"""Write console.asset.json and controller.asset.json for look 05, Clear Smoke.

The shells are explicit meshes made here from rounded outlines stacked in height. The
translucent smoke plastic is a screen-door stipple: a cutout texture (half its texels holes)
on double-sided faces, so the board, chips and cartridge inside show through, as Saturn-era
mesh transparency did. Run make_art.py first for art/clear_smoke.png.

    python3 examples/assets/console_lab/05_clear_smoke/make_models.py
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def r6(v):
    return round(v, 6)


# ---------------------------------------------------------------- outlines (x, z), z = back

def area2(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts)))


def cw(pts):
    """Clockwise as seen from above with +Z up the page (signed area negative)."""
    return pts if area2(pts) < 0 else pts[::-1]


def offset_poly(poly, t):
    """Move every edge of a clockwise polygon inward by t (mitred corners)."""
    n = len(poly)
    lines = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ex, ez = b[0] - a[0], b[1] - a[1]
        L = math.hypot(ex, ez)
        nx, nz = ez / L, -ex / L          # right of travel: inside for a clockwise polygon
        lines.append(((a[0] + nx * t, a[1] + nz * t), (ex / L, ez / L)))
    out = []
    for i in range(n):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        den = d1[0] * d2[1] - d1[1] * d2[0]
        s = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        out.append((p1[0] + d1[0] * s, p1[1] + d1[1] * s))
    return out


def fillet(poly, radii, seg):
    """Round each corner of a polygon with its radius, seg segments an arc."""
    n = len(poly)
    out = []
    for i in range(n):
        v, p, q = poly[i], poly[i - 1], poly[(i + 1) % n]
        r = radii[i]
        if r <= 0:
            out.extend([v] * (seg + 1))
            continue
        u1 = (p[0] - v[0], p[1] - v[1]); l1 = math.hypot(*u1); u1 = (u1[0] / l1, u1[1] / l1)
        u2 = (q[0] - v[0], q[1] - v[1]); l2 = math.hypot(*u2); u2 = (u2[0] / l2, u2[1] / l2)
        half = math.acos(max(-1, min(1, u1[0] * u2[0] + u1[1] * u2[1]))) / 2
        d = r / math.tan(half)
        bis = (u1[0] + u2[0], u1[1] + u2[1]); lb = math.hypot(*bis); bis = (bis[0] / lb, bis[1] / lb)
        c = (v[0] + bis[0] * r / math.sin(half), v[1] + bis[1] * r / math.sin(half))
        t1 = (v[0] + u1[0] * d, v[1] + u1[1] * d)
        t2 = (v[0] + u2[0] * d, v[1] + u2[1] * d)
        a1 = math.atan2(t1[1] - c[1], t1[0] - c[0])
        a2 = math.atan2(t2[1] - c[1], t2[0] - c[0])
        sw = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        for k in range(seg + 1):
            a = a1 + sw * k / seg
            out.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a)))
    return out


def rounded_outline(sharp, radii, seg):
    """outline(inset): the filleted polygon moved inward by inset, the same point count."""
    sharp = cw(sharp)
    convex = []
    n = len(sharp)
    for i in range(n):
        p, v, q = sharp[i - 1], sharp[i], sharp[(i + 1) % n]
        cross = (v[0] - p[0]) * (q[1] - v[1]) - (v[1] - p[1]) * (q[0] - v[0])
        convex.append(cross < 0)          # clockwise: right turns are convex

    def outline(inset):
        poly = offset_poly(sharp, inset) if inset else sharp
        rr = [r - inset if cv else r + inset for r, cv in zip(radii, convex)]
        return fillet(poly, rr, seg)
    return outline


def rrect(w, d, r, seg, cx=0.0, cz=0.0):
    sharp = [(cx - w / 2, cz + d / 2), (cx + w / 2, cz + d / 2),
             (cx + w / 2, cz - d / 2), (cx - w / 2, cz - d / 2)]
    return rounded_outline(sharp, [r] * 4, seg)


# ---------------------------------------------------------------- meshes

class Mesh:
    def __init__(self):
        self.v, self.f, self.m = [], [], []

    def vert(self, p):
        self.v.append([r6(p[0]), r6(p[1]), r6(p[2])])
        return len(self.v) - 1

    def face(self, idx, mat):
        self.f.append(list(idx))
        self.m.append(mat)

    def node(self, nid, uvs=None):
        mats = sorted(set(self.m))
        n = {'id': nid, 'op': 'mesh', 'vertices': self.v, 'faces': self.f}
        if len(mats) == 1:
            n['material'] = mats[0]
        else:
            n['face_materials'] = self.m
        return n


def ear_clip(pts):
    """Triangles (index triples) of a simple clockwise polygon in (x, z), clockwise too."""
    idx = list(range(len(pts)))
    tris = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if cross(a, b, c) >= -1e-12:   # not a clockwise (convex) corner
                continue
            ok = True
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                p = pts[j]
                if cross(a, b, p) < 0 and cross(b, c, p) < 0 and cross(c, a, p) < 0:
                    ok = False
                    break
            if ok:
                tris.append((i0, i1, i2))
                idx.pop(k)
                break
    tris.append(tuple(idx))
    return tris


def dedupe(pts):
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-7:
            out.append(p)
    if math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-7:
        out.pop()
    return out


def stack(mesh, outline, levels, top=None, bottom=None, ydef=None):
    """Walls between rings outline(inset) at each (y, inset, wall material) level (the wall
    material of a level is that of the band above it), and optional caps. ydef(x, z, level)
    moves a ring's vertices in y; a deformed cap is triangulated here."""
    rings = []
    for li, lv in enumerate(levels):
        y, ins = lv[0], lv[1]
        pts = dedupe(outline(ins))
        ring = []
        for (x, z) in pts:
            yy = y + (ydef(x, z, li) if ydef else 0.0)
            ring.append(mesh.vert((x, yy, z)))
        rings.append((ring, pts))
    n = len(rings[0][0])
    assert all(len(r[0]) == n for r in rings), [len(r[0]) for r in rings]
    for li in range(len(rings) - 1):
        lo, hi = rings[li][0], rings[li + 1][0]
        mat = levels[li][2]
        for j in range(n):
            k = (j + 1) % n
            mesh.face((lo[j], lo[k], hi[k]), mat)
            mesh.face((lo[j], hi[k], hi[j]), mat)
    for cap, ring, flip in ((top, rings[-1], False), (bottom, rings[0], True)):
        if not cap:
            continue
        idx, pts = ring
        ys = [mesh.v[i][1] for i in idx]
        if max(ys) - min(ys) < 1e-9:
            mesh.face(idx[::-1] if flip else idx, cap)
        else:
            for t in ear_clip(pts):
                tri = [idx[t[0]], idx[t[1]], idx[t[2]]]
                mesh.face(tri[::-1] if flip else tri, cap)
    return rings


def box(mesh, c, s, mats, skip=()):
    """An axis-aligned box: mats by side name (top, bottom, left, right, front = -Z, back = +Z)
    or one material for all."""
    x0, x1 = c[0] - s[0] / 2, c[0] + s[0] / 2
    y0, y1 = c[1] - s[1] / 2, c[1] + s[1] / 2
    z0, z1 = c[2] - s[2] / 2, c[2] + s[2] / 2
    P = lambda x, y, z: mesh.vert((x, y, z))
    sides = {
        'top': [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)],
        'bottom': [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
        'front': [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)],
        'back': [(x1, y1, z1), (x0, y1, z1), (x0, y0, z1), (x1, y0, z1)],
        'left': [(x0, y1, z1), (x0, y1, z0), (x0, y0, z0), (x0, y0, z1)],
        'right': [(x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (x1, y0, z0)],
    }
    cache = {}
    for name, quad in sides.items():
        if name in skip:
            continue
        ids = []
        for p in quad:
            if p not in cache:
                cache[p] = P(*p)
            ids.append(cache[p])
        mesh.face(ids, mats if isinstance(mats, str) else mats[name])


def cyl(nid, mat, r, h, c, seg=8, axis='y', caps=True):
    rot = {'y': [0, 0, 0], 'z': [90, 0, 0], 'x': [0, 0, 90]}[axis]
    n = {'id': nid, 'op': 'cylinder', 'radius': r, 'height': h, 'segments': seg, 'material': mat,
         'transform': {'translate': [r6(c[0]), r6(c[1]), r6(c[2])], 'rotate': rot}}
    if not caps:
        n['caps'] = False
    return n


def puck(nid, mat, r, h, c, seg=8):
    """A cylinder without its bottom cap, for buttons and rings that stand in a surface."""
    m = Mesh()
    circle = lambda ins: [(c[0] + r * math.cos(-2 * math.pi * k / seg), c[2] + r * math.sin(-2 * math.pi * k / seg))
                          for k in range(seg)]
    stack(m, circle, [(c[1] - h / 2, 0.0, mat), (c[1] + h / 2, 0.0, None)], top=mat)
    return m.node(nid)


def bx(nid, mat, size, c, open_=None, rot=None):
    n = {'id': nid, 'op': 'box', 'size': [r6(s) for s in size], 'material': mat,
         'transform': {'translate': [r6(v) for v in c]}}
    if rot:
        n['transform']['rotate'] = rot
    if open_:
        n['open'] = open_
    return n


# ---------------------------------------------------------------- materials

# 0 a hole, 1 smoke, 2 a glint: half the texels clear
STIPPLE_HI = ['10101010', '01010101', '10101010', '01020101'] * 2


def smoke(scale, colours=('#000000', '#5f6774', '#97a0ad'), rows=STIPPLE_HI):
    return {'color': colours[1], 'double_sided': True,
            'texture': {'texels': rows, 'colors': list(colours), 'clear': '#000000',
                        'projection': 'box', 'scale': [scale, scale]}}


def glass_top(cell):
    return {'color': '#5f6774', 'double_sided': True,
            'texture': {'sheet': 'art', 'cell': cell, 'projection': 'fit'}}


def sheet_tex(cell, bits=8):
    return {'sheet': 'art', 'cell': cell, 'bits': bits, 'projection': 'fit'}


COMMON_MATERIALS = {
    'tray': {'color': '#2c3038'},
    'shield': {'color': '#30343a'},
    'rim': {'color': '#737b88'},
    'seam': {'color': '#1c1f24'},
    'black': {'color': '#17181b'},
    'chip': {'color': '#202125'},
    'alu': {'color': '#aab2bc'},
    'silver': {'color': '#c9ced6'},
    'gold': {'color': '#c9a44c'},
    'connector': {'color': '#4a3a26'},
    'sun': {'color': '#f0a040'},
    'moon': {'color': '#a8c8f0'},
    'led': {'color': '#ff7a2a', 'class': 'emissive'},
    'logo': {'color': '#16181c', 'texture': sheet_tex('logo')},
}


def recipe(name, budget, materials, nodes, far):
    return {
        'format': 'mei-asset', 'version': 1, 'name': name,
        'budget': budget,
        'sheets': {'art': {'image': 'art/clear_smoke.png'}},
        'materials': materials,
        'lighting': {'direction': [-0.4, 0.85, -0.35], 'ambient': 0.5},
        'verification': {'required': True, 'depth': True, 'perspective': True},
        'nodes': nodes,
    }


# ---------------------------------------------------------------- the console

def console():
    W, D, R = 0.300, 0.220, 0.026
    SEG = 4
    body = rrect(W, D, R, SEG)
    Y_PCB = 0.031
    SLOPE = 0.07                       # the top rises 15 mm from front to back: a low wedge

    def top_y(z, base=0.062):
        return base + SLOPE * z

    def wedge(levels_from):
        return lambda x, z, li: SLOPE * z if li >= levels_from else 0.0

    nodes = []

    # the board on a metal shield tray, inside the clear case; its top is the circuit board
    m = Mesh()
    stack(m, body, [(0.003, 0.0045, 'shield'), (Y_PCB, 0.0045, None)], top='pcb', bottom='shield')
    nodes.append(m.node('board'))

    # the clear case: a smoke base, a dark seam at the board, smoke walls, a denser rounded
    # rim, a smoke top that slopes up toward the back
    m = Mesh()
    stack(m, body, [(0.0, 0.006, 'shell_lo'), (0.005, 0.0015, 'shell_lo'), (0.010, 0.0, 'shell_lo'),
                    (Y_PCB - 0.0012, 0.0, 'seam'), (Y_PCB + 0.0012, 0.0, 'shell'),
                    (0.054, 0.0015, 'rim'), (0.062, 0.009, None)],
          top='top_console', bottom='tray', ydef=wedge(5))
    nodes.append(m.node('shell'))

    # the raised cartridge bridge at the back, clear too, its top level
    DZ0, DZ1 = 0.002, 0.100
    deck = rrect(0.204, DZ1 - DZ0, 0.018, 3, cz=(DZ0 + DZ1) / 2)
    Y_DECK = 0.090
    m = Mesh()
    stack(m, deck, [(0.062 - 0.0015, 0.0, 'shell'), (Y_DECK - 0.006, 0.0, 'rim'),
                    (Y_DECK, 0.006, None)], top='top_deck',
          ydef=lambda x, z, li: SLOPE * z if li == 0 else 0.0)
    nodes.append(m.node('deck'))
    CZ = 0.056                         # the slot's centre line

    # the logo on the bridge's front face, where the front camera sees it
    m = Mesh()
    box(m, (0, 0.0738, DZ0 - 0.0002), (0.058, 0.0218, 0.0024),
        {'top': 'black', 'bottom': 'black', 'left': 'black', 'right': 'black', 'front': 'logo', 'back': 'black'})
    nodes.append(m.node('badge'))

    # the cartridge slot: a dark frame on the bridge and the opening around the cart
    m = Mesh()
    box(m, (0, Y_DECK + 0.0005, CZ), (0.128, 0.004, 0.034), 'seam')
    box(m, (0, Y_DECK + 0.0012, CZ), (0.110, 0.004, 0.024), 'black')
    nodes.append(m.node('slot'))

    # the cartridge in the slot: charcoal, a grip lip, the label facing the front
    CART_T, CART_W = 0.018, 0.100
    cart_bottom, cart_top = 0.036, 0.130
    pts = [(-CART_W / 2, cart_bottom), (CART_W / 2, cart_bottom), (CART_W / 2, cart_top - 0.006),
           (CART_W / 2 - 0.006, cart_top), (-CART_W / 2 + 0.006, cart_top), (-CART_W / 2, cart_top - 0.006)]
    nodes.append({'id': 'cart', 'op': 'extrude', 'points': [[r6(a), r6(b)] for a, b in pts],
                  'depth': CART_T, 'material': 'cart',
                  'transform': {'translate': [0, 0, CZ]}})
    m = Mesh()
    box(m, (0, 0.110, CZ - CART_T / 2 - 0.0004), (0.074, 0.034, 0.0016),
        {'top': 'cart', 'bottom': 'cart', 'left': 'cart', 'right': 'cart', 'front': 'label', 'back': 'cart'})
    nodes.append(m.node('cart_label'))
    nodes.append(bx('cart_grip', 'cart_dark', (0.070, 0.004, CART_T + 0.003), (0, cart_top - 0.010, CZ), open_=['bottom']))

    # power (the sun) and reset (the moon) on the sloping front of the top
    tilt = [-math.degrees(math.atan(SLOPE)), 0, 0]
    PZ = -0.070
    ty = top_y(PZ)

    def on_top(nid, mat, size, x, lift):
        n = bx(nid, mat, size, (x, ty + lift, PZ), rot=tilt, open_=['bottom'])
        return n
    nodes.append(on_top('power_track', 'seam', (0.040, 0.003, 0.016), -0.100, 0.0006))
    nodes.append(on_top('power_knob', 'sun', (0.016, 0.008, 0.012), -0.110, 0.0035))
    nodes.append(on_top('led', 'led', (0.005, 0.0024, 0.005), -0.068, 0.0004))
    nodes.append(dict(cyl('reset_ring', 'seam', 0.011, 0.003, (0.100, ty + 0.0006, PZ), seg=10)))
    nodes.append(dict(cyl('reset_button', 'moon', 0.0075, 0.008, (0.100, ty + 0.003, PZ), seg=10)))
    for n in nodes[-2:]:
        n['transform']['rotate'] = tilt
    m = Mesh()
    circle = lambda ins: [(0.015 * math.cos(-2 * math.pi * k / 12), 0.015 * math.sin(-2 * math.pi * k / 12))
                          for k in range(12)]
    stack(m, circle, [(-0.0012, 0.0, 'black'), (0.0012, 0.0, None)], top='emblem')
    em = m.node('emblem')
    em['transform'] = {'rotate': tilt, 'translate': [0, r6(ty), PZ]}
    nodes.append(em)
    nodes.append(on_top('led_moon', 'led_moon', (0.005, 0.0024, 0.005), 0.068, 0.0004))

    # the front: two controller ports inside, two memory card slots outside
    portm = {'top': 'tray', 'bottom': 'tray', 'left': 'tray', 'right': 'tray', 'front': 'port', 'back': 'tray'}
    cardm = dict(portm, front='card')
    m = Mesh()
    for x in (-0.034, 0.034):
        box(m, (x, 0.0205, -D / 2 + 0.004), (0.028, 0.017, 0.0136), portm)
    for x in (-0.096, 0.096):
        box(m, (x, 0.0205, -D / 2 + 0.004), (0.040, 0.010, 0.0130), cardm)
    nodes.append(m.node('front_ports'))

    # the back: AV multi-out, DC in, the MeiNet aerial socket
    nodes.append(bx('av_out', 'black', (0.034, 0.010, 0.010), (-0.050, 0.020, D / 2 - 0.002), open_=['bottom']))
    nodes.append(cyl('dc_in', 'black', 0.0055, 0.010, (0.020, 0.020, D / 2 - 0.002), seg=8, axis='z'))
    nodes.append(cyl('aerial', 'gold', 0.0042, 0.016, (0.075, 0.020, D / 2 + 0.002), seg=8, axis='z'))

    # inside: positions from the board art, 128 x 96 texels over the tray's top
    def at(u, v):
        return (-W / 2 + u / 128 * W, D / 2 - v / 96 * D)

    def foot(u0, v0, u1, v1, inset=0.002):
        (x0, z0), (x1, z1) = at(u0, v0), at(u1, v1)
        return ((x0 + x1) / 2, (z0 + z1) / 2), (abs(x1 - x0) - 2 * inset, abs(z1 - z0) - 2 * inset)

    (cx, cz), (sx, sz) = foot(18, 34, 44, 60)              # the CPU and its finned sink
    nodes.append(bx('cpu', 'chip', (sx, 0.004, sz), (cx, Y_PCB + 0.0015, cz), open_=['bottom']))
    nodes.append(bx('sink_base', 'alu', (sx - 0.004, 0.003, sz - 0.004), (cx, Y_PCB + 0.0045, cz), open_=['bottom']))
    fins = {'id': 'sink_fins', 'op': 'group', 'children': [
        bx('fin', 'alu', (0.0016, 0.014, sz - 0.007), (cx - (sx - 0.008) / 2, Y_PCB + 0.012, cz), open_=['bottom'])],
        'modifiers': [{'op': 'array', 'count': 6, 'step': [r6((sx - 0.008) / 5), 0, 0]}]}
    nodes.append(fins)
    (cx, cz), (sx, sz) = foot(60, 38, 88, 62)              # the Prism Engine under a silver lid
    nodes.append(bx('gpu', 'chip', (sx, 0.004, sz), (cx, Y_PCB + 0.0015, cz), open_=['bottom']))
    nodes.append(bx('gpu_lid', 'silver', (sx - 0.008, 0.003, sz - 0.008), (cx, Y_PCB + 0.004, cz), open_=['bottom']))
    nodes.append(bx('connector', 'connector', (0.116, 0.009, 0.026), (0, Y_PCB + 0.0035, CZ), open_=['bottom']))
    nodes.append(bx('connector_pins', 'gold', (0.104, 0.0024, 0.022), (0, Y_PCB + 0.0082, CZ), open_=['bottom']))
    for i, (u0, v0, u1, v1) in enumerate([(20, 66, 30, 76), (34, 66, 44, 76)]):   # RAM
        (cx, cz), (sx, sz) = foot(u0, v0, u1, v1, 0.0005)
        nodes.append(bx('ram%d' % i, 'chip', (sx, 0.003, sz), (cx, Y_PCB + 0.001, cz), open_=['bottom']))
    # the power supply: transformer, two capacitors, a heat-sink plate
    nodes.append(bx('transformer_core', 'black', (0.030, 0.020, 0.024), (0.105, Y_PCB + 0.009, -0.010), open_=['bottom']))
    nodes.append(bx('transformer_coil', 'coil', (0.020, 0.018, 0.028), (0.105, Y_PCB + 0.0085, -0.010), open_=['bottom']))
    nodes.append(cyl('cap_a', 'capacitor', 0.0065, 0.020, (0.078, Y_PCB + 0.009, 0.028), seg=8))
    nodes.append(cyl('cap_b', 'capacitor', 0.0050, 0.015, (0.094, Y_PCB + 0.007, 0.034), seg=8))
    nodes.append(bx('psu_sink', 'alu', (0.034, 0.020, 0.0024), (0.108, Y_PCB + 0.009, 0.020), open_=['bottom']))
    # the controller ports' backs
    m = Mesh()
    for x in (-0.034, 0.034):
        box(m, (x, Y_PCB + 0.003, -D / 2 + 0.024), (0.026, 0.010, 0.020), 'black', skip=('bottom',))
    nodes.append(m.node('port_blocks'))

    materials = dict(COMMON_MATERIALS)
    materials.update({
        'shell': smoke(0.032),
        'shell_lo': smoke(0.032, ('#000000', '#4f5662', '#7b8491')),
        'top_console': glass_top('top_console'),
        'top_deck': glass_top('top_deck'),
        'pcb': {'color': '#24603a', 'texture': sheet_tex('pcb_console')},
        'port': {'color': '#28292e', 'texture': sheet_tex('port')},
        'card': {'color': '#28292e', 'texture': sheet_tex('card')},
        'cart': {'color': '#34373e'},
        'cart_dark': {'color': '#24262b'},
        'label': {'color': '#2a2e50', 'texture': sheet_tex('label')},
        'coil': {'color': '#d9b24a'},
        'capacitor': {'color': '#2e4f9e'},
        'led_moon': {'color': '#7ab8ff', 'class': 'emissive'},
        'emblem': {'color': '#16181c', 'texture': sheet_tex('emblem')},
    })
    return recipe('clear_smoke_console', {'vertices': 2048, 'triangles': 1300}, materials, nodes, 100)


# ---------------------------------------------------------------- the controller

def controller():
    sharp = [(-0.064, 0.034), (0.064, 0.034), (0.077, 0.004), (0.072, -0.052), (0.044, -0.064),
             (0.026, -0.030), (-0.026, -0.030), (-0.044, -0.064), (-0.072, -0.052), (-0.077, 0.004)]
    radii = [0.016, 0.016, 0.026, 0.020, 0.014, 0.014, 0.014, 0.014, 0.020, 0.026]
    outline = rounded_outline(sharp, radii, 2)
    Y_PCB, Y_WALL, Y_TOP = 0.015, 0.0215, 0.026

    def grips(x, z, level):
        if level > 1:
            return 0.0
        t = max(0.0, min(1.0, (-0.004 - z) / 0.040))
        t = t * t * (3 - 2 * t)
        return -0.008 * t

    nodes = []
    m = Mesh()
    stack(m, outline, [(0.0, 0.006, 'base'), (0.006, 0.0, 'base'),
                       (Y_PCB, 0.0, None)], top='pcb', bottom='tray', ydef=grips)
    nodes.append(m.node('lower'))
    m = Mesh()
    stack(m, outline, [(Y_PCB, -0.0006, 'shell'), (Y_WALL, 0.001, 'rim'), (Y_TOP, 0.0045, None)],
          top='top_pad')
    nodes.append(m.node('upper'))

    # d-pad on the left, a plus with a dished centre
    DX, DZ = -0.045, 0.002
    arm, half = 0.0105, 0.0038
    plus = []
    for (a, b) in [(-half, arm), (half, arm), (half, half), (arm, half), (arm, -half), (half, -half),
                   (half, -arm), (-half, -arm), (-half, -half), (-arm, -half), (-arm, half), (-half, half)]:
        plus.append((DX + a, DZ + b))
    m = Mesh()
    stack(m, rounded_outline(plus, [0.0012, 0.0012, 0, 0.0012, 0.0012, 0, 0.0012, 0.0012, 0, 0.0012, 0.0012, 0], 1),
          [(Y_TOP - 0.004, 0.0, 'dpad'), (Y_TOP + 0.0035, 0.0, None)], top='dpad')
    nodes.append(m.node('dpad'))
    nodes.append(puck('dpad_well', 'seam', 0.0145, 0.003, (DX, Y_TOP + 0.0002, DZ)))

    # A B X Y on the right: Super Famicom colours, in clear-tinted plastic
    BX, BZ, S = 0.045, 0.002, 0.0105
    for nid, mat, (dx, dz) in [('btn_a', 'btn_a', (S, 0)), ('btn_b', 'btn_b', (0, -S)),
                                ('btn_x', 'btn_x', (0, S)), ('btn_y', 'btn_y', (-S, 0))]:
        nodes.append(puck(nid, mat, 0.0056, 0.008, (BX + dx, Y_TOP + 0.0015, BZ + dz)))
    nodes.append(puck('btn_well', 'seam', 0.0185, 0.003, (BX, Y_TOP + 0.0002, BZ)))

    # the analog stick in the middle, between the grips
    SX, SZ = 0.0, -0.022
    nodes.append(puck('stick_ring', 'seam', 0.0125, 0.003, (SX, Y_TOP + 0.0002, SZ)))
    nodes.append(cyl('stick_shaft', 'black', 0.0035, 0.012, (SX, Y_TOP + 0.004, SZ), seg=6))
    nodes.append({'id': 'stick_cap', 'op': 'lathe', 'segments': 8, 'material': 'stick',
                  'profile': [[0.0, Y_TOP + 0.0078], [0.0095, Y_TOP + 0.0080], [0.0106, Y_TOP + 0.0104],
                              [0.0094, Y_TOP + 0.0126], [0.0, Y_TOP + 0.0130]],
                  'transform': {'translate': [SX, 0, SZ]}})

    # Start and Select, small slanted pills, and the badge above them
    for nid, x in (('select', -0.011), ('start', 0.011)):
        nodes.append({'id': nid, 'op': 'cylinder', 'radius': 0.0026, 'height': 0.010, 'segments': 6,
                      'material': 'pill',
                      'transform': {'scale': [1, 1, 1], 'rotate': [0, 0, 90],
                                    'translate': [x, Y_TOP + 0.0008, 0.006]}})
    m = Mesh()
    box(m, (0, Y_TOP + 0.0004, 0.020), (0.030, 0.0018, 0.0105),
        {'top': 'logo_small', 'bottom': 'black', 'left': 'black', 'right': 'black', 'front': 'black', 'back': 'black'})
    nodes.append(m.node('badge'))

    # L and R on the shoulders, clear smoke, and the cable out of the back
    for nid, x in (('l', -0.050), ('r', 0.050)):
        sh = rrect(0.032, 0.012, 0.004, 1, cx=x, cz=0.036)
        m = Mesh()
        stack(m, sh, [(Y_PCB + 0.001, 0.0, 'shoulder'), (Y_TOP - 0.0015, 0.0, 'shoulder'),
                      (Y_TOP + 0.001, 0.0025, None)], top='shoulder')
        nodes.append(m.node(nid))
    nodes.append(cyl('cable', 'cable', 0.0028, 0.026, (0, 0.012, 0.045), seg=6, axis='z'))
    # inside, seen through the top: the cable's wires running to the board
    m = Mesh()
    for i, (x, mat) in enumerate(((-0.0032, 'wire_red'), (0.0, 'wire_white'), (0.0032, 'wire_black'))):
        box(m, (x, Y_PCB + 0.0009, 0.024 - 0.002 * abs(i - 1)), (0.0022, 0.0022, 0.022 - 0.004 * abs(i - 1)),
            mat, skip=('bottom',))
    nodes.append(m.node('wires'))

    materials = dict(COMMON_MATERIALS)
    materials.update({
        'shell': smoke(0.020),
        'top_pad': glass_top('top_pad'),
        # the lower half: the same smoke over the dark inside, painted, so it costs no faces
        'base': {'color': '#3a3f47', 'texture': {'texels': STIPPLE_HI, 'colors': ['#2c2f35', '#4f5662', '#7b8491'],
                                                 'projection': 'box', 'scale': [0.020, 0.020]}},
        'pcb': {'color': '#24603a', 'texture': sheet_tex('pcb_pad')},
        'logo_small': {'color': '#16181c', 'texture': sheet_tex('logo_small')},
        'dpad': {'color': '#4d535c'},
        'wire_red': {'color': '#c8402f'},
        'wire_white': {'color': '#e6e6e0'},
        'wire_black': {'color': '#202022'},
        'btn_a': {'color': '#e0503c'},
        'btn_b': {'color': '#e8bf3c'},
        'btn_x': {'color': '#4a72d6'},
        'btn_y': {'color': '#3aa45e'},
        'stick': {'color': '#3a3e46', 'smooth': True},
        'pill': {'color': '#8a919c'},
        'shoulder': {'color': '#59606b'},
        'cable': {'color': '#2a2c31'},
    })
    return recipe('clear_smoke_controller', {'vertices': 2048, 'triangles': 900}, materials, nodes, 100)


def write(name, data):
    path = os.path.join(HERE, name)
    with open(path, 'w') as fh:
        json.dump(data, fh, indent=1)
        fh.write('\n')
    print('wrote', path)


if __name__ == '__main__':
    write('console.asset.json', console())
    write('controller.asset.json', controller())
