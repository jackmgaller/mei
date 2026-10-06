"""Packing textures into Mei's texture slots and palettes (docs/ASSETKIT.md, "Textures").

A **tile** is one texture as the GPU will read it: a width and height in texels, a depth (4 or
8 bits), one or more frames of 15-bit colours (None for a hole: texel 0), and how faces sample
it: through a texture window (a repeating tile; power-of-two sizes 8-128) or plainly, with a
one-texel **gutter** that repeats its last column and row (a tile drawn once: a face's
coordinate may reach its width exactly at a corner). Nothing here knows what an asset or a
world is: the Asset Kit packs one asset or a set (`mei_assets.py pack`), and the World Kit can
pack a region's tiles the same way.

`pack(tiles, ...)` removes duplicates (equal keys), gives every tile a palette (4-bit tiles
share 16-colour palettes while their colours fit, 15 to a palette; 8-bit tiles share 256-colour
palettes, 255 to a palette; index 0 is never a colour), places each tile in a slot at an origin
that is a multiple of 8 (window-aligned), and returns a `Packing`, or raises KitError when the
tiles do not fit. A slot holds tiles of one depth: 256 x 256 4-bit texels, or 256 x 128 8-bit
texels (an 8-bit texture's rows 128 and on would be in the next slot). Slot 15 holds the fonts
and 4-bit palette 255 their colours: neither is ever used.
"""
from dataclasses import dataclass, field
import hashlib
import struct

from .errors import KitError

SLOT_BYTES = 32768
FONT_SLOT = 15
FONT_PALETTE = 255          # 4-bit palette 255 (colours 4080-4095) holds the fonts' colours
CELL = 8                    # placement grid: window origins are multiples of 8
WINDOW_SIZES = (8, 16, 32, 64, 128)


