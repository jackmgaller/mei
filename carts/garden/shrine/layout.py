"""The shrine slice's layout sketch: writes from_road.png, from_mountain.png and top.png beside
this file (python3 carts/garden/shrine/layout.py). A planning sketch, not the world recipe: metres,
map x east, map y south (north is negative y), z up. Needs Pillow and macOS's Avenir Next."""
import math, random, sys, os
from PIL import Image, ImageDraw, ImageFont

W = 192
Y0, YMAX = -96, 192          # the forest now runs 96 m further north
WY = YMAX - Y0
STEP = 3
FONT = '/System/Library/Fonts/Avenir Next.ttc'
f_lab = ImageFont.truetype(FONT, 15, index=5)
f_title = ImageFont.truetype(FONT, 24, index=5)
f_sm = ImageFont.truetype(FONT, 13, index=0)

def clamp(v, a, b): return max(a, min(b, v))

# ---- the ground
ROAD = (164, 176)                                   # road band (map y)
COMPOUND = (46, 40, 146, 160)                       # cleared shrine area x1, y1, x2, y2
POND = [(162, 108, 16), (164, 140, 17)]             # two lobes, like the sketch
STREAM = [(150, -58), (160, -30), (176, 0), (170, 30), (178, 60), (172, 90), (164, 108)]
CLEARINGS = [(44, -42, 14, 12.0), (148, -64, 12, 30.0), (98, -14, 11, 11.0)]

