"""Textured materials: sources (patterns, texel grids, PNG images, sheets), quantisation,
projections (UVs), splitting faces that span too many texels of a repeating texture, and the
default placement of a single asset's textures (docs/ASSETKIT.md, "Textures").

The order of work in compile_recipe():

1. `load(recipe, materials, base)`: each textured material's texture, as 15-bit colours (None
   for a hole), quantised to 15 or 255 colours.
2. `project(mesh, ...)`: texel coordinates (floats) for each corner of each textured face, from
   the corners' positions in their primitive's own coordinates (`Face.local`).
3. `split(mesh, ...)`: faces of a repeating texture that span more than 255 texels are cut
   along the lines u = kL and v = kL (L the largest multiple of the tile size not above 255), so
   every piece fits the GPU's 8-bit texture coordinates; the lines are the same for every face,
   and uncut neighbours get the cut points on their shared edges.
4. (the vertices are quantised to 16.16)
5. `finish(mesh, ...)`: integer texel coordinates per face, the tiles, and the default
   placement (kitcore/texpack.py) that `build` writes.
"""
import hashlib
import json
import math
from pathlib import Path

from kitcore.texpack import Tile, pack as pack_tiles
from .geometry import AssetError, add, sub, mul, cross, dot, norm

REPEATING = ('planar', 'box', 'cylindrical')    # the others (disc, fit) draw a texture once
MAX_WINDOWS = 7


