"""Moonlight Skeleton console: paints art/console_*.png and writes console.asset.json.

python3 make_console.py   (needs Pillow and the macOS Hiragino font for the 明 mark)
Model in metres, real size; faces -Z (the controller ports' side).
"""
import json, math, random
from PIL import Image
from mlib import *

# --- dimensions (m) ----------------------------------------------------------------------
HW, HD, R, SEG = 0.145, 0.105, 0.028, 6
# rings: (inset, y). The walls are b2..b3; the top cap is at b5.
RINGS = [(0.012, 0.000), (0.005, 0.004), (0.0, 0.011), (0.0, 0.050), (0.005, 0.060), (0.013, 0.066)]
YW0, YW1, YTOP = RINGS[2][1], RINGS[3][1], RINGS[5][1]
FX = HW - R          # half-length of the flat front/back walls
FZ = HD - R          # half-length of the flat side walls

SLOT_C = (-0.035, 0.040)          # cart slot centre (x, z)
SLOT_S = (0.142, 0.034)           # its surround's footprint
CART_S = (0.104, 0.018)
WIN_C = (0.074, 0.024)            # the moon window
WIN_R = 0.0345
PWR = (-0.104, -0.060)
RST = (-0.064, -0.060)
LED = (-0.123, -0.047)
PORTS_X = (-0.074, -0.030)        # controller ports 1 and 2 on the front wall
PORT_Y, CARD_Y = 0.024, 0.041

random.seed(7)

# =============================== textures ===================================================

def board_traces(p, x0, x1, z0, z1, n, rnd, color, alpha=150):
    """Manhattan traces between random points, the look of a board seen through plastic."""
    for _ in range(n):
        a = (rnd.uniform(x0, x1), rnd.uniform(z0, z1))
        b = (rnd.uniform(x0, x1), rnd.uniform(z0, z1))
        mid = (b[0], a[1]) if rnd.random() < 0.5 else (a[0], b[1])
        p.line([a, mid, b], color, 0.0006, alpha)


TX, TZ = HW - RINGS[5][0], HD - RINGS[5][0]   # the top cap's half extents: the top image covers it


