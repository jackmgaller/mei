#!/usr/bin/env python3
"""Mech Expo 2000: the rooftop showcase's city in polygons (the stage: stages.akr's rooftop row;
its plane art, the horizon's haze and far lights behind all this, is tools/gen_mechexpo_rooftop.py's,
which also packs what this writes).

Osaka, 2000, at the blue hour, seen from the expo tower's roof: the fight plane is z = 0, the
deck's far edge (the parapet) z = DECK_FAR = 30, and the street is GROUND_Y below the deck. All
of it stands behind the parapet and beyond the open edge (x > ROOF_HALF); nothing is nearer than
the parapet. Every building is a plain box: its roof, a front face and two side faces in window
textures (emissive: the night's lit windows are baked into the texture, in a front tone and a
darker side tone, so a building turns as the camera moves). The landmarks are a few more shapes.
Every recipe is one mesh in the world's coordinates, drawn at the origin.

Writes, beside this script:
  city_near.asset.json   the near rank, z 48-84: low blocks, some below the deck (their roofs
                         show past the open edge)
  city_mid.asset.json    the mid rank, z 100-148: towers
  city_umeda.asset.json  the Umeda Sky Building: two towers joined by the floating garden's ring
  city_lattice.asset.json  a lattice tower with a lit crown and an observation deck (Tsutenkaku)
  city_hep.asset.json    a department store with HEP's red Ferris wheel above it
  city_street.asset.json the street past the open edge: a ground with its avenues and the low
                         blocks nearest the tower (x 34-130, z 10-46)
  art/city_*.png         the textures: the windows (32 x 32 texels, 8 x 8 cells; each rank and
                         kind of building in a front and a side tone), the wheel and the street
                         (the lattice tower's panel is a texel grid in its recipe)
  cameras.json           the game's views of the city, for the Asset Kit's preview (--cameras)

The textures are drawn here with fixed seeds. Run from anywhere:
python3 carts/mechexpo/props/rooftop_city/make_city.py (Pillow, NumPy).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT/'tools'))
import gen_mechexpo_rooftop as R  # noqa: E402  (the stage's half-width and the deck's far edge)

HALF = R.ROOF_HALF
FAR = R.DECK_FAR
GROUND_Y = -48.0                 # the street, below the deck
LIGHTING = {'mode': 'vertical', 'ambient': 0.62}
POLICY = {'required': True, 'depth': True, 'perspective': True}


def rgb(s):
    return tuple(int(s[i:i+2], 16) for i in (1, 3, 5))


def mix(a, b, t):
    return tuple(round(x+(y-x)*t) for x, y in zip(a, b))


def hexs(c):
    return '#%02x%02x%02x' % tuple(c)


HAZE = rgb('#6a5478')                      # the glow at the horizon the far ranks fade toward
# per rank: the cell (metres wide, high), how far toward the haze, the wall and glass tones
RANKS = {
    'near': {'cell': (2.4, 2.7), 'haze': 0.00, 'wall': '#141b33', 'glass': '#1e2846', 'tex': 'n'},
    'mid':  {'cell': (3.2, 3.6), 'haze': 0.22, 'wall': '#1a2240', 'glass': '#26305a', 'tex': 'm'},
}
KINDS = ('resid', 'office', 'dim')
LIT = ['#b88c52', '#dcbc80', '#9c6c3a', '#7a9cc4']       # warm windows, a pale one, amber, cool
LIT_P = (0.55, 0.75, 0.92)                                 # the cumulative odds of the first three
SIDE = 0.66                                                # a side face's tone against the front's
LIT_RATE = {'resid': 0.14, 'office': 0.10, 'dim': 0.05}    # windows lit
LIT_FLOOR = {'resid': 0.06, 'office': 0.12, 'dim': 0.0}    # floors lit as a run


def tile(rank, kind, side, seed):
    """A window texture, 32 x 32 texels: 8 x 8 cells of 4 x 4 texels. 'resid': a window 2 x 2
    texels a cell; 'office': ribbon windows 4 x 2; 'dim': like resid, sparser. Lit cells are
    random (a fixed seed), the side tone is the front's darkened."""
    r = RANKS[rank]
    rng = np.random.default_rng(seed)
    k = SIDE if side else 1.0
    haze = r['haze']

    def tone(c, dim=1.0):
        return mix(mix(rgb(c), (0, 0, 0), 1-k*dim), HAZE, haze)
    wall, glass = tone(r['wall']), tone(r['glass'])
    lit = [mix(mix(rgb(c), (0, 0, 0), 1-(0.5+0.5*k)), HAZE, haze*0.5) for c in LIT]
    im = np.zeros((32, 32, 3), np.uint8)
    im[:] = wall
    for cy in range(8):
        floor_lit = rng.random() < LIT_FLOOR[kind]
        for cx in range(8):
            p = rng.random()
            state = p < 0.75 if floor_lit else p < LIT_RATE[kind]
            col = glass
            if state:
                q = rng.random()
                col = lit[0] if q < LIT_P[0] else lit[1] if q < LIT_P[1] else lit[2] if q < LIT_P[2] else lit[3]
            x, y = cx*4, cy*4
            if kind == 'office':
                im[y+1:y+3, x:x+4] = col
                if cx % 2 == 1:
                    im[y+1:y+3, x+3] = wall
            else:
                im[y+1:y+3, x+1:x+3] = col
    return im


