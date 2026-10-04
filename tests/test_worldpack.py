"""World pack format and reader (docs/WORLDPACK.md). Run: python3 -m unittest discover -s tests -p test_worldpack.py

The encoder/decoder tests need only Python. The console tests build packs at test time,
embed them in the carts in tests/worldpack/ and run them with mei-headless (MEIC and RUN
select the builds; they are skipped when the tools have not been built).
"""
from fractions import Fraction
import math
import os
from pathlib import Path
import random
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / 'worldpack'))
import fixture as F  # noqa: E402
from worldkit import pack as P  # noqa: E402
from worldkit.pack import (World, Cell, Placement, Tri, Entity, Layer, Region, PackError, encode,
                           decode, Oracle, fx, ONE)  # noqa: E402

VERBOSE = os.environ.get('WORLDPACK_VERBOSE')
needs_tools = unittest.skipUnless(F.tools_built(), 'meic and mei-headless are not built')


def tiny_world(**kw):
    m = F.box_mesh((-1, 0, -1), (1, 2, 1), 0xFFFFFF)
    c = Cell(0, 0, placements=[Placement(m, (32, 0, 32))],
             collision=[Tri((0, 0, 0), (64, 0, 0), (0, 0, 64), 1), Tri((64, 0, 64), (0, 0, 64), (64, 0, 0), 2)])
    return World(cells=[c], **kw)


class EncoderTests(unittest.TestCase):
    def test_round_trip_demo_world(self):
        w = F.demo_world()
        rep = {}
        data = encode(w, rep)
        self.assertEqual(data, encode(F.demo_world()), 'encoding is deterministic')
        p = decode(data)
        self.assertEqual((p.major, p.minor, p.cell_shift), (1, 3, 6))
        self.assertEqual(set(p.cells), {(0, 0), (1, 0), (0, 1), (1, 1), (5, 0)})
        self.assertEqual([l[0] for l in p.layers], ['gate', 'bridge_up', 'bridge_down'])
        self.assertEqual([l[1:] for l in p.layers], [(255, False), (0, True), (0, False)])
        c00 = p.cells[(0, 0)]
        self.assertEqual(len(c00.placements), 5)
        self.assertEqual([e['saved_bit'] for e in c00.entities], [0, 1])
        # positions are stored cell-locally around the centre
        self.assertEqual(c00.placements[1]['pos'], (fx(20 - 32), 0, fx(40 - 32)))
        self.assertEqual(c00.entities[0]['pos'], (fx(24 - 32), fx(3), fx(44 - 32)))
        # the gate's placement, collision and coin are in the cell's layer bit 0
        c10 = p.cells[(1, 0)]
        self.assertEqual(c10.layers, [0])
        self.assertEqual([pl['mask'] for pl in c10.placements], [0, 1])
        self.assertEqual(c10.entities[0]['mask'], 1)
        gate_tris = [f for f in c10.coll.floors + c10.coll.ceilings if (f[3] >> 16) == 8]
        self.assertTrue(gate_tris and all((f[3] >> 8) & 255 == 1 for f in gate_tris))
        # the switch's parameter record and its reference to coin 0
        sw = p.cells[(1, 1)].entities[0]
        self.assertEqual(struct.unpack('<BxxxiI4i', sw['params']), (2, fx(1.5), 0, fx(1), fx(2), fx(3), 0))
        self.assertEqual(p.entities[0], c00.entities[0]['off'])
        # the platform's own collision block
        plat = p.cells[(0, 1)].entities[0]
        self.assertEqual((len(plat['coll'].floors), len(plat['coll'].ceilings), len(plat['coll'].walls)), (2, 2, 8))
        # meshes are pooled: the ground is stored once for four cells
        self.assertEqual(len({pl['mesh'] for c in p.cells.values() for pl in c.placements if pl['tag'] == 1}), 1)
        # regions
        r = p.regions[0]
        self.assertEqual((r.name, r.first_colour, [v[0] for v in r.variants]), ('town', 1024, ['day', 'night']))
        self.assertEqual(r.variants[1][1], [0x0421, 0x0010, 0x0200])
        self.assertEqual(r.textures[0].data, bytes(range(256)) * 4)
        self.assertEqual(r.backdrop[0].address, 0x450000)
        self.assertEqual(rep['entities'][0], ((0, 0), 0))
        nums = P.entity_numbers(w)
        self.assertEqual(sorted(nums.values()), list(range(len(p.entities))))
        for (i, j, k), n in nums.items():
            self.assertEqual(p.cells[(i, j)].entities[k]['number'], n)

    def test_classification_by_angle(self):
        w = F.demo_world()
        o = Oracle(w)
        kinds = {}
        for t in o.tris:
            kinds.setdefault(t['tag'], set()).add(t['kind'])
        # tag 6 is the 50 degree ramp: its slope is a wall; tag 7 (40 degrees) a floor
        steep = [t for t in o.tris if t['tag'] == 6 and t['n'][1] > 0]
        gentle = [t for t in o.tris if t['tag'] == 7 and t['n'][1] > 0]
        self.assertTrue(all(t['kind'] == P.KIND_WALL for t in steep))
        self.assertTrue(all(t['kind'] == P.KIND_FLOOR for t in gentle))
        w2 = F.demo_world()
        w2.floor_max_degrees = 55
        steep2 = [t for t in Oracle(w2).tris if t['tag'] == 6 and t['n'][1] > 0]
        self.assertTrue(all(t['kind'] == P.KIND_FLOOR for t in steep2))

    def test_shared_edges_get_exactly_opposite_rows(self):
        w, step, n = F.heightfield_world(3, 6)
        p = decode(encode(w))
        for c in p.cells.values():
            rows = {e for f in c.coll.floors for e in f[4]}
            lonely = [e for e in rows if (-e[0], -e[1], -e[2]) not in rows]
            # only the lines along the heightfield's sides and the cell's seams (where the
            # neighbouring triangles are filed in the neighbouring cell) have no opposite
            self.assertLessEqual(len(lonely), 8)
            self.assertGreater(len(rows), 20)

    def test_triangles_are_copied_into_neighbouring_cells(self):
        # a wall 0.5 units inside cell (0, 0) reaches cell (1, 0) within the pad
        wall = Tri((63.5, 0, 10), (63.5, 0, 20), (63.5, 5, 10))
        w = World(cells=[Cell(0, 0, collision=[wall]), Cell(1, 0)], coll_pad=1.0)
        p = decode(encode(w))
        self.assertEqual(len(p.cells[(1, 0)].coll.walls), 1)
        w.coll_pad = 0.25
        p = decode(encode(w))
        self.assertIsNone(p.cells[(1, 0)].coll)

    def test_limits(self):
        with self.assertRaisesRegex(PackError, 'cell_shift'):
            encode(tiny_world(cell_shift=8))
        with self.assertRaisesRegex(PackError, 'cell_shift'):
            encode(tiny_world(cell_shift=3))
        with self.assertRaisesRegex(PackError, 'at least one cell'):
            encode(World(cells=[]))
        w = tiny_world()
        w.cells[0].layers = [f'l{k}' for k in range(9)]
        w.layers = [Layer(f'l{k}') for k in range(9)]
        with self.assertRaisesRegex(PackError, 'more than 8 layers'):
            encode(w)
        w = tiny_world()
        w.cells[0].layers = ['nope']
        with self.assertRaisesRegex(PackError, 'unknown layer'):
            encode(w)
        w = tiny_world()
        w.cells[0].collision = [Tri((0, 0, 0), (1, 0, 0), (2, 0, 0))]
        with self.assertRaisesRegex(PackError, 'degenerate'):
            encode(w)
        w = tiny_world()
        w.cells[0].placements[0].position = (70, 0, 32)
        with self.assertRaisesRegex(PackError, 'outside its cell'):
            encode(w)
        w.cells[0].placements[0].position = (63.9, 0, 32)
        w.overhang = 0.5
        with self.assertRaisesRegex(PackError, 'overhangs'):
            encode(w)
        w = tiny_world()
        w.cells.append(Cell(0, 0))
        with self.assertRaisesRegex(PackError, 'two cells'):
            encode(w)
        w = tiny_world()
        w.cells[0].collision = [Tri((0, 5000, 0), (1, 5000, 0), (0, 5000, 1))]
        with self.assertRaisesRegex(PackError, 'beyond'):
            encode(w)
        w = World(cells=[Cell(600, 0)])
        with self.assertRaisesRegex(PackError, 'beyond'):
            encode(w)
        w = tiny_world()
        w.cells[0].collision = [Tri((x, 0, z), (x + 1, 0, z), (x, 0, z + 1))
                                for x in range(30, 34) for z in range(30, 34) for _ in range(80)]
        with self.assertRaisesRegex(PackError, 'at most 255'):
            encode(w)

    def test_cell_sizes(self):
        for shift in (4, 5, 6, 7):
            S = 1 << shift
            x, z = -S + 3, 2 * S + 3
            w = World(cells=[Cell(-1, 2, collision=[Tri((x, 0, z), (x + 2, 0, z), (x, 0, z + 2))])],
                      cell_shift=shift, coll_pad=min(1.0, S / 2))
            p = decode(encode(w))
            self.assertEqual(p.cell_shift, shift)
            ij, lx, lz = p.cell_of(fx(x + 0.5), fx(z + 0.5))
            self.assertEqual(ij, (-1, 2))
            self.assertEqual((lx, lz), (fx(3.5 - S / 2), fx(3.5 - S / 2)))
            self.assertEqual(len(p.cells[ij].coll.floors), 1)

    def test_malformed_packs_are_refused(self):
        good = encode(F.demo_world())
        decode(good)
        cases = {
            'magic': b'MEIX' + good[4:],
            'version': good[:4] + struct.pack('<H', 2) + good[6:],
            'size': good[:-4],
            'truncated': good[:100],
            'shift': good[:12] + bytes([9]) + good[13:],
            'required flag': good[:13] + bytes([0x10]) + good[14:],
        }
        for name, data in cases.items():
            with self.subTest(name), self.assertRaises(PackError):
                decode(data)
        # a newer minor version is still read
        decode(good[:6] + struct.pack('<H', 7) + good[8:])
        decode(good[:13] + bytes([0x02]) + good[14:])     # an ignorable flag 1.1 does not define
        # corrupt offsets anywhere in the cell table must be caught, never crash
        p = decode(good)
        rng = random.Random(5)
        c = p.cells[(0, 0)].off
        for field in range(48, 96, 4):
            for _ in range(4):
                bad = bytearray(good)
                struct.pack_into('<I', bad, c + field, rng.choice([1, 3, len(good), len(good) + 64, 0xFFFFFFF0]))
                try:
                    decode(bytes(bad))
                except PackError:
                    pass
        # random byte flips: either decodes or raises PackError
        for _ in range(300):
            bad = bytearray(good)
            for _ in range(rng.randrange(1, 4)):
                bad[rng.randrange(len(bad))] = rng.randrange(256)
            try:
                decode(bytes(bad))
            except PackError:
                pass

    def test_ground_round_trip_and_older_packs(self):
        m = F.box_mesh((-1, 0, -1), (1, 2, 1), 0xFFFFFF)
        pls = [Placement(m, (8, 0, 8), tag=1), Placement(m, (9, 0, 9), tag=2, ground=True),
               Placement(m, (10, 0, 10), tag=3), Placement(m, (11, 0, 11), tag=4, ground=True)]
        w = World(cells=[Cell(0, 0, placements=pls)], cell_shift=5)
        data = encode(w)
        c = decode(data).cells[(0, 0)]
        # ground placements are filed first, each group in its own order
        self.assertEqual([p['tag'] for p in c.placements], [2, 4, 1, 3])
        self.assertEqual([p['ground'] for p in c.placements], [True, True, False, False])
        self.assertEqual(c.ground_count, 2)
        co = c.off
        self.assertEqual(struct.unpack_from('<I', data, co + 76)[0], 2)
        self.assertEqual(data[13], P.FLAG_GROUND)
        pl = struct.unpack_from('<I', data, co + 56)[0]
        self.assertEqual([data[pl + P.PLACEMENT_SIZE * k + 45] for k in range(4)], [1, 1, 0, 0])
        # the same pack read as 1.0: the fields 1.1 uses are reserved there, and ignored
        old = data[:6] + struct.pack('<H', 0) + data[8:]
        c0 = decode(old).cells[(0, 0)]
        self.assertEqual((c0.ground_count, [p['ground'] for p in c0.placements]), (0, [False] * 4))
        # a pack without ground is a 1.0 pack but for its minor version: 1.0 packs read as before
        plain = World(cells=[Cell(0, 0, placements=pls[:1] + [Placement(m, (9, 0, 9), tag=2)])], cell_shift=5)
        new = encode(plain)
        as10 = new[:6] + struct.pack('<H', 0) + new[8:]
        self.assertEqual(new[13], 0)
        for d in (new, as10):
            c = decode(d).cells[(0, 0)]
            self.assertEqual(c.ground_count, 0)
            self.assertEqual([(p['tag'], p['ground']) for p in c.placements], [(1, False), (2, False)])
        # inconsistent ground fields are refused
        for at, value, fmt in ((co + 76, 5, '<I'), (co + 76, 1, '<I'), (pl + P.PLACEMENT_SIZE * 2 + 45, 1, '<B'),
                               (13, 0, '<B')):
            bad = bytearray(data)
            struct.pack_into(fmt, bad, at, value)
            with self.subTest(at=at), self.assertRaises(PackError):
                decode(bytes(bad))

    def test_params_layout_matches_akari_structs(self):
        self.assertEqual(P.pack_params([('u8', 1), ('s16', -2), ('s32', 3)]), struct.pack('<Bxhi', 1, -2, 3))
        self.assertEqual(len(P.pack_params([('bool', True), ('vec3', (1, 2, 3))])), 20)
        self.assertEqual(len(P.pack_params([('u8', 1)])), 1)

    def test_oracle_basics(self):
        o = Oracle(tiny_world())
        (h, t), m = o.floor(F.raw((20, 5, 20)), 0)
        self.assertEqual((h, t['surface']), (0, 1))
        (h, t), m = o.floor(F.raw((50, 5, 50)), 0)
        self.assertEqual(t['surface'], 2)
        self.assertIsNone(o.floor(F.raw((20, -1, 20)), 0)[0])