def paint_top():
    # u = x, v = -z (image top = back), over the top cap's rectangle: 182 x 127 texels.
    p = Painter(182, 127, -TX, TX, TZ, -TZ, INDIGO)
    rnd = random.Random(11)
    # the main board, a dark teal seen through indigo; it stops short of the front-left corner
    p.poly([(-0.120, 0.082), (0.124, 0.082), (0.124, -0.084), (-0.040, -0.084), (-0.052, -0.040),
            (-0.120, -0.040)], GHOST, alpha=215)
    # buses from the chips to the cart connector
    cx, cz = SLOT_C
    for i in range(10):
        z = 0.010 - i * 0.0024
        p.line([(-0.100 + i * 0.004, cz - 0.012), (-0.100 + i * 0.004, z), (0.040, z), (0.048, z - 0.010)],
               GHOST_LINE, 0.0006, 120)
    for i in range(8):
        x = 0.006 + i * 0.0026
        p.line([(x, cz - 0.012), (x, -0.020), (x + 0.040, -0.044)], GHOST_LINE, 0.0006, 110)
    board_traces(p, -0.040, 0.120, -0.080, 0.000, 26, rnd, GHOST_LINE, 90)
    board_traces(p, -0.115, -0.050, -0.036, 0.075, 14, rnd, GHOST_LINE, 90)
    # cart connector under the slot, its pins
    p.rect(cx - 0.064, cz + 0.010, cx + 0.064, cz - 0.010, (16, 14, 50), alpha=235)
    for i in range(40):
        x = cx - 0.058 + i * 0.116 / 39
        p.line([(x, cz + 0.006), (x, cz - 0.006)], LAVENDER, 0.0005, 150)
    # the Prism chip and its RAM, black packages with pale legs
    for (x0, z0, x1, z1) in [(-0.010, -0.026, 0.026, -0.062), (0.048, -0.036, 0.064, -0.062),
                             (0.070, -0.036, 0.086, -0.062), (0.040, 0.070, 0.066, 0.058)]:
        p.rect(x0 - 0.0015, z0 + 0.0015, x1 + 0.0015, z1 - 0.0015, LAVENDER, alpha=90)
        p.rect(x0, z0, x1, z1, (12, 10, 34), alpha=240)
    p.circle(-0.004, -0.032, 0.0015, LAVENDER, alpha=160)
    # power supply, back left: transformer windings and a capacitor
    p.rect(-0.128, 0.086, -0.100, 0.050, (14, 12, 42), alpha=230)
    for i in range(6):
        p.line([(-0.126, 0.082 - i * 0.0055), (-0.102, 0.082 - i * 0.0055)], LAVENDER, 0.0008, 120)
    p.circle(-0.114, 0.034, 0.0075, (14, 12, 42), alpha=230)
    p.circle(-0.114, 0.034, 0.0050, LAVENDER, alpha=80)
    # the screw bosses: rings of pale plastic going down to the board
    for sx, sz in [(-0.116, -0.078), (0.116, -0.078), (-0.116, 0.076), (0.116, 0.076), (-0.004, 0.006)]:
        p.circle(sx, sz, 0.0068, INDIGO_EDGE, alpha=200)
        p.circle(sx, sz, 0.0040, LAVENDER, alpha=170)
        p.circle(sx, sz, 0.0018, INDIGO_DEEP, alpha=255)
    # the controller-port housings just inside the front edge
    for px_ in PORTS_X:
        p.rect(px_ - 0.018, -0.080, px_ + 0.018, -0.100, (16, 14, 50), alpha=210)
    # the moon window sits in a ring of shadow
    p.circle(WIN_C[0], WIN_C[1], WIN_R + 0.004, INDIGO_DEEP, alpha=220)
    # the shell's thickness: a darker line just inside the cap's edge
    p.rrect(-TX + 0.0015, TZ - 0.0015, TX - 0.0015, -TZ + 0.0015, 0.015, None, outline=INDIGO_DEEP, width=0.0022, alpha=150)
    # print: a dotted orbit around the window, from the crescent's tips
    for k in range(25):
        a = math.radians(150 + k * 10)
        p.circle(WIN_C[0] + 0.049 * math.cos(a), WIN_C[1] + 0.049 * math.sin(a), 0.0009, MOON, alpha=230)
    # gloss: two diagonal sheens
    p.sheen([(-0.130, 0.092), (-0.095, 0.092), (-0.010, -0.092), (-0.045, -0.092)], 40)
    p.sheen([(-0.080, 0.092), (-0.068, 0.092), (0.017, -0.092), (0.005, -0.092)], 28)
    img = p.finish()
    # printed labels at texel resolution
    for (x, z), s in [(PWR, 'POWER'), (RST, 'RESET')]:
        tx, ty = p.texel(x, z - 0.0135)
        pixel_text(img, tx, ty, s, MOON, center=True)
    tx, ty = p.texel(0.080, -0.060)
    img = logo(img, tx, ty, 15)
    tx, ty = p.texel(0.080, -0.075)
    pixel_text(img, tx, ty, 'MOONLIGHT', MOON, center=True)
    img.save(ART / 'console_top.png')


def paint_wall(name, width, base_ghost, extra=None):
    """A flat wall: u along the wall as seen from outside, v down from YW1 to YW0."""
    w = int(round(width * 800))
    h = int(round((YW1 - YW0) * 800))
    p = Painter(w, h, -width / 2, width / 2, YW1, YW0, INDIGO)
    rnd = random.Random(sum(map(ord, name)))
    # the board's edge seen through the wall, and the bottom shell's lip
    p.rect(-width / 2, 0.026, width / 2, 0.019, GHOST, alpha=170)
    p.rect(-width / 2, 0.016, width / 2, YW0, INDIGO_DEEP, alpha=110)
    if base_ghost:
        for _ in range(base_ghost):
            x = rnd.uniform(-width / 2 + 0.01, width / 2 - 0.01)
            hgt = rnd.uniform(0.003, 0.012)
            wd = rnd.uniform(0.004, 0.014)
            p.rect(x - wd / 2, 0.026 + hgt, x + wd / 2, 0.026, (22, 20, 64), alpha=170)
    if extra:
        extra(p)
    # a rim of light just under the bevel
    p.rect(-width / 2, YW1, width / 2, YW1 - 0.0015, INDIGO_EDGE, alpha=200)
    p.sheen([(-width / 2 + 0.02, YW1), (-width / 2 + 0.05, YW1), (-width / 2 + 0.035, YW0), (-width / 2 + 0.005, YW0)], 36)
    return p


