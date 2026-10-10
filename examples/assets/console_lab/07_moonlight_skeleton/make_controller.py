"""Moonlight Skeleton controller: paints art/pad_*.png and writes controller.asset.json.

python3 make_controller.py   (needs Pillow and the macOS Hiragino font for the 明 mark)
Model in metres, real size. It lies face up; the grips point toward -Z (the player), the
shoulder buttons and the cable toward +Z.
"""
import json, math, random
from mlib import *

# Right half of the plan outline (x, z), from the top centre round to the bottom centre.
HALF = [(0.000, 0.0440), (0.046, 0.0428), (0.060, 0.0395), (0.070, 0.0320),
        (0.0755, 0.0200), (0.0775, 0.0030), (0.0740, -0.0260),
        (0.0685, -0.0430), (0.0610, -0.0540), (0.0515, -0.0590), (0.0420, -0.0580),
        (0.0345, -0.0520), (0.0290, -0.0420), (0.0230, -0.0330), (0.0130, -0.0280),
        (0.000, -0.0265)]
OUTLINE = HALF[:-1] + [(-x, z) for x, z in reversed(HALF[1:])]   # clockwise seen from above
# rings: (inset, y); top cap at the last
RINGS = [(0.0055, 0.006), (0.0, 0.0140), (0.0, 0.0250), (0.003, 0.0310), (0.0075, 0.0335)]
YTOP = RINGS[-1][1]

DPAD = (-0.0505, 0.0095)
FACE = (0.0505, 0.0095)
STICK = (0.0, -0.0070)
SEL, START = (-0.0115, 0.0185), (0.0115, 0.0185)
BTN = {'y': (0.0, 0.0122), 'a': (0.0, -0.0122), 'x': (-0.0122, 0.0), 'b': (0.0122, 0.0)}
BTN_COL = {'a': (240, 214, 140), 'b': (182, 208, 255), 'x': (200, 186, 255), 'y': (236, 240, 250)}


def offset(points, d):
    """Offset a closed outline inward by d (miter joins). Works out the winding itself."""
    area = sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1]
               for i in range(len(points)))
    sgn = 1 if area > 0 else -1     # +1: counter-clockwise in (x, z)
    out = []
    n = len(points)
    for i in range(n):
        p0, p1, p2 = points[i - 1], points[i], points[(i + 1) % n]
        def nrm(a, b):
            dx, dz = b[0] - a[0], b[1] - a[1]
            l = math.hypot(dx, dz)
            return (-dz / l * sgn, dx / l * sgn)   # inward normal
        n1, n2 = nrm(p0, p1), nrm(p1, p2)
        bx, bz = n1[0] + n2[0], n1[1] + n2[1]
        bl = math.hypot(bx, bz)
        bx, bz = bx / bl, bz / bl
        cosh = bx * n1[0] + bz * n1[1]
        out.append((p1[0] + bx * d / cosh, p1[1] + bz * d / cosh))
    return out


CAP = offset(OUTLINE, RINGS[-1][0])
CUM = [0.0]
for _i in range(1, len(OUTLINE) + 1):
    _a, _b = OUTLINE[_i - 1], OUTLINE[_i % len(OUTLINE)]
    CUM.append(CUM[-1] + math.hypot(_b[0] - _a[0], _b[1] - _a[1]))
PERIM = CUM.pop()
SCREWS = [(-0.054, -0.040), (0.054, -0.040), (-0.034, 0.032), (0.034, 0.032)]


def outline_at(s_):
    """The outline point at arc length s_."""
    s_ %= PERIM
    for i in range(len(OUTLINE)):
        s0 = CUM[i]
        s1 = CUM[i + 1] if i + 1 < len(CUM) else PERIM
        if s_ <= s1:
            t = (s_ - s0) / (s1 - s0)
            a, b = OUTLINE[i], OUTLINE[(i + 1) % len(OUTLINE)]
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    return OUTLINE[0]


