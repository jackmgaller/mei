"""The World Kit's build cache and parallel checks (tools/worldkit/cache.py): a cached or
parallel result is exactly the one a fresh, serial run gives, and a change to any input of a
result misses the cache.

The Asset Checker tests need NumPy, meic (MEIC) and mei-asset-probe (PROBE); the World Checker
tests also mei-headless (RUN) and mei-scene-probe (SCENE_PROBE, else beside meic). Run with
`python3 -m unittest discover -s tests -p test_worldcache.py` (make test does).
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get('MEIC', ROOT/'build/meic')).resolve()
RUNNER = Path(os.environ.get('RUN', ROOT/'build/mei-headless')).resolve()
PROBE = Path(os.environ.get('PROBE', ROOT/'build/mei-asset-probe')).resolve()
SCENE_PROBE = Path(os.environ.get('SCENE_PROBE', COMPILER.parent/'mei-scene-probe')).resolve()
sys.path.insert(0, str(ROOT/'tools'))
from worldkit import cache  # noqa: E402
from worldkit.build import build  # noqa: E402

numpy_ready = importlib.util.find_spec('numpy') is not None
asset_ready = unittest.skipUnless(numpy_ready and COMPILER.exists() and PROBE.exists(),
                                  'the Asset Checker needs NumPy, meic and mei-asset-probe')
world_ready = unittest.skipUnless(numpy_ready and COMPILER.exists() and PROBE.exists() and RUNNER.exists()
                                  and SCENE_PROBE.exists(), 'the World Checker needs NumPy and the native tools')

POLICY = {'yaw_steps': 4, 'pitches': [0.3], 'distances': [1.5]}


def recipe(name='box', nodes=None, **extra):
    return {'format': 'mei-asset', 'version': 1, 'name': name, 'verification': dict(POLICY),
            'nodes': nodes or [{'id': 'body', 'op': 'box', 'size': [2, 2, 2]}], **extra}


def lod_recipe():
    r = recipe('lodded', [{'id': 'body', 'op': 'sphere', 'radius': 1, 'rings': 6, 'segments': 12, 'material': 'paint'}],
               materials={'paint': {'color': '#c04020', 'palette': True}, 'trim': {'color': '#202020'}})
    r['lod'] = {'levels': [{'distance': 12, 'nodes': [{'id': 'body', 'op': 'sphere', 'radius': 1, 'rings': 3,
                                                        'segments': 6, 'material': 'paint'}]},
                           {'distance': 30, 'nodes': [{'id': 'body', 'op': 'box', 'size': [1.6, 1.6, 1.6],
                                                        'material': 'trim'}]}], 'cull': 60}
    return r


def crossed():
    """Two boxes through each other: the Asset Checker fails it (wrong pixels, a cycle)."""
    return recipe('crossed', [{'id': 'a', 'op': 'box', 'size': [2, .2, 2]},
                              {'id': 'b', 'op': 'box', 'size': [2, .2, 2], 'transform': {'rotate': [0, 0, 30]}}])


def lod_crossed():
    """Level 0 passes, level 2 fails."""
    r = lod_recipe()
    r['name'] = 'lod_crossed'
    r['lod']['levels'][1]['nodes'] = crossed()['nodes']
    return r


def fresh(r):
    """What the world build keeps of verify(recipe): ok and the view count, or the error."""
    from assetkit.visibility import verify
    try:
        v = verify(r, compiler=COMPILER, probe=PROBE)
    except (ValueError, OSError) as error:
        return None, (type(error).__name__, str(error))
    return {'ok': v['ok'], 'views': len(v['views'])}, None


def outcome(pair):
    verdict, error = pair
    return verdict, (type(error).__name__, str(error)) if error else None


@asset_ready
class AssetVerdictTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='mei-cache-test-')).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def verdicts(self, cache_dir=None, compiler=COMPILER, probe=PROBE):
        return cache.AssetVerdicts(cache_dir, compiler, probe)

    def test_parallel_and_cached_verdicts_equal_a_fresh_run(self):
        recipes = {r['name']: r for r in (recipe(), lod_recipe(), crossed(), lod_crossed())}
        expected = {name: fresh(r) for name, r in recipes.items()}
        self.assertEqual(expected['box'][0], {'ok': True, 'views': 4})
        self.assertEqual(expected['lodded'][0], {'ok': True, 'views': 4})
        self.assertEqual(expected['crossed'][0]['ok'], False)
        self.assertEqual(expected['lod_crossed'][0], {'ok': False, 'views': 4})
        for jobs in ('1', '4'):
            with mock.patch.dict(os.environ, MEI_KIT_JOBS=jobs):
                got = self.verdicts().run(recipes)
            self.assertEqual({n: outcome(o) for n, o in got.items()}, expected, f'{jobs} jobs')
        first = self.verdicts(self.tmp).run(recipes)
        self.assertEqual({n: outcome(o) for n, o in first.items()}, expected)
        # every level is stored now: a second run checks nothing and gives the same verdicts
        with mock.patch.object(cache, '_verify_level', side_effect=AssertionError('checked again')), \
                mock.patch.dict(os.environ, MEI_KIT_JOBS='1'):
            again = self.verdicts(self.tmp).run(recipes)
        self.assertEqual({n: outcome(o) for n, o in again.items()}, expected)

    def test_errors_are_the_checkers_and_not_stored(self):
        missing = self.tmp/'no-probe'
        from assetkit.visibility import verify
        with self.assertRaises(ValueError) as raised:
            verify(recipe(), compiler=COMPILER, probe=missing)
        got = self.verdicts(self.tmp, probe=missing).run({'box': recipe()})
        self.assertEqual(outcome(got['box']), (None, (type(raised.exception).__name__, str(raised.exception))))
        self.assertEqual(getattr(got['box'][1], 'path', None), raised.exception.path)
        self.assertFalse(list((self.tmp/'assets').rglob('*.json')) if (self.tmp/'assets').exists() else [])

    def key(self, r, **kw):
        return self.verdicts(self.tmp, **kw).key(r)

    def test_a_change_to_any_input_misses(self):
        base = recipe(materials={'a': {'color': '#102030'}, 'b': {'color': '#405060'}})
        k = self.key(base)
        self.assertEqual(k, self.key(json.loads(json.dumps(base))))

        def changed(fn):
            r = json.loads(json.dumps(base))
            fn(r)
            return self.key(r)
        self.assertNotEqual(k, changed(lambda r: r['nodes'][0]['size'].__setitem__(0, 2.5)))   # the mesh
        self.assertNotEqual(k, changed(lambda r: r['materials']['a'].__setitem__('color', '#102031')))
        self.assertNotEqual(k, changed(lambda r: r['verification'].__setitem__('yaw_steps', 5)))  # the policy
        self.assertNotEqual(k, changed(lambda r: r['verification'].__setitem__('edge_margin', 0.5)))
        self.assertNotEqual(k, changed(lambda r: r['verification'].__setitem__('depth', True)))   # depth mode
        self.assertNotEqual(k, changed(lambda r: r['verification'].__setitem__('perspective', True)))
        # a depth world's assets are checked in depth mode, under another key
        from worldkit.assets import Library, Asset
        asset = Asset('box', 'box.asset.json', base, b'', {}, {}, [])
        self.assertNotEqual(k, self.key(Library.policy_recipe(asset, {'depth': True})))
        self.assertEqual(k, self.key(Library.policy_recipe(asset, {})))
        mine = json.loads(json.dumps(base))
        mine['verification']['depth'] = False
        self.assertFalse(Library.policy_recipe(Asset('box', '', mine, b'', {}, {}, []), {'depth': True})['verification']['depth'],
                         "the recipe's own setting wins")
        self.assertNotEqual(k, changed(lambda r: r.__setitem__('materials', dict(reversed(r['materials'].items())))))
        # the native tools and the standard library meic compiles with
        for name, source in (('compiler', COMPILER), ('probe', PROBE)):
            copy = self.tmp/name
            shutil.copy(source, copy)
            with mock.patch.dict(os.environ, MEI_STDLIB=str(COMPILER.parent/'..'/'stdlib')):
                self.assertEqual(k, self.key(base, **{name: copy}))
                with copy.open('ab') as f:
                    f.write(b'\0')
                self.assertNotEqual(k, self.key(base, **{name: copy}))
        std = self.tmp/'stdlib'
        shutil.copytree(ROOT/'stdlib', std)
        with mock.patch.dict(os.environ, MEI_STDLIB=str(std)):
            self.assertEqual(k, self.key(base))
            first = next(p for p in sorted(std.rglob('*.akr')))
            first.write_text(first.read_text()+'\n')
            self.assertNotEqual(k, self.key(base))
        # Python and NumPy
        with mock.patch.object(cache, 'runtime_versions', return_value={'python': 'other', 'numpy': None}):
            self.assertNotEqual(k, self.key(base))

    def test_the_checkers_code_is_in_the_key(self):
        tools = ROOT/'tools'
        files = {f.relative_to(tools).as_posix() for f in cache.code_files(tools/'assetkit'/'visibility.py')}
        for f in ('assetkit/visibility.py', 'assetkit/compiler.py', 'assetkit/geometry.py', 'assetkit/geometry_audit.py',
                  'assetkit/preview.py', 'assetkit/schema.py', 'kitcore/native.py', 'kitcore/jsonio.py', 'meshlib.py'):
            self.assertIn(f, files)
        world = {f.relative_to(tools).as_posix() for f in cache.code_files(tools/'worldkit'/'verify.py')}
        for f in ('worldkit/verify.py', 'worldkit/verify_render.py', 'worldkit/verify_static.py',
                  'worldkit/verify_shared.py', 'worldkit/pack.py', 'assetkit/visibility.py'):
            self.assertIn(f, world)
        self.assertNotIn('worldkit/world.py', world)          # the build's own code is not
        # an edit to any of them changes the hash
        copy = self.tmp/'tools'
        shutil.copytree(tools, copy, ignore=shutil.ignore_patterns('__pycache__', 'vscode-akari', 'meinet'))
        with mock.patch.object(cache, 'TOOLS', copy):
            h = cache.code_hash(copy/'assetkit'/'visibility.py')
            for f in sorted(files):
                path = copy/f
                text = path.read_text()
                path.write_text(text+'\n# edited\n')
                self.assertNotEqual(h, cache.code_hash(copy/'assetkit'/'visibility.py'), f)
                path.write_text(text)


@world_ready
class WorldCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='mei-cache-test-')).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        shutil.copytree(ROOT/'examples'/'worlds'/'test_room', self.tmp/'room')
        self.world = str(self.tmp/'room'/'test_room.world.json')

    def build(self, out, cache_dir=None, checker='full'):
        return build(self.world, self.tmp/out, COMPILER, RUNNER, PROBE, checker=checker, cache=cache_dir)

    def outputs(self, out):
        """Every output file's bytes, but for the checker's own report, which records timings."""
        root = self.tmp/out
        files = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        check = json.loads(files.pop('verification/world-check.json'))
        check.pop('timing')
        return files, check

    def test_cached_and_parallel_builds_equal_a_serial_uncached_build(self):
        with mock.patch.dict(os.environ, MEI_KIT_JOBS='1'):
            self.build('serial')
        reference = self.outputs('serial')
        self.assertIn('report.json', reference[0])
        self.assertTrue(reference[1]['views'])
        c = self.tmp/'cache'
        first = self.build('first', c)
        self.assertNotEqual(first['verification_timing'], {'cached': True})
        second = self.build('second', c)
        self.assertEqual(second['verification_timing'], {'cached': True})
        for out in ('first', 'second'):
            self.assertEqual(self.outputs(out), reference, out)

    def test_the_world_key_covers_its_inputs(self):
        from worldkit import verify
        out = self.tmp/'out'
        self.build('out', checker='skip')
        pack = next(out.glob('*.world.bin'))
        context = {'world': 'test_room', 'stage': str(out), 'pack': str(pack), 'mode': 'report', 'thresholds': {},
                   'probe': {'radius': 0.3}, 'checker': 'full', 'compiler': str(COMPILER), 'runner': str(RUNNER)}
        k = cache.world_key(context, verify)
        self.assertEqual(k, cache.world_key(dict(context), verify))
        for field, value in (('mode', 'enforce'), ('thresholds', {'gpu_cycles': 1}), ('probe', {'radius': 0.4}),
                             ('checker', 100), ('world', 'other'), ('runtime', {'depth': True})):
            self.assertNotEqual(k, cache.world_key({**context, field: value}, verify), field)
        other = self.tmp/'other.world.bin'
        other.write_bytes(pack.read_bytes()+b'\0')
        self.assertNotEqual(k, cache.world_key({**context, 'pack': str(other)}, verify))
        tools = self.tmp/'tools'
        tools.mkdir()
        for f in (COMPILER, SCENE_PROBE):
            shutil.copy(f, tools/f.name)
        moved = {**context, 'compiler': str(tools/COMPILER.name)}
        with mock.patch.dict(os.environ, MEI_STDLIB=str(ROOT/'stdlib')):
            k2 = cache.world_key(moved, verify)
            with (tools/'mei-scene-probe').open('ab') as f:
                f.write(b'\0')
            self.assertNotEqual(k2, cache.world_key(moved, verify))
        with mock.patch.object(cache, 'runtime_versions', return_value={'python': 'other', 'numpy': None}):
            self.assertNotEqual(k, cache.world_key(context, verify))


if __name__ == '__main__':
    unittest.main()
