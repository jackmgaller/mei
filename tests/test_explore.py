"""The explorer bot (tools/explore): its numbers come from the cart, its flights match the
controller's arithmetic on a hand-made world, the harness hooks still fit, and the reach map runs
on the garden world.

The model tests need NumPy; the garden run needs NumPy and SciPy (and compiles the garden world
into the kit cache of $B, else build/, the first time); the headless test needs meic and
mei-headless and the cart's worlds built (make). Run with
`python3 -m unittest discover -s tests -p test_explore.py -v`.
"""
import importlib.util
import math
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
BUILD = ROOT / os.environ.get('B', 'build')

numpy_ready = importlib.util.find_spec('numpy') is not None
scipy_ready = importlib.util.find_spec('scipy') is not None
needs_numpy = unittest.skipUnless(numpy_ready, 'the explorer needs NumPy')

from explore import tuning as TN  # noqa: E402
from explore import moves as M  # noqa: E402
from explore import confirm as C  # noqa: E402


class TuningTest(unittest.TestCase):
    def test_numbers_are_the_carts(self):
        tn = TN.load()
        text = (ROOT / 'carts/garden/tuning.akr').read_text()
        self.assertIn('name: "jump vy",        unit: "m/s",  def: %s' % _fmt(tn.t['JumpVy']), text)
        self.assertEqual(tn.radius, 0.3)
        self.assertEqual(tn.push_h, [0.36, 0.9, 1.4])
        self.assertEqual(tn.surfaces[:3], [0, 1, 2])

    def test_updraft_numbers(self):
        tn = TN.load()
        text = (ROOT / 'carts/garden/updraft.akr').read_text()
        self.assertIn('const UD_SPEED: fixed = %s' % _fmt(tn.updraft['UD_SPEED']), text)
        self.assertEqual(tn.updraft_defaults['base'], 0.0)
        self.assertEqual(tn.updraft_defaults['lean'], [0.0, 0.0, 0.0])
        q = C.probe_for_flight('u', {'move': 'updraft_glide', 'from': [1.0, 20.0, 3.0], 'heading_deg': 90.0})
        self.assertEqual(q.mode, C.MODE_UPDRAFT)

    def test_reaches(self):
        tn = TN.load()
        s = tn.summary()
        g = tn.t['Gravity']
        vy = tn.t['FlipVy']
        self.assertAlmostEqual(s['backflip'], vy * vy / (2 * g) - vy / 120, places=3)
        self.assertAlmostEqual(s['highest_with_grab'], s['third_running'] + tn.t['LedgeHigh'], places=3)

    def test_launch_states(self):
        tn = TN.load()
        vy, fwd, ctrl, cap, gl = M.launch_state(M.BY_NAME['jump'], tn)
        run = tn.t['RunSpeed'] / 60
        self.assertAlmostEqual(vy, tn.t['JumpVy'] / 60 + run * tn.t['JumpSpeedAdd'])
        self.assertAlmostEqual(fwd, run)
        vy, fwd, ctrl, cap, gl = M.launch_state(M.BY_NAME['backflip'], tn)
        self.assertAlmostEqual(fwd, -tn.t['FlipBack'] / 60)
        self.assertEqual(ctrl, 0.35)
        self.assertTrue(M.can_glide_from(M.BY_NAME['double_glide'], tn))


def _fmt(v):
    return ('%.2f' % v).rstrip('0').rstrip('.') if v != int(v) else '%.1f' % v


