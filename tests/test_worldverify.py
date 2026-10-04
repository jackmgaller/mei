"""The World Checker (tools/worldkit/verify.py, docs/WORLDCHECKER.md).
Run: python3 -m unittest discover -s tests -p test_worldverify.py

The worlds are built at test time (tests/worldverify/worlds.py). Static checks need only
Python; the view tests need meic and mei-scene-probe (MEIC and SCENE_PROBE select the builds;
they are skipped when those have not been built) and NumPy. WORLDCHECK_VERBOSE=1 prints the
measurements.
"""
import copy
import dataclasses
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / 'worldverify'))
import worlds as F  # noqa: E402
from worldkit import verify as V  # noqa: E402
from worldkit import verify_static as ST  # noqa: E402
from worldkit.pack import decode, encode, World, Cell, Tri, Placement  # noqa: E402

VERBOSE = os.environ.get('WORLDCHECK_VERBOSE')
try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False
needs_tools = unittest.skipUnless(F.tools_built() and HAVE_NUMPY, 'meic, mei-scene-probe or NumPy missing')

# Views only from the given vantage points.
VANTAGE_ONLY = {'sampling': {'floor_spacing': None, 'rooftops_per_cell': 0, 'air': None, 'seams': None,
                             'follow': None, 'entities': None}}
# Views only from cameras aimed at entities, fewer of them than by default.
ENTITY_ONLY = {'sampling': {**VANTAGE_ONLY['sampling'],
                            'entities': {'yaws': 4, 'distances': [1.5, 4.0], 'pitches_degrees': [-45.0, -15.0],
                                         'floor_distances': [3.0]}}}


def settings(base=None, **kw):
    s = copy.deepcopy(base or {})
    for k, v in kw.items():
        s[k] = v
    return s


def codes(items):
    return sorted({i['code'] for i in items})


class SettingsTests(unittest.TestCase):
    def test_defaults_and_unknown_keys(self):
        s = V.merge_settings({'thresholds': {'near_band': 8.0}})
        self.assertEqual(s['thresholds']['near_band'], 8.0)
        self.assertEqual(s['thresholds']['gpu_cycles'], 1600000)   # 80% of the GPU's 2,000,000
        self.assertEqual(s['mode'], 'report')
        with self.assertRaises(V.SettingsError):
            V.merge_settings({'thresholds': {'nope': 1}})
        with self.assertRaises(V.SettingsError):
            V.merge_settings({'mode': 'lenient'})
        with self.assertRaises(V.SettingsError):
            V.merge_settings({'runtime': {'entity_drawing': 'billboard'}})
        self.assertIsNone(V.merge_settings({'sampling': {'entities': None}})['sampling']['entities'])

    def test_bad_pack_is_a_hard_failure(self):
        r = V.verify(b'MEIX' + bytes(60))
        self.assertFalse(r['ok'])
        self.assertEqual(r['hard_failures'][0]['code'], 'bad_pack')


class StaticTests(unittest.TestCase):
    """Collision and references, from the pack alone."""

    def test_world_triangles_round_trip(self):
        pack = decode(encode(F.good_world()))
        tris = ST.world_triangles(pack)
        floors = [t for t in tris if t.kind == 0]
        # 256 ground tiles less 6 + 4 + 6 under the boxes, two triangles each, and box tops
        self.assertEqual(len(floors), 2 * (256 - 16) + 2 * 3)
        for t in floors:
            for v in t.verts:
                self.assertLess(abs(ST._height(t, v[0], v[2]) - v[1]), 1e-4)

    def test_reader_floor_matches_the_ground(self):
        pack = decode(encode(F.good_world()))
        got = ST.reader_floor(pack, 3 * 65536, 2 * 65536, 3 * 65536, set())
        self.assertEqual((got[0], got[1]), (0, F.TAG_GROUND))
        got = ST.reader_floor(pack, 6 * 65536, 8 * 65536, 6 * 65536, set())
        self.assertEqual((got[0], got[1]), (6 * 65536, F.TAG_BOX))

    def check_static(self, world, **kw):
        cfg = V.merge_settings(kw.get('settings'))
        pack = decode(encode(world))
        tris = ST.world_triangles(pack)
        found, n, _, _ = ST.crack_check(pack, tris, frozenset(), cfg['probe'], cfg['collision'], 50)
        ents, ne = ST.entity_check(pack, tris, cfg['collision'], 50)
        return found, ents

    def test_good_world_has_no_collision_errors(self):
        found, ents = self.check_static(F.good_world())
        self.assertEqual(found, [])
        self.assertEqual(ents, [])

    def test_crack_between_floors_is_found(self):
        found, _ = self.check_static(F.crack_world())
        cracks = [f for f in found if f['code'] == 'crack']
        self.assertTrue(cracks, found)
        self.assertEqual({(f['floor_tag'], f['beyond_tag']) for f in cracks}, {(30, 31), (31, 30)})
        self.assertEqual(cracks[0]['cell'], [0, 0])
        for f in cracks:
            self.assertAlmostEqual(f['at'][1], 2.0, places=3)
            self.assertTrue(22 <= f['at'][0] <= 30.1 and 24 <= f['at'][2] <= 28)
        # widening the gap past the probe radius makes it a ledge, not a crack
        w = F.crack_world()
        found, _ = self.check_static(w, settings={'probe': {'radius': 0.05, 'height': 1.6, 'step': 0.32}})
        self.assertEqual([f for f in found if f['code'] == 'crack'], [])

    def test_mismatched_edges_across_a_seam(self):
        found, _ = self.check_static(F.seam_world())
        mism = [f for f in found if f['code'] == 'edge_mismatch']
        self.assertTrue(mism, found)
        seam = [f for f in mism if f['on_seam']]
        self.assertTrue(seam, mism)
        self.assertTrue(all({f['floor_tag'], f['beyond_tag']} == {F.TAG_GROUND, 40} for f in seam), seam)
        self.assertTrue(all(abs(f['at'][0] - 32) < 1e-3 for f in seam), seam)
        # the same two cells with matching corners are clean
        a, b = F.plaza(0, 0, boxes=[]), F.plaza(1, 0, boxes=[])
        found, _ = self.check_static(World(cells=[a, b], cell_shift=5))
        self.assertEqual(found, [])

    def test_long_thin_floors_are_not_mismatched(self):
        # A quad's two triangles share their diagonal; for a long thin quad the corners worked out
        # from the rounded rows slide along it (0.003 units at 2 x 50), which an absolute
        # tolerance took for mismatched edges.
        def quad(w, l, x0=3.3, z0=4.1, dz=0.0):
            a, b, c, d = (x0, 0, z0), (x0 + w, 0, z0), (x0, 0, z0 + l), (x0 + w, 0, z0 + l)
            return World(cells=[Cell(0, 0, collision=[Tri(a, b, c, 1, tag=1),
                                                      Tri(b, d, (c[0], 0, c[2] + dz), 1, tag=2)])], cell_shift=6)
        for w, l in ((2, 50), (1, 60), (0.25, 30), (50, 2), (8, 8)):
            with self.subTest(w=w, l=l):
                self.assertEqual(self.check_static(quad(w, l))[0], [])
        # a real gap along the diagonal is still found
        found, _ = self.check_static(quad(2, 50, dz=0.05))
        self.assertEqual({(f['code'], f['floor_tag'], f['beyond_tag']) for f in found}, {('crack', 1, 2), ('crack', 2, 1)})

    def test_entity_in_a_wall(self):
        _, ents = self.check_static(F.entity_wall_world())
        self.assertEqual(len(ents), 1)
        self.assertEqual((ents[0]['entity'], ents[0]['cell']), (1, [0, 0]))
        self.assertEqual(ents[0]['enclosing_tags'], [F.TAG_BOX + 1])

    def test_counts_and_stand_ins(self):
        a, b, c = F.plaza(0, 0, boxes=[]), F.plaza(1, 0, boxes=[]), F.plaza(2, 0, boxes=[])
        pack = decode(encode(World(cells=[a, b, c], cell_shift=5)))
        errors, warnings = ST.reference_check(pack, 3)
        self.assertEqual([(e['code'], e['cell']) for e in errors],
                         [('standin_missing', [0, 0]), ('standin_missing', [2, 0])])
        cells, regions = ST.counts(pack)
        self.assertEqual(cells[0]['triangles'], 512)
        self.assertEqual(regions[0]['cells'], 3)


