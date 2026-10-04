"""The Mei world pack: reference encoder, decoder and exact query oracle (docs/WORLDPACK.md).

    from worldkit.pack import World, Cell, Placement, Tri, Entity, Layer, encode, decode
    w = World(cell_shift=6, layers=[Layer('gate')],
              cells=[Cell(0, 0, placements=[Placement(mesh_bytes, (32, 0, 32))],
                          collision=[Tri((0, 0, 0), (0, 0, 64), (64, 0, 0), surface=1)])])
    data = encode(w)            # bytes, deterministic
    pack = decode(data)         # validates everything; raises PackError

Everything the console reads is precomputed here: cell-local coordinates, plane rows for floors,
walls and ceilings (classified by angle), each collision block's lookup grid, and bounding
spheres. Positions given to the encoder are world coordinates (Y up, units); yaw is in degrees,
turning +Z toward +X as mesh_at() does. Collision triangles wind as mesh faces do: the front is
the side from which the corners appear counter-clockwise, so the front normal is
(c - a) x (b - a).

The Oracle class answers the reader's queries (floor, ceiling, wall push, segment) in exact
rational arithmetic over the same quantized triangles, with a margin that says how far the
answer is from changing, so a test can compare the console with it.

This module does not build assets, read recipes or know what a game is: it packs what it is
given. It depends only on the Python standard library.
"""
from dataclasses import dataclass, field
from fractions import Fraction
import math
import struct

MAGIC = b'MEIW'
VERSION_MAJOR = 1
VERSION_MINOR = 4           # the newest minor this module writes and reads
HEADER_SIZE = 80            # 64 in 1.0 and 1.1; 1.2 adds path_count and path_off; 1.3 near_far, lod_slots
HEADER_SIZE_1_4 = 84        # 1.4 adds region_ext_off
MINOR_PLAIN = 3             # the minor version written for a pack that needs no 1.4 region extension
HEADER_SIZE_1_2 = 72
MIN_HEADER_SIZE = 64
CELL_SIZE = 96
PLACEMENT_SIZE = 48
ENTITY_SIZE = 64
FLAT_SIZE = 64
WALL_SIZE = 80
COLL_SIZE = 48
BUCKET_SIZE = 8
LAYER_SIZE = 8
REGION_SIZE = 32
TEXTURE_SIZE = 12
SAMPLE_SIZE = 20
VRAM_COPY_SIZE = 12
PATH_SIZE = 48
PATH_POINT_SIZE = 40
LOD_HEAD_SIZE = 8
LOD_LEVEL_SIZE = 16
REGION_EXT_SIZE = 32        # (1.4) per region: palette runs, animated textures, the backdrop's planes
RUN_SIZE = 8
ANIM_SIZE = 20
SKY_SIZE = 32
SKY_SILHOUETTE = 1          # sky flags bit 0: a silhouette on plane BG1

ONE = 65536
NO_LAYER = 0xFF
NO_GROUP = 0xFF
MIN_CELL_SHIFT = 4          # 16 units
MAX_CELL_SHIFT = 7          # 128 units
MAX_GRID_SHIFT = 5          # 32 x 32 buckets
MAX_LAYERS = 255
MAX_CELL_LAYERS = 8
MAX_COORD = 4096            # |local collision coordinate| and |y| (units)
MAX_WORLD = 32767           # |world x, z| of everything (units)
MAX_MESH_VERTS = 2048
FLAG_SAVED = 1
PLACEMENT_GROUND = 1        # placement flags bit 0 (1.1): drawn in the ground pass
FLAGS_REQUIRED = 0xF0       # header flag bits a reader must understand (none defined in 1.1)
FLAG_GROUND = 1             # header flags bit 0 (1.1, ignorable): some placement is ground
PATH_RAISED = 1             # path flags bit 0 (1.2): raised, not lying on the ground
PATH_CLOSED = 2             # path flags bit 1 (1.2): a loop (its last stored point repeats its first)
MAX_PATH_POINTS = 4096      # stored points of one path
MAX_PATH_LENGTH = 16384     # units: keeps every product the reader forms inside fixed range
MAX_LOD_LEVELS = 8          # levels after level 0 in one LOD set, the cull mark included
MAX_LOD_DISTANCE = 1400     # units: (distance / 8)^2 stays inside fixed range
LOD_CULL = 1                # LOD set flags bit 0 (1.3): the last mark culls (its mesh is 0)

KIND_FLOOR, KIND_WALL, KIND_CEILING = 0, 1, 2
KIND_NAMES = ('floor', 'wall', 'ceiling')


class PackError(ValueError):
    """A world description the format cannot hold, or bytes that are not a valid pack."""


# ---- fixed point

def rnd(v):
    """Nearest integer, halves away from zero (so -x rounds to exactly -round(x))."""
    if isinstance(v, Fraction):
        n, d = abs(v.numerator), v.denominator
        q = (2 * n + d) // (2 * d)
        return q if v >= 0 else -q
    q = math.floor(abs(v) + 0.5)
    return int(q) if v >= 0 else -int(q)


def fx(v):
    """World units (float, int or Fraction) to raw 16.16."""
    return rnd(Fraction(v) * ONE) if not isinstance(v, float) else rnd(v * ONE)


def check_s32(v, what):
    if not -2**31 <= v < 2**31:
        raise PackError(f'{what} does not fit 16.16 fixed point')
    return v


def fmul(a, b):
    """The CPU's fmul: (a * b) >> 16 with a 64-bit product, arithmetic shift."""
    return (a * b) >> 16


def bucket_of(x, half, inv, g):
    """The lookup-grid column (or row) of raw coordinate x, exactly as the reader computes it:
    clamp(floor(fmul(x + half, inv) / 65536), 0, g - 1)."""
    return max(0, min(g - 1, fmul(x + half, inv) >> 16))


# ---- the description the encoder takes

@dataclass
class Tri:
    """A collision triangle. Corners are world coordinates for cell collision and the entity's
    own frame for entity collision. surface is the game's byte; layer a layer name or None;
    tag a 16-bit number carried into the record (0xFFFF: none), e.g. the placement it came from."""
    a: tuple
    b: tuple
    c: tuple
    surface: int = 0
    layer: str = None
    tag: int = 0xFFFF


@dataclass
class Placement:
    """An asset drawn at a position and yaw. ground: drawn in the reader's ground pass, before
    everything else near the camera (WORLDPACK.md, "Ground"); the encoder files a cell's ground
    placements first, keeping their order and the order of the rest."""
    mesh: bytes
    position: tuple
    yaw: float = 0.0
    layer: str = None
    tag: int = 0
    ground: bool = False
    lod: object = None      # Lod (1.3): coarser meshes farther away; mesh is level 0


@dataclass
class Lod:
    """A placement's levels of detail (WORLDPACK.md, "Levels of detail"): levels[k - 1] =
    (distance, mesh) for level k, from that distance (units from the viewer to the placement's
    sphere centre) on; a mesh of None is "not drawn" and may only be the last (a cull distance).
    band: the hysteresis, units."""
    levels: list
    band: float = 1.0


@dataclass
class Entity:
    type: int
    position: tuple
    yaw: float = 0.0
    layer: str = None
    saved_bit: int = -1
    params: bytes = b''
    names: list = field(default_factory=list)        # (byte offset in params, text): `name`
                                                     # parameters, patched to string offsets
    mesh: bytes = None
    collision: list = field(default_factory=list)    # Tri in the entity's own frame
    collision_half: float = None                     # grid half-extent (None: fitted)


@dataclass
class Cell:
    i: int
    j: int
    region: int = 0
    layers: list = field(default_factory=list)       # names; triangles' layers are added
    standin: bytes = None
    placements: list = field(default_factory=list)
    collision: list = field(default_factory=list)    # Tri, world coordinates
    entities: list = field(default_factory=list)
    grid_shift: int = None                           # None: chosen by the encoder


@dataclass
class Layer:
    name: str
    group: int = NO_GROUP
    on: bool = False


@dataclass
class Texture:
    slot: int
    data: bytes
    four_bit: bool = True


@dataclass
class Sample:
    name: str
    data: bytes
    samples: int
    loop_start: int = 0
    flags: int = 0


@dataclass
class VramCopy:
    address: int
    data: bytes


@dataclass
class PaletteRun:
    """(1.4) Palette colours beyond the region's main run (an 8-bit texture's 256-colour
    palette): one list of colours per palette variant of the region, in the variants' order."""
    first_colour: int
    variants: list


@dataclass
class Animation:
    """(1.4) An animated texture: `frames` frames in `data`, each `rows` rows of `row_bytes`,
    copied to texture-area byte `vram` (VRAM_TEXTURES + vram) with rows `stride` bytes apart,
    each shown `ticks` ticks."""
    data: bytes
    frames: int
    ticks: int
    row_bytes: int
    rows: int
    vram: int
    stride: int


@dataclass
class Sky:
    """(1.4) How the reader sets up the plane chip for a region's backdrop, whose art the
    region's backdrop copies put in VRAM (WORLDPACK.md, "Backdrops"): a sky gradient on the
    backdrop colour by elevation (radians above the horizon, increasing), one colour (0xBBGGRR)
    per stop for each palette variant; and optionally a silhouette on tile plane BG1 (`mode`,
    `atlas`, `map`: the plane's registers), scrolled `rate` pixels a radian of yaw, its plane
    row `horizon` on the horizon, its rows `top` .. `top + height - 1` shown."""
    elevations: list            # radians (floats, or raw ints), increasing
    colours: list               # per variant: [0xBBGGRR] * len(elevations)
    mode: int = 0
    atlas: int = 0
    map: int = 0
    rate: float = 0.0
    horizon: int = 0
    top: int = 0
    height: int = 0             # 0: no silhouette


@dataclass
class Region:
    name: str = 'default'
    textures: list = field(default_factory=list)
    first_colour: int = 0
    variants: list = field(default_factory=list)     # (name, [15-bit colours])
    samples: list = field(default_factory=list)
    backdrop: list = field(default_factory=list)     # VramCopy
    runs: list = field(default_factory=list)         # PaletteRun (1.4)
    animations: list = field(default_factory=list)   # Animation (1.4)
    sky: object = None                               # Sky (1.4)

    @property
    def extended(self):
        """Whether the region needs the 1.4 region extension."""
        return bool(self.runs or self.animations or self.sky)


@dataclass
class Path:
    """A named polyline in world coordinates (WORLDPACK.md, "Paths"). closed joins the last
    point back to the first (do not repeat it: the encoder stores the repeat). raised and surface
    are carried for the game; the format attaches no meaning to them."""
    name: str
    points: list
    raised: bool = False
    closed: bool = False
    surface: int = 0