def save4(arr, path):
    Image.fromarray(arr).quantize(colors=15, method=Image.Quantize.MEDIANCUT,
                                  dither=Image.Dither.NONE).convert('RGB').save(path)


def write_tiles():
    art = HERE/'art'
    art.mkdir(exist_ok=True)
    for ri, (rank, r) in enumerate(RANKS.items()):
        for ki, kind in enumerate(KINDS):
            for side in (0, 1):
                save4(tile(rank, kind, side, 11+29*ki+7*ri), art/f'city_{r["tex"]}_{kind[0]}{"s" if side else "f"}.png')
    write_wheel(art/'city_wheel.png')
    write_street(art/'city_street.png')


def write_wheel(path):
    """128 x 128, round, the rest a hole (alpha): HEP's wheel seen from the front: a rim 3 texels
    thick, a second ring inside it, 12 spokes and a hub, in HEP's red."""
    s = 128
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = s/2-0.5
    red, dark, hi, gold = (190, 40, 52, 255), (110, 26, 40, 255), (226, 100, 96, 255), (212, 170, 36, 255)
    d.ellipse([0, 0, s-1, s-1], fill=red)
    d.ellipse([3, 3, s-4, s-4], fill=(0, 0, 0, 0))
    d.ellipse([22, 22, s-23, s-23], outline=dark, width=2)
    for k in range(12):
        a = k*math.pi/6
        d.line([(c, c), (c+(c-2)*math.cos(a), c+(c-2)*math.sin(a))], fill=hi if k % 2 == 0 else dark, width=1)
    d.ellipse([c-5, c-5, c+5, c+5], fill=gold)
    # a gondola mark every 30 degrees on the rim
    for k in range(12):
        a = k*math.pi/6
        x, y = c+(c-1.5)*math.cos(a), c+(c-1.5)*math.sin(a)
        d.rectangle([x-2, y-2, x+2, y+2], fill=gold)
    # quantised through a palette image so the holes stay holes
    a = np.array(im)
    holes = a[:, :, 3] < 128
    pal = Image.fromarray(a[:, :, :3]).quantize(colors=7, method=Image.Quantize.MEDIANCUT,
                                                dither=Image.Dither.NONE).convert('RGB')
    out = np.array(pal)
    res = np.dstack([out, np.where(holes, 0, 255).astype(np.uint8)])
    Image.fromarray(res, 'RGBA').save(path)