def paint_front():
    def extra(p):
        for x in PORTS_X:   # the port housings behind their bezels
            p.rect(x - 0.019, 0.034, x + 0.019, 0.014, (20, 18, 60), alpha=200)
        # the edition's name, printed: 月光, moonlight, with a crescent before it
        p.text(0.083, 0.0315, '月光', 0.0175, MOON)
        p.circle(0.050, 0.0325, 0.0065, MOON)
        p.circle(0.0525, 0.0340, 0.0056, INDIGO)
    p = paint_wall('front', 2 * FX, 14, extra)
    img = p.finish()
    for x, s in zip(PORTS_X, '12'):
        tx, ty = p.texel(x + 0.0175, 0.030)
        pixel_text(img, tx, ty, s, MOON)
    tx, ty = p.texel(0.074, 0.0205)
    pixel_text(img, tx, ty, 'MOONLIGHT', MOON, center=True)
    img.save(ART / 'console_front.png')


BACK = {'ant': 0.070, 'av': -0.010, 'dc': -0.075}   # x of the back connectors (world)


def paint_back():
    def extra(p):
        # vents: slots in the shell (real openings: the board shows darker through them)
        for i in range(12):
            u = -0.020 - i * 0.0055 + 0.090      # in image space u = -x
            p.rect(u - 0.0016, 0.044, u + 0.0016, 0.030, (14, 12, 40), alpha=255)
        for key, x in BACK.items():
            p.rect(-x - 0.012, 0.037, -x + 0.012, 0.016, (20, 18, 60), alpha=170)
    p = paint_wall('back', 2 * FX, 8, extra)
    img = p.finish()
    for key, s in [('ant', 'MEINET'), ('av', 'AV OUT'), ('dc', 'DC IN')]:
        tx, ty = p.texel(-BACK[key], 0.0165)
        pixel_text(img, tx, ty, s, MOON, center=True)
    img.save(ART / 'console_back.png')


def paint_side():
    def extra(p):
        for i in range(7):   # side vents
            u = -0.045 + i * 0.006
            p.rect(u - 0.0015, 0.043, u + 0.0015, 0.031, (14, 12, 40), alpha=255)
    p = paint_wall('side', 2 * FZ, 9, extra)
    p.finish().save(ART / 'console_side.png')


def paint_lens():
    # the window, seen from above: the Prism Engine chip under pale glass; disc covers 2*WIN_R
    p = Painter(48, 48, -WIN_R, WIN_R, WIN_R, -WIN_R, (150, 170, 236))
    p.circle(0, 0, WIN_R, (116, 132, 222))
    p.rect(-0.030, 0.002, 0.030, -0.002, (70, 80, 180), alpha=255)      # traces
    p.rect(-0.002, 0.030, 0.002, -0.030, (70, 80, 180), alpha=255)
    p.rect(-0.018, 0.018, 0.018, -0.018, (44, 44, 120))                  # the chip
    p.rect(-0.015, 0.015, 0.015, -0.015, (66, 66, 150))
    for i in range(8):
        t = -0.016 + i * 0.032 / 7
        for a, b in [((t, 0.019), (t, 0.022)), ((t, -0.019), (t, -0.022)),
                     ((0.019, t), (0.022, t)), ((-0.019, t), (-0.022, t))]:
            p.line([a, b], (210, 220, 255), 0.0012)
    p.text(0, 0.0005, '明', 0.020, (214, 228, 255), alpha=230)
    p.sheen([(-0.03, 0.02), (-0.01, 0.034), (0.0, 0.03), (-0.024, 0.01)], 150)
    p.finish().save(ART / 'console_lens.png')


