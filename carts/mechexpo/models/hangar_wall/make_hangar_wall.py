#!/usr/bin/env python3
"""Mech Expo 2000: the demo hangar's side walls, the stage's edges at x = +-36.

The fight is seen side-on, so a wall at x = 36 is seen nearly edge-on: what reads is its front
(-Z) face, a steel pier 8 m wide and 26 m tall standing at the screen's edge, and, at a slant,
its inner face, where the mechs are cornered. The pier carries what an engineer would put on a
crash wall: a hazard-striped corner post and kick plate, two rubber impact buffers at mech
height on the inner face, ribs across the front, the hall's sign, and a floodlight cantilevered
over the arena at the top.

Writes, beside this script:
  hangar_wall_r.asset.json   the right wall: its inner face (the buffers' faces) at x = 0, the
                             pier toward +X, the front facing -Z; place it at x = +36 at yaw 0
  hangar_wall_l.asset.json   the same mirrored (inner face at x = 0, the pier toward -X); place
                             it at x = -36 at yaw 0 (mesh_at turns, it cannot mirror)
  art/wall_sign.png          the hall's sign (UAPC, the trial's hall number), drawn with the OFL
                             fonts in tools/fonts/
  cameras.json               the preview's views: the game's camera with the fighters near the
                             wall, the whole arena, and closer ones
Its floor footprint: x 0 to 8.8 (the right wall), z -6.5 to 14, the buffers z -5 to 1 at x 0-1.

Run from anywhere: python3 carts/mechexpo/models/hangar_wall/make_hangar_wall.py (Pillow).
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent/'hero'))
import mxpaint as P  # noqa: E402

FONTS = ROOT/'tools'/'fonts'
LIGHTING = {'direction': [0, 0.62, -0.78], 'ambient': 0.66}   # the mechs' light
POLICY = {'required': True, 'depth': True, 'perspective': True}

MATERIALS = {
    'steel':  {'color': '#66758a', 'texture': {
        'pattern': 'tile', 'colors': ['#66758a', '#4b586a', '#6e7d93'],
        'params': {'count': 2, 'grout': 1}, 'size': 16, 'projection': 'box', 'scale': [8, 8]}},
    'girder': {'color': '#55627a'},
    'rubber': {'color': '#2d3139'},
    'cap':    {'color': '#e8b800'},
    'hazard': {'color': '#f2c200', 'texture': {**P.hazard(['#f2c200', '#22242a']),
                                               'projection': 'box', 'scale': [1.0, 1.0]}},
    'sign':   {'color': '#1f3f78', 'texture': {'image': 'art/wall_sign.png', 'projection': 'fit'}},
    'lamp':   {'color': '#3a4150'},
    'light':  {'color': '#f2f6ff', 'class': 'emissive'},
}

FRONT_Z = -6.0          # the pier's front face
INNER_X = 0.8           # the pier's inner face; the buffers stand out from it to x = 0
HEIGHT = 26.0
WIDTH = 8.0
DEPTH = 20.0


def draw_sign(path):
    """48 x 64: UAPC over the hall's number, white and yellow on deep blue."""
    w, h, s = 48, 64, 8
    im = Image.new('RGB', (w*s, h*s), '#1f3f78')
    d = ImageDraw.Draw(im)
    bold = ImageFont.truetype(str(FONTS/'Figtree-BlackItalic.ttf'), 12*s)
    cond = ImageFont.truetype(str(FONTS/'SofiaSansCondensed-SemiBold.ttf'), 9*s)
    big = ImageFont.truetype(str(FONTS/'SofiaSansCondensed-SemiBold.ttf'), 30*s)
    d.rectangle([2*s, 2*s, (w-2)*s-1, (h-2)*s-1], outline='#f6f6f2', width=s)
    d.text((w*s/2, 13*s), 'UAPC', font=bold, fill='#f6f6f2', anchor='mm')
    d.rectangle([6*s, 21*s, (w-6)*s-1, 22*s-1], fill='#f2c200')
    d.text((w*s/2, 27*s), 'TRIAL HALL', font=cond, fill='#f6f6f2', anchor='mm')
    d.text((w*s/2, 47*s), '2', font=big, fill='#f2c200', anchor='mm')
    im = im.resize((w, h), Image.BOX).quantize(colors=8, method=Image.Quantize.MEDIANCUT,
                                                  dither=Image.Dither.NONE)
    im.convert('RGB').save(path)