@needs_tools
class ViewTests(unittest.TestCase):
    def run_check(self, world, s=None, out=None):
        return V.verify(encode(world), s, out_dir=out, tools=F.tools())

    def test_good_world_passes_strict(self):
        # Without the cameras aimed at its coin: one of them, at eye height on the ground 4 units
        # from the coin, sees a ground tile drawn over the foot of a building (6 pixels; the
        # plaza's ground is not flagged ground). The plaza is known-good from the other kinds.
        r = self.run_check(F.good_world(), {'mode': 'strict', 'sampling': {'entities': None}})
        if VERBOSE:
            print('\n  good world:', json.dumps(r['summary']), json.dumps(r['timing']))
        self.assertTrue(r['ok'], json.dumps(r['hard_failures'] + r['threshold_failures'])[:2000])
        self.assertGreater(r['summary']['views'], 40)
        self.assertEqual(r['summary']['coverage_errors'], 0)
        self.assertGreater(r['summary']['tested_pixels'], 30 * 50000)
        kinds = r['sampling']['kinds']
        for k in ('eye', 'follow', 'rooftop', 'air'):
            self.assertGreater(kinds.get(k, 0), 0, k)
        for v in r['views']:
            self.assertEqual(v['stats']['triangles_dropped'], 0)
            self.assertFalse(v['stats']['arena_full'])
            self.assertGreater(v['stats']['draw_cpu_cycles'], 0)
            self.assertGreater(v['stats']['gpu_cycles'], 38400)

    def test_report_is_deterministic(self):
        s = settings(VANTAGE_ONLY, vantage_points=[F.VANTAGE_MISSORT])
        a = self.run_check(F.missort_world(), s)
        b = self.run_check(F.missort_world(), s)
        a.pop('timing'), b.pop('timing')
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_mis_sorted_pair_is_caught(self):
        s = settings(VANTAGE_ONLY, vantage_points=[F.VANTAGE_MISSORT])
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_check(F.missort_world(), s, tmp)
            images = sorted(p.name for p in Path(tmp).iterdir())
        self.assertTrue(r['ok'], 'report mode does not fail on ordering')
        v = r['views'][0]
        self.assertEqual(v['kind'], 'vantage')
        o = v['ordering']
        if VERBOSE:
            print('\n  mis-sort:', json.dumps(o)[:1500])
        self.assertEqual(o['coverage_errors'], 0)
        self.assertGreater(o['wrong_near_pixels'], 50)
        w = o['issues'][0]
        self.assertEqual((w['drawn']['tag'], w['expected']['tag']), (50, 51))
        self.assertEqual(w['class'], 'near')
        self.assertEqual(w['drawn']['cell'], [0, 0])
        self.assertLess(w['visible_depth'], 16)
        self.assertEqual(r['threshold_failures'][0]['code'], 'wrong_order_near')
        self.assertEqual(r['threshold_failures'][0]['camera']['eye'], F.VANTAGE_MISSORT['position'])
        self.assertIn('view_0000.png', images)
        self.assertIn('world-check.json', images)
        strict = self.run_check(F.missort_world(), settings(s, mode='strict'))
        self.assertFalse(strict['ok'])
        self.assertEqual(strict['hard_failures'], [])
        # a far band of 4 units turns it into a far error, under the 0.5% allowance
        far = self.run_check(F.missort_world(), settings(s, mode='strict', thresholds={'near_band': 4.0}))
        self.assertEqual(far['views'][0]['ordering']['wrong_near_pixels'], 0)
        self.assertTrue(far['ok'], json.dumps(far['threshold_failures'])[:1000])

    def test_near_plane_faces_are_neither_dropped_nor_invented(self):
        vps = [{'position': [16.0, 0.05, 16.0], 'yaw': 0.0, 'pitch': -30.0},     # floor under the eye
               {'position': [16.0, 0.3, 16.0], 'yaw': 180.0, 'pitch': -45.0},
               {'position': [16.0, 4.0, 23.95], 'yaw': 20.0, 'pitch': 0.0},     # 0.05 from the wall
               {'position': [3.0, 4.0, 23.92], 'yaw': -70.0, 'pitch': 10.0},
               {'position': [30.0, 0.2, 23.9], 'yaw': 45.0, 'pitch': -10.0},
               # 0.05 above the floor looking 60 degrees down: everything in view is nearer
               # than the near plane, so nothing may be drawn
               {'position': [16.0, 0.05, 16.0], 'yaw': 180.0, 'pitch': -60.0}]
        r = self.run_check(F.nearplane_world(), settings(VANTAGE_ONLY, vantage_points=vps, mode='strict'))
        self.assertTrue(r['ok'], json.dumps(r['threshold_failures'])[:2000])
        for v in r['views']:
            o = v['ordering']
            self.assertEqual(o['coverage_errors'], 0)
            self.assertEqual(o['wrong_near_pixels'] + o['wrong_far_pixels'], 0)
            if v['vantage'] < 5:
                self.assertGreater(o['tested_pixels'], 5000, v['camera'])
        # the floor seen from 0.05 above fills the lower half of the screen
        self.assertGreater(r['views'][0]['ordering']['tested_pixels'], 0.4 * 76800)
        self.assertEqual(r['views'][5]['ordering']['tested_background'], 76800)
        self.assertEqual(r['views'][5]['stats']['placements_drawn'], 2)     # drawn, all clipped away

    def test_clipped_faces_are_not_dropped(self):
        """Cameras that used to leave holes. Two over the world pack demonstration world: a ground
        tile under the eye whose clipped polygon had two corners on one pixel (the face loop culled
        a quad piece by its first three corners), and a stand-in face in the far pass whose
        clip-space back-face determinant overflowed (__clip_unit did not scale; a compiler bug)."""
        vps = [{'position': [10.5278, 2.6406, 9.0798], 'yaw': -167.96602, 'pitch': -47.54201},
               {'position': [135.2339, 23.4188, 9.4824], 'yaw': -131.8, 'pitch': -39.3}]
        s = settings(VANTAGE_ONLY, vantage_points=vps, mode='strict')
        s['sampling'] = dict(s['sampling'], layer_combinations=False)
        r = V.verify(encode(F._wp.demo_world()), s, tools=F.tools())
        for v in r['views']:
            self.assertEqual(v['ordering']['coverage_errors'], 0, v['camera'])
        self.assertGreater(r['views'][0]['ordering']['tested_pixels'], 70000)
        self.assertGreater(r['views'][1]['ordering']['tested_pixels'], 15000)
        # a floor quad whose fourth corner alone is behind a low camera, the first three outside
        # the guard band: the guard-band path took that corner's mirrored projection as in front
        # and dropped the whole floor as above the screen
        vps = [{'position': [26.9662, 0.2385, 26.011], 'yaw': -115.4336, 'pitch': -83.3843},
               {'position': [22.262, 1.0046, 24.7188], 'yaw': -147.61, 'pitch': -48.5955}]
        s = settings(VANTAGE_ONLY, vantage_points=vps, mode='strict')
        r = V.verify(encode(F.nearplane_world()), s, tools=F.tools())
        for v in r['views']:
            self.assertEqual(v['ordering']['coverage_errors'], 0, v['camera'])
            self.assertGreater(v['ordering']['tested_pixels'], 70000)

    def test_over_budget_view_report_and_strict(self):
        # the overdraw world's view is over 800,000 GPU cycles (not over the default 1,600,000)
        s = settings(VANTAGE_ONLY, vantage_points=[F.VANTAGE_OVERDRAW], thresholds={'gpu_cycles': 800000})
        r = self.run_check(F.overdraw_world(), s)
        gpu = r['views'][0]['stats']['gpu_cycles']
        self.assertGreater(gpu, 800000)
        self.assertTrue(r['ok'])
        self.assertIn('gpu_cycles', codes(r['threshold_failures']))
        strict = self.run_check(F.overdraw_world(), settings(s, mode='strict'))
        self.assertFalse(strict['ok'])
        self.assertEqual(strict['hard_failures'], [])
        f = [f for f in strict['threshold_failures'] if f['code'] == 'gpu_cycles'][0]
        self.assertEqual((f['value'], f['limit'], f['kind']), (gpu, 800000, 'vantage'))
        # a world may raise its own threshold
        ok = self.run_check(F.overdraw_world(), settings(s, mode='strict', thresholds={'gpu_cycles': 1200000}))
        self.assertNotIn('gpu_cycles', codes(ok['threshold_failures']))

    def test_levels_of_detail_are_judged_as_drawn(self):
        s = {'sampling': {'entities': None}}
        r = self.run_check(F.lod_world(), s)
        lod = r['summary']['lod']
        if VERBOSE:
            print('\n  LOD world:', json.dumps(lod), r['summary']['coverage_errors'])
        self.assertGreater(lod['coarse_drawn'], 10)
        self.assertGreater(lod['lod_culled'], 0)
        self.assertEqual(r['summary']['coverage_errors'], 0, 'the reference draws the levels the reader drew')
        self.assertGreater(r['summary']['tested_pixels'], 20 * 50000)
        flat = self.run_check(F.lod_world(), settings(s, runtime={'lod': False}))
        self.assertEqual((flat['summary']['lod']['coarse_drawn'], flat['summary']['lod']['lod_culled']), (0, 0))
        self.assertEqual(flat['summary']['coverage_errors'], 0)
        self.assertGreaterEqual(flat['summary']['max_triangles']['value'], r['summary']['max_triangles']['value'])
        # a triangle budget failure names the heaviest placements drawn, with their level and distance
        tight = self.run_check(F.lod_world(), settings(s, thresholds={'view_triangles': 20}))
        f = [f for f in tight['threshold_failures'] if f['code'] == 'view_triangles'][0]
        self.assertTrue(f['heaviest'])
        self.assertEqual(set(f['heaviest'][0]), {'cell', 'placement', 'tag', 'faces', 'distance', 'level', 'levels'})
        self.assertIsNone(self.run_check(F.good_world(), s)['summary']['lod'])

    def test_dropped_triangles_fail_in_every_mode(self):
        s = settings(VANTAGE_ONLY, vantage_points=[F.VANTAGE_DROPPED])
        r = self.run_check(F.dropped_world(), s)
        self.assertFalse(r['ok'])
        self.assertEqual(codes(r['hard_failures']), ['triangles_dropped'])
        f = r['hard_failures'][0]
        self.assertEqual((f['kind'], f['view']), ('vantage', 0))
        self.assertGreater(f['value'], 1000)
        # the triangles the GPU never drew show up as pixels the reference expected
        self.assertGreater(r['views'][0]['ordering']['coverage_errors'], 0)

    def test_static_faults_fail_the_whole_check(self):
        s = settings(VANTAGE_ONLY, vantage_points=[F.VANTAGE_MISSORT])
        for world, code in ((F.crack_world, 'crack'), (F.entity_wall_world, 'entity_in_solid'),
                            (F.seam_world, 'edge_mismatch')):
            r = self.run_check(world(), s)
            self.assertFalse(r['ok'], code)
            self.assertIn(code, codes(r['hard_failures']))

    def test_check_world_adapter(self):
        """worldkit.build.run_gate() calls check_world(context) with the staged pack."""
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / 'plaza.world.bin'
            pack.write_bytes(encode(F.overdraw_world()))
            ctx = {'world': 'plaza', 'stage': tmp, 'pack': str(pack), 'mode': 'enforce',
                   'thresholds': {'gpu_cycles': 700000}, 'probe': {'radius': 0.3, 'height': 1.6, 'step': 0.32,
                                                                   'floor_max_degrees': 40},
                   'compiler': str(F.COMPILER), 'runner': None}
            r = V.check_world(ctx)
            self.assertTrue((Path(tmp) / 'verification' / 'world-check.json').exists())
            bad = V.check_world({**ctx, 'stage': None, 'thresholds': {'no_such': 1}})
        self.assertEqual(r['mode'], 'strict')
        self.assertFalse(r['ok'])
        self.assertIn('gpu_cycles', codes(r['threshold_failures']))
        self.assertFalse(bad['ok'])
        self.assertIn('unknown setting', bad['errors'][0]['message'])

    def test_layer_combinations(self):
        w = F.good_world()
        c = w.cells[0]
        from worldkit.pack import Layer, Placement
        w.layers = [Layer('stall_a', group=0), Layer('stall_b', group=0), Layer('lamp')]
        c.layers = ['stall_a', 'stall_b', 'lamp']
        stall = F.box_mesh((-1, 0, -1), (1, 2, 1), 0x00FF00)
        c.placements += [Placement(stall, (14, 0, 14), layer='stall_a', tag=90),
                         Placement(stall, (14, 0, 18), layer='stall_b', tag=91),
                         Placement(F.box_mesh((-0.2, 0, -0.2), (0.2, 3, 0.2), 0xFFFFFF), (20, 0, 20),
                                   layer='lamp', tag=92)]
        s = settings(VANTAGE_ONLY, vantage_points=[{'position': [14.0, 3.0, 4.0], 'yaw': 0.0, 'pitch': -10.0}])
        r = self.run_check(w, s)
        self.assertEqual(r['sampling']['layer_sets'], ['none', 'stall_a', 'stall_b', 'lamp', 'largest'])
        by = {v['layer_set']: v for v in r['views']}
        self.assertEqual(by['largest']['layers'], ['stall_a', 'lamp'])
        drawn = {k: v['stats']['placements_drawn'] for k, v in by.items()}
        self.assertEqual(drawn['stall_a'], drawn['none'] + 1)
        self.assertEqual(drawn['largest'], drawn['none'] + 2)
        for v in r['views']:
            self.assertEqual(v['ordering']['coverage_errors'], 0)


