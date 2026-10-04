"""Draws the forest structures' textures (forest_*.png beside this file).

Authored art: run once with `python3 carts/garden/shrine/assets/art/draw_forest.py` and commit the
PNGs; nothing rebuilds them. Needs Pillow. Each texture is drawn from a fixed seed, so a rerun
gives the same pictures. Every texture is 4-bit (15 colours at most), in the shrine palette
(carts/garden/shrine/STYLE.md).
"""

import random
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
CLEAR = (0, 0, 0, 0)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


class Canvas:
    def __init__(self, w, h, fill):
        self.w, self.h = w, h
        self.img = Image.new('RGBA', (w, h), rgb(fill) if fill else CLEAR)
        self.px = self.img.load()

    def set(self, x, y, c, wrap=True):
        if wrap:
            x %= self.w
            y %= self.h
        elif not (0 <= x < self.w and 0 <= y < self.h):
            return
        self.px[x, y] = rgb(c)

    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.set(x, y, c)

    def save(self, name):
        colours = {p for _, p in self.img.getcolors(4096) if p[3] >= 128}
        assert len(colours) <= 15, (name, len(colours))
        self.img.save(HERE / name)


def leaf(c, r, x, y, colour, wrap=True):
    """A fallen leaf: two or three texels."""
    c.set(x, y, colour, wrap)
    c.set(x + 1, y, colour, wrap)
    if r.random() < 0.6:
        c.set(x, y + 1, colour, wrap)


AUTUMN = ['#c8301e', '#e0502a', '#e8782a', '#f0c030', '#d89a20', '#8a2418']


def planks():
    """Deck boards: 8 boards of 4 texels running along v, staggered end joints, a few leaves."""
    r = random.Random(11)
    c = Canvas(32, 32, '#a07a52')
    tones = ['#a07a52', '#8a6446', '#b08a5e', '#967050']
    for b in range(8):
        x0 = b * 4
        c.rect(x0, 0, x0 + 4, 32, tones[r.randrange(len(tones))])
        for _ in range(3):
            gx, gy = x0 + r.randrange(1, 4), r.randrange(32)
            for k in range(r.randrange(4, 9)):
                c.set(gx, gy + k, '#7a5a3e')
        c.rect(x0, 0, x0 + 1, 32, '#5a3e2c')
        end = (b * 13 + 5) % 32
        c.rect(x0, end, x0 + 4, end + 1, '#5a3e2c')
    for (x, y, k) in [(6, 4, 0), (21, 11, 2), (13, 22, 3), (27, 27, 1), (2, 17, 4)]:
        leaf(c, r, x, y, AUTUMN[k])
    c.save('forest_planks.png')


def rail():
    """A railing bay with holes: top rail, middle rail, foot rail, a post at each edge and one
    in the middle."""
    c = Canvas(32, 32, None)
    dark, mid, light = '#5a3e2c', '#8a6446', '#a07a52'

    def bar(y0, y1):
        c.rect(0, y0, 32, y1, mid)
        c.rect(0, y0, 32, y0 + 1, light)
        c.rect(0, y1 - 1, 32, y1, dark)
    for x0, x1 in [(0, 2), (30, 32), (15, 17)]:
        c.rect(x0, 4, x1, 32, mid)
    c.rect(0, 4, 1, 32, dark)
    c.rect(16, 4, 17, 32, dark)
    c.rect(31, 4, 32, 32, light)
    bar(0, 5)
    bar(14, 17)
    bar(27, 30)
    c.save('forest_rail.png')


