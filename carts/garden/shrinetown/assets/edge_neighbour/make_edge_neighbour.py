#!/usr/bin/env python3
"""Writes the backs of the neighbours' buildings that close the shrine town's south, east and west
edges (README.md, "The frame"): art/facade_a.png (the balcony side of an apartment block),
art/facade_b.png (the back of an office building) and one recipe per grey-box neighbour,
edge_neighbour_s0..s8, _e0..e2, _w0..w2.asset.json, at the grey box's sizes (notes/gen_town.py,
"the level's frame": NEIGHBOURS below is that table).

Each is a cheap box seen from far and from rooftops: the face toward the level carries one
repeating 64 x 64 façade tile (6 m a repeat: two bays of 3 m, two storeys of 3 m; 9.4 cm a
texel), lined up so a storey's slab edge is the roof line; the ends and the roof are flat
palette colours; a stair house stands on the roof. 18 triangles before the kit splits the façade
(a face repeats a 64-texel tile at most three times: 18 m), 23-57 after; from LOD_FAR (60 m) the
same box and stair house, 18 triangles, its façade a 16 x 16 far tile (art/facade_a_far.png,
facade_b_far.png: each 4 x 4 block of the 64 x 64 tile in its commonest colour, so the windows,
the slabs and the lit panes stay where they were). All four tiles use one set of 15 colours, so
they share one 4-bit palette; about 4,700 bytes of VRAM for the four, whatever the number of
buildings.

Origin and facing: the façade faces -Z (the Asset Kit's front); the origin is INSET (0.2 m) in
front of the middle of its foot, so that it lies inside the level's cell when the façade stands
on the level's edge, and the box reaches DEPTH metres behind the façade. Each replaces the grey
box's neighbour_KEY at the same position (0.2 m inside the edge), with the yaw that turns the
front to the level (GROUND.md, "Edges"). Collision: "self" (the box's faces).

Night: the lit-window glass is its own colour (LIT below), so a palette variant lights some
windows: "texels": {"edge_neighbour_s0.facade": {"#3e4a5e": "#e8c878"}} (WORLDKIT.md, "Night");
make_world.py does that for every neighbour, both levels (NIGHT_TEXELS below).

Run: python3 carts/garden/shrinetown/assets/edge_neighbour/make_edge_neighbour.py   (Pillow)
"""
import json
import random
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ART = HERE / 'art'
N = 64
REPEAT = 6.0          # metres a repeat: two bays, two storeys
LOD_FAR = 60          # from here on the box and the stair house, the façade a 16 x 16 far tile
DEPTH = 8.0
INSET = 0.2

# name: (face width, height, façade); from gen_town.py's frame (west heights are its h - 4)
NEIGHBOURS = {
    **{f's{k}': (x2 - x1, h, 'ab'[k % 2]) for k, (x1, x2, h) in enumerate(
        [(0, 32, 26), (32, 64, 22), (64, 96, 28), (96, 136, 24), (136, 184, 22), (184, 216, 27),
         (216, 256, 23), (256, 288, 26), (288, 320, 24)])},
    **{f'e{k}': (z2 - z1, h, 'ba'[k % 2]) for k, (z1, z2, h) in enumerate([(0, 36, 25), (36, 72, 22), (72, 104, 27)])},
    **{f'w{k}': (z2 - z1, h - 4, 'ab'[k % 2]) for k, (z1, z2, h) in enumerate([(0, 36, 25), (36, 72, 22), (72, 104, 27)])},
}

# One palette for both tiles (15 colours).
WALL, WALL2, SLAB, SHADOW = '#c8c4b8', '#b4b0a4', '#dcd8cc', '#8e8c88'
GLASS, LIT, SHEEN = '#34404e', '#3e4a5e', '#5e6e84'
PARAPET, STAIN = '#d2cec2', '#a4a096'
AC, GRILLE, PIPE = '#e4e2da', '#6a6a6e', '#7a7872'
FUTON, FUTON2, CLOTH = '#b0806e', '#6a8aa4', '#ecebe6'
ROOF, END = '#7e7c76', '#b4b0a4'
FAR = '#a09e9a'        # both façades' mean colour: the stair house
LIT_NIGHT = '#e8c878'  # the lit panes at night


def night_texels(name):
    """The night variant's exact colours for a neighbour (make_world.py's town region): its lit
    panes, near and far."""
    return {f'{name}.{m}': {LIT: LIT_NIGHT} for m in ('facade', 'facade_far')}


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


