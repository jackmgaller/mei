#!/usr/bin/env python3
"""Writes street_building_dressing.asset.json and its _col beside this script: what the shrine's
street_building (../../../shrine/assets, placed as it is at (193, 0, 73), yaw 90) lacks as the
shrine town's building: windows and a painted advert on its blank north end wall, which faces the
front road and the torii crossing, and the clutter of a roof (air-conditioner condensers on a
stand, a television aerial). Alpha review r15 #4: the end wall was flat tan, the roof an empty
slab with two plain boxes.

    python3 carts/garden/shrinetown/assets/street_building_dressing/make_street_building_dressing.py
    (Pillow and the macOS Hiragino fonts, through ../town_shop_2f_a/gen_shops.py's helpers)

Origin: the end wall's plane at the building's middle, world (193, 0, 102), yaw 0; x is world x,
the wall faces +Z (north). The wall runs x -5.8..7.0 (world 187.2-200); the fire escape covers
x 1..6 (world 194-199), so the windows and the advert keep west of it. The roof deck is 15.2,
the parapet 16.0, the deck x -5.55..6.75 and z -57.75..-0.25 here. Glide G1 takes off along
world x 193 (x 0) toward the north edge: nothing stands within 2.5 m of that line.
Windows and the condensers' fronts are cells of the shops' sheet (shopfront.png: back_win, ac,
antenna); the advert is a mask in three colours, as the shops' signs.
"""
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location('gen_shops', os.path.join(ASSETS, 'town_shop_2f_a', 'gen_shops.py'))
gs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gs)

SHEET = '../town_shop_2f_a/art/shopfront.png'
STOREY = 3.04
DECK = 15.2
OUT = 0.02                      # the window panes stand off the wall


def advert():
    """Maruei Building, tenants wanted: the owner's name and a telephone number."""
    img, d = gs.mask(64, 32)
    gs.rect(d, 0, 0, 63, 31, outline=gs.RIM)
    gs.rect(d, 2, 2, 61, 29, outline=gs.RIM)
    for i, ch in enumerate('丸栄ビル'):
        gs.text(d, (11 + i * 14, 11), ch, 13, gs.FG)
    gs.text(d, (32, 23), 'テナント募集', 9, gs.FG, gs.GOTHIC_M)
    return img


def quad_z(nid, x0, x1, y0, y1, z, mat):
    """A pane facing +Z at z."""
    return {'id': nid, 'op': 'mesh', 'vertices': [[x1, y1, z], [x0, y1, z], [x0, y0, z], [x1, y0, z]],
            'faces': [[0, 1, 2, 3]], 'face_materials': [mat]}


def nodes(level):
    n = []
    # windows: two a storey on storeys 2-5, west of the fire escape
    k = 0
    for s in range(1, 5):
        y = s * STOREY + 1.5
        for x in (-4.3, -1.7):
            if s == 4 and x == -1.7:
                continue                                # the advert's place
            n.append(quad_z(f'win_{k}', x - 0.7, x + 0.7, y - 0.45, y + 0.45, OUT, 'window'))
            k += 1
    # the painted advert, high on the wall: seen from the road and the torii
    n.append(quad_z('advert', -3.6, 0.6, 12.0, 14.3, OUT, 'advert'))
    if level == 0:
        # the roof: three condensers on a steel stand by the west parapet, an aerial
        for i, z in enumerate((-38.0, -36.6, -35.2)):
            n.append(gs.box(f'ac_{i}', (0.35, 0.65, 0.9), (-4.9, DECK + 0.45, z), 'ac_body', open=['bottom'],
                            faces={'right': 'ac'}))
        n.append(gs.box('stand', (0.6, 0.12, 4.2), (-4.9, DECK + 0.06, -36.6), 'steel', open=['bottom']))
        n.append(gs.crossed_quads('aerial', (-4.6, DECK, -14.0), 1.6, 2.4, 'antenna'))
    return n


def main():
    gs.draw_sheet()                                     # the sheet's cells, for the helpers
    ad = ['#e6dcc4', '#a8321e', '#2c2a28']
    mats = {
        'window': {'color': '#c8d4d8', 'texture': gs.cell_tex('back_win')},
        'advert': {'color': ad[0], 'texture': gs.mask_grid(advert(), ad)},
        'ac': {'color': '#e2e0d6', 'texture': gs.cell_tex('ac')},
        'ac_body': {'color': '#e2e0d6', 'palette': True},
        'steel': {'color': '#5e6468', 'palette': True},
        'antenna': {'color': '#7a7e84', 'double_sided': True, 'texture': gs.cell_tex('antenna')},
    }
    r = gs.recipe('street_building_dressing', 120, mats, nodes(0),
                  [{'distance': 40, 'nodes': nodes(1)}], sheet=SHEET)
    r['lod']['cull'] = 160
    gs.write(os.path.join(HERE, 'street_building_dressing.asset.json'), r)
    col = gs.col_recipe('street_building_dressing_col', [
        gs.slab_box('acs', -5.2, -4.6, DECK, DECK + 0.9, -38.5, -34.7, open=('bottom',))])
    gs.write(os.path.join(HERE, 'street_building_dressing_col.asset.json'), col)
    print('wrote street_building_dressing')


if __name__ == '__main__':
    main()
