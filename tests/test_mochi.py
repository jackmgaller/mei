"""Mochi, the World Kit's game-schema language (tools/worldkit/mochi.py, docs/WORLDKIT.md). Run:
python3 -m unittest discover -s tests -p test_mochi.py

Parsing, formatting, the round trip and errors need only Python. The build test compares a world
built from the Mochi example schema with the same world given the JSON form
(tests/worldkit/garden.game.json); it needs meic and mei-headless (MEIC, RUN, PROBE as in
test_worldkit.py) and is skipped without them.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get('MEIC', ROOT/'build/meic')).resolve()
RUNNER = Path(os.environ.get('RUN', ROOT/'build/mei-headless')).resolve()
PROBE = Path(os.environ.get('PROBE', ROOT/'build/mei-asset-probe')).resolve()
sys.path.insert(0, str(ROOT/'tools'))
from worldkit import mochi  # noqa: E402
from worldkit.build import build, compile_source  # noqa: E402
from worldkit.schema import WorldError  # noqa: E402
from worldkit.world import load_game  # noqa: E402

EXAMPLES = ROOT/'examples'/'worlds'
GARDEN_JSON = ROOT/'tests'/'worldkit'/'garden.game.json'
CLI = [sys.executable, str(ROOT/'tools'/'mei_world.py')]
tools_built = unittest.skipUnless(COMPILER.exists() and RUNNER.exists(), 'meic and mei-headless are not built')

PROBE_LINE = 'probe { radius = 0.3  floor_max_degrees = 40 }\n'
SINK = '''// Every construct, written loosely; the formatter tidies it.
game sink   // a trailing comment

worlds hub, far_away
probe {
  radius = 0.25 height = 1.8
  step = 0.3
  floor_max_degrees = 45
  ceiling_max_degrees = 30
}

type plain
saved type flag
saved type everything { on: bool = true
  off:    bool
  small:  u8 = 255
  medium: s16 = -32768
  large:  s32 = -2147483648
  whole:  fixed = 2
  part:   fixed = -0.5
  tiny:   fixed = 1e-05
  spot:   vec3 = [0, -1.5, 2]
  size:   vec3
  mode:   a | b |
          c = c
  only:   | solo
  clash:  u8 | name = name
  label:  name = hello
  must:   ref
  maybe:  ref ?
  exit:   world = far_away
  home:   world
}
type empty {}
'''
SINK_JSON = {
    'format': 'mei-world-game', 'version': 1, 'name': 'sink',
    'probe': {'radius': 0.25, 'height': 1.8, 'step': 0.3, 'floor_max_degrees': 45, 'ceiling_max_degrees': 30},
    'types': {
        'plain': {}, 'flag': {'saved': True},
        'everything': {'saved': True, 'params': {
            'on': {'type': 'bool', 'default': True}, 'off': {'type': 'bool'},
            'small': {'type': 'u8', 'default': 255}, 'medium': {'type': 's16', 'default': -32768},
            'large': {'type': 's32', 'default': -2147483648}, 'whole': {'type': 'fixed', 'default': 2},
            'part': {'type': 'fixed', 'default': -0.5}, 'tiny': {'type': 'fixed', 'default': 1e-05},
            'spot': {'type': 'vec3', 'default': [0, -1.5, 2]}, 'size': {'type': 'vec3'},
            'mode': {'type': 'enum', 'values': ['a', 'b', 'c'], 'default': 'c'},
            'only': {'type': 'enum', 'values': ['solo']},
            'clash': {'type': 'enum', 'values': ['u8', 'name'], 'default': 'name'},
            'label': {'type': 'name', 'default': 'hello'},
            'must': {'type': 'entity_ref', 'required': True}, 'maybe': {'type': 'entity_ref'},
            'exit': {'type': 'world_ref', 'default': 'far_away'}, 'home': {'type': 'world_ref'}}},
        'empty': {}},
    'worlds': ['hub', 'far_away'],
}


def ordered(value):
    """JSON text that keeps key order, so equal means equal in order and int/float too."""
    return json.dumps(value)


def load_text(text, tmp):
    path = Path(tmp)/'g.game.mochi'
    path.write_text(text)
    return load_game(str(path))


def cli(*args):
    r = subprocess.run(CLI + [str(a) for a in args], capture_output=True, text=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    return r.returncode, json.loads(r.stdout)


class ParseTests(unittest.TestCase):
    def test_every_construct(self):
        game, at = mochi.parse(SINK)
        self.assertEqual(ordered(game), ordered(SINK_JSON))
        self.assertEqual(at['/types/everything/params/clash/default'], (27, 23))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(ordered(load_text(SINK, tmp)), ordered(SINK_JSON))   # and it validates

    def test_canonical_format_round_trips(self):
        text = mochi.format(SINK_JSON)
        self.assertIn('  mode:   a | b | c = c\n', text)
        self.assertIn('  only:   | solo\n', text)
        self.assertIn('  maybe:  ref?\n', text)
        self.assertIn('  tiny:   fixed = 1e-05\n', text)
        self.assertIn('worlds hub, far_away\n', text)
        self.assertEqual(ordered(mochi.parse(text)[0]), ordered(SINK_JSON))
        self.assertEqual(mochi.format(mochi.parse(text)[0]), text)

    def test_examples_round_trip(self):
        garden = json.loads(GARDEN_JSON.read_text())
        self.assertEqual(ordered(load_game(str(EXAMPLES/'test_room'/'garden.game.mochi'))), ordered(garden))
        self.assertEqual(mochi.format(garden), (EXAMPLES/'test_room'/'garden.game.mochi').read_text())
        for path in (EXAMPLES/'test_room'/'garden.game.mochi', EXAMPLES/'two_districts'/'city.game.mochi'):
            with self.subTest(path=path.name):
                game = load_game(str(path))
                self.assertEqual(mochi.format(game), path.read_text())        # the examples are canonical
                self.assertEqual(ordered(mochi.parse(mochi.format(game))[0]), ordered(game))

    def test_spellings_that_mean_the_same_are_normalised(self):
        game = dict(SINK_JSON, types={'a': {'saved': False, 'params': {}},
                                      'b': {'params': {'r': {'type': 'entity_ref', 'required': False}}}})
        self.assertEqual(mochi.parse(mochi.format(game))[0]['types'], {'a': {}, 'b': {'params': {'r': {'type': 'entity_ref'}}}})

    def test_schema_command_teaches_mochi(self):
        code, schema = cli('schema')
        self.assertEqual(code, 0)
        contract = schema['$defs']['game']['x-mochi']
        self.assertTrue(contract['grammar'] and contract['rules'])
        with tempfile.TemporaryDirectory() as tmp:
            game = load_text(contract['example'], tmp)
        self.assertEqual(mochi.format(game), contract['example'].split('\n', 1)[1])
        code, schema = cli('schema', '--game', EXAMPLES/'test_room'/'garden.game.mochi')
        self.assertEqual(code, 0)
        self.assertIn('x-mochi', schema['$defs']['game'])


class ErrorTests(unittest.TestCase):
    CASES = [
        # (text, line, column, path, part of the message)
        ('', 1, 1, '/input', 'starts with game NAME'),
        ('game Garden', 1, 6, '/name', 'Try garden'),
        ('game g\nprobe { radius 0.3 }', 2, 16, '/probe/radius', 'Expected = after radius'),
        ('game g\nprobe { radus = 0.3 }', 2, 9, '/probe/radus', 'Did you mean radius?'),
        ('game g\nprobe { radius = .5 floor_max_degrees = 40 }', 2, 18, '/probe/radius', 'not a number'),
        ('game g\nprobe { radius = 0 floor_max_degrees = 40 }', 2, 18, '/probe/radius', 'positive'),
        ('game g\nprobe { radius = 0.3 }', 2, 1, '/probe/floor_max_degrees', 'probe needs floor_max_degrees'),
        ('game g\ntype t', 2, 7, '/probe', 'no probe'),
        ('game g\n' + PROBE_LINE + 'typ t', 3, 1, '/input', 'Did you mean type?'),
        ('game g\n' + PROBE_LINE + '# note', 3, 1, '/input', 'comments start with //'),
        ('game g\n' + PROBE_LINE + 'saved coin', 3, 7, '/input', 'Expected type after saved'),
        ('game g\n' + PROBE_LINE + 'game h', 3, 1, '/input', 'only once'),
        ('game g\n' + PROBE_LINE + 'worlds a b', 3, 10, '/worlds', 'worlds a, b'),
        ('game g\n' + PROBE_LINE + 'worlds a, a', 3, 11, '/worlds/1', 'listed twice'),
        ('game g\n' + PROBE_LINE + 'type t\ntype t', 4, 6, '/types/t', 'already declared at line 3'),
        ('game g\n' + PROBE_LINE + 'type t {\n  a: u8\n', 5, 1, '/types/t', 'opened at line 3'),
        ('game g\n' + PROBE_LINE + 'type t {\n  a u8\n}', 4, 5, '/types/t/params/a', 'Expected : after field'),
        ('game g\n' + PROBE_LINE + 'type t {\n  a: u8,\n  b: u8\n}', 4, 8, '/types/t', 'need no separator'),
        ('game g\n' + PROBE_LINE + 'type t {\n  a: u8\n  a: s16\n}', 5, 3, '/types/t/params/a', 'already declared at line 4'),
        ('game g\n' + PROBE_LINE + 'type t {\n  a: u9\n}', 4, 6, '/types/t/params/a/type', 'one-value enum is | u9'),
        ('game g\n' + PROBE_LINE + 'type t {\n  a: entity_ref\n}', 4, 6, '/types/t/params/a/type', 'ref?'),
        ('game g\n' + PROBE_LINE + 'type t {\n  a: "x"\n}', 4, 6, '/types/t/params/a/type', 'no strings'),
        ('game g\n' + PROBE_LINE + 'type t {\n  a: u8?\n}', 4, 8, '/types/t/params/a', 'Only a ref can be optional'),
        ('game g\n' + PROBE_LINE + 'type t {\n  a: ref = b\n}', 4, 10, '/types/t/params/a/default', 'ref has no default'),
        ('game g\n' + PROBE_LINE + 'type t {\n  a: x | y | x\n}', 4, 14, '/types/t/params/a/values/2', 'listed twice'),
        ('game g\n' + PROBE_LINE + 'type t {\n  a: bool = yes\n}', 4, 13, '/types/t/params/a/default', 'true or false'),
        ('game g\n' + PROBE_LINE + 'type t {\n  a: vec3 = [1, 2]\n}', 4, 13, '/types/t/params/a/default', 'three numbers'),
        # Found by the kit's own validation, mapped back to the line.
        ('game g\n' + PROBE_LINE + 'type t {\n  a: u8 = 300\n}', 4, 11, '/types/t/params/a/default', 'Maximum is 255'),
        ('game g\n' + PROBE_LINE + 'type t {\n  a: s16 = 1.5\n}', 4, 12, '/types/t/params/a/default', 'integer'),
        ('game g\n' + PROBE_LINE + 'type t {\n  a: x | y = z\n}', 4, 14, '/types/t/params/a/default', 'one of'),
        ('game g\n' + PROBE_LINE + 'type t {\n  len: u8\n}', 4, 3, '/types/t/params/len', 'Akari keyword'),
        ('game g\n' + PROBE_LINE + 'type t {\n  w: world\n}', 4, 3, '/types/t/params/w', 'add worlds'),
        ('game g\n' + PROBE_LINE + 'worlds a\ntype t {\n  w: world = b\n}', 5, 14, '/types/t/params/w/default', 'one of'),
    ]

    def test_errors_give_line_column_and_a_fix(self):
        with tempfile.TemporaryDirectory() as tmp:
            for text, line, column, path, message in self.CASES:
                with self.subTest(text=text), self.assertRaises(WorldError) as error:
                    load_text(text, tmp)
                e = error.exception
                self.assertEqual((e.line, e.column, e.path), (line, column, path), str(e))
                self.assertIn(message, str(e))
                self.assertTrue(e.file.endswith('g.game.mochi'))

    def test_cli_reports_file_line_and_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(EXAMPLES/'test_room', Path(tmp)/'room', ignore=shutil.ignore_patterns('*.ids.json'))
            game = Path(tmp)/'room'/'garden.game.mochi'
            game.write_text(game.read_text().replace('count:       u8 = 1', 'count:       u8 = 256'))
            for args in (('validate', Path(tmp)/'room'/'test_room.world.json'), ('schema', '--game', game)):
                code, out = cli(*args)
                self.assertEqual((code, out['ok']), (1, False))
                failure = out['errors'][0]
                self.assertEqual((failure['path'], failure['line'], failure['column']),
                                 ('/types/trigger/params/count/default', 19, 21))
                self.assertEqual(Path(failure['file']).name, 'garden.game.mochi')


class ConvertTests(unittest.TestCase):
    def test_convert_both_ways(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = cli('convert', GARDEN_JSON, '-o', Path(tmp)/'garden.game.mochi')
            self.assertEqual(code, 0, out)
            self.assertEqual(Path(out['output']).read_text(), (EXAMPLES/'test_room'/'garden.game.mochi').read_text())
            code, out = cli('convert', Path(tmp)/'garden.game.mochi', '-o', Path(tmp)/'garden.game.json')
            self.assertEqual(code, 0, out)
            self.assertEqual(Path(out['output']).read_text(), GARDEN_JSON.read_text().rstrip('\n') + '\n')
            code, out = cli('convert', Path(tmp)/'garden.game.mochi')
            self.assertEqual((code, out['format']), (0, 'json'))
            self.assertEqual(ordered(out['game']), ordered(json.loads(GARDEN_JSON.read_text())))
            code, out = cli('convert', GARDEN_JSON)
            self.assertEqual((code, out['format'], out['text']), (0, 'mochi', mochi.format(json.loads(GARDEN_JSON.read_text()))))
            code, out = cli('convert', GARDEN_JSON, '-o', Path(tmp)/'garden.game.mochi')
            self.assertEqual((code, out['errors'][0]['path']), (1, '/arguments'))
            self.assertIn('--force', out['errors'][0]['message'])
            code, out = cli('convert', GARDEN_JSON, '-o', Path(tmp)/'x.json')
            self.assertIn('*.mochi', out['errors'][0]['message'])


class BuildTests(unittest.TestCase):
    def worlds(self, tmp):
        """The test room twice: with its Mochi game schema, and with the same schema as JSON."""
        a, b = Path(tmp)/'mochi', Path(tmp)/'json'
        for d in (a, b):
            shutil.copytree(EXAMPLES/'test_room', d, ignore=shutil.ignore_patterns('*.ids.json'))
        shutil.copy(GARDEN_JSON, b/'garden.game.json')
        (b/'garden.game.mochi').unlink()
        world = json.loads((b/'test_room.world.json').read_text())
        world['game'] = 'garden.game.json'
        (b/'test_room.world.json').write_text(json.dumps(world))
        return a/'test_room.world.json', b/'test_room.world.json'

    def test_mochi_and_json_compile_identically(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = (compile_source(str(w))[1] for w in self.worlds(tmp))
            self.assertEqual((a.pack, a.akr, a.game_akr), (b.pack, b.akr, b.game_akr))
            self.assertEqual(a.report['game_sha256'], b.report['game_sha256'])

    @tools_built
    def test_mochi_and_json_build_byte_identical_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            outs = []
            for world in self.worlds(tmp):
                coin = world.parent/'assets'/'coin.asset.json'
                recipe = json.loads(coin.read_text())
                recipe.pop('verification', None)        # the Asset Checker needs NumPy; not what this tests
                coin.write_text(json.dumps(recipe))
                out = world.parent.parent/(world.parent.name + '_out')
                build(str(world), out, COMPILER, RUNNER, PROBE)
                outs.append(out)
            for name in ('test_room.world.bin', 'test_room.akr', 'garden.game.akr', 'test_room.ids.json'):
                self.assertEqual((outs[0]/name).read_bytes(), (outs[1]/name).read_bytes(), name)
            self.assertEqual((outs[0]/'source'/'garden.game.mochi').read_text(),
                             (EXAMPLES/'test_room'/'garden.game.mochi').read_text())
            self.assertEqual(json.loads((outs[1]/'source'/'garden.game.json').read_text()),
                             json.loads(GARDEN_JSON.read_text()))


if __name__ == '__main__':
    unittest.main()
