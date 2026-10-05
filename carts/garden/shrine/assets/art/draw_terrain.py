"""Draws the shrine's ground textures (terrain_*.png beside this file), the textured terrain
materials of shrine.world.json: forest floor, the mountain's leaf litter, moss, earth, trail
dirt, raked gravel, the approach's paving, the terrace's ashlar, rock, the steps, the pond's
shore and bed, and the street's asphalt and sidewalk.

Authored art: run once with `python3 carts/garden/shrine/assets/art/draw_terrain.py` and commit
the PNGs; nothing rebuilds them. Needs Pillow. Each texture is drawn from a fixed seed, so a
rerun gives the same pictures. Every texture is a 32 x 32 tile that repeats seamlessly (every
mark wraps around the edges), 4-bit (15 colours at most), in the shrine palette
(carts/garden/shrine/STYLE.md), late October: maple red, ginkgo gold, brown oak and cedar
litter on the ground.
"""

import math
import random
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
N = 32


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


class Tile:
    def __init__(self, fill, seed):
        self.px = [[fill] * N for _ in range(N)]
        self.r = random.Random(seed)

    def set(self, x, y, c):
        self.px[y % N][x % N] = c

    def get(self, x, y):
        return self.px[y % N][x % N]

    def noise(self, colours, cells=4, bias=0.0):
        """Mottles the whole tile: a wrapping value noise of `cells` lattice cells a side picks
        among `colours` (darkest first)."""
        r = self.r
        g = [[r.random() for _ in range(cells)] for _ in range(cells)]
        g2 = [[r.random() for _ in range(cells * 2)] for _ in range(cells * 2)]

        def sample(grid, n, x, y):
            fx, fy = x * n / N, y * n / N
            i, j = int(fx), int(fy)
            tx, ty = fx - i, fy - j
            tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
            a, b = grid[j % n][i % n], grid[j % n][(i + 1) % n]
            c, d = grid[(j + 1) % n][i % n], grid[(j + 1) % n][(i + 1) % n]
            return (a + (b - a) * tx) * (1 - ty) + (c + (d - c) * tx) * ty

        for y in range(N):
            for x in range(N):
                v = 0.65 * sample(g, cells, x, y) + 0.35 * sample(g2, cells * 2, x, y) + bias
                v += (r.random() - 0.5) * 0.18
                k = max(0, min(len(colours) - 1, int(v * len(colours))))
                self.px[y][x] = colours[k]

    def scatter(self, colours, count):
        for _ in range(count):
            self.set(self.r.randrange(N), self.r.randrange(N), self.r.choice(colours))

    def blob(self, cx, cy, rx, ry, c, rough=0.0):
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                d = ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2
                if d <= 1 + (self.r.random() - 0.5) * rough:
                    self.set(x, y, c)

    def leaf(self, x, y, c, dark=None, kind=None):
        """A fallen leaf, 1-5 texels, turned at random: a maple's (a 2 x 2 block and a lobe), a
        ginkgo's fan (three in an L), an oval (two or three in a line) or a fleck (one or two).
        Lopsided on purpose: a symmetric cross reads as a mark, not a leaf."""
        r = self.r
        kind = kind or r.choice(('maple', 'fan', 'oval'))
        sx, sy = r.choice((-1, 1)), r.choice((-1, 1))
        if kind == 'maple':
            cells = [(0, 0), (1, 0), (0, 1), (1, 1), r.choice(((2, 0), (0, 2), (2, 1), (1, 2)))]
            if r.random() < 0.5:
                cells.pop(r.randrange(4))
        elif kind == 'fan':
            cells = [(0, 0), (1, 0), (0, 1)]
        elif kind == 'oval':
            cells = r.choice(([(0, 0), (1, 0)], [(0, 0), (1, 1)], [(0, 0), (1, 0), (2, 1)], [(0, 0), (1, 1), (1, 2)]))
        else:
            cells = r.choice(([(0, 0)], [(0, 0), (1, 0)], [(0, 0), (0, 1)]))
        for dx, dy in cells:
            self.set(x + sx * dx, y + sy * dy, c)
        if dark and len(cells) > 2:
            dx, dy = cells[-1]
            self.set(x + sx * dx, y + sy * dy, dark)

    def streak(self, x, y, length, angle, c):
        for k in range(length):
            self.set(round(x + k * math.cos(angle)), round(y + k * math.sin(angle)), c)

    def save(self, name):
        img = Image.new('RGBA', (N, N))
        img.putdata([rgb(c) for row in self.px for c in row])
        colours = {c for row in self.px for c in row}
        assert len(colours) <= 15, (name, len(colours))
        img.save(HERE / f'terrain_{name}.png')