def box(id_, size, mat, centre, faces=None, open_=None, decals=None):
    n = {'id': id_, 'op': 'box', 'size': [round(v, 4) for v in size], 'material': mat,
         'transform': {'translate': [round(v, 4) for v in centre]}}
    if faces:
        n['faces'] = faces
    if open_:
        n['open'] = open_
    if decals:
        n['decals'] = decals
    return n


def wall_nodes():
    """The right wall: the arena toward -X."""
    cx = INNER_X+WIDTH/2
    cz = FRONT_Z+DEPTH/2
    pier = box('pier', [WIDTH, HEIGHT, DEPTH], 'steel', [cx, HEIGHT/2, cz], open_=['bottom'],
               faces={'top': 'girder', 'front': 'girder', 'right': 'girder'},
               decals=[{'id': 'hall_sign', 'face': 'back', 'material': 'sign', 'size': [2.4, 3.2],
                        'at': [0.6, 0.0]}])
    # the corner the mechs hit: a hazard-striped post standing 15 cm proud of the front and the
    # inner face, and a kick plate along the front's foot
    post = box('corner_post', [0.8, 12.0, 0.8], 'hazard', [INNER_X+0.25, 6.0, FRONT_Z+0.25],
               open_=['bottom'], faces={'top': 'girder'})
    post_top = box('corner_post_top', [0.7, HEIGHT-12.4, 0.7], 'girder',
                   [INNER_X+0.25, 12.0+(HEIGHT-12.4)/2-0.2, FRONT_Z+0.25], open_=['bottom'])
    kick = box('kick_plate', [6.8, 1.4, 0.5], 'hazard', [5.1, 0.7, FRONT_Z+0.1],
               open_=['bottom', 'front'])
    ribs = [box(f'rib_{k}', [7.9, 0.6, 0.6], 'girder', [5.15, y, FRONT_Z+0.1],
                open_=['front'])
            for k, y in enumerate((9.0, 17.5))]
    # impact buffers at mech height, on the inner face, round the fight plane
    buffers = [box(f'buffer_{k}', [1.0, 2.6, 6.0], 'rubber', [INNER_X/2+0.1, y, -2.0],
                   faces={'top': 'cap', 'back': 'cap'}, open_=['right'])
               for k, y in enumerate((3.2, 7.4))]
    # a floodlight cantilevered over the arena from the top of the pier
    arm = box('lamp_arm', [4.4, 0.5, 0.6], 'girder', [INNER_X-1.6, HEIGHT-1.4, -1.0],
              open_=['right'])
    head = box('lamp_head', [1.8, 1.0, 1.4], 'lamp', [INNER_X-3.4, HEIGHT-2.1, -1.0],
               faces={'bottom': 'light'})
    return [pier, post, post_top, kick] + ribs + buffers + [arm, head]


def recipe(name, nodes):
    return {'format': 'mei-asset', 'version': 1, 'name': name,
            'budget': {'vertices': 512, 'triangles': 160},
            'lighting': LIGHTING, 'verification': POLICY,
            'materials': MATERIALS, 'nodes': nodes}


def cameras():
    """In the right wall's frame: the arena's middle is x = -36, the fight plane z = 0."""
    return [
        {'name': 'game_cornered', 'eye': [-12.0, 6.5, -30.0], 'target': [-12.0, 6.5, 0.0]},
        {'name': 'game_arena', 'eye': [-36.0, 8.0, -52.0], 'target': [-36.0, 8.0, 0.0]},
        {'name': 'near_inner', 'eye': [-14.0, 5.0, -14.0], 'target': [0.0, 5.0, -1.0]},
        {'name': 'front', 'eye': [4.0, 12.0, -34.0], 'target': [4.0, 12.0, 0.0]},
        {'name': 'top_corner', 'eye': [-10.0, 22.0, -12.0], 'target': [0.0, 22.0, -2.0]},
    ]


def write(path, data):
    path.write_text(json.dumps(data, indent=1)+'\n')


def main():
    draw_sign(HERE/'art'/'wall_sign.png')
    nodes = wall_nodes()
    write(HERE/'hangar_wall_r.asset.json', recipe('hangar_wall_r', nodes))
    write(HERE/'hangar_wall_l.asset.json', recipe('hangar_wall_l', [
        {'id': 'mirrored', 'op': 'group', 'children': wall_nodes(),
         'transform': {'scale': [-1, 1, 1]}}]))
    write(HERE/'cameras.json', cameras())


if __name__ == '__main__':
    main()
