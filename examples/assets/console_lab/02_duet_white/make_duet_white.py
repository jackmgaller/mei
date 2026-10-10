#!/usr/bin/env python3
"""Duet White: writes art/duet_sheet.png (+ .sheet.json), console.asset.json and
controller.asset.json beside this script. Real size, metres, Y up, facing -Z.

    python3 make_duet_white.py
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
MARU = '/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc'

PEARL = '#f4f1ee'
SUN = (255, 138, 28)
MOON = (92, 150, 240)


# ---------------------------------------------------------------- the sheet

def hexc(c):
    return '#%02x%02x%02x' % c


def mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw_mei(size, colour_wordmark, wordmark=True, bg=(244, 241, 238), plate_border=None):
    """明 in the two colours (日 sun, 月 moon) with MEI beside, drawn 8x and reduced."""
    w, h = size
    S = 8
    img = Image.new('RGB', (w * S, h * S), bg)
    d = ImageDraw.Draw(img)
    if plate_border:
        d.rounded_rectangle([S, S, w * S - S - 1, h * S - S - 1], radius=h * S // 2 - S,
                            outline=plate_border, width=int(1.2 * S))
    kanji_px = int(h * S * 0.74)
    font = ImageFont.truetype(MARU, kanji_px)
    # the glyph on its own layer to colour the halves
    glyph = Image.new('L', (kanji_px * 2, kanji_px * 2), 0)
    ImageDraw.Draw(glyph).text((kanji_px // 2, kanji_px // 2), '明', font=font, fill=255)
    box = glyph.getbbox()
    glyph = glyph.crop(box)
    gw, gh = glyph.size
    # 日 and 月 split at the emptiest column in the middle third
    cols = [sum(glyph.getpixel((x, y)) for y in range(gh)) for x in range(gw)]
    split = min(range(gw // 3, 2 * gw // 3), key=lambda x: cols[x])
    sun = Image.new('RGB', glyph.size, SUN)
    moon = Image.new('RGB', glyph.size, MOON)
    colour = Image.new('RGB', glyph.size)
    colour.paste(sun.crop((0, 0, split, gh)), (0, 0))
    colour.paste(moon.crop((split, 0, gw, gh)), (split, 0))
    if wordmark:
        gx = int(h * S * 0.55)
    else:
        gx = (w * S - gw) // 2
    gy = (h * S - gh) // 2
    # a soft drop shadow, as on the logo
    shadow = Image.new('RGB', glyph.size, mix(bg, (120, 116, 140), 0.35))
    img.paste(shadow, (gx + S, gy + S), glyph.filter(ImageFilter.GaussianBlur(S * 0.6)))
    img.paste(colour, (gx, gy), glyph)
    if wordmark:
        wf = ImageFont.truetype(MARU, int(h * S * 0.56))
        x0 = gx + gw + int(h * S * 0.35)
        tb = d.textbbox((0, 0), 'MEI', font=wf)
        d.text((x0 - tb[0], (h * S - (tb[3] - tb[1])) // 2 - tb[1]), 'MEI', font=wf,
               fill=colour_wordmark)
    return img.resize((w, h), Image.LANCZOS)


def draw_seam(w, h):
    """The Duet line: sun orange at the left, pearl in the middle, moon blue at the right."""
    img = Image.new('RGB', (w, h))
    pearl = (246, 240, 236)
    for x in range(w):
        t = x / (w - 1)
        if t < 0.5:
            c = mix(SUN, pearl, (t / 0.5) ** 1.2)
        else:
            c = mix(pearl, MOON, ((t - 0.5) / 0.5) ** 0.8)
        for y in range(h):
            img.putpixel((x, y), c)
    return img


def draw_label(w, h):
    """The cart's label: a white stage, a sky, a sun-drop and a moon-drop mid-bounce."""
    S = 8
    W, H = w * S, h * S
    img = Image.new('RGB', (W, H))
    d = ImageDraw.Draw(img)
    top, bot = (186, 214, 250), (252, 236, 222)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=mix(top, bot, y / H))
    # stage
    d.rectangle([0, int(H * 0.78), W, H], fill=(250, 248, 246))
    d.line([(0, int(H * 0.78)), (W, int(H * 0.78))], fill=(214, 206, 220), width=S)
    # bounce arcs (dotted)
    for cx, col in ((W * 0.33, SUN), (W * 0.67, MOON)):
        for k in range(7):
            t = k / 6
            x = cx + (t - 0.5) * W * 0.36 * (1 if col == SUN else -1)
            y = H * 0.74 - math.sin(t * math.pi) * H * 0.42
            r = S * 0.9
            d.ellipse([x - r, y - r, x + r, y + r], fill=mix(col, (255, 255, 255), 0.45))
    # the two drops
    def drop(cx, cy, r, col, crescent):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
        hl = mix(col, (255, 255, 255), 0.6)
        d.ellipse([cx - r * 0.55, cy - r * 0.6, cx - r * 0.1, cy - r * 0.2], fill=hl)
        if crescent:
            d.ellipse([cx - r * 0.1, cy - r * 1.05, cx + r * 1.35, cy + r * 0.6],
                      fill=mix(top, bot, (cy - r) / H))
    drop(W * 0.30, H * 0.56, H * 0.16, SUN, False)
    drop(W * 0.70, H * 0.56, H * 0.16, MOON, True)
    # title band
    f = ImageFont.truetype(MARU, int(H * 0.16))
    title = 'ふたつのしずく'
    tb = d.textbbox((0, 0), title, font=f)
    d.text(((W - (tb[2] - tb[0])) // 2 - tb[0], int(H * 0.06) - tb[1]), title, font=f,
           fill=(96, 88, 128))
    return img.resize((w, h), Image.LANCZOS)


def draw_padlogo(w, h):
    return draw_mei((w, h), (150, 144, 168), wordmark=False)


def draw_rear(w, h):
    """The rear panel print: vent slots at both ends, small grey labels over the connectors.
    Seen from behind, u runs toward -X: DC in (x +0.04) at u 0.27, AV at 0.5, MeiNet at 0.73."""
    S = 8
    bg = (238, 234, 236)
    img = Image.new('RGB', (w * S, h * S), bg)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(MARU, int(h * S * 0.16))
    for x, text in ((0.27, 'DC IN'), (0.5, 'AV OUT'), (0.73, 'MeiNet')):
        tb = d.textbbox((0, 0), text, font=f)
        d.text((x * w * S - (tb[2] - tb[0]) / 2 - tb[0], h * S * 0.2 - (tb[3] - tb[1]) / 2 - tb[1]),
               text, font=f, fill=(140, 134, 152))
    for k in range(5):
        for x0 in (0.02 + k * 0.022, 0.89 + k * 0.022):
            d.rounded_rectangle([x0 * w * S, h * S * 0.18, (x0 + 0.011) * w * S, h * S * 0.84],
                                radius=S * 1.5, fill=(150, 142, 162))
    return img.resize((w, h), Image.LANCZOS)


TOP_X, TOP_Z = 0.110, 0.074          # the console's flat top: its half sizes


def draw_top(w, h):
    """The console's top print: from each drop, a dotted bounce trail hops toward the cart
    slot, sun on the left and moon on the right, as in the Duet boot. Seen from above,
    u along +X and v toward -Z (the front)."""
    S = 8
    img = Image.new('RGB', (w * S, h * S), (244, 241, 238))
    d = ImageDraw.Draw(img)

    def px(x, z):
        return ((x + TOP_X) / (2 * TOP_X) * w * S, (TOP_Z - z) / (2 * TOP_Z) * h * S)

    for side, col in ((-1, SUN), (1, MOON)):
        # a dotted arc from the drop's tip, bowing outward, up to the end of the cart slot
        p0, p1, p2 = (side * 0.064, -0.036), (side * 0.092, -0.006), (side * 0.056, 0.014)
        n = 10
        for k in range(n):
            t = k / (n - 1)
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
            z = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
            r = S * (2.1 - 0.9 * t)
            cx, cy = px(x, z)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=mix(col, (244, 241, 238), 0.15 + 0.5 * t))
    return img.resize((w, h), Image.LANCZOS)


