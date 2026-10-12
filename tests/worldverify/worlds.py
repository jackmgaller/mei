"""Worlds for tests/test_worldverify.py: a known-good plaza and the same plaza with one planted
fault each. Built with tools/worldkit/pack.py at test time; nothing generated is committed.

The plaza is one 32-unit cell (cell_shift 5) of 2-unit ground tiles with three box buildings
standing on whole tiles, the tiles under them left out, so that the face pairs the painter's
algorithm meets are ordered correctly by average depth from the sampled cameras (not from all:
a camera at eye height 4 units from the coin sees a tile drawn over a building's foot).
"""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import importlib.util  # noqa: E402
from worldkit.pack import World, Cell, Placement, Tri, Entity, Lod, encode  # noqa: E402
import meshlib  # noqa: E402

# the world pack tests' mesh helpers (tests/worldpack/fixture.py)
_spec = importlib.util.spec_from_file_location('worldpack_fixture', ROOT / 'tests' / 'worldpack' / 'fixture.py')
_wp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_wp)
box_mesh, placed_tris, coin_mesh = _wp.box_mesh, _wp.placed_tris, _wp.coin_mesh

COMPILER = Path(os.environ.get('MEIC', ROOT / 'build/meic')).resolve()
PROBE = Path(os.environ.get('SCENE_PROBE', ROOT / 'build/mei-scene-probe')).resolve()

GREY = meshlib.rgb(120, 120, 120)
SAND = [meshlib.rgb(200, 190, 150), meshlib.rgb(185, 175, 140)]

TAG_GROUND, TAG_BOX = 1, 10           # boxes are TAG_BOX + n
BOXES = [(4, 4, 4, 4, 6), (18, 6, 4, 6, 8), (8, 20, 6, 4, 5)]      # x, z, width, depth, height


def tools_built():
    return COMPILER.exists() and PROBE.exists()


def tools():
    return {'compiler': COMPILER, 'probe': PROBE}


def grid_mesh(x0, z0, nx, nz, step, colours, y=0.0, skip=()):
    """Floor tiles facing up, sharing corners: nx x nz quads of `step` units from (x0, z0)."""
    m = meshlib.Mesh()
    idx = {}

    def v(i, k):
        if (i, k) not in idx:
            idx[(i, k)] = m.vertex(x0 + i * step, y, z0 + k * step)
        return idx[(i, k)]
    for k in range(nz):
        for i in range(nx):
            if (i, k) in skip:
                continue
            # strip order a b c d, facing up
            m.quad([v(i, k), v(i + 1, k), v(i, k + 1), v(i + 1, k + 1)], [colours[(i + k) % len(colours)]])
    return m.pack()