def _parse(lines):
    assert lines and lines[-1] == 'done', lines[-5:]
    return [list(map(int, l.split())) for l in lines[:-1]]


@needs_tools
class DifferentialTests(unittest.TestCase):
    """The console's answers against exact arithmetic over the same triangles."""

    EPS = 0.003          # decisions closer than this (units) to changing are not compared
    HTOL = 0.001         # height error allowed
    PTOL = 0.002         # push error allowed per wall

    def run_queries(self, w, recs, frames):
        with tempfile.TemporaryDirectory() as tmp:
            lines = F.run_cart(tmp, 'queries.akr', {'PACK': ('u8', encode(w)), 'QUERIES': ('WpQuery', b''.join(recs))},
                               frames=frames)
        return _parse(lines)

    def check_world(self, w, seed, nq=1200):
        S = 1 << w.cell_shift
        rng = random.Random(seed)
        oracle = Oracle(w)
        pack = decode(encode(w))
        stats = {'floor': [0, 0], 'ceiling': [0, 0], 'push': [0, 0], 'ray': [0, 0]}
        worst = {'floor': 0.0, 'ceiling': 0.0, 'push': 0.0, 'ray': 0.0}
        recs, checks = [], []
        layers = set()
        walls = [t for t in oracle.tris if t['kind'] == P.KIND_WALL]
        pushed = 0

        def rp(lo=-2.0, hi=28.0):
            x = rng.uniform(-S, 2 * S)
            z = rng.uniform(-S, S)
            r = rng.random()
            if r < 0.15:                     # on a cell seam
                x = float(rng.choice([-S, 0, S, 2 * S - 1e-5]))
            elif r < 0.25:
                z = float(rng.choice([-S, 0, S - 1e-5]))
            elif r < 0.3:                    # a hair either side of a seam
                x = rng.choice([0, S]) + rng.choice([-1, 1]) * rng.choice([1, 3, 20]) / ONE
            return F.raw((x, rng.uniform(lo, hi), z))

        for k in range(nq):
            if k == nq // 2:
                recs.append(F.query(F.OP_LAYER, arg=0 | 1 << 16))
                checks.append(None)
                layers = {'L1'}
            kind = rng.choice(['floor', 'ceiling', 'push', 'ray'])
            p = rp()
            if kind == 'floor':
                above = fx(rng.choice([0, 0.5, 2, 30]))
                recs.append(F.query(F.OP_FLOOR, p, (above, 0, 0)))
                checks.append((kind, p, above, frozenset(layers)))
            elif kind == 'ceiling':
                below = fx(rng.choice([0, 0.5, 2, 30]))
                recs.append(F.query(F.OP_CEILING, p, (below, 0, 0)))
                checks.append((kind, p, below, frozenset(layers)))
            elif kind == 'push':
                r = fx(rng.uniform(0.1, 1.0))
                if rng.random() < 0.6:       # beside a wall, within the radius of its plane
                    t = rng.choice(walls)
                    u, v = rng.random(), rng.random()
                    if u + v > 1:
                        u, v = 1 - u, 1 - v
                    a, b, c = t['v']
                    n = t['n']
                    nl = math.sqrt(sum(x * x for x in n))
                    off = rng.uniform(-0.9, 0.9) * r / nl
                    p = tuple(int(a[i] + u * (b[i] - a[i]) + v * (c[i] - a[i]) + off * n[i]) for i in range(3))
                recs.append(F.query(F.OP_PUSH, p, (r, 0, 0)))
                checks.append((kind, p, r, frozenset(layers)))
            else:
                ln = rng.uniform(0.5, S / 2)
                a1, a2 = rng.uniform(0, 2 * math.pi), rng.uniform(-1.2, 1.2)
                d = (math.cos(a1) * math.cos(a2) * ln, math.sin(a2) * ln, math.sin(a1) * math.cos(a2) * ln)
                b = tuple(p[i] + fx(d[i]) for i in range(3))
                recs.append(F.query(F.OP_RAY, p, b))
                checks.append((kind, p, b, frozenset(layers)))
        out = iter(self.run_queries(w, recs, frames=400))
        for chk in checks:
            if chk is None:
                continue
            got = next(out)
            kind, p, arg, lay = chk
            if kind in ('floor', 'ceiling'):
                best, margin = (oracle.floor if kind == 'floor' else oracle.ceiling)(p, arg, lay)
                if margin < self.EPS:
                    stats[kind][1] += 1
                    continue
                stats[kind][0] += 1
                if best is None:
                    self.assertEqual(got[0], 0, f'{kind} at {p}: console found {got}, exact none')
                    continue
                h, t = best
                self.assertEqual(got[0], 1, f'{kind} at {p}: console found none, exact {float(h) / ONE}')
                self.assertEqual(got[3], t['tag'], f'{kind} at {p}: triangle')
                self.assertEqual(got[2], t['surface'])
                err = abs(got[1] - float(h)) / ONE
                worst[kind] = max(worst[kind], err)
                self.assertLess(err, self.HTOL, f'{kind} at {p}: height')
            elif kind == 'push':
                ij, lx, lz = pack.cell_of(p[0], p[2])
                c = pack.cells.get(ij)
                order = []
                if c and c.coll:
                    order = [c.coll.walls[i][5] >> 16 for i in c.coll.bucket(lx, lz)[1]]
                (x, z), count, margin = oracle.push(p, arg, order, lay)
                if margin < self.EPS:
                    stats[kind][1] += 1
                    continue
                stats[kind][0] += 1
                self.assertEqual(got[2], count, f'push at {p}: walls')
                pushed += count > 0
                err = max(abs(got[0] - x), abs(got[1] - z)) / ONE
                worst[kind] = max(worst[kind], err)
                self.assertLess(err, self.PTOL * max(1, count), f'push at {p}')
            else:
                hit, margin = oracle.ray(p, arg, lay)
                if margin < self.EPS:
                    stats[kind][1] += 1
                    continue
                stats[kind][0] += 1
                if hit is None:
                    self.assertEqual(got[0], 0, f'ray {p} -> {arg}: console hit {got}')
                    continue
                t, tri, df = hit
                self.assertEqual(got[0], 1, f'ray {p} -> {arg}: console missed')
                self.assertEqual(got[2], tri['tag'], f'ray {p} -> {arg}: triangle')
                err = abs(got[1] / ONE - float(t))
                worst[kind] = max(worst[kind], err * df)
                self.assertLess(err, 4e-4 / df + 4 / ONE, f'ray {p} -> {arg}: t')
        if VERBOSE:
            print(f'\n  shift {w.cell_shift}: compared/skipped {stats}; pushed {pushed}; worst {worst}')
        for kind, (done, skipped) in stats.items():
            self.assertGreater(done, skipped + 20, f'{kind}: too few decisive cases')
        self.assertGreater(pushed, 50)
        return stats

    def test_random_worlds_at_three_cell_sizes(self):
        for shift, seed in ((6, 11), (5, 12), (7, 13)):
            with self.subTest(shift=shift):
                w, _ = F.random_world(seed, shift)
                self.check_world(w, seed + 100)

    def test_heightfield_is_watertight(self):
        """Every point over a heightfield has a floor, including points exactly on shared edges,
        vertices and cell seams, at the surface's height."""
        for shift in (5, 6):
            w, step, n = F.heightfield_world(7, shift)
            S = 1 << shift
            oracle = Oracle(w)
            rng = random.Random(shift)
            pts = []
            for _ in range(500):
                tx, tz = rng.randrange(n), rng.randrange(n)
                f = rng.random()
                choice = rng.randrange(5)
                if choice == 0:      # a vertex
                    x, z = tx * step, tz * step
                elif choice == 1:    # an edge along x
                    x, z = (tx + f) * step, tz * step
                elif choice == 2:    # an edge along z
                    x, z = tx * step, (tz + f) * step
                elif choice == 3:    # a diagonal
                    x, z = (tx + f) * step, (tz + (f if (tx + tz) % 2 == 0 else 1 - f)) * step
                else:                # a cell seam
                    x, z = float(S), rng.uniform(0, n * step)
                    if rng.random() < 0.5:
                        x, z = z, x
                x = min(max(x, 0.0), n * step - 1e-4)
                z = min(max(z, 0.0), n * step - 1e-4)
                pts.append(F.raw((x, 10, z)))
            recs = [F.query(F.OP_FLOOR, p, (fx(0), 0, 0)) for p in pts]
            with self.subTest(shift=shift):
                got = self.run_queries(w, recs, frames=60)
                worst = 0.0
                for p, g in zip(pts, got):
                    self.assertEqual(g[0], 1, f'no floor at {[c / ONE for c in p]}')
                    best, _ = oracle.floor(p, 0)
                    err = abs(g[1] - float(best[0])) / ONE
                    worst = max(worst, err)
                    self.assertLess(err, self.HTOL)
                if VERBOSE:
                    print(f'\n  heightfield shift {shift}: worst height error {worst:.6f}')

    def test_moving_object_in_its_own_frame(self):
        w, etris = F.random_world(21, 6)
        oracle = Oracle.from_tris(etris)
        pack = decode(encode(w))
        ent = [e for c in pack.cells.values() for e in c.entities][0]
        rng = random.Random(4)
        recs, checks = [], []
        for _ in range(300):
            p = F.raw((rng.uniform(-4, 4), rng.uniform(-1, 5), rng.uniform(-3, 3)))
            op = rng.choice(['floor', 'ceiling', 'push', 'ray'])
            if op == 'floor':
                recs.append(F.query(F.OP_EFLOOR, p, (fx(1), 0, 0), arg=ent['number']))
            elif op == 'ceiling':
                recs.append(F.query(F.OP_ECEILING, p, (fx(1), 0, 0), arg=ent['number']))
            elif op == 'push':
                recs.append(F.query(F.OP_EPUSH, p, (fx(0.5), 0, 0), arg=ent['number']))
            else:
                b = F.raw((rng.uniform(-4, 4), rng.uniform(-1, 5), rng.uniform(-3, 3)))
                recs.append(F.query(F.OP_ERAY, p, b, arg=ent['number']))
                p = (p, b)
            checks.append((op, p))
        got = self.run_queries(w, recs, frames=60)
        coll = ent['coll']
        compared = 0
        for (op, p), g in zip(checks, got):
            if op in ('floor', 'ceiling'):
                best, margin = (oracle.floor if op == 'floor' else oracle.ceiling)(p, fx(1))
                if margin < self.EPS:
                    continue
                self.assertEqual(g[0], 0 if best is None else 1, f'{op} at {p}')
                if best:
                    self.assertEqual(g[3], best[1]['tag'])
                    self.assertLess(abs(g[1] - float(best[0])) / ONE, self.HTOL)
            elif op == 'push':
                order = [coll.walls[i][5] >> 16 for i in coll.bucket(p[0], p[2])[1]]
                (x, z), count, margin = oracle.push(p, fx(0.5), order)
                if margin < self.EPS:
                    continue
                self.assertEqual(g[2], count)
                self.assertLess(max(abs(g[0] - x), abs(g[1] - z)) / ONE, self.PTOL * max(1, count))
            else:
                hit, margin = oracle.ray(*p)
                if margin < self.EPS:
                    continue
                self.assertEqual(g[0], 0 if hit is None else 1, f'ray {p}')
                if hit:
                    self.assertEqual(g[2], hit[1]['tag'])
            compared += 1
        self.assertGreater(compared, 200)