def paint_wall():
    y0, y1 = RINGS[1][1], RINGS[2][1]
    p = Painter(255, 12, 0, PERIM, y1, y0, INDIGO)
    step = PERIM / 255
    for k in range(255):
        x, z = outline_at((k + 0.5) * step)
        s_ = k * step
        # the board's edge where the board comes near the wall
        if -0.024 < z and abs(x) < 0.070:
            p.rect(s_, 0.0205, s_ + step, 0.0180, GHOST, alpha=200)
            p.rect(s_, 0.0180, s_ + step, 0.0172, GHOST_LINE, alpha=120)
        # the hollow grips: the far wall of the grip, darker, low down
        if z < -0.024:
            p.rect(s_, 0.0175, s_ + step, y0, INDIGO_DEEP, alpha=110)
        for sx, sz in SCREWS:
            d = math.hypot(x - sx, z - sz)
            if d < 0.016:
                p.rect(s_, y1, s_ + step, y0, LAVENDER, alpha=int(110 * (1 - d / 0.016)))
        if abs(x) < 0.006 and z > 0:      # the wires leaving
            p.rect(s_, 0.0215, s_ + step, 0.0185, (170, 70, 130), alpha=170)
    p.rect(0, y1, PERIM, y1 - 0.0010, INDIGO_EDGE, alpha=200)
    p.finish().save(ART / 'pad_wall.png')
CX0, CX1 = min(p[0] for p in CAP), max(p[0] for p in CAP)
CZ0, CZ1 = min(p[1] for p in CAP), max(p[1] for p in CAP)

# =============================== textures ===================================================

def paint_top():
    w = int(round((CX1 - CX0) * 1300))
    h = int(round((CZ1 - CZ0) * 1300))
    p = Painter(w, h, CX0, CX1, CZ1, CZ0, INDIGO)
    rnd = random.Random(5)
    # the shell's own edge: darker just inside, where the wall is seen edge on
    p.poly(CAP, INDIGO)
    p.line(CAP + CAP[:1], INDIGO_DEEP, 0.0016, 150)
    # the board: across the middle, into the tops of the grips
    board = [(-0.064, 0.034), (0.064, 0.034), (0.068, 0.010), (0.062, -0.022), (0.040, -0.030),
             (0.022, -0.024), (-0.022, -0.024), (-0.040, -0.030), (-0.062, -0.022), (-0.068, 0.010)]
    p.poly(board, GHOST, alpha=215)
    for _ in range(30):
        a = (rnd.uniform(-0.060, 0.060), rnd.uniform(-0.020, 0.030))
        b = (rnd.uniform(-0.060, 0.060), rnd.uniform(-0.020, 0.030))
        p.line([a, (b[0], a[1]), b], GHOST_LINE, 0.0004, 100)
    # the cable's wires, coloured, through the indigo: from the exit to the board's header
    wires = [(170, 70, 130), (220, 220, 245), (40, 40, 70), (100, 170, 230), (220, 190, 100)]
    for k, c in enumerate(wires):
        x = -0.0036 + k * 0.0018
        p.line([(x * 0.5, 0.046), (x * 0.5, 0.040), (x * 1.6 + 0.012, 0.031), (x * 1.6 + 0.012, 0.0265)], c, 0.0010, 235)
    p.rect(0.0035, 0.0275, 0.0205, 0.0245, LAVENDER, alpha=170)     # the header
    # contact pads under the buttons: rings that halo each button
    for dx, dz in [(0.0, 0.0105), (0.0, -0.0105), (0.0105, 0.0), (-0.0105, 0.0)]:
        p.circle(DPAD[0] + dx, DPAD[1] + dz, 0.0062, INDIGO_DEEP, alpha=180)
        p.circle(DPAD[0] + dx, DPAD[1] + dz, 0.0042, (14, 12, 40), alpha=220)
    for k, (dx, dz) in BTN.items():
        p.circle(FACE[0] + dx, FACE[1] + dz, 0.0078, INDIGO_DEEP, alpha=180)
        p.circle(FACE[0] + dx, FACE[1] + dz, 0.0068, LAVENDER, alpha=80)
    for x, z in (SEL, START):
        p.rrect(x - 0.0060, z + 0.0030, x + 0.0060, z - 0.0030, 0.003, INDIGO_DEEP, alpha=200)
    # the stick's gimbal: a square module and its two potentiometers
    sx, sz = STICK
    p.rect(sx - 0.0135, sz + 0.0135, sx + 0.0135, sz - 0.0135, (14, 12, 40), alpha=200)
    p.rect(sx + 0.0135, sz + 0.006, sx + 0.0175, sz - 0.006, LAVENDER, alpha=150)
    p.rect(sx - 0.006, sz - 0.0135, sx + 0.006, sz - 0.0175, LAVENDER, alpha=150)
    # screw posts: one in each grip, two at the top
    for x, z in SCREWS:
        p.circle(x, z, 0.0050, INDIGO_EDGE, alpha=210)
        p.circle(x, z, 0.0030, LAVENDER, alpha=170)
        p.circle(x, z, 0.0013, INDIGO_DEEP)
    # print: the d-pad's well, a dotted orbit round the stick
    p.circle(DPAD[0], DPAD[1], 0.0165, None, outline=MOON, width=0.0006, alpha=200)
    for k in range(24):
        a = math.radians(k * 15)
        p.circle(sx + 0.0175 * math.cos(a), sz + 0.0175 * math.sin(a), 0.0005, MOON, alpha=230)
    # gloss
    p.sheen([(-0.070, 0.045), (-0.050, 0.045), (-0.010, -0.060), (-0.030, -0.060)], 36)
    p.sheen([(0.020, 0.045), (0.028, 0.045), (0.068, -0.060), (0.060, -0.060)], 26)
    img = p.finish()
    for (x, z), s in [(SEL, 'SELECT'), (START, 'START')]:
        tx, ty = p.texel(x, z - 0.0045)
        pixel_text(img, tx, ty, s, MOON, center=True)
    tx, ty = p.texel(0.0, 0.0335)
    img = logo(img, tx, ty, 9)
    img.save(ART / 'pad_top.png')


