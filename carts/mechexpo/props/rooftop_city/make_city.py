#!/usr/bin/env python3
"""Mech Expo 2000: the rooftop showcase's city in polygons (the stage: stages.akr's rooftop row;
its plane art, the far shore, the moon and the sea on BG1 behind all this, is
tools/gen_mechexpo_rooftop.py's, which also packs what this writes).

Yokohama, October 2000, at the blue hour, seen from the expo tower's roof on the waterfront of
Minato Mirai 21: the fight plane is z = 0, the deck's far edge (the parapet) z = DECK_FAR = 30,
and the sea is SEA_Y below the deck. Inland to the left (-x) the district's towers, with
Landmark Tower and Queen's Square; in the middle, in the harbour, Cosmo Clock 21; to the right,
by the water, the sail hotel and the convention centre's exhibition hall (the expo's venue),
and far across the harbour the Marine Tower and the Bay Bridge. Below the open edge
(x > ROOF_HALF) the promenade along the quay, its lamps, kiosks and signs, and the tall ship in
her dock. As it stood in 2000: nothing that opened later.

A building is a box or a prism in emissive textures (the lit windows are in the texture: a front
tone and a darker side tone, so a building turns as the camera moves); the landmarks have
textures of their own (the wheel and its clock, the sail's face, the hall's sign) and lights in
flat emissive colours. The sea itself is BG1's (the plane behind the polygons); the reflections
of the lights that have open water between them and the camera are cards hanging below the
waterline, where a mirror image would be. Every recipe is one mesh in the world's coordinates,
drawn at the origin.

Writes, beside this script:
  city_mm.asset.json     Landmark Tower and Queen's Square's three towers (z 300-352)
  city_towers.asset.json the office and hotel towers inland (z 196-334), three with lit crowns
  city_wheel.asset.json  Cosmo Clock 21: the wheel, its clock at the hub (20:00) and its legs
  city_bay.asset.json    across the harbour: the Bay Bridge and the Marine Tower, and the
                         moon's glade on the water
  city_venue.asset.json  by the water on the right: the sail hotel and the exhibition hall with
                         its MECH EXPO 2000 sign band and banners, and their reflections
  city_quay.asset.json   below the open edge: the promenade, its lamps, kiosks and signs, the
                         dock and the tall ship, a harbour launch, and their reflections
  art/city_*.png         the textures: the windows (32 x 32 texels, 8 x 8 cells; each rank and
                         kind of building in a front and a side tone), the wheel, the sail, the
                         sign and the reflections; every one drawn in the colours of two shared
                         palettes (WINDOW, LANDMARK) so that the pack needs few palettes
  cameras.json           the game's views of the city, for the Asset Kit's preview (--cameras)

The textures are drawn here with fixed seeds. Run from anywhere:
python3 carts/mechexpo/props/rooftop_city/make_city.py (Pillow, NumPy).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT/'tools'))
import gen_mechexpo_rooftop as R  # noqa: E402  (the stage's half-width and the deck's far edge)

HALF = R.ROOF_HALF
SEA_Y = -48.0                    # the water, below the deck
QUAY_Y = SEA_Y + 2.0             # the quay's paving
LIGHTING = {'mode': 'vertical', 'ambient': 0.62}
POLICY = {'required': True, 'depth': True, 'perspective': True}


def rgb(s):
    return tuple(int(s[i:i+2], 16) for i in (1, 3, 5))


# ---- the textures' colours: two shared sets, so the pack fits them in few palettes

WINDOW = {                       # the windows of every building
    'm_wall_f': '#18203c', 'm_wall_s': '#10162a', 'm_glass_f': '#222c50', 'm_glass_s': '#171e38',
    'f_wall_f': '#262a48', 'f_wall_s': '#1b1f38', 'f_glass_f': '#30365a', 'f_glass_s': '#23294a',
    'q_glass_f': '#2c4470', 'q_glass_s': '#1f3054',
    'warm': '#b88c52', 'pale': '#dcbc80', 'amber': '#9c6c3a', 'cool': '#7a9cc4',
}
LANDMARK = {                     # the wheel and its clock, the sail, the sign, the reflections
    'rim': '#8ccfe4', 'rim_dk': '#3c7890', 'gold': '#f0c060', 'pink': '#e070a0',
    'spoke': '#5aa8c8', 'hub': '#0e1630', 'white': '#eef2f6',
    'sail_top': '#7e8cb4', 'sail_mid': '#a4b0cc', 'sail_low': '#dcd6cc', 'sail_win': '#6a789e',
    'blue': '#1e3c9a',
}
W = {k: rgb(v) for k, v in WINDOW.items()}
L = {k: rgb(v) for k, v in LANDMARK.items()}

# per rank: the cell (metres wide, high) and its textures' prefix; the cells are large enough
# that a window's texel stays about a pixel or more at the rank's distance (no shimmer)
RANKS = {
    'mid': {'cell': (5.6, 5.6), 'tex': 'm'},     # z 196-290
    'far': {'cell': (8.0, 8.0), 'tex': 'f'},     # z 300-352: Landmark Tower, Queen's Square
}
KINDS = ('office', 'resid', 'glass')
LIT_P = (0.55, 0.75, 0.92)       # the cumulative odds of warm, pale, amber (else cool)
LIT_RATE = {'resid': 0.12, 'office': 0.09, 'glass': 0.06}
LIT_FLOOR = {'resid': 0.05, 'office': 0.10, 'glass': 0.08}


def tile(rank, kind, side, seed):
    """A window texture, 32 x 32 texels: 8 x 8 cells of 4 x 4 texels. 'resid': a window 2 x 2
    texels a cell; 'office': ribbon windows 4 x 2; 'glass': Queen's Square's curtain walls,
    bands of glass 3 texels high. Lit cells are random (a fixed seed); the side's tones are
    darker than the front's."""
    t = RANKS[rank]['tex']
    s = 's' if side else 'f'
    rng = np.random.default_rng(seed)
    if kind == 'glass':
        wall, glass = W[f'{t}_wall_{s}'], W[f'q_glass_{s}']
    else:
        wall, glass = W[f'{t}_wall_{s}'], W[f'{t}_glass_{s}']
    lit = [W['warm'], W['pale'], W['amber'], W['cool']]
    im = np.zeros((32, 32, 3), np.uint8)
    im[:] = wall
    for cy in range(8):
        floor_lit = rng.random() < LIT_FLOOR[kind]
        for cx in range(8):
            p = rng.random()
            state = p < 0.7 if floor_lit else p < LIT_RATE[kind]
            col = glass
            if state:
                q = rng.random()
                col = lit[0] if q < LIT_P[0] else lit[1] if q < LIT_P[1] else lit[2] if q < LIT_P[2] else lit[3]
            x, y = cx*4, cy*4
            if kind == 'office':
                im[y+1:y+3, x:x+4] = col
                if cx % 2 == 1:
                    im[y+1:y+3, x+3] = wall
            elif kind == 'glass':
                im[y:y+3, x:x+4] = col
            else:
                im[y+1:y+3, x+1:x+3] = col
    return im