def _view_planes(eye_local, yaw, pitch, near, far, fx_=1.299, fy_=1.732):
    """The six planes wp_draw() culls with, in float, for camera_look(eye_local, yaw, pitch)."""
    sy, cy, sp, cp = math.sin(yaw), math.cos(yaw), math.sin(pitch), math.cos(pitch)
    right = (cy, 0.0, -sy)
    up = (-sy * sp, cp, -cy * sp)
    fwd = (sy * cp, sp, cy * cp)

    def row(v, k):
        return [v[0] * k, v[1] * k, v[2] * k, -sum(v[i] * eye_local[i] for i in range(3)) * k]
    r0, r1, r3 = row(right, fx_), row(up, fy_), row(fwd, 1.0)
    kx, ky = 1 / math.sqrt(1 + fx_ * fx_), 1 / math.sqrt(1 + fy_ * fy_)
    return [[(r3[i] + r0[i]) * kx for i in range(4)], [(r3[i] - r0[i]) * kx for i in range(4)],
            [(r3[i] + r1[i]) * ky for i in range(4)], [(r3[i] - r1[i]) * ky for i in range(4)],
            r3[:3] + [r3[3] - near], [-r3[0], -r3[1], -r3[2], far - r3[3]]]


def _sphere_test(planes, c, r, tol=0.01):
    """True / False, or None when the sphere is within tol of a plane's limit."""
    unsure = False
    for p in planes:
        d = p[0] * c[0] + p[1] * c[1] + p[2] * c[2] + p[3] + r
        if d < -tol:
            return False
        if d < tol:
            unsure = True
    return None if unsure else True


