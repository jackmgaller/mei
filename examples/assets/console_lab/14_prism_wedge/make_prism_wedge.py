#!/usr/bin/env python3
"""Prism Wedge: write art/*.png, console.asset.json and controller.asset.json.

Real size in metres, Y up, the front facing -Z. Run: python3 make_prism_wedge.py
(needs Pillow and the macOS fonts Hiragino Sans GB and Avenir Next for the art).
"""
import json
import math
from pathlib import Path

from prismkit import Builder, mesh_node, inset, add, sub, mul, unit, centroid, cross

HERE = Path(__file__).resolve().parent
ART = HERE / 'art'

SPECTRUM = ['#e2393b', '#f3842a', '#f2cd3c', '#3dbb5c', '#2c8fe3', '#7550d4']
SUN = '#f39a2e'    # the 日 orange
MOON = '#a9c8f0'   # the 月 pale blue

COMMON = {
    'deck': '#4d515b', 'chamfer': '#6c717c', 'wall': '#3a3d45', 'visor': '#15161a',
    'under': '#26282d', 'plinth': '#111215', 'port': '#0a0a0c', 'rim': '#6d727d',
    'gunmetal': '#5c616b',
}
for i, c in enumerate(SPECTRUM):
    COMMON[f'band{i}'] = c

POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'direction': [-0.4, 0.85, -0.35], 'ambient': 0.55}


# ---- art --------------------------------------------------------------------------------
def draw_logo(path, size, bg):
    from PIL import Image, ImageDraw, ImageFont
    W, H = size
    S = 8
    img = Image.new('RGB', (W * S, H * S), bg)
    d = ImageDraw.Draw(img)
    kanji = ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc', int(H * S * 0.86), index=2)
    word = ImageFont.truetype('/System/Library/Fonts/Avenir Next.ttc', int(H * S * 0.62), index=0)
    # 明: draw it white on a mask, then colour the 日 half orange and the 月 half blue
    mask = Image.new('L', img.size, 0)
    md = ImageDraw.Draw(mask)
    x0 = int(W * S * 0.04)
    bb = md.textbbox((0, 0), '明', font=kanji)
    gy = (H * S - (bb[3] - bb[1])) // 2 - bb[1]
    md.text((x0 - bb[0], gy), '明', font=kanji, fill=255)
    gw = bb[2] - bb[0]
    split = x0 + int(gw * 0.40)
    sun = Image.new('RGB', img.size, SUN)
    moon = Image.new('RGB', img.size, MOON)
    left = mask.copy()
    left.paste(0, (split, 0, img.size[0], img.size[1]))
    right = mask.copy()
    right.paste(0, (0, 0, split, img.size[1]))
    img.paste(sun, (0, 0), left)
    img.paste(moon, (0, 0), right)
    # the small dot between the mark and the word, as in the logo
    cx = x0 + gw + int(H * S * 0.14)
    r = int(H * S * 0.045)
    d.ellipse((cx - r, H * S * 0.62 - r, cx + r, H * S * 0.62 + r), fill='#ffffff')
    wb = d.textbbox((0, 0), 'MEI', font=word)
    wx = cx + int(H * S * 0.14)
    wy = (H * S - (wb[3] - wb[1])) // 2 - wb[1]
    d.text((wx - wb[0], wy), 'MEI', font=word, fill='#ffffff')
    img = img.resize((W, H), Image.LANCZOS)
    img.save(path)


