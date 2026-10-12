"""Writes cemetery_grave_row.asset.json and cemetery_grave_row_col.asset.json beside this script
(python3 make_cemetery_grave_row.py; the textures first with python3 art/draw_graves.py): a row
of eight family graves on the cemetery's terraces (shrine town spec 3.14; assets.md #24), about
40 placed, merged, culled at 40 m.

Footprint 8 x 2 m, origin at the middle of the footprint's base, the graves facing -Z. A granite
plinth 0.2 m high (a step up the player takes without jumping) holds eight plots of 1 x 2 m,
their kerbs and pebbles in its top's texture; the stones stand on the back half (z 0.1-0.8),
visitors stand on the front half. Four family graves (a base 0.72 m square and 0.34 high, an
upright 0.36 square to 1.38 with the family's name carved down it), three old pointed graves
(0.28 square, to 0.92) and one black modern one (a slab to 0.89 reading "yasuragi"). In front of
each, but one old grave nobody visits, a card of two stone flower holders with chrysanthemums and
the incense stand between them (art/graves.png, a cutout). The stones are the shared cemetery
stone (../cemetery_terrace_wall_12/art/), the sotoba racks (cemetery_sotoba_rack, 1.6 m) stand
behind a row.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

STONE = '../cemetery_terrace_wall_12/art/'
P = 0.2                          # the plinth's top
ZC = 0.45                        # the stones' centre line
X = 3.98                         # the plinth's half length


def planar(img, color, tag=None):
    m = {'color': color, 'texture': {'image': img, 'projection': 'planar'}}
    if tag:
        m['tag'] = tag
    return m


def cell(name, color, double=False):
    m = {'color': color, 'texture': {'sheet': 'graves', 'cell': name, 'projection': 'fit'}}
    if double:
        m['double_sided'] = True
    return m


MATS = {
    'kerb': planar(STONE + 'coping.png', '#b8b2a2', 'floor'),
    'plot': planar('art/plot.png', '#c8c2b2', 'floor'),
    'granite': planar(STONE + 'granite.png', '#a8a6a0'),
    'granite_dark': planar(STONE + 'granite_dark.png', '#3a3a40'),
    'old': planar(STONE + 'old_stone.png', '#8e887c'),
}
for n in ('name_yamada', 'name_tanaka', 'name_nakamura', 'name_ogawa'):
    MATS[n] = cell(n, '#a8a6a0')
MATS['old_a'] = cell('old_a', '#8e887c')
MATS['old_b'] = cell('old_b', '#8e887c')
MATS['western'] = cell('western', '#3a3a40')
for k in 'abc':
    MATS['flowers_' + k] = cell('flowers_' + k, '#f0c030', True)

# (kind, face material, flowers card or None), west to east
GRAVES = [('waga', 'name_yamada', 'a'), ('old', 'old_a', 'c'), ('waga', 'name_tanaka', 'b'),
          ('west', 'western', 'a'), ('waga', 'name_nakamura', 'a'), ('old', 'old_b', None),
          ('waga', 'name_ogawa', 'b'), ('old', 'old_a', 'a')]
CROP = {'back': (0, 0, 1, 1)}


def plinth(p):
    # 7.96 m, so the plots' top spans under 255 texels and needs no cut; rows 4 cm apart
    p.box({'*': 'kerb'}, -X, X, 0.0, P, -1.0, 1.0, open=('bottom', 'top'), su=2.0)
    p.face_uv('plot', [(-X, P, 1.0), (X, P, 1.0), (X, P, -1.0), (-X, P, -1.0)], 1.0, 2.0,
              origin=(-4.0, P, 1.0))


def card(p, x, kind, zf):
    w, h = 0.38, 0.57
    p.face('flowers_' + kind, [(x - w, P - 0.01 + h, zf), (x + w, P - 0.01 + h, zf),
                               (x + w, P - 0.01, zf), (x - w, P - 0.01, zf)],
           [(0, 0), (1, 0), (1, 1), (0, 1)])


def old_grave(p, x, face):
    a, z0, z1, top, apex = 0.14, ZC - 0.14, ZC + 0.14, 0.80, 0.92
    p.box({'*': 'old', 'back': face}, x - a, x + a, P - 0.01, top, z0, z1,
          open=('bottom', 'top'), su=0.5, crop=CROP)
    tip = (x, apex, ZC)
    corners = [(x - a, top, z0), (x + a, top, z0), (x + a, top, z1), (x - a, top, z1)]
    for k in range(4):
        p.face_uv('old', [corners[k], tip, corners[(k + 1) % 4]], 0.5)


def level0():
    base, stones, offer = ap.Part('plinth'), ap.Part('graves'), ap.Part('offerings')
    plinth(base)
    for k, (kind, face, fl) in enumerate(GRAVES):
        x = -3.5 + k
        if kind == 'waga':
            stones.box('granite', x - 0.36, x + 0.36, P - 0.01, 0.53, ZC - 0.36, ZC + 0.36,
                       open=('bottom',), su=0.5)
            stones.box({'*': 'granite', 'back': face}, x - 0.18, x + 0.18, 0.52, 1.38,
                       ZC - 0.18, ZC + 0.18, open=('bottom',), su=0.5, crop=CROP)
            zf = ZC - 0.36 - 0.05
        elif kind == 'old':
            old_grave(stones, x, face)
            zf = ZC - 0.14 - 0.08
        else:
            stones.box('granite_dark', x - 0.45, x + 0.45, P - 0.01, 0.40, ZC - 0.30, ZC + 0.30,
                       open=('bottom',), su=0.5)
            stones.box({'*': 'granite_dark', 'back': face}, x - 0.40, x + 0.40, 0.39, 0.89,
                       ZC - 0.08, ZC + 0.08, open=('bottom',), su=0.5, crop=CROP)
            zf = ZC - 0.30 - 0.05
        if fl:
            card(offer, x, fl, zf)
    return [base, stones, offer]


def level1():
    """From 16 m: the plinth, and each grave as one block without its offerings."""
    base, stones = ap.Part('plinth'), ap.Part('graves')
    plinth(base)
    for k, (kind, face, _) in enumerate(GRAVES):
        x = -3.5 + k
        if kind == 'waga':
            stones.box({'*': 'granite', 'back': face}, x - 0.26, x + 0.26, P - 0.01, 1.38,
                       ZC - 0.26, ZC + 0.26, open=('bottom',), su=0.5, crop=CROP)
        elif kind == 'old':
            stones.box({'*': 'old', 'back': face}, x - 0.14, x + 0.14, P - 0.01, 0.86,
                       ZC - 0.14, ZC + 0.14, open=('bottom',), su=0.5, crop=CROP)
        else:
            stones.box({'*': 'granite_dark', 'back': face}, x - 0.45, x + 0.45, P - 0.01, 0.89,
                       ZC - 0.2, ZC + 0.2, open=('bottom',), su=0.5, crop=CROP)
    return [base, stones]


def collision():
    p = ap.Part('body')
    ap.col_box(p, -X, X, 0.0, P, -1.0, 1.0, open=('bottom',))
    for k, (kind, _, _) in enumerate(GRAVES):
        x = -3.5 + k
        if kind == 'waga':
            ap.col_box(p, x - 0.36, x + 0.36, P, 0.53, ZC - 0.36, ZC + 0.36, open=('bottom',))
            ap.col_box(p, x - 0.2, x + 0.2, 0.53, 1.38, ZC - 0.2, ZC + 0.2, open=('bottom',))
        elif kind == 'old':
            ap.col_box(p, x - 0.15, x + 0.15, P, 0.86, ZC - 0.15, ZC + 0.15, open=('bottom',))
        else:
            ap.col_box(p, x - 0.45, x + 0.45, P, 0.40, ZC - 0.30, ZC + 0.30, open=('bottom',))
            ap.col_box(p, x - 0.42, x + 0.42, 0.40, 0.89, ZC - 0.1, ZC + 0.1, open=('bottom',))
    return [p]


def main():
    r = ap.recipe('cemetery_grave_row', MATS, level0(), 160,
                  {'levels': [(16, level1())], 'cull': 40, 'band': 2})
    r['sheets'] = {'graves': {'image': 'art/graves.png'}}
    ap.write(HERE / 'cemetery_grave_row.asset.json', r)
    ap.write(HERE / 'cemetery_grave_row_col.asset.json',
             ap.col_recipe('cemetery_grave_row_col', collision()))


if __name__ == '__main__':
    main()