def make_sheet():
    cells = {}
    parts = [('badge', draw_mei((88, 22), (138, 132, 156), plate_border=(214, 206, 220))),
             ('seam', draw_seam(32, 4)),
             ('label', draw_label(64, 44)),
             ('padlogo', draw_padlogo(24, 24)),
             ('rear', draw_rear(128, 24)),
             ('top', draw_top(128, 86))]
    W = 128
    x = y = rowh = 0
    placed = []
    for name, im in parts:
        if x + im.width > W:
            x, y, rowh = 0, y + rowh, 0
        placed.append((name, im, x, y))
        cells[name] = [x, y, im.width, im.height]
        x += im.width
        rowh = max(rowh, im.height)
    sheet = Image.new('RGB', (W, y + rowh), (0, 0, 0))
    for name, im, px, py in placed:
        sheet.paste(im, (px, py))
    (HERE / 'art').mkdir(exist_ok=True)
    sheet.save(HERE / 'art' / 'duet_sheet.png')
    (HERE / 'art' / 'duet_sheet.sheet.json').write_text(
        json.dumps({'format': 'mei-sheet', 'version': 1, 'cells': cells}, indent=1) + '\n')


# ---------------------------------------------------------------- geometry helpers

def r6(v):
    return round(v, 6)


def rounded_rect(hw, hd, r, per_corner):
    """Counter-clockwise (x right, z up, as the top view), starting at the front-right corner."""
    pts = []
    corners = [(hw - r, -hd + r, -90), (hw - r, hd - r, 0), (-hw + r, hd - r, 90), (-hw + r, -hd + r, 180)]
    for cx, cz, a0 in corners:
        for k in range(per_corner):
            a = math.radians(a0 + 90 * k / (per_corner - 1))
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def ring_body(rings, band_mats, bottom_mat, top_mat, uv_of=None):
    """A closed body from horizontal rings of equal point counts, counter-clockwise from above.

    rings: list of (y, [(x, z), ...]); band_mats[k] the material of the band between ring k and
    k+1 (a string, or a function of the segment index). Caps are single planar polygons."""
    verts, faces, mats, uvs = [], [], [], []
    n = len(rings[0][1])
    for k, (y, pts) in enumerate(rings):
        for i, (x, z) in enumerate(pts):
            verts.append([r6(x), r6(y), r6(z)])
            if uv_of:
                uvs.append(uv_of(x, y, z, k))
    for k in range(len(rings) - 1):
        for i in range(n):
            j = (i + 1) % n
            L0, L1, U0, U1 = k * n + i, k * n + j, (k + 1) * n + i, (k + 1) * n + j
            m = band_mats[k](i) if callable(band_mats[k]) else band_mats[k]
            faces += [[L0, U0, L1], [L1, U0, U1]]
            mats += [m, m]
    faces.append(list(range(n)))                       # bottom: counter-clockwise from above = down
    mats.append(bottom_mat)
    top0 = (len(rings) - 1) * n
    faces.append([top0 + i for i in reversed(range(n))])
    mats.append(top_mat)
    node = {'op': 'mesh', 'vertices': verts, 'faces': faces, 'face_materials': mats}
    if uv_of:
        node['uvs'] = [[r6(u), r6(v)] for u, v in uvs]
    return node


