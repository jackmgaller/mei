"""The Asset Kit's authoring module (tools/assetkit/author.py). Run:
python3 -m unittest discover -s tests -p test_author.py

Python only: the recipes it builds are checked with the kit's schema, its compiler and
`mei_assets.py validate`, and the generators ported to it are run in a scratch copy and compared
with their committed recipes byte for byte.
"""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from assetkit import author as A
from assetkit.compiler import compile_recipe
from assetkit.geometry import AssetError

# The generators written with the module, and the recipes each writes beside itself.
PORTED = {
    'carts/garden/shrinetown/assets/arch_wall_gate_bar/gen.py':
        ['arch_wall_gate_bar', 'arch_wall_gate_bar_lifted', 'arch_wall_gate_bar_col'],
    'carts/garden/shrinetown/assets/culvert_deck/make_culvert_deck.py':
        ['culvert_deck', 'culvert_deck_col'],
    'carts/garden/shrinetown/assets/sports_tyre_steps/make_sports_tyre_steps.py':
        ['sports_tyre_steps', 'sports_tyre_steps_col'],
}
MATS = {'stone': {'color': '#a8a69e', 'palette': True}, 'wood': {'color': '#8a6446'},
        'sign': {'color': '#d04030'}}


def every_op():
    """One node of each operation, transformed, with faces, decals and a modifier."""
    m = A.Mesh('panel')
    m.face('wood', [(-0.5, 2.0, 1.0), (0.5, 2.0, 1.0), (0.5, 1.5, 1.0), (-0.5, 1.5, 1.0)],
           out=(0, 0, -1))
    return [
        A.box('base', [2, 0.2, 2], [0, 0.1, 0], 'stone', open=['bottom'],
              decals=[A.decal('plate', 'back', 'sign', [0.4, 0.1])]),
        A.box_extents('step', -0.5, 0.5, 0.2, 0.35, -1.6, -1.0, 'stone', open=['bottom']),
        A.cylinder('post', 0.1, 1.8, [0, 1.1, 0], 'wood', segments=6, faces={'top': 'stone'}),
        A.cone('cap', 0.2, 0.3, [0, 2.15, 0], 'stone', segments=6),
        A.sphere('knob', 0.1, [0.6, 0.4, 0.6], 'stone', rings=3, segments=6),
        A.lathe('urn', [[0, 0], [0.15, 0.05], [0.12, 0.3], [0, 0.32]], 'stone',
                [-0.6, 0.2, 0.6], segments=8),
        A.extrude('ramp', [[0, 0], [0.6, 0], [0, 0.2]], 0.4, 'stone', [0.7, 0.2, -0.6]),
        A.loft('plinth', [A.section(0, [[-0.1, -0.1], [0.1, -0.1], [0.1, 0.1], [-0.1, 0.1]]),
                          A.section(0.2, [[-0.05, -0.05], [0.05, -0.05], [0.05, 0.05],
                                          [-0.05, 0.05]])],
               'stone', [-0.7, 0.2, -0.6]),
        A.group('rail', [A.box('bar', [0.05, 0.05, 1.2], None, 'wood')], [0.9, 0.6, 0],
                modifiers=[A.mirror('x')]),
        A.instance('knob_2', 'knob', [0.6, 0.4, -0.2]),
        A.quad_z('sign', 'sign', -0.3, 0.3, 0.6, 0.9, -1.0),
        m,
    ]


def sample():
    return A.recipe('sample', MATS, every_op(), budget=1200,
                    prototypes={'knob': A.sphere('knob', 0.1, None, 'stone', rings=3,
                                                 segments=6)},
                    lod=A.lod([(20, [A.box('body', [2, 2.3, 2], [0, 1.15, 0], 'stone',
                                           open=['bottom'])])], cull=60, band=2))


def normal(pts):
    n = A.newell(pts)
    return [c/math.sqrt(sum(x*x for x in n)) for c in n]


