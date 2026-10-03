"""The movement garden's layout sketch: writes layout.png beside this file.

A planning sketch, not the world recipe: units are metres, north is up, map x is east and map y
is south. Run: python3 carts/garden/layout.py (needs Pillow and macOS's Avenir Next)."""
from PIL import Image, ImageDraw, ImageFont
import math, os, sys

S = 11          # pixels per metre
M = 40          # margin
SIZE = 64       # garden is 64 x 64 m
FONT = '/System/Library/Fonts/Avenir Next.ttc'
f_lab = ImageFont.truetype(FONT, 13, index=5)   # demi bold
f_sm = ImageFont.truetype(FONT, 11, index=0)
f_title = ImageFont.truetype(FONT, 22, index=5)
f_leg = ImageFont.truetype(FONT, 13, index=0)

GRASS = (126, 160, 98)
PAVE = (196, 190, 176)
ROAD = (92, 92, 98)
PIT = (40, 44, 58)
FEAT = (232, 128, 60)
COIN = (250, 204, 40)
GLIDE = (250, 230, 120)
INK = (30, 30, 34)

def P(x, y): return (M + x * S, M + 46 + y * S)

def bldg(h):
    v = int(120 + min(h, 20) * 5.5)
    return (v, v - 6, v - 14)

def text_c(d, x, y, s, font=f_lab, fill=INK):
    w = d.textlength(s, font=font)
    d.text((x - w / 2, y), s, font=font, fill=fill)

