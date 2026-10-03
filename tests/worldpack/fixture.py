"""Worlds, query lists and a cart runner for tests/test_worldpack.py.

The worlds are described here by hand (boxes, ramps, a heightfield, random triangles), packed
with tools/worldkit/pack.py at test time and embedded into the carts in this directory through
a generated wrapper. Nothing generated is committed.
"""
import math
import os
from pathlib import Path
import random
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from worldkit.pack import (World, Cell, Placement, Tri, Entity, Layer, Region, Texture, VramCopy,
                           Sample, encode, decode, pack_params, mesh_triangles, fx, ONE)  # noqa: E402
import meshlib  # noqa: E402

HERE = Path(__file__).resolve().parent
COMPILER = Path(os.environ.get('MEIC', ROOT / 'build/meic')).resolve()
RUNNER = Path(os.environ.get('RUN', ROOT / 'build/mei-headless')).resolve()


def tools_built():
    return COMPILER.exists() and RUNNER.exists()


# ---- meshes and their collision

def _face(m, corners, colour, centre):
    """A quad from four corners in cyclic order, wound so its front faces away from centre."""
    a, b, c, d = corners
    ux = [d[k] - a[k] for k in range(3)]
    vx = [b[k] - a[k] for k in range(3)]
    n = (ux[1] * vx[2] - ux[2] * vx[1], ux[2] * vx[0] - ux[0] * vx[2], ux[0] * vx[1] - ux[1] * vx[0])
    fc = [sum(p[k] for p in corners) / 4 for k in range(3)]
    if sum(n[k] * (fc[k] - centre[k]) for k in range(3)) < 0:
        a, b, c, d = a, d, c, b
    idx = [m.vertex(*p) for p in (a, b, d, c)]          # strip order
    m.quad(idx, [colour])


