"""Electric Town's layout sketch: writes from_south_east.png, from_south_west.png and
store_profile.png beside this file (python3 carts/garden/electric/layout.py). A planning sketch:
metres, map x east, map y south, z up. Needs Pillow and macOS's Avenir Next."""
import math, random, sys, os
from PIL import Image, ImageDraw, ImageFont

W = 192
Y0, YMAX = 0, 192
WY = YMAX - Y0
STEP = 4
FONT = '/System/Library/Fonts/Avenir Next.ttc'
f_lab = ImageFont.truetype(FONT, 16, index=5)
f_title = ImageFont.truetype(FONT, 24, index=5)
f_sm = ImageFont.truetype(FONT, 14, index=0)

def clamp(v, a, b): return max(a, min(b, v))
def height(x, y): return 0.0
def is_water(x, y): return False
AVENUE = (64, 92)

boxes, cones, blobs, labels = [], [], [], []
ROW = (196, 202, 212)                    # the ordered buildings: one pale colour, all alike
NEON = [(255, 60, 180), (60, 210, 255), (255, 214, 60)]
ZIG = [(236, 222, 190), (226, 208, 170)]
RED = (210, 50, 44)
LINE = (250, 170, 30)

def box(x1, y1, x2, y2, h, col, z0=0.0):
    boxes.append((x1, y1, x2, y2, z0, z0 + h, col))

def coin(x, y, z): box(x - 1.4, y - 1.4, x + 1.4, y + 1.4, 2.6, (250, 205, 40), z)

# --- the ordered rows west of the avenue: identical narrow buildings, identical alleys
for k in range(6):
    x1 = 6 + k * 9.5
    for (y1, y2) in [(58, 96), (104, 142), (150, 186)]:
        box(x1, y1, x1 + 7, y2, 24, ROW)
        box(x1 + 7, y1 + 4, x1 + 7.6, y1 + 18, 1.0, NEON[k % 3], 8)        # one sign each, all in step
labels.append((34, 120, 30, 'The ordered rows: 24 m, 2.5 m alleys'))

# --- the department store: a stepped ziggurat east of the avenue
X1, Y1, X2, Y2 = 100, 62, 186, 182
STORE = (X1, Y1, X2, Y2)
TIERS = 6
for t in range(TIERS):
    inset = t * 7
    box(X1 + inset, Y1 + inset, X2 - inset, Y2 - inset, 8, ZIG[t % 2], t * 8)
    xa, ya, xb, yb, zb = X1 + inset - 0.3, Y1 + inset - 0.3, X2 - inset + 0.3, Y2 - inset + 0.3, t * 8 + 6.4
    box(xa, ya, xb, ya + 0.6, 1.2, RED, zb); box(xa, yb - 0.6, xb, yb, 1.2, RED, zb)        # a red band round each floor
    box(xa, ya, xa + 0.6, yb, 1.2, RED, zb); box(xb - 0.6, ya, xb, yb, 1.2, RED, zb)
top = TIERS * 8
cx, cy = (X1 + X2) / 2, (Y1 + Y2) / 2
box(cx - 10, cy - 3, cx + 10, cy + 3, 14, (40, 70, 160), top)                # giant sign
box(cx - 10.4, cy - 3.4, cx + 10.4, cy - 2.6, 14, (60, 120, 230), top)
coin(cx, cy, top + 15)
# what's on each terrace
for k in range(5):                                                            # T1: parked cars on the ramp deck
    box(X1 + 1 + k * 7, Y2 - 6, X1 + 5 + k * 7, Y2 - 2, 1.6, [(200, 60, 60), (60, 90, 200), (230, 230, 230)][k % 3], 8)
box(X2 - 6, Y1 + 30, X2 - 1, Y2 - 30, 0.5, (110, 110, 116), 4)                # T1: the car ramp up the side
for k in range(4):                                                            # T2: food court parasols
    box(X1 + 18 + k * 9, Y2 - 13, X1 + 22 + k * 9, Y2 - 9, 0.4, NEON[k % 3], 19)
box(X1 + 22, Y1 + 22, X1 + 30, Y1 + 30, 6, (240, 120, 160), 24)               # T3: a kiddie ride / small ferris frame
box(X2 - 34, Y2 - 26, X2 - 26, Y2 - 22, 0.3, (90, 200, 120), 24)              # T3: playground
for k in range(6):                                                            # T4: beer garden lanterns
    box(X1 + 32 + k * 5, Y2 - 30, X1 + 33 + k * 5, Y2 - 29, 1, (255, 120, 60), 34)