def bark_moss():
    """A log's bark around (u: one turn) and along (v): fissured bark, moss over the top (u 0.5)."""
    r = random.Random(23)
    c = Canvas(64, 32, '#5a4232')
    for x in range(64):
        tone = ['#5a4232', '#6a4632', '#4a3a2e'][(x * 7 + r.randrange(2)) % 3]
        c.rect(x, 0, x + 1, 32, tone)
    for _ in range(26):
        x, y = r.randrange(64), r.randrange(32)
        for k in range(r.randrange(6, 16)):
            c.set(x + (k // 6), y + k, '#3a2c22')
    for x in range(64):
        d = abs(x - 32)
        for y in range(32):
            edge = 8 + 3 * ((x * 5 + y * 3) % 7) / 6 + (2 if (y // 4 + x // 6) % 3 == 0 else 0)
            if d < edge:
                t = (x * 13 + y * 7 + (x * y) % 5) % 9
                col = '#5f7a34' if t < 4 else '#6f8a3c' if t < 7 else '#4f6a3a'
                if d > edge - 2.5:
                    col = '#4f6a3a'
                c.set(x, y, col)
    for (x, y, k) in [(30, 3, 0), (34, 12, 3), (28, 19, 2), (33, 26, 5), (36, 7, 4)]:
        leaf(c, r, x, y, AUTUMN[k])
    c.save('forest_bark_moss.png')


def mossy_stone():
    """A boulder's skin, drawn once (u around, v down): moss over the top rows, grey stone,
    an earth-stained foot."""
    r = random.Random(31)
    c = Canvas(32, 32, '#8e887c')
    for y in range(32):
        for x in range(32):
            t = r.random()
            col = '#8e887c' if t < 0.55 else '#9e988a' if t < 0.8 else '#7a756a'
            if y > 25 and r.random() < (y - 25) / 8:
                col = '#6a665e'
            c.set(x, y, col)
    for _ in range(7):
        x, y = r.randrange(32), r.randrange(12, 28)
        for k in range(r.randrange(3, 7)):
            c.set(x + k, y + (k % 3 == 2), '#5e5a52', wrap=False)
    for x in range(32):
        edge = 10 + int(3 * ((x * 7) % 5) / 4) + (2 if x % 9 in (2, 3, 4) else 0)
        for y in range(edge):
            t = (x * 11 + y * 5 + (x * y) % 7) % 10
            c.set(x, y, '#5f7a34' if t < 5 else '#6f8a3c' if t < 8 else '#4f6a3a')
        c.set(x, edge, '#7a8050')
        if x % 4 == 1:
            c.set(x, edge + 1, '#7a8050')
    for (x, y, k) in [(5, 3, 0), (19, 6, 3), (26, 1, 2), (12, 8, 5)]:
        leaf(c, r, x, y, AUTUMN[k], wrap=False)
    c.save('forest_mossy_stone.png')


def stone():
    """Worked granite for the lantern, the fox statue and the fox shrine's base: lichen, moss."""
    r = random.Random(41)
    c = Canvas(32, 32, '#a49e90')
    for y in range(32):
        for x in range(32):
            t = r.random()
            c.set(x, y, '#a49e90' if t < 0.5 else '#b4ae9e' if t < 0.75 else
                  '#8e887c' if t < 0.95 else '#6a665e')
    for _ in range(9):
        x, y = r.randrange(32), r.randrange(32)
        col = '#7a8050' if r.random() < 0.6 else '#6f8a3c'
        for dx, dy in [(0, 0), (1, 0), (0, 1), (1, 1), (2, 1), (1, 2)]:
            if r.random() < 0.8:
                c.set(x + dx, y + dy, col)
    c.save('forest_stone.png')


def hall_wall():
    """One 2 m bay of the stage hall, 4.4 m tall: half a column at each edge, a white plaster
    frieze with a strut, the vermilion tie beam, lattice doors and the sill."""
    c = Canvas(32, 64, '#2c2a28')
    col, col_d, beam = '#8a6446', '#6a4a36', '#5a3e2c'
    c.rect(0, 0, 32, 4, beam)
    c.rect(0, 4, 32, 15, '#ece4d2')
    c.rect(15, 4, 17, 15, col_d)
    c.rect(0, 14, 32, 15, '#c8bca8')
    c.rect(0, 15, 32, 18, '#d8462a')
    c.rect(0, 17, 32, 18, '#a8321e')
    c.rect(0, 18, 32, 59, '#3a2c22')
    for y in range(19, 58, 3):
        c.rect(3, y, 29, y + 1, col_d)
    for x in range(5, 28, 3):
        c.rect(x, 18, x + 1, 58, col_d)
    c.rect(15, 18, 17, 59, beam)
    c.rect(3, 37, 29, 39, beam)
    c.rect(0, 59, 32, 64, beam)
    c.rect(0, 59, 32, 60, col_d)
    for x0, x1 in [(0, 3), (29, 32)]:
        c.rect(x0, 0, x1, 64, col)
    c.rect(2, 0, 3, 64, col_d)
    c.rect(29, 0, 30, 64, col_d)
    for x in (0, 1, 30, 31):
        c.set(x, 16, '#d8b048')
    c.save('forest_hall_wall.png')


def roof_bark():
    """Cypress-bark roofing seen from above: fine streaks down the slope, faint courses, a little
    moss and the maple leaves that have fallen on it."""
    r = random.Random(53)
    c = Canvas(32, 32, '#6b4a3a')
    for x in range(32):
        c.rect(x, 0, x + 1, 32, ['#6b4a3a', '#62443a', '#74523e'][(x * 5 + r.randrange(2)) % 3])
    for _ in range(30):
        x, y = r.randrange(32), r.randrange(32)
        for k in range(r.randrange(3, 8)):
            c.set(x, y + k, '#5a3e2c')
    for y in (7, 15, 23, 31):
        for x in range(32):
            if (x + y) % 5:
                c.set(x, y, '#5a3e2c')
    for _ in range(4):
        x, y = r.randrange(32), r.randrange(32)
        for dx, dy in [(0, 0), (1, 0), (0, 1)]:
            c.set(x + dx, y + dy, '#5f7a34')
    for (x, y, k) in [(3, 2, 0), (12, 9, 2), (25, 5, 3), (19, 18, 1), (7, 24, 5), (28, 27, 4),
                      (14, 29, 0)]:
        leaf(c, r, x, y, AUTUMN[k])
    c.save('forest_roof_bark.png')


def inner_wood():
    """The inside of a hollow log: pale rotten fibres along v, dark cracks, pale fungus."""
    r = random.Random(61)
    c = Canvas(32, 32, '#8a6446')
    for x in range(32):
        c.rect(x, 0, x + 1, 32, ['#8a6446', '#9a7450', '#7a5a3e'][(x * 3 + r.randrange(2)) % 3])
    for _ in range(14):
        x, y = r.randrange(32), r.randrange(32)
        for k in range(r.randrange(5, 14)):
            c.set(x, y + k, '#5a3e2c')
    for _ in range(6):
        x, y = r.randrange(32), r.randrange(32)
        c.set(x, y, '#d4ccb8')
        c.set(x + 1, y, '#c8c4b0')
    c.save('forest_inner_wood.png')


def litter():
    """Leaf litter on earth: maple and ginkgo leaves of every age."""
    r = random.Random(71)
    c = Canvas(32, 32, '#7a4a2a')
    for y in range(32):
        for x in range(32):
            c.set(x, y, '#7a4a2a' if r.random() < 0.6 else '#6a4a30')
    cols = ['#9a5a2e', '#c8301e', '#e8782a', '#f0c030', '#d89a20', '#8a2418', '#e0502a']
    for _ in range(70):
        leaf(c, r, r.randrange(32), r.randrange(32), cols[r.randrange(len(cols))])
    c.save('forest_litter.png')


def shrine_front():
    """The fox shrine's front: vermilion posts and lintel, black lacquer doors, gold fittings."""
    c = Canvas(32, 32, '#2c2a28')
    verm, verm_d = '#d8462a', '#a8321e'
    c.rect(0, 0, 32, 5, verm)
    c.rect(0, 4, 32, 5, verm_d)
    c.rect(0, 0, 4, 32, verm)
    c.rect(28, 0, 32, 32, verm)
    c.rect(3, 0, 4, 32, verm_d)
    c.rect(28, 0, 29, 32, verm_d)
    c.rect(0, 29, 32, 32, verm)
    c.rect(15, 5, 17, 29, '#3e3a36')
    for y in (9, 24):
        c.rect(5, y, 9, y + 1, '#d8b048')
        c.rect(23, y, 27, y + 1, '#d8b048')
    c.rect(13, 16, 15, 18, '#d8b048')
    c.rect(17, 16, 19, 18, '#d8b048')
    c.save('forest_shrine_front.png')


def shrine_side():
    """The fox shrine's sides and back: vermilion posts and tie beam, white plaster."""
    c = Canvas(32, 32, '#ece4d2')
    verm, verm_d = '#d8462a', '#a8321e'
    c.rect(0, 0, 32, 4, verm)
    c.rect(0, 3, 32, 4, verm_d)
    c.rect(0, 13, 32, 16, verm)
    c.rect(0, 15, 32, 16, verm_d)
    c.rect(0, 29, 32, 32, verm)
    c.rect(0, 0, 4, 32, verm)
    c.rect(28, 0, 32, 32, verm)
    c.rect(3, 0, 4, 32, verm_d)
    c.rect(28, 0, 29, 32, verm_d)
    c.rect(4, 16, 28, 17, '#d4ccb8')
    c.save('forest_shrine_side.png')


def copper():
    """The fox shrine's old copper roof: standing seams down the slope, a few fallen leaves."""
    r = random.Random(83)
    c = Canvas(32, 32, '#7a8a70')
    for x in range(32):
        tone = '#6e8066' if x % 8 == 6 else '#8a9a80' if x % 8 == 7 else '#7a8a70'
        c.rect(x, 0, x + 1, 32, tone)
    for _ in range(18):
        c.set(r.randrange(32), r.randrange(32), '#6a7a62')
    for (x, y, k) in [(4, 5, 0), (17, 20, 3), (26, 11, 2)]:
        leaf(c, r, x, y, AUTUMN[k])
    c.save('forest_copper.png')


if __name__ == '__main__':
    planks()
    rail()
    bark_moss()
    mossy_stone()
    stone()
    hall_wall()
    roof_bark()
    inner_wood()
    litter()
    shrine_front()
    shrine_side()
    copper()