def box_mesh(cx, cy, cz, sx, sy, sz, mats):
    """A box as a mesh with a material per side: mats = dict(top, bottom, front(-Z), back(+Z), left, right)."""
    x0, x1, y0, y1, z0, z1 = cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, cz - sz / 2, cz + sz / 2
    v = [[x0, y1, z0], [x1, y1, z0], [x1, y0, z0], [x0, y0, z0],
         [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]
    v = [[r6(c) for c in p] for p in v]
    faces = {'front': [0, 1, 2, 3], 'back': [4, 5, 6, 7], 'left': [3, 4, 7, 0],
             'right': [1, 6, 5, 2], 'top': [7, 6, 1, 0], 'bottom': [3, 2, 5, 4]}
    use = [s for s in ('front', 'back', 'left', 'right', 'top', 'bottom') if mats.get(s)]
    return {'op': 'mesh', 'vertices': v, 'faces': [faces[s] for s in use],
            'face_materials': [mats[s] for s in use]}


def quad(corners, mat):
    """One quad; corners clockwise as seen from its front."""
    return {'op': 'mesh', 'vertices': [[r6(c) for c in p] for p in corners], 'faces': [[0, 1, 2, 3]],
            'material': mat}


def teardrop(length, width, n):
    """A drop outline in (x, z): round end at the origin side, tip toward +z. Counter-clockwise."""
    pts = []
    for k in range(n):
        t = 2 * math.pi * k / n
        z = -math.cos(t)                       # -1 .. 1, tip at t = pi
        x = math.sin(t) * abs(math.cos(t / 2)) ** 1.3
        pts.append((x, (z * 0.5 + 0.2) * length))
    xm = max(abs(p[0]) for p in pts)
    pts = [(x / xm * width / 2, z) for x, z in pts]
    # counter-clockwise from above: x right, z up
    a = sum(p[0] * q[1] - p[1] * q[0] for p, q in zip(pts, pts[1:] + pts[:1]))
    return pts if a > 0 else pts[::-1]


def offset_outline(pts, d):
    """Move each point of a counter-clockwise outline d inward along its averaged normal."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        def nrm(a, b):
            dx, dz = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dz)
            return (-dz / L, dx / L)           # left normal = inward for counter-clockwise
        a, b = nrm(p0, p1), nrm(p1, p2)
        m = (a[0] + b[0], a[1] + b[1])
        L = math.hypot(*m)
        m = (m[0] / L, m[1] / L)
        cosh = m[0] * a[0] + m[1] * a[1]
        out.append((p1[0] + m[0] * d / cosh, p1[1] + m[1] * d / cosh))
    return out


def chaikin(pts, it):
    for _ in range(it):
        q = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            q.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
            q.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
        pts = q
    return pts


def node(id_, n, **kw):
    out = {'id': id_}
    out.update(n)
    out.update(kw)
    return out


def tf(translate=None, rotate=None, scale=None):
    t = {}
    if scale:
        t['scale'] = [r6(s) for s in scale]
    if rotate:
        t['rotate'] = rotate
    if translate:
        t['translate'] = [r6(s) for s in translate]
    return t


VERIFY = {'required': True, 'depth': True, 'perspective': True}


# ---------------------------------------------------------------- console

def console():
    HW, HD, R = 0.140, 0.104, 0.050        # 28 x 20.8 cm
    PC = 6                                  # points per corner
    TOP = 0.078
    profile = [  # (y, inset)
        (0.000, 0.015), (0.005, 0.006), (0.011, 0.0015), (0.016, 0.0),
        (0.019, 0.0), (0.054, 0.0), (0.064, 0.003), (0.071, 0.009),
        (0.0758, 0.018), (TOP, 0.030)]
    rings = [(y, rounded_rect(HW - d, HD - d, R - d, PC)) for y, d in profile]
    bands = ['under', 'under', 'shell_lo', 'seam', 'shell', 'shell', 'shell', 'shell', 'shell']

    assert abs(HW - 0.030 - TOP_X) < 1e-9 and abs(HD - 0.030 - TOP_Z) < 1e-9

    def uv(x, y, z, k):
        if k == len(profile) - 1:           # the top: the printed bounce trails
            return ((x + TOP_X) / (2 * TOP_X), (TOP_Z - z) / (2 * TOP_Z))
        return (min(1, max(0, (x + HW) / (2 * HW))), 0.0 if k <= 3 else 1.0)

    body = ring_body(rings, bands, 'under', 'shell_top', uv_of=uv)

    nodes = [node('body', body)]

    # the cart slot: a soft collar near the back, its dark mouth and a cart standing in it
    SZ = 0.040
    collar_prof = [(TOP - 0.004, 0.0), (TOP + 0.006, 0.0015), (TOP + 0.0105, 0.006)]
    crings = [(y, [(x, z + SZ) for x, z in rounded_rect(0.074 - d, 0.025 - d, 0.023 - d, 6)])
              for y, d in collar_prof]
    nodes.append(node('slot_collar', ring_body(crings, ['shell', 'shell'], 'shell', 'shell_flat')))
    mouth_top = TOP + 0.0105 + 0.0012
    nodes.append(node('slot_mouth', box_mesh(0, mouth_top - 0.002, SZ, 0.116, 0.004, 0.022,
                                              {'top': 'slot_dark', 'front': 'slot_dark', 'back': 'slot_dark',
                                               'left': 'slot_dark', 'right': 'slot_dark'})))
    # cart: an extrusion in XY, rounded shoulders and a grip notch at each side
    cw, ch, ct = 0.104, 0.064, 0.016
    base = TOP - 0.002
    cart_pts = [(-cw / 2, 0), (cw / 2, 0), (cw / 2, ch - 0.016), (cw / 2 - 0.003, ch - 0.006),
                (cw / 2 - 0.010, ch), (-cw / 2 + 0.010, ch), (-cw / 2 + 0.003, ch - 0.006),
                (-cw / 2, ch - 0.016)]
    nodes.append(node('cart', {'op': 'extrude', 'points': [[r6(x), r6(y)] for x, y in cart_pts],
                               'depth': ct, 'material': 'cart'},
                      transform=tf(translate=[0, base, SZ])))
    # label on the cart's front face, 1.2 mm proud; and a grip ridge band on the top
    lz = SZ - ct / 2 - 0.0012
    ly0, ly1 = base + 0.019, base + 0.056
    nodes.append(node('cart_label', quad([[-0.042, ly1, lz], [0.042, ly1, lz],
                                          [0.042, ly0, lz], [-0.042, ly0, lz]], 'label')))
    # rear of the cart: three raised ribs
    nodes.append(node('cart_ribs', {'op': 'group', 'children': [
        node('rib', {'op': 'box', 'size': [0.070, 0.003, 0.003], 'material': 'cart_dark'},
             transform=tf(translate=[0, base + 0.040, SZ + ct / 2]))],
        'modifiers': [{'op': 'array', 'count': 2, 'step': [0, 0.009, 0]}]}))

    # power (sun-drop) and reset (moon-drop): domed drops on soft dishes, tips toward each other
    for side, name, mat, rim in ((-1, 'power', 'sun', 'sun_rim'), (1, 'reset', 'moon', 'moon_rim')):
        px, pz = side * 0.092, -0.054
        ang = side * 58                # tips turned in, toward each other
        dish = teardrop(0.050, 0.034, 10)
        dome = teardrop(0.040, 0.026, 10)
        sec = [{'y': r6(TOP - 0.002), 'points': [[r6(x), r6(z)] for x, z in dish]},
               {'y': r6(TOP + 0.0018), 'points': [[r6(x), r6(z)] for x, z in dish]}]
        nodes.append(node(name + '_dish', {'op': 'loft', 'sections': sec, 'material': rim},
                          transform=tf(rotate=[0, ang, 0], translate=[px, 0, pz])))
        dsec = []
        for y, s in ((TOP - 0.001, 1.0), (TOP + 0.0055, 0.86), (TOP + 0.0085, 0.52)):
            dsec.append({'y': r6(y), 'points': [[r6(x * s), r6(z * s + (1 - s) * 0.004)] for x, z in dome]})
        nodes.append(node(name, {'op': 'loft', 'sections': dsec, 'material': mat},
                          transform=tf(rotate=[0, ang, 0], translate=[px, 0, pz])))

    # the nameplate: a raised pearl badge printed with the logo
    brings = [(y, [(x, z - 0.066) for x, z in rounded_rect(0.044, 0.011, 0.0095, 4)])
              for y in (TOP - 0.002, TOP + 0.0014)]
    nodes.append(node('badge', ring_body(brings, ['badge_rim'], 'badge_rim', 'badge')))

    # front: two controller ports below two memory card slots, sun and moon dots
    FZ = -HD
    for side, dot in ((-1, 'sun'), (1, 'moon')):
        x = side * 0.046
        nodes.append(node(f'port_{side + 1 and 2 or 1}', {'op': 'cylinder', 'radius': 1, 'height': 0.006,
                                                          'segments': 8, 'material': 'port_rim'},
                          transform=tf(scale=[0.0165, 1, 0.0085], rotate=[-90, 0, 0],
                                       translate=[x, 0.031, FZ - 0.0005])))
        nodes.append(node(f'port_{side + 1 and 2 or 1}_socket', {'op': 'cylinder', 'radius': 1, 'height': 0.006,
                                                                 'segments': 8, 'material': 'slot_dark'},
                          transform=tf(scale=[0.0125, 1, 0.0052], rotate=[-90, 0, 0],
                                       translate=[x, 0.031, FZ - 0.0012])))
        nodes.append(node(f'card_{side + 1 and 2 or 1}', box_mesh(x, 0.0455, FZ - 0.0005, 0.040, 0.0075, 0.007,
                                                                  {k: 'port_rim' for k in ('front', 'top', 'bottom', 'left', 'right')})))
        nodes.append(node(f'card_{side + 1 and 2 or 1}_mouth', box_mesh(x, 0.0455, FZ - 0.0012, 0.032, 0.0026, 0.007,
                                                                        {k: 'slot_dark' for k in ('front', 'top', 'bottom', 'left', 'right')})))
        nodes.append(node(f'dot_{side + 1 and 2 or 1}', {'op': 'cylinder', 'radius': 0.0022, 'height': 0.004,
                                                         'segments': 6, 'material': dot},
                          transform=tf(rotate=[-90, 0, 0], translate=[side * 0.016, 0.031, FZ - 0.0002])))

    # rear: DC in, AV out, the MeiNet antenna socket, their printed labels, and vents
    BZ = HD
    RX, RY0, RY1 = 0.088, 0.021, 0.052
    nodes.append(node('rear_panel', quad([[RX, RY1, BZ + 0.0012], [-RX, RY1, BZ + 0.0012],
                                          [-RX, RY0, BZ + 0.0012], [RX, RY0, BZ + 0.0012]], 'rear')))
    nodes.append(node('dc_in', {'op': 'cylinder', 'radius': 0.0055, 'height': 0.008, 'segments': 6,
                                'material': 'slot_dark'},
                      transform=tf(rotate=[90, 0, 0], translate=[0.040, 0.033, BZ + 0.001])))
    nodes.append(node('av_out', box_mesh(0, 0.033, BZ + 0.001, 0.026, 0.009, 0.008,
                                         {k: 'slot_dark' for k in ('back', 'top', 'bottom', 'left', 'right')})))
    nodes.append(node('antenna_in', {'op': 'cylinder', 'radius': 0.0045, 'height': 0.016, 'segments': 6,
                                     'material': 'metal'},
                      transform=tf(rotate=[90, 0, 0], translate=[-0.040, 0.033, BZ + 0.005])))
    # a little MeiNet light beside the badge
    nodes.append(node('meinet_led', {'op': 'cylinder', 'radius': 0.0024, 'height': 0.004, 'segments': 6,
                                     'material': 'moon_glow'},
                      transform=tf(translate=[0.056, TOP, -0.066])))

    return {
        'format': 'mei-asset', 'version': 1, 'name': 'duet_white_console',
        'budget': {'vertices': 800, 'triangles': 1200},
        'sheets': {'duet': {'image': 'art/duet_sheet.png'}},
        'materials': {
            'shell': {'color': PEARL, 'smooth': True},
            'shell_top': {'color': PEARL, 'texture': {'sheet': 'duet', 'cell': 'top', 'bits': 8, 'projection': 'fit'}},
            'shell_flat': {'color': PEARL},
            'shell_lo': {'color': '#e9e4e6', 'smooth': True},
            'under': {'color': '#bdb6c6', 'smooth': True},
            'seam': {'color': '#f0d8c8', 'texture': {'sheet': 'duet', 'cell': 'seam', 'bits': 8, 'projection': 'fit'}},
            'slot_dark': {'color': '#4a4558'},
            'cart': {'color': '#ddd7e8'},
            'cart_dark': {'color': '#c4bcd4'},
            'label': {'color': '#c8d8f0', 'texture': {'sheet': 'duet', 'cell': 'label', 'bits': 8, 'projection': 'fit'}},
            'sun': {'color': hexc(SUN), 'smooth': True},
            'moon': {'color': hexc(MOON), 'smooth': True},
            'sun_rim': {'color': '#f6dcc4'},
            'moon_rim': {'color': '#d6e2f6'},
            'badge': {'color': PEARL, 'texture': {'sheet': 'duet', 'cell': 'badge', 'bits': 8, 'projection': 'fit'}},
            'port_rim': {'color': '#dcd6e0'},
            'badge_rim': {'color': '#e6e0e8'},
            'rear': {'color': '#e8e4e8', 'texture': {'sheet': 'duet', 'cell': 'rear', 'bits': 8, 'projection': 'fit'}},
            'metal': {'color': '#c8c6c0'},
            'vent': {'color': '#8e879c'},
            'moon_glow': {'color': '#8fc4ff', 'class': 'emissive'},
        },
        'verification': VERIFY,
        'nodes': nodes,
    }


# ---------------------------------------------------------------- controller

def controller():
    right = [(0.024, -0.024), (0.038, -0.050), (0.056, -0.067), (0.074, -0.058), (0.081, -0.022),
             (0.076, 0.013), (0.058, 0.033)]
    ctrl = [(0.0, -0.016)] + right + [(0.0, 0.039)] + [(-x, z) for x, z in reversed(right)]
    outline = chaikin(ctrl, 1)
    TOP = 0.026
    profile = [(0.000, 0.0060), (0.0105, 0.0), (0.0130, 0.0), (0.020, 0.0016), (TOP, 0.0062)]
    rings = [(y, offset_outline(outline, d)) for y, d in profile]
    xmax = max(abs(x) for x, z in outline)

    def uv(x, y, z, k):                     # the Duet line round the waist, as on the console
        return (min(1, max(0, (x + xmax) / (2 * xmax))), 0.0 if k <= 1 else 1.0)

    body = ring_body(rings, ['pad_lo', 'seam', 'pad', 'pad'], 'pad_lo', 'pad_top', uv_of=uv)
    nodes = [node('body', body)]

    # grip bulbs under each grip: half ellipsoids pointing down, open tops inside the body
    for side in (-1, 1):
        nodes.append(node(f'grip_{"l" if side < 0 else "r"}',
                          {'op': 'lathe', 'profile': [[0, -1], [0.62, -0.72], [0.93, -0.32], [1, 0]],
                           'segments': 6, 'caps': False, 'material': 'pad_lo'},
                          transform=tf(scale=[0.014, 0.010, 0.020], rotate=[0, side * 18, 0],
                                       translate=[side * 0.060, 0.004, -0.042])))

    def lift(y):
        return r6(y)

    # d-pad: a soft dish and a cross
    DX, DZ = -0.052, 0.010
    nodes.append(node('dpad_dish', {'op': 'cylinder', 'radius': 0.0165, 'height': 0.003, 'segments': 8,
                                    'material': 'dish'},
                      transform=tf(translate=[DX, TOP - 0.0003, DZ])))
    a, b = 0.0042, 0.0125
    cross = [(a, -b), (a, -a), (b, -a), (b, a), (a, a), (a, b), (-a, b), (-a, a), (-b, a), (-b, -a), (-a, -a), (-a, -b)]
    nodes.append(node('dpad', {'op': 'extrude', 'points': [[r6(x), r6(y)] for x, y in cross], 'depth': 0.006,
                               'material': 'keys'},
                      transform=tf(rotate=[90, 0, 0], translate=[DX, TOP + 0.002, DZ])))

    # A B X Y: a diamond, warm buttons up and right (X, A), cool down and left (Y, B)
    BX, BZ, sp = 0.052, 0.010, 0.0115
    for nm, dx, dz, mat in (('btn_a', sp, 0, 'sun'), ('btn_x', 0, sp, 'peach'),
                            ('btn_y', -sp, 0, 'sky'), ('btn_b', 0, -sp, 'moon')):
        nodes.append(node(nm, {'op': 'lathe', 'profile': [[0.0056, -0.002], [0.0050, 0.0036], [0, 0.0047]],
                               'segments': 8, 'caps': False, 'material': mat},
                          transform=tf(translate=[BX + dx, TOP, BZ + dz])))
    nodes.append(node('abxy_dish', {'op': 'cylinder', 'radius': 0.0205, 'height': 0.003, 'segments': 8,
                                    'material': 'dish'},
                      transform=tf(translate=[BX, TOP - 0.0003, BZ])))

    # the analog stick, inboard of the left grip
    SX, SZ = -0.028, -0.014
    nodes.append(node('stick', {'op': 'lathe', 'profile': [[0.0098, -0.001], [0.0072, 0.0034], [0.0034, 0.0044],
                                                           [0.0034, 0.0086], [0.0088, 0.0108], [0.0060, 0.0129],
                                                           [0, 0.0133]],
                                'segments': 8, 'caps': False, 'material': 'keys'},
                      transform=tf(translate=[SX, TOP, SZ])))

    # Start and Select: two small pills in the middle
    for nm, x in (('select', -0.011), ('start', 0.011)):
        nodes.append(node(nm, {'op': 'cylinder', 'radius': 1, 'height': 0.004, 'segments': 6, 'material': 'keys'},
                          transform=tf(scale=[0.0058, 1, 0.0027], rotate=[0, -20 if x < 0 else 20, 0],
                                       translate=[x, TOP + 0.0005, 0.000])))

    # the logo above them
    lz = 0.019
    s = 0.009
    nodes.append(node('logo', quad([[-s, TOP + 0.0008, lz - s], [-s, TOP + 0.0008, lz + s],
                                    [s, TOP + 0.0008, lz + s], [s, TOP + 0.0008, lz - s]], 'padlogo')))

    # L and R: soft shoulder buttons on the far edge
    for side in (-1, 1):
        nodes.append(node('shoulder_' + ('l' if side < 0 else 'r'),
                          {'op': 'sphere', 'radius': 1, 'rings': 4, 'segments': 6, 'material': 'shoulder'},
                          transform=tf(scale=[0.024, 0.0068, 0.0085], rotate=[0, side * 24, 0],
                                       translate=[side * 0.054, 0.0165, 0.0290])))

    # the cord, leaving the far edge in the middle
    nodes.append(node('cord_boot', {'op': 'cylinder', 'radius': 0.0042, 'height': 0.012, 'segments': 6,
                                    'material': 'pad_lo'},
                      transform=tf(rotate=[90, 0, 0], translate=[0, 0.013, 0.040])))
    nodes.append(node('cord', {'op': 'cylinder', 'radius': 0.0024, 'height': 0.022, 'segments': 6,
                               'material': 'cord'},
                      transform=tf(rotate=[100, 0, 0], translate=[0, 0.0105, 0.055])))

    return {
        'format': 'mei-asset', 'version': 1, 'name': 'duet_white_controller',
        'budget': {'vertices': 600, 'triangles': 820},
        'sheets': {'duet': {'image': 'art/duet_sheet.png'}},
        'materials': {
            'pad': {'color': PEARL, 'smooth': True},
            'pad_top': {'color': PEARL},
            'pad_lo': {'color': '#e6e1e6', 'smooth': True},
            'dish': {'color': '#e2dce8'},
            'keys': {'color': '#b4aec6', 'smooth': True},
            'shoulder': {'color': '#d4cede', 'smooth': True},
            'sun': {'color': hexc(SUN), 'smooth': True},
            'moon': {'color': hexc(MOON), 'smooth': True},
            'peach': {'color': '#ffc08e', 'smooth': True},
            'sky': {'color': '#a9c8f6', 'smooth': True},
            'cord': {'color': '#d8d2dc', 'smooth': True},
            'seam': {'color': '#f0d8c8', 'texture': {'sheet': 'duet', 'cell': 'seam', 'bits': 8, 'projection': 'fit'}},
            'padlogo': {'color': PEARL, 'texture': {'sheet': 'duet', 'cell': 'padlogo', 'bits': 8, 'projection': 'fit'}},
        },
        'verification': VERIFY,
        'nodes': nodes,
    }


def write(name, recipe):
    (HERE / name).write_text(json.dumps(recipe, indent=1) + '\n')


if __name__ == '__main__':
    make_sheet()
    write('console.asset.json', console())
    write('controller.asset.json', controller())