@dataclass
class World:
    cells: list
    cell_shift: int = 6
    layers: list = field(default_factory=list)
    regions: list = field(default_factory=lambda: [Region()])
    coll_pad: float = 1.0
    overhang: float = 8.0
    floor_max_degrees: float = 45.0
    ceiling_max_degrees: float = 45.0
    paths: list = field(default_factory=list)       # Path (1.2)
    near_far: float = None                          # (1.3) the near pass's far depth; None: 1.5 cells


# ---- meshes

def mesh_info(data, what='mesh'):
    """(vertex count, face count, vertex offset, face offset) of a native mesh, validated."""
    if len(data) < 16:
        raise PackError(f'{what}: shorter than a mesh header')
    nv, nf, vo, fo, res = struct.unpack_from('<HHIII', data)
    if nv > MAX_MESH_VERTS:
        raise PackError(f'{what}: {nv} vertices (at most {MAX_MESH_VERTS})')
    if vo % 4 or fo % 4 or vo < 16 or fo < 16:
        raise PackError(f'{what}: bad vertex or face offset')
    if vo + 16 * nv > len(data) or fo + 36 * nf > len(data):
        raise PackError(f'{what}: vertices or faces run past its end')
    return nv, nf, vo, fo


def mesh_vertices(data):
    nv, nf, vo, fo = mesh_info(data)
    return [tuple(Fraction(c, ONE) for c in struct.unpack_from('<3i', data, vo + 16 * k))
            for k in range(nv)]


def mesh_triangles(data, skip_flags=0):
    """The faces of a native mesh as front-facing triangles (a, b, c) of Fractions, ready to be
    Tri corners: quads give (0, 1, 2) and (2, 1, 3). Faces with any of skip_flags are left out."""
    nv, nf, vo, fo = mesh_info(data)
    verts = mesh_vertices(data)
    out = []
    for k in range(nf):
        flags = data[fo + 36 * k]
        idx = struct.unpack_from('<4H', data, fo + 36 * k + 4)
        if flags & skip_flags:
            continue
        if max(idx[:4 if flags & 4 else 3]) >= nv:
            raise PackError('mesh: face index out of range')
        out.append((verts[idx[0]], verts[idx[1]], verts[idx[2]]))
        if flags & 4:
            out.append((verts[idx[2]], verts[idx[1]], verts[idx[3]]))
    return out


# ---- geometry on raw integers

