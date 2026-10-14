#!/usr/bin/env python3
"""Mech Expo 2000: the container port's polygon props (the stage: stages.akr's port row; its
plane art and its layout are tools/gen_mechexpo_port.py's, which also packs what this writes).

The fight is seen side-on, so what reads is what faces the camera (-Z) and the faces toward the
arena seen at a slant. Every colour is graded for the port's sodium floodlights (G.sodium()).

Writes, beside this script:
  port_wall.asset.json   the closed side: a wall of 40-ft shipping containers (12.19 x 2.44 x
                         2.59 m) stacked two to four high in eleven rows from z = -8 to 19, their
                         long axis along x (x 0 to 12.19); the arena sees their doors (the -x
                         face, at x = 0) and, at a slant, the long sides of the front row and of
                         every container standing above the row in front of it, with their lines'
                         liveries and the makers' crates. Place it at x = +PORT_HALF at yaw 0
  port_kerb.asset.json   the open edge's coping: a low kerb along x = 0 to 0.45, z -20 to 20,
                         its top painted yellow, and two mooring bollards on it; place it at
                         x = -PORT_HALF
  art/wall_ends_K.png, art/wall_sides_K.png   each row's doors and sides, stacked (Pillow, the
                         OFL fonts in tools/fonts/ and the makers' emblems in models/*/)
  cameras.json           the game's views of the wall and of the open edge
  asset-preview.json     the preview's night colours

Run from anywhere: python3 carts/mechexpo/props/port/make_port.py (Pillow).
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MODELS = HERE.parents[1]/'models'
sys.path.insert(0, str(ROOT/'tools'))
import gen_mechexpo_port as G  # noqa: E402  (the layout, the liveries, the sodium grading)

FONTS = ROOT/'tools'/'fonts'
LIGHTING = {'direction': [-0.45, 0.6, -0.66], 'ambient': 0.6}  # the floodlights: above, in front, the arena's side
POLICY = {'required': True, 'depth': True, 'perspective': True}

CL, CW, CH = 12.19, 2.44, 2.59     # a 40-ft container
GAP = 0.1                          # between rows
Z0 = -8.0                          # the front row's front
# the rows, front to back: each a stack, bottom to top (a line's or a maker's key)
ROWS = [
    ['kuroshio', 'momentum', 'lease'],
    ['nordvik', 'trident'],
    ['hokusei', 'amber', 'umbral', 'meridian'],
    ['trident', 'kuroshio', 'lease', 'raiko'],
    ['lease', 'hokusei', 'nordvik'],
    ['amber', 'meridian'],
    ['kuroshio', 'trident', 'heartland'],
    ['meridian', 'lease', 'hokusei', 'binary'],
    ['nordvik', 'amber'],
    ['hokusei', 'kuroshio', 'trident'],
    ['lease', 'nordvik', 'meridian', 'amber'],
]
LIVERY = {k: (name, body, ink, mark) for k, name, body, ink, mark in G.LINES}
LIVERY.update({k: (name, body, ink, 'emblem:' + path) for k, name, body, ink, path in G.MAKERS})
SIDE_W, SIDE_H = 64, 16            # texels a container's long side
END_W, END_H = 16, 16              # and its doors


def rgb(c):
    return G.sodium(c)


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def mark(d, kind, x, y, s, ink):
    """A line's mark, s texels square at (x, y)."""
    if kind == 'wave':
        for i in range(s):
            yy = y + s // 2 + int(round((s / 4) * math.sin(i / s * 6.28)))
            d.rectangle([x + i, yy - 1, x + i, yy], fill=ink)
    elif kind == 'trident':
        d.rectangle([x + s // 2, y, x + s // 2, y + s - 1], fill=ink)
        d.rectangle([x + 1, y + s // 3, x + s - 2, y + s // 3], fill=ink)
        for xx in (x + 1, x + s - 2):
            d.rectangle([xx, y, xx, y + s // 3], fill=ink)
    elif kind == 'star':
        c = s // 2
        d.polygon([(x + c, y), (x + c + 2, y + c - 1), (x + s - 1, y + c), (x + c + 2, y + c + 1),
                   (x + c, y + s - 1), (x + c - 2, y + c + 1), (x, y + c), (x + c - 2, y + c - 1)], fill=ink)
    elif kind == 'bar':
        d.rectangle([x, y + 2, x + s - 1, y + 4], fill=ink)
        d.rectangle([x, y + s - 5, x + s - 1, y + s - 3], fill=ink)
    elif kind == 'cross':
        d.rectangle([x, y + s // 2 - 1, x + s - 1, y + s // 2], fill=ink)
        d.rectangle([x + s // 3, y, x + s // 3 + 1, y + s - 1], fill=ink)
    elif kind == 'ring':
        d.ellipse([x, y, x + s - 1, y + s - 1], outline=ink, width=2)


def draw_side(key, worn):
    """A container's long side, SIDE_W x SIDE_H: corrugated, its corner posts and rails, the
    line's mark and name (or a maker's emblem and name), weathered."""
    name, body, ink, mk = LIVERY[key]
    b = rgb(body)
    im = Image.new('RGB', (SIDE_W, SIDE_H), b)
    d = ImageDraw.Draw(im)
    d.fontmode = '1'
    for x in range(2, SIDE_W - 2, 2):                       # the corrugation
        d.rectangle([x, 1, x, SIDE_H - 2], fill=shade(b, 0.82))
    d.rectangle([0, 0, SIDE_W - 1, 0], fill=shade(b, 0.62))
    d.rectangle([0, SIDE_H - 1, SIDE_W - 1, SIDE_H - 1], fill=shade(b, 0.5))
    for x in (0, SIDE_W - 2):
        d.rectangle([x, 0, x + 1, SIDE_H - 1], fill=shade(b, 0.6))
    inkc = rgb(ink)
    f = ImageFont.truetype(str(FONTS/'SofiaSansCondensed-SemiBold.ttf'), 11)
    if mk and mk.startswith('emblem:'):
        em = Image.open(MODELS/mk[7:]).convert('RGBA').resize((12, 12), Image.LANCZOS)
        px = em.load()
        for yy in range(12):
            for xx in range(12):
                r, g, bb, a = px[xx, yy]
                px[xx, yy] = G.sodium((r, g, bb), 1.0, 0.1) + (255 if a > 140 else 0,)
        im.paste(em, (4, 2), em)
        d.text((38, 8), name, font=f, fill=inkc, anchor='mm')
    elif mk:
        mark(d, mk, 4, 3, 10, inkc)
        d.text((38, 8), name, font=f, fill=inkc, anchor='mm')
    else:                                                   # a leasing box: its number, small
        f2 = ImageFont.truetype(str(FONTS/'SofiaSansCondensed-SemiBold.ttf'), 7)
        d.text((SIDE_W - 6, 4), name, font=f2, fill=inkc, anchor='rm')
    # rust and grime: a few darker streaks under the top rail, scuffs along the bottom
    for k in range(5):
        x = 3 + (k * 13 + worn * 7) % (SIDE_W - 6)
        d.rectangle([x, 1, x, 3 + (k + worn) % 3], fill=shade(b, 0.55))
    d.rectangle([3 + worn * 5 % 20, SIDE_H - 3, 12 + worn * 5 % 20, SIDE_H - 2], fill=shade(b, 0.65))
    return im


def draw_end(key):
    """A container's doors, END_W x END_H: two leaves, four locking bars, the header and sill."""
    name, body, ink, mk = LIVERY[key]
    b = rgb(body)
    im = Image.new('RGB', (END_W, END_H), shade(b, 0.92))
    d = ImageDraw.Draw(im)
    for x in (0, END_W - 1):
        d.rectangle([x, 0, x, END_H - 1], fill=shade(b, 0.55))
    d.rectangle([0, 0, END_W - 1, 1], fill=shade(b, 0.6))
    d.rectangle([0, END_H - 1, END_W - 1, END_H - 1], fill=shade(b, 0.45))
    d.rectangle([END_W // 2, 2, END_W // 2, END_H - 2], fill=shade(b, 0.5))     # the leaves' join
    for x in (3, 6, 9, 12):
        d.rectangle([x, 2, x, END_H - 2], fill=G.sodium('#b8b4ac', 0.85))         # locking bars
    for x in (3, 6, 9, 12):
        d.rectangle([x - 1, 9, x, 10], fill=G.sodium('#d8d0c0'))                  # their handles
    d.rectangle([2, 3, 6, 4], fill=rgb(ink))                                       # the line's mark
    return im


def stack_texture(keys, side, worn0):
    """A row's stacked doors (side False) or long sides (True), bottom container at the bottom."""
    w, h = (SIDE_W, SIDE_H) if side else (END_W, END_H)
    im = Image.new('RGB', (w, h * len(keys)))
    for i, k in enumerate(keys):
        tile = draw_side(k, worn0 + i) if side else draw_end(k)
        im.paste(tile, (0, h * (len(keys) - 1 - i)))
    return im


def save4(im, path):
    im.quantize(colors=15, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert('RGB').save(path)


def box(id_, size, mat, centre, faces=None, open_=None):
    n = {'id': id_, 'op': 'box', 'size': [round(v, 4) for v in size], 'material': mat,
         'transform': {'translate': [round(v, 4) for v in centre]}}
    if faces:
        n['faces'] = faces
    if open_:
        n['open'] = open_
    return n


def wall():
    """The container wall: a box a row (its doors on the -x face, its sides on the -z face where
    they show, its top where it is below the eye), each in a texture of its stacked containers."""
    nodes, mats = [], {}
    art = HERE/'art'
    prev = 0
    for r, keys in enumerate(ROWS):
        n = len(keys)
        z0 = Z0 + r * (CW + GAP)
        h = n * CH
        save4(stack_texture(keys, False, r), art/f'wall_ends_{r}.png')
        mats[f'ends_{r}'] = {'color': G.shex(LIVERY[keys[0]][1]),
                             'texture': {'image': f'art/wall_ends_{r}.png', 'projection': 'fit'}}
        faces = {'left': f'ends_{r}'}
        opened = ['bottom', 'right', 'front']
        if n > prev:                                    # its side shows above the row in front
            save4(stack_texture(keys, True, r), art/f'wall_sides_{r}.png')
            mats[f'sides_{r}'] = {'color': G.shex(LIVERY[keys[0]][1]),
                                  'texture': {'image': f'art/wall_sides_{r}.png', 'projection': 'fit'}}
            faces['back'] = f'sides_{r}'
        else:
            opened.append('back')
        if n <= 3:                                      # the eye is 6.5 m up (a jump lifts it)
            mats[f'roof_{r}'] = {'color': G.shex(LIVERY[keys[-1]][1], 0.7)}
            faces['top'] = f'roof_{r}'
        else:
            opened.append('top')
        nodes.append(box(f'row_{r}', [CL, h, CW], f'ends_{r}', [CL / 2, h / 2, z0 + CW / 2],
                         faces=faces, open_=opened))
        prev = n
    return nodes, mats


def kerb():
    """The open edge's coping (x 0 to 0.45 inside the edge, 0.3 m high) and two bollards."""
    z0, z1 = -12.0, G.DECK_FAR - 0.02
    mats = {'coping': {'color': G.shex('#a49a8a', 0.8)},
            'paint': {'color': G.shex('#e8b830')},
            'iron': {'color': G.shex('#3a3634')},
            'cap': {'color': G.shex('#e8b830', 0.9)}}
    nodes = [box('kerb', [0.45, 0.3, z1 - z0], 'coping', [0.225, 0.15, (z0 + z1) / 2],
                 faces={'top': 'paint'}, open_=['bottom', 'left', 'back', 'front'])]
    for i, z in enumerate((-10.0, 6.0)):
        nodes.append(box(f'bollard_{i}', [0.7, 0.75, 0.7], 'iron', [0.9, 0.37, z], open_=['bottom', 'top']))
        nodes.append(box(f'bollard_cap_{i}', [1.05, 0.28, 1.05], 'iron', [0.9, 0.86, z],
                         faces={'top': 'cap'}, open_=['bottom']))
    return nodes, mats


def recipe(name, nodes, mats, tris):
    return {'format': 'mei-asset', 'version': 1, 'name': name,
            'budget': {'vertices': 512, 'triangles': tris},
            'lighting': LIGHTING, 'verification': POLICY,
            'materials': mats, 'nodes': nodes}


def cameras():
    """In the wall's frame: the arena toward -X (its middle at x = -PORT_HALF), the fight plane z = 0."""
    H = G.PORT_HALF
    return [
        {'name': 'game_cornered', 'eye': [-12.0, 6.5, -30.0], 'target': [-12.0, 6.5, 0.0]},
        {'name': 'game_arena', 'eye': [-H, 8.0, -52.0], 'target': [-H, 8.0, 0.0]},
        {'name': 'near_inner', 'eye': [-14.0, 5.0, -14.0], 'target': [0.0, 5.0, -1.0]},
        {'name': 'kerb', 'eye': [8.0, 4.0, -16.0], 'target': [0.0, 0.5, 0.0]},
    ]


def write(path, data):
    path.write_text(json.dumps(data, indent=1) + '\n')


def main():
    (HERE/'art').mkdir(exist_ok=True)
    wn, wm = wall()
    write(HERE/'port_wall.asset.json', recipe('stage_port_wall', wn, wm, 120))
    kn, km = kerb()
    write(HERE/'port_kerb.asset.json', recipe('stage_port_kerb', kn, km, 48))
    write(HERE/'cameras.json', cameras())
    write(HERE/'asset-preview.json', {'background': ['#05060c', '#3e2c24'], 'ground': '#3a2f24'})


if __name__ == '__main__':
    main()
