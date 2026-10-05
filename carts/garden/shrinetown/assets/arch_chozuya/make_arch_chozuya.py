"""Writes arch_chozuya.asset.json and arch_chozuya_col.asset.json beside this script
(python3 make_arch_chozuya.py): the purification water pavilion in the outer courtyard (shrine
town spec 3.6; assets.md #50).

Four vermilion posts on a stone pad carry a gabled tile roof, as the precinct's gate and halls
(the shrine's architecture textures; the roof is arch_wall_gate's, through arch_parts.py). Under
it a stone basin brimming with water, a bronze spout on a mossy rock at its back, three ladles
on its front rim, and a plaque on the front beam.

Footprint 6 x 4 m (the eaves; the pad is 5.2 x 3.4), origin at the middle of the pad's base, the
long side -Z toward the path. Eaves 2.0-2.22 at z +-2.0 (a jump and a grab from the gravel),
slopes 24 degrees to the ridge at 3.1, the ridge cap to 3.24 and its end tiles to 3.3. The posts
stand at x +-2.2, z +-1.25; the basin is 2.0 x 0.9, its water at 0.85.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

EX, EZ = 3.0, 2.0
LO, HI, RIDGE = 2.0, 2.22, 3.1
PAD = (2.6, 1.7, 0.15)          # half x, half z, height
PX, PZ, PW = 2.2, 1.25, 0.2     # posts
BASIN = (1.0, 0.45, 0.85)       # half x, half z, top
TOP_BEAM = (2.05, 2.3)


def pad(p):
    x, z, h = PAD
    p.box('stone', -x, x, 0.0, h, -z, z, open=('bottom',), su=2.4)


def frame(p):
    for sx in (-1, 1):
        for sz in (-1, 1):
            x0, x1 = sorted((sx * (PX - PW / 2), sx * (PX + PW / 2)))
            z0, z1 = sorted((sz * (PZ - PW / 2), sz * (PZ + PW / 2)))
            p.box('lacquer', x0, x1, PAD[2] - 0.02, TOP_BEAM[1] - 0.02, z0, z1,
                  open=('bottom', 'top'))
    for sz in (-1, 1):          # the beams along the long sides, their ends standing out
        z0, z1 = sorted((sz * (PZ - 0.065), sz * (PZ + 0.065)))
        p.box({'*': 'lacquer', 'bottom': 'shade'}, -PX - 0.3, PX + 0.3, TOP_BEAM[0],
              TOP_BEAM[1], z0, z1)
    for sx in (-1, 1):          # the tie beams across, under the gables
        x0, x1 = sorted((sx * (PX - 0.065), sx * (PX + 0.065)))
        p.box({'*': 'lacquer', 'bottom': 'shade'}, x0, x1, TOP_BEAM[0] + 0.06,
              TOP_BEAM[1] + 0.06, -PZ - 0.25, PZ + 0.25)


def roof(p):
    ap.gable_roof(p, EX, EZ, LO, HI, RIDGE)
    ap.ridge_cap(p, EX + 0.12, RIDGE - 0.1, 3.24, 0.15, oni=(0.24, 3.3, 0.21))


def plaque(p):
    """The name plaque (the halls' gaku) hanging on the front beam."""
    z = -PZ - 0.09
    p.box({'*': 'black', 'back': 'gaku'}, -0.14, 0.14, 1.62, 2.08, z - 0.1, z - 0.06,
          crop={'back': (0, 0, 1, 1)})


def basin_nodes():
    bx, bz, top = BASIN
    basin = {'id': 'basin', 'op': 'box', 'size': [2 * bx, top - 0.1, 2 * bz], 'material': 'stone_mid',
             'open': ['bottom'], 'faces': {'top': 'stone_pal'},
             'decals': [{'id': 'water', 'face': 'top', 'material': 'water',
                         'size': [2 * bx - 0.2, 2 * bz - 0.2]}],
             'transform': {'translate': [0, (top + 0.1) / 2, 0]}}
    return [basin]


def spout(p):
    """A mossy rock behind the basin and the bronze spout over the water."""
    p.box('mossy', -0.32, 0.32, 0.12, 1.3, BASIN[1] - 0.05, BASIN[1] + 0.45, open=('bottom',),
          su=1.0)
    p.box({'*': 'copper', 'back': 'black'}, -0.07, 0.07, 1.04, 1.16, BASIN[1] - 0.35,
          BASIN[1] + 0.02, open=('front',))


def ladles(p):
    """Three ladles laid across the basin's front rim, cups down, handles toward the water."""
    y = BASIN[2]
    for k, x in enumerate((-0.5, 0.0, 0.5)):
        z = -BASIN[1] + 0.02
        p.box('wood_new', x - 0.055, x + 0.055, y - 0.02, y + 0.07, z - 0.12, z - 0.01,
              open=('bottom',))
        p.box('wood_new', x - 0.014, x + 0.014, y + 0.03, y + 0.06, z - 0.01, z + 0.42,
              open=('back', 'bottom'))


def level0():
    base, fr, rf, det = ap.Part('pad'), ap.Part('frame'), ap.Part('roof'), ap.Part('details')
    pad(base)
    frame(fr)
    roof(rf)
    plaque(det)
    spout(det)
    ladles(det)
    return [base, fr, rf, det] + basin_nodes()


def level1():
    """From 35 m: the pad's top and sides, posts as open boxes, one beam per side, the roof
    without its soffit, the basin as a block."""
    p = ap.Part('chozuya')
    x, z, h = PAD
    p.box('stone', -x, x, 0.0, h, -z, z, open=('bottom',), su=2.4)
    for sx in (-1, 1):
        for sz in (-1, 1):
            x0, x1 = sorted((sx * (PX - PW / 2), sx * (PX + PW / 2)))
            z0, z1 = sorted((sz * (PZ - PW / 2), sz * (PZ + PW / 2)))
            p.box('lacquer', x0, x1, h - 0.02, TOP_BEAM[1], z0, z1, open=('bottom', 'top'))
    for s in (-1, 1):
        if s < 0:
            pts = [(-EX, RIDGE, 0), (EX, RIDGE, 0), (EX, LO, -EZ), (-EX, LO, -EZ)]
        else:
            pts = [(EX, RIDGE, 0), (-EX, RIDGE, 0), (-EX, LO, EZ), (EX, LO, EZ)]
        p.face_uv('tile', pts, 2.0, 2.0, origin=pts[3])
    p.face('shade', [(-EX, LO, -EZ), (EX, LO, -EZ), (EX, LO, EZ), (-EX, LO, EZ)])
    p.face('lacquer', [(EX, LO, -EZ), (EX, RIDGE, 0), (EX, LO, EZ)])
    p.face('lacquer', [(-EX, LO, EZ), (-EX, RIDGE, 0), (-EX, LO, -EZ)])
    bx, bz, top = BASIN
    p.box({'*': 'stone_mid', 'top': 'stone_pal'}, -bx, bx, h - 0.02, top, -bz, bz,
          open=('bottom',))
    return [p]


def level2():
    """From 80 m: the roof as a tent over four posts."""
    p = ap.Part('chozuya')
    for s in (-1, 1):
        if s < 0:
            pts = [(-EX, RIDGE, 0), (EX, RIDGE, 0), (EX, LO, -EZ), (-EX, LO, -EZ)]
        else:
            pts = [(EX, RIDGE, 0), (-EX, RIDGE, 0), (-EX, LO, EZ), (EX, LO, EZ)]
        p.face('tile_dark', pts)
    p.face('shade', [(-EX, LO, -EZ), (EX, LO, -EZ), (EX, LO, EZ), (-EX, LO, EZ)])
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (PX - PW / 2), sx * (PX + PW / 2)))
        p.face('lacquer', [(x0, LO, -PZ), (x1, LO, -PZ), (x1, 0, -PZ), (x0, 0, -PZ)])
        p.face('lacquer', [(x1, LO, PZ), (x0, LO, PZ), (x0, 0, PZ), (x1, 0, PZ)])
    return [p]