def save(arr, path):
    Image.fromarray(arr).save(path)


def write_tiles():
    art = HERE/'art'
    art.mkdir(exist_ok=True)
    for p in art.glob('city_*.png'):
        p.unlink()
    seed = 11
    for rank, kinds in (('mid', ('office', 'resid')), ('far', ('office', 'glass'))):
        for kind in kinds:
            for side in (0, 1):
                save(tile(rank, kind, side, seed), art/f'city_{RANKS[rank]["tex"]}_{kind[0]}{"s" if side else "f"}.png')
                seed += 7
    write_wheel(art/'city_wheel.png')
    write_sail(art/'city_sail.png')
    write_sign(art/'city_sign.png')
    for name, cols in REFL.items():
        write_refl(art/f'city_refl_{name}.png', cols)


# ---- the wheel and its clock

DIGITS = {        # 4 x 7, '#' lit
    '0': ['####', '#..#', '#..#', '#..#', '#..#', '#..#', '####'],
    '2': ['####', '...#', '...#', '####', '#...', '#...', '####'],
    ':': ['.', '.', '#', '.', '#', '.', '.'],
}
CLOCK = '20:00'


def write_wheel(path):
    """64 x 64, round, the rest a hole (alpha): Cosmo Clock 21 seen from the front, clean at game
    scale: a solid lit rim 3 texels thick with 16 gondola lights on it, eight spokes 2 texels
    thick, and at the hub the clock: a dark disc in a lit ring with CLOCK in large digits."""
    s = 64
    c = (s - 1) / 2
    a = np.zeros((s, s, 4), np.uint8)
    yy, xx = np.mgrid[0:s, 0:s]
    r = np.hypot(xx - c, yy - c)

    def put(mask, col):
        a[mask] = col + (255,)
    # spokes: 8, 2 texels thick, from the hub to the rim
    for k in range(8):
        t = k * math.pi / 4 + math.pi / 8
        d = np.abs(-(xx - c) * math.sin(t) + (yy - c) * math.cos(t))
        along = (xx - c) * math.cos(t) + (yy - c) * math.sin(t)
        put((d < 1.0) & (along > 12) & (r < 29.5), L['spoke'])
    put((r >= 28.5) & (r < 29.5), L['rim_dk'])
    put((r >= 29.5) & (r <= 31.9), L['rim'])
    # 16 gondola lights on the rim
    for k in range(16):
        t = k * math.pi / 8
        gx, gy = c + 30.6 * math.cos(t), c + 30.6 * math.sin(t)
        m = (np.abs(xx - gx) < 1.3) & (np.abs(yy - gy) < 1.3)
        put(m, L['gold'] if k % 2 else L['pink'])
    # the clock
    put(r < 13.5, L['rim'])
    put(r < 12.0, L['hub'])
    w = sum(len(DIGITS[ch][0]) for ch in CLOCK) + len(CLOCK) - 1
    x = int(round(c - w / 2 + 0.5))
    y0 = int(round(c - 3.5 + 0.5))
    for ch in CLOCK:
        g = DIGITS[ch]
        for j, row in enumerate(g):
            for i, v in enumerate(row):
                if v == '#':
                    a[y0 + j, x + i] = L['white'] + (255,)
        x += len(g[0]) + 1
    Image.fromarray(a, 'RGBA').save(path)


def write_sail(path):
    """32 x 64: the sail hotel's face, drawn once across it (planar): white, darker toward the
    top and lit warm from below, a faint floor line every 5 texels (a few rooms lit)."""
    rng = np.random.default_rng(31)
    a = np.zeros((64, 32, 3), np.uint8)
    for y in range(64):
        a[y, :] = L['sail_top'] if y < 24 else L['sail_mid'] if y < 50 else L['sail_low']
    for y in range(5, 58, 5):                    # the floors: a faint line, a few rooms lit
        a[y, 1:31] = L['sail_win'] if y < 24 else L['sail_top'] if y < 50 else L['sail_mid']
        for x in range(2, 30, 3):
            if rng.random() < 0.14:
                a[y, x:x+2] = L['gold']
    a[:, 0] = L['sail_top']                      # the frame's edges
    a[:, 31] = L['sail_top']
    save(a, path)


