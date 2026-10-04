"""Region backdrops (docs/WORLDKIT.md, "Backdrops"): a sky and a horizon silhouette drawn by the
Horizon Engine (docs/PLANES.md) behind the 3D world, at no GPU cost.

The sky is a gradient on the plane chip's backdrop colour, by elevation above the horizon: the
reader works out each stop's screen line from the camera's pitch every frame and fills the
backdrop line table (sky_gradient()). The silhouette is a 4-bit panorama of 256, 512 or 1024
pixels (a distant skyline, mountains) on tile plane BG1: its 8 x 8 tiles go into an atlas
page, deduplicated, its map into a 128 x 32 map at most, and the reader scrolls it by the
camera's yaw (horizontally) and pitch (so its horizon row stays on the horizon). Its colours
are a 4-bit palette in the region's main run, so palette variants recolour it like everything
else (the surface tint, and exact colours per variant).

Nothing here knows about packs or regions beyond names: it returns the art, the plane set-up
and the colours, and world.py puts them in the region.
"""
from dataclasses import dataclass, field
import math
from pathlib import Path

from assetkit.textures import read_png, quantise, rgb_of, mix
from assetkit.geometry import AssetError
from kitcore.errors import pointer
from .schema import WorldError

ATLAS = 0x460000            # plane page 12 (planes.akr's ATLAS_0): the silhouette's tiles
MAP = 0x452000              # planes.akr's MAP_BG1: the silhouette's map (up to 128 x 32 entries, 8 KB)
MAP_ROWS = 32               # the map is 32 tiles (256 pixels) tall; the reader's window shows one copy
FOCAL = 207.8               # pixels a radian at the screen's centre (the default 60-degree camera)
MAX_TILES = 1024            # 8 x 8 tiles in a 4-bit atlas page


def rgb_hex15(c15):
    r, g, b = rgb_of(c15)
    return f'#{r:02x}{g:02x}{b:02x}'


def word(color):
    """'#rrggbb' -> the plane chip's 0xBBGGRR."""
    r, g, b = (int(color[k:k + 2], 16) for k in (1, 3, 5))
    return r | g << 8 | b << 16