def paint_cart():
    # front of the cartridge: 0.104 wide, y 0.040..0.114; the label is above the surround
    w, h = 64, 46
    p = Painter(w, h, -0.052, 0.052, 0.114, 0.040, (150, 152, 170))
    p.rrect(-0.044, 0.110, 0.044, 0.078, 0.003, (18, 22, 60))        # the label: night sky
    p.circle(0.020, 0.100, 0.0085, (236, 238, 220))                    # full moon
    p.circle(0.017, 0.102, 0.0016, (200, 204, 196))
    p.circle(0.024, 0.097, 0.0012, (200, 204, 196))
    p.poly([(-0.044, 0.078), (-0.044, 0.088), (-0.020, 0.092), (0.004, 0.086), (0.030, 0.090),
            (0.044, 0.085), (0.044, 0.078)], (40, 70, 70))             # hills
    for x in [-0.036, -0.030, -0.012, 0.034]:                          # susuki grass
        p.line([(x, 0.078), (x + 0.003, 0.094)], (210, 200, 150), 0.0009)
    p.rect(-0.052, 0.076, 0.052, 0.074, (120, 122, 140))                  # grip ridge
    img = p.finish()
    tx, ty = p.texel(-0.020, 0.1085)
    pixel_text(img, tx, ty, 'GARDEN', (240, 240, 230), center=True)
    img.save(ART / 'console_cart.png')


def paint_small():
    # controller port socket, seen from the front: 0.030 x 0.016
    p = Painter(30, 16, -0.015, 0.015, 0.008, -0.008, (40, 36, 92))
    p.rrect(-0.012, 0.005, 0.012, -0.006, 0.002, (8, 8, 20))
    for i in range(5):
        x = -0.008 + i * 0.004
        p.rect(x - 0.0007, 0.002, x + 0.0007, -0.002, SILVER)
    p.finish().save(ART / 'console_port.png')
    # memory card slot: 0.036 x 0.007, a hinged door
    p = Painter(36, 8, -0.018, 0.018, 0.0035, -0.0035, (40, 36, 92))
    p.rect(-0.015, 0.0018, 0.015, -0.0020, (8, 8, 20))
    p.rect(-0.015, 0.0018, 0.015, 0.0010, (70, 64, 150))
    p.finish().save(ART / 'console_card.png')
    # cartridge slot surround top: dark mouth around the cart
    p = Painter(71, 17, -SLOT_S[0] / 2, SLOT_S[0] / 2, SLOT_S[1] / 2, -SLOT_S[1] / 2, (70, 60, 170))
    p.rrect(-0.058, 0.0115, 0.058, -0.0115, 0.002, (12, 10, 34))
    p.rect(-SLOT_S[0] / 2, SLOT_S[1] / 2, SLOT_S[0] / 2, SLOT_S[1] / 2 - 0.002, INDIGO_EDGE)
    p.finish().save(ART / 'console_slot.png')
    # AV multi-out socket
    p = Painter(20, 8, -0.010, 0.010, 0.004, -0.004, (30, 30, 40))
    p.rrect(-0.008, 0.0025, 0.008, -0.0025, 0.0015, (6, 6, 10))
    for i in range(6):
        p.rect(-0.0065 + i * 0.0025, 0.0007, -0.0055 + i * 0.0025, -0.0007, (200, 180, 100))
    p.finish().save(ART / 'console_av.png')


# =============================== geometry ===================================================

def ring_pts(k):
    inset, y = RINGS[k]
    pts, kinds = rounded_rect(HW, HD, R, inset, SEG)
    return [(x, y, z) for x, z in pts], kinds