GLYPHS = {        # 3 x 5
    'M': ['#.#', '###', '###', '#.#', '#.#'], 'E': ['###', '#..', '##.', '#..', '###'],
    'C': ['###', '#..', '#..', '#..', '###'], 'H': ['#.#', '#.#', '###', '#.#', '#.#'],
    'X': ['#.#', '#.#', '.#.', '#.#', '#.#'], 'P': ['###', '#.#', '###', '#..', '#..'],
    'O': ['###', '#.#', '#.#', '#.#', '###'], '2': ['###', '..#', '###', '#..', '###'],
    '0': ['###', '#.#', '#.#', '#.#', '###'], ' ': ['...'] * 5,
}


def write_sign(path):
    """128 x 16: the exhibition hall's sign, MECH EXPO 2000 in white on the expo's blue: 3 x 5
    letters drawn at two texels a dot, so that from every view (the sign 92 m wide, 230-260 m
    off, about 0.6 pixel a texel) no stroke or gap falls between the pixels."""
    a = np.zeros((8, 64, 3), np.uint8)
    a[:] = L['blue']
    text = 'MECH EXPO 2000'
    w = len(text) * 4 - 1
    x = (64 - w) // 2
    for ch in text:
        for j, row in enumerate(GLYPHS[ch]):
            for i, v in enumerate(row):
                if v == '#':
                    a[1 + j, x + i] = L['white']
        x += 4
    a[7, :] = L['gold']
    save(np.repeat(np.repeat(a, 2, axis=0), 2, axis=1), path)


REFL = {'warm': ('gold', 'sail_low'), 'white': ('sail_low', 'sail_mid')}


def write_refl(path, cols):
    """8 x 32, a hole but for the streak: a light's reflection on the water seen from the roof,
    broken into ripples, brightest and widest at the top (the waterline), thinning and breaking
    up below."""
    rng = np.random.default_rng(len(path.name) * 7 + sum(map(ord, path.name)))
    a = np.zeros((32, 8, 4), np.uint8)
    hi, lo = L[cols[0]], L[cols[1]]
    for y in range(32):
        if y > 2 and rng.random() < 0.2 + 0.5 * y / 32:
            continue                                   # a gap between ripples
        half = 3.5 * (1 - y / 40)
        jit = int(rng.integers(-1, 2)) if y > 6 else 0
        x0, x1 = int(round(4 - half)) + jit, int(round(4 + half)) + jit
        x0, x1 = max(x0, 0), min(x1, 8)
        col = hi if y < 10 or rng.random() < 0.4 else lo
        a[y, x0:x1] = col + (255,)
    Image.fromarray(a, 'RGBA').save(path)


# ---- materials

def materials():
    m = {}
    for rank, r in RANKS.items():
        t = r['tex']
        for kind in KINDS:
            for side in ('f', 's'):
                name = f'{t}_{kind[0]}{side}'
                if not (HERE/'art'/f'city_{name}.png').exists():
                    continue
                m[name] = {'color': WINDOW[f'{t}_wall_f'], 'class': 'emissive', 'texture': {
                    'image': f'art/city_{name}.png', 'projection': 'box',
                    'scale': [8*r['cell'][0], 8*r['cell'][1]]}}
        m[f'{t}_roof'] = {'color': '#262e50' if t == 'm' else '#2c3254'}
    m['steel'] = {'color': '#3c4568'}
    m['dark'] = {'color': '#141a30'}
    m['quay'] = {'color': '#2a3048'}
    m['quay_edge'] = {'color': '#4a5470'}
    m['hull'] = {'color': '#b4bed6', 'class': 'emissive'}
    m['hull_band'] = {'color': '#2a3a6a'}
    m['mast'] = {'color': '#7c88aa', 'class': 'emissive'}
    m['red'] = {'color': '#ff3a2a', 'class': 'emissive'}
    m['green'] = {'color': '#40e070', 'class': 'emissive'}
    m['crown'] = {'color': '#8ab8e8', 'class': 'emissive'}
    m['crown_w'] = {'color': '#e8eef8', 'class': 'emissive'}
    m['warm'] = {'color': '#e8b060', 'class': 'emissive'}
    m['lamp'] = {'color': '#ffd890', 'class': 'emissive'}
    m['deck_lit'] = {'color': '#f0d8a0', 'class': 'emissive'}
    m['bridge'] = {'color': '#8a9cc4', 'class': 'emissive'}
    m['bridge_dim'] = {'color': '#5c6e9c', 'class': 'emissive'}
    m['tower_lit'] = {'color': '#d8a868', 'class': 'emissive'}
    m['neon_c'] = {'color': '#38c8e0', 'class': 'emissive'}
    m['neon_p'] = {'color': '#e050a0', 'class': 'emissive'}
    m['neon_y'] = {'color': '#e0c040', 'class': 'emissive'}
    m['banner'] = {'color': '#2448a8', 'class': 'emissive'}
    m['hall_roof'] = {'color': '#3a4466'}
    m['wheel'] = {'color': '#9fe0f0', 'class': 'emissive', 'texture': {
        'image': 'art/city_wheel.png', 'projection': 'fit'}}
    m['sail'] = {'color': '#bcc8e0', 'class': 'emissive', 'texture': {
        'image': 'art/city_sail.png', 'projection': 'fit'}}
    m['sign'] = {'color': '#1e3c9a', 'class': 'emissive', 'texture': {
        'image': 'art/city_sign.png', 'projection': 'fit'}}
    for name in REFL:
        m[f'refl_{name}'] = {'color': LANDMARK[REFL[name][0]], 'class': 'emissive', 'texture': {
            'image': f'art/city_refl_{name}.png', 'projection': 'fit'}}
    return m


