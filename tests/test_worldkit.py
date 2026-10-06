"""World Kit regressions (tools/mei_world.py, docs/WORLDKIT.md). Run:
python3 -m unittest discover -s tests -p test_worldkit.py

The CLI, validation, ID, palette, collision and determinism tests need only Python. The console
tests build the example worlds, compile carts that load them with stdlib/worldpack.akr and run
them headless (MEIC and RUN select the builds; skipped when they have not been built). The
Asset Checker test also needs NumPy and mei-asset-probe (PROBE). Example worlds are copied to a
temporary directory first, so their committed ID lock files are never touched. Builds skip the
World Checker (build(checker='skip')) or sample a few views, except test_report_and_gate_seam,
which runs it in full; the checker's own suite is tests/test_worldverify.py.
"""
import importlib.util
import math
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get('MEIC', ROOT/'build/meic')).resolve()
RUNNER = Path(os.environ.get('RUN', ROOT/'build/mei-headless')).resolve()
PROBE = Path(os.environ.get('PROBE', ROOT/'build/mei-asset-probe')).resolve()
sys.path.insert(0, str(ROOT/'tools'))
from kitcore.schema import validator, obj, NAME, array  # noqa: E402
from kitcore.errors import KitError  # noqa: E402
from worldkit import pack as P  # noqa: E402
from worldkit import terrain as terrain_mod  # noqa: E402
from worldkit.terrain import cross  # noqa: E402
from worldkit.build import build, compile_source  # noqa: E402
from worldkit.schema import WorldError  # noqa: E402
import mei_world  # noqa: E402
import meshlib  # noqa: E402

EXAMPLES = ROOT/'examples'/'worlds'
CLI = [sys.executable, str(ROOT/'tools'/'mei_world.py')]
tools_built = unittest.skipUnless(COMPILER.exists() and RUNNER.exists(), 'meic and mei-headless are not built')
checker_ready = unittest.skipUnless(PROBE.exists() and COMPILER.exists() and importlib.util.find_spec('numpy'),
                                    'the Asset Checker needs NumPy, meic and mei-asset-probe')


def cli(*args, stdin=None):
    r = subprocess.run(CLI + [str(a) for a in args], capture_output=True, text=True, input=stdin,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    return r.returncode, json.loads(r.stdout)


class Example:
    """A copy of an example world in a temporary directory, editable as JSON."""

    def __init__(self, tmp, name='test_room', keep_lock=False):
        folder = {'test_room': 'test_room', 'two_districts': 'two_districts', 'shrine_grounds': 'shrine_grounds',
                  'night_market': 'night_market'}[name]
        self.dir = Path(tmp)/folder
        shutil.copytree(EXAMPLES/folder, self.dir, ignore=None if keep_lock else shutil.ignore_patterns('*.ids.json'))
        self.world = self.dir/f'{name}.world.json'
        self.lock = self.dir/f'{name}.ids.json'

    def read(self, rel=None):
        return json.loads((self.dir/rel if rel else self.world).read_text())

    def write(self, value, rel=None):
        (self.dir/rel if rel else self.world).write_text(json.dumps(value, indent=2))

    def edit(self, fn, rel=None):
        value = self.read(rel)
        fn(value)
        self.write(value, rel)

    def compile(self):
        return compile_source(str(self.world))[1]

    def build(self, out, checker='skip', **kw):
        """build(). The World Checker is skipped unless the test asks for it (checker='full', or
        a number of views): most tests are about what the kit writes, not about verification,
        and the full check of two_districts takes about 8 seconds."""
        return build(str(self.world), out, COMPILER, RUNNER, PROBE, checker=checker, **kw)


def add_paths(w):
    """Paths for the test room: a raised rail along the ledge (10 units), a closed loop and a wire
    that leaves the world; the trigger's name parameter names the rail."""
    w['paths'] = {
        'rail': {'points': [[22, 2, 36], [30, 2, 36], [30, 2, 38]], 'raised': True, 'tag': 'roof'},
        'loop': {'points': [[10, 0, 10], [20, 0, 10], [20, 0, 20], [10, 0, 20]], 'closed': True},
        'wire': {'points': [[60, 6, 10], [70, 6, 10]], 'raised': True, 'tag': 'rope'},
    }
    w['cells'][0]['entities'][1]['params']['event'] = 'rail'


def build_without_asset_checker(example, out, **kw):
    """build(), with the coin's Asset Checker policy dropped so the test needs no NumPy."""
    example.edit(lambda a: a.pop('verification', None), 'assets/coin.asset.json')
    return example.build(out, **kw)


class SharedCoreTests(unittest.TestCase):
    def test_validator_takes_any_root_and_error_class(self):
        class Mine(KitError): pass
        root = obj({'name': NAME, 'items': array({'$ref': '#/$defs/item'}, 0, 4)}, ['name'])
        root['$defs'] = {'item': obj({'n': NAME}, ['n'])}
        validate = validator(root, Mine)
        validate({'name': 'ok', 'items': [{'n': 'a'}]})
        with self.assertRaises(Mine) as error:
            validate({'name': 'ok', 'items': [{'n': 'a'}, {'m': 'b'}]})
        self.assertEqual(error.exception.path, '/items/1/n')

    def test_asset_kit_still_uses_its_own_schema(self):
        from assetkit.schema import validate
        from assetkit.geometry import AssetError
        with self.assertRaises(AssetError) as error:
            validate({'format': 'mei-asset', 'version': 1, 'name': 'x', 'nodes': [{'op': 'blob'}]})
        self.assertEqual(error.exception.path, '/nodes/0/op')


class CliTests(unittest.TestCase):
    def test_schema_is_published_and_folds_in_a_game(self):
        code, schema = cli('schema')
        self.assertEqual(code, 0)
        self.assertEqual(schema['properties']['format'], {'const': 'mei-world'})
        self.assertIn('cell_file', schema['$defs'])
        self.assertIn('game', schema['$defs'])
        self.assertIn('terrain', schema['properties'])
        self.assertIn('terrain', schema['$defs']['cell_file']['x-unknown'])
        self.assertIn('sweep', schema['properties']['paths']['additionalProperties']['properties'])
        code, schema = cli('schema', '--game', EXAMPLES/'test_room'/'garden.game.mochi')
        self.assertEqual(code, 0)
        branches = schema['properties']['cells']['items']['properties']['entities']['items']['oneOf']
        trigger = [b for b in branches if b['properties']['type'] == {'const': 'trigger'}][0]
        self.assertEqual(trigger['properties']['params']['properties']['time_window'], {'enum': ['any', 'day', 'night']})
        self.assertEqual(trigger['properties']['params']['required'], ['size', 'event'])

    def test_init_validate_and_inspect(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = cli('init', Path(tmp)/'room')
            self.assertEqual(code, 0, out)
            self.assertTrue(Path(out['world']).is_file())
            self.assertFalse((Path(tmp)/'room'/'test_room.ids.json').exists())
            code, out = cli('init', Path(tmp)/'room')
            self.assertEqual((code, out['errors'][0]['path']), (1, '/arguments'))
            code, out = cli('init', Path(tmp)/'city', '--example', 'city')
            self.assertEqual(code, 0, out)
            code, out = cli('validate', Path(tmp)/'room'/'test_room.world.json')
            self.assertEqual((code, out['ok'], out['cells']), (0, True, 1))
            code, out = cli('inspect', Path(tmp)/'city'/'two_districts.world.json', '--cell', 'shrine_gate')
            self.assertEqual(code, 0, out)
            self.assertEqual([c['id'] for c in out['cells']], ['shrine_gate'])
            self.assertEqual(list(out['regions']), ['shrine'])
            # validate and inspect never write the lock file
            self.assertFalse((Path(tmp)/'city'/'two_districts.ids.json').exists())

    def test_errors_are_json_with_pointers_and_files(self):
        code, out = cli('validate', '-', stdin='{"format": "mei-world", "format": 1}')
        self.assertEqual((code, out['ok'], out['errors'][0]['path']), (1, False, '/input'))
        self.assertIn('Duplicate', out['errors'][0]['message'])
        code, out = cli('build', 'x.world.json')
        self.assertEqual((code, out['errors'][0]['path']), (1, '/arguments'))
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp, 'two_districts')
            ex.edit(lambda c: c['placements'][1].update(asset='no_such_shop'), 'cells/downtown_b.cell.json')
            code, out = cli('validate', ex.world)
            self.assertEqual(code, 1)
            self.assertEqual(out['errors'][0]['path'], '/placements/1/asset')
            self.assertTrue(out['errors'][0]['file'].endswith('downtown_b.cell.json'))


class ValidationTests(unittest.TestCase):
    def check(self, edit, path, message=None, rel=None, name='test_room', file=None):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp, name)
            if rel == 'garden.game.json':
                # The JSON game schema form (tests/worldkit), so both forms stay covered.
                shutil.copy(ROOT/'tests'/'worldkit'/'garden.game.json', ex.dir)
                ex.edit(lambda w: w.update(game='garden.game.json'))
            ex.edit(edit, rel)
            with self.assertRaises(WorldError) as error:
                ex.compile()
            self.assertEqual(error.exception.path, path, str(error.exception))
            if message: self.assertIn(message, str(error.exception))
            if file: self.assertTrue((error.exception.file or '').endswith(file), error.exception.file)

    def cell(self, fn):
        return lambda w: fn(w['cells'][0])

    def test_world_errors(self):
        self.check(lambda w: w.update(regoins={}), '/regoins', 'Unknown property')
        self.check(lambda w: w.update(terrain={}), '/terrain/materials', 'Required')
        self.check(lambda w: w['regions']['lab'].update(audio=[]), '/regions/lab/audio', 'reserved')
        self.check(lambda w: w['regions']['lab'].update(textures={'slots': '15'}), '/regions/lab/textures/slots',
                   'fonts')
        self.check(lambda w: w['regions']['lab'].update(backdrop={'elevations': [5, 0], 'sky': {'day': ['#000000'] * 2}}),
                   '/regions/lab/backdrop/elevations', 'increase')
        self.check(lambda w: w.update(cell_dir='cells'), '/cells', 'not both')
        self.check(lambda w: w['grid'].update(cell_size=48), '/grid/cell_size')
        self.check(lambda w: w.update(collision={'pad': 0.1}), '/collision/pad', 'probe radius')
        self.check(lambda w: w.update(game='nope.json'), '/game', 'No game schema')

    def test_cell_and_placement_errors(self):
        self.check(self.cell(lambda c: c['placements'][0].update(asset='missing')), '/cells/0/placements/0/asset', 'No asset recipe')
        self.check(self.cell(lambda c: c['placements'][0].update(position=[64, 0, 10])), '/cells/0/placements/0/position', 'outside cell')
        self.check(self.cell(lambda c: c['placements'][0].update(layer='nope')), '/cells/0/placements/0/layer', 'No layer')
        self.check(self.cell(lambda c: c['placements'][1].update(id='floor')), '/cells/0/placements/1/id', 'Two placements')
        self.check(self.cell(lambda c: c['placements'][0].pop('collision')), '/cells/0/placements/0/collision', 'Required')
        self.check(self.cell(lambda c: c['placements'][0].update(collision='missing_col')), '/cells/0/placements/0/collision')
        self.check(self.cell(lambda c: c.update(region='attic')), '/cells/0/region', 'No region')

        def nine_layers(w):
            w['layers'].update({f'l{k}': {} for k in range(9)})
            for k in range(9):
                w['cells'][0]['placements'].append({'id': f'p{k}', 'asset': 'ledge_block', 'position': [5 + 5 * k, 0, 5],
                                                    'collision': 'none', 'layer': f'l{k}'})
        self.check(nine_layers, '/cells/0', 'at most 8')

    def test_entity_and_game_data_errors(self):
        ent = lambda fn: self.cell(lambda c: fn(c['entities'][1]))
        self.check(ent(lambda e: e.update(type='dragon')), '/cells/0/entities/1/type', 'No entity type')
        self.check(ent(lambda e: e['params'].update(time_window='dusk')), '/cells/0/entities/1/params/time_window', 'one of')
        self.check(ent(lambda e: e['params'].pop('size')), '/cells/0/entities/1/params/size', 'Required')
        self.check(ent(lambda e: e['params'].update(target='nobody')), '/cells/0/entities/1/params/target', 'No entity')
        self.check(ent(lambda e: e['params'].update(colour=1)), '/cells/0/entities/1/params/colour', 'Unknown property')
        self.check(ent(lambda e: e['params'].update(count=300)), '/cells/0/entities/1/params/count', 'Maximum')
        self.check(ent(lambda e: e.update(id='coin_ledge')), '/cells/0/entities/1/id', 'world-wide')
        self.check(lambda g: g['types']['trigger']['params'].update(len={'type': 'u8'}),
                   '/types/trigger/params/len', 'keyword', rel='garden.game.json', file='garden.game.json')
        self.check(lambda g: g['types']['trigger']['params']['time_window'].update(default='dusk'),
                   '/types/trigger/params/time_window/default', rel='garden.game.json')

    def test_path_errors(self):
        def paths(spec):
            return lambda w: w.update(paths=spec)
        line = [[1, 1, 1], [5, 1, 1]]
        self.check(paths({'rail': {'points': [[1, 1, 1]]}}), '/paths/rail/points', '2–4095 items')
        self.check(paths({'rail': {'points': line, 'raised': 1}}), '/paths/rail/raised')
        self.check(paths({'rail': {'points': line, 'width': 1}}), '/paths/rail/width', 'Unknown property')
        self.check(paths({'Rail': {'points': line}}), '/paths/Rail')
        self.check(paths({'rail': {'points': [[1, 1, 1], [1, 1, 1], [2, 1, 1]]}}), '/paths/rail/points/1', 'repeats')
        self.check(paths({'rail': {'points': line, 'closed': True}}), '/paths/rail/points', 'at least 3')
        self.check(paths({'rail': {'points': [[1, 1, 1], [5, 1, 1], [5, 1, 5], [1, 1, 1]], 'closed': True}}),
                   '/paths/rail/points/3', 'do not repeat')
        self.check(paths({'rail': {'points': [[0, 0, 0], [16000, 0, 0], [16000, 0, 900]]}}), '/paths/rail',
                   'longer than')

    def test_cell_file_errors_name_the_file(self):
        self.check(lambda c: c.update(id='downtown_z'), '/id', 'named after its cell', rel='cells/downtown_a.cell.json',
                   name='two_districts', file='downtown_a.cell.json')
        self.check(lambda c: c.update(at=[1, 0]), '/at', 'both at', rel='cells/shrine_gate.cell.json', name='two_districts')
        self.check(lambda c: c['entities'][1]['params'].pop('target'), '/entities/1/params/target', 'Required',
                   rel='cells/downtown_b.cell.json', name='two_districts', file='downtown_b.cell.json')

    def test_palette_errors(self):
        self.check(lambda w: w['regions']['lab']['variants']['night']['colors'].update({'gate.paint': '#000000'}),
                   '/regions/lab/variants/night/colors/gate.paint', 'No palette-backed material')

        def clash(w):
            w['regions']['shrine']['palettes'] = {'first': 0}
        self.check(clash, '/regions/shrine/palettes', 'both use', name='two_districts')

        def two_colours(w):
            w['regions']['downtown']['variants']['night']['colors'] = {'paving': '#000000', 'ground_tile.paving': '#ffffff'}
        self.check(two_colours, '/regions/downtown/variants/night/colors/ground_tile.paving', 'two colours', name='two_districts')


