"""Draws the shrine architecture's textures (arch_*.png beside this file).

Authored art: run once with `python3 carts/garden/shrine/assets/art/draw_arch.py` and commit the
PNGs; nothing rebuilds them. Needs Pillow. Every texture is 4-bit (15 colours at most), in the
shrine palette (carts/garden/shrine/STYLE.md).
"""

from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


VERM = rgb("#d8462a")
VERM_SH = rgb("#a8321e")
PLASTER = rgb("#ece4d2")
PLASTER_SH = rgb("#d8cfbc")
BLACK = rgb("#2c2a28")
TILE_D = rgb("#3e4248")
TILE = rgb("#565c64")
TILE_L = rgb("#6a7078")
GOLD = rgb("#d8b048")
WOOD_D = rgb("#5a3e2c")
WOOD = rgb("#8a6446")
GREEN = rgb("#3c5a34")
GREEN_L = rgb("#4f6a3a")
STONE_L = rgb("#b4ae9e")
STONE_M = rgb("#8e887c")
STONE_D = rgb("#6a665e")
MOSS = rgb("#7a8050")
MOSS_D = rgb("#5f7a34")


def h(x, y, s=0):
    """A small deterministic hash in 0..255."""
    v = (x * 374761393 + y * 668265263 + s * 2246822519) & 0xFFFFFFFF
    v = ((v ^ (v >> 13)) * 1274126177) & 0xFFFFFFFF
    return (v ^ (v >> 16)) & 0xFF


def new(w, hgt, fill):
    return Image.new("RGBA", (w, hgt), fill + (255,))


def rect(im, x0, y0, x1, y1, c):
    """Fill texels x0..x1-1, y0..y1-1."""
    for y in range(max(0, y0), min(im.height, y1)):
        for x in range(max(0, x0), min(im.width, x1)):
            im.putpixel((x, y), c + (255,))