def plaza(i=0, j=0, ground=True, boxes=BOXES):
    """A Cell of the plaza at grid (i, j) (32-unit cells), its collision included."""
    S = 32
    ox, oz = i * S, j * S
    c = Cell(i, j)
    skip = set()
    for bx, bz, w, d, h in boxes:
        for a in range(bx // 2, (bx + w) // 2):
            for b in range(bz // 2, (bz + d) // 2):
                skip.add((a, b))
    if ground:
        g = grid_mesh(-16, -16, 16, 16, 2.0, SAND, skip=skip)
        c.placements.append(Placement(g, (ox + 16, 0, oz + 16), tag=TAG_GROUND))
        c.collision += placed_tris(g, (ox + 16, 0, oz + 16), 1, tag=TAG_GROUND)
    for n, (bx, bz, w, d, h) in enumerate(boxes):
        m = box_mesh((-w / 2, 0, -d / 2), (w / 2, h, d / 2), meshlib.rgb(150 + 30 * n, 90, 70))
        pos = (ox + bx + w / 2, 0, oz + bz + d / 2)
        c.placements.append(Placement(m, pos, tag=TAG_BOX + n))
        c.collision += placed_tris(m, pos, 2, tag=TAG_BOX + n)
    return c


def good_world():
    """The known-good plaza: one cell, a coin above the ground."""
    c = plaza()
    c.entities.append(Entity(1, (12, 1, 14), mesh=box_mesh((-0.3, 0, -0.3), (0.3, 0.6, 0.3), meshlib.rgb(250, 220, 0))))
    return World(cells=[c], cell_shift=5)


def lod_world():
    """The good plaza whose buildings have levels of detail: a lower box from 10 units, a lower
    one still from 18, and none past 26 (the cull), so the sampled cameras see every level."""
    w = good_world()
    for p in w.cells[0].placements:
        if p.tag >= TAG_BOX:
            n = p.tag - TAG_BOX
            bx, bz, wd, d, h = BOXES[n]
            mid = box_mesh((-wd / 2, 0, -d / 2), (wd / 2, h * 0.75, d / 2), meshlib.rgb(90, 150 + 30 * n, 70))
            low = box_mesh((-wd / 2, 0, -d / 2), (wd / 2, h * 0.5, d / 2), meshlib.rgb(70, 90, 150 + 30 * n))
            p.lod = Lod([(10, mid), (18, low), (26, None)], band=1.0)
    return w


def crack_world():
    """The plaza with two slabs 0.1 units apart (narrower than the probe's 0.3 radius), their
    tops at the same height 2 units above the ground: a crack between tag 30 and tag 31."""
    w = good_world()
    c = w.cells[0]
    for tag, (x0, x1) in ((30, (22.0, 26.0)), (31, (26.1, 30.0))):
        m = box_mesh((0, 0, 0), (x1 - x0, 0.25, 4), GREY)
        c.placements.append(Placement(m, (x0, 1.75, 24), tag=tag))
        c.collision += placed_tris(m, (x0, 1.75, 24), 3, tag=tag)
    return w


def seam_world():
    """Two plaza cells side by side whose ground meets at the seam x = 32, but the right cell's
    ground tiles split the seam edge at different corners (1-unit tiles there): a T-junction."""
    a = plaza(0, 0, boxes=[])
    b = plaza(1, 0, boxes=[])
    # replace b's collision with tiles offset by one unit in z along the seam column
    b.collision = []
    for k in range(17):
        z0 = -1 + 2 * k
        za, zb = max(0, z0), min(32, z0 + 2)
        if za >= zb:
            continue
        b.collision += [Tri((32, 0, za), (34, 0, za), (32, 0, zb), tag=40),
                        Tri((34, 0, za), (34, 0, zb), (32, 0, zb), tag=40)]
    b.collision += [Tri((34, 0, 0), (64, 0, 0), (34, 0, 32), tag=41), Tri((64, 0, 0), (64, 0, 32), (34, 0, 32), tag=41)]
    return World(cells=[a, b], cell_shift=5)


def entity_wall_world():
    """The plaza with a coin (entity number 1) inside the second box."""
    w = good_world()
    w.cells[0].entities.append(Entity(1, (20, 3, 9)))
    return w


def missort_world():
    """The plaza without its ground, plus a runway strip (tag 50) from z 1 to z 17 along x 26..28
    and a crate (tag 51) standing on it at z 12..13: from VANTAGE_MISSORT, at the strip's near
    end, the strip's average depth (about 8) is nearer than the crate's front (10.5), so the
    strip is drawn over the crate's lower part. A known mis-sort in the near band."""
    c = plaza(ground=False)
    strip = meshlib.Mesh()
    a, b, cc, d = (strip.vertex(10, 0.01, -15), strip.vertex(12, 0.01, -15), strip.vertex(10, 0.01, 1),
                   strip.vertex(12, 0.01, 1))
    strip.quad([a, b, cc, d], [meshlib.rgb(60, 60, 200)])
    c.placements.append(Placement(strip.pack(), (16, 0, 16), tag=50))
    crate = box_mesh((-1, 0, -0.5), (1, 1.5, 0.5), meshlib.rgb(200, 60, 60))
    c.placements.append(Placement(crate, (27, 0.01, 12.5), tag=51))
    return World(cells=[c], cell_shift=5)


VANTAGE_MISSORT = {'position': [27.0, 1.2, 1.5], 'yaw': 0.0, 'pitch': -8.0}


def ground_missort_world(crate_ground=False, sink=0.0):
    """The mis-sorted pair of missort_world() with the strip (tag 50) flagged as ground, so the
    reader draws it first and the crate (tag 51) over it. crate_ground flags the crate as ground
    too (a raised ground piece: the pair is then sorted inside the ground pass, by average depth,
    and mis-sorted again); sink lowers the crate this far through the strip, so that the strip
    truly hides its bottom while the reader draws all of it over the strip."""
    w = missort_world()
    strip, crate = w.cells[0].placements[-2:]
    strip.ground = True
    crate.ground = crate_ground
    crate.position = (crate.position[0], crate.position[1] - sink, crate.position[2])
    return w


def surface_mesh(x0, z0, nx, nz, step, height, colours):
    """Up-facing quads over a grid of `step` units from (x0, z0), at heights height(x, z)."""
    m = meshlib.Mesh()
    idx = {}

    def v(i, k):
        if (i, k) not in idx:
            x, z = x0 + i * step, z0 + k * step
            idx[(i, k)] = m.vertex(x, height(x, z), z)
        return idx[(i, k)]
    for k in range(nz):
        for i in range(nx):
            m.quad([v(i, k), v(i + 1, k), v(i, k + 1), v(i + 1, k + 1)], [colours[(i + k) % len(colours)]])
    return m.pack()


def slope_world(ridge=False):
    """Ground that is all flagged ground: a flat (tag 1, z 0..14) and a ramp rising from its far
    edge (tag 2, z 14..22, up to y = 4), with a box building (tag 10) and a coin on the flat. Seen
    from above, the flat and the ramp make a valley: no ground face can hide another or hide what
    stands on the flat, so ground-first drawing is exact. ridge adds an upper flat at the ramp's
    top (tag 3, z 22..32) with a box (tag 11) on it: seen from the flat, the crest hides the
    bottom of that box, which the reader draws over the crest anyway (ground inversions)."""
    c = Cell(0, 0)
    flat = surface_mesh(0, 0, 16, 7, 2.0, lambda x, z: 0.0, SAND)
    ramp = surface_mesh(0, 14, 16, 4, 2.0, lambda x, z: (z - 14) * 0.5, SAND)
    parts = [(flat, 1), (ramp, 2)]
    if ridge:
        parts.append((surface_mesh(0, 22, 16, 5, 2.0, lambda x, z: 4.0, SAND), 3))
    for m, tag in parts:
        c.placements.append(Placement(m, (0, 0, 0), tag=tag, ground=True))
        c.collision += placed_tris(m, (0, 0, 0), 1, tag=tag)
    boxes = [((6, 0, 6), 10, 3.0)] + ([((16, 4.0, 25), 11, 3.0)] if ridge else [])
    for pos, tag, h in boxes:
        m = box_mesh((-2, 0, -1), (2, h, 1), meshlib.rgb(170, 90, 70))
        c.placements.append(Placement(m, pos, tag=tag))
        c.collision += placed_tris(m, pos, 2, tag=tag)
    coin = box_mesh((-0.3, 0, -0.3), (0.3, 0.6, 0.3), meshlib.rgb(250, 220, 0))
    c.entities.append(Entity(1, (20, 1, 8), mesh=coin))
    return World(cells=[c], cell_shift=5)


VANTAGE_RIDGE = {'position': [16.0, 1.0, 8.0], 'yaw': 0.0, 'pitch': 0.0}


def _up_tri(a, b, c, tag, slide=None):
    """A collision Tri of corners a, b, c wound to face up (pack.front_normal's y positive)."""
    u = [c[k] - a[k] for k in range(3)]
    w = [b[k] - a[k] for k in range(3)]
    if u[2] * w[0] - u[0] * w[2] < 0:
        b, c = c, b
    return Tri(a, b, c, tag=tag, slide_floor_degrees=slide)


def crease_world(slide=None):
    """The plaza with a steep V-shaped gully (tags 70 and 71) where its ground is left out, x 22..30
    and z 22..30: a 60-degree face from y 7 at x 22 down to y 0 at x 26, and a 63-degree face up
    to y 8 at x 30. Both are walls to the default probe (floors up to 45 degrees) and nothing is
    under them: a body dropped into the gully is pushed one way by one face and back by the
    other, and sinks through. slide makes them slide floors up to that slope as well (pack.Tri's
    slide_floor_degrees)."""
    w = good_world()
    c = w.cells[0]
    skip = {(a, b) for a in range(11, 15) for b in range(11, 15)}
    g = grid_mesh(-16, -16, 16, 16, 2.0, SAND, skip=skip | {(a, b) for bx, bz, wd, d, h in BOXES
                                                            for a in range(bx // 2, (bx + wd) // 2)
                                                            for b in range(bz // 2, (bz + d) // 2)})
    c.placements[0] = Placement(g, (16, 0, 16), tag=TAG_GROUND)
    c.collision = [t for t in c.collision if t.tag != TAG_GROUND] + placed_tris(g, (16, 0, 16), 1, tag=TAG_GROUND)
    for tag, (x0, y0), (x1, y1) in ((70, (22, 7), (26, 0)), (71, (26, 0), (30, 8))):
        p, q, r, s = (x0, y0, 22), (x1, y1, 22), (x0, y0, 30), (x1, y1, 30)
        c.collision += [_up_tri(p, q, r, tag, slide), _up_tri(q, s, r, tag, slide)]
    return w


def overdraw_world():
    """The plaza with twelve screen-filling panels (tag 60) stacked in front of VANTAGE_OVERDRAW,
    farthest first in depth: about 12 screens of fill, over the GPU threshold."""
    w = good_world()
    c = w.cells[0]
    m = meshlib.Mesh()
    for k in range(12):
        z = 30 - k * 0.5
        a, b, cc, d = m.vertex(-14, 0.01, z), m.vertex(14, 0.01, z), m.vertex(-14, 14, z), m.vertex(14, 14, z)
        m.quad([a, b, cc, d], [meshlib.rgb(20 * k, 100, 100)])
    c.placements.append(Placement(m.pack(), (16, 0, 0.5), tag=60))
    return w


VANTAGE_OVERDRAW = {'position': [16.0, 7.0, 21.0], 'yaw': 0.0, 'pitch': 0.0}


def dropped_world():
    """The plaza with three dense floors (tag 70, 1,922 triangles each) stacked under
    VANTAGE_DROPPED: more than the GPU's 4,000 triangles in one view."""
    w = good_world()
    c = w.cells[0]
    for k in range(3):
        m = grid_mesh(-15.5, -15.5, 31, 31, 1.0, [meshlib.rgb(40 * k, 200, 40)], y=0.02 + 0.02 * k)
        c.placements.append(Placement(m, (16, 0, 16), tag=70 + k))
    return w


VANTAGE_DROPPED = {'position': [16.0, 40.0, 16.0], 'yaw': 0.0, 'pitch': -89.0}


def nearplane_world():
    """A single large floor quad (tag 80) and a large wall quad (tag 81) for cameras so close
    that both cross the near plane."""
    c = Cell(0, 0)
    m = meshlib.Mesh()
    a, b, cc, d = m.vertex(-16, 0, -16), m.vertex(16, 0, -16), m.vertex(-16, 0, 16), m.vertex(16, 0, 16)
    m.quad([a, b, cc, d], [meshlib.rgb(90, 160, 90)])
    c.placements.append(Placement(m.pack(), (16, 0, 16), tag=80))
    wall = meshlib.Mesh()
    a, b, cc, d = wall.vertex(-16, 0, 0), wall.vertex(16, 0, 0), wall.vertex(-16, 8, 0), wall.vertex(16, 8, 0)
    wall.quad([a, b, cc, d], [meshlib.rgb(160, 90, 90)])
    c.placements.append(Placement(wall.pack(), (16, 0, 24), tag=81))
    return World(cells=[c], cell_shift=5)


def ledge_world():
    """test_room's ledge alone: ground (flagged ground) and a 3 x 2 x 3 block of triangles (tag
    2), split as the Asset Kit splits a box, with a coin (entity 0) floating 0.2 above its top.
    Drawn by their own depth alone (runtime entity_drawing 'mesh_at'), the top's two triangles
    are drawn over the coin from many cameras close above it, none of which the sampling without
    entity cameras makes."""
    c = Cell(0, 0)
    g = grid_mesh(-16, -16, 16, 16, 2.0, SAND)
    c.placements.append(Placement(g, (16, 0, 16), tag=TAG_GROUND, ground=True))
    c.collision += placed_tris(g, (16, 0, 16), 1, tag=TAG_GROUND)
    m = _wp.tri_box_mesh((-1.5, 0, -1.5), (1.5, 2, 1.5), GREY)
    c.placements.append(Placement(m, (16, 0, 16), tag=2))
    c.collision += placed_tris(m, (16, 0, 16), 2, tag=2)
    c.entities.append(Entity(1, (16, 2.5, 16), mesh=coin_mesh()))
    return World(cells=[c], cell_shift=5)


# The object world's places (see object_world()): each is (what, the coin's position).
OBJECTS = {
    'small_platform': (6.0, 2.0, 6.0),       # above a 4 x 4 platform 1.5 high, 0.2 clear of it
    'large_near': (15.5, 1.5, 5.5),          # above a 12 x 12 platform 1 high (one quad on top)
    'large_far': (24.5, 1.5, 14.5),
    'behind_wall': (5.5, 0.5, 20.6),         # on the ground 0.3 behind a thin wall 2 high
    'pair_a': (10.0, 0.5, 24.0),             # two coins on the ground, 0.5 apart
    'pair_b': (10.4, 0.5, 24.3),
    'under_slab': (24.0, 0.5, 24.0),         # on the ground under a slab at 2.2 .. 2.5
    'figure': (18.0, 1.0, 8.0),              # a character-sized figure standing on the large one
}


def figure_mesh():
    """A figure 1.85 high made of four separate boxes (legs, body, head and an arm held forward),
    its origin at its feet: a mesh whose own faces need sorting, like a character's."""
    m = meshlib.Mesh()
    parts = [((-0.2, 0, -0.15), (0.2, 0.75, 0.15), meshlib.rgb(60, 60, 160)),
             ((-0.3, 0.8, -0.18), (0.3, 1.5, 0.18), meshlib.rgb(200, 60, 60)),
             ((-0.17, 1.55, -0.17), (0.17, 1.85, 0.17), meshlib.rgb(240, 200, 160)),
             ((0.35, 1.2, -0.05), (0.5, 1.35, 0.5), meshlib.rgb(200, 60, 60))]
    for lo, hi, colour in parts:
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        ctr = [(lo[k] + hi[k]) / 2 for k in range(3)]
        for corners in ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
                        [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
                        [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
                        [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
                        [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
                        [(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)]):
            _wp._face(m, corners, colour, ctr)
    return m.pack()


def object_world():
    """Small objects (coins, entity meshes) where sorting by average depth goes wrong: ground of
    2-unit tiles (flagged ground) with a small platform, a large one, a thin wall, a slab held up
    in the air, and coins on and around them (OBJECTS). Placement tags: 1 ground, 20 the small
    platform, 21 the large one, 22 the wall, 23 the slab."""
    c = Cell(0, 0)
    g = grid_mesh(-16, -16, 16, 16, 2.0, SAND)
    c.placements.append(Placement(g, (16, 0, 16), tag=TAG_GROUND, ground=True))
    c.collision += placed_tris(g, (16, 0, 16), 1, tag=TAG_GROUND)
    for tag, lo, hi, colour in ((20, (4, 0, 4), (8, 1.5, 8), meshlib.rgb(140, 140, 160)),
                                (21, (14, 0, 4), (26, 1, 16), meshlib.rgb(120, 150, 120)),
                                (22, (4, 0, 20), (7, 2, 20.2), meshlib.rgb(170, 90, 70)),
                                (23, (22, 2.2, 22), (26, 2.5, 26), meshlib.rgb(90, 110, 170))):
        m = box_mesh((0, 0, 0), tuple(hi[k] - lo[k] for k in range(3)), colour)
        c.placements.append(Placement(m, lo, tag=tag))
        c.collision += placed_tris(m, lo, 2, tag=tag)
    for n, (name, pos) in enumerate(OBJECTS.items()):
        m = figure_mesh() if name == 'figure' else coin_mesh(meshlib.rgb(250, 200 + 5 * n, 60))
        c.entities.append(Entity(1, pos, yaw=0.3 * n, mesh=m))
    return World(cells=[c], cell_shift=5)


def depth_world():
    """object_world() with what only a depth buffer draws right (docs/RENDERING.md): two boxes
    crossing each other in an X (tags 31 and 32, interpenetrating), and a crate sunk 0.3 units
    through the ground (tag 30, not ground). Seen from VANTAGE_DEPTH."""
    w = object_world()
    c = w.cells[0]
    for tag, lo, size, colour in ((31, (8.0, 0.0, 12.7), (5.0, 1.0, 0.6), meshlib.rgb(200, 120, 40)),
                                  (32, (10.2, 0.0, 10.5), (0.6, 1.4, 5.0), meshlib.rgb(40, 120, 200)),
                                  (30, (27.0, -0.3, 22.0), (2.0, 1.5, 2.0), meshlib.rgb(200, 60, 60))):
        c.placements.append(Placement(box_mesh((0, 0, 0), size, colour), lo, tag=tag))
    return w


VANTAGE_DEPTH = [{'position': [10.5, 2.5, 7.0], 'yaw': 10.0, 'pitch': -20.0},      # the X
                 {'position': [13.0, 1.8, 9.0], 'yaw': -60.0, 'pitch': -15.0},
                 {'position': [28.0, 1.6, 17.0], 'yaw': 0.0, 'pitch': -12.0},      # the sunk crate
                 {'position': [20.0, 4.0, 0.5], 'yaw': 0.0, 'pitch': -30.0}]       # the large platform


def pack_of(world):
    return encode(world)