def write_street(path):
    """64 x 64, a 64 m square seen from above: blocks, an avenue each way with its centre line,
    the lamps along it, headlights and tail lights, the odd lit roof."""
    rng = np.random.default_rng(77)
    s = 64
    block, road, line = rgb('#0e1226'), rgb('#161b30'), rgb('#3a4466')
    roof = [rgb('#1a2140'), rgb('#202848'), rgb('#161c38')]
    im = np.zeros((s, s, 3), np.uint8)
    im[:] = block
    # the blocks: roofs of low buildings in the four quarters
    for (x0, y0, x1, y1) in ((2, 2, 27, 27), (37, 2, 62, 27), (2, 37, 27, 62), (37, 37, 62, 62)):
        for _ in range(3):
            bx, by = int(rng.integers(x0, x1-8)), int(rng.integers(y0, y1-8))
            im[by:by+int(rng.integers(6, 12)), bx:bx+int(rng.integers(6, 12))] = roof[int(rng.integers(0, 3))]
    im[28:36, :] = road
    im[:, 28:36] = road
    im[31:33, ::4] = line
    im[::4, 31:33] = line
    lamp, head, tail = rgb('#d8a860'), rgb('#f2e4b8'), rgb('#c8302a')
    for x in range(2, 64, 8):
        im[27, x] = lamp
        im[36, (x+4) % 64] = lamp
    for y in range(2, 64, 8):
        im[y, 27] = lamp
        im[(y+4) % 64, 36] = lamp
    for x in rng.choice(np.arange(0, 64), 7, replace=False):
        im[29, x] = head
        im[34, int(x)-3] = tail
    for y in rng.choice(np.arange(0, 64), 7, replace=False):
        im[y, 29] = head
        im[int(y)-3, 34] = tail
    for _ in range(14):                       # lit roofs and windows seen from above
        x, y = int(rng.integers(2, 62)), int(rng.integers(2, 62))
        if 27 < x < 37 or 27 < y < 37:
            continue
        im[y, x] = rgb('#a88048')
    save4(im, path)


def materials():
    m = {}
    for rank, r in RANKS.items():
        for kind in KINDS:
            for side in ('f', 's'):
                name = f'{r["tex"]}_{kind[0]}{side}'
                m[name] = {'color': r['wall'], 'class': 'emissive', 'texture': {
                    'image': f'art/city_{name}.png', 'projection': 'box',
                    'scale': [8*r['cell'][0], 8*r['cell'][1]]}}
        m[f'{r["tex"]}_roof'] = {'color': hexs(mix(rgb('#222b4c'), HAZE, r['haze']+0.1))}
    m['plant'] = {'color': '#2c3556'}
    m['red'] = {'color': '#ff3a2a', 'class': 'emissive'}
    m['steel'] = {'color': '#3c4568'}
    m['crown'] = {'color': '#6a9ad0', 'class': 'emissive'}
    m['warm'] = {'color': '#d8a860', 'class': 'emissive'}
    m['white'] = {'color': '#e8eef8', 'class': 'emissive'}
    m['neon_c'] = {'color': '#38b8d0', 'class': 'emissive'}
    m['neon_p'] = {'color': '#c8408c', 'class': 'emissive'}
    m['neon_y'] = {'color': '#d0b438', 'class': 'emissive'}
    m['ring'] = {'color': '#4a5780'}
    m['gondola_r'] = {'color': '#b02a34', 'class': 'emissive'}
    m['gondola_y'] = {'color': '#c89a28', 'class': 'emissive'}
    m['wheel'] = {'color': '#e02a34', 'class': 'emissive', 'texture': {
        'image': 'art/city_wheel.png', 'projection': 'fit'}}
    m['lattice'] = {'color': '#4a5780', 'double_sided': True, 'texture': {
        'texels': LATTICE, 'colors': ['#000000', '#4a5780'], 'clear': '#000000', 'projection': 'fit'}}
    m['street'] = {'color': '#0e1226', 'class': 'emissive', 'texture': {
        'image': 'art/city_street.png', 'projection': 'planar', 'axis': 'y', 'scale': [64, 64]}}
    return m


def lattice_texels():
    """32 x 32: a panel of a lattice tower: the two posts (3 texels), a bar top and bottom and an
    X between (2 texels thick; digit 1 the steel, 0 a hole)."""
    n = 32
    g = [[0]*n for _ in range(n)]
    for i in range(n):
        for t in range(-1, 1):
            for j in (i+t, n-1-i+t):
                if 0 <= j < n:
                    g[i][j] = 1
    for i in range(n):
        for j in (0, 1, 2, n-3, n-2, n-1):
            g[i][j] = 1
    for j in range(n):
        for i in (0, 1, n-2, n-1):
            g[i][j] = 1
    return [''.join(str(v) for v in row) for row in g]


