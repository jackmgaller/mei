"""Terrain: ground heightfields and profiles swept along paths, in world coordinates, cut per
cell by the kit so that seams match by construction (WORLDKIT.md, "Terrain").

    result = compile_terrain(world, base, cell_size, cells, surface_of, warnings, overhang,
                             floor_max_degrees)
    result.pieces[(i, j)]      [Piece]: a native mesh per tile or sweep, placed at the cell centre
    result.collision[(i, j)]   [pack.Tri] in world coordinates
    result.palette             the provisional palette entries of the materials used

A **field** is a grid of height samples `spacing` apart over a rectangle. Its heights start from
`height` or a text file and are changed by operations in order; its quads take materials. The
kit cuts it into tiles (a cell, or 16 quads a side if that is less) and merges each tile's quads
greedily into rectangles that share a material and lie within `tolerance` of the patch through
their corners. A rectangle with only its four corners on its edges is two triangles; one with
more (a smaller neighbour's corners, or the neighbouring tile's) is zipped between its two long
sides or fanned from its centre, so no edge has a vertex in the middle of another's: no
T-junctions inside a tile, and across a tile edge both tiles use the same points (every corner
either tile has there, at any level of detail). The coarse level is the same merge with a
larger tolerance; it keeps the tile's edge points, so neighbours drawn at different levels
still meet.

A **sweep** is a profile carried along a path: cross-sections at the path's points (mitred at
corners), where the path crosses a cell edge, and at each step of a stair. Each strip between two
cross-sections goes to the cell holding the middle of its centre line; the cross-section on a
seam is shared, so the two cells' pieces meet there exactly.

A material with a **texture** (an Asset Kit texture: a pattern, texel grid or image, projected
`box` or `planar` in world coordinates) repeats in world coordinates, so its pattern runs on
across tiles, cells and sweeps with no seam of its own. Each face's texel coordinates are
shifted by whole repeats to start in the first. The texture is stored repeated `span` texels
past its first repeat, drawn without a texture window, for the faces that reach no further (a
mesh with windows leaves the reader's quicker face loops); a face reaching further samples the
texture once more, stored plainly, through a texture window (8-bit coordinates: up to 255
texels), and only the pieces holding such faces carry a window table. Rectangles and sweep
strips of a textured material are kept within that windowed reach. The faces are written for the
region's texture packing by world.py (MeshOut.native).

Nothing here knows what ground, a path or a step is for: the outputs are ordinary placements and
collision triangles, and the World Checker checks them as it checks any other.
"""
from dataclasses import dataclass, field
import hashlib
import math

import meshlib
from assetkit import textures as T
from assetkit.compiler import assign_palette, shading
from kitcore.errors import KitError, pointer
from kitcore.texpack import Tile
from .schema import WorldError

TAG_FIELD = 0xFFFE          # placement and collision tag of a field's tiles
TAG_SWEEP = 0xFFFD          # of a sweep's pieces
TAG_SCATTER = 0xFFFC        # of scattered props' merged chunks and their collision
MAX_TILE_QUADS = 32
DEFAULT_TILE_QUADS = 16
DEFAULT_TOLERANCE = 0.01
DEFAULT_LOD_TOLERANCE = 0.25
DEFAULT_LOD_BAND = 2.0
MIN_MITRE_COS = 0.5         # a path may turn at most 120 degrees at a point
ONE = 65536
TERRAIN_PROJECTIONS = ('box', 'planar')
GENTLE = 0.9                # a textured quad rising less than this a unit is projected from above
DEFAULT_SPAN = 96           # texels a textured terrain face may reach past its first repeat unwindowed
MAX_TEXEL = 255             # a face's texel coordinates are 8 bits


def q16(v):
    """v rounded to the 16.16 grid (halves away from zero, as the pack rounds)."""
    r = math.floor(abs(v) * ONE + 0.5) / ONE
    return r if v >= 0 else -r


# ---- textures

def load_textures(materials, base, files):
    """material -> assetkit Texture, for each terrain material with a texture. A terrain texture
    is a pattern, a texel grid or an image (relative to the world file), without holes, projected
    `box` (default) or `planar` (default axis y: from above) in world coordinates. The images
    read join files [(path, sha256)]."""
    out = {}
    for name, mat in materials.items():
        if 'texture' not in mat:
            continue
        where = pointer('/terrain/materials', name) + '/texture'
        spec = dict(mat['texture'])
        span = spec.pop('span', DEFAULT_SPAN)
        for key in ('sheet', 'cell', 'frames', 'ticks'):
            if key in spec:
                raise WorldError(f'{where}/{key}', 'A terrain texture is a pattern, a texel grid or an image '
                                 '(no sheets or animations).')
        if 'clear' in spec:
            raise WorldError(where + '/clear', 'Terrain is solid: its textures have no holes.')
        projection = spec.setdefault('projection', 'box')
        if projection not in TERRAIN_PROJECTIONS:
            raise WorldError(where + '/projection', 'A terrain texture repeats in world coordinates: projection '
                             'box (the default: each face from the axis nearest its normal) or planar.')
        if projection == 'planar':
            spec.setdefault('axis', 'y')
        try:
            tex = T.load({'verification': {'depth': True}}, {name: dict(mat, texture=spec)}, base, {name})[name]
        except KitError as error:
            path = '/terrain' + error.path if error.path.startswith('/materials/') else where
            raise WorldError(path, str(error)) from error
        if tex.cutout:
            raise WorldError(where + '/image', 'Terrain is solid: the image has transparent pixels. Make it opaque.')
        if 'image' in spec:
            f = (base / spec['image']).resolve()
            if str(f) not in [g for g, _ in files]:
                files.append((str(f), hashlib.sha256(f.read_bytes()).hexdigest()))
        if not tex.tile.window:
            raise WorldError(where, 'A terrain texture repeats: its sides are 8, 16, 32, 64 or 128 texels.')
        # Stored repeated, span texels further each way, and drawn once: a face that starts in the
        # first repeat and reaches at most span texels on needs no texture window (a mesh with
        # windows leaves the reader's quicker loops; DECISIONS.md, "Texture windows"). Faces that
        # reach further sample the tile as loaded, through a window.
        tex.span = span
        tex.window_tile = tex.tile
        w, h = tex.width + span, tex.height + span
        if w > 255 or h > 255 or (tex.bits == 8 and h + 1 > 128):
            raise WorldError(where + '/span', f'The texture stored {span} texels further each way is {w} x {h} '
                             f'texels; at most 255 a side{" (127 tall for an 8-bit texture)" if tex.bits == 8 else ""}. '
                             'Use a smaller span or a smaller texture.')
        frames = [[[f[y % tex.height][x % tex.width] for x in range(w)] for y in range(h)] for f in tex.tile.frames]
        tex.tile = Tile(w, h, tex.bits, frames, window=False, name=f'terrain material {name!r}')
        out[name] = tex
    return out


def mean_colour(tex):
    """'#rrggbb': the mean of a texture's texels (frame 0), its colour from afar."""
    texels = [T.rgb_of(c) for row in tex.frames[0] for c in row if c is not None]
    return '#' + ''.join(f'{round(sum(t[k] for t in texels) / len(texels)):02x}' for k in range(3))


def texel_reach(tex, stored=False):
    """The farthest (units) two corners of one face of tex may lie apart along an axis of its
    projection, so that the face, starting in the first repeat, stays within 8-bit texel
    coordinates through a texture window, or, stored, within the stored repeats (span texels on,
    drawn without a window); less one texel for rounding."""
    su, sv = tex.spec.get('scale', [1, 1])
    if stored:
        return (tex.span - 1) / max(tex.width / su, tex.height / sv)
    return min((MAX_TEXEL - tex.width) / (tex.width / su), (MAX_TEXEL - tex.height) / (tex.height / sv))


def texel_coords(tex, pts):
    """Integer texel coordinates of a face's world corners (wound outward right-handed) under a
    repeating terrain texture, as the Asset Kit projects (box: from the axis nearest the face's
    normal; planar: along its axis), in world coordinates, shifted by whole repeats so the face
    starts in its first; whether it needs a texture window (it reaches past the stored repeats);
    and whether it had to be squeezed: a face reaching past 255 texels along an axis (a
    near-vertical quad no merge can shrink) has the texture stretched along that axis to fit."""
    spec = tex.spec
    if tex.projection == 'planar':
        n = T.PLANAR_VIEW[spec['axis']]
    else:
        m = cross(sub(pts[1], pts[0]), sub(pts[2], pts[0]))
        k = max(range(3), key=lambda i: (abs(m[i]), -i))
        n = tuple(float(i == k) * (1 if m[k] > 0 else -1) for i in range(3))
    right, down = T.basis(n)
    su, sv = spec.get('scale', [1, 1])
    ou, ov = spec.get('offset', [0, 0])
    w, h = tex.width, tex.height
    coords = []
    for p in pts:
        a, b = T.orient(dot(p, right), dot(p, down), spec)
        coords.append((round((a / su + ou) * w), round((b / sv + ov) * h)))
    du = math.floor(min(u for u, _ in coords) / w) * w
    dv = math.floor(min(v for _, v in coords) / h) * h
    coords = [(u - du, v - dv) for u, v in coords]
    limits = (tex.tile.width, tex.tile.height)
    windowed = any(max(c[k] for c in coords) > limits[k] for k in (0, 1))
    squeezed = any(max(c[k] for c in coords) > MAX_TEXEL for k in (0, 1))
    if squeezed:
        # stretched either way: to the stored repeats, which need no window
        windowed = False
        for k in (0, 1):
            top = max(c[k] for c in coords)
            if top > limits[k]:
                coords = [tuple(round(c[i] * limits[k] / top) if i == k else c[i] for i in (0, 1)) for c in coords]
    return coords, windowed, squeezed


@dataclass
class Piece:
    """A mesh the kit made for one cell: drawn at the cell centre, yaw 0."""
    kind: str                   # 'field' or 'sweep'
    name: str
    mesh: object                # level 0: bytes with provisional palette colours, or a MeshOut
                                # with textured faces, written per region (MeshOut.native)
    faces: int
    levels: list = field(default_factory=list)  # [(distance, mesh)] coarser levels, as mesh
    band: float = DEFAULT_LOD_BAND
    ground: bool = True
    tag: int = TAG_FIELD
    materials: set = field(default_factory=set)
    level_faces: list = field(default_factory=list)


@dataclass
class Result:
    pieces: dict                # (i, j) -> [Piece]
    collision: dict             # (i, j) -> [P.Tri]
    palette: dict               # assign_palette()'s result, or None
    report: dict
    files: list                 # height files read
    fields: dict = None         # name -> Field (its samples H, materials, h(), for tests and tools)
    water: list = field(default_factory=list)   # (a, b, c, surface): water surfaces facing up
    paths: dict = field(default_factory=dict)   # a draped path's points, as the kit resolved them
    floor_cos: float = 0.7071
    textures: dict = field(default_factory=dict)  # material -> assetkit Texture (textured terrain)
    windowed: set = field(default_factory=set)    # textured materials with faces through a texture window

    def floors(self):
        """A Floors query over the terrain's and sweeps' floors (not water)."""
        if not hasattr(self, '_floors'):
            self._floors = Floors([t for ts in self.collision.values() for t in ts], self.floor_cos)
        return self._floors

    def water_level(self, x, z):
        """The highest water surface at (x, z), or None."""
        best = None
        for a, b, c, _ in self.water:
            y = height_in((a, b, c), x, z)
            if y is not None and (best is None or y > best):
                best = y
        return best