def expected_view(pack, eye, yaw, pitch, layers_on, ring, near_far=96.0):
    """What wp_draw() should count: near cells, placements looked at, drawn and stand-ins, each
    as (lo, hi) to allow spheres that touch a plane within rounding."""
    S = 1 << pack.cell_shift
    half = S / 2
    ci, cj = math.floor(eye[0]) >> pack.cell_shift, math.floor(eye[2]) >> pack.cell_shift
    origin = (ci * S + half, 0, cj * S + half)
    local = tuple(eye[k] - origin[k] for k in range(3))
    names = [l[0] for l in pack.layers]
    out = {'near': [0, 0], 'placements': [0, 0], 'drawn': [0, 0], 'standins': [0, 0]}

    def count(key, verdict, n=1):
        if verdict is True:
            out[key][0] += n
            out[key][1] += n
        elif verdict is None:
            out[key][1] += n

    def sphere(s, di, dj):
        return (s[0] / ONE + di * S, s[1] / ONE, s[2] / ONE + dj * S), s[3] / ONE

    if ring >= 2:
        far = S * (2 * ring + 1) * 3 / 4
        planes = _view_planes(local, yaw, pitch, half, far)
        for dj in range(-ring, ring + 1):
            for di in range(-ring, ring + 1):
                c = pack.cells.get((ci + di, cj + dj))
                if max(abs(di), abs(dj)) < 2 or c is None or not c.standin:
                    continue
                count('standins', _sphere_test(planes, *sphere(c.standin_bounds, di, dj)))
    planes = _view_planes(local, yaw, pitch, 0.1, near_far)
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            c = pack.cells.get((ci + di, cj + dj))
            if c is None or not c.placements:
                continue
            out['near'][0] += 1
            out['near'][1] += 1
            cv = _sphere_test(planes, *sphere(c.bounds, di, dj))
            count('placements', cv, len(c.placements))
            if cv is False:
                continue
            mask = sum(1 << k for k, lid in enumerate(c.layers) if names[lid] in layers_on)
            for p in c.placements:
                if p['mask'] and not p['mask'] & mask:
                    continue
                v = _sphere_test(planes, *sphere(p['sphere'], di, dj))
                count('drawn', None if (v is not False and cv is None) else v)
    return out


DEMO_VIEWS = [  # as tests/worldpack/demo.akr's VIEWS: eye, yaw, pitch, layers on
    ((32, 2, 4), 0.0, 0.0, {'bridge_up'}),
    ((8, 20, 32), 1.5708, -0.15, {'bridge_up'}),
    ((8, 20, 32), 1.5708, -0.15, {'bridge_up', 'gate'}),
    ((8, 20, 32), 1.5708, -0.15, {'bridge_down'}),
    ((70, 30, -20), -0.4, -0.6, {'bridge_up'}),
    ((32, 5, 32), 0.0, 1.5, {'bridge_up'}),
]


def _fixed_float(v):
    """A literal as the compiler rounds it: to the nearest 1/65536."""
    return round(v * ONE) / ONE