def shell_nodes():
    shell = MeshBuilder('shell')
    walls = {k: MeshBuilder('wall_' + k, uv=True) for k in ('front', 'back', 'left', 'right')}
    top = MeshBuilder('top_plate', uv=True)
    rings = [ring_pts(k)[0] for k in range(len(RINGS))]
    kinds = ring_pts(0)[1]
    n = len(rings[0])
    band_mat = {0: 'shell_under', 1: 'shell_under', 2: 'shell_wall', 3: 'shell_bevel', 4: 'shell_bevel'}
    for b in range(len(RINGS) - 1):
        lo, hi = rings[b], rings[b + 1]
        for i in range(n):
            j = (i + 1) % n
            quad = [lo[i], lo[j], hi[j], hi[i]]
            cx = sum(p[0] for p in quad) / 4
            cz = sum(p[2] for p in quad) / 4
            cy = sum(p[1] for p in quad) / 4
            out = [cx, (cy - 0.033) * 0.5, cz]
            kind = kinds[i]
            if b == 2 and kind:
                side = {'nz': 'front', 'pz': 'back', 'nx': 'left', 'px': 'right'}[kind]
                uvs = []
                for (x, y, z) in quad:
                    v = (YW1 - y) / (YW1 - YW0)
                    if side == 'front':
                        u = (x + FX) / (2 * FX)
                    elif side == 'back':
                        u = (FX - x) / (2 * FX)
                    elif side == 'left':
                        u = (FZ - z) / (2 * FZ)
                    else:
                        u = (z + FZ) / (2 * FZ)
                    uvs.append((u, v))
                walls[side].face(quad, 'con_' + side if side in ('front', 'back') else 'con_side', out, uvs)
            else:
                shell.face([quad[0], quad[1], quad[2]], band_mat[b], out)
                shell.face([quad[0], quad[2], quad[3]], band_mat[b], out)
    # caps
    shell.face(rings[0], 'shell_under', [0, -1, 0])
    uvs = [((x + TX) / (2 * TX), (TZ - z) / (2 * TZ)) for x, y, z in rings[-1]]
    top.face(rings[-1], 'con_top', [0, 1, 0], uvs)
    return [top.node(), shell.node()] + [w.node() for w in walls.values()]


def box_mesh(ident, c, s, mats, uv_faces=()):
    """A box as a mesh, each side with its own corners so a side can carry a fitted texture.
    mats: material per side (top, bottom, front(-Z), back(+Z), left, right)."""
    mb = MeshBuilder(ident, uv=True)
    x0, x1 = c[0] - s[0] / 2, c[0] + s[0] / 2
    y0, y1 = c[1] - s[1] / 2, c[1] + s[1] / 2
    z0, z1 = c[2] - s[2] / 2, c[2] + s[2] / 2
    sides = {
        # corners listed top-left, top-right, bottom-right, bottom-left as seen from outside
        'top': ([(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)], [0, 1, 0]),
        'bottom': ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], [0, -1, 0]),
        'front': ([(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)], [0, 0, -1]),
        'back': ([(x1, y1, z1), (x0, y1, z1), (x0, y0, z1), (x1, y0, z1)], [0, 0, 1]),
        'left': ([(x0, y1, z1), (x0, y1, z0), (x0, y0, z0), (x0, y0, z1)], [-1, 0, 0]),
        'right': ([(x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (x1, y0, z0)], [1, 0, 0]),
    }
    for name, (pts, out) in sides.items():
        m = mats.get(name)
        if m is None:
            continue
        uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
        mb.face(pts, m, out, uvs)
    return mb.node()


def crescent_points(r_in, r_out, off, n_out=14, n_in=10):
    """A crescent hugging a circle of r_in at the origin: the region inside a circle of r_out
    centred at (-off, 0) and outside the r_in circle. Thick side toward -X."""
    xt = (r_out ** 2 - r_in ** 2 - off ** 2) / (2 * off)   # the tips: x on both circles
    yt = math.sqrt(r_in ** 2 - xt ** 2)
    a_in = math.atan2(yt, xt)
    a_out = math.atan2(yt, xt + off)
    pts = []
    for k in range(n_out + 1):   # outer arc, from the upper tip the long way round
        a = a_out + (2 * math.pi - 2 * a_out) * k / n_out
        pts.append((-off + r_out * math.cos(a), r_out * math.sin(a)))
    for k in range(1, n_in):     # inner arc back
        a = -a_in - (2 * math.pi - 2 * a_in) * k / n_in
        pts.append((r_in * math.cos(a), r_in * math.sin(a)))
    return [[round(x, 6), round(y, 6)] for x, y in pts]