def draw(d, items):
    for it in items:
        k = it[0]
        if k in ('area', 'bldg', 'feat', 'pit'):
            _, x0, y0, x1, y1, h, lab = (it + (None,) * 7)[:7]
            col = {'area': PAVE, 'pit': PIT, 'feat': FEAT}.get(k) or bldg(h)
            if k == 'area' and h == 'grass': col, h = GRASS, None
            if k == 'area' and h == 'road': col, h = ROAD, None
            d.rectangle([P(x0, y0), P(x1, y1)], fill=col, outline=INK, width=1)
            if lab:
                cx, cy = P((x0 + x1) / 2, (y0 + y1) / 2)
                lines = lab.split('\n')
                fill = (240, 240, 240) if k == 'pit' or col == ROAD else INK
                for i, ln in enumerate(lines):
                    text_c(d, cx, cy - 9 * len(lines) + i * 17, ln, fill=fill)
            if isinstance(h, (int, float)):
                d.text((P(x0, y0)[0] + 3, P(x0, y0)[1] + 1), f'{h:g} m', font=f_sm,
                       fill=(240, 240, 240) if k == 'pit' else INK)
        elif k == 'slope':          # ramp, shaded low to high along dir
            _, x0, y0, x1, y1, dirn, lab = it
            n = 24
            for i in range(n):
                t = i / n
                c = tuple(int(a + (b - a) * t) for a, b in zip((150, 120, 80), (240, 200, 150)))
                if dirn in 'EW':
                    a = x0 + (x1 - x0) * (t if dirn == 'E' else 1 - t - 1 / n)
                    d.rectangle([P(a, y0), P(a + (x1 - x0) / n, y1)], fill=c)
                else:
                    a = y0 + (y1 - y0) * (t if dirn == 'S' else 1 - t - 1 / n)
                    d.rectangle([P(x0, a), P(x1, a + (y1 - y0) / n)], fill=c)
            d.rectangle([P(x0, y0), P(x1, y1)], outline=INK, width=1)
            cx, cy = P((x0 + x1) / 2, (y0 + y1) / 2)
            text_c(d, cx, cy - 8, lab)
        elif k == 'pole':
            _, x, y, lab = it
            cx, cy = P(x, y)
            d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=FEAT, outline=INK, width=2)
            d.text((cx + 9, cy - 8), lab, font=f_lab, fill=INK)
        elif k == 'rail':
            _, pts, lab = it
            pp = [P(*p) for p in pts]
            d.line(pp, fill=INK, width=7); d.line(pp, fill=FEAT, width=4)
            if lab:
                mx, my = pp[len(pp) // 2]
                d.text((mx + 8, my - 18), lab, font=f_lab, fill=INK)
        elif k == 'coin':
            _, x, y = it
            cx, cy = P(x, y)
            pts = []
            for i in range(10):
                r = 11 if i % 2 == 0 else 5
                a = -math.pi / 2 + i * math.pi / 5
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            d.polygon(pts, fill=COIN, outline=INK)
        elif k == 'spawn':
            _, x, y = it
            cx, cy = P(x, y)
            d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=(255, 255, 255), outline=INK, width=3)
            d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=INK)
        elif k in ('glide', 'move', 'route'):
            _, pts = it[:2]
            pp = [P(*p) for p in pts]
            col = {'glide': GLIDE, 'move': (255, 255, 255), 'route': (255, 255, 255)}[k]
            for (ax, ay), (bx, by) in zip(pp, pp[1:]):
                L = math.hypot(bx - ax, by - ay); n = int(L // 10)
                for i in range(0, n, 2):
                    t0, t1 = i / n, min((i + 1) / n, 1)
                    seg = [(ax + (bx - ax) * t0, ay + (by - ay) * t0), (ax + (bx - ax) * t1, ay + (by - ay) * t1)]
                    d.line(seg, fill=INK, width=5); d.line(seg, fill=col, width=3)
            (ax, ay), (bx, by) = pp[-2], pp[-1]
            a = math.atan2(by - ay, bx - ax)
            head = [(bx, by), (bx - 13 * math.cos(a - .45), by - 13 * math.sin(a - .45)),
                    (bx - 13 * math.cos(a + .45), by - 13 * math.sin(a + .45))]
            d.polygon(head, fill=col, outline=INK)
            if k == 'move':   # two-way
                (ax, ay), (bx, by) = pp[1], pp[0]
                a = math.atan2(by - ay, bx - ax)
                d.polygon([(bx, by), (bx - 13 * math.cos(a - .45), by - 13 * math.sin(a - .45)),
                           (bx - 13 * math.cos(a + .45), by - 13 * math.sin(a + .45))], fill=col, outline=INK)
        elif k == 'zone':
            _, x0, y0, x1, y1 = it
            a, b = P(x0, y0), P(x1, y1)
            for x in range(int(a[0]), int(b[0]), 12):
                d.line([(x, a[1]), (min(x + 6, b[0]), a[1])], fill=(60, 110, 230), width=3)
                d.line([(x, b[1]), (min(x + 6, b[0]), b[1])], fill=(60, 110, 230), width=3)
            for y in range(int(a[1]), int(b[1]), 12):
                d.line([(a[0], y), (a[0], min(y + 6, b[1]))], fill=(60, 110, 230), width=3)
                d.line([(b[0], y), (b[0], min(y + 6, b[1]))], fill=(60, 110, 230), width=3)
        elif k in ('note', 'notew'):
            _, x, y, s = it
            d.text(P(x, y), s, font=f_sm, fill=INK if k == 'note' else (240, 240, 240))

def legend(d, x, y, notes):
    rows = [('spawn', 'Spawn'), ('feat', 'Movement feature'), ('slope', 'Slope (light = high)'),
            ('bldg', 'Building / block (light = tall)'), ('pit', 'Pit'), ('coin', 'Coin'),
            ('glide', 'Glide line'), ('zone', 'Camera zone')]
    for kind, lab in rows:
        if kind == 'spawn':
            d.ellipse([x, y, x + 16, y + 16], fill='white', outline=INK, width=3)
        elif kind == 'coin':
            d.polygon([(x + 8, y), (x + 10, y + 6), (x + 16, y + 6), (x + 11, y + 10), (x + 13, y + 16),
                       (x + 8, y + 12), (x + 3, y + 16), (x + 5, y + 10), (x, y + 6), (x + 6, y + 6)], fill=COIN, outline=INK)
        elif kind == 'glide':
            d.line([(x, y + 8), (x + 16, y + 8)], fill=INK, width=5); d.line([(x, y + 8), (x + 16, y + 8)], fill=GLIDE, width=3)
        elif kind == 'zone':
            d.rectangle([x, y, x + 16, y + 16], outline=(60, 110, 230), width=3)
        else:
            col = {'feat': FEAT, 'slope': (200, 160, 115), 'bldg': bldg(10), 'pit': PIT}[kind]
            d.rectangle([x, y, x + 16, y + 16], fill=col, outline=INK)
        d.text((x + 24, y - 1), lab, font=f_leg, fill=INK)
        y += 26
    y += 14
    for n in notes:
        d.text((x, y), n, font=f_leg, fill=INK); y += 20

def render(name, title, items, notes, out, size=64, scale=11, grid=8):
    global S, SIZE
    S, SIZE = scale, size
    W = M * 2 + SIZE * S + 280
    H = M * 2 + 46 + SIZE * S
    img = Image.new('RGB', (W, H), (246, 244, 238))
    d = ImageDraw.Draw(img)
    d.text((M, M - 10), title, font=f_title, fill=INK)
    d.rectangle([P(0, 0), P(SIZE, SIZE)], fill=GRASS, outline=INK, width=2)
    for i in range(0, SIZE + 1, grid):
        d.line([P(i, 0), P(i, SIZE)], fill=(110, 142, 86), width=1)
        d.line([P(0, i), P(SIZE, i)], fill=(110, 142, 86), width=1)
    draw(d, items)
    lx = M + SIZE * S + 30
    sx, sy = lx, M + 46
    d.line([(sx, sy + 8), (sx + grid * S, sy + 8)], fill=INK, width=3)
    d.text((sx + grid * S + 8, sy), f'{grid} m (grid)', font=f_leg, fill=INK)
    d.text((sx, sy + 22), f'Whole map: {SIZE} x {SIZE} m, north up', font=f_leg, fill=INK)
    legend(d, lx, sy + 60, notes)
    img.save(os.path.join(out, name + '.png'))


D = [
    # streets and the scramble crossing
    ('area', 0, 58, 128, 70, 'road', ''), ('area', 56, 0, 70, 128, 'road', ''),
    ('area', 56, 58, 70, 70, None, 'Scramble'),
    # elevated train line on pillars, north of the street
    ('area', 0, 46, 128, 52, None, ''), ('note', 72, 47.5, 'Elevated line, 10 m up: ride the train, hop off'),
    ('feat', 20, 46.5, 42, 51.5, None, ''), ('move', [(43, 49), (54, 49)]),
    ('bldg', 72, 39, 100, 46, 10, 'Station'), ('slope', 100, 39, 108, 46, 'W', ''),
    # NW: apartments, alley, office
    ('bldg', 4, 4, 24, 40, 14, 'Apartments'), ('feat', 2, 8, 4, 36, None, ''), ('note', 0.5, 37, 'Fire escape'),
    ('feat', 24, 6, 25, 38, None, ''),
    ('pit', 25, 4, 28, 40, 0, ''), ('zone', 24, 2, 29, 42), ('note', 22, 0.4, 'Kick alley 3 m'),
    ('bldg', 28, 4, 52, 34, 24, 'Office'), ('coin', 47, 9),
    ('feat', 33, 34, 44, 36, None, ''), ('note', 33, 36.3, 'Gondola'),
    ('bldg', 44, 20, 50, 26, 27, ''), ('note', 40.5, 26.3, 'Water tank'),
    # NE: construction site and crane
    ('area', 72, 2, 126, 36, None, ''), ('note', 73, 2.5, 'Construction site'),
    ('bldg', 76, 8, 100, 32, 30, 'Steel frame'), ('pole', 75, 7, ''), ('pole', 101, 7, ''), ('pole', 75, 33, ''), ('pole', 101, 33, ''),
    ('note', 76, 32.6, 'Scaffold poles, girder walks'),
    ('bldg', 110, 16, 116, 22, 36, ''), ('coin', 113, 19),
    ('rail', [(110, 19), (88, 19)], ''), ('note', 104, 23, 'Crane jib (beam)'),
    ('feat', 91, 23, 95, 27, None, ''), ('move', [(93, 28), (93, 35)]), ('note', 104, 26, 'Hook (moving)'),
    # wires and the overpass
    ('pole', 6, 56, ''), ('pole', 22, 56, ''), ('pole', 38, 56, ''), ('rail', [(6, 56), (22, 56), (38, 56)], ''),
    ('note', 6, 52.6, 'Pole wires = rail'),
    ('area', 44, 54, 50, 74, None, ''), ('rail', [(47, 53), (47, 75)], ''), ('note', 37, 74.5, 'Overpass rail'),
    ('rail', [(92, 72), (122, 56)], ''), ('pole', 92, 72, ''), ('pole', 122, 56, ''),
    # SE: konbini, shrine hill, festival
    ('bldg', 72, 76, 90, 92, 5, 'Konbini'), ('feat', 72, 72.5, 90, 76, None, ''), ('note', 73, 72.6, 'Bounce awning'),
    ('area', 94, 72, 126, 126, None, ''), ('note', 95, 72.5, 'Shrine hill'),
    ('slope', 96, 96, 106, 124, 'N', 'Steps'),
    ('bldg', 106, 76, 126, 126, 10, ''),
    ('bldg', 110, 80, 122, 92, 26, 'Pagoda'), ('coin', 116, 84),
    ('feat', 108, 98, 124, 104, None, ''), ('note', 108, 104.5, 'Festival stalls (night)'),
    ('bldg', 110, 110, 122, 122, 15, 'Shrine'),
    # SW: car park, park with spawn and test strip
    ('bldg', 4, 74, 30, 104, 12, ''), ('slope', 8, 78, 26, 86, 'E', 'Car park ramps'),
    ('slope', 8, 92, 26, 100, 'W', ''), ('coin', 26, 98),
    ('area', 34, 76, 54, 126, 'grass', ''), ('note', 35, 76.5, 'Park'),
    ('spawn', 44, 121),
    ('bldg', 35, 82, 36, 94, 8), ('bldg', 38, 82, 39, 94, 8), ('bldg', 42, 82, 43, 94, 8), ('bldg', 47, 82, 48, 94, 8),
    ('note', 35, 94.5, 'Kick walls'),
    ('slope', 35, 98, 37.5, 110, 'N', ''), ('slope', 38.5, 98, 41, 110, 'N', ''), ('slope', 42, 98, 44.5, 110, 'N', ''), ('slope', 45.5, 98, 48, 110, 'N', ''),
    ('note', 35, 110.5, 'Mounds 15-60'),
    ('feat', 49.5, 98, 53, 112, None, ''), ('note', 44, 113, 'Slide'),
    ('bldg', 4, 108, 30, 124, 6, 'Bathhouse'),
    # glide lines
    ('glide', [(46, 12), (60, 60), (100, 92)]),
    ('glide', [(113, 24), (100, 56), (80, 74)]),
]

if __name__ == '__main__':
    render('layout', 'C2. City block', D,
           ['128 x 128 m: one World Kit cell at', 'the largest size, or four 64 m cells.',
            'Five coins, one per corner + crane.', 'Spawn in the park, south-west.',
            'Train circles the line; ride it', 'to cross the block fast.'],
           os.path.dirname(os.path.abspath(__file__)), size=128, scale=7, grid=16)