# ---- geometry helpers

def box(id_, size, mat, centre, faces=None, open_=None, rot=None, modifiers=None):
    t = {'translate': [round(v, 4) for v in centre]}
    if rot:
        t['rotate'] = rot
    n = {'id': id_, 'op': 'box', 'size': [round(v, 4) for v in size], 'material': mat, 'transform': t}
    if faces:
        n['faces'] = faces
    if open_:
        n['open'] = open_
    if modifiers:
        n['modifiers'] = modifiers
    return n


ONLY_BACK = ['top', 'bottom', 'left', 'right', 'front']     # a card: only the face the fight sees (-z)


def card(id_, w, h, mat, centre):
    """A flat card facing the fight (-z): a sign, a lamp, a light."""
    return box(id_, [w, h, 0.2], mat, centre, open_=ONLY_BACK)


def mesh(id_, polys, mats):
    """A mesh node from polygons (each a list of (x, y, z) corners, either winding: turned to face
    `out`, the outward direction given with it as (corners, out)), a material each."""
    verts, faces, fm = [], [], []
    index = {}
    for (poly, out), mat in zip(polys, mats):
        p = [tuple(round(v, 4) for v in q) for q in poly]
        n = np.zeros(3)
        for i in range(len(p)):
            a, b = np.array(p[i]), np.array(p[(i+1) % len(p)])
            n += np.cross(a, b)
        if np.dot(n, out) < 0:
            p = p[::-1]
        f = []
        for q in p:
            if q not in index:
                index[q] = len(verts)
                verts.append(list(q))
            f.append(index[q])
        faces.append(f)
        fm.append(mat)
    return {'id': id_, 'op': 'mesh', 'vertices': verts, 'faces': faces, 'face_materials': fm,
            'material': mats[0]}


ROOF_SEEN_Y = 14.0           # the eye is 6.5 m up (cam_lift raises it a little): a roof above this
                             # is never seen from above
CAM_RIGHT, CAM_LEFT = 32.0, -30.0   # the camera's x: -22 to 24 (a view of the open edge, the angled framing)


def hidden_base(z):
    """About the lowest y seen over the parapet at depth z (the eye 6.5 m up at z -16 to -31, the
    parapet's rail 2.3 m at z = 30), less a margin: a building left of the open edge need not go
    lower (what is under the deck is never seen, but the GPU would draw it)."""
    return 6.5 - (6.5 - 2.3) * (z + 31.0) / 61.0 - 4.0


def block(id_, rank, kind, x0, x1, z0, z1, top, ground=None, mod=None, roof=True):
    """A building: x0..x1 across, z0..z1 deep, from `ground` (default: as low as is seen) up to
    `top`. Its -z face (the one the fight sees) takes the front texture and its sides the side
    texture; the bottom and the +z face are not made, nor a roof above the eye (or any roof when
    `roof` is false) or a side the camera never sees. `mod`: the box's modifiers."""
    t = RANKS[rank]['tex']
    k = kind[0]
    if ground is None:
        ground = SEA_Y if x1 > HALF - 2.0 else max(SEA_Y, hidden_base(z0))
    w, d, h = x1-x0, z1-z0, top-ground
    cx, cy, cz = (x0+x1)/2, (top+ground)/2, (z0+z1)/2
    opened = ['bottom', 'front']
    faces = {'left': f'{t}_{k}s', 'right': f'{t}_{k}s', 'top': f'{t}_roof'}
    if top > ROOF_SEEN_Y or not roof:
        opened.append('top')
        del faces['top']
    if x0 > CAM_RIGHT:
        opened.append('right')
        del faces['right']
    if x1 < CAM_LEFT:
        opened.append('left')
        del faces['left']
    return [box(id_, [w, h, d], f'{t}_{k}f', [cx, cy, cz], open_=opened, faces=faces, modifiers=mod)]


def used(nodes):
    """The material names a node list draws."""
    names = set()
    for n in nodes:
        if 'material' in n:
            names.add(n['material'])
        names.update(n.get('faces', {}).values() if isinstance(n.get('faces'), dict) else [])
        names.update(n.get('face_materials', []))
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


def refl(id_, mat, x, z, w, h, top=SEA_Y - 0.3):
    """A light's reflection: a card below the waterline at the light's x and depth, where its
    mirror image would be (the sea is BG1, behind every polygon, so nothing hides it)."""
    return card(id_, w, h, mat, [x, top - h/2, z - 0.5])


# ---- the district (inland, to the left): Landmark Tower, Queen's Square, the towers

LANDMARK_X, LANDMARK_Z = -112.0, 330.0
LANDMARK_TOP = 118.0             # the shaft's top above the deck; the crown above it