@needs_numpy
class FlightTest(unittest.TestCase):
    """Flights over a hand-made column world: a floor at 0 over x 0..40, z 0..40 (the frame), a
    block 5.5 m high with a wall on its west face at x 20..24, and a hole at x 10..14."""

    @classmethod
    def setUpClass(cls):
        cls.tn = TN.load()
        cls.m = fake_world(cls.tn)

    def fly(self, move, x, z, yaw, y=0.0):
        import numpy as np
        from explore import sim as S
        vy, fwd, ctrl, cap, gl = M.launch_state(move, self.tn)
        if move.backwards:
            yaw += math.pi
        b = S.Batch(np.array([x]), np.array([y]), np.array([z]), np.array([yaw]), np.array([vy]), np.array([fwd]),
                    np.array([ctrl]), np.array([cap]), np.array([float(move.stick)]), np.array([move.st], np.int8),
                    np.array([bool(gl)]), np.array([move.dive_at_apex]), max_ticks=600)
        return S.Flyer(self.m, self.tn).fly(b)

    def test_running_jump(self):
        from explore import sim as S
        r = self.fly(M.BY_NAME['jump'], 2.0, 30.0, math.pi / 2)
        self.assertEqual(r.outcome[0], S.LAND)
        # the controller's per-tick arithmetic: up at 15 m/s under 36 m/s2 at 9.6 m/s
        tn = self.tn
        vy = tn.t['JumpVy'] / 60 + tn.t['RunSpeed'] / 60 * tn.t['JumpSpeedAdd']
        y, t = 0.0, 0
        while True:
            vy -= tn.t['Gravity'] / 3600
            y += vy
            t += 1
            if y <= 0:
                break
        self.assertEqual(int(r.ticks[0]), t)
        self.assertAlmostEqual(float(r.x[0]), 2.0 + t * tn.t['RunSpeed'] / 60, delta=0.01)
        self.assertAlmostEqual(float(r.max_y[0]), tn.summary()['jump_running'], delta=0.05)

    def test_ledge_grab_on_the_block(self):
        from explore import sim as S
        r = self.fly(M.BY_NAME['double'], 16.0, 5.0, math.pi / 2)
        self.assertEqual(r.outcome[0], S.LEDGE)
        self.assertAlmostEqual(float(r.y[0]), 5.5, places=3)

    def test_backflip_grabs_what_a_jump_cannot(self):
        from explore import sim as S
        # a hop and a grab reach 3.85 m; a backflip that meets the wall near its apex and a grab
        # 6.4 m (a backflip meeting it low wall-slides, as the controller's air_wall() does)
        r = self.fly(M.BY_NAME['hop'], 18.5, 5.0, math.pi / 2)
        self.assertNotEqual(r.outcome[0], S.LEDGE)
        r = self.fly(M.BY_NAME['backflip'], 17.4, 5.0, math.pi / 2)
        self.assertEqual(r.outcome[0], S.LEDGE)
        r = self.fly(M.BY_NAME['backflip'], 19.5, 5.0, math.pi / 2)
        self.assertNotEqual(r.outcome[0], S.LEDGE)

    def test_leaving_the_frame(self):
        from explore import sim as S
        r = self.fly(M.BY_NAME['walk_off'], 40.0, 30.0, math.pi / 2)
        self.assertEqual(r.outcome[0], S.OUT)

    def test_falling_through_a_hole(self):
        from explore import sim as S
        r = self.fly(M.BY_NAME['walk_off'], 9.9, 30.0, math.pi / 2)
        self.assertEqual(r.outcome[0], S.FELL)
        self.assertTrue(10.0 <= r.hole_x[0] <= 14.2)

    def fly_rail(self, rail, move, x, z, y=0.0, vy=None):
        """A move under or over one rail along z at x 30 (attach.akr's rail rules)."""
        import numpy as np
        from explore import sim as S
        v, fwd, ctrl, cap, gl = M.launch_state(move, self.tn)
        b = S.Batch(np.array([x]), np.array([y]), np.array([z]), np.array([0.0]), np.array([v if vy is None else vy]),
                    np.array([fwd]), np.array([ctrl]), np.array([cap]), np.array([0.0]), np.array([move.st], np.int8),
                    np.array([False]), np.array([False]), max_ticks=300)
        return S.Flyer(self.m, self.tn, rails=[dict(rail, id='r', n=0, closed=False)]).fly(b)

    def test_rail_hang_rules(self):
        from explore import sim as S
        hop = M.BY_NAME['hop']
        rail = {'points': [(30.0, 3.2, 10.0), (30.0, 3.2, 30.0)]}
        self.assertEqual(self.fly_rail(rail, hop, 30.0, 20.0).outcome[0], S.HANG)
        # a rail 1.5 m over the floor (a stair's handrail) would hold the feet in the floor: no hang
        # (the hop comes down on it and grinds)
        low = {'points': [(30.0, 1.5, 10.0), (30.0, 1.5, 30.0)]}
        self.assertEqual(self.fly_rail(low, hop, 30.0, 20.0).outcome[0], S.RAIL)
        # a hang-only rail is not ground, nor caught falling fast; a plain one is ground
        drop = M.BY_NAME['walk_off']
        self.assertEqual(self.fly_rail(rail, drop, 30.0, 20.0, y=4.5, vy=0.0).outcome[0], S.RAIL)
        self.assertEqual(self.fly_rail(dict(rail, hang=True), drop, 30.0, 20.0, y=4.5, vy=0.0).outcome[0], S.LAND)
        # a catch: within its first 3 m only
        caught = dict(rail, hang=True, catch=3.0)
        self.assertEqual(self.fly_rail(caught, hop, 30.0, 11.0).outcome[0], S.HANG)
        self.assertEqual(self.fly_rail(caught, hop, 30.0, 20.0).outcome[0], S.LAND)

    def test_pushed_out_of_a_wall_not_into_the_ground(self):
        """A body pushed out of a wall is not put under a floor more than a step over its feet: a
        column that keeps a thin wall's back face pushed a glide 0.6 m up into a bank, and it
        flew on under the hill (the explorer's false falls through the world in the shrine town)."""
        import numpy as np
        from explore import sim as S
        tn = self.tn
        m = cliff_world(tn)
        # falling past the cliff's face in a column of its wall: pushed out along the normal the
        # column keeps (+x) the body went 0.25 m into the cliff, a metre under its top, and fell on
        # under it through the world; now it comes down the face to the foot
        b = S.Batch(np.array([19.75]), np.array([3.0]), np.array([20.0]), np.array([0.0]), np.array([0.0]),
                    np.array([0.0]), np.ones(1), np.array([tn.mps('AirMax')]), np.zeros(1), np.array([M.ST_FALL], np.int8),
                    np.array([False]), np.array([False]), max_ticks=600)
        r = S.Flyer(m, tn).fly(b)
        self.assertEqual(r.outcome[0], S.LAND)
        self.assertAlmostEqual(float(r.y[0]), 0.0)

    def test_updraft_lifts_a_glide_to_its_cap(self):
        """A glide east at 6 m through an updraft (x 8..38, from 2 m up, its cap 12): the flight
        is player.akr's st_glide() tick for tick (updraft.akr's targets in the box, the glide's
        outside), it rises to the cap and no higher, and its entry is recorded as a ride; a fall
        through the same box (no glide) does not rise."""
        import numpy as np
        from explore import sim as S
        tn = self.tn
        ud = {'lo': (8.0, 2.0, 25.0), 'hi': (38.0, 12.0 + tn.updraft['UD_TOP'], 35.0), 'cap': 12.0, 'lift': 6.0}
        fl = S.Flyer(self.m, tn, updrafts=[ud])
        gs, sink, ease = tn.mps('GlideSpeed'), tn.mps('GlideSink'), tn.rps('GlideEase')
        b = S.Batch(np.array([2.0]), np.array([6.0]), np.array([30.0]), np.array([math.pi / 2]), np.zeros(1),
                    np.array([gs]), np.ones(1), np.array([tn.mps('AirMax')]), np.ones(1),
                    np.array([M.ST_DOUBLE], np.int8), np.zeros(1, bool), np.zeros(1, bool),
                    state=np.array([M.GLIDE], np.int8), max_ticks=1200)
        r = fl.fly(b)
        # the controller's arithmetic (st_glide, air_move(0.0)), from the same start
        x, y, vy, fwd, top, entry, t = 2.0, 6.0, 0.0, gs, 6.0, None, 0
        while x <= 40.0 and t < 1200:
            t += 1
            inside = 8.0 <= x <= 38.0 and 2.0 <= y <= ud['hi'][1]
            if inside and entry is None:
                entry = t
            speed = tn.updraft['UD_SPEED'] / 60 if inside else gs
            target = min(max((12.0 - y) * tn.updraft['UD_HOLD'] / 60, -sink), 6.0 / 60) if inside else -sink
            fwd += (speed - fwd) * ease
            vy += (target - vy) * ease
            x += fwd
            y += vy
            top = max(top, y)
        self.assertEqual(r.outcome[0], S.OUT)
        self.assertAlmostEqual(float(r.max_y[0]), top, places=6)
        self.assertTrue(12.0 - 0.1 <= top <= 12.0 + 0.6, top)
        self.assertEqual(list(r.rides['updraft']), [0])
        self.assertEqual(int(r.rides['tick'][0]), entry)
        # falling through it: gravity as anywhere
        b = S.Batch(np.array([20.0]), np.array([10.0]), np.array([30.0]), np.array([0.0]), np.zeros(1), np.zeros(1),
                    np.ones(1), np.array([tn.mps('AirMax')]), np.zeros(1), np.array([M.ST_FALL], np.int8),
                    np.zeros(1, bool), np.zeros(1, bool), max_ticks=600)
        r = fl.fly(b)
        self.assertEqual(r.outcome[0], S.LAND)
        self.assertAlmostEqual(float(r.max_y[0]), 10.0, places=6)
        self.assertEqual(len(r.rides['i']), 0)