# The fallen leaves of late October (STYLE.md: maple, ginkgo, leaf litter).
MAPLE = ('#c8301e', '#e0502a', '#e8782a')
GINKGO = ('#f0c030', '#d89a20')
BROWN = ('#9a5a2e', '#7a4a26')


def leaves(t, count, colours, dark=None, kinds=None):
    for _ in range(count):
        t.leaf(t.r.randrange(N), t.r.randrange(N), t.r.choice(colours), dark, t.r.choice(kinds) if kinds else None)


def forest_floor():
    """The forest's ground: dark humus and cedar needles under a scatter of every colour of leaf."""
    t = Tile('#5a4c2c', 101)
    t.noise(['#3e3420', '#4a3e26', '#5a4c2c', '#6e6236'], cells=4)
    for _ in range(14):
        t.streak(t.r.randrange(N), t.r.randrange(N), t.r.randint(2, 4), t.r.uniform(0, math.pi), '#2e2618')
    leaves(t, 10, BROWN, kinds=('oval',))
    leaves(t, 9, MAPLE, dark='#8a2418', kinds=('maple',))
    leaves(t, 6, GINKGO, kinds=('fan',))
    t.save('floor')


def litter():
    """The mountain's deep litter: drifts of rust and brown leaves, red and gold on top."""
    t = Tile('#7a4e2a', 102)
    t.noise(['#5a3a20', '#6a4426', '#7a4e2a', '#8a5a30'], cells=4)
    leaves(t, 22, ('#9a5a2e', '#a86a34', '#6a3a1e'), kinds=('oval', 'maple'))
    leaves(t, 10, MAPLE, dark='#8a2418', kinds=('maple',))
    leaves(t, 5, GINKGO, kinds=('fan',))
    t.scatter(['#3e2a18'], 14)
    t.save('litter')


def moss():
    """Moss cushions in two greens, a few needles and a few red maple leaves fallen on them."""
    t = Tile('#5f7a34', 103)
    t.noise(['#3e5a26', '#4f6a2c', '#5f7a34', '#6f8a3c'], cells=5)
    for _ in range(10):
        t.blob(t.r.uniform(0, N), t.r.uniform(0, N), t.r.uniform(1.2, 2.4), t.r.uniform(1.0, 2.0), '#7c9a44', 0.5)
    t.scatter(['#8aa850', '#34501e'], 30)
    leaves(t, 4, MAPLE, kinds=('maple',))
    leaves(t, 2, GINKGO, kinds=('fan',))
    t.save('moss')


def earth():
    """Banks and trail sides: bare brown earth, roots, stones, a few leaves."""
    t = Tile('#6a4a30', 104)
    t.noise(['#4e3622', '#5a3e28', '#6a4a30', '#7a5a3c'], cells=4)
    for _ in range(4):
        x, y, a = t.r.randrange(N), t.r.randrange(N), t.r.uniform(-0.4, 0.4)
        t.streak(x, y, t.r.randint(5, 9), a, '#3a2818')
    for _ in range(7):
        x, y = t.r.uniform(0, N), t.r.uniform(0, N)
        t.blob(x, y, 1.1, 0.9, '#8e887c')
        t.set(int(x), int(y + 1), '#5e5a52')
    leaves(t, 6, BROWN + MAPLE[:1], kinds=('oval', 'fleck'))
    t.save('earth')