box(X1 + 38, Y1 + 36, X2 - 38, Y1 + 46, 7, (180, 220, 180), 40)               # T5: batting cage net

# --- the elevated line overhead: across the avenue, between the rows and the store
for px in range(4, 190, 14):
    box(px - 1.2, 40, px + 1.2, 42.4, 12, (160, 160, 156))
box(0, 38, W, 46, 1.8, (170, 170, 166), 12)
box(28, 38.8, 70, 45.2, 3.2, LINE, 13.8)                                       # a train
labels.append((49, 42, 21, 'Elevated line (12 m)'))
# the station, and a skybridge from its platform to the store's second terrace
box(108, 30, 170, 50, 10, (210, 206, 196))
box(108, 30, 170, 50, 1, (140, 140, 140), 14)
box(130, 46, 140, 62, 1.2, (230, 230, 236), 15)                                # skybridge
labels.append((139, 40, 20, 'Station'))
labels.append((135, 56, 20, 'Skybridge to terrace 2'))
labels.append((cx, cy, top + 22, 'Department store: 6 terraces, 48 m, sign to 62 m'))
# a few rooftop coins on the ordered rows, a red-coin line along the terraces
coin(10, 77, 24.5); coin(29, 123, 24.5); coin(53, 168, 24.5)

# ---- rendering (a larger scale and fewer labels than the first pass)
# ---- rendering
LIGHT = (-0.45, -0.55, 0.70)
LN = math.sqrt(sum(c * c for c in LIGHT)); LIGHT = tuple(c / LN for c in LIGHT)

def shade(col, n):
    k = 0.45 + 0.6 * max(0.0, sum(a * b for a, b in zip(n, LIGHT)))
    return tuple(int(clamp(c * k, 0, 255)) for c in col)

def ground_colour(x, y, h, slope):
    if is_water(x, y): return (70, 130, 190)
    if ROAD[0] <= y < ROAD[1]: return (84, 84, 90)
    if y >= ROAD[1] or y >= ROAD[0] - 2: return (172, 170, 164)
    if in_compound(x, y): return (206, 196, 172)
    if any(math.hypot(x - cx, y - cy) < r for cx, cy, r, fl in CLEARINGS): return (150, 170, 96)                   # raked gravel
    if route_dist(x, y) < 2.2: return (150, 120, 84)               # the forest trail
    if slope > 0.9: return (112, 96, 78)
    return (86, 120 + int(clamp(h, 0, 20)), 60)