LATTICE = lattice_texels()


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


# The lowest a building's face is ever seen: the deck and the parapet hide everything below a
# sight line from the eye (6.5 m up) over the parapet's rail (2.3 m, z = 30): about y = -1 at
# z = 60 and -8 at z = 130, whatever the zoom. A building wholly left of the open edge starts
# there instead of at the street (what is under the deck is never seen, and the GPU would
# draw it before the plane chip hid it); one that is not has a face past the lip down to the street.
HIDDEN_Y = {'near': -3.0, 'mid': -10.0}
ROOF_SEEN_Y = 14.0           # the eye is 6.5 m up (cam_lift raises it by 0.45 of a jump's height): a roof
                             # above this is never seen from above
CAM_RIGHT, CAM_LEFT = 32.0, -30.0   # the camera's x: -22 to 24 (a view of the open edge, the angled framing)


def base_for(rank, x1, top):
    """The y a building ends at below: the street if it is seen past the open edge, else a
    whole number of two floors under `top`, at or below HIDDEN_Y; None if it would be hidden
    altogether (its roof below that)."""
    if x1 > HALF - 2.0:
        return GROUND_Y
    cell_h = RANKS[rank]['cell'][1]
    if top <= HIDDEN_Y[rank]:
        return None
    return top - 2*cell_h*math.ceil((top-HIDDEN_Y[rank])/(2*cell_h))


def block(id_, rank, kind, x0, x1, z0, z1, top, ground=GROUND_Y, rng=None, beacon=None):
    """A building: x0..x1 across, z0..z1 deep, from `ground` up to `top`. A box whose -z face
    (the one the fight sees) takes the front texture and whose sides take the side texture; the
    bottom and the +z face are not drawn. A rooftop plant or two when `rng` is given (a roof
    below the eye shows), and the red aircraft light on a tall one when `beacon` (its size) is."""
    r = RANKS[rank]
    t = r['tex']
    k = kind[0]
    w, d, h = x1-x0, z1-z0, top-ground
    cx, cy, cz = (x0+x1)/2, (top+ground)/2, (z0+z1)/2
    # what the camera cannot see is not made: the bottom, the +z face, the roof of a building
    # above the eye, the +x face of one wholly right of where the camera goes (x up to 24, and 8 m
    # left of that in the angled framing) and the -x face of one wholly left of it
    opened = ['bottom', 'front']
    faces = {'left': f'{t}_{k}s', 'right': f'{t}_{k}s', 'top': f'{t}_roof'}
    if top > ROOF_SEEN_Y:
        opened.append('top')
        del faces['top']
    if x0 > CAM_RIGHT:
        opened.append('right')
        del faces['right']
    if x1 < CAM_LEFT:
        opened.append('left')
        del faces['left']
    nodes = [box(id_, [w, h, d], f'{t}_{k}f', [cx, cy, cz], open_=opened, faces=faces)]
    if rng is not None or beacon:
        cw = r['cell'][0]
        mat = 'plant'
        for i in range(int(rng.integers(0, 3)) if rng is not None else 0):
            pw, pd, ph = cw*float(rng.choice([1, 1.5, 2])), cw*float(rng.choice([1, 1.5])), cw*float(rng.choice([0.6, 0.9]))+0.17*i
            px = x0+pw/2+0.6+float(rng.random())*max(w-pw-1.2, 0)
            pz = z0+pd/2+0.6+float(rng.random())*max(d-pd-1.2, 0)
            nodes.append(box(f'{id_}_p{i}', [pw, ph, pd], mat, [px, top+ph/2-0.02, pz], open_=['bottom', 'front']))
        if beacon:
            nodes.append(box(f'{id_}_b', [beacon, beacon, beacon], 'red', [cx, top+1.65+beacon/2, cz]))
            nodes.append(box(f'{id_}_m', [0.3, 1.8, 0.3], 'steel', [cx, top+0.85, cz], open_=['bottom', 'front']))
    return nodes