def build():
    nodes = shell_nodes()
    sx, sz = SLOT_C
    # cart slot surround and the cartridge in it
    nodes.append(box_mesh('slot', (sx, 0.0685, sz), (SLOT_S[0], 0.010, SLOT_S[1]),
                          {'top': 'con_slot', 'front': 'shell_bevel', 'back': 'shell_bevel',
                           'left': 'shell_bevel', 'right': 'shell_bevel'}))
    nodes.append(box_mesh('cart', (sx, 0.077, sz), (CART_S[0], 0.074, CART_S[1]),
                          {'top': 'cart_shell', 'front': 'con_cart', 'back': 'cart_shell',
                           'left': 'cart_shell', 'right': 'cart_shell'}))
    # cartridge grip ridges on its top edge
    nodes.append({'id': 'cart_grip', 'op': 'box', 'size': [CART_S[0] - 0.012, 0.004, CART_S[1] + 0.003],
                  'material': 'cart_grip', 'transform': {'translate': [sx, 0.1135, sz]}})
    # the moon window: a lens dome and a crescent bezel
    nodes.append({'id': 'lens', 'op': 'lathe', 'material': 'con_lens', 'segments': 20, 'caps': False,
                  'profile': [[WIN_R, 0.0625], [WIN_R - 0.0012, 0.0675], [0.028, 0.0712],
                              [0.018, 0.0736], [0.0, 0.0746]],
                  'transform': {'translate': [WIN_C[0], 0, WIN_C[1]]}})
    nodes.append({'id': 'crescent', 'op': 'extrude', 'material': 'silver', 'depth': 0.005,
                  'points': crescent_points(WIN_R - 0.0004, 0.0425, 0.0115),
                  'transform': {'rotate': [90, 0, 0], 'translate': [WIN_C[0], 0.0675, WIN_C[1]]}})
    # but the crescent should hug the window on the side away from the cart: turn it
    nodes[-1]['transform']['rotate'] = [90, 180, 0]
    # power, reset and the power light
    nodes.append({'id': 'power', 'op': 'cylinder', 'radius': 0.0105, 'height': 0.008, 'segments': 12,
                  'material': 'silver', 'transform': {'translate': [PWR[0], 0.0665, PWR[1]]}})
    nodes.append({'id': 'power_cap', 'op': 'cylinder', 'radius': 0.0065, 'height': 0.0015, 'segments': 12,
                  'material': 'moon_blue', 'transform': {'translate': [PWR[0], 0.0706, PWR[1]]}})
    nodes.append({'id': 'reset', 'op': 'cylinder', 'radius': 0.0068, 'height': 0.006, 'segments': 10,
                  'material': 'silver', 'transform': {'translate': [RST[0], 0.0665, RST[1]]}})
    nodes.append({'id': 'led', 'op': 'cylinder', 'radius': 0.0025, 'height': 0.004, 'segments': 8,
                  'material': 'led', 'transform': {'translate': [LED[0], 0.0665, LED[1]]}})
    # front: controller ports and memory card slots
    zf = -HD
    for k, x in enumerate(PORTS_X):
        nodes.append(box_mesh('port%d' % (k + 1), (x, PORT_Y, zf - 0.0015), (0.030, 0.016, 0.006),
                              {'front': 'con_port', 'top': 'port_rim', 'bottom': 'port_rim',
                               'left': 'port_rim', 'right': 'port_rim'}))
        nodes.append(box_mesh('card%d' % (k + 1), (x, CARD_Y, zf - 0.001), (0.036, 0.007, 0.005),
                              {'front': 'con_card', 'top': 'port_rim', 'bottom': 'port_rim',
                               'left': 'port_rim', 'right': 'port_rim'}))
    # back: MeiNet antenna (F connector), AV multi-out, DC in
    zb = HD
    nodes.append({'id': 'ant_nut', 'op': 'cylinder', 'radius': 0.0055, 'height': 0.006, 'segments': 6,
                  'material': 'silver', 'transform': {'rotate': [90, 0, 0], 'translate': [BACK['ant'], 0.027, zb + 0.002]}})
    nodes.append({'id': 'ant_pin', 'op': 'cylinder', 'radius': 0.0035, 'height': 0.012, 'segments': 8,
                  'material': 'brass', 'transform': {'rotate': [90, 0, 0], 'translate': [BACK['ant'], 0.027, zb + 0.0065]}})
    nodes.append(box_mesh('av_out', (BACK['av'], 0.027, zb + 0.001), (0.020, 0.008, 0.005),
                          {'back': 'con_av', 'top': 'plug_black', 'bottom': 'plug_black',
                           'left': 'plug_black', 'right': 'plug_black'}))
    nodes.append({'id': 'dc_in', 'op': 'cylinder', 'radius': 0.0045, 'height': 0.006, 'segments': 8,
                  'material': 'plug_black', 'transform': {'rotate': [90, 0, 0], 'translate': [BACK['dc'], 0.027, zb + 0.001]}})
    nodes.append({'id': 'dc_hole', 'op': 'cylinder', 'radius': 0.002, 'height': 0.002, 'segments': 6,
                  'material': 'brass', 'transform': {'rotate': [90, 0, 0], 'translate': [BACK['dc'], 0.027, zb + 0.0035]}})
    # four rubber feet
    for k, (fx, fz) in enumerate([(-0.105, -0.068), (0.105, -0.068), (-0.105, 0.068), (0.105, 0.068)]):
        nodes.append({'id': 'foot%d' % k, 'op': 'cylinder', 'radius': 0.007, 'height': 0.004, 'segments': 8,
                      'material': 'rubber', 'transform': {'translate': [fx, 0.001, fz]}})
    return nodes


