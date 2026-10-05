"""Writes cemetery_gate.asset.json, cemetery_gate_col.asset.json and art/ beside this script
(python3 make_cemetery_gate.py; Pillow and macOS's Hiragino Mincho for the plaque): the gate of
the temple cemetery on the east shoulder (shrine town spec 3.14; assets.md #26).

A plain roofed gate (kabukimon) of dark old wood: two posts on granite footings, a tie beam
through them, a head beam, a ridge board, and a small gabled roof of grey kawara with a dark
ridge and end tiles. The cemetery's name plaque (東山墓地) hangs on the west post's face. No
doors: the gate stands open at the foot of the cemetery's middle stair.

Footprint 7.4 x 2.3 m (the eaves; the posts stand 5.5 m apart, centre to centre, with 5.2 m
clear between them), height 4.84 to the end tiles. Eaves 4.0-4.14 at z +-1.05, the slopes 24.6
degrees to the ridge at 4.62 (walkable), the ridge cap to 4.74. Origin at the middle of the
opening at ground level; front (-Z) toward the lane.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

ART = HERE / 'art'
MINCHO = '/System/Library/Fonts/ヒラギノ明朝 ProN.ttc'

PX = 2.75                     # posts' centres
PW = 0.15                     # posts' half width
FOOT = (0.28, 0.5)            # footing half width, top
KABUKI = (3.3, 3.2, 3.5, 0.1)         # half length, bottom, top, half depth
HEAD = (3.0, 3.85, 4.05, 0.2)         # half length, bottom, top, half depth
EX, EZ, LO, HI, RIDGE = 3.6, 1.05, 4.0, 4.14, 4.62
CAP = (RIDGE - 0.08, RIDGE + 0.12, 0.13)
ONI = (0.22, RIDGE + 0.22, 0.17)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def draw_art():
    """The name plaque: an old pale board, the name brushed in black, a dark frame."""
    ART.mkdir(exist_ok=True)
    im = Image.new('RGBA', (16, 64), rgb('#b8a07a'))
    d = ImageDraw.Draw(im)
    d.fontmode = '1'
    for y in range(64):
        if y % 7 == 3:
            d.line([(1, y), (14, y)], fill=rgb('#a8906a'))     # grain
    d.rectangle([0, 0, 15, 63], outline=rgb('#5a3e2c'))
    font = ImageFont.truetype(MINCHO, 13, index=2)
    for k, ch in enumerate('東山墓地'):
        w = d.textlength(ch, font=font)
        d.text(((16 - w) / 2, 3 + k * 14.5), ch, font=font, fill=rgb('#2c2a28'))
    im.save(ART / 'plaque.png')


MATS = ap.materials('tile', 'stone', 'tile_dark', extra={
    'wood': {'color': '#4a3a2e', 'palette': True},
    'wood_end': {'color': '#8a6446', 'palette': True},
    'rafters': {'color': '#2c2a28', 'palette': True},
    'plaque': {'color': '#b8a07a', 'texture': {'image': 'art/plaque.png', 'projection': 'fit'}},
})


def footings(p):
    hw, top = FOOT
    for s in (-1, 1):
        p.box('stone', s * PX - hw, s * PX + hw, 0.0, top, -hw, hw, open=('bottom',), su=1.0)


def posts():
    p = ap.Part('posts')
    idx = None
    for s in (-1, 1):
        if s < 0:
            idx = len(p.f)
        p.box('wood', s * PX - PW, s * PX + PW, FOOT[1] - 0.02, HEAD[1] + 0.07, -PW, PW,
              open=('bottom', 'top'))
    node = p.node()
    # the box's sides come back, front, right, left: the west post's front face is its first
    node['decals'] = [{'id': 'plaque', 'face': idx, 'material': 'plaque', 'size': [0.22, 0.88],
                       'at': [-PX, 2.35]}]
    return node


def beams(p):
    hl, y0, y1, hd = KABUKI
    p.box({'*': 'wood', 'left': 'wood_end', 'right': 'wood_end'}, -hl, hl, y0, y1, -hd, hd)
    hl, y0, y1, hd = HEAD
    p.box({'*': 'wood', 'left': 'wood_end', 'right': 'wood_end'}, -hl, hl, y0, y1, -hd, hd,
          open=())
    # the ridge board standing on the head beam, up into the roof
    p.box('wood', -hl + 0.2, hl - 0.2, y1 - 0.02, RIDGE - 0.1, -0.05, 0.05,
          open=('bottom', 'top'))


def roof(p):
    ap.gable_roof(p, EX, EZ, LO, HI, RIDGE, gable='wood')
    ap.ridge_cap(p, EX + 0.08, CAP[0], CAP[1], CAP[2], oni=ONI)


def level0():
    ft, bm, rf = ap.Part('footings'), ap.Part('beams'), ap.Part('roof')
    footings(ft)
    beams(bm)
    roof(rf)
    return [ft, posts(), bm, rf]


def simple_roof(p, cap=True):
    for s in (-1, 1):
        if s < 0:
            pts = [(-EX, RIDGE, 0), (EX, RIDGE, 0), (EX, LO, -EZ), (-EX, LO, -EZ)]
        else:
            pts = [(EX, RIDGE, 0), (-EX, RIDGE, 0), (-EX, LO, EZ), (EX, LO, EZ)]
        p.face_uv('tile', pts, 2.0, 2.0, origin=pts[3])
    end = [(EX, LO, -EZ), (EX, RIDGE, 0), (EX, LO, EZ)]
    p.face('wood', end)
    p.face('wood', ap.mirror_x(end))
    p.face('rafters', [(-EX, LO, -EZ), (EX, LO, -EZ), (EX, LO, EZ), (-EX, LO, EZ)])
    if cap:
        p.box('tile_dark', -EX - 0.08, EX + 0.08, CAP[0], CAP[1], -CAP[2], CAP[2],
              open=('bottom', 'left', 'right'))


def level1():
    """From 30 m: posts to the ground, the two beams without their ends, the roof as two slopes,
    two gables and a flat soffit."""
    p = ap.Part('gate')
    for s in (-1, 1):
        p.box('wood', s * PX - PW, s * PX + PW, 0.0, HEAD[1] + 0.07, -PW, PW,
              open=('bottom', 'top'))
    for hl, y0, y1, hd in (KABUKI, HEAD):
        p.box('wood', -hl, hl, y0, y1, -hd, hd, open=('left', 'right'))
    simple_roof(p, cap=False)
    return [p]


def level2():
    """From 70 m: two posts and the roof."""
    p = ap.Part('gate')
    for s in (-1, 1):
        p.box('wood', s * PX - PW, s * PX + PW, 0.0, LO + 0.02, -PW, PW,
              open=('bottom', 'top'))
    simple_roof(p, cap=False)
    return [p]


def collision():
    p = ap.Part('body')
    hw, top = FOOT
    for s in (-1, 1):
        ap.col_box(p, s * PX - hw, s * PX + hw, 0.0, top, -hw, hw, open=('bottom',))
        ap.col_box(p, s * PX - PW, s * PX + PW, top, HEAD[1], -PW, PW, open=('bottom', 'top'))
    hl, y0, y1, _ = KABUKI
    ap.col_box(p, -hl, hl, y0, y1, -0.12, 0.12)
    hl, y0, _, hd = HEAD
    ap.col_box(p, -hl, hl, y0, LO - 0.02, -hd, hd)
    # the roof as one solid: slopes, fascias, the flat underside and the gable ends
    for s in (-1, 1):
        if s < 0:
            ap.col_quad(p, (-EX, RIDGE, 0), (EX, RIDGE, 0), (EX, HI, -EZ), (-EX, HI, -EZ))
            ap.col_quad(p, (-EX, HI, -EZ), (EX, HI, -EZ), (EX, LO, -EZ), (-EX, LO, -EZ))
        else:
            ap.col_quad(p, (EX, RIDGE, 0), (-EX, RIDGE, 0), (-EX, HI, EZ), (EX, HI, EZ))
            ap.col_quad(p, (EX, HI, EZ), (-EX, HI, EZ), (-EX, LO, EZ), (EX, LO, EZ))
    ap.col_quad(p, (-EX, LO, -EZ), (EX, LO, -EZ), (EX, LO, EZ), (-EX, LO, EZ))
    end = [(EX, HI, -EZ), (EX, RIDGE, 0), (EX, HI, EZ), (EX, LO, EZ), (EX, LO, -EZ)]
    p.face('solid', end)
    p.face('solid', ap.mirror_x(end))
    return [p]


def main():
    draw_art()
    lod = {'levels': [(30, level1()), (70, level2())], 'cull': 150, 'band': 2}
    ap.write(HERE / 'cemetery_gate.asset.json',
             ap.recipe('cemetery_gate', MATS, level0(), 150, lod))
    ap.write(HERE / 'cemetery_gate_col.asset.json',
             ap.col_recipe('cemetery_gate_col', collision()))


if __name__ == '__main__':
    main()