def paint_buttons():
    from PIL import Image, ImageDraw, ImageFont
    for k, col in BTN_COL.items():
        ss = 8
        im = Image.new('RGB', (16 * ss, 16 * ss), col)
        d = ImageDraw.Draw(im)
        d.ellipse([ss * 1.5, ss * 1.5, ss * 14.5, ss * 14.5], fill=mix(col, (255, 255, 255), 0.35))
        f = ImageFont.truetype('/System/Library/Fonts/Avenir Next.ttc', 11 * ss, index=2)
        d.text((8 * ss, 8.4 * ss), k.upper(), font=f, fill=(40, 30, 110), anchor='mm')
        im.resize((16, 16), Image.BOX).save(ART / ('pad_btn_%s.png' % k))
    # the stick's cap: the full moon, its maria and craters
    p = Painter(24, 24, -0.0095, 0.0095, 0.0095, -0.0095, (60, 60, 120))
    p.circle(0, 0, 0.0095, (236, 236, 222))
    for x, z, r in [(-0.003, 0.003, 0.0032), (0.0025, 0.0015, 0.0022), (0.001, -0.0035, 0.0026),
                    (-0.0045, -0.002, 0.0015)]:
        p.circle(x, z, r, (196, 198, 196))
    for x, z, r in [(0.0045, -0.004, 0.0009), (-0.001, 0.0055, 0.0008), (0.0055, 0.004, 0.0007)]:
        p.circle(x, z, r, (176, 178, 180))
    p.circle(0, 0, 0.0095, None, outline=(200, 204, 230), width=0.0008)
    p.finish().save(ART / 'pad_moon.png')
    # the d-pad's top: arrows and a dimple
    p = Painter(24, 24, -0.0120, 0.0120, 0.0120, -0.0120, SILVER)
    for ang in range(0, 360, 90):
        a = math.radians(ang)
        c, s_ = math.cos(a), math.sin(a)
        tip, base, half = 0.0098, 0.0068, 0.0022
        pts = [(c * tip, s_ * tip), (c * base - s_ * half, s_ * base + c * half),
               (c * base + s_ * half, s_ * base - c * half)]
        p.poly(pts, (120, 116, 170))
    p.circle(0, 0, 0.0030, (170, 176, 204))
    p.finish().save(ART / 'pad_dpad.png')

# =============================== geometry ===================================================