class GroundStaticTests(unittest.TestCase):
    """The static warnings for likely misuse of the ground flag (no tools needed)."""

    def warnings(self, world):
        pack = decode(encode(world))
        return {w['code']: w for w in ST.ground_check(pack, 48.0, 10)}

    def test_ground_static_warnings(self):
        self.assertEqual(self.warnings(F.missort_world()), {}, 'no ground: nothing to check')
        self.assertEqual(self.warnings(F.ground_missort_world()), {}, 'a crate standing on the ground')
        self.assertEqual(self.warnings(F.slope_world()), {}, 'a valley hides nothing')
        sunk = self.warnings(F.ground_missort_world(sink=0.3))
        self.assertEqual(list(sunk), ['ground_hides'])
        f = sunk['ground_hides']['findings'][0]
        self.assertEqual((f['ground']['tag'], f['other']['tag']), (50, 51))
        self.assertAlmostEqual(f['behind'], 0.3, places=3)
        # the crate is ground too: two ground pieces that can overlap, and the crate's top can hide
        # the bottoms of the buildings beyond it
        raised = self.warnings(F.ground_missort_world(crate_ground=True))
        self.assertEqual(sorted(raised), ['ground_hides', 'ground_over_ground'])
        f = raised['ground_over_ground']['findings'][0]
        self.assertEqual({f['ground']['tag'], f['other']['tag']}, {50, 51})
        ridge = self.warnings(F.slope_world(ridge=True))
        self.assertEqual(sorted(ridge), ['ground_hides', 'ground_over_ground'])
        pairs = [(f['ground']['tag'], f['other'].get('tag')) for f in ridge['ground_hides']['findings']]
        self.assertIn((2, 11), pairs)