def landmark():
    """Landmark Tower (1993, then Japan's tallest): a square shaft tapering from 44 m to 30 m,
    then the stepped crown, four set-back storeys (a cool lit band, a storey of windows, a white
    lit band, a dark cap), and red aircraft lights at its corners and on top."""
    x, z = LANDMARK_X, LANDMARK_Z
    base, top = hidden_base(z) - 6.0, LANDMARK_TOP
    b, t = 44.0, 30.0
    taper = t / b
    nodes = block('lmt', 'far', 'office', x-b/2, x+b/2, z-b/2, z+b/2, top, ground=base,
                  mod=[{'op': 'taper', 'top': round(taper, 4)}], roof=False)
    cz = z
    y = top
    for i, (s, hgt, mat) in enumerate(((28.0, 5.0, 'crown'), (23.0, 6.0, 'f_of'), (17.0, 3.0, 'crown_w'),
                                       (12.0, 4.0, 'steel'))):
        nodes.append(box(f'lmt_c{i}', [s, hgt, s], mat, [x, y+hgt/2, cz], open_=['bottom', 'front', 'top'],
                         faces={'left': 'f_os', 'right': 'f_os'} if mat == 'f_of' else None))
        y += hgt
    for i, (dx, dz) in enumerate(((-1, -1), (1, -1))):
        nodes.append(box(f'lmt_r{i}', [1.6, 1.6, 1.6], 'red', [x+dx*12.5, top+5.8, cz+dz*12.5],
                         open_=['bottom', 'front', 'top']))
    nodes.append(box('lmt_rt', [1.8, 1.8, 1.8], 'red', [x, y+1.2, cz], open_=['bottom', 'front', 'top']))
    return nodes


def queens():
    """Queen's Square Yokohama (1997): three towers side by side stepping down toward the sea,
    each roof a slope falling seaward (+x), the three slopes one wave; the slopes lit cool."""
    nodes = []
    z0, d = 300.0, 22.0
    base = hidden_base(z0) - 4.0
    for i, (x0, w, hi, lo) in enumerate(((-90.0, 20.0, 78.0, 62.0), (-63.0, 18.0, 56.0, 43.0),
                                          (-38.0, 16.0, 37.0, 27.0))):
        x1 = x0 + w
        prof = [(x0, base), (x1, base), (x1, lo), (x0, hi)]
        polys = [([(x, y, z0) for x, y in prof], (0, 0, -1))]
        mats = ['f_gf']
        # the seaward wall (the camera is always to the right of them) and the roof's slope
        polys.append(([(x1, base, z0), (x1, base, z0+d), (x1, lo, z0+d), (x1, lo, z0)], (1, 0, 0)))
        mats.append('f_gs')
        polys.append(([(x0, hi, z0), (x1, lo, z0), (x1, lo, z0+d), (x0, hi, z0+d)], (0, 1, 0)))
        mats.append('f_roof')
        nodes.append(mesh(f'qs_{i}', polys, mats))
        # the lit edge of the slope's front
        nodes.append(mesh(f'qs_{i}_e', [([(x0, hi-1.6, z0-0.15), (x1, lo-1.6, z0-0.15), (x1, lo, z0-0.15),
                                           (x0, hi, z0-0.15)], (0, 0, -1))], ['crown_w']))
    nodes.append(box('qs_r', [1.4, 1.4, 1.4], 'red', [-88.0, 78.0+1.0, z0+4.0], open_=['bottom', 'front', 'top']))
    return nodes


def district():
    """The office and hotel towers of Minato Mirai inland, behind and around the landmarks: a
    few, with gaps, so the sky and the sea show between them; the tallest with a lit crown
    band, as the district's towers had. Those as far as Landmark Tower take its textures (the
    far rank's larger cells)."""
    nodes = []
    # (x0, width, z0, depth, top, kind, rank, crown)
    spec = [(-262.0, 33.6, 250.0, 22.4, 40.0, 'office', 'mid', False),
            (-222.0, 22.4, 214.0, 16.8, 22.0, 'resid', 'mid', False),
            (-196.0, 28.0, 262.0, 22.4, 56.0, 'office', 'mid', True),
            (-160.0, 22.4, 236.0, 22.4, 30.0, 'office', 'mid', False),
            (-150.0, 16.8, 196.0, 16.8, 12.0, 'resid', 'mid', False),
            (-128.0, 16.8, 270.0, 16.8, 46.0, 'resid', 'mid', True),
            (-104.0, 22.4, 226.0, 16.8, 18.0, 'office', 'mid', False),
            (-30.0, 16.8, 262.0, 16.8, 10.0, 'resid', 'mid', False),
            (-10.0, 22.4, 286.0, 16.8, 18.0, 'office', 'mid', False),
            (-176.0, 16.0, 318.0, 16.0, 72.0, 'office', 'far', True),
            (-240.0, 24.0, 306.0, 16.0, 32.0, 'office', 'far', False)]
    for i, (x0, w, z0, d, top, kind, rank, crown) in enumerate(spec):
        cell = RANKS[rank]['cell'][1]
        top = round(top / cell) * cell
        nodes += block(f'mm_{i}', rank, kind, x0, x0+w, z0, z0+d, top)
        if crown:
            opened = ['bottom', 'top', 'front'] + (['left'] if x0+w < CAM_LEFT else [])
            nodes.append(box(f'mm_{i}_c', [w+0.6, 2.2, d+0.6], 'crown', [x0+w/2, top-2.0, z0+d/2],
                             open_=opened))
    return nodes


# ---- Cosmo Clock 21