def cliff_world(tn):
    """Floors at 0 west of x 20 and at 4 east of it (x 0..40, z 0..40); the 4 m cliff's wall
    columns keep the normal of its back face (+x), as a thin wall's column may."""
    import numpy as np
    from explore import world as W
    m = object.__new__(W.WorldModel)
    m.tuning = tn
    m.grid = 0.25
    m.frame = (0.0, 0.0, 40.0, 40.0)
    m.ox = m.oz = -2.0
    m.nx = m.nz = int(44 / 0.25) + 1
    xs = m.ox + np.arange(m.nx) * m.grid
    zs = m.oz + np.arange(m.nz) * m.grid
    X, Z = np.meshgrid(xs, zs)
    col = np.arange(m.nx * m.nz).reshape(m.nz, m.nx)
    inside = (X >= 0) & (X <= 40) & (Z >= 0) & (Z <= 40)
    y = np.where(X >= 20, 4.0, 0.0)
    c = col[inside]
    n = len(c)
    m.floors = W._sorted(c, y[inside], ny=np.ones(n), surf=np.zeros(n, np.int32), tag=np.zeros(n, np.int32))
    m.ceilings = W._sorted([], [], ny=[], surf=[], tag=[])
    wc = col[inside & (X > 20 - tn.radius) & (X < 20)]
    lo = 0.0 - max(tn.push_h)
    hi = 4.0 - min(tn.push_h)
    k = len(wc)
    m.walls = W.Sorted(wc * W.KEY + lo, wc.astype(np.int64), np.full(k, lo),
                       {'hi': np.full(k, hi), 'hx': np.full(k, 1.0), 'hz': np.zeros(k), 'ny': np.zeros(k),
                        'tag': np.zeros(k, np.int32)})
    return m