def tile():
    """Hongawara: 8 columns of round tiles (4 texels each) and 4 courses down the slope.

    One repeat is 2 m x 2 m, so a tile is 0.25 m wide and a course 0.5 m long."""
    im = new(32, 32, TILE_D)
    for y in range(32):
        for x in range(32):
            col, cx = divmod(x, 4)
            cy = y % 8
            c = [BLACK, TILE_D, TILE, TILE_D][cx]
            if cy == 0 and cx in (1, 2, 3):      # the lip of the course above
                c = TILE_L if cx == 2 else TILE
            elif cy == 7 and cx != 0:            # shadow under the next course's lip
                c = BLACK if cx == 3 else TILE_D
            elif cx == 2 and h(col, y // 8, 1) < 40:
                c = TILE_L                        # a newer, paler tile here and there
            im.putpixel((x, y), c + (255,))
    # a little lichen in the gutters between tiles
    for (x, y) in ((0, 13), (0, 14), (16, 27), (24, 5), (8, 21)):
        im.putpixel((x, y), MOSS_D + (255,))
    return im


def bay(doors=False):
    """One 4 m bay of a hall wall, 64 x 64; v covers the wall from its sill to the eave beam.

    Half a post at each side (so neighbouring bays make whole posts), a beam at the top and at
    the head of the openings, white plaster, and either a green lattice window (renji-mado) over
    a plaster dado, or (doors) a pair of lattice-panel doors with gold fittings."""
    im = new(64, 64, PLASTER)
    # posts: 3 texels each side (~0.38 m post)
    rect(im, 0, 0, 3, 64, VERM)
    rect(im, 61, 0, 64, 64, VERM)
    rect(im, 3, 0, 4, 64, VERM_SH)               # the post's shaded edge
    # eave beam and frieze of bracket blocks under it
    rect(im, 0, 0, 64, 3, VERM)
    for bx in range(6, 60, 9):
        rect(im, bx, 3, bx + 4, 7, VERM)
        rect(im, bx, 6, bx + 4, 7, VERM_SH)
    rect(im, 0, 7, 64, 9, VERM)                  # upper tie beam
    rect(im, 0, 9, 64, 10, VERM_SH)
    # head beam (nageshi) over the openings
    rect(im, 0, 18, 64, 21, VERM)
    rect(im, 0, 21, 64, 22, VERM_SH)
    if doors:
        # two doors between the posts, rows 22..58
        rect(im, 6, 23, 58, 59, VERM)
        for x0 in (8, 33):
            rect(im, x0, 25, x0 + 23, 57, WOOD_D)
            for y in range(26, 56, 3):            # lattice of the panels
                rect(im, x0 + 1, y, x0 + 22, y + 1, VERM_SH)
            for x in range(x0 + 3, x0 + 22, 4):
                rect(im, x, 26, x + 1, 56, VERM_SH)
            rect(im, x0, 39, x0 + 23, 41, VERM)  # middle rail
        for gy in (27, 39, 53):                   # gold hinge plates
            rect(im, 8, gy, 10, gy + 2, GOLD)
            rect(im, 54, gy, 56, gy + 2, GOLD)
        rect(im, 30, 38, 34, 42, GOLD)            # the pull
        rect(im, 0, 59, 64, 61, VERM)            # threshold
    else:
        # lattice window, rows 24..41
        rect(im, 12, 24, 52, 42, VERM)
        rect(im, 14, 26, 50, 40, BLACK)
        for x in range(15, 50, 3):
            rect(im, x, 26, x + 2, 40, GREEN)
            rect(im, x + 1, 26, x + 2, 40, GREEN_L)
        rect(im, 0, 44, 64, 47, VERM)            # sill rail (koshi-nuki)
        rect(im, 0, 47, 64, 48, VERM_SH)
        rect(im, 4, 48, 61, 59, PLASTER_SH)      # the dado, a shade darker
        rect(im, 0, 59, 64, 61, VERM)
    rect(im, 0, 61, 64, 64, WOOD_D)              # the sill on the base
    return im


def small_bay():
    """A pagoda storey's bay, 32 x 32: posts, a central door with gold studs, plaster sides."""
    im = new(32, 32, PLASTER)
    rect(im, 0, 0, 2, 32, VERM)
    rect(im, 30, 0, 32, 32, VERM)
    rect(im, 0, 0, 32, 3, VERM)
    rect(im, 0, 3, 32, 4, VERM_SH)
    rect(im, 0, 8, 32, 10, VERM)
    rect(im, 10, 10, 22, 30, VERM)
    rect(im, 11, 11, 21, 29, VERM_SH)
    rect(im, 15, 11, 17, 29, VERM)
    for y in (13, 17, 21, 25):
        for x in (12, 14, 18, 20):
            im.putpixel((x, y), GOLD + (255,))
    rect(im, 3, 14, 8, 22, GREEN)                # little lattice windows
    rect(im, 24, 14, 29, 22, GREEN)
    for x in (4, 6, 25, 27):
        rect(im, x, 14, x + 1, 22, BLACK)
    rect(im, 0, 30, 32, 32, WOOD_D)
    return im


def stone():
    """Cut granite blocks, 32 x 32 for 2.4 m: four courses, joints with moss in them."""
    im = new(32, 32, STONE_M)
    for y in range(32):
        course, cy = divmod(y, 8)
        shift = 8 if course % 2 else 0
        for x in range(32):
            bx, cx = divmod((x + shift) % 32, 16)
            v = h(bx, course, 3)
            base = STONE_L if v < 110 else (STONE_M if v < 220 else MOSS)
            c = base
            if cy == 7 or cx == 15:
                c = STONE_D
                if h(x, y, 5) < 50:
                    c = MOSS_D
            elif cy == 0 or cx == 0:
                c = STONE_L if base != STONE_L else PLASTER_SH
            elif h(x, y, 7) < 24:
                c = STONE_D if base == STONE_M else STONE_M
            im.putpixel((x, y), c + (255,))
    return im


def koran():
    """A balcony railing, 32 x 8 for 2 m x 0.5 m: rails, posts and balusters; the rest a hole."""
    im = Image.new("RGBA", (32, 8), (0, 0, 0, 0))
    rect(im, 0, 0, 32, 2, VERM)                  # top rail
    rect(im, 0, 1, 32, 2, VERM_SH)
    rect(im, 0, 6, 32, 8, VERM)                  # bottom rail
    rect(im, 0, 4, 32, 5, VERM)                  # middle rail
    for x in (0, 16):
        rect(im, x, 0, x + 2, 8, VERM)           # posts
        rect(im, x, 0, x + 2, 1, GOLD)           # gold caps
    for x in (6, 11, 22, 27):
        rect(im, x, 2, x + 1, 6, VERM_SH)        # balusters
    return im


def gaku():
    """The torii's name plaque, 8 x 16: gold frame on black lacquer, two gold characters."""
    im = new(8, 16, BLACK)
    rect(im, 0, 0, 8, 1, GOLD)
    rect(im, 0, 15, 8, 16, GOLD)
    rect(im, 0, 0, 1, 16, GOLD)
    rect(im, 7, 0, 8, 16, GOLD)
    for (x, y) in ((3, 3), (4, 3), (2, 4), (5, 4), (3, 5), (4, 5), (3, 6), (4, 6),
                   (3, 9), (4, 9), (2, 10), (3, 10), (4, 10), (5, 10), (3, 11), (2, 12),
                   (4, 12), (5, 12)):
        im.putpixel((x, y), GOLD + (255,))
    return im


def rafters():
    """Eave undersides, 16 x 16 for 1 m: four rafters running out to the eave, white ends."""
    im = new(16, 16, VERM_SH)
    for x in range(16):
        c = [VERM, VERM, VERM_SH, BLACK][x % 4]
        for y in range(16):
            im.putpixel((x, y), (c if c != BLACK else WOOD_D) + (255,))
    return im


def wall_cap():
    """The precinct wall's tiled cap, drawn once along a whole 8 m run: 128 x 8 texels, u along
    the wall (32 round-tile columns of 0.25 m), v down the slope from the ridge to the eave."""
    im = new(128, 8, TILE_D)
    for y in range(8):
        for x in range(128):
            col, cx = divmod(x, 4)
            c = [BLACK, TILE_D, TILE, TILE_D][cx]
            if y == 0 and cx != 0:
                c = TILE_L if cx == 2 else TILE
            elif y == 7 and cx != 0:
                c = TILE_L if cx == 2 else TILE          # the round tile ends at the eave
            elif cx == 2 and h(col, 0, 9) < 50:
                c = TILE_L
            im.putpixel((x, y), c + (255,))
    for (x, y) in ((8, 3), (41, 5), (88, 2), (116, 4)):
        im.putpixel((x, y), MOSS_D + (255,))
    return im


def wall_footing():
    """The wall's stone footing along a whole 8 m run: 128 x 8 texels for 8 m x 0.5 m; blocks of
    0.75 to 1.1 m with mossy joints."""
    im = new(128, 8, STONE_M)
    x, k = 0, 0
    joints = []
    while x < 128:
        w = 12 + h(k, 1, 11) % 6
        joints.append((x, min(128, x + w), k))
        x += w
        k += 1
    for x0, x1, k in joints:
        v = h(k, 2, 13)
        base = STONE_L if v < 110 else (STONE_M if v < 220 else MOSS)
        for y in range(8):
            for x in range(x0, x1):
                c = base
                if x == x1 - 1 or y == 7:
                    c = MOSS_D if h(x, y, 5) < 60 else STONE_D
                elif y == 0 or x == x0:
                    c = STONE_L if base != STONE_L else PLASTER_SH
                elif h(x, y, 7) < 24:
                    c = STONE_D if base == STONE_M else STONE_M
                im.putpixel((x, y), c + (255,))
    return im


def main():
    for name, im in (("arch_tile", tile()), ("arch_bay", bay()), ("arch_bay_doors", bay(True)),
                     ("arch_small_bay", small_bay()), ("arch_stone", stone()),
                     ("arch_koran", koran()), ("arch_gaku", gaku()), ("arch_rafters", rafters()),
                     ("arch_wall_cap", wall_cap()), ("arch_wall_footing", wall_footing())):
        im.save(HERE / f"{name}.png")


if __name__ == "__main__":
    main()