WHEEL_X, WHEEL_Z, WHEEL_R, WHEEL_Y = 18.0, 200.0, 34.0, 20.0


def wheel():
    """Cosmo Clock 21 on Shinko: the wheel a single disc facing the fight (its texture: the rim,
    the gondolas' lights, eight spokes and the clock) and its two legs behind it. Its foot and
    its reflection are below the parapet's sight line from wherever the camera goes (left of
    the open edge), so they are not made."""
    x, z, r, y = WHEEL_X, WHEEL_Z, WHEEL_R, WHEEL_Y
    nodes = [card('disc', 2*r, 2*r, 'wheel', [x, y, z])]
    for i, s in enumerate((-1, 1)):
        top = (x + s*1.5, y - 1.0)
        foot = (x + s*15.0, SEA_Y + 9.0)
        dx, dy = top[0]-foot[0], top[1]-foot[1]
        ln = math.hypot(dx, dy)
        ang = math.degrees(math.atan2(dx, dy))
        nodes.append(box(f'leg_{i}', [1.6, ln, 1.6], 'steel', [(top[0]+foot[0])/2, (top[1]+foot[1])/2, z+2.5],
                         rot=[0, 0, round(-ang, 3)], open_=['bottom', 'top', 'front']))
    return nodes


# ---- across the harbour: the Bay Bridge, the Marine Tower

BRIDGE_Z = 356.0
BRIDGE_X0, BRIDGE_X1 = 150.0, 330.0
BRIDGE_TOWERS = (196.0, 270.0)
BRIDGE_DECK = -20.0              # the deck's top
BRIDGE_TOP = 6.0                 # the towers' tops


def bay():
    """Across the harbour: the Bay Bridge (1989), a cable-stayed girder on two towers with its
    lit deck and its stays' outer and middle cables in two fans a tower, and the Marine Tower
    (1961), a slim tapering tower with its lit observation deck and its green beacon."""
    nodes = []
    z = BRIDGE_Z
    x0, x1 = BRIDGE_X0, BRIDGE_X1
    # the deck: a long girder (its face and its lit lamp line)
    nodes.append(box('deck', [x1-x0, 4.0, 14.0], 'steel', [(x0+x1)/2, BRIDGE_DECK-2.0, z],
                     open_=['bottom', 'front', 'left', 'right']))
    nodes.append(card('deck_lit', x1-x0, 0.9, 'deck_lit', [(x0+x1)/2, BRIDGE_DECK-0.6, z-7.2]))
    nodes.append(card('deck_low', x1-x0, 0.7, 'bridge_dim', [(x0+x1)/2, BRIDGE_DECK-3.6, z-7.2]))
    # the towers: two legs each (an H seen from the bridge's ends), a crossbeam at the top, lit pale
    for i, tx in enumerate(BRIDGE_TOWERS):
        for j, dz in enumerate((-7.0, 7.0)):
            nodes.append(box(f't{i}_{j}', [2.0, BRIDGE_TOP-SEA_Y+8.0, 2.0], 'bridge',
                             [tx + (1.6 if j else -1.6), (BRIDGE_TOP+hidden_base(z)-8.0)/2, z+dz],
                             open_=['bottom', 'front', 'left', 'top'] if j else ['bottom', 'front', 'top']))
        nodes.append(card(f't{i}_x', 5.2, 1.6, 'bridge', [tx, BRIDGE_TOP-1.0, z-8.7]))
        # the cables: two fans a side, the outer and the middle stay
        for k, (s, reach) in enumerate(((-1, 40.0), (-1, 20.0), (1, 40.0), (1, 20.0))):
            ax, ay = tx + s*0.5, BRIDGE_TOP - 2.0 - (0 if reach > 30 else 3.0)
            bx, by = tx + s*reach, BRIDGE_DECK
            dx, dy = bx-ax, by-ay
            ln = math.hypot(dx, dy)
            ang = math.degrees(math.atan2(dx, -dy))
            nodes.append(box(f't{i}_c{k}', [2.4, ln, 0.2], 'bridge_dim', [(ax+bx)/2, (ay+by)/2, z-9.0-0.15*(4*i+k)],
                             rot=[0, 0, round(ang, 3)], open_=ONLY_BACK))
    nodes.append(box('bt_r0', [1.8, 1.8, 1.8], 'red', [BRIDGE_TOWERS[0], BRIDGE_TOP+1.0, z-7.0], open_=ONLY_BACK))
    nodes.append(box('bt_r1', [1.8, 1.8, 1.8], 'red', [BRIDGE_TOWERS[1], BRIDGE_TOP+1.0, z-7.0], open_=ONLY_BACK))
    # the Marine Tower (1961): a slim tapering hexagon, its lit observation deck and its beacon
    mx, mz = 132.0, 336.0
    base = hidden_base(mz) - 4.0
    nodes.append({'id': 'marine', 'op': 'cylinder', 'radius': 4.6, 'height': 30.0-base, 'segments': 6,
                  'caps': False, 'material': 'steel',
                  'modifiers': [{'op': 'taper', 'top': 0.45}],
                  'transform': {'translate': [mx, round((30.0+base)/2, 4), mz]}})
    nodes.append({'id': 'marine_deck', 'op': 'cylinder', 'radius': 5.4, 'height': 4.0, 'segments': 6,
                  'caps': False, 'material': 'tower_lit', 'transform': {'translate': [mx, 24.0, mz]}})
    # the moon's glade on the open water (the moon itself is BG1's, low over the bay)
    nodes.append(refl('glade', 'refl_white', 272.0, 366.0, 16.0, 80.0))
    nodes.append(box('marine_mast', [0.8, 6.0, 0.8], 'steel', [mx, 33.0, mz], open_=['bottom', 'front', 'top']))
    nodes.append(box('marine_b', [2.2, 2.2, 2.2], 'green', [mx, 36.5, mz], open_=['bottom', 'front', 'top']))
    return nodes