class BuilderTests(unittest.TestCase):
    def test_box_keys_and_transform_order(self):
        n = A.box('b', [1, 2, 3], [0, 1, 0], 'wood', open=['bottom'], faces={'back': 'sign'},
                  decals=[A.decal('d', 'front', 'sign', [0.2, 0.2], [0, 0.1])],
                  modifiers=[A.array(2, [2, 0, 0])], rotate=[0, 90, 0], scale=[1, 1, 2],
                  pivot=[0, 0, 0])
        self.assertEqual(list(n), ['id', 'op', 'size', 'material', 'open', 'faces', 'decals',
                                   'modifiers', 'transform'])
        self.assertEqual(list(n['transform']), ['pivot', 'scale', 'rotate', 'translate'])
        self.assertEqual(n['decals'][0], {'id': 'd', 'face': 'front', 'material': 'sign',
                                          'size': [0.2, 0.2], 'at': [0, 0.1]})
        self.assertEqual(A.box('b', [1, 1, 1]), {'id': 'b', 'op': 'box', 'size': [1, 1, 1]})

    def test_box_extents_is_box_by_size_and_centre(self):
        self.assertEqual(A.box_extents('b', -1, 3, 0, 2, -0.5, 0.5, 'wood', open=['bottom']),
                         A.box('b', [4, 2, 1.0], [1.0, 1.0, 0.0], 'wood', open=['bottom']))

    def test_optional_fields_left_out(self):
        self.assertEqual(A.cylinder('c', 0.5, 2), {'id': 'c', 'op': 'cylinder', 'radius': 0.5,
                                                   'height': 2})
        self.assertEqual(list(A.cylinder('c', 0.5, 2, [0, 1, 0], 'wood', segments=6, caps=False)),
                         ['id', 'op', 'radius', 'height', 'segments', 'caps', 'material',
                          'transform'])
        self.assertEqual(list(A.sphere('s', 1, segments=8, rings=4)),
                         ['id', 'op', 'radius', 'rings', 'segments'])
        self.assertEqual(list(A.quad('q', 'wood', [[0, 1, 0], [1, 1, 0], [1, 0, 0], [0, 0, 0]])),
                         ['id', 'op', 'material', 'vertices', 'faces'])
        self.assertEqual(A.mirror('x'), {'op': 'mirror', 'axis': 'x'})
        self.assertIsNone(A.transform())

    def test_axis_quads_face_the_way_named(self):
        for q, want in ((A.quad_z('q', 'm', 0, 1, 0, 1, 0), [0, 0, -1]),
                        (A.quad_z('q', 'm', 0, 1, 0, 1, 0, facing=1), [0, 0, 1]),
                        (A.quad_x('q', 'm', 0, 1, 0, 1, 0), [1, 0, 0]),
                        (A.quad_x('q', 'm', 0, 1, 0, 1, 0, facing=-1), [-1, 0, 0]),
                        (A.quad_y('q', 'm', 0, 1, 0, 1, 0), [0, 1, 0]),
                        (A.quad_y('q', 'm', 0, 1, 0, 1, 0, up=False), [0, -1, 0])):
            with self.subTest(want=want):
                self.assertEqual(normal(q['vertices']), want)

    def test_box_sides_face_outward(self):
        want = {'top': [0, 1, 0], 'bottom': [0, -1, 0], 'left': [-1, 0, 0], 'right': [1, 0, 0],
                'back': [0, 0, -1], 'front': [0, 0, 1]}
        for side, pts in A.box_sides(-1, 1, 0, 2, -1, 1).items():
            self.assertEqual(normal(pts), want[side], side)

    def test_wind_and_outward(self):
        v = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
        self.assertEqual(A.wind(v, [0, 1, 2, 3], [0, 0, 1]), [0, 1, 2, 3])
        self.assertEqual(A.wind(v, [0, 1, 2, 3], [0, 0, -1]), [3, 2, 1, 0])
        cube = [[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)]
        faces = A.outward(cube, [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6],
                                 [0, 2, 6, 4], [1, 5, 7, 3]])
        for f in faces:
            pts = [cube[i] for i in f]
            mid = [sum(p[k] for p in pts)/4-0.5 for k in range(3)]
            self.assertGreater(sum(a*b for a, b in zip(normal(pts), mid)), 0)