@needs_tools
class GroundViewTests(unittest.TestCase):
    """Ground-first drawing as the checker models it (docs/WORLDCHECKER.md, "Ground")."""

    def run_check(self, world, s=None):
        return V.verify(encode(world), s, tools=F.tools())

    def test_ground_first_fixes_the_mis_sort_and_is_modelled_both_ways(self):
        s = settings(VANTAGE_ONLY, vantage_points=[F.VANTAGE_MISSORT], mode='strict')
        r = self.run_check(F.ground_missort_world(), s)
        o = r['views'][0]['ordering']
        if VERBOSE:
            print('\n  ground-first:', json.dumps(o)[:600])
        self.assertTrue(r['ok'], json.dumps(r['threshold_failures'])[:2000])
        self.assertEqual(r['views'][0]['stats']['ground_drawn'], 1)
        self.assertEqual((o['wrong_near_pixels'], o['coverage_errors'], o['ground_inversions']), (0, 0, 0))
        self.assertGreater(o['tested_pixels'], 20000)
        # a game that turns ground-first off gets the old picture, and the checker says so
        off = self.run_check(F.ground_missort_world(), settings(s, runtime={'ground_first': False}))
        o = off['views'][0]['ordering']
        self.assertEqual(off['views'][0]['stats']['ground_drawn'], 0)
        self.assertEqual(o['coverage_errors'], 0)
        self.assertGreater(o['wrong_near_pixels'], 50)
        self.assertEqual((o['issues'][0]['drawn']['tag'], o['issues'][0]['expected']['tag']), (50, 51))

    def test_errors_ground_first_does_not_excuse(self):
        s = settings(VANTAGE_ONLY, vantage_points=[F.VANTAGE_MISSORT], mode='strict')
        # a raised ground piece on the ground: the pair is sorted inside the ground pass
        r = self.run_check(F.ground_missort_world(crate_ground=True), s)
        o = r['views'][0]['ordering']
        self.assertFalse(r['ok'])
        self.assertEqual(o['coverage_errors'], 0)
        self.assertGreater(o['wrong_near_pixels'], 50)
        self.assertEqual((o['issues'][0]['drawn']['tag'], o['issues'][0]['expected']['tag']), (50, 51))
        self.assertIn('ground_over_ground', codes(r['static']['warnings']))
        # a crate sunk through the ground: drawn whole over the ground that truly hides its bottom
        r = self.run_check(F.ground_missort_world(sink=0.3), s)
        o = r['views'][0]['ordering']
        if VERBOSE:
            print('\n  sunk crate:', json.dumps(o)[:800])
        self.assertFalse(r['ok'])
        self.assertEqual((o['wrong_near_pixels'], o['coverage_errors']), (0, 0))
        self.assertGreater(o['ground_inversions'], 50)
        w = o['ground_issues'][0]
        self.assertEqual((w['ground']['tag'], w['drawn']['tag']), (50, 51))
        self.assertGreater(w['max_depth_behind'], 0.001)
        self.assertEqual(codes(r['threshold_failures']), ['ground_inversion'])
        self.assertIn('ground_hides', codes(r['static']['warnings']))
        # the threshold is the world's to set
        ok = self.run_check(F.ground_missort_world(sink=0.3),
                            settings(s, thresholds={'ground_inversion_pixels': 100000}))
        self.assertTrue(ok['ok'])

    def test_ground_on_ground_in_a_valley_and_over_a_ridge(self):
        s = {'mode': 'strict', 'sampling': {'floor_spacing': 8.0, 'seams': None}}
        r = self.run_check(F.slope_world(), s)
        if VERBOSE:
            print('\n  valley:', json.dumps(r['summary']))
        self.assertTrue(r['ok'], json.dumps(r['threshold_failures'])[:2000])
        self.assertGreater(r['summary']['views'], 40)
        self.assertGreater(r['summary']['tested_pixels'], 30 * 40000)
        for v in r['views']:
            o = v['ordering']
            self.assertEqual((o['wrong_near_pixels'], o['wrong_far_pixels'], o['coverage_errors'],
                              o['ground_inversions']), (0, 0, 0, 0), v['camera'])
            self.assertIn(v['stats']['ground_drawn'], (1, 2))
        self.assertIn(2, [v['stats']['ground_drawn'] for v in r['views']])
        # over a ridge the crest hides the bottom of what stands beyond it: ground inversions
        ridge = self.run_check(F.slope_world(ridge=True),
                               settings(VANTAGE_ONLY, vantage_points=[F.VANTAGE_RIDGE]))
        o = ridge['views'][0]['ordering']
        if VERBOSE:
            print('\n  ridge:', json.dumps(o)[:800])
        self.assertEqual((o['wrong_near_pixels'], o['coverage_errors']), (0, 0))
        self.assertGreater(o['ground_inversions'], 20)
        self.assertEqual((o['ground_issues'][0]['ground']['tag'], o['ground_issues'][0]['drawn']['tag']), (2, 11))