# ---- by the water on the right: the sail hotel and the exhibition hall

SAIL_X, SAIL_Z = 84.0, 240.0
SAIL_W, SAIL_TOP = 30.0, 32.0


def venue():
    """The sail hotel (1991): a crescent bowed toward the fight, its outline a sail's (rising
    from the landward end to a rounded peak near the seaward one), white and lit from below; and
    the convention centre's exhibition hall beside it (the expo's venue): a long low hall with
    windows along its front, its roof's eaves, the MECH EXPO 2000 sign on its roof and blue
    banners; and the lights' reflections."""
    nodes = []
    # the sail: 8 faces along an arc bowed toward -z; its height a sail's curve
    n = 8
    x0, x1 = SAIL_X - SAIL_W/2, SAIL_X + SAIL_W/2
    base = SEA_Y + 3.0
    pts = []
    for i in range(n+1):
        t = i / n
        x = x0 + (x1-x0)*t
        z = SAIL_Z - 9.0*math.sin(math.pi*t)                       # bowed toward the fight
        u = t / 0.78 if t < 0.78 else 1.0 + (t - 0.78) / 0.22
        k = math.sin(math.pi/2 * u)**0.8 if u <= 1.0 else math.cos(math.pi/2 * (u - 1.0))**0.45
        h = base + (SAIL_TOP-base)*(0.38 + 0.62*k)
        pts.append((x, z, h))
    polys, mats = [], []
    for i in range(n):
        (xa, za, ha), (xb, zb, hb) = pts[i], pts[i+1]
        polys.append(([(xa, base, za), (xb, base, zb), (xb, hb, zb), (xa, ha, za)], (zb-za, 0, -(xb-xa))))
        mats.append('sail')
    sail = mesh('sail', polys, mats)
    # hand UVs: the texture drawn once across the whole face
    uv = []
    for v in sail['vertices']:
        uv.append([round((v[0]-x0)/(x1-x0), 4), round(1.0-(v[1]-base)/(SAIL_TOP-base), 4)])
    sail['uvs'] = uv
    nodes.append(sail)
    nodes.append(card('sail_foot', SAIL_W+4.0, 3.0, 'deck_lit', [SAIL_X, base-1.5, SAIL_Z-10.0]))
    nodes.append(box('sail_r', [1.2, 1.2, 1.2], 'red', [pts[-3][0], pts[-3][2]+0.8, pts[-3][1]], open_=ONLY_BACK))
    nodes.append(refl('sail_refl', 'refl_white', SAIL_X+4.0, SAIL_Z-9.0, 26.0, 40.0))
    # the exhibition hall: 120 m long, low, windows along its front, the roof's eaves, the sign
    hx0, hx1, hz0, hz1 = 112.0, 232.0, 226.0, 266.0
    top = SEA_Y + 20.0
    nodes.append(box('hall', [hx1-hx0, top-SEA_Y, hz1-hz0], 'dark', [(hx0+hx1)/2, (top+SEA_Y)/2, (hz0+hz1)/2],
                     open_=['bottom', 'front', 'right'], faces={'top': 'hall_roof', 'back': 'm_of'}))
    nodes.append(box('eaves', [hx1-hx0+6.0, 2.0, 8.0], 'steel', [(hx0+hx1)/2, top+1.0, hz0-1.0],
                     open_=['bottom', 'front', 'right']))
    nodes.append(card('sign', 92.0, 11.5, 'sign', [(hx0+hx1)/2-8.0, top+7.5, hz0+2.0]))
    for k in range(6):
        nodes.append(card(f'banner_{k}', 4.0, 11.0, 'banner', [hx0+8.0+k*20.0, SEA_Y+9.0, hz0-0.3]))
    nodes.append(refl('hall_refl', 'refl_warm', (hx0+hx1)/2-30.0, hz0, 60.0, 14.0))
    return nodes


# ---- below the open edge: the promenade, the dock and the tall ship

PROM_X0, PROM_X1 = 54.0, 80.0    # the promenade along the quay, running away from the fight
PROM_Z0, PROM_Z1 = 40.0, 300.0
SHIP_X, SHIP_Z, SHIP_L = 106.0, 124.0, 44.0