def fake_world(tn):
    import numpy as np
    from explore import world as W
    m = object.__new__(W.WorldModel)
    m.tuning = tn
    m.grid = 0.25
    m.frame = (0.0, 0.0, 40.0, 40.0)
    m.ox = m.oz = -2.0
    m.nx = m.nz = int(44 / 0.25) + 1
    xs = m.ox + np.arange(m.nx) * m.grid
    zs = m.oz + np.arange(m.nz) * m.grid
    X, Z = np.meshgrid(xs, zs)
    col = np.arange(m.nx * m.nz).reshape(m.nz, m.nx)
    inside = (X >= 0) & (X <= 40) & (Z >= 0) & (Z <= 40)
    hole = (X >= 10) & (X <= 14)
    block = (X >= 20) & (X <= 24)
    fl = inside & ~hole
    y = np.where(block, 5.5, 0.0)
    c = col[fl]
    n = len(c)
    m.floors = W._sorted(c, y[fl], ny=np.ones(n), surf=np.zeros(n, np.int32), tag=np.zeros(n, np.int32))
    m.ceilings = W._sorted([], [], ny=[], surf=[], tag=[])
    # the block's west face at x 20, a wall from 0 to 5.5: feet heights it pushes at, per column
    # within the radius west of it (one of the push heights inside 0..5.5)
    wc = col[inside & (X > 20 - tn.radius) & (X < 20)]
    lo = 0.0 - max(tn.push_h)
    hi = 5.5 - min(tn.push_h)
    k = len(wc)
    m.walls = W.Sorted(wc * W.KEY + lo, wc.astype(np.int64), np.full(k, lo),
                       {'hi': np.full(k, hi), 'hx': np.full(k, -1.0), 'hz': np.zeros(k), 'ny': np.zeros(k),
                        'tag': np.zeros(k, np.int32)})
    return m