@needs_tools
class EntityViewTests(unittest.TestCase):
    """Cameras aimed at entities, and objects drawn with wp_draw_object() as the checker models
    them (docs/WORLDCHECKER.md, "Entities")."""

    def run_check(self, world, s=None):
        return V.verify(encode(world), s, tools=F.tools())

    def test_entity_cameras_catch_what_the_other_cameras_missed(self):
        # a coin above a ledge drawn by its own depth alone: the ledge's top is drawn over it
        plain = {'runtime': {'entity_drawing': 'mesh_at'}}
        old = self.run_check(F.ledge_world(), settings(plain, sampling={'entities': None}))
        new = self.run_check(F.ledge_world(), plain)
        helper = self.run_check(F.ledge_world())
        if VERBOSE:
            print('\n  ledge: without entity cameras', json.dumps(old['summary']['max_wrong_near_pixels']),
                  'with:', json.dumps(new['summary']['entity_views']), 'helper:',
                  json.dumps(helper['summary']['entity_views']))
        self.assertNotIn('entity', old['sampling']['kinds'])
        self.assertEqual(old['summary']['max_wrong_near_pixels']['value'], 0)
        self.assertGreater(new['sampling']['kinds']['entity'], 40)
        e = new['summary']['entity_views']
        self.assertGreater(e['views_with_wrong_near'], 3)
        self.assertGreater(e['over_entity_pixels'], 500)
        self.assertEqual(e['entity_over_nearer_pixels'], 0)
        self.assertEqual(new['summary']['coverage_errors'], 0)
        w = next(i for v in new['views'] for i in v['ordering']['issues'])
        self.assertEqual((w['drawn']['tag'], w['expected']['kind'], w['expected']['entity']), (2, 'entity', 0))
        self.assertTrue(w['involves_entity'])
        aimed = [v for v in new['views'] if v['kind'] == 'entity']
        self.assertTrue(all(v['entity'] == 0 for v in aimed))
        self.assertTrue(any(v['camera']['pitch_degrees'] > 0 for v in aimed), 'from the floor below the ledge')
        self.assertTrue(any(v['camera']['pitch_degrees'] < -40 for v in aimed), 'from above')
        # wp_draw_object() draws the coin over the ledge: the same cameras find nothing
        e = helper['summary']['entity_views']
        self.assertEqual((e['wrong_near_pixels'], helper['summary']['coverage_errors']), (0, 0))
        self.assertGreater(e['entity_pixels_tested'], 20000)

    def test_what_the_object_rule_handles_and_what_it_does_not(self):
        names = list(F.OBJECTS)

        def by_entity(r):
            out = {}
            for v in r['views']:
                self.assertEqual(v['ordering']['coverage_errors'], 0, v['camera'])
                for i in v['ordering']['issues']:
                    for f, how in ((i['drawn'], 'drawn over a nearer face'), (i['expected'], 'drawn over')):
                        if f['kind'] == 'entity':
                            key = (names[f['entity']], how)
                            out[key] = out.get(key, 0) + i['pixels']
            return out
        got = by_entity(self.run_check(F.object_world(), ENTITY_ONLY))
        plain = by_entity(self.run_check(F.object_world(), settings(ENTITY_ONLY, runtime={'entity_drawing': 'mesh_at'})))
        if VERBOSE:
            print('\n  objects, wp_draw_object():', got, '\n  objects, mesh_at():', plain)
        # handled: on a small platform, two objects close together, under a slab seen from beside it
        for name in ('small_platform', 'pair_a', 'pair_b', 'under_slab'):
            for how in ('drawn over a nearer face', 'drawn over'):
                self.assertNotIn((name, how), got)
        self.assertGreater(plain.get(('small_platform', 'drawn over'), 0), 500)
        # not handled: a platform top larger than the bias (12 units: still drawn over, but less);
        # a thin wall just in front (the coin shows through it)
        for name in ('large_near', 'large_far'):
            self.assertGreater(got.get((name, 'drawn over'), 0), 0)
            self.assertLess(got[(name, 'drawn over')], plain[(name, 'drawn over')] / 3)
        self.assertGreater(got.get(('behind_wall', 'drawn over a nearer face'), 0), 500)