def height_in(v, x, z):
    """The height of triangle v (world corners) at (x, z) seen from above, or None outside."""
    sides = [(v[(e + 1) % 3][0] - v[e][0]) * (z - v[e][2]) - (v[(e + 1) % 3][2] - v[e][2]) * (x - v[e][0])
             for e in range(3)]
    if not (all(s >= -1e-9 for s in sides) or all(s <= 1e-9 for s in sides)):
        return None
    n = cross(sub(v[1], v[0]), sub(v[2], v[0]))
    if abs(n[1]) < 1e-12:
        return None
    return v[0][1] - (n[0] * (x - v[0][0]) + n[2] * (z - v[0][2])) / n[1]


class Floors:
    """The highest floor under a point, over collision triangles (pack.Tri, world corners),
    bucketed every 4 units."""

    def __init__(self, tris, floor_cos):
        self.grid = {}
        for t in tris:
            v = tuple(tuple(float(c) for c in p) for p in (t.a, t.b, t.c))
            n = cross(sub(v[1], v[0]), sub(v[2], v[0]))
            ln = math.sqrt(dot(n, n))
            if not ln or abs(n[1]) / ln < floor_cos:
                continue
            xs, zs = [p[0] for p in v], [p[2] for p in v]
            for i in range(math.floor(min(xs) / 4), math.floor(max(xs) / 4) + 1):
                for j in range(math.floor(min(zs) / 4), math.floor(max(zs) / 4) + 1):
                    self.grid.setdefault((i, j), []).append((v, t.tag, abs(n[1]) / ln))

    def at(self, x, z, below=None):
        """(height, tag, normal's y) of the highest floor at (x, z), at or under below when
        given; None."""
        best = None
        for v, tag, ny in self.grid.get((math.floor(x / 4), math.floor(z / 4)), ()):
            y = height_in(v, x, z)
            if y is None or (below is not None and y > below + 1e-6):
                continue
            if best is None or y > best[0]:
                best = (y, tag, ny)
        return best


def smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


# ---- areas

def _seg_closest(px, pz, a, b):
    """(distance, t) from (px, pz) to the segment a-b (each (x, z, ...)) seen from above."""
    dx, dz = b[0] - a[0], b[-1] - a[-1]
    ll = dx * dx + dz * dz
    t = 0.0 if ll == 0 else max(0.0, min(1.0, ((px - a[0]) * dx + (pz - a[-1]) * dz) / ll))
    x, z = a[0] + dx * t, a[-1] + dz * t
    return math.hypot(px - x, pz - z), t


class Polyline:
    """A path's line, for distances and heights seen from above."""

    def __init__(self, points, closed):
        self.points = [tuple(p) for p in points]
        self.closed = closed
        self.segs = list(zip(self.points, self.points[1:]))
        if closed:
            self.segs.append((self.points[-1], self.points[0]))

    def nearest(self, x, z):
        """(distance, height of the line there)."""
        best = None
        for a, b in self.segs:
            d, t = _seg_closest(x, z, a, b)
            if best is None or d < best[0]:
                best = (d, a[1] + (b[1] - a[1]) * t)
        return best

    def beyond(self, x, z, d):
        """Whether (x, z), at distance d from the line, lies past an end of an open path: its
        nearest point is the end, and it is ahead of it along the end segment."""
        if self.closed:
            return False
        for (a, b), sign in ((self.segs[0], -1), (self.segs[-1], 1)):
            p, q = (a, b) if sign > 0 else (b, a)      # q: the end, p: the point before it
            if math.hypot(x - q[0], z - q[-1]) <= d + 1e-9 and \
                    (x - q[0]) * (q[0] - p[0]) + (z - q[-1]) * (q[-1] - p[-1]) > 0:
                return True
        return False