def tex(img):
    return {'image': 'art/' + img, 'bits': 8, 'projection': 'fit'}


def recipe():
    mats = {
        'con_top': {'color': hexc(INDIGO), 'texture': tex('console_top.png')},
        'con_front': {'color': hexc(INDIGO), 'texture': tex('console_front.png')},
        'con_back': {'color': hexc(INDIGO), 'texture': tex('console_back.png')},
        'con_side': {'color': hexc(INDIGO), 'texture': tex('console_side.png')},
        'con_lens': {'color': '#96aaec', 'smooth': True,
                     'texture': {'image': 'art/console_lens.png', 'bits': 8, 'projection': 'disc'}},
        'con_cart': {'color': '#9698aa', 'texture': tex('console_cart.png')},
        'con_slot': {'color': '#463caa', 'texture': tex('console_slot.png')},
        'con_port': {'color': '#28245c', 'texture': {'image': 'art/console_port.png', 'projection': 'fit'}},
        'con_card': {'color': '#28245c', 'texture': {'image': 'art/console_card.png', 'projection': 'fit'}},
        'con_av': {'color': '#1e1e28', 'texture': {'image': 'art/console_av.png', 'projection': 'fit'}},
        'shell_wall': {'color': hexc(INDIGO), 'smooth': True},
        'shell_bevel': {'color': hexc(INDIGO_EDGE), 'smooth': True},
        'shell_under': {'color': hexc(INDIGO_DEEP), 'smooth': True},
        'cart_shell': {'color': '#9698aa'},
        'cart_grip': {'color': '#7c7e92'},
        'silver': {'color': hexc(SILVER)},
        'moon_blue': {'color': hexc(MOON)},
        'brass': {'color': '#c8b070'},
        'plug_black': {'color': '#1e1e28'},
        'port_rim': {'color': '#5a50c0'},
        'rubber': {'color': '#1a1830'},
        'led': {'color': '#9fd8ff', 'class': 'emissive'},
    }
    return {
        'format': 'mei-asset', 'version': 1, 'name': 'moonlight_console',
        'budget': {'vertices': 1400, 'triangles': 1200},
        'materials': mats,
        'lighting': {'direction': [-0.4, 0.85, -0.35], 'ambient': 0.55},
        'verification': {'required': True, 'depth': True, 'perspective': True},
        'nodes': build(),
    }


if __name__ == '__main__':
    ART.mkdir(exist_ok=True)
    paint_top(); paint_front(); paint_back(); paint_side(); paint_lens(); paint_cart(); paint_small()
    with open(HERE / 'console.asset.json', 'w') as f:
        json.dump(recipe(), f, indent=1)
    print('wrote console.asset.json')