def path():
    """The trail: packed light dirt with grit and pebbles, a leaf or two blown onto it."""
    t = Tile('#8a6a48', 105)
    t.noise(['#7a5c3c', '#8a6a48', '#8a6a48', '#9a7a56'], cells=3)
    t.scatter(['#a88a64', '#6a4e34'], 70)
    for _ in range(9):
        x, y = t.r.randrange(N), t.r.randrange(N)
        t.set(x, y, '#b4ae9e')
        t.set(x + 1, y, '#b4ae9e')
        t.set(x, y + 1, '#6a665e')
    leaves(t, 3, MAPLE[1:] + GINKGO[:1], kinds=('maple', 'fan'))
    t.save('path')


def gravel():
    """Raked white gravel: furrows every four texels (30 cm), grit, and a stray maple leaf."""
    t = Tile('#d4ccb8', 106)
    for y in range(N):
        for x in range(N):
            k = (y + round(0.9 * math.sin(2 * math.pi * x / N))) % 4
            t.px[y][x] = ('#b8b09c', '#d4ccb8', '#e2dac8', '#d4ccb8')[k]
    for _ in range(90):
        x, y = t.r.randrange(N), t.r.randrange(N)
        c = t.get(x, y)
        t.set(x, y, {'#b8b09c': '#a8a090', '#d4ccb8': t.r.choice(('#c4bca8', '#e2dac8')),
                     '#e2dac8': '#eee8da'}.get(c, c))
    t.leaf(9, 12, '#c8301e', None, 'oval')
    t.save('gravel')


