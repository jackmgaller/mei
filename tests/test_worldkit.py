"""World Kit regressions (tools/mei_world.py, docs/WORLDKIT.md). Run:
python3 -m unittest discover -s tests -p test_worldkit.py

The CLI, validation, ID, palette, collision and determinism tests need only Python. The console
tests build the example worlds, compile carts that load them with stdlib/worldpack.akr and run
them headless (MEIC and RUN select the builds; skipped when they have not been built). The
Asset Checker test also needs NumPy and mei-asset-probe (PROBE). Example worlds are copied to a
temporary directory first, so their committed ID lock files are never touched.
"""
import importlib.util
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
from worldkit.build import build, compile_source  # noqa: E402
from worldkit.schema import WorldError  # noqa: E402
import mei_world  # noqa: E402

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
        folder = {'test_room': 'test_room', 'two_districts': 'two_districts'}[name]
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

    def build(self, out, **kw):
        return build(str(self.world), out, COMPILER, RUNNER, PROBE, **kw)


def build_without_checker(example, out, **kw):
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
        self.assertIn('terrain', schema['x-unknown'])
        code, schema = cli('schema', '--game', EXAMPLES/'test_room'/'garden.game.json')
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
        self.check(lambda w: w.update(terrain={}), '/terrain', 'reserved')
        self.check(lambda w: w['regions']['lab'].update(textures=[]), '/regions/lab/textures', 'reserved')
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
            build_without_checker(ex, Path(tmp)/'out')
            lock = json.loads(ex.lock.read_text())
            self.assertEqual(lock['bits'], {'coin_ledge': 0, 'gate_switch': 1})
            # A new coin placed first gets the next bit; existing bits do not move.
            ex.edit(lambda w: w['cells'][0]['entities'].insert(0, {'id': 'coin_new', 'type': 'coin', 'position': [40, 1, 40]}))
            build_without_checker(ex, Path(tmp)/'out')
            lock = json.loads(ex.lock.read_text())
            self.assertEqual(lock['bits'], {'coin_ledge': 0, 'gate_switch': 1, 'coin_new': 2})
            # Rename with "was": the bit follows; the old name is recorded.
            def rename(w):
                e = w['cells'][0]['entities'][1]
                e['was'], e['id'] = e['id'], 'coin_on_ledge'
                w['cells'][0]['entities'][2]['params']['target'] = 'coin_on_ledge'
            ex.edit(rename)
            report = build_without_checker(ex, Path(tmp)/'out')
            lock = json.loads(ex.lock.read_text())
            self.assertEqual(lock['bits']['coin_on_ledge'], 0)
            self.assertEqual(lock['renamed'], {'coin_ledge': 'coin_on_ledge'})
            self.assertEqual(report['ids']['changes'], {'renamed': [['coin_ledge', 'coin_on_ledge']]})
            # Deleting retires the bit; a later entity never reuses it; re-adding revives it.
            ex.edit(lambda w: w['cells'][0]['entities'].pop(0))
            build_without_checker(ex, Path(tmp)/'out')
            ex.edit(lambda w: w['cells'][0]['entities'].append({'id': 'coin_late', 'type': 'coin', 'position': [41, 1, 41]}))
            build_without_checker(ex, Path(tmp)/'out')
            lock = json.loads(ex.lock.read_text())
            self.assertEqual(lock['retired'], {'coin_new': 2})
            self.assertEqual(lock['bits']['coin_late'], 3)
            ex.edit(lambda w: w['cells'][0]['entities'].append({'id': 'coin_new', 'type': 'coin', 'position': [42, 1, 41]}))
            report = build_without_checker(ex, Path(tmp)/'out')
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
                build_without_checker(ex, Path(tmp)/'out', locked=True)
            self.assertFalse(ex.lock.exists())
            build_without_checker(ex, Path(tmp)/'out')
            build_without_checker(ex, Path(tmp)/'out', locked=True)     # nothing changes: fine
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
        for name in ('test_room', 'two_districts'):
            with self.subTest(world=name), tempfile.TemporaryDirectory() as tmp:
                ex = Example(tmp, name, keep_lock=True)
                self.assertTrue(ex.lock.exists())
                self.assertEqual(ex.compile().lock_changes, {})


class BuildTests(unittest.TestCase):
    def test_builds_are_deterministic_and_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Example(Path(tmp)/'a', 'two_districts'), Example(Path(tmp)/'b', 'two_districts')
            ra = a.build(Path(tmp)/'out_a')
            rb = b.build(Path(tmp)/'out_b')
            for f in ('two_districts.world.bin', 'two_districts.akr', 'city.game.akr', 'two_districts.swatch',
                      'two_districts.ids.json', 'report.json'):
                self.assertEqual((Path(tmp)/'out_a'/f).read_bytes(), (Path(tmp)/'out_b'/f).read_bytes(), f)
            self.assertEqual(sorted(ra['files']), ['city.game.akr', 'report.json', 'source', 'two_districts.akr',
                                                   'two_districts.ids.json', 'two_districts.swatch', 'two_districts.world.bin',
                                                   'verification'])
            source = sorted(str(p.relative_to(Path(tmp)/'out_a'/'source')) for p in (Path(tmp)/'out_a'/'source').rglob('*.json'))
            self.assertIn('cells/shrine_gate.cell.json', source)
            self.assertIn('assets/shop.asset.json', source)
            self.assertIn('city.game.json', source)
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
            report = build_without_checker(ex, Path(tmp)/'out')
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

    def test_assets_must_pass_their_own_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp)
            # Two boxes that cut through each other fail the Asset Checker's geometry audit.
            ex.edit(lambda a: a['nodes'].append({'id': 'spike', 'op': 'box', 'size': [3, 0.2, 0.2],
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

    @checker_ready
    def test_required_policies_run_and_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Example(tmp).build(Path(tmp)/'out')
            self.assertEqual(report['assets']['coin']['verification'], 'passed')
            self.assertEqual(report['assets']['ramp']['verification'], 'none')


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
            report = build_without_checker(ex, out)
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

    def test_preview_renders_each_region_and_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = Example(tmp, 'two_districts')
            out = Path(tmp)/'out'
            code, report = cli('preview', ex.world, '-o', out, '--compiler', COMPILER, '--runner', RUNNER, '--probe', PROBE)
            self.assertEqual(code, 0, report)
            views = report['preview']['views']
            self.assertEqual([(v['cell'], v['variant']) for v in views],
                             [('downtown_a', 'day'), ('downtown_a', 'night'), ('shrine_gate', 'day'), ('shrine_gate', 'night')])
            self.assertTrue(all(v['stats']['tris_dropped'] == 0 and v['stats']['tris'] > 0 for v in views))
            self.assertTrue((out/'preview'/'contact.png').is_file())
            day, night = ((out/v['image']).read_bytes() for v in views[:2])
            self.assertNotEqual(day, night, 'the night variant recolours the scene')
            self.assertEqual(sorted(p.name for p in out.iterdir() if p.name.startswith('.')), [])

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


if __name__ == '__main__':
    unittest.main()
