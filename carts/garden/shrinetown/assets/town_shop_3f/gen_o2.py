"""Shrine town's three-storey shop, the shotengai's arcade roof and the bounce awning.

Writes, from this folder:
  art/tea.png, art/tea.sheet.json                  the tea shop's own cells (its interior, the
                                                   painted advert on its side wall, the legs of
                                                   its rooftop sign)
  town_shop_3f.asset.json, ..._col                 Ryokkoen, a tea merchant: three storeys, a flat
                                                   roof with a stair house, a water tank and a
                                                   sign frame
  ../arcade_roof_16/art/arcade.png, .sheet.json    the arcade's trusses and hanging banners
  ../arcade_roof_16/arcade_roof_16.asset.json, ..._col
                                                   a 16 x 16 m section of the covered arcade
  ../town_awning_bounce/town_awning_bounce.asset.json, ..._col
                                                   an 8 m canvas awning whose top is a bounce

Run with Pillow: python3 gen_o2.py. It reuses the helpers and the shopfront sheet of the
two-storey shops (../town_shop_2f_a/gen_shops.py, art/shopfront.png) and draws its lettering with
the macOS Hiragino fonts; the PNGs and the recipes are committed.

Sign lettering is drawn as masks (black board, white letters, grey rim) and written into the
recipes as texel grids in three colours, as the two-storey shops do, so a sign can be recoloured
without redrawing it.
"""
import importlib.util
import json
import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location('gen_shops', os.path.join(ASSETS, 'town_shop_2f_a', 'gen_shops.py'))
gs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gs)

Mesh, box, prism_x, crossed_quads = gs.Mesh, gs.box, gs.prism_x, gs.crossed_quads
slab_box, ledge, strip_top, bands, write, r4 = gs.slab_box, gs.ledge, gs.strip_top, gs.bands, gs.write, gs.r4
VERIFY, LIGHT, W, D = gs.VERIFY, gs.LIGHT, gs.W, gs.D
SHOPFRONT = '../town_shop_2f_a/art/shopfront.png'
MASK, FG, RIM = gs.MASK, gs.FG, gs.RIM


def cell(sheet, name, **kw):
    t = {'sheet': sheet, 'cell': name, 'projection': 'fit'}
    t.update(kw)
    return t


def new(cells, name, w, h, fill=(0, 0, 0, 0)):
    img = Image.new('RGBA', (w, h), fill)
    cells[name] = img
    d = ImageDraw.Draw(img)
    d.fontmode = '1'
    return img, d


def mask_texels(img, colours, clear=None):
    """A mask (black board, white letters, grey rim; transparent = a hole) as a texel grid.
    With `clear`, transparent texels become a fourth colour that is a hole."""
    keys = {MASK[:3]: '0', FG[:3]: '1', RIM[:3]: '2'}
    rows = []
    for y in range(img.height):
        row = ''
        for x in range(img.width):
            p = img.getpixel((x, y))
            row += '3' if p[3] < 128 else keys[p[:3]]
        rows.append(row)
    cols = list(colours)
    t = {'texels': rows, 'colors': cols, 'projection': 'fit'}
    if clear:
        cols.append(clear)
        t['clear'] = clear
    return t


def pack(cells, path):
    """Shelf-pack the cells into one PNG 128 wide (or wider when a cell is), with its sheet.json."""
    width = max(128, max(im.width for im in cells.values()))
    order = sorted(cells, key=lambda n: (-cells[n].height, n))
    x = y = shelf = 0
    rects = {}
    for n in order:
        im = cells[n]
        if x + im.width > width:
            x, y, shelf = 0, y + shelf, 0
        rects[n] = [x, y, im.width, im.height]
        x += im.width
        shelf = max(shelf, im.height)
    h = (y + shelf + 7) // 8 * 8
    sheet = Image.new('RGBA', (width, h), (0, 0, 0, 0))
    for n, (x, y, w, hh) in rects.items():
        sheet.paste(cells[n], (x, y))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.save(path)
    with open(path[:-4] + '.sheet.json', 'w') as f:
        json.dump({'format': 'mei-sheet', 'version': 1, 'cells': {n: rects[n] for n in sorted(rects)}}, f, indent=1)
        f.write('\n')


def col_recipe(name, nodes, materials=None, budget=300):
    mats = {'solid': {'color': '#ffffff', 'palette': True}}
    mats.update(materials or {})
    return {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': {'triangles': budget},
            'materials': mats, 'lighting': LIGHT, 'verification': VERIFY, 'nodes': nodes}


def recipe(name, budget, sheets, materials, nodes, levels=None, cull=None):
    r = {'format': 'mei-asset', 'version': 1, 'name': name, 'sheets': sheets,
         'budget': {'triangles': budget}, 'materials': materials, 'lighting': LIGHT,
         'verification': VERIFY, 'nodes': nodes}
    if levels:
        r['lod'] = {'levels': levels}
        if cull:
            r['lod']['cull'] = cull
    return r


def beam(m, p0, p1, w, mat):
    """A square tube of side w from p0 to p1 (its four long sides, ends open)."""
    d = [p1[i] - p0[i] for i in range(3)]
    L = math.sqrt(sum(c * c for c in d))
    d = [c / L for c in d]
    up = (0, 1, 0) if abs(d[1]) < 0.9 else (1, 0, 0)
    a = [d[1] * up[2] - d[2] * up[1], d[2] * up[0] - d[0] * up[2], d[0] * up[1] - d[1] * up[0]]
    la = math.sqrt(sum(c * c for c in a))
    a = [c / la * w / 2 for c in a]
    b = [d[1] * a[2] - d[2] * a[1], d[2] * a[0] - d[0] * a[2], d[0] * a[1] - d[1] * a[0]]
    corners = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
    for i in range(4):
        s0, t0 = corners[i]
        s1, t1 = corners[(i + 1) % 4]
        q = []
        for p in (p0, p1):
            for s, t in ((s0, t0), (s1, t1)):
                q.append(tuple(p[k] + s * a[k] + t * b[k] for k in range(3)))
        out = [(s0 + s1) / 2 * a[k] + (t0 + t1) / 2 * b[k] for k in range(3)]
        m.quad(q[0], q[1], q[3], q[2], out, mat)


# ============================================================================================
# The tea shop's cells
# ============================================================================================

TEA = {}
GOTHIC, GOTHIC_M = gs.GOTHIC, gs.GOTHIC_M
MINCHO = '/System/Library/Fonts/ヒラギノ明朝 ProN.ttc'