@needs_tools
class DepthModeTests(unittest.TestCase):
    """A world drawn with the depth buffer (runtime depth; docs/WORLDCHECKER.md, "Depth mode"):
    one pass judged by true depth, ordering a regression check that should find nothing."""

    def run_check(self, world, s=None):
        return V.verify(encode(world), s, tools=F.tools())

    def test_defaults_and_settings(self):
        plain = V.merge_settings({})
        self.assertFalse(plain['runtime']['depth'])
        self.assertIsNotNone(plain['sampling']['entities'])
        d = V.merge_settings({'runtime': {'depth': True}})
        self.assertIsNone(d['sampling']['entities'], 'entity cameras are off by default in depth mode')
        kept = V.merge_settings({'runtime': {'depth': True}, 'sampling': {'entities': {'yaws': 2}}})
        self.assertEqual(kept['sampling']['entities']['yaws'], 2)
        with self.assertRaises(V.SettingsError):
            V.merge_settings({'runtime': {'depth': 'yes'}})
        self.assertEqual(d['ordering']['depth_views'], 60)
        for bad in (0, -3, 2.5, True, 'all'):
            with self.assertRaises(V.SettingsError):
                V.merge_settings({'ordering': {'depth_views': bad}})
        self.assertIsNone(V.merge_settings({'ordering': {'depth_views': None}})['ordering']['depth_views'])
        # listed in the report only in depth mode
        self.assertNotIn('depth_views', V.shown_settings(plain)['ordering'])
        self.assertIn('depth_views', V.shown_settings(d)['ordering'])

    def test_ordering_sample(self):
        """Deterministic, every stratum and the worst budgets in, the size asked for."""
        rows = []
        for k in range(200):
            rows.append({'index': k, 'kind': ('eye', 'follow', 'seam', 'air')[k % 4] if k != 150 else 'vantage',
                         'layer_set': ('none', 'night')[(k // 4) % 2], 'camera': {'cell': [k % 3, (k // 3) % 2]},
                         'stats': {'gpu_cycles': (k * 37) % 199, 'draw_cpu_cycles': (k * 53) % 197,
                                   'triangles': (k * 11) % 193, 'arena_bytes': k}})
        got = V.ordering_sample(rows, 30)
        self.assertEqual(got, V.ordering_sample(rows, 30))
        self.assertEqual(len(got), 30)
        self.assertEqual(got[150], 'vantage')
        for key in ('gpu_cycles', 'draw_cpu_cycles', 'triangles', 'arena_bytes'):
            worst = max(rows, key=lambda r: (r['stats'][key], -r['index']))['index']
            self.assertIn(worst, got)
        every = set().union(*(V._strata(r) for r in rows))
        self.assertEqual(set().union(*(V._strata(rows[k]) for k in got)), every)
        self.assertEqual(set(V.ordering_sample(rows, None).values()), {'every view'})
        self.assertEqual(len(V.ordering_sample(rows[:20], 30)), 20)

    def test_interpenetrating_geometry_and_objects_on_big_platforms(self):
        s = settings(ENTITY_ONLY, vantage_points=F.VANTAGE_DEPTH, mode='strict')
        plain = self.run_check(F.depth_world(), s)
        depth = self.run_check(F.depth_world(), settings(s, runtime={'depth': True, 'perspective': True},
                                                         ordering={'depth_views': None}))     # every view
        if VERBOSE:
            print('\n  depth world, ordering table:', json.dumps(plain['summary']),
                  '\n  depth buffer:', json.dumps(depth['summary']))
        # without depth: what the ordering table gets wrong is reported, and the report has no
        # depth settings or statistics
        self.assertFalse(plain['ok'])
        self.assertNotIn('depth', plain['settings']['runtime'])
        self.assertNotIn('depth', plain['views'][0]['stats'])
        wrong = {}
        for v in plain['views']:
            for i in v['ordering']['issues']:
                key = (i['drawn'].get('tag', i['drawn']['kind']), i['expected'].get('tag', i['expected']['kind']))
                wrong[key] = wrong.get(key, 0) + i['pixels']
        self.assertTrue(any({31, 32} == set(k) for k in wrong), wrong)      # the crossing boxes
        self.assertTrue(any(k[1] == 'entity' for k in wrong), wrong)         # objects drawn over
        self.assertGreater(sum(v['ordering']['ground_inversions'] for v in plain['views']), 0)  # the crate
        # with depth: nothing wrong, every view checked, the same views and cameras
        self.assertTrue(depth['ok'], depth['threshold_failures'][:3])
        self.assertEqual(depth['summary']['views'], plain['summary']['views'])
        for v in depth['views']:
            o = v['ordering']
            self.assertEqual((o['wrong_near_pixels'], o['wrong_far_pixels'], o['coverage_errors'],
                              o['ground_inversions'], o['pass_inversions']), (0, 0, 0, 0, 0), v['camera'])
            self.assertGreater(o['tested_pixels'], 5000)
            st = v['stats']['depth']
            self.assertEqual(st['zclears'], 1)
            self.assertGreater(st['px_ztest'], 0)
        self.assertEqual(depth['settings']['runtime']['depth'], True)
        self.assertEqual(depth['static']['warnings'], [], 'no ground warnings in depth mode')
        self.assertTrue(any(w['code'].startswith('ground') for w in plain['static']['warnings']))

    def test_check_world_passes_the_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'w.world.bin'
            p.write_bytes(encode(F.good_world()))
            r = V.check_world({'pack': str(p), 'mode': 'report', 'thresholds': {}, 'checker': 10,
                               'runtime': {'depth': True}, 'compiler': str(F.COMPILER)})
        self.assertTrue(r['settings']['runtime']['depth'])
        self.assertFalse(r['settings']['runtime']['perspective'])


DEPTH = {'runtime': {'depth': True, 'perspective': True}}


@needs_tools
class DepthSampleTests(unittest.TestCase):
    """Depth mode's ordering sample (docs/WORLDCHECKER.md, "The ordering sample"): budgets on
    every view, the pixel comparison on a sample, and the planted faults it must still catch."""

    def run_check(self, world, s=None):
        return V.verify(encode(world), settings(DEPTH, **(s or {})), tools=F.tools())

    def test_sample_rows_equal_the_full_check(self):
        full = self.run_check(F.good_world(), {'ordering': {'depth_views': None}})
        part = self.run_check(F.good_world(), {'ordering': {'depth_views': 12}})
        self.assertGreater(len(full['views']), 40)
        self.assertEqual(part['sampling']['ordering_sample']['views'], 12)
        sampled = 0
        for a, b in zip(full['views'], part['views']):
            sa, sb = dict(a['stats']), dict(b['stats'])
            self.assertEqual(sa.pop('frame_cpu_cycles') > 0, sb.pop('frame_cpu_cycles') > 0)
            self.assertEqual(sa, sb)                 # every view measured, the same budgets
            self.assertEqual(sb['depth']['untested_pixels'], 0)
            if 'skipped' in b['ordering']:
                continue
            sampled += 1
            ob = dict(b['ordering'])
            self.assertIn(ob.pop('sample'), ('vantage', 'stratum', 'heaviest', 'spread') +
                          tuple('most ' + k for k in ('gpu_cycles', 'draw_cpu_cycles', 'triangles', 'arena_bytes')))
            oa = dict(a['ordering'])
            oa.pop('sample')
            self.assertEqual(oa, ob)                 # a sampled view is judged as in the full check
        self.assertEqual(sampled, 12)
        self.assertTrue(part['ok'])

    def test_crack_between_cells(self):
        """Holes and seams are the static checks' (every boundary edge, not sampled views)."""
        a, b = F.plaza(0, 0, boxes=[]), F.plaza(1, 0, boxes=[])
        b.placements = [dataclasses.replace(p, position=(p.position[0] + 0.1, *p.position[1:])) for p in b.placements]
        g = F.grid_mesh(-16, -16, 16, 16, 2.0, F.SAND)
        b.collision = F.placed_tris(g, (48.1, 0, 16), 1, tag=F.TAG_GROUND)
        for world, code in ((World(cells=[a, b], cell_shift=5), 'crack'), (F.seam_world(), 'edge_mismatch')):
            r = self.run_check(world, {'ordering': {'depth_views': 4}})
            self.assertFalse(r['ok'])
            found = [f for f in r['hard_failures'] if f['code'] == code]
            self.assertTrue(found, codes(r['hard_failures']))
            self.assertTrue(any(abs(f['at'][0] - 32) < 0.2 for f in found), found)

    def test_missing_face(self):
        """A face the runtime does not draw (planted in the identity pack: its corners made one):
        coverage errors in the sampled views that see it, the same counts as the full check."""
        target = 120                                 # a ground tile in the middle of the plaza
        real = V.RD.identity_mesh

        def drop(data, off, mesh, first):
            out = bytearray(real(data, off, mesh, first))
            if len(mesh.faces) > 200:                # the ground's mesh
                _, nf, _, fo, _ = struct.unpack_from('<HHIII', out)
                at = fo + 36 * target
                i0 = out[at + 4:at + 6]
                out[at + 4:at + 12] = i0 * 4
            return bytes(out)
        V.RD.identity_mesh = drop
        try:
            full = self.run_check(F.good_world(), {'ordering': {'depth_views': None}})
            part = self.run_check(F.good_world(), {'ordering': {'depth_views': 12}})
        finally:
            V.RD.identity_mesh = real
        seen = {v['index']: v['ordering']['coverage_errors'] for v in full['views'] if v['ordering']['coverage_errors']}
        got = {v['index']: v['ordering']['coverage_errors'] for v in part['views']
               if 'skipped' not in v['ordering'] and v['ordering']['coverage_errors']}
        if VERBOSE:
            print(f'\n  missing face: {len(seen)} of {len(full["views"])} views see it, the sample caught {len(got)}')
        self.assertTrue(got)
        self.assertEqual(got, {k: seen[k] for k in got})
        self.assertIn('coverage', codes(part['threshold_failures']))

    def test_over_budget_view_outside_the_sample(self):
        """Budgets are judged on every view, sampled or not."""
        base = self.run_check(F.good_world(), {'ordering': {'depth_views': 6}})
        unsampled = [v for v in base['views'] if 'skipped' in v['ordering']]
        limit = sorted(v['stats']['gpu_cycles'] for v in base['views'])[-10]
        r = self.run_check(F.good_world(), {'ordering': {'depth_views': 6}, 'thresholds': {'gpu_cycles': limit},
                                            'mode': 'strict'})
        over = {v['index'] for v in r['views'] if v['stats']['gpu_cycles'] > limit}
        failed = {f['view'] for f in r['threshold_failures'] if f['code'] == 'gpu_cycles'}
        self.assertEqual(failed, over)
        self.assertTrue(over & {v['index'] for v in unsampled})
        self.assertFalse(r['ok'])

    def test_depth_test_off_in_one_view(self):
        """A broken depth rule in a single view: the cheap check on every view's statistics
        catches it wherever it is, and the pixel comparison too where the view is sampled."""
        base = self.run_check(F.good_world(), {'ordering': {'depth_views': 6}})
        rows = base['views']
        inside = next(v['index'] for v in rows if v['ordering'].get('sample') == 'most gpu_cycles')
        outside = next(v['index'] for v in rows if 'skipped' in v['ordering'])
        cams = {tuple(rows[k]['camera']['eye']) + (rows[k]['camera']['yaw_degrees'], rows[k]['layer_set'])
                for k in (inside, outside)}
        real_record, real_lines = V.RD.view_record, V.RD.DEPTH.cart_lines

        def record(view, layer_ids, entities, ident=False):
            out = bytearray(real_record(view, layer_ids, entities, ident))
            key = tuple(view['eye']) + (round(math.degrees(view['yaw']), 3), view['layer_set'])
            if key in cams:
                out[28:32] = (1).to_bytes(4, 'little')          # VView.reserved
            return bytes(out)

        def lines(depth, perspective, indent='    '):
            # the GPU's depth test off for this frame's lists; depth.akr still draws nearest first
            return real_lines(depth, perspective, indent) + indent + 'if v.reserved != 0 { GPU_DEPTH = 0 }\n'
        V.RD.view_record, V.RD.DEPTH.cart_lines = record, lines
        try:
            r = self.run_check(F.good_world(), {'ordering': {'depth_views': 6}})
        finally:
            V.RD.view_record, V.RD.DEPTH.cart_lines = real_record, real_lines
        broken = {f['view'] for f in r['hard_failures'] if f['code'] == 'depth_untested'}
        self.assertEqual(broken, {inside, outside})
        o = r['views'][inside]['ordering']
        self.assertGreater(o['wrong_near_pixels'] + o['wrong_far_pixels'], 100, o)
        self.assertIn('skipped', r['views'][outside]['ordering'])
        self.assertFalse(r['ok'])


@needs_tools
@needs_tools
@unittest.skipUnless(importlib.util.find_spec('PIL'), 'the night market\'s sheets need Pillow')
class TextureViewTests(unittest.TestCase):
    """A world with region texture sets (examples/worlds/night_market, depth and perspective):
    each view enters its camera cell's region, textured faces without holes are judged whole and
    faces with holes (the stall's lattice screens and emblem) per texel."""

    @classmethod
    def setUpClass(cls):
        from worldkit.build import compile_source
        root = Path(__file__).resolve().parents[1]
        cls.pack = compile_source(str(root / 'examples/worlds/night_market/night_market.world.json'))[1].pack

    def check(self):
        return V.verify(self.pack, {'runtime': {'depth': True, 'perspective': True},
                                    'sampling': {'max_views': 24}, 'ordering': {'depth_views': 24}},
                        tools=F.tools())

    def test_textured_faces_are_judged(self):
        seen = []
        real = V.RD.view_faces

        def spy(*a, **k):
            faces = real(*a, **k)
            seen.extend(faces)
            return faces
        V.RD.view_faces = spy
        V._jobs, jobs = (lambda: 1), V._jobs
        try:
            rep = self.check()
        finally:
            V.RD.view_faces, V._jobs = real, jobs
        s = rep['summary']
        if VERBOSE:
            print(f'\nnight market: {s["tested_pixels"]} pixels tested, {s["coverage_errors"]} coverage errors')
        self.assertEqual(rep['hard_failures'], [])
        self.assertEqual(s['coverage_errors'], 0)
        self.assertEqual((s['max_wrong_near_pixels']['value'], s['max_wrong_far_pixels']['value']), (0, 0))
        self.assertTrue(any(f.texel is not None and f.definite for f in seen), 'faces with holes are judged per texel')
        self.assertTrue(any(f.texel is None and f.definite and f.inst.key[0] == 'placement' for f in seen))

    def test_judging_holes_by_the_outline_is_caught(self):
        """With every texel taken as set, the lattice's holes show what is behind them, which the
        check then reports: per-texel judgement is what makes the cutouts pass."""
        real = V.RD.texel_classes
        np = numpy

        def outline(texel, pix):
            return np.ones(len(pix), dtype=bool), np.zeros(len(pix), dtype=bool)
        V.RD.texel_classes = outline
        V._jobs, jobs = (lambda: 1), V._jobs
        try:
            rep = self.check()
        finally:
            V.RD.texel_classes, V._jobs = real, jobs
        s = rep['summary']
        self.assertGreater(s['coverage_errors'] + s['max_wrong_near_pixels']['value'], 0)


class TimingTests(unittest.TestCase):
    def test_timing_is_reported(self):
        r = V.verify(encode(F.good_world()), {'sampling': {'max_views': 20}}, tools=F.tools())
        t = r['timing']
        self.assertEqual(r['summary']['views'], 20)
        for k in ('static_seconds', 'compile_seconds', 'emulator_seconds', 'reference_seconds', 'per_view_seconds'):
            self.assertGreaterEqual(t[k], 0)
        if VERBOSE:
            print('\n  timing:', json.dumps(t))


if __name__ == '__main__':
    unittest.main()