def body_nodes():
    shell = MeshBuilder('body')
    top = MeshBuilder('face_plate', uv=True)
    wall = MeshBuilder('wall', uv=True)
    rings = []
    for inset, y in RINGS:
        pts = offset(OUTLINE, inset) if inset else OUTLINE
        rings.append([(x, y, z) for x, z in pts])
    mats = ['pad_under', 'pad_wall', 'pad_bevel', 'pad_bevel']
    n = len(OUTLINE)
    for b in range(len(RINGS) - 1):
        lo, hi = rings[b], rings[b + 1]
        for i in range(n):
            j = (i + 1) % n
            # outward: the edge's normal in plan, away from the inside
            ex, ez = OUTLINE[j][0] - OUTLINE[i][0], OUTLINE[j][1] - OUTLINE[i][1]
            out = [-ez, (sum(p[1] for p in (lo[i], hi[i])) / 2 - 0.018) * 0.3, ex]
            # OUTLINE runs clockwise seen from above (+X right, +Z up): its left normal points out
            if b == 1:   # the wall: a band texture along the outline
                ui, uj = CUM[i] / PERIM, (CUM[j] / PERIM if j else 1.0)
                wall.face([lo[i], lo[j], hi[j], hi[i]], 'pad_wall', out, [(ui, 1), (uj, 1), (uj, 0), (ui, 0)])
                continue
            shell.face([lo[i], lo[j], hi[j]], mats[b], out)
            shell.face([lo[i], hi[j], hi[i]], mats[b], out)
    shell.face(rings[0], 'pad_under', [0, -1, 0])
    uvs = [((x - CX0) / (CX1 - CX0), (CZ1 - z) / (CZ1 - CZ0)) for x, y, z in rings[-1]]
    top.face(rings[-1], 'pad_top', [0, 1, 0], uvs)
    return [top.node(), wall.node(), shell.node()]


def dpad_node():
    arm, half, y0, y1 = 0.0118, 0.0039, YTOP - 0.002, YTOP + 0.0040
    cx, cz = DPAD
    q = [(half, arm), (half, half), (arm, half), (arm, -half), (half, -half), (half, -arm),
         (-half, -arm), (-half, -half), (-arm, -half), (-arm, half), (-half, half), (-half, arm)]
    mb = MeshBuilder('dpad', uv=True)
    topp = [(cx + x, y1, cz + z) for x, z in q]
    uvs = [((x + 0.012) / 0.024, (0.012 - z) / 0.024) for x, z in q]
    mb.face(topp, 'pad_dpad', [0, 1, 0], uvs)
    for i in range(len(q)):
        j = (i + 1) % len(q)
        a, b = q[i], q[j]
        out = [b[1] - a[1], 0, -(b[0] - a[0])]
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if out[0] * mid[0] + out[2] * mid[1] < 0:
            out = [-out[0], 0, -out[2]]
        mb.face([(cx + a[0], y0, cz + a[1]), (cx + b[0], y0, cz + b[1]), (cx + b[0], y1, cz + b[1]),
                 (cx + a[0], y1, cz + a[1])], 'silver_side', out)
    return mb.node()


def shoulder_outline():
    """A bumper following the outline's far corner: outside it by 4 mm, inside by 4 mm."""
    n = len(OUTLINE)
    outer, inner = [], []
    for i in range(1, 5):
        p0, p1, p2 = OUTLINE[i - 1], OUTLINE[i], OUTLINE[(i + 1) % n]
        tx, tz = p2[0] - p0[0], p2[1] - p0[1]
        l = math.hypot(tx, tz)
        nx, nz = -tz / l, tx / l          # outward (the outline runs clockwise from above)
        outer.append((p1[0] + nx * 0.0040, p1[1] + nz * 0.0040))
        inner.append((p1[0] - nx * 0.0045, p1[1] - nz * 0.0045))
    return outer + list(reversed(inner))


