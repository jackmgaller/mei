#!/usr/bin/env python3
"""Mech Expo 2000: the rooftop showcase's polygon props (the stage: stages.akr's rooftop row;
its plane art is tools/gen_mechexpo_rooftop.py's, which sets the stage's half-width).

The fight is seen side-on, so what reads is what faces the camera (-Z) and the faces toward the
arena seen at a slant, as with the hangar's walls (models/hangar_wall/).

Writes, beside this script:
  roof_stairwell.asset.json  the closed side: the stairwell and freight lift's housing, 10 m deep
                             (x 0 to -10), 11 m tall, z -9 to 12, its face toward the arena at
                             x = 0 with the freight lift's door (the mechs came up in it) and its
                             lit sign, a hazard-striped corner post, a floodlight cantilevered
                             over the deck, a water tank and an aerial with a red light on the
                             roof; place it at x = -ROOF_HALF at yaw 0
  roof_parapet.asset.json    the deck's far edge: a concrete parapet with a steel rail along
                             z = 0 from x = -60 to +ROOF_HALF (the open edge), three floodlight
                             masts behind it facing the deck, and a hazard-striped post with a
                             red light at the open corner; place it at (0, 0, DECK_FAR)
  roof_kerb.asset.json       the open edge's lip: a low hazard-striped kerb along x = -0.4 to 0,
                             z -24 to 30; place it at x = +ROOF_HALF
  art/stair_door.png, art/stair_sign.png   the freight lift's door and the sign over it, drawn
                             with the OFL fonts in tools/fonts/
  cameras.json               the game's views of the housing and of the open corner

Run from anywhere: python3 carts/mechexpo/models/rooftop/make_rooftop.py (Pillow).
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[1]/'models'/'hero'))
sys.path.insert(0, str(ROOT/'tools'))
import mxpaint as P  # noqa: E402
import gen_mechexpo_rooftop as R  # noqa: E402  (the stage's half-width and the deck's far edge)

FONTS = ROOT/'tools'/'fonts'
LIGHTING = {'direction': [0, 0.62, -0.78], 'ambient': 0.66}   # the mechs' light
POLICY = {'required': True, 'depth': True, 'perspective': True}
HALF = R.ROOF_HALF
FAR = R.DECK_FAR

MATERIALS = {
    'concrete': {'color': '#6a7488', 'texture': {
        'pattern': 'tile', 'colors': ['#6a7488', '#5a6478', '#727c90'],
        'params': {'count': 2, 'grout': 1}, 'size': 16, 'projection': 'box', 'scale': [6, 6]}},
    'dark':     {'color': '#3e4658'},
    'cap':      {'color': '#9aa4b6'},
    'steel':    {'color': '#55607a'},
    'tank':     {'color': '#7e889c', 'smooth': True},
    'hazard':   {'color': '#f2c200', 'texture': {**P.hazard(['#f2c200', '#22242a']),
                                                 'projection': 'box', 'scale': [1.0, 1.0]}},
    'door':     {'color': '#4e5870', 'texture': {'image': 'art/stair_door.png', 'projection': 'fit'}},
    'sign':     {'color': '#1f3f78', 'class': 'emissive',
                 'texture': {'image': 'art/stair_sign.png', 'projection': 'fit'}},
    'lamp':     {'color': '#3a4150'},
    'light':    {'color': '#f2f6ff', 'class': 'emissive'},
    'red':      {'color': '#ff3a2a', 'class': 'emissive'},
}


def draw_door(path):
    """32 x 40: the freight lift's steel door, horizontal slats, a yellow and black frame."""
    w, h, s = 32, 40, 8
    im = Image.new('RGB', (w*s, h*s), '#4e5870')
    d = ImageDraw.Draw(im)
    for k in range(0, h*s, 3*s):
        d.rectangle([3*s, k, (w-3)*s-1, k+s-1], fill='#5c6882')
    # the frame's stripes
    for k in range(-h*s, (w+h)*s, 4*s):
        d.polygon([(k, 0), (k+2*s, 0), (k+2*s-h*s, h*s), (k-h*s, h*s)], fill='#f2c200')
    d.rectangle([3*s, 3*s, (w-3)*s-1, h*s-1], fill='#4e5870')
    for k in range(3*s, h*s, 3*s):
        d.rectangle([3*s, k, (w-3)*s-1, k+s-1], fill='#5c6882')
    d.rectangle([w*s//2-s//2, 3*s, w*s//2+s//2-1, h*s-1], fill='#2e3446')      # the leaves' join
    bold = ImageFont.truetype(str(FONTS/'Figtree-BlackItalic.ttf'), 9*s)
    d.text((w*s/2, 13*s), 'R1', font=bold, fill='#f2c200', anchor='mm')
    im = im.resize((w, h), Image.BOX).quantize(colors=8, method=Image.Quantize.MEDIANCUT,
                                                  dither=Image.Dither.NONE)
    im.convert('RGB').save(path)


def draw_sign(path):
    """64 x 20: the lit sign over the door, white on the expo's blue."""
    w, h, s = 64, 20, 8
    im = Image.new('RGB', (w*s, h*s), '#1f3f78')
    d = ImageDraw.Draw(im)
    bold = ImageFont.truetype(str(FONTS/'Figtree-BlackItalic.ttf'), 10*s)
    cond = ImageFont.truetype(str(FONTS/'SofiaSansCondensed-SemiBold.ttf'), 6*s)
    d.rectangle([s, s, (w-1)*s-1, (h-1)*s-1], outline='#f6f6f2', width=s)
    d.text((22*s, 10*s), 'R1', font=bold, fill='#f2c200', anchor='mm')
    d.text((44*s, 7*s), 'FREIGHT', font=cond, fill='#f6f6f2', anchor='mm')
    d.text((44*s, 13*s), 'LIFT', font=cond, fill='#f6f6f2', anchor='mm')
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


def stairwell_nodes():
    """The housing: its face toward the arena at x = 0, the block toward -X."""
    D, H, Z0, Z1 = 10.0, 11.0, -9.0, 12.0
    zc = (Z0+Z1)/2
    door_z, door_w, door_h = -1.0, 7.0, 8.0
    block = box('housing', [D, H, Z1-Z0], 'concrete', [-D/2, H/2, zc], open_=['bottom'],
                faces={'top': 'cap', 'back': 'dark'},
                decals=[{'id': 'lift_door', 'face': 'right', 'material': 'door',
                         'size': [door_w, door_h], 'at': [door_z-zc, door_h/2-H/2+0.01]},
                        {'id': 'lift_sign', 'face': 'right', 'material': 'sign',
                         'size': [5.0, 1.6], 'at': [door_z-zc, door_h+1.2-H/2]}])
    post = box('corner_post', [0.8, 11.6, 0.8], 'hazard', [0.25, 5.8, Z0+0.25],
               open_=['bottom'], faces={'top': 'steel'})
    tank = {'id': 'water_tank', 'op': 'cylinder', 'radius': 2.0, 'height': 3.0, 'segments': 8,
            'material': 'tank', 'transform': {'translate': [-6.0, H+1.49, 6.0]}}
    aerial = box('aerial', [0.25, 6.0, 0.25], 'steel', [-2.0, H+2.99, -6.0], open_=['bottom'])
    beacon = box('beacon', [0.5, 0.5, 0.5], 'red', [-2.0, H+6.2, -6.0])
    arm = box('lamp_arm', [4.4, 0.5, 0.6], 'steel', [1.6, H-0.6, -1.0], open_=['left'])
    head = box('lamp_head', [1.8, 1.0, 1.4], 'lamp', [3.4, H-1.3, -1.0], faces={'bottom': 'light'})
    return [block, post, tank, aerial, beacon, arm, head]


def parapet_nodes():
    """The far edge: the parapet's face toward the deck at z = 0, from x = -60 to +HALF."""
    x0, x1 = -60.0, HALF
    L = x1 - x0
    xc = (x0+x1)/2
    wall = box('parapet', [L, 1.3, 0.5], 'concrete', [xc, 0.65, 0.25], open_=['bottom'],
               faces={'top': 'cap'})
    rail = box('rail', [L-0.8, 0.18, 0.18], 'steel', [xc-0.4, 2.3, 0.3])
    nodes = [wall, rail]
    for k, x in enumerate((-36.0, -12.0, 12.0)):
        nodes.append(box(f'mast_{k}', [0.45, 14.8, 0.45], 'steel', [x, 7.4, 1.3], open_=['bottom']))
        nodes.append(box(f'mast_head_{k}', [3.2, 1.3, 1.0], 'lamp', [x, 15.2, 0.7],
                         faces={'back': 'light'}))
        nodes.append(box(f'rail_post_{k}', [0.2, 1.0, 0.1], 'steel', [x+2.0, 1.75, 0.3]))
    # the open corner: a hazard-striped post with a red warning light on it
    nodes.append(box('corner_post', [0.7, 2.4, 0.7], 'hazard', [x1-0.3, 1.2, 0.25], open_=['bottom'],
                     faces={'top': 'steel'}))
    nodes.append(box('corner_light', [0.4, 0.4, 0.4], 'red', [x1-0.3, 2.62, 0.25]))
    return nodes


def kerb_nodes():
    """The open edge's lip: x = -0.4 to 0, the deck's near edge to the parapet."""
    z0, z1 = R.DECK_NEAR, FAR - 0.02
    return [box('kerb', [0.4, 0.35, z1-z0], 'hazard', [-0.2, 0.175, (z0+z1)/2], open_=['bottom'],
                faces={'top': 'cap'})]


def recipe(name, nodes, tris):
    return {'format': 'mei-asset', 'version': 1, 'name': name,
            'budget': {'vertices': 512, 'triangles': tris},
            'lighting': LIGHTING, 'verification': POLICY,
            'materials': MATERIALS, 'nodes': nodes}


def cameras():
    """In the housing's frame: the arena toward +X (its middle at x = HALF), the fight plane z = 0."""
    return [
        {'name': 'game_cornered', 'eye': [12.0, 6.5, -30.0], 'target': [12.0, 6.5, 0.0]},
        {'name': 'game_arena', 'eye': [HALF, 8.0, -52.0], 'target': [HALF, 8.0, 0.0]},
        {'name': 'near_inner', 'eye': [14.0, 5.0, -14.0], 'target': [0.0, 5.0, -1.0]},
        {'name': 'top_corner', 'eye': [10.0, 16.0, -14.0], 'target': [0.0, 12.0, -2.0]},
    ]


def write(path, data):
    path.write_text(json.dumps(data, indent=1)+'\n')


def main():
    (HERE/'art').mkdir(exist_ok=True)
    draw_door(HERE/'art'/'stair_door.png')
    draw_sign(HERE/'art'/'stair_sign.png')
    write(HERE/'roof_stairwell.asset.json', recipe('stage_roof_stairwell', stairwell_nodes(), 260))
    write(HERE/'roof_parapet.asset.json', recipe('stage_roof_parapet', parapet_nodes(), 200))
    write(HERE/'roof_kerb.asset.json', recipe('stage_roof_kerb', kerb_nodes(), 40))
    write(HERE/'cameras.json', cameras())


if __name__ == '__main__':
    main()