class Area:
    """The signed distance (units, <= 0 inside) from a point to an operation's area."""

    def __init__(self, spec, paths, path):
        self.kind = None
        if spec is None:
            return
        kinds = [k for k in ('rect', 'circle', 'polygon', 'path') if k in spec]
        if len(kinds) != 1:
            raise WorldError(path, 'An area is exactly one of rect, circle, polygon or path.')
        self.kind = kinds[0]
        if ('width' in spec) != (self.kind == 'path'):
            raise WorldError(path + '/width', 'A path area takes a width, and only a path area does.')
        v = spec[self.kind]
        if self.kind == 'rect':
            self.r = (min(v[0], v[2]), min(v[1], v[3]), max(v[0], v[2]), max(v[1], v[3]))
        elif self.kind == 'circle':
            if v[2] <= 0:
                raise WorldError(path + '/circle/2', 'A circle\'s radius is positive.')
            self.c = v
        elif self.kind == 'polygon':
            self.poly = [tuple(p) for p in v]
        else:
            if v not in paths:
                raise WorldError(path + '/path', f'No path {v!r} in the world file\'s paths.')
            self.line = Polyline(paths[v]['points'], paths[v].get('closed', False))
            self.half = spec['width'] / 2

    def distance(self, x, z):
        k = self.kind
        if k is None:
            return -1.0
        if k == 'rect':
            x0, z0, x1, z1 = self.r
            dx, dz = max(x0 - x, 0.0, x - x1), max(z0 - z, 0.0, z - z1)
            if dx == 0 and dz == 0:
                return -min(x - x0, x1 - x, z - z0, z1 - z)
            return math.hypot(dx, dz)
        if k == 'circle':
            return math.hypot(x - self.c[0], z - self.c[1]) - self.c[2]
        if k == 'polygon':
            inside = False
            best = None
            n = len(self.poly)
            for i in range(n):
                a, b = self.poly[i], self.poly[(i + 1) % n]
                if (a[1] > z) != (b[1] > z) and x < a[0] + (z - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
                    inside = not inside
                d, _ = _seg_closest(x, z, a, b)
                best = d if best is None else min(best, d)
            return -best if inside else best
        return self.line.nearest(x, z)[0] - self.half

    def weight(self, x, z, falloff):
        d = self.distance(x, z)
        if d <= 0:
            return 1.0
        if falloff <= 0 or d >= falloff:
            return 0.0
        return smoothstep(1 - d / falloff)


# ---- heightfields

class Field:
    def __init__(self, name, spec, ctx):
        self.name, self.spec = name, spec
        self.path = pointer('/terrain/fields', name)
        s = spec['spacing']
        self.s = s
        (x0, z0), (x1, z1) = spec['min'], spec['max']
        for k, v in enumerate((x0, z0)):
            if v / s != math.floor(v / s):
                raise WorldError(f'{self.path}/min/{k}', f'The field\'s corners are multiples of its spacing ({s}).')
        for k, v in enumerate((x1, z1)):
            if v / s != math.floor(v / s):
                raise WorldError(f'{self.path}/max/{k}', f'The field\'s corners are multiples of its spacing ({s}).')
        if x1 <= x0 or z1 <= z0:
            raise WorldError(self.path + '/max', 'max lies beyond min in x and z.')
        size = ctx.size
        if size / s > 4096 or (x1 - x0) / s > 8192 or (z1 - z0) / s > 8192:
            raise WorldError(self.path + '/spacing', 'At most 8,192 quads along a side of a field.')
        self.qx0, self.qz0 = int(x0 / s), int(z0 / s)       # lattice coordinates of the low corner
        self.nx, self.nz = int((x1 - x0) / s), int((z1 - z0) / s)
        if self.nx * self.nz > 4_000_000:
            raise WorldError(self.path, 'At most 4,000,000 quads in a field.')
        tile = spec.get('tile')
        cell_quads = int(size / s)
        if tile is None:
            self.tq = min(cell_quads, DEFAULT_TILE_QUADS)
        else:
            if tile > size or tile / s > MAX_TILE_QUADS or tile / s < 1:
                raise WorldError(self.path + '/tile', f'A tile is at most a cell ({size}) and {MAX_TILE_QUADS} quads '
                                 f'({MAX_TILE_QUADS * s} units at this spacing), and at least one quad.')
            self.tq = int(tile / s)
        if cell_quads < 1:
            raise WorldError(self.path + '/spacing', 'The spacing is larger than a cell.')
        mats = ctx.materials
        for key in ('material',):
            if spec[key] not in mats:
                raise WorldError(f'{self.path}/{key}', f'No terrain material {spec[key]!r}.')
        if 'steep' in spec and spec['steep']['material'] not in mats:
            raise WorldError(self.path + '/steep/material', f'No terrain material {spec["steep"]["material"]!r}.')
        # slide_floor_degrees: faces steeper than the game's floor limit, up to this slope, are
        # floors as well as walls, so a falling body lands on steep ground (and the game slides it
        # down) instead of sinking between walls; the quads' splits judge kinds by it
        self.slide_floor = spec.get('slide_floor_degrees')
        self.floor_cos = ctx.floor_cos if self.slide_floor is None else math.cos(math.radians(self.slide_floor))
        # a textured material's rectangles stay within its texture's reach (its span)
        self.caps, self.reaches = {}, {}
        for m, tex in ctx.textures.items():
            self.reaches[m] = texel_reach(tex)
            self.caps[m] = math.floor(self.reaches[m] / s + 1e-9)
            if self.caps[m] < 1:
                raise WorldError(pointer('/terrain/materials', m) + '/texture/span',
                                 f'One quad of field {name!r} ({s} units) reaches more than the span of {m!r} '
                                 f'({tex.span} texels): give the texture a larger span or scale.')
        self.heights(ctx)
        self.materials = [[spec['material']] * self.nx for _ in range(self.nz)]
        self.painted = [[False] * self.nx for _ in range(self.nz)]
        self.O = [[0.0] * self.nx for _ in range(self.nz)]       # cliffs: each quad's offset (a sheet)
        self.cliff = [[None] * self.nx for _ in range(self.nz)]  # the cliff op that raised the quad
        self.waters = []                                         # water ops, applied when finished
        self.disp = {}
        self.split = {}                                          # cliff edges: (ix, jz) -> {offset: height}
        for k, op in enumerate(spec.get('operations', [])):
            self.apply(op, f'{self.path}/operations/{k}', ctx)

    def finish(self, ctx):
        """After the operations and any draped path's bed: heights rounded to 16.16, normals,
        steep quads' material, water and the cliffs' overhangs."""
        spec = self.spec
        self.H = [[q16(h) for h in row] for row in self.H]
        self.O = [[q16(o) for o in row] for row in self.O]
        self.split = {p: {q16(o): q16(h) for o, h in sp.items()} for p, sp in self.split.items()}
        self.normals()
        self.water = [[None] * self.nx for _ in range(self.nz)]  # (level, material) per quad
        for op, path in self.waters:
            area = Area(op.get('area'), ctx.paths, path + '/area')
            level = q16(op['level'])
            for jz in range(self.nz):
                for ix in range(self.nx):
                    if self.materials[jz][ix] is None:
                        continue
                    x, z = self.xz(ix, jz)
                    if area.distance(x + self.s / 2, z + self.s / 2) > 0:
                        continue
                    o = self.O[jz][ix]
                    if min(self.corners(ix, jz)) + o < level:
                        self.water[jz][ix] = (level, op['material'])
        self.displacements()
        if 'steep' in spec:
            lim = math.cos(math.radians(spec['steep']['degrees']))
            for jz in range(self.nz):
                for ix in range(self.nx):
                    m = self.materials[jz][ix]
                    if m is None or self.painted[jz][ix]:
                        continue
                    if min(n[1] / math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) for n in self.quad_normals(ix, jz)) < lim:
                        self.materials[jz][ix] = spec['steep']['material']

    # samples are H[jz][ix], jz along z from min, ix along x
    def heights(self, ctx):
        spec = self.spec
        if 'heights' in spec and 'height' in spec:
            raise WorldError(self.path + '/heights', 'Give height or a heights file, not both.')
        if 'heights' not in spec:
            self.H = [[float(spec.get('height', 0))] * (self.nx + 1) for _ in range(self.nz + 1)]
            return
        f = (ctx.base / spec['heights']).resolve()
        if not f.is_file():
            raise WorldError(self.path + '/heights', f'No heights file at {f}.')
        data = f.read_bytes()
        ctx.files.append((str(f), hashlib.sha256(data).hexdigest()))
        rows = []
        for n, line in enumerate(data.decode('utf-8').splitlines(), 1):
            line = line.split('#', 1)[0].split()
            if not line:
                continue
            try:
                row = [float(v) for v in line]
            except ValueError:
                raise WorldError(self.path + '/heights', f'{f}:{n}: heights are numbers separated by spaces.') from None
            if len(row) != self.nx + 1:
                raise WorldError(self.path + '/heights', f'{f}:{n}: {len(row)} heights; a row has {self.nx + 1} '
                                 f'(x from min to max every {self.s}).')
            if any(not math.isfinite(v) or abs(v) > 4000 for v in row):
                raise WorldError(self.path + '/heights', f'{f}:{n}: heights are finite and within +-4000.')
            rows.append(row)
        if len(rows) != self.nz + 1:
            raise WorldError(self.path + '/heights', f'{f}: {len(rows)} rows; the field has {self.nz + 1} '
                             f'(z from min to max every {self.s}).')
        self.H = rows

    def xz(self, ix, jz):
        return ((self.qx0 + ix) * self.s, (self.qz0 + jz) * self.s)

    def apply(self, op, path, ctx):
        kind = op['op']
        area = Area(op.get('area'), ctx.paths, path + '/area')
        falloff = op.get('falloff', 0.0)
        if kind in ('paint', 'hole', 'cliff', 'water') and 'falloff' in op:
            raise WorldError(path + '/falloff', f'{kind} acts on whole quads: it has no falloff.')
        if kind in ('paint', 'cliff', 'water') and 'material' in op and op['material'] not in ctx.materials:
            raise WorldError(path + '/material', f'No terrain material {op["material"]!r}.')
        if kind == 'paint' and ctx.materials[op['material']].get('water'):
            raise WorldError(path + '/material', 'A water material is laid with a water operation (or a sweep), '
                             'not painted.')
        if kind == 'water':
            if not ctx.materials[op['material']].get('water'):
                raise WorldError(path + '/material', f'{op["material"]!r} is not a water material: give it '
                                 '"water": true in terrain.materials.')
            self.waters.append((op, path))
            return
        if kind == 'cliff':
            # the quads whose centres lie in the area move up (or down) as a sheet; where a quad
            # meets one at another height, a wall joins them along their shared edge, and the
            # samples on that edge keep a height for each sheet
            wall = op.get('material', self.spec.get('steep', {}).get('material', self.spec['material']))
            if ctx.materials[wall].get('water'):
                raise WorldError(path + '/material', 'A cliff\'s face is not water.')
            if op.get('overhang', 0) and op.get('overhang', 0) > self.s / 2:
                raise WorldError(path + '/overhang', f'An overhang reaches at most half the spacing ({self.s / 2}).')
            s = self.s
            moved = {}
            for jz in range(self.nz):
                for ix in range(self.nx):
                    x, z = self.xz(ix, jz)
                    if area.distance(x + s / 2, z + s / 2) <= 0:
                        moved[(ix, jz)] = self.O[jz][ix]
            if not moved:
                return
            old = {}
            for (ix, jz), o in moved.items():
                for dx in (0, 1):
                    for dz in (0, 1):
                        old.setdefault((ix + dx, jz + dz), {})[(ix, jz)] = self.hq(ix + dx, jz + dz, o)
            for (ix, jz) in moved:
                self.O[jz][ix] += op['height']
                self.cliff[jz][ix] = (wall, op.get('overhang', 0.0), op.get('lip', 1.0))
            for p, heights in old.items():
                ix, jz = p
                sheets = {}
                for qx in (ix - 1, ix):
                    for qz in (jz - 1, jz):
                        if 0 <= qx < self.nx and 0 <= qz < self.nz:
                            o = self.O[qz][qx]
                            if (qx, qz) in heights:
                                sheets.setdefault(o, heights[(qx, qz)])
                            else:
                                sheets.setdefault(o, self.hq(ix, jz, o))
                if len(sheets) == 1:
                    self.H[jz][ix] = next(iter(sheets.values()))
                    self.split.pop(p, None)
                else:
                    self.split[p] = sheets
            return
        if kind in ('paint', 'hole'):
            s = self.s
            for jz in range(self.nz):
                for ix in range(self.nx):
                    x, z = self.xz(ix, jz)
                    if area.distance(x + s / 2, z + s / 2) <= 0:
                        if kind == 'hole':
                            self.materials[jz][ix] = None
                        elif self.materials[jz][ix] is not None:
                            self.materials[jz][ix] = op['material']
                            self.painted[jz][ix] = True
            return
        whole = area.kind is None
        if kind == 'smooth':
            for _ in range(op.get('passes', 1)):
                H = self.H
                nz, nx = self.nz, self.nx
                delta = {}
                for jz in range(nz + 1):
                    for ix in range(nx + 1):
                        acc = 0.0
                        for dz, wz in ((-1, 1), (0, 2), (1, 1)):
                            r = H[min(nz, max(0, jz + dz))]
                            acc += wz * (r[max(0, ix - 1)] + 2 * r[ix] + r[min(nx, ix + 1)])
                        delta[(ix, jz)] = acc / 16 - H[jz][ix]
                self.update(area.distance, lambda h, x, z, ix, jz: h + delta[(ix, jz)], falloff, whole)
            return
        if kind == 'ramp':
            a, b = op['from'], op['to']
            dx, dz = b[0] - a[0], b[2] - a[2]
            length = math.hypot(dx, dz)
            if length == 0:
                raise WorldError(path + '/to', 'A ramp\'s ends differ seen from above.')
            ux, uz = dx / length, dz / length
            half = op['width'] / 2

            def ramp_distance(x, z):
                t = (x - a[0]) * ux + (z - a[2]) * uz
                p = abs(-(x - a[0]) * uz + (z - a[2]) * ux)
                out = math.hypot(max(-t, t - length, 0.0), max(p - half, 0.0))
                return out if out > 0 else -min(half - p, t, length - t)

            def ramp_target(h, x, z, ix, jz):
                t = (x - a[0]) * ux + (z - a[2]) * uz
                return a[1] + (b[1] - a[1]) * max(0.0, min(1.0, t / length))
            self.update(ramp_distance, ramp_target, falloff, False)
            return
        if kind == 'bed':
            if op['path'] not in ctx.paths:
                raise WorldError(path + '/path', f'No path {op["path"]!r} in the world file\'s paths.')
            if 'area' in op:
                raise WorldError(path + '/area', 'A bed\'s area is its path and width.')
            if 'drape' in ctx.paths[op['path']]:
                raise WorldError(path + '/path', f'Path {op["path"]!r} is draped: it cuts its own bed (its '
                                 'drape.bed); remove this operation.')
            line = Polyline(ctx.paths[op['path']]['points'], ctx.paths[op['path']].get('closed', False))
            self.bed(line, op['width'] / 2, op.get('depth', 0.0), falloff)
            return
        if kind == 'terrace':
            step, bank, tb = op['step'], op.get('bank', 0.25), op.get('base', 0.0)

            def target(h, x, z, ix, jz):
                u = (h - tb) / step
                k = math.floor(u)
                return tb + (k + smoothstep((u - k - (1 - bank)) / bank)) * step
        elif kind == 'set':
            target = lambda h, x, z, ix, jz: op['height']           # noqa: E731
        elif kind == 'add':
            target = lambda h, x, z, ix, jz: h + op['height']       # noqa: E731
        elif kind == 'carve':
            target = lambda h, x, z, ix, jz: min(h, op['height'])   # noqa: E731
        else:                                                       # fill
            target = lambda h, x, z, ix, jz: max(h, op['height'])   # noqa: E731
        self.update(area.distance, target, falloff, whole)

    def update(self, distance, target, falloff, whole):
        """Every sample within falloff of an operation's area moves toward target(h, x, z, ix,
        jz) by the weight there. A sample on a cliff's edge has a height per sheet: a sheet's
        changes only where a quad of that sheet touching the sample is reached (its centre within
        the falloff), or everywhere for an operation on the whole field."""
        s = self.s
        for jz in range(self.nz + 1):
            row = self.H[jz]
            for ix in range(self.nx + 1):
                x, z = self.xz(ix, jz)
                d = distance(x, z)
                if d is None:
                    continue
                w = 1.0 if d <= 0 else (smoothstep(1 - d / falloff) if falloff > 0 and d < falloff else 0.0)
                if not w:
                    continue
                sp = self.split.get((ix, jz))
                if not sp:
                    # targets are world heights: a sample of a raised sheet is its height less
                    # the offset (every quad around it has the same one)
                    o = self.O[min(jz, self.nz - 1)][min(ix, self.nx - 1)]
                    row[ix] += w * (target(row[ix] + o, x, z, ix, jz) - o - row[ix])
                    continue
                row[ix] += w * (target(row[ix], x, z, ix, jz) - row[ix])
                for o in sp:
                    reached = whole
                    for qx in (ix - 1, ix):
                        for qz in (jz - 1, jz):
                            if reached or not (0 <= qx < self.nx and 0 <= qz < self.nz) or self.O[qz][qx] != o:
                                continue
                            dc = distance((self.qx0 + qx) * s + s / 2, (self.qz0 + qz) * s + s / 2)
                            reached = dc is not None and dc <= falloff
                    if reached:
                        sp[o] += w * (target(sp[o] + o, x, z, ix, jz) - o - sp[o])

    def hq(self, ix, jz, o):
        """Sample (ix, jz)'s height (less the offset) for the sheet at offset o."""
        sp = self.split.get((ix, jz))
        if sp and o in sp:
            return sp[o]
        return self.H[jz][ix]

    def bed(self, line, half, depth, falloff):
        """The ground within half of a path's line set to the line less depth, fading out over
        falloff; an open path's bed ends square at its ends."""
        lo_x, lo_z = self.qx0 * self.s, self.qz0 * self.s
        hi_x, hi_z = lo_x + self.nx * self.s, lo_z + self.nz * self.s
        xs = [p[0] for p in line.points]
        zs = [p[-1] for p in line.points]
        reach = half + falloff
        if max(xs) + reach < lo_x or min(xs) - reach > hi_x or max(zs) + reach < lo_z or min(zs) - reach > hi_z:
            return
        near = {}

        def distance(x, z):
            d, y = line.nearest(x, z)
            if d > reach or line.beyond(x, z, d):
                return None
            near[(x, z)] = y
            return d - half
        self.update(distance, lambda h, x, z, ix, jz: near[(x, z)] - depth, falloff, False)

    def ground_at(self, x, z):
        """The ground's height at (x, z) on the quad's two triangles (None: no quad there). Used
        before the heights are final, to drape a path."""
        s = self.s
        ix, jz = math.floor(x / s) - self.qx0, math.floor(z / s) - self.qz0
        ix, jz = min(ix, self.nx - 1), min(jz, self.nz - 1)
        if not (0 <= ix < self.nx and 0 <= jz < self.nz) or self.materials[jz][ix] is None:
            return None
        u, v = x / s - (self.qx0 + ix), z / s - (self.qz0 + jz)
        h00, h10, h01, h11 = self.corners(ix, jz)
        if abs(h00 - h11) <= abs(h10 - h01):         # along (0,0)-(1,1)
            y = h00 + (h10 - h00) * u + (h11 - h10) * v if u >= v else h00 + (h11 - h01) * u + (h01 - h00) * v
        else:                                        # along (1,0)-(0,1)
            y = h00 + (h10 - h00) * u + (h01 - h00) * v if u + v <= 1 else h11 + (h11 - h01) * (u - 1) + (h11 - h10) * (v - 1)
        return y + self.O[jz][ix]

    def displacements(self):
        """Where a cliff has an overhang, its top's edge points move out over the face: per
        (lattice point, sheet offset) the average of the outward normals times the overhang of
        the boundary edges there that the sheet is the top of."""
        acc = {}
        for jz in range(self.nz):
            for ix in range(self.nx):
                cl = self.cliff[jz][ix]
                if self.materials[jz][ix] is None or not cl or not cl[1]:
                    continue
                o = self.O[jz][ix]
                qx, qz = self.qx0 + ix, self.qz0 + jz
                for (dx, dz), ends in (((1, 0), ((1, 0), (1, 1))), ((-1, 0), ((0, 0), (0, 1))),
                                       ((0, 1), ((0, 1), (1, 1))), ((0, -1), ((0, 0), (1, 0)))):
                    n = (ix + dx, jz + dz)
                    if not (0 <= n[0] < self.nx and 0 <= n[1] < self.nz) or self.materials[n[1]][n[0]] is None:
                        continue
                    if self.O[n[1]][n[0]] >= o:
                        continue
                    for ex, ez in ends:
                        a = acc.setdefault(((qx + ex, qz + ez), o), [0.0, 0.0, 0])
                        a[0] += dx * cl[1]
                        a[1] += dz * cl[1]
                        a[2] += 1
        self.disp = {k: (q16(a[0] / a[2]), q16(a[1] / a[2])) for k, a in acc.items()}

    def offset(self, qx, qz):
        ix, jz = qx - self.qx0, qz - self.qz0
        return self.O[jz][ix]

    def walls(self):
        """The cliffs' faces: [(tile lattice point of the top quad, lower quad, upper quad, edge)]
        for every edge between two present quads at different offsets; edge is its two lattice
        points, in order."""
        out = []
        for jz in range(self.nz):
            for ix in range(self.nx):
                if self.materials[jz][ix] is None:
                    continue
                for dx, dz in ((1, 0), (0, 1)):
                    n = (ix + dx, jz + dz)
                    if n[0] >= self.nx or n[1] >= self.nz or self.materials[n[1]][n[0]] is None:
                        continue
                    a, b = self.O[jz][ix], self.O[n[1]][n[0]]
                    if a == b:
                        continue
                    qx, qz = self.qx0 + ix + dx, self.qz0 + jz + dz
                    edge = ((qx, qz), (qx, qz + 1)) if dx else ((qx, qz), (qx + 1, qz))
                    hi, lo = ((ix, jz), n) if a > b else (n, (ix, jz))
                    out.append((lo, hi, edge))
        return out

    def present(self, qx, qz):
        """The material of the quad at lattice (qx, qz), or None (outside the field or a hole)."""
        ix, jz = qx - self.qx0, qz - self.qz0
        if 0 <= ix < self.nx and 0 <= jz < self.nz:
            return self.materials[jz][ix]
        return None

    def h(self, qx, qz, o=None):
        """Lattice sample (qx, qz)'s height, less any offset: the sheet at offset o's on a cliff's
        edge."""
        ix, jz = qx - self.qx0, qz - self.qz0
        return self.H[jz][ix] if o is None else self.hq(ix, jz, o)

    def corners(self, ix, jz):
        """Quad (ix, jz)'s corner heights (less its offset): h00, h10, h01, h11."""
        o = self.O[jz][ix]
        return (self.hq(ix, jz, o), self.hq(ix + 1, jz, o), self.hq(ix, jz + 1, o), self.hq(ix + 1, jz + 1, o))

    def diagonal(self, ix, jz):
        """True: the quad splits along (0,0)-(1,1); False: along (1,0)-(0,1). The split whose two
        triangles are the same kind for the body (both floors or both walls, by the game's
        floor_max_degrees), so that a steep sliver never lies between two floors where they meet
        (a crack to a point query); then the one along the shorter rise."""
        key = self.__dict__.setdefault('_diag', {})
        if (ix, jz) not in key:
            h00, h10, h01, h11 = self.corners(ix, jz)
            rise = (abs(h00 - h11), abs(h10 - h01))
            mixed = []
            for d in (True, False):
                kinds = {n[1] / math.sqrt(dot(n, n)) >= self.floor_cos for n in self.split_normals(ix, jz, d)}
                mixed.append(len(kinds) > 1)
            key[(ix, jz)] = (mixed[0], rise[0]) <= (mixed[1], rise[1])
        return key[(ix, jz)]

    def split_normals(self, ix, jz, diag):
        """The quad's two triangles' upward normals (unnormalised, area weighted) for a split."""
        s = self.s
        h00, h10, h01, h11 = self.corners(ix, jz)
        c = {(0, 0): h00, (1, 0): h10, (0, 1): h01, (1, 1): h11}
        tris = (((0, 0), (1, 0), (1, 1)), ((0, 0), (1, 1), (0, 1))) if diag else \
            (((0, 0), (1, 0), (0, 1)), ((1, 0), (1, 1), (0, 1)))
        out = []
        for t in tris:
            p = [(u * s, c[(u, v)], v * s) for u, v in t]
            n = cross(sub(p[1], p[0]), sub(p[2], p[0]))
            out.append(n if n[1] > 0 else (-n[0], -n[1], -n[2]))
        return out

    def quad_normals(self, ix, jz):
        return self.split_normals(ix, jz, self.diagonal(ix, jz))

    def normals(self):
        """Per sample: the sum of the normals of the finest triangles around it (holes left out
        later: sampled from every quad of the field, so a seam's two sides agree)."""
        self.N = {}             # (ix, jz, sheet offset) -> summed normal
        for jz in range(self.nz):
            for ix in range(self.nx):
                if self.materials[jz][ix] is None:
                    continue
                n1, n2 = self.quad_normals(ix, jz)
                s = (n1[0] + n2[0], n1[1] + n2[1], n1[2] + n2[2])
                for dz in (0, 1):
                    for dx in (0, 1):
                        k = (ix + dx, jz + dz, self.O[jz][ix])
                        o = self.N.get(k, (0.0, 0.0, 0.0))
                        self.N[k] = (o[0] + s[0], o[1] + s[1], o[2] + s[2])

    def normal(self, qx, qz, o=0.0):
        n = self.N.get((qx - self.qx0, qz - self.qz0, o), (0.0, 0.0, 0.0))
        ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
        return (0.0, 1.0, 0.0) if ln == 0 else (n[0] / ln, n[1] / ln, n[2] / ln)

    # ---- merging quads

    def flat(self, x0, z0, w, d, tol):
        """Whether every sample of the w x d block at lattice (x0, z0) lies within tol of the
        bilinear patch of its corners, with the patch's twist (how far its two triangles can
        part from it) added. (The block is one sheet: its first quad's.)"""
        o = self.O[z0 - self.qz0][x0 - self.qx0]
        hh = lambda qx, qz: self.h(qx, qz, o)   # noqa: E731
        c00, c10 = hh(x0, z0), hh(x0 + w, z0)
        c01, c11 = hh(x0, z0 + d), hh(x0 + w, z0 + d)
        twist = abs(c00 + c11 - c10 - c01) / 4
        if twist > tol:
            return False
        for dz in range(d + 1):
            v = dz / d
            a, b = c00 + (c01 - c00) * v, c10 + (c11 - c10) * v
            for dx in range(w + 1):
                if abs(hh(x0 + dx, z0 + dz) - (a + (b - a) * dx / w)) + twist > tol:
                    return False
        return True

    def key(self, qx, qz, water=False):
        """What a quad merges by: (material, sheet offset) for the ground, (material, level)
        for water; None: nothing there. A ground quad with a corner an overhang moves merges
        with nothing (its edges are not straight lattice lines)."""
        ix, jz = qx - self.qx0, qz - self.qz0
        if not (0 <= ix < self.nx and 0 <= jz < self.nz):
            return None
        if water:
            wt = self.water[jz][ix]
            return None if wt is None else (wt[1], wt[0])
        m = self.materials[jz][ix]
        if m is None:
            return None
        o = self.O[jz][ix]
        if self.disp and any(((qx + dx, qz + dz), o) in self.disp for dx in (0, 1) for dz in (0, 1)):
            return (m, o, qx, qz)
        return (m, o)

    def reach(self, material, x0, z0, w, d, water):
        """Whether a w x d block of a textured material stays within its texture's reach: its
        quads gentle enough to be projected from above (their width is capped by the caller), or
        else rising no more than the reach (a steep face is projected from the side).
        Untextured materials and water: always."""
        if water or material not in self.caps:
            return True
        o = self.O[z0 - self.qz0][x0 - self.qx0]
        hs = {(dx, dz): self.h(x0 + dx, z0 + dz, o) for dx in range(w + 1) for dz in range(d + 1)}
        steep = GENTLE * self.s
        if all(abs(hs[(dx + 1, dz)] - hs[(dx, dz)]) < steep for dx in range(w) for dz in range(d + 1)) and \
           all(abs(hs[(dx, dz + 1)] - hs[(dx, dz)]) < steep for dx in range(w + 1) for dz in range(d)):
            return True
        return max(hs.values()) - min(hs.values()) <= self.reaches[material]

    def rects(self, tx0, tz0, tol, water=False, textured=True):
        """The tile at lattice (tx0, tz0) as rectangles of quads [(qx, qz, w, d, material,
        offset)]: greedily, row by row, each grown along x and then along z while its quads share
        a material and sheet and stay flat (within tol of one plane-like patch), and, textured,
        within a textured material's reach. Water: its flat surfaces, by material and level."""
        n = self.tq
        taken = set()
        out = []
        flat = (lambda *a: True) if water else self.flat
        for qz in range(tz0, tz0 + n):
            for qx in range(tx0, tx0 + n):
                if (qx, qz) in taken:
                    continue
                m = self.key(qx, qz, water)
                if m is None:
                    continue
                cap = self.caps.get(m[0], n) if textured else n
                reach = self.reach if textured else (lambda *a: True)
                w = 1
                while (qx + w < tx0 + n and w < cap and (qx + w, qz) not in taken and self.key(qx + w, qz, water) == m
                       and flat(qx, qz, w + 1, 1, tol) and reach(m[0], qx, qz, w + 1, 1, water)):
                    w += 1
                d = 1
                while (qz + d < tz0 + n and d < cap and all((x, qz + d) not in taken and self.key(x, qz + d, water) == m
                                                            for x in range(qx, qx + w))
                       and flat(qx, qz, w, d + 1, tol) and reach(m[0], qx, qz, w, d + 1, water)):
                    d += 1
                for z in range(qz, qz + d):
                    for x in range(qx, qx + w):
                        taken.add((x, z))
                out.append((qx, qz, w, d, m[0], m[1]))
        return out