def used(nodes):
    """The material names a node list draws."""
    names = set()
    for n in nodes:
        if 'material' in n:
            names.add(n['material'])
        names.update(n.get('faces', {}).values())
        names.update(d['material'] for d in n.get('decals', []))
        names |= used(n.get('children', []))
    return names


def recipe(name, nodes, tris, lighting=None):
    mats = materials()
    keep = used(nodes)
    return {'format': 'mei-asset', 'version': 1, 'name': name,
            'budget': {'vertices': 2000, 'triangles': tris},
            'lighting': lighting or LIGHTING, 'verification': POLICY,
            'materials': {k: v for k, v in mats.items() if k in keep}, 'nodes': nodes}


def rank_blocks(rank, kinds, z_of, x_lo, x_hi, widths, depths, tops, gap, seed, skip=(), tall=None,
                tops_lo=None, signs=0.0, caps=()):
    """A row of buildings from x_lo to x_hi: widths, depths and tops (random picks from lists, a
    fixed seed), with a gap between; `skip` is a list of (x0, x1) left empty for a landmark and
    `caps` a list of (x0, x1, top) that keep the buildings there no higher than `top`, so they
    do not hide a landmark behind them. A
    building taller than `tall` (floors) carries the red light."""
    rng = np.random.default_rng(seed)
    r = RANKS[rank]
    cw, ch = r['cell']
    nodes = []
    x = x_lo
    n = 0
    while x < x_hi:
        w = cw * 2 * int(rng.choice(widths))
        for s0, s1 in skip:
            if x < s1 and x + w > s0:
                x = s1 + gap
                break
        else:
            d = cw * 2 * int(rng.choice(depths))
            nf = int(rng.choice(tops_lo if tops_lo and x+w > HALF-2.0 else tops))
            for c0, c1, ct in caps:
                if x < c1 and x + w > c0:
                    nf = min(nf, int((ct-GROUND_Y)//(2*ch)))
            top = GROUND_Y + 2*ch*nf
            z0 = z_of(rng)
            kind = kinds[int(rng.integers(0, len(kinds)))]
            base = base_for(rank, x+w, top)
            if base is not None:
                nodes += block(f'{rank}_{n}', rank, kind, x, x+w, z0, z0+d, top, ground=base,
                              rng=rng if top < 0 else None, beacon=1.0 if tall and nf >= tall else None)
                if signs and top > GROUND_Y+12 and x+w > HALF-2.0:
                    for j in range(2 if w > 8*cw else 1):
                        if rng.random() < signs:
                            nodes += neon(f'{rank}_{n}_s{j}', rng, x, x+w, z0, top)
                n += 1
            x += w + 0.4 + float(rng.integers(0, 3)) * cw
    return nodes


def neon(id_, rng, x0, x1, z0, top):
    """A vertical neon sign on a building's front, a few metres in from a corner, and a lit
    board under it, as the old painting had along the avenue."""
    mat = ('neon_c', 'neon_p', 'neon_y')[int(rng.integers(0, 3))]
    sx = x0 + 1.5 + float(rng.random()) * max(x1-x0-3.0, 0.0)
    sh = float(rng.choice([4.0, 6.0, 8.0]))
    sy = top - 4.0 - sh/2 - float(rng.integers(0, 3)) * 3.0
    flat = ['top', 'bottom', 'left', 'right', 'front']          # a card: only the face the fight sees
    return [box(id_, [0.9, sh, 0.5], mat, [sx, sy, z0-0.25], open_=flat),
            box(id_+'b', [2.6, 1.2, 0.55], 'neon_y' if mat != 'neon_y' else 'neon_p',
                [sx, sy-sh/2-1.2, z0-0.275], open_=flat)]


def near_rank():
    return rank_blocks('near', ['resid', 'resid', 'office', 'dim'],
                       lambda rng: 48.0 + 2.4*int(rng.integers(0, 8)),
                       -150.0, 170.0, [2, 3, 4, 5], [2, 3, 4], [5, 6, 7, 8, 8, 9, 9, 10, 11, 12, 14], 2.4, 101,
                       tall=12, tops_lo=[3, 4, 5, 5, 6, 6, 7, 8, 9, 12], signs=0.85,
                       caps=[(-80.0, -20.0, 9.0), (55.0, 105.0, 14.0)])      # not in front of the wheel, the lattice tower


def mid_rank():
    skip = [(-66.0, -30.0), (-24.0, 28.0), (60.0, 96.0)]   # the store's, Umeda's, the lattice tower's
    return rank_blocks('mid', ['office', 'resid', 'dim'],
                       lambda rng: 100.0 + 3.2*int(rng.integers(0, 9)),
                       -230.0, 230.0, [2, 3, 4], [3, 4], [9, 10, 11, 12, 13, 14], 3.2, 202,
                       skip=skip, tall=14)


def umeda():
    """Two towers (12.8 m wide, 14 deep, to y = 69 from the street) 10.4 m apart, joined at the
    top by a bridge, the floating garden's ring (an octagon) standing in the gap above it, a
    warm line of lights along the bridge and a red light on a tower."""
    z0, z1 = 120.0, 134.0
    top = GROUND_Y + 7.2*14
    nodes = []
    for i, (x0, x1) in enumerate(((-18.4, -5.6), (5.6, 18.4))):
        nodes += block(f'tower_{i}', 'mid', ('office', 'resid')[i], x0, x1, z0, z1, top)
    # the bridge: between the towers near the top, 9 m deep from y = top - 13.5 to top - 4.5
    nodes.append(box('bridge', [11.2+0.4, 7.2, 13.0], 'm_of', [0.0, top-7.2, (z0+z1)/2],
                     open_=['bottom', 'front'], faces={'top': 'm_roof', 'left': 'm_os', 'right': 'm_os'}))
    nodes.append(box('bridge_lights', [11.0, 0.7, 0.3], 'warm', [0.0, top-6.5, z0+0.45], open_=['bottom', 'front']))
    # the ring: an octagon of 8 beams in the gap, above the bridge
    cy, r = top+4.5, 5.0
    seg = 2*r*math.tan(math.pi/8)
    for k in range(8):
        a = math.pi/8 + k*math.pi/4
        x, y = r*math.cos(a), r*math.sin(a)
        nodes.append(box(f'ring_{k}', [seg+0.5+0.03*k, 1.3, 7.0+0.1*k], 'ring', [x, cy+y, (z0+z1)/2],
                         rot=[0, 0, round(math.degrees(a)+90, 3)], open_=['front', 'left', 'right']))
    nodes.append(box('ring_light', [0.5, 0.5, 0.5], 'red', [-12.0, top+0.6, (z0+z1)/2]))
    nodes.append(box('ring_mast', [0.3, 1.2, 0.3], 'steel', [-12.0, top+0.55, (z0+z1)/2], open_=['bottom', 'front']))
    return nodes


def lattice():
    """A lattice tower from the street (Tsutenkaku): a lofted square tapering from 14 m to 6 m
    wide, a lit observation deck, a spire and a crown. Placed at x = 78, z = 118."""
    x, z = 78.0, 118.0
    secs = []
    for k in range(9):
        t = k/8.0
        secs.append((GROUND_Y+96*t, round(3.2+3.8*(1-t)**1.3, 3)))
    loft = {'id': 'lattice', 'op': 'loft', 'material': 'lattice', 'caps': False,
            'sections': [{'y': y, 'points': [[x-h, z-h], [x+h, z-h], [x+h, z+h], [x-h, z+h]]} for y, h in secs]}
    top = GROUND_Y+96
    nodes = [loft]
    nodes.append(box('deck', [9.0, 4.0, 9.0], 'steel', [x, top-12, z], open_=['bottom', 'front']))
    nodes.append(box('deck_band', [9.2, 1.0, 9.2], 'crown', [x, top-12, z], open_=['bottom', 'front']))
    nodes.append(box('crown_base', [5.0, 6.0, 5.0], 'steel', [x, top+2.0, z], open_=['bottom', 'front']))
    nodes.append(box('crown', [5.4, 2.6, 5.4], 'crown', [x, top+3.0, z], open_=['bottom', 'front']))
    nodes.append(box('mast', [0.5, 14.0, 0.5], 'steel', [x, top+12.0, z], open_=['bottom', 'front']))
    nodes.append(box('beacon', [0.9, 0.9, 0.9], 'red', [x, top+19.4, z]))
    return nodes


def hep():
    """A department store (mid textures; x -64 to -36, z 96 to 112, its roof 9.6 m above the deck)
    with HEP's wheel on its roof: two discs 3.5 m apart in a wheel texture (cutouts), twelve
    gondolas between them, the hub and two legs. Placed in the world's coordinates."""
    x0, x1, z0, z1 = -64.0, -36.0, 96.0, 112.0
    top = GROUND_Y + 7.2*8
    nodes = block('store', 'mid', 'office', x0, x1, z0, z1, top)
    cx, cz, R_ = -50.0, 104.0, 12.0
    cy = top + R_ + 4.0
    for i, dz in enumerate((-1.75, 1.75)):
        nodes.append(box(f'wheel_{i}', [2*R_, 2*R_, 0.3], 'wheel', [cx, cy, cz+dz*1.0],
                         open_=['top', 'bottom', 'left', 'right']))
    for k in range(12):
        a = k*math.pi/6
        nodes.append(box(f'gondola_{k}', [1.5, 1.5, 3.6], 'gondola_r' if k % 2 else 'gondola_y',
                         [cx+(R_-0.6)*math.cos(a), cy+(R_-0.6)*math.sin(a), cz],
                         open_=['top', 'bottom', 'left', 'right', 'front']))
    nodes.append(box('hub', [1.6, 1.6, 4.0], 'steel', [cx, cy, cz]))
    for i, s in enumerate((-1, 1)):
        nodes.append(box(f'leg_{i}', [0.8, 15.5, 0.8+0.1*i], 'steel', [cx+s*3.2, top+7.0, cz+0.9*s],
                         rot=[0, 0, round(-s*13.0, 3)], open_=['bottom']))
    return nodes


def street():
    """The ground past the open edge: x 24 to 344, z 0 to 330 at the street's level, in the
    avenue texture (a 64 m square a repeat), and the low blocks nearest the tower, their roofs
    below the deck."""
    nodes = [box('ground', [320.0, 1.0, 330.0], 'street', [24+160.0, GROUND_Y-0.5, 165.0],
                 open_=['bottom', 'left', 'right', 'back', 'front'])]
    rng = np.random.default_rng(404)
    x = 34.0
    n = 0
    while x < 130.0:
        w = 6.4*int(rng.choice([2, 3, 4]))
        d = 6.4*int(rng.choice([2, 3]))
        z0 = 10.0 + 6.4*int(rng.integers(0, 5))
        nf = int(rng.choice([2, 3, 4, 5, 6]))
        nodes += block(f'low_{n}', 'near', ['resid', 'dim', 'office'][int(rng.integers(0, 3))], x, x+w, z0, z0+d,
                       GROUND_Y+7.2*nf, rng=rng)
        x += w+0.4+3.2*int(rng.integers(0, 3))
        n += 1
    return nodes


def cameras():
    return [
        {'name': 'whole', 'eye': [0.0, 6.5, -30.0], 'target': [0.0, 20.0, 120.0]},
        {'name': 'edge', 'eye': [20.0, 6.5, -16.0], 'target': [60.0, -10.0, 60.0]},
    ]


def main():
    write_tiles()
    out = {
        'city_near': recipe('stage_roof_city_near', near_rank(), 2000),
        'city_mid': recipe('stage_roof_city_mid', mid_rank(), 2000),
        'city_umeda': recipe('stage_roof_city_umeda', umeda(), 400),
        'city_lattice': recipe('stage_roof_city_lattice', lattice(), 200),
        'city_hep': recipe('stage_roof_city_hep', hep(), 600),
        'city_street': recipe('stage_roof_city_street', street(), 600),
    }
    for k, v in out.items():
        (HERE/f'{k}.asset.json').write_text(json.dumps(v, indent=1)+'\n')
    (HERE/'cameras.json').write_text(json.dumps(cameras(), indent=1)+'\n')


if __name__ == '__main__':
    main()