def rgb15_of(r, g, b):
    return (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10


def rgb_of(c15):
    """A 15-bit colour as 8-bit channels, expanded as the GPU does (c << 3 | c >> 2)."""
    return tuple((v << 3) | (v >> 2) for v in ((c15 & 31), (c15 >> 5) & 31, (c15 >> 10) & 31))


def hex_rgb(color):
    return tuple(int(color[k:k+2], 16) for k in (1, 3, 5))


def mix(*values):
    """A deterministic 32-bit hash of small integers (no random numbers in recipes)."""
    h = 0x9E3779B9
    for v in values:
        h = (h ^ (v & 0xFFFFFFFF)) * 0x85EBCA6B & 0xFFFFFFFF
        h ^= h >> 13
        h = h * 0xC2B2AE35 & 0xFFFFFFFF
        h ^= h >> 16
    return h


# ---------------------------------------------------------------------------------------------
# Patterns: name -> (parameters with defaults and ranges, minimum colours, function). A function
# returns rows of indices into the texture's `colors`. Every pattern tiles seamlessly when its
# divisions divide the size (checked).

def _divides(n, parts, what, path):
    if n % parts:
        raise AssetError(path, f'{what} ({parts}) must divide the texture size ({n}) so the pattern repeats seamlessly.')
    return n // parts


def brick(w, h, p, n, path):
    """Courses of bricks with mortar joints; each course shifted by `bond` of a brick. A third
    colour varies the bricks."""
    ch = _divides(h, p['courses'], 'courses', path+'/courses')
    bw = _divides(w, p['bricks'], 'bricks', path+'/bricks')
    rows = []
    for y in range(h):
        c, yy = divmod(y, ch)
        shift = round(c*p['bond']*bw) % w
        row = []
        for x in range(w):
            xx = (x+shift) % w
            if yy < p['mortar'] or xx % bw < p['mortar']:
                row.append(1)
            else:
                row.append(2 if n > 2 and mix(c, xx//bw, p['seed']) % 3 == 0 else 0)
        rows.append(row)
    return rows


def tile(w, h, p, n, path):
    """Square tiles with grout lines; a third colour alternates them as a checkerboard."""
    tw = _divides(w, p['count'], 'count', path+'/count')
    th = _divides(h, p['count'], 'count', path+'/count')
    return [[1 if x % tw < p['grout'] or y % th < p['grout'] else
             (2 if n > 2 and (x//tw+y//th) % 2 else 0) for x in range(w)] for y in range(h)]


def planks(w, h, p, n, path):
    """Boards along u, a joint line above each and one staggered end joint per board; a third
    colour alternates boards, a fourth draws grain streaks."""
    bh = _divides(h, p['boards'], 'boards', path+'/boards')
    rows = []
    for y in range(h):
        b, yy = divmod(y, bh)
        end = mix(b, p['seed']) % w
        row = []
        for x in range(w):
            if yy < p['joint'] or (x-end) % w < p['joint']:
                row.append(1)
            elif n > 3 and yy == bh//2 and mix(b, x//4, p['seed']+1) % 3 == 0:
                row.append(3)
            else:
                row.append(2 if n > 2 and b % 2 else 0)
        rows.append(row)
    return rows


def grain(w, h, p, n, path):
    """Wood grain: `rings` bands across u, wavering `waves` times along v (a triangle wave, in
    integers). Colours light, dark and (optionally) a middle tone between them."""
    rows = []
    for y in range(h):
        # triangle wave of y, in 1/1024ths of a band
        t = (y*p['waves']*4096//h) % 4096
        wobble = (t if t < 2048 else 4096-t)-1024           # -1024..1024
        shift = wobble*p['amplitude']//1024 + mix(y//2, p['seed']) % 3 - 1
        row = []
        for x in range(w):
            band = ((x*p['rings']*1024//w)+shift*p['rings']*1024//w) % 1024
            row.append(1 if band < 256 else (2 if n > 2 and band < 384 else 0))
        rows.append(row)
    return rows


def checker(w, h, p, n, path):
    cw = _divides(w, p['count'], 'count', path+'/count')
    chh = _divides(h, p['count'], 'count', path+'/count')
    return [[(x//cw+y//chh) % 2 for x in range(w)] for y in range(h)]


def stripes(w, h, p, n, path):
    """`count` stripes across u (or v), cycling through the colours."""
    size = w if p['axis'] == 'u' else h
    sw = _divides(size, p['count'], 'count', path+'/count')
    return [[((x if p['axis'] == 'u' else y)//sw) % n for x in range(w)] for y in range(h)]


def lattice(w, h, p, n, path):
    """Bars (colour 0) on a background (colour 1): `count` bars each way, `bar` texels wide, or
    diagonal ones. With `clear` naming colour 1 it is a grille or a fence."""
    sw = _divides(w, p['count'], 'count', path+'/count')
    sh = _divides(h, p['count'], 'count', path+'/count')
    if p['diagonal']:
        if h % sw:
            raise AssetError(path+'/count', f'A diagonal lattice repeats every {sw} texels both ways: the height ({h}) must be a multiple.')
        return [[0 if (x+y) % sw < p['bar'] or (x-y) % sw < p['bar'] else 1 for x in range(w)] for y in range(h)]
    return [[0 if x % sw < p['bar'] or y % sh < p['bar'] else 1 for x in range(w)] for y in range(h)]


def speckle(w, h, p, n, path):
    """The first colour flecked with the others at `density` (0-1) of the texels."""
    limit = int(p['density']*65536)
    return [[0 if n < 2 or mix(x, y, p['seed']) % 65536 >= limit else 1+mix(y, x, p['seed']+7) % (n-1)
             for x in range(w)] for y in range(h)]


SEED = ('integer', 0, 65535, 0)
PATTERNS = {
    'brick':   (dict(courses=('integer', 1, 64, 4), bricks=('integer', 1, 16, 2), bond=('number', 0, 1, 0.5),
                     mortar=('integer', 0, 8, 1), seed=SEED), 2, brick),
    'tile':    (dict(count=('integer', 1, 32, 2), grout=('integer', 0, 8, 1)), 2, tile),
    'planks':  (dict(boards=('integer', 1, 32, 4), joint=('integer', 0, 4, 1), seed=SEED), 2, planks),
    'grain':   (dict(rings=('integer', 1, 16, 3), waves=('integer', 0, 8, 1), amplitude=('integer', 0, 64, 3),
                     seed=SEED), 2, grain),
    'checker': (dict(count=('integer', 1, 64, 2)), 2, checker),
    'stripes': (dict(count=('integer', 1, 64, 4), axis=('choice', ('u', 'v'), None, 'u')), 2, stripes),
    'lattice': (dict(count=('integer', 1, 32, 2), bar=('integer', 1, 32, 2), diagonal=('boolean', None, None, False)), 2, lattice),
    'speckle': (dict(density=('number', 0, 1, 0.25), seed=SEED), 1, speckle),
}


def pattern_params(name, given, path):
    spec = PATTERNS[name][0]
    out = {}
    for key, value in given.items():
        if key not in spec:
            raise AssetError(f'{path}/{key}', f'Pattern {name!r} has no parameter {key!r}; it takes {", ".join(spec)}.')
    for key, (kind, lo, hi, default) in spec.items():
        value = given.get(key, default)
        where = f'{path}/{key}'
        if kind == 'integer' and (type(value) is not int or not lo <= value <= hi):
            raise AssetError(where, f'Expected an integer {lo}-{hi}.')
        if kind == 'number' and (type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi):
            raise AssetError(where, f'Expected a number {lo}-{hi}.')
        if kind == 'boolean' and type(value) is not bool:
            raise AssetError(where, 'Expected true or false.')
        if kind == 'choice' and value not in lo:
            raise AssetError(where, f'Expected one of {list(lo)}.')
        out[key] = value
    return out


# ---------------------------------------------------------------------------------------------
# Sources

def read_png(path, where):
    """RGBA rows of a PNG (Pillow)."""
    try:
        from PIL import Image
    except ImportError as error:
        raise AssetError(where, 'Reading PNG images needs Pillow (python3 -m pip install Pillow). Patterns and '
                                'texel grids need nothing.') from error
    try:
        with Image.open(path) as image:
            if image.format != 'PNG':
                raise AssetError(where, f'{path} is not a PNG image.')
            image = image.convert('RGBA')
            w, h = image.size
            data = image.tobytes()
    except OSError as error:
        raise AssetError(where, f'Cannot read {path}: {error}') from error
    return w, h, [[tuple(data[(y*w+x)*4:(y*w+x)*4+4]) for x in range(w)] for y in range(h)]


class Sources:
    """Images and sheets of one recipe, read once each, relative to the recipe's folder."""

    def __init__(self, recipe, base):
        self.recipe, self.base = recipe, Path(base) if base else Path.cwd()
        self.images, self.files = {}, {}

    def image(self, name, where):
        path = (self.base/name).resolve()
        if name not in self.images:
            if not path.is_file():
                raise AssetError(where, f'No image {path} (paths are relative to the recipe\'s folder).')
            self.images[name] = read_png(path, where)
            self.files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return self.images[name]

    def cell(self, sheet, cell, where):
        """RGBA rows of one cell of a sheet: [column, row] of a grid, or a named rectangle."""
        if not (isinstance(cell, str) or isinstance(cell, list) and len(cell) == 2
                and all(type(n) is int and n >= 0 for n in cell)):
            raise AssetError(where, 'A cell is [column, row] of a grid sheet, or the name of a cell.')
        sheets = self.recipe.get('sheets', {})
        if sheet not in sheets:
            raise AssetError(where+'/sheet', f'Unknown sheet {sheet!r}; declare it in the recipe\'s sheets.')
        spec = sheets[sheet]
        w, h, rows = self.image(spec['image'], f'/sheets/{sheet}/image')
        if 'grid' in spec:
            if not isinstance(cell, list):
                raise AssetError(where, f'Sheet {sheet!r} is a grid: name a cell by [column, row].')
            cw, ch = spec['grid']
            if w % cw or h % ch:
                raise AssetError(f'/sheets/{sheet}/grid', f'The grid ({cw} x {ch}) must divide the image ({w} x {h}).')
            col, row = cell
            if col >= w//cw or row >= h//ch:
                raise AssetError(where, f'Sheet {sheet!r} has {w//cw} columns and {h//ch} rows.')
            x, y = col*cw, row*ch
        else:
            if not isinstance(cell, str):
                raise AssetError(where, f'Sheet {sheet!r} has named cells: name one.')
            rects = self.named(sheet, spec)
            if cell not in rects:
                raise AssetError(where, f'Sheet {sheet!r} has no cell {cell!r}; it has {", ".join(sorted(rects))}.')
            x, y, cw, ch = rects[cell]
        return cw, ch, [r[x:x+cw] for r in rows[y:y+ch]]

    def named(self, sheet, spec):
        image = Path(spec['image'])
        side = image.with_suffix('.sheet.json')
        path = (self.base/side).resolve()
        where = f'/sheets/{sheet}'
        if not path.is_file():
            raise AssetError(where, f'Sheet {sheet!r} has no grid, so its cells are named in {path} '
                                    '({"format": "mei-sheet", "version": 1, "cells": {"name": [x, y, width, height]}}).')
        try:
            data = json.loads(path.read_text())
        except ValueError as error:
            raise AssetError(where, f'{path}: {error}') from error
        if not isinstance(data, dict) or data.get('format') != 'mei-sheet' or data.get('version') != 1 or not isinstance(data.get('cells'), dict):
            raise AssetError(where, f'{path} is not a mei-sheet, version 1, with cells.')
        w, h, _ = self.image(spec['image'], where+'/image')
        self.files[str(side)] = hashlib.sha256(path.read_bytes()).hexdigest()
        out = {}
        for name, rect in data['cells'].items():
            if (not isinstance(rect, list) or len(rect) != 4 or any(type(v) is not int for v in rect)
                    or rect[0] < 0 or rect[1] < 0 or rect[2] < 1 or rect[3] < 1 or rect[0]+rect[2] > w or rect[1]+rect[3] > h):
                raise AssetError(where, f'{path}: cell {name!r} must be [x, y, width, height] inside the {w} x {h} image.')
            out[name] = rect
        return out


def quantise(frames, cap):
    """frames of rows of (r, g, b) or None -> frames of rows of 15-bit colours or None, with at
    most cap colours: exact when the 15-bit colours fit, else a median cut (weighted by count;
    each box's colour its weighted mean) and the nearest colour. Returns (frames, colours before,
    whether quantised)."""
    counts = {}
    for frame in frames:
        for row in frame:
            for c in row:
                if c is not None:
                    k = rgb15_of(*c)
                    counts[k] = counts.get(k, 0)+1
    before = len(counts)
    if before <= cap:
        return [[[None if c is None else rgb15_of(*c) for c in row] for row in frame] for frame in frames], before, False
    rgb = {c: rgb_of(c) for c in counts}

    def box(items):
        """(items, score): a box's colours and how much splitting it pays (its widest channel
        range times its texels)."""
        chans = [[rgb[c][k] for c, _ in items] for k in range(3)]
        spread = [max(ch)-min(ch) for ch in chans]
        return items, (max(spread)*sum(n for _, n in items) if len(items) > 1 else -1), spread

    boxes = [box(sorted(counts.items()))]
    while len(boxes) < cap:
        # split the box that pays most, along its widest channel, at its weighted median
        at = max(range(len(boxes)), key=lambda i: (boxes[i][1], -i))
        items, score, spread = boxes[at]
        if score < 0:
            break
        k = max(range(3), key=lambda j: (spread[j], -j))
        items = sorted(items, key=lambda item: (rgb[item[0]][k], item[0]))
        total, run, cut = sum(n for _, n in items), 0, 1
        for j, (_, n) in enumerate(items[:-1]):
            run += n
            if run*2 >= total:
                cut = j+1
                break
        boxes[at:at+1] = [box(items[:cut]), box(items[cut:])]
    palette = []
    for items, _, _ in boxes:
        weight = sum(n for _, n in items)
        mean = [round(sum(rgb[c][k]*n for c, n in items)/weight) for k in range(3)]
        palette.append(rgb15_of(*mean))
    palette = sorted(set(palette))
    pal_rgb = [(rgb_of(q), q) for q in palette]
    nearest = {}
    for c in counts:
        r, g, b_ = rgb[c]
        nearest[c] = min(pal_rgb, key=lambda e: ((r-e[0][0])**2+(g-e[0][1])**2+(b_-e[0][2])**2, e[1]))[1]
    return [[[None if c is None else nearest[rgb15_of(*c)] for c in row] for row in frame] for frame in frames], before, True


class Texture:
    """One textured material's texture, before placement."""

    def __init__(self, name, spec, frames, width, height, source, before, quantised):
        self.material, self.spec = name, spec
        self.frames, self.width, self.height = frames, width, height
        self.bits = spec.get('bits', 4)
        self.projection = spec.get('projection', 'box')
        self.repeat = self.projection in REPEATING
        self.source, self.colours_before, self.quantised = source, before, quantised
        self.ticks = spec.get('ticks')
        self.tile = Tile(width, height, self.bits, frames, window=self.repeat, name=f'material {name!r}')

    @property
    def cutout(self):
        return self.tile.holes

    def summary(self):
        tile = self.tile
        out = {'material': self.material, 'source': self.source, 'width': self.width, 'height': self.height,
               'bits': self.bits, 'colours': len(tile.colours()), 'projection': self.projection,
               'repeat': self.repeat, 'cutout': self.cutout, 'vram_bytes': tile.vram_bytes()*len(self.frames) if False else tile.vram_bytes()}
        if self.quantised:
            out['quantised_from'] = self.colours_before
        if len(self.frames) > 1:
            out['frames'] = len(self.frames)
            out['ticks'] = self.ticks
            out['rom_bytes'] = tile.row_bytes()*tile.alloc_height*len(self.frames)
        return out


def image_files(recipe):
    """The files a recipe's textures read, relative to its folder: images, sheets and the
    sheets' NAME.sheet.json."""
    names = [m['texture']['image'] for m in recipe.get('materials',{}).values() if 'image' in m.get('texture',{})]
    for sheet in recipe.get('sheets',{}).values():
        names.append(sheet['image'])
        if 'grid' not in sheet:
            names.append(str(Path(sheet['image']).with_suffix('.sheet.json')))
    return sorted(set(names))


def describe(tex):
    """A texture's source in a few words, for messages: pattern 'brick', image art/x.png, ..."""
    src = tex.source
    if 'pattern' in src:
        return f"pattern {src['pattern']!r}"
    if 'texels' in src:
        return f"a {src['texels']} texel grid"
    if 'sheet' in src:
        cell = src.get('cell', src.get('frames'))
        return f"sheet {src['sheet']!r} cell {cell}"
    return f"image {src['image']}"


def load(recipe, materials, base, used):
    """Each textured material the mesh uses -> its Texture."""
    sources = Sources(recipe, base)
    depth = recipe.get('verification', {}).get('depth', False)
    out = {}
    for name in sorted(used):
        mat = materials[name]
        if 'texture' not in mat:
            continue
        spec, where = mat['texture'], f'/materials/{name}/texture'
        if 'palette' in mat or 'share' in mat:
            key = 'palette' if 'palette' in mat else 'share'
            raise AssetError(f'/materials/{name}/{key}', 'A textured material draws through palettes of its own texture; remove '+key+'.')
        kinds = [k for k in ('pattern', 'texels', 'image', 'sheet') if k in spec]
        if len(kinds) != 1:
            raise AssetError(where, 'Give exactly one source: pattern, texels, image or sheet (with cell or frames).')
        kind = kinds[0]
        cap = 15 if spec.get('bits', 4) == 4 else 255
        clear = spec.get('clear')
        for key in ('colors', 'params', 'size'):
            if key in spec and kind not in (('pattern', 'texels') if key == 'colors' else ('pattern',)):
                raise AssetError(f'{where}/{key}', f'{key} applies to patterns{" and texel grids" if key == "colors" else ""}.')
        if 'clear' in spec and kind not in ('pattern', 'texels'):
            raise AssetError(where+'/clear', 'clear names a colour of a pattern or texel grid; an image\'s holes are its transparent pixels.')
        if ('cell' in spec or 'frames' in spec or 'ticks' in spec) and kind != 'sheet':
            raise AssetError(where, 'cell, frames and ticks apply to sheet textures.')
        projection = spec.get('projection', 'box')
        if 'axis' in spec and projection not in ('planar', 'disc'):
            raise AssetError(where+'/axis', 'axis applies to the planar and disc projections.')
        if 'scale' in spec and projection == 'fit':
            raise AssetError(where+'/scale', 'A fit texture covers each face exactly; it takes no scale.')
        if kind in ('pattern', 'texels'):
            colors = [c.lower() for c in spec.get('colors', [])]
            if kind == 'pattern' and not colors:
                colors = [mat['color'].lower()]
            if clear is not None and clear.lower() not in colors:
                raise AssetError(where+'/clear', f'clear must be one of the texture\'s colors ({", ".join(colors)}).')
            if kind == 'pattern':
                params_spec, minimum, fn = PATTERNS[spec['pattern']]
                if len(colors) < minimum:
                    raise AssetError(where+'/colors', f'Pattern {spec["pattern"]!r} needs at least {minimum} colours.')
                size = spec.get('size', 16)
                if type(size) is int:
                    size = [size, size]
                if (not isinstance(size, list) or len(size) != 2 or any(type(n) is not int for n in size)
                        or not all(1 <= n <= 255 for n in size)):
                    raise AssetError(where+'/size', 'size is an integer 1-255 (a square) or [width, height].')
                w, h = size
                params = pattern_params(spec['pattern'], spec.get('params', {}), where+'/params')
                indices = fn(w, h, params, len(colors), where+'/params')
                source = {'pattern': spec['pattern'], 'params': params}
            else:
                rows = spec['texels']
                w, h = len(rows[0]), len(rows)
                if any(len(r) != w for r in rows):
                    raise AssetError(where+'/texels', 'Every row of texels has the same length.')
                indices = [[int(ch, 16) for ch in r] for r in rows]
                if max(max(r) for r in indices) >= len(colors):
                    raise AssetError(where+'/texels', f'A texel names colour {max(max(r) for r in indices)}; there are {len(colors)} colors.')
                source = {'texels': f'{w} x {h}'}
            rgb = [None if c == (clear or '').lower() else hex_rgb(c) for c in colors]
            frames = [[[rgb[i] for i in row] for row in indices]]
        else:
            if kind == 'image':
                w, h, pixels = sources.image(spec['image'], where+'/image')
                pixel_frames = [pixels]
                source = {'image': spec['image'], 'sha256': sources.files[spec['image']]}
            else:
                if ('cell' in spec) == ('frames' in spec):
                    raise AssetError(where, 'A sheet texture takes cell (one picture) or frames (an animation).')
                if 'frames' in spec and 'ticks' not in spec:
                    raise AssetError(where+'/ticks', 'An animated texture says how many ticks each frame shows.')
                if 'ticks' in spec and 'frames' not in spec:
                    raise AssetError(where+'/ticks', 'ticks applies to frames.')
                cells = spec['frames'] if 'frames' in spec else [spec['cell']]
                pixel_frames, size = [], None
                for k, cell in enumerate(cells):
                    cw, ch, pixels = sources.cell(spec['sheet'], cell, where+(f'/frames/{k}' if 'frames' in spec else '/cell'))
                    if size and size != (cw, ch):
                        raise AssetError(where+f'/frames/{k}', 'Every frame of an animation has the same size.')
                    size = (cw, ch)
                    pixel_frames.append(pixels)
                w, h = size
                source = {'sheet': spec['sheet'], 'image': recipe['sheets'][spec['sheet']]['image'],
                          'sha256': sources.files[recipe['sheets'][spec['sheet']]['image']]}
                source['frames' if 'frames' in spec else 'cell'] = cells if 'frames' in spec else cells[0]
            frames = [[[None if p[3] < 128 else p[:3] for p in row] for row in pixels] for pixels in pixel_frames]
        holes = [[[c is None for c in row] for row in frame] for frame in frames]
        if any(h != holes[0] for h in holes):
            raise AssetError(where+'/frames', 'Every frame of an animation has its holes (transparent pixels) in the same '
                                              'places, so the faces cover the same pixels whatever the frame.')
        frames, before, quantised = quantise(frames, cap)
        try:
            texture = Texture(name, spec, frames, w, h, source, before, quantised)
        except AssetError as error:
            raise AssetError(where, str(error)) from error
        if texture.cutout and not depth:
            raise AssetError(where, 'This texture has holes (transparent pixels, or its clear colour): cutouts draw '
                                    'right only with the depth buffer. Set "verification": {"depth": true, '
                                    '"perspective": true} and draw the asset with render_depth(true), or make it opaque.')
        if texture.bits == 8 and texture.tile.alloc_height > 128:
            raise AssetError(where, 'An 8-bit texture is at most 128 texels tall (127 when drawn once).')
        out[name] = texture
    return out


# ---------------------------------------------------------------------------------------------
# Projections: surface coordinates (right, down) in world units, then rotate, flip, scale or
# fit, offset -> texel coordinates.

def basis(n):
    """(right, down) unit vectors of a plane with outward unit normal n, as seen from outside:
    up is +Y projected onto the plane (+Z for a face looking straight up or down)."""
    up = (0.0, 1.0, 0.0) if abs(n[1]) < 0.9 else (0.0, 0.0, 1.0)
    right = norm(cross(n, up))
    up = cross(right, n)
    return right, mul(up, -1)


AXES = {'x': (1.0, 0.0, 0.0), 'y': (0.0, 1.0, 0.0), 'z': (0.0, 0.0, 1.0)}
PLANAR_VIEW = {'x': (1.0, 0.0, 0.0), 'y': (0.0, 1.0, 0.0), 'z': (0.0, 0.0, -1.0)}


def orient(a, b, spec):
    """Rotate (clockwise, as seen) and flip surface coordinates."""
    for _ in range(spec.get('rotate', 0)//90):
        a, b = b, -a
    flip = spec.get('flip')
    if flip in ('u', 'both'):
        a = -a
    if flip in ('v', 'both'):
        b = -b
    return a, b


def face_normal(points):
    return norm(cross(sub(points[1], points[0]), sub(points[2], points[0])))


def project(mesh, textures):
    """Float texel coordinates (Face.uvf) for every corner of every textured face."""
    by_part = {}
    for face in mesh.faces:
        if face.material in textures:
            by_part.setdefault((face.part, face.material), []).append(face)
    for (part, name), faces in by_part.items():
        tex = textures[name]
        spec, kind = tex.spec, tex.projection
        su, sv = spec.get('scale', [1, 1])
        ou, ov = spec.get('offset', [0, 0])
        W, H = tex.width, tex.height

        def finish(a, b):
            return ((a/su+ou)*W, (b/sv+ov)*H)

        if kind == 'fit':
            groups = {}
            for face in faces:
                if face.uv:
                    continue
                n = face_normal(face.local)
                d = dot(n, face.local[0])
                key = (face.polygon, tuple(round(x, 5) for x in n), round(d, 5))
                groups.setdefault(key, []).append((face, n))
            for (_, _, _), members in groups.items():
                n = members[0][1]
                right, down = basis(n)
                coords = [[orient(dot(p, right), dot(p, down), spec) for p in f.local] for f, _ in members]
                flat = [c for cs in coords for c in cs]
                lo = [min(c[k] for c in flat) for k in (0, 1)]
                hi = [max(c[k] for c in flat) for k in (0, 1)]
                for (face, _), cs in zip(members, coords):
                    face.uvf = tuple(((a-lo[0])/(hi[0]-lo[0] or 1)*W+ou*W, (b-lo[1])/(hi[1]-lo[1] or 1)*H+ov*H) for a, b in cs)
        elif kind == 'disc':
            n = PLANAR_VIEW[spec.get('axis', 'y')]
            right, down = basis(n)
            radius = max(math.hypot(*(p[k] for k in range(3) if n[k] == 0)) for f in faces for p in f.local)
            span = spec['scale'] if 'scale' in spec else [2*radius, 2*radius]
            for face in faces:
                if face.uv:
                    continue
                face.uvf = tuple(((a/span[0]+0.5+ou)*W, (b/span[1]+0.5+ov)*H) for a, b in
                                 (orient(dot(p, right), dot(p, down), spec) for p in face.local))
        elif kind == 'cylindrical':
            radius = max(math.hypot(p[0], p[2]) for f in faces for p in f.local)
            around = max(1, round(2*math.pi*radius/su))
            for face in faces:
                if face.uv:
                    continue
                angles = [math.atan2(p[0], -p[2]) if math.hypot(p[0], p[2]) > 1e-9 else None for p in face.local]
                known = [t for t in angles if t is not None]
                ref = known[0] if known else 0.0
                fill = math.atan2(sum(math.sin(t) for t in known), sum(math.cos(t) for t in known)) if known else 0.0
                out = []
                for p, t in zip(face.local, angles):
                    t = fill if t is None else t
                    t += round((ref-t)/(2*math.pi))*2*math.pi        # unwrap next to the first corner
                    a = t/(2*math.pi)*around*su
                    out.append(finish(*orient(a, -p[1], spec)))
                face.uvf = tuple(out)
        else:
            for face in faces:
                if face.uv:
                    continue
                if kind == 'planar':
                    # as seen from the front (-Z), from +X, from above (+Y)
                    n = PLANAR_VIEW[spec.get('axis', 'z')]
                else:
                    m = face_normal(face.local)
                    k = max(range(3), key=lambda i: (abs(m[i]), -i))
                    n = tuple(float(i == k)*(1 if m[k] > 0 else -1) for i in range(3))
                right, down = basis(n)
                face.uvf = tuple(finish(*orient(dot(p, right), dot(p, down), spec)) for p in face.local)
        for face in faces:
            if face.uv:
                face.uvf = tuple((u*W, v*H) for u, v in face.uv)


def repeat_lines(size):
    """The spacing of the cuts for a repeating tile of size texels: the largest multiple of size
    not above 255, so that a piece shifted to start in its first repeat fits 0-255."""
    return size*(255//size)


def needs_split(face, tex):
    """Whether a face of a repeating texture spans more than 255 texels after the shift that
    finish() makes (its first corner's repeat to 0)."""
    coords = [(round(u), round(v)) for u, v in face.uvf]
    for axis, size in ((0, tex.width), (1, tex.height)):
        lo = min(c[axis] for c in coords)
        if max(c[axis] for c in coords)-math.floor(lo/size)*size > 255:
            return True
    return False


def split(mesh, textures):
    """Cut the faces of repeating textures that span more than 255 texels along the lines
    u = k L and v = k L (L = repeat_lines), the same lines for every face of the texture, so
    neighbours that are both cut share their cuts. A neighbour that needed no cut gets the cut
    points on the edges it shares (no T-junctions). Pieces replace their face in place; new
    vertices are appended. Returns the number of faces added."""
    made, on_edge = {}, {}
    first = []
    for face in mesh.faces:
        tex = textures.get(face.material)
        if not tex or not tex.repeat or not needs_split(face, tex):
            first.append((face, None))
            continue
        pieces = [[(i, uv) for i, uv in zip(face.indices, face.uvf)]]
        for axis, size in ((0, tex.width), (1, tex.height)):
            step = repeat_lines(size)
            done = []
            for piece in pieces:
                lo = min(uv[axis] for _, uv in piece)
                hi = max(uv[axis] for _, uv in piece)
                work = [piece]
                for k in range(math.floor(lo/step)+1, math.ceil(hi/step)):
                    work = [p for poly in work for p in cut(poly, axis, k*step, mesh, made, on_edge)]
                done += work
            pieces = done
        tris = []
        for piece in pieces:
            for k in range(1, len(piece)-1):
                tris.append((piece[0], piece[k], piece[k+1]))
        first.append((face, tris))
    out, added = [], 0
    for face, tris in first:
        if tris is None:
            tris = insert(face, on_edge)
            if tris is None:
                out.append(face)
                continue
        for tri in tris:
            f = face.copy(tuple(i for i, _ in tri))
            f.local = None
            f.uvf = tuple(uv for _, uv in tri) if face.uvf else None
            out.append(f)
        added += len(tris)-1
    mesh.faces = out
    return added


def cut(poly, axis, c, mesh, made, on_edge):
    """A convex polygon of (vertex, uv) split by the line uv[axis] = c into two polygons (a
    corner on the line belongs to both), or itself when the line does not cross it."""
    # A corner a hair off the line (float error of a scale that is not a power of two: a corner at
    # 240.00000000000017 texels) is on it: cutting there would make a sliver that collapses at
    # 16.16 precision. ON_LINE is far below a 16.16 step for any tile and scale.
    vals = [0.0 if abs(uv[axis]-c) <= ON_LINE else uv[axis]-c for _, uv in poly]
    if all(v >= 0 for v in vals) or all(v <= 0 for v in vals):
        return [poly]
    below, above, n = [], [], len(poly)
    for k in range(n):
        (i, uv), (j, uvj) = poly[k], poly[(k+1) % n]
        vp, vq = vals[k], vals[(k+1) % n]
        if vp <= 0:
            below.append(poly[k])
        if vp >= 0:
            above.append(poly[k])
        if vp < 0 < vq or vq < 0 < vp:
            # canonical direction (lower vertex index first), so both faces of an edge agree
            (a, ua), (b, ub) = ((i, uv), (j, uvj)) if i <= j else ((j, uvj), (i, uv))
            t = (c-ua[axis])/(ub[axis]-ua[axis])
            key = (a, b, round(t, 9))
            if key not in made:
                made[key] = len(mesh.vertices)
                pa, pb = mesh.vertices[a], mesh.vertices[b]
                mesh.vertices.append(add(pa, mul(sub(pb, pa), t)))
                on_edge.setdefault((a, b), []).append((t, made[key]))
            point = list(add(ua, mul(sub(ub, ua), t)))
            point[axis] = c
            entry = (made[key], tuple(point))
            below.append(entry)
            above.append(entry)
    return [below, above]


ON_LINE = 1e-6     # texels


def insert(face, on_edge):
    """A face that was not cut, split at the cut points on its edges (fans from the opposite
    corner), or None when its edges have none."""
    def points(x, y):
        a, b = min(x, y), max(x, y)
        found = sorted(on_edge.get((a, b), []))
        return [(t if x == a else 1-t, v) for t, v in found]

    def lerp(p, q, t):
        return tuple(a+(b-a)*t for a, b in zip(p, q)) if p is not None else None

    uvs = face.uvf or (None, None, None)
    work = [tuple(zip(face.indices, uvs))]
    done, changed = [], False
    while work:
        tri = work.pop(0)
        for k in range(3):
            (x, ux), (y, uy), (z, uz) = tri[k], tri[(k+1) % 3], tri[(k+2) % 3]
            pts = sorted(points(x, y))
            if pts:
                changed = True
                chain = [(x, ux)]+[(v, lerp(ux, uy, t)) for t, v in pts]+[(y, uy)]
                pieces = [((chain[m][0], chain[m][1]), (chain[m+1][0], chain[m+1][1]), (z, uz))
                          for m in range(len(chain)-1)]
                work = pieces+work
                break
        else:
            done.append(tri)
    return done if changed else None


# ---------------------------------------------------------------------------------------------

def finish(mesh, textures, recipe, layout):
    """Integer texel coordinates per textured face, the tiles, the window count, and the
    default placement of a single asset: slots from layout['slot'] down (never 15), avoiding
    the palette swatch, 4-bit palettes after the swatch's."""
    used = {}
    for face in mesh.faces:
        tex = textures.get(face.material)
        if not tex:
            continue
        used.setdefault(face.material, tex)
        coords = [(round(u), round(v)) for u, v in face.uvf]
        if tex.repeat:
            su = math.floor(min(u for u, _ in coords)/tex.width)*tex.width
            sv = math.floor(min(v for _, v in coords)/tex.height)*tex.height
            coords = [(u-su, v-sv) for u, v in coords]
            if max(max(u, v) for u, v in coords) > 255:
                raise AssetError('/nodes', f'Part {face.part!r}: a face spans more than 255 texels of {face.material!r} after splitting.')
        else:
            if min(min(u, v) for u, v in coords) < 0 or max(u for u, _ in coords) > tex.width or max(v for _, v in coords) > tex.height:
                raise AssetError(f'/materials/{face.material}/texture', f'Part {face.part!r}: a {tex.projection} texture is drawn once, so its '
                                 'coordinates stay inside it; remove offset (or hand UVs outside 0-1), or use a repeating projection.')
        face.texcoords = tuple(coords)
    windowed = [t for t in used.values() if t.repeat]
    keys = []
    for t in windowed:
        if t.tile.key not in keys:
            keys.append(t.tile.key)
    if len(keys) > MAX_WINDOWS:
        users = {}
        for t in windowed:
            users.setdefault(t.tile.key, []).append(t)
        listed = '; '.join(f'{k+1}: {describe(ts[0])} {ts[0].width} x {ts[0].height} ({", ".join(t.material for t in ts)})'
                           for k, ts in enumerate(users[key] for key in keys))
        raise AssetError('/materials', f'{len(keys)} different repeating textures; a mesh has at most {MAX_WINDOWS} texture '
                                       f'windows. Windows and the materials using them: {listed}. Merge textures (materials '
                                       'with the same texture share a window), or draw some with fit.')
    info = {'textures': used, 'tiles': [t.tile for t in used.values()]}
    info['packing'] = default_packing(info, mesh, layout)
    return info


def default_packing(info, mesh, layout):
    """Where `build` puts an asset's textures: slots from the palette layout's slot downward,
    the swatch's 8-row block reserved, 4-bit palettes after the swatch's palettes."""
    palette = mesh.palette
    slot = layout['slot']
    reserved, first = [], layout['first']
    if palette:
        reserved.append((slot, 0, layout['row']//8*8, 16, 8))
        first = palette['palettes'][-1]+1
    slots = [s for s in range(slot, -1, -1)]+[s for s in range(14, slot, -1)]
    return pack_tiles(info['tiles'], slots=slots, first_palette=first, reserved=reserved, path='/materials')