def draw_tea():
    # glass_t: the tea merchant's front. Tea tins on shelves, big ceramic jars, a counter with
    # its scale, a hanging scroll; behind the aluminium sash of the street's other shops.
    img, d = new(TEA, 'glass_t', 64, 32)

    def inside(d):
        gs.rect(d, 0, 0, 63, 31, fill='#e6dcb8')
        gs.rect(d, 0, 3, 63, 4, fill='#b89a6a')
        for y in (5, 11):                                    # two shelves of tins
            gs.rect(d, 0, y + 5, 63, y + 5, fill='#5a3e2c')
            for i, x in enumerate(range(1, 62, 4)):
                c = ['#2e5a2e', '#2c2a28', '#d8b048', '#2e5a2e', '#a8321e', '#6a8a3a'][(i * 5 + y) % 6]
                gs.rect(d, x, y + 1, x + 2, y + 4, fill=c)
                d.point((x + 1, y + 2), fill='#f4f0e0' if c != '#d8b048' else '#8a6446')
        gs.rect(d, 27, 4, 36, 15, fill='#f4f0e0')            # a hanging scroll: 茶
        gs.rect(d, 27, 4, 36, 4, fill='#6a4632')
        gs.rect(d, 30, 7, 33, 7, fill='#2e5a2e'); gs.rect(d, 31, 8, 32, 12, fill='#2e5a2e')
        gs.rect(d, 29, 10, 34, 10, fill='#2e5a2e')
        for x, c in ((3, '#8a5a3a'), (12, '#6a4a30'), (51, '#8a5a3a')):   # ceramic jars
            d.ellipse([x, 18, x + 8, 28], fill=c)
            gs.rect(d, x + 2, 17, x + 6, 18, fill='#2c2a28')
            d.point((x + 2, 21), fill='#c8a070')
        gs.rect(d, 22, 20, 46, 27, fill='#6a4632')           # the counter
        gs.rect(d, 22, 20, 46, 20, fill='#8a6446')
        gs.rect(d, 38, 17, 43, 19, fill='#c4c8cc')           # its scale
        gs.rect(d, 40, 16, 41, 16, fill='#2c2a28')
        gs.rect(d, 25, 18, 33, 19, fill='#e8e2d4')           # paper bags
        d.point((27, 18), fill='#2e5a2e'); d.point((31, 18), fill='#2e5a2e')
    gs.shopfront_frame(d, 64, 32, 4, inside)

    # ad: a painted advert on the side wall above the neighbours' roofs, faded rust and cream.
    img, d = new(TEA, 'ad', 64, 32)
    gs.rect(d, 0, 0, 63, 31, fill='#9a5a44')
    gs.rect(d, 1, 1, 62, 30, outline='#c8a088')
    for i, ch in enumerate('宇治銘茶'):
        gs.text(d, (9 + i * 15, 11), ch, 13, '#efe2c8', MINCHO)
    for i, ch in enumerate('緑香園'):
        gs.text(d, (18 + i * 14, 24), ch, 11, '#efe2c8', GOTHIC_M)
    for k in range(70):                                      # weathering
        x, y = (k * 37) % 62 + 1, (k * 23 + k // 5) % 30 + 1
        d.point((x, y), fill='#b07a62' if k % 3 else '#8a4e3a')
    for x in range(2, 62, 9):                                # streaks of rain
        gs.rect(d, x, 27, x, 30, fill='#86503c')

    # legs: the rooftop sign's steel frame (a cutout): posts, rails and cross braces.
    img, d = new(TEA, 'legs', 32, 8)
    steel = '#5e6468'
    for x in (0, 10, 21, 31):
        gs.rect(d, x, 0, x, 7, fill=steel)
    gs.rect(d, 0, 0, 31, 0, fill=steel)
    gs.rect(d, 0, 7, 31, 7, fill=steel)
    for x0, x1 in ((0, 10), (10, 21), (21, 31)):
        d.line([(x0, 0), (x1, 7)], fill=steel)
        d.line([(x0, 7), (x1, 0)], fill=steel)


def tea_masks():
    m = {}
    img, d = new(m, 'kanban', 128, 16, MASK)
    gs.rect(d, 0, 0, 127, 15, outline=RIM)
    d.ellipse([4, 1, 17, 14], fill=RIM)
    gs.text(d, (11, 8), '茶', 11, FG, GOTHIC)
    gs.text(d, (33, 8), 'お茶', 10, FG, GOTHIC_M)
    gs.rect(d, 46, 3, 46, 12, fill=RIM)
    for i, ch in enumerate('緑香園'):
        gs.text(d, (66 + i * 20, 8), ch, 14, FG, MINCHO)
    img, d = new(m, 'tate', 16, 48, MASK)
    gs.rect(d, 0, 0, 15, 47, outline=RIM)
    gs.vtext(d, 8, 8, 'お茶', 12, 13, FG)
    gs.rect(d, 3, 22, 12, 22, fill=RIM)
    gs.vtext(d, 8, 29, 'ほうじ', 9, 7, FG, GOTHIC_M)
    # the rooftop sign: one side to each end of the street
    img, d = new(m, 'roof_a', 96, 32, MASK)
    gs.rect(d, 0, 0, 95, 31, outline=RIM)
    gs.rect(d, 2, 2, 93, 29, outline=RIM)
    gs.text(d, (48, 9), 'お茶と海苔', 10, FG, GOTHIC_M)
    for i, ch in enumerate('緑香園'):
        gs.text(d, (22 + i * 26, 21), ch, 16, FG, GOTHIC_M)
    img, d = new(m, 'roof_b', 96, 32, MASK)
    gs.rect(d, 0, 0, 95, 31, outline=RIM)
    gs.rect(d, 2, 2, 93, 29, outline=RIM)
    d.ellipse([5, 5, 26, 26], fill=RIM)
    gs.text(d, (16, 16), '茶', 16, FG, GOTHIC)
    for i, ch in enumerate('宇治銘茶'):
        gs.text(d, (40 + i * 16, 16), ch, 15, FG, GOTHIC_M)
    # noren: the doorway's curtain, three panels with slits (transparent) between them
    img, d = new(m, 'noren', 32, 16, MASK)
    gs.text(d, (16, 9), '茶', 11, FG, GOTHIC)
    for x in (10, 21):
        gs.rect(d, x, 4, x, 15, fill=(0, 0, 0, 0))
    return m


# ============================================================================================
# The street's other three-storey shops (alpha review r15 #1: twelve shops, seven names; Ryokkoen
# four times): the same building with another trade's front, lettering and colours, and no
# rooftop sign. Their glass fronts are cells of their own sheet, art/more.png.
# ============================================================================================

MORE = {}


def draw_more():
    # glass_k: a kimono shop. A kimono on its stand, bolts of cloth on shelves, a tatami step.
    img, d = new(MORE, 'glass_k', 64, 32)

    def kimono(d):
        gs.rect(d, 0, 0, 63, 31, fill='#e8dcc0')
        gs.rect(d, 0, 24, 63, 31, fill='#b8a878')                # the tatami step
        gs.rect(d, 0, 24, 63, 24, fill='#8a7a4a')
        for i, x in enumerate(range(1, 20, 3)):                  # bolts of cloth, two shelves
            for y, k in ((4, i), (13, i + 3)):
                c = ['#7a2a4a', '#2a4a7a', '#c8a040', '#4a6a3a', '#a8321e', '#5a3a6a', '#d8b8c8'][k % 7]
                gs.rect(d, x, y, x + 1, y + 7, fill=c)
        gs.rect(d, 0, 12, 21, 12, fill='#6a4632')
        gs.rect(d, 0, 21, 21, 21, fill='#6a4632')
        gs.rect(d, 28, 3, 44, 3, fill='#2c2a28')                 # the stand's bar
        d.polygon([(30, 4), (42, 4), (44, 23), (28, 23)], fill='#5a2a6a')     # the kimono
        d.polygon([(34, 4), (36, 12), (38, 4)], fill='#f4f0e0')               # its collar
        gs.rect(d, 29, 13, 43, 15, fill='#d8b048')                            # the obi
        for x, y in ((31, 18), (39, 8), (35, 20), (41, 17)):
            d.point((x, y), fill='#f0a8c0')
            d.point((x + 1, y), fill='#f0a8c0')
        for i, x in enumerate(range(49, 62, 4)):                 # folded obi on the counter
            gs.rect(d, x, 18, x + 2, 23, fill=['#d8b048', '#a8321e', '#2a4a7a', '#4a6a3a'][i])
    gs.shopfront_frame(d, 64, 32, 4, kimono)

    # glass_h: a bookshop. Shelves of spines, a magazine rack in front, the till.
    img, d = new(MORE, 'glass_h', 64, 32)

    def books(d):
        gs.rect(d, 0, 0, 63, 31, fill='#e6e0cc')
        for y in (2, 10):                                        # two shelves of spines
            for i, x in enumerate(range(0, 64, 2)):
                c = ['#a8321e', '#2a4a7a', '#e8dcc0', '#3a5a3a', '#c8a040', '#5a3a2c', '#24345a'][(i * 3 + y) % 7]
                h = 6 + (i * 5 + y) % 2
                gs.rect(d, x, y + 7 - h, x, y + 7, fill=c)
            gs.rect(d, 0, y + 8, 63, y + 8, fill='#6a4632')
        covers = ['#f04880', '#f4d23c', '#3cb4e6', '#f4f2e8', '#e85a2a', '#64c864', '#c84a3a']
        for i, x in enumerate(range(2, 40, 6)):                  # the magazine rack, covers out
            gs.rect(d, x, 20, x + 4, 27, fill=covers[i % 7])
            gs.rect(d, x + 1, 21, x + 3, 22, fill='#2c2a28')
        gs.rect(d, 0, 28, 41, 29, fill='#8a6446')
        gs.rect(d, 46, 21, 61, 29, fill='#6a4632')               # the till's counter
        gs.rect(d, 50, 18, 55, 20, fill='#c4c8cc')
    gs.shopfront_frame(d, 64, 32, 4, books)


def kimono_masks():
    m = {}
    img, d = new(m, 'kanban', 128, 16, MASK)
    gs.rect(d, 0, 0, 127, 15, outline=RIM)
    d.ellipse([4, 1, 17, 14], fill=RIM)
    gs.text(d, (11, 8), '呉', 11, FG, GOTHIC)
    gs.text(d, (35, 8), 'ごふく', 9, FG, GOTHIC_M)
    gs.rect(d, 50, 3, 50, 12, fill=RIM)
    for i, ch in enumerate('きくや'):
        gs.text(d, (70 + i * 20, 8), ch, 14, FG, MINCHO)
    img, d = new(m, 'tate', 16, 48, MASK)
    gs.rect(d, 0, 0, 15, 47, outline=RIM)
    gs.vtext(d, 8, 8, '呉服', 12, 13, FG, MINCHO)
    gs.rect(d, 3, 22, 12, 22, fill=RIM)
    gs.vtext(d, 8, 29, 'きもの', 9, 7, FG, GOTHIC_M)
    img, d = new(m, 'noren', 32, 16, MASK)
    gs.text(d, (16, 9), '菊', 11, FG, MINCHO)
    for x in (10, 21):
        gs.rect(d, x, 4, x, 15, fill=(0, 0, 0, 0))
    return m


def book_masks():
    m = {}
    img, d = new(m, 'kanban', 128, 16, MASK)
    gs.rect(d, 0, 0, 127, 15, outline=RIM)
    gs.rect(d, 2, 2, 125, 13, outline=RIM)
    gs.text(d, (18, 8), '本', 11, FG, GOTHIC)
    for i, ch in enumerate('文栄堂書店'):
        gs.text(d, (42 + i * 17, 8), ch, 13, FG, MINCHO)
    img, d = new(m, 'tate', 16, 48, MASK)
    gs.rect(d, 0, 0, 15, 47, outline=RIM)
    gs.vtext(d, 8, 8, '書籍', 12, 13, FG)
    gs.rect(d, 3, 22, 12, 22, fill=RIM)
    gs.vtext(d, 8, 29, '雑誌', 9, 10, FG, GOTHIC_M)
    img, d = new(m, 'noren', 32, 16, MASK)
    gs.text(d, (16, 9), '本', 11, FG, GOTHIC)
    for x in (10, 21):
        gs.rect(d, x, 4, x, 15, fill=(0, 0, 0, 0))
    return m


VARIANTS_3F = {
    'town_shop_3f_kimono': dict(masks=kimono_masks, glass='glass_k', glass_col='#e8dcc0',
                                kanban=['#4a2a5a', '#f4f0e0', '#d8b048'], tate=['#f4f0e0', '#4a2a5a', '#4a2a5a'],
                                noren=['#4a2a5a', '#f4f0e0', '#4a2a5a'], awn=['#4a2a5a', '#e8e2c8'],
                                tile=('#7e7e86', '#9a9aa2', '#64646c')),
    'town_shop_3f_books': dict(masks=book_masks, glass='glass_h', glass_col='#e6e0cc',
                               kanban=['#7a1e1e', '#f4f0e0', '#d8b048'], tate=['#f4f0e0', '#7a1e1e', '#7a1e1e'],
                               noren=['#7a1e1e', '#f4f0e0', '#7a1e1e'], awn=['#7a1e1e', '#e8e2c8'],
                               tile=('#b89a6a', '#ccb48a', '#9a7e52')),
}


# ============================================================================================
# town_shop_3f: Ryokkoen, a tea merchant in a 1970s three-storey building faced in brown
# scratch tiles, the street's tallest shops (9.5 m to the parapet). Origin at the centre of its
# 9 x 14 m footprint at street level, front toward -Z, like the two-storey shops.
# ============================================================================================

H, DECK, PT = 9.5, 9.3, 0.25          # parapet top, roof deck, parapet thickness
OPX, OPY, ZR = 3.9, 2.6, -6.5         # the glass front's opening half width, height; its recess
SIGN_X, SIGN_Z0, SIGN_Z1, SIGN_Y0, SIGN_Y1 = 2.6, -6.4, -0.8, 10.4, 12.3   # rooftop sign board
PH_X, PH_Z, PH_W, PH_H = -2.6, 4.2, 2.6, 2.4                                # the stair house
TANK = (1.6, 1.1, 1.2)


def shop_3f(name='town_shop_3f'):
    """Ryokkoen; or, with the name of one of VARIANTS_3F, that trade's front without the rooftop
    sign and the side wall's advert."""
    v = VARIANTS_3F.get(name)
    masks = v['masks']() if v else tea_masks()
    kanban = v['kanban'] if v else ['#2e5a2e', '#f4f0e0', '#d8b048']
    tate = v['tate'] if v else ['#f4f0e0', '#2e5a2e', '#2e5a2e']
    roof_sign = ['#f4f0e0', '#2e5a2e', '#c8301e']
    noren = v['noren'] if v else ['#24345a', '#f4f0e0', '#24345a']
    awn = v['awn'] if v else ['#2e5a2e', '#e8e2c8']
    tiles = v['tile'] if v else ('#9a6a52', '#b49a84', '#865a44')
    tile, mortar = tiles[0], '#c8c4b8'
    sheets = {'shopfront': {'image': SHOPFRONT}, 'tea': {'image': 'art/tea.png'}}
    if v:
        sheets = {'shopfront': {'image': SHOPFRONT}, 'more': {'image': 'art/more.png'}}
    mats = {
        'tile': {'color': tile, 'tag': 'wall', 'texture': {
            'pattern': 'brick', 'size': 16, 'colors': list(tiles),
            'params': {'courses': 8, 'bricks': 4, 'bond': 0.5, 'mortar': 1, 'seed': 3},
            'projection': 'box', 'scale': [1, 0.5]}},
        'mortar': {'color': mortar, 'tag': 'wall', 'texture': {
            'pattern': 'speckle', 'size': 16, 'colors': [mortar, '#b8b4a8', '#d4d0c4'],
            'params': {'density': 0.25, 'seed': 9}, 'projection': 'box', 'scale': [1, 1]}},
        'deck': {'color': '#7a8070', 'tag': 'roof', 'texture': {
            'pattern': 'speckle', 'size': 16, 'colors': ['#7a8070', '#6a7062', '#8a907e'],
            'params': {'density': 0.3, 'seed': 4}, 'projection': 'box', 'scale': [2, 2]}},
        'parapet': {'color': '#d4d0c4', 'palette': True, 'tag': 'wall'},
        'reveal': {'color': '#a8acb0', 'palette': True},
        'board': {'color': '#3a3a3e', 'palette': True},
        'steel': {'color': '#5e6468', 'palette': True},
        'pipe': {'color': '#8e887c', 'palette': True},
        'ac_body': {'color': '#e2e0d6', 'palette': True},
        'tank': {'color': '#d8dcd4', 'texture': {
            'pattern': 'tile', 'size': 16, 'colors': ['#d8dcd4', '#a8aca4'], 'params': {'count': 1, 'grout': 1},
            'projection': 'box', 'scale': [1, 1]}},
        'awning': {'color': awn[0], 'tag': 'awning', 'texture': {
            'pattern': 'stripes', 'size': 16, 'colors': awn, 'params': {'count': 4, 'axis': 'u'},
            'projection': 'box', 'scale': [1, 1]}},
        'glass': {'color': v['glass_col'] if v else '#e6dcb8', 'class': 'emissive', 'tag': 'shopfront',
                  'texture': cell('more', v['glass']) if v else cell('tea', 'glass_t')},
        'window2': {'color': '#4e6a7a', 'texture': cell('shopfront', 'win_a')},
        'window3': {'color': '#4e6a7a', 'texture': cell('shopfront', 'win_c')},
        'ad': {'color': '#9a5a44', 'texture': cell('tea', 'ad')},
        'legs': {'color': '#5e6468', 'double_sided': True, 'texture': cell('tea', 'legs')},
        'kanban': {'color': kanban[0], 'class': 'emissive', 'tag': 'sign', 'texture': mask_texels(masks['kanban'], kanban)},
        'tate': {'color': tate[0], 'class': 'emissive', 'tag': 'sign', 'texture': mask_texels(masks['tate'], tate)},
        'roof_a': {'color': roof_sign[0], 'class': 'emissive', 'tag': 'sign',
                   'texture': None if v else mask_texels(masks['roof_a'], roof_sign)},
        # both faces of the rooftop sign show roof_a (one image, the town's texture budget: TEXTURES.md)
        'roof_b': {'color': roof_sign[0], 'class': 'emissive', 'tag': 'sign',
                   'texture': None if v else mask_texels(masks['roof_a'], roof_sign)},
        'noren': {'color': noren[0], 'texture': mask_texels(masks['noren'], noren, clear='#000000')},
        'ac': {'color': '#e2e0d6', 'texture': cell('shopfront', 'ac')},
        'antenna': {'color': '#7a7e84', 'double_sided': True, 'texture': cell('shopfront', 'antenna')},
        'back_door': {'color': '#8e949a', 'texture': cell('shopfront', 'back_door')},
        'back_win': {'color': '#c8d4d8', 'texture': cell('shopfront', 'back_win')},
    }
    if v:                               # no rooftop sign, no advert
        for k in ('ad', 'legs', 'roof_a', 'roof_b'):
            del mats[k]
    WIN2, WIN3 = 4.85, 8.05             # window centres on the second and third floors

    def shell(level):
        m = Mesh('shell')
        if level == 0:
            front = m.face([(-W, H, -D), (W, H, -D), (W, 0, -D), (OPX, 0, -D), (OPX, OPY, -D),
                            (-OPX, OPY, -D), (-OPX, 0, -D), (-W, 0, -D)], (0, 0, -1), 'tile')
            m.decal(front, 'window2', 'window2', (5.6, 1.1), (0, WIN2, -D), (0, 0, -1))
            m.decal(front, 'window3', 'window3', (5.6, 1.1), (0, WIN3, -D), (0, 0, -1))
            m.quad((-OPX, OPY, -D), (OPX, OPY, -D), (OPX, OPY, ZR), (-OPX, OPY, ZR), (0, -1, 0), 'reveal')
            m.quad((-OPX, 0, -D), (-OPX, OPY, -D), (-OPX, OPY, ZR), (-OPX, 0, ZR), (1, 0, 0), 'reveal')
            m.quad((OPX, 0, -D), (OPX, OPY, -D), (OPX, OPY, ZR), (OPX, 0, ZR), (-1, 0, 0), 'reveal')
            m.quad((-OPX, OPY, ZR), (OPX, OPY, ZR), (OPX, 0, ZR), (-OPX, 0, ZR), (0, 0, -1), 'glass')
            back = m.quad((-W, H, D), (W, H, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'mortar')
            for id, mat, (x, y), size in (('door', 'back_door', (2.6, 1.02), (0.9, 2.0)),
                                          ('win1', 'back_win', (-1.6, 4.6), (1.4, 0.9)),
                                          ('win2', 'back_win', (-1.6, 7.8), (1.4, 0.9))):
                m.decal(back, id, mat, size, (x, y, D), (0, 0, 1))
            side = m.quad((W, 0, -D), (W, H, -D), (W, H, D), (W, 0, D), (1, 0, 0), 'mortar')
            if not v:
                m.decal(side, 'ad', 'ad', (5.2, 2.6), (W, 8.0, -3.4), (1, 0, 0))
            # the deck and the parapet's inner faces and rim
            i_x, i_z = W - PT, D - PT
            m.quad((-i_x, DECK, -i_z), (i_x, DECK, -i_z), (i_x, DECK, i_z), (-i_x, DECK, i_z), (0, 1, 0), 'deck')
            m.quad((-i_x, H, -i_z), (i_x, H, -i_z), (i_x, DECK, -i_z), (-i_x, DECK, -i_z), (0, 0, 1), 'parapet')
            m.quad((-i_x, H, i_z), (i_x, H, i_z), (i_x, DECK, i_z), (-i_x, DECK, i_z), (0, 0, -1), 'parapet')
            for s in (-1, 1):
                m.quad((s * i_x, H, -i_z), (s * i_x, H, i_z), (s * i_x, DECK, i_z), (s * i_x, DECK, -i_z), (-s, 0, 0), 'parapet')
            m.quad((-W, H, -D), (W, H, -D), (i_x, H, -i_z), (-i_x, H, -i_z), (0, 1, 0), 'parapet')
            m.quad((-W, H, D), (W, H, D), (i_x, H, i_z), (-i_x, H, i_z), (0, 1, 0), 'parapet')
            for s in (-1, 1):
                m.quad((s * W, H, -D), (s * W, H, D), (s * i_x, H, i_z), (s * i_x, H, -i_z), (0, 1, 0), 'parapet')
        elif level == 1:
            front = m.quad((-W, H, -D), (W, H, -D), (W, 0, -D), (-W, 0, -D), (0, 0, -1), 'tile')
            m.decal(front, 'glass', 'glass', (2 * OPX, OPY - 0.02), (0, OPY / 2, -D), (0, 0, -1))
            m.decal(front, 'window2', 'window2', (5.6, 1.1), (0, WIN2, -D), (0, 0, -1))
            m.decal(front, 'window3', 'window3', (5.6, 1.1), (0, WIN3, -D), (0, 0, -1))
            m.quad((-W, H, D), (W, H, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'mortar')
            m.quad((W, 0, -D), (W, H, -D), (W, H, D), (W, 0, D), (1, 0, 0), 'mortar')
            m.quad((-W, H, -D), (W, H, -D), (W, H, D), (-W, H, D), (0, 1, 0), 'deck')
        else:
            bands(m, 'front', -W, W, -D, [0, 3.05, 3.95, H], ['glass', 'kanban', 'tile'])
            m.quad((-W, H, D), (W, H, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'mortar')
            m.quad((W, 0, -D), (W, H, -D), (W, H, D), (W, 0, D), (1, 0, 0), 'mortar')
            m.quad((-W, H, -D), (W, H, -D), (W, H, D), (-W, H, D), (0, 1, 0), 'deck')
        m.quad((-W, 0, -D), (-W, H, -D), (-W, H, D), (-W, 0, D), (-1, 0, 0), 'mortar')
        return m.node()

    prof = gs.awning_profile(3.0, -8.2, 2.62, 0.25, 2.78)

    def awning(level):
        m = Mesh('awning')
        if level == 2:
            return None
        prism_x(m, -4.45, 4.45, prof, {0: 'awning', 1: 'awning', 2: 'awning', 3: None, 'end': 'awning'},
                ends=(level == 0))
        return m.node()

    def sign(level):
        """The rooftop sign: a board standing across the roof (its faces to the two ends of the
        street) on a steel frame."""
        if v:
            return []
        sx, sz = 0.3, SIGN_Z1 - SIGN_Z0
        board = box('sign', (sx, SIGN_Y1 - SIGN_Y0, sz), (SIGN_X, (SIGN_Y0 + SIGN_Y1) / 2, (SIGN_Z0 + SIGN_Z1) / 2),
                    'steel', open=(['bottom', 'top', 'back', 'front'] if level else None),
                    faces={'left': 'roof_a', 'right': 'roof_b'})
        if level == 2:
            return [board]
        legs = Mesh('sign_legs')
        y0, y1 = DECK - 0.02, SIGN_Y0 + 0.02
        legs.quad((SIGN_X, y1, SIGN_Z1), (SIGN_X, y1, SIGN_Z0), (SIGN_X, y0, SIGN_Z0), (SIGN_X, y0, SIGN_Z1),
                  (-1, 0, 0), 'legs')
        return [board, legs.node()]

    def stair_house(level):
        ph = box('stair_house', (PH_W, PH_H, PH_W), (PH_X, DECK - 0.01 + PH_H / 2, PH_Z), 'mortar',
                 open=['bottom'] + (['front'] if level else []),
                 decals=(None if level else [{'id': 'door', 'face': 'back', 'material': 'back_door',
                                              'size': [0.85, 1.95], 'at': [0.5, -0.2]}]))
        return ph

    tank_y = DECK - 0.01 + PH_H - 0.01 + TANK[1] / 2
    tank = box('tank', TANK, (PH_X, tank_y, PH_Z), 'tank', open=['bottom'])
    kanban_box = box('kanban', (8.4, 0.85, 0.3), (0, 3.5, -7.13), 'board', open=['front'], faces={'back': 'kanban'})
    tate_box = box('tate', (0.16, 2.4, 0.62), (4.25, 4.6, -7.29), 'board', open=['front'],
                   faces={'left': 'tate', 'right': 'tate'})
    nor = Mesh('noren')
    nor.quad((-1.9, 2.58, -6.62), (-0.3, 2.58, -6.62), (-0.3, 1.86, -6.62), (-1.9, 1.86, -6.62), (0, 0, -1), 'noren')
    ac = box('ac', (0.9, 0.65, 0.35), (2.2, DECK + 0.315, 5.6), 'ac_body', open=['bottom'], faces={'back': 'ac'})
    pipe = box('downpipe', (0.1, H - 0.1, 0.1), (-4.38, (H - 0.1) / 2, 7.03), 'pipe', open=['top', 'bottom'])
    antenna = crossed_quads('antenna', (-0.4, DECK - 0.05, 3.2), 1.4, 1.8, 'antenna')

    nodes0 = [shell(0), awning(0), kanban_box, tate_box, nor.node(), stair_house(0), tank] + sign(0) + [ac, pipe, antenna]
    nodes1 = [shell(1), awning(1),
              box('kanban', (8.4, 0.85, 0.3), (0, 3.5, -7.13), 'board', open=['front', 'top'], faces={'back': 'kanban'}),
              stair_house(1)] + sign(1)
    nodes2 = [shell(2)] + sign(2)
    sheets_used = sheets
    r = recipe(name, 300, sheets_used, mats, nodes0,
               [{'distance': 20, 'nodes': nodes1}, {'distance': 50, 'nodes': nodes2}])
    write(os.path.join(HERE, name + '.asset.json'), r)

    # Collision: the walls, the deck, the parapet (a wall inside, its rim in short pieces), the
    # awning, the kanban's ledge, the stair house with its tank (a step up to 12.8), the
    # rooftop sign as a solid fin (its top 12.3 a ledge), the air conditioner.
    body = Mesh('body')
    gs.recess_col(body, -OPX, OPX, OPY, ZR, H)          # the glass front recessed, as drawn
    body.quad((-W, H, D), (W, H, D), (W, 0, D), (-W, 0, D), (0, 0, 1), 'solid')
    for s in (-1, 1):
        body.quad((s * W, 0, -D), (s * W, H, -D), (s * W, H, D), (s * W, 0, D), (s, 0, 0), 'solid')
    i_x, i_z = W - PT, D - PT
    body.quad((-i_x, DECK, -i_z), (i_x, DECK, -i_z), (i_x, DECK, i_z), (-i_x, DECK, i_z), (0, 1, 0), 'solid')
    body.quad((-i_x, H, -i_z), (i_x, H, -i_z), (i_x, DECK, -i_z), (-i_x, DECK, -i_z), (0, 0, 1), 'solid')
    body.quad((-i_x, H, i_z), (i_x, H, i_z), (i_x, DECK, i_z), (-i_x, DECK, i_z), (0, 0, -1), 'solid')
    for s in (-1, 1):
        body.quad((s * i_x, H, -i_z), (s * i_x, H, i_z), (s * i_x, DECK, i_z), (s * i_x, DECK, -i_z), (-s, 0, 0), 'solid')
    rims = [strip_top('rim_front', -W, W, -D, -i_z, H, 4, 'x'), strip_top('rim_back', -W, W, i_z, D, H, 4, 'x'),
            strip_top('rim_west', -W, -i_x, -i_z, i_z, H, 6, 'z'), strip_top('rim_east', i_x, W, -i_z, i_z, H, 6, 'z')]
    awc = Mesh('awning')
    prism_x(awc, -4.45, 4.45, gs.awning_profile(3.0, -8.2, 2.62, 0.25, 2.78, wall_z=-7.0),
            {0: 'solid', 1: 'solid', 2: 'solid', 3: None, 'end': 'solid'})
    ph0, ph1 = DECK, DECK + PH_H - 0.02
    nodes = [body.node()] + rims + [
        awc.node(),
        ledge('kanban', -4.2, 4.2, 3.075, 3.925, -7.28, -7.0, 3, 'x', open=('back',)),
        slab_box('stair_house', PH_X - PH_W / 2, PH_X + PH_W / 2, ph0, ph1, PH_Z - PH_W / 2, PH_Z + PH_W / 2, open=('bottom',)),
        slab_box('tank', PH_X - TANK[0] / 2, PH_X + TANK[0] / 2, ph1, ph1 + TANK[1], PH_Z - TANK[2] / 2, PH_Z + TANK[2] / 2,
                 open=('bottom',)),
        slab_box('ac', 1.75, 2.65, DECK, DECK + 0.63, 5.425, 5.775, open=('bottom',))]
    if not v:
        nodes.insert(-1, ledge('sign', SIGN_X - 0.15, SIGN_X + 0.15, DECK, SIGN_Y1, SIGN_Z0, SIGN_Z1, 4, 'z',
                               open=('bottom',)))
    write(os.path.join(HERE, name + '_col.asset.json'), col_recipe(name + '_col', nodes))


# ============================================================================================
# arcade_roof_16: a 16 x 16 m section of the shotengai's covered arcade. A gable of corrugated
# panels (eaves 7.0 at x = +-8, ridge 8.5 on the axis, 10.6 degrees: walkable), 0.3 thick, on
# steel trusses every 4 m (z = -6, -2, 2, 6) carried by two longitudinal girders at x = +-4.2
# and columns at the street's edges every 8 m (z = +-4), so sections placed end to end keep
# the rhythm. Fluorescent fixtures under the trusses, autumn sale banners on two of them.
# Origin on the street's axis at street level, the middle of the section; the street runs
# along z. The roof overhangs the shops' fronts by 2 m each side, as the grey box does.
# ============================================================================================

AR_E, AR_R, AR_T = 7.0, 8.5, 0.3       # eave top, ridge top, slab thickness
AR_X, AR_Z = 8.0, 8.0                  # half width (eaves), half length
GX, CZ = 4.2, 4.0                      # girder and column lines (x), column positions (z)
TRUSS_Z = (-6.0, -2.0, 2.0, 6.0)
TRUSS_DEPTH = 0.5
ARC = {}


def ar_top(x):
    return AR_R - (AR_R - AR_E) * abs(x) / AR_X


def ar_under(x):
    return ar_top(x) - AR_T


def draw_arcade():
    # truss: a Warren truss, eave end at the left, ridge end at the right (a cutout)
    img, d = new(ARC, 'truss', 64, 8)
    steel = '#5e6e72'
    gs.rect(d, 0, 0, 63, 1, fill=steel)          # top chord
    gs.rect(d, 0, 7, 63, 7, fill=steel)          # bottom chord
    gs.rect(d, 0, 0, 1, 7, fill=steel)           # end posts
    gs.rect(d, 62, 0, 63, 7, fill=steel)
    for k in range(8):                           # diagonals
        x0 = k * 8
        d.line([(x0, 7), (x0 + 4, 1)], fill=steel)
        d.line([(x0 + 4, 1), (x0 + 8, 7)], fill=steel)
    # banner: an autumn sale banner, white cloth with a maple leaf and 大売出し
    img, d = new(ARC, 'banner', 16, 64, (244, 240, 224, 255))
    gs.rect(d, 0, 0, 15, 1, fill='#c8301e')
    gs.rect(d, 0, 62, 15, 63, fill='#c8301e')
    leaf = ['....#...', '.#.###.#', '.######.', '..####..', '########', '.######.', '...##...', '...#....']
    for y, row in enumerate(leaf):
        for x, c in enumerate(row):
            if c == '#':
                d.point((4 + x, 4 + y), fill='#e8782a')
    gs.vtext(d, 8, 19, '大売出し', 10, 11, '#c8301e', GOTHIC)
    for x in range(1, 15, 3):
        d.point((x, 60), fill='#d8b048')


def arcade_roof():
    sheets = {'arcade': {'image': 'art/arcade.png'}}
    top_tex = []
    for y in range(16):
        row = ''
        for x in range(16):
            if x == 0:
                c = '3'                              # the lap where one sheet overlaps the next
            elif y % 4 < 2:
                c = '1'                              # corrugation crests, 25 cm apart
            else:
                c = '2'
            if (x * 11 + y * 5 + (x * y) % 7) % 61 == 0 and c != '3':
                c = '4'                              # grime
            row += c
        top_tex.append(row)
    under_tex = []
    for y in range(16):
        row = ''
        for x in range(16):
            if y in (0, 8):
                c = '3'                              # purlins every metre
            elif x == 0:
                c = '2'                              # sheet laps
            else:
                c = '1'
            row += c
        under_tex.append(row)
    mats = {
        'panel_top': {'color': '#9ebeb6', 'tag': 'roof', 'texture': {
            'texels': top_tex, 'colors': ['#000000', '#a4c2ba', '#9ab8b0', '#7e9c94', '#8e9e8e'],
            'projection': 'box', 'scale': [2, 2]}},
        'panel_under': {'color': '#f4f6e8', 'texture': {
            'texels': under_tex, 'colors': ['#000000', '#f4f6e8', '#dce2d2', '#7a868a'],
            'projection': 'box', 'scale': [2, 2]}},
        'fascia': {'color': '#e8e4d8', 'palette': True},
        'steel': {'color': '#5e6e72', 'palette': True},
        'steel_ds': {'color': '#5e6e72', 'palette': True, 'double_sided': True},
        'gutter': {'color': '#8e9298', 'palette': True},
        'ridge': {'color': '#6a7a7e', 'palette': True, 'tag': 'roof'},
        'lamp': {'color': '#fff4d0', 'class': 'emissive', 'tag': 'lantern'},
        'truss': {'color': '#5e6e72', 'double_sided': True, 'texture': cell('arcade', 'truss')},
        'banner': {'color': '#f4f0e0', 'texture': cell('arcade', 'banner')},
    }

    def slab(level):
        m = Mesh('roof')
        z0, z1 = -AR_Z, AR_Z
        for s in (-1, 1):
            e, r = (s * AR_X, AR_E), (0.0, AR_R)
            m.quad((e[0], e[1], z0), (0, r[1], z0), (0, r[1], z1), (e[0], e[1], z1), (s * 0.19, 1, 0), 'panel_top')
            m.quad((e[0], e[1] - AR_T, z0), (0, r[1] - AR_T, z0), (0, r[1] - AR_T, z1), (e[0], e[1] - AR_T, z1),
                   (-s * 0.19, -1, 0), 'panel_under')
            m.quad((e[0], e[1], z0), (e[0], e[1], z1), (e[0], e[1] - AR_T, z1), (e[0], e[1] - AR_T, z0),
                   (s, 0, 0), 'fascia')
        if level == 0:
            prof = [(-AR_X, AR_E), (0, AR_R), (AR_X, AR_E), (AR_X, AR_E - AR_T), (0, AR_R - AR_T), (-AR_X, AR_E - AR_T)]
            for z, out in ((z0, -1), (z1, 1)):
                m.face([(x, y, z) for x, y in prof], (0, 0, out), 'fascia')
        return m.node()

    def trusses():
        """Each truss two quads (eave line to ridge on each side), on hand UVs: the texture's
        left at the girder, its right at the ridge, so the pattern mirrors about the axis."""
        verts, uvs, faces, fm = [], [], [], []

        def v(p, uv):
            verts.append([r4(c) for c in p])
            uvs.append(uv)
            return len(verts) - 1

        for z in TRUSS_Z:
            top_r = ar_under(0) - 0.02
            ridge_t, ridge_b = v((0, top_r, z), [1, 0]), v((0, top_r - TRUSS_DEPTH, z), [1, 1])
            for s in (-1, 1):
                x = s * GX
                yt = ar_under(x) - 0.02
                a, b = v((x, yt, z), [0, 0]), v((x, yt - TRUSS_DEPTH, z), [0, 1])
                # seen from -Z: for the left half (s = -1) the eave end is on the left
                if s < 0:
                    faces.append([a, ridge_t, ridge_b, b])
                else:
                    faces.append([ridge_t, a, b, ridge_b])
                fm.append('truss')
        return {'id': 'trusses', 'op': 'mesh', 'vertices': verts, 'faces': faces, 'face_materials': fm, 'uvs': uvs}

    def columns(level):
        out = []
        h = 6.97
        for sx in (-1, 1):
            for sz in (-1, 1):
                id = f'column_{"w" if sx < 0 else "e"}{"s" if sz < 0 else "n"}'
                if level == 0:
                    out.append(box(id, (0.25, h, 0.25), (sx * GX, h / 2, sz * CZ), 'steel', open=['top', 'bottom']))
                else:
                    out.append(crossed_quads(id, (sx * GX, 0, sz * CZ), 0.25, h, 'steel_ds'))
        return out

    girders = [box(f'girder_{"w" if s < 0 else "e"}', (0.36, 0.5, 2 * AR_Z), (s * GX, 7.2, 0), 'steel_ds',
                   open=['top', 'back', 'front']) for s in (-1, 1)]
    gutters = [box(f'gutter_{"w" if s < 0 else "e"}', (0.22, 0.2, 2 * AR_Z), (s * 8.09, 6.88, 0), 'gutter',
                   open=['back', 'front']) for s in (-1, 1)]
    rc = Mesh('ridge_cap')
    ry = ar_top(0.35) - 0.01
    prof = [(-0.35, ry), (0.0, AR_R + 0.08), (0.35, ry)]
    for i in range(2):
        (x0, y0), (x1, y1) = prof[i], prof[i + 1]
        rc.quad((x0, y0, -AR_Z), (x1, y1, -AR_Z), (x1, y1, AR_Z), (x0, y0, AR_Z), ((x0 + x1) / 2, 1, 0), 'ridge')
    lamp_y = ar_under(0) - 0.02 - TRUSS_DEPTH
    lamps = [box(f'lamp_{i}', (0.22, 0.12, 1.2), (0, lamp_y - 0.04, z), 'lamp', open=['top', 'back', 'front'])
             for i, z in enumerate(TRUSS_Z)]
    ban = Mesh('banners')
    for z in (-2.0, 6.0):
        for x in (-2.4, 2.4):
            yt = ar_under(x) - 0.02 - TRUSS_DEPTH - 0.03
            yb = yt - 1.4
            for dz, out in ((-0.05, -1), (0.05, 1)):
                zz = z + dz
                if out < 0:
                    ban.quad((x - 0.25, yt, zz), (x + 0.25, yt, zz), (x + 0.25, yb, zz), (x - 0.25, yb, zz), (0, 0, -1), 'banner')
                else:
                    ban.quad((x + 0.25, yt, zz), (x - 0.25, yt, zz), (x - 0.25, yb, zz), (x + 0.25, yb, zz), (0, 0, 1), 'banner')

    nodes0 = [slab(0), trusses()] + girders + columns(0) + gutters + [rc.node()] + lamps + [ban.node()]
    nodes1 = [slab(1), trusses()] + columns(1)
    l2 = Mesh('roof')
    for s in (-1, 1):
        l2.quad((s * AR_X, AR_E, -AR_Z), (0, AR_R, -AR_Z), (0, AR_R, AR_Z), (s * AR_X, AR_E, AR_Z), (s * 0.19, 1, 0), 'panel_top')
        l2.quad((s * AR_X, AR_E - AR_T, -AR_Z), (0, AR_R - AR_T, -AR_Z), (0, AR_R - AR_T, AR_Z), (s * AR_X, AR_E - AR_T, AR_Z),
                (-s * 0.19, -1, 0), 'panel_under')
    nodes2 = [l2.node()]
    folder = os.path.join(ASSETS, 'arcade_roof_16')
    os.makedirs(folder, exist_ok=True)
    r = recipe('arcade_roof_16', 200, sheets, mats, nodes0,
               [{'distance': 24, 'nodes': nodes1}, {'distance': 60, 'nodes': nodes2}])
    write(os.path.join(folder, 'arcade_roof_16.asset.json'), r)

    # Collision: the slab (each slope in two pieces along z, the fascias the lips to grab, the
    # underside a ceiling, the ends) and the four columns.
    c = Mesh('roof')
    for s in (-1, 1):
        for z0, z1 in ((-AR_Z, 0.0), (0.0, AR_Z)):
            c.quad((s * AR_X, AR_E, z0), (0, AR_R, z0), (0, AR_R, z1), (s * AR_X, AR_E, z1), (s * 0.19, 1, 0), 'solid')
        c.quad((s * AR_X, AR_E - AR_T, -AR_Z), (0, AR_R - AR_T, -AR_Z), (0, AR_R - AR_T, AR_Z), (s * AR_X, AR_E - AR_T, AR_Z),
               (-s * 0.19, -1, 0), 'solid')
        c.quad((s * AR_X, AR_E, -AR_Z), (s * AR_X, AR_E, AR_Z), (s * AR_X, AR_E - AR_T, AR_Z), (s * AR_X, AR_E - AR_T, -AR_Z),
               (s, 0, 0), 'solid')
    prof = [(-AR_X, AR_E), (0, AR_R), (AR_X, AR_E), (AR_X, AR_E - AR_T), (0, AR_R - AR_T), (-AR_X, AR_E - AR_T)]
    for z, out in ((-AR_Z, -1), (AR_Z, 1)):
        c.face([(x, y, z) for x, y in prof], (0, 0, out), 'solid')
    cols = [slab_box(f'column_{i}', sx * GX - 0.125, sx * GX + 0.125, 0, ar_under(sx * GX) + 0.01,
                     sz * CZ - 0.125, sz * CZ + 0.125, open=('bottom', 'top'))
            for i, (sx, sz) in enumerate(((-1, -1), (-1, 1), (1, -1), (1, 1)))]
    # tag 'metal': the footsteps' surface byte 8 (carts/garden/README.md, "Surfaces")
    write(os.path.join(folder, 'arcade_roof_16_col.asset.json'),
          col_recipe('arcade_roof_16_col', [c.node()] + cols,
                     {'solid': {'color': '#ffffff', 'palette': True, 'tag': 'metal'}}))


# ============================================================================================
# town_awning_bounce: a shop's retractable canvas awning, 8 m wide and 1.5 m deep, whose top
# is a bounce (spec 3.2: 2.6 m, +4.5 m). Pink-red and cream stripes, the garden's bounce
# colour, so the first one a player meets reads as the thing to jump on. Origin at the centre
# of its footprint at street level: the wall it hangs on is the plane z = +0.75, the street
# toward -Z. The canvas runs from 2.95 at the wall down to 2.6 at its front edge, a scalloped
# valance hangs to 2.32.
# ============================================================================================

AW_WALL, AW_OUT = 0.77, -0.75
AW_TOP_W, AW_TOP_O, AW_VAL, AW_UND_W = 2.95, 2.6, 0.28, 2.72
AW_X = 4.0
AW_IN = -0.1                  # the back awnings' collision: bounce from here out (town_awning_bounce_back_col)


def awning_bounce():
    pink, cream = '#f04880', '#f4f0e0'
    val = []
    for y in range(8):
        row = ''
        for x in range(128):
            c = '0' if (x // 8) % 2 == 0 else '1'
            if y >= 6:                                       # scallops: a hole between each pair
                k = x % 8
                if (y == 6 and k in (0, 7)) or (y == 7 and k in (0, 1, 6, 7)):
                    c = '3'
            if y == 0:
                c = '2'                                      # the front bar's shadow line
            row += c
        val.append(row)
    mats = {
        'canvas': {'color': pink, 'tag': 'bounce', 'texture': {
            'pattern': 'stripes', 'size': 16, 'colors': [pink, cream], 'params': {'count': 2, 'axis': 'u'},
            'projection': 'box', 'scale': [1, 1]}},
        'valance': {'color': pink, 'tag': 'bounce', 'texture': {
            'texels': val, 'colors': [pink, cream, '#a8325a', '#000000'], 'clear': '#000000', 'projection': 'fit'}},
        'alu': {'color': '#c4c8cc', 'palette': True},
        'arm': {'color': '#8e9298', 'palette': True},
    }
    prof = [(AW_WALL, AW_TOP_W), (AW_OUT, AW_TOP_O), (AW_OUT, AW_TOP_O - AW_VAL), (AW_WALL, AW_UND_W)]

    def canvas(level):
        m = Mesh('canvas')
        if level == 0:
            prism_x(m, -AW_X, AW_X, prof, {0: 'canvas', 1: 'valance', 2: 'canvas', 3: None, 'end': 'canvas'})
        else:
            prism_x(m, -AW_X, AW_X, prof, {0: 'canvas', 1: 'valance', 2: None, 3: None, 'end': None}, ends=False)
        return m.node()

    roller = box('roller', (2 * AW_X + 0.2, 0.18, 0.2), (0, 3.0, 0.68), 'alu', open=['front'])
    arms = Mesh('arms')
    for x in (-3.4, 3.4):
        beam(arms, (x, 2.05, 0.8), (x, AW_TOP_O - AW_VAL + 0.06, AW_OUT + 0.12), 0.06, 'arm')
    nodes0 = [canvas(0), roller, arms.node()]
    nodes1 = [canvas(1)]
    folder = os.path.join(ASSETS, 'town_awning_bounce')
    os.makedirs(folder, exist_ok=True)
    r = recipe('town_awning_bounce', 40, {}, mats, nodes0, [{'distance': 20, 'nodes': nodes1}], cull=60)
    del r['sheets']
    write(os.path.join(folder, 'town_awning_bounce.asset.json'), r)

    # Collision: the canvas as a closed wedge against the wall; its top and its valance are the
    # bounce surface, the underside and the ends solid.
    c = Mesh('awning')
    cprof = [(0.75, AW_TOP_W), (AW_OUT, AW_TOP_O), (AW_OUT, AW_TOP_O - AW_VAL), (0.75, AW_UND_W)]
    prism_x(c, -AW_X, AW_X, cprof, {0: 'bounce', 1: 'bounce', 2: 'solid', 3: None, 'end': 'solid'})
    write(os.path.join(folder, 'town_awning_bounce_col.asset.json'),
          col_recipe('town_awning_bounce_col', [c.node()],
                     {'bounce': {'color': '#f04880', 'palette': True, 'tag': 'bounce'}}, budget=40))

    # The back walls' awnings (place/street.py: w2b, e3b, w4b) hang under their shops' eaves,
    # which reach 0.2-0.45 m out over the canvas: a bounce there struck the eave at 4.0 (alpha
    # review r08 #8). Their collision's inner 0.85 m is a steep face (60 degrees, a wall) from the
    # canvas up to the wall, which moves a body landing there out onto the outer part, from where a
    # bounce clears the eave.
    c = Mesh('awning')
    y_in = round(AW_TOP_W - (AW_TOP_W - AW_TOP_O) * (0.75 - AW_IN) / (0.75 - AW_OUT), 4)
    cprof = [(0.75, round(y_in + (0.75 - AW_IN) * 1.73, 4)), (AW_IN, y_in), (AW_OUT, AW_TOP_O),
             (AW_OUT, AW_TOP_O - AW_VAL), (0.75, AW_UND_W)]
    # (each side faced away from a point inside the section: the wall's height moves the vertices'
    # centroid, which prism_x faces by, above the canvas)
    inside = (0.3, 2.8)
    for i, mat in enumerate(['solid', 'bounce', 'bounce', 'solid', None]):
        (z0, y0), (z1, y1) = cprof[i], cprof[(i + 1) % len(cprof)]
        if mat:
            out = (0, (y0 + y1) / 2 - inside[1], (z0 + z1) / 2 - inside[0])
            c.quad((-AW_X, y0, z0), (AW_X, y0, z0), (AW_X, y1, z1), (-AW_X, y1, z1), out, mat)
    for x, sx in ((-AW_X, -1), (AW_X, 1)):
        c.face([(x, y, z) for z, y in cprof], (sx, 0, 0), 'solid')
    write(os.path.join(folder, 'town_awning_bounce_back_col.asset.json'),
          col_recipe('town_awning_bounce_back_col', [c.node()],
                     {'bounce': {'color': '#f04880', 'palette': True, 'tag': 'bounce'}}, budget=40))


if __name__ == '__main__':
    gs.draw_sheet()                     # the sheet's cells, for its helpers (nothing is written)
    draw_tea()
    pack(TEA, os.path.join(HERE, 'art', 'tea.png'))
    shop_3f()
    draw_more()
    pack(MORE, os.path.join(HERE, 'art', 'more.png'))
    for name in VARIANTS_3F:
        shop_3f(name)
    draw_arcade()
    pack(ARC, os.path.join(ASSETS, 'arcade_roof_16', 'art', 'arcade.png'))
    arcade_roof()
    awning_bounce()