class Sheet:
    """The ground at one sheet offset (cliffs), or a water level, as rect_triangles reads it."""

    def __init__(self, fld, offset, water=False):
        self.f, self.o, self.water = fld, offset, water
        self.s, self.qx0, self.qz0 = fld.s, fld.qx0, fld.qz0

    def h(self, qx, qz):
        return self.o if self.water else self.f.h(qx, qz, self.o) + self.o

    def normal(self, qx, qz):
        return (0.0, 1.0, 0.0) if self.water else self.f.normal(qx, qz, self.o)

    def diagonal(self, ix, jz):
        return True if self.water else self.f.diagonal(ix, jz)

    def pos(self, q):
        d = (0.0, 0.0) if self.water else self.f.disp.get((q, self.o), (0.0, 0.0))
        return (q16(q[0] * self.s + d[0]), q16(q[1] * self.s + d[1]))


def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def perimeter(x0, z0, w, d):
    """Lattice points around a w x d block, in order."""
    pts = [(x0 + k, z0) for k in range(w)]
    pts += [(x0 + w, z0 + k) for k in range(d)]
    pts += [(x0 + w - k, z0 + d) for k in range(w)]
    pts += [(x0, z0 + d - k) for k in range(d)]
    return pts


def rect_triangles(fld, rect, points):
    """A rectangle's triangles, each wound to face up (outward right-handed), as corners
    (world point, unit normal at it). With only its own four corners on its edges it is two
    triangles; with more (a neighbour's corners on its edges) it is a fan from its centre, so no
    corner of one face lies in the middle of another's edge."""
    x0, z0, w, d = rect[:4]
    s = fld.s

    def corner(q):
        x, z = fld.pos(q)
        return ((x, fld.h(*q), z), fld.normal(*q))

    ring = [p for p in perimeter(x0, z0, w, d) if p in points]
    inner_x = [p for p in ring if p[1] in (z0, z0 + d) and x0 < p[0] < x0 + w]     # on the x sides
    inner_z = [p for p in ring if p[0] in (x0, x0 + w) and z0 < p[1] < z0 + d]     # on the z sides
    if len(ring) > 4 and (not inner_x or not inner_z):
        # extra points on two opposite sides only: zip the two sides together (no centre, no
        # slivers from it); every triangle has two corners on one side and one on the other
        k = 0 if not inner_z else 1             # zip along x (the z = z0 and z0 + d sides) or along z
        lo = sorted((p for p in ring if p[1 - k] == (z0, x0)[k]), key=lambda p: p[k])
        hi = sorted((p for p in ring if p[1 - k] == (z0 + d, x0 + w)[k]), key=lambda p: p[k])
        tris = []
        i = j = 0
        while i < len(lo) - 1 or j < len(hi) - 1:
            # advance the side whose next step's middle is behind the other's, so each point
            # joins the nearer end of the opposite step (no long fan from one corner)
            if j == len(hi) - 1 or (i < len(lo) - 1 and lo[i][k] + lo[i + 1][k] <= hi[j][k] + hi[j + 1][k]):
                tris.append((lo[i], lo[i + 1], hi[j]))
                i += 1
            else:
                tris.append((lo[i], hi[j + 1], hi[j]))
                j += 1
        tris = [tuple(corner(q) for q in t) for t in tris]
    elif len(ring) == 4:
        c00, c10, c11, c01 = (x0, z0), (x0 + w, z0), (x0 + w, z0 + d), (x0, z0 + d)
        if w == d == 1:
            diag = fld.diagonal(x0 - fld.qx0, z0 - fld.qz0)
        else:
            diag = abs(fld.h(*c00) - fld.h(*c11)) <= abs(fld.h(*c10) - fld.h(*c01))
        tris = [(c00, c10, c11), (c00, c11, c01)] if diag else [(c00, c10, c01), (c10, c11, c01)]
        tris = [tuple(corner(q) for q in t) for t in tris]
    else:
        if w % 2 == 0 and d % 2 == 0:
            centre = corner((x0 + w // 2, z0 + d // 2))
        else:
            # between samples: on the patch of the corners (the rectangle is flat within tol)
            hs = [fld.h(x0, z0), fld.h(x0 + w, z0), fld.h(x0, z0 + d), fld.h(x0 + w, z0 + d)]
            a = (x0 * s, hs[0], z0 * s)
            n = unit(cross(sub((x0 * s, hs[3], (z0 + d) * s), a), sub(((x0 + w) * s, hs[1], z0 * s), a)))
            centre = ((q16((x0 + w / 2) * s), q16(sum(hs) / 4), q16((z0 + d / 2) * s)), n if n[1] > 0 else (-n[0], -n[1], -n[2]))
        tris = [(centre, corner(ring[k]), corner(ring[(k + 1) % len(ring)])) for k in range(len(ring))]
    out = []
    for t in tris:
        p = [c[0] for c in t]
        if cross(sub(p[1], p[0]), sub(p[2], p[0]))[1] < 0:
            t = (t[0], t[2], t[1])
        out.append(t)
    return out


# ---- native meshes

class MeshOut:
    """A cell-local native mesh being written: vertices deduplicated, palette swatch faces, and
    textured faces with their texel coordinates. Without textured faces it packs as is (pack());
    with them it is written per region, for the region's texture packing (native())."""

    def __init__(self, palette, centre, textures=None, materials=None, where='/terrain'):
        self.mesh = meshlib.Mesh()
        self.index = {}
        self.palette, self.centre = palette, centre
        self.faces = 0
        self.materials = set()
        self.textures, self.mats, self.where = textures or {}, materials or {}, where
        self.recs = []          # per face: (indices, colours, material, flags, texel coordinates or None,
                                #            windowed)
        self.textured = False
        self.windowed = set()   # textured materials with faces drawn through a texture window
        self.squeezed = {}      # textured material -> faces whose texture is stretched to fit

    def vertex(self, p):
        key = (p[0] - self.centre[0], p[1], p[2] - self.centre[2])
        if key not in self.index:
            self.index[key] = self.mesh.vertex(*key)
        return self.index[key]

    def tri(self, pts, shades, material, flags=0):
        """pts: world corners, wound outward right-handed; shades: 0-1 per corner. flags: the
        mesh face's (meshlib.SEMI for water: half blend, meshlib.DOUBLE)."""
        tex = self.textures.get(material)
        if tex is None:
            entry = self.palette['by_material'][material]
            emissive = entry['class'] == 'emissive'
        else:
            emissive = self.mats[material].get('class') == 'emissive'
        if emissive:
            shades = (1, 1, 1)
        idx = [self.vertex(p) for p in pts]
        cols = [meshlib.rgb(*([max(0, min(255, round(128 * sh)))] * 3)) for sh in shades]
        # Mei's front faces are the reverse of the outward right-handed winding (assetkit.compiler).
        if tex is not None:
            uv, windowed, squeezed = texel_coords(tex, pts)
            if squeezed:
                self.squeezed[material] = self.squeezed.get(material, 0) + 1
            if windowed:
                self.windowed.add(material)
            self.recs.append((list(reversed(idx)), list(reversed(cols)), material, flags, list(reversed(uv)), windowed))
            self.textured = True
        else:
            uv = (entry['index'], self.palette['layout']['row'])
            self.mesh.tri(list(reversed(idx)), list(reversed(cols)), [uv] * 3, flags,
                          slot=self.palette['layout']['slot'], four_bit=True, palette=entry['palette'])
            self.recs.append((list(reversed(idx)), list(reversed(cols)), material, flags, None, False))
        self.faces += 1
        self.materials.add(material)

    def pack(self):
        """The mesh with provisional palette colours, or, with textured faces, this MeshOut,
        for world.py to write per region (native())."""
        if len(self.mesh.verts) > 2048:
            raise WorldError('/terrain', 'A terrain piece has more than 2,048 vertices.')
        return self if self.textured else self.mesh.pack()

    def native(self, colours, slot, row, packing):
        """The mesh for a region: palette faces at the region's colours (provisional colour ->
        region colour) and the world's swatch, as relocate() writes them; textured faces at
        their stored repeats' place in packing (drawn once: no texture window), or, reaching
        further, in their tile's texture window (at most 7 a mesh)."""
        out = meshlib.Mesh()
        out.verts = list(self.mesh.verts)
        for idx, cols, material, flags, uv, windowed in self.recs:
            if uv is None:
                colour = self.palette['by_material'][material]['colour']
                colour = colours.get(colour, colour)
                out.tri(idx, cols, [(colour % 16, row)] * 3, flags, slot=slot, four_bit=True, palette=colour // 16)
                continue
            tex = self.textures[material]
            if windowed:
                place = packing.placements[tex.window_tile.key]
                if place.halfword() not in out.windows and len(out.windows) == 7:
                    raise WorldError(self.where, 'A terrain piece draws more than 7 textured materials through '
                                     'texture windows (a mesh has at most 7). Give some a larger span.')
                window = out.window(u=(place.width, place.x), v=(place.height, place.y))
                out.tri(idx, cols, uv, flags, slot=place.slot, four_bit=place.bits == 4, palette=place.palette,
                        window=window)
                continue
            place = packing.placements[tex.tile.key]
            out.tri(idx, cols, [(u + place.x, v + place.y) for u, v in uv], flags, slot=place.slot,
                    four_bit=place.bits == 4, palette=place.palette)
        return out.pack()


def unit(n):
    ln = math.sqrt(dot(n, n))
    return (0.0, 1.0, 0.0) if ln == 0 else (n[0] / ln, n[1] / ln, n[2] / ln)


# ---- sweeps

def right_of(t):
    """The horizontal unit vector to the right of horizontal direction t (x, z) seen from above
    with +x right and +z forward."""
    return (t[1], -t[0])


class Sweep:
    def __init__(self, name, spec, ctx):
        self.name = name
        self.path = pointer('/paths', name) + '/sweep'
        sw = spec['sweep']
        prof = [tuple(p) for p in sw['profile']]
        for k in range(1, len(prof)):
            if prof[k] == prof[k - 1]:
                raise WorldError(f'{self.path}/profile/{k}', 'A profile point repeats the one before it.')
        self.profile = prof
        if ('material' in sw) == ('materials' in sw):
            raise WorldError(self.path + '/material', 'Give material, or materials (one per profile edge).')
        mats = [sw['material']] * (len(prof) - 1) if 'material' in sw else sw['materials']
        if len(mats) != len(prof) - 1:
            raise WorldError(self.path + '/materials', f'The profile has {len(prof) - 1} edges; give one material each.')
        for k, m in enumerate(mats):
            if m not in ctx.materials:
                raise WorldError(self.path + ('/material' if 'material' in sw else f'/materials/{k}'),
                                 f'No terrain material {m!r}.')
        self.materials = mats
        self.points = [tuple(float(c) for c in p) for p in spec['points']]
        self.closed = bool(spec.get('closed'))
        self.raised = bool(spec.get('raised'))
        self.water = any(ctx.materials[m].get('water') for m in mats)
        self.ground = sw.get('ground', not self.raised and not self.water)
        self.double_sided = sw.get('double_sided', False)
        self.collision = sw.get('collision', True)
        self.caps = sw.get('caps', False)
        if self.caps and self.closed:
            raise WorldError(self.path + '/caps', 'A closed path has no ends to cap.')
        self.rise = sw['stairs']['rise'] if 'stairs' in sw else None
        # a textured edge's strips stay within its texture's reach: cross-sections at most
        # max_len apart along the path (less the edge's own length)
        self.max_len = None
        for k, m in enumerate(mats):
            if m in ctx.textures:
                (x0, y0), (x1, y1) = prof[k], prof[k + 1]
                # strips within the stored repeats (cutting a strip is cheaper than a window
                # table), unless the edge alone nearly fills them
                edge = math.hypot(x1 - x0, y1 - y0)
                room = texel_reach(ctx.textures[m], stored=True) - edge
                if room < edge:
                    room = texel_reach(ctx.textures[m]) - edge
                if room <= 0:
                    raise WorldError(self.path + '/profile', f'Edge {k} of the profile is more than 255 texels of '
                                     f'{m!r} long: give the texture a larger scale, or split the edge.')
                self.max_len = room if self.max_len is None else min(self.max_len, room)
        pts = self.points + ([self.points[0]] if self.closed else [])
        self.segs = []
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            dx, dz = b[0] - a[0], b[2] - a[2]
            ln = math.hypot(dx, dz)
            if ln == 0:
                raise WorldError(f'{pointer("/paths", name)}/points/{(k + 1) % len(self.points)}',
                                 'A swept path\'s points differ seen from above: a sweep cannot go straight up.')
            self.segs.append((a, b, (dx / ln, dz / ln), ln))
        # The frame at each path point: the mitre of the segments meeting there.
        n = len(self.segs)
        self.frames = []
        for k in range(len(pts)):
            t_in = self.segs[k - 1][2] if (k > 0 or self.closed) else None
            t_out = self.segs[k][2] if k < n else (self.segs[0][2] if self.closed else None)
            if k == n and self.closed:
                self.frames.append(self.frames[0])
                continue
            if t_in is None or t_out is None:
                t = t_in or t_out
                self.frames.append((right_of(t), 1.0))
                continue
            m = (t_in[0] + t_out[0], t_in[1] + t_out[1])
            ml = math.hypot(*m)
            cos = (m[0] * t_out[0] + m[1] * t_out[1]) / ml if ml else 0.0
            if cos < MIN_MITRE_COS:
                raise WorldError(f'{pointer("/paths", name)}/points/{k % len(self.points)}',
                                 'A swept path turns more than 120 degrees here; add a point to round the corner.')
            r = right_of((m[0] / ml, m[1] / ml))
            self.frames.append((r, 1.0 / cos))

    def stations(self, size):
        """Per segment: [(t, y, frame)] along it, t in 0..1, with a riser where two stations
        share a t (a step). Cross-sections where the centre line crosses a cell edge."""
        out = []
        for k, (a, b, tdir, ln) in enumerate(self.segs):
            ts = {0.0, 1.0}
            for axis in (0, 2):
                lo, hi = sorted((a[axis], b[axis]))
                m = math.floor(lo / size) + 1
                while m * size < hi:
                    if b[axis] != a[axis]:
                        ts.add((m * size - a[axis]) / (b[axis] - a[axis]))
                    m += 1
            rise = self.rise
            dy = b[1] - a[1]
            runs = None
            if rise is not None and dy != 0:
                runs = math.ceil(abs(dy) / rise - 1e-9) + 1
                for r in range(1, runs):
                    ts.add(r / runs)
            if self.max_len is not None:
                # textured: no strip longer than max_len; a longer gap between the cross-sections
                # already there is split evenly
                cuts = sorted(ts)
                for t0, t1 in zip(cuts, cuts[1:]):
                    pieces = math.ceil((t1 - t0) * ln / self.max_len - 1e-9)
                    for r in range(1, pieces):
                        ts.add(t0 + (t1 - t0) * r / pieces)
            seg = []
            mid = (right_of(tdir), 1.0)
            for t in sorted(ts):
                frame = self.frames[k] if t == 0 else self.frames[k + 1] if t == 1 else mid
                if runs is None:
                    seg.append((t, a[1] + dy * t, frame))
                    continue
                # run r covers t in [r / runs, (r + 1) / runs] at the r-th of runs equal heights
                # from a to b; between two runs a riser joins them
                r = t * runs
                rr = round(r)
                if 0 < rr < runs and abs(r - rr) < 1e-9:
                    seg.append((t, a[1] + dy * (rr - 1) / (runs - 1), frame))
                    seg.append((t, a[1] + dy * rr / (runs - 1), frame))
                else:
                    seg.append((t, a[1] + dy * min(runs - 1, math.floor(r + 1e-9)) / (runs - 1), frame))
            out.append(seg)
        return out


def sweep_section(sw, a, b, t, y, frame):
    """The cross-section's world points at t along segment a-b at height y."""
    x = a[0] + (b[0] - a[0]) * t
    z = a[2] + (b[2] - a[2]) * t
    (rx, rz), scale = frame
    return [(q16(x + px * rx * scale), q16(y + py), q16(z + px * rz * scale)) for px, py in sw.profile]


# ---- cliffs

def wall_spec(f, lo, hi):
    """(material, overhang, lip) of the wall between quads lo and hi (ix, jz): the cliff that
    raised the top one, else the one that lowered the bottom one, else the field's steep or
    own material."""
    cl = f.cliff[hi[1]][hi[0]] or f.cliff[lo[1]][lo[0]]
    if cl:
        return cl
    return (f.spec.get('steep', {}).get('material', f.spec['material']), 0.0, 1.0)


def cliff_faces(f, walls):
    """[(world triangle wound outward right-handed, material)] of walls [(lo, hi, edge)]: per
    edge a vertical quad from the bottom sheet's points to the top's; with an overhang, the
    face rises upright to lip below the top, then leans out to the top's points, which the
    overhang has moved out over it."""
    out = []
    for lo, hi, edge in walls:
        material, ov, lip = wall_spec(f, lo, hi)
        o_lo, o_hi = f.O[lo[1]][lo[0]], f.O[hi[1]][hi[0]]
        bottom, top = Sheet(f, o_lo), Sheet(f, o_hi)
        B = [(*bottom.pos(q), bottom.h(*q)) for q in edge]
        T = [(*top.pos(q), top.h(*q)) for q in edge]
        B = [(x, y, z) for x, z, y in B]
        T = [(x, y, z) for x, z, y in T]
        hint = (lo[0] - hi[0], 0.0, lo[1] - hi[1])
        if T[0][1] + T[1][1] < B[0][1] + B[1][1]:
            # the sheet at the higher offset ends lower here (operations after the cliffs set the
            # two sheets' heights the other way round): the face looks out over the lower one
            hint = (-hint[0], 0.0, -hint[2])
        bands = [(B, T)]
        if ov and T[0][1] - lip > B[0][1] and T[1][1] - lip > B[1][1]:
            M = [(b[0], q16(t[1] - lip), b[2]) for b, t in zip(B, T)]
            bands = [(B, M), (M, T)]
        for low, high in bands:
            for tri in ((low[0], low[1], high[1]), (low[0], high[1], high[0])):
                n = cross(sub(tri[1], tri[0]), sub(tri[2], tri[0]))
                if dot(n, n) == 0:
                    continue
                if dot(n, hint) < 0:
                    tri = (tri[0], tri[2], tri[1])
                out.append((tri, material))
    return out


# ---- draped paths

def drape_path(name, spec, fields):
    """A draped path's points: its line, resampled every drape.step units, at the height of the
    ground under it (the highest field there), smoothed, lifted; 16.16."""
    path = pointer('/paths', name)
    d = spec['drape']
    step = d.get('step', min((f.s for f in fields), default=2))
    pts = [(p[0], p[-1]) for p in spec['points']]
    closed = bool(spec.get('closed'))
    ring = pts + ([pts[0]] if closed else [])
    xz = []
    for k in range(len(ring) - 1):
        (ax, az), (bx, bz) = ring[k], ring[k + 1]
        n = max(1, math.ceil(math.hypot(bx - ax, bz - az) / step - 1e-9))
        xz += [(ax + (bx - ax) * i / n, az + (bz - az) * i / n) for i in range(n)]
    if not closed:
        xz.append(ring[-1])
    if len(xz) > 4095:
        raise WorldError(path + '/drape/step', f'Draping makes {len(xz)} points; a path holds 4,095. Lengthen the step.')
    ys = []
    for k, (x, z) in enumerate(xz):
        hs = [h for h in (f.ground_at(x, z) for f in fields) if h is not None]
        if not hs:
            raise WorldError(path + '/points', f'The draped path passes over no field at ({x:g}, {z:g}).')
        ys.append(max(hs))
    for _ in range(d.get('smooth', 2)):
        n = len(ys)
        if closed:
            ys = [(ys[k - 1] + 2 * ys[k] + ys[(k + 1) % n]) / 4 for k in range(n)]
        else:
            ys = [ys[0]] + [(ys[k - 1] + 2 * ys[k] + ys[k + 1]) / 4 for k in range(1, n - 1)] + [ys[-1]]
    if d.get('downhill'):
        # water: never higher than any point before it (the bed cuts through a rise)
        for k in range(1, len(ys)):
            ys[k] = min(ys[k], ys[k - 1])
    lift = d.get('lift', 0.0)
    return [(q16(x), q16(y + lift), q16(z)) for (x, z), y in zip(xz, ys)]


# ---- the whole terrain

@dataclass
class Context:
    base: object
    size: int
    paths: dict
    materials: dict
    files: list
    floor_cos: float = math.cos(math.radians(45))
    textures: dict = field(default_factory=dict)    # material -> assetkit Texture


def compile_terrain(w, base, size, cells, surface_of, warnings, overhang, floor_max_degrees=45.0):
    """cells: (i, j) -> anything (the cells that exist). Returns a Result; pieces carry meshes
    with provisional palette colours (assign_palette's layout), which world.py moves into each
    region's palettes as it moves an asset's."""
    from . import pack as P
    terrain = w.get('terrain')
    sweeps_spec = {n: p for n, p in w.get('paths', {}).items() if 'sweep' in p}
    if terrain is None and not sweeps_spec:
        return None
    if terrain is None:
        raise WorldError('/paths', 'A path with a sweep needs terrain materials: declare them in terrain.materials.')
    materials = terrain['materials']
    if not materials:
        raise WorldError('/terrain/materials', 'Declare at least one terrain material.')
    ctx = Context(base, size, w.get("paths", {}), materials, [], math.cos(math.radians(floor_max_degrees)))
    ctx.textures = load_textures(materials, base, ctx.files)
    textures = ctx.textures
    lighting = dict({'mode': 'vertical'}, **terrain.get('lighting', {}))
    if lighting['mode'] == 'vertical' and 'direction' in lighting:
        raise WorldError('/terrain/lighting/direction', 'Vertical lighting shades by the normal\'s Y only. Remove '
                         'direction, or use mode "directional".')
    if lighting['mode'] == 'directional' and dot(lighting.get('direction', [-0.4, 0.85, -0.35]),
                                                 lighting.get('direction', [-0.4, 0.85, -0.35])) == 0:
        raise WorldError('/terrain/lighting/direction', 'The light\'s direction is not zero.')
    shade_of = shading(lighting)
    floor_cos = ctx.floor_cos
    half = size / 2

    fields = []
    for name, spec in terrain.get('fields', {}).items():
        fields.append(Field(name, spec, ctx))
    for a in range(len(fields)):
        for b in range(a + 1, len(fields)):
            fa, fb = fields[a], fields[b]
            ax0, az0, ax1, az1 = fa.qx0 * fa.s, fa.qz0 * fa.s, (fa.qx0 + fa.nx) * fa.s, (fa.qz0 + fa.nz) * fa.s
            bx0, bz0, bx1, bz1 = fb.qx0 * fb.s, fb.qz0 * fb.s, (fb.qx0 + fb.nx) * fb.s, (fb.qz0 + fb.nz) * fb.s
            if ax0 <= bx1 and bx0 <= ax1 and az0 <= bz1 and bz0 <= az1:
                raise WorldError(fb.path, f'Fields {fa.name!r} and {fb.name!r} overlap or touch; fields keep apart '
                                 '(make one field, or leave a gap).')
    # draped paths: their line from the ground as the operations left it, then their own beds
    resolved = {}
    for pname, spec in w.get('paths', {}).items():
        if 'drape' in spec:
            resolved[pname] = drape_path(pname, spec, fields)
            bed = spec['drape'].get('bed')
            if bed:
                line = Polyline(resolved[pname], bool(spec.get('closed')))
                for f in fields:
                    f.bed(line, bed['width'] / 2, bed.get('depth', 0.0), bed.get('falloff', 0.0))
    for f in fields:
        f.finish(ctx)
    sweeps = [Sweep(n, dict(p, points=resolved.get(n, p['points'])), ctx) for n, p in sweeps_spec.items()]

    used = set()
    for f in fields:
        for row in f.materials:
            used.update(m for m in row if m is not None)
        for row in f.water:
            used.update(wt[1] for wt in row if wt is not None)
        for lo, hi, _ in f.walls():
            used.add(wall_spec(f, lo, hi)[0])
    for sw in sweeps:
        used.update(sw.materials)
    for name in materials:
        if name not in used:
            warnings.append({'code': 'terrain_material_unused', 'material': name,
                             'message': 'No field or sweep draws this terrain material.'})
    mats = {m: dict(materials[m], palette=True) for m in used if m not in textures}
    # A textured material's far colour, its texture's mean (a last mip level), for fields' coarse
    # levels: an entry of its own, drawn untextured from the lod distance.
    coarse = {m for f in fields if f.spec.get('lod') for row in f.materials for m in row if m in textures}
    coarse |= {wall_spec(f, lo, hi)[0] for f in fields if f.spec.get('lod') for lo, hi, _ in f.walls()} & set(textures)
    far = {}
    for m in sorted(coarse):
        far[m] = mean_colour(textures[m])
        mats[m] = {k: v for k, v in materials[m].items() if k != 'texture'} | {'palette': True, 'color': far[m]}
    faces = [type('F', (), {'material': m})() for m in sorted(mats)]
    palette = assign_palette(type('M', (), {'faces': faces})(), mats, {}) if used else None

    pieces, collision = {}, {}
    report = {'fields': {}, 'sweeps': {}, 'lighting': lighting['mode']}

    def centre_of(key):
        return (key[0] * size + half, 0.0, key[1] * size + half)

    # ---- fields: tiles, their rectangles at each level, the points every tile edge keeps
    water_tris = []             # (a, b, c, surface): the water surfaces' faces, for wp_water()
    for f in fields:
        spec = f.spec
        lod = spec.get('lod')
        tols = [spec.get('tolerance', DEFAULT_TOLERANCE)]
        if lod:
            tols.append(lod.get('tolerance', DEFAULT_LOD_TOLERANCE))
            if tols[1] <= tols[0]:
                raise WorldError(f.path + '/lod/tolerance', 'The coarse level\'s tolerance is larger than the field\'s.')
        tq = f.tq
        tiles, wtiles = {}, {}
        outside = 0
        for tz in range(math.floor(f.qz0 / tq), math.floor((f.qz0 + f.nz - 1) / tq) + 1):
            for tx in range(math.floor(f.qx0 / tq), math.floor((f.qx0 + f.nx - 1) / tq) + 1):
                cell = (math.floor(tx * tq * f.s / size), math.floor(tz * tq * f.s / size))
                if cell not in cells:
                    if any(f.present(qx, qz) for qz in range(tz * tq, tz * tq + tq) for qx in range(tx * tq, tx * tq + tq)):
                        outside += 1
                    continue
                # the coarse level is drawn in the textured materials' far colours: merged freely
                levels = [f.rects(tx * tq, tz * tq, t, textured=li == 0) for li, t in enumerate(tols)]
                if levels[0]:
                    tiles[(tx, tz)] = levels
                wl = f.rects(tx * tq, tz * tq, 0, water=True)
                if wl:
                    wtiles[(tx, tz)] = wl
        if outside:
            warnings.append({'code': 'terrain_outside_cells', 'field': f.name, 'tiles': outside,
                             'message': 'Parts of the field lie over no cell of the world; they are left out.'})

        def rect_corners(r):
            x0, z0, w, d = r[:4]
            return ((x0, z0), (x0 + w, z0), (x0, z0 + d), (x0 + w, z0 + d))

        def tile_of(q):
            return (math.floor(q[0] / tq), math.floor(q[1] / tq))

        # cliffs: each wall goes with its top quad's tile; its edge's points are kept by every
        # tile whose closure holds them, as the corners of rectangles are
        walls = f.walls()
        wall_points = set()
        for lo, hi, edge in walls:
            wall_points.update(edge)

        def gather(tilemap, extra=()):
            out = {}
            for key, levels in tilemap.items():
                pts = set()
                for lv in (levels if isinstance(levels[0], list) else [levels]):
                    for r in lv:
                        pts.update(rect_corners(r))
                out[key] = pts
            for p in extra:
                for tx in (math.floor(p[0] / tq) - (p[0] % tq == 0), math.floor(p[0] / tq)):
                    for tz in (math.floor(p[1] / tq) - (p[1] % tq == 0), math.floor(p[1] / tq)):
                        if (tx, tz) in out:
                            out[(tx, tz)].add(p)
            return out

        corners = gather(tiles, wall_points)
        wcorners = gather(wtiles)

        def edge_points(own, others, tx, tz):
            """The points every tile edge keeps: the tile's own on its border, and its four
            neighbours' on the shared edges."""
            x0, z0 = tx * tq, tz * tq
            pts = {p for p in own if p[0] in (x0, x0 + tq) or p[1] in (z0, z0 + tq)}
            for (dx, dz) in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                for p in others.get((tx + dx, tz + dz), ()):
                    if (dx == -1 and p[0] == x0) or (dx == 1 and p[0] == x0 + tq) or \
                            (dz == -1 and p[1] == z0) or (dz == 1 and p[1] == z0 + tq):
                        if x0 <= p[0] <= x0 + tq and z0 <= p[1] <= z0 + tq:
                            pts.add(p)
            return pts

        frep = {'spacing': f.s, 'samples': (f.nx + 1) * (f.nz + 1), 'quads': f.nx * f.nz,
                'holes': sum(m is None for row in f.materials for m in row),
                'heights': [min(min(f.corners(ix, jz)) + f.O[jz][ix] for jz in range(f.nz) for ix in range(f.nx)),
                            max(max(f.corners(ix, jz)) + f.O[jz][ix] for jz in range(f.nz) for ix in range(f.nx))],
                'tile': tq * f.s, 'tiles': len(tiles), 'triangles': [0] * len(tols), 'vertices': 0,
                'materials': {}, 'cells': {}}
        if walls:
            frep['cliff_triangles'] = 0
        if wtiles:
            frep['water_triangles'] = 0
        tile_walls = {}
        for lo, hi, edge in walls:
            tile_walls.setdefault(tile_of((f.qx0 + hi[0], f.qz0 + hi[1])), []).append((lo, hi, edge))
        smooth = spec.get('shading', 'smooth') == 'smooth'
        for (tx, tz), levels in sorted(tiles.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            x0, z0 = tx * tq, tz * tq
            edge = edge_points(corners[(tx, tz)], corners, tx, tz)
            mine = {p for p in wall_points if x0 <= p[0] <= x0 + tq and z0 <= p[1] <= z0 + tq}
            cell = (math.floor(x0 * f.s / size), math.floor(z0 * f.s / size))
            centre = centre_of(cell)
            meshes = []
            wall_tris = cliff_faces(f, tile_walls.get((tx, tz), []))
            for li, lv in enumerate(levels):
                points = edge | mine
                for r in lv:
                    points.update(rect_corners(r))
                out = MeshOut(palette, centre, textures if li == 0 else None, materials, f'field {f.name!r}')
                faces = []
                for rect in lv:
                    for t in rect_triangles(Sheet(f, rect[5]), rect, points):
                        world = [c[0] for c in t]
                        if smooth:
                            shades = [shade_of(c[1]) for c in t]
                        else:
                            shades = [shade_of(unit(cross(sub(world[1], world[0]), sub(world[2], world[0]))))] * 3
                        faces.append((world, shades, rect[4]))
                for world, material in wall_tris:
                    faces.append((world, [shade_of(unit(cross(sub(world[1], world[0]), sub(world[2], world[0]))))] * 3,
                                  material))
                for world, shades, material in faces:
                    out.tri(world, shades, material)
                    if li == 0:
                        frep['materials'][material] = frep['materials'].get(material, 0) + 1
                        if spec.get('collision', True):
                            a, b, c = world
                            collision.setdefault(cell, []).append(
                                P.Tri(c, b, a, surface=surface_of(materials[material].get('tag')), tag=TAG_FIELD,
                                      slide_floor_degrees=f.slide_floor))
                meshes.append(out)
                frep['triangles'][li] += out.faces
            if walls:
                frep['cliff_triangles'] += len(wall_tris)
            frep['vertices'] += len(meshes[0].mesh.verts)
            cr = frep['cells'].setdefault(f'{cell[0]},{cell[1]}', [0] * len(tols))
            for li, m in enumerate(meshes):
                cr[li] += m.faces
            piece = Piece('field', f.name, meshes[0].pack(), meshes[0].faces, ground=spec.get('ground', True),
                          tag=TAG_FIELD, materials=set().union(*(m.materials for m in meshes)),
                          level_faces=[m.faces for m in meshes])
            if lod and meshes[1].faces < meshes[0].faces:
                piece.levels = [(lod['distance'], meshes[1].pack())]
                piece.band = lod.get('band', DEFAULT_LOD_BAND)
            pieces.setdefault(cell, []).append(piece)
        # water: flat, semi-transparent surfaces over the quads below their level; not ground (it
        # can be seen through), no collision (the game wades: wp_water() answers the level)
        for (tx, tz), wl in sorted(wtiles.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            x0, z0 = tx * tq, tz * tq
            points = edge_points(wcorners[(tx, tz)], wcorners, tx, tz)
            for r in wl:
                points.update(rect_corners(r))
            cell = (math.floor(x0 * f.s / size), math.floor(z0 * f.s / size))
            out = MeshOut(palette, centre_of(cell), textures, materials, f'field {f.name!r}\'s water')
            for rect in wl:
                for t in rect_triangles(Sheet(f, rect[5], water=True), rect, points):
                    world = [c[0] for c in t]
                    out.tri(world, [shade_of((0.0, 1.0, 0.0))] * 3, rect[4], meshlib.SEMI)
                    water_tris.append((*world, surface_of(materials[rect[4]].get('tag'))))
            frep['water_triangles'] += out.faces
            pieces.setdefault(cell, []).append(Piece('water', f.name, out.pack(), out.faces, ground=False,
                                                     tag=TAG_FIELD, materials=set(out.materials),
                                                     level_faces=[out.faces]))
        frep['full_triangles'] = 2 * (f.nx * f.nz - frep['holes'])
        report['fields'][f.name] = frep

    # ---- sweeps: strips between cross-sections, risers and caps, each in the cell of its middle
    for sw in sweeps:
        outs = {}
        tris_by_cell = {}
        srep = {'path': sw.name, 'profile_edges': len(sw.profile) - 1, 'cross_sections': 0, 'steps': 0,
                'triangles': 0, 'cells': {}, 'ground': sw.ground}

        def cell_of(x, z):
            return (math.floor(x / size), math.floor(z / size))

        def emit(key, tri, material, normal_hint):
            if key not in cells:
                srep.setdefault('outside', 0)
                srep['outside'] += 1
                return
            lo_x, lo_z = key[0] * size, key[1] * size
            for p in tri:
                if not (lo_x - overhang <= p[0] <= lo_x + size + overhang and lo_z - overhang <= p[2] <= lo_z + size + overhang):
                    raise WorldError(sw.path + '/profile', f'The sweep reaches {p} from cell {list(key)}, past the '
                                     f'world\'s overhang ({overhang}): narrow the profile or raise overhang.')
            n = cross(sub(tri[1], tri[0]), sub(tri[2], tri[0]))
            if dot(n, n) == 0:
                return
            if dot(n, normal_hint) < 0:
                tri = (tri[0], tri[2], tri[1])
                n = (-n[0], -n[1], -n[2])
            if key not in outs:
                outs[key] = MeshOut(palette, centre_of(key), textures, materials, f'the sweep of path {sw.name!r}')
            water = materials[material].get('water')
            flags = (meshlib.SEMI if water else 0) | (meshlib.DOUBLE if sw.double_sided else 0)
            outs[key].tri(tri, [shade_of(unit(n))] * 3, material, flags)
            if water:
                # water is waded, not stood on: no collision; its upward faces answer wp_water()
                if n[1] >= floor_cos * math.sqrt(dot(n, n)):
                    water_tris.append((*tri, surface_of(materials[material].get('tag'))))
                return
            if sw.collision:
                a, b, c = tri
                tris_by_cell.setdefault(key, []).append(P.Tri(c, b, a, surface=surface_of(materials[material].get('tag')),
                                                              tag=TAG_SWEEP))

        def quad(key, p, material, hint):
            emit(key, (p[0], p[1], p[2]), material, hint)
            emit(key, (p[0], p[2], p[3]), material, hint)

        prof = sw.profile
        stations = sw.stations(size)
        for k, seg in enumerate(stations):
            a, b, tdir, ln = sw.segs[k]
            prev = None
            for t, y, frame in seg:
                cs = sweep_section(sw, a, b, t, y, frame)
                srep['cross_sections'] += 1
                if prev is not None:
                    pt, py, pcs, pframe = prev
                    x = a[0] + (b[0] - a[0]) * (pt + t) / 2
                    z = a[2] + (b[2] - a[2]) * (pt + t) / 2
                    key = cell_of(x, z)
                    if t == pt:             # a riser: the profile at two heights
                        srep['steps'] += 1
                        up = 1 if y > py else -1
                        hint = (-tdir[0] * up, 0.0, -tdir[1] * up)
                        for e in range(len(prof) - 1):
                            quad(key, (pcs[e], pcs[e + 1], cs[e + 1], cs[e]), sw.materials[e], hint)
                    else:
                        r = right_of(tdir)
                        for e in range(len(prof) - 1):
                            dx, dy = prof[e + 1][0] - prof[e][0], prof[e + 1][1] - prof[e][1]
                            hint = (-dy * r[0], dx, -dy * r[1])
                            quad(key, (pcs[e], pcs[e + 1], cs[e + 1], cs[e]), sw.materials[e], hint)
                prev = (t, y, cs, frame)
        if sw.caps and len(prof) >= 3:
            # the start faces back along the path, the end forward; each goes to the cell the
            # path leaves from or arrives in (an end on a cell edge belongs to the cell it is in)
            for k, station, sign in ((0, stations[0][0], -1), (len(stations) - 1, stations[-1][-1], 1)):
                a, b, tdir, ln = sw.segs[k]
                t, y, frame = station
                cs = sweep_section(sw, a, b, t, y, frame)
                x, z = a[0] + (b[0] - a[0]) * t, a[2] + (b[2] - a[2]) * t
                key = cell_of(x - tdir[0] * 1e-6 * sign, z - tdir[1] * 1e-6 * sign)
                hint = (tdir[0] * sign, 0.0, tdir[1] * sign)
                for e in range(1, len(cs) - 1):
                    emit(key, (cs[0], cs[e], cs[e + 1]), sw.materials[0], hint)
        if srep.get('outside'):
            warnings.append({'code': 'sweep_outside_cells', 'path': sw.name, 'triangles': srep['outside'],
                             'message': 'Parts of the sweep lie over no cell of the world; they are left out.'})
        for key in sorted(outs, key=lambda c: (c[1], c[0])):
            out = outs[key]
            pieces.setdefault(key, []).append(Piece('sweep', sw.name, out.pack(), out.faces, ground=sw.ground,
                                                    tag=TAG_SWEEP, materials=set(out.materials),
                                                    level_faces=[out.faces]))
            srep['triangles'] += out.faces
            srep['cells'][f'{key[0]},{key[1]}'] = out.faces
            collision.setdefault(key, []).extend(tris_by_cell.get(key, []))
        report['sweeps'][sw.name] = srep

    windowed = set()
    if textures:
        tri_count, win_count, squeezed, win_pieces = {}, {}, {}, 0
        for ps in pieces.values():
            for piece in ps:
                m = piece.mesh
                for rec in (m.recs if isinstance(m, MeshOut) else ()):
                    if rec[4] is not None:
                        tri_count[rec[2]] = tri_count.get(rec[2], 0) + 1
                    if rec[5]:
                        win_count[rec[2]] = win_count.get(rec[2], 0) + 1
                if isinstance(m, MeshOut) and m.windowed:
                    windowed |= m.windowed
                    win_pieces += 1
                for mo in [m] + [lv for _, lv in piece.levels]:
                    for k, n in (mo.squeezed.items() if isinstance(mo, MeshOut) else ()):
                        squeezed[k] = squeezed.get(k, 0) + n
        if squeezed:
            warnings.append({'code': 'terrain_texture_stretched', 'materials': squeezed,
                             'message': 'These faces span more than 255 texels of their texture along an axis '
                                        '(near-vertical quads no merge can shrink), so the texture is stretched '
                                        'on them. A larger scale, or a gentler slope, avoids it.'})
        report['texture_windows'] = {'pieces': win_pieces, 'triangles': sum(win_count.values())}
        report['textures'] = {}
        for m, tex in sorted(textures.items()):
            su, sv = tex.spec.get('scale', [1, 1])
            report['textures'][m] = dict(tex.summary(), scale=[su, sv], span=tex.span,
                                         stored=[tex.tile.width, tex.tile.height],
                                         texel_cm=[round(100 * su / tex.width, 2), round(100 * sv / tex.height, 2)],
                                         reach=round(texel_reach(tex), 3), triangles=tri_count.get(m, 0),
                                         windowed=win_count.get(m, 0), stretched=squeezed.get(m, 0),
                                         far=far.get(m))
    if ctx.files:
        report['files'] = [{'file': f, 'sha256': h} for f, h in ctx.files]
    if water_tris:
        report['water_triangles'] = len(water_tris)
    if resolved:
        report['draped'] = {n: len(p) for n, p in resolved.items()}
    return Result(pieces, collision, palette, report, [f for f, _ in ctx.files], {f.name: f for f in fields},
                  water_tris, resolved, floor_cos, {m: t for m, t in textures.items() if m in used}, windowed)