def seg_dist(px, py, a, b):
    ax, ay = a; bx, by = b
    dx, dy = bx - ax, by - ay
    t = clamp(((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy), 0, 1)
    return math.hypot(px - ax - t * dx, py - ay - t * dy)

def stream_dist(x, y): return min(seg_dist(x, y, a, b) for a, b in zip(STREAM, STREAM[1:]))

def pond_dist(x, y): return min(math.hypot(x - cx, (y - cy) * 0.9) / r for cx, cy, r in POND)

def in_compound(x, y):
    x1, y1, x2, y2 = COMPOUND
    return x1 <= x <= x2 and y1 <= y <= y2

def height(x, y):
    if y >= ROAD[0] - 2: return 0.0
    if in_compound(x, y):
        if 70 <= x <= 122 and 50 <= y <= 74: return 8.6                  # the temple's platform
        if 50 <= x <= 150 and 46 <= y <= 113: return 5.0                 # the inner precinct terrace
        if 88 <= x <= 104 and 113 < y <= 121: return 5.0 - (y - 113) / 8 * 4.4   # steps down
        return 0.6
    # the forest: rolling ground, rising to a wooded ridge behind the temple
    h = 2.2 + 1.8 * math.sin(x / 13.0) * math.cos(y / 17.0) + 1.2 * math.sin((x + y) / 9.0)
    h += 18 * math.exp(-((y - 22) / 18) ** 2)                      # the ridge behind the temple
    h += 58 * clamp((-30 - y) / 50, 0, 1) ** 0.8                   # a steep back mountain
    if -44 < y < -30: h += 10 * clamp((-30 - y) / 14, 0, 1)          # its cliff band
    h += 6 * clamp((30 - x) / 30, 0, 1)
    for cx, cy, r, fl in CLEARINGS:                                 # clearings are flattened
        d = math.hypot(x - cx, y - cy)
        if d < r + 6:
            t = clamp((d - r) / 6, 0, 1)
            h = fl + (h - fl) * t
    edge = min(abs(x - COMPOUND[0]), abs(x - COMPOUND[2]), abs(y - COMPOUND[1]))
    if COMPOUND[0] - 10 < x < COMPOUND[2] + 10 and y > COMPOUND[1] - 10:
        h *= clamp(edge / 10, 0, 1)                 # the forest floor eases down to the precinct
    sd = stream_dist(x, y)
    if sd < 5: h = min(h, h - 2.5 * (1 - sd / 5) - 0.5)
    pd = pond_dist(x, y)
    if pd < 1: h = min(h, -2.5 + 2.5 * pd ** 4)
    return max(h, -2.5)

def is_water(x, y):
    return pond_dist(x, y) < 0.92 or (stream_dist(x, y) < 1.6 and y < ROAD[0] - 4)

# ---- objects
boxes, cones, blobs, labels = [], [], [], []
RED, ROOF, WOOD, STONE, WHITE = (196, 48, 38), (58, 60, 68), (150, 104, 66), (150, 146, 136), (234, 230, 216)

def box(x1, y1, x2, y2, h, col, z0=None, lab=None, lz=2):
    base = height((x1 + x2) / 2, (y1 + y2) / 2) if z0 is None else z0
    boxes.append((x1, y1, x2, y2, base, base + h, col))
    if lab: labels.append(((x1 + x2) / 2, (y1 + y2) / 2, base + h + lz, lab))
    return base

def hall(x1, y1, x2, y2, h, roof_h, col=RED, lab=None, over=1.5):
    z = box(x1, y1, x2, y2, h, col)
    box(x1 - over, y1 - over, x2 + over, y2 + over, roof_h * 0.45, ROOF, z + h)
    box(x1 + (x2 - x1) * 0.2, y1 + (y2 - y1) * 0.2, x2 - (x2 - x1) * 0.2, y2 - (y2 - y1) * 0.2, roof_h * 0.55, ROOF, z + h + roof_h * 0.45)
    if lab: labels.append(((x1 + x2) / 2, (y1 + y2) / 2, z + h + roof_h + 2, lab))

def torii(cx, cy, s=1.0):
    zb = height(cx, cy)
    box(cx - 4 * s, cy - 0.5 * s, cx - 3.2 * s, cy + 0.5 * s, 8 * s, RED, zb)
    box(cx + 3.2 * s, cy - 0.5 * s, cx + 4 * s, cy + 0.5 * s, 8 * s, RED, zb)
    box(cx - 5.2 * s, cy - 0.7 * s, cx + 5.2 * s, cy + 0.7 * s, 0.9 * s, (40, 30, 30), zb + 7.4 * s)
    box(cx - 4.4 * s, cy - 0.4 * s, cx + 4.4 * s, cy + 0.4 * s, 0.5 * s, RED, zb + 6.0 * s)

# south of the road: the konbini and a building, as in the sketch
box(14, 178, 50, 192, 5, (214, 218, 224), 0, 'Konbini')
box(14, 176.5, 50, 178, 0.3, (240, 120, 40), 3)
box(110, 178, 168, 192, 16, (184, 176, 160), 0, 'Building')

# the torii at the road and the approach
torii(96, 158, 1.5)
labels.append((96, 158, 15, 'Torii'))
for yy in range(124, 156, 8):
    box(93.5, yy, 98.5, yy + 4, 0.3, STONE, 0.6)                    # stone paving stepping north

# the four side halls (the long red buildings): two outside the inner wall, two inside
hall(58, 118, 70, 154, 6, 5, lab='Side hall')
hall(122, 118, 134, 154, 6, 5)
hall(58, 76, 70, 108, 6, 5, lab='Corridor hall')
hall(122, 76, 134, 108, 6, 5)

# the inner wall (the black line) with its gaps: the main gate, the north and east forest gates
def wall(points, gaps):
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        n = max(1, int(math.hypot(bx - ax, by - ay) // 2))
        for k in range(n):
            t0, t1 = k / n, (k + 1) / n
            x0, y0 = ax + (bx - ax) * t0, ay + (by - ay) * t0
            x1, y1 = ax + (bx - ax) * t1, ay + (by - ay) * t1
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            if any(math.hypot(mx - gx, my - gy) < gr for gx, gy, gr in gaps): continue
            box(min(x0, x1) - 0.4, min(y0, y1) - 0.4, max(x0, x1) + 0.4, max(y0, y1) + 0.4, 2.2, (238, 232, 214), 5.0)
WALL = [(80, 113), (52, 113), (48, 106), (48, 56), (52, 46), (62, 44), (140, 44), (150, 50), (152, 62), (150, 96), (140, 113), (112, 113)]
wall(WALL, [])
labels.append((96, 113, 4, 'Inner gate'))

# the big temple
hall(70, 52, 122, 72, 9, 12, col=WOOD, lab='Main temple', over=3)
# lanterns along the courtyard
for xx in (84, 108):
    for yy in (80, 92, 104):
        box(xx - 0.6, yy - 0.6, xx + 0.6, yy + 0.6, 2, STONE, 5.0)

# the pond with a small bridge and a stone lantern on an island
# the pond crossing: the only way out of the forest back to the shrine
STONES = [(176, 96), (171, 101), (167, 106), (162, 110), (158, 116), (163, 122), (167, 128), (162, 134), (156, 138), (151, 141)]
for k, (sx, sy) in enumerate(STONES):
    if k in (3, 4):                                                  # floating logs that bob
        box(sx - 3, sy - 0.8, sx + 3, sy + 0.8, 0.8, (120, 84, 50), -0.6)
    elif k in (6, 7):                                                # a stretch of zig-zag red bridge
        box(sx - 2.5, sy - 1.2, sx + 2.5, sy + 1.2, 0.5, RED, 0.4)
    else:
        box(sx - 1.2, sy - 1.2, sx + 1.2, sy + 1.2, 0.9, STONE, -0.5)
for (lx, ly) in [(170, 116), (154, 126), (172, 140), (158, 150)]:     # lily pads
    box(lx - 1.6, ly - 1.6, lx + 1.6, ly + 1.6, 0.15, (90, 160, 80), -0.5)
labels.append((165, 118, 4, 'Pond crossing'))
labels.append((150, 141, 4, 'Back to the shrine'))
# a bamboo fence closes the shrine's east side, so the crossing is the only way in
for fy in range(96, 132, 2):
    box(145.4, fy, 146.4, fy + 2, 3.2, (150, 170, 90), 0.6)
for fy in range(146, 162, 2):
    box(145.4, fy, 146.4, fy + 2, 3.2, (150, 170, 90), 0.6)

# the forest: autumn maples (orange), ginkgo (yellow) and tall cedars (dark green)
rnd = random.Random(11)
ROUTE = [(44, 150), (24, 132), (14, 100), (20, 64), (30, 30), (44, -42), (40, -70), (66, -78), (98, -60), (98, -14), (120, -40), (148, -64), (162, -20), (174, 20), (180, 60), (178, 92)]
def route_dist(x, y): return min(seg_dist(x, y, a, b) for a, b in zip(ROUTE, ROUTE[1:]))
for i in range(1500):
    x, y = rnd.uniform(2, 190), rnd.uniform(Y0 + 2, ROAD[0] - 6)
    if in_compound(x, y) or is_water(x, y) or pond_dist(x, y) < 1.15: continue
    if route_dist(x, y) < 3.5: continue
    if any(math.hypot(x - cx, y - cy) < r + 5 for cx, cy, r, fl in CLEARINGS): continue
    if 88 <= x <= 104 and y > 110: continue
    r = rnd.random()
    if r < 0.35:
        cones.append((x, y, rnd.uniform(2.0, 3.0), rnd.uniform(18, 30), (40, 86 + rnd.randint(-10, 10), 52)))
    elif r < 0.7:
        blobs.append((x, y, rnd.uniform(3, 4.5), rnd.uniform(7, 10), (222, 104 + rnd.randint(-20, 20), 36)))
    else:
        blobs.append((x, y, rnd.uniform(3, 4.5), rnd.uniform(8, 12), (238, 196 + rnd.randint(-15, 10), 46)))
# forest obstacles and red coins along the route
obst = [(24, 132, 'Fallen log'), (14, 100, 'Mossy boulders'), (22, 62, 'Stepping stones'), (32, 26, 'Old stone stairs'),
        (82, -70, 'Rope bridge'), (162, -22, 'Stream crossing'), (122, -42, 'Hollow log')]
for (x, y, lab) in obst:
    labels.append((x, y, height(x, y) + 6, lab))
box(20, 130, 30, 131.6, 1.6, (110, 80, 50))                         # fallen log
for k in range(4): box(12 + k * 3, 98 + k, 14 + k * 3, 100 + k, 2.5, (120, 120, 112))
box(78, -73, 88, -67, 0.6, (130, 90, 50), height(82, -70) + 4)        # rope bridge over a gully
for (x, y) in [(40, 146), (20, 118), (16, 84), (28, 44), (42, -58), (90, -66), (112, -30), (160, -40)]:
    z = height(x, y) + 1.4
    box(x - 0.8, y - 0.8, x + 0.8, y + 0.8, 1.6, (230, 30, 30), z)
labels.append((40, 146, height(40, 146) + 6, 'Red coins (8)'))


# the northern clearings
labels.append((44, -42, 13, 'Fox shrine grove'))
for k in range(0, 24, 4):
    torii(36 + k * 0.6, -50 + k, 0.55)
box(46, -40, 52, -35, 3, RED); box(45, -41, 53, -34, 1.2, ROOF, 12.0)
for (fx, fy) in [(40, -36), (50, -46), (54, -38)]:
    box(fx - 0.6, fy - 0.6, fx + 0.6, fy + 0.6, 1.8, (236, 236, 228))
labels.append((148, -64, 30, 'Waterfall clearing'))
box(140, -76, 156, -74, 34, (90, 150, 220), 30.0)                   # the falls off the back mountain
labels.append((98, -14, 26, 'Sacred tree'))
cones.append((98, -14, 4.5, 34, (34, 74, 44)))
box(95.5, -16.5, 100.5, -11.5, 0.6, (240, 240, 230), 15.0)          # shimenawa rope
stage_z = height(66, -86) + 1
for px in range(52, 82, 5):
    for py in range(-80, -64, 5):
        box(px - 0.6, py - 0.6, px + 0.6, py + 0.6, stage_z - height(px, py), WOOD, height(px, py))
box(50, -82, 82, -62, 1.0, (170, 124, 80), stage_z)
box(58, -96, 76, -86, 6, WOOD, stage_z); box(56, -98, 78, -84, 2.2, ROOF, stage_z + 6)
labels.append((66, -72, stage_z + 4, 'Hall on a stage (Kiyomizu-style)'))

# coins on the rooftops
def coin(x, y, z):
    box(x - 1.3, y - 1.3, x + 1.3, y + 1.3, 2.4, (250, 205, 40), z)
for (x, y) in [(96, 62), (64, 92), (128, 92), (64, 136), (128, 136)]:
    coin(x, y, 0.6 + (21 + 1 if y == 62 else 11 + 1))
coin(30, 185, 6.2); coin(140, 185, 17.2); coin(96, 158, 13.5)
labels.append((128, 136, 16, 'Rooftop coins'))


# a five-storey pagoda inside the precinct, and a two-storey gate
pz = 5.0
for i in range(5):
    sz = 4.5 - i * 0.5
    box(134 - sz, 56 - sz, 134 + sz, 56 + sz, 3.6, (160, 60, 46), pz + i * 5.4)
    box(134 - sz - 1.8, 56 - sz - 1.8, 134 + sz + 1.8, 56 + sz + 1.8, 0.9, ROOF, pz + i * 5.4 + 3.6)
box(133.6, 55.6, 134.4, 56.4, 6, (200, 170, 60), pz + 27)
labels.append((134, 56, pz + 36, 'Pagoda (30 m)'))
box(87, 109, 105, 116, 6, RED, 5.0); box(85, 107, 107, 118, 1.2, ROOF, 11.0)
box(88, 110, 104, 115, 4, RED, 12.2); box(86, 108, 106, 117, 1.6, ROOF, 16.2)
labels.append((96, 112, 20, 'Two-storey gate'))
# a treetop walkway in the west forest: platforms on giant cedars joined by rope bridges
TOPS = [(22, 50, 10), (16, 30, 14), (26, 12, 18), (40, 2, 21), (56, -8, 24)]
for k, (tx, ty, tz) in enumerate(TOPS):
    cones.append((tx, ty, 2.8, tz + 16, (34, 76, 46)))
    box(tx - 3, ty - 3, tx + 3, ty + 3, 0.6, (170, 124, 80), height(tx, ty) + tz)
    if k:
        px, py, pz2 = TOPS[k - 1]
        n = 6
        for j in range(1, n):
            t = j / n
            bx, by = px + (tx - px) * t, py + (ty - py) * t
            bz = height(px, py) + pz2 + (height(tx, ty) + tz - height(px, py) - pz2) * t - 1.2 * math.sin(math.pi * t)
            box(bx - 0.8, by - 0.8, bx + 0.8, by + 0.8, 0.3, (130, 96, 60), bz)
labels.append((26, 12, height(26, 12) + 24, 'Treetop walkway'))
coin(56, -8, height(56, -8) + 25.5)
coin(134, 56, pz + 34)

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
    S = 2.6
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
    img = Image.new('RGB', (1120, 1060), (228, 232, 238))
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
    d.text((30, 54), '192 x 288 m. Verticality pass: terraced precinct, pagoda, two-storey gate, treetop walkway, mountain stage.', font=f_sm, fill=(40, 40, 40))
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

o = os.path.dirname(os.path.abspath(__file__))
render('se', 'Shrine in the forest, from the road (south-east)', os.path.join(o, 'from_road.png'))
render('nw', 'From behind the ridge (north-west)', os.path.join(o, 'from_mountain.png'))
topdown(os.path.join(o, 'top.png'))