@dataclass
class Tile:
    """frames: a list of frames, each a list of rows of 15-bit colours or None (a hole)."""
    width: int
    height: int
    bits: int
    frames: list
    window: bool = False
    name: str = ''
    key: str = field(default=None)

    def __post_init__(self):
        if self.bits not in (4, 8):
            raise KitError('/textures', f'{self.name}: a texture is 4-bit or 8-bit.')
        limit = 128 if self.window else 255
        if self.window and (self.width not in WINDOW_SIZES or self.height not in WINDOW_SIZES):
            raise KitError('/textures', f'{self.name}: a repeating texture is 8, 16, 32, 64 or 128 texels '
                                        f'on each side (texture windows are powers of two); it is {self.width} x {self.height}.')
        if not (1 <= self.width <= limit and 1 <= self.height <= limit):
            raise KitError('/textures', f'{self.name}: a texture drawn once is at most 255 x 255 texels (one more '
                                        f'for its gutter); it is {self.width} x {self.height}.')
        if self.bits == 8 and self.alloc_height > 128:
            raise KitError('/textures', f'{self.name}: an 8-bit texture is at most 128 texels tall in a slot.')
        if self.key is None:
            digest = hashlib.sha256(repr((self.width, self.height, self.bits, self.window, self.frames)).encode())
            self.key = digest.hexdigest()[:16]

    @property
    def gutter(self):
        return 0 if self.window else 1

    @property
    def alloc_width(self):
        return self.width + self.gutter

    @property
    def alloc_height(self):
        return self.height + self.gutter

    def colours(self):
        """The tile's colours in the order they first appear (frames, rows, texels)."""
        seen = {}
        for frame in self.frames:
            for row in frame:
                for c in row:
                    if c is not None and c not in seen:
                        seen[c] = len(seen)
        return list(seen)

    @property
    def holes(self):
        return any(c is None for frame in self.frames for row in frame for c in row)

    def cells(self):
        return -(-self.alloc_width // CELL), -(-self.alloc_height // CELL)

    def vram_bytes(self):
        """The bytes of VRAM the tile occupies (its gutter included, not the grid's rounding)."""
        return self.row_bytes()*self.alloc_height

    def allocated_bytes(self):
        """The bytes of VRAM the tile takes on the packer's 8-texel grid (as a region's texture
        budget counts them)."""
        cw, ch = self.cells()
        return cw*ch*CELL*CELL*self.bits//8

    def row_bytes(self):
        """Bytes per row of one frame in the tile's own layout (a frame file; 4-bit rows even)."""
        return -(-self.alloc_width // 2) if self.bits == 4 else self.alloc_width


@dataclass
class Placement:
    slot: int
    x: int
    y: int
    bits: int
    palette: int                # 4-bit palette 0-254, or 8-bit palette 0-14
    index: dict                 # 15-bit colour -> palette index 1-15 or 1-255
    window: bool
    width: int
    height: int

    def halfword(self):
        """The texture window halfword (DECISIONS.md, "Texture windows"), 0 for none."""
        if not self.window:
            return 0
        def axis(size, origin):
            return (size.bit_length()-3) | (origin//8) << 3
        return axis(self.width, self.x) | axis(self.height, self.y) << 8

    def first_colour(self):
        return self.palette*(16 if self.bits == 4 else 256)


class Packing:
    """Where every tile went: placements by key, the palettes, and the slots' contents."""

    def __init__(self, tiles, placements, palettes, slot_bits):
        self.tiles = tiles                  # key -> Tile
        self.placements = placements        # key -> Placement
        self.palettes = palettes            # (bits, palette) -> [15-bit colours], index 1 first
        self.slot_bits = slot_bits          # slot -> 4 or 8

    def encode(self, key, frame=0):
        """One frame of a tile in its own layout: alloc_height rows of row_bytes() bytes."""
        tile, place = self.tiles[key], self.placements[key]
        out = bytearray()
        rows = tile.frames[frame]
        for y in range(tile.alloc_height):
            row = rows[min(y, tile.height-1)]
            indices = [0 if c is None else place.index[c] for c in
                       (row[min(x, tile.width-1)] for x in range(tile.alloc_width))]
            if tile.bits == 4:
                indices += [0]*(len(indices) % 2)
                out += bytes(indices[k] | indices[k+1] << 4 for k in range(0, len(indices), 2))
            else:
                out += bytes(indices)
        return bytes(out)

    def slot_image(self, slot):
        """(first row, bytes) of the rows of the slot that tiles use, with frame 0 of each; the
        rows between tiles are zero. None for an unused slot."""
        stride = 128 if self.slot_bits[slot] == 4 else 256
        image, used = bytearray(SLOT_BYTES), []
        for key, place in self.placements.items():
            if place.slot != slot:
                continue
            tile, data = self.tiles[key], self.encode(key)
            n, at = tile.row_bytes(), place.x//2 if tile.bits == 4 else place.x
            for y in range(tile.alloc_height):
                image[(place.y+y)*stride+at:(place.y+y)*stride+at+n] = data[y*n:(y+1)*n]
            used += [place.y, place.y+tile.alloc_height]
        if not used:
            return None
        first, last = min(used), max(used)
        return first, bytes(image[first*stride:last*stride])

    def slots(self):
        return sorted(self.slot_bits)

    def palette_bytes(self, bits, palette):
        """A palette's 15-bit colours: 16 (4-bit) or 1 + its colours (8-bit), index 0 zero."""
        colours = self.palettes[bits, palette]
        size = 16 if bits == 4 else 1+len(colours)
        return struct.pack(f'<{size}H', 0, *colours, *[0]*(size-1-len(colours)))

    def summary(self):
        cells = sum(t.cells()[0]*t.cells()[1]*(CELL*CELL*t.bits//8) for t in self.tiles.values())
        return {'tiles': len(self.tiles), 'slots': self.slots(),
                'vram_bytes': sum(t.vram_bytes() for t in self.tiles.values()),
                'vram_bytes_allocated': cells,
                'palettes_4bit': sorted(p for b, p in self.palettes if b == 4),
                'palettes_8bit': sorted(p for b, p in self.palettes if b == 8)}


def assign_palettes(tiles, bits, first, last, path, group=None):
    """First fit: each tile's colours join the first palette that can hold them all (and, with
    group, whose tiles are in the tile's group: group(key) -> any hashable)."""
    cap = 15 if bits == 4 else 255
    palettes, of, groups = [], {}, []
    for key, tile in tiles.items():
        colours = tile.colours()
        mine = group(key) if group else None
        if len(colours) > cap:
            raise KitError(path, f'{tile.name}: {len(colours)} colours; a {bits}-bit texture has at most {cap}.')
        for k, pal in enumerate(palettes):
            if groups[k] != mine:
                continue
            new = [c for c in colours if c not in pal]
            if len(pal)+len(new) <= cap:
                pal += new
                of[key] = k
                break
        else:
            palettes.append(list(colours))
            groups.append(mine)
            of[key] = len(palettes)-1
    numbers = [first+k if bits == 4 else first-k for k in range(len(palettes))]
    if numbers and (numbers[-1] > last if bits == 4 else numbers[-1] < last):
        raise KitError(path, f'The {bits}-bit textures need {len(palettes)} palettes from {first}; only '
                             f'{abs(last-first)+1} are free there. Use fewer colours, or merge textures.')
    return {key: numbers[k] for key, k in of.items()}, {numbers[k]: pal for k, pal in enumerate(palettes)}


def pack(tiles, slots=tuple(range(14, -1, -1)), first_palette=0, palette8=14, reserved=(), path='/textures',
         group=None):
    """tiles: an iterable of Tile (equal keys are one tile). slots: the slots to use, in order of
    preference (never 15). first_palette: the first 4-bit palette for 4-bit tiles (they take
    consecutive ones). palette8: the first 8-bit palette (8-bit tiles take it and those below);
    8-bit palette p covers 4-bit palettes 16p-16p+15, which no 4-bit tile may use. reserved:
    (slot, x, y, width, height) rectangles in 4-bit texels that no tile may use (a swatch); a
    slot with one holds 4-bit tiles only. group: tile key -> a group; tiles share palettes only
    within their group (the World Kit keeps surface and emissive textures apart, so a palette
    variant can tint them differently)."""
    unique = {}
    for tile in tiles:
        unique.setdefault(tile.key, tile)
    if FONT_SLOT in slots:
        raise KitError(path, 'Texture slot 15 holds the fonts.')
    four = {k: t for k, t in unique.items() if t.bits == 4}
    eight = {k: t for k, t in unique.items() if t.bits == 8}
    pal8, palettes8 = assign_palettes(eight, 8, palette8, 0, path, group)
    lowest8 = min(palettes8) if palettes8 else 16
    limit4 = min(FONT_PALETTE, 16*lowest8)-1
    pal4, palettes4 = assign_palettes(four, 4, first_palette, limit4, path, group)
    if four and first_palette > limit4:
        raise KitError(path, f'4-bit palette {first_palette} lies in 8-bit palette {first_palette//16}, used by an 8-bit texture.')
    palettes = {**{(4, p): c for p, c in palettes4.items()}, **{(8, p): c for p, c in palettes8.items()}}

    # Occupancy grids of 8 x 8 cells: 32 x 32 for a 4-bit slot, 32 x 16 for an 8-bit one.
    grids, slot_bits = {}, {}
    for slot, x, y, w, h in reserved:
        grid = grids.setdefault(slot, [[False]*32 for _ in range(32)])
        slot_bits[slot] = 4
        for cy in range(y//CELL, -(-(y+h)//CELL)):
            for cx in range(x//CELL, -(-(x+w)//CELL)):
                grid[cy][cx] = True
    order = sorted(unique, key=lambda k: (-unique[k].cells()[1], -unique[k].cells()[0], list(unique).index(k)))
    placements = {}
    for key in order:
        tile = unique[key]
        cw, ch = tile.cells()
        spot = None
        for slot in slots:
            if slot_bits.get(slot, tile.bits) != tile.bits:
                continue
            grid = grids.get(slot) or [[False]*32 for _ in range(32 if tile.bits == 4 else 16)]
            spot = first_fit(grid, cw, ch)
            if spot:
                grids[slot], slot_bits[slot] = grid, tile.bits
                for cy in range(spot[1], spot[1]+ch):
                    for cx in range(spot[0], spot[0]+cw):
                        grid[cy][cx] = True
                spot = (slot, spot[0]*CELL, spot[1]*CELL)
                break
        if not spot:
            need = sum(t.vram_bytes() for t in unique.values())
            raise KitError(path, f'The textures do not fit in slots {list(slots)}: no room for {tile.name} '
                                 f'({tile.alloc_width} x {tile.alloc_height}, {tile.bits}-bit) after '
                                 f'{len(placements)} of {len(unique)} tiles ({need:,} bytes of texels in all, '
                                 f'{SLOT_BYTES:,} a slot). Use smaller or fewer textures, 4-bit rather '
                                 f'than 8-bit, or more slots.')
        palette = pal4[key] if tile.bits == 4 else pal8[key]
        colours = palettes[tile.bits, palette]
        placements[key] = Placement(spot[0], spot[1], spot[2], tile.bits, palette,
                                    {c: i+1 for i, c in enumerate(colours)}, tile.window, tile.width, tile.height)
    placements = {k: placements[k] for k in unique}      # in the tiles' own order
    return Packing(unique, placements, palettes, {s: b for s, b in slot_bits.items() if
                                                  any(p.slot == s for p in placements.values())})


def first_fit(grid, cw, ch):
    rows, cols = len(grid), len(grid[0])
    for y in range(rows-ch+1):
        for x in range(cols-cw+1):
            if all(not grid[y+j][x+i] for j in range(ch) for i in range(cw)):
                return x, y
    return None