def sub3(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def dot3(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross3(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def front_normal(a, b, c):
    """Unnormalized front normal (c - a) x (b - a), exact for integer or Fraction corners."""
    return cross3(sub3(c, a), sub3(b, a))


def classify(n, floor_cos, ceiling_cos):
    """KIND_* of a triangle with (unnormalized) front normal n."""
    ny = n[1]
    nn = dot3(n, n)
    if nn == 0:
        raise PackError('degenerate collision triangle')
    if ny > 0 and ny * ny >= floor_cos * floor_cos * nn:
        return KIND_FLOOR
    if ny < 0 and ny * ny >= ceiling_cos * ceiling_cos * nn:
        return KIND_CEILING
    return KIND_WALL


def _xz_edges(v):
    """Edge rows (mx, mz, k) of a flat triangle's XZ projection, positive inside. Each edge is
    computed from its endpoints in a canonical order and negated as needed, so two triangles
    sharing an edge get exactly opposite rows and no point between them is missed."""
    rows = []
    for e in range(3):
        p, q, r = v[e], v[(e + 1) % 3], v[(e + 2) % 3]
        P, Q = sorted([(p[0], p[2]), (q[0], q[2])])
        dx, dz = Q[0] - P[0], Q[1] - P[1]
        ln = math.hypot(dx, dz)
        mx, mz = rnd(-dz / ln * ONE), rnd(dx / ln * ONE)
        k = rnd(-Fraction(mx * (P[0] + Q[0]) + mz * (P[1] + Q[1]), 2 * ONE))
        side = -dz * (r[0] - P[0]) + dx * (r[2] - P[1])
        if side < 0:
            mx, mz, k = -mx, -mz, -k
        rows.append((mx, mz, k))
    return rows


def _plane_edges(v, n):
    """In-plane edge rows (ux, uy, uz, k) of a wall, positive inside: u is the unit vector in the
    plane, perpendicular to the edge, pointing at the third corner."""
    nl = math.sqrt(dot3(n, n))
    nu = (n[0] / nl, n[1] / nl, n[2] / nl)
    rows = []
    for e in range(3):
        p, q, r = v[e], v[(e + 1) % 3], v[(e + 2) % 3]
        P, Q = sorted([p, q])
        d = sub3(Q, P)
        u = cross3(nu, d)
        ul = math.sqrt(dot3(u, u))
        ur = tuple(rnd(c / ul * ONE) for c in u)
        k = rnd(-Fraction(dot3(ur, (P[0] + Q[0], P[1] + Q[1], P[2] + Q[2])), 2 * ONE))
        side = dot3(cross3(n, d), sub3(r, P))
        if side < 0:
            ur, k = (-ur[0], -ur[1], -ur[2]), -k
        rows.append(ur + (k,))
    return rows


def flat_record(v, n, info):
    """A floor or ceiling record: the height row (a, b, c, info) and three XZ edge rows with
    the triangle's lowest and highest y in the w lanes of the first two."""
    ny = n[1]
    a = rnd(Fraction(-n[0] * ONE, ny))
    b = rnd(Fraction(-n[2] * ONE, ny))
    g = [Fraction(v[0][k] + v[1][k] + v[2][k], 3) for k in range(3)]
    c = rnd(g[1] - Fraction(a * g[0] + b * g[2], ONE))       # exact at the centroid
    e = _xz_edges(v)
    ymin = min(p[1] for p in v)
    ymax = max(p[1] for p in v)
    vals = [a, b, c, info, e[0][0], e[0][1], e[0][2], ymin, e[1][0], e[1][1], e[1][2], ymax,
            e[2][0], e[2][1], e[2][2], 0]
    for x in vals[:3] + vals[4:]:
        check_s32(x, 'collision row')
    return struct.pack('<3iI12i', *vals)


def wall_record(v, n, info):
    nl = math.sqrt(dot3(n, n))
    nr = tuple(rnd(c / nl * ONE) for c in n)
    g2 = (v[0][0] + v[1][0] + v[2][0], v[0][1] + v[1][1] + v[2][1], v[0][2] + v[1][2] + v[2][2])
    w = rnd(-Fraction(dot3(nr, g2), 3 * ONE))
    e = _plane_edges(v, n)
    h = math.hypot(n[0], n[2])
    hx, hz, inv = rnd(n[0] / h * ONE), rnd(n[2] / h * ONE), rnd(nl / h * ONE)
    vals = list(nr) + [w] + [x for row in e for x in row] + [hx, hz, inv]
    for x in vals:
        check_s32(x, 'collision row')
    return struct.pack('<19iI', *vals, info)


# ---- layout helpers

class _Out:
    def __init__(self):
        self.b = bytearray()

    def align(self, n=4):
        while len(self.b) % n:
            self.b.append(0)

    def put(self, data, align=4):
        self.align(align)
        off = len(self.b)
        self.b += data
        return off

    def reserve(self, n, align=4):
        return self.put(bytes(n), align)

    def patch(self, off, fmt, *vals):
        struct.pack_into('<' + fmt, self.b, off, *vals)


def _sphere_of_points(pts):
    """A bounding sphere (raw centre, raw radius) of raw points: the box centre and the largest
    distance from it, rounded up."""
    lo = [min(p[k] for p in pts) for k in range(3)]
    hi = [max(p[k] for p in pts) for k in range(3)]
    c = [(lo[k] + hi[k]) // 2 for k in range(3)]
    r = max(math.sqrt(sum((p[k] - c[k]) ** 2 for k in range(3))) for p in pts)
    return c, math.ceil(r) + 2


def _sphere_of_spheres(spheres):
    lo = [min(c[k] - r for c, r in spheres) for k in range(3)]
    hi = [max(c[k] + r for c, r in spheres) for k in range(3)]
    cc = [(lo[k] + hi[k]) // 2 for k in range(3)]
    r = max(math.sqrt(sum((c[k] - cc[k]) ** 2 for k in range(3))) + rr for c, rr in spheres)
    return cc, math.ceil(r) + 2


def _yaw_rows(deg):
    a = math.radians(deg)
    return rnd(math.cos(a) * ONE), rnd(math.sin(a) * ONE)


def _rotate(v, c, s):
    """A mesh vertex (raw) turned as mesh_at() turns it, with the stored (rounded) cos and sin."""
    return (fmul(c, v[0]) + fmul(s, v[2]), v[1], fmul(-s, v[0]) + fmul(c, v[2]))


def _raw3(p, what):
    r = tuple(fx(c) for c in p)
    for c in r:
        check_s32(c, what)
    return r


class _Coll:
    """One collision block being built: classified raw triangles in its own frame."""

    def __init__(self):
        self.tris = []      # (kind, verts raw, n, surface, layer name, tag)


def _reach(kind, v, pad):
    """The box (x0, x1, z0, z1, raw) of every point at which the reader can find this
    triangle: for a floor or ceiling, every point its rounded edge rows accept (the triangle
    their lines make, worked out exactly); for a wall, every point within pad of it, grown by
    how far rounding can move its edges."""
    xs = [p[0] for p in v]
    zs = [p[2] for p in v]
    longest = max(math.sqrt(dot3(sub3(v[i], v[(i + 1) % 3]), sub3(v[i], v[(i + 1) % 3]))) for i in range(3))
    g = math.ceil(0.5 * longest / ONE) + 4
    grown = (min(xs) - pad - g, max(xs) + pad + g, min(zs) - pad - g, max(zs) + pad + g)
    if kind == KIND_WALL:
        return grown
    rows = _xz_edges(v)
    pts = list(zip(xs, zs))
    for i in range(3):
        a1, b1, c1 = rows[i]
        a2, b2, c2 = rows[(i + 1) % 3]
        det = a1 * b2 - a2 * b1
        if det == 0:
            return grown
        x = Fraction(-ONE * (c1 * b2 - c2 * b1), det)
        z = Fraction(-ONE * (a1 * c2 - a2 * c1), det)
        if not (min(xs) - ONE <= x <= max(xs) + ONE and min(zs) - ONE <= z <= max(zs) + ONE):
            return grown
        pts.append((x, z))
    return (math.floor(min(p[0] for p in pts)), math.ceil(max(p[0] for p in pts)),
            math.floor(min(p[1] for p in pts)), math.ceil(max(p[1] for p in pts)))


def _choose_grid(tris, half, pad, fixed_shift):
    shifts = [fixed_shift] if fixed_shift is not None else range(MAX_GRID_SHIFT + 1)
    best = None
    boxes = [(kind, _reach(kind, v, pad), ti) for kind, v, n, ti in tris]
    for gs in shifts:
        g = 1 << gs
        inv = rnd(Fraction(g * ONE * ONE, 2 * half))
        buckets = [[[], [], []] for _ in range(g * g)]
        for kind, (x0, x1, z0, z1), ti in boxes:
            # half-open: a point exactly on the box's far side is on the surface's outer edge
            for bz in range(bucket_of(z0, half, inv, g), bucket_of(max(z0, z1 - 1), half, inv, g) + 1):
                for bx in range(bucket_of(x0, half, inv, g), bucket_of(max(x0, x1 - 1), half, inv, g) + 1):
                    buckets[bz * g + bx][kind].append(ti)
        worst = max((max(len(l) for l in b) for b in buckets), default=0)
        cand = (gs, inv, buckets, worst)
        if fixed_shift is not None or worst <= 12:
            best = cand
            break
        if best is None or worst < best[3]:
            best = cand
    if best[3] > 255:
        raise PackError(f'a lookup bucket holds {best[3]} triangles of one kind (at most 255)')
    return best


def _write_coll(out, tris, half, pad, grid_shift, floor_cos, ceiling_cos, layer_mask_of):
    """Writes a collision block (frame-local raw triangles) and returns its offset, or 0."""
    if not tris:
        return 0
    by_kind = [[], [], []]
    classified = []
    for t in tris:
        v, surface, layer, tag = t
        n = front_normal(*v)
        kind = classify(n, floor_cos, ceiling_cos)
        if not 0 <= surface <= 255:
            raise PackError('surface byte out of range')
        if not 0 <= tag <= 0xFFFF:
            raise PackError('triangle tag out of range')
        for p in v:
            for k in range(3):
                if abs(p[k]) > MAX_COORD * ONE:
                    raise PackError(f'collision corner beyond +-{MAX_COORD} in its frame')
        info = surface | (layer_mask_of(layer) << 8) | (tag << 16)
        ti = len(by_kind[kind])
        by_kind[kind].append((v, n, info))
        classified.append((kind, v, n, ti))
    for kind in range(3):
        if len(by_kind[kind]) > 0xFFFF:
            raise PackError('more than 65535 collision triangles of one kind in a block')
    gs, inv, buckets, worst = _choose_grid(classified, half, pad, grid_shift)
    head = out.reserve(COLL_SIZE)
    offs = []
    for kind in range(3):
        if not by_kind[kind]:
            offs.append(0)
            continue
        recs = b''.join((wall_record if kind == KIND_WALL else flat_record)(v, n, info)
                        for v, n, info in by_kind[kind])
        offs.append(out.put(recs))
    lst = []
    brecs = bytearray()
    for b in buckets:
        brecs += struct.pack('<I4B', len(lst), len(b[0]), len(b[1]), len(b[2]), 0)
        lst += b[0] + b[1] + b[2]
    bucket_off = out.put(bytes(brecs))
    list_off = out.put(struct.pack(f'<{len(lst)}H', *lst)) if lst else 0
    out.patch(head, 'BBHiii8I', gs, 0, 0, half, inv, pad,
              len(by_kind[0]), offs[0], len(by_kind[1]), offs[1], len(by_kind[2]), offs[2],
              bucket_off, list_off)
    return head


def entity_numbers(world):
    """{(i, j, k): number} for the k-th entity of cell (i, j): the numbers encode() will give
    them (cells by row j, then column i; entities in order), for filling entity_ref parameters
    before encoding."""
    out = {}
    for c in sorted(world.cells, key=lambda c: (c.j, c.i)):
        for k in range(len(c.entities)):
            out[(c.i, c.j, k)] = len(out)
    return out


def world_triangles(world):
    """Every collision triangle of a world, quantized as the encoder quantizes it, in world raw
    coordinates: a list of dicts (kind, v, n, surface, layer, tag). The oracle uses these."""
    fc = math.cos(math.radians(world.floor_max_degrees))
    cc = math.cos(math.radians(world.ceiling_max_degrees))
    out = []
    for cell in world.cells:
        for t in cell.collision:
            v = tuple(_raw3(p, 'collision corner') for p in (t.a, t.b, t.c))
            n = front_normal(*v)
            out.append(dict(kind=classify(n, fc, cc), v=v, n=n, surface=t.surface,
                            layer=t.layer, tag=t.tag))
    return out


# ---- paths

def _round_sqrt(n):
    """round(sqrt(n)) for a non-negative integer n, exactly (halves cannot occur)."""
    r = math.isqrt(n)
    return r + 1 if n - r * r > r else r


def path_points(path):
    """A Path's stored point records, raw: a list of (pos, dir, s, len), where pos is the point,
    dir the rounded unit direction of the segment to the next point (zero for the last), len that
    segment's rounded length and s the sum of the lens before it. A closed path stores its first
    point again at the end. Also returns the box (lo, hi) of the points. Raises PackError for what
    the format cannot hold."""
    pts = [_raw3(p, f'path {path.name!r} point') for p in path.points]
    if path.closed:
        if len(pts) < 3:
            raise PackError(f'path {path.name!r}: a closed path has at least 3 points')
        pts.append(pts[0])
    if len(pts) < 2:
        raise PackError(f'path {path.name!r}: a path has at least 2 points')
    if len(pts) > MAX_PATH_POINTS:
        raise PackError(f'path {path.name!r}: more than {MAX_PATH_POINTS} points')
    for p in pts:
        if max(abs(c) for c in p) > MAX_WORLD * ONE:
            raise PackError(f'path {path.name!r}: a point lies beyond +-{MAX_WORLD} units')
    recs = []
    s = 0
    for k, p in enumerate(pts):
        if k == len(pts) - 1:
            recs.append((p, (0, 0, 0), s, 0))
            break
        d = sub3(pts[k + 1], p)
        n2 = dot3(d, d)
        ln = _round_sqrt(n2)
        if ln == 0:
            raise PackError(f'path {path.name!r}: segment {k} has no length')
        exact = math.sqrt(n2)
        u = tuple(rnd(c / exact * ONE) for c in d)
        recs.append((p, u, s, ln))
        s += ln
    if s > MAX_PATH_LENGTH * ONE:
        raise PackError(f'path {path.name!r}: longer than {MAX_PATH_LENGTH} units')
    lo = tuple(min(p[k] for p in pts) for k in range(3))
    hi = tuple(max(p[k] for p in pts) for k in range(3))
    return recs, lo, hi


def _write_paths(out, paths, string_ref):
    """The path table and each path's points (1.2); returns the table's offset, or 0."""
    if not paths:
        return 0
    names = set()
    for p in paths:
        if not p.name or p.name in names:
            raise PackError(f'path names must be distinct and not empty ({p.name!r})')
        names.add(p.name)
        if not 0 <= p.surface <= 255:
            raise PackError(f'path {p.name!r}: surface byte out of range')
    table = out.reserve(PATH_SIZE * len(paths))
    for k, p in enumerate(paths):
        recs, lo, hi = path_points(p)
        body = b''.join(struct.pack('<4i4i2i', *pos, 0, *u, 0, s, ln) for pos, u, s, ln in recs)
        po = out.put(body)
        at = table + PATH_SIZE * k
        flags = (PATH_RAISED if p.raised else 0) | (PATH_CLOSED if p.closed else 0)
        out.patch(at, 'IIIBBH4i4i', 0, len(recs), po, flags, p.surface, 0, *lo, recs[-1][2], *hi, 0)
        string_ref(at, p.name)
    return table


# ---- levels of detail

def lod_square(d):
    """(d / 8)^2 as raw 16.16 for a distance d in units, from d rounded to 16.16 first."""
    D = fx(d)
    return rnd(Fraction(D * D, 64 * ONE))


def lod_rows(lod):
    """A Lod's level rows: [(at2, out2, in2, mesh or None)], checked."""
    if not 1 <= len(lod.levels) <= MAX_LOD_LEVELS:
        raise PackError(f'a LOD set has 1..{MAX_LOD_LEVELS} levels after level 0')
    band = lod.band
    if band < 0:
        raise PackError('LOD band below 0')
    prev = 0
    rows = []
    for k, (d, mesh) in enumerate(lod.levels):
        if mesh is None and k != len(lod.levels) - 1:
            raise PackError('only the last LOD level may cull (no mesh)')
        if mesh is not None:
            mesh_info(mesh)
        if d - band <= prev + band or d + band > MAX_LOD_DISTANCE:
            raise PackError(f'LOD distance {d}: distances increase by more than twice the band ({band}), '
                            f'and stay within {MAX_LOD_DISTANCE} units with the band')
        prev = d
        rows.append((lod_square(d), lod_square(d + band), lod_square(d - band), mesh))
    return rows


def lod_level(rows, d2, state=None, fine=False):
    """The level the reader draws (0 .. len(rows)) for d2, the squared distance / 64 as raw (what
    the reader computes), given the level drawn before (state, None when unknown): with no state
    the plain thresholds; with one, the level kept within the hysteresis band; fine: the finest
    level the band allows (the World Checker's worst case)."""
    plain = sum(1 for r in rows if d2 >= r[0])
    lo = sum(1 for r in rows if d2 >= r[1])       # past (d + band): must be at least this coarse
    hi = sum(1 for r in rows if d2 >= r[2])       # past (d - band): may be this coarse
    if fine:
        return lo
    if state is None:
        return plain
    return min(max(state, lo), hi)


def lod_d2(sphere, eye_local, off=(0, 0, 0)):
    """The reader's d2 for a placement sphere (raw, cell-local) seen from eye_local (raw,
    relative to the same cell's centre after off): q = (centre + off - eye) * 0.125 with the CPU's
    fmul, then vdot's exact sum shifted right 16."""
    q = [fmul(sphere[i] + off[i] - eye_local[i], ONE // 8) for i in range(3)]
    return (q[0] * q[0] + q[1] * q[1] + q[2] * q[2]) >> 16


# ---- the encoder

def encode(world, report=None):
    """The pack for a World, as bytes. Raises PackError for anything the format cannot hold.
    If report is a dict it receives the layer ids, entity numbers and offsets."""
    if not MIN_CELL_SHIFT <= world.cell_shift <= MAX_CELL_SHIFT:
        raise PackError(f'cell_shift must be {MIN_CELL_SHIFT}..{MAX_CELL_SHIFT}')
    if not world.cells:
        raise PackError('a world has at least one cell')
    shift = world.cell_shift
    size = 1 << shift
    half = (size // 2) * ONE
    pad = fx(world.coll_pad)
    overhang = fx(world.overhang)
    if not 0 <= pad <= half or not 0 <= overhang <= half:
        raise PackError('coll_pad and overhang must be 0..half a cell')
    fc = math.cos(math.radians(world.floor_max_degrees))
    cc = math.cos(math.radians(world.ceiling_max_degrees))
    if len(world.layers) > MAX_LAYERS:
        raise PackError(f'more than {MAX_LAYERS} layers')
    layer_id = {}
    for k, l in enumerate(world.layers):
        if l.name in layer_id:
            raise PackError(f'duplicate layer {l.name!r}')
        if not 0 <= l.group <= 255:
            raise PackError('layer group out of range')
        layer_id[l.name] = k
    if not world.regions or len(world.regions) > 0xFFFF:
        raise PackError('a world has 1..65535 regions')
    seen = set()
    for c in world.cells:
        if (c.i, c.j) in seen:
            raise PackError(f'two cells at ({c.i}, {c.j})')
        seen.add((c.i, c.j))
        if not 0 <= c.region < len(world.regions):
            raise PackError(f'cell ({c.i}, {c.j}): no region {c.region}')
        lo, hi = (c.i << shift) * ONE, ((c.i + 1) << shift) * ONE
        if min(c.i << shift, c.j << shift) < -MAX_WORLD or max((c.i + 1) << shift, (c.j + 1) << shift) > MAX_WORLD:
            raise PackError(f'cell ({c.i}, {c.j}) lies beyond +-{MAX_WORLD} units')
    i0 = min(c.i for c in world.cells)
    j0 = min(c.j for c in world.cells)
    gw = max(c.i for c in world.cells) - i0 + 1
    gh = max(c.j for c in world.cells) - j0 + 1
    cells = sorted(world.cells, key=lambda c: (c.j, c.i))

    # Collision: every triangle goes into each cell whose square (grown by the pad for walls)
    # its box overlaps, translated into that cell's frame.
    tris = world_triangles(world)
    cell_tris = {(c.i, c.j): [] for c in cells}
    cell_layers = {(c.i, c.j): list(c.layers) for c in cells}
    for c in cells:
        for name in c.layers:
            if name not in layer_id:
                raise PackError(f'cell ({c.i}, {c.j}): unknown layer {name!r}')
    for t in tris:
        if t['layer'] is not None and t['layer'] not in layer_id:
            raise PackError(f'collision triangle: unknown layer {t["layer"]!r}')
        xs = [p[0] for p in t['v']]
        zs = [p[2] for p in t['v']]
        far = pad + 2 * ONE
        for ci in range(((min(xs) - far) >> 16) >> shift, (((max(xs) + far) >> 16) >> shift) + 1):
            for cj in range(((min(zs) - far) >> 16) >> shift, (((max(zs) + far) >> 16) >> shift) + 1):
                key = (ci, cj)
                if key not in cell_tris:
                    continue
                cx, cz = (ci << shift) * ONE + half, (cj << shift) * ONE + half
                x0, x1, z0, z1 = _reach(t['kind'], tuple((p[0] - cx, p[1], p[2] - cz) for p in t['v']), pad)
                if x1 <= -half or x0 >= half or z1 <= -half or z0 >= half:
                    continue
                v = tuple((p[0] - cx, p[1], p[2] - cz) for p in t['v'])
                cell_tris[key].append((v, t['surface'], t['layer'], t['tag']))
                if t['layer'] is not None and t['layer'] not in cell_layers[key]:
                    cell_layers[key].append(t['layer'])

    out = _Out()
    out.reserve(HEADER_SIZE_1_4 if any(r.extended for r in world.regions) else HEADER_SIZE)
    strings = {}
    pending_strings = []        # (patch offset, text)

    def string_ref(at, text):
        pending_strings.append((at, text))

    meshes = {}
    mesh_order = []
    pending_meshes = []         # (patch offset, bytes)

    def mesh_ref(at, data):
        if data is None:
            return
        mesh_info(data)
        if data not in meshes:
            meshes[data] = None
            mesh_order.append(data)
        pending_meshes.append((at, data))

    blobs = []                  # (patch offset, bytes, align, [(offset in bytes, string)])

    def blob_ref(at, data, align=4, names=()):
        blobs.append((at, data, align, names))

    index_off = out.reserve(4 * gw * gh)
    layer_off = out.reserve(LAYER_SIZE * len(world.layers)) if world.layers else 0
    for k, l in enumerate(world.layers):
        at = layer_off + LAYER_SIZE * k
        out.patch(at, 'IBBH', 0, l.group, 1 if l.on else 0, 0)
        string_ref(at, l.name)

    region_off = out.reserve(REGION_SIZE * len(world.regions))
    for k, r in enumerate(world.regions):
        at = region_off + REGION_SIZE * k
        string_ref(at, r.name)
        tex_off = out.reserve(TEXTURE_SIZE * len(r.textures)) if r.textures else 0
        for t, tex in enumerate(r.textures):
            if not 0 <= tex.slot <= 15:
                raise PackError('texture slot out of range')
            out.patch(tex_off + TEXTURE_SIZE * t, 'BBHII', tex.slot, 1 if tex.four_bit else 0, 0, 0,
                      len(tex.data))
            blob_ref(tex_off + TEXTURE_SIZE * t + 4, tex.data)
        smp_off = out.reserve(SAMPLE_SIZE * len(r.samples)) if r.samples else 0
        for s, smp in enumerate(r.samples):
            at2 = smp_off + SAMPLE_SIZE * s
            out.patch(at2, '5I', 0, 0, smp.samples, smp.loop_start, smp.flags)
            string_ref(at2, smp.name)
            blob_ref(at2 + 4, smp.data)
        nvar = len(r.variants)
        ncol = len(r.variants[0][1]) if r.variants else 0
        pal_off = 0
        if nvar:
            if any(len(cols) != ncol for _, cols in r.variants):
                raise PackError(f'region {r.name!r}: palette variants differ in length')
            if r.first_colour + ncol > 4096:
                raise PackError(f'region {r.name!r}: palette runs past colour 4095')
            pal_off = out.reserve(4 * nvar)
            for vi, (name, cols) in enumerate(r.variants):
                string_ref(pal_off + 4 * vi, name)
            out.put(b''.join(struct.pack(f'<{ncol}H', *cols) for _, cols in r.variants))
        bd_off = out.reserve(VRAM_COPY_SIZE * len(r.backdrop)) if r.backdrop else 0
        for b, cp in enumerate(r.backdrop):
            out.patch(bd_off + VRAM_COPY_SIZE * b, '3I', cp.address, 0, len(cp.data))
            blob_ref(bd_off + VRAM_COPY_SIZE * b + 4, cp.data)
        out.patch(at + 4, 'HHIIHHHHII', len(r.textures), len(r.samples), tex_off, smp_off,
                  nvar, ncol, r.first_colour, len(r.backdrop), pal_off, bd_off)

    extended = any(r.extended for r in world.regions)
    ext_off = out.reserve(REGION_EXT_SIZE * len(world.regions)) if extended else 0
    for k, r in enumerate(world.regions):
        if extended:
            _write_region_ext(out, ext_off + REGION_EXT_SIZE * k, r, blob_ref)

    path_off = _write_paths(out, world.paths, string_ref)

    def mask_for(key):
        names = cell_layers[key]
        return lambda name: 0 if name is None else 1 << names.index(name)

    any_ground = False
    lod_pool = {}               # (band, rows) -> offset of the pooled LOD set
    lod_slots = 0               # placements in cells with a LOD table: the reader's level memory
    entity_numbers = []         # (cell (i, j), k)
    entity_records = []         # offsets
    cell_offs = {}
    for c in cells:
        key = (c.i, c.j)
        names = cell_layers[key]
        if len(names) > MAX_CELL_LAYERS:
            raise PackError(f'cell ({c.i}, {c.j}): more than {MAX_CELL_LAYERS} layers')
        mask_of = mask_for(key)
        cx, cz = (c.i << shift) * ONE + half, (c.j << shift) * ONE + half
        at = out.reserve(CELL_SIZE)
        lod_sets = []
        cell_offs[key] = at
        # placements
        spheres = []
        prec = bytearray()
        placements = [p for p in c.placements if p.ground] + [p for p in c.placements if not p.ground]
        ground_count = sum(1 for p in placements if p.ground)
        any_ground = any_ground or ground_count > 0
        for p in placements:
            pos = _raw3(p.position, 'placement position')
            local = (pos[0] - cx, pos[1], pos[2] - cz)
            if not (-half <= local[0] < half and -half <= local[2] < half):
                raise PackError(f'cell ({c.i}, {c.j}): a placement at {p.position} lies outside its cell')
            cs, sn = _yaw_rows(p.yaw)
            verts = [tuple(fx(x) for x in v) for v in mesh_vertices(p.mesh)]
            if not verts:
                raise PackError('placement mesh has no vertices')
            rows = lod_rows(p.lod) if p.lod is not None else None
            lod_sets.append(rows)
            for r in rows or ():        # the sphere and the overhang hold every level
                if r[3] is not None:
                    verts += [tuple(fx(x) for x in v) for v in mesh_vertices(r[3])]
            pts = [tuple(a + b for a, b in zip(_rotate(v, cs, sn), local)) for v in verts]
            sc, sr = _sphere_of_points(pts)
            reach = max(max(abs(q[0]), abs(q[2])) for q in pts)
            if reach > half + overhang:
                raise PackError(f'cell ({c.i}, {c.j}): a placement overhangs its cell by more '
                                f'than {world.overhang} units')
            spheres.append((sc, sr))
            if p.layer is not None and p.layer not in names:
                raise PackError(f'cell ({c.i}, {c.j}): placement layer {p.layer!r} not in the cell')
            if not 0 <= p.tag <= 0xFFFF:
                raise PackError('placement tag out of range')
            prec += struct.pack('<8i2iIBBH', *sc, sr, *local, 0, cs, sn, 0, mask_of(p.layer),
                                PLACEMENT_GROUND if p.ground else 0, p.tag)
        pl_off = out.put(bytes(prec)) if placements else 0
        for k, p in enumerate(placements):
            mesh_ref(pl_off + PLACEMENT_SIZE * k + 40, p.mesh)
        # levels of detail (1.3): a table of set offsets per placement, sets pooled per pack
        lod_off, lod_first = 0, 0
        if any(r is not None for r in lod_sets):
            lod_off = out.reserve(4 * len(placements))
            lod_first = lod_slots
            lod_slots += len(placements)
            for k, rows in enumerate(lod_sets):
                if rows is None:
                    continue
                band = fx(placements[k].lod.band)
                pool_key = (band, tuple((a, b, d, m) for a, b, d, m in rows))
                if pool_key not in lod_pool:
                    so = out.reserve(LOD_HEAD_SIZE + LOD_LEVEL_SIZE * len(rows))
                    out.patch(so, 'BBHi', len(rows), LOD_CULL if rows[-1][3] is None else 0, 0, band)
                    for q, (a, b, d, m) in enumerate(rows):
                        out.patch(so + LOD_HEAD_SIZE + LOD_LEVEL_SIZE * q, '3iI', a, b, d, 0)
                        mesh_ref(so + LOD_HEAD_SIZE + LOD_LEVEL_SIZE * q + 12, m)
                    lod_pool[pool_key] = so
                out.patch(lod_off + 4 * k, 'I', lod_pool[pool_key])
        bounds = _sphere_of_spheres(spheres) if spheres else ([0, 0, 0], 0)
        sb = ([0, 0, 0], 0)
        if c.standin is not None:
            sv = [tuple(fx(x) for x in v) for v in mesh_vertices(c.standin)]
            if not sv:
                raise PackError('stand-in mesh has no vertices')
            sb = _sphere_of_points(sv)
        # entities
        first = len(entity_numbers)
        en_off = out.reserve(ENTITY_SIZE * len(c.entities)) if c.entities else 0
        for k, e in enumerate(c.entities):
            pos = _raw3(e.position, 'entity position')
            local = (pos[0] - cx, pos[1], pos[2] - cz)
            if not (-half <= local[0] < half and -half <= local[2] < half):
                raise PackError(f'cell ({c.i}, {c.j}): an entity at {e.position} lies outside its cell')
            if e.layer is not None and e.layer not in names:
                raise PackError(f'cell ({c.i}, {c.j}): entity layer {e.layer!r} not in the cell')
            if not 0 <= e.type <= 0xFFFF:
                raise PackError('entity type out of range')
            ea = en_off + ENTITY_SIZE * k
            out.patch(ea, '4iHBBiiIIIII4I', *local, 0, e.type, mask_of(e.layer),
                      FLAG_SAVED if e.saved_bit >= 0 else 0, e.saved_bit,
                      rnd(math.radians(e.yaw) * ONE), 0, 0, 0, len(e.params),
                      len(entity_numbers), at, 0, 0, 0)
            mesh_ref(ea + 28, e.mesh)
            if e.params:
                for o, _ in e.names:
                    if not 0 <= o <= len(e.params) - 4 or o % 4:
                        raise PackError('name parameter offset out of range')
                blob_ref(ea + 36, bytes(e.params), 4, e.names)
            elif e.names:
                raise PackError('name parameters without a parameter record')
            entity_numbers.append(((c.i, c.j), k))
            entity_records.append(ea)
            if e.collision:
                etris = []
                for t in e.collision:
                    v = tuple(_raw3(p, 'entity collision corner') for p in (t.a, t.b, t.c))
                    if t.layer is not None:
                        raise PackError('entity collision triangles take no layer')
                    etris.append((v, t.surface, None, t.tag))
                ext = max(max(abs(p[0]), abs(p[2])) for v, *_ in etris for p in v)
                eh = fx(e.collision_half) if e.collision_half else ((ext + ONE - 1) // ONE + 1) * ONE
                coff = _write_coll(out, etris, eh, pad, None, fc, cc, lambda name: 0)
                out.patch(ea + 32, 'I', coff)
        coll_off = _write_coll(out, cell_tris[key], half, pad, c.grid_shift, fc, cc, mask_of)
        lay = [layer_id[n] for n in names] + [NO_LAYER] * (MAX_CELL_LAYERS - len(names))
        out.patch(at, 'hhHBB8B4i4iIIIIIII5I', c.i, c.j, c.region, len(names), 0, *lay,
                  *bounds[0], bounds[1], *sb[0], sb[1], 0, len(c.placements), pl_off,
                  len(c.entities), en_off, first, coll_off, ground_count, lod_off, lod_first, 0, 0)
        if c.standin is not None:
            mesh_ref(at + 48, c.standin)

    for (i, j), off in cell_offs.items():
        out.patch(index_off + 4 * ((j - j0) * gw + (i - i0)), 'I', off)
    ent_dir = out.put(struct.pack(f'<{len(entity_records)}I', *entity_records)) if entity_records else 0
    mesh_dir = out.reserve(4 * len(mesh_order)) if mesh_order else 0
    for k, m in enumerate(mesh_order):
        meshes[m] = out.put(m, 4)
        out.patch(mesh_dir + 4 * k, 'I', meshes[m])
    for at, m in pending_meshes:
        out.patch(at, 'I', meshes[m])
    for at, data, align, names in blobs:
        off = out.put(data, align)
        out.patch(at, 'I', off)
        for o, text in names:
            string_ref(off + o, text)
    for at, text in pending_strings:
        if text not in strings:
            raw = text.encode('ascii')
            if b'\0' in raw:
                raise PackError('names cannot contain NUL')
            strings[text] = out.put(raw + b'\0', 1)
        out.patch(at, 'I', strings[text])
    out.align(4)
    near_far = fx(world.near_far) if world.near_far is not None else 0
    if world.near_far is not None and not 0 < near_far <= 2048 * ONE:
        raise PackError('near_far must be more than 0 and at most 2048 units')
    out.patch(0, '4sHHIBBHhhHHIiiHHIIIIIIIIiI', MAGIC, VERSION_MAJOR, VERSION_MINOR if extended else MINOR_PLAIN,
              len(out.b), shift, FLAG_GROUND if any_ground else 0, HEADER_SIZE_1_4 if extended else HEADER_SIZE,
              i0, j0, gw, gh, index_off, pad, overhang,
              len(world.regions), len(world.layers), region_off, layer_off,
              len(entity_records), ent_dir, len(mesh_order), mesh_dir, len(world.paths), path_off,
              near_far, lod_slots)
    if extended:
        out.patch(HEADER_SIZE, 'I', ext_off)
    if report is not None:
        report['layers'] = dict(layer_id)
        report['cell_layers'] = {k: list(v) for k, v in cell_layers.items()}
        report['entities'] = entity_numbers
        report['cells'] = dict(cell_offs)
        report['meshes'] = len(mesh_order)
        report['paths'] = {p.name: k for k, p in enumerate(world.paths)}
        report['lod_slots'] = lod_slots
        report['lod_sets'] = len(lod_pool)
    return bytes(out.b)


# ---- the decoder

@dataclass
class Coll:
    off: int
    grid_shift: int
    half: int
    inv: int
    pad: int
    floors: list        # (a, b, c, info, edges[3] (mx, mz, k), ymin, ymax)
    walls: list         # (n (4), edges[3] (ux, uy, uz, k), hx, hz, inv, info)
    ceilings: list
    buckets: list       # (start, nf, nw, nc)
    lists: list         # per bucket: (floor ids, wall ids, ceiling ids)

    def bucket(self, x, z):
        g = 1 << self.grid_shift
        return self.lists[bucket_of(z, self.half, self.inv, g) * g + bucket_of(x, self.half, self.inv, g)]


@dataclass
class DCell:
    off: int
    i: int
    j: int
    region: int
    layers: list
    bounds: tuple
    standin_bounds: tuple
    standin: int
    placements: list    # dicts; a 1.1 pack's ground placements come first ('ground': True)
    entities: list      # dicts
    entity_first: int
    coll: Coll
    ground_count: int = 0


@dataclass
class Pack:
    data: bytes
    major: int
    minor: int
    cell_shift: int
    i0: int
    j0: int
    w: int
    h: int
    pad: int
    overhang: int
    layers: list        # (name, group, on)
    regions: list       # dicts
    cells: dict         # (i, j) -> DCell
    entities: list      # record offsets
    meshes: list        # offsets
    paths: list = field(default_factory=list)   # dicts (1.2): name, flags, surface, lo, hi, length, points
    near_far: int = 0       # (1.3) raw; 0: the reader's default (1.5 cells)
    lod_slots: int = 0      # (1.3)

    def cell_of(self, x, z):
        """(i, j) of the cell holding raw world point (x, z), and its local x and z."""
        i, j = x >> (16 + self.cell_shift), z >> (16 + self.cell_shift)
        half = 1 << (15 + self.cell_shift)
        return (i, j), x - (i << (16 + self.cell_shift)) - half, z - (j << (16 + self.cell_shift)) - half


class _Reader:
    def __init__(self, data):
        self.d = data

    def u(self, fmt, off, what):
        n = struct.calcsize('<' + fmt)
        if off < 0 or off + n > len(self.d):
            raise PackError(f'{what} at {off} runs past the end of the pack')
        return struct.unpack_from('<' + fmt, self.d, off)

    def table(self, off, count, size, what, header_size):
        if count == 0:
            return
        if off % 4 or off < header_size or off + count * size > len(self.d):
            raise PackError(f'{what}: bad offset {off}')

    def string(self, off, what):
        if off == 0:
            return None
        if off >= len(self.d):
            raise PackError(f'{what}: string offset out of range')
        end = self.d.find(b'\0', off)
        if end < 0:
            raise PackError(f'{what}: unterminated string')
        try:
            return self.d[off:end].decode('ascii')
        except UnicodeDecodeError:
            raise PackError(f'{what}: name is not ASCII')

    def blob(self, off, n, what):
        if n == 0:
            return b''
        if off == 0 or off + n > len(self.d):
            raise PackError(f'{what}: data out of range')
        return self.d[off:off + n]


def _decode_coll(r, off, hs):
    if off == 0:
        return None
    r.table(off, 1, COLL_SIZE, 'collision block', hs)
    gs, _, _, half, inv, pad, nf, fo, nw, wo, nc, co, bo, lo = r.u('BBHiii8I', off, 'collision block')
    if gs > MAX_GRID_SHIFT or half <= 0 or inv <= 0 or pad < 0:
        raise PackError('collision block: bad grid')
    r.table(fo, nf, FLAT_SIZE, 'floors', hs)
    r.table(wo, nw, WALL_SIZE, 'walls', hs)
    r.table(co, nc, FLAT_SIZE, 'ceilings', hs)
    g = 1 << gs
    r.table(bo, g * g, BUCKET_SIZE, 'buckets', hs)
    if bo == 0:
        raise PackError('collision block: no buckets')

    def flat(o):
        v = r.u('3iI12i', o, 'flat')
        return (v[0], v[1], v[2], v[3], ((v[4], v[5], v[6]), (v[8], v[9], v[10]), (v[12], v[13], v[14])),
                v[7], v[11])

    def wall(o):
        v = r.u('19iI', o, 'wall')
        return (v[0:4], (v[4:8], v[8:12], v[12:16]), v[16], v[17], v[18], v[19])

    floors = [flat(fo + FLAT_SIZE * k) for k in range(nf)]
    walls = [wall(wo + WALL_SIZE * k) for k in range(nw)]
    ceilings = [flat(co + FLAT_SIZE * k) for k in range(nc)]
    buckets, lists = [], []
    total = 0
    for k in range(g * g):
        start, bf, bw, bc, _ = r.u('I4B', bo + BUCKET_SIZE * k, 'bucket')
        buckets.append((start, bf, bw, bc))
        total = max(total, start + bf + bw + bc)
    if total:
        r.table(lo, total, 2, 'lookup list', hs)
        if lo == 0:
            raise PackError('collision block: no lookup list')
    for start, bf, bw, bc in buckets:
        ids = list(r.u(f'{bf + bw + bc}H', lo + 2 * start, 'lookup list')) if bf + bw + bc else []
        f, w, c = ids[:bf], ids[bf:bf + bw], ids[bf + bw:]
        if any(x >= nf for x in f) or any(x >= nw for x in w) or any(x >= nc for x in c):
            raise PackError('lookup list names a triangle that does not exist')
        lists.append((f, w, c))
    return Coll(off, gs, half, inv, pad, floors, walls, ceilings, buckets, lists)


def decode(data):
    """Parses and validates a pack. Raises PackError for anything a reader must refuse."""
    data = bytes(data)
    r = _Reader(data)
    if len(data) < 16 or data[:4] != MAGIC:
        raise PackError('not a world pack (no MEIW magic)')
    major, minor, size = r.u('HHI', 4, 'header')
    if major != VERSION_MAJOR:
        raise PackError(f'pack version {major}.{minor}: this reader reads {VERSION_MAJOR}.x')
    if size != len(data) or size % 4:
        raise PackError(f'pack size field {size} does not match its {len(data)} bytes')
    (shift, flags, hs, i0, j0, gw, gh, index_off, pad, overhang, nreg, nlay, reg_off, lay_off,
     nent, ent_dir, nmesh, mesh_dir) = r.u('BBHhhHHIiiHHIIIIII', 12, 'header')
    if flags & FLAGS_REQUIRED:
        raise PackError(f'pack needs features this reader lacks (header flags {flags:#x})')
    if hs < MIN_HEADER_SIZE or hs % 4 or hs > size:
        raise PackError('bad header size')
    if not MIN_CELL_SHIFT <= shift <= MAX_CELL_SHIFT:
        raise PackError(f'cell shift {shift} out of range')
    if gw == 0 or gh == 0:
        raise PackError('empty grid')
    half = 1 << (15 + shift)
    if pad < 0 or pad > half or overhang < 0 or overhang > half:
        raise PackError('bad collision pad or overhang')
    r.table(index_off, gw * gh, 4, 'index', hs)
    r.table(lay_off, nlay, LAYER_SIZE, 'layers', hs)
    r.table(reg_off, nreg, REGION_SIZE, 'regions', hs)
    r.table(ent_dir, nent, 4, 'entity directory', hs)
    r.table(mesh_dir, nmesh, 4, 'mesh directory', hs)
    if nreg == 0:
        raise PackError('no regions')
    paths = _decode_paths(r, minor, hs)
    near_far, lod_slots = 0, 0
    if minor >= 3:
        if hs < HEADER_SIZE:
            raise PackError(f'a 1.{minor} header is at least {HEADER_SIZE} bytes')
        near_far, lod_slots = r.u('iI', 72, 'header')
        if near_far < 0 or near_far > 2048 * ONE:
            raise PackError('bad near_far')
    layers = []
    for k in range(nlay):
        no, grp, fl, _ = r.u('IBBH', lay_off + LAYER_SIZE * k, 'layer')
        layers.append((r.string(no, 'layer'), grp, bool(fl & 1)))
    regions = []
    for k in range(nreg):
        at = reg_off + REGION_SIZE * k
        no, ntex, nsmp, to, so, nvar, ncol, first, nbd, po, bo = r.u('IHHIIHHHHII', at, 'region')
        r.table(to, ntex, TEXTURE_SIZE, 'textures', hs)
        r.table(so, nsmp, SAMPLE_SIZE, 'samples', hs)
        r.table(bo, nbd, VRAM_COPY_SIZE, 'backdrop', hs)
        texs = []
        for t in range(ntex):
            slot, fl, _, do, n = r.u('BBHII', to + TEXTURE_SIZE * t, 'texture')
            if slot > 15:
                raise PackError('texture slot out of range')
            texs.append(Texture(slot, r.blob(do, n, 'texture'), bool(fl & 1)))
        smps = []
        for s in range(nsmp):
            sn, do, ns, ls, fl = r.u('5I', so + SAMPLE_SIZE * s, 'sample')
            smps.append(Sample(r.string(sn, 'sample'), None, ns, ls, fl))
            smps[-1].offset = do
        variants = []
        if nvar:
            if first + ncol > 4096:
                raise PackError('palette runs past colour 4095')
            r.table(po, nvar, 4, 'palette variants', hs)
            names = [r.string(r.u('I', po + 4 * v, 'variant')[0], 'variant') for v in range(nvar)]
            base = po + 4 * nvar
            for v in range(nvar):
                variants.append((names[v], list(r.u(f'{ncol}H', base + 2 * ncol * v, 'palette'))))
        bds = []
        for b in range(nbd):
            addr, do, n = r.u('3I', bo + VRAM_COPY_SIZE * b, 'backdrop copy')
            bds.append(VramCopy(addr, r.blob(do, n, 'backdrop copy')))
        regions.append(Region(r.string(no, 'region'), texs, first, variants, smps, bds))
    if minor >= 4:
        if hs < HEADER_SIZE_1_4:
            raise PackError(f'a 1.{minor} header is at least {HEADER_SIZE_1_4} bytes')
        ext_off = r.u('I', HEADER_SIZE, 'header')[0]
        if ext_off:
            r.table(ext_off, nreg, REGION_EXT_SIZE, 'region extensions', hs)
            for k, reg in enumerate(regions):
                _decode_region_ext(r, ext_off + REGION_EXT_SIZE * k, reg, hs)

    meshes = []
    for k in range(nmesh):
        mo = r.u('I', mesh_dir + 4 * k, 'mesh directory')[0]
        if mo % 4 or mo < hs or mo >= size:
            raise PackError('mesh offset out of range')
        mesh_info(data[mo:], f'mesh at {mo}')
        meshes.append(mo)

    def mesh_at(mo, what):
        if mo == 0:
            return 0
        if mo % 4 or mo < hs or mo >= size:
            raise PackError(f'{what}: mesh offset out of range')
        mesh_info(data[mo:], f'{what} mesh')
        return mo

    cells = {}
    for k in range(gw * gh):
        co = r.u('I', index_off + 4 * k, 'index')[0]
        if co == 0:
            continue
        r.table(co, 1, CELL_SIZE, 'cell', hs)
        v = r.u('hhHBB8B4i4iIIIIIII5I', co, 'cell')
        ci, cj, reg, nl, _ = v[0:5]
        lay = list(v[5:5 + nl])
        if (cj - j0) * gw + (ci - i0) != k:
            raise PackError(f'cell ({ci}, {cj}) is filed at the wrong index entry')
        if reg >= nreg:
            raise PackError(f'cell ({ci}, {cj}): no region {reg}')
        if nl > MAX_CELL_LAYERS or any(x >= nlay for x in lay):
            raise PackError(f'cell ({ci}, {cj}): bad layer list')
        bounds = v[13:17]
        sbounds = v[17:21]
        sto, npl, plo, nen, eno, efirst, collo = v[21:28]
        nground = v[28] if minor >= 1 else 0        # reserved (ignored) in 1.0
        if nground > npl:
            raise PackError(f'cell ({ci}, {cj}): more ground placements than placements')
        r.table(plo, npl, PLACEMENT_SIZE, 'placements', hs)
        r.table(eno, nen, ENTITY_SIZE, 'entities', hs)
        lmask = (1 << nl) - 1
        pls = []
        for p in range(npl):
            pv = r.u('8i2iIBBH', plo + PLACEMENT_SIZE * p, 'placement')
            if pv[11] & ~lmask or bin(pv[11]).count('1') > 1:
                raise PackError(f'cell ({ci}, {cj}): bad placement layer mask')
            if pv[10] == 0:
                raise PackError(f'cell ({ci}, {cj}): a placement has no mesh')
            ground = minor >= 1 and bool(pv[12] & PLACEMENT_GROUND)
            if ground != (p < nground):
                raise PackError(f'cell ({ci}, {cj}): the ground placements are not the first {nground}')
            pls.append(dict(sphere=pv[0:4], pos=pv[4:7], cos=pv[8], sin=pv[9],
                            mesh=mesh_at(pv[10], 'placement'), mask=pv[11], tag=pv[13], ground=ground, lod=None))
        lod_off, lod_first = (v[29], v[30]) if minor >= 3 else (0, 0)
        if lod_off:
            r.table(lod_off, npl, 4, f'cell ({ci}, {cj}) LOD table', hs)
            if npl == 0 or lod_first + npl > lod_slots:
                raise PackError(f'cell ({ci}, {cj}): LOD slots out of range')
            for p in range(npl):
                so = r.u('I', lod_off + 4 * p, 'LOD table')[0]
                if so:
                    pls[p]['lod'] = _decode_lod(r, so, hs, mesh_at)
                    pls[p]['lod_field'] = lod_off + 4 * p
                    pls[p]['lod_slot'] = lod_first + p
        ens = []
        for e in range(nen):
            ea = eno + ENTITY_SIZE * e
            ev = r.u('4iHBBiiIIIII4I', ea, 'entity')
            if ev[5] & ~lmask:
                raise PackError(f'cell ({ci}, {cj}): bad entity layer mask')
            if ev[14] != co or ev[13] != efirst + e:
                raise PackError(f'cell ({ci}, {cj}): entity back-references disagree')
            ens.append(dict(off=ea, pos=ev[0:3], type=ev[4], mask=ev[5], flags=ev[6], saved_bit=ev[7],
                            yaw=ev[8], mesh=mesh_at(ev[9], 'entity'), coll=_decode_coll(r, ev[10], hs),
                            params=r.blob(ev[11], ev[12], 'entity parameters'), number=ev[13]))
        coll = _decode_coll(r, collo, hs)
        if coll is not None and coll.half != half:
            raise PackError(f'cell ({ci}, {cj}): collision grid is not the cell square')
        cells[(ci, cj)] = DCell(co, ci, cj, reg, lay, bounds, sbounds, mesh_at(sto, 'stand-in'), pls, ens,
                                efirst, coll, nground)
    if minor >= 1 and bool(flags & FLAG_GROUND) != any(c.ground_count for c in cells.values()):
        raise PackError('the header\'s ground flag disagrees with the cells')
    ents = []
    for k in range(nent):
        eo = r.u('I', ent_dir + 4 * k, 'entity directory')[0]
        ents.append(eo)
    by_off = {e['off']: e for c in cells.values() for e in c.entities}
    for k, eo in enumerate(ents):
        if eo not in by_off or by_off[eo]['number'] != k:
            raise PackError('entity directory disagrees with the cells')
    if len(by_off) != nent:
        raise PackError('entity count disagrees with the cells')
    return Pack(data, major, minor, shift, i0, j0, gw, gh, pad, overhang, layers, regions, cells,
                ents, meshes, paths, near_far, lod_slots)


def _write_region_ext(out, at, r, blob_ref):
    """(1.4) A region's extension record: palette runs, animated textures and the sky record."""
    nvar = len(r.variants)
    if r.runs and not nvar:
        raise PackError(f'region {r.name!r}: palette runs need the region\'s palette variants')
    run_off = out.reserve(RUN_SIZE * len(r.runs)) if r.runs else 0
    for q, run in enumerate(r.runs):
        n = len(run.variants[0]) if run.variants else 0
        if len(run.variants) != nvar or any(len(v) != n for v in run.variants) or not 0 < n <= 256 \
                or run.first_colour + n > 4096:
            raise PackError(f'region {r.name!r}: a palette run needs 1-256 colours for each palette variant')
        out.patch(run_off + RUN_SIZE * q, 'HHI', run.first_colour, n, 0)
        blob_ref(run_off + RUN_SIZE * q + 4, b''.join(struct.pack(f'<{n}H', *v) for v in run.variants))
    anim_off = out.reserve(ANIM_SIZE * len(r.animations)) if r.animations else 0
    for q, a in enumerate(r.animations):
        if not (1 <= a.frames <= 0xFFFF and 1 <= a.ticks <= 255 and a.rows >= 1 and 1 <= a.row_bytes <= a.stride
                and len(a.data) == a.frames * a.rows * a.row_bytes and a.stride in (128, 256)
                and (a.vram % a.stride) + a.row_bytes <= a.stride and 0 <= a.vram
                and a.vram + (a.rows - 1) * a.stride + a.row_bytes <= 16 * 32768):
            raise PackError(f'region {r.name!r}: bad animated texture')
        out.patch(anim_off + ANIM_SIZE * q, 'II6H', 0, a.vram, a.frames, a.ticks, a.row_bytes, a.rows, a.stride, 0)
        blob_ref(anim_off + ANIM_SIZE * q, a.data)
    sky_off = 0
    if r.sky:
        s = r.sky
        n = len(s.elevations)
        if not 1 <= n <= 64 or len(s.colours) != max(nvar, 1) or any(len(c) != n for c in s.colours):
            raise PackError(f'region {r.name!r}: a sky needs 1-64 stops and one colour list per palette variant')
        raw = [e if isinstance(e, int) else fx(e) for e in s.elevations]
        if any(b <= a for a, b in zip(raw, raw[1:])):
            raise PackError(f'region {r.name!r}: sky elevations must increase')
        sky_off = out.reserve(SKY_SIZE)
        out.patch(sky_off, 'IIIihhHHII', s.mode, s.atlas, s.map, fx(s.rate), s.horizon, s.top, s.height, n,
                  SKY_SILHOUETTE if s.height else 0, 0)
        blob_ref(sky_off + 28, struct.pack(f'<{n}i', *raw) + b''.join(struct.pack(f'<{n}I', *c) for c in s.colours))
    out.patch(at, 'HHIII4I', len(r.runs), len(r.animations), run_off, anim_off, sky_off, 0, 0, 0, 0)


def _decode_region_ext(r, at, reg, hs):
    nrun, nanim, run_off, anim_off, sky_off = r.u('HHIII', at, 'region extension')
    nvar = len(reg.variants)
    r.table(run_off, nrun, RUN_SIZE, 'palette runs', hs)
    r.table(anim_off, nanim, ANIM_SIZE, 'animated textures', hs)
    for q in range(nrun):
        first, n, do = r.u('HHI', run_off + RUN_SIZE * q, 'palette run')
        if n == 0 or n > 256 or first + n > 4096 or not nvar:
            raise PackError('palette run: bad colours, or a region without palette variants')
        r.blob(do, 2 * n * nvar, 'palette run')
        reg.runs.append(PaletteRun(first, [list(r.u(f'{n}H', do + 2 * n * v, 'palette run')) for v in range(nvar)]))
    for q in range(nanim):
        do, vram, frames, ticks, rb, rows, stride, _ = r.u('II6H', anim_off + ANIM_SIZE * q, 'animated texture')
        if frames == 0 or rows == 0 or not 1 <= ticks <= 255 or stride not in (128, 256) or not 1 <= rb <= stride:
            raise PackError('animated texture: bad fields')
        if (vram % stride) + rb > stride or vram + (rows - 1) * stride + rb > 16 * 32768:
            raise PackError('animated texture: its tile runs past the texture area')
        reg.animations.append(Animation(r.blob(do, frames * rows * rb, 'animated texture'), frames, ticks, rb, rows,
                                        vram, stride))
    if sky_off:
        r.table(sky_off, 1, SKY_SIZE, 'sky', hs)
        mode, atlas, mp, rate, horizon, top, height, n, flags, do = r.u('IIIihhHHII', sky_off, 'sky')
        if not 1 <= n <= 64 or bool(flags & SKY_SILHOUETTE) != bool(height):
            raise PackError('sky: bad stops or silhouette')
        raw = list(r.u(f'{n}i', do, 'sky stops'))
        if any(b <= a for a, b in zip(raw, raw[1:])):
            raise PackError('sky: elevations do not increase')
        cols = [list(r.u(f'{n}I', do + 4 * n * (1 + v), 'sky colours')) for v in range(max(nvar, 1))]
        reg.sky = Sky(raw, cols, mode, atlas, mp, rate / ONE, horizon, top, height)


def _decode_lod(r, so, hs, mesh_at):
    """A LOD set (1.3): {'off', 'band', 'cull', 'rows': [(at2, out2, in2, mesh offset)]}."""
    r.table(so, 1, LOD_HEAD_SIZE, 'LOD set', hs)
    n, flags, _, band = r.u('BBHi', so, 'LOD set')
    if not 1 <= n <= MAX_LOD_LEVELS or band < 0:
        raise PackError('LOD set: bad level count or band')
    r.table(so, 1, LOD_HEAD_SIZE + LOD_LEVEL_SIZE * n, 'LOD set', hs)
    rows = []
    prev_out = -1
    for q in range(n):
        at2, out2, in2, mo = r.u('3iI', so + LOD_HEAD_SIZE + LOD_LEVEL_SIZE * q, 'LOD level')
        last_cull = flags & LOD_CULL and q == n - 1
        if (mo == 0) != bool(last_cull):
            raise PackError('LOD set: a level without a mesh that is not the cull mark')
        if not prev_out < in2 <= at2 <= out2:
            raise PackError('LOD set: switch distances out of order')
        prev_out = out2
        rows.append((at2, out2, in2, mesh_at(mo, 'LOD level')))
    return {'off': so, 'band': band, 'cull': bool(flags & LOD_CULL), 'rows': rows}


def _decode_paths(r, minor, hs):
    """The path table of a 1.2 pack (none before 1.2), validated: names, point tables, and that
    every point record agrees with the next (s and len add up, the last has no segment, a closed
    path ends where it starts, the box holds every point)."""
    if minor < 2:
        return []
    if hs < HEADER_SIZE_1_2:
        raise PackError(f'a 1.{minor} header is at least {HEADER_SIZE_1_2} bytes')
    count, table = r.u('II', 64, 'header')
    r.table(table, count, PATH_SIZE, 'paths', hs)
    if count and table == 0:
        raise PackError('paths: no table')
    out, names = [], set()
    for k in range(count):
        v = r.u('IIIBBH4i4i', table + PATH_SIZE * k, 'path')
        name = r.string(v[0], 'path')
        if not name or name in names:
            raise PackError(f'path {k}: missing or repeated name')
        names.add(name)
        npt, po, flags, surface = v[1], v[2], v[3], v[4]
        lo, length, hi = v[6:9], v[9], v[10:13]
        if npt < 2 or npt > MAX_PATH_POINTS:
            raise PackError(f'path {name!r}: {npt} points')
        if po == 0:
            raise PackError(f'path {name!r}: no points')
        r.table(po, npt, PATH_POINT_SIZE, f'path {name!r} points', hs)
        pts = []
        s = 0
        for q in range(npt):
            pv = r.u('4i4i2i', po + PATH_POINT_SIZE * q, 'path point')
            pos, u, ps, ln = pv[0:3], pv[4:7], pv[8], pv[9]
            last = q == npt - 1
            if ps != s or (ln <= 0) != last or (last and (ln or any(u))):
                raise PackError(f'path {name!r}: point {q} disagrees with its neighbours')
            if any(not lo[i] <= pos[i] <= hi[i] for i in range(3)):
                raise PackError(f'path {name!r}: point {q} lies outside its box')
            s += ln
            pts.append(dict(pos=pos, dir=u, s=ps, len=ln))
        if length != s or length > MAX_PATH_LENGTH * ONE:
            raise PackError(f'path {name!r}: bad length')
        if flags & PATH_CLOSED and (npt < 4 or pts[0]['pos'] != pts[-1]['pos']):
            raise PackError(f'path {name!r}: a closed path ends where it starts')
        out.append(dict(name=name, flags=flags, surface=surface, raised=bool(flags & PATH_RAISED),
                        closed=bool(flags & PATH_CLOSED), lo=lo, hi=hi, length=length, points=pts))
    return out


# ---- entity parameter records

_PARAM = {'bool': ('B', 1), 'u8': ('B', 1), 'enum': ('B', 1), 's16': ('h', 2), 's32': ('i', 4),
          'fixed': ('i', 4), 'name': ('I', 4), 'entity_ref': ('I', 4), 'world_ref': ('I', 4),
          'vec3': ('4i', 4)}


def pack_params(fields):
    """A parameter record laid out as an Akari struct with the same fields in order (natural
    alignment, vec3 as 16 bytes with w = 0, size padded to its alignment). fields is a list of
    (type, value); fixed and vec3 values are in units."""
    out = bytearray()
    align = 1
    for t, v in fields:
        if t not in _PARAM:
            raise PackError(f'unknown parameter type {t!r}')
        fmt, al = _PARAM[t]
        align = max(align, al)
        while len(out) % al:
            out.append(0)
        if t == 'fixed':
            v = fx(v)
        elif t == 'vec3':
            v = [fx(c) for c in v] + [0]
        elif t == 'bool':
            v = 1 if v else 0
        out += struct.pack('<' + fmt, *(v if isinstance(v, list) else [v]))
    while len(out) % align:
        out.append(0)
    return bytes(out)


# ---- the exact oracle

def _side2(p, q, x, z):
    return (q[0] - p[0]) * (z - p[2]) - (q[2] - p[2]) * (x - p[0])


class Oracle:
    """The reader's queries over a world's quantized triangles in exact rational arithmetic.
    Coordinates are raw 16.16 integers (world). Each answer carries `margin`: the smallest
    distance (units, approximate) by which any decision it made (inside an edge or not, below
    the limit or not, which of two surfaces is nearer) could change; when the margin is larger
    than the console's rounding, the console must make the same decisions."""

    def __init__(self, world):
        self.tris = world_triangles(world)
        self.by_tag = {}
        for t in self.tris:
            self.by_tag.setdefault(t['tag'], t)

    @classmethod
    def from_tris(cls, tris, floor_max_degrees=45.0, ceiling_max_degrees=45.0):
        """An oracle over Tri corners in one frame (an entity's collision, say)."""
        return cls(World(cells=[Cell(0, 0, collision=list(tris))], floor_max_degrees=floor_max_degrees,
                         ceiling_max_degrees=ceiling_max_degrees))

    @staticmethod
    def _active(t, layers_on):
        return t['layer'] is None or t['layer'] in layers_on

    @staticmethod
    def _xz_margin(v, x, z):
        """Signed distance (units) of (x, z) from the triangle's XZ outline: positive inside."""
        orient = _side2(v[0], v[1], v[2][0], v[2][2])
        best = None
        for e in range(3):
            p, q = v[e], v[(e + 1) % 3]
            s = _side2(p, q, x, z) * (1 if orient > 0 else -1)
            d = s / math.hypot(q[0] - p[0], q[2] - p[2]) / ONE
            best = d if best is None else min(best, d)
        return best

    @staticmethod
    def _height(t, x, z):
        n, p = t['n'], t['v'][0]
        return Fraction(p[1]) - Fraction(n[0] * (x - p[0]) + n[2] * (z - p[2]), n[1])

    def _flat(self, kind, p, lim_off, layers_on, pick_max):
        x, y, z = p
        lim = y + lim_off
        margin = float('inf')
        cands = []
        for t in self.tris:
            if t['kind'] != kind or not self._active(t, layers_on):
                continue
            m = self._xz_margin(t['v'], x, z)
            margin = min(margin, abs(m))
            if m < 0:
                continue
            h = self._height(t, x, z)
            margin = min(margin, abs(float(h - lim)) / ONE)
            if (h <= lim) if pick_max else (h >= lim):
                cands.append((h, t))
        if not cands:
            return None, margin
        cands.sort(key=lambda c: c[0], reverse=pick_max)
        if len(cands) > 1:          # a tie (0) is ambiguous: the reader takes the first filed
            margin = min(margin, abs(float(cands[0][0] - cands[1][0])) / ONE)
        return cands[0], margin

    def floor(self, p, above, layers_on=()):
        """(height raw Fraction, triangle dict) or None for the highest floor under raw point p
        at or below p.y + above; and the margin."""
        return self._flat(KIND_FLOOR, p, above, set(layers_on), True)

    def ceiling(self, p, below, layers_on=()):
        return self._flat(KIND_CEILING, p, -below, set(layers_on), False)

    @staticmethod
    def _wall_terms(t, q):
        """Exact signed plane distance (raw) and the smallest in-plane edge margin (units)."""
        n, v = t['n'], t['v']
        nl = math.sqrt(dot3(n, n))
        dist = Fraction(dot3(n, sub3(q, v[0]))) / Fraction(nl)    # nl irrational: float ratio
        best = None
        for e in range(3):
            a, b, c = v[e], v[(e + 1) % 3], v[(e + 2) % 3]
            d = sub3(b, a)
            u = cross3(n, d)
            s = dot3(u, sub3(c, a))
            val = dot3(u, sub3(q, a)) * (1 if s > 0 else -1)
            # the projection's distance from the edge, in units
            em = float(val) / math.sqrt(dot3(u, u)) / ONE
            best = em if best is None else min(best, em)
        return dist, best

    def push(self, p, radius, order, layers_on=()):
        """Wall push-out as the reader does it: walls in `order` (tags), each tested at the
        position the earlier ones left. Returns (x, z) raw floats, walls pushed, margin."""
        layers_on = set(layers_on)
        x, y, z = (float(c) for c in p)
        margin = float('inf')
        count = 0
        for tag in order:
            t = self.by_tag[tag]
            if not self._active(t, layers_on):
                continue
            n = t['n']
            dist, em = self._wall_terms(t, (Fraction(x), Fraction(y), Fraction(z)))
            dist = float(dist)
            margin = min(margin, abs(dist + radius) / ONE, abs(dist - radius) / ONE)
            if dist <= -radius or dist >= radius:
                continue
            margin = min(margin, abs(em))
            if em < 0:
                continue
            h = math.hypot(n[0], n[2])
            nl = math.sqrt(dot3(n, n))
            amount = (radius - dist) * nl / h
            x += n[0] / h * amount
            z += n[2] / h * amount
            count += 1
        return (x, z), count, margin

    def ray(self, a, b, layers_on=()):
        """The first triangle the segment a -> b (raw) crosses, not counting one it starts on:
        (t Fraction, triangle, how far the segment moves across its plane in units) or None,
        and the margin."""
        layers_on = set(layers_on)
        margin = float('inf')
        hits = []
        seg = math.sqrt(sum(float(b[k] - a[k]) ** 2 for k in range(3))) / ONE
        for t in self.tris:
            if not self._active(t, layers_on):
                continue
            n, v = t['n'], t['v']
            fa = dot3(n, sub3(a, v[0]))
            fb = dot3(n, sub3(b, v[0]))
            nl = math.sqrt(dot3(n, n))
            if t['kind'] == KIND_WALL:
                da, db = fa / nl / ONE, fb / nl / ONE
            else:       # the reader compares heights: vertical distances
                da, db = fa / abs(n[1]) / ONE, fb / abs(n[1]) / ONE
            crosses = (fa > 0 and fb <= 0) or (fa < 0 and fb >= 0)
            tt = Fraction(fa, fa - fb) if fa != fb else None
            df = abs(da - db)
            if tt is not None and 0 <= tt <= 1:
                q = tuple(a[k] + (b[k] - a[k]) * tt for k in range(3))
                if t['kind'] == KIND_WALL:
                    _, em = self._wall_terms(t, q)
                else:
                    em = self._xz_margin(v, q[0], q[2])
                margin = min(margin, abs(da), abs(db), abs(em))
                if crosses and em >= 0:
                    hits.append((tt, t, df))
            else:
                margin = min(margin, abs(da), abs(db))
        if not hits:
            return None, margin
        hits.sort(key=lambda h: h[0])
        if len(hits) > 1:
            margin = min(margin, float(hits[1][0] - hits[0][0]) * seg)
        return hits[0], margin


# ---- paths, exactly

def path_nearest(path, p, reach):
    """What wp_path_nearest() answers, in exact rational arithmetic over a decoded path's records
    (decode(...).paths[k]): the nearest point to raw point p on any segment whose nearest point
    lies within reach (units) of p in each of x, y and z. Returns ((segment, t, s, point,
    squared distance), margin) in units (Fractions), or (None, margin); margin is how far (units)
    the answer is from changing: from the reach box, or from a second segment as near."""
    q = [Fraction(c, ONE) for c in p]
    reach = Fraction(reach)
    margin = float('inf')
    best = second = None
    for k, rec in enumerate(path['points'][:-1]):
        pos = [Fraction(c, ONE) for c in rec['pos']]
        u = [Fraction(c, ONE) for c in rec['dir']]
        d = [q[i] - pos[i] for i in range(3)]
        t = min(max(sum(d[i] * u[i] for i in range(3)), Fraction(0)), Fraction(rec['len'], ONE))
        c = [pos[i] + u[i] * t for i in range(3)]
        e = [q[i] - c[i] for i in range(3)]
        margin = min(margin, min(abs(abs(x) - reach) for x in e))
        if any(abs(x) >= reach for x in e):
            continue
        d2 = sum(x * x for x in e)
        cand = (d2, k, t, Fraction(rec['s'], ONE) + t, tuple(c))
        if best is None or d2 < best[0]:
            best, second = cand, best
        elif second is None or d2 < second[0]:
            second = cand
    if best is None:
        return None, margin
    if second is not None:
        margin = min(margin, float(second[0] - best[0]) / (2 * math.sqrt(max(float(second[0]), 1e-12))))
    d2, k, t, s, c = best
    return (k, t, s, c, d2), margin


def path_at(path, s):
    """What wp_path_at() answers: (segment, point) at arc length s (units) along a decoded path;
    a closed path wraps s, an open one clamps it to its ends."""
    s = Fraction(s)
    total = Fraction(path['length'], ONE)
    if path['closed']:
        s -= total * math.floor(s / total)
    s = min(max(s, Fraction(0)), total)
    pts = path['points']
    k = 0
    while k + 1 < len(pts) - 1 and Fraction(pts[k + 1]['s'], ONE) <= s:
        k += 1
    rec = pts[k]
    t = s - Fraction(rec['s'], ONE)
    return k, tuple(Fraction(rec['pos'][i], ONE) + Fraction(rec['dir'][i], ONE) * t for i in range(3))