def draw_label(path, size):
    """The cart in the slot: a made-up racing game, sun and moon over a spectrum road."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = size
    S = 8
    w, h = W * S, H * S
    img = Image.new('RGB', (w, h), '#1b2350')
    d = ImageDraw.Draw(img)
    for y in range(h):  # night-to-dusk sky
        t = y / h
        c = (int(27 + 120 * t), int(35 + 40 * t), int(80 + 30 * t))
        d.line((0, y, w, y), fill=c)
    # sun and moon
    d.ellipse((w * 0.10, h * 0.10, w * 0.30, h * 0.10 + w * 0.20), fill=SUN)
    d.ellipse((w * 0.74, h * 0.08, w * 0.88, h * 0.08 + w * 0.14), fill=MOON)
    d.ellipse((w * 0.78, h * 0.05, w * 0.92, h * 0.05 + w * 0.14), fill=(40, 52, 98))
    # a road of spectrum bands toward a vanishing point
    vx, vy = w * 0.5, h * 0.50
    n = len(SPECTRUM)
    for i, c in enumerate(SPECTRUM):
        a0, a1 = i / n, (i + 1) / n
        d.polygon([(vx, vy), (w * (-0.2 + 1.4 * a0), h), (w * (-0.2 + 1.4 * a1), h)], fill=c)
    d.rectangle((0, h * 0.50, w, h * 0.53), fill='#11131c')
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Futura.ttc', int(h * 0.20), index=4)
    t = 'PRISM RALLY'
    bb = d.textbbox((0, 0), t, font=font)
    tx = (w - (bb[2] - bb[0])) // 2 - bb[0]
    ty = int(h * 0.30) - bb[1]
    for dx, dy in ((-S, 0), (S, 0), (0, -S), (0, S)):
        d.text((tx + dx, ty + dy), t, font=font, fill='#11131c')
    d.text((tx, ty), t, font=font, fill='#ffffff')
    img.resize((W, H), Image.LANCZOS).save(path)


def make_art():
    ART.mkdir(exist_ok=True)
    draw_logo(ART / 'logo_visor.png', (96, 32), '#1c1d24')  # renders as the visor does
    draw_logo(ART / 'logo_deck.png', (96, 32), COMMON['deck'])
    draw_label(ART / 'cart_label.png', (64, 32))


# ---- shared helpers ---------------------------------------------------------------------
def outward2(poly, i):
    """Outward plan normal (x, z) of edge i -> i+1 of a simple polygon (either winding)."""
    n = len(poly)
    area = sum(poly[k][0] * poly[(k + 1) % n][1] - poly[(k + 1) % n][0] * poly[k][1] for k in range(n))
    a, b = poly[i], poly[(i + 1) % n]
    ex, ez = b[0] - a[0], b[1] - a[1]
    nx, nz = (ez, -ex) if area > 0 else (-ez, ex)
    L = math.hypot(nx, nz)
    return nx / L, nz / L


def ngon(cx, cz, r, n, y, phase=0.0, sx=1.0, sz=1.0):
    return [(cx + r * sx * math.cos(phase + 2 * math.pi * k / n), y,
             cz + r * sz * math.sin(phase + 2 * math.pi * k / n)) for k in range(n)]


def frustum(b, cx, cz, r0, r1, y0, y1, n, side, top, phase=0.0, sx=1.0, sz=1.0):
    b.loft([ngon(cx, cz, r0, n, y0, phase, sx, sz), ngon(cx, cz, r1, n, y1, phase, sx, sz)],
           [side], (0, 1, 0), cap_mats=(side, top))


def stripes(b, tags, c0, width, slope, zone=None, before='visor', after=None):
    """Cut the chevron z - slope*|x| = c0 + k*width (k = 0..6) through faces with these tags
    and colour them: before the first line `before`, inside the bands the spectrum."""
    def sel(f, side):
        if f.tag not in tags:
            return False
        c = centroid(f.pts)
        if zone and not zone(c):
            return False
        return c[0] * side > 0
    for side in (1, -1):
        fn = (lambda p, s=side: p[2] - slope * s * p[0])
        for k in range(len(SPECTRUM) + 1):
            b.cut(fn, c0 + k * width, lambda f, s=side: sel(f, s))
    for f in b.faces:
        if f.tag not in tags:
            continue
        c = centroid(f.pts)
        if zone and not zone(c):
            continue
        v = c[2] - slope * abs(c[0])
        if v < c0:
            if before and f.tag in ('top', 'ch'):
                f.mat = before
        elif v < c0 + len(SPECTRUM) * width:
            f.mat = f'band{int((v - c0) // width)}'
        elif after:
            f.mat = after


def rect_lines(x0, x1, z0, z1):
    return [((lambda p: -p[0]), -x0), ((lambda p: p[0]), x1),
            ((lambda p: -p[2]), -z0), ((lambda p: p[2]), z1)]


def set_mat(mat):
    def act(f):
        f.mat = mat
        return f
    return act


def textured(path):
    return {'color': COMMON['visor'], 'texture': {'image': path, 'bits': 8, 'projection': 'fit'}}


def write(name, recipe):
    p = HERE / f'{name}.asset.json'
    p.write_text(json.dumps(recipe, indent=1) + '\n')
    tris = sum(len(n.get('faces', [])) for n in recipe['nodes'] if n['op'] == 'mesh')
    print(f'{p.name}: {tris} mesh triangles in mesh nodes')


# ---- console ----------------------------------------------------------------------------
def console():
    OUT = [(0.0, -0.128), (0.150, -0.098), (0.150, 0.094), (0.128, 0.116), (0.0, 0.116),
           (-0.128, 0.116), (-0.150, 0.094), (-0.150, -0.098)]
    TAGS = ['wfr', 'wr', 'wbr', 'wb', 'wb', 'wbl', 'wl', 'wfl']
    BASE, CH_IN, CH_UP = 0.010, 0.016, 0.010

    def R(x, z):
        return 0.040 + 0.20 * (z + 0.128) - 0.09 * abs(x)

    def deck_y(x, z):
        return R(x, z) + CH_UP

    INN = inset(OUT, CH_IN)
    INN = [(round(x, 9) if abs(x) > 1e-9 else 0.0, z) for x, z in INN]
    bot = [(x, BASE, z) for x, z in OUT]
    top = [(x, R(x, z), z) for x, z in OUT]
    inn = [(x, deck_y(x, z), z) for x, z in INN]

    b = Builder()
    n = len(OUT)
    for i in range(n):
        j = (i + 1) % n
        nx, nz = outward2(OUT, i)
        b.add([bot[i], bot[j], top[j], top[i]], 'wall', out=(nx, 0, nz), tag=TAGS[i])
        b.add([top[i], top[j], inn[j], inn[i]], 'chamfer', out=(nx, 1.2, nz), tag='ch')
    right = [p for p in inn if p[0] >= 0]
    left = [p for p in inn if p[0] <= 0]
    b.add(right, 'deck', out=(0, 1, 0), tag='top')
    b.add(left, 'deck', out=(0, 1, 0), tag='top')
    b.add(bot, 'under', out=(0, -1, 0), tag='bottom')

    # the spectrum chevron, black visor ahead of it
    stripes(b, ('top', 'ch', 'wr', 'wl'), -0.050, 0.0045, 0.35)

    # the logo on the visor's left facet
    LX0, LX1, LZ1 = -0.118, -0.038, -0.0496
    LZ0 = LZ1 - (LX1 - LX0) / 3
    b.region(rect_lines(LX0, LX1, LZ0, LZ1), lambda f: f.tag == 'top' and centroid(f.pts)[0] < 0,
             set_mat('logo'))

    # front ports: controllers on the left front facet, memory cards on the right
    def wall_frame(a2, c2, t, yc):
        a = (a2[0], 0, a2[1])
        c = (c2[0], 0, c2[1])
        U = unit(sub(c, a))
        center = add(a, mul(sub(c, a), t))
        center = (center[0], yc, center[2])
        N = unit(cross(U, (0, 1, 0)))
        if N[2] > 0:
            N = mul(N, -1)
        return center, U, N

    def port(center, U, N, outline, rim, depth, sel_tag):
        V = (0, 1, 0)
        big = [(u * (1 + rim / 0.012), v * (1 + rim / 0.0065)) for u, v in outline]
        corners = [add(center, add(mul(U, u), mul(V, v))) for u, v in big]
        cc = centroid(corners)
        lines = []
        for i in range(len(corners)):
            p, q = corners[i], corners[(i + 1) % len(corners)]
            o = unit(cross(sub(q, p), N))
            if sum(o[k] * (p[k] - cc[k]) for k in range(3)) < 0:
                o = mul(o, -1)
            lines.append(((lambda x, o=o: o[0] * x[0] + o[1] * x[1] + o[2] * x[2]),
                          o[0] * p[0] + o[1] * p[1] + o[2] * p[2]))
        b.region(lines, lambda f: f.tag == sel_tag, set_mat('rim'))
        b.recess(center, U, V, N, outline, depth, 'port', 'port',
                 lambda f: f.tag == sel_tag and f.mat == 'rim')

    CTRL = [(-0.012, -0.0035), (-0.0085, -0.0065), (0.0085, -0.0065), (0.012, -0.0035),
            (0.012, 0.0055), (-0.012, 0.0055)]
    for t in (0.30, 0.64):
        center, U, N = wall_frame(OUT[7], OUT[0], t, 0.0225)
        port(center, U, N, CTRL, 0.0025, 0.010, 'wfl')
    CARD = [(-0.016, -0.0025), (0.016, -0.0025), (0.0175, 0.0025), (-0.0175, 0.0025)]
    for t in (0.36, 0.70):
        center, U, N = wall_frame(OUT[0], OUT[1], t, 0.0250)
        port(center, U, N, CARD, 0.0022, 0.012, 'wfr')

    # back: AV multi-out and DC in (seen from behind, at the right-hand half's wall)
    def back_recess(xc, yc, outline, depth):
        b.recess((xc, yc, 0.116), (-1, 0, 0), (0, 1, 0), (0, 0, 1), outline, depth, 'port', 'port',
                 lambda f: f.tag == 'wb' and centroid(f.pts)[0] * xc > 0)
    back_recess(0.055, 0.040, [(-0.013, -0.003), (0.013, -0.003), (0.015, 0.0), (0.013, 0.003),
                               (-0.013, 0.003), (-0.015, 0.0)], 0.008)
    back_recess(0.105, 0.036, [(-0.0045, -0.0045), (0.0045, -0.0045), (0.0045, 0.0045),
                               (-0.0045, 0.0045)], 0.008)
    for k in range(4):  # vent slits on the left half
        back_recess(-0.095 - 0.007 * k, 0.040, [(-0.0018, -0.012), (0.0018, -0.012),
                                                  (0.0018, 0.012), (-0.0018, 0.012)], 0.006)

    LOGO = {'x0': LX0, 'x1': LX1, 'z0': LZ0, 'z1': LZ1}

    def uv(p):
        return ((p[0] - LOGO['x0']) / (LOGO['x1'] - LOGO['x0']),
                (LOGO['z1'] - p[2]) / (LOGO['z1'] - LOGO['z0']))
    body = mesh_node('body', b, uv)

    # plinth: a recessed black base
    pl = Builder()
    PO = inset(OUT, 0.012)
    pl.loft([[(x, 0.0, z) for x, z in PO], [(x, 0.0125, z) for x, z in PO]], ['plinth'], (0, 1, 0))
    plinth = mesh_node('plinth', pl)

    # cart bay: a chamfered hexagonal block with the slot in its top
    H = [(-0.080, 0.034), (-0.060, 0.014), (0.060, 0.014), (0.080, 0.034), (0.080, 0.112),
         (-0.080, 0.112)]
    BT, SZ = 0.104, 0.064   # bay top, slot centre
    HI = inset(H, 0.018)
    bay = Builder()
    bay.loft([[(x, 0.060, z) for x, z in H], [(x, 0.084, z) for x, z in H],
              [(x, BT, z) for x, z in HI]], ['bay_wall', 'bay_chamfer'], (0, 1, 0),
             cap_mats=('bay_wall', 'bay_top'))
    for f in bay.faces:
        if f.mat == 'bay_top':
            f.tag = 'baytop'
    bay.region(rect_lines(-0.0545, 0.0545, SZ - 0.017, SZ + 0.017), lambda f: f.tag == 'baytop',
               set_mat('rim'))
    bay.recess((0, BT, SZ), (1, 0, 0), (0, 0, 1), (0, 1, 0),
               [(-0.0515, -0.0135), (0.0515, -0.0135), (0.0515, 0.0135), (-0.0515, 0.0135)],
               0.012, 'port', 'port', lambda f: f.tag == 'baytop' and f.mat == 'rim')
    cart_bay = mesh_node('cart_bay', bay)

    # the cart, standing in the slot, its label facing front
    cb = Builder()
    prof = [(-0.048, 0.088), (0.048, 0.088), (0.048, 0.142), (0.041, 0.150), (-0.041, 0.150),
            (-0.048, 0.142)]
    cb.prism([(x, y, SZ + 0.009) for x, y in prof], (0, 0, -0.018), 'cart', 'cart', 'cart')
    for f in cb.faces:
        if all(abs(p[2] - (SZ - 0.009)) < 1e-9 for p in f.pts):
            f.tag = 'front'
    CL = (-0.036, 0.036, 0.106, 0.142)
    cb.region([((lambda p: -p[0]), -CL[0]), ((lambda p: p[0]), CL[1]),
               ((lambda p: -p[1]), -CL[2]), ((lambda p: p[1]), CL[3])],
              lambda f: f.tag == 'front', set_mat('label'))
    # grip ribs on the cart's top edge
    for k in range(5):
        x = -0.020 + 0.010 * k
        cb.prism([(x - 0.0015, 0.1475, SZ - 0.0065), (x + 0.0015, 0.1475, SZ - 0.0065),
                  (x + 0.0015, 0.1515, SZ - 0.0065), (x - 0.0015, 0.1515, SZ - 0.0065)],
                 (0, 0, 0.013), 'cart_rib')
    cart = mesh_node('cart', cb, lambda p: ((p[0] - CL[0]) / (CL[1] - CL[0]),
                                           (CL[3] - p[1]) / (CL[3] - CL[2])))

    # power (sun orange) and reset (moon blue): hexagonal keys on the right deck
    keys = Builder()
    for (x, z, r, mat) in ((0.111, 0.050, 0.0100, 'power'), (0.111, 0.080, 0.0068, 'reset')):
        y0 = deck_y(x + r, z - r) - 0.004
        y1 = max(deck_y(x, z + r), deck_y(x - r, z + r)) + 0.0055
        keys.loft([ngon(x, z, r * 1.25, 6, y0, math.pi / 6), ngon(x, z, r * 1.25, 6, y1 - 0.004, math.pi / 6),
                   ngon(x, z, r, 6, y1, math.pi / 6)], ['gunmetal', 'gunmetal'], (0, 1, 0),
                  cap_mats=('gunmetal', mat))
    # the power lamp: a small forward-pointing triangle on the visor
    lx, lz = 0.040, -0.088
    tri = [(lx, 0, lz - 0.005), (lx + 0.0045, 0, lz + 0.003), (lx - 0.0045, 0, lz + 0.003)]
    ly = deck_y(lx + 0.0045, lz + 0.003)
    keys.prism([(x, ly - 0.002, z) for x, _, z in tri], (0, 0.0035, 0), 'lamp_side', 'lamp_side', 'lamp')
    # prism ribs (triangular section) on the left deck, along the chevron
    a = 0.35
    d = unit((-1.0, 0.0, a))
    w = unit((a, 0.0, 1.0))
    for k in range(5):
        zc = 0.024 + 0.012 * k
        E1 = (-0.090, 0, zc)
        E1 = (E1[0], deck_y(E1[0], E1[2]), E1[2])
        L = 0.040
        E2 = add(E1, mul(d, L))
        E2 = (E2[0], deck_y(E2[0], E2[2]), E2[2])
        ring = [add(E1, add(mul(w, 0.0032), (0, -0.0025, 0))), add(E1, (0, 0.0042, 0)),
                add(E1, add(mul(w, -0.0032), (0, -0.0025, 0)))]
        keys.prism(ring, sub(E2, E1), 'rib')
    controls = mesh_node('controls', keys)

    nodes = [body, plinth, cart_bay, cart, controls,
             {'id': 'antenna_nut', 'op': 'cylinder', 'radius': 0.0068, 'height': 0.0055, 'segments': 6,
              'material': 'gunmetal', 'transform': {'rotate': [90, 0, 0], 'translate': [-0.062, 0.040, 0.11675]}},
             {'id': 'antenna_pin', 'op': 'cylinder', 'radius': 0.0042, 'height': 0.012, 'segments': 8,
              'material': 'brass', 'transform': {'rotate': [90, 0, 0], 'translate': [-0.062, 0.040, 0.121]}}]
    mats = {k: {'color': v} for k, v in COMMON.items()}
    mats.update({
        'logo': textured('art/logo_visor.png'),
        'label': {'color': '#3a4a8a', 'texture': {'image': 'art/cart_label.png', 'bits': 8, 'projection': 'fit'}},
        'cart': {'color': '#9ea3ab'}, 'cart_rib': {'color': '#8a8f98'},
        'bay_wall': {'color': '#3d4048'}, 'bay_chamfer': {'color': '#5a5f6a'}, 'bay_top': {'color': '#454952'},
        'power': {'color': SUN}, 'reset': {'color': MOON},
        'lamp': {'color': '#ff9a3c', 'class': 'emissive'}, 'lamp_side': {'color': '#7a3a12'},
        'rib': {'color': '#50545e'}, 'brass': {'color': '#c9a55a'},
    })
    used = set()
    for nd in nodes:
        used.update(nd.get('face_materials', []))
        if 'material' in nd:
            used.add(nd['material'])
    mats = {k: v for k, v in mats.items() if k in used}
    recipe = {'format': 'mei-asset', 'version': 1, 'name': 'prism_wedge_console',
              'budget': {'vertices': 2048, 'triangles': 1200},
              'materials': mats, 'lighting': LIGHT, 'verification': POLICY, 'nodes': nodes}
    write('console', recipe)


# ---- controller -------------------------------------------------------------------------
def controller():
    RH = [(0.056, 0.040), (0.071, 0.030), (0.079, 0.006), (0.078, -0.028), (0.066, -0.056),
          (0.048, -0.063), (0.035, -0.051), (0.026, -0.034)]
    DROP = [0.0, 0.0, 0.001, 0.004, 0.008, 0.009, 0.006, 0.0]
    OUT = RH + [(-x, z) for x, z in reversed(RH)]
    DR = DROP + list(reversed(DROP))
    TOP = 0.026
    T = [(x, TOP, z) for x, z in inset(OUT, 0.006)]
    W = [(x, 0.019 - d, z) for (x, z), d in zip(OUT, DR)]
    Bi = inset(OUT, 0.005)
    B = [(x, 0.003 - 2.2 * d, z) for (x, z), d in zip(Bi, DR)]

    b = Builder()
    n = len(OUT)
    for i in range(n):
        j = (i + 1) % n
        nx, nz = outward2(OUT, i)
        b.add([T[i], T[j], W[j], W[i]], 'chamfer', out=(nx, 1.0, nz), tag='ch')
        b.add([W[i], W[j], B[j], B[i]], 'wall', out=(nx, -0.3, nz), tag='wall')
    b.add(T, 'deck', out=(0, 1, 0), tag='top')
    # the underside: not planar, triangulated in plan
    from prismkit import _triangulate, newell
    P = {k: p for k, p in enumerate(B)}
    for tri in _triangulate(list(range(n)), P, newell(B)):
        b.add([B[k] for k in tri], 'under', out=(0, -1, 0), tag='bottom')

    # centre panel: the chevron (black ahead of it) between the button clusters
    b.cut(lambda p: p[0], 0.0, lambda f: f.tag == 'top')
    for xc in (0.032, -0.032):
        b.cut(lambda p: p[0], xc, lambda f: f.tag == 'top')
    stripes(b, ('top',), -0.007, 0.0025, 0.30, zone=lambda c: abs(c[0]) < 0.032)
    LX0, LX1, LZ0 = -0.020, 0.020, 0.0155
    LZ1 = LZ0 + (LX1 - LX0) / 3
    b.region(rect_lines(LX0, LX1, LZ0, LZ1), lambda f: f.tag == 'top' and f.mat == 'deck'
             and abs(centroid(f.pts)[0]) < 0.032, set_mat('logo'))
    assert LZ1 < 0.034
    body = mesh_node('shell', b, lambda p: ((p[0] - LX0) / (LX1 - LX0), (LZ1 - p[2]) / (LZ1 - LZ0)))

    k = Builder()
    # d-pad on a black hexagonal plate
    dx, dz = -0.053, 0.004
    frustum(k, dx, dz, 0.0165, 0.0155, TOP - 0.003, TOP + 0.0012, 6, 'plate_side', 'visor', math.pi / 6)
    A, Wd = 0.0115, 0.0042
    cross_pts = [(Wd, A), (Wd, Wd), (A, Wd), (A, -Wd), (Wd, -Wd), (Wd, -A), (-Wd, -A), (-Wd, -Wd),
                 (-A, -Wd), (-A, Wd), (-Wd, Wd), (-Wd, A)]
    k.prism([(dx + u, TOP - 0.002, dz + v) for u, v in cross_pts], (0, 0.0058, 0), 'pad', 'pad', 'pad')
    # A B X Y on a matching plate, in the spectrum
    ax, az = 0.053, 0.004
    frustum(k, ax, az, 0.0175, 0.0165, TOP - 0.003, TOP + 0.0012, 6, 'plate_side', 'visor', math.pi / 6)
    s = 0.0102
    for (ox, oz, mat) in ((0, -s, 'btn_a'), (s, 0, 'btn_b'), (-s, 0, 'btn_x'), (0, s, 'btn_y')):
        k.loft([ngon(ax + ox, az + oz, 0.0047, 6, TOP - 0.001, math.pi / 6),
                ngon(ax + ox, az + oz, 0.0047, 6, TOP + 0.0042, math.pi / 6),
                ngon(ax + ox, az + oz, 0.0036, 6, TOP + 0.0056, math.pi / 6)],
               [mat + '_side', mat + '_side'], (0, 1, 0), cap_mats=(mat + '_side', mat))
    # analog stick: hexagonal gate, shaft, octagonal cap
    sx, sz = -0.034, -0.021
    frustum(k, sx, sz, 0.0118, 0.0106, TOP - 0.003, TOP + 0.0016, 6, 'plate_side', 'visor', math.pi / 6)
    frustum(k, sx, sz, 0.0034, 0.0034, TOP - 0.002, TOP + 0.0075, 6, 'pad', 'pad')
    k.loft([ngon(sx, sz, 0.0082, 8, TOP + 0.0070, math.pi / 8),
            ngon(sx, sz, 0.0082, 8, TOP + 0.0098, math.pi / 8),
            ngon(sx, sz, 0.0064, 8, TOP + 0.0118, math.pi / 8)],
           ['stick', 'stick_bevel'], (0, 1, 0), cap_mats=('stick', 'stick_top'))
    # select and start: long hexagonal keys on the black centre
    for x in (-0.0095, 0.0095):
        z = -0.016
        hexk = [(x - 0.0055, z), (x - 0.0038, z - 0.0018), (x + 0.0038, z - 0.0018), (x + 0.0055, z),
                (x + 0.0038, z + 0.0018), (x - 0.0038, z + 0.0018)]
        k.prism([(u, TOP - 0.0015, v) for u, v in hexk], (0, 0.0040, 0), 'gunmetal', 'gunmetal', 'key_top')
    # L and R on the back edge
    for side in (1, -1):
        prof = [(0.030, 0.0075), (0.0465, 0.0075), (0.0495, 0.0108), (0.0485, 0.0172), (0.030, 0.0172)]
        x0, x1 = (0.024, 0.061) if side > 0 else (-0.061, -0.024)
        k.prism([(x0, y, z) for z, y in prof], (x1 - x0, 0, 0), 'shoulder')
    keys = mesh_node('keys', k)

    nodes = [body, keys,
             {'id': 'cord_boot', 'op': 'cylinder', 'radius': 0.0042, 'height': 0.014, 'segments': 8,
              'material': 'cable', 'transform': {'rotate': [90, 0, 0], 'translate': [0, 0.012, 0.0455]}}]
    mats = {k2: {'color': v} for k2, v in COMMON.items()}
    mats.update({
        'logo': {'color': COMMON['deck'], 'texture': {'image': 'art/logo_deck.png', 'bits': 8, 'projection': 'fit'}},
        'plate_side': {'color': '#2a2c32'}, 'pad': {'color': '#2c2e34'},
        'stick': {'color': '#4a4e57'}, 'stick_bevel': {'color': '#5f646e'}, 'stick_top': {'color': '#3a3d45'},
        'key_top': {'color': '#7a7f89'}, 'shoulder': {'color': '#5c616b'}, 'cable': {'color': '#1c1d21'},
        'btn_a': {'color': SPECTRUM[0]}, 'btn_a_side': {'color': '#a22426'},
        'btn_b': {'color': SPECTRUM[2]}, 'btn_b_side': {'color': '#b08d1c'},
        'btn_x': {'color': SPECTRUM[4]}, 'btn_x_side': {'color': '#1c5f9e'},
        'btn_y': {'color': SPECTRUM[3]}, 'btn_y_side': {'color': '#257a3a'},
    })
    used = set()
    for nd in nodes:
        used.update(nd.get('face_materials', []))
        if 'material' in nd:
            used.add(nd['material'])
    mats = {k2: v for k2, v in mats.items() if k2 in used}
    recipe = {'format': 'mei-asset', 'version': 1, 'name': 'prism_wedge_controller',
              'budget': {'vertices': 1536, 'triangles': 800},
              'materials': mats, 'lighting': LIGHT, 'verification': POLICY, 'nodes': nodes}
    write('controller', recipe)


if __name__ == '__main__':
    make_art()
    console()
    controller()