def build():
    nodes = body_nodes()
    # grip bulbs underneath
    for k, sx in enumerate((-1, 1)):
        nodes.append({'id': 'grip_%s' % ('l' if sx < 0 else 'r'), 'op': 'sphere', 'radius': 1.0,
                      'rings': 4, 'segments': 8, 'material': 'pad_grip',
                      'transform': {'scale': [0.0200, 0.0160, 0.0270], 'rotate': [0, -18 * sx, 0],
                                    'translate': [0.0540 * sx, 0.0160, -0.0340]}})
    # d-pad and its well
    nodes.append({'id': 'dpad_well', 'op': 'lathe', 'segments': 12, 'caps': False, 'material': 'well',
                  'profile': [[0.0150, YTOP - 0.0020], [0.0150, YTOP + 0.0007], [0.0, YTOP + 0.0009]],
                  'transform': {'translate': [DPAD[0], 0, DPAD[1]]}})
    nodes.append(dpad_node())
    # face buttons
    for k, (dx, dz) in BTN.items():
        nodes.append({'id': 'btn_' + k, 'op': 'cylinder', 'radius': 0.0056, 'height': 0.0070, 'segments': 8,
                      'material': 'btn_' + k,
                      'transform': {'translate': [FACE[0] + dx, YTOP + 0.0005, FACE[1] + dz]}})
    # start and select pills
    for name, (x, z) in (('select', SEL), ('start', START)):
        nodes.append({'id': name, 'op': 'cylinder', 'radius': 0.0026, 'height': 0.0035, 'segments': 6,
                      'material': 'silver', 'transform': {'scale': [1.9, 1, 1], 'rotate': [0, -20 if x < 0 else 20, 0],
                                                          'translate': [x, YTOP + 0.0004, z]}})
    # the analog stick: gasket, shaft and the full-moon cap
    sx, sz = STICK
    nodes.append({'id': 'stick_gasket', 'op': 'lathe', 'segments': 12, 'caps': False, 'material': 'well',
                  'profile': [[0.0128, YTOP - 0.002], [0.0120, YTOP + 0.0016], [0.0, YTOP + 0.0034]],
                  'transform': {'translate': [sx, 0, sz]}})
    nodes.append({'id': 'stick_shaft', 'op': 'cylinder', 'radius': 0.0042, 'height': 0.0090, 'segments': 6, 'caps': False,
                  'material': 'well', 'transform': {'translate': [sx, YTOP + 0.0060, sz]}})
    nodes.append({'id': 'stick_cap', 'op': 'lathe', 'segments': 12, 'material': 'pad_moon', 'caps': False,
                  'profile': [[0.0, YTOP + 0.0080], [0.0095, YTOP + 0.0092], [0.0088, YTOP + 0.0118], [0.0, YTOP + 0.0130]],
                  'transform': {'translate': [sx, 0, sz]}})
    # shoulder buttons, on the far edge
    band = shoulder_outline()
    for name, sgn in (('l', -1), ('r', 1)):
        pts = [[round(sgn * x, 6), round(z, 6)] for x, z in band]
        if sgn < 0:
            pts.reverse()
        nodes.append({'id': 'shoulder_' + name, 'op': 'extrude', 'points': pts, 'depth': 0.0080,
                      'material': 'shoulder', 'transform': {'rotate': [90, 0, 0], 'translate': [0, 0.0230, 0]}})
    # the cable's strain relief
    nodes.append({'id': 'cable_relief', 'op': 'cylinder', 'radius': 0.0034, 'height': 0.016, 'segments': 6,
                  'material': 'cable', 'transform': {'rotate': [90, 0, 0], 'translate': [0, 0.0190, 0.0475]}})
    return nodes


def recipe():
    mats = {
        'pad_top': {'color': hexc(INDIGO), 'texture': {'image': 'art/pad_top.png', 'bits': 8, 'projection': 'fit'}},
        'pad_wall': {'color': hexc(INDIGO), 'smooth': True,
                     'texture': {'image': 'art/pad_wall.png', 'bits': 8, 'projection': 'fit'}},
        'pad_bevel': {'color': hexc(INDIGO_EDGE), 'smooth': True},
        'pad_under': {'color': hexc(INDIGO_DEEP), 'smooth': True},
        'pad_grip': {'color': hexc(mix(INDIGO, INDIGO_DEEP, 0.4)), 'smooth': True},
        'pad_dpad': {'color': hexc(SILVER), 'texture': {'image': 'art/pad_dpad.png', 'projection': 'fit'}},
        'pad_moon': {'color': '#ececde', 'smooth': True,
                     'texture': {'image': 'art/pad_moon.png', 'projection': 'disc'}},
        'silver': {'color': hexc(SILVER)},
        'silver_side': {'color': '#a4a8c4'},
        'well': {'color': '#1c1844'},
        'shoulder': {'color': '#aeb4d2'},
        'cable': {'color': '#2a2650', 'smooth': True},
    }
    for k, col in BTN_COL.items():
        mats['btn_' + k] = {'color': hexc(col),
                            'texture': {'image': 'art/pad_btn_%s.png' % k, 'projection': 'disc'}}
    return {
        'format': 'mei-asset', 'version': 1, 'name': 'moonlight_controller',
        'budget': {'vertices': 900, 'triangles': 800},
        'materials': mats,
        'lighting': {'direction': [-0.4, 0.85, -0.35], 'ambient': 0.55},
        'verification': {'required': True, 'depth': True, 'perspective': True},
        'nodes': build(),
    }


if __name__ == '__main__':
    ART.mkdir(exist_ok=True)
    paint_top(); paint_wall(); paint_buttons()
    with open(HERE / 'controller.asset.json', 'w') as f:
        json.dump(recipe(), f, indent=1)
    print('wrote controller.asset.json')