@needs_tools
class DemoTests(unittest.TestCase):
    """The demonstration cart: drawing, culling, layers, pictures, a body and entities."""

    def run_demo(self, scene, frames=2, dump=None):
        marker = F.box_mesh((-0.5, 0, -0.5), (0.5, 1, 0.5), meshlib_rgb(255, 255, 0))
        with tempfile.TemporaryDirectory() as tmp:
            dpath = Path(tmp) / 'shot.ppm' if dump else None
            lines = F.run_cart(tmp, 'demo.akr', {'PACK': ('u8', encode(F.demo_world())), 'MARKER': ('Mesh', marker)},
                               {'SCENE': scene}, frames=frames, dump=dpath)
            pix = F.read_ppm(dpath) if dump else None
        return lines, pix

    def test_drawing_culling_and_layers(self):
        lines, _ = self.run_demo(1, frames=len(DEMO_VIEWS) + 2)
        pack = decode(encode(F.demo_world()))
        views = {}
        tris = {}
        for l in lines:
            f = l.split()
            if f[0] == 'view':
                views[int(f[1])] = list(map(int, f[2:]))
            elif f[0] == 'tris':
                tris[int(f[1])] = int(f[2])
        self.assertEqual(len(views), len(DEMO_VIEWS))
        for k, (eye, yaw, pitch, layers) in enumerate(DEMO_VIEWS):
            exp = expected_view(pack, eye, _fixed_float(yaw), _fixed_float(pitch), layers, ring=6)
            near, placements, drawn, standins, cycles, arena = views[k]
            with self.subTest(view=k):
                self.assertEqual(near, exp['near'][0])
                for name, got in (('placements', placements), ('drawn', drawn), ('standins', standins)):
                    lo, hi = exp[name]
                    self.assertTrue(lo <= got <= hi, f'{name}: {got} not in {lo}..{hi}')
            if VERBOSE:
                print(f'\n  view {k}: {views[k]} tris {tris.get(k)} expected {exp}')
        self.assertEqual(views[1][3], 1, 'the far cell\'s stand-in is drawn looking east')
        self.assertEqual(views[0][3], 0, 'and not looking north')
        self.assertEqual(views[2][2], views[1][2] + 1, 'the gate layer adds its placement')
        self.assertGreater(tris[2], tris[1])
        self.assertEqual(tris[5], 0, 'nothing drawn looking at the sky')
        self.assertGreater(tris[0], 100)

    def colours(self, pix):
        w, h, px = pix
        cnt = {'magenta': 0, 'blue': 0, 'yellow': 0}
        for k in range(w * h):
            r, g, b = px[3 * k], px[3 * k + 1], px[3 * k + 2]
            if r > 200 and g < 40 and b > 200:
                cnt['magenta'] += 1
            elif r < 40 and g < 40 and b > 200:
                cnt['blue'] += 1
            elif r > 200 and g > 200 and b < 40:
                cnt['yellow'] += 1
        return cnt

    def test_pictures(self):
        """The far stand-in (magenta) shows looking east, the gate (blue) only with its layer
        on, and a game object drawn relative to wp_view_origin() (the yellow marker on coin 0)
        lands where the world put the coin."""
        _, north = self.run_demo(10, frames=3, dump=True)
        _, east = self.run_demo(11, frames=3, dump=True)
        _, gate = self.run_demo(12, frames=3, dump=True)
        n, e, g = self.colours(north), self.colours(east), self.colours(gate)
        if VERBOSE:
            print(f'\n  north {n} east {e} gate {g}')
        self.assertEqual(n['magenta'], 0)
        self.assertGreater(e['magenta'], 50)
        self.assertEqual(e['blue'], 0)
        self.assertGreater(g['blue'], 50)
        self.assertGreater(n['yellow'], 10)
        # the marker's middle projects where the coin is: (24, 3.5, 44) seen from view 0
        w, h, px = north
        eye = (32, 2, 4)
        d = (24 - eye[0], 3.5 - eye[1], 44 - eye[2])
        sx = 160 + 160 * 1.299 * d[0] / d[2]
        sy = 120 - 120 * 1.732 * d[1] / d[2]
        ys = [k // w for k in range(w * h) if px[3 * k] > 200 and px[3 * k + 1] > 200 and px[3 * k + 2] < 40]
        xs = [k % w for k in range(w * h) if px[3 * k] > 200 and px[3 * k + 1] > 200 and px[3 * k + 2] < 40]
        self.assertLess(abs(sum(xs) / len(xs) - sx), 2)
        self.assertLess(abs(sum(ys) / len(ys) - sy), 2)

    def test_body(self):
        lines, _ = self.run_demo(2)
        self.assertEqual(lines[-1], 'done')
        got = {}
        for l in lines[:-1]:
            f = l.split()
            got[f[0]] = [int(x) for x in f[1:]] if f[0] in ('seam', 'outside', 'bumped', 'land_surface',
                                                             'push_walls', 'ray_kind', 'steep_floor') else int(f[1]) / ONE
        if VERBOSE:
            print('\n  ' + ' '.join(f'{k}={v}' for k, v in got.items()))
        near = lambda a, b, tol=0.002: self.assertLess(abs(a - b), tol, f'{a} != {b}')  # noqa: E731
        near(got['land_y'], 1.5)                    # on the ramp at x 23
        self.assertEqual(got['land_surface'], [F.SURF_RAMP])
        near(got['ramp_nx'], -1 / math.sqrt(5))
        near(got['ramp_ny'], 2 / math.sqrt(5))
        near(got['walk_x'], 33)
        near(got['walk_y'], 4)                      # up the ramp onto the platform
        near(got['push_x'], 39.5)                   # radius 0.5 from the block's face at x 40
        self.assertGreater(got['push_walls'][0], 10)
        near(got['corner_z'], 7.5)                  # slid along the block's north face
        near(got['ceiling_y'], 3)
        self.assertEqual(got['bumped'], [1])
        near(got['ray_t'], 0.5)
        near(got['ray_x'], 40)
        self.assertEqual(got['ray_kind'], [1])
        near(got['down_y'], 3.5)                    # the roof's top
        self.assertEqual(got['steep_floor'], [1, F.SURF_GROUND])   # the 50 degree slope is a wall
        near(got['gentle_y'], 5.03 / 2)             # the 40 degree one a floor
        near(got['gate_off_x'], 86)
        near(got['gate_on_x'], 83.5)
        near(got['gate_top'], 3)
        near(got['platform_y'], 2.5)
        self.assertEqual(got['seam'], [111])
        self.assertEqual(got['outside'], [0])

    def test_entities(self):
        lines, _ = self.run_demo(3)
        self.assertEqual(lines[-1], 'done')
        self.assertIn('entities 6', lines)
        self.assertIn(f'cell00 {F.T_COIN} 0 {fx(24)}', lines)
        self.assertIn(f'cell00 {F.T_COIN} 1 {fx(12)}', lines)
        self.assertIn(f'switch 2 {fx(1.5)} 0', lines)
        self.assertIn('bridges 01 10', lines)
        steps = {}
        cur = None
        for l in lines:
            if l.startswith('step'):
                cur = int(l.split()[1])
                steps[cur] = []
            elif cur is not None and l.startswith(('spawn', 'retire')):
                steps[cur].append(l)
        # numbers: cell (0, 0): 0, 1; (1, 0): 2 (gate layer); (5, 0): 3; (0, 1): 4; (1, 1): 5
        self.assertEqual(sorted(steps[1]), ['spawn 0', 'spawn 1', 'spawn 4', 'spawn 5'])
        self.assertEqual(steps[2], [])
        self.assertEqual(steps[3], ['spawn 2'])
        self.assertEqual(sorted(steps[4]), ['retire 0', 'retire 1', 'retire 2', 'retire 4', 'retire 5', 'spawn 3'])
        self.assertEqual(steps[4][-1], 'spawn 3', 'retiring comes before spawning')
        self.assertEqual(sorted(steps[5]), ['retire 3', 'spawn 0', 'spawn 1'])
        self.assertEqual(sorted(steps[6]), ['retire 0', 'retire 1'])

    def test_open_checks_the_version(self):
        good = encode(World(cells=[Cell(0, 0)], cell_shift=5))
        cases = [(good, 'open 1 32'),
                 (good[:6] + struct.pack('<H', 9) + good[8:], 'open 1 32'),       # a newer minor
                 (good[:13] + bytes([0x02]) + good[14:], 'open 1 32'),            # an ignorable flag
                 (good[:4] + struct.pack('<H', 2) + good[6:], 'open 0'),          # another major
                 (good[:13] + bytes([0x10]) + good[14:], 'open 0'),               # a required feature
                 (b'MEIX' + good[4:], 'open 0')]
        for data, want in cases:
            with tempfile.TemporaryDirectory() as tmp:
                lines = F.run_cart(tmp, 'open.akr', {'PACK': ('u8', data)})
            self.assertEqual(lines[-1], want)

    def test_palettes_and_textures(self):
        lines, _ = self.run_demo(4)
        self.assertEqual(lines[-1], 'done')
        vals = dict(l.split(' ', 1) for l in lines[:-1])
        self.assertEqual(vals['day'], '32767 31 992')
        self.assertEqual(vals['night'], '1057 16 512')
        self.assertEqual(vals['texture'], '0 1 255')
        for d, a, b in zip(*(map(int, vals[k].split()) for k in ('dusk', 'day', 'night'))):
            for sh in (0, 5, 10):          # each 5-bit channel half way, give or take one
                ca, cb, cd = (a >> sh) & 31, (b >> sh) & 31, (d >> sh) & 31
                self.assertLessEqual(abs(cd - (ca + cb) / 2), 1)


def meshlib_rgb(r, g, b):
    return (r & 255) | ((g & 255) << 8) | ((b & 255) << 16)


@needs_tools
def ground_test_world(strip=True, crate=True, ground=True):
    """tests/worldverify's mis-sorted pair alone: a runway strip (blue, z 1..17) and a crate (red)
    standing on it at z 12..13, seen from the strip's near end (tests/worldpack/ground.akr), where
    the strip's average depth is nearer than the crate's front: one near pass draws the strip over
    the crate's lower part."""
    c = Cell(0, 0)
    if strip:
        m = F.meshlib.Mesh()
        a, b, cc, d = m.vertex(-1, 0.01, -8), m.vertex(1, 0.01, -8), m.vertex(-1, 0.01, 8), m.vertex(1, 0.01, 8)
        m.quad([a, b, cc, d], [meshlib_rgb(60, 60, 200)])
        c.placements.append(Placement(m.pack(), (27, 0, 9), tag=50, ground=ground))
    if crate:
        c.placements.append(Placement(F.box_mesh((-1, 0, -0.5), (1, 1.5, 0.5), meshlib_rgb(200, 60, 60)),
                                      (27, 0.01, 12.5), tag=51))
    return World(cells=[c], cell_shift=5)


@needs_tools
class GroundTests(unittest.TestCase):
    """Ground-first drawing on the console: an object standing on the ground is overdrawn by it
    in one near pass and whole with the ground drawn first."""

    def shot(self, data, ground_first=True):
        with tempfile.TemporaryDirectory() as tmp:
            dump = Path(tmp) / 'shot.ppm'
            lines = F.run_cart(tmp, 'ground.akr', {'PACK': ('u8', data)},
                               {'GROUND': 'true' if ground_first else 'false'}, frames=2, dump=dump)
            w, h, px = F.read_ppm(dump)
        red = sum(1 for k in range(w * h) if px[3 * k] > 150 and px[3 * k + 2] < 100)
        blue = sum(1 for k in range(w * h) if px[3 * k + 2] > 150 and px[3 * k] < 100)
        return lines[-1], red, blue

    def test_object_on_ground_is_no_longer_overdrawn(self):
        pack = encode(ground_test_world())
        _, alone, _ = self.shot(encode(ground_test_world(strip=False)))
        line, red, blue = self.shot(pack)
        off_line, off_red, off_blue = self.shot(pack, ground_first=False)
        old_line, old_red, _ = self.shot(pack[:6] + struct.pack('<H', 0) + pack[8:])    # read as 1.0
        if VERBOSE:
            print(f'\n  crate alone {alone}, ground first {red} (strip {blue}), '
                  f'one pass {off_red} (strip {off_blue}), as 1.0 {old_red}')
        self.assertGreater(alone, 1000)
        self.assertEqual(line, 'drawn 2 ground 1')
        self.assertEqual(red, alone, 'the whole crate is drawn over the ground')
        self.assertGreater(blue, 1000)
        self.assertEqual(off_line, 'drawn 2 ground 0')
        self.assertLess(off_red, alone - 100, 'one near pass draws the strip over the crate')
        self.assertEqual(off_red + off_blue, red + blue)
        self.assertEqual((old_line, old_red), (off_line, off_red), 'a 1.0 reading is one near pass')


GREEN = meshlib_rgb(40, 250, 40)


def object_test_world(platform=True, coin=True, pair=False):
    """A ledge like test_room's (a 3 x 2 x 3 block of triangles, grey) on ground (flagged ground,
    blue), and a coin (an entity, green; fixture.coin_mesh()) floating 0.2 above it, for
    tests/worldpack/objects.akr. pair adds a second coin (red) beside the first."""
    c = Cell(0, 0)
    g = F.meshlib.Mesh()
    a, b, cc, d = g.vertex(-16, 0, -16), g.vertex(16, 0, -16), g.vertex(-16, 0, 16), g.vertex(16, 0, 16)
    g.quad([a, b, cc, d], [meshlib_rgb(40, 40, 200)])
    c.placements.append(Placement(g.pack(), (16, 0, 16), tag=1, ground=True))
    if platform:
        c.placements.append(Placement(F.tri_box_mesh((-1.5, 0, -1.5), (1.5, 2, 1.5), meshlib_rgb(140, 140, 140)),
                                      (16, 0, 16), tag=2))
    if coin:
        c.entities.append(Entity(1, (16, 2.5, 16), mesh=F.coin_mesh(GREEN)))
    if pair:
        c.entities.append(Entity(1, (16.45, 2.5, 16.3), mesh=F.coin_mesh(meshlib_rgb(250, 40, 40))))
    return World(cells=[c], cell_shift=5)


@needs_tools
class ObjectTests(unittest.TestCase):
    """wp_draw_object() on the console (tests/worldpack/objects.akr): a coin above a ledge is
    overdrawn by the ledge's top when sorted by its own depth, and whole when drawn as an object;
    from below the ledge's top the ledge's side still hides it."""
    ABOVE = (16.812, 3.1339, 14.9097, 323.325, -25.0)     # 1.5 units from the coin, above it
    FOLLOW = (13.4, 4.6, 19.5, 143.3, -25.0)             # a follow camera's distance
    BELOW = (13.6, 1.8, 15.5, 76.0, 12.0)                # below the ledge's top, looking up

    def shot(self, view, mode, platform=True):
        ex, ey, ez, yd, pd = view
        with tempfile.TemporaryDirectory() as tmp:
            dump = Path(tmp) / 'shot.ppm'
            lines = F.run_cart(tmp, 'objects.akr', {'PACK': ('u8', encode(object_test_world(platform=platform)))},
                               {'MODE': mode, 'EX': ex, 'EY': ey, 'EZ': ez, 'YAW': math.radians(yd),
                                'PITCH': math.radians(pd), 'BIAS': 1.5}, frames=2, dump=dump)
            w, h, px = F.read_ppm(dump)
        green = sum(1 for k in range(w * h) if px[3 * k + 1] > 200 and px[3 * k] < 100)
        f = lines[-1].split()       # drawn N cycles C bounds C radius low (thousandths)
        st = dict(zip(f[0:6:2], (int(x) for x in f[1:6:2])))
        st['radius'], st['low'] = int(f[6]), int(f[7])
        return green, st

    def test_an_object_on_a_ledge(self):
        for name, view in (('above', self.ABOVE), ('follow', self.FOLLOW), ('below', self.BELOW)):
            alone, _ = self.shot(view, 1, platform=False)
            plain, st0 = self.shot(view, 0)
            entities, st1 = self.shot(view, 1)
            character, st2 = self.shot(view, 2)
            if VERBOSE:
                print(f'\n  {name}: coin alone {alone}, mesh_at {plain}, wp_draw_entities {entities}, '
                      f'wp_draw_object {character}; cycles {st0["cycles"]}, {st1["cycles"]}, {st2["cycles"]}, '
                      f'wp_mesh_bounds {st1["bounds"]}')
            self.assertGreater(alone, 300)
            self.assertEqual(entities, character)
            self.assertEqual((st0['drawn'], st1['drawn'], st2['drawn']), (1, 1, 1))
            if name == 'below':
                self.assertEqual(entities, plain, 'from below the top, sorted as before')
                self.assertLess(entities, alone - 50, 'the ledge hides the bottom of the coin')
            else:
                self.assertEqual(entities, alone, 'the whole coin is drawn over the ledge')
                self.assertLess(plain, alone - 40, 'by its own depth, the top is drawn over the coin')
        # the costs: wp_draw_object() over mesh_at(), and the bounds scan (100 vertices)
        self.assertLess(st2['cycles'] - st0['cycles'], 400)
        self.assertLess(st1['bounds'], 100 * 18 + 300)
        self.assertEqual((st1['radius'], st1['low']), (310, -286))     # sqrt(0.3^2 + 0.04^2) + 1/128

    def test_an_object_out_of_view_is_culled(self):
        _, st = self.shot((16.0, 3.0, 22.0, 0.0, 0.0), 1)        # looking away from the coin
        _, st0 = self.shot((16.0, 3.0, 22.0, 0.0, 0.0), 0)
        if VERBOSE:
            print(f'\n  culled: wp_draw_entities {st["cycles"]} cycles, mesh_at {st0["cycles"]}')
        self.assertEqual((st['drawn'], st0['drawn']), (0, 1))
        self.assertLess(st['cycles'], st0['cycles'] - st['bounds'] / 2)     # most of it the bounds scan


class CostTests(unittest.TestCase):
    """Cycles per query and per frame in fixture.bench_world(): a 64-unit cell holds 2,128
    floors, 320 walls and 80 ceilings (a heightfield of 2-unit quads and 40 buildings), and 100
    small boxes as placements."""

    def test_costs(self):
        rng = random.Random(1)
        pts = b''.join(struct.pack('<4i', fx(rng.uniform(1, 191)), fx(1.3), fx(rng.uniform(1, 191)), 0)
                       for _ in range(400))
        with tempfile.TemporaryDirectory() as tmp:
            lines = F.run_cart(tmp, 'bench.akr', {'PACK': ('u8', encode(F.bench_world(100))), 'PTS': ('vec4', pts)},
                               frames=60)
        self.assertEqual(lines[-1], 'done')
        got = {}
        for l in lines:
            f = l.split()
            got.setdefault(f[0], []).append([int(x) for x in f[1:]])
        if VERBOSE:
            print('\n  ' + '\n  '.join(lines))
        per = {k: got[k][0][0] for k in ('cell', 'floor', 'ceiling', 'push', 'ray4', 'ray15')}
        # Tsumiki's floor query among 41 solids took about 2,000 cycles (docs/WORLDKIT.md)
        self.assertLess(per['floor'], 1000)
        self.assertLess(per['ceiling'], 1000)
        self.assertLess(per['push'], 1000)
        self.assertLess(per['ray4'], 5000)
        self.assertLess(per['ray15'], 15000)
        culled = got['culled'][0]
        self.assertEqual(culled[2], 0)
        self.assertLess(culled[0] / culled[1], 100, 'cycles per placement culled')


def lod_world(seed=0, n=30, share=True):
    """One 64-unit cell of boxes, most with levels of detail (two coarser boxes and, for some, a
    cull distance), a few without, sets shared between placements when share is set."""
    rng = random.Random(seed)
    tall = F.box_mesh((-1, 0, -1), (1, 4, 1), meshlib_rgb(200, 200, 200))
    mid = F.box_mesh((-1, 0, -1), (1, 3, 1), meshlib_rgb(200, 120, 60))
    low = F.box_mesh((-1, 0, -1), (1, 2, 1), meshlib_rgb(60, 120, 200))
    sets = [P.Lod([(12, mid), (24, low)], band=1.0), P.Lod([(8, mid), (20, low), (40, None)], band=2.0),
            P.Lod([(15.5, low), (30, None)], band=0.5)]
    pls = []
    for k in range(n):
        lod = None if k % 7 == 3 else (sets[k % 3] if share else P.Lod(list(sets[k % 3].levels), sets[k % 3].band))
        pls.append(Placement(tall, (rng.uniform(4, 60), 0, rng.uniform(4, 60)), rng.choice([0, 90, 30]), tag=k,
                             ground=k % 11 == 5, lod=lod))
    return World(cells=[Cell(0, 0, placements=pls), Cell(1, 0, placements=[Placement(tall, (70, 0, 10))])])


class LodEncoderTests(unittest.TestCase):
    def test_round_trip_and_pooling(self):
        w = lod_world()
        data = encode(w)
        pack = decode(data)
        self.assertEqual((pack.minor, struct.unpack_from('<H', data, 14)[0]), (3, 80))
        c = pack.cells[(0, 0)]
        ordered = [p for p in w.cells[0].placements if p.ground] + [p for p in w.cells[0].placements if not p.ground]
        offs = set()
        for src, got in zip(ordered, c.placements):
            self.assertEqual(got['tag'], src.tag)
            if src.lod is None:
                self.assertIsNone(got['lod'])
                continue
            rows = got['lod']['rows']
            self.assertEqual(len(rows), len(src.lod.levels))
            for (d, m), (at2, out2, in2, mo) in zip(src.lod.levels, rows):
                self.assertEqual(at2, P.lod_square(d))
                self.assertEqual((out2, in2), (P.lod_square(d + src.lod.band), P.lod_square(d - src.lod.band)))
                self.assertEqual(mo == 0, m is None)
                if m is not None:
                    self.assertEqual(data[mo:mo + len(m)], m)
            offs.add(got['lod']['off'])
        self.assertEqual(len(offs), 3, 'one set per distinct set, shared')
        self.assertEqual(pack.lod_slots, len(c.placements))
        self.assertIsNone(pack.cells[(1, 0)].placements[0]['lod'])
        self.assertEqual(struct.unpack_from('<II', data, pack.cells[(1, 0)].off + 80), (0, 0))
        # the sphere holds every level (here level 0, the tallest)
        self.assertEqual(c.placements[0]['sphere'], decode(encode(World(cells=[Cell(0, 0, placements=[
            Placement(ordered[0].mesh, ordered[0].position, ordered[0].yaw)])]))).cells[(0, 0)].placements[0]['sphere'])

    def test_without_levels_and_older_packs(self):
        plain = World(cells=[Cell(0, 0, placements=[Placement(F.box_mesh((-1, 0, -1), (1, 2, 1), 1), (8, 0, 8))])])
        data = encode(plain)
        pack = decode(data)
        self.assertEqual((pack.near_far, pack.lod_slots), (0, 0))
        self.assertEqual(struct.unpack_from('<iI', data, 72), (0, 0))
        # read as 1.2: the cell's LOD words are reserved there and the header's are past 72
        lod = encode(lod_world())
        old = decode(lod[:6] + struct.pack('<H', 2) + lod[8:])
        self.assertTrue(all(p['lod'] is None for p in old.cells[(0, 0)].placements))
        self.assertEqual((old.near_far, old.lod_slots), (0, 0))
        nf = World(cells=plain.cells, near_far=48)
        self.assertEqual(decode(encode(nf)).near_far, fx(48))

    def test_limits(self):
        m = F.box_mesh((-1, 0, -1), (1, 2, 1), 1)
        for lod, message in ((P.Lod([]), 'levels'), (P.Lod([(10, m)] * 9), 'levels'),
                             (P.Lod([(10, None), (20, m)]), 'only the last'), (P.Lod([(10, m), (10, m)]), 'increase'),
                             (P.Lod([(10, m), (13, m)], band=2), 'increase'), (P.Lod([(3, m)], band=2), 'increase'),
                             (P.Lod([(1500, m)]), 'within'), (P.Lod([(10, m)], band=-1), 'band')):
            with self.subTest(message=message), self.assertRaisesRegex(PackError, message):
                encode(World(cells=[Cell(0, 0, placements=[Placement(m, (8, 0, 8), lod=lod)])]))
        with self.assertRaisesRegex(PackError, 'near_far'):
            encode(World(cells=[Cell(0, 0)], near_far=0))

    def test_malformed_levels_are_refused(self):
        good = encode(lod_world())
        pack = decode(good)
        c = pack.cells[(0, 0)]
        p = next(p for p in c.placements if p['lod'] and p['lod']['cull'])
        so = p['lod']['off']
        cases = [(c.off + 84, '<I', 999), (c.off + 80, '<I', len(good)), (76, '<I', 3), (p['lod_field'], '<I', 6),
                 (so, '<B', 0), (so, '<B', 9), (so + 1, '<B', 0), (so + 8 + 16 + 8, '<i', 0),
                 (so + 8, '<i', fx(10000)), (so + 8 + 12, '<I', 0), (72, '<i', -5)]
        for at, fmt, value in cases:
            bad = bytearray(good)
            struct.pack_into(fmt, bad, at, value)
            with self.subTest(at=at, value=value), self.assertRaises(PackError):
                decode(bytes(bad))
        short = bytearray(good)
        struct.pack_into('<H', short, 14, 72)
        with self.assertRaisesRegex(PackError, 'header'):
            decode(bytes(short))

    def test_level_rule(self):
        rows = P.lod_rows(P.Lod([(10, b'x' * 0 or F.box_mesh((0, 0, 0), (1, 1, 1), 1)), (20, None)], band=2))
        d = lambda u: P.lod_square(u)
        self.assertEqual([P.lod_level(rows, d(u)) for u in (0, 9.9, 10, 19.9, 20, 50)], [0, 0, 1, 1, 2, 2])
        # inside the band the level drawn before is kept; past it, it changes
        self.assertEqual([P.lod_level(rows, d(u), 0) for u in (9, 11.9, 12, 15)], [0, 0, 1, 1])
        self.assertEqual([P.lod_level(rows, d(u), 1) for u in (15, 8.1, 7.9)], [1, 1, 0])
        self.assertEqual([P.lod_level(rows, d(u), 2) for u in (25, 18.1, 17.9)], [2, 2, 1])
        self.assertEqual([P.lod_level(rows, d(u), fine=True) for u in (11.9, 12, 21.9, 22)], [0, 1, 1, 2])


@needs_tools
class LodTests(unittest.TestCase):
    """The reader's level choices against lod_level(), replayed in order; its cost."""

    def run_lod(self, w, recs, eye=(32.0, 32.0, 0.0)):
        consts = {'PACK_EYE_X': f'{eye[0]:.4f}', 'PACK_EYE_Z': f'{eye[1]:.4f}', 'PACK_EYE_YAW': f'{eye[2]:.4f}'}
        with tempfile.TemporaryDirectory() as tmp:
            lines = F.run_cart(tmp, 'lod.akr', {'PACK': ('u8', encode(w)), 'QUERIES': ('WpLodQuery', b''.join(recs))},
                               consts, frames=len(recs) // 100 + 5)
        self.assertEqual(lines[-1], 'done')
        return lines

    def test_choices_match_the_rule(self):
        w = lod_world(2)
        data = encode(w)
        pack = decode(data)
        cell = pack.cells[(0, 0)]
        rng = random.Random(3)
        recs, want = [], []
        state = {}
        targets = [k for k, p in enumerate(cell.placements) if p['lod']]
        for walk in range(12):
            k = rng.choice(targets)
            p = cell.placements[k]
            s = p['sphere']
            start = rng.uniform(0, 50)
            fine = walk % 5 == 4
            for step in range(60):
                # toward and away from the placement, hovering about switch distances
                dist = abs(start + 25 * math.sin(step / 6) + rng.uniform(-0.6, 0.6))
                ang = rng.uniform(0, math.tau) if step == 0 else ang
                eye = (s[0] / ONE + 32 + dist * math.cos(ang), 1.5, s[2] / ONE + 32 + dist * math.sin(ang))
                flags = (1 if fine else 0) | (2 if rng.random() < 0.03 else 0)
                if flags & 2:
                    state = {}
                raw = F.raw(eye)
                local = (raw[0] - 32 * ONE, raw[1], raw[2] - 32 * ONE)
                d2 = P.lod_d2(s, local)
                rows = p['lod']['rows']
                level = P.lod_level(rows, d2, state.get(p['lod_slot']), fine)
                state[p['lod_slot']] = level
                want.append(p['mesh'] if level == 0 else rows[level - 1][3])
                recs.append(struct.pack('<4i4i', *raw, 0, flags, 0, 0, k))
        lines = self.run_lod(w, recs)
        got = [int(l.split()[1]) for l in lines if l.startswith('q ')]
        self.assertEqual(got, want)
        self.assertGreater(len(set(got)), 3, 'every level and the cull mark are exercised')

    def test_drawing_and_cost(self):
        w = lod_world(5, n=60)
        # with the levels drawn, from the middle of the cell
        lines = self.run_lod(w, [], eye=(32.0, 2.0, 0.0))
        got = {l.split()[0]: [int(x) for x in l.split()[1:]] for l in lines if l.split()[0] in ('lod', 'flat')}
        lod, flat = got['lod'], got['flat']
        self.assertEqual(lod[1], flat[1])
        self.assertGreater(lod[3], 5)
        self.assertGreater(lod[4], 0)
        self.assertEqual(lod[2] + lod[4], flat[2])
        self.assertEqual(flat[3:], [0, 0])
        # the cost of choosing: every set's levels the same mesh as level 0, so only the choice differs
        same = lod_world(5, n=60)
        for p in same.cells[0].placements:
            if p.lod:
                p.lod = P.Lod([(d, p.mesh) for d, _ in p.lod.levels], p.lod.band)
        lines = self.run_lod(same, [], eye=(32.0, 2.0, 0.0))
        got = {l.split()[0]: [int(x) for x in l.split()[1:]] for l in lines if l.split()[0] in ('lod', 'flat')}
        per = (got['lod'][0] - got['flat'][0]) / got['lod'][2]
        if VERBOSE:
            print(f'\n  LOD choice: {per:.0f} cycles a placement drawn ({got["lod"][2]} drawn, '
                  f'{got["lod"][0]} against {got["flat"][0]} cycles)')
        self.assertLess(per, 200)


def path_world(seed=0, cell_shift=6):
    """A one-cell world with paths only: random polylines in the cell and over its edges, some
    closed, some raised, after a rail named "rail" (paths.akr looks it up by name)."""
    rng = random.Random(seed)
    S = 1 << cell_shift
    paths = [P.Path('rail', [(4, 3, 4), (20, 3, 4), (20, 6, 30), (40.5, 6.25, 30)], raised=True, surface=7)]
    for k in range(7):
        n = rng.randrange(2, 9)
        pts = []
        while len(pts) < n:
            q = (round(rng.uniform(-8, S + 8), 3), round(rng.uniform(0, 12), 3), round(rng.uniform(-8, S + 8), 3))
            if not pts or q != pts[-1]:
                pts.append(q)
        paths.append(P.Path(f'p{k}', pts, raised=k % 2 == 1, closed=n >= 3 and k % 3 == 0, surface=k))
    return World(cells=[Cell(0, 0)], cell_shift=cell_shift, paths=paths)


def path_query(op, path, arg, p=(0, 0, 0)):
    """One WpPathQuery record (paths.akr); p is raw."""
    return struct.pack('<iiii4i', op, path, fx(arg), 0, *p, 0)


class PathEncoderTests(unittest.TestCase):
    def test_round_trip(self):
        w = path_world()
        data = encode(w)
        pack = decode(data)
        self.assertEqual(struct.unpack_from('<HH', data, 4), (1, 3))
        self.assertEqual(struct.unpack_from('<H', data, 14)[0], 80)
        self.assertEqual(struct.unpack_from('<I', data, 64)[0], len(w.paths))
        self.assertEqual([p['name'] for p in pack.paths], [p.name for p in w.paths])
        for src, got in zip(w.paths, pack.paths):
            with self.subTest(path=src.name):
                stored = list(src.points) + ([src.points[0]] if src.closed else [])
                self.assertEqual([tuple(q['pos']) for q in got['points']], [F.raw(q) for q in stored])
                self.assertEqual((got['raised'], got['closed'], got['surface']), (src.raised, src.closed, src.surface))
                exact = sum(math.dist(a, b) for a, b in zip(stored, stored[1:]))
                self.assertAlmostEqual(got['length'] / ONE, exact, delta=len(stored) / ONE)
                for a, b in zip(got['points'], got['points'][1:]):
                    self.assertEqual(b['s'], a['s'] + a['len'])
                    self.assertAlmostEqual(math.hypot(*a['dir']) / ONE, 1.0, delta=4 / ONE)
                self.assertEqual((got['points'][-1]['len'], got['points'][-1]['dir']), (0, (0, 0, 0)))
        # strings are stored once: an entity's name parameter "rail" is the path's own name string
        w.cells[0].entities.append(Entity(0, (8, 0, 8), params=P.pack_params([('name', 0)]), names=[(0, 'rail')]))
        data = encode(w)
        pack = decode(data)
        name_off = struct.unpack_from('<I', data, struct.unpack_from('<I', data, 68)[0])[0]
        self.assertEqual(struct.unpack_from('<I', pack.cells[(0, 0)].entities[0]['params'])[0], name_off)

    def test_worlds_without_paths_and_older_packs(self):
        data = encode(tiny_world())
        self.assertEqual(struct.unpack_from('<II', data, 64), (0, 0))
        self.assertEqual(decode(data).paths, [])
        # read as 1.1: the header's words past 64 are not 1.1's, and are ignored
        with_paths = encode(path_world())
        self.assertEqual(decode(with_paths[:6] + struct.pack('<H', 1) + with_paths[8:]).paths, [])
        # a 1.2 header holds the path words
        short = bytearray(with_paths)
        struct.pack_into('<H', short, 14, 64)
        with self.assertRaisesRegex(PackError, 'header'):
            decode(bytes(short))

    def test_limits(self):
        def bad(paths, message):
            with self.subTest(message=message), self.assertRaisesRegex(PackError, message):
                encode(World(cells=[Cell(0, 0)], paths=paths))
        bad([P.Path('a', [(1, 1, 1)])], 'at least 2 points')
        bad([P.Path('a', [(1, 1, 1), (2, 1, 1)], closed=True)], 'closed path has at least 3')
        bad([P.Path('a', [(1, 1, 1), (1, 1, 1)])], 'no length')
        bad([P.Path('a', [(1, 1, 1), (1, 1, 1 + 1e-6)])], 'no length')
        bad([P.Path('a', [(0, 0, 0), (16000, 0, 0), (16000, 0, 900)])], 'longer than')
        bad([P.Path('a', [(0, 0, 0), (1, 0, 0)], surface=256)], 'surface')
        bad([P.Path('a', [(0, 0, 0), (1, 0, 0)]), P.Path('a', [(0, 0, 0), (2, 0, 0)])], 'distinct')
        bad([P.Path('a', [(0, 0, 0), (40000, 0, 0)])], 'beyond|fit')
        encode(World(cells=[Cell(0, 0)], paths=[P.Path('a', [(0, 0, 0), (16000, 0, 0), (16000, 0, 300)])]))

    def test_malformed_paths_are_refused(self):
        good = encode(path_world())
        table = struct.unpack_from('<I', good, 68)[0]
        pts = struct.unpack_from('<I', good, table + 8)[0]
        closed = next(k for k, p in enumerate(path_world().paths) if p.closed)
        cpts = struct.unpack_from('<I', good, table + P.PATH_SIZE * closed + 8)[0]
        cases = [(68, '<I', 3), (68, '<I', len(good)), (64, '<I', 1000), (table + 4, '<I', 1),
                 (table + 4, '<I', 9999), (table + 8, '<I', 0), (table, '<I', 0),
                 (pts + 32, '<i', 5), (pts + 36, '<i', 0), (pts + 36, '<i', 12345),
                 (pts + P.PATH_POINT_SIZE * 3 + 36, '<i', 7), (pts + P.PATH_POINT_SIZE * 3 + 16, '<i', 7),
                 (table + 28, '<i', 1), (table + 16, '<i', fx(100)), (cpts, '<i', fx(63))]
        for at, fmt, value in cases:
            bad = bytearray(good)
            struct.pack_into(fmt, bad, at, value)
            with self.subTest(at=at, value=value), self.assertRaises(PackError):
                decode(bytes(bad))
        rng = random.Random(4)
        for _ in range(300):        # random byte flips: either decodes or raises PackError
            bad = bytearray(good)
            bad[rng.randrange(64, table + 600)] = rng.randrange(256)
            try:
                decode(bytes(bad))
            except PackError:
                pass

    def test_oracle(self):
        rail = decode(encode(path_world())).paths[0]
        (k, t, s, c, d2), margin = P.path_nearest(rail, F.raw((12, 4, 5)), 2)
        self.assertEqual((k, t, s, c, d2), (0, 8, 8, (12, 3, 4), 2))
        self.assertIsNone(P.path_nearest(rail, F.raw((12, 4, 5)), 1)[0])
        self.assertEqual(P.path_at(rail, 3), (0, (7, 3, 4)))
        self.assertEqual(P.path_at(rail, -5), (0, (4, 3, 4)))
        self.assertEqual(P.path_at(rail, 999)[0], 2)


@needs_tools
class PathTests(unittest.TestCase):
    """wp_path_nearest() and wp_path_at() on the console against exact arithmetic."""

    EPS = 0.003          # answers whose decisions lie closer than this to changing are not compared
    PTOL = 0.003         # position, lengths along and squared distance

    def run_paths(self, data, recs):
        with tempfile.TemporaryDirectory() as tmp:
            lines = F.run_cart(tmp, 'paths.akr', {'PACK': ('u8', data), 'QUERIES': ('WpPathQuery', b''.join(recs))},
                               frames=len(recs) // 100 + 3)
        self.assertEqual(lines[-1], 'done')
        return lines

    def test_queries_match_the_oracle(self):
        w = path_world(3)
        data = encode(w)
        pack = decode(data)
        rng = random.Random(7)
        recs, checks = [], []
        for _ in range(900):
            k = rng.randrange(len(w.paths))
            path = pack.paths[k]
            L = path['length'] / ONE
            if rng.random() < 0.7:
                reach = rng.choice([0.25, 0.6, 1.5, 4.0, 20.0])
                _, base = P.path_at(path, rng.uniform(0, L))
                rq = F.raw(tuple(float(base[i]) + rng.uniform(-1.2, 1.2) * reach for i in range(3)))
                recs.append(path_query(0, k, reach, rq))
                checks.append(('near',) + P.path_nearest(path, rq, Fraction(fx(reach), ONE)))
            else:
                s = rng.uniform(-L, 2 * L) if path['closed'] else rng.uniform(-1, L + 1)
                if rng.random() < 0.1:
                    s = rng.choice([0.0, L, -L, 2 * L]) if path['closed'] else rng.choice([0.0, L])
                recs.append(path_query(1, k, s))
                sm = s % L if path['closed'] else min(max(s, 0), L)
                margin = min(abs(sm - q['s'] / ONE) for q in path['points'])
                if path['closed']:
                    margin = min(margin, abs(s - round(s / L) * L))
                checks.append(('at', P.path_at(path, Fraction(fx(s), ONE)), margin))
        lines = self.run_paths(data, recs)
        self.assertEqual(lines[0], f'paths {len(w.paths)}')
        for src, got, line in zip(w.paths, pack.paths, lines[1:]):
            want = [src.name, len(src.points), len(got['points']), got['length'], got['flags'], src.surface,
                    *got['points'][1]['pos']]
            self.assertEqual(line.split(), [str(x) for x in want])
        self.assertEqual(lines[1 + len(w.paths)], 'find 0 1 1 1')
        answers = lines[2 + len(w.paths):2 + len(w.paths) + len(recs)]
        compared = worst = 0
        for (kind, want, margin), line in zip(checks, answers):
            if margin < self.EPS:
                continue
            f = [int(x) for x in line.split()]
            if kind == 'near':
                self.assertEqual(f[0], 1 if want else 0, line)
                if not want:
                    continue
                k, t, s, c, d2 = want
                self.assertEqual(f[1], k, line)
                err = max(abs(f[2] / ONE - float(t)), abs(f[3] / ONE - float(s)), abs(f[7] / ONE - float(d2)),
                          *(abs(f[4 + i] / ONE - float(c[i])) for i in range(3)))
            else:
                k, c = want
                self.assertEqual(f[:2], [1, k], line)
                err = max(abs(f[4 + i] / ONE - float(c[i])) for i in range(3))
            compared += 1
            worst = max(worst, err)
            self.assertLess(err, self.PTOL, line)
        if VERBOSE:
            print(f'\n  paths: {compared} of {len(recs)} answers compared, largest error {worst:.2e} units')
        self.assertGreater(compared, len(recs) * 3 // 4)

    def test_drawn_as_lines(self):
        w = World(cells=[Cell(0, 0)], paths=[P.Path('rail', [(20, 2, 20), (40, 2, 20), (40, 4, 40)])])
        with tempfile.TemporaryDirectory() as tmp:
            dump = Path(tmp) / 'shot.ppm'
            F.run_cart(tmp, 'path_draw.akr', {'PACK': ('u8', encode(w))}, frames=2, dump=dump)
            width, height, px = F.read_ppm(dump)
        yellow = sum(1 for k in range(width * height) if px[3 * k] > 200 and px[3 * k + 1] > 150 and px[3 * k + 2] < 100)
        self.assertGreater(yellow, 60)

    def test_older_pack_has_no_paths(self):
        data = encode(path_world())
        lines = self.run_paths(data[:6] + struct.pack('<H', 1) + data[8:], [])
        self.assertEqual(lines[0], 'paths 0')

    def test_costs(self):
        """Cycles of wp_path_nearest() for a grind check by a rail of 1, 4 and 16 segments and out
        of reach of it, and of wp_path_at()."""
        got = {}
        for segs in (1, 4, 16):
            w = World(cells=[Cell(0, 0)],
                      paths=[P.Path('rail', [(4 + 2 * k, 3 + 0.1 * k, 4 + (k % 2)) for k in range(segs + 1)])])
            rng = random.Random(segs)
            sets = [[path_query(0, 0, 0.6, F.raw((rng.uniform(4, 4 + 2 * segs), 3.5, 4.5))) for _ in range(50)],
                    [path_query(0, 0, 0.6, F.raw((40, 3, 40))) for _ in range(50)],
                    [path_query(1, 0, rng.uniform(0, 2 * segs)) for _ in range(50)],
                    [path_query(2, 0, 0) for _ in range(50)]]
            row = []
            for op, recs in zip((0, 0, 1, 2), sets):
                lines = self.run_paths(encode(w), recs)
                f = next(l.split() for l in lines if l.startswith(f'time {op}'))
                row.append(int(f[3]) / int(f[2]))
            got[segs] = [t - row[3] for t in row[:3]]      # the call itself taken off
        if VERBOSE:
            print('\n  ' + '\n  '.join(f'{s:2} segments: nearest {a:.0f}, out of reach {b:.0f}, at {c:.0f} cycles'
                                       for s, (a, b, c) in got.items()))
        self.assertLess(got[1][1], 200)
        self.assertLess(got[4][0], 800)
        self.assertLess(got[16][0], 2500)


if __name__ == '__main__':
    unittest.main()
