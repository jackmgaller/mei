"""Worlds for tests/test_worldverify.py: a known-good plaza and the same plaza with one planted
fault each. Built with tools/worldkit/pack.py at test time; nothing generated is committed.

The plaza is one 32-unit cell (cell_shift 5) of 2-unit ground tiles with three box buildings
standing on whole tiles, the tiles under them left out, so that every face pair the painter's
algorithm meets is ordered correctly by average depth from anywhere above the ground.
"""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import importlib.util  # noqa: E402
from worldkit.pack import World, Cell, Placement, Tri, Entity, encode  # noqa: E402
import meshlib  # noqa: E402

# the world pack tests' mesh helpers (tests/worldpack/fixture.py)
_spec = importlib.util.spec_from_file_location('worldpack_fixture', ROOT / 'tests' / 'worldpack' / 'fixture.py')
_wp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_wp)
box_mesh, placed_tris = _wp.box_mesh, _wp.placed_tris

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


def pack_of(world):
    return encode(world)
