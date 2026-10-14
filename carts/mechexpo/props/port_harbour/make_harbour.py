#!/usr/bin/env python3
"""Mech Expo 2000: the container port's harbour in polygons (the stage: stages.akr's port row;
its plane art, the far harbour and the Bay Bridge behind all this, and its layout are
tools/gen_mechexpo_port.py's, which also packs what this writes).

Honmoku pier, berth D-5, at night. The fight plane is z = 0, the apron's BG2 part ends at the
landside crane rail (z = DECK_FAR = 20), the waterside rail is at z = 48 and the berth's face at
z = 52; the water is WATER_Y below the apron. Every recipe is one mesh in the world's coordinates,
drawn at the origin into PL, behind the apron (BG2): what is under the apron is hidden by it.
Every colour is graded for the sodium floodlights (G.sodium()). What the camera never sees is
not made: the camera's eye is 6.5 m up and its x runs -27.5 to 18.5, so tops above the eye,
faces toward +z and the far sides of things are left open.

Writes, beside this script:
  port_water.asset.json    the harbour's water past the open edge (x -400 to -24, z -18 to 160:
                           6 m under the apron, so a mech falling past the lip sinks into it),
                           black, and the reflections of the ship's and the cranes' lights on it
  port_apron.asset.json    the apron past the landside rail (z 20 to 52, x -30 to 90): asphalt,
                           the waterside rail, the berth's coping and the open edge's; the yard's
                           ground behind the container wall (x 60 to 300)
  port_crane_a.asset.json  gantry crane A, Honmoku's light blue, over the ship's stern bays
                           (legs at x 11 and 29): legs, bogies, portal, sill girders, the boom
                           over the ship with its floodlights, the apex, the stays, the
                           machinery house, the trolley and its cab, a container on the spreader;
                           red aircraft lights
  port_crane_b.asset.json  gantry crane B, white with a red and white boom and apex (legs at x 49
                           and 67), standing idle with its boom raised; less detail (it is seen
                           least): no bogies, backstays, machinery house, floodlights or trolley
  port_ship.asset.json     the container ship KUROSHIO SPIRIT moored at the berth (x -20 to 270,
                           z 54 to 86): her hull, the accommodation block and bridge at the stern,
                           her funnel, and her deck cargo stacked four to seven high
  port_yard.asset.json     the yard behind the container wall: stacks three to five high, and
                           two floodlight masts (in the yard by the wall, and on the far apron
                           at the quay's corner) with their sodium glow
  art/*.png                the textures (Pillow; the containers' liveries are make_port.py's)
  cameras.json             the game's views of the harbour, for the Asset Kit's preview

Run from anywhere: python3 carts/mechexpo/props/port_harbour/make_harbour.py (Pillow, NumPy).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT/'tools'))
sys.path.insert(0, str(HERE.parent/'port'))
import gen_mechexpo_port as G  # noqa: E402  (the layout, the sodium grading)
import make_port as P  # noqa: E402  (the containers' liveries)

FONTS = ROOT/'tools'/'fonts'
POLICY = {'required': True, 'depth': True, 'perspective': True}
FLOOD = {'direction': [0.0, -0.75, -0.6], 'ambient': 0.42}     # the cranes, lit from the quay below
FLAT = {'mode': 'vertical', 'ambient': 0.62}

WY = G.WATER_Y
HALF = G.PORT_HALF
QF = G.QUAY_FAR
SHIP_X0, SHIP_X1 = -20.0, 270.0     # the ship's stern (the transom) and bow
SHIP_Z0, SHIP_Z1 = 54.0, 86.0       # her side toward the berth, and her far side
SHIP_DECK = 10.0                    # her main deck, above the apron


def hexs(c):
    return '#%02x%02x%02x' % tuple(c)


def sod(c, lit=1.0, grey=0.22):
    return G.shex(c, lit, grey)


def box(id_, size, mat, centre, faces=None, open_=None, rot=None):
    t = {'translate': [round(v, 4) for v in centre]}
    if rot:
        t['rotate'] = rot
    n = {'id': id_, 'op': 'box', 'size': [round(v, 4) for v in size], 'material': mat, 'transform': t}
    if faces:
        n['faces'] = faces
    if open_:
        n['open'] = open_
    return n


def span(id_, a, b, w, mat, keep=('back', 'bottom')):
    """A beam w x w from point a to point b (in the y-z plane, at a's x), as a box rotated about
    x; only the sides in `keep` are made."""
    dy, dz = b[1] - a[1], b[2] - a[2]
    ln = math.hypot(dy, dz)
    ang = math.degrees(math.atan2(dy, dz))        # tilts +z toward +y
    mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2]
    sides = ['top', 'bottom', 'left', 'right', 'back', 'front']
    return box(id_, [w, w, ln], mat, mid, open_=[s for s in sides if s not in keep], rot=[-ang, 0, 0])


def save4(im, path, colours=15):
    im.convert('RGB').quantize(colors=colours, method=Image.Quantize.MEDIANCUT,
                               dither=Image.Dither.NONE).convert('RGB').save(path)


# ---- textures

def mosaic(keys, cols, rows, cw, ch, side, seed):
    """Containers stacked `rows` high and `cols` bays across, each cw x ch texels (their sides
    or their doors, from make_port.py's liveries, scaled down), a dark gap between bays."""
    rng = np.random.default_rng(seed)
    im = Image.new('RGB', (cw * cols, ch * rows))
    for c in range(cols):
        for r in range(rows):
            k = keys[int(rng.integers(0, len(keys)))]
            t = P.draw_side(k, r + c) if side else P.draw_end(k)
            im.paste(t.resize((cw, ch), Image.BOX), (c * cw, r * ch))
        if side:
            ImageDraw.Draw(im).rectangle([c * cw + cw - 1, 0, c * cw + cw - 1, ch * rows - 1],
                                         fill=G.sodium('#141210'))
    return im


SHIP_KEYS = ['kuroshio', 'kuroshio', 'kuroshio', 'trident', 'hokusei', 'amber', 'nordvik', 'meridian',
             'lease', 'lease']
YARD_KEYS = ['trident', 'hokusei', 'amber', 'nordvik', 'meridian', 'lease', 'lease', 'kuroshio']


def draw_hull(path, w, h, name):
    """The hull's side for one stretch: navy plating, its seams, a white sheer line, the boot
    topping at the waterline; `name` in white letters (or none)."""
    navy = G.sodium('#22385e', 0.95, 0.15)
    im = Image.new('RGB', (w, h), navy)
    d = ImageDraw.Draw(im)
    d.fontmode = '1'
    d.rectangle([0, 0, w - 1, 0], fill=G.sodium('#e8e4dc', 0.9))               # the sheer line
    d.rectangle([0, 1, w - 1, 1], fill=G.sodium('#1a2a48'))
    for x in range(5, w, 9):                                                     # plate seams
        d.rectangle([x, 2, x, h - 3], fill=G.sodium('#1c3052', 0.95))
    d.rectangle([0, h * 2 // 3, w - 1, h * 2 // 3], fill=G.sodium('#1c3052', 0.95))
    d.rectangle([0, h - 2, w - 1, h - 1], fill=G.sodium('#8a2a26', 0.8))        # boot topping
    for x in range(12, w, 40):                                                   # deck lamps on the rail
        d.rectangle([x, 0, x + 1, 0], fill=G.sodium('#fff4d8'))
    if name:
        f = ImageFont.truetype(str(FONTS/'Figtree-Bold.ttf'), h - 6)
        d.text((w // 2, h // 2 + 1), name, font=f, fill=G.sodium('#f0f0ec', 0.92), anchor='mm')
    save4(im, path, 8)


def draw_house(path, w, h, storeys, seed, bridge=True):
    """The accommodation block's face: white, `storeys` rows of windows (some lit), the bridge's
    window band at the top."""
    rng = np.random.default_rng(seed)
    wall = G.sodium('#d8d6d0', 0.78, 0.1)
    im = Image.new('RGB', (w, h), wall)
    d = ImageDraw.Draw(im)
    sh = h / storeys
    for s in range(storeys):
        y = int(s * sh)
        d.rectangle([0, y, w - 1, y], fill=G.sodium('#a8a49c', 0.7))
        top = s == 0 and bridge
        for x in range(2, w - 2, 3):
            lit = rng.random() < (0.85 if top else 0.3)
            c = G.sodium('#ffe8b0', 1.0, 0.0) if lit else G.sodium('#2a2e36', 0.9)
            if top:
                d.rectangle([x - 1, y + 2, x + 1, y + int(sh) - 2], fill=c)
            else:
                d.rectangle([x, y + 2, x, y + 3], fill=c)
    save4(im, path, 10)


def draw_funnel(path):
    """The funnel's side: the line's colours, KUROSHIO's white wave on a blue band."""
    im = Image.new('RGB', (16, 24), G.sodium('#d8d6d0', 0.8, 0.1))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 15, 3], fill=G.sodium('#141414'))
    d.rectangle([0, 6, 15, 17], fill=G.sodium('#2a4a7c', 0.9, 0.1))
    for x in range(2, 14):
        y = 11 + int(round(2 * math.sin((x - 2) / 12 * 6.28)))
        d.rectangle([x, y, x, y + 1], fill=G.sodium('#f0f0ec'))
    save4(im, path, 6)


def draw_asphalt(path):
    """32 x 32, 8 m: the apron's asphalt at the BG2 apron's tones near the rail, a slab seam."""
    rng = np.random.default_rng(52)
    lv = rng.random((32, 32)) * 1.6 + 4.2
    lv[rng.random((32, 32)) < 0.05] -= 1.5
    idx = np.clip(np.round(lv).astype(int), 0, 9)
    a = np.array(G.ASPHALT, np.uint8)[idx]
    a[0, :] = G.ASPHALT[2]
    a[:, 0] = G.ASPHALT[2]
    Image.fromarray(a).save(path)


def draw_streak(path):
    """8 x 32: a light's reflection broken by ripples (the rest a hole)."""
    rng = np.random.default_rng(9)
    im = Image.new('RGBA', (8, 32), (0, 0, 0, 0))
    px = im.load()
    for y in range(32):
        w = int(rng.integers(1, 5))
        x0 = int(rng.integers(0, 8 - w + 1))
        if rng.random() < 0.7:
            for x in range(x0, x0 + w):
                px[x, y] = G.sodium('#f0b860', 0.9, 0.0) + (255,)
    im.save(path)


def draw_ripples(path):
    """32 x 32, 16 m: black water, its ripples catching the floodlights: short dashes along x."""
    rng = np.random.default_rng(15)
    a = np.zeros((32, 32, 3), np.uint8)
    a[:] = (6, 8, 13)
    for _ in range(26):
        x, y, w = int(rng.integers(0, 32)), int(rng.integers(0, 32)), int(rng.integers(2, 6))
        c = (22, 22, 26) if rng.random() < 0.7 else G.sodium('#5a4028', 0.9, 0.0)
        for k in range(w):
            a[y, (x + k) % 32] = c
    Image.fromarray(a).save(path)


def draw_halo(path):
    """16 x 16: a floodlight's glow, for an additive card (the corners a hole)."""
    im = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    px = im.load()
    for y in range(16):
        for x in range(16):
            r = math.hypot(x - 7.5, y - 7.5) / 8.0
            if r < 1.0:
                k = (1 - r) ** 1.6
                px[x, y] = tuple(int(c * k) for c in (255, 170, 80)) + (255,)
    im.save(path)


def write_textures():
    art = HERE/'art'
    art.mkdir(exist_ok=True)
    save4(mosaic(SHIP_KEYS, 2, 4, 32, 8, True, 3), art/'cargo_sides.png')
    save4(mosaic(SHIP_KEYS, 4, 4, 8, 8, False, 4), art/'cargo_ends.png')
    save4(mosaic(YARD_KEYS, 2, 4, 32, 8, True, 5), art/'yard_sides.png')
    draw_hull(art/'hull_stern.png', 128, 18, None)
    draw_hull(art/'hull_name.png', 160, 18, 'KUROSHIO')
    draw_hull(art/'hull_bow.png', 160, 18, None)
    draw_house(art/'house_front.png', 32, 64, 11, 7)
    draw_house(art/'house_side.png', 56, 64, 11, 8)
    draw_funnel(art/'funnel.png')
    draw_asphalt(art/'asphalt.png')
    draw_streak(art/'streak.png')
    draw_ripples(art/'ripples.png')
    draw_halo(art/'halo.png')
    save4(P.draw_side('amber', 2).resize((32, 8), Image.BOX), art/'hanging.png', 10)


# ---- the recipes

def recipe(name, nodes, mats, tris, lighting=None):
    keep = used(nodes)
    return {'format': 'mei-asset', 'version': 1, 'name': name,
            'budget': {'vertices': 2000, 'triangles': tris},
            'lighting': lighting or FLAT, 'verification': POLICY,
            'materials': {k: v for k, v in mats.items() if k in keep}, 'nodes': nodes}


def used(nodes):
    names = set()
    for n in nodes:
        if 'material' in n:
            names.add(n['material'])
        names.update(n.get('faces', {}).values())
        names |= used(n.get('children', []))
    return names


def emissive(c, tex=None):
    m = {'color': c, 'class': 'emissive'}
    if tex:
        m['texture'] = tex
    return m


def water():
    mats = {'water': emissive('#06080d', {'image': 'art/ripples.png', 'projection': 'planar', 'axis': 'y',
                                          'scale': [32.0, 32.0]}),
            'streak': emissive('#f0b860', {'image': 'art/streak.png', 'projection': 'planar', 'axis': 'y',
                                           'scale': [1.6, 12.0]})}
    mats['streak']['blend'] = 'add'
    flat = ['bottom', 'left', 'right', 'back', 'front']
    # in two pieces: only the near one (z -18 to -6) ever reaches behind the eye (the camera's eye is
    # 16 to 31 m in front of the fight plane), so only its two triangles are clipped
    nodes = [box('water_near', [376.0, 1.0, 12.0], 'water', [-400 + 188.0, WY - 0.5, -12.0], open_=flat),
             box('water', [376.0, 1.0, 166.0], 'water', [-400 + 188.0, WY - 0.5, 77.0], open_=flat)]
    # reflections: under the ship's stern lights and the near crane's floodlights (seen past the
    # quay's corner), and the bridge's near tower further out
    for i, (x, z0, z1) in enumerate([(-22.5, 58.0, 130.0), (-31.0, 54.0, 140.0), (-60.0, 90.0, 158.0)]):
        nodes.append(box(f'streak_{i}', [1.6, 0.1, z1 - z0], 'streak', [x, WY + 0.05, (z0 + z1) / 2],
                         open_=flat))
    return nodes, mats


def apron():
    mats = {'asphalt': emissive(hexs(G.ASPHALT[5]), {'image': 'art/asphalt.png', 'projection': 'planar',
                                                     'axis': 'y', 'scale': [16.0, 16.0]}),
            'rail': emissive(sod('#a8a49c', 0.85)),
            'coping': emissive(sod('#a49a8a', 0.7)),
            'edge': emissive(sod('#e0b030', 0.85)),
            'concrete': emissive(sod('#6a6258', 0.6))}
    flat = ['bottom', 'left', 'right', 'back', 'front']
    x0, x1 = -HALF, 90.0
    z0 = G.DECK_FAR - 0.5
    nodes = [box('apron', [x1 - x0, 1.0, QF - z0], 'asphalt', [(x0 + x1) / 2, -0.5, (z0 + QF) / 2], open_=flat),
             box('rail_sea', [x1 - x0, 0.1, 0.6], 'rail', [(x0 + x1) / 2, 0.0, G.RAIL_SEA], open_=flat),
             box('berth_coping', [x1 - x0, 0.3, 0.45], 'coping', [(x0 + x1) / 2, 0.15, QF - 0.225],
                 faces={'top': 'edge'}, open_=['bottom', 'front', 'left', 'right']),
             box('edge_coping', [0.45, 0.3, QF - G.DECK_FAR], 'coping', [x0 + 0.225, 0.15, (G.DECK_FAR + QF) / 2 - 0.45],
                 faces={'top': 'edge'}, open_=['bottom', 'left', 'back', 'front']),
             # the yard's ground behind the container wall, where BG2's map ends (x 64)
             box('yard', [240.0, 1.0, 25.4], 'asphalt', [180.0, -0.5, 6.7], open_=flat)]
    return nodes, mats


def crane(tag, cx, paint, trim, boom_up, rich):
    """A ship-to-shore gantry crane straddling the rails (z 20 and 48), its legs at x = cx -+ 9.
    `paint` the steel's colour, `trim` the boom's and the apex's (red and white on crane B);
    `boom_up`: the boom raised (tilted up from its hinge at the waterside legs), as a crane
    standing idle; `rich`: the trolley's cab and a container on the spreader."""
    zl, zs = G.RAIL_LAND + 0.6, G.RAIL_SEA
    top = 44.0
    nodes = []
    mats = {'steel': {'color': paint}, 'trim': trim, 'dark': {'color': sod('#2a2a2e', 0.8)},
            'lamp': emissive(G.shex('#ffd890', 1.0, 0.0)), 'red': emissive('#ff3a2a'),
            'glass': emissive(G.shex('#ffe8b0', 0.9, 0.0)),
            'halo': {'color': '#ffaa50', 'class': 'emissive', 'blend': 'add',
                     'texture': {'image': 'art/halo.png', 'projection': 'fit'}},
            'hanging': {'color': sod('#b4682c'), 'texture': {'image': 'art/hanging.png', 'projection': 'fit'}}}
    for i, x in enumerate((cx - 9, cx + 9)):
        for j, z in enumerate((zl, zs)):
            nodes.append(box(f'leg_{i}{j}', [2.2, top, 2.2], 'steel', [x, top / 2, z],
                             open_=['bottom', 'top', 'front']))
            if j == 0 and rich:
                nodes.append(box(f'bogie_{i}{j}', [6.0, 2.2, 2.8], 'dark', [x, 1.1, z],
                                 open_=['bottom', 'front', 'left', 'right']))
    for j, z in enumerate((zl, zs)):
        nodes.append(box(f'portal_{j}', [20.8, 4.0, 2.6], 'steel', [cx, top + 1.0, z],
                         open_=['top', 'front', 'left', 'right']))
    for i, x in enumerate((cx - 9, cx + 9)):
        nodes.append(box(f'sill_{i}', [2.4, 3.6, zs - zl - 2.6], 'steel', [x, top + 1.0, (zl + zs) / 2],
                         open_=['top', 'front', 'back']))
    # the boom: from the backreach (z 4) over the ship to z 104, hinged at the waterside legs
    hb = top + 5.0
    if boom_up:
        # the outreach raised 75 degrees about its hinge (zs, hb); the backreach stays level
        ln = 56.0
        tip = (cx, hb + ln * math.sin(math.radians(75)), zs + ln * math.cos(math.radians(75)))
        nodes.append(box('backreach', [3.6, 4.0, zs - 4.0 - 2.0], 'trim', [cx, hb, (4.0 + zs - 2.0) / 2],
                         faces={'bottom': 'steel'}, open_=['top', 'front']))
        nodes.append(span('boom', (cx, hb, zs), tip, 3.6, 'trim', keep=('back', 'bottom', 'left', 'right')))
        tipz, tipy = tip[2], tip[1]
    else:
        nodes.append(box('boom', [3.6, 4.0, 100.0], 'trim', [cx, hb, 54.0],
                         faces={'bottom': 'steel'}, open_=['top', 'front']))
        tipz, tipy = 104.0, hb
        # its floodlights: a row of lamps under the boom over the ship
        for k, z in enumerate((60.0, 72.0, 84.0, 96.0)):
            nodes.append(box(f'boom_lamp_{k}', [2.2, 0.5, 1.0], 'lamp', [cx, hb - 2.2, z],
                             open_=['top', 'front', 'left', 'right', 'back']))
    # the apex: two posts on the portal over the gauge's middle, a beam across, the stays
    az = (zl + zs) / 2
    ay = 78.0
    for i, s in enumerate((-1, 1)):
        nodes.append(box(f'apex_{i}', [1.8, ay - hb, 1.8], 'trim', [cx + s * 7.0, (ay + hb) / 2, az],
                         open_=['bottom', 'top', 'front']))
        nodes.append(span(f'forestay_{i}', (cx + s * 1.4, ay, az), (cx + s * 1.4, tipy + 1.0, tipz), 0.5, 'steel',
                          keep=('bottom',)))
        if rich:
            nodes.append(span(f'backstay_{i}', (cx + s * 7.0, ay, az), (cx + s * 7.0, hb + 1.0, 6.0), 0.6, 'steel',
                              keep=('bottom',)))
    nodes.append(box('apex_beam', [16.0, 2.2, 2.2], 'trim', [cx, ay + 1.0, az], open_=['top', 'front', 'left', 'right']))
    nodes.append(box('apex_light_0', [0.6, 0.6, 0.6], 'red', [cx - 7.0, ay + 2.4, az], open_=LIT))
    nodes.append(box('apex_light_1', [0.6, 0.6, 0.6], 'red', [cx + 7.0, ay + 2.4, az], open_=LIT))
    nodes.append(box('tip_light', [0.7, 0.7, 0.7], 'red', [cx, tipy + 2.4, tipz], open_=LIT))
    if not rich:
        return nodes, mats
    # the machinery house on the backreach
    nodes.append(box('house', [8.0, 5.0, 12.0], 'steel', [cx, hb + 4.4, 11.0], open_=['top', 'front', 'bottom']))
    # floodlights under the portal toward the quay, and their glow
    for k, x in enumerate((cx - 6.0, cx + 6.0)):
        nodes.append(box(f'portal_lamp_{k}', [2.0, 0.6, 1.0], 'lamp', [x, top - 1.3, zl - 0.6],
                         open_=['top', 'front', 'left', 'right']))
        nodes.append(box(f'portal_halo_{k}', [9.0, 9.0, 0.1], 'halo', [x, top - 1.3, zl - 2.0],
                         open_=['top', 'bottom', 'left', 'right', 'front']))
    if not boom_up:
        tz = 72.0
        nodes.append(box('trolley', [4.6, 2.6, 6.0], 'steel', [cx, hb - 3.3, tz], open_=['top', 'front', 'left', 'right']))
        nodes.append(box('cab', [2.6, 2.4, 3.0], 'steel', [cx - 0.6, hb - 5.8, tz - 2.0],
                         faces={'back': 'glass'}, open_=['top', 'front', 'right']))
        sy = 16.0
        for i, s in enumerate((-1, 1)):
            nodes.append(box(f'rope_{i}', [0.12, hb - 4.6 - sy, 0.12], 'dark',
                             [cx + s * 1.6, (hb - 4.6 + sy) / 2, tz], open_=['top', 'bottom', 'front', 'left', 'right']))
        nodes.append(box('spreader', [12.4, 0.6, 2.6], 'dark', [cx, sy - 0.3, tz], open_=['top', 'front', 'left', 'right']))
        nodes.append(box('hanging', [12.19, 2.59, 2.44], 'hanging', [cx, sy - 0.62 - 1.295, tz],
                         faces={'bottom': 'dark', 'left': 'dark', 'right': 'dark'}, open_=['top', 'front']))
    return nodes, mats


LIT = ['top', 'bottom', 'left', 'right', 'front']     # a light: only its face toward the camera


def ship():
    mats = {'hull_stern': emissive(sod('#22385e'), {'image': 'art/hull_stern.png', 'projection': 'fit'}),
            'hull_name': emissive(sod('#22385e'), {'image': 'art/hull_name.png', 'projection': 'fit'}),
            'hull_bow': emissive(sod('#22385e'), {'image': 'art/hull_bow.png', 'projection': 'fit'}),
            'transom': emissive(G.shex('#1c3052', 0.85)),
            'house_f': emissive(sod('#d8d6d0', 0.78), {'image': 'art/house_front.png', 'projection': 'fit'}),
            'house_s': emissive(sod('#d8d6d0', 0.6), {'image': 'art/house_side.png', 'projection': 'fit'}),
            'wing': emissive(sod('#d8d6d0', 0.62)),
            'wing_under': emissive(sod('#d8d6d0', 0.45)),
            'funnel': emissive(sod('#d8d6d0', 0.7), {'image': 'art/funnel.png', 'projection': 'fit'}),
            'funnel_s': emissive(sod('#d8d6d0', 0.5)),
            'cargo': emissive(sod('#2a4a7c', 0.8), {'image': 'art/cargo_sides.png', 'projection': 'box',
                                                     'scale': [26.0, 10.36]}),
            'cargo_end': emissive(sod('#2a4a7c', 0.6), {'image': 'art/cargo_ends.png', 'projection': 'box',
                                                         'scale': [9.76, 10.36]}),
            'mast': emissive(sod('#d8d6d0', 0.5)),
            'red': emissive('#ff3a2a'), 'white': emissive('#fff4e0')}
    zc = (SHIP_Z0 + SHIP_Z1) / 2
    hb, ht = -1.0, SHIP_DECK
    hh = ht - hb
    nodes = []
    for name, x0, x1, extra in (('hull_stern', SHIP_X0, 60.0, {'left': 'transom'}),
                                ('hull_name', 60.0, 160.0, {}), ('hull_bow', 160.0, SHIP_X1, {})):
        faces = {'back': name}
        faces.update(extra)
        opened = ['top', 'bottom', 'front', 'right']
        if not extra:
            opened.append('left')
        nodes.append(box(name, [x1 - x0, hh, SHIP_Z1 - SHIP_Z0], name, [(x0 + x1) / 2, (hb + ht) / 2, zc],
                         faces=faces, open_=opened))
    # the accommodation block at the stern, eleven storeys, the bridge on top; its wings out to
    # the ship's sides; the funnel behind it; a mast with its lights
    hx0, hx1, hz0, hz1, hy1 = -18.0, -2.0, 57.0, 83.0, 42.0
    nodes.append(box('house', [hx1 - hx0, hy1 - ht, hz1 - hz0], 'house_f', [(hx0 + hx1) / 2, (ht + hy1) / 2, (hz0 + hz1) / 2],
                     faces={'left': 'house_s', 'right': 'house_s'}, open_=['top', 'bottom', 'front']))
    nodes.append(box('wings', [hx1 - hx0 + 1.0, 2.6, SHIP_Z1 - SHIP_Z0 + 2.0], 'wing',
                     [(hx0 + hx1) / 2, hy1 - 1.6, zc], faces={'bottom': 'wing_under'},
                     open_=['top', 'front']))
    nodes.append(box('funnel', [8.0, 12.0, 9.0], 'funnel', [-10.0, hy1 + 5.0, 76.0],
                     faces={'left': 'funnel_s', 'right': 'funnel_s'}, open_=['top', 'bottom', 'front']))
    nodes.append(box('mast', [0.5, 9.0, 0.5], 'mast', [-10.0, hy1 + 4.4, 64.0], open_=['top', 'bottom', 'front']))
    nodes.append(box('mast_light', [0.6, 0.6, 0.6], 'red', [-10.0, hy1 + 9.2, 64.0], open_=['bottom']))
    nodes.append(box('stern_light', [0.6, 0.6, 0.6], 'white', [SHIP_X0 + 0.5, ht + 0.6, 56.0], open_=['bottom']))
    # the deck cargo, in blocks of two or three bays (13 m each), four to seven high
    blocks = [(2.0, 28.0, 6), (28.4, 54.4, 7), (54.8, 80.8, 5), (81.2, 120.2, 6), (120.6, 146.6, 7),
              (147.0, 173.0, 4), (173.4, 212.4, 6), (212.8, 264.8, 5)]
    for i, (x0, x1, n) in enumerate(blocks):
        h = n * 2.59
        nodes.append(box(f'cargo_{i}', [x1 - x0, h, 28.0], 'cargo', [(x0 + x1) / 2, ht + h / 2 - 0.02, zc],
                         faces={'left': 'cargo_end'}, open_=['top', 'bottom', 'front', 'right']))
    return nodes, mats


def yard():
    mats = {'stack': emissive(sod('#2e5e40', 0.7), {'image': 'art/yard_sides.png', 'projection': 'box',
                                                     'scale': [26.0, 10.36]}),
            'stack_end': emissive(sod('#2e5e40', 0.55), {'image': 'art/cargo_ends.png', 'projection': 'box',
                                                         'scale': [9.76, 10.36]}),
            'pole': {'color': sod('#6a6a66', 0.8)},
            'head': {'color': sod('#3a3a3a')},
            'lamp': emissive(G.shex('#ffd890', 1.0, 0.0)),
            'halo': {'color': '#ffaa50', 'class': 'emissive', 'blend': 'add',
                     'texture': {'image': 'art/halo.png', 'projection': 'fit'}}}
    nodes = []
    for i, (x0, x1, z0, z1, n) in enumerate([(66.0, 92.0, -14.0, 2.0, 4), (66.0, 92.0, 6.0, 19.0, 3),
                                             (98.0, 150.0, -20.0, 10.0, 5), (98.0, 150.0, 22.0, 46.0, 4)]):
        h = n * 2.59
        opened = ['bottom', 'front', 'right']
        if h > 6.0:
            opened.append('top')
        nodes.append(box(f'stack_{i}', [x1 - x0, h, z1 - z0], 'stack', [(x0 + x1) / 2, h / 2, (z0 + z1) / 2],
                         faces={'left': 'stack_end', 'top': 'head'} if 'top' not in opened else {'left': 'stack_end'},
                         open_=opened))
    for i, (x, z) in enumerate([(44.0, -6.0), (-26.0, 32.0)]):
        hgt = 30.0
        nodes.append(box(f'mast_{i}', [0.8, hgt, 0.8], 'pole', [x, hgt / 2, z], open_=['top', 'bottom', 'front']))
        nodes.append(box(f'head_{i}', [4.4, 1.2, 2.4], 'head', [x, hgt + 0.4, z], faces={'back': 'lamp'},
                         open_=['top', 'front']))
        nodes.append(box(f'halo_{i}', [16.0, 16.0, 0.1], 'halo', [x, hgt + 0.2, z - 1.6],
                         open_=['top', 'bottom', 'left', 'right', 'front']))
    return nodes, mats


def cameras():
    return [
        {'name': 'start', 'eye': [0.0, 6.5, -19.5], 'target': [0.0, 5.5, 60.0]},
        {'name': 'wide', 'eye': [-6.0, 6.5, -31.0], 'target': [-6.0, 4.0, 60.0]},
        {'name': 'open_edge', 'eye': [-27.0, 6.5, -16.0], 'target': [-27.0, 5.0, 60.0]},
        {'name': 'wall', 'eye': [18.0, 6.5, -16.0], 'target': [18.0, 5.0, 60.0]},
    ]


def main():
    write_textures()
    # Honmoku's light blue is kept nearly as it is: the cranes carry their own white floodlights
    na, ma = crane('a', 20.0, '#6aa2bc', {'color': '#6aa2bc'}, False, True)
    nb, mb = crane('b', 58.0, '#d8d4cc',
                   {'color': sod('#c8302a', 0.9, 0.05),
                    'texture': {'pattern': 'stripes', 'colors': [sod('#c8302a', 0.9, 0.05), sod('#e4e0d8', 0.85, 0.08)],
                                'params': {'count': 2, 'axis': 'v'}, 'size': 16, 'projection': 'box',
                                'scale': [8.0, 16.0]}}, True, False)
    wn, wm = water()
    an, am = apron()
    sn, sm = ship()
    yn, ym = yard()
    out = {
        'port_water': recipe('stage_port_water', wn, wm, 40),
        'port_apron': recipe('stage_port_apron', an, am, 80),
        'port_crane_a': recipe('stage_port_crane_a', na, ma, 200, FLOOD),
        'port_crane_b': recipe('stage_port_crane_b', nb, mb, 200, FLOOD),
        'port_ship': recipe('stage_port_ship', sn, sm, 160),
        'port_yard': recipe('stage_port_yard', yn, ym, 100),
    }
    for k, v in out.items():
        (HERE/f'{k}.asset.json').write_text(json.dumps(v, indent=1) + '\n')
    (HERE/'cameras.json').write_text(json.dumps(cameras(), indent=1) + '\n')
    (HERE/'asset-preview.json').write_text(json.dumps({'background': ['#04050a', '#3e2c24'],
                                                       'ground': '#2f271e'}, indent=1) + '\n')


if __name__ == '__main__':
    main()