def render(view, title, out):
    S = 3.0
    if view == 'se':   T = lambda x, y: (x, y - Y0);       U = lambda X, Y: (X, Y + Y0)
    elif view == 'sw': T = lambda x, y: (W - x, y - Y0);   U = lambda X, Y: (W - X, Y + Y0)
    else:              T = lambda x, y: (W - x, YMAX - y);   U = lambda X, Y: (W - X, YMAX - Y)
    def P(x, y, z):
        X, Y = T(x, y)
        return (40 + (X - Y + WY) * 0.866 * S, 200 + (X + Y) * 0.5 * S - z * S)
    polys = []
    for i in range(W // STEP):
        for j in range(WY // STEP):
            x0, y0 = i * STEP, Y0 + j * STEP
            c = [(x0, y0), (x0 + STEP, y0), (x0 + STEP, y0 + STEP), (x0, y0 + STEP)]
            hs = [height(*p) for p in c]
            hx = (hs[1] + hs[2] - hs[0] - hs[3]) / (2 * STEP)
            hy = (hs[2] + hs[3] - hs[0] - hs[1]) / (2 * STEP)
            L = math.sqrt(hx * hx + hy * hy + 1); nn = (-hx / L, -hy / L, 1 / L)
            cx, cy = x0 + STEP / 2, y0 + STEP / 2
            col = shade(ground_colour(cx, cy, sum(hs) / 4, math.hypot(hx, hy)), nn)
            if is_water(cx, cy): hs = [min(h, -0.6) for h in hs]
            X, Y = T(cx, cy)
            polys.append((X + Y, [P(px, py, h) for (px, py), h in zip(c, hs)], col, None))
    for (x1, y1, x2, y2, z0, z1, col) in boxes:
        X1, Y1 = T(x1, y1); X2, Y2 = T(x2, y2)
        xa, xb, ya, yb = min(X1, X2), max(X1, X2), min(Y1, Y2), max(Y1, Y2)
        Q = lambda X, Y, z: P(*U(X, Y), z)
        key = xb + yb + 0.01 + (1000 if col == (250, 205, 40) else 0)
        if STORE[0] - 1 <= x1 and x2 <= STORE[2] + 1 and STORE[1] - 1 <= y1 and y2 <= STORE[3] + 1: key += 2.2 * z0   # stacked terraces: higher drawn later
        polys.append((key, [Q(xb, ya, z0), Q(xb, yb, z0), Q(xb, yb, z1), Q(xb, ya, z1)], shade(col, (0.7, 0.2, 0.7)), (30, 30, 30)))
        polys.append((key, [Q(xa, yb, z0), Q(xb, yb, z0), Q(xb, yb, z1), Q(xa, yb, z1)], shade(col, (0.2, 0.3, 0.7)), (30, 30, 30)))
        polys.append((key + 0.001, [Q(xa, ya, z1), Q(xb, ya, z1), Q(xb, yb, z1), Q(xa, yb, z1)], shade(col, (0, 0, 1)), (30, 30, 30)))
    for (x, y, r, h, col) in cones:
        z = height(x, y); X, Y = T(x, y)
        bx, by = P(x, y, z); tx, ty = P(x, y, z + h)
        w = r * 0.866 * S
        polys.append((X + Y + 0.5, [(bx - w, by), (tx, ty), (bx, by + w * 0.35)], tuple(int(c * 0.75) for c in col), None))
        polys.append((X + Y + 0.5, [(bx, by + w * 0.35), (tx, ty), (bx + w, by)], col, None))
    for (x, y, r, h, col) in blobs:
        z = height(x, y); X, Y = T(x, y)
        bx, by = P(x, y, z); tx, ty = P(x, y, z + h)
        polys.append((X + Y + 0.5, ('trunk', bx, by, ty + r * S * 0.6), (90, 60, 40), None))
        polys.append((X + Y + 0.51, ('blob', tx, ty + r * S * 0.5, r * S * 1.15, r * S * 0.85), col, None))
    img = Image.new('RGB', (1260, 900), (232, 236, 242))
    d = ImageDraw.Draw(img)
    for _, pts, col, outline in sorted(polys, key=lambda p: p[0]):
        if isinstance(pts, tuple) and pts[0] == 'trunk':
            _, bx, by, ty = pts; d.line([(bx, by), (bx, ty)], fill=col, width=3)
        elif isinstance(pts, tuple) and pts[0] == 'blob':
            _, cx, cy, rx, ry = pts
            d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=col, outline=tuple(int(c * 0.7) for c in col))
            d.ellipse([cx - rx * 0.6, cy - ry * 0.75, cx + rx * 0.2, cy - ry * 0.05], fill=tuple(min(255, int(c * 1.08)) for c in col))
        else:
            d.polygon(pts, fill=col, outline=outline)
    for (x, y, z, lab) in labels:
        sx, sy = P(x, y, z)
        w = d.textlength(lab, font=f_lab)
        d.rectangle([sx - w / 2 - 4, sy - 22, sx + w / 2 + 4, sy - 2], fill=(255, 255, 255), outline=(40, 40, 40))
        d.text((sx - w / 2, sy - 22), lab, font=f_lab, fill=(20, 20, 20))
        d.line([(sx, sy - 2), (sx, sy + 8)], fill=(40, 40, 40), width=2)
    d.text((30, 20), title, font=f_title, fill=(20, 20, 20))
    d.text((30, 54), '192 x 192 m. Rough sketch.', font=f_sm, fill=(40, 40, 40))
    img.save(out)

def topdown(out):
    S = 4
    S = 3
    img = Image.new('RGB', (W * S + 40, WY * S + 80), (246, 244, 238))
    d = ImageDraw.Draw(img)
    for i in range(0, W, 2):
        for j in range(Y0, YMAX, 2):
            h = height(i + 1, j + 1)
            col = ground_colour(i + 1, j + 1, h, 0)
            col = tuple(int(c * (0.8 + 0.2 * clamp(h / 30, 0, 1))) for c in col)
            d.rectangle([20 + i * S, 60 + (j - Y0) * S, 20 + (i + 2) * S, 60 + (j - Y0 + 2) * S], fill=col)
    for (x1, y1, x2, y2, z0, z1, col) in boxes:
        d.rectangle([20 + x1 * S, 60 + (y1 - Y0) * S, 20 + x2 * S, 60 + (y2 - Y0) * S], fill=col, outline=(30, 30, 30))
    for (x, y, r, h, col) in cones + blobs:
        d.ellipse([20 + (x - r) * S, 60 + (y - Y0 - r) * S, 20 + (x + r) * S, 60 + (y - Y0 + r) * S], fill=col)
    for (x, y, z, lab) in labels:
        w = d.textlength(lab, font=f_lab)
        d.text((20 + x * S - w / 2, 60 + (y - Y0) * S - 9), lab, font=f_lab, fill=(10, 10, 10), stroke_width=3, stroke_fill=(255, 255, 255))
    d.text((20, 18), 'Top-down: 192 x 288 m, north up', font=f_title, fill=(20, 20, 20))
    img.save(out)


def ground_colour(x, y, h, slope):
    if AVENUE[0] <= x <= AVENUE[1] or 50 <= y <= 56 or 96 <= y <= 104 or 142 <= y <= 150: return (64, 64, 70)
    return (150, 148, 144)

def elevation(out):
    """The store in profile, looking north, with a 1.6 m figure for scale."""
    S = 7
    img = Image.new('RGB', (1300, 760), (240, 242, 246))
    d = ImageDraw.Draw(img)
    gx, gy = 60, 720
    def P(x, z): return (gx + (x - X1 + 6) * S * 0.9, gy - z * S)
    d.line([P(X1 - 10, 0), P(X2 + 4, 0)], fill=(40, 40, 40), width=3)
    names = ['Car deck + ramp', 'Food court, skybridge', 'Kids rides, playground', 'Beer garden', 'Batting cage', 'Roof: the giant sign']
    for t in range(TIERS):
        inset = t * 7
        a, b = P(X1 + inset, t * 8), P(X2 - inset, t * 8 + 8)
        d.rectangle([a[0], b[1], b[0], a[1]], fill=ZIG[t % 2], outline=(60, 50, 40), width=2)
        d.rectangle([a[0], b[1], b[0], b[1] + 6], fill=RED)
        rx, ry = P(X2 - inset, t * 8 + 8)
        d.line([(rx + 4, ry + 6), (rx + 30, ry + 6)], fill=(60, 60, 60), width=1)
        d.text((rx + 34, ry - 4), f'T{t + 1}  {t * 8 + 8} m: {names[t]}', font=f_sm, fill=(20, 20, 20))
    a, b = P(cx - 10, top), P(cx + 10, top + 14)
    d.rectangle([a[0], b[1], b[0], a[1]], fill=(40, 70, 160), outline=(20, 30, 80), width=2)
    d.text((a[0] + 40, b[1] + 30), 'SIGN', font=f_title, fill=(240, 240, 255))
    cxp, cyp = P(cx, top + 16.5); d.ellipse([cxp - 10, cyp - 10, cxp + 10, cyp + 10], fill=(250, 205, 40), outline=(80, 60, 0))
    fx, fy = P(X1 - 5, 0); d.rectangle([fx - 4, fy - 1.6 * S, fx + 4, fy], fill=(220, 40, 40)); d.text((fx - 30, fy + 6), '1.6 m', font=f_sm, fill=(20, 20, 20))
    for t in range(TIERS):                                                         # 7 m terrace depth markers
        p0 = P(X1 + t * 7, t * 8 + 8); p1 = P(X1 + t * 7 + 7, t * 8 + 8)
        d.line([p0, p1], fill=(200, 40, 40), width=3)
    d.text((40, 20), 'The department store in profile: 8 m floors, each set back 7 m', font=f_title, fill=(20, 20, 20))
    d.text((40, 56), 'The red dashes mark each terrace you can stand on (7 m deep). A single jump reaches 2.1 m, so each 8 m step is a', font=f_sm, fill=(40, 40, 40))
    d.text((40, 76), 'climb: wall kicks, signs, pipes, a ramp or stairs. The skybridge from the station lands on terrace 2.', font=f_sm, fill=(40, 40, 40))
    img.save(out)

o = os.path.dirname(os.path.abspath(__file__))
render('se', 'Electric Town: ordered rows against the stepped store', os.path.join(o, 'from_south_east.png'))
render('sw', 'From the south-west', os.path.join(o, 'from_south_west.png'))
elevation(os.path.join(o, 'store_profile.png'))