class MeshTests(unittest.TestCase):
    def test_faces_keep_their_corners_unless_shared(self):
        quad = [(0, 1, 0), (1, 1, 0), (1, 0, 0), (0, 0, 0)]
        m = A.Mesh('m')
        m.face('a', quad)
        m.face('b', quad)
        self.assertEqual(len(m.vertices), 8)
        s = A.Mesh('m', share=True)
        s.face('a', quad)
        s.face('b', quad)
        self.assertEqual(len(s.vertices), 4)
        self.assertEqual(s.faces, [[0, 1, 2, 3], [0, 1, 2, 3]])
        self.assertEqual(m.triangles(), 4)

    def test_node_and_uvs(self):
        m = A.Mesh('m')
        m.face('a', [(0, 1, 0), (1, 1, 0), (1, 0, 0)], uvs=[(0, 0), (1, 0), (1, 1)])
        m.face('a', [(0, 1, 1), (1, 1, 1), (1, 0, 1)])
        n = m.node()
        self.assertEqual(list(n), ['id', 'op', 'vertices', 'faces', 'face_materials', 'uvs'])
        self.assertEqual(n['face_materials'], ['a', 'a'])
        self.assertEqual(n['uvs'][3:], [[0, 0]]*3)
        self.assertNotIn('uvs', A.Mesh('x').node())

    def test_face_out_reverses_corners_and_uvs(self):
        m = A.Mesh('m')
        m.face('a', [(0, 0, 0), (1, 0, 0), (1, 1, 0)], uvs=[(0, 1), (1, 1), (1, 0)],
               out=(0, 0, -1))
        self.assertEqual(normal([m.vertices[i] for i in m.faces[0]]), [0, 0, -1])
        self.assertEqual(m.uvs[0], [1, 0])

    def test_box_by_side(self):
        m = A.Mesh('m')
        m.box({'*': 'a', 'top': 'b'}, 0, 1, 0, 1, 0, 1, open=('bottom',))
        self.assertEqual(len(m.faces), 5)
        self.assertEqual(sorted(m.materials), ['a', 'a', 'a', 'a', 'b'])


class RecipeTests(unittest.TestCase):
    def test_skeleton(self):
        r = A.recipe('thing', MATS, [A.box('b', [1, 1, 1], None, 'wood')], budget=12)
        self.assertEqual(list(r), ['format', 'version', 'name', 'budget', 'materials', 'lighting',
                                   'verification', 'nodes'])
        self.assertEqual(r['budget'], {'triangles': 12})
        self.assertEqual(r['lighting'], {'mode': 'vertical', 'ambient': 0.5})
        self.assertEqual(r['verification'], {'required': True, 'depth': True,
                                             'perspective': True})
        bare = A.recipe('thing', None, [A.box('b', [1, 1, 1])], lighting=None, verification=None)
        self.assertEqual(list(bare), ['format', 'version', 'name', 'nodes'])

    def test_lod_and_meshes(self):
        empty = A.Mesh('empty')
        lv = A.lod([(20, [A.box('b', [1, 1, 1])]), A.level(40, [A.box('c', [1, 1, 1])])],
                   cull=90, band=2)
        self.assertEqual(list(lv), ['levels', 'cull', 'band'])
        self.assertEqual(lv['levels'][0], {'distance': 20, 'nodes': [A.box('b', [1, 1, 1])]})
        self.assertEqual(A.lod(cull=60), {'cull': 60})
        m = A.Mesh('m')
        m.face('wood', [(0, 1, 0), (1, 1, 0), (1, 0, 0)])
        r = A.recipe('thing', MATS, [m, empty], lod=A.lod([(20, [m, empty])]))
        self.assertEqual([n['id'] for n in r['nodes']], ['m'])
        self.assertEqual([n['id'] for n in r['lod']['levels'][0]['nodes']], ['m'])

    def test_collision_fills_its_material(self):
        m = A.Mesh('body')
        m.box(None, 0, 1, 0, 1, 0, 1)
        c = A.collision('thing_col', [
            A.box_extents('wall', 0, 1, 0, 2, 0, 0.2),
            A.group('g', [A.box('a', [1, 1, 1]), A.box('b', [1, 1, 1], None, 'awning')]),
            A.instance('i', 'p'), m],
            prototypes={'p': A.box('p', [1, 1, 1], None, 'solid')})
        self.assertEqual(c['materials'], {'solid': {'color': '#ffffff', 'palette': True}})
        wall, g, i, body = c['nodes']
        self.assertEqual(list(wall), ['id', 'op', 'size', 'material', 'transform'])
        self.assertEqual(wall['material'], 'solid')
        self.assertEqual([n['material'] for n in g['children']], ['solid', 'awning'])
        self.assertNotIn('material', g)
        self.assertNotIn('material', i)
        self.assertEqual(body['face_materials'], ['solid']*6)
        self.assertEqual(A.collision('x', [A.box('a', [1, 1, 1])], color='#c8c4b8')['materials'],
                         {'solid': {'color': '#c8c4b8', 'palette': True}})