class Tile:
    def __init__(self, fill, seed):
        self.px = [[fill] * N for _ in range(N)]
        self.r = random.Random(seed)

    def set(self, x, y, c):
        self.px[y % N][x % N] = c

    def get(self, x, y):
        return self.px[y % N][x % N]

    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.set(x, y, c)

    def save(self, name):
        n = len({c for row in self.px for c in row})
        assert n <= 15, (name, n)
        img = Image.new('RGB', (N, N))
        img.putdata([rgb(c) for row in self.px for c in row])
        ART.mkdir(exist_ok=True)
        img.save(ART / f'{name}.png')
        self.save_far(name)

    def save_far(self, name, k=4):
        """The far tile: each k x k block in its commonest colour (ties to the first seen)."""
        m = N // k
        out = []
        for by in range(m):
            for bx in range(m):
                block = [self.px[by * k + y][bx * k + x] for y in range(k) for x in range(k)]
                out.append(max(dict.fromkeys(block), key=block.count))
        img = Image.new('RGB', (m, m))
        img.putdata([rgb(c) for c in out])
        img.save(ART / f'{name}_far.png')


def wall_grain(t, count=160):
    for _ in range(count):
        x, y = t.r.randrange(N), t.r.randrange(N)
        if t.get(x, y) == WALL:
            t.set(x, y, WALL2)


def drip(t, x, y, n):
    for k in range(n):
        if t.get(x, y + k) in (WALL, PARAPET, WALL2):
            t.set(x, y + k, STAIN)


def facade_a():
    """The balcony side of an apartment block: per storey (32 rows, the slab edge on top), a
    sliding window behind the balcony, the balcony's solid parapet with its rail, an air
    conditioner on a bracket between bays, laundry, a futon airing over a parapet, a drain pipe."""
    t = Tile(WALL, 301)
    wall_grain(t)
    for s in range(2):
        y0 = s * 32
        t.rect(0, y0, N, y0 + 2, SLAB)
        t.rect(0, y0 + 2, N, y0 + 3, SHADOW)
        for b in range(2):
            x0 = b * 32
            lit = (s + b) % 2 == 0
            t.rect(x0 + 4, y0 + 4, x0 + 28, y0 + 19, STAIN)                   # the frame
            t.rect(x0 + 5, y0 + 5, x0 + 27, y0 + 19, LIT if lit else GLASS)
            for x in (x0 + 15, x0 + 16):                                        # the sash
                for y in range(y0 + 5, y0 + 19):
                    t.set(x, y, STAIN)
            for k in range(5):                                                  # a sheen
                t.set(x0 + 7 + k, y0 + 6 + k, SHEEN)
            t.rect(x0 + 1, y0 + 19, x0 + 31, y0 + 20, SLAB)                    # the rail
            t.rect(x0 + 1, y0 + 20, x0 + 31, y0 + 30, PARAPET)                 # the parapet
            t.rect(x0 + 1, y0 + 30, x0 + 31, y0 + 32, SHADOW)
            for x in range(x0 + 3, x0 + 30, 5):
                drip(t, x + t.r.randrange(2), y0 + 21, t.r.randint(2, 6))
        # laundry on the upper storey's left bay, a futon on the lower's right bay
    for k, c in enumerate((CLOTH, FUTON2, CLOTH, CLOTH, CLOTH, FUTON2)):
        x = 7 + k * 3
        t.rect(x, 12, x + 2, 12 + 4 + (k % 3), c)
    for x in range(6, 26):
        t.set(x, 11, PIPE)
    t.rect(42, 47, 54, 54, FUTON)
    # air conditioners on brackets between the bays (u 28-36 wraps over the bay line)
    for y0 in (8, 40):
        t.rect(27, y0, 37, y0 + 7, AC)
        for x in range(28, 36, 2):
            t.set(x, y0 + 2, GRILLE)
            t.set(x + 1, y0 + 4, GRILLE)
        t.rect(27, y0 + 7, 37, y0 + 8, SHADOW)
    # the drain pipe at the tile's edge (u 0-1), full height
    for y in range(N):
        t.set(0, y, PIPE)
        t.set(1, y, SHADOW if y % 16 == 0 else PIPE)
    t.save('facade_a')


