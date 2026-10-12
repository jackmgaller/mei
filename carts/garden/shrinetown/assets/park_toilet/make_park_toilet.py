"""Writes park_toilet.asset.json, park_toilet_col.asset.json and art/ beside this script
(python3 make_park_toilet.py; Pillow and macOS's Hiragino Sans for the art): the park's public
toilet (shrine town spec 3.16; assets.md #30), a 1990s concrete block with a flat roof, and a
step onto the park's routes.

A 5.2 x 4.0 m block of painted concrete over a brown mosaic-tile wainscot, on a 0.12 m pad,
under a flat concrete roof slab (top 3.0, 6.0 x 5.2, its front 0.8 m out as a canopy over the two
doorways). In front of each doorway a privacy wall 1.8 m wide, 0.3 m thick and 1.9 m tall, with
the men's and women's pictograms; the sign over the doorways; breeze-block vents under the roof;
a cleaner's door at the back, a hand basin on the east side, a water tank on the roof, a
fluorescent lamp under the canopy (emissive, `window`).

The route: ground -> a privacy wall's top (1.9, a jump) -> the roof (3.0, a hop, its edge 0.25 m
behind the wall) or the roof's edge straight from the ground (jump and grab) -> the tank (3.6).

Origin at the centre of the block's width and of the whole footprint's depth, at ground level;
front (-Z) toward the park.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

ART = HERE / 'art'
JP_FONT = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'

PAD = (3.0, -3.1, 2.6, 0.12)          # half x, z0, z1, top
BLOCK = (2.6, -1.6, 2.4, 2.72)        # half x, z0 (front), z1, top (under the slab)
SLAB = (3.0, -2.4, 2.8, 2.7, 3.0)     # half x, z0, z1, bottom, top
SCREEN = (0.5, 2.3, -2.95, -2.65, 1.9)  # x from, x to (each side), z0, z1, top
DOOR_X = 1.4
TANK = (-1.7, -0.5, 0.6, 1.6, 3.6)    # x0, x1, z0, z1, top


# --------------------------------------------------------------------------------------------
# art

def rgb(h, a=255):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (a,)


def hsh(x, y, s=0):
    v = (x * 374761393 + y * 668265263 + s * 2246822519) & 0xFFFFFFFF
    v = ((v ^ (v >> 13)) * 1274126177) & 0xFFFFFFFF
    return (v ^ (v >> 16)) & 0xFF


def draw_art():
    ART.mkdir(exist_ok=True)
    # wall: 2 m x 2.7 m a repeat. Painted concrete over a mosaic-tile wainscot (the bottom 1.0 m,
    # 12 texels), a dark cap tile between them, a stain or two.
    im = Image.new('RGBA', (32, 32))
    px = im.load()
    paint, paint_d, paint_l = rgb('#d8d0bc'), rgb('#bfb6a2'), rgb('#e4dccb')
    tiles = [rgb('#8a6a48'), rgb('#84643f'), rgb('#92724e'), rgb('#7e5e40')]
    for y in range(32):
        for x in range(32):
            if y >= 20:                                  # mosaic, 2-texel tiles with grout
                if x % 2 == 1 and y % 2 == 1:
                    c = rgb('#74583e')
                else:
                    c = tiles[hsh(x // 2, y // 2) % 4]
            elif y == 19:
                c = rgb('#5a3e2c')                       # the cap tile
            else:
                h = hsh(x, y, 3)
                c = paint_d if h < 18 else paint_l if h > 236 else paint
                if x in (9, 10) and 8 < y < 19 and hsh(x, y, 5) < 140:
                    c = paint_d                          # a rain streak
            px[x, y] = c
    im.save(ART / 'wall.png')

    # doorway: the dark inside, a pale tiled floor, a strip light, a tiled partition corner
    im = Image.new('RGBA', (16, 32), rgb('#3a3e40'))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 27, 15, 31], fill=rgb('#8e9490'))
    for x in range(0, 16, 3):
        d.line([(x, 27), (x, 31)], fill=rgb('#6a706c'))
    d.rectangle([2, 1, 13, 1], fill=rgb('#cfd8d0'))
    d.rectangle([10, 4, 15, 26], fill=rgb('#5a6466'))
    d.line([(10, 4), (10, 26)], fill=rgb('#2c2a28'))
    d.rectangle([0, 0, 15, 0], fill=rgb('#2c2a28'))
    im.save(ART / 'doorway.png')

    # the sign over the doorways: white on dark green, crisp text
    im = Image.new('RGBA', (64, 16), rgb('#2e5a46'))
    d = ImageDraw.Draw(im)
    d.fontmode = '1'
    d.rectangle([0, 0, 63, 15], outline=rgb('#eceae4'))
    font = ImageFont.truetype(JP_FONT, 13)
    text = 'トイレ'
    w = d.textlength(text, font=font)
    d.text(((64 - w) / 2, 0), text, font=font, fill=rgb('#eceae4'))
    im.save(ART / 'sign.png')

    # pictograms on white enamel plates: blue man, red woman
    for name, col, skirt in (('pict_men', '#3a6ab0', False), ('pict_women', '#c8301e', True)):
        im = Image.new('RGBA', (16, 24), rgb('#eceae4'))
        d = ImageDraw.Draw(im)
        c = rgb(col)
        d.rectangle([0, 0, 15, 23], outline=rgb('#8e887c'))
        d.ellipse([6, 3, 9, 6], fill=c)                   # head
        if skirt:
            d.polygon([(7, 8), (8, 8), (12, 16), (3, 16)], fill=c)
            d.rectangle([5, 8, 10, 11], fill=c)
            d.rectangle([5, 17, 6, 20], fill=c)
            d.rectangle([9, 17, 10, 20], fill=c)
        else:
            d.rectangle([5, 8, 10, 14], fill=c)
            d.rectangle([3, 8, 4, 13], fill=c)
            d.rectangle([11, 8, 12, 13], fill=c)
            d.rectangle([5, 15, 6, 20], fill=c)
            d.rectangle([9, 15, 10, 20], fill=c)
        im.save(ART / f'{name}.png')

    # breeze-block vent: a row of hollow blocks, dark holes with a cross
    im = Image.new('RGBA', (32, 8), rgb('#c8c4b8'))
    d = ImageDraw.Draw(im)
    for k in range(4):
        x0 = k * 8
        d.rectangle([x0 + 1, 1, x0 + 6, 6], fill=rgb('#3a3e40'))
        d.line([(x0 + 1, 1), (x0 + 6, 6)], fill=rgb('#a8a69e'))
        d.line([(x0 + 6, 1), (x0 + 1, 6)], fill=rgb('#a8a69e'))
        d.line([(x0 + 7, 0), (x0 + 7, 7)], fill=rgb('#8e887c'))
    im.save(ART / 'vent.png')


# --------------------------------------------------------------------------------------------
# materials

def fit(name, color, **kw):
    m = {'color': color, 'texture': {'image': f'art/{name}.png', 'projection': 'fit'}}
    m.update(kw)
    return m


MATS = {
    'wall': {'color': '#d8d0bc', 'tag': 'wall',
             'texture': {'image': 'art/wall.png', 'projection': 'box', 'scale': [2, 2.7]}},
    'roof_top': {'color': '#b8b4a8', 'tag': 'roof',
                 'texture': {'sheet': 'concrete', 'cell': 'soffit', 'projection': 'planar',
                             'axis': 'y', 'scale': [4, 4]}},
    'doorway': fit('doorway', '#3a3e40', tag='door'),
    'sign': fit('sign', '#2e5a46', tag='sign'),
    'pict_men': fit('pict_men', '#eceae4'),
    'pict_women': fit('pict_women', '#eceae4'),
    'vent': fit('vent', '#8e887c'),
    'back_door': {'color': '#9aa0a4', 'tag': 'door',
                  'texture': {'sheet': 'shopfront', 'cell': 'back_door', 'projection': 'fit'}},
    'concrete': {'color': '#c8c4b8', 'palette': True},
    'fascia': {'color': '#eceae4', 'palette': True},
    'pad': {'color': '#a8a69e', 'palette': True},
    'steel': {'color': '#8e9498', 'palette': True},
    'tank': {'color': '#3a6ab0', 'palette': True},
    'lamp': {'color': '#e8f0e0', 'class': 'emissive', 'tag': 'window'},
}
SHEETS = {'concrete': {'image': '../viaduct_span_16/art/concrete.png'},
          'shopfront': {'image': '../town_shop_2f_a/art/shopfront.png'}}

WALL_TOP = 2.7       # the wall texture's top row sits here, its repeat 2 m wide and 2.7 tall


def wall_face(p, pts, x_origin):
    """A wall polygon whose texture's top is at WALL_TOP: 2 m a repeat across, one repeat high.
    The material's box projection says the same (scale [2, 2.7]): a face with decals is mapped
    by the projection rather than by these hand UVs."""
    p.face_uv('wall', pts, 2.0, WALL_TOP, origin=x_origin)


def wall_box(p, x0, x1, y0, y1, z0, z1, open=()):
    sides = {
        'back': [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)],
        'front': [(x1, y1, z1), (x0, y1, z1), (x0, y0, z1), (x1, y0, z1)],
        'right': [(x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (x1, y0, z0)],
        'left': [(x0, y1, z1), (x0, y1, z0), (x0, y0, z0), (x0, y0, z1)],
    }
    idx = {}
    for side, pts in sides.items():
        if side in open:
            continue
        idx[side] = len(p.f)
        wall_face(p, pts, (pts[0][0], WALL_TOP, pts[0][2]))
    return idx


# --------------------------------------------------------------------------------------------
# parts

def pad(p):
    hx, z0, z1, top = PAD
    p.box({'*': 'pad'}, -hx, hx, 0.0, top, z0, z1, open=('bottom',))


def block():
    p = ap.Part('block')
    hx, z0, z1, top = BLOCK
    idx = wall_box(p, -hx, hx, PAD[3] - 0.02, top, z0, z1)
    node = p.node()
    fy = PAD[3] - 0.02
    node['decals'] = [
        {'id': 'door_men', 'face': idx['back'], 'material': 'doorway', 'size': [0.9, 2.0],
         'at': [-DOOR_X, PAD[3] + 0.01 + 1.0]},
        {'id': 'door_women', 'face': idx['back'], 'material': 'doorway', 'size': [0.9, 2.0],
         'at': [DOOR_X, PAD[3] + 0.01 + 1.0]},
        {'id': 'sign', 'face': idx['back'], 'material': 'sign', 'size': [1.6, 0.4],
         'at': [0.0, 2.36]},
        {'id': 'vent_e', 'face': idx['right'], 'material': 'vent', 'size': [3.2, 0.32],
         'at': [(z0 + z1) / 2, 2.45]},
        {'id': 'vent_w', 'face': idx['left'], 'material': 'vent', 'size': [3.2, 0.32],
         'at': [-(z0 + z1) / 2, 2.45]},
        {'id': 'cleaner', 'face': idx['front'], 'material': 'back_door', 'size': [0.85, 1.9],
         'at': [1.2, PAD[3] + 0.01 + 0.95]},
        {'id': 'vent_n', 'face': idx['front'], 'material': 'vent', 'size': [2.0, 0.32],
         'at': [-1.0, 2.45]},
    ]
    return node


def slab(p):
    hx, z0, z1, y0, y1 = SLAB
    p.box({'*': 'fascia', 'top': 'roof_top', 'bottom': 'concrete'}, -hx, hx, y0, y1, z0, z1,
          su=4.0)


def screens():
    nodes = []
    a, b, z0, z1, top = SCREEN
    for s, name, pict in ((-1, 'screen_men', 'pict_men'), (1, 'screen_women', 'pict_women')):
        p = ap.Part(name)
        x0, x1 = sorted((s * a, s * b))
        idx = wall_box(p, x0, x1, PAD[3] - 0.02, top, z0, z1)
        p.face('concrete', [(x0, top, z1), (x1, top, z1), (x1, top, z0), (x0, top, z0)])
        node = p.node()
        node['decals'] = [{'id': 'pict', 'face': idx['back'], 'material': pict,
                           'size': [0.4, 0.6], 'at': [s * (a + b) / 2, 1.4]}]
        nodes.append(node)
    return nodes


def details(p):
    x0, x1, z0, z1, top = TANK                    # the water tank on the roof
    p.box({'*': 'tank', 'top': 'steel'}, x0, x1, SLAB[4] - 0.02, top, z0, z1, open=('bottom',))
    hx = BLOCK[0]                                 # the hand basin on the east wall
    p.box({'*': 'concrete', 'top': 'steel'}, hx - 0.02, hx + 0.38, 0.62, 0.86, -0.6, 0.0,
          open=('left',))
    p.box('steel', hx - 0.02, hx + 0.08, 0.98, 1.06, -0.34, -0.26, open=('left',))   # the tap
    # the canopy's lamp, hung under the slab over the sign
    p.box('lamp', -0.45, 0.45, SLAB[3] - 0.08, SLAB[3] + 0.02, -2.05, -1.95, open=('top',))


def level0():
    pd, sl, det = ap.Part('pad'), ap.Part('slab'), ap.Part('details')
    pad(pd)
    slab(sl)
    details(det)
    return [pd, block(), sl, det] + screens()


def level1():
    """From 25 m: the block with its doorways and sign, the slab, the screens as boxes, the
    tank."""
    p = ap.Part('block')
    hx, z0, z1, top = BLOCK
    idx = wall_box(p, -hx, hx, 0.0, top, z0, z1)
    node = p.node()
    node['decals'] = [
        {'id': 'door_men', 'face': idx['back'], 'material': 'doorway', 'size': [0.9, 2.0],
         'at': [-DOOR_X, 1.1]},
        {'id': 'door_women', 'face': idx['back'], 'material': 'doorway', 'size': [0.9, 2.0],
         'at': [DOOR_X, 1.1]}]
    q = ap.Part('rest')
    hx2, sz0, sz1, y0, y1 = SLAB
    q.box({'*': 'fascia', 'top': 'roof_top', 'bottom': 'concrete'}, -hx2, hx2, y0, y1, sz0, sz1,
          su=4.0)
    a, b, w0, w1, wt = SCREEN
    for s in (-1, 1):
        x0, x1 = sorted((s * a, s * b))
        wall_box(q, x0, x1, 0.0, wt, w0, w1)
        q.face('concrete', [(x0, wt, w1), (x1, wt, w1), (x1, wt, w0), (x0, wt, w0)])
    x0, x1, tz0, tz1, ttop = TANK
    q.box('tank', x0, x1, y1 - 0.02, ttop, tz0, tz1, open=('bottom',))
    return [node, q]


def level2():
    """From 60 m: the block and slab as one box, the screens as two blocks."""
    p = ap.Part('toilet')
    hx, z0, z1, top = BLOCK
    p.box({'*': 'concrete', 'top': 'roof_top'}, -SLAB[0], SLAB[0], 0.0, SLAB[4], SLAB[1],
          SLAB[2], open=('bottom',), su=4.0)
    a, b, w0, w1, wt = SCREEN
    for s in (-1, 1):
        x0, x1 = sorted((s * a, s * b))
        p.box('concrete', x0, x1, 0.0, wt, w0, w1, open=('bottom', 'front'))
    return [p]


def collision():
    p = ap.Part('body')
    hx, z0, z1, top = PAD
    ap.col_box(p, -hx, hx, 0.0, top, z0, z1, open=('bottom',))
    bx, bz0, bz1, _ = BLOCK
    sx, sz0, sz1, sy0, sy1 = SLAB
    ap.col_box(p, -bx, bx, top, sy0, bz0, bz1, open=('bottom', 'top'))
    ap.col_box(p, -sx, sx, sy0, sy1, sz0, sz1)
    a, b, w0, w1, wt = SCREEN
    for s in (-1, 1):
        x0, x1 = sorted((s * a, s * b))
        ap.col_box(p, x0, x1, top, wt, w0, w1, open=('bottom',))
    x0, x1, tz0, tz1, ttop = TANK
    ap.col_box(p, x0, x1, sy1, ttop, tz0, tz1, open=('bottom',))
    ap.col_box(p, bx, bx + 0.38, top, 0.86, -0.6, 0.0, open=('bottom', 'left'))
    return [p]


def main():
    draw_art()
    lod = {'levels': [(25, level1()), (60, level2())], 'cull': 140, 'band': 2}
    r = ap.recipe('park_toilet', MATS, level0(), 200, lod)
    r = {'format': r.pop('format'), 'version': r.pop('version'), 'name': r.pop('name'),
         'sheets': SHEETS, **r}
    ap.write(HERE / 'park_toilet.asset.json', r)
    ap.write(HERE / 'park_toilet_col.asset.json', ap.col_recipe('park_toilet_col', collision()))


if __name__ == '__main__':
    main()