@dataclass
class Backdrop:
    elevations: list            # radians, increasing
    sky: dict                   # variant name -> [colour hex] (given ones only)
    colours: list = field(default_factory=list)     # the silhouette's 15-bit colours (index 1..)
    width: int = 0
    height: int = 0             # 0: no silhouette
    horizon: int = 0            # plane row on the horizon
    top: int = 0                # plane row of the silhouette's first row
    repeat: int = 1
    atlas: bytes = b''
    map: bytes = b''
    tiles: int = 0

    @property
    def rate(self):
        """Plane pixels a radian of yaw: the panorama goes `repeat` times around the circle."""
        return self.width * self.repeat / (2 * math.pi)

    def mode(self, palette):
        """The BG1_MODE register: map width, 32 rows, 8 x 8 4-bit tiles, the palette base."""
        return {32: 0, 64: 1, 128: 2}[self.width // 8] | (palette & 255) << 8

    def report(self):
        out = {'stops': len(self.elevations), 'variants_given': sorted(self.sky)}
        if self.height:
            out['silhouette'] = {'width': self.width, 'height': self.height, 'colours': len(self.colours),
                                 'tiles': self.tiles, 'repeat': self.repeat,
                                 'pixels_per_radian': round(self.rate, 2),
                                 'against_the_camera': round(self.rate / FOCAL, 3),
                                 'vram_bytes': {'atlas': len(self.atlas), 'map': len(self.map)}}
        return out


def build(spec, path, base):
    """A region's backdrop recipe -> Backdrop (the palette and the variants' colours come later)."""
    elev = spec['elevations']
    if any(b <= a for a, b in zip(elev, elev[1:])):
        raise WorldError(pointer(path, 'elevations'), 'Elevations increase from the first stop to the last.')
    for vname, cols in spec['sky'].items():
        if len(cols) != len(elev):
            raise WorldError(pointer(pointer(path, 'sky'), vname), f'Give one colour for each of the {len(elev)} elevations.')
    out = Backdrop([math.radians(e) for e in elev], dict(spec['sky']))
    if 'silhouette' in spec:
        silhouette(out, spec['silhouette'], pointer(path, 'silhouette'), base)
    return out


def silhouette(out, spec, path, base):
    has = [k for k in ('image', 'pattern') if k in spec]
    if len(has) != 1:
        raise WorldError(path, 'A silhouette is an image or a pattern (exactly one).')
    if 'image' in spec:
        for k in ('width', 'height', 'colors', 'seed'):
            if k in spec:
                raise WorldError(pointer(path, k), f'{k} is for patterns; an image has its own size and colours.')
        file = (Path(base) / spec['image']).resolve()
        if not file.is_file():
            raise WorldError(pointer(path, 'image'), f'No image {file} (paths are relative to the world recipe).')
        try:
            w, h, rows = read_png(file, pointer(path, 'image'))
            frames, _, _ = quantise([[[None if p[3] < 128 else p[:3] for p in r] for r in rows]], 15)
        except AssetError as error:
            raise WorldError(pointer(path, 'image'), str(error)) from error
        pixels = frames[0]
        colours = sorted({c for r in pixels for c in r if c is not None})
        index = {c: k + 1 for k, c in enumerate(colours)}
        grid = [[0 if c is None else index[c] for c in r] for r in pixels]
    else:
        for k in ('width', 'height', 'colors'):
            if k not in spec:
                raise WorldError(pointer(path, k), f'A {spec["pattern"]} pattern needs {k}.')
        w, h = spec['width'], spec['height']
        cols = [c.lower() for c in spec['colors']]
        need = {'skyline': 2, 'mountains': 2}[spec['pattern']]
        if len(cols) < need:
            raise WorldError(pointer(path, 'colors'), f'A {spec["pattern"]} takes {need} or more colours (see the schema).')
        grid = (skyline if spec['pattern'] == 'skyline' else mountains)(w, h, len(cols), spec.get('seed', 0))
        colours = [(int(c[1:3], 16) >> 3) | (int(c[3:5], 16) >> 3) << 5 | (int(c[5:7], 16) >> 3) << 10 for c in cols]
    if w not in (256, 512, 1024):
        raise WorldError(path, f'A silhouette is 256, 512 or 1024 pixels wide (a tile plane wraps at its map\'s '
                               f'width); this one is {w}.')
    if not 1 <= h <= 128:
        raise WorldError(path, f'A silhouette is 1-128 pixels tall; this one is {h}.')
    below = spec.get('horizon', 0)
    if below >= h:
        raise WorldError(pointer(path, 'horizon'), 'The horizon lies inside the silhouette: fewer rows below it than its height.')
    pad = (8 - h % 8) % 8
    rows = [[0] * w for _ in range(pad)] + grid
    out.colours, out.width, out.height, out.top = colours, w, h, pad
    out.horizon = pad + h - below
    default = max(1, round(2 * math.pi * FOCAL / w))
    out.repeat = spec.get('repeat', default)
    # 8 x 8 tiles, tile 0 empty, each distinct tile stored once
    tiles, entries = {bytes(32): 0}, []
    for ty in range(MAP_ROWS):
        for tx in range(w // 8):
            if ty * 8 >= len(rows):
                entries.append(0)
                continue
            data = bytearray()
            for y in range(8):
                r = rows[ty * 8 + y][tx * 8:tx * 8 + 8]
                data += bytes(r[k] | r[k + 1] << 4 for k in range(0, 8, 2))
            entries.append(tiles.setdefault(bytes(data), len(tiles)))
    if len(tiles) > MAX_TILES:
        raise WorldError(path, f'The silhouette has {len(tiles)} distinct 8 x 8 tiles; an atlas page holds {MAX_TILES}. '
                               'Use fewer details, or a narrower silhouette.')
    atlas = bytearray(((len(tiles) + 31) // 32) * 8 * 128)
    for data, t in tiles.items():
        x, y = (t % 32) * 8, (t // 32) * 8
        for r in range(8):
            atlas[(y + r) * 128 + x // 2:(y + r) * 128 + x // 2 + 4] = data[r * 4:r * 4 + 4]
    out.atlas, out.tiles = bytes(atlas), len(tiles)
    out.map = b''.join(e.to_bytes(2, 'little') for e in entries)


def skyline(w, h, n, seed):
    """A distant city: blocks of varied width and height in colour 1 (and 3, 4.. for nearer
    rows of blocks when given), lit windows in colour 2, the odd mast. Deterministic."""
    grid = [[0] * w for _ in range(h)]
    layers = max(1, n - 1)          # colour 1, then 3, 4, ... : farther to nearer
    for layer in range(layers):
        colour = 1 if layer == 0 else layer + 2
        x = -(mix(seed, layer, 7) % 24)
        while x < w:
            bw = 10 + mix(seed, layer, x, 1) % 26
            top = h - 1 - (h * (25 + mix(seed, layer, x, 2) % 70) // 100) * (layers - layer) // layers
            top = max(2, min(h - 3, top))
            for xx in range(max(0, x), min(w, x + bw - 1)):
                for y in range(top, h):
                    grid[y][xx] = colour
            if mix(seed, layer, x, 3) % 5 == 0:          # a mast
                mx = x + bw // 2
                for y in range(max(0, top - 4 - mix(seed, x, 4) % 6), top):
                    if 0 <= mx < w: grid[y][mx] = colour
            for y in range(top + 2, h - 1, 3):             # windows, every third row and second column
                for xx in range(x + 2, x + bw - 3, 2):
                    if 0 <= xx < w and mix(seed, layer, xx, y) % 100 < 38:
                        grid[y][xx] = 2
            x += bw
    # seamless: the pattern is drawn on the circle (blocks wrap from the right edge to the left)
    return grid


def mountains(w, h, n, seed):
    """Ridges: a far range in colour 1 and a nearer one in colour 2 (3.. more ranges), each a sum
    of whole-period waves around the circle, so the panorama joins seamlessly."""
    grid = [[0] * w for _ in range(h)]
    ranges = n
    for r in range(ranges):
        waves = [(1 + mix(seed, r, k) % (3 + 2 * k), (mix(seed, r, k, 9) % 1000) / 1000 * 2 * math.pi,
                  1 / (1 + k)) for k in range(5)]
        total = sum(a for _, _, a in waves)
        top_frac = 0.95 - 0.55 * (ranges - r) / ranges
        for x in range(w):
            s = sum(a * math.sin(2 * math.pi * f * x / w + p) for f, p, a in waves) / total
            ridge = h - 1 - int(h * top_frac * (0.6 + 0.4 * s))
            for y in range(max(0, ridge), h):
                grid[y][x] = r + 1
    return grid