def facade_b():
    """The back of an office building: per storey, two tall windows a bay with a mullion, sills
    and rust-stain streaks under them, a spandrel band, an air conditioner and a pair of pipes."""
    t = Tile(WALL2, 302)
    for y in range(N):
        for x in range(N):
            if t.r.random() < 0.12:
                t.set(x, y, WALL)
    for s in range(2):
        y0 = s * 32
        t.rect(0, y0, N, y0 + 2, SLAB)
        t.rect(0, y0 + 2, N, y0 + 3, SHADOW)
        t.rect(0, y0 + 24, N, y0 + 32, WALL)                                     # spandrel band
        for b in range(2):
            x0 = b * 32
            for w, (a0, a1) in enumerate(((4, 14), (17, 27))):
                lit = (s * 4 + b * 2 + w) % 3 == 0
                t.rect(x0 + a0, y0 + 6, x0 + a1, y0 + 21, STAIN)
                t.rect(x0 + a0 + 1, y0 + 7, x0 + a1 - 1, y0 + 21, LIT if lit else GLASS)
                for y in range(y0 + 7, y0 + 21):
                    t.set(x0 + (a0 + a1) // 2, y, STAIN)
                t.set(x0 + a0 + 2, y0 + 8, SHEEN)
                t.set(x0 + a0 + 3, y0 + 9, SHEEN)
                t.rect(x0 + a0 - 1, y0 + 21, x0 + a1 + 1, y0 + 22, SLAB)       # the sill
                for x in range(x0 + a0, x0 + a1, 3):
                    drip(t, x + t.r.randrange(2), y0 + 22, t.r.randint(2, 7))
    for y0 in (24, 56):                                                         # air conditioners
        t.rect(5, y0 + 1, 13, y0 + 7, AC)
        for x in range(6, 12, 2):
            t.set(x, y0 + 3, GRILLE)
        t.rect(5, y0 + 7, 13, y0 + 8, SHADOW)
    for y in range(N):                                                          # two pipes
        t.set(30, y, PIPE)
        t.set(33, y, PIPE)
        if y % 16 == 4:
            t.set(31, y, SHADOW)
            t.set(32, y, SHADOW)
    t.save('facade_b')


def recipe(name, width, height, style):
    w2 = width / 2
    # u = x / REPEAT + offset: the façade's left edge on a repeat; v = -y / REPEAT + offset: the
    # roof line on a repeat (the slab edge at the top of the tile)
    offset = [round((w2 / REPEAT) % 1, 4), round((height / REPEAT) % 1, 4)]
    # the stair house on the roof: 4 x 3 x 4 m, a third of the way along, set back 2 m
    hx = round(-w2 / 3, 2)
    z0, z1 = INSET, INSET + DEPTH
    v = [[-w2, 0, z0], [w2, 0, z0], [w2, height, z0], [-w2, height, z0],
         [-w2, 0, z1], [w2, 0, z1], [w2, height, z1], [-w2, height, z1]]
    faces = [[0, 1, 2, 3][::-1], [3, 2, 6, 7][::-1], [4, 0, 3, 7][::-1], [1, 5, 6, 2][::-1]]
    house = {'id': 'stair_house', 'op': 'box', 'size': [4, 3, 4], 'material': 'house',
             'open': ['bottom'], 'faces': {'top': 'roof'},
             'transform': {'translate': [hx, height + 1.5, INSET + 4.0]}}
    return {
        'format': 'mei-asset', 'version': 1, 'name': name,
        'budget': {'triangles': 60},
        'lighting': {'mode': 'vertical', 'ambient': 0.5},
        'verification': {'required': True, 'depth': True, 'perspective': True},
        'materials': {
            'facade': {'color': WALL, 'tag': 'wall',
                       'texture': {'image': f'art/facade_{style}.png', 'projection': 'box',
                                   'scale': [REPEAT, REPEAT], 'offset': offset}},
            'end': {'color': END, 'palette': True, 'tag': 'wall'},
            'roof': {'color': ROOF, 'palette': True, 'tag': 'roof'},
            'house': {'color': FAR, 'palette': True, 'tag': 'wall'},
            'facade_far': {'color': WALL, 'tag': 'wall',
                           'texture': {'image': f'art/facade_{style}_far.png', 'projection': 'box',
                                       'scale': [REPEAT, REPEAT], 'offset': offset}},
        },
        'nodes': [
            {'id': 'body', 'op': 'mesh', 'vertices': v, 'faces': faces,
             'face_materials': ['facade', 'roof', 'end', 'end']},
            house,
        ],
        'lod': {'levels': [{'distance': LOD_FAR, 'nodes': [
            {'id': 'body', 'op': 'mesh', 'vertices': v, 'faces': faces,
             'face_materials': ['facade_far', 'roof', 'end', 'end']},
            house]}]},
    }


if __name__ == '__main__':
    facade_a()
    facade_b()
    for old in HERE.glob('edge_neighbour_*.asset.json'):
        old.unlink()
    for key, (width, height, style) in NEIGHBOURS.items():
        name = f'edge_neighbour_{key}'
        (HERE / f'{name}.asset.json').write_text(json.dumps(recipe(name, width, height, style), indent=1) + '\n')
        print(f'{name}: {width} x {height} m, facade_{style}')