def collision():
    p = ap.Part('body')
    x, z, h = PAD
    ap.col_box(p, -x, x, 0.0, h, -z, z, open=('bottom',))
    for sx in (-1, 1):
        for sz in (-1, 1):
            ap.col_box(p, sx * PX - 0.11, sx * PX + 0.11, h, TOP_BEAM[0] + 0.02, sz * PZ - 0.11,
                       sz * PZ + 0.11, open=('bottom',))
    bx, bz, top = BASIN
    ap.col_box(p, -bx, bx, h, top, -bz, bz + 0.45, open=('bottom',))    # basin and rock
    # the roof: the beams' level up to the slopes, as one solid over the posts' tops
    ys = (LO, HI, RIDGE)
    for s in (-1, 1):
        if s < 0:
            ap.col_quad(p, (-EX, RIDGE, 0), (EX, RIDGE, 0), (EX, HI, -EZ), (-EX, HI, -EZ))
            ap.col_quad(p, (-EX, HI, -EZ), (EX, HI, -EZ), (EX, LO, -EZ), (-EX, LO, -EZ))
            ap.col_quad(p, (-EX, LO, -EZ), (EX, LO, -EZ), (EX, TOP_BEAM[0], -PZ - 0.1),
                        (-EX, TOP_BEAM[0], -PZ - 0.1))
        else:
            ap.col_quad(p, (EX, RIDGE, 0), (-EX, RIDGE, 0), (-EX, HI, EZ), (EX, HI, EZ))
            ap.col_quad(p, (EX, HI, EZ), (-EX, HI, EZ), (-EX, LO, EZ), (EX, LO, EZ))
            ap.col_quad(p, (EX, LO, EZ), (-EX, LO, EZ), (-EX, TOP_BEAM[0], PZ + 0.1),
                        (EX, TOP_BEAM[0], PZ + 0.1))
    ap.col_quad(p, (-EX, TOP_BEAM[0], -PZ - 0.1), (EX, TOP_BEAM[0], -PZ - 0.1),
                (EX, TOP_BEAM[0], PZ + 0.1), (-EX, TOP_BEAM[0], PZ + 0.1))
    del ys
    end = [(EX, HI, -EZ), (EX, RIDGE, 0), (EX, HI, EZ), (EX, LO, EZ), (EX, TOP_BEAM[0], PZ + 0.1),
           (EX, TOP_BEAM[0], -PZ - 0.1), (EX, LO, -EZ)]
    p.face('solid', end)
    p.face('solid', ap.mirror_x(end))
    return [p]


def main():
    mats = ap.materials('tile', 'rafters', 'stone', 'gaku', 'lacquer', 'shade', 'tile_dark',
                        'black', 'copper', 'wood_new', 'water', 'stone_pal',
                        extra={'stone_mid': {'color': '#8e887c', 'palette': True},
                               'mossy': {'color': '#7a8050',
                                         'texture': {'image': ap.ART + 'forest_mossy_stone.png',
                                                     'projection': 'box', 'scale': [1.2, 1.2]}}})
    lod = {'levels': [(35, level1()), (80, level2())], 'cull': 160, 'band': 2}
    ap.write(HERE / 'arch_chozuya.asset.json', ap.recipe('arch_chozuya', mats, level0(), 300, lod))
    ap.write(HERE / 'arch_chozuya_col.asset.json', ap.col_recipe('arch_chozuya_col', collision()))


if __name__ == '__main__':
    main()