class HarnessTest(unittest.TestCase):
    def test_hooks_fit_the_harness(self):
        text = C.patch_harness((ROOT / 'carts/garden/tests/harness.akr').read_text())
        self.assertIn('import "explore_cases.akr"', text)
        self.assertIn('ex_case(f)', text)

    def test_game_has_a_draw(self):
        self.assertEqual((ROOT / 'carts/garden/game.akr').read_text().count('fn draw() {'), 1)

    def test_state_names(self):
        self.assertIn('glide', C.read_st_names())

    def test_probe_table(self):
        q = C.Probe(find='x', p=(1, 2, 3), yaw=0.5, head=0.5, mode=3)
        text = C.probes_akr([q, q], (0, 0, 64, 64), 'garden')
        self.assertIn('const EX_PROBES: [2]ExProbe', text)
        self.assertEqual(text.count('ExProbe { p: vec3('), 2)

    def test_glide_cases(self):
        g = C.glide_cases(ROOT / 'carts/garden/tests/shrinetown_cases.akr')
        self.assertIn('G8', g)
        self.assertEqual(len(g['G8']['from']), 3)


@unittest.skipUnless(numpy_ready and scipy_ready, 'the reach map needs NumPy and SciPy')
class GardenReachTest(unittest.TestCase):
    """The reach map on the garden world (4 cells): the spawn's floor is reached, every coin is
    reachable, and nothing leaves the frame by walking."""

    def test_garden(self):
        from explore import reach as R, finds as FD
        e = R.Explorer(str(ROOT / 'carts/garden/world/garden.world.json'), BUILD, TN.load(), {},
                       opts=R.Options(lattice=8, kick_depth=1), log=lambda *a: None)
        e.run()
        import numpy as np
        self.assertTrue(np.isfinite(e.dist[e.start]))
        got = FD.collectibles(e)
        coins = [c for c in got if c['type'] == 'coin']
        self.assertTrue(coins)
        self.assertTrue(all(c['reachable'] for c in coins), [c['id'] for c in coins if not c['reachable']])
        steps = e.route(int(np.nanargmax(np.where(np.isfinite(e.dist[:e.n_floor]), e.dist[:e.n_floor], -1))))
        self.assertTrue(steps)


@unittest.skipUnless((BUILD / 'meic').exists() and (BUILD / 'mei-headless').exists()
                     and (BUILD / 'cart-worlds/garden').exists(), 'the confirmer needs meic, mei-headless and the worlds')
class HeadlessTest(unittest.TestCase):
    """One probe flown by the real cart: a running jump on the garden's lane comes down where the
    controller's numbers say."""

    def test_jump_on_the_lane(self):
        r = C.Runner(BUILD, 'garden', (0, 0, 128, 128), log=lambda *a: None, processes=1)
        got = r.run([C.Probe(find='t', p=(40.0, 0.5, 8.0), yaw=math.pi / 2, head=math.pi / 2, mode=3, t=90)], name='test')
        self.assertEqual(len(got), 1)
        o = got[0]
        self.assertFalse(o.out)
        self.assertAlmostEqual(o.maxy, TN.load().summary()['jump_running'], delta=0.1)

    def test_written_case_runs_in_the_cart(self):
        """A case as the explorer writes it, run in the real cart: a jump on the lane stays in the
        level (the check passes, exit 0); one off the garden's south edge leaves it (exit 2)."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for name, p, head, want in (('stays', (40.0, 0.5, 8.0), math.pi / 2, 0),
                                        ('leaves', (44.0, 0.5, 0.5), math.pi, 2)):
                st = {'probe': C.asdict(C.Probe(find=name, p=p, yaw=head, head=head, mode=3, t=90)), 'seed': 1}
                path = Path(tmp) / f'{name}.akr'
                path.write_text(C.case_text('garden', 'escape', {'id': name}, st, (0, 0, 128, 128), -5.0))
                code, out = C.run_case(BUILD, path, draw=False)
                self.assertEqual(code, want, out[-800:])


if __name__ == '__main__':
    unittest.main()