def quay():
    """Below the open edge: the promenade along the quay running away from the fight, its
    lamps every 10 m, kiosks and sign pylons in neon colours; the dock and the tall ship (a white
    four-masted barque, broadside, her bow to the right, her yards and deck lights); a harbour
    launch with her cabin lit. The ship and the launch have reflections; the promenade's lights
    would not show one (from the roof the quay itself hides where it would be)."""
    nodes = []
    nodes.append(box('prom', [PROM_X1-PROM_X0, 1.0, PROM_Z1-PROM_Z0], 'quay',
                     [(PROM_X0+PROM_X1)/2, QUAY_Y-0.5, (PROM_Z0+PROM_Z1)/2],
                     open_=['bottom', 'left', 'right', 'back', 'front']))
    k = 0
    for z in np.arange(PROM_Z0+50.0, PROM_Z1-40.0, 10.0):          # nearer is below the screen
        nodes.append(card(f'lamp_{k}', 1.8, 1.6, 'lamp', [PROM_X1-1.0, QUAY_Y+5.5, float(z)]))
        k += 1
    # kiosks and sign pylons along the promenade, lit in the old neon colours
    for i, (z, mat) in enumerate(((84.0, 'neon_c'), (128.0, 'neon_p'), (176.0, 'neon_y'), (222.0, 'neon_c'))):
        nodes.append(box(f'kiosk_{i}', [6.0, 4.0, 7.0], 'dark', [PROM_X1-7.0, QUAY_Y+2.0, z],
                         open_=['bottom', 'front', 'right']))
        nodes.append(card(f'kiosk_{i}_s', 6.2, 1.8, mat, [PROM_X1-7.0, QUAY_Y+4.6, z-3.6]))
    for i, (z, mat) in enumerate(((104.0, 'neon_p'), (198.0, 'neon_c'))):
        nodes.append(card(f'pylon_{i}', 1.6, 7.0, mat, [PROM_X1-3.0, QUAY_Y+4.5, z]))
    # a harbour launch out on the water, her cabin lit, her running lights
    bx, bz = 152.0, 196.0
    nodes.append(card('launch', 16.0, 2.4, 'hull_band', [bx, SEA_Y+1.2, bz]))
    nodes.append(card('launch_cab', 7.0, 2.2, 'warm', [bx-2.0, SEA_Y+3.4, bz+0.3]))
    nodes.append(card('launch_g', 0.9, 0.9, 'green', [bx+7.6, SEA_Y+2.8, bz-0.2]))
    nodes.append(refl('launch_r', 'refl_warm', bx-2.0, bz, 7.0, 12.0))
    # the dock: the quay's arm on the far side of the ship
    nodes.append(box('pier', [56.0, 1.0, 8.0], 'quay', [SHIP_X+2.0, QUAY_Y-0.5, SHIP_Z+16.0],
                     open_=['bottom', 'front', 'right', 'left'], faces={'back': 'quay_edge'}))
    # the tall ship: a white hull broadside to the fight, the bow to the right, four masts (the
    # three forward ones square-rigged, three yards each; the aftmost, a barque's, without), her
    # deck lights
    sx, sz, ln = SHIP_X, SHIP_Z, SHIP_L
    hull_top = SEA_Y + 6.0
    bow = sx + ln/2
    stern = sx - ln/2
    prof = [(stern, SEA_Y), (bow - 6.0, SEA_Y), (bow + 4.0, hull_top + 0.6), (stern - 1.0, hull_top)]
    polys = [([(x, y, sz) for x, y in prof], (0, 0, -1))]
    mats = ['hull']
    polys.append(([(stern - 1.0, hull_top, sz), (bow + 4.0, hull_top + 0.6, sz), (bow + 4.0, hull_top + 0.6, sz+9.0),
                   (stern - 1.0, hull_top, sz+9.0)], (0, 1, 0)))
    mats.append('quay')
    nodes.append(mesh('hull', polys, mats))
    nodes.append(card('hull_band', ln + 6.0, 0.8, 'hull_band', [sx + 2.0, SEA_Y + 2.2, sz - 0.25]))
    masts = [stern + 7.0 + i*9.5 for i in range(4)]
    for i, mx in enumerate(masts):
        h = 34.0 if i in (1, 2) else 31.0
        nodes.append(card(f'mast_{i}', 0.8, h, 'mast', [mx, hull_top + h/2, sz + 4.0]))
        for j, (yy, yw) in enumerate(((0.42, 14.0), (0.66, 11.0), (0.86, 8.0))):
            if i == 0:
                continue
            nodes.append(card(f'yard_{i}_{j}', yw, 0.6, 'mast', [mx, hull_top + h*yy, sz + 3.9 - 0.15*i]))
    nodes.append(card('deck_lights', ln - 6.0, 0.6, 'lamp', [sx, hull_top + 1.2, sz + 3.0]))
    nodes.append(refl('ship_refl', 'refl_white', sx + 2.0, sz, ln * 0.8, 10.0))
    return nodes


def cameras():
    return [
        {'name': 'start', 'eye': [0.0, 6.5, -19.5], 'target': [0.0, 4.0, 120.0]},
        {'name': 'whole', 'eye': [4.0, 6.5, -31.2], 'target': [4.0, 4.0, 120.0]},
        {'name': 'edge', 'eye': [22.0, 6.5, -16.2], 'target': [40.0, -8.0, 120.0]},
    ]


def main():
    write_tiles()
    out = {
        'city_mm': recipe('stage_roof_city_mm', landmark() + queens(), 300),
        'city_towers': recipe('stage_roof_city_towers', district(), 300),
        'city_wheel': recipe('stage_roof_city_wheel', wheel(), 200),
        'city_bay': recipe('stage_roof_city_bay', bay(), 400),
        'city_venue': recipe('stage_roof_city_venue', venue(), 300),
        'city_quay': recipe('stage_roof_city_quay', quay(), 600),
    }
    for p in HERE.glob('city_*.asset.json'):
        p.unlink()
    for k, v in out.items():
        (HERE/f'{k}.asset.json').write_text(json.dumps(v, indent=1)+'\n')
    (HERE/'cameras.json').write_text(json.dumps(cameras(), indent=1)+'\n')


if __name__ == '__main__':
    main()