def box_mesh(lo, hi, colour):
    """A closed box between corners lo and hi (in the mesh's own frame)."""
    m = meshlib.Mesh()
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    ctr = [(lo[k] + hi[k]) / 2 for k in range(3)]
    for corners in (
            [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
            [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
            [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
            [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
            [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
            [(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)]):
        _face(m, corners, colour, ctr)
    return m.pack()


def ramp_mesh(x0, x1, z0, z1, h, colour):
    """A wedge rising from y 0 at x0 to y h at x1 (its slope, two sides and the back)."""
    m = meshlib.Mesh()
    ctr = ((x0 + 2 * x1) / 3, h / 3, (z0 + z1) / 2)
    _face(m, [(x0, 0, z0), (x1, h, z0), (x1, h, z1), (x0, 0, z1)], colour, ctr)
    _face(m, [(x1, 0, z0), (x1, h, z0), (x1, h, z1), (x1, 0, z1)], colour, ctr)
    for z in (z0, z1):
        ia, ib, ic = m.vertex(x0, 0, z), m.vertex(x1, 0, z), m.vertex(x1, h, z)
        # wind each side triangle away from the centre
        a, b, c = (x0, 0, z), (x1, 0, z), (x1, h, z)
        n = ((c[1] - a[1]) * (b[2] - a[2]) - (c[2] - a[2]) * (b[1] - a[1]),
             (c[2] - a[2]) * (b[0] - a[0]) - (c[0] - a[0]) * (b[2] - a[2]),
             (c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0]))
        if n[2] * (z - ctr[2]) > 0:
            m.tri([ia, ib, ic], [colour])
        else:
            m.tri([ia, ic, ib], [colour])
    return m.pack()


def ground_mesh(size, tiles, colours):
    """A square floor of tiles x tiles quads centred on the origin at y 0, facing up."""
    m = meshlib.Mesh()
    step = size / tiles
    for tz in range(tiles):
        for tx in range(tiles):
            x0, z0 = -size / 2 + tx * step, -size / 2 + tz * step
            _face(m, [(x0, 0, z0), (x0 + step, 0, z0), (x0 + step, 0, z0 + step), (x0, 0, z0 + step)],
                  colours[(tx + tz) % len(colours)], (x0 + step / 2, -1, z0 + step / 2))
    return m.pack()


def placed_tris(mesh, pos, surface=0, layer=None, tag=0xFFFF):
    """The mesh's faces as collision triangles at world position pos (no yaw)."""
    out = []
    for a, b, c in mesh_triangles(mesh):
        out.append(Tri(*[tuple(float(p[k]) + pos[k] for k in range(3)) for p in (a, b, c)],
                       surface=surface, layer=layer, tag=tag))
    return out


# ---- the demonstration world (cell size 64)

MAGENTA = meshlib.rgb(255, 0, 255)
GATE_BLUE = meshlib.rgb(0, 0, 255)
SURF_GROUND, SURF_RAMP, SURF_BLOCK, SURF_ROOF, SURF_GATE, SURF_STEEP, SURF_PLATFORM = 1, 2, 3, 4, 5, 6, 7
T_COIN, T_SWITCH, T_PLATFORM = 1, 2, 3


def demo_world(cell_shift=6):
    """A few cells with floors, a ramp, a block, a roof, a steep and a gentle slope, a gate in a
    layer, two exclusive bridge layers, coins, a switch and a moving platform; and a far cell
    whose stand-in is magenta."""
    S = 1 << cell_shift
    assert S == 64, 'the demonstration world is laid out for 64-unit cells'
    ground = ground_mesh(S, 8, [meshlib.rgb(60, 140, 60), meshlib.rgb(70, 160, 70)])
    grey = box_mesh((-4, 0, -4), (4, 30, 4), meshlib.rgb(120, 120, 120))
    near_standin = box_mesh((-30, 0, -30), (30, 2, 30), meshlib.rgb(90, 110, 90))
    cells = {}
    for i, j in ((0, 0), (1, 0), (0, 1), (1, 1)):
        c = Cell(i, j, standin=near_standin)
        centre = (i * S + S / 2, 0, j * S + S / 2)
        c.placements.append(Placement(ground, centre, tag=1))
        c.collision += placed_tris(ground, centre, SURF_GROUND, tag=1)
        cells[(i, j)] = c
    c00 = cells[(0, 0)]
    ramp = ramp_mesh(0, 8, 0, 8, 4, meshlib.rgb(200, 160, 80))
    c00.placements.append(Placement(ramp, (20, 0, 40), tag=2))       # x 20..28 rises 0..4
    c00.collision += placed_tris(ramp, (20, 0, 40), SURF_RAMP, tag=2)
    plat = box_mesh((0, 0, 0), (8, 4, 8), meshlib.rgb(200, 160, 80))
    c00.placements.append(Placement(plat, (28, 0, 40), tag=3))       # top at y 4
    c00.collision += placed_tris(plat, (28, 0, 40), SURF_RAMP, tag=3)
    block = box_mesh((0, 0, 0), (4, 6, 16), meshlib.rgb(150, 80, 60))
    c00.placements.append(Placement(block, (40, 0, 8), tag=4))       # x 40..44, z 8..24
    c00.collision += placed_tris(block, (40, 0, 8), SURF_BLOCK, tag=4)
    roof = box_mesh((0, 0, 0), (12, 0.5, 12), meshlib.rgb(180, 180, 200))
    c00.placements.append(Placement(roof, (8, 3, 8), tag=5))         # underside at y 3
    c00.collision += placed_tris(roof, (8, 3, 8), SURF_ROOF, tag=5)
    c01 = cells[(0, 1)]
    steep = ramp_mesh(0, 4, 0, 6, 4.77, meshlib.rgb(140, 140, 40))   # about 50 degrees: walls
    gentle = ramp_mesh(0, 6, 0, 6, 5.03, meshlib.rgb(140, 140, 40))  # about 40 degrees: a floor
    c01.placements += [Placement(steep, (10, 0, 74), tag=6), Placement(gentle, (30, 0, 74), tag=7)]
    c01.collision += placed_tris(steep, (10, 0, 74), SURF_STEEP, tag=6)
    c01.collision += placed_tris(gentle, (30, 0, 74), SURF_STEEP, tag=7)
    c10 = cells[(1, 0)]
    c10.layers = ['gate']
    gate = box_mesh((0, 0, 0), (4, 3, 8), GATE_BLUE)
    c10.placements.append(Placement(gate, (84, 0, 28), layer='gate', tag=8))   # x 84..88, z 28..36
    c10.collision += placed_tris(gate, (84, 0, 28), SURF_GATE, layer='gate', tag=8)
    c11 = cells[(1, 1)]
    c11.layers = ['bridge_up', 'bridge_down']
    up = box_mesh((0, 0, 0), (10, 1, 4), meshlib.rgb(220, 220, 220))
    c11.placements += [Placement(up, (90, 5, 90), layer='bridge_up', tag=9),
                       Placement(up, (90, 0, 90), layer='bridge_down', tag=10)]
    far = Cell(5, 0, standin=box_mesh((-5, 0, -5), (5, 30, 5), MAGENTA))
    far.placements.append(Placement(grey, (5 * S + 32, 0, 32), tag=11))
    cells[(5, 0)] = far
    # entities: coins, a switch that refers to coin 0, a platform with collision of its own
    c00.entities += [Entity(T_COIN, (24, 3, 44), saved_bit=0), Entity(T_COIN, (12, 1, 12), saved_bit=1)]
    c10.entities.append(Entity(T_COIN, (86, 4, 32), layer='gate', saved_bit=2))
    c11.entities.append(Entity(T_SWITCH, (100, 0, 100), yaw=90, saved_bit=4,
                               params=pack_params([('u8', 2), ('fixed', 1.5), ('entity_ref', 0),
                                                   ('vec3', (1, 2, 3))])))
    pbox = box_mesh((-2, -0.5, -2), (2, 0.5, 2), meshlib.rgb(250, 250, 0))
    c01.entities.append(Entity(T_PLATFORM, (50, 2, 100), yaw=30, mesh=pbox,
                               collision=placed_tris(pbox, (0, 0, 0), SURF_PLATFORM, tag=12)))
    far.entities.append(Entity(T_COIN, (5 * S + 40, 1, 40), saved_bit=3))
    layers = [Layer('gate'), Layer('bridge_up', group=0, on=True), Layer('bridge_down', group=0)]
    region = Region('town', textures=[Texture(3, bytes(range(256)) * 4)], first_colour=1024,
                    variants=[('day', [0x7FFF, 0x001F, 0x03E0]), ('night', [0x0421, 0x0010, 0x0200])],
                    samples=[Sample('hum', bytes(64), 128, 0, 0)], backdrop=[VramCopy(0x450000, bytes(32))])
    w = World(cells=list(cells.values()), cell_shift=cell_shift, layers=layers, regions=[region])
    return w


# ---- random worlds for the differential test

def random_world(seed, cell_shift):
    """Six cells (i -1..1, j -1..0) under a heightfield, with random floors, walls, ceilings,
    slivers and slopes at the floor/wall threshold, some in a layer. Every triangle's tag is
    its index."""
    rng = random.Random(seed)
    S = 1 << cell_shift
    x0, x1, z0, z1 = -S, 2 * S, -S, S
    tris = []

    def add(a, b, c, layer=None):
        tris.append(Tri(a, b, c, surface=rng.randrange(256), layer=layer, tag=len(tris)))

    step = S / 8
    nx, nz = int((x1 - x0) / step), int((z1 - z0) / step)
    hts = [[rng.uniform(0, step * 0.8) for _ in range(nx + 1)] for _ in range(nz + 1)]
    for tz in range(nz):
        for tx in range(nx):
            p = [(x0 + (tx + dx) * step, hts[tz + dz][tx + dx], z0 + (tz + dz) * step)
                 for dx, dz in ((0, 0), (1, 0), (1, 1), (0, 1))]
            add(p[0], p[1], p[3])           # front up: (c - a) x (b - a) has +y
            add(p[1], p[2], p[3])

    def rpt(lo=0.0, hi=30.0):
        return (rng.uniform(x0, x1), rng.uniform(lo, hi), rng.uniform(z0, z1))

    for _ in range(60):                     # floors and ceilings at random heights, some slivers
        c = rpt(2, 25)
        r = rng.uniform(0.5, S / 4)
        a1 = rng.uniform(0, 2 * math.pi)
        spread = rng.choice([2.0, 1.0, 0.02])
        pts = [(c[0] + r * math.cos(a1 + k * spread), c[1] + rng.uniform(-1, 1), c[2] + r * math.sin(a1 + k * spread))
               for k in range(3)]
        layer = 'L1' if rng.random() < 0.2 else None
        add(*pts, layer=layer)              # either winding: a floor or a ceiling (or a steep wall)
    for _ in range(60):                     # walls: vertical and leaning quads
        c = rpt(0, 20)
        ang = rng.uniform(0, 2 * math.pi)
        w, h = rng.uniform(1, S / 3), rng.uniform(1, 8)
        lean = rng.uniform(-0.3, 0.3)
        dx, dz = math.cos(ang) * w / 2, math.sin(ang) * w / 2
        ox, oz = -math.sin(ang) * lean * h, math.cos(ang) * lean * h
        a, b = (c[0] - dx, c[1], c[2] - dz), (c[0] + dx, c[1], c[2] + dz)
        cc, d = (b[0] + ox, c[1] + h, b[2] + oz), (a[0] + ox, c[1] + h, a[2] + oz)
        layer = 'L1' if rng.random() < 0.2 else None
        add(a, d, b, layer=layer)
        add(b, d, cc, layer=layer)
    for k in range(40):                     # slopes within a hair of 45 degrees
        c = rpt(0, 20)
        deg = 45 + rng.choice([-1, 1]) * rng.choice([0.001, 0.01, 0.1])
        sl = math.tan(math.radians(deg))
        ang = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(1, 6)
        ux, uz = math.cos(ang), math.sin(ang)
        p0 = (c[0], c[1], c[2])
        p1 = (c[0] + ux * r, c[1] + sl * r, c[2] + uz * r)
        p2 = (c[0] - uz * r, c[1], c[2] + ux * r)
        add(p0, p2, p1)
        add(p0, p1, p2)
    w = World(cells=[Cell(i, j) for i in (-1, 0, 1) for j in (-1, 0)], cell_shift=cell_shift,
              layers=[Layer('L1')])
    w.cells[0].collision = tris
    # an entity with collision of its own (a moving object), in its own frame
    plat = box_mesh((-3, -0.5, -2), (3, 0.5, 2), 0xFFFFFF)
    ramp = ramp_mesh(-3, 3, -2, 2, 3, 0xFFFFFF)
    etris = placed_tris(plat, (0, 0, 0), 1, tag=1000) + placed_tris(ramp, (0, 0.5, 0), 2, tag=2000)
    for k, t in enumerate(etris):
        t.tag = 1000 + k
    [c for c in w.cells if (c.i, c.j) == (0, 0)][0].entities.append(Entity(9, (1, 0, 1), collision=etris))
    return w, etris


def heightfield_world(seed, cell_shift):
    """A heightfield only, over 2 x 2 cells with a vertex grid that does not line up with the
    cells' lookup grids: every point over it has a floor, which watertightness tests probe on
    edges, vertices and cell seams."""
    rng = random.Random(seed)
    S = 1 << cell_shift
    step = S / 6
    n = 12
    hts = [[rng.uniform(0, 3) for _ in range(n + 1)] for _ in range(n + 1)]
    tris = []
    for tz in range(n):
        for tx in range(n):
            p = [((tx + dx) * step, hts[tz + dz][tx + dx], (tz + dz) * step)
                 for dx, dz in ((0, 0), (1, 0), (1, 1), (0, 1))]
            if (tx + tz) % 2:
                tris.append(Tri(p[0], p[1], p[3], tag=len(tris)))
                tris.append(Tri(p[1], p[2], p[3], tag=len(tris)))
            else:
                tris.append(Tri(p[0], p[1], p[2], tag=len(tris)))
                tris.append(Tri(p[0], p[2], p[3], tag=len(tris)))
    w = World(cells=[Cell(i, j) for i in (0, 1) for j in (0, 1)], cell_shift=cell_shift)
    w.cells[0].collision = tris
    return w, step, n


# ---- query lists

OP_FLOOR, OP_CEILING, OP_PUSH, OP_RAY, OP_LAYER = 0, 1, 2, 3, 4
OP_EFLOOR, OP_EPUSH, OP_ERAY, OP_ECEILING = 5, 6, 7, 8


def query(op, p=(0, 0, 0), q=(0, 0, 0), arg=0):
    """One WpQuery record (queries.akr); p and q are raw 16.16 triples."""
    return struct.pack('<ii4i4i', op, arg, *p, 0, *q, 0)


def raw(p):
    return tuple(fx(c) for c in p)


# ---- running carts

def run_cart(tmp, main, embeds, consts=None, frames=2, dump=None, extra=()):
    """Builds a wrapper that defines consts and embeds (name: (type, bytes)) and imports main
    (a file in this directory), compiles it and runs it headless. Returns stdout lines."""
    tmp = Path(tmp)
    lines = ['cart "World Pack Test"']
    for k, v in (consts or {}).items():
        lines.append(f'const {k} = {v}')
    for name, (typ, data) in embeds.items():
        (tmp / f'{name}.bin').write_bytes(data)
        lines.append(f'embed {name}: {typ} = "{name}.bin"')
    lines.append(f'import "{HERE / main}"')
    src = tmp / 'wrapper.akr'
    src.write_text('\n'.join(lines) + '\n')
    env = dict(os.environ, MEI_STDLIB=str(ROOT / 'stdlib'))
    mei = tmp / 'wrapper.mei'
    r = subprocess.run([str(COMPILER), str(src), '-o', str(mei)], env=env, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError('compile failed:\n' + r.stderr)
    args = [str(RUNNER), str(mei), '--frames', str(frames)] + list(extra)
    if dump:
        args += ['--dump', str(dump)]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f'run failed ({r.returncode}):\n' + r.stdout[-2000:] + r.stderr[-2000:])
    return r.stdout.splitlines()


def read_ppm(path):
    data = Path(path).read_bytes()
    assert data[:2] == b'P6'
    parts = data.split(b'\n', 3)
    w, h = map(int, parts[1].split())
    px = parts[3]
    return w, h, px


# ---- a dense world for measuring

def bench_world(placements=100, cell_shift=6, seed=5):
    """3 x 3 cells, each with a heightfield ground of 2-unit quads (a 64-unit cell holds 2,048
    floor triangles), 40 box buildings (walls, roofs and undersides: 480 more triangles), and
    `placements` small boxes (12 triangles each) scattered as placements."""
    rng = random.Random(seed)
    S = 1 << cell_shift
    step = 2.0
    n = int(S / step)

    def ht(gx, gz):
        return 0.5 * math.sin(gx * 0.3) + 0.5 * math.cos(gz * 0.23)

    small = box_mesh((-0.5, 0, -0.5), (0.5, 1, 0.5), meshlib.rgb(200, 200, 90))
    house = box_mesh((-2, 0, -2), (2, 5, 2), meshlib.rgb(170, 120, 100))
    cells = []
    for ci in range(3):
        for cj in range(3):
            c = Cell(ci, cj)
            gx0, gz0 = ci * n, cj * n
            for tz in range(n):
                for tx in range(n):
                    g = [(gx0 + tx + dx, gz0 + tz + dz) for dx, dz in ((0, 0), (1, 0), (1, 1), (0, 1))]
                    p = [(a * step, ht(a, b), b * step) for a, b in g]
                    c.collision.append(Tri(p[0], p[1], p[3], surface=1))
                    c.collision.append(Tri(p[1], p[2], p[3], surface=1))
            for k in range(40):
                pos = (ci * S + rng.uniform(3, S - 3), 1.5, cj * S + rng.uniform(3, S - 3))
                c.collision += placed_tris(house, pos, 2)
            for k in range(placements):
                pos = (ci * S + rng.uniform(1, S - 1), 1, cj * S + rng.uniform(1, S - 1))
                c.placements.append(Placement(small, pos, yaw=rng.uniform(0, 360)))
            cells.append(c)
    return World(cells=cells, cell_shift=cell_shift)
