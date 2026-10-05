"""Writes festival_yagura.asset.json, festival_yagura_col.asset.json and art/ beside this script
(python3 make_festival_yagura.py; Pillow for the art): the bon-odori tower on the park's
festival ground (shrine town spec 3.16; assets.md #31), a climbable landmark.

A timber scaffold in two tiers wrapped in red-and-white kohaku cloth: the lower stage, 6.1 m
square, its deck at 2.45 with a railing (top 3.35) hung with paper lanterns; the drummers' stage,
3.9 m square, its deck at 4.72 with a railing (top 5.45) and a taiko on a stand; four posts
carrying a low pyramid roof (eaves 6.6 at +-2.3, apex 7.6, 23.5 degrees, walkable) and the
lantern pole to 8.0, where the festival's lantern strings start. Vertical ladders at the back
(+Z): ground to the lower deck at x +1.2, lower deck to the upper at x -0.6, each through a gap in
its railing.

Origin at the centre of the footprint at ground level; front (-Z) toward the dance ground.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

ART = HERE / 'art'

# lower tier
SK1 = 2.9                    # skirt half width
D1 = (3.05, 2.28, 2.45)      # deck slab: half width, bottom, top
R1 = (3.0, 2.9, 3.25, 3.35)  # railing ring: outer, inner half widths, bottom, top
P1 = (2.83, 2.95)            # corner posts' span (each axis, positive side)
# upper tier
SK2 = 1.75
D2 = (1.95, 4.58, 4.72)
R2 = (1.9, 1.8, 5.35, 5.45)
P2 = (1.72, 1.86)            # roof posts' span
# roof
RE, RLO, RHI, APEX = 2.3, 6.45, 6.6, 7.6
POLE = (0.06, 7.5, 8.0)      # half width, bottom, top
# ladders (x centre, plane z, bottom, top) and the railing gaps they come through
LAD1 = (1.2, 3.12, 0.0, 3.3)
LAD2 = (-0.6, 2.02, 2.45, 5.4)
GAP1 = (0.8, 1.6)
GAP2 = (-1.0, -0.2)
BAND = (3.08, 2.66, 3.22)    # lantern band: plane, bottom, top


# --------------------------------------------------------------------------------------------
# art

def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def draw_art():
    ART.mkdir(exist_ok=True)
    # kohaku: red and white stripes, 16 texels each, with the folds of gathered cloth
    im = Image.new('RGBA', (32, 32))
    px = im.load()
    red, red_d, red_l = rgb('#c8301e'), rgb('#8a2418'), rgb('#d8462a')
    wht, wht_d = rgb('#ece4d2'), rgb('#c8bfac')
    for x in range(32):
        for y in range(32):
            k = x % 16
            if x < 16:
                c = red_d if k in (0, 7) else red_l if k in (3, 11) else red
            else:
                c = wht_d if k in (0, 7) else wht
            if y in (0,) and x % 4 == 0:
                c = red_d if x < 16 else wht_d
            px[x, y] = c
    im.save(ART / 'kohaku.png')

    # chochin: a string of paper lanterns, alternating red and white, holes between (cutout)
    im = Image.new('RGBA', (128, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    string = rgb('#2c2a28')
    d.line([(0, 0), (127, 0)], fill=string)
    for k in range(12):
        cx = 5 + k * 10.6
        x0 = int(round(cx - 3))
        body = rgb('#e0502a') if k % 2 == 0 else rgb('#f4ead0')
        rib = rgb('#a8321e') if k % 2 == 0 else rgb('#d8b048')
        d.point((x0 + 3, 1), fill=string)
        d.rectangle([x0 + 1, 2, x0 + 5, 2], fill=string)          # cap
        d.rectangle([x0, 3, x0 + 6, 12], fill=body)
        d.point([(x0, 3), (x0 + 6, 3), (x0, 12), (x0 + 6, 12)], fill=(0, 0, 0, 0))
        for y in (5, 8, 11):
            d.line([(x0 + 1, y), (x0 + 5, y)], fill=rib)
        d.rectangle([x0 + 1, 13, x0 + 5, 13], fill=string)        # foot
        if k % 2 == 1:
            d.line([(x0 + 3, 4), (x0 + 3, 10)], fill=rgb('#c8301e'))   # a painted mark
    im.save(ART / 'chochin.png')

    # ladder: two stiles and rungs, holes between
    im = Image.new('RGBA', (16, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    wood, wood_d = rgb('#8a6446'), rgb('#5a3e2c')
    d.rectangle([0, 0, 2, 63], fill=wood)
    d.rectangle([13, 0, 15, 63], fill=wood)
    d.line([(2, 0), (2, 63)], fill=wood_d)
    d.line([(15, 0), (15, 63)], fill=wood_d)
    for y in range(4, 64, 6):
        d.rectangle([3, y, 12, y + 1], fill=wood)
        d.line([(3, y + 1), (12, y + 1)], fill=wood_d)
    im.save(ART / 'ladder.png')


# --------------------------------------------------------------------------------------------
# parts

MATS = {
    'kohaku': {'color': '#d8462a', 'texture': {'image': 'art/kohaku.png', 'projection': 'box'}},
    'planks': {'color': '#a07a52', 'texture': {'image': ap.ART + 'forest_planks.png',
                                               'projection': 'planar', 'axis': 'y',
                                               'scale': [2, 2]}},
    'roof': {'color': '#8a8e92', 'tag': 'roof',
             'texture': {'sheet': 'town_common', 'cell': 'tin', 'projection': 'box',
                         'scale': [2, 2]}},
    'ladder': {'color': '#8a6446', 'double_sided': True,
               'texture': {'image': 'art/ladder.png', 'projection': 'fit'}},
    'chochin': {'color': '#f0b050', 'class': 'emissive', 'tag': 'lantern', 'double_sided': True,
                'texture': {'image': 'art/chochin.png', 'projection': 'fit'}},
    'wood': {'color': '#8a6446', 'palette': True},
    'wood_dark': {'color': '#5a3e2c', 'palette': True},
    'wood_new': {'color': '#b08a5e', 'palette': True},
    'drum': {'color': '#a8321e', 'palette': True},
    'drum_head': {'color': '#ece4d2', 'palette': True},
    'black': {'color': '#2c2a28', 'palette': True},
}
SHEETS = {'town_common': {'image': '../town_alley_house_a/art/town_common.png'}}


def ring(p, outer, inner, y0, y1, gap=None, bottom=True, inner_faces=True, mat='wood_new'):
    """A square railing bar around the origin: top, outer, inner and bottom faces, mitred at the
    corners. `gap` = (x0, x1) leaves an opening in the back (+Z) side, with end caps."""
    o, i = outer, inner
    # per side: outer corners (left, right as seen from outside), inner corners
    sides = {
        'front': ((-o, -o), (o, -o), (-i, -i), (i, -i)),
        'right': ((o, -o), (o, o), (i, -i), (i, i)),
        'back': ((o, o), (-o, o), (i, i), (-i, i)),
        'left': ((-o, o), (-o, -o), (-i, i), (-i, -i)),
    }
    for name, (ol, orr, il, ir) in sides.items():
        pieces = [(ol, orr, il, ir)]
        if name == 'back' and gap:
            g0, g1 = gap          # x from g1 down to g0 (the back runs from +x to -x)
            pieces = [(ol, (g1, o), il, (g1, i)), ((g0, o), orr, (g0, i), ir)]
        for (a, b, c, e) in pieces:
            P = lambda q, y: (q[0], y, q[1])
            p.face(mat, [P(c, y1), P(e, y1), P(b, y1), P(a, y1)])          # top
            p.face(mat, [P(a, y1), P(b, y1), P(b, y0), P(a, y0)])          # outer
            if inner_faces:
                p.face(mat, [P(e, y1), P(c, y1), P(c, y0), P(e, y0)])      # inner
            if bottom:
                p.face('wood', [P(a, y0), P(b, y0), P(e, y0), P(c, y0)])   # bottom
        if name == 'back' and gap:
            g0, g1 = gap
            # caps facing into the gap
            p.face(mat, [(g1, y1, i), (g1, y1, o), (g1, y0, o), (g1, y0, i)][::-1])
            p.face(mat, [(g0, y1, o), (g0, y1, i), (g0, y0, i), (g0, y0, o)][::-1])


def tier(p, skirt, deck, sk_y0, slab_bottom=True):
    hw, y0, y1 = deck
    p.box('kohaku', -skirt, skirt, sk_y0, y0 + 0.02, -skirt, skirt, open=('top', 'bottom'),
          su=1.0)
    sides = {'*': 'wood_dark', 'top': 'planks'}
    p.box(sides, -hw, hw, y0, y1, -hw, hw, open=() if slab_bottom else ('bottom',))


def posts(p, span, y0, y1, mat='wood', outer_only=False):
    a, b = span
    for sx in (-1, 1):
        for sz in (-1, 1):
            x0, x1 = sorted((sx * a, sx * b))
            z0, z1 = sorted((sz * a, sz * b))
            shut = ('top', 'bottom')
            if outer_only:
                shut += ('left' if sx > 0 else 'right', 'back' if sz > 0 else 'front')
            p.box(mat, x0, x1, y0, y1, z0, z1, open=shut)


def roof(p, soffit=True, fascia=True):
    e, lo, hi, ap_ = RE, RLO, RHI, APEX
    corners = [(-e, -e), (e, -e), (e, e), (-e, e)]
    for k in range(4):
        (x0, z0), (x1, z1) = corners[k], corners[(k + 1) % 4]
        tri = [(x0, hi, z0), (0.0, ap_, 0.0), (x1, hi, z1)]
        # slopes: tin's corrugations run down the slope
        p.face_uv('roof', [tri[1], tri[2], tri[0]], 2.0, 2.0)
        if fascia:
            p.face('black', [(x0, hi, z0), (x1, hi, z1), (x1, lo, z1), (x0, lo, z0)])
    if soffit:
        p.face('wood_dark', [(-e, lo, -e), (e, lo, -e), (e, lo, e), (-e, lo, e)])


def taiko(nodes):
    y = D2[2] + 0.42 + 0.36
    nodes.append({'id': 'taiko', 'op': 'cylinder', 'radius': 0.36, 'height': 0.5, 'segments': 8,
                  'material': 'drum', 'faces': {'top': 'drum_head', 'bottom': 'drum_head'},
                  'transform': {'rotate': [90, 0, 0], 'translate': [0.0, y, 0.25]}})
    nodes.append({'id': 'stand', 'op': 'box', 'size': [0.7, 0.44, 0.4], 'material': 'wood_dark',
                  'open': ['bottom'],
                  'transform': {'translate': [0.0, D2[2] - 0.02 + 0.22, 0.25]}})


def ladder(p, lad, mat='ladder'):
    x, z, y0, y1 = lad
    p.face(mat, [(x - 0.3, y1, z), (x + 0.3, y1, z), (x + 0.3, y0, z), (x - 0.3, y0, z)],
           [(0, 0), (1, 0), (1, 1), (0, 1)])


def band(p):
    """The lanterns hung along the outside of the lower railing, the back side split around the
    ladder."""
    r, y0, y1 = BAND
    L = r - 0.05

    def strip(a, b, u0=0.0, u1=1.0):
        (ax, az), (bx, bz) = a, b
        p.face('chochin', [(ax, y1, az), (bx, y1, bz), (bx, y0, bz), (ax, y0, az)],
               [(u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)])
    strip((-L, -r), (L, -r))
    strip((r, -L), (r, L))
    strip((-r, L), (-r, -L))
    g0, g1 = LAD1[0] - 0.4, LAD1[0] + 0.4
    span = 2 * L
    strip((L, r), (g1, r), 0.0, (L - g1) / span)
    strip((g0, r), (-L, r), (L - g0) / span, 1.0)


def finial(p):
    h, y0, y1 = POLE
    p.box('wood', -h, h, y0, y1, -h, h, open=('bottom',))


def level0():
    base, rail, up, rf, det = (ap.Part(n) for n in ('lower', 'railings', 'upper', 'roof',
                                                     'details'))
    tier(base, SK1, D1, 0.0)
    posts(rail, P1, D1[2] - 0.02, R1[2] + 0.02)
    ring(rail, R1[0], R1[1], R1[2], R1[3], gap=GAP1)
    tier(up, SK2, D2, D1[2] - 0.02)
    posts(up, P2, D2[2] - 0.02, RLO + 0.02)
    ring(rail, R2[0], R2[1], R2[2], R2[3], gap=GAP2)
    roof(rf)
    finial(rf)
    ladder(det, LAD1)
    ladder(det, LAD2)
    band(det)
    nodes = [base, rail, up, rf, det]
    taiko(nodes)
    return nodes


def level1():
    """From 30 m: the tiers' skirts and decks (no slab undersides), the railings' outer faces, the
    roof posts' outer faces, the roof without its fascia, the lanterns."""
    p = ap.Part('yagura')
    tier(p, SK1, D1, 0.0, slab_bottom=False)
    tier(p, SK2, D2, D1[2] - 0.02, slab_bottom=False)
    for r in (R1, R2):          # the railings' outer faces only
        o = r[0]
        for pts in ([(-o, -o), (o, -o)], [(o, -o), (o, o)], [(o, o), (-o, o)], [(-o, o), (-o, -o)]):
            (ax, az), (bx, bz) = pts
            p.face('wood_new', [(ax, r[3], az), (bx, r[3], bz), (bx, r[2], bz), (ax, r[2], az)])
    posts(p, P2, D2[2] - 0.02, RLO + 0.02, outer_only=True)
    roof(p, fascia=False)
    q = ap.Part('lanterns')
    band(q)
    return [p, q]