class IdTests(unittest.TestCase):
    def test_bits_survive_edits_renames_and_deletions(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            build_without_asset_checker(ex, Path(tmp)/'out')
            lock = json.loads(ex.lock.read_text())
            self.assertEqual(lock['bits'], {'coin_ledge': 0, 'gate_switch': 1})
            # A new coin placed first gets the next bit; existing bits do not move.
            ex.edit(lambda w: w['cells'][0]['entities'].insert(0, {'id': 'coin_new', 'type': 'coin', 'position': [40, 1, 40]}))
            build_without_asset_checker(ex, Path(tmp)/'out')
            lock = json.loads(ex.lock.read_text())
            self.assertEqual(lock['bits'], {'coin_ledge': 0, 'gate_switch': 1, 'coin_new': 2})
            # Rename with "was": the bit follows; the old name is recorded.
            def rename(w):
                e = w['cells'][0]['entities'][1]
                e['was'], e['id'] = e['id'], 'coin_on_ledge'
                w['cells'][0]['entities'][2]['params']['target'] = 'coin_on_ledge'
            ex.edit(rename)
            report = build_without_asset_checker(ex, Path(tmp)/'out')
            lock = json.loads(ex.lock.read_text())
            self.assertEqual(lock['bits']['coin_on_ledge'], 0)
            self.assertEqual(lock['renamed'], {'coin_ledge': 'coin_on_ledge'})
            self.assertEqual(report['ids']['changes'], {'renamed': [['coin_ledge', 'coin_on_ledge']]})
            # Deleting retires the bit; a later entity never reuses it; re-adding revives it.
            ex.edit(lambda w: w['cells'][0]['entities'].pop(0))
            build_without_asset_checker(ex, Path(tmp)/'out')
            ex.edit(lambda w: w['cells'][0]['entities'].append({'id': 'coin_late', 'type': 'coin', 'position': [41, 1, 41]}))
            build_without_asset_checker(ex, Path(tmp)/'out')
            lock = json.loads(ex.lock.read_text())
            self.assertEqual(lock['retired'], {'coin_new': 2})
            self.assertEqual(lock['bits']['coin_late'], 3)
            ex.edit(lambda w: w['cells'][0]['entities'].append({'id': 'coin_new', 'type': 'coin', 'position': [42, 1, 41]}))
            report = build_without_asset_checker(ex, Path(tmp)/'out')
            self.assertEqual(json.loads(ex.lock.read_text())['bits']['coin_new'], 2)
            self.assertEqual(report['ids']['changes'], {'revived': ['coin_new']})
            # The pack carries the bits; the .akr names them.
            pack = P.decode((Path(tmp)/'out'/'test_room.world.bin').read_bytes())
            bits = sorted(e['saved_bit'] for e in pack.cells[(0, 0)].entities)
            self.assertEqual(bits, [0, 1, 2, 3])
            self.assertIn('const WORLD_TEST_ROOM_SAVED_COIN_NEW = 2', (Path(tmp)/'out'/'test_room.akr').read_text())

    def test_locked_builds_and_bad_renames_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            with self.assertRaisesRegex(WorldError, 'locked'):
                build_without_asset_checker(ex, Path(tmp)/'out', locked=True)
            self.assertFalse(ex.lock.exists())
            build_without_asset_checker(ex, Path(tmp)/'out')
            build_without_asset_checker(ex, Path(tmp)/'out', locked=True)     # nothing changes: fine
            ex.edit(lambda w: w['cells'][0]['entities'][0].update(was='gate_switch'))
            with self.assertRaises(WorldError) as error:
                ex.compile()
            self.assertEqual(error.exception.path, '/cells/0/entities/0/was')
            ex.edit(lambda w: w['cells'][0]['entities'][1].update(was='never_was', id='switch_x'))
            with self.assertRaisesRegex(WorldError, 'No saved entity'):
                ex.compile()
            # A hand-edited lock that gives two IDs one bit is refused.
            lock = json.loads(ex.lock.read_text())
            lock['bits']['gate_switch'] = 0
            ex.lock.write_text(json.dumps(lock))
            with self.assertRaisesRegex(WorldError, 'distinct'):
                compile_source(str(ex.world))

    def test_committed_example_locks_match_their_recipes(self):
        for name in ('test_room', 'two_districts', 'shrine_grounds'):
            with self.subTest(world=name), tempfile.TemporaryDirectory() as tmp:
                ex = Example(tmp, name, keep_lock=True)
                self.assertTrue(ex.lock.exists())
                self.assertEqual(ex.compile().lock_changes, {})


class BuildTests(unittest.TestCase):
    def test_builds_are_deterministic_and_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Example(Path(tmp)/'a', 'two_districts'), Example(Path(tmp)/'b', 'two_districts')
            # A reduced sample of the World Checker: its report must be deterministic too.
            ra = a.build(Path(tmp)/'out_a', checker=12)
            rb = b.build(Path(tmp)/'out_b', checker=12)
            for f in ('two_districts.world.bin', 'two_districts.akr', 'city.game.akr', 'two_districts.swatch',
                      'two_districts.ids.json', 'report.json'):
                self.assertEqual((Path(tmp)/'out_a'/f).read_bytes(), (Path(tmp)/'out_b'/f).read_bytes(), f)
            self.assertEqual(sorted(ra['files']), ['city.game.akr', 'report.json', 'source', 'two_districts.akr',
                                                   'two_districts.ids.json', 'two_districts.swatch', 'two_districts.world.bin',
                                                   'verification'])
            # report.json keeps the World Checker's summary and failures; the row per view stays
            # in the checker's own report.
            checked = json.loads((Path(tmp)/'out_a'/'report.json').read_text())['verification']
            self.assertNotIn('views', checked)
            self.assertIn('summary', checked)
            self.assertIn('threshold_failures', checked)
            self.assertEqual(checked['views_report'], 'verification/world-check.json')
            full = json.loads((Path(tmp)/'out_a'/'verification'/'world-check.json').read_text())
            self.assertEqual(len(full['views']), checked['summary']['views'])
            self.assertLessEqual(checked['summary']['views'], 12)
            self.assertEqual(checked['reduced']['max_views'], 12)
            source = sorted(str(p.relative_to(Path(tmp)/'out_a'/'source')) for p in (Path(tmp)/'out_a'/'source').rglob('*.json'))
            self.assertIn('cells/shrine_gate.cell.json', source)
            self.assertIn('assets/shop.asset.json', source)
            self.assertEqual((Path(tmp)/'out_a'/'source'/'city.game.mochi').read_text(),
                             (EXAMPLES/'two_districts'/'city.game.mochi').read_text())
            # A failing build leaves the previous outputs in place.
            before = (Path(tmp)/'out_a'/'two_districts.world.bin').read_bytes()
            a.edit(lambda c: c['placements'][0].update(position=[999, 0, 0]), 'cells/downtown_a.cell.json')
            with self.assertRaises(WorldError):
                a.build(Path(tmp)/'out_a')
            self.assertEqual((Path(tmp)/'out_a'/'two_districts.world.bin').read_bytes(), before)
            # The recipe directory is not an output directory.
            with self.assertRaisesRegex(WorldError, 'overwrite'):
                b.build(b.dir)

    def test_report_and_gate_seam(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            # The one build in this suite with the full World Checker, as make's world rule runs it.
            report = build_without_asset_checker(ex, Path(tmp)/'out', checker='full')
            cell = report['cells'][0]
            self.assertEqual(cell['layers'], ['gate_closed', 'gate_open'])
            self.assertEqual(cell['triangles']['by_layer'], {'gate_closed': 12, 'gate_open': 12})
            self.assertGreater(cell['collision']['stripped_resting'], 0)
            self.assertEqual(report['regions']['lab']['palette']['classes']['emissive']['entries'], 1)
            self.assertEqual(report['verification']['mode'], 'report')
            self.assertTrue(report['verification']['ran'])
            self.assertNotIn('timing', report['verification'])
            self.assertTrue(all(not a['recipe'].startswith('/') for a in report['assets'].values()))
            self.assertEqual(report['assets']['canopy_col']['used_as'], ['collision'])
            self.assertNotIn('reduced', report['verification'])
            self.assertEqual(report['verification']['summary']['views'],
                             len(json.loads((Path(tmp)/'out'/'verification'/'world-check.json').read_text())['views']))

    def test_world_checker_can_be_skipped_or_reduced_but_never_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            report = build_without_asset_checker(ex, Path(tmp)/'out', checker='skip')
            self.assertEqual({k: report['verification'][k] for k in ('ran', 'ok', 'skipped')},
                             {'ran': False, 'ok': None, 'skipped': True})
            written = json.loads((Path(tmp)/'out'/'report.json').read_text())['verification']
            self.assertIn('not verified', written['reason'])
            self.assertFalse((Path(tmp)/'out'/'verification').exists())
            for bad in ('none', '0', -3, True, '2.5'):
                with self.assertRaisesRegex(WorldError, 'full, skip or a number'):
                    ex.build(Path(tmp)/'out', checker=bad)
            # A world that enforces the World Checker builds only with the full check.
            ex.edit(lambda w: w.update(verification={'mode': 'enforce'}))
            for quick in ('skip', 5):
                with self.assertRaises(WorldError) as error:
                    ex.build(Path(tmp)/'out', checker=quick)
                self.assertEqual(error.exception.path, '/verification/mode')
            code, out = cli('build', ex.world, '-o', Path(tmp)/'out', '--world-checker', 'skip')
            self.assertEqual((code, out['errors'][0]['path']), (1, '/verification/mode'))

    def test_palettes_are_packed_per_region(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp, 'two_districts')
            c = ex.compile()
            regions = c.report['regions']
            down, shrine = regions['downtown']['palette'], regions['shrine']['palette']
            self.assertEqual((down['palettes'], shrine['palettes']), ([0], [1]))
            kinds = [e['class'] for e in down['entries']]
            self.assertEqual(kinds, sorted(kinds, key=['surface', 'emissive'].index), 'surface entries come first')
            # Same class and colour share an entry across assets; share: false keeps one apart.
            paving = [e for e in down['entries'] if 'ground_tile.paving' in e['materials']][0]
            self.assertEqual(paving['materials'], ['ground_tile.paving', 'block_far.paving'])
            window = [e for e in down['entries'] if 'shop.window' in e['materials']][0]
            self.assertTrue(window['separate'])
            self.assertEqual(regions['downtown']['variants']['night'][str(window['colour'])], '#fff0b0')
            # Every textured face of every mesh in a cell samples its own region's palettes.
            pack = P.decode(c.pack)
            for (i, j), cell in pack.cells.items():
                region = pack.regions[cell.region]
                first, count = region.first_colour, len(region.variants[0][1])
                meshes = [p['mesh'] for p in cell.placements] + [cell.standin]
                for m in meshes:
                    nv, nf, vo, fo, _ = struct.unpack_from('<HHIII', c.pack, m)
                    for k in range(nf):
                        flags, _, tex, pal = c.pack[m + fo + 36 * k:m + fo + 36 * k + 4]
                        if flags & 2:
                            uv = struct.unpack_from('<H', c.pack, m + fo + 36 * k + 28)[0]
                            colour = pal * 16 + (uv & 255)
                            self.assertTrue(first <= colour < first + count, (i, j, colour))
                            self.assertEqual((tex & 15, uv >> 8), (14, 0))
            # The same shop mesh is stored once per region it is drawn in, at most.
            self.assertEqual([r.name for r in pack.regions], ['downtown', 'shrine'])
            self.assertEqual([v[0] for v in pack.regions[1].variants], ['day', 'night'])

    def test_collision_from_companion_assets_layers_and_resting_faces(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = Example(tmp).compile()
            o = P.Oracle(c.world)
            raw = lambda *p: tuple(P.fx(x) for x in p)
            (h, t), _ = o.floor(raw(38, 3, 26), 0)
            self.assertEqual((float(h) / 65536, t['surface'], t['tag']), (1.0, 2, 1))           # the slope
            (h, t), _ = o.ceiling(raw(32, 1, 30), 0)
            self.assertEqual((float(h) / 65536, t['surface'], t['tag']), (3.0, 4, 4))           # canopy_col
            hit, _ = o.ceiling(raw(37, -0.25, 26), 0)
            self.assertIsNone(hit, 'the ramp\'s underside rests on the floor and is stripped')
            gate = [t for t in o.tris if t['tag'] == 5]
            self.assertTrue(gate and all(t['layer'] == 'gate_closed' for t in gate))
            self.assertEqual(c.world.coll_pad, 0.3)
            self.assertEqual(c.world.floor_max_degrees, 40)

    def test_merged_scatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp, 'two_districts')
            c = ex.compile()
            a = [x for x in c.report['cells'] if x['id'] == 'downtown_a'][0]
            self.assertEqual(a['merged'][0]['meshes'], 1)
            self.assertEqual((a['placements'], a['drawn_placements']), (11, 4))
            pack = P.decode(c.pack)
            merged = [p for p in pack.cells[(0, 0)].placements if p['tag'] == 0xFFFF]
            self.assertEqual(len(merged), 1)
            nv, nf = struct.unpack_from('<HH', c.pack, merged[0]['mesh'])
            single = c.library.assets['bollard']
            self.assertEqual(nf, 8 * single.triangles)
            # Unmerged, each bollard is a placement of its own and the triangles are the same.
            ex.edit(lambda cell: [p.pop('merge', None) for p in cell['placements']], 'cells/downtown_a.cell.json')
            a2 = [x for x in ex.compile().report['cells'] if x['id'] == 'downtown_a'][0]
            self.assertEqual(a2['drawn_placements'], 11)
            self.assertEqual(a2['triangles'], a['triangles'])
            # Merged lanterns stay in their layer.
            s = [x for x in c.report['cells'] if x['id'] == 'shrine_gate'][0]
            self.assertEqual(s['merged'][0]['layer'], 'festival')
            self.assertEqual(s['triangles']['by_layer'], {'festival': 4 * c.library.assets['lantern'].triangles})

    def test_ground_placements(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            c = ex.compile()
            cell = P.decode(c.pack).cells[(0, 0)]
            # the room's floor is declared ground: filed first in its cell, flagged, counted
            self.assertEqual((cell.ground_count, cell.placements[0]['ground'], cell.placements[0]['tag']), (1, True, 0))
            self.assertEqual([p['ground'] for p in cell.placements[1:]], [False] * 6)
            self.assertEqual(c.report['cells'][0]['ground_placements'], 1)
            self.assertEqual(c.report['pack']['version'], '1.3')
            ex.edit(lambda w: w['cells'][0]['placements'][0].update(ground='yes'))
            with self.assertRaises(WorldError) as cm:
                ex.compile()
            self.assertEqual(cm.exception.path, '/cells/0/placements/0/ground')
        with tempfile.TemporaryDirectory() as tmp:
            # merged props stay apart by ground as by layer: a merged ground mesh is ground
            ex = Example(tmp, 'two_districts')
            ex.edit(lambda cell: [p.update(ground=True) for p in cell['placements'][3:6]], 'cells/downtown_a.cell.json')
            c = ex.compile()
            a = [x for x in c.report['cells'] if x['id'] == 'downtown_a'][0]
            self.assertEqual([(m.get('ground', False), len(m['placements'])) for m in a['merged']], [(False, 5), (True, 3)])
            pls = P.decode(c.pack).cells[(0, 0)].placements
            self.assertEqual([(p['tag'], p['ground']) for p in pls if p['ground']], [(0, True), (0xFFFF, True)])

    def test_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            ex.edit(add_paths)
            c = ex.compile()
            pack = P.decode(c.pack)
            self.assertEqual([p['name'] for p in pack.paths], ['rail', 'loop', 'wire'])
            rail, loop, wire = pack.paths
            self.assertEqual((rail['raised'], rail['closed'], rail['surface']), (True, False, 4))
            self.assertEqual((loop['raised'], loop['closed'], loop['surface'], len(loop['points'])), (False, True, 0, 5))
            self.assertEqual(rail['length'], P.fx(10))
            self.assertEqual(c.report['paths']['rail'], {'number': 0, 'points': 3, 'segments': 2, 'length': 10.0,
                                                         'raised': True, 'closed': False, 'surface': 4})
            self.assertEqual(c.report['paths']['loop']['segments'], 4)
            self.assertIn('const WORLD_TEST_ROOM_PATH_WIRE = 2', c.akr)
            self.assertIn('const WORLD_TEST_ROOM_PATHS = 3', c.akr)
            outside = [w for w in c.report['warnings'] if w['code'] == 'path_outside_cells']
            self.assertEqual([(w['path'], w['points']) for w in outside], [('wire', [1])])
            self.assertIn('rope', next(w for w in c.report['warnings'] if w['code'] == 'unmapped_tags')['tags'])
        with tempfile.TemporaryDirectory() as tmp:
            # a world without paths has an empty path table, and the same pack otherwise
            c = Example(tmp).compile()
            self.assertEqual((P.decode(c.pack).paths, c.report['paths']), ([], {}))
            self.assertNotIn('PATH', c.akr)

    def test_levels_of_detail(self):
        def add_lod(a):
            a['lod'] = {'levels': [{'distance': 20, 'nodes': [{'id': 'top', 'op': 'box', 'size': [3, 2, 3], 'open': ['bottom'],
                                                                'transform': {'translate': [0, 1, 0]}, 'material': 'stone'}]}],
                        'cull': 50, 'band': 2}
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            ex.edit(add_lod, 'assets/ledge_block.asset.json')
            ex.edit(lambda w: w.update(runtime={'near_far': 48}))
            c = ex.compile()
            pack = P.decode(c.pack)
            self.assertEqual(pack.near_far, P.fx(48))
            self.assertIn('const WORLD_TEST_ROOM_NEAR_FAR: fixed = 48.0', c.akr)
            ledge = [p for p in pack.cells[(0, 0)].placements if p['tag'] == 2][0]
            rows = ledge['lod']['rows']
            self.assertEqual([r[0] for r in rows], [P.lod_square(20), P.lod_square(50)])
            self.assertEqual(rows[1][3], 0)
            self.assertEqual(len(P.mesh_triangles(c.pack[rows[0][3]:])), 10)
            self.assertEqual(c.report['lod']['ledge_block'], {'distances': [20], 'cull': 50, 'band': 2, 'off': False,
                                                              'triangles': [12, 10]})
            self.assertEqual(c.report['assets']['ledge_block']['lod']['levels'][1]['triangles'], 10)
            self.assertEqual(sum(1 for p in pack.cells[(0, 0)].placements if p['lod']), 1)
            # the world's own distances and scale
            ex.edit(lambda w: w.update(lod={'scale': 0.5, 'assets': {'ledge_block': {'distances': [30], 'cull': None}}}))
            c = ex.compile()
            self.assertEqual(c.report['lod']['ledge_block']['distances'], [15])
            self.assertEqual(len([p for p in P.decode(c.pack).cells[(0, 0)].placements if p['lod']][0]['lod']['rows']), 1)
            ex.edit(lambda w: w.update(lod={'assets': {'ledge_block': {'off': True}, 'ramp': {'band': 1}}}))
            c = ex.compile()
            self.assertFalse(any(p['lod'] for p in P.decode(c.pack).cells[(0, 0)].placements))
            self.assertIn('lod_unused', [w['code'] for w in c.report['warnings']])
            for spec, path in (({'assets': {'ledge_block': {'distances': [10, 20]}}}, '/lod/assets/ledge_block/distances'),
                               ({'assets': {'ledge_block': {'distances': [48]}}}, '/lod/assets/ledge_block'),
                               ({'scale': 0.1}, '/lod/scale')):
                ex.edit(lambda w: w.update(lod=spec))
                with self.assertRaises(WorldError) as cm:
                    ex.compile()
                self.assertEqual(cm.exception.path, path)
        with tempfile.TemporaryDirectory() as tmp:
            c = Example(tmp).compile()
            pack = P.decode(c.pack)
            self.assertEqual((pack.near_far, pack.lod_slots, c.report['lod']), (0, 0, {}))

    def test_asset_dirs_add_directories_and_refuse_a_name_in_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            before = ex.compile().pack
            (ex.dir/'more').mkdir()
            shutil.move(str(ex.dir/'assets'/'ramp.asset.json'), str(ex.dir/'more'/'ramp.asset.json'))
            with self.assertRaisesRegex(WorldError, 'No asset recipe'):
                ex.compile()
            ex.edit(lambda w: w.update(asset_dirs=['more']))
            self.assertEqual(ex.compile().pack, before)
            shutil.copy(ex.dir/'more'/'ramp.asset.json', ex.dir/'assets'/'ramp.asset.json')
            with self.assertRaisesRegex(WorldError, 'more than one asset directory'):
                ex.compile()

    def test_assets_must_pass_their_own_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            # Two boxes that cut through each other fail the Asset Checker's geometry audit.
            ex.edit(lambda a: a['nodes'].append({'id': 'spike', 'op': 'box', 'size': [3.4, 0.2, 0.2],
                                                 'material': 'stone', 'transform': {'translate': [0, 1, 0]}}),
                    'assets/ledge_block.asset.json')
            ex.edit(lambda a: a.update(verification={'required': True, 'yaw_steps': 4, 'pitches': [0], 'distances': [1.5]}),
                    'assets/ledge_block.asset.json')
            ex.compile()           # validate/inspect do not run the checker
            if not (PROBE.exists() and importlib.util.find_spec('numpy')):
                self.skipTest('the Asset Checker needs NumPy and mei-asset-probe')
            with self.assertRaisesRegex(WorldError, 'ledge_block'):
                ex.build(Path(tmp)/'out')
            self.assertFalse((Path(tmp)/'out'/'test_room.world.bin').exists())
            # In a world drawn with the depth buffer the crossing boxes are drawn right: its assets
            # are checked in depth mode, and so is the world (docs/WORLDKIT.md, "Depth mode").
            ex.edit(lambda w: w.update(runtime={'depth': True, 'perspective': True}))
            if not (COMPILER.parent/'mei-scene-probe').exists():
                return
            report = ex.build(Path(tmp)/'out', checker=8)
            self.assertEqual(report['assets']['ledge_block']['verified_with'], {'depth': True, 'perspective': True})
            self.assertNotIn('verified_with', report['assets']['ramp'])
            settings = report['verification']['settings']['runtime']
            self.assertEqual((settings['depth'], settings['perspective']), (True, True))
            self.assertEqual(report['verification']['summary']['views'], 8)
            # an asset's own policy wins over the world's
            ex.edit(lambda a: a['verification'].update(depth=False), 'assets/ledge_block.asset.json')
            with self.assertRaisesRegex(WorldError, 'ledge_block'):
                ex.build(Path(tmp)/'out', checker=8)

    @checker_ready
    def test_required_policies_run_and_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Example(tmp).build(Path(tmp)/'out')
            self.assertEqual(report['assets']['coin']['verification'], 'passed')
            self.assertEqual(report['assets']['ramp']['verification'], 'none')


class TerrainWorld:
    """A world of terrain only, in a temporary directory: cells of 32 units over [0, 64)^2 and the
    test game schema, with a terrain and paths given by the test."""

    def __init__(self, tmp, terrain=None, paths=None, cells=((0, 0), (1, 0), (0, 1), (1, 1)), size=32, **extra):
        self.dir = Path(tmp)
        (self.dir/'assets').mkdir(exist_ok=True)
        shutil.copy(ROOT/'tests'/'worldkit'/'garden.game.json', self.dir)
        w = {'format': 'mei-world', 'version': 1, 'name': 'terrain_test', 'game': 'garden.game.json',
             'assets': 'assets', 'grid': {'cell_size': size},
             'regions': {'r': {'variants': {'day': {}, 'night': {'surface': {'multiply': '#404080'}}}}},
             'cells': [{'id': f'c{i}_{j}', 'at': [i, j], 'region': 'r'} for i, j in cells], **extra}
        if terrain is not None: w['terrain'] = terrain
        if paths is not None: w['paths'] = paths
        self.world = self.dir/'terrain_test.world.json'
        self.world.write_text(json.dumps(w))

    def compile(self):
        return compile_source(str(self.world))[1]


MATERIALS = {'grass': {'color': '#508040', 'tag': 'grass'}, 'earth': {'color': '#806040'},
             'stone': {'color': '#a0a0a0', 'tag': 'stone'}}


def field(**kw):
    return {'materials': MATERIALS, 'fields': {'main': dict({'spacing': 2, 'min': [0, 0], 'max': [64, 64],
                                                             'material': 'grass'}, **kw)}}


def mesh_world_triangles(compiled, cell, mesh):
    """A cell-local native mesh's triangles in world coordinates (floats)."""
    S = 1 << compiled.world.cell_shift
    cx, cz = cell.i * S + S / 2, cell.j * S + S / 2
    return [tuple((float(p[0]) + cx, float(p[1]), float(p[2]) + cz) for p in t) for t in P.mesh_triangles(mesh)]


def t_junctions(tris):
    """Vertices lying strictly inside another triangle's edge (seen in 3D, within 1e-6)."""
    verts = {v for t in tris for v in t}
    found = []
    for t in tris:
        for e in range(3):
            a, b = t[e], t[(e + 1) % 3]
            ab = [b[k] - a[k] for k in range(3)]
            ll = sum(c * c for c in ab)
            for v in verts:
                if v in (a, b): continue
                s = sum((v[k] - a[k]) * ab[k] for k in range(3)) / ll
                if 1e-9 < s < 1 - 1e-9 and sum((a[k] + ab[k] * s - v[k]) ** 2 for k in range(3)) < 1e-12:
                    found.append((a, b, v))
    return found


class TerrainTests(unittest.TestCase):
    """Ground heightfields and sweeps (WORLDKIT.md, "Terrain")."""

    def error(self, tmp, **kw):
        with self.assertRaises(WorldError) as caught:
            TerrainWorld(tmp, **kw).compile()
        return caught.exception

    def test_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            e = self.error(tmp, terrain=field(material='moss'))
            self.assertEqual((e.path, 'No terrain material' in str(e)), ('/terrain/fields/main/material', True))
            e = self.error(tmp, terrain=field(min=[1, 0]))
            self.assertEqual(e.path, '/terrain/fields/main/min/0')
            e = self.error(tmp, terrain=field(operations=[{'op': 'set', 'height': 1, 'area': {'rect': [0, 0, 4, 4], 'circle': [1, 1, 1]}}]))
            self.assertEqual(e.path, '/terrain/fields/main/operations/0/area')
            e = self.error(tmp, terrain=field(operations=[{'op': 'bed', 'path': 'nowhere', 'width': 2}]))
            self.assertEqual(e.path, '/terrain/fields/main/operations/0/path')
            e = self.error(tmp, terrain=field(operations=[{'op': 'hole', 'falloff': 2}]))
            self.assertEqual(e.path, '/terrain/fields/main/operations/0/falloff')
            e = self.error(tmp, terrain=field(tile=32, spacing=0.5))
            self.assertEqual(e.path, '/terrain/fields/main/tile')
            two = field()
            two['fields']['other'] = {'spacing': 2, 'min': [64, 0], 'max': [70, 8], 'material': 'grass'}
            e = self.error(tmp, terrain=two)
            self.assertIn('overlap or touch', str(e))
            sweep = {'points': [[2, 0, 2], [30, 0, 2]], 'sweep': {'profile': [[-1, 0], [1, 0]], 'material': 'stone'}}
            e = self.error(tmp, paths={'p': sweep})
            self.assertEqual(e.path, '/paths')
            e = self.error(tmp, terrain=field(), paths={'p': dict(sweep, points=[[2, 0, 2], [30, 0, 2], [2, 0, 4]])})
            self.assertEqual(e.path, '/paths/p/points/1')
            e = self.error(tmp, terrain=field(), paths={'p': dict(sweep, sweep={'profile': [[-1, 0], [1, 0], [2, -1]], 'materials': ['stone']})})
            self.assertEqual(e.path, '/paths/p/sweep/materials')
            # terrain stays reserved in a cell
            w = json.loads(TerrainWorld(tmp).world.read_text())
            w['cells'][0]['terrain'] = {}
            (Path(tmp)/'cell.world.json').write_text(json.dumps(w))
            with self.assertRaisesRegex(WorldError, 'Terrain in a cell is reserved'):
                compile_source(str(Path(tmp)/'cell.world.json'))

    def test_operations_shape_the_samples(self):
        ops = [{'op': 'set', 'area': {'rect': [0, 0, 20, 64]}, 'height': 2},
               {'op': 'add', 'area': {'circle': [40, 40, 4]}, 'height': 3},
               {'op': 'carve', 'area': {'circle': [10, 50, 4]}, 'height': -1, 'falloff': 4},
               {'op': 'fill', 'area': {'rect': [44, 0, 64, 10]}, 'height': 1.5},
               {'op': 'ramp', 'from': [24, 0, 20], 'to': [36, 6, 20], 'width': 4},
               {'op': 'terrace', 'area': {'rect': [50, 30, 64, 64]}, 'step': 1},
               {'op': 'paint', 'area': {'rect': [0, 0, 8, 8]}, 'material': 'stone'},
               {'op': 'hole', 'area': {'rect': [56, 56, 64, 64]}}]
        with tempfile.TemporaryDirectory() as tmp:
            c = TerrainWorld(tmp, terrain=field(operations=ops, height=0.25)).compile()
            f = c.terrain.fields['main']
            h = lambda x, z: f.h(x // 2, z // 2)
            self.assertEqual(h(10, 10), 2)                  # set
            self.assertEqual(h(40, 40), 3.25)               # add inside the circle
            self.assertEqual(h(40, 46), 0.25)               # outside it
            self.assertEqual(h(10, 50), -1)                 # carve
            self.assertTrue(-1 < h(10, 56) < 2)             # its falloff (4 outside the radius)
            self.assertEqual(h(10, 60), 2)                  # past the falloff: as set
            self.assertEqual(h(50, 4), 1.5)                 # fill
            self.assertEqual((h(24, 20), h(30, 20), h(36, 20)), (0, 3, 6))   # ramp
            self.assertEqual(h(30, 24), 0.25)               # beside it
            self.assertEqual(f.materials[1][1], 'stone')
            self.assertEqual(f.materials[30][30], None)
            self.assertEqual(c.report['terrain']['fields']['main']['holes'], 16)
            # terrace: smooth heights become flats a step apart, joined by banks
            t = TerrainWorld(tmp, terrain=field(operations=[
                {'op': 'ramp', 'from': [0, 0, 32], 'to': [64, 4, 32], 'width': 64},
                {'op': 'terrace', 'step': 1, 'bank': 0.5}])).compile().terrain.fields['main']
            row = [t.h(x, 16) for x in range(33)]
            self.assertEqual(row[0], 0)
            self.assertEqual(row[2], 0)                     # 0.125 terraced to the flat at 0
            self.assertEqual(row[12], 1)                    # 1.5: the end of the flat at 1 (bank: the top half)
            self.assertEqual(row[14], 1.5)                  # 1.75: halfway up the bank
            self.assertEqual(row[18], 2)
            # smooth: a spike spreads to its neighbours
            s = TerrainWorld(tmp, terrain=field(operations=[{'op': 'add', 'area': {'circle': [32, 32, 0.5]}, 'height': 16},
                                                            {'op': 'smooth'}])).compile().terrain.fields['main']
            self.assertEqual((s.h(16, 16), s.h(17, 16), s.h(17, 17)), (4, 2, 1))

    def test_heights_file_and_bed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = '\n'.join(' '.join(str(0.5 * x) for x in range(5)) for _ in range(5))
            (Path(tmp)/'g.heights').write_text('# a plane rising along x\n' + rows + '\n')
            t = field(heights='g.heights', min=[0, 0], max=[8, 8])
            c = TerrainWorld(tmp, terrain=t, cells=((0, 0),)).compile()
            self.assertEqual([c.terrain.fields['main'].h(x, 2) for x in range(5)], [0, 0.5, 1, 1.5, 2])
            self.assertEqual(c.report['terrain']['fields']['main']['triangles'], [2], 'a plane is one rectangle')
            self.assertEqual(c.terrain_files, [str((Path(tmp)/'g.heights').resolve())])
            (Path(tmp)/'g.heights').write_text('0 0 0\n')
            with self.assertRaisesRegex(WorldError, 'a row has 5'):
                TerrainWorld(tmp, terrain=t, cells=((0, 0),)).compile()
            # a bed: the ground along a path set to its line, less the depth; square at the ends
            path = {'p': {'points': [[8, 2, 32], [56, 2, 32]]}}
            b = TerrainWorld(tmp, terrain=field(operations=[{'op': 'bed', 'path': 'p', 'width': 4, 'depth': 0.5, 'falloff': 2}]),
                             paths=path).compile().terrain.fields['main']
            self.assertEqual([b.h(16, 16), b.h(16, 17), b.h(16, 18)], [1.5, 1.5, 0])
            self.assertEqual(b.h(4, 16), 1.5)               # on the end
            self.assertEqual(b.h(3, 16), 0)                 # past it: the bed ends square

    def test_flat_ground_is_two_triangles_a_tile_and_seams_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            flat = TerrainWorld(tmp, terrain=field()).compile()
            self.assertEqual(flat.report['terrain']['fields']['main']['triangles'], [8])
            self.assertEqual(flat.report['terrain']['fields']['main']['tiles'], 4)
            ops = [{'op': 'add', 'area': {'circle': [30, 34, 6]}, 'height': 9, 'falloff': 14},
                   {'op': 'terrace', 'step': 3, 'bank': 0.3},
                   {'op': 'carve', 'area': {'circle': [12, 50, 5]}, 'height': -1.5, 'falloff': 3},
                   {'op': 'paint', 'area': {'rect': [40, 0, 64, 20]}, 'material': 'stone'},
                   {'op': 'hole', 'area': {'rect': [58, 58, 64, 64]}}]
            c = TerrainWorld(tmp, terrain=field(operations=ops, steep={'degrees': 30, 'material': 'earth'},
                                                lod={'distance': 40, 'tolerance': 0.4})).compile()
            rep = c.report['terrain']['fields']['main']
            self.assertLess(rep['triangles'][0], rep['full_triangles'])
            self.assertLess(rep['triangles'][1], rep['triangles'][0])
            self.assertIn('earth', rep['materials'])
            S = 32
            levels = {}          # (cell, level) -> world triangles of the cell's field pieces
            for cell in c.world.cells:
                for pl in cell.placements:
                    if pl.tag != 0xFFFE: continue
                    self.assertEqual((pl.position, pl.yaw, pl.ground), ((cell.i * S + 16, 0, cell.j * S + 16), 0, True))
                    meshes = [pl.mesh] + ([m for _, m in pl.lod.levels] if pl.lod else [pl.mesh])
                    for lv, m in enumerate(meshes[:2]):
                        levels.setdefault(((cell.i, cell.j), lv), []).extend(mesh_world_triangles(c, cell, m))
            self.assertTrue(any(pl.lod for cell in c.world.cells for pl in cell.placements))
            # no T-junctions inside a cell's pieces at either level
            for key, tris in levels.items():
                self.assertEqual(t_junctions(tris), [], key)
            # across every seam, at every pair of levels, both sides have the same points on it
            def on(tris, axis, v):
                return {p for t in tris for p in t if abs(p[axis] - v) < 1e-9}
            for (a, b, axis, v) in (((0, 0), (1, 0), 0, 32), ((0, 1), (1, 1), 0, 32), ((0, 0), (0, 1), 2, 32), ((1, 0), (1, 1), 2, 32)):
                for la in (0, 1):
                    for lb in (0, 1):
                        self.assertEqual(on(levels[(a, la)], axis, v), on(levels[(b, lb)], axis, v), (a, b, la, lb))
            # collision is the level-0 faces, in world coordinates, floors and walls by the probe's angle
            n = sum(len([t for t in cell.collision if t.tag == 0xFFFE]) for cell in c.world.cells)
            self.assertEqual(n, rep['triangles'][0])
            kinds = [P.classify(P.front_normal(t.a, t.b, t.c), math.cos(math.radians(40)), math.cos(math.radians(45)))
                     for cell in c.world.cells for t in cell.collision]
            self.assertIn(P.KIND_WALL, kinds)
            self.assertNotIn(P.KIND_CEILING, kinds)

    def test_sweeps_cut_at_seams_with_stairs_and_caps(self):
        paths = {'walk': {'points': [[4, 0, 10], [60, 0, 10]], 'tag': 'path',
                          'sweep': {'profile': [[-1.5, -0.3], [-1, 0], [1, 0], [1.5, -0.3]],
                                    'materials': ['earth', 'stone', 'earth'], 'caps': True}},
                 'steps': {'points': [[48, 0, 40], [48, 3, 52]], 'raised': True,
                           'sweep': {'profile': [[-1, 0], [1, 0]], 'material': 'stone', 'stairs': {'rise': 0.25}}}}
        with tempfile.TemporaryDirectory() as tmp:
            c = TerrainWorld(tmp, terrain={'materials': MATERIALS}, paths=paths).compile()
            rep = c.report['terrain']['sweeps']
            self.assertEqual(rep['walk']['cells'], {'0,0': 8, '1,0': 8})        # 3 edges x 2 strip faces + a cap of 2
            self.assertEqual(rep['steps']['steps'], 12)                          # 3 / 0.25 risers
            self.assertEqual(rep['steps']['triangles'], 13 * 2 + 12 * 2)
            self.assertFalse(rep['steps']['ground'])
            by_cell = {(cell.i, cell.j): cell for cell in c.world.cells}
            tris = {k: mesh_world_triangles(c, by_cell[k], pl.mesh) for k in by_cell
                    for pl in by_cell[k].placements if pl.tag == 0xFFFD and k[1] == 0}
            seam = lambda ts: {p for t in ts for p in t if p[0] == 32}
            self.assertEqual(seam(tris[(0, 0)]), seam(tris[(1, 0)]))
            self.assertEqual(len(seam(tris[(0, 0)])), 4)
            # stairs: treads are floors at most rise apart, risers walls
            fc = math.cos(math.radians(40))
            steps = [t for t in by_cell[(1, 1)].collision if t.tag == 0xFFFD]
            floors = sorted({round(float(t.a[1]), 4) for t in steps if P.classify(P.front_normal(t.a, t.b, t.c), fc, fc) == P.KIND_FLOOR})
            self.assertEqual(len(floors), 13)
            self.assertLessEqual(max(b - a for a, b in zip(floors, floors[1:])), 0.25)
            self.assertTrue(any(P.classify(P.front_normal(t.a, t.b, t.c), fc, fc) == P.KIND_WALL for t in steps))
            # every face faces out: the top of the walk faces up
            top = [t for t in by_cell[(0, 0)].collision if t.tag == 0xFFFD and abs(float(t.a[1])) < 1e-9
                   and abs(float(t.b[1])) < 1e-9 and abs(float(t.c[1])) < 1e-9]
            self.assertTrue(top and all(P.front_normal(t.a, t.b, t.c)[1] > 0 for t in top))

    def test_materials_join_region_palettes_and_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = TerrainWorld(tmp, terrain=field(operations=[{'op': 'paint', 'area': {'rect': [0, 0, 8, 8]}, 'material': 'stone'}]))
            spec = json.loads(w.world.read_text())
            spec['regions']['r']['variants']['night']['colors'] = {'terrain.stone': '#102030', 'grass': '#000800'}
            w.world.write_text(json.dumps(spec))
            c = w.compile()
            palette = c.report['regions']['r']['palette']
            self.assertEqual([e['materials'] for e in palette['entries']], [['terrain.grass'], ['terrain.stone']])
            night = c.report['regions']['r']['variants']['night']
            self.assertEqual(sorted(night.values()), ['#000800', '#102030'])
            self.assertIn('terrain_material_unused', [x['code'] for x in c.report['warnings']])
            # every terrain face is a palette swatch face moved to the region's entries
            for cell in c.world.cells:
                for pl in cell.placements:
                    for k in range(P.mesh_info(pl.mesh)[1]):
                        at = P.mesh_info(pl.mesh)[3] + 36 * k
                        self.assertTrue(pl.mesh[at] & 2 and pl.mesh[at + 2] & 16)
                        self.assertIn(pl.mesh[at + 3] * 16 + (pl.mesh[at + 28] & 15), (1, 2))

    def test_cliffs_make_walls_and_sheets_keep_their_own_edges(self):
        ops = [{'op': 'ramp', 'from': [32, 0, 0], 'to': [32, 8, 64], 'width': 100},
               {'op': 'cliff', 'area': {'rect': [0, 40, 64, 64]}, 'height': 6, 'material': 'stone',
                'overhang': 0.5, 'lip': 1},
               # after the cliff: a ramp on the low sheet only, up to the cliff's foot
               {'op': 'ramp', 'from': [10, 0, 30], 'to': [10, 5, 40], 'width': 8}]
        with tempfile.TemporaryDirectory() as tmp:
            c = TerrainWorld(tmp, terrain=field(operations=ops)).compile()
            f = c.terrain.fields['main']
            rep = c.report['terrain']['fields']['main']
            self.assertGreater(rep['cliff_triangles'], 0)
            # the edge's samples hold a height per sheet: the low ramp's top did not move the top
            self.assertEqual(f.h(5, 20, 0.0), 5)              # x 10, z 40: the low sheet, at the ramp's end
            self.assertEqual(f.h(5, 20, 6.0), 5)              # the top sheet: still the first ramp's 5
            self.assertEqual(f.h(10, 20, 0.0), f.h(10, 20, 6.0))   # away from the second ramp: the same
            # the top's edge points move out over the wall by the overhang (toward -z, the low side)
            self.assertEqual(f.disp[((10, 20), 6.0)], (0.0, -0.5))
            # walls are part of the tile meshes with no T-junctions, and are collision (some ceiling-ish
            # at the lip, the rest walls)
            for cell in c.world.cells:
                tris = []
                for pl in cell.placements:
                    if pl.tag == 0xFFFE:
                        tris += mesh_world_triangles(c, cell, pl.mesh)
                self.assertEqual(t_junctions(tris), [], (cell.i, cell.j))
            fc = math.cos(math.radians(40))
            kinds = {P.classify(P.front_normal(t.a, t.b, t.c), fc, math.cos(math.radians(45)))
                     for cell in c.world.cells for t in cell.collision}
            self.assertIn(P.KIND_WALL, kinds)
            top = c.terrain.floors().at(30, 50)
            self.assertAlmostEqual(top[0], 8 * 50 / 64 + 6, places=3)

    def test_a_cliff_face_looks_out_over_the_lower_sheet(self):
        # Two flats cut as sheets and set after: the one at the higher offset (0.02) ends at 4, the
        # other (0.01) at 20, so the higher sheet is the lower ground. The face between them is
        # wound outward over the lower ground (toward -z), as a wall the body stops at.
        ops = [{'op': 'cliff', 'area': {'rect': [0, 32, 64, 64]}, 'height': 0.01, 'material': 'stone'},
               {'op': 'set', 'area': {'rect': [0, 32, 64, 64]}, 'height': 20},
               {'op': 'cliff', 'area': {'rect': [0, 20, 64, 32]}, 'height': 0.02, 'material': 'stone'},
               {'op': 'set', 'area': {'rect': [0, 20, 64, 32]}, 'height': 4}]
        with tempfile.TemporaryDirectory() as tmp:
            c = TerrainWorld(tmp, terrain=field(operations=ops)).compile()
            faces = [(t, m) for t, m in terrain_mod.cliff_faces(c.terrain.fields['main'], c.terrain.fields['main'].walls())
                     if all(abs(p[2] - 32) < 1e-6 for p in t)]
            self.assertTrue(faces)
            for t, _ in faces:
                n = cross(tuple(b - a for a, b in zip(t[0], t[1])), tuple(b - a for a, b in zip(t[0], t[2])))
                self.assertLess(n[2], 0, t)

    def test_water_is_semi_transparent_without_collision_and_answers_wp_water(self):
        ops = [{'op': 'carve', 'area': {'circle': [20, 20, 6]}, 'height': -1, 'falloff': 2},
               {'op': 'water', 'area': {'circle': [20, 20, 12]}, 'level': -0.25, 'material': 'pond'}]
        mats = dict(MATERIALS, pond={'color': '#3060a0', 'water': True, 'tag': 'stone'})
        t = {'materials': mats, 'fields': {'main': {'spacing': 2, 'min': [0, 0], 'max': [64, 64],
                                                    'material': 'grass', 'operations': ops}}}
        paths = {'creek': {'points': [[40, 1, 2], [40, 0.5, 60]],
                           'sweep': {'profile': [[-1, 0], [1, 0]], 'material': 'pond'}}}
        with tempfile.TemporaryDirectory() as tmp:
            c = TerrainWorld(tmp, terrain=t, paths=paths).compile()
            self.assertGreater(c.report['terrain']['fields']['main']['water_triangles'], 0)
            self.assertEqual(c.terrain.water_level(20, 20), -0.25)
            self.assertIsNone(c.terrain.water_level(60, 60))
            self.assertAlmostEqual(c.terrain.water_level(40, 31), 0.75, places=3)
            semi = 0
            for cell in c.world.cells:
                for pl in cell.placements:
                    nf, fo = P.mesh_info(pl.mesh)[1], P.mesh_info(pl.mesh)[3]
                    semi += sum(1 for k in range(nf) if pl.mesh[fo + 36 * k] & 8)
                self.assertFalse(any(t.tag == 0xFFFD for t in cell.collision), 'water sweeps have no collision')
            self.assertEqual(semi, len(c.terrain.water))
            self.assertEqual(len(c.water), 4 + 56 * len(c.terrain.water))
            self.assertIn('wpwater.akr', c.akr)
            self.assertEqual(struct.unpack_from('<I', c.water)[0], len(c.terrain.water))
            with self.assertRaisesRegex(WorldError, 'not a water material'):
                TerrainWorld(tmp, terrain=field(operations=[{'op': 'water', 'level': 0, 'material': 'grass'}])).compile()

    def test_draped_paths_follow_the_ground_and_cut_their_bed(self):
        ops = [{'op': 'ramp', 'from': [0, 0, 32], 'to': [64, 8, 32], 'width': 100}]
        paths = {'trail': {'points': [[4, 30], [60, 30]], 'drape': {'smooth': 0, 'bed': {'width': 2, 'depth': 0.25}},
                           'sweep': {'profile': [[-1, 0], [1, 0]], 'material': 'stone'}},
                 'stream': {'points': [[60, 50], [30, 50], [4, 50]], 'drape': {'downhill': True, 'step': 4}}}
        with tempfile.TemporaryDirectory() as tmp:
            c = TerrainWorld(tmp, terrain=field(operations=ops), paths=paths).compile()
            line = c.terrain.paths['trail']
            self.assertEqual(len(line), 29)                         # every 2 units
            self.assertTrue(all(abs(y - x / 8) < 1e-3 for x, y, z in line))
            f = c.terrain.fields['main']
            self.assertAlmostEqual(f.h(16, 15), 32 / 8 - 0.25, places=3)   # its bed under it
            self.assertEqual(c.report['paths']['trail']['points'], 29)
            ys = [y for _, y, _ in c.terrain.paths['stream']]
            self.assertEqual(ys, sorted(ys, reverse=True))
            bad = dict(paths, plain={'points': [[1, 2], [3, 4]]})
            with self.assertRaisesRegex(WorldError, r'\[x, z\] only on a draped path'):
                TerrainWorld(tmp, terrain=field(operations=ops), paths=bad).compile()
            bed = field(operations=ops + [{'op': 'bed', 'path': 'trail', 'width': 2}])
            with self.assertRaisesRegex(WorldError, 'cuts its own bed'):
                TerrainWorld(tmp, terrain=bed, paths=paths).compile()

    def test_things_set_on_the_ground_and_scatter(self):
        ops = [{'op': 'ramp', 'from': [0, 0, 32], 'to': [64, 8, 32], 'width': 100},
               {'op': 'water', 'area': {'circle': [50, 50, 6]}, 'level': 9, 'material': 'pond'}]
        mats = dict(MATERIALS, pond={'color': '#3060a0', 'water': True})
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)          # for its assets
            shutil.copytree(ex.dir/'assets', Path(tmp)/'w'/'assets')
            t = {'materials': mats, 'fields': {'main': {'spacing': 2, 'min': [0, 0], 'max': [64, 64],
                                                        'material': 'grass', 'operations': ops}}}
            scatter = {'blocks': {'assets': [{'asset': 'ledge_block', 'weight': 2}, {'asset': 'coin'}],
                                  'area': {'rect': [0, 0, 64, 64]}, 'spacing': 6, 'seed': 5, 'cull': 40,
                                  'exclude': [{'circle': [16, 16, 8]}], 'clearance': 2}}
            paths = {'walk': {'points': [[2, 1, 40], [62, 7.5, 40]],
                              'sweep': {'profile': [[-1, 0], [1, 0]], 'material': 'stone'}}}
            w = TerrainWorld(Path(tmp)/'w', terrain=t, paths=paths, scatter=scatter)
            spec = json.loads(w.world.read_text())
            spec['cells'][0]['placements'] = [{'id': 'p', 'asset': 'ledge_block', 'position': [8, 8], 'lift': -0.5,
                                               'collision': 'none'},
                                              {'id': 'q', 'asset': 'ledge_block', 'position': [8, 50, 12], 'drop': True,
                                               'collision': 'none'}]
            w.world.write_text(json.dumps(spec))
            c = w.compile()
            pls = {p.tag: p for p in c.world.cells[0].placements}
            self.assertAlmostEqual(pls[0].position[1], 1 - 0.5, places=3)
            self.assertAlmostEqual(pls[1].position[1], 1, places=3)
            rep = c.report['scatter']['blocks']
            self.assertGreater(rep['placed'], 20)
            self.assertTrue({'excluded', 'water', 'sweep'} <= set(rep['dropped']))
            chunks = [p for cell in c.world.cells for p in cell.placements if p.tag == 0xFFFC]
            self.assertEqual(len(chunks), rep['chunks'])
            self.assertTrue(all(p.lod and p.lod.levels[-1] == (40, None) for p in chunks))
            again = w.compile()
            self.assertEqual(again.pack, c.pack, 'the same recipe scatters the same props')
            spec['cells'][0]['placements'][0]['position'] = [8, 1, 8]
            w.world.write_text(json.dumps(spec))
            with self.assertRaisesRegex(WorldError, 'lift raises'):
                w.compile()

    def test_textured_terrain(self):
        """Terrain textures repeat in world coordinates: each face starts in the first repeat, is
        drawn from the stored repeats without a window when it fits in them, through a texture
        window when it reaches further, and never past 255 texels."""
        grass = {'pattern': 'checker', 'colors': ['#406030', '#508040'], 'size': 16, 'scale': [8, 8],
                 'projection': 'planar'}                  # 2 texels a unit; 96 stored: 47.5 units
        stone = {'pattern': 'checker', 'colors': ['#808080', '#a0a0a0'], 'size': 16, 'span': 32}   # 16 a unit
        mats = dict(MATERIALS, grass=dict(MATERIALS['grass'], texture=grass),
                    stone=dict(MATERIALS['stone'], texture=stone))
        ops = [{'op': 'paint', 'area': {'rect': [0, 0, 32, 32]}, 'material': 'stone'},
               {'op': 'ramp', 'from': [40, 0, 48], 'to': [64, 6, 48], 'width': 12}]
        t = {'materials': mats, 'fields': {'main': {'spacing': 2, 'min': [0, 0], 'max': [64, 64],
                                                    'material': 'grass', 'operations': ops,
                                                    'lod': {'distance': 30, 'tolerance': 2}}}}
        paths = {'walk': {'points': [[36, 0.5, 4], [36, 0.5, 60]],
                          'sweep': {'profile': [[-1, 0], [1, 0], [1.5, -0.5]], 'materials': ['stone', 'grass']}}}
        with tempfile.TemporaryDirectory() as tmp:
            c = TerrainWorld(tmp, terrain=t, paths=paths).compile()
            rep = c.report['terrain']['textures']
            self.assertEqual(rep['grass']['stored'], [112, 112])
            self.assertEqual(rep['grass']['windowed'], 0, 'every grass face fits in its stored repeats')
            self.assertEqual(rep['stone']['stored'], [48, 48])
            self.assertGreater(rep['stone']['windowed'], 0, 'big stone rectangles reach past 48 texels')
            self.assertEqual(rep['stone']['reach'], round((255 - 16) / 16, 3))
            self.assertTrue(rep['grass']['far'].startswith('#'))
            region = c.report['regions']['r']['textures']
            self.assertEqual(region['by_asset']['terrain']['tiles'], 3)     # grass, stone, stone's window tile
            windowed, plain = 0, 0
            for cell in c.world.cells:
                for pl in cell.placements:
                    if pl.tag not in (0xFFFE, 0xFFFD):
                        continue
                    nv, nf, vo, fo = P.mesh_info(pl.mesh)
                    table = struct.unpack_from('<I', pl.mesh, 12)[0]
                    wins = []
                    if table:
                        wins = [struct.unpack_from('<H', pl.mesh, o)[0] for o in range(table, len(pl.mesh) - 1, 2)]
                    tris = mesh_world_triangles(c, cell, pl.mesh)
                    for k in range(nf):
                        f = fo + 36 * k
                        uv = [struct.unpack_from('<H', pl.mesh, f + 28 + 2 * i)[0] for i in range(3)]
                        us, vs = [w & 255 for w in uv], [w >> 8 for w in uv]
                        window = pl.mesh[f + 2] >> 5
                        if window:
                            windowed += 1
                            half = wins[window - 1]
                            self.assertEqual((4 << (half & 7), 4 << ((half >> 8) & 7)), (16, 16))
                            self.assertLess(min(us), 16)        # starts in the first repeat
                            self.assertLess(min(vs), 16)
                            # on a level face, texel steps are world steps at 16 texels a unit
                            if len({round(p[1], 6) for p in tris[k]}) == 1:
                                (xa, _, za), (xb, _, zb) = tris[k][0], tris[k][1]
                                steps = sorted((abs(us[1] - us[0]), abs(vs[1] - vs[0])))
                                for got, want in zip(steps, sorted((16 * abs(xb - xa), 16 * abs(zb - za)))):
                                    self.assertAlmostEqual(got, want, delta=1)
                        elif pl.mesh[f] & 2 and table == 0:
                            plain += 1
            self.assertEqual(windowed, sum(r['windowed'] for r in rep.values()))
            self.assertGreater(plain, 0)
            self.assertEqual(c.report['terrain']['texture_windows']['triangles'], windowed)
            self.assertEqual(TerrainWorld(tmp, terrain=t, paths=paths).compile().pack, c.pack, 'deterministic')
            # errors: no holes, sheets or non-repeating projections; the span within 254 texels
            for bad, path in ((dict(stone, clear='#808080'), '/clear'), (dict(stone, projection='fit'), '/projection'),
                              (dict(stone, span=240), '/span'), (dict(stone, size=12), '')):
                m = dict(mats, stone=dict(mats['stone'], texture=bad))
                e = self.error(tmp, terrain=dict(t, materials=m), paths=paths)
                self.assertEqual(e.path, '/terrain/materials/stone/texture' + path, str(e))

    def test_worlds_without_terrain_report_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = Example(tmp).compile()
            self.assertNotIn('terrain', c.report)
            self.assertIsNone(c.terrain)

    def test_example_shrine_grounds(self):
        c = compile_source(str(EXAMPLES/'shrine_grounds'/'shrine_grounds.world.json'))[1]
        rep = c.report['terrain']
        f = rep['fields']['grounds']
        self.assertEqual((f['quads'], f['tiles']), (4096, 16))
        self.assertLess(f['triangles'][0], f['full_triangles'] // 3)
        self.assertEqual(rep['sweeps']['sando']['steps'], 40)
        self.assertLessEqual(max(cell['triangles']['most'] for cell in c.report['cells']), 2000)
        floors = mei_world.floors(str(EXAMPLES/'shrine_grounds'/'shrine_grounds.world.json'),
                                  ['20', '30', '47', '100', '86', '77', '76', '20'])['floors']
        self.assertEqual([(p['y'], p['from']) for p in floors],
                         [(0, 'terrain'), (3, 'terrain'), (12, 'terrain'), (0, 'sweep')])


pillow = unittest.skipUnless(importlib.util.find_spec('PIL'), 'the night market\'s sheets need Pillow')


def tri_set(mesh):
    """A native mesh's triangles as a set of vertex triples, each turned to start at its least
    corner (so the same triangle compares equal however its corners are numbered)."""
    out = set()
    for t in P.mesh_triangles(mesh):
        k = min(range(3), key=lambda i: t[i])
        out.add(tuple(t[(k + i) % 3] for i in range(3)))
    return out


def raw_mesh(verts, faces):
    """A native mesh of palette-swatch-like faces: faces are (indices, flags, colour)."""
    import meshlib
    m = meshlib.Mesh()
    for v in verts:
        m.vertex(*v)
    for idx, flags, col in faces:
        m.face(list(idx), [col] * len(idx), [(1, 0)] * len(idx), flags)
    return m.pack()


class FarLodTests(unittest.TestCase):
    """Levels of detail for distance: quads, far ground, scatter levels from the assets, thinning,
    sweep culls, cull-only recipes and stand-ins made by the kit (WORLDKIT.md)."""

    def test_quads_pair_flat_convex_pairs_only(self):
        from worldkit import quads
        sq = [(0, 0, 0), (1, 0, 0), (0, 0, 1), (1, 0, 1)]
        # a flat square in two triangles (upward, Mei's winding) becomes one quad, same triangles
        m = raw_mesh(sq, [((0, 2, 1), 0, 0x808080), ((1, 2, 3), 0, 0x808080)])
        q = quads.pair(m)
        self.assertEqual(struct.unpack_from('<H', q, 2)[0], 1)
        self.assertEqual(tri_set(q), tri_set(m))
        # folded 90 degrees: stays two faces
        fold = [(0, 0, 0), (1, 0, 0), (0, 0, 1), (1, 1, 1)]
        m2 = raw_mesh(fold, [((0, 2, 1), 0, 0x808080), ((1, 2, 3), 0, 0x808080)])
        self.assertEqual(quads.pair(m2), m2)
        # a dart (concave quad) stays two faces
        dart = [(0, 0, 0), (2, 0, 0), (0, 0, 2), (0.4, 0, 0.4)]
        m3 = raw_mesh(dart, [((0, 3, 1), 0, 0x808080), ((0, 2, 3), 0, 0x808080)])
        self.assertEqual(struct.unpack_from('<H', quads.pair(m3), 2)[0], 2)
        # different colours, semi-transparent faces and skipped flags stay as they were
        m4 = raw_mesh(sq, [((0, 2, 1), 0, 0x808080), ((1, 2, 3), 0, 0x404040)])
        self.assertEqual(quads.pair(m4), m4)
        m5 = raw_mesh(sq, [((0, 2, 1), 8, 0x808080), ((1, 2, 3), 8, 0x808080)])
        self.assertEqual(quads.pair(m5), m5)
        m6 = raw_mesh(sq, [((0, 2, 1), 16, 0x808080), ((1, 2, 3), 16, 0x808080)])
        self.assertEqual(struct.unpack_from('<H', quads.pair(m6), 2)[0], 1)
        self.assertEqual(quads.pair(m6, skip=quads.DOUBLE), m6)

    def test_quads_in_a_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            before = ex.compile()
            ex.edit(lambda w: w.update(meshes={'quads': True}))
            after = ex.compile()
            pb, pa = P.decode(before.pack), P.decode(after.pack)
            fb = fa = 0
            for key, cell in pb.cells.items():
                for x, y in zip(cell.placements, pa.cells[key].placements):
                    self.assertEqual(tri_set(before.pack[x['mesh']:]), tri_set(after.pack[y['mesh']:]))
                    self.assertEqual(x['sphere'], y['sphere'])
                    fb += P.mesh_info(before.pack[x['mesh']:])[1]
                    fa += P.mesh_info(after.pack[y['mesh']:])[1]
            self.assertLess(fa, fb * 0.8)

    def test_far_ground_levels_and_skirts(self):
        ops = [{'op': 'ramp', 'from': [0, 0, 32], 'to': [64, 12, 32], 'width': 100},
               {'op': 'add', 'area': {'circle': [40, 40, 12]}, 'height': 4, 'falloff': 12}]
        t = field(operations=ops, tile=16, lod={'distance': 20, 'tolerance': 0.5})
        with tempfile.TemporaryDirectory() as tmp:
            plain = TerrainWorld(tmp, terrain=t).compile()
            w = TerrainWorld(tmp, terrain=t, lod={'ground': [{'distance': 40, 'grid': 8}, {'distance': 80, 'grid': 16}]})
            c = w.compile()
            self.assertNotEqual(c.pack, plain.pack)
            rep = c.report['far_ground']
            self.assertEqual(rep['levels'][0], {'distance': 40, 'grid': 8})
            self.assertGreater(rep['tiles'][0], 0)
            from worldkit import farground
            tiles = [p for cell in c.world.cells for p in cell.placements if p.tag == 0xFFFE]
            self.assertTrue(any(p.lod and len(p.lod.levels) > 1 for p in tiles))
            for p in tiles:
                if not p.lod:
                    continue
                ds = [d for d, _ in p.lod.levels]
                self.assertEqual(ds, sorted(ds))
                for d, m in p.lod.levels[1:]:
                    # far levels: fewer faces, every corner on the tile's own surface (or a
                    # skirt's foot below it)
                    self.assertLess(P.mesh_info(m)[1], P.mesh_info(p.lod.levels[0][1])[1])
            # a grid resampled from a known slope: heights exact, no skirt where the edges are straight
            slope = raw_mesh([(-8, 0, -8), (8, 4, -8), (-8, 0, 8), (8, 4, 8)],
                             [((0, 2, 1), 0, 0x808080), ((1, 2, 3), 0, 0x808080)])
            l8, l16 = farground.far_levels(slope, [8, 16])
            self.assertEqual(P.mesh_info(l8)[1], 8)
            self.assertEqual(P.mesh_info(l16)[1], 2)
            for v in P.mesh_vertices(l8):
                self.assertAlmostEqual(float(v[1]), (float(v[0]) + 8) / 4, places=3)
            bump = raw_mesh([(-8, 0, -8), (0, 0, -8), (8, 0, -8), (-8, 0, 0), (0, 3, 0), (8, 0, 0),
                             (-8, 0, 8), (0, 2, 8), (8, 0, 8)],
                            [((0, 3, 1), 0, 0x808080), ((1, 3, 4), 0, 0x808080), ((1, 4, 2), 0, 0x808080),
                             ((2, 4, 5), 0, 0x808080), ((3, 6, 4), 0, 0x808080), ((4, 6, 7), 0, 0x808080),
                             ((4, 7, 5), 0, 0x808080), ((5, 7, 8), 0, 0x808080)])
            (b16,) = farground.far_levels(bump, [16])
            # the 16-unit square cuts the ridge at z = 8 (its edge runs at height 0 over a point
            # at 2): no skirt needed there, since the edge stands below; none above either
            self.assertEqual(P.mesh_info(b16)[1], 2)
            hollow = raw_mesh([(-8, 1, -8), (0, 1, -8), (8, 1, -8), (-8, 1, 0), (0, 1, 0), (8, 1, 0),
                               (-8, 1, 8), (0, -1, 8), (8, 1, 8)],
                              [((0, 3, 1), 0, 0x808080), ((1, 3, 4), 0, 0x808080), ((1, 4, 2), 0, 0x808080),
                               ((2, 4, 5), 0, 0x808080), ((3, 6, 4), 0, 0x808080), ((4, 6, 7), 0, 0x808080),
                               ((4, 7, 5), 0, 0x808080), ((5, 7, 8), 0, 0x808080)])
            (h16,) = farground.far_levels(hollow, [16])
            self.assertEqual(P.mesh_info(h16)[1], 3, 'a skirt where the straight edge stands over the dip')
            (h16b,) = farground.far_levels(hollow, [16], skirted=lambda a, b: False)
            self.assertEqual(P.mesh_info(h16b)[1], 2)
            with self.assertRaises(WorldError) as cm:
                TerrainWorld(tmp, terrain=t, lod={'ground': [{'distance': 21, 'grid': 8}]}).compile()
            self.assertEqual(cm.exception.path, '/lod/ground')

    def scatter_world(self, tmp, scatter, **extra):
        ex = Example(tmp)
        def lod(a):
            a['lod'] = {'levels': [{'distance': 20, 'nodes': [{'id': 'top', 'op': 'box', 'size': [3, 2, 3],
                                                                'open': ['bottom'], 'material': 'stone',
                                                                'transform': {'translate': [0, 1, 0]}}]}],
                        'cull': 50, 'band': 2}
        ex.edit(lod, 'assets/ledge_block.asset.json')
        ex.edit(lambda a: a.update(lod={'cull': 30}), 'assets/ramp.asset.json')
        shutil.copytree(ex.dir/'assets', Path(tmp)/'w'/'assets')
        return TerrainWorld(Path(tmp)/'w', terrain=field(), scatter=scatter, **extra)

    def test_scatter_levels_from_the_assets_and_thinning(self):
        base = {'assets': [{'asset': 'ledge_block'}, {'asset': 'ramp'}], 'area': {'rect': [0, 0, 64, 64]},
                'spacing': 6, 'seed': 2, 'chunk': 32}
        with tempfile.TemporaryDirectory() as tmp:
            c = self.scatter_world(tmp, {'s': dict(base, lod='assets')}).compile()
            chunks = [p for cell in c.world.cells for p in cell.placements if p.tag == 0xFFFC]
            self.assertTrue(chunks)
            for p in chunks:
                ds = [d for d, _ in p.lod.levels]
                # the ramp is culled at 30, the block switches at 20 and is culled at 50
                self.assertEqual(ds, [20, 30, 50])
                self.assertIsNone(p.lod.levels[-1][1])
                self.assertLess(P.mesh_info(p.lod.levels[1][1])[1], P.mesh_info(p.lod.levels[0][1])[1])
            # the scatter's cull caps them; thinning keeps a share, grown
            c2 = self.scatter_world(tmp + '/b', {'s': dict(base, lod='assets', cull=40,
                                                          thin={'distance': 25, 'keep': 0.5, 'scale': 1.5})}).compile()
            chunks2 = [p for cell in c2.world.cells for p in cell.placements if p.tag == 0xFFFC]
            for p in chunks2:
                ds = [d for d, _ in p.lod.levels]
                self.assertEqual(ds[-1], 40)
                self.assertIn(25, ds)
            # without lod, a scatter is built as before
            plain = self.scatter_world(tmp + '/c', {'s': dict(base, coarse=20, cull=40)}).compile()
            self.assertTrue(all([d for d, _ in p.lod.levels] == [20, 40]
                                for cell in plain.world.cells for p in cell.placements if p.tag == 0xFFFC))
            for bad, path in ((dict(base, lod='assets', coarse=10), '/scatter/s/coarse'),
                              (dict(base, thin={'distance': 10, 'keep': 0.5}), '/scatter/s/thin')):
                with self.assertRaises(WorldError) as cm:
                    self.scatter_world(tmp + '/d' + path[-4:], {'s': bad}).compile()
                self.assertEqual(cm.exception.path, path)

    def test_cull_only_recipes_and_sweep_culls(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            ex.edit(lambda a: a.update(lod={'cull': 40}), 'assets/ledge_block.asset.json')
            c = ex.compile()
            ledge = [p for p in P.decode(c.pack).cells[(0, 0)].placements if p['tag'] == 2][0]
            self.assertEqual([(r[0], r[3]) for r in ledge['lod']['rows']], [(P.lod_square(40), 0)])
            self.assertEqual(c.report['lod']['ledge_block']['cull'], 40)
        paths = {'walk': {'points': [[2, 1, 40], [62, 1, 40]], 'sweep': {'profile': [[-1, 0.2], [1, 0.2]], 'material': 'stone'}},
                 'stair': {'points': [[2, 1, 10], [62, 1, 10]], 'sweep': {'profile': [[-1, 0.2], [1, 0.2]], 'material': 'stone'}}}
        with tempfile.TemporaryDirectory() as tmp:
            c = TerrainWorld(tmp, terrain=field(), paths=paths,
                             lod={'sweeps': {'cull': 60, 'paths': {'stair': {'cull': None}}}}).compile()
            sweeps = [p for cell in c.world.cells for p in cell.placements if p.tag == 0xFFFD]
            self.assertTrue(sweeps)
            for p in sweeps:
                cz = P.mesh_vertices(p.mesh)[0][2] + p.position[2]
                if cz > 24:
                    self.assertEqual(p.lod.levels, [(60, None)], 'the walk is culled from 60')
                else:
                    self.assertIsNone(p.lod, 'the stair is never culled')

    def test_standins_made_by_the_kit(self):
        ops = [{'op': 'ramp', 'from': [0, 0, 32], 'to': [64, 10, 32], 'width': 100}]
        scatter = {'s': {'assets': [{'asset': 'ledge_block'}, {'asset': 'ramp'}], 'area': {'rect': [0, 0, 64, 64]},
                         'spacing': 6, 'seed': 2, 'chunk': 32, 'lod': 'assets'}}
        with tempfile.TemporaryDirectory() as tmp:
            t = field(operations=ops, tile=16, lod={'distance': 12, 'tolerance': 0.5})
            w = self.scatter_world(tmp, scatter, standins={'distance': 48},
                                   lod={'ground': [{'distance': 30, 'grid': 16}]})
            spec = json.loads(w.world.read_text())
            spec['terrain'] = t
            w.world.write_text(json.dumps(spec))
            c = w.compile()
            self.assertEqual(set(c.report['standins']['cells']), {'c0_0', 'c1_0', 'c0_1', 'c1_1'})
            self.assertNotIn('no_standin', [x['code'] for x in c.report['warnings']])
            for cell in c.world.cells:
                self.assertIsNotNone(cell.standin)
                # the stand-in holds the scatter at 48 (blocks at level 1, ramps culled) and the
                # ground's far level without the skirts between its own tiles
                chunks = [p for p in cell.placements if p.tag == 0xFFFC]
                want = sum(P.mesh_info([m for d, m in p.lod.levels if d <= 48][-1])[1] for p in chunks)
                ground = sum(P.mesh_info(p.lod.levels[-1][1] if p.lod else p.mesh)[1]
                             for p in cell.placements if p.tag == 0xFFFE)
                self.assertLessEqual(P.mesh_info(cell.standin)[1], want + ground)
                self.assertGreaterEqual(P.mesh_info(cell.standin)[1], want)
            pack = P.decode(c.pack)
            self.assertTrue(all(pc.standin for pc in pack.cells.values()))
            # a second region: the stand-ins, untextured, are the same
            spec['regions']['r2'] = {}
            w.world.write_text(json.dumps(spec))
            self.assertEqual([x.standin for x in w.compile().world.cells], [x.standin for x in c.world.cells])

    def test_standin_caps_and_ground(self):
        from worldkit.world import standin_triangles
        scatter = {'s': {'assets': [{'asset': 'ledge_block'}, {'asset': 'ramp'}], 'area': {'rect': [0, 0, 64, 64]},
                         'spacing': 6, 'seed': 2, 'chunk': 32, 'lod': 'assets'}}

        def box(name, size):
            return {'format': 'mei-asset', 'version': 1, 'name': name,
                    'materials': {'m': {'color': '#806040', 'palette': True}},
                    'nodes': [{'id': 'b', 'op': 'box', 'size': size, 'material': 'm',
                               'transform': {'translate': [0, size[1] / 2, 0]}}]}
        with tempfile.TemporaryDirectory() as tmp:
            w = self.scatter_world(tmp, scatter, lod={'ground': [{'distance': 30, 'grid': 16}]})
            # a tower (10 high, 2 wide: size 20), a slab (1 high, 10 wide: 10) and the scatter's
            # blocks at level 1 (2 high, 3 wide: 6), on flat ground
            (w.dir/'assets'/'tower.asset.json').write_text(json.dumps(box('tower', [2, 10, 2])))
            (w.dir/'assets'/'slab.asset.json').write_text(json.dumps(box('slab', [10, 1, 10])))
            spec = json.loads(w.world.read_text())
            spec['cells'][0]['placements'] = [{'id': 'slab', 'asset': 'slab', 'position': [8, 8], 'collision': 'none'},
                                              {'id': 'tower', 'asset': 'tower', 'position': [24, 24], 'collision': 'none'}]

            def compile_with(**standins):
                spec['standins'] = dict(distance=48, **standins)
                w.world.write_text(json.dumps(spec))
                return w.compile()

            def tops(mesh):
                return {round(float(v[1]), 2) for v in P.mesh_vertices(mesh)}
            plain = compile_with()
            self.assertEqual(plain.report['standins']['cells']['c0_0']['left_out'], 0)
            self.assertLessEqual({1.0, 2.0, 10.0}, tops(plain.world.cells[0].standin))
            # the ground alone: a cap below it keeps the ground and warns
            bare = compile_with(triangles=1)
            over = [x for x in bare.report['warnings'] if x['code'] == 'standin_over_cap']
            self.assertEqual(sorted(x['cell'] for x in over), ['c0_0', 'c0_1', 'c1_0', 'c1_1'])
            ground = [cell.standin for cell in bare.world.cells]
            self.assertEqual(tops(ground[0]), {0.0})
            g0 = standin_triangles(ground[0])
            tower = next(p for p in plain.world.cells[0].placements if p.tag != 0xFFFE and p.tag != 0xFFFC
                         and P.mesh_info(p.mesh)[0] and max(float(v[1]) for v in P.mesh_vertices(p.mesh)) > 9)
            t = standin_triangles(tower.mesh)
            # room for the tower and less than the slab: the tower, then blocks where they fit
            c = compile_with(triangles=g0 + 2 * t - 1)
            rep = c.report['standins']['cells']['c0_0']
            standin = c.world.cells[0].standin
            self.assertLessEqual(standin_triangles(standin), g0 + 2 * t - 1)
            self.assertEqual(rep['triangles'], standin_triangles(standin))
            self.assertEqual(rep['cap'], g0 + 2 * t - 1)
            self.assertIn(10.0, tops(standin))
            self.assertNotIn(1.0, tops(standin), 'the slab does not fit')
            self.assertIn(2.0, tops(standin), 'blocks of the chunk go in one by one where they fit')
            self.assertGreater(rep['left_out'], 1)
            # the ground goes in first, unchanged
            gv, gf = P.mesh_info(ground[0])[:2]
            self.assertEqual(standin[16:16 + 16 * gv], ground[0][16:16 + 16 * gv])
            sv = P.mesh_info(standin)[0]
            self.assertEqual(standin[16 + 16 * sv:][:36 * gf], ground[0][16 + 16 * gv:][:36 * gf])
            # deterministic
            self.assertEqual([x.standin for x in compile_with(triangles=g0 + 2 * t - 1).world.cells],
                             [x.standin for x in c.world.cells])
            # a cell's own cap, and the ground on a coarser grid: one square over the flat cell
            c = compile_with(triangles=4000, ground=32, cells={'c1_1': {'triangles': 1}})
            rep = c.report['standins']['cells']
            self.assertEqual([x['cell'] for x in c.report['warnings'] if x['code'] == 'standin_over_cap'], ['c1_1'])
            self.assertEqual((rep['c1_1']['cap'], rep['c1_1']['triangles'], rep['c1_1']['ground']), (1, 2, 32))
            self.assertEqual(rep['c0_0']['left_out'], 0)
            self.assertEqual(rep['c0_0']['triangles'], plain.report['standins']['cells']['c0_0']['triangles'] - g0 + 2)
            # without a cap, the ground grid alone
            c = compile_with(ground=32)
            self.assertEqual(c.report['standins']['cells']['c1_1']['triangles'],
                             plain.report['standins']['cells']['c1_1']['triangles'] - standin_triangles(ground[3]) + 2)
            self.assertNotIn('cap', c.report['standins']['cells']['c1_1'])
            with self.assertRaises(WorldError) as cm:
                compile_with(cells={'nowhere': {'triangles': 10}})
            self.assertEqual(cm.exception.path, '/standins/cells/nowhere')


def rgb15_of(c):
    return (int(c[1:3], 16) >> 3) | (int(c[3:5], 16) >> 3) << 5 | (int(c[5:7], 16) >> 3) << 10


def tinted(c15, tint):
    """A 15-bit colour times a tint, as palettes.multiply() does it on the expanded colour."""
    ch = [((c15 >> s) & 31) for s in (0, 5, 10)]
    ex = [(v << 3) | (v >> 2) for v in ch]
    t = [int(tint[k:k + 2], 16) for k in (1, 3, 5)]
    return sum((round(e * tt / 255) >> 3) << s for e, tt, s in zip(ex, t, (0, 5, 10)))


def no_policies(ex):
    """The asset recipes without required Asset Checker runs (depth stays: cutouts need it)."""
    for a in ex.dir.glob('assets/*.asset.json'):
        spec = json.loads(a.read_text())
        if 'verification' in spec:
            spec['verification']['required'] = False
        a.write_text(json.dumps(spec))


@pillow
class TextureTests(unittest.TestCase):
    """Textures in worlds (WORLDKIT.md, "Textures per region"), on the night market example."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ex = Example(self.tmp.name, 'night_market')

    def tearDown(self):
        self.tmp.cleanup()

    def test_textures_are_packed_per_region(self):
        c = self.ex.compile()
        pack = P.decode(c.pack)
        self.assertEqual((pack.major, pack.minor), (1, 4))
        market, harbour = (c.report['regions'][r]['textures'] for r in ('market', 'harbour'))
        # every asset's tiles once per region, duplicates removed (the crate's planks are in both)
        self.assertEqual(sorted(market['by_asset']), ['crate', 'paving', 'shopfront', 'stall'])
        self.assertEqual(sorted(harbour['by_asset']), ['crate', 'quay', 'warehouse'])
        self.assertEqual(market['tiles'], 14)
        self.assertLess(market['tiles'], sum(a['tiles'] for a in market['by_asset'].values()) + 1)
        self.assertEqual([s['slot'] for s in market['slots']], [12, 13])      # "13-6": 4-bit 13, 8-bit 12
        self.assertEqual(market['palettes_8bit'], [31])     # palette.first8's default: the top of bank 1
        self.assertEqual([a['material'] for a in market['animations']], ['shopfront.neon', 'stall.lantern'])
        self.assertEqual(harbour['animations'], [])
        rm, rh = pack.regions
        self.assertEqual(sorted(t.slot for t in rm.textures), [12, 13])
        self.assertEqual([t.slot for t in rh.textures], [13])
        self.assertEqual(len(rm.animations), 2)
        self.assertEqual(rm.runs[0].first_colour, 31 * 256)
        # disjoint palettes: textures after each region's entries, every region's set coexisting
        pm, ph = (set(c.report['regions'][r]['palette']['palettes']) for r in ('market', 'harbour'))
        self.assertFalse(pm & ph)
        self.assertTrue(set(market['palettes_4bit']) <= pm and set(harbour['palettes_4bit']) <= ph)
        # every textured face of a region's meshes reads that region's slots and palettes
        for cell in pack.cells.values():
            reg = pack.regions[cell.region]
            slots = {t.slot for t in reg.textures} | {14}       # 14: the world's swatch
            pals = {k // 16 for k in range(reg.first_colour, reg.first_colour + len(reg.variants[0][1]))}
            for pl in cell.placements:
                nv, nf, vo, fo = P.mesh_info(pack.data[pl['mesh']:])
                for k in range(nf):
                    at = pl['mesh'] + fo + 36 * k
                    if pack.data[at] & 2:
                        flags, tex, pal = pack.data[at], pack.data[at + 2], pack.data[at + 3]
                        pal = meshlib.face_palette(flags, tex, pal)
                        self.assertIn(meshlib.face_slot(flags, tex), slots)
                        self.assertTrue(pal in pals if tex & 16 else 256 * pal == reg.runs[0].first_colour)

    def test_standins_with_several_regions_draw_far_colours(self):
        # a stand-in is drawn whichever region is loaded: its textured faces become palette-backed
        # faces (the world's swatch) in their tiles' far colours, entries of the cell's own region
        self.ex.edit(lambda w: w.__setitem__('standins', {'distance': 8}))
        for name in ('market', 'harbour'):
            self.ex.edit(lambda cell: cell.pop('standin'), f'cells/{name}.cell.json')
        c = self.ex.compile()
        pack = P.decode(c.pack)
        far = {r: [e for e in c.report['regions'][r]['palette']['entries']
                   if any(m.startswith('far.') for m in e['materials'])] for r in ('market', 'harbour')}
        self.assertTrue(far['market'] and far['harbour'])
        self.assertIn('far.stall.sign', [m for e in far['market'] for m in e['materials']])
        drawn = 0
        for cell in pack.cells.values():
            self.assertIsNotNone(cell.standin)
            reg = pack.regions[cell.region]
            entry_pals = {e['colour'] // 16 for e in c.report['regions'][reg.name]['palette']['entries']}
            colours = {e['colour'] for e in far[reg.name]}
            mesh = pack.data[cell.standin:]
            nv, nf, vo, fo = P.mesh_info(mesh)
            for k in range(nf):
                face = mesh[fo + 36 * k:fo + 36 * k + 36]
                if not face[0] & 2:
                    continue
                self.assertEqual(face[2], 14 | 16)                  # the swatch, 4-bit, no window
                self.assertIn(face[3], entry_pals)
                self.assertEqual(face[29], 0)                       # the swatch's row
                drawn += face[3] * 16 + face[28] in colours
        self.assertGreater(drawn, 0)
        sign = next(e for e in far['market'] if 'far.stall.sign' in e['materials'])
        self.assertEqual(sign['class'], 'emissive')
        # the placements themselves still draw their textures
        self.assertEqual(c.report['regions']['market']['textures']['tiles'], 14)

    def test_night_variants_per_colour_and_by_multiply(self):
        c = self.ex.compile()
        pack = P.decode(c.pack)
        rm = pack.regions[0]
        (_, day), (_, night) = rm.variants
        tint = '#4a5a88'
        first = rm.first_colour
        changed = [(d, n) for d, n in zip(day, night) if d != n]
        self.assertTrue(changed)
        lit = rgb15_of('#ffd27a')
        self.assertIn(lit, night, 'the shop window texel is lit at night (texels)')
        self.assertIn(rgb15_of('#ffd070'), night, 'the skyline\'s windows are lit at night (backdrop)')
        # every other surface texture colour is its day colour times the surface tint
        tex = c.report['regions']['market']['textures']
        for pal in tex['palettes_4bit']:
            for i in range(1, 16):
                d, n = day[pal * 16 + i - first], night[pal * 16 + i - first]
                if d and n not in (lit, d):
                    self.assertEqual(n, tinted(d, tint))
        # the 8-bit sign is emissive: its run keeps its colours; tinted when it is a surface
        run = rm.runs[0]
        self.assertEqual(run.variants[0], run.variants[1])
        self.ex.edit(lambda a: a['materials']['sign'].pop('class'), 'assets/stall.asset.json')
        run = P.decode(self.ex.compile().pack).regions[0].runs[0]
        self.assertEqual(run.variants[1], [0] + [tinted(x, tint) for x in run.variants[0][1:]])

    def test_variant_errors(self):
        def texels(sel, src):
            def f(w):
                w['regions']['market']['variants']['night']['texels'] = {sel: {src: '#ffffff'}}
            return f
        for edit, msg in ((texels('kiosk.glass', '#000000'), 'No textured material'),
                          (texels('shopfront.window', '#123456'), 'has no colour'),
                          (texels('stall.sign', '#fff7d6'), '8-bit')):
            ex = Example(self.tmp.name + f'/{len(msg)}', 'night_market')
            ex.edit(edit)
            with self.assertRaises(WorldError) as e:
                ex.compile()
            self.assertIn(msg, str(e.exception))

    def test_a_region_over_its_budget_fails_naming_its_assets(self):
        self.ex.edit(lambda w: w['regions']['market'].__setitem__('textures', {'budget': 2048}))
        with self.assertRaises(WorldError) as e:
            self.ex.compile()
        msg = str(e.exception)
        self.assertEqual(e.exception.path, '/regions/market/textures')
        self.assertIn("Region 'market' needs 3,360 bytes", msg)
        for name in ('stall', 'shopfront', 'crate', 'paving'):
            self.assertIn(name, msg)
        # within the budget but not in the slots given: one 4-bit slot cannot also hold the 8-bit sign
        self.ex.edit(lambda w: w['regions']['market'].__setitem__('textures', {'slots': '13'}))
        with self.assertRaises(WorldError) as e:
            self.ex.compile()
        self.assertIn('do not fit in its slots', str(e.exception))

    def test_second_megabyte(self):
        # VRAM at 2 MB (DECISIONS.md): a region in slots 16-31 and 4-bit palettes from 256, the
        # 8-bit sign from 8-bit palette 14 (bank 0) when the recipe says so
        self.ex.edit(lambda w: w['regions']['market'].__setitem__('textures', {'slots': '20,17-16'}))
        self.ex.edit(lambda w: w['regions']['market'].__setitem__('palettes', {'first': 300}))
        self.ex.edit(lambda w: w.__setitem__('palette', {'first8': 14}))
        c = self.ex.compile()
        pack = P.decode(c.pack)
        market = c.report['regions']['market']
        self.assertEqual(sorted(s['slot'] for s in market['textures']['slots']), [17, 20])
        self.assertEqual(market['textures']['palettes_8bit'], [14])
        self.assertTrue(all(p >= 300 for p in market['palette']['palettes']))
        rm = pack.regions[0]
        self.assertEqual(rm.first_colour, 300 * 16)
        self.assertEqual(sorted(t.slot for t in rm.textures), [17, 20])
        hi = 0
        for cell in pack.cells.values():
            if cell.region != 0:
                continue
            for pl in cell.placements:
                nv, nf, vo, fo = P.mesh_info(pack.data[pl['mesh']:])
                for k in range(nf):
                    at = pl['mesh'] + fo + 36 * k
                    flags, tex, pal = pack.data[at], pack.data[at + 2], pack.data[at + 3]
                    if not flags & 2:
                        continue
                    slot, palette = meshlib.face_slot(flags, tex), meshlib.face_palette(flags, tex, pal)
                    self.assertIn(slot, (14, 17, 20))
                    self.assertTrue(palette >= 300 if tex & 16 else palette == 14)
                    hi += bool(flags & 64)
        self.assertGreater(hi, 0)
        # a region that would run across palette 255 starts at 256 instead
        self.ex.edit(lambda w: w['regions']['market'].pop('palettes'))
        self.ex.edit(lambda w: w.__setitem__('palette', {'first': 252}))     # the market needs 5
        c = self.ex.compile()
        pm = c.report['regions']['market']['palette']['palettes']
        self.assertNotIn(255, pm + c.report['regions']['harbour']['palette']['palettes'])
        self.assertEqual(min(pm), 256)
        # the default slots reach into the second megabyte, after 13-0
        from worldkit.textures import DEFAULT_SLOTS
        self.assertEqual(DEFAULT_SLOTS, tuple(range(13, -1, -1)) + tuple(range(16, 32)))
        for bad in ('32', '15-16'):
            self.ex.edit(lambda w: w['regions']['market'].__setitem__('textures', {'slots': bad}))
            with self.assertRaises(WorldError):
                self.ex.compile()

    def test_slots_and_swatch(self):
        # the swatch's slot may hold region textures: the swatch row is kept and copied with them
        self.ex.edit(lambda w: w.__setitem__('textures', {'slots': '14-12'}))
        c = self.ex.compile()
        rm = P.decode(c.pack).regions[0]
        s14 = [t for t in rm.textures if t.slot == 14][0]
        self.assertEqual(s14.data[:8], c.swatch)
        for bad in ('15', '13-14,13'):
            self.ex.edit(lambda w: w.__setitem__('textures', {'slots': bad}))
            with self.assertRaises(WorldError):
                self.ex.compile()

    def test_stand_ins_and_merged_meshes(self):
        self.ex.edit(lambda c: c.__setitem__('standin', 'crate'), 'cells/market.cell.json')
        with self.assertRaises(WorldError) as e:
            self.ex.compile()
        self.assertIn('cannot use a region', str(e.exception))
        self.ex.edit(lambda c: c.__setitem__('standin', 'block_far'), 'cells/market.cell.json')
        self.ex.edit(lambda c: c['placements'][5].__setitem__('merge', True), 'cells/market.cell.json')
        with self.assertRaises(WorldError) as e:
            self.ex.compile()
        self.assertIn('texture window', str(e.exception))

    def test_backdrops(self):
        c = self.ex.compile()
        rm, rh = P.decode(c.pack).regions
        self.assertEqual(len(rm.sky.elevations), 5)
        self.assertEqual((rm.sky.height, rm.sky.horizon, rm.sky.top), (40, 40, 0))
        self.assertEqual(rm.sky.colours[0][0], 0x98928a)              # '#8a9298' as 0xBBGGRR
        self.assertEqual([cp.address for cp in rm.backdrop], [0x460000, 0x452000])
        self.assertEqual(len(rm.backdrop[1].data), 128 * 32 * 2)       # a 128 x 32 map
        self.assertEqual(rm.sky.mode & 0xFF00, (c.report['regions']['market']['palette']['palettes'][-1]) << 8)
        bd = c.report['regions']['harbour']['backdrop']['silhouette']
        self.assertEqual((bd['width'], bd['repeat']), (512, 3))
        # a variant without sky colours: the first's, times its surface tint
        self.ex.edit(lambda w: w['regions']['harbour']['backdrop']['sky'].pop('night'))
        rh2 = P.decode(self.ex.compile().pack).regions[1]
        day = rh2.sky.colours[0]
        word = lambda c15: sum(((((c15 >> s) & 31) << 3 | ((c15 >> s) & 31) >> 2)) << (8 * k) for k, s in enumerate((0, 5, 10)))
        self.assertEqual(len(rh2.sky.colours[1]), len(day))
        self.assertNotEqual(rh2.sky.colours[1], day)
        self.ex.edit(lambda w: w['regions']['harbour']['backdrop']['sky'].__setitem__('dusk', ['#000000'] * 4))
        with self.assertRaises(WorldError):
            self.ex.compile()

    def test_untextured_worlds_are_unchanged(self):
        for name in ('test_room', 'two_districts', 'shrine_grounds'):
            c = compile_source(str(EXAMPLES/name/f'{name}.world.json'))[1]
            p = P.decode(c.pack)
            self.assertEqual((p.minor, struct.unpack_from('<H', c.pack, 14)[0]), (3, 80), name)
            self.assertNotIn('wp_region_enter', c.akr)
            self.assertNotIn('wpbackdrop', c.akr)

    def test_silhouette_palette_of_a_bank_1_region_is_in_bank_0(self):
        # a plane reads palette bank 0 only: the harbour, placed from 256, keeps its silhouette's
        # palette in bank 0 as a run of its own, loaded with each variant
        self.ex.edit(lambda w: w['regions']['harbour'].__setitem__('palettes', {'first': 256}))
        c = self.ex.compile()
        rm, rh = P.decode(c.pack).regions
        self.assertGreaterEqual(rh.first_colour, 256 * 16)
        pal = (rh.sky.mode >> 8) & 255
        market = c.report['regions']['market']['palette']['palettes']
        self.assertNotIn(pal, market)
        self.assertGreater(pal, max(market))
        run = [r for r in rh.runs if r.first_colour == pal * 16]
        self.assertEqual(len(run), 1)
        self.assertEqual(len(run[0].variants), 2)                  # day and night
        self.assertTrue(any(run[0].variants[0][1:]))

    def far_world(self, **extra):
        """Night market with the kit's stand-ins from 8 units (every cell draws one)."""
        self.ex.edit(lambda w: w.__setitem__('standins', {'distance': 8, **extra}))
        for name in ('market', 'harbour'):
            self.ex.edit(lambda cell: cell.pop('standin', None), f'cells/{name}.cell.json')

    def test_standin_texture_set_keeps_cutout_cards(self):
        # the stall's lattice (a cutout) is in the stand-ins' own set, at one place in every
        # region's set; stand-ins keep it textured instead of drawing it in a far colour
        before = self.ex.compile()
        self.far_world(textures={'slots': '6'})
        c = self.ex.compile()
        pack = P.decode(c.pack)
        common = c.report['standins']['textures']
        self.assertEqual(common['slots_given'], [6])
        self.assertEqual({m.split('.')[0] for m in common['by_material']}, {'stall'})
        self.assertGreater(common['vram_bytes'], 0)
        images = {}
        for reg in pack.regions:
            slots = {t.slot: t for t in reg.textures}
            self.assertIn(6, slots, reg.name)             # every region's set holds the common slot
            images[reg.name] = slots[6].data
            self.assertNotIn(6, c.report['regions'][reg.name]['textures']['slots_given'])
        self.assertEqual(images['market'], images['harbour'])
        cards = 0
        for cell in pack.cells.values():
            mesh = pack.data[cell.standin:]
            nv, nf, vo, fo = P.mesh_info(mesh)
            for k in range(nf):
                face = mesh[fo + 36 * k:fo + 36 * k + 36]
                if face[0] & 2 and face[2] & 15 == 6:
                    cards += 1
                    self.assertTrue(face[2] & 16)
        self.assertGreater(cards, 0)
        # the region's own set no longer holds the lattice; the placements are unchanged
        self.assertLess(c.report['regions']['market']['textures']['vram_bytes'],
                        before.report['regions']['market']['textures']['vram_bytes'])

    def test_haze(self):
        from worldkit.haze import Haze, mix, sky_at
        self.assertEqual(sky_at([-8, 0, 6], ['#000000', '#646464', '#c8c8c8'], 3), '#969696')
        self.assertEqual(mix('#000000', '#ffffff', 0.5), '#808080')
        self.far_world(textures={'slots': '6'})
        plain = self.ex.compile()
        self.ex.edit(lambda w: w.__setitem__('haze', {'end': 40, 'amount': 0.5, 'standins': 0.4}))
        c = self.ex.compile()
        hz = c.report['haze']
        # the haze colour per region and variant: the backdrop's sky at 2 degrees
        self.assertEqual(hz['colors']['market']['day'], sky_at([-8, 0, 6, 30, 70],
                         ['#8a9298', '#e8dcc8', '#b8d0e8', '#6898d0', '#3060a8'], 2))
        self.assertEqual(set(hz['colors']['harbour']), {'day', 'night'})
        # stand-ins' far colours are entries of their own, hazed in each variant toward its colour
        pack = P.decode(c.pack)
        for reg in pack.regions:
            entries = c.report['regions'][reg.name]['palette']['entries']
            far = [e for e in entries if any(m.startswith('far.far') for m in e['materials'])]
            self.assertTrue(far, reg.name)
            (vd, day), (vn, night) = reg.variants
            for e in far:
                want = mix(e['color'], hz['colors'][reg.name]['day'],
                           0.4 * (0.5 if e['class'] == 'emissive' else 1))
                self.assertEqual(day[e['colour'] - reg.first_colour], rgb15_of(want))
        # placements' level 0 is never hazed (its colours; the palettes move: the far colours are
        # entries of their own now)
        plain_pack = P.decode(plain.pack)

        def mesh_bytes(data, at):
            nv, nf, vo, fo = P.mesh_info(data[at:])
            return [data[at + fo + 36 * k + 12:at + fo + 36 * k + 28] for k in range(nf)]
        for key in pack.cells:
            for pl, ppl in zip(pack.cells[key].placements, plain_pack.cells[key].placements):
                self.assertEqual(mesh_bytes(pack.data, pl['mesh']), mesh_bytes(plain_pack.data, ppl['mesh']))
        # the tint of a level: an untextured face mixed exactly; a textured one's tint toward
        # the colour its base needs, clamped at 255
        h = Haze({'end': 100, 'amount': 1.0}, 0)
        h.colours['r'] = {'day': '#c8c8c8'}
        self.assertEqual(h.at(50), 0.5)
        mesh = struct.pack('<HHIII', 3, 2, 16, 64, 0) + bytes(48)
        flat = struct.pack('<BBBB4H4I4H', 0, 0, 0, 0, 0, 1, 2, 0, 0x000000, 0, 0, 0, 0, 0, 0, 0)
        textured = struct.pack('<BBBB4H4I4H', 2, 0, 16 | 3, 7, 0, 1, 2, 0, *[0x808080] * 4, 0, 0, 0, 0)
        out = h.tint(mesh + flat + textured, 0.5, lambda flags, tex, pal, uvs, hw: ((100, 100, 100), 'surface'), 'r')
        f0 = struct.unpack_from('<4I', out, 64 + 12)
        f1 = struct.unpack_from('<4I', out, 64 + 36 + 12)
        self.assertEqual(f0[0], 0x646464)                   # black halfway to #c8c8c8
        self.assertEqual(f1[0], 0xC0C0C0)                   # 128 * 0.5 + 128 * 0.5 * 200 / 100 = 192
        self.assertEqual(h.tint(mesh + flat + textured, 0.0, None, 'r'), mesh + flat + textured)


@tools_built
class ConsoleTests(unittest.TestCase):
    def run_cart(self, out, cart, frames=2, dump=None):
        shutil.copy(ROOT/'tests'/'worldkit'/cart, out/cart)
        env = dict(os.environ, MEI_STDLIB=str(ROOT/'stdlib'))
        r = subprocess.run([str(COMPILER), str(out/cart), '-o', str(out/'cart.mei')], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        args = [str(RUNNER), str(out/'cart.mei'), '--frames', str(frames)] + (['--dump', str(dump)] if dump else [])
        r = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = {}
        for line in r.stdout.splitlines():
            words = line.split()
            if words and words[0] not in lines: lines[words[0]] = words[1:]
        return lines

    def test_test_room_draws_and_collides_on_the_console(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            out = Path(tmp)/'out'
            report = build_without_asset_checker(ex, out)
            got = self.run_cart(out, 'room.akr', dump=out/'room.ppm')
            fx = lambda v: str(P.fx(v))
            self.assertEqual(got['ledge'], ['1', fx(2), '1', '2'])
            self.assertEqual(got['slope'], ['1', fx(1), '2', '1'])
            self.assertEqual(got['ground'], ['1', '0', '1', '0'])
            self.assertEqual(got['ceiling'], ['1', fx(3), '4', '4'])
            self.assertEqual(got['ramp_underside'][0], '0')
            self.assertEqual(got['wall'][1:3], [fx(41.45), '1'])
            closed, opened = got['gate_closed'], got['gate_open']
            self.assertNotEqual(closed[1], '0', 'the closed gate pushes')
            self.assertEqual(opened, [fx(22.1), '0', '0', '0'], 'opening the gate switches its collision off')
            self.assertEqual(got['coin'], ['0', '0', '1', '1'])
            self.assertEqual(got['trigger'], ['1', '1', '0', '1'])        # target: entity 0; time_window: day
            self.assertEqual(got['trigger_more'], [fx(2), '1', '0', '1'])
            self.assertEqual(got['event'], ['open_gate'])
            self.assertEqual(got['names'], ['lab', 'night', 'gate_open'])
            self.assertEqual(got['names_out'], ['1', '0', '0', '0'])
            self.assertEqual(got['probe'], [fx(0.3), fx(1.6), fx(0.32), fx(45)])
            lab = report['regions']['lab']
            day, night = lab['variants']['day'], lab['variants']['night']
            rgb15 = lambda c: (int(c[1:3], 16) >> 3) | (int(c[3:5], 16) >> 3) << 5 | (int(c[5:7], 16) >> 3) << 10
            surface, emissive = str(lab['palette']['classes']['surface']['first_colour']), str(lab['palette']['classes']['emissive']['first_colour'])
            self.assertEqual(got['palette_day'], [str(rgb15(day[surface])), str(rgb15(day[emissive])), '0', '0'])
            self.assertEqual(got['palette_night'], [str(rgb15(night[surface])), str(rgb15(day[emissive])), '0', '0'])
            near, looked, drawn = map(int, got['draw'][:3])
            self.assertEqual(near, 1)
            self.assertGreaterEqual(drawn, 4)
            # The floor is drawn through its palette entry: the floor colour appears on screen.
            data = (out/'room.ppm').read_bytes().split(b'\n', 3)[3]
            pixels = {data[k:k + 3] for k in range(0, len(data), 3)}
            self.assertGreater(len(pixels), 6)
            self.assertNotEqual(data[(200 * 320 + 160) * 3:(200 * 320 + 160) * 3 + 3], bytes([40, 60, 120]))

    def test_fog_per_variant_on_the_console(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            def night_fog(w):
                w['regions']['lab']['variants']['night']['fog'] = {'color': '#102040', 'near': 8, 'far': 40}
            ex.edit(night_fog)
            out = Path(tmp)/'out'
            build_without_asset_checker(ex, out)
            akr = (out/'test_room.akr').read_text()
            self.assertIn('fn world_test_room_fog(region: s32, variant: s32) {', akr)
            got = self.run_cart(out, 'room_fog.akr', frames=1)
            self.assertEqual(got['day'], ['0', '0'])              # no fog declared: off
            # bit 24 on, 0x402010; near 8 units = 128 sixteenths, scale 65,536 / 32 = 2,048
            self.assertEqual(got['night'], [str(1 << 24 | 0x402010), str(2048 << 16 | 128)])
        # without fog the generated source has no fog function; far must pass near by a unit
        with tempfile.TemporaryDirectory() as tmp:
            self.assertNotIn('_fog(', Example(tmp + '/a').compile().akr)
            bad = Example(tmp + '/b')
            bad.edit(lambda w: w['regions']['lab']['variants']['day'].__setitem__('fog', {'color': '#ffffff', 'near': 10, 'far': 10.5}))
            with self.assertRaises(WorldError) as e:
                bad.compile()
            self.assertEqual(e.exception.path, '/regions/lab/variants/day/fog')

    def test_paths_on_the_console(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            ex.edit(add_paths)
            out = Path(tmp)/'out'
            build_without_asset_checker(ex, out)
            got = self.run_cart(out, 'room_paths.akr', frames=1)
            fx = lambda v: str(P.fx(v))
            self.assertEqual(got['paths'], ['3', '3', '3', '1'])
            self.assertEqual(got['by_name'], ['1', '1', '4', '0'])
            self.assertEqual(got['grind'], ['1', '1', fx(9), fx(0.25)])
            self.assertEqual(got['no_grind'], ['0', '0', '0', '0'])
            self.assertEqual(got['loop'], [fx(15), fx(10), '0', fx(40)])

    def test_preview_renders_each_region_and_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp, 'two_districts')
            out = Path(tmp)/'out'
            code, report = cli('preview', ex.world, '-o', out, '--compiler', COMPILER, '--runner', RUNNER, '--probe', PROBE,
                               '--world-checker', 'skip')
            self.assertEqual(code, 0, report)
            views = report['preview']['views']
            self.assertEqual([(v['cell'], v['variant']) for v in views],
                             [('downtown_a', 'day'), ('downtown_a', 'night'), ('shrine_gate', 'day'), ('shrine_gate', 'night')])
            self.assertTrue(all(v['stats']['tris_dropped'] == 0 and v['stats']['tris'] > 0 for v in views))
            self.assertTrue((out/'preview'/'contact.png').is_file())
            day, night = ((out/v['image']).read_bytes() for v in views[:2])
            self.assertNotEqual(day, night, 'the night variant recolours the scene')
            self.assertEqual(sorted(p.name for p in out.iterdir() if p.name.startswith('.')), [])

    def test_terrain_example_collides_and_draws_on_the_console(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'shrine_grounds'
            shutil.copytree(EXAMPLES/'shrine_grounds', folder, ignore=shutil.ignore_patterns('*.ids.json'))
            out = Path(tmp)/'out'
            for a in folder.glob('assets/*.asset.json'):     # no NumPy needed: drop the policies
                spec = json.loads(a.read_text())
                spec.pop('verification', None)
                a.write_text(json.dumps(spec))
            build(str(folder/'shrine_grounds.world.json'), out, COMPILER, RUNNER, PROBE, checker='skip')
            got = self.run_cart(out, 'shrine.akr')
            fx = lambda v: ['1', str(P.fx(v))]
            self.assertEqual(got['ground'], fx(0))
            self.assertEqual(got['tier1'], fx(3))
            self.assertEqual(got['tier2'], fx(6))
            self.assertEqual(got['summit'], fx(12))
            self.assertEqual(got['pond'], fx(-1.4))
            self.assertEqual(got['sando'], fx(0))
            self.assertEqual(got['tread'], fx(6))
            self.assertEqual(got['back_path'][0], '1')
            self.assertLessEqual(abs(int(got['back_path'][1]) - P.fx(3)), 2)      # on its slope, rounded
            near, drawn, ground, coarse = map(int, got['draw'])
            self.assertEqual(near, 4)
            self.assertGreater(drawn, 16)                    # 16 tiles, 2 sweeps' pieces and the props
            self.assertGreater(coarse, 0, 'far tiles are drawn at their coarse level')

    @pillow
    def test_textures_and_backdrops_on_the_console(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp, 'night_market')
            no_policies(ex)
            out = Path(tmp)/'out'
            ex.build(out)
            shutil.copy(ROOT/'tests'/'worldkit'/'market.akr', out/'market.akr')
            env = dict(os.environ, MEI_STDLIB=str(ROOT/'stdlib'))
            r = subprocess.run([str(COMPILER), str(out/'market.akr'), '-o', str(out/'cart.mei')], capture_output=True,
                               text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            (out/'shots').mkdir()
            r = subprocess.run([str(RUNNER), str(out/'cart.mei'), '--frames', '48', '--dump-from', '5', '--dump-every',
                                '6', str(out/'shots'/'v'), '--gpu-stats', str(out/'gpu.csv')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            views = {}
            for line in r.stdout.splitlines():
                w = line.split()
                if w and w[0] == 'view':
                    views[int(w[1])] = dict(zip(w[2::2], map(int, w[3::2])))
                elif w and w[0] == 'enter':
                    enter = int(w[1])
            self.assertEqual(sorted(views), list(range(8)))
            if os.environ.get('WORLDKIT_VERBOSE'):
                print('\nenter', enter, views)
            self.assertGreater(enter, 5000)
            self.assertGreater(views[1]['anim_copy_max'], views[1]['anim'], 'a frame change copies rows')
            self.assertLess(max(v['anim'] for v in views.values()), 1000)
            self.assertLess(max(v['backdrop'] for v in views.values()), 10000)
            self.assertGreater(views[5]['enter'], 0, 'the harbour is entered')
            pics = [(out/'shots'/f'v_{5 + 6 * k:05}.ppm').read_bytes().split(b'\n', 3)[3] for k in range(8)]
            self.assertNotEqual(pics[0], pics[1], 'night recolours the textures and the sky')
            self.assertNotEqual(pics[1], pics[4], 'turning scrolls the skyline')
            # the sky: the top line is the gradient's top colours, from the backdrop (no cls)
            top = lambda pic: tuple(pic[0:3])
            self.assertEqual(top(pics[0]), top(pics[0][3 * 300:3 * 301]))
            self.assertGreater(sum(top(pics[0])), sum(top(pics[1])) + 150, 'the day sky is brighter than the night')
            # the GPU clears only when wp_backdrop_show() (planes_on()) runs, once a view: the plane
            # chip erases every other frame
            rows = (out/'gpu.csv').read_text().splitlines()
            head = rows[0].split(',')
            self.assertLessEqual(sum(int(r.split(',')[head.index('clears')]) for r in rows[1:]), 8)

    def test_cliffs_water_and_scatter_on_the_console(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'forest_mountain'
            shutil.copytree(EXAMPLES/'forest_mountain', folder, ignore=shutil.ignore_patterns('*.ids.json', 'screenshots'))
            out = Path(tmp)/'out'
            for a in folder.glob('assets/*.asset.json'):     # no NumPy needed: drop the policies
                spec = json.loads(a.read_text())
                spec.pop('verification', None)
                a.write_text(json.dumps(spec))
            report = build(str(folder/'forest_mountain.world.json'), out, COMPILER, RUNNER, PROBE, checker='skip')
            self.assertTrue((out/'forest_mountain.water.bin').is_file())
            got = self.run_cart(out, 'forest.akr')
            fx = lambda v: str(P.fx(v))
            self.assertEqual(got['plateau'][0], '1')
            self.assertGreater(int(got['plateau'][1]), P.fx(40))            # the cliff's top sheet
            self.assertEqual(got['below_cliff'][0], '1')
            self.assertLess(int(got['below_cliff'][1]), P.fx(20))
            self.assertEqual(got['trail'], ['1', '0'])                       # the draped trail at the gate
            self.assertEqual(got['pond'], ['1', fx(1.4), '3'])               # level, surface byte (tag water: 3)
            self.assertEqual(got['pool'], ['1', fx(12.2), '3'])
            self.assertEqual(got['dry'][0], '0')
            near, drawn, coarse, culled = map(int, got['draw'])
            self.assertGreater(culled, 0, 'far forest chunks are culled')
            self.assertGreater(report['scatter']['forest']['placed'], 200)

    def test_multi_region_world_loads_and_draws_stand_ins(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp, 'two_districts')
            out = Path(tmp)/'out'
            report = ex.build(out)
            got = self.run_cart(out, 'districts.akr')
            down, shrine = report['regions']['downtown']['palette'], report['regions']['shrine']['palette']
            rgb15 = lambda c: (int(c[1:3], 16) >> 3) | (int(c[3:5], 16) >> 3) << 5 | (int(c[5:7], 16) >> 3) << 10
            self.assertEqual(got['palettes'], [str(rgb15(down['entries'][0]['color'])), str(rgb15(shrine['entries'][0]['color']))])
            near, looked, drawn, standins = map(int, got['east'])
            self.assertGreaterEqual(standins, 1, 'the far shrine cell is drawn as its stand-in')
            self.assertGreaterEqual(drawn, 3)
            self.assertEqual(got['festival'][:2], ['0', '1'])
            self.assertEqual(got['floor'], ['1', '0', '1'])


SCENE_PROBE = Path(os.environ.get('SCENE_PROBE', COMPILER.parent/'mei-scene-probe')).resolve()
checker_tools = unittest.skipUnless(COMPILER.exists() and SCENE_PROBE.exists() and importlib.util.find_spec('numpy'),
                                    'the World Checker needs NumPy, meic and mei-scene-probe')


class AssetDirTests(unittest.TestCase):
    """asset_dirs: up to 256 entries, DIR/* for every subfolder, clashes naming both files."""

    def test_a_folder_of_asset_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            before = ex.compile().pack
            for name in ('ramp', 'gate'):
                (ex.dir/'more'/name).mkdir(parents=True)
                shutil.move(str(ex.dir/'assets'/f'{name}.asset.json'), str(ex.dir/'more'/name/f'{name}.asset.json'))
            (ex.dir/'more'/'.hidden').mkdir()
            ex.edit(lambda w: w.update(asset_dirs=['more/*']))
            self.assertEqual(ex.compile().pack, before)
            ex.edit(lambda w: w.update(asset_dirs=['more/*', 'more/ramp']))     # named twice: searched once
            self.assertEqual(ex.compile().pack, before)
            (ex.dir/'empty').mkdir()
            ex.edit(lambda w: w.update(asset_dirs=['more/*', 'empty/*']))
            with self.assertRaises(WorldError) as cm:
                ex.compile()
            self.assertEqual(cm.exception.path, '/asset_dirs/1')
            # a name in two folders: the message names both files
            ex.edit(lambda w: w.update(asset_dirs=['more/*']))
            shutil.copy(ex.dir/'more'/'ramp'/'ramp.asset.json', ex.dir/'assets'/'ramp.asset.json')
            with self.assertRaisesRegex(WorldError, 'more than one asset directory') as cm:
                ex.compile()
            self.assertIn(os.path.join('assets', 'ramp.asset.json') + ' and ' + os.path.join('more', 'ramp', 'ramp.asset.json'),
                          str(cm.exception))

    def test_the_schema_takes_256(self):
        from worldkit.schema import validate_world
        with tempfile.TemporaryDirectory() as tmp:
            world = Example(tmp).read()
        validate_world(dict(world, asset_dirs=[f'd{k}' for k in range(256)]))
        with self.assertRaises(WorldError):
            validate_world(dict(world, asset_dirs=[f'd{k}' for k in range(257)]))

    def test_make_depends_on_the_subfolders(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            (ex.dir/'more'/'ramp').mkdir(parents=True)
            shutil.move(str(ex.dir/'assets'/'ramp.asset.json'), str(ex.dir/'more'/'ramp'/'ramp.asset.json'))
            ex.edit(lambda w: w.update(asset_dirs=['more/*']))
            sys.path.insert(0, str(ROOT/'tools'))
            import world_cart
            deps = world_cart.depfile(str(ex.world), Path(tmp)/'out')
            self.assertIn('ramp.asset.json', deps)
            self.assertIn(str(ex.dir/'more').replace(' ', '\\ ') + ' ', deps.replace('\n', ' ') + ' ')


class QuickToolTests(unittest.TestCase):
    """mei_world.py check, floors and textures (worldkit/quick.py)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name)/'cache'

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_compiled_world_is_kept_by_its_inputs(self):
        from worldkit.quick import load_world
        ex = Example(self.tmp.name)
        first = load_world(str(ex.world), None, self.cache)
        self.assertFalse(first.cached)
        self.assertEqual(first.pack, ex.compile().pack)
        again = load_world(str(ex.world), None, self.cache)
        self.assertTrue(again.cached)
        self.assertEqual((again.pack, again.meta['cells']), (first.pack, first.meta['cells']))
        ex.edit(lambda w: w['cells'][0]['placements'][1].update(position=[36, 0, 27]))
        moved = load_world(str(ex.world), None, self.cache)
        self.assertFalse(moved.cached)
        self.assertNotEqual(moved.pack, first.pack)
        ex.edit(lambda a: a['nodes'][0].update(size=[2.5, 1, 4]) if a['nodes'][0].get('size') else None,
                'assets/ramp.asset.json')
        self.assertFalse(load_world(str(ex.world), None, self.cache).cached)      # an asset recipe changed
        (ex.dir/'assets'/'new.asset.json').write_text((ex.dir/'assets'/'ramp.asset.json').read_text())
        self.assertFalse(load_world(str(ex.world), None, self.cache).cached)      # an asset directory's listing
        self.assertTrue(load_world(str(ex.world), None, self.cache).cached)

    def test_floors_are_the_packs(self):
        from worldkit.quick import load_world, floors, floors_text
        ex = Example(self.tmp.name)
        world = load_world(str(ex.world), None, self.cache)
        # off the faces' edges (where the reader's rows and the kit's float test may differ)
        r = floors(world, (20.5, 20.5, 43.5, 43.5), 1.0, ['gate_closed', 'gate_open'])     # the kit's floor: every layer
        points = []
        for b, z in enumerate(r['z']):
            for a, x in enumerate(r['x']):
                points += [x, z]
        kit = mei_world.floors(str(ex.world), points)['floors']
        got = [h for row in r['heights'] for h in row]
        self.assertEqual(len(kit), len(got))
        for k, (want, h) in enumerate(zip(kit, got)):
            if want['y'] is None or h is None:
                self.assertEqual(want['y'], h, kit[k])
            else:
                self.assertAlmostEqual(want['y'], h, places=3)
        names = {g['what'] for g in r['sources']}
        self.assertIn('room/slope', names)
        self.assertEqual(floors(world, (20, 20, 21, 21), 1.0)['layers'], ['gate_closed'])     # those on at the start
        self.assertIn('heights', floors_text(r))
        under = floors(world, (32, 30, 32, 30), 1.0, below=2.0)
        self.assertLessEqual(under['heights'][0][0], 2.0)

    def test_textures_are_the_regions(self):
        from worldkit.quick import load_world, textures, textures_text
        from worldkit.assets import Library, asset_directories
        ex = Example(self.tmp.name, 'night_market')
        report = ex.compile().report
        world = load_world(str(ex.world), None, self.cache)
        r = textures(world)
        for name in ('market', 'harbour'):
            want = report['regions'][name]['textures']
            self.assertEqual(r['regions'][name]['allocated'], want['vram_bytes_allocated'])
            self.assertEqual(r['regions'][name]['tiles'], want['tiles'])
            self.assertEqual({a['asset']: a['allocated'] for a in r['regions'][name]['assets']},
                             {n: a['vram_bytes'] for n, a in want['by_asset'].items()})
        crate = next(a for a in r['regions']['market']['assets'] if a['asset'] == 'crate')
        self.assertEqual(crate['allocated'], crate['own'] + crate['shared'])
        one = textures(world, cells=[(1, 0)])
        self.assertEqual(list(one['regions']), ['harbour'])
        self.assertEqual(one['regions']['harbour']['selected']['assets'], ['crate', 'quay', 'warehouse'])
        from worldkit.world import load
        s = load(str(ex.world))
        dirs = asset_directories(s.world, s.base)
        added = textures(world, 'harbour', add={'harbour': ['stall']}, library=Library(dirs[0], s.base, dirs[1:]))
        self.assertGreater(added['regions']['harbour']['allocated'], r['regions']['harbour']['allocated'])
        self.assertIn('market:', textures_text(r))

    @checker_tools
    def test_check_one_cell_and_a_camera(self):
        from worldkit.quick import load_world, check, check_text, parse_cells, parse_cameras
        from worldkit import verify as V
        ex = Example(self.tmp.name, 'two_districts')
        world = load_world(str(ex.world), None, self.cache)
        tools = {'compiler': COMPILER, 'probe': SCENE_PROBE}
        cells = parse_cells(['1,0'], world)
        cams = parse_cameras(['street=40,1.5,8@90,0'], None)
        r = check(world, cells, cams, tools, 40)
        self.assertEqual(r['focus']['cells'], [[1, 0]])
        named = [v for v in r['views'] if 'name' in v]
        self.assertTrue(named and all(v['name'] == 'street' and v['kind'] == 'vantage' for v in named))
        self.assertTrue(all(tuple(v['camera']['cell']) == (1, 0) for v in r['views'] if 'name' not in v))
        self.assertTrue(all('heaviest' in v for v in r['views']))
        self.assertEqual([c['cell'] for c in r['static']['cells']], [[1, 0]])
        # the cell's static findings are the full check's there
        full = V.verify(world.pack, {'sampling': {'max_views': 1}}, None, None, tools)
        mine = lambda f: (f['code'], f['floor_tag'], f['beyond_tag'], tuple(f['at']))
        there = [f for f in full['static']['collision']['findings'] if (int(f['at'][0]) // 32, int(f['at'][2]) // 32) == (1, 0)]
        self.assertEqual(sorted(map(mine, r['static']['collision']['findings'])), sorted(map(mine, there)))
        self.assertIn('street', check_text(r, world, cells, cams))
        with self.assertRaises(WorldError):
            parse_cells(['9,9'], world)
        self.assertEqual(parse_cells([world.meta['cells'][0]['id']], world), [tuple(world.meta['cells'][0]['at'])])

    def test_cli_text_and_json(self):
        ex = Example(self.tmp.name, 'night_market')
        base = [*CLI, 'textures', str(ex.world), '--cache', str(self.cache)]
        r = subprocess.run(base, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(r.stdout.startswith('night_market: texture VRAM'))
        code, out = cli('textures', ex.world, '--cache', self.cache, '--json', '--region', 'market')
        self.assertEqual((code, list(out['regions'])), (0, ['market']))
        self.assertTrue(out['compiled']['compiled'] == 'cached')
        r = subprocess.run([*CLI, 'floors', str(ex.world), '--cache', str(self.cache), '--area', '1,2'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stdout.startswith('error at /arguments/area'), r.stdout)
        code, out = cli('check', ex.world, '--cache', self.cache, '--json')
        self.assertEqual((code, out['errors'][0]['path']), (1, '/arguments'))


if __name__ == '__main__':
    unittest.main()