class WriteTests(unittest.TestCase):
    def test_rounding(self):
        r = A.recipe('thing', MATS, [A.box('b', [0.1+0.2, 2, 1/3], [-1e-9, 1, 2.0], 'wood')])
        n = A.tidy(r)['nodes'][0]
        self.assertEqual(n['size'], [0.3, 2, 0.3333])
        self.assertEqual(n['transform']['translate'], [0.0, 1, 2.0])
        self.assertEqual(str(n['transform']['translate'][0]), '0.0')     # not -0.0
        self.assertIsInstance(n['size'][1], int)
        self.assertIs(A.tidy({'a': True})['a'], True)
        self.assertEqual(A.tidy([1.23456], places=2), [1.23])
        with self.assertRaises(ValueError):
            A.tidy([float('nan')])

    def test_hand_written_keys_put_in_order(self):
        r = {'nodes': [{'transform': {'translate': [0, 1, 0], 'rotate': [0, 45, 0]},
                        'material': 'wood', 'open': ['bottom'], 'size': [1, 1, 1], 'op': 'box',
                        'id': 'b'}],
             'materials': MATS, 'name': 'thing', 'version': 1, 'format': 'mei-asset',
             'lod': {'cull': 50, 'levels': [{'nodes': [{'op': 'box', 'size': [1, 1, 1]}],
                                             'distance': 10}]}}
        t = A.tidy(r)
        self.assertEqual(list(t), ['format', 'version', 'name', 'materials', 'nodes', 'lod'])
        self.assertEqual(list(t['nodes'][0]), ['id', 'op', 'size', 'material', 'open',
                                               'transform'])
        self.assertEqual(list(t['nodes'][0]['transform']), ['rotate', 'translate'])
        self.assertEqual(list(t['lod']), ['levels', 'cull'])
        self.assertEqual(list(t['lod']['levels'][0]), ['distance', 'nodes'])

    def test_write_is_stable_and_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = A.write(Path(tmp)/'s.asset.json', sample())
            text = path.read_text()
            self.assertTrue(text.startswith('{\n "format": "mei-asset",\n'))
            self.assertTrue(text.endswith('}\n'))
            self.assertEqual(A.dumps(json.loads(text)), text)
            with self.assertRaises(AssetError):
                A.write(Path(tmp)/'bad.asset.json',
                        A.recipe('thing', MATS, [A.box('Bad Id', [1, 1, 1])]))
            with self.assertRaises(AssetError):
                A.dumps(A.recipe('thing', MATS, [A.box('b', [1, -1, 1])]))
            self.assertFalse((Path(tmp)/'bad.asset.json').exists())

    def test_built_recipes_compile_and_validate(self):
        r = sample()
        mesh, _, report = compile_recipe(json.loads(A.dumps(r)))
        self.assertGreater(len(mesh.faces), 0)
        with tempfile.TemporaryDirectory() as tmp:
            for rec in (r, A.collision('sample_col', [A.box_extents('b', -1, 1, 0, 2.3, -1, 1,
                                                                    open=['bottom'])])):
                path = A.write(Path(tmp)/f'{rec["name"]}.asset.json', rec)
                out = subprocess.run([sys.executable, str(ROOT/'tools/mei_assets.py'), 'validate',
                                      str(path)], capture_output=True, text=True)
                with self.subTest(recipe=rec['name']):
                    self.assertEqual(out.returncode, 0, out.stdout+out.stderr)
                    self.assertTrue(json.loads(out.stdout)['ok'])


class PortedGeneratorTests(unittest.TestCase):
    def test_ported_generators_write_their_committed_recipes(self):
        """Each runs in a scratch tree (its folder copied, tools/ linked) so the checkout is
        not written."""
        with tempfile.TemporaryDirectory() as tmp:
            os.symlink(ROOT/'tools', Path(tmp)/'tools')
            for script, names in PORTED.items():
                src = ROOT/script
                dst = Path(tmp)/script
                shutil.copytree(src.parent, dst.parent,
                                ignore=shutil.ignore_patterns('*.asset.json', 'art'))
                out = subprocess.run([sys.executable, str(dst)], capture_output=True, text=True,
                                     env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
                self.assertEqual(out.returncode, 0, out.stderr)
                for name in names:
                    with self.subTest(recipe=name):
                        self.assertEqual((dst.parent/f'{name}.asset.json').read_bytes(),
                                         (src.parent/f'{name}.asset.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