def level2():
    """From 70 m: the two cloth blocks, the open storey under the roof as a dark block, the
    roof."""
    p = ap.Part('yagura')
    p.box({'*': 'kohaku', 'top': 'wood_new'}, -D1[0], D1[0], 0.0, D1[2], -D1[0], D1[0],
          open=('bottom',), su=1.0)
    p.box('kohaku', -D2[0], D2[0], D1[2] - 0.02, D2[2], -D2[0], D2[0],
          open=('top', 'bottom'), su=1.0)
    p.box('wood_dark', -P2[1], P2[1], D2[2] - 0.02, RLO + 0.02, -P2[1], P2[1],
          open=('top', 'bottom'))
    e, lo, hi = RE, RLO, RHI
    corners = [(-e, -e), (e, -e), (e, e), (-e, e)]
    for k in range(4):
        (x0, z0), (x1, z1) = corners[k], corners[(k + 1) % 4]
        p.face('black', [(x0, lo, z0), (0.0, APEX, 0.0), (x1, lo, z1)])
    p.face('wood_dark', [(-e, lo, -e), (e, lo, -e), (e, lo, e), (-e, lo, e)])
    return [p]


def collision():
    p = ap.Part('body')
    hw, _, top = D1
    ap.col_box(p, -hw, hw, 0.0, top, -hw, hw, open=('bottom',))
    # lower railing: walls 0.2 thick inside the deck's edge, a gap at the ladder
    rails(p, hw, top, R1[3], GAP1)
    h2, _, top2 = D2
    ap.col_box(p, -h2, h2, top, top2, -h2, h2, open=('bottom',))
    rails(p, h2, top2, R2[3], GAP2)
    # the taiko and its stand
    ap.col_box(p, -0.38, 0.38, top2, top2 + 1.14, -0.05, 0.55, open=('bottom',))
    # roof posts (0.24 square) from the upper railing to the roof
    for sx in (-1, 1):
        for sz in (-1, 1):
            c = (P2[0] + P2[1]) / 2
            ap.col_box(p, sx * c - 0.12, sx * c + 0.12, R2[3], RLO, sz * c - 0.12, sz * c + 0.12,
                       open=('bottom', 'top'))
    # roof: four slopes from the fascia top to the apex, the fascia and a flat soffit
    e = RE
    corners = [(-e, -e), (e, -e), (e, e), (-e, e)]
    for k in range(4):
        (x0, z0), (x1, z1) = corners[k], corners[(k + 1) % 4]
        p.face('solid', [(x0, RHI, z0), (0.0, APEX, 0.0), (x1, RHI, z1)])
        p.face('solid', [(x0, RHI, z0), (x1, RHI, z1), (x1, RLO, z1), (x0, RLO, z0)])
    ap.col_quad(p, (-e, RLO, -e), (e, RLO, -e), (e, RLO, e), (-e, RLO, e))
    return [p]


def rails(p, hw, y0, y1, gap):
    t = 0.2
    a = hw - t
    ap.col_box(p, -hw, hw, y0, y1, -hw, -a, open=('bottom',))                 # front
    ap.col_box(p, a, hw, y0, y1, -a, a, open=('bottom', 'back', 'front'))     # right
    ap.col_box(p, -hw, -a, y0, y1, -a, a, open=('bottom', 'back', 'front'))   # left
    g0, g1 = gap
    ap.col_box(p, g1, hw, y0, y1, a, hw, open=('bottom',))                    # back, east part
    ap.col_box(p, -hw, g0, y0, y1, a, hw, open=('bottom',))                   # back, west part


def main():
    draw_art()
    lod = {'levels': [(30, level1()), (70, level2())], 'band': 2}
    r = ap.recipe('festival_yagura', MATS, level0(), 300, lod)
    r = {'format': r.pop('format'), 'version': r.pop('version'), 'name': r.pop('name'),
         'sheets': SHEETS, **r}
    ap.write(HERE / 'festival_yagura.asset.json', r)
    ap.write(HERE / 'festival_yagura_col.asset.json',
             ap.col_recipe('festival_yagura_col', collision()))


if __name__ == '__main__':
    main()