def slabs(fill, tones, joint, moss, seed, rows=4, cols=2):
    """Stone slabs in running bond: rows of `cols` slabs, every other row shifted half a slab;
    each slab its own tone with a little grit, dark joints, moss in some of them."""
    t = Tile(fill, seed)
    h, w = N // rows, N // cols
    for row in range(rows):
        shift = (w // 2) * (row % 2)
        for col in range(cols):
            tone = t.r.choice(tones)
            x0, y0 = col * w + shift, row * h
            for y in range(y0, y0 + h):
                for x in range(x0, x0 + w):
                    t.set(x, y, tone)
            for _ in range(w * h // 9):
                t.set(x0 + t.r.randrange(1, w), y0 + t.r.randrange(1, h), t.r.choice(tones))
            for x in range(x0, x0 + w):
                t.set(x, y0, joint)
            for y in range(y0, y0 + h):
                t.set(x0, y, joint)
            # a worn, lighter edge on the slab's lower side
            for x in range(x0 + 1, x0 + w):
                if t.r.random() < 0.5:
                    t.set(x, y0 + h - 1, tones[-1])
    for _ in range(14):
        x, y = t.r.randrange(N), t.r.randrange(N)
        if t.get(x, y) == joint:
            t.set(x, y, moss)
            t.set(x + 1, y, moss)
    return t


def paving():
    """The approach's paving: long granite slabs, 1.2 m by 0.6 m, mossy joints."""
    t = slabs('#b4ae9e', ('#a8a294', '#b4ae9e', '#bcb6a6', '#c4bfb0'), '#7a766c', '#7a8050', 107)
    t.leaf(20, 6, '#c8301e', None, 'oval')
    t.save('paving')


def steps():
    """The stone steps: worn darker slabs, moss in the joints. No leaves: the same picture is
    drawn at twice the scale on the wide steps (shrine.world.json's stairs_wide), where a leaf
    would be half a metre across; the litter patches scattered over the level bring them."""
    t = slabs('#9a9488', ('#8e887c', '#9a9488', '#a49e92'), '#6a665e', '#6a7a40', 108, rows=2, cols=2)
    t.save('steps')


def ashlar():
    """The terrace's retaining wall: big rough-faced granite blocks, moss creeping up the joints."""
    t = Tile('#8e887c', 109)
    rows = (0, 9, 16, 25)
    for i, y0 in enumerate(rows):
        y1 = rows[i + 1] if i + 1 < len(rows) else N
        start = x = t.r.randrange(N)
        while x < start + N:
            w = min(t.r.randint(9, 14), start + N - x)
            tone = t.r.choice(('#7e786c', '#8e887c', '#a09a8c', '#9a9284'))
            for y in range(y0, y1):
                for xx in range(x, x + w):
                    t.set(xx, y, tone)
            for _ in range(w * (y1 - y0) // 6):
                t.set(x + t.r.randrange(1, w), y0 + t.r.randrange(1, y1 - y0), t.r.choice(('#7e786c', '#a09a8c', '#b4ae9e')))
            for y in range(y0, y1):
                t.set(x, y, '#5e5a52')
            for xx in range(x, x + w):
                t.set(xx, y0, '#5e5a52')
                if t.r.random() < 0.6:
                    t.set(xx, y1 - 1, '#6a665e')
            x += w
    for _ in range(18):
        x, y = t.r.randrange(N), t.r.randrange(N)
        if t.get(x, y) in ('#5e5a52', '#6a665e'):
            t.set(x, y, '#6a7a44')
            t.set(x, y + 1, '#7a8050')
    t.save('stone')


def rock():
    """The mountain's rock and cliffs: grey strata, cracks, lichen and moss."""
    t = Tile('#6a665e', 110)
    for y in range(N):
        band = ('#5a564e', '#6a665e', '#7a766c', '#6a665e', '#625e56')[(y // 3 + (y // 7)) % 5]
        for x in range(N):
            t.px[y][x] = band
    for _ in range(120):
        x, y = t.r.randrange(N), t.r.randrange(N)
        t.set(x, y, t.r.choice(('#5a564e', '#7a766c', '#86827a')))
    for _ in range(6):
        x, y = t.r.randrange(N), t.r.randrange(N)
        for k in range(t.r.randint(4, 8)):
            t.set(x, y + k, '#3a3832')
            x += t.r.choice((-1, 0, 0, 1))
    for _ in range(6):
        t.blob(t.r.uniform(0, N), t.r.uniform(0, N), t.r.uniform(1.0, 2.2), t.r.uniform(0.8, 1.5), '#8a8a6a', 0.6)
    for _ in range(5):
        t.blob(t.r.uniform(0, N), t.r.uniform(0, N), t.r.uniform(1.0, 2.0), t.r.uniform(0.8, 1.4), '#5a6a3a', 0.6)
    t.scatter(['#4a463e'], 20)
    t.save('rock')


def pond_bed():
    """The pond's shore and bed: dark mud, pebbles, sunken leaves."""
    t = Tile('#4e4632', 111)
    t.noise(['#3e3828', '#4e4632', '#5a5238'], cells=4)
    for _ in range(12):
        x, y = t.r.uniform(0, N), t.r.uniform(0, N)
        t.blob(x, y, t.r.uniform(0.7, 1.4), t.r.uniform(0.6, 1.1), t.r.choice(('#6a665e', '#7a766c', '#8e887c')))
    leaves(t, 6, ('#6a3a20', '#8a4a26', '#a8642a'), kinds=('oval', 'maple'))
    t.scatter(['#2e2a1e'], 18)
    t.save('pond_bed')


def asphalt():
    """The city road: worn asphalt with grit and a tar-sealed crack."""
    t = Tile('#4a4a50', 112)
    t.noise(['#424248', '#4a4a50', '#4a4a50', '#525258'], cells=3)
    t.scatter(['#5c5c62', '#3a3a40', '#68686c'], 120)
    x = 4
    for y in range(N):
        t.set(x, y, '#323236')
        x += t.r.choice((-1, 0, 0, 1)) if 0 < y < N - 4 else 0
    t.save('asphalt')


def sidewalk():
    """The sidewalk: square concrete pavers, 40 cm, a few stained and one leaf."""
    t = Tile('#b8b4a8', 113)
    for y in range(N):
        for x in range(N):
            t.px[y][x] = '#9c988c' if x % 8 == 0 or y % 8 == 0 else '#b8b4a8'
    for by in range(4):
        for bx in range(4):
            tone = t.r.choice(('#b8b4a8', '#b8b4a8', '#c4c0b4', '#aca89c'))
            for y in range(by * 8 + 1, by * 8 + 8):
                for x in range(bx * 8 + 1, bx * 8 + 8):
                    t.px[y][x] = tone
    t.scatter(['#a8a49a', '#c8c4b8'], 50)
    t.leaf(13, 21, '#f0c030', None, 'fleck')
    t.save('sidewalk')


if __name__ == '__main__':
    for draw in (forest_floor, litter, moss, earth, path, gravel, paving, steps, ashlar, rock, pond_bed,
                 asphalt, sidewalk):
        draw()
